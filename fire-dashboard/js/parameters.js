// Input parameters and assessment thresholds for the fire safety dashboard.
//
// Only parameters that feed an assessment rule or a comparison with the NASA
// data are included. Before adding one, make sure the dashboard has data or a
// rule that uses it.
//
// Field types:
//   number - numeric input; `unit` is shown beside it
//   choice - pick one of `options`

(function () {
  const REF = window.REFERENCE_DATA;

  // Fuel and material lists come from the data sets, so every option has
  // matching NASA test data. "Butane / Nitrogen (30/70)" -> "Butane",
  // "75 % Propylene" -> "Propylene".
  const unique = (xs) => [...new Set(xs)].sort((a, b) => a.localeCompare(b));
  const baseFuel = (name) => name.replace(/^\d+\s*%\s*/, "").split("/")[0].trim();
  const fuels = unique([
    ...REF.acme.tests.map((t) => baseFuel(t.fuel)),
    ...REF.spice.runs.map((r) => baseFuel(r.fuel)),
  ].filter((f) => f && f !== "Unspecified"));
  const materials = unique(REF.samer.tests.map((t) => t.material));

  const LEAK = ["None detected", "Suspected", "Confirmed", "Unknown"];

  window.PARAMETER_SECTIONS = [
    {
      id: "environment",
      title: "Environment",
      fields: [
        { id: "environment", label: "Environmental condition", type: "choice", options: ["Pressurised", "Partially pressurised", "Vacuum"] },
        { id: "gravity", label: "Gravity condition", type: "choice", options: ["Microgravity (~0 g)", "Lunar (0.17 g)", "Martian (0.38 g)", "Earth (1 g)"] },
        { id: "internal_temp_c", label: "Internal temperature", type: "number", unit: "°C", step: "0.1" },
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
        { id: "monitoring", label: "Atmospheric monitoring status", type: "choice", options: ["Nominal", "Degraded", "Offline", "Unknown"] },
        { id: "oxidizer_leak", label: "Oxygen / oxidizer leakage status", type: "choice", options: LEAK },
      ],
    },
    {
      id: "fuels",
      title: "Nearby fuels (gases)",
      fields: [
        { id: "fuel_type", label: "Fuel type", type: "choice", options: fuels },
        { id: "fuel_storage", label: "Fuel storage condition", type: "choice", options: ["Sealed cylinder", "Plumbed line (in use)", "Open / vented"] },
        { id: "fuel_leak", label: "Fuel leakage status", type: "choice", options: LEAK },
        { id: "fuel_distance_m", label: "Fuel distance from ignition sources", type: "number", unit: "m", min: 0, step: "0.01" },
      ],
    },
    {
      id: "materials",
      title: "Combustible materials (solids)",
      fields: [
        { id: "material_type", label: "Material type", type: "choice", options: materials },
        { id: "material_distance_m", label: "Material distance from ignition sources", type: "number", unit: "m", min: 0, step: "0.01" },
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
    environment: "Pressurised", gravity: "Microgravity (~0 g)", internal_temp_c: 22.5, pressure_kpa: 101.3,
    o2_pct: 21.5, n2_pct: 78.0, co2_ppm: 3000, h2_ppm: 20, ch4_ppm: 5, co_ppm: 2,
    monitoring: "Nominal", oxidizer_leak: "None detected",
    fuel_type: "Propane", fuel_storage: "Sealed cylinder", fuel_leak: "None detected", fuel_distance_m: 2.0,
    material_type: "Kapton", material_distance_m: 0.4,
  };
})();
