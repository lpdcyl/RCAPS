"""Post-validation Parallax-inspired mechanism campaign, continue on failure."""
from __future__ import annotations
import argparse
import faulthandler
import os
from pathlib import Path
import subprocess
import sys
import time
from experiments.v4_formal.run import ROOT,read,write,digest,stamp,capture,environment
from experiments.v4_external.run import validate as validate_external

HERE=Path(__file__).resolve().parent
MANIFEST,INDEX=HERE/'neighbor_manifest.json',HERE/'neighbor_index.json'


def jobs():
    return [dict(scenario=scenario,load=load,seed=seed,cell='parallax_p2',
                 key=f'{scenario}/load{load}/parallax_p2/seed{seed}')
        for scenario,loads in [('single',[350,700]),('multi',[160,320])]
        for load in loads for seed in [0,1,2]]


def validate():
    validate_external()
    frozen=read(MANIFEST)
    assert environment()==frozen['environment']
    for name,h in frozen['sources_sha256'].items(): assert digest(ROOT/name)==h,name
    return frozen


def one(key):
    faulthandler.enable()
    frozen=validate(); job=next(x for x in frozen['jobs'] if x['key']==key)
    out=HERE/'neighbor_runs'/key/'result.json'
    assert not out.exists() and not out.with_name('failure.json').exists()
    start=time.perf_counter()
    try:
        from .parallax_mechanism import evaluate
        row=evaluate(job)
        row.update(job=job,manifest_sha256=digest(MANIFEST),status='completed',finished_at=stamp(),
                   elapsed_wall_s=time.perf_counter()-start,environment=environment())
        validate(); write(out,row)
    except BaseException as e:
        write(out.with_name('failure.json'),dict(capture(e),job=job,finished_at=stamp()))
        raise


def queue():
    frozen=validate(); assert not INDEX.exists()
    pending,active=list(frozen['jobs']),[]
    index=dict(status='running',pid=os.getpid(),started_at=stamp(),jobs={},manifest_sha256=digest(MANIFEST))
    write(INDEX,index)
    while pending or active:
        while pending and len(active)<2:
            job=pending.pop(0); directory=HERE/'neighbor_runs'/job['key']
            directory.mkdir(parents=True,exist_ok=True)
            log=(directory/'worker.log').open('x',encoding='utf-8')
            p=subprocess.Popen([sys.executable,'-u','-X','faulthandler','-m',
                'experiments.v4_validation.neighbor_run','--phase','one','--key',job['key']],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            active.append((p,log,job)); index['jobs'][job['key']]=dict(status='running',pid=p.pid,started_at=stamp())
            write(INDEX,index); print('START',job['key'],p.pid,flush=True)
        for p,log,job in list(active):
            code=p.poll()
            if code is None: continue
            log.close(); active.remove((p,log,job)); out=HERE/'neighbor_runs'/job['key']/'result.json'
            ok=code==0 and out.exists(); failure=out.with_name('failure.json')
            if not ok and not failure.exists(): write(failure,dict(kind='process_failure',job=job,exit_code=code))
            index['jobs'][job['key']].update(status='completed' if ok else 'failed',exit_code=code,
                finished_at=stamp(),result_sha256=digest(out) if ok else None,
                failure_sha256=digest(failure) if failure.exists() else None)
            write(INDEX,index); print('DONE' if ok else 'FAILED',job['key'],code,flush=True)
        if active: time.sleep(2)
    index.update(status='completed',finished_at=stamp()); write(INDEX,index)


def after_validation():
    # Wait for the necessary experiments (including preflight) to finish.
    target=HERE/'diagnostic_index.json'
    while not target.exists() or read(target)['status']=='running': time.sleep(10)
    validate_external()
    from .parallax_mechanism import evaluate
    check={}
    try:
        row=evaluate(dict(scenario='multi',load=320,seed=0,cell='parallax_p2'),60)
        assert row['arrivals']>0 and row['phase_link_profile']['validation']['legality']['complete_paths']>0
        check=dict(status='passed',kind='engineering_only',duration_s=60,identity=row['comparison_identity'])
    except BaseException as e:
        check=dict(status='failed',kind='engineering_only',**capture(e))
    write(HERE/'neighbor_preflight.json',check)
    if check['status']!='passed':
        write(INDEX,dict(status='blocked_preflight',jobs={},finished_at=stamp(),failure=check))
        return
    assert not MANIFEST.exists()
    paths=[Path(__file__),HERE/'parallax_mechanism.py',HERE/'diagnostics.py',HERE/'neighbor_preflight.json',
           ROOT/'novelty_check/html/2509.26182.txt',ROOT/'experiments/v4_formal/manifest.json']
    write(MANIFEST,dict(registered_at=stamp(),environment=environment(),jobs=jobs(),
        sources_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in paths},
        identity=check['identity'],protocol=dict(duration_s=1800,seeds=[0,1,2],concurrency=2,
            failure_policy='record and continue; no automatic retry',tuning='None',warmup_s=0,drain=False)))
    queue()


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--phase',required=True,choices=['one','queue','after-validation']); p.add_argument('--key')
    a=p.parse_args()
    if a.phase=='one': one(a.key)
    elif a.phase=='queue': queue()
    else: after_validation()
