"""Diagnostic only: replay a prefix, never enter a performance decision.

This file is not imported by the frozen production runner. Its own hash is
recorded with each probe. It observes the pure ModelLayer function contract.
"""
import argparse
import contextlib
import dis
import hashlib
import io
import json
import time
import traceback
from pathlib import Path


def main():
    from work3_control.run import ROOT, HERE, trace_for, ExecutionWitness
    from experiments.v3_adaptive_space_cohort.run import environment
    from experiments.v3_path_crossover import run as original
    from experiments.v3_cluster42.kv_admission import install_completion_wakeup
    from benchmarks import fixed_window
    from rcaps.v3.topology import TopologyModel
    from simulator.event_simulator.model import ModelLayer
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=('bare','timing','witness','both'),required=True)
    parser.add_argument('--duration',type=int,default=60)
    parser.add_argument('--contract',action='store_true')
    args=parser.parse_args()
    code=ModelLayer.get_inference_statistics.__code__
    result={'classification':'runtime_diagnostic_only','mode':args.mode,
            'duration':args.duration,'contract_wrapper':args.contract,'environment':environment(),
            'probe_sha256':original.digest(Path(__file__)),
            'layer_function':{'qualname':ModelLayer.get_inference_statistics.__qualname__,
                              'source':code.co_filename,'bytecode_sha256':hashlib.sha256(code.co_code).hexdigest(),
                              'last_instructions':[(i.opname,str(i.argval)) for i in list(dis.get_instructions(code))[-8:]]},
            'stats_calls':0,'bad_returns':[]}
    original_stats=ModelLayer.get_inference_statistics
    if args.contract:
        def checked(layer,requests):
            value=original_stats(layer,requests)
            result['stats_calls']+=1
            if not isinstance(value,tuple) or len(value)!=2:
                result['bad_returns'].append({'type':type(value).__name__,'repr':repr(value),
                    'layer':layer.layer_id,'request_ids':[r.request_uid for r in requests],
                    'repeated':repr(original_stats(layer,requests))})
                raise TypeError('Pure ModelLayer contract violation captured')
            return value
        ModelLayer.get_inference_statistics=checked
    context=original.load_context()
    holder={}
    def factory(sim):
        scheduler=original.builder('canonical',context)(sim)
        if args.mode in ('witness','both'):
            holder['witness']=ExecutionWitness(sim,scheduler)
        install_completion_wakeup(sim,scheduler)
        return scheduler
    trace=trace_for(104,200)
    started=time.perf_counter()
    folder=HERE/'diagnostics'/'runs'
    folder.mkdir(parents=True,exist_ok=True)
    label=f'{args.mode}_{args.duration}_contract{int(args.contract)}'
    target=folder/f'{label}.json'
    if target.exists(): raise ValueError('Never overwrite preserved diagnostic')
    try:
        with target.with_suffix('.log').open('w',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
            window=fixed_window.run(context['topology'],'queue_dag',0,args.duration,0,104,
                original.DEPLOY/'solution.ini',original.DEPLOY/'simulator_cluster.ini',
                compact=True,record_query_samples=True,scheduler_factory=factory,
                profile_scheduler=args.mode in ('timing','both'),trace_override=trace,
                physical_cluster=context['physical'],machine_counts=TopologyModel(context['physical']).machine_counts)
        result.update(status='passed',arrivals=window['arrivals'],
                      output_count=window['output_throughput_tokens_per_s']*args.duration,
                      route_counts=window['route_counts'])
    except Exception as error:
        result.update(status='failed',error=repr(error),traceback=traceback.format_exc())
    result['wall_seconds']=time.perf_counter()-started
    original.write(target,result)
    print(json.dumps(result,ensure_ascii=False))
    if result['status']!='passed': raise SystemExit(1)


if __name__=='__main__': main()
