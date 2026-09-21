"""Optional slow CBGP checks for end-to-end scheduler integration."""

from __future__ import annotations

from dataclasses import dataclass

from src.analysis.breakpoint import PlacementSignature, placement_signature
from src.analysis.carbon_bottleneck import analyze_carbon_bottlenecks
from src.carbon.config import CBGPConfig
from src.carbon.model import CarbonCostModel, EnergyProvider
from src.graph.serving_graph import LayerPlacement, ModelProfile, ThroughputProvider
from src.graph.topology import ClusterTopology
from src.optimizer.cbgp import CBGPResult, solve_cbgp
from src.scheduler.carbon_flow_scheduler import FlowSchedule


@dataclass(frozen=True, slots=True)
class PlacementUpdate:
    timestamp: float
    invoked: bool
    accepted: bool
    placement_changed: bool
    reason: str
    cbgp_result: CBGPResult | None


class SlowCBGPController:
    """Run CBGP only after persistent structural bottleneck observations."""

    def __init__(
        self,
        topology: ClusterTopology,
        model: ModelProfile,
        initial_placement: LayerPlacement,
        throughput_provider: ThroughputProvider,
        energy_provider: EnergyProvider,
        config: CBGPConfig,
        *,
        phase: str,
        batch_size: int,
        placement_check_interval_seconds: float,
        persistence_intervals: int,
        minimum_dwell_seconds: float,
    ) -> None:
        if placement_check_interval_seconds <= 0.0:
            raise ValueError("placement_check_interval_seconds must be positive")
        if persistence_intervals <= 0:
            raise ValueError("persistence_intervals must be positive")
        if minimum_dwell_seconds < 0.0:
            raise ValueError("minimum_dwell_seconds cannot be negative")
        self.topology = topology
        self.model = model
        self.current_placement = initial_placement
        self.throughput_provider = throughput_provider
        self.energy_provider = energy_provider
        self.config = config
        self.phase = phase
        self.batch_size = batch_size
        self.placement_check_interval_seconds = placement_check_interval_seconds
        self.persistence_intervals = persistence_intervals
        self.minimum_dwell_seconds = minimum_dwell_seconds
        self._last_check: float | None = None
        self._last_change: float = float("-inf")
        self._persistent_count = 0
        self.invocation_count = 0
        self.accepted_count = 0

    def maybe_update(
        self,
        timestamp: float,
        schedule: FlowSchedule,
    ) -> PlacementUpdate:
        now = float(timestamp)
        if (
            self._last_check is not None
            and now - self._last_check < self.placement_check_interval_seconds
        ):
            return PlacementUpdate(now, False, False, False, "check_not_due", None)
        self._last_check = now
        carbon_model = CarbonCostModel.build(
            self.topology,
            self.model,
            self.current_placement,
            self.energy_provider,
            schedule.ci_snapshot,
            phase=self.phase,
            batch_size=self.batch_size,
        )
        report = analyze_carbon_bottlenecks(
            schedule.serving_graph,
            carbon_model,
            schedule.flow_result,
            utilization_threshold=self.config.bottleneck_utilization_threshold,
            tolerance=self.config.solver_tolerance,
        )
        structural = bool(
            report.saturated_compute_gpus
            and report.low_carbon_headroom_gpus
            and any(signal.bottleneck_relevant for signal in report.boundary_signals)
        )
        self._persistent_count = self._persistent_count + 1 if structural else 0
        if not structural:
            return PlacementUpdate(now, False, False, False, "no_structural_bottleneck", None)
        if self._persistent_count < self.persistence_intervals:
            return PlacementUpdate(now, False, False, False, "persistence_not_met", None)
        if now - self._last_change < self.minimum_dwell_seconds:
            return PlacementUpdate(now, False, False, False, "minimum_dwell_not_met", None)

        self.invocation_count += 1
        result = solve_cbgp(
            self.topology,
            self.model,
            self.throughput_provider,
            self.energy_provider,
            schedule.ci_snapshot,
            self.current_placement,
            schedule.served_throughput,
            self.config,
            phase=self.phase,
            batch_size=self.batch_size,
        )
        changed = placement_signature(result.placement) != placement_signature(
            self.current_placement
        )
        if changed:
            self.current_placement = result.placement
            self.accepted_count += 1
            self._last_change = now
            self._persistent_count = 0
            return PlacementUpdate(now, True, True, True, "cbgp_improvement", result)
        return PlacementUpdate(now, True, False, False, result.termination_reason, result)
