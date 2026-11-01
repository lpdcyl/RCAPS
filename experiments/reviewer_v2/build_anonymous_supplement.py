"""Package only reviewed aggregate outputs from E4, E6, and retry audit."""
import hashlib
import json
import re
import zipfile
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, read, sha, write

HERE = Path(__file__).resolve().parent
OUT = HERE / "reviewer_v2_anonymous_evidence.zip"
AUDIT = HERE / "ANONYMOUS_EVIDENCE_AUDIT.json"
PRIVATE = re.compile(r"[A-Za-z]:[\/]|[\/]Users[\/]|[\/]home[\/]|Panda|Joseph Williams", re.I)
FILES = (
    "E4_tcp_wsl/RESULTS_CN.md",
    "E4_tcp_wsl/individual.csv",
    "E4_tcp_wsl/FINAL_AUDIT.json",
    "E4_tcp_wsl/REPLAY_AUDIT_CN.md",
    "E6_cumulative/RESULTS_CN.md",
    "E6_cumulative/paired.json",
    "E6_cumulative/failure_replay/FINAL_AUDIT.json",
    "remaining_failure_retry_20261031/RESULTS_CN.md",
    "remaining_failure_retry_20261031/FINAL_AUDIT.json",
)


def main():
    if not read(HERE / "E4_tcp_wsl/FINAL_AUDIT.json")["passed"]:
        raise RuntimeError("E4 audit not passed")
    if not read(HERE / "E6_cumulative/FINAL_AUDIT.json")["passed"]:
        raise RuntimeError("E6 audit not passed")
    if not read(HERE / "remaining_failure_retry_20261031/FINAL_AUDIT.json")["passed"]:
        raise RuntimeError("Retry audit not passed")
    payload = {}
    for rel in FILES:
        raw = (HERE / rel).read_bytes()
        text = raw.decode("utf-8-sig")
        if PRIVATE.search(text):
            raise RuntimeError("Potential private identifier in " + rel)
        payload[rel] = raw
    manifest = {"scope": "Curated E4/E6 and retry audit evidence; formal and replay raw artifacts stay separate",
                "files": [{"path": k, "sha256": hashlib.sha256(v).hexdigest(), "bytes": len(v)}
                          for k, v in payload.items()]}
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for rel, raw in payload.items():
            z.writestr(rel, raw)
        z.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
    write(AUDIT, {"passed": True, "zip_sha256": sha(OUT), "file_count": len(payload),
                  "scope": manifest["scope"]})
    print({"archive": str(OUT.relative_to(ROOT)), "sha256": sha(OUT), "files": len(payload)})


if __name__ == "__main__":
    main()
