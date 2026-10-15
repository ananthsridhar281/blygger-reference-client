"""Command-line interface for the Blygger reference client.

Thin glue over the library (publish/emit on one side, resolve/reconcile on the
other). Lets you stand up a static blyg, serve it, and subscribe to one from the
terminal.

Subcommands:
  blygger init   <store> --title T --author NAME [--site URL]
  blygger publish <store> (--fragment TEXT | --thread MD)
  blygger pin     <store> <id> <version>
  blygger withdraw <store> <id> [--note NOTE]
  blygger emit    <store> <out> --origin URL
  blygger serve   <dir> [--port N] [--host H]
  blygger read    <url> [--archive DIR]
  blygger demo
"""
import argparse
import functools
import json
import sys
import tempfile
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .core import timefmt
from .core.errors import PublishError
from .publish.store import Store
from .publish.studio import Studio
from .publish.emit import emit as emit_surface
from .read.archive import Archive
from .read.reconcile import Reconciler
from .read.resolve import resolve_subscription
from .transport.fs import FsTransport
from .transport.http import HttpTransport

GENERATOR = "blygger-ref/0.1"


def _now_iso() -> str:
    return timefmt.to_iso(datetime.now(timezone.utc))


def _studio(store: Store) -> Studio:
    # origin/author are injected at emit time from the store's manifest meta, so
    # the values passed here are not persisted into item versions.
    return Studio(store, origin="local")


# ---------------------------------------------------------------- commands ----
def cmd_init(args) -> int:
    store = Store(Path(args.store))
    meta = {"title": args.title or "", "site": args.site or ""}
    if args.author:
        meta["author"] = {"name": args.author}
    store.set_manifest_meta(meta)
    print(f"Initialized blyg store at {args.store}")
    print(f"  title:  {meta['title']!r}")
    print(f"  author: {args.author!r}")
    return 0


def cmd_publish(args) -> int:
    store = Store(Path(args.store))
    studio = _studio(store)
    try:
        if args.fragment is not None:
            item_id = studio.publish_fragment(args.fragment)
            kind = "fragment"
        else:
            item_id = studio.publish_thread(args.thread)
            kind = "thread"
    except PublishError as e:
        print(f"publish error: {e}", file=sys.stderr)
        return 1
    print(f"published {kind} {item_id}")
    return 0


def cmd_pin(args) -> int:
    store = Store(Path(args.store))
    try:
        _studio(store).pin(args.id, args.version)
    except PublishError as e:
        print(f"pin error: {e}", file=sys.stderr)
        return 1
    print(f"pinned {args.id} v{args.version}")
    return 0


def cmd_withdraw(args) -> int:
    store = Store(Path(args.store))
    try:
        version = _studio(store).withdraw(args.id, note=args.note)
    except PublishError as e:
        print(f"withdraw error: {e}", file=sys.stderr)
        return 1
    print(f"withdrew {args.id} (endcap v{version})")
    return 0


def cmd_emit(args) -> int:
    store = Store(Path(args.store))
    out = Path(args.out)
    try:
        emit_surface(store, out, origin=args.origin, generator=GENERATOR,
                     updated=_now_iso())
    except PublishError as e:
        print(f"emit error: {e}", file=sys.stderr)
        return 1
    files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    print(f"emitted {len(files)} files to {out} (origin {args.origin})")
    for f in files:
        print(f"  {f}")
    return 0


def cmd_serve(args) -> int:
    directory = str(Path(args.dir).resolve())
    handler = functools.partial(SimpleHTTPRequestHandler, directory=directory)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    host, port = server.server_address
    print(f"serving {directory} at http://{host}:{port}/  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0


def _print_subscription_state(archive: Archive, origin: str) -> None:
    ids = sorted(archive.known_ids(origin))
    if not ids:
        print("  (no items)")
        return
    for iid in ids:
        state = archive.get(origin, iid)
        wm = archive.watermark(origin, iid)
        if state is None:
            print(f"  {iid}  [withdrawn, watermark v{wm}]")
        else:
            snippet = (state.get("content_md") or "").replace("\n", " ")[:50]
            print(f"  {iid}  v{state['version']} {state['kind']}  {snippet!r}")


def cmd_read(args) -> int:
    archive_dir = Path(args.archive) if args.archive else Path(tempfile.mkdtemp())
    transport = HttpTransport(generator=GENERATOR)
    sub = resolve_subscription(transport, args.url)
    if sub.kind != "blyg":
        print(f"could not resolve {args.url} as a blyg (result: {sub.kind})",
              file=sys.stderr)
        return 1
    print(f"resolved origin: {sub.origin}")
    print(f"title:           {sub.manifest.title!r}")
    if sub.site_mismatch:
        print(f"  ! manifest 'site' ({sub.manifest.site}) disagrees with fetch origin "
              f"— using fetch origin")
    archive = Archive(archive_dir)
    result = Reconciler(transport, archive).reconcile(sub)
    print(f"fetched {result.fetched} item document(s); "
          f"{len(result.discrepancies)} discrepancy(ies)")
    for d in result.discrepancies:
        print(f"  ! {d.type}: {d.id} — {d.detail}")
    print("archive state:")
    _print_subscription_state(archive, sub.origin)
    print(f"(archive stored at {archive_dir})")
    return 0


def cmd_web(args) -> int:
    from .web.server import WebConfig, serve
    config = WebConfig(store_dir=Path(args.store), site_dir=Path(args.site),
                       origin=args.origin, archive_dir=Path(args.archive))
    return serve(config, host=args.host, port=args.port)


def cmd_demo(args) -> int:
    store_dir = Path(tempfile.mkdtemp(prefix="blyg-store-"))
    out_dir = Path(tempfile.mkdtemp(prefix="blyg-out-"))
    archive_dir = Path(tempfile.mkdtemp(prefix="blyg-archive-"))
    origin = "https://demo.example/blyg/"

    print("== 1. publish ==")
    store = Store(store_dir)
    store.set_manifest_meta({"title": "Demo blyg", "site": origin,
                             "author": {"name": "Ada Lovelace"}})
    studio = _studio(store)
    f1 = studio.publish_fragment("A short thought, published *in public*.")
    studio.edit(f1, "A short thought, published *in public*, now sharpened.",
                note="sharpen")
    f2 = studio.publish_fragment("A second fragment worth pinning.")
    studio.pin(f2, 1)
    t1 = studio.publish_thread(f"Here is a longer piece.\n\n![[{f1}]]\n\nClosing remark.")
    f3 = studio.publish_fragment("This one will be withdrawn.")
    studio.withdraw(f3)
    print(f"  fragment f1={f1} (edited to v2)")
    print(f"  fragment f2={f2} (pinned v1)")
    print(f"  thread   t1={t1} (transcludes f1)")
    print(f"  fragment f3={f3} (withdrawn)")

    print("== 2. emit static surface ==")
    emit_surface(store, out_dir, origin=origin, generator=GENERATOR, updated=_now_iso())
    files = sorted(p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*") if p.is_file())
    for f in files:
        print(f"  {f}")

    print("== 3. subscribe + reconcile (filesystem transport) ==")
    transport = FsTransport(origin, out_dir)
    sub = resolve_subscription(transport, origin)
    archive = Archive(archive_dir)
    result = Reconciler(transport, archive).reconcile(sub)
    print(f"  resolved origin: {sub.origin}")
    print(f"  fetched {result.fetched} docs; {len(result.discrepancies)} discrepancies")
    print("  reader archive state:")
    _print_subscription_state(archive, sub.origin)

    print("\nDemo complete. To try the HTTP path yourself:")
    print(f"  blygger serve {out_dir} --port 8017")
    print(f"  blygger read http://127.0.0.1:8017/")
    return 0


# ------------------------------------------------------------------ parser ----
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="blygger",
                                description="Blygger v0.3 reference client (L1 + blogroll).")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("init", help="create a blyg store")
    pi.add_argument("store")
    pi.add_argument("--title", default="")
    pi.add_argument("--author", default="")
    pi.add_argument("--site", default="")
    pi.set_defaults(func=cmd_init)

    pp = sub.add_parser("publish", help="publish a fragment or thread")
    pp.add_argument("store")
    g = pp.add_mutually_exclusive_group(required=True)
    g.add_argument("--fragment", metavar="TEXT")
    g.add_argument("--thread", metavar="MARKDOWN")
    pp.set_defaults(func=cmd_publish)

    pn = sub.add_parser("pin", help="pin a version")
    pn.add_argument("store")
    pn.add_argument("id")
    pn.add_argument("version", type=int)
    pn.set_defaults(func=cmd_pin)

    pw = sub.add_parser("withdraw", help="withdraw an item")
    pw.add_argument("store")
    pw.add_argument("id")
    pw.add_argument("--note", default=None)
    pw.set_defaults(func=cmd_withdraw)

    pe = sub.add_parser("emit", help="render the static surface")
    pe.add_argument("store")
    pe.add_argument("out")
    pe.add_argument("--origin", required=True, help="absolute origin URL, e.g. https://x/blyg/")
    pe.set_defaults(func=cmd_emit)

    ps = sub.add_parser("serve", help="serve a directory over HTTP")
    ps.add_argument("dir")
    ps.add_argument("--port", type=int, default=8000)
    ps.add_argument("--host", default="127.0.0.1")
    ps.set_defaults(func=cmd_serve)

    pr = sub.add_parser("read", help="resolve + reconcile a blyg URL")
    pr.add_argument("url")
    pr.add_argument("--archive", default=None, help="archive dir (default: temp)")
    pr.set_defaults(func=cmd_read)

    pweb = sub.add_parser("web", help="launch the reader + studio web UI")
    pweb.add_argument("--store", default="./blyg/store", help="private store dir")
    pweb.add_argument("--site", default="./blyg/site", help="emitted static-site dir")
    pweb.add_argument("--archive", default="./blyg/archive", help="reader archive dir")
    pweb.add_argument("--origin", default="https://localhost/blyg/",
                      help="origin URL stamped into emitted files")
    pweb.add_argument("--port", type=int, default=8000)
    pweb.add_argument("--host", default="127.0.0.1")
    pweb.set_defaults(func=cmd_web)

    pd = sub.add_parser("demo", help="run an end-to-end round-trip demo")
    pd.set_defaults(func=cmd_demo)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
