#!/bin/sh
# Gate: every row of tools/figures_expected.tsv is re-derived from the live sibling checkout and
# compared with that row's own `expected` value, so a TREE-vs-TSV drift is a failing check.
#
# WHY. The documents record measurements against ~/seed7 and ~/Seed7Home. Those trees move
# (new libraries are installed, the homepage is regenerated), and a figure recorded last month
# is silently wrong the moment the sibling adds a file.
#
# WHAT THIS DOES NOT DEFEND: a DOCUMENT that drifts from the TSV. The fourth field, `host`, is
# never read -- the loop binds it and uses it only in the FAIL line -- so the TSV-to-document
# link is by hand, and it is incomplete. These present-tense corpus figures are in no row and
# nothing re-derives them: `src/scan.sd7:61` and `src/features/folding_range.sd7:12` (both
# "213 lib/*.s7i"), `src/blocks.sd7:332` ("215 lib/*.s7i"), `AGENTS.md:340` ("184 of the 214",
# excluded by the plan that chartered this gate, and restatable only by re-running
# tools/rf10_probe.sh), and the `SENTINEL files=344 regions=56492 skips=1` row of "Every change
# -- the two blockRegions post-passes, measured (2026-10-31)" in docs/seed7-cli.md. Edit one of
# those and this gate stays green.
#
# HOW. The TSV has four tab-separated fields: name, command, expected, host-file:line.
# The command is eval'd with SEED7 and HOME_DIR in the environment, so each row is
# self-describing and the gate carries no hard-coded figure. The host column is documentation
# only -- it tells a human where to restate a drifted number. Making it a real arm needs the
# TYPESET form of the figure per row: 2 of the 12 rows state it with space-separated thousands
# at their host line (`corpus_bytes` as "24 995 434" in tools/regions_gate.sh:8,
# `home_index_bytes` as "532 702" in docs/seed7-cli.md:412), so a literal grep for `expected`
# misses those two. The other 10 do appear verbatim on their host line.
#
# SKIP path: if $SEED7 is not a directory or $HOME_DIR is not a directory, the gate prints
# `figures: 0 checks, 0 failed` and a SKIP line and exits 0. A machine without the siblings
# must not fail the suite, and must not look like it verified anything. The label is
# all-or-nothing and always reads `no-seed7-checkout`: a machine that HAS ~/seed7 and lacks
# ~/Seed7Home prints it having verified none of the 7 $SEED7 rows either. The graded zero is
# honest; the label names the wrong missing tree.
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
  actual=$(eval "$cmd" </dev/null 2>/dev/null) || actual=""
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

# An empty TSV would print `0 checks, 0 failed` and exit 0 -- a green run that checks nothing,
# the same silent-green defect as agents_gate.sh:110-116 and graph_test.sh:156-157 name.
if [ "$checks" -eq 0 ]; then
  printf 'FAIL tools/figures_expected.tsv holds no rows\n'
  failed=1
fi

printf 'figures: %d checks, %d failed\n' "$checks" "$failed"
[ "$failed" -eq 0 ] || exit 1
exit 0
