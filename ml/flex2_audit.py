"""Reproducible coverage and candidate-feature audit; no inferred physical labels."""
from collections import Counter
from datetime import timedelta
import json
from pathlib import Path

import numpy as np

from flex2_data import ROOT, FIELDS, rows, sha, stamp


def audit():
    manifest=json.loads((ROOT/'manifest.json').read_text())
    records=manifest['records']
    if len(records)!=100 or len({r['run'] for r in records})!=100:
        raise ValueError('The 100-run audit requires exactly 100 independent runs')
    stability=[]
    for r in records:
        folder=ROOT/r['run']
        for m in r['metadata']+r['members']:
            if sha((folder/m['file']).read_bytes())!=m['sha256']:
                raise ValueError('Source hash mismatch: '+r['run']+'/'+m['file'])
        chamber=next(m for m in r['metadata'] if m['file'].endswith('_Chamber_Readings.txt'))
        before=[v for v in rows((folder/chamber['file']).read_text())
                if stamp(r['ignition'])-timedelta(seconds=5)<=stamp(v['FCU TimeStamp'])<stamp(r['ignition'])]
        p=np.array([[float(v[f'FCU_MP_PT{k}(PSIA)']) for k in [16,17,28,29]] for v in before])*6.894757293
        t=np.array([[float(v[f'FCU_MP_TM{k}(Deg C)']) for k in [1,2,3,4]] for v in before])
        stability.append(dict(run=r['run'],preignition_samples=len(before),
            pressure_temporal_std_kpa=float(p.mean(1).std()),temperature_temporal_std_c=float(t.mean(1).std()),
            pressure_channel_spread_kpa=float(np.ptp(p.mean(0))),temperature_channel_spread_c=float(np.ptp(t.mean(0)))))
    coverage={}
    for fuel in manifest['fuels']:
        group=[r for r in records if r['fuel']==fuel]
        x=np.array([r['features'] for r in group])
        coverage[fuel]=dict(runs=len(group),splits=dict(Counter(r['split'] for r in group)),
            ranges={key:dict(min=float(x[:,j].min()),max=float(x[:,j].max())) for j,key in enumerate(FIELDS)},
            distinct_pressure_temperature_pairs=len(set(tuple(r['features']) for r in group)))
    camera={}
    for key in ['ZOOM_POSITION(N/A)','EXPOSURE_MODE(N/A)','SHUTTER_POSITION(N/A)','GAIN_POSITION(N/A)','WBMODE(N/A)','RGAIN(N/A)','BGAIN(N/A)']:
        values=[r['camera_settings'][0].get(key) if r['camera_settings'] else None for r in records]
        camera[key]=dict(available=sum(v is not None for v in values),values=dict(Counter(v for v in values if v is not None)))
    data=np.load(ROOT/'prepared.npz')
    image_quality=[dict(run=r['run'],weak_mask_pixels=int(data['masks'][i].sum()),
        saturated_pixel_fraction=float((data['images'][i].max(2)==255).mean())) for i,r in enumerate(records)]
    result=dict(source='PSI-68',dataset_sha256=sha((ROOT/'prepared.npz').read_bytes()),counts=manifest['counts'],
        verification='Exact run/category joins, pre-ignition telemetry, RGB24 source geometry, selected ZIP CRC at acquisition and cached metadata/frame SHA256; fixed ROI connected-colour screening. Not physical validation or certified steady states.',
        coverage=coverage,campaigns=dict(Counter(r['category'] for r in records)),
        exclusions=manifest['excluded'],camera_settings=camera,telemetry_quality=stability,image_quality=image_quality,
        candidate_features=[
            dict(feature='Pre-ignition temporal stability and sensor spread',status='Available for all accepted runs',use='Quality flags or optional ablation; sensor differences may be spatial offsets, not uncertainty estimates'),
            dict(feature='Camera zoom, exposure, gain and white balance',status='Coverage and raw values above',use='Stratified evaluation or nuisance covariates after checking settings semantics; not physical slider inputs'),
            dict(feature='Acquisition date/campaign',status='Available in event timestamps and category',use='Grouped holdout evaluation to detect campaign leakage; not a physical control'),
            dict(feature='Oxygen fraction, initial droplet diameter, ambient gas composition and airflow',status='Not verified by these chamber/camera records',use='Keep absent until exact-run authoritative labels are joined; tracked in issue #18')],
        evaluation_note='Independent run count is not unique physical-state coverage. Whole-run splits do not prevent same-day/campaign confounding. Repeated frames are never counted as independent states.')
    report_dir=Path(__file__).parent/'reports'
    report_dir.mkdir(exist_ok=True)
    path=report_dir/'flex2-100-audit.json'
    (report_dir/'flex2-100-data.json').write_text(json.dumps(manifest,indent=2)+'\n')
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(counts=result['counts'],coverage=coverage,campaigns=result['campaigns']),indent=2))
    return result


if __name__=='__main__':audit()
