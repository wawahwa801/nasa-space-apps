"""Structure-preserving continuous hybrid prototype, trained on all verified runs."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

from flex2_overnight import load_verified
from flex2_continuous import soft_references,atomic_json
from flame_display import centre_flame


def aligned_data(images,masks):
    aligned=[];aligned_masks=[]
    for im,mask in zip(images,masks):
        result,info=centre_flame(im);dx,dy=info['shift_pixels']
        aligned.append(result)
        aligned_masks.append(cv2.warpAffine(mask.astype('float32'),np.float32([[1,0,dx],[0,1,dy]]),(256,256),flags=cv2.INTER_NEAREST))
    return np.array(aligned),np.array(aligned_masks)


class ShapeHybrid(nn.Module):
    """Predict smooth spatial transport and RGB corrections from aligned references."""
    def __init__(self,features):
        super().__init__()
        self.condition=nn.Sequential(nn.Linear(features*3,128),nn.SiLU(),nn.Linear(128,16*8*8),nn.SiLU())
        self.conv=nn.Sequential(nn.Conv2d(19,32,3,padding=1),nn.SiLU(),nn.Conv2d(32,32,3,padding=1),nn.SiLU(),nn.Conv2d(32,16,3,padding=1),nn.SiLU(),nn.Conv2d(16,6,3,padding=1))
        nn.init.zeros_(self.conv[-1].weight);nn.init.zeros_(self.conv[-1].bias)
        coordinates=torch.linspace(-1,1,256);yy,xx=torch.meshgrid(coordinates,coordinates,indexing='ij')
        self.register_buffer('grid',torch.stack([xx,yy],-1).unsqueeze(0))

    def forward(self,query,reference_features,reference):
        condition=self.condition(torch.cat([query,reference_features,query-reference_features],1)).reshape(-1,16,8,8)
        z=torch.cat([F.interpolate(condition,size=64,mode='bilinear',align_corners=False),F.interpolate(reference,size=64,mode='area')],1)
        output=F.interpolate(self.conv(z),size=256,mode='bilinear',align_corners=False)
        flow=output[:,:2].tanh()*(32/127.5)
        warped=F.grid_sample(reference,self.grid+flow.permute(0,2,3,1),align_corners=True,padding_mode='zeros')
        rgb=(torch.logit(warped.clamp(.001,.999))+output[:,2:5]).sigmoid()
        return rgb,output[:,5:6],flow


def gradients(x):return x[:,:,:,1:]-x[:,:,:,:-1],x[:,:,1:,:]-x[:,:,:-1,:]


def train(dataset,out,epochs=30):
    if epochs<1:raise ValueError('epochs must be positive')
    dataset=Path(dataset);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    if out.name=='training' and not (out.parent/'expanded').exists():
        (out.parent/'expanded').symlink_to(dataset.resolve(),target_is_directory=True)
    d,m,x,_,evidence_hash=load_verified(dataset);torch.set_num_threads(2);torch.manual_seed(43);rng=np.random.default_rng(43)
    arrays,masks=aligned_data(d['images'],d['masks'])
    images=torch.tensor(arrays).permute(0,3,1,2).float()/255;masks=torch.tensor(masks).unsqueeze(1)
    conditions=torch.tensor(x);fuels=torch.tensor(d['fuels']);model=ShapeHybrid(x.shape[1]);opt=torch.optim.AdamW(model.parameters(),lr=3e-4,weight_decay=1e-3)
    metadata=dict(architecture='aligned-soft-shape-v1',target_ids=d['groups'].tolist(),features=d['feature_names'],evidence_sha256=evidence_hash,manifest_sha256=hashlib.sha256((dataset/'manifest.json').read_bytes()).hexdigest(),temperature=.02,preprocessing=dict(low=d['feature_low'].tolist(),scale=d['feature_scale'].tolist()),alignment='Integer translation only, same shift for image and weak mask',independent_evaluation=False,epochs=epochs,seed=43)
    atomic_json(out/'run.json',metadata)
    for epoch in range(1,epochs+1):
        losses=[]
        for ids in np.array_split(rng.permutation(len(x)),int(np.ceil(len(x)/8))):
            ix=torch.tensor(ids);weights=soft_references(conditions[ix],conditions,fuels,fuels[ix],ix,.02)
            reference=torch.einsum('bn,nchw->bchw',weights,images)
            prediction,mask_logits,flow=model(conditions[ix],weights@conditions,reference)
            error=(prediction-images[ix]).abs();mask=masks[ix]
            rgb=error.mean()+.75*(error*mask).sum()/(3*mask.sum()).clamp(min=1)
            gx,gy=gradients(prediction);tx,ty=gradients(images[ix]);edge=(gx-tx).abs().mean()+(gy-ty).abs().mean()
            mask_loss=F.binary_cross_entropy_with_logits(mask_logits,mask,pos_weight=torch.tensor(4.))
            fx,fy=gradients(flow);loss=rgb+1.5*edge+.05*mask_loss+.01*(fx.abs().mean()+fy.abs().mean())
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite loss')
            opt.zero_grad(set_to_none=True);loss.backward();g=nn.utils.clip_grad_norm_(model.parameters(),2.)
            if not torch.isfinite(g):raise FloatingPointError('Nonfinite gradient')
            opt.step();losses.append([float(v.detach()) for v in (loss,rgb,edge,mask_loss)])
        row=dict(epoch=epoch,training_loss=float(np.mean(losses,0)[0]),rgb_loss=float(np.mean(losses,0)[1]),edge_loss=float(np.mean(losses,0)[2]),weak_mask_loss=float(np.mean(losses,0)[3]),independent_evaluation=False)
        with (out/'metrics.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        tmp=out/'checkpoint.tmp.pt';torch.save(dict(state=model.state_dict(),optimizer=opt.state_dict(),metadata=metadata,seed=43,epoch=epoch),tmp);tmp.replace(out/'final.pt');print(json.dumps(row),flush=True)
    return model


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--epochs',type=int,default=30);a=p.parse_args();train(a.dataset,a.out,a.epochs)
