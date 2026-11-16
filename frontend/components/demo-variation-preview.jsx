"use client";

import { useEffect, useRef, useState } from "react";

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

// Nearby-condition images are prepared only while the image is hovered or
// keyboard-focused. Leaving returns immediately to the selected prediction.
export function DemoVariationPreview({ preview, controls, info, disabled, active = true, onPointerDown }) {
  const [frames, setFrames] = useState([]);
  const [index, setIndex] = useState(0);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [status, setStatus] = useState("");
  const [reduced, setReduced] = useState(true);
  const [visible, setVisible] = useState(true);
  const exploring = active && visible && !disabled && !reduced && (hovered || focused);
  const signature = JSON.stringify(controls);
  const cache = useRef({ signature: "", frames: [] });

  useEffect(() => {
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduced(media.matches);
    const visibility = () => setVisible(!document.hidden);
    sync(); visibility();
    media.addEventListener("change", sync);
    document.addEventListener("visibilitychange", visibility);
    return () => { media.removeEventListener("change", sync); document.removeEventListener("visibilitychange", visibility); };
  }, []);

  useEffect(() => {
    setFrames([]); setIndex(0); setStatus("");
    if (!exploring || !info) return;
    if (cache.current.signature === signature) { setFrames(cache.current.frames); return; }
    const selected = JSON.parse(signature);
    if (info.numeric.some(s => selected[s.key] === "" || !Number.isFinite(Number(selected[s.key])))) return;
    const queries = variationQueries(selected, info.numeric, 5);
    if (queries.length < 2) return;
    const abort = new AbortController();
    let current = true;
    const timeout = setTimeout(() => abort.abort(), 60000);
    async function generate() {
      try {
        const generated = [];
        for (const query of queries) {
          if (!current) return;
          setStatus(`Preparing hover preview ${generated.length + 1} of ${queries.length}…`);
          const response = await fetch("/hybrid/compare?" + new URLSearchParams(query), { signal: abort.signal });
          const data = await response.json();
          if (!response.ok) throw Error(data.error || "Variation service unavailable");
          const image = new Image(); image.src = data.hybrid; await image.decode();
          generated.push({ hybrid: data.hybrid, conditions: data.conditions });
        }
        if (!current) return;
        cache.current = { signature, frames: generated };
        setFrames(generated); setStatus("Exploring nearby conditions; not a time prediction.");
      } catch (error) {
        if (current) setStatus(abort.signal.aborted ? "Hover preview timed out." : error.message);
      } finally { clearTimeout(timeout); }
    }
    generate();
    return () => { current = false; abort.abort(); clearTimeout(timeout); };
  }, [exploring, info, signature]);

  useEffect(() => {
    if (!exploring || frames.length < 2) return;
    const timer = setInterval(() => setIndex(i => (i + 1) % frames.length), 100);
    return () => clearInterval(timer);
  }, [exploring, frames.length]);

  const shown = exploring && frames[index] ? frames[index] : preview;
  return (
    <div className="demo-variation-preview">
      <button className="demo-image-button" type="button" aria-label="Explore flame variations"
        aria-disabled={disabled || undefined}
        title="Hover or focus to explore nearby conditions. Move away for the selected prediction."
        onPointerEnter={e => { if (e.pointerType !== "touch") setHovered(true); }}
        onPointerLeave={() => setHovered(false)}
        onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
        onPointerDown={e => { if (!disabled) onPointerDown?.(e); }}>
        <img className="demo-flame-image" draggable={false} style={{ touchAction: "none" }}
          src={shown.hybrid} alt={exploring && frames.length ? "Nearby-condition CNN variation" : "Selected hybrid CNN flame estimate"} width="256" height="256" />
      </button>
      <p className="demo-frame-conditions">{shown.conditions}</p>
      <p className="demo-hover-note">{exploring ? status || "Hover preview" : "Selected prediction · hover to explore"}</p>
    </div>
  );
}
