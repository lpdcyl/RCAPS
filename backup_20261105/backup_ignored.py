"""Supplemental backup for ignored V3 raw traces, logs, and indexes."""
from __future__ import annotations

import json
from pathlib import Path

import backup as base

base.MANIFEST = base.HERE / "ignored_manifest.json"
base.TAG = "experiment-backup-20261105-v3-raw"


def inventory():
    if base.MANIFEST.exists():
        raise RuntimeError("Supplemental manifest exists; never replace it silently")
    raw = base.git("ls-files", "--others", "--ignored", "--exclude-standard", "-z",
                   "--", "experiments", "work3_*")
    candidates = sorted(x.decode("utf-8") for x in raw.split(b"\0") if x)
    candidates = [p for p in candidates if p.endswith((".jsonl.gz", ".log", ".json"))]
    entries = []
    for index, relative in enumerate(candidates, 1):
        path = base.ROOT / relative
        if not path.is_file() or path.is_symlink():
            continue
        linked = None
        if relative.endswith(".jsonl.gz"):
            linked = path.with_suffix("").with_suffix(".json")
        entries.append({"path": relative, "bytes": path.stat().st_size,
                        "sha256": base.sha(path),
                        "provenance": "paired_result_present_local_sha256" if linked and linked.is_file()
                        else "ignored_local_file_sha256"})
        if index % 100 == 0:
            print("hashed ignored", index, "of", len(candidates), flush=True)
    chunks, current, size = [], [], 0
    for entry in entries:
        if current and size + entry["bytes"] > base.MAX_ASSET:
            chunks.append(current)
            current, size = [], 0
        current.append(entry["path"])
        size += entry["bytes"]
    if current:
        chunks.append(current)
    assets = [{"name": "rcaps-v3-raw-%02d.zip" % (i + 1), "files": names}
              for i, names in enumerate(chunks)]
    manifest = {"tag": base.TAG, "scope": "Ignored experiment .jsonl.gz raw events, .log, and .json indexes",
                "note": "Raw events are identified by adjacent result JSON where present. The result's trace_sha256 is the input trace digest, not the raw event file digest. No outcome is reclassified.",
                "git_base": base.git("rev-parse", "HEAD").decode().strip(),
                "file_count": len(entries), "total_bytes": sum(e["bytes"] for e in entries),
                "files": entries, "assets": assets}
    base.MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ignored inventory", len(entries), "files", manifest["total_bytes"],
          "bytes", len(assets), "assets", flush=True)


if __name__ == "__main__":
    import sys
    {"inventory": inventory, "pack": base.pack, "upload": base.upload,
     "verify-remote": base.verify_remote, "verify-local": base.verify_local}[sys.argv[1]]()
