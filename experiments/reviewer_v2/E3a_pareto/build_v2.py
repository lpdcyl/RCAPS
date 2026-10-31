"""Frozen-source, five-seed Pareto reanalysis for the RCAPS review supplement."""
import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MANIFEST = HERE / "manifest_v2.json"
SOURCES = {
    "core": "experiments/v5_core_supplement/individual.csv",
    "hr_profile": "experiments/reviewer_v2/HR_profile/individual.csv",
    "session": "experiments/v6_completion/session_cost/individual.csv",
    "weight": "experiments/v6_completion/weight_online/individual.csv",
    "bandwidth": "experiments/v6_completion/bandwidth_threshold/individual.csv",
}
CORE = ("HH", "HHplus", "HR", "RHplus", "RR", "V4")
SESSION = ("batch", "marginal", "cycle", "no_session", "k1", "k1_5", "k3", "k4")
T4 = 2.7764451051977987


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_out(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def register():
    audit = ROOT / "experiments/reviewer_v2/HR_profile/FINAL_AUDIT.json"
    if not json.loads(audit.read_text(encoding="utf-8"))["passed"]:
        raise RuntimeError("Independent HR resource-profile audit did not pass")
    value = {"source_csv_sha256": {k: sha(ROOT / v) for k, v in SOURCES.items()},
             "script_sha256": sha(__file__), "loads": {"single": 700, "multi": 320},
             "core": CORE, "session": SESSION, "single_weight": ("w0_high", "w2_low"),
             "multi_bandwidth": ("canonical_chunk", "canonical_nochunk"),
             "ci": "two-sided 95% t, df=4; minimize both means",
             "revision": "HR profile seed0-4 independent remeasurement; old core HR untouched",
             "previous_manifest_sha256": sha(HERE / "manifest.json"),
             "profile_audit_sha256": sha(audit),
             "amendment_sha256": sha(HERE / "AMENDMENT_2_CN.md")}
    if MANIFEST.exists():
        if json.loads(MANIFEST.read_text(encoding="utf-8")) != json.loads(json.dumps(value)):
            raise RuntimeError("Frozen E3a inputs or script changed")
    else:
        json_out(MANIFEST, value)
    return value


def load(name):
    with (ROOT / SOURCES[name]).open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def source_rows():
    selected = defaultdict(list)
    for r in load("core"):
        if (r["scenario"], int(r["load"])) in (("single", 700), ("multi", 320)) and r["cell"] in CORE:
            if r["cell"] == "HR":
                continue
            selected[(r["scenario"], "core:" + r["cell"])].append(r)
    for r in load("hr_profile"):
        if (r["scenario"], int(r["load"])) in (("single", 700), ("multi", 320)) and r["cell"] == "HR":
            selected[(r["scenario"], "core:HR")].append(r)
    for r in load("session"):
        if (r["scenario"], int(r["load"])) in (("single", 700), ("multi", 320)) and r["variant"] in SESSION:
            selected[(r["scenario"], "session:" + r["variant"])].append(r)
    for r in load("weight"):
        if (r["scenario"], int(r["load"])) == ("single", 700) and r["label"] in ("w0_high", "w2_low"):
            selected[("single", "weight:" + r["label"])].append(r)
    for r in load("bandwidth"):
        if r["condition"] == "B12p5_T50" and r["cell"] in ("canonical_chunk", "canonical_nochunk"):
            selected[("multi", "bandwidth:" + r["cell"])].append(r)
    return selected


def csv_out(name, rows):
    with (HERE / name).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build():
    register()
    previous = ROOT / "experiments/v4_paper_seed45/retry_env"
    if json.loads((previous / "index.json").read_text(encoding="utf-8"))["status"] != "terminal":
        raise RuntimeError("Prior V4 replay is still running")
    if not json.loads((previous / "FINAL_AUDIT.json").read_text(encoding="utf-8"))["passed"]:
        raise RuntimeError("Prior V4 replay audit did not pass")
    selected = source_rows()
    if len(selected) != 32:
        raise RuntimeError(f"Expected 32 points; found {len(selected)}")
    traces = defaultdict(set)
    individual, summary = [], []
    for (scenario, label), rows in sorted(selected.items()):
        if len(rows) != 5 or {int(r["seed"]) for r in rows} != set(range(5)):
            raise RuntimeError(f"Missing seed: {scenario}/{label}")
        for r in rows:
            if r.get("status", "completed") != "completed":
                raise RuntimeError(f"Failed source: {scenario}/{label}/seed{r['seed']}")
            digest = sha(ROOT / r["source"])
            expected = r.get("artifact_sha256") or r.get("source_sha256")
            if expected and digest != expected:
                raise RuntimeError(f"Source hash changed: {r['source']}")
            traces[(scenario, int(r["seed"]))].add(r["trace_sha256"])
            individual.append({"scenario": scenario, "load": 700 if scenario == "single" else 320,
                               "point": label, "seed": int(r["seed"]), "tpot_p95_s": r["tpot_p95_s"],
                               "gpu_seconds_per_output_token": r["gpu_seconds_per_output_token"],
                               "trace_sha256": r["trace_sha256"], "source": r["source"], "source_sha256": digest})
        tpot = [float(r["tpot_p95_s"]) for r in rows]
        work = [float(r["gpu_seconds_per_output_token"]) for r in rows]
        summary.append({"scenario": scenario, "load": 700 if scenario == "single" else 320,
                        "point": label, "n": 5, "tpot_mean_s": mean(tpot),
                        "tpot_ci95_half_s": T4 * stdev(tpot) / math.sqrt(5),
                        "gpu_s_per_token_mean": mean(work),
                        "gpu_s_per_token_ci95_half": T4 * stdev(work) / math.sqrt(5)})
    if len(traces) != 10 or any(len(v) != 1 for v in traces.values()):
        raise RuntimeError("Seed-matched traces are not identical")
    for r in summary:
        rivals = (x for x in summary if x is not r and x["scenario"] == r["scenario"])
        r["pareto_frontier"] = not any(x["tpot_mean_s"] <= r["tpot_mean_s"] and
            x["gpu_s_per_token_mean"] <= r["gpu_s_per_token_mean"] and
            (x["tpot_mean_s"] < r["tpot_mean_s"] or x["gpu_s_per_token_mean"] < r["gpu_s_per_token_mean"])
            for x in rivals)
    csv_out("individual.csv", individual)
    csv_out("summary.csv", summary)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    for ax, scenario in zip(axes, ("single", "multi")):
        subset = [r for r in summary if r["scenario"] == scenario]
        for r in subset:
            color = "#c00000" if r["pareto_frontier"] else "#4472c4"
            ax.errorbar(r["gpu_s_per_token_mean"], r["tpot_mean_s"],
                        xerr=r["gpu_s_per_token_ci95_half"], yerr=r["tpot_ci95_half_s"],
                        fmt="o", color=color, markersize=4, capsize=2)
            ax.annotate(r["point"].split(":", 1)[1], (r["gpu_s_per_token_mean"], r["tpot_mean_s"]),
                        xytext=(4, 4), textcoords="offset points", fontsize=6)
        front = sorted((r for r in subset if r["pareto_frontier"]), key=lambda r: r["gpu_s_per_token_mean"])
        ax.plot([r["gpu_s_per_token_mean"] for r in front], [r["tpot_mean_s"] for r in front],
                color="#c00000", alpha=.55, linewidth=1)
        ax.set_title("Single cluster, 700 token/s" if scenario == "single" else "Three clusters, 320 token/s")
        ax.set_xlabel("GPU busy seconds / output token")
        ax.set_ylabel("P95 TPOT (s)")
        ax.grid(alpha=.2)
    fig.savefig(HERE / "pareto.png", dpi=240)
    fig.savefig(HERE / "pareto.pdf")
    plt.close(fig)
    lines = ["# E3a：P95 TPOT 与 GPU 工作量 Pareto 重分析", "",
             "两轴均为五种子均值；误差棒为 t(4) 95% CI 半宽。范围仅为两个模拟负载点。", "",
             "| 拓扑 | 方法 | TPOT s [95% CI 半宽] | GPU s/token [95% CI 半宽] | 均值前沿 |",
             "|---|---|---:|---:|---|"]
    for r in summary:
        lines.append(f"| {r['scenario']} | {r['point']} | {r['tpot_mean_s']:.4f} ± {r['tpot_ci95_half_s']:.4f} | {r['gpu_s_per_token_mean']:.4f} ± {r['gpu_s_per_token_ci95_half']:.4f} | {'是' if r['pareto_frontier'] else '否'} |")
    lines += ["", "## 论文可用表述", "",
              "在单集群 700 和三集群 320 token/s 的五种子模拟结果中，P95 TPOT 与每输出 token GPU 忙碌秒呈现不同权衡点。",
              "图中红色点按两轴均值定义 Pareto 前沿，误差棒反映种子间不确定性。",
              "这些结果不能说明跨负载普适优势或真实 GPU 集群效率。"]
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_out(HERE / "FINAL_AUDIT.json", {"passed": True, "points": len(summary), "seeds_per_point": 5,
             "trace_groups": len(traces), "manifest_sha256": sha(MANIFEST),
             "individual_sha256": sha(HERE / "individual.csv"), "summary_sha256": sha(HERE / "summary.csv"),
             "figure_sha256": sha(HERE / "pareto.png"), "results_sha256": sha(HERE / "RESULTS_CN.md")})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    if args.register:
        register()
    elif args.build:
        build()
    else:
        parser.error("choose --register or --build")
