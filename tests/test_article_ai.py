"""Testy notek z oficjalnych komunikatów – bez sieci (strona źródła i odpowiedź modelu są podstawiane)."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import yaml

from gn import article_ai
from gn.build import attach_releases

TEXT = ("Od poniedziałku 30 listopada 2026 r. linia nr 5 pojedzie zmienioną trasą. Powodem jest remont "
        "ulicy Sienkiewicza prowadzony przez Zarząd Dróg Powiatowych. Autobusy ominą przystanek "
        "Sienkiewicza 02 i zatrzymają się na przystanku tymczasowym przy ulicy 11 Listopada. "
        "Zmiana potrwa do 18 grudnia. Rozkład jazdy jest dostępny na stronie przewoźnika oraz pod numerem "
        "22 755 55 34. Bilety zachowują ważność. Kierowcy sprzedają bilety jednorazowe w cenie 4 zł. "
        "Prosimy pasażerów o zwracanie uwagi na komunikaty wywieszone na przystankach.")
PAGE = f"""<html><head><title>GPA</title><script>var x = 1;</script></head><body>
<nav><a href="/">Start</a><a href="/rozklady">Rozkłady jazdy</a></nav>
<header><h1>Grodziskie Przewozy Autobusowe</h1></header>
<article><header><h2>Zmiana trasy linii 5</h2></header>
<div class="entry-content"><p>{TEXT[:300]}</p><p>{TEXT[300:]}</p>
<form><input name="q"><button>Szukaj</button></form></div></article>
<aside>Najczęściej czytane: Cennik biletów 2026</aside>
<footer>Kontakt: biuro@example.com, tel. 99 999 99 99</footer></body></html>"""
ITEM = {"id": "abcdef0123456789", "source": "gpa", "source_name": "Grodziskie Przewozy Autobusowe",
        "category": "transport", "title": "Zmiana trasy linii 5", "lead": "", "published": "2026-11-24",
        "url": "https://example.org/aktualnosci/101/", "fetched_at": "2026-11-24T10:00:00+00:00"}
GOOD = {"title": "Linia 5 zmienia trasę na czas remontu ulicy Sienkiewicza",
        "lead": "Od 30 listopada autobusy linii nr 5 omijają przystanek Sienkiewicza 02. Objazd potrwa do 18 grudnia.",
        "body": ("Autobusy linii nr 5 od poniedziałku 30 listopada jeżdżą inną trasą. Przewoźnik tłumaczy to remontem "
                 "ulicy Sienkiewicza, który prowadzi Zarząd Dróg Powiatowych.\n\nNa czas robót wyłączony jest przystanek "
                 "Sienkiewicza 02. Pasażerowie wsiadają na przystanku tymczasowym przy ulicy 11 Listopada. "
                 "Zmiana ma obowiązywać do 18 grudnia.\n\nBilety pozostają ważne, a u kierowcy można kupić bilet "
                 "jednorazowy za 4 zł. Rozkład jazdy przewoźnik udostępnia na swojej stronie i pod numerem 22 755 55 34.")}
SOURCES = [{"id": "gpa", "article": "auto"}, {"id": "policja", "article": "draft"}, {"id": "ck"}]
SITE = {"title": "Grodzisk Mazowiecki", "lang": "pl"}


def answer(payload) -> tuple[str, dict]:
    return json.dumps(payload, ensure_ascii=False), {"prompt_tokens": 100, "completion_tokens": 50}


class ExtractTest(unittest.TestCase):
    def test_content_without_menu_footer_and_forms(self):
        text = article_ai.extract_text(PAGE)
        self.assertIn("linia nr 5 pojedzie zmienioną trasą", text)
        self.assertIn("zwracanie uwagi na komunikaty", text)
        for junk in ("Rozkłady jazdy", "Szukaj", "Cennik biletów", "biuro@example.com", "var x"):
            self.assertNotIn(junk, text)

    def test_fallback_picks_block_with_most_paragraph_text(self):
        page = (f"<body><div id='menu'><p>Start</p><p>Kontakt</p></div><div class='tresc'><p>{TEXT[:300]}</p>"
                f"<p>{TEXT[300:]}</p></div><div class='stopka'><p>Wszelkie prawa zastrzeżone</p></div></body>")
        text = article_ai.extract_text(page)
        self.assertTrue(text.startswith("Od poniedziałku"))
        self.assertNotIn("Wszelkie prawa", text)

    def test_selector_from_source_wins(self):
        page = f"<body><article><p>{TEXT}</p></article><div class='komunikat'><p>Tylko to.</p></div></body>"
        self.assertEqual(article_ai.extract_text(page, ".komunikat"), "Tylko to.")


class ParseTest(unittest.TestCase):
    def test_json_with_fences_and_markup(self):
        raw = '```json\n{"title": "Tytuł.", "lead": "<b>Zajawka</b>", "body": "Raz [link](https://x.pl).\\n\\n## Dwa **mocno**"}\n```'
        self.assertEqual(article_ai.parse_answer(raw),
                         {"title": "Tytuł", "lead": "Zajawka", "body": "Raz link.\n\nDwa mocno"})

    def test_skip_and_garbage(self):
        self.assertEqual(article_ai.parse_answer('{"skip": "sam plakat"}'), {"skip": "sam plakat"})
        self.assertEqual(article_ai.parse_answer("Nie mogę pomóc."), {})
        self.assertEqual(article_ai.parse_answer('{"title": "Bez treści"}'), {})


class ValidateTest(unittest.TestCase):
    source = article_ai.user_prompt(ITEM, TEXT)

    def test_clean_article_has_no_notes(self):
        self.assertEqual(article_ai.validate(GOOD, self.source), [])

    def test_number_formats_are_equivalent(self):
        source = "Koszt: 1500 zł, termin 05.12, telefon 22 755 55 34, dotacja 12 000 zł."
        same = {"title": "t", "lead": "", "body": "1 500 zł do 5 grudnia, tel. 22 755 55 34, dotacja 12000 zł"}
        self.assertEqual(article_ai.unsupported_numbers(same, source), [])
        self.assertEqual(article_ai.unsupported_numbers(dict(same, lead="2 500 zł"), source), ["2500"])

    def test_invented_number(self):
        bad = dict(GOOD, body=GOOD["body"].replace("za 4 zł", "za 6 zł"))
        self.assertEqual(article_ai.unsupported_numbers(bad, self.source), ["6"])
        self.assertIn("liczby spoza komunikatu: 6", article_ai.validate(bad, self.source))

    def test_invented_name_but_declension_allowed(self):
        bad = dict(GOOD, body=GOOD["body"].replace("Przewoźnik tłumaczy", "Rzecznik Jan Kowalski tłumaczy"))
        notes = article_ai.validate(bad, self.source)
        self.assertEqual(notes, ["nazwy spoza komunikatu: Jan, Kowalski"])
        declined = dict(GOOD, body=GOOD["body"].replace("ulicy Sienkiewicza, który", "ulicy Sienkiewicza w Grodzisku, który"))
        self.assertEqual(article_ai.validate(declined, self.source + " Grodzisk"), [])

    def test_invented_quote_and_length(self):
        bad = dict(GOOD, body=GOOD["body"] + " „Bardzo przepraszamy wszystkich pasażerów za utrudnienia” – dodał.")
        self.assertTrue(any(note.startswith("cytat spoza komunikatu") for note in article_ai.validate(bad, self.source)))
        short = dict(GOOD, body="Za krótko.")
        self.assertIn("długość treści: 10 znaków", article_ai.validate(short, self.source))


class AnnotateTest(unittest.TestCase):
    def run_once(self, items, answers, page=PAGE):
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.dict("os.environ", {article_ai.KEY_ENV: "k"}), \
                mock.patch.object(article_ai.http, "get", return_value=mock.Mock(text=page)), \
                mock.patch.object(article_ai, "complete", side_effect=answers) as model, \
                mock.patch.object(article_ai, "pending", wraps=lambda i, m, today=None: article_ai.__dict__["_pending"](i, m, date(2026, 11, 24))):
            message = article_ai.annotate(items, SOURCES, SITE, Path(folder))
            files = {p.name: p.read_text(encoding="utf-8") for p in (Path(folder) / article_ai.FOLDER).glob("*.md")}
        return message, files, model

    @classmethod
    def setUpClass(cls):
        article_ai._pending = article_ai.pending

    def test_auto_source_is_published_with_source_fields(self):
        items = [dict(ITEM)]
        message, files, _ = self.run_once(items, [answer(GOOD)])
        self.assertEqual(items[0]["article"]["state"], "published")
        name, raw = next(iter(files.items()))
        self.assertEqual(name, items[0]["article"]["file"])
        self.assertTrue(name.startswith("2026-11-24-linia-5-zmienia-trase") and name.endswith("-abcdef.md"))
        meta = yaml.safe_load(raw.split("---")[1])
        self.assertEqual((meta["draft"], meta["item_id"], meta["source_url"], meta["category"], meta["check_notes"]),
                         (False, ITEM["id"], ITEM["url"], "transport", ""))
        self.assertIn("opublikowane 1, szkice 0", message)

    def test_draft_source_sensitive_topic_and_notes_become_drafts(self):
        police = dict(ITEM, id="1111111111111111", source="policja")
        sensitive = dict(ITEM, id="2222222222222222", photo_ai={"topic": "none", "picks": []})
        invented = dict(ITEM, id="3333333333333333")
        bad = dict(GOOD, body=GOOD["body"].replace("Przewoźnik tłumaczy", "Rzecznik Jan Kowalski tłumaczy"))
        items = [police, sensitive, invented]
        _, files, _ = self.run_once(items, [answer(GOOD), answer(GOOD), answer(bad)])
        self.assertEqual([item["article"]["state"] for item in items], ["draft"] * 3)
        self.assertEqual(sensitive["article"]["note"], "temat wrażliwy")
        self.assertIn("Jan, Kowalski", invented["article"]["note"])
        self.assertTrue(all(yaml.safe_load(raw.split("---")[1])["draft"] for raw in files.values()))

    def test_wrong_number_gets_one_retry(self):
        items = [dict(ITEM)]
        bad = dict(GOOD, body=GOOD["body"].replace("za 4 zł", "za 6 zł"))
        _, _, model = self.run_once(items, [answer(bad), answer(GOOD)])
        self.assertEqual(model.call_count, 2)
        self.assertIn("not in the announcement: 6", model.call_args_list[1].args[0][-1]["content"])
        self.assertEqual(items[0]["article"]["state"], "published")

    def test_short_skip_unreadable_and_untouched(self):
        short = [dict(ITEM)]
        self.run_once(short, [], page="<article><p>Zapraszamy na plakat.</p></article>")
        self.assertEqual(short[0]["article"]["state"], "skipped")
        items = [dict(ITEM, id="a" * 16), dict(ITEM, id="b" * 16), dict(ITEM, id="c" * 16, source="ck"),
                 dict(ITEM, id="d" * 16, published="2026-11-01"), dict(ITEM, id="e" * 16, event_date="2026-12-01 18:00:00")]
        _, files, model = self.run_once(items, [answer({"skip": "sam plakat"}), ("bzdury", {})])
        self.assertEqual([item.get("article", {}).get("state") for item in items],
                         ["skipped", "rejected", None, None, None])
        self.assertEqual((files, model.call_count), ({}, 2))

    def test_network_error_leaves_item_for_next_run(self):
        items = [dict(ITEM)]
        message, _, _ = self.run_once(items, [RuntimeError("502")])
        self.assertNotIn("article", items[0])
        self.assertIn("błędy: gpa: 502", message)

    def test_disabled_without_key_or_sources(self):
        with mock.patch.dict("os.environ", {article_ai.KEY_ENV: ""}):
            self.assertIn("wyłączone", article_ai.annotate([dict(ITEM)], SOURCES, SITE))
        self.assertIn("żadne źródło", article_ai.annotate([dict(ITEM)], [{"id": "gpa"}], SITE))


class BuildTest(unittest.TestCase):
    def test_release_replaces_its_item_and_takes_thumbnail(self):
        items = [{"id": "a", "source": "gpa", "image": "https://x/a.jpg", "photo_ai": {"topic": "bus", "picks": []}},
                 {"id": "b", "source": "gpa", "image": ""}]
        releases = [{"item_id": "a", "image": ""}, {"item_id": "dawno-usuniety", "image": ""}]
        left = attach_releases(releases, items)
        self.assertEqual([item["id"] for item in left], ["b"])
        self.assertEqual((releases[0]["image"], releases[0]["id"], releases[0]["photo_ai"]["topic"]),
                         ("https://x/a.jpg", "a", "bus"))
        self.assertEqual(releases[1]["image"], "")


if __name__ == "__main__":
    unittest.main()
