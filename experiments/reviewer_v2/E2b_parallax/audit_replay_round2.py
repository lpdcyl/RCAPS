"""Audit second-round E2b replay lineage without changing run artifacts."""
import json
from collections import Counter

from experiments.v5_core_supplement.run import ROOT, read, sha
from .run import HERE
from .failure_replay.audit import classify


def main():
    folders = [HERE / name for name in ('formal', 'failure_replay', 'failure_replay_round2')]
    manifests = [read(p / 'manifest.json') for p in folders]
    indexes = [read(p / 'index.json') for p in folders]
    for p, index in zip(folders, indexes):
        if index['status'] != 'terminal' or index['manifest_sha256'] != sha(p / 'manifest.json'):
            raise RuntimeError('Batch not terminal or manifest changed: ' + str(p))
    fm, f1, f2 = manifests
    i0, i1, i2 = indexes
    expected = {key for key, value in i1['jobs'].items() if value['status'] == 'failed'}
    if len(expected) != 6 or expected != set(i2['jobs']) or expected != {job['key'] for job in f2['jobs']}:
        raise RuntimeError('Second-round keys do not match unresolved first-round failures')
    for field, path in (('formal_manifest_sha256', folders[0] / 'manifest.json'),
                        ('formal_index_sha256', folders[0] / 'index.json'),
                        ('first_manifest_sha256', folders[1] / 'manifest.json'),
                        ('first_index_sha256', folders[1] / 'index.json')):
        if f2[field] != sha(path):
            raise RuntimeError('Upstream hash mismatch: ' + field)
    jobs0 = {job['key']: job for job in fm['jobs']}
    jobs1 = {job['key']: job for job in f1['jobs']}
    rows = []
    for job in f2['jobs']:
        key = job['key']
        if jobs0[key] != job or jobs1[key] != job:
            raise RuntimeError('Job mismatch: ' + key)
        old, first, last = (index['jobs'][key] for index in indexes)
        if old['status'] != 'failed' or first['status'] != 'failed' or last['status'] not in ('failed', 'completed'):
            raise RuntimeError('Unexpected job status: ' + key)
        for recorded, entry in zip(f2['sources'][key], (old, first)):
            if recorded != {'source': entry['source'], 'sha256': entry['artifact_sha256']}:
                raise RuntimeError('Lineage mismatch: ' + key)
        for entry in (old, first, last):
            if sha(ROOT / entry['source']) != entry['artifact_sha256']:
                raise RuntimeError('Artifact hash mismatch: ' + key)
            if read(ROOT / entry['source']).get('job') != job:
                raise RuntimeError('Artifact job mismatch: ' + key)
        data = read(ROOT / last['source'])
        if last['status'] == 'completed' and (data.get('origin') != 'second_independent_failure_replay' or
                data.get('source_formal_manifest_sha256') != f2['formal_manifest_sha256'] or
                len(data.get('query_samples', [])) != data.get('arrivals')):
            raise RuntimeError('Replay result provenance mismatch: ' + key)
        rows.append(dict(key=key, status=last['status'], category=classify(last, data),
                         error=data.get('error', data.get('classification')),
                         original_sha256=old['artifact_sha256'], first_sha256=first['artifact_sha256'],
                         second_sha256=last['artifact_sha256']))
    audit = dict(passed=True, registered=len(rows),
                 completed=sum(row['status'] == 'completed' for row in rows),
                 failed=sum(row['status'] == 'failed' for row in rows),
                 categories=dict(Counter(row['category'] for row in rows)),
                 formal_index_sha256=sha(folders[0] / 'index.json'),
                 first_index_sha256=sha(folders[1] / 'index.json'),
                 second_index_sha256=sha(folders[2] / 'index.json'),
                 interpretation='Lineage audit only; replays do not replace original results', rows=rows)
    (folders[2] / 'FINAL_AUDIT.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print({key: value for key, value in audit.items() if key != 'rows'})


if __name__ == '__main__':
    main()
