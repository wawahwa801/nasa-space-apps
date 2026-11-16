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

  const KPA_PER_MMHG = 0.133322;
  const KPA_PER_PSI = 6.894757;

  /** Inspired O₂ partial pressure (mmHg): PIO₂ = (Pb − PH₂O) × FiO₂. */
  function inspiredO2(o2_pct, pressure_kpa, H) {
    if (num(o2_pct) === null || num(pressure_kpa) === null) return null;
    return Math.max(0, pressure_kpa / KPA_PER_MMHG - H.water_vapour_mmhg) * (o2_pct / 100);
  }

  /**
   * Is the air habitable for the crew? NASA-STD-3001 limits from T.habitable
   * (OCHMO-TB-003): total pressure, inspired O₂ (PIO₂) and inert diluent gas.
   * Either value may be null. Returns [{ level, title, detail, field }], where
   * "critical" / "serious" mean unsafe, "warning" unhealthy and "good" within limits.
   */
  function habitableAtmosphere(o2_pct, pressure_kpa, T) {
    const H = T.habitable;
    const out = [];
    if (!H) return out;
    const add = (level, title, detail, field) => out.push({ level, title, detail, field });
    const o2 = num(o2_pct), p = num(pressure_kpa);
    const mmHg = (kpa) => Math.round(kpa / KPA_PER_MMHG);
    let pressureOk = null, pio2Ok = null, diluentOk = null;

    if (p !== null) {
      const { min, max } = H.pressure_kpa;
      pressureOk = p > min && p <= max;
      if (p <= H.ebullism_kpa) {
        add("critical", "Pressure low enough for body fluids to boil",
          `Pressure is ${r1(p)} kPa, at or below ${H.ebullism_kpa} kPa where body fluids vaporise at body temperature (ebullism). Unsurvivable without a pressure suit.`, "pressure_kpa");
      } else if (p < H.supplemental_o2_min_kpa) {
        add("critical", "Pressure too low even for supplemental oxygen",
          `Pressure is ${r1(p)} kPa (${mmHg(p)} mmHg), below ${H.supplemental_o2_min_kpa} kPa (130 mmHg) where oxygen masks may not keep the crew conscious. Pressure suits are needed.`, "pressure_kpa");
      } else if (p <= min) {
        add("serious", "Cabin pressure below NASA's safe range",
          `Pressure is ${r1(p)} kPa. NASA-STD-3001 [V2 6006] allows ${min}–${max} kPa for indefinite crew exposure.`, "pressure_kpa");
      } else if (p > max) {
        add("warning", "Cabin pressure above NASA's indefinite-exposure range",
          `Pressure is ${r1(p)} kPa, above ${max} kPa ([V2 6006]). Limit how long the crew is exposed.`, "pressure_kpa");
      }
    }

    if (o2 !== null) {
      const maxO2 = 100 - H.min_diluent_pct;
      diluentOk = o2 <= maxO2;
      if (!diluentOk) {
        add("warning", "Too little inert gas in the cabin air",
          `O₂ is ${r1(o2)}%, leaving ${r1(100 - o2)}% inert (diluent) gas. NASA requires at least ${H.min_diluent_pct}% ([V2 6002]): without it, long exposures can collapse lung air sacs (atelectasis) and fires burn more easily.`, "o2_pct");
      }
    }

    if (o2 !== null && p !== null && p > H.ebullism_kpa) {
      const pio2 = inspiredO2(o2, p, H);
      const L = H.pio2_mmhg;
      const shown = Math.round(pio2);
      pio2Ok = pio2 >= L.exploration_min;
      if (pio2 < L.absolute_min) {
        add("serious", "Unsafe oxygen level: crew at risk of hypoxia",
          `Inspired O₂ (PIO₂) is about ${shown} mmHg, below NASA's absolute minimum of ${L.absolute_min} mmHg ([V2 6003]). Expect impaired thinking and vision, then loss of consciousness. Use supplemental oxygen and restore pressure or O₂.`, "o2_pct");
      } else if (pio2 < L.exploration_min) {
        add("warning", "Unhealthy oxygen level: mild hypoxia",
          `Inspired O₂ (PIO₂) is about ${shown} mmHg, below ${L.exploration_min} mmHg. NASA allows ${L.absolute_min}–${L.exploration_min} mmHg only as a 1-hour average; expect fatigue, headache and slower thinking.`, "o2_pct");
      } else if (pio2 < L.normoxia * (1 - H.normoxia_tolerance)) {
        add("info", "Mildly reduced oxygen (within NASA's exploration range)",
          `Inspired O₂ (PIO₂) is about ${shown} mmHg vs ${L.normoxia} mmHg in sea-level air. NASA accepts down to ${L.exploration_min} mmHg with a crew health monitoring plan.`, "o2_pct");
      }
    }

    if (pressureOk && pio2Ok && diluentOk) {
      add("good", "Breathable: pressure and oxygen within NASA's habitable limits",
        `Pressure ${r1(p)} kPa and inspired O₂ about ${Math.round(inspiredO2(o2, p, H))} mmHg (NASA-STD-3001). Humidity, temperature and CO₂ are checked separately.`, "pressure_kpa");
    }
    return out;
  }

  /**
   * Fastest pressure change between consecutive readings, checked against
   * [V2 6007]: changes > 1 psi must not exceed 13.5 psi/min. Returns an event or null.
   * Readings minutes apart only show an average rate, which can hide brief faster changes.
   */
  function pressureRateEvent(rs, T) {
    const R = T.habitable && T.habitable.pressure_rate;
    if (!R) return null;
    const ps = rs.filter((r) => num(r.pressure_kpa) !== null);
    let worst = null;
    for (let i = 1; i < ps.length; i++) {
      const dPsi = Math.abs(ps[i].pressure_kpa - ps[i - 1].pressure_kpa) / KPA_PER_PSI;
      const min = (ps[i].t - ps[i - 1].t) / 60000;
      if (min <= 0 || dPsi <= R.applies_above_psi) continue;
      const rate = dPsi / min;
      if (rate > R.max_psi_per_min && (!worst || rate > worst.rate)) worst = { rate, dPsi, min };
    }
    if (!worst) return null;
    return { level: "serious", title: "Pressure changing faster than NASA's limit",
      detail: `Pressure changed ${r1(worst.dPsi)} psi in ${r1(worst.min)} min (${r1(worst.rate)} psi/min). NASA-STD-3001 [V2 6007] allows at most ${R.max_psi_per_min} psi/min for changes over ${R.applies_above_psi} psi; fast changes risk ear and lung injury (barotrauma) and decompression sickness.`,
      field: "pressure_kpa" };
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
    // Flammable gas and oxygen levels in the latest reading.
    for (const [id, gas, name] of [["h2_ppm", "h2", "Hydrogen"], ["ch4_ppm", "ch4", "Methane"]]) {
      const x = latest[id];
      if (x === null) continue;
      const share = x / (T.lfl_pct[gas] * 10000);
      if (share >= T.lfl_critical_share) add("critical", `${name} near flammable concentration`, `${name} is ${Math.round(x)} ppm, ${r1(share * 100)}% of its lower flammability limit.`, id);
      else if (share >= T.lfl_warning_share) add("warning", `${name} elevated`, `${name} is ${Math.round(x)} ppm, ${r1(share * 100)}% of its lower flammability limit.`, id);
    }
    const o2Now = latest.o2_pct;
    if (o2Now !== null && T.o2_enriched_pct && o2Now > T.o2_enriched_pct) add("serious", "Oxygen-enriched air", `O₂ is ${r1(o2Now)}%, above ${T.o2_enriched_pct}%: materials ignite more easily and burn faster.`, "o2_pct");
    else if (o2Now !== null && T.o2_deficient_pct && o2Now < T.o2_deficient_pct) add("warning", "Oxygen-deficient air", `O₂ is ${r1(o2Now)}%, below ${T.o2_deficient_pct}%.`, "o2_pct");
    if (co2 !== null && co2 > T.co2_ppm.serious) add("serious", "Carbon dioxide above the NIOSH short-term limit", `CO₂ is ${Math.round(co2)} ppm.`, "co2_ppm");
    else if (co2 !== null && co2 > T.co2_ppm.warning) add("warning", "Carbon dioxide above the NIOSH exposure limit", `CO₂ is ${Math.round(co2)} ppm.`, "co2_ppm");
    // Habitable atmosphere (NASA-STD-3001): unsafe / unhealthy pressure and oxygen.
    for (const e of habitableAtmosphere(latest.o2_pct, latest.pressure_kpa, T)) {
      if (e.level !== "good") add(e.level, e.title, e.detail, e.field);
    }

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

      // Pressure: NASA rate-of-change limit, and time until it leaves the safe range.
      const rateEvent = pressureRateEvent(rs, T);
      if (rateEvent) add(rateEvent.level, rateEvent.title, rateEvent.detail, rateEvent.field);
      const p = latest.pressure_kpa, pRate = rates.pressure_kpa, H = T.habitable;
      if (H && p !== null && pRate !== null && pRate < 0 && p > H.pressure_kpa.min) {
        const minutes = ((p - H.pressure_kpa.min) / -pRate) * M.interval_min;
        if (minutes <= 60) add(minutes <= 15 ? "warning" : "info", `Pressure could fall below ${H.pressure_kpa.min} kPa in about ${Math.max(1, Math.round(minutes))} min`,
          `Pressure ${show(pRate, "kPa")} ${per}. Below ${H.pressure_kpa.min} kPa is outside NASA's safe range for the crew; check for a leak.`, "pressure_kpa");
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

  // Demo scenarios: 12 readings each. Synthetic numbers for demonstrations and
  // testing, not NASA measurements. Each step is [CO ppm, CO₂ ppm, O₂ %, temp °C, H₂ ppm].
  const DEMOS = {
    flaming: {
      label: "Smouldering turning into flames",
      summary: "steady air, then CO rises without heat (smouldering), then heat and CO₂ jump (flames)",
      steps: [
        [1, 450, 20.9, 22.0, 0.5], [1, 455, 20.9, 22.0, 0.5], [1.2, 450, 20.9, 22.1, 0.5], [1.1, 460, 20.9, 22.0, 0.5],
        [4, 470, 20.9, 22.1, 0.5], [9, 490, 20.9, 22.2, 0.5], [16, 520, 20.9, 22.3, 0.5], [26, 620, 20.85, 22.6, 0.5],
        [45, 1100, 20.6, 24, 0.5], [95, 2400, 20.1, 31, 0.5], [190, 4800, 19.4, 46, 0.5], [320, 7500, 18.6, 68, 0.5],
      ],
    },
    smoulder: {
      label: "Smouldering with no flame",
      summary: "CO climbs steadily for an hour with little heat or CO₂: something is smouldering",
      steps: [
        [1, 450, 20.9, 22.0, 0.5], [1.1, 452, 20.9, 22.0, 0.5], [1, 455, 20.9, 22.0, 0.5], [3, 465, 20.9, 22.1, 0.5],
        [8, 480, 20.9, 22.1, 0.5], [14, 500, 20.9, 22.2, 0.5], [21, 520, 20.89, 22.3, 0.5], [28, 545, 20.88, 22.4, 0.5],
        [40, 580, 20.87, 22.5, 0.5], [65, 640, 20.85, 22.7, 0.5], [100, 720, 20.82, 22.9, 0.5], [150, 820, 20.8, 23.2, 0.5],
      ],
    },
    leak: {
      label: "Oxygen and hydrogen leak",
      summary: "no combustion gases, but O₂ and H₂ build up: a leak that makes a fire more likely",
      steps: [
        [1, 450, 20.9, 22.0, 0.5], [1, 452, 20.9, 22.0, 0.5], [1, 450, 21.2, 22.0, 50], [1, 455, 22.0, 22.0, 1500],
        [1, 452, 22.9, 22.0, 4000], [1, 455, 23.8, 22.0, 7000], [1.1, 450, 24.7, 22.1, 10500], [1, 455, 25.6, 22.0, 14000],
        [1, 452, 26.5, 22.0, 18000], [1, 450, 27.4, 22.1, 22000], [1, 455, 28.3, 22.0, 26000], [1.1, 452, 29.2, 22.0, 30000],
      ],
    },
  };

  // Readings for one demo, ending at about `start + 11 intervals`.
  function demoSequence(start = Date.now() - 11 * 5 * 60000, intervalMin = 5, id = "flaming") {
    const demo = DEMOS[id] || DEMOS.flaming;
    return demo.steps.map(([co, co2, o2, temp, h2], i) => ({
      t: start + i * intervalMin * 60000,
      co_ppm: co, co2_ppm: co2, o2_pct: o2, internal_temp_c: temp,
      humidity_pct: 45, h2_ppm: h2, ch4_ppm: 1.9, pressure_kpa: 101.3,
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

  window.Monitoring = { FIELDS, DEMOS, detect, demoSequence, parseReadingsCsv, normalise, ratePerInterval, bassCoRatios, observedCoRatio, suspectMaterials, habitableAtmosphere, inspiredO2 };
})();
