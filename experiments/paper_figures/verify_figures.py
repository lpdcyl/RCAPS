"""Check output completeness and that PDFs contain vector text."""

from pathlib import Path
from xml.etree import ElementTree

import fitz
from PIL import Image


HERE = Path(__file__).resolve().parent


def main():
    scripts = [HERE / "ccf_integrated_framework.py",
               *sorted(HERE.glob("fig[0-9][0-9]_*.py"))]
    assert len(scripts) == 17, len(scripts)
    for script in scripts:
        stem = script.stem
        pdf = HERE / f"{stem}.pdf"
        png = HERE / f"{stem}.png"
        assert pdf.is_file() and png.is_file(), stem
        assert pdf.stat().st_size > 2000 and png.stat().st_size > 10000, stem
        with fitz.open(pdf) as doc:
            assert len(doc) == 1, stem
            page = doc[0]
            assert len(page.get_text().strip()) > 25, stem
            assert page.rect.width > 200 and page.rect.height > 100, stem
        with Image.open(png) as preview:
            assert min(preview.size) >= 500, (stem, preview.size)
    ElementTree.parse(HERE / "ccf_integrated_framework.svg")
    print(f"Verified {len(scripts)} PDFs and PNG previews")


if __name__ == "__main__":
    main()
