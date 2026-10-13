#!/bin/sh
# Regenerate src/keywords.sd7's CANNOT_BE_NAME, the word list the rename gate consults.
#
# WHY A GENERATOR. Seed7 declares no reserved words (Seed7Home/manual/intro.htm:230), so no
# document defines the list, and globalObjects cannot enumerate $ syntax declarations, so no
# runtime call answers it either (M5 spec 11.1 and 11.5). The only honest criterion is
# behavioural: a word is gate-worthy exactly when the interpreter refuses to let it be a plain
# declared name. That is what this script measures, one word per program, per interpreter
# release. Measured here with s7 5.4.10; the seven hand-written keyword lists this branch has
# compared all disagree with each other, which is the whole argument for generating.
#
# HOW. For every candidate word, write
#     const proc: main is func  local var integer: <WORD> is 1;  begin writeln(1); end func;
# and analyse it with `s7 -q -a`. A word the analyzer rejects is syntax (the report is always
# `Expression expected found "is"` or `"[" expected found "is"`, never a redeclaration), so it
# can never name a user symbol and the gate must refuse it. A word that analyses cleanly is a
# legal identifier and the gate must NOT refuse it: renaming to or from it is a real edit.
#
# Candidates are every identifier in a `$ syntax` template body of the library (where the
# language's own words live) plus EXTRA below (words the manual and editor lists carry that no
# template body mentions, so the clean half of the measurement is measured too).
#
# Usage:  sh tools/keyword_gate.sh   # prints the words, then compares with the shipped array
#         SEED7_LIB=/path/to/seed7/lib sh tools/keyword_gate.sh
# Exit status 0 only when this run's measurement equals CANNOT_BE_NAME in src/keywords.sd7. Not
# part of `make test`: it asks the interpreter, not the server (Task 11's corpus gate standing).

set -e
LC_ALL=C
export LC_ALL

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SEED7_LIB=${SEED7_LIB:-"$HOME/seed7/lib"}
S7=${S7:-s7}
SYNTAX="$SEED7_LIB/syntax.s7i"
MODULE="$ROOT/src/keywords.sd7"

# Re-probed by name as well as from the template bodies: these are the words M5 spec 11.11 names
# as the interesting clean half, and every one of them analysed cleanly under 5.4.10. A gate
# built from a vocabulary list would refuse them for a reason the language does not have.
EXTRA='and by cast conv div enum exit find forward leave member mod nested out parse proc rem result static switch times type value'

[ -r "$SYNTAX" ] || { echo "keyword_gate: cannot read $SYNTAX (set SEED7_LIB)" >&2; exit 1; }
command -v "$S7" >/dev/null || { echo "keyword_gate: $S7 not on PATH" >&2; exit 1; }

PROBE=$(mktemp -d)
trap 'rm -rf "$PROBE"' EXIT

candidates=$(
  {
    grep '\$ syntax' "$SYNTAX" | sed 's/.*\$ syntax [a-zA-Z]*:*//' | sed 's/ is .*//' |
      grep -o '[A-Za-z_][A-Za-z0-9_]*'
    printf '%s\n' "$EXTRA" | tr ' ' '\n'
  } | sort -u
)

for word in $candidates
do
  printf '$ include "seed7_05.s7i";\n\nconst proc: main is func\n  local\n    var integer: %s is 1;\n  begin\n    writeln(1);\n  end func;\n' \
    "$word" > "$PROBE/t.sd7"
  if [ -n "$("$S7" -q -a "$PROBE/t.sd7" 2>&1 >/dev/null)" ]; then
    printf '%s\n' "$word"
  fi
done > "$PROBE/measured"

# The sentinel: a probe that never ran prints an empty list, which would read as "nothing is a
# keyword". Require one word the language refuses and one it allows.
if ! grep -qx begin "$PROBE/measured"; then
  echo "keyword_gate: begin passed the probe -- the interpreter or the probe changed" >&2
  exit 1
fi
if grep -qx type "$PROBE/measured"; then
  echo "keyword_gate: type failed the probe -- re-read M5 spec 11.11 before shipping" >&2
  exit 1
fi

cat "$PROBE/measured"

# Only the quoted literals of the array, never the declaration line's own words.
sed -n '/CANNOT_BE_NAME is/,/");/p' "$MODULE" |
  grep -o '"[A-Za-z_][A-Za-z0-9_]*"' | tr -d '"' | sort > "$PROBE/shipped"
if cmp -s "$PROBE/measured" "$PROBE/shipped"; then
  echo "keyword_gate: $(wc -l < "$PROBE/measured") words, equal to $MODULE" >&2
else
  echo "keyword_gate: MISMATCH with $MODULE (measured < , shipped >)" >&2
  diff -u "$PROBE/measured" "$PROBE/shipped" >&2 || true
  exit 1
fi
