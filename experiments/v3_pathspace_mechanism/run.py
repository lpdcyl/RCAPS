"""T2 step A: passive full-DAG versus canonical-path diagnosis."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import traceback
from functools import partial
from pathlib import Path

from benchmarks.fixed_window import run as fixed_window_run
from experiments.m2_multistage_candidate.placement import digest, validate
from experiments.m2_multistage_candidate.prepare import files
from experiments.v3_pathspace_ablation.run import CanonicalGraphDagScheduler, canonical_edges
from experiments.v3_pathspace_mechanism.probe import PathSpaceProbe
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler
from rcaps.v3.topology import TopologyModel


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CASES = {"C1_single": ("single", 700.0), "C1_multi": ("multi", 320.0)}
VARIANTS = ("canonical", "full")
SEEDS = (0, 1, 2)
FIELDS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
          "completion_fraction", "backlog_at_window_end", "route_counts")
HYPOTHESES = {
    "H1": ("mean_compute_links_per_query", 1),
    "H2": ("mean_gpu_token_weighted_decode_batch_size", -1),
    "H3": ("mean_top3_gpu_busy_fraction", 1),
    "H4": ("message_weighted_decode_same_link_prompt_blocked_fraction", 1),
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    part.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    part.replace(path)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def require_environment() -> None:
    for key, value in (("PYTHONHASHSEED", "0"), ("MPLBACKEND", "Agg")):
        if os.environ.get(key) != value:
            raise EnvironmentError(f"{key} must be {value!r}; found {os.environ.get(key)!r}")


def case_config(case: str):
    scenario, offered = CASES[case]
    physical, _, topology = files(case)
    assert scenario == topology
    deployment = ROOT / "rcaps/v3_layouts" / scenario
    solution = deployment / "solution.ini"
    sim_cluster = deployment / "simulator_cluster.ini"
    model = TopologyModel(physical)
    state = read(deployment / "placement.json")["state"]
    dag = validate(model, state)["dag"]
    base_edges = canonical_edges(state, dag)
    offset = 2
    allowed = frozenset((a if isinstance(a, str) else a + offset,
                         b if isinstance(b, str) else b + offset)
                        for a, b in base_edges)
    return scenario, offered, physical, solution, sim_cluster, model, allowed


def reference_path(case: str, variant: str, seed: int) -> Path:
    if variant == "canonical":
        return ROOT / "experiments/v3_pathspace_ablation/runs/formal" / case / f"seed{seed}.json"
    return ROOT / "benchmarks/runs" / CASES[case][0] / f"seed{seed}" / "rcaps_v3.json"


def diagnostics(row: dict, allowed: frozenset) -> dict:
    links = row["phase_link_profile"]["links"]
    compute_edges = {(int(link["from"]), int(link["to"])) for link in links
                     if link["compute_to_compute"]}
    total_routes = sum(row["route_counts"].values())
    nodes_weighted = hops_weighted = 0
    cross_counts = {}
    for route, count in row["route_counts"].items():
        nodes = [int(part) for part in route.split("-") if part]
        edges = list(zip(nodes, nodes[1:]))
        nodes_weighted += count * len(nodes)
        hops_weighted += count * sum(edge in compute_edges for edge in edges)
        for left, right in edges:
            if (left, right) not in allowed and (left, right) in compute_edges:
                key = f"{left}-{right}"
                cross_counts[key] = cross_counts.get(key, 0) + count
    gpu_busy = row["gpu_busy_fraction"]
    # ResourceProfile keys by entity_name; probe uses numeric node UID.
    numeric_busy = {}
    for label, value in gpu_busy.items():
        uid = int(label.removeprefix("Compute-").removeprefix("compute_node_"))
        numeric_busy[uid] = value
    batches = row["phase_link_profile"]["path_space"]["gpu_decode_batch"]
    batch_means = [entry["token_weighted_mean"] for entry in batches.values()]
    blocking_numerator = blocking_denominator = 0.0
    for link in links:
        if not link["compute_to_compute"]:
            continue
        samples = link["decode_same_prompt_samples"]
        fraction = link["decode_same_prompt_blocked_fraction"]
        if samples and fraction is not None:
            blocking_numerator += samples * fraction
        # PhaseLinkProbe stores an overlap sample only when a Decode message
        # waited. The denominator is all Decode messages on compute links.
        blocking_denominator += link["decode_messages"]
    cross_rows = []
    for edge, count in sorted(cross_counts.items()):
        left, right = map(int, edge.split("-"))
        cross_rows.append({"edge": edge, "count": count,
                           "from_gpu_busy_fraction": numeric_busy.get(left),
                           "to_gpu_busy_fraction": numeric_busy.get(right)})
    return {
        "mean_compute_nodes_per_query": nodes_weighted / total_routes if total_routes else None,
        "mean_compute_links_per_query": hops_weighted / total_routes if total_routes else None,
        "mean_gpu_token_weighted_decode_batch_size":
            sum(batch_means) / len(batch_means) if batch_means else None,
        "mean_top3_gpu_busy_fraction": sum(sorted(gpu_busy.values(), reverse=True)[:3]) / 3,
        "message_weighted_decode_same_link_prompt_blocked_fraction":
            blocking_numerator / blocking_denominator if blocking_denominator else None,
        "message_weighted_decode_denominator": blocking_denominator,
        "cross_replica_edge_uses": sum(cross_counts.values()),
        "cross_replica_edges": cross_rows,
    }


def run_one(case: str, variant: str, seed: int, duration: int, destination: Path) -> dict:
    require_environment()
    scenario, offered, physical, solution, sim_cluster, model, allowed = case_config(case)
    identity = {
        "task": "T2_step_A", "case": case, "variant": variant, "seed": seed,
        "duration_s": duration, "offered_tokens_per_s": offered,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "mplbackend": os.environ.get("MPLBACKEND"),
        "physical_sha256": digest(physical), "solution_sha256": digest(solution),
        "sim_cluster_sha256": digest(sim_cluster),
        "protocol_sha256": digest(HERE / "protocol.json"),
        "runner_sha256": digest(HERE / "run.py"), "probe_sha256": digest(HERE / "probe.py"),
    }
    if destination.exists():
        old = read(destination)
        if all(old.get(key) == value for key, value in identity.items()):
            return old
        raise ValueError(f"Existing window identity differs: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    scheduler_factory = (partial(CanonicalGraphDagScheduler, allowed_edges=allowed)
                         if variant == "canonical" else GraphModeledQueueAwareDagScheduler)
    probe = PathSpaceProbe()
    with destination.with_suffix(".log").open("w", encoding="utf-8") as log, \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            row = fixed_window_run(
                scenario, "queue_dag", offered, duration, 0, seed,
                solution, sim_cluster, profile_resources=True, compact=True,
                record_query_samples=True, physical_cluster=physical,
                machine_counts=model.machine_counts,
                scheduler_factory=scheduler_factory, phase_link_probe=probe)
            row.update(identity)
            if len(row["query_samples"]) != row["arrivals"]:
                raise AssertionError("Incomplete query samples")
            row["path_space_diagnostics"] = diagnostics(row, allowed)
            write(destination, row)
            return row
        except Exception as exc:
            traceback.print_exc(file=log)
            write(destination.with_suffix(".failure.json"),
                  {**identity, "status": "failed", "error": repr(exc),
                   "exception_type": type(exc).__name__, "traceback": traceback.format_exc(),
                   "log": relative(destination.with_suffix(".log"))})
            raise
        finally:
            probe.close()


def compare(row: dict, reference: dict) -> dict:
    return {field: {"new": row.get(field), "reference": reference.get(field)}
            for field in ("trace_sha256", *FIELDS)
            if row.get(field) != reference.get(field)}


def smoke(case: str, variant: str):
    require_environment()
    rows = []
    for attempt in (7, 8):
        destination = HERE / "runs/smoke" / case / variant / f"seed100_attempt{attempt}.json"
        rows.append(run_one(case, variant, 100, 60, destination))
    fields = ("trace_sha256", "arrivals", *FIELDS, "path_space_diagnostics",
              "phase_link_profile", "gpu_busy_fraction")
    mismatch = {field: [rows[0].get(field), rows[1].get(field)] for field in fields
                if rows[0].get(field) != rows[1].get(field)}
    result = {"case": case, "variant": variant, "seed": 100, "duration_s": 60,
              "fields": list(fields), "mismatch": mismatch, "passed": not mismatch}
    write(HERE / "smoke_parity.json", result)
    if mismatch:
        raise AssertionError(f"60-second deterministic parity failed: {list(mismatch)}")
    print("T2 60-second deterministic parity passed")


def formal(workers: int):
    require_environment()
    if not read(HERE / "smoke_parity.json")["passed"]:
        raise RuntimeError("Smoke parity gate not passed")
    # A single process ensures an immediate stop on a reproduction or interpreter failure.
    # workers is accepted for CLI compatibility but deliberately capped at one here.
    index_path = HERE / "index.json"
    index = read(index_path) if index_path.exists() else {"task": "T2_step_A", "jobs": {}}
    for case in CASES:
        for variant in VARIANTS:
            for seed in SEEDS:
                key = f"{case}/{variant}/seed{seed}"
                destination = HERE / "runs/formal" / case / variant / f"seed{seed}.json"
                try:
                    row = run_one(case, variant, seed, 1800, destination)
                    mismatch = compare(row, read(reference_path(case, variant, seed)))
                    status = "passed" if not mismatch else "reproduction_mismatch"
                    index["jobs"][key] = {
                        "status": status, "path": relative(destination),
                        "sha256": digest(destination), "trace_sha256": row["trace_sha256"],
                        "reference": relative(reference_path(case, variant, seed)),
                        "reproduction_mismatch": mismatch,
                    }
                    write(index_path, index)
                    print(status.upper(), key, flush=True)
                    if mismatch:
                        raise AssertionError(f"Reproduction mismatch: {key}: {list(mismatch)}")
                except Exception as exc:
                    if key not in index["jobs"]:
                        failure = destination.with_suffix(".failure.json")
                        index["jobs"][key] = {
                            "status": "failed", "path": relative(failure) if failure.exists() else None,
                            "error": repr(exc), "exception_type": type(exc).__name__,
                        }
                        write(index_path, index)
                    raise
    print("All 12 reproduction checks passed")


def _hypothesis(rows: dict, case: str, key: str):
    field, sign = HYPOTHESES[key]
    pair = []
    for seed in SEEDS:
        canonical = rows[f"{case}/canonical/seed{seed}"][field]
        full = rows[f"{case}/full/seed{seed}"][field]
        pair.append({"seed": seed, "canonical": canonical, "full": full,
                     "difference": full - canonical,
                     "relative_difference": (full - canonical) / canonical if canonical else None})
    cm = sum(item["canonical"] for item in pair) / 3
    fm = sum(item["full"] for item in pair) / 3
    relative = (fm - cm) / cm if cm else None
    same_direction = all(sign * item["difference"] > 0 for item in pair)
    confirmed = same_direction and relative is not None and sign * relative >= 0.05
    return {"statistic": field, "pairs": pair, "canonical_mean": cm, "full_mean": fm,
            "relative_difference_of_means": relative, "all_three_expected_direction": same_direction,
            "confirmed": confirmed}


def report():
    index = read(HERE / "index.json")
    if len(index["jobs"]) != 12 or any(item["status"] != "passed" for item in index["jobs"].values()):
        raise RuntimeError("All 12 formal windows must pass reproduction before analysis")
    rows = {key: read(ROOT / item["path"])["path_space_diagnostics"]
            for key, item in index["jobs"].items()}
    findings = {case: {hyp: _hypothesis(rows, case, hyp) for hyp in HYPOTHESES} for case in CASES}
    interpretations = {}
    for hyp in HYPOTHESES:
        single = findings["C1_single"][hyp]
        multi = findings["C1_multi"][hyp]
        if not single["confirmed"]:
            interpretations[hyp] = "单集群未确认"
        elif not multi["confirmed"]:
            interpretations[hyp] = "可解释拓扑差异"
        else:
            interpretations[hyp] = "不能解释拓扑差异"
    h1 = interpretations["H1"] == "可解释拓扑差异"
    t12 = "建议启用项 X，针对跨副本切换增加的路径链路数" if h1 else "不建议基于 H1 启用项 X"
    analysis = {"reproduction_check": "12/12 exact match", "findings": findings,
                "topology_interpretation": interpretations, "t12_switch_cost_recommendation": t12}
    from experiments.v3_pathspace_mechanism.report import global_metrics
    global_result, global_lines = global_metrics(ROOT, index, CASES, SEEDS)
    analysis["global_metrics"] = global_result
    write(HERE / "analysis.json", analysis)
    lines = ["# T2 步骤 A：完整 DAG 退化诊断", "", "## 复现检查", "",
             "12 个窗口的吞吐、P95 TTFT、P95 TPOT、完成率、积压、route_counts 和轨迹哈希逐项与既有正式结果相同。", "",
             "## 假设检验", "", "确认口径：单集群三个种子同向，且三种子均值相对差至少 5%。", ""]
    for case in CASES:
        lines += [f"### {case}", "", "| 假设 | 种子 | 规范路径 | 完整 DAG | 相对差 |", "| --- | ---: | ---: | ---: | ---: |"]
        for hyp, outcome in findings[case].items():
            for item in outcome["pairs"]:
                lines.append(f"| {hyp} | {item['seed']} | {item['canonical']:.6f} | {item['full']:.6f} | {item['relative_difference']:+.2%} |")
            lines.append(f"| {hyp} 均值 | — | {outcome['canonical_mean']:.6f} | {outcome['full_mean']:.6f} | {outcome['relative_difference_of_means']:+.2%} |")
        lines += [""]
    lines += ["## 判定", ""] + [f"- {hyp}：{interpretations[hyp]}。" for hyp in HYPOTHESES]
    lines += ["", "## T12 项 X 建议", "", t12, ""] + global_lines
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "formal", "report"), required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--case", choices=tuple(CASES), default="C1_single")
    parser.add_argument("--variant", choices=VARIANTS, default="full")
    args = parser.parse_args()
    if args.phase == "smoke":
        smoke(args.case, args.variant)
    elif args.phase == "formal":
        formal(args.workers)
    else:
        report()


if __name__ == "__main__":
    main()
