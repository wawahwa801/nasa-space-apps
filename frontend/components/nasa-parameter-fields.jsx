"use client";

// NASA comparison inputs shown inside the Parameters panel, in the panel's own
// style. Field definitions, units and ranges come from
// ../../fire-dashboard/js/parameters.js (loaded by FireSafetyComparison).
// Fields that the flame simulation already has (O₂, pressure, temperature,
// CO₂, gravity) are shared and not repeated here; see SHARED_FIELDS.

export const SHARED_FIELDS = {
  o2_pct: "oxygen",
  pressure_kpa: "pressure",
  internal_temp_c: "temperature",
  co2_ppm: "co2",
  humidity_pct: "humidity",
  gravity: "gravity",
};

// Starting values for the NASA-only gas readings (base units): typical cabin
// air, so the air composition chart has data before anything is entered.
// With the flame panel's defaults (20.9% O₂, 0.04% CO₂, 45% humidity at 22 °C)
// the remainder is ~0.9%, roughly the argon in Earth air.
export const NASA_DEFAULTS = {
  n2_pct: 77,
  h2_ppm: 0.5,
  ch4_ppm: 1.9,
  co_ppm: 0.1,
};

const tidy = (x) => String(Number(x.toPrecision(6)));

export function unitOf(field, units, unitPrefs) {
  if (!field.units) return { unit: field.unit || "", toBase: (x) => x, fromBase: (x) => x };
  const system = units[field.units];
  return system.find((u) => u.unit === unitPrefs[field.id]) || system[0];
}

// Convert the raw text entered in the panel to the dashboard's base units.
export function nasaInputsFromRaw(defs, raw, unitPrefs) {
  const out = {};
  if (!defs) return out;
  for (const section of defs.sections) {
    for (const f of section.fields) {
      if (SHARED_FIELDS[f.id]) continue;
      const x = raw[f.id];
      if (f.type === "number") {
        out[f.id] = x === undefined || x === "" ? null : unitOf(f, defs.units, unitPrefs).toBase(Number(x));
      } else {
        out[f.id] = x || "";
      }
    }
  }
  return out;
}

// Turn base-unit values (e.g. EXAMPLE_INPUT) into raw panel text in the current units.
export function rawFromBase(defs, values, unitPrefs) {
  const out = {};
  for (const section of defs.sections) {
    for (const f of section.fields) {
      if (SHARED_FIELDS[f.id] || values[f.id] === undefined || values[f.id] === null) continue;
      out[f.id] = f.type === "number"
        ? tidy(unitOf(f, defs.units, unitPrefs).fromBase(Number(values[f.id])))
        : String(values[f.id]);
    }
  }
  return out;
}

function rangeError(field, raw, unit) {
  if (raw === undefined || raw === "") return "";
  const n = Number(raw);
  if (!Number.isFinite(n)) return "Enter a number.";
  const base = unit.toBase(n);
  if ((field.min != null && base < field.min - 1e-9) || (field.max != null && base > field.max + 1e-9)) {
    return `Enter ${tidy(unit.fromBase(field.min))}–${tidy(unit.fromBase(field.max))} ${unit.unit}. Ignored until corrected.`;
  }
  return "";
}

export function NasaParameterFields({ defs, raw, unitPrefs, onChange, onUnitChange }) {
  if (!defs) {
    return (
      <div className="field-section">
        <span className="field-section-title">Hazard checks · NASA comparison</span>
        <p className="nasa-fields-note">Loading NASA comparison inputs…</p>
      </div>
    );
  }
  const sections = defs.sections
    .map((s) => ({ ...s, fields: s.fields.filter((f) => !SHARED_FIELDS[f.id]) }))
    .filter((s) => s.fields.length);

  return (
    <div className="nasa-fields">
      <p className="nasa-fields-intro">
        <b>Hazard checks · NASA comparison.</b> O₂, pressure, temperature, CO₂, humidity and gravity above are shared with the NASA comparison.
      </p>
      {sections.map((section) => (
        <div className="field-section" key={section.id}>
          <span className="field-section-title">{section.title}</span>
          <div className="fields-grid">
            {section.fields.map((f) => {
              const id = `nasa-${f.id}`;
              const unit = unitOf(f, defs.units, unitPrefs);
              const error = f.type === "number" ? rangeError(f, raw[f.id], unit) : "";
              return (
                <div className="field nasa-field" key={f.id}>
                  <label htmlFor={id}>{f.label}</label>
                  {f.type === "number" ? (
                    <div className="nasa-unit-row">
                      <input
                        id={id}
                        type="number"
                        inputMode="decimal"
                        step="any"
                        value={raw[f.id] ?? ""}
                        aria-invalid={error ? true : undefined}
                        aria-describedby={`${id}-hint ${id}-error`}
                        onChange={(e) => onChange(f.id, e.target.value)}
                      />
                      {f.units ? (
                        <select
                          aria-label={`${f.label} unit`}
                          value={unit.unit}
                          onChange={(e) => onUnitChange(f.id, unit.unit, e.target.value)}
                        >
                          {defs.units[f.units].map((u) => (
                            <option key={u.unit}>{u.unit}</option>
                          ))}
                        </select>
                      ) : (
                        <span className="nasa-unit">{f.unit}</span>
                      )}
                    </div>
                  ) : (
                    <select
                      id={id}
                      value={raw[f.id] ?? ""}
                      aria-describedby={`${id}-hint`}
                      onChange={(e) => onChange(f.id, e.target.value)}
                    >
                      <option value="">Not specified</option>
                      {f.options.map((o) => (
                        <option key={o}>{o}</option>
                      ))}
                    </select>
                  )}
                  {error && (
                    <small className="nasa-field-error" id={`${id}-error`}>
                      {error}
                    </small>
                  )}
                  {f.hint && (
                    <small className="nasa-hint" id={`${id}-hint`}>
                      {f.hint}
                    </small>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// Convert a raw value when the user switches its unit.
export function convertRaw(defs, id, rawValue, fromUnit, toUnit) {
  if (rawValue === undefined || rawValue === "" || !Number.isFinite(Number(rawValue))) return rawValue;
  const field = defs.sections.flatMap((s) => s.fields).find((f) => f.id === id);
  const system = defs.units[field.units];
  const from = system.find((u) => u.unit === fromUnit) || system[0];
  const to = system.find((u) => u.unit === toUnit) || system[0];
  return tidy(to.fromBase(from.toBase(Number(rawValue))));
}
