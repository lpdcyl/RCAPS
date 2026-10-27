"""Reconcile registered attempts and produce auditable, complete-triple tables."""
from __future__ import annotations
from collections import Counter,defaultdict
import csv
import math
from pathlib import Path
from statistics import mean,stdev
import time

from experiments.v4_formal.run import ROOT,read,write,digest,stamp
from experiments.v4_paper.build_report import collect

HERE=Path(__file__).resolve().parent
METRICS=['tpot_p95_s','ttft_p95_s','output_throughput_tokens_per_s',
         'gpu_seconds_per_output_token','completion_fraction','backlog_at_window_end']


def check(row):
    errors=[]
    for k in METRICS:
        v=row.get(k)
        if not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:
            errors.append(f'Invalid metric {k}: {v}')
    if len(row.get('query_samples',{}))!=row['arrivals']: errors.append('Query sample count differs')
    for field in ['gpu_busy_fraction','link_occupied_fraction']:
        if any(not math.isfinite(v) or v < -1e-8 or v > 1+1e-7 for v in row.get(field,{}).values()):
            errors.append(f'Invalid resource bounds: {field}')
    for gpu,counts in row.get('phase_link_profile',{}).get('gpu',{}).items():
        if abs(counts['busy_s']/row['duration_s']-row['gpu_busy_fraction'][gpu])>1e-8:
            errors.append(f'Independent GPU accounting differs: {gpu}')
    cohort=row.get('cohort')
    if cohort and cohort['completed'] and cohort['target_output_tokens']!=cohort['produced_output_tokens']:
        errors.append('Completed cohort token conservation differs')
    return errors


def mechanism(row):
    profile=row.get('phase_link_profile',{}); hist=Counter()
    for g in profile.get('gpu',{}).values():
        hist.update({int(k):v for k,v in g.get('decode_batch_histogram',{}).items()})
    tokens=sum(k*v for k,v in hist.items()); n=sum(hist.values())
    val=profile.get('validation',{})
    return dict(paths=len(row.get('route_counts',{})),
        token_weighted_decode_batch=sum(k*k*v for k,v in hist.items())/tokens if tokens else None,
        singleton_execution_fraction=hist[1]/n if n else None,
        decode_gpu_busy_s=sum(g.get('decode_busy_s',0) for g in profile.get('gpu',{}).values()),
        decode_network_wait_s=sum(l.get('decode_wait_s',0) for l in profile.get('links',{}).values()),
        prompt_network_wait_s=sum(l.get('prompt_wait_s',0) for l in profile.get('links',{}).values()),
        eligible_chunk_links=len(profile.get('chunking',{}).get('eligible_link_uids',[])),
        completed_chunks=profile.get('chunking',{}).get('completed_chunks',0),
        boundary_pending=val.get('arrival_boundary'),end_pending=val.get('end_pending'),
        cohort=row.get('cohort'),scheduler_call_profile=row.get('scheduler_call_profile'))


def main():
    old,old_provenance,_=collect()
    raw=[]; failures=[]; rejected=[]; states={}
    for index_name,folder in [('external_index.json','external_runs'),
                              ('external_continue_index.json','external_runs'),
                              ('diagnostic_index.json','diagnostic_runs'),
                              ('neighbor_index.json','neighbor_runs')]:
        p=HERE/index_name
        if not p.exists():
            states[index_name]={'status':'not_started'}; continue
        idx=read(p); counts=Counter(x['status'] for x in idx.get('jobs',{}).values())
        states[index_name]=dict(status=idx['status'],counts=dict(counts),source_sha256=digest(p))
        for key,item in idx.get('jobs',{}).items():
            f=HERE/folder/key/'result.json'; fail=f.with_name('failure.json')
            if item['status']=='completed':
                assert digest(f)==item['result_sha256'],str(f)
                row=read(f); errors=check(row)
                if errors:
                    rejected.append(dict(source=str(f.relative_to(ROOT)),errors=errors)); continue
                job=row['job']; condition=job.get('condition','neighbor' if folder=='neighbor_runs' else 'external')
                cell=job.get('cell',job.get('method'))
                raw.append(dict(condition=condition,scenario=job['scenario'],load=job['load'],cell=cell,
                    seed=job['seed'],source=f.relative_to(ROOT).as_posix(),sha256=digest(f),
                    trace_sha256=row['trace_sha256'],metrics={m:row.get(m) for m in METRICS},
                    mechanism=mechanism(row),row=row))
            elif item['status']=='failed':
                detail=read(fail) if fail.exists() else {'error':'Process failed; no Python exception record'}
                failures.append(dict(key=key,source=fail.relative_to(ROOT).as_posix(),
                    sha256=digest(fail) if fail.exists() else None,error=detail.get('error',detail.get('exit_code'))))
    groups=defaultdict(list)
    for r in raw: groups[r['condition'],r['scenario'],r['load'],r['cell']].append(r)
    summaries=[]; pairs=[]; interactions=[]
    for (condition,sc,load,cell),rows in groups.items():
        complete=sorted(r['seed'] for r in rows)==[0,1,2]
        summaries.append(dict(condition=condition,scenario=sc,load=load,cell=cell,
            seeds=sorted(r['seed'] for r in rows),complete_three_seed_group=complete,
            metrics={m:dict(mean=mean(r['metrics'][m] for r in rows),
                            sample_sd=stdev(r['metrics'][m] for r in rows)) for m in METRICS} if complete else None))
    bykey={(r['condition'],r['scenario'],r['load'],r['cell'],r['seed']):r for r in raw}
    for (condition,sc,load,cell),rows in groups.items():
        if cell=='v4': continue
        perseed=[]
        for r in sorted(rows,key=lambda x:x['seed']):
            if condition in ['external','neighbor']:
                target=old.get((sc,load,'v4',r['seed']))
            else:
                other=bykey.get((condition,sc,load,'v4',r['seed']))
                target=other['row'] if other else None
            if target is None: continue
            assert target['trace_sha256']==r['trace_sha256'], (condition,sc,load,cell,r['seed'])
            perseed.append(dict(seed=r['seed'],relative_full_over_comparator={m:target[m]/r['metrics'][m]-1
                if r['metrics'][m] else None for m in METRICS}))
        complete=len(perseed)==3 and sorted(x['seed'] for x in perseed)==[0,1,2]
        pairs.append(dict(condition=condition,scenario=sc,load=load,comparator=cell,seeds=perseed,
            complete=complete,paired_mean_relative={m:mean(x['relative_full_over_comparator'][m] for x in perseed)
                for m in METRICS if all(x['relative_full_over_comparator'][m] is not None for x in perseed)} if complete else None))
    for condition in ['network_half','prompt_heavy']:
        for seed in [0,1,2]:
            rs=[bykey.get((condition,'multi',320,c,seed)) for c in ['v3','spatial','temporal','v4']]
            if all(rs):
                assert len({r['trace_sha256'] for r in rs})==1
                y=[r['metrics']['tpot_p95_s'] for r in rs]
                interactions.append(dict(condition=condition,seed=seed,
                    log_tpot_interaction=math.log(y[3])-math.log(y[1])-math.log(y[2])+math.log(y[0])))
    # Full cohort rows additionally compare to the same arrival trace at 1800s.
    cohort_window=[]
    for r in raw:
        if r['condition']!='cohort_tail': continue
        previous=old.get((r['scenario'],r['load'],r['cell'],r['seed']))
        if previous:
            assert previous['trace_sha256']==r['trace_sha256']
            cohort_window.append(dict(scenario=r['scenario'],load=r['load'],cell=r['cell'],seed=r['seed'],
                original_1800s_metrics={m:previous[m] for m in METRICS},
                bounded_tail_metrics=r['metrics'],cohort=r['row']['cohort'],source=r['source']))
    # Keep metadata compact, not duplicate all per-query data in the report.
    public_raw=[{k:v for k,v in r.items() if k!='row'} for r in raw]
    result=dict(generated_at=stamp(),states=states,successful_validated_windows=len(raw),
        failures=failures,rejected_outputs=rejected,groups=summaries,paired=pairs,
        factorial=interactions,cohort_window_checks=cohort_window,windows=public_raw,
        validation_scope='Executor reconciliation and invariant checks; not an independent external review.')
    write(HERE/'validation_results.json',result)
    with (HERE/'validation_metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['condition','scenario','load','cell','seed',*METRICS,'source'])
        writer.writeheader()
        for r in raw: writer.writerow({k:r[k] for k in ['condition','scenario','load','cell','seed','source']}|r['metrics'])
    final=all(states.get(n,{}).get('status') in ['completed','blocked_preflight','blocked_controller']
              for n in ['external_continue_index.json','diagnostic_index.json','neighbor_index.json'])
    lines=['# RCAPS 必要验证扩展：'+('执行结束' if final else '进行中'),'',
        '生成时间（UTC）：`'+result['generated_at']+'`。完整方法为 V4 实现的 RCAPS。',
        '',f"新成功且通过数值/身份核对的窗口：**{len(raw)}**；失败：**{len(failures)}**；被核对拒绝的输出：**{len(rejected)}**。",
        '失败不是性能为零、也不是延迟无穷；未完成三种子的条件不生成三种子均值。',
        '', '## 队列状态','', '| 队列 | 状态 | 窗口状态 |','|---|---|---|']
    for n,s in states.items(): lines.append(f"| {n} | {s['status']} | {s.get('counts',{})} |")
    lines+=['','## 完整三种子结果','',
        '| 条件 | 场景/负载 | 方法/替换 | TPOT s | TTFT s | 输出 token/s | GPU s/token | 完成率 | 积压 |',
        '|---|---|---|---:|---:|---:|---:|---:|---:|']
    for g in summaries:
        if not g['complete_three_seed_group']: continue
        m=g['metrics']; vals=[f"{m[k]['mean']:.5g}" for k in METRICS]
        lines.append(f"| {g['condition']} | {g['scenario']}/{g['load']} | {g['cell']} | "+' | '.join(vals)+' |')
    lines+=['','cohort_tail 的吞吐分母是 5400 秒观测窗，不能与 1800 秒主表直接比较；该组检验固定工作量、完成情况、尾部和 GPU 工作。',
        'neighbor 为 Parallax-inspired 选路机制替换，**不是完整 Parallax 系统复现**。原文机制、状态估计和共同栈限制见结果的 comparison_identity。',
        '', '## 配对相对变化','',
        '以下为逐种子完整 RCAPS / 对照 − 1 的均值；负值不总是好，须结合指标方向。',
        '', '| 条件 | 场景/负载 | 对照 | TPOT | TTFT | 输出吞吐 | GPU 工作/token |',
        '|---|---|---|---:|---:|---:|---:|']
    for p in pairs:
        if not p['complete']:continue
        m=p['paired_mean_relative']
        lines.append(f"| {p['condition']} | {p['scenario']}/{p['load']} | {p['comparator']} | "+
            ' | '.join(f"{m[k]*100:+.2f}%" if k in m else '不适用' for k in METRICS[:4])+' |')
    lines+=['','## 失败记录','', '| 窗口 | 错误 |','|---|---|']
    for r in failures:lines.append(f"| {r['key']} | {str(r['error']).replace('|','/')} |")
    lines+=['','## 边界与复核','',
        '- 原始 result/failure、manifest、index 和逐种子 CSV 均保留；旧冻结结果未覆盖。',
        '- 机制分布、S/T 激活、未结算等待、窗口/尾部对照和调度器计时见 validation_results.json。',
        '- M1 结构与负例检查见 static_audit.json；首次负例测试的纠正记录保留在 static_audit_attempt1.json。',
        '- 本轮是 CPU 离散事件仿真。本地单张 24 GB GPU 不等于模拟的 24 GPU 异构集群，未完成真实 70B 分布式端到端/网络画像校准。',
        '- 本报告提供自动核对与数值，不冒称独立外部评审或统计显著结论。']
    (HERE/'RESULTS_CN.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('SUMMARY',len(raw),'success',len(failures),'failed','terminal',final,flush=True)


if __name__=='__main__': main()
