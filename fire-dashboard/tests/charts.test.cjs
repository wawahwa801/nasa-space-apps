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
