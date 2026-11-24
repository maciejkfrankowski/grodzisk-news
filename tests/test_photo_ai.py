"""Testy doboru ilustracji modelem AI – bez sieci (odpowiedź modelu jest podstawiana)."""
import json
import unittest
from pathlib import Path
from unittest import mock

from gn import photo_ai

ROOT = Path(__file__).resolve().parent.parent
ENTRIES = [{"id": "a1", "title": "Skradziono rower sprzed sklepu", "lead": "Policja szuka sprawcy."},
           {"id": "b2", "title": "Dziki lokator w pustostanie", "lead": ""},
           {"id": "c3", "title": "Tragiczny wypadek na obwodnicy", "lead": ""}]


class CatalogTest(unittest.TestCase):
    def test_catalog_matches_pool_files(self):
        catalog = photo_ai.load_catalog()
        described = {key for group in catalog.values() for key in group["scenes"]}
        for topic, group in catalog.items():
            self.assertTrue(all(key.startswith(topic + "-") for key in group["scenes"]), topic)
        files = {p.stem for p in (ROOT / "static" / "img" / "topics-photo").glob("*.jpg")}
        if files:  # paczka z kodem nie zawiera obrazów; w repo sprawdzamy zgodność
            self.assertEqual(files - described, set(), "pliki bez opisu w photo_scenes.yaml")

    def test_catalog_limited_to_pool(self):
        catalog = photo_ai.load_catalog({"police": ["police-4.jpg"], "road": []})
        self.assertEqual(list(catalog), ["police"])
        self.assertEqual(list(catalog["police"]["scenes"]), ["police-4"])

    def test_prompt_lists_every_scene(self):
        catalog = photo_ai.load_catalog()
        prompt = photo_ai.system_prompt(catalog)
        self.assertIn("police-4: a bicycle locked", prompt)
        self.assertIn('"items"', prompt)
        self.assertEqual(sum(len(g["scenes"]) for g in catalog.values()), 114)


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.catalog = photo_ai.load_catalog()

    def parse(self, payload):
        text = payload if isinstance(payload, str) else json.dumps(payload)
        return photo_ai.parse_answer(text, ENTRIES, self.catalog)

    def test_valid_answer_with_code_fence(self):
        text = '```json\n{"items": [{"id": 1, "topic": "police", "picks": ["police-4", "police-5"]}]}\n```'
        self.assertEqual(self.parse(text), {"a1": {"topic": "police", "picks": ["police-4", "police-5"]}})

    def test_rejects_unknown_ids_topics_and_foreign_files(self):
        result = self.parse({"items": [
            {"id": 9, "topic": "police", "picks": ["police-1"]},           # numer spoza paczki
            {"id": 1, "topic": "crime", "picks": ["police-1"]},            # temat spoza katalogu
            {"id": "2", "topic": "general", "picks": ["boar-1", "general-4", "general-4", "general-9", 7]},
        ]})
        self.assertEqual(result, {"b2": {"topic": "general", "picks": ["general-4"]}})

    def test_none_and_pick_limit(self):
        result = self.parse({"items": [
            {"id": 3, "topic": "none", "picks": ["police-1"]},
            {"id": 1, "topic": "Police", "picks": ["police-4", "police-5", "police-1", "police-2"]},
        ]})
        self.assertEqual(result["c3"], {"topic": "none", "picks": []})
        self.assertEqual(result["a1"]["picks"], ["police-4", "police-5", "police-1"])

    def test_truncated_answer_keeps_complete_items(self):
        text = ('{"items": [{"id": 1, "topic": "police", "picks": ["police-4"]},\n'
                ' {"id": 2, "topic": "general", "picks": ["general-1"]},\n {"id": 3, "topic": "no')
        self.assertEqual(list(self.parse(text)), ["a1", "b2"])

    def test_garbage_gives_empty_result(self):
        for text in ("", "Nie wiem.", '{"items": "x"}', '{"items": [1, null]}', "{broken", '{"id": 1, "picks": "x"}'):
            self.assertEqual(self.parse(text), {})


class ClassifyTest(unittest.TestCase):
    def test_failed_batch_does_not_stop_the_rest(self):
        catalog = photo_ai.load_catalog()
        entries = [{"id": f"e{n}", "title": "t", "lead": ""} for n in range(photo_ai.BATCH + 2)]
        answers = [RuntimeError("503"), ({"e25": {"topic": "road", "picks": []}}, {"prompt_tokens": 10})]
        with mock.patch.object(photo_ai, "ask", side_effect=answers):
            results, usage = photo_ai.classify(entries, catalog)
        self.assertEqual(list(results), ["e25"])
        self.assertEqual((usage["calls"], usage["prompt_tokens"], len(usage["errors"])), (2, 10, 1))

    def test_call_limit(self):
        entries = [{"id": f"e{n}", "title": "t", "lead": ""} for n in range(photo_ai.BATCH * 3)]
        with mock.patch.object(photo_ai, "ask", return_value=({}, {})) as ask:
            photo_ai.classify(entries, photo_ai.load_catalog(), max_calls=2)
        self.assertEqual(ask.call_count, 2)

    def test_request_shape_and_missing_key(self):
        catalog = photo_ai.load_catalog()
        with mock.patch.dict("os.environ", {}, clear=True), self.assertRaises(RuntimeError):
            photo_ai.ask(ENTRIES, catalog)
        reply = mock.Mock()
        reply.json.return_value = {"choices": [{"message": {"content": None}, "finish_reason": "length"}],
                                   "usage": {"prompt_tokens": 5}}
        with mock.patch.object(photo_ai.requests, "post", return_value=reply) as post:
            found, usage = photo_ai.ask(ENTRIES, catalog, key="test")
        self.assertEqual(found, {})
        self.assertIn("finish_reason=length", usage["note"])
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["model"], photo_ai.DEFAULT_MODEL)
        self.assertIn("Skradziono rower", body["messages"][1]["content"])
        self.assertNotIn("a1", body["messages"][1]["content"])  # do modelu idzie numer, nie identyfikator
        self.assertGreaterEqual(body["max_tokens"], 4000)


if __name__ == "__main__":
    unittest.main()
