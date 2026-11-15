"""Wspólny model wpisu pobranego ze źródła zewnętrznego."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from html import unescape


@dataclass
class Item:
    id: str
    source: str
    source_name: str
    category: str
    title: str
    lead: str
    url: str
    published: str  # ISO: YYYY-MM-DD
    fetched_at: str  # ISO datetime UTC

    def to_dict(self) -> dict:
        return asdict(self)


def make_id(url: str) -> str:
    return hashlib.sha1(url.strip().encode("utf-8")).hexdigest()[:16]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: str, limit: int | None = None) -> str:
    """Usuwa tagi HTML i nadmiarowe białe znaki; opcjonalnie przycina do `limit`."""
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = re.sub(r"\s+", " ", unescape(text)).strip()
    text = re.sub(r"\s+([,.;:!?…])", r"\1", text)
    # stopka dodawana przez WordPressa do zajawek w RSS
    text = re.sub(r"\s*(Artykuł .{0,200} pochodzi z serwisu|The post .{0,200} appeared first on) .*$", "", text)
    if limit and len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(",.;:–- ") + "…"
    return text


_DATE_PATTERNS = (
    (re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b"), ("d", "m", "y")),
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), ("y", "m", "d")),
)


def find_date(text: str) -> str | None:
    """Zwraca pierwszą datę z tekstu (DD.MM.RRRR lub RRRR-MM-DD) jako ISO."""
    for pattern, order in _DATE_PATTERNS:
        match = pattern.search(text or "")
        if not match:
            continue
        parts = dict(zip(order, (int(g) for g in match.groups())))
        try:
            return date(parts["y"], parts["m"], parts["d"]).isoformat()
        except ValueError:
            continue
    return None
