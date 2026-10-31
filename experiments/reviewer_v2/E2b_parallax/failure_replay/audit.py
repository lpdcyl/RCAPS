"""Verify every independent E2b replay against its preserved original failure."""
import json
from collections import Counter
from pathlib import Path

from experiments.v5_core_supplement.run import ROOT, read, sha
from experiments.reviewer_v2.E2b_parallax.run import HERE, check


def classify(entry, data):
    if entry['status'] == 'completed':
        return 'success'
    error = str(data.get('error', ''))
    if 'KV-cache capacity' in error:
        return 'kv_capacity_assertion'
    if entry.get('exit_code') == 3221225477:
        return 'windows_native_access_violation'
    if data.get('classification') == 'controller_and_worker_interrupted_by_reboot':
        return 'reboot_interruption'
    if data.get('classification') in ('abnormal_exit', 'native_or_abnormal_exit'):
        return 'abnormal_exit'
    return 'python_exception'


def main():
    replay = HERE / 'failure_replay'
    original_manifest = read(HERE / 'formal/manifest.json')
    check(original_manifest)
    original_index = read(HERE / 'formal/index.json')
    manifest = read(replay / 'manifest.json')
    index = read(replay / 'index.json')
    if original_index['status'] != 'terminal' or index['status'] != 'terminal':
        raise RuntimeError('Both batches must be terminal')
    if manifest['source_index_sha256'] != sha(HERE / 'formal/index.json'):
        raise RuntimeError('Original index changed')
    if manifest['source_manifest_sha256'] != sha(HERE / 'formal/manifest.json'):
        raise RuntimeError('Original manifest changed')
    if index['manifest_sha256'] != sha(replay / 'manifest.json'):
        raise RuntimeError('Replay manifest changed')
    failed = {key for key, entry in original_index['jobs'].items() if entry['status'] == 'failed'}
    if failed != set(index['jobs']) or failed != {job['key'] for job in manifest['jobs']}:
        raise RuntimeError('Replay must cover exactly the original failed keys')
    rows = []
    for key in sorted(failed):
        job = next(j for j in manifest['jobs'] if j['key'] == key)
        before, after = original_index['jobs'][key], index['jobs'][key]
        recorded = manifest['original_failures'][key]
        if recorded['source'] != before['source'] or recorded['artifact_sha256'] != before['artifact_sha256']:
            raise RuntimeError('Original failure record changed: ' + key)
        for entry in (before, after):
            if sha(ROOT / entry['source']) != entry['artifact_sha256']:
                raise RuntimeError('Artifact hash mismatch: ' + key)
        if after['status'] not in ('completed', 'failed') or not after['source'].startswith('experiments/reviewer_v2/E2b_parallax/failure_replay/runs/'):
            raise RuntimeError('Invalid replay entry: ' + key)
        old, new = read(ROOT / before['source']), read(ROOT / after['source'])
        if old.get('job') != job or new.get('job') != job:
            raise RuntimeError('Job identity mismatch: ' + key)
        if after['status'] == 'completed':
            if new.get('source_formal_manifest_sha256') != manifest['source_manifest_sha256']:
                raise RuntimeError('Replay provenance missing: ' + key)
            if len(new.get('query_samples', [])) != new.get('arrivals'):
                raise RuntimeError('Replay samples incomplete: ' + key)
        rows.append(dict(key=key, original=classify(before, old), original_error=old.get('error'),
                         replay=classify(after, new), replay_error=new.get('error'),
                         original_source=before['source'], replay_source=after['source'],
                         original_sha256=before['artifact_sha256'], replay_sha256=after['artifact_sha256']))
    result = dict(passed=len(rows) == len(failed) == 11, original_failed=len(failed),
                  replay_completed=sum(row['replay'] == 'success' for row in rows),
                  replay_failed=sum(row['replay'] != 'success' for row in rows),
                  original_reasons=dict(Counter(row['original'] for row in rows)),
                  replay_reasons=dict(Counter(row['replay'] for row in rows)),
                  original_index_sha256=sha(HERE / 'formal/index.json'),
                  replay_index_sha256=sha(replay / 'index.json'), rows=rows)
    (replay / 'FINAL_AUDIT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if not result['passed']:
        raise RuntimeError('Replay coverage incomplete')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
