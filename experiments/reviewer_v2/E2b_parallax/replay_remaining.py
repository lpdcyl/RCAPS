"""Second independent replay for E2b keys that failed their first replay."""
import argparse
import os
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, ENV, read, write, sha, relative, now, check
from experiments.reviewer_v2.E2b_parallax.run import HERE, evaluate

FORMAL = HERE / 'formal'
FIRST = HERE / 'failure_replay'
SECOND = HERE / 'failure_replay_round2'


def register():
    SECOND.mkdir(exist_ok=True)
    target = SECOND / 'manifest.json'
    if target.exists():
        return read(target)
    formal = read(FORMAL / 'index.json')
    first = read(FIRST / 'index.json')
    frozen = read(FORMAL / 'manifest.json')
    check(frozen)
    if formal['status'] != 'terminal' or first['status'] != 'terminal':
        raise RuntimeError('Earlier batches are not terminal')
    if first['manifest_sha256'] != sha(FIRST / 'manifest.json'):
        raise RuntimeError('First replay manifest mismatch')
    jobs = [j for j in frozen['jobs'] if first['jobs'].get(j['key'], {}).get('status') == 'failed']
    if len(jobs) != 6:
        raise RuntimeError('Expected six unresolved keys, got ' + str(len(jobs)))
    sources = {}
    for job in jobs:
        key = job['key']
        if formal['jobs'][key]['status'] != 'failed':
            raise RuntimeError('Not an original failure: ' + key)
        sources[key] = []
        for previous in (formal['jobs'][key], first['jobs'][key]):
            if sha(ROOT / previous['source']) != previous['artifact_sha256']:
                raise RuntimeError('Prior artifact changed: ' + key)
            sources[key].append(dict(source=previous['source'], sha256=previous['artifact_sha256']))
    manifest = dict(registered_at=now(), jobs=jobs, sources=sources,
        formal_manifest_sha256=sha(FORMAL / 'manifest.json'),
        formal_index_sha256=sha(FORMAL / 'index.json'),
        first_manifest_sha256=sha(FIRST / 'manifest.json'),
        first_index_sha256=sha(FIRST / 'index.json'),
        worker_source_sha256=sha(Path(__file__)),
        policy='Independent second replay; serial fresh workers; original artifacts read-only')
    write(target, manifest)
    return manifest


def worker(key):
    manifest = read(SECOND / 'manifest.json')
    job = next(j for j in manifest['jobs'] if j['key'] == key)
    folder = SECOND / 'runs' / key
    start = time.perf_counter()
    try:
        result = evaluate(job)
        if len(result['query_samples']) != result['arrivals']:
            raise ValueError('Invalid replay sample count')
        result.update(status='completed', job=job, origin='second_independent_failure_replay',
                      source_formal_manifest_sha256=manifest['formal_manifest_sha256'],
                      elapsed_wall_s=time.perf_counter() - start, finished_at=now())
        write(folder / 'result.json', result)
    except BaseException as exc:
        write(folder / 'failure.json', dict(status='failed', job=job, error=repr(exc),
            traceback=traceback.format_exc(), origin='second_independent_failure_replay',
            elapsed_wall_s=time.perf_counter() - start, finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)


def queue():
    manifest = register()
    index_path = SECOND / 'index.json'
    if index_path.exists():
        raise RuntimeError('Second replay index exists; inspect before recovery')
    index = dict(status='running', controller_pid=os.getpid(), registered_at=now(),
        manifest_sha256=sha(SECOND / 'manifest.json'),
        jobs={j['key']: dict(status='pending') for j in manifest['jobs']})
    write(index_path, index)
    for job in manifest['jobs']:
        key = job['key']
        for previous in manifest['sources'][key]:
            if sha(ROOT / previous['source']) != previous['sha256']:
                raise RuntimeError('Prior artifact changed: ' + key)
        folder = SECOND / 'runs' / key
        folder.mkdir(parents=True, exist_ok=False)
        with (folder / 'worker.log').open('x', encoding='utf-8') as log:
            proc = subprocess.Popen([sys.executable, '-u', '-X', 'faulthandler', '-m',
                'experiments.reviewer_v2.E2b_parallax.replay_remaining', '--worker', key],
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
