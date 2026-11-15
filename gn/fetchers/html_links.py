"""Adapter HTML bez znajomości klas CSS.

Szuka linków pasujących do `link_pattern` (regex na pełnym URL), a tytuł, datę
i lead bierze z najbliższego kontenera, który zawiera dokładnie jeden taki wpis.
Dzięki temu jeden adapter obsługuje strony typu /aktualnosci/{id}.

Opcje źródła: `strip` (regexy wycinane z tytułu i leadu), `require_date` (pomija linki,
przy których nie ma daty – przydatne, gdy wzorzec URL łapie też menu).
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from ..models import Item, clean_lead, clean_text, find_date, make_id, now_iso
from . import http

MAX_CLIMB = 5
MIN_TITLE = 8
TITLE_CLASS = re.compile(r"title|tytul", re.I)


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


def _tidy(text: str, strip: list[re.Pattern]) -> str:
    """Usuwa fragmenty z `strip` (sources.yaml) oraz daty wplecione w tekst."""
    for pattern in strip:
        text = pattern.sub(" ", text)
    text = re.sub(r"(\b\d{1,2}\.\d{1,2}\.\d{4}\b(\s*r\.)?|\b\d{4}-\d{2}-\d{2}\b)", " ", text)
    return clean_text(text)


def parse(html: str, source: dict) -> list[Item]:
    base = source["url"]
    strip = [re.compile(p) for p in source.get("strip", [])]
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
        heading = box.find(re.compile(r"^h[1-6]$")) or box.find(class_=TITLE_CLASS)
        candidates = [clean_text(a.get_text(" ")) for a in group]
        if heading:
            candidates.insert(0, clean_text(heading.get_text(" ")))
        candidates += [a.get("title", "") for a in group]
        titles = [c for c in candidates if len(c) >= MIN_TITLE and not find_date(c) == c]
        if not titles:
            continue
        raw_title = titles[0] if heading else max(titles, key=len)

        box_text = clean_text(box.get_text(" "))
        published = find_date(box_text)
        if not published and source.get("require_date"):
            continue  # link z menu lub stopki, nie wpis z listy
        published = published or date.today().isoformat()
        title = _tidy(raw_title, strip)
        lead = _tidy(box_text.replace(raw_title, " "), strip).replace(title, " ")
        lead = re.sub(r"(?i)\b(czytaj (więcej|dalej)|więcej|zobacz)\b\s*[»>→]*", " ", lead)
        if len(title) < MIN_TITLE:
            continue
        items.append(
            Item(
                id=make_id(url),
                source=source["id"],
                source_name=source["name"],
                category=source["category"],
                title=title,
                lead=clean_lead(lead),
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
