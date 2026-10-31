"""Audit the amended E5b boundary campaign; never replace failed measurements."""
import json
from collections import Counter, defaultdict
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, check, read, sha
from experiments.reviewer_v2.E5_scale_kv.run_e5b import HERE, layout

BASE = HERE / 'E5b'
DIAG = BASE / 'formal_boundary_diagnostic'


def classify(entry, data):
    if entry['status'] == 'completed':
        return 'success'
    code = entry.get('exit_code')
    if code == 3221225477:
        return 'windows_access_violation'
    if code == 3221226505:
        return 'windows_stack_buffer_overrun'
    error = data.get('error', data.get('classification', 'unknown'))
    if 'profile_boundary_exceeded' in error:
        return 'profile_boundary_exceeded'
    if 'Exceed KV-cache capacity' in error:
        return 'kv_capacity_assertion'
    if 'No next level node meets scheduling requirement' in error:
        return 'no_eligible_downstream_node'
    if code == 1:
        return 'python_or_simulator_exception'
    return 'other_abnormal_exit'


def main():
    manifest_path = DIAG / 'manifest.json'
    index_path = DIAG / 'index.json'
    manifest, index = read(manifest_path), read(index_path)
    check(manifest)
    if manifest['environment']['conda_default_env'] != 'gllm':
        raise RuntimeError('Campaign did not record activated gllm')
    if index['status'] != 'terminal' or index['manifest_sha256'] != sha(manifest_path):
        raise RuntimeError('Campaign not terminal or manifest mismatch')
    jobs = manifest['jobs']
    if len(jobs) != 80 or set(index['jobs']) != {j['key'] for j in jobs}:
        raise RuntimeError('80-window job population mismatch')
    trace_groups, groups, rows = defaultdict(set), defaultdict(dict), []
    for job in jobs:
        key, entry = job['key'], index['jobs'][job['key']]
        if entry['status'] not in ('completed', 'failed'):
            raise RuntimeError('Nonterminal key: ' + key)
        artifact = ROOT / entry['source']
        if sha(artifact) != entry['artifact_sha256']:
            raise RuntimeError('Artifact SHA mismatch: ' + key)
        data = read(artifact)
        if data.get('job') != job:
            raise RuntimeError('Artifact job identity mismatch: ' + key)
        category = classify(entry, data)
        row = dict(key=key, family=job['family'], scenario=job['scenario'],
                   load=job['load'], method=job['method'], seed=job['seed'],
                   status=entry['status'], category=category,
                   error=data.get('error', data.get('classification')),
                   source=entry['source'], artifact_sha256=entry['artifact_sha256'])
        if entry['status'] == 'completed':
            solution, cluster, physical = layout(job['scenario'], job['method'])
            if (data.get('manifest_sha256') != sha(manifest_path) or
                data.get('solution_sha256') != sha(solution) or
                data.get('sim_cluster_sha256') != sha(cluster) or
                data.get('physical_sha256') != sha(physical) or
                data.get('capacity_scale') != job['capacity_scale'] or
                data.get('prompt_multiplier') != job['prompt_multiplier'] or
                len(data.get('query_samples', {})) != data.get('arrivals') or
                (job['family'] != 'half_kv' and data.get('trace_profile_bounds_checked') is not True)):
                raise RuntimeError('Completed window provenance mismatch: ' + key)
            trace_groups[(job['family'], job['scenario'], job['seed'])].add(data['trace_sha256'])
            groups[(job['family'], job['scenario'], job['method'])][job['seed']] = data
            row.update(trace_sha256=data['trace_sha256'], arrivals=data['arrivals'],
                       tpot_p95_s=data.get('tpot_p95_s'),
                       ttft_p95_s=data.get('ttft_p95_s'),
                       completion_fraction=data.get('completion_fraction'))
        rows.append(row)
    if any(len(hashes) > 1 for hashes in trace_groups.values()):
        raise RuntimeError('Successful methods have mismatched traces')
    audit = dict(passed=True, interpretation='Provenance pass only, not an experimental success claim',
        amended_boundary_diagnostic=True, registered=80,
        completed=sum(r['status'] == 'completed' for r in rows),
        failed=sum(r['status'] == 'failed' for r in rows),
        failure_categories=dict(Counter(r['category'] for r in rows if r['status'] == 'failed')),
        complete_five_seed_groups=sum(len(group) == 5 for group in groups.values()),
        group_counts={'/'.join(map(str, key)):len(group) for key, group in sorted(groups.items())},
        manifest_sha256=sha(manifest_path), index_sha256=sha(index_path), rows=rows)
    (DIAG / 'FINAL_AUDIT.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print({k:v for k,v in audit.items() if k not in ('rows','group_counts')})


if __name__ == '__main__':
    main()
