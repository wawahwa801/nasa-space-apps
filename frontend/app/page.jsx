"use client";

import { useState } from "react";
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

export default function Home() {
  const [values, setValues] = useState(defaults);
  const [unit, setUnit] = useState("C");
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState("");
  const [view, setView] = useState("workspace");
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
    ["physics", "Physics simulation", "physics"],
  ];
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#workspace"
          onClick={() => setView("workspace")}
        >
          ember<span>.</span>
        </a>
        <button
          className="new-scenario"
          onClick={() => {
            reset();
            setMessages([]);
            setPrompt("");
            setView("workspace");
          }}
        >
          <Symbol name="plus" /> New scenario
        </button>
        <p className="nav-caption">YOUR WORKSPACE</p>
        <nav aria-label="Simulation workspace">
          {nav.map(([key, label, icon]) => (
            <button
              key={key}
              className={`nav-item ${view === key ? "active" : ""}`}
              aria-pressed={view === key}
              onClick={() => setView(key)}
            >
              <Symbol name={icon} />
              {label}
            </button>
          ))}
          <a className="nav-item" href="#parameters">
            <Symbol name="sliders" />
            Parameters
          </a>
        </nav>
        <div className="sidebar-note">
          <span className="status-dot" />
          Local workspace
          <p>Your scenarios stay in this page. Models are not connected.</p>
        </div>
        <div className="profile">
          <span className="avatar">JW</span>
          <div>
            Research workspace<small>Personal environment</small>
          </div>
        </div>
      </aside>
      <div className="workspace-shell" id="workspace">
        <header className="topbar">
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
          <main className="conversation">
            <section className="page-heading">
              <span className="eyebrow">FIRE & ENVIRONMENT LAB</span>
              <h1>What would you like to explore?</h1>
              <p>Define the environment. Explore the flame and the physics.</p>
            </section>
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
                    <span className="preview-badge">Visual preview</span>
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
                      ILLUSTRATIVE · NOT MODEL OUTPUT
                    </span>
                  </div>
                  <div className="card-footer">
                    <span>{values.fuel}</span>
                    <button
                      className="text-button"
                      aria-pressed={paused}
                      onClick={() => setPaused(!paused)}
                    >
                      {paused ? "Play preview" : "Pause preview"}
                    </button>
                  </div>
                  <p className="model-note">
                    Flame prediction model not connected.
                  </p>
                </section>
              )}
              {view !== "flame" && (
                <section
                  className="simulation-card physics-card"
                  aria-labelledby="physics-heading"
                >
                  <div className="card-heading">
                    <div className="card-title">
                      <span className="card-icon">
                        <Symbol name="physics" />
                      </span>
                      <h2 id="physics-heading">Physics simulation</h2>
                    </div>
                    <span className="preview-badge">Scene preview</span>
                  </div>
                  <div className="physics-stage">
                    <svg
                      className="room-diagram"
                      viewBox="0 0 620 330"
                      role="img"
                      aria-label="Illustrative room schematic showing fuel, equipment and airflow; not a simulation"
                    >
                      <defs>
                        <pattern
                          id="floorGrid"
                          width="30"
                          height="30"
                          patternUnits="userSpaceOnUse"
                          patternTransform="matrix(1 .48 -1 .48 310 90)"
                        >
                          <path
                            d="M30 0H0V30"
                            fill="none"
                            stroke="#443033"
                            strokeWidth="1"
                          />
                        </pattern>
                        <linearGradient id="wall" x2="0" y2="1">
                          <stop stopColor="#302325" />
                          <stop offset="1" stopColor="#1a1415" />
                        </linearGradient>
                        <radialGradient id="glow">
                          <stop stopColor="#e85050" stopOpacity=".3" />
                          <stop
                            offset="1"
                            stopColor="#e85050"
                            stopOpacity="0"
                          />
                        </radialGradient>
                      </defs>
                      <path
                        d="m80 165 230-110 230 110-230 112Z"
                        fill="#191516"
                        stroke="#70565a"
                      />
                      <path
                        d="m80 165 230-110 230 110-230 112Z"
                        fill="url(#floorGrid)"
                      />
                      <path
                        d="M80 165V65L310 5v50Z"
                        fill="url(#wall)"
                        opacity=".65"
                        stroke="#594247"
                      />
                      <path
                        d="M310 55V5l230 60v100Z"
                        fill="#21191b"
                        opacity=".8"
                        stroke="#594247"
                      />
                      <path
                        d="M310 5v50M80 65l230 107 230-107"
                        fill="none"
                        stroke="#70565a"
                        strokeDasharray="4 6"
                        opacity=".5"
                      />
                      <ellipse
                        cx="310"
                        cy="190"
                        rx="110"
                        ry="55"
                        fill="url(#glow)"
                      />
                      <g>
                        <path d="m270 163 45-22 45 22-45 22Z" fill="#c95058" />
                        <path d="m270 163 45 22v35l-45-22Z" fill="#742b33" />
                        <path d="m315 185 45-22v35l-45 22Z" fill="#9a3842" />
                        <path
                          d="m292 153 45 22v35"
                          fill="none"
                          stroke="#f69a9f"
                        />
                        <path
                          d="M315 139v-30"
                          stroke="#ff7c86"
                          strokeDasharray="3 4"
                        />
                        <circle cx="315" cy="106" r="4" fill="#ff7c86" />
                        <text
                          x="315"
                          y="92"
                          textAnchor="middle"
                          fill="#ffd1d5"
                          fontSize="13"
                        >
                          FUEL SOURCE
                        </text>
                      </g>
                      <g
                        opacity={
                          values.machinery === "None identified" ? 0.18 : 1
                        }
                      >
                        <path d="m415 120 38-18 25 12-38 19Z" fill="#747474" />
                        <path d="m415 120 25 13v50l-25-13Z" fill="#383838" />
                        <path d="m440 133 38-19v50l-38 19Z" fill="#515151" />
                        <path
                          d="m447 140 23-11m-23 20 23-11m-23 20 23-11"
                          stroke="#ababab"
                        />
                        <circle cx="449" cy="169" r="2" fill="#ff6b77" />
                      </g>
                      <g
                        transform={`rotate(${Number(values.direction || 0) - 90} 190 195)`}
                        fill="none"
                        stroke="#ffaaaa"
                        strokeWidth="2"
                      >
                        <path d="M130 175h80m-12-6 12 6-12 6M120 194h100m-12-6 12 6-12 6M135 213h75m-12-6 12 6-12 6" />
                      </g>
                      <text x="120" y="253" fill="#c8bbbb" fontSize="13">
                        AIRFLOW · {values.flow || 0} m/s
                      </text>
                      <path d="M465 195v31h44" fill="none" stroke="#a38b90" />
                      <text x="462" y="245" fill="#c8bbbb" fontSize="12">
                        EQUIPMENT ZONE
                      </text>
                      <path
                        d="m310 277 0 22m-10-5 10 5 10-5"
                        stroke="#a38b90"
                        fill="none"
                      />
                      <text
                        x="310"
                        y="320"
                        fill="#b29da1"
                        textAnchor="middle"
                        fontSize="12"
                      >
                        ILLUSTRATIVE · NOT TO SCALE
                      </text>
                    </svg>
                  </div>
                  <div className="card-footer">
                    <span>Airflow · {values.flow || 0} m/s</span>
                    <span>Gravity · {values.gravity || 0} g</span>
                  </div>
                  <p className="model-note">
                    Physics solver not connected. Arrows show input direction.
                  </p>
                </section>
              )}
            </div>
            <div className="scenario-strip" role="status">
              <span className={`status-dot ${snapshot ? "ready" : ""}`} />
              {snapshot
                ? "Parameters applied locally · Ready for a model connection"
                : "Edit parameters to set up your scenario"}
            </div>
            <section
              className="conversation-log"
              aria-label="Scenario conversation"
              aria-live="polite"
            >
              {messages.length === 0 ? (
                <div className="conversation-intro">
                  <span className="assistant-mark">e.</span>
                  <div>
                    <h2>A space for your scenario</h2>
                    <p>
                      Add a question or describe what you want to explore. Your
                      note and parameters will be kept together here.
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
                          Scenario note saved with {message.parameters.oxygen}%
                          oxygen, {message.parameters.pressure} kPa pressure,{" "}
                          {message.parameters.flow} m/s airflow and{" "}
                          {message.parameters.gravity} g gravity.
                        </p>
                        <p className="muted">
                          No model is connected, so I can’t generate a
                          simulation or assess this scenario yet.
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
                  placeholder="Describe a scenario or ask about your environment…"
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
                Local preview · No AI response or validated simulation is
                generated.
              </p>
            </div>
          </main>
          <aside
            className="parameter-panel"
            id="parameters"
            aria-labelledby="parameters-heading"
          >
            <div className="parameters-heading">
              <div>
                <h2 id="parameters-heading">Parameters</h2>
                <p>Define your environment</p>
              </div>
              <Symbol name="sliders" />
            </div>
            <form id="scenario-form" onSubmit={preview}>
              <div className="field-section">
                <span className="field-section-title">
                  Atmospheric conditions
                </span>
                <div className="fields-grid">
                  {fields
                    .slice(0, 4)
                    .map(([key, label, suffix, min, max, step]) => (
                      <label className="field" key={key}>
                        <span>{label}</span>
                        <div className="input-wrap">
                          <input
                            type="number"
                            required
                            min={min}
                            max={max}
                            step={step}
                            value={values[key]}
                            onChange={(e) => update(key, e.target.value)}
                          />
                          <span>{suffix}</span>
                        </div>
                      </label>
                    ))}
                  <div className="field">
                    <span>
                      <label htmlFor="temperature">Temperature</label>
                      <button
                        className="unit-toggle"
                        type="button"
                        onClick={() => setUnit(unit === "C" ? "K" : "C")}
                        aria-label={`Switch temperature to ${unit === "C" ? "Kelvin" : "Celsius"}`}
                      >
                        °C / K
                      </button>
                    </span>
                    <div className="input-wrap">
                      <input
                        id="temperature"
                        type="number"
                        required
                        min={unit === "C" ? -273.15 : 0}
                        max={unit === "C" ? 2000 : 2273.15}
                        step="any"
                        value={temperature}
                        onChange={(e) =>
                          update(
                            "temperature",
                            e.target.value === ""
                              ? ""
                              : Number(e.target.value) -
                                  (unit === "K" ? 273.15 : 0),
                          )
                        }
                      />
                      <span>{unit === "C" ? "°C" : "K"}</span>
                    </div>
                  </div>
                  {fields
                    .slice(4, 5)
                    .map(([key, label, suffix, min, max, step]) => (
                      <label className="field" key={key}>
                        <span>{label}</span>
                        <div className="input-wrap">
                          <input
                            type="number"
                            required
                            min={min}
                            max={max}
                            step={step}
                            value={values[key]}
                            onChange={(e) => update(key, e.target.value)}
                          />
                          <span>{suffix}</span>
                        </div>
                      </label>
                    ))}
                  {fields
                    .slice(6)
                    .map(([key, label, suffix, min, max, step]) => (
                      <label className="field" key={key}>
                        <span>{label}</span>
                        <div className="input-wrap">
                          <input
                            type="number"
                            required
                            min={min}
                            max={max}
                            step={step}
                            value={values[key]}
                            onChange={(e) => update(key, e.target.value)}
                          />
                          <span>{suffix}</span>
                        </div>
                      </label>
                    ))}
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
                  <label className="field">
                    <span>Fuel surface area</span>
                    <div className="input-wrap">
                      <input
                        type="number"
                        required
                        min="0"
                        max="100000"
                        step="any"
                        value={values.area}
                        onChange={(e) => update("area", e.target.value)}
                      />
                      <span>cm²</span>
                    </div>
                  </label>
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
              <p className="form-footnote">
                Inputs stay in this page. No server request is made.
              </p>
            </form>
          </aside>
        </div>
      </div>
    </div>
  );
}
