// ISO-8601 UTC (no milliseconds) for protocol fields; RFC-822 GMT for RSS (spec 4).
export function toIso(date) {
  return date.toISOString().replace(/\.\d{3}Z$/, "Z");
}

export function parseIso(s) {
  return new Date(s);
}

export function toRfc822(date) {
  return date.toUTCString(); // "Sat, 18 Jul 2026 09:30:00 GMT"
}

export function nowIso() {
  return toIso(new Date());
}
