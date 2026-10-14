"""Audit the paired 350/160-token/s experiment and write its compact report."""

from __future__ import annotations

import hashlib
import json
from configparser import ConfigParser
from pathlib import Path
from statistics import mean, stdev

from benchmarks.compare import MATCH_FIELDS, common_cohort
from benchmarks.layout import scenario as physical_scenario
from benchmarks.registry import METHODS


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RUNS = {"single": HERE / "common_low_formal",
        "multi": HERE / "common_low_formal_multi"}
METHODS_IN_TABLE = ("rcaps_v2", "helix", "swarm", "separate")
SEEDS = (0, 1, 2)
LOADS = {"single": 350.0, "multi": 160.0}
METRICS = {
    "output_throughput_tokens_per_s": ("吞吐 token/s ↑", "higher", 1),
    "ttft_p95_s": ("P95 TTFT s ↓", "lower", 1),
    "tpot_p95_s": ("P95 TPOT s ↓", "lower", 1),
    "completion_fraction": ("完成率 % ↑", "higher", 100),
    "backlog_at_window_end": ("末端积压 ↓", "lower", 1),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_sp_physical(scenario: str) -> dict[str, list[int]]:
    """Verify the three SP subclusters partition the original 24-GPU graph."""
    full = ConfigParser()
    full.read(physical_scenario(scenario)[0])
    manifest = json.loads((HERE / "layouts" / f"sp_{scenario}.json").read_text(
        encoding="utf-8"))
    mapping = {}
    for group, gpu_type in (("a100", "A100"), ("l4", "L4"), ("t4", "T4")):
        entry = manifest["groups"][group]
        sub = ConfigParser()
        sub.read(ROOT / entry["physical"]["path"])
        ids = [index for index in range(24)
               if full[f"ComputeNode-{index}"]["type"] == gpu_type]
        if len(ids) != int(sub["NodeNames"]["total_compute_nodes"]):
            raise ValueError(f"{scenario}/{group}: device count mismatch")
        for local, actual in enumerate(ids):
            for left, right in ((f"Link-source-{local}", f"Link-source-{actual}"),
                                (f"Link-{local}-sink", f"Link-{actual}-sink")):
                for field in ("bandwidth", "latency"):
                    if sub[left][field] != full[right][field]:
                        raise ValueError(f"{scenario}/{group}: {left}/{field} mismatch")
            for later in range(local + 1, len(ids)):
                for field in ("bandwidth", "latency"):
                    if sub[f"Link-{local}-{later}"][field] != full[
                            f"Link-{actual}-{ids[later]}"][field]:
                        raise ValueError(f"{scenario}/{group}: internal {field} mismatch")
        mapping[group] = ids
    if sorted(index for ids in mapping.values() for index in ids) != list(range(24)):
        raise ValueError(f"{scenario}: SP does not partition all 24 GPUs")
    return mapping


def read(scenario: str, seed: int, method: str) -> tuple[dict, Path]:
    path = RUNS[scenario] / scenario / f"seed{seed}" / f"{method}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    solution, cluster = METHODS[method].layout(scenario, ROOT)
    expected = {
        "system": method, "scenario": scenario, "seed": seed,
        "offered_tokens_per_s": LOADS[scenario], "duration_s": 1800,
        "warmup_s": 0, "evaluation_protocol": "fixed_window_no_tail_drain",
        "query_samples_schema": 1, "solution_sha256": digest(solution),
        "sim_cluster_sha256": digest(cluster),
    }
    for field, value in expected.items():
        if record.get(field) != value:
            raise ValueError(f"{path}: unexpected {field}")
    if len(record.get("query_samples", {})) != record["arrivals"]:
        raise ValueError(f"{path}: missing query identities")
    return record, path


def summary(values: list[float]) -> dict:
    return {"mean": mean(values), "sample_sd": stdev(values),
            "by_seed": dict(zip(SEEDS, values))}


def fmt(item: dict | None, decimals: int = 3) -> str:
    if item is None:
        return "—"
    return f"{item['mean']:.{decimals}f} ± {item['sample_sd']:.{decimals}f}"


def main() -> None:
    report = {"protocol": "70B, 24 GPUs, common 350/160 offered token/s, "
                          "seeds 0/1/2, 1800 s, zero warmup, no tail drain",
              "source_sha256": {}, "scenarios": {}}
    lines = ["# 四方法共同负载实验：完整窗口核查", "",
             "70B；单集群 350、三集群 160 提供 token/s；种子 0/1/2；"
             "1800 秒、零预热、不排空尾部。四方法共用同一请求轨迹。"
             "每格为三个种子各自完整窗口指标的均值 ± 样本标准差。", "",
             "这组负载取自原 Helix artifact 的 Swarm 设置，在查看本组结果前固定。"
             "它是四方法共同可运行负载的补充实验；700/320 token/s 的 V2–Helix 主表"
             "仍单独报告，两个负载档的数值不直接相减。", ""]
    for scenario in LOADS:
        report.setdefault("sp_physical_device_mapping", {})[scenario] = (
            audit_sp_physical(scenario))
        rows = {method: [] for method in METHODS_IN_TABLE}
        for seed in SEEDS:
            for method in METHODS_IN_TABLE:
                record, path = read(scenario, seed, method)
                rows[method].append(record)
                report["source_sha256"][path.relative_to(ROOT).as_posix()] = digest(path)
            reference = rows["helix"][-1]
            for method in METHODS_IN_TABLE:
                record = rows[method][-1]
                if any(record.get(field) != reference.get(field)
                       for field in MATCH_FIELDS):
                    raise ValueError(f"{scenario}/seed{seed}/{method}: trace mismatch")
                common_cohort(record, reference)
        scene = {"methods": {}, "v2_paired": {}}
        for method, records in rows.items():
            scene["methods"][method] = {
                key: summary([record[key] * factor for record in records])
                for key, (_, _, factor) in METRICS.items()}
        for method in METHODS_IN_TABLE[1:]:
            gains = {}
            for key, (_, direction, _) in METRICS.items():
                values = []
                for a, b in zip(rows["rcaps_v2"], rows[method]):
                    if b[key] is None or a[key] is None:
                        raise ValueError(f"{scenario}/{method}: invalid {key}")
                    if b[key] <= 0:
                        values = None
                        break
                    values.append(100 * (a[key] / b[key] - 1 if direction == "higher"
                                         else 1 - a[key] / b[key]))
                gains[key] = summary(values) if values is not None else None
            cohorts = [common_cohort(a, b) for a, b in
                       zip(rows["rcaps_v2"], rows[method])]
            scene["v2_paired"][method] = {"improvement_percent": gains,
                                           "common_cohort_by_seed": cohorts}
        report["scenarios"][scenario] = scene
        scene["trace_sha256_by_seed"] = {
            seed: rows["helix"][seed]["trace_sha256"] for seed in SEEDS}
        lines += [f"## {'单集群' if scenario == 'single' else '三集群'}", "",
                  "| 方法 | " + " | ".join(label for label, _, _ in METRICS.values()) + " |",
                  "| --- |" + " ---: |" * len(METRICS)]
        for method in METHODS_IN_TABLE:
            lines.append("| " + method + " | " + " | ".join(
                fmt(scene["methods"][method][key], 1 if key == "backlog_at_window_end" else 3)
                for key in METRICS) + " |")
        lines += ["", "相对各基线的 V2 配对改善（均值 ± 样本标准差）：", "",
                  "| 基线 | 吞吐 % ↑ | P95 TTFT % ↓ | P95 TPOT % ↓ | 完成率 % ↑ | 积压 % ↓ |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for method in METHODS_IN_TABLE[1:]:
            lines.append("| " + method + " | " + " | ".join(
                fmt(scene["v2_paired"][method]["improvement_percent"][key], 2)
                for key in METRICS) + " |")
        lines.append("")
    lines += ["请求身份、布局哈希和协议字段逐种子校验；SP 的三个物理子图合起来"
              "恰好覆盖同一套 24 GPU，链路参数逐边核对。配对百分比先按同种子计算，"
              "再取均值与样本标准差；三个种子不用于显著性推断。"
              "SP 使用按原 artifact 子集群负载比例确定的请求数分配，"
              "不根据目标输出长度作分配决策。单集群 V2 与 SP 的吞吐相当，"
              "不能声称 V2 在这一档对所有基线均有吞吐增益；V2 的两项 P95 延迟较低。", ""]
    (HERE / "common_low_summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (HERE / "COMMON_LOW_SUMMARY_CN.md").write_text(
        "\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
