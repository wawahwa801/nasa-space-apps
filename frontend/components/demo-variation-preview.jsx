"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";

// A finite sensitivity sweep, never a calibrated confidence interval. Keep all
// other conditions (including fuel and apparatus flags) at their selected values.
export function variationQueries(controls, numeric, percent) {
  const axes = ["n0", "n1"].map(key => numeric.find(s => s.key === key));
  if (axes.some(s => !s) || !Number.isFinite(percent) || percent < 1 || percent > 20) return [];
  const queries = [];
  const seen = new Set();
  for (let i = 0; i < 8; i++) {
    const angle = i * Math.PI / 4;
    const query = { ...controls };
    axes.forEach((s, j) => {
      const offset = (s.max - s.min) * percent / 100 * (j ? Math.sin(angle) : Math.cos(angle));
      query[s.key] = Math.max(s.min, Math.min(s.max, Number((Number(controls[s.key]) + offset).toFixed(6))));
    });
    const key = new URLSearchParams(query).toString();
    if (!seen.has(key)) { seen.add(key); queries.push(query); }
  }
  return queries;
}

export function DemoVariationPreview({ preview, controls, info, disabled, onPointerDown }) {
  const id = useId();
  const [percent, setPercent] = useState(5);
  const [frames, setFrames] = useState([]);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [stopped, setStopped] = useState(false);
  const [reduced, setReduced] = useState(false);
  const active = useRef(true);
  const request = useRef(null);
  const version = useRef(0);

  useEffect(() => {
    active.current = true;
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    function sync() { setReduced(media.matches); if (media.matches) setPlaying(false); }
    sync();
    media.addEventListener("change", sync);
    return () => { active.current = false; request.current?.abort(); media.removeEventListener("change", sync); };
  }, []);

  useEffect(() => {
    if (!playing || reduced || frames.length < 2) return;
    const timer = setInterval(() => setIndex(i => (i + 1) % frames.length), 100);
    return () => clearInterval(timer);
  }, [playing, reduced, frames.length]);

  const reset = useCallback(() => {
    version.current++;
    request.current?.abort();
    setFrames([]); setIndex(0); setPlaying(false); setLoading(false); setStatus("");
  }, []);

  const generate = useCallback(async () => {
    reset();
    setStopped(false);
    if (!info || info.numeric.some(s => controls[s.key] === "" || !Number.isFinite(Number(controls[s.key])))) {
      setStatus("Enter valid model conditions first."); return;
    }
    const queries = variationQueries(controls, info.numeric, Number(percent));
    if (queries.length < 2) { setStatus("Choose a range from 1% to 20%."); return; }
    const current = version.current;
    const abort = new AbortController(); request.current = abort;
    const timeout = setTimeout(() => abort.abort(), 60000);
    setLoading(true);
    try {
      const generated = [];
      for (const query of queries) {
        if (!active.current || current !== version.current) return;
        setStatus(`Generating variation ${generated.length + 1} of ${queries.length}…`);
        const response = await fetch("/hybrid/compare?" + new URLSearchParams(query), { signal: abort.signal });
        const data = await response.json();
        if (!response.ok) throw Error(data.error || "Variation service unavailable");
        const image = new Image(); image.src = data.hybrid; await image.decode();
        generated.push({ hybrid: data.hybrid, conditions: data.conditions, controls: query });
      }
      if (!active.current || current !== version.current) return;
      setFrames(generated); setIndex(0);
      setPlaying(!matchMedia("(prefers-reduced-motion: reduce)").matches);
      setStatus(`${generated.length} generated alternatives ready.`);
    } catch (error) {
      if (active.current && current === version.current) {
        setStatus(abort.signal.aborted ? "Generation timed out. Try again." : `Could not generate variations: ${error.message}`);
      }
    } finally {
      clearTimeout(timeout);
      if (active.current && current === version.current) setLoading(false);
    }
  }, [controls, info, percent, reset]);

  // Debounce edits, then prepare each frame once; playback never queries the model.
  useEffect(() => {
    if (disabled) return;
    const timer = setTimeout(generate, 250);
    return () => {
      clearTimeout(timer);
      version.current++;
      request.current?.abort();
    };
  }, [disabled, generate]);

  const shown = frames[index] || preview;
  return (
    <div className="demo-variation-preview">
      <img className={`demo-flame-image ${frames.length ? "showing-variation" : ""}`} draggable={false}
        style={{ touchAction: "none" }} onPointerDown={frames.length ? undefined : onPointerDown}
        title={frames.length ? "Generated alternative; restore selected prediction to drag into a room" : "Drag onto a room to set its ignition point"}
        src={shown.hybrid} alt={frames.length ? "Exploratory CNN variation" : "Hybrid CNN flame estimate"} width="256" height="256" />
      <p className="demo-frame-conditions">{shown.conditions}</p>
      <div className="demo-variation-controls" aria-label="Demo variation animation">
        <label htmlFor={`${id}-range`}>Pressure / temperature range
          <span><input id={`${id}-range`} type="number" min="1" max="20" step="1" value={percent}
            onChange={e => { reset(); setStopped(false); setPercent(e.target.value); }} />% of each control’s full range</span>
        </label>
        <p className="hybrid-muted">Exploratory variation, not calibrated uncertainty or flame motion. Settings are clipped to slider limits; combinations may lack training support. Room simulation uses the selected inputs.</p>
        <div className="demo-variation-actions">
          {(frames.length > 0 || loading) && <button type="button" onClick={() => { reset(); setStopped(true); }}>{loading ? "Cancel animation" : "Selected prediction"}</button>}
          {!loading && !frames.length && (stopped || status) && <button type="button" disabled={disabled} onClick={generate}>{stopped ? "Resume animation" : "Retry animation"}</button>}
          {frames.length > 0 && !reduced && <button type="button" onClick={() => setPlaying(p => !p)}>{playing ? "Pause variations" : "Play variations"}</button>}
        </div>
        {frames.length > 0 && <label htmlFor={`${id}-frame`}>Alternative {index + 1} of {frames.length}
          <input id={`${id}-frame`} type="range" min="0" max={frames.length - 1} value={index}
            onChange={e => { setPlaying(false); setIndex(Number(e.target.value)); }} />
        </label>}
        {reduced && frames.length > 0 && <p className="hybrid-muted">Reduced motion is enabled. Use the alternative slider to inspect images.</p>}
        <p role="status" className="hybrid-muted">{status}</p>
      </div>
    </div>
  );
}
