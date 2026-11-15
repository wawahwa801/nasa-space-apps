// No model service or Python environment required to audit the shipped evidence.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const folder = new URL("../public/flames/flex2/", import.meta.url);
const data = JSON.parse(await readFile(new URL("index.json", folder), "utf8"));
assert.equal(data.source, "PSI-68");
assert.equal(data.license, "CC0-1.0");
assert.equal(data.count, data.records.length);
assert.ok(data.count > 0);
assert.deepEqual(data.fields.map(f => f.key), ["pressure_kpa", "temperature_c"]);
assert.ok(data.scale.every(n => Number.isFinite(n) && n > 0));
const ids = new Set();
for (const record of data.records) {
  assert.match(record.id, /^[A-Z]\d{3}[A-Z]\d{2}$/);
  assert.ok(!ids.has(record.id)); ids.add(record.id);
  const fuel = data.fuels.find(f => f.name === record.fuel);
  assert.ok(fuel);
  assert.equal(record.image, `/flames/flex2/${record.id}.png`);
  assert.ok(record.archive.includes(record.id + "D.zip"));
  assert.ok(record.source_category.endsWith(record.fuel));
  for (const field of data.fields) {
    const v = record.features[field.key], range = fuel.ranges[field.key];
    assert.ok(Number.isFinite(v) && v >= range.min && v <= range.max);
  }
  assert.ok(record.members.length > 0);
  for (const member of record.members) assert.match(member.sha256, /^[a-f0-9]{64}$/);
  const image = await readFile(new URL(`${record.id}.png`, folder));
  assert.equal(createHash("sha256").update(image).digest("hex"), record.image_sha256);
  assert.equal(image.toString("hex", 0, 8), "89504e470d0a1a0a");
  assert.equal(image.readUInt32BE(16), 256); assert.equal(image.readUInt32BE(20), 256);
}
for (const fuel of data.fuels) {
  const records = data.records.filter(r => r.fuel === fuel.name);
  assert.equal(fuel.count, records.length);
  assert.ok(records.some(r => data.fields.every(f => r.features[f.key] === fuel.defaults[f.key])));
}
assert.equal((await readdir(fileURLToPath(folder))).filter(n => n.endsWith(".png")).length, data.count);
console.log(`Verified ${data.count} unique FLEX-2 runs, feature ranges, source joins and 256px image hashes.`);
