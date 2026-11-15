"""Opt-in bounded search, verification, target expansion, then overnight training.

Run from the repository root:
  python ml/flex2_discovery.py --hours 8 --additional-runs 60 --seeds 3 --patience 25

Search time is capped at half the budget (at most four hours), leaving the rest for
training. Search outputs are written to a new ignored directory per invocation.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from flex2_data import ROOT as BASE_ROOT

DISCOVERY_CATEGORIES={
    'Reduced Gravity/SurrogateFuel 2014 - Heptane50_Toluene50':'Heptane50_Toluene50',
    'Reduced Gravity/SurrogateFuel 2014 - Heptane50_Iso-Octane50':'Heptane50_Iso-Octane50',
    'Reduced Gravity/SurrogateFuel 2014 - Decane75_Propylbenzene25':'Decane75_Propylbenzene25',
    'Reduced Gravity/ SurrogateFuel 2014 - Decane25_Propylbenzene75':'Decane25_Propylbenzene75',
    'Reduced Gravity/SurrogateFuel 2012 - Decane50_Propylbenzene50':'Decane50_Propylbenzene50',
    'Reduced Gravity/SurrogateFuel 2012 - Propylbenzene':'Propylbenzene',
}


def run(hours=8,additional_runs=60,seeds=3,patience=25):
    if not 0<hours<=8 or additional_runs<1:raise ValueError('Use 0 < hours <= 8 and positive --additional-runs')
    started=time.monotonic();search_deadline=started+min(hours*1800,4*3600)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    workspace=BASE_ROOT.parent/'flex2-discovery'/f'run-{stamp}'
    workspace.mkdir(parents=True,exist_ok=False);log=workspace/'workflow.jsonl'
    def event(stage,**details):
        row={'utc':datetime.now(timezone.utc).isoformat(),'stage':stage,**details}
        with log.open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
        print(json.dumps(row),flush=True)

    dataset=None;search_error=None
    try:
        import flex2_data
        import flex2_inputs
        flex2_data.ROOT=workspace/'candidate-cache'
        flex2_data.CATEGORIES={**flex2_data.CATEGORIES,**DISCOVERY_CATEGORIES}
        flex2_inputs.ROOT=flex2_data.ROOT
        flex2_inputs.REPORTS=workspace/'audit'
        flex2_inputs.SUFFIXES=['_MDCA_Testpoint_Settings.txt']
        real_read=flex2_data.read
        def budget_read(*args,**kwargs):
            if time.monotonic()>=search_deadline:raise TimeoutError('Search time budget exhausted')
            return real_read(*args,**kwargs)
        flex2_data.read=budget_read
        flex2_inputs.read=budget_read
        event('search_started',search_budget_seconds=search_deadline-started,categories=list(DISCOVERY_CATEGORIES))
        flex2_data.fetch(limit=100)
        if time.monotonic()>=search_deadline:raise TimeoutError('Search time budget exhausted before image screening')
        flex2_data.prepare()
        flex2_inputs.fetch();flex2_inputs.audit()
        candidate_manifest=json.loads((flex2_data.ROOT/'manifest.json').read_text())
        candidate_evidence=flex2_inputs.REPORTS/'flex2-inputs.csv'
        expanded=workspace/'expanded'
        import flex2_expand
        report=flex2_expand.expand(flex2_data.ROOT,candidate_evidence,
            target_runs=len(json.loads((BASE_ROOT/'manifest.json').read_text())['records'])+additional_runs,
            out=expanded,run_cache=flex2_data.ROOT,base_root=BASE_ROOT)
        dataset=expanded
        search_report={'candidate_target_count':len(candidate_manifest['records']),**report,
            'search_elapsed_seconds':time.monotonic()-started,'search_error':None}
        (workspace/'search-report.json').write_text(json.dumps(search_report,indent=2)+'\n')
        event('search_complete',additional_runs=report['added_count'],target_runs=report['target_count'],
            elapsed_seconds=search_report['search_elapsed_seconds'])
    except Exception as exc:
        search_error=f'{type(exc).__name__}: {exc}'
        event('search_incomplete',error=search_error,elapsed_seconds=time.monotonic()-started)

    if dataset is None:
        # Keep the overnight training useful if NASA discovery is incomplete; the
        # report clearly identifies that only the already verified expansion was used.
        dataset=BASE_ROOT.parent/'flex2-expanded'
        fallback={'search_error':search_error,'dataset':'existing verified 140-target snapshot',
            'search_elapsed_seconds':time.monotonic()-started}
        (workspace/'search-report.json').write_text(json.dumps(fallback,indent=2)+'\n')
    remaining=hours-(time.monotonic()-started)/3600
    if remaining<=0:
        event('training_skipped',reason='Search used the complete time budget')
        return 2
    event('training_started',hours_remaining=remaining,dataset=str(dataset))
    from flex2_overnight import main
    main(remaining,seeds,patience,dataset_root=dataset,output_dir=workspace/'training')
    event('workflow_complete',elapsed_seconds=time.monotonic()-started,search_error=search_error)
    print(f'Workflow artifacts: {workspace}',flush=True)
    return 0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hours',type=float,default=8);p.add_argument('--additional-runs',type=int,default=60);p.add_argument('--seeds',type=int,default=3);p.add_argument('--patience',type=int,default=25);a=p.parse_args();raise SystemExit(run(a.hours,a.additional_runs,a.seeds,a.patience))
