# CLAUDE.md – zasady pracy w repo grodzisk-news

## Cel
Statyczny serwis lokalnych wiadomości i prostej rozrywki dla Grodziska Mazowieckiego.
Etap: demo na darmowej infrastrukturze (GitHub Actions + Pages). Docelowo możliwa migracja na VPS.

## Zasady
- Dokumentacja i komunikaty po polsku; identyfikatory w kodzie po angielsku.
- Najpierw aktualizacja `docs/`, potem kod.
- Brak backendu: stan trzymamy w repo (`data/*.json`, `content/articles/*.md`).
- Wpisy zewnętrzne: tylko tytuł, krótki lead (≤220 znaków), data i link do źródła.
  Nie kopiujemy pełnych treści ani zdjęć. Mediów komercyjnych nie pobieramy.
- Każde źródło = wpis w `sources.yaml`. Nowy adapter tylko wtedy, gdy `rss` i `html_links` nie wystarczą.
- Adapter ma funkcję `parse(content, source) -> list[Item]` (testowalna offline) i `fetch(source)`.
- Błąd jednego źródła nie może przerwać przebiegu; wynik trafia do `data/status.json`.
- Linki w szablonach zawsze przez zmienną `root` (serwis działa w podkatalogu `/grodzisk-news/`).
- Front bez frameworków i bez zewnętrznych bibliotek; JS w `static/app.js`.
- Przed commitem: `python -m unittest discover -s tests && python -m gn.build`.

## Mapa
| Ścieżka | Rola |
|---|---|
| `sources.yaml` | katalog źródeł |
| `site.yaml` | nazwa, kategorie, slot reklamowy, e-mail kontaktowy |
| `gn/fetch.py` | pobieranie + scalanie z `data/items.json` |
| `gn/fetchers/` | adaptery `rss`, `html_links`, klient HTTP |
| `gn/build.py` | generator `dist/` |
| `templates/`, `static/` | szablony Jinja2, CSS, JS |
| `content/articles/` | własne artykuły (Markdown + YAML) |
| `.github/workflows/build.yml` | cron, commit danych, deploy Pages |

## Otwarte
- Potwierdzić, że źródła nie blokują adresów IP GitHub Actions (strona `/zrodla/`).
- CMS w przeglądarce (Sveltia CMS / Pages CMS) – etap 3.
- Sudoku dnia, potem krzyżówka – etap 4.
