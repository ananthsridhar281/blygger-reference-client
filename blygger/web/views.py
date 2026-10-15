"""Pure HTML view functions for the web UI. No I/O — take plain data, return
HTML strings. Untrusted item HTML is rendered inside a sandboxed iframe (spec 14)."""
from html import escape

_CSS = """
*{box-sizing:border-box}
body{font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:0;color:#1a1a1a;background:#fafafa}
header{background:#1a1a2e;color:#fff;padding:12px 20px;display:flex;align-items:center;gap:20px}
header h1{font-size:16px;margin:0;font-weight:600}
header a{color:#cfcfe6;text-decoration:none;padding:4px 10px;border-radius:5px}
header a.active,header a:hover{background:#2d2d44;color:#fff}
main{max-width:820px;margin:0 auto;padding:24px 20px}
h2{font-size:20px;margin:0 0 16px}
.card{background:#fff;border:1px solid #e3e3e3;border-radius:8px;padding:16px;margin:0 0 14px}
.badge{display:inline-block;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;padding:2px 7px;border-radius:4px;vertical-align:middle}
.badge.fragment{background:#e3f0ff;color:#1b5fb0}
.badge.thread{background:#ede3ff;color:#6b3fb0}
.badge.withdrawn{background:#eee;color:#888}
.badge.pinned{background:#fff2d6;color:#9a6b00}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:#666}
.muted{color:#888}
form.inline{display:inline}
textarea,input[type=text]{width:100%;font:inherit;padding:8px;border:1px solid #ccc;border-radius:6px}
textarea{min-height:90px;resize:vertical}
button{font:inherit;font-weight:600;background:#1b5fb0;color:#fff;border:0;padding:8px 14px;border-radius:6px;cursor:pointer}
button.secondary{background:#555}
button.danger{background:#b03b3b}
button.small{padding:4px 9px;font-size:13px}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.flash{background:#e6f6e6;border:1px solid #bfe3bf;color:#246b24;padding:10px 14px;border-radius:6px;margin:0 0 16px}
.warn{background:#fff3e0;border:1px solid #f0d49b;color:#8a5a00;padding:10px 14px;border-radius:6px;margin:0 0 10px}
.err{background:#fde8e8;border:1px solid #f0b0b0;color:#9a2b2b;padding:10px 14px;border-radius:6px;margin:0 0 16px}
iframe.content{width:100%;height:220px;border:1px solid #eee;border-radius:6px;background:#fff}
fieldset{border:1px solid #e3e3e3;border-radius:8px;margin:0 0 20px;padding:16px}
legend{font-weight:600;padding:0 6px}
label{display:block;font-size:13px;font-weight:600;margin:0 0 4px;color:#444}
.tombstone{color:#999;font-style:italic}
"""


def render_page(title: str, active: str, body: str) -> str:
    def nav(href, key, label):
        cls = ' class="active"' if key == active else ""
        return f'<a href="{href}"{cls}>{escape(label)}</a>'
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>{escape(title)}</title><style>{_CSS}</style></head><body>"
        "<header><h1>Blygger</h1>"
        f"{nav('/studio', 'studio', 'Studio')}{nav('/reader', 'reader', 'Reader')}"
        "</header><main>" + body + "</main></body></html>"
    )


def _badge(kind: str) -> str:
    return f'<span class="badge {escape(kind)}">{escape(kind)}</span>'


# ----------------------------------------------------------------- studio ----
def studio_view(items, origin, fragment_ids, site_emitted, flash=None) -> str:
    out = ["<h2>Studio</h2>"]
    if flash:
        out.append(f'<div class="flash">{escape(flash)}</div>')
    out.append(f'<p class="muted">Store origin on publish: <span class="mono">{escape(origin)}</span></p>')

    out.append('<fieldset><legend>Publish a fragment</legend>'
               '<form method="post" action="/studio/publish-fragment">'
               '<label>Markdown</label>'
               '<textarea name="text" placeholder="A short thought..."></textarea>'
               '<div class="row" style="margin-top:8px"><button>Publish fragment</button></div>'
               '</form></fieldset>')

    hint = ""
    if fragment_ids:
        ids = " ".join(f'<span class="mono">![[{escape(i)}]]</span>' for i in fragment_ids)
        hint = f'<p class="muted">Transcludable fragment ids: {ids}</p>'
    out.append('<fieldset><legend>Publish a thread</legend>'
               '<form method="post" action="/studio/publish-thread">'
               '<label>Markdown (use a lone <span class="mono">![[id]]</span> line to transclude)</label>'
               '<textarea name="text" placeholder="Intro...\n\n![[id]]\n\nmore"></textarea>'
               f'{hint}'
               '<div class="row" style="margin-top:8px"><button>Publish thread</button></div>'
               '</form></fieldset>')

    out.append('<fieldset><legend>Items in store</legend>')
    if not items:
        out.append('<p class="muted">No items yet.</p>')
    for it in items:
        out.append(_studio_item_card(it))
    out.append('</fieldset>')

    emit_note = ' <span class="muted">(site emitted)</span>' if site_emitted else ""
    out.append('<form method="post" action="/studio/emit">'
               f'<button class="secondary">Publish to site{escape("")}</button>{emit_note}'
               '</form>')
    return "".join(out)


def _studio_item_card(it) -> str:
    badges = _badge(it["kind"])
    for v in it["pinned_versions"]:
        badges += f' <span class="badge pinned">pin v{v}</span>'
    body = [
        '<div class="card">',
        f'<div class="row"><span class="mono">{escape(it["id"])}</span> {badges} '
        f'<span class="muted">v{it["version"]}</span></div>',
    ]
    if it["note"]:
        body.append(f'<div class="muted">note: {escape(it["note"])}</div>')
    if it["md_snippet"]:
        body.append(f'<div>{escape(it["md_snippet"])}</div>')
    if not it["withdrawn"]:
        body.append('<div class="row" style="margin-top:8px">')
        body.append('<form class="inline" method="post" action="/studio/pin">'
                    f'<input type="hidden" name="id" value="{escape(it["id"])}">'
                    f'<input type="hidden" name="version" value="{it["version"]}">'
                    f'<button class="small secondary">Pin v{it["version"]}</button></form>')
        body.append('<form class="inline" method="post" action="/studio/withdraw">'
                    f'<input type="hidden" name="id" value="{escape(it["id"])}">'
                    '<button class="small danger">Withdraw</button></form>')
        body.append('</div>')
    else:
        body.append('<div class="tombstone">withdrawn</div>')
    body.append('</div>')
    return "".join(body)


# ----------------------------------------------------------------- reader ----
def reader_view(form_url, result) -> str:
    out = ['<h2>Reader</h2>',
           '<form method="get" action="/reader">'
           '<label>Blyg URL</label>'
           '<div class="row">'
           f'<input type="text" name="url" value="{escape(form_url or "")}" '
           'placeholder="https://example.com/blyg/" style="flex:1">'
           '<button name="src" value="url">Read</button>'
           '<button class="secondary" name="src" value="local">Read my local site</button>'
           '</div></form>']

    if result is None:
        out.append('<p class="muted">Enter a blyg URL, or read the site you emitted in Studio.</p>')
        return "".join(out)

    if result.get("error"):
        out.append(f'<div class="err">{escape(result["error"])} '
                   f'(<span class="mono">{escape(result.get("target", ""))}</span>)</div>')
        return "".join(out)

    out.append('<div class="card">'
               f'<div><strong>{escape(result["title"] or "(untitled)")}</strong></div>'
               f'<div class="mono">{escape(result["origin"])}</div>'
               f'<div class="muted">fetched {result["fetched"]} document(s)</div></div>')
    if result.get("site_mismatch"):
        out.append('<div class="warn">manifest <span class="mono">site</span> disagrees with the '
                   'fetch origin — using the fetch origin as identity.</div>')
    for typ, iid, detail in result["discrepancies"]:
        out.append(f'<div class="warn"><strong>{escape(typ)}</strong> '
                   f'<span class="mono">{escape(iid)}</span> — {escape(detail)}</div>')

    if not result["items"]:
        out.append('<p class="muted">No items.</p>')
    for it in result["items"]:
        out.append(_reader_item_card(it))
    return "".join(out)


def _sandbox_srcdoc(content_html: str) -> str:
    """Wrap untrusted HTML in a minimal doc and escape it for a sandboxed srcdoc."""
    doc = (
        '<!doctype html><meta charset="utf-8"><base target="_blank">'
        '<style>body{font:14px/1.5 -apple-system,sans-serif;margin:8px;color:#1a1a1a}'
        'blockquote.blyg-transclusion{border-left:3px solid #bbb;margin:0 0 8px;'
        'padding:4px 0 4px 12px;color:#333}img{max-width:100%}</style>' + content_html
    )
    return escape(doc, quote=True)


def _reader_item_card(it) -> str:
    head = (f'<div class="row"><span class="mono">{escape(it["id"])}</span> '
            f'{_badge(it["kind"])} <span class="muted">v{it["version"]}</span>'
            + (f' <span class="muted">· {escape(it["author_name"])}</span>'
               if it.get("author_name") else "") + '</div>')
    if it["withdrawn"]:
        inner = '<div class="tombstone">withdrawn by the author</div>'
    else:
        # sandbox="" -> scripts, forms, top-navigation all disabled (spec 14)
        inner = f'<iframe class="content" sandbox srcdoc="{_sandbox_srcdoc(it["content_html"])}"></iframe>'
    return f'<div class="card">{head}{inner}</div>'
