"""Generate RGB and an unconstrained spatial flame mask from multiscale references."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

from flex2_overnight import load_verified
from flex2_continuous import soft_references,atomic_json
from flex2_shape import aligned_data,gradients


class GeometryHybrid(nn.Module):
    """Multiscale latent retrieval; no reference RGB skip, warp, or fixed silhouette."""
    def __init__(self,features):
        super().__init__()
        self.encoders=nn.ModuleList([nn.Sequential(nn.Conv2d(a,b,4,2,1),nn.SiLU(),nn.Conv2d(b,b,3,padding=1),nn.SiLU()) for a,b in [(3,8),(8,16),(16,32)]])
        self.condition=nn.Sequential(nn.Linear(features*3,128),nn.SiLU())
        self.seed=nn.Linear(128,32*8*8)
        self.blocks=nn.ModuleList([nn.Conv2d(a,b,3,padding=1) for a,b in [(64,32),(48,16),(24,8),(8,8)]])
        self.modulations=nn.ModuleList([nn.Linear(128,2*b) for b in [32,16,8,8]])
        self.head=nn.Conv2d(8,4,3,padding=1)
        nn.init.constant_(self.head.bias,-2.)

    def encode_references(self,images):
        outputs=[];z=images
        for encoder in self.encoders:z=encoder(z);outputs.append(z)
        return outputs

    def decode(self,query,reference_features,pyramid):
        condition=self.condition(torch.cat([query,reference_features,query-reference_features],1))
        z=self.seed(condition).reshape(-1,32,8,8)
        for index,(block,modulate) in enumerate(zip(self.blocks,self.modulations)):
            size=[32,64,128,256][index];z=F.interpolate(z,size=size,mode='bilinear',align_corners=False)
            if index<3:z=torch.cat([z,pyramid[2-index]],1)
            z=block(z);gain,bias=modulate(condition).chunk(2,1)
            z=F.silu(z*(1+.2*gain[:,:,None,None])+bias[:,:,None,None])
        output=self.head(z);mask_logits=output[:,3:4]
        # Separate probabilities for geometry; no threshold in the RGB path.
        rgb=output[:,:3].sigmoid()*mask_logits.sigmoid()
        return rgb,mask_logits


def objective(rgb,logits,target,mask):
    error=(rgb-target).abs();image=error.mean()+1.5*(error*mask).sum()/(3*mask.sum()).clamp(min=1)
    # Include bright saturated regions omitted by the original colour-only mask.
    probability=logits.sigmoid()
    dice=1-(2*(probability*mask).sum()+1)/(probability.sum()+mask.sum()+1)
    segmentation=F.binary_cross_entropy_with_logits(logits,mask,pos_weight=torch.tensor(3.))+dice
    gx,gy=gradients(rgb);tx,ty=gradients(target)
    edge=(gx-tx).abs().mean()+(gy-ty).abs().mean()
    # Laplacian difference gives high-frequency structure an explicit penalty.
    lap=lambda x:x-F.avg_pool2d(x,5,1,2)
    detail=(lap(rgb)-lap(target)).abs().mean()
    return image+4*edge+2*detail+.15*segmentation,dict(rgb=image,edge=edge,detail=detail,mask=segmentation)


def train(dataset,out,epochs,temperature=.002,resume=None,threads=4):
    if epochs<1 or not np.isfinite(temperature) or temperature<=0 or threads<1:raise ValueError('Use positive epochs, temperature and thread count')
    dataset=Path(dataset);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    if not (out.parent/'expanded').exists():(out.parent/'expanded').symlink_to(dataset.resolve(),target_is_directory=True)
    d,m,x,_,evidence=load_verified(dataset);torch.set_num_threads(threads);torch.manual_seed(43);rng=np.random.default_rng(43)
    raw,masks=aligned_data(d['images'],d['masks']);images=torch.tensor(raw).permute(0,3,1,2).float()/255
    masks=torch.maximum(torch.tensor(masks).unsqueeze(1),((images.max(1,keepdim=True).values>.35).float()))
    conditions=torch.tensor(x);fuels=torch.tensor(d['fuels']);net=GeometryHybrid(x.shape[1]);optimizer=torch.optim.AdamW(net.parameters(),lr=4e-4,weight_decay=1e-3)
    start=0
    if resume:
        saved=torch.load(resume,map_location='cpu',weights_only=True)
        if saved['metadata']['architecture']!='multiscale-geometry-v1' or saved['metadata']['features']!=d['feature_names'] or saved['metadata']['target_ids']!=d['groups'].tolist() or saved['metadata']['evidence_sha256']!=evidence or saved['metadata']['manifest_sha256']!=hashlib.sha256((dataset/'manifest.json').read_bytes()).hexdigest():raise ValueError('Resume architecture/schema/data mismatch')
        net.load_state_dict(saved['state']);optimizer.load_state_dict(saved['optimizer']);start=saved['epoch']
    metadata=dict(architecture='multiscale-geometry-v1',features=d['feature_names'],target_ids=d['groups'].tolist(),temperature=temperature,evidence_sha256=evidence,manifest_sha256=hashlib.sha256((dataset/'manifest.json').read_bytes()).hexdigest(),preprocessing=dict(low=d['feature_low'].tolist(),scale=d['feature_scale'].tolist()),independent_evaluation=False,mask_note='Weak image-derived geometry plus bright-source regions; not calibrated flame boundaries',epochs=epochs,seed=43,continued_from_epoch=start)
    atomic_json(out/'run.json',metadata)
    for epoch in range(start+1,start+epochs+1):
        with torch.no_grad():
            parts=[net.encode_references(b) for b in images.split(8)]
            banks=[torch.cat([p[k] for p in parts]) for k in range(3)]
        logs=[]
        for ids in np.array_split(rng.permutation(len(x)),int(np.ceil(len(x)/4))):
            ix=torch.tensor(ids);weights=soft_references(conditions[ix],conditions,fuels,fuels[ix],ix,temperature)
            pyramid=[torch.einsum('bn,nchw->bchw',weights,bank) for bank in banks]
            rgb,logits=net.decode(conditions[ix],weights@conditions,pyramid)
            loss,terms=objective(rgb,logits,images[ix],masks[ix])
            # Auxiliary reconstruction trains the shared encoder on supervised targets.
            # Main retrieval prediction above always excludes the target's own run.
            reconstruction,aux_mask=net.decode(conditions[ix],conditions[ix],net.encode_references(images[ix]))
            aux,_=objective(reconstruction,aux_mask,images[ix],masks[ix]);total=loss+.2*aux
            if not torch.isfinite(total):raise FloatingPointError('Nonfinite loss')
            optimizer.zero_grad(set_to_none=True);total.backward();norm=nn.utils.clip_grad_norm_(net.parameters(),2.)
            if not torch.isfinite(norm):raise FloatingPointError('Nonfinite gradient')
            optimizer.step();logs.append([float(total.detach())]+[float(v.detach()) for v in terms.values()])
        mean=np.mean(logs,axis=0);row=dict(epoch=epoch,training_loss=float(mean[0]),**{k:float(mean[j+1]) for j,k in enumerate(terms)},independent_evaluation=False)
        with (out/'metrics.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        tmp=out/'checkpoint.tmp.pt';torch.save(dict(state=net.state_dict(),optimizer=optimizer.state_dict(),metadata=metadata,seed=43,epoch=epoch),tmp);tmp.replace(out/'final.pt');print(json.dumps(row),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--epochs',type=int,default=30);p.add_argument('--temperature',type=float,default=.002);p.add_argument('--resume',type=Path);p.add_argument('--threads',type=int,default=4);a=p.parse_args();train(a.dataset,a.out,a.epochs,a.temperature,a.resume,a.threads)
