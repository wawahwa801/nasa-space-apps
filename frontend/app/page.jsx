"use client";

import { useState } from "react";
import Link from "next/link";
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

export default function Home() {
  const [values, setValues] = useState(defaults);
  const [unit, setUnit] = useState("C");
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState("");
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
  function preview(event) {
    event.preventDefault();
    if (Number(values.oxygen) + Number(values.co2) > 100) {
      setError("Oxygen and CO₂ concentrations must total 100% or less.");
      return;
    }
    setSnapshot({ ...values });
  }
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" href="/" aria-label="Ember home">
          ember<span>.</span>
        </Link>
        <span className="connection">Local preview</span>
      </header>
      <main className="main-content" id="overview">
        <section className="page-heading">
          <h1>Fire safety</h1>
          <p>Set the conditions for your environment.</p>
        </section>
        <div className="workspace-grid">
          <section
            className="parameter-panel"
            id="parameters"
            aria-labelledby="parameters-heading"
          >
            <h2 id="parameters-heading">Parameters</h2>
            <form onSubmit={preview}>
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
                <LiquidButton className="primary-button" type="submit">
                  Update scenario <span aria-hidden="true">→</span>
                </LiquidButton>
                <button
                  className="reset-button"
                  type="button"
                  onClick={() => {
                    setValues(defaults);
                    setUnit("C");
                    setSnapshot(null);
                    setError("");
                  }}
                  aria-label="Reset parameters"
                >
                  Reset
                </button>
              </div>
              <p className="form-footnote">
                Inputs stay in this browser session. No server request is made.
              </p>
            </form>
          </section>
          <div className="visual-column">
            <section className="scene-panel" aria-labelledby="preview-heading">
              <div className="panel-heading">
                <h2 id="preview-heading">Environment</h2>
                <span>Illustrative preview</span>
              </div>
              <div className="scene">
                <div className="scene-top">
                  <span>{values.location || "Location not specified"}</span>
                </div>
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
                      <stop offset="1" stopColor="#e85050" stopOpacity="0" />
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
                    <path d="m292 153 45 22v35" fill="none" stroke="#f69a9f" />
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
                    opacity={values.machinery === "None identified" ? 0.18 : 1}
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
                <div className="scene-legend">
                  <span>
                    <i className="legend-fuel" />
                    Fuel source
                  </span>
                  <span>
                    <i className="legend-flow" />
                    Airflow
                  </span>
                  <span>
                    <i className="legend-equipment" />
                    Machinery
                  </span>
                </div>
              </div>
            </section>
            <section
              className="insights-panel"
              id="insights"
              aria-labelledby="assessment-heading"
            >
              <h2 id="assessment-heading">Assessment</h2>
              <p>
                Model not connected. Predictions will appear here when
                available.
              </p>
              <p className="scenario-status" role="status">
                {snapshot
                  ? "Scenario updated locally. Ready for a future model connection."
                  : "Adjust parameters, then update your scenario."}
              </p>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
