"""E5a 42-node, four-method CPU simulator campaign with immutable inputs."""
from __future__ import annotations

import argparse
import configparser
import importlib.metadata
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, ENV, read, write, sha, relative, now, check

HERE = Path(__file__).resolve().parent
BASE = ROOT / 'artifact_evaluation/high_heterogeneity'
PHYSICAL = BASE / 'config/cluster42.ini'
PROFILE = BASE / 'config/machine_profiles.ini'
RCAPS = ROOT / 'experiments/v3_cluster42/layout'
HELIX = BASE / 'layout_llama70b/ilp'
METHODS = ('RCAPS', 'RCAPS-KV', 'Helix', 'Helix+')
LOADS = (1450, 1800, 2150)


def paths(method):
    layout = RCAPS if method.startswith('RCAPS') else HELIX
    return (layout / ('solution.ini' if layout == RCAPS else 'ilp_sol.ini'),
            layout / 'simulator_cluster.ini')


def inputs():
    files = [Path(__file__), HERE / 'PLAN_CN.md',
             ROOT / 'experiments/reviewer_v2/PLAN_CN.md',
             ROOT / 'RCAPS_审稿补充实验清单_v2.md',
             ROOT / 'experiments/v3_cluster42/analysis.json',
             ROOT / 'experiments/v3_cluster42/layout/placement.json',
             ROOT / 'experiments/v5_kv_admission/scheduler.py',
             ROOT / 'experiments/v5_core_supplement/adapters.py',
             PHYSICAL, PROFILE]
    for method in METHODS:
        files.extend(paths(method))
    for directory in ('simulator', 'rcaps', 'benchmarks', 'baselines'):
        files.extend(p for p in (ROOT / directory).rglob('*') if p.is_file()
                     and p.suffix in ('.py', '.csv', '.pkl')
                     and '__pycache__' not in p.parts)
    return {relative(p): sha(p) for p in sorted(set(files))}


def register(phase):
    folder = HERE / phase
    folder.mkdir(exist_ok=True)
    manifest_path = folder / 'manifest.json'
    if manifest_path.exists():
        manifest = read(manifest_path)
        check(manifest)
        return manifest
    if phase == 'formal':
        validate_smoke()
    jobs = [dict(key=f'E5a/load{load}/{method}/seed{seed}', load=load,
                 method=method, seed=seed, duration_s=60 if phase == 'smoke' else 1800)
            for load in ((1450,) if phase == 'smoke' else LOADS)
            for method in METHODS for seed in ((100,) if phase == 'smoke' else range(5))]
    manifest = dict(registered_at=now(), experiment='E5a', phase=phase, jobs=jobs,
        model='LLaMa70B', physical_nodes=42, physical_gpus=64,
        loads=LOADS, methods=METHODS, seeds=[100] if phase == 'smoke' else list(range(5)),
        max_workers=2, timeout_wall_s=14400, warmup_s=0, drain_tail=False,
        duration_s=60 if phase == 'smoke' else 1800,
        placement_policy='V4/KV execute frozen V3 42-node placement; Helix/+ execute original artifact ILP placement; no new placement tuning',
        failure_policy='One original attempt per key; preserve failure.json, replay independently',
        environment=dict(executable=sys.executable, python=sys.version, env=ENV,
                         packages={name: importlib.metadata.version(name)
                                   for name in ('numpy', 'scipy', 'networkx', 'gurobipy')}),
        sources_sha256=inputs())
    write(manifest_path, manifest)
    return manifest


def validate_smoke():
    smoke = read(HERE / 'smoke/index.json')
    retry = read(HERE / 'smoke_retry/index.json')
    if smoke['status'] != 'terminal' or retry['status'] != 'terminal':
        raise RuntimeError('E5a smoke/replay must be terminal')
    if retry['manifest_sha256'] != sha(HERE / 'smoke_retry/manifest.json'):
        raise RuntimeError('E5a replay manifest changed')
    for key, entry in smoke['jobs'].items():
        if sha(ROOT / entry['source']) != entry['artifact_sha256']:
            raise RuntimeError('E5a smoke artifact changed: ' + key)
        if entry['status'] == 'completed':
            continue
        replay = retry['jobs'].get(key)
        if (entry['status'] != 'failed' or replay is None or
                replay['status'] != 'completed' or
                replay['original_failure_sha256'] != entry['artifact_sha256'] or
                sha(ROOT / replay['source']) != replay['artifact_sha256']):
            raise RuntimeError('E5a smoke unresolved: ' + key)


def active_nodes(solution):
    parser = configparser.ConfigParser()
    parser.read(solution, encoding='utf-8')
    return sum(bool(value.strip() != '[]') for _, value in parser['Solution'].items())


def evaluate(job):
    from benchmarks.fixed_window import run
    from experiments.v5_core_supplement.adapters import HelixPlus, SetupProbe
    from experiments.v5_kv_admission.scheduler import KVAdmissionScheduler
    from rcaps.v3.topology import TopologyModel
    from rcaps.v4.admission import AdmissionScheduler
    from rcaps.v4.chunking import PromptTransferChunkHook
    from rcaps.v4.probe import MechanismProbe

    method = job['method']
    solution, cluster = paths(method)
    state = read(RCAPS / 'placement.json')['state'] if method.startswith('RCAPS') else None
    if method == 'Helix':
        driver, factory, probe = 'helix', None, None
    elif method == 'Helix+':
        driver, factory, probe = 'queue_dag', HelixPlus, SetupProbe()
    else:
        cls = KVAdmissionScheduler if method == 'RCAPS-KV' else AdmissionScheduler
        factory = lambda sim: cls(sim, state=state, admission='sparse', routing_state='live')
        probe = SetupProbe(delegate=MechanismProbe(PromptTransferChunkHook(4_194_304, scope='slow')))
        driver = 'queue_dag'
    counts = TopologyModel(PHYSICAL).machine_counts
    row = run('single', driver, job['load'], job['duration_s'], 0, job['seed'],
              solution, cluster, physical_cluster=PHYSICAL, machine_profile=PROFILE,
              machine_counts=counts, scheduler_factory=factory, phase_link_probe=probe,
              profile_resources=True, profile_scheduler=True, compact=True,
              record_query_samples=True)
    if method.startswith('RCAPS'):
        row.update(row['phase_link_profile']['corrected_network_accounting'])
    throughput = row['output_throughput_tokens_per_s']
    row.update(cell=method, solution_sha256=sha(solution), sim_cluster_sha256=sha(cluster),
               physical_sha256=sha(PHYSICAL), machine_profile_sha256=sha(PROFILE),
               placement_sha256=sha(RCAPS / 'placement.json') if state is not None else None,
               deployed_compute_nodes=active_nodes(solution), physical_compute_nodes=42,
               physical_gpu_count=64,
               planning_wall_s=read(RCAPS / 'placement.json').get('planning_wall_s')
                   if state is not None else None,
               gpu_seconds_per_output_token=sum(row['gpu_busy_fraction'].values()) / throughput
                   if throughput > 0 else None,
               routing_timing_definition='scheduler _route for RCAPS; schedule_transmission for Helix')
    return row


def worker(phase, key):
    manifest_path = HERE / phase / 'manifest.json'
    manifest = read(manifest_path)
    job = next(j for j in manifest['jobs'] if j['key'] == key)
    dest = HERE / phase / 'runs' / key
    start = time.perf_counter()
    try:
        check(manifest)
        row = evaluate(job)
        check(manifest)
        if len(row['query_samples']) != row['arrivals']:
            raise RuntimeError('Query sample population mismatch')
        row.update(status='completed', job=job, manifest_sha256=sha(manifest_path),
                   environment=manifest['environment'], elapsed_wall_s=time.perf_counter()-start,
                   finished_at=now())
        write(dest / 'result.json', row)
    except BaseException as exc:
        write(dest / 'failure.json', dict(status='failed', job=job, error=repr(exc),
              traceback=traceback.format_exc(), manifest_sha256=sha(manifest_path),
              elapsed_wall_s=time.perf_counter()-start, finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)


def queue(phase):
    if phase == 'formal':
        validate_smoke()
    manifest = register(phase)
    folder = HERE / phase
    index_path = folder / 'index.json'
    if index_path.exists():
        raise RuntimeError('Index exists; inspect controller before recovery')
    index = dict(status='running', controller_pid=os.getpid(), registered_at=now(),
                 manifest_sha256=sha(folder / 'manifest.json'),
                 jobs={j['key']: dict(status='pending') for j in manifest['jobs']})
    write(index_path, index)
    pending, active = list(manifest['jobs']), []
    while pending or active:
        while pending and len(active) < manifest['max_workers']:
            check(manifest)
            job = pending.pop(0)
            key = job['key']
            dest = folder / 'runs' / key
            dest.mkdir(parents=True, exist_ok=False)
            log = (dest / 'worker.log').open('x', encoding='utf-8')
            cmd = [sys.executable, '-u', '-X', 'faulthandler', '-m',
                   'experiments.reviewer_v2.E5_scale_kv.run', '--phase', phase, '--worker', key]
            proc = subprocess.Popen(cmd, cwd=ROOT, env=dict(os.environ, **ENV), stdout=log, stderr=log)
            active.append((proc, job, log, time.monotonic()))
            index['jobs'][key] = dict(status='running', pid=proc.pid, started_at=now())
            write(index_path, index)
            print('START', key, flush=True)
        for item in list(active):
            proc, job, log, start = item
            code = proc.poll()
            timed_out = code is None and time.monotonic()-start > manifest['timeout_wall_s']
            if timed_out:
                proc.kill()
                code = proc.wait()
            if code is None:
                continue
            log.close()
            active.remove(item)
            key = job['key']
            dest = folder / 'runs' / key
            passed = code == 0 and (dest / 'result.json').exists()
            artifact = dest / ('result.json' if passed else 'failure.json')
            if not artifact.exists():
                write(artifact, dict(status='failed', job=job, exit_code=code,
                      classification='timeout' if timed_out else 'native_or_abnormal_exit',
                      finished_at=now()))
            index['jobs'][key].update(status='completed' if passed else 'failed',
                exit_code=code, source=relative(artifact), artifact_sha256=sha(artifact),
                finished_at=now())
            write(index_path, index)
            print('END', key, code, flush=True)
        if active:
            time.sleep(2)
    check(manifest)
    index.update(status='terminal', finished_at=now())
    write(index_path, index)
    print('TERMINAL', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=('smoke', 'formal'), default='smoke')
    parser.add_argument('--register', action='store_true')
    parser.add_argument('--worker')
    args = parser.parse_args()
    if args.worker:
        worker(args.phase, args.worker)
    elif args.register:
        register(args.phase)
    else:
        queue(args.phase)
