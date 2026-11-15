// Live monitoring: detect fire and smoke indicators from readings taken over
// time (e.g. every 5 minutes). Pure functions only; app.js renders the result.
//
// A reading is { t: <ms since epoch>, co_ppm, co2_ppm, o2_pct, internal_temp_c,
// humidity_pct, h2_ppm, ch4_ppm, pressure_kpa } in the dashboard's base units.
// Thresholds come from THRESHOLDS.monitoring in parameters.js and are
// placeholders, not validated detection limits.

(function () {
  const FIELDS = [
    { id: "co_ppm", label: "Carbon monoxide (CO)", short: "CO", unit: "ppm" },
    { id: "co2_ppm", label: "Carbon dioxide (CO₂)", short: "CO₂", unit: "ppm" },
    { id: "o2_pct", label: "Oxygen (O₂)", short: "O₂", unit: "%" },
    { id: "internal_temp_c", label: "Temperature", short: "Temp", unit: "°C" },
    { id: "humidity_pct", label: "Relative humidity", short: "RH", unit: "%" },
    { id: "h2_ppm", label: "Hydrogen (H₂)", short: "H₂", unit: "ppm" },
    { id: "ch4_ppm", label: "Methane (CH₄)", short: "CH₄", unit: "ppm" },
    { id: "pressure_kpa", label: "Pressure", short: "P", unit: "kPa" },
  ];
  const RANK = { good: 0, info: 1, warning: 2, serious: 3, critical: 4 };
  const num = (x) => (typeof x === "number" && isFinite(x) ? x : null);
  const r1 = (x) => Math.round(x * 10) / 10;

  // Keep readings sorted by time and drop exact-duplicate timestamps (last wins).
  function normalise(readings) {
    const byTime = new Map();
    for (const r of readings || []) if (r && isFinite(r.t)) byTime.set(r.t, r);
    return [...byTime.values()].sort((a, b) => a.t - b.t);
  }

  // Change per monitoring interval between the last two readings that both have
  // a value for this field. Returns null when there aren't two such readings.
  function ratePerInterval(rs, id, intervalMin, end = rs.length) {
    let b = -1;
    for (let i = end - 1; i >= 0; i--) if (num(rs[i][id]) !== null) { b = i; break; }
    let a = -1;
    for (let i = b - 1; i >= 0; i--) if (num(rs[i][id]) !== null) { a = i; break; }
    if (a < 0 || b < 0) return null;
    const minutes = (rs[b].t - rs[a].t) / 60000;
    if (minutes <= 0) return null;
    return ((rs[b][id] - rs[a][id]) / minutes) * intervalMin;
  }

  // How many consecutive intervals (ending at the latest) this field rose by at least `min`.
  function risingStreak(rs, id, intervalMin, min) {
    let streak = 0;
    for (let end = rs.length; end >= 2; end--) {
      const rate = ratePerInterval(rs, id, intervalMin, end);
      if (rate === null || rate < min) break;
      streak++;
    }
    return streak;
  }

  function latestValue(rs, id) {
    for (let i = rs.length - 1; i >= 0; i--) if (num(rs[i][id]) !== null) return rs[i][id];
    return null;
  }

  /**
   * Detect fire / smoke indicators.
   * T: the full THRESHOLDS object (uses T.monitoring, T.co_ppm, T.co2_ppm, T.lfl_pct).
   * now: current time in ms (for the monitoring-gap check).
   * Returns { level, headline, pattern, events: [{ level, title, detail, field }], rates, count, latest }.
   * pattern: "flaming", "combustion", "smouldering", "co_rising" or null (no fire pattern).
   */
  function detect(readings, T, now = Date.now()) {
    const M = T.monitoring;
    const rs = normalise(readings);
    const events = [];
    const add = (level, title, detail, field) => events.push({ level, title, detail, field });
    const rates = Object.fromEntries(FIELDS.map((f) => [f.id, ratePerInterval(rs, f.id, M.interval_min)]));
    const latest = Object.fromEntries(FIELDS.map((f) => [f.id, latestValue(rs, f.id)]));
    const per = `per ${M.interval_min} min`;
    let pattern = null;

    if (rs.length === 0) {
      return { level: null, headline: "No readings yet", pattern, events, rates, count: 0, latest };
    }

    // Monitoring gap.
    const ageMin = (now - rs[rs.length - 1].t) / 60000;
    if (ageMin > M.interval_min * M.stale_after_intervals) {
      add("warning", `No new reading for ${Math.round(ageMin)} min`,
        `Readings are expected every ${M.interval_min} min. Changes since the last reading can't be detected.`, null);
    }

    // Exposure limits on the latest values (smoke and breathing hazard).
    const co = latest.co_ppm;
    const co2 = latest.co2_ppm;
    if (co !== null && co > T.co_ppm.serious) add("serious", "Carbon monoxide above the NIOSH ceiling", `CO is ${r1(co)} ppm (ceiling ${T.co_ppm.serious} ppm). Breathing hazard.`, "co_ppm");
    else if (co !== null && co > T.co_ppm.warning) add("warning", "Carbon monoxide above the NIOSH exposure limit", `CO is ${r1(co)} ppm (limit ${T.co_ppm.warning} ppm, 8-hour average).`, "co_ppm");
    if (co2 !== null && co2 > T.co2_ppm.serious) add("serious", "Carbon dioxide above the NIOSH short-term limit", `CO₂ is ${Math.round(co2)} ppm.`, "co2_ppm");
    else if (co2 !== null && co2 > T.co2_ppm.warning) add("warning", "Carbon dioxide above the NIOSH exposure limit", `CO₂ is ${Math.round(co2)} ppm.`, "co2_ppm");

    if (rs.length < 2) {
      add("info", "Need at least two readings to detect changes", `Record another reading in about ${M.interval_min} min.`, null);
    } else {
      const coRate = rates.co_ppm, co2Rate = rates.co2_ppm, o2Rate = rates.o2_pct, tRate = rates.internal_temp_c;
      const coUp = coRate !== null && coRate >= M.co_rise_ppm.warning;
      const co2Up = co2Rate !== null && co2Rate >= M.co2_rise_ppm;
      const o2Down = o2Rate !== null && o2Rate <= -M.o2_drop_pct;
      const tempUp = tRate !== null && tRate >= M.temp_rise_c.warning;
      const tempFast = tRate !== null && tRate >= M.temp_rise_c.serious;
      const coStreak = risingStreak(rs, "co_ppm", M.interval_min, M.co_rise_ppm.warning);
      const show = (x, unit) => `${x >= 0 ? "+" : ""}${r1(x)} ${unit}`;

      // Fire signatures, most specific first.
      if (tempFast && (co2Up || coUp)) {
        pattern = "flaming";
        add("critical", "Possible flaming fire",
          `Temperature ${show(tRate, "°C")} and ${co2Up ? `CO₂ ${show(co2Rate, "ppm")}` : `CO ${show(coRate, "ppm")}`} ${per}: rapid heating with combustion gases.`, "internal_temp_c");
      } else if (coUp && co2Up && (o2Down || tempUp)) {
        pattern = "combustion";
        add("serious", "Combustion signature: CO and CO₂ rising together",
          `CO ${show(coRate, "ppm")}, CO₂ ${show(co2Rate, "ppm")}${o2Down ? `, O₂ ${show(o2Rate, "%")}` : ""}${tempUp ? `, temperature ${show(tRate, "°C")}` : ""} ${per}. Something may be burning.`, "co_ppm");
      } else if (coUp && coStreak >= 2 && !tempUp) {
        pattern = "smouldering";
        add("serious", "Possible smouldering or overheating",
          `CO has risen for ${coStreak} intervals in a row (now ${show(coRate, "ppm")} ${per}) without much heat. Smouldering materials produce CO and smoke before flames.`, "co_ppm");
      } else if (coUp) {
        pattern = "co_rising";
        add(coRate >= M.co_rise_ppm.serious ? "serious" : "warning", "Carbon monoxide rising",
          `CO ${show(coRate, "ppm")} ${per}.`, "co_ppm");
      } else if (tempUp) {
        add("warning", "Temperature rising", `Temperature ${show(tRate, "°C")} ${per}.`, "internal_temp_c");
      }

      // Projection: time until CO reaches the next limit at the current rate.
      if (co !== null && coRate !== null && coRate > 0) {
        const next = co < T.co_ppm.warning ? T.co_ppm.warning : co < T.co_ppm.serious ? T.co_ppm.serious : null;
        if (next !== null) {
          const minutes = ((next - co) / coRate) * M.interval_min;
          if (minutes <= 60) add(minutes <= 15 ? "warning" : "info", `CO could reach ${next} ppm in about ${Math.max(1, Math.round(minutes))} min`,
            `At the current rise of ${r1(coRate)} ppm ${per}.`, "co_ppm");
        }
      }

      // Flammable gases accumulating.
      for (const [id, gas, name] of [["h2_ppm", "h2", "Hydrogen"], ["ch4_ppm", "ch4", "Methane"]]) {
        const rate = rates[id];
        const lfl = T.lfl_pct[gas] * 10000;
        if (rate !== null && rate / lfl >= M.lfl_share_rise) {
          add("serious", `${name} accumulating`, `${name} ${show(rate, "ppm")} ${per} (${r1((rate / lfl) * 100)}% of its flammability limit each interval). Possible leak.`, id);
        }
      }

      // Oxygen rising: possible oxidizer leak.
      if (o2Rate !== null && o2Rate >= M.o2_rise_pct) {
        add("warning", "Oxygen rising", `O₂ ${show(o2Rate, "%")} ${per}. Possible oxygen or oxidizer leak; materials burn more readily.`, "o2_pct");
      }
    }

    events.sort((a, b) => RANK[b.level] - RANK[a.level]);
    const top = events.find((e) => e.level !== "info");
    const level = top ? top.level : rs.length >= 2 ? "good" : "info";
    const headline = top ? top.title : rs.length >= 2 ? "No fire or smoke indicators in recent readings" : "Need at least two readings";
    return { level, headline, pattern, events, rates, count: rs.length, latest };
  }

  // Measured CO rise per unit of CO₂ rise (both ppm) in BASS-II burns, by
  // material category: { category: { median, min, max, n } }.
  function bassCoRatios(tests) {
    const by = {};
    for (const t of tests || []) {
      if (!(t.co_rise_ppm > 0) || !(t.co2_rise_pct > 0)) continue;
      (by[t.category] = by[t.category] || []).push(t.co_rise_ppm / (t.co2_rise_pct * 10000));
    }
    const out = {};
    for (const [cat, xs] of Object.entries(by)) {
      xs.sort((a, b) => a - b);
      const m = xs.length % 2 ? xs[(xs.length - 1) / 2] : (xs[xs.length / 2 - 1] + xs[xs.length / 2]) / 2;
      out[cat] = { median: m, min: xs[0], max: xs[xs.length - 1], n: xs.length };
    }
    return out;
  }

  // CO rise / CO₂ rise (ppm/ppm) between the first and latest readings that
  // have both, or null when CO₂ hasn't risen enough to divide by.
  function observedCoRatio(readings, minCo2RisePpm = 50) {
    const rs = normalise(readings).filter((r) => num(r.co_ppm) !== null && num(r.co2_ppm) !== null);
    if (rs.length < 2) return null;
    const a = rs[0], b = rs[rs.length - 1];
    const dCo = b.co_ppm - a.co_ppm, dCo2 = b.co2_ppm - a.co2_ppm;
    if (dCo2 < minCo2RisePpm || dCo <= 0) return null;
    return dCo / dCo2;
  }

  /**
   * Rank the materials listed as present by how well each fits the detected
   * fire pattern. Indicative only: it uses each material's typical behaviour
   * (profiles[m].behaviour, general knowledge) and, where BASS-II measured it,
   * the CO/CO₂ ratio of its burns.
   * Returns { pattern, ratio, items: [{ material, score, likelihood, reasons }] },
   * or null when there is no fire pattern or no materials.
   */
  function suspectMaterials(result, readings, materials, profiles, ratios) {
    if (!result || !result.pattern || !materials || !materials.length) return null;
    const smoulderLike = result.pattern === "smouldering" || result.pattern === "co_rising";
    const ratio = observedCoRatio(readings);
    const fit = smoulderLike
      ? { smoulders: [3, "can smoulder without a flame, giving off CO and smoke first"],
          chars: [1, "chars and smokes when overheated, but is hard to ignite"],
          flames: [0, "usually melts and burns with a flame rather than smouldering"],
          resists: [-1, "rarely burns in normal air; overheating gives fumes rather than much CO"] }
      : { flames: [3, "melts or vaporises and burns with a flame"],
          smoulders: [1, "can turn from smouldering into flames"],
          chars: [1, "can burn once well heated, though it is hard to ignite"],
          resists: [-1, "rarely burns in normal air"] };
    const items = materials.map((material) => {
      const reasons = [];
      let score = 0;
      const b = profiles[material] && profiles[material].behaviour;
      if (b && fit[b]) { score += fit[b][0]; reasons.push(`Typically ${fit[b][1]}.`); }
      const r = ratios[material];
      if (ratio !== null && r) {
        const sig = (x) => String(Number(x.toPrecision(2)));
        const shown = `${sig(ratio)} vs ${sig(r.min)}–${sig(r.max)} in ${r.n} BASS-II burn${r.n > 1 ? "s" : ""}`;
        if (ratio >= r.min && ratio <= r.max) { score += 2; reasons.push(`CO/CO₂ rise matches its burns (${shown}).`); }
        else if (ratio >= r.median / 2 && ratio <= r.median * 2) { score += 1; reasons.push(`CO/CO₂ rise is close to its burns (${shown}).`); }
        else reasons.push(`CO/CO₂ rise differs from its burns (${shown}).`);
      } else if (ratio !== null) {
        reasons.push("No BASS-II CO/CO₂ data to compare.");
      }
      const likelihood = score >= 4 ? "More likely" : score >= 2 ? "Possible" : "Less likely";
      return { material, score, likelihood, reasons };
    }).sort((a, b) => b.score - a.score || a.material.localeCompare(b.material));
    return { pattern: result.pattern, ratio, items };
  }

  // Illustrative scenario: steady cabin air, then smouldering, then flames.
  // Synthetic numbers for demonstrations, not NASA measurements.
  function demoSequence(start = Date.now() - 11 * 5 * 60000, intervalMin = 5) {
    const steps = [
      [1, 450, 20.9, 22.0], [1, 455, 20.9, 22.0], [1.2, 450, 20.9, 22.1], [1.1, 460, 20.9, 22.0],
      [4, 470, 20.9, 22.1], [9, 490, 20.9, 22.2], [16, 520, 20.9, 22.3], [26, 620, 20.85, 22.6],
      [40, 950, 20.7, 23.5], [70, 1400, 20.5, 27], [130, 2100, 20.2, 38], [210, 3200, 19.9, 52],
    ];
    return steps.map(([co, co2, o2, temp], i) => ({
      t: start + i * intervalMin * 60000,
      co_ppm: co, co2_ppm: co2, o2_pct: o2, internal_temp_c: temp,
      humidity_pct: 45, h2_ppm: 0.5, ch4_ppm: 1.9, pressure_kpa: 101.3,
    }));
  }

  // Parse a readings CSV. Needs a time column (ISO date/time, or minutes from the
  // start) and any of the gas/temperature columns, matched by name.
  function parseReadingsCsv(rows, columns, startMs = Date.now()) {
    const find = (re) => columns.findIndex((c) => re.test(c.toLowerCase()));
    const timeCol = find(/time|minute|date/);
    if (timeCol < 0) throw new Error("No time column (e.g. 'time' or 'minutes').");
    const map = {
      co2_ppm: find(/co2|co₂|carbon dioxide/),
      co_ppm: columns.findIndex((c) => /^\s*co\b|carbon monoxide|co[\s_(]*ppm/.test(c.toLowerCase()) && !/co2|co₂/.test(c.toLowerCase())),
      o2_pct: find(/(^|[^c])o2|o₂|oxygen/),
      internal_temp_c: find(/temp/),
      humidity_pct: find(/humid|\brh\b/),
      h2_ppm: find(/(^|[^c])h2\b|h₂|hydrogen/),
      ch4_ppm: find(/ch4|ch₄|methane/),
      pressure_kpa: find(/press/),
    };
    const out = [];
    for (const row of rows) {
      const rawT = (row[timeCol] || "").trim();
      if (!rawT) continue;
      const asNum = Number(rawT);
      const t = isFinite(asNum) ? startMs + asNum * 60000 : Date.parse(rawT);
      if (!isFinite(t)) continue;
      const reading = { t };
      for (const [id, col] of Object.entries(map)) {
        if (col < 0) continue;
        const v = Number((row[col] || "").trim());
        if ((row[col] || "").trim() !== "" && isFinite(v)) reading[id] = v;
      }
      out.push(reading);
    }
    if (!out.length) throw new Error("No rows with a usable time value.");
    return normalise(out);
  }

  window.Monitoring = { FIELDS, detect, demoSequence, parseReadingsCsv, normalise, ratePerInterval, bassCoRatios, observedCoRatio, suspectMaterials };
})();
