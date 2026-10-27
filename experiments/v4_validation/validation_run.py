"""Continue-on-failure queue for registered RCAPS mechanism validation."""
from __future__ import annotations

import argparse
import faulthandler
import os
from pathlib import Path
import subprocess
import sys
import time

from experiments.v4_formal.run import ROOT, read, write, digest, environment, stamp, capture
from experiments.v4_external.run import validate as validate_external

HERE = Path(__file__).resolve().parent
MANIFEST, INDEX = HERE/'diagnostic_manifest.json', HERE/'diagnostic_index.json'


def external_active():
    target=HERE/'external_continue_index.json'
    if not target.exists():return 0
    index=read(target)
    return sum(j['status']=='running' for j in index.get('jobs',{}).values())


def jobs():
    rows = []
    def add(condition, scenario, load, cells):
        for cell in cells:
            for seed in (0,1,2):
                rows.append(dict(condition=condition, scenario=scenario, load=load, cell=cell,
                    seed=seed, key=f'{condition}/{scenario}/load{load}/{cell}/seed{seed}',
                    duration=5400 if condition=='cohort_tail' else 1800, arrival_horizon=1800))
    add('singleton1','multi',320,['v4','temporal'])
    add('network_half','multi',320,['v3','spatial','temporal','v4'])
    add('prompt_heavy','multi',320,['v3','spatial','temporal','v4'])
    add('cohort_tail','single',700,['v4','static','single_boundary'])
    add('cohort_tail','multi',320,['v4','static','spatial','temporal'])
    return rows


def preflight():
    from .diagnostics import evaluate
    from rcaps.v4_method import evaluate_variant
    from experiments.v4_formal.run import inputs
    from rcaps.v3.topology import TopologyModel
    checks = {}
    base = dict(scenario='multi', load=320, cell='v4', seed=0, condition='reference')
    physical, layout = inputs(base)
    reference = evaluate_variant('multi',320,60,0,0,layout/'solution.ini',layout/'simulator_cluster.ini',
        physical_cluster=physical,machine_counts=TopologyModel(physical).machine_counts)
    checks['reference'] = {'status':'running'}
    try:
        row=evaluate(base,60,60)
        fields=['trace_sha256','arrivals','tpot_p95_s','ttft_p95_s','output_throughput_tokens_per_s',
                'completion_fraction','backlog_at_window_end','query_samples','route_counts','gpu_busy_fraction']
        differences=[k for k in fields if row[k]!=reference[k]]
        assert not differences, differences
        checks['reference']=dict(status='passed',exact_fields=fields)
    except BaseException as e:
        checks['reference']=dict(status='failed',**capture(e))
    for condition in ['singleton1','network_half','prompt_heavy','cohort_tail']:
        try:
            row=evaluate(dict(base,condition=condition),180 if condition=='cohort_tail' else 60,60)
            assert row['arrivals']==reference['arrivals']
            v=row['phase_link_profile']['validation']
            assert v['legality']['complete_paths']>0
            if condition=='network_half':
                assert v['changed_links'] and all(x['new_Bps']==x['old_Bps']/2 for x in v['changed_links'])
                assert row['admission']['allowed_edges']==reference['admission']['allowed_edges']
            if condition=='prompt_heavy':
                tr=row['validation_protocol']['trace']
                assert tr['input_tokens']>tr['original_input_tokens']
            if condition=='cohort_tail':
                assert row['trace_sha256']==reference['trace_sha256']
                assert row['backlog_at_window_end']<=reference['backlog_at_window_end']
            checks[condition]=dict(status='passed',duration_s=row['duration_s'],arrivals=row['arrivals'],
                                   legality=v['legality'])
        except BaseException as e:
            checks[condition]=dict(status='failed',**capture(e))
        print('PREFLIGHT',condition,checks[condition]['status'],flush=True)
    write(HERE/'diagnostic_preflight.json',dict(kind='engineering_only',checks=checks,
        finished_at=stamp(),source_sha256=digest(HERE/'diagnostics.py')))
    return checks


def freeze():
    validate_external()
    assert not MANIFEST.exists(), 'Do not refreeze'
    check=read(HERE/'diagnostic_preflight.json')
    assert check['source_sha256']==digest(HERE/'diagnostics.py')
    checks=check['checks']
    rows=jobs()
    permitted=[r for r in rows if checks['reference']['status']=='passed'
               and checks[r['condition']]['status']=='passed']
    write(MANIFEST,dict(registered_at=stamp(),environment=environment(),jobs=permitted,
        blocked_jobs=[r for r in rows if r not in permitted],
        sources_sha256={str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in
            [Path(__file__),HERE/'diagnostics.py',HERE/'diagnostic_preflight.json',
             ROOT/'experiments/v4_formal/manifest.json',ROOT/'experiments/v4_external/manifest.json']},
        protocol=dict(seeds=[0,1,2],concurrency=2,failure_policy='record and continue; no automatic retry',
            singleton='Change explicit multiplier 2 to 1 in execution AND M3 session pricing; otherwise same profile.',
            network='Multiply only original compute-compute <=50 MB/s link bandwidth by 0.5; placement fixed.',
            workload='Same arrival times and per-request total tokens; move min(output//2,max(0,4096-input)) tokens to prompt.',
            cohort='Identical 1800s arrivals, no new arrivals afterward, observe until 5400s; retain right censoring.',
            tuning='None; negative or failed results retained; seed0 preflight not paper evidence.',
            resources='CPU simulator; routing times are local control overhead, not real end-to-end GPU execution.')))
    print('DIAGNOSTIC_REGISTERED',len(permitted),'blocked',len(rows)-len(permitted),flush=True)


def validate():
    validate_external()
    frozen=read(MANIFEST)
    assert environment()==frozen['environment']
    for name,expected in frozen['sources_sha256'].items():
        assert digest(ROOT/name)==expected, name
    return frozen


def one(key):
    faulthandler.enable()
    frozen=validate()
    job=next(j for j in frozen['jobs'] if j['key']==key)
    out=HERE/'diagnostic_runs'/key/'result.json'
    assert not out.exists() and not out.with_name('failure.json').exists(), 'Existing attempt'
    started=time.perf_counter()
    try:
        from .diagnostics import evaluate
        row=evaluate(job,job['duration'],job['arrival_horizon'])
        row.update(job=job,status='completed',finished_at=stamp(),elapsed_wall_s=time.perf_counter()-started,
                   manifest_sha256=digest(MANIFEST),environment=environment())
        validate()
        write(out,row)
    except BaseException as error:
        write(out.with_name('failure.json'),dict(capture(error),job=job,finished_at=stamp(),
            elapsed_wall_s=time.perf_counter()-started))
        raise


def queue():
    frozen=validate()
    assert not INDEX.exists(), 'Queue already registered'
    pending,active=list(frozen['jobs']),[]
    index=dict(status='running',started_at=stamp(),pid=os.getpid(),manifest_sha256=digest(MANIFEST),jobs={})
    write(INDEX,index)
    while pending or active:
        while pending and len(active)<max(0,2-external_active()):
            job=pending.pop(0)
            directory=HERE/'diagnostic_runs'/job['key']
            directory.mkdir(parents=True,exist_ok=True)
            log=(directory/'worker.log').open('x',encoding='utf-8')
            p=subprocess.Popen([sys.executable,'-u','-X','faulthandler','-m',
                'experiments.v4_validation.validation_run','--phase','one','--key',job['key']],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            active.append((p,log,job))
            index['jobs'][job['key']]=dict(status='running',pid=p.pid,started_at=stamp())
            write(INDEX,index)
            print('START',job['key'],p.pid,flush=True)
        for p,log,job in list(active):
            code=p.poll()
            if code is None: continue
            log.close(); active.remove((p,log,job))
            out=HERE/'diagnostic_runs'/job['key']/'result.json'
            ok=code==0 and out.exists()
            failure=out.with_name('failure.json')
            if not ok and not failure.exists():
                write(failure,dict(kind='process_failure',exit_code=code,job=job,finished_at=stamp()))
            index['jobs'][job['key']].update(status='completed' if ok else 'failed',exit_code=code,
                finished_at=stamp(),result_sha256=digest(out) if ok else None,
                failure_sha256=digest(failure) if failure.exists() else None)
            write(INDEX,index)
            print('DONE' if ok else 'FAILED',job['key'],code,flush=True)
        if active or pending: time.sleep(2)
    index.update(status='completed',finished_at=stamp(),pending=[])
    write(INDEX,index)
    print('DIAGNOSTIC_QUEUE_FINISHED',flush=True)


def after_external():
    target=HERE/'external_continue_index.json'
    while target.exists() and read(target)['status']=='running':
        index=read(target)
        # Once all external windows were dispatched, a vacant slot cannot be
        # reclaimed by that queue. Use it without exceeding two total workers.
        if len(index['jobs'])==len(index['pending_initial']) and external_active()<=1:
            break
        time.sleep(10)
    # Earlier failures are independent of these environments; do not gate them.
    preflight()
    freeze()
    queue()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',required=True,choices=['preflight','freeze','one','queue','after-external'])
    parser.add_argument('--key')
    a=parser.parse_args()
    if a.phase=='one': one(a.key)
    elif a.phase=='after-external': after_external()
    else: globals()[a.phase]()
