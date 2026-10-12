# Blygger Reference Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure-stdlib Python round-trip reference client for the Blygger v0.3 protocol at conformance **L1 (single-origin) + blogroll, static**, where a publisher emits a static blyg and a reader resolves/subscribes/reconciles it, sharing only the protocol core.

**Architecture:** One `blygger` package in three layers that reach across only through a pure, I/O-free `core` (ids, hashing, models, markdown, transclusion baking, serialization, and the pure spec rules `rollup`/`watermark_check`/`resolve`). `publish/` holds a private all-versions store + studio ops + a static-surface emitter. `read/` holds resolution, an origin-scoped archive + watermark, and the reconciler. `transport/` abstracts fetching behind HTTP and filesystem backends. The round-trip test is the conformance oracle.

**Tech Stack:** Python 3.11+, standard library only (`json`, `hashlib`, `secrets`, `xml.etree.ElementTree`, `urllib`, `email.utils`, `http.server`, `unittest`, `dataclasses`, `datetime`, `re`, `pathlib`).

**Spec:** `docs/superpowers/specs/2026-10-11-blygger-reference-client-design.md` (Blygger 0.3, pinned to 2026-09-28 snapshot).

---

## File Structure

```
blygger/
  __init__.py
  core/
    __init__.py
    ids.py          # new_id(), is_valid_id(), ALPHABET
    hashing.py      # content_hash()
    timefmt.py      # to_iso/parse_iso/to_rfc822
    errors.py       # PublishError, Discrepancy
    model.py        # Author, Media, ChangelogEntry, Transclusion, Generated, Item, Manifest, IndexEntry
    markdown.py     # render() — minimal subset
    transclude.py   # bake()
    serialize.py    # item<->dict, manifest<->dict, index<->dict (tolerant parse)
    rules.py        # rollup(), watermark_check(), resolve(), result dataclasses
  publish/
    __init__.py
    store.py        # Store — private all-versions canonical store
    studio.py       # Studio — publish_fragment/publish_thread/edit/pin/withdraw
    emit.py         # emit() — render static surface (+ build_feed, build_opml)
  read/
    __init__.py
    archive.py      # Archive — origin-scoped state + watermark
    feed.py         # parse_feed()
    resolve.py      # resolve_subscription()
    reconcile.py    # Reconciler
    poll.py         # PollState — backoff/conditional-request policy
  transport/
    __init__.py
    base.py         # Transport ABC, Response
    fs.py           # FsTransport
    http.py         # HttpTransport
tests/
  __init__.py
  test_ids.py, test_hashing.py, test_timefmt.py, test_markdown.py,
  test_transclude.py, test_serialize.py, test_rules_rollup.py,
  test_rules_resolve.py, test_store.py, test_studio.py, test_emit.py,
  test_transport_fs.py, test_archive.py, test_reconcile.py,
  test_resolve.py, test_roundtrip.py
```

**Test convention:** all tests use `unittest`. Run a single test with
`python -m unittest tests.test_x -v`; run everything with `python -m unittest discover -s tests -v`.

---

# Phase 1 — Core + Publisher

## Task 0: Project scaffold

**Files:**
- Create: `blygger/__init__.py`, `blygger/core/__init__.py`, `blygger/publish/__init__.py`, `blygger/read/__init__.py`, `blygger/transport/__init__.py`, `tests/__init__.py`, `.gitignore`

- [ ] **Step 1: Create package files**

```bash
mkdir -p blygger/core blygger/publish blygger/read blygger/transport tests
touch blygger/__init__.py blygger/core/__init__.py blygger/publish/__init__.py \
      blygger/read/__init__.py blygger/transport/__init__.py tests/__init__.py
printf '__pycache__/\n*.pyc\n.venv/\nbuild/\n' > .gitignore
```

- [ ] **Step 2: Verify discovery works (no tests yet)**

Run: `python -m unittest discover -s tests -v`
Expected: `Ran 0 tests` and `OK`.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "chore: scaffold blygger package layout"
```

---

## Task 1: `core/ids.py` — item id generation & validation

**Files:**
- Create: `blygger/core/ids.py`
- Test: `tests/test_ids.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ids.py
import unittest
from blygger.core import ids

class TestIds(unittest.TestCase):
    def test_new_id_is_26_lowercase_crockford_chars(self):
        i = ids.new_id()
        self.assertEqual(len(i), 26)
        self.assertTrue(all(c in ids.ALPHABET for c in i))
        for bad in "ilou":
            self.assertNotIn(bad, ids.ALPHABET)

    def test_new_ids_are_unique(self):
        self.assertEqual(len({ids.new_id() for _ in range(1000)}), 1000)

    def test_is_valid_id(self):
        self.assertTrue(ids.is_valid_id(ids.new_id()))
        self.assertFalse(ids.is_valid_id("too-short"))
        self.assertFalse(ids.is_valid_id("A" * 26))          # uppercase
        self.assertFalse(ids.is_valid_id("i" * 26))          # excluded letter
        self.assertFalse(ids.is_valid_id("7c9wk2mhq0v3xj8tn5rzfd41b"))  # 25 chars

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_ids -v`
Expected: FAIL (`ModuleNotFoundError` / `AttributeError`).

- [ ] **Step 3: Write minimal implementation**

```python
# blygger/core/ids.py
"""Item identifiers: 128 random bits as 26 lowercase Crockford base32 chars (spec 5.1)."""
import secrets

ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"  # Crockford base32: no i, l, o, u
_ALPHASET = frozenset(ALPHABET)
_LEN = 26


def new_id() -> str:
    n = int.from_bytes(secrets.token_bytes(16), "big")  # 128 bits
    chars = []
    for _ in range(_LEN):
        chars.append(ALPHABET[n & 31])
        n >>= 5
    return "".join(reversed(chars))


def is_valid_id(value: object) -> bool:
    return isinstance(value, str) and len(value) == _LEN and all(c in _ALPHASET for c in value)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_ids -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/core/ids.py tests/test_ids.py
git commit -m "feat(core): item id generation and validation"
```

---

## Task 2: `core/hashing.py` — content hash

**Files:**
- Create: `blygger/core/hashing.py`
- Test: `tests/test_hashing.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hashing.py
import hashlib, unittest
from blygger.core.hashing import content_hash

class TestHashing(unittest.TestCase):
    def test_prefixed_sha256_of_utf8_markdown(self):
        md = "Markdown source of the *latest* version."
        expected = "sha256:" + hashlib.sha256(md.encode("utf-8")).hexdigest()
        self.assertEqual(content_hash(md), expected)

    def test_empty_string(self):
        self.assertEqual(
            content_hash(""),
            "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )

    def test_unicode_is_utf8_encoded(self):
        self.assertEqual(content_hash("café"),
                         "sha256:" + hashlib.sha256("café".encode("utf-8")).hexdigest())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_hashing -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

```python
# blygger/core/hashing.py
"""content_hash covers content_md only (spec 5.1)."""
import hashlib


def content_hash(content_md: str) -> str:
    return "sha256:" + hashlib.sha256(content_md.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_hashing -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/core/hashing.py tests/test_hashing.py
git commit -m "feat(core): content_hash"
```

---

## Task 3: `core/timefmt.py` — timestamp helpers

**Files:**
- Create: `blygger/core/timefmt.py`
- Test: `tests/test_timefmt.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_timefmt.py
import unittest
from datetime import datetime, timezone
from blygger.core import timefmt

class TestTimefmt(unittest.TestCase):
    def setUp(self):
        self.dt = datetime(2026, 7, 18, 9, 30, 0, tzinfo=timezone.utc)

    def test_to_iso(self):
        self.assertEqual(timefmt.to_iso(self.dt), "2026-07-18T09:30:00Z")

    def test_parse_iso_roundtrip(self):
        self.assertEqual(timefmt.parse_iso("2026-07-18T09:30:00Z"), self.dt)

    def test_to_rfc822_is_gmt(self):
        self.assertEqual(timefmt.to_rfc822(self.dt), "Sat, 18 Jul 2026 09:30:00 GMT")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_timefmt -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# blygger/core/timefmt.py
"""ISO-8601 UTC for protocol fields; RFC-822 GMT for RSS pubDate/lastBuildDate (spec 4)."""
from datetime import datetime, timezone
from email.utils import formatdate


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def to_rfc822(dt: datetime) -> str:
    return formatdate(dt.astimezone(timezone.utc).timestamp(), usegmt=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_timefmt -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/core/timefmt.py tests/test_timefmt.py
git commit -m "feat(core): ISO-8601 and RFC-822 timestamp helpers"
```

---

## Task 4: `core/errors.py` — error & discrepancy types

**Files:**
- Create: `blygger/core/errors.py`
- Test: `tests/test_errors.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_errors.py
import unittest
from blygger.core.errors import PublishError, Discrepancy

class TestErrors(unittest.TestCase):
    def test_publish_error_is_exception(self):
        with self.assertRaises(PublishError):
            raise PublishError("bad")

    def test_discrepancy_is_a_record(self):
        d = Discrepancy(type="stealth_edit", origin="https://x/", id="7" * 26, detail="hash")
        self.assertEqual(d.type, "stealth_edit")
        self.assertEqual(d.id, "7" * 26)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_errors -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# blygger/core/errors.py
"""Publish-side hard errors; read-side inspectable discrepancies (spec 8)."""
from dataclasses import dataclass


class PublishError(Exception):
    """Raised when a publish operation would produce a non-conformant surface."""


@dataclass(frozen=True)
class Discrepancy:
    type: str     # "regression" | "stealth_edit" | "hash_mismatch" | "malformed" | "site_mismatch"
    origin: str
    id: str
    detail: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_errors -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/core/errors.py tests/test_errors.py
git commit -m "feat(core): PublishError and Discrepancy types"
```

---

## Task 5: `core/model.py` — data model

**Files:**
- Create: `blygger/core/model.py`
- Test: `tests/test_model.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model.py
import unittest
from blygger.core.model import (
    Author, Media, ChangelogEntry, Transclusion, Generated, Item, Manifest, IndexEntry,
)

class TestModel(unittest.TestCase):
    def test_item_defaults_and_fields(self):
        item = Item(
            blyg="0.3", id="7" * 26, kind="fragment", origin="https://x/blyg/",
            author=Author(name="A"), created="2026-07-17T18:00:00Z",
            updated="2026-07-17T18:00:00Z", version=1,
            content_md="hi", content_html="<p>hi</p>", content_hash="sha256:...",
            media=[], changelog=[ChangelogEntry(version=1, at="2026-07-17T18:00:00Z")],
        )
        self.assertEqual(item.kind, "fragment")
        self.assertIsNone(item.transclusions)     # fragments omit the key
        self.assertIsNone(item.page)
        self.assertEqual(item.extra, {})

    def test_changelog_entry_defaults(self):
        c = ChangelogEntry(version=2, at="t", note="typo")
        self.assertFalse(c.pinned)
        self.assertFalse(c.generated)

    def test_transclusion_remote_optional_fields(self):
        t = Transclusion(id="1" * 26, version=1, origin="https://y/", selector={"exact": "q"})
        self.assertEqual(t.origin, "https://y/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_model -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_model -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/core/model.py tests/test_model.py
git commit -m "feat(core): data model dataclasses"
```

---

## Task 6: `core/markdown.py` — minimal markdown renderer

**Files:**
- Create: `blygger/core/markdown.py`
- Test: `tests/test_markdown.py`

Scope reminder (spec 2): paragraphs, emphasis (`*`/`_`), inline code, fenced code blocks,
blockquotes, links, images. Reference-grade, not CommonMark-complete. Transclusion
directives are NOT handled here (that is `transclude.py`); a lone `![[id]]` line passed to
`render()` is treated as an ordinary paragraph.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_markdown.py
import unittest
from blygger.core.markdown import render

class TestMarkdown(unittest.TestCase):
    def test_paragraph_and_emphasis(self):
        self.assertEqual(render("Markdown source of the *latest* version."),
                         "<p>Markdown source of the <em>latest</em> version.</p>")

    def test_underscore_emphasis(self):
        self.assertEqual(render("a _b_ c"), "<p>a <em>b</em> c</p>")

    def test_inline_code_is_escaped(self):
        self.assertEqual(render("use `a<b>`"), "<p>use <code>a&lt;b&gt;</code></p>")

    def test_link_and_image(self):
        self.assertEqual(render("[t](https://x)"), '<p><a href="https://x">t</a></p>')
        self.assertEqual(render("![alt](https://x/i.png)"),
                         '<p><img src="https://x/i.png" alt="alt"></p>')

    def test_blockquote(self):
        self.assertEqual(render("> quoted"), "<blockquote><p>quoted</p></blockquote>")

    def test_fenced_code_block_escapes(self):
        self.assertEqual(render("```\na < b\n```"), "<pre><code>a &lt; b\n</code></pre>")

    def test_two_paragraphs(self):
        self.assertEqual(render("one\n\ntwo"), "<p>one</p>\n<p>two</p>")

    def test_html_special_chars_escaped_in_text(self):
        self.assertEqual(render("a & b < c"), "<p>a &amp; b &lt; c</p>")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_markdown -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# blygger/core/markdown.py
"""Reference-grade minimal markdown subset -> HTML (spec 2). NOT CommonMark-complete."""
import re
from html import escape

_IMG = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_CODE = re.compile(r"`([^`]+)`")
_EM = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)|(?<!_)_([^_]+)_(?!_)")


def _inline(text: str) -> str:
    # Protect inline code spans first so their contents are escaped verbatim.
    spans = []

    def _stash_code(m):
        spans.append("<code>" + escape(m.group(1)) + "</code>")
        return f"\x00{len(spans) - 1}\x00"

    text = _CODE.sub(_stash_code, text)
    text = escape(text, quote=False)
    text = _IMG.sub(lambda m: f'<img src="{escape(m.group(2), quote=True)}" '
                              f'alt="{escape(m.group(1), quote=True)}">', text)
    text = _LINK.sub(lambda m: f'<a href="{escape(m.group(2), quote=True)}">'
                               f'{m.group(1)}</a>', text)
    text = _EM.sub(lambda m: f"<em>{m.group(1) or m.group(2)}</em>", text)
    text = re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], text)
    return text


def render(md: str) -> str:
    lines = md.split("\n")
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == "":
            i += 1
            continue
        if line.startswith("```"):
            i += 1
            code = []
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1  # consume closing fence
            body = "".join(l + "\n" for l in code)
            blocks.append("<pre><code>" + escape(body) + "</code></pre>")
            continue
        if line.startswith(">"):
            quoted = []
            while i < len(lines) and lines[i].startswith(">"):
                quoted.append(lines[i][1:].lstrip())
                i += 1
            inner = render("\n".join(quoted))
            blocks.append("<blockquote>" + inner + "</blockquote>")
            continue
        # paragraph: gather until blank line
        para = []
        while i < len(lines) and lines[i].strip() != "" and not lines[i].startswith("```") \
                and not lines[i].startswith(">"):
            para.append(lines[i])
            i += 1
        blocks.append("<p>" + _inline(" ".join(para)) + "</p>")
    return "\n".join(blocks)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_markdown -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/core/markdown.py tests/test_markdown.py
git commit -m "feat(core): minimal markdown renderer"
```

---

## Task 7: `core/transclude.py` — publish-time transclusion baking

**Files:**
- Create: `blygger/core/transclude.py`
- Test: `tests/test_transclude.py`

Spec 10.1–10.3: a line consisting solely of `![[id]]` (whitespace allowed) is a directive;
the reserved `![[id@vN]]` form MUST be rejected at publish; the directive bakes to
`<blockquote class="blyg-transclusion" data-blyg-id data-blyg-version>...</blockquote>`;
provenance is recorded in directive order. `resolver(id)` returns `(version, html)` or
raises `PublishError`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_transclude.py
import unittest
from blygger.core.transclude import bake
from blygger.core.errors import PublishError

FID = "7c9wk2mhq0v3xj8tn5rzfd41bg"

def resolver(id):
    if id == FID:
        return (3, "<p>quoted</p>")
    raise PublishError(f"unknown {id}")

class TestTransclude(unittest.TestCase):
    def test_directive_line_bakes_blockquote_and_provenance(self):
        html, trans = bake(f"Intro.\n\n![[{FID}]]\n\nOutro.", resolver)
        self.assertIn('<blockquote class="blyg-transclusion" '
                      f'data-blyg-id="{FID}" data-blyg-version="3"><p>quoted</p></blockquote>', html)
        self.assertIn("<p>Intro.</p>", html)
        self.assertIn("<p>Outro.</p>", html)
        self.assertEqual([(t.id, t.version) for t in trans], [(FID, 3)])

    def test_inline_directive_is_inert(self):
        html, trans = bake(f"see ![[{FID}]] here", resolver)
        self.assertEqual(trans, [])
        self.assertNotIn("blyg-transclusion", html)

    def test_reserved_version_form_rejected(self):
        with self.assertRaises(PublishError):
            bake(f"![[{FID}@v2]]", resolver)

    def test_unknown_target_is_publish_error(self):
        with self.assertRaises(PublishError):
            bake("![[" + "0" * 26 + "]]", resolver)

    def test_order_preserved(self):
        second = "1vgtgz0gq5b2c9k7d3m8r4n6xy"
        def r2(id):
            return {FID: (3, "<p>a</p>"), second: (1, "<p>b</p>")}[id]
        _, trans = bake(f"![[{FID}]]\n\n![[{second}]]", r2)
        self.assertEqual([t.id for t in trans], [FID, second])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_transclude -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# blygger/core/transclude.py
"""Publish-time transclusion resolution and HTML baking (spec 10)."""
import re
from .errors import PublishError
from .markdown import render
from .model import Transclusion

_DIRECTIVE = re.compile(r"^\s*!\[\[([0-9a-z]{26})\]\]\s*$")
_RESERVED = re.compile(r"^\s*!\[\[[0-9a-z]{26}@v\d+\]\]\s*$")


def bake(md: str, resolver):
    """Return (content_html, [Transclusion]) resolving own-origin directives in order."""
    lines = md.split("\n")
    out_blocks = []
    transclusions = []
    buffer = []

    def flush():
        if buffer:
            chunk = "\n".join(buffer).strip("\n")
            if chunk.strip():
                out_blocks.append(render(chunk))
            buffer.clear()

    for line in lines:
        if _RESERVED.match(line):
            raise PublishError("reserved version-qualified transclusion ![[id@vN]]")
        m = _DIRECTIVE.match(line)
        if m:
            flush()
            tid = m.group(1)
            version, html = resolver(tid)   # raises PublishError on bad target
            out_blocks.append(
                f'<blockquote class="blyg-transclusion" data-blyg-id="{tid}" '
                f'data-blyg-version="{version}">{html}</blockquote>'
            )
            transclusions.append(Transclusion(id=tid, version=version))
        else:
            buffer.append(line)
    flush()
    return "\n".join(out_blocks), transclusions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_transclude -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/core/transclude.py tests/test_transclude.py
git commit -m "feat(core): publish-time transclusion baking"
```

---

## Task 8: `core/serialize.py` — wire (de)serialization

**Files:**
- Create: `blygger/core/serialize.py`
- Test: `tests/test_serialize.py`

Spec 5–6, 13.1: `item_to_public_dict` emits only L1 keys (latest content; `transclusions`
only for threads; `page` when set; no L2 keys). `parse_item` is tolerant — unknown members
go to `extra`, known L2 members are parsed into their model slots.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_serialize -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_serialize -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/core/serialize.py tests/test_serialize.py
git commit -m "feat(core): wire serialization with tolerant parse"
```

---

## Task 9: `core/rules.py` (part A) — rollup & watermark

**Files:**
- Create: `blygger/core/rules.py`
- Test: `tests/test_rules_rollup.py`

Spec 13.1–13.3: highest `version` wins, ties by `updated`; `withdrawn` endcap rolls to
null; watermark is monotonic — lower version is a regression, same version + different hash
is a stealth edit.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rules_rollup.py
import unittest
from blygger.core import rules
from blygger.core.model import Item

def _item(version, kind="fragment", updated="2026-01-01T00:00:00Z", chash="sha256:a"):
    return Item(blyg="0.3", id="7" * 26, kind=kind, origin="https://x/blyg/", author=None,
                created="c", updated=updated, version=version, content_md="m",
                content_html="<p>m</p>", content_hash=chash, media=[], changelog=[])

class TestRollup(unittest.TestCase):
    def test_higher_version_wins(self):
        r = rules.rollup(_item(2), _item(3))
        self.assertEqual(r.item.version, 3)
        self.assertFalse(r.withdrawn)

    def test_tie_broken_by_updated(self):
        older = _item(3, updated="2026-01-01T00:00:00Z")
        newer = _item(3, updated="2026-02-01T00:00:00Z")
        self.assertEqual(rules.rollup(older, newer).item.updated, "2026-02-01T00:00:00Z")

    def test_none_local_adopts_fetched(self):
        self.assertEqual(rules.rollup(None, _item(1)).item.version, 1)

    def test_withdrawn_rolls_to_null(self):
        r = rules.rollup(_item(3), _item(4, kind="withdrawn"))
        self.assertIsNone(r.item)
        self.assertTrue(r.withdrawn)

class TestWatermark(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(rules.watermark_check(2, "sha256:a", _item(3)), rules.OK)

    def test_regression(self):
        self.assertEqual(rules.watermark_check(5, "sha256:a", _item(3)), rules.REGRESSION)

    def test_stealth_edit(self):
        self.assertEqual(rules.watermark_check(3, "sha256:a", _item(3, chash="sha256:b")),
                         rules.STEALTH_EDIT)

    def test_same_version_same_hash_is_ok(self):
        self.assertEqual(rules.watermark_check(3, "sha256:a", _item(3, chash="sha256:a")),
                         rules.OK)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_rules_rollup -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_rules_rollup -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/core/rules.py tests/test_rules_rollup.py
git commit -m "feat(core): rollup and watermark rules"
```

---

## Task 10: `core/rules.py` (part B) — resolution ladder

**Files:**
- Modify: `blygger/core/rules.py`
- Test: `tests/test_rules_resolve.py`

Spec 12.1: deterministic ≤6-fetch ladder. `fetch(url)` returns a `FetchResult`
(`status`, `body: bytes`, `final_url`). `resolve` is content-sniffing: parse-success of
`blyg.json` is the test (ignore Content-Type). Identity = final fetch origin minus
`blyg.json`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rules_resolve.py
import json, unittest
from blygger.core import rules

MANIFEST = json.dumps({"blyg": "0.3", "site": "https://x.example/blyg/"}).encode()
FEED_WITH_MANIFEST = (b'<?xml version="1.0"?><rss xmlns:blyg="https://blygger.org/ns/0.1">'
                      b'<channel><blyg:manifest>https://x.example/blyg/blyg.json'
                      b'</blyg:manifest></channel></rss>')
HTML_REL = b'<html><head><link rel="blyg" href="https://x.example/blyg/"></head></html>'
PLAIN_RSS = b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>'

def make_fetch(table):
    calls = []
    def fetch(url):
        calls.append(url)
        status, body, final = table.get(url, (404, b"", url))
        return rules.FetchResult(status=status, body=body, final_url=final)
    fetch.calls = calls
    return fetch

class TestResolve(unittest.TestCase):
    def test_direct_probe(self):
        fetch = make_fetch({"https://x.example/blyg/blyg.json":
                            (200, MANIFEST, "https://x.example/blyg/blyg.json")})
        r = rules.resolve("https://x.example/blyg/", fetch)
        self.assertEqual(r.kind, "blyg")
        self.assertEqual(r.origin, "https://x.example/blyg/")

    def test_identity_is_final_fetch_origin_after_redirect(self):
        fetch = make_fetch({"https://x.example/blyg/blyg.json":
                            (200, MANIFEST, "https://new.example/blyg/blyg.json")})
        r = rules.resolve("https://x.example/blyg/", fetch)
        self.assertEqual(r.origin, "https://new.example/blyg/")

    def test_feed_upgrade(self):
        fetch = make_fetch({
            "https://x.example/feed.xml/blyg.json": (404, b"", "x"),
            "https://x.example/feed.xml": (200, FEED_WITH_MANIFEST, "https://x.example/feed.xml"),
            "https://x.example/blyg/blyg.json": (200, MANIFEST, "https://x.example/blyg/blyg.json"),
        })
        r = rules.resolve("https://x.example/feed.xml", fetch)
        self.assertEqual(r.kind, "blyg")

    def test_rel_probe_one_hop(self):
        fetch = make_fetch({
            "https://x.example/post/blyg.json": (404, b"", "x"),
            "https://x.example/post/": (200, HTML_REL, "https://x.example/post/"),
            "https://x.example/blyg/blyg.json": (200, MANIFEST, "https://x.example/blyg/blyg.json"),
        })
        r = rules.resolve("https://x.example/post/", fetch)
        self.assertEqual(r.kind, "blyg")

    def test_rss_fallback_is_l0(self):
        fetch = make_fetch({
            "https://x.example/feed.xml/blyg.json": (404, b"", "x"),
            "https://x.example/feed.xml": (200, PLAIN_RSS, "https://x.example/feed.xml"),
        })
        r = rules.resolve("https://x.example/feed.xml", fetch)
        self.assertEqual(r.kind, "l0")

    def test_failure_when_nothing_found(self):
        fetch = make_fetch({})
        r = rules.resolve("https://x.example/nope/", fetch)
        self.assertEqual(r.kind, "fail")

    def test_bounded_to_six_fetches(self):
        fetch = make_fetch({})
        rules.resolve("https://x.example/nope/", fetch)
        self.assertLessEqual(len(fetch.calls), 6)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_rules_resolve -v`
Expected: FAIL (`AttributeError: FetchResult`).

- [ ] **Step 3: Write minimal implementation (append to `rules.py`)**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_rules_resolve -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/core/rules.py tests/test_rules_resolve.py
git commit -m "feat(core): URL-to-subscription resolution ladder"
```

---

## Task 11: `publish/store.py` — private canonical store

**Files:**
- Create: `blygger/publish/store.py`
- Test: `tests/test_store.py`

Spec 5.2, 8: the store retains ALL versions (withheld history) so retroactive pinning
works. Backed by plain JSON under a private directory.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_store.py
import tempfile, unittest
from pathlib import Path
from blygger.publish.store import Store

class TestStore(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = Store(Path(self.dir))

    def test_create_and_get_item(self):
        self.store.create_item("7" * 26, "fragment", "2026-01-01T00:00:00Z")
        self.store.add_version("7" * 26, {"version": 1, "at": "2026-01-01T00:00:00Z",
                                          "kind": "fragment", "content_md": "hi",
                                          "content_html": "<p>hi</p>", "content_hash": "sha256:a",
                                          "media": [], "note": None})
        rec = self.store.get_item("7" * 26)
        self.assertEqual(rec["authored_kind"], "fragment")
        self.assertEqual(len(rec["versions"]), 1)

    def test_persists_across_instances(self):
        self.store.create_item("7" * 26, "fragment", "c")
        reopened = Store(Path(self.dir))
        self.assertIsNotNone(reopened.get_item("7" * 26))

    def test_set_pinned(self):
        self.store.create_item("7" * 26, "fragment", "c")
        self.store.add_version("7" * 26, {"version": 1, "at": "t", "kind": "fragment",
                                          "content_md": "m", "content_html": "<p>m</p>",
                                          "content_hash": "sha256:a", "media": [], "note": None})
        self.store.set_pinned("7" * 26, 1)
        self.assertTrue(self.store.get_item("7" * 26)["versions"][0]["pinned"])

    def test_all_items(self):
        self.store.create_item("7" * 26, "fragment", "c")
        self.store.create_item("1" * 26, "thread", "c")
        self.assertEqual(set(self.store.all_item_ids()), {"7" * 26, "1" * 26})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_store -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# blygger/publish/store.py
"""Private canonical store: every version of every item, plus manifest + blogroll
metadata. Nothing here is served directly (spec 5.2, 8)."""
import json
from pathlib import Path


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        (self.root / "items").mkdir(parents=True, exist_ok=True)

    def _item_path(self, item_id: str) -> Path:
        return self.root / "items" / f"{item_id}.json"

    def _read(self, path: Path):
        return json.loads(path.read_text("utf-8")) if path.exists() else None

    def _write(self, path: Path, data) -> None:
        path.write_text(json.dumps(data, indent=2, sort_keys=True), "utf-8")

    # ---- items ----
    def create_item(self, item_id: str, authored_kind: str, created: str) -> None:
        if self._item_path(item_id).exists():
            return
        self._write(self._item_path(item_id),
                    {"authored_kind": authored_kind, "created": created, "versions": []})

    def add_version(self, item_id: str, version_record: dict) -> None:
        rec = self._read(self._item_path(item_id))
        version_record.setdefault("pinned", False)
        rec["versions"].append(version_record)
        self._write(self._item_path(item_id), rec)

    def get_item(self, item_id: str):
        return self._read(self._item_path(item_id))

    def set_pinned(self, item_id: str, version: int) -> None:
        rec = self._read(self._item_path(item_id))
        for v in rec["versions"]:
            if v["version"] == version:
                v["pinned"] = True
        self._write(self._item_path(item_id), rec)

    def all_item_ids(self):
        return [p.stem for p in (self.root / "items").glob("*.json")]

    # ---- manifest / blogroll metadata ----
    def set_manifest_meta(self, meta: dict) -> None:
        self._write(self.root / "manifest.json", meta)

    def get_manifest_meta(self):
        return self._read(self.root / "manifest.json") or {}

    def set_blogroll(self, entries) -> None:
        self._write(self.root / "blogroll.json", entries)

    def get_blogroll(self):
        return self._read(self.root / "blogroll.json") or []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_store -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/publish/store.py tests/test_store.py
git commit -m "feat(publish): private all-versions canonical store"
```

---

## Task 12: `publish/studio.py` — publish operations

**Files:**
- Create: `blygger/publish/studio.py`
- Test: `tests/test_studio.py`

Spec 5–10: operations enforce MUSTs (version +1, `updated` == latest changelog `at`, id
immutable, thread transclusion resolves to local published items). `Studio` takes a clock
callable (`() -> datetime`) so tests are deterministic.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_studio.py
import tempfile, unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from blygger.publish.store import Store
from blygger.publish.studio import Studio
from blygger.core.errors import PublishError

class Clock:
    def __init__(self):
        self.t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    def __call__(self):
        self.t += timedelta(minutes=1)
        return self.t

class TestStudio(unittest.TestCase):
    def setUp(self):
        self.store = Store(Path(tempfile.mkdtemp()))
        self.studio = Studio(self.store, origin="https://x/blyg/",
                             author={"name": "A"}, clock=Clock())

    def test_publish_fragment(self):
        fid = self.studio.publish_fragment("Hello *world*.")
        rec = self.store.get_item(fid)
        self.assertEqual(rec["authored_kind"], "fragment")
        v = rec["versions"][0]
        self.assertEqual(v["version"], 1)
        self.assertEqual(v["content_html"], "<p>Hello <em>world</em>.</p>")
        self.assertTrue(v["content_hash"].startswith("sha256:"))

    def test_edit_increments_version(self):
        fid = self.studio.publish_fragment("v1")
        self.studio.edit(fid, "v2", note="change")
        versions = self.store.get_item(fid)["versions"]
        self.assertEqual([v["version"] for v in versions], [1, 2])

    def test_withdraw_produces_empty_endcap(self):
        fid = self.studio.publish_fragment("bye soon")
        self.studio.withdraw(fid, note="done")
        last = self.store.get_item(fid)["versions"][-1]
        self.assertEqual(last["kind"], "withdrawn")
        self.assertEqual(last["content_md"], "")
        self.assertEqual(last["content_html"], "")
        self.assertEqual(last["media"], [])

    def test_publish_thread_transcludes_local_fragment(self):
        fid = self.studio.publish_fragment("quoted text")
        tid = self.studio.publish_thread(f"Intro\n\n![[{fid}]]\n\nEnd")
        rec = self.store.get_item(tid)
        v = rec["versions"][0]
        self.assertEqual(v["kind"], "thread")
        self.assertIn("blyg-transclusion", v["content_html"])
        self.assertEqual(v["transclusions"], [{"id": fid, "version": 1}])

    def test_thread_with_unknown_target_errors(self):
        with self.assertRaises(PublishError):
            self.studio.publish_thread("![[" + "0" * 26 + "]]")

    def test_pin_marks_version(self):
        fid = self.studio.publish_fragment("v1")
        self.studio.edit(fid, "v2")
        self.studio.pin(fid, 1)
        self.assertTrue(self.store.get_item(fid)["versions"][0]["pinned"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_studio -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_studio -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/publish/studio.py tests/test_studio.py
git commit -m "feat(publish): studio publish/edit/withdraw/pin/thread ops"
```

---

## Task 13: `publish/emit.py` — static surface emitter

**Files:**
- Create: `blygger/publish/emit.py`
- Test: `tests/test_emit.py`

Spec 4, 6, 7, 8: emit `blyg.json`, `items/{id}.json` (latest only), `items/{id}/v{n}.json`
(pinned), `items/index.json` (complete, updated desc), `feed.xml` (one entry per publish
event, newest first, windowed, per-version GUIDs, latest-content descriptions, single
`withdrawn` entry), `blogroll.opml` (when non-empty). Idempotent + additive; errors on
would-be pin deletion.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_emit.py
import json, tempfile, unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET
from blygger.publish.store import Store
from blygger.publish.studio import Studio
from blygger.publish.emit import emit
from blygger.core.errors import PublishError

NS = {"blyg": "https://blygger.org/ns/0.1"}

class Clock:
    def __init__(self):
        self.t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    def __call__(self):
        self.t += timedelta(minutes=1)
        return self.t

class TestEmit(unittest.TestCase):
    def setUp(self):
        self.private = Path(tempfile.mkdtemp())
        self.out = Path(tempfile.mkdtemp())
        self.store = Store(self.private)
        self.store.set_manifest_meta({"title": "T", "site": "https://x/blyg/",
                                      "author": {"name": "A"}})
        self.studio = Studio(self.store, origin="https://x/blyg/", author={"name": "A"},
                             clock=Clock())

    def _emit(self):
        emit(self.store, self.out, origin="https://x/blyg/",
             generator="blygger-ref/0.1", updated="2026-01-01T12:00:00Z")

    def test_manifest_and_item_and_index(self):
        fid = self.studio.publish_fragment("hello")
        self._emit()
        manifest = json.loads((self.out / "blyg.json").read_text())
        self.assertEqual(manifest["blyg"], "0.3")
        self.assertEqual(manifest["level"], 1)
        item = json.loads((self.out / "items" / f"{fid}.json").read_text())
        self.assertEqual(item["version"], 1)
        self.assertNotIn("transclusions", item)
        index = json.loads((self.out / "items" / "index.json").read_text())
        self.assertEqual(index["items"][0]["id"], fid)

    def test_feed_one_entry_per_event_newest_first(self):
        fid = self.studio.publish_fragment("v1")
        self.studio.edit(fid, "v2", note="change")
        self._emit()
        root = ET.fromstring((self.out / "feed.xml").read_text())
        guids = [g.text for g in root.findall(".//item/guid")]
        self.assertEqual(guids, [f"blyg:{fid}:v2", f"blyg:{fid}:v1"])
        # descriptions carry LATEST html even for the older entry
        descs = [d.text for d in root.findall(".//item/description")]
        self.assertTrue(all("v2" in d for d in descs))

    def test_withdrawn_single_entry(self):
        fid = self.studio.publish_fragment("hi")
        self.studio.withdraw(fid)
        self._emit()
        root = ET.fromstring((self.out / "feed.xml").read_text())
        items = root.findall(".//item")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].find("title").text, "withdrawn")

    def test_pinned_version_file_emitted(self):
        fid = self.studio.publish_fragment("v1")
        self.studio.edit(fid, "v2")
        self.studio.pin(fid, 1)
        self._emit()
        self.assertTrue((self.out / "items" / fid / "v1.json").exists())

    def test_emit_never_deletes_existing_pin(self):
        fid = self.studio.publish_fragment("v1")
        self.studio.pin(fid, 1)
        self._emit()
        # Simulate a store that forgot the pin, then re-emit: must error, not delete.
        rec = self.store.get_item(fid)
        rec["versions"][0]["pinned"] = False
        self.store._write(self.store._item_path(fid), rec)
        with self.assertRaises(PublishError):
            self._emit()

    def test_blogroll_emitted_when_present(self):
        self.studio.publish_fragment("hi")
        self.store.set_blogroll([{"text": "I", "xmlUrl": "https://i/feed", "htmlUrl": "https://i/"}])
        self._emit()
        self.assertTrue((self.out / "blogroll.opml").exists())
        manifest = json.loads((self.out / "blyg.json").read_text())
        self.assertEqual(manifest["blogroll"], "blogroll.opml")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_emit -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
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
                excerpt = latest["content_md"][:60]
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_emit -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/publish/emit.py tests/test_emit.py
git commit -m "feat(publish): static surface emitter"
```

---

## Task 14: Phase 1 checkpoint — full publisher suite green

- [ ] **Step 1: Run the whole suite**

Run: `python -m unittest discover -s tests -v`
Expected: all tests PASS.

- [ ] **Step 2: Commit a checkpoint tag**

```bash
git commit --allow-empty -m "checkpoint: phase 1 (core + publisher) complete"
```

---

# Phase 2 — Reader + Transport + Round-trip

## Task 15: `transport/base.py` + `transport/fs.py`

**Files:**
- Create: `blygger/transport/base.py`, `blygger/transport/fs.py`
- Test: `tests/test_transport_fs.py`

Spec 7: `Response` carries `final_url` (load-bearing for resolution identity). `FsTransport`
maps an origin URL onto an emitted output dir; `200` for present files, `404` for missing;
conditional requests return `304` via a content ETag.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_transport_fs.py
import tempfile, unittest
from pathlib import Path
from blygger.transport.fs import FsTransport

class TestFsTransport(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "blyg.json").write_text('{"blyg": "0.3"}', "utf-8")
        self.t = FsTransport("https://x.example/blyg/", self.root)

    def test_get_existing_file(self):
        r = self.t.get("https://x.example/blyg/blyg.json")
        self.assertEqual(r.status, 200)
        self.assertIn(b'"blyg"', r.body)
        self.assertEqual(r.final_url, "https://x.example/blyg/blyg.json")

    def test_missing_file_404(self):
        self.assertEqual(self.t.get("https://x.example/blyg/missing.json").status, 404)

    def test_conditional_request_304(self):
        r1 = self.t.get("https://x.example/blyg/blyg.json")
        etag = r1.headers["ETag"]
        r2 = self.t.get("https://x.example/blyg/blyg.json", etag=etag)
        self.assertEqual(r2.status, 304)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_transport_fs -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# blygger/transport/base.py
"""Transport interface. Policy (polling/backoff) lives above this, in read/poll.py."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    final_url: str
    headers: dict = field(default_factory=dict)


class Transport(ABC):
    @abstractmethod
    def get(self, url: str, *, etag=None, last_modified=None) -> Response:
        ...
```

```python
# blygger/transport/fs.py
"""Filesystem transport: serve an emitted output directory as an origin (spec 7)."""
import hashlib
from pathlib import Path
from .base import Transport, Response


class FsTransport(Transport):
    def __init__(self, origin: str, root: Path):
        if not origin.endswith("/"):
            origin += "/"
        self.origin = origin
        self.root = Path(root)

    def _path_for(self, url: str):
        if not url.startswith(self.origin):
            return None
        rel = url[len(self.origin):]
        return self.root / rel if rel else self.root

    def get(self, url: str, *, etag=None, last_modified=None) -> Response:
        path = self._path_for(url)
        if path is None or not path.is_file():
            return Response(status=404, body=b"", final_url=url)
        body = path.read_bytes()
        tag = '"' + hashlib.sha256(body).hexdigest()[:16] + '"'
        if etag is not None and etag == tag:
            return Response(status=304, body=b"", final_url=url, headers={"ETag": tag})
        return Response(status=200, body=body, final_url=url, headers={"ETag": tag})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_transport_fs -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/transport/base.py blygger/transport/fs.py tests/test_transport_fs.py
git commit -m "feat(transport): Transport ABC and filesystem backend"
```

---

## Task 16: `transport/http.py` — urllib HTTP backend

**Files:**
- Create: `blygger/transport/http.py`
- Test: `tests/test_transport_http.py`

Spec 12.2–12.3, 14: conditional headers, bounded redirects (≤5) tracking `final_url`,
identifying `User-Agent`, size cap + timeout. Tested against a localhost `http.server`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_transport_http.py
import tempfile, threading, unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from blygger.transport.http import HttpTransport

class TestHttpTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp())
        (cls.root / "blyg.json").write_text('{"blyg": "0.3"}', "utf-8")
        handler = partial(SimpleHTTPRequestHandler, directory=str(cls.root))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_get_200(self):
        t = HttpTransport(generator="blygger-ref/0.1")
        r = t.get(f"http://127.0.0.1:{self.port}/blyg.json")
        self.assertEqual(r.status, 200)
        self.assertIn(b'"blyg"', r.body)

    def test_get_404(self):
        t = HttpTransport(generator="blygger-ref/0.1")
        r = t.get(f"http://127.0.0.1:{self.port}/missing.json")
        self.assertEqual(r.status, 404)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_transport_http -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# blygger/transport/http.py
"""HTTP transport over urllib with fetch hygiene (spec 12.2-12.3, 14)."""
import urllib.request
import urllib.error
import urllib.parse
from .base import Transport, Response

_MAX_REDIRECTS = 5
_MAX_BYTES = 5 * 1024 * 1024
_TIMEOUT = 30


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # we follow manually to track final_url


class HttpTransport(Transport):
    def __init__(self, generator="blygger-ref/0.1", max_redirects=_MAX_REDIRECTS,
                 max_bytes=_MAX_BYTES, timeout=_TIMEOUT):
        self.user_agent = generator
        self.max_redirects = max_redirects
        self.max_bytes = max_bytes
        self.timeout = timeout
        self._opener = urllib.request.build_opener(_NoRedirect())

    def get(self, url: str, *, etag=None, last_modified=None) -> Response:
        current = url
        for _ in range(self.max_redirects + 1):
            req = urllib.request.Request(current, method="GET")
            req.add_header("User-Agent", self.user_agent)
            if etag:
                req.add_header("If-None-Match", etag)
            if last_modified:
                req.add_header("If-Modified-Since", last_modified)
            try:
                resp = self._opener.open(req, timeout=self.timeout)
            except urllib.error.HTTPError as e:
                if e.code in (301, 302, 303, 307, 308):
                    loc = e.headers.get("Location")
                    if not loc:
                        return Response(status=e.code, body=b"", final_url=current)
                    current = urllib.parse.urljoin(current, loc)
                    continue
                if e.code == 304:
                    return Response(status=304, body=b"", final_url=current,
                                    headers=dict(e.headers))
                return Response(status=e.code, body=b"", final_url=current,
                                headers=dict(e.headers))
            except (urllib.error.URLError, OSError):
                return Response(status=0, body=b"", final_url=current)
            with resp:
                body = resp.read(self.max_bytes + 1)
                if len(body) > self.max_bytes:
                    body = body[:self.max_bytes]
                return Response(status=resp.status, body=body,
                                final_url=resp.geturl(), headers=dict(resp.headers))
        return Response(status=0, body=b"", final_url=current)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_transport_http -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/transport/http.py tests/test_transport_http.py
git commit -m "feat(transport): urllib HTTP backend with fetch hygiene"
```

---

## Task 17: `read/archive.py` — origin-scoped state + watermark

**Files:**
- Create: `blygger/read/archive.py`
- Test: `tests/test_archive.py`

Spec 13.1, 13.3: everything scoped to `(origin, id)`; tracks current state, `content_hash`,
and the monotonic watermark.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_archive.py
import tempfile, unittest
from pathlib import Path
from blygger.read.archive import Archive

class TestArchive(unittest.TestCase):
    def setUp(self):
        self.a = Archive(Path(tempfile.mkdtemp()))
        self.origin = "https://x/blyg/"

    def test_put_and_get(self):
        self.a.put(self.origin, "7" * 26, {"version": 1, "content_hash": "sha256:a"})
        rec = self.a.get(self.origin, "7" * 26)
        self.assertEqual(rec["version"], 1)
        self.assertEqual(self.a.watermark(self.origin, "7" * 26), 1)

    def test_watermark_is_monotonic(self):
        self.a.put(self.origin, "7" * 26, {"version": 3, "content_hash": "sha256:a"})
        self.a.put(self.origin, "7" * 26, {"version": 2, "content_hash": "sha256:a"})
        self.assertEqual(self.a.watermark(self.origin, "7" * 26), 3)

    def test_scoped_by_origin(self):
        self.a.put("https://a/", "7" * 26, {"version": 1, "content_hash": "x"})
        self.assertIsNone(self.a.get("https://b/", "7" * 26))

    def test_roll_to_null_keeps_watermark(self):
        self.a.put(self.origin, "7" * 26, {"version": 2, "content_hash": "x"})
        self.a.roll_to_null(self.origin, "7" * 26)
        self.assertIsNone(self.a.get(self.origin, "7" * 26))
        self.assertEqual(self.a.watermark(self.origin, "7" * 26), 2)

    def test_known_ids(self):
        self.a.put(self.origin, "7" * 26, {"version": 1, "content_hash": "x"})
        self.assertEqual(self.a.known_ids(self.origin), {"7" * 26})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_archive -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# blygger/read/archive.py
"""Origin-scoped reader archive with a monotonic watermark (spec 13.1, 13.3)."""
import hashlib
import json
from pathlib import Path


def _origin_key(origin: str) -> str:
    return hashlib.sha256(origin.encode("utf-8")).hexdigest()[:16]


class Archive:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _file(self, origin: str) -> Path:
        return self.root / f"{_origin_key(origin)}.json"

    def _load(self, origin: str) -> dict:
        f = self._file(origin)
        return json.loads(f.read_text("utf-8")) if f.exists() else {"origin": origin, "items": {}}

    def _save(self, origin: str, data: dict) -> None:
        self._file(origin).write_text(json.dumps(data, indent=2, sort_keys=True), "utf-8")

    def put(self, origin: str, item_id: str, state: dict) -> None:
        data = self._load(origin)
        entry = data["items"].get(item_id, {"watermark": 0})
        entry["state"] = state
        entry["watermark"] = max(entry.get("watermark", 0), int(state.get("version", 0)))
        data["items"][item_id] = entry
        self._save(origin, data)

    def roll_to_null(self, origin: str, item_id: str) -> None:
        data = self._load(origin)
        entry = data["items"].get(item_id, {"watermark": 0})
        entry["state"] = None
        data["items"][item_id] = entry
        self._save(origin, data)

    def get(self, origin: str, item_id: str):
        entry = self._load(origin)["items"].get(item_id)
        return entry["state"] if entry else None

    def watermark(self, origin: str, item_id: str) -> int:
        entry = self._load(origin)["items"].get(item_id)
        return entry.get("watermark", 0) if entry else 0

    def bump_watermark(self, origin: str, item_id: str, version: int) -> None:
        data = self._load(origin)
        entry = data["items"].get(item_id, {"watermark": 0, "state": None})
        entry["watermark"] = max(entry.get("watermark", 0), version)
        data["items"][item_id] = entry
        self._save(origin, data)

    def known_ids(self, origin: str):
        return set(self._load(origin)["items"].keys())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_archive -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/read/archive.py tests/test_archive.py
git commit -m "feat(read): origin-scoped archive with watermark"
```

---

## Task 18: `read/feed.py` — RSS feed parsing

**Files:**
- Create: `blygger/read/feed.py`
- Test: `tests/test_feed.py`

Spec 7, 13.2: parse feed entries (`blyg:id`, `blyg:version`, `blyg:item`, `blyg:kind`);
malformed entries are skipped individually, not fatal.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_feed.py
import unittest
from blygger.read.feed import parse_feed

FEED = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:blyg="https://blygger.org/ns/0.1">
  <channel>
    <blyg:manifest>https://x/blyg/blyg.json</blyg:manifest>
    <item>
      <guid isPermaLink="false">blyg:AAAAAAAAAAAAAAAAAAAAAAAAAA:v2</guid>
      <blyg:id>AAAAAAAAAAAAAAAAAAAAAAAAAA</blyg:id>
      <blyg:kind>fragment</blyg:kind>
      <blyg:version>2</blyg:version>
      <blyg:item>https://x/blyg/items/AAAAAAAAAAAAAAAAAAAAAAAAAA.json</blyg:item>
    </item>
  </channel>
</rss>"""

class TestFeed(unittest.TestCase):
    def test_parse_entries(self):
        entries = parse_feed(FEED)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["id"], "AAAAAAAAAAAAAAAAAAAAAAAAAA")
        self.assertEqual(e["version"], 2)
        self.assertEqual(e["item_url"], "https://x/blyg/items/AAAAAAAAAAAAAAAAAAAAAAAAAA.json")

    def test_unparseable_feed_returns_empty(self):
        self.assertEqual(parse_feed(b"not xml"), [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_feed -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# blygger/read/feed.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_feed -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/read/feed.py tests/test_feed.py
git commit -m "feat(read): blyg RSS feed parsing"
```

---

## Task 19: `read/resolve.py` — wire transport into resolution

**Files:**
- Create: `blygger/read/resolve.py`
- Test: `tests/test_resolve.py`

Spec 12: `resolve_subscription(transport, url)` adapts a `Transport` into the pure
`core.rules.resolve` fetch callable and returns a `Subscription` (origin + manifest). Also
surfaces the `site`-vs-origin discrepancy without adopting `site`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_resolve.py
import json, tempfile, unittest
from pathlib import Path
from blygger.transport.fs import FsTransport
from blygger.read.resolve import resolve_subscription

class TestResolveSubscription(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "blyg.json").write_text(json.dumps(
            {"blyg": "0.3", "site": "https://x.example/blyg/", "title": "T",
             "feed": "feed.xml", "items": "items/index.json"}), "utf-8")
        self.t = FsTransport("https://x.example/blyg/", self.root)

    def test_direct_resolution(self):
        sub = resolve_subscription(self.t, "https://x.example/blyg/")
        self.assertEqual(sub.kind, "blyg")
        self.assertEqual(sub.origin, "https://x.example/blyg/")
        self.assertEqual(sub.manifest.title, "T")

    def test_site_mismatch_surfaced_but_not_adopted(self):
        (self.root / "blyg.json").write_text(json.dumps(
            {"blyg": "0.3", "site": "https://LYING.example/blyg/", "title": "T",
             "feed": "feed.xml", "items": "items/index.json"}), "utf-8")
        sub = resolve_subscription(self.t, "https://x.example/blyg/")
        self.assertEqual(sub.origin, "https://x.example/blyg/")   # fetch origin wins
        self.assertTrue(sub.site_mismatch)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_resolve -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# blygger/read/resolve.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_resolve -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/read/resolve.py tests/test_resolve.py
git commit -m "feat(read): resolve_subscription wiring transport into ladder"
```

---

## Task 20: `read/reconcile.py` — import & reconciliation

**Files:**
- Create: `blygger/read/reconcile.py`
- Test: `tests/test_reconcile.py`

Spec 13: feed triggers item fetch; index diff is total reconciliation; only a fetched
document advances state; watermark enforcement; withdrawal rolls to null; discrepancies are
recorded not thrown.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reconcile.py
import json, tempfile, unittest
from pathlib import Path
from blygger.transport.fs import FsTransport
from blygger.read.archive import Archive
from blygger.read.resolve import resolve_subscription
from blygger.read.reconcile import Reconciler

def _write_blyg(root, items, feed_entries, index_entries):
    (root / "items").mkdir(parents=True, exist_ok=True)
    (root / "blyg.json").write_text(json.dumps(
        {"blyg": "0.3", "site": "https://x/blyg/", "title": "T",
         "feed": "feed.xml", "items": "items/index.json"}), "utf-8")
    for iid, doc in items.items():
        (root / "items" / f"{iid}.json").write_text(json.dumps(doc), "utf-8")
    (root / "items" / "index.json").write_text(json.dumps(
        {"updated": "2026-01-01T00:00:00Z", "items": index_entries}), "utf-8")
    item_xml = "".join(
        f"<item><blyg:id>{e['id']}</blyg:id><blyg:version>{e['version']}</blyg:version>"
        f"<blyg:item>https://x/blyg/items/{e['id']}.json</blyg:item></item>"
        for e in feed_entries)
    (root / "feed.xml").write_text(
        '<?xml version="1.0"?><rss xmlns:blyg="https://blygger.org/ns/0.1"><channel>'
        + item_xml + "</channel></rss>", "utf-8")

def _doc(iid, version, kind="fragment", chash="sha256:a", md="hi"):
    return {"blyg": "0.3", "id": iid, "kind": kind, "origin": "https://x/blyg/",
            "author": {"name": "A"}, "created": "2026-01-01T00:00:00Z",
            "updated": f"2026-01-0{version}T00:00:00Z", "version": version,
            "content_md": md, "content_html": f"<p>{md}</p>", "content_hash": chash,
            "media": [], "changelog": []}

A = "a" * 26

class TestReconcile(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.archive = Archive(Path(tempfile.mkdtemp()))

    def _reconciler(self):
        t = FsTransport("https://x/blyg/", self.root)
        sub = resolve_subscription(t, "https://x/blyg/")
        return Reconciler(t, self.archive), sub

    def test_feed_triggers_fetch_and_rollup(self):
        _write_blyg(self.root, {A: _doc(A, 1)},
                    [{"id": A, "version": 1}], [{"id": A, "kind": "fragment",
                     "created": "c", "updated": "u", "version": 1}])
        rec, sub = self._reconciler()
        result = rec.reconcile(sub)
        self.assertEqual(self.archive.get(sub.origin, A)["version"], 1)
        self.assertEqual(result.discrepancies, [])

    def test_index_backfill_when_feed_window_misses(self):
        # feed is empty, but index lists the item -> index diff recovers it
        _write_blyg(self.root, {A: _doc(A, 1)}, [],
                    [{"id": A, "kind": "fragment", "created": "c", "updated": "u", "version": 1}])
        rec, sub = self._reconciler()
        rec.reconcile(sub)
        self.assertEqual(self.archive.get(sub.origin, A)["version"], 1)

    def test_withdrawal_rolls_to_null(self):
        _write_blyg(self.root, {A: _doc(A, 2, kind="withdrawn", md="")},
                    [{"id": A, "version": 2}],
                    [{"id": A, "kind": "withdrawn", "created": "c", "updated": "u", "version": 2}])
        rec, sub = self._reconciler()
        rec.reconcile(sub)
        self.assertIsNone(self.archive.get(sub.origin, A))
        self.assertEqual(self.archive.watermark(sub.origin, A), 2)

    def test_version_regression_is_recorded_not_adopted(self):
        _write_blyg(self.root, {A: _doc(A, 5)}, [{"id": A, "version": 5}],
                    [{"id": A, "kind": "fragment", "created": "c", "updated": "u", "version": 5}])
        rec, sub = self._reconciler()
        rec.reconcile(sub)
        # now origin rewrites history to v3
        (self.root / "items" / f"{A}.json").write_text(json.dumps(_doc(A, 3)), "utf-8")
        (self.root / "feed.xml").write_text(
            '<?xml version="1.0"?><rss xmlns:blyg="https://blygger.org/ns/0.1"><channel>'
            f'<item><blyg:id>{A}</blyg:id><blyg:version>3</blyg:version>'
            f'<blyg:item>https://x/blyg/items/{A}.json</blyg:item></item>'
            '</channel></rss>', "utf-8")
        result = rec.reconcile(sub)
        self.assertEqual(self.archive.get(sub.origin, A)["version"], 5)   # not adopted
        self.assertTrue(any(d.type == "regression" for d in result.discrepancies))

    def test_stealth_edit_adopts_content_and_records(self):
        _write_blyg(self.root, {A: _doc(A, 1, chash="sha256:a")}, [{"id": A, "version": 1}],
                    [{"id": A, "kind": "fragment", "created": "c", "updated": "u", "version": 1}])
        rec, sub = self._reconciler()
        rec.reconcile(sub)
        (self.root / "items" / f"{A}.json").write_text(
            json.dumps(_doc(A, 1, chash="sha256:b", md="changed")), "utf-8")
        result = rec.reconcile(sub)
        self.assertEqual(self.archive.get(sub.origin, A)["content_hash"], "sha256:b")
        self.assertTrue(any(d.type == "stealth_edit" for d in result.discrepancies))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_reconcile -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# blygger/read/reconcile.py
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
        # hash self-consistency check (defect report, not a reject)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_reconcile -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/read/reconcile.py tests/test_reconcile.py
git commit -m "feat(read): reconciler with watermark and withdrawal handling"
```

---

## Task 21: `read/poll.py` — polling etiquette

**Files:**
- Create: `blygger/read/poll.py`
- Test: `tests/test_poll.py`

Spec 12.3: conditional-request bookkeeping, exponential backoff, honor `Retry-After`, never
tighten interval on failure, never discard state. Pure policy (no I/O), so it is unit-tested
directly.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_poll.py
import unittest
from blygger.read.poll import PollState

class TestPoll(unittest.TestCase):
    def test_success_resets_interval(self):
        p = PollState(base_interval=60, max_interval=3600)
        p.on_failure(); p.on_failure()
        p.on_success(etag='"abc"')
        self.assertEqual(p.next_interval(), 60)
        self.assertEqual(p.etag, '"abc"')

    def test_failure_backs_off_exponentially(self):
        p = PollState(base_interval=60, max_interval=3600)
        p.on_failure()
        self.assertEqual(p.next_interval(), 120)
        p.on_failure()
        self.assertEqual(p.next_interval(), 240)

    def test_interval_capped_at_max(self):
        p = PollState(base_interval=60, max_interval=100)
        for _ in range(10):
            p.on_failure()
        self.assertEqual(p.next_interval(), 100)

    def test_retry_after_honored(self):
        p = PollState(base_interval=60, max_interval=3600)
        p.on_retry_after(900)
        self.assertEqual(p.next_interval(), 900)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_poll -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

```python
# blygger/read/poll.py
"""Polling policy: conditional requests + backoff (spec 12.3). Pure, no I/O."""


class PollState:
    def __init__(self, base_interval=60, max_interval=3600):
        self.base_interval = base_interval
        self.max_interval = max_interval
        self.failures = 0
        self.etag = None
        self.last_modified = None
        self._retry_after = None

    def on_success(self, etag=None, last_modified=None):
        self.failures = 0
        self._retry_after = None
        if etag is not None:
            self.etag = etag
        if last_modified is not None:
            self.last_modified = last_modified

    def on_failure(self):
        self.failures += 1               # never discards etag/state

    def on_retry_after(self, seconds):
        self._retry_after = seconds

    def next_interval(self):
        if self._retry_after is not None:
            return min(self._retry_after, self.max_interval) if self._retry_after > self.max_interval \
                else self._retry_after
        interval = self.base_interval * (2 ** self.failures)
        return min(interval, self.max_interval)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_poll -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add blygger/read/poll.py tests/test_poll.py
git commit -m "feat(read): polling etiquette state machine"
```

---

## Task 22: Round-trip conformance oracle

**Files:**
- Create: `tests/test_roundtrip.py`

Spec 9 (plan): publisher publishes a scripted history → emit writes a dir → reader resolves
from scratch, subscribes, reconciles → final reader state equals the publisher's public
truth. Run over BOTH `FsTransport` (fast) and a real localhost `HttpTransport`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_roundtrip.py
import tempfile, threading, unittest
from datetime import datetime, timezone, timedelta
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from blygger.publish.store import Store
from blygger.publish.studio import Studio
from blygger.publish.emit import emit
from blygger.transport.fs import FsTransport
from blygger.transport.http import HttpTransport
from blygger.read.archive import Archive
from blygger.read.resolve import resolve_subscription
from blygger.read.reconcile import Reconciler

class Clock:
    def __init__(self):
        self.t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    def __call__(self):
        self.t += timedelta(minutes=1)
        return self.t

def publish_history(out_dir, origin):
    store = Store(Path(tempfile.mkdtemp()))
    store.set_manifest_meta({"title": "T", "site": origin, "author": {"name": "A"}})
    studio = Studio(store, origin=origin, author={"name": "A"}, clock=Clock())
    f1 = studio.publish_fragment("first fragment")
    studio.edit(f1, "first fragment, sharpened", note="sharpen")
    f2 = studio.publish_fragment("second fragment")
    studio.pin(f2, 1)
    t1 = studio.publish_thread(f"Thread intro\n\n![[{f1}]]\n\nend")
    f3 = studio.publish_fragment("doomed")
    studio.withdraw(f3)
    emit(store, out_dir, origin=origin, generator="blygger-ref/0.1",
         updated="2026-01-01T12:00:00Z")
    return {"f1": f1, "f2": f2, "t1": t1, "f3": f3}

def run_reader(transport, url):
    archive = Archive(Path(tempfile.mkdtemp()))
    sub = resolve_subscription(transport, url)
    assert sub.kind == "blyg", sub
    Reconciler(transport, archive).reconcile(sub)
    return archive, sub.origin

class TestRoundTripFs(unittest.TestCase):
    def test_reader_state_equals_publisher_truth(self):
        out = Path(tempfile.mkdtemp())
        origin = "https://pub.example/blyg/"
        ids = publish_history(out, origin)
        transport = FsTransport(origin, out)
        archive, resolved_origin = run_reader(transport, origin)

        # live fragment rolled to latest version
        self.assertEqual(archive.get(resolved_origin, ids["f1"])["version"], 2)
        # pinned fragment present at v1
        self.assertEqual(archive.get(resolved_origin, ids["f2"])["version"], 1)
        # thread present and carries baked transclusion html
        self.assertEqual(archive.get(resolved_origin, ids["t1"])["kind"], "thread")
        self.assertIn("blyg-transclusion", archive.get(resolved_origin, ids["t1"])["content_html"])
        # withdrawn item rolled to null, watermark retained
        self.assertIsNone(archive.get(resolved_origin, ids["f3"]))
        self.assertEqual(archive.watermark(resolved_origin, ids["f3"]), 2)

class TestRoundTripHttp(unittest.TestCase):
    def test_reader_over_real_http(self):
        # Serve a root dir; the blyg lives under /blyg/ so resolution finds it.
        served = Path(tempfile.mkdtemp())
        handler = partial(SimpleHTTPRequestHandler, directory=str(served))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = server.server_address[1]
        origin = f"http://127.0.0.1:{port}/blyg/"
        ids = publish_history(served / "blyg", origin)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            transport = HttpTransport(generator="blygger-ref/0.1")
            archive, resolved_origin = run_reader(transport, origin)
            self.assertEqual(archive.get(resolved_origin, ids["f1"])["version"], 2)
            self.assertIsNone(archive.get(resolved_origin, ids["f3"]))
        finally:
            server.shutdown()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_roundtrip -v`
Expected: FAIL initially if any wiring gap exists; fix the specific failure (common gaps:
`emit` not creating the served subdir, origin trailing slash). Iterate until green.

- [ ] **Step 3: Make it pass**

No new production code should be required beyond small fixes surfaced by the test. If a fix
is needed, make the minimal change in the implicated module and re-run.

- [ ] **Step 4: Run the full suite**

Run: `python -m unittest discover -s tests -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_roundtrip.py
git commit -m "test: round-trip conformance oracle over fs and http"
```

---

## Task 23: Phase 2 checkpoint & README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write a short README**

```markdown
# blygger-reference-client

A pure-stdlib Python reference client for the [Blygger](https://blygger.org/) protocol
(v0.3, conformance **L1 + blogroll, static**). Publisher + reader share only `blygger.core`;
the round-trip test is the conformance oracle.

## Run the tests

    python -m unittest discover -s tests -v

## Layout

- `blygger/core` — pure protocol logic (ids, hashing, models, markdown, transclusion,
  serialization, rollup/watermark/resolution). No I/O.
- `blygger/publish` — private all-versions store, studio ops, static-surface emitter.
- `blygger/read` — resolution, archive+watermark, reconciler, polling policy.
- `blygger/transport` — Transport ABC + filesystem and HTTP backends.

## Scope

L1 single-origin + optional blogroll, emitted as plain static files. L2 constructs
(cross-origin/partial transclusion, stubs, forks, generation disclosure, Webmention) and
L0 RSS grandfathering are deferred (see `docs/superpowers/specs/`).
```

- [ ] **Step 2: Run full suite one more time**

Run: `python -m unittest discover -s tests -v`
Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: project README"
git commit --allow-empty -m "checkpoint: phase 2 (reader + round-trip) complete"
```

---

## Self-Review Notes (for the executor)

- **Spec coverage:** ids (T1), content_hash (T2), timestamps (T3), models (T5),
  markdown (T6), transclusion baking incl. reserved `@vN` + inert-inline (T7), tolerant
  serialization incl. L2 carry-through (T8), rollup/watermark (T9), resolution ladder ≤6
  fetches + identity (T10), private all-versions store (T11), studio publish/edit/withdraw/
  pin/thread (T12), emitter incl. per-version GUIDs, latest-content descriptions, single
  withdrawn entry, additive pins, blogroll (T13), transports fs+http (T15,T16), archive +
  watermark (T17), feed parse (T18), resolve_subscription + site mismatch (T19), reconcile
  incl. index backfill, withdrawal, regression, stealth edit (T20), poll etiquette (T21),
  round-trip oracle fs+http (T22).
- **Deferred (by design, not gaps):** Webmention, cross-origin/partial transclusion emit,
  stubs, forks, generation authoring, L0 consumption, CommonMark completeness.
- **Type consistency:** `rules.FetchResult`/`Resolution` used by `read/resolve.py`;
  `Response.final_url` consumed by resolution identity; `Reconciler.reconcile(subscription)`
  consumes `Subscription.origin`/`.feed_url`/`.manifest.items`; `Archive` API
  (`put/get/watermark/bump_watermark/roll_to_null/known_ids`) consistent across T17/T20.
```
