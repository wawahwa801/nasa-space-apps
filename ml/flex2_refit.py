"""Fit all eligible verified runs for a demo; no held-out evaluation is produced."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

from flex2_overnight import load_verified, RetrievalConditioned


def refit(source,epochs=8,seed=43):
    if epochs<1:raise ValueError('epochs must be positive')
    source=Path(source);stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    destination=source.parent/f'all-runs-refit-{stamp}';dataset=destination/'expanded';dataset.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((source/'expanded/manifest.json').read_text())
    data=np.load(source/'expanded/prepared.npz')
    arrays={k:data[k] for k in data.files};arrays['splits']=np.asarray(['train']*len(arrays['groups']))
    np.savez_compressed(dataset/'prepared.npz',**arrays)
    for record in manifest['records']:record['split']='train'
    manifest['counts']['splits']={'train':len(arrays['groups']),'validation':0,'test':0}
    manifest['split']='All eligible verified runs used for final demo fitting; no independent evaluation.'
    (dataset/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    with (source/'expanded/features.csv').open(newline='') as f:
        reader=csv.DictReader(f);columns=reader.fieldnames;rows=list(reader)
    for row in rows:row['split']='train'
    with (dataset/'features.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns,lineterminator='\n');writer.writeheader();writer.writerows(rows)
    d,m,x,refs,evidence_hash=load_verified(dataset)
    assert all(d['groups'][i]!=d['groups'][j] for i,j in enumerate(refs))
    torch.set_num_threads(4);torch.manual_seed(seed);rng=np.random.default_rng(seed)
    net=RetrievalConditioned(x.shape[1]*3);opt=torch.optim.AdamW(net.parameters(),lr=5e-4,weight_decay=1e-3)
    conditions=torch.tensor(x);images=torch.tensor(d['images']).permute(0,3,1,2).float()/255
    masks=torch.tensor(d['masks']).unsqueeze(1).float()
    training=destination/'training';training.mkdir()
    metadata={'fit':'all eligible runs','source':str(source),'target_ids':d['groups'].tolist(),
              'excluded_ids':d['excluded_unverified_settings_ids'],'features':d['feature_names'],
              'epochs':epochs,'seed':seed,'epoch_choice':'8 epochs chosen from prior validation-selected seed 43; no new validation/test tuning',
              'reference_policy':'all eligible training runs, same fuel, self-run excluded',
              'independent_evaluation':False,'evidence_sha256':evidence_hash}
    (training/'run.json').write_text(json.dumps(metadata,indent=2)+'\n')
    for epoch in range(1,epochs+1):
        net.train();losses=[]
        for ids in np.array_split(rng.permutation(len(x)),int(np.ceil(len(x)/8))):
            p=net(conditions[ids],conditions[refs[ids]],images[refs[ids]])
            error=(p-images[ids]).abs()
            loss=error.mean()+.5*(error*masks[ids]).sum()/(3*masks[ids].sum()).clamp(min=1)
            loss=loss+.3*F.l1_loss(F.adaptive_avg_pool2d(p,32),F.adaptive_avg_pool2d(images[ids],32))
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite loss')
            opt.zero_grad(set_to_none=True);loss.backward();gradient=nn.utils.clip_grad_norm_(net.parameters(),2.)
            if not torch.isfinite(gradient):raise FloatingPointError('Nonfinite gradient')
            opt.step();losses.append(float(loss.detach()))
        row={'epoch':epoch,'training_loss':float(np.mean(losses)),'targets':len(x),'independent_evaluation':False}
        with (training/'metrics.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        temporary=training/'checkpoint.tmp.pt'
        torch.save({'state':net.state_dict(),'epoch':epoch,'seed':seed,'metadata':metadata},temporary)
        temporary.replace(training/'final.pt');print(json.dumps(row),flush=True)
    print('Final all-run fit: '+str(destination),flush=True)
    return destination


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--epochs',type=int,default=8);a=p.parse_args();refit(a.source,a.epochs)
