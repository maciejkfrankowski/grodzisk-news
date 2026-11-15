"""Adapter RSS/Atom (WordPress i pokrewne)."""
from __future__ import annotations

import time
from datetime import date

import feedparser

from ..models import Item, clean_text, make_id, now_iso
from . import http


def parse(content: bytes | str, source: dict) -> list[Item]:
    feed = feedparser.parse(content)
    fetched = now_iso()
    items: list[Item] = []
    for entry in feed.entries:
        url = (entry.get("link") or "").strip()
        title = clean_text(entry.get("title", ""))
        if not url or not title:
            continue
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        published = time.strftime("%Y-%m-%d", stamp) if stamp else date.today().isoformat()
        items.append(
            Item(
                id=make_id(url),
                source=source["id"],
                source_name=source["name"],
                category=source["category"],
                title=title,
                lead=clean_text(entry.get("summary", ""), limit=220),
                url=url,
                published=published,
                fetched_at=fetched,
            )
        )
    return items


def fetch(source: dict) -> list[Item]:
    """Próbuje `url`, a potem `fallback_urls`; przy 0 wpisów zgłasza, co zwrócił serwer."""
    notes = []
    for url in [source["url"], *source.get("fallback_urls", [])]:
        try:
            response = http.get(url)
        except RuntimeError as error:
            notes.append(str(error)[:120])
            continue
        items = parse(response.content, source)
        if items:
            return items
        snippet = clean_text(response.text[:400])[:70]
        notes.append(f"{url}: HTTP {response.status_code}, "
                     f"{response.headers.get('Content-Type', '?')}, treść: „{snippet}”")
    raise RuntimeError("0 wpisów w RSS. " + " | ".join(notes))
