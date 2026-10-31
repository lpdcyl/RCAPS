"""Strict E2b audit: preserve original failures and only summarize complete groups."""
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev

from experiments.v5_core_supplement.run import ROOT, read, sha
from experiments.reviewer_v2.E2b_parallax.run import HERE, paths, check

METRICS=('tpot_p95_s','ttft_p95_s','output_throughput_tokens_per_s',
         'completion_fraction','gpu_seconds_per_output_token')
T4=2.7764451051977987


def main():
    manifest_path=HERE/'formal/manifest.json'
    index_path=HERE/'formal/index.json'
    manifest=read(manifest_path)
    index=read(index_path)
    check(manifest)
    if index['status']!='terminal' or index['manifest_sha256']!=sha(manifest_path):
        raise RuntimeError('E2b formal not terminal')
    if set(index['jobs'])!={j['key'] for j in manifest['jobs']}:
        raise RuntimeError('E2b job keys differ from manifest')
    baseline={}
    with (ROOT/'experiments/v5_core_supplement/individual.csv').open(newline='',encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if row['cell']=='V4':
                baseline[(row['scenario'],int(row['load']),int(row['seed']))]=row
    rows=[]
    groups=defaultdict(dict)
    failures=Counter()
    for job in manifest['jobs']:
        key=job['key']
        entry=index['jobs'][key]
        artifact=ROOT/entry['source']
        if sha(artifact)!=entry['artifact_sha256']:
            raise RuntimeError('Artifact hash mismatch: '+key)
        data=read(artifact)
        if data['job']!=job:
            raise RuntimeError('Job mismatch: '+key)
        if data.get('manifest_sha256') not in (None, sha(manifest_path)):
            raise RuntimeError('Manifest mismatch: '+key)
        if data.get('manifest_sha256') is None and entry['status']=='completed':
            raise RuntimeError('Completed result lacks manifest hash: '+key)
        row=dict(scenario=job['scenario'],load=job['load'],executor=job['executor'],
                 seed=job['seed'],status=entry['status'],source=entry['source'],
                 artifact_sha256=entry['artifact_sha256'],error='')
        if entry['status']!='completed':
            row['error']=data.get('error',data.get('classification','unknown'))
            failures[row['error']]+=1
        else:
            solution,cluster,physical,placement=paths(job['scenario'])
            expected=baseline[(job['scenario'],job['load'],job['seed'])]
            if (data['trace_sha256']!=expected['trace_sha256'] or
                data['solution_sha256']!=sha(solution) or
                data['sim_cluster_sha256']!=sha(cluster) or
                data['placement_sha256']!=sha(placement) or
                not data['route_audit']['checked'] or
                len(data['query_samples'])!=data['arrivals']):
                raise RuntimeError('Trace, deployment or route mismatch: '+key)
            work=sum(data['gpu_busy_fraction'].values())/data['output_throughput_tokens_per_s']
            if not math.isclose(work,data['gpu_seconds_per_output_token'],rel_tol=1e-10):
                raise RuntimeError('GPU work mismatch: '+key)
            row.update(trace_sha256=data['trace_sha256'],
                       solution_sha256=data['solution_sha256'],
                       sim_cluster_sha256=data['sim_cluster_sha256'],
                       **{m:data[m] for m in METRICS})
            groups[(job['scenario'],job['load'],job['executor'])][job['seed']]=data
        rows.append(row)
    columns=['scenario','load','executor','seed','status','source','artifact_sha256',
             'error','trace_sha256','solution_sha256','sim_cluster_sha256',*METRICS]
    with (HERE/'individual.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=columns)
        writer.writeheader();writer.writerows(rows)
    lines=['# E2b Parallax（模拟器复现）','',
           '70B 画像驱动 CPU 仿真；1800 s 固定窗口、零预热、不排空。',
           '该物理池总容量 152 层，小于两条 80 层流水线所需 160 层；DP 仅能选 k=1。',
           '计算能力以 batch=8 Decode 单层画像耗时倒数近似，不等于原版 TFLOPS。',
           '无真实 Parallax 执行后端、动态成员协议和分布式遥测。','',
           '| 拓扑/负载 | 执行器 | 成功 | P95 TPOT s | P95 TTFT s | 吞吐 token/s | 完成率 | GPU s/token | 相对 V4 TPOT 配对变化 |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    full=0
    for scenario,load in (('single',350),('single',700),('multi',160),('multi',320)):
        for executor in ('fifo','shared'):
            group=groups[(scenario,load,executor)]
            if len(group)!=5:
                lines.append(f'| {scenario}/{load} | {executor} | {len(group)}/5 | — | — | — | — | — | — |')
                continue
            full+=1
            avg={m:mean(group[s][m] for s in range(5)) for m in METRICS}
            changes=[100*(group[s]['tpot_p95_s']/float(baseline[(scenario,load,s)]['tpot_p95_s'])-1)
                     for s in range(5)]
            delta=mean(changes);half=T4*stdev(changes)/math.sqrt(5)
            lines.append(f"| {scenario}/{load} | {executor} | 5/5 | {avg['tpot_p95_s']:.4f} | {avg['ttft_p95_s']:.4f} | {avg['output_throughput_tokens_per_s']:.2f} | {avg['completion_fraction']:.3f} | {avg['gpu_seconds_per_output_token']:.4f} | {delta:+.2f}% ± {half:.2f}pp |")
    lines.extend(['','仅完整五种子组报告均值与 t(4) 配对 95% CI；失败单列，不填零。',
                  '相对 V4 的数字为整体方法差异，不能归因于单独放置、路由或执行器。'])
    replay_path=HERE/'failure_replay/FINAL_AUDIT.json'
    replay=read(replay_path) if replay_path.exists() else None
    if replay is not None:
        if (not replay['passed'] or replay['original_failed']!=sum(failures.values()) or
                replay['original_index_sha256']!=sha(index_path)):
            raise RuntimeError('E2b independent replay audit mismatch')
        lines.extend(['','## 原失败与独立重放',
                      f"正式批次 {sum(e['status']=='completed' for e in index['jobs'].values())}/40 成功、{replay['original_failed']} 个原失败；独立重放 {replay['replay_completed']}/{replay['original_failed']} 成功，{replay['replay_failed']} 仍失败。",
                      '原失败按 Windows native access violation、Python 异常、KV 容量断言和重启中断分列；重放不替换正式值。',
                      f"原失败分类：{replay['original_reasons']}；重放分类：{replay['replay_reasons']}。",
                      '逐键来源、错误和 SHA256 见 failure_replay/FINAL_AUDIT.json。'])
    (HERE/'RESULTS_CN.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    audit=dict(passed=len(rows)==40 and index['status']=='terminal',registered=40,
               completed=sum(e['status']=='completed' for e in index['jobs'].values()),
               original_failed=sum(failures.values()),failure_reasons=dict(failures),
               complete_five_seed_groups=full,manifest_sha256=sha(manifest_path),
               replay_audit_sha256=sha(replay_path) if replay is not None else None,
               index_sha256=sha(index_path),individual_sha256=sha(HERE/'individual.csv'),
               results_sha256=sha(HERE/'RESULTS_CN.md'),report_script_sha256=sha(Path(__file__)))
    (HERE/'FINAL_AUDIT.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(audit)


if __name__=='__main__':main()
