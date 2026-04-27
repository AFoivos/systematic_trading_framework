#!/bin/bash

# Download Dukascopy 30-minute BID and ASK OHLCV CSV files for the FTMO
# opening range breakout universe.
#
# First run:
#   chmod +x scripts/download_dukascopy_30m.sh
#   ./scripts/download_dukascopy_30m.sh
#
# Test run:
#   FROM_DATE=2024-01-01 TO_DATE=2024-02-01 ./scripts/download_dukascopy_30m.sh
#
# Full run:
#   FROM_DATE=2020-01-01 TO_DATE=2026-04-28 ./scripts/download_dukascopy_30m.sh

#!/bin/bash

set -euo pipefail

FROM_DATE="${FROM_DATE:-2020-01-01}"
TO_DATE="${TO_DATE:-2026-04-28}"
OUT_DIR="${OUT_DIR:-data/raw/dukascopy_30m}"

if ! command -v npx >/dev/null 2>&1; then
  echo "ERROR: npx is required. Install Node.js/npm, then rerun this script." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

echo "Downloading Dukascopy 30-minute data"
echo "Date range: $FROM_DATE to $TO_DATE"
echo "Output directory: $OUT_DIR"
echo

while IFS='|' read -r FRAMEWORK_SYMBOL INSTRUMENT FILE_SYMBOL; do
  if [ -z "$FRAMEWORK_SYMBOL" ]; then
    continue
  fi

  for PRICE_TYPE in bid ask; do
    OUT_FILE="${FILE_SYMBOL}_30m_${PRICE_TYPE}"
    OUT_PATH="$OUT_DIR/${OUT_FILE}.csv"

    if [ -s "$OUT_PATH" ]; then
      echo "[$FRAMEWORK_SYMBOL] Skipping existing file: $OUT_PATH"
      continue
    fi

    echo "[$FRAMEWORK_SYMBOL] Downloading $PRICE_TYPE from $INSTRUMENT -> $OUT_PATH"

    npx --yes dukascopy-node \
      --instrument "$INSTRUMENT" \
      --date-from "$FROM_DATE" \
      --date-to "$TO_DATE" \
      --timeframe m30 \
      --price-type "$PRICE_TYPE" \
      --format csv \
      --volumes true \
      --date-format "YYYY-MM-DD HH:mm:ss" \
      --time-zone UTC \
      --directory "$OUT_DIR" \
      --file-name "$OUT_FILE"

    if [ ! -s "$OUT_PATH" ]; then
      echo "ERROR: Expected output file was not created or is empty: $OUT_PATH" >&2
      exit 1
    fi

    echo "[$FRAMEWORK_SYMBOL] Finished $PRICE_TYPE"
  done
done <<'INSTRUMENTS'
XAUUSD|xauusd|xauusd
US100|usatechidxusd|us100
US30|usa30idxusd|us30
SPX500|usa500idxusd|spx500
GER40|deuidxeur|ger40
INSTRUMENTS

echo
echo "Success: Dukascopy 30-minute BID and ASK downloads completed in $OUT_DIR"