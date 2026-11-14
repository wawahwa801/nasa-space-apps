"""Reproduce the recorded public downloads and verify SHA-256 hashes."""
import hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).parent
for item in json.loads((ROOT/'references/manifest.json').read_text())['downloads']:
    path=ROOT/item['path']
    if not path.exists():
        with urllib.request.urlopen(item['url'],timeout=60) as response:
            data=response.read(32*1024*1024+1)
        if len(data)>32*1024*1024:raise ValueError('Download exceeds 32 MiB cap')
        if hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Hash mismatch; inspect upstream revision before accepting')
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError(f'Hash mismatch: {path}')
    print('Verified',item['path'])
