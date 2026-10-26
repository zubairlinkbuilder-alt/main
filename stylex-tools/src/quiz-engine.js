/*!
 * StyleX Face Shape Quiz v1.0
 *
 * Seven questions, no mirror maths and no photo. Each answer carries weights
 * across the seven shapes; the weights are summed and the highest total wins.
 * When the top two finish close, both are reported, because most faces really
 * do sit between two shapes.
 *
 * Exposes: window.StyleXQuiz
 *   .QUESTIONS   the question set
 *   .score(answers) -> { id, label, confidence, runnerUp, close, ranked }
 *   .CLOSE_MARGIN
 */
(function () {
  'use strict';

  // Two shapes within this fraction of each other are reported as a split.
  var CLOSE_MARGIN = 0.12;

  var LABELS = {
    oval: 'Oval', round: 'Round', square: 'Square', oblong: 'Oblong',
    heart: 'Heart', diamond: 'Diamond', triangle: 'Triangle'
  };

  /* Each option's `w` maps shape -> weight. Weights are deliberately uneven:
     a jaw that is the widest part of the face is near-decisive for triangle,
     while a rounded hairline only nudges round and oval. */
  var QUESTIONS = [
    {
      id: 'length',
      q: 'Is your face longer than it is wide?',
      hint: 'Pull your hair back and look straight into a mirror. Compare the distance from hairline to chin against the width across your cheekbones.',
      options: [
        { t: 'Clearly longer', d: 'Noticeably taller than wide, about one and a half times or more',
          w: { oblong: 4.5, oval: 1.2, diamond: 0.8 } },
        { t: 'A little longer', d: 'Taller than wide, but not dramatically',
          w: { oval: 2.4, heart: 1.0, diamond: 1.0, oblong: 0.6 } },
        { t: 'About the same', d: 'Roughly as wide as it is long',
          w: { round: 3.0, square: 3.0 } }
      ]
    },
    {
      id: 'widest',
      q: 'Which part of your face is widest?',
      hint: 'Measure by eye across three lines: the forehead at the hairline, the cheekbones under the outer corners of your eyes, and the jaw at its widest.',
      options: [
        { t: 'My forehead', d: 'Widest at the top, narrowing downward',
          w: { heart: 3.0, oval: 0.5, diamond: 0.3 } },
        { t: 'My cheekbones', d: 'Widest across the middle of the face',
          w: { diamond: 2.6, oval: 1.4, round: 1.0 } },
        { t: 'My jaw', d: 'Widest at the bottom, narrowing upward',
          w: { triangle: 3.4, square: 0.8 } },
        { t: 'All three look about equal', d: 'No single part stands out',
          w: { square: 1.8, oblong: 1.8, round: 1.0 } }
      ]
    },
    {
      id: 'jaw',
      q: 'How would you describe your jawline?',
      hint: 'Run a finger from below your ear to your chin and notice the shape it traces.',
      options: [
        { t: 'Sharp and angular', d: 'Clear corners where it turns toward the chin',
          w: { square: 3.2, oblong: 1.6, triangle: 0.6 } },
        { t: 'Soft and curved', d: 'No corners, one continuous curve',
          w: { round: 2.8, oval: 1.6 } },
        { t: 'Narrow, tapering to the chin', d: 'Clearly narrower than my cheekbones',
          w: { heart: 2.2, diamond: 2.2, oval: 0.6 } },
        { t: 'Wide and heavy', d: 'The strongest line on my face',
          w: { triangle: 3.0, square: 1.2 } }
      ]
    },
    {
      id: 'chin',
      q: 'What shape is your chin?',
      hint: 'Look at the very bottom of your face, ignoring your jaw for a moment.',
      options: [
        { t: 'Pointed', d: 'Comes to a visible point',
          w: { heart: 2.6, diamond: 2.4, oval: 0.4 } },
        { t: 'Rounded', d: 'Curved with no point or corners',
          w: { round: 2.4, oval: 1.6 } },
        { t: 'Square or flat', d: 'Broad and level across the bottom',
          w: { square: 2.4, oblong: 2.0, triangle: 1.2 } }
      ]
    },
    {
      id: 'forehead',
      q: 'How wide is your forehead?',
      hint: 'Compare it against the rest of your face, not against other people.',
      options: [
        { t: 'Wide', d: 'One of the broadest parts of my face',
          w: { heart: 2.4, square: 1.0, round: 0.8, oblong: 0.6 } },
        { t: 'Narrow', d: 'Noticeably narrower than my cheekbones',
          w: { diamond: 2.4, triangle: 1.8 } },
        { t: 'Average', d: 'Neither stands out nor disappears',
          w: { oval: 1.6, oblong: 1.0, round: 0.6, square: 0.6 } }
      ]
    },
    {
      id: 'hairline',
      q: 'What does your hairline look like?',
      hint: 'If your hairline has receded, answer for the shape it traces rather than how high it sits.',
      options: [
        { t: 'Rounded', d: 'Curves in a smooth arc',
          w: { round: 1.8, oval: 1.4 } },
        { t: 'Straight across', d: 'Runs roughly level from side to side',
          w: { square: 1.8, oblong: 1.8 } },
        { t: 'A widow’s peak', d: 'Dips to a point in the middle',
          w: { heart: 2.6, diamond: 0.8 } }
      ]
    },
    {
      id: 'cheeks',
      q: 'How prominent are your cheekbones?',
      hint: 'Place two fingers under the outer corner of each eye and press gently.',
      options: [
        { t: 'Very prominent', d: 'They stand out as the widest, highest point',
          w: { diamond: 3.0, oval: 0.6 } },
        { t: 'Softly rounded', d: 'There, but they blend into my cheeks',
          w: { round: 2.4, oval: 1.0 } },
        { t: 'Flat', d: 'Roughly in line with my jaw',
          w: { square: 1.8, oblong: 1.8, triangle: 1.0 } },
        { t: 'A little wider than my jaw', d: 'Slightly the widest, but not striking',
          w: { oval: 2.2, heart: 0.8 } }
      ]
    }
  ];

  /**
   * answers: an object of questionId -> option index, or an array in question
   * order. Unanswered questions simply contribute nothing.
   */
  function score(answers) {
    var totals = { oval: 0, round: 0, square: 0, oblong: 0, heart: 0, diamond: 0, triangle: 0 };

    QUESTIONS.forEach(function (question, qi) {
      var pick = Array.isArray(answers) ? answers[qi] : answers[question.id];
      if (pick === undefined || pick === null) return;
      var option = question.options[pick];
      if (!option) return;
      Object.keys(option.w).forEach(function (shape) {
        totals[shape] += option.w[shape];
      });
    });

    var ranked = Object.keys(totals)
      .map(function (k) { return { id: k, label: LABELS[k], score: totals[k] }; })
      .sort(function (a, b) { return b.score - a.score; });

    var top = ranked[0], second = ranked[1];
    var sum = top.score + second.score;
    var confidence = sum > 0 ? top.score / sum : 0.5;
    var close = top.score > 0 && (top.score - second.score) / top.score < CLOSE_MARGIN;

    return {
      id: top.id,
      label: top.label,
      confidence: confidence,
      runnerUp: second.id,
      runnerUpLabel: second.label,
      close: close,
      ranked: ranked
    };
  }

  window.StyleXQuiz = {
    version: '1.0',
    QUESTIONS: QUESTIONS,
    LABELS: LABELS,
    CLOSE_MARGIN: CLOSE_MARGIN,
    score: score
  };
})();
