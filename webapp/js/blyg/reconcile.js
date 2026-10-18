// Importer/reconciler: feed trigger + index diff -> rollup (spec 13). Port of read/reconcile.py.
// `transport.get(url)` -> Promise<{ status, body (string), finalUrl }>.
import { rollup, watermarkCheck, resolve, OK, REGRESSION, STEALTH_EDIT } from "./rules.js";
import { parseItem, parseIndex, parseFeed, parseManifest } from "./serialize.js";
import { contentHash } from "./hash.js";
import { discrepancy } from "./errors.js";

// Resolve a URL to a subscription { kind, origin, manifest, feedUrl, siteMismatch }.
// `transport.get(url)` -> Promise<{ status, body, finalUrl }>.
export async function resolveSubscription(transport, url) {
  const fetchFn = async (u) => {
    const r = await transport.get(u);
    return { status: r.status, body: r.body, finalUrl: r.finalUrl };
  };
  const res = await resolve(url, fetchFn);
  if (res.kind !== "blyg") return { kind: res.kind, feedUrl: res.feedUrl || null };
  const mr = await transport.get(res.manifestUrl);
  const manifest = parseManifest(JSON.parse(mr.body));
  const siteMismatch = !!manifest.site && manifest.site !== res.origin;
  return {
    kind: "blyg", origin: res.origin, manifest,
    feedUrl: res.origin + manifest.feed, siteMismatch,
  };
}

// Origin-scoped in-memory archive (reader state is per-session).
export class InMemoryArchive {
  constructor() { this.byOrigin = new Map(); }
  _o(origin) {
    if (!this.byOrigin.has(origin)) this.byOrigin.set(origin, new Map());
    return this.byOrigin.get(origin);
  }
  get(origin, id) { const e = this._o(origin).get(id); return e ? e.state : null; }
  watermark(origin, id) { const e = this._o(origin).get(id); return e ? e.watermark : 0; }
  put(origin, id, state) {
    const e = this._o(origin).get(id) || { watermark: 0, state: null };
    e.state = state;
    e.watermark = Math.max(e.watermark, Number(state.version || 0));
    this._o(origin).set(id, e);
  }
  rollToNull(origin, id) {
    const e = this._o(origin).get(id) || { watermark: 0, state: null };
    e.state = null;
    this._o(origin).set(id, e);
  }
  bumpWatermark(origin, id, version) {
    const e = this._o(origin).get(id) || { watermark: 0, state: null };
    e.watermark = Math.max(e.watermark, version);
    this._o(origin).set(id, e);
  }
  knownIds(origin) { return [...this._o(origin).keys()]; }
}

function stateFromItem(item) {
  return {
    version: item.version, content_hash: item.content_hash, kind: item.kind,
    updated: item.updated, content_md: item.content_md,
    content_html: item.content_html, page: item.page,
  };
}

export class Reconciler {
  constructor(transport, archive) {
    this.transport = transport;
    this.archive = archive;
  }

  async _fetchItem(url) {
    const r = await this.transport.get(url);
    if (r.status !== 200) return null;
    try { return parseItem(JSON.parse(r.body)); } catch { return null; }
  }

  async _advance(origin, item, result) {
    const localState = this.archive.get(origin, item.id);
    const wm = this.archive.watermark(origin, item.id);
    const localHash = localState ? localState.content_hash : null;
    const verdict = watermarkCheck(wm, localHash, item);
    if (verdict === REGRESSION) {
      result.discrepancies.push(discrepancy("regression", origin, item.id,
        `fetched v${item.version} < watermark v${wm}`));
      return;
    }
    if (verdict === STEALTH_EDIT) {
      result.discrepancies.push(discrepancy("stealth_edit", origin, item.id,
        `v${item.version} content_hash changed`));
    }
    if (item.kind !== "withdrawn" && (await contentHash(item.content_md)) !== item.content_hash) {
      result.discrepancies.push(discrepancy("hash_mismatch", origin, item.id,
        "content_hash does not match content_md"));
    }
    let localItem = null;
    if (localState) {
      localItem = { kind: localState.kind, updated: localState.updated,
                    version: localState.version, content_hash: localState.content_hash };
    }
    const roll = rollup(localItem, item);
    if (roll.withdrawn) {
      this.archive.rollToNull(origin, item.id);
      this.archive.bumpWatermark(origin, item.id, item.version);
    } else {
      this.archive.put(origin, item.id, stateFromItem(roll.item));
    }
  }

  async reconcile(subscription) {
    const result = { fetched: 0, discrepancies: [] };
    const origin = subscription.origin;

    // 1. Feed trigger (lossy).
    const feedResp = await this.transport.get(subscription.feedUrl);
    const triggered = feedResp.status === 200 ? parseFeed(feedResp.body) : [];
    for (const entry of triggered) {
      if (entry.item_url) {
        const item = await this._fetchItem(entry.item_url);
        if (item) { await this._advance(origin, item, result); result.fetched += 1; }
      }
    }

    // 2. Index diff (total reconciliation).
    const indexUrl = origin + subscription.manifest.items;
    const idxResp = await this.transport.get(indexUrl);
    if (idxResp.status === 200) {
      let entries = [];
      try { entries = parseIndex(JSON.parse(idxResp.body)).entries; } catch { entries = []; }
      for (const e of entries) {
        const local = this.archive.get(origin, e.id);
        const wm = this.archive.watermark(origin, e.id);
        if (local === null && wm >= e.version) continue;
        if (local !== null && local.version >= e.version) continue;
        const item = await this._fetchItem(`${origin}items/${e.id}.json`);
        if (item) { await this._advance(origin, item, result); result.fetched += 1; }
      }
    }
    return result;
  }
}
