"""Read-only, post-hoc description of the frozen development matrix.

This does not rerun the simulator, tune the controller, estimate unobserved
counterfactuals, or supply an independent research review.
"""
from __future__ import annotations

import hashlib
import json
import statistics
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "work3_control/runs/v3"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def distribution(values):
    values = sorted(values)
    if not values:
        return {"count": 0}
    def quantile(q):
        at = (len(values) - 1) * q
        low = int(at)
        high = min(low + 1, len(values) - 1)
        return values[low] + (at-low) * (values[high]-values[low])
    return {"count": len(values), "mean": statistics.mean(values),
            "min": values[0], "p50": quantile(.5), "p95": quantile(.95),
            "max": values[-1]}


def main():
    analysis = read(RUN / "development_analysis.json")
    integrity = read(RUN / "development_extended_verification.json")
    index = read(RUN / "development_index.json")
    assert integrity["all_passed"] and integrity["historical_analyses_unchanged"]
    assert index["complete"] and len(index["jobs"]) == index["expected"] == 10
    assert all(job["exit_code"] == 0 for job in index["jobs"].values())
    evidence = {p["source"]: p["sha256"] for p in analysis["validation"]}
    records = []
    control = []
    for seed in (104, 105):
        raw = {}
        for policy in ("canonical", "partial", "full", "adaptive_link", "route_control"):
            path = RUN / "development" / f"{policy}_seed{seed}.json"
            assert digest(path) == evidence[str(path.relative_to(ROOT))]
            row = raw[policy] = read(path)
            metrics = analysis["metrics"][str(seed)][policy]
            assert row["seed"] == seed and row["policy"] == policy
            assert row["lifecycle"]["arrivals"] == row["lifecycle"]["completed"]
            verification = next(r for r in integrity["records"]
                                if r["seed"] == seed and r["policy"] == policy)
            records.append({"seed": seed, "policy": policy, **metrics,
                            "arrivals": row["lifecycle"]["arrivals"],
                            "completed": row["lifecycle"]["completed"],
                            "output_tokens": row["lifecycle"]["output_tokens_completed"],
                            "active_gpus": verification["active_gpus"],
                            "kv_peak_fraction": verification["kv_peak_fraction"],
                            "cpu_route": row["window"]["scheduler_call_profile"]["_route"],
                            "stage_arrival_cohorts": verification["stage_arrival_cohorts"]})
        controller = raw["route_control"]
        events = controller["control_events"]
        comparable = [e for e in events if not e["capacity_fallback"]]
        different = [e for e in comparable if e["candidates_differ"]]
        selected = [e for e in different if e["selected_expanded"]]
        vetoed = [e for e in different if e["cost_baseline_s"] > e["cost_expanded_s"]
                  and e["net_proxy_s"] <= 0]
        positive_blocked = [e for e in different if e["net_proxy_s"] > 0
                            and not e["selected_expanded"]]
        verified = next(r for r in integrity["records"]
                        if r["seed"] == seed and r["policy"] == "route_control")
        cmetrics = analysis["metrics"][str(seed)]["route_control"]
        comparisons = {}
        for policy in ("canonical", "partial", "full", "adaptive_link"):
            base = analysis["metrics"][str(seed)][policy]
            comparisons[policy] = {
                "tpot_relative_change": cmetrics["tpot"] / base["tpot"] - 1,
                "ttft_relative_change": cmetrics["ttft"] / base["ttft"] - 1,
                "throughput_relative_change": cmetrics["throughput"] / base["throughput"] - 1,
                "gpu_work_relative_change": cmetrics["gpu_per_token"] / base["gpu_per_token"] - 1,
                "mean_decode_batch_relative_change": cmetrics["batch"] / base["batch"] - 1,
                "cpu_route_p95_ratio": cmetrics["route_cpu_p95_us"] / base["route_cpu_p95_us"],
            }
        control.append({
            "seed": seed, "counts": controller["control_counts"],
            "gate_switches": controller["control_switches"],
            "capacity_fallbacks": sum(e["capacity_fallback"] for e in events),
            "positive_net_blocked_by_gate": len(positive_blocked),
            "selected_fraction_of_distinct_candidates": len(selected)/len(different),
            "batch_veto_count": len(vetoed),
            "selected_with_zero_penalty": sum(e["batch_penalty_s"] == 0 for e in selected),
            "selected_prompt_relief_s": distribution(
                [e["cost_baseline_s"]-e["cost_expanded_s"] for e in selected]),
            "selected_batch_penalty_s": distribution([e["batch_penalty_s"] for e in selected]),
            "selected_batch_delta_s": distribution(
                [e["batch_expanded_s"]-e["batch_baseline_s"] for e in selected]),
            "selected_cost_term_relief_mean_s": {
                term: statistics.mean(e["terms_baseline"].get(term, 0)-e["terms_expanded"].get(term, 0)
                                      for e in selected)
                for term in ("prompt_s", "transfer_s", "link_wait_s", "gpu_wait_s", "session_s")},
            "stage_actions": verified["control_reconstruction"]["stage_actions"],
            "comparisons": comparisons,
        })
    aggregate = {key: {"paired_mean": statistics.mean(c["comparisons"]["full"][key] for c in control),
                       "paired_sample_std": statistics.stdev(c["comparisons"]["full"][key] for c in control)}
                 for key in ("tpot_relative_change", "gpu_work_relative_change")}
    result = {"classification": "post_hoc_descriptive_only", "revision": "v3",
              "generated_at_local": datetime.now().astimezone().isoformat(),
              "script_sha256": digest(Path(__file__)),
              "inputs": {str(p.relative_to(ROOT)): digest(p) for p in
                         (RUN/"development_analysis.json", RUN/"development_extended_verification.json",
                          RUN/"development_index.json")},
              "raw_result_sha256": evidence, "records": records, "control": control,
              "paired_description_vs_full": aggregate, "registered_decision": analysis["decision"],
              "limits": ["Two development seeds; no significance or generality claim.",
                         "Simulated GPU time; CPU overhead is separate and not charged to the simulation.",
                         "Observed per-stage cohorts overlap in service time; not steady-state experiments.",
                         "No same-state counterfactual outcomes or causal ablations were observed.",
                         "One decode-round proxy is not lifetime TPOT or GPU-work prediction.",
                         "A failed development gate stops this candidate; it does not refute all adaptive control.",
                         "Independent reviewer unavailable; no claim acceptance is issued."]}
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    versioned = RUN / f"development_mechanism_{stamp}.json"
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    versioned.write_text(output, encoding="utf-8")
    (RUN/"development_mechanism.json").write_text(output, encoding="utf-8")
    print(json.dumps({"source": str(versioned.relative_to(ROOT)), "control": control,
                      "paired_description_vs_full": aggregate}, ensure_ascii=False))


if __name__ == "__main__":
    main()
