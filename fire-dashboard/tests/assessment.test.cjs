// Regression tests for assessment wording and smoke status (issues #39, #40).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');

function load() {
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
  return context.FireDashboard._test;
}

const { assess, smokeStatus } = load();
const bassFlag = (v) => assess(v).flags.find((f) => f.title.includes('BASS-II'));

test('#39: BASS-II O2 comparison describes the tested range, never a burning threshold', () => {
  const inside = bassFlag({ material_type: 'PMMA (acrylic)', o2_pct: 18 });
  assert.match(inside.title, /within the range BASS-II tested/);
  assert.equal(inside.level, 'info');

  const above = bassFlag({ material_type: 'PMMA (acrylic)', o2_pct: 30 });
  assert.match(above.title, /above the range BASS-II tested/);
  assert.match(above.detail, /no test data at your level/);

  const below = bassFlag({ material_type: 'PMMA (acrylic)', o2_pct: 10 });
  assert.match(below.title, /Below the lowest O₂ BASS-II tested/);
  assert.match(below.detail, /not evidence that the material cannot burn/);

  for (const f of [inside, above, below]) assert.doesNotMatch(f.detail, /could be sustained/);
});

test('#40: missing CO/CO2 readings with nominal monitoring are incomplete, not OK', () => {
  const s = smokeStatus({ monitoring: 'Nominal' });
  assert.equal(s.overall, 'unknown');
  assert.deepEqual([...s.missing], ['CO', 'CO₂']);
});

test('#40: known hazards still show when readings are missing', () => {
  assert.equal(smokeStatus({ monitoring: 'Offline' }).overall, 'serious');
  assert.equal(smokeStatus({ material_type: 'Teflon' }).overall, 'serious');
  assert.equal(smokeStatus({ co_ppm: 250 }).overall, 'serious');
});

test('#40: OK only when both readings are present and within limits', () => {
  assert.equal(smokeStatus({ co_ppm: 2, co2_ppm: 400, monitoring: 'Nominal' }).overall, 'good');
  assert.equal(smokeStatus({ co_ppm: 2, monitoring: 'Nominal' }).overall, 'unknown');
});

test('vacuum: the pressure value is ignored, with a near-zero pressure note', () => {
  const { flags, near } = assess({ environment: 'Vacuum', pressure_kpa: 101.3, o2_pct: 21 });
  assert.equal(near, null); // no ACME comparison without a pressure
  assert.ok(!flags.some((f) => /partial pressure/.test(f.title)));
  const note = flags.find((f) => f.title === 'Vacuum: pressure ignored');
  assert.match(note.detail, /near-zero pressure/);
  assert.ok(!flags.some((f) => /disagree/.test(f.title)));
});

test('materials list: each listed material is assessed; old single material_type still works', () => {
  const titles = assess({ material_types: ['PMMA (acrylic)', 'Teflon', 'Kapton', 'Lampwick'], o2_pct: 18 }).flags.map((f) => f.title);
  assert.ok(titles.some((t) => /BASS-II tested for PMMA/.test(t)));
  assert.ok(titles.includes('Toxic smoke if Teflon overheats or burns'));
  assert.ok(titles.includes('Toxic smoke if Kapton overheats or burns'));
  assert.ok(titles.includes('Smoke from PMMA (acrylic), Lampwick'));
  assert.equal(smokeStatus({ material_types: ['PMMA (acrylic)', 'Teflon'] }).overall, 'serious');
  assert.ok(bassFlag({ material_type: 'PMMA (acrylic)', o2_pct: 18 })); // legacy saves
});
