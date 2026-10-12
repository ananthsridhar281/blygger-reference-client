import unittest
from blygger.read.feed import parse_feed

FEED = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:blyg="https://blygger.org/ns/0.1">
  <channel>
    <blyg:manifest>https://x/blyg/blyg.json</blyg:manifest>
    <item>
      <guid isPermaLink="false">blyg:AAAAAAAAAAAAAAAAAAAAAAAAAA:v2</guid>
      <blyg:id>AAAAAAAAAAAAAAAAAAAAAAAAAA</blyg:id>
      <blyg:kind>fragment</blyg:kind>
      <blyg:version>2</blyg:version>
      <blyg:item>https://x/blyg/items/AAAAAAAAAAAAAAAAAAAAAAAAAA.json</blyg:item>
    </item>
  </channel>
</rss>"""

class TestFeed(unittest.TestCase):
    def test_parse_entries(self):
        entries = parse_feed(FEED)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["id"], "AAAAAAAAAAAAAAAAAAAAAAAAAA")
        self.assertEqual(e["version"], 2)
        self.assertEqual(e["item_url"], "https://x/blyg/items/AAAAAAAAAAAAAAAAAAAAAAAAAA.json")

    def test_unparseable_feed_returns_empty(self):
        self.assertEqual(parse_feed(b"not xml"), [])
