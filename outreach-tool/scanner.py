"""Find articles published in a date range, pull external links from the article body, verify them.

Article discovery, most to least precise:
  1. WordPress REST API  - exact publish dates and the exact post body HTML.
  2. RSS / Atom feeds    - exact publish dates, usually only the latest 10-50 posts.
  3. XML sitemaps        - <lastmod> is a *modified* date, so every candidate page is
                           fetched and its real publish date read from the page itself.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

import net

MAX_SITEMAPS = 25
MAX_SITEMAP_CANDIDATES = 400

CONTENT_SELECTORS = [
    "[itemprop=articleBody]", ".entry-content", ".post-content", ".article-content", ".article-body",
    ".post-body", ".td-post-content", ".single-content", ".blog-content", ".content-inner",
    "article", "main", "#content",
]
# Page furniture inside the content area whose links are not editorial.
NOISE_SELECTORS = [
    "nav", "header", "footer", "aside", "form", "script", "style", "noscript",
    ".sidebar", ".widget", ".related", ".related-posts", ".jp-relatedposts", ".comments", "#comments",
    ".comment", ".author-box", ".author-bio", ".about-author", ".share", ".sharedaddy", ".social",
    ".social-share", ".post-tags", ".tags", ".breadcrumb", ".breadcrumbs", ".newsletter", ".ads",
    ".advertisement", ".yarpp-related", ".wp-block-navigation", ".toc", "#toc", ".ez-toc-container",
]


def parse_date(value):
    if not value:
        return None
    try:
        d = dateparser.parse(str(value))
    except (ValueError, OverflowError, TypeError):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def in_range(d, start, end):
    return d is not None and start <= d.date() <= end


# ---------------------------------------------------------------- discovery

def discover_wordpress(site, start, end, limit, log, timeout):
    out = []
    page = 1
    while len(out) < limit:
        url = (f"{site}/wp-json/wp/v2/posts?per_page=100&page={page}&orderby=date&order=desc"
               f"&after={start.isoformat()}T00:00:00&before={end.isoformat()}T23:59:59"
               "&_fields=link,title,date_gmt,date,content")
        try:
            r = net.fetch(url, timeout=timeout)
        except Exception:
            return None if page == 1 else out
        if r.status_code != 200 or "json" not in r.headers.get("Content-Type", ""):
            if page == 1:
                return None  # not WordPress / API disabled
            break
        try:
            posts = r.json()
        except ValueError:
            return None if page == 1 else out
        if not isinstance(posts, list) or not posts:
            break
        for p in posts:
            d = parse_date(p.get("date_gmt") and p["date_gmt"] + "Z" or p.get("date"))
            if not in_range(d, start, end):
                continue
            out.append({
                "url": p.get("link"),
                "title": BeautifulSoup((p.get("title") or {}).get("rendered", ""), "lxml").get_text(" ", strip=True),
                "published_at": d,
                "html": (p.get("content") or {}).get("rendered", ""),
                "source": "wordpress-api",
            })
        if len(posts) < 100:
            break
        page += 1
    log(f"  WordPress API: {len(out)} posts in range")
    return out[:limit]


def _feed_urls(site, home_html):
    urls = []
    if home_html:
        soup = BeautifulSoup(home_html, "lxml")
        for l in soup.find_all("link", rel="alternate"):
            t = (l.get("type") or "").lower()
            if ("rss" in t or "atom" in t) and l.get("href") and "comments" not in l["href"]:
                urls.append(urljoin(site + "/", l["href"]))
    urls += [f"{site}/feed", f"{site}/feed/", f"{site}/rss", f"{site}/rss.xml", f"{site}/feed.xml",
             f"{site}/atom.xml", f"{site}/index.xml", f"{site}/blog/feed", f"{site}/blog/rss.xml"]
    seen, uniq = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def discover_feeds(site, home_html, start, end, limit, log, timeout):
    found = {}
    for fu in _feed_urls(site, home_html):
        try:
            r = net.fetch(fu, timeout=timeout)
        except Exception:
            continue
        if r.status_code != 200 or b"<" not in r.content[:500]:
            continue
        soup = BeautifulSoup(r.content, "xml")
        items = soup.find_all("item") or soup.find_all("entry")
        if not items:
            continue
        for it in items:
            link = it.find("link")
            href = (link.get("href") or link.get_text(strip=True)) if link else None
            d = parse_date(_text(it, "pubDate") or _text(it, "published") or _text(it, "updated") or _text(it, "date"))
            if href and in_range(d, start, end):
                content = _text(it, "encoded") or _text(it, "content")
                found[href] = {"url": href, "title": _text(it, "title"), "published_at": d,
                               "html": None, "feed_html": content, "source": "feed"}
        if found:
            log(f"  Feed {fu}: {len(found)} posts in range")
            break
    return list(found.values())[:limit]


def _text(node, name):
    t = node.find(name)
    return t.get_text(strip=True) if t else None


def _sitemap_roots(site, timeout):
    roots = []
    try:
        r = net.fetch(f"{site}/robots.txt", timeout=timeout)
        if r.status_code == 200:
            roots += re.findall(r"(?im)^\s*sitemap:\s*(\S+)", r.text)
    except Exception:
        pass
    roots += [f"{site}/sitemap_index.xml", f"{site}/sitemap.xml", f"{site}/post-sitemap.xml", f"{site}/wp-sitemap.xml"]
    return list(dict.fromkeys(roots))


def discover_sitemaps(site, start, end, limit, log, timeout):
    queue, seen, candidates = _sitemap_roots(site, timeout), set(), {}
    while queue and len(seen) < MAX_SITEMAPS:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        try:
            r = net.fetch(sm, timeout=timeout)
        except Exception:
            continue
        if r.status_code != 200:
            continue
        soup = BeautifulSoup(r.content, "xml")
        for s in soup.find_all("sitemap"):
            loc = _text(s, "loc")
            lm = parse_date(_text(s, "lastmod"))
            low = (loc or "").lower()
            # Skip child sitemaps that obviously aren't posts or weren't touched since `start`.
            if not loc or any(k in low for k in ("tag", "category", "author", "page-sitemap", "product", "image", "video")):
                continue
            if lm and lm.date() < start:
                continue
            queue.append(loc)
        for u in soup.find_all("url"):
            loc = _text(u, "loc")
            lm = parse_date(_text(u, "lastmod"))
            # lastmod >= publish date, so lastmod < start means it can't be in range. Missing lastmod -> keep.
            if loc and (lm is None or lm.date() >= start):
                candidates[loc] = lm
    # Newest first, capped; publish date is confirmed later from the page itself.
    ordered = sorted(candidates.items(), key=lambda kv: kv[1] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    ordered = [u for u, _ in ordered if urlparse(u).path.strip("/")][:MAX_SITEMAP_CANDIDATES]
    log(f"  Sitemaps: {len(ordered)} candidate URLs to confirm by publish date")
    return [{"url": u, "title": None, "published_at": None, "html": None, "source": "sitemap"} for u in ordered]


# ---------------------------------------------------------------- page parsing

def page_publish_date(soup):
    for attrs in ({"property": "article:published_time"}, {"name": "article:published_time"},
                  {"itemprop": "datePublished"}, {"name": "date"}, {"name": "publish-date"},
                  {"name": "parsely-pub-date"}, {"property": "og:published_time"}):
        m = soup.find("meta", attrs=attrs)
        if m and parse_date(m.get("content")):
            return parse_date(m.get("content"))
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "")
        except (ValueError, TypeError):
            continue
        for node in _walk_jsonld(data):
            if isinstance(node, dict) and node.get("datePublished"):
                d = parse_date(node["datePublished"])
                if d:
                    return d
    t = soup.find("time", attrs={"datetime": True})
    if t:
        return parse_date(t["datetime"])
    return None


def _walk_jsonld(data):
    if isinstance(data, list):
        for x in data:
            yield from _walk_jsonld(x)
    elif isinstance(data, dict):
        yield data
        for k in ("@graph", "mainEntity"):
            if k in data:
                yield from _walk_jsonld(data[k])


def content_root(soup):
    for sel in CONTENT_SELECTORS:
        nodes = soup.select(sel)
        if nodes:
            # Largest matching node by text length = the article body, not a teaser card.
            return max(nodes, key=lambda n: len(n.get_text()))
    return soup.body or soup


def extract_external_links(body_html, page_url, site_domain, is_full_page):
    soup = BeautifulSoup(body_html, "lxml")
    root = content_root(soup) if is_full_page else soup
    for sel in NOISE_SELECTORS:
        for n in root.select(sel):
            n.decompose()
    links = {}
    for a in root.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            continue
        absu = urljoin(page_url, href)
        p = urlparse(absu)
        if p.scheme not in ("http", "https") or not p.hostname:
            continue
        dom = net.registered_domain(p.hostname)
        if not dom or dom == site_domain:
            continue
        u = net.clean_url(absu)
        if u not in links:
            links[u] = {"url": u, "domain": dom, "anchor": a.get_text(" ", strip=True)[:200],
                        "rel": " ".join(a.get("rel") or [])}
    return list(links.values())


# ---------------------------------------------------------------- verification

def verify_link(url, timeout):
    """Return (status_code, final_url, verdict). verdict: live | dead | blocked | error."""
    try:
        r = net.session().head(url, timeout=timeout, allow_redirects=True)
        if r.status_code in (403, 405, 400, 429, 501) or r.status_code >= 500:
            r = net.fetch(url, timeout=timeout, stream=True)
            r.close()
    except Exception as e:
        try:
            r = net.fetch(url, timeout=timeout, stream=True)
            r.close()
        except Exception:
            return None, None, "error: " + type(e).__name__
    code = r.status_code
    if code < 400:
        verdict = "live"
    elif code in (401, 403, 429, 503):
        verdict = "blocked"  # bot protection: site likely exists, can't confirm the page
    else:
        verdict = "dead"
    return code, r.url, verdict


def verify_links(links, timeout, workers=8):
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda l: verify_link(l["url"], timeout), links))
    for l, (code, final, verdict) in zip(links, results):
        l["status_code"], l["final_url"], l["verdict"] = code, final, verdict
    return links
