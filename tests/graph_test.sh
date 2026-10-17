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
# shortcut: /tmp/g1 and /tmp/g2 (the brief's paths) and /tmp/s1, /tmp/s2, /tmp/s3, /tmp/s4 are fixed
#           paths. Serial `make test' is fine; the day it runs with -j, or on a host with a shared
#           /tmp, they become mktemp -d.
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

# ---- method inventory and reconciliation (Task 3) ----
# The `A`/`C` anchors below are the generator's row format `'%s %s %-38s %s'`, so a row reads
# `A C textDocument/hover                 hoverProvider`. "every tsv method appears exactly once" is
# the existence control for the two assertions of absence here ("completionItem/resolve is NOT marked
# advertised", and the `- -` half of "codeAction is neither answered nor advertised"): on an artifact
# with no method rows `grep -c` answers 0 and an absence check passes unread. It is also what makes
# "reconciliation is clean" mean something -- `clean` over an empty inventory is a check that prints
# the expected answer whatever the code does.
# "answered rows equal the dispatcher's method list" is an equality, not a count of the tsv's own
# rows: the generator derives `A' from `msg.method = "..."' in src/lsp_server.sd7 and also emits an
# `A - <method> -' row for any answered method the frozen inventory does not list, so a dispatcher
# method outside the 75 raises this count instead of hiding (proved by mutation: appending
# `zz/fakeAnswered' to the extracted list reddens exactly this check, 1 failed of 15). The count is
# today's 21; a feature task that answers a new method regenerates the artifact and updates this
# number in the same commit.
check "spec inventory is 75 client->server|both" \
      'test $(wc -l < tools/lsp_methods.tsv) -eq 75'
check "answered rows equal the dispatcher's method list" \
      'test $(grep -c "^A " docs/PROJECT_GRAPH.md) -eq 21'
check "completionItem/resolve is NOT marked advertised" \
      'test $(grep -c "^- C completionItem/resolve" docs/PROJECT_GRAPH.md) -eq 0'
check "semanticTokens/range IS marked advertised" \
      'test $(grep -c "^A C textDocument/semanticTokens/range" docs/PROJECT_GRAPH.md) -eq 1'
check "codeAction is neither answered nor advertised" \
      'test $(grep -c "^- - textDocument/codeAction" docs/PROJECT_GRAPH.md) -eq 1'
# This one greps the generator's stdout, not the committed artifact, and it is the only check here that
# does. Freshness (check 1 + the last) pins artifact == generator, so it reddens a hand-edit of the
# document; nothing else reddens a revert of the clause inside the generator, which is how the header
# came to be misread as "diagnosticProvider is advertised" (invariant 5 backwards). Written after the
# wording landed (723f391), so it passes on sight; proved by mutation -- restoring the 55c912d generator
# prints 0 for this grep and FAILs this title.
check "methods header names the spec column, not an advertisement" \
      'test $(sh tools/project_graph.sh | grep -c "^## methods .*the last column is the capability the SPEC requires.*C is the only advertisement marker") -eq 1'
# The end address `^\`\`\`` is how the brief scopes the range to the section; today no artifact line
# starts with a fence, so sed prints to EOF and `^  clean` is still counted once. Verified against the
# mutant: with name-prefix matching the section prints five gaps and this check goes FAIL.
# "every tsv method appears exactly once" reads each method name out of the tsv and greps it as a
# BRE: GNU grep takes a `$` mid-pattern as a literal, which the three `$/...` methods need (verified:
# each scores exactly 1), and the trailing space in the pattern is what keeps
# `textDocument/semanticTokens/full` from matching inside `.../full/delta`.
check "reconciliation is clean on today's tree" \
      'test $(sed -n "/^## reconciliation/,/^\`\`\`/p" docs/PROJECT_GRAPH.md | grep -c "^  clean") -eq 1'
check "every tsv method appears exactly once" \
      'test $(while IFS= read -r line; do m=$(printf %s "$line" | cut -f1); \
           grep -c "[-AC] [-AC] $m " docs/PROJECT_GRAPH.md | grep -qx 1 || echo bad; \
         done < tools/lsp_methods.tsv | grep -c bad) -eq 0'

# ---- test-suite map, size ceiling, atomic regeneration (Task 4) ----
# Both coverage checks COMPUTE their expected number from the tree instead of pinning it. The plan's
# prose claimed three suites name no src module and offered `lsp_server' as one of them;
# src/lsp_server.sd7 exists, and the tree answers five -- folding, features, agents, graph,
# transcript. A literal would go stale the day a module is renamed, so no expected count is pinned
# here. The two paths fs_suite_files names below are not a pinned count: they are the price of a floor
# that must not read the Makefile, and the tree gives no pattern that separates a suite gate from
# tools/keyword_gate.sh.
#
# The Makefile is the only list of suites, so the checks read it: TESTS and TESTS_SH name the
# `test-<name>' targets, `test:' lists any bare target (today only transcript). Temp files rather
# than `<(...)' because `make test' runs this suite with `sh', and process substitution is a
# bash-ism. The two seds are re-spelled here instead of sharing the generator's functions on purpose:
# a coverage check that calls the code it measures compares that code with itself and cannot fail.
# That shared-source reading has a hole, and fs_suite_files below is what closes it: if the Makefile's
# list ever changes shape (`TESTS +=', a backslash continuation, `$(strip …)', a tab before `:='),
# BOTH sides extract nothing, the generator emits no rows, and a names-vs-rows comparison passes on
# 0 -eq 0. So one more comparison is made against a source that is neither file: the filesystem.
suite_names() {
  sed -n 's/^TESTS\(_SH\)\?[[:space:]]*: *=//p' Makefile | tr ' ' '\n' | grep -vE '^$'
}

bare_names() {
  sed -n 's/^test: //p' Makefile | tr ' ' '\n' | grep -vE '\$\(|\)'
}

# The floor: the suite files that exist on disk. `*_test.sd7' and `*_test.sh' under tests/ can only
# be suites (the Makefile's own test-% convention names them); the other two are NAMED, not globbed,
# because `tools/*_gate.sh' also matches tools/keyword_gate.sh, which is a generator and not a suite
# -- measured, it puts the floor at 22 against 21 rows and reddens a correct tree. Printing the two
# named paths unconditionally is what makes an empty extraction loud rather than vacuous: a section
# with no rows scores 21 file-only lines here, never 0 -eq 0.
fs_suite_files() {
  find tests -maxdepth 1 \( -name '*_test.sd7' -o -name '*_test.sh' \) -print
  printf '%s\n' tests/transcript.py tools/agents_gate.sh
}

# Column 2 of every row, and the row's target name with the optional `test-' stripped.
artifact_rows() { # $1 = col2 | name
  case $1 in
    col2) grep -oE '^  make (test-)?[a-z0-9_]+ +[^ ]+' docs/PROJECT_GRAPH.md |
            sed -E 's/^  make (test-)?[a-z0-9_]+ +//' ;;
    name) grep -oE '^  make (test-)?[a-z0-9_]+' docs/PROJECT_GRAPH.md |
            sed -E 's/^  make (test-)?//' ;;
  esac | sort -u
}

# All three halves of the atomicity fix, at once: a failed `make graph' must exit non-zero (an
# `|| rm -f ...' arm without the `exit 1' makes the recipe SUCCEED on a dead generator), must leave
# the previous artifact byte-for-byte (a plain `>' redirect truncates it before the generator runs),
# and must leave no .tmp behind -- .gitignore has no `*.tmp' pattern, so a leftover is an untracked
# file that `git status --porcelain -uall' shows and a broad `git add -A' commits.
# The guard is tripped in a sandbox: the generator's only reachable failure is `no src/ under
# $ROOT', and moving the repo's src/ is not this suite's to do. mktemp -d, not a fixed path -- a
# stale .tmp from an earlier run is exactly what the check looks for. The .tmp path is read out of
# the Makefile recipe so a renamed temp file cannot hide from it.
failed_graph_is_clean() {
  box=$(mktemp -d)
  mkdir -p "$box/docs" "$box/tools"
  cp Makefile "$box/Makefile"
  cp tools/project_graph.sh "$box/tools/project_graph.sh"
  cp docs/PROJECT_GRAPH.md "$box/docs/PROJECT_GRAPH.md"
  tmp=$(sed -n 's/.*> \([^ ]*\.tmp\).*/\1/p' Makefile)
  if make -C "$box" graph >/dev/null 2>&1; then status=0; else status=1; fi
  # an empty extraction means the recipe stopped writing through a .tmp at all, which is the
  # non-atomic form this check exists to refuse -- so it counts as a leftover, not as "clean".
  if [ -z "$tmp" ] || [ -e "$box/$tmp" ]; then leftover=1; else leftover=0; fi
  if cmp -s "$box/docs/PROJECT_GRAPH.md" docs/PROJECT_GRAPH.md; then kept=1; else kept=0; fi
  rm -rf "$box"
  test "$status" -ne 0 -a "$leftover" -eq 0 -a "$kept" -eq 1
}

check "every Makefile suite name has a row, and no row lacks one" \
      'for n in $(suite_names) $(bare_names); do printf "%s\n" "$n"; done | sort -u >/tmp/s1; artifact_rows name >/tmp/s2; test $(comm -3 /tmp/s1 /tmp/s2 | grep -c .) -eq 0'
# One comm over two sets does three jobs, which is why there is no separate "column 2 exists" check:
# a row naming a file that is not on disk shows up as a row-only line, a suite file with no row as a
# file-only line, and a section with no rows at all as 21 file-only lines. Neither input comes from
# the Makefile or the generator, so the shape change that silences the check above cannot silence
# this one.
check "the suite map is floored on suite files that exist, not on the Makefile" \
      'fs_suite_files | sort -u >/tmp/s3; artifact_rows col2 >/tmp/s4; test $(comm -3 /tmp/s3 /tmp/s4 | grep -c .) -eq 0'
check "graph is under the ceiling" \
      'test $(wc -c < docs/PROJECT_GRAPH.md) -le $(sed -n "s/^MAX_GRAPH_BYTES=//p" tools/project_graph.sh)'
check "a failed make graph leaves no leftover tmp file" \
      'failed_graph_is_clean'
check "suites with no src module are labelled, not hidden" \
      'test $(grep -c "no src module" docs/PROJECT_GRAPH.md) -eq $(for n in $(suite_names) $(bare_names); do { [ -f "src/$n.sd7" ] || [ -f "src/features/$n.sd7" ]; } || echo x; done | grep -c x)'

report
