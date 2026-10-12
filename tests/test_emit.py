# tests/test_emit.py
import json, tempfile, unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET
from blygger.publish.store import Store
from blygger.publish.studio import Studio
from blygger.publish.emit import emit
from blygger.core.errors import PublishError

NS = {"blyg": "https://blygger.org/ns/0.1"}

class Clock:
    def __init__(self):
        self.t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    def __call__(self):
        self.t += timedelta(minutes=1)
        return self.t

class TestEmit(unittest.TestCase):
    def setUp(self):
        self.private = Path(tempfile.mkdtemp())
        self.out = Path(tempfile.mkdtemp())
        self.store = Store(self.private)
        self.store.set_manifest_meta({"title": "T", "site": "https://x/blyg/",
                                      "author": {"name": "A"}})
        self.studio = Studio(self.store, origin="https://x/blyg/", author={"name": "A"},
                             clock=Clock())

    def _emit(self):
        emit(self.store, self.out, origin="https://x/blyg/",
             generator="blygger-ref/0.1", updated="2026-01-01T12:00:00Z")

    def test_manifest_and_item_and_index(self):
        fid = self.studio.publish_fragment("hello")
        self._emit()
        manifest = json.loads((self.out / "blyg.json").read_text())
        self.assertEqual(manifest["blyg"], "0.3")
        self.assertEqual(manifest["level"], 1)
        item = json.loads((self.out / "items" / f"{fid}.json").read_text())
        self.assertEqual(item["version"], 1)
        self.assertNotIn("transclusions", item)
        index = json.loads((self.out / "items" / "index.json").read_text())
        self.assertEqual(index["items"][0]["id"], fid)

    def test_feed_one_entry_per_event_newest_first(self):
        fid = self.studio.publish_fragment("v1")
        self.studio.edit(fid, "v2", note="change")
        self._emit()
        root = ET.fromstring((self.out / "feed.xml").read_text())
        guids = [g.text for g in root.findall(".//item/guid")]
        self.assertEqual(guids, [f"blyg:{fid}:v2", f"blyg:{fid}:v1"])
        # descriptions carry LATEST html even for the older entry
        descs = [d.text for d in root.findall(".//item/description")]
        self.assertTrue(all("v2" in d for d in descs))

    def test_withdrawn_single_entry(self):
        fid = self.studio.publish_fragment("hi")
        self.studio.withdraw(fid)
        self._emit()
        root = ET.fromstring((self.out / "feed.xml").read_text())
        items = root.findall(".//item")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].find("title").text, "withdrawn")

    def test_pinned_version_file_emitted(self):
        fid = self.studio.publish_fragment("v1")
        self.studio.edit(fid, "v2")
        self.studio.pin(fid, 1)
        self._emit()
        self.assertTrue((self.out / "items" / fid / "v1.json").exists())

    def test_emit_never_deletes_existing_pin(self):
        fid = self.studio.publish_fragment("v1")
        self.studio.pin(fid, 1)
        self._emit()
        # Simulate a store that forgot the pin, then re-emit: must error, not delete.
        rec = self.store.get_item(fid)
        rec["versions"][0]["pinned"] = False
        self.store._write(self.store._item_path(fid), rec)
        with self.assertRaises(PublishError):
            self._emit()

    def test_blogroll_emitted_when_present(self):
        self.studio.publish_fragment("hi")
        self.store.set_blogroll([{"text": "I", "xmlUrl": "https://i/feed", "htmlUrl": "https://i/"}])
        self._emit()
        self.assertTrue((self.out / "blogroll.opml").exists())
        manifest = json.loads((self.out / "blyg.json").read_text())
        self.assertEqual(manifest["blogroll"], "blogroll.opml")
