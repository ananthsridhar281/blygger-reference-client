# tests/test_store.py
import tempfile, unittest
from pathlib import Path
from blygger.publish.store import Store

class TestStore(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = Store(Path(self.dir))

    def test_create_and_get_item(self):
        self.store.create_item("7" * 26, "fragment", "2026-01-01T00:00:00Z")
        self.store.add_version("7" * 26, {"version": 1, "at": "2026-01-01T00:00:00Z",
                                          "kind": "fragment", "content_md": "hi",
                                          "content_html": "<p>hi</p>", "content_hash": "sha256:a",
                                          "media": [], "note": None})
        rec = self.store.get_item("7" * 26)
        self.assertEqual(rec["authored_kind"], "fragment")
        self.assertEqual(len(rec["versions"]), 1)

    def test_persists_across_instances(self):
        self.store.create_item("7" * 26, "fragment", "c")
        reopened = Store(Path(self.dir))
        self.assertIsNotNone(reopened.get_item("7" * 26))

    def test_set_pinned(self):
        self.store.create_item("7" * 26, "fragment", "c")
        self.store.add_version("7" * 26, {"version": 1, "at": "t", "kind": "fragment",
                                          "content_md": "m", "content_html": "<p>m</p>",
                                          "content_hash": "sha256:a", "media": [], "note": None})
        self.store.set_pinned("7" * 26, 1)
        self.assertTrue(self.store.get_item("7" * 26)["versions"][0]["pinned"])

    def test_all_items(self):
        self.store.create_item("7" * 26, "fragment", "c")
        self.store.create_item("1" * 26, "thread", "c")
        self.assertEqual(set(self.store.all_item_ids()), {"7" * 26, "1" * 26})
