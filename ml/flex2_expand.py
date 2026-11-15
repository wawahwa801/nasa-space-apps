"""Combine the frozen 100-run library with verified new independent training runs.

Example:
  python ml/flex2_expand.py --candidates /path/to/expanded-candidate-cache \
      --evidence /path/to/flex2-inputs.csv --target-runs 140

Original validation/test membership is frozen. New runs are added to training only.
"""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

import numpy as np

from flex2_data import ROOT


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def expand(candidates,evidence,target_runs=140,out=None,run_cache=None):
    candidates=Path(candidates);evidence=Path(evidence);out=Path(out or ROOT.parent/'flex2-expanded')
    run_cache=Path(run_cache or candidates)
    base_npz=np.load(ROOT/'prepared.npz');base=json.loads((ROOT/'manifest.json').read_text())
    cand_npz=np.load(candidates/'prepared.npz');cand=json.loads((candidates/'manifest.json').read_text())
    rows={r['run_id']:r for r in csv.DictReader(evidence.open(newline=''))}
    if target_runs<=len(base_npz['groups']) or target_runs>len(base_npz['groups'])+len(cand_npz['groups']):
        raise ValueError('Target must extend the base and fit available candidate rows')
    if base['fuels']!=cand['fuels']:raise ValueError('Fuel-index schemas differ')
    base_ids=set(base_npz['groups'].astype(str));cand_ids=cand_npz['groups'].astype(str)
    if len(base_ids)!=len(base_npz['groups']) or len(set(cand_ids))!=len(cand_ids):raise ValueError('Duplicate run IDs in source datasets')
    extra_count=target_runs-len(base_ids);records={r['run']:r for r in cand['records']}
    valid=[]
    for i,run in enumerate(cand_ids):
        run=str(run)
        if run in base_ids:continue
        row=rows.get(run)
        if not row or row['settings_status']!='exact_run_match' or row['fiber_usage_flag'] not in ('True','False'):
            continue
        if not np.isfinite(cand_npz['images'][i]).all():raise ValueError('Non-finite target image: '+run)
        valid.append(i)
    if len(valid)<extra_count:raise ValueError(f'Only {len(valid)} new exact-settings image targets; need {extra_count}')
    # Candidate preparation pressure-spreads across fuels; stable ordering keeps selection reproducible.
    selected=valid[:extra_count]
    fields=('features','fuels','images','masks','groups')
    payload={k:np.concatenate([base_npz[k],cand_npz[k][selected]],axis=0) for k in fields}
    old_splits=base_npz['splits'].astype(str);new_splits=np.asarray(['train']*len(selected))
    payload['splits']=np.concatenate([old_splits,new_splits])
    merged_records=[dict(r) for r in base['records']]
    for i in selected:
        r=dict(records[str(cand_ids[i])]);r['split']='train';merged_records.append(r)
    out.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out/'prepared.npz',**payload)
    manifest=dict(base,records=merged_records,target_runs=target_runs,
        split='Original validation/test run IDs frozen; new independently verified targets assigned to training.',
        counts=dict(pairs=target_runs,groups=target_runs,
            splits={s:int(np.sum(payload['splits']==s)) for s in ('train','validation','test')}),
        expansion=dict(base_manifest_sha256=sha(ROOT/'manifest.json'),candidate_manifest_sha256=sha(candidates/'manifest.json'),
            candidate_input_evidence_sha256=sha(evidence),added_run_ids=[str(cand_ids[i]) for i in selected],
            new_runs_are_independent=True))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    out_rows=[];on_time_joined=0
    for r in rows.values():
        if r['run_id'] in set(payload['groups'].astype(str)):
            r=dict(r);run=r['run_id'];r['split']=str(payload['splits'][list(payload['groups'].astype(str)).index(run)])
            rec=next(record for record in merged_records if record['run']==run)
            summary=next(m for m in rec['metadata'] if Path(m['file']).name.endswith(run+'.txt'))
            source=run_cache/run/summary['file'];raw=source.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=summary['sha256']:raise ValueError('Run-summary checksum mismatch: '+run)
            text=raw.decode('utf-8-sig')
            id_ok=bool(re.search(r'Test Point:\s*'+re.escape(run)+r'\b',text))
            duration=re.search(r'Igniter On Time \(milliseconds\):\s*([\d.]+)',text)
            seconds=float(duration.group(1))/1000 if id_ok and duration else None
            if seconds is not None and seconds>0:on_time_joined+=1
            r['igniter_on_time_s']=seconds;r['igniter_on_time_status']='exact_run_match' if seconds is not None and seconds>0 else 'not_verified'
            r['igniter_on_time_source']=summary['file'] if seconds is not None else ''
            out_rows.append(r)
    columns=list(out_rows[0])
    with (out/'features.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,lineterminator='\n');w.writeheader();w.writerows(out_rows)
    report={'target_count':target_runs,'base_count':len(base_ids),'added_count':len(selected),
        'counts_by_fuel':{name:int(np.sum(payload['fuels']==i)) for i,name in enumerate(base['fuels'])},
        'splits':manifest['counts']['splits'],'target_sha256':sha(out/'prepared.npz'),
        'manifest_sha256':sha(out/'manifest.json'),'feature_evidence_sha256':sha(out/'features.csv'),
        'added_run_ids':manifest['expansion']['added_run_ids'],'igniter_on_time_exact_run_joins':on_time_joined}
    (out/'expansion-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidates',required=True);p.add_argument('--evidence',required=True);p.add_argument('--target-runs',type=int,default=140);p.add_argument('--out');p.add_argument('--run-cache');a=p.parse_args()
    print(json.dumps(expand(a.candidates,a.evidence,a.target_runs,a.out,a.run_cache),indent=2))
