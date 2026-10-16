#!/bin/sh
# Suite for tools/project_graph.sh -- the generated module graph in docs/PROJECT_GRAPH.md.
#
# WHY. A generated file is read as fact, so the two ways it lies are (1) it disagrees with the
# tree (prose inside comments counted as includes) and (2) it is stale (committed from an older
# src/). One check each: the blocks.sd7 row pins the anchor, the freshness check pins the commit.
#
# HOW. `check TITLE COMMAND` evals COMMAND as a shell command, so every condition is a real
# command (`test ... -eq N`, `cmp -s ...`) and a failing one prints FAIL and counts. The first
# check leaves the fresh output in /tmp/g1, which the last check compares against the committed
# copy -- that is why the order below is load-bearing.
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

check "generator is stdout-only" \
      'test $(sh tools/project_graph.sh >/tmp/g1 2>/tmp/g2; wc -c </tmp/g2) -eq 0'
check "blocks.sd7 lists no prose include" \
      'test $(sh tools/project_graph.sh | grep "^blocks.sd7" | grep -c " x ") -eq 0'
check "blocks.sd7 lists scan.sd7" \
      'test $(sh tools/project_graph.sh | grep "^blocks.sd7" | grep -c "scan.sd7") -eq 1'
check "progs.s7i appears for analysis.sd7 only" \
      'test $(sh tools/project_graph.sh | grep -c "progs.s7i") -eq 1'
# The name class admits digits: with [a-z_]+ the digit-named module utf8bytes.sd7 is not a row
# as far as this check is concerned, and the count came out 15 against find's 16 (same trap the
# Makefile's S7TOTAL comment records).
check "every src module is a row" \
      'test $(sh tools/project_graph.sh | grep -cE "^[a-z0-9_]+\.sd7 +[0-9]") -eq $(find src -maxdepth 1 -name "*.sd7" | wc -l)'
check "committed artifact is fresh" \
      'cmp -s /tmp/g1 docs/PROJECT_GRAPH.md'

report
