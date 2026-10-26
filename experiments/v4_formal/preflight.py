"""Engineering parity checks, not development or parameter-selection runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from benchmarks.fixed_window import run
from experiments.v3_cycle_pricing.run import physical_input, scheduler_factory
from experiments.v3_gated_pathspace.scheduler import SlowLinkGatedScheduler
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler
from rcaps.v3.topology import TopologyModel
from rcaps.v4.probe import IntervalUnion
from rcaps.v4_method import evaluate_variant
from work3_selective_chunk.chunking import SlowLinkPromptTransferChunkHook

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ("trace_sha256", "arrivals", "output_throughput_tokens_per_s", "ttft_p95_s",
          "tpot_p95_s", "completion_fraction", "backlog_at_window_end", "route_counts",
          "query_samples", "gpu_busy_fraction")


def main():
    union = IntervalUnion()
    for a, b in [(0, 2), (1, 3), (4, 5)]:
        union.add(a, b)
    assert union.overlap(1, 4.5) == 2.5
    checks = []
    for scenario, admission, chunk in [("multi", "full", 0), ("multi", "sparse", 0),
                                       ("multi", "full", 4_194_304),
                                       ("multi", "sparse", 4_194_304),
                                       ("single", "sparse", 4_194_304)]:
        physical, _ = physical_input("C1_" + scenario)
        canonical = scheduler_factory("C1_" + scenario, "canonical").keywords["allowed_edges"]
        factory = (GraphModeledQueueAwareDagScheduler if admission == "full" else
                   lambda sim: SlowLinkGatedScheduler(sim, allowed_edges=canonical))
        layout = ROOT / "rcaps/v3_layouts" / scenario
        kwargs = dict(physical_cluster=physical, machine_counts=TopologyModel(physical).machine_counts)
        old = run(scenario, "queue_dag", 320 if scenario == "multi" else 700,
                  60, 0, 0, layout / "solution.ini", layout / "simulator_cluster.ini",
                  profile_resources=True, scheduler_factory=factory, compact=True,
                  record_query_samples=True,
                  phase_link_probe=SlowLinkPromptTransferChunkHook(chunk, 50_000_000) if chunk else None,
                  **kwargs)
        new = evaluate_variant(scenario, 320 if scenario == "multi" else 700,
                               60, 0, 0, layout / "solution.ini", layout / "simulator_cluster.ini",
                               admission=admission, chunk_bytes=chunk, **kwargs)
        for key in FIELDS:
            assert old[key] == new[key], (scenario, admission, chunk, key)
        probe = new["phase_link_profile"]
        for label, stats in probe["gpu"].items():
            assert abs(stats["busy_s"] / 60 - new["gpu_busy_fraction"][label]) < 1e-10
        if not chunk or scenario == "single":
            for key in ("link_occupied_fraction", "link_service_request_s", "link_propagation_request_s"):
                for label, value in new[key].items():
                    assert abs(value - old[key].get(label, 0)) < 1e-7, (key, label)
        else:
            assert probe["chunking"]["paused_chunks"] > 0, "Parity fixture must exercise resumes"
            assert sum(new["link_service_request_s"].values()) > sum(old["link_service_request_s"].values())
        checks.append({"scenario": scenario, "admission": admission, "chunk_bytes": chunk,
                       "seed": 0, "duration_s": 60, "status": "passed",
                       "trace_sha256": new["trace_sha256"]})
        print("PARITY", checks[-1], flush=True)
    sources = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in (list((ROOT / "rcaps/v4").glob("*.py")) + [ROOT / "rcaps/v4_method.py"])}
    result = {"kind": "engineering_parity_not_formal_performance", "checks": checks,
              "sources_sha256": sources, "status": "passed"}
    target = ROOT / "experiments/v4_formal/preflight.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("V4_PREFLIGHT_PASSED", flush=True)


if __name__ == "__main__":
    main()
