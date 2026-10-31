"""Verify independent E5b boundary failure replays and preserve both populations."""
import json
from collections import Counter, defaultdict

from experiments.v5_core_supplement.run import ROOT, check, read, sha
from experiments.reviewer_v2.E5_scale_kv.audit_e5b_boundary import classify
from experiments.reviewer_v2.E5_scale_kv.run_e5b import HERE, layout

ORIGINAL = HERE / 'E5b' / 'formal_boundary_diagnostic'
REPLAY = HERE / 'E5b' / 'boundary_failure_replay'


def main():
    original_manifest_path = ORIGINAL / 'manifest.json'
    original_index_path = ORIGINAL / 'index.json'
    replay_manifest_path = REPLAY / 'manifest.json'
    replay_index_path = REPLAY / 'index.json'
    original_manifest = read(original_manifest_path)
    original_index = read(original_index_path)
    replay_manifest = read(replay_manifest_path)
    replay_index = read(replay_index_path)
    check(original_manifest)
    if original_index['status'] != 'terminal' or replay_index['status'] != 'terminal':
        raise RuntimeError('Both batches must be terminal')
    if original_index['manifest_sha256'] != sha(original_manifest_path):
        raise RuntimeError('Original manifest mismatch')
    if replay_index['manifest_sha256'] != sha(replay_manifest_path):
        raise RuntimeError('Replay manifest mismatch')
    if (replay_manifest['original_manifest_sha256'] != sha(original_manifest_path) or
        replay_manifest['original_index_sha256'] != sha(original_index_path) or
        replay_manifest['original_audit_sha256'] != sha(ORIGINAL / 'FINAL_AUDIT.json')):
        raise RuntimeError('Replay source lineage mismatch')
    if replay_manifest['environment']['conda_default_env'] != 'gllm':
        raise RuntimeError('Replay did not record activated gllm')
    jobs = replay_manifest['jobs']
    original_jobs = {job['key']: job for job in original_manifest['jobs']}
    expected = {key for key, entry in original_index['jobs'].items()
                if entry['status'] == 'failed'}
    if len(jobs) != 59 or set(replay_index['jobs']) != expected or {j['key'] for j in jobs} != expected:
        raise RuntimeError('Replay population must equal all 59 original failures')
    rows, trace_groups = [], defaultdict(set)
    for job in jobs:
        key = job['key']
        if original_jobs.get(key) != job:
            raise RuntimeError('Job identity mismatch: ' + key)
        old = original_index['jobs'][key]
        new = replay_index['jobs'][key]
        lineage = replay_manifest['original_failures'][key]
        if (old['status'] != 'failed' or new['status'] not in ('failed', 'completed') or
            lineage != {'source': old['source'], 'sha256': old['artifact_sha256']}):
            raise RuntimeError('Artifact lineage mismatch: ' + key)
        for entry in (old, new):
            if sha(ROOT / entry['source']) != entry['artifact_sha256']:
                raise RuntimeError('Artifact SHA mismatch: ' + key)
        source = read(ROOT / old['source'])
        data = read(ROOT / new['source'])
        if source.get('job') != job or data.get('job') != job:
            raise RuntimeError('Artifact job mismatch: ' + key)
        row = dict(key=key, family=job['family'], scenario=job['scenario'],
                   method=job['method'], seed=job['seed'],
                   original_status='failed', original_category=classify(old, source),
                   original_error=source.get('error', source.get('classification')),
                   original_source=old['source'], original_sha256=old['artifact_sha256'],
                   replay_status=new['status'], replay_category=classify(new, data),
                   replay_error=data.get('error', data.get('classification')),
                   replay_source=new['source'], replay_sha256=new['artifact_sha256'])
        if new['status'] == 'completed':
            solution, cluster, physical = layout(job['scenario'], job['method'])
            if (data.get('origin') != 'independent_boundary_failure_replay' or
                data.get('source_manifest_sha256') != replay_manifest['original_manifest_sha256'] or
                data.get('solution_sha256') != sha(solution) or
                data.get('sim_cluster_sha256') != sha(cluster) or
                data.get('physical_sha256') != sha(physical) or
                data.get('capacity_scale') != job['capacity_scale'] or
                data.get('prompt_multiplier') != job['prompt_multiplier'] or
                len(data.get('query_samples', {})) != data.get('arrivals') or
                (job['family'] != 'half_kv' and data.get('trace_profile_bounds_checked') is not True)):
                raise RuntimeError('Completed replay provenance mismatch: ' + key)
            row.update(arrivals=data['arrivals'], trace_sha256=data['trace_sha256'])
            trace_groups[(job['family'], job['scenario'], job['seed'])].add(data['trace_sha256'])
        rows.append(row)
    if any(len(hashes) > 1 for hashes in trace_groups.values()):
        raise RuntimeError('Replay successful methods have mismatched traces')
    audit = dict(passed=True, interpretation='Provenance pass only; replays do not replace original failures',
                 original_registered=len(original_manifest['jobs']),
                 original_completed=sum(e['status'] == 'completed' for e in original_index['jobs'].values()),
                 original_failed=len(jobs), replay_registered=len(jobs),
                 replay_completed=sum(r['replay_status'] == 'completed' for r in rows),
                 replay_failed=sum(r['replay_status'] == 'failed' for r in rows),
                 original_failure_categories=dict(Counter(r['original_category'] for r in rows)),
                 replay_categories=dict(Counter(r['replay_category'] for r in rows)),
                 original_manifest_sha256=sha(original_manifest_path),
                 original_index_sha256=sha(original_index_path),
                 replay_manifest_sha256=sha(replay_manifest_path),
                 replay_index_sha256=sha(replay_index_path), rows=rows)
    (REPLAY / 'FINAL_AUDIT.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print({key: value for key, value in audit.items() if key != 'rows'})


if __name__ == '__main__':
    main()
