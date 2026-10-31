"""Wait for preregistered campaigns, then replay failures and rebuild evidence."""
from __future__ import annotations

import collections
import subprocess
import sys
import time
import traceback
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, now, read, write

HERE = Path(__file__).resolve().parent
DIR = HERE / "watchdog"
CAMPAIGNS = ("generalization", "session_cost", "robustness", "weight_online",
             "session_capacity", "bandwidth_threshold", "scalability")


def snapshot():
    state = {}
    for name in CAMPAIGNS:
        index = read(HERE / name / "formal/index.json")
        state[name] = dict(status=index["status"],
                           counts=dict(collections.Counter(
                               x["status"] for x in index["jobs"].values())))
    return state


def command(*args):
    call = [sys.executable, "-u", "-m", *args]
    with (DIR / "steps.log").open("a", encoding="utf-8") as out:
        out.write(f"\n{now()} START {' '.join(call)}\n")
        out.flush()
        result = subprocess.run(call, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT)
        out.write(f"{now()} EXIT {result.returncode}\n")
    if result.returncode:
        raise RuntimeError(f"Command exited {result.returncode}: {' '.join(call)}")


def status_mark(state, **extra):
    payload = dict(updated_at=now(), state=state, campaigns=snapshot(), **extra)
    for attempt in range(20):
        try:
            write(DIR / "status.json", payload)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(min(0.25 * (attempt + 1), 2.0))


def main():
    DIR.mkdir(parents=True, exist_ok=True)
    try:
        while True:
            current = snapshot()
            status_mark("waiting_for_registered_campaigns")
            if all(item["status"] == "terminal" for item in current.values()):
                break
            time.sleep(60)
        status_mark("reporting")
        for name in CAMPAIGNS:
            if name == "scalability":
                command("experiments.v6_completion.scalability", "report")
            else:
                command("experiments.v6_completion." + name, "--report")
            assert read(HERE / name / "FINAL_AUDIT.json")["passed"]
        command("experiments.v6_completion.session_batch_report")
        assert read(HERE / "session_cost/BATCH_AUDIT.json")["passed"]
        status_mark("replaying_failed_windows")
        command("experiments.v6_completion.failure_replay", "--workers", "6")
        command("experiments.v6_completion.freeze_campaign", "failure_replay")
        assert read(HERE / "failure_replay/FINAL_AUDIT.json")["passed"]
        status_mark("rebuilding_paper_evidence")
        command("experiments.v6_completion.rebuild_all")
        assert read(HERE / "REBUILD_AUDIT.json")["passed"]
        lines = ["# V6 实验最终状态", "",
                 "所有登记的 CPU 离散事件模拟批次已经终结；数值与失败原因见各批 RESULTS_CN.md。",
                 "真机网络微基准 P1-2 和 Sarathi 计算侧 chunked-prefill P2-3 按用户范围跳过。", "",
                 "| 批次 | 完成 | 失败 | 状态 |", "|---|---:|---:|---|"]
        for name, item in snapshot().items():
            counts = item["counts"]
            lines.append(f"| {name} | {counts.get('completed', 0)} | "
                         f"{counts.get('failed', 0)} | {item['status']} |")
        replay = read(HERE / "failure_replay/FINAL_AUDIT.json")
        lines += ["", f"独立诊断重放 {replay['windows']} 个 V6 失败键；"
                  "重放成功不自动替换首轮结果或成为新种子。",
                  "图表、表格、匿名衍生证据包及总重建审计均已生成。"]
        (HERE / "STATUS_CN.md").write_text(chr(10).join(lines) + chr(10),
                                           encoding="utf-8")
        command("experiments.v6_completion.public_bundle")
        assert read(HERE / "PUBLIC_BUNDLE_AUDIT.json")["passed"]
        status_mark("complete")
    except BaseException as exc:
        write(DIR / "error.json", dict(at=now(), error=repr(exc),
                                       traceback=traceback.format_exc()))
        status_mark("needs_attention", error=repr(exc))
        raise


if __name__ == "__main__":
    main()
