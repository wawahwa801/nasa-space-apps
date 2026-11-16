"use client";
import {useState} from 'react';

export function RoomEnvironmentEditor({environment, source, onChange, onSource, onReset, selected, onSelect}) {
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
    onChange({...environment,rooms:[...rooms,{id,name:`Room ${rooms.length+1}`,fuel:true,...point}]});onSelect(rooms.length);setError('');
  }
  function removeRoom() {
    if(rooms.length===1)return;
    const index=rooms.indexOf(room);
    const next=rooms.filter((_,i)=>i!==index);
    const edges=environment.edges.filter(e=>e.a!==index&&e.b!==index).map(e=>({...e,a:e.a>index?e.a-1:e.a,b:e.b>index?e.b-1:e.b}));
    const newSource=source===index?Math.max(0,next.findIndex(r=>r.fuel)):source>index?source-1:source;
    onChange({...environment,rooms:next,edges},newSource);onSelect(Math.min(index,next.length-1));setEnd('');setError('');
  }
  function connect() {
    const a=rooms.indexOf(room),b=rooms.findIndex(r=>r.id===end);
    if(b<0||a===b)return;
    if(environment.edges.some(e=>(e.a===a&&e.b===b)||(e.a===b&&e.b===a))){setError('These rooms are already connected.');return;}
    setError('');onChange({...environment,edges:[...environment.edges,{a,b,open:true}]});
  }
  return <aside className="room-editor" aria-label="Environment editor">
    <div className="room-editor-heading"><h3>Environment</h3><span>{rooms.length}/16 rooms</span></div>
    <p className="hybrid-muted">Select a room on the map. Click an empty grid point to move the selected room, or enter X/Y below. Open hallways control spread.</p>
    <label>Selected room<select value={room.id} onChange={e=>{onSelect(rooms.findIndex(r=>r.id===e.target.value));setError('');}}>{rooms.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
    <label>Room name<input maxLength={60} value={room.name} onChange={e=>updateRoom({name:e.target.value})}/></label>
    <div className="room-coordinate-fields">{['x','y'].map(axis=><label key={axis}>{axis.toUpperCase()} position<input type="number" min="0" max="9" step="1" value={room[axis]} onChange={e=>{const n=e.target.valueAsNumber;if(Number.isInteger(n)&&n>=0&&n<=9)updateRoom({[axis]:n});}}/></label>)}</div>
    <label className="room-check"><input type="checkbox" checked={room.fuel} onChange={e=>updateRoom({fuel:e.target.checked})}/>Contains fuel</label>
    <button type="button" disabled={!room.fuel} onClick={()=>onSource(rooms.indexOf(room))}>{source===rooms.indexOf(room)?'Ignition starts here':'Set ignition here'}</button>
    <div className="room-editor-actions"><button type="button" disabled={rooms.length>=16} onClick={addRoom}>Add room</button><button type="button" disabled={rooms.length===1} onClick={removeRoom}>Remove room</button></div>
    <details open><summary>Hallways</summary><label>Connect to<select aria-label="Connect to" value={end} onChange={e=>setEnd(e.target.value)}><option value="">Choose a room</option>{rooms.filter(r=>r.id!==room.id).map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label><button type="button" disabled={!end||!rooms.some(r=>r.id===end)} onClick={connect}>Connect rooms</button>
    <ul className="room-hallways">{environment.edges.map((edge,i)=>{const index=rooms.indexOf(room);if(edge.a!==index&&edge.b!==index)return null;const other=rooms[edge.a===index?edge.b:edge.a];return <li key={`${edge.a}-${edge.b}`}><label className="room-check"><input type="checkbox" aria-label={`Open hallway to ${other.name}`} checked={edge.open} onChange={e=>onChange({...environment,edges:environment.edges.map((v,j)=>j===i?{...v,open:e.target.checked}:v)})}/>{other.name}</label><button type="button" aria-label={`Remove hallway to ${other.name}`} onClick={()=>onChange({...environment,edges:environment.edges.filter((_,j)=>j!==i)})}>×</button></li>;})}</ul></details>
    {error&&<p role="alert" className="room-editor-error">{error}</p>}
    <button className="room-reset" type="button" onClick={()=>{onReset();setError('');setEnd('');}}>Reset station layout</button>
  </aside>;
}
