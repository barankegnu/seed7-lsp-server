#!/bin/sh
# Corpus gate for M5's occurrence index -- a spike, not a suite.
#
# shortcut: this checks only that occurrencesOf terminates and finds a name it just scanned; it
#           does NOT check columns, scopes, or bindings. Those are pinned by the unit and wire
#           suites. Upgrade it to column checks only if scan.sd7's col16 derivation changes.
#
# For every Seed7 source in the checkout it takes the first 12 indexable tokens off the real
# text, asks occurrencesOf for each, and reports a name the SAME scan produced but the index
# could not find. That is a positive control, not a coverage claim: the name comes from the
# scanner, so a zero is a bug in the index rather than a missing fixture.
#
# Not wired into `make test`, and it must not be: it shells out over 340 files and takes
# minutes. Run it when scan.sd7, occurrences.sd7 or utf8bytes.sd7 changes.
#
#   sh tools/corpus_scan.sh [SEED7_DIR]        # default /home/username/seed7
set -eu

SEED7=${1:-/home/username/seed7}
SRC=$(cd "$(dirname "$0")/.." && pwd)/src
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

cat > "$WORK/driver.sd7" <<'SD7'
$ include "seed7_05.s7i";
  include "scan.sd7";
  include "occurrences.sd7";

var integer: files_read is 0;
var integer: names_probed is 0;
var integer: misses is 0;
var integer: occurrences_total is 0;

const func string: readAll (in string: path) is func
  result
    var string: out is "";
  local
    var file: f is STD_NULL;
    var string: one is "";
  begin
    block
      f := open(path, "r");
      while not eof(f) do
        readln(f, one);
        out := out & one & "\n";
      end while;
      close(f);
    exception
      catch FILE_ERROR:
        out := "";
    end block;
  end func;

const proc: probe (in string: path) is func
  local
    var string: text is "";
    var scanCursor: cur is scanCursor.value;
    var tok: tk is tok.value;
    var array string: names is 0 times "";
    var array occurrence: found is 0 times occurrence.value;
    var integer: i is 0;
  begin
    text := readAll(path);
    if length(text) = 0 then
    else
      files_read +:= 1;
      cur := scanCursor.value;
      while cur.offset <= length(text) and length(names) < 12 do
        skipWhitespace(text, cur);
        if cur.offset > length(text) then
        else
          tk := nextToken(text, cur);
          if indexableKind(tk.kind) then
            names &:= text[tk.start .. tk.stop];
          end if;
        end if;
      end while;
      for i range 1 to length(names) do
        found := occurrencesOf(text, names[i]);
        names_probed +:= 1;
        occurrences_total +:= length(found);
        if length(found) = 0 then
          writeln("MISS name=[" & names[i] & "] file=" & path);
          misses +:= 1;
        end if;
      end for;
    end if;
  end func;

const proc: main is func
  local
    var integer: i is 0;
  begin
    for i range 1 to length(argv(PROGRAM)) do
      probe(argv(PROGRAM)[i]);
    end for;
    writeln("CORPUS files=" & str(files_read) & " names_probed=" & str(names_probed) &
            " occurrences=" & str(occurrences_total) & " misses=" & str(misses));
    if misses <> 0 then
      exit(1);
    end if;
  end func;
SD7

[ -d "$SEED7/lib" ] || { echo "corpus_scan: no Seed7 checkout at $SEED7" >&2; exit 2; }
s7 -q -l "$SRC" "$WORK/driver.sd7" "$SEED7"/lib/*.s7i "$SEED7"/prg/*.sd7
