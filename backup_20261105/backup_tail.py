"""Upload the final V3 archives as small, SHA-verified binary parts."""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile

import backup as base

HERE = base.HERE
SOURCE = HERE / "shard_v3_manifest.json"
base.MANIFEST = HERE / "tail_v3_manifest.json"
base.TAG = "experiment-backup-20261105-v3-raw"
PART_BYTES = 50_000_000


def part_path(name):
    """Use the Git-backed copy after a fresh clone when no local staging file exists."""
    staged = HERE / name
    return staged if staged.is_file() else HERE / "git_parts" / name


def inventory():
    if base.MANIFEST.exists():
        raise RuntimeError("Tail manifest exists; never silently replace it")
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    client = base.session()
    release = base.release(client)
    remote = {x["name"]: x for x in base.release_assets(client, release["id"])}
    existing, missing = [], []
    for asset in source["assets"]:
        found = remote.get(asset["name"])
        if found and found["state"] == "starter" and not found.get("digest"):
            found = base.remove_incomplete_asset(client, release["id"], found)
        if found and found["state"] == "uploaded" and found["size"] == asset["bytes"] and found.get("digest") == "sha256:" + asset["sha256"]:
            existing.append(asset)
        elif found:
            raise RuntimeError("Conflicting remote asset: " + asset["name"])
        else:
            missing.append(asset)
    parts = []
    for original in missing:
        path = HERE / original["name"]
        if path.stat().st_size != original["bytes"] or base.sha(path) != original["sha256"]:
            raise RuntimeError("Original archive changed: " + original["name"])
        pieces = []
        assembled = hashlib.sha256()
        with path.open("rb") as stream:
            number = 1
            while True:
                data = stream.read(PART_BYTES)
                if not data:
                    break
                assembled.update(data)
                name = original["name"].removesuffix(".zip") + "-part%02d.bin" % number
                target = HERE / name
                digest = hashlib.sha256(data).hexdigest()
                if target.exists():
                    if target.stat().st_size != len(data) or base.sha(target) != digest:
                        raise RuntimeError("Existing part differs: " + name)
                else:
                    target.write_bytes(data)
                pieces.append({"name": name, "bytes": len(data), "sha256": digest,
                               "source_archive": original["name"], "part_index": number})
                number += 1
        if assembled.hexdigest() != original["sha256"] or sum(p["bytes"] for p in pieces) != original["bytes"]:
            raise RuntimeError("Part reconstruction mismatch: " + original["name"])
        parts.extend(pieces)
        print("split", original["name"], len(pieces), "parts", flush=True)
    existing_paths = [p for asset in existing for p in asset["files"]]
    missing_paths = [p for asset in missing for p in asset["files"]]
    by_path = {e["path"]: e for e in source["files"]}
    covered = existing_paths + missing_paths
    if len(covered) != source["file_count"] or set(covered) != set(by_path):
        raise RuntimeError("Tail does not cover the source shard manifest")
    manifest = {"tag": base.TAG, "source_manifest": SOURCE.name,
                "scope": "Replacement binary parts for V3 shard ZIPs not uploaded in full",
                "note": "Concatenate each archive's numbered parts, verify the original ZIP SHA256, then extract it.",
                "existing_shard_assets": existing, "original_archives": missing,
                "file_count": len(missing_paths),
                "total_bytes": sum(by_path[p]["bytes"] for p in missing_paths),
                "files": [by_path[p] for p in missing_paths], "assets": parts}
    base.MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("tail inventory", len(missing), "archives", len(parts), "parts",
          sum(p["bytes"] for p in parts), "bytes", flush=True)


def restore():
    manifest = json.loads(base.MANIFEST.read_text(encoding="utf-8"))
    for archive in manifest["original_archives"]:
        target = HERE / archive["name"]
        if target.exists():
            if target.stat().st_size != archive["bytes"] or base.sha(target) != archive["sha256"]:
                raise RuntimeError("Existing archive differs: " + archive["name"])
            print("already restored", archive["name"], flush=True)
            continue
        parts = sorted((p for p in manifest["assets"] if p["source_archive"] == archive["name"]),
                       key=lambda p: p["part_index"])
        if not parts or [p["part_index"] for p in parts] != list(range(1, len(parts) + 1)):
            raise RuntimeError("Missing part index for " + archive["name"])
        temp = HERE / (archive["name"] + ".restoring")
        if temp.exists():
            raise RuntimeError("Partial restore exists: " + temp.name)
        digest = hashlib.sha256()
        total = 0
        with temp.open("wb") as output:
            for part in parts:
                path = part_path(part["name"])
                if path.stat().st_size != part["bytes"] or base.sha(path) != part["sha256"]:
                    raise RuntimeError("Missing or changed part: " + part["name"])
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                        output.write(block)
                        digest.update(block)
                        total += len(block)
        if total != archive["bytes"] or digest.hexdigest() != archive["sha256"]:
            raise RuntimeError("Reconstructed archive mismatch: " + archive["name"])
        with zipfile.ZipFile(temp) as zipped:
            if zipped.testzip() is not None:
                raise RuntimeError("Reconstructed ZIP CRC failed: " + archive["name"])
        temp.rename(target)
        print("restored", archive["name"], flush=True)


def verify_parts():
    manifest = json.loads(base.MANIFEST.read_text(encoding="utf-8"))
    for archive in manifest["original_archives"]:
        digest = hashlib.sha256()
        total = 0
        parts = sorted((p for p in manifest["assets"] if p["source_archive"] == archive["name"]),
                       key=lambda p: p["part_index"])
        if not parts or [p["part_index"] for p in parts] != list(range(1, len(parts) + 1)):
            raise RuntimeError("Missing part index for " + archive["name"])
        for part in parts:
            path = part_path(part["name"])
            if path.stat().st_size != part["bytes"] or base.sha(path) != part["sha256"]:
                raise RuntimeError("Missing or changed part: " + part["name"])
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                    digest.update(block)
                    total += len(block)
        if total != archive["bytes"] or digest.hexdigest() != archive["sha256"]:
            raise RuntimeError("Part reconstruction mismatch: " + archive["name"])
        print("parts verified", archive["name"], flush=True)


def verify_remote():
    manifest = json.loads(base.MANIFEST.read_text(encoding="utf-8"))
    base.verify_remote()
    client = base.session()
    release = base.release(client)
    found = {x["name"]: x for x in base.release_assets(client, release["id"])}
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    original = manifest["existing_shard_assets"] + source["existing_assets"]
    for asset in original:
        item = found.get(asset["name"])
        if (not item or item["state"] != "uploaded" or item["size"] != asset["bytes"]
                or item.get("digest") != "sha256:" + asset["sha256"]):
            raise RuntimeError("Missing or mismatched original V3 asset: " + asset["name"])
    if any(x["state"] != "uploaded" for x in found.values()):
        raise RuntimeError("Incomplete remote assets remain")
    print("V3_COMPLETE_REMOTE_VERIFIED", len(original), "original assets",
          len(manifest["assets"]), "part assets", flush=True)


if __name__ == "__main__":
    {"inventory": inventory, "upload": base.upload, "restore": restore,
     "verify-parts": verify_parts, "verify-remote": verify_remote,
     "verify-local": base.verify_local}[sys.argv[1]]()
