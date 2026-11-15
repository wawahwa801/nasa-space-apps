"""Continue a smooth-reference CNN after finding N new eligible independent runs."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import torch

from flex2_continuous import ORIGINAL_ROOT,atomic_json,prepare_all,train,frozen_features
from flex2_overnight import load_verified


def load_parent(checkpoint):
    checkpoint=Path(checkpoint).resolve()
    saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
    if saved['metadata'].get('architecture')!='soft-reference-generator-v1':raise ValueError('Use a continuous-model final.pt checkpoint')
    dataset=checkpoint.parent.parent/'expanded'
    if hashlib.sha256((dataset/'manifest.json').read_bytes()).hexdigest()!=saved['metadata']['manifest_sha256']:
        raise ValueError('Parent dataset manifest differs from checkpoint')
    d,_,_,_,evidence_hash=load_verified(dataset)
    if 'preprocessing' in saved['metadata']:frozen_features(d,saved['metadata'])
    if evidence_hash!=saved['metadata']['evidence_sha256'] or d['feature_names']!=saved['metadata']['features'] or d['groups'].tolist()!=saved['metadata']['target_ids']:
        raise ValueError('Parent preprocessing, evidence, or IDs differ from checkpoint')
    if 'preprocessing' not in saved['metadata']:
        saved['metadata']['preprocessing']=dict(low=d['feature_low'].tolist(),scale=d['feature_scale'].tolist())
    return saved


def continue_run(checkpoint,new_runs,search_hours,train_hours,epochs):
    if new_runs<0 or not 0<search_hours<=2 or not 0<train_hours<=8 or epochs<1:raise ValueError('Invalid run count or budget')
    saved=load_parent(checkpoint);old=set(saved['metadata']['target_ids'])
    discovery=ORIGINAL_ROOT.parent/'flex2-discovery';caches=sorted(discovery.glob('run-*/candidate-cache'))
    cache=caches[-1] if caches else discovery/'continuous-source-cache'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    workspace=discovery/f'continuation-{stamp}';workspace.mkdir(parents=True,exist_ok=False)
    # Immutable snapshot: an actively training parent's atomic checkpoint may advance.
    torch.save(saved,workspace/'parent.pt')
    deadline=time.monotonic()+search_hours*3600;attempt=0;dataset=None
    command=[sys.executable,str(Path(__file__).parent/'flex2_continuous.py'),'--worker-cache',str(cache.resolve())]
    while True:
        if new_runs:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise RuntimeError(f'Deadline reached before {new_runs} new verified runs; training was not started. Reports: {workspace}')
            with (workspace/'search.log').open('a') as log:
                worker=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
                try:worker.wait(timeout=min(300,remaining))
                except subprocess.TimeoutExpired:
                    worker.terminate()
                    try:worker.wait(timeout=10)
                    except subprocess.TimeoutExpired:worker.kill();worker.wait()
        attempt+=1;candidate=workspace/f'screened-{attempt}'
        prepare_all(cache,candidate)
        d,_,_,_,_=load_verified(candidate);ids=set(d['groups'].tolist());added=sorted(ids-old);missing=sorted(old-ids)
        report=dict(parent_epoch=saved['epoch'],parent_targets=len(old),requested_new_runs=new_runs,verified_new_count=len(added),added_run_ids=added,missing_parent_ids=missing,total_targets=len(ids))
        atomic_json(workspace/'discovery-report.json',report);print(json.dumps(report),flush=True)
        if missing:raise ValueError('Some parent runs were not verified in the new dataset; stopped before training')
        if len(added)>=new_runs:dataset=candidate;break
        if new_runs==0:raise ValueError('No usable dataset')
        # Retry unavailable records and refresh catalog without hammering the service.
        time.sleep(max(0,min(30,deadline-time.monotonic())))
    atomic_json(workspace/'continuation.json',dict(checkpoint=str(Path(checkpoint).resolve()),snapshot='parent.pt',dataset=str(dataset),**report))
    # Comparison loader expects the same layout as the original workflow.
    (workspace/'expanded').symlink_to(dataset.name,target_is_directory=True)
    train(dataset,workspace/'training',train_hours,epochs,resume=saved)
    print('Continued checkpoint: '+str(workspace/'training/final.pt'),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--resume',required=True,type=Path);p.add_argument('--new-runs',type=int,required=True);p.add_argument('--search-hours',type=float,default=2);p.add_argument('--train-hours',type=float,default=1);p.add_argument('--epochs',type=int,default=50);a=p.parse_args()
    continue_run(a.resume,a.new_runs,a.search_hours,a.train_hours,a.epochs)
