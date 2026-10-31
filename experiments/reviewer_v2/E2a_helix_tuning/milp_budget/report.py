"""Audit original workspace failures and independent callback-budget replay."""
from __future__ import annotations

import csv
from pathlib import Path

from experiments.v3_search_efficiency.worker import HELIX, ROOT, audit_export
from .run import HERE, check, read, sha, write

RETRY = HERE / "retry_workspace"


def main():
    original_manifest_path = HERE / "formal/manifest.json"
    original_index_path = HERE / "formal/index.json"
    replay_manifest_path = RETRY / "formal/manifest.json"
    replay_index_path = RETRY / "formal/index.json"
    original_manifest = read(original_manifest_path)
    check(original_manifest)
    original_index = read(original_index_path)
    replay_manifest = read(replay_manifest_path)
    replay_index = read(replay_index_path)
    if (original_index["status"] != "terminal" or replay_index["status"] != "terminal" or
            original_index["manifest_sha256"] != sha(original_manifest_path) or
            replay_index["manifest_sha256"] != sha(replay_manifest_path) or
            replay_manifest["original_manifest_sha256"] != sha(original_manifest_path) or
            replay_manifest["original_index_sha256"] != sha(original_index_path)):
        raise RuntimeError("MILP original/replay provenance mismatch")
    jobs = {job["key"]:job for job in original_manifest["jobs"]}
    if set(jobs) != set(original_index["jobs"]) or set(jobs) != set(replay_index["jobs"]):
        raise RuntimeError("MILP key mismatch")
    rows = []
    for key, job in jobs.items():
        original = original_index["jobs"][key]
        replay = replay_index["jobs"][key]
        if original["status"] != "failed" or replay["status"] not in ("completed", "failed"):
            raise RuntimeError("Unexpected MILP job state: "+key)
        original_path = ROOT / original["source"]
        replay_path = ROOT / replay["source"]
        if (sha(original_path) != original["artifact_sha256"] or
                sha(replay_path) != replay["artifact_sha256"] or
                replay_manifest["original_failures"][key]["artifact_sha256"] != original["artifact_sha256"]):
            raise RuntimeError("MILP result artifact hash mismatch: "+key)
        old, outcome = read(original_path), read(replay_path)
        if (old.get("job") != job or "Workspace path is not empty!" not in old.get("error", "") or
                outcome.get("job") != job):
            raise RuntimeError("MILP identity or original cause mismatch: "+key)
        folder = RETRY / "formal/runs" / key
        if (sha(folder / "stdout.txt") != replay["stdout_sha256"] or
                sha(folder / "stderr.txt") != replay["stderr_sha256"]):
            raise RuntimeError("MILP solver log changed: "+key)
        row = dict(case=job["case"], budget_s=job["callback_budget_s"],
            original_status=original["status"], original_error=old["error"],
            original_source=original["source"], replay_status=replay["status"],
            replay_source=replay["source"], replay_exit_code=replay["exit_code"],
            solver_status="", incumbent="", bound="", gap_pct="",
            planning_wall_s="", deployment_valid="", paths="",
            deployment_sha256="", historical_layout_equal="")
        if "model" in outcome:
            model = outcome["model"]
            deployment = outcome["deployment"]
            layout = folder / "layout"
            direct = audit_export(job["case"], layout / "ilp_sol.ini",
                                  layout / "simulator_cluster.ini")
            if (direct != deployment or outcome["input_sha256"] != sha(HELIX[job["case"]]["physical"]) or
                    outcome["profile_sha256"] != sha(HELIX[job["case"]]["profile"]) or
                    outcome["heuristic_sha256"] != sha(HELIX[job["case"]]["warm_start"])):
                raise RuntimeError("MILP deployment/input audit mismatch: "+key)
            if (replay["status"] == "completed") != bool(deployment["valid"]):
                raise RuntimeError("MILP deployment status mismatch: "+key)
            row.update(solver_status=model.get("solver_status"), incumbent=model.get("objective"),
                bound=model.get("objective_bound"),
                gap_pct=100 * model["mip_gap"] if "mip_gap" in model else "",
                planning_wall_s=outcome["total_wall_s"], deployment_valid=deployment["valid"],
                paths=deployment["complete_paths"], deployment_sha256=deployment["solution_sha256"])
        else:
            row["replay_error"] = outcome.get("error", outcome.get("classification"))
        rows.append(row)
    out = HERE / "individual.csv"
    columns = sorted(set().union(*(x.keys() for x in rows)))
    with out.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    lines = ["# E2a 离线 MILP 求解预算诊断", "",
        "原首次四个窗口因运行器将日志写入求解器工作目录，均触发空目录断言；原失败完整保留。",
        "独立重放将日志与 `layout/` 工作目录分离，使用原 Helix 70B ILP 模型与提前停止回调。",
        "仅将回调 max_run_time 从 120 s 改为 480 s；未增加 Gurobi TimeLimit。", "",
        "| 拓扑 | 回调预算 s | 重放状态 | incumbent | bound | Gurobi gap | 有效完整路径 | 规划耗时 s |",
        "|---|---:|---|---:|---:|---:|---:|---:|"]
    for row in rows:
        if isinstance(row["incumbent"], (float, int)):
            lines.append(f"| {row['case']} | {row['budget_s']} | {row['replay_status']} | "
                f"{row['incumbent']:.6g} | {row['bound']:.6g} | {row['gap_pct']:.1f}% | "
                f"{row['paths']} | {row['planning_wall_s']:.1f} |")
        else:
            lines.append(f"| {row['case']} | {row['budget_s']} | {row['replay_status']} | — | — | — | — | — |")
    lines += ["", "该诊断只验证离线规划预算对 incumbent、bound、gap 与导出可行性的影响。",
        "即使候选部署有效，未在相同轨迹下做五种子在线模拟，故不称其延迟或 goodput 优于历史 Helix 放置。",
        "Gurobi gap 非零且可能极大，不能宣称已收敛或达到全局最优。","",
        "## 论文可用表述","",
        "我们对 Helix 原 ILP 模型分别给予 120 s 与 480 s 的回调求解预算，并独立验证导出的部署路径。",
        "求解状态、incumbent、bound、gap 及有效路径数逐条件列于上表。",
        "这些结果说明原 Helix 放置求解仍受预算约束；它们不替代在线调优基线或证明新布局的推理性能。",""]
    (HERE / "RESULTS_CN.md").write_text("\n".join(lines),encoding="utf-8")
    write(HERE / "FINAL_AUDIT.json",dict(passed=True, original_failures=4, replay_windows=4,
        valid_deployments=sum(x["deployment_valid"] is True for x in rows),
        invalid_deployments=sum(x["deployment_valid"] is False for x in rows),
        sources=dict(original_manifest_sha256=sha(original_manifest_path),
                     original_index_sha256=sha(original_index_path),
                     replay_manifest_sha256=sha(replay_manifest_path),
                     replay_index_sha256=sha(replay_index_path)),
        outputs=dict(individual_sha256=sha(out),results_sha256=sha(HERE/"RESULTS_CN.md")),
        script_sha256=sha(Path(__file__))))
    print("MILP diagnostic audited: 4 original workspace failures; 4 independent replays")


if __name__ == "__main__":
    main()
