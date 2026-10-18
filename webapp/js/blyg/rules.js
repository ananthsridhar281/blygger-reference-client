// Pure spec rules: rollup, watermark, resolution ladder (spec 12, 13). Port of core/rules.py.
// `fetch` is injected: fetch(url) -> { status, body (string), finalUrl }.

export const OK = "ok";
export const REGRESSION = "regression";
export const STEALTH_EDIT = "stealth_edit";

export function rollup(local, fetched) {
  let winner;
  if (local === null || local === undefined) winner = fetched;
  else if (fetched.version > local.version) winner = fetched;
  else if (fetched.version === local.version && fetched.updated >= local.updated) winner = fetched;
  else winner = local;
  if (winner.kind === "withdrawn") return { item: null, withdrawn: true };
  return { item: winner, withdrawn: false };
}

export function watermarkCheck(watermark, localHash, fetched) {
  if (fetched.version < watermark) return REGRESSION;
  if (fetched.version === watermark && localHash != null &&
      fetched.content_hash !== localHash) return STEALTH_EDIT;
  return OK;
}

// ----------------------------------------------------------------- resolve ----
const MANIFEST_EL = /<blyg:manifest>\s*([^<\s]+)\s*<\/blyg:manifest>/;
const REL_BLYG = /<link[^>]+rel=["']blyg["'][^>]*>/i;
const HREF = /href=["']([^"']+)["']/i;

function normalize(url) {
  url = url.split("#")[0].split("?")[0];
  const m = /^(https?:\/\/[^/]+)(\/.*)?$/.exec(url);
  if (m) {
    const host = m[1];
    const path = m[2] || "";
    if (path === "") return host + "/";
    const last = path.split("/").pop();
    if (!path.endsWith("/") && !last.includes(".")) return url + "/";
    return url;
  }
  return url.endsWith("/") ? url : url + "/";
}

function originOf(manifestUrl) {
  return manifestUrl.endsWith("blyg.json")
    ? manifestUrl.slice(0, -"blyg.json".length) : manifestUrl;
}

function isManifest(body) {
  try {
    const obj = JSON.parse(body);
    return obj && typeof obj === "object" && !Array.isArray(obj) && "blyg" in obj;
  } catch { return false; }
}

function schemeHost(url) {
  const m = /^(https?:\/\/[^/]+)/.exec(url);
  return m ? m[1] : url;
}

export async function resolve(url, fetch) {
  const trail = [];
  const probed = new Set();
  let budget = 6;

  async function probeManifest(manifestUrl) {
    if (budget <= 0 || probed.has(manifestUrl)) return null;
    probed.add(manifestUrl);
    budget -= 1;
    trail.push(manifestUrl);
    const res = await fetch(manifestUrl);
    if (res.status === 200 && isManifest(res.body)) {
      return { kind: "blyg", origin: originOf(res.finalUrl), manifestUrl: res.finalUrl, trail: [...trail] };
    }
    return null;
  }

  const candidate = normalize(url);
  let hit = await probeManifest(candidate + "blyg.json");
  if (hit) return hit;

  let l0Feed = null;
  if (budget > 0) {
    budget -= 1;
    trail.push(url);
    const res = await fetch(url);
    const body = res.status === 200 ? res.body : "";
    if (body) {
      if (body.includes("<rss") || body.includes("<feed")) {
        const m = MANIFEST_EL.exec(body);
        if (m) {
          hit = await probeManifest(m[1]);
          if (hit) return hit;
        } else {
          l0Feed = res.finalUrl;
        }
      } else if (/<html/i.test(body) || /<link/i.test(body)) {
        const tag = REL_BLYG.exec(body);
        if (tag) {
          const href = HREF.exec(tag[0]);
          if (href) {
            hit = await probeManifest(normalize(href[1]) + "blyg.json");
            if (hit) return hit;
          }
        }
      }
    }
  }

  const root = schemeHost(candidate);
  for (const mount of [root + "/blyg/blyg.json", root + "/blyg.json"]) {
    hit = await probeManifest(mount);
    if (hit) return hit;
  }

  if (l0Feed) return { kind: "l0", feedUrl: l0Feed, trail: [...trail] };
  return { kind: "fail", trail: [...trail] };
}
