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
        if meta.get("draft"):
            continue
        slug = meta.get("slug") or slugify(path.stem)
        articles.append({
            "title": meta["title"],
            "lead": meta.get("lead", ""),
            "published": str(meta["date"])[:10],
            "category": meta.get("category", "redakcja"),
            "image": meta.get("image", ""),
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
        item.update(href=item["url"], external=True, featured=False, image="")
    return items


def build() -> None:
    site = yaml.safe_load((ROOT / "site.yaml").read_text(encoding="utf-8"))
    categories = {c["slug"]: c for c in site["categories"]}
    fallback = site["categories"][0]

    entries = load_articles() + load_items()
    for entry in entries:
        entry["cat"] = categories.get(entry["category"], fallback)
        entry["date_pl"] = date_pl(entry["published"])
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
    (DIST / ".nojekyll").write_text("")

    def render(template: str, target: str, **context) -> None:
        path = DIST / target / "index.html" if target else DIST / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        root = "../" * target.strip("/").count("/") + "../" if target else ""
        path.write_text(env.get_template(template).render(root=root, **context), encoding="utf-8")

    # Strona główna
    hero = next((e for e in entries if e["featured"]), entries[0] if entries else None)
    rest = [e for e in entries if e is not hero]
    today, seen = [], set()
    for entry in rest:  # „Grodzisk dziś”: najnowszy wpis z każdej kategorii
        if entry["category"] not in seen:
            seen.add(entry["category"])
            today.append(entry)
    top = [e for e in rest if e not in today[:4]][:3]
    columns = [{"cat": c, "entries": [e for e in rest if e["category"] == c["slug"]][:4]}
               for c in env.globals["nav"]]
    render("index.html", "", hero=hero, today=today[:4], top=top,
           columns=[c for c in columns if c["entries"]][:3], active="")

    # Kategorie
    for cat in site["categories"]:
        render("list.html", f"kategoria/{cat['slug']}", cat=cat, active=cat["slug"],
               entries=[e for e in entries if e["category"] == cat["slug"]][:60])

    # Artykuły własne
    for entry in entries:
        if not entry["external"]:
            render("article.html", entry["href"].strip("/"), entry=entry, active="")

    render("rozrywka.html", "rozrywka", active="rozrywka")
    render("zrodla.html", "zrodla", sources=sources, active="",
           status={s["id"]: s for s in status})

    search = [{"t": e["title"], "l": e["lead"], "u": e["href"], "x": e["external"],
               "d": e["date_pl"], "s": e["source_name"]} for e in entries[:300]]
    (DIST / "search.json").write_text(json.dumps(search, ensure_ascii=False), encoding="utf-8")
    print(f"Zbudowano dist/: {len(entries)} wpisów, {len(site['categories'])} kategorii")


if __name__ == "__main__":
    build()
