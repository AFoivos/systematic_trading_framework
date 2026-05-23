from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import _frontend_index_path, _resolve_frontend_asset


def test_frontend_helpers_resolve_existing_asset_and_fallback_index(tmp_path: Path) -> None:
    dist_root = tmp_path / "dist"
    assets_root = dist_root / "assets"
    assets_root.mkdir(parents=True)
    (dist_root / "index.html").write_text("<html></html>", encoding="utf-8")
    (assets_root / "app.js").write_text("console.log('ok');", encoding="utf-8")

    assert _frontend_index_path(dist_root) == dist_root / "index.html"
    assert _resolve_frontend_asset(dist_root, "assets/app.js") == assets_root / "app.js"
    assert _resolve_frontend_asset(dist_root, "workspace/layout") == dist_root / "index.html"


def test_frontend_helper_rejects_path_traversal(tmp_path: Path) -> None:
    dist_root = tmp_path / "dist"
    dist_root.mkdir(parents=True)
    (dist_root / "index.html").write_text("<html></html>", encoding="utf-8")

    assert _resolve_frontend_asset(dist_root, "../secrets.txt") is None
