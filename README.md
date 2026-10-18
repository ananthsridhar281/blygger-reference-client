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

## Browser web app (`webapp/`)

A second, independent conforming client — a **read + write space that runs entirely in the
browser**, hosted on GitHub Pages with no backend. It ports the protocol to vanilla JS
(no framework, no build step) and publishes straight to GitHub.

- **Write:** compose fragments/threads (with `![[id]]` transclusion), pin, withdraw. The
  private all-versions history lives in IndexedDB.
- **Publish:** emits the static blyg and commits it atomically to a repo you configure,
  via the GitHub Git Data API using a fine-grained Personal Access Token.
- **Read:** resolve + reconcile any blyg URL (or your own), rendering untrusted
  `content_html` in a sandboxed `<iframe>`.

Run the JS tests (Node 18+, zero dependencies):

    node --test tests-js/*.test.mjs

### Deploying / using it

1. In this repo's **Settings → Pages**, set the source to **GitHub Actions** (one-time).
   Pushing `webapp/**` then deploys via `.github/workflows/pages.yml` to
   `https://<you>.github.io/blygger-reference-client/`.
2. Create a separate repo to hold your blyg and enable Pages on it.
3. Create a fine-grained PAT (that repo, `Contents: write`), open the app, fill in
   **Settings**, write, and click **Publish to GitHub**.
