param([string]$Revision='v3',[ValidateSet('smoke','development')][string]$Phase='smoke')
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
(& 'D:/software/miniconda/Scripts/conda.exe' shell.powershell hook) | Out-String | Invoke-Expression
conda activate gllm
$env:PYTHONHASHSEED='0'
@'
import copy, gzip, json, math, sys
from pathlib import Path
from experiments.v3_path_crossover import run as old
from experiments.v3_adaptive_space_cohort.report import recompute
from work3_control.run import HERE, ROOT, PROTOCOL, POLICIES, check_frozen, trace_for
from work3_control.report import validate

revision,phase=sys.argv[1:]
check_frozen(revision)
context=old.load_context()
seeds=[PROTOCOL['smoke_seed']] if phase=='smoke' else PROTOCOL['development_seeds']
records=[]
base=None
def identity(row,policy,seed):
    required={'experiment':PROTOCOL['experiment'],'revision':revision,'phase':phase,
              'policy':policy,'seed':seed,'duration_s':3*PROTOCOL['stage_duration_s'][phase],
              'classification':'simulation_only','audit_sha256':old.digest(HERE/'audits'/f'{revision}.json')}
    assert all(row.get(k)==v for k,v in required.items()),'result identity'
    assert row['environment']==old.read(HERE/'audits'/f'{revision}.json')['environment'],'result environment'
for seed in seeds:
    expected=trace_for(seed,PROTOCOL['stage_duration_s'][phase])
    for policy in POLICIES:
        path=HERE/'runs'/revision/phase/f'{policy}_seed{seed}.json'
        row=old.read(path)
        identity(row,policy,seed)
        with gzip.open(ROOT/row['execution_source'],'rt',encoding='utf-8') as stream:
            events=json.load(stream)
        issues=validate(row,events,expected,context)
        if issues: raise AssertionError(issues[:10])
        assert old.digest(ROOT/row['execution_source'])==row['execution_sha256']
        for uid,sample in row['lifecycle']['query_samples'].items():
            assert sample['route']==[stage[1] for stage in sample['route_stages'][:-1]],uid
        record={'policy':policy,'seed':seed,'source_sha256':old.digest(path),
                'active_gpus':len(row['execution']['gpu_seconds_per_gpu']),
                'kv_peak_fraction':max(v/row['kv_capacity'][k] for k,v in row['kv_peak_reserved'].items()),
                'stage_arrival_cohorts':[], 'control_reconstruction':None}
        for stage in row['stages']:
            selected={uid:s for uid,s in row['lifecycle']['query_samples'].items()
                      if stage['start_s']<=s['arrival_s']<stage['end_s']}
            record['stage_arrival_cohorts'].append({**stage,**recompute(selected)})
        if policy=='route_control':
            filtered=0.0
            opened=False
            last=switched=None
            switches=0
            stage_actions=[dict(different=0,selected=0,positive_net=0,batch_veto=0) for _ in row['stages']]
            for item in row['control_events']:
                if item['capacity_fallback']: continue
                now=item['time_s']
                if last is None: last=switched=now
                assert now>=last
                filtered+=(1-math.exp(-(now-last)/PROTOCOL['candidate']['ewma_tau_s']))*(item['net_proxy_s']-filtered)
                last=now
                target=opened
                if not opened and filtered>PROTOCOL['candidate']['open_s']: target=True
                elif opened and filtered<=PROTOCOL['candidate']['close_s']: target=False
                if target!=opened and now-switched>=PROTOCOL['candidate']['dwell_s']:
                    opened=target; switched=now; switches+=1
                assert math.isclose(filtered,item['filtered_s'],rel_tol=1e-10,abs_tol=1e-10)
                assert opened==item['gate_open']
                expected_selection=item['candidates_differ'] and opened and item['net_proxy_s']>0
                assert expected_selection==item['selected_expanded']
                if item['selected_expanded']:
                    path=[s[1] for s in item['expanded'][:-1]]
                    vertices=['source',*path,'sink']
                    assert any(edge not in context['partial_edges'] for edge in zip(vertices,vertices[1:])), 'Expanded choice stayed entirely in partial'
                arrival=row['lifecycle']['query_samples'][str(item['query_uid'])]['arrival_s']
                index=min(2,int(arrival//PROTOCOL['stage_duration_s'][phase]))
                stage_actions[index]['different']+=item['candidates_differ']
                stage_actions[index]['selected']+=item['selected_expanded']
                stage_actions[index]['positive_net']+=item['candidates_differ'] and item['net_proxy_s']>0
                stage_actions[index]['batch_veto']+=item['candidates_differ'] and item['cost_baseline_s']>item['cost_expanded_s'] and item['net_proxy_s']<=0
            assert switches==row['control_switches']
            record['control_reconstruction']={'passed':True,'switches':switches,'stage_actions':stage_actions}
        records.append(record)
        if base is None: base=(row,events,expected)

authentic,events,expected=base
assert not validate(authentic,events,expected,context)
corruptions={}
def rejects(name,mutator):
    altered=copy.deepcopy(authentic)
    mutator(altered)
    try:
        identity(altered,authentic['policy'],authentic['seed'])
        problems=validate(altered,events,expected,context)
    except (ValueError,KeyError,IndexError,AssertionError,TypeError): problems=['invalid data rejected']
    if not problems: raise AssertionError('Corruption accepted: '+name)
    corruptions[name]={'rejected':True,'first_issue':problems[0]}
rejects('reported_metric',lambda r:r['lifecycle'].__setitem__('tpot_p95_s',r['lifecycle']['tpot_p95_s']+.01))
def delete_token(r):
    sample=max(r['lifecycle']['query_samples'].values(),key=lambda s:len(s['decode_completion_times_s']))
    sample['decode_completion_times_s'].pop()
rejects('missing_decode_token',delete_token)
def input_change(r):
    next(iter(r['lifecycle']['query_samples'].values()))['input_tokens']+=1
rejects('trace_input_change',input_change)
def overflow(r):
    uid=next(iter(r['kv_peak_reserved']))
    r['kv_peak_reserved'][uid]=r['kv_capacity'][uid]+1
rejects('kv_overflow',overflow)
def illegal(r): next(iter(r['lifecycle']['query_samples'].values()))['route'][0]=999999
rejects('illegal_route',illegal)
def incomplete(r): next(iter(r['lifecycle']['query_samples'].values()))['completed']=False
rejects('incomplete_query',incomplete)
rejects('execution_work_metric',lambda r:r['execution'].__setitem__('gpu_seconds_lifecycle',-1))
rejects('duplicate_probe_counts',lambda r:r.__setitem__('route_count',r['route_count']+1))
rejects('wrong_seed_header',lambda r:r.__setitem__('seed',0))
rejects('wrong_policy_header',lambda r:r.__setitem__('policy','full' if r['policy']!='full' else 'partial'))

historical_hashes={
 'experiments/v3_path_crossover/analysis.json':'728da75a8adea33fc6c713e869cd5306165e2a9e2988c5c76587be9b2cda1f65',
 'experiments/v3_path_crossover/validation.json':'fad12b888890e45819a21a4e1b173d41d900d8a7b27a0a8419b50068685af540',
 'experiments/v3_adaptive_space_cohort/formal_analysis.json':'79ba5792748ed9a6e57cb35cf3c73a13b71808cab2f504e2bdff929c6d56a9c4'}
assert all(old.digest(ROOT/p)==h for p,h in historical_hashes.items())
result={'phase':phase,'revision':revision,'verification_script_sha256':old.digest(HERE/'verify.ps1'),
        'all_passed':True,'records':records,'corruption_probes':corruptions,
        'historical_analyses_unchanged':historical_hashes,
        'scope':'deterministic integrity and descriptive mechanism diagnostics, not independent external review'}
destination=HERE/'runs'/revision/f'{phase}_extended_verification.json'
if destination.exists():
    previous=old.read(destination)
    backup=destination.with_name(f"{phase}_extended_verification_{previous['verification_script_sha256'][:12]}.json")
    if not backup.exists(): old.write(backup,previous)
old.write(destination,result)
print(json.dumps({'validated':len(records),'corruption_rejections':len(corruptions),'history_unchanged':True,'source':str(destination)},ensure_ascii=False))
'@ | python -X faulthandler - $Revision $Phase
if ($LASTEXITCODE -ne 0) { throw "Extended verification failed: $LASTEXITCODE" }
