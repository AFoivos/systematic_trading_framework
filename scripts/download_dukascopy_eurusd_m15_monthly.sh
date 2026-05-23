#!/bin/bash

# Download EURUSD Dukascopy 15-minute OHLCV CSV files in monthly chunks.
#
# This mirrors the older 30m Dukascopy scripts but downloads a single price
# stream only. It does not download BID+ASK pairs and does not build a mid-price
# file. By default PRICE_TYPE=bid because dukascopy-node requires a price side.
#
# Defaults:
#   FROM_DATE=<today UTC minus 3 years>
#   TO_DATE=<today UTC>
#   OUT_ROOT=data/raw/dukascopy/eurusd/m15
#   PRICE_TYPE=bid
#   REFRESH_LAST_CHUNK=1
#
# Examples:
#   ./scripts/download_dukascopy_eurusd_m15_monthly.sh
#   FROM_DATE=2024-01-01 TO_DATE=2024-04-01 ./scripts/download_dukascopy_eurusd_m15_monthly.sh
#
# Merge after downloading:
#   python scripts/merge_dukascopy_eurusd_m15_monthly.py

set -uo pipefail

if ! command -v npx >/dev/null 2>&1; then
  echo "ERROR: npx is required. Install Node.js/npm, then rerun this script." >&2
  exit 1
fi

if ! command -v python >/dev/null 2>&1; then
  echo "ERROR: python is required." >&2
  exit 1
fi

DEFAULT_TO_DATE="$(
  python -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).date().isoformat())'
)"
DEFAULT_FROM_DATE="$(
  python -c 'from datetime import datetime, timezone; d=datetime.now(timezone.utc).date(); print((d.replace(year=d.year-3) if not (d.month == 2 and d.day == 29) else d.replace(year=d.year-3, day=28)).isoformat())'
)"

FROM_DATE="${FROM_DATE:-$DEFAULT_FROM_DATE}"
TO_DATE="${TO_DATE:-$DEFAULT_TO_DATE}"
OUT_ROOT="${OUT_ROOT:-data/raw/dukascopy/eurusd/m15}"
MONTHLY_DIR="$OUT_ROOT/monthly"
FAILED_LOG="$OUT_ROOT/failed_downloads.txt"

FRAMEWORK_SYMBOL="${FRAMEWORK_SYMBOL:-EURUSD}"
INSTRUMENT="${INSTRUMENT:-eurusd}"
FILE_SYMBOL="${FILE_SYMBOL:-eurusd}"
TIMEFRAME_LABEL="${TIMEFRAME_LABEL:-m15}"
DUKAS_TIMEFRAME="${DUKAS_TIMEFRAME:-m15}"
PRICE_TYPE="${PRICE_TYPE:-bid}"
REFRESH_LAST_CHUNK="${REFRESH_LAST_CHUNK:-1}"

case "$FROM_DATE" in
  [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9])
    ;;
  *)
    echo "ERROR: FROM_DATE must use YYYY-MM-DD format, got: $FROM_DATE" >&2
    exit 1
    ;;
esac

case "$TO_DATE" in
  [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9])
    ;;
  *)
    echo "ERROR: TO_DATE must use YYYY-MM-DD format, got: $TO_DATE" >&2
    exit 1
    ;;
esac

case "$REFRESH_LAST_CHUNK" in
  0|1)
    ;;
  *)
    echo "ERROR: REFRESH_LAST_CHUNK must be 0 or 1, got: $REFRESH_LAST_CHUNK" >&2
    exit 1
    ;;
esac

mkdir -p "$MONTHLY_DIR" || exit 1
: > "$FAILED_LOG" || exit 1

echo "Downloading Dukascopy EURUSD 15-minute monthly data"
echo "Date range: $FROM_DATE to $TO_DATE"
echo "Instrument: $INSTRUMENT"
echo "Price stream: $PRICE_TYPE"
echo "Output root: $OUT_ROOT"
echo "Monthly directory: $MONTHLY_DIR"
echo "Refresh last chunk: $REFRESH_LAST_CHUNK"
echo "Failure log: $FAILED_LOG"
echo

log_failure() {
  MESSAGE="$1"
  echo "$MESSAGE" >> "$FAILED_LOG"
  echo "FAILED: $MESSAGE" >&2
}

download_month() {
  MONTH_LABEL="$1"
  CHUNK_FROM="$2"
  CHUNK_TO="$3"
  OUT_DIR="$4"
  IS_LAST_CHUNK="$5"

  OUT_FILE="${FILE_SYMBOL}_${TIMEFRAME_LABEL}"
  OUT_PATH="$OUT_DIR/${OUT_FILE}.csv"

  if [ -s "$OUT_PATH" ] && { [ "$IS_LAST_CHUNK" -ne 1 ] || [ "$REFRESH_LAST_CHUNK" -ne 1 ]; }; then
    echo "[$MONTH_LABEL][$FRAMEWORK_SYMBOL] Skipping existing non-empty file: $OUT_PATH"
    return 0
  fi

  echo "[$MONTH_LABEL][$FRAMEWORK_SYMBOL] Downloading $INSTRUMENT $PRICE_TYPE from $CHUNK_FROM to $CHUNK_TO -> $OUT_PATH"

  npx --yes dukascopy-node \
    --instrument "$INSTRUMENT" \
    --date-from "$CHUNK_FROM" \
    --date-to "$CHUNK_TO" \
    --timeframe "$DUKAS_TIMEFRAME" \
    --price-type "$PRICE_TYPE" \
    --format csv \
    --volumes true \
    --date-format "YYYY-MM-DD HH:mm:ss" \
    --time-zone UTC \
    --directory "$OUT_DIR" \
    --file-name "$OUT_FILE" \
    --retries 5 \
    --retry-pause 3000 \
    --batch-size 5 \
    --batch-pause 1500

  STATUS=$?
  if [ "$STATUS" -ne 0 ]; then
    log_failure "$MONTH_LABEL|$FRAMEWORK_SYMBOL|$INSTRUMENT|$PRICE_TYPE|$CHUNK_FROM|$CHUNK_TO|exit_status=$STATUS"
    return 0
  fi

  if [ ! -s "$OUT_PATH" ]; then
    log_failure "$MONTH_LABEL|$FRAMEWORK_SYMBOL|$INSTRUMENT|$PRICE_TYPE|$CHUNK_FROM|$CHUNK_TO|missing_or_empty_output=$OUT_PATH"
    return 0
  fi

  echo "[$MONTH_LABEL][$FRAMEWORK_SYMBOL] Finished"
  return 0
}

CHUNKS_FILE="$(mktemp)"
trap 'rm -f "$CHUNKS_FILE"' EXIT

python - "$FROM_DATE" "$TO_DATE" > "$CHUNKS_FILE" <<'PY'
from __future__ import annotations

import calendar
import sys
from datetime import date


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def add_month(value: date) -> date:
    year = value.year + int(value.month == 12)
    month = 1 if value.month == 12 else value.month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


start = parse_date(sys.argv[1])
end = parse_date(sys.argv[2])
if start >= end:
    raise SystemExit(f"FROM_DATE must be before TO_DATE, got {start} >= {end}")

current = start
while current < end:
    month_start = date(current.year, current.month, 1)
    next_month = add_month(month_start)
    chunk_end = min(next_month, end)
    print(f"{current:%Y-%m}|{current.isoformat()}|{chunk_end.isoformat()}")
    current = chunk_end
PY

while IFS='|' read -r MONTH_LABEL CHUNK_FROM CHUNK_TO; do
  if [ -z "$MONTH_LABEL" ]; then
    continue
  fi

  OUT_DIR="$MONTHLY_DIR/$MONTH_LABEL"
  mkdir -p "$OUT_DIR" || exit 1

  echo "=== $MONTH_LABEL: $CHUNK_FROM to $CHUNK_TO ==="
  IS_LAST_CHUNK=0
  if [ "$CHUNK_TO" = "$TO_DATE" ]; then
    IS_LAST_CHUNK=1
  fi

  download_month "$MONTH_LABEL" "$CHUNK_FROM" "$CHUNK_TO" "$OUT_DIR" "$IS_LAST_CHUNK"
  echo
done < "$CHUNKS_FILE"

if [ -s "$FAILED_LOG" ]; then
  echo "Completed with failures. See: $FAILED_LOG"
else
  echo "Success: all monthly Dukascopy EURUSD M15 downloads completed."
  echo "No failures logged: $FAILED_LOG"
fi

echo
echo "Merge command:"
echo "  python scripts/merge_dukascopy_eurusd_m15_monthly.py"
