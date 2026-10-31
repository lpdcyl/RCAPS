"""Run one preserved failure key into a new directory after conda activation."""
import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, ENV, read, sha, write, now

CAMPAIGNS = {
    'E2b': ('E2b_parallax/formal', 'E2b_parallax/failure_replay_round2'),
    'E3b': ('E3b_goodput/formal', 'E3b_goodput/failure_replay'),
    'E5a': ('E5_scale_kv/formal', 'E5_scale_kv/E5a_failure_replay'),
    'E5b': ('E5_scale_kv/E5b/formal_boundary_diagnostic', 'E5_scale_kv/E5b/boundary_failure_replay'),
}
BASE = ROOT / 'experiments/reviewer_v2'
EXTRA = {'V5': ROOT / 'experiments/v5_failure_replay/formal',
         'V6': ROOT / 'experiments/v6_completion/failure_replay/formal'}


def selected(group, key):
    if group in EXTRA:
        replay_dir = EXTRA[group]
        replay_manifest_path = replay_dir / 'manifest.json'
        replay_manifest = read(replay_manifest_path)
        replay_index = read(replay_dir / 'index.json')
        audit_path = replay_dir.parent / 'FINAL_AUDIT.json'
        if not audit_path.exists():
            audit_path = replay_dir / 'FINAL_AUDIT.json'
        if replay_index['status'] != 'terminal' or replay_index['manifest_sha256'] != sha(replay_manifest_path) or not read(audit_path)['passed']:
            raise RuntimeError('Replay source has not passed audit')
        replay_job = next(j for j in replay_manifest['jobs'] if j['key'] == key)
        last = replay_index['jobs'][key]
        if last['status'] != 'failed' or sha(ROOT / last['source']) != last['artifact_sha256']:
            raise RuntimeError('Replay failure changed')
        if group == 'V5':
            original_dir = ROOT / 'experiments' / replay_job['campaign'] / 'formal'
            original_key = replay_job['original_key']
            original_job = replay_job['job']
        else:
            original_dir = ROOT / 'experiments/v6_completion' / replay_job['campaign'] / 'formal'
            original_job = replay_job['original_job']
            original_key = original_job['key']
        original_manifest = original_dir / 'manifest.json'
        old_index = read(original_dir / 'index.json')
        old = old_index['jobs'][original_key]
        if (old['status'] not in ('failed', 'reused_failure') or
                old_index['manifest_sha256'] != sha(original_manifest) or
                sha(ROOT / old['source']) != old['artifact_sha256']):
            raise RuntimeError('Original failure changed')
        return original_job, original_manifest, old, last
    original, last = (BASE / name for name in CAMPAIGNS[group])
    manifest_path = original / 'manifest.json'
    manifest = read(manifest_path)
    previous = read(last / 'index.json')
    audit_path = BASE / 'E3b_goodput/FINAL_AUDIT.json' if group == 'E3b' else last / 'FINAL_AUDIT.json'
    if previous['status'] != 'terminal' or not read(audit_path)['passed']:
        raise RuntimeError('Source replay audit is not terminal and passed')
    if previous['jobs'][key]['status'] != 'failed':
        raise RuntimeError('Key is not a remaining failure: ' + key)
    job = next(j for j in manifest['jobs'] if j['key'] == key)
    if sha(ROOT / previous['jobs'][key]['source']) != previous['jobs'][key]['artifact_sha256']:
        raise RuntimeError('Previous failure SHA changed')
    original_index = read(original / 'index.json')
    old = original_index['jobs'][key]
    if old['status'] != 'failed' or sha(ROOT / old['source']) != old['artifact_sha256']:
        raise RuntimeError('Original failure SHA changed')
    if original_index['manifest_sha256'] != sha(manifest_path):
        raise RuntimeError('Frozen original manifest changed')
    return job, manifest_path, old, previous['jobs'][key]


def verify_registry(group, key):
    job, manifest, original, replay = selected(group, key)
    if group == 'V5':
        registered = read(EXTRA[group] / 'manifest.json')
        source = next(j for j in registered['jobs'] if j['key'] == key)
        if source['job'] != job or source['prior_failure_sha256'] != original['artifact_sha256']:
            raise RuntimeError('V5 replay lineage mismatch')
    elif group == 'V6':
        registered = read(EXTRA[group] / 'manifest.json')
        source = next(j for j in registered['jobs'] if j['key'] == key)
        if source['original_job'] != job or source['prior_sha256'] != original['artifact_sha256']:
            raise RuntimeError('V6 replay lineage mismatch')
    return job, manifest, original, replay


def evaluate(group, key, job, folder):
    if group == 'V5':
        from experiments.v5_failure_replay.run import evaluate as run
        manifest = read(EXTRA[group] / 'manifest.json')
        replay_job = next(j for j in manifest['jobs'] if j['key'] == key)
        return run(replay_job, folder)
    if group == 'V6':
        from experiments.v6_completion.failure_replay import evaluate as run
        manifest = read(EXTRA[group] / 'manifest.json')
        replay_job = next(j for j in manifest['jobs'] if j['key'] == key)
        return run(replay_job)
    if group == 'E2b':
        from experiments.reviewer_v2.E2b_parallax.run import evaluate as run
        return run(job)
    if group == 'E3b':
        from experiments.reviewer_v2.E3b_goodput.evaluate import evaluate as run
        return run(job['scenario'], job['load'], job['method'], job['seed'])
    if group == 'E5a':
        from experiments.reviewer_v2.E5_scale_kv.run import evaluate as run
        return run(job)
    from experiments.reviewer_v2.E5_scale_kv.run_e5b import evaluate as run
    return run(job, folder)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--group', choices=tuple(CAMPAIGNS) + tuple(EXTRA), required=True)
    parser.add_argument('--key', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--internal', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--validate-only', action='store_true', help='Check activated environment, source SHA and output availability without running')
    args = parser.parse_args()
    prefix = Path(os.environ.get('CONDA_PREFIX', '')).resolve()
    if (os.environ.get('CONDA_DEFAULT_ENV') != 'gllm' or prefix.name.lower() != 'gllm'
            or Path(sys.executable).resolve().parent != prefix):
        raise RuntimeError('Run conda activate gllm before using this command')
    job, manifest, original, replay = verify_registry(args.group, args.key)
    dest = args.output.resolve()
    if not dest.is_relative_to(ROOT / 'experiments'):
        raise RuntimeError('Output must be under this project experiments directory')
    if args.validate_only:
        if dest.exists():
            raise RuntimeError('Output directory exists: ' + str(dest))
        print(json.dumps({'valid': True, 'group': args.group, 'key': args.key,
                          'original_sha256': original['artifact_sha256'],
                          'replay_sha256': replay['artifact_sha256'],
                          'output': str(dest)}, ensure_ascii=False))
        return
    if args.internal:
        start = time.perf_counter()
        try:
            result = evaluate(args.group, args.key, job, dest)
            if 'query_samples' in result and len(result['query_samples']) != result.get('arrivals'):
                raise RuntimeError('Query sample count mismatch')
            result.update(status='completed', job=job, origin='user_manual_independent_rerun',
                          elapsed_wall_s=time.perf_counter() - start, finished_at=now())
            write(dest / 'result.json', result)
        except BaseException as error:
            write(dest / 'failure.json', dict(status='failed', job=job, error=repr(error),
                traceback=traceback.format_exc(), origin='user_manual_independent_rerun',
                elapsed_wall_s=time.perf_counter() - start, finished_at=now()))
            traceback.print_exc()
            raise SystemExit(1)
        return
    dest.mkdir(parents=True, exist_ok=False)
    write(dest / 'lineage.json', dict(group=args.group, key=args.key, job=job,
        original_manifest=manifest.relative_to(ROOT).as_posix(),
        original_manifest_sha256=sha(manifest),
        original_failure=original, last_replay_failure=replay,
        conda_prefix=str(prefix), executable=sys.executable, started_at=now()))
    cmd = [sys.executable, '-u', '-X', 'faulthandler', '-m',
        'experiments.reviewer_v2.manual_rerun', '--group', args.group, '--key', args.key,
        '--output', str(dest), '--internal']
    with (dest / 'worker.log').open('x', encoding='utf-8') as stream:
        process = subprocess.run(cmd, cwd=ROOT, env=dict(os.environ, **ENV),
                                 stdout=stream, stderr=subprocess.STDOUT)
    artifact = dest / ('result.json' if process.returncode == 0 and (dest / 'result.json').exists()
                       else 'failure.json')
    if not artifact.exists():
        write(artifact, dict(status='failed', job=job, exit_code=process.returncode,
            classification='native_or_abnormal_exit', finished_at=now()))
    write(dest / 'index.json', dict(group=args.group, key=args.key,
        status='completed' if artifact.name == 'result.json' else 'failed',
        exit_code=process.returncode, artifact=artifact.name, artifact_sha256=sha(artifact),
        original_sha256=original['artifact_sha256'], replay_sha256=replay['artifact_sha256'],
        finished_at=now()))
    print(json.dumps({'key': args.key, 'status': 'completed' if artifact.name == 'result.json' else 'failed',
                      'output': str(dest), 'exit_code': process.returncode}, ensure_ascii=False))
    if artifact.name != 'result.json':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
