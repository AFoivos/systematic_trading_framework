from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.paths import DashboardPaths, get_paths


class LayoutStore:
    def __init__(self, paths: DashboardPaths | None = None) -> None:
        self.paths = paths or get_paths()
        self.paths.layouts_root.mkdir(parents=True, exist_ok=True)

    def list_layouts(self) -> list[dict[str, Any]]:
        layouts: list[dict[str, Any]] = []
        for path in sorted(self.paths.layouts_root.glob("*.json")):
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            layouts.append(
                {
                    "layout_id": payload.get("layout_id") or path.stem,
                    "name": payload.get("name") or path.stem,
                    "path": str(path),
                    "updated_at": payload.get("updated_at"),
                }
            )
        return layouts

    def save_layout(self, payload: dict[str, Any]) -> dict[str, Any]:
        layout_id = str(payload.get("layout_id") or self._slug(payload.get("name")) or uuid4().hex)
        clean_id = self._slug(layout_id)
        if not clean_id:
            clean_id = uuid4().hex
        out = dict(payload)
        out["layout_id"] = clean_id
        path = self._layout_path(clean_id)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(out, handle, indent=2, sort_keys=True)
        return out

    def load_layout(self, layout_id: str) -> dict[str, Any]:
        path = self._layout_path(layout_id)
        if not path.exists():
            raise FileNotFoundError(f"Unknown layout_id: {layout_id}")
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}

    def _layout_path(self, layout_id: str) -> Path:
        clean_id = self._slug(layout_id)
        return self.paths.layouts_root / f"{clean_id}.json"

    @staticmethod
    def _slug(value: Any) -> str:
        raw = str(value or "").strip().lower()
        raw = re.sub(r"[^a-z0-9_.-]+", "-", raw)
        return raw.strip("-")

