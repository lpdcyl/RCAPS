"""Full V4 under preregistered environmental counterfactuals and cohort tails.

All interventions are explicit and process-local. No frozen source is edited.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import json
from pathlib import Path
from time import perf_counter_ns

from benchmarks import fixed_window
from benchmarks.accumulator import WindowAccumulator
from rcaps.v3.topology import TopologyModel
from rcaps.v4.admission import AdmissionScheduler
from rcaps.v4.chunking import PromptTransferChunkHook
from rcaps.v4.probe import MechanismProbe
from simulator.event_simulator.model import ModelLayer
from simulator.event_simulator.request import RequestPhase
from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder
from experiments.v4_formal.run import ROOT, inputs


@contextmanager
def singleton_profile(multiplier):
    """Change only the explicit singleton penalty, leaving interpolation intact."""
    original = ModelLayer.get_inference_statistics
    def statistics(layer, requests):
        time_s, vram = original(layer, requests)
        decode = sum(r.token_seq_length for r in requests if r.phase == RequestPhase.Increment)
        if decode == 1:
            time_s += (multiplier - 2) * layer.get_decode_inference_time(1)
        return time_s, vram
    if multiplier != 2:
        ModelLayer.get_inference_statistics = statistics
    try:
        yield
    finally:
        ModelLayer.get_inference_statistics = original


class ProfileScheduler(AdmissionScheduler):
    def __init__(self, simulator, *, singleton_multiplier=2, **kwargs):
        super().__init__(simulator, **kwargs)
        self.singleton_multiplier = singleton_multiplier

    def _decode_token_service(self, node, first, end, active_sessions):
        # The inherited final M3 multiplies the interpolated singleton by two.
        return (self.singleton_multiplier / 2) * super()._decode_token_service(
            node, first, end, active_sessions)


class ValidationProbe(MechanismProbe):
    """Passive boundary snapshots, runtime legality checks and cost recording."""
    def __init__(self, chunk_hook, arrival_horizon, bandwidth_factor=1):
        super().__init__(chunk_hook)
        self.arrival_horizon = arrival_horizon
        self.bandwidth_factor = bandwidth_factor
        self.boundary = None
        self.changed_links = []
        self.accumulator = None
        self.last_completion_s = None
        self.last_output_s = None
        self.invariant = None

    def pending_snapshot(self, at):
        phases = {k: dict(messages=0, age_sum_s=0., max_age_s=0.) for k in ['prompt', 'decode']}
        # MechanismProbe.ready only measures outbound-ready intervals. Chunk
        # pause intervals have a separate session state and are reported below.
        for node in (self.simulator.source_node, *self.simulator.compute_nodes.values()):
            for request in node.outbound_request_dict.values():
                ready = self.ready.get((node.node_uid, request.request_uid))
                if ready is None:
                    continue
                age = max(0., at-max(ready, self.begin))
                stats = phases[self.kind(request)]
                stats['messages'] += 1
                stats['age_sum_s'] += age
                stats['max_age_s'] = max(stats['max_age_s'], age)
        phases['active_queries'] = len(self.simulator.query_manager.queries_on_the_fly)
        phases['time_from_start_s'] = at-self.begin
        phases['unfinished_chunk_sessions'] = len(self.chunk_hook.sessions) if self.chunk_hook else 0
        return phases

    def install(self, simulator, beginning, ending):
        for link in simulator.links.values():
            if (link.node_in_type.name == 'Compute' and link.node_out_type.name == 'Compute'
                    and link.bandwidth <= 50_000_000 and self.bandwidth_factor != 1):
                old = link.bandwidth
                assert link.available_bandwidth == old
                link.bandwidth *= self.bandwidth_factor
                link.available_bandwidth *= self.bandwidth_factor
                self.changed_links.append(dict(uid=link.link_uid, old_Bps=old, new_Bps=link.bandwidth))
        super().install(simulator, beginning, ending)
        simulator.scheduler._initialize_graph()
        scheduler = simulator.scheduler
        full, canon, allowed = scheduler.execution_dag, scheduler.canonical_edges, scheduler.allowed_edges
        from rcaps.v3.resource_graph import LayerCompatibilityDag
        assert canon <= allowed <= full.edge_set
        for left, right in full.edges:
            if not isinstance(left, str) and not isinstance(right, str):
                assert full.spans[right][0] <= full.spans[left][1] < full.spans[right][1]
        self.invariant = dict(canonical_subset=True, legal_subset=True,
                              complete_paths=LayerCompatibilityDag(full.spans, tuple(allowed), full.layers).path_count())
        assert self.invariant['complete_paths'] > 0
        original = simulator.simulate
        cut = beginning+self.arrival_horizon
        def simulate(*args, **kwargs):
            until = kwargs.get('until', args[0] if args else None)
            if until is not None and until >= cut and self.boundary is None:
                original(until=cut)
                self.boundary = self.pending_snapshot(cut)
            if until is not None and until > cut:
                # Tail compaction is identical to normal compact collection;
                # it only discards history after accounting for its events.
                while simulator.current_time < until:
                    target = min(until, simulator.current_time+60)
                    original(until=target)
                    if self.accumulator is not None:
                        self.accumulator.collect(simulator, beginning, ending)
                return None
            return original(*args, **kwargs)
        simulator.simulate = simulate

    def summary(self, query_samples):
        result = super().summary(query_samples)
        result['validation'] = dict(
            arrival_boundary=self.boundary, end_pending=self.pending_snapshot(self.end),
            changed_links=self.changed_links, legality=self.invariant,
            last_completion_s=self.last_completion_s, last_output_s=self.last_output_s,
            waiting_scope='outbound-ready unsettled waits; paused chunk sessions separately counted')
        return result


def evaluate(job, duration=1800, arrival_horizon=1800):
    physical, deployment = inputs(job)
    state = json.loads((deployment/'placement.json').read_text(encoding='utf-8'))['state']
    cell, condition = job['cell'], job['condition']
    admission = 'full' if cell in ['v3', 'temporal'] else 'sparse'
    chunk = 0 if cell in ['v3', 'spatial'] else 4_194_304
    multiplier = 1 if condition == 'singleton1' else 2
    factor = .5 if condition == 'network_half' else 1
    probe = ValidationProbe(PromptTransferChunkHook(chunk) if chunk else None,
                            arrival_horizon, factor)
    holder = {}
    def factory(simulator):
        scheduler = ProfileScheduler(simulator, state=state, admission=admission,
            routing_state='static' if cell == 'static' else 'live', singleton_multiplier=multiplier)
        holder['scheduler'] = scheduler
        return scheduler

    trace = None
    trace_metadata = {'transform': 'none'}
    if condition in ['cohort_tail', 'prompt_heavy']:
        original_trace = OnlineRequestFeeder(job['load'], 0, arrival_horizon, job['seed']).trace
        trace = list(original_trace)
        if condition == 'prompt_heavy':
            trace = [(t, p+min(o//2, max(0, 4096-p)), o-min(o//2, max(0, 4096-p)))
                     for t,p,o in original_trace]
            assert all(a[1]+a[2] == b[1]+b[2] and a[0] == b[0] for a,b in zip(trace,original_trace))
        trace_metadata = dict(transform=condition, arrivals=len(trace),
            original_input_tokens=sum(p for _,p,o in original_trace),
            input_tokens=sum(p for _,p,o in trace), target_output_tokens=sum(o for _,p,o in trace),
            total_offered_tokens=sum(p+o for _,p,o in trace),
            observed_offered_tokens_per_s=sum(p+o for _,p,o in trace)/arrival_horizon)

    original_collect = WindowAccumulator.collect
    def collect(acc, simulator, beginning, ending):
        probe.accumulator = acc
        for finish, query in simulator.query_manager.finished_queries.values():
            probe.last_completion_s = max(probe.last_completion_s or 0, finish-beginning)
        for finish, request in simulator.finished_requests.values():
            if request.phase == RequestPhase.Increment:
                probe.last_output_s = max(probe.last_output_s or 0, finish-beginning)
        return original_collect(acc, simulator, beginning, ending)
    WindowAccumulator.collect = collect
    try:
        with singleton_profile(multiplier):
            row = fixed_window.run(job['scenario'], 'queue_dag', job['load'], duration, 0,
                job['seed'], deployment/'solution.ini', deployment/'simulator_cluster.ini',
                profile_resources=True, scheduler_factory=factory, compact=True,
                record_query_samples=True, phase_link_probe=probe,
                physical_cluster=physical, machine_counts=TopologyModel(physical).machine_counts,
                trace_override=trace, profile_scheduler=True)
    finally:
        WindowAccumulator.collect = original_collect
    row['admission'] = holder['scheduler'].summary()
    row.update(row['phase_link_profile']['corrected_network_accounting'])
    row['network_accounting'] = 'v4_chunk_aware_v1'
    row['gpu_seconds_per_output_token'] = sum(row['gpu_busy_fraction'].values()) / row['output_throughput_tokens_per_s']
    row['validation_protocol'] = dict(condition=condition, singleton_multiplier=multiplier,
        slow_link_bandwidth_factor=factor, arrival_horizon_s=arrival_horizon,
        observation_horizon_s=duration, trace=trace_metadata,
        runtime_profile='Python simulator control overhead, not real distributed-engine overhead')
    if condition == 'cohort_tail':
        row['evaluation_protocol'] = 'fixed_arrival_prefix_bounded_tail'
        row['cohort'] = dict(completed=row['backlog_at_window_end']==0,
            target_output_tokens=trace_metadata['target_output_tokens'],
            produced_output_tokens=round(row['output_throughput_tokens_per_s']*duration),
            tail_cap_s=duration-arrival_horizon,
            last_completion_s=probe.last_completion_s,
            total_gpu_busy_s=sum(row['gpu_busy_fraction'].values())*duration,
            right_censored_queries=row['backlog_at_window_end'])
    return row
