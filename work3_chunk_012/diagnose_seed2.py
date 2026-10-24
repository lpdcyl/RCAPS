"""Isolated diagnostic replay after the preserved sequential-run seed-2 failure.

This file is not part of the frozen 0/1/2 candidate runner or audit and does
not write a replacement result window.
"""

from __future__ import annotations

import json
import traceback

from benchmarks.fixed_window import run as fixed_window_run
from experiments.v3_cycle_pricing.run import physical_input, scheduler_factory
from experiments.v3_gated_pathspace.scheduler import SlowLinkGatedScheduler
from rcaps.v3.topology import TopologyModel
from work3_chunk_012.run import HERE, PROTOCOL, ROOT
from work3_selective_chunk.chunking import SlowLinkPromptTransferChunkHook


def main() -> None:
    physical, topology = physical_input(PROTOCOL["case"])
    deployment = ROOT / "rcaps" / "v3_layouts" / topology
    canonical = scheduler_factory(PROTOCOL["case"], "canonical").keywords["allowed_edges"]
    hook = SlowLinkPromptTransferChunkHook(PROTOCOL["chunk_bytes"],
                                           PROTOCOL["slow_link_threshold_Bps"])
    try:
        row = fixed_window_run(
            topology, "queue_dag", PROTOCOL["offered_tokens_per_s"],
            PROTOCOL["duration_s"], PROTOCOL["warmup_s"], 2,
            deployment / "solution.ini", deployment / "simulator_cluster.ini",
            profile_resources=True, compact=True, record_query_samples=True,
            physical_cluster=physical,
            machine_counts=TopologyModel(physical).machine_counts,
            scheduler_factory=lambda sim: SlowLinkGatedScheduler(sim, allowed_edges=canonical),
            phase_link_probe=hook)
        result = {"status": "completed_in_isolated_process", "seed": 2,
                  "trace_sha256": row["trace_sha256"], "arrivals": row["arrivals"],
                  "tpot_p95_s": row["tpot_p95_s"],
                  "output_throughput_tokens_per_s": row["output_throughput_tokens_per_s"],
                  "chunk_bytes": row["phase_link_profile"]["chunk_bytes"]}
    except Exception as error:
        frames = []
        tb = error.__traceback__
        while tb is not None:
            frame = tb.tb_frame
            item = {"file": frame.f_code.co_filename, "function": frame.f_code.co_name,
                    "line": tb.tb_lineno}
            if frame.f_code.co_filename.endswith("event_simulator\\model.py") and \
                    frame.f_code.co_name == "get_inference_statistics":
                local = frame.f_locals
                layer = local.get("self")
                item.update({
                    "layer_id": getattr(layer, "layer_id", None),
                    "prompt_tokens": local.get("prompt_phase_tokens"),
                    "decode_tokens": local.get("decode_phase_tokens"),
                    "decode_left": local.get("decode_left"),
                    "decode_right": local.get("decode_right"),
                    "decode_time_type": type(local.get("decode_time")).__name__,
                    "decode_profile_types": {str(k): type(v).__name__ for k, v in
                                             getattr(layer, "decode_bs2time", {}).items()},
                })
            frames.append(item)
            tb = tb.tb_next
        result = {"status": "failed_in_isolated_process", "seed": 2,
                  "error": repr(error), "traceback": traceback.format_exc(),
                  "frames": frames}
    output = HERE / "diagnostic_seed2.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    print(result["status"])


if __name__ == "__main__":
    main()
