"""ISO-8601 UTC for protocol fields; RFC-822 GMT for RSS pubDate/lastBuildDate (spec 4)."""
from datetime import datetime, timezone
from email.utils import formatdate


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def to_rfc822(dt: datetime) -> str:
    return formatdate(dt.astimezone(timezone.utc).timestamp(), usegmt=True)
