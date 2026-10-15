import tempfile, threading, unittest, urllib.request, urllib.parse
from pathlib import Path
from blygger.web.server import WebConfig, make_server


class TestWebServer(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        self.config = WebConfig(store_dir=d / "store", site_dir=d / "site",
                                origin="https://demo.example/blyg/", archive_dir=d / "arch")
        self.server = make_server(self.config, port=0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def _get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
            return r.status, r.read().decode("utf-8")

    def _post(self, path, data):
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}",
                                     data=body, method="POST")
        with urllib.request.urlopen(req) as r:   # follows the 303 to /studio
            return r.status, r.read().decode("utf-8")

    def test_root_redirects_to_studio(self):
        _, body = self._get("/")
        self.assertIn("Studio", body)

    def test_publish_fragment_then_studio_lists_it(self):
        self._post("/studio/publish-fragment", {"text": "Hello from the web UI."})
        status, body = self._get("/studio")
        self.assertEqual(status, 200)
        self.assertIn("Hello from the web UI.", body)

    def test_emit_then_read_local_renders_content_in_sandbox(self):
        self._post("/studio/publish-fragment", {"text": "Rendered in a sandbox."})
        self._post("/studio/emit", {})
        status, body = self._get("/reader?src=local")
        self.assertEqual(status, 200)
        self.assertIn('sandbox srcdoc=', body)
        self.assertIn("Rendered in a sandbox.", body)

    def test_publish_thread_transcluding_fragment(self):
        self._post("/studio/publish-fragment", {"text": "quoted bit"})
        # grab the fragment id from the studio listing
        _, studio = self._get("/studio")
        import re
        fid = re.search(r"[0-9a-z]{26}", studio).group(0)
        self._post("/studio/publish-thread", {"text": f"Intro\n\n![[{fid}]]\n\nEnd"})
        self._post("/studio/emit", {})
        _, body = self._get("/reader?src=local")
        self.assertIn("blyg-transclusion", body)   # baked transclusion reached the reader
