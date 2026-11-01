"""Audit the new independent retries only after every registered key is terminal."""
import json
from collections import Counter, defaultdict
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, read, sha
from experiments.reviewer_v2.auto_retry_remaining import BATCH, INDEX, MANIFEST
from experiments.reviewer_v2.manual_rerun import verify_registry


def classify(state, artifact):
    if state['status'] == 'completed':
        return 'success'
    # The controller records manual_rerun's wrapper exit (usually 1).  The
    # child artifact/index records the native worker exit, when available.
    code = artifact.get('exit_code', state.get('exit_code'))
    error = str(artifact.get('error', artifact.get('classification', '')))
    if 'profile_boundary' in error or 'outside profile range' in error:
        return 'profile_boundary'
    if 'No next level node meets scheduling requirement' in error:
        return 'no_eligible_downstream_node'
    if 'Exceed KV-cache capacity' in error or 'KV-cache capacity' in error:
        return 'kv_capacity_assertion'
    if code == 3221225477:
        return 'windows_access_violation'
    if code == 3221226356:
        return 'windows_heap_corruption'
    if code == 3221226505:
        return 'windows_stack_buffer_overrun'
    if code == 1:
        return 'python_or_simulator_exception'
    return 'other_abnormal_exit'


def main():
    manifest, index = read(MANIFEST), read(INDEX)
    if index['status'] != 'terminal' or index['manifest_sha256'] != sha(MANIFEST):
        raise RuntimeError('Retry campaign not terminal or manifest changed')
    if len(manifest['jobs']) != 254 or len(index['jobs']) != 254:
        raise RuntimeError('Expected 254 registered keys')
    rows, groups = [], defaultdict(Counter)
    for job in manifest['jobs']:
        group, key = job['group'], job['key']
        token = f'{group}::{key}'
        state = index['jobs'][token]
        if state['status'] not in ('completed', 'failed'):
            raise RuntimeError('Nonterminal key: ' + token)
        original_job, source_manifest, original, previous = verify_registry(group, key)
        if (original_job != job['job'] or sha(source_manifest) != job['source_manifest_sha256'] or
            original['artifact_sha256'] != job['original_failure_sha256'] or
            previous['artifact_sha256'] != job['last_failure_sha256']):
            raise RuntimeError('Source lineage changed: ' + token)
        folder = BATCH / 'runs' / group / key
        child = folder / 'index.json'
        if child.exists():
            if sha(child) != state['child_index_sha256']:
                raise RuntimeError('Child index hash changed: ' + token)
            outcome = read(child)
            if (outcome['group'] != group or outcome['key'] != key or
                outcome['status'] != state['status'] or
                outcome['original_sha256'] != original['artifact_sha256'] or
                outcome['replay_sha256'] != previous['artifact_sha256']):
                raise RuntimeError('Child index mismatch: ' + token)
            artifact_path = folder / outcome['artifact']
            if sha(artifact_path) != outcome['artifact_sha256']:
                raise RuntimeError('Child artifact SHA changed: ' + token)
            artifact = read(artifact_path)
            if artifact.get('job') != original_job:
                raise RuntimeError('Result job mismatch: ' + token)
            if state['status'] == 'completed':
                if (outcome['artifact'] != 'result.json' or
                    artifact.get('origin') != 'user_manual_independent_rerun' or
                    ('query_samples' in artifact and len(artifact['query_samples']) != artifact.get('arrivals'))):
                    raise RuntimeError('Completed result invalid: ' + token)
            elif outcome['artifact'] != 'failure.json':
                raise RuntimeError('Failed artifact name invalid: ' + token)
            artifact_source = artifact_path.relative_to(ROOT).as_posix()
            artifact_sha = outcome['artifact_sha256']
        else:
            name = 'interrupted.json' if state.get('interruption_sha256') else 'controller_failure.json'
            artifact_path = folder / name
            artifact_sha = state.get('interruption_sha256', state.get('controller_failure_sha256'))
            if state['status'] != 'failed' or not artifact_sha or sha(artifact_path) != artifact_sha:
                raise RuntimeError('Controller failure artifact invalid: ' + token)
            artifact = read(artifact_path)
            artifact_source = artifact_path.relative_to(ROOT).as_posix()
        category = classify(state, artifact)
        groups[group][state['status']] += 1
        groups[group][category] += 1
        rows.append({'group': group, 'key': key, 'status': state['status'], 'category': category,
                     'error': artifact.get('error', artifact.get('classification')),
                     'artifact': artifact_source, 'artifact_sha256': artifact_sha,
                     'original_failure_sha256': original['artifact_sha256'],
                     'previous_replay_sha256': previous['artifact_sha256']})
    summary = {'passed': True, 'interpretation': 'Independent retry outcomes only; original formal results unchanged',
               'registered': len(rows), 'completed': sum(x['status'] == 'completed' for x in rows),
               'failed': sum(x['status'] == 'failed' for x in rows),
               'groups': {k: dict(v) for k, v in groups.items()},
               'manifest_sha256': sha(MANIFEST), 'index_sha256': sha(INDEX), 'rows': rows}
    (BATCH / 'FINAL_AUDIT.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
