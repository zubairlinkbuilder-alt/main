# StyleX Tools

Two on-device face tools for stylexmagazine.com. Both run entirely in the
visitor's browser ,  no photo is ever uploaded, nothing is stored, and there is
no server, no API key and no per-use cost.

| Tool | File | Targets |
|---|---|---|
| **Face Shape Detector & Haircut Finder** (primary) | `dist/face-shape.html` | face shape / haircut cluster |
| **How Old Do I Look?** | `dist/age-test.html` | apparent-age cluster |
| **Face Shape Quiz** | `dist/face-shape-quiz.html` | quiz cluster, haircut gap |

---

## Deploy

### Option A ,  iframe embed (recommended)

1. Upload `dist/face-shape.html` to your server at `/stylex-tools/face-shape.html`.
2. Create the page (e.g. `/tools/face-shape-detector/`).
3. Add a **Custom HTML** block and paste `seo/embed-wordpress.html`.
4. Paste `seo/face-shape-schema.json` into your SEO plugin's custom-schema
   field, correcting the URLs.

The iframe isolates the tool from your theme, so a theme or plugin update
cannot break it. `allow="camera"` is required for the camera button.

### Option B ,  paste inline

Use the files in `dist/elementor/`, produced by:

```
python3 build-elementor.py
```

They have no `<!doctype>`, `<html>`, `<head>` or `<body>`, so they drop
straight into an Elementor **HTML widget** or a WordPress **Custom HTML**
block. Open the file, select all, paste.

They also carry a block of theme guards scoped to `.sx-tool`. A theme styles
bare elements globally and often with `!important`, which reaches into
anything pasted into a widget. The guards pin the button colours, input
borders, table backgrounds, heading case, link colours and the `[hidden]`
behaviour, while leaving prose bullets and numbering intact. Nothing in them
applies outside `.sx-tool`, so the rest of your page is untouched.

Verified against a deliberately hostile stylesheet (uppercase headings, red
`!important` buttons, 5px magenta input borders, 28px red list text,
`[hidden] { display: block !important }`): 30 checks, all passing, with the
theme's own styling unaffected outside the widget.

### Requirements

- **HTTPS.** The camera button will not work over plain HTTP.
- Models load once from jsDelivr (~980 KB total) and are then browser-cached.
  To self-host instead, copy the `model/` and `dist/` folders out of the
  `@vladmandic/face-api` npm package and change `MODEL_URL` and `LIB_URL` at
  the top of `src/engine.js`.

---

## Editing

| Want to change | Where |
|---|---|
| Haircut / beard recommendations | `SHAPES` in `src/engine.js` |
| Every internal link on every page | `src/links.json` |
| Classifier calibration | `TUNING` in `src/engine.js` |
| Quiz questions and answer weights | `src/quiz-engine.js` |
| Colours, spacing | `src/_ui.css` (tokens at the top) |
| The face shape CTA target | search `face-shape-calculator` in `src/age-test.html` |

After editing anything in `src/`, rebuild:

```
python3 build.py          # writes dist/
node tests/classify.test.mjs
node tests/quiz.test.mjs
```

`LINKS` starts empty on purpose ,  add only URLs confirmed in your sitemap, or
the list stays hidden. Nothing ships a broken link.

### Brand colours

The palette lives in the `:root` block at the top of `src/_ui.css`:
`#2B2D42` ink, `#F2C230` gold, `#F2C23021` gold tint, `#3F4368` indigo,
`#FFFFFF`. Light mode is white with the gold as the button and accent colour;
dark mode moves to `#2B2D42` with the gold kept as the accent. Gold carries
`#2B2D42` text rather than white ,  measured at 8.1:1, where gold-on-white text
would fail contrast outright. Change a token in one place and both tools
follow.

### Why the photo is read with FileReader, not createObjectURL

`URL.createObjectURL` produces a `blob:` URL, and a strict
Content-Security-Policy with `img-src 'self' data:` blocks it ,  the image
simply fails to load and the tool reports that it could not read the file.
Both tools now read uploads with `FileReader.readAsDataURL`, which works under
that policy. If you add a CSP to your own site, keep `data:` in `img-src`.

HEIC is detected and rejected with a clear message, because no browser decodes
it. iPhone users either convert to JPG or switch Settings › Camera › Formats
to "Most Compatible".

### Why the CTA is in the static HTML

The face shape button sits directly below the tool, in the page source at
load rather than injected after an analysis.
That matters ,  a crawler never uploads a photo, so anything rendered only in
the result state is invisible to it. The same goes for the prose sections:
every H2 is in the HTML at rest.

---

## How the face shape result is produced

1. `tinyFaceDetector` finds faces; the largest is used.
2. `faceLandmark68Net` places 68 points.
3. Head roll is cancelled using the eye centres, so widths are measured on a
   level face.
4. Four measurements are taken: cheekbone width (points 1–15), jaw width
   (3–13), forehead width (outer brows, 17–26), and face length (brow midpoint
   to chin, projected to the hairline).
5. Seven shapes are scored with smooth membership functions. The winner, its
   confidence and the full ranking are all shown to the visitor.

### A caveat worth knowing

The 68-point model has no hairline landmark, and landmark spans are not
anatomical widths. Measured across a calibration set, the brow span runs about
0.80× cheekbone width and the jaw span about 0.89×, so raw ratios cluster well
below the textbook numbers the shape definitions assume. `JAW_NORM`,
`FOREHEAD_NORM` and `FACE_LENGTH_FACTOR` in `TUNING` correct for this.

Those three constants were fitted on a small calibration set. The classifier
itself is verified against all seven textbook archetypes
(`tests/classify.test.mjs`), but on real photos the distribution skews toward
oval, round and square. **Run 15–20 of your own photos through it before
launch**; if results lean one way, adjust `FACE_LENGTH_FACTOR` (raise it if
faces read too round, lower it if everything reads oblong).

---

## Privacy and legal

Everything runs on-device. Nothing is transmitted, so no biometric identifier
is ever collected, stored or shared by you. That is the point: a tool that
uploads a face to a server extracts facial geometry, which is a biometric
identifier under Illinois BIPA and a special-category identifier under GDPR
Article 9 when used to identify someone ,  a live litigation area, with face-scan
class actions filed through 2026 against several large platforms.

Still do this before launch:

- Add a line to your privacy policy stating the tool processes images locally
  in the browser and transmits nothing.
- Keep the on-page privacy notice visible. It is a conversion asset as well as
  a compliance one ,  none of the competing tools can make the same claim.
- Do not add analytics events that record results against a user identifier.
- Never present the age tool as age verification. That is a regulated use.

---

## The quiz

`dist/face-shape-quiz.html` is a different route to the same answer: seven
questions, no photo and no measuring, for people who have neither a tape
measure nor a usable straight-on photo. It loads no model at all, so it is
instant and makes zero network requests after the page itself.

Answer weights live in `src/quiz-engine.js`. Each option carries weights
across the seven shapes; they are summed and the highest total wins, with a
close second reported when the top two finish within 12 percent.

Face length is the heaviest-weighted question because it is the only thing
separating oblong from square. In the first draft it was not, and every
oblong answer set scored as square ,  `tests/quiz.test.mjs` caught it.

`seo/quiz-research.md` has the keyword analysis the page content was built
against, and the cannibalisation boundaries between the three tool pages.

## Tests

```
node tests/classify.test.mjs
node tests/quiz.test.mjs
node tests/links.test.mjs
```

Checks all seven archetypes classify correctly, that an average face does not
land on a rare shape, that every shape is reachable, and that confidence stays
inside the documented band.

The browser-level checks run against a local copy of the models (upload,
camera capture, no-face handling, the gender toggle, reset, overlay painting,
dark mode and 360px layout), plus a structure pass that checks the CTA is in
the static HTML, the heading outline, breadcrumbs, word count and the
gold-button contrast ratio in both themes. Screenshots of the verified output
are in `docs/`.
