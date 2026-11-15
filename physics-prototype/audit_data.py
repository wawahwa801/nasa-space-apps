"""Audit downloaded XLSX without treating sensor channels as spread labels."""
import hashlib,json,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).parent
p=ROOT/'data/saffire-sensors.xlsx';ns={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(p) as z:
    sheets=[s.attrib['name'] for s in ET.fromstring(z.read('xl/workbook.xml')).findall('x:sheets/x:sheet',ns)]
report={'investigation':'PSI-98','run_id':'SAFFIRE-I Sample 2 (team-supplied filename; channel interpretation unverified)','sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'sheets':sheets,'role':'Sensor workbook audit only; not calibrated or used as model input','missing':['matched surface ignition positions/times','material thermal properties','sensor geometry mapping','verified channel units','upstream reuse terms']}
(ROOT/'data/workbook-audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
