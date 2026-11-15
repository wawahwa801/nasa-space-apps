"use client";

// Room simulation tab: the hybrid CNN flame image (ml/dashboard_simulation.py,
// proxied at /hybrid/*) drives the illustrative room-spread physics from
// physics-flex2/rooms.py. Controls live in this tab so the flame simulation
// and its Parameters panel are unchanged.

import { useEffect, useRef, useState } from "react";
import { LlmInsights } from "./llm-insights";

const MODULES = ["Forward dock", "Cargo", "Habitat node", "Station core", "Science node", "Laboratory", "Observatory", "Cupola",
  "Command", "Crew quarters", "Medical", "EVA airlock", "Life support", "Engineering", "Power systems", "Greenhouse"];
const ROOM_FILL = { burning: "#e65326", burned: "#444", warming: "#8a6134", unignited: "#243a49", inert: "#222" };

export function HybridSimulation() {
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
  const [playing, setPlaying] = useState(false);
  const [comparison, setComparison] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const generation = useRef(0);
  const dragging = useRef(false);

  // Dropping the flame image on a room restarts the fire there.
  useEffect(() => {
    function drop(e) {
      if (!dragging.current) return;
      dragging.current = false;
      const room = document.elementFromPoint(e.clientX, e.clientY)?.closest("[data-room]");
      if (room) {
        const index = Number(room.getAttribute("data-room"));
        setSource(index);
        run(index);
      }
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
    fetch("/hybrid/runs", { signal: abort.signal })
      .then(async (r) => {
        if (!r.ok) throw Error("unavailable");
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
    const timer = setInterval(() => setFrame((i) => {
      if (i >= result.simulation.frames.length - 1) {
        setPlaying(false);
        return i;
      }
      return i + 1;
    }), 500);
    return () => clearInterval(timer);
  }, [playing, result]);

  function invalidate() {
    setApplied(null);
    generation.current++;
    setResult(null);
    setPlaying(false);
    setBusy(false);
    setFrame(0);
    setStatus("Inputs changed. Press Simulate to run.");
  }
  function change(key, value) {
    invalidate();
    setControls((c) => ({ ...c, [key]: value }));
  }

  async function run(start = source) {
    const id = ++generation.current;
    setBusy(true);
    setResult(null);
    setPlaying(false);
    setStatus("Generating hybrid image and running room simulation…");
    try {
      const response = await fetch("/hybrid/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ controls, mm_per_pixel: scale, k_mm2_s: k, source: start }),
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.error || "Simulation failed");
      if (id !== generation.current) return;
      setResult(data);
      setApplied({
        conditions: data.prediction.conditions,
        model: data.prediction.model_note,
        ...data.simulation.burn_model,
        ignition_module: data.simulation.scenario.rooms[start].name,
        assumptions: data.simulation.assumptions,
      });
      setFrame(0);
      setPlaying(true);
      setStatus("Simulation ready · illustrative flame-size proxy");
    } catch (e) {
      if (id === generation.current) setStatus(e.message);
    } finally {
      if (id === generation.current) setBusy(false);
    }
  }

  const current = result?.simulation.frames[frame];
  const restartAt = (i) => {
    setSource(i);
    run(i);
  };

  return (
    <section className="hybrid-active" aria-label="Hybrid CNN room simulation">
      <header className="hybrid-head">
        <h2>Room simulation</h2>
        <p>
          The hybrid CNN generates a flame image for the chosen conditions; its flame size drives an illustrative fire-spread
          model across station modules.
        </p>
        <p role="status" className="hybrid-status">{status}</p>
      </header>

      <div className="hybrid-layout">
        {/* noValidate: the service validates ranges; browser step checks would
            otherwise silently block defaults such as K = 0.8 with step 0.01. */}
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
                <label key={s.key}>{s.label} ({s.unit})
                  <input type="number" min={s.min} max={s.max} step={s.step} value={controls[s.key] ?? ""} onChange={(e) => change(s.key, e.target.value)} />
                </label>
              ))}
              {info.categories.map((s) => (
                <label key={s.key}>{s.label}
                  <select value={controls[s.key]} onChange={(e) => change(s.key, e.target.value)}>
                    <option value="unknown">Unknown</option>
                    {s.levels.map(([, v]) => <option key={v} value={v}>{v}</option>)}
                  </select>
                </label>
              ))}
              <label>Assumed size conversion (mm/pixel)
                <input type="number" min="0.0001" max="0.1" step="0.001" value={scale} onChange={(e) => { invalidate(); setScale(Number(e.target.value)); }} />
              </label>
              <label>Assumed burn coefficient (mm²/s)
                <input type="number" min="0.000001" max="10" step="0.01" value={k} onChange={(e) => { invalidate(); setK(Number(e.target.value)); }} />
              </label>
              <label>Ignition module
                <select value={source} onChange={(e) => { invalidate(); setSource(Number(e.target.value)); }}>
                  {MODULES.map((n, i) => <option key={n} value={i}>{n}</option>)}
                </select>
              </label>
              <button type="submit" disabled={busy}>{busy ? "Simulating…" : "Simulate"}</button>
            </>
          ) : (
            <p className="hybrid-muted">Controls appear once the model service responds.</p>
          )}
        </form>

        <div className="hybrid-results">
          {!result && <p className="hybrid-muted">Run a simulation to see the generated flame and how fire spreads between modules.</p>}
          {result && current && (
            <>
              <div className="hybrid-flame">
                <img
                  draggable={false}
                  style={{ touchAction: "none" }}
                  onPointerDown={(e) => { e.preventDefault(); dragging.current = true; }}
                  title="Drag onto a room to set its ignition point"
                  src={result.prediction.hybrid}
                  alt="Hybrid CNN flame estimate"
                  width="256"
                  height="256"
                />
                <div>
                  <p>{result.prediction.conditions} · {result.prediction.model_note}</p>
                  <p>Mask diameter: {result.simulation.burn_model.diameter_px.toFixed(1)} px → assumed proxy {result.simulation.burn_model.initial_diameter_mm.toFixed(2)} mm</p>
                  <p className="hybrid-muted">Drag the flame onto a room, or select a room, to restart the fire there.</p>
                  <button type="button" aria-expanded={comparison} onClick={() => setComparison((v) => !v)}>Compare source images</button>
                </div>
              </div>
              {comparison && (
                <div className="source-comparison">
                  <figure><img src={result.prediction.cnn} alt="Feature-only CNN for applied parameters" width="192" height="192" /><figcaption>Feature-only CNN</figcaption></figure>
                  <figure><img src={result.prediction.retrieval} alt="Retrieved reference for applied parameters" width="192" height="192" /><figcaption>Recorded reference · {result.prediction.retrieval_reference}</figcaption></figure>
                </div>
              )}
              <svg viewBox="0 0 800 500" role="img" aria-label={`Room spread at ${current.time_s} seconds`}>
                {result.simulation.scenario.edges.map((e, i) => {
                  const a = result.simulation.scenario.rooms[e.a];
                  const b = result.simulation.scenario.rooms[e.b];
                  return <line key={i} x1={a.x * 110 + 60} y1={a.y * 90 + 45} x2={b.x * 110 + 60} y2={b.y * 90 + 45} stroke="#888" strokeWidth="5" />;
                })}
                {result.simulation.scenario.rooms.map((r, i) => (
                  <g key={r.id} data-room={i} role="button" tabIndex={0} aria-label={`Start fire in ${r.name}`}
                    onClick={() => restartAt(i)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); restartAt(i); } }}>
                    <rect x={r.x * 110 + 10} y={r.y * 90 + 10} width="100" height="70" rx="6" fill={ROOM_FILL[current.rooms[i].state]} />
                    <text x={r.x * 110 + 60} y={r.y * 90 + 47} textAnchor="middle" fill="white" fontSize="10">{r.name}</text>
                  </g>
                ))}
              </svg>
              <div className="hybrid-playback">
                <button type="button" onClick={() => { if (frame === result.simulation.frames.length - 1) setFrame(0); setPlaying((p) => !p); }}>{playing ? "Pause" : "Play"}</button>
                <label>Time: {current.time_s.toFixed(1)} s
                  <input type="range" min="0" max={result.simulation.frames.length - 1} value={frame} onChange={(e) => { setPlaying(false); setFrame(Number(e.target.value)); }} />
                </label>
              </div>
            </>
          )}
          <p className="hybrid-muted">
            Illustrative room spread using an assumed conversion from flame mask size. Burn rate and room transfer are assumptions;
            airflow and oxygen effects are not solved.
          </p>
        </div>
      </div>

      <LlmInsights scenario={applied} />
    </section>
  );
}
