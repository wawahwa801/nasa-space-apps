"""Smooth-reference CNN: bounded discovery followed by all-data training.

python ml/flex2_continuous.py --search-hours 2 --train-hours 6
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time

import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

from flex2_data import ROOT as ORIGINAL_ROOT
from flex2_discovery import DISCOVERY_CATEGORIES
from flex2_overnight import load_verified


def atomic_json(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');tmp.replace(path)


class ContinuousCNN(nn.Module):
    """Generate pixels from soft reference embeddings; no copied-image skip."""
    def __init__(self,features):
        super().__init__()
        self.encoder=nn.Sequential(nn.Conv2d(3,16,5,2,2),nn.SiLU(),nn.Conv2d(16,32,4,2,1),nn.SiLU(),nn.Conv2d(32,48,4,2,1),nn.SiLU(),nn.Conv2d(48,64,4,2,1),nn.SiLU())
        self.condition=nn.Sequential(nn.Linear(features*3,256),nn.SiLU(),nn.Linear(256,64*8*8),nn.SiLU())
        self.fuse=nn.Conv2d(128,64,3,padding=1)
        self.layers=nn.ModuleList([nn.Conv2d(a,b,3,padding=1) for a,b in [(64,48),(48,32),(32,24),(24,16),(16,8)]])
        self.output=nn.Conv2d(8,3,1)
        nn.init.constant_(self.output.bias,-3.)

    def encode_references(self,images):
        return F.adaptive_avg_pool2d(self.encoder(images),8)

    def decode(self,query,reference_features,reference_embedding):
        condition=self.condition(torch.cat([query,reference_features,query-reference_features],1)).reshape(-1,64,8,8)
        z=F.silu(self.fuse(torch.cat([reference_embedding,condition],1)))
        for layer in self.layers:z=F.silu(layer(F.interpolate(z,scale_factor=2,mode='bilinear',align_corners=False)))
        return self.output(z).sigmoid()


def soft_references(query,features,fuels,query_fuels,exclude,temperature=.15):
    """All same-fuel references receive smooth weights; own run always excluded."""
    distance=(query[:,None,:]-features[None,:,:]).square().mean(2)
    valid=query_fuels[:,None]==fuels[None,:]
    if exclude is not None:valid[torch.arange(len(query),device=query.device),exclude]=False
    if not valid.any(1).all():raise ValueError('Each query needs another independent same-fuel run')
    return (-distance/temperature).masked_fill(~valid,-torch.inf).softmax(1)


def search_worker(cache):
    import flex2_data as fd
    from flex2_inputs import setting_values
    fd.ROOT=Path(cache);fd.ROOT.mkdir(parents=True,exist_ok=True)
    fd.CATEGORIES={**fd.CATEGORIES,**DISCOVERY_CATEGORIES}
    nodes=fd.file_tree()
    selected=[n for n in nodes if n.get('subcategory') in fd.CATEGORIES and not n.get('restricted') and re.search(r'[A-Z]\d{3}[A-Z]\d{2}D\.zip$',n['key'])]
    candidates={}
    for node in selected:
        name=Path(node['key']).name
        if name in candidates:raise ValueError('Conflicting archive identity: '+name)
        candidates[name]=node
    # Breadth across fuels, and new IDs before already cached source members.
    groups={}
    for name,node in sorted(candidates.items()):
        run=re.search(r'([A-Z]\d{3}[A-Z]\d{2})D\.zip$',name)[1]
        groups.setdefault(node['subcategory'],[]).append((run,node))
    for values in groups.values():values.sort(key=lambda item:((fd.ROOT/item[0]/'record.json').exists(),item[0]))
    ordered=[]
    while any(groups.values()):
        for category in sorted(groups):
            if groups[category]:ordered.append(groups[category].pop(0))
    def one(item):
        run,node=item
        try:
            record=fd.acquire_run(node,nodes)
            matches=[n for n in nodes if Path(n['key']).name.endswith(run+'_MDCA_Testpoint_Settings.txt')]
            if len(matches)!=1 or matches[0].get('restricted'):raise ValueError('Missing/ambiguous/restricted settings')
            n=matches[0];p=fd.ROOT/run/Path(n['key']).name
            if not p.exists():p.write_bytes(fd.read(fd.signed(p.name),2_000_000))
            raw=p.read_bytes();values=setting_values(run,raw.decode('utf-8-sig'))
            if values['status']!='exact_run_match' or values['fiber_usage_flag'] is None:raise ValueError('Settings ID/usage rejected')
            atomic_json(fd.ROOT/run/'continuous-settings.json',dict(run=run,file=p.name,sha256=fd.sha(raw),resource_id=n['id'],version=n['version']))
            return dict(run=run,status='source_and_settings_matched')
        except Exception as error:return dict(run=run,status='excluded',reason=str(error))
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(one,item) for item in ordered]):
            result=future.result()
            with (fd.ROOT/'search.jsonl').open('a') as f:f.write(json.dumps(result)+'\n')
            print(json.dumps(result),flush=True)


def prepare_all(cache,dataset):
    import flex2_data as fd
    from flex2_inputs import setting_values
    fd.ROOT=cache;fd.CATEGORIES={**fd.CATEGORIES,**DISCOVERY_CATEGORIES}
    conflicts=json.loads((Path(__file__).parent/'reports/flex2-input-evidence.json').read_text())['conflicting_assertions']
    conflict_ids={run for a in conflicts for run in a['run_ids']}
    records=[];evidence={};exclusions=[]
    for path in sorted(cache.glob('*/record.json')):
        r=json.loads(path.read_text());run=r['run']
        try:
            if run in conflict_ids:raise ValueError('Known catalog/paper fuel conflict')
            if r['category'] not in fd.CATEGORIES:raise ValueError('Incompatible campaign')
            for member in r['metadata']+r['members']:
                if fd.sha((cache/run/member['file']).read_bytes())!=member['sha256']:raise ValueError('Source checksum mismatch')
            settings=list((cache/run).glob('*'+run+'_MDCA_Testpoint_Settings.txt'))
            if len(settings)!=1:raise ValueError('Settings unavailable/ambiguous')
            text=settings[0].read_text(encoding='utf-8-sig');v=setting_values(run,text)
            if v['status']!='exact_run_match' or v['fiber_usage_flag'] is None:raise ValueError('Settings rejected')
            summary=next(m for m in r['metadata'] if Path(m['file']).name.endswith(run+'.txt'))
            event=(cache/run/summary['file']).read_text(encoding='utf-8-sig')
            if not re.search(r'Test Point:\s*'+re.escape(run)+r'\b',event):raise ValueError('Event ID mismatch')
            match=re.search(r'Igniter On Time \(milliseconds\):\s*([\d.]+)',event)
            duration=float(match[1])/1000 if match else None
            evidence[run]=dict(run_id=run,fuel=r['fuel'],split='train',settings_status='exact_run_match',fiber_usage_flag=str(v['fiber_usage_flag']),igniter_power_setting_w=v['igniter_power_setting_w'],igniter_on_time_s=duration,igniter_on_time_status='exact_run_match' if duration and duration>0 else 'not_verified',settings_sha256=fd.sha(settings[0].read_bytes()),event_sha256=summary['sha256'])
            records.append(r)
        except Exception as error:exclusions.append(dict(run=run,reason=str(error)))
    atomic_json(cache/'inventory.json',records);fd.prepare()
    manifest=json.loads((cache/'manifest.json').read_text());data=np.load(cache/'prepared.npz')
    payload={k:data[k] for k in data.files};payload['splits']=np.asarray(['train']*len(data['groups']))
    dataset.mkdir(parents=True,exist_ok=False);np.savez_compressed(dataset/'prepared.npz',**payload)
    for r in manifest['records']:r['split']='train'
    manifest['counts']['splits']={'train':len(manifest['records']),'validation':0,'test':0};manifest['split']='All verified runs for fitting; no held-out evaluation'
    atomic_json(dataset/'manifest.json',manifest)
    rows=[evidence[str(run)] for run in data['groups']]
    with (dataset/'features.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    atomic_json(dataset/'verification.json',dict(accepted=len(rows),exclusions=exclusions,image_screen_exclusions=manifest['excluded'],known_fuel_conflict_ids_excluded=sorted(conflict_ids)))


def train(dataset,out,hours,epochs):
    d,m,x,_,evidence_hash=load_verified(dataset);out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(2);torch.manual_seed(43);rng=np.random.default_rng(43)
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    images=torch.tensor(d['images']).permute(0,3,1,2).float()/255
    conditions=torch.tensor(x,device=device);fuels=torch.tensor(d['fuels'],device=device)
    model=ContinuousCNN(x.shape[1]).to(device);optimizer=torch.optim.AdamW(model.parameters(),lr=3e-4,weight_decay=1e-3)
    metadata=dict(architecture='soft-reference-generator-v1',target_ids=d['groups'].tolist(),features=d['feature_names'],evidence_sha256=evidence_hash,manifest_sha256=hashlib.sha256((dataset/'manifest.json').read_bytes()).hexdigest(),temperature=.15,epochs=epochs,seed=43,parameters=sum(p.numel() for p in model.parameters()),independent_evaluation=False)
    atomic_json(out/'run.json',metadata);deadline=time.monotonic()+hours*3600
    for epoch in range(1,epochs+1):
        if time.monotonic()>=deadline:break
        model.train();losses=[]
        # Refresh detached reference encodings each epoch, so query-side generation
        # and reference encoder both train without retaining the whole image graph.
        with torch.no_grad():bank=torch.cat([model.encode_references(b.to(device)) for b in images.split(8)])
        for ids in np.array_split(rng.permutation(len(x)),math.ceil(len(x)/8)):
            ix=torch.tensor(ids,device=device);weights=soft_references(conditions[ix],conditions,fuels,fuels[ix],ix)
            # Query-independent soft attention has no nearest-neighbor switch.
            reference_embedding=torch.einsum('bn,nchw->bchw',weights,bank)
            # Train the encoder using a weighted reference image as an auxiliary
            # encoding path; no output image is copied directly into prediction.
            reference_image=torch.einsum('bn,nchw->bchw',weights.cpu(),images).to(device)
            reference_embedding=.5*reference_embedding+.5*model.encode_references(reference_image)
            prediction=model.decode(conditions[ix],weights@conditions,reference_embedding)
            target=images[ids].to(device);mask=torch.tensor(d['masks'][ids],device=device).unsqueeze(1)
            error=(prediction-target).abs();loss=error.mean()+.5*(error*mask).sum()/(3*mask.sum()).clamp(min=1)+.3*F.l1_loss(F.adaptive_avg_pool2d(prediction,32),F.adaptive_avg_pool2d(target,32))
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite loss')
            optimizer.zero_grad(set_to_none=True);loss.backward();gradient=nn.utils.clip_grad_norm_(model.parameters(),2.)
            if not torch.isfinite(gradient):raise FloatingPointError('Nonfinite gradient')
            optimizer.step();losses.append(float(loss.detach()))
        row=dict(epoch=epoch,training_loss=float(np.mean(losses)),independent_evaluation=False)
        with (out/'metrics.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        tmp=out/'checkpoint.tmp.pt';torch.save(dict(state={k:v.detach().cpu() for k,v in model.state_dict().items()},metadata=metadata,epoch=epoch,seed=43),tmp);tmp.replace(out/'final.pt')
        print(json.dumps(row),flush=True)


def main(search_hours,train_hours,epochs):
    if not 0<search_hours<=2 or not 0<train_hours<=8 or epochs<1:raise ValueError('Invalid search/training budget')
    discovery=ORIGINAL_ROOT.parent/'flex2-discovery'
    # Reuse downloaded sources. No published NPZ/checkpoint is overwritten.
    caches=sorted(discovery.glob('run-*/candidate-cache'))
    cache=caches[-1] if caches else discovery/'continuous-source-cache'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');workspace=discovery/f'continuous-{stamp}';workspace.mkdir(parents=True,exist_ok=False)
    command=[sys.executable,str(Path(__file__).resolve()),'--worker-cache',str(cache.resolve())]
    with (workspace/'search.log').open('w') as log:
        print(f'Searching up to {search_hours} hours; progress: {workspace / "search.log"}',flush=True)
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        try:process.wait(timeout=search_hours*3600)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()
    atomic_json(workspace/'search-status.json',dict(returncode=process.returncode,search_budget_hours=search_hours,cache=str(cache),note='Completed verified cached records are screened even when search reaches deadline'))
    print('Screening all cached source-verified runs and preparing all-data training',flush=True)
    prepare_all(cache,workspace/'expanded')
    train(workspace/'expanded',workspace/'training',train_hours,epochs)
    print('Completed continuous model: '+str(workspace),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--search-hours',type=float,default=2);p.add_argument('--train-hours',type=float,default=6);p.add_argument('--epochs',type=int,default=200);p.add_argument('--worker-cache',type=Path);a=p.parse_args()
    if a.worker_cache:search_worker(a.worker_cache)
    else:main(a.search_hours,a.train_hours,a.epochs)
