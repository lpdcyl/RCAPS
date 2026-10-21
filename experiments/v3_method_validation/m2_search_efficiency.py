"""Offline sanity checks for V3's bounded M2 search components.

The comparisons share legal initial states, neighbors, the frozen objective,
and each pool's reference. They do not claim global search optimality.
"""

from __future__ import annotations

import argparse
import random
import time
from pathlib import Path

from experiments.m2_multistage_candidate.prepare import (files, initial_state,
                                                           reference_state)
from rcaps.v3.placement import measure, objective, signature
from rcaps.v3.search import cheap_cost, initial_states, neighbors
from rcaps.v3.topology import TopologyModel

from .crossover import HERE, _read, _write
from .m2_objective import CASES


RANDOM_SEEDS = (10, 11, 12, 13, 14)


def _initial_pool(model, seed):
    single, _ = initial_states(model, a100_prefix=False, multistage=False)
    multi, _ = initial_states(model, a100_prefix=False, multistage=True)
    pool = {signature(state): state for state in (seed, *single, *multi)}
    return [pool[key] for key in sorted(pool)]


def _run(model, reference, pool, budget: int, method: str, rng_seed: int | None):
    started = time.perf_counter()
    rng = random.Random(rng_seed)
    evaluated = {}
    best = None
    curve = []

    def evaluate(state):
        nonlocal best
        key = signature(state)
        if key in evaluated or len(evaluated) >= budget:
            return evaluated.get(key)
        value = objective(measure(model, state), reference)
        evaluated[key] = value
        if best is None or value < best[0]:
            best = (value, state)
        curve.append({"unique_evaluations": len(evaluated),
                      "best_frozen_score": best[0],
                      "elapsed_s": time.perf_counter() - started})
        return value

    ranked = sorted(pool, key=lambda state: (cheap_cost(model, state), signature(state)))
    if method == "initializer_only":
        for state in ranked:
            evaluate(state)
            if len(evaluated) >= budget:
                break
    elif method == "one_start_greedy":
        for state in ranked[:min(160, budget)]:
            evaluate(state)
        if best is not None:
            current = best
            for _ in range(16):
                candidate = None
                for _, state in neighbors(model, current[1]):
                    value = evaluate(state)
                    if value is not None and value < current[0] - 1e-9 and (
                            candidate is None or value < candidate[0]):
                        candidate = (value, state)
                    if len(evaluated) >= budget:
                        break
                if candidate is None:
                    break
                current = candidate
    elif method == "random_neighborhood":
        attempts = 0
        current = rng.choice(pool)
        while len(evaluated) < budget and attempts < budget * 20:
            if attempts % 25 == 0:
                current = rng.choice(pool)
            options = list(neighbors(model, current))
            if options:
                current = rng.choice(options)[1]
            evaluate(current)
            attempts += 1
    else:
        raise ValueError(method)
    return {"method": method, "random_seed": rng_seed,
            "budget": budget, "unique_evaluations": len(evaluated),
            "best_frozen_score": best[0] if best else None,
            "best_signature": signature(best[1]) if best else None,
            "planning_wall_s": time.perf_counter() - started,
            "curve": curve}


def run() -> dict:
    offline = _read(HERE / "m2_offline_index.json")
    output = HERE / "m2_search_efficiency.json"
    result = (_read(output) if output.is_file() else
              {"random_seeds": list(RANDOM_SEEDS), "cases": {}})
    for case in ("C1_single", "C1_multi"):
        if case in result["cases"]:
            if "initial_pool_build_s" not in result["cases"][case]:
                physical, _, _ = files(case)
                model = TopologyModel(physical)
                seed = initial_state(case, model)
                started = time.perf_counter()
                _initial_pool(model, seed)
                result["cases"][case]["initial_pool_build_s"] = time.perf_counter() - started
                _write(output, result)
            continue
        physical, _, _ = files(case)
        model = TopologyModel(physical)
        seed = initial_state(case, model)
        reference = measure(model, reference_state(case, model, seed))
        if reference != offline["cases"][case]["full"]["reference"]:
            raise ValueError(f"M2 search reference drifted: {case}")
        started_pool = time.perf_counter()
        pool = _initial_pool(model, seed)
        pool_build_s = time.perf_counter() - started_pool
        frozen = offline["cases"][case]["full"]
        budget = frozen["candidate_evaluations"]
        entries = [{"method": "full_v3", "budget": budget,
                    "unique_evaluations": budget,
                    "best_frozen_score": frozen["score_under_frozen_full_objective"],
                    "planning_wall_s": frozen["search_wall_s"], "curve": None}]
        for method in ("initializer_only", "one_start_greedy"):
            entries.append(_run(model, reference, pool, budget, method, None))
        for rng_seed in RANDOM_SEEDS:
            entries.append(_run(model, reference, pool, budget,
                                "random_neighborhood", rng_seed))
        result["cases"][case] = {"initial_legal_pool": len(pool),
                                  "initial_pool_build_s": pool_build_s,
                                  "frozen_evaluation_budget": budget,
                                  "methods": entries}
        _write(HERE / "m2_search_efficiency.json", result)
        print(f"{case}: full={entries[0]['best_frozen_score']:.4f}, "
              f"initializer={entries[1]['best_frozen_score']:.4f}, "
              f"greedy={entries[2]['best_frozen_score']:.4f}", flush=True)
    lines = ["# V3 M2 离线搜索效率诊断", "",
             "所有方法使用相同的合法布局表示、冻结静态目标及各池参考。",
             "完整 V3 行记录冻结搜索的实际评价数与总规划时间；简单方法最多使用该池相同评价数上限。",
             "简单方法的规划秒数包含共同合法初始候选池的构建时间；时间受并行任务影响，仅作开销描述。",
             "未用完预算按实际评价数报告。该实验不宣称搜索算法具有全局最优性。", "",
             "| 资源池 | 方法 | 随机种子 | 实际评价数 | 最低冻结目标分数 | 规划秒 |",
             "| --- | --- | ---: | ---: | ---: | ---: |"]
    for case in ("C1_single", "C1_multi"):
        for entry in result["cases"][case]["methods"]:
            seed = entry["random_seed"] if entry.get("random_seed") is not None else "—"
            planning_seconds = entry["planning_wall_s"] + (
                result["cases"][case]["initial_pool_build_s"]
                if entry["method"] != "full_v3" else 0.0)
            lines.append(f"| {case} | {entry['method']} | {seed} | "
                         f"{entry['unique_evaluations']} | "
                         f"{entry['best_frozen_score']:.4f} | "
                         f"{planning_seconds:.2f} |")
    lines.extend(["", "随机运行若找到更低静态分数，应保留为负结果；"
                  "静态分数不等于在线吞吐或 P95。", ""])
    (HERE / "m2_search_efficiency_report.md").write_text("\n".join(lines),
                                                            encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
