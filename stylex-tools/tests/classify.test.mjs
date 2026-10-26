/**
 * Unit test for the shape classifier.
 *
 * Feeds textbook archetypes for each of the seven shapes straight into
 * classify(), bypassing photo quality and landmark detection. If an
 * archetype does not return its own shape, the scoring targets in
 * engine.js are wrong.
 *
 *   node tests/classify.test.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root = path.dirname(new URL(import.meta.url).pathname);
const source = fs.readFileSync(path.join(root, '..', 'src', 'engine.js'), 'utf8');

const sandbox = { window: {}, console };
vm.createContext(sandbox);
new vm.Script(source).runInContext(sandbox);
const { classify } = sandbox.window.StyleXFace._internal;

// lengthToCheek, jawToCheek, foreheadToCheek, chinAngle — on the normalised
// scale an average face reads 1.45 / 0.95 / 0.95 / ~118.
const ARCHETYPES = [
  ['oval',     { lr: 1.50, jc: 0.88, fc: 0.92, chin: 120 }],
  ['round',    { lr: 1.15, jc: 0.96, fc: 0.96, chin: 125 }],
  ['square',   { lr: 1.28, jc: 1.02, fc: 1.00, chin: 100 }],
  ['oblong',   { lr: 1.80, jc: 0.96, fc: 0.96, chin: 115 }],
  ['heart',    { lr: 1.45, jc: 0.85, fc: 1.05, chin: 95  }],
  ['diamond',  { lr: 1.58, jc: 0.84, fc: 0.86, chin: 98  }],
  ['triangle', { lr: 1.35, jc: 1.08, fc: 0.92, chin: 120 }]
];

function metrics(a) {
  return {
    lengthToCheek: a.lr,
    jawToCheek: a.jc,
    foreheadToCheek: a.fc,
    foreheadToJaw: a.fc / a.jc,
    chinAngle: a.chin
  };
}

let failed = 0;

console.log('archetype -> classified          conf  runner-up');
for (const [expected, a] of ARCHETYPES) {
  const r = classify(metrics(a));
  const ok = r.id === expected;
  if (!ok) failed++;
  console.log(
    `  ${ok ? 'PASS' : 'FAIL'}  ${expected.padEnd(9)} -> ${r.id.padEnd(9)}  ` +
    `${(r.confidence * 100).toFixed(0)}%   ${r.runnerUp}` +
    (ok ? '' : `   EXPECTED ${expected}`)
  );
}

// An average face must not land on a rare shape.
const avg = classify(metrics({ lr: 1.45, jc: 0.95, fc: 0.95, chin: 118 }));
const plausible = ['oval', 'round', 'square', 'oblong'];
if (!plausible.includes(avg.id)) {
  console.log(`  FAIL  average face -> ${avg.id} (expected one of ${plausible.join('/')})`);
  failed++;
} else {
  console.log(`  PASS  average face -> ${avg.id}`);
}

// Every shape must be reachable, and all seven must be ranked every time.
if (avg.ranked.length !== 7) { console.log('  FAIL  ranked list is not 7 long'); failed++; }
const reachable = new Set(ARCHETYPES.map(([e, a]) => classify(metrics(a)).id));
if (reachable.size !== 7) {
  console.log(`  FAIL  only ${reachable.size}/7 shapes reachable: ${[...reachable].join(', ')}`);
  failed++;
} else {
  console.log('  PASS  all 7 shapes reachable');
}

// Confidence must stay inside the documented band.
const band = ARCHETYPES.every(([, a]) => {
  const c = classify(metrics(a)).confidence;
  return c >= 0.55 - 1e-9 && c <= 0.95 + 1e-9;
});
if (!band) { console.log('  FAIL  confidence outside 0.55-0.95'); failed++; }
else { console.log('  PASS  confidence clamped to 0.55-0.95'); }

console.log(failed === 0 ? '\nclassifier: all checks passed' : `\nclassifier: ${failed} failure(s)`);
process.exit(failed ? 1 : 0);
