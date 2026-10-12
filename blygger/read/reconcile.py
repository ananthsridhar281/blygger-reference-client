"""Importer/reconciler: feed trigger + index diff -> rollup (spec 13)."""
import json
from dataclasses import dataclass, field
from ..core import rules, serialize
from ..core.errors import Discrepancy
from .feed import parse_feed


@dataclass
class ReconcileResult:
    fetched: int = 0
    discrepancies: list = field(default_factory=list)


class Reconciler:
    def __init__(self, transport, archive):
        self.transport = transport
        self.archive = archive

    def _state_from_item(self, item):
        return {"version": item.version, "content_hash": item.content_hash,
                "kind": item.kind, "updated": item.updated,
                "content_md": item.content_md, "content_html": item.content_html,
                "page": item.page}

    def _advance(self, origin, item, result):
        """Apply one fetched document to state under the §13.3 rules."""
        local_state = self.archive.get(origin, item.id)
        wm = self.archive.watermark(origin, item.id)
        local_hash = local_state["content_hash"] if local_state else None
        verdict = rules.watermark_check(wm, local_hash, item)
        if verdict == rules.REGRESSION:
            result.discrepancies.append(Discrepancy(
                type="regression", origin=origin, id=item.id,
                detail=f"fetched v{item.version} < watermark v{wm}"))
            return
        if verdict == rules.STEALTH_EDIT:
            result.discrepancies.append(Discrepancy(
                type="stealth_edit", origin=origin, id=item.id,
                detail=f"v{item.version} content_hash changed"))
        # hash self-consistency check (defect report, not a reject) — spec 13.3 SHOULD
        from ..core.hashing import content_hash
        if item.kind != "withdrawn" and content_hash(item.content_md) != item.content_hash:
            result.discrepancies.append(Discrepancy(
                type="hash_mismatch", origin=origin, id=item.id,
                detail="content_hash does not match content_md"))
        local_item = None
        if local_state:
            # reconstruct a minimal Item for rollup comparison
            from ..core.model import Item
            local_item = Item(blyg="", id=item.id, kind=local_state["kind"], origin=origin,
                              author=None, created="", updated=local_state["updated"],
                              version=local_state["version"], content_md="", content_html="",
                              content_hash=local_state["content_hash"], media=[], changelog=[])
        roll = rules.rollup(local_item, item)
        if roll.withdrawn:
            self.archive.roll_to_null(origin, item.id)
            self.archive.bump_watermark(origin, item.id, item.version)
        else:
            self.archive.put(origin, item.id, self._state_from_item(roll.item))

    def _fetch_item(self, url):
        r = self.transport.get(url)
        if r.status != 200:
            return None
        try:
            return serialize.parse_item(json.loads(r.body.decode("utf-8")))
        except (ValueError, KeyError):
            return None

    def reconcile(self, subscription) -> ReconcileResult:
        result = ReconcileResult()
        origin = subscription.origin

        # 1. Feed trigger (lossy): fetch each triggered item document.
        feed_resp = self.transport.get(subscription.feed_url)
        triggered = parse_feed(feed_resp.body) if feed_resp.status == 200 else []
        for entry in triggered:
            if entry.get("item_url"):
                item = self._fetch_item(entry["item_url"])
                if item:
                    self._advance(origin, item, result)
                    result.fetched += 1

        # 2. Index diff (total reconciliation): recover anything the feed missed.
        index_url = origin + subscription.manifest.items
        idx_resp = self.transport.get(index_url)
        if idx_resp.status == 200:
            try:
                _, entries = serialize.parse_index(json.loads(idx_resp.body.decode("utf-8")))
            except (ValueError, KeyError):
                entries = []
            for e in entries:
                local = self.archive.get(origin, e.id)
                wm = self.archive.watermark(origin, e.id)
                if local is None and wm >= e.version:
                    continue  # already withdrawn/seen at >= this version
                if local is not None and local["version"] >= e.version:
                    continue  # already current
                item = self._fetch_item(f"{origin}items/{e.id}.json")
                if item:
                    self._advance(origin, item, result)
                    result.fetched += 1
        return result
