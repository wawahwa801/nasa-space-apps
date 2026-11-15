"""Verify the published retrieval library and matching trained CNN checkpoint."""
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from flex2_data import ROOT, ART, FIELDS
from flex2_model import load

REPO=Path(__file__).resolve().parent.parent
INDEX=REPO/'ml/reports/flex2-model-artifacts.json'
EXPECTED={
    'ml/data/flex2-study/prepared.npz',
    'ml/data/flex2-study/manifest.json',
    'ml/artifacts/flex2-study/selected.pt',
    'ml/artifacts/flex2-study/report.json',
}


def verify():
    release=json.loads(INDEX.read_text())
    paths=[entry['path'] for entry in release['files']]
    if len(paths)!=len(EXPECTED) or set(paths)!=EXPECTED:
        raise ValueError('Unexpected published artifact paths')
    for entry in release['files']:
        path=REPO/entry['path'];raw=path.read_bytes()
        if len(raw)!=entry['bytes'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']:
            raise ValueError('Published artifact checksum mismatch: '+entry['path'])
    manifest=json.loads((ROOT/'manifest.json').read_text())
    report=json.loads((ART/'report.json').read_text())
    net,saved=load()  # Existing loader uses torch.load(weights_only=True), then validates state_dict.
    if report!=saved['report']:raise ValueError('Checkpoint/report mismatch')
    dataset_hash=hashlib.sha256((ROOT/'prepared.npz').read_bytes()).hexdigest()
    if report['dataset_sha256']!=dataset_hash or release['dataset_sha256']!=dataset_hash:
        raise ValueError('Checkpoint/dataset mismatch')
    if manifest['fields']!=FIELDS or report['fields']!=FIELDS or manifest['fuels']!=report['fuels']:
        raise ValueError('Feature/fuel schema mismatch')
    records=manifest['records'];n=len(records)
    with np.load(ROOT/'prepared.npz',allow_pickle=False) as data:
        if data['images'].shape!=(n,256,256,3) or data['masks'].shape!=(n,256,256) or data['features'].shape!=(n,len(FIELDS)):
            raise ValueError('Unexpected prepared array shapes')
        if data['images'].dtype!=np.uint8 or not np.isfinite(data['features']).all():
            raise ValueError('Invalid image dtype or non-finite features')
        if len(set(data['groups'].tolist()))!=n:raise ValueError('Duplicate independent run IDs')
        for i,record in enumerate(records):
            if str(data['groups'][i])!=record['run'] or str(data['splits'][i])!=record['split']:
                raise ValueError('Prepared run/split mismatch')
            fuel=int(data['fuels'][i])
            if fuel<0 or fuel>=len(manifest['fuels']) or manifest['fuels'][fuel]!=record['fuel']:
                raise ValueError('Prepared fuel mismatch')
            if not np.allclose(data['features'][i],record['features'],rtol=1e-6,atol=1e-6):
                raise ValueError('Prepared feature mismatch')
        counts=dict(Counter(data['splits'].tolist()))
        if n!=100 or manifest['counts']['groups']!=n or manifest['counts']['pairs']!=n or counts!={'train':60,'validation':20,'test':20}:
            raise ValueError('Published 100-run split mismatch')
        if manifest['counts']!=report['counts'] or manifest['counts']['splits']!=counts:
            raise ValueError('Manifest/report counts mismatch')
        for split in counts:
            expected=data['groups'][data['splits']==split].tolist()
            if expected!=report['groups'][split]:raise ValueError('Reported split membership mismatch')
        training=data['features'][data['splits']=='train']
        low=training.min(0);scale=np.maximum(training.max(0)-low,1e-6)
        if not np.allclose(saved['low'].numpy(),low) or not np.allclose(saved['scale'].numpy(),scale):
            raise ValueError('Checkpoint normalization is inconsistent with training data')
    if sum(p.numel() for p in net.parameters())!=report['parameters']:
        raise ValueError('Checkpoint architecture/report mismatch')
    result=dict(runs=n,fuels=manifest['fuels'],splits=counts,selected_epoch=report['selected_epoch'],
        dataset_sha256=dataset_hash,files_verified=len(paths),qualified_for_promotion=report['qualified_for_promotion'])
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':verify()
