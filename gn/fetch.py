"""Pobiera wszystkie włączone źródła i scala je z data/items.json.

Uruchomienie: python -m gn.fetch
Błąd jednego źródła nie przerywa pozostałych; wynik każdego trafia do data/status.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from .fetchers import ADAPTERS
from .models import now_iso

ROOT = Path(__file__).resolve().parent.parent
ITEMS_PATH = ROOT / "data" / "items.json"
STATUS_PATH = ROOT / "data" / "status.json"
MAX_ITEMS = 600
MAX_PER_RUN = 30  # ile najnowszych wpisów bierzemy z jednego źródła na przebieg


def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def merge(existing: list[dict], fresh: list[dict]) -> tuple[list[dict], int]:
    """Dokleja nowe wpisy; istniejące zostają bez zmian (stabilna data i tytuł)."""
    known = {item["id"] for item in existing}
    titles = {(item["source"], item["title"].casefold()) for item in existing}
    added = 0
    for item in fresh:
        key = (item["source"], item["title"].casefold())
        if item["id"] in known or key in titles:
            continue
        existing.append(item)
        known.add(item["id"])
        titles.add(key)
        added += 1
    existing.sort(key=lambda i: (i["published"], i["fetched_at"]), reverse=True)
    return existing[:MAX_ITEMS], added


def run() -> int:
    sources = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))["sources"]
    items = load_json(ITEMS_PATH, [])
    status = []
    for source in sources:
        if not source.get("enabled", True):
            continue
        entry = {"id": source["id"], "name": source["name"], "url": source["url"],
                 "home": source.get("home", source["url"]), "checked_at": now_iso()}
        try:
            fetched = ADAPTERS[source["adapter"]](source)
            fresh = sorted((i.to_dict() for i in fetched), key=lambda i: i["published"],
                           reverse=True)[:MAX_PER_RUN]
            items, added = merge(items, fresh)
            entry.update(ok=bool(fetched), found=len(fetched), added=added,
                         error="" if fetched else "0 wpisów – sprawdź strukturę strony")
        except Exception as error:  # noqa: BLE001 – jedno źródło nie może zatrzymać reszty
            entry.update(ok=False, found=0, added=0, error=str(error)[:300])
        status.append(entry)
        print(f"[{'OK ' if entry['ok'] else 'ERR'}] {entry['id']}: znaleziono {entry['found']}, "
              f"nowych {entry['added']} {entry['error']}")
    save_json(ITEMS_PATH, items)
    save_json(STATUS_PATH, status)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
