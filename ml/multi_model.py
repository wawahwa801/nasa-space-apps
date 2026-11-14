"""Condition-only multi-source CNN with explicit missing-value masks."""
import argparse
import json

import numpy as np
import torch
from torch import nn

from flame import DATA,OUT
from multisource_data import FIELDS,SOURCE_IDS,SIZE,FPS

VERSION='multi-source-conditions-v1'


class MultiCNN(nn.Module):
    def __init__(self,inputs):
        super().__init__()
        self.encode=nn.Sequential(nn.Linear(inputs,64),nn.ReLU(),nn.Linear(64,32*8*8),nn.ReLU())
        self.decode=nn.Sequential(nn.ConvTranspose2d(32,16,4,2,1),nn.ReLU(),
            nn.ConvTranspose2d(16,8,4,2,1),nn.ReLU(),nn.ConvTranspose2d(8,8,4,2,1),nn.ReLU(),
            nn.ConvTranspose2d(8,3,4,2,1),nn.Sigmoid())
        nn.init.normal_(self.decode[-2].weight,std=.01);nn.init.constant_(self.decode[-2].bias,-2)

    def forward(self,x):return self.decode(self.encode(x).reshape(-1,32,8,8))


def encode(records,schema):
    result=[]
    for record in records:
        values=[];masks=[]
        for i,(key,_,_) in enumerate(FIELDS):
            v=record['features'].get(key)
            values.append(0. if v is None else (v-schema['low'][i])/schema['scale'][i])
            masks.append(0. if v is None else 1.)
        values+=masks
        values += [float(record['source']==s) for s in SOURCE_IDS]
        values += [float(record['material']==m) for m in schema['materials']]
        result.append(values)
    return torch.tensor(result,dtype=torch.float32)


def fit_schema(records):
    low=[];high=[]
    for key,_,_ in FIELDS:
        values=[r['features'][key] for r in records if r['features'].get(key) is not None]
        low.append(min(values) if values else 0.);high.append(max(values) if values else 0.)
    return dict(low=low,high=high,scale=[max(b-a,1e-6) for a,b in zip(low,high)],
                materials=sorted({r['material'] for r in records}))


def train(epochs):
    if epochs<1:raise ValueError('epochs must be positive')
    torch.manual_seed(42);torch.set_num_threads(2)
    manifest=json.loads((DATA/'multi-manifest.json').read_text());records=manifest['records']
    mask=np.array([r['split']=='train' for r in records])
    schema=fit_schema([r for r in records if r['split']=='train'])
    x=encode(records,schema)
    y=torch.from_numpy(np.load(DATA/'multi-images.npz')['images']).permute(0,3,1,2).float()/255
    net=MultiCNN(x.shape[1]);opt=torch.optim.Adam(net.parameters(),lr=.0007)
    tx,ty=x[mask],y[mask]
    for epoch in range(epochs):
        for indices in torch.randperm(len(tx)).split(16):
            p=net(tx[indices]);target=ty[indices]
            loss=(((p-target)**2)*(1+70*target.amax(1,keepdim=True))).mean()
            opt.zero_grad();loss.backward();opt.step()
        if (epoch+1)%10==0:print(f'epoch {epoch+1}/{epochs} weighted MSE {loss.item():.5f}',flush=True)
    net.eval();validation={}
    with torch.inference_mode():
        for source in SOURCE_IDS:
            vm=np.array([r['source']==source and r['split']=='validation' for r in records])
            tm=np.array([r['source']==source and r['split']=='train' for r in records])
            if not vm.any():validation[source]=dict(images=0,mse=None,baseline_mse=None,note='No independent held-out experiment in this source sample');continue
            p=net(x[vm]);target=y[vm];baseline=y[tm].mean(0,keepdim=True)
            validation[source]=dict(images=int(vm.sum()),mse=((p-target)**2).mean().item(),
                                   baseline_mse=((baseline-target)**2).mean().item())
    metrics=dict(version=VERSION,epochs=epochs,seed=42,resolution=SIZE,sampled_fps=FPS,
        parameters=sum(p.numel() for p in net.parameters()),images_per_source=manifest['counts'],
        train_images=int(mask.sum()),validation_images=int((~mask).sum()),validation=validation,
        input_fields=[k for k,_,_ in FIELDS],time_is_input=False,
        train_experiments=sorted({r['experiment'] for r in records if r['split']=='train'}),
        validation_experiments=sorted({r['experiment'] for r in records if r['split']=='validation'}))
    OUT.mkdir(exist_ok=True)
    torch.save(dict(version=VERSION,state=net.state_dict(),schema=schema,metrics=metrics,input_size=x.shape[1]),OUT/'multi.pt')
    (OUT/'multi-metrics.json').write_text(json.dumps(metrics,indent=2));print(json.dumps(metrics,indent=2))


def load_model():
    saved=torch.load(OUT/'multi.pt',map_location='cpu',weights_only=True)
    if saved['version']!=VERSION:raise ValueError('Retrain multi-source model')
    net=MultiCNN(saved['input_size']);net.load_state_dict(saved['state']);net.eval()
    return net,saved


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--epochs',type=int,default=120);a=p.parse_args();train(a.epochs)
