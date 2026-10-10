"""Audit and summarize the paired V2 structure experiment."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from statistics import mean, stdev


ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "benchmarks" / "runs"
LAYOUTS = ROOT / "rcaps" / "v2_layouts"
METHODS = ("rcaps", "rcaps_v2_fixed_structure", "rcaps_v2")
SCENARIOS = ("single", "multi")
SEEDS = (0, 1, 2)
METRICS = {
    "output_throughput_tokens_per_s": "吞吐 token/s",
    "ttft_p95_s": "P95 TTFT s",
    "tpot_p95_s": "P95 TPOT s/token",
    "completion_fraction": "完成率",
    "backlog_at_window_end": "窗口末积压",
}


def load_runs() -> dict:
    result = {}
    for scenario in SCENARIOS:
        for seed in SEEDS:
            batch = {}
            for method in METHODS:
                path = RUNS / scenario / f"seed{seed}" / f"{method}.json"
                batch[method] = json.loads(path.read_text(encoding="utf-8"))
                layout = (ROOT / "rcaps" / "layouts" / scenario if method == "rcaps"
                          else LAYOUTS / f"{scenario}_{'adaptive' if method == 'rcaps_v2' else 'fixed'}")
                for field, filename in (("solution_sha256", "solution.ini"),
                                        ("sim_cluster_sha256", "simulator_cluster.ini")):
                    actual = hashlib.sha256((layout / filename).read_bytes()).hexdigest()
                    if batch[method][field] != actual:
                        raise ValueError(f"Layout mismatch: {scenario} seed={seed} {method} {field}")
            checks = ("trace_sha256", "scenario", "seed", "duration_s",
                      "warmup_s", "offered_tokens_per_s", "query_samples_schema")
            for field in checks:
                if len({str(record[field]) for record in batch.values()}) != 1:
                    raise ValueError(f"Protocol mismatch: {scenario} seed={seed} {field}")
            if batch["rcaps"]["duration_s"] != 1800 or batch["rcaps"]["warmup_s"] != 0:
                raise ValueError("Expected 1800 seconds with zero warmup")
            for method in METHODS[1:]:
                if not batch[method].get("gpu_queue_request_s"):
                    raise ValueError(f"Missing GPU queue profile: {scenario} {seed} {method}")
            result[(scenario, seed)] = batch
    return result


def layout_summary(scenario: str, variant: str) -> dict:
    path = LAYOUTS / f"{scenario}_{variant}" / "placement.json"
    placement = json.loads(path.read_text(encoding="utf-8"))
    copies = sum(end - start for start, end in placement["intervals"].values())
    return {"stem": placement["stem"], "prefix_layers": placement["prefix_layers"],
            "branches": len(placement["branches"]), "layer_copies": copies,
            "active_gpus": len(placement["intervals"]),
            "candidate_evaluations": placement["candidate_evaluations"],
            "planning_s": placement["planning_s"],
            "placement_score": placement["score"]}


def route_gpu_count(record: dict) -> float:
    count = sum(record["route_counts"].values())
    return (sum(len(route.split("-")) * visits for route, visits in
                record["route_counts"].items()) / count if count else 0.0)


def used_gpus(record: dict) -> int:
    return len({node for route in record["route_counts"]
                for node in route.split("-")})


def normalized_queue(record: dict) -> float:
    return sum(record["gpu_queue_request_s"].values()) / record["arrivals"]


def paired_percent(batch: dict, candidate: str, baseline: str, key: str) -> float:
    left = batch[candidate][key]
    right = batch[baseline][key]
    if right == 0:
        raise ValueError(f"Zero baseline for {key}")
    direction = 1 if key in ("output_throughput_tokens_per_s",
                              "completion_fraction") else -1
    return direction * (left / right - 1) * 100


def summarize() -> tuple[dict, str]:
    runs = load_runs()
    output = {}
    lines = ["# V2 自适应结构实验结果", "",
             "所有数字均为两种拓扑内的种子 0/1/2 配对结果。正的相对变化表示改善；不作统计显著性断言。", ""]
    for scenario in SCENARIOS:
        summary = {"layouts": {variant: layout_summary(scenario, variant)
                               for variant in ("fixed", "adaptive")},
                   "seeds": {}, "paired": {}}
        lines += [f"## {scenario}", "",
                  f"固定结构：`{summary['layouts']['fixed']}`", "",
                  f"自适应结构：`{summary['layouts']['adaptive']}`", ""]
        lines += ["| 种子 | 方法 | 吞吐 | P95 TTFT | P95 TPOT | 完成率 | 积压 | GPU 排队 s/到达 | 每请求 GPU 数 | 实际执行 GPU 数 |",
                  "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for seed in SEEDS:
            batch = runs[(scenario, seed)]
            summary["seeds"][str(seed)] = {}
            for method in METHODS:
                record = batch[method]
                queue = (normalized_queue(record) if "gpu_queue_request_s" in record
                         else None)
                item = {key: record[key] for key in METRICS}
                item.update({"trace_sha256": record["trace_sha256"],
                             "gpu_queue_request_s_per_arrival": queue,
                             "route_gpu_count": route_gpu_count(record),
                             "used_gpus": used_gpus(record)})
                summary["seeds"][str(seed)][method] = item
                queue_text = f"{queue:.3f}" if queue is not None else "—"
                lines.append(f"| {seed} | {method} | "
                             f"{record['output_throughput_tokens_per_s']:.3f} | "
                             f"{record['ttft_p95_s']:.3f} | "
                             f"{record['tpot_p95_s']:.3f} | "
                             f"{record['completion_fraction']:.3f} | "
                             f"{record['backlog_at_window_end']} | {queue_text} | "
                             f"{item['route_gpu_count']:.1f} | {item['used_gpus']} |")
        lines += ["", "| 配对比较（平均相对改善 ± 样本标准差） | 吞吐 | TTFT | TPOT | 完成率 | 积压 |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for candidate, baseline in (("rcaps_v2", "rcaps_v2_fixed_structure"),
                                    ("rcaps_v2", "rcaps")):
            label = f"{candidate} vs {baseline}"
            summary["paired"][label] = {}
            values = []
            for key in METRICS:
                per_seed = [paired_percent(runs[(scenario, seed)], candidate, baseline, key)
                            for seed in SEEDS]
                summary["paired"][label][key] = per_seed
                values.append(f"{mean(per_seed):+.2f} ± {stdev(per_seed):.2f}%")
            lines.append("| " + label + " | " + " | ".join(values) + " |")
        lines += ["", "V1 历史结果未启用资源画像，因此 GPU 排队仅在 V2 的两个变体间直接比较。结构变化同时改变复制量和每请求路径长度；归因以固定结构消融为准。", ""]
        output[scenario] = summary
    return output, "\n".join(lines) + "\n"


def main() -> None:
    data, markdown = summarize()
    folder = Path(__file__).resolve().parent
    (folder / "summary.json").write_text(json.dumps(data, indent=2) + "\n",
                                         encoding="utf-8")
    (folder / "RESULTS.md").write_text(markdown, encoding="utf-8")
    print(folder / "RESULTS.md")


if __name__ == "__main__":
    main()
