"use client";

import { useState, useEffect, useMemo } from "react";
import { LiquidButton } from "../components/ui/liquid-glass-button";
import { FireSafetyComparison } from "../components/fire-safety-comparison";
import { FeatureRetrieval } from "../components/feature-retrieval";
import { HybridSimulation } from "../components/hybrid-simulation";
import {
  NASA_DEFAULTS,
  NasaParameterFields,
  SHARED_FIELDS,
  VACUUM_NOTE,
  convertRaw,
  isVacuum,
  nasaInputsFromRaw,
  rawFromBase,
} from "../components/nasa-parameter-fields";

// Shared values: the flame simulation's inputs mapped to the NASA comparison's
// base units (CO₂ % -> ppm; gravity in g -> microgravity below 0.05 g).
function sharedNasaInputs(values) {
  const num = (x) =>
    x === "" || x === null || x === undefined || !Number.isFinite(Number(x))
      ? null
      : Number(x);
  const g = num(values.gravity);
  const co2 = num(values.co2);
  return {
    o2_pct: num(values.oxygen),
    pressure_kpa: num(values.pressure),
    internal_temp_c: num(values.temperature),
    co2_ppm: co2 === null ? null : co2 * 10000,
    humidity_pct: num(values.humidity),
    gravity: g === null ? "" : g < 0.05 ? "Microgravity (~0 g)" : `${g} g`,
  };
}

const defaults = {
  oxygen: 20.9,
  pressure: 101.3,
  flow: 0.4,
  direction: 90,
  temperature: 22,
  gravity: 1,
  area: 120,
  humidity: 45,
  co2: 0.04,
  fuel: "Polymer / plastic",
  location: "Research module · Bay 04",
  machinery: "Electrical equipment",
};
const fields = [
  ["oxygen", "Oxygen concentration", "%", 0, 100, 0.1],
  ["pressure", "Ambient pressure", "kPa", 0.1, 500, 0.1],
  ["flow", "Wind / flow speed", "m/s", 0, 100, 0.1],
  ["direction", "Flow direction", "°", 0, 359, 1],
  ["gravity", "Gravity", "g", 0, 5, 0.01],
  ["area", "Fuel surface area", "cm²", 0, 100000, 1],
  ["humidity", "Relative humidity", "%", 0, 100, 1],
  ["co2", "CO₂ concentration", "%", 0, 100, 0.01],
];

// Unit choices for sliders. The first unit is the base unit the value is stored in.
const PERCENT_UNITS = [
  { unit: "%", toBase: (x) => x, fromBase: (x) => x },
  { unit: "ppm", toBase: (x) => x / 10000, fromBase: (x) => x * 10000 },
];
const SLIDER_UNITS = {
  oxygen: PERCENT_UNITS,
  co2: PERCENT_UNITS,
  pressure: [
    { unit: "kPa", toBase: (x) => x, fromBase: (x) => x },
    {
      unit: "psia",
      toBase: (x) => x * 6.894757,
      fromBase: (x) => x / 6.894757,
    },
    { unit: "atm", toBase: (x) => x * 101.325, fromBase: (x) => x / 101.325 },
  ],
  temperature: [
    { unit: "°C", toBase: (x) => x, fromBase: (x) => x },
    { unit: "K", toBase: (x) => x - 273.15, fromBase: (x) => x + 273.15 },
    {
      unit: "°F",
      toBase: (x) => ((x - 32) * 5) / 9,
      fromBase: (x) => (x * 9) / 5 + 32,
    },
  ],
};
// Up to 6 significant figures, without float noise (e.g. 209000 not 208999.99999).
const tidyNumber = (x) => Number(Number(x).toPrecision(6));

function Symbol({ name, ...props }) {
  const paths = {
    plus: "M12 5v14M5 12h14",
    chat: "M21 11a8 8 0 0 1-8 8H6l-4 3V11a9 9 0 0 1 19 0Z",
    flame:
      "M13 3c1 6-5 6-3 11 2-1 3-3 3-4 5 4 7 11-1 11C3 21 3 12 7 8c0 4 2 4 2 4-1-4 3-6 4-9Z",
    physics: "M4 7h16M7 4v16M4 17h16M17 4v16",
    sliders: "M5 3v8m0 4v6M12 3v3m0 4v11M19 3v11m0 4v3M2 11h6m1-5h6m1 8h6",
    arrow: "M12 19V5m-6 6 6-6 6 6",
  };
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path d={paths[name] || paths.chat} />
    </svg>
  );
}

function Slider({
  name,
  label,
  suffix,
  min,
  max,
  step,
  value,
  onChange,
  units,
  onUnitChange,
  disabled = false,
  note = "",
}) {
  const [draft, setDraft] = useState(String(value));
  useEffect(() => setDraft(String(value)), [value]);
  // Keep at least as many decimals as the step needs (e.g. atm or psia steps).
  const decimals = Math.min(
    6,
    Math.max(2, -Math.floor(Math.log10(Math.abs(step) || 1))),
  );
  const change = (v) =>
    onChange(Number(Math.min(max, Math.max(min, v)).toFixed(decimals)));
  return (
    <div className={`slider-field${disabled ? " is-disabled" : ""}`}>
      <div>
        <label htmlFor={name}>{label}</label>
        <span className="editable-value">
          <input
            aria-label={`${label} value`}
            disabled={disabled}
            aria-describedby={note ? `${name}-note` : undefined}
            type="number"
            required
            min={min}
            max={max}
            step={units ? "any" : step}
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
              const n = e.target.valueAsNumber;
              if (Number.isFinite(n) && n >= min && n <= max) onChange(n);
            }}
            onBlur={() => {
              const n = Number(draft);
              if (draft.trim() && Number.isFinite(n)) {
                const bounded = Number(
                  Math.min(max, Math.max(min, n)).toFixed(decimals),
                );
                onChange(bounded);
                setDraft(String(bounded));
              } else setDraft(String(value));
            }}
          />
          {units ? (
            <select
              className="slider-unit"
              disabled={disabled}
              aria-label={`${label} unit`}
              value={suffix}
              onChange={(e) => onUnitChange(e.target.value)}
            >
              {units.map((u) => (
                <option key={u.unit}>{u.unit}</option>
              ))}
            </select>
          ) : (
            <span>{suffix}</span>
          )}
        </span>
      </div>
      <input
        id={name}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        aria-describedby={note ? `${name}-note` : undefined}
        aria-valuetext={`${value} ${suffix}`}
        onChange={(e) => change(Number(e.target.value))}
      />
      <div className="slider-limits">
        <span>{Number(Number(min).toPrecision(5))}</span>
        <button
          type="button"
          aria-label={`Decrease ${label}`}
          disabled={disabled || value <= min}
          onClick={() => change(Number(value) - step)}
        >
          −
        </button>
        <button
          type="button"
          aria-label={`Increase ${label}`}
          disabled={disabled || value >= max}
          onClick={() => change(Number(value) + step)}
        >
          +
        </button>
        <span>
          {Number(Number(max).toPrecision(5))} {suffix}
        </span>
      </div>
      {note && (
        <small className="slider-note" id={`${name}-note`}>
          {note}
        </small>
      )}
    </div>
  );
}

export default function Home() {
  const [parametersOpen, setParametersOpen] = useState(false);
  useEffect(() => {
    const media = matchMedia("(min-width: 721px)");
    const wideMedia = matchMedia("(min-width: 1200px)");
    const sync = () => {
      if (!media.matches) setParametersOpen(false);
    };
    const syncPanels = () => {
      setParametersOpen(wideMedia.matches);
    };
    sync();
    syncPanels();
    media.addEventListener("change", sync);
    wideMedia.addEventListener("change", syncPanels);
    return () => {
      media.removeEventListener("change", sync);
      wideMedia.removeEventListener("change", syncPanels);
    };
  }, []);
  const [values, setValues] = useState(defaults);
  // NASA comparison inputs that the flame simulation doesn't have (raw text in
  // the chosen unit), their units, and the field definitions from fire-dashboard.
  const [nasaDefs, setNasaDefs] = useState(null);
  const [nasaRaw, setNasaRaw] = useState(() =>
    Object.fromEntries(
      Object.entries(NASA_DEFAULTS).map(([k, v]) => [k, String(v)]),
    ),
  );
  const [nasaUnits, setNasaUnits] = useState({});
  const dashboardInputs = useMemo(
    () => ({
      ...nasaInputsFromRaw(nasaDefs, nasaRaw, nasaUnits),
      ...sharedNasaInputs(values),
      // A vacuum has near-zero pressure: the slider value is ignored.
      ...(isVacuum(nasaRaw) ? { pressure_kpa: null } : {}),
    }),
    [nasaDefs, nasaRaw, nasaUnits, values],
  );
  const [sliderUnits, setSliderUnits] = useState({});
  const [, setSnapshot] = useState(null);
  const [error, setError] = useState("");
  const [view, setView] = useState("flame");
  const [retrievalSession, setRetrievalSession] = useState(0);
  const update = (key, value) => {
    setValues((v) => ({ ...v, [key]: value }));
    setSnapshot(null);
    setError("");
  };
  const sliderUnit = (key) =>
    SLIDER_UNITS[key]?.find((u) => u.unit === sliderUnits[key]) ||
    SLIDER_UNITS[key]?.[0];
  function reset() {
    setValues(defaults);
    setSnapshot(null);
    setError("");
    // Back to the default gas readings, shown in whatever units are selected.
    setNasaRaw(
      nasaDefs
        ? rawFromBase(nasaDefs, NASA_DEFAULTS, nasaUnits)
        : Object.fromEntries(
            Object.entries(NASA_DEFAULTS).map(([k, v]) => [k, String(v)]),
          ),
    );
  }
  // Fill both the shared values and the NASA-only inputs from one of the
  // dashboard's examples (the default one when no id is given).
  function loadNasaExample(id) {
    if (!nasaDefs) return;
    const ex =
      (typeof id === "string" &&
        nasaDefs.examples?.find((x) => x.id === id)?.values) ||
      nasaDefs.example;
    // "Lunar (0.17 g)" -> 0.17; microgravity -> 0.
    const g = String(ex.gravity || "");
    const gravity = g.startsWith("Microgravity")
      ? 0
      : Number((g.match(/([\d.]+)\s*g/) || [])[1]);
    setValues((v) => ({
      ...v,
      oxygen: ex.o2_pct,
      pressure: ex.pressure_kpa,
      temperature: ex.internal_temp_c,
      co2: Number((ex.co2_ppm / 10000).toFixed(4)),
      humidity: ex.humidity_pct ?? v.humidity,
      gravity: Number.isFinite(gravity) ? gravity : v.gravity,
    }));
    setNasaRaw(rawFromBase(nasaDefs, ex, nasaUnits));
    setSnapshot(null);
    setError("");
  }
  // Open the NASA comparison inputs and focus the requested field.
  function gotoNasaField(id) {
    const inputs = document.getElementById("nasa-inputs");
    if (inputs) inputs.open = true;
    const target = SHARED_FIELDS[id] || `nasa-${id}`;
    setTimeout(() => {
      const el = document.getElementById(target);
      if (!el) return;
      el.scrollIntoView({ block: "center" });
      el.focus({ preventScroll: true });
    }, 60);
  }
  function preview(event) {
    event.preventDefault();
    if (Number(values.oxygen) + Number(values.co2) > 100) {
      setError("Oxygen and CO₂ concentrations must total 100% or less.");
      document
        .getElementById("nasa-inputs")
        .scrollIntoView({ block: "nearest" });
      return;
    }
    const next = { ...values };
    setSnapshot(next);
    setError("");
  }
  const nav = [
    ["flame", "Flame simulation", "flame"],
    ["rooms", "Room simulation", "flame"],
  ];
  function changeView(next) {
    setView(next);
    window.scrollTo({ top: 0, behavior: "instant" });
    if (next === "flame")
      requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
  }
  function handleViewKey(event, key) {
    const index = nav.findIndex(([id]) => id === key);
    const next =
      event.key === "ArrowRight"
        ? (index + 1) % nav.length
        : event.key === "ArrowLeft"
          ? (index + nav.length - 1) % nav.length
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? nav.length - 1
              : null;
    if (next === null) return;
    event.preventDefault();
    changeView(nav[next][0]);
    document.getElementById(`${nav[next][0]}-tab`)?.focus();
  }
  return (
    <div className={`app-shell ${parametersOpen ? "controls-open" : ""}`}>
      <div className="workspace-shell" id="workspace">
        <header className="topbar">
          <a className="brand" href="#workspace">
            pyroclast<span>.</span>
          </a>
          <h1 className="sr-only">Pyroclast dashboard · {nav.find(([key]) => key === view)[1]}</h1>
          <div className="dashboard-tabs" role="tablist" aria-label="Dashboard views">
            {nav.map(([key, label]) => <button key={key} id={`${key}-tab`} type="button" role="tab"
              aria-selected={view === key} aria-controls={`${key}-panel`} tabIndex={view === key ? 0 : -1}
              onClick={() => changeView(key)} onKeyDown={event => handleViewKey(event, key)}>{label}</button>)}
          </div>
          <button
            className="text-button new-scenario-button"
            aria-label="New scenario"
            onClick={() => {
              reset();
              setPaused(false);
              setRetrievalSession((n) => n + 1);
            }}
          >
            New scenario
          </button>
          <a
            className="text-button nasa-link"
            href="#nasa-comparison"
            onClick={() => {
              changeView("flame");
              requestAnimationFrame(() =>
                document
                  .getElementById("nasa-comparison")
                  ?.scrollIntoView({ block: "start" }),
              );
            }}
          >
            NASA data
          </a>
          <button
            className="panel-toggle"
            hidden={view !== "flame"}
            aria-expanded={parametersOpen}
            aria-controls="parameters"
            onClick={() => setParametersOpen((open) => !open)}
          >
            Parameters
          </button>
          <span>
            Pyroclast <span className="header-divider">/</span>{" "}
            <b>{nav.find(([key]) => key === view)[1]}</b>
          </span>
          <a href="#parameters" className="parameter-link">
            <Symbol name="sliders" />
            Edit parameters
          </a>
        </header>
        <div
          className="content-grid dashboard-tab-panel"
          id="flame-panel"
          role="tabpanel"
          aria-labelledby="flame-tab"
          hidden={view !== "flame"}
        >
          <main className="conversation">
            <div
              className={`simulation-grid ${view !== "workspace" ? "single-view" : ""}`}
            >
              {view !== "physics" && (
                <section
                  className="simulation-card flame-card"
                  aria-labelledby="flame-heading"
                >
                  <div className="card-heading">
                    <div className="card-title">
                      <span className="card-icon warm">
                        <Symbol name="flame" />
                      </span>
                      <h2 id="flame-heading" className="sr-only">
                        Flame preview
                      </h2>
                    </div>
                    <span className="preview-badge">Preview</span>
                  </div>
                  <div
                    className={`flame-stage ${paused ? "paused" : ""}`}
                    style={{ "--playback-speed": speed }}
                    key={animationKey}
                  >
                    <svg
                      className="ember-particles"
                      viewBox="0 0 600 300"
                      preserveAspectRatio="xMidYMid slice"
                      aria-hidden="true"
                    >
                      <defs>
                        <radialGradient id="particle-glow">
                          <stop stopColor="#f35b25" stopOpacity=".28" />
                          <stop
                            offset="1"
                            stopColor="#f35b25"
                            stopOpacity="0"
                          />
                        </radialGradient>
                      </defs>
                      <ellipse
                        cx="300"
                        cy="165"
                        rx="250"
                        ry="130"
                        fill="url(#particle-glow)"
                      />
                      {Array.from({ length: 180 }, (_, i) => {
                        const x = (i * 137.508) % 600;
                        const spread = ((i * 79) % 100) / 100;
                        const y =
                          155 +
                          Math.sin(x / 85) * 38 +
                          (spread - 0.5) *
                            (50 + (95 * Math.abs(x - 300)) / 300);
                        // Round so server (Node) and browser Math.sin agree; avoids a hydration mismatch.
                        const round = (v) => Math.round(v * 100) / 100;
                        return (
                          <circle
                            key={i}
                            cx={round(x)}
                            cy={round(y)}
                            r={i % 13 === 0 ? 1.5 : 0.65}
                            fill={i % 4 === 0 ? "#ffad64" : "#e6542d"}
                            opacity={round(0.2 + (i % 5) * 0.1)}
                          />
                        );
                      })}
                    </svg>

                    <div
                      className="field-annotations"
                      aria-label="Current flame scenario inputs"
                    >
                      <div className="field-annotation annotation-oxygen">
                        <span>ATMOSPHERE / O₂</span>
                        <strong>
                          {values.oxygen}
                          <small> %</small>
                        </strong>
                        <i />
                      </div>
                      <div className="field-annotation annotation-pressure">
                        <span>AMBIENT PRESSURE</span>
                        <strong>
                          {values.pressure}
                          <small> kPa</small>
                        </strong>
                        <i />
                      </div>
                      <div className="field-annotation annotation-airflow">
                        <span>AIRFLOW</span>
                        <strong>
                          {values.flow}
                          <small> m/s</small>
                        </strong>
                        <i />
                      </div>
                      <div className="field-annotation annotation-gravity">
                        <span>GRAVITY</span>
                        <strong>
                          {values.gravity}
                          <small> g</small>
                        </strong>
                        <i />
                      </div>
                    </div>
                    <svg
                      viewBox="0 0 400 250"
                      role="img"
                      aria-label="Decorative flame illustration; not a calculated flame prediction"
                      className="flame-art"
                    >
                      <defs>
                        <linearGradient
                          id="flame-fill"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop offset="0" stopColor="#ff9a43" />
                          <stop offset=".38" stopColor="#ff9359" />
                          <stop offset=".61" stopColor="#b475a2" />
                          <stop offset=".82" stopColor="#287cc4" />
                          <stop
                            offset="1"
                            stopColor="#2445ad"
                            stopOpacity=".7"
                          />
                        </linearGradient>
                        <linearGradient
                          id="flame-rim"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop stopColor="#2449ce" />
                          <stop offset=".55" stopColor="#359df1" />
                          <stop
                            offset="1"
                            stopColor="#4bb9f4"
                            stopOpacity=".65"
                          />
                        </linearGradient>
                        <filter
                          id="flame-soft"
                          x="-30%"
                          y="-25%"
                          width="160%"
                          height="150%"
                        >
                          <feGaussianBlur stdDeviation="4" />
                        </filter>
                        <filter
                          id="flame-glow"
                          x="-50%"
                          y="-40%"
                          width="200%"
                          height="180%"
                        >
                          <feGaussianBlur stdDeviation="9" />
                        </filter>
                      </defs>
                      <g className="flame-shape">
                        <path
                          className="flame-aura"
                          d="M146 218C130 191 126 162 132 131C140 87 165 49 200 48C235 49 260 87 268 131C274 162 270 191 254 218Z"
                          fill="#1d65e8"
                          opacity=".55"
                          filter="url(#flame-glow)"
                        />
                        <path
                          className="flame-core"
                          d="M146 216C132 191 129 163 135 133C143 91 168 53 200 53C232 53 257 91 265 133C271 163 268 191 254 216Z"
                          fill="url(#flame-fill)"
                          stroke="url(#flame-rim)"
                          strokeWidth="9"
                          filter="url(#flame-soft)"
                        />
                        <path
                          className="flame-edge"
                          d="M147 211C132 182 133 152 140 130M253 211C268 182 267 152 260 130"
                          fill="none"
                          stroke="#50bcff"
                          strokeWidth="3"
                          opacity=".65"
                          filter="url(#flame-soft)"
                        />
                      </g>
                    </svg>
                  </div>
                  <div className="card-footer">
                    <span>{values.fuel}</span>
                    <div className="playback-controls">
                      <label>
                        Speed{" "}
                        <select
                          value={speed}
                          onChange={(e) => setSpeed(Number(e.target.value))}
                          aria-label="Animation playback speed"
                        >
                          <option value={0.5}>0.5×</option>
                          <option value={1}>1×</option>
                          <option value={2}>2×</option>
                        </select>
                      </label>
                      <button
                        className="text-button"
                        type="button"
                        onClick={() => {
                          setAnimationKey((k) => k + 1);
                          setPaused(false);
                        }}
                      >
                        Restart
                      </button>
                      <button
                        className="text-button"
                        aria-pressed={paused}
                        onClick={() => setPaused(!paused)}
                      >
                        {paused ? "Play" : "Pause"}
                      </button>
                    </div>
                  </div>
                </section>
              )}
            </div>
            <div className="scenario-strip" role="status">
              <span className={`status-dot ${snapshot ? "ready" : ""}`} />
              {snapshot
                ? "Parameters applied"
                : "Adjust parameters to configure your scenario"}
            </div>
            {/* One triangle tab: on the panel's right edge (◀ hides it), or on the
              screen's left edge when hidden (▶ shows it). */}
            {view === "flame" && (
              <button
                type="button"
                className={`parameters-tab ${parametersOpen ? "is-open" : ""}`}
                aria-controls="parameters"
                aria-expanded={parametersOpen}
                aria-label={
                  parametersOpen ? "Hide parameters" : "Show parameters"
                }
                title={parametersOpen ? "Hide parameters" : "Show parameters"}
                onClick={() => setParametersOpen((open) => !open)}
              >
                <span className="parameters-tab-arrow" aria-hidden="true">
                  {parametersOpen ? "◀" : "▶"}
                </span>
              </button>
            )}
            <section
              className={`parameter-panel ${parametersOpen ? "parameters-open" : ""}`}
              id="parameters"
              onKeyDown={(e) => {
                if (e.key === "Escape") setParametersOpen(false);
              }}
              aria-labelledby="parameters-heading"
            >
              <div className="parameters-heading">
                <div>
                  <h2 id="parameters-heading">Parameters</h2>
                </div>
              </div>
              <form id="scenario-form" onSubmit={preview}>
                <div className="field-section">
                  <span className="field-section-title">
                    Atmospheric conditions
                  </span>
                  <div className="fields-grid">
                    {[
                      ...fields.filter(([key]) => key !== "area"),
                      ["temperature", "Temperature", "°C", -273.15, 2000, 0.01],
                    ].map(([key, label, suffix, min, max, step]) => {
                      // Sliders with unit choices show converted values; the
                      // stored value stays in the base unit.
                      const u = sliderUnit(key);
                      const show = (x) => (u ? tidyNumber(u.fromBase(x)) : x);
                      return (
                        <Slider
                          key={key}
                          name={key}
                          label={label}
                          suffix={u ? u.unit : suffix}
                          min={show(min)}
                          max={show(max)}
                          step={
                            u
                              ? tidyNumber(
                                  Math.abs(
                                    u.fromBase(min + step) - u.fromBase(min),
                                  ),
                                )
                              : step
                          }
                          value={
                            values[key] === "" ? "" : show(Number(values[key]))
                          }
                          units={SLIDER_UNITS[key]}
                          disabled={key === "pressure" && isVacuum(nasaRaw)}
                          note={
                            key === "pressure" && isVacuum(nasaRaw)
                              ? VACUUM_NOTE
                              : ""
                          }
                          onUnitChange={(next) =>
                            setSliderUnits((s) => ({ ...s, [key]: next }))
                          }
                          onChange={(v) =>
                            update(key, u ? tidyNumber(u.toBase(v)) : v)
                          }
                        />
                      );
                    })}
                  </div>
                </div>
                <div className="field-section">
                  <span className="field-section-title">
                    Fuel & surroundings
                  </span>
                  <div className="fields-grid">
                    <label className="field">
                      <span>Fuel material</span>
                      <select
                        value={values.fuel}
                        onChange={(e) => update("fuel", e.target.value)}
                      >
                        {[
                          "Polymer / plastic",
                          "Wood / cellulose",
                          "Textile / fabric",
                          "Liquid fuel",
                          "Metal",
                          "Other / unknown",
                        ].map((f) => (
                          <option key={f}>{f}</option>
                        ))}
                      </select>
                    </label>
                    <Slider
                      name="area"
                      label="Fuel surface area"
                      suffix="cm²"
                      min={0}
                      max={100000}
                      step={1}
                      value={values.area}
                      onChange={(v) => update("area", v)}
                    />{" "}
                    <label className="field full">
                      <span>Location</span>
                      <input
                        required
                        maxLength={100}
                        value={values.location}
                        onChange={(e) => update("location", e.target.value)}
                      />
                    </label>
                    <label className="field full">
                      <span>Nearby fuels or machinery</span>
                      <select
                        value={values.machinery}
                        onChange={(e) => update("machinery", e.target.value)}
                      >
                        {[
                          "Electrical equipment",
                          "Fuel storage",
                          "Mechanical equipment",
                          "Mixed fuels and machinery",
                          "None identified",
                          "Unknown",
                        ].map((m) => (
                          <option key={m}>{m}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                </div>

                <NasaParameterFields
                  defs={nasaDefs}
                  raw={nasaRaw}
                  unitPrefs={nasaUnits}
                  onChange={(id, value) =>
                    setNasaRaw((r) => ({ ...r, [id]: value }))
                  }
                  onUnitChange={(id, from, to) => {
                    setNasaRaw((r) => ({
                      ...r,
                      [id]: convertRaw(nasaDefs, id, r[id], from, to),
                    }));
                    setNasaUnits((u) => ({ ...u, [id]: to }));
                  }}
                />

                {error && (
                  <p className="form-error" role="alert">
                    {error}
                  </p>
                )}
                <div className="form-actions">
                  <LiquidButton type="submit">
                    Apply parameters <span aria-hidden="true">↗</span>
                  </LiquidButton>
                  <button
                    className="reset-button"
                    type="button"
                    onClick={reset}
                    aria-label="Reset parameters"
                  >
                    Reset
                  </button>
                </div>
              </form>
            </section>

            <section
              className="comparison-section"
              id="nasa-comparison"
              aria-labelledby="nasa-comparison-title"
            >
              <div className="comparison-heading">
                <div>
                  <h2 id="nasa-comparison-title">NASA data comparison</h2>
                  <p>
                    Your parameters checked against ACME, Saffire-I, SPICE and
                    SAME-R microgravity fire experiments. Edit values in the
                    Parameters panel.
                  </p>
                </div>
                <div className="comparison-actions">
                  <button
                    type="button"
                    className="text-button"
                    onClick={() => setParametersOpen(true)}
                  >
                    Edit parameters
                  </button>
                  <select
                    className="text-button example-select"
                    aria-label="Load an example scenario"
                    value=""
                    disabled={!nasaDefs}
                    onChange={(e) =>
                      e.target.value && loadNasaExample(e.target.value)
                    }
                  >
                    <option value="">Load example…</option>
                    {(nasaDefs?.examples || []).map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.label}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="text-button"
                    onClick={() => window.FireDashboard?.exportJSON()}
                  >
                    Export results
                  </button>
                </div>
              </div>
              <FireSafetyComparison
                inputs={dashboardInputs}
                onDefinitions={setNasaDefs}
                onGotoField={gotoNasaField}
                onLoadExample={() => loadNasaExample()}
              />
            </section>
          </main>
        </div>
        <main
          className="dashboard-tab-panel retrieval-tab-panel"
          id="retrieval-panel"
          role="tabpanel"
          aria-labelledby="retrieval-tab"
          hidden={view !== "retrieval"}
        >
          <FeatureRetrieval key={retrievalSession} />
        </main>
        {/* CNN flame image -> room spread physics (ml/dashboard_simulation.py). */}
        <main
          className="dashboard-tab-panel retrieval-tab-panel rooms-tab-panel"
          id="rooms-panel"
          role="tabpanel"
          aria-labelledby="rooms-tab"
          hidden={view !== "rooms"}
        >
          <HybridSimulation key={retrievalSession} />
        </main>
      </div>
    </div>
  );
}
