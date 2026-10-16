# Seed7 interpreter CLI

The `s7` / `s7c` command line, the two `-p` flags, the optimizer knobs, how to read
`profile_out` and the measured profiling rows. Moved verbatim out of `AGENTS.md`, which
keeps the rules that make them mandatory (red first, `make test` before and after, never
`time`-ed off the interpreter, never `-s` for a probe).

The headings keep the old section names, so a grep for the old phrase lands here — including the
"*Seed7 traps* below" cross-reference inside the profiling paragraph, which names the next section.

## Every change — profiling

Performance numbers are never `time`-ed off the interpreter. Build a profiled, optimized binary —
`s7c -p -O2 -l src <file>`, run it, and read `profile_out`, which the program writes when it
finishes (`-p` activates simple function profiling, <https://seed7.net/faq.htm#profile_programs>;
`-p` on `s7` is a different flag — its trace-protocol file). The table is
`usecs / calls / place / name`, tab-separated and ordered by time consumed, so the rows at the top
are the cost; the FAQ's own reading rule is that a function called often *and* consuming much time
is the refactoring candidate. Profile the optimized build, because an unoptimized one misleads: the
pass you want to see often hides behind interpreter overhead. Record the command and the table next
to any figure that reaches a document — the measured example is in *Seed7 traps* below. Clean up
after a probe: the binary lands beside its source and `profile_out` in the cwd.

## Seed7 traps — s7/s7c options

- **Profile with `s7c -p`, and never confuse the two `-p` flags.** `s7 -p FILE` names a protocol
  file for trace output. `s7c -p` activates simple function profiling: compile, run the executable,
  and it writes `profile_out` — a tab-separated table of microseconds, call count, `file(line)` and
  function name, ordered by the time each function consumes
  (<https://seed7.net/faq.htm#profile_programs>; a binary may also be profiled with external tools
  such as Valgrind). Measured here as `s7c -p -O2 -l src tests/occurrences_test.sd7`, running it
  gave 194 700 µs in `main`, of which 164 211 µs was 7 `analysisOf` calls (`src/analysis.sd7:333`
  `analyzeAll`, then `collectSyms` at 78 441 µs) — i.e. analysis and the symbol walk dominate, which
  is the evidence behind "one analysis per version" and the buffered-only `locals` guard. Compiled
  probes write a binary next to their source (`tests/occurrences_test`) plus `profile_out` in
  the cwd — delete both; `git status --porcelain -uall` must be empty afterwards.
- **Three optimizer knobs, and one of them is about constants.** Per
  <https://seed7.net/faq.htm#compile>: `-On` tells the *C compiler* to optimise at level 1–3 (`-O`
  is `-O1`); `-ocn` optimises the *generated C code with constants* at level 0–3 — level 1 (the
  default) uses literals and named constants, level 2 also evaluates constant parameter expressions,
  level 3 evaluates **all** constant expressions; `-flto` enables link time optimization. So
  constant folding is `-ocN`, not `-On`, and `-p` measures without optimizing. `s7 -a` suppresses
  only the execution phase, never the constant evaluation.
- **`s7c` IS the interpreter's analyze phase, so the security note has no escape hatch.**
  <https://seed7.net/faq.htm#compile> says `s7c` "uses the analyze phase of the interpreter to
  convert a program to call-code", then emits C, which it calls portable assembler "not intended for
  human readers". Compiling is therefore not a way to avoid evaluating a document: the same engine
  analyses, and the generated program is where evaluation moves to, not where it stops.
- **Never build a probe with `-s`.** `s7c -s x` *suppresses* runtime checks — `d` division by zero,
  `i` index checks (string, array), `o` integer overflow, `r` range checks. This repo depends on
  those staying live: an uncaught `INDEX_ERROR` on stdout costs a suite its graded line (hence the
  degrading accessors in `tests/occurrences_test.sd7`), and `RANGE_ERROR`/`INDEX_ERROR` are what
  `rpc.sd7`'s total accessors catch to keep the protocol channel clean. To see an escape instead use
  `-e` (the executable signals on an uncaught exception, so a debugger can catch it) with `-g`
  (debug information referring to the `.sd7` files and line numbers; only `-g-debug_c` refers to the
  temporary C).
- **`s7` takes options *before* the file name, and fills in a missing `.sd7`.**
  <https://seed7.net/faq.htm#interpreter>: `s7 [options] sourcefile [parameters]`, and if the file
  is not found `.sd7` is appended and searched. That is why the Makefile's `s7 -q -l src
  tests/x_test.sd7` shape is what it is — `-q` compiles quiet (line and file information and
  compilation statistics suppressed), `-l DIR` adds an include-library directory, `-n` removes the
  limit on errors displayed (default 10, so a suite that counts raw diagnostics must not inherit
  that cap), `-a` analyses only, `-i` prints the identifier table after analysis — the same records
  `collectSyms` walks — and `-d x` / `-t x` set the compile-time and runtime trace levels from the
  letters `a c d e h s` (`-t` alone is `-ta`; `s7c -t` takes a different set, `e f s`).
