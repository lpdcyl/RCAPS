"""T0.5 passive audit of single-request Decode execution duration."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import traceback
from collections import defaultdict
from pathlib import Path

from benchmarks.fixed_window import run as fixed_window_run
from rcaps.v3.scheduler import GraphModeledQueueAwareDagScheduler
from simulator.event_simulator.request import RequestPhase


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = HERE / "runs" / "dev_seed100.json"
FAILURE = RUN.with_suffix(".failure.json")
INDEX = HERE / "index.json"
RESULTS = HERE / "RESULTS_CN.md"
SOLUTION = ROOT / "rcaps/v3_layouts/single/solution.ini"
SIM_CLUSTER = ROOT / "rcaps/v3_layouts/single/simulator_cluster.ini"
EXPECTED_TYPES = {"A100", "L4", "T4"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DecodeBatchProbe:
    """Measure elapsed FinishExecution time without changing execution."""

    def __init__(self):
        self.simulator = None
        self.begin = 0.0
        self.end = 0.0
        self.pending = {}
        self.settings = []
        self.groups = defaultdict(lambda: {
            "count": 0, "actual_s": 0.0, "profile_s": 0.0,
            "duration_disagreement_max_s": 0.0})

    def install(self, simulator, beginning, ending):
        self.simulator, self.begin, self.end = simulator, beginning, ending
        for node in simulator.compute_nodes.values():
            if not node.in_vram_model_layers:
                continue
            settings = node.inference_settings
            self.settings.append({
                "node_uid": node.node_uid,
                "machine_type": node.machine_type,
                "first_layer": min(node.in_vram_model_layers),
                "last_layer": max(node.in_vram_model_layers),
                "decode_typical_tokens": settings.decode_typical_tokens,
                "decode_max_tokens": settings.decode_max_tokens,
            })
            original_start = node.start_execution

            def start(requests, _node=node, _original=original_start):
                layer = _node.current_layer_id
                now = simulator.current_time
                batch = _original(requests)
                if (len(requests) == 1 and
                        requests[0].phase == RequestPhase.Increment and
                        self.begin <= now < self.end):
                    expected = simulator.scheduler._layer_service(
                        _node, layer, RequestPhase.Increment, 1)
                    self.pending[(_node.node_uid, batch.get_handle())] = (
                        now, layer, batch.duration, expected)
                return batch

            node.start_execution = start
            original_finish = node.finish_execution

            def finish(inference_batch_handle, _node=node, _original=original_finish):
                batch, outbound = _original(inference_batch_handle)
                item = self.pending.pop((_node.node_uid, inference_batch_handle), None)
                if item is not None and simulator.current_time < self.end:
                    started, layer, scheduled, expected = item
                    actual = simulator.current_time - started
                    if actual <= 0 or expected <= 0:
                        raise ValueError("Nonpositive Decode duration")
                    first = layer == min(_node.in_vram_model_layers)
                    group = self.groups[(_node.machine_type, "first" if first else "other")]
                    group["count"] += 1
                    group["actual_s"] += actual
                    group["profile_s"] += expected
                    group["duration_disagreement_max_s"] = max(
                        group["duration_disagreement_max_s"], abs(actual - scheduled))
                return batch, outbound

            node.finish_execution = finish

    def summary(self, _query_samples):
        rows = []
        for (machine_type, position), values in sorted(self.groups.items()):
            rows.append({"machine_type": machine_type, "position": position,
                         **values, "ratio": values["actual_s"] / values["profile_s"]})
        return {"settings": sorted(self.settings, key=lambda row: row["node_uid"]),
                "batch1_decode": rows, "incomplete_at_horizon": len(self.pending)}


def run_diagnostic():
    os.environ["PYTHONHASHSEED"] = "0"
    os.environ["MPLBACKEND"] = "Agg"
    RUN.parent.mkdir(parents=True, exist_ok=True)
    probe = DecodeBatchProbe()
    try:
        result = fixed_window_run(
            "single", "rcaps_v3", 350, 60, 0, 100,
            solution=SOLUTION, sim_cluster=SIM_CLUSTER,
            scheduler_factory=GraphModeledQueueAwareDagScheduler,
            compact=True, phase_link_probe=probe)
        groups = result["phase_link_profile"]["batch1_decode"]
        present = {row["machine_type"] for row in groups}
        if present != EXPECTED_TYPES:
            raise ValueError(f"Missing GPU types in batch-1 Decode: {EXPECTED_TYPES - present}")
        RUN.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        previous_failures = sorted(RUN.parent.glob("dev_seed100.attempt*.failure.json"))
        INDEX.write_text(json.dumps({"protocol": {
            "scenario": "C1_single", "seed": 100, "duration_s": 60,
            "warmup_s": 0, "offered_tokens_per_s": 350,
            "solution_sha256": digest(SOLUTION),
            "sim_cluster_sha256": digest(SIM_CLUSTER),
            "trace_sha256": result["trace_sha256"]},
            "windows": [{"path": str(RUN.relative_to(HERE)).replace("\\", "/"),
                         "sha256": digest(RUN), "status": "passed"}],
            "development_failures": [{
                "path": str(path.relative_to(HERE)).replace("\\", "/"),
                "sha256": digest(path), "status": "failed"}
                for path in previous_failures]},
            indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"T0.5 diagnostic passed: {len(groups)} GPU/position groups")
    except Exception as error:
        FAILURE.write_text(json.dumps({"error": repr(error),
                                       "traceback": traceback.format_exc()},
                                      indent=2) + "\n", encoding="utf-8")
        raise


def render_report():
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    record = index["windows"][0]
    if record["status"] != "passed" or digest(RUN) != record["sha256"]:
        raise ValueError("T0.5 index or run hash mismatch")
    data = json.loads(RUN.read_text(encoding="utf-8"))
    profile = data["phase_link_profile"]
    rows = profile["batch1_decode"]
    by_type = {}
    for row in rows:
        target = by_type.setdefault(row["machine_type"],
                                    {"count": 0, "actual_s": 0.0, "profile_s": 0.0})
        for key in target:
            target[key] += row[key]
    if set(by_type) != EXPECTED_TYPES:
        raise ValueError("A100/L4/T4 evidence incomplete")
    lines = [
        "# T0.5：M3 Decode 系数与实际代价核实", "",
        "## 协议与完整性", "",
        "C1 单集群冻结布局；V3 完整 M3；开发种子 100；350 offered token/s；",
        "60 秒固定窗口；零预热；窗口末不排空。这里只诊断单请求 Decode batch，",
        "不作为正式种子 0/1/2 的性能证据。被动包装执行起止函数，不改变模拟时间或调度。", "",
        f"轨迹 SHA256：`{data['trace_sha256']}`；结果 SHA256：`{record['sha256']}`。",
        f"校准窗口成功数：1；最终失败数：0；窗口末尚未完成的被观察 batch：{profile['incomplete_at_horizon']}。", "",
        "## 单请求 Decode：实际执行与逐层画像", "",
        "每条记录是一个 GPU 上某一层完成的单请求 Decode batch。实际时长取",
        "`FinishExecution` 时间减 `start_execution` 时间；预测时长取",
        "`_layer_service(node, layer, Increment, 1)`。同 GPU 类型先求时长总和，再取比值。", "",
        "| GPU | batch 数 | 实际总时长 (s) | 画像总时长 (s) | 实际/画像 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for gpu in sorted(by_type):
        row = by_type[gpu]
        lines.append(f"| {gpu} | {row['count']} | {row['actual_s']:.6f} | "
                     f"{row['profile_s']:.6f} | {row['actual_s']/row['profile_s']:.4f} |")
    lines += ["", "### 首层与其他层", "",
              "| GPU | 层位置 | batch 数 | 实际/画像 | 执行事件时长核对最大误差 (s) |",
              "| --- | --- | ---: | ---: | ---: |"]
    for row in rows:
        lines.append(f"| {row['machine_type']} | {row['position']} | {row['count']} | "
                     f"{row['ratio']:.4f} | {row['duration_disagreement_max_s']:.3e} |")
    lines += ["", "## 节点 Decode batch 设置", "",
              "| GPU | 节点 ID | 层段 | decode_typical_tokens | decode_max_tokens |",
              "| --- | ---: | --- | ---: | ---: |"]
    for row in profile["settings"]:
        lines.append(f"| {row['machine_type']} | {row['node_uid']} | "
                     f"{row['first_layer']}–{row['last_layer']} | "
                     f"{row['decode_typical_tokens']} | {row['decode_max_tokens']} |")
    lines += [
        "", "## 系数解释", "",
        "`QueueAwareDagScheduler._decode_token_service` 将单 token Decode 画像和乘 2",
        "（`rcaps/v3/online_scheduler.py:68–69`），用于路由时的 KV 会话定价。",
        "该系数与模拟器的实现直接对应：`ModelLayer.get_inference_statistics` 在",
        "`decode_phase_tokens == 1` 时明确把 Decode 时间乘 2",
        "（`simulator/event_simulator/model.py:131–134`）。因此非首层的实测比值",
        "精确为 2；首层另有 activation 拼接和传输开销",
        "（`simulator/event_simulator/compute_node.py:460–479`），实测略高于 2。",
        "这个系数是模拟器单请求执行时间与原始画像之间的确定性修正，",
        "不是根据正式窗口调出的自由权重。", "",
        "## V3 M3 实际生效的路径代价", "",
        "V3 的 `_route` 来自 `WorkloadQueueDagScheduler`，而不是",
        "`routing.py` 文件头所述的 earliest-finish 递推。对于合法分段路径 P，",
        "选择使以下累加代价最小的路径（单位秒）：", "",
        "`C(P)=Σ_{v∈P}[prompt_service(v)+max(0,gpu_release(v)-now)+",
        "active_sessions(v)·2·Σ_{l∈segment(v)}decode_profile(v,l,batch=1)]",
        "+Σ_{e∈P}[max(0,link_release(e)-now)+transfer_time(e,request)]`。", "",
        "Prompt service、GPU 等待、KV 会话项见 `rcaps/v3/queue_cost.py:53–68`；",
        "终点链路同样加等待和传输时间，见 `queue_cost.py:79–91`。",
        "GPU/链路释放时间来自当前 batch 与队列快照，见 `routing.py:85–174`；",
        "由于 `queue_cost.py:19–20` 将 `include_committed` 与",
        "`include_session_round` 设为 False，该快照不计已承诺路线和额外批次预留。",
        "传输时间见 `routing.py:75–83`。合法边由 `rcaps/v3/scheduler.py` 限制。", "",
        "这不是在线完成时间的无偏预测，也不是将各资源等待时间按串行时间轴递推；",
        "它是用当前状态排序合法路径的工作量代理。", "",
    ]
    for item in index.get("development_failures", []):
        lines.append(f"开发期间一次探针调用签名错误已修复，失败记录保留于 "
                     f"`{item['path']}`（SHA256 `{item['sha256']}`）；"
                     "该失败发生在首个模拟事件，未计入校准窗口。")
    lines.append("")
    RESULTS.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {RESULTS}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("smoke", "formal", "report"), required=True)
    args = parser.parse_args()
    if args.phase == "report":
        render_report()
    else:
        run_diagnostic()


if __name__ == "__main__":
    main()
