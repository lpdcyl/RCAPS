"""Audit E5a original batch and report only complete five-seed groups."""
import csv
import json
import math
from collections import Counter, defaultdict
from statistics import mean, stdev

from experiments.v5_core_supplement.run import ROOT, read, sha, check
from .run import HERE, METHODS, LOADS, paths, PHYSICAL, PROFILE

METRICS = ('tpot_p95_s', 'ttft_p95_s', 'output_throughput_tokens_per_s',
           'completion_fraction', 'gpu_seconds_per_output_token')
T4 = 2.7764451051977987


def main():
    manifest_path = HERE / 'formal/manifest.json'
    index_path = HERE / 'formal/index.json'
    manifest, index = read(manifest_path), read(index_path)
    check(manifest)
    if index['status'] != 'terminal' or index['manifest_sha256'] != sha(manifest_path):
        raise RuntimeError('E5a batch not terminal or manifest mismatch')
    if len(manifest['jobs']) != 60 or set(index['jobs']) != {j['key'] for j in manifest['jobs']}:
        raise RuntimeError('E5a job keys mismatch')
    groups, traces = defaultdict(dict), defaultdict(set)
    rows, reasons, failed = [], Counter(), []
    for job in manifest['jobs']:
        key, entry = job['key'], index['jobs'][job['key']]
        if entry['status'] not in ('completed', 'failed'):
            raise RuntimeError('Nonterminal E5a entry: ' + key)
        artifact = ROOT / entry['source']
        if sha(artifact) != entry['artifact_sha256']:
            raise RuntimeError('Artifact hash mismatch: ' + key)
        data = read(artifact)
        if data.get('job') != job:
            raise RuntimeError('Job identity mismatch: ' + key)
        row = dict(load=job['load'], method=job['method'], seed=job['seed'],
                   status=entry['status'], source=entry['source'],
                   artifact_sha256=entry['artifact_sha256'], error='')
        if entry['status'] == 'failed':
            row['error'] = data.get('error', data.get('classification', 'unknown'))
            reasons[row['error']] += 1
            failed.append(entry['source'])
        else:
            solution, cluster = paths(job['method'])
            if (data['solution_sha256'] != sha(solution) or
                    data['sim_cluster_sha256'] != sha(cluster) or
                    data['physical_sha256'] != sha(PHYSICAL) or
                    data['machine_profile_sha256'] != sha(PROFILE) or
                    data['manifest_sha256'] != sha(manifest_path) or
                    len(data['query_samples']) != data['arrivals']):
                raise RuntimeError('E5a provenance mismatch: ' + key)
            throughput = data['output_throughput_tokens_per_s']
            if throughput <= 0 or not math.isclose(
                    sum(data['gpu_busy_fraction'].values()) / throughput,
                    data['gpu_seconds_per_output_token'], rel_tol=1e-10):
                raise RuntimeError('E5a GPU work mismatch: ' + key)
            traces[(job['load'], job['seed'])].add(data['trace_sha256'])
            groups[(job['load'], job['method'])][job['seed']] = data
            op = '_route' if job['method'].startswith('RCAPS') else 'schedule_transmission'
            profile = data.get('scheduler_call_profile', {}).get(op, {})
            row.update(trace_sha256=data['trace_sha256'],
                       deployed_compute_nodes=data['deployed_compute_nodes'],
                       physical_gpu_count=data['physical_gpu_count'],
                       planning_wall_s=data['planning_wall_s'],
                       route_mean_us=profile.get('mean_us'),
                       route_p95_us=profile.get('p95_us'),
                       **{metric: data[metric] for metric in METRICS})
        rows.append(row)
    if any(len(hashes) > 1 for hashes in traces.values()):
        raise RuntimeError('E5a matched trace mismatch')
    fields = ('load', 'method', 'seed', 'status', 'source', 'artifact_sha256',
              'error', 'trace_sha256', 'deployed_compute_nodes', 'physical_gpu_count',
              'planning_wall_s', 'route_mean_us', 'route_p95_us', *METRICS)
    with (HERE / 'E5a_individual.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    lines = ['# E5a 42 节点规模实验', '',
             '70B CPU 画像仿真；42 个计算节点，按设备配置共 64 张物理 GPU。',
             'RCAPS V4 运行机制及 KV 准入变体使用历史 V3 的 42 节点放置，未重新搜索 V4 放置。',
             '旧 V3 在 2150 token/s 的原失败原件缺失，不能从二手报告判断异常原因。',
             '仅五种子完整组报告均值和配对 t(4) 95% CI；失败不填零。', '',
             '| 负载 | 方法 | 成功 | P95 TPOT s | P95 TTFT s | 吞吐 token/s | 完成率 | GPU s/token | 路由均值/P95 μs | 相对 Helix TPOT |',
             '|---:|---|---:|---:|---:|---:|---:|---:|---|---|']
    complete = 0
    for load in LOADS:
        for method in METHODS:
            group = groups[(load, method)]
            if len(group) != 5:
                lines.append(f'| {load} | {method} | {len(group)}/5 | — | — | — | — | — | — | — |')
                continue
            complete += 1
            avg = {m: mean(group[s][m] for s in range(5)) for m in METRICS}
            op = '_route' if method.startswith('RCAPS') else 'schedule_transmission'
            profile = [group[s].get('scheduler_call_profile', {}).get(op, {}) for s in range(5)]
            route = (f"{mean(p['mean_us'] for p in profile):.1f}/{mean(p['p95_us'] for p in profile):.1f}"
                     if all(p.get('mean_us') is not None and p.get('p95_us') is not None for p in profile) else '—')
            baseline = groups[(load, 'Helix')]
            if method == 'Helix':
                delta = '基线'
            elif len(baseline) == 5:
                changes = [100 * (group[s]['tpot_p95_s'] / baseline[s]['tpot_p95_s'] - 1) for s in range(5)]
                delta = f'{mean(changes):+.2f}% ± {T4 * stdev(changes) / math.sqrt(5):.2f}pp'
            else:
                delta = '—'
            lines.append(f"| {load} | {method} | 5/5 | {avg['tpot_p95_s']:.4f} | {avg['ttft_p95_s']:.4f} | {avg['output_throughput_tokens_per_s']:.2f} | {avg['completion_fraction']:.3f} | {avg['gpu_seconds_per_output_token']:.4f} | {route} | {delta} |")
    lines += ['', '规划墙钟只在 RCAPS 历史 V3 放置元数据中记录；Helix 工件缺少同口径规划时间。',
              '独立重放将另列，不能替代本表正式窗口。']
    (HERE / 'E5a_RESULTS_CN.md').write_text(chr(10).join(lines) + chr(10), encoding='utf-8')
    audit = dict(passed=True, registered=60,
                 completed=sum(e['status'] == 'completed' for e in index['jobs'].values()),
                 original_failed=len(failed), complete_five_seed_groups=complete,
                 original_failure_reasons=dict(reasons), original_failure_artifacts=failed,
                 original_index_sha256=sha(index_path), manifest_sha256=sha(manifest_path),
                 individual_sha256=sha(HERE / 'E5a_individual.csv'),
                 results_sha256=sha(HERE / 'E5a_RESULTS_CN.md'))
    (HERE / 'E5a_FINAL_AUDIT.json').write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    print({key: value for key, value in audit.items() if key != 'original_failure_artifacts'})


if __name__ == '__main__':
    main()
