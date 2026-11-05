"""Create and upload a SHA-verified backup of local RCAPS experiment artifacts.

The Git commit contains the manifest and this recovery tool. Large artifacts live
in GitHub Release assets, each below 2 GiB. No source files are modified.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
TAG = "experiment-backup-20261105"
MAX_ASSET = 1_400_000_000


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git(*args, input=None):
    return subprocess.run(["git", *args], cwd=ROOT, input=input,
                          capture_output=True, check=True).stdout


def candidates():
    raw = git("ls-files", "--others", "--exclude-standard", "-z")
    paths = sorted(x.decode("utf-8") for x in raw.split(b"\0") if x)
    return [p for p in paths if p.startswith("experiments/") or
            p.split("/", 1)[0].startswith("work3_")]


def referenced_sha(path):
    if path.name == "kv.csv.gz":
        field = "kv_series_sha256"
    elif path.name == "raw_latency.json.gz":
        field = "raw_latency_sha256"
    else:
        return None, None
    result = path.parent / "result.json"
    if not result.is_file():
        return field, None
    try:
        return field, json.loads(result.read_text(encoding="utf-8")).get(field)
    except (UnicodeError, ValueError):
        return field, None


def inventory():
    if MANIFEST.exists():
        raise RuntimeError("Manifest exists; never silently replace a frozen backup")
    entries, issues = [], []
    paths = candidates()
    for index, relative in enumerate(paths, 1):
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            issues.append({"path": relative, "issue": "not regular file"})
            continue
        digest = sha(path)
        field, expected = referenced_sha(path)
        provenance = "recorded_sidecar_sha256" if field and expected == digest else "local_file_sha256"
        if field and expected != digest:
            issues.append({"path": relative, "issue": "result hash absent or mismatch",
                           "field": field, "expected": expected, "actual": digest})
            provenance = "unverified_sidecar"
        entries.append({"path": relative, "bytes": path.stat().st_size,
                        "sha256": digest, "provenance": provenance})
        if index % 100 == 0:
            print("hashed", index, "of", len(paths), flush=True)
    # Keep problematic files in the backup as forensic evidence, labeled explicitly.
    chunks, current, size = [], [], 0
    for entry in sorted(entries, key=lambda e: e["path"]):
        if current and size + entry["bytes"] > MAX_ASSET:
            chunks.append(current)
            current, size = [], 0
        current.append(entry["path"])
        size += entry["bytes"]
    if current:
        chunks.append(current)
    assets = [{"name": "rcaps-experiments-%02d.zip" % (i + 1), "files": names}
              for i, names in enumerate(chunks)]
    manifest = {"tag": TAG, "scope": "Untracked experiments/ and work3_* local artifacts",
                "note": "A backup of evidence, including labeled failed or unverified artifacts; does not change formal outcomes.",
                "git_base": git("rev-parse", "HEAD").decode().strip(),
                "file_count": len(entries), "total_bytes": sum(e["bytes"] for e in entries),
                "issues": issues, "files": entries, "assets": assets}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("inventory", len(entries), "files", manifest["total_bytes"], "bytes",
          len(assets), "assets", len(issues), "issues", flush=True)


def pack():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_path = {e["path"]: e for e in manifest["files"]}
    for i, asset in enumerate(manifest["assets"], 1):
        target = HERE / asset["name"]
        if target.exists():
            if asset.get("sha256") == sha(target):
                print("already packed", target.name, flush=True)
                continue
            raise RuntimeError("Existing archive differs: " + target.name)
        part = HERE / (asset["name"] + ".part")
        if part.exists():
            part.unlink()
        with zipfile.ZipFile(part, "w", compression=zipfile.ZIP_STORED,
                             allowZip64=True) as archive:
            for relative in asset["files"]:
                path = ROOT / relative
                entry = by_path[relative]
                if path.stat().st_size != entry["bytes"] or sha(path) != entry["sha256"]:
                    raise RuntimeError("Source file changed: " + relative)
                archive.write(path, arcname=relative)
        with zipfile.ZipFile(part) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("ZIP CRC failed: " + part.name)
        part.rename(target)
        asset["bytes"] = target.stat().st_size
        asset["sha256"] = sha(target)
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("packed", i, "of", len(manifest["assets"]), target.name,
              asset["bytes"], flush=True)


def credential():
    output = git("credential", "fill", input=b"protocol=https\nhost=github.com\n\n")
    values = dict(line.split("=", 1) for line in output.decode().splitlines() if "=" in line)
    return values["password"]


def session():
    import requests
    client = requests.Session()
    # The local HTTP proxy intermittently terminates long TLS uploads.
    client.trust_env = False
    client.headers.update({"Authorization": "Bearer " + credential(),
                           "Accept": "application/vnd.github+json",
                           "X-GitHub-Api-Version": "2022-11-28",
                           "Connection": "close"})
    return client


def api(client, method, url, **kwargs):
    import requests
    for attempt in range(5 if method == "GET" else 1):
        try:
            response = client.request(method, url, timeout=120, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            if method != "GET" or attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))


def release(client):
    base = "https://api.github.com/repos/lpdcyl/RCAPS"
    for attempt in range(5):
        try:
            response = client.get(base + "/releases/tags/" + TAG, timeout=30)
            break
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))
    if response.status_code == 404:
        remote_branch = api(client, "GET", base + "/branches/codex/work3-upload-20261024")
        if git("rev-parse", "HEAD").decode().strip() != remote_branch["commit"]["sha"]:
            raise RuntimeError("Push the manifest commit before creating the release")
        return api(client, "POST", base + "/releases", json={
            "tag_name": TAG, "target_commitish": "codex/work3-upload-20261024",
            "name": "RCAPS experiment evidence backup " + TAG,
            "body": "SHA-verified local experiment artifacts. See backup_20261105/" + MANIFEST.name + " in the tagged commit for paths, hashes, provenance labels and recovery steps.",
            "draft": False, "prerelease": True})
    response.raise_for_status()
    return response.json()


def upload():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    client = session()
    item = release(client)
    base = "https://api.github.com/repos/lpdcyl/RCAPS"
    for index, asset in enumerate(manifest["assets"], 1):
        path = HERE / asset["name"]
        if path.stat().st_size != asset["bytes"] or sha(path) != asset["sha256"]:
            raise RuntimeError("Archive changed: " + path.name)
        remote = api(client, "GET", base + "/releases/" + str(item["id"]))
        existing = {x["name"]: x for x in remote["assets"]}
        if asset["name"] in existing:
            found = existing[asset["name"]]
            if found["size"] == asset["bytes"] and found.get("digest") == "sha256:" + asset["sha256"]:
                print("already verified remote", asset["name"], flush=True)
                continue
            raise RuntimeError("Remote asset conflicts: " + asset["name"])
        url = item["upload_url"].split("{", 1)[0]
        for attempt in range(3):
            try:
                with path.open("rb") as stream:
                    response = client.post(url, params={"name": asset["name"]}, data=stream,
                                           headers={"Content-Type": "application/zip",
                                                    "Content-Length": str(asset["bytes"])},
                                           timeout=(30, 3600))
                response.raise_for_status()
                found = response.json()
            except Exception as error:
                # An EOF after the request body may still mean GitHub stored it.
                remote = api(client, "GET", base + "/releases/" + str(item["id"]))
                found = next((x for x in remote["assets"] if x["name"] == asset["name"]), None)
                if found is None:
                    if attempt == 2:
                        raise RuntimeError("Upload failed after 3 attempts: " + asset["name"]) from error
                    print("retry upload", asset["name"], attempt + 2, "of 3", flush=True)
                    time.sleep(5)
                    continue
            if found["size"] != asset["bytes"] or found.get("digest") != "sha256:" + asset["sha256"]:
                raise RuntimeError("Remote digest/size mismatch: " + asset["name"])
            print("uploaded and verified", index, "of", len(manifest["assets"]),
                  asset["name"], flush=True)
            break
    print("RELEASE_COMPLETE", item["html_url"], flush=True)


def verify_remote():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    client = session()
    item = release(client)
    remote = api(client, "GET", "https://api.github.com/repos/lpdcyl/RCAPS/releases/" + str(item["id"]))
    found = {x["name"]: x for x in remote["assets"]}
    for asset in manifest["assets"]:
        item = found.get(asset["name"])
        if not item or item["size"] != asset["bytes"] or item.get("digest") != "sha256:" + asset["sha256"]:
            raise RuntimeError("Missing or mismatched remote asset: " + asset["name"])
    print("REMOTE_VERIFIED", len(manifest["assets"]), "assets", manifest["total_bytes"], "source bytes", flush=True)


def verify_local():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for index, entry in enumerate(manifest["files"], 1):
        path = ROOT / entry["path"]
        if not path.is_file() or path.stat().st_size != entry["bytes"] or sha(path) != entry["sha256"]:
            raise RuntimeError("Missing or mismatched restored file: " + entry["path"])
        if index % 200 == 0:
            print("verified", index, "of", manifest["file_count"], flush=True)
    print("LOCAL_VERIFIED", manifest["file_count"], "files", flush=True)


if __name__ == "__main__":
    {"inventory": inventory, "pack": pack, "upload": upload,
     "verify-remote": verify_remote, "verify-local": verify_local}[sys.argv[1]]()
