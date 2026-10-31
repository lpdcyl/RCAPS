"""Archive and verify the registered source bytes of a V6 campaign."""
from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, check, read, sha, write


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign", choices=("robustness", "generalization",
                                             "session_cost", "weight_online",
                                             "session_capacity", "bandwidth_threshold",
                                             "scalability", "failure_replay"))
    parser.add_argument("--phase", choices=("formal", "smoke", "smoke_v2"),
                        default="formal")
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent / args.campaign / args.phase
    manifest_path = folder / "manifest.json"
    manifest = read(manifest_path)
    check(manifest)
    sources = manifest["sources_sha256"]
    archive_path = folder / "frozen_runtime_inputs.zip"
    if not archive_path.exists():
        with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6) as archive:
            for name, expected in sorted(sources.items()):
                content = (ROOT / name).read_bytes()
                assert hashlib.sha256(content).hexdigest() == expected, name
                archive.writestr(name, content)
    with zipfile.ZipFile(archive_path) as archive:
        assert set(archive.namelist()) == set(sources)
        for name, expected in sources.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == expected, name
    write(folder / "frozen_runtime_archive.json", dict(
        passed=True, sha256=sha(archive_path), files=len(sources),
        manifest_sha256=sha(manifest_path)))
    print(args.campaign, args.phase, "verified", len(sources), "files")


if __name__ == "__main__":
    main()
