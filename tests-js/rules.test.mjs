import { test } from "node:test";
import assert from "node:assert/strict";
import { rollup, watermarkCheck, resolve, OK, REGRESSION, STEALTH_EDIT }
  from "../webapp/js/blyg/rules.js";

function item(version, { kind = "fragment", updated = "2026-01-01T00:00:00Z",
                        chash = "sha256:a" } = {}) {
  return { id: "7".repeat(26), kind, updated, version, content_hash: chash };
}

test("rollup: higher version wins; tie by updated; none adopts; withdrawn -> null", () => {
  assert.equal(rollup(item(2), item(3)).item.version, 3);
  assert.equal(rollup(item(3, { updated: "2026-01-01T00:00:00Z" }),
                      item(3, { updated: "2026-02-01T00:00:00Z" })).item.updated,
               "2026-02-01T00:00:00Z");
  assert.equal(rollup(null, item(1)).item.version, 1);
  const w = rollup(item(3), item(4, { kind: "withdrawn" }));
  assert.equal(w.item, null);
  assert.ok(w.withdrawn);
});

test("watermarkCheck: ok / regression / stealth", () => {
  assert.equal(watermarkCheck(2, "sha256:a", item(3)), OK);
  assert.equal(watermarkCheck(5, "sha256:a", item(3)), REGRESSION);
  assert.equal(watermarkCheck(3, "sha256:a", item(3, { chash: "sha256:b" })), STEALTH_EDIT);
  assert.equal(watermarkCheck(3, "sha256:a", item(3, { chash: "sha256:a" })), OK);
});

const MANIFEST = JSON.stringify({ blyg: "0.3", site: "https://x.example/blyg/" });
const FEED_WITH_MANIFEST =
  '<?xml version="1.0"?><rss xmlns:blyg="https://blygger.org/ns/0.1"><channel>' +
  "<blyg:manifest>https://x.example/blyg/blyg.json</blyg:manifest></channel></rss>";
const PLAIN_RSS = '<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>';

function makeFetch(table) {
  const calls = [];
  const fn = async (url) => {
    calls.push(url);
    const row = table[url] || [404, "", url];
    return { status: row[0], body: row[1], finalUrl: row[2] };
  };
  fn.calls = calls;
  return fn;
}

test("resolve: direct probe + identity from final fetch origin", async () => {
  const fetch = makeFetch({
    "https://x.example/blyg/blyg.json": [200, MANIFEST, "https://new.example/blyg/blyg.json"],
  });
  const r = await resolve("https://x.example/blyg/", fetch);
  assert.equal(r.kind, "blyg");
  assert.equal(r.origin, "https://new.example/blyg/"); // final fetch origin wins
});

test("resolve: feed upgrade via blyg:manifest", async () => {
  const fetch = makeFetch({
    "https://x.example/feed.xml/blyg.json": [404, "", "x"],
    "https://x.example/feed.xml": [200, FEED_WITH_MANIFEST, "https://x.example/feed.xml"],
    "https://x.example/blyg/blyg.json": [200, MANIFEST, "https://x.example/blyg/blyg.json"],
  });
  assert.equal((await resolve("https://x.example/feed.xml", fetch)).kind, "blyg");
});

test("resolve: rss fallback -> l0; nothing -> fail; <= 6 fetches", async () => {
  const l0 = makeFetch({
    "https://x.example/feed.xml/blyg.json": [404, "", "x"],
    "https://x.example/feed.xml": [200, PLAIN_RSS, "https://x.example/feed.xml"],
  });
  assert.equal((await resolve("https://x.example/feed.xml", l0)).kind, "l0");

  const empty = makeFetch({});
  assert.equal((await resolve("https://x.example/nope/", empty)).kind, "fail");
  assert.ok(empty.calls.length <= 6);
});
