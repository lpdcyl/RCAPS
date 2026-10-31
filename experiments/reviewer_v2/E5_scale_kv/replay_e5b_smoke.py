"""Independently replay failed E5b smoke keys in an activated conda environment."""
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

SMOKE = HERE / 'E5b' / 'smoke'
REPLAY = HERE / 'E5b' / 'smoke_failure_replay'


def register():
    REPLAY.mkdir(exist_ok=True)
    target = REPLAY / 'manifest.json'
    if target.exists():
        return read(target)
    original_manifest = read(SMOKE / 'manifest.json')
    original_index = read(SMOKE / 'index.json')
    check(original_manifest)
    if original_index['status'] != 'terminal':
        raise RuntimeError('Smoke batch is not terminal')
    if original_index['manifest_sha256'] != sha(SMOKE / 'manifest.json'):
        raise RuntimeError('Smoke manifest changed')
    jobs = [job for job in original_manifest['jobs']
            if original_index['jobs'][job['key']]['status'] == 'failed']
    if len(jobs) != 3:
        raise RuntimeError(f'Expected 3 failed smoke keys, found {len(jobs)}')
    lineage = {}
    for job in jobs:
        entry = original_index['jobs'][job['key']]
        if sha(ROOT / entry['source']) != entry['artifact_sha256']:
            raise RuntimeError('Original failure changed: ' + job['key'])
        lineage[job['key']] = {'source': entry['source'], 'sha256': entry['artifact_sha256']}
    manifest = dict(registered_at=now(), jobs=jobs, original_failures=lineage,
                    smoke_manifest_sha256=sha(SMOKE / 'manifest.json'),
                    smoke_index_sha256=sha(SMOKE / 'index.json'),
                    worker_source_sha256=sha(Path(__file__)),
                    environment={'executable': sys.executable,
                                 'conda_prefix': os.environ.get('CONDA_PREFIX'),
                                 'conda_default_env': os.environ.get('CONDA_DEFAULT_ENV')},
                    policy='Fresh serial workers in independent directory; original failures read-only')
    if manifest['environment']['conda_default_env'] != 'gllm':
        raise RuntimeError('Activate conda gllm before registration')
    write(target, manifest)
    return manifest


def worker(key):
    manifest = read(REPLAY / 'manifest.json')
    job = next(j for j in manifest['jobs'] if j['key'] == key)
    folder = REPLAY / 'runs' / key
    start = time.perf_counter()
    try:
        check(read(SMOKE / 'manifest.json'))
        result = evaluate(job, folder)
        if len(result['query_samples']) != result['arrivals']:
            raise ValueError('Query sample count mismatch')
        result.update(status='completed', job=job, origin='independent_activated_smoke_replay',
                      source_smoke_manifest_sha256=manifest['smoke_manifest_sha256'],
                      elapsed_wall_s=time.perf_counter()-start, finished_at=now())
        write(folder / 'result.json', result)
    except BaseException as exc:
        write(folder / 'failure.json', dict(status='failed', job=job, error=repr(exc),
              traceback=traceback.format_exc(), origin='independent_activated_smoke_replay',
              elapsed_wall_s=time.perf_counter()-start, finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)


def queue():
    manifest = register()
    index_path = REPLAY / 'index.json'
    if index_path.exists():
        raise RuntimeError('Replay index exists; inspect before recovery')
    index = dict(status='running', controller_pid=os.getpid(), registered_at=now(),
                 manifest_sha256=sha(REPLAY / 'manifest.json'),
                 jobs={j['key']: dict(status='pending') for j in manifest['jobs']})
    write(index_path, index)
    for job in manifest['jobs']:
        key = job['key']
        prior = manifest['original_failures'][key]
        if sha(ROOT / prior['source']) != prior['sha256']:
            raise RuntimeError('Original failure changed: ' + key)
        folder = REPLAY / 'runs' / key
        folder.mkdir(parents=True, exist_ok=False)
        with (folder / 'worker.log').open('x', encoding='utf-8') as log:
            proc = subprocess.Popen([sys.executable, '-u', '-X', 'faulthandler', '-m',
                'experiments.reviewer_v2.E5_scale_kv.replay_e5b_smoke', '--worker', key],
                cwd=ROOT, env=dict(os.environ, **ENV), stdout=log, stderr=log)
            index['jobs'][key] = dict(status='running', pid=proc.pid, started_at=now())
            write(index_path, index)
            print('START', key, flush=True)
            try:
                code = proc.wait(timeout=7200)
            except subprocess.TimeoutExpired:
                proc.kill()
                code = proc.wait()
        passed = code == 0 and (folder / 'result.json').exists()
        artifact = folder / ('result.json' if passed else 'failure.json')
        if not artifact.exists():
            write(artifact, dict(status='failed', job=job, exit_code=code,
                                 classification='native_or_abnormal_exit', finished_at=now()))
        index['jobs'][key].update(status='completed' if passed else 'failed',
            exit_code=code, source=relative(artifact), artifact_sha256=sha(artifact), finished_at=now())
        write(index_path, index)
        print('END', key, code, flush=True)
    index.update(status='terminal', finished_at=now())
    write(index_path, index)
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
