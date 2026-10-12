# tests/test_studio.py
import tempfile, unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from blygger.publish.store import Store
from blygger.publish.studio import Studio
from blygger.core.errors import PublishError

class Clock:
    def __init__(self):
        self.t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    def __call__(self):
        self.t += timedelta(minutes=1)
        return self.t

class TestStudio(unittest.TestCase):
    def setUp(self):
        self.store = Store(Path(tempfile.mkdtemp()))
        self.studio = Studio(self.store, origin="https://x/blyg/",
                             author={"name": "A"}, clock=Clock())

    def test_publish_fragment(self):
        fid = self.studio.publish_fragment("Hello *world*.")
        rec = self.store.get_item(fid)
        self.assertEqual(rec["authored_kind"], "fragment")
        v = rec["versions"][0]
        self.assertEqual(v["version"], 1)
        self.assertEqual(v["content_html"], "<p>Hello <em>world</em>.</p>")
        self.assertTrue(v["content_hash"].startswith("sha256:"))

    def test_edit_increments_version(self):
        fid = self.studio.publish_fragment("v1")
        self.studio.edit(fid, "v2", note="change")
        versions = self.store.get_item(fid)["versions"]
        self.assertEqual([v["version"] for v in versions], [1, 2])

    def test_withdraw_produces_empty_endcap(self):
        fid = self.studio.publish_fragment("bye soon")
        self.studio.withdraw(fid, note="done")
        last = self.store.get_item(fid)["versions"][-1]
        self.assertEqual(last["kind"], "withdrawn")
        self.assertEqual(last["content_md"], "")
        self.assertEqual(last["content_html"], "")
        self.assertEqual(last["media"], [])

    def test_publish_thread_transcludes_local_fragment(self):
        fid = self.studio.publish_fragment("quoted text")
        tid = self.studio.publish_thread(f"Intro\n\n![[{fid}]]\n\nEnd")
        rec = self.store.get_item(tid)
        v = rec["versions"][0]
        self.assertEqual(v["kind"], "thread")
        self.assertIn("blyg-transclusion", v["content_html"])
        self.assertEqual(v["transclusions"], [{"id": fid, "version": 1}])

    def test_thread_with_unknown_target_errors(self):
        with self.assertRaises(PublishError):
            self.studio.publish_thread("![[" + "0" * 26 + "]]")

    def test_pin_marks_version(self):
        fid = self.studio.publish_fragment("v1")
        self.studio.edit(fid, "v2")
        self.studio.pin(fid, 1)
        self.assertTrue(self.store.get_item(fid)["versions"][0]["pinned"])
