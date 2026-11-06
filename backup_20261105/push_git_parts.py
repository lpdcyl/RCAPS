"""Push the verified V3 tail parts one at a time through Git transport."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import backup


BRANCH = "refs/heads/codex/backup-parts-20261106"
REPO = Path(os.environ.get("TEMP", "C:/Temp")) / "rcaps-git-push-probe"
MANIFEST = backup.HERE / "tail_v3_manifest.json"


def git(*args, check=True):
    result = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True,
                            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if check and result.returncode:
        raise RuntimeError("git " + " ".join(args) + ": " + result.stderr[-700:])
    return result


def sync():
    local = git("rev-parse", "HEAD").stdout.strip()
    remote = remote_sha()
    if remote == local:
        return
    ancestry = git("merge-base", "--is-ancestor", remote, local, check=False)
    if ancestry.returncode:
        raise RuntimeError("Remote branch diverged; refusing to overwrite it")
    proxy = os.environ.get("HTTPS_PROXY", "http://127.0.0.1:7897")
    routes = [proxy, "", proxy] if os.environ.get("RCAPS_GIT_PROXY_FIRST") == "1" else ["", proxy, ""]
    for attempt in range(1, 4):
        route = routes[attempt - 1]
        print("pushing pending commit", local, "attempt", attempt, "of 3",
              "proxy" if route else "direct", flush=True)
        result = git("-c", "http.proxy=" + route, "-c", "http.sslBackend=openssl",
                     "-c", "http.version=HTTP/1.1", "-c", "http.postBuffer=104857600",
                     "push", "origin", "HEAD:" + BRANCH, check=False)
        if remote_sha() == local:
            print(result.stderr[-250:], flush=True)
            return
        print("push incomplete", result.returncode, result.stderr[-250:], flush=True)
        if attempt < 3:
            time.sleep(5 * attempt)
    raise RuntimeError("Git push failed after 3 attempts: " + local)


def remote_sha():
    for attempt in range(3):
        result = git("ls-remote", "origin", BRANCH, check=False)
        if result.returncode == 0 and result.stdout.split():
            return result.stdout.split()[0]
        if attempt < 2:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("Could not read remote backup branch")


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not (REPO / ".git").is_dir():
        raise RuntimeError("Missing initialized temporary Git repository: " + str(REPO))
    sync()
    for index, asset in enumerate(manifest["assets"], 1):
        source = backup.HERE / asset["name"]
        if source.stat().st_size != asset["bytes"] or backup.sha(source) != asset["sha256"]:
            raise RuntimeError("Source part changed: " + asset["name"])
        target = REPO / asset["name"]
        if not target.exists():
            shutil.copy2(source, target)
        if target.stat().st_size != asset["bytes"] or backup.sha(target) != asset["sha256"]:
            raise RuntimeError("Copied part changed: " + asset["name"])
        if git("ls-files", "--error-unmatch", asset["name"], check=False).returncode == 0:
            print("already committed", index, "of", len(manifest["assets"]), asset["name"], flush=True)
            continue
        git("add", "--", asset["name"])
        git("-c", "gc.auto=0", "commit", "-m", "Back up V3 part " + asset["name"])
        sync()
        print("GIT_PART_PUSHED", index, "of", len(manifest["assets"]), asset["name"], flush=True)
    sync()
    print("ALL_GIT_PARTS_PUSHED", len(manifest["assets"]), git("rev-parse", "HEAD").stdout.strip(), flush=True)


if __name__ == "__main__":
    main()
