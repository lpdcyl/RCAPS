"""Frozen, isolated formal V4 windows. Failure stops new queue dispatch."""
from __future__ import annotations

import argparse
import faulthandler
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
import time
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
INDEX = HERE / "index.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat()


def environment():
    spec = read(HERE / "env-spec.json")
    result = {"python": platform.python_version(), "executable": sys.executable,
              "packages": {n: importlib.metadata.version(n) for n in spec["packages"]},
              "env": {n: os.environ.get(n) for n in spec["env"]},
              "platform": platform.platform()}
    if (result["python"] != spec["python"] or result["packages"] != spec["packages"]
            or result["env"] != spec["env"]):
        raise RuntimeError(f"Environment differs from frozen spec: {result}")
    return result


def jobs():
    rows = {}
    def add(scenario, load, cell, group):
        for seed in (0, 1, 2):
            key = f"{scenario}/load{load}/{cell}/seed{seed}"
            if key not in rows:
                rows[key] = {"key": key, "scenario": scenario, "load": load,
                             "cell": cell, "seed": seed, "groups": []}
            if group not in rows[key]["groups"]:
                rows[key]["groups"].append(group)
    for load in (320, 160):
        for cell in ("v3", "spatial", "temporal", "v4"):
            add("multi", load, cell, "factorial")
    for scenario, loads in {"single": [100, 200, 350, 500, 700, 900],
                            "multi": [50, 100, 160, 240, 320, 400]}.items():
        for load in loads:
            add(scenario, load, "v4", "curve")
    for cell in ("canonical4", "all4", "chunk1", "chunk2", "chunk8"):
        add("multi", 320, cell, "mechanism")
    for scenario, load in (("single", 700), ("multi", 320)):
        add(scenario, load, "static", "components")
        add(scenario, load, "single_boundary", "components")
    for scenario, load in (("C2", 160), ("C3", 400)):
        for cell in ("v3", "v4"):
            add(scenario, load, cell, "generalization")
    return list(rows.values())


def inputs(job):
    scenario = job["scenario"]
    case = "C1_" + scenario if scenario in {"single", "multi"} else scenario
    planning = read(ROOT / "rcaps/v3/planning_inputs.json")[case]
    deployment = (ROOT / "experiments/m2_multistage_candidate/layouts" / case / "single_any"
                  if job["cell"] == "single_boundary" else ROOT / "rcaps/v3_layouts" / scenario)
    return ROOT / planning["physical"], deployment


def source_files():
    paths = set()
    for directory in ("rcaps", "simulator"):
        for p in (ROOT / directory).rglob("*"):
            if p.is_file() and p.suffix in {".py", ".ini", ".csv", ".pkl", ".json"}:
                paths.add(p)
    for directory in ("benchmarks", "baselines", "experiments/v4_formal"):
        paths.update((ROOT / directory).glob("*.py"))
    paths.update([HERE / "protocol.json", HERE / "env-spec.json"])
    for job in jobs():
        physical, layout = inputs(job)
        paths.add(physical)
        paths.update(layout / name for name in ("solution.ini", "simulator_cluster.ini", "placement.json"))
    return sorted(paths)


def anchor_path(job):
    if job["scenario"] != "multi" or job["load"] != 320:
        return None
    seed, cell = job["seed"], job["cell"]
    names = {"v3": f"benchmarks/runs/multi/seed{seed}/rcaps_v3.json",
             "spatial": f"work3_sparse_replication/runs/C1_multi/gated_seed{seed}.json",
             "v4": f"work3_chunk_012/runs/chunk_4MiB_seed{seed}.json"}
    return ROOT / names[cell] if cell in names else None


def freeze():
    preflight = read(HERE / "preflight.json")
    if preflight["status"] != "passed":
        raise RuntimeError("Preflight has not passed")
    for name, expected in preflight["sources_sha256"].items():
        if digest(ROOT / name) != expected:
            raise RuntimeError(f"Core changed after preflight: {name}")
    paths = source_files()
    controls = {p.relative_to(ROOT).as_posix(): digest(p)
                for j in jobs() if (p := anchor_path(j)) is not None}
    content = {"protocol": read(HERE / "protocol.json"), "environment": environment(),
               "sources_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in paths},
               "anchor_controls_sha256": controls,
               "preflight_sha256": digest(HERE / "preflight.json"), "jobs": jobs()}
    if MANIFEST.exists():
        old = read(MANIFEST)
        for key, value in content.items():
            if old[key] != value:
                raise RuntimeError(f"Frozen manifest changed: {key}")
    else:
        content.update({"registered_at": stamp(),
                        "git_commit_at_registration": subprocess.check_output(
                            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                        "historical_runtime_exception": "unresolved; prospective diagnostics enabled"})
        write(MANIFEST, content)
    return read(MANIFEST)


def validate():
    frozen = read(MANIFEST)
    if environment() != frozen["environment"]:
        raise RuntimeError("Worker environment drift")
    for category in ("sources_sha256", "anchor_controls_sha256"):
        for name, expected in frozen[category].items():
            if digest(ROOT / name) != expected:
                raise RuntimeError(f"Frozen input changed: {name}")
    return frozen


def capture(error):
    frames, tb = [], error.__traceback__
    wanted = {"prompt_time", "decode_time", "prompt_vram", "decode_vram",
              "prompt_phase_tokens", "decode_phase_tokens", "decode_left", "decode_right",
              "layer_id", "query_uid", "num_tokens"}
    while tb:
        f = tb.tb_frame
        item = {"file": f.f_code.co_filename, "function": f.f_code.co_name, "line": tb.tb_lineno}
        if "simulator" in f.f_code.co_filename:
            item["locals"] = {k: {"type": type(v).__name__, "repr": repr(v)[:250]}
                              for k, v in f.f_locals.items() if k in wanted}
            obj = f.f_locals.get("self")
            for field in ("prompt_bs2time", "decode_bs2time"):
                if hasattr(obj, field):
                    item[field] = {str(k): {"type": type(v).__name__, "repr": repr(v)[:120]}
                                   for k, v in getattr(obj, field).items()}
        frames.append(item)
        tb = tb.tb_next
    return {"exception_type": type(error).__name__, "error": repr(error),
            "traceback": traceback.format_exc(), "frames": frames}


def run_one(key):
    faulthandler.enable()
    output = HERE / "runs" / key / "result.json"
    if output.exists() or output.with_name("failure.json").exists():
        raise RuntimeError("Existing attempt retained; automatic overwrite/retry forbidden")
    started = time.perf_counter()
    try:
        frozen = validate()
        job = next(j for j in frozen["jobs"] if j["key"] == key)
        from rcaps.v3.topology import TopologyModel
        from rcaps.v4_method import evaluate_variant
        physical, deployment = inputs(job)
        cell = job["cell"]
        admission = "full" if cell in {"v3", "temporal"} else "canonical" if cell == "canonical4" else "sparse"
        chunk = {"v3": 0, "spatial": 0, "chunk1": 1048576,
                 "chunk2": 2097152, "chunk8": 8388608}.get(cell, 4194304)
        scenario = job["scenario"] if job["scenario"] in {"single", "multi"} else "single"
        row = evaluate_variant(scenario, job["load"], 1800, 0, job["seed"],
                               deployment / "solution.ini", deployment / "simulator_cluster.ini",
                               admission=admission, chunk_bytes=chunk,
                               scope="all" if cell == "all4" else "slow",
                               routing_state="static" if cell == "static" else "live",
                               physical_cluster=physical,
                               machine_counts=TopologyModel(physical).machine_counts)
        row.update({"job": job, "system": cell, "case": job["scenario"],
                    "manifest_sha256": digest(MANIFEST), "environment": environment(),
                    "elapsed_wall_s": time.perf_counter() - started,
                    "finished_at": stamp(), "status": "completed"})
        row["gpu_seconds_per_output_token"] = sum(row["gpu_busy_fraction"].values()) / row["output_throughput_tokens_per_s"]
        previous = anchor_path(job)
        if previous is not None:
            old = read(previous)
            fields = ("trace_sha256", "output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
                      "completion_fraction", "backlog_at_window_end", "route_counts", "query_samples", "gpu_busy_fraction")
            differences = [k for k in fields if row[k] != old[k]]
            row["historical_anchor_parity"] = {"source": previous.relative_to(ROOT).as_posix(),
                                               "differences": differences, "passed": not differences}
            if differences:
                write(output.with_name("parity_mismatch_result.json"), row)
                raise RuntimeError(f"Historical anchor semantic mismatch: {differences}")
        validate()
        write(output, row)
        print("FORMAL_COMPLETED", key, flush=True)
    except BaseException as error:
        failure = capture(error)
        failure.update({"key": key, "finished_at": stamp(), "pid": os.getpid(),
                        "elapsed_wall_s": time.perf_counter() - started})
        write(output.with_name("failure.json"), failure)
        raise


def report():
    records = []
    grouped, raw = {}, {}
    from statistics import mean, stdev
    metrics = ("tpot_p95_s", "ttft_p95_s", "output_throughput_tokens_per_s",
               "gpu_seconds_per_output_token", "completion_fraction", "backlog_at_window_end")
    for job in jobs():
        target = HERE / "runs" / job["key"] / "result.json"
        if target.exists():
            row = read(target)
            raw[job["scenario"], job["load"], job["cell"], job["seed"]] = row
            records.append(dict(job, **{k: row[k] for k in metrics}))
            grouped.setdefault((job["scenario"], job["load"], job["cell"]), []).append(row)
    summary = []
    for (scenario, load, cell), rows in grouped.items():
        complete = sorted(r["seed"] for r in rows) == [0, 1, 2]
        summary.append({"scenario": scenario, "load": load, "cell": cell,
                        "completed_seeds": sorted(r["seed"] for r in rows),
                        "complete_three_seed_group": complete,
                        "metrics": ({k: {"mean": mean(r[k] for r in rows),
                                           "sample_sd": stdev(r[k] for r in rows)}
                                     for k in metrics} if complete else None)})
    factorial = []
    import numpy as np
    for load in (320, 160):
        for seed in (0, 1, 2):
            keys = [("multi", load, cell, seed) for cell in ("v3", "spatial", "temporal", "v4")]
            if not all(k in raw for k in keys):
                continue
            base, spatial, temporal, full = [raw[k] for k in keys]
            effects = {}
            for name, left, right in (("spatial_vs_v3", base, spatial),
                                      ("temporal_vs_v3", base, temporal),
                                      ("v4_vs_spatial", spatial, full),
                                      ("v4_vs_temporal", temporal, full),
                                      ("v4_vs_v3", base, full)):
                if left["trace_sha256"] != right["trace_sha256"]:
                    raise RuntimeError("Unpaired formal traces")
                common = [uid for uid, a in left["query_samples"].items()
                          if a["completed"] and right["query_samples"][uid]["completed"]
                          and a["tpot_s"] is not None and right["query_samples"][uid]["tpot_s"] is not None]
                l = float(np.percentile([left["query_samples"][uid]["tpot_s"] for uid in common], 95)) if common else None
                r = float(np.percentile([right["query_samples"][uid]["tpot_s"] for uid in common], 95)) if common else None
                effects[name] = {"relative": {k: right[k] / left[k] - 1 if left[k] else None for k in metrics},
                                 "common_completed_count": len(common),
                                 "common_completed_tpot_p95_s": {"left": l, "right": r,
                                                                  "relative": r / l - 1 if l else None}}
            entry = {"load": load, "seed": seed, "effects": effects,
                     "tpot_log_interaction": math.log(full["tpot_p95_s"] / spatial["tpot_p95_s"]) -
                                             math.log(temporal["tpot_p95_s"] / base["tpot_p95_s"])}
            if load == 320:
                e = effects["v4_vs_spatial"]
                rel = e["relative"]
                checks = {"tpot": rel["tpot_p95_s"] <= -0.10,
                          "common_tpot": e["common_completed_tpot_p95_s"]["relative"] is not None
                              and e["common_completed_tpot_p95_s"]["relative"] <= -0.05,
                          "gpu_work": rel["gpu_seconds_per_output_token"] <= 0.05,
                          "ttft": rel["ttft_p95_s"] <= 0.02,
                          "throughput": rel["output_throughput_tokens_per_s"] >= -0.01,
                          "completion": full["completion_fraction"] - spatial["completion_fraction"] >= -0.01}
                entry["anchor_numeric_checks"] = dict(checks, all_passed=all(checks.values()))
            factorial.append(entry)
    write(HERE / "summary.json", {"generated_at": stamp(), "individual": records,
                                   "groups": summary, "factorial": factorial,
                                   "note": "Partial groups never get three-seed means."})
    print("completed windows", len(records), flush=True)


def queue(group):
    frozen = validate()
    if INDEX.exists():
        index = read(INDEX)
        if index["manifest_sha256"] != digest(MANIFEST):
            raise RuntimeError("Index manifest mismatch")
        if any(x["status"] in {"running", "failed"} for x in index["jobs"].values()):
            raise RuntimeError("Unresolved running/failed attempts; no automatic retry")
    else:
        index = {"manifest_sha256": digest(MANIFEST), "jobs": {}}
    selected = [j for j in frozen["jobs"] if group == "mandatory" or group in j["groups"]]
    pending = [j for j in selected if index["jobs"].get(j["key"], {}).get("status") != "completed"]
    active = []
    halted = False
    index.update({"queue_pid": os.getpid(), "group": group, "selected_windows": len(selected),
                  "queue_started_at": stamp(), "queue_status": "running"})
    write(INDEX, index)
    while pending or active:
        while pending and len(active) < frozen["protocol"]["concurrency"] and not halted:
            job = pending.pop(0)
            directory = HERE / "runs" / job["key"]
            directory.mkdir(parents=True, exist_ok=True)
            log = (directory / "worker.log").open("x", encoding="utf-8")
            command = [sys.executable, "-u", "-X", "faulthandler", "-m", "experiments.v4_formal.run",
                       "--phase", "one", "--key", job["key"]]
            process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            active.append((process, log, job))
            index["jobs"][job["key"]] = {"status": "running", "pid": process.pid,
                                          "started_at": stamp(), "command": command}
            write(INDEX, index)
            print("START", job["key"], "pid", process.pid, flush=True)
        for process, log, job in list(active):
            code = process.poll()
            if code is None:
                continue
            log.close()
            active.remove((process, log, job))
            output = HERE / "runs" / job["key"] / "result.json"
            success = code == 0 and output.exists()
            index["jobs"][job["key"]].update({"status": "completed" if success else "failed",
                                                "exit_code": code, "finished_at": stamp(),
                                                "result_sha256": digest(output) if success else None})
            halted |= not success
            index["queue_status"] = "halting_after_failure" if halted else "running"
            write(INDEX, index)
            print("DONE" if success else "FAILED", job["key"], "exit", code, flush=True)
        if halted and not active:
            break
        if active:
            time.sleep(2)
    index.update({"queue_status": "halted" if halted else "completed",
                  "queue_finished_at": stamp(), "unstarted_windows": len(pending)})
    write(INDEX, index)
    report()
    if halted:
        raise SystemExit("Queue halted after preserved failure; no automatic retries")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("freeze", "one", "queue", "report"), required=True)
    parser.add_argument("--key")
    parser.add_argument("--group", choices=("factorial", "mandatory", "curve", "mechanism", "components", "generalization"), default="factorial")
    args = parser.parse_args()
    if args.phase == "freeze":
        content = freeze()
        print("FROZEN", len(content["jobs"]), "unique windows", digest(MANIFEST))
    elif args.phase == "one":
        run_one(args.key)
    elif args.phase == "queue":
        queue(args.group)
    else:
        report()


if __name__ == "__main__":
    main()
