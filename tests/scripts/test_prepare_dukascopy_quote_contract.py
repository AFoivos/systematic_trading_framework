from __future__ import annotations

import json

import pandas as pd
import pytest

from scripts.audit_quote_contract_references import audit_references
from scripts.prepare_dukascopy_30m_bid_ask_mid import _merge_bid_ask as merge_panel
from scripts.prepare_dukascopy_ftmo_mid import _merge_bid_ask as merge_single
from scripts.migrate_legacy_spread_contract import audit_legacy_csv, migrate_legacy_csv


def _side(side: str, close: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2026-01-01T00:00:00")],
            f"{side}_open": [close],
            f"{side}_high": [close],
            f"{side}_low": [close],
            f"{side}_close": [close],
            f"{side}_volume": [10.0],
        }
    )


@pytest.mark.parametrize(
    "merge,owner_keyword",
    [(merge_panel, "asset"), (merge_single, "label")],
)
def test_dukascopy_producers_emit_canonical_spread_columns(
    merge, owner_keyword: str
) -> None:
    kwargs = {owner_keyword: "test", "max_bad_spread_rate": 0.0}
    out = merge(_side("bid", 100.0), _side("ask", 100.10), **kwargs)

    assert out.loc[0, "close"] == pytest.approx(100.05)
    assert out.loc[0, "spread_close"] == pytest.approx(0.10)
    assert out.loc[0, "spread_absolute"] == pytest.approx(0.10)
    assert out.loc[0, "spread_fraction"] == pytest.approx(0.10 / 100.05)
    assert out.loc[0, "spread_bps"] == pytest.approx(10_000.0 * 0.10 / 100.05)


@pytest.mark.parametrize(
    "merge,owner_keyword",
    [(merge_panel, "asset"), (merge_single, "label")],
)
def test_dukascopy_producers_never_write_crossed_close_quotes(
    merge, owner_keyword: str
) -> None:
    kwargs = {owner_keyword: "test", "max_bad_spread_rate": 1.0}
    with pytest.raises(ValueError, match="never permits crossed"):
        merge(_side("bid", 100.10), _side("ask", 100.0), **kwargs)


@pytest.mark.parametrize(
    "merge,owner_keyword",
    [(merge_panel, "asset"), (merge_single, "label")],
)
def test_dukascopy_producers_refuse_silent_bid_ask_join_loss(
    merge,
    owner_keyword: str,
) -> None:
    bid = _side("bid", 100.0)
    ask = _side("ask", 100.10)
    ask["timestamp"] = ask["timestamp"] + pd.Timedelta(minutes=30)
    kwargs = {owner_keyword: "test", "max_bad_spread_rate": 0.0}

    with pytest.raises(ValueError, match="refuses silent inner-join loss"):
        merge(bid, ask, **kwargs)


def test_legacy_migration_preserves_old_value_and_remains_research_blocked(
    tmp_path,
) -> None:
    source = tmp_path / "legacy.csv"
    legacy = merge_panel(
        _side("bid", 100.0),
        _side("ask", 100.10),
        asset="test",
        max_bad_spread_rate=0.0,
    )
    legacy["spread_bps"] = legacy["spread_fraction"]
    legacy = legacy.drop(columns=["spread_absolute", "spread_fraction"])
    legacy.to_csv(source, index=False)
    source_before = source.read_bytes()

    audit = audit_legacy_csv(source)
    assert audit["spread_bps_semantics"] == "LEGACY_FRACTION"
    output, sidecar = migrate_legacy_csv(source, output_path=tmp_path / "migrated.csv")
    migrated = pd.read_csv(output)
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))

    assert source.read_bytes() == source_before
    assert migrated.loc[0, "spread_bps_legacy_fraction"] == pytest.approx(
        legacy.loc[0, "spread_bps"]
    )
    assert migrated.loc[0, "spread_bps"] == pytest.approx(
        10_000.0 * migrated.loc[0, "spread_fraction"]
    )
    assert bool(metadata["research_eligible"]) is False
    assert metadata["classification"] == "REGENERATE_REQUIRED"


def test_legacy_migration_refuses_to_overwrite_conflicting_absolute_spread(
    tmp_path,
) -> None:
    source = tmp_path / "legacy-conflict.csv"
    legacy = merge_panel(
        _side("bid", 100.0),
        _side("ask", 100.10),
        asset="test",
        max_bad_spread_rate=0.0,
    )
    legacy["spread_bps"] = legacy["spread_fraction"]
    legacy["spread_close"] = 99.0
    legacy = legacy.drop(columns=["spread_absolute", "spread_fraction"])
    legacy.to_csv(source, index=False)

    with pytest.raises(ValueError, match="spread_close conflicts"):
        migrate_legacy_csv(source, output_path=tmp_path / "must-not-exist.csv")

    assert not (tmp_path / "must-not-exist.csv").exists()


def test_quote_reference_audit_includes_shell_and_csv_text_sources(tmp_path) -> None:
    scripts = tmp_path / "scripts"
    configs = tmp_path / "config"
    scripts.mkdir()
    configs.mkdir()
    (scripts / "download.sh").write_text("PRICE_SIDE=bid\n", encoding="utf-8")
    (configs / "fixture.csv").write_text(
        "timestamp,spread_bps\n1,2\n", encoding="utf-8"
    )

    audit = audit_references(tmp_path)
    observed = {item["path"] for item in audit["occurrences"]}

    assert "scripts/download.sh" in observed
    assert "config/fixture.csv" in observed
