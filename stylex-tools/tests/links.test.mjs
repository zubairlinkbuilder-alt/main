/**
 * Link integrity.
 *
 * Nothing in dist/ may point at a URL that links.json does not declare, and
 * no link may be left as a placeholder or an empty href. A page is allowed to
 * mention a URL only if it is in the map.
 *
 *   node tests/links.test.mjs
 */
import fs from 'node:fs';
import path from 'node:path';

const root = path.dirname(new URL(import.meta.url).pathname);
const dist = path.join(root, '..', 'dist');
const links = JSON.parse(fs.readFileSync(path.join(root, '..', 'src', 'links.json'), 'utf8'));

const declared = new Set();
for (const [k, v] of Object.entries(links)) {
  if (typeof v === 'string' && v.startsWith('http')) declared.add(v);
  if (k === 'shapes' && v) for (const u of Object.values(v)) if (u) declared.add(u);
  if (k === 'related' && Array.isArray(v)) for (const l of v) if (l?.href) declared.add(l.href);
}

const ALLOWED_EXTERNAL = [
  'https://cdn.jsdelivr.net/',   // the face model, on the two photo tools
];

let failed = 0;
for (const file of fs.readdirSync(dist).filter(f => f.endsWith('.html'))) {
  const html = fs.readFileSync(path.join(dist, file), 'utf8');
  const problems = [];

  // unresolved build placeholders
  for (const p of ['{{', '<!--BREADCRUMB-->', 'INJECT_CSS', 'INJECT_ENGINE', 'INJECT_QUIZ', 'INJECT_LINKS']) {
    if (html.includes(p)) problems.push(`unresolved placeholder ${p}`);
  }

  // every href must be declared, an in-page anchor, or an allowed CDN
  const hrefs = [...html.matchAll(/href="([^"]*)"/g)].map(m => m[1]);
  for (const href of hrefs) {
    if (!href.trim()) { problems.push('empty href'); continue; }
    if (href.startsWith('#')) continue;
    if (ALLOWED_EXTERNAL.some(a => href.startsWith(a))) continue;
    if (declared.has(href)) continue;
    problems.push(`undeclared link: ${href}`);
  }

  // a stylexmagazine URL hardcoded anywhere, not just in href
  const hardcoded = [...html.matchAll(/https:\/\/stylexmagazine\.com\/[^"'\s<)]*/g)].map(m => m[0]);
  for (const u of new Set(hardcoded)) {
    if (!declared.has(u)) problems.push(`hardcoded URL not in links.json: ${u}`);
  }

  if (problems.length) {
    failed++;
    console.log(`  FAIL  ${file}`);
    [...new Set(problems)].slice(0, 6).forEach(p => console.log(`        ${p}`));
  } else {
    console.log(`  PASS  ${file}  (${hrefs.length} links, all declared)`);
  }
}

// em dashes must not reappear in shipped copy
for (const file of fs.readdirSync(dist).filter(f => f.endsWith('.html'))) {
  const n = (fs.readFileSync(path.join(dist, file), 'utf8').match(/—/g) || []).length;
  if (n) { console.log(`  FAIL  ${file}: ${n} em dash(es)`); failed++; }
}
if (!failed) console.log('  PASS  no em dashes in any built page');

console.log(failed ? `\nlinks: ${failed} failure(s)` : '\nlinks: all checks passed');
process.exit(failed ? 1 : 0);
