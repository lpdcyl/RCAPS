"""Stage only the final SHA-verified upload manifest; never commit or push."""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, read, sha

from .run import HERE


BRANCH = "codex/work3-upload-20261024"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def verify_staged_bytes(entries):
    indexed = {}
    for record in git("ls-files", "--stage", "-z").split(b"\0"):
        if not record:
            continue
        metadata, name = record.split(b"\t", 1)
        mode, object_id, stage = metadata.split()
        if stage == b"0":
            indexed[name.decode("utf-8")] = object_id
    if any(entry["path"] not in indexed for entry in entries):
        raise RuntimeError("Upload path missing from Git index")
    request = b"\n".join(indexed[entry["path"]] for entry in entries) + b"\n"
    result = subprocess.run(["git", "cat-file", "--batch"], input=request,
                            stdout=subprocess.PIPE, check=True, cwd=ROOT)
    data, offset = result.stdout, 0
    for entry in entries:
        end = data.index(b"\n", offset)
        _, kind, length = data[offset:end].split()
        if kind != b"blob":
            raise RuntimeError("Upload index entry is not a blob: " + entry["path"])
        size = int(length)
        offset = end + 1
        content = data[offset:offset + size]
        offset += size + 1
        if hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise RuntimeError("Git staged bytes differ from manifest: " + entry["path"])


def main():
    branch = git("branch", "--show-current").decode().strip()
    if branch != BRANCH:
        raise RuntimeError("Wrong upload branch: " + branch)
    if git("diff", "--cached", "--name-only", "-z"):
        raise RuntimeError("Existing staged changes must be reviewed before staging this bundle")
    manifest_path = HERE / "UPLOAD_MANIFEST.json"
    manifest = read(manifest_path)
    if sha(HERE / "FINAL_RECONCILIATION.json") != manifest["final_reconciliation_sha256"]:
        raise RuntimeError("Final reconciliation changed")
    names = []
    for entry in manifest["files"]:
        path = (ROOT / entry["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise RuntimeError("Invalid upload path: " + entry["path"])
        if path.stat().st_size != entry["bytes"] or sha(path) != entry["sha256"]:
            raise RuntimeError("Upload file changed: " + entry["path"])
        names.append(entry["path"])
    if len(names) != manifest["file_count"] or len(names) != len(set(names)):
        raise RuntimeError("Upload manifest file population changed")
    names.append(manifest_path.relative_to(ROOT).as_posix())
    with tempfile.TemporaryDirectory(prefix="rcaps_upload_") as folder:
        pathspec = Path(folder) / "paths.nul"
        pathspec.write_bytes(b"\0".join(name.encode("utf-8") for name in names) + b"\0")
        pathspec_options = ["--pathspec-from-file=" + str(pathspec), "--pathspec-file-nul"]
        subprocess.run(["git", "-c", "core.autocrlf=false", "--literal-pathspecs",
                        "add", "-f", *pathspec_options], cwd=ROOT, check=True)
        # Git may consider a previously normalized index entry unchanged on the
        # first add. Renormalize every listed path with conversion disabled.
        subprocess.run(["git", "-c", "core.autocrlf=false", "--literal-pathspecs",
                        "add", "--renormalize", "-f", *pathspec_options],
                       cwd=ROOT, check=True)
    staged = {name.decode().replace("\\", "/") for name in
              git("diff", "--cached", "--name-only", "-z").split(b"\0") if name}
    if not staged or not staged.issubset(set(names)) or names[-1] not in staged:
        raise RuntimeError("Unexpected staged path set; inspect git diff --cached")
    verify_staged_bytes(manifest["files"] + [{"path": names[-1], "sha256": sha(manifest_path)}])
    print({"branch": branch, "manifest_file_count": manifest["file_count"],
           "staged_paths": len(staged), "bundle_bytes": manifest["total_bytes"],
           "committed": False, "pushed": False})


if __name__ == "__main__":
    main()
