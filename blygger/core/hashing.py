"""content_hash covers content_md only (spec 5.1)."""
import hashlib


def content_hash(content_md: str) -> str:
    return "sha256:" + hashlib.sha256(content_md.encode("utf-8")).hexdigest()
