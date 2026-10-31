"""Independently replay E5a smoke failures; never alter original artifacts."""
import json
import os
import sys
import time
import traceback
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, read, write, sha, relative, now, check
from .run import HERE, evaluate


def main():
    original = read(HERE / 'smoke/index.json')
    manifest = read(HERE / 'smoke/manifest.json')
    check(manifest)
    if original['status'] != 'terminal':
        raise RuntimeError('Smoke batch not terminal')
    jobs = [j for j in manifest['jobs'] if original['jobs'][j['key']]['status'] == 'failed']
    if not jobs:
        raise RuntimeError('No failures to replay')
    folder = HERE / 'smoke_retry'
    folder.mkdir(exist_ok=True)
    if (folder / 'index.json').exists():
        raise RuntimeError('Replay already exists')
    replay_manifest = dict(registered_at=now(), original_manifest_sha256=sha(HERE / 'smoke/manifest.json'),
                           original_index_sha256=sha(HERE / 'smoke/index.json'), jobs=jobs,
                           runner_sha256=sha(Path(__file__)), policy='Independent replay; no original overwrite')
    write(folder / 'manifest.json', replay_manifest)
    entries = {}
    for job in jobs:
        key = job['key']
        original_entry = original['jobs'][key]
        if sha(ROOT / original_entry['source']) != original_entry['artifact_sha256']:
            raise RuntimeError('Original artifact changed: '+key)
        dest = folder / 'runs' / key
        dest.mkdir(parents=True, exist_ok=False)
        start = time.perf_counter()
        try:
            row = evaluate(job)
            check(manifest)
            if len(row['query_samples']) != row['arrivals']:
                raise RuntimeError('Query samples incomplete')
            row.update(status='completed', job=job, original_failure_source=original_entry['source'],
                       original_failure_sha256=original_entry['artifact_sha256'],
                       source_manifest_sha256=sha(HERE/'smoke/manifest.json'),
                       elapsed_wall_s=time.perf_counter()-start, finished_at=now())
            artifact = dest / 'result.json'
            write(artifact, row)
            status='completed'
        except BaseException as exc:
            artifact = dest / 'failure.json'
            write(artifact, dict(status='failed', job=job, error=repr(exc), traceback=traceback.format_exc(),
                 elapsed_wall_s=time.perf_counter()-start, finished_at=now()))
            status='failed'
        entries[key] = dict(status=status, source=relative(artifact), artifact_sha256=sha(artifact),
                            original_failure_source=original_entry['source'],
                            original_failure_sha256=original_entry['artifact_sha256'])
    write(folder / 'index.json', dict(status='terminal', manifest_sha256=sha(folder/'manifest.json'), jobs=entries))
    print(json.dumps({k:v['status'] for k,v in entries.items()}))


if __name__ == '__main__':
    main()
