"""Public simulator mapping of Parallax's capacity DP and water filling."""
from functools import lru_cache
from pathlib import Path
import json

from benchmarks.layout import scenario
from rcaps.v3.topology import TopologyModel, profile_at
from rcaps.v3.resource_graph import from_topology, layer_dag
from experiments.reviewer_v2.E1_placement.placement_multi import digest

HERE = Path(__file__).resolve().parent


def choose_pipeline(model):
    resources = from_topology(model)
    nodes = sorted(model.types, key=lambda n: (-model.capacity[n], n))
    caps = [model.capacity[n] for n in nodes]
    suffix = [0] * (len(nodes) + 1)
    for i in range(len(nodes) - 1, -1, -1):
        suffix[i] = suffix[i + 1] + caps[i]
    max_k = suffix[0] // model.layers
    candidates = []
    for k in range(1, max_k + 1):
        actions = {}

        @lru_cache(None)
        def dp(i, remaining, finished):
            if finished == k and remaining == 0:
                return 0
            if i == len(nodes) or suffix[i] < remaining + max(0, k-finished-1)*model.layers:
                return float('inf')
            skip = dp(i+1, remaining, finished)
            take = float('inf')
            if finished < k:
                if remaining == 0:
                    if ('source', nodes[i]) in resources.links:
                        rest = model.layers - caps[i]
                        take = 1 + dp(i+1, max(0, rest), finished + int(rest <= 0))
                elif (nodes[i], 'sink') in resources.links:
                    rest = remaining - caps[i]
                    take = 1 + dp(i+1, max(0, rest), finished + int(rest <= 0))
            actions[(i, remaining, finished)] = take < skip
            return min(skip, take)

        stages = dp(0, 0, 0)
        if stages == float('inf'):
            continue
        candidates.append((k*k/stages, k, stages, actions, dp.cache_info().currsize))
    if not candidates:
        raise ValueError('No capacity-feasible complete pipeline')
    score, k, stages, actions, states = max(candidates, key=lambda x: x[0])
    i = remaining = finished = 0
    pipes = [[] for _ in range(k)]
    while finished < k:
        if actions.get((i, remaining, finished), False):
            pipes[finished].append(nodes[i])
            remaining = max(0, (model.layers if remaining == 0 else remaining)-caps[i])
            if remaining == 0:
                finished += 1
        i += 1
        if i > len(nodes):
            raise AssertionError('DP backtracking incomplete')
    for pipe in pipes:
        if any((a,b) not in resources.links for a,b in zip(pipe, pipe[1:])):
            raise ValueError('DP capacity path has no physical link')
    return pipes, dict(k=k, stages=stages, score=score, dp_states=states,
                       max_k_capacity=max_k)


def water_fill(model, pipe):
    caps = [model.capacity[n] for n in pipe]
    powers = [1/profile_at(model.profiles[model.types[n]].decode_bs2time, 8) for n in pipe]
    lo, hi = 0, max(c/p for c,p in zip(caps,powers))
    for _ in range(40):
        mid = (lo+hi)/2
        if sum(min(c,mid*p) for c,p in zip(caps,powers)) >= model.layers: hi = mid
        else: lo = mid
    targets = [min(c,hi*p) for c,p in zip(caps,powers)]
    counts = [int(t) for t in targets]
    missing = model.layers-sum(counts)
    for i in sorted(range(len(pipe)), key=lambda i: (-(targets[i]-counts[i]),i)):
        if missing and counts[i]<caps[i]: counts[i]+=1; missing-=1
    if missing or min(counts)<1:
        raise ValueError('Water filling did not produce positive full coverage')
    return counts, powers


def build(name):
    from configparser import ConfigParser
    physical, _, _, template = scenario(name)
    model = TopologyModel(physical)
    pipes, choice = choose_pipeline(model)
    spans, power_map = {}, {}
    for pipe in pipes:
        counts, powers = water_fill(model, pipe)
        start = 0
        for node, count, power in zip(pipe,counts,powers):
            spans[node] = (start,start+count)
            power_map[node] = power
            start += count
        assert start == model.layers
    resources = from_topology(model)
    dag = layer_dag(resources,spans,tuple(pipe[0] for pipe in pipes))
    if dag.path_count()<len(pipes): raise ValueError('Incomplete DAG')
    for node,(start,end) in spans.items():
        if end-start>model.capacity[node] or model.manager.get_kv_cache_capacity(model.types[node],end-start)<=0:
            raise ValueError('Capacity or KV violation')
    out = HERE/'layouts'/name
    out.mkdir(parents=True,exist_ok=True)
    sol = ConfigParser()
    sol['Settings']={'offset':'2'}
    sol['Solution']={f'compute_node_{n+2}':repr(list(range(*span))) for n,span in sorted(spans.items())}
    solution=out/'solution.ini'
    with solution.open('w',encoding='utf-8') as stream: sol.write(stream)
    cluster=ConfigParser()
    if not cluster.read(template): raise FileNotFoundError(template)
    for n,(start,end) in spans.items():
        cluster[f'compute_node_{n+2}']['kv_cache_capacity']=str(model.manager.get_kv_cache_capacity(model.types[n],end-start))
    for section in list(cluster.sections()):
        if section.startswith('link_'): cluster.remove_section(section)
    names=[]
    for a,b in dag.edges:
        left=a if a=='source' else f'compute_node_{a+2}'
        right=b if b=='sink' else f'compute_node_{b+2}'
        section=f'link_{left}_{right}'
        link=f'Link-{a}-{b}'
        if link not in model.config: link=f'Link-{b}-{a}'
        cluster[section]={'in':left,'out':right,'latency':model.config[link]['latency'],'bandwidth':model.config[link]['bandwidth']}
        names.append(section)
    cluster['Links']['names']=repr(names)
    deployed=out/'simulator_cluster.ini'
    with deployed.open('w',encoding='utf-8') as stream: cluster.write(stream)
    record={'source_commit':'162354a03234a28cf6e2946e2e0b2203da7c3721',
            'choice':choice,'pipelines':pipes,'spans':{str(n):list(s) for n,s in spans.items()},
            'compute_power':{str(n):p for n,p in power_map.items()},'compatible_paths':dag.path_count(),
            'physical_sha256':digest(physical),'template_sha256':digest(template),
            'solution_sha256':digest(solution),'cluster_sha256':digest(deployed)}
    (out/'placement.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    return record
