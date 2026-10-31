#!/bin/sh
# Corpus gate for blockRegions -- a spike, not a suite.
#
# It prints the ANSWER, not a verdict: one line per Seed7 source file,
#   <path>\t<region count>\t<start-end[:kind] ...>
# for every `lib/*.s7i` and `prg/*.sd7` in the Seed7 checkout. The value is the diff between two
# runs: a refactor of the post-passes in `src/blocks.sd7` may move no answer, and 344 real files
# (24 981 055 bytes of source -- `LC_ALL=C wc -c ~/seed7/lib/*.s7i ~/seed7/prg/*.sd7 | tail -1', the
# same two globs the run below passes; 4 881 regions in the worst one, prg/chkarr.sd7) is the widest
# such check this tree can build. The regions come from `blockRegions` in `src/blocks.sd7` itself --
# a retyped copy would gate a machine the server does not have.
#
# Files are read with openUtf8 and a readln loop, the same decoded text the server sees. A plain
# open(path, "r") decodes one character per byte; `tools/rf10_probe.sh`'s header documents what that
# contamination did to a measured figure. `gets(f, -1)` is not an option: it raises RANGE_ERROR at
# ut8_rtl.c(586).
#
# One file in the corpus cannot be decoded at all: `prg/err.sd7` is the interpreter's own
# invalid-encoding test program, and readln over it raises RANGE_ERROR at ut8_rtl.c(771). It gets a
# labelled SKIP row rather than a region list, so the row set is still one line per corpus file and
# the diff stays meaningful. The raise is caught because an uncaught Seed7 exception prints its
# trace to STDOUT -- the artifact's own stream -- which is how the first run of this gate came to
# have five trace lines appended to it.
#
# The 215 `lib/*.s7i` and 129 `prg/*.sd7` files are otherwise valid UTF-8; nothing here opens an
# undecodable file without the catch above.
#
# lastLine is computed the way `tests/blocks_test.sd7` computes it -- pred(linesIn(text)) over the
# text's own newline count -- so the gate's input shape is the unit suite's input shape.
#
# Not wired into `make test`, and it must not be: it is a measurement over an external corpus, it
# takes ~23 s on this tree (41.4 s measured against the quadratic post-passes it gated), and it
# compares against a baseline file rather than asserting anything by itself. Run it before and after
# any change to blockRegions, and diff the two artifacts.
#
#   sh tools/regions_gate.sh [OUTFILE] [SEED7_DIR]   # OUTFILE default stdout,
#                                                    # SEED7_DIR default /home/username/seed7.
#                                                    # There is no /dev/stdout default any more, so
#                                                    # naming SEED7_DIR alone needs an explicit
#                                                    # empty first argument:
#                                                    #   sh tools/regions_gate.sh "" ~/seed7
#
# The last line is the sentinel, and no payload counts as a result without it -- absent, the script
# exits 3 and writes nothing to OUT:
#   SENTINEL files=<rows written> regions=<regions across them>
set -eu

# The artifact is diffed line by line, so the row order must be the byte order of the glob rather
# than the shell's collation -- the same reason `tools/rf10_probe.sh' sets it.
LC_ALL=C
export LC_ALL

OUT=${1:-}
SEED7=${2:-/home/username/seed7}
SRC=$(cd "$(dirname "$0")/.." && pwd)/src
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

[ -d "$SEED7/lib" ] || { echo "regions_gate: no Seed7 checkout at $SEED7" >&2; exit 2; }

cat > "$WORK/regions_gate.sd7" <<'SD7'
$ include "seed7_05.s7i";
  include "utf8.s7i";
  include "blocks.sd7";

var integer: files is 0;
var integer: regions is 0;
var integer: skips is 0;

# Every complaint goes to stderr: stdout is the artifact's stream, and a stray line there would
# read as a row.
const proc: fatal (in string: message) is func
  begin
    writeln(STD_ERR, "regions_gate: " & message);
    exit(1);
  end func;

# A whole file, with the readln loop and the charset the interpreter's own source scanner uses.
# `decoded' comes back FALSE for a file whose bytes no UTF-8 decoder accepts, which is a result the
# caller must see rather than an empty text it would read as a clean file.
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
        out := "";
        decoded := FALSE;
    end block;
  end func;

# blocks_test.sd7's line count, copied rather than imported because that file defines main and so
# cannot be included. A trailing newline counts as a phantom line, and pred(linesIn(text)) is the
# lastLine the suite hands blockRegions.
const func integer: linesIn (in string: text) is func
  result
    var integer: out is 1;
  local
    var integer: i is 0;
  begin
    for i range 1 to length(text) do
      if text[i] = '\n' then
        out +:= 1;
      end if;
    end for;
  end func;

const proc: report (in string: path) is func
  local
    var string: text is "";
    var array blockRef: rs is 0 times blockRef.value;
    var boolean: decoded is FALSE;
    var integer: i is 0;
    var string: line is "";
  begin
    files +:= 1;
    text := readAll(path, decoded);
    line := path & "\9;";
    if not decoded then
      skips +:= 1;
      line &:= "0\9;SKIP:not-valid-utf8";
    elsif length(text) = 0 then
      # A failed open leaves STD_NULL and the loop reads nothing, and a 0-byte file reads as the
      # single "\n" the loop appends. Either would print a plausible empty row.
      fatal(path & " read empty or unreadable");
    else
      rs := blockRegions(text, pred(linesIn(text)));
      regions +:= length(rs);
      line &:= str(length(rs)) & "\9;";
      for i range 1 to length(rs) do
        if i > 1 then
          line &:= " ";
        end if;
        line &:= str(rs[i].startLine) & "-" & str(rs[i].endLine);
        if rs[i].kind <> "" then
          line &:= ":" & rs[i].kind;
        end if;
      end for;
    end if;
    writeln(line);
  end func;

const proc: main is func
  local
    var integer: i is 0;
  begin
    for i range 1 to length(argv(PROGRAM)) do
      report(argv(PROGRAM)[i]);
    end for;
    writeln("SENTINEL files=" & str(files) & " regions=" & str(regions) & " skips=" & str(skips));
    if files = 0 then
      fatal("the file list held no readable file");
    end if;
  end func;
SD7

s7 -q -l "$SRC" "$WORK/regions_gate.sd7" "$SEED7"/lib/*.s7i "$SEED7"/prg/*.sd7 > "$WORK/out.txt"

# The sentinel is DEMANDED, not hoped for: AGENTS.md forbids judging a run by its status code, and
# only the sentinel proves `main' ran to the end. The two failure paths catch different failures, and
# neither writes OUT. `set -eu' catches a nonzero s7 -- an analysis error exits 1, measured in "Seed7
# traps -- the exit code, re-measured" in docs/seed7-cli.md -- and aborts on the run line, before this
# grep and before the copy to OUT; that is what the old one-line redirect could not do, and why it
# left a 0-byte artifact for the next reader to diff (measured at 3b64d54 with a `blocks.sd7' that did
# not parse). Exit 3 is therefore reachable only when s7 exits 0 and still printed no sentinel, and
# the shape that does that is a probe which analysed CLEAN but whose `main' the interpreter does not
# recognise: it prints `*** Declaration for main missing' on stdout instead of any row. That printf is
# gated on a zero error count, so a `main' that FAILED to analyse exits 1 and `set -eu' already caught
# it on the run line above -- it cannot reach this grep. Because OUT survives both paths, a STALE
# artifact is what the next reader diffs: check its SENTINEL row and line count against the new run,
# not only the diff between them.
grep -q '^SENTINEL files=' "$WORK/out.txt" || {
  echo "regions_gate: no SENTINEL line -- s7 did not complete" >&2
  exit 3
}

if [ -n "$OUT" ]; then
  cat "$WORK/out.txt" > "$OUT"
else
  cat "$WORK/out.txt"
fi
