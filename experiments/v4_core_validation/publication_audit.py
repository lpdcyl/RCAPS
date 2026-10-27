"""Read-only publication byte checks; no simulation or result regeneration."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PREFIX = HERE.relative_to(ROOT).as_posix()


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    expected = {}
    problems = []

    def expect(path, digest):
        path = Path(path).as_posix()
        if path in expected and expected[path] != digest:
            problems.append({"kind": "conflicting_hash", "path": path})
        expected[path] = digest

    result = read(f"{PREFIX}/results.json")
    manifest = read(f"{PREFIX}/manifest.json")
    index = read(f"{PREFIX}/execution/index.json")
    for name in ("manifest.json", "launch_amendment.json", "execution_amendment.json"):
        item = read(f"{PREFIX}/{name}")
        for path, digest in item.get("sources_sha256", {}).items():
            expect(path, digest)
        if "manifest_sha256" in item:
            expect(f"{PREFIX}/manifest.json", item["manifest_sha256"])
    for ref in manifest["references"]:
        expect(ref["path"], ref["sha256"])
    for row in result["windows"]:
        expect(row["source"], row["sha256"])
    for failure in result["failures"]:
        for path, digest in failure["files"].items():
            expect(path, digest)
    expect(f"{PREFIX}/manifest.json", result["manifest_sha256"])
    expect(f"{PREFIX}/execution/index.json", result["execution_index_sha256"])
    expect(f"{PREFIX}/report.py", result["report_source_sha256"])
    expect(f"{PREFIX}/index.json", result["prior_engineering_dispatch_failures"]["index_sha256"])
    enrichment = read(f"{PREFIX}/report_enrichment.json")
    expect(f"{PREFIX}/results.json", enrichment["results_sha256"])
    expect(f"{PREFIX}/RESULTS_CN.md", enrichment["report_sha256"])
    expect(f"{PREFIX}/reconciliation_v1.json", enrichment["results_archive_sha256"])
    expect(f"{PREFIX}/enrich_results.py", result["report_enrichment"]["source_sha256"])
    expect(f"{PREFIX}/report.py", read(f"{PREFIX}/report_registration.json")["report_sha256"])
    for path, digest in expected.items():
        p = ROOT / path
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            problems.append({"kind": "registered_byte_mismatch", "path": path})
        blob = subprocess.run(["git", "show", f":{path}"], cwd=ROOT, capture_output=True)
        if blob.returncode or hashlib.sha256(blob.stdout).hexdigest() != digest:
            problems.append({"kind": "git_index_byte_mismatch", "path": path})

    tracked = subprocess.check_output(["git", "ls-files", "-z", "--", PREFIX], cwd=ROOT).decode().split("\0")
    tracked = [p for p in tracked if p and not p.endswith("/publication_byte_audit.json")]
    for path in tracked:
        raw = (ROOT / path).read_bytes()
        blob = subprocess.check_output(["git", "show", f":{path}"], cwd=ROOT)
        if raw != blob:
            problems.append({"kind": "published_core_bytes_differ", "path": path})

    statuses = dict(Counter(x["status"] for x in index["jobs"].values()))
    if statuses != {"completed": 14, "failed": 1}:
        problems.append({"kind": "unexpected_execution_counts", "actual": statuses})
    if len(result["checks"]) != 727 or any(not c["passed"] for c in result["checks"]):
        problems.append({"kind": "prior_reconciliation_not_passed"})
    if result["missing"] or result["rejected"] or result["right_censored"]:
        problems.append({"kind": "unexpected_incomplete_results"})
    if len(manifest["references"]) != 9 or result["hardware_calibration_completed"]:
        problems.append({"kind": "unexpected_evidence_identity"})

    staged = subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"], cwd=ROOT).decode().split("\0")
    credential = re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")
    secret_hits = []
    for path in filter(None, staged):
        data = subprocess.check_output(["git", "show", f":{path}"], cwd=ROOT)
        if credential.search(data):
            secret_hits.append(path)
        if len(data) >= 100_000_000:
            problems.append({"kind": "oversized_git_blob", "path": path})
    if secret_hits:
        problems.append({"kind": "credential_pattern_detected", "paths": secret_hits})

    payload = {
        "scope": "publication identity checks only; no scientific-result regeneration",
        "status": "passed" if not problems else "failed",
        "registered_artifacts_checked": len(expected),
        "core_files_with_exact_git_bytes": len(tracked),
        "formal_execution": statuses,
        "reused_references": len(manifest["references"]),
        "previous_scientific_reconciliation_checks": len(result["checks"]),
        "previous_dispatch_failures": result["prior_engineering_dispatch_failures"]["count"],
        "hardware_calibration_completed": False,
        "credential_pattern_hits": len(secret_hits),
        "registered_artifacts": expected,
        "problems": problems,
    }
    if args.write:
        (HERE / "publication_byte_audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k != "registered_artifacts"}, ensure_ascii=False, indent=2))
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
