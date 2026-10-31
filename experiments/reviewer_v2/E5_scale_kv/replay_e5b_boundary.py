"""Independent serial replay of all E5b amended-diagnostic failures."""
import argparse
import os
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, ENV, check, now, read, relative, sha, write
from experiments.reviewer_v2.E5_scale_kv.run_e5b import HERE, evaluate

ORIGINAL = HERE / 'E5b' / 'formal_boundary_diagnostic'
REPLAY = HERE / 'E5b' / 'boundary_failure_replay'


def register():
    REPLAY.mkdir(exist_ok=True)
    target = REPLAY / 'manifest.json'
    if target.exists():
        return read(target)
    if os.environ.get('CONDA_DEFAULT_ENV') != 'gllm':
        raise RuntimeError('Activate conda gllm before replay registration')
    frozen, index = read(ORIGINAL / 'manifest.json'), read(ORIGINAL / 'index.json')
    check(frozen)
    if index['status'] != 'terminal' or index['manifest_sha256'] != sha(ORIGINAL / 'manifest.json'):
        raise RuntimeError('Original diagnostic not terminal or manifest changed')
    jobs = [j for j in frozen['jobs'] if index['jobs'][j['key']]['status'] == 'failed']
    if len(jobs) != 59:
        raise RuntimeError(f'Expected 59 failed keys; found {len(jobs)}')
    lineage = {}
    for job in jobs:
        entry = index['jobs'][job['key']]
        if sha(ROOT / entry['source']) != entry['artifact_sha256']:
            raise RuntimeError('Original failure changed: ' + job['key'])
        lineage[job['key']] = dict(source=entry['source'], sha256=entry['artifact_sha256'])
    manifest = dict(registered_at=now(), jobs=jobs, original_failures=lineage,
        original_manifest_sha256=sha(ORIGINAL / 'manifest.json'),
        original_index_sha256=sha(ORIGINAL / 'index.json'),
        original_audit_sha256=sha(ORIGINAL / 'FINAL_AUDIT.json'),
        worker_source_sha256=sha(Path(__file__)),
        environment=dict(executable=sys.executable,
            conda_prefix=os.environ.get('CONDA_PREFIX'),
            conda_default_env=os.environ.get('CONDA_DEFAULT_ENV'),
            path_head=os.environ.get('PATH', '').split(';')[:7]),
        policy='Fresh serial workers, independent index, original diagnostic artifacts read-only')
    write(target, manifest)
    return manifest


def worker(key):
    manifest = read(REPLAY / 'manifest.json')
    job = next(j for j in manifest['jobs'] if j['key'] == key)
    folder = REPLAY / 'runs' / key
    start = time.perf_counter()
    try:
        check(read(ORIGINAL / 'manifest.json'))
        row = evaluate(job, folder)
        if len(row['query_samples']) != row['arrivals']:
            raise ValueError('Query sample count mismatch')
        row.update(status='completed', job=job, origin='independent_boundary_failure_replay',
                   source_manifest_sha256=manifest['original_manifest_sha256'],
                   elapsed_wall_s=time.perf_counter()-start, finished_at=now())
        write(folder / 'result.json', row)
    except BaseException as exc:
        write(folder / 'failure.json', dict(status='failed', job=job, error=repr(exc),
              traceback=traceback.format_exc(), origin='independent_boundary_failure_replay',
              elapsed_wall_s=time.perf_counter()-start, finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)


def queue():
    manifest = register()
    target = REPLAY / 'index.json'
    if target.exists():
        raise RuntimeError('Replay index exists; inspect before recovery')
    index = dict(status='running', controller_pid=os.getpid(), registered_at=now(),
        manifest_sha256=sha(REPLAY / 'manifest.json'),
        jobs={j['key']: dict(status='pending') for j in manifest['jobs']})
    write(target, index)
    for job in manifest['jobs']:
        key = job['key']
        source = manifest['original_failures'][key]
        if sha(ROOT / source['source']) != source['sha256']:
            raise RuntimeError('Original failure changed: ' + key)
        folder = REPLAY / 'runs' / key
        folder.mkdir(parents=True, exist_ok=False)
        with (folder / 'worker.log').open('x', encoding='utf-8') as log:
            proc = subprocess.Popen([sys.executable, '-u', '-X', 'faulthandler', '-m',
                'experiments.reviewer_v2.E5_scale_kv.replay_e5b_boundary', '--worker', key],
                cwd=ROOT, env=dict(os.environ, **ENV), stdout=log, stderr=log)
            index['jobs'][key] = dict(status='running', pid=proc.pid, started_at=now())
            write(target, index)
            print('START', key, flush=True)
            try:
                code = proc.wait(timeout=14400)
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
