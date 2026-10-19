"""Paired reporting for the isolated layer-hotspot and burst experiments."""

from __future__ import annotations

import json
from statistics import mean, stdev

from benchmarks.compare import MATCH_FIELDS, common_cohort
from experiments.m2_multistage_candidate.analysis import common_completed, pending
from rcaps.v3.placement import digest

from .plan import SCENES, write_json
from .pool import HERE, ROOT
from .run import MAIN_LOADS, SEEDS, VARIANTS, identity, key, matrix, trace


METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "completion_fraction", "backlog_at_window_end")


def load(index: dict, job: tuple) -> dict | None:
    item = index["jobs"].get(key(job))
    if item is None or item["status"] != "passed":
        return None
    path = ROOT / item["source"]
    if digest(path) != item["sha256"]:
        raise ValueError(f"Raw result changed: {path}")
    row = json.loads(path.read_text(encoding="utf-8"))
    scene, offered, burst, seed, variant = job
    expected = identity(scene, offered, burst, seed, variant, 1800)
    for field, value in expected.items():
        if field == "variant" and item.get("reused_from"):
            continue
        if row.get(field) != value:
            raise ValueError(f"Window identity mismatch {key(job)}: {field}")
    if len(row.get("query_samples", {})) != row["arrivals"]:
        raise ValueError(f"Incomplete query samples: {key(job)}")
    return row


def paired(left: dict, right: dict) -> dict:
    for field in MATCH_FIELDS:
        if left.get(field) != right.get(field):
            raise ValueError(f"Paired record differs in {field}")
    common_cohort(left, right)
    return {"delta": {metric: left[metric] - right[metric]
                      for metric in METRICS},
            "common_completed": common_completed(left, right)}


def report() -> None:
    index = json.loads((HERE / "formal_index.json").read_text(encoding="utf-8"))
    plan = json.loads((HERE / "plan_index.json").read_text(encoding="utf-8"))
    data = {"scenes": SCENES, "protocol": {"seeds": SEEDS,
            "duration_s": 1800, "warmup_s": 0, "tail_drain": False,
            "main_loads": MAIN_LOADS, "control_load": 300},
            "structure": plan["results"], "runs": {}, "pairs": {},
            "burst_trace_check": {}}
    lines = ["# V3 多级复制合成层热点压力验证", "",
             "此实验的逐层热点为合成画像；逐层知情适配器不属于冻结 V3。",
             "下表均为种子 0/1/2 的完整 1800 秒窗口，未完成窗口留空。", "",
             "## 离线结构", "",
             "| 信息条件/场景/结构 | 边界 | 各段副本数 | 层副本量 | 启用 GPU | 瓶颈资源 | 评分次数 | 规划秒数 |",
             "| --- | --- | --- | ---: | ---: | --- | ---: | ---: |"]
    for label, item in plan["results"].items():
        if item["status"] != "feasible":
            lines.append(f"| {label} | 不可行 | — | — | — | — | — | — |")
            continue
        lines.append(f"| {label} | {item['boundaries']} | {item['widths']} | "
                     f"{item['layer_copies']} | {item['active_gpus']} | "
                     f"{item['bottleneck_resource']} | "
                     f"{item['candidate_evaluations']} | {item['search_wall_s']:.2f} |")
    lines += ["", "## 在线结果", "",
             "| 场景 | 负载 | 到达 | 布局 | 吞吐 | P95 TTFT | P95 TPOT | 完成率 | 积压 | 实际路径数 | 跨副本请求比 |",
             "| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    jobs = matrix()
    for scene, offered, burst, _, variant in jobs:
        group = (scene, offered, burst, variant)
        label = f"{scene}/{'burst' if burst else 'uniform'}/{offered}/{variant}"
        if label in data["runs"]:
            continue
        rows = []
        for seed in SEEDS:
            row = load(index, (scene, offered, burst, seed, variant))
            if row is None:
                rows.append({"seed": seed, "status": index["jobs"].get(
                    key((scene, offered, burst, seed, variant)), {}).get("status", "missing")})
                continue
            samples = row["query_samples"].values()
            rows.append({"seed": seed, "status": "passed",
                         "source": index["jobs"][key((scene, offered, burst, seed, variant))],
                         "trace_sha256": row["trace_sha256"],
                         "actual_input_offered": sum(s["input_tokens"] for s in samples) / 1800,
                         "target_output_offered": sum(s["output_tokens"] for s in samples) / 1800,
                         "pending": pending(row), "path_use": row["path_use"],
                         "gpu_busy_fraction": row.get("gpu_busy_fraction", {}),
                         **{metric: row[metric] for metric in METRICS}})
        data["runs"][label] = rows
        if all(item["status"] == "passed" for item in rows):
            means = [mean(item[metric] for item in rows) for metric in METRICS]
            paths = mean(item["path_use"]["actual_paths"] for item in rows)
            crossed = mean(item["path_use"]["cross_replica_fraction"] or 0
                           for item in rows)
            lines.append(f"| {scene} | {offered} | {'burst' if burst else 'uniform'} | "
                         f"{variant} | {means[0]:.3f} | {means[1]:.3f} | "
                         f"{means[2]:.3f} | {means[3]:.3f} | {means[4]:.1f} | "
                         f"{paths:.1f} | {crossed:.3f} |")
        else:
            lines.append(f"| {scene} | {offered} | {'burst' if burst else 'uniform'} | "
                         f"{variant} | 不完整 | — | — | — | — | — | — |")
    for scene in SCENES:
        loads = MAIN_LOADS if scene == "mid_x4" else (300,)
        for offered in loads:
            for burst in ((False, True) if scene == "mid_x4" and offered == 300
                          else (False,)):
                for left, right in (("aware_multi", "aware_single"),
                                    ("uniform_multi", "uniform_single"),
                                    ("aware_multi", "uniform_multi"),
                                    ("witness", "aware_single")):
                    pairs = {}
                    for seed in SEEDS:
                        a = load(index, (scene, offered, burst, seed, left))
                        b = load(index, (scene, offered, burst, seed, right))
                        if a is not None and b is not None:
                            pairs[str(seed)] = paired(a, b)
                    data["pairs"][f"{scene}/{offered}/{burst}/{left}-{right}"] = pairs
    for seed in SEEDS:
        uniform = trace(300, seed, False)
        burst = trace(300, seed, True)
        same_sequence = [(i, o) for _, i, o in uniform] == [
            (i, o) for _, i, o in burst]
        if not same_sequence:
            raise ValueError(f"Burst changes request lengths or order: seed {seed}")
        data["burst_trace_check"][str(seed)] = {
            "same_request_count_and_length_order": True,
            "requests": len(uniform),
            "uniform_middle_arrivals": sum(600 <= t < 900 for t, _, _ in uniform),
            "burst_middle_arrivals": sum(600 <= t < 900 for t, _, _ in burst)}
    lines += ["", "## 同场景配对差值", "",
              "正值表示左侧布局高于右侧；TTFT/TPOT 的负值表示左侧更快。",
              "仅三种子齐全时汇总。", "",
              "| 场景/负载/到达 | 对比 | 吞吐差 | P95 TTFT 差 | P95 TPOT 差 | 完成率差 |",
              "| --- | --- | ---: | ---: | ---: | ---: |"]
    for label, pairs in data["pairs"].items():
        if len(pairs) != len(SEEDS):
            continue
        averages = {metric: mean(item["delta"][metric] for item in pairs.values())
                    for metric in METRICS}
        group, comparison = label.rsplit("/", 1)
        lines.append(f"| {group} | {comparison} | "
                     f"{averages[METRICS[0]]:+.3f} | {averages[METRICS[1]]:+.3f} | "
                     f"{averages[METRICS[2]]:+.3f} | {averages[METRICS[3]]:+.3f} |")
    write_json(HERE / "analysis.json", data)
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.6))
    for variant in VARIANTS:
        if variant == "witness":
            continue
        points = []
        for offered in MAIN_LOADS:
            values = data["runs"].get(f"mid_x4/uniform/{offered}/{variant}", [])
            if len(values) == len(SEEDS) and all(
                    item["status"] == "passed" for item in values):
                points.append((offered, values))
        for axis, metric in zip(axes, METRICS[:3]):
            axis.errorbar(
                [x for x, _ in points],
                [mean(item[metric] for item in values) for _, values in points],
                yerr=[stdev(item[metric] for item in values) for _, values in points],
                marker="o", capsize=3, label=variant)
    for axis, title in zip(axes, ("Output throughput (token/s)",
                                   "P95 TTFT (s)", "P95 TPOT (s)")):
        axis.set_title(title)
        axis.set_xlabel("Offered input + target-output token/s")
        axis.grid(alpha=.25)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(HERE / "mid_hotspot_curve.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    report()
