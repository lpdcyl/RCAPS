"""Generate a full-width LaTeX V3 ablation table from audited paired results."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, stdev


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "formal_analysis.json"
CELLS = ("A", "B", "C", "D")
CASES = ("C1_single", "C1_multi")
METRICS = ("output_throughput_tokens_per_s", "ttft_p95_s", "tpot_p95_s")
LABELS = {
    "A": r"A: Single + Static",
    "B": r"B: Multistage + Static",
    "C": r"C: Single + Live M3",
    "D": r"D: Multistage + Live M3 (V3)",
}


def aggregate(source: dict) -> dict:
    if source["failures"]:
        raise ValueError("Cannot make a complete paper table from failed windows")
    output = {}
    for case in CASES:
        seeds = source["paired"][case]
        if set(seeds) != {"0", "1", "2"}:
            raise ValueError(f"Expected paired seeds 0/1/2 for {case}")
        output[case] = {}
        for cell in CELLS:
            output[case][cell] = {}
            for metric in METRICS:
                values = [seeds[str(seed)]["metrics"][cell][metric]
                          for seed in (0, 1, 2)]
                output[case][cell][metric] = (mean(values), stdev(values))
    return output


def _value(aggregated: dict, case: str, cell: str, metric: str) -> str:
    mu, sd = aggregated[case][cell][metric]
    means = {row: aggregated[case][row][metric][0] for row in CELLS}
    best = (max(means.values()) if metric == "output_throughput_tokens_per_s"
            else min(means.values()))
    encoded = f"{mu:.3f} $\\pm$ {sd:.3f}"
    return rf"\textbf{{{encoded}}}" if mu == best else encoded


def tabular(aggregated: dict) -> str:
    lines = [
        r"\begin{table*}[t]",
        r"\caption{Core V3 placement and routing ablation under the C1 GPU pool.}",
        r"\label{tab:v3-core-ablation}",
        r"\centering",
        r"\footnotesize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular}{@{}lccc@{\hspace{0.65em}\vrule\hspace{0.65em}}ccc@{}}",
        r"\toprule",
        r" & \multicolumn{3}{c}{Single cluster (700 token/s)} & "
        r"\multicolumn{3}{c}{Three clusters (320 token/s)} \\",
        r"\cmidrule(lr){2-4}\cmidrule(l){5-7}",
        r"Method & \shortstack{Output\\token/s $\uparrow$} & "
        r"\shortstack{P95 TTFT\\(s) $\downarrow$} & "
        r"\shortstack{P95 TPOT\\(s) $\downarrow$} & "
        r"\shortstack{Output\\token/s $\uparrow$} & "
        r"\shortstack{P95 TTFT\\(s) $\downarrow$} & "
        r"\shortstack{P95 TPOT\\(s) $\downarrow$} \\",
        r"\midrule",
    ]
    for cell in CELLS:
        values = [_value(aggregated, case, cell, metric)
                  for case in CASES for metric in METRICS]
        lines.append(LABELS[cell] + " & " + " & ".join(values) + r" \\")
    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\vspace{2pt}",
        r"\parbox{\textwidth}{\footnotesize Values are mean $\pm$ sample standard "
        r"deviation over paired seeds 0--2 (1800-s windows, zero warmup, "
        r"no tail drain). M1 graph modeling is shared by all rows. The incremental "
        r"sequence is A$\rightarrow$B$\rightarrow$D; C is the orthogonal "
        r"single-boundary/live-routing control. Bold marks the best observed mean "
        r"in a column and does not imply statistical significance. In the three-cluster "
        r"case, B and D retain a single boundary; their differences from A and C "
        r"reflect micro-placement.}",
        r"\end{table*}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    block = tabular(aggregate(source))
    (HERE / "v3_ablation_table.tex").write_text(block, encoding="utf-8")
    standalone = (r"\documentclass[twocolumn]{article}" + "\n" +
                  r"\usepackage{booktabs}" + "\n" +
                  r"\setlength{\textwidth}{7.16in}" + "\n" +
                  r"\setlength{\columnsep}{0.24in}" + "\n" +
                  r"\begin{document}" + "\n" +
                  block + "\n" +
                  r"\end{document}" + "\n")
    (HERE / "v3_ablation_preview.tex").write_text(standalone, encoding="utf-8")
    print(HERE / "v3_ablation_table.tex")


if __name__ == "__main__":
    main()
