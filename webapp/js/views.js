// Pure HTML-string builders for the UI (no DOM, no I/O) — unit-testable.
// Untrusted item HTML renders in a sandboxed iframe (spec 14).
import { escapeHtml as esc } from "./blyg/markdown.js";

function badge(kind) {
  return `<span class="badge ${esc(kind)}">${esc(kind)}</span>`;
}

// ----------------------------------------------------------------- write ----
export function writeView(items, originUrl, fragmentIds) {
  const frags = fragmentIds.length
    ? `<p class="muted">Transcludable fragment ids: ${
        fragmentIds.map((i) => `<code>![[${esc(i)}]]</code>`).join(" ")}</p>`
    : "";
  const list = items.length
    ? items.map(writeItemCard).join("")
    : '<p class="muted">No items yet.</p>';
  return `
    <section class="card">
      <h3>Publish a fragment</h3>
      <textarea id="frag-text" placeholder="A short thought..."></textarea>
      <div class="row"><button data-action="publish-fragment">Publish fragment</button></div>
    </section>
    <section class="card">
      <h3>Publish a thread</h3>
      <textarea id="thread-text" placeholder="Intro...&#10;&#10;![[id]]&#10;&#10;more"></textarea>
      ${frags}
      <div class="row"><button data-action="publish-thread">Publish thread</button></div>
    </section>
    <section class="card">
      <h3>Items</h3>
      ${list}
    </section>
    <section class="card">
      <h3>Publish to GitHub</h3>
      <p class="muted">Emits the static blyg and commits it to
        <code>${esc(originUrl || "(set origin in Settings)")}</code>.</p>
      <div class="row"><button data-action="publish-site">Publish to GitHub</button></div>
    </section>`;
}

function writeItemCard(it) {
  let badges = badge(it.kind);
  for (const v of it.pinned_versions) badges += ` <span class="badge pinned">pin v${v}</span>`;
  const actions = it.withdrawn ? '<span class="tombstone">withdrawn</span>' : `
      <button class="small secondary" data-action="pin" data-id="${esc(it.id)}" data-version="${it.version}">Pin v${it.version}</button>
      <button class="small danger" data-action="withdraw" data-id="${esc(it.id)}">Withdraw</button>`;
  return `
    <div class="item">
      <div class="row"><code>${esc(it.id)}</code> ${badges} <span class="muted">v${it.version}</span></div>
      ${it.note ? `<div class="muted">note: ${esc(it.note)}</div>` : ""}
      ${it.md_snippet ? `<div>${esc(it.md_snippet)}</div>` : ""}
      <div class="row">${actions}</div>
    </div>`;
}

// ----------------------------------------------------------------- read ----
export function readView(result) {
  const form = `
    <section class="card">
      <div class="row">
        <input type="text" id="read-url" placeholder="https://example.com/blyg/" style="flex:1"
               value="${esc(result && result.inputUrl ? result.inputUrl : "")}">
        <button data-action="read-url">Read</button>
        <button class="secondary" data-action="read-local">Read my blyg</button>
      </div>
    </section>`;
  if (!result) {
    return form + '<p class="muted">Enter a blyg URL, or read the blyg you published.</p>';
  }
  if (result.error) {
    return form + `<div class="err">${esc(result.error)}<br><code>${esc(result.target || "")}</code></div>`;
  }
  const head = `
    <section class="card">
      <div><strong>${esc(result.title || "(untitled)")}</strong></div>
      <div><code>${esc(result.origin)}</code></div>
      <div class="muted">fetched ${result.fetched} document(s)</div>
    </section>`;
  const warns = (result.siteMismatch
    ? '<div class="warn">manifest <code>site</code> disagrees with the fetch origin — using the fetch origin.</div>'
    : "") + result.discrepancies.map((d) =>
      `<div class="warn"><strong>${esc(d.type)}</strong> <code>${esc(d.id)}</code> — ${esc(d.detail)}</div>`).join("");
  const items = result.items.length
    ? result.items.map(readItemCard).join("")
    : '<p class="muted">No items.</p>';
  return form + head + warns + items;
}

function sandboxSrcdoc(contentHtml) {
  const doc =
    '<!doctype html><meta charset="utf-8"><base target="_blank">' +
    "<style>body{font:14px/1.5 -apple-system,sans-serif;margin:8px;color:#1a1a1a}" +
    "blockquote.blyg-transclusion{border-left:3px solid #bbb;margin:0 0 8px;" +
    "padding:4px 0 4px 12px;color:#333}img{max-width:100%}</style>" + contentHtml;
  return esc(doc, true);
}

function readItemCard(it) {
  const head = `<div class="row"><code>${esc(it.id)}</code> ${badge(it.kind)} <span class="muted">v${it.version}</span></div>`;
  const inner = it.withdrawn
    ? '<div class="tombstone">withdrawn by the author</div>'
    : `<iframe class="content" sandbox srcdoc="${sandboxSrcdoc(it.content_html)}"></iframe>`;
  return `<div class="item">${head}${inner}</div>`;
}

// --------------------------------------------------------------- settings ----
export function settingsView(s) {
  const f = (id, label, value, type = "text", ph = "") =>
    `<label>${esc(label)}</label><input type="${type}" id="set-${id}" value="${esc(value || "")}" placeholder="${esc(ph)}">`;
  return `
    <section class="card">
      <h3>GitHub target</h3>
      ${f("owner", "Owner (user/org)", s.owner, "text", "ananthsridhar281")}
      ${f("repo", "Repo", s.repo, "text", "my-blyg")}
      ${f("branch", "Branch", s.branch, "text", "main")}
      ${f("basePath", "Base path in repo", s.basePath, "text", "(blank = repo root)")}
      ${f("pat", "Fine-grained PAT (contents: write)", s.pat, "password")}
      <p class="warn">Your token is stored in this browser's localStorage. Treat it as sensitive;
        scope it to just this repo.</p>
    </section>
    <section class="card">
      <h3>Blyg identity</h3>
      ${f("originUrl", "Public blyg URL (origin)", s.originUrl, "text", "https://ananthsridhar281.github.io/my-blyg/")}
      ${f("title", "Title", s.title)}
      ${f("authorName", "Author name", s.authorName)}
    </section>
    <section class="card">
      <div class="row">
        <button data-action="save-settings">Save</button>
        <button class="secondary" data-action="test-connection">Test connection</button>
      </div>
    </section>`;
}
