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
from datetime import datetime
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
EXPANDED_ROOT = ROOT.parent / 'flex2-expanded'


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

    def forward(self, condition, reference_condition, reference):
        fused_condition=torch.cat([condition,reference_condition,condition-reference_condition],dim=1)
        z=torch.cat([self.ref(reference),self.condition(fused_condition).reshape(-1,64,16,16)],1)
        z=self.fuse(z)
        for layer in self.up:
            z=layer(F.interpolate(z,scale_factor=2,mode='bilinear',align_corners=False))
        return (reference + .25*torch.tanh(self.out(z))).clamp(0,1)


def load_verified(dataset_root=EXPANDED_ROOT):
    dataset_root=Path(dataset_root)
    data=np.load(dataset_root/'prepared.npz');manifest=json.loads((dataset_root/'manifest.json').read_text())
    evidence_path=dataset_root/'features.csv'
    raw=evidence_path.read_bytes();reader=csv.DictReader(raw.decode('utf-8-sig').splitlines());rows={r['run_id']:r for r in reader}
    if len(set(data['groups'].tolist()))!=len(data['groups']):
        raise ValueError('Image library must have unique run IDs')
    if manifest['fields']!=FIELDS or not np.isfinite(data['features']).all():raise ValueError('Unexpected/malformed base feature schema')
    fiber=[];power=[];power_missing=[];duration=[];duration_missing=[];stage=[];campaign=[];shutter=[];gain=[];keep=[];excluded=[]
    records={r['run']:r for r in manifest['records']}
    for i,run in enumerate(data['groups'].tolist()):
        row=rows.get(run)
        if not row or row['settings_status']!='exact_run_match':
            excluded.append(run);continue
        if row['split']!=str(data['splits'][i]):raise ValueError(f'Split mismatch for {run}; refusing leakage-prone run')
        if row['fiber_usage_flag'] not in ('True','False'):raise ValueError(f'Unknown fiber setting for {run}')
        record=records.get(run)
        if record is None:raise ValueError(f'Image manifest missing event/camera record for {run}')
        keep.append(i)
        fiber.append(float(row['fiber_usage_flag']=='True'))
        try:
            on_time=float(row['igniter_on_time_s']);on_time_ok=row['igniter_on_time_status']=='exact_run_match' and math.isfinite(on_time) and on_time>0
        except (KeyError,TypeError,ValueError):on_time_ok=False;on_time=0.
        duration.append(on_time if on_time_ok else np.nan);duration_missing.append(float(not on_time_ok))
        ignition=datetime.fromisoformat(record['ignition'])
        frame_times=sorted(datetime.fromisoformat(m['timestamp']) for m in record['members'])
        middle=(frame_times[(len(frame_times)-1)//2]+(frame_times[len(frame_times)//2]-frame_times[(len(frame_times)-1)//2])/2)
        stage.append(float((middle-ignition).total_seconds()))
        campaign.append(record['category'])
        settings=record.get('camera_settings') or [{}]
        shutter.append(settings[0].get('SHUTTER_POSITION(N/A)','unknown'))
        gain.append(settings[0].get('GAIN_POSITION(N/A)','unknown'))
        try:
            value=float(row['igniter_power_setting_w']);present=math.isfinite(value) and value>0
        except (TypeError,ValueError):present=False;value=0.
        power.append(value if present else np.nan);power_missing.append(float(not present))
    if len(keep)<30:raise ValueError(f'Only {len(keep)} image targets have verified apparatus settings')
    data={k:data[k][keep] for k in data.files};data['excluded_unverified_settings_ids']=excluded
    data['campaign']=np.asarray(campaign);data['stage_since_igniter_s']=np.asarray(stage)
    cats={'campaign':campaign,'camera_shutter_code':shutter,'camera_gain_code':gain}
    columns=[np.asarray([float(v==level) for v in values],dtype='float32') for name,values in cats.items() for level in sorted(set(values[i] for i in range(len(keep)) if data['splits'][i]=='train'))]
    names=['pressure_kpa','temperature_c','fiber_usage_flag','igniter_power_setting_w','power_missing_flag','igniter_on_time_s','igniter_on_time_missing_flag','seconds_since_igniter_on']
    names += [f'{name}={level}' for name,values in cats.items() for level in sorted(set(values[i] for i in range(len(keep)) if data['splits'][i]=='train'))]
    x=np.column_stack([data['features'],fiber,power,power_missing,duration,duration_missing,stage,*columns]).astype('float32')
    split=data['splits'];train=np.where(split=='train')[0]
    median=np.nanmedian(x[train],axis=0);median=np.nan_to_num(median,nan=0.)
    missing=~np.isfinite(x);x[missing]=np.take(median,np.where(missing)[1])
    low=x[train].min(0);scale=np.maximum(x[train].max(0)-low,1e-6)
    x=np.clip((x-low)/scale,-.25,1.25).astype('float32')
    data['feature_names']=names
    # Derive training-only nearest references. A training target cannot retrieve itself;
    # validation/test references come only from training runs.
    refs=[];fuel=data['fuels'];groups=data['groups']
    for i in range(len(x)):
        candidates=train[(fuel[train]==fuel[i]) & (groups[train]!=groups[i])]
        if not len(candidates):raise ValueError(f'No leakage-safe reference for {groups[i]}')
        dist=np.mean((x[candidates]-x[i])**2,axis=1)
        refs.append(int(candidates[np.argmin(dist)]))
    return data,manifest,x,np.asarray(refs),hashlib.sha256(raw).hexdigest()


def main(hours,seed_count,patience,dataset_root=EXPANDED_ROOT,output_dir=OUT):
    if not 0<hours<=8:raise ValueError('--hours must be between 0 and 8')
    dataset_root=Path(dataset_root);output_dir=Path(output_dir)
    data,manifest,x,refs,evidence_hash=load_verified(dataset_root)
    output_dir.mkdir(parents=True,exist_ok=True);torch.set_num_threads(max(1,min(4,os.cpu_count() or 1)))
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    start=time.monotonic();deadline=start+hours*3600;log=output_dir/'metrics.jsonl'
    images=torch.tensor(data['images'],device=device).permute(0,3,1,2).float()/255
    masks=torch.tensor(data['masks'],device=device).unsqueeze(1).float()
    cond=torch.tensor(x,device=device);refs=torch.tensor(refs,device=device)
    splits={s:np.where(data['splits']==s)[0] for s in ('train','validation','test')}
    metadata={'device':str(device),'hours':hours,'target_count':len(x),'features':data['feature_names'],'feature_caveats':'Camera shutter/gain values are categorical raw device codes, not calibrated exposure measurements. Campaign one-hot may act as a proxy for acquisition conditions. Igniter on-time is exact-run event-summary metadata, not measured delivered energy.','dataset_root':str(dataset_root),'manifest_sha256':hashlib.sha256((dataset_root/'manifest.json').read_bytes()).hexdigest(),'evidence_sha256':evidence_hash,'target_ids':data['groups'].tolist(),'split_ids':{k:data['groups'][v].tolist() for k,v in splits.items()},'selection':'validation foreground-weighted MAE; test split evaluated after training','reference_pool':'train only; self-run excluded','model':'small retrieval-conditioned CNN; query, reference features, feature difference, and reference image'}
    (output_dir/'run.json').write_text(json.dumps(metadata,indent=2))
    run_no=0
    while time.monotonic()<deadline and run_no<seed_count:
        seed=42+run_no;random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
        net=RetrievalConditioned(cond.shape[1]*3).to(device);opt=torch.optim.AdamW(net.parameters(),lr=5e-4,weight_decay=1e-3)
        best=math.inf;best_state=None;stale=0;epoch=0
        while time.monotonic()<deadline and stale<patience:
            epoch+=1;net.train();order=np.random.permutation(splits['train']);losses=[]
            for ids in np.array_split(order,max(1,math.ceil(len(order)/8))):
                ix=torch.as_tensor(ids,device=device);pred=net(cond[ix],cond[refs[ix]],images[refs[ix]])
                err=(pred-images[ix]).abs();loss=err.mean()+.5*(err*masks[ix]).sum()/(3*masks[ix].sum()).clamp(min=1)+.3*F.l1_loss(F.adaptive_avg_pool2d(pred,32),F.adaptive_avg_pool2d(images[ix],32))
                if not torch.isfinite(loss):raise FloatingPointError('Non-finite training loss; run stopped')
                opt.zero_grad(set_to_none=True);loss.backward();grad=nn.utils.clip_grad_norm_(net.parameters(),2.)
                if not torch.isfinite(grad):raise FloatingPointError('Non-finite gradient; run stopped')
                opt.step();losses.append(float(loss.detach()))
            net.eval()
            with torch.inference_mode():
                vi=torch.as_tensor(splits['validation'],device=device);vp=net(cond[vi],cond[refs[vi]],images[refs[vi]])
                val=metrics(vp,images[vi],masks[vi]);score=val['weighted_mae']
            if not math.isfinite(score):raise FloatingPointError('Non-finite validation metric; run stopped')
            improved=score<best
            if improved:
                best=score;stale=0;best_state={k:v.detach().cpu().clone() for k,v in net.state_dict().items()}
                tmp=output_dir/f'.seed-{seed}.tmp.pt';torch.save({'state':best_state,'seed':seed,'epoch':epoch,'validation':val,'metadata':metadata},tmp);tmp.replace(output_dir/f'seed-{seed}-best.pt')
            else:stale+=1
            rec={'seed':seed,'epoch':epoch,'train_loss':float(np.mean(losses)),'validation':val,'best_validation_weighted_mae':best,'stale_epochs':stale,'seconds':time.monotonic()-start,'gpu_memory_bytes':torch.cuda.max_memory_allocated() if device.type=='cuda' else None}
            with log.open('a') as f:f.write(json.dumps(rec,allow_nan=False)+'\n')
            print(json.dumps(rec),flush=True)
            if device.type=='cuda' and torch.cuda.memory_reserved()>torch.cuda.get_device_properties(device).total_memory*.95:raise RuntimeError('GPU memory exceeds 95% stability limit')
        if best_state:
            net.load_state_dict(best_state);net.eval()
            with torch.inference_mode():
                ix=torch.as_tensor(splits['test'],device=device);pred=net(cond[ix],cond[refs[ix]],images[refs[ix]])
                hybrid_score=metrics(pred,images[ix],masks[ix])
                retrieval_score=metrics(images[refs[ix]],images[ix],masks[ix])
                train_ix=torch.as_tensor(splits['train'],device=device)
                mean_images=torch.stack([images[train_ix][torch.as_tensor(data['fuels'][splits['train']]==data['fuels'][i],device=device)].mean(0) for i in splits['test']])
                mean_score=metrics(mean_images,images[ix],masks[ix])
                base_net,base_saved=load_published();base_net=base_net.to(device)
                base_cond=encode(torch.tensor(data['features'][splits['test']],device=device),torch.tensor(data['fuels'][splits['test']],device=device),base_saved['low'].to(device),base_saved['scale'].to(device),len(base_saved['report']['fuels']))
                base_pred=torch.cat([base_net(batch)[0] for batch in base_cond.split(8)])
                base_score=metrics(base_pred,images[ix],masks[ix])
            out={'seed':seed,'selected_epoch':epoch-stale,'test_metrics':{'retrieval_conditioned_cnn':hybrid_score,'extended_feature_retrieval':retrieval_score,'same_fuel_training_mean':mean_score,'published_feature_only_cnn':base_score},'test_reference_ids':data['groups'][refs[splits['test']]].tolist()}
            (output_dir/f'seed-{seed}-test.json').write_text(json.dumps(out,indent=2,allow_nan=False))
        run_no+=1
    print(json.dumps({'finished_seeds':run_no,'elapsed_seconds':time.monotonic()-start,'deadline_seconds':hours*3600,'metrics_log':str(log),'artifacts':str(output_dir)},indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hours',type=float,default=8);p.add_argument('--seeds',type=int,default=3);p.add_argument('--patience',type=int,default=25);a=p.parse_args();main(a.hours,a.seeds,a.patience)
