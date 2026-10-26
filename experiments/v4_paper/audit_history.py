"""Audit legacy load curves using exact Git sources and default-path AST parity."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(path):
    return subprocess.check_output(["git", "show", f"6001997:{path}"], cwd=ROOT)


def normalize_default_run(data, modern):
    tree = ast.parse(data.decode("utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run")
    if modern:
        assert [a.arg for a in fn.args.args[-2:]] == ["phase_link_probe", "model_name"]
        assert ast.dump(fn.args.defaults[-2]) == "Constant(value=None)"
        assert ast.unparse(fn.args.defaults[-1]) == "ModelName.LLaMa70B"
        fn.args.args = fn.args.args[:-2]
        fn.args.defaults = fn.args.defaults[:-2]
        fn.body = [n for n in fn.body if not (isinstance(n, ast.If)
                   and ast.unparse(n.test) == "phase_link_probe is not None")]
        class DefaultModel(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id == "model_name" and isinstance(node.ctx, ast.Load):
                    return ast.parse("ModelName.LLaMa70B", mode="eval").body
                return node
        fn = DefaultModel().visit(fn)
    return ast.dump(fn, include_attributes=False)


def main():
    current = (ROOT / "benchmarks/fixed_window.py").read_bytes()
    original = git_blob("benchmarks/fixed_window.py")
    assert sha(original) == "4e87beec2cfa1b8c1dca0731c8966470fa1bc733c4de73b852035e596d2c237f"
    default_parity = normalize_default_run(original, False) == normalize_default_run(current, True)
    if not default_parity:
        raise RuntimeError("Default run body differs beyond disabled probe and default model parameter")
    source_checks = {}
    for base in ("simulator", "baselines"):
        for p in sorted((ROOT / base).rglob("*")):
            if p.is_file() and p.suffix in {".py", ".csv", ".pkl", ".ini"}:
                name = p.relative_to(ROOT).as_posix()
                old = git_blob(name)
                equal = old.replace(b"\r\n", b"\n") == p.read_bytes().replace(b"\r\n", b"\n")
                source_checks[name] = {"current_sha256": sha(p.read_bytes()),
                                       "historical_sha256": sha(old), "newline_normalized_equal": equal}
                if not equal:
                    raise RuntimeError(f"Historical simulator/data/baseline differs: {name}")
    for p in list((ROOT / "rcaps/v3").glob("*.py")) + [ROOT / f"benchmarks/{n}.py" for n in ("layout", "resource_profile", "accumulator")]:
        name = p.relative_to(ROOT).as_posix()
        if name == "rcaps/v3/topology.py":
            continue  # only read-only machine-count lookup is used for frozen deployments
        old = git_blob(name)
        equal = old.replace(b"\r\n", b"\n") == p.read_bytes().replace(b"\r\n", b"\n")
        source_checks[name] = {"current_sha256": sha(p.read_bytes()), "historical_sha256": sha(old),
                               "newline_normalized_equal": equal}
        if not equal:
            raise RuntimeError(f"Historical routing/measurement differs: {name}")
    from baselines import helix
    from rcaps import v3_method
    from benchmarks.layout import scenario
    index_path = ROOT / "experiments/v3_load_boundary/index.json"
    index = read(index_path)
    audit_path = ROOT / "experiments/v3_load_boundary/audit.json"
    assert sha(audit_path.read_bytes()) == index["audit_sha256"]
    checked = {}
    for key, entry in index["jobs"].items():
        if entry["status"] == "failed":
            path = ROOT / entry["failure_source"]
            assert sha(path.read_bytes()) == entry["failure_sha256"]
            checked[key] = dict(entry, reuse_decision="retain_failure_not_zero")
            continue
        assert entry["status"] in {"passed", "reused"}
        path = ROOT / entry["source"]
        assert sha(path.read_bytes()) == entry["sha256"]
        row = read(path)
        sc, load, sd, method = key.split("/")
        sol, cluster = (v3_method if method == "rcaps_v3" else helix).layout(sc, ROOT)
        expected = {"scenario": sc, "seed": int(sd[4:]), "offered_tokens_per_s": float(load),
                    "duration_s": 1800, "warmup_s": 0,
                    "evaluation_protocol": "fixed_window_no_tail_drain",
                    "solution_sha256": sha(sol.read_bytes()), "sim_cluster_sha256": sha(cluster.read_bytes()),
                    "physical_sha256": sha(scenario(sc)[0].read_bytes()), "benchmark_sha256": sha(original)}
        assert all(row[k] == v for k, v in expected.items()), key
        assert len(row["query_samples"]) == row["arrivals"], key
        checked[key] = dict(entry, reuse_decision="accepted_default_execution_equivalence",
                            resource_metrics_available="gpu_busy_fraction" in row)
    result = {"schema": 1, "audit_script_sha256": sha(Path(__file__).read_bytes()),
              "historical_commit": subprocess.check_output(["git", "rev-parse", "6001997"], cwd=ROOT, text=True).strip(),
              "fixed_window_default_run_ast_equal": default_parity,
              "current_fixed_window_sha256": sha(current), "historical_fixed_window_sha256": sha(original),
              "scope": "Disabled optional probe, default LLaMA70B, function invocation (not changed CLI). Existing default simulation/model/data/routing code verified against Git. Topology planning is not rerun for these frozen placements.",
              "source_checks": source_checks, "jobs": checked,
              "successful_windows": sum(e["reuse_decision"] == "accepted_default_execution_equivalence" for e in checked.values()),
              "retained_failures": sum(e["reuse_decision"] == "retain_failure_not_zero" for e in checked.values())}
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / "history_audit.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("HISTORY_AUDIT", result["successful_windows"], "successes", result["retained_failures"], "retained failures")


if __name__ == "__main__": main()
