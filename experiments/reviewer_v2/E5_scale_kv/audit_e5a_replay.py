"""Verify the independent E5a failure replay without rewriting formal data."""
import json
from collections import Counter

from experiments.v5_core_supplement.run import ROOT, read, sha, check
from .run import HERE, paths, PHYSICAL, PROFILE

FORMAL = HERE / 'formal'
REPLAY = HERE / 'E5a_failure_replay'


def category(entry, data):
    if entry['status'] == 'completed':
        return 'success'
    code = entry.get('exit_code')
    if code == 3221225477:
        return 'windows_access_violation'
    if code == 3221226356:
        return 'windows_heap_corruption'
    error = data.get('error', data.get('classification', 'unknown'))
    if 'Exceed KV-cache capacity' in error:
        return 'kv_capacity_assertion'
    if code == 1:
        return 'python_exception'
    return 'other_abnormal_exit'


def main():
    original_manifest = read(FORMAL / 'manifest.json')
    original_index = read(FORMAL / 'index.json')
    replay_manifest = read(REPLAY / 'manifest.json')
    replay_index = read(REPLAY / 'index.json')
    check(original_manifest)
    if original_index['status'] != 'terminal' or replay_index['status'] != 'terminal':
        raise RuntimeError('Both campaigns must be terminal')
    if original_index['manifest_sha256'] != sha(FORMAL / 'manifest.json'):
        raise RuntimeError('Original manifest mismatch')
    if replay_index['manifest_sha256'] != sha(REPLAY / 'manifest.json'):
        raise RuntimeError('Replay manifest mismatch')
    if replay_manifest['source_manifest_sha256'] != sha(FORMAL / 'manifest.json'):
        raise RuntimeError('Replay source manifest mismatch')
    if replay_manifest['source_index_sha256'] != sha(FORMAL / 'index.json'):
        raise RuntimeError('Original index changed since replay registration')
    jobs = replay_manifest['jobs']
    if len(jobs) != 56 or set(replay_index['jobs']) != {job['key'] for job in jobs}:
        raise RuntimeError('Replay key population mismatch')
    original_jobs = {job['key']: job for job in original_manifest['jobs']}
    rows = []
    for job in jobs:
        key = job['key']
        if original_jobs.get(key) != job:
            raise RuntimeError('Original job identity mismatch: ' + key)
        old = original_index['jobs'][key]
        new = replay_index['jobs'][key]
        if old['status'] != 'failed' or new['status'] not in ('failed', 'completed'):
            raise RuntimeError('Unexpected status: ' + key)
        lineage = replay_manifest['original_failures'][key]
        if lineage != {'source': old['source'], 'artifact_sha256': old['artifact_sha256']}:
            raise RuntimeError('Failure lineage mismatch: ' + key)
        for record in (old, new):
            if sha(ROOT / record['source']) != record['artifact_sha256']:
                raise RuntimeError('Artifact SHA mismatch: ' + key)
        source = read(ROOT / old['source'])
        data = read(ROOT / new['source'])
        if source.get('job') != job or data.get('job') != job:
            raise RuntimeError('Artifact job mismatch: ' + key)
        if new['status'] == 'completed':
            solution, cluster = paths(job['method'])
            if (data.get('origin') != 'independent_failure_replay' or
                data.get('source_formal_manifest_sha256') != replay_manifest['source_manifest_sha256'] or
                data.get('solution_sha256') != sha(solution) or
                data.get('sim_cluster_sha256') != sha(cluster) or
                data.get('physical_sha256') != sha(PHYSICAL) or
                data.get('machine_profile_sha256') != sha(PROFILE) or
                len(data.get('query_samples', [])) != data.get('arrivals')):
                raise RuntimeError('Replay provenance or sample mismatch: ' + key)
        rows.append(dict(key=key, original_status=old['status'],
            original_error=source.get('error', source.get('classification')),
            original_sha256=old['artifact_sha256'],
            replay_status=new['status'], replay_category=category(new, data),
            replay_error=data.get('error', data.get('classification')),
            replay_sha256=new['artifact_sha256'],
            replay_arrivals=data.get('arrivals') if new['status'] == 'completed' else None,
            replay_trace_sha256=data.get('trace_sha256') if new['status'] == 'completed' else None))
    summary = dict(passed=True, registered=len(jobs),
        original_formal_completed=sum(x['status'] == 'completed' for x in original_index['jobs'].values()),
        original_formal_failed=sum(x['status'] == 'failed' for x in original_index['jobs'].values()),
        replay_completed=sum(row['replay_status'] == 'completed' for row in rows),
        replay_failed=sum(row['replay_status'] == 'failed' for row in rows),
        replay_categories=dict(Counter(row['replay_category'] for row in rows)),
        formal_manifest_sha256=sha(FORMAL / 'manifest.json'),
        formal_index_sha256=sha(FORMAL / 'index.json'),
        replay_manifest_sha256=sha(REPLAY / 'manifest.json'),
        replay_index_sha256=sha(REPLAY / 'index.json'), rows=rows,
        interpretation='Provenance audit only. Replays do not replace original formal failures.')
    (REPLAY / 'FINAL_AUDIT.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print({key: value for key, value in summary.items() if key != 'rows'})


if __name__ == '__main__':
    main()
