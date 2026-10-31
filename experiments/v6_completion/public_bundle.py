"""Build a reviewable anonymous evidence bundle after full local rebuild."""
from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, read, sha, write

HERE = Path(__file__).resolve().parent
OUT = HERE / "public_bundle"
PRIVATE = re.compile(r"[A-Za-z]:\\|[A-Za-z]:/(?!/)|/Users/|[\\/]Users[\\/]|Panda|Joseph Williams", re.I)
CAMPAIGNS = ("robustness", "generalization", "session_cost", "session_capacity",
             "weight_search", "weight_online", "bandwidth_threshold", "scalability",
             "failure_replay")


def main():
    assert read(HERE / "REBUILD_AUDIT.json")["passed"]
    sources = [HERE / "STATUS_CN.md",
               ROOT / "experiments/v5_failure_replay/CAUSES_CN.md",
               ROOT / "experiments/v5_failure_replay/cause_classification.csv"]
    for name in ("v5_core_supplement", "v5_model30b_pools", "v5_seed_completion",
                 "v5_kv_stress", "v5_link_models", "v5_parallax", "v5_kv_admission"):
        folder = ROOT / "experiments" / name
        sources += [path for path in (folder / "RESULTS_CN.md", folder / "individual.csv")
                    if path.is_file()]
        sources += list(folder.glob("*.png")) + list(folder.glob("*.pdf"))
    for name in CAMPAIGNS:
        folder = HERE / name
        for file_name in ("RESULTS_CN.md", "individual.csv"):
            path = folder / file_name
            if path.exists():
                sources.append(path)
    sources += [HERE / "session_cost/BATCH_RESULTS_CN.md",
                HERE / "session_cost/decode_batch.csv",
                HERE / "session_capacity/slo_grid.csv",
                HERE / "session_capacity/slo_capacity.csv",
                HERE / "scalability/INTERPRETATION_CN.md"]
    sources += list((HERE / "figures").glob("*.png"))
    sources += list((HERE / "figures").glob("*.pdf"))
    assert all(path.is_file() for path in sources)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for source in sources:
        target = OUT / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix in (".md", ".csv"):
            content = source.read_text(encoding="utf-8-sig").replace(
                "D:/software/miniconda/envs/gllm/python.exe", "python")
            match = PRIVATE.search(content)
            if match:
                raise RuntimeError(f"Potential identifier in {source}: {match.group()}")
            target.write_text(content, encoding="utf-8")
        else:
            shutil.copy2(source, target)
        manifest.append(dict(path=target.relative_to(OUT).as_posix(),
                             sha256=sha(target), source_sha256=sha(source),
                             bytes=target.stat().st_size))
    readme = OUT / "README_CN.md"
    readme.write_text(
        "# RCAPS 匿名实验结果材料\n\n"
        "本包含 CPU 离散事件模拟得出的逐种子汇总表、审计后报告和可重建图表。"
        "真实性与来源哈希请对照内部 REBUILD_AUDIT.json；原始 JSON/日志与完整源码另行发布前需匿名审查。\n\n"
        "P1-2 真机链路微基准与 P2-3 Sarathi 式计算侧 chunked-prefill 按用户范围跳过。"
        "任何容量失败均保留，不填零。\n\n"
        "在含完整原始结果的仓库根目录，Windows gllm 环境中运行 "
        "python -m experiments.v6_completion.rebuild_all 可重新生成全部论文图表、表格和审计。\n",
        encoding="utf-8")
    manifest.append(dict(path="README_CN.md", sha256=sha(readme),
                         bytes=readme.stat().st_size))
    write(OUT / "MANIFEST.json", dict(passed=True, files=manifest,
          scope="Curated anonymous derived evidence; raw artifacts require separate privacy review"))
    archive = HERE / "rcaps_anonymous_evidence.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for item in manifest:
            bundle.write(OUT / item["path"], item["path"])
        bundle.write(OUT / "MANIFEST.json", "MANIFEST.json")
    write(HERE / "PUBLIC_BUNDLE_AUDIT.json", dict(passed=True,
          archive_sha256=sha(archive), files=len(manifest),
          manifest_sha256=sha(OUT / "MANIFEST.json")))
    print("PUBLIC_BUNDLE_PREPARED", len(manifest), flush=True)


if __name__ == "__main__":
    main()
