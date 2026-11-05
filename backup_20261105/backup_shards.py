"""Create smaller replacement assets for not-yet-uploaded backup archives."""
from __future__ import annotations

import json
import sys

import backup as base

GROUP = sys.argv[1]
if GROUP not in {"main", "v3"}:
    raise SystemExit("group must be main or v3")
ORIGINAL = base.HERE / ("manifest.json" if GROUP == "main" else "ignored_manifest.json")
base.MANIFEST = base.HERE / ("shard_main_manifest.json" if GROUP == "main" else "shard_v3_manifest.json")
base.TAG = "experiment-backup-20261105" + ("" if GROUP == "main" else "-v3-raw")
PREFIX = "rcaps-experiments-shard-" if GROUP == "main" else "rcaps-v3-shard-"
SHARD_LIMIT = 300_000_000


def inventory():
    if base.MANIFEST.exists():
        raise RuntimeError("Shard manifest exists; never silently replace it")
    original = json.loads(ORIGINAL.read_text(encoding="utf-8"))
    client = base.session()
    release = base.release(client)
    remote = base.api(client, "GET", "https://api.github.com/repos/lpdcyl/RCAPS/releases/" + str(release["id"]))
    present = {x["name"]: x for x in remote["assets"]}
    existing, missing = [], []
    for asset in original["assets"]:
        found = present.get(asset["name"])
        if found and found["size"] == asset["bytes"] and found.get("digest") == "sha256:" + asset["sha256"]:
            existing.append(asset)
        elif found:
            raise RuntimeError("Conflicting remote asset: " + asset["name"])
        else:
            missing.extend(asset["files"])
    by_path = {e["path"]: e for e in original["files"]}
    chunks, current, size = [], [], 0
    for path in missing:
        entry = by_path[path]
        if current and size + entry["bytes"] > SHARD_LIMIT:
            chunks.append(current)
            current, size = [], 0
        current.append(path)
        size += entry["bytes"]
    if current:
        chunks.append(current)
    assets = [{"name": PREFIX + "%03d.zip" % (i + 1), "files": names}
              for i, names in enumerate(chunks)]
    covered = [p for a in existing for p in a["files"]] + [p for a in assets for p in a["files"]]
    if len(covered) != original["file_count"] or set(covered) != set(by_path):
        raise RuntimeError("Shard coverage is incomplete")
    manifest = {"tag": base.TAG, "source_manifest": ORIGINAL.name,
                "scope": "SHA-verified smaller assets for original assets missing on GitHub",
                "file_count": len(missing), "total_bytes": sum(by_path[p]["bytes"] for p in missing),
                "files": [by_path[p] for p in missing],
                "existing_assets": existing, "assets": assets}
    base.MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("shards", GROUP, len(missing), "files", len(existing), "existing assets",
          len(assets), "new assets", flush=True)


def verify_remote():
    manifest = json.loads(base.MANIFEST.read_text(encoding="utf-8"))
    base.verify_remote()
    client = base.session()
    release = base.release(client)
    remote = base.api(client, "GET", "https://api.github.com/repos/lpdcyl/RCAPS/releases/" + str(release["id"]))
    found = {x["name"]: x for x in remote["assets"]}
    for asset in manifest["existing_assets"]:
        item = found.get(asset["name"])
        if not item or item["size"] != asset["bytes"] or item.get("digest") != "sha256:" + asset["sha256"]:
            raise RuntimeError("Missing original asset: " + asset["name"])
    print("COMPLETE_GROUP_VERIFIED", GROUP, len(manifest["existing_assets"]),
          "original assets", len(manifest["assets"]), "shard assets", flush=True)


if __name__ == "__main__":
    {"inventory": inventory, "pack": base.pack, "upload": base.upload,
     "verify-remote": verify_remote, "verify-local": base.verify_local}[sys.argv[2]]()
