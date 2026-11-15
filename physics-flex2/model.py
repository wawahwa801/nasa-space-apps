"""Small FLEX-2 D² regression baseline; Python standard library only."""
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'frontend/public/flames/flex2/index.json'
CONFLICTS = {'E135F02', 'E135F06', 'E135F11', 'E156F05', 'E156F10', 'E159F01', 'E159F04'}


def number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be finite in [{low}, {high}]')
    return float(value)


def records():
    index = json.loads(INDEX.read_text())
    with (ROOT / 'ml/reports/flex2-inputs.csv').open() as source:
        settings = {r['run_id']: r for r in csv.DictReader(source)}
    result = []
    for row in index['records']:
        if row['id'] == 'E183L11':  # placeholder, not an independently identified run
            continue
        row = dict(row)
        row['apparatus'] = settings.get(row['id'], {})
        row['fuel_conflict'] = row['id'] in CONFLICTS
        result.append(row)
    return result


def diameter(observation):
    """Diameter is measured in the image's own coordinate system, after any resize."""
    px = number(observation['diameter_px'], 'diameter_px', .01, 100000)
    scale = number(observation['mm_per_pixel'], 'mm_per_pixel', 1e-8, 100)
    if not str(observation.get('calibration_source', '')).strip():
        raise ValueError('Supply calibration_source for the image coordinate system')
    if observation.get('image_kind') not in ('cnn_estimate', 'measured_backlit'):
        raise ValueError('image_kind must be cnn_estimate or measured_backlit')
    return number(px * scale, 'diameter_mm', .01, 10)


def trajectory(d0, k, duration=30, step=.25):
    d0 = number(d0, 'diameter_mm', .01, 10)
    k = number(k, 'k_mm2_s', 1e-6, 10)
    duration = number(duration, 'duration_s', .01, 600)
    step = number(step, 'step_s', .01, 10)
    if duration / step > 10000:
        raise ValueError('At most 10000 time steps')
    times = [i * step for i in range(math.floor(duration / step) + 1)]
    if times[-1] < duration:
        times.append(duration)
    return [{'time_s': t, 'diameter_mm': math.sqrt(max(0, d0*d0-k*t)),
             'relative_volume': (max(0, d0*d0-k*t)/(d0*d0))**1.5} for t in times]


def predict(query, fitted=None):
    run = next((r for r in records() if r['id'] == query.get('run_id')), None)
    if run is None:
        raise ValueError('Unknown or excluded FLEX-2 run')
    if run['fuel_conflict']:
        raise ValueError('Fuel identity unresolved for this run; see issue #33')
    d0 = diameter(query['observation'])
    warnings = ['22% O2 / 78% N2 is a scenario assumption, not a relabeling of NASA records.',
                'D² is a quasi-steady baseline: ignition transients, extinction and cool-flame stages are not solved.',
                'Diameter must describe the liquid droplet, not the surrounding luminous flame.']
    if query['observation']['image_kind'] == 'cnn_estimate':
        warnings.append('Initial diameter is model-derived; this trajectory is not independent experimental evidence.')
    outside = None
    if fitted is None:
        k = number(query.get('k_mm2_s', .8), 'k_mm2_s', 1e-6, 10)
        mode = 'assumed_coefficient'
        reference = None
        warnings.append('K is supplied as an assumption; fuel, pressure and temperature do not alter it automatically.')
    else:
        candidates = [r for r in fitted['training_runs'] if r['fuel'] == run['fuel'] and r['run_id'] != run['id']
                      and r['fiber_usage_flag'] == run['apparatus'].get('fiber_usage_flag', '')]
        if not candidates:
            raise ValueError('No independent training reference with matching fuel and fiber configuration')
        scales = fitted['scales']
        reference = min(candidates, key=lambda r: sum(((run['features'][f]-r[f])/scales[f])**2 for f in scales))
        outside = any(not min(r[f] for r in candidates) <= run['features'][f] <= max(r[f] for r in candidates) for f in scales)
        k = reference['k_mm2_s']
        mode = 'measured_history_reference'
        warnings.append('K uses nearest independent training run; no causal pressure/temperature law or calibrated confidence interval.')
    return dict(mode=mode, run=run, observation=dict(query['observation']), initial_diameter_mm=d0, k_mm2_s=k,
                oxygen_mole_fraction=.22, nitrogen_mole_fraction=.78, gas_status='user_assumed',
                outside_reference_range=outside, reference=reference, warnings=warnings,
                formal_zero_diameter_time_s=d0*d0/k,
                frames=trajectory(d0, k, query.get('duration_s', 30)))


def fit(path):
    """Fit K separately per measured run; reserve original experiment splits."""
    raw = Path(path).read_bytes()
    rows = list(csv.DictReader(raw.decode('utf-8-sig').splitlines()))
    runs = {r['id']: r for r in records()}
    groups = {}
    provenance = {}
    for row in rows:
        run_id = row['run_id']
        if run_id not in runs or run_id in CONFLICTS:
            raise ValueError('Unknown/excluded/disputed run: ' + run_id)
        if row['measurement_source'] != 'measured_backlit' or not row['source_file'].strip() or not row['calibration_source'].strip():
            raise ValueError('Training requires measured backlit targets, source_file and calibration_source')
        o2, n2 = float(row['oxygen_mole_fraction']), float(row['nitrogen_mole_fraction'])
        if not (math.isclose(o2, .22, abs_tol=1e-6) and math.isclose(n2, .78, abs_tol=1e-6)):
            raise ValueError('This model fits only measured 22/78 runs; do not overwrite recorded composition')
        t = number(float(row['time_s']), 'time_s', 0, 600)
        d = number(float(row['diameter_mm']), 'diameter_mm', .01, 10)
        groups.setdefault(run_id, []).append((t, d))
        provenance.setdefault(run_id, set()).add((row['source_file'], row['calibration_source']))
    fitted = []
    for run_id, points in groups.items():
        points.sort()
        if len(points) < 3 or len({t for t, _ in points}) != len(points):
            raise ValueError('Need at least three unique timestamps per run')
        ts = [p[0] for p in points]; ys = [p[1]**2 for p in points]
        mt, my = sum(ts)/len(ts), sum(ys)/len(ys)
        k = -sum((t-mt)*(y-my) for t,y in zip(ts,ys))/sum((t-mt)**2 for t in ts)
        number(k, 'fitted K', 1e-6, 10)
        run = runs[run_id]
        fitted.append(dict(run_id=run_id, fuel=run['fuel'], split=run['split'], **run['features'],
                           fiber_usage_flag=run['apparatus'].get('fiber_usage_flag', ''),
                           measurement_provenance=[dict(source_file=a, calibration_source=b) for a,b in sorted(provenance[run_id])],
                           k_mm2_s=k, d2_fit_rmse_mm2=math.sqrt(sum((y-(my+k*mt-k*t))**2 for t,y in zip(ts,ys))/len(ts))))
    training = [r for r in fitted if r['split'] == 'train']
    if not training:
        raise ValueError('No training-split runs; held-out runs cannot fit the predictor')
    scales = {f: max(max(r[f] for r in training)-min(r[f] for r in training), 1.) for f in ('pressure_kpa', 'temperature_c')}
    evaluation = []
    for target in fitted:
        if target['split'] == 'train':
            continue
        refs = [r for r in training if r['fuel'] == target['fuel'] and r['fiber_usage_flag'] == target['fiber_usage_flag']]
        if not refs:
            evaluation.append(dict(run_id=target['run_id'], status='no_matching_training_reference'))
            continue
        ref = min(refs, key=lambda r: sum(((r[f]-target[f])/scales[f])**2 for f in scales))
        points = sorted(groups[target['run_id']]); t0,d0 = points[0]
        error = math.sqrt(sum((math.sqrt(max(0,d0*d0-ref['k_mm2_s']*(t-t0)))-d)**2 for t,d in points)/len(points))
        evaluation.append(dict(run_id=target['run_id'], split=target['split'], reference_run=ref['run_id'], diameter_rmse_mm=error))
    return dict(schema=1, input_sha256=hashlib.sha256(raw).hexdigest(),
                source_index_sha256=hashlib.sha256(INDEX.read_bytes()).hexdigest(),
                gas_assumption=[.22,.78], training_runs=training, scales=scales,
                per_run_fits=fitted, held_out=evaluation,
                limitation='Nearest-run K baseline; no learned apparatus/camera effects or confidence intervals')
