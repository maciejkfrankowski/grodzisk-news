# grodzisk-news

Statyczny serwis z lokalnymi wiadomościami z Grodziska Mazowieckiego. GitHub Actions raz dziennie
pobiera komunikaty ze źródeł publicznych, zapisuje je w `data/items.json` i publikuje stronę na
GitHub Pages. Własne artykuły to pliki Markdown w `content/articles/`.

## Uruchomienie lokalne

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests   # testy offline
python -m gn.fetch                     # pobranie źródeł -> data/
python -m gn.build                     # generacja -> dist/
python -m http.server -d dist 8000     # podgląd: http://localhost:8000
```

## Pierwsze wdrożenie

1. Utwórz puste publiczne repo `maciejkfrankowski/grodzisk-news`.
2. Wypchnij kod:
   ```bash
   git init -b main && git add . && git commit -m "init: szkielet serwisu"
   git remote add origin https://github.com/maciejkfrankowski/grodzisk-news.git
   git push -u origin main
   ```
3. Settings → Pages → Source: **GitHub Actions**.
4. Actions → „Pobierz i opublikuj” → Run workflow (albo poczekaj na push/cron).
5. Strona: `https://maciejkfrankowski.github.io/grodzisk-news/`; stan źródeł: `/zrodla/`.

## Panel redakcji (CMS)

Adres: `https://maciejkfrankowski.github.io/grodzisk-news/admin/` (link „Panel redakcji” w stopce).
Panel to Sveltia CMS – działa w przeglądarce i zapisuje artykuły jako commity do tego repo.

Logowanie tokenem GitHuba (jednorazowo na przeglądarkę):

1. GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token.
2. Repository access: **Only select repositories** → `grodzisk-news`.
3. Permissions → Repository permissions → **Contents: Read and write**.
4. Skopiuj token, w panelu wybierz **Sign In Using Access Token** i wklej go.

Token daje prawo zapisu do repo – nie udostępniaj go i ustaw datę wygaśnięcia.
Po zapisaniu artykułu strona przebudowuje się sama (ok. 1–2 min). Zdjęcia trafiają do `static/img/uploads/`.

## Nowy artykuł ręcznie

Plik `content/articles/RRRR-MM-DD-tytul.md`:

```markdown
---
title: Tytuł
date: 2026-11-20
category: redakcja        # slug z site.yaml
lead: Jedno zdanie zajawki.
image: static/img/foto.jpg  # opcjonalnie
featured: true              # opcjonalnie: trafia do hero
draft: false                # true = nie publikuj
---
Treść w Markdownie.
```

Commit do `main` uruchamia przebudowę.

## Nowa krzyżówka

Wrzuć samodzielny plik HTML do `content/krzyzowki/` (np. `potop.html`). Generator skopiuje go do
`/rozrywka/krzyzowki/{nazwa}/`, doklei pasek powrotu do serwisu i doda kartę na stronie Rozrywka
(tytuł karty bierze z `<title>` pliku).

## Nowe źródło

Dopisz wpis w `sources.yaml` (`adapter: rss` albo `html_links` + `link_pattern`). Szczegóły:
`docs/01-architektura.md`, lista kandydatów: `docs/02-zrodla.md`.
