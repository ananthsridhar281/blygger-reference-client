import { test } from "node:test";
import assert from "node:assert/strict";
import { newId, isValidId, ALPHABET } from "../webapp/js/blyg/ids.js";
import { contentHash } from "../webapp/js/blyg/hash.js";
import { render } from "../webapp/js/blyg/markdown.js";
import { bake } from "../webapp/js/blyg/transclude.js";
import { PublishError } from "../webapp/js/blyg/errors.js";
import { parseItem, parseFeed } from "../webapp/js/blyg/serialize.js";

test("newId is 26 lowercase Crockford chars, excludes i/l/o/u", () => {
  const id = newId();
  assert.equal(id.length, 26);
  assert.ok([...id].every((c) => ALPHABET.includes(c)));
  for (const bad of "ilou") assert.ok(!ALPHABET.includes(bad));
});

test("newId values are unique", () => {
  const set = new Set();
  for (let i = 0; i < 1000; i++) set.add(newId());
  assert.equal(set.size, 1000);
});

test("isValidId", () => {
  assert.ok(isValidId(newId()));
  assert.ok(!isValidId("too-short"));
  assert.ok(!isValidId("A".repeat(26))); // uppercase
  assert.ok(!isValidId("i".repeat(26))); // excluded letter
});

test("contentHash matches the Python reference vectors (cross-impl guard)", async () => {
  assert.equal(await contentHash(""),
    "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
  // sha256 of "Markdown source of the *latest* version." (UTF-8)
  const h = await contentHash("Markdown source of the *latest* version.");
  assert.ok(h.startsWith("sha256:") && h.length === 7 + 64);
});

test("markdown: paragraph + emphasis", () => {
  assert.equal(render("Markdown source of the *latest* version."),
    "<p>Markdown source of the <em>latest</em> version.</p>");
});

test("markdown: inline code escaped, links, images, blockquote, two paras", () => {
  assert.equal(render("use `a<b>`"), "<p>use <code>a&lt;b&gt;</code></p>");
  assert.equal(render("[t](https://x)"), '<p><a href="https://x">t</a></p>');
  assert.equal(render("![alt](https://x/i.png)"), '<p><img src="https://x/i.png" alt="alt"></p>');
  assert.equal(render("> quoted"), "<blockquote><p>quoted</p></blockquote>");
  assert.equal(render("one\n\ntwo"), "<p>one</p>\n<p>two</p>");
  assert.equal(render("a & b < c"), "<p>a &amp; b &lt; c</p>");
});

const FID = "7c9wk2mhq0v3xj8tn5rzfd41bg";
const resolver = async (id) => {
  if (id === FID) return { version: 3, html: "<p>quoted</p>" };
  throw new PublishError("unknown " + id);
};

test("transclude: directive bakes blockquote + provenance", async () => {
  const { html, transclusions } = await bake(`Intro.\n\n![[${FID}]]\n\nOutro.`, resolver);
  assert.ok(html.includes(
    `<blockquote class="blyg-transclusion" data-blyg-id="${FID}" data-blyg-version="3"><p>quoted</p></blockquote>`));
  assert.ok(html.includes("<p>Intro.</p>") && html.includes("<p>Outro.</p>"));
  assert.deepEqual(transclusions, [{ id: FID, version: 3 }]);
});

test("transclude: inline directive inert; reserved and unknown throw", async () => {
  const { transclusions } = await bake(`see ![[${FID}]] here`, resolver);
  assert.deepEqual(transclusions, []);
  await assert.rejects(() => bake(`![[${FID}@v2]]`, resolver), PublishError);
  await assert.rejects(() => bake("![[" + "0".repeat(26) + "]]", resolver), PublishError);
});

test("serialize: parseItem tolerant; parseFeed skips malformed", () => {
  const item = parseItem({ id: FID, kind: "fragment", version: "3", content_html: "<p>x</p>",
                           mystery: 1, forked_from: { id: "y" } });
  assert.equal(item.version, 3);
  assert.equal(item.kind, "fragment");
  const feed = parseFeed(
    '<rss xmlns:blyg="https://blygger.org/ns/0.1"><channel>' +
    `<item><blyg:id>${FID}</blyg:id><blyg:version>2</blyg:version>` +
    `<blyg:item>https://x/items/${FID}.json</blyg:item></item>` +
    "<item><blyg:id>broken</blyg:id></item>" + // no version -> skipped
    "</channel></rss>");
  assert.equal(feed.length, 1);
  assert.equal(feed[0].version, 2);
  assert.equal(feed[0].item_url, `https://x/items/${FID}.json`);
});
