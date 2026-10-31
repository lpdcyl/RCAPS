"""Per-request SLO goodput over the existing warmup-and-drain protocol."""
from __future__ import annotations

from collections import defaultdict

from experiments.v5_core_supplement.drain import DrainProbe

SLO = {
    "single": {"strict": (4.0, 0.4), "medium": (6.0, 0.6),
               "loose": (10.0, 1.0)},
    "multi": {"strict": (6.0, 0.5), "medium": (10.0, 0.8),
              "loose": (15.0, 1.2)},
}


class GoodputProbe(DrainProbe):
    def __init__(self, setup, case, tail_cap=3600, warmup=300, measurement=1800):
        super().__init__(setup, tail_cap, warmup, measurement)
        self.case = case
        self.busy = defaultdict(float)
        self.last_busy_interval = {}

    def install(self, simulator, beginning, ending):
        super().install(simulator, beginning, ending)
        self.deployed_gpu_count = sum(bool(node.in_vram_model_layers)
                                      for node in simulator.compute_nodes.values())
        if self.deployed_gpu_count <= 0:
            raise RuntimeError("No deployed GPU in goodput probe")
        for node in simulator.compute_nodes.values():
            original = node.start_execution
            uid = node.node_uid

            def start_execution(*args, _original=original, _uid=uid, **kwargs):
                batch = _original(*args, **kwargs)
                start, finish = simulator.current_time, simulator.current_time + batch.duration
                self.busy[_uid] += max(0.0, min(finish, ending+self.tail_cap) -
                                        max(start, beginning))
                self.last_busy_interval[_uid] = (start, finish)
                return batch

            node.start_execution = start_execution

    def summary(self, samples):
        result = super().summary(samples)
        drain = result["drain"]
        stop = self.end + drain["tail_elapsed_s"]
        busy_by_gpu = {}
        for uid, used in self.busy.items():
            start, finish = self.last_busy_interval[uid]
            beyond_stop = max(0.0, min(finish, self.end+self.tail_cap) -
                              max(start, stop))
            busy_by_gpu[str(uid)] = max(0.0, used - beyond_stop)
        total_busy = sum(busy_by_gpu.values())
        measures = drain["query_samples"]
        thresholds = SLO[self.case]
        tiers = {}
        for name, (ttft_limit, tpot_limit) in thresholds.items():
            accepted = [row for row in measures
                        if row["completed"] and row["output_tokens"] >= 2
                        and row["ttft_s"] is not None and row["tpot_s"] is not None
                        and row["ttft_s"] <= ttft_limit and row["tpot_s"] <= tpot_limit]
            tokens = sum(row["output_tokens"] for row in accepted)
            rate = tokens / self.measurement
            tiers[name] = dict(ttft_limit_s=ttft_limit, tpot_limit_s=tpot_limit,
                               qualified_requests=len(accepted),
                               qualified_output_tokens=tokens,
                               goodput_tokens_per_s=rate,
                               goodput_tokens_per_s_per_gpu=rate/self.deployed_gpu_count,
                               qualified_tokens_per_gpu_busy_s=(
                                   tokens/total_busy if total_busy > 0 else None))
        counts = [tiers[name]["qualified_requests"] for name in ("strict", "medium", "loose")]
        if counts != sorted(counts):
            raise RuntimeError("SLO tiers are not monotone")
        result["goodput"] = dict(case=self.case, measurement_s=self.measurement,
            tail_stop_s=stop, deployed_gpu_count=self.deployed_gpu_count,
            gpu_busy_seconds_measurement_and_tail=total_busy,
            gpu_busy_seconds_by_uid=busy_by_gpu,
            measurement_arrivals=len(measures),
            completed_by_tail=drain["completed"],
            right_censored=drain["right_censored"],
            excluded_under_two_output_tokens=sum(x["output_tokens"] < 2 for x in measures),
            tiers=tiers,
            busy_scope="All deployed GPU computation from measurement start through drain stop; includes competing warmup traffic.")
        return result
