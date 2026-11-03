"""List safe one-key commands after all completion replays are audited."""
from __future__ import annotations

from collections import Counter

from experiments.v5_core_supplement.run import ROOT

from .manual_failed_key import SOURCES, selected


def main():
    lines = ["# RCAPS 补全实验剩余失败键手工命令", "",
             "这些命令只用于新增独立诊断目录；成功也不能回填正式五种子组。",
             "每个键执行前都会核对原正式失败、最近独立失败和审计 SHA256。",
             "已有输出目录会拒绝覆盖。每条命令均需要在 PowerShell 中单独运行。", ""]
    counts = Counter()
    for campaign, (base, _) in SOURCES.items():
        from experiments.v5_core_supplement.run import read

        index = read(base / "index.json")
        manifest = read(base / "manifest.json")
        campaign_keys = {item["key"] for item in manifest["jobs"]
                         if campaign == "milp" or item["campaign"] == campaign}
        keys = sorted(key for key, state in index["jobs"].items()
                      if state["status"] == "failed" and key in campaign_keys)
        lines.extend([f"## {campaign.upper()}：{len(keys)} 键", ""])
        for key in keys:
            item, state, formal, _ = selected(campaign, key)
            output = ROOT / "experiments" / "manual_completion_after_audited_replay_20261103" / campaign / key
            if output.exists():
                raise RuntimeError("Manual output already exists: " + str(output))
            relative = output.relative_to(ROOT).as_posix()
            lines.extend([f"### {key}", "",
                          f"正式失败 SHA256：{formal['artifact_sha256']}；最新独立失败 SHA256：{state['artifact_sha256']}。", "",
                          "~~~powershell", "$ErrorActionPreference = 'Stop'",
                          "Set-Location 'D:/PythonProject/Helix-GREEN'",
                          ". 'D:/software/miniconda/shell/condabin/conda-hook.ps1'",
                          "conda activate gllm",
                          f"python -m experiments.reviewer_v2.completion_20261101.manual_failed_key --campaign '{campaign}' --key '{key}' --output '{relative}'",
                          "~~~", ""])
            counts[campaign] += 1
    target = ROOT / "experiments/reviewer_v2/completion_20261101/MANUAL_FAILED_KEY_COMMANDS_CN.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    print(target, dict(counts))


if __name__ == "__main__":
    main()
