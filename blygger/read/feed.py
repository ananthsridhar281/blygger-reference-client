"""Parse a blyg RSS feed into trigger entries (spec 7, 13.2)."""
from xml.etree import ElementTree as ET

_NS = "{https://blygger.org/ns/0.1}"


def parse_feed(body: bytes):
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    entries = []
    for item in root.iter("item"):
        try:
            iid = item.findtext(f"{_NS}id")
            version = item.findtext(f"{_NS}version")
            item_url = item.findtext(f"{_NS}item")
            if not iid or version is None:
                continue
            entries.append({
                "id": iid, "version": int(version),
                "kind": item.findtext(f"{_NS}kind"),
                "item_url": item_url,
            })
        except (ValueError, TypeError):
            continue  # skip malformed entry only
    return entries
