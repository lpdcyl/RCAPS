"""Resume the frozen independent-retry campaign with two concurrent keys.

This is a separate controller. It never changes the frozen manifest, source
runner, or previously written key artifacts. One running key can be adopted
after the original single-worker controller has been stopped.
"""
import argparse
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from experiments.v5_core_supplement.run import ENV, ROOT, now, read, sha, write
from experiments.reviewer_v2.auto_retry_remaining import (
    BATCH, INDEX, MANIFEST, environment, process_alive, verify,
)
from experiments.reviewer_v2.manual_rerun import verify_registry

MAX_WORKERS = 2
POLL_SECONDS = 3


def finish(index, token, folder, exit_code):
    child = folder / 'index.json'
    if child.exists():
        outcome = read(child)
        if outcome['status'] not in ('completed', 'failed'):
            raise RuntimeError('Invalid child status: ' + token)
        index['jobs'][token].update(
            status=outcome['status'], exit_code=exit_code,
            child_index_sha256=sha(child), finished_at=now(),
        )
    else:
        folder.mkdir(parents=True, exist_ok=True)
        failure = folder / 'controller_failure.json'
        if failure.exists():
            raise RuntimeError('Existing controller failure: ' + token)
        write(failure, {'status': 'failed', 'key': token, 'exit_code': exit_code,
                        'classification': 'child_did_not_write_index', 'finished_at': now()})
        index['jobs'][token].update(
            status='failed', exit_code=exit_code,
            controller_failure_sha256=sha(failure), finished_at=now(),
        )
    write(INDEX, index)
    print('END', token, index['jobs'][token]['status'], exit_code, flush=True)


def start(index, job):
    token = f"{job['group']}::{job['key']}"
    if index['jobs'][token]['status'] != 'pending':
        return None
    _, source_manifest, original, previous = verify_registry(job['group'], job['key'])
    if (sha(source_manifest) != job['source_manifest_sha256'] or
            original['artifact_sha256'] != job['original_failure_sha256'] or
            previous['artifact_sha256'] != job['last_failure_sha256']):
        raise RuntimeError('Registered source lineage changed: ' + token)
    folder = BATCH / 'runs' / job['group'] / job['key']
    if folder.exists():
        raise RuntimeError('Refuse to overwrite retry folder: ' + str(folder))
    cmd = [sys.executable, '-u', '-m', 'experiments.reviewer_v2.manual_rerun',
           '--group', job['group'], '--key', job['key'], '--output', str(folder)]
    with (BATCH / 'parallel_controller.log').open('a', encoding='utf-8') as stream:
        proc = subprocess.Popen(cmd, cwd=ROOT, env=dict(os.environ, **ENV),
                                stdout=stream, stderr=subprocess.STDOUT)
    index['jobs'][token] = {'status': 'running', 'pid': proc.pid, 'started_at': now(),
                            'controller': 'parallel_two_worker'}
    write(INDEX, index)
    print('START', token, proc.pid, flush=True)
    return proc


def run():
    environment()
    manifest = read(MANIFEST)
    verify(manifest)
    index = read(INDEX)
    if index['manifest_sha256'] != sha(MANIFEST) or len(index['jobs']) != len(manifest['jobs']):
        raise RuntimeError('Frozen manifest or index mismatch')
    if index['status'] == 'terminal':
        print('ALREADY_TERMINAL', flush=True)
        return
    previous_pid = index['controller_pid']
    if previous_pid != os.getpid() and process_alive(previous_pid):
        raise RuntimeError('Existing controller is still alive: ' + str(previous_pid))
    running = {token: {'pid': int(state['pid']), 'proc': None}
               for token, state in index['jobs'].items() if state['status'] == 'running'}
    if len(running) > MAX_WORKERS:
        raise RuntimeError('Too many existing workers to adopt')
    for token, state in running.items():
        if not process_alive(state['pid']) and not (BATCH / 'runs' / token.replace('::', '/', 1) / 'index.json').exists():
            raise RuntimeError('Missing worker and result; investigate before resuming: ' + token)
    index['controller_pid'] = os.getpid()
    index['controller_mode'] = 'parallel_two_worker'
    index.setdefault('controller_handoffs', []).append(
        {'at': now(), 'from_pid': previous_pid, 'to_pid': os.getpid(),
         'adopted': list(running), 'max_workers': MAX_WORKERS})
    write(INDEX, index)
    print('HANDOFF', previous_pid, os.getpid(), 'adopted', list(running), flush=True)
    try:
        while True:
            verify(manifest)
            for token, state in list(running.items()):
                proc, pid = state['proc'], state['pid']
                code = proc.poll() if proc else None
                if code is None and process_alive(pid):
                    continue
                if code is None:
                    # The adopted process has exited; let its atomic index write settle.
                    child = BATCH / 'runs' / token.replace('::', '/', 1) / 'index.json'
                    for _ in range(10):
                        if child.exists():
                            code = read(child).get('exit_code')
                            break
                        time.sleep(1)
                folder = BATCH / 'runs' / token.replace('::', '/', 1)
                finish(index, token, folder, code)
                del running[token]
            for job in manifest['jobs']:
                if len(running) >= MAX_WORKERS:
                    break
                token = f"{job['group']}::{job['key']}"
                if index['jobs'][token]['status'] != 'pending':
                    continue
                proc = start(index, job)
                running[token] = {'pid': proc.pid, 'proc': proc}
            if not running and all(s['status'] in ('completed', 'failed')
                                   for s in index['jobs'].values()):
                index.update(status='terminal', finished_at=now())
                write(INDEX, index)
                print('TERMINAL', dict(Counter(s['status'] for s in index['jobs'].values())), flush=True)
                return
            time.sleep(POLL_SECONDS)
    except BaseException:
        print('CONTROLLER_ERROR; preserve workers and inspect index before restart', flush=True)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume', action='store_true', required=True)
    parser.parse_args()
    run()
