// Reference-grade minimal markdown subset -> HTML (spec 2). NOT CommonMark-complete.
// Port of core/markdown.py.

export function escapeHtml(s, quote = false) {
  s = s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  if (quote) s = s.replace(/"/g, "&quot;").replace(/'/g, "&#x27;");
  return s;
}

const IMG = /!\[([^\]]*)\]\(([^)]+)\)/g;
const LINK = /\[([^\]]+)\]\(([^)]+)\)/g;
const CODE = /`([^`]+)`/g;
const EM = /(?<!\*)\*([^*]+)\*(?!\*)|(?<!_)_([^_]+)_(?!_)/g;

function inline(text) {
  const spans = [];
  text = text.replace(CODE, (_, c) => {
    spans.push("<code>" + escapeHtml(c, true) + "</code>");
    return "\x00" + (spans.length - 1) + "\x00";
  });
  text = escapeHtml(text, false);
  text = text.replace(IMG, (_, alt, src) =>
    `<img src="${escapeHtml(src, true)}" alt="${escapeHtml(alt, true)}">`);
  text = text.replace(LINK, (_, t, u) => `<a href="${escapeHtml(u, true)}">${t}</a>`);
  text = text.replace(EM, (_, a, b) => `<em>${a || b}</em>`);
  text = text.replace(/\x00(\d+)\x00/g, (_, i) => spans[Number(i)]);
  return text;
}

export function render(md) {
  const lines = md.split("\n");
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.trim() === "") { i++; continue; }
    if (line.startsWith("```")) {
      i++;
      const code = [];
      while (i < lines.length && !lines[i].startsWith("```")) { code.push(lines[i]); i++; }
      i++; // consume closing fence
      const body = code.map((l) => l + "\n").join("");
      blocks.push("<pre><code>" + escapeHtml(body, true) + "</code></pre>");
      continue;
    }
    if (line.startsWith(">")) {
      const quoted = [];
      while (i < lines.length && lines[i].startsWith(">")) {
        quoted.push(lines[i].slice(1).replace(/^\s+/, ""));
        i++;
      }
      blocks.push("<blockquote>" + render(quoted.join("\n")) + "</blockquote>");
      continue;
    }
    const para = [];
    while (i < lines.length && lines[i].trim() !== "" &&
           !lines[i].startsWith("```") && !lines[i].startsWith(">")) {
      para.push(lines[i]); i++;
    }
    blocks.push("<p>" + inline(para.join(" ")) + "</p>");
  }
  return blocks.join("\n");
}
