#!/usr/bin/env python3
"""
Spotify Newsroom scraper — běží v GitHub Actions,
výsledky zapíše do news.json (git commit udělá workflow).
"""

import json
import re
import urllib.request
from datetime import datetime, timezone
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

MAX_ITEMS_PER_SOURCE = 10
OUTPUT_FILE = "news.json"


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
            self._current["summary"] = clean[:300]


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


if __name__ == "__main__":
    print(f"🕐 Spuštěno: {datetime.now(timezone.utc).isoformat()}")

    results = []
    for source in SOURCES:
        print(f"📥 Stahuji: {source['name']}")
        items = fetch_rss(source["rss"])
        results.append({
            "source": source["name"],
            "url": source["url"],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "items": items,
        })
        print(f"   ✅ {len(items)} článků")

    payload = {"updated_at": datetime.now(timezone.utc).isoformat(), "sources": results}

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"💾 Uloženo do {OUTPUT_FILE}")
    print("🏁 Hotovo")
