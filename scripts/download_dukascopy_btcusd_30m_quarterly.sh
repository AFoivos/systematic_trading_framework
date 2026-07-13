#!/usr/bin/env bash

# Download Dukascopy BTCUSD 30-minute OHLCV CSV files in quarterly chunks.
#
# The output filenames intentionally do not contain "bid" or "ask":
#   btcusd_30m.csv
#
# Dukascopy/dukascopy-node still needs a source price side internally.
# We use BID by default, but do not expose it in filenames. Override with:
#   SOURCE_PRICE_SIDE=ask ./scripts/download_dukascopy_btcusd_30m_quarterly.sh
#
# Defaults:
#   START_YEAR=2017
#   FIRST_AVAILABLE_DATE=2017-05-07
#   END_DATE=<today UTC>
#   OUT_ROOT=data/raw/dukascopy_btcusd_quarterly
#   FAILED_LOG=<OUT_ROOT>/failed_downloads.txt
#
# Examples:
#   ./scripts/download_dukascopy_btcusd_30m_quarterly.sh
#   START_YEAR=2024 END_DATE=2025-01-01 ./scripts/download_dukascopy_btcusd_30m_quarterly.sh
#
# Notes:
# - END_DATE acts as the upper boundary of the final requested chunk.
# - Existing non-empty CSV files with at least one data row are skipped.
# - Failed chunks do not stop the full run; they are recorded in FAILED_LOG.

set -uo pipefail

START_YEAR="${START_YEAR:-2015}"
FIRST_AVAILABLE_DATE="${FIRST_AVAILABLE_DATE:-2015-01-01}"
END_DATE="${END_DATE:-$(date -u +%F)}"
OUT_ROOT="${OUT_ROOT:-data/raw/dukascopy_btcusd_quarterly}"
FAILED_LOG="${FAILED_LOG:-$OUT_ROOT/failed_downloads.txt}"

FRAMEWORK_SYMBOL="${FRAMEWORK_SYMBOL:-BTCUSD}"
INSTRUMENT="${INSTRUMENT:-btcusd}"
FILE_SYMBOL="${FILE_SYMBOL:-btcusd}"
TIMEFRAME_LABEL="${TIMEFRAME_LABEL:-15m}"
DUKAS_TIMEFRAME="${DUKAS_TIMEFRAME:-m15}"
SOURCE_PRICE_SIDE="${SOURCE_PRICE_SIDE:-bid}"
DUKASCOPY_NODE_VERSION="${DUKASCOPY_NODE_VERSION:-1.46.4}"

if ! command -v npx >/dev/null 2>&1; then
  echo "ERROR: npx is required. Install Node.js/npm, then rerun this script." >&2
  exit 1
fi

validate_year() {
  local value="$1"
  local name="$2"

  case "$value" in
    ''|*[!0-9]*)
      echo "ERROR: $name must be a numeric year, got: $value" >&2
      exit 1
      ;;
  esac
}

validate_date() {
  local value="$1"
  local name="$2"

  case "$value" in
    [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9])
      ;;
    *)
      echo "ERROR: $name must use YYYY-MM-DD format, got: $value" >&2
      exit 1
      ;;
  esac
}

validate_year "$START_YEAR" "START_YEAR"
validate_date "$FIRST_AVAILABLE_DATE" "FIRST_AVAILABLE_DATE"
validate_date "$END_DATE" "END_DATE"

case "$SOURCE_PRICE_SIDE" in
  bid|ask)
    ;;
  *)
    echo "ERROR: SOURCE_PRICE_SIDE must be bid or ask, got: $SOURCE_PRICE_SIDE" >&2
    exit 1
    ;;
esac

if [[ "${START_YEAR}-01-01" > "$END_DATE" ]]; then
  echo "ERROR: START_YEAR begins after END_DATE: ${START_YEAR}-01-01 > $END_DATE" >&2
  exit 1
fi

mkdir -p "$OUT_ROOT" || exit 1
: > "$FAILED_LOG" || exit 1

printf 'timestamp_utc|quarter|symbol|instrument|source_side|from_date|to_date|reason\n' > "$FAILED_LOG"

echo "Downloading Dukascopy BTCUSD 15-minute quarterly data"
echo "START_YEAR: $START_YEAR"
echo "FIRST_AVAILABLE_DATE: $FIRST_AVAILABLE_DATE"
echo "END_DATE: $END_DATE"
echo "Instrument: $INSTRUMENT"
echo "Internal source side: $SOURCE_PRICE_SIDE"
echo "Output filename per quarter: ${FILE_SYMBOL}_${TIMEFRAME_LABEL}.csv"
echo "OUT_ROOT: $OUT_ROOT"
echo "Failure log: $FAILED_LOG"
echo "dukascopy-node version: $DUKASCOPY_NODE_VERSION"
echo

log_failure() {
  local quarter_label="$1"
  local from_date="$2"
  local to_date="$3"
  local reason="$4"
  local command_log="${5:-}"
  local timestamp_utc

  timestamp_utc="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf '%s|%s|%s|%s|%s|%s|%s|%s\n' \
    "$timestamp_utc" \
    "$quarter_label" \
    "$FRAMEWORK_SYMBOL" \
    "$INSTRUMENT" \
    "$SOURCE_PRICE_SIDE" \
    "$from_date" \
    "$to_date" \
    "$reason" >> "$FAILED_LOG"

  if [ -n "$command_log" ] && [ -s "$command_log" ]; then
    {
      echo "--- command output: $quarter_label ---"
      tail -n 80 "$command_log"
      echo "--- end command output: $quarter_label ---"
    } >> "$FAILED_LOG"
  fi

  echo "FAILED: $quarter_label | $from_date -> $to_date | $reason" >&2
}

csv_has_data_rows() {
  local path="$1"

  [ -s "$path" ] || return 1
  awk 'END { exit(NR > 1 ? 0 : 1) }' "$path"
}

download_one() {
  local quarter_label="$1"
  local from_date="$2"
  local to_date="$3"
  local out_dir="$4"
  local out_file="${FILE_SYMBOL}_${TIMEFRAME_LABEL}"
  local out_path="$out_dir/${out_file}.csv"
  local command_log
  local status

  if csv_has_data_rows "$out_path"; then
    echo "[$quarter_label][$FRAMEWORK_SYMBOL] Skipping existing CSV with data: $out_path"
    return 0
  fi

  if [ -e "$out_path" ]; then
    echo "[$quarter_label][$FRAMEWORK_SYMBOL] Removing empty/header-only output: $out_path"
    rm -f "$out_path"
  fi

  command_log="$(mktemp)"

  echo "[$quarter_label][$FRAMEWORK_SYMBOL] Downloading $INSTRUMENT from $from_date to $to_date -> $out_path"

  npx --yes "dukascopy-node@${DUKASCOPY_NODE_VERSION}" \
    --instrument "$INSTRUMENT" \
    --date-from "$from_date" \
    --date-to "$to_date" \
    --timeframe "$DUKAS_TIMEFRAME" \
    --price-type "$SOURCE_PRICE_SIDE" \
    --format csv \
    --volumes true \
    --date-format "YYYY-MM-DD HH:mm:ss" \
    --time-zone UTC \
    --directory "$out_dir" \
    --file-name "$out_file" \
    --retries 5 \
    --retry-pause 3000 \
    --retry-on-empty \
    --batch-size 3 \
    --batch-pause 2500 2>&1 | tee "$command_log"

  status=${PIPESTATUS[0]}

  if [ "$status" -ne 0 ]; then
    log_failure "$quarter_label" "$from_date" "$to_date" "exit_status=$status" "$command_log"
    rm -f "$command_log"
    return 0
  fi

  if ! csv_has_data_rows "$out_path"; then
    log_failure "$quarter_label" "$from_date" "$to_date" "missing_empty_or_header_only_output=$out_path" "$command_log"
    rm -f "$command_log"
    return 0
  fi

  rm -f "$command_log"
  echo "[$quarter_label][$FRAMEWORK_SYMBOL] Finished"
  return 0
}

YEAR="$START_YEAR"
END_YEAR="${END_DATE%%-*}"

while [ "$YEAR" -le "$END_YEAR" ]; do
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

    if [[ "$FROM_DATE" > "$END_DATE" || "$FROM_DATE" == "$END_DATE" ]]; then
      break
    fi

    TO_DATE="$NEXT_DATE"
    if [[ "$END_DATE" < "$TO_DATE" ]]; then
      TO_DATE="$END_DATE"
    fi

    if [[ "$TO_DATE" < "$FIRST_AVAILABLE_DATE" || "$TO_DATE" == "$FIRST_AVAILABLE_DATE" ]]; then
      QUARTER=$((QUARTER + 1))
      continue
    fi

    if [[ "$FROM_DATE" < "$FIRST_AVAILABLE_DATE" ]]; then
      FROM_DATE="$FIRST_AVAILABLE_DATE"
    fi

    QUARTER_LABEL="${YEAR}_Q${QUARTER}"
    OUT_DIR="$OUT_ROOT/$QUARTER_LABEL"
    mkdir -p "$OUT_DIR" || exit 1

    echo "=== $QUARTER_LABEL: $FROM_DATE to $TO_DATE ==="
    download_one "$QUARTER_LABEL" "$FROM_DATE" "$TO_DATE" "$OUT_DIR"
    echo

    QUARTER=$((QUARTER + 1))
  done

  YEAR=$((YEAR + 1))
done

FAILURE_COUNT="$(awk -F'|' 'NR > 1 && $2 ~ /_Q[1-4]$/ && NF >= 8 {count++} END {print count + 0}' "$FAILED_LOG")"

if [ "$FAILURE_COUNT" -gt 0 ]; then
  echo "Completed with $FAILURE_COUNT failed chunk(s). See: $FAILED_LOG"
  exit 2
fi

echo "Success: all quarterly Dukascopy BTCUSD 30-minute downloads completed."
echo "No failed chunks logged: $FAILED_LOG"
