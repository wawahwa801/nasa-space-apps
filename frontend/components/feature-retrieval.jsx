"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import styles from "./feature-retrieval.module.css";

const INDEX = "/flames/flex2/index.json";

function validateLibrary(data) {
  if (data.source !== "PSI-68" || !Array.isArray(data.records) || !data.records.length ||
      !Array.isArray(data.fuels) || !data.fuels.length || data.fields?.length !== 2 ||
      data.fields[0].key !== "pressure_kpa" || data.fields[1].key !== "temperature_c" ||
      data.scale?.length !== 2 || !data.scale.every(n => Number.isFinite(n) && n > 0)) {
    throw new Error("The FLEX-2 library has an unsupported format.");
  }
  for (const fuel of data.fuels) {
    for (const field of data.fields) {
      const range = fuel.ranges?.[field.key], value = fuel.defaults?.[field.key];
      if (!range || ![range.min, range.max, value].every(Number.isFinite) || range.min > range.max || value < range.min || value > range.max) {
        throw new Error("The recorded feature ranges could not be loaded.");
      }
    }
    if (!data.records.some(r => r.fuel === fuel.name)) throw new Error("A fuel has no recorded images.");
  }
  for (const record of data.records) {
    if (!data.fuels.some(f => f.name === record.fuel) || !/^[A-Z]\d{3}[A-Z]\d{2}$/.test(record.id) ||
        record.image !== `/flames/flex2/${record.id}.png` ||
        !data.fields.every(field => Number.isFinite(record.features?.[field.key]))) {
      throw new Error("A recorded image has invalid source information.");
    }
  }
  return data;
}

function ConditionControl({ field, range, value, onChange }) {
  const [draft, setDraft] = useState(value.toFixed(2));
  const [editing, setEditing] = useState(false);
  useEffect(() => { if (!editing) setDraft(value.toFixed(2)); }, [value, editing]);
  const displayMin = Number(range.min.toFixed(2)), displayMax = Number(range.max.toFixed(2));
  const numeric = Number(draft);
  const valid = draft.trim() !== "" && Number.isFinite(numeric) && numeric >= displayMin && numeric <= displayMax;
  const id = `retrieval-${field.key}`;
  return (
    <div className={styles.control}>
      <label htmlFor={id}>{field.label}</label>
      <div className={styles.valueRow}>
        <input type="number" aria-label={`${field.label} value`} min={displayMin} max={displayMax} step="any"
          value={draft} aria-invalid={!valid} aria-describedby={`${id}-range${valid ? "" : ` ${id}-error`}`}
          onFocus={() => setEditing(true)} onBlur={() => { setEditing(false); setDraft(value.toFixed(2)); }}
          onChange={event => {
            const text = event.target.value, n = event.target.valueAsNumber;
            setDraft(text);
            if (text.trim() && Number.isFinite(n) && n >= displayMin && n <= displayMax) onChange(Math.min(range.max, Math.max(range.min, n)));
          }} />
        <span>{field.unit}</span>
      </div>
      <input id={id} type="range" min={range.min} max={range.max} step="any" value={value}
        aria-valuetext={`${value.toFixed(2)} ${field.unit}`} aria-describedby={`${id}-range`}
        onChange={event => { const n = Number(event.target.value); setDraft(n.toFixed(2)); onChange(n); }} />
      <small id={`${id}-range`}>Recorded range {range.min.toFixed(2)}–{range.max.toFixed(2)} {field.unit}</small>
      {!valid && <small id={`${id}-error`} className={styles.error} role="alert">Enter a value in the recorded range. The image uses the last valid value.</small>}
    </div>
  );
}

export function FeatureRetrieval() {
  const [library, setLibrary] = useState(null), [fuel, setFuel] = useState("");
  const [values, setValues] = useState({}), [loadError, setLoadError] = useState("");
  const [attempt, setAttempt] = useState(0), [failedImage, setFailedImage] = useState("");
  const [imageAttempt, setImageAttempt] = useState(0), [loadedId, setLoadedId] = useState("");
  const [controlVersion, setControlVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    setLoadError(""); setLibrary(null);
    fetch(INDEX, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error(`Library request failed (${response.status}).`);
      return validateLibrary(await response.json());
    }).then(data => {
      if (cancelled) return;
      setLibrary(data); setFuel(data.fuels[0].name); setValues({ ...data.fuels[0].defaults });
    }).catch(error => { if (error.name !== "AbortError" && !cancelled) setLoadError(error.message); });
    return () => { cancelled = true; controller.abort(); };
  }, [attempt]);

  const selectedFuel = library?.fuels.find(f => f.name === fuel);
  const matches = useMemo(() => {
    if (!library || !selectedFuel) return [];
    return library.records.filter(r => r.fuel === fuel).map(record => ({
      ...record,
      distance: Math.sqrt(library.fields.reduce((sum, field, j) => sum + ((record.features[field.key] - values[field.key]) / library.scale[j]) ** 2, 0) / library.fields.length),
    })).sort((a, b) => a.distance - b.distance || a.id.localeCompare(b.id));
  }, [library, selectedFuel, fuel, values]);
  const match = matches[0];
  const exact = match && library.fields.every(f => Math.abs(match.features[f.key] - values[f.key]) < 1e-5);

  function selectFuel(name) {
    const next = library.fuels.find(f => f.name === name);
    setFuel(name); setValues({ ...next.defaults }); setFailedImage(""); setImageAttempt(0);
  }
  function reset() {
    setValues({ ...selectedFuel.defaults }); setFailedImage(""); setImageAttempt(0);
    setControlVersion(n => n + 1);
  }
  function selectRun(id) {
    const run = library.records.find(r => r.id === id);
    if (!run) return;
    setFuel(run.fuel); setValues({ ...run.features }); setFailedImage(""); setImageAttempt(0);
    setControlVersion(n => n + 1);
  }

  if (loadError) return <div className={styles.root}><div className={styles.errorBox} role="alert"><h2>Flame library unavailable</h2><p>{loadError}</p><button onClick={() => setAttempt(n => n + 1)}>Retry loading library</button></div></div>;
  if (!library || !match) return <div className={styles.root}><p role="status">Loading recorded FLEX-2 flames…</p></div>;

  return (
    <div className={styles.root}>
      <div className={styles.heading}>
        <div><p className={styles.eyebrow}>NASA FLEX-2 · microgravity droplets</p><h2>Find a recorded flame</h2><p>Explore real colour images by fuel, chamber pressure and temperature.</p></div>
        <span className={styles.count}>{library.records.length} verified runs</span>
      </div>
      <div className={styles.grid}>
        <section className={styles.controls} aria-label="FLEX-2 retrieval conditions">
          <label className={styles.selectLabel} htmlFor="retrieval-fuel">Fuel</label>
          <select id="retrieval-fuel" value={fuel} onChange={event => selectFuel(event.target.value)}>
            {library.fuels.map(f => <option key={f.name} value={f.name}>{f.name} · {f.count} runs</option>)}
          </select>
          {library.fields.map(field => <ConditionControl key={`${fuel}-${controlVersion}-${field.key}`} field={field} range={selectedFuel.ranges[field.key]} value={values[field.key]}
            onChange={value => setValues(previous => ({ ...previous, [field.key]: value }))} />)}
          <button className={styles.reset} type="button" onClick={reset}>Reset retrieval conditions</button>
          <label className={styles.selectLabel} htmlFor="retrieval-run">Load a recorded run</label>
          <select id="retrieval-run" value={exact ? match.id : ""} onChange={event => selectRun(event.target.value)}>
            <option value="">Choose a run</option>
            {library.records.map(record => <option key={record.id} value={record.id}>{record.id} · {record.fuel}</option>)}
          </select>
          <p className={styles.note}>These controls apply to the FLEX-2 library. Chamber temperature is not flame temperature. Oxygen and droplet-size labels are not yet linked per run.</p>
        </section>
        <section className={styles.result} aria-label="Retrieved flame result" data-run-id={match.id}>
          <div className={styles.resultTop}><span>Recorded image</span><span role="status" aria-live="polite">{exact ? "Exact recorded conditions" : "Closest available conditions"}</span></div>
          <figure>
            <div className={styles.imageFrame}>
              {failedImage === match.id ? <div className={styles.imageError} role="alert"><p>This recorded image could not load.</p><button onClick={() => { setFailedImage(""); setImageAttempt(n => n + 1); }}>Retry image</button></div> : <>
                <Image key={`${match.id}-${imageAttempt}`} src={match.image + (imageAttempt ? `?retry=${imageAttempt}` : "")} alt={`Recorded ${fuel} droplet flame in microgravity, NASA FLEX-2 run ${match.id}`}
                  width={256} height={256} unoptimized className={styles.image} onError={() => setFailedImage(match.id)} onLoad={() => setLoadedId(match.id)} />
                {loadedId !== match.id && <span className={styles.imageLoading} role="status">Loading image…</span>}
              </>}
            </div>
            <figcaption><strong>{match.id}</strong><span>{match.fuel} · {match.features.pressure_kpa.toFixed(2)} kPa · {match.features.temperature_c.toFixed(2)} °C</span></figcaption>
          </figure>
          <dl className={styles.conditions}>
            {library.fields.map(field => <div key={field.key}><dt>{field.label}</dt><dd><span>Requested {values[field.key].toFixed(2)} {field.unit}</span><strong>Recorded {match.features[field.key].toFixed(2)} {field.unit}</strong></dd></div>)}
          </dl>
          <p className={styles.note}>The image changes when another recorded run becomes closer. This is retrieved experimental evidence, not a generated prediction.</p>
          <details><summary>Source and image preparation</summary><p>{library.display_note}</p><p>{library.stage}</p><p>{library.limitation}</p><p>Source archive: <span className={styles.archive}>{match.archive}</span></p><p>NASA public data · {library.license}</p><a href={library.source_url} target="_blank" rel="noopener noreferrer">Open NASA FLEX-2 dataset ↗</a><a href={match.image} target="_blank" rel="noopener noreferrer">Open this prepared image ↗</a></details>
        </section>
      </div>
    </div>
  );
}
