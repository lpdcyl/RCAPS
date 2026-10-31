"""Prospectively registered diagnostic after E5b smoke exposed boundary failures."""
import argparse
import importlib.metadata
import os
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, ENV, check, now, read, relative, sha, write
from experiments.reviewer_v2.E5_scale_kv.run_e5b import HERE, evaluate, jobs, sources

BASE = HERE / 'E5b'
SMOKE = BASE / 'smoke'
SMOKE_REPLAY = BASE / 'smoke_failure_replay'
DIAGNOSTIC = BASE / 'formal_boundary_diagnostic'
EXPECTED_FAILURES = {
    'E5b/prompt_1.5/single/load700/Helix+/seed100',
    'E5b/prompt_2.0/single/load700/Helix+/seed100',
    'E5b/prompt_2.0/multi/load320/Helix+/seed100',
}
EXPECTED_ERROR = "AssertionError('No next level node meets scheduling requirement at compute 0!')"


def register():
    DIAGNOSTIC.mkdir(exist_ok=True)
    target = DIAGNOSTIC / 'manifest.json'
    if target.exists():
        manifest = read(target)
        check(manifest)
        return manifest
    if os.environ.get('CONDA_DEFAULT_ENV') != 'gllm':
        raise RuntimeError('Activate conda gllm before registration')
    smoke_manifest = read(SMOKE / 'manifest.json')
    smoke_index = read(SMOKE / 'index.json')
    replay_manifest = read(SMOKE_REPLAY / 'manifest.json')
    replay_index = read(SMOKE_REPLAY / 'index.json')
    check(smoke_manifest)
    if smoke_index['status'] != 'terminal' or replay_index['status'] != 'terminal':
        raise RuntimeError('Smoke and independent replay must be terminal')
    if smoke_index['manifest_sha256'] != sha(SMOKE / 'manifest.json'):
        raise RuntimeError('Smoke manifest mismatch')
    if replay_index['manifest_sha256'] != sha(SMOKE_REPLAY / 'manifest.json'):
        raise RuntimeError('Smoke replay manifest mismatch')
    if replay_manifest['smoke_manifest_sha256'] != sha(SMOKE / 'manifest.json'):
        raise RuntimeError('Smoke replay lineage mismatch')
    failed = {key for key, entry in smoke_index['jobs'].items() if entry['status'] == 'failed'}
    if len(smoke_index['jobs']) != 16 or failed != EXPECTED_FAILURES:
        raise RuntimeError('Smoke status differs from registered amendment')
    if set(replay_index['jobs']) != failed:
        raise RuntimeError('Independent replay keys differ from smoke failures')
    frozen = sources()
    frozen[relative(Path(__file__))] = sha(Path(__file__))
    frozen[relative(BASE / 'AMENDMENT_CN.md')] = sha(BASE / 'AMENDMENT_CN.md')
    for folder, index in ((SMOKE, smoke_index), (SMOKE_REPLAY, replay_index)):
        frozen[relative(folder / 'manifest.json')] = sha(folder / 'manifest.json')
        frozen[relative(folder / 'index.json')] = sha(folder / 'index.json')
        for key, entry in index['jobs'].items():
            artifact = ROOT / entry['source']
            if sha(artifact) != entry['artifact_sha256']:
                raise RuntimeError('Smoke artifact changed: ' + key)
            frozen[entry['source']] = entry['artifact_sha256']
            if key in EXPECTED_FAILURES:
                if read(artifact).get('error') != EXPECTED_ERROR:
                    raise RuntimeError('Unexpected smoke failure: ' + key)
    if any(entry['status'] != 'failed' for entry in replay_index['jobs'].values()):
        raise RuntimeError('Smoke replay result changed')
    campaign = jobs('formal')
    if len(campaign) != 80:
        raise RuntimeError('Expected 80 diagnostic windows')
    manifest = dict(registered_at=now(), experiment='E5b_boundary_diagnostic',
        amendment='E5b/AMENDMENT_CN.md', jobs=campaign,
        scope='16 conditions x seeds 0-4; all original conditions retained',
        protocol='1800 s fixed window; zero warmup; no drain',
        source_smoke_manifest_sha256=sha(SMOKE / 'manifest.json'),
        source_smoke_index_sha256=sha(SMOKE / 'index.json'),
        source_smoke_replay_index_sha256=sha(SMOKE_REPLAY / 'index.json'),
        expected_smoke_failures=sorted(failed), max_workers=1, timeout_wall_s=14400,
        environment=dict(executable=sys.executable, python=sys.version,
            conda_prefix=os.environ.get('CONDA_PREFIX'),
            conda_default_env=os.environ.get('CONDA_DEFAULT_ENV'),
            path_head=os.environ.get('PATH', '').split(';')[:7], env=ENV,
            packages={p: importlib.metadata.version(p)
                      for p in ('numpy', 'scipy', 'networkx', 'gurobipy')}),
        sources_sha256=frozen, failure_policy='Preserve each original failure; replay separately')
    write(target, manifest)
    return manifest


def worker(key):
    target = DIAGNOSTIC / 'manifest.json'
    manifest = read(target)
    job = next(j for j in manifest['jobs'] if j['key'] == key)
    folder = DIAGNOSTIC / 'runs' / key
    start = time.perf_counter()
    try:
        check(manifest)
        row = evaluate(job, folder)
        check(manifest)
        if len(row['query_samples']) != row['arrivals']:
            raise ValueError('Query sample count mismatch')
        row.update(status='completed', job=job, origin='amended_boundary_diagnostic',
                   manifest_sha256=sha(target), environment=manifest['environment'],
                   elapsed_wall_s=time.perf_counter()-start, finished_at=now())
        write(folder / 'result.json', row)
    except BaseException as exc:
        write(folder / 'failure.json', dict(status='failed', job=job, error=repr(exc),
             traceback=traceback.format_exc(), origin='amended_boundary_diagnostic',
             manifest_sha256=sha(target), elapsed_wall_s=time.perf_counter()-start,
             finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)


def queue():
    manifest = register()
    target = DIAGNOSTIC / 'index.json'
    if target.exists():
        raise RuntimeError('Diagnostic index exists; inspect before recovery')
    index = dict(status='running', controller_pid=os.getpid(), registered_at=now(),
        manifest_sha256=sha(DIAGNOSTIC / 'manifest.json'),
        jobs={job['key']: dict(status='pending') for job in manifest['jobs']})
    write(target, index)
    for job in manifest['jobs']:
        check(manifest)
        key = job['key']
        folder = DIAGNOSTIC / 'runs' / key
        folder.mkdir(parents=True, exist_ok=False)
        with (folder / 'worker.log').open('x', encoding='utf-8') as log:
            proc = subprocess.Popen([sys.executable, '-u', '-X', 'faulthandler', '-m',
                'experiments.reviewer_v2.E5_scale_kv.run_e5b_boundary', '--worker', key],
                cwd=ROOT, env=dict(os.environ, **ENV), stdout=log, stderr=log)
            index['jobs'][key] = dict(status='running', pid=proc.pid, started_at=now())
            write(target, index)
            print('START', key, flush=True)
            try:
                code = proc.wait(timeout=manifest['timeout_wall_s'])
            except subprocess.TimeoutExpired:
                proc.kill()
                code = proc.wait()
        passed = code == 0 and (folder / 'result.json').exists()
        artifact = folder / ('result.json' if passed else 'failure.json')
        if not artifact.exists():
            write(artifact, dict(status='failed', job=job, exit_code=code,
                                 classification='native_or_abnormal_exit', finished_at=now()))
        index['jobs'][key].update(status='completed' if passed else 'failed',
            exit_code=code, source=relative(artifact), artifact_sha256=sha(artifact),
            finished_at=now())
        write(target, index)
        print('END', key, code, flush=True)
    check(manifest)
    index.update(status='terminal', finished_at=now())
    write(target, index)
    print('TERMINAL', dict(Counter(e['status'] for e in index['jobs'].values())), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--register', action='store_true')
    parser.add_argument('--worker')
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
    elif args.register:
        register()
    else:
        queue()
