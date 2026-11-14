// Input parameters and assessment thresholds for the fire safety dashboard.
//
// To add a built-in parameter, add an entry to a section's `fields` list.
// Field types:
//   number   - numeric input; `unit` is shown beside it
//   choice   - pick one of `options` (a fixed list)
//   suggest  - free text with suggested `options` (users may type their own)
//   text     - free text
//   quantity - number plus a unit picked from `units`
// Users can also add their own parameters from the page; those are stored in
// the browser and do not need code changes.

window.PARAMETER_SECTIONS = [
  {
    id: "location",
    title: "Location & environment",
    fields: [
      {
        id: "location_type", label: "Location type", type: "suggest",
        options: ["Spacecraft cabin", "Space station module", "Planetary habitat", "Airlock", "Ground test chamber", "Launch facility"],
      },
      { id: "area", label: "Area / compartment", type: "suggest", options: ["Galley", "Crew quarters", "Experiment rack", "Stowage", "Hygiene area", "Avionics bay"] },
      { id: "environment", label: "Environmental condition", type: "choice", options: ["Pressurised", "Partially pressurised", "Vacuum"] },
      {
        id: "gravity", label: "Gravity condition", type: "choice",
        options: ["Microgravity (~0 g)", "Lunar (0.17 g)", "Martian (0.38 g)", "Earth (1 g)"],
      },
      { id: "internal_temp_c", label: "Internal temperature", type: "number", unit: "°C", step: "0.1" },
      { id: "external_temp_c", label: "External temperature", type: "number", unit: "°C", step: "0.1" },
      { id: "pressure_kpa", label: "Internal pressure", type: "number", unit: "kPa", min: 0, step: "0.1" },
    ],
  },
  {
    id: "atmosphere",
    title: "Atmospheric composition",
    fields: [
      { id: "o2_pct", label: "Oxygen (O₂) concentration", type: "number", unit: "%", min: 0, max: 100, step: "0.1" },
      { id: "n2_pct", label: "Nitrogen (N₂) concentration", type: "number", unit: "%", min: 0, max: 100, step: "0.1" },
      { id: "co2_ppm", label: "Carbon dioxide (CO₂) concentration", type: "number", unit: "ppm", min: 0 },
      { id: "h2_ppm", label: "Hydrogen (H₂) concentration", type: "number", unit: "ppm", min: 0 },
      { id: "ch4_ppm", label: "Methane (CH₄) concentration", type: "number", unit: "ppm", min: 0 },
      { id: "co_ppm", label: "Carbon monoxide (CO) concentration", type: "number", unit: "ppm", min: 0 },
      { id: "other_gas_types", label: "Other gas types", type: "text", placeholder: "e.g. Ammonia, Formaldehyde" },
      { id: "other_gas_conc", label: "Other gas concentrations", type: "text", placeholder: "e.g. 2 ppm, 0.1 ppm (same order)" },
      { id: "monitoring", label: "Atmospheric monitoring status", type: "choice", options: ["Nominal", "Degraded", "Offline", "Unknown"] },
    ],
  },
  {
    id: "fuels",
    title: "Nearby fuels & combustible materials",
    fields: [
      {
        id: "fuel_type", label: "Fuel / material type", type: "suggest",
        options: ["Kapton", "Silicone", "Teflon", "Pyrell foam", "Lampwick (cotton)", "Cotton-fiberglass fabric",
          "Ethane", "Propane", "Butane", "Methane", "Ethylene", "Propylene", "Hydrogen"],
      },
      { id: "physical_state", label: "Physical state", type: "choice", options: ["Solid", "Liquid", "Gas"] },
      { id: "fuel_quantity", label: "Fuel quantity", type: "quantity", units: ["g", "kg", "L", "mL", "m²", "cm²", "items"] },
      { id: "storage", label: "Fuel storage condition", type: "suggest", options: ["Sealed container", "Stowage bag", "Open / exposed", "Pressurised tank", "In use"] },
      { id: "ignition_distance_m", label: "Distance from ignition sources", type: "number", unit: "m", min: 0, step: "0.01" },
      { id: "fuel_leak", label: "Fuel leakage status", type: "choice", options: ["None detected", "Suspected", "Confirmed", "Unknown"] },
      { id: "oxidizer_type", label: "Oxidizer type", type: "suggest", options: ["Oxygen (O₂)", "Air", "Nitrous oxide (N₂O)", "Hydrogen peroxide"] },
      { id: "oxidizer_leak", label: "Oxidizer leakage status", type: "choice", options: ["None detected", "Suspected", "Confirmed", "Unknown"] },
    ],
  },
  {
    id: "notes",
    title: "Observations",
    fields: [
      { id: "notes", label: "Notes", type: "textarea", placeholder: "Anything else: smells, smoke, alarms, recent maintenance…" },
    ],
  },
];

// Thresholds used by the assessment. These are reference values for a
// prototype, not certified spacecraft limits: replace them with the limits
// that apply to your vehicle or facility.
window.THRESHOLDS = {
  // OSHA 29 CFR 1910.146 definitions (oxygen-enriched / oxygen-deficient).
  o2_enriched_pct: 23.5,
  o2_deficient_pct: 19.5,
  // Oxygen partial pressure of sea-level air (20.95 % of 101.325 kPa), for comparison.
  sea_level_ppo2_kpa: 21.2,
  // Lower flammability limits in air, % by volume.
  lfl_pct: { h2: 4.0, ch4: 5.0 },
  // Alarm points as a share of the LFL (typical gas-detector settings).
  lfl_warning_share: 0.10,
  lfl_critical_share: 0.25,
  // NIOSH recommended exposure limits.
  co_ppm: { warning: 35, serious: 200 },     // TWA, ceiling
  co2_ppm: { warning: 5000, serious: 30000 }, // TWA, STEL
  // Placeholder: set to your own minimum separation from ignition sources.
  min_ignition_distance_m: 1.0,
  // Number of nearest ACME test points to compare against.
  acme_neighbours: 10,
};

// Example input, roughly an ISS-like cabin. Used by the "Load example" button.
window.EXAMPLE_INPUT = {
  location_type: "Space station module", area: "Experiment rack", environment: "Pressurised",
  gravity: "Microgravity (~0 g)", internal_temp_c: 22.5, external_temp_c: -100, pressure_kpa: 101.3,
  o2_pct: 21.5, n2_pct: 78.0, co2_ppm: 3000, h2_ppm: 20, ch4_ppm: 5, co_ppm: 2,
  other_gas_types: "", other_gas_conc: "", monitoring: "Nominal",
  fuel_type: "Kapton", physical_state: "Solid", fuel_quantity: { value: 0.5, unit: "kg" },
  storage: "In use", ignition_distance_m: 0.4, fuel_leak: "None detected",
  oxidizer_type: "Air", oxidizer_leak: "None detected",
  notes: "Wire harness insulation near a powered experiment heater.",
};
