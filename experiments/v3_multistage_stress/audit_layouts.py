"""Verify every exported stress layout against its M1 deployment DAG."""

from __future__ import annotations

import json

from experiments.m2_multistage_candidate.prepare import _audit_export
from rcaps.v3.placement import digest, validate
from rcaps.v3.topology import TopologyModel

from .plan import write_json
from .pool import HERE, PHYSICAL, prepare


def main() -> None:
    prepare()
    model = TopologyModel(PHYSICAL)
    entries = {}
    for path in sorted((HERE / "layouts").rglob("placement.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        checked = validate(model, record["state"])
        export = _audit_export(path.parent, checked)
        if record["compatible_paths"] != checked["dag"].path_count():
            raise ValueError(f"Stored path count differs: {path}")
        entries[path.relative_to(HERE).as_posix()] = {
            "placement_sha256": digest(path),
            "solution_sha256": digest(path.parent / "solution.ini"),
            "sim_cluster_sha256": digest(path.parent / "simulator_cluster.ini"),
            "layer_copies": checked["layer_copies"],
            "active_gpus": checked["active_gpus"],
            "dag_edges": len(checked["dag"].edges),
            "dag_paths": checked["dag"].path_count(),
            "export": export}
    write_json(HERE / "layout_audit.json", {
        "physical_sha256": digest(PHYSICAL), "layouts": entries})
    print(f"verified {len(entries)} stress deployment files")


if __name__ == "__main__":
    main()
