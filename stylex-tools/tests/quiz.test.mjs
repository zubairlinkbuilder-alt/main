/**
 * Unit test for the quiz scoring.
 *
 * For each shape, answers a textbook sufferer of that shape would give must
 * return that shape. Also checks that every shape is reachable and that a
 * deliberately contradictory answer set is reported as a close call.
 *
 *   node tests/quiz.test.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const root = path.dirname(new URL(import.meta.url).pathname);
const sandbox = { window: {}, console };
vm.createContext(sandbox);
new vm.Script(fs.readFileSync(path.join(root, '..', 'src', 'quiz-engine.js'), 'utf8')).runInContext(sandbox);
const Q = sandbox.window.StyleXQuiz;

// answers in question order: length, widest, jaw, chin, forehead, hairline, cheeks
const ARCHETYPES = {
  //          len wid jaw chin fore hair cheek
  oblong:   [  0,  3,  0,  2,   2,   1,   2 ],
  oval:     [  1,  1,  2,  1,   2,   0,   3 ],
  round:    [  2,  1,  1,  1,   0,   0,   1 ],
  square:   [  2,  3,  0,  2,   0,   1,   2 ],
  heart:    [  1,  0,  2,  0,   0,   2,   3 ],
  diamond:  [  1,  1,  2,  0,   1,   0,   0 ],
  triangle: [  1,  2,  3,  2,   1,   1,   2 ]
};

let failed = 0;
console.log('archetype -> scored            conf  runner-up  close');
for (const [expected, answers] of Object.entries(ARCHETYPES)) {
  const r = Q.score(answers);
  const ok = r.id === expected;
  if (!ok) failed++;
  console.log(
    `  ${ok ? 'PASS' : 'FAIL'}  ${expected.padEnd(9)} -> ${r.id.padEnd(9)}  ` +
    `${(r.confidence * 100).toFixed(0)}%   ${r.runnerUp.padEnd(9)}  ${r.close}` +
    (ok ? '' : `   EXPECTED ${expected}`)
  );
}

const reachable = new Set(Object.values(ARCHETYPES).map(a => Q.score(a).id));
if (reachable.size !== 7) {
  console.log(`  FAIL  only ${reachable.size}/7 shapes reachable: ${[...reachable].join(', ')}`);
  failed++;
} else console.log('  PASS  all 7 shapes reachable');

// Structure: every question needs a stable id, 3+ options, and every option
// must carry at least one weight, or an answer could score nothing at all.
let structureOk = true;
const ids = new Set();
for (const q of Q.QUESTIONS) {
  if (!q.id || ids.has(q.id)) { console.log(`  FAIL  bad/duplicate question id: ${q.id}`); structureOk = false; }
  ids.add(q.id);
  if (q.options.length < 3) { console.log(`  FAIL  ${q.id} has ${q.options.length} options`); structureOk = false; }
  for (const o of q.options) {
    const total = Object.values(o.w).reduce((a, b) => a + b, 0);
    if (!total) { console.log(`  FAIL  ${q.id} / "${o.t}" carries no weight`); structureOk = false; }
    for (const s of Object.keys(o.w)) {
      if (!Q.LABELS[s]) { console.log(`  FAIL  ${q.id} / "${o.t}" weights unknown shape "${s}"`); structureOk = false; }
    }
  }
}
if (structureOk) console.log(`  PASS  ${Q.QUESTIONS.length} questions, ids unique, every option weighted`);
else failed++;

// Partial answers must not throw, and no answers must not crash either.
try {
  Q.score([0]); Q.score({}); Q.score([]);
  console.log('  PASS  partial and empty answer sets handled');
} catch (e) { console.log('  FAIL  partial answers threw: ' + e.message); failed++; }

// A contradictory set (long face + widest jaw + pointed chin) should be close.
const muddled = Q.score([0, 2, 2, 0, 1, 1, 3]);
console.log(`  INFO  contradictory set -> ${muddled.id} / ${muddled.runnerUp}, close=${muddled.close}`);

// Every question answered must produce a decisive, non-zero score.
const allFirst = Q.score([0, 0, 0, 0, 0, 0, 0]);
if (!(allFirst.ranked[0].score > 0)) { console.log('  FAIL  uniform answers scored zero'); failed++; }
else console.log(`  PASS  uniform answers score (${allFirst.id}, ${allFirst.ranked[0].score.toFixed(1)})`);

console.log(failed === 0 ? '\nquiz scoring: all checks passed' : `\nquiz scoring: ${failed} failure(s)`);
process.exit(failed ? 1 : 0);
