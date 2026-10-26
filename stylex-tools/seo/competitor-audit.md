# Audit — the four tools you sent

**Method note:** this container's network policy blocks all four domains
(the proxy returned 403 on every request), so none of the four could be
crawled directly. Everything below comes from search-indexed copy of those
pages plus their own published docs. Vendor claims are labelled as such.
Verify the numbers yourself before quoting any of them in an article.

---

## 1. howolddoyoulook.com

**What it is:** an apparent-age estimator. Upload a photo, get an age.

**Pipeline (from its own blog):** face detection crops the face → facial
landmark mapping over eyes, nose, mouth and jawline → a deep neural network
trained with supervised learning on labelled-age images predicts the age. The
homepage also pitches an API for the same three stages.

**Honest about the right thing:** its FAQ separates chronological age from
biological age and positions itself as apparent age. That is the correct
framing and the one to copy.

**Weaknesses:**
- Publishes no accuracy figure, no training-set size, no model detail.
- Server-side processing — the photo is uploaded.
- A swarm of near-identical lookalike domains (`howolddoilook.com`, `.cv`,
  `.co`, `.app`, `.io`, `howolddoyoulook.app`) makes contradictory claims:
  one cites 56 million training photos, another says it calls a multimodal
  model, accuracy claims range from "3–5 years" to "within a few years".
  Those belong to other domains and none of it is verifiable.

**Takeaway:** low technical moat. The category is a commodity with heavy
domain squatting.

---

## 2. faceage.ai

**What it is:** apparent-age estimator with a "biological age" flavour.

**Claims:** photos processed instantly, never stored or shared;
privacy-focused.

**Weaknesses:**
- No independent review or audit of the privacy claim exists. It rests
  entirely on its own marketing, while the photo is still uploaded.
- **Name collision with real research.** There is a genuine FaceAge from Mass
  General Brigham / Harvard AIM, published in *The Lancet Digital Health*,
  that estimates biological age from face photographs to improve
  prognostication. It was trained on nearly 60,000 images of healthy people
  and validated on 6,000+ patients starting radiotherapy, which found cancer
  patients appeared roughly five years older than their chronological age.
  That tool is at `faceage.bwh.harvard.edu`, requires a consent form, and is
  research-only. The commercial `.ai` domain is a different thing.

**Takeaway:** do not borrow the "biological age" framing. On a fashion and
grooming site, a health-adjacent claim pulls the page into YMYL territory
where you have no author credentials, no citations and no clinical basis —
for a number a selfie cannot support.

---

## 3. rigr.ai/capabilities/age-estimation/

**What it is:** not a consumer toy. This is a B2B **age assurance** vendor
selling to platforms that must keep minors out.

**Vendor-reported accuracy:** overall MAE 1.64 years; 0.87 years for ages
0–18; 68.9% of estimates within ±1 year. Model is a vision transformer (v3)
producing a point estimate plus a calibrated uncertainty value. Its API
reference quotes ~1.6 years MAE.

**The number nobody quotes — and the one that matters to you:** accuracy
collapses with age. **MAE 3.30 years at ages 26–40 and 5.04 years at 40+.**
Rigr's own page notes these describe its benchmark dataset, not every upload.

**Independent signal:** the Australian Government's Age Assurance Technology
Trial includes a Rigr case study, rating it strongly on technical readiness,
privacy and usability with fast on-device processing and low false-positive
rates. The trial tested against its own dataset, not the vendor's, and the
trial's MAE figures are not public — so the 1.64 figure stays unverified.
Its "on-device/edge-enabled" architecture is also unverified: the only
documented interface is a server endpoint (`POST /api/image`), with no SDK or
on-device latency benchmark published.

**Takeaway:** the best-documented vendor in your set, and the wrong category
for you. It also hands you the single most useful fact in this audit — the
3.30 / 5.04 year error band for adults is exactly why a "how old do I look"
result should be shown as a range, not a number.

---

## 4. longevity-cities.com/en/tools/face-age

**What it is:** a face-age tool inside a longevity-content site. Nothing from
this domain is indexed in the searches run, so it could not be verified at
all. A sister domain (`longevity-germany.com/en/tools/face-age`) runs the same
"How Old Do I Look? AI Face Age Calculator" page.

**Takeaway:** structurally, the pattern to note. A content site uses a face
tool as a top-of-funnel magnet for its real subject (longevity). The tool
serves the content vertical. That is the correct relationship, and the exact
test your own tool should pass.

---

## What all four share

| | Processing | Photo uploaded | Accuracy published | Privacy verifiable |
|---|---|---|---|---|
| howolddoyoulook.com | Server | Yes | No | No |
| faceage.ai | Server | Yes | No | No |
| rigr.ai | Server (claims edge) | Yes | Yes, with caveats | Partly — gov trial |
| longevity-cities.com | Unknown | Presumed | No | No |

**Every one of them uploads the photo.** That is the gap. A tool that
processes on-device can say "your photo never leaves this page" and mean it —
which is both the strongest conversion line on the page and the reason you
never touch a biometric identifier under BIPA or GDPR Article 9.

---

## The strategic problem with the brief

You asked for an age tool. Three things argue against making it your main one:

1. **Topical fit.** StyleX covers haircuts, grooming, fashion and lifestyle.
   "How old do I look" traffic shares no intent with any of that. It arrives,
   gets a number, and leaves. It builds no topical authority for the cluster
   you actually rank in, and it has no internal-link relationship with a
   single existing article.

2. **The incumbents are pure-plays.** `howolddoyoulook.com`,
   `howolddoilook.com` and their dozen cousins exist for that one query, with
   every signal on the domain pointing at it. Searchers already name them in
   queries (`novos how old do i look`, `buzztests how old do i look`), which
   means brand recall in the category. A tools subfolder on a magazine domain
   is fighting uphill for a query that monetises badly even if you win it.

3. **Risk for no return.** Face uploads are the most actively litigated area
   in US privacy right now — face-scan class actions were filed through 2026
   against several large platforms, with BIPA statutory damages of $1,000 per
   negligent and $5,000 per intentional violation, per person. An on-device
   tool sidesteps this, which is how both tools here are built. But the
   risk-adjusted case for the age tool as your flagship is still weak.

**The better fit, which is why it is the primary deliverable:** a **face shape
detector**. Same technology, same on-device privacy story, and it sits
directly on top of the cluster StyleX already publishes into — "diamond face
shape" alone is 90,500/mo, with "what is my face shape", "face shape
analyzer", "face shape best haircut" and "according to face shape haircut"
behind it. Every shape-specific haircut article links into it; its result
links back out to the matching article. It turns a tool page into the hub of a
content cluster instead of a cul-de-sac.

Both are built and tested. Ship the face shape tool as the flagship, and the
age tool as a secondary page that hands its traffic to the face shape tool.
