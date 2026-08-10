from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "integrations/ctrader_model06/standalone"
PREDICTOR = BASE / "Model06Predictor.cs"
FEATURES = BASE / "Model06Features.cs"
STREAMING_FEATURES = BASE / "Model06StreamingFeatures.cs"
BOT = BASE / "Model06StandaloneBacktestBot.cs"
OUTPUT = BASE / "Model06StandaloneAllInOne.cs"

USINGS = """using System;\nusing System.Collections.Generic;\nusing System.Globalization;\nusing System.Linq;\nusing cAlgo.API;\nusing cAlgo.API.Internals;\nusing CTraderModel06Standalone;\n\n"""


def namespace_part(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    marker_candidates = ["namespace CTraderModel06Standalone", "namespace cAlgo.Robots"]
    positions = [text.find(m) for m in marker_candidates if text.find(m) >= 0]
    if not positions:
        raise RuntimeError(f"No namespace marker found in {path}")
    return text[min(positions):].strip() + "\n"


def main() -> None:
    sources = (PREDICTOR, FEATURES, STREAMING_FEATURES, BOT)
    for path in sources:
        if not path.is_file():
            raise FileNotFoundError(path)

    combined = (
        "// AUTO-GENERATED STANDALONE MODEL06 cBOT\n"
        "// Contains the 800-tree predictor, validated 48-feature engines and cTrader bot.\n"
        "// Regenerate; do not hand-edit.\n\n"
        + USINGS
        + namespace_part(PREDICTOR)
        + "\n"
        + namespace_part(FEATURES)
        + "\n"
        + namespace_part(STREAMING_FEATURES)
        + "\n"
        + namespace_part(BOT)
    )
    OUTPUT.write_text(combined, encoding="utf-8")
    print(f"Saved: {OUTPUT}")
    print(f"Size: {OUTPUT.stat().st_size / 1024 / 1024:.2f} MiB")


if __name__ == "__main__":
    main()
