from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STANDALONE_DIR = PROJECT_ROOT / "integrations/ctrader_model06/standalone"
DUMP_PATH = STANDALONE_DIR / "model06_lightgbm_dump.json"
CONTRACT_PATH = STANDALONE_DIR / "model06_contract.json"
REFERENCE_PATH = STANDALONE_DIR / "model06_python_reference.csv"
OUTPUT_PATH = STANDALONE_DIR / "Model06Predictor.cs"


MISSING_NONE = 0
MISSING_ZERO = 1
MISSING_NAN = 2


class FlatModel:
    def __init__(self) -> None:
        self.feature: list[int] = []
        self.threshold: list[float] = []
        self.left: list[int] = []
        self.right: list[int] = []
        self.leaf: list[float] = []
        self.default_left: list[int] = []
        self.missing_type: list[int] = []
        self.roots: list[int] = []
        self.decision_types: set[str] = set()
        self.missing_types_seen: set[str] = set()

    def reserve_node(self) -> int:
        index = len(self.feature)
        self.feature.append(-1)
        self.threshold.append(0.0)
        self.left.append(-1)
        self.right.append(-1)
        self.leaf.append(0.0)
        self.default_left.append(0)
        self.missing_type.append(MISSING_NONE)
        return index

    def add_tree(self, tree: dict[str, Any]) -> None:
        self.roots.append(self.add_node(tree))

    def add_node(self, node: dict[str, Any]) -> int:
        index = self.reserve_node()

        if "leaf_value" in node:
            self.leaf[index] = float(node["leaf_value"])
            return index

        decision_type = str(node.get("decision_type", "<="))
        self.decision_types.add(decision_type)
        if decision_type != "<=":
            raise RuntimeError(
                f"Unsupported LightGBM decision_type={decision_type!r}. "
                "Model06 C# generator currently supports numeric <= splits only."
            )

        missing_name = str(node.get("missing_type", "None"))
        self.missing_types_seen.add(missing_name)
        missing_code = {
            "None": MISSING_NONE,
            "Zero": MISSING_ZERO,
            "NaN": MISSING_NAN,
        }.get(missing_name)
        if missing_code is None:
            raise RuntimeError(f"Unsupported LightGBM missing_type={missing_name!r}")

        feature = int(node["split_feature"])
        threshold = node["threshold"]
        if isinstance(threshold, str):
            raise RuntimeError(
                "Categorical/string threshold found; Model06 was expected to be numeric-only."
            )

        self.feature[index] = feature
        self.threshold[index] = float(threshold)
        self.default_left[index] = 1 if bool(node.get("default_left", False)) else 0
        self.missing_type[index] = missing_code

        left_index = self.add_node(dict(node["left_child"]))
        right_index = self.add_node(dict(node["right_child"]))
        self.left[index] = left_index
        self.right[index] = right_index
        return index


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame]:
    for path in (DUMP_PATH, CONTRACT_PATH, REFERENCE_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Required export file is missing: {path}")

    model_dump = json.loads(DUMP_PATH.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    reference = pd.read_csv(REFERENCE_PATH)
    return model_dump, contract, reference


def validate_contract(model_dump: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    feature_order = [str(x) for x in contract.get("feature_order", [])]
    dump_features = [str(x) for x in model_dump.get("feature_names", [])]

    if len(feature_order) != 48:
        raise RuntimeError(f"Expected 48 contract features, got {len(feature_order)}")
    if dump_features != feature_order:
        raise RuntimeError("LightGBM feature_names do not exactly match contract feature_order")
    if str(model_dump.get("objective")) != "regression":
        raise RuntimeError(f"Expected regression objective, got {model_dump.get('objective')!r}")
    if bool(model_dump.get("average_output", False)):
        raise RuntimeError("average_output=true is not supported/expected for Model06")
    if int(model_dump.get("num_class", 1)) != 1:
        raise RuntimeError("Model06 must have num_class=1")
    if int(model_dump.get("num_tree_per_iteration", 1)) != 1:
        raise RuntimeError("Model06 must have one tree per iteration")

    tree_info = list(model_dump.get("tree_info", []) or [])
    expected_trees = int(contract.get("tree_count", 0) or 0)
    if len(tree_info) != expected_trees:
        raise RuntimeError(
            f"Tree-count mismatch: dump={len(tree_info)}, contract={expected_trees}"
        )
    return feature_order


def build_flat_model(model_dump: dict[str, Any]) -> FlatModel:
    flat = FlatModel()
    for tree_entry in list(model_dump.get("tree_info", []) or []):
        structure = dict(tree_entry["tree_structure"])
        flat.add_tree(structure)
    return flat


def evaluate_raw(flat: FlatModel, features: np.ndarray) -> float:
    total = 0.0
    for root in flat.roots:
        node = root
        while flat.feature[node] >= 0:
            feature_index = flat.feature[node]
            value = float(features[feature_index])
            missing = flat.missing_type[node]

            if math.isnan(value):
                go_left = bool(flat.default_left[node])
            elif missing == MISSING_ZERO and value == 0.0:
                go_left = bool(flat.default_left[node])
            else:
                go_left = value <= flat.threshold[node]

            node = flat.left[node] if go_left else flat.right[node]

        total += flat.leaf[node]
    return total


def service_prediction(raw_prediction: float) -> float:
    # src.models.artifacts.predict_with_model_bundle stores regression predictions
    # in a float32 Series before the service converts the scalar back to Python float.
    return float(np.float32(raw_prediction))


def parity_test(flat: FlatModel, feature_order: list[str], reference: pd.DataFrame) -> dict[str, float]:
    required = feature_order + ["pred_ret"]
    missing = [name for name in required if name not in reference.columns]
    if missing:
        raise RuntimeError(f"Reference CSV missing columns: {missing}")

    predicted: list[float] = []
    expected: list[float] = []

    for row in reference.itertuples(index=False):
        mapping = row._asdict()
        x = np.asarray([float(mapping[name]) for name in feature_order], dtype=np.float64)
        raw = evaluate_raw(flat, x)
        predicted.append(service_prediction(raw))
        expected.append(float(mapping["pred_ret"]))

    pred = np.asarray(predicted, dtype=np.float64)
    exp = np.asarray(expected, dtype=np.float64)
    abs_err = np.abs(pred - exp)

    metrics = {
        "rows": float(len(exp)),
        "max_abs_error": float(abs_err.max()) if len(abs_err) else float("nan"),
        "mean_abs_error": float(abs_err.mean()) if len(abs_err) else float("nan"),
        "exact_float32_matches": float(np.sum(pred == exp)),
    }

    if len(abs_err) and metrics["max_abs_error"] > 1e-7:
        worst = int(np.argmax(abs_err))
        raise RuntimeError(
            "Tree-dump evaluator failed parity against Python reference: "
            f"max_abs_error={metrics['max_abs_error']:.17g}, "
            f"row={worst}, expected={exp[worst]:.17g}, got={pred[worst]:.17g}"
        )

    return metrics


def cs_double(value: float) -> str:
    if math.isnan(value):
        return "double.NaN"
    if math.isinf(value):
        return "double.PositiveInfinity" if value > 0 else "double.NegativeInfinity"
    text = format(float(value), ".17g")
    if "e" not in text.lower() and "." not in text:
        text += ".0"
    return text


def emit_numeric_array(
    name: str,
    cs_type: str,
    values: list[int] | list[float],
    formatter,
    per_line: int = 16,
) -> str:
    lines = [f"        private static readonly {cs_type}[] {name} = new {cs_type}[]", "        {"]
    for i in range(0, len(values), per_line):
        chunk = values[i : i + per_line]
        lines.append("            " + ", ".join(formatter(v) for v in chunk) + ",")
    lines.append("        };\n")
    return "\n".join(lines)


def emit_string_array(name: str, values: list[str], per_line: int = 4) -> str:
    def quote(value: str) -> str:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    lines = [f"        public static readonly string[] {name} = new string[]", "        {"]
    for i in range(0, len(values), per_line):
        lines.append("            " + ", ".join(quote(v) for v in values[i : i + per_line]) + ",")
    lines.append("        };\n")
    return "\n".join(lines)


def generate_csharp(flat: FlatModel, feature_order: list[str], contract: dict[str, Any]) -> str:
    feature_count = len(feature_order)
    model_name = str(contract.get("model_name", "model_06_vwap_plus_robust_z"))

    parts: list[str] = []
    parts.append(
        "// <auto-generated>\n"
        "// Generated from the validated LightGBM dump for Model06.\n"
        "// Do not hand-edit. Regenerate with integrations/ctrader_model06/generate_model06_csharp.py.\n"
        "// Predict() intentionally casts the raw LightGBM sum to System.Single and back to double\n"
        "// to reproduce the float32 pred_ret storage used by the Python execution bundle.\n"
        "// </auto-generated>\n\n"
        "using System;\n\n"
        "namespace CTraderModel06Standalone\n"
        "{\n"
        "    public static class Model06Predictor\n"
        "    {\n"
        f"        public const string ModelName = \"{model_name}\";\n"
        f"        public const int FeatureCount = {feature_count};\n"
        f"        public const int TreeCount = {len(flat.roots)};\n"
        f"        public const int NodeCount = {len(flat.feature)};\n\n"
    )

    parts.append(emit_string_array("FeatureOrder", feature_order))
    parts.append(emit_numeric_array("TreeRoots", "int", flat.roots, lambda v: str(int(v))))
    parts.append(emit_numeric_array("FeatureIndex", "int", flat.feature, lambda v: str(int(v))))
    parts.append(emit_numeric_array("Threshold", "double", flat.threshold, cs_double, per_line=8))
    parts.append(emit_numeric_array("LeftChild", "int", flat.left, lambda v: str(int(v))))
    parts.append(emit_numeric_array("RightChild", "int", flat.right, lambda v: str(int(v))))
    parts.append(emit_numeric_array("LeafValue", "double", flat.leaf, cs_double, per_line=8))
    parts.append(emit_numeric_array("DefaultLeft", "byte", flat.default_left, lambda v: str(int(v)), per_line=32))
    parts.append(emit_numeric_array("MissingType", "byte", flat.missing_type, lambda v: str(int(v)), per_line=32))

    parts.append(
        "        public static double Predict(double[] features)\n"
        "        {\n"
        "            return (double)(float)PredictRaw(features);\n"
        "        }\n\n"
        "        public static double PredictRaw(double[] features)\n"
        "        {\n"
        "            if (features == null)\n"
        "                throw new ArgumentNullException(nameof(features));\n"
        "            if (features.Length != FeatureCount)\n"
        "                throw new ArgumentException($\"Expected {FeatureCount} features, got {features.Length}.\", nameof(features));\n\n"
        "            double total = 0.0;\n"
        "            for (int tree = 0; tree < TreeRoots.Length; tree++)\n"
        "                total += EvaluateTree(TreeRoots[tree], features);\n"
        "            return total;\n"
        "        }\n\n"
        "        private static double EvaluateTree(int node, double[] features)\n"
        "        {\n"
        "            while (FeatureIndex[node] >= 0)\n"
        "            {\n"
        "                int feature = FeatureIndex[node];\n"
        "                double value = features[feature];\n"
        "                bool goLeft;\n\n"
        "                if (double.IsNaN(value))\n"
        "                {\n"
        "                    goLeft = DefaultLeft[node] != 0;\n"
        "                }\n"
        "                else if (MissingType[node] == 1 && value == 0.0)\n"
        "                {\n"
        "                    goLeft = DefaultLeft[node] != 0;\n"
        "                }\n"
        "                else\n"
        "                {\n"
        "                    goLeft = value <= Threshold[node];\n"
        "                }\n\n"
        "                node = goLeft ? LeftChild[node] : RightChild[node];\n"
        "            }\n\n"
        "            return LeafValue[node];\n"
        "        }\n"
        "    }\n"
        "}\n"
    )

    return "".join(parts)


def main() -> None:
    print("=" * 72)
    print("MODEL06 LIGHTGBM -> STANDALONE C#")
    print("=" * 72)

    model_dump, contract, reference = load_inputs()
    feature_order = validate_contract(model_dump, contract)
    flat = build_flat_model(model_dump)

    print(f"Features:       {len(feature_order)}")
    print(f"Trees:          {len(flat.roots)}")
    print(f"Flat nodes:     {len(flat.feature):,}")
    print(f"Decision types: {sorted(flat.decision_types)}")
    print(f"Missing types:  {sorted(flat.missing_types_seen)}")

    metrics = parity_test(flat, feature_order, reference)
    rows = int(metrics["rows"])
    exact = int(metrics["exact_float32_matches"])
    print()
    print("PYTHON DUMP-EVALUATOR PARITY")
    print(f"Rows:               {rows}")
    print(f"Exact matches:      {exact}/{rows}")
    print(f"Max abs error:      {metrics['max_abs_error']:.17g}")
    print(f"Mean abs error:     {metrics['mean_abs_error']:.17g}")

    source = generate_csharp(flat, feature_order, contract)
    OUTPUT_PATH.write_text(source, encoding="utf-8")

    print()
    print(f"Saved C# predictor: {OUTPUT_PATH}")
    print(f"C# source size:     {OUTPUT_PATH.stat().st_size / 1024 / 1024:.2f} MiB")
    print()
    print("NEXT: compile Model06Predictor.cs and run C# parity against model06_python_reference.csv")
    print("=" * 72)


if __name__ == "__main__":
    main()
