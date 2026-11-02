#!/bin/sh
# Corpus gate for the scanner's columns -- a spike, not a suite.
#
# For every Seed7 source file, scans the text with the shipped scan.sd7 and checks:
#   - each token's col16 equals the UTF-16 units counted by hand from the start of its own line
#   - each token's width16 equals the units from its start to the first line break inside it
#     (multi-line tokens report only their start line -- that is scan.sd7's contract)
#   - maskOf preserves length and every newline position
# One row per file:
#   <path>\t<token count>\t<mismatch count>
# A SKIP row is printed for files the UTF-8 reader refuses.
#
# The scanner is the shipped src/scan.sd7 -- not a retyped copy. A retyped copy would gate a
# machine the server does not have.
#
# SECURITY: this gate reads corpus text and SCANS it. It does not call parseStri, analyzeAll
# or any other analyzer entry point. Analysis executes the analysed code (documented in the
# README's security section and AGENTS.md); scanning is lexical only and safe.
#
# Files are read with openUtf8 and a readln loop, the same decoded text the server sees. The
# readAll function is called per file: its local string does not survive the return, so a
# RANGE_ERROR on one file does not leave a corrupted buffer in the caller. This is the shape
# doc_index.readLinesOf uses (measured: 200 proseFor calls over an invalid-UTF-8 library
# through the running server answered 200 hovers with exit 0). The oracle probe that kept a
# loop-carried buffer in main aborted later with MEMORY_ERROR at sigutl.c(355) -- a probe-side
# artifact, not a shipped-code defect.
#
# One file in the corpus cannot be decoded at all: prg/err.sd7 is the interpreter's own
# invalid-encoding test program, and readln over it raises RANGE_ERROR at ut8_rtl.c(771). It
# gets a labelled SKIP row so the sentinel's files= and skips= fields disclose it.
#
# Not wired into `make test`, and it must not be: it is a measurement over an external corpus,
# it takes tens of seconds for prg/*.sd7 alone (~82 s measured, compiled with -O2), and it
# compares against a baseline file rather than asserting anything by itself. Run it before and
# after any change to scan.sd7's column or width derivation.
#
#   sh tools/tokens_gate.sh [OUTFILE] [SEED7_DIR]   # OUTFILE default stdout,
#                                                    # SEED7_DIR default /home/username/seed7
#
# The last line is the sentinel, and no payload counts as a result without it -- absent, the
# script exits 3 and writes nothing to OUT:
#   SENTINEL files=<n> tokens=<n> mismatches=<n> skips=<n>
set -eu

LC_ALL=C
export LC_ALL

OUT=${1:-}
SEED7=${2:-/home/username/seed7}
SRC=$(cd "$(dirname "$0")/.." && pwd)/src
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

[ -d "$SEED7/lib" ] || { echo "tokens_gate: no Seed7 checkout at $SEED7" >&2; exit 2; }

cat > "$WORK/tokens_gate.sd7" <<'SD7'
$ include "seed7_05.s7i";
  include "utf8.s7i";
  include "scan.sd7";

var integer: files is 0;
var integer: toks is 0;
var integer: bad is 0;
var integer: skips is 0;

const proc: fatal (in string: message) is func
  begin
    writeln(STD_ERR, "tokens_gate: " & message);
    exit(1);
  end func;

# Per-call local string: a RANGE_ERROR leaves nothing in the caller. The function's stack
# frame, including `out', is collected on return -- this is the shape that avoids the
# loop-carried MEMORY_ERROR the oracle probe hit.
const func string: readAll (in string: path, inout boolean: decoded) is func
  result
    var string: out is "";
  local
    var file: f is STD_NULL;
    var string: one is "";
  begin
    decoded := TRUE;
    block
      f := openUtf8(path, "r");
      while not eof(f) do
        readln(f, one);
        out &:= one;
        out &:= "\n";
      end while;
      close(f);
    exception
      catch FILE_ERROR:
        out := "";
      catch RANGE_ERROR:
        # ut8_rtl.c(771): "The file contains an invalid encoding." Measured on prg/err.sd7.
        close(f);
        out := "";
        decoded := FALSE;
    end block;
  end func;

# UTF-16 code units across a character range.
const func integer: unitsOf (in string: text, in integer: pos1, in integer: count) is func
  result
    var integer: out is 0;
  local
    var integer: k is 0;
  begin
    for k range 0 to count - 1 do
      out +:= utf16CharLength(text[pos1 + k]);
    end for;
  end func;

# 1-based index of the first character on the line holding text[idx].
# Walks backward; returns 1 when no break precedes idx.
const func integer: lineStartBefore (in string: text, in integer: idx) is func
  result
    var integer: out is 1;
  local
    var integer: i is 0;
  begin
    i := idx - 1;
    while i >= 1 and out = 1 do
      if text[i] = '\n' or text[i] = '\r' then
        out := i + 1;
      else
        i := i - 1;
      end if;
    end while;
  end func;

# Last index in text[pos1..stop] before the first line break inside that range.
# Returns stop when no break is present -- the single-line token case.
const func integer: firstLineEnd (in string: text, in integer: pos1, in integer: stop) is func
  result
    var integer: out is 0;
  local
    var integer: i is 0;
  begin
    out := stop;
    for i range pos1 to stop do
      if out = stop and (text[i] = '\n' or text[i] = '\r') then
        out := i - 1;
      end if;
    end for;
  end func;

const proc: report (in string: path) is func
  local
    var string: text is "";
    var boolean: decoded is FALSE;
    var scanCursor: cur is scanCursor.value;
    var tok: tk is tok.value;
    var integer: ls is 0;
    var integer: fb is 0;
    var integer: wantCol is 0;
    var integer: wantWidth is 0;
    var integer: fileToks is 0;
    var integer: fileBad is 0;
    var string: m is "";
    var integer: i is 0;
  begin
    files +:= 1;
    text := readAll(path, decoded);
    if not decoded then
      skips +:= 1;
      writeln(path & "\9;0\9;SKIP:not-valid-utf8");
    elsif length(text) = 0 then
      fatal(path & " read empty or unreadable");
    else
      # maskOf invariant: preserves length and every newline position.
      m := maskOf(text);
      if length(m) <> length(text) then
        fileBad +:= 1;
        writeln(STD_ERR, "MASKLEN " & path & " text=" & str(length(text)) & " mask=" & str(length(m)));
      end if;
      for i range 1 to length(text) do
        if (text[i] = '\n' or text[i] = '\r') <> (m[i] = '\n' or m[i] = '\r') then
          fileBad +:= 1;
          if fileBad <= 25 then
            writeln(STD_ERR, "MASKNL " & path & " at " & str(i));
          end if;
        end if;
      end for;
      # Token column and width check.
      cur := scanCursor.value;
      while cur.offset <= length(text) do
        skipWhitespace(text, cur);
        if cur.offset <= length(text) then
          tk := nextToken(text, cur);
          fileToks +:= 1;
          ls := lineStartBefore(text, tk.start);
          fb := firstLineEnd(text, tk.start, tk.stop);
          wantCol := unitsOf(text, ls, tk.start - ls);
          wantWidth := unitsOf(text, tk.start, fb - tk.start + 1);
          if tk.col16 <> wantCol or tk.width16 <> wantWidth then
            fileBad +:= 1;
            if fileBad <= 25 then
              writeln(STD_ERR, "DIFF " & path
                      & " at=" & str(tk.start)
                      & " kind=" & str(tk.kind)
                      & " col " & str(tk.col16) & "/" & str(wantCol)
                      & " w " & str(tk.width16) & "/" & str(wantWidth));
            end if;
          end if;
        end if;
      end while;
      toks +:= fileToks;
      bad +:= fileBad;
      writeln(path & "\9;" & str(fileToks) & "\9;" & str(fileBad));
    end if;
  end func;

const proc: main is func
  local
    var integer: i is 0;
  begin
    for i range 1 to length(argv(PROGRAM)) do
      report(argv(PROGRAM)[i]);
    end for;
    writeln("SENTINEL files=" & str(files) & " tokens=" & str(toks) & " mismatches=" & str(bad) & " skips=" & str(skips));
    if bad > 0 then
      fatal(str(bad) & " mismatches");
    end if;
    if files = 0 then
      fatal("the file list held no readable file");
    end if;
  end func;
SD7

# Compile with -O2: interpreted is far too slow for 4 million tokens (~82 s compiled vs
# estimated hours interpreted for prg/*.sd7 alone). Compiler output goes to /dev/null --
# only the binary's stdout is the artifact.
s7c -O2 -l "$SRC" "$WORK/tokens_gate.sd7" >/dev/null 2>&1

# Run the compiled binary. The exit code carries three shapes:
#   0 -- clean run, sentinel present
#   1 -- mismatches found (fatal() in the probe), sentinel still printed
#   >=2 -- an unhandled error; the sentinel may be absent
# `set -eu' would abort on any nonzero exit and skip the sentinel grep, so the binary's exit
# is captured explicitly here. The sentinel check below still catches a missing sentinel.
rc=0
"$WORK/tokens_gate" "$SEED7"/lib/*.s7i "$SEED7"/prg/*.sd7 > "$WORK/out.txt" || rc=$?
if [ "$rc" -gt 1 ]; then
  echo "tokens_gate: probe exited $rc" >&2
  exit "$rc"
fi

# The sentinel is DEMANDED, not hoped for: without it the run does not count. Exit 3 when s7
# exited 0 but printed no sentinel -- the shape that does that is a probe whose main the
# interpreter does not recognise.
grep -q '^SENTINEL files=' "$WORK/out.txt" || {
  echo "tokens_gate: no SENTINEL line -- scanner did not complete" >&2
  exit 3
}

if [ -n "$OUT" ]; then
  cat "$WORK/out.txt" > "$OUT"
else
  cat "$WORK/out.txt"
fi
exit "$rc"
