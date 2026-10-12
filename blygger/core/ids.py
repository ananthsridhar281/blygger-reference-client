"""Item identifiers: 128 random bits as 26 lowercase Crockford base32 chars (spec 5.1)."""
import secrets

ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"  # Crockford base32: no i, l, o, u
_ALPHASET = frozenset(ALPHABET)
_LEN = 26


def new_id() -> str:
    n = int.from_bytes(secrets.token_bytes(16), "big")  # 128 bits
    chars = []
    for _ in range(_LEN):
        chars.append(ALPHABET[n & 31])
        n >>= 5
    return "".join(reversed(chars))


def is_valid_id(value: object) -> bool:
    return isinstance(value, str) and len(value) == _LEN and all(c in _ALPHASET for c in value)
