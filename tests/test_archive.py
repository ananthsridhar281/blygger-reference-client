import tempfile, unittest
from pathlib import Path
from blygger.read.archive import Archive

class TestArchive(unittest.TestCase):
    def setUp(self):
        self.a = Archive(Path(tempfile.mkdtemp()))
        self.origin = "https://x/blyg/"

    def test_put_and_get(self):
        self.a.put(self.origin, "7" * 26, {"version": 1, "content_hash": "sha256:a"})
        rec = self.a.get(self.origin, "7" * 26)
        self.assertEqual(rec["version"], 1)
        self.assertEqual(self.a.watermark(self.origin, "7" * 26), 1)

    def test_watermark_is_monotonic(self):
        self.a.put(self.origin, "7" * 26, {"version": 3, "content_hash": "sha256:a"})
        self.a.put(self.origin, "7" * 26, {"version": 2, "content_hash": "sha256:a"})
        self.assertEqual(self.a.watermark(self.origin, "7" * 26), 3)

    def test_scoped_by_origin(self):
        self.a.put("https://a/", "7" * 26, {"version": 1, "content_hash": "x"})
        self.assertIsNone(self.a.get("https://b/", "7" * 26))

    def test_roll_to_null_keeps_watermark(self):
        self.a.put(self.origin, "7" * 26, {"version": 2, "content_hash": "x"})
        self.a.roll_to_null(self.origin, "7" * 26)
        self.assertIsNone(self.a.get(self.origin, "7" * 26))
        self.assertEqual(self.a.watermark(self.origin, "7" * 26), 2)

    def test_known_ids(self):
        self.a.put(self.origin, "7" * 26, {"version": 1, "content_hash": "x"})
        self.assertEqual(self.a.known_ids(self.origin), {"7" * 26})
