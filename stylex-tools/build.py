#!/usr/bin/env python3
"""Inline the shared CSS and engine into each tool page.

Produces self-contained single-file HTML in dist/ that can be pasted
straight into a WordPress Custom HTML block or saved as a .html page.

    python3 build.py
"""
import json
import pathlib

HERE = pathlib.Path(__file__).parent
SRC = HERE / "src"
DIST = HERE / "dist"

PAGES = ["face-shape.html", "age-test.html", "face-shape-quiz.html"]


def breadcrumb(links: dict, page_name: str) -> str:
    """Static breadcrumb. A URL that is null renders as plain text, never as a
    link to a page that may not exist."""
    parts = []
    if links.get("home"):
        parts.append(f'<a href="{links["home"]}">StyleX Magazine</a>')
    else:
        parts.append("StyleX Magazine")
    if links.get("tools"):
        parts.append(f'<a href="{links["tools"]}">Tools</a>')
    parts.append(f'<span aria-current="page">{page_name}</span>')
    return " \u203a\n    ".join(parts)


def linkify_shapes(html: str, links: dict) -> str:
    """Turn <strong data-shape="oval">Oval</strong> into a link when that
    shape has a live article, and leave it as plain text when it does not."""
    shapes = links.get("shapes") or {}
    for shape, url in shapes.items():
        marker = f'<strong data-shape="{shape}">'
        start = html.find(marker)
        if start == -1:
            continue
        end = html.find("</strong>", start)
        label = html[start + len(marker):end]
        old = html[start:end + len("</strong>")]
        new = (f'<a href="{url}"><strong>{label}</strong></a>' if url
               else f"<strong>{label}</strong>")
        html = html.replace(old, new, 1)
    return html


def build() -> None:
    links = json.loads((SRC / "links.json").read_text(encoding="utf-8"))
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
        if "<!--BREADCRUMB-->" in html:
            page_name = {
                "face-shape-quiz.html": "Face Shape Quiz",
                "age-test.html": "How Old Do I Look",
                "face-shape.html": "Face Shape Detector",
            }[name]
            html = html.replace("<!--BREADCRUMB-->", breadcrumb(links, page_name))
        html = linkify_shapes(html, links)
        html = html.replace("/*!INJECT_LINKS*/", json.dumps(links))

        for placeholder, key in (("{{CALCULATOR}}", "calculator"),
                                 ("{{HOME}}", "home")):
            if placeholder in html:
                url = links.get(key)
                if not url:
                    raise SystemExit(f"{name}: {placeholder} has no URL in links.json")
                html = html.replace(placeholder, url)

        if "{{" in html or "<!--BREADCRUMB-->" in html:
            raise SystemExit(f"{name}: unresolved placeholder remains")

        out = DIST / name
        out.write_text(html, encoding="utf-8")
        print(f"{out.relative_to(HERE)}  {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    build()
