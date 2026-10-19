"""Check all one- and two-branch subsets of each frozen three-branch parent."""

from __future__ import annotations

import contextlib
import itertools
import json
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from pathlib import Path

from benchmarks.fixed_window import run as fixed_window_run
from experiments.m2_multistage_candidate.prepare import _audit_export, files
from experiments.v3_m2_branch_parallelism.run import (
    HERE, ROOT, CanonicalGraphDagScheduler, canonical_edges, read,
    select, write,
)
from rcaps.v3.placement import digest, save, validate
from rcaps.v3.resource_graph import LayerCompatibilityDag
from rcaps.v3.topology import TopologyModel


COMBINATIONS = ((1,), (2,), (0, 2), (1, 2))


def one(case: str, branches: tuple[int, ...]) -> str:
    physical, template, scenario = files(case)
    model = TopologyModel(physical)
    parent = read(HERE / "parents" / f"{case}.json")["state"]
    state = select(parent, branches)
    checked = validate(model, state)
    label = "k" + str(len(branches)) + "_b" + "".join(map(str, branches))
    deployment = HERE / "layouts" / case / label
    exported = save(model, template, state, deployment,
                    {"case": case, "variant": label,
                     "experiment": "M2 branch subset robustness"})
    _audit_export(deployment, checked)
    allowed_graph = canonical_edges(state, checked["dag"])
    reduced = LayerCompatibilityDag(checked["dag"].spans,
                                    tuple(allowed_graph), checked["dag"].layers)
    if reduced.path_count() != len(branches):
        raise ValueError("Canonical path count mismatch")
    allowed = frozenset((a if isinstance(a, str) else a + 2,
                         b if isinstance(b, str) else b + 2)
                        for a, b in allowed_graph)
    load = 700. if case == "C1_single" else 320.
    output = HERE / "runs" / "subsets" / case / label / f"load{load:g}_seed0.json"
    if output.exists():
        old = read(output)
        if old["solution_sha256"] == exported["solution_sha256"]:
            return str(output)
        raise ValueError("Existing subset result changed")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(".log").open("w", encoding="utf-8") as log, \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            row = fixed_window_run(
                scenario, "queue_dag", load, 1800, 0, 0,
                deployment / "solution.ini", deployment / "simulator_cluster.ini",
                profile_resources=True, compact=True, record_query_samples=True,
                physical_cluster=physical, machine_counts=model.machine_counts,
                scheduler_factory=partial(CanonicalGraphDagScheduler,
                                          allowed_edges=allowed))
            row.update({"case": case, "variant": label,
                        "branches": list(branches),
                        "solution_sha256": exported["solution_sha256"],
                        "sim_cluster_sha256": exported["sim_cluster_sha256"],
                        "subset_runner_sha256": digest(HERE / "subsets.py")})
            write(output, row)
        except Exception:
            traceback.print_exc(file=log)
            raise
    return str(output)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("C1_single", "C1_multi"), action="append")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    jobs = tuple(itertools.product(args.case or ("C1_single", "C1_multi"),
                                   COMBINATIONS))
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(one, *job): job for job in jobs}
        for future in as_completed(futures):
            job = futures[future]
            try:
                print("PASS", job, future.result(), flush=True)
            except Exception as exc:
                print("FAIL", job, repr(exc), flush=True)


if __name__ == "__main__":
    main()
