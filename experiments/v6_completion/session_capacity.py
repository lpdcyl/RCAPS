"""Predeclared five-seed SLO capacity grid for session-pricing variants."""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from experiments.v5_core_supplement.run import ENV, ROOT, check, now, read, sha, write
from experiments.v6_completion.campaign_queue import queue, worker
from experiments.v6_completion.session_cost import VARIANTS, evaluate

HERE = Path(__file__).resolve().parent / "session_capacity"
GRID = {"single": (350, 500, 700), "multi": (160, 240, 320)}
NEW_LOADS = {"single": (350, 500), "multi": (160, 240)}
HIGH = {"single": 700, "multi": 320}
TPOT_LIMIT = {"single": 0.6, "multi": 0.8}
COMPLETION_LIMIT = 0.95
CELLS = ("HH", "HHplus", "V4", *VARIANTS)


def register(phase, workers):
    path = HERE / phase / "manifest.json"
    if path.exists():
        manifest = read(path)
        check(manifest)
        return manifest
    if phase == "formal":
        smoke = read(HERE / "smoke/index.json")
        assert smoke["status"] == "terminal"
        assert all(x["status"] == "completed" for x in smoke["jobs"].values())
    if phase == "smoke":
        jobs = [dict(key=f"{scenario}/load{load}/{variant}/seed100", scenario=scenario,
                     load=load, variant=variant, seed=100, duration=60)
                for scenario, load, variant in (("single", 350, "batch"),
                                                ("multi", 160, "marginal"))]
    else:
        jobs = [dict(key=f"{scenario}/load{load}/{variant}/seed{seed}",
                     scenario=scenario, load=load, variant=variant, seed=seed, duration=1800)
                for scenario, loads in NEW_LOADS.items() for load in loads
                for variant in VARIANTS for seed in range(5)]
    core = read(ROOT / "experiments/v5_core_supplement/formal/manifest.json")
    sources = dict(core["sources_sha256"])
    for name in ("experiments/v6_completion/session_capacity.py",
                 "experiments/v6_completion/session_cost.py",
                 "experiments/v6_completion/campaign_queue.py"):
        sources[name] = sha(ROOT / name)
    manifest = dict(registered_at=now(), phase=phase, jobs=jobs,
                    sources_sha256=sources, worker_limit=workers,
                    timeout_wall_s=14400, preregistered_grid=GRID,
                    tpot_p95_limit_s=TPOT_LIMIT,
                    completion_fraction_limit=COMPLETION_LIMIT,
                    reused_baselines="v5_seed_completion for HH/HHplus/V4; v6 session_cost for high-load variants",
                    decision_rule="All five seeds must meet both limits; failures uncertified; largest feasible offered load on grid",
                    failure_policy="One attempt per key; failures preserved without imputation",
                    environment=dict(executable=sys.executable, env=ENV))
    write(path, manifest)
    return manifest


def source_entry(index, key):
    entry = index["jobs"][key]
    assert entry["status"] in ("completed", "reused", "failed", "reused_failure")
    source = ROOT / entry["source"]
    assert sha(source) == entry["artifact_sha256"]
    return entry["status"], entry["source"], read(source)


def report():
    formal = HERE / "formal"
    manifest, index = read(formal / "manifest.json"), read(formal / "index.json")
    assert index["status"] == "terminal"
    prior = read(ROOT / "experiments/v5_seed_completion/formal/index.json")
    high = read(ROOT / "experiments/v6_completion/session_cost/formal/index.json")
    assert prior["status"] == high["status"] == "terminal"
    records = []
    for scenario, loads in GRID.items():
        for load in loads:
            for cell in CELLS:
                for seed in range(5):
                    if cell in ("HH", "HHplus", "V4"):
                        status, source, item = source_entry(prior,
                            f"{scenario}/load{load}/{cell}/seed{seed}")
                        evidence = "existing_main"
                    elif load == HIGH[scenario]:
                        status, source, item = source_entry(high,
                            f"{scenario}/{cell}/seed{seed}")
                        evidence = "existing_high_variant"
                    else:
                        status, source, item = source_entry(index,
                            f"{scenario}/load{load}/{cell}/seed{seed}")
                        evidence = "new_capacity"
                    if status in ("completed", "reused"):
                        assert len(item["query_samples"]) == item["arrivals"]
                        assert item["trace_sha256"]
                    records.append(dict(scenario=scenario, load=load, cell=cell,
                                        seed=seed, evidence=evidence, status=status,
                                        source=source, source_sha256=sha(ROOT / source),
                                        trace_sha256=item.get("trace_sha256", ""),
                                        tpot_p95_s=item.get("tpot_p95_s"),
                                        completion_fraction=item.get("completion_fraction"),
                                        output_throughput_tokens_per_s=item.get(
                                            "output_throughput_tokens_per_s"),
                                        error=item.get("error", "")))
    contexts = defaultdict(set)
    for row in records:
        if row["trace_sha256"]:
            contexts[row["scenario"], row["load"], row["seed"]].add(row["trace_sha256"])
    assert all(len(x) == 1 for x in contexts.values())
    with (HERE / "individual.csv").open("w", newline="", encoding="utf-8-sig") as out:
        writer = csv.DictWriter(out, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    grid_rows, limits = [], []
    for scenario, loads in GRID.items():
        for cell in CELLS:
            feasible = []
            for load in loads:
                rows = [r for r in records if (r["scenario"], r["load"], r["cell"]) ==
                        (scenario, load, cell)]
                assert len(rows) == 5
                complete = all(r["status"] in ("completed", "reused") for r in rows)
                passed = complete and all(
                    float(r["tpot_p95_s"]) <= TPOT_LIMIT[scenario] and
                    float(r["completion_fraction"]) >= COMPLETION_LIMIT for r in rows)
                if passed:
                    feasible.append(load)
                grid_rows.append(dict(scenario=scenario, cell=cell, offered_load=load,
                    n_success=sum(r["status"] in ("completed", "reused") for r in rows),
                    status="feasible" if passed else "slo_violated" if complete else "uncertified_failure",
                    max_seed_tpot_p95_s=max((float(r["tpot_p95_s"]) for r in rows
                                             if r["tpot_p95_s"] is not None), default=None),
                    min_seed_completion=min((float(r["completion_fraction"]) for r in rows
                                             if r["completion_fraction"] is not None), default=None),
                    mean_output_throughput=mean(float(r["output_throughput_tokens_per_s"])
                                                for r in rows) if complete else None))
            limits.append(dict(scenario=scenario, cell=cell,
                largest_tested_feasible_load=max(feasible) if feasible else None,
                feasible_grid_loads=feasible,
                grid_upper_edge_reached=bool(feasible and max(feasible) == max(loads))))
    for name, rows in (("slo_grid.csv", grid_rows), ("slo_capacity.csv", limits)):
        with (HERE / name).open("w", newline="", encoding="utf-8-sig") as out:
            writer = csv.DictWriter(out, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    lines = ["# 会话代价变体的预设 SLO 容量网格", "",
        "正式新增 160 个低、中负载窗口；高负载变体和主方法负载曲线按原始来源复用，不增加独立种子数。",
        "单集群 P95 TPOT ≤ 0.6 s，三集群 ≤ 0.8 s，均要求五种子逐一完成率 ≥ 95%。",
        "最大负载只指预设网格中的最大可行点；网格外容量和真实硬件容量未估计。失败不填零。", "",
        "| 拓扑 | 方法 | 网格最大五种子可行负载（token/s） | 达到上界 |",
        "|---|---|---:|---|"]
    for row in limits:
        lines.append(f"| {row['scenario']} | {row['cell']} | "
                     f"{row['largest_tested_feasible_load'] if row['largest_tested_feasible_load'] is not None else '无已认证点'} | "
                     f"{row['grid_upper_edge_reached']} |")
    (HERE / "RESULTS_CN.md").write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    write(HERE / "FINAL_AUDIT.json", dict(passed=True, new_jobs=len(manifest["jobs"]),
          counts=dict(Counter(x["status"] for x in index["jobs"].values())),
          reused_rows=sum(r["evidence"] != "new_capacity" for r in records),
          source_manifest_sha256=sha(formal / "manifest.json"),
          individual_sha256=sha(HERE / "individual.csv"),
          capacity_sha256=sha(HERE / "slo_capacity.csv"),
          report_sha256=sha(HERE / "RESULTS_CN.md")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "formal"))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--worker")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.report:
        report()
    elif args.worker:
        worker(HERE, args.phase, args.worker, evaluate)
    else:
        queue(HERE, "experiments.v6_completion.session_capacity", args.phase,
              args.workers, register, report)


if __name__ == "__main__":
    main()
