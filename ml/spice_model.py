"""Conditional convolutional generator and same-fuel nearest-condition baseline."""
import argparse
import copy
import json
import time

import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
from PIL import Image, ImageDraw

from spice_data import ROOT, ART, SIZE, FIELDS


class FlameCNN(nn.Module):
    """Features only -> learned spatial field -> native 256px RGB and weak mask."""
    def __init__(self, inputs):
        super().__init__()
        self.encode = nn.Sequential(nn.Linear(inputs,1024),nn.SiLU(),nn.Linear(1024,64*2*8),nn.SiLU())
        channels=[64,48,32,24,16,8]
        self.blocks=nn.ModuleList([
            nn.Sequential(nn.Conv2d(a,b,3,padding=1),nn.SiLU(),nn.Conv2d(b,b,3,padding=1),nn.SiLU())
            for a,b in zip(channels,channels[1:])])
        self.condition=nn.ModuleList([nn.Linear(inputs,b) for b in channels[1:]])
        self.output=nn.Conv2d(8,4,1)
        nn.init.constant_(self.output.bias,-3.)

    def forward(self,x):
        z=self.encode(x).reshape(-1,64,2,8)
        for block,condition in zip(self.blocks,self.condition):
            z=F.interpolate(z,scale_factor=2,mode='bilinear',align_corners=False)
            z=block(z)+condition(x)[:,:,None,None]
        out=self.output(z)
        # All prepared images share a 38px camera strip within a black square.
        # Learn a 64x256 band; fixed zero padding has no trainable information.
        return F.pad(out[:,:3].sigmoid(),(0,0,96,96)),F.pad(out[:,3:4],(0,0,96,96),value=-20.)


def encode(features,fuels,low,scale,nfuels):
    return torch.cat(((features-low)/scale,F.one_hot(fuels,nfuels).float()),dim=1)


def nearest(features,fuels,query,fuel,scale,candidates):
    """Same fuel, then exact nozzle when recorded, then normalized flow distance."""
    indices=np.array([int(i) for i in candidates if fuels[i]==fuel],dtype=int)
    if not len(indices):
        raise ValueError('No reference images for requested fuel')
    exact_nozzle=np.isclose(features[indices,0],query[0],atol=1e-5,rtol=0)
    if exact_nozzle.any():indices=indices[exact_nozzle]
    distances=np.mean(((features[indices]-query)/scale)**2,axis=1)
    order=np.argsort(distances,kind='stable')
    return indices[order],np.sqrt(distances[order])


def metrics(pred,target,mask):
    error=(pred-target).abs()
    fg=mask.expand(-1,3,-1,-1)
    guessed=pred.max(1,keepdim=True).values>40/255
    actual=mask.bool()
    union=(guessed|actual).sum((1,2,3)).clamp(min=1)
    return dict(rgb_mae=error.mean().item(),rgb_mse=((pred-target)**2).mean().item(),
        foreground_mae=(error*fg).sum().item()/max(fg.sum().item(),1),
        weak_mask_iou=((guessed&actual).sum((1,2,3))/union).mean().item(),
        weighted_mae=error.mean().item()+.5*(error*fg).sum().item()/max(fg.sum().item(),1))


def run(epochs=250):
    if epochs<1:raise ValueError('epochs must be positive')
    started=time.perf_counter();torch.set_num_threads(2);torch.manual_seed(42)
    rng=np.random.default_rng(42)
    d=np.load(ROOT/'prepared.npz');manifest=json.loads((ROOT/'manifest.json').read_text())
    x=torch.tensor(d['features']);fuel=torch.tensor(d['fuels'],dtype=torch.long)
    y=torch.tensor(d['images']).permute(0,3,1,2).float()/255
    mask=torch.tensor(d['masks']).unsqueeze(1).float()
    selections={s:np.where(d['splits']==s)[0] for s in ['train','validation','test']}
    train=selections['train'];val=selections['validation']
    low=x[train].amin(0);scale=(x[train].amax(0)-low).clamp(min=1e-6)
    z=encode(x,fuel,low,scale,len(manifest['fuels']))
    net=FlameCNN(z.shape[1]);opt=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.0001)
    best=float('inf');best_state=None;best_epoch=0;history=[]
    for epoch in range(epochs):
        net.train();loss_sum=0.
        for batch in np.array_split(rng.permutation(train),max(1,int(np.ceil(len(train)/8)))):
            p,l=net(z[batch]);target=y[batch];m=mask[batch]
            error=(p-target).abs()
            loss=error.mean()+.5*(error*m).sum()/(3*m.sum()).clamp(min=1)
            for size in [32,64]:
                loss=loss+.3*F.l1_loss(F.adaptive_avg_pool2d(p,size),F.adaptive_avg_pool2d(target,size))
            loss=loss+.01*F.binary_cross_entropy_with_logits(l,m,pos_weight=torch.tensor(8.))
            opt.zero_grad();loss.backward();nn.utils.clip_grad_norm_(net.parameters(),5.);opt.step()
            loss_sum+=loss.item()*len(batch)
        if epoch==0 or (epoch+1)%5==0:
            net.eval()
            with torch.inference_mode():
                preds=torch.cat([net(z[b])[0] for b in np.array_split(val,max(1,int(np.ceil(len(val)/8))))])
                score=metrics(preds,y[val],mask[val])['weighted_mae']
            history.append(dict(epoch=epoch+1,train_loss=loss_sum/len(train),validation_weighted_mae=score))
            if score<best:
                best=score;best_state=copy.deepcopy(net.state_dict());best_epoch=epoch+1
            if (epoch+1)%10==0:print(f'epoch {epoch+1}: validation {score:.6f}; best {best_epoch}',flush=True)
            if epoch+1-best_epoch>=50:
                print('Validation early stopping',flush=True);break
    net.load_state_dict(best_state);net.eval();ART.mkdir(parents=True,exist_ok=True)
    report=dict(version='spice-conditional-v1',resolution=SIZE,parameters=sum(p.numel() for p in net.parameters()),
        fields=FIELDS,fuels=manifest['fuels'],counts=manifest['counts'],seed=42,
        selected_epoch=best_epoch,epochs_completed=epoch+1,max_epochs=epochs,
        selection='minimum validation foreground-weighted RGB MAE; test evaluated after checkpoint selection',
        split=manifest['split'],groups={s:sorted(set(d['groups'][idx].tolist())) for s,idx in selections.items()},
        ids={s:[manifest['records'][int(i)]['id'] for i in idx] for s,idx in selections.items()},
        dataset_sha256=__import__('hashlib').sha256((ROOT/'prepared.npz').read_bytes()).hexdigest(),
        mask_note='HSV image-derived proxy; not manually annotated or physically calibrated',
        architecture='feature MLP plus condition-injected convolutional decoder; native 64x256 camera band, fixed black padding to 256x256; no mean-image residual',
        qualified_for_promotion=False,evaluation={},history=history)
    for s,idx in selections.items():
        with torch.inference_mode():
            p=torch.cat([net(z[b])[0] for b in np.array_split(idx,max(1,int(np.ceil(len(idx)/8))))])
        means=torch.stack([y[train[fuel[train].numpy()==int(fuel[i])]].mean(0) for i in idx])
        refs=[nearest(d['features'],d['fuels'],d['features'][i],int(fuel[i]),scale.numpy(),train)[0][0] for i in idx]
        report['evaluation'][s]=dict(cnn=metrics(p,y[idx],mask[idx]),same_fuel_mean=metrics(means,y[idx],mask[idx]),
            training_only_retrieval=metrics(y[refs],y[idx],mask[idx]))
        canvas=Image.new('RGB',(SIZE*3,(SIZE+24)*len(idx)));draw=ImageDraw.Draw(canvas)
        for j,i in enumerate(idx):
            for col,array in enumerate([y[i],p[j],y[refs[j]]]):
                image=Image.fromarray((array.permute(1,2,0).numpy().clip(0,1)*255).astype('uint8'))
                canvas.paste(image,(col*SIZE,j*(SIZE+24)))
                draw.text((col*SIZE,j*(SIZE+24)+SIZE),['Recorded '+manifest['records'][i]['id'],'CNN','Training-only retrieval'][col],fill='white')
        canvas.save(ART/f'{s}-comparison.jpg')
    sensitivity=[]
    with torch.inference_mode():
        for f,name in enumerate(manifest['fuels']):
            indices=train[d['fuels'][train]==f];base=x[indices].median(0).values
            for j,key in enumerate(FIELDS):
                a=base.clone();b=base.clone();a[j]=x[indices,j].min();b[j]=x[indices,j].max()
                if a[j]==b[j]:continue
                pair=torch.stack([a,b]);p,_=net(encode(pair,torch.tensor([f,f]),low,scale,len(manifest['fuels'])))
                diff=(p[0]-p[1]).abs()
                sensitivity.append(dict(fuel=name,feature=key,low=float(a[j]),high=float(b[j]),
                    mean_absolute_pixel_change=float(diff.mean()),maximum_pixel_change=float(diff.max())))
    report['feature_sensitivity']=sensitivity
    report['training_seconds']=time.perf_counter()-started
    report['limitation']='Small selected still-image subset; camera settings/stage may confound features. Unknown settings/saturation flags remain. Predictions are experimental images, not heat flux, temperature or validated fire forecasts.'
    torch.save(dict(state=best_state,low=low,scale=scale,report=report),ART/'selected.pt')
    (ART/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ['history','ids','groups']},indent=2),flush=True)


def load():
    saved=torch.load(ART/'selected.pt',map_location='cpu',weights_only=True)
    net=FlameCNN(len(FIELDS)+len(saved['report']['fuels']));net.load_state_dict(saved['state']);net.eval()
    return net,saved


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--epochs',type=int,default=250);run(p.parse_args().epochs)
