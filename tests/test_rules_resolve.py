# tests/test_rules_resolve.py
import json, unittest
from blygger.core import rules

MANIFEST = json.dumps({"blyg": "0.3", "site": "https://x.example/blyg/"}).encode()
FEED_WITH_MANIFEST = (b'<?xml version="1.0"?><rss xmlns:blyg="https://blygger.org/ns/0.1">'
                      b'<channel><blyg:manifest>https://x.example/blyg/blyg.json'
                      b'</blyg:manifest></channel></rss>')
HTML_REL = b'<html><head><link rel="blyg" href="https://x.example/blyg/"></head></html>'
PLAIN_RSS = b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>'

def make_fetch(table):
    calls = []
    def fetch(url):
        calls.append(url)
        status, body, final = table.get(url, (404, b"", url))
        return rules.FetchResult(status=status, body=body, final_url=final)
    fetch.calls = calls
    return fetch

class TestResolve(unittest.TestCase):
    def test_direct_probe(self):
        fetch = make_fetch({"https://x.example/blyg/blyg.json":
                            (200, MANIFEST, "https://x.example/blyg/blyg.json")})
        r = rules.resolve("https://x.example/blyg/", fetch)
        self.assertEqual(r.kind, "blyg")
        self.assertEqual(r.origin, "https://x.example/blyg/")

    def test_identity_is_final_fetch_origin_after_redirect(self):
        fetch = make_fetch({"https://x.example/blyg/blyg.json":
                            (200, MANIFEST, "https://new.example/blyg/blyg.json")})
        r = rules.resolve("https://x.example/blyg/", fetch)
        self.assertEqual(r.origin, "https://new.example/blyg/")

    def test_feed_upgrade(self):
        fetch = make_fetch({
            "https://x.example/feed.xml/blyg.json": (404, b"", "x"),
            "https://x.example/feed.xml": (200, FEED_WITH_MANIFEST, "https://x.example/feed.xml"),
            "https://x.example/blyg/blyg.json": (200, MANIFEST, "https://x.example/blyg/blyg.json"),
        })
        r = rules.resolve("https://x.example/feed.xml", fetch)
        self.assertEqual(r.kind, "blyg")

    def test_rel_probe_one_hop(self):
        fetch = make_fetch({
            "https://x.example/post/blyg.json": (404, b"", "x"),
            "https://x.example/post/": (200, HTML_REL, "https://x.example/post/"),
            "https://x.example/blyg/blyg.json": (200, MANIFEST, "https://x.example/blyg/blyg.json"),
        })
        r = rules.resolve("https://x.example/post/", fetch)
        self.assertEqual(r.kind, "blyg")

    def test_rss_fallback_is_l0(self):
        fetch = make_fetch({
            "https://x.example/feed.xml/blyg.json": (404, b"", "x"),
            "https://x.example/feed.xml": (200, PLAIN_RSS, "https://x.example/feed.xml"),
        })
        r = rules.resolve("https://x.example/feed.xml", fetch)
        self.assertEqual(r.kind, "l0")

    def test_failure_when_nothing_found(self):
        fetch = make_fetch({})
        r = rules.resolve("https://x.example/nope/", fetch)
        self.assertEqual(r.kind, "fail")

    def test_bounded_to_six_fetches(self):
        fetch = make_fetch({})
        rules.resolve("https://x.example/nope/", fetch)
        self.assertLessEqual(len(fetch.calls), 6)
