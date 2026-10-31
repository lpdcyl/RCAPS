"""Five-method, matched-trace SLO goodput simulator adapter."""
from __future__ import annotations

from pathlib import Path

from benchmarks.fixed_window import run
from experiments.v5_core_supplement.adapters import HelixPlus, SetupProbe
from experiments.v5_core_supplement.run import paths, read, sha
from experiments.v6_completion.session_cost import scheduler_for
from experiments.reviewer_v2.E2a_helix_tuning.adapters import factory as tuned_factory
from simulator.scheduler.global_maxflow.global_maxflow_scheduler import GlobalFlowScheduler

from .probe import GoodputProbe

ROOT = Path(__file__).resolve().parents[3]
METHODS = ("RCAPS", "RCAPS-batch", "Helix+", "Helix", "Helix-tuned")


class OriginalHelix(HelixPlus):
    schedule_transmission = GlobalFlowScheduler.schedule_transmission
    schedule_execution = GlobalFlowScheduler.schedule_execution


def tuned_params(case):
    from experiments.reviewer_v2.E2a_helix_tuning.run import HERE as e2a
    folder = e2a / "single_correction" if case == "single" else e2a
    selection = read(folder / "selection.json")
    first, last = ((350, 700) if case == "single" else (160, 320))
    a = selection[f"{case}/{first}"]["params"]
    b = selection[f"{case}/{last}"]["params"]
    if a != b:
        raise RuntimeError("E2a selected different settings within topology")
    return a


def evaluate(case, load, method, seed, *, warmup=300, measurement=1800, tail_cap=3600):
    if method not in METHODS:
        raise ValueError(method)
    layout_cell = "V4" if method.startswith("RCAPS") else "HH"
    solution, cluster, physical = paths(case, layout_cell)
    delegate = None
    if method == "Helix":
        scheduler_factory = OriginalHelix
    elif method == "Helix+":
        scheduler_factory = HelixPlus
    elif method == "Helix-tuned":
        params = tuned_params(case)
        scheduler_factory = tuned_factory(params["priority"], params["batch"],
                                          params["hwm"], params["ratio"])
    else:
        from rcaps.v4.admission import AdmissionScheduler
        from rcaps.v4.chunking import PromptTransferChunkHook
        from rcaps.v4.probe import MechanismProbe
        state = read(solution.parent / "placement.json")["state"]
        scheduler, routing_state = (
            (AdmissionScheduler, "live") if method == "RCAPS"
            else scheduler_for("batch"))
        scheduler_factory = lambda sim: scheduler(
            sim, state=state, admission="sparse", routing_state=routing_state)
        delegate = MechanismProbe(PromptTransferChunkHook(4_194_304, scope="slow"))
    probe = GoodputProbe(SetupProbe(delegate=delegate), case, tail_cap, warmup, measurement)
    row = run(case, "queue_dag", load, warmup+measurement, warmup, seed,
              solution, cluster, physical_cluster=physical,
              scheduler_factory=scheduler_factory, compact=True,
              record_query_samples=True, profile_resources=False,
              phase_link_probe=probe)
    row["drain"] = row["phase_link_profile"].pop("drain")
    row["goodput"] = row["phase_link_profile"].pop("goodput")
    row.update(cell=method, solution_sha256=sha(solution),
               sim_cluster_sha256=sha(cluster),
               evaluation_protocol=row["drain"]["evaluation_protocol"])
    if (len(row["drain"]["query_samples"]) != row["drain"]["arrivals"] or
            row["goodput"]["measurement_arrivals"] != row["drain"]["arrivals"]):
        raise RuntimeError("Goodput cohort accounting mismatch")
    return row
