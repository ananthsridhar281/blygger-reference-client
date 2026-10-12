import tempfile, unittest
from pathlib import Path
from blygger.transport.fs import FsTransport

class TestFsTransport(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "blyg.json").write_text('{"blyg": "0.3"}', "utf-8")
        self.t = FsTransport("https://x.example/blyg/", self.root)

    def test_get_existing_file(self):
        r = self.t.get("https://x.example/blyg/blyg.json")
        self.assertEqual(r.status, 200)
        self.assertIn(b'"blyg"', r.body)
        self.assertEqual(r.final_url, "https://x.example/blyg/blyg.json")

    def test_missing_file_404(self):
        self.assertEqual(self.t.get("https://x.example/blyg/missing.json").status, 404)

    def test_conditional_request_304(self):
        r1 = self.t.get("https://x.example/blyg/blyg.json")
        etag = r1.headers["ETag"]
        r2 = self.t.get("https://x.example/blyg/blyg.json", etag=etag)
        self.assertEqual(r2.status, 304)
