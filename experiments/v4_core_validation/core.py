"""Isolated final-RCAPS controls; frozen implementation files remain untouched."""
from __future__ import annotations

from contextlib import contextmanager
from collections import Counter
import copy

from experiments.v4_validation import diagnostics as legacy
from rcaps.v4.chunking import PromptTransferChunkHook
from simulator.event_simulator.event import EventHandler


class BoundaryCostHook(PromptTransferChunkHook):
    """Add no-byte resource holding time before each intermediate release."""

    def __init__(self, *args, boundary_cost_s=0.0, **kwargs):
        super().__init__(*args, **kwargs)
        if boundary_cost_s < 0:
            raise ValueError("Negative boundary cost")
        self.boundary_cost_s = float(boundary_cost_s)
        self.overhead_observer = None
        self.boundaries_charged = 0
        self.boundaries_released = 0
        self.holding = {}

    def install(self, simulator, beginning, ending):
        super().install(simulator, beginning, ending)
        if not self.boundary_cost_s:
            return  # exact zero-cost event path, including event UID order
        original_handle = simulator.handle_event

        def handle(event):
            if event.event_handler == EventHandler.FinishSending:
                key = (event.args["link_uid"], event.args["transmission_object_handle"])
                if event.args.get("_core_boundary_cost_paid"):
                    if key not in self.holding:
                        raise AssertionError("Unmatched cost-release event")
                    del self.holding[key]
                    self.boundaries_released += 1
                    return original_handle(event)
                session = self.sessions.get(key)
                if session is not None and session["remaining"] > 0:
                    if session["paused"] or key in self.holding:
                        raise AssertionError("Duplicate boundary charge")
                    now = event.event_time
                    if now < simulator.current_time:
                        raise AssertionError("Boundary cost traveled backward")
                    simulator.current_time = now
                    link = session["link"]
                    end = now + self.boundary_cost_s
                    self.holding[key] = end
                    self.boundaries_charged += 1
                    obj = link.requests_on_the_fly[key[1]]
                    if self.overhead_observer is not None:
                        self.overhead_observer(link, obj, now, end)
                    args = dict(event.args, _core_boundary_cost_paid=True, send_end_time=end)
                    self._event(EventHandler.FinishSending, end, link.node_in, args,
                                event.description)
                    return  # keep all three original bandwidth reservations
            return original_handle(event)

        simulator.handle_event = handle

    def summary(self, query_samples):
        result = super().summary(query_samples)
        result["boundary_cost"] = {
            "seconds_per_intermediate_boundary": self.boundary_cost_s,
            "semantics": "hold allocated link/send-NIC/receive-NIC bandwidth; zero bytes; then release",
            "hardware_measurement": False,
            "boundaries_charged": self.boundaries_charged,
            "boundaries_released": self.boundaries_released,
            "holding_at_end": len(self.holding),
            "nominal_total_added_hold_s": self.boundaries_charged * self.boundary_cost_s,
        }
        return result


class CoreProbe(legacy.ValidationProbe):
    def __init__(self, chunk_hook, arrival_horizon, bandwidth_factor=1):
        super().__init__(chunk_hook, arrival_horizon, bandwidth_factor)
        if isinstance(chunk_hook, BoundaryCostHook):
            chunk_hook.overhead_observer = self.cost_interval

    def cost_interval(self, link, obj, start, end):
        label = f"{link.node_in.entity_name}->{link.node_out.entity_name}"
        stats = self.links[label]
        duration = self.overlap(start, end)
        normalized = duration * obj.bandwidth_usage / link.bandwidth
        stats["occupied_s"] += normalized
        stats["service_request_s"] += duration * len(obj.requests)
        stats["prompt_occupied_s"] += normalized
        stats["boundary_cost_occupied_s"] += normalized
        stats["boundary_cost_hold_s"] += duration
        stats["boundary_cost_events"] += 1
        # Deliberately do not change prompt_bytes_in_window or serialization segments.
        for resource in (("link", link.link_uid), ("send", link.node_in.node_uid),
                         ("receive", link.node_out.node_uid)):
            self.prompt[resource].add(start, end)

    def summary(self, query_samples):
        result = super().summary(query_samples)
        result["boundary_cost_accounting"] = {
            "hold_s": sum(x.get("boundary_cost_hold_s", 0) for x in self.links.values()),
            "capacity_normalized_occupied_s": sum(
                x.get("boundary_cost_occupied_s", 0) for x in self.links.values()),
            "added_payload_bytes": 0,
            "note": "Reported occupancy includes explicit no-byte holds; payload counters exclude them.",
        }
        return result


@contextmanager
def isolated_adapter(routing_state, cost_s):
    old_scheduler = legacy.ProfileScheduler
    old_hook = legacy.PromptTransferChunkHook
    old_probe = legacy.ValidationProbe

    def scheduler(simulator, **kwargs):
        kwargs["routing_state"] = routing_state
        return old_scheduler(simulator, **kwargs)

    def hook(*args, **kwargs):
        return BoundaryCostHook(*args, boundary_cost_s=cost_s, **kwargs)

    legacy.ProfileScheduler, legacy.PromptTransferChunkHook = scheduler, hook
    legacy.ValidationProbe = CoreProbe
    try:
        yield
    finally:
        legacy.ProfileScheduler = old_scheduler
        legacy.PromptTransferChunkHook = old_hook
        legacy.ValidationProbe = old_probe


def evaluate(job, *, duration=None, arrival_horizon=None):
    duration = job.get("duration", 5400) if duration is None else duration
    horizon = job.get("arrival_horizon", 1800) if arrival_horizon is None else arrival_horizon
    routing = "no_session" if job["experiment"] == "session" else "live"
    cost = job.get("boundary_cost_s", 0.0)
    internal = dict(job, condition="cohort_tail", cell="v4")
    with isolated_adapter(routing, cost):
        row = legacy.evaluate(internal, duration, horizon)
    row["core_protocol"] = {
        "experiment": job["experiment"], "routing_state": routing,
        "boundary_cost_s": cost, "arrival_horizon_s": horizon,
        "observation_horizon_s": duration, "hardware_calibration": False,
        "reference_stack": "complete RCAPS with frozen sparse graph and 4 MiB slow-link chunks",
    }
    if row["admission"]["routing_state"] != routing:
        raise AssertionError("Requested routing intervention did not apply")
    return row


def validate_row(row):
    """Invariants apply equally to favorable, unfavorable, and censored runs."""
    import math
    required = ["ttft_p95_s", "tpot_p95_s", "output_throughput_tokens_per_s",
                "gpu_seconds_per_output_token", "completion_fraction"]
    for field in required:
        if not isinstance(row[field], (int, float)) or not math.isfinite(row[field]):
            raise AssertionError(f"Non-finite metric: {field}")
    for field in ("gpu_busy_fraction", "link_occupied_fraction"):
        if any(not -1e-8 <= value <= 1 + 1e-8 for value in row[field].values()):
            raise AssertionError(f"Invalid occupancy: {field}")
    if row["cohort"]["completed"]:
        if row["cohort"]["target_output_tokens"] != row["cohort"]["produced_output_tokens"]:
            raise AssertionError("Completed cohort changed token count")
        if row["backlog_at_window_end"] != 0:
            raise AssertionError("Completed cohort has backlog")
    probe = row["phase_link_profile"]
    if not probe["validation"]["legality"]["complete_paths"] > 0:
        raise AssertionError("No complete legal path")
    chunk = probe.get("chunking", {})
    cost = chunk.get("boundary_cost", {})
    if cost.get("seconds_per_intermediate_boundary", 0) > 0:
        if cost["boundaries_charged"] <= 0:
            raise AssertionError("Cost intervention never activated")
        if cost["boundaries_released"] + cost["holding_at_end"] != cost["boundaries_charged"]:
            raise AssertionError("Boundary cost event imbalance")
        if cost["boundaries_released"] != chunk["paused_chunks"]:
            raise AssertionError("Not exactly one charge per release")
        expected = sum(v.get("boundary_cost_hold_s", 0) for v in probe["links"].values())
        if not math.isclose(expected, probe["boundary_cost_accounting"]["hold_s"], abs_tol=1e-9):
            raise AssertionError("Hold accounting mismatch")
    return {"finite_metrics": True, "occupancy_bounds": True, "legal_paths": True,
            "complete_cohort_token_conservation": row["cohort"]["completed"],
            "cost_event_conservation": True}


def engineering_checks():
    """Only new critical paths; none of these short windows are paper data."""
    base = dict(experiment="reference", scenario="multi", load=320, seed=0,
                boundary_cost_s=0.0)
    old = legacy.evaluate(dict(base, condition="cohort_tail", cell="v4"), 180, 60)
    zero = evaluate(base, duration=180, arrival_horizon=60)
    fields = ["trace_sha256", "arrivals", "tpot_p95_s", "ttft_p95_s",
              "output_throughput_tokens_per_s", "completion_fraction", "backlog_at_window_end",
              "query_samples", "route_counts", "gpu_busy_fraction", "cohort",
              "link_occupied_fraction", "link_service_request_s", "link_propagation_request_s"]
    differences = [k for k in fields if old[k] != zero[k]]
    if differences:
        raise AssertionError(f"Zero intervention drift: {differences}")
    print("ENGINEERING zero_adapter_equivalent", flush=True)
    no_session = evaluate(dict(base, experiment="session"), duration=180, arrival_horizon=60)
    if no_session["admission"]["allowed_edges"] != zero["admission"]["allowed_edges"]:
        raise AssertionError("Session control changed admission graph")
    validate_row(no_session)
    print("ENGINEERING session_control_active", flush=True)
    positive = evaluate(dict(base, experiment="boundary_cost", boundary_cost_s=0.01),
                        duration=180, arrival_horizon=60)
    validate_row(positive)
    if positive["trace_sha256"] != zero["trace_sha256"]:
        raise AssertionError("Cost intervention changed arrivals")
    if positive["admission"]["allowed_edges"] != zero["admission"]["allowed_edges"]:
        raise AssertionError("Cost intervention changed graph")
    # With both short cohorts fully completed and unchanged routes, serialization
    # payload is identical even though no-byte occupied intervals were added.
    check_bytes = (positive["cohort"]["completed"] and zero["cohort"]["completed"]
                   and positive["route_counts"] == zero["route_counts"])
    if check_bytes:
        for kind in ["prompt", "decode"]:
            a = sum(v.get(kind + "_bytes_in_window", 0) for v in positive["phase_link_profile"]["links"].values())
            b = sum(v.get(kind + "_bytes_in_window", 0) for v in zero["phase_link_profile"]["links"].values())
            if abs(a - b) > max(1e-3, abs(b) * 1e-10):
                raise AssertionError(f"Cost interval fabricated bytes: {kind}")
    print("ENGINEERING cost_active_and_conserved", flush=True)
    return {"status": "passed", "kind": "engineering_only", "zero_exact_fields": fields,
            "session": no_session["admission"]["routing_state"],
            "cost": positive["phase_link_profile"]["chunking"]["boundary_cost"],
            "same_route_full_payload_comparison_applied": check_bytes}
