// Input parameters and assessment thresholds for the fire safety dashboard.
//
// Only parameters that feed an assessment rule or a comparison with the NASA
// data are included. Before adding one, make sure the dashboard has data or a
// rule that uses it.
//
// Field types:
//   number - numeric input. Either a fixed `unit`, or `units` naming one of
//            UNIT_SYSTEMS so the user can pick the unit.
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

  // Units a user can enter values in. The first unit of each system is the
  // base unit: values are stored and assessed in it.
  window.UNIT_SYSTEMS = {
    pressure: [
      { unit: "kPa", toBase: (x) => x, fromBase: (x) => x },
      { unit: "psia", toBase: (x) => x * 6.894757, fromBase: (x) => x / 6.894757 },
      { unit: "atm", toBase: (x) => x * 101.325, fromBase: (x) => x / 101.325 },
    ],
    temperature: [
      { unit: "°C", toBase: (x) => x, fromBase: (x) => x },
      { unit: "K", toBase: (x) => x - 273.15, fromBase: (x) => x + 273.15 },
      { unit: "°F", toBase: (x) => ((x - 32) * 5) / 9, fromBase: (x) => (x * 9) / 5 + 32 },
    ],
    concentration: [
      { unit: "ppm", toBase: (x) => x, fromBase: (x) => x },
      { unit: "%", toBase: (x) => x * 10000, fromBase: (x) => x / 10000 },
    ],
    // Major gases, stored in % (1% = 10,000 ppm).
    percent: [
      { unit: "%", toBase: (x) => x, fromBase: (x) => x },
      { unit: "ppm", toBase: (x) => x / 10000, fromBase: (x) => x * 10000 },
    ],
    length: [
      { unit: "m", toBase: (x) => x, fromBase: (x) => x },
      { unit: "cm", toBase: (x) => x / 100, fromBase: (x) => x * 100 },
      { unit: "ft", toBase: (x) => x * 0.3048, fromBase: (x) => x / 0.3048 },
    ],
  };

  // `min`/`max` are in the base unit. `hint` says what the input is used for.
  window.PARAMETER_SECTIONS = [
    {
      id: "environment",
      title: "Environment",
      fields: [
        { id: "environment", label: "Environmental condition", type: "choice", options: ["Pressurised", "Partially pressurised", "Vacuum"],
          hint: "Checked against the pressure reading." },
        { id: "gravity", label: "Gravity condition", type: "choice", options: ["Microgravity (~0 g)", "Lunar (0.17 g)", "Martian (0.38 g)", "Earth (1 g)"],
          hint: "Microgravity changes how a flame gets oxygen. All loaded NASA tests are in microgravity." },
        { id: "internal_temp_c", label: "Internal temperature", type: "number", units: "temperature", min: -273.15, max: 2000,
          hint: "Shown against plume temperatures from the Saffire-I burn." },
        { id: "pressure_kpa", label: "Internal pressure", type: "number", units: "pressure", min: 0, max: 1000,
          hint: "Used with O₂ for partial pressure and to find similar ACME tests." },
      ],
    },
    {
      id: "atmosphere",
      title: "Atmospheric composition",
      fields: [
        { id: "o2_pct", label: "Oxygen (O₂) concentration", type: "number", units: "percent", min: 0, max: 100,
          hint: "Checked for enrichment and deficiency, and placed on the ACME chart." },
        { id: "n2_pct", label: "Nitrogen (N₂) concentration", type: "number", units: "percent", min: 0, max: 100,
          hint: "Checked with O₂ so the gas percentages add up." },
        { id: "co2_ppm", label: "Carbon dioxide (CO₂) concentration", type: "number", units: "concentration", min: 0, max: 1e6,
          hint: "Compared with NIOSH exposure limits and the Saffire-I burn." },
        { id: "h2_ppm", label: "Hydrogen (H₂) concentration", type: "number", units: "concentration", min: 0, max: 1e6,
          hint: "Compared with hydrogen's lower flammability limit (4%)." },
        { id: "ch4_ppm", label: "Methane (CH₄) concentration", type: "number", units: "concentration", min: 0, max: 1e6,
          hint: "Compared with methane's lower flammability limit (5%)." },
        { id: "co_ppm", label: "Carbon monoxide (CO) concentration", type: "number", units: "concentration", min: 0, max: 1e6,
          hint: "Compared with NIOSH limits. Rising CO can signal smouldering." },
        { id: "monitoring", label: "Atmospheric monitoring status", type: "choice", options: ["Nominal", "Degraded", "Offline", "Unknown"],
          hint: "Degraded or offline monitoring makes the gas readings less reliable." },
        { id: "oxidizer_leak", label: "Oxygen / oxidizer leakage status", type: "choice", options: LEAK,
          hint: "A leak can enrich O₂ locally, above the measured level." },
      ],
    },
    {
      id: "fuels",
      title: "Nearby fuels (gases)",
      fields: [
        { id: "fuel_type", label: "Fuel type", type: "choice", options: fuels,
          hint: "Filters the ACME chart and finds SPICE flame runs for this fuel." },
        { id: "fuel_storage", label: "Fuel storage condition", type: "choice", options: ["Sealed cylinder", "Plumbed line (in use)", "Open / vented"],
          hint: "Open or vented fuel is flagged." },
        { id: "fuel_leak", label: "Fuel leakage status", type: "choice", options: LEAK,
          hint: "Suspected or confirmed leaks are flagged, more severely with an oxidizer leak." },
        { id: "fuel_distance_m", label: "Fuel distance from ignition sources", type: "number", units: "length", min: 0, max: 1000,
          hint: "Flagged when closer than the minimum separation in parameters.js." },
      ],
    },
    {
      id: "materials",
      title: "Combustible materials (solids)",
      fields: [
        { id: "material_type", label: "Material type", type: "choice", options: materials,
          hint: "Finds SAME-R smoke tests for this material." },
        { id: "material_distance_m", label: "Material distance from ignition sources", type: "number", units: "length", min: 0, max: 1000,
          hint: "Flagged when closer than the minimum separation in parameters.js." },
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
