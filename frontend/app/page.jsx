"use client";

import { useState, useEffect, useRef } from "react";
import { LiquidButton } from "../components/ui/liquid-glass-button";

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

function Slider({ name, label, suffix, min, max, step, value, onChange }) {
  const [draft, setDraft] = useState(String(value));
  useEffect(() => setDraft(String(value)), [value]);
  const change = (v) =>
    onChange(Number(Math.min(max, Math.max(min, v)).toFixed(2)));
  return (
    <div className="slider-field">
      <div>
        <label htmlFor={name}>{label}</label>
        <span className="editable-value"><input aria-label={`${label} value`} type="number" required min={min} max={max} step={step} value={draft} onChange={e => {setDraft(e.target.value); const n=e.target.valueAsNumber; if(Number.isFinite(n) && n>=min && n<=max) onChange(n);}} onBlur={() => {const n=Number(draft); if(draft.trim() && Number.isFinite(n)) {const bounded=Number(Math.min(max,Math.max(min,n)).toFixed(2));onChange(bounded);setDraft(String(bounded));} else setDraft(String(value));}}/><span>{suffix}</span></span>
      </div>
      <input
        id={name}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-valuetext={`${value} ${suffix}`}
        onChange={(e) => change(Number(e.target.value))}
      />
      <div className="slider-limits">
        <span>{min}</span>
        <button
          type="button"
          aria-label={`Decrease ${label}`}
          disabled={value <= min}
          onClick={() => change(Number(value) - step)}
        >
          −
        </button>
        <button
          type="button"
          aria-label={`Increase ${label}`}
          disabled={value >= max}
          onClick={() => change(Number(value) + step)}
        >
          +
        </button>
        <span>
          {max} {suffix}
        </span>
      </div>
    </div>
  );
}

export default function Home() {
  const [chatOpen, setChatOpen] = useState(false);
  const [mobile, setMobile] = useState(false);
  const chatRef = useRef(null),
    chatTrigger = useRef(null);
  useEffect(() => {
    const media = matchMedia("(min-width: 721px)");
    const sync = () => {
      setMobile(!media.matches);

    };
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);
  useEffect(() => {
    if (chatOpen && mobile) chatRef.current?.focus();
  }, [chatOpen, mobile]);
  function closeChat() {
    setChatOpen(false);
    chatTrigger.current?.focus();
  }
  function handleChatKey(e) {
    if (e.key === "Escape") closeChat();
    if (e.key === "Tab" && mobile) {
      const nodes = chatRef.current.querySelectorAll(
        "button:not(:disabled),textarea,a[href]",
      );
      const first = nodes[0],
        last = nodes[nodes.length - 1];
      if (
        e.shiftKey &&
        (document.activeElement === first ||
          document.activeElement === chatRef.current)
      ) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }
  const [values, setValues] = useState(defaults);
  const [unit, setUnit] = useState("C");
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState("");
  const view = "flame";
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState([]);
  const [paused, setPaused] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [animationKey, setAnimationKey] = useState(0);
  const update = (key, value) => {
    setValues((v) => ({ ...v, [key]: value }));
    setSnapshot(null);
    setError("");
  };
  const temperature =
    values.temperature === ""
      ? ""
      : unit === "C"
        ? values.temperature
        : Number((Number(values.temperature) + 273.15).toFixed(2));
  function reset() {
    setValues(defaults);
    setUnit("C");
    setSnapshot(null);
    setError("");
  }
  function preview(event) {
    event.preventDefault();
    if (Number(values.oxygen) + Number(values.co2) > 100) {
      setError("Oxygen and CO₂ concentrations must total 100% or less.");
      document
        .getElementById("parameters")
        .scrollIntoView({ block: "nearest" });
      return;
    }
    const next = { ...values };
    setSnapshot(next);
    setError("");
    if (event.nativeEvent.submitter?.value === "send" && prompt.trim()) {
      setMessages((old) => [...old, { text: prompt.trim(), parameters: next }]);
      setPrompt("");
    }
  }
  const nav = [
    ["workspace", "Workspace", "chat"],
    ["flame", "Flame simulation", "flame"],
  ];
  return (
    <div className={`app-shell ${chatOpen ? "chat-open" : ""}`}>
      <div className="workspace-shell" id="workspace">
        <header className="topbar">
          <a className="brand" href="#workspace">
            ember<span>.</span>
          </a>
          <button
            className="text-button"
            onClick={() => {
              reset();
              setMessages([]);
              setPrompt("");
              setPaused(false);
            }}
          >
            + New scenario
          </button>
          <button
            ref={chatTrigger}
            className="chat-toggle"
            aria-expanded={chatOpen}
            aria-controls="chat-panel"
            onClick={() => (chatOpen ? closeChat() : setChatOpen(true))}
          >
            Scenario chat
          </button>
          <span>
            Ember <span className="header-divider">/</span>{" "}
            <b>{nav.find(([key]) => key === view)[1]}</b>
          </span>
          <a href="#parameters" className="parameter-link">
            <Symbol name="sliders" />
            Edit parameters
          </a>
        </header>
        <div className="content-grid">
          {chatOpen && mobile && (
            <button
              className="chat-backdrop"
              aria-label="Dismiss chat"
              onClick={closeChat}
            />
          )}
          <main className="conversation">
            <div className="dashboard-intro">
              <div><p className="dashboard-kicker">EMBER / WORKSPACE</p><h1>Flame simulation</h1><p>Explore a scenario by adjusting the environment below.</p></div>
              <a className="dashboard-link" href="#parameters">Adjust parameters <span aria-hidden="true">↓</span></a>
            </div>
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
                      <h2 id="flame-heading">Flame simulation</h2>
                    </div>
                    <span className="preview-badge">Preview</span>
                  </div>
                  <div className={`flame-stage ${paused ? "paused" : ""}`} style={{ "--playback-speed": speed }} key={animationKey}>
                    <div className="field-overlay" aria-hidden="true"><span>RELATIVE FIELD</span><span>+Y</span><span>+X →</span></div>
                    <svg
                      viewBox="0 0 400 250"
                      role="img"
                      aria-label="Decorative flame illustration; not a calculated flame prediction"
                      className="flame-art"
                    >
                      <defs>
                        <linearGradient id="flame-fill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0" stopColor="#ff9a43" />
                          <stop offset=".38" stopColor="#ff9359" />
                          <stop offset=".61" stopColor="#b475a2" />
                          <stop offset=".82" stopColor="#287cc4" />
                          <stop offset="1" stopColor="#2445ad" stopOpacity=".7" />
                        </linearGradient>
                        <linearGradient id="flame-rim" x1="0" y1="0" x2="0" y2="1">
                          <stop stopColor="#2449ce" />
                          <stop offset=".55" stopColor="#359df1" />
                          <stop offset="1" stopColor="#4bb9f4" stopOpacity=".65" />
                        </linearGradient>
                        <filter id="flame-soft" x="-30%" y="-25%" width="160%" height="150%">
                          <feGaussianBlur stdDeviation="4" />
                        </filter>
                        <filter id="flame-glow" x="-50%" y="-40%" width="200%" height="180%">
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
                      <rect x="171" y="218" width="58" height="10" rx="2" fill="#080b10" />
                    </svg>
                    <span className="stage-label">
                      ILLUSTRATIVE
                    </span>
                  </div>
                  <div className="card-footer">
                    <span>{values.fuel} · Illustrative graphic</span>
                    <div className="playback-controls"><label>Speed <select value={speed} onChange={e => setSpeed(Number(e.target.value))} aria-label="Animation playback speed"><option value={0.5}>0.5×</option><option value={1}>1×</option><option value={2}>2×</option></select></label>
                    <button className="text-button" type="button" onClick={() => { setAnimationKey(k => k + 1); setPaused(false); }}>Restart</button>
                    <button
                      className="text-button"
                      aria-pressed={paused}
                      onClick={() => setPaused(!paused)}
                    >
                      {paused ? "Play" : "Pause"}
                    </button></div>
                  </div>
                </section>
              )}
            </div>
            <section className="prediction-panel" aria-labelledby="prediction-heading">
              <div className="prediction-heading"><div className="prediction-title"><span className="prediction-icon" aria-hidden="true">✧</span><h2 id="prediction-heading">Prediction analysis</h2></div><span className="model-status">Awaiting model</span></div>
              <div className="prediction-metrics"><div><span>Flame height</span><strong>— <small>mm</small></strong></div><div><span>Peak temperature</span><strong>— <small>K</small></strong></div><div><span>Model confidence</span><strong>— <small>%</small></strong></div></div>
              <div className="prediction-note"><span className="prediction-info" aria-hidden="true">ⓘ</span><div><strong>AI interpretation</strong><p>Model predictions and interpretation will appear here when a prediction model is connected.</p></div></div>
            </section>
            <div className="readouts-heading"><h2>Environmental conditions</h2><span>Current inputs</span></div>
            <div className="dashboard-readouts" aria-label="Current scenario inputs">
              {[["Oxygen", values.oxygen, "%", "Reference: Earth 20.9%", 100, "oxygen"], ["Pressure", values.pressure, "kPa", "Reference: Earth 101.3 kPa", 500, "pressure"], ["Airflow", values.flow, "m/s", "Input range: 0–100 m/s", 100, "airflow"], ["Gravity", values.gravity, "g", "Reference: Earth 1 g", 5, "gravity"]].map(([label, value, unitLabel, context, max, kind]) => <div className={`instrument ${kind}`} key={kind}><span>{label}</span><strong>{value}<small> {unitLabel}</small></strong><div className="instrument-track" aria-hidden="true"><i style={{ width: `${Math.min(100, Math.max(0, Number(value) / max * 100))}%` }} /></div><p>{context}</p></div>)}
            </div>
            <div className="scenario-strip" role="status">
              <span className={`status-dot ${snapshot ? "ready" : ""}`} />
              {snapshot
                ? "Parameters applied"
                : "Adjust parameters below"}
            </div>
          <section
            className="parameter-panel"
            id="parameters"
            aria-labelledby="parameters-heading"
          >
            <div className="parameters-heading">
              <div>
                <h2 id="parameters-heading">Parameters</h2>

              </div>
              <Symbol name="sliders" />
            </div>
            <form id="scenario-form" onSubmit={preview}>
              <div className="field-section">
                <span className="field-section-title">
                  Atmospheric conditions
                </span>
                <div className="fields-grid">
                  {[
                    ...fields.filter(([key]) => key !== "area"),
                    [
                      "temperature",
                      "Temperature",
                      unit === "C" ? "°C" : "K",
                      unit === "C" ? -273.15 : 0,
                      unit === "C" ? 2000 : 2273.15,
                      0.01,
                    ],
                  ].map(([key, label, suffix, min, max, step]) => (
                    <Slider
                      key={key}
                      name={key}
                      label={label}
                      suffix={suffix}
                      min={min}
                      max={max}
                      step={step}
                      value={key === "temperature" ? temperature : values[key]}
                      onChange={(v) =>
                        update(
                          key,
                          key === "temperature" && unit === "K"
                            ? Number((v - 273.15).toFixed(2))
                            : v,
                        )
                      }
                    />
                  ))}
                  <button
                    type="button"
                    className="unit-toggle"
                    onClick={() => setUnit(unit === "C" ? "K" : "C")}
                  >
                    Temperature unit: {unit === "C" ? "°C → K" : "K → °C"}
                  </button>
                </div>
              </div>
              <div className="field-section">
                <span className="field-section-title">Fuel & surroundings</span>
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
          </main>
          <aside
            className="chat-panel"
            id="chat-panel"
            hidden={!chatOpen}
            ref={chatRef}
            tabIndex={-1}
            role={mobile ? "dialog" : undefined}
            aria-modal={mobile || undefined}
            aria-label="Scenario chat"
            onKeyDown={handleChatKey}
          >
            <div className="chat-heading">
              <h2>Experiment assistant</h2>
              <button onClick={closeChat} aria-label="Close chat">
                ×
              </button>
            </div>{" "}
            <div className="chat-summary"><span>CURRENT INPUTS</span><p>{values.oxygen}% O₂ · {values.pressure} kPa · {values.gravity} g</p><small>Notes are saved locally for this session. AI explanations are not connected.</small></div>
            <section
              className="conversation-log"
              aria-label="Scenario conversation"
              aria-live="polite"
            >
              {messages.length === 0 ? (
                <div className="conversation-intro">
                  <span className="assistant-mark">e.</span>
                  <div>
                    <h2>Scenario notes</h2>
                    <p>
                      Save experiment observations with the current parameter values.
                    </p>
                  </div>
                </div>
              ) : (
                messages.map((message, index) => (
                  <article className="conversation-turn" key={index}>
                    <div className="user-message">{message.text}</div>
                    <div className="assistant-message">
                      <span className="assistant-mark">e.</span>
                      <div>
                        <p>
                          Saved · {message.parameters.oxygen}%
                          oxygen, {message.parameters.pressure} kPa pressure,{" "}
                          {message.parameters.flow} m/s airflow and{" "}
                          {message.parameters.gravity} g gravity.
                        </p>
                      </div>
                    </div>
                  </article>
                ))
              )}
            </section>
            <div className="composer-area">
              <div className="composer">
                <label className="sr-only" htmlFor="scenario-prompt">
                  Describe your scenario
                </label>
                <textarea
                  id="scenario-prompt"
                  form="scenario-form"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Add a scenario note…"
                  maxLength={2000}
                  rows={2}
                />
                <div className="composer-toolbar">
                  <a href="#parameters">
                    <Symbol name="sliders" />
                    Parameters
                  </a>
                  <button
                    type="submit"
                    form="scenario-form"
                    value="send"
                    className="send-button"
                    aria-label="Save scenario note"
                    disabled={!prompt.trim()}
                  >
                    <Symbol name="arrow" />
                  </button>
                </div>
              </div>
              <p className="composer-disclaimer">
                Model not connected · Notes only.
              </p>
            </div>
          </aside>{" "}

        </div>
      </div>
    </div>
  );
}
