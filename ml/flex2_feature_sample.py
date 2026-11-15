"""Bounded metadata-only FLEX-2 feature survey beyond the current 100-run library."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import timedelta
import json
import math
from pathlib import Path
import re
import statistics

import numpy as np

from flex2_data import DATA, file_tree, read, rows, sha, signed, event, stamp

ROOT=DATA/'flex2-feature-sample'
REPORTS=Path(__file__).parent/'reports'
GAS_SOURCE='https://doi.org/10.1080/00102202.2025.2595114'
REPORTED_HEPTANE={'E066C01','E066C02','E066C03','E066C04','E073C01','E073C02','E073C03','E073C04','E073C07','E073C09','E087C01','E087C04','E087C06','E087C07'}
CATEGORIES=[
    'Reduced Gravity/Quiescent 2016 - Decane',
    'Reduced Gravity/SurrogateFuel 2013 - Heptane',
    'Reduced Gravity/SurrogateFuel 2012 - N_Octane',
    'Reduced Gravity/SurrogateFuel 2014 - IsoOctane',
    'Reduced Gravity/SurrogateFuel 2014 - Toluene',
    'Reduced Gravity/SurrogateFuel 2012 - Propylbenzene',
    'Reduced Gravity/SurrogateFuel 2014 - Heptane50_Toluene50',
    'Reduced Gravity/SurrogateFuel 2014 - Decane75_Propylbenzene25',
    'Reduced Gravity/Convective Flow 2012 - Decane',
    'Reduced Gravity/Binary Array 2015 - Decane',
    'Reduced Gravity/Binary Array 2014 - Ethanol',
    'Reduced Gravity/Condensed Phase 2016 - Propanol95_Glycerol5',
]
SUFFIXES=['.txt','_Chamber_Readings.txt','_MDCA_Testpoint_Settings.txt',
          '_MDCA_Color_Camera_Settings.txt','_Color_Camera_Settings.txt','_HIBMS_Camera_Settings.txt','_Comments.txt']


def select(nodes,excluded):
    result=[]
    for category in CATEGORIES:
        group={}
        for node in nodes:
            match=re.search(r'([A-Z]\d{3}[A-Z]\d{2})D\.zip$',node['key'])
            if match and node.get('subcategory')==category and not node.get('restricted') and match[1] not in excluded:
                group[match[1]]=node
        ids=sorted(group)
        if len(ids)<4:raise ValueError('Fewer than four additional candidates for '+category)
        for i in np.linspace(0,len(ids)-1,4).astype(int):
            result.append(dict(run=ids[i],category=category,archive_resource_id=group[ids[i]]['id']))
    if len(result)!=48 or len({r['run'] for r in result})!=48:raise ValueError('Sample count/independence mismatch')
    return result


def fetch():
    nodes=file_tree()
    release=json.loads((REPORTS/'flex2-100-data.json').read_text())
    excluded={r['run'] for r in release['records']}
    selected=select(nodes,excluded);ROOT.mkdir(parents=True,exist_ok=True)
    def acquire(record):
        folder=ROOT/record['run'];folder.mkdir(exist_ok=True);sources=[]
        for suffix in SUFFIXES:
            found=[n for n in nodes if Path(n['key']).name.endswith(record['run']+suffix)]
            if len(found)!=1 or found[0].get('restricted'):
                sources.append(dict(suffix=suffix,status='missing_ambiguous_or_restricted'));continue
            node=found[0];p=folder/Path(node['key']).name
            try:
                if not p.exists():p.write_bytes(read(signed(p.name),2_000_000))
                raw=p.read_bytes()
                sources.append(dict(suffix=suffix,file=p.name,resource_id=node['id'],version=node['version'],
                    sha256=sha(raw),bytes=len(raw),status='available'))
            except Exception as error:sources.append(dict(suffix=suffix,status='error',reason=str(error)))
        record=dict(record,sources=sources);print(record['run'],record['category'],flush=True);return record
    with ThreadPoolExecutor(max_workers=4) as pool:inventory=list(pool.map(acquire,selected))
    (ROOT/'inventory.json').write_text(json.dumps(inventory,indent=2))


def number(text):
    try:
        value=float(text)
        return value if math.isfinite(value) else None
    except (ValueError,TypeError):return None


def audit():
    inventory=json.loads((ROOT/'inventory.json').read_text());records=[]
    raw_fields={};source_counts=Counter();keywords=[]
    for entry in inventory:
        sources={};texts={}
        for s in entry['sources']:
            source_counts[s['suffix']+'/'+s['status']]+=1
            if s['status']!='available':continue
            raw=(ROOT/entry['run']/s['file']).read_bytes()
            if sha(raw)!=s['sha256']:raise ValueError('Source hash mismatch: '+s['file'])
            texts[s['suffix']]=raw.decode('utf-8-sig');sources[s['suffix']]=s['file']
        r=dict(run=entry['run'],category=entry['category'],catalog_fuel=entry['category'].split(' - ')[-1],
            configuration=re.sub(r'\s+\d{4}$','',entry['category'].split(' - ')[0].split('/')[-1]),features={},status={})
        features=r['features'];text=texts.get('.txt','')
        joined=bool(re.search(r'Test Point:\s*'+re.escape(entry['run'])+r'\b',text))
        r['event_run_verified']=joined
        if joined:
            for label,key,scale in [('Igniter On Time (milliseconds)','igniter_duration_s',.001),('Igniter Wattage','event_igniter_power_w',1.),('Burn to Completion (milliseconds)','programmed_duration_s',.001)]:
                match=re.search(re.escape(label)+r':\s*([-\d.]+)',text)
                if match and number(match[1]) is not None and number(match[1])>0:features[key]=number(match[1])*scale
            try:
                ignition=event(text,'AS Burn to Completion/Igniter On');retraction=event(text,'AS Retract Completed')
                features['igniter_to_retraction_s']=(retraction-ignition).total_seconds()
                features['target_stage_since_ignition_s']=features['igniter_to_retraction_s']+4.15
                chamber=rows(texts.get('_Chamber_Readings.txt',''))
                window=[v for v in chamber if ignition-timedelta(seconds=5)<=stamp(v['FCU TimeStamp'])<ignition]
                if len(window)<3:raise ValueError('Fewer than three pre-ignition samples')
                p=np.array([[float(v[f'FCU_MP_PT{k}(PSIA)']) for k in [16,17,28,29]] for v in window])*6.894757293
                t=np.array([[float(v[f'FCU_MP_TM{k}(Deg C)']) for k in [1,2,3,4]] for v in window])
                if not np.isfinite(p).all() or not np.isfinite(t).all():raise ValueError('Non-finite telemetry')
                features.update(pressure_kpa=float(p.mean()),temperature_c=float(t.mean()),
                    pressure_temporal_std_kpa=float(p.mean(1).std()),temperature_temporal_std_c=float(t.mean(1).std()))
                r['preignition_samples']=len(window)
            except (KeyError,ValueError) as error:r['status']['telemetry']=str(error)
        settings=rows(texts.get('_MDCA_Testpoint_Settings.txt',''))
        valid=len(settings)==1 and settings[0].get('TEST_POINT_DESIGNATOR(N/A)')==entry['run']
        r['settings_run_verified']=valid
        if valid:
            s=settings[0]
            for column,key in [('TP_PARAMETER_FIBER_USAGE_FLAG(N/A)','fiber_usage'),('TP_PARAMETER_SOOT_SAMPLER_USAGE_FLAG(N/A)','soot_sampler_usage'),('COLOR_CAMERA_ILLUMINATION_LIGHT_USAGE_FLAG(N/A)','illumination_usage')]:
                if s.get(column) in ['Yes','No']:features[key]=s[column]
            power=number(s.get('TP_PARAMETER_IGNITER_WATTAGE(Watts)'))
            if power is not None and power>0:features['igniter_power_setting_w']=power
        for suffix in ['_MDCA_Testpoint_Settings.txt','_MDCA_Color_Camera_Settings.txt','_HIBMS_Camera_Settings.txt','_Color_Camera_Settings.txt']:
            table=rows(texts.get(suffix,''))
            if not table:continue
            for key,value in table[0].items():
                # Include all observed fields in the machine-readable audit, even ambiguous codes.
                field=suffix+':'+key
                raw_fields.setdefault(field,[]).append(dict(run=entry['run'],value=value))
                if suffix=='_MDCA_Color_Camera_Settings.txt' and key in ['ZOOM_POSITION(N/A)','EXPOSURE_MODE(N/A)','SHUTTER_POSITION(N/A)','GAIN_POSITION(N/A)','WBMODE(N/A)','RGAIN(N/A)','BGAIN(N/A)','FOCUS_MODE(N/A)','APERTURE_GAIN(N/A)']:
                    features['camera_'+key]=value
        for suffix,text in texts.items():
            for line in text.splitlines():
                if re.search(r'oxygen|\bo2\b|diameter|\bcomposition\b|mm/pixel|m/s|cm/s',line,re.I):
                    keywords.append(dict(run=entry['run'],file=sources[suffix],line=line[:1500]))
        # Published conditions require an exact ID/fuel match; no range cross-products.
        r['reported_gas_condition']=dict(oxygen_mole_fraction=.21,nitrogen_mole_fraction=.79,
            source=GAS_SOURCE,uncertainty=None) if r['run'] in REPORTED_HEPTANE and r['catalog_fuel']=='Heptane' else None
        r['sources']=entry['sources'];records.append(r)
    feature_summary={}
    for key in sorted({key for r in records for key in r['features']}):
        values=[r['features'][key] for r in records if key in r['features']]
        stats=dict(available=len(values),distinct=len(set(values)))
        if all(isinstance(v,(float,int)) for v in values):stats.update(min=min(values),max=max(values))
        else:stats['values']=dict(Counter(values))
        feature_summary[key]=stats
    raw_summary={key:dict(available=len(values),distinct=len({v['value'] for v in values}),values=dict(Counter(v['value'] for v in values))) for key,values in raw_fields.items()}
    study_sources=[]
    for filename in ['catalog.json','PSI-68_Experimental table_Flex2.csv']:
        path=ROOT/filename
        if path.exists():study_sources.append(dict(file=filename,sha256=sha(path.read_bytes()),bytes=path.stat().st_size))
    existing=json.loads((REPORTS/'flex2-100-data.json').read_text())['records']
    elapsed=[statistics.median((stamp(m['timestamp'])-stamp(r['ignition'])).total_seconds() for m in r['members']) for r in existing]
    report=dict(sample=dict(runs=len(records),campaigns=len(CATEGORIES),runs_per_campaign=4,
            excludes_published_100=True,selection='Four evenly spaced run IDs per prespecified campaign; metadata only, no image-quality preselection',
            statistical_significance_tested=False,stopping_rule='Fixed cap of 48 additional runs and seven small files per run; no image archives'),
        campaigns=dict(Counter(r['category'] for r in records)),source_counts=dict(source_counts),
        total_metadata_bytes=sum(s.get('bytes',0) for r in records for s in r['sources']),
        feature_summary=feature_summary,raw_field_summary=raw_summary,keyword_hits=keywords,records=records,
        catalog_fuels=dict(Counter(r['catalog_fuel'] for r in records)),
        configurations=dict(Counter(r['configuration'] for r in records)),study_sources=study_sources,
        existing_library_median_frame_seconds_since_igniter_on=dict(runs=len(elapsed),min=min(elapsed),max=max(elapsed)),
        reported_gas_matches=[r['run'] for r in records if r['reported_gas_condition']],
        interpretation=['This is an availability/variation screen, not an outcome-based feature-importance or causal analysis.',
            'No new image targets were downloaded or visually qualified; failed/restricted/mismatched metadata remain explicit.',
            'target_stage_since_ignition_s is a hypothetical proxy at 4.15s after retraction, not a newly sampled image timestamp or measured flame onset.',
            'Camera enum 0.0 and device position/gain codes remain raw; distinct encodings do not establish distinct physical settings.',
            'The small official summary describes possible values/ranges, not an exact-run label table. Do not assign combinations to runs.',
            'All sampled campaigns are catalogued Reduced Gravity; no gravity-response feature was established.',
            'Catalog fuel identities and nominal mixture ratios remain subject to issue #33; mixture percentage basis is not inferred.'])
    (REPORTS/'flex2-feature-sample.json').write_text(json.dumps(report,indent=2)+'\n')
    columns=['run','category','catalog_fuel','configuration','event_run_verified','settings_run_verified']+list(feature_summary)
    with (REPORTS/'flex2-feature-sample.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='ignore');writer.writeheader()
        for r in records:writer.writerow(dict(r,**r['features']))
    print(json.dumps(dict(sample=report['sample'],source_counts=report['source_counts'],feature_summary=feature_summary,total_metadata_bytes=report['total_metadata_bytes']),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['fetch','audit']);args=p.parse_args()
    fetch() if args.command=='fetch' else audit()
