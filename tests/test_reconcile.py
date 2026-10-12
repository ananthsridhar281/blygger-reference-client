import json, tempfile, unittest
from pathlib import Path
from blygger.transport.fs import FsTransport
from blygger.read.archive import Archive
from blygger.read.resolve import resolve_subscription
from blygger.read.reconcile import Reconciler
from blygger.core.hashing import content_hash

def _write_blyg(root, items, feed_entries, index_entries):
    (root / "items").mkdir(parents=True, exist_ok=True)
    (root / "blyg.json").write_text(json.dumps(
        {"blyg": "0.3", "site": "https://x/blyg/", "title": "T",
         "feed": "feed.xml", "items": "items/index.json"}), "utf-8")
    for iid, doc in items.items():
        (root / "items" / f"{iid}.json").write_text(json.dumps(doc), "utf-8")
    (root / "items" / "index.json").write_text(json.dumps(
        {"updated": "2026-01-01T00:00:00Z", "items": index_entries}), "utf-8")
    item_xml = "".join(
        f"<item><blyg:id>{e['id']}</blyg:id><blyg:version>{e['version']}</blyg:version>"
        f"<blyg:item>https://x/blyg/items/{e['id']}.json</blyg:item></item>"
        for e in feed_entries)
    (root / "feed.xml").write_text(
        '<?xml version="1.0"?><rss xmlns:blyg="https://blygger.org/ns/0.1"><channel>'
        + item_xml + "</channel></rss>", "utf-8")

def _doc(iid, version, kind="fragment", md="hi"):
    # content_hash is a real hash of content_md so the reader's §13.3 self-consistency
    # check does not false-fire; stealth edits are simulated by changing md (hence hash).
    return {"blyg": "0.3", "id": iid, "kind": kind, "origin": "https://x/blyg/",
            "author": {"name": "A"}, "created": "2026-01-01T00:00:00Z",
            "updated": f"2026-01-0{version}T00:00:00Z", "version": version,
            "content_md": md, "content_html": f"<p>{md}</p>", "content_hash": content_hash(md),
            "media": [], "changelog": []}

A = "a" * 26

class TestReconcile(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.archive = Archive(Path(tempfile.mkdtemp()))

    def _reconciler(self):
        t = FsTransport("https://x/blyg/", self.root)
        sub = resolve_subscription(t, "https://x/blyg/")
        return Reconciler(t, self.archive), sub

    def test_feed_triggers_fetch_and_rollup(self):
        _write_blyg(self.root, {A: _doc(A, 1)},
                    [{"id": A, "version": 1}], [{"id": A, "kind": "fragment",
                     "created": "c", "updated": "u", "version": 1}])
        rec, sub = self._reconciler()
        result = rec.reconcile(sub)
        self.assertEqual(self.archive.get(sub.origin, A)["version"], 1)
        self.assertEqual(result.discrepancies, [])

    def test_index_backfill_when_feed_window_misses(self):
        # feed is empty, but index lists the item -> index diff recovers it
        _write_blyg(self.root, {A: _doc(A, 1)}, [],
                    [{"id": A, "kind": "fragment", "created": "c", "updated": "u", "version": 1}])
        rec, sub = self._reconciler()
        rec.reconcile(sub)
        self.assertEqual(self.archive.get(sub.origin, A)["version"], 1)

    def test_withdrawal_rolls_to_null(self):
        _write_blyg(self.root, {A: _doc(A, 2, kind="withdrawn", md="")},
                    [{"id": A, "version": 2}],
                    [{"id": A, "kind": "withdrawn", "created": "c", "updated": "u", "version": 2}])
        rec, sub = self._reconciler()
        rec.reconcile(sub)
        self.assertIsNone(self.archive.get(sub.origin, A))
        self.assertEqual(self.archive.watermark(sub.origin, A), 2)

    def test_version_regression_is_recorded_not_adopted(self):
        _write_blyg(self.root, {A: _doc(A, 5)}, [{"id": A, "version": 5}],
                    [{"id": A, "kind": "fragment", "created": "c", "updated": "u", "version": 5}])
        rec, sub = self._reconciler()
        rec.reconcile(sub)
        # now origin rewrites history to v3
        (self.root / "items" / f"{A}.json").write_text(json.dumps(_doc(A, 3)), "utf-8")
        (self.root / "feed.xml").write_text(
            '<?xml version="1.0"?><rss xmlns:blyg="https://blygger.org/ns/0.1"><channel>'
            f'<item><blyg:id>{A}</blyg:id><blyg:version>3</blyg:version>'
            f'<blyg:item>https://x/blyg/items/{A}.json</blyg:item></item>'
            '</channel></rss>', "utf-8")
        result = rec.reconcile(sub)
        self.assertEqual(self.archive.get(sub.origin, A)["version"], 5)   # not adopted
        self.assertTrue(any(d.type == "regression" for d in result.discrepancies))

    def test_stealth_edit_adopts_content_and_records(self):
        _write_blyg(self.root, {A: _doc(A, 1, md="hi")}, [{"id": A, "version": 1}],
                    [{"id": A, "kind": "fragment", "created": "c", "updated": "u", "version": 1}])
        rec, sub = self._reconciler()
        rec.reconcile(sub)
        # same version, different content -> different (real) hash == stealth edit
        (self.root / "items" / f"{A}.json").write_text(
            json.dumps(_doc(A, 1, md="changed")), "utf-8")
        result = rec.reconcile(sub)
        self.assertEqual(self.archive.get(sub.origin, A)["content_hash"], content_hash("changed"))
        self.assertTrue(any(d.type == "stealth_edit" for d in result.discrepancies))
