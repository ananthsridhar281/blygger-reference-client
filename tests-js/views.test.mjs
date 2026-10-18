import { test } from "node:test";
import assert from "node:assert/strict";
import { writeView, readView, settingsView } from "../webapp/js/views.js";

test("writeView lists items and publish controls", () => {
  const html = writeView(
    [{ id: "a".repeat(26), kind: "fragment", version: 1, note: null,
       pinned_versions: [], withdrawn: false, md_snippet: "hi there" }],
    "https://x/blyg/", ["a".repeat(26)]);
  assert.ok(html.includes("a".repeat(26)));
  assert.ok(html.includes('data-action="publish-fragment"'));
  assert.ok(html.includes('data-action="publish-thread"'));
  assert.ok(html.includes('data-action="publish-site"'));
  assert.ok(html.includes("hi there"));
});

test("readView renders untrusted html in a sandboxed iframe, escaping scripts", () => {
  const result = { origin: "https://x/blyg/", title: "T", siteMismatch: false, fetched: 1,
    discrepancies: [], items: [{ id: "a".repeat(26), withdrawn: false, version: 1,
      kind: "fragment", content_html: "<p>hi <script>bad()</script></p>" }] };
  const html = readView(result);
  assert.ok(html.includes('<iframe class="content" sandbox srcdoc='));
  assert.ok(!html.includes("allow-scripts"));
  assert.ok(!html.includes("<script>bad()"));         // not live in the parent doc
  assert.ok(html.includes("&lt;script&gt;bad()"));    // escaped inside srcdoc
});

test("readView shows discrepancy + site-mismatch banners; tombstone for withdrawn", () => {
  const html = readView({ origin: "o", title: "T", siteMismatch: true, fetched: 1,
    discrepancies: [["x"]].map(() => ({ type: "stealth_edit", id: "a".repeat(26), detail: "changed" })),
    items: [{ id: "b".repeat(26), withdrawn: true, version: 2, kind: "withdrawn", content_html: "" }] });
  assert.ok(html.includes("stealth_edit"));
  assert.ok(html.includes("disagrees with the fetch origin"));
  assert.ok(html.includes("withdrawn by the author"));
});

test("settingsView renders fields and a token warning", () => {
  const html = settingsView({ owner: "me", repo: "r", branch: "main", basePath: "",
    pat: "secret", originUrl: "https://x/", title: "T", authorName: "A" });
  assert.ok(html.includes('id="set-owner"'));
  assert.ok(html.includes('id="set-pat"'));
  assert.ok(html.includes("sensitive"));
});
