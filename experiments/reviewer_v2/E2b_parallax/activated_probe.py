"""One-key A/B diagnostic for a repeatedly failing E2b window."""
import argparse
import os
import sys
import time
import traceback
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, check, now, read, relative, sha, write
from experiments.reviewer_v2.E2b_parallax.run import HERE, evaluate

KEY = 'multi/load320/shared/seed1'
DEST = HERE / 'activated_probe'
FORMAL = HERE / 'formal'
FIRST = HERE / 'failure_replay'
SECOND = HERE / 'failure_replay_round2'


def register():
    DEST.mkdir(exist_ok=True)
    target = DEST / 'manifest.json'
    if target.exists():
        return read(target)
    if os.environ.get('CONDA_DEFAULT_ENV') != 'gllm':
        raise RuntimeError('Activate conda gllm before registration')
    frozen = read(FORMAL / 'manifest.json')
    check(frozen)
    job = next(j for j in frozen['jobs'] if j['key'] == KEY)
    lineage = []
    for folder in (FORMAL, FIRST, SECOND):
        index = read(folder / 'index.json')
        entry = index['jobs'][KEY]
        if index['status'] != 'terminal' or entry['status'] != 'failed':
            raise RuntimeError('Prior failed batch is not terminal: ' + str(folder))
        if sha(ROOT / entry['source']) != entry['artifact_sha256']:
            raise RuntimeError('Prior artifact SHA changed: ' + str(folder))
        lineage.append(dict(index=relative(folder / 'index.json'),
                            source=entry['source'], sha256=entry['artifact_sha256']))
    manifest = dict(registered_at=now(), job=job, lineage=lineage,
        formal_manifest_sha256=sha(FORMAL / 'manifest.json'),
        worker_source_sha256=sha(Path(__file__)),
        environment=dict(executable=sys.executable, conda_prefix=os.environ.get('CONDA_PREFIX'),
                         conda_default_env=os.environ.get('CONDA_DEFAULT_ENV'),
                         path_head=os.environ.get('PATH', '').split(';')[:7]),
        policy='Single activated gllm worker; diagnostic only; prior artifacts read-only')
    write(target, manifest)
    return manifest


def run():
    manifest = register()
    if (DEST / 'index.json').exists():
        raise RuntimeError('Probe already indexed')
    job = manifest['job']
    write(DEST / 'index.json', dict(status='running', job=job, pid=os.getpid(),
                                   manifest_sha256=sha(DEST / 'manifest.json'),
                                   started_at=now()))
    start = time.perf_counter()
    try:
        check(read(FORMAL / 'manifest.json'))
        result = evaluate(job)
        if len(result['query_samples']) != result['arrivals']:
            raise ValueError('Query sample count mismatch')
        result.update(status='completed', job=job, origin='activated_environment_probe',
                      elapsed_wall_s=time.perf_counter()-start, finished_at=now())
        artifact = DEST / 'result.json'
        write(artifact, result)
        status = 'completed'
    except BaseException as exc:
        artifact = DEST / 'failure.json'
        write(artifact, dict(status='failed', job=job, error=repr(exc),
                             traceback=traceback.format_exc(),
                             origin='activated_environment_probe',
                             elapsed_wall_s=time.perf_counter()-start, finished_at=now()))
        status = 'failed'
        traceback.print_exc()
    write(DEST / 'index.json', dict(status=status, job=job,
        manifest_sha256=sha(DEST / 'manifest.json'), source=relative(artifact),
        artifact_sha256=sha(artifact), finished_at=now()))
    print('PROBE', status, flush=True)
    if status == 'failed':
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--register', action='store_true')
    args = parser.parse_args()
    if args.register:
        register()
    else:
        run()
