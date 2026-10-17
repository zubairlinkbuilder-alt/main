#!/usr/bin/env python3
"""List the exercise sections in a WordPress export, for planning GIF purchases.

Usage: python3 extract_exercises.py export.xml [out.csv]

Reads a WordPress export (Tools → Export → Posts), and for every published post
writes one row per H2/H3 heading: article, URL, heading, whether that section
has an image, the image file and its alt text. Headings that are plainly not
exercises (FAQ, conclusion, sets and reps tables, ...) are marked so they can
be filtered out.
"""

import csv
import re
import sys
import xml.etree.ElementTree as ET
from html import unescape

NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "wp": "http://wordpress.org/export/1.2/",
}

NOT_EXERCISE = re.compile(
    r"\?|\b(?:faqs?|frequently|conclusion|summary|takeaway|quick answer|how to|why|what|when|"
    r"benefits?|mistakes?|tips?|safety|warm|sample|workout plan|routine|sets? and reps|"
    r"choose|choosing|weight|ball size|final|bottom line|who should|program|schedule|"
    r"related|references|sources|about the author)\b",
    re.I,
)

HEADING = re.compile(r"<h([23])[^>]*>(.*?)</h\1>", re.I | re.S)
IMG = re.compile(r"<img\b[^>]*>", re.I)
ATTR = re.compile(r'(src|alt)\s*=\s*"([^"]*)"', re.I)


def text(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", html))).strip()


def clean_heading(heading):
    # "3. Medicine Ball Squat" / "Exercise 3: Medicine Ball Squat" -> "Medicine Ball Squat"
    return re.sub(r"^(exercise\s*)?#?\d+[.):\-–]?\s*", "", heading, flags=re.I).strip()


def sections(html):
    """Yields (level, heading, section_html) for each H2/H3."""
    marks = list(HEADING.finditer(html))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(html)
        yield m.group(1), text(m.group(2)), html[m.end():end]


def rows(xml_path):
    root = ET.parse(xml_path).getroot()
    for item in root.iter("item"):
        if item.findtext("wp:post_type", namespaces=NS) != "post":
            continue
        if item.findtext("wp:status", namespaces=NS) != "publish":
            continue
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        html = item.findtext("content:encoded", namespaces=NS) or ""
        for level, heading, body in sections(html):
            imgs = [dict(ATTR.findall(tag)) for tag in IMG.findall(body)]
            yield {
                "article": title,
                "url": link,
                "level": "H" + level,
                "heading": heading,
                "exercise": "" if NOT_EXERCISE.search(heading) else clean_heading(heading),
                "images": len(imgs),
                "image_file": " | ".join(i.get("src", "").rsplit("/", 1)[-1] for i in imgs),
                "image_alt": " | ".join(i.get("alt", "") for i in imgs),
            }


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    out = sys.argv[2] if len(sys.argv) > 2 else "exercise-sections.csv"
    data = list(rows(sys.argv[1]))
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(data[0].keys()) if data else ["article"])
        writer.writeheader()
        writer.writerows(data)
    exercises = [r for r in data if r["exercise"]]
    print(f"{len({r['url'] for r in data})} articles, {len(exercises)} exercise sections -> {out}")


if __name__ == "__main__":
    main()
