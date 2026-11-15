"use client";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export function HybridSimulation() {
  const [info, setInfo] = useState(null), [controls, setControls] = useState({});
  const [target, setTarget] = useState(null), [result, setResult] = useState(null);
  const [status, setStatus] = useState("Loading hybrid controls…"), [busy, setBusy] = useState(false);
  const [scale, setScale] = useState(.03), [k, setK] = useState(.8), [source, setSource] = useState(3);
  const [frame, setFrame] = useState(0), [playing, setPlaying] = useState(false);
  const generation = useRef(0);
  useEffect(() => {
    setTarget(document.getElementById("hybrid-controls"));
    const abort = new AbortController();
    fetch('/hybrid/runs', {signal: abort.signal}).then(async r => {if (!r.ok) throw Error('Hybrid service unavailable. Start python ml/dashboard_simulation.py.'); return r.json();}).then(data => {
      setInfo(data); setControls({run: data.runs[0].id, ...data.runs[0].values}); setStatus('Choose model conditions, then Simulate.');
    }).catch(e => {if(e.name !== 'AbortError') setStatus(e.message);});
    return () => {abort.abort(); generation.current++;};
  }, []);
  useEffect(() => {
    if (!playing || !result) return;
    const timer = setInterval(() => setFrame(i => {if(i >= result.simulation.frames.length - 1) {setPlaying(false); return i;} return i + 1;}), 500);
    return () => clearInterval(timer);
  }, [playing, result]);
  function invalidate() {generation.current++; setResult(null); setPlaying(false); setBusy(false); setFrame(0); setStatus('Inputs changed. Press Simulate to run.');}
  function change(key, value) {invalidate(); setControls(c => ({...c, [key]: value}));}
  async function run() {
    const id = ++generation.current; setBusy(true); setResult(null); setPlaying(false); setStatus('Generating hybrid image and running room simulation…');
    try {
      const response = await fetch('/hybrid/simulate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({controls, mm_per_pixel:scale, k_mm2_s:k, source})});
      const data = await response.json(); if (!response.ok) throw Error(data.error || 'Simulation failed');
      if(id !== generation.current) return;
      setResult(data); setFrame(0); setPlaying(true); setStatus('Simulation running · illustrative flame-size proxy');
    } catch(e) {if(id === generation.current) setStatus(e.message);}
    finally {if(id === generation.current) setBusy(false);}
  }
  const current = result?.simulation.frames[frame];
  return <section className="hybrid-active" aria-label="Hybrid CNN room simulation">
    {target && createPortal(<div className="field-section"><h3>Hybrid model & simulation</h3><p>These controls drive Simulate. Atmospheric controls below remain available for NASA comparison.</p>
      {info && <><label>Recorded fuel / state<select value={controls.run} onChange={e => {invalidate(); const r=info.runs.find(r=>r.id===e.target.value);setControls({run:r.id,...r.values});}}>{info.runs.map(r=><option key={r.id} value={r.id}>{r.label}</option>)}</select></label>
      {info.numeric.map(s=><label key={s.key}>{s.label} ({s.unit})<input type="number" min={s.min} max={s.max} step={s.step} value={controls[s.key] ?? ''} onChange={e=>change(s.key,e.target.value)} /></label>)}
      {info.categories.map(s=><label key={s.key}>{s.label}<select value={controls[s.key]} onChange={e=>change(s.key,e.target.value)}><option value="unknown">Unknown</option>{s.levels.map(([,v])=><option key={v} value={v}>{v}</option>)}</select></label>)}
      <label>Assumed size conversion (mm/pixel)<input type="number" min="0.0001" max="0.1" step="0.001" value={scale} onChange={e=>{invalidate();setScale(Number(e.target.value));}} /></label>
      <label>Assumed burn coefficient (mm²/s)<input type="number" min="0.000001" max="10" step="0.01" value={k} onChange={e=>{invalidate();setK(Number(e.target.value));}} /></label>
      <label>Ignition module<select value={source} onChange={e=>{invalidate();setSource(Number(e.target.value));}}>{['Forward dock','Cargo','Habitat node','Station core','Science node','Laboratory','Observatory','Cupola','Command','Crew quarters','Medical','EVA airlock','Life support','Engineering','Power systems','Greenhouse'].map((n,i)=><option key={n} value={i}>{n}</option>)}</select></label>
      <button type="button" onClick={run} disabled={busy}>Simulate</button></>}
    </div>,target)}
    <p role="status">{status}</p>
    {result && <><img src={result.prediction.hybrid} alt="Hybrid CNN flame estimate" width="256" height="256" />
      <p>{result.prediction.conditions} · {result.prediction.model_note}</p>
      <p>Mask diameter: {result.simulation.burn_model.diameter_px.toFixed(1)} px → assumed proxy {result.simulation.burn_model.initial_diameter_mm.toFixed(2)} mm</p>
      <svg viewBox="0 0 800 500" role="img" aria-label={`Room spread at ${current.time_s} seconds`}>
        {result.simulation.scenario.edges.map((e,i)=>{const a=result.simulation.scenario.rooms[e.a],b=result.simulation.scenario.rooms[e.b];return <line key={i} x1={a.x*110+60} y1={a.y*90+45} x2={b.x*110+60} y2={b.y*90+45} stroke="#888" strokeWidth="5"/>;})}
        {result.simulation.scenario.rooms.map((r,i)=><g key={r.id}><rect x={r.x*110+10} y={r.y*90+10} width="100" height="70" rx="6" fill={({burning:'#e65326',burned:'#444',warming:'#8a6134',unignited:'#243a49',inert:'#222'})[current.rooms[i].state]} /><text x={r.x*110+60} y={r.y*90+47} textAnchor="middle" fill="white" fontSize="10">{r.name}</text></g>)}
      </svg>
      <button type="button" onClick={()=>setPlaying(p=>!p)}>{playing?'Pause':'Play'}</button>
      <label>Time: {current.time_s.toFixed(1)} s<input type="range" min="0" max={result.simulation.frames.length-1} value={frame} onChange={e=>{setPlaying(false);setFrame(Number(e.target.value));}} /></label>
    </>}
    <p>Illustrative room spread using an assumed conversion from flame mask size. Burn rate and room transfer are assumptions; airflow and oxygen effects are not solved.</p>
  </section>;
}
