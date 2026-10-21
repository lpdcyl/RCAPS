"""Run the preregistered T0.6 offline checks without invoking the simulator."""

from __future__ import annotations

import ast
import csv
import gzip
import hashlib
import json
import math
import os
from collections import defaultdict
from configparser import ConfigParser
from pathlib import Path
from statistics import mean, median

from rcaps.v3 import placement
from rcaps.v3.topology import TopologyModel
from simulator.event_simulator.utils import MB, MilliSec, Sec, gbps, kbps, mbps
from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder

from .model import LinkMoments, effective_bandwidth, from_trace_shares, path_weighted_wait


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PHASE = ROOT / "experiments/v3_phase_link_diagnosis"
COUNTER = ROOT / "experiments/v3_dynamic_bottleneck_counterfactuals"
SEARCH = ROOT / "experiments/v3_search_sensitivity"
SELECTION = ROOT / "experiments/v3_m2_linear_proxy"
UNITS = {"kbps": kbps, "mbps": mbps, "gbps": gbps, "MB": MB,
         "MilliSec": MilliSec, "Sec": Sec}


class Sources:
    def __init__(self):
        self.files: dict[str, str] = {}

    def mark(self, path: Path) -> Path:
        path = path.resolve()
        relative = path.relative_to(ROOT).as_posix()
        if relative not in self.files:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                    digest.update(chunk)
            self.files[relative] = digest.hexdigest()
        return path

    def json(self, path: Path):
        return json.loads(self.mark(path).read_text(encoding="utf-8"))


def scalar(text: str) -> float:
    return float(eval(text, {"__builtins__": {}}, UNITS))


def config(path: Path, sources: Sources) -> ConfigParser:
    parser = ConfigParser()
    if not parser.read(sources.mark(path), encoding="utf-8"):
        raise FileNotFoundError(path)
    return parser


def node_name(uid: int) -> str:
    return f"compute_node_{uid}"


def link_hardware(sim_cluster: Path, sources: Sources) -> dict[tuple[int, int], dict]:
    parser = config(sim_cluster, sources)
    result = {}
    for section in ast.literal_eval(parser["Links"]["names"]):
        item = parser[section]
        left, right = item["in"], item["out"]
        if not (left.startswith("compute_node_") and right.startswith("compute_node_")):
            continue
        from_uid, to_uid = int(left.removeprefix("compute_node_")), int(right.removeprefix("compute_node_"))
        capacity = scalar(item["bandwidth"])
        sender = scalar(parser[left]["outbound_nic_speed"])
        receiver = scalar(parser[right]["inbound_nic_speed"])
        result[from_uid, to_uid] = {
            "link_Bps": capacity, "sender_nic_Bps": sender,
            "receiver_nic_Bps": receiver,
            "effective_Bps": effective_bandwidth(capacity, sender, receiver),
        }
    return result


def averages(values: list[float]) -> dict:
    if not values:
        raise ValueError("Empty statistic")
    return {"count": len(values), "mean": mean(values)}


def rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    result = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        midpoint = (start + 1 + end) / 2
        for index in order[start:end]:
            result[index] = midpoint
        start = end
    return result


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    rx, ry = rank(xs), rank(ys)
    mx, my = mean(rx), mean(ry)
    cov = sum((x-mx)*(y-my) for x, y in zip(rx, ry))
    vx = sum((x-mx)**2 for x in rx)
    vy = sum((y-my)**2 for y in ry)
    return cov / math.sqrt(vx*vy) if vx and vy else None


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Empty quantile")
    position = (len(ordered)-1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper]-ordered[lower]) * (position-lower)


def message_stats(path: Path, sources: Sources) -> dict[int, dict[str, list[float]]]:
    """One streaming pass per baseline; exact byte first/second moments."""
    sources.mark(path)
    totals = defaultdict(lambda: {"prompt": [0, 0.0, 0.0],
                                  "decode": [0, 0.0, 0.0]})
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if '"event":"start"' not in line[:48]:
                continue
            try:
                event = json.loads(line)
            except (SystemError, json.JSONDecodeError) as error:
                raise RuntimeError(f"Cannot parse {path}:{line_number}: {error}") from error
            if event.get("event") != "start" or event.get("phase") not in ("prompt", "decode"):
                continue
            item = totals[int(event["link_uid"])][event["phase"]]
            size = float(event["physical_bytes"])
            item[0] += 1
            item[1] += size
            item[2] += size * size
    return totals


def cv2_from_queries(run: dict) -> float:
    lengths = [sample["input_tokens"] for sample in run["query_samples"].values()]
    if not lengths:
        raise ValueError("No query_samples for fallback CV")
    avg = mean(lengths)
    return mean([(value-avg)**2 for value in lengths]) / (avg*avg) if avg else 0.0


def moments_for_link(link: dict, hardware: dict, duration: int, stats: dict | None,
                     cv2: float) -> tuple[LinkMoments, str]:
    bandwidth = hardware["effective_Bps"]
    if stats is not None:
        p, d = stats["prompt"], stats["decode"]
        if p[0] != link["prompt_messages"] or d[0] != link["decode_messages"]:
            raise ValueError(f"Event count differs from profile for link {link['link_uid']}: "
                             f"{p[0]}/{d[0]} versus {link['prompt_messages']}/{link['decode_messages']}")
        m = LinkMoments(p[0]/duration, d[0]/duration,
                        p[1]/p[0]/bandwidth if p[0] else 0.0,
                        d[1]/d[0]/bandwidth if d[0] else 0.0,
                        p[2]/p[0]/bandwidth**2 if p[0] else 0.0,
                        d[2]/d[0]/bandwidth**2 if d[0] else 0.0)
        return m, "exact_events"
    p_count, d_count = link["prompt_messages"], link["decode_messages"]
    p_mean = link["prompt_bytes"] / p_count / bandwidth if p_count else 0.0
    d_mean = link["decode_bytes"] / d_count / bandwidth if d_count else 0.0
    return LinkMoments(p_count/duration, d_count/duration, p_mean, d_mean,
                       p_mean*p_mean*(1+cv2), d_mean*d_mean*(1+cv2)), "query_input_cv_fallback"


def baseline_data(sources: Sources):
    csv_path = sources.mark(PHASE / "slow_links.csv")
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        slow_rows = list(csv.DictReader(stream))
    groups = defaultdict(list)
    for row in slow_rows:
        groups[row["variant"], int(row["load"]), int(row["seed"])].append(row)
    all_runs, a_rows = {}, []
    for key in sorted(groups):
        variant, load, seed = key
        path = PHASE / f"runs/formal/C1_multi/{variant}/baseline/load{load}_seed{seed}.json"
        run = sources.json(path)
        duration = int(run["duration_s"])
        if duration != 600:
            raise ValueError(f"Unexpected baseline duration: {path}")
        hardware = link_hardware(Path(run["sim_cluster"]), sources)
        events_path = path.with_suffix(".jsonl.gz")
        exact = message_stats(events_path, sources) if events_path.is_file() else None
        fallback_cv2 = cv2_from_queries(run) if exact is None else 0.0
        records = {}
        for link in run["phase_link_profile"]["links"]:
            if not link["compute_to_compute"]:
                continue
            edge = (link["from"], link["to"])
            hw = hardware[edge]
            if not math.isclose(hw["link_Bps"], link["capacity_Bps"], rel_tol=1e-12):
                raise ValueError(f"Profile capacity differs from link config: {path}, {edge}")
            stats = (exact.get(link["link_uid"],
                               {"prompt": [0, 0.0, 0.0], "decode": [0, 0.0, 0.0]})
                     if exact is not None else None)
            if exact is not None and stats["prompt"][0] + stats["decode"][0] == 0 and \
                    (link["prompt_messages"] or link["decode_messages"]):
                raise ValueError(f"Missing events for active link {link['link_uid']}")
            moments, method = moments_for_link(link, hw, duration, stats, fallback_cv2)
            records[int(link["link_uid"])] = {"profile": link, "hardware": hw,
                                               "moments": moments, "method": method}
        for row in groups[key]:
            uid = int(row["link_uid"])
            record = records[uid]
            m = record["moments"]
            for field, expected in (("prompt_messages", m.lambda_prompt*duration),
                                    ("decode_messages", m.lambda_decode*duration)):
                if int(row[field]) != round(expected):
                    raise ValueError(f"slow_links.csv differs from baseline profile: {key}/{uid}/{field}")
            if not math.isclose(float(row["capacity_MBps"])*1_000_000,
                                record["hardware"]["link_Bps"], rel_tol=1e-10):
                raise ValueError(f"slow_links.csv capacity differs: {key}/{uid}")
            predicted = m.wait_decode_s
            observed = (float(row["decode_wait_mean_s"])
                        if row["decode_wait_mean_s"] else None)
            if observed is None and (int(row["prompt_messages"]) != 0 or
                                     int(row["decode_messages"]) != 0):
                raise ValueError(f"Missing observed wait on an active link: {key}/{uid}")
            a_rows.append({"variant": variant, "load": load, "seed": seed,
                           "link_uid": uid, "from": int(row["from"]), "to": int(row["to"]),
                           "capacity_MBps": float(row["capacity_MBps"]),
                           "effective_MBps": record["hardware"]["effective_Bps"]/1e6,
                           "prompt_messages": int(row["prompt_messages"]),
                           "decode_messages": int(row["decode_messages"]),
                           "lambda_prompt": m.lambda_prompt, "lambda_decode": m.lambda_decode,
                           "mean_prompt_s": m.mean_prompt_s,
                           "mean_decode_s": m.mean_decode_s,
                           "second_prompt_s2": m.second_prompt_s2,
                           "second_decode_s2": m.second_decode_s2,
                           "rho_decode": m.rho_decode, "predicted_wait_s": predicted,
                           "observed_wait_s": observed, "es2_method": record["method"],
                           "saturated": m.rho_decode >= 1,
                           "rank_eligible": observed is not None and m.rho_decode < 1,
                           "missing_observed_reason": ("no_messages" if observed is None else None)})
        all_runs[key] = {"run": run, "links": records, "source": path.relative_to(ROOT).as_posix()}
    return all_runs, a_rows


def check_a(rows: list[dict]) -> dict:
    output = {"rows": rows, "rankings": {}, "saturated_count": sum(r["saturated"] for r in rows),
              "no_observed_wait_count": sum(r["observed_wait_s"] is None for r in rows),
              "es2_methods": {method: sum(r["es2_method"] == method for r in rows)
                              for method in sorted({r["es2_method"] for r in rows})}}
    for variant in ("k1", "k3", "combined"):
        subset = [r for r in rows if r["rank_eligible"] and
                  (variant == "combined" or r["variant"] == variant)]
        ratios = [r["predicted_wait_s"]/r["observed_wait_s"] for r in subset
                  if r["observed_wait_s"] > 0]
        output["rankings"][variant] = {
            "n": len(subset),
            "spearman": spearman([r["predicted_wait_s"] for r in subset],
                                 [r["observed_wait_s"] for r in subset]),
            "predicted_to_observed_ratio_median": median(ratios) if ratios else None,
            "predicted_to_observed_ratio_q1": quantile(ratios, 0.25) if ratios else None,
            "predicted_to_observed_ratio_q3": quantile(ratios, 0.75) if ratios else None,
            "ratio_n": len(ratios),
        }
    return output


def route_edge_shares(run: dict) -> dict[tuple[int, int], float]:
    routes = run["route_counts"]
    count = sum(routes.values())
    if count <= 0:
        raise ValueError("No baseline routes")
    shares = defaultdict(float)
    for route, amount in routes.items():
        nodes = [int(node) for node in route.split("-")]
        for edge in zip(nodes, nodes[1:]):
            shares[edge] += amount / count
    return dict(shares)


def modified_wait(m: LinkMoments, baseline_bandwidth: float,
                  replacement_bandwidth: float, treatment: str) -> float:
    if treatment == "ideal_bandwidth":
        return 0.0
    if treatment == "prompt_zero":
        return LinkMoments(0, m.lambda_decode, 0, m.mean_decode_s,
                           0, m.second_decode_s2).wait_decode_s
    if treatment == "bandwidth_double":
        factor = baseline_bandwidth / replacement_bandwidth
        return LinkMoments(m.lambda_prompt, m.lambda_decode,
                           m.mean_prompt_s*factor, m.mean_decode_s*factor,
                           m.second_prompt_s2*factor*factor,
                           m.second_decode_s2*factor*factor).wait_decode_s
    if treatment == "baseline":
        return m.wait_decode_s
    raise ValueError(treatment)


def baseline_path_cost(baseline: dict, treatment: str) -> float:
    shares = route_edge_shares(baseline["run"])
    edges = {(record["profile"]["from"], record["profile"]["to"]): record
             for record in baseline["links"].values()}
    total = 0.0
    for edge, share in shares.items():
        record = edges[edge]
        hw = record["hardware"]
        new_bandwidth = effective_bandwidth(
            hw["link_Bps"]*2 if treatment == "bandwidth_double" else hw["link_Bps"],
            hw["sender_nic_Bps"], hw["receiver_nic_Bps"])
        wait = modified_wait(record["moments"], hw["effective_Bps"],
                             new_bandwidth, treatment)
        total += share * wait
    return total


def direction(delta: float, tolerance: float = 1e-12) -> str:
    return "down" if delta < -tolerance else "up" if delta > tolerance else "flat"


def check_b(all_runs: dict, sources: Sources) -> dict:
    sources.mark(COUNTER / "formal600_report.md")
    rows = []
    for treatment in ("bandwidth_double", "ideal_bandwidth", "prompt_zero"):
        for variant in ("k1", "k3"):
            for seed in (1, 2, 3):
                baseline = all_runs[variant, 320, seed]
                if treatment == "bandwidth_double":
                    base_path = COUNTER / f"runs/formal600/network/{variant}_base/load320_seed{seed}.json"
                    treated_path = COUNTER / f"runs/formal600/network/{variant}_bw2/load320_seed{seed}.json"
                    control = sources.json(base_path)
                    if control["trace_sha256"] != baseline["run"]["trace_sha256"] or \
                            control["solution_sha256"] != baseline["run"]["solution_sha256"]:
                        raise ValueError(f"Bandwidth control does not match baseline: {base_path}")
                    observed_base = control["tpot_p95_s"]
                else:
                    treated_path = PHASE / f"runs/formal/C1_multi/{variant}/{treatment}/load320_seed{seed}.json"
                    observed_base = baseline["run"]["tpot_p95_s"]
                treated = sources.json(treated_path)
                if treated["duration_s"] != 600 or treated["seed"] != seed or \
                        treated["trace_sha256"] != baseline["run"]["trace_sha256"] or \
                        treated["solution_sha256"] != baseline["run"]["solution_sha256"]:
                    raise ValueError(f"Invalid intervention identity: {treated_path}")
                predicted_base = baseline_path_cost(baseline, "baseline")
                predicted_treated = baseline_path_cost(baseline, treatment)
                rows.append({"intervention": treatment, "variant": variant, "seed": seed,
                             "predicted_baseline_s": predicted_base,
                             "predicted_treated_s": predicted_treated,
                             "predicted_improvement_s": predicted_base-predicted_treated,
                             "observed_baseline_tpot_p95_s": observed_base,
                             "observed_treated_tpot_p95_s": treated["tpot_p95_s"],
                             "observed_improvement_s": observed_base-treated["tpot_p95_s"],
                             "treated_source": treated_path.relative_to(ROOT).as_posix()})
    by_case = {}
    all_correct = True
    for treatment in ("bandwidth_double", "ideal_bandwidth", "prompt_zero"):
        group = [r for r in rows if r["intervention"] == treatment]
        comparison = {}
        for variant in ("k1", "k3"):
            subset = [r for r in group if r["variant"] == variant]
            predicted = mean([r["predicted_improvement_s"] for r in subset])
            observed = mean([r["observed_improvement_s"] for r in subset])
            comparison[variant] = {"predicted_improvement_mean_s": predicted,
                                   "observed_improvement_mean_s": observed,
                                   "direction_match": direction(predicted) == direction(observed)}
            all_correct &= comparison[variant]["direction_match"]
        pred_dominance = (comparison["k1"]["predicted_improvement_mean_s"]
                          - comparison["k3"]["predicted_improvement_mean_s"])
        obs_dominance = (comparison["k1"]["observed_improvement_mean_s"]
                         - comparison["k3"]["observed_improvement_mean_s"])
        comparison["k1_improvement_gt_k3"] = {
            "predicted": pred_dominance > 0, "observed": obs_dominance > 0,
            "match": direction(pred_dominance) == direction(obs_dominance)}
        all_correct &= comparison["k1_improvement_gt_k3"]["match"]
        by_case[treatment] = comparison
    switches = []
    for seed in (1, 2, 3):
        k1 = all_runs["k1", 320, seed]
        k3 = all_runs["k3", 320, seed]
        switches.append({"seed": seed,
                         "predicted_k1_s": baseline_path_cost(k1, "baseline"),
                         "predicted_k3_s": baseline_path_cost(k3, "baseline"),
                         "observed_k1_tpot_p95_s": k1["run"]["tpot_p95_s"],
                         "observed_k3_tpot_p95_s": k3["run"]["tpot_p95_s"]})
    predicted_switch = mean([r["predicted_k1_s"]-r["predicted_k3_s"] for r in switches])
    observed_switch = mean([r["observed_k1_tpot_p95_s"]-r["observed_k3_tpot_p95_s"]
                            for r in switches])
    by_case["k1_to_k3"] = {
        "predicted_k1_minus_k3_s": predicted_switch,
        "observed_k1_minus_k3_tpot_p95_s": observed_switch,
        "direction_match": direction(predicted_switch) == direction(observed_switch),
        "k1_improvement_gt_k3": "not_defined_for_layout_switch"}
    all_correct &= by_case["k1_to_k3"]["direction_match"]
    return {"rows": rows, "switch_rows": switches, "summary": by_case,
            "all_directions_correct": bool(all_correct)}


def canonical_shares(state: dict, checked: dict) -> dict[tuple[int, int], float]:
    segments = state["segments"]
    probabilities = [[0.0] * len(segment["replicas"]) for segment in segments]
    probabilities[0][0] = 1.0
    shares = defaultdict(float)
    for level, segment in enumerate(segments):
        for index, replica in enumerate(segment["replicas"]):
            share = probabilities[level][index]
            for edge in zip(replica, replica[1:]):
                shares[edge[0]+2, edge[1]+2] += share
            if level == len(segments)-1:
                continue
            successors = [j for i, j in checked["transitions"][level] if i == index]
            if not successors and share:
                raise ValueError("No reachable successor")
            for successor in successors:
                target = segments[level+1]["replicas"][successor][0]
                shares[replica[-1]+2, target+2] += share / len(successors)
                probabilities[level+1][successor] += share / len(successors)
    return dict(shares)


def layout_offline(case: str, label: str, load: int, layout: Path,
                   trace: list[tuple[float, int, int]], duration: int,
                   model: TopologyModel, reference: dict, sources: Sources) -> dict:
    source = sources.json(layout / "placement.json")
    state = placement.normalize(source["state"])
    checked = placement.validate(model, state)
    shares = canonical_shares(state, checked)
    hardware = link_hardware(layout / "simulator_cluster.ini", sources)
    sources.mark(layout / "solution.ini")
    edge_bandwidths = {edge: hardware[edge]["effective_Bps"] for edge in shares}
    lengths = [(int(entry[1]), int(entry[2])) for entry in trace]
    resources = checked["resources"]
    moments = from_trace_shares(lengths, duration, shares, edge_bandwidths,
                                resources.token_bytes, resources.activation_bytes)
    static = placement.objective(placement.measure(model, state), reference)
    return {"case": case, "label": label, "load": load,
            "layout": layout.relative_to(ROOT).as_posix(),
            "solution_sha256": sources.files[(layout / "solution.ini").relative_to(ROOT).as_posix()],
            "sim_cluster_sha256": sources.files[(layout / "simulator_cluster.ini").relative_to(ROOT).as_posix()],
            "interference_cost_s": path_weighted_wait(shares, moments),
            "frozen_static_objective": static,
            "saturated_links": [f"{left}->{right}" for (left, right), m in moments.items()
                                if m.rho_decode >= 1 and shares[left, right] > 0],
            "link_count": len(shares), "trace_requests": len(lengths),
            "trace_first_last_s": [trace[0][0], trace[-1][0]] if trace else []}


def candidate_layouts(sources: Sources) -> dict[str, dict[str, Path]]:
    sensitivity = sources.json(SEARCH / "planning_index.json")
    selection = sources.json(SELECTION / "selection_manifest.json")
    layouts = {}
    for case in ("C1_single", "C1_multi"):
        group = {}
        for label in sorted(sensitivity["cases"][case]):
            group[label] = SEARCH / "layouts" / case / label
        for candidate in selection["cases"][case]["candidates"]:
            label = candidate["label"]
            group.setdefault(label, ROOT / label)
        layouts[case] = group
    return layouts


def online_records(sources: Sources) -> dict[tuple[str, int, str, str, int], dict]:
    """Read formal results only after all offline layout scores exist."""
    chosen = {}
    sensitivity = sources.json(SEARCH / "formal_index.json")
    for name, item in sorted(sensitivity["jobs"].items()):
        if item["status"] not in ("passed", "reused"):
            continue
        identity = item["identity"]
        path = ROOT / item["source"]
        row = sources.json(path)
        if sources.files[item["source"]] != item["sha256"] or \
                row["solution_sha256"] != identity["solution_sha256"] or \
                row["sim_cluster_sha256"] != identity["sim_cluster_sha256"] or \
                row["trace_sha256"] != item["trace_sha256"] or \
                row["duration_s"] != 1800 or row["warmup_s"] != 0 or \
                row["seed"] != identity["seed"] or \
                row["offered_tokens_per_s"] != identity["offered_tokens_per_s"]:
            raise ValueError(f"Invalid search sensitivity formal identity: {name}")
        key = (identity["case"], int(identity["offered_tokens_per_s"]),
               identity["solution_sha256"], identity["sim_cluster_sha256"],
               identity["seed"])
        chosen[key] = {"source": item["source"], "tpot_p95_s": row["tpot_p95_s"],
                       "trace_sha256": row["trace_sha256"]}
    selection = sources.json(SELECTION / "selection_manifest.json")
    formal = sources.json(SELECTION / "formal_manifest.json")
    if formal["status"] != "complete":
        raise ValueError("M2 linear proxy formal manifest is incomplete")
    for item in formal["rows"]:
        case, load, seed = item["case"], item["offered"], item["seed"]
        selected = selection["cases"][case]
        for method in ("weighted", "linear"):
            label = selected[f"{method}_selected"]
            candidate = next(row for row in selected["candidates"] if row["label"] == label)
            source = item[f"{method}_source"]
            row = sources.json(ROOT / source)
            if sources.files[source] != item[f"{method}_sha256"] or \
                    row["solution_sha256"] != candidate["solution_sha256"] or \
                    row["sim_cluster_sha256"] != candidate["sim_cluster_sha256"] or \
                    row["seed"] != seed or row["offered_tokens_per_s"] != load or \
                    row["duration_s"] != 1800 or row["warmup_s"] != 0 or \
                    row["trace_sha256"] != item["trace_sha256"]:
                raise ValueError(f"Invalid linear proxy formal identity: {source}")
            key = (case, load, candidate["solution_sha256"],
                   candidate["sim_cluster_sha256"], seed)
            # Six search-sensitivity layouts use their own preregistered index.
            # The linear proxy manifest adds only candidates absent from that set.
            chosen.setdefault(key, {"source": source, "tpot_p95_s": row["tpot_p95_s"],
                                    "trace_sha256": row["trace_sha256"]})
    return chosen


def check_c(sources: Sources) -> dict:
    plans = sources.json(ROOT / "rcaps/v3/planning_inputs.json")
    layouts = candidate_layouts(sources)
    offline = []
    for case in ("C1_single", "C1_multi"):
        physical = ROOT / plans[case]["physical"]
        sources.mark(physical)
        model = TopologyModel(physical)
        reference_state = placement.normalize(plans[case]["reference_state"])
        reference = placement.measure(model, reference_state)
        for load in ((350, 700) if case == "C1_single" else (160, 320)):
            trace = OnlineRequestFeeder(load, start_time=0, duration=1800, seed=100).trace
            for label, layout in layouts[case].items():
                offline.append(layout_offline(case, label, load, layout, trace, 1800,
                                              model, reference, sources))
    online = online_records(sources)
    for row in offline:
        matching = [online.get((row["case"], row["load"], row["solution_sha256"],
                                row["sim_cluster_sha256"], seed)) for seed in (0, 1, 2)]
        if all(matching):
            row["online_tpot_p95_by_seed"] = {str(seed): matching[seed]["tpot_p95_s"]
                                              for seed in (0, 1, 2)}
            row["online_sources"] = [item["source"] for item in matching]
            row["online_tpot_p95_mean_s"] = mean(item["tpot_p95_s"] for item in matching)
        else:
            row["online_tpot_p95_mean_s"] = None
            row["missing_online_seeds"] = [seed for seed, item in enumerate(matching)
                                           if item is None]
    rankings = {}
    for case in ("C1_single", "C1_multi"):
        for load in ((350, 700) if case == "C1_single" else (160, 320)):
            eligible = [row for row in offline if row["case"] == case and row["load"] == load
                        and row["online_tpot_p95_mean_s"] is not None]
            # Duplicate deployment hashes represent the same layout, not extra ranking samples.
            unique = {(row["solution_sha256"], row["sim_cluster_sha256"]): row
                      for row in reversed(eligible)}
            ranked = list(unique.values())
            rankings[f"{case}/{load}"] = {
                "n_layouts": len(ranked), "labels": [row["label"] for row in ranked],
                "interference_spearman": spearman(
                    [row["interference_cost_s"] for row in ranked],
                    [row["online_tpot_p95_mean_s"] for row in ranked]),
                "frozen_static_spearman": spearman(
                    [row["frozen_static_objective"] for row in ranked],
                    [row["online_tpot_p95_mean_s"] for row in ranked]),
                "saturated_layouts": sum(bool(row["saturated_links"]) for row in ranked),
            }
    return {"rows": offline, "rankings": rankings,
            "offline_trace": {"generator": "OnlineRequestFeeder", "seed": 100,
                              "duration_s": 1800, "start_time_s": 0}}


def verdict(a: dict, b: dict, c: dict, protocol: dict) -> dict:
    r = a["rankings"]
    a_pass = (r["combined"]["spearman"] is not None and
              r["combined"]["spearman"] >= 0.6 and
              all(r[variant]["spearman"] is not None and
                  r[variant]["spearman"] > 0 for variant in ("k1", "k3")))
    b_pass = b["all_directions_correct"]
    selected = c["rankings"]["C1_multi/320"]
    score = selected["interference_spearman"]
    reference = selected["frozen_static_spearman"]
    c_pass = score is not None and reference is not None and score > 0 and score >= reference
    tier = 0 if a_pass and b_pass and c_pass else 1 if a_pass and b_pass else 2
    return {"a_pass": a_pass, "b_pass": b_pass, "c_pass": c_pass,
            "tier": tier+1, "result": protocol["decision_rules"][tier]["result"],
            "conclusion": protocol["decision_rules"][tier]["conclusion"]}


def fmt(value, digits=5) -> str:
    if value is None:
        return "未定义"
    return "∞" if value == math.inf else f"{value:.{digits}f}"


def render(result: dict) -> str:
    a, b, c, decision = (result[key] for key in ("A", "B", "C", "verdict"))
    lines = ["# T0.6 Prefill/Decode 链路干扰模型离线检验", "",
             "## 模型与口径", "",
             "Decode 为非抢占式高优先级；每条计算节点间链路使用独立 M/G/1 等待代理：",
             "`W=(λp E[Sp²]+λd E[Sd²])/[2(1−ρd)]`，`ρd=λd E[Sd]`。",
             "消息占用时间为 `_transfer_time` 的 payload 除以 `min(链路,发送 NIC,接收 NIC)`，不含传播延迟。",
             "A 的精确二阶矩来自 baseline 事件流；若事件流缺失，按锁定方案用输入长度 CV² 退化估计。",
             "B 仅以 baseline 链路统计与路线份额作模型输入；C 仅以种子 100 的生成轨迹和均分路径假设作模型输入。",
             f"Python 哈希种子：`{result['pythonhashseed']}`；图形后端：`{result['mplbackend']}`。", "",
             "## 检验 A：链路级排序", "",
             "| 集合 | 非饱和链路行数 | Spearman | 预测/实测中位数 | Q1–Q3 |",
             "| --- | ---: | ---: | ---: | --- |"]
    for name in ("k1", "k3", "combined"):
        r = a["rankings"][name]
        lines.append(f"| {name} | {r['n']} | {fmt(r['spearman'])} | "
                     f"{fmt(r['predicted_to_observed_ratio_median'])} | "
                     f"{fmt(r['predicted_to_observed_ratio_q1'])}–{fmt(r['predicted_to_observed_ratio_q3'])} |")
    lines += ["", f"饱和链路：**{a['saturated_count']}** 行；ρd≥1 的 W 记为无穷，未参加 Spearman。",
              f"另有 **{a['no_observed_wait_count']}** 条零消息链路没有实测等待值，逐行保留但不能参加配对 Spearman。",
              f"E[S²] 方法行数：{a['es2_methods']}。", "",
              "| 结构 | 负载 | 种子 | 链路 | 链路/有效 MB/s | Prompt/Decode 消息数 | λp/λd | E[Sp]/E[Sd] s | E[Sp²]/E[Sd²] s² | ρd | 预测 W s | 实测等待 s | E[S²] 方法 |",
              "| --- | ---: | ---: | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |"]
    for row in a["rows"]:
        lines.append(f"| {row['variant']} | {row['load']} | {row['seed']} | {row['from']}→{row['to']} "
                     f"({row['link_uid']}) | {fmt(row['capacity_MBps'])}/{fmt(row['effective_MBps'])} | "
                     f"{row['prompt_messages']}/{row['decode_messages']} | "
                     f"{fmt(row['lambda_prompt'])}/{fmt(row['lambda_decode'])} | "
                     f"{fmt(row['mean_prompt_s'])}/{fmt(row['mean_decode_s'])} | "
                     f"{fmt(row['second_prompt_s2'])}/{fmt(row['second_decode_s2'])} | "
                     f"{fmt(row['rho_decode'])} | {fmt(row['predicted_wait_s'])} | "
                     f"{fmt(row['observed_wait_s'])} | {row['es2_method']} |")
    lines += ["", "## 检验 B：干预方向", "",
              "| 干预 | 结构 | 种子 | 预测基线→干预 s | 实测 P95 TPOT 基线→干预 s |",
              "| --- | --- | ---: | --- | --- |"]
    for row in b["rows"]:
        lines.append(f"| {row['intervention']} | {row['variant']} | {row['seed']} | "
                     f"{fmt(row['predicted_baseline_s'])}→{fmt(row['predicted_treated_s'])} | "
                     f"{fmt(row['observed_baseline_tpot_p95_s'])}→{fmt(row['observed_treated_tpot_p95_s'])} |")
    for row in b["switch_rows"]:
        lines.append(f"| k1→k3 | 两结构 | {row['seed']} | "
                     f"{fmt(row['predicted_k1_s'])}→{fmt(row['predicted_k3_s'])} | "
                     f"{fmt(row['observed_k1_tpot_p95_s'])}→{fmt(row['observed_k3_tpot_p95_s'])} |")
    lines += ["", "| 干预 | k1 预测/实测改善 s | k3 预测/实测改善 s | 两结构方向 | k1 改善大于 k3：预测/实测/一致 |",
              "| --- | --- | --- | --- | --- |"]
    for treatment in ("bandwidth_double", "ideal_bandwidth", "prompt_zero"):
        group = b["summary"][treatment]
        k1, k3 = group["k1"], group["k3"]
        dominant = group["k1_improvement_gt_k3"]
        lines.append(f"| {treatment} | {fmt(k1['predicted_improvement_mean_s'])} / "
                     f"{fmt(k1['observed_improvement_mean_s'])} | "
                     f"{fmt(k3['predicted_improvement_mean_s'])} / "
                     f"{fmt(k3['observed_improvement_mean_s'])} | "
                     f"{k1['direction_match']} / {k3['direction_match']} | "
                     f"{dominant['predicted']} / {dominant['observed']} / {dominant['match']} |")
    switch = b["summary"]["k1_to_k3"]
    lines.append(f"| k1→k3 | {fmt(switch['predicted_k1_minus_k3_s'])} (k1−k3) | "
                 f"{fmt(switch['observed_k1_minus_k3_tpot_p95_s'])} (k1−k3) | "
                 f"{switch['direction_match']} | 不适用：结构切换只有一对结构 |")
    lines += ["", "## 检验 C：布局排序", "",
              "| 拓扑/负载 | 布局数 | 干扰模型 Spearman | 冻结静态目标 Spearman | 饱和布局 |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for key, row in c["rankings"].items():
        lines.append(f"| {key} | {row['n_layouts']} | {fmt(row['interference_spearman'])} | "
                     f"{fmt(row['frozen_static_spearman'])} | {row['saturated_layouts']} |")
    lines += ["", "| 拓扑 | 负载 | 布局 | 预测干扰 s | 冻结目标 | 在线 P95 TPOT 三种子均值 s | 在线种子 |",
              "| --- | ---: | --- | ---: | ---: | ---: | --- |"]
    for row in c["rows"]:
        seeds = row.get("online_tpot_p95_by_seed", {})
        lines.append(f"| {row['case']} | {row['load']} | {row['label']} | "
                     f"{fmt(row['interference_cost_s'])} | {fmt(row['frozen_static_objective'])} | "
                     f"{fmt(row['online_tpot_p95_mean_s'])} | {seeds or '无完整在线结果'} |")
    lines += ["", "判定只使用三集群负载 320；其他负载和单集群仅作参考。重复部署哈希只计一次。",
              "六个搜索敏感性布局使用其 `formal_index.json` 的在线结果；候选池中仅加入 `formal_manifest.json` 已选择且有完整结果的额外布局。",
              "同一部署在其他方法消融中也有运行，因方法或请求协议不同，不混入本次布局排序；缺少本次协议三种子结果的候选仍列在上表，但不参与 Spearman。", "",
              "## 预注册判定", "",
              f"A：**{decision['a_pass']}**；B：**{decision['b_pass']}**；C：**{decision['c_pass']}**。",
              f"档位 **{decision['tier']}**：{decision['conclusion']}", "",
              "## 已知局限", "",
              "M/G/1 假设平稳泊松到达；模拟器具有 Decode 合并发送与请求时序反馈；多跳链路可能耦合，",
              "同一发送端或接收端还可能共享 NIC。故该代理检验方向和排序，不将数值 W 当作在线 P95 TPOT。", "",
              "所用文件及 SHA256 见 `analysis.json` 的 `source_files`；本卡未运行新仿真窗口。", ""]
    return "\n".join(lines)


def json_safe(value):
    """Keep saturation explicit without emitting non-standard JSON Infinity."""
    if isinstance(value, float) and math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def main() -> None:
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("MPLBACKEND") != "Agg":
        raise RuntimeError("Set PYTHONHASHSEED=0 and MPLBACKEND=Agg before analysis")
    sources = Sources()
    protocol = sources.json(HERE / "protocol.json")
    all_runs, a_rows = baseline_data(sources)
    a = check_a(a_rows)
    b = check_b(all_runs, sources)
    c = check_c(sources)
    decision = verdict(a, b, c, protocol)
    output = {"task": "T0.6", "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
              "mplbackend": os.environ.get("MPLBACKEND"), "A": a, "B": b, "C": c,
              "verdict": decision, "source_files": dict(sorted(sources.files.items()))}
    encoded = json.dumps(json_safe(output), ensure_ascii=False, indent=2,
                         allow_nan=False) + "\n"
    (HERE / "analysis.json").write_text(encoded, encoding="utf-8", newline="\n")
    (HERE / "RESULTS_CN.md").write_text(render(output), encoding="utf-8", newline="\n")
    index = {"task": "T0.6", "simulation_windows": {}, "status": "offline_complete",
             "inputs": [{"path": path, "sha256": sha, "status": "read"}
                        for path, sha in sorted(sources.files.items())]}
    (HERE / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": decision, "a": a["rankings"], "b": b["summary"],
                      "c": c["rankings"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
