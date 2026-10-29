#!/bin/sh
# R-F10 measurement -- the reason an open .s7i is analysed through analysis.sd7's driverFor(path).
#
# Per library file it runs BOTH routes of the same analysis and prints one row for each:
#   DRIVER  the text analysis.sd7's driverFor(path) builds -- the interpreter opens the file's path
#   LEAD    "$ include "seed7_05.s7i";" then the file's own text -- what a buffer would be
# Each row carries CLEAN/NOISY, errorCount, length(globalObjects(prog)), the number of records whose
# file(obj) is analysis.sd7's BUFFER_FILE, and the first error message. The DRIVER text comes from
# driverFor itself -- the heredoc includes analysis.sd7 and the compile adds -l src -- because a
# retyped copy would measure a route the server no longer has.
#
# Files are read with openUtf8 (utf8.s7i), the charset the interpreter's own source scanner uses.
# A plain open(path, "r") decodes one character per byte, and the C1 characters that produces inside
# string and char literals are what the analyzer then refuses: 16 of the first run's 46 NOISY rows
# were that probe-decoder artifact and not the route. requireDecoded refuses to grade text holding a
# character in U+0080..U+009F, which no decoded Seed7 source file contains, so the contamination
# fails the run instead of becoming a row.
#
# recordsSame counts the libraries whose two routes report the SAME length(globalObjects(prog)), and
# only when that count is real -- the reflection walk reports -1 if it raises, and two failures are
# not an agreement. A library whose counts differ is printed as a RECORDS-DIFF row. The 2026-10-29
# scratch figure of 178 came from comparing the two formatted rows at a fixed byte position, so it
# read "different" whenever the two error counts had different digit widths.
#
# The file list is the argument's domain, not the corpus. textToAnalyze uses driverFor for a .s7i and
# never for a .sd7, so the 129 programs carry no weight here: only the top-level libraries are
# counted, plus prg/hello.sd7 as a CONTROL row. Dropping the essential include from LEAD sends the
# libraries noisy and leaves that CONTROL row clean -- a program is a whole program and a library is
# not -- which is the proof that this probe grades the route rather than the file list.
#
# Not wired into `make test`, and it must not be: it measures rather than checks, and it starts one
# analyze phase per route per library -- two per file, over the 214 libraries plus the control. Run it
# when analysis.sd7's driverFor changes, or when the interpreter's library set does, and commit the
# output as docs/rf10-measurement.md.
#
#   sh tools/rf10_probe.sh [SEED7_DIR]        # default /home/username/seed7
#
# The last line is the sentinel, and no payload counts as a result without it:
#   SENTINEL files=<libraries counted> leadClean=<N> leadNoisy=<N> recordsSame=<N>
set -eu

SEED7=${1:-/home/username/seed7}
SRC=$(cd "$(dirname "$0")/.." && pwd)/src
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

[ -d "$SEED7/lib" ] || { echo "rf10_probe: no library dir at $SEED7/lib" >&2; exit 2; }
[ -f "$SEED7/prg/hello.sd7" ] || { echo "rf10_probe: no control program at $SEED7/prg/hello.sd7" >&2; exit 2; }

cat > "$WORK/rf10_probe.sd7" <<'SD7'
$ include "seed7_05.s7i";
  include "progs.s7i";
  include "ref_list.s7i";
  include "utf8.s7i";
  include "analysis.sd7";

var integer: libFiles is 0;
var integer: leadClean is 0;
var integer: leadNoisy is 0;
var integer: recordsSame is 0;

# The line the LEAD route starts with. BUFFER_FILE and driverFor are analysis.sd7's own, so this
# probe cannot drift from what the server does.
const string: ESSENTIAL is "$ include \"seed7_05.s7i\";\n";

const type: gradeRec is new struct
    var boolean: clean is TRUE;
    var integer: errs is 0;
    var integer: recs is 0;
    var integer: strRecs is 0;
    var string: first is "";
  end struct;

# Every diagnostic goes to stderr: stdout is the artifact's stream, and a half line there would
# read as a measurement.
const proc: fatal (in string: message) is func
  begin
    writeln(STD_ERR, "rf10_probe: " & message);
    exit(1);
  end func;

const func boolean: isC1 (in char: ch) is func
  result
    var boolean: out is FALSE;
  begin
    out := ord(ch) >= 128;
    if out then
      out := ord(ch) <= 159;
    end if;
  end func;

# A decoded Seed7 source file holds no character in U+0080..U+009F. One here means the bytes were
# read one character per byte, so the LEAD route would grade this probe's decoder instead of the
# route -- which is how 16 libraries came to be reported NOISY in the first run.
const proc: requireDecoded (in string: stri, in string: path) is func
  local
    var integer: i is 0;
  begin
    for i range 1 to length(stri) do
      if isC1(stri[i]) then
        fatal(path & " holds code point " & str(ord(stri[i])) & " at offset " & str(i));
      end if;
    end for;
  end func;

# A whole file, read with the readln loop and the charset the interpreter's source scanner uses.
# gets(f, -1) raises RANGE_ERROR (AGENTS.md), and an unreadable or empty file is fatal rather than
# a row, because essential-include-only text grades CLEAN and would be a lie about the library.
const func string: readAll (in string: path) is func
  result
    var string: out is "";
  local
    var file: f is STD_NULL;
    var string: one is "";
  begin
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
        fatal("cannot read " & path);
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
    if length(own) <= 1 then
      # A failed open leaves STD_NULL and the loop reads nothing; a 0-byte file reads as the single
      # "\n" the loop appends. Either text is essential-include-only, which grades CLEAN.
      fatal(path & " read empty or unreadable");
    end if;
    requireDecoded(own, path);
    led := grade(ESSENTIAL & own, dirs);
    if isLibrary then
      libFiles +:= 1;
      drv := grade(driverFor(path), dirs);
      report("DRIVER", path, drv);
      report("LEAD", path, led);
      if led.clean then
        leadClean +:= 1;
      else
        leadNoisy +:= 1;
      end if;
      if drv.recs = led.recs and drv.recs >= 0 then
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
      fatal("the file list held no .s7i library");
    end if;
  end func;
SD7

echo "# rf10_probe.sh -- DRIVER (analysis.sd7 driverFor) vs LEAD (buffer text), one row per route"
echo "# columns: route file verdict errors=<errorCount> records=<length(globalObjects)> string=<records with file()=BUFFER_FILE> first=<getError(1).message>"
echo "# seed7 tree: $SEED7 $(git -C "$SEED7" rev-parse --short HEAD 2>/dev/null || echo "(not a git checkout)")"

# s7c writes its progress to stdout, which is the artifact's stream, so the compile goes to a log;
# it is replayed on stderr only when the compile fails.
s7c -O2 -l "$SEED7/lib" -l "$SRC" "$WORK/rf10_probe.sd7" > "$WORK/s7c.log" 2>&1 || { cat "$WORK/s7c.log" >&2; exit 1; }
"$WORK/rf10_probe" "$SEED7"/lib/*.s7i "$SEED7"/prg/hello.sd7
