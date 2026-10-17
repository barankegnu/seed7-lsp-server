#!/bin/sh
# Gate: every token frozen in tools/agents_required.txt must still appear in AGENTS.md or
# docs/seed7-cli.md -- except a section header, which has to be in AGENTS.md itself (see R26 below).
#
# WHY. Reference text may MOVE out of AGENTS.md into docs/, but a rule that moves has to arrive.
# Prose editing is where a sentence silently disappears, and the only mechanical way to tell
# "rewrote it elsewhere" from "deleted it" is a list of what today's file asserts, kept as a
# committed artifact so a later edit is compared against a frozen past, not against itself.
#
# HOW. tools/agents_required.txt was extracted from AGENTS.md by mechanical `grep -oE` rules alone:
# section headers, file:line citations, measured counts, the invariant owners
# (`^[0-9]+\. Only [^ ]+[^ ,;.]*` -- pins each invariant to the FILE that owns it), every invariant
# by number (`^[0-9]+\. [^ ]+[^ ,;.]*` -- catches the owners that name no file), and the code-shaped
# backticked literals of the regions Task 5 moves -- `AGENTS.md:53-62` and `:100-139` in the
# pre-split blob `git show d300662:AGENTS.md`. The 50-59 / 97-136 written here before Task 5 went
# stale the moment Task 4 inserted three lines above them: a span counted forward from an anchor
# loses a wrapped line; print the line past each boundary. Kept only when they occur nowhere else --
# a token that survives elsewhere is a check that cannot fail. Both invariant rules are kept on
# purpose: the number form alone would drop the owner paths, the owner form alone covers 4 of 7.
#
# AFTER THE SPLIT (Task 5). AGENTS.md:53-62 and :100-139 now live in docs/seed7-cli.md, so the
# line-range recipe above is spent: those ranges bound different prose today, and re-extracting the
# list wholesale would drop the moved tokens from it. Append only, never re-extract.
#
# ADMISSION TEST for an append (R26), before or after a cut: the append commit names the parent blob
# whose AGENTS.md it replayed class 6 and class 7 against, and shows every new token absent from the
# REST of that blob (outside-count 0). "Prefer to append BEFORE the cut" was too soft: a
# measurement can always be replayed against a parent blob after the fact, so the replay is the
# test and the order is only a preference. Task 5's 12 tokens (32 -> 44) were all replayed against
# `git show d300662:AGENTS.md`.
#
# What dropped the three late ones was NOT the shape of the extractor: class 6/7 replayed against
# that blob surface `s7 -p FILE`, `s7 -a` and `s7c -s x` as standalone backticked literals, each
# with outside-count 0, in a 29-candidate / 20-survivor set. They were cut at the Step 0 ruling's
# survivor list, whose counts (24 candidates, 16-17 unique, 9 new) reproduce under neither
# substring nor occurrence counting, and the mechanism inside that ruling is UNIDENTIFIED. The only
# reading that rejects all three matches their parts (`s7`, `-a`, `x`, `FILE` each occur outside)
# word-wise -- the mistake R21's own message says it stopped making. Do not install a tidier story
# here; re-run the replay.
#
# Proof of the net: deleting each of the six cut units from docs/seed7-cli.md alone gives 2, 5, 4,
# none, 2, 2 MISSING, and deleting the single host line of each late token gives 1, 2, 1. Lines 26
# and 49 were GREEN under the 41-token list and are RED under the 44, so those two reach clauses
# the unit-level tokens never could, while line 42 already reddened on -ocN, so `s7 -a` is
# redundancy there, nothing more. The `s7c` IS-the-analyze-phase bullet stays a declared permanent
# gap: its only literals, `s7c` (1 occurrence outside the moved text) and
# https://seed7.net/faq.htm#compile (1 outside), already pass on text nobody moved, and a prose
# fragment as a token is a check that cannot fail. And 44 checks are not 44 independent risks:
# `s7c -p` is implied by the two longer `s7c -p -O2 ...` tokens, so it can only go MISSING when all
# three do.
# Each token in the list is one check: `grep -qF` over the union of AGENTS.md and
# docs/seed7-cli.md, in that order, whichever of them exist. A file named in the list that does not
# exist yet counts as empty, not fatal. One check per token, so N is the list length and M counts
# the tokens no existing file holds.
# Exception (R26): a token starting `## ` is checked in AGENTS.md ALONE. The moved reference keeps
# the old section names as grep targets, so under union semantics either borrowed heading could
# vanish from the rules file with the gate green -- measured with the pre-R26 gate in a sandbox:
# deleting `## Seed7 traps` from AGENTS.md alone printed `agents: 44 checks, 0 failed` and exit 0.
# shortcut: a token list frozen today cannot catch a token that was never in AGENTS.md -- the list
#           is a regression net, not a specification. Re-extract the list whenever AGENTS.md gains
#           a rule worth keeping.
#
# Usage:  sh tools/agents_gate.sh          # also `make test-agents`, part of `make test`
# Prints each missing token as `MISSING <token>`, then the graded line
# `agents: N checks, M failed`; exits 1 iff M > 0.

# `set -u' for typo-catching. `set -e' kept out so a future `grep' outside a conditional cannot
# abort the gate: every grep today is an `if' condition, where POSIX `set -e' would not fire anyway.
set -u

LC_ALL=C
export LC_ALL

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
LIST="$ROOT/tools/agents_required.txt"
AGENTS="$ROOT/AGENTS.md"
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
  case $tok in
    '## '*)
      if grep -qF -- "$tok" "$AGENTS" 2>/dev/null; then found=1; fi
      ;;
    *)
      for f in $PRESENT; do
        if grep -qF -- "$tok" "$f"; then
          found=1
          break
        fi
      done
      ;;
  esac
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
