import { test } from "node:test";
import assert from "node:assert/strict";
import { emit } from "../webapp/js/blyg/emit.js";
import { contentHash } from "../webapp/js/blyg/hash.js";
import { Reconciler, InMemoryArchive, resolveSubscription } from "../webapp/js/blyg/reconcile.js";

const FID = "a".repeat(26);
const F2 = "b".repeat(26);
const TID = "c".repeat(26);
const F3 = "d".repeat(26);
const ORIGIN = "https://pub.example/blyg/";

async function version(v, at, md, kind = "fragment", extra = {}) {
  return { version: v, at, kind, note: extra.note ?? null, content_md: md,
           content_html: extra.html ?? `<p>${md}</p>`, content_hash: await contentHash(md),
           media: [], pinned: !!extra.pinned, ...(extra.transclusions ? { transclusions: extra.transclusions } : {}) };
}

async function buildSnapshot() {
  const baked = `<blockquote class="blyg-transclusion" data-blyg-id="${FID}" data-blyg-version="2"><p>first, sharpened</p></blockquote>`;
  return {
    manifestMeta: { title: "Demo blyg", site: ORIGIN, author: { name: "Ada" } },
    blogroll: [],
    items: [
      { id: FID, authoredKind: "fragment", created: "2026-01-01T00:00:00Z", versions: [
        await version(1, "2026-01-01T00:01:00Z", "first"),
        await version(2, "2026-01-01T00:02:00Z", "first, sharpened", "fragment", { note: "sharpen" }),
      ] },
      { id: F2, authoredKind: "fragment", created: "2026-01-01T00:03:00Z", versions: [
        await version(1, "2026-01-01T00:04:00Z", "pinned fragment", "fragment", { pinned: true }),
      ] },
      { id: TID, authoredKind: "thread", created: "2026-01-01T00:05:00Z", versions: [
        await version(1, "2026-01-01T00:06:00Z", `Intro\n\n![[${FID}]]\n\nEnd`, "thread",
          { html: `<p>Intro</p>\n${baked}\n<p>End</p>`, transclusions: [{ id: FID, version: 2 }] }),
      ] },
      { id: F3, authoredKind: "fragment", created: "2026-01-01T00:07:00Z", versions: [
        await version(1, "2026-01-01T00:08:00Z", "doomed"),
        { version: 2, at: "2026-01-01T00:09:00Z", kind: "withdrawn", note: null,
          content_md: "", content_html: "", content_hash: await contentHash(""), media: [], pinned: false },
      ] },
    ],
  };
}

function stubTransport(origin, files) {
  return {
    async get(url) {
      if (url.startsWith(origin)) {
        const rel = url.slice(origin.length);
        if (rel in files) return { status: 200, body: files[rel], finalUrl: url };
      }
      return { status: 404, body: "", finalUrl: url };
    },
  };
}

test("emit produces the expected surface (paths, pins, withdrawn feed entry)", async () => {
  const files = emit(await buildSnapshot(), { origin: ORIGIN, generator: "blygger-web/0.1",
                                              updated: "2026-01-01T12:00:00Z" });
  assert.ok("blyg.json" in files);
  assert.ok("feed.xml" in files);
  assert.ok("items/index.json" in files);
  assert.ok(`items/${FID}.json` in files);
  assert.ok(`items/${F2}/v1.json` in files, "pinned version file emitted");
  const manifest = JSON.parse(files["blyg.json"]);
  assert.equal(manifest.level, 1);
  assert.equal(manifest.blyg, "0.3");
  // withdrawn item contributes exactly one 'withdrawn' feed entry
  const withdrawnGuids = (files["feed.xml"].match(new RegExp(`blyg:${F3}:v\\d+`, "g")) || []);
  assert.equal(withdrawnGuids.length, 1);
  assert.ok(files["feed.xml"].includes("<title>withdrawn</title>"));
});

test("round-trip: publish -> emit -> resolve -> reconcile equals publisher truth", async () => {
  const files = emit(await buildSnapshot(), { origin: ORIGIN, generator: "blygger-web/0.1",
                                              updated: "2026-01-01T12:00:00Z" });
  const transport = stubTransport(ORIGIN, files);
  const sub = await resolveSubscription(transport, ORIGIN);
  assert.equal(sub.kind, "blyg");
  assert.equal(sub.origin, ORIGIN);

  const archive = new InMemoryArchive();
  const result = await new Reconciler(transport, archive).reconcile(sub);

  assert.equal(archive.get(ORIGIN, FID).version, 2);       // edited fragment rolled to latest
  assert.equal(archive.get(ORIGIN, F2).version, 1);        // pinned fragment present
  const thread = archive.get(ORIGIN, TID);
  assert.equal(thread.kind, "thread");
  assert.ok(thread.content_html.includes("blyg-transclusion")); // baked quote survived
  assert.equal(archive.get(ORIGIN, F3), null);             // withdrawn -> null
  assert.equal(archive.watermark(ORIGIN, F3), 2);          // watermark retained
  assert.deepEqual(result.discrepancies, []);              // hashes consistent, no surprises
});
