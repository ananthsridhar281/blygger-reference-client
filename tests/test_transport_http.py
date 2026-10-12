import tempfile, threading, unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from blygger.transport.http import HttpTransport

class TestHttpTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp())
        (cls.root / "blyg.json").write_text('{"blyg": "0.3"}', "utf-8")
        handler = partial(SimpleHTTPRequestHandler, directory=str(cls.root))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_get_200(self):
        t = HttpTransport(generator="blygger-ref/0.1")
        r = t.get(f"http://127.0.0.1:{self.port}/blyg.json")
        self.assertEqual(r.status, 200)
        self.assertIn(b'"blyg"', r.body)

    def test_get_404(self):
        t = HttpTransport(generator="blygger-ref/0.1")
        r = t.get(f"http://127.0.0.1:{self.port}/missing.json")
        self.assertEqual(r.status, 404)
