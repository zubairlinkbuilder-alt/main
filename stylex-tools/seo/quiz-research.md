# Face Shape Quiz ,  research & positioning

## What was analysed

| Source | Rows |
|---|---|
| thehairstyler.com/face-shape-quiz (CSV) | 34 |
| wikihow.com/Face-Shape-Quiz (CSV) | 12 |
| oblongfaceshape.com/face-shape-quiz (CSV) | 7 |
| **Total rows** | **53** |
| **Unique keywords** | **36** |

Combined volume across those 36: roughly 6,750 searches a month.

Supplementary, outside the CSVs: four autocomplete pulls from Keyword Tool
(`face shape` 650 variants, `how old do i look` 399, `face shape detector`
399, `face shape calculator` 142) and six search passes on the four
competitor pages to establish their question counts, scoring approach and
accuracy claims.

**The fourth URL, faceshapedetector.app, has no CSV**, so it contributes
structure (7 questions, weighted scoring, a reported close second) but no
keyword data. Everything in the tables below comes from your three exports.

**Method note:** the four competitor URLs could not be crawled from this
container (network policy returns 403 on every outbound host), so page
structure below comes from search-indexed copy of those pages plus their own
descriptions. The keyword figures come from your CSV exports and are solid.

---

## What the competitors actually own

| Keyword | Vol | Best pos | KD | Who |
|---|---|---|---|---|
| face shape recognizer | 480 | 4 | 25 | thehairstyler |
| what type of face do i have quiz | 70 | 1 | 25 | thehairstyler |
| what's my face shape quiz | 50 | 1 | 23 | thehairstyler |
| what face type am i | 50 | 3 | 29 | wikihow |

That is the whole list. TheHairStyler sits at #1 for its two head terms and
collects 17 and 12 monthly visits from them. **The quiz category is small at
the head and the incumbents are not strong beyond it.**

## Where the volume actually is ,  and nobody serves it

| Keyword | Vol | Best pos | KD | Intent |
|---|---|---|---|---|
| face structure | 1,300 | 32 | 28 | I |
| what is your face shape | 880 | 37 | 24 | I |
| types of face | 590 | 26 | 29 | I |
| shape test | 320 | 75 | 26 | I |
| **what haircut for my face shape** | **260** | **69** | 29 | I |
| headshape | 260 | 16 | 28 | I |
| face measurements | 210 | 14 | 28 | I |
| how do you measure your face shape | 170 | 39 | 21 | I |
| woman face shape | 170 | 13 | 23 | I |
| i have a round face | 170 | 26 | 21 | I |
| **what haircut suits me quiz** | **140** | **57** | **17** | **CI** |
| apple face shape | 110 | 55 | 24 | I |
| what haircut is right for me quiz | 110 | 40 | 21 | I |
| how to find the shape of face | 110 | 25 | 18 | I |

## The wedge

Roughly **670/mo of haircut-connected terms** sit unclaimed, with best
positions between #31 and #79:

- what haircut for my face shape ,  260
- what haircut suits me quiz ,  140 (KD 17, commercial intent)
- what hairstyle suits my face shape ,  90
- what hairstyle fits my face shape ,  90
- how to determine face shape for haircut ,  70

**All four competitors stop at the shape name.** wikiHow is an article,
TheHairStyler's quiz hands you a label, and the two tool sites push you to
their detector. None of them finishes the job the searcher came for, which is
a haircut. That is StyleX's existing subject, so this is the one angle where
the site is the natural answer rather than a challenger.

## How this page is built against that

| Gap found | What the page does |
|---|---|
| Quiz ends at a label | Result goes straight to cuts for the detected shape, men and women, plus beard guidance |
| `face structure` 1,300/mo unserved | "What your face structure actually means" ,  the four widths, the ratio, the chin |
| `types of face` 590/mo unserved | A 7-row table: how to recognise each shape and its cut brief |
| `what haircut for my face shape` | Its own H2: how to translate a shape into a brief for the chair |
| `woman face shape` / `face shape types women` | "Does face shape differ for men and women?" ,  same shapes, different silhouettes |
| `apple face shape` 110/mo | Named and explained as a make-up term for round, not an eighth shape |
| Competitors claim "100% accurate" | An honest accuracy section ,  what a quiz can and cannot do, and when to measure instead |
| No competitor shows its working | "See how your answers were scored" ,  the per-answer recap |
| Rectangle / long face / pear / inverted triangle | All mapped to their real shape, catching the alias queries |

## Cannibalisation boundaries

Three pages on one topic only works with hard boundaries:

| Page | Owns | Input |
|---|---|---|
| `/face-shape-quiz/` | `*quiz`, `what face type am i`, `what is your face shape`, `face structure`, `types of face` | 7 questions |
| `/face-shape-calculator/` | `calculator`, `detector`, `recognizer`, `measure`, `face measurements` | Measurements or photo |
| `/tools/how-old-do-i-look/` | `how old do i look`, apparent age | Photo |

The risk is real, not theoretical: `face shape calculator online` and `face
shape calculator female` already rank on **both** competitor quiz pages, so
Google does blend the two. Keep the quiz page off the words "calculator" and
"detector" in its title, H1 and H2s ,  it uses them only once, inside the
comparison table where the distinction is the point, and in the CTA that
hands traffic over.

Link them in one direction each: the quiz sends people to the calculator for
precision; the calculator should send people to the quiz with "no tape
measure?".


---

## Is this page better than the competitors?

Better on content and on the gap that matters. Not yet better on the things
that decide rankings.

**Where it genuinely wins**

- The haircut terms. Best competitor positions are #31 to #79, which means
  nobody has an optimised page for them, only incidental mentions. That is a
  weak field, not a strong one.
- Depth: 1,080 words, 12 H2s, 2 comparison tables and 7 FAQs against a quiz
  that hands you a label.
- Transparency: the per-answer recap shows how the result was reached. No
  competitor shows its working.
- Topical fit. `what haircut for my face shape` sits naturally on a haircuts
  magazine; it does not sit naturally on wikiHow.

**Where it does not win, and will not soon**

- Domain strength. wikiHow and TheHairStyler are large, aged domains holding
  #1 to #4 on the head terms. A new URL will not displace them on
  `what face type am i` or `what's my face shape quiz` on content alone.
- No history and no links. Those four terms are worth 70, 50, 50 and 480 a
  month, and the incumbents are entrenched.

**What is unproven**

The answer weights are reasoned from the standard shape definitions and
verified against seven textbook archetypes in `tests/quiz.test.mjs`. They
have **not** been validated against real faces. oblongfaceshape.com claims
its weighting was checked against 51,247 analyses; that is self-reported and
unverifiable, but it is a real claim this page cannot match.

A fair expectation: this page competes for the long tail around haircuts and
face structure, where the field is weak, rather than for the head quiz terms,
where it is not. Run 15 to 20 people you know through it and compare against
the calculator before treating the result as settled.
