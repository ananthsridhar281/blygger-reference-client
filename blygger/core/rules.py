# blygger/core/rules.py
"""Pure spec rules: rollup, watermark, resolution (spec 12, 13). No I/O."""
from dataclasses import dataclass
from typing import Optional
from .model import Item

OK = "ok"
REGRESSION = "regression"
STEALTH_EDIT = "stealth_edit"


@dataclass(frozen=True)
class RollupResult:
    item: Optional[Item]
    withdrawn: bool


def rollup(local: Optional[Item], fetched: Item) -> RollupResult:
    if local is None:
        winner = fetched
    elif fetched.version > local.version:
        winner = fetched
    elif fetched.version == local.version and fetched.updated >= local.updated:
        winner = fetched
    else:
        winner = local
    if winner.kind == "withdrawn":
        return RollupResult(item=None, withdrawn=True)
    return RollupResult(item=winner, withdrawn=False)


def watermark_check(watermark: int, local_hash: Optional[str], fetched: Item) -> str:
    if fetched.version < watermark:
        return REGRESSION
    if fetched.version == watermark and local_hash is not None \
            and fetched.content_hash != local_hash:
        return STEALTH_EDIT
    return OK
