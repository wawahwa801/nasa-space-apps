"""NASA FLEX/FLEX-2 conditions ingestion; no invented image pairing."""
import csv
from io import StringIO
import hashlib
import json

from flame import DATA
from multisource_data import acquire

RELEASES={'PSI-69':('FLEX','PSI-69_Experimental table_FLEX.csv'),
          'PSI-68':('FLEX-2','PSI-68_Experimental table_Flex2.csv')}


def fetch():
    folder=DATA/'flex';folder.mkdir(exist_ok=True);releases=[]
    for accession,(label,filename) in RELEASES.items():
        path=acquire(accession,filename);raw=path.read_bytes()
        try:text=raw.decode('utf-8-sig');encoding='utf-8-sig'
        except UnicodeDecodeError:text=raw.decode('cp1252');encoding='cp1252'
        reader=csv.DictReader(StringIO(text));rows=[]
        for record in reader:
            if any(str(v or '').strip() for v in record.values()):
                rows.append({str(k).strip():str(v or '').strip() for k,v in record.items() if k is not None})
        meta=json.loads((path.parent/'catalog.json').read_text())
        assets=[];scope='release-change metadata only'
        if accession=='PSI-69':
            from flex_images import file_tree,entries,ROOT
            assets=[f['key'] for f in entries(file_tree()) if f['key'].lower().endswith(('.mp4','.mpg','.avi','.jpg','.jpeg','.png','.zip')) and '/metadata/' not in f['key']]
            scope='full public /files/v2 listing'
        matched=[]
        study=DATA/'flex'/'study'
        if accession=='PSI-69' and study.exists():
            for selection in study.glob('*/selection.json'):
                matched.append(json.loads(selection.read_text())['run'])
        release=dict(accession=accession,label=label,source=f'https://psi.nasa.gov/physci/repo/data/investigations/{accession}',
            source_file=filename,sha256=hashlib.sha256(raw).hexdigest(),encoding=encoding,
            license=meta.get('licenseName'),columns=list(rows[0]) if rows else [],rows=rows,
            raw_asset_listing_scope=scope,raw_asset_count=len(assets),matched_image_runs=matched,
            image_training_eligible=bool(matched),
            limitation='FLEX camera-B methanol imagery is joined only for selected verified run IDs; other table rows and FLEX-2 are conditions-only in this prototype. Release-change metadata is not a complete raw-file inventory.')
        releases.append(release);print(label,'conditions rows',len(rows),'columns',release['columns'],flush=True)
    (folder/'conditions.json').write_text(json.dumps(releases,indent=2))


if __name__=='__main__':fetch()
