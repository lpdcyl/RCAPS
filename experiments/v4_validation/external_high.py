"""Twelve preregistered high-load external windows, using unchanged adapters."""
from __future__ import annotations

import argparse
import faulthandler
import os
from pathlib import Path
import subprocess
import sys
import time

from experiments.v4_formal.run import ROOT, read, write, digest, environment, stamp, capture
from experiments.v4_external.run import validate as validate_external
from experiments.v4_external.evaluate import evaluate

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'external_manifest.json'
INDEX = HERE / 'external_index.json'


def jobs():
    return [dict(key=f'{scenario}/load{load}/{method}/seed{seed}',
                 scenario=scenario, load=load, method=method, seed=seed)
            for scenario, load in [('single', 700), ('multi', 320)]
            for method in ['swarm', 'separate'] for seed in [0, 1, 2]]


def freeze():
    validate_external()
    content = dict(
        registered_at=stamp(), source_commit=subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        authorization='User requested autonomous completion of the research contract, 2026-10-26.',
        protocol=dict(duration_s=1800, warmup_s=0, drain=False, concurrency=2,
                      seeds=[0, 1, 2], adaptation='None; existing external adapters and layouts.',
                      failure_policy='Stop dispatch, retain failures; no automatic retries or tuning.'),
        environment=environment(), jobs=jobs(), sources_sha256={
            'experiments/v4_validation/external_high.py': digest(Path(__file__)),
            'experiments/v4_external/manifest.json': digest(ROOT/'experiments/v4_external/manifest.json'),
            'experiments/v4_formal/manifest.json': digest(ROOT/'experiments/v4_formal/manifest.json'),
            'experiments/v4_external/preflight.json': digest(ROOT/'experiments/v4_external/preflight.json')},
        engineering_validation='Reuse hash-verified existing external-adapter parity; no algorithm changes.')
    if MANIFEST.exists():
        raise RuntimeError('Manifest already exists; do not refreeze an executed protocol')
    write(MANIFEST, content)
    print('REGISTERED', len(content['jobs']), digest(MANIFEST), flush=True)


def validate():
    validate_external()
    frozen = read(MANIFEST)
    assert environment() == frozen['environment'], 'Environment drift'
    for name, expected in frozen['sources_sha256'].items():
        assert digest(ROOT/name) == expected, f'Source drift: {name}'
    return frozen


def one(key):
    faulthandler.enable()
    frozen = validate()
    job = next(j for j in frozen['jobs'] if j['key'] == key)
    out = HERE/'external_runs'/key/'result.json'
    assert not out.exists() and not out.with_name('failure.json').exists(), 'Attempt exists'
    started = time.perf_counter()
    try:
        row = evaluate(job['scenario'], job['method'], job['load'], 1800, job['seed'], ROOT)
        assert row['arrivals'] > 0 and row['gpu_seconds_per_output_token'] > 0
        row.update(job=job, manifest_sha256=digest(MANIFEST), environment=environment(),
                   elapsed_wall_s=time.perf_counter()-started, finished_at=stamp(), status='completed')
        validate()
        write(out, row)
        print('COMPLETED', key, row['elapsed_wall_s'], flush=True)
    except BaseException as error:
        write(out.with_name('failure.json'), dict(capture(error), job=job, pid=os.getpid(),
              elapsed_wall_s=time.perf_counter()-started, finished_at=stamp()))
        raise


def queue():
    frozen = validate()
    assert not INDEX.exists(), 'Queue already exists; preserve its record'
    pending, active, halted = list(frozen['jobs']), [], False
    index = dict(status='running', started_at=stamp(), pid=os.getpid(), jobs={},
                 manifest_sha256=digest(MANIFEST))
    write(INDEX, index)
    while pending or active:
        while pending and len(active) < 2 and not halted:
            job = pending.pop(0)
            directory = HERE/'external_runs'/job['key']
            directory.mkdir(parents=True, exist_ok=True)
            log = (directory/'worker.log').open('x', encoding='utf-8')
            process = subprocess.Popen([sys.executable, '-u', '-X', 'faulthandler', '-m',
                'experiments.v4_validation.external_high', '--phase', 'one', '--key', job['key']],
                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            active.append((process, log, job))
            index['jobs'][job['key']] = dict(status='running', pid=process.pid, started_at=stamp())
            write(INDEX, index)
            print('START', job['key'], process.pid, flush=True)
        for process, log, job in list(active):
            code = process.poll()
            if code is None:
                continue
            log.close()
            active.remove((process, log, job))
            out = HERE/'external_runs'/job['key']/'result.json'
            success = code == 0 and out.exists()
            index['jobs'][job['key']].update(status='completed' if success else 'failed',
                exit_code=code, finished_at=stamp(), result_sha256=digest(out) if success else None)
            if not success and not out.with_name('failure.json').exists():
                write(out.with_name('failure.json'), dict(kind='process_failure', exit_code=code,
                    job=job, finished_at=stamp()))
            halted |= not success
            write(INDEX, index)
            print('DONE' if success else 'FAILED', job['key'], code, flush=True)
        if halted and not active:
            break
        if active:
            time.sleep(2)
    index.update(status='halted' if halted else 'completed', finished_at=stamp(),
                 pending=[j['key'] for j in pending])
    write(INDEX, index)
    if halted:
        raise SystemExit('Failure retained; queue halted')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', required=True, choices=['freeze', 'queue', 'one'])
    parser.add_argument('--key')
    args = parser.parse_args()
    if args.phase == 'one':
        one(args.key)
    elif args.phase == 'freeze':
        freeze()
    else:
        queue()
