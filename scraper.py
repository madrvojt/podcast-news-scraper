#!/usr/bin/env python3
"""
Newsroom scraper — stáhne RSS z více webů a pošle hezký HTML e-mail.
"""

import os
import re
import smtplib
import urllib.request
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html.parser import HTMLParser


# ── konfigurace ───────────────────────────────────────────────────────────────
SOURCES = [
    {
        "name": "Spotify Newsroom",
        "rss": "https://newsroom.spotify.com/feed/",
        "url": "https://newsroom.spotify.com/",
    },
    # přidej další weby sem:
    # { "name": "The Verge", "rss": "https://www.theverge.com/rss/index.xml", "url": "https://www.theverge.com" },
]

MAX_ITEMS_PER_SOURCE = 8

GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
MAIL_TO = os.environ.get("MAIL_TO", "")


# ── RSS parser ────────────────────────────────────────────────────────────────
class RSSParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self._current = {}
        self._tag = ""
        self._in_item = False

    def handle_starttag(self, tag, attrs):
        self._tag = tag
        if tag in ("item", "entry"):
            self._in_item = True
            self._current = {}

    def handle_endtag(self, tag):
        if tag in ("item", "entry") and self._in_item:
            self._in_item = False
            if self._current.get("title"):
                self.items.append(self._current.copy())
        self._tag = ""

    def handle_data(self, data):
        data = data.strip()
        if not data or not self._in_item:
            return
        t = self._tag
        if t == "title" and "title" not in self._current:
            self._current["title"] = data
        elif t == "link" and "link" not in self._current:
            self._current["link"] = data
        elif t in ("pubdate", "published", "updated") and "date" not in self._current:
            self._current["date"] = data
        elif t in ("description", "summary") and "summary" not in self._current:
            clean = re.sub(r"<[^>]+>", "", data)
            self._current["summary"] = clean[:200]


def fetch_rss(url: str) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 NewsScraper/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            content = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  ⚠️  Chyba při stahování {url}: {e}")
        return []
    parser = RSSParser()
    parser.feed(content)
    return parser.items[:MAX_ITEMS_PER_SOURCE]


# ── HTML e-mail ───────────────────────────────────────────────────────────────
def build_html(sources: list) -> str:
    today = datetime.now(timezone.utc).strftime("%-d. %-m. %Y")
    blocks = []
    total = 0

    for source in sources:
        items_html = []
        for item in source["items"]:
            total += 1
            title = re.sub(r"<[^>]+>", "", item.get("title", ""))
            link = item.get("link", "#")
            summary = re.sub(r"<[^>]+>", "", item.get("summary", ""))[:160]
            items_html.append(f"""
              <tr>
                <td style="padding:14px 0;border-bottom:1px solid #eee;">
                  <a href="{link}" style="color:#191414;text-decoration:none;font-weight:600;font-size:15px;line-height:1.4;">{title}</a>
                  {f'<div style="color:#888;font-size:13px;line-height:1.5;margin-top:5px;">{summary}…</div>' if summary else ''}
                </td>
              </tr>""")

        blocks.append(f"""
          <tr><td style="padding-top:28px;">
            <div style="font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#1DB954;padding-bottom:4px;">
              {source['name']}
            </div>
            <table width="100%" cellpadding="0" cellspacing="0">{''.join(items_html)}</table>
          </td></tr>""")

    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:24px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;max-width:600px;">
        <tr><td style="background:#191414;padding:28px 32px;">
          <div style="color:#fff;font-size:22px;font-weight:800;">📰 News Feed</div>
          <div style="color:#1DB954;font-size:13px;margin-top:4px;">{today} · {total} článků</div>
        </td></tr>
        <tr><td style="padding:0 32px 32px 32px;">
          <table width="100%" cellpadding="0" cellspacing="0">{''.join(blocks)}</table>
        </td></tr>
        <tr><td style="padding:20px 32px;background:#fafafa;border-top:1px solid #eee;color:#aaa;font-size:11px;text-align:center;">
          Automaticky generováno · podcast-news-scraper
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def send_email(html: str, count: int):
    msg = MIMEMultipart("alternative")
    today = datetime.now(timezone.utc).strftime("%-d. %-m.")
    msg["Subject"] = f"📰 Novinky {today} ({count} článků)"
    msg["From"] = GMAIL_USER
    msg["To"] = MAIL_TO
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
    print(f"✅ E-mail odeslán na {MAIL_TO}")


# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🕐 Spuštěno: {datetime.now(timezone.utc).isoformat()}")

    sources = []
    total = 0
    for source in SOURCES:
        print(f"📥 Stahuji: {source['name']}")
        items = fetch_rss(source["rss"])
        total += len(items)
        sources.append({"name": source["name"], "url": source["url"], "items": items})
        print(f"   ✅ {len(items)} článků")

    if total == 0:
        print("⚠️  Žádné články, e-mail neposílám")
    else:
        html = build_html(sources)
        send_email(html, total)

    print("🏁 Hotovo")
