// content_hash = "sha256:" + hex(SHA-256(utf8(content_md))) (spec 5.1). Async (SubtleCrypto).
export async function contentHash(contentMd) {
  const data = new TextEncoder().encode(contentMd);
  const digest = await crypto.subtle.digest("SHA-256", data);
  const hex = [...new Uint8Array(digest)]
    .map((b) => b.toString(16).padStart(2, "0")).join("");
  return "sha256:" + hex;
}
