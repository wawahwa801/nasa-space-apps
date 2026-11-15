"""Validation-selected, residual shape/RGB CNN for the BASS-only study."""
import argparse
import copy
import json

import cv2
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

from bass_study import WORK,ART,SIZE,FIELDS,VERSION


class StageCNN(nn.Module):
    def __init__(self,base_rgb,base_mask,inputs=3):
        super().__init__()
        self.register_buffer('base_rgb',base_rgb)
        self.register_buffer('base_mask_logits',torch.logit(base_mask.clamp(.001,.999)))
        self.encode=nn.Sequential(nn.Linear(inputs,32),nn.Tanh(),nn.Linear(32,16*8*8),nn.Tanh())
        channels=[16,16,8,8,4,4];layers=[]
        for a,b in zip(channels,channels[1:]):
            layers += [nn.Upsample(scale_factor=2,mode='bilinear',align_corners=False),nn.Conv2d(a,b,3,padding=1),nn.ReLU()]
        layers += [nn.Conv2d(4,4,3,padding=1)]
        self.decode=nn.Sequential(*layers)
        nn.init.zeros_(self.decode[-1].weight);nn.init.zeros_(self.decode[-1].bias)

    def forward(self,x):
        delta=self.decode(self.encode(x).reshape(-1,16,8,8))
        rgb=(self.base_rgb+.3*torch.tanh(delta[:,:3])).clamp(0,1)
        logits=self.base_mask_logits+delta[:,3:4]
        return rgb,logits


def statistics(prediction,probability,target,mask):
    error=((prediction-target)**2).mean(1)
    guessed=probability[:,0]>=.5;actual=mask[:,0]>=.5
    intersection=(guessed&actual).sum((1,2)).float();union=(guessed|actual).sum((1,2)).float().clamp(min=1)
    area=(guessed.sum((1,2))-actual.sum((1,2))).abs().float()/(SIZE*SIZE)
    height=[]
    for a,b in zip(guessed,actual):
        def extent(m):
            ys=torch.where(m.any(1))[0]
            return (ys[-1]-ys[0]+1).item() if len(ys) else 0
        height.append(abs(extent(a)-extent(b))/SIZE)
    return dict(rgb_mse=error.mean().item(),flame_rgb_mse=error[actual].mean().item(),
        mask_iou=(intersection/union).mean().item(),area_absolute_fraction=area.mean().item(),
        height_absolute_fraction=float(np.mean(height)))


def run(epochs,work=WORK,art=ART,fields=FIELDS,version=VERSION,stage=None,mask_note=None):
    if epochs<1:raise ValueError('epochs must be positive')
    torch.set_num_threads(2)
    d=np.load(work/'prepared.npz');x=torch.from_numpy(d['features']);y=torch.from_numpy(d['images']).permute(0,3,1,2).float()/255
    masks=torch.from_numpy(d['masks']).float().unsqueeze(1)
    train=d['splits']=='train';val=d['splits']=='validation';test=d['splits']=='test'
    low=x[train].amin(0);scale=(x[train].amax(0)-low).clamp(min=1e-6);z=(x-low)/scale
    mean_rgb=y[train].mean(0,keepdim=True);mean_mask=masks[train].mean(0,keepdim=True)
    best=None;candidates=[]
    # Both objectives and selection rule are fixed before inspecting any test result.
    for name,mask_weight in [('rgb-focused',.001),('shape-assisted',.01)]:
        torch.manual_seed(42);net=StageCNN(mean_rgb,mean_mask,len(fields));opt=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.001)
        best_score=float('inf');best_state=None;best_epoch=0
        for epoch in range(epochs):
            net.train();rgb,logits=net(z[train])
            loss=((rgb-y[train])**2).mean()+mask_weight*F.binary_cross_entropy_with_logits(logits,masks[train],pos_weight=torch.tensor(4.))
            opt.zero_grad();loss.backward();opt.step()
            if (epoch+1)%20==0 or epoch==0:
                net.eval()
                with torch.inference_mode():
                    p,l=net(z[val]);metrics=statistics(p,l.sigmoid(),y[val],masks[val])
                # Pixel fidelity selects checkpoints; IoU separately gates promotion.
                score=metrics['rgb_mse']
                if score<best_score:best_score=score;best_state=copy.deepcopy(net.state_dict());best_epoch=epoch+1
                if (epoch+1)%100==0:print(name,'epoch',epoch+1,'val MSE',round(score,7),flush=True)
        net.load_state_dict(best_state);net.eval()
        with torch.inference_mode():
            p,l=net(z[val]);validation=statistics(p,l.sigmoid(),y[val],masks[val])
        candidates.append(dict(name=name,selected_epoch=best_epoch,validation=validation))
        if best is None or validation['rgb_mse']<best['validation']['rgb_mse']:
            best=dict(name=name,validation=validation,state=best_state,selected_epoch=best_epoch)
    selected=StageCNN(mean_rgb,mean_mask,len(fields));selected.load_state_dict(best['state']);selected.eval()
    report=dict(version=version,resolution=SIZE,fields=fields,seed=42,
        trials={s:d['trials'][d['splits']==s].tolist() for s in ['train','validation','test']},
        targets_per_trial=1,mask_ground_truth=mask_note or 'weak HSV/color-derived masks, not manual/physical measurements',
        stage=stage or 'fixed five-second visually stable area proxy; physical steady conditions not established',
        selection='lowest validation RGB MSE across predeclared objectives/checkpoints; test used only after selection',
        candidates=candidates,selected=best['name'],selected_epoch=best['selected_epoch'],evaluation={})
    train_indices=np.where(train)[0]
    for split_name,selection in [('validation',val),('test',test)]:
        with torch.inference_mode():
            p,l=selected(z[selection]);cnn=statistics(p,l.sigmoid(),y[selection],masks[selection])
            n=int(selection.sum());baseline=statistics(mean_rgb.expand(n,-1,-1,-1),mean_mask.expand(n,-1,-1,-1),y[selection],masks[selection])
            distances=torch.cdist(z[selection],z[train]);nearest=train_indices[distances.argmin(1).numpy()]
            retrieval=statistics(y[nearest],masks[nearest],y[selection],masks[selection])
        report['evaluation'][split_name]=dict(cnn=cnn,mean_image=baseline,nearest_condition=retrieval)
    def passes(e):return e['cnn']['rgb_mse']<e['mean_image']['rgb_mse'] and e['cnn']['mask_iou']>e['mean_image']['mask_iou']
    report['baseline_check_passed']=all(passes(e) for e in report['evaluation'].values())
    report['qualified_for_promotion']=False
    report['promotion_note']='Experimental only: two test trials and image-derived weak targets are insufficient to establish reliable physical accuracy; inspect every reported metric.'
    art.mkdir(parents=True,exist_ok=True)
    torch.save(dict(version=version,state=selected.state_dict(),low=low,scale=scale,report=report),art/'selected.pt')
    (art/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))


def load_model(art=ART):
    saved=torch.load(art/'selected.pt',map_location='cpu',weights_only=True)
    state=saved['state'];net=StageCNN(state['base_rgb'],state['base_mask_logits'].sigmoid(),state['encode.0.weight'].shape[1])
    net.load_state_dict(state);net.eval();return net,saved


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--epochs',type=int,default=400);a=p.parse_args();run(a.epochs)
