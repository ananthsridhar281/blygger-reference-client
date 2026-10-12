"""Wire a Transport into the pure resolution ladder (spec 12)."""
import json
from dataclasses import dataclass
from typing import Optional
from ..core import rules, serialize
from ..core.model import Manifest


@dataclass(frozen=True)
class Subscription:
    kind: str                       # "blyg" | "l0" | "fail"
    origin: Optional[str] = None
    manifest: Optional[Manifest] = None
    feed_url: Optional[str] = None
    site_mismatch: bool = False


def resolve_subscription(transport, url: str) -> Subscription:
    def fetch(u):
        r = transport.get(u)
        return rules.FetchResult(status=r.status, body=r.body, final_url=r.final_url)

    res = rules.resolve(url, fetch)
    if res.kind == "blyg":
        mr = transport.get(res.manifest_url)
        manifest = serialize.parse_manifest(json.loads(mr.body.decode("utf-8")))
        mismatch = bool(manifest.site) and manifest.site != res.origin
        return Subscription(kind="blyg", origin=res.origin, manifest=manifest,
                            feed_url=res.origin + manifest.feed, site_mismatch=mismatch)
    if res.kind == "l0":
        return Subscription(kind="l0", feed_url=res.feed_url)
    return Subscription(kind="fail")
