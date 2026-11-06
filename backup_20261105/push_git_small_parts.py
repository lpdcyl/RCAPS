"""Split and push the last V3 tail parts in 10 MB Git commits."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import backup


BRANCH = "refs/heads/codex/backup-parts-small-20261106"
REPO = Path(os.environ.get("TEMP", "C:/Temp")) / "rcaps-git-small-parts"
SOURCE = backup.HERE / "tail_v3_manifest.json"
MANIFEST = backup.HERE / "small_parts_manifest.json"
PART_BYTES = 10_000_000
FIRST_SMALL_INDEX = 32


def git(*args, check=True):
    result = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True,
                            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if check and result.returncode:
        raise RuntimeError("git " + " ".join(args) + ": " + result.stderr[-500:])
    return result


def remote_sha():
    for attempt in range(3):
        result = git("ls-remote", "origin", BRANCH, check=False)
        if result.returncode == 0 and result.stdout.split():
            return result.stdout.split()[0]
        if attempt < 2:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("Cannot read remote small-parts branch")


def sync():
    local = git("rev-parse", "HEAD").stdout.strip()
    remote = remote_sha()
    if remote == local:
        return
    if git("merge-base", "--is-ancestor", remote, local, check=False).returncode:
        raise RuntimeError("Remote small-parts branch diverged")
    proxy = os.environ.get("HTTPS_PROXY", "http://127.0.0.1:7897")
    for attempt, route in enumerate((proxy, "", proxy), 1):
        print("pushing", local, "attempt", attempt, "of 3",
              "proxy" if route else "direct", flush=True)
        result = git("-c", "http.proxy=" + route, "-c", "http.sslBackend=openssl",
                     "-c", "http.version=HTTP/1.1", "-c", "http.postBuffer=104857600",
                     "push", "origin", "HEAD:" + BRANCH, check=False)
        if remote_sha() == local:
            print(result.stderr[-200:], flush=True)
            return
        print("push incomplete", result.returncode, result.stderr[-200:], flush=True)
        if attempt < 3:
            time.sleep(5 * attempt)
    raise RuntimeError("Small-part push failed after 3 attempts: " + local)


def inventory():
    if MANIFEST.exists():
        raise RuntimeError("Small-parts manifest already exists")
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    originals = source["assets"][FIRST_SMALL_INDEX:]
    pieces = []
    for original in originals:
        path = backup.HERE / original["name"]
        if path.stat().st_size != original["bytes"] or backup.sha(path) != original["sha256"]:
            raise RuntimeError("Source tail part changed: " + original["name"])
        with path.open("rb") as stream:
            number = 1
            while data := stream.read(PART_BYTES):
                name = original["name"].removesuffix(".bin") + "-sub%02d.bin" % number
                target = REPO / name
                digest = hashlib.sha256(data).hexdigest()
                if target.exists():
                    if target.stat().st_size != len(data) or backup.sha(target) != digest:
                        raise RuntimeError("Existing small part differs: " + name)
                else:
                    target.write_bytes(data)
                pieces.append({"name": name, "bytes": len(data), "sha256": digest,
                               "source_part": original["name"], "sub_index": number})
                number += 1
        print("split", original["name"], number - 1, "subparts", flush=True)
    manifest = {"source_manifest": SOURCE.name,
                "full_git_parts": source["assets"][:FIRST_SMALL_INDEX],
                "original_parts": originals, "assets": pieces,
                "total_bytes": sum(p["bytes"] for p in pieces), "branch": BRANCH}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("SMALL_PARTS_INVENTORY", len(originals), "original parts",
          len(pieces), "subparts", manifest["total_bytes"], "bytes", flush=True)


def upload():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    sync()
    for index, asset in enumerate(manifest["assets"], 1):
        path = REPO / asset["name"]
        if path.stat().st_size != asset["bytes"] or backup.sha(path) != asset["sha256"]:
            raise RuntimeError("Small part changed: " + asset["name"])
        if git("ls-files", "--error-unmatch", asset["name"], check=False).returncode == 0:
            print("already committed", index, "of", len(manifest["assets"]), asset["name"], flush=True)
            continue
        git("add", "--", asset["name"])
        git("-c", "gc.auto=0", "commit", "-m", "Back up V3 subpart " + asset["name"])
        sync()
        print("SMALL_PART_PUSHED", index, "of", len(manifest["assets"]), asset["name"], flush=True)
        if index % 2 == 0:
            time.sleep(30)
    sync()
    print("ALL_SMALL_PARTS_PUSHED", len(manifest["assets"]),
          git("rev-parse", "HEAD").stdout.strip(), flush=True)


def restore():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for original in manifest["original_parts"]:
        target = backup.HERE / original["name"]
        if target.exists():
            if target.stat().st_size != original["bytes"] or backup.sha(target) != original["sha256"]:
                raise RuntimeError("Existing original part differs: " + original["name"])
            print("already restored", original["name"], flush=True)
            continue
        pieces = sorted((p for p in manifest["assets"] if p["source_part"] == original["name"]),
                        key=lambda p: p["sub_index"])
        if not pieces or [p["sub_index"] for p in pieces] != list(range(1, len(pieces) + 1)):
            raise RuntimeError("Missing subpart: " + original["name"])
        temp = target.with_suffix(".restoring")
        if temp.exists():
            raise RuntimeError("Partial restore exists: " + str(temp))
        digest = hashlib.sha256()
        total = 0
        with temp.open("wb") as output:
            for piece in pieces:
                path = backup.HERE / "git_small_parts" / piece["name"]
                if path.stat().st_size != piece["bytes"] or backup.sha(path) != piece["sha256"]:
                    raise RuntimeError("Small part changed: " + piece["name"])
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                        output.write(block)
                        digest.update(block)
                        total += len(block)
        if total != original["bytes"] or digest.hexdigest() != original["sha256"]:
            raise RuntimeError("Reconstructed part differs: " + original["name"])
        temp.rename(target)
        print("restored", original["name"], flush=True)


if __name__ == "__main__":
    {"inventory": inventory, "upload": upload, "restore": restore}[sys.argv[1]]()
