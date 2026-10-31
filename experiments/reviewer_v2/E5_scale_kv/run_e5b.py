"""E5b half-KV and long-prompt boundary campaign on the frozen 70B layouts."""
from __future__ import annotations

import argparse
import importlib.metadata
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, ENV, read, write, sha, relative, now, check, paths
from experiments.v5_core_supplement.adapters import HelixPlus
from experiments.v5_kv_stress.evaluate import CapacityProbe

HERE = Path(__file__).resolve().parent
CONDITIONS = (('single', 700), ('multi', 320))
METHODS = {'half_kv': ('RCAPS-KV', 'Helix+'),
           'prompt_1.5': ('RCAPS', 'RCAPS-KV', 'Helix+'),
           'prompt_2.0': ('RCAPS', 'RCAPS-KV', 'Helix+')}


def layout(case, method):
    return paths(case, 'HH' if method == 'Helix+' else 'V4')


def sources():
    files = [Path(__file__), HERE/'PLAN_CN.md',
             ROOT/'experiments/v5_kv_stress/evaluate.py',
             ROOT/'experiments/v5_kv_admission/scheduler.py',
             ROOT/'experiments/v5_core_supplement/adapters.py',
             ROOT/'experiments/v5_kv_stress/formal/index.json',
             ROOT/'experiments/v5_kv_stress/analysis.json']
    for case, _ in CONDITIONS:
        for method in ('RCAPS', 'Helix+'):
            solution, cluster, physical = layout(case, method)
            files.extend((solution, cluster, physical))
            if method == 'RCAPS':
                files.append(solution.parent/'placement.json')
    for name in ('simulator', 'rcaps', 'benchmarks', 'baselines'):
        files.extend(p for p in (ROOT/name).rglob('*') if p.is_file()
                     and p.suffix in ('.py', '.csv', '.pkl')
                     and '__pycache__' not in p.parts)
    return {relative(p):sha(p) for p in sorted(set(files))}


def jobs(phase):
    return [dict(key=f'E5b/{family}/{case}/load{load}/{method}/seed{seed}',
                 family=family, scenario=case, load=load, method=method, seed=seed,
                 capacity_scale=0.5 if family=='half_kv' else 1.0,
                 prompt_multiplier=1.0 if family=='half_kv' else float(family.split('_')[1]),
                 duration_s=60 if phase=='smoke' else 1800)
            for family, methods in METHODS.items() for case, load in CONDITIONS
            for method in methods for seed in ((100,) if phase=='smoke' else range(5))]


def register(phase):
    dest=HERE/'E5b'/phase
    dest.mkdir(parents=True,exist_ok=True)
    manifest_path=dest/'manifest.json'
    if manifest_path.exists():
        manifest=read(manifest_path);check(manifest);return manifest
    if phase=='formal':
        smoke=read(HERE/'E5b/smoke/index.json')
        if smoke['status']!='terminal' or any(e['status']!='completed' for e in smoke['jobs'].values()):
            raise RuntimeError('E5b smoke must be 16/16 complete before formal')
    manifest=dict(registered_at=now(),experiment='E5b',phase=phase,jobs=jobs(phase),
        protocol='1800 s fixed window; zero warmup; no drain',
        base_loads=dict(CONDITIONS), methods=METHODS,
        semantics='half_kv: same arrivals with all node KV capacity halved; prompt factors: input tokens multiplied and offered load halved; output tokens unchanged',
        profile_bound_tokens=7500, max_workers=2, timeout_wall_s=14400,
        failure_policy='Original failures preserved; replay in independent directory',
        environment=dict(executable=sys.executable,python=sys.version,env=ENV,
                         packages={p:importlib.metadata.version(p)
                                   for p in ('numpy','scipy','networkx','gurobipy')}),
        sources_sha256=sources())
    write(manifest_path,manifest)
    return manifest


def make_trace(job):
    if job['prompt_multiplier']==1.0:
        return None
    from simulator.trace_generator.simulator_query_feeder import OnlineRequestFeeder
    feeder=OnlineRequestFeeder(cluster_token_throughput=job['load']/2,
                              start_time=0,duration=job['duration_s'],seed=job['seed'])
    factor=job['prompt_multiplier']
    trace=[(arrival,int(prompt*factor),output) for arrival,prompt,output in feeder.trace]
    excess=[(prompt,output) for _,prompt,output in trace if prompt+output>7500]
    if excess:
        raise ValueError(f'profile_boundary_exceeded: {len(excess)} requests, maximum {max(p+o for p,o in excess)} tokens')
    return trace


def evaluate(job, dest):
    from benchmarks.fixed_window import run
    from rcaps.v4.admission import AdmissionScheduler
    from rcaps.v4.chunking import PromptTransferChunkHook
    from rcaps.v4.probe import MechanismProbe
    from experiments.v5_kv_admission.scheduler import KVAdmissionScheduler

    method=job['method']
    solution,cluster,physical=layout(job['scenario'],method)
    state=read(solution.parent/'placement.json')['state'] if method!='Helix+' else None
    if method=='Helix+':
        factory=HelixPlus;delegate=None
    else:
        cls=KVAdmissionScheduler if method=='RCAPS-KV' else AdmissionScheduler
        factory=lambda sim:cls(sim,state=state,admission='sparse',routing_state='live')
        delegate=MechanismProbe(PromptTransferChunkHook(4_194_304,scope='slow'))
    probe=CapacityProbe(job['capacity_scale'],dest/'capacities.json',delegate=delegate)
    trace=make_trace(job)
    row=run(job['scenario'],'queue_dag',job['load'] if trace is None else job['load']/2,
            job['duration_s'],0,job['seed'],solution,cluster,physical_cluster=physical,
            scheduler_factory=factory,compact=True,record_query_samples=True,
            profile_resources=True,phase_link_probe=probe,trace_override=trace)
    if method!='Helix+':
        row.update(row['phase_link_profile']['corrected_network_accounting'])
    throughput=row['output_throughput_tokens_per_s']
    row.update(cell=method,family=job['family'],capacity_scale=job['capacity_scale'],
               prompt_multiplier=job['prompt_multiplier'],solution_sha256=sha(solution),
               sim_cluster_sha256=sha(cluster),physical_sha256=sha(physical),
               gpu_seconds_per_output_token=sum(row['gpu_busy_fraction'].values())/throughput
                   if throughput>0 else None,
               trace_profile_bounds_checked=(max((p+o for _,p,o in trace),default=0)<=7500) if trace else None)
    return row


def worker(phase,key):
    dest=HERE/'E5b'/phase
    manifest_path=dest/'manifest.json'
    manifest=read(manifest_path)
    job=next(j for j in manifest['jobs'] if j['key']==key)
    folder=dest/'runs'/key
    start=time.perf_counter()
    try:
        check(manifest)
        row=evaluate(job,folder)
        check(manifest)
        if len(row['query_samples'])!=row['arrivals']:
            raise RuntimeError('Query sample count mismatch')
        row.update(status='completed',job=job,manifest_sha256=sha(manifest_path),
                   environment=manifest['environment'],elapsed_wall_s=time.perf_counter()-start,
                   finished_at=now())
        write(folder/'result.json',row)
    except BaseException as exc:
        write(folder/'failure.json',dict(status='failed',job=job,error=repr(exc),
              traceback=traceback.format_exc(),manifest_sha256=sha(manifest_path),
              elapsed_wall_s=time.perf_counter()-start,finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)


def queue(phase):
    manifest=register(phase)
    dest=HERE/'E5b'/phase
    index_path=dest/'index.json'
    if index_path.exists():
        raise RuntimeError('Index exists; inspect controller before recovery')
    index=dict(status='running',controller_pid=os.getpid(),registered_at=now(),
               manifest_sha256=sha(dest/'manifest.json'),
               jobs={j['key']:dict(status='pending') for j in manifest['jobs']})
    write(index_path,index)
    pending,active=list(manifest['jobs']),[]
    while pending or active:
        while pending and len(active)<manifest['max_workers']:
            check(manifest)
            job=pending.pop(0);key=job['key']
            folder=dest/'runs'/key
            folder.mkdir(parents=True,exist_ok=False)
            log=(folder/'worker.log').open('x',encoding='utf-8')
            proc=subprocess.Popen([sys.executable,'-u','-X','faulthandler','-m',
                'experiments.reviewer_v2.E5_scale_kv.run_e5b','--phase',phase,'--worker',key],
                cwd=ROOT,env=dict(os.environ,**ENV),stdout=log,stderr=log)
            active.append((proc,job,log,time.monotonic()))
            index['jobs'][key]=dict(status='running',pid=proc.pid,started_at=now())
            write(index_path,index);print('START',key,flush=True)
        for item in list(active):
            proc,job,log,start=item
            code=proc.poll()
            timed_out=code is None and time.monotonic()-start>manifest['timeout_wall_s']
            if timed_out:proc.kill();code=proc.wait()
            if code is None:continue
            log.close();active.remove(item)
            folder=dest/'runs'/job['key']
            ok=code==0 and (folder/'result.json').exists()
            artifact=folder/('result.json' if ok else 'failure.json')
            if not artifact.exists():
                write(artifact,dict(status='failed',job=job,exit_code=code,
                    classification='timeout' if timed_out else 'native_or_abnormal_exit',finished_at=now()))
            index['jobs'][job['key']].update(status='completed' if ok else 'failed',
                 exit_code=code,source=relative(artifact),artifact_sha256=sha(artifact),finished_at=now())
            write(index_path,index);print('END',job['key'],code,flush=True)
        if active:time.sleep(2)
    check(manifest)
    index.update(status='terminal',finished_at=now())
    write(index_path,index);print('TERMINAL',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',choices=('smoke','formal'),default='smoke')
    parser.add_argument('--register',action='store_true')
    parser.add_argument('--worker')
    args=parser.parse_args()
    if args.worker:worker(args.phase,args.worker)
    elif args.register:register(args.phase)
    else:queue(args.phase)
