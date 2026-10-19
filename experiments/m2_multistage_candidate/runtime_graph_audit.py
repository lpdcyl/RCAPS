"""Compare every exported placement edge with M3's loaded execution DAG."""

from __future__ import annotations

import argparse
import json

from benchmarks.layout import _NullLogger, load_graph_layout
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler
from rcaps.v3.resource_graph import from_simulator
from rcaps.v3.topology import TopologyModel
from simulator.event_simulator.cluster_simulator import ClusterSimulator
from simulator.model_manager.model_manager import ModelName

from .placement import HERE, validate
from .prepare import CASES, VARIANTS, files


def audit(cases=CASES) -> dict:
    records = {}
    for case in cases:
        physical, _, _ = files(case)
        model = TopologyModel(physical)
        records[case] = {}
        for variant in VARIANTS:
            folder = HERE / "layouts" / case / variant
            if not (folder / "placement.json").exists():
                continue
            placement = json.loads((folder / "placement.json").read_text(encoding="utf-8"))
            expected = validate(model, placement["state"])
            simulator = ClusterSimulator(model_name=ModelName.LLaMa70B,
                                         machine_num_dict=model.machine_counts)
            simulator.logger = _NullLogger()
            simulator.from_ini_file(config_file_name=str(folder / "simulator_cluster.ini"))
            simulator.set_scheduler(GraphModeledQueueAwareDagScheduler(simulator))
            simulator.init_query_manager()
            simulator.mark_as_ready()
            load_graph_layout(simulator, folder / "solution.ini")
            runtime = from_simulator(simulator)
            normalized_edges = frozenset((
                left if left == "source" else left - 2,
                right if right == "sink" else right - 2)
                for left, right in runtime.edges)
            normalized_spans = {node - 2: span for node, span in runtime.spans.items()}
            if normalized_edges != expected["dag"].edge_set or \
                    normalized_spans != expected["spans"]:
                raise ValueError(f"Runtime DAG differs from export: {case}/{variant}")
            records[case][variant] = {"status": "identical", "edges": len(runtime.edges),
                                      "paths": runtime.path_count(),
                                      "active_gpus": len(runtime.spans)}
    (HERE / "runtime_graph_audit.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8")
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES)
    args = parser.parse_args()
    result = audit((args.case,) if args.case else CASES)
    print(sum(len(group) for group in result.values()), "runtime graphs checked")
