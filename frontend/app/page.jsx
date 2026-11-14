"use client";

import { useState } from "react";
import Link from "next/link";

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

function Icon({ name = "grid", size = 20, ...props }) {
  const paths = {
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </>
    ),
    flame: (
      <path d="M13 3c1 6-5 6-3 11 2-1 3-3 3-4 5 4 7 11-1 11C3 21 3 12 7 8c0 4 2 4 2 4-1-4 3-6 4-9Z" />
    ),
    arrow: (
      <>
        <path d="M5 12h14M13 6l6 6-6 6" />
      </>
    ),
    wind: (
      <>
        <path d="M3 8h12c5 0 5-6 1-5M3 12h16c4 0 4 6 0 6M3 16h8" />
      </>
    ),
    pin: (
      <>
        <path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z" />
        <circle cx="12" cy="10" r="2" />
      </>
    ),
    layers: (
      <>
        <path d="m12 3 10 5-10 5L2 8l10-5Zm-10 9 10 5 10-5M2 16l10 5 10-5" />
      </>
    ),
    shield: (
      <>
        <path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z" />
        <path d="m8 12 3 3 5-6" />
      </>
    ),
    reset: (
      <>
        <path d="M4 10a8 8 0 1 1 1 8M4 4v6h6" />
      </>
    ),
    chart: (
      <>
        <path d="M4 3v17h17M8 15l4-5 4 3 5-7" />
      </>
    ),
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {paths[name] || paths.grid}
    </svg>
  );
}

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
      <aside className="sidebar">
        <Link className="brand" href="/" aria-label="Ember home">
          <span className="brand-icon">
            <Icon name="flame" size={24} />
          </span>
          <span>
            ember<span className="brand-dot">.</span>
          </span>
        </Link>
        <p className="nav-caption">WORKSPACE</p>
        <nav aria-label="Workspace">
          <a className="nav-item active" href="#overview">
            <Icon />
            Overview
          </a>
          <a className="nav-item" href="#parameters">
            <Icon name="layers" />
            Parameters
          </a>
          <a className="nav-item" href="#insights">
            <Icon name="chart" />
            Insights
          </a>
        </nav>
        <div className="sidebar-bottom">
          <div className="demo-symbol">
            <Icon name="shield" />
          </div>
          <strong>A clearer view of fire safety.</strong>
          <p>Explore environmental conditions before connecting a model.</p>
          <span className="small-pill">UI PREVIEW</span>
        </div>
        <div className="profile">
          <span className="avatar">JW</span>
          <div>
            Research workspace<small>Local environment</small>
          </div>
        </div>
      </aside>

      <main id="overview">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span> <b>Environmental safety</b>
          </div>
          <span className="connection">
            <i />
            Local preview
          </span>
        </header>
        <div className="main-content">
          <section className="page-heading">
            <div>
              <p className="eyebrow">ENVIRONMENTAL INTELLIGENCE</p>
              <h1>Fire safety dashboard</h1>
              <p className="subtitle">
                Understand the conditions. Explore the potential.
              </p>
            </div>
            <div className="heading-tag">
              <Icon name="shield" size={16} /> Environmental assessment
            </div>
          </section>

          <div className="preview-notice">
            <span className="notice-dot" />
            <span>
              <strong>Preview workspace</strong> · Visualize your inputs. Risk
              scores and predictions will appear when a model is connected.
            </span>
            <span className="notice-label">NO MODEL CONNECTED</span>
          </div>

          <section
            className="metrics"
            aria-label="Current environmental inputs"
          >
            {[
              [
                "O₂",
                "Oxygen concentration",
                values.oxygen,
                "%",
                "Atmospheric composition",
                "mint",
              ],
              [
                "↗",
                "Ambient pressure",
                values.pressure,
                "kPa",
                "Environmental pressure",
                "blue",
              ],
              [
                "≈",
                "Airflow velocity",
                values.flow,
                "m/s",
                `${values.direction || 0}° flow direction`,
                "purple",
              ],
              [
                "g",
                "Gravitational field",
                values.gravity,
                "g",
                "Relative to Earth gravity",
                "amber",
              ],
            ].map(([symbol, title, value, suffix, note, color]) => (
              <article className="metric" key={title}>
                <div className="metric-top">
                  <span>{title}</span>
                  <span className={`metric-icon ${color}`}>{symbol}</span>
                </div>
                <p className="metric-value">
                  {value === "" ? "—" : value}
                  <span>{suffix}</span>
                </p>
                <p className="metric-note">{note}</p>
              </article>
            ))}
          </section>

          <div className="workspace-grid">
            <section className="panel parameter-panel" id="parameters">
              <div className="panel-heading">
                <div>
                  <h2>Environment parameters</h2>
                  <p>Define the conditions for your scenario.</p>
                </div>
                <span className="section-number">01</span>
              </div>
              <form onSubmit={preview}>
                <div className="field-section">
                  <span className="field-section-title">
                    <Icon name="wind" size={16} /> Atmospheric conditions
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
                  <span className="field-section-title">
                    <Icon name="layers" size={16} /> Fuel & surroundings
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
                  <button className="primary-button" type="submit">
                    Update scenario <Icon name="arrow" size={17} />
                  </button>
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
                    <Icon name="reset" size={18} />
                  </button>
                </div>
                <p className="form-footnote">
                  Inputs stay in this browser session. No server request is
                  made.
                </p>
              </form>
            </section>

            <div className="visual-column">
              <section className="panel scene-panel">
                <div className="panel-heading">
                  <div>
                    <h2>Environment overview</h2>
                    <p>A spatial view of your scenario.</p>
                  </div>
                  <span className="small-pill">SCHEMATIC</span>
                </div>
                <div className="scene">
                  <div className="scene-top">
                    <span>
                      <i />
                      {values.location || "Location not specified"}
                    </span>
                    <span>ISOMETRIC VIEW</span>
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
                          stroke="#33413e"
                          strokeWidth="1"
                        />
                      </pattern>
                      <linearGradient id="wall" x2="0" y2="1">
                        <stop stopColor="#24342f" />
                        <stop offset="1" stopColor="#15211f" />
                      </linearGradient>
                      <radialGradient id="glow">
                        <stop stopColor="#eba95a" stopOpacity=".3" />
                        <stop offset="1" stopColor="#eba95a" stopOpacity="0" />
                      </radialGradient>
                    </defs>
                    <path
                      d="m80 165 230-110 230 110-230 112Z"
                      fill="#182621"
                      stroke="#52665c"
                    />
                    <path
                      d="m80 165 230-110 230 110-230 112Z"
                      fill="url(#floorGrid)"
                    />
                    <path
                      d="M80 165V65L310 5v50Z"
                      fill="url(#wall)"
                      opacity=".65"
                      stroke="#3c5045"
                    />
                    <path
                      d="M310 55V5l230 60v100Z"
                      fill="#1c2b26"
                      opacity=".8"
                      stroke="#3c5045"
                    />
                    <path
                      d="M310 5v50M80 65l230 107 230-107"
                      fill="none"
                      stroke="#516359"
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
                      <path d="m270 163 45-22 45 22-45 22Z" fill="#bd975d" />
                      <path d="m270 163 45 22v35l-45-22Z" fill="#785d39" />
                      <path d="m315 185 45-22v35l-45 22Z" fill="#9a7847" />
                      <path
                        d="m292 153 45 22v35"
                        fill="none"
                        stroke="#d2b37d"
                      />
                      <path
                        d="M315 139v-30"
                        stroke="#e8bd77"
                        strokeDasharray="3 4"
                      />
                      <circle cx="315" cy="106" r="4" fill="#e8bd77" />
                      <text
                        x="315"
                        y="92"
                        textAnchor="middle"
                        fill="#e4d1ac"
                        fontSize="11"
                      >
                        FUEL SOURCE
                      </text>
                    </g>
                    <g
                      opacity={
                        values.machinery === "None identified" ? 0.18 : 1
                      }
                    >
                      <path d="m415 120 38-18 25 12-38 19Z" fill="#59716b" />
                      <path d="m415 120 25 13v50l-25-13Z" fill="#344942" />
                      <path d="m440 133 38-19v50l-38 19Z" fill="#425b51" />
                      <path
                        d="m447 140 23-11m-23 20 23-11m-23 20 23-11"
                        stroke="#7f9c8c"
                      />
                      <circle cx="449" cy="169" r="2" fill="#b5e8b8" />
                    </g>
                    <g
                      transform={`rotate(${Number(values.direction || 0) - 90} 190 195)`}
                      fill="none"
                      stroke="#a4ccaf"
                      strokeWidth="2"
                    >
                      <path d="M130 175h80m-12-6 12 6-12 6M120 194h100m-12-6 12 6-12 6M135 213h75m-12-6 12 6-12 6" />
                    </g>
                    <text x="120" y="253" fill="#a5b8ab" fontSize="11">
                      AIRFLOW · {values.flow || 0} m/s
                    </text>
                    <path d="M465 195v31h44" fill="none" stroke="#718a79" />
                    <text x="462" y="245" fill="#a5b8ab" fontSize="10">
                      EQUIPMENT ZONE
                    </text>
                    <path
                      d="m310 277 0 22m-10-5 10 5 10-5"
                      stroke="#718a79"
                      fill="none"
                    />
                    <text
                      x="310"
                      y="320"
                      fill="#789084"
                      textAnchor="middle"
                      fontSize="10"
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
                <div className="scene-stats">
                  <div>
                    <span>Selected material</span>
                    <strong>{values.fuel}</strong>
                  </div>
                  <div>
                    <span>Exposed surface</span>
                    <strong>
                      {values.area === "" ? "—" : values.area}{" "}
                      <small>cm²</small>
                    </strong>
                  </div>
                  <div>
                    <span>Temperature</span>
                    <strong>
                      {temperature === "" ? "—" : temperature}{" "}
                      <small>{unit === "C" ? "°C" : "K"}</small>
                    </strong>
                  </div>
                </div>
              </section>

              <section className="panel insights-panel" id="insights">
                <div className="panel-heading">
                  <div>
                    <h2>Safety insights</h2>
                    <p>Context for the conditions you define.</p>
                  </div>
                  <span className="status-tag">MODEL PENDING</span>
                </div>
                <div className="insight-body">
                  <div className="risk-placeholder">
                    <div className="risk-gauge">
                      <span>—</span>
                    </div>
                    <div>
                      <span className="eyebrow">OVERALL RISK</span>
                      <h3>Awaiting assessment</h3>
                      <p>No risk score calculated</p>
                    </div>
                  </div>
                  <div className="context-item">
                    <span className="context-icon amber">
                      <Icon name="layers" size={17} />
                    </span>
                    <div>
                      <h3>Fuel & equipment context</h3>
                      <p>
                        {values.fuel} · {values.machinery}. Review material
                        properties and equipment details with your assessment.
                      </p>
                    </div>
                  </div>
                  <div className="context-item">
                    <span className="context-icon mint">
                      <Icon name="wind" size={17} />
                    </span>
                    <div>
                      <h3>Atmospheric inputs</h3>
                      <p>
                        Oxygen, pressure, flow and gravity are captured as model
                        inputs. Their combined effect is not evaluated in this
                        preview.
                      </p>
                    </div>
                  </div>
                  <div className="model-output">
                    <span>
                      Ignition likelihood <b>—</b>
                    </span>
                    <span>
                      Flame spread <b>—</b>
                    </span>
                    <span>
                      Potential threats <b>—</b>
                    </span>
                  </div>
                  <p className="scenario-status" role="status">
                    {snapshot
                      ? "Scenario updated locally. Ready for a future model connection."
                      : "Adjust parameters, then update your scenario."}
                  </p>
                </div>
              </section>
            </div>
          </div>
          <footer className="footer">
            <span>
              <span className="footer-dot" /> Environmental Fire Safety
              Dashboard
            </span>
            <span>Concept workspace · Results require a validated model</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
