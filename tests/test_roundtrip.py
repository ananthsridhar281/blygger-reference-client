import tempfile, threading, unittest
from datetime import datetime, timezone, timedelta
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from blygger.publish.store import Store
from blygger.publish.studio import Studio
from blygger.publish.emit import emit
from blygger.transport.fs import FsTransport
from blygger.transport.http import HttpTransport
from blygger.read.archive import Archive
from blygger.read.resolve import resolve_subscription
from blygger.read.reconcile import Reconciler

class Clock:
    def __init__(self):
        self.t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    def __call__(self):
        self.t += timedelta(minutes=1)
        return self.t

def publish_history(out_dir, origin):
    store = Store(Path(tempfile.mkdtemp()))
    store.set_manifest_meta({"title": "T", "site": origin, "author": {"name": "A"}})
    studio = Studio(store, origin=origin, author={"name": "A"}, clock=Clock())
    f1 = studio.publish_fragment("first fragment")
    studio.edit(f1, "first fragment, sharpened", note="sharpen")
    f2 = studio.publish_fragment("second fragment")
    studio.pin(f2, 1)
    t1 = studio.publish_thread(f"Thread intro\n\n![[{f1}]]\n\nend")
    f3 = studio.publish_fragment("doomed")
    studio.withdraw(f3)
    emit(store, out_dir, origin=origin, generator="blygger-ref/0.1",
         updated="2026-01-01T12:00:00Z")
    return {"f1": f1, "f2": f2, "t1": t1, "f3": f3}

def run_reader(transport, url):
    archive = Archive(Path(tempfile.mkdtemp()))
    sub = resolve_subscription(transport, url)
    assert sub.kind == "blyg", sub
    Reconciler(transport, archive).reconcile(sub)
    return archive, sub.origin

class TestRoundTripFs(unittest.TestCase):
    def test_reader_state_equals_publisher_truth(self):
        out = Path(tempfile.mkdtemp())
        origin = "https://pub.example/blyg/"
        ids = publish_history(out, origin)
        transport = FsTransport(origin, out)
        archive, resolved_origin = run_reader(transport, origin)

        # live fragment rolled to latest version
        self.assertEqual(archive.get(resolved_origin, ids["f1"])["version"], 2)
        # pinned fragment present at v1
        self.assertEqual(archive.get(resolved_origin, ids["f2"])["version"], 1)
        # thread present and carries baked transclusion html
        self.assertEqual(archive.get(resolved_origin, ids["t1"])["kind"], "thread")
        self.assertIn("blyg-transclusion", archive.get(resolved_origin, ids["t1"])["content_html"])
        # withdrawn item rolled to null, watermark retained
        self.assertIsNone(archive.get(resolved_origin, ids["f3"]))
        self.assertEqual(archive.watermark(resolved_origin, ids["f3"]), 2)

class TestRoundTripHttp(unittest.TestCase):
    def test_reader_over_real_http(self):
        # Serve a root dir; the blyg lives under /blyg/ so resolution finds it.
        served = Path(tempfile.mkdtemp())
        handler = partial(SimpleHTTPRequestHandler, directory=str(served))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = server.server_address[1]
        origin = f"http://127.0.0.1:{port}/blyg/"
        ids = publish_history(served / "blyg", origin)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            transport = HttpTransport(generator="blygger-ref/0.1")
            archive, resolved_origin = run_reader(transport, origin)
            self.assertEqual(archive.get(resolved_origin, ids["f1"])["version"], 2)
            self.assertIsNone(archive.get(resolved_origin, ids["f3"]))
        finally:
            server.shutdown()
