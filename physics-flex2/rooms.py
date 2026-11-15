"""Illustrative room graph driven by the droplet engine, not a cabin fire solver."""
import math
from model import number, predict, trajectory

LABELS = ['Bridge', 'Avionics', 'Science', 'Crew quarters', 'Central hub', 'Medical', 'Life support', 'Cargo', 'Engineering']


def example():
    rooms = [dict(id=f'R{i+1}', name=name, x=i % 3, y=i // 3, fuel=True) for i, name in enumerate(LABELS)]
    edges = [dict(a=i, b=j, open=True) for i in range(9) for j in range(i+1,9)
             if abs(rooms[i]['x']-rooms[j]['x'])+abs(rooms[i]['y']-rooms[j]['y']) == 1]
    return dict(rooms=rooms, edges=edges, source=4, duration_s=60,
                transfer_fraction=.8, ignition_threshold=.10, cooling_time_s=30,
                run_id='A184D09', k_mm2_s=.8,
                observation=dict(diameter_px=100, mm_per_pixel=.03,
                                 calibration_source='Illustrative scale, not verified calibration', image_kind='cnn_estimate'))


def simulate(query, fitted=None):
    rooms, edges = query['rooms'], query['edges']
    if not isinstance(rooms,list) or not 1 <= len(rooms) <= 16 or not isinstance(edges,list) or len(edges)>120:
        raise ValueError('Supply 1–16 rooms and at most 120 edges')
    coords, ids = set(), set()
    for room in rooms:
        if not isinstance(room,dict) or type(room.get('fuel')) is not bool:
            raise ValueError('Each room needs a boolean fuel flag')
        if not isinstance(room.get('id'),str) or not 1 <= len(room['id']) <= 30 or room['id'] in ids:
            raise ValueError('Unique room IDs required')
        ids.add(room['id'])
        for axis in ('x','y'):
            if type(room.get(axis)) is not int or not 0 <= room[axis] <= 9:
                raise ValueError('Room coordinates must be integers from 0 to 9')
        coord = room['x'],room['y']
        if coord in coords:
            raise ValueError('Rooms cannot overlap')
        coords.add(coord)
        if not isinstance(room.get('name'),str) or len(room['name'])>60:
            raise ValueError('Room names must be strings of at most 60 characters')
    source = query['source']
    if type(source) is not int or not 0 <= source < len(rooms) or not rooms[source]['fuel']:
        raise ValueError('Ignition source must be a room containing fuel')
    links = [[] for _ in rooms]; seen = set()
    for edge in edges:
        a,b = edge['a'],edge['b']
        if type(a) is not int or type(b) is not int or a==b or not 0<=a<len(rooms) or not 0<=b<len(rooms) or type(edge.get('open')) is not bool:
            raise ValueError('Invalid room connection')
        key = tuple(sorted((a,b)))
        if key in seen:
            raise ValueError('Duplicate room connection')
        seen.add(key)
        if edge['open']:
            links[a].append(b);links[b].append(a)
    duration=number(query.get('duration_s',60),'duration_s',1,180)
    capture=number(query.get('transfer_fraction',.8),'transfer_fraction',0,1)
    threshold=number(query.get('ignition_threshold',.1),'ignition_threshold',.001,1)
    cooling=number(query.get('cooling_time_s',30),'cooling_time_s',.1,300)
    burn = predict(dict(query, duration_s=duration), fitted)
    count = math.ceil(duration/.1);dt=duration/count
    curve = trajectory(burn['initial_diameter_mm'],burn['k_mm2_s'],duration,dt)
    ignition=[None]*len(rooms);ignition[source]=0
    exposure=[0.]*len(rooms); released=transferred=0.;frames=[]

    def snapshot(step):
        states=[]
        for i, room in enumerate(rooms):
            age = None if ignition[i] is None else step-ignition[i]
            remaining=1. if age is None else curve[age]['relative_volume']
            state='inert' if not room['fuel'] else 'burned' if remaining<=0 else 'burning' if age is not None else 'warming' if exposure[i]>1e-8 else 'unignited'
            states.append(dict(id=room['id'],state=state,remaining_fraction=remaining if room['fuel'] else 0.,
                               exposure_fraction=min(1.,exposure[i]/threshold),
                               droplet_diameter_mm=None if age is None else curve[age]['diameter_mm']))
        return dict(time_s=round(step*dt,6),rooms=states)

    frames.append(snapshot(0))
    for step in range(1,count+1):
        increments=[0.]*len(rooms)
        for i,start in enumerate(ignition):
            if start is None:
                continue
            # Finite per-room proxy budget: one initial droplet-equivalent volume.
            amount=curve[step-1-start]['relative_volume']-curve[step-start]['relative_volume']
            released+=amount
            if links[i]:
                allocation=amount*capture/len(links[i])
                transferred+=amount*capture
                for target in links[i]:
                    increments[target]+=allocation
        # Apply all transfers together; new ignitions contribute only next step.
        for i,room in enumerate(rooms):
            if ignition[i] is None and room['fuel']:
                exposure[i]=exposure[i]*math.exp(-dt/cooling)+increments[i]
                if exposure[i]>=threshold:
                    ignition[i]=step
        if step%5==0 or step==count:
            frames.append(snapshot(step))
    return dict(scenario=query, burn_model={k:v for k,v in burn.items() if k!='frames'},
                frames=frames, ignition_times_s={room['id']:None if ignition[i] is None else round(ignition[i]*dt,6) for i,room in enumerate(rooms)},
                diagnostics=dict(released_proxy=released,transferred_proxy=transferred,integration_step_s=dt),
                assumptions=['Illustrative spaceship graph; FLEX-2 does not calibrate cabin fire spread.',
                             'Each fueled room contains one identical droplet-equivalent proxy, not a measured cabin fuel load.',
                             'Open edges split a bounded fraction of consumed-volume proxy equally; closed edges transfer zero.',
                             'Unignited rooms accumulate this proxy with exponential cooling and ignite at an assumed threshold.',
                             'No physical room temperatures, smoke, oxygen depletion, ventilation field or compartment radiation are solved.'])
