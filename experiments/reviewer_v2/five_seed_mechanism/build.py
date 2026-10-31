"""Rebuild mechanism and Figure 14 evidence from audited five-seed artifacts."""
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
T4 = 2.7764451051977987

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def load_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))

def put_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def ci(values):
    if len(values) != 5:
        raise RuntimeError("Incomplete five-seed group")
    return mean(values), T4 * stdev(values) / math.sqrt(5)

def metrics(row):
    counts = row["route_counts"]
    routed = sum(counts.values())
    if routed <= 0:
        raise RuntimeError("No routed requests")
    profile = row.get("phase_link_profile", {})
    gpu = profile.get("gpu", {})
    weighted = tokens = executions = singleton = 0
    for item in gpu.values():
        for size, count in item["decode_batch_histogram"].items():
            n = int(size)
            weighted += n * n * count
            tokens += n * count
            executions += count
            singleton += count if n == 1 else 0
    wait = sum(x.get("decode_wait_s", 0) for x in profile.get("links", {}).values())
    output_tokens = row["output_throughput_tokens_per_s"] * row["duration_s"]
    return dict(actual_paths=len(counts), routed_requests=routed,
        max_path_share=max(counts.values()) / routed,
        decode_token_weighted_batch=weighted / tokens if tokens else None,
        singleton_execution_fraction=singleton / executions if executions else None,
        decode_network_wait_per_output_token_s=wait / output_tokens if gpu and output_tokens else None)

def main():
    required = [ROOT / "experiments/v4_paper_seed45/five_seed_reconciled/FINAL_AUDIT.json",
                ROOT / "experiments/v6_completion/session_cost/FINAL_AUDIT.json",
                ROOT / "experiments/v6_completion/scalability/FINAL_AUDIT.json"]
    if not all(read(path)["passed"] for path in required):
        raise RuntimeError("Prerequisite audit failed")
    core_path = ROOT / "experiments/v5_core_supplement/individual.csv"
    session_path = ROOT / "experiments/v6_completion/session_cost/individual.csv"
    scale_path = ROOT / "experiments/v6_completion/scalability/individual.csv"
    core = [r for r in load_csv(core_path) if r["scenario"] == "multi" and r["load"] == "320"
            and r["cell"] in ("RR", "V4")]
    session = [r for r in load_csv(session_path) if r["scenario"] == "multi" and r["load"] == "320"
               and r["variant"] == "no_session"]
    selected = [(r["cell"], r) for r in core] + [("no_session", r) for r in session]
    if len(selected) != 15 or any({int(r["seed"]) for label, r in selected if label == method} != set(range(5))
                              for method in ("RR", "V4", "no_session")):
        raise RuntimeError("Missing one or more five-seed mechanism groups")
    detail, paths, exits, digests = [], [], [], {}
    for method, source_row in selected:
        source = ROOT / source_row["source"]
        digest = sha(source)
        if source_row.get("artifact_sha256") and source_row["artifact_sha256"] != digest:
            raise RuntimeError("Source hash differs: " + str(source))
        row = read(source)
        seed = int(source_row["seed"])
        if row["seed"] != seed or row["trace_sha256"] != source_row["trace_sha256"]:
            raise RuntimeError("Seed or trace mismatch: " + str(source))
        digests[source.relative_to(ROOT).as_posix()] = digest
        detail.append(dict(method=method, seed=seed, **metrics(row), source=source.relative_to(ROOT).as_posix(), sha256=digest))
        if method in ("V4", "no_session"):
            counts = row["route_counts"]
            total = sum(counts.values())
            exit_counts = defaultdict(int)
            for path, count in counts.items():
                exits_key = path.split("-")[-1]
                exit_counts[exits_key] += count
                paths.append(dict(method=method, seed=seed, path=path, requests=count, share=count / total,
                                  routed_requests=total, source=source.relative_to(ROOT).as_posix()))
            for exit_key, count in exit_counts.items():
                exits.append(dict(method=method, seed=seed, exit_gpu=exit_key, requests=count,
                                  share=count / total, routed_requests=total))
    put_csv(HERE / "mechanism_individual.csv", detail)
    put_csv(HERE / "figure14_paths_individual.csv", paths)
    put_csv(HERE / "figure14_exits_individual.csv", exits)
    path_summary = []
    for method in ("V4", "no_session"):
        route_names = sorted({r["path"] for r in paths if r["method"] == method})
        for path in route_names:
            values = [next((float(r["share"]) for r in paths if r["method"] == method and
                        r["seed"] == seed and r["path"] == path), 0.0) for seed in range(5)]
            avg, half = ci(values)
            path_summary.append(dict(method=method, path=path, mean_share=avg, ci95_half=half))
    put_csv(HERE / "figure14_paths_summary.csv", path_summary)
    exit_summary = []
    for method in ("V4", "no_session"):
        for exit_key in sorted({r["exit_gpu"] for r in exits if r["method"] == method}):
            values = [next((float(r["share"]) for r in exits if r["method"] == method
                       and r["seed"] == seed and r["exit_gpu"] == exit_key), 0.0)
                      for seed in range(5)]
            avg, half = ci(values)
            exit_summary.append(dict(method=method, exit_gpu=exit_key,
                                     mean_share=avg, ci95_half=half))
    put_csv(HERE / "figure14_exits_summary.csv", exit_summary)
    scale = load_csv(scale_path)
    if len(scale) != 10 or any({int(r["seed"]) for r in scale if r["size"] == str(size)} != set(range(5))
                              for size in (48, 96)):
        raise RuntimeError("Incomplete scalability data")
    for r in scale:
        if sha(ROOT / r["source"]) != r["source_sha256"]:
            raise RuntimeError("Scalability result hash mismatch")
        digests[r["source"]] = r["source_sha256"]
    lines = ["# 第 7 节五种子机制、图 14 与路由耗时重分析", "",
             "三集群 320 token/s；所有份额先按种子内已路由请求归一化，再对五种子求均值。", "",
             "| 方法 | 实际路径数 | 最大单路径份额 | Decode token 加权批量 | Decode 网络等待/输出 token s |",
             "|---|---:|---:|---:|---:|"]
    for method in ("RR", "V4", "no_session"):
        group = [r for r in detail if r["method"] == method]
        def fmt(name):
            values = [float(r[name]) for r in group if r[name] is not None]
            return ("— (仅 %d/5 有画像)" % len(values)) if len(values) != 5 else "%.4f ± %.4f" % ci(values)
        lines.append(f"| {method} | {fmt('actual_paths')} | {fmt('max_path_share')} | " +
                     f"{fmt('decode_token_weighted_batch')} | {fmt('decode_network_wait_per_output_token_s')} |")
    lines += ["", "图 14 路径平均份额和误差范围见 figure14_paths_summary.csv。", "",
              "| 方法 | 出口 GPU | 路由份额五种子均值 ± 95% CI 半宽 |",
              "|---|---:|---:|"]
    for row in exit_summary:
        lines.append(f"| {row['method']} | {row['exit_gpu']} | "
                     f"{100 * row['mean_share']:.2f}% ± {100 * row['ci95_half']:.2f}pp |")
    lines += ["", "旧稿中的“RCAPS 单路径不超过 18.5%”与五种子最大单路径均值 19.53% 不一致，应改为五种子口径。", "",
              "## 独立路由耗时", "", "48/96 GPU 是另一组合成候选池，部署实际仅 8/11 张 GPU；不是本节三集群部署的路由时间。", "",
              "| 候选池 GPU | 路由调用数（五种子总计） | 窗口内路由均值 µs（五种子均值 ± 95% CI 半宽） |",
              "|---:|---:|---:|"]
    for size in (48, 96):
        group = [r for r in scale if r["size"] == str(size)]
        avg, half = ci([float(r["route_mean_us"]) for r in group])
        lines.append(f"| {size} | {sum(int(r['route_calls']) for r in group)} | {avg:.1f} ± {half:.1f} |")
    lines += ["", "RR 的 seed3/4 无分阶段画像，故不能据仅三种子 Decode/网络指标宣称五种子机制差异。",
              "路径数和负载分布是观测相关性，不独立证明中介因果；网络等待总和也不全是可归因于 Prompt 的延迟。"]
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    for ax, method in zip(axes, ("V4", "no_session")):
        group = sorted((r for r in path_summary if r["method"] == method),
                       key=lambda r: r["mean_share"])
        labels = [r["path"].replace("-", "→") for r in group]
        ax.barh(range(len(group)), [r["mean_share"] for r in group],
                xerr=[r["ci95_half"] for r in group], capsize=2,
                color="#4472C4" if method == "V4" else "#D67F33")
        ax.set_yticks(range(len(group)), labels, fontsize=5)
        ax.set_xlabel("Share of routed requests (five-seed mean ± 95% CI)")
        ax.set_xlim(0, max(0.9, 1.1 * max(r["mean_share"] + r["ci95_half"] for r in group)))
        ax.set_title(method)
    fig.savefig(HERE / "figure14_five_seed.png", dpi=200)
    fig.savefig(HERE / "figure14_five_seed.pdf")
    plt.close(fig)
    audit = dict(passed=True, methods=3, seeds_per_method=5, figure14_methods=2,
        inputs_sha256={str(p.relative_to(ROOT)): sha(p) for p in (core_path, session_path, scale_path, *required)},
        source_sha256=digests, script_sha256=sha(__file__),
        mechanism_sha256=sha(HERE / "mechanism_individual.csv"),
        figure14_paths_sha256=sha(HERE / "figure14_paths_summary.csv"),
        figure14_exits_sha256=sha(HERE / "figure14_exits_summary.csv"),
        figure14_png_sha256=sha(HERE / "figure14_five_seed.png"),
        results_sha256=sha(HERE / "RESULTS_CN.md"))
    (HERE / "FINAL_AUDIT.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("five-seed mechanisms and Figure 14: audit passed")

if __name__ == "__main__":
    main()
