"""Summarize completed formal600 counterfactual windows without hiding failures."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
INDEX = HERE / "formal600_index.json"
METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s",
           "e2e_p95_s", "completion_fraction")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def fmt(value: float | None, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def key(row: dict) -> tuple[str, str, float]:
    return row["group"], row["treatment"], row["load"]


def summarize() -> tuple[dict, str]:
    index = read(INDEX)
    rows = []
    for item in index["jobs"].values():
        if item["status"] != "passed":
            continue
        row = read(ROOT / item["source"])
        rows.append(row)
    grouped = defaultdict(list)
    for row in rows:
        grouped[key(row)].append(row)
    table = []
    for group_key, values in sorted(grouped.items()):
        group, treatment, load = group_key
        total = sum(1 for item in index["jobs"] if item.startswith(
            f"{group}/{treatment}/load{load:g}/"))
        metrics = {name: mean([row[name] for row in values if row[name] is not None])
                   if any(row[name] is not None for row in values) else None
                   for name in METRICS}
        table.append({"group": group, "treatment": treatment, "load": load,
                      "passed": len(values), "total": total, "metrics": metrics})

    by_key_seed = {(row["group"], row["treatment"], row["load"], row["seed"]): row
                   for row in rows}
    pairs = []
    for group, control, test, load in (
            ("kv", "base", "kv2", 600.),
            ("network", "k1_base", "k1_bw2", 320.),
            ("network", "k1_base", "k1_flat", 320.),
            ("network", "k3_base", "k3_bw2", 320.),
            ("oracle", "fixed", "length_oracle", 320.)):
        matched = [(by_key_seed[(group, control, load, seed)],
                    by_key_seed[(group, test, load, seed)])
                   for seed in (1, 2, 3, 4, 5, 6)
                   if (group, control, load, seed) in by_key_seed and
                   (group, test, load, seed) in by_key_seed]
        if not matched:
            continue
        deltas = {metric: mean(test_row[metric] - control_row[metric]
                               for control_row, test_row in matched
                               if test_row[metric] is not None and control_row[metric] is not None)
                  for metric in ("output_throughput_tokens_per_s", "ttft_p95_s",
                                 "tpot_p95_s", "completion_fraction")}
        pairs.append({"group": group, "control": control, "test": test,
                      "load": load, "paired_seeds": len(matched), "delta": deltas})

    result = {"protocol": index["phase"], "failed_jobs": index["failures"],
              "summary": table, "paired_differences": pairs}
    markdown = ["# V3 Dynamic-Bottleneck Counterfactual Results", "",
                "The table reports means over completed fixed 600 s windows. Failed windows remain listed below and are not converted into latency values.", "",
                "| Group | Treatment | Load | Passed | Output tok/s | TTFT P95 s | TPOT P95 s | Completion |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for item in table:
        metric = item["metrics"]
        markdown.append(
            f"| {item['group']} | {item['treatment']} | {item['load']:g} | "
            f"{item['passed']}/{item['total']} | {fmt(metric['output_throughput_tokens_per_s'])} | "
            f"{fmt(metric['ttft_p95_s'])} | {fmt(metric['tpot_p95_s'])} | "
            f"{fmt(metric['completion_fraction'])} |")
    markdown += ["", "## Paired treatment minus control", "",
                 "Positive throughput/completion deltas favor the treatment; negative latency deltas favor it.", "",
                 "| Group | Comparison | Paired seeds | Δ output tok/s | Δ TTFT P95 s | Δ TPOT P95 s | Δ completion |",
                 "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for item in pairs:
        delta = item["delta"]
        markdown.append(
            f"| {item['group']} | {item['test']} − {item['control']} | {item['paired_seeds']} | "
            f"{fmt(delta['output_throughput_tokens_per_s'])} | {fmt(delta['ttft_p95_s'])} | "
            f"{fmt(delta['tpot_p95_s'])} | {fmt(delta['completion_fraction'])} |")
    markdown += ["", "## Failed windows", ""]
    if index["failures"]:
        markdown.extend(f"- `{job}`: `{error}`" for job, error in index["failures"].items())
    else:
        markdown.append("None.")
    return result, "\n".join(markdown) + "\n"


if __name__ == "__main__":
    result, markdown = summarize()
    (HERE / "formal600_summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write(HERE / "formal600_report.md", markdown)
    print(HERE / "formal600_report.md")
