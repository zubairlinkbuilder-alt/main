"""Gmail sending (SMTP) and draft creation (IMAP) using a Google App Password."""
import imaplib
import re
import smtplib
import time
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, formatdate

SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 587
IMAP_HOST = "imap.gmail.com"

VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_]+)\s*\}\}")
VARIABLES = ["site_name", "domain", "email", "article_title", "article_url", "source_site",
             "linked_url", "anchor_text", "my_name", "my_website"]


def render(text, ctx):
    return VAR_RE.sub(lambda m: str(ctx.get(m.group(1), "") or ""), text)


def unknown_vars(text):
    return sorted({v for v in VAR_RE.findall(text) if v not in VARIABLES})


def build_message(settings, to, subject, body):
    msg = EmailMessage()
    addr = settings["gmail_address"].strip()
    msg["From"] = formataddr((settings.get("from_name") or "", addr))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=addr.split("@")[-1] or None)
    msg.set_content(body)
    return msg


def _creds(settings):
    user = settings.get("gmail_address", "").strip()
    pwd = settings.get("gmail_app_password", "").replace(" ", "")
    if not user or not pwd:
        raise RuntimeError("Gmail address / App Password not set (Settings page).")
    return user, pwd


class Sender:
    """Keeps one SMTP connection open across a batch."""

    def __init__(self, settings):
        self.settings = settings
        self.smtp = None

    def __enter__(self):
        user, pwd = _creds(self.settings)
        self.smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60)
        self.smtp.starttls()
        self.smtp.login(user, pwd)
        return self

    def send(self, to, subject, body):
        msg = build_message(self.settings, to, subject, body)
        try:
            self.smtp.send_message(msg)
        except smtplib.SMTPServerDisconnected:
            self.__enter__()
            self.smtp.send_message(msg)

    def __exit__(self, *a):
        try:
            self.smtp.quit()
        except Exception:
            pass


def _drafts_folder(imap):
    typ, data = imap.list()
    for line in data or []:
        s = line.decode(errors="ignore")
        if "\\Drafts" in s:
            return s.rsplit(' "/" ', 1)[-1].strip()
    return '"[Gmail]/Drafts"'


def save_drafts(settings, messages):
    """messages: list of (to, subject, body). Saves them to the Gmail Drafts folder."""
    user, pwd = _creds(settings)
    imap = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        imap.login(user, pwd)
        folder = _drafts_folder(imap)
        for to, subject, body in messages:
            msg = build_message(settings, to, subject, body)
            typ, resp = imap.append(folder, "(\\Draft)", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
            if typ != "OK":
                raise RuntimeError(f"IMAP append failed: {resp}")
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def test_connection(settings):
    with Sender(settings):
        pass
    user, pwd = _creds(settings)
    imap = imaplib.IMAP4_SSL(IMAP_HOST)
    imap.login(user, pwd)
    imap.logout()
