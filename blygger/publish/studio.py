# blygger/publish/studio.py
"""High-level publish operations on the private store (spec 5-10)."""
from datetime import datetime, timezone
from ..core import ids, hashing, timefmt
from ..core.errors import PublishError
from ..core.transclude import bake


def _now_utc():
    return datetime.now(timezone.utc)


class Studio:
    def __init__(self, store, origin: str, author=None, clock=_now_utc):
        self.store = store
        self.origin = origin
        self.author = author
        self.clock = clock

    # ---- resolver used by thread baking: local published items only (spec 10.2) ----
    def _resolver(self, publishing_id):
        def resolve(target_id):
            if target_id == publishing_id:
                raise PublishError("thread cannot transclude itself")
            rec = self.store.get_item(target_id)
            if rec is None or not rec["versions"]:
                raise PublishError(f"unknown transclusion target {target_id}")
            latest = rec["versions"][-1]
            if latest["kind"] == "withdrawn":
                raise PublishError(f"target {target_id} is withdrawn")
            return latest["version"], latest["content_html"]
        return resolve

    def _append(self, item_id, kind, content_md, note, media=None, transclusions=None):
        rec = self.store.get_item(item_id)
        next_version = (rec["versions"][-1]["version"] + 1) if rec["versions"] else 1
        at = timefmt.to_iso(self.clock())
        record = {
            "version": next_version, "at": at, "kind": kind, "note": note,
            "content_md": content_md,
            "content_html": "" if kind == "withdrawn" else self._render(item_id, kind, content_md),
            "content_hash": hashing.content_hash(content_md),
            "media": media or [],
        }
        if kind == "withdrawn":
            record["content_html"] = ""
        if kind == "thread":
            record["transclusions"] = transclusions or []
        self.store.add_version(item_id, record)
        return next_version

    def _render(self, item_id, kind, content_md):
        if kind == "thread":
            html, _ = bake(content_md, self._resolver(item_id))
            return html
        from ..core.markdown import render
        return render(content_md)

    # ---- public operations ----
    def publish_fragment(self, content_md: str, media=None) -> str:
        item_id = ids.new_id()
        self.store.create_item(item_id, "fragment", timefmt.to_iso(self.clock()))
        self._append(item_id, "fragment", content_md, note=None, media=media)
        return item_id

    def publish_thread(self, content_md: str) -> str:
        item_id = ids.new_id()
        html, transclusions = bake(content_md, self._resolver(item_id))
        self.store.create_item(item_id, "thread", timefmt.to_iso(self.clock()))
        trans = [{"id": t.id, "version": t.version} for t in transclusions]
        rec = self.store.get_item(item_id)
        at = timefmt.to_iso(self.clock())
        self.store.add_version(item_id, {
            "version": 1, "at": at, "kind": "thread", "note": None,
            "content_md": content_md, "content_html": html,
            "content_hash": hashing.content_hash(content_md), "media": [],
            "transclusions": trans,
        })
        return item_id

    def edit(self, item_id: str, content_md: str, note=None, media=None) -> int:
        rec = self.store.get_item(item_id)
        if rec is None:
            raise PublishError(f"unknown item {item_id}")
        kind = rec["authored_kind"]
        transclusions = None
        if kind == "thread":
            _, ts = bake(content_md, self._resolver(item_id))
            transclusions = [{"id": t.id, "version": t.version} for t in ts]
        return self._append(item_id, kind, content_md, note, media, transclusions)

    def withdraw(self, item_id: str, note=None) -> int:
        rec = self.store.get_item(item_id)
        if rec is None:
            raise PublishError(f"unknown item {item_id}")
        return self._append(item_id, "withdrawn", "", note, media=[],
                            transclusions=[] if rec["authored_kind"] == "thread" else None)

    def pin(self, item_id: str, version: int) -> None:
        rec = self.store.get_item(item_id)
        if rec is None or not any(v["version"] == version for v in rec["versions"]):
            raise PublishError(f"cannot pin unknown version {item_id} v{version}")
        if any(v["version"] == version and v["kind"] == "withdrawn" for v in rec["versions"]):
            raise PublishError("withdrawal endcaps MUST NOT be pinned")
        self.store.set_pinned(item_id, version)
