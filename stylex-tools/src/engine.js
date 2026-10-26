/*!
 * StyleX Face Engine v1.0
 * On-device face analysis for StyleX Magazine (stylexmagazine.com)
 *
 * Nothing leaves the visitor's browser. No upload, no server, no storage.
 * Model weights are fetched from jsDelivr once and cached by the browser.
 *
 * Exposes: window.StyleXFace
 *   .loadModels(onProgress) -> Promise
 *   .analyze(HTMLImageElement|HTMLVideoElement|HTMLCanvasElement) -> Promise<Result>
 *   .TUNING  (calibration constants, safe to edit)
 *   .SHAPES  (shape ids + editorial copy)
 */
(function () {
  'use strict';

  var MODEL_URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.15/model';
  var LIB_URL   = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.15/dist/face-api.esm.js';

  var api = null;      // face-api module once imported
  var ready = null;    // in-flight load promise

  /* ------------------------------------------------------------------ *
   * Calibration
   *
   * The 68-point model has no hairline landmark, so forehead width is
   * measured across the outer brow points and face length is projected
   * from brow->chin using the classical "rule of thirds" (brow->chin is
   * roughly two thirds of hairline->chin). FACE_LENGTH_FACTOR converts
   * one to the other. Raise it if the tool reads faces as too round;
   * lower it if everything comes back oblong.
   * ------------------------------------------------------------------ */
  var TUNING = {
    // Landmark spans are not anatomical widths. Measured across a calibration
    // set, the outer-brow span runs about 0.80x cheekbone width and the upper
    // jaw span about 0.89x, so the raw ratios cluster far below the textbook
    // numbers the shape definitions use. These three factors put all four
    // measurements on one comparable scale, where an average face reads
    // length/cheek ~1.45, jaw/cheek ~0.95 and forehead/cheek ~0.95.
    // Re-tune them against your own sample photos if results skew.
    FACE_LENGTH_FACTOR: 1.70,
    JAW_NORM: 1.07,
    FOREHEAD_NORM: 1.195,

    MIN_FACE_PX: 90,          // reject faces too small to measure reliably
    DUP_FACE_OVERLAP: true,   // treat boxes sharing a centre as one face
    CONFIDENCE_FLOOR: 0.55,   // reported confidence is clamped into this band
    CONFIDENCE_CEIL: 0.95,
    AGE_BAND: 4               // +/- years shown around the point estimate
  };

  /* ---------------------------- geometry ---------------------------- */

  function dist(a, b) { var dx = a.x - b.x, dy = a.y - b.y; return Math.sqrt(dx * dx + dy * dy); }
  function mid(a, b) { return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }; }
  function mean(pts) {
    var sx = 0, sy = 0;
    for (var i = 0; i < pts.length; i++) { sx += pts[i].x; sy += pts[i].y; }
    return { x: sx / pts.length, y: sy / pts.length };
  }

  // Angle ABC at vertex B, in degrees.
  function angleAt(b, a, c) {
    var v1 = { x: a.x - b.x, y: a.y - b.y };
    var v2 = { x: c.x - b.x, y: c.y - b.y };
    var d = (v1.x * v2.x + v1.y * v2.y) /
            (Math.sqrt(v1.x * v1.x + v1.y * v1.y) * Math.sqrt(v2.x * v2.x + v2.y * v2.y) || 1);
    return Math.acos(Math.max(-1, Math.min(1, d))) * 180 / Math.PI;
  }

  // Cancel head roll so widths are measured on a level face.
  function deroll(pts) {
    var rightEye = mean(pts.slice(36, 42));
    var leftEye = mean(pts.slice(42, 48));
    var ang = Math.atan2(leftEye.y - rightEye.y, leftEye.x - rightEye.x);
    var cos = Math.cos(-ang), sin = Math.sin(-ang);
    var c = mid(rightEye, leftEye);
    return pts.map(function (p) {
      var dx = p.x - c.x, dy = p.y - c.y;
      return { x: c.x + dx * cos - dy * sin, y: c.y + dx * sin + dy * cos };
    });
  }

  // Yaw proxy: 1.0 = dead-on, lower = turned away.
  function symmetry(pts) {
    var nose = pts[30];
    var l = dist(nose, pts[0]);   // right jaw edge
    var r = dist(nose, pts[16]);  // left jaw edge
    return Math.min(l, r) / (Math.max(l, r) || 1);
  }

  function measure(raw) {
    var p = deroll(raw);
    var chin = p[8];
    var browMid = mid(p[21], p[22]);

    // Raw landmark spans.
    var cheek = dist(p[1], p[15]);        // zygomatic / cheekbone width
    var jawRaw = dist(p[3], p[13]);       // upper jaw, nearest the gonion
    var browRaw = dist(p[17], p[26]);     // outer brow span (forehead proxy)

    // Normalised to a comparable scale — see TUNING.
    var jaw = jawRaw * TUNING.JAW_NORM;
    var forehead = browRaw * TUNING.FOREHEAD_NORM;
    var length = dist(browMid, chin) * TUNING.FACE_LENGTH_FACTOR;
    var chinAngle = angleAt(chin, p[5], p[11]);     // small = pointed chin

    return {
      cheekPx: cheek, jawPx: jaw, foreheadPx: forehead, lengthPx: length,
      jawRawPx: jawRaw, foreheadRawPx: browRaw,
      lengthToCheek: length / cheek,
      jawToCheek: jaw / cheek,
      foreheadToCheek: forehead / cheek,
      foreheadToJaw: forehead / jaw,
      chinAngle: chinAngle,
      symmetry: symmetry(p)
    };
  }

  /* ------------------------- classification ------------------------- */

  // Triangular membership: 1 at target, 0 beyond tolerance.
  function near(v, target, tol) { return Math.max(0, 1 - Math.abs(v - target) / tol); }
  // Ramp: 0 below t, 1 at t+k.
  function above(v, t, k) { return Math.max(0, Math.min(1, (v - t) / k)); }

  function classify(m) {
    var lr = m.lengthToCheek;
    var jc = m.jawToCheek;
    var fc = m.foreheadToCheek;
    var fj = m.foreheadToJaw;
    var pointed = above(130 - m.chinAngle, 10, 30); // 1 = sharply pointed chin
    var soft = above(m.chinAngle, 105, 30);         // 1 = wide, rounded chin

    var scores = {
      oval:      near(lr, 1.50, 0.30) * 1.5 + near(jc, 0.90, 0.14) + near(fc, 0.93, 0.15) + soft * 0.5,
      round:     near(lr, 1.18, 0.22) * 1.8 + near(jc, 0.95, 0.15) + near(fc, 0.95, 0.15) + soft,
      square:    near(lr, 1.28, 0.25) * 1.3 + near(jc, 1.00, 0.12) * 1.5 + near(fc, 0.99, 0.14) + pointed * 0.6,
      oblong:    above(lr, 1.65, 0.35) * 2.0 + near(jc, 0.95, 0.15) + near(fc, 0.95, 0.15),
      heart:     above(fj, 1.12, 0.20) * 1.8 + above(fc, 1.00, 0.12) * 1.2 + pointed + near(lr, 1.45, 0.35) * 0.6,
      diamond:   above(1 / fc, 1.08, 0.15) * 1.5 + above(1 / jc, 1.08, 0.15) * 1.5 + near(lr, 1.55, 0.30) + pointed * 0.8,
      triangle:  above(jc, 1.02, 0.10) * 2.2 + above(jc / fc, 1.10, 0.15) * 1.6 + near(lr, 1.35, 0.35) * 0.6
    };

    var ranked = Object.keys(scores)
      .map(function (k) { return { id: k, score: scores[k] }; })
      .sort(function (a, b) { return b.score - a.score; });

    var top = ranked[0], second = ranked[1];
    var sum = top.score + second.score;
    var conf = sum > 0 ? top.score / sum : 0.5;
    conf = Math.max(TUNING.CONFIDENCE_FLOOR, Math.min(TUNING.CONFIDENCE_CEIL, conf));

    return { id: top.id, confidence: conf, runnerUp: second.id, ranked: ranked, scores: scores };
  }

  /* --------------------------- crop helper -------------------------- */

  // Square crop centred on the detected face, so the result preview shows the
  // face that was measured rather than the whole photo. Returns the crop plus
  // its offset, which callers subtract from landmark coordinates.
  function cropFace(canvas, box, scale) {
    var side = Math.max(box.width, box.height) * (scale || 2.0);
    side = Math.min(side, canvas.width, canvas.height);
    var cx = box.x + box.width / 2;
    var cy = box.y + box.height / 2;
    var x = Math.round(Math.max(0, Math.min(canvas.width - side, cx - side / 2)));
    var y = Math.round(Math.max(0, Math.min(canvas.height - side, cy - side / 2)));
    side = Math.round(side);

    var out = document.createElement('canvas');
    out.width = side; out.height = side;
    out.getContext('2d').drawImage(canvas, x, y, side, side, 0, 0, side, side);
    return { canvas: out, x: x, y: y, size: side };
  }

  /* ----------------------------- loading ---------------------------- */

  function loadModels(onProgress) {
    if (ready) return ready;
    var step = onProgress || function () {};
    ready = (function () {
      step('library', 0.1);
      return import(/* webpackIgnore: true */ LIB_URL).then(function (mod) {
        api = mod;
        step('detector', 0.35);
        return api.nets.tinyFaceDetector.loadFromUri(MODEL_URL);
      }).then(function () {
        step('landmarks', 0.6);
        return api.nets.faceLandmark68Net.loadFromUri(MODEL_URL);
      }).then(function () {
        step('age', 0.85);
        return api.nets.ageGenderNet.loadFromUri(MODEL_URL);
      }).then(function () {
        step('done', 1);
        return true;
      });
    })().catch(function (err) {
      ready = null; // allow a retry
      throw err;
    });
    return ready;
  }

  /* ---------------------------- analysis ---------------------------- */

  function analyze(media) {
    return loadModels().then(function () {
      var opts = new api.TinyFaceDetectorOptions({ inputSize: 416, scoreThreshold: 0.4 });
      return api.detectAllFaces(media, opts).withFaceLandmarks().withAgeAndGender();
    }).then(function (results) {
      if (!results || !results.length) {
        return { ok: false, error: 'no_face' };
      }

      // Largest face wins if several are present.
      results.sort(function (a, b) {
        return (b.detection.box.width * b.detection.box.height) -
               (a.detection.box.width * a.detection.box.height);
      });
      var r = results[0];
      var box = r.detection.box;

      if (Math.min(box.width, box.height) < TUNING.MIN_FACE_PX) {
        return { ok: false, error: 'face_too_small', faces: results.length };
      }

      var pts = r.landmarks.positions.map(function (p) { return { x: p.x, y: p.y }; });
      var metrics = measure(pts);
      var shape = classify(metrics);

      // The detector often returns several boxes for one face. Count a box as
      // a separate person only when its centre falls outside every box
      // already counted.
      var distinct = [];
      results.forEach(function (d) {
        var b = d.detection.box;
        var cx = b.x + b.width / 2, cy = b.y + b.height / 2;
        var inside = distinct.some(function (k) {
          return cx >= k.x && cx <= k.x + k.width && cy >= k.y && cy <= k.y + k.height;
        });
        if (!inside) distinct.push(b);
      });

      var warnings = [];
      if (TUNING.DUP_FACE_OVERLAP ? distinct.length > 1 : results.length > 1) {
        warnings.push('multiple_faces');
      }
      if (metrics.symmetry < 0.80) warnings.push('head_turned');
      if (Math.min(box.width, box.height) < 160) warnings.push('low_resolution');

      var age = Math.round(r.age);
      return {
        ok: true,
        faces: distinct.length,
        detections: results.length,
        box: { x: box.x, y: box.y, width: box.width, height: box.height },
        landmarks: pts,
        metrics: metrics,
        shape: shape,
        age: age,
        ageLow: Math.max(1, age - TUNING.AGE_BAND),
        ageHigh: age + TUNING.AGE_BAND,
        gender: r.gender,                 // 'male' | 'female' — a guess, always overridable
        genderProbability: r.genderProbability,
        detectionScore: r.detection.score,
        warnings: warnings
      };
    });
  }

  /* --------------------- editorial copy per shape -------------------- */

  var SHAPES = {
    oval: {
      label: 'Oval',
      summary: 'Length is noticeably greater than width, cheekbones are the widest point, and the jaw rounds off softly. The most forgiving shape — almost nothing fights it.',
      men: {
        best: ['Textured crop', 'Mid or low taper fade', 'Classic side part', 'Quiff', 'Buzz cut'],
        avoid: ['Heavy fringe straight across the forehead — it shortens the face and hides the proportion that works for you', 'Very long, flat, centre-parted hair that drags the face longer'],
        beard: 'Short stubble or a trimmed full beard. Keep the chin line squared off rather than pointed.'
      },
      women: {
        best: ['Blunt shoulder-length bob', 'Long layers', 'Curtain bangs', 'Lob with soft movement', 'Pixie with volume on top'],
        avoid: ['Thick, heavy bangs that cover the forehead entirely', 'Flat, one-length hair with no movement at the jaw'],
        beard: null
      }
    },
    round: {
      label: 'Round',
      summary: 'Width and length are close to equal, cheekbones sit at the widest point, and the jaw is soft with no hard corners. The goal of every cut is vertical height and a tighter perimeter.',
      men: {
        best: ['High or mid fade with height on top', 'Pompadour', 'Faux hawk', 'Angular fringe', 'Side part with volume'],
        avoid: ['Buzz cuts at one length — they expose the full width of the face', 'Bowl cuts or a rounded fringe', 'Bulk at the sides'],
        beard: 'A beard is your best structural tool. Keep the sides short and let the chin grow longer to lengthen the face. Avoid round, full cheek growth.'
      },
      women: {
        best: ['Long layers starting below the chin', 'Side-swept or curtain bangs', 'Lob cut at collarbone length', 'Deep side part', 'High ponytail or topknot'],
        avoid: ['Chin-length blunt bob — it widens the face at its widest point', 'Full, straight-across bangs', 'Tight curls set at cheek height'],
        beard: null
      }
    },
    square: {
      label: 'Square',
      summary: 'Forehead, cheekbones and jaw are close to the same width, with a strong, angular jawline. Cuts either lean into that structure or soften it — both work, nothing in between.',
      men: {
        best: ['Crew cut', 'Buzz cut', 'Short textured quiff', 'Side part', 'Classic taper'],
        avoid: ['Very long, heavy hair that hides the jawline', 'Blunt, boxy fringes that repeat the square outline'],
        beard: 'Stubble or a short full beard that follows the jaw. Avoid square, boxed-off beard lines — you already have the angle.'
      },
      women: {
        best: ['Soft, face-framing layers', 'Side part with waves', 'Wavy lob', 'Long curtain bangs', 'Textured shag'],
        avoid: ['Blunt jaw-length bob with no texture', 'Straight-across heavy bangs', 'Severe centre part with flat hair'],
        beard: null
      }
    },
    oblong: {
      label: 'Oblong / Rectangle',
      summary: 'Noticeably longer than it is wide, with the forehead, cheekbones and jaw at similar widths. Every cut should add width at the sides and keep height off the top.',
      men: {
        best: ['Textured fringe or French crop', 'Medium length with side volume', 'Low taper (not a high fade)', 'Side part with fullness at the temples'],
        avoid: ['Pompadours, quiffs and anything with height on top — it stretches the face further', 'Very short sides with long top', 'Slicked-back hair'],
        beard: 'A full beard with width at the cheeks shortens the face. Keep the chin trimmed short — avoid long, pointed goatees.'
      },
      women: {
        best: ['Chin-length bob with waves', 'Blunt fringe or curtain bangs', 'Mid-length cut with layers at the cheekbone', 'Side-swept volume'],
        avoid: ['Long, straight, one-length hair past the chest', 'Centre part with no volume', 'Very high topknots'],
        beard: null
      }
    },
    heart: {
      label: 'Heart',
      summary: 'A wide forehead and cheekbones narrowing to a small, pointed chin. Cuts aim to reduce visual weight up top and add fullness around the jaw.',
      men: {
        best: ['Textured fringe that breaks up the forehead', 'Medium-length with movement', 'Side-swept crop', 'Longer top with soft edges'],
        avoid: ['Slicked-back hair that fully exposes the forehead', 'High and tight fades that narrow the lower face further', 'Very short sides with heavy top volume'],
        beard: 'A fuller beard along the jaw adds the width your chin lacks. Avoid thin goatees that sharpen the point.'
      },
      women: {
        best: ['Chin-length or collarbone lob', 'Side-swept and curtain bangs', 'Layers that start at the jaw', 'Soft waves with volume low down'],
        avoid: ['Tight, slicked-back styles', 'Short pixie cuts with all the volume on top', 'Blunt bangs straight across a wide forehead'],
        beard: null
      }
    },
    diamond: {
      label: 'Diamond',
      summary: 'Cheekbones are clearly the widest point, with a narrower forehead and a narrow, often pointed chin. The rarest shape — the brief is to widen the forehead and jaw while keeping the cheekbones from dominating.',
      men: {
        best: ['Textured fringe or forward-swept crop', 'Medium-length with side fullness', 'Low taper', 'Quiff with width rather than height'],
        avoid: ['Slicked-back styles that expose a narrow forehead', 'High fades that strip width from the sides', 'Centre parts'],
        beard: 'A full beard squares off the chin and balances the cheekbones. Stubble alone leaves the chin looking pointed.'
      },
      women: {
        best: ['Chin-length bob', 'Side-swept bangs or a soft fringe', 'Layers starting at the chin', 'Deep side part', 'Volume at the jaw'],
        avoid: ['Pulling all hair back tightly', 'Heavy layers cut at the cheekbone', 'Very short, sleek crops'],
        beard: null
      }
    },
    triangle: {
      label: 'Triangle / Pear',
      summary: 'The jaw is the widest point, narrowing up through the cheekbones to a smaller forehead. Cuts add volume and width above the eyeline to balance the jaw.',
      men: {
        best: ['Volume on top — quiff, pompadour or a full textured crop', 'High or mid fade to narrow the lower sides', 'Side part with lift at the root'],
        avoid: ['Flat, forward-combed hair', 'Heavy fringes', 'Long hair that hangs level with the jaw'],
        beard: 'Keep it short and tight to the jaw, or clean-shaven. A full beard widens the widest part of your face.'
      },
      women: {
        best: ['Volume and layers above the jaw', 'Short to mid-length cuts with lift at the crown', 'Side-swept bangs', 'Pixie or bob ending above the jaw'],
        avoid: ['Blunt cuts ending exactly at the jawline', 'Flat roots with heavy, dense ends', 'Long one-length hair with no top volume'],
        beard: null
      }
    }
  };

  window.StyleXFace = {
    version: '1.0',
    loadModels: loadModels,
    analyze: analyze,
    cropFace: cropFace,
    TUNING: TUNING,
    SHAPES: SHAPES,
    _internal: { measure: measure, classify: classify, deroll: deroll }
  };
})();
