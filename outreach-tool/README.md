# Outreach Tool

Websites add karo → date range choose karo → tool un dinon ke articles dhoondta hai → article body ke
external links nikaalta aur verify karta hai → un linked websites se email dhoondta hai → aapke template
se draft banata hai → review/approve ke baad aapke Gmail se send karta hai.

## Chalaane ka tareeqa

1. Python 3.10+ install karein (Windows: python.org se, install ke waqt "Add to PATH" tick karein).
2. Is folder me:
   - **Windows:** `run.bat` pe double-click
   - **Mac/Linux:** `./run.sh`
3. Browser me http://127.0.0.1:5000 khulega.
4. **Settings** me Gmail address + **App Password** daalein (normal password kaam nahi karega):
   Google Account → Security → 2-Step Verification ON → App passwords → naya banayein → 16 characters paste karein.
   "Save & test Gmail connection" dabayein.

Saara data `outreach.db` (SQLite) me aapke computer pe rehta hai. Tool sirf aapke computer pe chalta hai (127.0.0.1).

## Features

| Page | Kaam |
|---|---|
| Websites | Ek line me ek URL, bulk add / remove |
| Scan | Websites select, **From/To date**, max articles per site. Optional: scan ke foran baad email search |
| Articles | Date/website filter, har article ke external links aur unka status |
| Prospects & Emails | Har linked domain, mila hua email, source, MX check, contact page. Email edit, block, drafts banana |
| Drafts & Send | Har email edit, approve, **Gmail Drafts me save**, ya send. Daily limit + delay |
| Templates | Multiple templates, default set karna, variables, live preview |
| Blocklist | Jin domains ko kabhi scan/email nahi karna (subdomains bhi block). Social/big sites pehle se block |

Template variables: `{{site_name}} {{domain}} {{email}} {{article_title}} {{article_url}} {{source_site}}
{{linked_url}} {{anchor_text}} {{my_name}} {{my_website}}`

## Accuracy kaise rakhi gayi hai (aur kya 100% nahi ho sakta)

**Articles & dates**
- WordPress sites: WordPress REST API se exact publish date aur exact post body — sabse accurate.
- Baqi sites: RSS feed (exact date), phir sitemap. Sitemap ki `lastmod` sirf "last updated" hoti hai, isliye
  har page khol ke uski asli publish date (meta / JSON-LD / `<time>`) check hoti hai. **Jis page pe publish date
  na mile, wo skip hota hai** — galat date wala article lene se behtar hai.
- Limit: JavaScript-only sites (React SPA) aur Cloudflare "checking your browser" wali sites scan nahi hoti.

**External links**
- Sirf article body ke links. Nav, header, footer, sidebar, comments, author box, share buttons, related posts hata diye jaate hain.
- Har link live check: `live` (2xx/3xx), `blocked` (401/403/429/503 — bot protection, site maujood hai par page confirm nahi), `dead` (404 etc). Dead links prospect nahi bante.
- Redirects follow hote hain — prospect asli final domain banta hai. `utm_*` tracking hata di jaati hai.

**Emails**
- Homepage + contact / about / write-for-us / advertise pages (max 9 pages per site).
- Sources: `mailto:` links, Cloudflare-protected emails (decode), JSON-LD, page text, `name [at] site [dot] com`.
- Junk filter: image names (`logo@2x.png`), Sentry/Wix keys, `example.com`, `noreply`, theme/plugin vendor emails.
- MX check: jis domain ka mail server hi nahi, wo email drop.
- Score: site ke apne domain ka email > Gmail/Outlook > baqi; mailto > text; editor/contact/hello/info ko preference.
- **Limits:** jo site email publicly nahi dikhati (sirf contact form) — wahan `not_found` aayega, koi tool wahan email
  nahi nikaal sakta bina guess kiye. Guess (jaise `info@domain`) tool jaan boojh ke nahi karta, kyunki wo bounce hote hain
  aur aapka Gmail damage karte hain. Mailbox exist karta hai ya nahi, ye 100% confirm karna (SMTP verify) mumkin nahi —
  Gmail/Outlook har address ko "ok" bolte hain.

**Sending**
- Ek address pe sirf ek dafa email (duplicate automatically skip).
- Daily limit (default 40) aur emails ke beech random delay (default 90s ±30%).
- Fully auto-send nahi rakha: draft → review → approve → send. Cold email me galat email ya galat template
  ek baar chala jaaye to wapas nahi aata.

## Gmail ke baare me zaroori baat
Personal Gmail ki limit ~500/day hai, lekin naye account se 30-50 se zyada cold emails/day bhejne pe spam
folder ya account suspension ka risk hai. Kam se shuru karein, aur outreach ke liye alag Gmail/Google Workspace
account behtar hai. CAN-SPAM/GDPR ke mutabiq email me apna asli naam/website rakhein aur jo "no" bole usko dobara na bhejein
(us domain ko Blocklist me daal dein).

## Test
```
python -m tests.test_pipeline
```
Fake websites pe poora pipeline (WordPress API, RSS, sitemap, link verify, email find, drafts, daily limit, UI pages) test karta hai.
