"""Build one PowerShell command for every unresolved audited failure key."""
from collections import Counter
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, read
from .manual_rerun import verify_registry


INDEXES = {
    'E2b': 'experiments/reviewer_v2/E2b_parallax/failure_replay_round2/index.json',
    'E3b': 'experiments/reviewer_v2/E3b_goodput/failure_replay/index.json',
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
    retry_audit = read(ROOT / 'experiments/reviewer_v2/remaining_failure_retry_20261031/FINAL_AUDIT.json')
    if not retry_audit['passed'] or retry_audit['registered'] != 254:
        raise RuntimeError('Independent retry audit incomplete')
    retries = {(row['group'], row['key']): row for row in retry_audit['rows']}
    if len(retries) != 254:
        raise RuntimeError('Duplicate retry key')
    for group, rel in INDEXES.items():
        index, audit = read(ROOT / rel), read(ROOT / AUDITS[group])
        if index['status'] != 'terminal' or not audit['passed']:
            raise RuntimeError('Unaudited source: ' + group)
        keys = sorted(k for k, v in index['jobs'].items()
                      if v['status'] == 'failed' and retries[(group, k)]['status'] == 'failed')
        lines = [f'## {group}：{len(keys)} 个未解决键', '', f'来源：{AUDITS[group]}。', '']
        for n, key in enumerate(keys, 1):
            _, _, original, last = verify_registry(group, key)
            if group == 'E3b' and audit['replay_failed'] != audit['original_failed']:
                raise RuntimeError('E3b replay population changed')
            latest = retries[(group, key)]
            output = f'experiments/manual_reruns_after_auto_20261101/{group}/{key}'
            if (ROOT / output).exists():
                raise RuntimeError('Manual output already exists: ' + output)
            lines.extend([f'### {group} {n:03d} · {key}', '',
                f'原失败 SHA256：{original["artifact_sha256"]}；先前重放失败 SHA256：{last["artifact_sha256"]}；本轮独立重跑失败 SHA256：{latest["artifact_sha256"]}。', '',
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
    e6_path = ROOT / 'experiments/reviewer_v2/E6_cumulative/failure_replay/FINAL_AUDIT.json'
    e6 = read(e6_path)
    if (not e6['passed'] or e6['formal_registered'] != 60 or e6['replay_registered'] != 13
            or e6['replay_failed'] != 4):
        raise RuntimeError('E6 replay audit incomplete')
    e6_failed = sorted((row for row in e6['rows'] if row['replay_status'] == 'failed'),
                       key=lambda row: row['key'])
    e6_lines = ['## E6：4 个独立重放后仍失败键', '',
                'E6 原正式 47/60、独立重放 9/13；下面四键仍失败。两批结果分别审计，不合并正式成功率。', '']
    for n, row in enumerate(e6_failed, 1):
        key = row['key']
        output = f'experiments/manual_e6_reruns_after_replay_20261101/{key}'
        if (ROOT / output).exists():
            raise RuntimeError('E6 manual output already exists: ' + output)
        e6_lines.extend([f'### E6 {n:03d} · {key}', '',
            f'原正式失败 SHA256：{row["original_sha256"]}；独立重放失败 SHA256：{row["replay_sha256"]}。', '',
            '~~~powershell', "$ErrorActionPreference = 'Stop'",
            "Set-Location 'D:/PythonProject/Helix-GREEN'",
            ". 'D:/software/miniconda/shell/condabin/conda-hook.ps1'",
            'conda activate gllm',
            "if ($env:CONDA_DEFAULT_ENV -ne 'gllm' -or $env:CONDA_PREFIX -notlike '*gllm') { throw 'gllm 未激活' }",
            f"python -u -m experiments.reviewer_v2.E6_cumulative.manual_rerun --key '{key}' --output '{output}'",
            '~~~', ''])
    counts['E6'] = len(e6_failed)
    sections.extend(e6_lines)
    intro = ['# RCAPS 剩余失败键手工独立重跑命令', '',
             f'共 {total + counts["E6"]} 键：' + '；'.join(f'{g} {counts[g]}' for g in counts) + '。', '',
             '254 键独立重跑已审计：22 成功、232 失败。以下仅列本轮后仍失败的键；原正式结果与先前重放均保留。',
             'E6 原正式失败 13 键，独立重放成功 9、仍失败 4。各段均从项目根目录执行、真正激活 conda gllm，并写入新的独立输出目录。',
             '已有输出目录会拒绝覆盖；若需再试，请保留原件并指定另一新目录。重跑成功不能替换原正式失败。',
             '结果见各输出目录的 index.json、worker.log、result.json 或 failure.json。',
             'E5b 原 formal 冒烟门槛未达，因此其命令只针对预登记的修订边界诊断。', '',
             '## E4：WSL2 网络微基准', '',
             '150 次测量已审计：149 成功、1 次启动后中断，原件位于 E4_tcp_wsl/runs/12p5MBps/priority/repeat0；不属于上述 Windows gllm 键。',
             '该中断键已在独立目录 E4_tcp_wsl/interrupted_replay_20261101 复测成功，原失败和原批 149/150 口径保持不变。',
             'E4 独立补测不属于下面 Windows gllm 失败键。', '']
    target = Path(__file__).resolve().parent / 'MANUAL_RERUN_COMMANDS_CN.md'
    target.write_text(chr(10).join(intro + sections) + chr(10), encoding='utf-8')
    print(target, dict(counts), 'total', total + counts['E6'])


if __name__ == '__main__':
    main()
