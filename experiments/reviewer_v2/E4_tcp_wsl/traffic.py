"""Freeze a proxy link-traffic trace and compute ideal link-model predictions."""
import argparse
import hashlib
import json
import random
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT / "experiments/v6_completion/bandwidth_threshold/formal/runs/B12p5_T50/sparse_chunk/seed0/result.json"
TRAFFIC = HERE / "traffic.json"
MANIFEST = HERE / "manifest.json"
CLIP_START_S = 600.0
CLIP_S = 30.0
LARGE_BYTES = 12_300_000
SMALL_BYTES = 16_384
REPEATS = 10
PLAN_SEED = 20261029


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_traffic():
    source = read(SOURCE)
    candidates = [(name, value) for name, value in source["phase_link_profile"]["links"].items()
                  if name.startswith("Compute-") and "->Compute-" in name
                  and 10_000_000 <= value["capacity_Bps"] <= 20_000_000
                  and value["prompt_messages"] > 0 and value["decode_messages"] > 0]
    if not candidates:
        raise RuntimeError("No qualifying slow internal link")
    name, link = sorted(candidates, key=lambda x: (-x[1]["decode_messages"], x[0]))[0]
    arrivals = sorted(float(row["arrival_s"]) for row in source["query_samples"].values())
    n = int(link["prompt_messages"])
    if n > len(arrivals):
        raise RuntimeError("Selected link has more Prompt messages than arrivals")
    indices = set(random.Random(PLAN_SEED).sample(range(len(arrivals)), n))
    large = [round(t - CLIP_START_S, 9) for i, t in enumerate(arrivals)
             if i in indices and CLIP_START_S <= t < CLIP_START_S + CLIP_S]
    if not large:
        raise RuntimeError("Fixed clip has no large messages")
    rate = link["decode_messages"] / 1800.0
    repetitions = []
    for repeat in range(REPEATS):
        rng = random.Random(PLAN_SEED + repeat)
        small = []
        t = 0.0
        while True:
            t += rng.expovariate(rate)
            if t >= CLIP_S:
                break
            small.append(round(t, 9))
        events = ([{"kind": "L", "id": i, "at_s": t, "bytes": LARGE_BYTES}
                   for i, t in enumerate(large)] +
                  [{"kind": "S", "id": 100000 + i, "at_s": t, "bytes": SMALL_BYTES}
                   for i, t in enumerate(small)])
        events.sort(key=lambda e: (e["at_s"], e["id"]))
        repetitions.append({"repeat": repeat, "events": events,
                            "large_count": len(large), "small_count": len(small)})
    return {"source": SOURCE.relative_to(ROOT).as_posix(), "source_sha256": sha(SOURCE),
            "trace_sha256": source["trace_sha256"], "selected_link": name,
            "link_capacity_Bps": link["capacity_Bps"],
            "link_prompt_messages_1800s": n,
            "link_decode_messages_1800s": int(link["decode_messages"]),
            "decode_rate_per_s": rate, "global_arrivals_1800s": len(arrivals),
            "selection_seed": PLAN_SEED, "clip_start_s": CLIP_START_S, "clip_s": CLIP_S,
            "large_bytes": LARGE_BYTES, "small_bytes": SMALL_BYTES,
            "proxy_note": "Prompt times are deterministic thinning of global query arrivals; original result has no per-link event times",
            "repetitions": repetitions}


def prepare():
    generated = make_traffic()
    if TRAFFIC.exists():
        if read(TRAFFIC) != generated:
            raise RuntimeError("Frozen traffic differs from source or code")
    else:
        write(TRAFFIC, generated)
    scripts = {name: sha(HERE / name) for name in ("traffic.py", "bench.py")}
    manifest = {"source_sha256": generated["source_sha256"], "traffic_sha256": sha(TRAFFIC),
                "scripts_sha256": scripts, "bandwidth_MBps": [12.5, 25, 50],
                "one_way_delay_ms": 25, "modes": ["fifo", "priority", "chunk4", "chunk1", "two_connections"],
                "repeats": REPEATS, "clip_s": CLIP_S,
                "failure_policy": "Each run has separate result/failure; no overwrites or zero imputation"}
    if MANIFEST.exists():
        if read(MANIFEST) != manifest:
            raise RuntimeError("Frozen manifest differs from current traffic, scripts or configuration")
    else:
        write(MANIFEST, manifest)
    return manifest


def serial_prediction(events, mode, rate_Bps, delay_s):
    """Single-link model: FIFO or Decode-first at whole-message/chunk boundaries."""
    pending = deque()
    current_large = None
    t = 0.0
    cursor = 0
    small_completed = {}
    large_completed = {}
    chunk = 4_194_304 if mode == "chunk4" else 1_048_576 if mode == "chunk1" else LARGE_BYTES
    while cursor < len(events) or pending or current_large:
        while cursor < len(events) and events[cursor]["at_s"] <= t + 1e-12:
            pending.append(dict(events[cursor]))
            cursor += 1
        if not pending and not current_large:
            t = events[cursor]["at_s"]
            continue
        if mode == "fifo":
            chosen = pending.popleft()
        else:
            small_at = next((i for i, e in enumerate(pending) if e["kind"] == "S"), None)
            if small_at is not None:
                chosen = pending[small_at]
                del pending[small_at]
            elif current_large:
                chosen = current_large
                current_large = None
            else:
                chosen = pending.popleft()
        amount = min(chosen["bytes"], chunk) if chosen["kind"] == "L" else chosen["bytes"]
        t += amount / rate_Bps
        chosen["bytes"] -= amount
        if chosen["kind"] == "S":
            small_completed[chosen["id"]] = t + delay_s
        elif chosen["bytes"]:
            current_large = chosen
        else:
            large_completed[chosen["id"]] = t + delay_s
    return small_completed, large_completed


def fair_prediction(events, rate_Bps, delay_s):
    """Optimistic fluid fair share of one large and one small TCP flow."""
    queues = [deque(), deque()]
    t = 0.0
    cursor = 0
    small_completed, large_completed = {}, {}
    while cursor < len(events) or queues[0] or queues[1]:
        while cursor < len(events) and events[cursor]["at_s"] <= t + 1e-12:
            event = dict(events[cursor])
            queues[0 if event["kind"] == "L" else 1].append(event)
            cursor += 1
        active = [q for q in queues if q]
        if not active:
            t = events[cursor]["at_s"]
            continue
        share = rate_Bps / len(active)
        next_arrival = events[cursor]["at_s"] - t if cursor < len(events) else float("inf")
        dt = min(next_arrival, *(q[0]["bytes"] / share for q in active))
        if dt < -1e-9:
            raise RuntimeError("Nonmonotonic fair-share event clock")
        dt = max(0.0, dt)
        for q in active:
            q[0]["bytes"] -= dt * share
        t += dt
        for q in active:
            if q and q[0]["bytes"] <= 1e-6:
                event = q.popleft()
                target = large_completed if event["kind"] == "L" else small_completed
                target[event["id"]] = t + delay_s
    return small_completed, large_completed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        manifest = prepare()
        t = read(TRAFFIC)
        print("PREPARED", t["selected_link"], "large", t["repetitions"][0]["large_count"],
              "small_repeats", [r["small_count"] for r in t["repetitions"]],
              "traffic_sha256", manifest["traffic_sha256"])
    else:
        parser.error("choose --prepare")
