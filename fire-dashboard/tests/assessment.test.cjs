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
  lastContext = context;
  return context.FireDashboard._test;
}
let lastContext = null;
const loadContext = () => lastContext;

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
  // A material is only a hazard when it may be burning (no readings here).
  assert.equal(smokeStatus({ material_type: 'Teflon', co_ppm: 1, co2_ppm: 400 }).overall, 'good');
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
  // No smoke warnings for materials that are merely present.
  assert.ok(!titles.some((t) => /smoke/i.test(t)));
  assert.ok(bassFlag({ material_type: 'PMMA (acrylic)', o2_pct: 18 })); // legacy saves
});

test('safety insight HTML escapes the model text and tolerates bad levels', () => {
  const { insightHtml } = load();
  const html = insightHtml({
    model: 'dots-studio/dots-3-note-preview:free', provider: 'openrouter',
    insight: { headline: '<img src=x onerror=alert(1)>', risk_level: 'extreme', summary: 'ok',
      concerns: [{ title: 'CO', level: 'boom', explanation: '<b>60</b> ppm', action: 'Check' }], checks: ['a'], data_gaps: [] },
  });
  assert.doesNotMatch(html, /<img|<b>/);
  assert.match(html, /&lt;img/);
  assert.match(html, /Incomplete/); // unknown risk level
  assert.match(insightHtml({ text: 'Line one\n\nLine <two>' }), /Line &lt;two&gt;/);
});

test('uncertainty: missing readings and context are named, never treated as safe', () => {
  const r = assess({ o2_pct: 21, co_ppm: 1 });
  const titles = r.uncertain.map((u) => u.title);
  assert.ok(titles.some((t) => /^Not measured: .*CO₂/.test(t)));
  assert.ok(!titles.some((t) => /^Not measured: .*\bCO\b(?!₂)/.test(t))); // CO was given
  assert.ok(titles.some((t) => /^Not specified: .*materials present/.test(t)));
  assert.ok(titles.includes('No trend over time yet'));
  assert.ok(titles.includes('Limits are reference values'));
  for (const u of r.uncertain) assert.equal(u.level, 'uncertain');
  // A vacuum doesn't count pressure as missing; unknown burn data is named.
  const vac = assess({ environment: 'Vacuum', material_types: ['Teflon'] }).uncertain.map((u) => u.title);
  assert.ok(!vac.some((t) => /pressure/.test(t)));
  // Scoped to the loaded data, never a claim that no tests exist (issue #58).
  assert.ok(vac.includes('No matching BASS-II records in the loaded data for Teflon'));
  const detail = assess({ material_types: ['Teflon'] }).uncertain.find((u) => /Teflon/.test(u.title)).detail;
  assert.match(detail, /loaded in this dashboard/);
  assert.doesNotMatch(detail, /didn't burn|never|No NASA/);
});

test('every example scenario produces at least one warning', () => {
  const { EXAMPLE_INPUTS } = loadContext();
  for (const ex of EXAMPLE_INPUTS) {
    const worst = assess(ex.values).flags.filter((f) => ['warning', 'serious', 'critical'].includes(f.level));
    assert.ok(worst.length > 0, ex.label);
  }
});
