#!/usr/bin/env python3
"""Make Elementor-ready versions of the built pages.

An Elementor HTML widget sits inside an existing document, so the page
skeleton has to go, and the theme's own CSS will reach into whatever you
paste. This strips the skeleton and prepends defensive resets scoped to
.sx-tool so a theme cannot restyle the tool's buttons, tables or inputs.

    python3 build-elementor.py
"""
import pathlib
import re

HERE = pathlib.Path(__file__).parent
DIST = HERE / "dist"
OUT = DIST / "elementor"

PAGES = ["age-test.html", "face-shape-quiz.html", "face-shape.html"]

# Scoped resets. These go BEFORE the tool's own CSS, so the tool's rules win
# on equal specificity while the theme's rules do not.
RESET = """<style>
/* ---------------------------------------------------------------
   Theme guards for Elementor.

   A theme styles bare elements globally and often with !important,
   which reaches straight into anything you paste into an HTML
   widget. Part 1 normalises; part 2 forces the handful of
   properties themes commonly !important. Everything is scoped to
   .sx-tool, so nothing here touches the rest of your page.
   --------------------------------------------------------------- */

/* 1. Normalisation */
.sx-tool, .sx-tool *, .sx-tool *::before, .sx-tool *::after { box-sizing: border-box; }
.sx-tool [hidden] { display: none !important; }
.sx-tool button { font-family: inherit; font-size: inherit; margin: 0; }
.sx-tool input { font-family: inherit; margin: 0; max-width: 100%; height: auto; }
.sx-tool table { border-collapse: collapse; width: 100%; }
.sx-tool th, .sx-tool td { vertical-align: top; }
.sx-tool img, .sx-tool video, .sx-tool canvas { max-width: 100%; height: auto; }
.sx-tool details summary { list-style: none; }
.sx-tool details summary::-webkit-details-marker { display: none; }

/* Component lists carry no markers; prose lists keep theirs. */
.sx-tool ul, .sx-tool ol { margin: 0; padding: 0; }
.sx-tool .sx-list, .sx-tool .sx-opts, .sx-tool .sx-bars,
.sx-tool .sx-links, .sx-tool .sx-chips, .sx-tool .sx-steps,
.sx-tool .sx-metrics { list-style: none !important; padding-left: 0 !important; }
.sx-tool .sx-prose ul { list-style: disc !important; padding-left: 1.2em !important; margin: 0 0 1em !important; }
.sx-tool .sx-prose ol { list-style: decimal !important; padding-left: 1.2em !important; margin: 0 0 1em !important; }
.sx-tool .sx-prose li { margin-bottom: .45em; }

/* 2. Hard guards against theme !important */
.sx-tool, .sx-tool p, .sx-tool li, .sx-tool td, .sx-tool span, .sx-tool strong {
  color: inherit;
}
.sx-tool h1, .sx-tool h2, .sx-tool h3 {
  text-transform: none !important;
  letter-spacing: -.01em !important;
  color: var(--sx-text) !important;
}
.sx-tool p, .sx-tool li { font-size: inherit; }
.sx-tool .sx-prose p, .sx-tool .sx-prose li { font-size: .95rem !important; color: var(--sx-text) !important; }
.sx-tool th, .sx-tool td { background: none !important; border-color: var(--sx-border) !important; }
.sx-tool table { background: none !important; border: 0 !important; }

.sx-tool .sx-btn {
  background: var(--sx-accent) !important;
  color: var(--sx-accent-text) !important;
  border: 1px solid var(--sx-accent) !important;
  border-radius: 999px !important;
  text-transform: none !important;
  letter-spacing: normal !important;
  width: auto !important;
  box-shadow: none !important;
  font-family: inherit !important;
}
.sx-tool .sx-btn--ghost {
  background: transparent !important;
  color: var(--sx-text) !important;
  border-color: var(--sx-border) !important;
}
.sx-tool .sx-toggle button, .sx-tool .sx-tabs button, .sx-tool .sx-opt {
  background: transparent !important;
  border-radius: inherit;
  text-transform: none !important;
  letter-spacing: normal !important;
  width: auto !important;
  box-shadow: none !important;
  border: 0;
}
.sx-tool .sx-opt {
  width: 100% !important;
  border: 1.5px solid var(--sx-border) !important;
  border-radius: 12px !important;
  background: var(--sx-bg) !important;
}
.sx-tool .sx-opt[aria-pressed="true"] { background: var(--sx-surface) !important; border-color: var(--sx-accent) !important; }
.sx-tool .sx-toggle button[aria-pressed="true"] { background: var(--sx-accent) !important; color: var(--sx-accent-text) !important; }
.sx-tool .sx-tabs button[aria-selected="true"] { background: var(--sx-bg) !important; }
.sx-tool .sx-tabs { background: var(--sx-surface-2) !important; }

.sx-tool a:not(.sx-btn) {
  color: var(--sx-ink) !important;
  text-decoration: none !important;
  font-size: inherit !important;
  box-shadow: none !important;
}
.sx-tool a.sx-btn { color: var(--sx-accent-text) !important; text-decoration: none !important; }
.sx-tool .sx-crumbs a { color: var(--sx-muted) !important; }

.sx-tool input {
  border: 1px solid var(--sx-border) !important;
  background: var(--sx-surface-2) !important;
  color: var(--sx-text) !important;
  padding: 12px 14px !important;
  width: 100% !important;
  max-width: 190px !important;
  box-shadow: none !important;
}
.sx-tool .sx-app-head { background: var(--sx-brand-ink) !important; }
.sx-tool .sx-app-head strong, .sx-tool .sx-app-head span { color: #fff !important; }
.sx-tool .sx-app-head .sx-app-sub { color: #C9CCE4 !important; }
.sx-tool .sx-pill { background: var(--sx-accent) !important; color: var(--sx-brand-ink) !important; }
</style>
"""


def strip_skeleton(html: str) -> str:
    # everything before the first <style> is document head, which a widget
    # must not carry: no doctype, no <title>, no <meta>.
    start = html.index("<style>")
    html = html[start:]

    # the standalone-page style block only exists for the .html file
    html = re.sub(
        r"<style>\n/\* Standalone page only\..*?</style>\n",
        "",
        html,
        flags=re.S,
    )

    html = html.replace("</head>\n", "").replace("<body>\n", "")
    html = html.replace("\n</body>\n</html>\n", "\n")

    for banned in ("<!doctype", "<html", "<head", "<body", "<title>", "<meta "):
        if banned in html.lower():
            raise SystemExit(f"skeleton leftover: {banned}")
    return html


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in PAGES:
        html = RESET + strip_skeleton((DIST / name).read_text(encoding="utf-8"))
        target = OUT / name.replace(".html", "-elementor.html")
        target.write_text(html, encoding="utf-8")
        print(f"{target.relative_to(HERE)}  {target.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
