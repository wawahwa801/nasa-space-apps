"""Dimensioned thermal-network scenarios, NOT a validated compartment/spacecraft solver.

Heat rates in kW=kJ/s, capacities in kJ/K, lengths in m. Specified t² HRR
is motivated by NIST CFAST's user-specified fire approach; numeric defaults,
transport speeds and ignition thresholds below are scenario assumptions.
"""
import copy
import math
from model import number
from rooms import example, validate_layout

PROFILES = {
    'earlier_spread': dict(growth=150., ignition=140., inertia=1.5, transfer=.6, velocity=.8),
    'nominal': dict(growth=300., ignition=180., inertia=2., transfer=.5, velocity=.5),
    'later_spread': dict(growth=600., ignition=240., inertia=3., transfer=.35, velocity=.25),
}


def default_environment():
    q=example()
    for i,r in enumerate(q['rooms']):
        r.update(width_m=4.+i%3, length_m=5.+i%2, height_m=2.7)
    for i,e in enumerate(q['edges']):
        e.update(length_m=4.+i%4*2., width_m=1.2)
    q.update(duration_s=1200,model='dimensioned_thermal_network_v1')
    return q


def dimensions(query):
    q=copy.deepcopy(query)
    validate_layout(q)
    number(q.get('duration_s',1200),'duration_s',60,3600)
    for r in q['rooms']:
        for key,default,low,high in [('width_m',5.,2.,12.),('length_m',5.,2.,12.),('height_m',2.7,2.,5.)]:
            r[key]=number(r.get(key,default),key,low,high)
    for e in q['edges']:
        e['length_m']=number(e.get('length_m',6.),'hallway length_m',1.,100.)
        e['width_m']=number(e.get('width_m',1.2),'hallway width_m',.5,3.)
    return q


def _scenario(q, profile):
    rooms=q['rooms'];n=len(rooms);duration=int(q.get('duration_s',1200));ambient=22.
    capacity=[r['width_m']*r['length_m']*r['height_m']*1.2*profile['inertia'] for r in rooms]
    # kW-loss/K: effective heat loss timescale, not fitted wall construction.
    cooling=1200.
    energy=[r['width_m']*r['length_m']*30_000 if r['fuel'] else 0. for r in rooms]
    initial=list(energy);temperatures=[ambient]*n
    ignition=[None]*n;ignition[q['source']]=0
    links=[[] for _ in rooms]
    for e in q['edges']:
        if e['open']:
            for a,b in [(e['a'],e['b']),(e['b'],e['a'])]:links[a].append((b,e))
    history=[];frames=[];released=0.;transferred=0.
    for t in range(duration+1):
        powers=[]
        for i in range(n):
            age=None if ignition[i] is None else t-ignition[i]
            power=0. if age is None or energy[i]<=0 else min(1000.,20.+1000.*(age/profile['growth'])**2)
            powers.append(min(power,energy[i]))
        states=[]
        for i,r in enumerate(rooms):
            state='inert' if not r['fuel'] else 'unignited' if ignition[i] is None and temperatures[i]<ambient+1 else 'warming' if ignition[i] is None else 'burned' if energy[i]<=0 else 'burning'
            states.append(dict(id=r['id'],state=state,remaining_fraction=energy[i]/initial[i] if initial[i] else 0.,
                               exposure_fraction=min(1.,max(0.,(temperatures[i]-ambient)/(profile['ignition']-ambient))),
                               temperature_c=round(temperatures[i],3),heat_release_kw=round(powers[i],3),droplet_diameter_mm=None))
        if t%5==0 or t==duration:frames.append(dict(time_s=t,rooms=states))
        if t==duration:break
        history.append(powers)
        incoming=[0.]*n
        for i in range(n):
            incoming[i]+=powers[i]*(1-profile['transfer'])
            total_width=sum(e['width_m'] for _,e in links[i])
            for j,e in links[i]:
                delay=math.ceil(e['length_m']/profile['velocity'])
                if t<delay:continue
                # Finite outgoing share; longer halls delay/attenuate transfer.
                amount=history[t-delay][i]*profile['transfer']*e['width_m']/total_width*math.exp(-e['length_m']/20.)
                incoming[j]+=amount;transferred+=amount
        for i,r in enumerate(rooms):
            released+=powers[i];energy[i]=max(0.,energy[i]-powers[i])
            wall_area=2*(r['width_m']*r['length_m']+r['width_m']*r['height_m']+r['length_m']*r['height_m'])
            # Effective radiative loss to ambient surfaces; assumed emissivity,
            # not an explicitly solved gas/wall radiation exchange.
            radiative=.15*5.670374419e-11*wall_area*((temperatures[i]+273.15)**4-(ambient+273.15)**4)
            change=(incoming[i]-radiative)/capacity[i]
            temperatures[i]=max(ambient,ambient+(temperatures[i]-ambient)*math.exp(-1/cooling)+change)
        # Synchronous ignition prevents room-order-dependent cascades.
        for i,r in enumerate(rooms):
            if r['fuel'] and ignition[i] is None and temperatures[i]>=profile['ignition']:ignition[i]=t+1
    return dict(frames=frames,ignition_times_s={r['id']:ignition[i] for i,r in enumerate(rooms)},
                diagnostics=dict(released_energy_kj=released,transferred_energy_kj=transferred,initial_fuel_energy_kj=sum(initial),integration_step_s=1.))


def simulate_dimensioned(query, image_provenance=None):
    q=dimensions(query)
    runs={name:_scenario(q,profile) for name,profile in PROFILES.items()}
    result=runs['nominal'];intervals={}
    for r in q['rooms']:
        times=[v['ignition_times_s'][r['id']] for v in runs.values()]
        reached=[t for t in times if t is not None]
        intervals[r['id']]=dict(earliest_s=min(reached) if reached else None,
            latest_s=max(reached) if reached and len(reached)==len(times) else None,
            not_reached_in_some_scenarios=any(t is None for t in times),scenarios_reached=len(reached),scenarios_total=len(times))
    for k,frame in enumerate(result['frames']):
        for i,state in enumerate(frame['rooms']):
            temps=[v['frames'][k]['rooms'][i]['temperature_c'] for v in runs.values()]
            state.update(temperature_lower_c=min(temps),temperature_upper_c=max(temps))
    return dict(result,scenario=q,burn_model=dict(image_provenance or {},mode='dimensioned_thermal_network_v1',
        cnn_role='Image and mask are visual provenance only; they do not set compartment HRR, fuel load, or ignition timing.'),
        ignition_intervals=intervals,uncertainty=dict(kind='scenario_sensitivity_envelope',calibrated=False,
            confidence_level=None,profiles=PROFILES,statement='Range across three assumed growth/transfer/ignition scenarios; not a confidence interval. Null upper bound means at least one scenario did not ignite within the simulated horizon.'),
        assumptions=['Specified t² fire growth, 1 MW cap and 30 MJ/m² fuel load are assumptions, not CNN outputs or measured cabin inputs.',
                     'Room dimensions change effective heat capacity; hall length delays and attenuates transfer; closed doors block modeled transfer entirely.',
                     'Single-temperature thermal network: no stratification, pressure-driven ventilation, smoke, oxygen depletion, wall conduction or radiative ignition; effective emissivity 0.15 is an assumed loss term.',
                     'Not CFAST/FDS, not calibrated spacecraft physics. Full-scale tests are required for physical claims.'])
