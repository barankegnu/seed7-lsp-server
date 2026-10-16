#!/bin/sh
# Suite for tools/project_graph.sh -- the generated module graph in docs/PROJECT_GRAPH.md.
#
# WHY. A generated file is read as fact, so the ways it lies are that it disagrees with the tree
# (prose counted as an include, a whole class of rows lost, the essential include leaking into every
# row) and that it is stale. Each of those gets a CONTENT check, not just the freshness comparison:
# a content check is what still bites after `make graph` re-blesses a wrong artifact.
#
# HOW. `check TITLE COMMAND` evals COMMAND as a shell command, so every condition is a real command
# (`test ... -eq N`, `cmp -s ...`) and a failing one prints FAIL and counts. The first check leaves
# the fresh output in /tmp/g1, which the last check compares against the committed copy -- that is
# why the order is load-bearing. The two row-count checks (5, 7) are the existence control for the
# two assertions of absence (2, 6): on an artifact with no rows, `grep -c` prints 0 and an absence
# check would pass unread.
#
# shortcut: /tmp/g1 and /tmp/g2 are fixed paths, as the brief writes them. Serial `make test` is
#           fine; the day it runs with -j, or on a host with a shared /tmp, they become mktemp -d.
#
# Wired into `make test` (as TESTS_SH := graph): it runs the generator a handful of times over
# the repo's own src/, which is milliseconds.
#
# Usage:  sh tests/graph_test.sh    # prints `graph: N checks, M failed`, exits 1 iff M > 0

set -eu
LC_ALL=C
export LC_ALL
# The checks below use repo-relative paths, as the brief writes them, so run from the repo root
# however the suite was invoked.
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd -- "$ROOT"

checks=0
failed=0

check() {
  checks=$((checks + 1))
  if eval "$2"; then
    :
  else
    failed=$((failed + 1))
    printf 'FAIL %s\n' "$1"
  fi
}

report() {
  printf 'graph: %d checks, %d failed\n' "$checks" "$failed"
  [ "$failed" -eq 0 ] || exit 1
}

check "generator writes nothing to stderr" \
      'test $(sh tools/project_graph.sh >/tmp/g1 2>/tmp/g2; wc -c </tmp/g2) -eq 0'
# The two blocks.sd7 checks are a pair: whole-row equality (the row exists and holds no other edge,
# which is what "and nothing else" means) and the presence control naming the one edge it must keep.
check "blocks.sd7 row is scan.sd7 and nothing else" \
      'test $(sh tools/project_graph.sh | grep -cE "^blocks\.sd7 +[0-9]+ +scan\.sd7$") -eq 1'
check "blocks.sd7 lists scan.sd7" \
      'test $(sh tools/project_graph.sh | grep "^blocks.sd7" | grep -c "scan.sd7") -eq 1'
check "progs.s7i appears for analysis.sd7 only" \
      'test $(sh tools/project_graph.sh | grep -c "progs.s7i") -eq 1'
# The name class admits digits: with [a-z_]+ the digit-named module utf8bytes.sd7 is not a row
# as far as this check is concerned, and the count came out 15 against find's 16 (same trap the
# Makefile's S7TOTAL comment records).
check "every src module is a row" \
      'test $(sh tools/project_graph.sh | grep -cE "^[a-z0-9_]+\.sd7 +[0-9]") -eq $(find src -maxdepth 1 -name "*.sd7" | wc -l)'
# All 28 modules include seed7_05.s7i on line 1, so losing the exclusion in the generator's case
# statement adds a universal edge to every row -- a content property, pinned here rather than by
# freshness alone. Pattern spells the file name: `seed7_\.s7i` matches nothing even when the arm is
# deleted (measured: 0 clean, 0 mutant, against 28 for the spelled pattern).
check "no row lists seed7_05.s7i" \
      'test $(sh tools/project_graph.sh | grep -c "seed7_05\.s7i") -eq 0'
# `/` is outside [a-z0-9_], so check 5 cannot see a features/ row; without this one all 12 could
# vanish and only freshness would notice.
check "every features module is a row" \
      'test $(sh tools/project_graph.sh | grep -cE "^features/[a-z0-9_]+\.sd7 +[0-9]") -eq $(find src/features -maxdepth 1 -name "*.sd7" | wc -l)'
check "committed artifact is fresh" \
      'cmp -s /tmp/g1 docs/PROJECT_GRAPH.md'

report
