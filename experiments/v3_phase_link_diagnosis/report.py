"""Create a reproducible Chinese mechanism report and slow-link figure."""

from __future__ import annotations

import csv
import gzip
import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent


def fmt(value, digits=3):
    return "NA" if value is None else f"{value:.{digits}f}"


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_optional(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def slow_link_summary(run):
    links = [link for link in run["phase_link_profile"]["links"]
             if link["compute_to_compute"] and link["capacity_Bps"] <= 50_000_000]
    used = [link for link in links if link["prompt_messages"] or link["decode_messages"]]
    return {"active_links": len(used),
            "prompt_MB_total": sum(link["prompt_bytes"] for link in used) / 1_000_000,
            "prompt_MB_max_link": max((link["prompt_bytes"] for link in used), default=0) / 1_000_000,
            "utilization_max_link": max((link["busy_utilization"] for link in used), default=0),
            "mean_slow_links_per_query": run["route_summary"]["mean_slow_compute_links_per_query"]}


def query_tail_test(run, seed):
    """One raw-log pass for the query bootstrap and message overlap ledger."""
    profile = run["phase_link_profile"]
    raw_path = profile.get("raw_events")
    if not raw_path or not Path(raw_path).exists():
        raise FileNotFoundError(f"Missing local event stream {raw_path}; rerun the "
                                "formal baseline window before regenerating this report")
    all_links = profile["links"]
    compute_ids = {row["from"] for row in all_links if row["compute_to_compute"]}
    compute_ids |= {row["to"] for row in all_links if row["compute_to_compute"]}
    sink_links = {row["link_uid"] for row in all_links
                  if row["from"] in compute_ids and row["to"] not in compute_ids}
    slow_links = {row["link_uid"] for row in all_links
                  if row["compute_to_compute"] and row["capacity_Bps"] <= 50_000_000}
    blocked_by_request = defaultdict(float)
    slow_blocked_by_request = defaultdict(float)
    phase_by_request = {}
    completed = defaultdict(list)
    completed_slow = defaultdict(list)
    per_link_decode = defaultdict(lambda: {"messages": 0, "blocked_messages": 0})
    byte_ledger = defaultdict(lambda: {"prompt": 0.0, "decode": 0.0})
    totals = {"decode_messages": 0, "decode_wait_s": 0.0,
              "same_link_prompt_s": 0.0, "shared_nic_prompt_s": 0.0,
              "prompt_union_s": 0.0, "same_and_nic_overlap_s": 0.0,
              "slow_decode_messages": 0, "slow_decode_wait_s": 0.0,
              "slow_same_link_prompt_s": 0.0}
    with gzip.open(raw_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            uid = item.get("request_uid")
            if item["event"] == "start":
                phase_by_request[uid] = item["phase"]
                byte_ledger[item["link_uid"]][item["phase"]] += item["physical_bytes"]
                if item["phase"] == "decode":
                    same = item["same_prompt_wait_s"]
                    nic = item["nic_prompt_wait_s"]
                    union = item["any_prompt_wait_s"]
                    link_count = per_link_decode[item["link_uid"]]
                    link_count["messages"] += 1
                    link_count["blocked_messages"] += same > 1e-9
                    blocked_by_request[uid] += same
                    totals["decode_messages"] += 1
                    totals["decode_wait_s"] += max(0.0, item["time_s"] - item["ready_s"])
                    totals["same_link_prompt_s"] += same
                    totals["shared_nic_prompt_s"] += nic
                    totals["prompt_union_s"] += union
                    totals["same_and_nic_overlap_s"] += max(0.0, same + nic - union)
                    if item["link_uid"] in slow_links:
                        slow_blocked_by_request[uid] += same
                        totals["slow_decode_messages"] += 1
                        totals["slow_decode_wait_s"] += max(
                            0.0, item["time_s"] - item["ready_s"])
                        totals["slow_same_link_prompt_s"] += same
            elif (item["event"] == "arrival" and item["link_uid"] in sink_links
                  and phase_by_request.get(uid) == "decode"):
                completed[item["query_uid"]].append(blocked_by_request.pop(uid, 0.0))
                completed_slow[item["query_uid"]].append(
                    slow_blocked_by_request.pop(uid, 0.0))
                phase_by_request.pop(uid, None)
    for link in all_links:
        for phase in ("prompt", "decode"):
            observed = byte_ledger[link["link_uid"]][phase]
            if abs(observed - link[f"{phase}_bytes"]) > 1e-5:
                raise AssertionError(f"Raw byte ledger mismatch: {raw_path}, "
                                     f"link {link['link_uid']}, {phase}")
        if per_link_decode[link["link_uid"]]["messages"] != link["decode_messages"]:
            raise AssertionError(f"Raw Decode message count mismatch: {raw_path}, "
                                 f"link {link['link_uid']}")
    eligible = {int(uid) for uid, sample in run["query_samples"].items()
                if sample["tpot_s"] is not None}
    tail = set(profile["tail_query_ids"])
    rates = {uid: sum(value > 1e-9 for value in completed[uid][1:]) /
             len(completed[uid][1:]) for uid in eligible if len(completed[uid]) >= 2}
    a = [rates[uid] for uid in tail if uid in rates]
    b = [rates[uid] for uid in eligible - tail if uid in rates]
    if not a or not b:
        return None, totals, dict(per_link_decode)
    observed = mean(a) - mean(b)
    rng = random.Random(seed)
    samples = []
    for _ in range(2000):
        left = mean(rng.choice(a) for _ in a)
        right = mean(rng.choice(b) for _ in b)
        samples.append(left - right)
    samples.sort()
    slow_rates = {uid: sum(value > 1e-9 for value in completed_slow[uid][1:]) /
                  len(completed_slow[uid][1:]) for uid in eligible
                  if len(completed_slow[uid]) >= 2}
    slow_tail = [slow_rates[uid] for uid in tail if uid in slow_rates]
    slow_other = [slow_rates[uid] for uid in eligible - tail if uid in slow_rates]
    slow_samples = []
    for _ in range(2000):
        left = mean(rng.choice(slow_tail) for _ in slow_tail)
        right = mean(rng.choice(slow_other) for _ in slow_other)
        slow_samples.append(left - right)
    slow_samples.sort()
    def step_fraction(ids):
        steps = [value for uid in ids for value in completed_slow[uid][1:]]
        return sum(value > 1e-9 for value in steps) / len(steps) if steps else None
    return {"tail_queries": len(a), "other_queries": len(b),
            "tail_query_mean_fraction": mean(a),
            "other_query_mean_fraction": mean(b),
            "difference": observed,
            "bootstrap_95_ci": [samples[50], samples[1949]],
            "tail_exceeds_other_at_95pct": samples[50] > 0,
            "slow_tail_step_fraction": step_fraction(tail),
            "slow_all_step_fraction": step_fraction(eligible),
            "slow_query_bootstrap_95_ci": [slow_samples[50], slow_samples[1949]],
            "slow_tail_exceeds_other_at_95pct": slow_samples[50] > 0}, totals, dict(per_link_decode)


def generate(analysis, results):
    slow_rows = []
    interference_rows = []
    points = []
    grouped = defaultdict(list)
    tail_tests = {}
    link_blocking = {}
    for (variant, treatment, load, seed), run in sorted(results.items()):
        if treatment != "baseline":
            continue
        grouped[(variant, load)].append(run)
        tail_result, message_totals, per_link = query_tail_test(run, seed)
        tail_tests[f"{variant}/load{load}/seed{seed}"] = tail_result
        for link_uid, counts in per_link.items():
            link_blocking[(variant, load, seed, link_uid)] = counts
        interference_rows.append({"variant": variant, "load": load, "seed": seed,
                                  **(message_totals or {})})
        for link in run["phase_link_profile"]["links"]:
            if not link["compute_to_compute"] or link["capacity_Bps"] > 50_000_000:
                continue
            row = {"variant": variant, "load": load, "seed": seed,
                   "link_uid": link["link_uid"], "from": link["from"], "to": link["to"],
                   "capacity_MBps": link["capacity_Bps"] / 1_000_000,
                   "prompt_MB": link["prompt_bytes"] / 1_000_000,
                   "decode_MB": link["decode_bytes"] / 1_000_000,
                   "utilization": link["busy_utilization"],
                   "prompt_utilization": link["prompt_busy_utilization"],
                   "decode_utilization": link["decode_busy_utilization"],
                   "decode_messages": link["decode_messages"],
                   "prompt_messages": link["prompt_messages"],
                   "decode_blocked_messages": per_link[link["link_uid"]]["blocked_messages"],
                   "decode_blocked_fraction": (
                       per_link[link["link_uid"]]["blocked_messages"] /
                       per_link[link["link_uid"]]["messages"]
                       if per_link[link["link_uid"]]["messages"] else None),
                   "decode_wait_mean_s": link["decode_wait_mean_s"]}
            slow_rows.append(row)
            if row["decode_blocked_fraction"] is not None:
                points.append(row)
        run_key = f"{variant}/baseline/load{load}/seed{seed}"
        for link in analysis["runs"][run_key]["slow_links"]:
            counts = per_link[link["link_uid"]]
            link["decode_blocked_messages_all"] = counts["blocked_messages"]
            link["decode_blocked_fraction_all"] = (
                counts["blocked_messages"] / counts["messages"]
                if counts["messages"] else None)
    analysis["link_blocking_definition"] = (
        "decode_blocked_fraction_all uses all Decode start events on that link; "
        "the simulator probe's original decode_same_prompt_blocked_fraction "
        "is conditional on a positive ready-to-start wait")
    (HERE / "analysis.json").write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(HERE / "slow_links.csv", slow_rows)
    write_csv(HERE / "interference_components.csv", interference_rows)
    (HERE / "tail_query_bootstrap.json").write_text(
        json.dumps(tail_tests, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    fig, ax = plt.subplots(figsize=(7, 5), dpi=180)
    colors = {"k1": "#c43c39", "k3": "#2368a2"}
    markers = {160: "o", 320: "s", 330: "^", 340: "^", 350: "^"}
    seen = set()
    for row in points:
        label = f"{row['variant']} load {row['load']}"
        ax.scatter(row["utilization"], row["decode_blocked_fraction"],
                   color=colors[row["variant"]], marker=markers.get(row["load"], "^"),
                   alpha=0.6, s=35, label=label if label not in seen else None)
        seen.add(label)
    ax.set_xlabel("Slow compute-link serialization utilization")
    ax.set_ylabel("Decode messages delayed by active Prompt")
    ax.set_xlim(left=0)
    ax.set_ylim(0, max(row["decode_blocked_fraction"] for row in points) * 1.15)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(HERE / "blocking_vs_utilization.png")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.5), dpi=180, sharex=True)
    for variant in ("k1", "k3"):
        trajectories = []
        for load in sorted({load for name, load in grouped if name == variant}):
            selected = []
            for run in grouped[(variant, load)]:
                slow = [link for link in run["phase_link_profile"]["links"]
                        if link["compute_to_compute"] and
                        link["capacity_Bps"] <= 50_000_000 and
                        link_blocking.get((variant, load, run["seed"], link["link_uid"]),
                                          {}).get("messages", 0) > 0]
                if slow:
                    busiest = max(slow, key=lambda item: item["busy_utilization"])
                    count = link_blocking[(variant, load, run["seed"], busiest["link_uid"])]
                    selected.append((busiest["busy_utilization"],
                                     count["blocked_messages"] / count["messages"]))
            if not selected:
                continue
            trajectories.append((load, mean(point[0] for point in selected),
                                 mean(point[1] for point in selected)))
            for utilization, fraction in selected:
                axes[0].scatter(load, utilization, color=colors[variant], alpha=0.25, s=18)
                axes[1].scatter(load, fraction, color=colors[variant], alpha=0.25, s=18)
        for ax, column in zip(axes, (1, 2)):
            ax.plot([point[0] for point in trajectories],
                    [point[column] for point in trajectories],
                    marker="o", label=variant, color=colors[variant])
    axes[0].set_ylabel("Busiest slow link utilization")
    axes[1].set_ylabel("Decode messages delayed by Prompt")
    for ax in axes:
        ax.set_xlabel("Offered load (tokens/s)")
        ax.set_ylim(bottom=0)
        ax.grid(alpha=0.25)
    axes[0].legend()
    fig.tight_layout()
    fig.savefig(HERE / "load_vs_interference.png")
    plt.close(fig)

    comparison_rows = []
    for item in analysis["comparisons"]:
        pair = item["common_completed"]
        comparison_rows.append({
            "variant": item["variant"], "treatment": item["treatment"],
            "load": item["load"], "seed": item["seed"],
            "delta_tpot_p95_s": item["delta_tpot_p95_s"],
            "delta_ttft_p95_s": item["delta_ttft_p95_s"],
            "delta_throughput_tok_s": item["delta_throughput_tok_s"],
            "delta_completion_fraction": item["delta_completion_fraction"],
            "delta_backlog": item["delta_backlog"],
            "common_completed_queries": pair["common_completed_queries"],
            "common_tpot_base_p95_s": pair["tpot_s"]["baseline_p95_s"],
            "common_tpot_treatment_p95_s": pair["tpot_s"]["treatment_p95_s"],
        })
    write_csv(HERE / "interventions.csv", comparison_rows)

    lines = [
        "# V3 慢链路 Prefill/Decode 传输干扰验证",
        "",
        "## 口径",
        "",
        "固定窗口 600 秒，不排空；逐种子配对相同到达轨迹。链路利用率是窗口内发送占用带宽相对容量的积分，不含传播延迟。逐链路 Prompt 字节为窗口内开始发送的消息总量。尾部查询按每查询平均 TPOT 取最高 5%；被阻挡步骤只统计对 TPOT 有贡献的第二个及后续已完成 Decode 步骤。同链路与共享 NIC 的时间交集单独计算，合并占用取时间并集。",
        "",
        "## 基线画像",
        "",
        "| 结构 | 负载 | 种子 | 吞吐 tok/s | TPOT P95 s | 尾部同链路阻挡率 | 全体同链路阻挡率 | 慢链路尾部/全体阻挡率 | 尾部平均阻挡秒/步 | 全体平均阻挡秒/步 | 尾部查询/步数 | 查询级差值 95% CI |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for (variant, load), runs in sorted(grouped.items()):
        for run in sorted(runs, key=lambda item: item["seed"]):
            profile = run["phase_link_profile"]
            test = tail_tests.get(f"{variant}/load{load}/seed{run['seed']}")
            ci = (f"[{fmt(test['bootstrap_95_ci'][0])}, "
                  f"{fmt(test['bootstrap_95_ci'][1])}]" if test else "NA")
            lines.append(f"| {variant} | {load} | {run['seed']} | "
                         f"{fmt(run['output_throughput_tokens_per_s'])} | "
                         f"{fmt(run['tpot_p95_s'])} | "
                         f"{fmt(profile['tail']['same_link_blocked_fraction'])} | "
                         f"{fmt(profile['all']['same_link_blocked_fraction'])} | "
                         f"{fmt(test['slow_tail_step_fraction'])}/"
                         f"{fmt(test['slow_all_step_fraction'])} | "
                         f"{fmt(profile['tail']['same_link_wait_mean_s'])} | "
                         f"{fmt(profile['all']['same_link_wait_mean_s'])} | "
                         f"{profile['tail']['queries']}/{profile['tail']['steps']} | {ci} |")
    lines += ["", "![负载、最忙慢链路利用率与 Decode 阻挡比例](load_vs_interference.png)",
              "", "![逐慢链路发送占用率与 Decode 阻挡比例](blocking_vs_utilization.png)",
              "", "查询级差值是尾部查询与其余查询的平均阻挡步骤比例之差，95% 区间由查询为聚类单位的 2000 次 bootstrap 得到；完整数值见 `tail_query_bootstrap.json`，其中也有仅限慢速计算节点间链路的查询级区间。逐链路 Prompt/Decode 字节、消息数、利用率和等待统计见 `slow_links.csv`；其中逐链路阻挡率以该链路**全部 Decode 消息**为分母，由原始事件重算。同链路、共享 NIC 和交叠时间的消息级分解见 `interference_components.csv`，交叠只在并集内计算一次，另有慢链路 Decode 等待与 Prompt 占用总时长。这些消息级时间不相加冒充 TPOT。每次运行的所有链路与路径统计见 `analysis.json`。不同结构可能选用不同路径，逐链路字节下降不能单独证明复制的纯因果作用。",
              "", "### 慢链路 Decode 等待的 Prompt 重叠（负载 320）", "",
              "| 结构 | 种子 | 慢链路 Decode 等待总秒数 | 与同链路 Prompt 重叠秒数 | 重叠占等待比例 |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for item in interference_rows:
        if item["load"] != 320:
            continue
        wait = item["slow_decode_wait_s"]
        fraction = item["slow_same_link_prompt_s"] / wait if wait else None
        lines.append(f"| {item['variant']} | {item['seed']} | "
                     f"{fmt(wait, 1)} | {fmt(item['slow_same_link_prompt_s'], 1)} | "
                     f"{fmt(fraction)} |")
    lines += ["", "分母仅是已开始发送的 Decode 消息在慢速计算节点间链路上的就绪至开始等待，不包含 GPU 等待或请求尚未就绪的时间；该比例不能解释同等比例的查询 TPOT。",
              "", "## 传输字节干预", "",
              "| 结构 | 干预 | 种子 | ΔTPOT P95 s | ΔTTFT P95 s | Δ吞吐 tok/s | Δ完成率 | Δ积压 | 共同完成查询 | 配对 TPOT P95 原→干预 s |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for item in sorted(comparison_rows, key=lambda row: (row["variant"], row["treatment"], row["seed"])):
        lines.append(f"| {item['variant']} | {item['treatment']} | {item['seed']} | "
                     f"{fmt(item['delta_tpot_p95_s'])} | "
                     f"{fmt(item['delta_ttft_p95_s'])} | "
                     f"{fmt(item['delta_throughput_tok_s'])} | "
                     f"{fmt(item['delta_completion_fraction'])} | "
                     f"{item['delta_backlog']} | "
                     f"{item['common_completed_queries']} | "
                     f"{fmt(item['common_tpot_base_p95_s'])}→"
                     f"{fmt(item['common_tpot_treatment_p95_s'])} |")
    ideal_gap_rows = []
    for seed in (1, 2, 3):
        one = results.get(("k1", "baseline", 320, seed))
        three = results.get(("k3", "baseline", 320, seed))
        one_ideal = results.get(("k1", "ideal_bandwidth", 320, seed))
        three_ideal = results.get(("k3", "ideal_bandwidth", 320, seed))
        if all((one, three, one_ideal, three_ideal)):
            gap = one["tpot_p95_s"] - three["tpot_p95_s"]
            ideal_gap = one_ideal["tpot_p95_s"] - three_ideal["tpot_p95_s"]
            ideal_gap_rows.append((seed, gap, ideal_gap,
                                   (gap - ideal_gap) / gap if gap else None))
    if ideal_gap_rows:
        lines += ["", "### 近似无限带宽下的 k1 与 k3 差距", "",
                  "| 种子 | 原 TPOT P95 差距 s | 理想带宽差距 s | 差距缩小比例 |",
                  "| ---: | ---: | ---: | ---: |"]
        for seed, gap, ideal_gap, fraction in ideal_gap_rows:
            lines.append(f"| {seed} | {fmt(gap)} | {fmt(ideal_gap)} | {fmt(fraction)} |")
        lines += ["", "带宽极大化保留传播延迟，给出串行化通信的系统级反事实；差距缩小比例不是逐请求延迟的精确归因比例。"]
    lines += ["", "完整配对结果、完成率与积压变化见 `interventions.csv`。Prompt/Decode 置零仅作用于计算节点间的激活字节；token 字节、传播延迟、计算、KV 和输入轨迹不变。它改变后续请求时序，因此是系统级因果干预，而非精确的延迟分量扣除。",
              "", "## 慢链路负担与路径", "",
              "| 结构 | 负载 | 种子 | 活跃慢链路 | Prompt 总 MB | 最忙链路 Prompt MB | 最高发送占用率 | 每查询平均慢链路数 |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for (variant, load), runs in sorted(grouped.items()):
        for run in sorted(runs, key=lambda item: item["seed"]):
            item = slow_link_summary(run)
            lines.append(f"| {variant} | {load} | {run['seed']} | "
                         f"{item['active_links']} | {fmt(item['prompt_MB_total'], 1)} | "
                         f"{fmt(item['prompt_MB_max_link'], 1)} | "
                         f"{fmt(item['utilization_max_link'])} | "
                         f"{fmt(item['mean_slow_links_per_query'])} |")
    lines += ["", "总字节和最忙链路字节应分别解释：k3 可在多条路径上传相近总字节，但降低单条慢链路的占用。路径份额、每查询跨链路次数见 `analysis.json`；路径变化与复制结构共同发生，此处不能将全部差值单独归因于复制。",
              "", "## GPU 等待与计算画像", "",
              "| 结构 | 负载 | 种子 | Decode 执行数 | 每执行平均 GPU 等待 s | 每执行平均计算 s |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for (variant, load), runs in sorted(grouped.items()):
        for run in sorted(runs, key=lambda item: item["seed"]):
            gpu = run["phase_link_profile"]["gpu_by_phase"].get("decode", {})
            n = gpu.get("executions", 0)
            lines.append(f"| {variant} | {load} | {run['seed']} | {n} | "
                         f"{fmt(gpu.get('wait_s', 0) / n if n else None)} | "
                         f"{fmt(gpu.get('compute_s', 0) / n if n else None)} |")
    lines += ["", "GPU 数值是逐节点执行事件的均值，不直接相加为查询级 TPOT。",
              "", "## 结论边界", ""]

    from .run import trigger_condition
    triggered, evidence = trigger_condition(analysis, results) if results else (False, "missing runs")
    if triggered:
        burden = []
        for seed in (1, 2, 3):
            k1 = results.get(("k1", "baseline", 320, seed))
            k3 = results.get(("k3", "baseline", 320, seed))
            if k1 and k3:
                one, three = slow_link_summary(k1), slow_link_summary(k3)
                burden.append(three["prompt_MB_max_link"] < one["prompt_MB_max_link"])
        if len(burden) == 3 and all(burden):
            lines.append("600 秒窗口的三个预注册条件均通过：k1 尾部同链路阻挡率高于全体，Prompt 字节置零使 k1 TPOT P95 每种子下降至少 10%，k3 最忙慢链路的 Prompt 字节每种子均低于 k1。此结论是结构与路径选择共同作用的系统级机制证据；是否在更长窗口成立见下列复核。")
        else:
            lines.append("k1 的阻挡富集与 Prompt 字节干预通过门槛，但 k3 最忙慢链路负担下降未在三个种子全部成立，不能将机制写成 V3 收益证据。")
    else:
        lines.append(f"预注册筛选条件未通过或数据尚不完整：{evidence}。不得把 Prompt 传输占用表述为已证实的 V3 尾延迟主因。")
    lines += ["", "## 分块传输与长窗口复核", ""]
    for phase in ("formal", "confirm"):
        chunk = read_optional(HERE / f"chunk_{phase}_analysis.json")
        if chunk:
            lines += [f"### {phase} 分块对照", "",
                      "| 结构 | 种子 | 窗口 s | 原 TPOT P95 s | 分块 TPOT P95 s | 原 TTFT P95 s | 分块 TTFT P95 s |",
                      "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
            for row in chunk["rows"]:
                lines.append(f"| {row['variant']} | {row['seed']} | {row['duration_s']} | "
                             f"{fmt(row['baseline_tpot_p95_s'])} | {fmt(row['chunk_tpot_p95_s'])} | "
                             f"{fmt(row['baseline_ttft_p95_s'])} | {fmt(row['chunk_ttft_p95_s'])} |")
            lines.append("")
    confirm_rows = []
    for variant in ("k1", "k3"):
        for seed in (1, 2, 3):
            folder = HERE / "runs" / "confirm" / "C1_multi" / variant
            base = read_optional(folder / "baseline" / f"load320_seed{seed}.json")
            zero = read_optional(folder / "prompt_zero" / f"load320_seed{seed}.json")
            decode = read_optional(folder / "decode_zero" / f"load320_seed{seed}.json")
            if base and zero and decode:
                confirm_rows.append((variant, seed, base, zero, decode))
    if confirm_rows:
        from .run import paired
        confirm_comparisons = []
        for variant, seed, base, zero, decode in confirm_rows:
            for treatment, target in (("prompt_zero", zero), ("decode_zero", decode)):
                if base["trace_sha256"] != target["trace_sha256"]:
                    raise AssertionError("1800-second paired traces differ")
                matched = paired(base, target)
                confirm_comparisons.append({
                    "variant": variant, "seed": seed, "treatment": treatment,
                    "baseline_tpot_p95_s": base["tpot_p95_s"],
                    "treatment_tpot_p95_s": target["tpot_p95_s"],
                    "baseline_ttft_p95_s": base["ttft_p95_s"],
                    "treatment_ttft_p95_s": target["ttft_p95_s"],
                    "baseline_throughput_tok_s": base["output_throughput_tokens_per_s"],
                    "treatment_throughput_tok_s": target["output_throughput_tokens_per_s"],
                    "baseline_completion_fraction": base["completion_fraction"],
                    "treatment_completion_fraction": target["completion_fraction"],
                    "baseline_backlog": base["backlog_at_window_end"],
                    "treatment_backlog": target["backlog_at_window_end"],
                    "common_completed_queries": matched["common_completed_queries"],
                    "paired_tpot_base_p95_s": matched["tpot_s"]["baseline_p95_s"],
                    "paired_tpot_treatment_p95_s": matched["tpot_s"]["treatment_p95_s"],
                })
        write_csv(HERE / "confirm_interventions.csv", confirm_comparisons)
        lines += ["### 1800 秒字节干预", "",
                  "| 结构 | 种子 | 原 TPOT P95 s | Prompt 零字节 | Decode 零字节 | 尾部同链路阻挡率 | 全体同链路阻挡率 |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for variant, seed, base, zero, decode in confirm_rows:
            lines.append(f"| {variant} | {seed} | {fmt(base['tpot_p95_s'])} | "
                         f"{fmt(zero['tpot_p95_s'])} | {fmt(decode['tpot_p95_s'])} | "
                         f"{fmt(base['phase_link_profile']['tail']['same_link_blocked_fraction'])} | "
                         f"{fmt(base['phase_link_profile']['all']['same_link_blocked_fraction'])} |")
        lines += ["", "长窗口的 TTFT、吞吐、完成率、积压及共同完成查询配对结果见 `confirm_interventions.csv`。", ""]
        chunk_confirm = read_optional(HERE / "chunk_confirm_analysis.json")
        chunk_map = {(row["variant"], row["seed"]): row
                     for row in chunk_confirm["rows"]} if chunk_confirm else {}
        lines += ["### 综合判定", ""]
        for variant in ("k1", "k3"):
            cohort = [(seed, base, zero, decode) for name, seed, base, zero, decode
                      in confirm_rows if name == variant]
            if len(cohort) != 3:
                continue
            prompt_effect = mean((base["tpot_p95_s"] - zero["tpot_p95_s"]) /
                                 base["tpot_p95_s"] for _, base, zero, _ in cohort)
            decode_effect = mean((base["tpot_p95_s"] - decode["tpot_p95_s"]) /
                                 base["tpot_p95_s"] for _, base, _, decode in cohort)
            tail_enriched = all(base["phase_link_profile"]["tail"]["same_link_blocked_fraction"] >
                                base["phase_link_profile"]["all"]["same_link_blocked_fraction"]
                                for _, base, _, _ in cohort)
            chunk_effects = [
                (row["baseline_tpot_p95_s"] - row["chunk_tpot_p95_s"]) /
                row["baseline_tpot_p95_s"]
                for seed, _, _, _ in cohort if (row := chunk_map.get((variant, seed)))]
            chunk_clause = (f"；1 MiB 分块平均下降 {fmt(100 * mean(chunk_effects), 1)}%"
                            if len(chunk_effects) == 3 else "；分块长窗口尚不完整")
            lines.append(f"- {variant}：三个种子尾部阻挡率均高于全体："
                         f"{'是' if tail_enriched else '否'}；Prompt 字节置零 TPOT P95 "
                         f"平均下降 {fmt(100 * prompt_effect, 1)}%，Decode 字节置零 "
                         f"平均下降 {fmt(100 * decode_effect, 1)}%{chunk_clause}。")
        burden_confirm = []
        for seed in (1, 2, 3):
            left = next((base for name, s, base, _, _ in confirm_rows
                         if name == "k1" and s == seed), None)
            right = next((base for name, s, base, _, _ in confirm_rows
                          if name == "k3" and s == seed), None)
            if left and right:
                burden_confirm.append(
                    slow_link_summary(right)["prompt_MB_max_link"] <
                    slow_link_summary(left)["prompt_MB_max_link"])
        if len(burden_confirm) == 3:
            lines.append("- k3 最忙慢链路 Prompt 字节在三个长窗口种子中均低于 k1："
                         f"{'是' if all(burden_confirm) else '否'}。")
        lines += ["", "这些结果支持已开始的 Prompt 激活传输占用慢链路是 k1 Decode 尾延迟的一个重要成因；k3 通过多路径降低单条慢链路负担并缓解该现象。带宽理想化后仍存在结构差距，因此该机制不能解释全部 k1→k3 收益。k3 路由在干预下会变化，且此处没有隔离复制与路径选择的独立因果效应。", ""]
    if not confirm_rows and not read_optional(HERE / "chunk_formal_analysis.json"):
        lines.append("长窗口与分块对照尚未完成。")
    kv_rows = []
    for seed in (1, 2, 3):
        path = HERE / "runs" / "formal" / "C1_single" / "k3" / "baseline" / f"load1100_seed{seed}"
        if path.with_suffix(".json").exists():
            row = read_optional(path.with_suffix(".json"))
            kv_rows.append(f"种子 {seed}：成功，吞吐 "
                           f"{fmt(row['output_throughput_tokens_per_s'])} tok/s，"
                           f"窗口末积压 {row['backlog_at_window_end']}")
        elif path.with_suffix(".failure.json").exists():
            failure = read_optional(path.with_suffix(".failure.json"))
            kv_rows.append(f"种子 {seed}：失效（{failure['error']}）")
    if kv_rows:
        lines += ["", "## 高负载 KV 可行性", "", "；".join(kv_rows) + "。"]
    recovered = []
    for failure_path in (HERE / "runs").rglob("*.failure.json"):
        success_path = failure_path.with_name(failure_path.name.replace(".failure.json", ".json"))
        if success_path.exists():
            failure = read_optional(failure_path)
            recovered.append((failure_path.relative_to(HERE), failure.get("error")))
    if recovered:
        lines += ["", "## 运行异常与重试", ""]
        for path, error in sorted(recovered):
            lines.append(f"- `{path}` 首次失败，随后相同配置成功：`{error}`。失败元数据保留，成功窗口计入分析。")
    lines += ["", "相关先例：[MoLink](https://aclanthology.org/2025.findings-emnlp.957/) 已提出在流水线部署中分块 Prefill 激活传输并调度 Decode；[Sarathi-Serve](https://arxiv.org/abs/2403.02310) 研究计算侧分块预填。这里的分块对照不作为新颖性主张。",
              "", "KV 容量断言属于仿真窗口失效，不折算为零吞吐。请求级分量不直接相加为查询级 TPOT。", ""]
    (HERE / "formal_report.md").write_text("\n".join(lines), encoding="utf-8")
