"""Testy adapterów na próbkach offline (bez sieci)."""
import unittest

from gn.fetch import merge
from gn.fetchers import html_links, rss

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
