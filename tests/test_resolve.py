import json, tempfile, unittest
from pathlib import Path
from blygger.transport.fs import FsTransport
from blygger.read.resolve import resolve_subscription

class TestResolveSubscription(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "blyg.json").write_text(json.dumps(
            {"blyg": "0.3", "site": "https://x.example/blyg/", "title": "T",
             "feed": "feed.xml", "items": "items/index.json"}), "utf-8")
        self.t = FsTransport("https://x.example/blyg/", self.root)

    def test_direct_resolution(self):
        sub = resolve_subscription(self.t, "https://x.example/blyg/")
        self.assertEqual(sub.kind, "blyg")
        self.assertEqual(sub.origin, "https://x.example/blyg/")
        self.assertEqual(sub.manifest.title, "T")

    def test_site_mismatch_surfaced_but_not_adopted(self):
        (self.root / "blyg.json").write_text(json.dumps(
            {"blyg": "0.3", "site": "https://LYING.example/blyg/", "title": "T",
             "feed": "feed.xml", "items": "items/index.json"}), "utf-8")
        sub = resolve_subscription(self.t, "https://x.example/blyg/")
        self.assertEqual(sub.origin, "https://x.example/blyg/")   # fetch origin wins
        self.assertTrue(sub.site_mismatch)
