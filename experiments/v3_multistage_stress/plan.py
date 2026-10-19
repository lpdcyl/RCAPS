"""Plan controlled single/multistage layouts under uniform or layered costs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

from rcaps.v3 import placement, search
from rcaps.v3.topology import TopologyModel

from . import cost
from .pool import HERE, PHYSICAL, TEMPLATE, prepare


SCENES = {"mid_x1": ((32, 48), 1.0),
          "mid_x2": ((32, 48), 2.0),
          "mid_x4": ((32, 48), 4.0),
          "front_x4": ((0, 16), 4.0)}
INFORMATIONS = ("uniform", "layer_aware")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def first_built(model: TopologyModel, boundaries: tuple[int, ...],
                widths: tuple[int, ...]) -> dict:
    positions = (0, *boundaries, model.layers)
    required = [end - start for start, end, width in zip(
        positions, positions[1:], widths) for _ in range(width)]
    for assignment in search.assignments(model, required, a100_prefix=False, keep=64):
        state = search.build(model, boundaries, widths, assignment)
        if state is not None:
            return state
    raise ValueError(f"No legal witness for {boundaries}/{widths}")


def run() -> None:
    prepare()
    model = TopologyModel(PHYSICAL)
    reference = first_built(model, (32,), (1, 2))
    witness = first_built(model, (32, 48), (1, 4, 1))
    cost.assert_unit_parity(model, [reference, witness])
    if placement.validate(model, witness)["layer_copies"] != 128:
        raise ValueError("The 1→4→1 witness is not 128 layer copies")
    placement.save(model, TEMPLATE, witness, HERE / "layouts/witness_1_4_1",
                   {"purpose": "predeclared structural diagnostic", "boundaries": [32, 48]})
    write_json(HERE / "reference.json", {"state": reference,
                                           "uniform_metrics": placement.measure(model, reference),
                                           "physical_sha256": placement.digest(PHYSICAL),
                                           "template_sha256": placement.digest(TEMPLATE)})
    manifest = {"scenes": SCENES, "physical_sha256": placement.digest(PHYSICAL),
                "template_sha256": placement.digest(TEMPLATE), "results": {}}
    for information in INFORMATIONS:
        for scene, (interval, multiplier) in SCENES.items():
            if information == "uniform" and scene != "mid_x1":
                continue  # The frozen V3 score cannot distinguish these scenes.
            if information == "layer_aware":
                local_measure = lambda m, s, i=interval, x=multiplier: cost.measure(
                    m, s, interval=i, multiplier=x)
                local_cheap = lambda m, s, i=interval, x=multiplier: cost.cheap_cost(
                    m, s, interval=i, multiplier=x)
            else:
                local_measure = placement.measure
                local_cheap = search.cheap_cost
            # All patching is process-local; the frozen V3 modules on disk stay intact.
            with patch.object(search, "measure", local_measure), patch.object(
                    search, "cheap_cost", local_cheap):
                result = search.search(model, reference, a100_prefix=False)
            if result.get("status") == "infeasible":
                raise ValueError("No legal stress-pool single-boundary initializer")
            for mode in ("single", "multi"):
                item = result[mode]
                key = f"{information}/{scene}/{mode}"
                if item["status"] != "feasible":
                    manifest["results"][key] = item
                    continue
                destination = HERE / "layouts" / information / scene / mode
                metadata = {"information": information, "scene": scene,
                            "candidate_evaluations": item["candidate_evaluations"],
                            "common_evaluations": item["common_evaluations"],
                            "additional_evaluations": item["additional_evaluations"],
                            "search_wall_s": result["search_wall_s"],
                            "reference": item["reference"], "score": item["score"],
                            "metrics": item["metrics"],
                            "initialization": item["initialization"]}
                saved = placement.save(model, TEMPLATE, item["state"], destination,
                                       metadata)
                manifest["results"][key] = {"status": "feasible",
                    "source": (destination / "placement.json").relative_to(HERE).as_posix(),
                    "state_signature": placement.signature(item["state"]),
                    "boundaries": [s["end"] for s in item["state"]["segments"][:-1]],
                    "widths": saved["widths"], "layer_copies": saved["layer_copies"],
                    "active_gpus": saved["active_gpus"],
                    "compatible_paths": saved["compatible_paths"],
                    "candidate_evaluations": item["candidate_evaluations"],
                    "search_wall_s": result["search_wall_s"],
                    "bottleneck_resource": item["metrics"]["bottleneck_resource"],
                    "score": item["score"],
                    "solution_sha256": saved["solution_sha256"],
                    "sim_cluster_sha256": saved["sim_cluster_sha256"]}
                print(key, saved["widths"], item["score"], flush=True)
            write_json(HERE / "plan_index.json", manifest)
    uniform = manifest["results"]
    for mode in ("single", "multi"):
        left = uniform[f"uniform/mid_x1/{mode}"]
        right = uniform[f"layer_aware/mid_x1/{mode}"]
        if left["state_signature"] != right["state_signature"] or \
                abs(left["score"] - right["score"]) > 1e-10:
            raise AssertionError(f"Unit-multiplier search parity failed: {mode}")
    print(HERE / "plan_index.json")


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    run()
