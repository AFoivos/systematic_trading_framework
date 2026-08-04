from __future__ import annotations

from pathlib import Path

from scripts.generate_ftmo_v2_suite import (
    ANCHOR_DATASET_ID,
    EXPECTED_FILENAMES,
    MODEL_INSTALL_DIR,
    MODEL_NAME,
    OUTPUT_DIR,
)
from src.utils.config import load_experiment_config
from src.utils.run_metadata import compute_config_hash


def test_ftmo_v2_matrix_is_standalone_and_reuses_one_oos_anchor() -> None:
    paths = [OUTPUT_DIR / filename for filename in EXPECTED_FILENAMES]
    assert all(path.is_file() for path in paths)
    assert len(paths) == 24

    configs = [load_experiment_config(path) for path in paths]
    anchor = configs[0]
    anchor_hash, _ = compute_config_hash(anchor)
    expected_cache_id = f"{ANCHOR_DATASET_ID}_{anchor_hash[:8]}"
    expected_cache_suffix = f"data/processed/processed/{expected_cache_id}/dataset.csv"

    assert anchor["model"]["kind"] == "lightgbm_regressor"
    assert anchor["model"]["final_refit"] is True
    assert anchor["logging"]["save_model"] is True
    assert anchor["logging"]["install_model"] is True
    assert anchor["logging"]["model_name"] == MODEL_NAME
    assert anchor["logging"]["model_install_dir"].endswith(MODEL_INSTALL_DIR)
    assert anchor["data"]["storage"]["save_processed"] is True

    for cfg in configs[1:]:
        assert cfg["model"]["kind"] == "none"
        assert cfg["model"]["pred_is_oos_col"] == "pred_is_oos"
        assert cfg["backtest"]["oos_mode"] == "strict"
        assert cfg["data"]["storage"]["dataset_id"] == expected_cache_id
        assert cfg["data"]["storage"]["load_path"].endswith(expected_cache_suffix)
        assert cfg["data"]["storage"]["save_processed"] is False
        assert cfg["logging"]["save_model"] is False
        assert cfg["research_metadata"]["model_training_performed"] is False
        assert cfg["research_metadata"]["oos_cache_anchor_config_hash_sha256"] == anchor_hash


def test_ftmo_v2_matrix_covers_soft_risk_session_threshold_and_cost_hypotheses() -> None:
    combined_min = load_experiment_config(OUTPUT_DIR / EXPECTED_FILENAMES[17])
    combined_multiply = load_experiment_config(OUTPUT_DIR / EXPECTED_FILENAMES[18])
    session = load_experiment_config(OUTPUT_DIR / EXPECTED_FILENAMES[20])
    harder_threshold = load_experiment_config(OUTPUT_DIR / EXPECTED_FILENAMES[22])
    adverse_cost = load_experiment_config(OUTPUT_DIR / EXPECTED_FILENAMES[23])

    min_modifiers = combined_min["backtest"]["entry_risk_modifiers"]
    assert min_modifiers["combine"] == "min"
    assert {rule["kind"] for rule in min_modifiers["rules"]} == {
        "previous_stop",
        "column_range",
        "local_hour",
    }
    assert combined_multiply["backtest"]["entry_risk_modifiers"]["combine"] == "multiply"

    assert session["features"][-1]["step"] == "session_context"
    assert session["features"][-1]["params"]["sessions"]["liquid_12_18_utc"] == [12, 18]
    assert session["signals"]["params"]["activation_filters"][-1]["col"] == "session_liquid_12_18_utc"

    assert harder_threshold["signals"]["params"]["upper"] == 0.85
    assert harder_threshold["signals"]["params"]["lower"] == -1.0
    assert adverse_cost["risk"]["cost_per_turnover"] == 0.001625


def test_ftmo_v2_configs_do_not_use_inheritance() -> None:
    for filename in EXPECTED_FILENAMES:
        raw = (OUTPUT_DIR / filename).read_text(encoding="utf-8")
        assert "extends:" not in raw
        assert Path(filename).suffix == ".yaml"
