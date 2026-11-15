"""Small, identifier-joined FLEX camera-B subset using bounded ZIP range reads."""
import argparse
import csv
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
import zipfile

import cv2
import numpy as np
from PIL import Image,ImageDraw

from flame import DATA
from multisource_data import BASE,read

ROOT=DATA/'flex'/'study'
IDS=['C06M101','C07M101','C07M201','C05M101','C05M201','C06M201','C06M401','C05M301']
VAL={'C05M101','C06M201'}
TEST={'C05M201','C06M401'}
FIELDS=['initial_oxygen_percent','pressure_kpa','initial_co2_percent','droplet_diameter_mm']


class RangeFile(io.RawIOBase):
    """Read only requested ZIP bytes; reject servers that ignore HTTP Range."""
    def __init__(self,url):
        self.url=url;self.position=0;self.transferred=0
        with urlopen(Request(url,headers={'Range':'bytes=0-0'}),timeout=90) as r:
            if r.status!=206:raise ValueError('Server does not support bounded byte ranges')
            self.length=int(r.headers['Content-Range'].split('/')[-1]);r.read(1)
    def seekable(self):return True
    def readable(self):return True
    def tell(self):return self.position
    def seek(self,offset,whence=0):
        self.position=offset if whence==0 else self.position+offset if whence==1 else self.length+offset
        if self.position<0:raise ValueError('Negative seek')
        return self.position
    def read(self,n=-1):
        n=self.length-self.position if n<0 else min(n,self.length-self.position)
        if n<=0:return b''
        if n>16_000_000 or self.transferred+n>60_000_000:raise ValueError('ZIP range budget exceeded')
        start=self.position
        with urlopen(Request(self.url,headers={'Range':f'bytes={start}-{start+n-1}'}),timeout=90) as r:
            if r.status!=206:raise ValueError('Server ignored Range')
            data=r.read(n+1)
            if len(data)!=n:raise ValueError('Incomplete ZIP range')
        self.position+=n;self.transferred+=n;return data


def clock(text):
    text=text.strip()
    value=datetime.strptime(text,'%H:%M:%S.%f' if '.' in text else '%H:%M:%S')
    return value.hour*3600+value.minute*60+value.second+value.microsecond/1e6


def file_tree():
    p=DATA/'flex'/'full-file-tree.json'
    if p.exists():return json.loads(p.read_text())
    catalog=json.loads((DATA/'multi'/'PSI-69'/'catalog.json').read_text())
    body=json.dumps(dict(folder='PSI-69/',fileType='study',studyId='PSI-69',version=catalog['version'],obfuscationcode='')).encode()
    request=Request(BASE+'/files/v2',data=body,headers={'Content-Type':'application/json'})
    data=read(request,15_000_000);p.write_bytes(data);return json.loads(data)


def entries(tree):
    result=[]
    def walk(n):
        if isinstance(n,dict):
            if n.get('directory') is False and n.get('key'):result.append(n)
            for v in n.values():
                if isinstance(v,(dict,list)):walk(v)
        elif isinstance(n,list):
            for v in n:walk(v)
    walk(tree);return result


def fetch():
    ROOT.mkdir(parents=True,exist_ok=True)
    releases=json.loads((DATA/'flex'/'conditions.json').read_text())
    rows={r['FLEX Identifier']:r for r in releases[0]['rows']}
    nodes=entries(file_tree());audit=[]
    for identifier in IDS:
        r=rows[identifier]
        if r['Fuel']!='Methanol' or r['Test end']!='Extinction':
            audit.append(dict(run=identifier,status='excluded',reason='Requires documented methanol extinction trial'));continue
        name=f'PSI-69_Raw Data_{identifier}B.zip'
        found=[n for n in nodes if Path(n['key']).name==name]
        if len(found)!=1 or found[0].get('restricted'):raise ValueError('Ambiguous/restricted FLEX archive')
        cache=ROOT/identifier;cache.mkdir(exist_ok=True)
        cached=cache/'selection.json'
        if cached.exists():
            record=json.loads(cached.read_text());record['archive_version']=found[0].get('version');record['stage']='25–65% of documented burn time after reported Test GMT; timestamp-selected post-reported-burn camera baseline, not certified dark frames'
            record['integrity']='Selected ZIP member CRC32 and SHA256; full archive SHA256 not calculated for range reads'
            cached.write_text(json.dumps(record,indent=2));audit.append(record);print('Cached',identifier,flush=True);continue
        full=DATA/'flex'/'raw'/name
        stream=None
        if full.exists():z=zipfile.ZipFile(full)
        else:
            signed=read(BASE+'/studies/PSI-69/download?'+urlencode({'file':name,'redirect':'false'}),20_000).decode().strip().strip('"')
            stream=RangeFile(signed);z=zipfile.ZipFile(stream)
        try:
            metadata=z.read(identifier+'B.txt').decode('utf-8-sig')
            (cache/'timestamps.txt').write_text(metadata)
            table=[{k.strip():v.strip() for k,v in row.items()} for row in csv.DictReader(io.StringIO('\n'.join(metadata.splitlines()[2:])))]
            t0=clock(r['Test GMT']);burn=float(r['Burn time; s'])
            frames=[row for row in table if t0+.25*burn<=clock(row['MTimeStamp'])<=t0+.65*burn]
            background=[row for row in table if clock(row['MTimeStamp'])>t0+burn+1][-15:]
            if len(frames)<5 or len(background)<10:raise ValueError('Insufficient mid-burn or post-reported-burn frames')
            chosen=[frames[i] for i in np.unique(np.linspace(0,len(frames)-1,min(16,len(frames))).astype(int))]
            names=set(z.namelist());selected=[]
            for role,group in [('target',chosen),('background',background)]:
                for row in group:
                    member=row['FileName']+'.tif'
                    if member not in names:raise ValueError('Timestamp/image member mismatch')
                    raw=z.read(member) # zipfile verifies the member CRC32.
                    (cache/Path(member).name).write_bytes(raw)
                    selected.append(dict(role=role,file=member,sha256=hashlib.sha256(raw).hexdigest(),timestamp=row['MTimeStamp']))
            record=dict(run=identifier,status='matched',split='test' if identifier in TEST else 'validation' if identifier in VAL else 'train',
                source='PSI-69',material='Methanol',camera='B; monochrome 16-bit flame imagery',archive=name,
                archive_bytes=found[0]['bytes_size'],archive_version=found[0].get('version'),resource_id=found[0]['id'],original_row=r,members=selected,
                integrity='Selected ZIP member CRC32 and SHA256; full archive SHA256 not calculated for range reads',
                fields=FIELDS,features=[100*float(r['O initial ambient composition; mole fraction']),
                    .133322*float(r['Ambient pressure; mmHg']),100*float(r['CO initial ambient composition; mole fraction']),float(r['Droplet initial diameter; mm'])],
                stage='25–65% of documented burn time after reported Test GMT; timestamp-selected post-reported-burn baseline',
                source_url='https://psi.nasa.gov/physci/repo/data/investigations/PSI-69',
                bytes_retrieved=stream.transferred if stream else full.stat().st_size)
            cached.write_text(json.dumps(record,indent=2));audit.append(record)
            print('Matched',identifier,record['split'],len(chosen),'target frames',flush=True)
        except (ValueError,KeyError,zipfile.BadZipFile) as error:
            audit.append(dict(run=identifier,status='excluded',reason=str(error)));print('Excluded',identifier,str(error),flush=True)
        finally:
            z.close()
            if stream:stream.close()
    (ROOT/'inventory.json').write_text(json.dumps(audit,indent=2))


def prepare():
    audit=json.loads((ROOT/'inventory.json').read_text());features=[];targets=[];masks=[];groups=[];splits=[];processing=[]
    for record in audit:
        if record['status']!='matched':continue
        cache=ROOT/record['run'];arrays={}
        for role in ['target','background']:
            items=[]
            for member in record['members']:
                if member['role']!=role:continue
                path=cache/member['file']
                if hashlib.sha256(path.read_bytes()).hexdigest()!=member['sha256']:
                    raise ValueError('Cached TIFF checksum mismatch: '+member['file'])
                items.append(np.array(Image.open(path),dtype='float32'))
            arrays[role]=np.stack(items)
        background=np.median(arrays['background'],axis=0)
        signal=np.maximum(arrays['target'].mean(0)-background,0)
        signal=cv2.GaussianBlur(signal,(7,7),1.5)
        mask=(signal>100).astype('uint8')
        count,labels,stats,_=cv2.connectedComponentsWithStats(mask,8)
        cleaned=np.zeros(mask.shape,dtype='uint8')
        for j in range(1,count):
            if stats[j,cv2.CC_STAT_AREA]>=40:cleaned[labels==j]=1
        ys,xs=np.nonzero(cleaned)
        if len(xs)<50:raise ValueError('No qualified luminous signal in '+record['run'])
        shift=np.float32([[1,0,signal.shape[1]/2-np.median(xs)],[0,1,signal.shape[0]/2-np.median(ys)]])
        # Fixed display scale; no conversion from intensity into temperature or heat flux.
        shown=np.uint8(np.clip(signal/2000,0,1)*255)*cleaned
        shown=cv2.warpAffine(shown,shift,(signal.shape[1],signal.shape[0]))
        cleaned=cv2.warpAffine(cleaned,shift,(signal.shape[1],signal.shape[0]),flags=cv2.INTER_NEAREST)
        shown=cv2.resize(shown,(256,256),interpolation=cv2.INTER_AREA)
        cleaned=cv2.resize(cleaned,(256,256),interpolation=cv2.INTER_NEAREST)
        targets.append(np.repeat(shown[:,:,None],3,axis=2));masks.append(cleaned)
        features.append(record['features']);groups.append(record['run']);splits.append(record['split'])
        processing.append(dict(run=record['run'],source_shape=list(signal.shape),translation_pixels=[float(shift[0,2]),float(shift[1,2])],
            display_counts_scale=2000,signal_threshold_counts=100,gaussian_kernel=7,gaussian_sigma=1.5,minimum_component_area=40,
            resolution=256,target_members=[m['file'] for m in record['members'] if m['role']=='target'],background_members=[m['file'] for m in record['members'] if m['role']=='background']))
    if any(splits.count(s)<2 for s in ['train','validation','test']):raise ValueError('Need >=2 FLEX trials in each split')
    np.savez_compressed(ROOT/'prepared.npz',features=np.array(features,dtype='float32'),images=np.array(targets),masks=np.array(masks),trials=np.array(groups),splits=np.array(splits))
    canvas=Image.new('RGB',(4*256,((len(targets)+3)//4)*290));draw=ImageDraw.Draw(canvas)
    for i,(target,run,part) in enumerate(zip(targets,groups,splits)):
        x=i%4*256;y=i//4*290;canvas.paste(Image.fromarray(target),(x,y));draw.text((x,y+260),run+' / '+part,fill='white')
    canvas.save(ROOT/'targets-montage.png');(ROOT/'preprocessing.json').write_text(json.dumps(processing,indent=2));print('Prepared FLEX targets',len(targets),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['fetch','prepare']);a=p.parse_args();fetch() if a.command=='fetch' else prepare()
