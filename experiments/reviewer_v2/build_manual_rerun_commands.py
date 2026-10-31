"""Build one PowerShell command for every unresolved audited failure key."""
from collections import Counter
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, read
from .manual_rerun import verify_registry


INDEXES = {
    'E2b': 'experiments/reviewer_v2/E2b_parallax/failure_replay_round2/index.json',
    'E3b': 'experiments/reviewer_v2/E3b_goodput/formal/index.json',
    'E5a': 'experiments/reviewer_v2/E5_scale_kv/E5a_failure_replay/index.json',
    'E5b': 'experiments/reviewer_v2/E5_scale_kv/E5b/boundary_failure_replay/index.json',
    'V5': 'experiments/v5_failure_replay/formal/index.json',
    'V6': 'experiments/v6_completion/failure_replay/formal/index.json',
}
AUDITS = {
    'E2b': 'experiments/reviewer_v2/E2b_parallax/failure_replay_round2/FINAL_AUDIT.json',
    'E3b': 'experiments/reviewer_v2/E3b_goodput/FINAL_AUDIT.json',
    'E5a': 'experiments/reviewer_v2/E5_scale_kv/E5a_failure_replay/FINAL_AUDIT.json',
    'E5b': 'experiments/reviewer_v2/E5_scale_kv/E5b/boundary_failure_replay/FINAL_AUDIT.json',
    'V5': 'experiments/v5_failure_replay/FINAL_AUDIT.json',
    'V6': 'experiments/v6_completion/failure_replay/FINAL_AUDIT.json',
}


def main():
    sections, counts = [], Counter()
    for group, rel in INDEXES.items():
        index, audit = read(ROOT / rel), read(ROOT / AUDITS[group])
        if index['status'] != 'terminal' or not audit['passed']:
            raise RuntimeError('Unaudited source: ' + group)
        keys = sorted(k for k, v in index['jobs'].items() if v['status'] == 'failed')
        lines = [f'## {group}：{len(keys)} 个未解决键', '', f'来源：{AUDITS[group]}。', '']
        for n, key in enumerate(keys, 1):
            _, _, original, last = verify_registry(group, key)
            if group == 'E3b' and audit['replay_failed'] != audit['original_failed']:
                raise RuntimeError('E3b replay population changed')
            output = f'experiments/manual_reruns/{group}/{key}'
            if (ROOT / output).exists():
                raise RuntimeError('Manual output already exists: ' + output)
            lines.extend([f'### {group} {n:03d} · {key}', '',
                f'原失败 SHA256：{original["artifact_sha256"]}；最后重放失败 SHA256：{last["artifact_sha256"]}。', '',
                '~~~powershell',
                "$ErrorActionPreference = 'Stop'",
                "Set-Location 'D:/PythonProject/Helix-GREEN'",
                ". 'D:/software/miniconda/shell/condabin/conda-hook.ps1'",
                'conda activate gllm',
                "if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }",
                f"python -u -m experiments.reviewer_v2.manual_rerun --group '{group}' --key '{key}' --output '{output}'",
                '~~~', ''])
            counts[group] += 1
        sections.extend(lines)
    total = sum(counts.values())
    intro = ['# RCAPS 剩余失败键手工独立重跑命令', '',
             f'共 {total} 键：' + '；'.join(f'{g} {counts[g]}' for g in INDEXES) + '。', '',
             '每段均从项目根目录执行、真正激活 conda gllm，并写入新的 experiments/manual_reruns 子目录。',
             '已有输出目录会拒绝覆盖；若需再试，请保留原件并指定另一新目录。重跑成功不能替换原正式失败。',
             '结果见各输出目录的 index.json、worker.log、result.json 或 failure.json。',
             'E5b 原 formal 冒烟门槛未达，因此其命令只针对预登记的修订边界诊断。', '',
             '## E4：由用户在 WSL2 执行', '',
             'E4 不属于上述 Windows gllm 逐键重跑；需 WSL2 的 python3、ip、tc 和 sudo 权限。', '',
             '~~~bash',
             'cd /mnt/d/PythonProject/Helix-GREEN',
             'python3 experiments/reviewer_v2/E4_tcp_wsl/bench.py --prepare',
             'sudo python3 experiments/reviewer_v2/E4_tcp_wsl/bench.py --preflight',
             'sudo python3 experiments/reviewer_v2/E4_tcp_wsl/bench.py --run | tee experiments/reviewer_v2/E4_tcp_wsl/console.log',
             'python3 experiments/reviewer_v2/E4_tcp_wsl/bench.py --report',
             '~~~', '',
             'E4 共 3 速率×5 模式×10 次测量。', '']
    target = Path(__file__).resolve().parent / 'MANUAL_RERUN_COMMANDS_CN.md'
    target.write_text(chr(10).join(intro + sections) + chr(10), encoding='utf-8')
    print(target, dict(counts), 'total', total)


if __name__ == '__main__':
    main()
