const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');

function node() {
  return {
    clientWidth: 600, children: [], attrs: {},
    setAttribute(k, v) { this.attrs[k] = v; },
    appendChild(child) { this.children.push(child); },
    addEventListener() {},
  };
}

for (const [name, values] of [
  ['adjacent floating-point values', [1, 1 + Number.EPSILON]],
  ['large input arrays', Array.from({ length: 150000 }, (_, i) => i)],
  ['constant values', [3, 3]],
]) {
  test(name, () => {
    const container = node();
    const context = vm.createContext({
      window: {}, document: { createElementNS: node }, container, values,
    });
    vm.runInContext(readFileSync(require.resolve('../js/charts.js'), 'utf8'), context);
    vm.runInContext('window.Charts.line(container, {x: values, y: values})', context, { timeout: 3000 });
    const svg = container.children[0];
    assert.ok(svg);
    const path = svg.children.find(child => child.attrs.class === 'series-line');
    assert.ok(path);
    assert.doesNotMatch(path.attrs.d, /NaN|Infinity/);
  });
}

test('strip plot places one dot per finite point and ignores unknown rows', () => {
  const container = node();
  const context = vm.createContext({ window: {}, document: { createElementNS: node }, container });
  vm.runInContext(readFileSync(require.resolve('../js/charts.js'), 'utf8'), context);
  vm.runInContext(`window.Charts.strip(container, {
    rows: [{ id: 'a', label: 'A' }, { id: 'b', label: 'B', highlight: true }],
    points: [{ row: 'a', x: 18, tip: 'x' }, { row: 'b', x: 21, tip: 'y' }, { row: 'b', x: NaN, tip: 'z' }, { row: 'zz', x: 20, tip: 'w' }],
    xLabel: 'O2', ref: { value: 21.5, label: 'You' },
  })`, context, { timeout: 3000 });
  const svg = container.children[0];
  const dots = svg.children.filter((c) => c.attrs.class === 'dot s1');
  assert.equal(dots.length, 2);
  for (const d of dots) assert.ok(Number.isFinite(Number(d.attrs.cx)) && Number.isFinite(Number(d.attrs.cy)));
  assert.ok(svg.children.some((c) => c.attrs.class === 'row-label highlight'));
});

test('bar chart draws finite bars from zero and skips missing values', () => {
  const container = node();
  const context = vm.createContext({ window: {}, document: { createElementNS: node }, container });
  vm.runInContext(readFileSync(require.resolve('../js/charts.js'), 'utf8'), context);
  vm.runInContext(`window.Charts.bars(container, {
    bars: [{ label: 'A', value: 575 }, { label: 'B', value: 0.4 }, { label: 'C', value: NaN, highlight: true }],
    unit: 'ppm', xLabel: 'CO',
  })`, context, { timeout: 3000 });
  const svg = container.children[0];
  const bars = svg.children.filter((c) => c.attrs.class === 'bar s1');
  assert.equal(bars.length, 2);
  for (const b of bars) assert.doesNotMatch(b.attrs.d, /NaN|Infinity/);
  assert.ok(svg.children.some((c) => c.attrs.class === 'row-label highlight'));
});
