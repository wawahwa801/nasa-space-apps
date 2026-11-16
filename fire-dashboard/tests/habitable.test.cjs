// Tests for NASA-STD-3001 habitable-atmosphere checks (OCHMO-TB-003):
// total pressure, inspired O₂ (PIO₂), inert diluent gas and rate of pressure change.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');

const context = vm.createContext({
  localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  matchMedia: () => ({ matches: false }),
  document: { readyState: 'complete', getElementById: () => null, addEventListener() {} },
  console,
});
context.window = context;
for (const file of ['../data/reference-data.js', '../js/parameters.js', '../js/charts.js', '../js/monitoring.js', '../js/app.js']) {
  vm.runInContext(readFileSync(require.resolve(file), 'utf8'), context, { filename: file });
}
const T = context.THRESHOLDS;
const { habitableAtmosphere, inspiredO2, detect } = context.Monitoring;
const { assess } = context.FireDashboard._test;
const check = (o2, p) => habitableAtmosphere(o2, p, T);
const levels = (events) => Array.from(events, (e) => e.level);
const find = (events, re) => events.find((e) => re.test(e.title));
const MIN = 60000;

test('PIO2 follows (Pb - 47 mmHg) x FiO2 from the brief', () => {
  // Brief's worked example: 760 mmHg, 21 % -> 149.7 mmHg.
  assert.ok(Math.abs(inspiredO2(21, 760 * 0.133322, T.habitable) - 149.7) < 0.1);
});

test('sea-level cabin air is breathable, with no warning', () => {
  const e = check(20.9, 101.3);
  assert.deepEqual(levels(e), ['good']);
  assert.match(e[0].title, /Breathable/);
});

test("NASA's 56.5 kPa / 34 % exploration atmosphere is mildly reduced but acceptable", () => {
  const e = check(34, 56.5); // PIO2 ≈ 128 mmHg
  assert.ok(find(e, /Mildly reduced oxygen/));
  assert.ok(!e.some((x) => ['warning', 'serious', 'critical'].includes(x.level)));
  assert.ok(find(e, /Breathable/));
});

test('hypoxia: below 127 mmHg is unhealthy, below 122 mmHg unsafe', () => {
  const mild = check(17.5, 101.3);   // ≈ 124.7 mmHg
  assert.equal(find(mild, /oxygen level/).level, 'warning');
  assert.match(find(mild, /oxygen level/).title, /Unhealthy/);
  const low = check(17, 101.3);      // ≈ 121.2 mmHg
  assert.equal(find(low, /oxygen level/).level, 'serious');
  assert.match(find(low, /oxygen level/).title, /Unsafe/);
  assert.ok(!find(low, /Breathable/));
});

test('total pressure bands from [V2 6006], supplemental O2 and ebullism', () => {
  assert.equal(find(check(21, 110), /above NASA/).level, 'warning');
  assert.equal(find(check(60, 30), /below NASA's safe range/).level, 'serious');
  assert.equal(find(check(100, 15), /supplemental oxygen/).level, 'critical');
  const vac = check(100, 5);
  assert.equal(find(vac, /body fluids/).level, 'critical');
  assert.ok(!find(vac, /oxygen level/), 'no PIO2 verdict below ebullism pressure');
  assert.ok(!find(check(21, 34.5), /Breathable/), '34.5 kPa itself is outside the range (P > 34.5)');
  assert.ok(find(check(21, 103), /Breathable/), '103 kPa is inside the range (P ≤ 103)');
});

test('at least 30 % inert diluent gas [V2 6002]', () => {
  assert.equal(find(check(75, 40), /inert gas/).level, 'warning');
  assert.ok(!find(check(70, 40), /inert gas/));
});

test('#85: high PIO2 is never "Breathable"; upper exposure is marked not checked', () => {
  const e = check(70, 101.3); // PIO2 ≈ 499 mmHg
  assert.ok(!find(e, /Breathable/));
  assert.equal(find(e, /upper exposure limits not checked/).level, 'info');
  assert.ok(!find(check(22, 101.3), /Breathable/), '≈157 mmHg is above the sea-level band');
  assert.ok(find(check(21, 101.3), /Breathable/), 'sea-level air still passes');
  const r = assess({ o2_pct: 70, pressure_kpa: 101.3 });
  assert.ok(!r.flags.some((f) => /Breathable/.test(f.title)));
});

test('missing values give no verdict', () => {
  assert.equal(check(null, null).length, 0);
  assert.ok(!find(check(21, null), /Breathable/));
});

test('assessment includes the habitable-atmosphere flags; vacuum skips pressure checks', () => {
  const r = assess({ o2_pct: 17, pressure_kpa: 101.3 });
  assert.ok(r.flags.some((f) => /Unsafe oxygen level/.test(f.title) && f.level === 'serious'));
  const v = assess({ environment: 'Vacuum', o2_pct: 21, pressure_kpa: 0 });
  assert.ok(!v.flags.some((f) => /body fluids|pressure/i.test(f.title) && f.field === 'pressure_kpa' && f.level !== 'info'));
});

test('a normal O2 % at low pressure is not called "normal" next to a hypoxia flag', () => {
  const r = assess({ o2_pct: 21, pressure_kpa: 30 });
  assert.ok(r.flags.some((f) => /Unsafe oxygen level/.test(f.title)));
  assert.ok(!r.flags.some((f) => /Oxygen concentration in normal range/.test(f.title)));
  assert.ok(assess({ o2_pct: 20.9, pressure_kpa: 101.3 }).flags.some((f) => /Oxygen concentration in normal range/.test(f.title)));
});

const base = { co_ppm: 1, co2_ppm: 450, o2_pct: 20.9, internal_temp_c: 22, humidity_pct: 45, h2_ppm: 0.5, ch4_ppm: 1.9, pressure_kpa: 101.3 };

test('live monitoring flags unsafe latest air but stays quiet for normal air', () => {
  const ok = [0, 1, 2].map((i) => ({ t: i * 5 * MIN, ...base }));
  const quiet = detect(ok, T, ok[2].t + MIN);
  assert.equal(quiet.level, 'good');
  assert.ok(!quiet.events.some((e) => e.field === 'pressure_kpa'));

  const low = [0, 1].map((i) => ({ t: i * 5 * MIN, ...base, pressure_kpa: 30 }));
  const r = detect(low, T, low[1].t + MIN);
  assert.equal(r.level, 'serious');
  assert.ok(r.events.some((e) => /below NASA's safe range/.test(e.title)));
});

test('rate of pressure change above 13.5 psi/min is flagged [V2 6007]', () => {
  const fast = [{ t: 0, ...base }, { t: MIN, ...base, pressure_kpa: 101.3 - 14 * 6.894757 }]; // 14 psi in 1 min
  assert.ok(detect(fast, T, fast[1].t + 1000).events.some((e) => /faster than NASA's limit/.test(e.title)));
  const slow = [{ t: 0, ...base }, { t: 5 * MIN, ...base, pressure_kpa: 101.3 - 2 * 6.894757 }]; // 2 psi in 5 min
  assert.ok(!detect(slow, T, slow[1].t + 1000).events.some((e) => /faster than NASA's limit/.test(e.title)));
});

test('falling pressure projects when it will leave the safe range', () => {
  const rs = [0, 1, 2].map((i) => ({ t: i * 5 * MIN, ...base, pressure_kpa: 50 - i * 4 })); // 4 kPa per 5 min, now 42 kPa
  const r = detect(rs, T, rs[2].t + MIN);
  const e = r.events.find((x) => /could fall below 34.5 kPa/.test(x.title));
  assert.ok(e, 'projection present');
  assert.equal(e.level, 'warning'); // (42 - 34.5) / 4 * 5 ≈ 9 min
});
