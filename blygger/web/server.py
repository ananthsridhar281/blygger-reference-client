"""Localhost web server for the Blygger reader + studio UI. Thin controller over
the library: studio drives Studio/emit, reader drives resolve_subscription +
Reconciler. Pure-stdlib (http.server). Single-user, localhost only."""
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from ..core import timefmt
from ..core.errors import PublishError
from ..publish.store import Store
from ..publish.studio import Studio
from ..publish.emit import emit as emit_surface
from ..read.archive import Archive
from ..read.reconcile import Reconciler
from ..read.resolve import resolve_subscription
from ..transport.fs import FsTransport
from ..transport.http import HttpTransport
from . import views

GENERATOR = "blygger-ref/0.1"


@dataclass
class WebConfig:
    store_dir: Path
    site_dir: Path
    origin: str
    archive_dir: Path
    site_emitted: bool = False


def _now_iso() -> str:
    return timefmt.to_iso(datetime.now(timezone.utc))


# ------------------------------------------------------------- data helpers ----
def collect_items(store: Store):
    """Store records -> plain dicts for studio_view, newest first."""
    out = []
    for iid in store.all_item_ids():
        rec = store.get_item(iid)
        if not rec["versions"]:
            continue
        latest = rec["versions"][-1]
        out.append({
            "id": iid,
            "authored_kind": rec["authored_kind"],
            "version": latest["version"],
            "kind": latest["kind"],
            "note": latest.get("note"),
            "pinned_versions": [v["version"] for v in rec["versions"] if v.get("pinned")],
            "withdrawn": latest["kind"] == "withdrawn",
            "md_snippet": " ".join((latest.get("content_md") or "").split())[:80],
            "at": latest["at"],
        })
    out.sort(key=lambda d: d["at"], reverse=True)
    return out


def fragment_ids(store: Store):
    ids = []
    for iid in store.all_item_ids():
        rec = store.get_item(iid)
        if rec["versions"] and rec["authored_kind"] == "fragment" \
                and rec["versions"][-1]["kind"] != "withdrawn":
            ids.append(iid)
    return ids


def read_blyg(config: WebConfig, src: str, url: str):
    """Resolve + reconcile, returning a dict for reader_view."""
    if src == "local":
        transport = FsTransport(config.origin, config.site_dir)
        target = config.origin
    else:
        transport = HttpTransport(generator=GENERATOR)
        target = (url or "").strip()
    if not target:
        return {"error": "no URL given", "target": ""}
    sub = resolve_subscription(transport, target)
    if sub.kind != "blyg":
        return {"error": f"could not resolve as a blyg (result: {sub.kind})", "target": target}
    archive = Archive(config.archive_dir)
    result = Reconciler(transport, archive).reconcile(sub)
    items = []
    for iid in archive.known_ids(sub.origin):
        st = archive.get(sub.origin, iid)
        if st is None:
            items.append({"id": iid, "withdrawn": True,
                          "version": archive.watermark(sub.origin, iid),
                          "kind": "withdrawn", "content_html": "",
                          "author_name": None, "updated": ""})
        else:
            items.append({"id": iid, "withdrawn": False, "version": st["version"],
                          "kind": st["kind"], "content_html": st.get("content_html", ""),
                          "author_name": None, "updated": st.get("updated") or ""})
    items.sort(key=lambda d: d["updated"], reverse=True)
    return {
        "origin": sub.origin, "title": sub.manifest.title,
        "site_mismatch": sub.site_mismatch, "fetched": result.fetched,
        "discrepancies": [(d.type, d.id, d.detail) for d in result.discrepancies],
        "items": items,
    }


# ----------------------------------------------------------------- handler ----
class Handler(BaseHTTPRequestHandler):
    server_version = "blygger-web"

    @property
    def config(self) -> WebConfig:
        return self.server.config

    def log_message(self, *args):  # keep the console quiet
        pass

    # -- response helpers --
    def _html(self, body: str, status=200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location: str):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def _form(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        return {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}

    def _flash_param(self):
        q = parse_qs(urlsplit(self.path).query)
        return q.get("flash", [None])[0]

    # -- GET --
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/":
            return self._redirect("/studio")
        if path == "/studio":
            store = Store(self.config.store_dir)
            body = views.studio_view(collect_items(store), self.config.origin,
                                     fragment_ids(store), self.config.site_emitted,
                                     flash=self._flash_param())
            return self._html(views.render_page("Blygger · Studio", "studio", body))
        if path == "/reader":
            q = parse_qs(urlsplit(self.path).query)
            src = q.get("src", [None])[0]
            url = q.get("url", [""])[0]
            result = read_blyg(self.config, src, url) if src else None
            body = views.reader_view(url, result)
            return self._html(views.render_page("Blygger · Reader", "reader", body))
        return self._html("<h2>Not found</h2>", status=404)

    # -- POST (studio mutations; PRG pattern) --
    def do_POST(self):
        path = urlsplit(self.path).path
        store = Store(self.config.store_dir)
        studio = Studio(store, origin=self.config.origin)
        form = self._form()
        try:
            if path == "/studio/publish-fragment":
                studio.publish_fragment(form.get("text", ""))
                return self._redirect("/studio?flash=fragment+published")
            if path == "/studio/publish-thread":
                studio.publish_thread(form.get("text", ""))
                return self._redirect("/studio?flash=thread+published")
            if path == "/studio/pin":
                studio.pin(form["id"], int(form["version"]))
                return self._redirect("/studio?flash=pinned")
            if path == "/studio/withdraw":
                studio.withdraw(form["id"])
                return self._redirect("/studio?flash=withdrawn")
            if path == "/studio/emit":
                emit_surface(store, self.config.site_dir, origin=self.config.origin,
                             generator=GENERATOR, updated=_now_iso())
                self.config.site_emitted = True
                return self._redirect("/studio?flash=site+published")
        except PublishError as e:
            return self._redirect(f"/studio?flash=error:+{e}".replace(" ", "+"))
        return self._html("<h2>Not found</h2>", status=404)


class _Server(ThreadingHTTPServer):
    def __init__(self, addr, config: WebConfig):
        super().__init__(addr, Handler)
        self.config = config


def make_server(config: WebConfig, host="127.0.0.1", port=8000) -> _Server:
    config.store_dir = Path(config.store_dir)
    config.site_dir = Path(config.site_dir)
    config.archive_dir = Path(config.archive_dir)
    config.store_dir.mkdir(parents=True, exist_ok=True)
    config.site_dir.mkdir(parents=True, exist_ok=True)
    config.archive_dir.mkdir(parents=True, exist_ok=True)
    return _Server((host, port), config)


def serve(config: WebConfig, host="127.0.0.1", port=8000) -> int:
    server = make_server(config, host, port)
    h, p = server.server_address
    print(f"Blygger web UI at http://{h}:{p}/  (Ctrl-C to stop)")
    print(f"  store:   {config.store_dir}")
    print(f"  site:    {config.site_dir}")
    print(f"  origin:  {config.origin}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0
