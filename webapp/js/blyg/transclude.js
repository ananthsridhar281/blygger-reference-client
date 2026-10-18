// Publish-time transclusion resolution + HTML baking (spec 10). Port of core/transclude.py.
// `resolver(id)` returns (or resolves to) { version, html } or throws PublishError.
import { PublishError } from "./errors.js";
import { render } from "./markdown.js";

const DIRECTIVE = /^\s*!\[\[([0-9a-z]{26})\]\]\s*$/;
const RESERVED = /^\s*!\[\[[0-9a-z]{26}@v\d+\]\]\s*$/;

export async function bake(md, resolver) {
  const lines = md.split("\n");
  const out = [];
  const transclusions = [];
  let buffer = [];

  const flush = () => {
    if (buffer.length) {
      const chunk = buffer.join("\n").replace(/^\n+|\n+$/g, "");
      if (chunk.trim()) out.push(render(chunk));
      buffer = [];
    }
  };

  for (const line of lines) {
    if (RESERVED.test(line)) {
      throw new PublishError("reserved version-qualified transclusion ![[id@vN]]");
    }
    const m = DIRECTIVE.exec(line);
    if (m) {
      flush();
      const tid = m[1];
      const { version, html } = await resolver(tid); // throws PublishError on bad target
      out.push(
        `<blockquote class="blyg-transclusion" data-blyg-id="${tid}" ` +
        `data-blyg-version="${version}">${html}</blockquote>`,
      );
      transclusions.push({ id: tid, version });
    } else {
      buffer.push(line);
    }
  }
  flush();
  return { html: out.join("\n"), transclusions };
}
