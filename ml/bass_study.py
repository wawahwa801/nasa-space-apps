"""BASS-only experiment: matched PMMA trials, fixed stage rule, whole-trial splits."""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageOps
import torch
from torch import nn
import torch.nn.functional as F

from flame import DATA,OUT
from multisource_data import acquire

TRIALS=['B1','B2','B4','B6','B8','B9','B10','B11','B14','B16','B18','B19','B20','B21','B22']
VALIDATION={'B9','B10','B20'}
TEST={'B11','B19'}
SIZE=256
WORK=DATA/'bass-study'
ART=OUT/'bass-study'
FIELDS=['initial_oxygen_percent','thickness_mm','width_cm']
VERSION='bass-stage-v1'


def conditions(row):
    material=row['Fuel Sample Material']
    if 'PMMA' not in material:raise ValueError('Polymer is not explicitly documented')
    micron=re.search(r'(\d+)\s*micron',material)
    mm=re.search(r'(\d*\.?\d+)\s*mm',material)
    width=re.search(r'(\d*\.?\d+)\s*cm',material)
    if not (micron or mm) or not width:raise ValueError('Missing explicit geometry')
    return [float(row['Calibrated  initial O2 % by vol ']),
            float(micron.group(1))/1000 if micron else float(mm.group(1)),float(width.group(1))]


def split(trial):
    return 'test' if trial in TEST else 'validation' if trial in VALIDATION else 'train'


def fetch():
    catalog=json.loads((DATA/'bass-catalog.json').read_text())
    rows={r['Test #']:r for r in csv.DictReader((DATA/'PSI-25_Experimental table_BASS-II.csv').open(encoding='utf-8-sig'))}
    WORK.mkdir(exist_ok=True);inventory=[]
    for trial in TRIALS:
        matches=[f for f in catalog['added'] if re.search(r'TEST_?'+trial+r'\.mp4$',f['file_name'])]
        if len(matches)!=1:
            inventory.append(dict(trial=trial,status='excluded',reason='No unique primary-view video'));continue
        values=conditions(rows[trial]);name=matches[0]['file_name']
        existing=DATA/name
        if not existing.exists():existing=acquire('PSI-25',name)
        inventory.append(dict(trial=trial,status='downloaded',path=str(existing.resolve()),features=values,
            row=rows[trial],split=split(trial),source='https://psi.nasa.gov/physci/repo/data/investigations/PSI-25'))
        print('Ready',trial,flush=True)
    (WORK/'inventory.json').write_text(json.dumps(inventory,indent=2))


def flame_mask(rgb):
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
    raw=((hsv[:,:,1]>65)&(hsv[:,:,2]>45)).astype('uint8')
    count,labels,stats,_=cv2.connectedComponentsWithStats(raw,8)
    mask=np.zeros(raw.shape,dtype='uint8')
    # Remove sensor specks. This is weak color supervision, not a manual ground truth mask.
    for j in range(1,count):
        if stats[j,cv2.CC_STAT_AREA]>=12:mask[labels==j]=1
    return mask


def prepare():
    inventory=json.loads((WORK/'inventory.json').read_text())
    features=[];targets=[];masks=[];groups=[];parts=[];audit=[]
    for entry in inventory:
        if entry['status']!='downloaded':audit.append(entry);continue
        path=Path(entry['path']);cap=cv2.VideoCapture(str(path))
        try:
            fps=cap.get(cv2.CAP_PROP_FPS);duration=cap.get(cv2.CAP_PROP_FRAME_COUNT)/fps if fps else 0
            if fps<6 or duration<8:raise ValueError('Video cannot be decoded or is too short')
            frames=[];times=[];indices=[];areas=[]
            # Search the early burn, not a fixed absolute time; fixed for every split.
            for t in np.arange(2,min(duration-1,90),.5):
                cap.set(cv2.CAP_PROP_POS_MSEC,float(t)*1000);ok,frame=cap.read()
                if not ok:continue
                h,w=frame.shape[:2]
                crop=frame[int(.32*h):int(.93*h),int(.12*w):int(.88*w)]
                rgb=cv2.cvtColor(crop,cv2.COLOR_BGR2RGB)
                rgb=np.array(ImageOps.pad(Image.fromarray(rgb),(SIZE,SIZE),method=Image.Resampling.LANCZOS))
                mask=flame_mask(rgb)
                frames.append((rgb,mask));times.append(float(t));indices.append(int(round(cap.get(cv2.CAP_PROP_POS_FRAMES)))-1);areas.append(int(mask.sum()))
            if len(frames)<10:raise ValueError('Insufficient readable frames')
            # Choose a five-second window with stable luminous area and a visible flame.
            candidates=[]
            for start in range(len(frames)-9):
                a=np.array(areas[start:start+10],dtype=float)
                if (a<60).any() or np.median(a)>SIZE*SIZE*.25:continue
                if not np.allclose(np.diff(times[start:start+10]),.5):continue
                score=np.std(a)/(np.mean(a)+1)+.02*start/len(frames)
                candidates.append((float(score),start))
            if not candidates:raise ValueError('No qualifying visually stable luminous window')
            score,start=min(candidates)
            selected=frames[start:start+10]
            # Translation-only registration removes camera position, retaining relative extent.
            yy,xx=np.nonzero(np.stack([m for _,m in selected]).mean(0)>.4)
            if len(xx)<20:raise ValueError('Unstable flame support')
            dx=int(round(SIZE/2-np.median(xx)));dy=int(round(SIZE/2-np.median(yy)))
            transform=np.float32([[1,0,dx],[0,1,dy]])
            registered=[];registered_masks=[]
            for rgb,mask in selected:
                image=cv2.warpAffine(rgb*mask[:,:,None],transform,(SIZE,SIZE))
                target_mask=cv2.warpAffine(mask,transform,(SIZE,SIZE),flags=cv2.INTER_NEAREST)
                registered.append(image);registered_masks.append(target_mask)
            # One representative target per experiment avoids pretending nearby frames are independent.
            representative=np.mean(registered,axis=0).astype('uint8')
            representative_mask=(np.mean(registered_masks,axis=0)>=.5).astype('uint8')
            if representative_mask.sum()<30:raise ValueError('Representative target has no visible flame')
            features.append(entry['features']);targets.append(representative);masks.append(representative_mask)
            groups.append(entry['trial']);parts.append(entry['split'])
            audit.append(dict(entry,status='prepared',stage_proxy='minimum area coefficient of variation over ten 2-fps frames',
                selected_times=times[start:start+10],source_frame_indices=indices[start:start+10],
                stage_score=score,translation_pixels=[dx,dy],duration_seconds=duration,native_fps=fps,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),raw_frames_used=10))
            print('Prepared',entry['trial'],entry['split'],times[start:start+10],flush=True)
        except (ValueError,cv2.error) as error:
            audit.append(dict(entry,status='excluded',reason=str(error)));print('Excluded',entry['trial'],str(error),flush=True)
        finally:cap.release()
    if any(parts.count(s)<2 for s in ['train','validation','test']):raise ValueError('Need >=2 independent trials in each split')
    np.savez_compressed(WORK/'prepared.npz',features=np.array(features,dtype='float32'),images=np.array(targets),
                        masks=np.array(masks),trials=np.array(groups),splits=np.array(parts))
    manifest=dict(version=VERSION,fields=FIELDS,resolution=SIZE,inventory=audit,
        frozen_validation=sorted(VALIDATION),frozen_test=sorted(TEST),
        note='Color masks and stable-window selection are weak image-derived supervision; no claim of measured steady physical conditions or calibrated lengths.')
    (WORK/'manifest.json').write_text(json.dumps(manifest,indent=2))
    canvas=Image.new('RGB',(5*256,((len(targets)+4)//5)*290));draw=ImageDraw.Draw(canvas)
    for i,(rgb,trial,part) in enumerate(zip(targets,groups,parts)):
        x=i%5*256;y=i//5*290;canvas.paste(Image.fromarray(rgb),(x,y));draw.text((x,y+260),f'{trial} / {part}',fill='white')
    canvas.save(WORK/'targets-montage.png')
    print('Independent targets:',dict(zip(*np.unique(parts,return_counts=True))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['fetch','prepare']);a=p.parse_args()
    fetch() if a.command=='fetch' else prepare()
