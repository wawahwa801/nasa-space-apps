// Tests for live-monitoring change detection (js/monitoring.js).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');

const context = vm.createContext({});
context.window = context;
for (const file of ['../data/reference-data.js', '../js/parameters.js', '../js/monitoring.js']) {
  vm.runInContext(readFileSync(require.resolve(file), 'utf8'), context, { filename: file });
}
const { detect, demoSequence, parseReadingsCsv } = context.Monitoring;
const T = context.THRESHOLDS;
const MIN = 60000;
const base = { co2_ppm: 450, o2_pct: 20.9, internal_temp_c: 22, humidity_pct: 45, h2_ppm: 0.5, ch4_ppm: 1.9, pressure_kpa: 101.3 };
const series = (rows) => rows.map((r, i) => ({ t: i * 5 * MIN, ...base, ...r }));
const run = (rs) => detect(rs, T, rs[rs.length - 1].t + MIN);
const titles = (r) => r.events.map((e) => e.title);

test('no readings, then one reading: asks for more data', () => {
  assert.equal(detect([], T).level, null);
  const one = run(series([{ co_ppm: 1 }]));
  assert.ok(titles(one).includes('Need at least two readings to detect changes'));
});

test('steady cabin air gives no fire indicators (no false alarm)', () => {
  const r = run(series([{ co_ppm: 1 }, { co_ppm: 1.2 }, { co_ppm: 1.1 }, { co_ppm: 1 }]));
  assert.equal(r.level, 'good');
  assert.match(r.headline, /No fire or smoke indicators/);
});

test('CO rising for several intervals without heat is flagged as smouldering', () => {
  const r = run(series([{ co_ppm: 1 }, { co_ppm: 8 }, { co_ppm: 16 }, { co_ppm: 25 }]));
  assert.equal(r.level, 'serious');
  assert.equal(r.headline, 'Possible smouldering or overheating');
  assert.ok(r.events.some((e) => /CO could reach 35 ppm/.test(e.title)));
});

test('CO and CO2 rising with O2 falling is a combustion signature', () => {
  const r = run(series([{ co_ppm: 2 }, { co_ppm: 12, co2_ppm: 800, o2_pct: 20.6 }]));
  assert.equal(r.headline, 'Combustion signature: CO and CO₂ rising together');
});

test('fast temperature rise with combustion gases is a possible flaming fire', () => {
  const r = run(series([{ co_ppm: 20, internal_temp_c: 25 }, { co_ppm: 60, co2_ppm: 1500, internal_temp_c: 40 }]));
  assert.equal(r.level, 'critical');
  assert.equal(r.headline, 'Possible flaming fire');
});

test('rates are scaled to the monitoring interval, not per reading', () => {
  // +10 ppm over 10 minutes is +5 ppm per 5-minute interval: exactly the warning rise.
  const rs = [{ t: 0, co_ppm: 1 }, { t: 10 * MIN, co_ppm: 11 }];
  const r = detect(rs, T, 11 * MIN);
  assert.equal(r.rates.co_ppm, 5);
  assert.equal(r.headline, 'Carbon monoxide rising');
});

test('flammable gas accumulating and oxygen rising are flagged', () => {
  const r = run(series([{ co_ppm: 1, h2_ppm: 0.5, o2_pct: 20.9 }, { co_ppm: 1, h2_ppm: 2500, o2_pct: 21.6 }]));
  assert.ok(titles(r).includes('Hydrogen accumulating'));
  assert.ok(titles(r).includes('Oxygen rising'));
});

test('a missed reading is reported as a monitoring gap', () => {
  const rs = series([{ co_ppm: 1 }, { co_ppm: 1 }]);
  const r = detect(rs, T, rs[1].t + 30 * MIN);
  assert.ok(r.events.some((e) => /No new reading for 30 min/.test(e.title)));
});

test('the demo sequence escalates from no indicators to a possible flaming fire', () => {
  const seq = demoSequence(0, 5);
  const at = (n) => detect(seq.slice(0, n), T, seq[n - 1].t + MIN);
  assert.equal(at(4).level, 'good');
  assert.equal(at(7).headline, 'Possible smouldering or overheating');
  assert.equal(at(12).level, 'critical');
});

test('CSV import maps columns by name and times in minutes', () => {
  const cols = ['minutes', 'CO (ppm)', 'CO2 (ppm)', 'O2 (%)', 'Temperature (C)'];
  const rows = [['0', '1', '450', '20.9', '22'], ['5', '9', '700', '20.7', '23'], ['', '5', '', '', '']];
  const out = parseReadingsCsv(rows, cols, 0);
  assert.equal(out.length, 2);
  assert.deepEqual({ ...out[1] }, { t: 5 * MIN, co_ppm: 9, co2_ppm: 700, o2_pct: 20.7, internal_temp_c: 23 });
  assert.throws(() => parseReadingsCsv([['1']], ['co'], 0), /No time column/);
});

test('which listed material could be burning: smouldering favours cotton, flaming favours PMMA', () => {
  const { suspectMaterials, bassCoRatios } = context.Monitoring;
  const ratios = bassCoRatios(context.REFERENCE_DATA.bass.tests);
  const profiles = context.SMOKE_PRODUCTS.materials;
  const listed = ['Teflon', 'PMMA (acrylic)', 'SIBAL fabric (cotton-fiberglass)'];
  const seq = demoSequence(0, 5);
  const rank = (n) => {
    const rs = seq.slice(0, n);
    return suspectMaterials(detect(rs, T, rs[n - 1].t + MIN), rs, listed, profiles, ratios);
  };
  const smoulder = rank(7);
  assert.equal(smoulder.pattern, 'smouldering');
  assert.equal(smoulder.items[0].material, 'SIBAL fabric (cotton-fiberglass)');
  const flaming = rank(12);
  assert.equal(flaming.pattern, 'flaming');
  assert.equal(flaming.items[0].material, 'PMMA (acrylic)');
  assert.ok(flaming.items[0].reasons.some((r) => /BASS-II/.test(r)));
  assert.equal(flaming.items.at(-1).material, 'Teflon');
  // No fire pattern, or nothing listed: no ranking.
  assert.equal(rank(3), null);
  assert.equal(suspectMaterials(detect(seq, T, seq[11].t + MIN), seq, [], profiles, ratios), null);
});
