"""Integrated V4 adapter; frozen V3 placement and online route prices."""

from __future__ import annotations

import json
from pathlib import Path

from .v3_method import layout

NAME = "rcaps_v4"
DESCRIPTION = "V3 placement/routing with static sparse admission and slow-link 4 MiB transfer chunks"


def evaluate_variant(scenario, offered, duration, warmup, seed, solution, sim_cluster,
                     *, admission="sparse", chunk_bytes=4_194_304, scope="slow",
                     routing_state="live", mechanism=True, physical_cluster=None,
                     machine_counts=None):
    from benchmarks.fixed_window import run
    from .v4.admission import AdmissionScheduler
    from .v4.chunking import PromptTransferChunkHook
    from .v4.probe import MechanismProbe
    state = json.loads((Path(solution).parent / "placement.json").read_text(encoding="utf-8"))["state"]
    hook = PromptTransferChunkHook(chunk_bytes, scope=scope) if chunk_bytes else None
    probe = MechanismProbe(hook) if mechanism else hook
    holder = {}
    def factory(simulator):
        holder["scheduler"] = AdmissionScheduler(simulator, state=state, admission=admission,
                                                  routing_state=routing_state)
        return holder["scheduler"]
    row = run(scenario, "queue_dag", offered, duration, warmup, seed,
              solution, sim_cluster, profile_resources=True, scheduler_factory=factory,
              compact=True, record_query_samples=True, phase_link_probe=probe,
              physical_cluster=physical_cluster, machine_counts=machine_counts)
    row["admission"] = holder["scheduler"].summary()
    if mechanism:
        row.update(row["phase_link_profile"]["corrected_network_accounting"])
        row["network_accounting"] = "v4_chunk_aware_v1"
    return row


def evaluate(scenario, offered, duration, warmup, seed, solution, sim_cluster):
    return evaluate_variant(scenario, offered, duration, warmup, seed, solution, sim_cluster)
