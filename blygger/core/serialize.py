# blygger/core/serialize.py
"""(De)serialization between models and wire JSON dicts (spec 5, 6, 13.1)."""
from .model import (Author, ChangelogEntry, Generated, IndexEntry, Item, Manifest,
                    Media, Transclusion)

_ITEM_KNOWN = {"blyg", "id", "kind", "origin", "author", "created", "updated", "version",
               "content_md", "content_html", "content_hash", "media", "changelog", "page",
               "transclusions", "generated", "forked_from", "stub_of"}
_MANIFEST_KNOWN = {"blyg", "level", "generator", "generator_url", "site", "title", "author",
                   "feed", "items", "blogroll", "webmention", "updated"}


# ---- authors ----
def _author_to_dict(a):
    if a is None:
        return None
    d = {}
    if a.name is not None:
        d["name"] = a.name
    if a.url is not None:
        d["url"] = a.url
    d.update(a.extra)
    return d


def _parse_author(d):
    if d is None:
        return None
    extra = {k: v for k, v in d.items() if k not in ("name", "url")}
    return Author(name=d.get("name"), url=d.get("url"), extra=extra)


# ---- items ----
def item_to_public_dict(item: Item) -> dict:
    d = {
        "blyg": item.blyg, "id": item.id, "kind": item.kind, "origin": item.origin,
        "author": _author_to_dict(item.author),
        "created": item.created, "updated": item.updated, "version": item.version,
        "content_md": item.content_md, "content_html": item.content_html,
        "content_hash": item.content_hash,
        "media": [{"url": m.url, "mime": m.mime, **({"alt": m.alt} if m.alt is not None else {})}
                  for m in item.media],
        "changelog": [
            {"version": c.version, "at": c.at, "note": c.note,
             **({"pinned": True} if c.pinned else {}),
             **({"generated": True} if c.generated else {})}
            for c in item.changelog
        ],
    }
    if item.page is not None:
        d["page"] = item.page
    if item.kind == "thread":
        d["transclusions"] = [
            {"id": t.id, "version": t.version} for t in (item.transclusions or [])
        ]
    return d


def _parse_transclusion(d):
    return Transclusion(id=d["id"], version=d["version"],
                        origin=d.get("origin"), selector=d.get("selector"))


def parse_item(d: dict) -> Item:
    media = [Media(url=m["url"], mime=m.get("mime", ""), alt=m.get("alt"))
             for m in d.get("media", [])]
    changelog = [ChangelogEntry(version=c["version"], at=c["at"], note=c.get("note"),
                                pinned=bool(c.get("pinned", False)),
                                generated=bool(c.get("generated", False)))
                 for c in d.get("changelog", [])]
    trans = d.get("transclusions")
    if trans is not None:
        trans = [_parse_transclusion(t) for t in trans]
    extra = {k: v for k, v in d.items() if k not in _ITEM_KNOWN}
    return Item(
        blyg=d.get("blyg", ""), id=d["id"], kind=d.get("kind", ""),
        origin=d.get("origin", ""), author=_parse_author(d.get("author")),
        created=d.get("created", ""), updated=d.get("updated", ""),
        version=int(d.get("version", 0)),
        content_md=d.get("content_md", ""), content_html=d.get("content_html", ""),
        content_hash=d.get("content_hash", ""), media=media, changelog=changelog,
        page=d.get("page"), transclusions=trans, generated=d.get("generated"),
        forked_from=d.get("forked_from"), stub_of=d.get("stub_of"), extra=extra,
    )


# ---- manifest ----
def manifest_to_dict(m: Manifest) -> dict:
    d = {"blyg": m.blyg, "level": m.level, "generator": m.generator, "site": m.site,
         "title": m.title, "author": _author_to_dict(m.author), "feed": m.feed,
         "items": m.items, "updated": m.updated}
    if m.generator_url is not None:
        d["generator_url"] = m.generator_url
    if m.blogroll is not None:
        d["blogroll"] = m.blogroll
    if m.webmention is not None:
        d["webmention"] = m.webmention
    return d


def parse_manifest(d: dict) -> Manifest:
    extra = {k: v for k, v in d.items() if k not in _MANIFEST_KNOWN}
    return Manifest(
        blyg=d.get("blyg", ""), level=int(d.get("level", 0)),
        generator=d.get("generator", ""), site=d.get("site", ""),
        title=d.get("title", ""), author=_parse_author(d.get("author")),
        feed=d.get("feed", "feed.xml"), items=d.get("items", "items/index.json"),
        updated=d.get("updated", ""), generator_url=d.get("generator_url"),
        blogroll=d.get("blogroll"), webmention=d.get("webmention"), extra=extra,
    )


# ---- index ----
def index_to_dict(updated: str, entries) -> dict:
    return {"updated": updated,
            "items": [{"id": e.id, "kind": e.kind, "created": e.created,
                       "updated": e.updated, "version": e.version} for e in entries]}


def parse_index(d: dict):
    entries = [IndexEntry(id=e["id"], kind=e.get("kind", ""), created=e.get("created", ""),
                          updated=e.get("updated", ""), version=int(e.get("version", 0)))
               for e in d.get("items", [])]
    return d.get("updated", ""), entries
