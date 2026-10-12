# tests/test_serialize.py
import unittest
from blygger.core import serialize
from blygger.core.model import (Author, ChangelogEntry, Item, Media, Manifest, IndexEntry)

def _fragment():
    return Item(
        blyg="0.3", id="7" * 26, kind="fragment", origin="https://x/blyg/",
        author=Author(name="A", url="https://x/blyg/"),
        created="2026-07-17T18:00:00Z", updated="2026-07-18T09:30:00Z", version=3,
        content_md="hi", content_html="<p>hi</p>", content_hash="sha256:ab",
        media=[Media(url="media/x.png", mime="image/png", alt="d")],
        changelog=[ChangelogEntry(version=1, at="2026-07-17T18:00:00Z"),
                   ChangelogEntry(version=2, at="2026-07-17T21:12:00Z", note="typo", pinned=True),
                   ChangelogEntry(version=3, at="2026-07-18T09:30:00Z", note="sharpened")],
        page="f/" + "7" * 26 + "/",
    )

class TestSerialize(unittest.TestCase):
    def test_fragment_public_dict_omits_transclusions(self):
        d = serialize.item_to_public_dict(_fragment())
        self.assertEqual(d["blyg"], "0.3")
        self.assertEqual(d["kind"], "fragment")
        self.assertNotIn("transclusions", d)
        self.assertEqual(d["media"][0]["mime"], "image/png")
        self.assertEqual(d["changelog"][1]["pinned"], True)
        self.assertEqual(d["page"], "f/" + "7" * 26 + "/")

    def test_item_roundtrip(self):
        d = serialize.item_to_public_dict(_fragment())
        back = serialize.parse_item(d)
        self.assertEqual(back.id, "7" * 26)
        self.assertEqual(back.content_hash, "sha256:ab")
        self.assertEqual(len(back.changelog), 3)
        self.assertEqual(back.media[0].alt, "d")

    def test_parse_tolerates_unknown_and_l2_members(self):
        d = serialize.item_to_public_dict(_fragment())
        d["mystery"] = {"a": 1}
        d["forked_from"] = {"origin": "https://y/", "id": "1" * 26, "version": 1}
        d["transclusions"] = [{"id": "1" * 26, "version": 1, "origin": "https://y/"}]
        back = serialize.parse_item(d)
        self.assertEqual(back.extra["mystery"], {"a": 1})
        self.assertEqual(back.forked_from["id"], "1" * 26)
        self.assertEqual(back.transclusions[0].origin, "https://y/")

    def test_manifest_roundtrip(self):
        m = Manifest(blyg="0.3", level=1, generator="blygger-ref/0.1", site="https://x/blyg/",
                     title="T", author=Author(name="A"), feed="feed.xml",
                     items="items/index.json", updated="2026-07-18T09:30:00Z",
                     blogroll="blogroll.opml")
        back = serialize.parse_manifest(serialize.manifest_to_dict(m))
        self.assertEqual(back.level, 1)
        self.assertEqual(back.blogroll, "blogroll.opml")
        self.assertIsNone(back.webmention)

    def test_index_roundtrip(self):
        entries = [IndexEntry(id="7" * 26, kind="fragment", created="c", updated="u", version=3)]
        d = serialize.index_to_dict("2026-07-18T09:30:00Z", entries)
        updated, parsed = serialize.parse_index(d)
        self.assertEqual(updated, "2026-07-18T09:30:00Z")
        self.assertEqual(parsed[0].version, 3)
