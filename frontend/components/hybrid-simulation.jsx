"use client";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export function HybridSimulation({ onStarted, onResult }) {
  const [info, setInfo] = useState(null), [controls, setControls] = useState({});
  const [target, setTarget] = useState(null), [result, setResult] = useState(null);
  const [status, setStatus] = useState("Loading hybrid controls…"), [busy, setBusy] = useState(false);
  const [scale, setScale] = useState(.03), [k, setK] = useState(.8), [source, setSource] = useState(3);
  const [frame, setFrame] = useState(0), [playing, setPlaying] = useState(false);
  const [preview, setPreview] = useState(null), [previewStatus, setPreviewStatus] = useState('');
  const previewQueue = useRef(null), previewBusy = useRef(false), previewVersion = useRef(0);
  const alive = useRef(true);
  useEffect(() => {alive.current=true;return ()=>{alive.current=false;previewVersion.current++;previewQueue.current=null;};}, []);
  useEffect(() => {
    if (!info) return;
    const version = ++previewVersion.current;
    if (info.numeric.some(s => controls[s.key] === '' || !Number.isFinite(Number(controls[s.key])))) {
      previewQueue.current=null; setPreviewStatus('Enter valid model parameters.'); return;
    }
    previewQueue.current={controls:{...controls},version};
    setPreviewStatus('Updating live preview…');
    async function pump() {
      if (previewBusy.current) return;
      previewBusy.current=true;
      try {
        while (alive.current && previewQueue.current) {
          const next=previewQueue.current;previewQueue.current=null;
          try {
            const response=await fetch('/hybrid/compare?'+new URLSearchParams(next.controls));
            const data=await response.json();
            if (!response.ok) throw Error(data.error || 'Preview unavailable');
            if (alive.current && next.version===previewVersion.current) {
              setPreview(data);setPreviewStatus('Live hybrid preview');
            }
          } catch(e) {if(alive.current && next.version===previewVersion.current)setPreviewStatus(e.message);}
        }
      } finally {previewBusy.current=false;}
    }
    const timer=setTimeout(pump,70);
    return ()=>clearTimeout(timer);
  }, [info, controls]);
  const generation = useRef(0);
  const dragging = useRef(false);
  useEffect(() => {
    function drop(e) {if(!dragging.current)return;dragging.current=false;const room=document.elementFromPoint(e.clientX,e.clientY)?.closest("[data-room]");if(room){const index=Number(room.getAttribute("data-room"));setSource(index);run(index);}}
    window.addEventListener("pointerup",drop);
    return ()=>window.removeEventListener("pointerup",drop);
  });
  const [comparison, setComparison] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    setTarget(document.getElementById("hybrid-controls"));
    const abort = new AbortController();
    let retry, active = true;
    const timeout = setTimeout(() => abort.abort(), 10000);
    fetch('/hybrid/runs', {signal: abort.signal}).then(async r => {if (!r.ok) throw Error('Hybrid service unavailable. Start python ml/dashboard_simulation.py.'); return r.json();}).then(data => {
      if (!active) return;
      setInfo(data); setControls({run: data.runs[0].id, ...data.runs[0].values}); setStatus('Choose model conditions, then Simulate.');
    }).catch(() => {if (!active) return; setStatus('Connecting to model… retrying automatically.'); retry=setTimeout(()=>setAttempt(n=>n+1),3000);}).finally(()=>clearTimeout(timeout));
    return () => {active=false;abort.abort();clearTimeout(retry); clearTimeout(timeout); generation.current++;};
  }, [attempt]);
  useEffect(() => {
    if (!playing || !result) return;
    const timer = setInterval(() => setFrame(i => {if(i >= result.simulation.frames.length - 1) {setPlaying(false); return i;} return i + 1;}), 500);
    return () => clearInterval(timer);
  }, [playing, result]);
  function invalidate() {onResult?.(null);generation.current++; setResult(null); setPlaying(false); setBusy(false); setFrame(0); setStatus('Inputs changed. Press Simulate to run.');}
  function change(key, value) {invalidate(); setControls(c => ({...c, [key]: value}));}
  async function run(start = source) {
    const id = ++generation.current; setBusy(true); setResult(null); setPlaying(false); setStatus('Generating hybrid image and running room simulation…');
    try {
      const response = await fetch('/hybrid/simulate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({controls, mm_per_pixel:scale, k_mm2_s:k, source:start})});
      const data = await response.json(); if (!response.ok) throw Error(data.error || 'Simulation failed');
      if(id !== generation.current) return;
      setPreview(data.prediction);setResult(data); onResult?.({conditions:data.prediction.conditions, model:data.prediction.model_note, ...data.simulation.burn_model, ignition_module:data.simulation.scenario.rooms[start].name, assumptions:data.simulation.assumptions}); setFrame(0); setPlaying(true); setStatus('Simulation ready · illustrative flame-size proxy'); onStarted?.();
    } catch(e) {if(id === generation.current) setStatus(e.message);}
    finally {if(id === generation.current) setBusy(false);}
  }
  const current = result?.simulation.frames[frame];
  return <section className="hybrid-active" aria-label="Hybrid CNN room simulation">
    {target && createPortal(<div className="field-section"><span className="field-section-title">Model conditions</span>
      {info && <><label>Recorded fuel / state<select value={controls.run} onChange={e => {invalidate(); const r=info.runs.find(r=>r.id===e.target.value);setControls({run:r.id,...r.values});}}>{info.runs.map(r=><option key={r.id} value={r.id}>{r.label}</option>)}</select></label>
      {info.numeric.map(s=><div className="slider-field" key={s.key}><div><label htmlFor={`hybrid-${s.key}`}>{s.label}</label><span className="editable-value"><input aria-label={`${s.label} value`} type="number" min={s.min} max={s.max} step="any" value={controls[s.key] ?? ''} onChange={e=>change(s.key,e.target.value)}/><span>{s.unit}</span></span></div><input id={`hybrid-${s.key}`} type="range" min={s.min} max={s.max} step={s.step} value={controls[s.key] ?? s.min} onChange={e=>change(s.key,e.target.value)}/></div>)}
      {info.categories.map(s=><label key={s.key}>{s.label}<select value={controls[s.key]} onChange={e=>change(s.key,e.target.value)}><option value="unknown">Unknown</option>{s.levels.map(([,v])=><option key={v} value={v}>{v}</option>)}</select></label>)}
      <label>Assumed size conversion (mm/pixel)<input type="number" min="0.0001" max="0.1" step="0.001" value={scale} onChange={e=>{invalidate();setScale(Number(e.target.value));}} /></label>
      <label>Assumed burn coefficient (mm²/s)<input type="number" min="0.000001" max="10" step="0.01" value={k} onChange={e=>{invalidate();setK(Number(e.target.value));}} /></label>
      <label>Ignition module<select value={source} onChange={e=>{invalidate();setSource(Number(e.target.value));}}>{['Forward dock','Cargo','Habitat node','Station core','Science node','Laboratory','Observatory','Cupola','Command','Crew quarters','Medical','EVA airlock','Life support','Engineering','Power systems','Greenhouse'].map((n,i)=><option key={n} value={i}>{n}</option>)}</select></label>
      <button type="button" onClick={()=>run()} disabled={busy}>Simulate</button></>}
    </div>,target)}
    <h2 className="sr-only">Hybrid flame & room simulation</h2><p role="status">{status}</p>{info && <button type="button" onClick={()=>run()} disabled={busy}>{busy ? "Simulating…" : "Simulate current parameters"}</button>}
    <p role="status" aria-live="polite">{previewStatus}</p>
    {preview && <><img draggable={false} style={{touchAction:"none"}} onPointerDown={e=>{e.preventDefault();dragging.current=true;}} onDragStart={e=>{e.dataTransfer.setData("text/plain","ember-hybrid");e.dataTransfer.effectAllowed="copy";}} title="Drag onto a room to set its ignition point" src={preview.hybrid} alt="Hybrid CNN flame estimate" width="256" height="256" />
      <p>Drag the flame onto a room, or select a room to restart there.</p><button type="button" aria-expanded={comparison} onClick={()=>setComparison(v=>!v)}>Compare source images</button>{comparison && <div className="source-comparison"><figure><img src={preview.cnn} alt="Feature-only CNN for applied parameters" width="192" height="192"/><figcaption>Feature-only CNN</figcaption></figure><figure><img src={preview.retrieval} alt="Retrieved reference for applied parameters" width="192" height="192"/><figcaption>Recorded reference · {preview.retrieval_reference}</figcaption></figure></div>}<p>{preview.conditions} · {preview.model_note}</p>
    </>}
    {result && <><p>Mask diameter: {result.simulation.burn_model.diameter_px.toFixed(1)} px → assumed proxy {result.simulation.burn_model.initial_diameter_mm.toFixed(2)} mm</p>
      <svg viewBox="0 0 800 500" role="img" aria-label={`Room spread at ${current.time_s} seconds`}>
        {result.simulation.scenario.edges.map((e,i)=>{const a=result.simulation.scenario.rooms[e.a],b=result.simulation.scenario.rooms[e.b];return <line key={i} x1={a.x*110+60} y1={a.y*90+45} x2={b.x*110+60} y2={b.y*90+45} stroke="#888" strokeWidth="5"/>;})}
        {result.simulation.scenario.rooms.map((r,i)=><g key={r.id} data-room={i} role="button" tabIndex={0} aria-label={`Start fire in ${r.name}`} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(e.dataTransfer.getData("text/plain")==="ember-hybrid"){setSource(i);run(i);}}} onClick={()=>{setSource(i);run(i);}} onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();setSource(i);run(i);}}}><rect x={r.x*110+10} y={r.y*90+10} width="100" height="70" rx="6" fill={({burning:'#e65326',burned:'#444',warming:'#8a6134',unignited:'#243a49',inert:'#222'})[current.rooms[i].state]} /><text x={r.x*110+60} y={r.y*90+47} textAnchor="middle" fill="white" fontSize="10">{r.name}</text></g>)}
      </svg>
      <button type="button" onClick={()=>{if(frame===result.simulation.frames.length-1)setFrame(0);setPlaying(p=>!p);}}>{playing?'Pause':'Play'}</button>
      <label>Time: {current.time_s.toFixed(1)} s<input type="range" min="0" max={result.simulation.frames.length-1} value={frame} onChange={e=>{setPlaying(false);setFrame(Number(e.target.value));}} /></label>
    </>}
    <details className="hybrid-limitations"><summary>Simulation assumptions</summary><p>Illustrative room spread using an assumed conversion from flame mask size. Burn rate and room transfer are assumptions; airflow and oxygen effects are not solved.</p></details>
  </section>;
}
