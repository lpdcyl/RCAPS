"""Resume only never-started E2b keys after an interrupted formal controller.

The frozen manifest and worker remain unchanged. Existing successes and failures
are never retried or overwritten here. Interrupted workers get separate failure
artifacts; independent replay is a later, separately indexed operation.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, ENV, read, write, sha, relative, now, check

HERE = Path(__file__).resolve().parent
FORMAL = HERE / 'formal'
MANIFEST = FORMAL / 'manifest.json'
INDEX = FORMAL / 'index.json'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--acknowledge-dead-pids', action='store_true', required=True)
    args = parser.parse_args()
    manifest = read(MANIFEST)
    check(manifest)
    index = read(INDEX)
    if index['status'] != 'running' or index['manifest_sha256'] != sha(MANIFEST):
        raise RuntimeError('Formal index is not an interrupted matching campaign')
    if set(index['jobs']) != {job['key'] for job in manifest['jobs']}:
        raise RuntimeError('Formal job keys differ from frozen manifest')
    recovery = HERE / 'recovery_after_reboot'
    recovery.mkdir(exist_ok=True)
    snapshot = recovery / 'original_index.json'
    if snapshot.exists():
        raise RuntimeError('Recovery already registered; inspect before another attempt')
    snapshot.write_bytes(INDEX.read_bytes())
    stale = []
    for job in manifest['jobs']:
        key = job['key']
        entry = index['jobs'][key]
        if entry['status'] != 'running':
            continue
        folder = FORMAL / 'runs' / key
        result = folder / 'result.json'
        failure = folder / 'failure.json'
        if result.exists() or failure.exists():
            artifact = result if result.exists() else failure
            status = 'completed' if result.exists() else 'failed'
        else:
            artifact = failure
            write(failure, dict(status='failed', classification='controller_and_worker_interrupted_by_reboot',
                 job=job, original_pid=entry.get('pid'), original_started_at=entry.get('started_at'),
                 detected_at=now(), message='No terminal worker artifact; original log retained'))
            status = 'failed'
        entry.update(status=status, source=relative(artifact), artifact_sha256=sha(artifact),
                     recovered_at=now())
        stale.append(key)
    index['recovery_controller_pid'] = os.getpid()
    index['recovery_started_at'] = now()
    index['recovery_snapshot'] = relative(snapshot)
    write(INDEX, index)
    write(recovery / 'amendment.json', dict(registered_at=now(),
        original_index_sha256=sha(snapshot), frozen_manifest_sha256=sha(MANIFEST),
        interrupted_keys=stale, original_controller_pid=index['controller_pid'],
        policy='Only pending keys run; completed/failed originals retained'))
    pending = [job for job in manifest['jobs'] if index['jobs'][job['key']]['status'] == 'pending']
    active = []
    print('RESUME', len(pending), 'PENDING;', len(stale), 'INTERRUPTED', flush=True)
    while pending or active:
        while pending and len(active) < manifest['max_workers']:
            check(manifest)
            job = pending.pop(0)
            folder = FORMAL / 'runs' / job['key']
            folder.mkdir(parents=True, exist_ok=False)
            log = (folder / 'worker.log').open('x', encoding='utf-8')
            command = [sys.executable, '-u', '-X', 'faulthandler', '-m',
                       'experiments.reviewer_v2.E2b_parallax.run', '--phase', 'formal',
                       '--worker', job['key']]
            proc = subprocess.Popen(command, cwd=ROOT, env=dict(os.environ, **ENV),
                                    stdout=log, stderr=log)
            active.append((proc, job, log, time.monotonic()))
            index['jobs'][job['key']] = dict(status='running', pid=proc.pid,
                                             started_at=now(), recovery=True)
            write(INDEX, index)
            print('START', job['key'], flush=True)
        for item in list(active):
            proc, job, log, start = item
            code = proc.poll()
            timed_out = code is None and time.monotonic() - start > 7200
            if timed_out:
                proc.kill()
                code = proc.wait()
            if code is None:
                continue
            log.close()
            active.remove(item)
            folder = FORMAL / 'runs' / job['key']
            passed = code == 0 and (folder / 'result.json').exists()
            artifact = folder / ('result.json' if passed else 'failure.json')
            if not artifact.exists():
                write(artifact, dict(status='failed', job=job, exit_code=code,
                     classification='timeout' if timed_out else 'native_or_abnormal_exit', finished_at=now()))
            index['jobs'][job['key']].update(status='completed' if passed else 'failed',
                 exit_code=code, source=relative(artifact), artifact_sha256=sha(artifact),
                 finished_at=now())
            write(INDEX, index)
            print('END', job['key'], code, flush=True)
        if active:
            time.sleep(2)
    check(manifest)
    if any(v['status'] in ('pending', 'running') for v in index['jobs'].values()):
        raise RuntimeError('Incomplete E2b index')
    index.update(status='terminal', finished_at=now())
    write(INDEX, index)
    print('TERMINAL', dict(Counter(v['status'] for v in index['jobs'].values())), flush=True)


if __name__ == '__main__':
    main()
