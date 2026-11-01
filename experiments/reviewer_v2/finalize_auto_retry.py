"""Publish independent retry audit, summary, and commands after terminal state."""
from collections import Counter, defaultdict
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, read
from experiments.reviewer_v2.audit_auto_retry import main as audit_retries
from experiments.reviewer_v2.auto_retry_remaining import BATCH
from experiments.reviewer_v2.build_manual_rerun_commands import AUDITS, main as build_commands

HERE = Path(__file__).resolve().parent


def main():
    audit_retries()
    report = read(BATCH / 'FINAL_AUDIT.json')
    if not report['passed'] or report['registered'] != 254:
        raise RuntimeError('Retry audit is not complete')
    by_group = defaultdict(list)
    for row in report['rows']:
        by_group[row['group']].append(row)
    lines = ['# RCAPS 剩余失败键新一轮独立重跑结果', '',
             '所有 254 个键在原先已审计的失败之外各进行一次新尝试，采用真正激活的 conda gllm，先串行后最多 2 worker，独立输出目录。',
             '新重跑不是新随机种子，不替换正式批次，也不把失败填零。', '',
             '| 来源 | 本轮登记 | 新成功 | 仍失败 | 原审计 |',
             '|---|---:|---:|---:|---|']
    for group, rows in by_group.items():
        good = sum(row['status'] == 'completed' for row in rows)
        lines.append(f'| {group} | {len(rows)} | {good} | {len(rows)-good} | {AUDITS[group]} |')
    lines.extend(['', f'总计：{report["completed"]}/{report["registered"]} 新成功，{report["failed"]} 仍失败。', '',
                  '失败类别按本轮结果逐键见 FINAL_AUDIT.json；不能用新的成功数重算原正式实验成功率。', ''])
    for group, rows in by_group.items():
        causes = Counter(row['category'] for row in rows if row['status'] == 'failed')
        lines.append(f'- {group} 仍失败类型：' + ('；'.join(f'{name} {count}' for name,count in sorted(causes.items())) if causes else '无'))
    (BATCH / 'RESULTS_CN.md').write_text(chr(10).join(lines) + chr(10), encoding='utf-8')
    build_commands()
    print('FINALIZED',report['completed'],report['failed'],HERE / 'MANUAL_RERUN_COMMANDS_CN.md')


if __name__ == '__main__':
    main()
