"""Frozen-layout E1 CPU simulator campaign with preserved failures."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
ENV = dict(PYTHONHASHSEED="0", PYTHONIOENCODING="utf-8", MPLBACKEND="Agg",
           OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
CONDITIONS = (("single", 350), ("single", 700), ("multi", 160), ("multi", 320))
VARIANTS = ("R-noshare", "R-uniform", "R-greedy", "R-random")

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

def rel(path):
    return Path(path).relative_to(ROOT).as_posix()

def now():
    return datetime.now(timezone.utc).isoformat()

def paths(job):
    from benchmarks.layout import scenario as physical
    case = "C1_" + job["scenario"]
    folder = HERE / "layouts" / case / job["variant"]
    return folder / "solution.ini", folder / "simulator_cluster.ini", physical(job["scenario"])[0], folder / "placement.json"

def inputs():
    files = [Path(__file__), HERE / "PLAN_CN.md", HERE / "planning_manifest.json",
             HERE / "placement_multi.py", HERE / "search_multi.py",
             ROOT / "experiments/v5_core_supplement/individual.csv"]
    for folder in ("simulator", "rcaps", "benchmarks", "baselines"):
        files.extend(p for p in (ROOT / folder).rglob("*") if p.is_file() and p.suffix in (".py", ".csv", ".pkl")
                     and "__pycache__" not in p.parts)
    for scenario, load in CONDITIONS:
        for variant in VARIANTS:
            files.extend(paths(dict(scenario=scenario, variant=variant)))
    with (ROOT / "experiments/v5_core_supplement/individual.csv").open(newline="", encoding="utf-8-sig") as stream:
        files.extend(ROOT / row["source"] for row in csv.DictReader(stream)
                     if row["cell"] in ("HR", "V4") and
                     (row["scenario"], int(row["load"])) in CONDITIONS)
    return {rel(p): sha(p) for p in sorted(set(files))}

def check(manifest):
    for name, digest in manifest["sources_sha256"].items():
        if sha(ROOT / name) != digest:
            raise RuntimeError("Frozen E1 input changed: " + name)

def register(phase):
    directory = HERE / phase
    directory.mkdir(exist_ok=True)
    path = directory / "manifest.json"
    if path.exists():
        manifest = read(path)
        check(manifest)
        return manifest
    if phase == "formal":
        smoke = read(HERE / "smoke/index.json")
        if smoke["status"] != "terminal" or any(v["status"] != "completed" for v in smoke["jobs"].values()):
            raise RuntimeError("E1 smoke failed or incomplete")
    seeds = (100,) if phase == "smoke" else tuple(range(5))
    jobs = [dict(key=f"{scenario}/{load}/{variant}/seed{seed}", scenario=scenario, load=load,
                 variant=variant, seed=seed, duration_s=60 if phase == "smoke" else 1800)
            for scenario, load in CONDITIONS for variant in VARIANTS for seed in seeds]
    manifest = dict(registered_at=now(), phase=phase, jobs=jobs, max_workers=2,
        warmup_s=0, drain_tail=False, failure_policy="one attempt per key; original failure preserved",
        expected_formal_windows=80, structural_infeasible="R-pipelines: 152 layer capacity < 160 needed",
        environment=dict(executable=sys.executable, python=sys.version, env=ENV,
            packages={name: importlib.metadata.version(name) for name in ("numpy", "scipy", "networkx", "gurobipy")}),
        sources_sha256=inputs())
    write(path, manifest)
    return manifest

def worker(phase, key):
    path = HERE / phase / "manifest.json"
    manifest = read(path)
    job = next(j for j in manifest["jobs"] if j["key"] == key)
    dest = HERE / phase / "runs" / key
    start = time.perf_counter()
    try:
        check(manifest)
        solution, cluster, physical, placement_path = paths(job)
        state = read(placement_path)["state"]
        from benchmarks.fixed_window import run
        from rcaps.v4.admission import AdmissionScheduler
        from rcaps.v4.chunking import PromptTransferChunkHook
        from rcaps.v4.probe import MechanismProbe
        from experiments.v5_core_supplement.adapters import SetupProbe
        factory = lambda simulator: AdmissionScheduler(simulator, state=state, admission="sparse", routing_state="live")
        row = run(job["scenario"], "queue_dag", job["load"], job["duration_s"], 0,
            job["seed"], solution, cluster, physical_cluster=physical,
            scheduler_factory=factory, compact=True, record_query_samples=True,
            profile_resources=True, phase_link_probe=SetupProbe(delegate=MechanismProbe(
                PromptTransferChunkHook(4_194_304, scope="slow"))))
        check(manifest)
        if len(row["query_samples"]) != row["arrivals"] or row["output_throughput_tokens_per_s"] <= 0:
            raise RuntimeError("Bad sample count or zero output throughput")
        row.update(row["phase_link_profile"]["corrected_network_accounting"])
        work = sum(row["gpu_busy_fraction"].values()) / row["output_throughput_tokens_per_s"]
        row.update(status="completed", job=job, cell=job["variant"],
            solution_sha256=sha(solution), sim_cluster_sha256=sha(cluster),
            gpu_seconds_per_output_token=work, environment=manifest["environment"],
            manifest_sha256=sha(path), elapsed_wall_s=time.perf_counter()-start, finished_at=now())
        write(dest / "result.json", row)
    except BaseException as error:
        write(dest / "failure.json", dict(status="failed", job=job, error=repr(error),
            traceback=traceback.format_exc(), manifest_sha256=sha(path),
            elapsed_wall_s=time.perf_counter()-start, finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)

def queue(phase):
    manifest = register(phase)
    directory = HERE / phase
    index_path = directory / "index.json"
    if index_path.exists():
        raise RuntimeError("E1 index exists; inspect before recovery")
    index = dict(status="running", controller_pid=os.getpid(), started_at=now(),
        manifest_sha256=sha(directory / "manifest.json"),
        jobs={job["key"]: dict(status="pending") for job in manifest["jobs"]})
    write(index_path, index)
    pending = list(manifest["jobs"])
    active = []
    environment = dict(os.environ, **ENV)
    while pending or active:
        while pending and len(active) < manifest["max_workers"]:
            check(manifest)
            job = pending.pop(0)
            run_dir = directory / "runs" / job["key"]
            run_dir.mkdir(parents=True, exist_ok=False)
            log = (run_dir / "worker.log").open("x", encoding="utf-8")
            command = [sys.executable, "-u", "-X", "faulthandler", "-m",
                "experiments.reviewer_v2.E1_placement.run", "--phase", phase, "--worker", job["key"]]
            proc = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=log)
            active.append((proc, job, log, time.monotonic()))
            index["jobs"][job["key"]] = dict(status="running", pid=proc.pid, started_at=now())
            write(index_path, index)
        for item in list(active):
            proc, job, log, start = item
            code = proc.poll()
            timed_out = code is None and time.monotonic()-start > 7200
            if timed_out:
                proc.kill()
                code = proc.wait()
            if code is None:
                continue
            log.close()
            active.remove(item)
            run_dir = directory / "runs" / job["key"]
            passed = code == 0 and (run_dir / "result.json").exists()
            output = run_dir / ("result.json" if passed else "failure.json")
            if not output.exists():
                write(output, dict(status="failed", job=job, exit_code=code,
                    classification="timeout" if timed_out else "native_or_abnormal_exit", finished_at=now()))
            index["jobs"][job["key"]].update(status="completed" if passed else "failed",
                exit_code=code, source=rel(output), artifact_sha256=sha(output), finished_at=now())
            write(index_path, index)
        if active:
            time.sleep(2)
    check(manifest)
    index.update(status="terminal", finished_at=now())
    write(index_path, index)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "formal"), required=True)
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--worker")
    args = parser.parse_args()
    if args.worker:
        worker(args.phase, args.worker)
    elif args.register:
        register(args.phase)
    else:
        queue(args.phase)
