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
    return parse(http.get(source["url"]).content, source)
