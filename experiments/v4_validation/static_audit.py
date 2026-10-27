"""M1 legality evidence, real-placement controls, and environment feasibility."""
from __future__ import annotations
import ast
from configparser import ConfigParser
from copy import deepcopy
from pathlib import Path
import subprocess
from unittest.mock import patch

from experiments.v4_formal.run import ROOT,inputs,read,write,digest,stamp,capture
from rcaps.v3.topology import TopologyModel
from rcaps.v3.placement import validate as validate_placement
from rcaps.v3.resource_graph import from_topology,LayerCompatibilityDag
from rcaps.v4.admission import canonical_edges,admitted_edges

HERE=Path(__file__).resolve().parent


def rejection(function):
    try:
        function()
    except ValueError as e:
        return dict(passed=True,error=str(e))
    return dict(passed=False,error='Invalid input unexpectedly accepted')


def main():
    results=[]
    for scenario,cell in [('single','v4'),('multi','v4'),('C2','v4'),('C3','v4'),
                          ('single','single_boundary'),('multi','single_boundary')]:
        job=dict(scenario=scenario,cell=cell)
        physical,layout=inputs(job)
        record=dict(scenario=scenario,cell=cell,physical=str(physical.relative_to(ROOT)),
                    layout=str(layout.relative_to(ROOT)))
        try:
            obj=read(layout/'placement.json'); state=obj['state']; model=TopologyModel(physical)
            checked=validate_placement(model,state); dag=checked['dag']
            for a,b in dag.edges:
                if not isinstance(a,str) and not isinstance(b,str):
                    assert dag.spans[b][0]<=dag.spans[a][1]<dag.spans[b][1]
            canon=canonical_edges(state,dag,uid_offset=0)
            bandwidth={k:v.bandwidth_bytes_per_s for k,v in checked['resources'].links.items()}
            sparse=admitted_edges(canon,dag.edge_set,bandwidth)
            assert canon<=sparse<=dag.edge_set
            assert LayerCompatibilityDag(dag.spans,tuple(sparse),dag.layers).path_count()>0
            ini=ConfigParser(); ini.read(layout/'simulator_cluster.ini')
            def uid(name): return name if name in ['source','sink'] else int(name.rsplit('_',1)[1])-2
            exported={(uid(ini[s]['in']),uid(ini[s]['out'])) for s in ast.literal_eval(ini['Links']['names'])}
            assert exported==dag.edge_set, 'Exported and M1 edges differ'
            sol=ConfigParser(); sol.read(layout/'solution.ini')
            exported_spans={uid(n):(v[0],v[-1]+1) for n,t in sol['Solution'].items() if (v:=ast.literal_eval(t))}
            assert exported_spans==dag.spans
            bad=deepcopy(state); first=bad['segments'][0]['replicas'][0][0]
            bad['lengths'][str(first)]=model.capacity[first]+1
            tests={'over_capacity':rejection(lambda:validate_placement(model,bad))}
            gap=deepcopy(state); gap['segments'][1]['start']+=1
            tests['layer_gap']=rejection(lambda:validate_placement(model,gap))
            duplicate=deepcopy(state); duplicate['segments'][1]['replicas'][0][0]=first
            tests['reused_gpu']=rejection(lambda:validate_placement(model,duplicate))
            with patch.object(model.manager,'get_kv_cache_capacity',return_value=0):
                tests['zero_kv']=rejection(lambda:validate_placement(model,state))
            broken=TopologyModel(physical)
            # A cross-replica boundary can remain reachable after one edge is
            # removed. Remove an actual internal chain edge instead.
            replica=next(r for segment in state['segments'] for r in segment['replicas'] if len(r)>1)
            edge=(replica[0],replica[1])
            for a,b in [edge,edge[::-1]]:
                broken.config.remove_section(f'Link-{a}-{b}')
            from_topology.cache_clear()
            tests['missing_canonical_link']=rejection(lambda:validate_placement(broken,state))
            from_topology.cache_clear()
            assert all(t['passed'] for t in tests.values()),tests
            record.update(status='passed',strict_layer_progress=True,exported_edges_equal=True,
                exported_spans_equal=True,full_edges=len(dag.edges),canonical_edges=len(canon),
                sparse_edges=len(sparse),full_paths=dag.path_count(),
                sparse_paths=LayerCompatibilityDag(dag.spans,tuple(sparse),dag.layers).path_count(),
                active_gpus=checked['active_gpus'],layer_copies=checked['layer_copies'],
                negative_checks=tests,recorded_planning_wall_s=obj.get('search_wall_s'),
                planning_time_note='Historical asset metadata; not an independent timing measurement of this restricted candidate.',
                input_hashes={str((layout/n).relative_to(ROOT)):digest(layout/n)
                              for n in ['placement.json','solution.ini','simulator_cluster.ini']})
        except BaseException as e:
            record.update(status='failed',**capture(e))
        results.append(record)
        print('M1',scenario,cell,record['status'],flush=True)
    hardware=subprocess.run(['C:/Windows/System32/nvidia-smi.exe',
        '--query-gpu=name,memory.total,memory.free','--format=csv,noheader'],capture_output=True,text=True)
    result=dict(finished_at=stamp(),kind='structural_validation_not_performance_experiment',cases=results,
        test_correction='Attempt 1 wrongly expected rejection after removing a redundant boundary edge. Original retained; corrected to remove an internal replica-chain edge.',
        hardware=hardware.stdout.strip(),hardware_exit_code=hardware.returncode,
        limitations=['Legality and reachability do not guarantee arbitrary-load KV safety.',
                     'Single local GPU does not reproduce the simulated 24-GPU heterogeneous hardware.',
                     'No full 70B distributed-engine or real inter-GPU network calibration has been performed.'])
    write(HERE/'static_audit.json',result)


if __name__=='__main__': main()
