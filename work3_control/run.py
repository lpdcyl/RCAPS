"""Isolated, bounded development of the whole-route control candidate."""
from __future__ import annotations

import argparse
import contextlib
import copy
import gzip
import io
import json
import math
import shutil
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from unittest.mock import patch

from experiments.v3_adaptive_space_cohort import run as historical
from experiments.v3_path_crossover import run as original
from work3_control.scheduler import KVRouteController, signature

ROOT = original.ROOT
HERE = Path(__file__).resolve().parent
PROTOCOL = original.read(HERE / "protocol.json")
POLICIES = tuple(PROTOCOL["policies"])


def exception_evidence(error):
    """Preserve callable/frame identity; never alter a failed calculation."""
    frames=[]
    current=error.__traceback__
    while current:
        frame=current.tb_frame
        item={"file":frame.f_code.co_filename,"function":frame.f_code.co_name,
              "line":current.tb_lineno}
        if "cur_layer" in frame.f_locals:
            layer=frame.f_locals["cur_layer"]
            method=getattr(layer,"get_inference_statistics",None)
            code=getattr(method,"__code__",None)
            item.update(layer_type=f"{type(layer).__module__}.{type(layer).__qualname__}",
                        method_qualname=getattr(method,"__qualname__",None),
                        method_file=code.co_filename if code else None,
                        method_code_sha256=original.hashlib.sha256(code.co_code).hexdigest() if code else None)
        if "requests" in frame.f_locals and isinstance(frame.f_locals["requests"],list):
            item["request_contracts"]=[{"uid":getattr(r,"request_uid",None),
                "phase":str(getattr(r,"phase",None)),"tokens":getattr(r,"token_seq_length",None)}
                for r in frame.f_locals["requests"][:8]]
        frames.append(item)
        current=current.tb_next
    return frames


def source_hashes():
    paths = list(HERE.glob("*.py")) + [HERE / "protocol.json",
        ROOT / PROTOCOL["registered_design"], historical.HERE / "audit.json"]
    return {p.relative_to(ROOT).as_posix(): original.digest(p) for p in sorted(paths)}


def audit_path(revision):
    if not revision.replace("_", "").isalnum():
        raise ValueError("Revision must be a simple alphanumeric name")
    return HERE / "audits" / f"{revision}.json"


def freeze(revision):
    legacy = historical.check_frozen()
    target = audit_path(revision)
    if target.exists():
        check_frozen(revision)
        return {"status": "already_frozen", "audit": str(target)}
    snapshot = HERE / "snapshots" / revision
    if snapshot.exists():
        raise ValueError("Preserved snapshot already exists")
    snapshot.mkdir(parents=True)
    for name in source_hashes():
        if name.startswith("work3_control/"):
            shutil.copy2(ROOT / name, snapshot / Path(name).name)
    data = {"revision": revision, "registered_at_utc": historical.timestamp(),
            "environment": historical.environment(), "sources_sha256": source_hashes(),
            "historical_source_count": len(legacy["sources_sha256"]),
            "historical_audit_sha256": original.digest(historical.HERE / "audit.json"),
            "source_tree": str(snapshot.relative_to(ROOT))}
    original.write(target, data)
    return {"status": "frozen", "audit": str(target), "sources": len(data["sources_sha256"])}


def check_frozen(revision):
    historical.check_frozen()
    audit = original.read(audit_path(revision))
    if audit["sources_sha256"] != source_hashes():
        raise ValueError("Source drift: preserve this revision; register a new revision")
    if audit["environment"] != historical.environment():
        raise ValueError("Environment differs from registered gllm")
    return audit


def trace_for(seed, stage_duration):
    from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder
    trace = []
    with contextlib.redirect_stdout(io.StringIO()):
        for index, spec in enumerate(PROTOCOL["stages"]):
            # The released Azure generator requires a multiple of three.
            # Generate the minimum enclosing trace and retain exactly the
            # preregistered 10/200-second arrival interval.
            generated_duration = 3 * ((stage_duration + 2) // 3)
            feeder = OnlineRequestFeeder(spec["offered"], 0.0, generated_duration,
                                        seed=seed * 100 + index)
            trace.extend((arrival + index * stage_duration, prompt, output)
                         for arrival, prompt, output in feeder.trace
                         if 0 <= arrival < stage_duration)
    if not trace:
        raise ValueError("Registered trace generated zero requests")
    if trace != sorted(trace, key=lambda entry: entry[0]):
        raise ValueError("Trace is not arrival ordered")
    return trace


class ExecutionWitness:
    """Read-only observation; retain raw execution events for recomputation."""
    def __init__(self, simulator, scheduler):
        self.simulator = simulator
        self.events = []
        self.routes = {}
        self.decode_route_checks = 0
        route_original = scheduler._route

        def routed(request):
            route = route_original(request)
            self.routes[request.base_query_uid] = signature(route)
            return route

        scheduler._route = routed
        source_original = simulator.source_node.issue_request

        def issued(request):
            from simulator.event_simulator.request import RequestPhase
            if request.phase == RequestPhase.Increment:
                if signature(request.mini_pipeline) != self.routes[request.base_query_uid]:
                    raise AssertionError("Decode route migrated")
                self.decode_route_checks += 1
            return source_original(request)

        simulator.source_node.issue_request = issued
        for node in simulator.compute_nodes.values():
            node.start_execution = self._wrap(node, node.start_execution)

    def _wrap(self, node, original_start):
        def record(requests):
            from simulator.event_simulator.request import RequestPhase
            batch = original_start(requests)
            decodes = sum(r.phase == RequestPhase.Increment for r in requests)
            prompts = len(requests) - decodes
            self.events.append([self.simulator.current_time, batch.duration,
                                node.node_uid, node.current_layer_id, decodes, prompts])
            return batch
        return record


def execute(revision, phase, policy, seed):
    check_frozen(revision)
    if policy not in POLICIES or phase not in ("smoke", "development"):
        raise ValueError("Unregistered policy/phase")
    seeds = [PROTOCOL["smoke_seed"]] if phase == "smoke" else PROTOCOL["development_seeds"]
    if seed not in seeds:
        raise ValueError("Do not replace development seeds or use formal seeds")
    stage_duration = PROTOCOL["stage_duration_s"][phase]
    duration = 3 * stage_duration
    target = HERE / "runs" / revision / phase / f"{policy}_seed{seed}.json"
    identity = {"experiment": PROTOCOL["experiment"], "revision": revision,
                "phase": phase, "policy": policy, "seed": seed, "duration_s": duration,
                "audit_sha256": original.digest(audit_path(revision)),
                "classification": "simulation_only"}
    failure = target.with_suffix(".failure.json")
    if failure.exists():
        raise ValueError(f"Preserved failure: {failure}")
    if target.exists():
        prior = original.read(target)
        if any(prior.get(k) != v for k, v in identity.items()):
            raise ValueError("Refusing to overwrite mismatched result")
        return {"status": "reused", "source": str(target.relative_to(ROOT))}
    from benchmarks import accumulator, fixed_window
    from experiments.v3_cluster42.kv_admission import install_completion_wakeup
    from experiments.v3_dynamic_pathspace.scheduler import KVAdaptiveLink
    from rcaps.v3.topology import TopologyModel
    from simulator.event_simulator.request import RequestPhase
    from simulator.event_simulator.model import ModelLayer
    context = original.load_context()
    full_edges = frozenset((a if isinstance(a, str) else a + 2,
                            b if isinstance(b, str) else b + 2)
                           for a, b in context["full_dag"].edge_set)
    if policy == "route_control":
        base = partial(KVRouteController, baseline_edges=context["partial_edges"], full_edges=full_edges)
    elif policy == "adaptive_link":
        base = partial(KVAdaptiveLink, allowed_edges=context["canonical_edges"], min_link_relief_s=0.01)
    else:
        base = original.builder(policy, context)
    holder = {}

    class CapturingAccumulator(accumulator.WindowAccumulator):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            holder["accumulator"] = self

        def _observe_query(self, query, beginning, ending, finish=None):
            super()._observe_query(query, beginning, ending, finish)
            sample = self.query_samples.get(str(query.query_uid))
            if sample is not None:
                prompt = query.inference_history[0] if query.inference_history else None
                sample.update(finish_s=finish - beginning if finish is not None else None,
                              prompt_end_s=prompt.end_time - beginning if prompt else None,
                              route=[s.node_uid for s in prompt.path[:-1]] if prompt else [],
                              route_stages=signature(prompt.path) if prompt else [],
                              decode_completion_times_s=[item.end_time - beginning
                                  for item in query.inference_history[1:]
                                  if item.request_phase == RequestPhase.Increment and item.end_time < ending])

    def factory(simulator):
        scheduler = base(simulator)
        witness = ExecutionWitness(simulator, scheduler)
        install_completion_wakeup(simulator, scheduler)
        holder.update(simulator=simulator, scheduler=scheduler, witness=witness)
        return scheduler

    target.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    statistics_original=ModelLayer.get_inference_statistics
    statistics_contract={"calls":0,"violations":0}

    def checked_statistics(layer,requests):
        result=statistics_original(layer,requests)
        statistics_contract["calls"]+=1
        if not isinstance(result,tuple) or len(result)!=2 or not all(
                isinstance(value,(int,float)) and math.isfinite(value) and value>=0 for value in result):
            statistics_contract["violations"]+=1
            raise TypeError(f"ModelLayer statistics contract: {type(result).__name__}: {result!r}")
        return result

    try:
        with target.with_suffix(".log").open("w", encoding="utf-8") as log, \
                contextlib.redirect_stdout(log), contextlib.redirect_stderr(log), \
                patch.object(accumulator, "WindowAccumulator", CapturingAccumulator), \
                patch.object(ModelLayer, "get_inference_statistics", checked_statistics):
            trace = trace_for(seed, stage_duration)
            window = fixed_window.run(context["topology"], "queue_dag", 0.0, duration, 0, seed,
                original.DEPLOY / "solution.ini", original.DEPLOY / "simulator_cluster.ini",
                compact=True, record_query_samples=True, profile_scheduler=True,
                scheduler_factory=factory, trace_override=trace, physical_cluster=context["physical"],
                machine_counts=TopologyModel(context["physical"]).machine_counts)
            window = copy.deepcopy(window)
            sim, scheduler, captured, witness = (holder[k] for k in
                ("simulator", "scheduler", "accumulator", "witness"))
            horizon = sim.current_time
            beginning = horizon - duration
            deadline = horizon + PROTOCOL["maximum_drain_s"]
            while sim.query_manager.queries_on_the_fly and sim.current_time < deadline:
                sim.simulate(until=min(deadline, sim.current_time + 30))
                captured.collect(sim, beginning, deadline)
            if sim.query_manager.queries_on_the_fly:
                raise ValueError("Bounded drain did not complete")
            scheduler.reap_finished()
            samples = copy.deepcopy(captured.query_samples)
            if len(samples) != len(trace) or not all(s["completed"] for s in samples.values()):
                raise ValueError("Missing or incomplete arrival cohort")
            if sum(s["output_tokens"] for s in samples.values()) != captured.output_count:
                raise ValueError("Output token conservation failed")
            events = [[t - beginning, *rest] for t, *rest in witness.events]
            event_path = target.with_suffix(".execution.json.gz")
            with gzip.open(str(event_path) + ".part", "wt", encoding="utf-8") as stream:
                json.dump(events, stream, separators=(",", ":"))
            Path(str(event_path) + ".part").replace(event_path)
            from work3_control.report import execution_metrics
            life = {**historical.cohort_summary(samples), "query_samples": samples,
                    "output_tokens_completed": captured.output_count,
                    "last_completion_s": max(s["finish_s"] for s in samples.values())}
            capacity = {str(uid): n.kv_cache.max_capacity for uid, n in sim.compute_nodes.items()
                        if n.kv_cache is not None}
            row = {**identity, "environment": historical.environment(),
                   "finished_at_utc": historical.timestamp(), "wall_seconds": time.perf_counter() - started,
                   "trace_sha256": window["trace_sha256"], "trace": trace,
                   "stages": [{"start_s": i * stage_duration, "end_s": (i+1)*stage_duration,
                               "offered_input_plus_output_tokens_per_s": stage["offered"]}
                              for i, stage in enumerate(PROTOCOL["stages"])],
                   "window": window, "lifecycle": life,
                   "execution_source": str(event_path.relative_to(ROOT)),
                   "execution_sha256": original.digest(event_path),
                   "execution": execution_metrics(events, duration),
                   "decode_route_checks": witness.decode_route_checks,
                   "statistics_contract": statistics_contract,
                   "kv_capacity": capacity,
                   "kv_peak_reserved": {str(k): v for k, v in scheduler.peak_reserved.items()},
                   "remaining_kv": {str(k): v for k, v in scheduler._reserved.items()},
                   "kv_admission": scheduler.kv_admission,
                   "route_count": scheduler.routes_assigned,
                   "control_counts": dict(getattr(scheduler, "control_counts", {})),
                   "control_events": getattr(scheduler, "control_events", []),
                   "control_switches": getattr(getattr(scheduler, "control", None), "switches", 0),
                   "legacy_gate_counts": dict(getattr(scheduler, "gate_counts", {}))}
            original.write(target, row)
    except Exception as error:
        with target.with_suffix(".log").open("a", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        original.write(failure, {**identity, "error": repr(error),
            "traceback": traceback.format_exc(), "exception_frames": exception_evidence(error),
            "statistics_contract": statistics_contract, "failed_at_utc": historical.timestamp()})
        raise
    return {"status": "passed", "source": str(target.relative_to(ROOT)),
            "wall_seconds": row["wall_seconds"], "arrivals": len(trace)}


def drive(revision, phase):
    check_frozen(revision)
    seeds = [PROTOCOL["smoke_seed"]] if phase == "smoke" else PROTOCOL["development_seeds"]
    jobs = [(policy, seed) for seed in seeds for policy in POLICIES]
    index_path = HERE / "runs" / revision / f"{phase}_index.json"
    if list((index_path.parent / phase).glob("*.failure.json")):
        raise ValueError("Investigate preserved failures before launching further jobs")
    started = time.perf_counter()
    index = {"phase": phase, "revision": revision, "expected": len(jobs), "jobs": {},
             "started_at_utc": historical.timestamp(), "complete": False}
    original.write(index_path, index)

    def launch(job):
        policy, seed = job
        command = [sys.executable, "-X", "faulthandler", "-m", "work3_control.run",
                   "--revision", revision, "--phase", phase, "--one", policy, str(seed)]
        try:
            process = subprocess.run(command, cwd=ROOT, capture_output=True,
                text=True, encoding="utf-8", timeout=PROTOCOL["cell_timeout_s"])
            return {"exit_code": process.returncode, "stdout": process.stdout, "stderr": process.stderr,
                    "result_exists": (index_path.parent / phase / f"{policy}_seed{seed}.json").exists()}
        except subprocess.TimeoutExpired as error:
            return {"exit_code": None, "timeout": True, "error": str(error), "result_exists": False}

    with ThreadPoolExecutor(max_workers=2) as pool:
        for offset in range(0, len(jobs), 2):
            if time.perf_counter() - started >= PROTOCOL["matrix_timeout_s"]:
                raise TimeoutError("Registered matrix budget exhausted")
            batch = jobs[offset:offset+2]
            outcomes = list(pool.map(launch, batch))
            for job, outcome in zip(batch, outcomes):
                key = f"{job[0]}/seed{job[1]}"
                index["jobs"][key] = outcome
                original.write(index_path, index)
                print(json.dumps({"done": len(index["jobs"]), "expected": len(jobs),
                                  "job": key, **outcome}, ensure_ascii=False), flush=True)
            if any(o["exit_code"] != 0 or not o["result_exists"] for o in outcomes):
                raise RuntimeError("Preserve failure; no additional jobs launched")
    index.update(complete=True, finished_at_utc=historical.timestamp(),
                 wall_seconds=time.perf_counter() - started)
    original.write(index_path, index)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default="v1")
    parser.add_argument("--phase", required=True, choices=("freeze", "smoke", "development", "report"))
    parser.add_argument("--one", nargs=2, metavar=("POLICY", "SEED"))
    args = parser.parse_args()
    if args.phase == "freeze":
        print(json.dumps(freeze(args.revision)))
    elif args.phase == "report":
        from work3_control.report import generate
        print(json.dumps(generate(args.revision), ensure_ascii=False))
    elif args.one:
        print(json.dumps(execute(args.revision, args.phase, args.one[0], int(args.one[1]))))
    else:
        drive(args.revision, args.phase)


if __name__ == "__main__":
    main()
