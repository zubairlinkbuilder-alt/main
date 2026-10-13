"""Offline end-to-end test: fake websites served through a patched HTTP layer.
Run from outreach-tool/:  python -m tests.test_pipeline
"""
import json
import os
import sys
import tempfile
from datetime import date

os.environ["OUTREACH_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db, emailfinder, jobs, mailer, net, scanner  # noqa: E402

WP_POSTS = [
    {"link": "https://wpblog.com/post-a", "title": {"rendered": "Post &amp; A"}, "date_gmt": "2026-10-05T10:00:00",
     "content": {"rendered": '<p>See <a href="https://toolsite.io/guide?utm_source=x">this guide</a>, '
                             '<a href="https://www.facebook.com/page">fb</a>, <a href="https://deadsite.net/gone">old</a>, '
                             '<a href="/about">internal</a>, <a href="https://blog.wpblog.com/x">sub-internal</a>, '
                             '<a href="https://moved.com/a">moved</a>.</p>'}},
    {"link": "https://wpblog.com/post-b", "title": {"rendered": "Post B"}, "date_gmt": "2026-10-01T10:00:00",
     "content": {"rendered": '<p><a href="https://toolsite.io/other">again</a></p>'}},
]
RSS = """<?xml version="1.0"?><rss><channel>
<item><title>In range</title><link>https://rssblog.com/in</link><pubDate>Mon, 06 Oct 2026 09:00:00 +0000</pubDate></item>
<item><title>Too old</title><link>https://rssblog.com/old</link><pubDate>Mon, 01 Jun 2026 09:00:00 +0000</pubDate></item>
</channel></rss>"""
RSS_ARTICLE = """<html><head><meta property="article:published_time" content="2026-10-06T09:00:00Z"></head><body>
<nav><a href="https://navlink.com">nav</a></nav>
<article><div class="entry-content"><p>Body <a href="https://gmailowner.org/post">owner</a></p>
<div class="sharedaddy"><a href="https://sharer.com/x">share</a></div></div></article>
<aside class="sidebar"><a href="https://sidebarad.com">ad</a></aside><footer><a href="https://footer.com">f</a></footer></body></html>"""
SM_INDEX = """<?xml version="1.0"?><sitemapindex><sitemap><loc>https://smblog.com/post-sitemap.xml</loc><lastmod>2026-10-08</lastmod></sitemap>
<sitemap><loc>https://smblog.com/tag-sitemap.xml</loc></sitemap></sitemapindex>"""
SM_POSTS = """<?xml version="1.0"?><urlset>
<url><loc>https://smblog.com/fresh</loc><lastmod>2026-10-08</lastmod></url>
<url><loc>https://smblog.com/updated-old</loc><lastmod>2026-10-07</lastmod></url>
<url><loc>https://smblog.com/no-date</loc><lastmod>2026-10-07</lastmod></url>
<url><loc>https://smblog.com/ancient</loc><lastmod>2025-01-01</lastmod></url></urlset>"""

def page(date_meta, body):
    m = f'<script type="application/ld+json">{{"@graph":[{{"@type":"Article","datePublished":"{date_meta}"}}]}}</script>' if date_meta else ""
    return f"<html><head>{m}</head><body><main>{body}</main></body></html>"

ROUTES = {
    "https://wpblog.com/wp-json/wp/v2/posts": (200, json.dumps(WP_POSTS), "application/json"),
    "https://rssblog.com/": (200, '<html><head><link rel="alternate" type="application/rss+xml" href="/feed/"></head></html>', "text/html"),
    "https://rssblog.com/feed/": (200, RSS, "application/rss+xml"),
    "https://rssblog.com/in": (200, RSS_ARTICLE, "text/html"),
    "https://smblog.com/robots.txt": (200, "User-agent: *\nSitemap: https://smblog.com/sitemap_index.xml", "text/plain"),
    "https://smblog.com/sitemap_index.xml": (200, SM_INDEX, "application/xml"),
    "https://smblog.com/post-sitemap.xml": (200, SM_POSTS, "application/xml"),
    "https://smblog.com/fresh": (200, page("2026-10-08T08:00:00+00:00", '<a href="https://obfus.net/x">x</a>'), "text/html"),
    "https://smblog.com/updated-old": (200, page("2024-03-01T08:00:00+00:00", '<a href="https://shouldnot.com">x</a>'), "text/html"),
    "https://smblog.com/no-date": (200, page(None, '<a href="https://nodate.com">x</a>'), "text/html"),
    # prospects
    "https://toolsite.io/guide": (200, "ok", "text/html"),
    "https://toolsite.io/other": (200, "ok", "text/html"),
    "https://deadsite.net/gone": (404, "nope", "text/html"),
    "https://gmailowner.org/post": (200, "ok", "text/html"),
    "https://obfus.net/x": (200, "ok", "text/html"),
    "https://toolsite.io/": (200, '<html><head><meta property="og:site_name" content="Tool Site"></head><body>'
                                 '<a href="/contact-us">Contact</a> <img src="logo@2x.png"> sentry 1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d@o1.ingest.sentry.io</body></html>', "text/html"),
    "https://toolsite.io/contact-us": (200, '<a href="mailto:Editor@ToolSite.io?subject=hi">mail</a> '
                                           '<a href="/cdn-cgi/l/email-protection#' + "42" + "".join(f"{b ^ 0x42:02x}" for b in b"hello@toolsite.io") + '">[email protected]</a>'
                                           ' theme by support@themevendor.com', "text/html"),
    "https://gmailowner.org/": (200, "<p>Reach me: owner.name [at] gmail [dot] com. Built with noreply@gmailowner.org</p>", "text/html"),
    "https://obfus.net/": (200, "<p>nothing here, use the form</p>", "text/html"),
}
REDIRECTS = {"https://moved.com/a": "https://newhome.com/a"}

class Resp:
    def __init__(self, url, code, body, ctype):
        self.url, self.status_code, self.text, self.content = url, code, body, body.encode()
        self.headers = {"Content-Type": ctype}
    def json(self): return json.loads(self.text)
    def close(self): pass

def fake_get(url, timeout=20, **kw):
    if url in REDIRECTS:
        return Resp(REDIRECTS[url], 200, "ok", "text/html")
    key = url.split("?")[0]
    if key in ROUTES:
        return Resp(url, *ROUTES[key])
    if key.endswith("/") and key.rstrip("/") in ROUTES:
        return Resp(url, *ROUTES[key.rstrip("/")])
    return Resp(url, 404, "not found", "text/html")

class FakeSession:
    def get(self, url, **kw): return fake_get(url, **kw)
    def head(self, url, **kw): return fake_get(url, **kw)

net.fetch = fake_get
net.session = lambda: FakeSession()
emailfinder.has_mx = lambda d: d != "deadmail.xyz"

class J(jobs.Job):
    cancelled = False
    def log(self, m): print(m)
    def progress(self, *a): pass

def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        check.failed = True
check.failed = False

db.init()
with db.conn() as c:
    for u in ["https://wpblog.com", "https://rssblog.com", "https://smblog.com"]:
        c.execute("INSERT INTO websites(url,domain,added_at) VALUES (?,?,?)", (u, net.registered_domain(u), db.now()))
    ids = [r[0] for r in c.execute("SELECT id FROM websites")]

jobs.scan_websites(J(0), ids, date(2026, 10, 1), date(2026, 10, 13), 30, False, True)

with db.conn() as c:
    arts = {r["url"]: r for r in c.execute("SELECT * FROM articles")}
    links = [dict(r) for r in c.execute("SELECT * FROM links")]
    pros = {r["domain"]: dict(r) for r in c.execute("SELECT * FROM prospects")}

print()
check(set(arts) == {"https://wpblog.com/post-a", "https://wpblog.com/post-b", "https://rssblog.com/in", "https://smblog.com/fresh"},
      f"only in-range articles kept: {sorted(arts)}")
check(arts["https://wpblog.com/post-a"]["title"] == "Post & A", "WP title HTML-decoded")
dl = {l["url"]: l for l in links}
check("https://toolsite.io/guide" in dl, "utm params stripped from link")
check(not any("facebook" in l["url"] for l in links), "blocklisted facebook excluded")
check(not any("wpblog.com" in l["domain"] for l in links), "internal + subdomain links excluded")
check(dl["https://deadsite.net/gone"]["verdict"] == "dead", "404 link marked dead")
check("deadsite.net" not in pros, "dead link not a prospect")
check("newhome.com" in pros and "moved.com" not in pros, "redirect followed to real domain")
rss_links = {l["domain"] for l in links if l["article_id"] == arts["https://rssblog.com/in"]["id"]}
check(rss_links == {"gmailowner.org"}, f"nav/sidebar/footer/share links stripped: {rss_links}")
check("shouldnot.com" not in pros and "nodate.com" not in pros, "sitemap: old/undated pages rejected")
check(pros["toolsite.io"]["best_email"] in ("editor@toolsite.io", "hello@toolsite.io"), f"toolsite best = {pros['toolsite.io']['best_email']}")
te = {e["email"] for e in json.loads(pros["toolsite.io"]["emails"])}
check(te == {"editor@toolsite.io", "hello@toolsite.io"}, f"mailto + cloudflare decoded, junk/vendor dropped: {te}")
check(pros["toolsite.io"]["site_name"] == "Tool Site", "site name read")
check(pros["gmailowner.org"]["best_email"] == "owner.name@gmail.com", f"obfuscated gmail decoded, noreply dropped: {pros['gmailowner.org']['best_email']}")
check(pros["obfus.net"]["status"] == "not_found", "no-email site honestly marked not_found")

# Drafts / templates
import app as webapp  # noqa: E402
db.set_settings({"my_name": "Zubair", "my_website": "mysite.com"})
made, skipped = webapp.create_drafts(list(r["id"] for r in pros.values()), None)
with db.conn() as c:
    outs = [dict(r) for r in c.execute("SELECT * FROM outreach")]
check(made == 2 and len(outs) == 2, f"drafts only for prospects with email (made={made}, skipped={skipped})")
o = next(x for x in outs if x["to_email"].endswith("toolsite.io"))
check("Tool Site team" in o["body"] and "https://wpblog.com/post-" in o["body"] and "{{" not in o["body"] and "Zubair" in o["body"],
      "template variables filled")
made2, _ = webapp.create_drafts(list(r["id"] for r in pros.values()), None)
check(made2 == 0, "no duplicate drafts for same email")
check(mailer.unknown_vars("Hi {{site_name}} {{firstname}}") == ["firstname"], "unknown template variable detected")

# Sending with a fake SMTP
sent = []
class FakeSender:
    def __init__(self, s): pass
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def send(self, to, subj, body): sent.append(to)
mailer.Sender = FakeSender
db.set_settings({"send_delay_seconds": "0", "daily_send_limit": "1"})
with db.conn() as c:
    c.execute("UPDATE outreach SET status='approved'")
jobs.send_approved(J(0), [])
check(len(sent) == 1, f"daily limit respected ({len(sent)} sent)")
with db.conn() as c:
    st = sorted(r[0] for r in c.execute("SELECT status FROM outreach"))
check(st == ["approved", "sent"], f"unsent stays approved for tomorrow: {st}")

# Web UI smoke test
client = webapp.app.test_client()
for path in ["/", "/websites", "/scan", "/articles", f"/articles/{arts['https://wpblog.com/post-a']['id']}", "/prospects",
             f"/prospects/{pros['toolsite.io']['id']}", "/outreach", f"/outreach/{o['id']}", "/templates", "/templates/1",
             "/templates/new", "/blocklist", "/settings"]:
    r = client.get(path)
    check(r.status_code == 200, f"GET {path} -> {r.status_code}")
r = client.post("/blocklist", data={"domains": "https://www.spam.com/page\ncompetitor.org"})
check(db.is_blocked("spam.com") and db.is_blocked("blog.competitor.org"), "blocklist add (URL + subdomain match)")

sys.exit(1 if check.failed else 0)
