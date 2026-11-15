"""Bounded backlit feasibility pilot: two runs per fuel, no calibrated diameter claim."""
import argparse,json,zipfile
from pathlib import Path
from io import BytesIO
from datetime import timedelta,datetime
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import flex2_data as f
from flex_images import RangeFile
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--documents-only',action='store_true',help='Acquire only science/engineering PDFs and their provenance')
args=parser.parse_args()
nodes=f.file_tree();outdir=f.ROOT/'input-investigation';outdir.mkdir(exist_ok=True)
docs=[n for n in nodes if 'Science Documents' in n['key'] and n['key'].endswith('.pdf') or 'Engineering Requirments Document.pdf' in n['key']]
document_sources=[]
for n in docs:
    p=outdir/Path(n['key']).name
    if not p.exists():p.write_bytes(f.read(f.signed(p.name),3_000_000))
    document_sources.append(dict(file=p.name,resource_id=n['id'],version=n['version'],sha256=f.sha(p.read_bytes())))
    print('Document',p.name,flush=True)
(outdir/'documents-audit.json').write_text(json.dumps(document_sources,indent=2))
if args.documents_only:raise SystemExit(0)
records=json.loads((f.ROOT/'manifest.json').read_text())['records'];pilots=[]
for fuel in sorted({r['fuel'] for r in records}):
    group=[r for r in records if r['fuel']==fuel]
    pilots.extend(group[i] for i in sorted({0,len(group)-1}))
def one(r):
    run=r['run'];folder=outdir/run;folder.mkdir(exist_ok=True)
    result=dict(run=run,fuel=r['fuel'],initial_diameter_mm=None,calibration_status='No exact-run spatial calibration verified')
    try:
        n,=[n for n in nodes if Path(n['key']).name.endswith(run+'A.zip') and not n.get('restricted')]
        result.update(archive=Path(n['key']).name,resource_id=n['id'],version=n['version'])
        stream=RangeFile(f.signed(result['archive']))
        with zipfile.ZipFile(stream) as z:
            raw=z.read(run+'A.txt');(folder/'timestamps.txt').write_bytes(raw)
            result['timestamp_metadata']=dict(file='timestamps.txt',source_member=run+'A.txt',sha256=f.sha(raw))
            table=f.rows('\n'.join(raw.decode('utf-8-sig').splitlines()[2:]));names=set(z.namelist());selected=[]
            for offset in [-1.,-.5,-.1]:
                requested=f.stamp(r['ignition'])+timedelta(seconds=offset)
                row=min(table,key=lambda v:abs((datetime.strptime(v['Date']+' '+v['MTimeStamp'],'%m/%d/%Y %H:%M:%S.%f')-requested).total_seconds()))
                time=datetime.strptime(row['Date']+' '+row['MTimeStamp'],'%m/%d/%Y %H:%M:%S.%f')
                if abs((time-requested).total_seconds())>.08:raise ValueError('Pre-ignition frame absent')
                matches=[m for m in names if m.rsplit('.',1)[0]==row['FileName']]
                if len(matches)!=1:raise ValueError('Ambiguous timestamp/image mapping')
                member=matches[0];p=folder/Path(member).name
                p.write_bytes(z.read(member))  # ZIP verifies source CRC on every acquisition.
                raw=p.read_bytes();im=Image.open(BytesIO(raw))
                if im.size!=(1024,1024) or im.mode not in ['I;16','I;16L','I;16B','I']:
                    raise ValueError('Unexpected backlit camera geometry or bit depth')
                selected.append(dict(file=p.name,timestamp=time.isoformat(),offset_before_ignition_s=offset,sha256=f.sha(raw),mode=im.mode,size=im.size))
            result.update(frames=selected,bytes_retrieved=stream.transferred)
    except Exception as e:result['error']=str(e)
    print(run,result.get('error','Selected pre-ignition frames'),flush=True);return result
with ThreadPoolExecutor(max_workers=3) as pool:pilots=list(pool.map(one,pilots))
(outdir/'backlit-pilot.json').write_text(json.dumps(pilots,indent=2))
