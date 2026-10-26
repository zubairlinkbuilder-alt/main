#!/usr/bin/env python3
"""Inline the shared CSS and engine into each tool page.

Produces self-contained single-file HTML in dist/ that can be pasted
straight into a WordPress Custom HTML block or saved as a .html page.

    python3 build.py
"""
import pathlib

HERE = pathlib.Path(__file__).parent
SRC = HERE / "src"
DIST = HERE / "dist"

PAGES = ["face-shape.html", "age-test.html", "face-shape-quiz.html"]


def build() -> None:
    css = (SRC / "_ui.css").read_text(encoding="utf-8")
    engine = (SRC / "engine.js").read_text(encoding="utf-8")
    quiz = (SRC / "quiz-engine.js").read_text(encoding="utf-8")
    DIST.mkdir(exist_ok=True)

    for name in PAGES:
        html = (SRC / name).read_text(encoding="utf-8")
        for token, payload in (("/*!INJECT_CSS*/", css),
                               ("/*!INJECT_ENGINE*/", engine),
                               ("/*!INJECT_QUIZ*/", quiz)):
            if token not in html:
                # only the quiz page needs the quiz engine
                if token == "/*!INJECT_QUIZ*/":
                    continue
                raise SystemExit(f"{name}: missing {token}")
            html = html.replace(token, payload)
        out = DIST / name
        out.write_text(html, encoding="utf-8")
        print(f"{out.relative_to(HERE)}  {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    build()
