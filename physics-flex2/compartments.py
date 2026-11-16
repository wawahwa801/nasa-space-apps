"""Dimensioned thermal-network scenarios, NOT a validated compartment/spacecraft solver.

Heat rates in kW=kJ/s, capacities in kJ/K, lengths in m. An equivalent
droplet D² curve is explicitly time-scaled into aggregate fuel release. The
aggregation scale, transport and ignition parameters are scenario assumptions.
"""
import copy
import math
from model import number
from rooms import validate_layout

PROFILES = {
    'earlier_spread': dict(growth=150., ignition=140., inertia=1.5, transfer=.6, velocity=.8),
    'nominal': dict(growth=300., ignition=180., inertia=2., transfer=.5, velocity=.5),
    'later_spread': dict(growth=600., ignition=240., inertia=3., transfer=.35, velocity=.25),
}


def default_environment():
    q={}
    names=['Habitat','Laboratory','Cargo','Junction','Airlock','Engineering']
    positions=[(0,0),(1,0),(2,0),(1,1),(0,1),(2,1)]
    q['rooms']=[dict(id=f'R{i+1}',name=name,x=positions[i][0],y=positions[i][1],fuel=True,
                     width_m=5.,length_m=5.,height_m=2.7) for i,name in enumerate(names)]
    q['edges']=[dict(a=a,b=b,open=True,length_m=6.,width_m=1.2) for a,b in [(0,1),(1,2),(1,3),(3,4),(3,5)]]
    q.update(source=1,duration_s=1200,droplet_time_scale=600.,model='scaled_droplet_thermal_network_v2')
    return q


def dimensions(query):
    q=copy.deepcopy(query)
    validate_layout(q)
    number(q.get('duration_s',1200),'duration_s',60,3600)
    q['droplet_time_scale']=number(q.get('droplet_time_scale',600.),'droplet_time_scale',60,3600)
    for r in q['rooms']:
        for key,default,low,high in [('width_m',5.,2.,12.),('length_m',5.,2.,12.),('height_m',2.7,2.,5.)]:
            r[key]=number(r.get(key,default),key,low,high)
    for e in q['edges']:
        e['length_m']=number(e.get('length_m',6.),'hallway length_m',1.,100.)
        e['width_m']=number(e.get('width_m',1.2),'hallway width_m',.5,3.)
    return q


def _scenario(q, profile, droplet):
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
    lifetime=droplet['raw_lifetime_s']*q['droplet_time_scale']*profile['growth']/300.
    ramp=min(profile['growth'],lifetime*.3)
    history=[];frames=[];released=0.;transferred=0.
    for t in range(duration+1):
        powers=[]
        for i in range(n):
            age=None if ignition[i] is None else t-ignition[i]
            consumed=0. if age is None else max(0.,1-age/lifetime)**1.5-max(0.,1-(age+1)/lifetime)**1.5
            power=0. if age is None or energy[i]<=0 else initial[i]*consumed*min(1.,((age+.5)/max(.000001,ramp))**2)
            powers.append(min(power,energy[i]))
        states=[]
        for i,r in enumerate(rooms):
            state='inert' if not r['fuel'] else 'unignited' if ignition[i] is None and temperatures[i]<ambient+1 else 'warming' if ignition[i] is None else 'burned' if energy[i]<=0 else 'extinguished' if t-ignition[i]>=lifetime else 'burning'
            states.append(dict(id=r['id'],state=state,remaining_fraction=energy[i]/initial[i] if initial[i] else 0.,
                               exposure_fraction=min(1.,max(0.,(temperatures[i]-ambient)/(profile['ignition']-ambient))),
                               temperature_c=round(temperatures[i],3),heat_release_kw=round(powers[i],3),droplet_diameter_mm=None, equivalent_droplet_diameter_mm=None if ignition[i] is None else droplet['diameter_mm']*math.sqrt(max(0.,1-(t-ignition[i])/lifetime))))
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
                diagnostics=dict(released_energy_kj=released,transferred_energy_kj=transferred,initial_fuel_energy_kj=sum(initial),integration_step_s=1.,scaled_burn_duration_s=lifetime))


def simulate_dimensioned(query, image_provenance=None):
    q=dimensions(query)
    provenance=dict(image_provenance or {})
    diameter=number(provenance.get('initial_diameter_mm',1.),'equivalent droplet diameter_mm',.01,20.)
    coefficient=number(provenance.get('k_mm2_s',provenance.get('legacy_k_mm2_s_ignored',.8)),'droplet K_mm2_s',.000001,10.)
    droplet=dict(diameter_mm=diameter,k_mm2_s=coefficient,raw_lifetime_s=diameter*diameter/coefficient,
                 aggregate_time_scale=q['droplet_time_scale'],diameter_status='CNN flame-mask equivalent droplet proxy; not a measured liquid-droplet diameter' if image_provenance else 'Assumed 1 mm standalone reference, not a CNN measurement',
                 time_scale_status='Assumed aggregation scaling; no experimentally validated droplet-to-compartment similarity law')
    runs={name:_scenario(q,profile,droplet) for name,profile in PROFILES.items()}
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
    return dict(result,scenario=q,burn_model=dict(image_provenance or {},mode='scaled_droplet_thermal_network_v2',
        droplet_scaling=droplet, cnn_role='CNN mask plus assumed image scale sets an equivalent droplet diameter; its D² history shapes an explicitly scaled aggregate heat-release curve.'),
        ignition_intervals=intervals,uncertainty=dict(kind='scenario_sensitivity_envelope',calibrated=False,
            confidence_level=None,profiles=PROFILES,statement='Range across three assumed growth/transfer/ignition scenarios; not a confidence interval. Null upper bound means at least one scenario did not ignite within the simulated horizon.'),
        assumptions=['D² lifetime d²/K is multiplied by an assumed aggregation time scale; normalized volume-consumption rate shapes finite room fuel release. This extrapolation is not calibrated.',
                     'The CNN image measures a luminous flame mask, not a calibrated liquid droplet; image scale, K and 30 MJ/m² room fuel load remain assumptions.',
                     'Room dimensions change effective heat capacity; hall length delays and attenuates transfer; closed doors block modeled transfer entirely.',
                     'Single-temperature thermal network: no stratification, pressure-driven ventilation, smoke, oxygen depletion, wall conduction or radiative ignition; effective emissivity 0.15 is an assumed loss term.',
                     'Not CFAST/FDS, not calibrated spacecraft physics. Full-scale tests are required for physical claims.'])
