"""Pre-result E1 layout construction with explicit hard-constraint outcomes."""
import argparse
import hashlib
import importlib.metadata
import json
import math
import random
import sys
import time
from pathlib import Path

from rcaps.v3.topology import TopologyModel, profile_at
from rcaps.v3.placement import normalize as original_normalize
from experiments.reviewer_v2.E1_placement.placement_multi import measure, objective, save, validate, signature
from experiments.reviewer_v2.E1_placement.search_multi import (
    assignments, _shape_requirements, build, build_ordered, search)

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
CASES = ("C1_single", "C1_multi")
VARIANTS = ("R-noshare", "R-uniform", "R-pipelines", "R-greedy", "R-random")
RANDOM_SEED = 20261029
RANDOM_TARGET = 1000
RANDOM_PROPOSAL_CAP = 25000

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def put(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def input_files():
    files = [Path(__file__), HERE / "PLAN_CN.md", HERE / "placement_multi.py", HERE / "search_multi.py",
        ROOT / "rcaps/v3/planning_inputs.json"]
    for folder in ("simulator", "rcaps", "benchmarks", "baselines"):
        files.extend(p for p in (ROOT / folder).rglob("*") if p.is_file() and p.suffix in (".py", ".csv", ".pkl")
                     and "__pycache__" not in p.parts)
    for item in (read(ROOT / "rcaps/v3/planning_inputs.json")[name] for name in CASES):
        files.extend((ROOT / item["physical"], ROOT / item["template"]))
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(files))}

def register():
    path = HERE / "planning_manifest.json"
    if path.exists():
        manifest = read(path)
        check(manifest)
        return manifest
    manifest = dict(registered_at="2026-10-29", variants=VARIANTS, cases=CASES,
        search=dict(beam=64, common_budget=500, extension_budget=500,
                    random_seed=RANDOM_SEED, random_target=RANDOM_TARGET,
                    random_proposal_cap=RANDOM_PROPOSAL_CAP),
        environment=dict(executable=sys.executable, python=sys.version,
            packages={name: importlib.metadata.version(name) for name in ("numpy", "scipy", "networkx", "gurobipy")}),
        sources_sha256=input_files())
    put(path, manifest)
    return manifest

def check(manifest):
    for name, digest in manifest["sources_sha256"].items():
        if sha(ROOT / name) != digest:
            raise RuntimeError("Frozen planning input changed: " + name)

def reference_state(item):
    return original_normalize(item["reference_state"])

def choose_greedy(model, reference):
    """Fastest feasible canonical chain, then bottleneck-guided replicas."""
    reference_metrics = measure(model, reference)
    start = time.perf_counter()
    scored = []
    evaluated = 0
    for boundary in range(4, model.layers, 4):
        bounds = (boundary,)
        for bins in assignments(model, _shape_requirements(model.layers, bounds, (1, 1)),
                                a100_prefix=False, keep=2):
            state = build_ordered(model, bounds, (1, 1), bins, first_fastest=True)
            if state is None:
                continue
            item = measure(model, state)
            evaluated += 1
            scored.append((objective(item, reference_metrics), signature(state), state, item))
    if not scored:
        raise RuntimeError("No feasible initial greedy chain")
    best = min(scored)
    # A valid widened state must not share GPUs between replicas; try the slowest
    # stage first, then retain only score-improving legal candidates.
    seed = best[2]
    stage_cost = []
    for idx, segment in enumerate(seed["segments"]):
        cost = sum(seed["lengths"][n] * (0.4 * profile_at(model.profiles[model.types[n]].prompt_bs2time,
            model.prompt_tokens) + 0.35 * profile_at(model.profiles[model.types[n]].decode_bs2time,
            model.decode_batch)) for n in segment["replicas"][0])
        stage_cost.append((cost, idx))
    for _, target in sorted(stage_cost, reverse=True):
        stage_best = best
        for boundary in range(max(4, seed["segments"][0]["end"] - 4),
                              min(model.layers, seed["segments"][0]["end"] + 8), 4):
            widths = [1, 1]
            widths[target] = 2
            bounds = (boundary,)
            for bins in assignments(model, _shape_requirements(model.layers, bounds, tuple(widths)),
                                    a100_prefix=False, keep=2):
                state = build_ordered(model, bounds, tuple(widths), bins, first_fastest=True)
                if state is None:
                    continue
                item = measure(model, state)
                evaluated += 1
                candidate = (objective(item, reference_metrics), signature(state), state, item)
                if candidate[:2] < stage_best[:2]:
                    stage_best = candidate
        if stage_best is not best:
            best = stage_best
            break
    return best[2], dict(candidate_evaluations=evaluated, score=best[0],
        search_wall_s=time.perf_counter()-start, static_metrics=best[3],
        algorithm="fastest feasible chain plus bottleneck-stage replica")

def choose_random(model, reference, seed):
    reference_metrics = measure(model, reference)
    rng = random.Random(seed)
    start = time.perf_counter()
    cache = {}
    proposals = 0
    best = None
    while len(cache) < RANDOM_TARGET and proposals < RANDOM_PROPOSAL_CAP:
        proposals += 1
        if rng.random() < .5:
            bounds = (rng.randrange(4, model.layers, 4),)
            widths = (1, rng.choice((1, 2, 3, 4)))
        else:
            bounds = tuple(sorted(rng.sample(range(4, model.layers, 4), 2)))
            widths = (1, rng.choice((1, 2, 3, 4)), rng.choice((1, 2, 3, 4)))
        bins = assignments(model, _shape_requirements(model.layers, bounds, widths), a100_prefix=False, keep=2)
        if not bins:
            continue
        state = build(model, bounds, widths, bins[rng.randrange(len(bins))])
        if state is None or signature(state) in cache:
            continue
        metrics = measure(model, state)
        score = objective(metrics, reference_metrics)
        cache[signature(state)] = score
        candidate = (score, signature(state), state, metrics)
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    if best is None:
        raise RuntimeError("No valid random placement")
    return best[2], dict(candidate_evaluations=len(cache), proposal_count=proposals,
        target_evaluations=RANDOM_TARGET, proposal_cap=RANDOM_PROPOSAL_CAP,
        score=best[0], search_wall_s=time.perf_counter()-start,
        static_metrics=best[3], algorithm="seeded valid-state random static search")

def plan(case, variant):
    manifest = register()
    check(manifest)
    item = read(ROOT / "rcaps/v3/planning_inputs.json")[case]
    model = TopologyModel(ROOT / item["physical"])
    template = ROOT / item["template"]
    reference = reference_state(item)
    destination = HERE / "layouts" / case / variant
    if (destination / "placement.json").exists():
        raise RuntimeError("Placement exists; do not overwrite")
    if variant == "R-pipelines":
        capacity = sum(model.capacity.values())
        needed = 2 * model.layers
        if capacity < needed:
            outcome = dict(case=case, variant=variant, status="infeasible",
                reason="two disjoint full-model replicas need at least 2*layers capacity",
                available_layer_capacity=capacity, required_layer_capacity=needed,
                model_layers=model.layers, planning_manifest_sha256=sha(HERE / "planning_manifest.json"))
            put(destination / "INFEASIBLE.json", outcome)
            return outcome
    if variant == "R-uniform":
        # Fixed three equal-length segments, remainder assigned from the last
        # segment backwards. Maximize the common width under hard constraints.
        one = model.layers // 3
        lengths = [one, one, model.layers - 2 * one]
        bounds = (lengths[0], lengths[0] + lengths[1])
        valid = []
        evaluated = 0
        start = time.perf_counter()
        reference_metrics = measure(model, reference)
        for width in range(4, 0, -1):
            shape = (width, width, width)
            for bins in assignments(model, _shape_requirements(model.layers, bounds, shape),
                                    a100_prefix=False, keep=2):
                state = build(model, bounds, shape, bins)
                if state is None:
                    continue
                metrics = measure(model, state)
                evaluated += 1
                valid.append((objective(metrics, reference_metrics), signature(state), state, metrics))
            if valid:
                break
        if not valid:
            outcome = dict(case=case, variant=variant, status="infeasible",
                reason="No feasible equal-third, equal-width placement under physical and KV constraints",
                planning_manifest_sha256=sha(HERE / "planning_manifest.json"))
            put(destination / "INFEASIBLE.json", outcome)
            return outcome
        chosen = min(valid)
        state = chosen[2]
        metadata = dict(candidate_evaluations=evaluated, score=chosen[0],
                        search_wall_s=time.perf_counter()-start, static_metrics=chosen[3],
                        algorithm="max feasible equal width on equal third segments")
    elif variant == "R-noshare":
        result = search(model, reference, a100_prefix=False, no_share_only=True)
        candidates = [result[key] for key in ("single", "multi") if result[key]["status"] == "feasible"
                      and len(result[key]["state"]["segments"][0]["replicas"]) > 1]
        if not candidates:
            raise RuntimeError("No feasible no-share candidate")
        selected = min(candidates, key=lambda r: (r["score"], signature(r["state"])))
        state = selected["state"]
        metadata = {key: value for key, value in selected.items() if key not in ("state", "status")}
        metadata.update(search_wall_s=result["search_wall_s"], algorithm="E1 no-share bounded M2")
    elif variant == "R-greedy":
        state, metadata = choose_greedy(model, reference)
    elif variant == "R-random":
        state, metadata = choose_random(model, reference, RANDOM_SEED + (0 if case == "C1_single" else 1))
    else:
        raise ValueError(variant)
    validated = validate(model, state)
    if variant == "R-noshare" and len(state["segments"][0]["replicas"]) == 1:
        raise RuntimeError("No-share method accidentally returned a shared first stage")
    record = save(model, template, state, destination, metadata)
    record.update(case=case, variant=variant, planning_manifest_sha256=sha(HERE / "planning_manifest.json"),
        physical_sha256=sha(ROOT / item["physical"]), template_sha256=sha(template),
        available_layer_capacity=sum(model.capacity.values()), full_paths=validated["dag"].path_count())
    put(destination / "PLAN_AUDIT.json", record)
    check(manifest)
    return dict(case=case, variant=variant, status="feasible", widths=record["widths"],
        candidate_evaluations=metadata.get("candidate_evaluations"),
        solution_sha256=record["solution_sha256"], sim_cluster_sha256=record["sim_cluster_sha256"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--case", choices=CASES)
    parser.add_argument("--variant", choices=VARIANTS)
    args = parser.parse_args()
    if args.register:
        print(sha(HERE / "planning_manifest.json") if (HERE / "planning_manifest.json").exists() else
              sha(HERE / "PLAN_CN.md"))
        register()
    else:
        if not args.case or not args.variant:
            parser.error("--case and --variant required")
        print(json.dumps(plan(args.case, args.variant), ensure_ascii=False))
