// Input parameters and assessment thresholds for the fire safety dashboard.
//
// Only parameters that feed an assessment rule or a comparison with the NASA
// data are included. Before adding one, make sure the dashboard has data or a
// rule that uses it.
//
// Field types:
//   number - numeric input. Either a fixed `unit`, or `units` naming one of
//            UNIT_SYSTEMS so the user can pick the unit.
//   choice - pick one of `options` (`optionHints` explains each option)
//   multi  - tick any number of `options` (stored as an array)

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
  // Solid materials: SAME-R smoke tests plus BASS / BASS-II burn categories.
  const materials = unique([
    ...REF.samer.tests.map((t) => t.material),
    ...REF.bass.tests.map((t) => t.category),
    ...REF.bass.bass1.runs.map((r) => r.category),
  ].filter((m) => m && m !== "Other"));

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
          hint: "Sets how the pressure reading is used. Vacuum ignores it.",
          optionHints: {
            "Pressurised": "Held at about sea-level pressure (~101 kPa, 14.7 psia) with Earth-like air (~21% O₂), as on the ISS.",
            "Partially pressurised": "Held below sea-level pressure on purpose, e.g. ~56.5 kPa (8.2 psia) with ~34% O₂ in exploration habitats " +
              "to shorten spacewalk prep. Less total oxygen, but the higher O₂ share helps materials burn.",
            "Vacuum": "Open to space: pressure is near zero, so the pressure value is ignored. With no oxygen, nothing can burn, " +
              "but materials can still overheat and outgas.",
          } },
        { id: "gravity", label: "Gravity condition", type: "choice", options: ["Microgravity (~0 g)", "Lunar (0.17 g)", "Martian (0.38 g)", "Earth (1 g)"],
          hint: "Microgravity changes how a flame gets oxygen. All loaded NASA tests are in microgravity." },
        { id: "internal_temp_c", label: "Internal temperature", type: "number", units: "temperature", min: -273.15, max: 2000,
          hint: "Shown against plume temperatures from the Saffire-I burn." },
        { id: "pressure_kpa", label: "Internal pressure", type: "number", units: "pressure", min: 0, max: 1000,
          hint: "Used with O₂ for partial pressure and to find similar ACME tests. Ignored in a vacuum." },
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
        { id: "humidity_pct", label: "Relative humidity", type: "number", unit: "%", min: 0, max: 100,
          hint: "With temperature and pressure, gives the water vapour shown in the air composition chart." },
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
        { id: "material_types", label: "Materials present", type: "multi", options: materials,
          hint: "Tick every material nearby. Finds SAME-R smoke tests and BASS / BASS-II burns, and is compared with live readings to suggest what could be burning." },
        { id: "material_distance_m", label: "Closest material's distance from ignition sources", type: "number", units: "length", min: 0, max: 1000,
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
    // Live monitoring: change detection between timed readings.
    // PLACEHOLDERS, not validated detection thresholds: tune them with real
    // sensor data for your cabin volume, ventilation and sensor noise.
    // Rises are per monitoring interval (rates are scaled to interval_min).
    monitoring: {
      interval_min: 5,                // expected time between readings
      stale_after_intervals: 2,       // flag a gap after this many missed intervals
      co_rise_ppm: { warning: 5, serious: 20 },
      co2_rise_ppm: 300,
      o2_drop_pct: 0.2,
      o2_rise_pct: 0.5,               // possible oxidizer leak
      temp_rise_c: { warning: 2, serious: 10 },
      lfl_share_rise: 0.05,           // H₂ / CH₄ rise as a share of the LFL
      max_readings: 500,
    },
  };

  // How each material typically behaves when heated (general fire-science
  // knowledge, NOT from the loaded NASA data), used to suggest which listed
  // material could be burning:
  //   smoulders - can burn slowly without flame (cellulose, foams), giving CO and smoke first
  //   flames    - melts or vaporises and burns with a flame (thermoplastics, wax)
  //   chars     - high-temperature polymer: hard to ignite, chars and smokes when overheated
  //   resists   - barely burns in normal air; overheating gives fumes rather than CO
  // The BASS-II CO/CO₂ ratios used alongside this are measured (data/reference-data.js).

  // What each material or fuel can release when it overheats or burns.
  // This is general combustion chemistry inferred from what each material is
  // made of (elements present), NOT measured in the loaded NASA data. Actual
  // amounts depend on temperature, oxygen and airflow. Review before relying on it.
  //   level: how the assessment flags it ("serious", "warning" or "info")
  //   products: [name, why it matters]
  const ORGANIC = ["Carbon monoxide (CO)", "Toxic; binds to blood haemoglobin. Produced by incomplete burning and smouldering."];
  const CO2 = ["Carbon dioxide (CO₂)", "Builds up in a closed cabin; raises breathing rate."];
  const HCN = ["Hydrogen cyanide (HCN)", "Highly toxic; can form when nitrogen-containing materials burn or decompose."];
  window.SMOKE_PRODUCTS = {
    materials: {
      "Kapton": { makeup: "polyimide film (carbon, hydrogen, nitrogen, oxygen)", level: "warning", behaviour: "chars",
        products: [ORGANIC, HCN, ["Nitrogen oxides (NOx)", "Respiratory irritants."], ["Dense smoke particles", "Obscure vision and carry adsorbed toxins."]] },
      "Nomex": { makeup: "aramid fabric (carbon, hydrogen, nitrogen, oxygen)", level: "warning", behaviour: "chars",
        products: [ORGANIC, HCN, ["Smoke particles", "Irritant; carry adsorbed toxins."]] },
      "Ultem": { makeup: "polyetherimide (carbon, hydrogen, nitrogen, oxygen)", level: "warning", behaviour: "chars",
        products: [ORGANIC, HCN, ["Smoke particles", "Irritant; carry adsorbed toxins."]] },
      "Pyrell": { makeup: "flame-retardant polyurethane foam (carbon, hydrogen, nitrogen, oxygen)", level: "warning", behaviour: "smoulders",
        products: [ORGANIC, HCN, ["Isocyanate vapours", "Strong respiratory irritants from decomposing polyurethane."], ["Dense smoke particles", "Foams smoulder and smoke heavily."]] },
      "Teflon": { makeup: "PTFE fluoropolymer (carbon, fluorine)", level: "serious", behaviour: "resists",
        products: [["Hydrogen fluoride (HF)", "Highly toxic and corrosive; forms from fluorinated decomposition products and moisture."],
          ["Carbonyl fluoride (COF₂)", "Toxic gas from overheated PTFE."],
          ["Fluorinated fume particles", "Overheated PTFE fume causes 'polymer fume fever'."]] },
      "PMMA (acrylic)": { makeup: "acrylic plastic (carbon, hydrogen, oxygen)", level: "info", behaviour: "flames",
        products: [ORGANIC, CO2, ["Methyl methacrylate vapour", "Irritant monomer released as PMMA decomposes."]] },
      "SIBAL fabric (cotton-fiberglass)": { makeup: "cotton (cellulose) with fiberglass", level: "info", behaviour: "smoulders",
        products: [ORGANIC, CO2, ["Smoke particles", "Cotton smoulders and smokes; fiberglass doesn't burn."]] },
      "Lampwick": { makeup: "cotton (cellulose)", level: "info", behaviour: "smoulders",
        products: [ORGANIC, CO2, ["Smoke particles", "Cotton smoulders and smokes."]] },
      "Silicone": { makeup: "silicone polymer (silicon, oxygen, carbon, hydrogen)", level: "info", behaviour: "resists",
        products: [ORGANIC, CO2, ["Silica (SiO₂) particles", "Fine white smoke; irritant if inhaled."]] },
      "Wax (candle or slab)": { makeup: "paraffin or plant wax (carbon, hydrogen, oxygen)", level: "info", behaviour: "flames",
        products: [ORGANIC, CO2, ["Soot", "Wax flames are sooty; soot coats surfaces and sensors."]] },
    },
    // Hydrocarbon gas fuels (all in the fuel list): same products whatever the gas.
    fuel: { makeup: "hydrocarbon gas (carbon, hydrogen)", level: "info",
      products: [ORGANIC, CO2, ["Soot", "Forms when the flame is short of oxygen; SPICE studied when these flames start to smoke."]] },
  };

  // Example input, roughly an ISS-like cabin. Used by the "Load example" button.
  window.EXAMPLE_INPUT = {
    environment: "Pressurised", gravity: "Microgravity (~0 g)", internal_temp_c: 22.5, pressure_kpa: 101.3,
    o2_pct: 21.5, n2_pct: 76.3, humidity_pct: 45, co2_ppm: 3000, h2_ppm: 20, ch4_ppm: 5, co_ppm: 2,
    monitoring: "Nominal", oxidizer_leak: "None detected",
    fuel_type: "Propane", fuel_storage: "Sealed cylinder", fuel_leak: "None detected", fuel_distance_m: 2.0,
    material_types: ["Kapton", "PMMA (acrylic)", "SIBAL fabric (cotton-fiberglass)"], material_distance_m: 0.4,
  };
})();
