"""Acquire and audit exact-run FLEX-2 input evidence without filling missing labels."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
import json
import math
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

from flex2_data import ROOT, file_tree, read, rows, sha, signed

REPORTS=Path(__file__).parent/'reports'
SUFFIXES=['_MDCA_Testpoint_Settings.txt','_Comments.txt','_Event_Log_entry.docx','_HIBMS_Camera_Settings.txt']
EVIDENCE=REPORTS/'flex2-input-evidence.json'


def fetch():
    nodes=file_tree()
    records=json.loads((ROOT/'manifest.json').read_text())['records']
    def one(r):
        out=[]
        for suffix in SUFFIXES:
            found=[n for n in nodes if Path(n['key']).name.endswith(r['run']+suffix)]
            if len(found)!=1 or found[0].get('restricted'):
                out.append(dict(run=r['run'],suffix=suffix,error='Missing/ambiguous/restricted'));continue
            node=found[0];p=ROOT/r['run']/Path(node['key']).name
            try:
                if not p.exists():p.write_bytes(read(signed(p.name),2_000_000))
                raw=p.read_bytes()
                if suffix.endswith('.docx'):
                    with zipfile.ZipFile(p) as z:doc=ET.fromstring(z.read('word/document.xml'))
                    text='\n'.join(''.join(t.itertext()) for t in doc.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'))
                else:text=raw.decode('utf-8-sig')
                out.append(dict(run=r['run'],file=p.name,resource_id=node['id'],version=node['version'],sha256=sha(raw),text=text))
            except Exception as e:out.append(dict(run=r['run'],suffix=suffix,error=str(e)))
        print(r['run'],flush=True);return out
    with ThreadPoolExecutor(max_workers=4) as pool:out=[x for group in pool.map(one,records) for x in group]
    (ROOT/'input-metadata-search.json').write_text(json.dumps(out,indent=2))


def setting_values(run,text):
    table=rows(text)
    if len(table)!=1 or table[0].get('TEST_POINT_DESIGNATOR(N/A)')!=run:
        return dict(status='rejected_run_id',fiber_usage_flag=None,igniter_power_setting_w=None,flow_nozzle_setting=None)
    r=table[0];fiber=r.get('TP_PARAMETER_FIBER_USAGE_FLAG(N/A)')
    try:
        power=float(r['TP_PARAMETER_IGNITER_WATTAGE(Watts)'])
        if not math.isfinite(power) or power<=0:power=None
    except (KeyError,ValueError):power=None
    return dict(status='exact_run_match',fiber_usage_flag={'Yes':True,'No':False}.get(fiber),
        igniter_power_setting_w=power,flow_nozzle_setting=r.get('FLOW_NOZZLE_1_SPEED(N/A)'))


def reported_gas(record,evidence):
    for assertion in evidence['assertions']:
        if record['run'] in assertion['run_ids'] and record['fuel']==assertion['catalog_fuel']:
            return dict(oxygen_mole_fraction=assertion['oxygen_mole_fraction'],
                nitrogen_mole_fraction=assertion['nitrogen_mole_fraction'],source=assertion['source_url'],
                status='reported_condition_exact_run_and_fuel_match',uncertainty=None)
    return dict(oxygen_mole_fraction=None,nitrogen_mole_fraction=None,source=None,status='not_verified',uncertainty=None)


def audit():
    manifest=json.loads((ROOT/'manifest.json').read_text())
    inventory=json.loads((ROOT/'input-metadata-search.json').read_text())
    evidence=json.loads(EVIDENCE.read_text());records=[];sources=[]
    for item in inventory:
        if 'file' in item:
            raw=(ROOT/item['run']/item['file']).read_bytes()
            if sha(raw)!=item['sha256']:raise ValueError('Metadata checksum mismatch: '+item['file'])
            sources.append({k:v for k,v in item.items() if k!='text'})
        else:sources.append(item)
    for r in manifest['records']:
        for m in r['metadata']:
            if m['file'].endswith(r['run']+'.txt'):
                if sha((ROOT/r['run']/m['file']).read_bytes())!=m['sha256']:
                    raise ValueError('Event-summary checksum mismatch: '+m['file'])
                sources.append(dict(run=r['run'],**m,kind='event_summary'))
        items=[x for x in inventory if x['run']==r['run']]
        setting=next((x for x in items if x.get('file','').endswith('_MDCA_Testpoint_Settings.txt')),None)
        values=setting_values(r['run'],setting['text']) if setting else dict(status='missing_settings',fiber_usage_flag=None,igniter_power_setting_w=None,flow_nozzle_setting=None)
        gas=reported_gas(r,evidence)
        conflicts=[dict(source_url=a['source_url'],paper_fuel=a['paper_fuel'],catalog_fuel=r['fuel'])
                   for a in evidence['conflicting_assertions'] if r['run'] in a['run_ids'] and r['fuel']!=a['paper_fuel']]
        records.append(dict(run_id=r['run'],fuel=r['fuel'],split=r['split'],
            oxygen_mole_fraction=gas['oxygen_mole_fraction'],nitrogen_mole_fraction=gas['nitrogen_mole_fraction'],
            gas_source=gas['source'],gas_status=gas['status'],gas_uncertainty_mole_fraction=gas['uncertainty'],
            initial_diameter_mm=None,initial_diameter_uncertainty_mm=None,
            diameter_status='No exact-run spatial calibration and validated post-deployment initial-frame measurement',
            flow_m_s=None,flow_status='No calibrated velocity; N/A nozzle settings are not m/s',
            fiber_usage_flag=values['fiber_usage_flag'],igniter_power_setting_w=values['igniter_power_setting_w'],
            settings_status=values['status'],settings_source=setting['file'] if setting else None,
            raw_flow_nozzle_setting=values['flow_nozzle_setting'],source_conflict=bool(conflicts),source_conflicts=conflicts))
    if len({r['run_id'] for r in records})!=len(records):raise ValueError('Duplicate run IDs')
    pilot_path=ROOT/'input-investigation'/'backlit-pilot.json'
    pilots=json.loads(pilot_path.read_text()) if pilot_path.exists() else []
    for pilot in pilots:
        if pilot.get('timestamp_metadata'):
            m=pilot['timestamp_metadata'];p=pilot_path.parent/pilot['run']/m['file']
            if sha(p.read_bytes())!=m['sha256']:raise ValueError('Backlit timestamp checksum mismatch')
        for m in pilot.get('frames',[]):
            p=pilot_path.parent/pilot['run']/m['file']
            if sha(p.read_bytes())!=m['sha256']:raise ValueError('Backlit checksum mismatch')
    documents_path=ROOT/'input-investigation'/'documents-audit.json'
    documents=json.loads(documents_path.read_text()) if documents_path.exists() else []
    for document in documents:
        if sha((documents_path.parent/document['file']).read_bytes())!=document['sha256']:
            raise ValueError('Science/engineering document checksum mismatch')
    result=dict(source='PSI-68',dataset_sha256=sha((ROOT/'prepared.npz').read_bytes()),
        counts=dict(runs=len(records),metadata_sources=len([s for s in sources if 'file'in s]),
            metadata_unavailable=len([s for s in sources if 'error'in s]),
            oxygen=sum(r['oxygen_mole_fraction'] is not None for r in records),
            nitrogen=sum(r['nitrogen_mole_fraction'] is not None for r in records),
            initial_diameter_mm=0,flow_m_s=0,fiber_usage_flag=sum(r['fiber_usage_flag'] is not None for r in records),
            igniter_power_setting_w=sum(r['igniter_power_setting_w'] is not None for r in records)),
        records=records,sources=sources,backlit_pilot=pilots,documents=documents,
        limitations=['Reported gas conditions are not new sensor measurements; source gives no uncertainty.',
            'The ten matched heptane runs all have the same reported gas mixture; this alone cannot train oxygen sensitivity.',
            'Fiber usage is an apparatus setting; igniter wattage is a commanded setting, not measured flame power.',
            'Pre-ignition frames can show an attached liquid bridge. No pilot diameter is promoted to a physical initial diameter.',
            'Conflicting paper/catalog fuel identities remain unresolved; no model or dashboard labels are silently changed.'])
    REPORTS.mkdir(exist_ok=True)
    (REPORTS/'flex2-input-coverage.json').write_text(json.dumps(result,indent=2)+'\n')
    columns=['run_id','fuel','split','oxygen_mole_fraction','nitrogen_mole_fraction','gas_source','gas_status','gas_uncertainty_mole_fraction','initial_diameter_mm','initial_diameter_uncertainty_mm','diameter_status','flow_m_s','flow_status','fiber_usage_flag','igniter_power_setting_w','settings_status','settings_source','raw_flow_nozzle_setting','source_conflict']
    with (REPORTS/'flex2-inputs.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(records)
    print(json.dumps(result['counts'],indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['fetch','audit']);a=p.parse_args()
    fetch() if a.command=='fetch' else audit()
