# Blygger Web App (GitHub Pages) — Design

- **Date:** 2026-10-17
- **Status:** Approved design, pre-implementation
- **Relation:** Browser-native companion to the Python reference client in this repo. A
  second, independent **conforming client** (publisher + reader) implemented in JavaScript.
- **Target protocol:** Blygger v0.3, conformance **L1 + blogroll** (same scope as the
  Python client). Reader tolerates L2 inbound but does not act on it.

## 1. Purpose & Success Criteria

A simple **reading + writing space** that runs entirely in the browser, hosted on GitHub
Pages with **no backend**. The user writes fragments/threads and **publishes straight to
GitHub** (the generated static blyg is committed to a repo they own and served via GitHub
Pages). The same app reads blygs (their own and others') and renders them.

Success = from `ananthsridhar281.github.io/blygger-reference-client/` the user can: write a
fragment/thread, click Publish, and see it live as a static blyg on GitHub Pages; and enter
a blyg URL (or "my blyg") and read it rendered.

## 2. Key Decisions (from brainstorming)

| Decision | Choice | Rationale |
|---|---|---|
| Hosting | GitHub Pages, static only | User requirement; no server |
| Writing model | **Publish straight to GitHub** | User choice (option B) |
| Auth | **Fine-grained PAT**, pasted, stored in browser | Only backendless path on pure Pages |
| Implementation | **Native JS port** (no Pyodide) | Lean, instant load, offline; = 2nd reference client |
| Tooling | **Vanilla JS, ES modules, no build step, no npm** | Matches project's zero-dependency ethos |
| Tests | **`node:test`** (built-in, zero-dep) over pure modules | Node 22 present; no external deps |
| App location | `webapp/` in this repo, deployed to Pages via Actions | One home; source == tested |

### CORS note
The app (`ananthsridhar281.github.io/blygger-reference-client/`) and the user's published
blyg (e.g. `ananthsridhar281.github.io/<blyg-repo>/`) share host `ananthsridhar281.github.io`
→ **same-origin**, so reading one's own blyg has no CORS issue. Reading arbitrary external
blygs is subject to the remote origin's CORS headers (spec SHOULD: `Access-Control-Allow-Origin: *`).

## 3. Architecture

Static SPA, no framework, loaded as ES modules. Three tabs: **Write**, **Read**, **Settings**.

```
webapp/
  index.html            # shell: tabs, mount points, loads js/app.js as a module
  css/app.css           # plain CSS (ported look from the Python UI)
  js/
    app.js              # UI controller: tabs, forms, event wiring, rendering
    views.js            # pure DOM-string builders (testable; mirrors web/views.py)
    store.js            # IndexedDB private all-versions store (async)
    github.js           # GitHub Git Data API client (atomic multi-file commit)
    settings.js         # localStorage-backed settings (repo, branch, path, PAT, origin)
    reader.js           # fetch-based transport + drives resolve + reconcile for reading
    blyg/               # the protocol port (pure, no DOM, no network)
      ids.js            #   newId() via crypto.getRandomValues -> 26-char Crockford base32
      hash.js           #   contentHash(md) via crypto.subtle SHA-256 -> "sha256:"+hex (async)
      markdown.js       #   minimal-subset md -> html (port of markdown.py)
      transclude.js     #   bake(md, resolver) -> {html, transclusions} (async-safe)
      serialize.js      #   item/manifest/index <-> plain objects (tolerant parse)
      emit.js           #   emit(store-snapshot) -> { "path": "contents" } map (async)
      rules.js          #   rollup, watermarkCheck, resolve ladder (fetch injected)
      reconcile.js      #   feed trigger + index diff -> rollup; discrepancies
  .nojekyll             # so Pages serves files verbatim
tests-js/
  *.test.mjs            # node:test over js/blyg/* and views.js (pure logic)
.github/workflows/
  pages.yml             # deploy webapp/ to GitHub Pages
```

**Boundaries:** `js/blyg/` is pure (no DOM, no network, no IndexedDB) — the only part that
must exactly track the protocol, and the part that is unit-tested. `store.js`, `github.js`,
`reader.js`, `app.js` are the impure shells. `views.js` is pure string-building.

### Async ripple
`crypto.subtle.digest` is async, so `contentHash`, `emit`, and the studio operations are
`async`. All call sites use `await`. This is expected and contained.

## 4. Protocol Port (`js/blyg/`)

Faithful port of the Python `core` + publish/emit + read logic. Behavior parity is the
goal; permanent wire tokens are identical (`blyg-transclusion`, GUID `blyg:{id}:v{n}`,
namespace `https://blygger.org/ns/0.1`, etc.).

- **ids.js** — 16 random bytes → 26 chars of `0123456789abcdefghjkmnpqrstvwxyz`; `isValidId`.
- **hash.js** — `"sha256:" + hex(SHA-256(utf8(md)))` via SubtleCrypto (async).
- **markdown.js** — paragraphs, emphasis, inline code, fenced code, blockquotes, links,
  images; HTML-escaped; reference-grade (not CommonMark-complete).
- **transclude.js** — line-only `![[id]]` directive → `<blockquote class="blyg-transclusion"
  data-blyg-id data-blyg-version>…</blockquote>`; reject reserved `![[id@vN]]`; inert inline.
- **serialize.js** — item→public object (latest only; `transclusions` only for threads;
  `page`; no L2 keys); tolerant parse (unknown keys preserved, L2 keys recognized).
- **emit.js** — build `blyg.json`, `items/{id}.json`, `items/{id}/v{n}.json` (pinned),
  `items/index.json`, `feed.xml`, `blogroll.opml` as a path→string map; additive pins
  (never drop a pin); `"level": 1`.
- **rules.js** — `rollup`, `watermarkCheck` (OK/REGRESSION/STEALTH_EDIT), `resolve(url, fetch)`
  ≤6-fetch ladder, identity = final fetch origin.
- **reconcile.js** — feed trigger → fetch item → rollup; index backfill; content_hash
  self-consistency (§13.3); withdrawal → null; discrepancies collected, never thrown.

## 5. Private Store (`store.js`, IndexedDB)

Mirrors the Python private store: one record per item `{ authoredKind, created, versions:[…]
}` holding every version (content_md/html/hash, media, note, pinned, transclusions), plus
manifest meta and optional blogroll. Async API: `createItem`, `addVersion`, `getItem`,
`setPinned`, `allItemIds`, `setManifestMeta`, `getManifestMeta`, `setBlogroll`, `getBlogroll`.

**Cross-device caveat:** the store is per-browser. On a fresh browser the app offers to
**rebuild current state from the published blyg** (fetch index + item docs → seed versions
at their latest), enough to continue editing (next version = latest+1). Withheld pre-publish
history does not travel; retroactive pinning of never-published versions is unavailable
cross-device. This limitation is shown in the UI.

## 6. Publishing (`github.js`)

On Publish: `emit` produces the file map, then an **atomic commit** via the GitHub Git Data
API against the configured target:
1. `GET` current branch ref → base commit → base tree SHA.
2. Create a blob per file (`POST /git/blobs`, base64).
3. Create a tree (`POST /git/trees`, `base_tree` = current) with all paths under the
   configured base path.
4. Create a commit (`POST /git/commits`) with the new tree + parent.
5. Update the ref (`PATCH /git/refs/heads/{branch}`).

Settings: `owner`, `repo`, `branch` (default `main`), `basePath` (default `""`), `pat`,
`originUrl` (the blyg's public URL, stamped into emitted files + used by "read my blyg").
On `409`/stale-ref, surface a "remote changed, retry" message. The PAT is sent only to
`api.github.com` over HTTPS.

## 7. Reading (`reader.js`)

`fetchTransport` wraps `fetch` into the `resolve(url, fetch)` callable + document fetches,
returning `{status, body, finalUrl}` (final URL from `response.url` for identity). Drives
`resolve` then `reconcile`; renders feed newest-first. Each item's `content_html` renders in
`<iframe sandbox srcdoc="…escaped…">` (no `allow-scripts`). "Read my blyg" uses the settings
`originUrl`. External URLs work when the remote sends permissive CORS; failures render a
plain-English explanation (likely CORS or offline).

## 8. UI (`app.js`, `views.js`)

- **Write tab:** forms for fragment/thread (with a transcludable-id helper), a list of store
  items with Pin/Withdraw actions, and a **Publish to GitHub** button (shows commit progress
  + resulting commit URL).
- **Read tab:** URL box + "Read my blyg"; renders feed, badges, tombstones, discrepancy banners.
- **Settings tab:** GitHub target + PAT + origin URL, with validation ("Test connection"
  calls `GET /repos/{owner}/{repo}` and reports access). Sensitive-token warning shown.
- `views.js` builds HTML strings (pure, unit-tested for escaping/structure); `app.js` wires
  events and talks to the shells.

## 9. Error Handling

- **Publish-time** (`transclude`/studio): bad `![[id]]`, reserved form, invalid version step
  → thrown as a typed error, caught by `app.js`, shown inline; nothing committed.
- **GitHub**: 401/403 (bad/insufficient token), 404 (wrong repo/branch), 409 (stale ref) →
  specific messages; partial failure never updates the ref (ref update is the last step).
- **Reader**: unparseable feed → index diff; unparseable item/entry → skip; fetch/CORS error
  → explained; discrepancies → banners (not fatal).
- Untrusted HTML always sandboxed before render.

## 10. Testing

- `node:test` + `node:assert` (built-in) over `js/blyg/*` and `views.js`:
  ids format/uniqueness, hash vectors (matching the Python `content_hash`), markdown subset,
  transclusion baking incl. reserved/inert, serialize round-trip + tolerant parse, emit
  output shape (paths + feed GUIDs + single withdrawn entry + additive pins), rollup/
  watermark, resolve ladder over a stub fetch, reconcile round-trip over an in-memory stub
  transport (emit map → stub → reconcile → assert state), and views escaping (sandbox attr,
  no `allow-scripts`).
- **Cross-implementation check:** a test asserts the JS `contentHash` of a known string
  equals the value the Python client produces (hard-coded vector), guarding against drift.
- `store.js` (IndexedDB), `github.js` (network), and DOM wiring are covered by a documented
  **manual smoke test** (publish → see commit → read-my-blyg renders), since they need a
  browser/network.
- Run: `node --test tests-js/`.

## 11. Deployment (`.github/workflows/pages.yml`)

A GitHub Actions workflow publishes `webapp/` to GitHub Pages on push to `main`
(`actions/upload-pages-artifact` + `actions/deploy-pages`). `.nojekyll` ensures files serve
verbatim. App goes live at `ananthsridhar281.github.io/blygger-reference-client/`. (Pages
"source: GitHub Actions" enabled once in repo settings — a manual one-time step, noted in
the README.)

## 12. Out of Scope (v1)

OAuth / "Login with GitHub"; cross-device private-history sync beyond rebuild-from-published;
L2 authoring (cross-origin/partial transclusion, stubs, forks, generation disclosure);
Webmention; L0 RSS reading; auto-creating/enabling Pages on the target blyg repo (user does
that once manually); CommonMark-complete markdown.
