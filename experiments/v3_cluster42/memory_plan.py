"""Plan a capacity-aware 42-GPU candidate without changing the frozen V3 layout."""

from __future__ import annotations

import json

from rcaps.v3.placement import save, validate
from rcaps.v3.topology import TopologyModel
from experiments.v3_cluster42.run import BASE, HERE, PHYSICAL

DESTINATION = HERE / "layout_memory"
# Azure Conversation allows at most 2047 prompt and 1000 output tokens. A
# conservative 3000-token session therefore has >0 room on every selected GPU.
MIN_SESSION_TOKENS = 3000


def admissible_layers(model: TopologyModel, node: int) -> int:
    return max((layers for layers in range(1, model.capacity[node] + 1)
                if model.manager.get_kv_cache_capacity(model.types[node], layers) // layers
                >= MIN_SESSION_TOKENS), default=0)


def plan() -> dict:
    model = TopologyModel(PHYSICAL)
    capacities = {node: admissible_layers(model, node) for node in model.types}
    stem = min((node for node, capacity in capacities.items() if capacity),
               key=lambda node: (-model.manager.get_kv_cache_capacity(model.types[node], 1), node))
    candidates = sorted((node for node, capacity in capacities.items() if capacity and node != stem),
                        key=lambda node: (-capacities[node], node))
    # Four complete model replicas are possible only when the sum of usable
    # layer slots reaches 320. In this cluster the physical total is 350.
    if sum(capacities[node] for node in candidates) < 4 * (model.layers - 1):
        raise ValueError("Insufficient KV-safe layer capacity for four replicas")
    replicas = [[] for _ in range(4)]
    totals = [0] * 4
    for node in candidates:
        index = min(range(4), key=lambda i: (totals[i], i))
        replicas[index].append(node)
        totals[index] += capacities[node]
    if min(totals) < model.layers - 1:
        raise ValueError(f"Cannot cover every replica: {totals}")
    lengths = {}
    for replica in replicas:
        remaining = model.layers - 1
        for position, node in enumerate(replica):
            rest = len(replica) - position - 1
            assigned = min(capacities[node], remaining - rest)
            if assigned < 1:
                raise ValueError("GPU grouping has excess members")
            lengths[node] = assigned
            remaining -= assigned
        if remaining:
            raise ValueError(f"Replica leaves {remaining} layers uncovered")
    # The V3 validator requires a one-replica shared stem. Give it layer 0
    # on a high-memory GPU, then use four independent 79-layer branches.
    state = {"segments": [
        {"start": 0, "end": 1, "replicas": [[stem]]},
        {"start": 1, "end": model.layers, "replicas": replicas},
    ], "lengths": {**lengths, stem: 1}}
    validate(model, state)
    template = BASE / "layout_llama70b/ilp/simulator_cluster.ini"
    metadata = {"candidate": "full-pool KV-capacity layout",
                "capacity_threshold_session_tokens": MIN_SESSION_TOKENS,
                "physical": PHYSICAL.relative_to(HERE.parents[1]).as_posix()}
    return save(model, template, state, DESTINATION, metadata)


def memory_shortlist():
    """Shortlist diverse sub-42-GPU placements by capacity and path cost."""
    from rcaps.v3.placement import measure
    from rcaps.v3.search import assignments, build

    model = TopologyModel(PHYSICAL)
    ranked = []
    for boundary in (1, 4, 8, 12, 16, 20, 24, 32, 40, 48):
        for width in (2, 3, 4):
            need = [boundary] + [model.layers - boundary] * width
            for bins in assignments(model, need, a100_prefix=False, keep=8):
                state = build(model, (boundary,), (1, width), bins)
                if state is None or len(state["lengths"]) >= 42:
                    continue
                kv = {node: model.manager.get_kv_cache_capacity(
                    model.types[node], layers) // layers
                    for node, layers in state["lengths"].items()}
                if min(kv.values()) < 3047:
                    continue
                paths = [prefix + branch
                         for prefix in state["segments"][0]["replicas"]
                         for branch in state["segments"][1]["replicas"]]
                slots = min(min(kv[node] // 3047 for node in path)
                            for path in paths)
                hops = max(len(path) for path in paths)
                metrics = measure(model, state)
                score = (metrics["bottleneck_s"] * 4 + metrics["tpot_s"] +
                         0.03 * hops + 0.15 / slots)
                ranked.append((score, boundary, width, state,
                               {**metrics, "active_gpus": len(kv),
                                "max_hops": hops, "min_session_slots": slots,
                                "kv_tokens_per_layer": kv}))
    ranked.sort(key=lambda row: (row[0], row[4]["active_gpus"], row[1]))
    chosen = {}
    for row in ranked:
        chosen.setdefault(row[2], row)
    destination = HERE / "kv_candidate"
    records = []
    for width in (2, 3, 4):
        if width not in chosen:
            continue
        score, boundary, _, state, metrics = chosen[width]
        name = f"w{width}_b{boundary}"
        save(model, BASE / "layout_llama70b/ilp/simulator_cluster.ini",
             state, destination / name,
             {"candidate": name, "selection_score": score,
              "capacity_profile": metrics})
        records.append({"name": name, "score": score, **metrics})
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "shortlist.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8")
    return records


if __name__ == "__main__":
    print(json.dumps([{key: row[key] for key in
                      ("name", "active_gpus", "max_hops",
                       "min_session_slots", "score")}
                      for row in memory_shortlist()], indent=2))
