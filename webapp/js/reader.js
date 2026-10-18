// Reader: fetch-based transport + drive resolve + reconcile, shaping a view-model.
import { resolveSubscription, Reconciler, InMemoryArchive } from "./blyg/reconcile.js";

export function fetchTransport() {
  return {
    async get(url) {
      try {
        const res = await fetch(url, { redirect: "follow" });
        const body = await res.text();
        return { status: res.status, body, finalUrl: res.url || url };
      } catch (e) {
        // Most commonly a CORS rejection or network/offline error.
        return { status: 0, body: "", finalUrl: url, error: String(e) };
      }
    },
  };
}

export async function readBlyg({ url, local, originUrl }) {
  const transport = fetchTransport();
  const target = local ? originUrl : (url || "").trim();
  if (!target) return { error: "no URL given", target: "" };

  const sub = await resolveSubscription(transport, target);
  if (sub.kind !== "blyg") {
    return {
      error: `could not resolve as a blyg (result: ${sub.kind}). ` +
        "If this is an external site, it may be blocking cross-origin reads (CORS).",
      target,
    };
  }

  const archive = new InMemoryArchive();
  const result = await new Reconciler(transport, archive).reconcile(sub);

  const items = [];
  for (const id of archive.knownIds(sub.origin)) {
    const st = archive.get(sub.origin, id);
    if (st === null) {
      items.push({ id, withdrawn: true, version: archive.watermark(sub.origin, id),
                   kind: "withdrawn", content_html: "", updated: "" });
    } else {
      items.push({ id, withdrawn: false, version: st.version, kind: st.kind,
                   content_html: st.content_html || "", updated: st.updated || "" });
    }
  }
  items.sort((a, b) => (b.updated || "").localeCompare(a.updated || ""));

  return {
    origin: sub.origin, title: sub.manifest.title, siteMismatch: sub.siteMismatch,
    fetched: result.fetched, discrepancies: result.discrepancies, items,
  };
}
