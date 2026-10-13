"""HTTP helpers and URL/domain normalisation shared by the scanner and the email finder."""
import random
import threading
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import requests
import tldextract

# Use the bundled public-suffix snapshot; no network fetch at startup.
_extract = tldextract.TLDExtract(suffix_list_urls=())

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
]

_local = threading.local()


def session():
    s = getattr(_local, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        _local.session = s
    return s


def fetch(url, timeout=20, **kw):
    """GET a URL. Returns Response or raises requests.RequestException."""
    return session().get(url, timeout=timeout, allow_redirects=True, **kw)


def registered_domain(url_or_host):
    host = urlparse(url_or_host).hostname if "://" in url_or_host else url_or_host
    if not host:
        return ""
    ext = _extract(host.lower())
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}"
    return host.lower()


def normalize_site(url):
    url = url.strip()
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}".rstrip("/")


_TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid", "ref"}


def clean_url(url):
    p = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in _TRACKING]
    return urlunparse((p.scheme, p.netloc.lower(), p.path or "/", "", urlencode(q), ""))
