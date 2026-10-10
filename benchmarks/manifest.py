"""Write a portable manifest of code, simulator inputs, and software versions."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy
import scipy

from .run import ROOT


CONFIGS = (
    "requirements.txt",
    "examples/simulation/config/single24.ini",
    "examples/simulation/config/machine_profile.ini",
    "artifact_evaluation/distributed_clusters/config/3cluster24.ini",
    "artifact_evaluation/distributed_clusters/config/machine_profiles.ini",
    "artifact_evaluation/single_cluster/layout_llama70b/ilp/ilp_sol.ini",
    "artifact_evaluation/single_cluster/layout_llama70b/ilp/simulator_cluster.ini",
    "artifact_evaluation/distributed_clusters/layout_llama70b/ilp/ilp_sol.ini",
    "artifact_evaluation/distributed_clusters/layout_llama70b/ilp/simulator_cluster.ini",
    "rcaps/layouts/single/solution.ini",
    "rcaps/layouts/single/simulator_cluster.ini",
    "rcaps/layouts/multi/solution.ini",
    "rcaps/layouts/multi/simulator_cluster.ini",
) + tuple(f"rcaps/variant_layouts/{variant}/{name}"
          for variant in ("single_capacity", "multi_capacity", "single_coarse",
                          "multi_coarse", "multi_ensemble")
          for name in ("placement.json", "solution.ini", "simulator_cluster.ini"))


def fingerprint(path: Path) -> dict:
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size}


def manifest() -> dict:
    try:
        import gurobipy
        gurobi_version = ".".join(map(str, gurobipy.gurobi.version()))
    except ImportError:
        gurobi_version = None
    trace_files = sorted((ROOT / "simulator" / "trace_generator").rglob("*.pkl"))
    files = [ROOT / relative for relative in CONFIGS] + trace_files
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                     text=True).strip()
    return {
        "source_commit": commit,
        "software": {
            "python": sys.version.split()[0],
            "numpy": numpy.__version__,
            "scipy": scipy.__version__,
            "gurobi": gurobi_version,
            "operating_system": platform.system(),
            "architecture": platform.machine(),
        },
        "protocol": {
            "scenarios": ["single", "multi"],
            "offered_tokens_per_s": {"single": 700, "multi": 320},
            "duration_s": 1800,
            "warmup_s": 0,
            "evaluation": "fixed_window_no_tail_drain",
            "seeds": [0, 1, 2],
            "independent_holdout": False,
        },
        "input_files": {path.relative_to(ROOT).as_posix(): fingerprint(path)
                        for path in files},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "paper" / "RUN_MANIFEST.json")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest(), indent=2) + "\n",
                           encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
