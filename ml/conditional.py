"""Feature vector -> convolutional image decoder; no image input at inference."""
import argparse
import csv
import hashlib
import json
import re

import cv2
import numpy as np
from PIL import Image, ImageOps
import torch
from torch import nn

from flame import DATA, OUT

FEATURES = [
    dict(key='thickness', label='Film thickness', unit='mm', step=.01),
    dict(key='fan', label='Fan display', unit='display reading', step=.5),
    dict(key='air', label='Air display', unit='display reading', step=.1),
    dict(key='co2', label='Initial CO₂', unit='% by volume', step=.001),
    dict(key='time', label='Video time', unit='seconds', step=.25),
]
TRIALS = ['B1', 'B3', 'B4', 'B5', 'B12']
ARCHITECTURE = 'condition-decoder-v1'


class ConditionalCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.encode = nn.Sequential(nn.Linear(len(FEATURES), 64), nn.ReLU(),
                                    nn.Linear(64, 32*8*8), nn.ReLU())
        self.decode = nn.Sequential(nn.ConvTranspose2d(32, 16, 4, 2, 1), nn.ReLU(),
                                    nn.ConvTranspose2d(16, 8, 4, 2, 1), nn.ReLU(),
                                    nn.ConvTranspose2d(8, 3, 4, 2, 1), nn.Sigmoid())
        nn.init.normal_(self.decode[-2].weight, std=.01)
        nn.init.constant_(self.decode[-2].bias, -2)

    def forward(self, features):
        return self.decode(self.encode(features).reshape(-1, 32, 8, 8))


def prepare():
    with (DATA/'PSI-25_Experimental table_BASS-II.csv').open(encoding='utf-8-sig') as f:
        rows = {r['Test #']:r for r in csv.DictReader(f)}
    features, images, groups, manifest = [], [], [], []
    for trial in TRIALS:
        row = rows[trial]
        material = row['Fuel Sample Material']
        # Read only explicitly documented film dimensions; preserve original material text.
        thickness = re.search(r'(\d+)\s+micron', material)
        width = re.search(r'(\d+)\s+cm\s+wide', material)
        if not thickness or not width:
            raise ValueError('Missing documented geometry: '+trial)
        candidates = list(DATA.glob(f'*_SAMPLE_{row["Sample #"]}_TEST_{trial}.mp4'))
        if len(candidates) != 1:
            raise ValueError('Need exactly one source video for '+trial)
        video = candidates[0]
        capture = cv2.VideoCapture(str(video))
        timestamps = []
        try:
            for t in np.arange(15, 35, .5):
                capture.set(cv2.CAP_PROP_POS_MSEC, float(t)*1000)
                ok, frame = capture.read()
                if not ok:
                    raise ValueError(f'{trial}: no frame at {t}')
                h,w = frame.shape[:2]
                # Fixed normalized ROI removes top telemetry; pad to preserve aspect ratio.
                frame = frame[int(.22*h):int(.95*h), int(.05*w):int(.95*w)]
                image = ImageOps.pad(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)),
                                     (64,64), method=Image.Resampling.BILINEAR)
                features.append([float(thickness.group(1))/1000, float(row['Fan display']),
                    float(row['Air display']), float(row['Initial CO2 % by vol']), float(t)])
                images.append(np.array(image));groups.append(trial);timestamps.append(float(t))
        finally:
            capture.release()
        manifest.append(dict(trial=trial, sample=row['Sample #'], material=material,
            width_cm=float(width.group(1)), initial_oxygen_percent=float(row['Calibrated  initial O2 % by vol ']),
            video=video.name, sha256=hashlib.sha256(video.read_bytes()).hexdigest(),
            row=row, timestamps=timestamps, source='https://psi.nasa.gov/physci/repo/data/investigations/PSI-25'))
    np.savez_compressed(DATA/'conditional.npz', features=np.array(features,dtype='float32'),
                        images=np.array(images), groups=np.array(groups))
    (DATA/'conditional-manifest.json').write_text(json.dumps(manifest,indent=2))
    print(f'Prepared {len(images)} labeled images across {len(manifest)} trials')


def train(epochs):
    if epochs < 1:
        raise ValueError('epochs must be positive')
    torch.manual_seed(42);torch.set_num_threads(2)
    data = np.load(DATA/'conditional.npz')
    train_mask = data['groups'] != 'B3'
    x = torch.from_numpy(data['features'])
    y = torch.from_numpy(data['images']).permute(0,3,1,2).float()/255
    low,high = x[train_mask].amin(0),x[train_mask].amax(0)
    scale = (high-low).clamp(min=1e-6)
    normalized = (x-low)/scale
    net=ConditionalCNN();optimizer=torch.optim.Adam(net.parameters(),lr=.0005)
    tx,ty=normalized[train_mask],y[train_mask]
    for epoch in range(epochs):
        net.train()
        for indices in torch.randperm(len(tx)).split(16):
            prediction=net(tx[indices]);target=ty[indices]
            # Give the observed luminous region weight without replacing targets.
            weight=1+100*target.amax(1,keepdim=True)
            loss=(((prediction-target)**2)*weight).mean()
            optimizer.zero_grad();loss.backward();optimizer.step()
        if (epoch+1)%25==0:
            print(f'epoch {epoch+1}/{epochs} weighted MSE {loss.item():.5f}',flush=True)
    net.eval()
    with torch.inference_mode():
        prediction=net(normalized[~train_mask]);target=y[~train_mask]
        mse=((prediction-target)**2).mean().item()
        baseline=((ty.mean(0,keepdim=True)-target)**2).mean().item()
        sensitivity={}
        middle=torch.full((1,len(FEATURES)),.5)
        for i,f in enumerate(FEATURES):
            a=middle.clone();b=middle.clone();a[0,i]=0;b[0,i]=1
            sensitivity[f['key']]=(net(a)-net(b)).abs().mean().item()
    specs=[dict(f,min=float(low[i]),max=float(high[i])) for i,f in enumerate(FEATURES)]
    metrics=dict(architecture=ARCHITECTURE,epochs=epochs,seed=42,
        parameters=sum(p.numel() for p in net.parameters()),train_trials=['B1','B4','B5','B12'],
        validation_trials=['B3'],train_images=int(train_mask.sum()),validation_images=int((~train_mask).sum()),
        validation_mse=mse,mean_image_baseline_mse=baseline,feature_sensitivity=sensitivity)
    OUT.mkdir(exist_ok=True)
    torch.save(dict(architecture=ARCHITECTURE,state=net.state_dict(),low=low,scale=scale,
                    features=specs,metrics=metrics),OUT/'conditional.pt')
    (OUT/'conditional-metrics.json').write_text(json.dumps(metrics,indent=2))
    montage=torch.cat([prediction[0],target[0]],dim=2).permute(1,2,0).numpy()
    Image.fromarray(np.uint8(montage.clip(0,1)*255)).save(OUT/'conditional-comparison.png')
    print(json.dumps(metrics,indent=2))


def load_model():
    saved=torch.load(OUT/'conditional.pt',map_location='cpu',weights_only=True)
    if saved['architecture'] != ARCHITECTURE:
        raise ValueError('Retrain the conditional model')
    net=ConditionalCNN();net.load_state_dict(saved['state']);net.eval()
    return net,saved


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','train'])
    p.add_argument('--epochs',type=int,default=250);a=p.parse_args()
    prepare() if a.command=='prepare' else train(a.epochs)
