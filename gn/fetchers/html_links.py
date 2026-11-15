"""Adapter HTML bez znajomości klas CSS.

Szuka linków pasujących do `link_pattern` (regex na pełnym URL), a tytuł, datę
i lead bierze z najbliższego kontenera, który zawiera dokładnie jeden taki wpis.
Dzięki temu jeden adapter obsługuje strony typu /aktualnosci/{id}.
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from ..models import Item, clean_text, find_date, make_id, now_iso
from . import http

MAX_CLIMB = 5
MIN_TITLE = 8


def _container(anchor: Tag, url: str, base: str, pattern: re.Pattern) -> Tag:
    """Największy przodek, w którym wszystkie pasujące linki prowadzą do `url`."""
    best: Tag = anchor
    node = anchor.parent
    for _ in range(MAX_CLIMB):
        if node is None or node.name in ("body", "html", "[document]"):
            break
        urls = {
            urljoin(base, a["href"]).split("#")[0]
            for a in node.find_all("a", href=True)
            if pattern.search(urljoin(base, a["href"]))
        }
        if urls != {url}:
            break
        best = node
        node = node.parent
    return best


def parse(html: str, source: dict) -> list[Item]:
    base = source["url"]
    pattern = re.compile(source["link_pattern"])
    soup = BeautifulSoup(html, "lxml")
    fetched = now_iso()

    anchors: dict[str, list[Tag]] = {}
    for anchor in soup.find_all("a", href=True):
        url = urljoin(base, anchor["href"]).split("#")[0]
        if pattern.search(url):
            anchors.setdefault(url, []).append(anchor)

    items: list[Item] = []
    for url, group in anchors.items():
        box = _container(group[0], url, base, pattern)
        heading = box.find(re.compile(r"^h[1-6]$"))
        candidates = [clean_text(a.get_text(" ")) for a in group]
        if heading:
            candidates.insert(0, clean_text(heading.get_text(" ")))
        candidates += [a.get("title", "") for a in group]
        titles = [c for c in candidates if len(c) >= MIN_TITLE and not find_date(c) == c]
        if not titles:
            continue
        title = titles[0] if heading else max(titles, key=len)
        title = re.sub(r"\s*\b\d{1,2}\.\d{1,2}\.\d{4}\b\s*", " ", title).strip()

        box_text = clean_text(box.get_text(" "))
        published = find_date(box_text) or date.today().isoformat()
        lead = box_text.replace(title, " ")
        lead = re.sub(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b|\b\d{4}-\d{2}-\d{2}\b", " ", lead)
        lead = re.sub(r"(?i)\b(czytaj (więcej|dalej)|więcej|zobacz)\b\s*[»>→]*", " ", lead)
        items.append(
            Item(
                id=make_id(url),
                source=source["id"],
                source_name=source["name"],
                category=source["category"],
                title=title,
                lead=clean_text(lead, limit=220),
                url=url,
                published=published,
                fetched_at=fetched,
            )
        )
    return items


def fetch(source: dict) -> list[Item]:
    response = http.get(source["url"])
    response.encoding = response.apparent_encoding or response.encoding
    return parse(response.text, source)
