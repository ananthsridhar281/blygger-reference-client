// localStorage-backed settings: GitHub target + PAT + blyg origin URL.
const KEY = "blygger-web-settings";

const DEFAULTS = {
  owner: "",
  repo: "",
  branch: "main",
  basePath: "",      // commit files at repo root by default
  pat: "",           // fine-grained PAT, contents:write (sensitive)
  originUrl: "",     // public URL of the blyg (stamped into emitted files)
  title: "",
  authorName: "",
};

export function loadSettings() {
  try {
    return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) || "{}") };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveSettings(settings) {
  localStorage.setItem(KEY, JSON.stringify({ ...DEFAULTS, ...settings }));
}

export function settingsComplete(s) {
  return !!(s.owner && s.repo && s.pat && s.originUrl);
}
