#!/bin/sh
# Gate: every token frozen in tools/agents_required.txt must still appear in AGENTS.md or
# docs/seed7-cli.md.
#
# WHY. Reference text may MOVE out of AGENTS.md into docs/, but a rule that moves has to arrive.
# Prose editing is where a sentence silently disappears, and the only mechanical way to tell
# "rewrote it elsewhere" from "deleted it" is a list of what today's file asserts, kept as a
# committed artifact so a later edit is compared against a frozen past, not against itself.
#
# HOW. tools/agents_required.txt was extracted from AGENTS.md with four `grep -oE` rules --
# section headers, file:line citations, measured counts, invariant owners -- sorted and committed
# verbatim. Each token in it is one check: `grep -qF` over the union of AGENTS.md and
# docs/seed7-cli.md, in that order, whichever of them exist. A file named in the list that does not
# exist yet counts as empty, not fatal. One check per token, so N is the list length and M counts
# the tokens no existing file holds.
# shortcut: a token list frozen today cannot catch a token that was never in AGENTS.md -- the list
#           is a regression net, not a specification. Re-extract the list whenever AGENTS.md gains
#           a rule worth keeping.
#
# Usage:  sh tools/agents_gate.sh          # also `make test-agents`, part of `make test`
# Prints each missing token as `MISSING <token>`, then the graded line
# `agents: N checks, M failed`; exits 1 iff M > 0.

LC_ALL=C
export LC_ALL

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
LIST="$ROOT/tools/agents_required.txt"
FILES="$ROOT/AGENTS.md $ROOT/docs/seed7-cli.md"

[ -r "$LIST" ] || { echo "agents_gate: cannot read $LIST" >&2; exit 1; }

PRESENT=''
for f in $FILES; do
  if [ -f "$f" ]; then PRESENT="$PRESENT $f"; fi
done

checks=0
failed=0
while IFS= read -r tok || [ -n "$tok" ]; do
  checks=$((checks + 1))
  found=0
  for f in $PRESENT; do
    if grep -qF -- "$tok" "$f"; then
      found=1
      break
    fi
  done
  if [ "$found" -eq 0 ]; then
    failed=$((failed + 1))
    printf 'MISSING %s\n' "$tok"
  fi
done < "$LIST"

# An empty list would print `0 checks, 0 failed` and exit 0 -- a green run that checks nothing,
# the same silent-green defect as a Makefile rule that matches no suite file.
if [ "$checks" -eq 0 ]; then
  printf 'MISSING tools/agents_required.txt holds no tokens\n'
  failed=1
fi

printf 'agents: %d checks, %d failed\n' "$checks" "$failed"
[ "$failed" -eq 0 ] || exit 1
exit 0
