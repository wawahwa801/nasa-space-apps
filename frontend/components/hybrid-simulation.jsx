"use client";

// Shared model workspace for the flame and room tabs. The main tab portals
// the same working controls into its collapsible Parameters panel.

import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { DemoVariationPreview } from "./demo-variation-preview";
import { RoomDeck } from "./room-deck";
import { RoomEnvironmentEditor } from "./room-environment-editor";
import { LlmInsights } from "./llm-insights";

const MODULES = ["Forward dock", "Cargo", "Habitat node", "Station core", "Science node", "Laboratory", "Observatory", "Cupola",
  "Command", "Crew quarters", "Medical", "EVA airlock", "Life support", "Engineering", "Power systems", "Greenhouse"];

export function HybridSimulation({ controlsContainerId, title = "Room simulation" }) {
  const controlId = useId();
  const workspaceRef = useRef(null);
  const [controlsContainer, setControlsContainer] = useState(null);
  useEffect(() => {
    setControlsContainer(controlsContainerId ? document.getElementById(controlsContainerId) : null);
  }, [controlsContainerId]);
  const [placingRooms, setPlacingRooms] = useState(false);
  const [environment, setEnvironment] = useState(null), [defaultEnvironment, setDefaultEnvironment] = useState(null);
  const [editing, setEditing] = useState(!controlsContainerId), [selectedRoom, setSelectedRoom] = useState(0);
  const playTime = useRef(0);
  const [playbackSpeed, setPlaybackSpeed] = useState(30);
  const [info, setInfo] = useState(null);
  const [controls, setControls] = useState({});
  const [result, setResult] = useState(null);
  const [applied, setApplied] = useState(null);
  const [status, setStatus] = useState("Loading hybrid model controls…");
  const [busy, setBusy] = useState(false);
  const [scale, setScale] = useState(0.03);
  const [k, setK] = useState(0.8);
  const [source, setSource] = useState(3);
  const [frame, setFrame] = useState(0);
  const [displayTime, setDisplayTime] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [comparison, setComparison] = useState(false);
  const [attempt, setAttempt] = useState(0);
  // Live preview of the hybrid flame image while the model controls change.
  const [preview, setPreview] = useState(null);
  const [previewStatus, setPreviewStatus] = useState("");
  const generation = useRef(0);
  const dragging = useRef(false);
  const alive = useRef(true);
  const previewQueue = useRef(null);
  const previewBusy = useRef(false);
  const previewVersion = useRef(0);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      previewVersion.current++;
      previewQueue.current = null;
    };
  }, []);

  // Live preview: at most one /hybrid/compare request in flight; only the
  // newest controls are sent next, and stale answers are ignored.
  useEffect(() => {
    if (!info) return;
    const version = ++previewVersion.current;
    if (info.numeric.some((s) => controls[s.key] === "" || !Number.isFinite(Number(controls[s.key])))) {
      previewQueue.current = null;
      setPreviewStatus("Enter valid model parameters.");
      return;
    }
    previewQueue.current = { controls: { ...controls }, version };
    setPreviewStatus("Updating live preview…");
    async function pump() {
      if (previewBusy.current) return;
      previewBusy.current = true;
      try {
        while (alive.current && previewQueue.current) {
          const next = previewQueue.current;
          previewQueue.current = null;
          try {
            const response = await fetch("/hybrid/compare?" + new URLSearchParams(next.controls));
            const data = await response.json();
            if (!response.ok) throw Error(data.error || "Preview unavailable");
            if (alive.current && next.version === previewVersion.current) {
              setPreview(data);
              setPreviewStatus("Live hybrid preview");
            }
          } catch (e) {
            if (alive.current && next.version === previewVersion.current) setPreviewStatus(e.message);
          }
        }
      } finally {
        previewBusy.current = false;
      }
    }
    const timer = setTimeout(pump, 70);
    return () => clearTimeout(timer);
  }, [info, controls]);

  // Dropping the flame image on a room restarts the fire there.
  useEffect(() => {
    function drop(e) {
      if (!dragging.current) return;
      dragging.current = false;
      const room = document.elementFromPoint(e.clientX, e.clientY)?.closest("[data-room]");
      if (room && workspaceRef.current?.contains(room)) {const i=Number(room.getAttribute("data-room"));if(editing)setSelectedRoom(i);else if(environment?.rooms[i]?.fuel)restartAt(i);}
    }
    window.addEventListener("pointerup", drop);
    return () => window.removeEventListener("pointerup", drop);
  });

  // Load the recorded runs and control ranges; retry while the service starts.
  useEffect(() => {
    const abort = new AbortController();
    let retry;
    let active = true;
    const timeout = setTimeout(() => abort.abort(), 10000);
    Promise.all([fetch("/hybrid/runs", { signal: abort.signal }), fetch("/hybrid/environment", {signal:abort.signal})])
      .then(async ([r, env]) => {
        if (!r.ok || !env.ok) throw Error("unavailable");
        const data=await env.json();
        if(active){setDefaultEnvironment(data);setSource(data.source);setEnvironment({rooms:data.rooms,edges:data.edges,duration_s:data.duration_s||1200,droplet_time_scale:data.droplet_time_scale||600});}
        return r.json();
      })
      .then((data) => {
        if (!active) return;
        setInfo(data);
        setControls({ run: data.runs[0].id, ...data.runs[0].values });
        setStatus("Choose model conditions, then Simulate.");
      })
      .catch(() => {
        if (!active) return;
        setStatus("Connecting to the hybrid model service (python ml/dashboard_simulation.py)… retrying automatically.");
        retry = setTimeout(() => setAttempt((n) => n + 1), 3000);
      })
      .finally(() => clearTimeout(timeout));
    return () => {
      active = false;
      abort.abort();
      clearTimeout(retry);
      clearTimeout(timeout);
      generation.current++;
    };
  }, [attempt]);

  useEffect(() => {
    if (!playing || !result) return;
    const frames = result.simulation.frames;
    let previous = null;
    let elapsed = playTime.current;
    let raf;
    const tick = (now) => {
      if (previous !== null) elapsed += (now - previous) / 1000 * playbackSpeed;
      previous = now;
      playTime.current=elapsed;
      const last = frames.length - 1;
      if (elapsed >= frames[last].time_s) {
        setFrame(last);
        setDisplayTime(frames[last].time_s);
        setPlaying(false);
        return;
      }
      let next = 0;
      while (next < last - 1 && frames[next + 1].time_s <= elapsed) next++;
      setFrame(next);
      setDisplayTime(elapsed);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, result, playbackSpeed]);

  function invalidate() {
    setApplied(null);
    generation.current++;
    setResult(null);
    setPlaying(false);
    setBusy(false);
    setFrame(0);
    setDisplayTime(null);
    playTime.current=0;
    setStatus("Inputs changed. Press Simulate to run.");
  }
  function change(key, value) {
    invalidate();
    setControls((c) => ({ ...c, [key]: value }));
  }

  async function run(start = source, selectedEnvironment = environment) {
    if(selectedEnvironment && !selectedEnvironment.rooms[start]?.fuel){setStatus("Choose an ignition room containing fuel.");return;}
    const id = ++generation.current;
    setBusy(true);
    setResult(null);
    setPlaying(false);
    setStatus("Generating hybrid image and running room simulation…");
    try {
      const response = await fetch("/hybrid/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ controls, mm_per_pixel: scale, k_mm2_s: k, source: start, ...(selectedEnvironment ? {environment:selectedEnvironment} : {}) }),
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.error || "Simulation failed");
      if (id !== generation.current) return;
      setPreview(data.prediction);
      setResult(data);
      setApplied({
        conditions: data.prediction.conditions,
        model: data.prediction.model_note,
        ...data.simulation.burn_model,
        ignition_module: data.simulation.scenario.rooms[start].name,
        assumptions: data.simulation.assumptions,
        environment: data.simulation.scenario,
        ignition_intervals: data.simulation.ignition_intervals,
        uncertainty: data.simulation.uncertainty,
      });
      setFrame(0);
      setDisplayTime(0);
      playTime.current=0;
      setPlaying(true);
      setStatus("Simulation ready · dimensioned thermal scenarios");
    } catch (e) {
      if (id === generation.current) setStatus(e.message);
    } finally {
      if (id === generation.current) setBusy(false);
    }
  }

  function restartAt(i) {
    setSource(i);
    run(i);
  }

  const current = result?.simulation.frames[frame];
  const mapEnvironment = result?.simulation.scenario || environment;
  function editEnvironment(next, nextSource=source) {invalidate();setEnvironment(next);setSource(nextSource);}
  function changeDoors(next) {const recompute=Boolean(result)||busy;editEnvironment(next);if(recompute)run(source,next); }
  function exportSimulation() {
    if(!result)return;
    const url=URL.createObjectURL(new Blob([JSON.stringify(result.simulation,null,2)],{type:'application/json'}));
    const link=document.createElement('a');link.href=url;link.download='dimensioned-room-scenario.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function seek(time) {playTime.current=time;setDisplayTime(time);setFrame(result.simulation.frames.findLastIndex(f=>f.time_s<=time));}

  const modelControls = (
    <form className="hybrid-controls" noValidate onSubmit={(e) => { e.preventDefault(); run(); }}>
          <h3>Model conditions</h3>
          {info ? (
            <>
              <label>Recorded fuel / state
                <select value={controls.run} onChange={(e) => {
                  invalidate();
                  const r = info.runs.find((x) => x.id === e.target.value);
                  setControls({ run: r.id, ...r.values });
                }}>
                  {info.runs.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
                </select>
              </label>
              {info.numeric.map((s) => (
                <div className="slider-field" key={s.key}>
                  <div>
                    <label htmlFor={`${controlId}-${s.key}`}>{s.label}</label>
                    <span className="editable-value">
                      <input aria-label={`${s.label} value`} type="number" min={s.min} max={s.max} step="any"
                        value={controls[s.key] ?? ""} onChange={(e) => change(s.key, e.target.value)} />
                      <span>{s.unit}</span>
                    </span>
                  </div>
                  <input id={`${controlId}-${s.key}`} type="range" min={s.min} max={s.max} step={s.step}
                    value={controls[s.key] ?? s.min} onChange={(e) => change(s.key, e.target.value)} />
                </div>
              ))}
              {info.categories.map((s) => (
                <label key={s.key}>{s.label}
                  <select value={controls[s.key]} onChange={(e) => change(s.key, e.target.value)}>
                    <option value="unknown">Unknown</option>
                    {s.levels.map(([, v]) => <option key={v} value={v}>{v}</option>)}
                  </select>
                </label>
              ))}
              <label>Equivalent-droplet image scale (mm/pixel)
                <input type="number" min="0.0001" max="0.1" step="0.001" value={scale} onChange={(e) => { invalidate(); setScale(Number(e.target.value)); }} />
              </label>
              <label>Assumed droplet K (mm²/s)<input type="number" min="0.000001" max="10" step="0.01" value={k} onChange={e=>{invalidate();setK(Number(e.target.value));}}/></label>
              <label>Ignition module
                <select value={source} onChange={(e) => { invalidate(); setSource(Number(e.target.value)); }}>
                  {source<0 && <option value={-1}>Choose a fueled room</option>}
                  {(environment?.rooms || MODULES.map(name=>({name,fuel:true}))).map((r,i)=><option key={r.id||i} value={i} disabled={!r.fuel}>{r.name}</option>)}
                </select>
              </label>
              <button type="submit" disabled={busy}>{busy ? "Simulating…" : "Simulate"}</button>
            </>
          ) : (
            <p className="hybrid-muted">Controls appear once the model service responds.</p>
          )}
        </form>
  );

  const roomEditor = (<>
          {environment && <RoomEnvironmentEditor environment={environment} source={source} selected={selectedRoom} onSelect={setSelectedRoom} onLayoutMode={setPlacingRooms} onChange={editEnvironment} onSource={i=>{invalidate();setSource(i);}} onReset={()=>{editEnvironment({rooms:defaultEnvironment.rooms,edges:defaultEnvironment.edges,duration_s:defaultEnvironment.duration_s||1200,droplet_time_scale:defaultEnvironment.droplet_time_scale||600},defaultEnvironment.source);setSelectedRoom(0);}}/>}
  </>);
  return (
    <section ref={workspaceRef} className={`hybrid-active ${controlsContainerId ? "hybrid-with-panel" : ""}`} aria-label={title}>
      <header className="hybrid-head">
        <h2>{title}</h2>
        <p>
          The hybrid CNN generates a flame image for the chosen conditions; the equivalent droplet D² history is scaled into finite room fuel release, with room dimensions and hallway transport included.
        </p>
        <p role="status" className="hybrid-status">{status}</p>
      </header>

      <div className="hybrid-layout">
        {/* noValidate: the service validates ranges; browser step checks would
            otherwise silently block defaults such as K = 0.8 with step 0.01. */}
        {controlsContainerId ? (controlsContainer && createPortal(modelControls, controlsContainer)) : editing ? roomEditor : modelControls}

        <div className="hybrid-results">
          {!preview && !result && <p className="hybrid-muted">The generated flame appears here; Simulate shows how fire spreads between modules.</p>}
          {preview && (
            <>
              <div className="hybrid-flame">
                {controlsContainerId ? (
                  <DemoVariationPreview key={JSON.stringify([controls, scale, k, source, busy])}
                    preview={preview} controls={controls} info={info} disabled={busy || previewStatus !== "Live hybrid preview"}
                    onPointerDown={(e) => { e.preventDefault(); dragging.current = true; }} />
                ) : (
                <img
                  draggable={false}
                  style={{ touchAction: "none" }}
                  onPointerDown={(e) => { e.preventDefault(); dragging.current = true; }}
                  title="Drag onto a room to set its ignition point"
                  src={preview.hybrid}
                  alt="Hybrid CNN flame estimate"
                  width="256"
                  height="256"
                />
                )}
                <div>
                  <p className="hybrid-muted" aria-live="polite">{previewStatus}</p>
                  <p>{!controlsContainerId && `${preview.conditions} · `}{preview.model_note}</p>
                  {result && <p>Visual prediction mask diameter: {result.simulation.burn_model.diameter_px.toFixed(1)} px → assumed proxy {result.simulation.burn_model.initial_diameter_mm.toFixed(2)} mm (equivalent-droplet proxy)</p>}
                  {result && <p className="hybrid-muted">Drag the flame onto a room, or select a room, to restart the fire there.</p>}
                  <button type="button" aria-expanded={comparison} onClick={() => setComparison((v) => !v)}>{controlsContainerId ? "Compare selected prediction sources" : "Compare source images"}</button>
                </div>
              </div>
              {comparison && (
                <div className="source-comparison">
                  <figure><img src={preview.cnn} alt="Feature-only CNN for applied parameters" width="192" height="192" /><figcaption>Feature-only CNN</figcaption></figure>
                  <figure><img src={preview.retrieval} alt="Retrieved reference for applied parameters" width="192" height="192" /><figcaption>Recorded reference · {preview.retrieval_reference}</figcaption></figure>
                </div>
              )}
            </>
          )}
          {environment && <div className="room-environment-tools"><button type="button" aria-pressed={editing} onClick={()=>setEditing(true)}>Environment</button><button type="button" aria-pressed={!editing} onClick={()=>setEditing(false)}>Model parameters</button><span>{environment.rooms.length} rooms · {environment.edges.length} hallways</span></div>}
          {result?.simulation.burn_model.droplet_scaling && <p className="hybrid-muted">Equivalent droplet: {result.simulation.burn_model.droplet_scaling.diameter_mm.toFixed(2)} mm · D² lifetime {result.simulation.burn_model.droplet_scaling.raw_lifetime_s.toFixed(2)} s × assumed {result.simulation.burn_model.droplet_scaling.aggregate_time_scale} scale = {result.simulation.diagnostics.scaled_burn_duration_s.toFixed(0)} simulated seconds (nominal).</p>}
          <div className={`room-workspace ${editing?'is-editing':''}`}>

          {controlsContainerId && editing && roomEditor}
          <div className="room-map-panel">
          {result && current && <div className="room-playback-toolbar">
            <button type="button" onClick={()=>{if(!playing && playTime.current>=result.simulation.frames.at(-1).time_s)seek(0);setPlaying(v=>!v);}}>{playing?'Pause':'Play'}</button>
            <button type="button" onClick={()=>{seek(0);setPlaying(true);}}>Restart</button>
            <span className="room-clock">Simulated time <strong>{Math.floor((displayTime ?? current.time_s)/60)}:{((displayTime ?? current.time_s)%60).toFixed(1).padStart(4,"0")}</strong><small>{(displayTime ?? current.time_s).toFixed(1)} seconds · {playbackSpeed}× playback</small></span>
            <label>Speed<select aria-label="Room playback speed" value={playbackSpeed} onChange={e=>setPlaybackSpeed(Number(e.target.value))}>{[1,8,16,30,60,120].map(v=><option key={v} value={v}>{v}×</option>)}</select></label>
            <label className="room-time-scrub">Playback<input aria-label="Room playback time" type="range" min="0" max={result.simulation.frames.at(-1).time_s} step="0.1" value={displayTime ?? current.time_s} onChange={e=>{setPlaying(false);seek(Number(e.target.value));}}/></label>
          </div>}
          {mapEnvironment && <RoomDeck environment={mapEnvironment} current={current} source={source} selected={selectedRoom} onSelect={setSelectedRoom} onIgnite={restartAt} editing={editing && placingRooms}
            onDoor={i=>changeDoors({...environment,edges:environment.edges.map((e,j)=>j===i?{...e,open:!e.open}:e)})}
            onAllDoors={open=>changeDoors({...environment,edges:environment.edges.map(e=>({...e,open}))})}
            onPlace={(x,y)=>{if(environment.rooms.some((r,i)=>i!==selectedRoom&&r.x===x&&r.y===y))return;editEnvironment({...environment,rooms:environment.rooms.map((r,i)=>i===selectedRoom?{...r,x,y}:r)});}}
            onExport={exportSimulation} intervals={result?.simulation.ignition_intervals} uncertainty={result?.simulation.uncertainty}/>}
          </div></div>
          <p className="hybrid-muted">
            Equivalent-droplet-scaled thermal scenarios with assumed aggregation, fuel load and transfer. These are sensitivity ranges, not calibrated spacecraft predictions; ventilation, smoke and oxygen depletion are not solved.
          </p>
        </div>
      </div>

      <LlmInsights scenario={applied} />
    </section>
  );
}
