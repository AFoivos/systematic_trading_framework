#!/bin/bash

# Download Dukascopy 30-minute BID and ASK OHLCV CSV files in quarterly chunks.
#
# Defaults:
#   START_YEAR=2020
#   END_DATE=2026-04-28
#   OUT_ROOT=data/raw/dukascopy_quarterly
#
# Example:
#   START_YEAR=2024 END_DATE=2024-02-01 ./scripts/download_dukascopy_30m_quarterly.sh
#
# Merge after downloading:
#   python scripts/merge_dukascopy_quarterly_30m.py

set -uo pipefail

START_YEAR="${START_YEAR:-2020}"
END_DATE="${END_DATE:-2026-04-28}"
OUT_ROOT="${OUT_ROOT:-data/raw/dukascopy_quarterly}"
FAILED_LOG="$OUT_ROOT/failed_downloads.txt"

if ! command -v npx >/dev/null 2>&1; then
  echo "ERROR: npx is required. Install Node.js/npm, then rerun this script." >&2
  exit 1
fi

case "$START_YEAR" in
  ''|*[!0-9]*)
    echo "ERROR: START_YEAR must be a numeric year, got: $START_YEAR" >&2
    exit 1
    ;;
esac

case "$END_DATE" in
  [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9])
    ;;
  *)
    echo "ERROR: END_DATE must use YYYY-MM-DD format, got: $END_DATE" >&2
    exit 1
    ;;
esac

mkdir -p "$OUT_ROOT" || exit 1
: > "$FAILED_LOG" || exit 1

echo "Downloading Dukascopy 30-minute quarterly data"
echo "START_YEAR: $START_YEAR"
echo "END_DATE: $END_DATE"
echo "OUT_ROOT: $OUT_ROOT"
echo "Failure log: $FAILED_LOG"
echo

log_failure() {
  MESSAGE="$1"
  echo "$MESSAGE" >> "$FAILED_LOG"
  echo "FAILED: $MESSAGE" >&2
}

download_one() {
  FRAMEWORK_SYMBOL="$1"
  INSTRUMENT="$2"
  FILE_SYMBOL="$3"
  PRICE_TYPE="$4"
  QUARTER_LABEL="$5"
  FROM_DATE="$6"
  TO_DATE="$7"
  OUT_DIR="$8"

  OUT_FILE="${FILE_SYMBOL}_30m_${PRICE_TYPE}"
  OUT_PATH="$OUT_DIR/${OUT_FILE}.csv"

  if [ -s "$OUT_PATH" ]; then
    echo "[$QUARTER_LABEL][$FRAMEWORK_SYMBOL][$PRICE_TYPE] Skipping existing non-empty file: $OUT_PATH"
    return 0
  fi

  echo "[$QUARTER_LABEL][$FRAMEWORK_SYMBOL][$PRICE_TYPE] Downloading $INSTRUMENT from $FROM_DATE to $TO_DATE -> $OUT_PATH"

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
    --file-name "$OUT_FILE" \
    --retries 5 \
    --retry-pause 3000 \
    --batch-size 3 \
    --batch-pause 2500

  STATUS=$?
  if [ "$STATUS" -ne 0 ]; then
    log_failure "$QUARTER_LABEL|$FRAMEWORK_SYMBOL|$INSTRUMENT|$PRICE_TYPE|$FROM_DATE|$TO_DATE|exit_status=$STATUS"
    return 0
  fi

  if [ ! -s "$OUT_PATH" ]; then
    log_failure "$QUARTER_LABEL|$FRAMEWORK_SYMBOL|$INSTRUMENT|$PRICE_TYPE|$FROM_DATE|$TO_DATE|missing_or_empty_output=$OUT_PATH"
    return 0
  fi

  echo "[$QUARTER_LABEL][$FRAMEWORK_SYMBOL][$PRICE_TYPE] Finished"
  return 0
}

YEAR="$START_YEAR"
while [ "$YEAR" -le "${END_DATE%%-*}" ]; do
  QUARTER=1
  while [ "$QUARTER" -le 4 ]; do
    case "$QUARTER" in
      1)
        FROM_DATE="${YEAR}-01-01"
        NEXT_DATE="${YEAR}-04-01"
        ;;
      2)
        FROM_DATE="${YEAR}-04-01"
        NEXT_DATE="${YEAR}-07-01"
        ;;
      3)
        FROM_DATE="${YEAR}-07-01"
        NEXT_DATE="${YEAR}-10-01"
        ;;
      4)
        FROM_DATE="${YEAR}-10-01"
        NEXT_DATE="$((YEAR + 1))-01-01"
        ;;
    esac

    if [ "$FROM_DATE" \> "$END_DATE" ]; then
      break
    fi

    TO_DATE="$NEXT_DATE"
    if [ "$END_DATE" \< "$TO_DATE" ]; then
      TO_DATE="$END_DATE"
    fi

    QUARTER_LABEL="${YEAR}_Q${QUARTER}"
    OUT_DIR="$OUT_ROOT/$QUARTER_LABEL"
    mkdir -p "$OUT_DIR" || exit 1

    echo "=== $QUARTER_LABEL: $FROM_DATE to $TO_DATE ==="

    while IFS='|' read -r FRAMEWORK_SYMBOL INSTRUMENT FILE_SYMBOL; do
      if [ -z "$FRAMEWORK_SYMBOL" ]; then
        continue
      fi

      for PRICE_TYPE in bid ask; do
        download_one "$FRAMEWORK_SYMBOL" "$INSTRUMENT" "$FILE_SYMBOL" "$PRICE_TYPE" "$QUARTER_LABEL" "$FROM_DATE" "$TO_DATE" "$OUT_DIR"
      done
    done <<'INSTRUMENTS'
XAUUSD|xauusd|xauusd
US100|usatechidxusd|us100
US30|usa30idxusd|us30
SPX500|usa500idxusd|spx500
GER40|deuidxeur|ger40
INSTRUMENTS

    echo
    QUARTER=$((QUARTER + 1))
  done

  YEAR=$((YEAR + 1))
done

if [ -s "$FAILED_LOG" ]; then
  echo "Completed with failures. See: $FAILED_LOG"
else
  echo "Success: all quarterly Dukascopy 30-minute BID/ASK downloads completed."
  echo "No failures logged: $FAILED_LOG"
fi
