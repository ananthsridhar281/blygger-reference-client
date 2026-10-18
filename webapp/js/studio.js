// Studio publish operations over the IndexedDB store (mirrors publish/studio.py).
// Async because hashing + transclusion baking + IndexedDB are async.
import { newId } from "./blyg/ids.js";
import { contentHash } from "./blyg/hash.js";
import { render } from "./blyg/markdown.js";
import { bake } from "./blyg/transclude.js";
import { PublishError } from "./blyg/errors.js";
import { nowIso } from "./blyg/timefmt.js";

// Resolver for thread baking: local published fragments/threads only (spec 10.2).
function makeResolver(store, publishingId) {
  return async (targetId) => {
    if (targetId === publishingId) throw new PublishError("thread cannot transclude itself");
    const rec = await store.getItem(targetId);
    if (!rec || !rec.versions.length) throw new PublishError(`unknown transclusion target ${targetId}`);
    const latest = rec.versions[rec.versions.length - 1];
    if (latest.kind === "withdrawn") throw new PublishError(`target ${targetId} is withdrawn`);
    return { version: latest.version, html: latest.content_html };
  };
}

async function nextVersion(store, id) {
  const rec = await store.getItem(id);
  return rec.versions.length ? rec.versions[rec.versions.length - 1].version + 1 : 1;
}

export async function publishFragment(store, md) {
  const id = newId();
  await store.createItem(id, "fragment", nowIso());
  await store.addVersion(id, {
    version: 1, at: nowIso(), kind: "fragment", note: null, content_md: md,
    content_html: render(md), content_hash: await contentHash(md), media: [],
  });
  return id;
}

export async function publishThread(store, md) {
  const id = newId();
  const { html, transclusions } = await bake(md, makeResolver(store, id));
  await store.createItem(id, "thread", nowIso());
  await store.addVersion(id, {
    version: 1, at: nowIso(), kind: "thread", note: null, content_md: md,
    content_html: html, content_hash: await contentHash(md), media: [], transclusions,
  });
  return id;
}

export async function editItem(store, id, md, note = null) {
  const rec = await store.getItem(id);
  if (!rec) throw new PublishError(`unknown item ${id}`);
  const kind = rec.authoredKind;
  const record = {
    version: await nextVersion(store, id), at: nowIso(), kind, note,
    content_md: md, content_hash: await contentHash(md), media: [],
  };
  if (kind === "thread") {
    const { html, transclusions } = await bake(md, makeResolver(store, id));
    record.content_html = html;
    record.transclusions = transclusions;
  } else {
    record.content_html = render(md);
  }
  await store.addVersion(id, record);
  return record.version;
}

export async function pinItem(store, id, version) {
  const rec = await store.getItem(id);
  if (!rec || !rec.versions.some((v) => v.version === version)) {
    throw new PublishError(`cannot pin unknown version ${id} v${version}`);
  }
  if (rec.versions.some((v) => v.version === version && v.kind === "withdrawn")) {
    throw new PublishError("withdrawal endcaps MUST NOT be pinned");
  }
  await store.setPinned(id, version);
}

export async function withdrawItem(store, id, note = null) {
  const rec = await store.getItem(id);
  if (!rec) throw new PublishError(`unknown item ${id}`);
  const record = {
    version: await nextVersion(store, id), at: nowIso(), kind: "withdrawn", note,
    content_md: "", content_html: "", content_hash: await contentHash(""), media: [],
  };
  if (rec.authoredKind === "thread") record.transclusions = [];
  await store.addVersion(id, record);
  return record.version;
}
