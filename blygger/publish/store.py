# blygger/publish/store.py
"""Private canonical store: every version of every item, plus manifest + blogroll
metadata. Nothing here is served directly (spec 5.2, 8)."""
import json
from pathlib import Path


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        (self.root / "items").mkdir(parents=True, exist_ok=True)

    def _item_path(self, item_id: str) -> Path:
        return self.root / "items" / f"{item_id}.json"

    def _read(self, path: Path):
        return json.loads(path.read_text("utf-8")) if path.exists() else None

    def _write(self, path: Path, data) -> None:
        path.write_text(json.dumps(data, indent=2, sort_keys=True), "utf-8")

    # ---- items ----
    def create_item(self, item_id: str, authored_kind: str, created: str) -> None:
        if self._item_path(item_id).exists():
            return
        self._write(self._item_path(item_id),
                    {"authored_kind": authored_kind, "created": created, "versions": []})

    def add_version(self, item_id: str, version_record: dict) -> None:
        rec = self._read(self._item_path(item_id))
        version_record.setdefault("pinned", False)
        rec["versions"].append(version_record)
        self._write(self._item_path(item_id), rec)

    def get_item(self, item_id: str):
        return self._read(self._item_path(item_id))

    def set_pinned(self, item_id: str, version: int) -> None:
        rec = self._read(self._item_path(item_id))
        for v in rec["versions"]:
            if v["version"] == version:
                v["pinned"] = True
        self._write(self._item_path(item_id), rec)

    def all_item_ids(self):
        return [p.stem for p in (self.root / "items").glob("*.json")]

    # ---- manifest / blogroll metadata ----
    def set_manifest_meta(self, meta: dict) -> None:
        self._write(self.root / "manifest.json", meta)

    def get_manifest_meta(self):
        return self._read(self.root / "manifest.json") or {}

    def set_blogroll(self, entries) -> None:
        self._write(self.root / "blogroll.json", entries)

    def get_blogroll(self):
        return self._read(self.root / "blogroll.json") or []
