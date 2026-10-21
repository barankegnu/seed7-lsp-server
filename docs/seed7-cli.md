# Seed7 interpreter CLI, and the evidence behind `AGENTS.md`

Reference material only: nothing in this file is a rule, and every rule it supports is stated
in `AGENTS.md`. Two collections live here because they are consulted *during* an edit, not
before it.

* **The `s7` / `s7c` command line** — the two `-p` flags, the optimizer knobs, the profiling
  recipe and the measured µs rows. Moved verbatim out of `AGENTS.md` when the file was last
  cut; `AGENTS.md` keeps red first, `make test` before and after, and the pointer that says
  never guess a flag.
* **`AGENTS.md` provenance** — the measured figures, citations, fixtures and decision history
  behind the rules that still sit in `AGENTS.md`. Moved out by the later cut, which left a
  pointer at each one. Read a section here when a number, a citation or a past measurement
  bears on your change, or before you restate either. A rule listed below is **not** weaker
  than one in the rules file, and this is not a place a rule goes to stop being enforceable.

The headings below keep `AGENTS.md`'s old section names, so a grep for the old phrase lands
here. Moved text is pasted **verbatim**: if wording here ever disagrees with `AGENTS.md`, the
rules file wins and the disagreement is a defect to fix in one of them.

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

---

# AGENTS.md provenance

## Every change — mutation and measurement provenance

The mutation proof that found four assertions passing for unrelated reasons and one
branch no input could ever reach -- the claim the rules file keeps without its tally:

```
rather than inventing a synthetic trigger. To prove an assertion can fail, mutate one
production branch and require that named check to go FAIL; this found four assertions that
passed for unrelated reasons and one branch no input could ever reach. Do it after
```

"No fixture reaches it" is not "no input reaches it": the guard the unit suite could not
see was killed in two seconds by the wire suite, so the honest answer was a missing fixture,
not an equivalent mutant.

```
it"** — a guard the unit suite could not see was killed in two seconds by the wire suite,
and the honest answer was a missing fixture, not an equivalent mutant. And a probe
```

The two measurement stories, with the numbers they bought:

```
Two measurement rules, both bought with a wrong number that reached a document or a
commit. A byte count must come from the artifact the product emits — the wire
`Content-Length` — never from re-serialising a parsed copy: `json.dumps` writes `", "`
between elements, which turned a 309 521-byte `semanticTokens` frame into a recorded
"451 KB", a 46 % overstatement on a 142 005-element array. And a probe must print a
sentinel that the harness requires before any payload is counted as a result — a fuzz
whose entry point had never run reported fourteen inputs as "no raise" while printing
nothing but the interpreter banner.
```

The tests-written-after example: the nine readFrameBody checks of dd99890, four mutants
that reddened a named check, and the high-surrogate mutant that escaped until two lone-lows
were added -- which is the discovery the check existed to record.

```
should be said so out loud (`dd99890`'s nine `readFrameBody` checks are this case: four mutants reddened
named checks, and one mutant — widening the high-surrogate bound — escaped until two lone-lows were
added, which is the discovery the check existed to record).
```

## Seed7 traps — the refused-name set

`CANNOT_BE_NAME` as measured: 63 entries for `s7` 5.4.10, re-probed word by word. The array
is generated; the rules file keeps the "never hand-edit it, run the generator" command and the
membership that surprises people.

```
- Which names the language refuses is measured, not remembered: `src/keywords.sd7`'s
  `CANNOT_BE_NAME` (63 entries for `s7` 5.4.10) is regenerated by `tools/keyword_gate.sh`, which
  probes `var integer: <WORD> is 1;` per word and exits 1 if the array drifts. `step`, `key`,
  `len`, `range` are on it and fail as parameters AND as locals; `type`, `proc`, `result`, `enum`,
  `and`, `or`, `div` are NOT — `const func integer: type (in integer: n)` analyses and prints `3`.
  Never extend or shorten the array by hand; run the generator.
```

The note that made the hand-written name list subordinate to the generated set:

```
- `key`, `len` and `line` are taken by the language and library. Choose other names.  (The first bullet of this list is the generated, measured set.)
```

## Seed7 traps — original text of the merged bullets

Char and string literals, as two separate bullets before they became one:

```
- Strings are `"...\"..."`. There are no single quotes, and `""` is not escaping.
  Tab inside a literal is `\9;`. A char literal cannot hold the escape character
  (`'\'` does not parse — the escape eats the closing quote): write `chr(92)` and name it.
  `doc_store.BACKSLASH` is that name.
```

```
- A char literal cannot hold the escape character or a quote the way you expect: `'\'` does
  not parse. Use `chr(92)`/`chr(39)` and name them — `doc_store.BACKSLASH`/`SINGLE_QUOTE`.
  The quote character is written `'''` — open, the quote as content, close — and `''''` is
  the parse error ("Character literal exceeds source line"). Verify a spelling with `s7`
  before coding to it; two of this session's test fixtures were wrong because I guessed.
```

`in` / `not in`, as two separate bullets before they became one:

```
- `x not in arr` does not parse when `x` is a struct-field select (`syms[i].sign not in
  shown`); `analysis.listed()` exists because of it.
```

```
- `in` and `not in` work for hashes and sets, but not for arrays: `k in arr` fails to
  match for any `k` and any `array` type. The existing `x not in arr` entry names the
  struct-field-select case; the broader rule is that `in` has no array overload.
```

## Seed7 traps — corrections and wasted cycles recorded

The str(ch) bullet once read no char-to-string conversion, and that cost a wasted
attempt at the M5 surrogate joiner:

```
  what `jsonw.sd7` does, but it is a choice, not a necessity. This line said "no char-to-string
  conversion" and cost a wasted attempt building M5's surrogate joiner.
```

Guessing a char-literal spelling put two fixtures wrong before s7 was asked:

```
  the parse error ("Character literal exceeds source line"). Verify a spelling with `s7`
  before coding to it; two of this session's test fixtures were wrong because I guessed.
```

A parameterised main let one fuzz report a result it had never computed:

```
- `main` takes **no parameter** here. A parameterised `main` (probed with both
  `arguments` and `argv`) was not recognised by 5.4.10: `*** Declaration for main
  missing`, exit 0, and the probe silently never ran — which is how one fuzz of mine
  reported a result it had not computed. The idiom the standard library uses is a plain
```

## Seed7 traps — the bounds-guard case

The slice rule, with the measured branch that shows a green suite proves nothing:

```
- A slice whose low bound exceeds its high bound is the **empty string, silently** —
  `text[3 .. 2]` has length 0. So "I deleted this bounds guard and every suite stayed
  green" proves the guard is *harmless to remove*, never that its `FALSE` branch is
  unreachable; `scan.maskOf`'s gap guard is exactly that case, and its `FALSE` branch is
  ordinary adjacency (`(b`), firing more often than `TRUE` on `a := (b) + c[1];`.
```

## Protocol decisions — the analyzer-column derivation

The three pinned checks in `tests/analysis_test.sd7`, each carrying the raw error count, the
kind, the line and the message beside its column. The rules file keeps the convention, the
`lspRangeBytes` rule and the fact that these checks go red if the interpreter changes; the
figures are here, and re-measure from them before restating one.

```
  escape for `ILLEGAL_STRING_ESCAPE`. Pinned by three checks in
  `tests/analysis_test.sd7`, each carrying the raw error count, the kind, the line
  and the message beside the column: `Illegal string escape "\z"` reports column 26 both after
  `"ππ"` (the `z` there is the 24th character) and after one astral character (there it is
  the 23rd); and the first diagnostic on `    writeln(1) writeln(2);` — **with its
  four-space indent**, the byte arithmetic is not the same without it — is
  `EXPECTED_SYMBOL` at line 4 column 23, one byte past a `writeln` spanning bytes 16-22.
  Change the interpreter's convention and those checks go red.
```

## Protocol decisions — the rename refusals, measured

Both arms as first recorded. The first carries the measured cost of the over-refusal: it
also refuses a legal rename of const integer: x is 1; const integer: y is x;. The second
carries what the field-access arm replaced, and why a silent file that no longer compiles was
the failure mode.

```
- `rename` refuses when the declaration line holds more than one record of the name. Seed7 lets a
  parameter share its routine's name, and the index has no column for a declaration, so choosing by
  line would sometimes rewrite the wrong symbol. Measured cost: it also refuses a legal rename of
  `const integer: x is 1; const integer: y is x;`. Refusal on a write is the rule — do not "fix" the
  over-refusal with a column test unless regions become column-aware.
```

```
- `rename` also refuses when the symbol's own scope window holds the same spelling written after a
  `.' — a record field (`counter := counter + box.counter;`). Measured on `m5-review-fixes`: before
  the arm, the cursor on that local answered six edits, two of them the field access, and the
  field's declaration sits outside the window, so the write renames the field's uses and leaves the
  field — a file that no longer compiles, silently. The flag is `occurrence.dotPrev`, stamped in
  `occurrencesOf` (the only pass that knows the previous token), and the predicate is
  `occurrences.scopeHasFieldAccess`, which applies scope: a field access in another routine must
  not refuse this one's rename, and `features_test.sd7` pins that control. Measured cost: a
  **global** refuses on a field access anywhere in its file, because a global's window is the whole
  document. `references` keeps the over-inclusive list but now sets `unresolved` for it — spec
  12.2's split, read may over-include, write must not.
```

## Protocol decisions — `#` and based literals

Why the radix-versus-comment ambiguity is not theoretical:

```
- `#` is both the line-comment introducer and the radix marker of `16#beef`.
  The scanner decides, because it knows whether it is inside a number token.
  `lib/aes.s7i` has 691 lines with based literals, so this is not theoretical.
```

## Do not "fix" these — the evidence that compiling is not an escape

The rules file keeps the rule and points at README, which is the single source of truth
for it; the s7c mechanism and its citation are here and in the CLI reference above:

```
- Analysis executes the analysed code. It is a property of using the interpreter as the
  parser, not a bug to route around — see the README's security section, which is the
  single source of truth for it. The M3 trust gate now ships: `analysable` gates
  `ensureAnalyzed` and `refresh` by path containment on decoded paths, and a client that
  declares no root runs unguarded. It is a containment control, not a sandbox. Compiling
  is not an escape either: `s7c` produces its call-code by running that same analyze phase
  (<https://seed7.net/faq.htm#compile>), so there is no second front end to hide behind and no
  build flag that makes analysis inert.
```

## Milestones

The M1-M5 record in full: what is merged, what is still open from M3, why R-F10 is a
conformance violation as well as stale data, the M5 reflection re-measurement, the measured
cost of filling every library scope record, and how scan.sd7 carries the UTF-16 column of a
token without a cumulative table. What is true today for a reader is the What works / What does
not work yet pair in README.md; the rules that survive from this record are in AGENTS.md under
Milestones.

```
M1+M2 (base protocol, lifecycle, sync, diagnostics), M3's five symbol features
(documentSymbol, definition, hover, completion, signatureHelp), and M4's scanner and
token-backed features (`scan.sd7`, `blocks.sd7`, `utf8bytes.sd7`, foldingRange,
selectionRange, semanticTokens, one-analysis-per-version) are merged, and M5's cross-reference
features (`occurrences.sd7`, references, file-local `prepareRename`/`rename`) are merged on
`m5-references-and-rename`. Still open from M3: local-variable
completion, and R-F10 — which is a conformance violation as well as stale data, because
`textToAnalyze` reads an open `.s7i` back from disk while the spec says the server must
not read a document's content through its uri.

M5's `occurrences.sd7` is the only use-site index, and it is lexical by necessity, not by
choice: re-measured in M5, reflection still yields declarations only — `body()` answers
`CALLOBJECT` and `getValue(b, attr reference)` fails to match, so there is no use-site walk.
`resolveBinding` decides whose name a token is (a routine's own locals come from
`analysis.sd7`'s scope records, whose cost is measured: filling every library record would add
7–10 ms per analysis) and `inScope` is the ONLY place scope is applied. Two refusals are
invariants of the write path, not preferences: an unprovable binding and `scopeUncertain`
(a nested routine's locals, or a one-line routine's absent region, mean the scope cannot be
seen) both make `rename` answer `null` rather than guess — over-inclusive on a read,
refusal on a write. `workspace/symbol` and project-wide rename are M6: they need an index of
files the editor never opened, and with them the staleness and watching questions R-F10 already
show are not free.

M4's `scan.sd7` is the server's only lexical machine; `doc_store.codeText` is a
projection of it. A token's UTF-16 column is carried forward incrementally by `nextToken`
(`scan.sd7:95` advances `cur.col16` by `utf16CharLength(ch)` per character and `:291`
stamps `out.col16 := cur.col16`), so no cumulative table is built and scanning a whole
document is O(document), not O(document × tokens). The reflection API yields declarations
only, never use sites, which is why references and rename stay M5.
```

## Citation defect, counted and closed

AGENTS.md put the catchable exceptions at lines 277-291 of `lib/seed7_05.s7i` and repeated that
range in Protocol decisions. The Background section of
docs/superpowers/plans/2026-10-16-project-graph-and-agents-layering.md said 280-294 for 5.4.10 and
left the correction to Task 7, which counted it in this checkout. Both AGENTS.md places now carry
the counted range, and the frozen token in `tools/agents_required.txt` was substituted, not added
to beside the stale one.

The commands, run here against the installed interpreter. `grep -n 'type: EXCEPTION'` gives the
type declaration at 256; `grep -n '^const EXCEPTION: ' | sed -n '1p;$p'` gives 280 `OKAY_NO_ERROR`
and 294 `IN_ERROR`; `grep -c` on that pattern gives 15 names, so 14 catchable. Do NOT anchor on
`EXCEPTION is newtype` with single spaces: the declaration is padded (`EXCEPTION      is newtype`),
so that grep prints nothing and exits 1, which reads exactly like an enum that moved. An empty grep
is a bad anchor, not a result.

The masking is the finding worth keeping. While this section still carried the old range it was the
only file in the gate's union holding it, so `tools/agents_gate.sh` printed `agents: 44 checks, 0
failed` AFTER AGENTS.md had been corrected and BEFORE the list entry was substituted: the defect
record was satisfying the check meant to catch the defect. A file that documents a wrong citation
can prop up the net that guards it. So this section names both ranges without the `seed7_05.s7i:`
prefix, which leaves AGENTS.md the only file that can satisfy the token -- a citation dropped or
made stale there now prints MISSING.

## Every change — the mask rebuild cost, measured

`scan.maskOf` is rebuilt on every `didChange` (through `doc_store.setVersion`). Its append loop
used `&`, which copies its whole left side per token, making it quadratic in document size. The
rewrite to `&:=` (`STR_APPEND`, grows in place) is what makes `didChange` cheap.

Profiled, optimized build: `s7c -p -O2 -l src /tmp/mask_cost.sd7` then run `/tmp/mask_cost`,
reading `profile_out` with `awk -F'\t' '$4=="maskOf"{print $1" usecs, "$2" calls"}'`.
The probe calls `maskOf` once on the text of `~/seed7/lib/shiftjis.s7i` (375 352 characters,
read with a `readln` loop — `gets(f, -1)` raises `RANGE_ERROR`).

Before the rewrite:

    22567957 usecs, 1 calls

After the rewrite:

    30239 usecs, 1 calls

Three orders of magnitude. The `ponytail:` lazy-fill upgrade path that lived in
`src/doc_store.sd7`'s note is deleted: at ~30 ms over a stdlib-sized file it no longer matters.
