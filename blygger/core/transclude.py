# blygger/core/transclude.py
"""Publish-time transclusion resolution and HTML baking (spec 10)."""
import re
from .errors import PublishError
from .markdown import render
from .model import Transclusion

_DIRECTIVE = re.compile(r"^\s*!\[\[([0-9a-z]{26})\]\]\s*$")
_RESERVED = re.compile(r"^\s*!\[\[[0-9a-z]{26}@v\d+\]\]\s*$")


def bake(md: str, resolver):
    """Return (content_html, [Transclusion]) resolving own-origin directives in order."""
    lines = md.split("\n")
    out_blocks = []
    transclusions = []
    buffer = []

    def flush():
        if buffer:
            chunk = "\n".join(buffer).strip("\n")
            if chunk.strip():
                out_blocks.append(render(chunk))
            buffer.clear()

    for line in lines:
        if _RESERVED.match(line):
            raise PublishError("reserved version-qualified transclusion ![[id@vN]]")
        m = _DIRECTIVE.match(line)
        if m:
            flush()
            tid = m.group(1)
            version, html = resolver(tid)   # raises PublishError on bad target
            out_blocks.append(
                f'<blockquote class="blyg-transclusion" data-blyg-id="{tid}" '
                f'data-blyg-version="{version}">{html}</blockquote>'
            )
            transclusions.append(Transclusion(id=tid, version=version))
        else:
            buffer.append(line)
    flush()
    return "\n".join(out_blocks), transclusions
