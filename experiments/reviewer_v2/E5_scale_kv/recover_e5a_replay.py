"""Continue only never-started E5a replay keys after a machine reboot.

This recovery controller preserves the formal campaign and every existing
replay artifact. An interrupted replay worker is recorded as a failure; it is
eligible for a later, independently indexed replay round.
"""
import argparse
import os
import subprocess
import sys
import time
from collections import Counter

from experiments.v5_core_supplement.run import ROOT, ENV, read, write, sha, relative, now
from experiments.reviewer_v2.E5_scale_kv.replay_e5a import FORMAL, REPLAY


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--acknowledge-dead-pids', required=True, action='store_true')
    parser.add_argument('--recovery-name', default='recovery_after_reboot')
    args = parser.parse_args()
    manifest_path = REPLAY / 'manifest.json'
    index_path = REPLAY / 'index.json'
    manifest = read(manifest_path)
    index = read(index_path)
    if index['status'] != 'running' or index['manifest_sha256'] != sha(manifest_path):
        raise RuntimeError('Replay campaign is not an interrupted matching campaign')
    if set(index['jobs']) != {job['key'] for job in manifest['jobs']}:
        raise RuntimeError('Replay job population changed')
    if manifest['source_manifest_sha256'] != sha(FORMAL / 'manifest.json'):
        raise RuntimeError('Formal source manifest changed')
    if manifest['source_index_sha256'] != sha(FORMAL / 'index.json'):
        raise RuntimeError('Formal source index changed')
    original = read(FORMAL / 'index.json')
    for job in manifest['jobs']:
        key = job['key']
        source = manifest['original_failures'][key]
        prior = original['jobs'][key]
        if prior['status'] != 'failed' or prior['source'] != source['source']:
            raise RuntimeError('Formal failure lineage changed: ' + key)
        if sha(ROOT / source['source']) != source['artifact_sha256']:
            raise RuntimeError('Formal failure artifact changed: ' + key)
        entry = index['jobs'][key]
        if entry['status'] in ('failed', 'completed'):
            if sha(ROOT / entry['source']) != entry['artifact_sha256']:
                raise RuntimeError('Existing replay artifact changed: ' + key)

    if not args.recovery_name.startswith('recovery_after_reboot') or '/' in args.recovery_name or '\\' in args.recovery_name:
        raise ValueError('Recovery name must be a local recovery_after_reboot directory')
    recovery = REPLAY / args.recovery_name
    recovery.mkdir(exist_ok=True)
    snapshot = recovery / 'original_index.json'
    if snapshot.exists():
        raise RuntimeError('Recovery already registered; inspect before another attempt')
    snapshot.write_bytes(index_path.read_bytes())
    interrupted = []
    for job in manifest['jobs']:
        key = job['key']
        entry = index['jobs'][key]
        if entry['status'] != 'running':
            continue
        folder = REPLAY / 'runs' / key
        result, failure = folder / 'result.json', folder / 'failure.json'
        if result.exists() and failure.exists():
            raise RuntimeError('Conflicting terminal artifacts: ' + key)
        if result.exists():
            artifact, status = result, 'completed'
        elif failure.exists():
            artifact, status = failure, 'failed'
        else:
            artifact, status = failure, 'failed'
            write(artifact, dict(status='failed', job=job,
                classification='controller_and_worker_interrupted_by_reboot',
                original_pid=entry.get('pid'), original_started_at=entry.get('started_at'),
                detected_at=now(), origin='independent_failure_replay',
                message='No terminal worker artifact; original worker.log retained'))
        entry.update(status=status, source=relative(artifact),
                     artifact_sha256=sha(artifact), recovered_at=now())
        interrupted.append(key)
    index.update(recovery_controller_pid=os.getpid(), recovery_started_at=now(),
                 recovery_snapshot=relative(snapshot))
    write(index_path, index)
    write(recovery / 'amendment.json', dict(registered_at=now(),
        original_index_sha256=sha(snapshot), replay_manifest_sha256=sha(manifest_path),
        formal_index_sha256=sha(FORMAL / 'index.json'), interrupted_keys=interrupted,
        original_controller_pid=index['controller_pid'],
        policy='Keep terminal replay artifacts; mark interrupted key; run only pending keys'))
    pending = [job for job in manifest['jobs'] if index['jobs'][job['key']]['status'] == 'pending']
    print('RESUME', len(pending), 'PENDING;', len(interrupted), 'INTERRUPTED', flush=True)
    for job in pending:
        key = job['key']
        source = manifest['original_failures'][key]
        if sha(ROOT / source['source']) != source['artifact_sha256']:
            raise RuntimeError('Formal failure artifact changed during recovery: ' + key)
        folder = REPLAY / 'runs' / key
        folder.mkdir(parents=True, exist_ok=False)
        with (folder / 'worker.log').open('x', encoding='utf-8') as log:
            proc = subprocess.Popen([sys.executable, '-u', '-X', 'faulthandler', '-m',
                'experiments.reviewer_v2.E5_scale_kv.replay_e5a', '--worker', key],
                cwd=ROOT, env=dict(os.environ, **ENV), stdout=log, stderr=log)
            index['jobs'][key] = dict(status='running', pid=proc.pid,
                                      started_at=now(), recovery=True)
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
            exit_code=code, source=relative(artifact), artifact_sha256=sha(artifact),
            finished_at=now())
        write(index_path, index)
        print('END', key, code, flush=True)
    if any(entry['status'] in ('pending', 'running') for entry in index['jobs'].values()):
        raise RuntimeError('Replay index still has nonterminal keys')
    index.update(status='terminal', finished_at=now())
    write(index_path, index)
    print('TERMINAL', dict(Counter(e['status'] for e in index['jobs'].values())), flush=True)


if __name__ == '__main__':
    main()
