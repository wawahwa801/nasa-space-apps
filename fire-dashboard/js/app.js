// Fire safety dashboard prototype.
// The layout is fixed; user input fills it in. Nothing is sent over the network.
//
// FireDashboard.mount(root) starts the dashboard inside `root` (the document,
// or a shadow root when embedded in another page) and returns a cleanup function.

(function () {
  const REF = window.REFERENCE_DATA;
  const T = window.THRESHOLDS;
  const SMOKE = window.SMOKE_PRODUCTS;
  const SECTIONS = window.PARAMETER_SECTIONS;
  const UNITS = window.UNIT_SYSTEMS;
  const { fmt } = window.Charts;

  const STORE = { values: "fd.values", datasets: "fd.datasets", units: "fd.units", compUnit: "fd.compUnit" };
  const LEVELS = {
    critical: { label: "Critical", icon: "✕", rank: 4 },
    serious: { label: "Serious", icon: "▲", rank: 3 },
    warning: { label: "Warning", icon: "!", rank: 2 },
    info: { label: "Note", icon: "i", rank: 1 },
    good: { label: "OK", icon: "✓", rank: 0 },
    // Not a severity: readings needed to judge are missing.
    unknown: { label: "Incomplete", icon: "?", rank: 0.5 },
  };

  // All lookups go through ROOT so the dashboard also works inside a shadow root.
  let ROOT = document;
  const $ = (sel, root = ROOT) => root.querySelector(sel);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  function load(key, fallback) {
    try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; }
  }

  let userDatasets = load(STORE.datasets, []);
  let unitPrefs = load(STORE.units, {});
  let compUnit = load(STORE.compUnit, "%") === "ppm" ? "ppm" : "%";
  // Mount options. With externalInputs, the host page supplies the values
  // (via FireDashboard.setInputs) and the dashboard's own form is hidden.
  let OPTS = {};
  let externalValues = {};
  const external = () => Boolean(OPTS.externalInputs);
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------------------------------------------------------------- form

  function allFields() {
    const out = [];
    for (const s of SECTIONS) for (const f of s.fields) out.push({ ...f, section: s.id });
    return out;
  }

  const FIELDS = Object.fromEntries(allFields().map((f) => [f.id, f]));

  // The unit a field is currently entered in ({unit, toBase, fromBase}).
  function unitOf(f) {
    if (!f.units) return { unit: f.unit || "", toBase: (x) => x, fromBase: (x) => x };
    const sys = UNITS[f.units];
    return sys.find((u) => u.unit === unitPrefs[f.id]) || sys[0];
  }
  // Up to 6 significant figures, without trailing zeros.
  const tidy = (x) => String(Number(x.toPrecision(6)));

  function fieldHtml(f) {
    const id = `f-${f.id}`;
    const described = `${id}-hint ${id}-err`;
    let control;
    if (f.type === "number") {
      const cur = unitOf(f).unit;
      const unit = f.units
        ? `<select id="${id}-unit" class="unit-select" data-field="${f.id}" data-prev="${esc(cur)}" aria-label="${esc(f.label)} unit">${UNITS[f.units]
            .map((u) => `<option ${u.unit === cur ? "selected" : ""}>${esc(u.unit)}</option>`).join("")}</select>`
        : `<span class="unit">${esc(f.unit || "")}</span>`;
      control = `<div class="with-unit"><input id="${id}" type="number" inputmode="decimal" step="any" aria-describedby="${described}">${unit}</div>`;
    } else {
      control = `<select id="${id}" aria-describedby="${described}"><option value="">Not specified</option>${f.options.map((o) => `<option>${esc(o)}</option>`).join("")}</select>`;
    }
    return `<div class="field" data-field="${f.id}"><label for="${id}">${esc(f.label)}</label>${control}
      <p class="field-error" id="${id}-err" hidden></p>
      ${f.hint ? `<p class="field-hint" id="${id}-hint">${esc(f.hint)}</p>` : ""}</div>`;
  }

  function renderForm() {
    $("#input-sections").innerHTML = SECTIONS
      .map((s) => `<details class="input-section" open>
          <summary>${esc(s.title)} <span class="count" data-count="${s.id}"></span></summary>
          <div class="fields">${s.fields.map(fieldHtml).join("")}</div>
        </details>`)
      .join("");
  }

  function rangeMessage(f) {
    const u = unitOf(f);
    return `Enter a value from ${tidy(u.fromBase(f.min))} to ${tidy(u.fromBase(f.max))} ${u.unit}. This value is ignored until it is corrected.`;
  }

  // External mode: values arrive in base units from the host page. Invalid
  // numbers and unknown choices are left out, just like form input.
  function readExternal() {
    const v = {};
    for (const f of allFields()) {
      const x = externalValues[f.id];
      if (f.type === "number") {
        const n = x === "" || x == null ? NaN : Number(x);
        const inRange = isFinite(n) && !(f.min != null && n < f.min - 1e-9) && !(f.max != null && n > f.max + 1e-9);
        v[f.id] = inRange ? n : null;
      } else if (f.id === "gravity") {
        // The host may describe gravity as a value (e.g. "0.5 g"); only the
        // microgravity prefix is used by the assessment.
        v[f.id] = typeof x === "string" ? x : "";
      } else {
        v[f.id] = f.options.includes(x) ? x : "";
      }
    }
    return { v, errors: {} };
  }

  // Values come back in base units. Invalid numbers are reported and left out.
  function readValues() {
    if (external()) return readExternal();
    const v = {};
    const errors = {};
    for (const f of allFields()) {
      const node = $(`#f-${CSS.escape(f.id)}`);
      if (!node) continue;
      if (f.type !== "number") { v[f.id] = node.value; continue; }
      v[f.id] = null;
      if (node.value === "") {
        if (node.validity && node.validity.badInput) errors[f.id] = "Enter a number.";
        continue;
      }
      const base = unitOf(f).toBase(Number(node.value));
      if (!isFinite(base)) errors[f.id] = "Enter a number.";
      else if ((f.min != null && base < f.min - 1e-9) || (f.max != null && base > f.max + 1e-9)) errors[f.id] = rangeMessage(f);
      else v[f.id] = base;
    }
    return { v, errors };
  }

  function writeValues(v) {
    for (const f of allFields()) {
      const node = $(`#f-${CSS.escape(f.id)}`);
      if (!node) continue;
      const x = v[f.id];
      if (f.type === "number") node.value = typeof x === "number" && isFinite(x) ? tidy(unitOf(f).fromBase(x)) : "";
      // Ignore saved values that are no longer valid options.
      else node.value = f.options.includes(x) ? x : "";
    }
  }

  function showErrors(errors) {
    for (const f of allFields()) {
      const box = $(`#f-${CSS.escape(f.id)}-err`);
      const input = $(`#f-${CSS.escape(f.id)}`);
      if (!box || !input) continue;
      const msg = errors[f.id];
      box.textContent = msg || "";
      box.hidden = !msg;
      if (msg) input.setAttribute("aria-invalid", "true");
      else input.removeAttribute("aria-invalid");
    }
  }

  function updateCounts(v) {
    for (const s of SECTIONS) {
      const filled = s.fields.filter((f) => has(v[f.id])).length;
      const node = $(`[data-count="${s.id}"]`);
      node.textContent = `${filled}/${s.fields.length}`;
      node.classList.toggle("complete", filled === s.fields.length);
      node.setAttribute("aria-label", `${filled} of ${s.fields.length} filled`);
    }
  }

  // Open the field's section, scroll to it and focus it.
  function gotoField(id) {
    const input = $(`#f-${CSS.escape(id)}`);
    if (!input) return;
    const details = input.closest("details");
    if (details) details.open = true;
    input.scrollIntoView({ block: "center", behavior: reducedMotion ? "auto" : "smooth" });
    input.focus({ preventScroll: true });
    const field = input.closest(".field");
    field.classList.remove("flash");
    void field.offsetWidth; // restart the highlight animation
    field.classList.add("flash");
  }

  // ---------------------------------------------------------- assessment

  const has = (x) => x != null && x !== "" && !(typeof x === "number" && isNaN(x));

  function fuelKey(text) {
    return (text || "").toLowerCase().replace(/[^a-z0-9 ]/g, " ").split(/\s+/).filter((w) => w.length > 2);
  }
  function matches(name, fuelText) {
    const words = fuelKey(fuelText);
    const n = name.toLowerCase();
    return words.length > 0 && words.some((w) => n.includes(w));
  }

  function nearestAcme(v) {
    if (!has(v.o2_pct) || !has(v.pressure_kpa)) return null;
    let pool = REF.acme.tests.filter((t) => t.pressure_kpa != null);
    const fuelMatched = pool.filter((t) => matches(t.fuel, v.fuel_type));
    if (fuelMatched.length >= T.acme_neighbours) pool = fuelMatched;
    const o2s = pool.map((t) => t.o2_pct);
    const ps = pool.map((t) => t.pressure_kpa);
    const o2Span = Math.max(...o2s) - Math.min(...o2s) || 1;
    const pSpan = Math.max(...ps) - Math.min(...ps) || 1;
    const ranked = pool
      .map((t) => ({ t, d: Math.hypot((t.o2_pct - v.o2_pct) / o2Span, (t.pressure_kpa - v.pressure_kpa) / pSpan) }))
      .sort((a, b) => a.d - b.d)
      .slice(0, T.acme_neighbours)
      .map((r) => r.t);
    const outOfRange =
      v.o2_pct < Math.min(...o2s) || v.o2_pct > Math.max(...o2s) || v.pressure_kpa < Math.min(...ps) || v.pressure_kpa > Math.max(...ps);
    return { tests: ranked, ignited: ranked.filter((t) => t.ignited).length, fuelMatched: pool === fuelMatched, outOfRange };
  }

  function leakLevel(status) {
    return status === "Confirmed" ? "critical" : status === "Suspected" ? "serious" : status === "Unknown" ? "warning" : null;
  }

  function assess(v) {
    const flags = [];
    const add = (level, title, detail, field) => flags.push({ level, title, detail, field });

    if (has(v.o2_pct)) {
      if (v.o2_pct > T.o2_enriched_pct) add("serious", "Oxygen-enriched atmosphere", `O₂ is ${fmt(v.o2_pct)}%, above ${T.o2_enriched_pct}%. Materials ignite more easily and burn faster.`, "o2_pct");
      else if (v.o2_pct < T.o2_deficient_pct) add("warning", "Oxygen-deficient atmosphere", `O₂ is ${fmt(v.o2_pct)}%, below ${T.o2_deficient_pct}%. A crew health concern; check for leaks of other gases.`, "o2_pct");
      else add("good", "Oxygen concentration in normal range", `O₂ is ${fmt(v.o2_pct)}%.`, "o2_pct");
    }
    if (has(v.o2_pct) && has(v.pressure_kpa)) {
      const pp = (v.o2_pct / 100) * v.pressure_kpa;
      if (pp > T.sea_level_ppo2_kpa * 1.05) add("info", "Oxygen partial pressure above sea-level air", `${fmt(pp)} kPa vs ${T.sea_level_ppo2_kpa} kPa at sea level. Flammability depends on both O₂ % and pressure.`, "pressure_kpa");
    }
    if (has(v.o2_pct) && has(v.n2_pct) && v.o2_pct + v.n2_pct > 100.5) {
      add("warning", "Gas percentages add up to more than 100%", `O₂ ${fmt(v.o2_pct)}% + N₂ ${fmt(v.n2_pct)}% = ${fmt(v.o2_pct + v.n2_pct)}%. Check the readings.`, "n2_pct");
    }

    for (const [key, gas, name] of [["h2_ppm", "h2", "Hydrogen"], ["ch4_ppm", "ch4", "Methane"]]) {
      if (!has(v[key])) continue;
      const share = v[key] / (T.lfl_pct[gas] * 10000);
      const pct = `${fmt(share * 100)}% of its lower flammability limit (${T.lfl_pct[gas]}% by volume)`;
      if (share >= T.lfl_critical_share) add("critical", `${name} near flammable concentration`, `${fmt(v[key])} ppm is ${pct}.`, key);
      else if (share >= T.lfl_warning_share) add("warning", `${name} elevated`, `${fmt(v[key])} ppm is ${pct}.`, key);
    }
    if (has(v.co_ppm)) {
      if (v.co_ppm > T.co_ppm.serious) add("serious", "Carbon monoxide very high", `${fmt(v.co_ppm)} ppm, above the ${T.co_ppm.serious} ppm NIOSH ceiling. CO can indicate smouldering or incomplete combustion.`, "co_ppm");
      else if (v.co_ppm > T.co_ppm.warning) add("warning", "Carbon monoxide elevated", `${fmt(v.co_ppm)} ppm, above the ${T.co_ppm.warning} ppm NIOSH exposure limit. CO can indicate smouldering.`, "co_ppm");
    }
    if (has(v.co2_ppm)) {
      if (v.co2_ppm > T.co2_ppm.serious) add("serious", "Carbon dioxide very high", `${fmt(v.co2_ppm)} ppm, above the ${fmt(T.co2_ppm.serious)} ppm NIOSH short-term limit.`, "co2_ppm");
      else if (v.co2_ppm > T.co2_ppm.warning) add("warning", "Carbon dioxide elevated", `${fmt(v.co2_ppm)} ppm, above the ${fmt(T.co2_ppm.warning)} ppm NIOSH exposure limit.`, "co2_ppm");
    }

    const fl = leakLevel(v.fuel_leak);
    const ol = leakLevel(v.oxidizer_leak);
    if (fl) add(fl, `Fuel leakage: ${v.fuel_leak.toLowerCase()}`, `${v.fuel_type ? esc(v.fuel_type) + ": " : ""}a leaking fuel can form a flammable mixture away from its storage location.`, "fuel_leak");
    if (ol) add(ol, `Oxygen / oxidizer leakage: ${v.oxidizer_leak.toLowerCase()}`, "A leak can locally enrich the atmosphere above the measured O₂ level.", "oxidizer_leak");
    if (["Suspected", "Confirmed"].includes(v.fuel_leak) && ["Suspected", "Confirmed"].includes(v.oxidizer_leak)) {
      add("critical", "Fuel and oxidizer both leaking", "Fuel and oxidizer leaks together greatly increase the chance of ignition.", "fuel_leak");
    }
    for (const [key, what, type] of [["fuel_distance_m", "Fuel", v.fuel_type], ["material_distance_m", "Material", v.material_type]]) {
      if (has(v[key]) && v[key] < T.min_ignition_distance_m) {
        add("warning", `${what} close to an ignition source`, `${type ? esc(type) + " is " : ""}${fmt(v[key])} m away, under the ${T.min_ignition_distance_m} m separation set in parameters.js.`, key);
      }
    }
    if (v.fuel_storage === "Open / vented") add("warning", "Fuel open or vented", `${v.fuel_type ? esc(v.fuel_type) : "The fuel"} is not contained, so it can mix with the cabin air.`, "fuel_storage");

    if (v.monitoring === "Offline") add("serious", "Atmospheric monitoring offline", "Gas readings may be stale or missing.", "monitoring");
    else if (v.monitoring === "Degraded" || v.monitoring === "Unknown") add("warning", `Atmospheric monitoring ${v.monitoring.toLowerCase()}`, "Treat gas readings with caution.", "monitoring");

    if (v.environment === "Vacuum" && has(v.pressure_kpa) && v.pressure_kpa > 1) {
      add("warning", "Condition and pressure disagree", `Marked as vacuum, but pressure is ${fmt(v.pressure_kpa)} kPa.`, "environment");
    }
    if ((v.gravity || "").startsWith("Microgravity")) {
      add("info", "Microgravity", "With no buoyant flow, a flame's oxygen supply depends on ventilation. Flames can spread upstream into the airflow and may persist at lower O₂ than on Earth.", "gravity");
    }

    const near = nearestAcme(v);
    if (near) {
      const share = near.ignited / near.tests.length;
      // Only warn when the comparison uses the same fuel; otherwise it is context.
      const level = !near.outOfRange && near.fuelMatched && share >= 0.5 ? "warning" : "info";
      add(level, `${near.ignited} of ${near.tests.length} similar ACME tests ignited`,
        `ACME test points with the closest O₂ % and pressure${near.fuelMatched ? ` using a fuel matching "${esc(v.fuel_type)}"` : " (all fuels)"}. ` +
        "Those tests had a gaseous fuel and a deliberate igniter, so this indicates whether the atmosphere can support burning, not whether a fire will start." +
        (near.outOfRange ? " Your conditions are outside the range ACME tested." : ""), near.fuelMatched ? "fuel_type" : "o2_pct");
    }

    // BASS-II: solid-material flames studied on the ISS at a range of O₂ levels.
    const bassTests = v.material_type
      ? REF.bass.tests.filter((t) => t.category === v.material_type && t.o2_initial_pct != null)
      : [];
    if (bassTests.length && has(v.o2_pct)) {
      const o2s = bassTests.map((t) => t.o2_initial_pct);
      const lo = Math.min(...o2s);
      const hi = Math.max(...o2s);
      const mat = esc(v.material_type);
      // The BASS-II matrix records starting O₂ but not ignition or extinction,
      // so this only places the user's O₂ relative to the tested range (issue #39).
      const caveat = " The test sheets don't record whether flames ignited or went out, and sample shapes and airflow varied, " +
        "so this compares conditions only; it is not a burning threshold.";
      if (v.o2_pct >= lo && v.o2_pct <= hi) {
        add("info", `Your O₂ is within the range BASS-II tested for ${mat}`,
          `${bassTests.length} BASS-II tests studied flames on ${mat} in microgravity at starting chamber O₂ from ${fmt(lo)}% to ${fmt(hi)}%; ` +
          `your O₂ (${fmt(v.o2_pct)}%) is inside that range.` + caveat, "material_type");
      } else if (v.o2_pct > hi) {
        add("info", `Your O₂ is above the range BASS-II tested for ${mat}`,
          `BASS-II tests on ${mat} started at ${fmt(lo)}–${fmt(hi)}% O₂; your O₂ (${fmt(v.o2_pct)}%) is higher, so there is no test data at your level.` + caveat, "o2_pct");
      } else {
        add("info", `Below the lowest O₂ BASS-II tested for ${mat}`,
          `BASS-II tests on ${mat} started at ${fmt(lo)}% O₂ or more; your O₂ (${fmt(v.o2_pct)}%) is lower. ` +
          "There is no test data at your level, which is not evidence that the material cannot burn.", "o2_pct");
      }
    }

    // Smoke: what the selected material can release when it overheats or burns
    // (general chemistry from its composition; see SMOKE_PRODUCTS in parameters.js).
    const smoke = v.material_type ? SMOKE.materials[v.material_type] : null;
    if (smoke) {
      const mat = esc(v.material_type);
      const names = smoke.products.map(([name]) => name).join(", ");
      add(smoke.level, smoke.level === "info" ? `Smoke from ${mat}` : `Toxic smoke if ${mat} overheats or burns`,
        `${mat} (${esc(smoke.makeup)}) can release ${esc(names)}. Overheating alone can produce this smoke, before any flame. ` +
        "General combustion chemistry, not measured in the loaded data; see Smoke and soot hazards.", "material_type");
    }

    flags.sort((a, b) => LEVELS[b.level].rank - LEVELS[a.level].rank);
    return { flags, near };
  }

  // ------------------------------------------------------------ rendering

  function badge(level) {
    return `<span class="status status-${level}"><span class="status-icon" aria-hidden="true">${LEVELS[level].icon}</span>${LEVELS[level].label}</span>`;
  }

  function renderSummary(v, result) {
    const issues = result.flags.filter((f) => LEVELS[f.level].rank >= 2);
    const top = issues[0]?.level || (result.flags.length ? "good" : null);
    const pu = unitOf(FIELDS.pressure_kpa);
    const pp = has(v.o2_pct) && has(v.pressure_kpa) ? (v.o2_pct / 100) * v.pressure_kpa : null;
    const tile = (label, value, unit, sub) =>
      `<div class="tile"><div class="tile-label">${label}</div><div class="tile-value">${value}<span class="tile-unit">${unit}</span></div>${sub ? `<div class="tile-sub">${sub}</div>` : ""}</div>`;
    $("#summary").innerHTML = `
      <div class="tile hero">
        <div class="tile-label">Issues found</div>
        <div class="hero-value">${top ? issues.length : "–"}</div>
        <div class="tile-sub">${top ? badge(top) + (issues.length ? " highest severity" : " nothing flagged") : "Enter conditions to assess"}</div>
      </div>
      ${tile("Oxygen", has(v.o2_pct) ? fmt(v.o2_pct) : "–", "%", has(v.o2_pct) ? `Enrichment threshold ${T.o2_enriched_pct}%` : "")}
      ${tile("O₂ partial pressure", pp != null ? fmt(pu.fromBase(pp)) : "–", pu.unit, `Sea-level air ${fmt(pu.fromBase(T.sea_level_ppo2_kpa))} ${pu.unit}`)}
      ${tile("Internal pressure", has(v.pressure_kpa) ? fmt(pu.fromBase(v.pressure_kpa)) : "–", pu.unit, v.environment ? esc(v.environment) : "")}`;
    $("#results-bar-summary").innerHTML = top
      ? `${badge(top)} ${issues.length} issue${issues.length === 1 ? "" : "s"}`
      : "No inputs yet";
  }

  function renderFlags(result) {
    const list = $("#flags");
    if (!result.flags.length) {
      list.innerHTML = external()
        ? '<li class="empty">No inputs yet. Set values in the Parameters panel, or <button type="button" class="link-btn" data-action="example">load the example</button> to see how it works.</li>'
        : '<li class="empty">No inputs yet. Fill in the form, or <button type="button" class="link-btn" data-action="example">load the example</button> to see how it works.</li>';
      return;
    }
    list.innerHTML = result.flags
      .map((f) => `<li class="flag">${badge(f.level)}<div>${f.field
        ? `<button type="button" class="flag-title flag-link" data-goto="${f.field}" title="Go to ${esc(FIELDS[f.field]?.label || "input")}">${f.title}</button>`
        : `<div class="flag-title">${f.title}</div>`}<div class="flag-detail">${f.detail}</div></div></li>`)
      .join("");
  }

  function meter(label, value, limit, unitText, levels) {
    if (!has(value)) return `<div class="meter"><div class="meter-head"><span>${label}</span><span class="muted">no reading</span></div><div class="meter-track"></div></div>`;
    const share = value / limit;
    const level = share >= levels[1] ? "critical" : share >= levels[0] ? "warning" : "good";
    const width = Math.min(share, 1) * 100;
    return `<div class="meter">
      <div class="meter-head"><span>${label}</span><span>${unitText} ${badge(level)}</span></div>
      <div class="meter-track track-${level}" role="meter" aria-valuemin="0" aria-valuemax="${limit}" aria-valuenow="${value}" aria-label="${label}">
        <div class="meter-fill fill-${level}" style="width:${Math.max(width, 1)}%"></div>
      </div></div>`;
  }

  function renderMeters(v) {
    const lfl = (gas, key, name) => {
      const limit = T.lfl_pct[gas] * 10000;
      return meter(`${name}, share of flammability limit`, v[key], limit,
        has(v[key]) ? `${fmt((v[key] / limit) * 100)}% of LFL` : "", [T.lfl_warning_share, T.lfl_critical_share]);
    };
    const exposure = (key, name, limits) =>
      meter(`${name}, share of NIOSH limit`, v[key], limits.serious, has(v[key]) ? `${fmt(v[key])} ppm` : "",
        [limits.warning / limits.serious, 1]);
    $("#meters").innerHTML = [
      lfl("h2", "h2_ppm", "Hydrogen"),
      lfl("ch4", "ch4_ppm", "Methane"),
      exposure("co_ppm", "Carbon monoxide", T.co_ppm),
      exposure("co2_ppm", "Carbon dioxide", T.co2_ppm),
    ].join("");
  }

  let acmeFilter = "auto";

  function renderAcme(v, result) {
    const fuels = [...new Set(REF.acme.tests.map((t) => t.fuel))].sort();
    const sel = $("#acme-fuel");
    if (sel.options.length <= 1) {
      sel.innerHTML = `<option value="auto">Match my fuel</option><option value="all">All fuels</option>` +
        fuels.map((f) => `<option value="${esc(f)}">${esc(f)}</option>`).join("");
      sel.value = acmeFilter;
    }
    let tests = REF.acme.tests.filter((t) => t.pressure_kpa != null);
    let caption;
    if (acmeFilter === "auto") {
      const m = tests.filter((t) => matches(t.fuel, v.fuel_type));
      if (m.length) { tests = m; caption = `Fuels matching "${esc(v.fuel_type)}"`; } else caption = v.fuel_type ? `No ACME fuel matches "${esc(v.fuel_type)}"; showing all fuels` : "All fuels";
    } else if (acmeFilter !== "all") {
      tests = tests.filter((t) => t.fuel === acmeFilter);
      caption = esc(acmeFilter);
    } else caption = "All fuels";
    const nearIds = new Set((result.near?.tests || []).map((t) => t.id));
    $("#acme-caption").innerHTML = `${caption} · ${tests.length} test points · ${tests.filter((t) => t.ignited).length} ignited` +
      (has(v.o2_pct) && has(v.pressure_kpa) ? "" : '<br><span class="muted">Enter O₂ and internal pressure to place your conditions on the chart.</span>');

    const point = (t) => ({
      x: t.o2_pct, y: t.pressure_kpa, series: t.ignited ? "yes" : "no",
      tip: `<strong>${t.ignited ? "Ignited" : "Did not ignite"}</strong><br>${esc(t.fuel)}<br>O₂ ${fmt(t.o2_pct)}% · ${fmt(t.pressure_kpa)} kPa<br>Fuel ${fmt(t.fuel_pct)}% · ${esc(t.date)}<br><span class="muted">${esc(t.id)}</span>`,
    });
    Charts.scatter($("#acme-chart"), {
      points: tests.map(point),
      series: [{ id: "no", name: "Did not ignite", cls: "s1" }, { id: "yes", name: "Ignited", cls: "s2" }],
      xLabel: "Oxygen in chamber mixture (%)",
      yLabel: "Chamber pressure (kPa)",
      height: 320,
      dodge: 5,
      marker: has(v.o2_pct) && has(v.pressure_kpa) ? { x: v.o2_pct, y: v.pressure_kpa, label: "Your input" } : null,
    });
    $("#acme-table").innerHTML = `<table><thead><tr><th>Test point</th><th>Fuel</th><th>O₂ %</th><th>Pressure kPa</th><th>Fuel %</th><th>Result</th></tr></thead><tbody>${tests
      .map((t) => `<tr class="${nearIds.has(t.id) ? "highlight" : ""}"><td>${esc(t.id)}</td><td>${esc(t.fuel)}</td><td>${fmt(t.o2_pct)}</td><td>${fmt(t.pressure_kpa)}</td><td>${fmt(t.fuel_pct)}</td><td>${t.ignited ? "Ignited" : "No ignition"}</td></tr>`)
      .join("")}</tbody></table>`;
  }

  function renderSaffire(v) {
    const s = REF.saffire.series;
    const panels = [
      { key: "o2_pct", title: "Oxygen", unit: "%", ref: has(v.o2_pct) ? v.o2_pct : null },
      { key: "co2_pct", title: "Carbon dioxide", unit: "%", ref: has(v.co2_ppm) ? v.co2_ppm / 10000 : null },
      { key: "pressure_kpa", title: "Pressure", unit: "kPa", ref: has(v.pressure_kpa) ? v.pressure_kpa : null },
      { key: "plume_max_c", title: "Hottest plume thermocouple (not cabin air)", unit: "°C" },
    ];
    $("#saffire-charts").innerHTML = panels.map((p) => `<figure class="mini"><figcaption>${p.title} <span class="muted">(${p.unit})</span></figcaption><div class="chart" id="saffire-${p.key}"></div></figure>`).join("");
    for (const p of panels) {
      Charts.line($(`#saffire-${p.key}`), {
        x: s.t_s, y: s[p.key], xLabel: "Time (s)", yLabel: p.unit, unit: p.unit, height: 170,
        ref: p.ref != null ? { value: p.ref, label: `${p.refName || "Your input"}: ${fmt(p.ref)} ${p.unit}` } : null,
      });
    }
  }

  // Air composition donut. Everything is converted to ppm (1% = 10,000 ppm),
  // then shown in the unit the user picked.
  const TRACE = [["co2_ppm", "CO₂"], ["h2_ppm", "H₂"], ["ch4_ppm", "CH₄"], ["co_ppm", "CO"]];

  // Water vapour (ppm by volume) from relative humidity, temperature and
  // pressure: saturation pressure from the Buck equations (over water at or
  // above 0 °C, over ice below), capped at the total pressure.
  function waterVapourPpm(v) {
    if (!has(v.humidity_pct) || !has(v.internal_temp_c) || !has(v.pressure_kpa) || v.pressure_kpa <= 0) return null;
    const t = v.internal_temp_c;
    const psat = t >= 0
      ? 0.61121 * Math.exp((18.678 - t / 234.5) * (t / (257.14 + t)))
      : 0.61115 * Math.exp((23.036 - t / 333.7) * (t / (279.82 + t)));
    if (!isFinite(psat)) return null;
    const pv = Math.min((v.humidity_pct / 100) * psat, v.pressure_kpa);
    return (pv / v.pressure_kpa) * 1e6;
  }

  function compText(ppm) {
    if (compUnit === "ppm") return `${Math.round(ppm).toLocaleString()} ppm`;
    const pct = ppm / 10000;
    if (pct === 0) return "0%";
    return `${pct >= 1 ? pct.toLocaleString(undefined, { maximumFractionDigits: 2 }) : pct.toLocaleString(undefined, { maximumSignificantDigits: 3 })}%`;
  }

  function renderComposition(v) {
    ROOT.querySelectorAll("[data-comp-unit]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.compUnit === compUnit)));
    const n2 = has(v.n2_pct) ? v.n2_pct * 10000 : null;
    const o2 = has(v.o2_pct) ? v.o2_pct * 10000 : null;
    const water = waterVapourPpm(v);
    const trace = [["Water vapour (H₂O)", water], ...TRACE.map(([k, name]) => [name, has(v[k]) ? v[k] : null])];
    const traceSum = trace.reduce((a, [, x]) => a + (x || 0), 0);
    const known = (n2 || 0) + (o2 || 0) + traceSum;
    const legend = $("#composition-legend");
    const caption = $("#composition-caption");
    if (!known) {
      Charts.donut($("#composition-chart"), { slices: [], size: 180, center: { value: "–", label: "no readings" }, label: "No gas readings yet" });
      legend.innerHTML = '<li class="comp-note">Enter O₂, N₂, humidity or trace gas readings to see the composition.</li>';
      caption.textContent = "Share of each gas in the cabin air.";
      return;
    }
    const over = known > 1e6 + 1;
    const other = over ? 0 : Math.max(0, 1e6 - known);
    const slices = [
      { name: "Nitrogen (N₂)", value: n2 || 0, cls: "s1" },
      { name: "Oxygen (O₂)", value: o2 || 0, cls: "s2" },
      { name: "Minor gases", value: traceSum, cls: "s3" },
      { name: "Unaccounted", value: other, cls: "other" },
    ];
    for (const sl of slices) sl.tip = `<strong>${sl.name}</strong><br>${compText(sl.value)} · ${fmt((sl.value / Math.max(known, 1e6)) * 100)}% of total`;
    Charts.donut($("#composition-chart"), {
      slices, size: 180,
      center: { value: compText(Math.min(known, 1e6)).replace(" ppm", ""), label: compUnit === "ppm" ? "ppm measured" : "measured" },
      label: `Air composition: ${slices.filter((x) => x.value > 0).map((x) => `${x.name} ${compText(x.value)}`).join(", ")}`,
    });
    const row = (sl) => `<li><span class="swatch ${sl.cls}" aria-hidden="true"></span><span>${sl.name}</span><span class="value">${compText(sl.value)}</span></li>`;
    legend.innerHTML = [
      n2 !== null ? row(slices[0]) : '<li><span class="swatch s1" aria-hidden="true"></span><span>Nitrogen (N₂)</span><span class="value muted">no reading</span></li>',
      o2 !== null ? row(slices[1]) : '<li><span class="swatch s2" aria-hidden="true"></span><span>Oxygen (O₂)</span><span class="value muted">no reading</span></li>',
      row(slices[2]),
      ...trace.map(([name, x]) => `<li class="sub"><span>${name}</span><span class="value${x === null ? " muted" : ""}">${x === null ? (name.startsWith("Water") ? "needs humidity, temperature and pressure" : "no reading") : compText(x)}</span></li>`),
      over ? "" : row(slices[3]),
      over ? `<li class="comp-note">Readings add up to ${compText(known)}, more than 100%. Check the values; the chart is scaled to the total.</li>`
        : '<li class="comp-note">Water vapour is calculated from relative humidity, temperature and pressure. Unaccounted is the remainder up to 100% (mostly argon in Earth-like air, plus gases not entered).</li>',
    ].join("");
    caption.textContent = "Share of each gas in the cabin air. Water vapour and trace gases are drawn as one slice; each is listed.";
  }

  function renderBass(v) {
    const tests = REF.bass.tests;
    const runs = REF.bass.bass1.runs;
    const counts = new Map();
    for (const t of tests) counts.set(t.category, (counts.get(t.category) || 0) + 1);
    const rows = [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([cat, n]) => ({ id: cat, label: `${cat} (${n})`, shortLabel: `${cat.split(" (")[0]} (${n})`, highlight: cat === v.material_type }));
    const coText = (t) => `${fmt(t.co_initial_ppm)} → ${t.co_final_ppm != null ? fmt(t.co_final_ppm) : esc(t.co_final_raw || "–")} ppm`;
    Charts.strip($("#bass-chart"), {
      rows,
      points: tests.map((t) => ({
        row: t.category,
        x: t.o2_initial_pct,
        tip: `<strong>${esc(t.material)}</strong><br>${esc(t.pi)} · test ${esc(t.test)}${t.date ? " · " + esc(t.date) : ""}` +
          `<br>O₂ ${fmt(t.o2_initial_pct)}% → ${fmt(t.o2_final_pct)}%<br>CO ${coText(t)}` +
          (t.air_display ? `<br><span class="muted">Air display: ${esc(t.air_display)}</span>` : ""),
      })),
      xLabel: "Starting chamber O₂ (%)",
      ref: has(v.o2_pct) ? { value: v.o2_pct, label: `Your O₂: ${fmt(v.o2_pct)}%` } : null,
    });

    $("#bass-caption").textContent =
      `${tests.length} tests by six research teams. Each dot is one test at its starting chamber O₂; ` +
      `hover for the sample, CO change and recorded air flow. The earlier BASS experiment (2012–13) logged ${runs.length} runs without atmosphere readings.`;

    const selected = rows.some((r) => r.highlight) ? v.material_type : null;
    const pool = selected ? tests.filter((t) => t.category === selected) : tests;
    const o2s = pool.map((t) => t.o2_initial_pct).filter((x) => x != null);
    const coMax = pool.filter((t) => t.co_rise_ppm != null).sort((a, b) => b.co_rise_ppm - a.co_rise_ppm)[0];
    const co2Max = Math.max(...pool.map((t) => t.co2_rise_pct ?? -Infinity));
    const runsFor = selected ? runs.filter((r) => r.category === selected) : runs;
    const wake = runsFor.filter((r) => r.configuration === "wake ignition").length;
    const opposed = runsFor.filter((r) => r.configuration === "opposed flow").length;
    const what = selected ? esc(selected) : "all materials";
    const items = [
      `<li><strong>BASS-II, ${what}:</strong> ${pool.length} tests with starting O₂ ${range(o2s)}%.</li>`,
      coMax ? `<li><strong>Combustion products:</strong> chamber CO rose by up to ${fmt(coMax.co_rise_ppm)} ppm during one test (${esc(coMax.pi)} ${esc(coMax.test)}), and CO₂ by up to ${fmt(co2Max)}%.</li>` : "",
      `<li><strong>BASS (2012–13), ${what}:</strong> ${runsFor.length} runs${wake || opposed ? `, including ${wake} wake-ignition and ${opposed} opposed-flow tests` : ""}.</li>`,
      `<li class="muted">Ignition and extinction aren't recorded as columns, so this shows the O₂ levels at which flames were studied, not whether a given fire would start.</li>`,
    ];
    if (v.material_type && !selected) items.unshift(`<li class="muted">No BASS-II tests for "${esc(v.material_type)}"; showing all materials.</li>`);
    $("#bass-stats").innerHTML = items.join("");

    $("#bass-table").innerHTML = `<table><thead><tr><th>Team</th><th>Test</th><th>Material</th><th>O₂ start → end %</th><th>CO₂ start → end %</th><th>CO start → end ppm</th></tr></thead><tbody>${[...tests]
      .sort((a, b) => a.category.localeCompare(b.category) || a.o2_initial_pct - b.o2_initial_pct)
      .map((t) => `<tr class="${t.category === v.material_type ? "highlight" : ""}"><td>${esc(t.pi)}</td><td>${esc(t.test)}</td><td>${esc(t.material)}</td><td>${fmt(t.o2_initial_pct)} → ${fmt(t.o2_final_pct)}</td><td>${fmt(t.co2_initial_pct)} → ${fmt(t.co2_final_pct)}</td><td>${coText(t)}</td></tr>`)
      .join("")}</tbody></table>`;
  }

  // Overall smoke status. Known hazards (high CO/CO₂, monitoring down, a
  // toxic-smoke material) always show. Otherwise the result is only "OK" when
  // both CO and CO₂ readings are present: a working monitor is not evidence
  // that unreported readings are safe (issue #40).
  function smokeStatus(v) {
    const gasLevel = (x, lim) => (!has(x) ? null : x > lim.serious ? "serious" : x > lim.warning ? "warning" : "good");
    const co = gasLevel(v.co_ppm, T.co_ppm);
    const co2 = gasLevel(v.co2_ppm, T.co2_ppm);
    const detection = v.monitoring === "Offline" ? "serious" : ["Degraded", "Unknown"].includes(v.monitoring) ? "warning" : v.monitoring ? "good" : null;
    const material = v.material_type ? SMOKE.materials[v.material_type] : null;
    const missing = [["CO", co], ["CO₂", co2]].filter(([, lv]) => !lv).map(([name]) => name);
    const known = [co, co2, material && material.level, detection === "good" ? null : detection].filter(Boolean);
    const worst = known.sort((a, b) => LEVELS[b].rank - LEVELS[a].rank)[0] || null;
    let overall;
    if (worst && LEVELS[worst].rank >= LEVELS.warning.rank) overall = worst;
    else if (missing.length) overall = "unknown";
    else overall = worst || "good";
    return { overall, co, co2, detection, material, missing };
  }

  function renderSmoke(v) {
    const { overall, co, co2, detection, material, missing } = smokeStatus(v);
    $("#smoke-level").innerHTML = `${badge(overall)} <span class="muted">smoke hazard${missing.length ? ` · ${missing.join(" and ")} reading${missing.length > 1 ? "s" : ""} needed` : ""}</span>`;

    const reading = (label, value, unit, lv, note) =>
      `<li><span>${label}</span><span class="value">${value === null ? '<span class="muted">no reading</span>' : `${fmt(value)} ${unit}`}</span>${lv ? badge(lv) : "<span></span>"}<small>${note}</small></li>`;
    $("#smoke-readings").innerHTML = [
      reading("Carbon monoxide (CO)", has(v.co_ppm) ? v.co_ppm : null, "ppm", co, `NIOSH limits ${T.co_ppm.warning} ppm (8-hour average) and ${T.co_ppm.serious} ppm (ceiling). Rising CO is an early sign of smouldering.`),
      reading("Carbon dioxide (CO₂)", has(v.co2_ppm) ? v.co2_ppm : null, "ppm", co2, `NIOSH limits ${T.co2_ppm.warning.toLocaleString()} ppm (8-hour average) and ${T.co2_ppm.serious.toLocaleString()} ppm (short-term).`),
      `<li><span>Smoke detection</span><span class="value">${v.monitoring ? esc(v.monitoring) : '<span class="muted">not specified</span>'}</span>${detection ? badge(detection) : "<span></span>"}<small>${detection === "serious" || detection === "warning" ? "Smoke and toxic gases may go unnoticed while monitoring is " + esc(v.monitoring.toLowerCase()) + "." : "Atmospheric monitoring status from the Parameters panel."}</small></li>`,
    ].join("");

    const productList = (title, entry) => `<li class="smoke-group">${title} <span class="muted">(${esc(entry.makeup)})</span></li>` +
      entry.products.map(([name, why]) => `<li><span>${esc(name)}</span><small>${esc(why)}</small></li>`).join("");
    const groups = [];
    if (material) groups.push(productList(`If <strong>${esc(v.material_type)}</strong> overheats or burns`, material));
    if (v.fuel_type) groups.push(productList(`If <strong>${esc(v.fuel_type)}</strong> burns`, SMOKE.fuel));
    $("#smoke-products").innerHTML = groups.length ? groups.join("") : '<li class="muted">Select a material or fuel in the Parameters panel to see what its smoke can contain.</li>';

    // Measured: chamber CO rise during BASS-II burns, by material.
    const byCat = new Map();
    for (const t of REF.bass.tests) {
      if (!byCat.has(t.category)) byCat.set(t.category, []);
      byCat.get(t.category).push(t);
    }
    const median = (xs) => { const a = [...xs].sort((p, q) => p - q); return a.length ? (a.length % 2 ? a[(a.length - 1) / 2] : (a[a.length / 2 - 1] + a[a.length / 2]) / 2) : null; };
    const barsData = [...byCat.entries()].map(([cat, tests]) => {
      const rises = tests.map((t) => t.co_rise_ppm).filter((x) => x != null);
      const co2r = tests.map((t) => t.co2_rise_pct).filter((x) => x != null);
      return {
        label: cat, shortLabel: cat.split(" (")[0], value: rises.length ? Math.max(...rises) : NaN, highlight: cat === v.material_type,
        tip: `<strong>${esc(cat)}</strong><br>${rises.length} tests with CO readings<br>Typical CO rise ${fmt(median(rises))} ppm, largest ${fmt(Math.max(...rises))} ppm` +
          (co2r.length ? `<br>CO₂ rise up to ${fmt(Math.max(...co2r))}%` : ""),
      };
    }).sort((a, b) => (b.value || 0) - (a.value || 0));
    Charts.bars($("#smoke-chart"), { bars: barsData, unit: "ppm", xLabel: "Largest CO rise in one test (ppm)" });

    const notes = [];
    const allRises = REF.bass.tests.map((t) => t.co_rise_ppm).filter((x) => x != null);
    notes.push(`<li>CO rose in ${allRises.filter((x) => x > 0).length} of ${allRises.length} BASS-II burns with CO readings, by up to ${fmt(Math.max(...allRises))} ppm. These are readings in the small BASS-II test chamber; in a full cabin the same burn is diluted into more air, but smoke collects near its source first.</li>`);
    if ((v.gravity || "").startsWith("Microgravity")) {
      notes.push("<li><strong>Microgravity:</strong> smoke doesn't rise. It lingers around the source and moves only with ventilation airflow, so where it goes depends on the cabin fans.</li>");
    }
    const same = v.material_type ? REF.samer.tests.filter((t) => t.material === v.material_type) : [];
    notes.push(same.length
      ? `<li><strong>SAME-R</strong> heated ${esc(v.material_type)} in ${same.length} tests to study the smoke spacecraft detectors must sense. Its measured particle sizes aren't in the loaded data.</li>`
      : "<li><strong>Data gap:</strong> the loaded data doesn't measure smoke particles or toxic gases such as HCN or HF; SAME-R's particle-size results and SPICE's smoke points would fill it.</li>");
    $("#smoke-notes").innerHTML = notes.join("");
  }

  function range(values) {
    const xs = values.filter((x) => x != null);
    return xs.length ? `${fmt(Math.min(...xs))}–${fmt(Math.max(...xs))}` : "–";
  }

  function renderRelated(v) {
    const out = [];
    if (v.material_type) {
      const same = REF.samer.tests.filter((t) => t.material === v.material_type);
      const bass2 = REF.bass.tests.filter((t) => t.category === v.material_type);
      const bass1 = REF.bass.bass1.runs.filter((r) => r.category === v.material_type);
      if (bass2.length || bass1.length) {
        out.push(`<li><strong>BASS / BASS-II burns (${esc(v.material_type)}):</strong> ${bass2.length} BASS-II tests at starting O₂ ${range(bass2.map((t) => t.o2_initial_pct))}% and ${bass1.length} earlier BASS runs. See the BASS-II chart for details.</li>`);
      }
      if (same.length) out.push(`<li><strong>SAME-R smoke tests (${esc(v.material_type)}):</strong> ${same.length} tests, with heater ratio Rt/R0 ${range(same.map((t) => t.heater_ratio))} and flow ${range(same.map((t) => t.inlet_velocity_cm_s))} cm/s. Shows the conditions under which this material's smoke was measured.</li>`);
    }
    if (v.fuel_type) {
      const spice = REF.spice.runs.filter((r) => matches(r.fuel, v.fuel_type));
      if (spice.length) {
        out.push(`<li><strong>SPICE gas-jet flames (${esc(v.fuel_type)}):</strong> ${spice.length} runs${new Set(spice.map((r) => r.fuel)).size > 1 ? " including diluted mixtures" : ""}, at fuel rates ${range(spice.map((r) => r.fuel_rate_mg_s))} mg/s and coflow ${range(spice.map((r) => r.air_rate_cm_s))} cm/s.</li>`);
      }
      const acme = REF.acme.tests.filter((t) => matches(t.fuel, v.fuel_type));
      if (acme.length) {
        const lit = acme.filter((t) => t.ignited);
        out.push(`<li><strong>ACME chamber tests (${esc(v.fuel_type)}):</strong> ${acme.length} test points; ${lit.length} ignited${lit.length ? `, at O₂ as low as ${fmt(Math.min(...lit.map((t) => t.o2_pct)))}%` : ""}.</li>`);
      }
    }
    $("#related").innerHTML = out.length ? out.join("") : '<li class="muted">Select a fuel or material to see related NASA tests.</li>';
  }

  // ------------------------------------------------------------- datasets

  function parseCsv(text) {
    const rows = [];
    let row = [], cell = "", quoted = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (quoted) {
        if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; }
        else if (c === '"') quoted = false;
        else cell += c;
      } else if (c === '"') quoted = true;
      else if (c === ",") { row.push(cell); cell = ""; }
      else if (c === "\n" || c === "\r") {
        if (c === "\r" && text[i + 1] === "\n") i++;
        row.push(cell); rows.push(row); row = []; cell = "";
      } else cell += c;
    }
    if (cell !== "" || row.length) { row.push(cell); rows.push(row); }
    const nonEmpty = rows.filter((r) => r.some((x) => x.trim() !== ""));
    const header = (nonEmpty.shift() || []).map((h, i) => h.trim() || `Column ${i + 1}`);
    return { columns: header, rows: nonEmpty };
  }

  function numericColumns(ds) {
    return ds.columns
      .map((name, i) => {
        const vals = ds.rows.map((r) => (r[i] === undefined || r[i].trim() === "" ? null : Number(r[i]))).filter((x) => x !== null);
        const nums = vals.filter((x) => isFinite(x));
        return { name, i, nums, numeric: nums.length >= Math.max(2, vals.length * 0.8) };
      })
      .filter((c) => c.numeric);
  }

  function builtInRows() {
    return [
      { name: REF.acme.name, file: REF.acme.file, rows: REF.acme.tests.length, desc: REF.acme.description },
      { name: REF.saffire.name, file: REF.saffire.file, rows: REF.saffire.series.t_s.length, desc: REF.saffire.description },
      { name: REF.spice.name, file: REF.spice.file, rows: REF.spice.runs.length, desc: REF.spice.description },
      { name: REF.samer.name, file: REF.samer.file, rows: REF.samer.tests.length, desc: REF.samer.description },
      { name: REF.bass.name, file: REF.bass.file, rows: REF.bass.tests.length, desc: REF.bass.description },
      { name: REF.bass.bass1.name, file: REF.bass.bass1.file, rows: REF.bass.bass1.runs.length, desc: REF.bass.bass1.description },
    ];
  }

  function renderDatasets() {
    const builtIn = builtInRows()
      .map((d) => `<li><div class="ds-name">${esc(d.name)} <span class="muted">· ${d.rows} rows · built in</span></div><div class="ds-desc">${esc(d.desc)}</div><div class="ds-file muted">data/${esc(d.file)}</div></li>`)
      .join("");
    const mine = userDatasets
      .map((d, k) => {
        const cols = numericColumns(d);
        const opts = (sel) => cols.map((c) => `<option value="${c.i}" ${c.i === sel ? "selected" : ""}>${esc(c.name)}</option>`).join("");
        const yi = d.y ?? cols[1]?.i ?? cols[0]?.i;
        const summary = cols.map((c) => {
          const mean = c.nums.reduce((a, b) => a + b, 0) / c.nums.length;
          return `<tr><td>${esc(c.name)}</td><td>${fmt(Math.min(...c.nums))}</td><td>${fmt(mean)}</td><td>${fmt(Math.max(...c.nums))}</td></tr>`;
        }).join("");
        return `<li class="user-ds">
          <div class="ds-name">${esc(d.name)} <span class="muted">· ${d.rows.length} rows · ${d.columns.length} columns · added by you</span>
            <button type="button" class="link-btn" data-remove-ds="${k}">Remove</button></div>
          ${cols.length ? `<div class="ds-controls">
              <label>X <select data-ds="${k}" data-axis="x"><option value="-1">Row number</option>${opts(d.x ?? -1)}</select></label>
              <label>Y <select data-ds="${k}" data-axis="y">${opts(yi)}</select></label></div>
            <div class="chart" id="ds-chart-${k}"></div>
            <details><summary>Column summary</summary><table><thead><tr><th>Column</th><th>Min</th><th>Mean</th><th>Max</th></tr></thead><tbody>${summary}</tbody></table></details>`
          : '<p class="muted">No numeric columns found to chart.</p>'}
        </li>`;
      })
      .join("");
    $("#datasets").innerHTML = builtIn + mine;
    userDatasets.forEach((d, k) => {
      const cols = numericColumns(d);
      if (!cols.length) return;
      const yi = d.y ?? cols[1]?.i ?? cols[0]?.i;
      const xi = d.x ?? -1;
      const col = (i) => d.rows.map((r) => (r[i] === undefined || r[i].trim() === "" ? null : Number(r[i])));
      const ys = col(yi).map((x) => (isFinite(x) ? x : null));
      const xs = xi < 0 ? ys.map((_, j) => j + 1) : col(xi).map((x) => (isFinite(x) ? x : null));
      const yName = d.columns[yi];
      Charts.line($(`#ds-chart-${k}`), { x: xs, y: ys, xLabel: xi < 0 ? "Row" : d.columns[xi], yLabel: yName, unit: "", height: 200 });
    });
  }

  function addDataset(file) {
    const status = $("#dataset-status");
    if (!/\.csv$/i.test(file.name)) { status.textContent = "Only .csv files can be added here. Save Excel sheets as CSV first."; return; }
    const reader = new FileReader();
    reader.onload = () => {
      const parsed = parseCsv(String(reader.result));
      if (!parsed.rows.length) { status.textContent = `${file.name} has no data rows.`; return; }
      userDatasets.push({ name: file.name, ...parsed });
      const saved = save(STORE.datasets, userDatasets);
      status.textContent = `Added ${file.name} (${parsed.rows.length} rows).` + (saved ? "" : " It is too large to keep after reloading the page.");
      renderDatasets();
    };
    reader.onerror = () => { status.textContent = `Could not read ${file.name}.`; };
    reader.readAsText(file);
  }

  // ---------------------------------------------------------------- wiring

  let timer;
  function update() {
    const { v, errors } = readValues();
    if (!external()) {
      showErrors(errors);
      updateCounts(v);
      save(STORE.values, v);
    }
    const result = assess(v);
    renderSummary(v, result);
    renderFlags(result);
    renderMeters(v);
    renderComposition(v);
    renderBass(v);
    renderSmoke(v);
    renderAcme(v, result);
    renderSaffire(v);
    renderRelated(v);
    return { v, result };
  }
  const scheduleUpdate = () => { clearTimeout(timer); timer = setTimeout(update, 150); };

  function init() {
    renderForm();
    writeValues(load(STORE.values, {}));
    renderDatasets();
    update();
    $("#generated").textContent = REF.generated;

    $("#input-form").addEventListener("input", scheduleUpdate);
    $("#input-form").addEventListener("change", scheduleUpdate);
    $("#input-form").addEventListener("submit", (e) => e.preventDefault());
    const status = (msg) => { $("#input-status").textContent = msg; };
    const loadExample = () => { writeValues(window.EXAMPLE_INPUT); update(); status("Example loaded. Change any value to see the dashboard update."); };
    $("#load-example").addEventListener("click", loadExample);
    $("#flags").addEventListener("click", (e) => {
      if (e.target.closest("[data-action=example]")) {
        if (OPTS.onLoadExample) OPTS.onLoadExample(); else loadExample();
        return;
      }
      const id = e.target.closest("[data-goto]")?.dataset.goto;
      if (id) (OPTS.onGotoField || gotoField)(id);
    });
    $("#clear-inputs").addEventListener("click", () => {
      const filled = Object.values(readValues().v).filter(has).length;
      if (filled && !window.confirm(`Clear all ${filled} inputs? Export them first if you want to keep them.`)) return;
      writeValues({});
      update();
      status("Inputs cleared.");
    });

    // Changing a unit converts the value already entered.
    $("#input-sections").addEventListener("change", (e) => {
      const sel = e.target.closest(".unit-select");
      if (!sel) return;
      const f = FIELDS[sel.dataset.field];
      const input = $(`#f-${CSS.escape(f.id)}`);
      const prev = UNITS[f.units].find((u) => u.unit === sel.dataset.prev) || UNITS[f.units][0];
      const next = UNITS[f.units].find((u) => u.unit === sel.value);
      if (input.value !== "" && isFinite(Number(input.value))) input.value = tidy(next.fromBase(prev.toBase(Number(input.value))));
      sel.dataset.prev = next.unit;
      unitPrefs[f.id] = next.unit;
      save(STORE.units, unitPrefs);
    });

    $("#export").addEventListener("click", () => {
      exportJSON();
      status("Exported. Use Import to load this file again later.");
    });
    $("#import-file").addEventListener("change", (e) => {
      const file = e.target.files[0];
      e.target.value = "";
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const data = JSON.parse(String(reader.result));
          const inputs = data && typeof data.inputs === "object" ? data.inputs : data;
          const known = Object.keys(inputs || {}).filter((k) => FIELDS[k]);
          if (!known.length) throw new Error("no recognised inputs");
          writeValues(Object.fromEntries(known.map((k) => [k, inputs[k]])));
          update();
          status(`Imported ${known.length} inputs from ${file.name}.`);
        } catch {
          status(`${file.name} is not an export from this dashboard.`);
        }
      };
      reader.readAsText(file);
    });

    // Phone layout: a bar that jumps between the inputs and the results.
    const bar = $("#results-bar");
    let resultsVisible = false;
    let observer = null;
    if ("IntersectionObserver" in window) {
      observer = new IntersectionObserver(([entry]) => {
        resultsVisible = entry.isIntersecting;
        $("#results-bar-action").textContent = resultsVisible ? "Edit inputs ↑" : "View results ↓";
      }, { threshold: 0.15 });
      observer.observe($("#results"));
    }
    bar.addEventListener("click", () => {
      const target = resultsVisible ? $("#inputs") : $("#results");
      target.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
    });

    $("#acme-fuel").addEventListener("change", (e) => { acmeFilter = e.target.value; update(); });
    $("#composition-card").addEventListener("click", (e) => {
      const unit = e.target.closest("[data-comp-unit]")?.dataset.compUnit;
      if (!unit || unit === compUnit) return;
      compUnit = unit;
      save(STORE.compUnit, compUnit);
      update();
    });

    $("#dataset-file").addEventListener("change", (e) => {
      for (const f of e.target.files) addDataset(f);
      e.target.value = "";
    });
    $("#datasets").addEventListener("change", (e) => {
      const k = e.target.dataset.ds;
      if (k === undefined) return;
      userDatasets[k][e.target.dataset.axis] = Number(e.target.value);
      save(STORE.datasets, userDatasets);
      renderDatasets();
    });
    $("#datasets").addEventListener("click", (e) => {
      const k = e.target.dataset.removeDs;
      if (k === undefined) return;
      userDatasets.splice(Number(k), 1);
      save(STORE.datasets, userDatasets);
      renderDatasets();
    });

    let resizeTimer;
    const onResize = () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { update(); renderDatasets(); }, 200); };
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      if (observer) observer.disconnect();
      clearTimeout(resizeTimer);
      clearTimeout(timer);
      window.Charts.removeTooltip();
    };
  }

  // Download the inputs (base units) and the current assessment as JSON.
  function exportJSON() {
    const { v, result } = update();
    const baseUnits = Object.fromEntries(allFields().filter((f) => f.type === "number").map((f) => [f.id, f.units ? UNITS[f.units][0].unit : f.unit]));
    const blob = new Blob([JSON.stringify({
      exported: new Date().toISOString(), inputs: v, units: baseUnits,
      assessment: result.flags.map((f) => ({ level: f.level, title: f.title, detail: f.detail.replace(/<[^>]+>/g, "") })),
    }, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `fire-safety-inputs-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  // External mode: replace the input values (base units) and refresh.
  function setInputs(values) {
    externalValues = values || {};
    if (cleanup) scheduleUpdate();
  }

  let cleanup = null;

  /**
   * Start the dashboard inside `root`, which must already contain the markup
   * from index.html. Options:
   *   embedded: true  - show the page title as a smaller h2 (the host page has its own h1)
   *   title: string   - replacement title text when embedded; "" removes the title
   *   externalInputs: true - hide the dashboard's form; values come from
   *                   options.inputs and FireDashboard.setInputs (base units)
   *   subtitle: string - replacement intro line
   *   onGotoField(id), onLoadExample() - host handlers for assessment links
   */
  function mount(root = document, options = {}) {
    if (cleanup) cleanup();
    ROOT = root;
    OPTS = options;
    if (options.externalInputs) {
      externalValues = options.inputs || {};
      $(".layout").classList.add("external");
      $(".page-header").classList.add("external");
      $("#results-bar").style.display = "none";
    }
    if (options.subtitle) {
      const sub = $(".page-header .subtitle");
      if (sub) sub.textContent = options.subtitle;
    }
    window.Charts.setTooltipHost(root === document ? document.body : root);
    if (options.embedded) {
      const h1 = $(".page-header h1");
      if (h1 && options.title === "") {
        h1.remove();
      } else if (h1) {
        const h2 = document.createElement("h2");
        h2.className = "embedded-title";
        h2.textContent = options.title || h1.textContent;
        h1.replaceWith(h2);
      }
    }
    cleanup = init();
    return () => { if (cleanup) { cleanup(); cleanup = null; } };
  }

  window.FireDashboard = { mount, setInputs, exportJSON };
  // Pure functions exposed for the regression tests in tests/.
  window.FireDashboard._test = { assess, smokeStatus };

  // Standalone page: mount when the dashboard markup is in the document itself.
  const autoMount = () => { if (document.getElementById("input-sections")) mount(document); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", autoMount);
  else autoMount();
})();
