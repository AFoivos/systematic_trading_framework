from __future__ import annotations

from typing import Any

import pandas as pd


_CORE_STAGE_COLUMNS = ("open", "high", "low", "close", "volume")
_IMPORTANT_PREFIXES = ("pred_", "signal_", "action_", "target_")
_IMPORTANT_EXACT = ("pred_is_oos", "close_logret")


def _as_serializable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, pd.Timestamp):
        return value.isoformat(sep=" ")
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return str(value)


def _display_frame(df: pd.DataFrame) -> pd.DataFrame:
    index_name = str(df.index.name or "timestamp")
    out = df.reset_index()
    if out.columns[0] != index_name:
        out = out.rename(columns={out.columns[0]: index_name})
    return out


def _selected_columns(
    df: pd.DataFrame,
    *,
    added_columns: list[str],
    max_columns: int,
) -> tuple[list[str], list[str]]:
    display = _display_frame(df)
    timestamp_col = str(display.columns[0])
    ordered: list[str] = [timestamp_col]

    for col in _CORE_STAGE_COLUMNS:
        if col in display.columns and col not in ordered:
            ordered.append(col)
    for col in added_columns:
        if col in display.columns and col not in ordered:
            ordered.append(col)
    for col in display.columns:
        if col in _IMPORTANT_EXACT and col not in ordered:
            ordered.append(col)
    for col in display.columns:
        if any(str(col).startswith(prefix) for prefix in _IMPORTANT_PREFIXES) and col not in ordered:
            ordered.append(col)
    for col in display.columns:
        if col not in ordered:
            ordered.append(str(col))

    shown = ordered[:max(1, int(max_columns))]
    truncated = ordered[len(shown) :]
    return shown, truncated


def _asset_stage_payload(
    *,
    asset: str,
    current: pd.DataFrame,
    previous: pd.DataFrame | None,
    limit: int,
    max_columns: int,
) -> dict[str, Any]:
    prev_columns = list(previous.columns) if previous is not None else []
    curr_columns = list(current.columns)
    added_columns = [str(col) for col in curr_columns if col not in prev_columns]
    removed_columns = [str(col) for col in prev_columns if col not in curr_columns]
    shown_columns, truncated_columns = _selected_columns(
        current,
        added_columns=added_columns,
        max_columns=max_columns,
    )

    display = _display_frame(current)
    tail = display.loc[:, shown_columns].tail(limit).copy()
    tail_rows = [
        {str(key): _as_serializable(value) for key, value in row.items()}
        for row in tail.to_dict(orient="records")
    ]

    previous_rows = int(len(previous)) if previous is not None else 0
    return {
        "asset": str(asset),
        "rows": int(len(current)),
        "row_delta": int(len(current) - previous_rows),
        "column_count": int(len(curr_columns)),
        "column_delta": int(len(curr_columns) - len(prev_columns)),
        "added_columns": added_columns,
        "removed_columns": removed_columns,
        "shown_columns": shown_columns,
        "truncated_columns": truncated_columns,
        "tail_rows": tail_rows,
    }


def build_stage_tail_snapshot(
    *,
    stage: str,
    asset_frames: dict[str, pd.DataFrame],
    previous_asset_frames: dict[str, pd.DataFrame] | None,
    limit: int,
    max_columns: int,
    max_assets: int,
) -> dict[str, Any]:
    assets = sorted(asset_frames)[: max(1, int(max_assets))]
    payloads = []
    for asset in assets:
        payloads.append(
            _asset_stage_payload(
                asset=asset,
                current=asset_frames[asset],
                previous=(previous_asset_frames or {}).get(asset),
                limit=max(1, int(limit)),
                max_columns=max(1, int(max_columns)),
            )
        )
    return {
        "stage": str(stage),
        "asset_count": int(len(asset_frames)),
        "shown_asset_count": int(len(payloads)),
        "limit": int(limit),
        "max_columns": int(max_columns),
        "max_assets": int(max_assets),
        "assets": payloads,
    }


def format_stage_tail_snapshot(snapshot: dict[str, Any]) -> str:
    lines = [
        f"[stage_tails] stage={snapshot.get('stage')} assets={snapshot.get('shown_asset_count')}/{snapshot.get('asset_count')}",
    ]
    limit = int(snapshot.get("limit", 10) or 10)
    for asset_payload in list(snapshot.get("assets", []) or []):
        lines.append(
            "  "
            + f"asset={asset_payload.get('asset')} rows={asset_payload.get('rows')} "
            + f"row_delta={asset_payload.get('row_delta')} cols={asset_payload.get('column_count')} "
            + f"col_delta={asset_payload.get('column_delta')}"
        )
        added = list(asset_payload.get("added_columns", []) or [])
        removed = list(asset_payload.get("removed_columns", []) or [])
        lines.append(f"  added_columns={added if added else '[]'}")
        lines.append(f"  removed_columns={removed if removed else '[]'}")
        shown_columns = list(asset_payload.get("shown_columns", []) or [])
        truncated_columns = list(asset_payload.get("truncated_columns", []) or [])
        lines.append(f"  shown_columns={shown_columns}")
        if truncated_columns:
            lines.append(f"  truncated_columns={truncated_columns}")
        tail_rows = list(asset_payload.get("tail_rows", []) or [])
        if tail_rows:
            tail_df = pd.DataFrame(tail_rows)
            lines.append(f"  tail({min(limit, len(tail_rows))}):")
            table = tail_df.to_string(index=False)
            lines.extend(f"    {line}" for line in table.splitlines())
        else:
            lines.append("  tail(0): <empty>")
    return "\n".join(lines)


__all__ = ["build_stage_tail_snapshot", "format_stage_tail_snapshot"]
