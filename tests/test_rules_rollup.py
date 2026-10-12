# tests/test_rules_rollup.py
import unittest
from blygger.core import rules
from blygger.core.model import Item

def _item(version, kind="fragment", updated="2026-01-01T00:00:00Z", chash="sha256:a"):
    return Item(blyg="0.3", id="7" * 26, kind=kind, origin="https://x/blyg/", author=None,
                created="c", updated=updated, version=version, content_md="m",
                content_html="<p>m</p>", content_hash=chash, media=[], changelog=[])

class TestRollup(unittest.TestCase):
    def test_higher_version_wins(self):
        r = rules.rollup(_item(2), _item(3))
        self.assertEqual(r.item.version, 3)
        self.assertFalse(r.withdrawn)

    def test_tie_broken_by_updated(self):
        older = _item(3, updated="2026-01-01T00:00:00Z")
        newer = _item(3, updated="2026-02-01T00:00:00Z")
        self.assertEqual(rules.rollup(older, newer).item.updated, "2026-02-01T00:00:00Z")

    def test_none_local_adopts_fetched(self):
        self.assertEqual(rules.rollup(None, _item(1)).item.version, 1)

    def test_withdrawn_rolls_to_null(self):
        r = rules.rollup(_item(3), _item(4, kind="withdrawn"))
        self.assertIsNone(r.item)
        self.assertTrue(r.withdrawn)

class TestWatermark(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(rules.watermark_check(2, "sha256:a", _item(3)), rules.OK)

    def test_regression(self):
        self.assertEqual(rules.watermark_check(5, "sha256:a", _item(3)), rules.REGRESSION)

    def test_stealth_edit(self):
        self.assertEqual(rules.watermark_check(3, "sha256:a", _item(3, chash="sha256:b")),
                         rules.STEALTH_EDIT)

    def test_same_version_same_hash_is_ok(self):
        self.assertEqual(rules.watermark_check(3, "sha256:a", _item(3, chash="sha256:a")),
                         rules.OK)
