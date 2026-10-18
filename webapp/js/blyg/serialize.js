// Tolerant parsing of fetched wire JSON/XML into plain objects (spec 5, 6, 7, 13.1).
// The reader only needs to parse; emit.js builds public objects itself.

export function parseItem(d) {
  // Returns a normalized item object; unknown members are ignored for L1 behavior.
  return {
    blyg: d.blyg || "",
    id: d.id,
    kind: d.kind || "",
    origin: d.origin || "",
    author: d.author || null,
    created: d.created || "",
    updated: d.updated || "",
    version: Number(d.version || 0),
    content_md: d.content_md || "",
    content_html: d.content_html || "",
    content_hash: d.content_hash || "",
    media: Array.isArray(d.media) ? d.media : [],
    changelog: Array.isArray(d.changelog) ? d.changelog : [],
    page: d.page || null,
    transclusions: Array.isArray(d.transclusions) ? d.transclusions : null,
  };
}

export function parseManifest(d) {
  return {
    blyg: d.blyg || "",
    level: Number(d.level || 0),
    generator: d.generator || "",
    site: d.site || "",
    title: d.title || "",
    author: d.author || null,
    feed: d.feed || "feed.xml",
    items: d.items || "items/index.json",
    blogroll: d.blogroll || null,
    webmention: d.webmention || null,
    updated: d.updated || "",
  };
}

export function parseIndex(d) {
  const entries = (Array.isArray(d.items) ? d.items : []).map((e) => ({
    id: e.id,
    kind: e.kind || "",
    created: e.created || "",
    updated: e.updated || "",
    version: Number(e.version || 0),
  }));
  return { updated: d.updated || "", entries };
}

// Regex feed parsing (no XML DOM dependency; works in Node + browser). Skips malformed
// entries individually, mirroring core/read feed.py tolerance.
const ITEM_BLOCK = /<item\b[\s\S]*?<\/item>/g;
const BLYG_ID = /<blyg:id>\s*([^<\s]+)\s*<\/blyg:id>/;
const BLYG_VERSION = /<blyg:version>\s*(\d+)\s*<\/blyg:version>/;
const BLYG_ITEM = /<blyg:item>\s*([^<\s]+)\s*<\/blyg:item>/;
const BLYG_KIND = /<blyg:kind>\s*([^<\s]+)\s*<\/blyg:kind>/;

export function parseFeed(xmlText) {
  const entries = [];
  const blocks = xmlText.match(ITEM_BLOCK) || [];
  for (const block of blocks) {
    const idM = BLYG_ID.exec(block);
    const verM = BLYG_VERSION.exec(block);
    if (!idM || !verM) continue; // skip malformed entry only
    const itemM = BLYG_ITEM.exec(block);
    const kindM = BLYG_KIND.exec(block);
    entries.push({
      id: idM[1],
      version: Number(verM[1]),
      item_url: itemM ? itemM[1] : null,
      kind: kindM ? kindM[1] : null,
    });
  }
  return entries;
}
