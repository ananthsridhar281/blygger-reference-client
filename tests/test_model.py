# tests/test_model.py
import unittest
from blygger.core.model import (
    Author, Media, ChangelogEntry, Transclusion, Generated, Item, Manifest, IndexEntry,
)

class TestModel(unittest.TestCase):
    def test_item_defaults_and_fields(self):
        item = Item(
            blyg="0.3", id="7" * 26, kind="fragment", origin="https://x/blyg/",
            author=Author(name="A"), created="2026-07-17T18:00:00Z",
            updated="2026-07-17T18:00:00Z", version=1,
            content_md="hi", content_html="<p>hi</p>", content_hash="sha256:...",
            media=[], changelog=[ChangelogEntry(version=1, at="2026-07-17T18:00:00Z")],
        )
        self.assertEqual(item.kind, "fragment")
        self.assertIsNone(item.transclusions)     # fragments omit the key
        self.assertIsNone(item.page)
        self.assertEqual(item.extra, {})

    def test_changelog_entry_defaults(self):
        c = ChangelogEntry(version=2, at="t", note="typo")
        self.assertFalse(c.pinned)
        self.assertFalse(c.generated)

    def test_transclusion_remote_optional_fields(self):
        t = Transclusion(id="1" * 26, version=1, origin="https://y/", selector={"exact": "q"})
        self.assertEqual(t.origin, "https://y/")
