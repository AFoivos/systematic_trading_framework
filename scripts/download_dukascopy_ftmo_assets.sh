#!/bin/bash

# Download Dukascopy BID/ASK OHLCV data for the FTMO asset/timeframe set and
# write canonical mid-price CSVs under data/raw/ftmo_assets.
#
# Defaults:
#   FROM_DATE=2020-01-01
#   TO_DATE=2026-04-28
#   OUT_DIR=data/raw/ftmo_assets
#   RAW_DIR=data/raw/ftmo_assets_bidask
#
# Example:
#   FROM_DATE=2024-01-01 TO_DATE=2024-02-01 ./scripts/download_dukascopy_ftmo_assets.sh

set -euo pipefail

FROM_DATE="${FROM_DATE:-2020-01-01}"
TO_DATE="${TO_DATE:-2026-04-28}"
OUT_DIR="${OUT_DIR:-data/raw/ftmo_assets}"
RAW_DIR="${RAW_DIR:-data/raw/ftmo_assets_bidask}"

if ! command -v npx >/dev/null 2>&1; then
  echo "ERROR: npx is required. Install Node.js/npm, then rerun this script." >&2
  exit 1
fi

if ! command -v python >/dev/null 2>&1; then
  echo "ERROR: python is required." >&2
  exit 1
fi

mkdir -p "$OUT_DIR" "$RAW_DIR"

echo "Downloading Dukascopy FTMO asset data"
echo "Date range: $FROM_DATE to $TO_DATE"
echo "Raw BID/ASK directory: $RAW_DIR"
echo "Output directory: $OUT_DIR"
echo

download_side() {
  FRAMEWORK_SYMBOL="$1"
  INSTRUMENT="$2"
  TIMEFRAME_LABEL="$3"
  DUKAS_TIMEFRAME="$4"
  PRICE_TYPE="$5"

  OUT_FILE="${FRAMEWORK_SYMBOL}_${TIMEFRAME_LABEL}_${PRICE_TYPE}"
  OUT_PATH="$RAW_DIR/${OUT_FILE}.csv"

  if [ -s "$OUT_PATH" ]; then
    echo "[$FRAMEWORK_SYMBOL][$TIMEFRAME_LABEL][$PRICE_TYPE] Skipping existing file: $OUT_PATH"
    return 0
  fi

  echo "[$FRAMEWORK_SYMBOL][$TIMEFRAME_LABEL][$PRICE_TYPE] Downloading $INSTRUMENT -> $OUT_PATH"
  npx --yes dukascopy-node \
    --instrument "$INSTRUMENT" \
    --date-from "$FROM_DATE" \
    --date-to "$TO_DATE" \
    --timeframe "$DUKAS_TIMEFRAME" \
    --price-type "$PRICE_TYPE" \
    --format csv \
    --volumes true \
    --date-format "YYYY-MM-DD HH:mm:ss" \
    --time-zone UTC \
    --directory "$RAW_DIR" \
    --file-name "$OUT_FILE" \
    --retries 5 \
    --retry-pause 3000 \
    --batch-size 5 \
    --batch-pause 1500

  if [ ! -s "$OUT_PATH" ]; then
    echo "ERROR: Expected output file was not created or is empty: $OUT_PATH" >&2
    exit 1
  fi
}

prepare_mid() {
  FRAMEWORK_SYMBOL="$1"
  TIMEFRAME_LABEL="$2"

  BID_PATH="$RAW_DIR/${FRAMEWORK_SYMBOL}_${TIMEFRAME_LABEL}_bid.csv"
  ASK_PATH="$RAW_DIR/${FRAMEWORK_SYMBOL}_${TIMEFRAME_LABEL}_ask.csv"
  OUT_PATH="$OUT_DIR/${FRAMEWORK_SYMBOL}_${TIMEFRAME_LABEL}.csv"

  python scripts/prepare_dukascopy_ftmo_mid.py \
    --bid-path "$BID_PATH" \
    --ask-path "$ASK_PATH" \
    --output-path "$OUT_PATH" \
    --asset "$FRAMEWORK_SYMBOL" \
    --timeframe "$TIMEFRAME_LABEL"
}

while IFS='|' read -r FRAMEWORK_SYMBOL INSTRUMENT; do
  if [ -z "$FRAMEWORK_SYMBOL" ]; then
    continue
  fi

  while IFS='|' read -r TIMEFRAME_LABEL DUKAS_TIMEFRAME; do
    if [ -z "$TIMEFRAME_LABEL" ]; then
      continue
    fi

    for PRICE_TYPE in bid ask; do
      download_side "$FRAMEWORK_SYMBOL" "$INSTRUMENT" "$TIMEFRAME_LABEL" "$DUKAS_TIMEFRAME" "$PRICE_TYPE"
    done
    prepare_mid "$FRAMEWORK_SYMBOL" "$TIMEFRAME_LABEL"
  done <<'TIMEFRAMES'
M5|m5
M15|m15
H1|h1
TIMEFRAMES
done <<'INSTRUMENTS'
XAUUSD|xauusd
EURUSD|eurusd
GBPUSD|gbpusd
US100|usatechidxusd
INSTRUMENTS

echo
echo "Success: FTMO Dukascopy files written to $OUT_DIR"
