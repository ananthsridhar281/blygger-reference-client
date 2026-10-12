# blygger/core/rules.py
"""Pure spec rules: rollup, watermark, resolution (spec 12, 13). No I/O."""
from dataclasses import dataclass
from typing import Optional
from .model import Item

OK = "ok"
REGRESSION = "regression"
STEALTH_EDIT = "stealth_edit"


@dataclass(frozen=True)
class RollupResult:
    item: Optional[Item]
    withdrawn: bool


def rollup(local: Optional[Item], fetched: Item) -> RollupResult:
    if local is None:
        winner = fetched
    elif fetched.version > local.version:
        winner = fetched
    elif fetched.version == local.version and fetched.updated >= local.updated:
        winner = fetched
    else:
        winner = local
    if winner.kind == "withdrawn":
        return RollupResult(item=None, withdrawn=True)
    return RollupResult(item=winner, withdrawn=False)


def watermark_check(watermark: int, local_hash: Optional[str], fetched: Item) -> str:
    if fetched.version < watermark:
        return REGRESSION
    if fetched.version == watermark and local_hash is not None \
            and fetched.content_hash != local_hash:
        return STEALTH_EDIT
    return OK


# --- append to blygger/core/rules.py ---
import json as _json
import re as _re

_NS = "https://blygger.org/ns/0.1"
_MANIFEST_EL = _re.compile(rb"<blyg:manifest>\s*([^<\s]+)\s*</blyg:manifest>")
_REL_BLYG = _re.compile(rb'<link[^>]+rel=["\']blyg["\'][^>]*>', _re.I)
_HREF = _re.compile(rb'href=["\']([^"\']+)["\']', _re.I)


@dataclass(frozen=True)
class FetchResult:
    status: int
    body: bytes
    final_url: str


@dataclass(frozen=True)
class Resolution:
    kind: str                 # "blyg" | "l0" | "fail"
    origin: Optional[str] = None
    manifest_url: Optional[str] = None
    feed_url: Optional[str] = None
    trail: tuple = ()


def _normalize(url: str) -> str:
    url = url.split("#", 1)[0].split("?", 1)[0]
    m = _re.match(r"(https?://[^/]+)(/.*)?$", url)
    if m:
        host, path = m.group(1), m.group(2) or ""
        if path == "":
            return host + "/"                      # bare host -> add root slash
        last = path.rsplit("/", 1)[-1]
        if not path.endswith("/") and "." not in last:
            return url + "/"                        # directory-like path -> add slash
        return url                                  # file-like path (has a dot) -> leave
    return url if url.endswith("/") else url + "/"


def _origin_of(manifest_url: str) -> str:
    return manifest_url[: -len("blyg.json")] if manifest_url.endswith("blyg.json") else manifest_url


def _is_manifest(body: bytes) -> bool:
    try:
        obj = _json.loads(body.decode("utf-8"))
    except Exception:
        return False
    return isinstance(obj, dict) and "blyg" in obj


def _scheme_host(url: str) -> str:
    m = _re.match(r"(https?://[^/]+)", url)
    return m.group(1) if m else url


def resolve(url: str, fetch) -> Resolution:
    trail = []
    probed = set()
    budget = [6]

    def probe_manifest(candidate_manifest_url):
        if budget[0] <= 0 or candidate_manifest_url in probed:
            return None
        probed.add(candidate_manifest_url)
        budget[0] -= 1
        trail.append(candidate_manifest_url)
        res = fetch(candidate_manifest_url)
        if res.status == 200 and _is_manifest(res.body):
            return Resolution(kind="blyg", origin=_origin_of(res.final_url),
                              manifest_url=res.final_url, trail=tuple(trail))
        return None

    # Step 1-2: normalize + direct probe
    candidate = _normalize(url)
    hit = probe_manifest(candidate + "blyg.json")
    if hit:
        return hit

    # Step 3: fetch the input itself; feed upgrade or hold L0 candidate
    l0_feed = None
    if budget[0] > 0:
        budget[0] -= 1
        trail.append(url)
        res = fetch(url)
        body = res.body if res.status == 200 else b""
        if body:
            if b"<rss" in body or b"<feed" in body:
                m = _MANIFEST_EL.search(body)
                if m:
                    hit = probe_manifest(m.group(1).decode("utf-8"))
                    if hit:
                        return hit
                else:
                    l0_feed = res.final_url
            elif b"<html" in body.lower() or b"<link" in body.lower():
                # Step 4: rel="blyg" one hop
                tag = _REL_BLYG.search(body)
                if tag:
                    href = _HREF.search(tag.group(0))
                    if href:
                        base = _normalize(href.group(1).decode("utf-8"))
                        hit = probe_manifest(base + "blyg.json")
                        if hit:
                            return hit

    # Step 5: conventional mounts at scheme+host root
    root = _scheme_host(candidate)
    for mount in (root + "/blyg/blyg.json", root + "/blyg.json"):
        hit = probe_manifest(mount)
        if hit:
            return hit

    # Step 6: RSS fallback -> L0, else fail
    if l0_feed:
        return Resolution(kind="l0", feed_url=l0_feed, trail=tuple(trail))
    return Resolution(kind="fail", trail=tuple(trail))
