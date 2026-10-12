"""Origin-scoped reader archive with a monotonic watermark (spec 13.1, 13.3)."""
import hashlib
import json
from pathlib import Path


def _origin_key(origin: str) -> str:
    return hashlib.sha256(origin.encode("utf-8")).hexdigest()[:16]


class Archive:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _file(self, origin: str) -> Path:
        return self.root / f"{_origin_key(origin)}.json"

    def _load(self, origin: str) -> dict:
        f = self._file(origin)
        return json.loads(f.read_text("utf-8")) if f.exists() else {"origin": origin, "items": {}}

    def _save(self, origin: str, data: dict) -> None:
        self._file(origin).write_text(json.dumps(data, indent=2, sort_keys=True), "utf-8")

    def put(self, origin: str, item_id: str, state: dict) -> None:
        data = self._load(origin)
        entry = data["items"].get(item_id, {"watermark": 0})
        entry["state"] = state
        entry["watermark"] = max(entry.get("watermark", 0), int(state.get("version", 0)))
        data["items"][item_id] = entry
        self._save(origin, data)

    def roll_to_null(self, origin: str, item_id: str) -> None:
        data = self._load(origin)
        entry = data["items"].get(item_id, {"watermark": 0})
        entry["state"] = None
        data["items"][item_id] = entry
        self._save(origin, data)

    def get(self, origin: str, item_id: str):
        entry = self._load(origin)["items"].get(item_id)
        return entry["state"] if entry else None

    def watermark(self, origin: str, item_id: str) -> int:
        entry = self._load(origin)["items"].get(item_id)
        return entry.get("watermark", 0) if entry else 0

    def bump_watermark(self, origin: str, item_id: str, version: int) -> None:
        data = self._load(origin)
        entry = data["items"].get(item_id, {"watermark": 0, "state": None})
        entry["watermark"] = max(entry.get("watermark", 0), version)
        data["items"][item_id] = entry
        self._save(origin, data)

    def known_ids(self, origin: str):
        return set(self._load(origin)["items"].keys())
