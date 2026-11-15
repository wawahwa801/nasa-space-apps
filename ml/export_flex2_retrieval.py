"""Export verified FLEX-2 retrieval evidence for the standalone Next.js frontend.

Uses prepared image/feature pairs, not a trained CNN or a running model service.
"""
import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

import numpy as np
from PIL import Image

from flame_display import centre_flame


def export(data_path, output):
    manifest=json.loads((data_path/'manifest.json').read_text())
    d=np.load(data_path/'prepared.npz',allow_pickle=False)
    if manifest['source']!='PSI-68' or manifest['fields']!=['pressure_kpa','temperature_c']:
        raise ValueError('Expected verified FLEX-2 pressure/temperature pairs')
    if len(manifest['records'])!=len(d['images']):raise ValueError('Manifest/image count mismatch')
    train=d['splits']=='train'
    if not train.any():raise ValueError('Training subset required for existing retrieval normalization')
    scale=np.maximum(np.ptp(d['features'][train],axis=0),1e-6)
    records=[];output.mkdir(parents=True,exist_ok=True)
    for i,r in enumerate(manifest['records']):
        if r['run']!=str(d['groups'][i]) or r['fuel']!=manifest['fuels'][int(d['fuels'][i])]:
            raise ValueError('Run/fuel join mismatch')
        if d['images'][i].shape!=(256,256,3):raise ValueError('Expected 256px RGB targets')
        if not np.isfinite(d['features'][i]).all():raise ValueError('Nonfinite physical feature')
        shown,alignment=centre_flame(d['images'][i])
        stream=BytesIO();Image.fromarray(shown).save(stream,format='PNG')
        raw=stream.getvalue();name=r['run']+'.png';(output/name).write_bytes(raw)
        records.append(dict(id=r['run'],fuel=r['fuel'],features={k:float(d['features'][i,j]) for j,k in enumerate(manifest['fields'])},
            image='/flames/flex2/'+name,image_sha256=sha256(raw).hexdigest(),split=r['split'],
            archive=r['archive'],archive_version=r['archive_version'],source_category=r['category'],
            members=r['members'],display_alignment=alignment))
    fuels=[]
    for fuel in manifest['fuels']:
        values=[r for r in records if r['fuel']==fuel]
        default=next(r for r in values if r['split']=='train')
        fuels.append(dict(name=fuel,count=len(values),defaults=default['features'],
            ranges={k:dict(min=min(r['features'][k] for r in values),max=max(r['features'][k] for r in values)) for k in manifest['fields']}))
    index=dict(version='flex2-retrieval-v1',source='PSI-68',source_url=manifest['source_url'],license='CC0-1.0',
        resolution=256,count=len(records),scale=scale.astype(float).tolist(),
        fields=[dict(key=k,label=label,unit=unit) for k,label,unit in zip(manifest['fields'],['Chamber pressure','Chamber temperature'],['kPa','°C'])],
        fuels=fuels,records=records,features_note=manifest['features_note'],stage=manifest['stage'],
        preprocessing=manifest['preprocessing'],
        prepared_sha256=sha256((data_path/'prepared.npz').read_bytes()).hexdigest(),
        matching='Exact fuel; lowest sum of squared feature differences normalized by the original training-subset feature ranges. All verified targets are searchable.',
        display_note='Detected luminous region translated to centre without scaling or recolouring. Alignment is approximate; weak detections retain position.',
        limitation='Selected microgravity droplet experiments, not the full FLEX-2 dataset. Missing per-run oxygen/droplet-size labels and camera/stage variation prevent a causal or calibrated fire prediction.')
    (output/'index.json').write_text(json.dumps(index,indent=2,sort_keys=True)+'\n')
    print(f'Exported {len(records)} FLEX-2 targets; {sum(p.stat().st_size for p in output.glob("*.png")):,} image bytes')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=Path(__file__).parent/'data'/'flex2-study')
    p.add_argument('--output',type=Path,default=Path(__file__).parent.parent/'frontend'/'public'/'flames'/'flex2')
    a=p.parse_args();export(a.data,a.output)
