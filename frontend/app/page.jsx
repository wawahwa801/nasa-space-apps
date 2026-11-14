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
  const [chatOpen, setChatOpen] = useState(true);
  const [mobile, setMobile] = useState(false);
  const chatRef = useRef(null),
    chatTrigger = useRef(null);
  useEffect(() => {
    const media = matchMedia("(min-width: 721px)");
    const sync = () => {
      setMobile(!media.matches);
      setChatOpen(media.matches);
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
                  <div className={`flame-stage ${paused ? "paused" : ""}`}>
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
                          y1="1"
                          x2="0"
                          y2="0"
                        >
                          <stop stopColor="#ff622e" />
                          <stop offset=".5" stopColor="#ffb670" />
                          <stop offset="1" stopColor="#ffe7be" />
                        </linearGradient>
                        <radialGradient id="flame-halo">
                          <stop stopColor="#ff5a26" stopOpacity=".2" />
                          <stop
                            offset="1"
                            stopColor="#ff5a26"
                            stopOpacity="0"
                          />
                        </radialGradient>
                      </defs>
                      <ellipse
                        cx="200"
                        cy="170"
                        rx="145"
                        ry="85"
                        fill="url(#flame-halo)"
                      />
                      <path
                        d="M45 215H355"
                        stroke="#ffffff"
                        strokeOpacity=".12"
                      />
                      <g className="flame-shape">
                        <path
                          d="M200 213C142 213 139 175 158 147c-3 24 11 27 14 30-9-37 30-57 27-102 33 32 26 55 21 71 13-6 18-17 17-28 44 47 36 95-37 95Z"
                          fill="url(#flame-fill)"
                        />
                        <path
                          d="M200 213c-28 0-28-23-15-43-1 16 9 12 12 0 2-13 4-25 12-32-2 26 19 37 12 57-3 11-11 18-21 18Z"
                          fill="#fff0cb"
                        />
                      </g>
                      <rect
                        x="167"
                        y="216"
                        width="66"
                        height="8"
                        rx="4"
                        fill="#4c3b35"
                      />
                    </svg>
                    <span className="stage-label">
                      ILLUSTRATIVE
                    </span>
                  </div>
                  <div className="card-footer">
                    <span>{values.fuel}</span>
                    <button
                      className="text-button"
                      aria-pressed={paused}
                      onClick={() => setPaused(!paused)}
                    >
                      {paused ? "Play" : "Pause"}
                    </button>
                  </div>
                </section>
              )}
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
              <h2>Scenario chat</h2>
              <button onClick={closeChat} aria-label="Close chat">
                ×
              </button>
            </div>{" "}
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
                      Save a note with your parameters.
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
