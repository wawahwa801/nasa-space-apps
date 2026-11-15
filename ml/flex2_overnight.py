"""Run a bounded, monitored FLEX-2 retrieval-conditioned CNN experiment.

Run from the repository root: python ml/flex2_overnight.py --hours 8
Uses only the frozen 100-target library and exact-run fiber/power joins.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

from flex2_data import ROOT, ART, FIELDS
from flex2_model import nearest, load as load_published
from spice_model import encode, metrics

EVIDENCE = Path(__file__).resolve().parent / 'reports' / 'flex2-inputs.csv'
OUT = ART / 'overnight'


class RetrievalConditioned(nn.Module):
    """Small reference encoder + condition MLP + image decoder (~1-2M params)."""
    def __init__(self, condition_size):
        super().__init__()
        self.ref = nn.Sequential(
            nn.Conv2d(3, 16, 5, stride=2, padding=2), nn.SiLU(),
            nn.Conv2d(16, 32, 4, stride=2, padding=1), nn.SiLU(),
            nn.Conv2d(32, 48, 4, stride=2, padding=1), nn.SiLU(),
            nn.Conv2d(48, 64, 4, stride=2, padding=1), nn.SiLU(),
        )
        self.condition = nn.Sequential(nn.Linear(condition_size, 128), nn.SiLU(), nn.Linear(128, 64*16*16), nn.SiLU())
        self.fuse = nn.Sequential(nn.Conv2d(128, 64, 3, padding=1), nn.SiLU())
        self.up = nn.ModuleList([
            nn.Sequential(nn.Conv2d(64,48,3,padding=1),nn.SiLU()),
            nn.Sequential(nn.Conv2d(48,32,3,padding=1),nn.SiLU()),
            nn.Sequential(nn.Conv2d(32,24,3,padding=1),nn.SiLU()),
            nn.Sequential(nn.Conv2d(24,16,3,padding=1),nn.SiLU()),
        ])
        self.out = nn.Conv2d(16, 3, 3, padding=1)

    def forward(self, condition, reference):
        z=torch.cat([self.ref(reference),self.condition(condition).reshape(-1,64,16,16)],1)
        z=self.fuse(z)
        for layer in self.up:
            z=layer(F.interpolate(z,scale_factor=2,mode='bilinear',align_corners=False))
        return (reference + .25*torch.tanh(self.out(z))).clamp(0,1)


def load_verified():
    data=np.load(ROOT/'prepared.npz');manifest=json.loads((ROOT/'manifest.json').read_text())
    raw=EVIDENCE.read_bytes();reader=csv.DictReader(raw.decode('utf-8-sig').splitlines());rows={r['run_id']:r for r in reader}
    if len(set(data['groups'].tolist()))!=len(data['groups']):
        raise ValueError('Image library must have unique run IDs')
    if manifest['fields']!=FIELDS or not np.isfinite(data['features']).all():raise ValueError('Unexpected/malformed base feature schema')
    fiber=[];power=[];power_missing=[];keep=[];excluded=[]
    for i,run in enumerate(data['groups'].tolist()):
        row=rows.get(run)
        if not row or row['settings_status']!='exact_run_match':
            excluded.append(run);continue
        if row['split']!=str(data['splits'][i]):raise ValueError(f'Split mismatch for {run}; refusing leakage-prone run')
        if row['fiber_usage_flag'] not in ('True','False'):raise ValueError(f'Unknown fiber setting for {run}')
        keep.append(i)
        fiber.append(float(row['fiber_usage_flag']=='True'))
        try:
            value=float(row['igniter_power_setting_w']);present=math.isfinite(value) and value>0
        except (TypeError,ValueError):present=False;value=0.
        power.append(value if present else np.nan);power_missing.append(float(not present))
    if len(keep)<30:raise ValueError(f'Only {len(keep)} image targets have verified apparatus settings')
    data={k:data[k][keep] for k in data.files};data['excluded_unverified_settings_ids']=excluded
    x=np.column_stack([data['features'],fiber,power,power_missing]).astype('float32')
    split=data['splits'];train=np.where(split=='train')[0]
    median=np.nanmedian(x[train],axis=0);median=np.nan_to_num(median,nan=0.)
    missing=~np.isfinite(x);x[missing]=np.take(median,np.where(missing)[1])
    low=x[train].min(0);scale=np.maximum(x[train].max(0)-low,1e-6)
    x=np.clip((x-low)/scale,-.25,1.25).astype('float32')
    # Derive training-only nearest references. A training target cannot retrieve itself;
    # validation/test references come only from training runs.
    refs=[];fuel=data['fuels'];groups=data['groups']
    for i in range(len(x)):
        candidates=train[(fuel[train]==fuel[i]) & (groups[train]!=groups[i])]
        if not len(candidates):raise ValueError(f'No leakage-safe reference for {groups[i]}')
        dist=np.mean((x[candidates]-x[i])**2,axis=1)
        refs.append(int(candidates[np.argmin(dist)]))
    return data,manifest,x,np.asarray(refs),hashlib.sha256(raw).hexdigest()


def main(hours,seed_count,patience):
    if not 0<hours<=8:raise ValueError('--hours must be between 0 and 8')
    data,manifest,x,refs,evidence_hash=load_verified()
    OUT.mkdir(parents=True,exist_ok=True);torch.set_num_threads(max(1,min(4,os.cpu_count() or 1)))
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    start=time.monotonic();deadline=start+hours*3600;log=OUT/'metrics.jsonl'
    images=torch.tensor(data['images'],device=device).permute(0,3,1,2).float()/255
    masks=torch.tensor(data['masks'],device=device).unsqueeze(1).float()
    cond=torch.tensor(x,device=device);refs=torch.tensor(refs,device=device)
    splits={s:np.where(data['splits']==s)[0] for s in ('train','validation','test')}
    metadata={'device':str(device),'hours':hours,'target_count':len(x),'features':['pressure_kpa','temperature_c','fiber_usage_flag','igniter_power_setting_w','power_missing_flag'],'manifest_sha256':hashlib.sha256((ROOT/'manifest.json').read_bytes()).hexdigest(),'evidence_sha256':evidence_hash,'target_ids':data['groups'].tolist(),'split_ids':{k:data['groups'][v].tolist() for k,v in splits.items()},'selection':'validation foreground-weighted MAE; test split evaluated after training','reference_pool':'train only; self-run excluded','model':'small retrieval-conditioned CNN'}
    (OUT/'run.json').write_text(json.dumps(metadata,indent=2))
    run_no=0
    while time.monotonic()<deadline and run_no<seed_count:
        seed=42+run_no;random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
        net=RetrievalConditioned(cond.shape[1]).to(device);opt=torch.optim.AdamW(net.parameters(),lr=5e-4,weight_decay=1e-3)
        best=math.inf;best_state=None;stale=0;epoch=0
        while time.monotonic()<deadline and stale<patience:
            epoch+=1;net.train();order=np.random.permutation(splits['train']);losses=[]
            for ids in np.array_split(order,max(1,math.ceil(len(order)/8))):
                ix=torch.as_tensor(ids,device=device);pred=net(cond[ix],images[refs[ix]])
                err=(pred-images[ix]).abs();loss=err.mean()+.5*(err*masks[ix]).sum()/(3*masks[ix].sum()).clamp(min=1)+.3*F.l1_loss(F.adaptive_avg_pool2d(pred,32),F.adaptive_avg_pool2d(images[ix],32))
                if not torch.isfinite(loss):raise FloatingPointError('Non-finite training loss; run stopped')
                opt.zero_grad(set_to_none=True);loss.backward();grad=nn.utils.clip_grad_norm_(net.parameters(),2.)
                if not torch.isfinite(grad):raise FloatingPointError('Non-finite gradient; run stopped')
                opt.step();losses.append(float(loss.detach()))
            net.eval()
            with torch.inference_mode():
                vi=torch.as_tensor(splits['validation'],device=device);vp=net(cond[vi],images[refs[vi]])
                val=metrics(vp,images[vi],masks[vi]);score=val['weighted_mae']
            if not math.isfinite(score):raise FloatingPointError('Non-finite validation metric; run stopped')
            improved=score<best
            if improved:
                best=score;stale=0;best_state={k:v.detach().cpu().clone() for k,v in net.state_dict().items()}
                tmp=OUT/f'.seed-{seed}.tmp.pt';torch.save({'state':best_state,'seed':seed,'epoch':epoch,'validation':val,'metadata':metadata},tmp);tmp.replace(OUT/f'seed-{seed}-best.pt')
            else:stale+=1
            rec={'seed':seed,'epoch':epoch,'train_loss':float(np.mean(losses)),'validation':val,'best_validation_weighted_mae':best,'stale_epochs':stale,'seconds':time.monotonic()-start,'gpu_memory_bytes':torch.cuda.max_memory_allocated() if device.type=='cuda' else None}
            with log.open('a') as f:f.write(json.dumps(rec,allow_nan=False)+'\n')
            print(json.dumps(rec),flush=True)
            if device.type=='cuda' and torch.cuda.memory_reserved()>torch.cuda.get_device_properties(device).total_memory*.95:raise RuntimeError('GPU memory exceeds 95% stability limit')
        if best_state:
            net.load_state_dict(best_state);net.eval()
            with torch.inference_mode():
                ix=torch.as_tensor(splits['test'],device=device);pred=net(cond[ix],images[refs[ix]])
                hybrid_score=metrics(pred,images[ix],masks[ix])
                retrieval_score=metrics(images[refs[ix]],images[ix],masks[ix])
                train_ix=torch.as_tensor(splits['train'],device=device)
                mean_images=torch.stack([images[train_ix][torch.as_tensor(data['fuels'][splits['train']]==data['fuels'][i],device=device)].mean(0) for i in splits['test']])
                mean_score=metrics(mean_images,images[ix],masks[ix])
                base_net,base_saved=load_published();base_net=base_net.to(device)
                base_cond=encode(torch.tensor(data['features'][splits['test']],device=device),torch.tensor(data['fuels'][splits['test']],device=device),base_saved['low'].to(device),base_saved['scale'].to(device),len(manifest['fuels']))
                base_pred=torch.cat([base_net(batch)[0] for batch in base_cond.split(8)])
                base_score=metrics(base_pred,images[ix],masks[ix])
            out={'seed':seed,'selected_epoch':epoch-stale,'test_metrics':{'retrieval_conditioned_cnn':hybrid_score,'extended_feature_retrieval':retrieval_score,'same_fuel_training_mean':mean_score,'published_feature_only_cnn':base_score},'test_reference_ids':data['groups'][refs[splits['test']]].tolist()}
            (OUT/f'seed-{seed}-test.json').write_text(json.dumps(out,indent=2,allow_nan=False))
        run_no+=1
    print(json.dumps({'finished_seeds':run_no,'elapsed_seconds':time.monotonic()-start,'deadline_seconds':hours*3600,'metrics_log':str(log),'artifacts':str(OUT)},indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hours',type=float,default=8);p.add_argument('--seeds',type=int,default=3);p.add_argument('--patience',type=int,default=25);a=p.parse_args();main(a.hours,a.seeds,a.patience)
