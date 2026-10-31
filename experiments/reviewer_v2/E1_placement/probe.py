"""Before any formal run, verify multi-entry E1 layout through the real executor."""
import json
from pathlib import Path

from rcaps.v3.topology import TopologyModel
from rcaps.v3.resource_graph import from_simulator
from experiments.reviewer_v2.E1_placement.search_multi import assignments, _shape_requirements, build
from experiments.reviewer_v2.E1_placement.placement_multi import validate, measure, save

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def main():
    cases = json.loads((ROOT / "rcaps/v3/planning_inputs.json").read_text(encoding="utf-8"))
    item = cases["C1_single"]
    model = TopologyModel(ROOT / item["physical"])
    boundary, widths = 4, (2, 1)
    bins = assignments(model, _shape_requirements(model.layers, (boundary,), widths), a100_prefix=False)
    state = next((candidate for bucket in bins if
                  (candidate := build(model, (boundary,), widths, bucket)) is not None), None)
    if state is None:
        raise RuntimeError("Cannot construct verified multi-entry test placement")
    checked = validate(model, state)
    if len(state["segments"][0]["replicas"]) != 2 or checked["dag"].path_count() < 2:
        raise RuntimeError("Multi-entry validation failed")
    out = HERE / "probe_layout"
    record = save(model, ROOT / item["template"], state, out,
                  dict(probe_only=True, static_metrics=measure(model, state)))
    from benchmarks.fixed_window import run
    from rcaps.v4.admission import AdmissionScheduler
    from rcaps.v4.chunking import PromptTransferChunkHook
    from rcaps.v4.probe import MechanismProbe
    from experiments.v5_core_supplement.adapters import SetupProbe
    from benchmarks.layout import scenario as physical
    factory = lambda simulator: AdmissionScheduler(simulator, state=state, admission="sparse", routing_state="live")
    result = run("single", "queue_dag", 350, 60, 0, 107,
                 out / "solution.ini", out / "simulator_cluster.ini",
                 physical_cluster=physical("single")[0], scheduler_factory=factory,
                 compact=True, record_query_samples=True, profile_resources=True,
                 phase_link_probe=SetupProbe(delegate=MechanismProbe(
                     PromptTransferChunkHook(4_194_304, scope="slow"))))
    if len(result["route_counts"]) < 2:
        raise RuntimeError("The actual executor did not exercise multiple paths")
    summary = dict(passed=True, entries=[replica[0] for replica in state["segments"][0]["replicas"]],
                   path_count=checked["dag"].path_count(), actual_paths=result["route_counts"],
                   arrivals=result["arrivals"], output_throughput_tokens_per_s=result["output_throughput_tokens_per_s"],
                   solution_sha256=record["solution_sha256"], cluster_sha256=record["sim_cluster_sha256"])
    (HERE / "PROBE_AUDIT.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
