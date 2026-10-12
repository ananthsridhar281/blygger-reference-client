# blygger/publish/emit.py
"""Render the public static surface from the private store (spec 4,6,7,8)."""
import json
from pathlib import Path
from xml.sax.saxutils import escape as xesc
from ..core import timefmt
from ..core.errors import PublishError

_PAGE_PREFIX = {"fragment": "f", "thread": "t", "withdrawn": "f"}


def _page_for(authored_kind, item_id):
    return f"{_PAGE_PREFIX.get(authored_kind, 'f')}/{item_id}/"


def _latest(rec):
    return rec["versions"][-1]


def _public_item_dict(origin, item_id, rec, author):
    latest = _latest(rec)
    d = {
        "blyg": "0.3", "id": item_id, "kind": latest["kind"], "origin": origin,
        "page": _page_for(rec["authored_kind"], item_id), "author": author,
        "created": rec["created"], "updated": latest["at"], "version": latest["version"],
        "content_md": latest["content_md"], "content_html": latest["content_html"],
        "content_hash": latest["content_hash"], "media": latest.get("media", []),
        "changelog": [
            {"version": v["version"], "at": v["at"], "note": v.get("note"),
             **({"pinned": True} if v.get("pinned") else {})}
            for v in rec["versions"]
        ],
    }
    if rec["authored_kind"] == "thread":
        d["transclusions"] = latest.get("transclusions", []) if latest["kind"] != "withdrawn" else []
    return d


def _pin_dict(origin, item_id, rec, version_record, author):
    return {
        "blyg": "0.3", "id": item_id, "kind": version_record["kind"],
        "version": version_record["version"], "at": version_record["at"],
        "note": version_record.get("note"), "pinned": True, "origin": origin,
        "author": author, "content_md": version_record["content_md"],
        "content_html": version_record["content_html"],
        "content_hash": version_record["content_hash"],
    }


def _build_feed(origin, title, author_name, updated, entries, window=50):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<rss version="2.0" xmlns:blyg="https://blygger.org/ns/0.1" '
             'xmlns:dc="http://purl.org/dc/elements/1.1/">', "  <channel>",
             f"    <title>{xesc(title)}</title>", f"    <link>{xesc(origin)}</link>",
             "    <description></description>",
             f"    <lastBuildDate>{timefmt.to_rfc822(timefmt.parse_iso(updated))}</lastBuildDate>",
             "    <blyg:level>1</blyg:level>",
             f"    <blyg:manifest>{xesc(origin)}blyg.json</blyg:manifest>"]
    for e in entries[:window]:
        lines += [
            "    <item>",
            f'      <guid isPermaLink="false">blyg:{e["id"]}:v{e["version"]}</guid>',
            f'      <link>{xesc(origin)}{xesc(e["page"])}</link>',
            f"      <title>{xesc(e['title'])}</title>",
            f"      <description><![CDATA[{e['html']}]]></description>",
            f"      <pubDate>{timefmt.to_rfc822(timefmt.parse_iso(e['at']))}</pubDate>",
        ]
        if author_name:
            lines.append(f"      <dc:creator>{xesc(author_name)}</dc:creator>")
        lines += [
            f"      <blyg:id>{e['id']}</blyg:id>",
            f"      <blyg:kind>{e['kind']}</blyg:kind>",
            f"      <blyg:version>{e['version']}</blyg:version>",
            f"      <blyg:created>{e['created']}</blyg:created>",
            f"      <blyg:item>{xesc(origin)}items/{e['id']}.json</blyg:item>",
            "    </item>",
        ]
    lines += ["  </channel>", "</rss>", ""]
    return "\n".join(lines)


def _build_opml(title, entries):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<opml version="2.0">',
             f"  <head><title>{xesc(title)}</title></head>", "  <body>"]
    for e in entries:
        lines.append(f'    <outline type="rss" text="{xesc(e["text"])}" '
                     f'xmlUrl="{xesc(e["xmlUrl"])}" htmlUrl="{xesc(e["htmlUrl"])}" />')
    lines += ["  </body>", "</opml>", ""]
    return "\n".join(lines)


def emit(store, out_dir, origin, generator, updated):
    out = Path(out_dir)
    (out / "items").mkdir(parents=True, exist_ok=True)
    meta = store.get_manifest_meta()
    author = meta.get("author")
    author_name = (author or {}).get("name")

    item_ids = store.all_item_ids()
    records = {iid: store.get_item(iid) for iid in item_ids}
    records = {iid: r for iid, r in records.items() if r["versions"]}

    # --- item documents (latest only) + pins (additive, never delete) ---
    feed_rows = []
    index_rows = []
    for iid, rec in records.items():
        (out / "items").mkdir(exist_ok=True)
        pub = _public_item_dict(origin, iid, rec, author)
        (out / "items" / f"{iid}.json").write_text(
            json.dumps(pub, indent=2, sort_keys=True), "utf-8")
        index_rows.append({"id": iid, "kind": pub["kind"], "created": rec["created"],
                           "updated": pub["updated"], "version": pub["version"]})

        # pins: emit for each pinned version; refuse to delete a previously-emitted pin
        pin_dir = out / "items" / iid
        pinned_versions = {v["version"] for v in rec["versions"] if v.get("pinned")}
        if pin_dir.exists():
            for existing in pin_dir.glob("v*.json"):
                ver = int(existing.stem[1:])
                if ver not in pinned_versions:
                    raise PublishError(
                        f"emit would delete existing pin {iid} v{ver}; pins are irrevocable")
        for v in rec["versions"]:
            if v.get("pinned"):
                pin_dir.mkdir(exist_ok=True)
                (pin_dir / f"v{v['version']}.json").write_text(
                    json.dumps(_pin_dict(origin, iid, rec, v, author), indent=2, sort_keys=True),
                    "utf-8")

        # feed rows: latest content for every entry; withdrawn -> single endcap entry
        latest = _latest(rec)
        page = _page_for(rec["authored_kind"], iid)
        if latest["kind"] == "withdrawn":
            feed_rows.append({"id": iid, "version": latest["version"], "at": latest["at"],
                              "created": rec["created"], "kind": "withdrawn", "page": page,
                              "title": "withdrawn", "html": ""})
        else:
            for v in rec["versions"]:
                note = v.get("note")
                # single-line excerpt: collapse whitespace, drop lone transclusion directives
                words = " ".join(latest["content_md"].split())
                excerpt = words[:60]
                title = f"{note} — {excerpt}" if note else excerpt
                feed_rows.append({"id": iid, "version": v["version"], "at": v["at"],
                                  "created": rec["created"], "kind": latest["kind"],
                                  "page": page, "title": title, "html": latest["content_html"]})

    feed_rows.sort(key=lambda r: (r["at"], r["version"]), reverse=True)
    index_rows.sort(key=lambda r: r["updated"], reverse=True)

    # --- blogroll ---
    blogroll = store.get_blogroll()
    blogroll_key = None
    if blogroll:
        (out / "blogroll.opml").write_text(
            _build_opml(meta.get("title", ""), blogroll), "utf-8")
        blogroll_key = "blogroll.opml"

    # --- manifest ---
    manifest = {"blyg": "0.3", "level": 1, "generator": generator,
                "site": meta.get("site", origin), "title": meta.get("title", ""),
                "author": author, "feed": "feed.xml", "items": "items/index.json",
                "updated": updated}
    if blogroll_key:
        manifest["blogroll"] = blogroll_key
    (out / "blyg.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), "utf-8")

    # --- index + feed ---
    (out / "items" / "index.json").write_text(
        json.dumps({"updated": updated, "items": index_rows}, indent=2, sort_keys=True), "utf-8")
    (out / "feed.xml").write_text(
        _build_feed(origin, meta.get("title", ""), author_name, updated, feed_rows), "utf-8")
