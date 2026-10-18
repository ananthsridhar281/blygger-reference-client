// UI controller: tabs, event delegation, wiring the shells together.
import { Store } from "./store.js";
import { loadSettings, saveSettings, settingsComplete } from "./settings.js";
import { publishFragment, publishThread, pinItem, withdrawItem } from "./studio.js";
import { emit } from "./blyg/emit.js";
import { nowIso } from "./blyg/timefmt.js";
import { commitFiles, testConnection } from "./github.js";
import { readBlyg } from "./reader.js";
import { writeView, readView, settingsView } from "./views.js";

const store = new Store();
let tab = "write";
let lastRead = null;

const $view = () => document.getElementById("view");
const $flash = () => document.getElementById("flash");

function flash(msg, kind = "ok") {
  const el = $flash();
  el.className = kind;
  el.textContent = msg;
  el.hidden = !msg;
}

async function studioItems() {
  const recs = await store.allItems();
  return recs.filter((r) => r.versions.length).map((r) => {
    const latest = r.versions[r.versions.length - 1];
    return {
      id: r.id, kind: latest.kind, version: latest.version, note: latest.note,
      pinned_versions: r.versions.filter((v) => v.pinned).map((v) => v.version),
      withdrawn: latest.kind === "withdrawn",
      md_snippet: (latest.content_md || "").split(/\s+/).filter(Boolean).join(" ").slice(0, 80),
      at: latest.at,
    };
  }).sort((a, b) => (b.at || "").localeCompare(a.at || ""));
}

async function render() {
  for (const a of document.querySelectorAll("nav a")) {
    a.classList.toggle("active", a.dataset.tab === tab);
  }
  const s = loadSettings();
  if (tab === "write") {
    const items = await studioItems();
    const fragIds = items.filter((i) => i.kind === "fragment" && !i.withdrawn).map((i) => i.id);
    $view().innerHTML = writeView(items, s.originUrl, fragIds);
  } else if (tab === "read") {
    $view().innerHTML = readView(lastRead);
  } else {
    $view().innerHTML = settingsView(s);
  }
}

async function publishSite() {
  const s = loadSettings();
  if (!settingsComplete(s)) {
    flash("Fill in GitHub owner/repo/PAT and the blyg origin URL in Settings first.", "err");
    tab = "settings"; await render(); return;
  }
  flash("Emitting and committing…", "ok");
  await store.setManifestMeta({
    title: s.title, site: s.originUrl,
    author: s.authorName ? { name: s.authorName } : null,
  });
  const files = emit(await store.snapshot(),
    { origin: s.originUrl, generator: "blygger-web/0.1", updated: nowIso() });
  try {
    const { commitUrl } = await commitFiles(files, s, "Publish blyg via blygger-web");
    const el = $flash();
    el.className = "ok";
    el.innerHTML = `Published. <a href="${commitUrl}" target="_blank" rel="noopener">View commit</a>`;
    el.hidden = false;
  } catch (e) {
    flash(String(e.message || e), "err");
  }
}

async function onClick(ev) {
  const tabLink = ev.target.closest("[data-tab]");
  if (tabLink) { ev.preventDefault(); tab = tabLink.dataset.tab; flash(""); await render(); return; }

  const el = ev.target.closest("[data-action]");
  if (!el) return;
  const action = el.dataset.action;
  try {
    if (action === "publish-fragment") {
      const md = document.getElementById("frag-text").value.trim();
      if (!md) return flash("Nothing to publish.", "err");
      await publishFragment(store, md);
      flash("Fragment published (not yet pushed — hit Publish to GitHub).");
      await render();
    } else if (action === "publish-thread") {
      const md = document.getElementById("thread-text").value.trim();
      if (!md) return flash("Nothing to publish.", "err");
      await publishThread(store, md);
      flash("Thread published (not yet pushed — hit Publish to GitHub).");
      await render();
    } else if (action === "pin") {
      await pinItem(store, el.dataset.id, Number(el.dataset.version));
      flash("Pinned."); await render();
    } else if (action === "withdraw") {
      await withdrawItem(store, el.dataset.id);
      flash("Withdrawn."); await render();
    } else if (action === "publish-site") {
      await publishSite();
    } else if (action === "read-url") {
      const url = document.getElementById("read-url").value.trim();
      flash("Reading…");
      lastRead = { ...(await readBlyg({ url })), inputUrl: url };
      flash(""); await render();
    } else if (action === "read-local") {
      const s = loadSettings();
      if (!s.originUrl) return flash("Set your blyg origin URL in Settings first.", "err");
      flash("Reading your blyg…");
      lastRead = { ...(await readBlyg({ local: true, originUrl: s.originUrl })), inputUrl: "" };
      flash(""); await render();
    } else if (action === "save-settings") {
      saveSettings({
        owner: val("set-owner"), repo: val("set-repo"), branch: val("set-branch") || "main",
        basePath: val("set-basePath"), pat: val("set-pat"), originUrl: val("set-originUrl"),
        title: val("set-title"), authorName: val("set-authorName"),
      });
      flash("Settings saved.");
    } else if (action === "test-connection") {
      const s = loadSettings();
      flash("Testing…");
      const info = await testConnection(s);
      flash(`Connected to ${info.fullName} (default branch ${info.defaultBranch}).`);
    }
  } catch (e) {
    flash(String(e.message || e), "err");
  }
}

function val(id) { return document.getElementById(id).value.trim(); }

document.addEventListener("click", onClick);
render();
