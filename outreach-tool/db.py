"""SQLite storage. Each call opens its own connection so background threads are safe."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.environ.get("OUTREACH_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "outreach.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS websites (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL,
    domain TEXT NOT NULL UNIQUE,
    name TEXT,
    added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY,
    website_id INTEGER NOT NULL REFERENCES websites(id) ON DELETE CASCADE,
    url TEXT NOT NULL UNIQUE,
    title TEXT,
    published_at TEXT,
    source TEXT,
    scanned_at TEXT,
    status TEXT DEFAULT 'new',
    error TEXT
);
CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    final_url TEXT,
    domain TEXT NOT NULL,
    anchor TEXT,
    rel TEXT,
    status_code INTEGER,
    verdict TEXT,
    checked_at TEXT,
    UNIQUE(article_id, url)
);
CREATE TABLE IF NOT EXISTS prospects (
    id INTEGER PRIMARY KEY,
    domain TEXT NOT NULL UNIQUE,
    homepage TEXT,
    site_name TEXT,
    status TEXT DEFAULT 'new',
    emails TEXT DEFAULT '[]',
    best_email TEXT,
    contact_page TEXT,
    checked_at TEXT,
    error TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS blocklist (
    id INTEGER PRIMARY KEY,
    domain TEXT NOT NULL UNIQUE,
    added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    is_default INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS outreach (
    id INTEGER PRIMARY KEY,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    link_id INTEGER REFERENCES links(id) ON DELETE SET NULL,
    template_id INTEGER,
    to_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT DEFAULT 'draft',
    gmail_draft INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    sent_at TEXT,
    error TEXT
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT DEFAULT 'running',
    progress INTEGER DEFAULT 0,
    total INTEGER DEFAULT 0,
    log TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_links_domain ON links(domain);
CREATE INDEX IF NOT EXISTS idx_outreach_email ON outreach(to_email);
"""

# Domains that are never outreach targets (social, big platforms, CDNs). User can edit.
DEFAULT_BLOCKLIST = [
    "facebook.com", "twitter.com", "x.com", "instagram.com", "linkedin.com", "youtube.com",
    "youtu.be", "pinterest.com", "tiktok.com", "reddit.com", "t.me", "whatsapp.com", "wa.me",
    "google.com", "goo.gl", "g.co", "apple.com", "microsoft.com", "amazon.com", "amzn.to",
    "wikipedia.org", "wikimedia.org", "github.com", "medium.com", "wordpress.org", "wordpress.com",
    "gravatar.com", "w.org", "bit.ly", "t.co", "ow.ly", "tinyurl.com", "feedburner.com",
    "cloudflare.com", "gstatic.com", "googleapis.com", "doubleclick.net", "googletagmanager.com",
    "creativecommons.org", "schema.org", "w3.org", "addtoany.com", "sharethis.com", "disqus.com",
    "spotify.com", "soundcloud.com", "vimeo.com", "flickr.com", "tumblr.com", "quora.com",
    "ncbi.nlm.nih.gov", "nih.gov", "who.int", "cdc.gov",
]

DEFAULT_TEMPLATE = {
    "name": "Default outreach",
    "subject": "Quick question about {{domain}}",
    "body": (
        "Hi {{site_name}} team,\n\n"
        "I came across {{source_site}}'s article \"{{article_title}}\" ({{article_url}}) "
        "where they linked to your page: {{linked_url}}\n\n"
        "I run {{my_website}} and I'd love to explore working together.\n\n"
        "Would you be open to a quick chat?\n\n"
        "Best,\n{{my_name}}\n{{my_website}}"
    ),
}

DEFAULT_SETTINGS = {
    "gmail_address": "",
    "gmail_app_password": "",
    "from_name": "",
    "my_name": "",
    "my_website": "",
    "send_delay_seconds": "90",
    "daily_send_limit": "40",
    "verify_mx": "1",
    "request_timeout": "20",
}


def now():
    return datetime.utcnow().replace(microsecond=0).isoformat()


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with conn() as c:
        c.execute("PRAGMA journal_mode = WAL")
        c.executescript(SCHEMA)
        if not c.execute("SELECT 1 FROM blocklist LIMIT 1").fetchone():
            c.executemany("INSERT OR IGNORE INTO blocklist(domain, added_at) VALUES (?, ?)",
                          [(d, now()) for d in DEFAULT_BLOCKLIST])
        if not c.execute("SELECT 1 FROM templates LIMIT 1").fetchone():
            c.execute("INSERT INTO templates(name, subject, body, is_default) VALUES (?, ?, ?, 1)",
                      (DEFAULT_TEMPLATE["name"], DEFAULT_TEMPLATE["subject"], DEFAULT_TEMPLATE["body"]))
        for k, v in DEFAULT_SETTINGS.items():
            c.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, v))
        # Jobs left "running" by a previous crash/restart can never finish.
        c.execute("UPDATE jobs SET status='interrupted', finished_at=? WHERE status='running'", (now(),))


def get_settings():
    with conn() as c:
        return {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM settings")}


def set_settings(values):
    with conn() as c:
        for k, v in values.items():
            c.execute("INSERT INTO settings(key, value) VALUES (?, ?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, v))


def blocklist():
    with conn() as c:
        return {r["domain"] for r in c.execute("SELECT domain FROM blocklist")}


def is_blocked(domain, blocked=None):
    """True if domain or any parent domain is on the blocklist."""
    blocked = blocklist() if blocked is None else blocked
    parts = domain.lower().split(".")
    return any(".".join(parts[i:]) in blocked for i in range(len(parts) - 1))


def emails_of(row):
    try:
        return json.loads(row["emails"] or "[]")
    except (ValueError, TypeError):
        return []
