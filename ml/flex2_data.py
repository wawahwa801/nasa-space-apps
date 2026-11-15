"""Bounded, run-ID-joined FLEX-2 RGB subset with pre-ignition telemetry."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timedelta
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request
import zipfile

import cv2
import numpy as np
from PIL import Image, ImageDraw

from flame import DATA, OUT
from multisource_data import BASE, read
from flex_images import RangeFile, entries

ROOT=DATA/'flex2-study'
ART=OUT/'flex2-study'
FIELDS=['pressure_kpa','temperature_c']
SIZE=256
OFFSETS=[4.0,4.1,4.2,4.3]
CATEGORIES={
    'Reduced Gravity/Quiescent 2016 - Decane':'Decane',
    'Reduced Gravity/Quiescent 2012 - Decane':'Decane',
    'Reduced Gravity/SurrogateFuel 2013 - Heptane':'Heptane',
    'Reduced Gravity/SurrogateFuel 2012 - N_Octane':'N_Octane',
    'Reduced Gravity/SurrogateFuel 2013 - N_Octane':'N_Octane',
    'Reduced Gravity/SurrogateFuel 2014 - IsoOctane':'IsoOctane',
    'Reduced Gravity/SurrogateFuel 2014 - Toluene':'Toluene',
}


def sha(raw):return hashlib.sha256(raw).hexdigest()


def file_tree():
    path=DATA/'flex'/'flex2-full-file-tree.json'
    if not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        meta=json.loads(read(BASE+'/repo/investigations/PSI-68',8_000_000))
        payload=dict(folder='PSI-68/',fileType='study',studyId='PSI-68',version=meta['version'],obfuscationcode='')
        path.write_bytes(read(Request(BASE+'/files/v2',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'}),20_000_000))
    nodes=entries(json.loads(path.read_text()))
    return list({json.dumps(n,sort_keys=True):n for n in nodes}.values())


def signed(name):
    return read(BASE+'/studies/PSI-68/download?'+urlencode({'file':name,'redirect':'false'}),20_000).decode().strip().strip('"')


def stamp(text):
    return datetime.fromisoformat(text.strip())


def rows(text):
    return [{str(k).strip():str(v or '').strip() for k,v in r.items()} for r in csv.DictReader(StringIO(text))]


def event(text,label):
    match=re.search(re.escape(label)+r':\s*(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d(?:\.\d+)?)',text)
    if not match:raise ValueError('Missing event '+label)
    return stamp(match.group(1))


def acquire_run(node,files):
    name=Path(node['key']).name
    run=re.search(r'([A-Z]\d{3}[A-Z]\d{2})D\.zip$',name).group(1)
    folder=ROOT/run;folder.mkdir(parents=True,exist_ok=True)
    record_path=folder/'record.json'
    if record_path.exists():
        cached=json.loads(record_path.read_text())
        if ([m['offset_after_retraction'] for m in cached['members']]==OFFSETS
            and cached['archive_version']==node['version'] and cached['archive_resource_id']==node['id']
            and all((folder/m['file']).exists() and sha((folder/m['file']).read_bytes())==m['sha256'] for m in cached['members']+cached['metadata'])):
            return cached
    audit=[]
    def get(suffix):
        found=[f for f in files if Path(f['key']).name.endswith(run+suffix)]
        if len(found)!=1 or found[0].get('restricted'):raise ValueError('Missing/ambiguous metadata '+suffix)
        entry=found[0];filename=Path(entry['key']).name;p=folder/filename
        if not p.exists():p.write_bytes(read(signed(filename),2_000_000))
        raw=p.read_bytes();audit.append(dict(file=filename,sha256=sha(raw),resource_id=entry['id'],version=entry['version']))
        return raw.decode('utf-8-sig')
    text=get('.txt')
    if not re.search(r'Test Point:\s*'+run+r'\b',text):raise ValueError('Test point ID mismatch')
    ignition=event(text,'AS Burn to Completion/Igniter On')
    retracted=event(text,'AS Retract Completed')
    chamber=rows(get('_Chamber_Readings.txt'))
    required=['FCU TimeStamp']+[f'FCU_MP_PT{k}(PSIA)' for k in [16,17,28,29]]+[f'FCU_MP_TM{k}(Deg C)' for k in [1,2,3,4]]
    if not chamber or any(k not in chamber[0] for k in required):
        raise ValueError('Missing chamber timestamp or explicitly unit-labelled PSIA/Deg C telemetry')
    before=[r for r in chamber if ignition-timedelta(seconds=5)<=stamp(r['FCU TimeStamp'])<ignition]
    if len(before)<3:raise ValueError('Insufficient pre-ignition environmental telemetry')
    pressure=float(np.mean([[float(r[f'FCU_MP_PT{k}(PSIA)']) for k in [16,17,28,29]] for r in before]))*6.894757293
    temperature=float(np.mean([[float(r[f'FCU_MP_TM{k}(Deg C)']) for k in [1,2,3,4]] for r in before]))
    if not 20<pressure<400 or not 0<temperature<60:raise ValueError('Invalid measured chamber conditions')
    settings=rows(get('_Color_Camera_Settings.txt'))
    if not settings or settings[0].get('IPSU_ARCHIVE_FMT(N/A)')!='RGB 24':raise ValueError('Colour RGB24 camera not verified')
    camera=get('_MDCA_Color_Camera_Settings.txt')
    stream=RangeFile(signed(name))
    selected=[]
    with zipfile.ZipFile(stream) as archive:
        members=archive.namelist();meta=archive.read(run+'D.txt').decode('utf-8-sig')
        (folder/'timestamps.txt').write_text(meta)
        audit.append(dict(file='timestamps.txt',sha256=sha(meta.encode()),source_member=run+'D.txt'))
        table=rows('\n'.join(meta.splitlines()[2:]))
        times=[datetime.strptime(r['Date']+' '+r['MTimeStamp'],'%m/%d/%Y %H:%M:%S.%f') for r in table]
        used=set()
        # Fixed post-retraction window avoids the most immediate ignition flare.
        # This remains a stage proxy, not measured steady state.
        for offset in OFFSETS:
            requested=retracted+timedelta(seconds=offset)
            idx=min(range(len(times)),key=lambda i:abs((times[i]-requested).total_seconds()))
            if abs((times[idx]-requested).total_seconds())>.08 or idx in used:raise ValueError('Missing/duplicate stage frame')
            used.add(idx);member=table[idx]['FileName']+'.bmp'
            if member not in members:raise ValueError('Timestamp/member mismatch')
            raw=archive.read(member);image=Image.open(BytesIO(raw))
            if image.mode!='RGB' or image.size!=(640,480):raise ValueError('Unexpected colour-camera geometry')
            (folder/Path(member).name).write_bytes(raw)
            selected.append(dict(file=member,sha256=sha(raw),timestamp=times[idx].isoformat(),offset_after_retraction=offset))
    record=dict(run=run,fuel=CATEGORIES[node['subcategory']],category=node['subcategory'],features=[pressure,temperature],
        archive=name,archive_version=node['version'],archive_resource_id=node['id'],archive_bytes=node['bytes_size'],
        ignition=ignition.isoformat(),retraction=retracted.isoformat(),members=selected,metadata=audit,
        bytes_retrieved=stream.transferred,camera_settings=rows(camera),
        integrity='Selected ZIP member CRC and SHA256; full ranged archive SHA256 not computed')
    record_path.write_text(json.dumps(record,indent=2));return record


def fetch(limit=16):
    ROOT.mkdir(parents=True,exist_ok=True);files=file_tree()
    candidates=[]
    for category in CATEGORIES:
        group=sorted([f for f in files if f.get('subcategory')==category and re.search(r'[A-Z]\d{3}[A-Z]\d{2}D\.zip$',f['key']) and not f.get('restricted')],key=lambda f:f['key'])
        # Spread selection over available runs before image inspection.
        candidates.extend(group[i] for i in np.unique(np.linspace(0,len(group)-1,min(limit,len(group))).astype(int)))
    def attempt(node):
        try:
            result=acquire_run(node,files);print('Matched',result['run'],result['fuel'],flush=True);return result
        except Exception as error:
            name=Path(node['key']).name
            print('Excluded',name,type(error).__name__,str(error)[:200],flush=True)
            return dict(archive=name,excluded=True,reason=str(error)[:300])
    if len({Path(n['key']).name for n in candidates})!=len(candidates):
        raise ValueError('Conflicting archive listings; resolve source identity before acquisition')
    inventory=list(ThreadPoolExecutor(max_workers=4).map(attempt,candidates))
    (ROOT/'inventory.json').write_text(json.dumps(inventory,indent=2))


def prepare(target_runs=None):
    inventory=json.loads((ROOT/'inventory.json').read_text());records=[];images=[];masks=[]
    excluded=[r for r in inventory if r.get('excluded')]
    for r in inventory:
        if r.get('excluded'):continue
        arrays=[]
        for member in r['members']:
            raw=(ROOT/r['run']/member['file']).read_bytes()
            if sha(raw)!=member['sha256']:raise ValueError('Cached frame checksum mismatch')
            arrays.append(np.array(Image.open(BytesIO(raw)),dtype='float32'))
        mean=np.median(arrays,axis=0)
        # Fixed crop and display gain preserve image-relative scale and measured RGB ratios.
        shown=np.uint8(np.clip((mean[100:420,160:480]-3)*2,0,255))
        shown=cv2.GaussianBlur(shown,(3,3),.6)
        shown=cv2.resize(shown,(SIZE,SIZE),interpolation=cv2.INTER_AREA)
        hsv=cv2.cvtColor(shown,cv2.COLOR_RGB2HSV)
        mask=((hsv[:,:,1]>55)&(hsv[:,:,2]>50)).astype('uint8')
        # Limit hardware at the lower edge; no per-image recentering or scale changes.
        mask[:15]=0;mask[220:]=0;mask[:,:15]=0;mask[:,240:]=0
        count,labels,stats,_=cv2.connectedComponentsWithStats(mask,8)
        if count<2 or stats[1:,cv2.CC_STAT_AREA].max()<400:
            excluded.append(dict(run=r['run'],reason='Fewer than 400 connected colour pixels in fixed ROI'));continue
        mask=(labels==(1+stats[1:,cv2.CC_STAT_AREA].argmax())).astype('uint8')
        images.append(shown);masks.append(mask);records.append(dict(r))
    supported={fuel for fuel in CATEGORIES.values() if sum(r['fuel']==fuel for r in records)>=6}
    keep=[i for i,r in enumerate(records) if r['fuel'] in supported]
    excluded.extend(dict(run=r['run'],reason='Fewer than six usable trials for this fuel') for r in records if r['fuel'] not in supported)
    records=[records[i] for i in keep];images=[images[i] for i in keep];masks=[masks[i] for i in keep]
    if not records:raise ValueError('No supported FLEX-2 data; inspect inventory')
    if len({r['run'] for r in records})!=len(records):raise ValueError('Duplicate independent run IDs')
    if target_runs is not None:
        if target_runs<6*len(supported):raise ValueError('Target must allow at least six runs per fuel')
        if len(records)<target_runs:raise ValueError(f'Only {len(records)} usable independent runs; requested {target_runs}')
        # Round-robin across fuels, pressure-spread ordering within each fuel.
        pools={f:sorted([i for i,r in enumerate(records) if r['fuel']==f],key=lambda i:(records[i]['features'][0],records[i]['run'])) for f in sorted(supported)}
        keep=[]
        # Evenly spaced positions avoid truncating every fuel to low pressures.
        quota={f:0 for f in pools}
        for _ in range(target_runs):
            f=min((f for f in pools if quota[f]<len(pools[f])),key=lambda f:(quota[f],f));quota[f]+=1
        for f,p in pools.items():keep.extend(p[i] for i in np.linspace(0,len(p)-1,quota[f]).astype(int))
        excluded.extend(dict(run=r['run'],reason='Verified usable run outside bounded target selection') for i,r in enumerate(records) if i not in keep)
        records=[records[i] for i in keep];images=[images[i] for i in keep];masks=[masks[i] for i in keep]
    for fuel in sorted(supported):
        group=sorted([r for r in records if r['fuel']==fuel],key=lambda r:sha(('flex2-42/'+r['run']).encode()))
        n=max(1,round(len(group)*.2))
        for j,r in enumerate(group):r['split']='test' if j<n else 'validation' if j<2*n else 'train'
    fuels=sorted(supported)
    np.savez_compressed(ROOT/'prepared.npz',features=np.array([r['features'] for r in records],dtype='float32'),
        fuels=np.array([fuels.index(r['fuel']) for r in records]),images=np.array(images),masks=np.array(masks),
        groups=np.array([r['run'] for r in records]),splits=np.array([r['split'] for r in records]))
    manifest=dict(source='PSI-68',target_runs=target_runs,source_url='https://psi.nasa.gov/physci/repo/data/investigations/PSI-68',
        fields=FIELDS,fuels=fuels,records=records,excluded=excluded,resolution=SIZE,
        features_note='Mean of four chamber pressure and temperature channels in the five seconds before ignition; PSIA converted to kPa. Fuel is the NASA file subcategory. No per-run oxygen, droplet diameter or airflow labels inferred.',
        stage='Median of four RGB frames at 4.0/4.1/4.2/4.3 seconds after recorded igniter retraction; stage proxy, not steady-state measurement',
        preprocessing='Fixed 320px square crop x160:480/y100:420; clip((RGB-3)*2), Gaussian 3px sigma .6, resize to 256; no synthetic colour',
        split='Whole test-point hash split within fuel; no frames cross splits. Different unmeasured droplet sizes/oxygen and camera settings may confound predictions.',
        counts=dict(pairs=len(records),groups=len(records),splits={s:sum(r['split']==s for r in records) for s in ['train','validation','test']}))
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    canvas=Image.new('RGB',(5*256,((len(images)+4)//5)*280));draw=ImageDraw.Draw(canvas)
    for i,(im,r) in enumerate(zip(images,records)):
        x=i%5*256;y=i//5*280;canvas.paste(Image.fromarray(im),(x,y));draw.text((x,y+256),r['run']+' '+r['fuel']+' '+r['split'],fill='white')
    canvas.save(ROOT/'montage.jpg');print(json.dumps(manifest['counts']),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['fetch','prepare']);p.add_argument('--runs-per-fuel',type=int,default=100,help='Maximum candidate runs per campaign category')
    p.add_argument('--target-runs',type=int,help='Require and select exactly this many usable independent runs')
    a=p.parse_args();fetch(a.runs_per_fuel) if a.command=='fetch' else prepare(a.target_runs)
