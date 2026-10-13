"""Collect contact emails from a prospect's website.

Sources, most to least reliable: mailto: links, Cloudflare-protected emails, JSON-LD "email",
then plain-text addresses (including "name [at] site [dot] com" obfuscation). Every result is
checked for a valid shape and junk patterns, and optionally for MX records on its domain.
"""
import json
import re
from urllib.parse import urljoin, urlparse, unquote

from bs4 import BeautifulSoup

import net

try:
    import dns.resolver
except ImportError:  # dnspython optional
    dns = None

EMAIL_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._%+\-]{0,63}@[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9\-]{1,63})*\.[a-zA-Z]{2,24}")
# "name [at] site [dot] com" / "name(at)site.com". Bare " at " / " dot " is not accepted:
# "read more at example.com" would otherwise become an address.
_DOT = r"(?:\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*|\.)"
OBFUSCATED_RE = re.compile(
    r"([a-zA-Z0-9._%+\-]+)\s*[\[\(\{]\s*at\s*[\]\)\}]\s*([a-zA-Z0-9\-]+(?:" + _DOT + r"[a-zA-Z0-9\-]+)+)", re.I)

CONTACT_HINTS = ("contact", "about", "write-for-us", "write for us", "advertise", "advertising",
                 "guest-post", "contribute", "team", "imprint", "impressum", "work-with", "partnership")
GUESS_PATHS = ["/contact", "/contact-us", "/about", "/about-us", "/write-for-us", "/advertise"]
MAX_PAGES = 9

BAD_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js", ".ico", ".pdf", ".mp4", ".avif")
BAD_DOMAINS = {"example.com", "example.org", "domain.com", "yourdomain.com", "email.com", "test.com",
               "sentry.io", "wixpress.com", "sentry.wixpress.com", "sentry-next.wixpress.com",
               "mysite.com", "yoursite.com", "website.com", "company.com", "godaddy.com", "placeholder.com",
               "ingest.sentry.io", "2x.png", "latofonts.com", "typekit.com"}
BAD_LOCAL = {"noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon", "postmaster",
             "abuse", "yourname", "your-name", "name", "user", "username", "email", "youremail",
             "john.doe", "jane.doe", "johndoe", "test", "privacy-noreply"}
PREFERRED_LOCAL = ("editor", "editorial", "contact", "hello", "hi", "info", "partnership", "partner",
                   "marketing", "outreach", "pr", "press", "media", "team", "admin", "office", "support")
FREE_MAIL = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "aol.com", "proton.me",
             "protonmail.com", "live.com", "ymail.com", "zoho.com", "gmx.com", "mail.com"}

_mx_cache = {}


def has_mx(domain):
    if dns is None:
        return None
    if domain in _mx_cache:
        return _mx_cache[domain]
    ok = False
    try:
        ok = len(dns.resolver.resolve(domain, "MX", lifetime=8)) > 0
    except dns.resolver.NoAnswer:
        try:  # RFC 5321: no MX -> mail goes to the A record
            ok = len(dns.resolver.resolve(domain, "A", lifetime=8)) > 0
        except Exception:
            ok = False
    except Exception:
        ok = False
    _mx_cache[domain] = ok
    return ok


def clean_email(raw):
    e = unquote(raw).strip().strip(".,;:'\"()<>[]{}").lower()
    e = e.split("?")[0]
    if e.startswith("mailto:"):
        e = e[7:]
    if not EMAIL_RE.fullmatch(e):
        return None
    local, _, dom = e.rpartition("@")
    if e.endswith(BAD_EXT) or dom in BAD_DOMAINS or local in BAD_LOCAL:
        return None
    if re.search(r"@\d+x\.", e) or re.fullmatch(r"[0-9a-f]{24,}", local):  # retina image names, sentry keys
        return None
    return e


def decode_cfemail(hexstr):
    try:
        key = int(hexstr[:2], 16)
        return "".join(chr(int(hexstr[i:i + 2], 16) ^ key) for i in range(2, len(hexstr), 2))
    except (ValueError, IndexError):
        return None


def emails_in_html(html):
    """Return {email: source} found in one HTML page."""
    found = {}
    soup = BeautifulSoup(html, "lxml")

    def add(e, src):
        e = clean_email(e) if e else None
        if e and (e not in found or src == "mailto"):
            found[e] = src

    for a in soup.find_all("a", href=True):
        h = a["href"].strip()
        if h.lower().startswith("mailto:"):
            for part in unquote(h[7:]).split("?")[0].split(","):
                add(part, "mailto")
        if "/cdn-cgi/l/email-protection#" in h:
            add(decode_cfemail(h.split("#", 1)[1]), "mailto")
    for n in soup.select("[data-cfemail]"):
        add(decode_cfemail(n["data-cfemail"]), "mailto")
    for s in soup.find_all("script", type="application/ld+json"):
        for m in re.findall(r'"email"\s*:\s*"([^"]+)"', s.string or ""):
            add(m, "schema")
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    text = soup.get_text(" ")
    for m in EMAIL_RE.findall(text):
        add(m, "text")
    for user, rest in OBFUSCATED_RE.findall(text):
        dom = re.sub(_DOT, ".", rest, flags=re.I)
        if "." in dom:
            add(f"{user}@{dom}", "obfuscated")
    return found, soup


def score(email, source, page_kind, site_domain):
    local, _, dom = email.partition("@")
    s = {"mailto": 30, "schema": 25, "text": 15, "obfuscated": 10}.get(source, 0)
    if net.registered_domain(dom) == site_domain:
        s += 50
    elif dom in FREE_MAIL:
        s += 15  # site owner's personal Gmail etc. is common on small blogs
    if page_kind == "contact":
        s += 10
    if any(local == p or local.startswith(p) for p in PREFERRED_LOCAL):
        s += 10
    return s


def find_emails(homepage, timeout=20, verify_mx=True, log=lambda m: None):
    """Crawl homepage + contact-like pages. Returns dict with emails (ranked), best, contact_page, site_name."""
    site = net.normalize_site(homepage)
    site_domain = net.registered_domain(site)
    to_visit = [(site + "/", "home")]
    visited, results, contact_page, site_name, errors = set(), {}, None, None, []

    while to_visit and len(visited) < MAX_PAGES:
        url, kind = to_visit.pop(0)
        key = url.rstrip("/")
        if key in visited:
            continue
        visited.add(key)
        try:
            r = net.fetch(url, timeout=timeout)
        except Exception as e:
            errors.append(f"{url}: {type(e).__name__}")
            continue
        if r.status_code >= 400 or "html" not in r.headers.get("Content-Type", "html"):
            if kind == "home":
                errors.append(f"{url}: HTTP {r.status_code}")
            continue
        if kind == "home":
            final = net.normalize_site(r.url)
            if net.registered_domain(final) != site_domain:  # site redirects elsewhere
                site, site_domain = final, net.registered_domain(final)
        found, soup = emails_in_html(r.text)
        if kind == "home":
            og = soup.find("meta", property="og:site_name")
            site_name = (og.get("content") if og else None) or (soup.title.get_text(strip=True).split("|")[0].split(" - ")[0].strip() if soup.title else None)
            for a in soup.find_all("a", href=True):
                label = (a.get_text(" ", strip=True) + " " + a["href"]).lower()
                if any(h in label for h in CONTACT_HINTS):
                    link = urljoin(r.url, a["href"])
                    if net.registered_domain(link) == site_domain and urlparse(link).scheme in ("http", "https"):
                        to_visit.insert(0, (link.split("#")[0], "contact"))
            for p in GUESS_PATHS:
                to_visit.append((site + p, "contact"))
        if found and kind == "contact" and not contact_page:
            contact_page = r.url
        for e, src in found.items():
            sc = score(e, src, kind, site_domain)
            if e not in results or sc > results[e]["score"]:
                results[e] = {"email": e, "source": src, "page": r.url, "score": sc}

    emails = sorted(results.values(), key=lambda x: -x["score"])
    if verify_mx:
        for item in emails:
            item["mx"] = has_mx(item["email"].split("@")[1])
        emails = [e for e in emails if e["mx"] is not False]
    # Addresses on unrelated corporate domains (theme authors, plugin vendors) are noise.
    emails = [e for e in emails if net.registered_domain(e["email"].split("@")[1]) == site_domain
              or e["email"].split("@")[1] in FREE_MAIL or e["score"] >= 40]
    return {
        "emails": emails,
        "best": emails[0]["email"] if emails else None,
        "contact_page": contact_page,
        "site_name": site_name,
        "pages_checked": len(visited),
        "errors": errors,
    }
