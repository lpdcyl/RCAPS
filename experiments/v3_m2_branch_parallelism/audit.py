"""Build a source-hash ledger and enforce the planned run matrix."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from rcaps.v3.placement import digest


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    plan = read(HERE / "plan.json")
    expected = {}
    for case, loads, seeds in (("C1_single", (350., 700., 1100.), (0,)),
                               ("C1_multi", (160., 320., 500.), (0,))):
        for variant in plan["cases"][case]["variants"]:
            for load in loads:
                for seed in seeds:
                    expected[("explore", case, variant, load, seed)] = None
    for case, load, seeds in (("C1_single", 700., (1, 2, 3)),
                              ("C1_multi", 320., (1, 2, 3)),
                              ("C1_single", 600., (4, 5, 6))):
        for variant in plan["cases"][case]["variants"]:
            for seed in seeds:
                expected[("formal", case, variant, load, seed)] = None
    for case, load in (("C1_single", 700.), ("C1_multi", 320.)):
        for branch in ((1,), (2,), (0, 2), (1, 2)):
            label = "k" + str(len(branch)) + "_b" + "".join(map(str, branch))
            expected[("subsets", case, label, load, 0)] = None
    for case, variant, load in (("C1_single", "k2", 700.),
                                ("C1_single", "k3", 700.),
                                ("C1_multi", "k2", 320.)):
        expected[("full_dag", case, variant, load, 0)] = None
    result = {"plan_sha256": digest(HERE / "plan.json"),
              "formal_protocol_sha256": digest(HERE / "formal_protocol.json"),
              "adaptive_protocol_sha256": digest(HERE / "adaptive_protocol.json"),
              "runs": {}, "missing": [], "failures": [], "trace_mismatches": []}
    traces = defaultdict(set)
    for phase, case, variant, load, seed in expected:
        base = HERE / "runs" / phase / case / variant / f"load{load:g}_seed{seed}"
        output = base.with_suffix(".json")
        log = base.with_suffix(".log")
        key = f"{phase}/{case}/{variant}/load{load:g}/seed{seed}"
        if output.exists():
            row = read(output)
            if (row["case"] != case or row["variant"] != variant or
                    row["seed"] != seed or row["offered_tokens_per_s"] != load or
                    len(row["query_samples"]) != row["arrivals"]):
                raise ValueError(f"Run identity/sample mismatch: {key}")
            if phase in ("formal", "explore", "full_dag"):
                info = plan["cases"][case]["variants"][variant]
                if (row["solution_sha256"] != info["solution_sha256"] or
                        row["sim_cluster_sha256"] != info["sim_cluster_sha256"]):
                    raise ValueError(f"Deployment mismatch: {key}")
            traces[(phase, case, load, seed)].add(row["trace_sha256"])
            result["runs"][key] = {"status": "passed",
                                    "source": output.relative_to(ROOT).as_posix(),
                                    "sha256": digest(output),
                                    "trace_sha256": row["trace_sha256"]}
        elif log.exists() and "Traceback (most recent call last):" in log.read_text(
                encoding="utf-8"):
            lines = log.read_text(encoding="utf-8").splitlines()
            result["runs"][key] = {"status": "failed",
                                    "source": log.relative_to(ROOT).as_posix(),
                                    "sha256": digest(log), "error": lines[-1]}
            result["failures"].append(key)
        else:
            result["missing"].append(key)
    for (phase, case, load, seed), hashes in traces.items():
        if len(hashes) != 1:
            result["trace_mismatches"].append(f"{phase}/{case}/load{load:g}/seed{seed}")
    destination = HERE / "run_manifest.json"
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(json.dumps({"expected": len(expected),
                      "passed": sum(item["status"] == "passed" for item in
                                    result["runs"].values()),
                      "failed": len(result["failures"]),
                      "missing": result["missing"],
                      "trace_mismatches": result["trace_mismatches"]}, indent=2))
    if result["missing"] or result["trace_mismatches"]:
        raise ValueError("Incomplete or nonpaired experiment")


if __name__ == "__main__":
    main()
