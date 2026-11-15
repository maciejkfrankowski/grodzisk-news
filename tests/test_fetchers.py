"""Testy adapterów na próbkach offline (bez sieci)."""
import unittest

from gn.fetch import merge
from gn.fetchers import html_links, rss, tribe_events
from gn.models import clean_lead
from gn.sudoku import count_solutions, daily

SOURCE = {"id": "t", "name": "Test", "category": "powiat",
          "url": "https://example.org/aktualnosci/wszystkie/", "link_pattern": r"/aktualnosci/\d+/?$"}

HTML_LIST = """
<html><body><nav><a href="/aktualnosci/wszystkie/">Aktualności</a></nav>
<div class="list">
  <div class="row"><a href="/aktualnosci/728"><img src="a.jpg" alt=""></a>
    <div><span>06.11.2026</span><h3><a href="/aktualnosci/728">Obchody Święta Niepodległości</a></h3>
    <p>Zapraszamy mieszkańców na uroczystości.</p><a href="/aktualnosci/728">czytaj więcej</a></div></div>
  <div class="row"><span class="d">30.10.2026</span>
    <a href="https://example.org/aktualnosci/727">Powiat dla zdrowia psychicznego</a></div>
</div>
<ul><li><a href="aktualnosci/726">28.10.2026 Informacje dla inwestorów giełdowych</a></li></ul>
</body></html>
"""

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>Turniej &amp; festyn</title><link>https://example.org/2026/09/10/turniej/</link>
<pubDate>Thu, 10 Sep 2026 14:03:30 +0000</pubDate>
<description><![CDATA[<p>Zapraszamy na <b>turniej</b>.</p>]]></description></item>
</channel></rss>"""


class HtmlLinksTest(unittest.TestCase):
    def setUp(self):
        self.items = {i.url.rsplit("/", 1)[-1]: i for i in html_links.parse(HTML_LIST, SOURCE)}

    def test_finds_only_article_links(self):
        self.assertEqual(sorted(self.items), ["726", "727", "728"])

    def test_title_date_lead(self):
        item = self.items["728"]
        self.assertEqual(item.title, "Obchody Święta Niepodległości")
        self.assertEqual(item.published, "2026-11-06")
        self.assertEqual(item.lead, "Zapraszamy mieszkańców na uroczystości.")

    def test_date_outside_anchor_and_inside_anchor(self):
        self.assertEqual(self.items["727"].published, "2026-10-30")
        self.assertEqual(self.items["726"].published, "2026-10-28")
        self.assertEqual(self.items["726"].title, "Informacje dla inwestorów giełdowych")


class StripTest(unittest.TestCase):
    def test_strips_cms_suffix(self):
        html = """<div><div class="n"><a href="/aktualnosci/728">Obchody Święta Niepodległości
        (Zam: 06.11.2026 r., godz. 12.00) 193</a><p>Zapraszamy na uroczystości.</p></div>
        <div class="n"><a href="/aktualnosci/727">Inny wpis powiatu (Zam: 30.10.2026 r., godz. 10.05) 224</a></div></div>"""
        source = dict(SOURCE, strip=[r"\(Zam:[^)]*\)\s*\d*"])
        first, second = html_links.parse(html, source)
        self.assertEqual(first.title, "Obchody Święta Niepodległości")
        self.assertEqual(first.published, "2026-11-06")
        self.assertEqual(first.lead, "Zapraszamy na uroczystości.")
        self.assertEqual(second.title, "Inny wpis powiatu")


GOV_LIST = """<html><body>
<nav><ul><li><a href="/web/kppsp-grodzisk-mazowiecki/kontakt">Kontakt z komendą</a></li>
<li><a href="/web/kppsp-grodzisk-mazowiecki/aktualnosci">Aktualności komendy</a></li></ul></nav>
<div class="art-prev"><ul>
<li><a href="/web/kppsp-grodzisk-mazowiecki/dzien-flagi"><picture><img src="x.jpg" alt=""></picture>
  <div><div class="event"><span class="date">02.05.2026</span></div>
  <div class="title">Dzień Flagi Rzeczypospolitej Polskiej</div>
  <div class="intro">Strażacy uczcili święto państwowe.</div></div></a></li>
<li><a href="/web/kppsp-grodzisk-mazowiecki/24-04-2026-polmaraton"><div><span class="date">24.04.2026</span>
  <div class="title">Mistrzostwa Polski w Półmaratonie Strażaków</div></div></a></li>
</ul></div><a href="/web/kppsp-grodzisk-mazowiecki/aktualnosci?page=2">2</a></body></html>"""


class GovListTest(unittest.TestCase):
    def test_require_date_and_title_class(self):
        source = dict(SOURCE, url="https://www.gov.pl/web/kppsp-grodzisk-mazowiecki/aktualnosci",
                      link_pattern=r"/web/kppsp-grodzisk-mazowiecki/[^/?#]+$", require_date=True)
        items = html_links.parse(GOV_LIST, source)
        self.assertEqual([i.title for i in items], ["Dzień Flagi Rzeczypospolitej Polskiej",
                                                    "Mistrzostwa Polski w Półmaratonie Strażaków"])
        self.assertEqual(items[0].published, "2026-05-02")
        self.assertEqual(items[0].lead, "Strażacy uczcili święto państwowe.")
        self.assertEqual(items[1].lead, "")


class EventsTest(unittest.TestCase):
    def test_parse_and_refresh(self):
        payload = """{"events": [
          {"url": "https://e.org/wydarzenie/a/", "title": "Koncert &#8211; dla dzieci", "start_date": "2026-11-15 13:00:00",
           "all_day": false, "excerpt": "", "description": "<p>Zapraszamy na koncert familijny.</p>", "venue": {"venue": "Mediateka"}},
          {"url": "https://e.org/wydarzenie/b/", "title": "Wystawa plakatu", "start_date": "2026-11-20 00:00:00",
           "all_day": true, "excerpt": "", "description": "", "venue": []}]}"""
        first, second = tribe_events.parse(payload, SOURCE)
        self.assertEqual(first.title, "Koncert – dla dzieci")
        self.assertEqual(first.event_date, "2026-11-15 13:00:00")
        self.assertEqual(first.lead, "Mediateka · Zapraszamy na koncert familijny.")
        self.assertEqual((second.lead, second.event_date), ("", "2026-11-20 00:00:00"))
        merged, _ = merge([], [first.to_dict()])
        moved = dict(first.to_dict(), event_date="2026-11-16 18:00:00")
        merged, added = merge(merged, [moved])
        self.assertEqual((added, merged[0]["event_date"]), (0, "2026-11-16 18:00:00"))


class LeadTest(unittest.TestCase):
    def test_empty_like_leads(self):
        self.assertEqual(clean_lead("."), "")
        self.assertEqual(clean_lead(" – "), "")
        self.assertEqual(clean_lead("Szczegóły na plakacie"), "Szczegóły na plakacie")


class SudokuTest(unittest.TestCase):
    def test_daily_is_valid_unique_and_stable(self):
        today = daily("2026-11-15")
        self.assertEqual(today, daily("2026-11-15"))
        self.assertNotEqual(today, daily("2026-11-16"))
        for level in today["levels"]:
            grid = [int(c) for c in level["puzzle"]]
            self.assertEqual(count_solutions(grid[:]), 1)
            self.assertTrue(all(p in ("0", s) for p, s in zip(level["puzzle"], level["solution"])))
            for unit in range(9):
                self.assertEqual(sorted(level["solution"][unit * 9:unit * 9 + 9]), list("123456789"))


class RssTest(unittest.TestCase):
    def test_parse(self):
        (item,) = rss.parse(RSS, SOURCE)
        self.assertEqual(item.title, "Turniej & festyn")
        self.assertEqual(item.published, "2026-09-10")
        self.assertEqual(item.lead, "Zapraszamy na turniej.")


class MergeTest(unittest.TestCase):
    def test_no_duplicates(self):
        fresh = [i.to_dict() for i in html_links.parse(HTML_LIST, SOURCE)]
        merged, added = merge([], fresh)
        self.assertEqual(added, 3)
        merged, added = merge(merged, fresh)
        self.assertEqual((len(merged), added), (3, 0))


if __name__ == "__main__":
    unittest.main()
