"""P1-6 offline placement-weight sensitivity, without changing frozen M2 code."""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from unittest.mock import patch

from experiments.m2_multistage_candidate.prepare import _audit_export, files, initial_state, reference_state
from experiments.v5_core_supplement.run import ROOT, now, read, relative, sha, write
from rcaps.v3 import placement, search
from rcaps.v3.topology import TopologyModel, profile_at

HERE = Path(__file__).resolve().parent / "weight_search"
CASES = ("C1_single", "C1_multi")
BASE = (0.40, 0.35, 0.25)
SETTINGS = tuple(f"w{i}_{direction}" for i in range(3) for direction in ("low", "high"))


def weights(label):
    index = int(label[1])
    factor = 0.5 if label.endswith("low") else 1.5
    values = list(BASE)
    values[index] *= factor
    total = sum(values)
    return tuple(value / total for value in values)


def weighted_cheap_cost(model, state, chosen):
    costs = []
    for segment in state["segments"]:
        replica_costs = []
        for replica in segment["replicas"]:
            cost = 0.0
            for node in replica:
                profile = model.profiles[model.types[node]]
                length = state["lengths"][node]
                cost += length * (chosen[0] * profile_at(profile.prompt_bs2time, model.prompt_tokens) +
                                  chosen[1] * profile_at(profile.decode_bs2time, model.decode_batch))
            replica_costs.append(cost)
        costs.append(max(replica_costs))
    return sum(costs) + 0.002 * sum(state["lengths"].values())


def register():
    target = HERE / "manifest.json"
    if target.exists():
        manifest = read(target)
        for path, digest in manifest["sources_sha256"].items():
            assert sha(ROOT / path) == digest, path
        return manifest
    sources = {}
    for path in (Path(__file__), ROOT / "rcaps/v3/search.py", ROOT / "rcaps/v3/placement.py",
                 ROOT / "rcaps/v3/topology.py", ROOT / "experiments/m2_multistage_candidate/prepare.py"):
        sources[relative(path)] = sha(path)
    jobs = []
    for case in CASES:
        physical, template, _ = files(case)
        sources[relative(physical)] = sha(physical)
        sources[relative(template)] = sha(template)
        for label in SETTINGS:
            jobs.append(dict(key=f"{case}/{label}", case=case, label=label,
                             weights=weights(label), beam=64, stage_budget=500))
    manifest = dict(registered_at=now(), jobs=jobs, sources_sha256=sources,
                    policy="Six one-coordinate ±50% perturbations, renormalized; both objective and cheap initialization rank use the varied weights; original search source unchanged",
                    status="registered")
    write(target, manifest)
    return manifest


def run_one(case, label):
    manifest = register()
    job = next(j for j in manifest["jobs"] if (j["case"], j["label"]) == (case, label))
    target = HERE / "runs" / case / label / "result.json"
    if target.exists():
        return read(target)
    physical, template, scenario = files(case)
    model = TopologyModel(physical)
    seed = initial_state(case, model)
    reference = reference_state(case, model, seed)
    chosen = tuple(job["weights"])
    with patch.object(placement, "WEIGHTS", chosen), patch.object(
            search, "cheap_cost", lambda m, s: weighted_cheap_cost(m, s, chosen)):
        outcome = search.search(model, reference, a100_prefix=False, seed_state=seed)
    candidate = outcome.get("multi")
    assert candidate and candidate["status"] == "feasible"
    state = candidate["state"]
    checked = placement.validate(model, state)
    folder = target.parent
    saved = placement.save(model, template, state, folder,
                           dict(case=case, scenario=scenario, label=label, objective_weights=chosen,
                                search_wall_s=outcome["search_wall_s"],
                                score=candidate["score"], metrics=candidate["metrics"]))
    export_audit = _audit_export(folder, checked)
    row = dict(status="completed", case=case, scenario=scenario, label=label,
               objective_weights=chosen, score=candidate["score"],
               search_wall_s=outcome["search_wall_s"],
               candidate_evaluations=candidate["candidate_evaluations"],
               widths=saved["widths"], boundaries=[s["end"] for s in state["segments"][:-1]],
               active_gpus=saved["active_gpus"], layer_copies=saved["layer_copies"],
               compatible_paths=saved["compatible_paths"],
               solution_sha256=saved["solution_sha256"],
               sim_cluster_sha256=saved["sim_cluster_sha256"],
               placement_sha256=sha(folder / "placement.json"),
               physical_sha256=sha(physical), export_audit=export_audit,
               manifest_sha256=sha(HERE / "manifest.json"), finished_at=now())
    write(target, row)
    return row


def report():
    manifest = register()
    rows = []
    for job in manifest["jobs"]:
        target = HERE / "runs" / job["case"] / job["label"] / "result.json"
        assert target.exists(), target
        row = read(target)
        assert row["manifest_sha256"] == sha(HERE / "manifest.json")
        folder = target.parent
        for name, field in (("solution.ini", "solution_sha256"),
                            ("simulator_cluster.ini", "sim_cluster_sha256"),
                            ("placement.json", "placement_sha256")):
            assert sha(folder / name) == row[field]
        rows.append(row)
    with (HERE / "offline_individual.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        fields = ("case", "label", "objective_weights", "score", "search_wall_s",
                  "candidate_evaluations", "widths", "boundaries", "active_gpus",
                  "layer_copies", "compatible_paths", "solution_sha256", "sim_cluster_sha256")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})
    lines = ["# 放置权重敏感性：离线搜索", "",
             "分别把三项权重单独乘 0.5 或 1.5，再归一化。Beam=64，B0=B1=500；原搜索源代码未改。",
             "这一阶段只报告离线结构和搜索耗时，不能作为在线 TPOT/TTFT 结论。", "",
             "| 拓扑 | 权重变体 | 归一化权重 | 段副本数 | 边界 | 使用 GPU | 可行路径 | 搜索秒 |",
             "|---|---|---|---|---|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['scenario']} | {row['label']} | {row['objective_weights']} | "
                     f"{row['widths']} | {row['boundaries']} | {row['active_gpus']} | "
                     f"{row['compatible_paths']} | {row['search_wall_s']:.2f} |")
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write(HERE / "FINAL_AUDIT.json", dict(passed=True, jobs=len(rows),
          manifest_sha256=sha(HERE / "manifest.json"),
          csv_sha256=sha(HERE / "offline_individual.csv"),
          report_sha256=sha(HERE / "RESULTS_CN.md")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("one", "all", "report"))
    parser.add_argument("--case", choices=CASES)
    parser.add_argument("--label", choices=SETTINGS)
    args = parser.parse_args()
    if args.command == "one":
        assert args.case and args.label
        row = run_one(args.case, args.label)
        print(row["case"], row["label"], row["score"], flush=True)
    elif args.command == "all":
        manifest = register()
        for job in manifest["jobs"]:
            row = run_one(job["case"], job["label"])
            print(row["case"], row["label"], row["score"], flush=True)
        report()
    else:
        report()


if __name__ == "__main__":
    main()
