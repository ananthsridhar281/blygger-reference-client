# blygger/core/markdown.py
"""Reference-grade minimal markdown subset -> HTML (spec 2). NOT CommonMark-complete."""
import re
from html import escape

_IMG = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_CODE = re.compile(r"`([^`]+)`")
_EM = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)|(?<!_)_([^_]+)_(?!_)")


def _inline(text: str) -> str:
    # Protect inline code spans first so their contents are escaped verbatim.
    spans = []

    def _stash_code(m):
        spans.append("<code>" + escape(m.group(1)) + "</code>")
        return f"\x00{len(spans) - 1}\x00"

    text = _CODE.sub(_stash_code, text)
    text = escape(text, quote=False)
    text = _IMG.sub(lambda m: f'<img src="{escape(m.group(2), quote=True)}" '
                              f'alt="{escape(m.group(1), quote=True)}">', text)
    text = _LINK.sub(lambda m: f'<a href="{escape(m.group(2), quote=True)}">'
                               f'{m.group(1)}</a>', text)
    text = _EM.sub(lambda m: f"<em>{m.group(1) or m.group(2)}</em>", text)
    text = re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], text)
    return text


def render(md: str) -> str:
    lines = md.split("\n")
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == "":
            i += 1
            continue
        if line.startswith("```"):
            i += 1
            code = []
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1  # consume closing fence
            body = "".join(l + "\n" for l in code)
            blocks.append("<pre><code>" + escape(body) + "</code></pre>")
            continue
        if line.startswith(">"):
            quoted = []
            while i < len(lines) and lines[i].startswith(">"):
                quoted.append(lines[i][1:].lstrip())
                i += 1
            inner = render("\n".join(quoted))
            blocks.append("<blockquote>" + inner + "</blockquote>")
            continue
        # paragraph: gather until blank line
        para = []
        while i < len(lines) and lines[i].strip() != "" and not lines[i].startswith("```") \
                and not lines[i].startswith(">"):
            para.append(lines[i])
            i += 1
        blocks.append("<p>" + _inline(" ".join(para)) + "</p>")
    return "\n".join(blocks)
