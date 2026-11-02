#!/bin/sh
# Gate: every present-tense figure the documents state about the sibling checkouts
# is re-derived here from the live tree, so a drift is a failing check, not a stale number.
#
# WHY. The documents record measurements against ~/seed7 and ~/Seed7Home. Those trees move
# (new libraries are installed, the homepage is regenerated), and a figure recorded last month
# is silently wrong the moment the sibling adds a file. The gate re-runs every command and
# compares to the expected value in tools/figures_expected.tsv; a mismatch is a failing check.
#
# HOW. The TSV has four tab-separated fields: name, command, expected, host-file:line.
# The command is eval'd with SEED7 and HOME_DIR in the environment, so each row is
# self-describing and the gate carries no hard-coded figure. The host column is documentation
# only -- it tells a human where to restate a drifted number.
#
# SKIP path: if $SEED7 is not a directory or $HOME_DIR is not a directory, the gate prints
# `figures: 0 checks, 0 failed` and a SKIP line and exits 0. A machine without the siblings
# must not fail the suite, and must not look like it verified anything.
#
# Usage: sh tools/figures_gate.sh [SEED7_DIR] [HOME_DIR]
#   also: make test-figures (part of make test)

set -u

LC_ALL=C
export LC_ALL

SEED7=${1:-/home/username/seed7}
HOME_DIR=${2:-/home/username/Seed7Home}
export SEED7 HOME_DIR

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TSV="$ROOT/tools/figures_expected.tsv"

[ -r "$TSV" ] || { echo "figures_gate: cannot read $TSV" >&2; exit 1; }

# SKIP path: if either sibling is absent, print the graded line as zero checks and exit 0.
if [ ! -d "$SEED7" ] || [ ! -d "$HOME_DIR" ]; then
  printf 'SKIP:no-seed7-checkout SEED7=%s HOME_DIR=%s\n' "$SEED7" "$HOME_DIR"
  printf 'figures: 0 checks, 0 failed\n'
  exit 0
fi

checks=0
failed=0

while IFS='	' read -r name cmd expected host || [ -n "$name" ]; do
  # skip blank lines and comments
  case "$name" in
    ''|'#'*) continue ;;
  esac
  checks=$((checks + 1))
  actual=$(eval "$cmd" 2>/dev/null) || actual=""
  # corpus_bytes: wc -c tail -1 prints "NNNN total" or just "NNNN"; take field 1
  case "$name" in
    corpus_bytes) actual=$(printf '%s\n' "$actual" | awk '{print $1}') ;;
  esac
  # trim whitespace
  actual=$(printf '%s' "$actual" | tr -d '[:space:]')
  expected=$(printf '%s' "$expected" | tr -d '[:space:]')
  if [ "$actual" != "$expected" ]; then
    failed=$((failed + 1))
    printf 'FAIL %s expected=%s actual=%s host=%s\n' "$name" "$expected" "$actual" "$host"
  fi
done < "$TSV"

printf 'figures: %d checks, %d failed\n' "$checks" "$failed"
[ "$failed" -eq 0 ] || exit 1
exit 0
