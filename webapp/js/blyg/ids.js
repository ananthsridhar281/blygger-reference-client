// Item identifiers: 128 random bits -> 26 lowercase Crockford base32 chars (spec 5.1).
export const ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"; // no i, l, o, u
const LEN = 26;

export function newId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16)); // 128 bits
  let bits = 0n;
  for (const b of bytes) bits = (bits << 8n) | BigInt(b);
  const chars = [];
  for (let i = 0; i < LEN; i++) {
    chars.push(ALPHABET[Number(bits & 31n)]);
    bits >>= 5n;
  }
  return chars.reverse().join("");
}

export function isValidId(value) {
  return typeof value === "string" && value.length === LEN &&
    [...value].every((c) => ALPHABET.includes(c));
}
