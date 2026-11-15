"""Adapter HTML bez znajomości klas CSS.

Szuka linków pasujących do `link_pattern` (regex na pełnym URL), a tytuł, datę
i lead bierze z najbliższego kontenera, który zawiera dokładnie jeden taki wpis.
Dzięki temu jeden adapter obsługuje strony typu /aktualnosci/{id}.

Opcje źródła: `strip` (regexy wycinane z tytułu i leadu), `require_date` (pomija linki,
przy których nie ma daty – przydatne, gdy wzorzec URL łapie też menu), `events` (wpisy to
wydarzenia: data i „godz. GG:MM” z listy trafiają do `event_date`).
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
ELLIPSIS = re.compile(r"\s*(\.{3}|…)\s*$")
TIME = re.compile(r"(?i)\bgodz\.?\s*(\d{1,2})[:.](\d{2})")
DATE = r"\b\d{1,2}\s?[.\-]\s?\d{1,2}\s?[.\-]\s?\d{4}\b(\s*r\.)?|\b\d{4}-\d{2}-\d{2}\b"


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
    text = re.sub(DATE, " ", text)
    text = TIME.sub(" ", text)
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

    events = bool(source.get("events"))
    items: list[Item] = []
    for url, group in anchors.items():
        # ten sam link bywa na stronie kilka razy (lista, siatka kalendarza, miniatura);
        # bierzemy wystąpienie, przy którym jest data
        boxes = [_container(anchor, url, base, pattern) for anchor in group]
        texts = [clean_text(box.get_text(" ")) for box in boxes]
        dated = next((n for n, text in enumerate(texts) if find_date(text)), None)
        if dated is None and (events or source.get("require_date")):
            continue  # link z menu lub stopki, nie wpis z listy
        box, box_text = boxes[dated or 0], texts[dated or 0]
        published = find_date(box_text) or date.today().isoformat()

        heading = box.find(re.compile(r"^h[1-6]$")) or box.find(class_=TITLE_CLASS)
        candidates = [clean_text(a.get_text(" ")) for a in group] + [a.get("title", "") for a in group]
        if heading:
            candidates.insert(0, clean_text(heading.get_text(" ")))
        candidates = [c for c in candidates if len(_tidy(c, strip)) >= MIN_TITLE]
        if not candidates:
            continue
        raw_title = candidates[0] if heading else max(candidates, key=len)
        title = _tidy(raw_title, strip)
        if ELLIPSIS.search(title):  # ucięty tytuł: szukamy pełnej wersji przy innym wystąpieniu linku
            stem = ELLIPSIS.sub("", title)[:20]
            full = [t for t in (_tidy(c, strip) for c in candidates)
                    if t.startswith(stem) and not ELLIPSIS.search(t)]
            title = max(full, key=len) if full else title

        event_date = ""
        if events:
            clock = TIME.search(box_text)
            event_date = f"{published} {int(clock.group(1)):02d}:{clock.group(2)}:00" if clock else f"{published} 00:00:00"
            published, lead = date.today().isoformat(), ""
        else:
            lead = _tidy(box_text.replace(raw_title, " "), strip).replace(title, " ")
            lead = re.sub(r"(?i)\b(czytaj (więcej|dalej)|więcej|zobacz)\b\s*[»>→]*", " ", lead)
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
                event_date=event_date,
            )
        )
    return items


def fetch(source: dict) -> list[Item]:
    response = http.get(source["url"])
    response.encoding = response.apparent_encoding or response.encoding
    return parse(response.text, source)
