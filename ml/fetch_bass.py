"""Download five small unrestricted BASS-II trials and their public conditions table."""
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent / 'data'
BASE = 'https://psi.nasa.gov/geode-py/ws'
FILES = ['PSI-25_Raw Data_BASS_GMT50_SAMPLE_147_TEST_B1.mp4',
         'PSI-25_Raw Data_BASS_GMT50_SAMPLE_148_TEST_B3.mp4',
         'PSI-25_Experimental table_BASS-II.csv',
         'PSI-25_Raw Data_BASS_GMT50_SAMPLE_159_TEST_B4.mp4',
         'PSI-25_Raw Data_BASS_GMT50_SAMPLE_156_TEST_B5.mp4',
         'PSI-25_Raw Data_BASS_GMT50_SAMPLE_160_TEST_B12.mp4']


def read(url, limit):
    with urlopen(url, timeout=60) as response:
        data = response.read(limit+1)
    if len(data) > limit:
        raise ValueError('Download exceeds size cap')
    return data


def main():
    ROOT.mkdir(exist_ok=True)
    catalog = json.loads(read(BASE+'/repo/investigations/PSI-25', 5_000_000))
    (ROOT/'bass-catalog.json').write_text(json.dumps(catalog, indent=2))
    entries = {f['file_name']: f for f in catalog['added'] + catalog['experimentalTable']}
    selected = []
    for name in FILES:
        entry = entries[name]
        if entry.get('restricted') or entry['file_size'] > 15_000_000:
            raise ValueError('File is restricted or too large')
        target = ROOT/name
        if not target.exists():
            query = urlencode({'file': name, 'redirect': 'false'})
            signed = read(BASE+'/studies/PSI-25/download?'+query, 20000).decode().strip().strip('"')
            target.write_bytes(read(signed, 15_000_000))
        selected.append({k:entry.get(k) for k in ['file_name','file_size','version','subcategory','restricted']})
        print('Ready:',name)
    (ROOT/'bass-selection.json').write_text(json.dumps(dict(source=BASE+'/repo/investigations/PSI-25',
        license=catalog['licenseName'], files=selected), indent=2))


if __name__ == '__main__':
    main()
