// Writes data/sample-readings/*.csv from the demo scenarios in js/monitoring.js,
// as test files for "Import readings CSV". Synthetic data, not measurements.
// Run: node fire-dashboard/scripts/make_sample_readings.cjs
const { readFileSync, writeFileSync, mkdirSync } = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.join(__dirname, '..');
const ctx = vm.createContext({});
ctx.window = ctx;
vm.runInContext(readFileSync(path.join(root, 'js/monitoring.js'), 'utf8'), ctx);
const { DEMOS, demoSequence } = ctx.Monitoring;

const out = path.join(root, 'data/sample-readings');
mkdirSync(out, { recursive: true });
const cols = [['co_ppm', 'CO (ppm)'], ['co2_ppm', 'CO2 (ppm)'], ['o2_pct', 'O2 (%)'], ['internal_temp_c', 'Temperature (C)'],
  ['humidity_pct', 'Humidity (%)'], ['h2_ppm', 'H2 (ppm)'], ['ch4_ppm', 'CH4 (ppm)'], ['pressure_kpa', 'Pressure (kPa)']];
for (const id of Object.keys(DEMOS)) {
  const rows = demoSequence(0, 5, id).map((r) => [r.t / 60000, ...cols.map(([k]) => r[k])].join(','));
  writeFileSync(path.join(out, `${id}.csv`), ['minutes,' + cols.map(([, h]) => h).join(','), ...rows].join('\n') + '\n');
  console.log(`wrote data/sample-readings/${id}.csv`);
}
