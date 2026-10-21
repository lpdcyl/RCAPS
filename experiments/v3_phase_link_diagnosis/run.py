"""Serial fixed-window diagnosis of V3's slow-link phase interference.

Run from the repository root:
  python -m experiments.v3_phase_link_diagnosis.run --phase smoke
  python -m experiments.v3_phase_link_diagnosis.run --phase formal
  python -m experiments.v3_phase_link_diagnosis.run --phase analyze
  python -m experiments.v3_phase_link_diagnosis.run --phase confirm

Each job writes an atomic JSON result and a compressed per-message event stream.
Existing results with a matching identity are reused. Failed KV windows remain
visible as failure records and are never converted to zero throughput.
"""

from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import json
import traceback
from collections import defaultdict
from pathlib import Path

from benchmarks.fixed_window import run as fixed_window_run
from experiments.m2_multistage_candidate.prepare import files
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler
from rcaps.v3.topology import TopologyModel
from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder

from .probe import PhaseLinkProbe, percentile


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SEEDS = (1, 2, 3)
LOW, MID = 160, 320
HIGH_CANDIDATES = (350, 340, 330)
SOURCE_FILES = (
    "benchmarks/fixed_window.py",
    "benchmarks/accumulator.py",
    "simulator/event_simulator/network_link.py",
    "simulator/event_simulator/cluster_simulator.py",
    "rcaps/v3/online_scheduler.py",
    "experiments/v3_phase_link_diagnosis/probe.py",
    "experiments/v3_phase_link_diagnosis/run.py",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def source_hashes():
    return {name: digest(ROOT / name) for name in SOURCE_FILES}


def layout(case: str, variant: str):
    physical, _, scenario = files(case)
    parent = ROOT / "experiments/v3_m2_branch_parallelism/layouts" / case / variant
    solution = parent / "solution.ini"
    cluster = parent / "simulator_cluster.ini"
    for path in (physical, solution, cluster):
        if not path.exists():
            raise FileNotFoundError(path)
    return physical, solution, cluster, scenario


def trace_for(load: int, duration: int, seed: int):
    feeder = OnlineRequestFeeder(cluster_token_throughput=load,
                                 start_time=0, duration=duration, seed=seed)
    return [(arrival, inputs, outputs) for arrival, inputs, outputs in feeder.trace]


def result_path(phase, case, variant, treatment, load, seed):
    return (HERE / "runs" / phase / case / variant / treatment /
            f"load{load}_seed{seed}.json")


def route_summary(result):
    links = result.get("phase_link_profile", {}).get("links", [])
    edge = {(row["from"], row["to"]): row for row in links}
    total = sum(result["route_counts"].values())
    routes = []
    weighted_slow = 0
    weighted_hops = 0
    for route, count in sorted(result["route_counts"].items()):
        nodes = [int(part) for part in route.split("-") if part]
        traversed = [edge.get((a, b)) for a, b in zip(nodes, nodes[1:])]
        slow = sum(item is not None and item["compute_to_compute"] and
                   item["capacity_Bps"] <= 50_000_000 for item in traversed)
        hops = sum(item is not None and item["compute_to_compute"] for item in traversed)
        weighted_slow += count * slow
        weighted_hops += count * hops
        routes.append({"path": route, "count": count,
                       "share": count / total if total else None,
                       "slow_compute_links": slow, "compute_links": hops})
    return {"routes": routes, "mean_slow_compute_links_per_query":
            weighted_slow / total if total else None,
            "mean_compute_links_per_query": weighted_hops / total if total else None}


def verify_ledger(result, raw_path):
    actual = defaultdict(lambda: {"prompt": 0.0, "decode": 0.0})
    with gzip.open(raw_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            event = json.loads(line)
            if event["event"] == "start":
                actual[event["link_uid"]][event["phase"]] += event["physical_bytes"]
    for row in result["phase_link_profile"]["links"]:
        for phase in ("prompt", "decode"):
            if abs(row[f"{phase}_bytes"] - actual[row["link_uid"]][phase]) > 1e-5:
                raise AssertionError((row["link_uid"], phase, "byte ledger mismatch"))


def run_one(phase: str, case: str, variant: str, treatment: str,
            load: int, seed: int, duration: int, *, probe_enabled=True):
    physical, solution, cluster, scenario = layout(case, variant)
    output = result_path(phase, case, variant, treatment, load, seed)
    identity = {
        "phase": phase, "case": case, "variant": variant,
        "treatment": treatment, "load": load, "seed": seed,
        "duration_s": duration, "profile_enabled": probe_enabled,
        "solution_sha256": digest(solution),
        "sim_cluster_sha256": digest(cluster),
        "physical_sha256": digest(physical),
        "source_sha256": source_hashes(),
    }
    if output.exists():
        old = read(output)
        if all(old.get(key) == value for key, value in identity.items()):
            return old
        raise ValueError(f"Existing result has different identity: {output}")
    trace = trace_for(load, duration, seed)
    raw_path = output.with_suffix(".jsonl.gz") if probe_enabled else None
    probe = PhaseLinkProbe(raw_path, treatment) if probe_enabled else None
    output.parent.mkdir(parents=True, exist_ok=True)
    print(f"START {phase}/{case}/{variant}/{treatment}/load{load}/seed{seed}", flush=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as log, \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            row = fixed_window_run(
                scenario, "queue_dag", load, duration, 0, seed,
                solution, cluster, compact=True, record_query_samples=True,
                physical_cluster=physical,
                machine_counts=TopologyModel(physical).machine_counts,
                scheduler_factory=GraphModeledQueueAwareDagScheduler,
                trace_override=trace, phase_link_probe=probe)
            row.update(identity)
            if len(row["query_samples"]) != row["arrivals"]:
                raise AssertionError("Missing query samples")
            if probe_enabled:
                row["route_summary"] = route_summary(row)
                if phase == "smoke":
                    verify_ledger(row, raw_path)
            write(output, row)
            return row
        except Exception as exc:
            failure = {**identity, "status": "failed", "error": repr(exc),
                       "traceback": traceback.format_exc()}
            write(output.with_suffix(".failure.json"), failure)
            raise
        finally:
            if probe is not None:
                probe.close()


def smoke():
    plain = run_one("smoke", "C1_multi", "k1", "baseline_plain",
                    MID, 1, 60, probe_enabled=False)
    measured = run_one("smoke", "C1_multi", "k1", "baseline",
                       MID, 1, 60)
    fields = ("trace_sha256", "route_counts", "arrivals",
              "output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
              "completion_fraction", "backlog_at_window_end")
    mismatch = {field: [plain[field], measured[field]] for field in fields
                if plain[field] != measured[field]}
    write(HERE / "smoke_parity.json", {"fields": fields, "mismatch": mismatch,
                                        "passed": not mismatch})
    if mismatch:
        raise AssertionError(f"Probe changed baseline results: {mismatch}")
    print("Smoke parity and raw-byte ledger passed.")


def formal(section: str):
    if not read(HERE / "smoke_parity.json")["passed"]:
        raise RuntimeError("Smoke parity gate failed")
    if section in {"all", "high"}:
        selected = None
        for candidate in HIGH_CANDIDATES:
            statuses = []
            for variant in ("k1", "k3"):
                for seed in SEEDS:
                    try:
                        run_one("formal", "C1_multi", variant, "baseline",
                                candidate, seed, 600)
                        statuses.append(True)
                    except AssertionError as exc:
                        if "Exceed KV-cache capacity!" not in str(exc):
                            raise
                        statuses.append(False)
            if all(statuses):
                selected = candidate
                break
        write(HERE / "high_load_selection.json", {
            "candidate_order": HIGH_CANDIDATES, "selected": selected,
            "rule": "first candidate for which k1 and k3 pass all seeds"})
    if section in {"all", "baseline"}:
        selection = read(HERE / "high_load_selection.json")["selected"]
        loads = (LOW, MID) + ((selection,) if selection is not None else ())
        for load in loads:
            for variant in ("k1", "k3"):
                for seed in SEEDS:
                    run_one("formal", "C1_multi", variant, "baseline",
                            load, seed, 600)
    if section in {"all", "intervention"}:
        for treatment in ("prompt_zero", "decode_zero"):
            for variant in ("k1", "k3"):
                for seed in SEEDS:
                    run_one("formal", "C1_multi", variant, treatment,
                            MID, seed, 600)
    if section in {"all", "ideal"}:
        for variant in ("k1", "k3"):
            for seed in SEEDS:
                run_one("formal", "C1_multi", variant, "ideal_bandwidth",
                        MID, seed, 600)
    if section in {"all", "kv"}:
        for seed in SEEDS:
            try:
                run_one("formal", "C1_single", "k3", "baseline",
                        1100, seed, 600, probe_enabled=False)
            except AssertionError as exc:
                if "Exceed KV-cache capacity!" not in str(exc):
                    raise
    print("Formal section complete.")


def paired(base, intervention):
    left = base["query_samples"]
    right = intervention["query_samples"]
    common = [qid for qid in left.keys() & right.keys()
              if left[qid]["completed"] and right[qid]["completed"]]
    result = {"common_completed_queries": len(common)}
    for field in ("ttft_s", "tpot_s"):
        both = [qid for qid in common if left[qid][field] is not None
                and right[qid][field] is not None]
        result[field] = {"n": len(both),
                         "baseline_p95_s": percentile([left[qid][field] for qid in both], 95),
                         "treatment_p95_s": percentile([right[qid][field] for qid in both], 95)}
    return result


def collect():
    selection_path = HERE / "high_load_selection.json"
    selected = read(selection_path)["selected"] if selection_path.exists() else None
    loads = (LOW, MID) + ((selected,) if selected else ())
    results = {}
    for load in loads:
        for variant in ("k1", "k3"):
            for seed in SEEDS:
                path = result_path("formal", "C1_multi", variant, "baseline", load, seed)
                if path.exists():
                    results[(variant, "baseline", load, seed)] = read(path)
    for treatment in ("prompt_zero", "decode_zero", "ideal_bandwidth"):
        for variant in ("k1", "k3"):
            for seed in SEEDS:
                path = result_path("formal", "C1_multi", variant, treatment, MID, seed)
                if path.exists():
                    results[(variant, treatment, MID, seed)] = read(path)
    comparisons = []
    for (variant, treatment, load, seed), row in results.items():
        if treatment == "baseline":
            continue
        base = results.get((variant, "baseline", load, seed))
        if base is None:
            continue
        if row["trace_sha256"] != base["trace_sha256"]:
            raise AssertionError("Unpaired traces")
        comparisons.append({"variant": variant, "treatment": treatment,
                            "seed": seed, "load": load,
                            "delta_tpot_p95_s": row["tpot_p95_s"] - base["tpot_p95_s"],
                            "delta_ttft_p95_s": row["ttft_p95_s"] - base["ttft_p95_s"],
                            "delta_throughput_tok_s": row["output_throughput_tokens_per_s"] -
                                base["output_throughput_tokens_per_s"],
                            "delta_completion_fraction": row["completion_fraction"] -
                                base["completion_fraction"],
                            "delta_backlog": row["backlog_at_window_end"] -
                                base["backlog_at_window_end"],
                            "route_counts_baseline": base["route_counts"],
                            "route_counts_treatment": row["route_counts"],
                            "common_completed": paired(base, row)})
    analysis = {"selected_high_load": selected, "runs": {},
                "comparisons": comparisons}
    for (variant, treatment, load, seed), row in results.items():
        analysis["runs"][f"{variant}/{treatment}/load{load}/seed{seed}"] = {
            "trace_sha256": row["trace_sha256"],
            "throughput_tok_s": row["output_throughput_tokens_per_s"],
            "ttft_p95_s": row["ttft_p95_s"], "tpot_p95_s": row["tpot_p95_s"],
            "completion_fraction": row["completion_fraction"],
            "backlog": row["backlog_at_window_end"],
            "route_summary": row.get("route_summary"),
            "tail": row.get("phase_link_profile", {}).get("tail"),
            "all": row.get("phase_link_profile", {}).get("all"),
            "gpu_by_phase": row.get("phase_link_profile", {}).get("gpu_by_phase"),
            "slow_links": [link for link in row.get("phase_link_profile", {}).get("links", [])
                           if link["compute_to_compute"] and link["capacity_Bps"] <= 50_000_000],
        }
    write(HERE / "analysis.json", analysis)
    return analysis, results


def trigger_condition(analysis, results):
    paired_seeds = []
    for seed in SEEDS:
        base = results.get(("k1", "baseline", MID, seed))
        zero = results.get(("k1", "prompt_zero", MID, seed))
        if base is None or zero is None:
            return False, "missing k1 baseline or prompt_zero run"
        profile = base["phase_link_profile"]
        all_fraction = profile["all"]["same_link_blocked_fraction"]
        tail_fraction = profile["tail"]["same_link_blocked_fraction"]
        if all_fraction is None or tail_fraction is None:
            return False, "no eligible tail steps"
        reduction = (base["tpot_p95_s"] - zero["tpot_p95_s"]) / base["tpot_p95_s"]
        paired_seeds.append((seed, tail_fraction - all_fraction, reduction))
    passed = all(enrichment > 0 and reduction >= 0.10
                 for _, enrichment, reduction in paired_seeds)
    return passed, paired_seeds


def confirm():
    analysis, results = collect()
    passed, evidence = trigger_condition(analysis, results)
    write(HERE / "confirm_gate.json", {"passed": passed, "evidence": evidence,
        "rule": "k1 at load320: tail same-link blocked fraction above all and "
                "prompt_zero reduces TPOT P95 by >=10% in each of three seeds"})
    if not passed:
        print("Confirm gate did not pass; 1800-second and chunking controls are skipped.")
        return
    for treatment in ("baseline", "prompt_zero", "decode_zero"):
        for variant in ("k1", "k3"):
            for seed in SEEDS:
                run_one("confirm", "C1_multi", variant, treatment, MID, seed, 1800)
    print("1800-second confirmation complete. Chunking control requires full-event implementation.")


def analyze():
    from .report import generate
    analysis, results = collect()
    generate(analysis, results)
    print(f"Wrote {HERE / 'analysis.json'} and report artifacts.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "formal", "analyze", "confirm"),
                        required=True)
    parser.add_argument("--section", choices=("all", "high", "baseline", "intervention",
                                             "ideal", "kv"), default="all")
    args = parser.parse_args()
    if args.phase == "smoke":
        smoke()
    elif args.phase == "formal":
        formal(args.section)
    elif args.phase == "analyze":
        analyze()
    else:
        confirm()


if __name__ == "__main__":
    main()
