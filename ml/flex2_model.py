"""Full-square FLEX-2 conditional CNN, with whole-test-point evaluation."""
import argparse
import copy
import hashlib
import json
import time

import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
from PIL import Image, ImageDraw

from flex2_data import ROOT, ART, FIELDS, SIZE
from spice_model import encode, metrics


class DropletCNN(nn.Module):
    def __init__(self,inputs):
        super().__init__()
        self.encode=nn.Sequential(nn.Linear(inputs,512),nn.SiLU(),nn.Linear(512,32*8*8),nn.SiLU())
        channels=[32,24,16,12,8,4]
        self.blocks=nn.ModuleList([nn.Sequential(nn.Conv2d(a,b,3,padding=1),nn.SiLU(),nn.Conv2d(b,b,3,padding=1),nn.SiLU()) for a,b in zip(channels,channels[1:])])
        self.conditions=nn.ModuleList([nn.Linear(inputs,b) for b in channels[1:]])
        self.output=nn.Conv2d(4,4,1);nn.init.constant_(self.output.bias,-3.)

    def forward(self,x):
        z=self.encode(x).reshape(-1,32,8,8)
        for block,condition in zip(self.blocks,self.conditions):
            z=block(F.interpolate(z,scale_factor=2,mode='bilinear',align_corners=False))+condition(x)[:,:,None,None]
        out=self.output(z);return out[:,:3].sigmoid(),out[:,3:4]


def nearest(features,fuels,query,fuel,scale,candidates):
    idx=np.array([int(i) for i in candidates if fuels[i]==fuel],dtype=int)
    if not len(idx):raise ValueError('No images for this fuel')
    distance=np.sqrt(np.mean(((features[idx]-query)/scale)**2,axis=1));order=np.argsort(distance,kind='stable')
    return idx[order],distance[order]


def run(epochs=250):
    if epochs<1:raise ValueError('epochs must be positive')
    started=time.perf_counter();torch.set_num_threads(2);torch.manual_seed(42);rng=np.random.default_rng(42)
    d=np.load(ROOT/'prepared.npz');m=json.loads((ROOT/'manifest.json').read_text())
    x=torch.tensor(d['features']);fuels=torch.tensor(d['fuels'],dtype=torch.long)
    y=torch.tensor(d['images']).permute(0,3,1,2).float()/255;mask=torch.tensor(d['masks']).unsqueeze(1).float()
    splits={s:np.where(d['splits']==s)[0] for s in ['train','validation','test']};train=splits['train'];val=splits['validation']
    low=x[train].amin(0);scale=(x[train].amax(0)-low).clamp(min=1e-6);z=encode(x,fuels,low,scale,len(m['fuels']))
    net=DropletCNN(z.shape[1]);opt=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.0001)
    best=float('inf');best_state=None;best_epoch=0;history=[]
    for epoch in range(epochs):
        net.train()
        for batch in np.array_split(rng.permutation(train),max(1,int(np.ceil(len(train)/8)))):
            p,l=net(z[batch]);target=y[batch];bmask=mask[batch];error=(p-target).abs()
            loss=error.mean()+.5*(error*bmask).sum()/(3*bmask.sum()).clamp(min=1)
            loss=loss+.3*F.l1_loss(F.adaptive_avg_pool2d(p,32),F.adaptive_avg_pool2d(target,32))
            loss=loss+.01*F.binary_cross_entropy_with_logits(l,bmask,pos_weight=torch.tensor(4.))
            opt.zero_grad();loss.backward();nn.utils.clip_grad_norm_(net.parameters(),5.);opt.step()
        if epoch==0 or (epoch+1)%5==0:
            net.eval()
            with torch.inference_mode():
                p=torch.cat([net(z[b])[0] for b in np.array_split(val,max(1,int(np.ceil(len(val)/8))))])
                score=metrics(p,y[val],mask[val])['weighted_mae']
            history.append(dict(epoch=epoch+1,validation_weighted_mae=score))
            if score<best:best=score;best_state=copy.deepcopy(net.state_dict());best_epoch=epoch+1
            if (epoch+1)%10==0:print('epoch',epoch+1,'validation',round(score,6),'best',best_epoch,flush=True)
            if epoch+1-best_epoch>=50:break
    net.load_state_dict(best_state);net.eval();ART.mkdir(parents=True,exist_ok=True)
    report=dict(version='flex2-rgb-v2',source='PSI-68',fields=FIELDS,fuels=m['fuels'],resolution=SIZE,
        parameters=sum(p.numel() for p in net.parameters()),seed=42,counts=m['counts'],
        groups={s:d['groups'][idx].tolist() for s,idx in splits.items()},selected_epoch=best_epoch,
        epochs_completed=epoch+1,max_epochs=epochs,selection='Minimum validation global MAE plus 0.5 foreground MAE; test evaluated after selection',
        dataset_sha256=hashlib.sha256((ROOT/'prepared.npz').read_bytes()).hexdigest(),
        architecture='Feature-conditioned convolutional decoder, native full 256x256 RGB; no SPICE checkpoint or mean-image residual',
        features_note=m['features_note'],stage=m['stage'],preprocessing=m['preprocessing'],history=history,evaluation={},
        qualified_for_promotion=False,
        limitation='Experimental feature-conditioned imagery only. Missing per-run oxygen/droplet-size labels, camera differences, weak masks and small trial splits prevent physical-accuracy or causal claims. Temperature variation may be a nuisance correlate.')
    for s,idx in splits.items():
        with torch.inference_mode():
            p=torch.cat([net(z[b])[0] for b in np.array_split(idx,max(1,int(np.ceil(len(idx)/8))))])
        mean=torch.stack([y[train[d['fuels'][train]==d['fuels'][i]]].mean(0) for i in idx])
        refs=[nearest(d['features'],d['fuels'],d['features'][i],d['fuels'][i],scale.numpy(),train)[0][0] for i in idx]
        report['evaluation'][s]=dict(cnn=metrics(p,y[idx],mask[idx]),same_fuel_mean=metrics(mean,y[idx],mask[idx]),training_only_retrieval=metrics(y[refs],y[idx],mask[idx]))
        canvas=Image.new('RGB',(3*SIZE,len(idx)*(SIZE+24)));draw=ImageDraw.Draw(canvas)
        for j,i in enumerate(idx):
            for col,array in enumerate([y[i],p[j],y[refs[j]]]):
                canvas.paste(Image.fromarray(np.uint8(array.permute(1,2,0).numpy().clip(0,1)*255)),(col*SIZE,j*(SIZE+24)))
                draw.text((col*SIZE,j*(SIZE+24)+SIZE),[str(d['groups'][i]),'CNN','Training-only retrieval'][col],fill='white')
        canvas.save(ART/(s+'-comparison.jpg'))
    sensitivity=[]
    with torch.inference_mode():
        for fuel,name in enumerate(m['fuels']):
            idx=train[d['fuels'][train]==fuel];base=x[idx].median(0).values
            for j,key in enumerate(FIELDS):
                a=base.clone();b=base.clone();a[j]=x[idx,j].min();b[j]=x[idx,j].max()
                if a[j]==b[j]:continue
                p,_=net(encode(torch.stack([a,b]),torch.tensor([fuel,fuel]),low,scale,len(m['fuels'])))
                sensitivity.append(dict(fuel=name,feature=key,low=float(a[j]),high=float(b[j]),mean_absolute_pixel_change=float((p[0]-p[1]).abs().mean()),maximum_pixel_change=float((p[0]-p[1]).abs().max())))
    report['feature_sensitivity']=sensitivity;report['training_seconds']=time.perf_counter()-started
    torch.save(dict(state=best_state,low=low,scale=scale,report=report),ART/'selected.pt')
    (ART/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='history'},indent=2),flush=True)


def load():
    saved=torch.load(ART/'selected.pt',map_location='cpu',weights_only=True)
    net=DropletCNN(len(FIELDS)+len(saved['report']['fuels']));net.load_state_dict(saved['state']);net.eval();return net,saved


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--epochs',type=int,default=250);run(p.parse_args().epochs)
