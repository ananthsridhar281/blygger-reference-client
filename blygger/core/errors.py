"""Publish-side hard errors; read-side inspectable discrepancies (spec 8)."""
from dataclasses import dataclass


class PublishError(Exception):
    """Raised when a publish operation would produce a non-conformant surface."""


@dataclass(frozen=True)
class Discrepancy:
    type: str     # "regression" | "stealth_edit" | "hash_mismatch" | "malformed" | "site_mismatch"
    origin: str
    id: str
    detail: str
