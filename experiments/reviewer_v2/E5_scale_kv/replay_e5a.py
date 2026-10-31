"""Independent E5a failure replay; original formal artifacts are read-only."""
import argparse
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, ENV, read, write, sha, relative, now, check
from experiments.reviewer_v2.E5_scale_kv.run import HERE, evaluate

FORMAL = HERE / 'formal'
REPLAY = HERE / 'E5a_failure_replay'


def register():
    REPLAY.mkdir(exist_ok=True)
    target = REPLAY / 'manifest.json'
    if target.exists():
        manifest = read(target)
        check(read(FORMAL/'manifest.json'))
        return manifest
    original = read(FORMAL / 'index.json')
    frozen = read(FORMAL / 'manifest.json')
    check(frozen)
    if original['status'] != 'terminal':
        raise RuntimeError('Original formal batch is not terminal')
    jobs = [job for job in frozen['jobs']
            if original['jobs'][job['key']]['status']=='failed']
    manifest = dict(registered_at=now(), source_index_sha256=sha(FORMAL/'index.json'),
        source_manifest_sha256=sha(FORMAL/'manifest.json'), jobs=jobs,
        original_failures={job['key']:dict(source=original['jobs'][job['key']]['source'],
            artifact_sha256=original['jobs'][job['key']]['artifact_sha256']) for job in jobs},
        worker_source_sha256=sha(Path(__file__)),
        policy='Independent fresh process per key; no original overwrite')
    write(target,manifest)
    return manifest


def worker(key):
    manifest=read(REPLAY/'manifest.json')
    job=next(j for j in manifest['jobs'] if j['key']==key)
    folder=REPLAY/'runs'/key
    start=time.perf_counter()
    try:
        result=evaluate(job)
        if len(result['query_samples']) != result['arrivals']:
            raise ValueError('Invalid replay sample count')
        result.update(status='completed',job=job,origin='independent_failure_replay',
                      source_formal_manifest_sha256=manifest['source_manifest_sha256'],
                      elapsed_wall_s=time.perf_counter()-start,finished_at=now())
        write(folder/'result.json',result)
    except BaseException as exc:
        import traceback
        write(folder/'failure.json',dict(status='failed',job=job,error=repr(exc),
              traceback=traceback.format_exc(),origin='independent_failure_replay',
              elapsed_wall_s=time.perf_counter()-start,finished_at=now()))
        traceback.print_exc()
        raise SystemExit(1)


def queue():
    manifest=register()
    index_path=REPLAY/'index.json'
    if index_path.exists():
        raise RuntimeError('Replay index already exists')
    original=read(FORMAL/'index.json')
    index=dict(status='running',controller_pid=os.getpid(),registered_at=now(),
               manifest_sha256=sha(REPLAY/'manifest.json'),
               jobs={job['key']:dict(status='pending') for job in manifest['jobs']})
    write(index_path,index)
    active=[]; pending=list(manifest['jobs'])
    # Serialize independent replays to test whether original concurrent workers
    # contributed to the Windows native failures. Original results stay intact.
    while pending or active:
        while pending and len(active)<1:
            job=pending.pop(0)
            key=job['key']
            origin=manifest['original_failures'][key]
            if sha(ROOT/origin['source'])!=origin['artifact_sha256']:
                raise RuntimeError('Original failure artifact changed: '+key)
            folder=REPLAY/'runs'/key
            folder.mkdir(parents=True,exist_ok=False)
            log=(folder/'worker.log').open('x',encoding='utf-8')
            proc=subprocess.Popen([sys.executable,'-u','-X','faulthandler','-m',
                'experiments.reviewer_v2.E5_scale_kv.replay_e5a','--worker',key],
                cwd=ROOT,env=dict(os.environ,**ENV),stdout=log,stderr=log)
            active.append((proc,job,log,time.monotonic()))
            index['jobs'][key]=dict(status='running',pid=proc.pid,started_at=now())
            write(index_path,index)
            print('START',key,flush=True)
        for item in list(active):
            proc,job,log,start=item
            code=proc.poll()
            timed_out=code is None and time.monotonic()-start>7200
            if timed_out: proc.kill();code=proc.wait()
            if code is None: continue
            log.close();active.remove(item)
            folder=REPLAY/'runs'/job['key']
            passed=code==0 and (folder/'result.json').exists()
            artifact=folder/('result.json' if passed else 'failure.json')
            if not artifact.exists():
                write(artifact,dict(status='failed',job=job,exit_code=code,
                      classification='timeout' if timed_out else 'native_or_abnormal_exit',finished_at=now()))
            index['jobs'][job['key']].update(status='completed' if passed else 'failed',
                exit_code=code,source=relative(artifact),artifact_sha256=sha(artifact),finished_at=now())
            write(index_path,index)
            print('END',job['key'],code,flush=True)
        if active: time.sleep(2)
    index.update(status='terminal',finished_at=now())
    write(index_path,index)
    print('TERMINAL',dict(Counter(v['status'] for v in index['jobs'].values())),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--register',action='store_true')
    parser.add_argument('--worker')
    args=parser.parse_args()
    if args.worker: worker(args.worker)
    elif args.register: register()
    else: queue()

