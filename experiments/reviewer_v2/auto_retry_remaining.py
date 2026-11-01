"""One-attempt independent retry of every unresolved audited RCAPS key.

Preserves all formal and earlier replay artifacts. The index allows a controller
to resume only jobs that were never started after a machine restart.
"""
import argparse
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

from experiments.v5_core_supplement.run import ENV, ROOT, now, read, sha, write
from experiments.reviewer_v2.build_manual_rerun_commands import AUDITS, INDEXES
from experiments.reviewer_v2.manual_rerun import verify_registry

HERE = Path(__file__).resolve().parent
BATCH = HERE / 'remaining_failure_retry_20261031'
MANIFEST = BATCH / 'manifest.json'
INDEX = BATCH / 'index.json'
PYTHON = Path(sys.executable).resolve()


def environment():
    prefix = Path(os.environ.get('CONDA_PREFIX', '')).resolve()
    if (os.environ.get('CONDA_DEFAULT_ENV') != 'gllm' or prefix.name.lower() != 'gllm'
            or PYTHON.parent != prefix):
        raise RuntimeError('Activate conda gllm before register/run/resume')
    return {'conda_prefix': str(prefix), 'python': str(PYTHON),
            'conda_default_env': os.environ['CONDA_DEFAULT_ENV'],
            'path_head': os.environ.get('PATH', '').split(os.pathsep)[:7]}


def register():
    env = environment()
    if MANIFEST.exists():
        return read(MANIFEST)
    BATCH.mkdir(parents=True, exist_ok=True)
    jobs, sources = [], {}
    for group, path in INDEXES.items():
        source_index = ROOT / path
        source_audit = ROOT / AUDITS[group]
        index, audit = read(source_index), read(source_audit)
        if index['status'] != 'terminal' or not audit['passed']:
            raise RuntimeError('Source not audited: ' + group)
        sources[group] = {'index': path, 'index_sha256': sha(source_index),
                          'audit': AUDITS[group], 'audit_sha256': sha(source_audit)}
        for key, entry in sorted(index['jobs'].items()):
            if entry['status'] != 'failed':
                continue
            job, original_manifest, original, last = verify_registry(group, key)
            jobs.append({'group': group, 'key': key, 'job': job,
                         'source_manifest': original_manifest.relative_to(ROOT).as_posix(),
                         'source_manifest_sha256': sha(original_manifest),
                         'original_failure_sha256': original['artifact_sha256'],
                         'last_failure_sha256': last['artifact_sha256']})
    if len(jobs) != 254:
        raise RuntimeError('Expected 254 unresolved keys, got ' + str(len(jobs)))
    manifest = {'registered_at': now(), 'environment': env, 'jobs': jobs,
                'sources': sources, 'runner_source_sha256': sha(HERE / 'manual_rerun.py'),
                'controller_source_sha256': sha(Path(__file__)),
                'policy': 'One fresh independent retry per unresolved key; one worker at a time; originals immutable; no imputation.'}
    write(MANIFEST, manifest)
    return manifest


def verify(manifest):
    if sha(HERE / 'manual_rerun.py') != manifest['runner_source_sha256']:
        raise RuntimeError('Manual runner changed after registration')
    if sha(Path(__file__)) != manifest['controller_source_sha256']:
        raise RuntimeError('Controller changed after registration')
    if environment()['conda_prefix'] != manifest['environment']['conda_prefix']:
        raise RuntimeError('Conda prefix changed')
    for group, source in manifest['sources'].items():
        if sha(ROOT / source['index']) != source['index_sha256'] or sha(ROOT / source['audit']) != source['audit_sha256']:
            raise RuntimeError('Audited source changed: ' + group)


def fresh_index(manifest):
    if INDEX.exists():
        raise RuntimeError('Index already exists; use --resume only after checking controller PID')
    index = {'status': 'running', 'controller_pid': os.getpid(),
             'manifest_sha256': sha(MANIFEST), 'started_at': now(),
             'jobs': {f"{j['group']}::{j['key']}": {'status': 'pending'} for j in manifest['jobs']}}
    write(INDEX, index)
    return index


def process_alive(pid):
    if not pid:
        return False
    proc = subprocess.run(['powershell', '-NoProfile', '-Command',
        f'if (Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue) {{ exit 0 }} else {{ exit 1 }}'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc.returncode == 0


def resume_index(manifest):
    if not INDEX.exists():
        raise RuntimeError('No index to resume')
    index = read(INDEX)
    if index['manifest_sha256'] != sha(MANIFEST):
        raise RuntimeError('Manifest changed')
    if index['status'] == 'terminal':
        return index
    if process_alive(index.get('controller_pid')):
        raise RuntimeError('Previous controller is still alive')
    for token, state in index['jobs'].items():
        if state['status'] != 'running':
            continue
        if process_alive(state.get('pid')):
            raise RuntimeError('Existing worker still alive: ' + token)
        folder = BATCH / 'runs' / token.split('::', 1)[0] / token.split('::', 1)[1]
        child = folder / 'index.json'
        if child.exists():
            outcome = read(child)
            state.update(status=outcome['status'], child_index_sha256=sha(child),
                         finished_at=outcome['finished_at'], interrupted_recovered=True)
        else:
            failure = folder / 'interrupted.json'
            write(failure, {'status': 'failed', 'classification': 'controller_and_worker_interrupted',
                            'key': token, 'recorded_at': now()})
            state.update(status='failed', interruption_sha256=sha(failure),
                         finished_at=now(), interrupted_recovered=True)
    index['controller_pid'] = os.getpid()
    index['resumed_at'] = now()
    write(INDEX, index)
    return index


def run(resume=False):
    manifest = register()
    verify(manifest)
    index = resume_index(manifest) if resume else fresh_index(manifest)
    if index['status'] == 'terminal':
        print('ALREADY_TERMINAL', dict(Counter(v['status'] for v in index['jobs'].values())), flush=True)
        return
    for job in manifest['jobs']:
        token = f"{job['group']}::{job['key']}"
        if index['jobs'][token]['status'] != 'pending':
            continue
        verify(manifest)
        _, source_manifest, original, last = verify_registry(job['group'], job['key'])
        if (sha(source_manifest) != job['source_manifest_sha256'] or
                original['artifact_sha256'] != job['original_failure_sha256'] or
                last['artifact_sha256'] != job['last_failure_sha256']):
            raise RuntimeError('Registered source lineage changed: ' + token)
        folder = BATCH / 'runs' / job['group'] / job['key']
        if folder.exists():
            raise RuntimeError('Refuse to overwrite retry folder: ' + str(folder))
        cmd = [sys.executable, '-u', '-m', 'experiments.reviewer_v2.manual_rerun',
               '--group', job['group'], '--key', job['key'], '--output', str(folder)]
        log = BATCH / 'controller.log'
        with log.open('a', encoding='utf-8') as stream:
            proc = subprocess.Popen(cmd, cwd=ROOT, env=dict(os.environ, **ENV),
                                    stdout=stream, stderr=subprocess.STDOUT)
            index['jobs'][token] = {'status': 'running', 'pid': proc.pid, 'started_at': now()}
            write(INDEX, index)
            print('START', token, proc.pid, flush=True)
            try:
                code = proc.wait(timeout=14400)
            except subprocess.TimeoutExpired:
                proc.kill()
                code = proc.wait()
        child = folder / 'index.json'
        if child.exists():
            outcome = read(child)
            status = outcome['status']
            index['jobs'][token].update(status=status, exit_code=code,
                                        child_index_sha256=sha(child), finished_at=now())
        else:
            folder.mkdir(parents=True, exist_ok=True)
            failure = folder / 'controller_failure.json'
            write(failure, {'status': 'failed', 'key': token, 'exit_code': code,
                            'classification': 'child_did_not_write_index', 'finished_at': now()})
            index['jobs'][token].update(status='failed', exit_code=code,
                                        controller_failure_sha256=sha(failure), finished_at=now())
        write(INDEX, index)
        print('END', token, index['jobs'][token]['status'], code, flush=True)
    index.update(status='terminal', finished_at=now())
    write(INDEX, index)
    print('TERMINAL', dict(Counter(v['status'] for v in index['jobs'].values())), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--register', action='store_true')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.register:
        register()
    else:
        run(resume=args.resume)
