#!/bin/sh
# R-F10 measurement -- the reason an open .s7i is analysed through analysis.sd7's driverFor(path).
#
# Per library file it runs BOTH routes of the same analysis and prints one row for each:
#   DRIVER  "$ include "seed7_05.s7i";" then `include <the file's own path>;` -- what the server does
#   LEAD    "$ include "seed7_05.s7i";" then the file's own text              -- what a buffer would be
# Each row carries CLEAN/NOISY, errorCount, length(globalObjects(prog)), the number of records whose
# file(obj) is "STRING", and the first error message.
#
# recordsSame counts the libraries whose two routes report the SAME length(globalObjects(prog)).
# The 2026-10-29 scratch figure of 178 came from comparing the two formatted rows at a fixed byte
# position, so it read "different" whenever the two error counts had different digit widths; 213 of
# the 214 libraries agree, and the one that does not is printed as a RECORDS-DIFF row.
#
# shortcut: the DRIVER text is driverFor's shape copied by hand, because the probe is compiled with
#           -l only for the interpreter's library. If driverFor changes, this stops describing it.
#
# The file list is the argument's domain, not the corpus. textToAnalyze uses driverFor for a .s7i and
# never for a .sd7, so the 129 programs carry no weight here: only the top-level libraries are
# counted, plus prg/hello.sd7 as a CONTROL row. Dropping the essential include from LEAD sends the
# libraries noisy and leaves that CONTROL row clean -- a program is a whole program and a library is
# not -- which is the proof that this probe grades the route rather than the file list.
#
# Not wired into `make test`, and it must not be: nothing here can go RED -- it measures, it does not
# check -- and the run costs 22 s wall for 215 files, 5 s of that the s7c compile (measured). Run it
# when analysis.sd7's driverFor changes, or when the interpreter's library set does, and commit the
# output as docs/rf10-measurement.md.
#
#   sh tools/rf10_probe.sh [SEED7_DIR]        # default /home/username/seed7
#
# The last line is the sentinel, and no payload counts as a result without it:
#   SENTINEL files=<libraries counted> leadClean=<N> leadNoisy=<N> recordsSame=<N>
set -eu

SEED7=${1:-/home/username/seed7}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

[ -d "$SEED7/lib" ] || { echo "rf10_probe: no library dir at $SEED7/lib" >&2; exit 2; }
[ -f "$SEED7/prg/hello.sd7" ] || { echo "rf10_probe: no control program at $SEED7/prg/hello.sd7" >&2; exit 2; }

cat > "$WORK/rf10_probe.sd7" <<'SD7'
$ include "seed7_05.s7i";
  include "progs.s7i";
  include "ref_list.s7i";

var integer: libFiles is 0;
var integer: leadClean is 0;
var integer: leadNoisy is 0;
var integer: recordsSame is 0;

# The line every route starts with, and the value analysis.sd7's BUFFER_FILE holds for a
# declaration made in the text handed to parseStri.
const string: ESSENTIAL is "$ include \"seed7_05.s7i\";\n";
const string: BUFFER_FILE is "STRING";

const type: gradeRec is new struct
    var boolean: clean is TRUE;
    var integer: errs is 0;
    var integer: recs is 0;
    var integer: strRecs is 0;
    var string: first is "";
  end struct;

# A whole file, read with the readln loop. gets(f, -1) raises RANGE_ERROR (AGENTS.md).
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
        out &:= one;
        out &:= "\n";
      end while;
      close(f);
    exception
      catch FILE_ERROR:
        out := "";
    end block;
  end func;

const proc: countRecords (in program: prog, inout gradeRec: out) is func
  local
    var ref_list: objs is ref_list.EMPTY;
    var reference: obj is NIL;
  begin
    objs := globalObjects(prog);
    out.recs := length(objs);
    for obj range objs do
      if file(obj) = BUFFER_FILE then
        out.strRecs +:= 1;
      end if;
    end for;
  end func;

# One analyze phase, the same parseOptions and libraryDirs the server passes (main.sd7: ".").
# parseStri is deliberately unguarded here, as it is in analysis.sd7's analyzeAll.
const func gradeRec: grade (in string: stri, in array string: dirs) is func
  result
    var gradeRec: out is gradeRec.value;
  local
    var program: prog is program.EMPTY;
  begin
    prog := parseStri(stri, parseOptions.value, dirs);
    out.errs := errorCount(prog);
    out.clean := out.errs = 0;
    if not out.clean then
      out.first := getError(prog, 1).message;
    end if;
    block
      countRecords(prog, out);
    exception
      # A walk that raises reports -1, so a partly-counted list cannot read as a real count.
      catch RANGE_ERROR:
        out.recs := -1;
      catch INDEX_ERROR:
        out.recs := -1;
      catch ILLEGAL_ACTION:
        out.recs := -1;
    end block;
    if out.recs < 0 then
      out.strRecs := -1;
    end if;
  end func;

const func string: verdict (in boolean: ok) is func
  result
    var string: out is "";
  begin
    if ok then
      out := "CLEAN";
    else
      out := "NOISY";
    end if;
  end func;

const proc: report (in string: route, in string: path, in gradeRec: g) is func
  begin
    writeln(route & " " & path & " " & verdict(g.clean) &
            " errors=" & str(g.errs) & " records=" & str(g.recs) &
            " string=" & str(g.strRecs) & " first=" & g.first);
  end func;

const proc: probeFile (in string: path, in boolean: isLibrary,
                       in array string: dirs) is func
  local
    var string: own is "";
    var gradeRec: drv is gradeRec.value;
    var gradeRec: led is gradeRec.value;
  begin
    own := readAll(path);
    led := grade(ESSENTIAL & own, dirs);
    if isLibrary then
      libFiles +:= 1;
      drv := grade(ESSENTIAL & "  include " & literal(path) & ";\n", dirs);
      report("DRIVER", path, drv);
      report("LEAD", path, led);
      if led.clean then
        leadClean +:= 1;
      else
        leadNoisy +:= 1;
      end if;
      if drv.recs = led.recs then
        recordsSame +:= 1;
      else
        writeln("RECORDS-DIFF " & path & " driver=" & str(drv.recs) &
                " lead=" & str(led.recs));
      end if;
    else
      report("CONTROL", path, led);
    end if;
  end func;

const proc: main is func
  local
    var integer: i is 0;
    var string: path is "";
    var array string: dirs is 0 times "";
  begin
    dirs := 1 times ".";
    for i range 1 to length(argv(PROGRAM)) do
      path := argv(PROGRAM)[i];
      probeFile(path, endsWith(path, ".s7i"), dirs);
    end for;
    writeln("SENTINEL files=" & str(libFiles) & " leadClean=" & str(leadClean) &
            " leadNoisy=" & str(leadNoisy) & " recordsSame=" & str(recordsSame));
    if libFiles = 0 then
      writeln("rf10_probe: the file list held no .s7i library");
      exit(1);
    end if;
  end func;
SD7

echo "# rf10_probe.sh -- DRIVER (analysis.sd7 driverFor) vs LEAD (buffer text), one row per route"
echo "# columns: route file verdict errors=<errorCount> records=<length(globalObjects)> string=<records with file()=STRING> first=<getError(1).message>"
echo "# seed7 tree: $SEED7 $(git -C "$SEED7" rev-parse --short HEAD 2>/dev/null || echo "(not a git checkout)")"

# s7c writes its progress to stdout, which is the artifact's stream, so the compile goes to a log;
# it is replayed on stderr only when the compile fails.
s7c -O2 -l "$SEED7/lib" "$WORK/rf10_probe.sd7" > "$WORK/s7c.log" 2>&1 || { cat "$WORK/s7c.log" >&2; exit 1; }
"$WORK/rf10_probe" "$SEED7"/lib/*.s7i "$SEED7"/prg/hello.sd7
