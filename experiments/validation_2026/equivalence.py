"""Check when the single-cluster static search reproduces topology-only input."""

from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def normalized_ini(path: Path) -> dict[str, dict[str, str]]:
    ini = ConfigParser()
    if not ini.read(path):
        raise FileNotFoundError(path)
    return {section: dict(ini[section]) for section in ini.sections()}


def static_single_equals_coarse() -> bool:
    variants = ROOT / "rcaps/variant_layouts"
    static = variants / "single_static_no_graph"
    coarse = variants / "single_coarse"
    return all(normalized_ini(static / file) == normalized_ini(coarse / file)
               for file in ("solution.ini", "simulator_cluster.ini"))
