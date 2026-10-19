"""Record why historical C1 windows were or were not reused."""

from __future__ import annotations

import json

from experiments.v3_release.verify import digest

from .run import (DURATION, HERE, LOADS, METHODS, ROOT, SEEDS, _historical,
                  identity, read_json, reuse, write_json)


def main() -> None:
    rows = []
    for scenario, loads in LOADS.items():
        for load in loads:
            for seed in SEEDS:
                for method in METHODS:
                    path = _historical(scenario, load, seed, method)
                    if path is None:
                        continue
                    record = {"scenario": scenario, "load": load, "seed": seed,
                              "method": method,
                              "path": path.relative_to(ROOT).as_posix(),
                              "exists": path.is_file()}
                    if path.is_file():
                        saved = read_json(path)
                        expected = identity(scenario, load, seed, method)
                        record["sha256"] = digest(path)
                        fields = ("scenario", "seed", "offered_tokens_per_s",
                                  "duration_s", "warmup_s", "evaluation_protocol",
                                  "query_samples_schema", "solution_sha256",
                                  "sim_cluster_sha256", "physical_sha256")
                        record["mismatches"] = {name: {"historical": saved.get(name),
                                                         "current": expected[name]}
                                                 for name in fields
                                                 if saved.get(name) != expected[name]}
                        if method == "rcaps_v3":
                            current = digest(ROOT / "experiments/v3_release/manifest.json")
                            if saved.get("release_manifest_sha256") != current:
                                record["mismatches"]["release_manifest_sha256"] = {
                                    "historical": saved.get("release_manifest_sha256"),
                                    "current": current}
                        record["complete_samples"] = (
                            len(saved.get("query_samples", {})) == saved.get("arrivals"))
                    record["reused"] = reuse(scenario, load, seed, method) is not None
                    rows.append(record)
    write_json(HERE / "historical_audit.json", {"rows": rows,
              "rule": "Reuse requires all protocol, deployment, physical, release and sample checks"})
    print(f"historical={len(rows)}, reused={sum(row['reused'] for row in rows)}")


if __name__ == "__main__":
    main()
