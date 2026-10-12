# blygger/core/model.py
"""Frozen dataclasses mirroring the wire vocabulary (spec 5, 6). L2 fields are
parsed/carried but never emitted at L1."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Author:
    name: Optional[str] = None
    url: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Media:
    url: str
    mime: str
    alt: Optional[str] = None


@dataclass(frozen=True)
class ChangelogEntry:
    version: int
    at: str
    note: Optional[str] = None
    pinned: bool = False
    generated: bool = False


@dataclass(frozen=True)
class Transclusion:
    id: str
    version: int
    origin: Optional[str] = None       # L2: None means own-origin
    selector: Optional[dict] = None    # L2: partial-transclusion text-quote


@dataclass(frozen=True)
class Generated:
    sources: list = field(default_factory=list)
    model: Optional[str] = None
    at: Optional[str] = None


@dataclass(frozen=True)
class Item:
    blyg: str
    id: str
    kind: str                           # fragment | thread | withdrawn
    origin: str
    author: Optional[Author]
    created: str
    updated: str
    version: int
    content_md: str
    content_html: str
    content_hash: str
    media: list = field(default_factory=list)          # list[Media]
    changelog: list = field(default_factory=list)      # list[ChangelogEntry]
    page: Optional[str] = None
    transclusions: Optional[list] = None               # list[Transclusion] (threads only)
    generated: Optional[list] = None                   # L2, carried not emitted
    forked_from: Optional[dict] = None                 # L2, carried not emitted
    stub_of: Optional[dict] = None                     # L2, carried not emitted
    extra: dict = field(default_factory=dict)          # unknown members (spec 13.1)


@dataclass(frozen=True)
class Manifest:
    blyg: str
    level: int
    generator: str
    site: str
    title: str
    author: Optional[Author]
    feed: str
    items: str
    updated: str
    generator_url: Optional[str] = None
    blogroll: Optional[str] = None
    webmention: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class IndexEntry:
    id: str
    kind: str
    created: str
    updated: str
    version: int
