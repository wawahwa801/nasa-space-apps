"""Exactly joined NASA SPICE still/condition pairs, with ignition-group splits."""
import argparse
from collections import Counter
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlencode
import zipfile

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps
import xlrd

from flame import DATA, OUT
from multisource_data import BASE, read

ROOT = DATA / 'spice-study'
ART = OUT / 'spice-study'
SOURCE = DATA / 'multi' / 'PSI-107'
SIZE = 256
FIELDS = ['nozzle_mm', 'fuel_sccm', 'air_cm_s']
ARCHIVES = {
    45: 'PSI-107_Raw Data_SPICE GMT045 2009 jpegs.zip',
    48: 'PSI-107_Raw Data_SPICE GMT048 2009 jpegs.zip',
    52: 'PSI-107_Raw Data_SPICE_GMT052_2009_jpegs.zip',
    55: 'PSI-107_Raw Data_SPICE_GMT2009_055_jpeg.zip',
    62: 'PSI-107_Raw Data_SPICE_GMT2009_062_jpegs.zip',
}
BOOK = 'PSI-107_Raw Data_Spice Flight Test Data II modified.xls'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fetch():
    SOURCE.mkdir(parents=True, exist_ok=True)
    catalog = SOURCE / 'catalog.json'
    if not catalog.exists():
        catalog.write_bytes(read(BASE + '/repo/investigations/PSI-107', 8_000_000))
    meta = json.loads(catalog.read_text())
    files = {f['file_name']: f for k in ['added', 'modified', 'experimentalTable'] for f in meta.get(k, [])}
    for name in [BOOK, *ARCHIVES.values()]:
        entry = files[name]
        if entry.get('restricted') or float(entry['file_size']) > 160_000_000:
            raise ValueError('Restricted file or acquisition budget exceeded')
        path = SOURCE / name
        if not path.exists():
            signed = read(BASE + '/studies/PSI-107/download?' + urlencode({'file': name, 'redirect': 'false'}), 20_000).decode().strip().strip('"')
            raw = read(signed, 160_000_000)
            if len(raw) != int(float(entry['file_size'])):
                raise ValueError('Incomplete source download: ' + name)
            path.write_bytes(raw)
        print('Ready', name, flush=True)


def clock(value):
    if isinstance(value, (float, int)):
        return round(float(value) * 86400)
    parts = re.findall(r'\d+', str(value))
    if len(parts) != 3:
        raise ValueError('Missing/ambiguous ignition clock')
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])


def split_groups(records):
    """Split whole ignitions within fuel; no bracketing or neighboring frames leak."""
    mapping = {}
    for fuel in sorted({r['fuel'] for r in records}):
        groups = sorted({r['group'] for r in records if r['fuel'] == fuel}, key=lambda g: sha(('spice42/' + g).encode()))
        if len(groups) < 4:
            raise ValueError('Insufficient ignition groups for ' + fuel)
        n = max(1, round(len(groups) * .15))
        for j, group in enumerate(groups):
            mapping[group] = 'test' if j < n else 'validation' if j < 2*n else 'train'
    for r in records:
        r['split'] = mapping[r['group']]


def prepare():
    ROOT.mkdir(parents=True, exist_ok=True)
    sheet = xlrd.open_workbook(str(SOURCE / BOOK)).sheet_by_index(0)
    archives = {day: zipfile.ZipFile(SOURCE / name) for day, name in ARCHIVES.items()}
    indexes = {d: {Path(n).stem.upper(): n for n in z.namelist() if n.lower().endswith(('.jpg', '.jpeg'))} for d, z in archives.items()}
    records, images, masks, excluded = [], [], [], []
    seen = set()
    try:
        for i in range(4, sheet.nrows):
            row = sheet.row_values(i)
            try:
                day = int(float(row[0]))
            except (ValueError, TypeError):
                continue
            if day not in archives or not row[29]:
                continue
            try:
                if any(not isinstance(row[k], (int, float)) or not np.isfinite(row[k]) or row[k] <= 0 for k in [9, 17, 20]):
                    raise ValueError('Missing physical condition')
                names = str(row[29]).splitlines()
                ev = str(row[32]).splitlines()
                if len(names) != len(ev) or '-5' not in ev:
                    raise ValueError('No unambiguous -5 EV bracket')
                j = ev.index('-5')
                for k in [39, 40, 41]:
                    flags = str(row[k]).split('\n')
                    if j < len(flags) and flags[j].strip().lower() == 'y':
                        raise ValueError('Source marks selected bracket saturated')
                identifier = names[j].strip().upper()
                if identifier in seen:
                    raise ValueError('Duplicate source image')
                member = indexes[day].get(identifier)
                if member is None:
                    raise ValueError('Image ID not present in archive')
                ignition = clock(row[2])
                raw = archives[day].read(member)  # ZIP CRC verified here.
                image = Image.open(BytesIO(raw)).convert('RGB')
                if image.size != (3008, 2000):
                    raise ValueError('Unexpected camera geometry')
                # Fixed camera ROI, equal scale for all targets; no flame-dependent resize.
                # Retains the horizontal camera orientation and removes lower reflections.
                image = image.crop((150, 680, 2950, 1100))
                image = ImageOps.pad(image, (SIZE, SIZE), method=Image.Resampling.LANCZOS)
                array = np.array(image)
                hsv = cv2.cvtColor(array, cv2.COLOR_RGB2HSV)
                mask = ((hsv[:, :, 1] > 45) & (hsv[:, :, 2] > 40)).astype('uint8')
                count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
                if count < 2 or stats[1:, cv2.CC_STAT_AREA].max() < 5:
                    raise ValueError('No visible flame in fixed ROI')
                mask = (labels == (1 + stats[1:, cv2.CC_STAT_AREA].argmax())).astype('uint8')
                record = dict(id=identifier, excel_row=i+1, day=day, fuel=str(row[8]).strip(),
                    group=f'{day:03d}-ignition-{ignition}', features=[float(row[k]) for k in [9, 17, 20]],
                    pressure_pa=float(row[10]), exposure_bracket_ev=-5,
                    archive=ARCHIVES[day], member=member, image_sha256=sha(raw),
                    original_row=row, source='PSI-107')
                records.append(record); images.append(array); masks.append(mask); seen.add(identifier)
            except (ValueError, KeyError) as error:
                excluded.append(dict(excel_row=i+1, reason=str(error)))
    finally:
        for z in archives.values():
            z.close()
    # Identical physical conditions must not straddle evaluation splits either.
    # Union overlapping ignition/condition groups before assigning the final split.
    parent = {r['group']: r['group'] for r in records}
    def root(g):
        while parent[g] != g:
            parent[g] = parent[parent[g]]; g = parent[g]
        return g
    conditions = {}
    for r in records:
        key = (r['fuel'], *[round(v, 6) for v in r['features']])
        if key in conditions:
            parent[root(r['group'])] = root(conditions[key])
        conditions[key] = r['group']
    for r in records:
        r['ignition_group'] = r['group']; r['group'] = root(r['group'])
    supported = {fuel for fuel in {r['fuel'] for r in records}
        if len({r['group'] for r in records if r['fuel']==fuel}) >= 4}
    keep = [i for i,r in enumerate(records) if r['fuel'] in supported]
    excluded.extend(dict(excel_row=r['excel_row'],reason='Fuel has fewer than four usable ignition/condition groups')
        for r in records if r['fuel'] not in supported)
    records = [records[i] for i in keep]
    images = [images[i] for i in keep]; masks = [masks[i] for i in keep]
    split_groups(records)
    fuel_names = sorted({r['fuel'] for r in records})
    np.savez_compressed(ROOT / 'prepared.npz', images=np.array(images), masks=np.array(masks),
        features=np.array([r['features'] for r in records], dtype='float32'),
        fuels=np.array([fuel_names.index(r['fuel']) for r in records]),
        groups=np.array([r['group'] for r in records]), splits=np.array([r['split'] for r in records]))
    manifest = dict(source_url='https://psi.nasa.gov/physci/repo/data/investigations/PSI-107',
        license='CC0-1.0 (NASA PSI catalog)', fields=FIELDS, fuels=fuel_names, resolution=SIZE,
        preprocessing=dict(camera_size=[3008,2000], fixed_crop=[150,680,2950,1100],
            resize='aspect-preserving pad to 256; no per-flame scale normalization',
            exposure='-5 EV bracket only; reject workbook-marked RGB saturation; unknown flags retained',
            mask='weak HSV largest component, not a physical measurement'),
        split='seed42 hash order within fuel; whole ignitions and duplicate physical conditions grouped',
        files={n: dict(bytes=(SOURCE/n).stat().st_size, sha256=sha((SOURCE/n).read_bytes())) for n in [BOOK,*ARCHIVES.values()]},
        counts=dict(pairs=len(records), groups=len(set(r['group'] for r in records)),
            splits=dict(Counter(r['split'] for r in records)), fuels=dict(Counter(r['fuel'] for r in records))),
        records=records, excluded=excluded)
    (ROOT/'manifest.json').write_text(json.dumps(manifest, indent=2))
    canvas = Image.new('RGB', (6*SIZE, ((len(images)+5)//6)*(SIZE+35)))
    draw = ImageDraw.Draw(canvas)
    for i, (im, r) in enumerate(zip(images, records)):
        x=i%6*SIZE; y=i//6*(SIZE+35); canvas.paste(Image.fromarray(im),(x,y))
        draw.text((x,y+SIZE),f"{r['id']} {r['split']}\n{r['fuel']} {r['features'][1]:.1f} sccm",fill='white')
    canvas.save(ROOT/'montage.jpg')
    print(json.dumps(manifest['counts'], indent=2), flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['fetch','prepare'])
    fetch() if p.parse_args().command=='fetch' else prepare()
