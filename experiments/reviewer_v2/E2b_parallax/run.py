"""Frozen E2b simulator campaign; failed keys are preserved."""
import argparse
import importlib.metadata
import os
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, ENV, read, write, sha, relative, now, check

HERE = Path(__file__).resolve().parent
LOADS = {'single': (350, 700), 'multi': (160, 320)}
EXECUTORS = ('fifo', 'shared')


def paths(name):
    from benchmarks.layout import scenario
    folder = HERE / 'layouts' / name
    return (folder/'solution.ini', folder/'simulator_cluster.ini',
            scenario(name)[0], folder/'placement.json')


def inputs():
    files = [Path(__file__), HERE/'PLAN_CN.md', HERE/'placement.py',
             ROOT/'experiments/v5_parallax/evaluate.py',
             ROOT/'experiments/v4_validation/parallax_mechanism.py',
             HERE/'route_audit.py',
             ROOT/'experiments/v5_parallax/source/layer_allocation.py',
             ROOT/'experiments/v5_parallax/source/request_routing.py',
             ROOT/'experiments/v5_parallax/source/provenance.json']
    for directory in ('simulator', 'rcaps', 'benchmarks', 'baselines'):
        files.extend(p for p in (ROOT/directory).rglob('*')
                     if p.is_file() and p.suffix in ('.py', '.csv', '.pkl')
                     and '__pycache__' not in p.parts)
    for name in LOADS:
        files.extend(paths(name))
    return {relative(p): sha(p) for p in sorted(set(files))}


def register(phase):
    folder = HERE/phase
    folder.mkdir(exist_ok=True)
    target = folder/'manifest.json'
    if target.exists():
        manifest = read(target)
        check(manifest)
        return manifest
    if phase == 'formal':
        smoke = read(HERE/'smoke_correction/index.json')
        if smoke['status'] != 'terminal' or any(j['status'] != 'completed' for j in smoke['jobs'].values()):
            raise RuntimeError('Smoke not complete')
    seeds = [100] if phase in ('smoke','smoke_correction') else list(range(5))
    duration = 60 if phase in ('smoke','smoke_correction') else 1800
    jobs = [dict(key=f'{name}/load{load}/{executor}/seed{seed}', scenario=name,
                 load=load, executor=executor, seed=seed, duration=duration)
            for name, loads in LOADS.items()
            for load in (loads[-1:] if phase in ('smoke','smoke_correction') else loads)
            for executor in EXECUTORS for seed in seeds]
    manifest = dict(registered_at=now(), phase=phase, jobs=jobs,
        model='LLaMa70B', max_workers=2, duration_s=duration,
        warmup_s=0, drain_tail=False,
        failure_policy='One original attempt; replay in a separate directory.',
        source_commit='162354a03234a28cf6e2946e2e0b2203da7c3721',
        limitations=['One pipeline due to 152<160 layer capacity.',
                     'Profile-derived reciprocal decode latency replaces TFLOPS.',
                     'No original backend or dynamic membership.'],
        environment=dict(executable=sys.executable, python=sys.version, env=ENV,
                         packages={p: importlib.metadata.version(p) for p in
                                   ('numpy','scipy','networkx','gurobipy')}),
        sources_sha256=inputs())
    write(target, manifest)
    return manifest


def evaluate(job):
    from benchmarks.fixed_window import run
    from experiments.v5_parallax.evaluate import FIFOParallax, FullGraphParallax
    from experiments.v5_core_supplement.adapters import SetupProbe
    from .route_audit import audit as audit_routes
    solution, cluster, physical, placement = paths(job['scenario'])
    cls = FIFOParallax if job['executor'] == 'fifo' else FullGraphParallax
    holder = {}
    def factory(simulator):
        scheduler = cls(simulator, state={}, admission='full', routing_state='live',
                        singleton_multiplier=2)
        holder['scheduler'] = scheduler
        return scheduler
    row = run(job['scenario'], 'queue_dag', job['load'], job['duration'], 0,
              job['seed'], solution, cluster, physical_cluster=physical,
              scheduler_factory=factory, compact=True, record_query_samples=True,
              profile_resources=True, phase_link_probe=SetupProbe())
    row.update(cell='Parallax-simulator-'+job['executor'],
               solution_sha256=sha(solution), sim_cluster_sha256=sha(cluster),
               placement_sha256=sha(placement),
               gpu_seconds_per_output_token=sum(row['gpu_busy_fraction'].values()) /
                                            row['output_throughput_tokens_per_s'],
               route_audit=audit_routes(row, solution, cluster, physical),
               admission=holder['scheduler'].summary(),
               comparison_identity=dict(kind='Parallax phase-1 plus P2 simulator mapping',
                   executor=job['executor'], source_commit=
                   '162354a03234a28cf6e2946e2e0b2203da7c3721',
                   limitations=['No real Parallax backend, telemetry or membership.',
                                'Endpoint overhead not independently represented.',
                                'Compute power derived from reciprocal decode profile.']))
    return row


def worker(phase, key):
    manifest_path = HERE/phase/'manifest.json'
    manifest = read(manifest_path)
    job = next(j for j in manifest['jobs'] if j['key'] == key)
    folder = HERE/phase/'runs'/key
    start = time.perf_counter()
    try:
        check(manifest)
        row = evaluate(job)
        check(manifest)
        if len(row['query_samples']) != row['arrivals'] or row['output_throughput_tokens_per_s'] <= 0:
            raise ValueError('Invalid samples or zero throughput')
        row.update(status='completed', job=job, environment=manifest['environment'],
                   manifest_sha256=sha(manifest_path), elapsed_wall_s=time.perf_counter()-start,
                   finished_at=now())
        write(folder/'result.json', row)
    except BaseException as error:
        write(folder/'failure.json',dict(status='failed',job=job,error=repr(error),
            traceback=traceback.format_exc(),manifest_sha256=sha(manifest_path),
            elapsed_wall_s=time.perf_counter()-start,finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)


def queue(phase):
    manifest = register(phase)
    folder = HERE/phase
    index_path = folder/'index.json'
    if index_path.exists():
        raise RuntimeError('Existing index; inspect before recovery')
    index = dict(status='running',controller_pid=os.getpid(),registered_at=now(),
                 manifest_sha256=sha(folder/'manifest.json'),
                 jobs={j['key']:dict(status='pending') for j in manifest['jobs']})
    write(index_path,index)
    active=[]
    pending=list(manifest['jobs'])
    while pending or active:
        while pending and len(active)<manifest['max_workers']:
            check(manifest)
            job=pending.pop(0)
            run_dir=folder/'runs'/job['key']
            run_dir.mkdir(parents=True,exist_ok=False)
            log=(run_dir/'worker.log').open('x',encoding='utf-8')
            proc=subprocess.Popen([sys.executable,'-u','-X','faulthandler','-m',
                'experiments.reviewer_v2.E2b_parallax.run','--phase',phase,
                '--worker',job['key']],cwd=ROOT,env=dict(os.environ,**ENV),
                stdout=log,stderr=log)
            active.append((proc,job,log,time.monotonic()))
            index['jobs'][job['key']]=dict(status='running',pid=proc.pid,started_at=now())
            write(index_path,index)
        for item in list(active):
            proc,job,log,start=item
            code=proc.poll()
            timeout=code is None and time.monotonic()-start>7200
            if timeout: proc.kill(); code=proc.wait()
            if code is None: continue
            log.close();active.remove(item)
            result=folder/'runs'/job['key']/('result.json' if code==0 else 'failure.json')
            if not result.exists():
                write(result,dict(status='failed',job=job,exit_code=code,
                     classification='timeout' if timeout else 'abnormal_exit',finished_at=now()))
            ok=code==0 and result.name=='result.json'
            index['jobs'][job['key']].update(status='completed' if ok else 'failed',
                exit_code=code,source=relative(result),artifact_sha256=sha(result),finished_at=now())
            write(index_path,index)
        if active: time.sleep(2)
    check(manifest)
    index.update(status='terminal',finished_at=now())
    write(index_path,index)
    print('TERMINAL',dict(Counter(j['status'] for j in index['jobs'].values())),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',choices=('smoke','smoke_correction','formal'),required=True)
    parser.add_argument('--register',action='store_true')
    parser.add_argument('--worker')
    args=parser.parse_args()
    if args.worker: worker(args.phase,args.worker)
    elif args.register: register(args.phase)
    else: queue(args.phase)
