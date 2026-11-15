"""Exploratory lumped-surface energy model, SI units; no CNN dependencies."""
import copy
import math

SIGMA = 5.670374419e-8
WORK_BUDGET = 400_000


def number(obj, key, low, high):
    v = obj.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not low <= v <= high:
        raise ValueError(f'{key} must be a finite number in [{low}, {high}]')
    return float(v)


def validate(s):
    if not isinstance(s, dict):
        raise ValueError('Scenario must be an object')
    for key, lo, hi in [('duration', 1, 600), ('dt', .005, .1), ('ambient_k', 200, 400), ('oxygen_percent', 0, 100), ('oxygen_cutoff', 0, 100), ('h', 0, 100), ('source_w', 0, 2000), ('source_seconds', 0, 600), ('capture_fraction', 0, .8)]:
        number(s, key, lo, hi)
    patches = s.get('patches')
    if not isinstance(patches, list) or not 1 <= len(patches) <= 100:
        raise ValueError('Supply 1–100 patches')
    if type(s.get('source_index')) is not int or not 0 <= s['source_index'] < len(patches):
        raise ValueError('Invalid source index')
    if len(patches) * s["duration"] / s["dt"] > WORK_BUDGET:
        raise ValueError("Scenario exceeds interactive computation budget")
    coords = set()
    for p in patches:
        if not isinstance(p, dict) or type(p.get('fuel')) is not bool:
            raise ValueError('Each patch needs a boolean fuel flag')
        for key, lo, hi in [('x', 0, 20), ('y', 0, 20), ('area', .001, .1), ('thickness', .0001, .01), ('density', 50, 3000), ('cp', 100, 5000), ('conductivity', 0, 10), ('emissivity', 0, 1), ('ignition_k', 401, 1200), ('heat_combustion', 1e6, 5e7), ('burn_w', 0, 500)]:
            number(p, key, lo, hi)
        if type(p['x']) is not int or type(p['y']) is not int:
            raise ValueError('Patch coordinates must be integer grid positions')
        if (p['x'], p['y']) in coords:
            raise ValueError('Patch positions must be unique')
        coords.add((p['x'], p['y']))
    return s


def simulate(s, factor=1.0):
    validate(s)
    patches = s['patches']; n = len(patches); ambient = s['ambient_k']
    capacity = [p['area'] * p['thickness'] * p['density'] * p['cp'] for p in patches]
    fuel = [p['area'] * p['thickness'] * p['density'] if p['fuel'] else 0 for p in patches]
    temp = [ambient] * n; ignition = [None] * n
    # Reciprocal conductive links between touching grid patches. Common side is
    # sqrt(area); interface thickness is averaged, path length is center spacing.
    links = []
    weights = []
    for i, p in enumerate(patches):
        w = [0 if j == i else 1 / ((p['x']-q['x'])**2 + (p['y']-q['y'])**2) for j, q in enumerate(patches)]
        total = sum(w)
        weights.append([s['capture_fraction'] * v / total if total else 0 for v in w])
        for j in range(i):
            q = patches[j]
            if abs(p['x']-q['x']) + abs(p['y']-q['y']) == 1:
                k = 2*p['conductivity']*q['conductivity']/(p['conductivity']+q['conductivity']) if p['conductivity']+q['conductivity'] else 0
                g = k * min(math.sqrt(p['area']), math.sqrt(q['area'])) * min(p['thickness'], q['thickness']) / ((math.sqrt(p['area'])+math.sqrt(q['area']))/2)
                links.append((i, j, g))
    frames=[]; t=0.; next_frame=0.; emitted=absorbed=external=losses=0.; steps=0
    initial_fuel=sum(fuel)
    while t < s['duration']-1e-9:
        # The adaptive stability limit can make the actual step count far larger
        # than duration / the user-requested dt. Bound real patch updates too.
        if (steps + 1) * n > WORK_BUDGET:
            raise ValueError('Scenario exceeds interactive computation budget')
        steps += 1
        conductance=[s['h']*p['area'] + 4*p['emissivity']*SIGMA*p['area']*max(temp[i], ambient)**3 for i,p in enumerate(patches)]
        for i,j,g in links: conductance[i]+=g; conductance[j]+=g
        dt=min(s['dt'],s['duration']-t,min(.2*capacity[i]/g for i,g in enumerate(conductance) if g>0) if any(conductance) else s['dt'])
        if dt < 1e-5: raise ValueError('Scenario too stiff; increase patch thermal mass')
        for i,p in enumerate(patches):
            if p['fuel'] and fuel[i]>0 and temp[i]>=p['ignition_k'] and s['oxygen_percent']>=s['oxygen_cutoff'] and ignition[i] is None: ignition[i]=t
        power=[0.]*n
        source_dt=max(0,min(dt,s['source_seconds']-t))
        power[s['source_index']]+=s['source_w']*factor*source_dt/dt
        external+=s['source_w']*factor*source_dt
        for i,p in enumerate(patches):
            if ignition[i] is not None and fuel[i]>0 and s['oxygen_percent']>=s['oxygen_cutoff']:
                energy=min(p['burn_w']*factor*dt,fuel[i]*p['heat_combustion'])
                fuel[i]=max(0,fuel[i]-energy/p['heat_combustion']); emitted+=energy
                for j,w in enumerate(weights[i]): power[j]+=energy*w/dt; absorbed+=energy*w
        for i,j,g in links:
            q=g*(temp[j]-temp[i]); power[i]+=q; power[j]-=q
        for i,p in enumerate(patches):
            loss=s['h']*p['area']*(temp[i]-ambient)+p['emissivity']*SIGMA*p['area']*(temp[i]**4-ambient**4)
            losses+=loss*dt; temp[i]+=(power[i]-loss)*dt/capacity[i]
            if not math.isfinite(temp[i]) or temp[i]>2000: raise ValueError('Temperature exceeds simplified model range (2000 K)')
        t+=dt
        if t>=next_frame or t>=s['duration']-1e-9:
            frames.append({'time':round(t,3),'temperature_k':temp.copy(),'state':['burned' if p['fuel'] and fuel[i]<=1e-12 else 'burning' if ignition[i] is not None else 'unignited' if p['fuel'] else 'inert' for i,p in enumerate(patches)],'ignited_area_m2':sum(p['area'] for i,p in enumerate(patches) if ignition[i] is not None)})
            next_frame=t+1
    stored=sum(capacity[i]*(temp[i]-ambient) for i in range(n))
    return {'frames':frames,'ignition_seconds':ignition,'remaining_fuel_kg':fuel,'diagnostics':{'external_j':external,'combustion_j':emitted,'captured_j':absorbed,'escaped_combustion_j':emitted-absorbed,'loss_j':losses,'stored_j':stored,'balance_residual_j':external+absorbed-losses-stored,'initial_fuel_kg':initial_fuel},'assumptions':['Prescribed constant oxygen; no depletion, gas flow or smoke solver.','Radiative source allocation is an assumed inverse-grid-distance kernel, not geometric view factors.','Ignition is a temperature threshold; no pyrolysis kinetics.','Ventilation acts through user-specified h; airflow speed is not automatically converted.','All default thermal and combustion properties are illustrative assumptions, not calibrated spacecraft materials.']}


def ensemble(s):
    results={name:simulate(copy.deepcopy(s),f) for name,f in [('low',.8),('base',1),('high',1.2)]}
    return {'mode':'assumption sensitivity, not confidence intervals','cases':results}


def example():
    material=dict(area=.01,thickness=.001,density=300,cp=1400,conductivity=.1,emissivity=.8,ignition_k=570,heat_combustion=16e6,burn_w=400)
    return dict(duration=180,dt=.05,ambient_k=295,oxygen_percent=21,oxygen_cutoff=15,h=5,source_w=400,source_seconds=20,capture_fraction=.6,source_index=10,patches=[dict(material,x=x,y=y,fuel=True) for y in range(4) for x in range(6)])
