"""Bounded acquisition and preparation of four NASA combustion sources."""
import csv
import hashlib
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
import zipfile

from flame import DATA

BASE='https://psi.nasa.gov/geode-py/ws'
SOURCES={'PSI-98':'SAFFIRE-I','PSI-100':'SAFFIRE-III','PSI-107':'SPICE'}


def read(url,limit):
    with urlopen(url,timeout=90) as r:
        body=r.read(limit+1)
    if len(body)>limit:raise ValueError('Download too large')
    return body


def acquire(investigation, name):
    folder=DATA/'multi'/investigation;folder.mkdir(parents=True,exist_ok=True)
    catalog=folder/'catalog.json'
    if not catalog.exists():catalog.write_bytes(read(BASE+'/repo/investigations/'+investigation,8_000_000))
    meta=json.loads(catalog.read_text())
    entries={f['file_name']:f for group in ['added','modified','experimentalTable'] for f in meta.get(group,[])}
    f=entries[name]
    if f.get('restricted') or float(f.get('file_size',1e12))>120_000_000:raise ValueError('Restricted/large file')
    target=folder/name
    if not target.exists():
        query=urlencode({'file':name,'redirect':'false'})
        signed=read(BASE+'/studies/'+investigation+'/download?'+query,20_000).decode().strip().strip('"')
        target.write_bytes(read(signed,120_000_000))
    return target



# Shared numeric schema: missing values remain null, not inferred measurements.
FIELDS=[
    ('oxygen_low','Documented O₂ lower bound','% vol'),('oxygen_high','Documented O₂ upper bound','% vol'),
    ('airflow','Airflow','m/s'),('pressure','Pressure','kPa'),
    ('thickness','Sample thickness','mm'),('width','Sample width','cm'),
    ('length','Sample length','cm'),('co2','Initial CO₂','% vol'),
    ('nozzle','Nozzle diameter','mm'),('fuel_low','Fuel flow lower bound','sccm'),
    ('fuel_high','Fuel flow upper bound','sccm')]
SOURCE_IDS=['PSI-25','PSI-98','PSI-100','PSI-107']
FPS=6
SIZE=128
SAFFIRE_START={'PSI-98':800,'PSI-100':800}


def rows(path):
    with path.open(encoding='utf-8-sig') as f:
        return [{k.strip():v.strip() for k,v in r.items()} for r in csv.DictReader(f)]


def build():
    import re
    import cv2
    import numpy as np
    import xlrd
    from PIL import Image,ImageOps
    targets=[]; records=[]; experiments=[]
    def add_experiment(source,run,material,values,original,images,validation=False):
        if len(images)==0:raise ValueError('Empty experiment')
        experiment=dict(source=source,run=run,material=material,features={k:values.get(k) for k,_,_ in FIELDS},
            original=original,split='validation' if validation else 'train',
            source_url=f'https://psi.nasa.gov/physci/repo/data/investigations/{source}')
        experiments.append(experiment)
        for im,location in images:
            im=ImageOps.pad(im.convert('RGB'),(SIZE,SIZE),method=Image.Resampling.LANCZOS)
            targets.append(np.array(im));records.append(dict(experiment=run,image_index=len(targets)-1,**location))
    def video_frames(path,count,offset):
        cap=cv2.VideoCapture(str(path));result=[];used=set()
        try:
            native=cap.get(cv2.CAP_PROP_FPS)
            if native<FPS:raise ValueError('Video frame rate below sampling rate')
            for i in range(count):
                t=offset+i/FPS;cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,frame=cap.read()
                if not ok:raise ValueError(f'Cannot decode {path.name} at {t}')
                index=int(round(cap.get(cv2.CAP_PROP_POS_FRAMES)))-1
                if index in used:raise ValueError('Duplicate source frame')
                used.add(index);h,w=frame.shape[:2]
                # Both small-tunnel streams have telemetry above the flame.
                frame=frame[int(.25*h):int(.94*h),int(.1*w):int(.9*w)]
                result.append((Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)),
                    dict(file=path.name,video_time_seconds=t,source_frame=index,native_fps=native,sampled_fps=FPS)))
        finally:cap.release()
        return result
    bass={r['Test #']:r for r in rows(DATA/'PSI-25_Experimental table_BASS-II.csv')}
    for trial in ['B1','B3','B4','B5','B12','B16']:
        r=bass[trial];material=r['Fuel Sample Material']
        thickness=float(re.search(r'(\d+)\s+micron',material).group(1))/1000
        width=float(re.search(r'(\d+)\s+cm',material).group(1))
        path=next(DATA.glob(f'*_SAMPLE_{r["Sample #"]}_TEST_{trial}.mp4'),None)
        if path is None:
            # The B16 table uses sample 150m; the catalog video uses 150.
            # Join by the explicit B16 trial ID, preserving both identifiers.
            candidates=list((DATA/'multi'/'PSI-25').glob(f'*_TEST{trial}.mp4'))
            if len(candidates)!=1:raise ValueError('Ambiguous/missing trial video: '+trial)
            path=candidates[0]
        vals=dict(thickness=thickness,width=width,co2=float(r['Initial CO2 % by vol']),
                  oxygen_low=float(r['Calibrated  initial O2 % by vol']),oxygen_high=float(r['Calibrated  initial O2 % by vol']))
        add_experiment('PSI-25','BASS-'+trial,'PMMA' if 'PMMA' in material else 'Unspecified film',
                       vals,r,video_frames(path,25,15),trial=='B3')
    for source in ['PSI-98','PSI-100']:
        folder=DATA/'multi'/source
        table=next(folder.glob('*Experimental table*.csv'))
        r=next(r for r in rows(table) if r['Sample Number']=='S1')
        if source=='PSI-98':
            vals=dict(thickness=float(r['Sample Thickness (cm)'])*10,width=float(r['Sample Width (cm)']),
                length=float(r['Sample Length (cm)']),airflow=float(r['Air Flow (cm/s)'])/100,
                oxygen_low=21.5,oxygen_high=21.7)
            name='PSI-98_Raw Data_SAFFIRE_I_S1C1_jpeg_part1.zip'
        else:
            number=lambda text:float(re.search(r'[\d.]+',text).group())
            vals=dict(thickness=number(r['Sample Thickness'])*10,width=number(r['Sample Width']),
                length=number(r['Sample Length']),airflow=number(r['Air Flow'])/100)
            name='PSI-100_Raw Data_SAFFIRE_III_S1C1_jpeg_part1.zip'
        archive=folder/name
        with zipfile.ZipFile(archive) as z:
            names=sorted(n for n in z.namelist() if n.lower().endswith('.jpeg'))
            stamps=np.array([int(re.search(r'-(\d+)\.',n).group(1)) for n in names])
            # A visible burn window is selected explicitly below after source QA.
            start=SAFFIRE_START[source]
            origin=stamps[start];chosen=[];used=set()
            for requested in np.arange(origin,stamps[-1],1000/FPS):
                index=int(np.argmin(abs(stamps-requested)))
                if index in used:raise ValueError('Insufficient native archive cadence')
                used.add(index);member=names[index]
                raw=Image.open(BytesIO(z.read(member))).convert('RGB')
                a=np.asarray(raw,dtype='float32')
                red,green,blue=a[:,:,0],a[:,:,1],a[:,:,2]
                illumination=(green>40)&(green>red*1.3)&(green>blue*1.3)
                luminous=(red>40)&(red>green*1.2)&(red>blue*1.2)
                if illumination.mean()>.02 or luminous.sum()<50:
                    continue
                # Fixed low-light display transform, not radiometric/heat-flux calibration.
                a=np.clip((a-3)*6,0,255).astype('uint8')
                raw=Image.fromarray(a)
                w,h=raw.size;raw=raw.crop((int(.2*w),int(.03*h),int(.85*w),int(.97*h)))
                chosen.append((raw,dict(file=archive.name,member=member,display_transform='clip((RGB-3)*6)',
                    source_timestamp_ms=int(stamps[index]),sampled_fps=FPS)))
                if len(chosen)==150:break
            if len(chosen)!=150:raise ValueError(f'{source}: insufficient qualified flame frames: {len(chosen)}')
        add_experiment(source,source+'-S1',r['Material'],vals,r,chosen)
    workbook=DATA/'multi'/'PSI-107'/'PSI-107_Raw Data_Spice Flight Test Data II modified.xls'
    sheet=xlrd.open_workbook(str(workbook)).sheet_by_index(0)
    for indices,run,offset in [([295,297],'SPICE-062-99-high',15),([296],'SPICE-062-99-low',40)]:
        rr=[sheet.row_values(i) for i in indices]
        vals=dict(nozzle=float(rr[0][9]),pressure=float(rr[0][10])/1000,
            airflow=float(rr[0][20])/100,fuel_low=min(float(r[17]) for r in rr),fuel_high=max(float(r[17]) for r in rr))
        path=DATA/'multi'/'PSI-107'/'PSI-107_Raw Data_GMT62_11.41.mp4'
        # The source clock/display was visually checked over this stable high-fuel segment.
        add_experiment('PSI-107',run,str(rr[0][8]),vals,
            dict(workbook=workbook.name,excel_rows=[i+1 for i in indices],rows=rr,
                 join='GMT062 clip, ignition interval and stable fuel/air display checked against workbook'),
            video_frames(path,75,offset),False)
    experiment_map={e['run']:e for e in experiments}
    for record in records:record.update(experiment_map[record['experiment']])
    counts={sid:sum(r['source']==sid for r in records) for sid in SOURCE_IDS}
    if any(n!=150 for n in counts.values()):raise ValueError(f'Wrong source counts: {counts}')
    np.savez_compressed(DATA/'multi-images.npz',images=np.array(targets))
    files={}
    for record in records:
        name=record['file']
        if name in files:continue
        path=DATA/name
        if not path.exists():path=DATA/'multi'/record['source']/name
        files[name]=dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size)
    (DATA/'multi-manifest.json').write_text(json.dumps(dict(files=files,schema=FIELDS,sources=SOURCE_IDS,
        resolution=SIZE,sampled_fps=FPS,counts=counts,experiments=experiments,records=records),indent=2))
    with (DATA/'multi-pairs.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['image_index','source','experiment','split','material']+[k for k,_,_ in FIELDS]+['file','member','video_time_seconds','source_frame','source_timestamp_ms'])
        writer.writeheader()
        for r in records:
            writer.writerow({**{k:r.get(k,'') for k in ['image_index','source','experiment','split','material','file','member','video_time_seconds','source_frame','source_timestamp_ms']},**r['features']})
    print('Prepared',counts,'total',len(targets),flush=True)


def download_selected():
    from fetch_bass import main as fetch_bass
    fetch_bass()
    acquire('PSI-25','PSI-25_Raw Data_BASS_GMT183_SAMPLE_150_TESTB16.mp4')
    for source,filename in [
        ('PSI-98','PSI-98_Experimental table_SAFFIRE-1.csv'),
        ('PSI-98','PSI-98_Raw Data_SAFFIRE_I_S1C1_jpeg_part1.zip'),
        ('PSI-100','PSI-100_Experimental table_SAFFIRE-3.csv'),
        ('PSI-100','PSI-100_Raw Data_SAFFIRE_III_S1C1_jpeg_part1.zip'),
        ('PSI-107','PSI-107_Raw Data_Spice Flight Test Data II modified.xls'),
        ('PSI-107','PSI-107_Raw Data_GMT62_11.41.mp4')]:
        print('Ready:',acquire(source,filename).name,flush=True)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('command',choices=['fetch','prepare']);a=p.parse_args()
    download_selected() if a.command=='fetch' else build()
