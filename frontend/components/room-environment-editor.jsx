"use client";
import {useState} from 'react';

export function RoomEnvironmentEditor({environment, source, onChange, onSource, onReset, selected, onSelect, onLayoutMode}) {
  const [end, setEnd] = useState(''), [error,setError] = useState('');
  const rooms=environment.rooms, room=rooms[selected] || rooms[0];
  function updateRoom(patch) {
    const next={...room,...patch};
    if(rooms.some(r=>r.id!==room.id && r.x===next.x && r.y===next.y)){setError('That grid position already contains a room.');return;}
    setError('');onChange({...environment,rooms:rooms.map(r=>r.id===room.id?next:r)});
  }
  function addRoom() {
    if(rooms.length>=16)return;
    let point;
    for(let y=0;y<10&&!point;y++)for(let x=0;x<10;x++)if(!rooms.some(r=>r.x===x&&r.y===y)){point={x,y};break;}
    const id='custom-'+Date.now();
    onChange({...environment,rooms:[...rooms,{id,name:`Room ${rooms.length+1}`,fuel:true,width_m:5,length_m:5,height_m:2.7,...point}]});onSelect(rooms.length);setError('');
  }
  function removeRoom() {
    if(rooms.length===1)return;
    const index=rooms.indexOf(room);
    const next=rooms.filter((_,i)=>i!==index);
    const edges=environment.edges.filter(e=>e.a!==index&&e.b!==index).map(e=>({...e,a:e.a>index?e.a-1:e.a,b:e.b>index?e.b-1:e.b}));
    const newSource=source===index?next.findIndex(r=>r.fuel):source>index?source-1:source;
    onChange({...environment,rooms:next,edges},newSource);onSelect(Math.min(index,next.length-1));setEnd('');setError('');
  }
  function connect() {
    const a=rooms.indexOf(room),b=rooms.findIndex(r=>r.id===end);
    if(b<0||a===b)return;
    if(environment.edges.some(e=>(e.a===a&&e.b===b)||(e.a===b&&e.b===a))){setError('These rooms are already connected.');return;}
    setError('');onChange({...environment,edges:[...environment.edges,{a,b,open:true,length_m:6,width_m:1.2}]});
  }
  return <aside className="room-editor" aria-label="Environment editor">
    <div className="room-editor-heading"><h3>Environment</h3><span>{rooms.length}/16 rooms</span></div>
    <label>Room<select aria-label="Selected room" value={room.id} onChange={e=>{onSelect(rooms.findIndex(r=>r.id===e.target.value));setError('');}}>{rooms.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
    <div className="room-coordinate-fields">{[['width_m','Width'],['length_m','Length']].map(([key,label])=><label key={key}>{label} (m)<input type="number" min="2" max="12" step="0.1" value={room[key]??5} onChange={e=>{const n=e.target.valueAsNumber;if(Number.isFinite(n)&&n>=2&&n<=12)updateRoom({[key]:n});}}/></label>)}</div>
    <button type="button" disabled={!room.fuel} onClick={()=>onSource(rooms.indexOf(room))}>{source===rooms.indexOf(room)?'Ignition starts here':'Set ignition here'}</button>
    <h4>Connected hallways</h4><ul className="room-hallways">{environment.edges.map((edge,i)=>{const index=rooms.indexOf(room);if(edge.a!==index&&edge.b!==index)return null;const other=rooms[edge.a===index?edge.b:edge.a];return <li className="room-hallway-item" key={`${edge.a}-${edge.b}`}><label className="room-check"><input type="checkbox" aria-label={`Open hallway to ${other.name}`} checked={edge.open} onChange={e=>onChange({...environment,edges:environment.edges.map((v,j)=>j===i?{...v,open:e.target.checked}:v)})}/>{other.name}</label><label className="hallway-length">Length (m)<input aria-label={`Length of hallway to ${other.name}`} type="number" min="1" max="100" step="0.5" value={edge.length_m??6} onChange={e=>{const n=e.target.valueAsNumber;if(Number.isFinite(n)&&n>=1&&n<=100)onChange({...environment,edges:environment.edges.map((v,j)=>j===i?{...v,length_m:n}:v)});}}/></label></li>;})}</ul>
    <details onToggle={e=>onLayoutMode?.(e.currentTarget.open)}><summary>Layout tools</summary><label>Name<input maxLength={60} aria-label="Room name" value={room.name} onChange={e=>updateRoom({name:e.target.value})}/></label>
      <div className="room-coordinate-fields">{['x','y'].map(axis=><label key={axis}>{axis.toUpperCase()} position<input type="number" min="0" max="9" value={room[axis]} onChange={e=>{const n=e.target.valueAsNumber;if(Number.isInteger(n)&&n>=0&&n<=9)updateRoom({[axis]:n});}}/></label>)}</div>
      <label>Height (m)<input type="number" min="2" max="5" step="0.1" value={room.height_m??2.7} onChange={e=>{const n=e.target.valueAsNumber;if(Number.isFinite(n)&&n>=2&&n<=5)updateRoom({height_m:n});}}/></label>
      <label className="room-check"><input type="checkbox" checked={room.fuel} onChange={e=>updateRoom({fuel:e.target.checked})}/>Contains fuel</label>
      <div className="room-editor-actions"><button type="button" disabled={rooms.length>=16} onClick={addRoom}>Add room</button><button type="button" disabled={rooms.length===1} onClick={removeRoom}>Remove room</button></div>
      <label>Connect to<select aria-label="Connect to" value={end} onChange={e=>setEnd(e.target.value)}><option value="">Choose a room</option>{rooms.filter(r=>r.id!==room.id).map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label><button type="button" disabled={!end||!rooms.some(r=>r.id===end)} onClick={connect}>Connect rooms</button>
      {environment.edges.map((e,i)=>e.a===rooms.indexOf(room)||e.b===rooms.indexOf(room)?<button className="room-remove-link" type="button" key={i} onClick={()=>onChange({...environment,edges:environment.edges.filter((_,j)=>j!==i)})}>Remove link to {rooms[e.a===rooms.indexOf(room)?e.b:e.a].name}</button>:null)}
      <p className="hybrid-muted">Select a room and click an empty map point to move it. Hallway width stays 1.2 m unless imported.</p>
    </details>
    <details><summary>Droplet scaling assumptions</summary>
      <label>Aggregation time multiplier<input type="number" min="60" max="3600" step="10" value={environment.droplet_time_scale??600} onChange={e=>{const n=e.target.valueAsNumber;if(Number.isFinite(n)&&n>=60&&n<=3600)onChange({...environment,droplet_time_scale:n});}}/></label>
      <label>Simulation horizon (minutes)<input type="number" min="1" max="60" value={(environment.duration_s||1200)/60} onChange={e=>{const n=e.target.valueAsNumber;if(Number.isFinite(n)&&n>=1&&n<=60)onChange({...environment,duration_s:n*60});}}/></label>
      <p className="hybrid-muted">Room burn times use CNN equivalent-droplet d²/K × this assumed multiplier. Not a calibrated droplet-to-room similarity law.</p>
    </details>
    {error&&<p role="alert" className="room-editor-error">{error}</p>}
    <button className="room-reset" type="button" onClick={()=>{onReset();setError('');setEnd('');}}>Reset layout</button>
  </aside>;
}
