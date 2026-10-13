"""Outreach tool - web UI. Run: python app.py  then open http://127.0.0.1:5000"""
import os
from datetime import date, timedelta

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

import db
import jobs
import mailer
import net

app = Flask(__name__)
app.secret_key = os.environ.get("OUTREACH_SECRET", "local-outreach-tool")
db.init()


def ids_from_form(name="ids"):
    return [int(x) for x in request.form.getlist(name) if x.isdigit()]


@app.context_processor
def inject():
    with db.conn() as c:
        running = c.execute("SELECT id, kind FROM jobs WHERE status='running' ORDER BY id DESC").fetchall()
    return {"running_jobs": running, "VARIABLES": mailer.VARIABLES}


# ------------------------------------------------------------------ dashboard

@app.route("/")
def dashboard():
    with db.conn() as c:
        stats = {
            "websites": c.execute("SELECT COUNT(*) FROM websites").fetchone()[0],
            "articles": c.execute("SELECT COUNT(*) FROM articles").fetchone()[0],
            "links": c.execute("SELECT COUNT(*) FROM links").fetchone()[0],
            "prospects": c.execute("SELECT COUNT(*) FROM prospects").fetchone()[0],
            "with_email": c.execute("SELECT COUNT(*) FROM prospects WHERE best_email IS NOT NULL").fetchone()[0],
            "drafts": c.execute("SELECT COUNT(*) FROM outreach WHERE status='draft'").fetchone()[0],
            "approved": c.execute("SELECT COUNT(*) FROM outreach WHERE status='approved'").fetchone()[0],
            "sent": c.execute("SELECT COUNT(*) FROM outreach WHERE status='sent'").fetchone()[0],
        }
        recent = c.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT 10").fetchall()
    return render_template("dashboard.html", stats=stats, recent=recent, sent_today=jobs.sent_today(),
                           settings=db.get_settings())


# ------------------------------------------------------------------ websites

@app.route("/websites", methods=["GET", "POST"])
def websites():
    if request.method == "POST":
        added = 0
        for line in request.form.get("urls", "").splitlines():
            site = net.normalize_site(line)
            if not site:
                continue
            with db.conn() as c:
                cur = c.execute("INSERT OR IGNORE INTO websites(url, domain, added_at) VALUES (?, ?, ?)",
                                (site, net.registered_domain(site), db.now()))
                added += cur.rowcount
        flash(f"{added} website(s) added.")
        return redirect(url_for("websites"))
    with db.conn() as c:
        rows = c.execute("""SELECT w.*, COUNT(a.id) AS n_articles, MAX(a.published_at) AS latest
                            FROM websites w LEFT JOIN articles a ON a.website_id=w.id
                            GROUP BY w.id ORDER BY w.domain""").fetchall()
    return render_template("websites.html", rows=rows)


@app.post("/websites/delete")
def websites_delete():
    ids = ids_from_form()
    with db.conn() as c:
        c.executemany("DELETE FROM websites WHERE id=?", [(i,) for i in ids])
    flash(f"{len(ids)} website(s) removed.")
    return redirect(url_for("websites"))


# ------------------------------------------------------------------ scan

@app.route("/scan", methods=["GET", "POST"])
def scan():
    if request.method == "POST":
        ids = ids_from_form("website_ids")
        if not ids:
            flash("Select at least one website.")
            return redirect(url_for("scan"))
        try:
            start = date.fromisoformat(request.form["start"])
            end = date.fromisoformat(request.form["end"])
        except (KeyError, ValueError):
            flash("Invalid date.")
            return redirect(url_for("scan"))
        if start > end:
            start, end = end, start
        job_id = jobs.start("scan", jobs.scan_websites, ids, start, end,
                            max(1, int(request.form.get("max_per_site") or 30)),
                            bool(request.form.get("rescan")), bool(request.form.get("auto_emails")))
        return redirect(url_for("job_view", job_id=job_id))
    with db.conn() as c:
        sites = c.execute("SELECT * FROM websites ORDER BY domain").fetchall()
    today = date.today()
    return render_template("scan.html", sites=sites, today=today.isoformat(),
                           week_ago=(today - timedelta(days=7)).isoformat())


# ------------------------------------------------------------------ jobs

@app.route("/jobs/<int:job_id>")
def job_view(job_id):
    with db.conn() as c:
        job = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        return redirect(url_for("dashboard"))
    return render_template("job.html", job=job)


@app.route("/api/jobs/<int:job_id>")
def job_api(job_id):
    with db.conn() as c:
        job = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return jsonify(dict(job) if job else {})


@app.post("/jobs/<int:job_id>/cancel")
def job_cancel(job_id):
    jobs.cancel(job_id)
    flash("Cancel requested - the job stops after its current step.")
    return redirect(url_for("job_view", job_id=job_id))


# ------------------------------------------------------------------ articles

@app.route("/articles")
def articles():
    site = request.args.get("site", type=int)
    start, end = request.args.get("start") or "", request.args.get("end") or ""
    q = """SELECT a.*, w.domain AS site,
                  (SELECT COUNT(*) FROM links l WHERE l.article_id=a.id) AS n_links,
                  (SELECT COUNT(*) FROM links l WHERE l.article_id=a.id AND l.verdict='live') AS n_live
           FROM articles a JOIN websites w ON w.id=a.website_id WHERE 1=1"""
    args = []
    if site:
        q += " AND a.website_id=?"
        args.append(site)
    if start:
        q += " AND a.published_at >= ?"
        args.append(start)
    if end:
        q += " AND a.published_at < ?"
        args.append((date.fromisoformat(end) + timedelta(days=1)).isoformat())
    with db.conn() as c:
        rows = c.execute(q + " ORDER BY a.published_at DESC LIMIT 500", args).fetchall()
        sites = c.execute("SELECT id, domain FROM websites ORDER BY domain").fetchall()
    return render_template("articles.html", rows=rows, sites=sites, site=site, start=start, end=end)


@app.route("/articles/<int:aid>")
def article_detail(aid):
    with db.conn() as c:
        art = c.execute("SELECT a.*, w.domain AS site FROM articles a JOIN websites w ON w.id=a.website_id WHERE a.id=?",
                        (aid,)).fetchone()
        links = c.execute("SELECT * FROM links WHERE article_id=? ORDER BY verdict, domain", (aid,)).fetchall()
    return render_template("article.html", art=art, links=links)


# ------------------------------------------------------------------ prospects

@app.route("/prospects")
def prospects():
    status = request.args.get("status", "")
    qtext = request.args.get("q", "").strip()
    q = """SELECT p.*, COUNT(l.id) AS n_links,
                  (SELECT COUNT(*) FROM outreach o WHERE o.prospect_id=p.id) AS n_outreach,
                  (SELECT GROUP_CONCAT(DISTINCT w.domain) FROM links l2 JOIN articles a ON a.id=l2.article_id
                     JOIN websites w ON w.id=a.website_id WHERE l2.domain=p.domain) AS sources
           FROM prospects p LEFT JOIN links l ON l.domain=p.domain WHERE 1=1"""
    args = []
    if status:
        q += " AND p.status=?"
        args.append(status)
    if qtext:
        q += " AND (p.domain LIKE ? OR p.best_email LIKE ?)"
        args += [f"%{qtext}%", f"%{qtext}%"]
    with db.conn() as c:
        rows = c.execute(q + " GROUP BY p.id ORDER BY p.created_at DESC LIMIT 1000", args).fetchall()
        templates = c.execute("SELECT id, name, is_default FROM templates ORDER BY is_default DESC, name").fetchall()
    blocked = db.blocklist()
    rows = [r for r in rows if not db.is_blocked(r["domain"], blocked)]
    return render_template("prospects.html", rows=rows, status=status, q=qtext, templates=templates,
                           emails_of=db.emails_of)


@app.post("/prospects/action")
def prospects_action():
    ids, action = ids_from_form(), request.form.get("action")
    if action == "find_all_new":
        with db.conn() as c:
            ids = [r["id"] for r in c.execute("SELECT id FROM prospects WHERE status IN ('new','error')")]
        action = "find_emails"
    if not ids:
        flash("Nothing selected.")
        return redirect(request.referrer or url_for("prospects"))
    if action == "find_emails":
        return redirect(url_for("job_view", job_id=jobs.start("emails", jobs.find_emails, ids)))
    if action == "create_drafts":
        made, skipped = create_drafts(ids, request.form.get("template_id", type=int))
        flash(f"{made} draft(s) created. {skipped} skipped (no email, or this email already has an outreach).")
        return redirect(url_for("outreach"))
    if action in ("block", "delete"):
        with db.conn() as c:
            doms = [r["domain"] for r in c.execute(f"SELECT domain FROM prospects WHERE id IN ({','.join('?'*len(ids))})", ids)]
            if action == "block":
                c.executemany("INSERT OR IGNORE INTO blocklist(domain, added_at) VALUES (?, ?)", [(d, db.now()) for d in doms])
            c.executemany("DELETE FROM prospects WHERE id=?", [(i,) for i in ids])
        flash(f"{len(doms)} domain(s) {'blocked' if action == 'block' else 'deleted'}.")
    return redirect(request.referrer or url_for("prospects"))


@app.route("/prospects/<int:pid>", methods=["GET", "POST"])
def prospect_detail(pid):
    if request.method == "POST":
        email = request.form.get("best_email", "").strip().lower() or None
        with db.conn() as c:
            c.execute("UPDATE prospects SET best_email=?, status=CASE WHEN ? IS NULL THEN status ELSE 'found' END WHERE id=?",
                      (email, email, pid))
        flash("Saved.")
        return redirect(url_for("prospect_detail", pid=pid))
    with db.conn() as c:
        p = c.execute("SELECT * FROM prospects WHERE id=?", (pid,)).fetchone()
        if not p:
            return redirect(url_for("prospects"))
        links = c.execute("""SELECT l.*, a.title, a.url AS article_url, a.published_at, w.domain AS site
                             FROM links l JOIN articles a ON a.id=l.article_id JOIN websites w ON w.id=a.website_id
                             WHERE l.domain=? ORDER BY a.published_at DESC""", (p["domain"],)).fetchall()
        outreach_rows = c.execute("SELECT * FROM outreach WHERE prospect_id=? ORDER BY id DESC", (pid,)).fetchall()
    return render_template("prospect.html", p=p, emails=db.emails_of(p), links=links, outreach_rows=outreach_rows)


def template_context(c, prospect, settings):
    link = c.execute("""SELECT l.*, a.title, a.url AS article_url, w.domain AS site, w.name AS site_label
                        FROM links l JOIN articles a ON a.id=l.article_id JOIN websites w ON w.id=a.website_id
                        WHERE l.domain=? ORDER BY (l.verdict='live') DESC, a.published_at DESC LIMIT 1""",
                     (prospect["domain"],)).fetchone()
    ctx = {
        "site_name": prospect["site_name"] or prospect["domain"],
        "domain": prospect["domain"],
        "email": prospect["best_email"],
        "my_name": settings.get("my_name"),
        "my_website": settings.get("my_website"),
    }
    if link:
        ctx.update({"article_title": link["title"], "article_url": link["article_url"],
                    "source_site": link["site_label"] or link["site"], "linked_url": link["final_url"] or link["url"],
                    "anchor_text": link["anchor"]})
    return ctx, (link["id"] if link else None)


def create_drafts(prospect_ids, template_id):
    settings = db.get_settings()
    made = skipped = 0
    with db.conn() as c:
        tpl = (c.execute("SELECT * FROM templates WHERE id=?", (template_id,)).fetchone() if template_id else None) \
            or c.execute("SELECT * FROM templates ORDER BY is_default DESC, id LIMIT 1").fetchone()
        for pid in prospect_ids:
            p = c.execute("SELECT * FROM prospects WHERE id=?", (pid,)).fetchone()
            if not p or not p["best_email"]:
                skipped += 1
                continue
            if c.execute("SELECT 1 FROM outreach WHERE to_email=? AND status NOT IN ('failed')", (p["best_email"],)).fetchone():
                skipped += 1
                continue
            ctx, link_id = template_context(c, p, settings)
            c.execute("INSERT INTO outreach(prospect_id, link_id, template_id, to_email, subject, body, created_at) "
                      "VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (pid, link_id, tpl["id"], p["best_email"], mailer.render(tpl["subject"], ctx),
                       mailer.render(tpl["body"], ctx), db.now()))
            made += 1
    return made, skipped


# ------------------------------------------------------------------ outreach

@app.route("/outreach")
def outreach():
    status = request.args.get("status", "")
    q = "SELECT o.*, p.domain FROM outreach o JOIN prospects p ON p.id=o.prospect_id"
    args = []
    if status:
        q += " WHERE o.status=?"
        args.append(status)
    with db.conn() as c:
        rows = c.execute(q + " ORDER BY o.id DESC LIMIT 1000", args).fetchall()
    s = db.get_settings()
    return render_template("outreach.html", rows=rows, status=status, sent_today=jobs.sent_today(),
                           limit=s.get("daily_send_limit"), configured=bool(s.get("gmail_app_password")))


@app.post("/outreach/action")
def outreach_action():
    ids, action = ids_from_form(), request.form.get("action")
    if action == "send_all_approved":
        return redirect(url_for("job_view", job_id=jobs.start("send", jobs.send_approved, [])))
    if not ids:
        flash("Nothing selected.")
        return redirect(request.referrer or url_for("outreach"))
    marks = ",".join("?" * len(ids))
    with db.conn() as c:
        if action == "approve":
            c.execute(f"UPDATE outreach SET status='approved' WHERE id IN ({marks}) AND status IN ('draft','failed')", ids)
        elif action == "unapprove":
            c.execute(f"UPDATE outreach SET status='draft' WHERE id IN ({marks}) AND status='approved'", ids)
        elif action == "delete":
            c.execute(f"DELETE FROM outreach WHERE id IN ({marks}) AND status<>'sent'", ids)
    if action == "gmail_drafts":
        return redirect(url_for("job_view", job_id=jobs.start("gmail-drafts", jobs.push_gmail_drafts, ids)))
    if action == "send":
        with db.conn() as c:
            c.execute(f"UPDATE outreach SET status='approved' WHERE id IN ({marks}) AND status IN ('draft','failed')", ids)
        return redirect(url_for("job_view", job_id=jobs.start("send", jobs.send_approved, ids)))
    flash("Done.")
    return redirect(request.referrer or url_for("outreach"))


@app.route("/outreach/<int:oid>", methods=["GET", "POST"])
def outreach_detail(oid):
    if request.method == "POST":
        with db.conn() as c:
            c.execute("UPDATE outreach SET to_email=?, subject=?, body=? WHERE id=? AND status<>'sent'",
                      (request.form["to_email"].strip(), request.form["subject"], request.form["body"], oid))
            if request.form.get("approve"):
                c.execute("UPDATE outreach SET status='approved' WHERE id=? AND status IN ('draft','failed')", (oid,))
        flash("Saved.")
        return redirect(url_for("outreach_detail", oid=oid))
    with db.conn() as c:
        o = c.execute("SELECT o.*, p.domain FROM outreach o JOIN prospects p ON p.id=o.prospect_id WHERE o.id=?", (oid,)).fetchone()
    if not o:
        return redirect(url_for("outreach"))
    return render_template("outreach_edit.html", o=o)


# ------------------------------------------------------------------ templates

@app.route("/templates")
def templates_list():
    with db.conn() as c:
        rows = c.execute("SELECT * FROM templates ORDER BY is_default DESC, name").fetchall()
    return render_template("templates.html", rows=rows)


@app.route("/templates/new", methods=["GET", "POST"])
@app.route("/templates/<int:tid>", methods=["GET", "POST"])
def template_edit(tid=None):
    if request.method == "POST":
        name, subject, body = request.form["name"].strip(), request.form["subject"], request.form["body"]
        bad = mailer.unknown_vars(subject + body)
        if bad:
            flash("Unknown variables: " + ", ".join("{{%s}}" % b for b in bad) + " - they would be sent blank.")
        with db.conn() as c:
            if tid:
                c.execute("UPDATE templates SET name=?, subject=?, body=? WHERE id=?", (name, subject, body, tid))
            else:
                tid = c.execute("INSERT INTO templates(name, subject, body) VALUES (?, ?, ?)", (name, subject, body)).lastrowid
            if request.form.get("is_default"):
                c.execute("UPDATE templates SET is_default = (id=?)", (tid,))
        if not bad:
            flash("Template saved.")
        return redirect(url_for("template_edit", tid=tid))
    tpl, preview = None, None
    if tid:
        with db.conn() as c:
            tpl = c.execute("SELECT * FROM templates WHERE id=?", (tid,)).fetchone()
            p = c.execute("SELECT * FROM prospects WHERE best_email IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
            if tpl:
                if p:
                    ctx, _ = template_context(c, p, db.get_settings())
                else:
                    ctx = {v: f"[{v}]" for v in mailer.VARIABLES}
                preview = {"subject": mailer.render(tpl["subject"], ctx), "body": mailer.render(tpl["body"], ctx),
                           "from": p["domain"] if p else "sample values"}
    return render_template("template_edit.html", tpl=tpl, preview=preview)


@app.post("/templates/<int:tid>/delete")
def template_delete(tid):
    with db.conn() as c:
        if c.execute("SELECT COUNT(*) FROM templates").fetchone()[0] > 1:
            c.execute("DELETE FROM templates WHERE id=?", (tid,))
            if not c.execute("SELECT 1 FROM templates WHERE is_default=1").fetchone():
                c.execute("UPDATE templates SET is_default=1 WHERE id=(SELECT MIN(id) FROM templates)")
        else:
            flash("Keep at least one template.")
    return redirect(url_for("templates_list"))


# ------------------------------------------------------------------ blocklist

@app.route("/blocklist", methods=["GET", "POST"])
def blocklist_view():
    if request.method == "POST":
        added = 0
        for line in request.form.get("domains", "").replace(",", "\n").splitlines():
            line = line.strip().lower()
            if not line:
                continue
            dom = (net.registered_domain(line) if "://" in line else line.removeprefix("www.")).strip("/")
            with db.conn() as c:
                added += c.execute("INSERT OR IGNORE INTO blocklist(domain, added_at) VALUES (?, ?)", (dom, db.now())).rowcount
        flash(f"{added} domain(s) blocked. Blocked domains are skipped in scans, email search and drafts.")
        return redirect(url_for("blocklist_view"))
    with db.conn() as c:
        rows = c.execute("SELECT * FROM blocklist ORDER BY domain").fetchall()
    return render_template("blocklist.html", rows=rows)


@app.post("/blocklist/delete")
def blocklist_delete():
    ids = ids_from_form()
    with db.conn() as c:
        c.executemany("DELETE FROM blocklist WHERE id=?", [(i,) for i in ids])
    flash(f"{len(ids)} domain(s) unblocked.")
    return redirect(url_for("blocklist_view"))


# ------------------------------------------------------------------ settings

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        vals = {k: request.form.get(k, "").strip() for k in db.DEFAULT_SETTINGS if k != "verify_mx"}
        vals["verify_mx"] = "1" if request.form.get("verify_mx") else "0"
        if not vals["gmail_app_password"]:
            vals.pop("gmail_app_password")  # blank field = keep the saved password
        db.set_settings(vals)
        flash("Settings saved.")
        if request.form.get("test"):
            try:
                mailer.test_connection(db.get_settings())
                flash("Gmail connection OK (SMTP + IMAP).")
            except Exception as e:
                flash(f"Gmail connection failed: {e}")
        return redirect(url_for("settings"))
    return render_template("settings.html", s=db.get_settings())


if __name__ == "__main__":
    print("Outreach tool running at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False, threaded=True)
