"""Background jobs: scan websites, find emails, push Gmail drafts, send emails."""
import json
import random
import threading
import time
import traceback
from datetime import datetime, timezone

from bs4 import BeautifulSoup

import db
import emailfinder
import mailer
import net
import scanner

_cancel = set()
_lock = threading.Lock()


class Job:
    def __init__(self, job_id):
        self.id = job_id

    def log(self, msg):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n"
        with db.conn() as c:
            c.execute("UPDATE jobs SET log = log || ? WHERE id=?", (line, self.id))

    def progress(self, done, total=None):
        with db.conn() as c:
            if total is None:
                c.execute("UPDATE jobs SET progress=? WHERE id=?", (done, self.id))
            else:
                c.execute("UPDATE jobs SET progress=?, total=? WHERE id=?", (done, total, self.id))

    @property
    def cancelled(self):
        return self.id in _cancel


def start(kind, fn, *args):
    with db.conn() as c:
        job_id = c.execute("INSERT INTO jobs(kind, created_at) VALUES (?, ?)", (kind, db.now())).lastrowid
    job = Job(job_id)

    def run():
        status = "done"
        try:
            fn(job, *args)
            if job.cancelled:
                status = "cancelled"
        except Exception as e:
            status = "failed"
            job.log(f"ERROR: {e}\n{traceback.format_exc()}")
        with db.conn() as c:
            c.execute("UPDATE jobs SET status=?, finished_at=? WHERE id=?", (status, db.now(), job_id))
        _cancel.discard(job_id)

    threading.Thread(target=run, daemon=True).start()
    return job_id


def cancel(job_id):
    _cancel.add(job_id)


# ------------------------------------------------------------------ scan

def scan_websites(job, website_ids, start, end, max_per_site, rescan, auto_emails):
    s = db.get_settings()
    timeout = int(s.get("request_timeout") or 20)
    with db.conn() as c:
        sites = [dict(r) for r in c.execute(
            f"SELECT * FROM websites WHERE id IN ({','.join('?' * len(website_ids))})", website_ids)]
    job.progress(0, len(sites))
    new_domains = set()
    for i, site in enumerate(sites):
        if job.cancelled:
            break
        job.log(f"Scanning {site['url']}  ({start} -> {end})")
        try:
            new_domains |= _scan_site(job, site, start, end, max_per_site, rescan, timeout)
        except Exception as e:
            job.log(f"  failed: {e}")
        job.progress(i + 1)
    job.log(f"Scan finished. {len(new_domains)} new prospect domains.")
    if auto_emails and new_domains and not job.cancelled:
        with db.conn() as c:
            ids = [r["id"] for r in c.execute(
                f"SELECT id FROM prospects WHERE domain IN ({','.join('?' * len(new_domains))})", list(new_domains))]
        find_emails(job, ids)


def _scan_site(job, site, start, end, limit, rescan, timeout):
    base = site["url"]
    site_domain = net.registered_domain(base)
    home_html = None
    try:
        r = net.fetch(base + "/", timeout=timeout)
        if r.status_code < 400:
            home_html = r.text
            og = BeautifulSoup(home_html, "lxml").find("meta", property="og:site_name")
            if og and og.get("content") and not site.get("name"):
                with db.conn() as c:
                    c.execute("UPDATE websites SET name=? WHERE id=?", (og["content"].strip()[:100], site["id"]))
    except Exception as e:
        job.log(f"  homepage unreachable: {type(e).__name__}")

    articles = scanner.discover_wordpress(base, start, end, limit, job.log, timeout)
    if articles is None:
        job.log("  Not a WordPress REST site, trying feeds + sitemaps")
        articles = scanner.discover_feeds(base, home_html, start, end, limit, job.log, timeout)
        have = {a["url"] for a in articles}
        if len(articles) < limit:
            articles += [a for a in scanner.discover_sitemaps(base, start, end, limit, job.log, timeout)
                         if a["url"] not in have]

    blocked = db.blocklist()
    new_domains, kept = set(), 0
    for art in articles:
        if job.cancelled or kept >= limit:
            break
        url = art["url"]
        with db.conn() as c:
            existing = c.execute("SELECT id, status FROM articles WHERE url=?", (url,)).fetchone()
        if existing and existing["status"] == "done" and not rescan:
            continue
        html, full_page = art.get("html"), False
        title, pub = art.get("title"), art.get("published_at")
        if not html:
            try:
                r = net.fetch(url, timeout=timeout)
            except Exception as e:
                job.log(f"  skip {url}: {type(e).__name__}")
                continue
            if r.status_code >= 400:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            page_date = scanner.page_publish_date(soup)
            pub = pub or page_date
            if not scanner.in_range(pub, start, end):
                continue  # sitemap candidate outside the range, or no publish date at all
            if not title:
                og = soup.find("meta", property="og:title")
                h1 = soup.find("h1")
                title = (og.get("content") if og else None) or (h1.get_text(" ", strip=True) if h1 else url)
            html, full_page = r.text, True
        kept += 1
        links = [l for l in scanner.extract_external_links(html, url, site_domain, full_page)
                 if not db.is_blocked(l["domain"], blocked)]
        scanner.verify_links(links, timeout)
        with db.conn() as c:
            if existing:
                art_id = existing["id"]
                c.execute("UPDATE articles SET title=?, published_at=?, source=?, scanned_at=?, status='done', error=NULL WHERE id=?",
                          (title, pub.isoformat() if pub else None, art["source"], db.now(), art_id))
                c.execute("DELETE FROM links WHERE article_id=?", (art_id,))
            else:
                art_id = c.execute(
                    "INSERT INTO articles(website_id, url, title, published_at, source, scanned_at, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'done')",
                    (site["id"], url, title, pub.isoformat() if pub else None, art["source"], db.now())).lastrowid
            for l in links:
                target = l["domain"]
                if l["verdict"] == "live" and l["final_url"]:
                    target = net.registered_domain(l["final_url"]) or target  # follow redirects to the real site
                c.execute("INSERT OR IGNORE INTO links(article_id, url, final_url, domain, anchor, rel, status_code, verdict, checked_at) "
                          "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (art_id, l["url"], l["final_url"], target, l["anchor"], l["rel"], l["status_code"], l["verdict"], db.now()))
                if l["verdict"] in ("live", "blocked") and target != site_domain and not db.is_blocked(target, blocked):
                    cur = c.execute("INSERT OR IGNORE INTO prospects(domain, homepage, created_at) VALUES (?, ?, ?)",
                                    (target, f"https://{target}", db.now()))
                    if cur.rowcount:
                        new_domains.add(target)
        live = sum(1 for l in links if l["verdict"] == "live")
        job.log(f"  [{pub.date() if pub else '?'}] {title[:70]}  -> {len(links)} external links ({live} live)")
    job.log(f"  {kept} articles processed for {site['domain']}")
    return new_domains


# ------------------------------------------------------------------ emails

def find_emails(job, prospect_ids):
    s = db.get_settings()
    timeout = int(s.get("request_timeout") or 20)
    verify = s.get("verify_mx", "1") == "1"
    job.progress(0, len(prospect_ids))
    found_count = 0
    for i, pid in enumerate(prospect_ids):
        if job.cancelled:
            break
        with db.conn() as c:
            p = c.execute("SELECT * FROM prospects WHERE id=?", (pid,)).fetchone()
            if p:
                c.execute("UPDATE prospects SET status='searching' WHERE id=?", (pid,))
        if not p:
            continue
        try:
            res = emailfinder.find_emails(p["homepage"], timeout=timeout, verify_mx=verify)
            status = "found" if res["best"] else "not_found"
            err = "; ".join(res["errors"][:3]) if not res["best"] and res["errors"] else None
            with db.conn() as c:
                c.execute("UPDATE prospects SET status=?, emails=?, best_email=COALESCE(best_email, ?), contact_page=?, "
                          "site_name=COALESCE(?, site_name), checked_at=?, error=? WHERE id=?",
                          (status, json.dumps(res["emails"]), res["best"], res["contact_page"], res["site_name"],
                           db.now(), err, pid))
            if res["best"]:
                found_count += 1
            job.log(f"{p['domain']}: {res['best'] or 'no email'} ({len(res['emails'])} found, {res['pages_checked']} pages)")
        except Exception as e:
            with db.conn() as c:
                c.execute("UPDATE prospects SET status='error', error=?, checked_at=? WHERE id=?", (str(e)[:300], db.now(), pid))
            job.log(f"{p['domain']}: error {e}")
        job.progress(i + 1)
    job.log(f"Email search finished: {found_count}/{len(prospect_ids)} domains with an email.")


# ------------------------------------------------------------------ drafts / sending

def push_gmail_drafts(job, outreach_ids):
    s = db.get_settings()
    with db.conn() as c:
        rows = [dict(r) for r in c.execute(
            f"SELECT * FROM outreach WHERE id IN ({','.join('?' * len(outreach_ids))}) AND status IN ('draft','approved')",
            outreach_ids)]
    job.progress(0, len(rows))
    batch = 20
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        mailer.save_drafts(s, [(r["to_email"], r["subject"], r["body"]) for r in chunk])
        with db.conn() as c:
            c.executemany("UPDATE outreach SET gmail_draft=1 WHERE id=?", [(r["id"],) for r in chunk])
        job.progress(i + len(chunk))
        job.log(f"Saved {i + len(chunk)}/{len(rows)} to Gmail Drafts")


def sent_today():
    today = datetime.utcnow().date().isoformat()
    with db.conn() as c:
        return c.execute("SELECT COUNT(*) FROM outreach WHERE status='sent' AND sent_at >= ?", (today,)).fetchone()[0]


def send_approved(job, outreach_ids):
    s = db.get_settings()
    limit = int(s.get("daily_send_limit") or 40)
    delay = int(s.get("send_delay_seconds") or 90)
    with db.conn() as c:
        q = "SELECT * FROM outreach WHERE status='approved'"
        args = []
        if outreach_ids:
            q += f" AND id IN ({','.join('?' * len(outreach_ids))})"
            args = outreach_ids
        rows = [dict(r) for r in c.execute(q + " ORDER BY id", args)]
    job.progress(0, len(rows))
    if not rows:
        job.log("Nothing approved to send.")
        return
    with mailer.Sender(s) as sender:
        for i, r in enumerate(rows):
            if job.cancelled:
                break
            if sent_today() >= limit:
                job.log(f"Daily limit of {limit} reached. Remaining emails stay approved for tomorrow.")
                break
            with db.conn() as c:
                dup = c.execute("SELECT 1 FROM outreach WHERE to_email=? AND status='sent' AND id<>?",
                                (r["to_email"], r["id"])).fetchone()
                if dup:
                    c.execute("UPDATE outreach SET status='skipped', error='already emailed' WHERE id=?", (r["id"],))
                    job.log(f"Skip {r['to_email']}: already emailed before")
                    job.progress(i + 1)
                    continue
            try:
                sender.send(r["to_email"], r["subject"], r["body"])
                with db.conn() as c:
                    c.execute("UPDATE outreach SET status='sent', sent_at=?, error=NULL WHERE id=?", (db.now(), r["id"]))
                job.log(f"Sent -> {r['to_email']}")
            except Exception as e:
                with db.conn() as c:
                    c.execute("UPDATE outreach SET status='failed', error=? WHERE id=?", (str(e)[:300], r["id"]))
                job.log(f"FAILED {r['to_email']}: {e}")
            job.progress(i + 1)
            if i < len(rows) - 1 and not job.cancelled:
                wait = delay * random.uniform(0.7, 1.3)  # human-like spacing, helps deliverability
                end = time.time() + wait
                while time.time() < end and not job.cancelled:
                    time.sleep(1)
