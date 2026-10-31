"""Synthetic 48/96-GPU placement search and measured online route timing."""
from __future__ import annotations

import argparse
import ast
import csv
import sys
import time
from collections import Counter
from configparser import ConfigParser
from pathlib import Path
from statistics import mean

from experiments.v5_core_supplement.run import ENV, ROOT, check, now, read, sha, write
from experiments.v6_completion.campaign_queue import queue, worker

HERE = Path(__file__).resolve().parent / "scalability"
SIZES = (48, 96)
TEMPLATE = ROOT / "examples/simulation/layouts/ilp/simulator_cluster.ini"
SEED = 0
LOAD = 100


def prepare():
    from simulator.initial_layout.fake_cluster_generator import FakeClusterGenerator
    from simulator.event_simulator.utils import MilliSec, gbps
    for size in SIZES:
        folder = HERE / f"gpu{size}"
        folder.mkdir(parents=True, exist_ok=True)
        physical, template = folder / "physical.ini", folder / "template.ini"
        if not physical.exists():
            generator = FakeClusterGenerator()
            generator.set_node_statistics(
                num_compute_nodes=size, avg_degree=size - 1,
                source_degree=size, sink_degree=size,
                node_type_percentage={"A100": size // 6, "L4": size // 3,
                                      "T4": size // 2})
            generator.set_link_statistics(
                avg_bandwidth=1 * gbps, var_bandwidth=0,
                avg_latency=1 * MilliSec, var_latency=0,
                fill_with_slow_link=True,
                slow_link_avg_bandwidth=1 * gbps, slow_link_var_bandwidth=0,
                slow_link_avg_latency=1 * MilliSec, slow_link_var_latency=0)
            generator.generator_fake_cluster(file_name=str(physical), seed=SEED)
        if not template.exists():
            base, output = ConfigParser(), ConfigParser()
            assert base.read(TEMPLATE)
            for section in ("Coordinator", "MachineTypes"):
                output[section] = dict(base[section])
            physical_ini = ConfigParser()
            assert physical_ini.read(physical)
            types = [physical_ini[f"ComputeNode-{i}"]["type"] for i in range(size)]
            assert Counter(types) == {"A100": size // 6, "L4": size // 3,
                                      "T4": size // 2}
            samples = {}
            for section in base.sections():
                if section.startswith("compute_node_"):
                    kind = ast.literal_eval(base[section]["machine_type"])
                    samples.setdefault(kind, dict(base[section]))
            output["ComputeNodes"] = {"names": repr([f"compute_node_{i + 2}"
                                                      for i in range(size)])}
            for i, kind in enumerate(types):
                output[f"compute_node_{i + 2}"] = dict(samples[kind])
            output["Links"] = {"names": "[]"}
            with template.open("w", encoding="utf-8") as stream:
                output.write(stream)
        print("PREPARED", size, sha(physical), sha(template), flush=True)


def search_one(size):
    from rcaps.v3.placement import save, validate
    from rcaps.v3.search import initial_states, search
    from rcaps.v3.topology import TopologyModel
    from rcaps.v4.admission import admitted_edges, canonical_edges
    folder = HERE / f"gpu{size}"
    path = folder / "search_result.json"
    if path.exists():
        result = read(path)
        for name, digest in result["inputs_sha256"].items():
            assert sha(folder / name) == digest
        return result
    model = TopologyModel(folder / "physical.ini")
    assert model.machine_counts == {"A100": size // 6, "L4": size // 3,
                                    "T4": size // 2}
    started = time.perf_counter()
    candidates, initialization = initial_states(model, a100_prefix=False,
                                                multistage=False)
    assert candidates, initialization
    reference = candidates[0]
    outcome = search(model, reference, a100_prefix=False, seed_state=reference)
    selected = outcome["multi"]
    assert selected["status"] == "feasible", selected
    state = selected["state"]
    checked = validate(model, state)
    deployment = folder / "deployment"
    saved = save(model, folder / "template.ini", state, deployment,
                 dict(synthetic_size=size, generation_seed=SEED))
    dag = checked["dag"]
    canonical = canonical_edges(state, dag, uid_offset=0)
    bandwidth = {edge: model.link(*edge)[1] for edge in dag.edge_set
                 if not isinstance(edge[0], str) and not isinstance(edge[1], str)}
    allowed = admitted_edges(canonical, dag.edge_set, bandwidth)
    result = dict(status="completed", size=size, topology_seed=SEED,
                  machine_counts=model.machine_counts,
                  inputs_sha256={name: sha(folder / name)
                                 for name in ("physical.ini", "template.ini")},
                  source_sha256={name: sha(ROOT / name) for name in (
                      "rcaps/v3/search.py", "rcaps/v3/placement.py",
                      "experiments/v6_completion/scalability.py")},
                  reference_initialization=initialization,
                  search_wall_s=outcome["search_wall_s"],
                  total_search_wall_s=time.perf_counter() - started,
                  candidate_evaluations=selected["candidate_evaluations"],
                  score=selected["score"], widths=saved["widths"],
                  active_gpus=saved["active_gpus"],
                  full_dag_edges=len(dag.edge_set),
                  sparse_admission_edges=len(allowed),
                  full_compatible_paths=dag.path_count(),
                  solution_sha256=saved["solution_sha256"],
                  sim_cluster_sha256=saved["sim_cluster_sha256"],
                  placement_sha256=sha(deployment / "placement.json"),
                  finished_at=now())
    write(path, result)
    print("SEARCH", size, result["total_search_wall_s"],
          result["full_compatible_paths"], flush=True)
    return result


def evaluate(job):
    from benchmarks.fixed_window import run
    from experiments.v5_core_supplement.adapters import SetupProbe
    from rcaps.v3.topology import TopologyModel
    from rcaps.v4.admission import AdmissionScheduler
    from rcaps.v4.chunking import PromptTransferChunkHook
    from rcaps.v4.probe import MechanismProbe
    folder = HERE / f"gpu{job['size']}"
    search_result = read(folder / "search_result.json")
    deployment = folder / "deployment"
    assert sha(deployment / "solution.ini") == search_result["solution_sha256"]
    assert sha(deployment / "simulator_cluster.ini") == search_result["sim_cluster_sha256"]
    model = TopologyModel(folder / "physical.ini")
    state = read(deployment / "placement.json")["state"]
    factory = lambda sim: AdmissionScheduler(sim, state=state, admission="sparse",
                                              routing_state="live")
    row = run("single", "queue_dag", LOAD, job["duration"], 0, job["seed"],
              deployment / "solution.ini", deployment / "simulator_cluster.ini",
              physical_cluster=folder / "physical.ini", machine_counts=model.machine_counts,
              scheduler_factory=factory, compact=True, record_query_samples=True,
              profile_scheduler=True, phase_link_probe=SetupProbe(
                  delegate=MechanismProbe(PromptTransferChunkHook(4_194_304, scope="slow"))))
    route = row["scheduler_call_profile"]["_route"]
    assert route["calls"] > 0
    row.update(size=job["size"], route_calls=route["calls"],
               route_mean_us=route["mean_us"], route_p95_us=route["p95_us"],
               solution_sha256=search_result["solution_sha256"],
               sim_cluster_sha256=search_result["sim_cluster_sha256"])
    return row


def register(phase, workers):
    path = HERE / phase / "manifest.json"
    if path.exists():
        manifest = read(path)
        check(manifest)
        return manifest
    for size in SIZES:
        assert read(HERE / f"gpu{size}/search_result.json")["status"] == "completed"
    archived_source = HERE / "search_source_v1.py"
    for size in SIZES:
        original_hash = read(HERE / f"gpu{size}/search_result.json")[
            "source_sha256"]["experiments/v6_completion/scalability.py"]
        assert sha(archived_source) == original_hash
    if phase == "formal":
        smoke = read(HERE / "smoke_v2/index.json")
        assert smoke["status"] == "terminal"
        assert all(x["status"] == "completed" for x in smoke["jobs"].values())
    sizes = (48,) if phase.startswith("smoke") else SIZES
    seeds = (100,) if phase.startswith("smoke") else tuple(range(5))
    jobs = [dict(key=f"gpu{size}/seed{seed}", size=size, seed=seed,
                 load=LOAD, duration=60 if phase.startswith("smoke") else 300)
            for size in sizes for seed in seeds]
    sources = dict(read(ROOT / "experiments/v5_core_supplement/formal/manifest.json")["sources_sha256"])
    for name in ("experiments/v6_completion/scalability.py",
                 "experiments/v6_completion/campaign_queue.py"):
        sources[name] = sha(ROOT / name)
    for size in SIZES:
        folder = HERE / f"gpu{size}"
        for path_in in (folder / "physical.ini", folder / "template.ini",
                        folder / "search_result.json", folder / "deployment/solution.ini",
                        folder / "deployment/simulator_cluster.ini",
                        folder / "deployment/placement.json"):
            sources[path_in.relative_to(ROOT).as_posix()] = sha(path_in)
    sources[archived_source.relative_to(ROOT).as_posix()] = sha(archived_source)
    manifest = dict(registered_at=now(), phase=phase, jobs=jobs,
                    sources_sha256=sources, worker_limit=workers,
                    timeout_wall_s=14400, topology_seed=SEED,
                    gpu_types_ratio="A100:L4:T4 = 1:2:3",
                    search="unchanged M2 beam64/B0=B1=500; reference is first feasible single-boundary initializer",
                    engineering_amendment="Original smoke exited at CLI parsing because generic workers omit positional command; search_source_v1.py preserves exact offline search code, smoke_v2 and formal accept command default online",
                    online="V4 sparse admission and 4MiB Prompt transfer chunking; profile_scheduler measures actual _route wall time",
                    failure_policy="One attempt per online key; no imputation",
                    environment=dict(executable=sys.executable, env=ENV))
    write(path, manifest)
    return manifest


def report():
    folder = HERE / "formal"
    manifest, index = read(folder / "manifest.json"), read(folder / "index.json")
    assert index["status"] == "terminal"
    rows = []
    for job in manifest["jobs"]:
        entry = index["jobs"][job["key"]]
        source = ROOT / entry["source"]
        assert sha(source) == entry["artifact_sha256"]
        result = read(source)
        rows.append(dict(size=job["size"], seed=job["seed"], status=entry["status"],
                         route_calls=result.get("route_calls"),
                         route_mean_us=result.get("route_mean_us"),
                         route_p95_us=result.get("route_p95_us"),
                         source=entry["source"], source_sha256=entry["artifact_sha256"],
                         error=result.get("error", "")))
    with (HERE / "individual.csv").open("w", newline="", encoding="utf-8-sig") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = ["# 48/96 GPU 合成拓扑扩展性（P2-1）", "",
             "节点类型 A100:L4:T4=1:2:3，单区域全连接 1 GB/s，拓扑生成 seed0。",
             "放置沿用 M2 beam64/B0=B1=500；路由耗时在 Windows gllm CPU 模拟运行中测量。",
             "路由均值和 P95 是每个窗口内真实 _route 调用的墙钟时间；不同机器不可直接比较。", "",
             "| GPU | 搜索总秒 | 候选评分次数 | 全部兼容路径 | 准入边/全图边 | 路由成功 | 路由均值 µs | 路由 P95 µs |",
             "|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for size in SIZES:
        offline = read(HERE / f"gpu{size}/search_result.json")
        valid = [r for r in rows if r["size"] == size and r["status"] == "completed"]
        mu = f"{mean(r['route_mean_us'] for r in valid):.1f}" if len(valid) == 5 else "未汇总"
        p95 = f"{mean(r['route_p95_us'] for r in valid):.1f}" if len(valid) == 5 else "未汇总"
        lines.append(f"| {size} | {offline['total_search_wall_s']:.2f} | "
                     f"{offline['candidate_evaluations']} | {offline['full_compatible_paths']} | "
                     f"{offline['sparse_admission_edges']}/{offline['full_dag_edges']} | "
                     f"{len(valid)}/5 | {mu} | {p95} |")
    (HERE / "RESULTS_CN.md").write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    write(HERE / "FINAL_AUDIT.json", dict(passed=True, jobs=len(rows),
          counts=dict(Counter(x["status"] for x in index["jobs"].values())),
          source_manifest_sha256=sha(folder / "manifest.json"),
          csv_sha256=sha(HERE / "individual.csv"),
          report_sha256=sha(HERE / "RESULTS_CN.md")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="online",
                        choices=("prepare", "search", "online", "report"))
    parser.add_argument("--size", type=int, choices=SIZES)
    parser.add_argument("--phase", choices=("smoke", "smoke_v2", "formal"))
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--worker")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "search":
        for size in ((args.size,) if args.size else SIZES):
            search_one(size)
    elif args.command == "report":
        report()
    elif args.worker:
        worker(HERE, args.phase, args.worker, evaluate)
    else:
        queue(HERE, "experiments.v6_completion.scalability", args.phase,
              args.workers, register, report)


if __name__ == "__main__":
    main()
