"""Generator statyczny: data/items.json + content/articles/*.md -> dist/.

Uruchomienie: python -m gn.build
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import clean_lead
from .sudoku import daily

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
          "sierpnia", "września", "października", "listopada", "grudnia"]
PL_MAP = str.maketrans("ąćęłńóśźż", "acelnoszz")


def date_pl(iso: str) -> str:
    year, month, day = (int(part) for part in iso[:10].split("-"))
    return f"{day} {MONTHS[month - 1]} {year}"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().translate(PL_MAP)).strip("-")


def load_articles() -> list[dict]:
    """Własne artykuły: Markdown z nagłówkiem YAML między liniami `---`."""
    articles = []
    for path in sorted((ROOT / "content" / "articles").glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
        if not match:
            print(f"[POMINIĘTO] {path.name}: brak nagłówka YAML")
            continue
        meta = yaml.safe_load(match.group(1)) or {}
        if meta.get("draft") or not meta.get("title") or not meta.get("date"):
            continue
        slug = meta.get("slug") or slugify(path.stem)
        articles.append({
            "title": meta["title"],
            "lead": meta.get("lead") or "",
            "published": str(meta["date"])[:10],
            "category": meta.get("category") or "redakcja",
            "image": str(meta.get("image") or "").lstrip("/"),
            "image_credit": str(meta.get("image_credit") or "").strip(),
            "featured": bool(meta.get("featured")),
            "href": f"artykul/{slug}/",
            "external": False,
            "source_name": "Redakcja",
            "body": markdown.markdown(match.group(2), extensions=["extra"]),
        })
    return articles


def load_items() -> list[dict]:
    path = ROOT / "data" / "items.json"
    items = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    for item in items:
        item.update(href=item["url"], external=True, featured=False, image="",
                    event_date=item.get("event_date", ""))
        if not item["event_date"]:
            item["lead"] = clean_lead(item["lead"])
    return items


def event_labels(stamp: str) -> dict:
    """Etykiety terminu wydarzenia z `RRRR-MM-DD GG:MM:SS`."""
    year, month, day = (int(part) for part in stamp[:10].split("-"))
    time = stamp[11:16] if stamp[11:16] not in ("", "00:00") else ""
    return {"event_pl": f"{day} {MONTHS[month - 1]}" + (f", godz. {time}" if time else ""),
            "event_day": day, "event_mon": MONTHS[month - 1][:3]}


BACK_BAR = ('<a href="../../" style="display:block;padding:10px 14px;background:#173b2a;color:#fff;'
            'font:600 14px system-ui,sans-serif;text-decoration:none">← Grodzisk lokalnie · Rozrywka</a>')


def build_crosswords() -> list[dict]:
    """Kopiuje gotowe krzyżówki (samodzielne pliki HTML) do dist/rozrywka/krzyzowki/.

    Do każdej dokleja pasek powrotu do serwisu; plik źródłowy pozostaje bez zmian.
    """
    found = []
    for path in sorted((ROOT / "content" / "krzyzowki").glob("*.html")):
        html = path.read_text(encoding="utf-8")
        title = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
        slug = slugify(path.stem)
        html = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + BACK_BAR.replace("../../", "../../"),
                      html, count=1, flags=re.I)
        target = DIST / "rozrywka" / "krzyzowki" / slug / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        name = (title.group(1).strip() if title else path.stem)
        found.append({"title": re.sub(r"\s*[–-]\s*krzyżówka\s*$", "", name, flags=re.I),
                      "href": f"rozrywka/krzyzowki/{slug}/"})
    return found


def build() -> None:
    site = yaml.safe_load((ROOT / "site.yaml").read_text(encoding="utf-8"))
    categories = {c["slug"]: c for c in site["categories"]}
    fallback = site["categories"][0]

    today_iso = date.today().isoformat()
    everything = load_articles() + load_items()
    for entry in everything:
        entry.setdefault("event_date", "")
        entry["cat"] = categories.get(entry["category"], fallback)
        entry["date_pl"] = date_pl(entry["published"])
        if entry["event_date"]:
            entry.update(event_labels(entry["event_date"]))
    # Wydarzenia (z terminem) idą osobnym torem: tylko nadchodzące, od najbliższego
    events = sorted((e for e in everything if e["event_date"][:10] >= today_iso),
                    key=lambda e: e["event_date"])
    entries = [e for e in everything if not e["event_date"]]
    entries.sort(key=lambda e: (e["published"], not e["external"]), reverse=True)

    status_path = ROOT / "data" / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else []
    sources = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))["sources"]

    env = Environment(loader=FileSystemLoader(ROOT / "templates"),
                      autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
    env.globals.update(site=site, nav=[c for c in site["categories"] if c.get("nav", True)],
                       build_date=date_pl(date.today().isoformat()))

    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(ROOT / "static", DIST / "static")
    shutil.copytree(ROOT / "admin", DIST / "admin")
    (DIST / ".nojekyll").write_text("")

    def render(template: str, target: str, **context) -> None:
        path = DIST / target / "index.html" if target else DIST / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        root = "../" * target.strip("/").count("/") + "../" if target else ""
        path.write_text(env.get_template(template).render(root=root, **context), encoding="utf-8")

    # Strona główna
    hero = next((e for e in entries if e["featured"]), entries[0] if entries else None)
    rest = [e for e in entries if e is not hero]
    today, seen = events[:2], set()
    for entry in rest:  # „Grodzisk dziś”: najnowszy wpis z każdej kategorii
        if entry["category"] not in seen:
            seen.add(entry["category"])
            today.append(entry)
    top = [e for e in rest if e not in today[:4]][:3]
    columns = [{"cat": c, "entries": [e for e in rest if e["category"] == c["slug"]][:4]}
               for c in env.globals["nav"]]
    render("index.html", "", hero=hero, today=today[:4], top=top, events=events[2:6] or events[:4],
           columns=[c for c in columns if c["entries"]][:3], active="")

    # Kategorie
    for cat in site["categories"]:
        render("list.html", f"kategoria/{cat['slug']}", cat=cat, active=cat["slug"],
               entries=[e for e in entries if e["category"] == cat["slug"]][:60])

    # Artykuły własne
    for entry in entries:
        if not entry["external"]:
            render("article.html", entry["href"].strip("/"), entry=entry, active="")

    crosswords = build_crosswords()
    render("wydarzenia.html", "wydarzenia", entries=events[:80], active="wydarzenia")
    render("rozrywka.html", "rozrywka", active="rozrywka", sudoku=daily(today_iso), crosswords=crosswords,
           sudoku_date=date_pl(today_iso))
    render("zrodla.html", "zrodla", sources=sources, active="",
           status={s["id"]: s for s in status})

    search = [{"t": e["title"], "l": e["lead"], "u": e["href"], "x": e["external"],
               "d": e.get("event_pl") or e["date_pl"], "s": e["source_name"]}
              for e in events[:80] + entries[:300]]
    (DIST / "search.json").write_text(json.dumps(search, ensure_ascii=False), encoding="utf-8")
    print(f"Zbudowano dist/: {len(entries)} wpisów, {len(events)} wydarzeń, {len(site['categories'])} kategorii")


if __name__ == "__main__":
    build()
