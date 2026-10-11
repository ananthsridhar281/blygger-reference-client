# Blygger Reference Client — Design

- **Date:** 2026-10-11
- **Status:** Approved design, pre-implementation
- **Target protocol:** Blygger v0.3 (living draft), implementation pinned to the **2026-09-28** dated snapshot (`https://blygger.org/spec/0.3/2026-09-28/`) for build stability.
- **Language/runtime:** Python 3.11+, **standard library only**.

## 1. Purpose & Scope

Build a **round-trip reference client** for the Blygger protocol — a publisher and a
reader that share only the protocol core, so a green round-trip proves the *protocol*
(not shared plumbing) carries state. The project is explicitly phased:

1. **Conformance core (this spec):** a clean, correct, readable implementation that
   exercises every relevant MUST/SHOULD, with a test suite that acts as a conformance
   oracle. Correctness and clarity beat polish.
2. **Usable-tool glue (later):** CLI + hosting ergonomics so the author can publish a
   real blyg and subscribe to live nodes. Out of scope here.

### Conformance scope

Target spec version is **0.3**, but the implemented behavior is **L1 (single-origin)
+ blogroll, purely static**.

- **Publisher emits only L1 constructs:** fragments, threads with *same-origin*
  transclusion, pins, withdrawal, manifest, archive index, RSS feed, and an optional
  OPML blogroll. Manifest advertises `"level": 1`. Documents carry `"blyg": "0.3"`.
- **Reader is a 0.3 L1 reader** that must *tolerate* L2 inbound (per §13.1): it
  recognizes and preserves known-0.3 L2 fields (`forked_from`, `stub_of`,
  `transclusions[].origin`, `generated`, `cited`, `page`) but does not act on them,
  driving rollup purely off `id`/`version`/`content_hash`. The one L2-era field honored
  at L1 is **`page`** (SHOULD use when present; else fall back to the `f/{id}/` /
  `t/{id}/` convention), because it makes feed `<link>`s correct and is cheap.

### Explicitly deferred (not in the conformance core)

- All L2 **emission**: cross-origin transclusion (`data-blyg-origin`), partial
  transclusion (`blyg-partial`, `selector`), stubs (`stub_of`), forks (`forked_from`),
  generation disclosure authoring, `cited` labels.
- **Webmention (§15)** entirely — sender and receiver. It is the protocol's only
  dynamic (non-static) surface; deferring it keeps the core purely static.
- **L0 grandfathering** (reader-side wrapping of arbitrary RSS/Atom). Resolution still
  *recognizes* and reports an L0 fallback, but does not consume it.

## 2. Key Decisions (captured from brainstorming)

| Decision | Choice | Rationale |
|---|---|---|
| Primary purpose | Conformance core first, usable glue later | The round-trip test *is* the conformance oracle |
| Sides | Both publisher + reader (round-trip) | Self-validating; proves interop via `core` only |
| Language | Python 3.11+ | Matches existing tooling |
| Dependencies | **Pure stdlib** | Self-contained, auditable reference; protocol logic hand-written |
| Markdown | Documented **minimal subset**, reference-grade (not CommonMark-complete) | Rolling a full CommonMark engine is a distraction from protocol conformance |
| Transport | Abstraction with **HTTP + filesystem** backends | Fast socket-free unit tests *and* a real-HTTP integration proof |
| Spec version | 0.3 living draft, pinned to 2026-09-28 snapshot | User asked for latest; snapshot holds text still while building |
| Conformance | 0.3 **L1 + blogroll, static**; tolerate L2 inbound | Smallest correct core; L2/Webmention are later glue |
| Emit semantics | Idempotent + additive; never delete an existing pin (error instead) | Honors the irrevocable-pin promise across runs |

### Minimal-markdown subset (reference-grade)

Supported: paragraphs, emphasis (`*`/`_`), inline code, fenced code blocks, blockquotes,
links, images, and the Blygger transclusion directive. Explicitly **not** full
CommonMark; documented as such. Protocol-critical constructs — the line-only `![[id]]`
transclusion directive, inert-in-code behavior, and the baked `blyg-transclusion` HTML
wrapper — get first-class, exact treatment regardless of the renderer's general limits.

## 3. Architecture

A single `blygger` package, three internal layers that reach across only through `core`.

```
blygger/
  core/              # pure protocol logic — NO I/O. The "reference" artifact.
    ids.py           #   128-bit id gen + validation (Crockford base32, 26 chars)
    hashing.py       #   content_hash = "sha256:" + hex(sha256(content_md utf-8))
    model.py         #   dataclasses: Manifest, Item, ChangelogEntry, Media,
                     #     Author, Transclusion, Generated, IndexEntry
    markdown.py      #   minimal-subset md->html; transclusion directive tokenizer
    transclude.py    #   bake(md, resolver) -> (html, transclusions[]) at publish time
    rules.py         #   pure spec rules: rollup(), watermark_check(),
                     #     resolve(url, fetch)  <- §12 ladder, fetch injected
    serialize.py     #   model<->dict, wire-JSON parse w/ ignore-unknown-members
    timefmt.py       #   ISO-8601 (protocol) + RFC-822 (RSS) helpers
  publish/
    store.py         #   PRIVATE canonical store — retains ALL versions (history
                     #     withheld from the wire; needed for retroactive pinning)
    studio.py        #   ops: publish_fragment, publish_thread, edit, pin, withdraw
    emit.py          #   render the public static surface to an output dir (atomic)
  read/
    resolve.py       #   wires transport into core.rules.resolve
    archive.py       #   origin-scoped local store + monotonic watermark
    reconcile.py     #   §13: feed trigger -> fetch item -> rollup; index backfill
    poll.py          #   etiquette: conditional GET, backoff, Retry-After
  transport/
    base.py          #   Transport ABC (get -> status, headers, body, final_url)
    http.py          #   HttpTransport (urllib): etag/if-modified-since, redirects, 304
    fs.py            #   FsTransport: maps an origin URL -> local output dir
  cli.py             #   thin glue — stubbed in core phase, fleshed out in phase 2
tests/
  ...                #   unit tests per module + the round-trip conformance oracle
```

### Load-bearing rules

- **`core` imports nothing from `publish`/`read`/`transport` and does no I/O.**
  Resolution's §12 ladder lives here as `resolve(url, fetch)` with `fetch` injected, so
  it is testable without sockets.
- **`publish` and `read` share only `core`** — proving the protocol, not shared
  plumbing, carries the round-trip.
- **The publisher keeps two separate things:** a *private* canonical store (every
  version, including withheld history) and the *public* emitted surface. Retroactive
  pinning promotes a withheld version from the private store into a public `v{n}.json`.

### Design philosophy: tolerant inbound, strict outbound

`serialize.parse_*` never rejects a document over unknown kinds/members/`blyg:*`
elements (§13.4); unknowns are stashed in `extra`. Publish-side studio/emit enforce every
MUST at construction/publish time.

## 4. Core domain model & pure rules

### Data model (`model.py`, frozen dataclasses)

- `Author(name: str|None, url: str|None, extra: dict)` — carried verbatim, never synthesized.
- `Media(url, mime, alt)` — immutable once published.
- `ChangelogEntry(version, at, note, pinned=False, generated=False)`.
- `Transclusion(id, version, origin=None, selector=None)` — `origin`/`selector` parsed
  but not emitted at L1.
- `Generated(sources, model, at)` — parsed, not emitted at L1.
- `Item(blyg, id, kind, origin, author, created, updated, version, content_md,
  content_html, content_hash, media, changelog, page=None, transclusions=None,
  generated=None, forked_from=None, stub_of=None, extra=dict)`.
  `kind ∈ {fragment, thread, withdrawn}`; `transclusions` present only for threads.
- `Manifest(blyg, level, generator, generator_url, site, title, author, feed, items,
  blogroll=None, webmention=None, updated)`.
- `IndexEntry(id, kind, created, updated, version)`.

### Pure rules (`rules.py`, side-effect-free)

- `rollup(local, fetched) -> ItemState` — highest `version` wins; ties broken by
  `updated`; `withdrawn` endcap rolls to null.
- `watermark_check(watermark, fetched) -> Verdict` — `OK` / `REGRESSION` (version <
  watermark; surface, do not adopt) / `STEALTH_EDIT` (same version, different
  `content_hash`; content wins, record discrepancy, watermark unchanged).
- `resolve(url, fetch) -> Resolution` — §12 ladder (normalize → direct `blyg.json`
  probe → feed `blyg:manifest` upgrade → HTML `rel="blyg"` one hop → conventional-mount
  probes → RSS fallback), **≤6 fetches**, `fetch` injected. Identity = final fetch
  origin, never the manifest's `site`.
- `bake_transclusions(md, resolver) -> (html, [Transclusion])` — parses line-only
  `![[id]]` directives, rejects reserved `![[id@vN]]` and invalid targets, snapshots the
  target's latest version into
  `<blockquote class="blyg-transclusion" data-blyg-id data-blyg-version>`.
- `content_hash(content_md) -> str`; id generation/validation.

Both `resolve()` and `rollup()` take injected callables / plain data, so the entire
§12 + §13 logic is unit-testable with zero network and zero disk.

## 5. Publisher

### `store.py` — private canonical store

The full state plane: every version of every item, including history withheld from the
wire. Plain JSON on disk (auditable; `sqlite3` is available but files match the
"files you own" ethos).

```
<private>/
  manifest.json              # author masthead, title, site, generator
  items/{id}.json            # { authored_kind, created, versions: [ {version, at,
                             #     note, pinned, kind, content_md, content_html,
                             #     content_hash, media, transclusions?} ] }
  blogroll.json              # list of {text, xmlUrl, htmlUrl}
```

Nothing here is served directly; `emit.py` derives the public surface from it.

### `studio.py` — publish operations (enforce MUSTs)

- `publish_fragment(md, author=None)` → new id, version 1.
- `publish_thread(md, author=None)` → resolves `![[id]]` against currently-published
  *local* fragments/threads via `core.bake_transclusions`; drafts/withdrawn/unknown
  targets are publish errors; stores baked `content_html` + `transclusions`. (One local
  closure check: a thread MUST NOT transclude a local thread whose transitive local
  closure contains the publishing thread's own id.)
- `edit(id, md, note=None)` → version +1, append changelog, recompute hash; threads
  re-bake transclusions to fresh snapshots.
- `pin(id, version)` → sets `pinned=True`; retroactive pinning promotes a withheld
  version to public; emits **no** feed event.
- `withdraw(id, note=None)` → terminal endcap: version +1, `kind="withdrawn"`, empty
  `content_md`/`content_html`/`media`, `transclusions=[]` for threads, full changelog
  retained, keeps `page`. Reversible by a later publish/edit under the same id.

Invariants asserted on every op: version increments by exactly 1; `updated` equals the
latest changelog `at`; ids immutable across versions.

### `emit.py` — render the public static surface

- `blyg.json` — manifest; `blogroll` key present only if non-empty; `"level": 1`.
- `items/{id}.json` — **latest version only**; `transclusions` present only for threads;
  `page` emitted.
- `items/{id}/v{n}.json` — one file per **pinned** version; additive, never deleted.
- `items/index.json` — **complete**, every item, ordered by `updated` desc.
- `feed.xml` — one `<item>` per publish event, newest first, windowed (default 50);
  per-version `guid` `blyg:{id}:v{n}` (`isPermaLink="false"`); `<description>` always
  carries the **latest** version's self-contained HTML (absolute media URLs) even when
  the entry announces an older event; withdrawn item contributes exactly one `withdrawn`
  entry (earlier events dropped); pinning emits nothing; `<blyg:manifest>` mandatory;
  `pubDate`/`lastBuildDate` in RFC 822, `blyg:*` timestamps in ISO 8601.
- `blogroll.opml` — OPML 2.0, `type="rss"` outlines.

**Atomic + idempotent + additive:** emit writes to a temp location and swaps; re-emitting
reproduces the current public surface and **never removes an already-published pin
file** — it detects a would-be pin deletion and errors rather than break the
irrevocable-pin promise.

## 6. Reader

### `resolve.py` — §12 resolution

Wires a `Transport` into `core.rules.resolve`. Returns a `Subscription` whose identity is
the **final fetch origin minus `blyg.json`** (after ≤5 redirects), never the manifest's
`site`; a disagreement is surfaced, not adopted. L0 fallback is recognized and reported
but not consumed.

### `archive.py` — origin-scoped store + watermark

Everything scoped to `(origin, id)`. Per imported item: current rolled-up state (or null
if withdrawn), `content_hash`, and the **monotonic watermark**. Plain JSON on disk.

### `reconcile.py` — §13 import logic

- **Feed is a trigger, never state.** An interesting feed entry (including `withdrawn`)
  triggers an `items/{id}.json` fetch; only the fetched document advances state via
  `rollup`.
- **Index is the reconciliation surface.** `items/index.json` is complete by
  construction; a diff against local state recovers any missed window losslessly.
  Reconcile on first subscribe, on any detected gap, and periodically.
- **Watermark enforcement** via `watermark_check`: regression is not silently adopted
  (surface; user-confirmed reset only); stealth edit adopts content but records +
  surfaces a discrepancy; watermark unchanged.
- **`content_hash` verification** on import — mismatch is a logged discrepancy, not a
  hard reject.
- **Withdrawal** rolls to null and drops the stored copy, except content backed by a
  pinned version (MAY retain with attribution linking the pin).
- **Degrade, don't corrupt:** unparseable feed → index diff; unparseable entry → skip
  that entry; poll failures never mutate stored state.
- **Ordering across origins** is reader policy: default key
  `min(claimed updated, first-observed-locally)`.
- **L2 tolerance:** L2 fields on fetched documents are preserved but not acted on;
  rollup is driven purely off `id`/`version`/`content_hash`.

### `poll.py` — etiquette

Lives above transport. Owns conditional requests (honor `304`), exponential backoff on
failure, honoring `Retry-After` on `429`/`503`, never tightening the interval on failure,
never discarding state on a failed poll.

## 7. Transport

```python
class Transport(ABC):
    def get(self, url, *, etag=None, last_modified=None) -> Response: ...
# Response: status, headers (dict), body (bytes), final_url (after redirects)
```

- `final_url` is load-bearing for resolution identity (§12.2) and redirect following.
- `http.py` — `HttpTransport` (urllib): sets `If-None-Match`/`If-Modified-Since`,
  surfaces `304`, follows bounded redirects (≤5) tracking `final_url`, sends an
  identifying `User-Agent` from `generator`, applies §14 fetch hygiene (bounded
  redirects, response size cap, timeout). A clearly-marked seam is left for
  private-network blocking (a deferred §15 concern).
- `fs.py` — `FsTransport`: maps an origin URL to the publisher's output dir; `200` for
  present files, `404` for missing; implements conditional requests via hash/mtime so
  `304` paths are exercised.

Policy (etiquette) stays in `poll.py`, not the transport, so the same `reconcile.py` runs
identically over both backends.

## 8. Error handling

### Publish side — fail loud, fail early

`PublishError` on: unresolvable `![[id]]`, directive to a draft/withdrawn/unknown/invalid
target, reserved `![[id@vN]]`, version not incrementing by exactly 1, `updated` ≠ latest
changelog `at`, would-be deletion of an existing pin. Emit is atomic — a failed emit never
leaves a torn surface.

### Read side — degrade, never corrupt

The reconciler never throws on bad remote data; it records a first-class, inspectable
`Discrepancy(type, origin, id, detail)` and continues. Unparseable feed → index diff;
unparseable entry/item → skip; `content_hash` mismatch / stealth edit / version
regression → discrepancy (+ §13.3 behavior); transport/poll failure → no state mutation;
unknown/L2 constructs → preserved or ignored, never reject the document. Surfacing
history-rewrites and stealth edits loudly is a protocol requirement; tests assert on them.

## 9. Testing & the conformance oracle

1. **Pure-rule unit tests (`core`)** — zero I/O: id format/uniqueness, `content_hash`
   vectors, markdown-subset rendering, transclusion tokenizer (directive vs inert-in-code
   vs reserved `@vN`), `bake_transclusions` bytes, `rollup`, `watermark_check`
   (OK/regression/stealth), `resolve` over a stub `fetch` exercising all six ladder rungs
   + redirect identity.
2. **Publisher golden-file tests** — a scripted history (publish → edit → pin → withdraw
   → return → thread transcluding a fragment) through studio + emit, byte-compared to
   committed golden files. These double as human-readable reference fixtures of a
   conformant 0.3-L1 blyg.
3. **Reader tests over `FsTransport`** — reconcile against the golden fixtures; assert
   rolled-up state, watermark, discrepancies. Adversarial fixtures: missing feed window
   (index backfill), 404 index (lossy fallback), stealth edit, version regression,
   withdrawal-with-retained-pin, and an L2-laden inbound document (tolerated).
4. **Round-trip conformance oracle** — studio publishes a history → emit writes a dir → a
   stdlib `http.server` serves it → the reader resolves the URL from scratch, subscribes,
   reconciles; final reader state asserted equal to the publisher's public truth. Run
   twice: `FsTransport` (fast) and real `HttpTransport` (proves probing/`304`/redirects).
   Publisher and reader share only `core`.
5. **`unittest` + stdlib only**, no pytest.

## 10. Out of scope (future phases)

- Usable-tool glue: full CLI (publish/subscribe commands), hosting ergonomics, real
  deployment, subscribing to live nodes.
- L2 emission: cross-origin + partial transclusion, stubs, forks, generation disclosure
  authoring, `cited` labels.
- Webmention (§15): sender, receiver endpoint, structural verification, per-item curation.
- L0 grandfathering (consuming arbitrary RSS/Atom).
- CommonMark-complete markdown.
