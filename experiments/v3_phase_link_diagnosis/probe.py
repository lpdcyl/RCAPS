"""Optional, passive event probe and isolated activation-byte interventions.

The probe is attached to one simulator instance by ``benchmarks.fixed_window``.
No scheduler choice or event timestamp is changed in the baseline mode.
"""

from __future__ import annotations

import bisect
import gzip
import json
from collections import defaultdict
from pathlib import Path

from simulator.event_simulator.base_node import NodeType
from simulator.event_simulator.request import RequestPhase


def percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * pct / 100
    low = int(position)
    return ordered[low] + (ordered[min(low + 1, len(ordered) - 1)] - ordered[low]) * (position - low)


def union_length(intervals):
    if not intervals:
        return 0.0
    intervals.sort()
    total = 0.0
    left, right = intervals[0]
    for start, end in intervals[1:]:
        if start > right:
            total += right - left
            left, right = start, end
        else:
            right = max(right, end)
    return total + right - left


class PromptHistory:
    def __init__(self):
        self.completed = []
        self.ends = []
        self.active = {}

    def start(self, key, when):
        self.active[key] = when

    def finish(self, key, when):
        start = self.active.pop(key)
        self.completed.append((start, when))
        self.ends.append(when)

    def overlaps(self, start, end):
        intervals = []
        for left, right in self.completed[bisect.bisect_right(self.ends, start):]:
            if left < end:
                intervals.append((max(start, left), min(end, right)))
        for left in self.active.values():
            if left < end:
                intervals.append((max(start, left), end))
        return intervals


class PhaseLinkProbe:
    def __init__(self, raw_path: Path | None, treatment: str = "baseline"):
        if treatment not in {"baseline", "prompt_zero", "decode_zero", "ideal_bandwidth"}:
            raise ValueError(treatment)
        self.raw_path = raw_path
        self.treatment = treatment
        self.raw = None
        self.simulator = None
        self.begin = 0.0
        self.end = 0.0
        self.ready = {}
        self.gpu_ready = {}
        self.prompt_history = defaultdict(PromptHistory)
        self.link_stats = {}
        self.active_transmissions = {}
        self.request_block = defaultdict(lambda: {"same_s": 0.0, "nic_s": 0.0,
                                                  "union_s": 0.0, "wait_s": 0.0})
        self.query_steps = defaultdict(list)
        self.decode_finished = defaultdict(int)
        self.gpu_by_phase = defaultdict(lambda: {"wait_s": 0.0, "compute_s": 0.0,
                                                "executions": 0})
        self.transfer_events = 0

    def close(self):
        if self.raw is not None:
            self.raw.close()
            self.raw = None

    def log(self, kind, **fields):
        if self.raw is not None:
            self.raw.write(json.dumps({"event": kind, "time_s": self.simulator.current_time,
                                       **fields}, separators=(",", ":")) + "\n")
        self.transfer_events += 1

    @staticmethod
    def phase(request):
        return "prompt" if request.phase == RequestPhase.Initialization else "decode"

    @staticmethod
    def physical_bytes(link, request):
        token = request.token_size * request.token_seq_length
        if link.node_in_type == NodeType.Compute and link.node_out_type == NodeType.Compute:
            return token + request.activation_size * request.token_seq_length
        return token

    def effective_bytes(self, link, request):
        token = request.token_size * request.token_seq_length
        if link.node_in_type != NodeType.Compute or link.node_out_type != NodeType.Compute:
            return token
        activation = request.activation_size * request.token_seq_length
        if self.treatment == "prompt_zero" and request.phase == RequestPhase.Initialization:
            activation = 0
        if self.treatment == "decode_zero" and request.phase == RequestPhase.Increment:
            activation = 0
        return token + activation

    def _wait_overlap(self, link, ready_at, now):
        link_intervals = self.prompt_history[("link", link.link_uid)].overlaps(ready_at, now)
        nic_intervals = (
            self.prompt_history[("send", link.node_in.node_uid)].overlaps(ready_at, now) +
            self.prompt_history[("receive", link.node_out.node_uid)].overlaps(ready_at, now))
        same = union_length(link_intervals)
        nic = union_length(nic_intervals)
        combined = union_length(link_intervals + nic_intervals)
        return same, nic, combined

    def install(self, simulator, beginning, ending):
        self.simulator, self.begin, self.end = simulator, beginning, ending
        if self.raw_path is not None:
            self.raw_path.parent.mkdir(parents=True, exist_ok=True)
            self.raw = gzip.open(self.raw_path, "wt", encoding="utf-8", compresslevel=3)
        if self.treatment == "ideal_bandwidth":
            factor = 1_000_000.0
            for node in [simulator.source_node, *simulator.compute_nodes.values(),
                         simulator.sink_node]:
                for direction in ("inbound", "outbound"):
                    speed = f"{direction}_nic_speed"
                    available = f"{direction}_available_bandwidth"
                    if hasattr(node, speed):
                        setattr(node, speed, getattr(node, speed) * factor)
                        setattr(node, available, getattr(node, available) * factor)
            for link in simulator.links.values():
                link.bandwidth *= factor
                link.available_bandwidth *= factor

        for link in simulator.links.values():
            self.link_stats[link.link_uid] = {
                "link_uid": link.link_uid, "from": link.node_in.node_uid,
                "to": link.node_out.node_uid, "capacity_Bps": link.bandwidth,
                "latency_s": link.latency,
                "compute_to_compute": (link.node_in_type == NodeType.Compute and
                                       link.node_out_type == NodeType.Compute),
                "prompt_bytes": 0.0, "decode_bytes": 0.0,
                "prompt_effective_bytes": 0.0, "decode_effective_bytes": 0.0,
                "prompt_messages": 0, "decode_messages": 0,
                "prompt_sends": 0, "decode_sends": 0,
                "busy_fraction_numerator_s": 0.0,
                "prompt_busy_fraction_numerator_s": 0.0,
                "decode_busy_fraction_numerator_s": 0.0,
                "decode_wait_samples_s": [], "prompt_wait_samples_s": [],
                "same_prompt_wait_samples_s": [],
            }
            if self.treatment in {"prompt_zero", "decode_zero"}:
                def calculate(requests, planned_bandwidth, _link=link):
                    assert planned_bandwidth <= _link.available_bandwidth
                    return _link.latency + sum(self.effective_bytes(_link, req)
                                               for req in requests) / planned_bandwidth
                link.calculate_transmission_time = calculate
            original_start = link.start_sending
            def start(requests, bandwidth_requirement, transmission_type,
                      _link=link, _original=original_start):
                now = simulator.current_time
                handle = _original(requests, bandwidth_requirement, transmission_type)
                key = (_link.link_uid, handle.get_handle())
                send_end = now + handle.duration - _link.latency
                self.active_transmissions[key] = (now, send_end, requests)
                stats = self.link_stats[_link.link_uid]
                overlap = max(0.0, min(send_end, self.end) - max(now, self.begin))
                fraction = overlap * bandwidth_requirement / _link.bandwidth
                stats["busy_fraction_numerator_s"] += fraction
                kind = self.phase(requests[0])
                stats[f"{kind}_busy_fraction_numerator_s"] += fraction
                stats[f"{kind}_sends"] += 1
                if kind == "prompt":
                    for resource in (("link", _link.link_uid),
                                     ("send", _link.node_in.node_uid),
                                     ("receive", _link.node_out.node_uid)):
                        self.prompt_history[resource].start(key, now)
                for request in requests:
                    phase = self.phase(request)
                    uid = request.request_uid
                    ready_at = self.ready.pop((uid, _link.node_in.node_uid), now)
                    wait = max(0.0, now - ready_at)
                    same = nic = combined = 0.0
                    if phase == "decode" and wait:
                        same, nic, combined = self._wait_overlap(_link, ready_at, now)
                        totals = self.request_block[uid]
                        totals["same_s"] += same
                        totals["nic_s"] += nic
                        totals["union_s"] += combined
                        totals["wait_s"] += wait
                        stats["same_prompt_wait_samples_s"].append(same)
                    stats[f"{phase}_bytes"] += self.physical_bytes(_link, request)
                    stats[f"{phase}_effective_bytes"] += self.effective_bytes(_link, request)
                    stats[f"{phase}_messages"] += 1
                    stats[f"{phase}_wait_samples_s"].append(wait)
                    self.log("start", request_uid=uid, query_uid=request.base_query_uid,
                             phase=phase, link_uid=_link.link_uid, ready_s=ready_at,
                             planned_bandwidth_Bps=bandwidth_requirement,
                             physical_bytes=self.physical_bytes(_link, request),
                             effective_bytes=self.effective_bytes(_link, request),
                             send_end_s=send_end, same_prompt_wait_s=same,
                             nic_prompt_wait_s=nic, any_prompt_wait_s=combined)
                return handle
            link.start_sending = start

            original_send_end = link.finish_sending
            def finish_send(transmission_object_handle, _link=link,
                            _original=original_send_end):
                obj = _original(transmission_object_handle)
                key = (_link.link_uid, transmission_object_handle)
                now = simulator.current_time
                if self.phase(obj.requests[0]) == "prompt":
                    for resource in (("link", _link.link_uid),
                                     ("send", _link.node_in.node_uid),
                                     ("receive", _link.node_out.node_uid)):
                        self.prompt_history[resource].finish(key, now)
                for request in obj.requests:
                    self.log("send_end", request_uid=request.request_uid,
                             query_uid=request.base_query_uid, link_uid=_link.link_uid)
                self.active_transmissions.pop(key)
                return obj
            link.finish_sending = finish_send

            original_arrive = link.finish_transmission
            def arrive(finish_time, transmission_object_handle, _link=link,
                       _original=original_arrive):
                obj = _original(finish_time, transmission_object_handle)
                for request in obj.requests:
                    if _link.node_out_type == NodeType.Compute:
                        self.gpu_ready[request.request_uid] = simulator.current_time
                    self.log("arrival", request_uid=request.request_uid,
                             query_uid=request.base_query_uid, link_uid=_link.link_uid)
                return obj
            link.finish_transmission = arrive

        for node in simulator.compute_nodes.values():
            original_exec = node.start_execution
            def start_execution(requests, _node=node, _original=original_exec):
                now = simulator.current_time
                batch = _original(requests)
                for request in requests:
                    uid = request.request_uid
                    ready_at = self.gpu_ready.pop(uid, now)
                    item = self.gpu_by_phase[self.phase(request)]
                    item["wait_s"] += max(0.0, now - ready_at)
                    item["compute_s"] += batch.duration
                    item["executions"] += 1
                    self.log("gpu_start", request_uid=uid,
                             query_uid=request.base_query_uid, node_uid=_node.node_uid,
                             ready_s=ready_at, compute_s=batch.duration)
                return batch
            node.start_execution = start_execution

            original_finish_exec = node.finish_execution
            def finish_execution(inference_batch_handle, _node=node,
                                 _original=original_finish_exec):
                batch, outbound = _original(inference_batch_handle)
                now = simulator.current_time
                for request in batch.requests:
                    if outbound:
                        self.ready[(request.request_uid, _node.node_uid)] = now
                        self.log("ready", request_uid=request.request_uid,
                                 query_uid=request.base_query_uid, node_uid=_node.node_uid,
                                 phase=self.phase(request))
                    else:
                        self.gpu_ready[request.request_uid] = now
                return batch, outbound
            node.finish_execution = finish_execution

        original_source = simulator.handle_command_new_request
        def source_ready(event):
            result = original_source(event)
            if result:
                request = event.args["request"]
                self.ready[(request.request_uid, simulator.source_node.node_uid)] = simulator.current_time
                self.log("ready", request_uid=request.request_uid,
                         query_uid=request.base_query_uid,
                         node_uid=simulator.source_node.node_uid,
                         phase=self.phase(request))
            return result
        simulator.handle_command_new_request = source_ready

        original_gather = simulator.handle_gather_finished
        def gather(event):
            finished = list(simulator.sink_node.inbound_request_queue)
            result = original_gather(event)
            if self.begin <= simulator.current_time < self.end:
                for request in finished:
                    if request.phase != RequestPhase.Increment:
                        continue
                    query = request.base_query_uid
                    self.decode_finished[query] += 1
                    if self.decode_finished[query] < 2:
                        continue  # First output token contributes to TTFT, not TPOT.
                    block = self.request_block.pop(request.request_uid, None)
                    self.query_steps[query].append(block or {"same_s": 0.0,
                        "nic_s": 0.0, "union_s": 0.0, "wait_s": 0.0})
            return result
        simulator.handle_gather_finished = gather

    def summary(self, query_samples):
        self.close()
        eligible = [(int(qid), sample["tpot_s"]) for qid, sample in query_samples.items()
                    if sample.get("tpot_s") is not None]
        eligible.sort(key=lambda item: (-item[1], item[0]))
        tail_count = max(1, int(len(eligible) * 0.05 + 0.999999)) if eligible else 0
        tail_ids = {uid for uid, _ in eligible[:tail_count]}
        eligible_ids = {uid for uid, _ in eligible}

        def cohort(ids):
            steps = [step for uid in ids for step in self.query_steps.get(uid, [])]
            same = [step["same_s"] for step in steps]
            any_prompt = [step["union_s"] for step in steps]
            return {"queries": len(ids), "steps": len(steps),
                    "same_link_blocked_steps": sum(value > 1e-9 for value in same),
                    "same_link_blocked_fraction": (sum(value > 1e-9 for value in same) / len(steps)
                                                   if steps else None),
                    "any_prompt_blocked_fraction":
                        (sum(value > 1e-9 for value in any_prompt) / len(steps)
                         if steps else None),
                    "same_link_wait_mean_s": sum(same) / len(steps) if steps else None,
                    "same_link_wait_p95_s": percentile(same, 95),
                    "any_prompt_wait_mean_s": sum(any_prompt) / len(steps) if steps else None}

        link_rows = []
        for stats in self.link_stats.values():
            row = {key: value for key, value in stats.items() if not key.endswith("samples_s")}
            duration = self.end - self.begin
            for key in ("busy", "prompt_busy", "decode_busy"):
                row[f"{key}_utilization"] = row.pop(f"{key}_fraction_numerator_s") / duration
            for phase in ("prompt", "decode"):
                waits = stats[f"{phase}_wait_samples_s"]
                row[f"{phase}_wait_mean_s"] = sum(waits) / len(waits) if waits else None
                row[f"{phase}_wait_p95_s"] = percentile(waits, 95)
            same = stats["same_prompt_wait_samples_s"]
            row["decode_same_prompt_wait_mean_s"] = sum(same) / len(same) if same else None
            row["decode_same_prompt_blocked_fraction"] = (
                sum(value > 1e-9 for value in same) / len(same) if same else None)
            row["decode_same_prompt_samples"] = len(same)
            link_rows.append(row)
        return {"treatment": self.treatment, "raw_events": str(self.raw_path)
                if self.raw_path else None, "event_count": self.transfer_events,
                "links": sorted(link_rows, key=lambda x: x["link_uid"]),
                "tail": cohort(tail_ids), "all": cohort(eligible_ids),
                "gpu_by_phase": dict(self.gpu_by_phase),
                "tail_query_ids": sorted(tail_ids),
                "tail_tpot_threshold_s": eligible[tail_count - 1][1] if eligible else None}
