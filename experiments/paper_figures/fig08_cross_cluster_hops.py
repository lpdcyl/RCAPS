"""Measured request-path inter-cluster hop counts in the three-cluster run."""

import ast
from collections import Counter
import re

import matplotlib.pyplot as plt
import numpy as np

from common import HELIX, OURS, ROOT, official, save


def cluster_map():
    raw = (ROOT / "artifact_evaluation/distributed_clusters/config/3cluster24.ini").read_text()
    groups = [ast.literal_eval(match.group(1)) for match in
              re.finditer(r"^#\s+partition-\d+:\s+(\[.*\])$", raw, re.MULTILINE)]
    assert [len(x) for x in groups] == [4, 10, 10]
    return {node: index for index, group in enumerate(groups)
            for node in range(sum(map(len, groups[:index])),
                              sum(map(len, groups[:index + 1])))}


def histogram(data, membership):
    counts = Counter()
    for route, freq in data["route_counts"].items():
        nodes = [int(uid) - 2 for uid in route.split("-")]
        regions = [membership[n] for n in nodes]
        counts[sum(a != b for a, b in zip(regions, regions[1:]))] += freq
    assert sum(counts.values()) == data["first_tokens_in_window"]
    return counts


def main():
    membership = cluster_map()
    baseline = histogram(official("multi", "helix"), membership)
    candidate = histogram(official("multi", "integrated"), membership)
    keys = sorted(set(baseline) | set(candidate))
    fig, ax = plt.subplots(figsize=(3.45, 2.65))
    x = np.arange(len(keys))
    total_a, total_b = sum(baseline.values()), sum(candidate.values())
    ax.bar(x - 0.17, [100 * baseline[k] / total_a for k in keys], 0.34,
           label="Helix", color=HELIX)
    ax.bar(x + 0.17, [100 * candidate[k] / total_b for k in keys], 0.34,
           label="RCAPS", color=OURS, hatch="//", edgecolor="white", linewidth=0.4)
    ax.set_xticks(x, keys)
    ax.set_xlabel("Cross-cluster hops per routed request")
    ax.set_ylabel("Requests (%)")
    ax.set_ylim(0, 110)
    ax.legend(frameon=False, loc="upper right")
    ax.grid(axis="y", alpha=0.16, linewidth=0.5)
    ax.set_axisbelow(True)
    fig.subplots_adjust(left=0.17, right=0.98, bottom=0.23, top=0.95)
    save(fig, "fig08_cross_cluster_hops")


if __name__ == "__main__":
    main()
