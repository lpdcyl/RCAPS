"""Extract manuscript paragraph/table text from DOCX without changing it."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def text_of(node):
    return "".join(x.text or "" for x in node.iter(W + "t")).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with zipfile.ZipFile(args.source) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        styles = ET.fromstring(z.read("word/styles.xml"))
        names = {}
        for style in styles.iter(W + "style"):
            key = style.get(W + "styleId")
            name = style.find(W + "name")
            if key and name is not None:
                names[key] = name.get(W + "val") or key
        body = root.find(W + "body")
        assert body is not None
        items = []
        for node in body:
            if node.tag == W + "p":
                text = text_of(node)
                if not text:
                    continue
                ppr = node.find(W + "pPr")
                style = ppr.find(W + "pStyle") if ppr is not None else None
                style_id = style.get(W + "val") if style is not None else "Normal"
                items.append(dict(kind="paragraph", style=names.get(style_id, style_id),
                                  text=text))
            elif node.tag == W + "tbl":
                rows = []
                for tr in node.findall(W + "tr"):
                    rows.append([text_of(tc) for tc in tr.findall(W + "tc")])
                items.append(dict(kind="table", rows=rows))
    for number, item in enumerate(items):
        item["index"] = number
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(
        source=str(args.source), source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
        items=items), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PARAGRAPHS", sum(i["kind"] == "paragraph" for i in items),
          "TABLES", sum(i["kind"] == "table" for i in items))
    for item in items:
        if item["kind"] != "paragraph":
            continue
        text = item["text"]
        style = item["style"]
        if ("heading" in style.lower() or "标题" in style or
                any(text.lower().startswith(prefix) for prefix in (
                    "abstract", "introduction", "7.", "vii.", "conclusion", "evaluation"))):
            print(item["index"], style, text[:160])


if __name__ == "__main__":
    main()
