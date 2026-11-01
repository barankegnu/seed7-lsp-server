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
`s7c -p -l src <file>`, run it, and read `profile_out`, which the program writes when it
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
  such as Valgrind). Measured here as `s7c -p -l src tests/occurrences_test.sd7`, running it
  gave 194 700 µs in `main`, of which 164 211 µs was 7 `analysisOf` calls (`analyzeAll`, now at
  `src/analysis.sd7:354`, then `collectSyms` at 78 441 µs) — analysis and the symbol walk dominate, which
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

## Build — the two flag sets

The invocation this project uses to compile the server or a probe. Both lines were run against
this tree on 2026-10-22; the flags are transcribed from `~/seed7/doc/s7c.1`, never guessed.

| build | flags |
|---|---|
| release | `-O3 -flto -oc3 -w2` |
| debug | `-O3 -flto -oc3 -w2 -e -g-debug_c -p -tefs` |

With `-l src src/main.sd7` after them, and what each flag is (`s7c.1`, and
<https://seed7.net/faq.htm#compile> for the optimizer knobs):

- `-On` — hands `-O3` to the *C compiler*; `-ocn` optimises the generated C **with constants**,
  where level 3 evaluates *all* constant expressions. Constant folding is `-ocN`, not `-On`.
- `-flto` — link time optimization.
- `-w2` — warning level 2 (`-wn`).
- `-e` — the executable signals on an uncaught exception, so a debugger can catch it; pair with
  `-g` (debug information referring to the `.sd7` files) or `-g-debug_c` (referring to the
  temporary C). Never pair either with `-s`: that *suppresses* the runtime checks this repo
  depends on.
- `-p` — simple function profiling; the run writes `profile_out` in the cwd.
- `-tefs` — runtime trace levels from the set `e f s`.

Measured, release line: builds in 7.2 s to an 1 888 176-byte `src/main`, and that binary speaks
the protocol — one probe sent `initialize` (with `rootUri`), a `didOpen` of a broken document,
`shutdown` and `exit`, and got 3 frames back, `hoverProvider` present and an Error diagnostic
published, with nothing but frames on stdout.

**The debug line must not be used to run the server.** Bisected on this tree: `-te` prints every
caught exception to **stdout** — `*** Exception INDEX_ERROR raised at hsh_rtl.c(1073)` followed by
the interactive `RETURN / * / /` prompt — and `atKey` catches `INDEX_ERROR` and `ILLEGAL_ACTION` on
the request path *by design* (`src/rpc.sd7`), so those bytes land in the protocol channel. Measured:
stdout began with 642 bytes of non-frame text before the first frame; `-p` alone, `-e` alone and
`-tf`/`-ts` each stayed clean, so `e` is the whole cause. The debug line is therefore for a probe
you run by hand to find a crash, not for a session. To trace a running server, build
`-O3 -flto -oc3 -w2 -e -g-debug_c -p -tfs` — verified clean — and remember `profile_out` appears in
its cwd.

What each build leaves behind, measured: the release line leaves only `src/main`; the debug line
also keeps `src/tmp_main.c` (5 030 213 bytes), because `-g-debug_c` points the debug information at
the generated C and s7c does not delete the file it refers to. Both are gitignored and
`make clean-build` removes them together with `profile_out`. `make build`, `make build-debug` and
`make clean-build` are these two lines in the Makefile; `make build-debug` uses the `-tfs` form
above, so a traced server is buildable without ever putting a byte on the protocol channel —
verified the same way: 3 frames, `hoverProvider` present, Error diagnostic published, `-> main`
trace lines on stderr only.

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

Both revert recipes in the executed plans are the same trap, one level finer. The id plan tells a
mutator to revert each mutation with `git checkout HEAD -- <file>`, and two of its tasks did exactly that.
The command restores the *committed* file, so it also discards any uncommitted work in that file: on this
branch it ate the coordinator's own new `transcript` pin along with the mutation it was undoing, and the
proof had to be run a second time after the check was re-applied. `AGENTS.md` § *Every change* now names
both forms — `git checkout -- .` (index) and `git checkout HEAD -- <file>` (committed state) — and the rule
is to restore the exact bytes changed when a file has uncommitted work in it. The plans keep the old
recipe as written: a plan describes the tree as it was when it was authored, not as it is.

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
  `scan.BACKSLASH` is that name.
```

```
- A char literal cannot hold the escape character or a quote the way you expect: `'\'` does
  not parse. Use `chr(92)`/`chr(39)` and name them — `scan.BACKSLASH`/`scan.APOSTROPHE`.
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

The M1-M5 record in full, plus what `m5-containment-and-rf10` merged on top of it: what is
merged, what is still open from M3, why R-F10 is a
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

`m5-containment-and-rf10` merges two waves over M5. The R-F10 *disclosure*: `refresh` appends one
`Information` diagnostic per publish, for a `.s7i` buffer and for no other document
(`src/lsp_server.sd7`'s `LIB_STALE_MESSAGE`), anchored by `doc_store.firstNonEmptyLine` because all
266 real libraries open with an empty line and a range over an empty line has no width; with it,
`doc_index`'s prose read catches `RANGE_ERROR`, so an unreadable comment costs the prose and not
the whole hover. Request-id *fidelity*: `rpc.sd7` echoes the id as the JSON text `readJson` saw
(a string, a float, an exponent, an integer too wide for Seed7's `integer`), treats any echoable id
as a request, and answers nothing at all when there is nothing to echo — which is what removed the
string-id `-32601` silence and the answer delivered under a borrowed id. R-F10 itself stays open:
what closed is the silence, not the staleness. The measurements are the sections below — *R-F10 —
the two routes, measured*, *Do not "fix" these — the `-32603` net, reached by `readJson`*, and
*Protocol decisions — the exit code and the id on the wire, measured*.
```

## Figures re-measured against the sibling checkouts, 2026-10-21

Every figure below was restated from a fresh run of the command beside it, against the `~/seed7`
and `~/Seed7Home` checkouts on this machine (`Seed7Home` HEAD dated the same day). The older
numbers elsewhere in these documents are not errors — they are measurements of an earlier tree.

| figure | now | command |
|---|---|---|
| `libraries/*.htm` declaration anchors | 3001 (2923 distinct) | `grep -ho '<a name="[^"]*"' libraries/*.htm \| wc -l` (\| `sort -u \| wc -l`) |
| `<li><a href="libraries/` in `subject_index.htm` | 3173 (2988 with a `#`, 185 plain) | `grep -c '<li><a href="libraries/' subject_index.htm` |
| all `<li><a` there | 3493 (320 to other dirs: 286 `manual/`, 34 `scrshots/`) | `grep -o '<li><a href="[^"]+"' subject_index.htm \| wc -l` |
| `subject_index.htm` size | 524 628 bytes | `wc -c < subject_index.htm` |
| `$ syntax` lines in `lib/syntax.s7i` | 194 | `grep -c '^\$ syntax' lib/syntax.s7i` |
| distinct `$ syntax` terminals | 77 (unchanged) | the M4 §6.2 pipeline |
| `CANNOT_BE_NAME` entries | 63 (unchanged) | `sh tools/keyword_gate.sh` |
| `corpus_scan.sh`'s file set | 344 (215 `lib/*.s7i` + 129 `prg/*.sd7`), re-measured 2026-10-31; the row read 342 / 213 for the life of the branch, and what moved is the installed library set, not the tool: `lib/pixel.s7i`, last touched at Seed7 `f849fc6a` (2026-10-23), and `lib/pointlist.s7i`, added at `bafe40e2` (2026-10-26), are the two files the older row did not count | `ls lib/*.s7i prg/*.sd7 \| wc -l`; the two additions: `git -C ~/seed7 log --diff-filter=A --format='%h %ad' --date=short --name-only -- 'lib/*.s7i' \| head -6` |
| suite totals | 21 suites, 1135 checks — these nine are the suites that moved or that carry a figure here, not an enumeration of the 21: `rpc` 47, `scan` 66, `doc_store` 81, `features` 191, `lsp_server` 82, `doc_index` 14, `transcript` 227, `blocks` 83, `agents` 45 (the 1040 row was measured 2026-10-21 on this suite set, before these checks existed; 1 061 → 1 064 is the test-discipline wave's `hover` and `signatureHelp` wire pins plus `libFirstLength`'s path-declared `definition` pin; 1 064 → 1 075 is the R-F10 disclosure wave, measured 2026-10-30: `lsp_server` 79 → 82, `transcript` 196 → 202, `doc_index` 10 → 12, `scan` and `features` unmoved; 1 075 → 1 076 is the gate's own list growing by the one token that freezes the heading of the section below, so the `agents` figure in this row is the number `make test-agents` prints, not a suite's assertions; 1 076 → 1 077 is the fix wave's one `transcript` check, the hover of a func declared in `lib/asn1.s7i`, which reads its prose from disk and is the only wire pin on that read; 1 077 → 1 100 is the request-id wave, measured 2026-10-31 at HEAD and against the tree at `8d00014`, where the 1 077 was taken: `rpc` 31 → 47 — the largest single growth on the branch, the id-fidelity pins (string, float, exponent, over-wide, surrogate pair) plus the notification-silence pins — and `transcript` 203 → 210; the other 19 suites are unmoved — which per-suite measurement shows and arithmetic does NOT: equal sums at the two endpoints bound the total, they do not force each member, since one suite could grow while another shrank (1 100 − 47 − 210 = 1 077 − 31 − 203 = 843). That correction is the id plan's own Task 2 Step 2 rule — if the run disagrees, the run wins — landing one wave late. 1 100 → 1 106 is the disclosure-anchor and `RANGE_ERROR`-half fix wave, measured 2026-10-31: `transcript` 210 → 211 (the disclosure's non-zero-width pin, on a library fixture whose line 1 is empty as every real `.s7i` has it), `doc_store` 77 → 80 (the three cases of `firstNonEmptyLine`), `doc_index` 12 → 14 (the `catch` arm and the empty-list reset inside it, pinned separately); 1 106 → 1 108 is the minors pass on that review: `transcript` 211 → 212 and `doc_store` 80 → 81. The first is the pin that the library fixture's line 1 IS empty — the anchor checks DERIVE their line from the fixture, so deleting the blank line keeps every one of them green while the production helper is reverted; the original defect survived precisely because nothing pinned that property. The second pins a CRLF blank prefix, which was right on the wire by inheritance from the line-break model and had no check at all. 1 108 → 1 133 is the transport-and-region wave, measured 2026-10-31 at `3b64d54` by `make test` (21 suites, 1 133 checks, 0 failed): `transcript` 212 → 225 and `blocks` 71 → 83, and the other 19 unmoved because nothing could move them: `git diff --name-only 5d8b72c..HEAD` touches only `src/blocks.sd7`, `src/transport.sd7` and those two suites' own files — so the two deltas (+13, +12) sum to the total's +25 rather than merely happening to. `transcript`'s 13 are the framing pins, one commit at a time: +1 for the fourth hostile label, `over-wide` (`e24e464`), +4 for the two undecodable-byte sessions (`8d9e630`), +2 for the continuation-header session (`676ff57`), and +2 for the length-less block with +4 for the one-framing-line-per-fatal-frame pin across the four labels (`a1753f1`). `blocks`'s 12 are three fixtures at three checks each (the region list, the region invariant, `linesIn` matches `lineCount`): Task 4's two `is <value>` fixtures (`311b34e`, 71 → 77), Task 5's `is new enum` pin (`007812f`, 77 → 80) and its round-1 per-window fixture 6 (`3b64d54`, 80 → 83). 1 133 → 1 135 is the merge-fix wave, measured 2026-10-31 at HEAD by `make test` (21 suites, 1 135 checks, 0 failed): `transcript` 225 → 227 for review finding I3's two `-32700` pins, the other 20 suites unmoved because that wave touched `tests/transcript.py` and four documentation files and no `src/` file — `git diff --stat` over it shows `src/` empty. | `make test`; the 31 and the 203: `git archive 8d00014 src tests \| tar -x -C /tmp/at1077` then `s7 -q -l /tmp/at1077/src /tmp/at1077/tests/rpc_test.sd7` and `python3 /tmp/at1077/tests/transcript.py` |

Two measurement traps found while taking these, both of which produce a confidently wrong number:

- **A case-limited character class silently undercounts the keyword set.** `"[a-z_0-9]+"` finds
  62 entries in `src/keywords.sd7`, not 63, because one word is `fixLen`. The array is correct;
  the regex was wrong. Count mixed-case words with `[A-Za-z_0-9]+` or verify against
  `sh tools/keyword_gate.sh`, which re-derives the set from the interpreter itself.
- **`find` recurses where the tool's glob does not.** `find ~/seed7/lib ~/seed7/prg -name '*.s7i'
  -o -name '*.sd7'` reports 396 files, because `lib` holds 266 `.s7i` counting its
  subdirectories (215 top level + 51 in `lib/comp`) and `prg` holds one `.s7i` of its own
  (`dna_base.s7i`) beside its 129 `.sd7`, while `tools/corpus_scan.sh` passes
  `"$SEED7"/lib/*.s7i "$SEED7"/prg/*.sd7` and so sees 344 (both re-measured 2026-10-31; the document
  carried 394 / 264 / 342, which were the same install two libraries short of this one —
  `lib/pixel.s7i` and `lib/pointlist.s7i`, above). A drift claim against that number was an artifact
  of the measuring command, not of the checkout; re-derive a file count with the same glob the tool
  uses, and remember the recursion also picks up that one `prg/*.s7i`.

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

Profiled, optimized build: `s7c -p -l src /tmp/mask_cost.sd7` then run `/tmp/mask_cost`,
reading `profile_out` with `awk -F'\t' '$4=="maskOf"{print $1" usecs, "$2" calls"}'`.
The probe calls `maskOf` once on the text of `~/seed7/lib/shiftjis.s7i` (375 352 characters,
read with a `readln` loop — `gets(f, -1)` raises `RANGE_ERROR`).

Before the rewrite:

    22567957 usecs, 1 calls

After the rewrite:

    30239 usecs, 1 calls

746×. The `ponytail:` lazy-fill upgrade path that lived in
`src/doc_store.sd7`'s note is deleted: the ratio holds, but the absolute ~30 ms is an
optimized-build figure (`s7c -p`); the shipped interpreted server pays more per call.

## Every change — the two hot paths, measured

Two conversions walked the whole document where a line would do, and both were on the keystroke
path. `doc_store.lspRange` turned the analyzer's byte column into a character column with
`utf16Before(start + ch) - utf16Before(start)` — two walks from index 1, so a publish of N
diagnostics cost O(N × document) — and `features/selection_range.sd7` called `blocks.blockRegions`
inside `chainForPosition`, so one request with P positions paid P full-document scans. The fixes are
`unitsOfPrefix` (walk the line, stop at `count` or a break) and `enclosingRegionsFrom` (filter the
list the caller already holds). `utf16Before` and `enclosingRegions` are gone; neither has a caller.

Command, on the committed code, both sides of each pair — `50833bb` for before, `2f37da4` for after,
each built as its own binary from its own tree so the comparison is binary-vs-binary:

    git worktree add -f --detach /tmp/rm/base 50833bb
    for L in <the two src dirs>; do s7c -p -l $L /tmp/rm/d1.sd7; done   # then run each
    awk -F'\t' '$4=="diagnosticsJson"{print $1, $2, $4}' profile_out

Probes are `/tmp/rm/d1.sd7` (`lib/shiftjis.s7i`, 375 354 characters, 100 diagnostics placed at
`line1 := 30 + i * 36`, five `diagnosticsJson` calls), `/tmp/rm/d2.sd7` (a synthetic 2 004-line /
113 005-character document, those diagnostics on its first hundred lines) and `/tmp/rm/s.sd7`
(`shiftjis.s7i` again, 32 positions on lines `500 + i * 12`, `character: 10`, three
`selectionResult` calls). Every one prints a `SENTINEL` line with the document size and the published
frame's byte length before any timing row is read, and `profile_out` is the only source of the µs.

| probe | `50833bb` | `2f37da4` | published bytes |
|---|---|---|---|
| `d1` `diagnosticsJson`, 5 publishes on `shiftjis.s7i` | 17 277 011 µs | 4 986 µs | 13 684 both sides |
| per publish | 3.46 s | 997 µs | 3 464× |
| `d2` `diagnosticsJson`, 5 publishes on the 2 004-line document | 272 654 µs | 4 535 µs | 13 322 both sides |
| per publish | 54.5 ms | 907 µs | 60× |
| `s` `selectionResult`, 3 requests of 32 positions | 6 864 122 µs | 668 029 µs | 5 441 both sides |
| per request | 2.29 s | 223 ms | 10.3× |
| `s` `blockRegions` calls for those 3 requests | 96 | 3 | — |

The published bytes matching on every probe is the point of the exercise, not a footnote: both changes
claim to move no answer, and a byte-equal frame from `d1`/`d2`/`s` is what makes that claim observed
rather than argued. It is also what the equivalence sweep covers more broadly — `lspRange` old against
new over 3 674 148 line-and-column positions (every line, every column, out-of-range lines included,
across `shiftjis.s7i`, a document mixing astral and 2-byte characters with lone `\r`, `\r\n` and `\n`,
a final line with no terminator, and the empty document) returned 0 disagreements, and 375 464 when
the off-by-one `n <= count` was injected into the new helper. A comparison that has never failed is
not evidence.

Three caveats, all of them this file's own kind of honesty:

- **Absolute µs move between runs of identical binaries.** This branch has three sets of rows for the
  same fix: 16 697 357 / 3 440 (measured in a scratch copy while the plan was being written, quoted in
  the plan), 14 821 089 / 3 532 (measured by the implementing agent, and what
  `src/doc_store.sd7`'s comment and commit `3a6c8ef` carry), and the 17 277 011 / 4 986 above
  (measured on the committed code). All three agree on shape and disagree on magnitude by up to ~2.5×,
  because the earlier two ran on trees that were being edited under the probe and against fixtures whose
  synthetic document differs by 114 characters. The rows above are the ones to quote; the older pairs
  stay where they are because they are the evidence for claims already committed, and rewriting a
  commit's numbers would make the commit describe a run nobody did.
- **`99 → 6` in the plan is a different probe, not a different truth.** That probe drove three
  `selectionResult` calls *and* three `foldingResult` calls, so `blockRegions` was called 96 + 3 times
  before the fix and 3 + 3 after. The `s` probe above drives only `selectionResult`: 96 → 3. Both
  counts are correct for the probe that printed them, which is the whole reason each row here names its
  probe.
- **These are optimized-build figures.** The server ships interpreted (`s7 -q -l src src/main.sd7`), so
  the shipped cost per call is higher on both sides of every row; the ratios are the part that
  transfers.

One semantic question two reviews declined is settled here rather than assumed: whether
`out &:= all[i]` in `enclosingRegionsFrom` copies a record or shares it. A standalone probe
(`/tmp/alias/a.sd7`, a struct with two integers, append four into a second array, then write a field of
one appended element) reported `src[2].a=2 dst[2].a=999` — copied. So the held region list a request
reuses across positions cannot be corrupted by a future field write inside the filter, which is a
stronger statement than the one the diff supported.

One correction to the reasoning above, bought by the own-first ranking (`5fe718c`). The plan's
Architecture paragraph said the producer-side reorder costs "at zero extra cost"; that sentence is
retracted, and it has been removed from the plan. Every record that survives the dedupe in
`analysis.collectSyms` is now copied TWICE — once into its group array (`ownAdds &:= rec` /
`otherAdds &:= rec`) and once again by the two bulk appends that close the proc in
`src/analysis.sd7` — where one append into `syms` used to do. The copy, not a share, is what the
`/tmp/alias/a.sd7` probe just above establishes. No figure is recorded here, because the only probe
run was an interpreted throwaway with no sentinel and no compiled pair, and the first caveat above
is precisely why such a run cannot be quoted; the structural fact is what stops "zero" being
restated. The two-array shape is kept on purpose: the library group must be buffered either way, and
appending the buffer's own records straight into `syms` would spare only the second copy of one group
while deleting the pair of arrays the mutation proof targets.

Task 1's RED record, which `5fe718c`'s commit body does not carry: against `22ea2fc`'s `collectSyms`
the two ranking checks printed `got: /home/username/seed7/lib/string.s7i` where they expected
`STRING` and `/tmp/seed7_lsp_probe2.s7i` (`analysis: 49 checks, 2 failed`), and Step 9's mutation — the
same single `syms &:= rec` — added `FAIL definition on an own overload of a stdlib name lists the buffer
first` (`transcript: 193 checks, 1 failed`). Reproduce in a scratch worktree with
`git checkout 22ea2fc -- src/analysis.sd7 && make test-analysis`, and restore with
`git checkout HEAD -- src/analysis.sd7` — NOT `git checkout -- src/analysis.sd7`, which reads the index
the staged checkout just wrote and restores the mutant. On this tree that same mutant reddens FIVE checks,
not three: `rankShape`'s group-order pin joined the analysis set at
`got: 0|Widget,length,main,|type,`, and the wire `definition` check dropped out because
`definitionResult`'s own-first pass (Task 2) no longer depends on the order the producer handed it.

The defect the own-records-first rule in `AGENTS.md` exists to prevent, measured on the pre-branch tree.
A buffer declaring `const func integer: length (in Widget: w)` and calling it answered
`textDocument/definition` with 10 locations, the buffer's own `st2.sd7:4` LAST, behind
`string.s7i:336`, `ref_list.s7i:191`, `basearray.s7i:196`, `struct.s7i:37`, `array.s7i:228`,
`file.s7i:195`, `null_file.s7i:274`, `clib_file.s7i:247` and `external_file.s7i:266`; and
`textDocument/semanticTokens/full` marked that own declaration tokenType `function` (legend index 3)
with `defaultLibrary` and no `declaration`, i.e. `{"data":[0,0,6,3,2]}` where the rule makes it
`[0,0,6,5,1]`. Reproduce by driving `s7 -q -l src src/main.sd7` over real frames with that fixture
— `didOpen`, then `definition` at `{"line": 12, "character": 18}` (one past the token; `wordAt` is
left-of-character) and `semanticTokens/full` — or read the same two answers as green pins in
`tests/transcript.py` and `tests/semantic_tokens_test.sd7`.

## R-F10 — the two routes, measured

AGENTS.md's *Do not "fix" these* keeps the rule: an open `.s7i` is analysed through `analysis.sd7`'s
`driverFor(path)`, which reads the file back from disk; `refresh` discloses that with one `Information`
diagnostic per publish; the staleness itself stays open. This is the evidence for the figures in that
bullet, and the way to take them again — the measurement behind the first version of the claim was a
`/tmp` scratch, which made it unciteable.

The heading's wording is now a frozen token in `tools/agents_required.txt`, appended after the R26
replay (`git show d300662:AGENTS.md` matches neither the full heading nor the looser `two routes`, so
none of it was already there). Its limit is the gate's own union rule: the check reddens only when
`AGENTS.md`'s two italic pointers and this heading go **together** — measured, removing all three
prints `MISSING` and one failed check, while deleting this heading alone with the pointers still
naming the old wording prints `0 failed`. A rename on one side of the pair therefore stays green and
leaves two dangling references, the same shape R26 in `tools/agents_gate.sh` exists to catch, so a
rename must move both hosts at once. Do not answer the gap with a second token beside the first: that
would be a guard that cannot fail for exactly the rename it is meant to catch.

    sh tools/rf10_probe.sh                    # $1 overrides the default /home/username/seed7

One Seed7 program, compiled `s7c -O2 -l "$SEED7/lib" -l "$SRC"` (`$SRC` is this repo's `src`, so the
probe reads the working tree's `analysis.sd7`), run over the 214 top-level `lib/*.s7i`
plus `prg/hello.sd7` as a labelled `CONTROL` row outside the aggregate. Per library it prints two rows
of the same analysis: `DRIVER` — the text `driverFor(path)` builds, taken from `analysis.sd7` rather
than retyped, so the probe cannot drift from the server — and `LEAD` —
`$ include "seed7_05.s7i";` then the file's own text, what a buffer would be. Each row carries
`CLEAN`/`NOISY`, `errorCount`, `length(globalObjects(prog))`, the records whose `file(obj)` is
`BUFFER_FILE`, and the first error message. Deliberately not in `make test`: one analyze phase per
route per library.

The committed artifact is `docs/rf10-measurement.md` (434 lines, header
`# seed7 tree: /home/username/seed7 c93282a6`). Its reproducibility claim has two halves measured in
two environments, and they must not be read as one: the original **three consecutive runs byte-identical**
were three runs in this shell's collation, before anything set `LC_ALL=C`. The `LC_ALL=C` export came
later, in the fix wave, because the row order is the shell's collation of the `lib/*.s7i` glob and not
anything the probe decides — `tools/rf10_probe.sh` exports it itself. The artifact was then regenerated
under `C`, and four further runs under `C` are byte-identical; that regeneration moved **44 lines** of
position with no row and no figure changed — verified from the two committed artifacts, where
`git diff --numstat 20a058d 8d00014 -- docs/rf10-measurement.md` reports 44 added and 44 removed and
the sorted files are identical, so it is a pure reorder — `aes.s7i` before `aes_gcm.s7i` being one
moved pair rather than the total. Five named rows
and the aggregate, taken from the artifact (`string=` there counts the records whose `file(obj)` is
`BUFFER_FILE`, and it is 0 for the two `NOISY` libraries — nothing was attributed to the buffer):

| file | `DRIVER` | `LEAD` |
|---|---|---|
| `lib/strifile.s7i` | `CLEAN errors=0 records=3132` | `CLEAN errors=0 records=3132`, 17 records report `STRING` |
| `lib/json.s7i` | `CLEAN errors=0 records=4903` | `CLEAN errors=0 records=4903`, 92 `STRING` |
| `lib/bigint.s7i` | `CLEAN errors=0 records=3472` | `CLEAN errors=0 records=3472`, 66 `STRING` |
| `lib/basearray.s7i` | `CLEAN errors=0 records=3060` | `NOISY errors=2 records=3060`, first `Redeclaration of "array [ (val integer: minIdx) .. ] (val type: baseType)"` |
| `lib/null_file.s7i` | `CLEAN errors=0 records=3060` | `NOISY errors=44 records=3060`, first `Redeclaration of "null_file"` |
| the 214 top-level libraries | — | **184 `CLEAN` / 30 `NOISY`**; records agree for 213 |

    SENTINEL files=214 leadClean=184 leadNoisy=30 recordsSame=213

Two caveats a sentinel cannot carry, both readable in the artifact. 29 of the 30 `NOISY` rows begin
`Redeclaration of …`; the 30th is `lib/multiscr.s7i` (`errors=2 records=4094 string=5 first=Match for
openWindow(SCR, 2, 2, 10, 78) failed`), which is `NOISY` on **both** routes — `SCR` is `var file:` at
`multiscr.s7i:41` while `window.s7i:57` wants `ref text: outText`, so the no-match belongs to the
library and not to the route — and so it is not a route split: the count of libraries whose own text is
not analysable while the driver route is clean is 29. And the record counts agree for 213 of 214: the
one disagreement gets its own row, `RECORDS-DIFF …/lib/seed7_05.s7i driver=3060 lead=3061`.

Two figures were refuted on the way and must not be restated: `recordsSame=178` came from comparing the
two formatted rows at a fixed byte position, so it read "different" whenever the two error counts had
different digit widths; and the first run's `leadNoisy=46` counted 16 rows the probe's own reader had
contaminated — a plain `open(path, "r")` yields one character per byte, and the C1 characters that
produces inside string and char literals are what the analyzer then refused. `readAll` now uses
`openUtf8` and `requireDecoded` fails the run on any character in U+0080..U+009F rather than grading it:
that is where 46 became 30.

**The probe grades the route, not the file list.** Re-measured on this tree by mutating one line
(`led := grade(own, dirs)` — `LEAD` loses the essential include), writing the output outside the repo
and restoring the script from a saved copy:

    SENTINEL files=214 leadClean=1 leadNoisy=213 recordsSame=1
    LEAD /home/username/seed7/lib/strifile.s7i NOISY errors=1731 records=0 string=0 first=Expression expected found const
    CONTROL /home/username/seed7/prg/hello.sd7 CLEAN errors=0 records=3061 string=1 first=

A library is not a whole program: stripped of the include, `LEAD` parses nothing — the `strifile.s7i`
row above answers `records=0`, so nothing is attributed to the buffer — and 213 of the 214 go `NOISY`,
while the program control stays `CLEAN` with its one `STRING` record. Restoring the include returns the
sentinel to `184 / 30 / 213`.

**A scratch path is not an escape.** The tempting fix for the staleness — write the buffer's text to a
temp file and analyse *that* path — was measured with the same probe over two copies placed outside
`lib/`, in a scratch directory, nothing written into the repo. Each gave the `DRIVER` route the same
counts as `LEAD`, and the same first messages as the real paths: `basearray.s7i` **2** errors
(`Redeclaration of "array [ (val integer: minIdx) .. ] (val type: baseType)"`) and `null_file.s7i`
**44** (`Redeclaration of "null_file"`), where the identical `DRIVER` route on the real `lib/` path is
`CLEAN`. The reason is the closure: `seed7_05.s7i` has already read `lib/basearray.s7i`, so a second
path carrying the same declarations is a second declaration set rather than a way around the driver.
The driver route is clean for a library only when the path is the one the closure already read — which
is R-F10 in one sentence, and why the temp-file route, like comparing buffer to disk, buys nothing.

**The disclosure, and what pins it.** `src/lsp_server.sd7`'s `LIB_STALE_MESSAGE` is the whole sentence
the user reads, quoted verbatim in `README.md`'s *What does not work yet*. It is appended after
`mapDiagnostics`, so a document capped at `MAX_DIAGNOSTICS` still sees it; it fires on `uris.sd7`'s
`isLibraryBufferPath` and on no other document, and inside `analysable(uri)`, so an untrusted buffer
still publishes nothing. The record is `SEV_INFORMATION` at `column1 := 0` and
`line1 := doc_store.firstNonEmptyLine(openDocs[uri])`; the publish path lands on the whole first
NON-EMPTY line of the buffer — or on line 1 when the buffer holds no character at all, where no
width exists to anchor on and the range collapses again by necessity, not by oversight — and
`didClose` publishes the empty list that clears it. Line 1 is NOT that
line in any real library: `find ~/seed7/lib -name '*.s7i' -exec sh -c 'head -1 "$1" | wc -c' _ {} \; |
sort -u` prints only `1` — a bare newline — for all 266 of them (215 top level), and an anchor on an
empty line has no width: `charColumnForBytes` returns column 1 without entering its loop, so
`lspRangeBytes` collapses both bounds to 0 and **no `column1` value fixes it**. The shipped
`transcript` library fixture began with a real declaration, so its range pin was truthful about the
fixture and blind to the domain — the defect was measured on `lib/aes.s7i` and five other libraries as
`{"start":{"line":0,"character":0},"end":{"line":0,"character":0}}`, the only diagnostic in the
publish. What pins it now: three `lsp_server` checks grade the decision (a `.s7i` gains exactly one, a
`.sd7` gains nothing, the severity is `Information`), four `doc_store` checks grade the anchor (two
blank leading lines name the third, a line 1 that holds text stays 1, an all-blank buffer falls back to
1, and a CRLF blank prefix is blank too), and eight `transcript` checks pin it on frames — once per
publish, `severity` 3, the whole sentence
(the Seed7 unit suite prints ASCII, so only two words of it are comparable there), that the fixture's
line 1 IS empty (the anchor expectations are DERIVED from the fixture, so its shape is a premise and not
a coincidence, which is why it gets its own check rather than hiding in the range's description), that
the range has non-zero width, that it is the whole first non-empty line, the
`didClose` clear, and that no other document in the run receives it. Not measured: whether a client
drops a `start == end` range or only fails to squiggle it — `start == end` is legal LSP and no client
exists in this environment.

**Why the `-32603` bullet is conditional.** `doc_index.readLinesOf` reads library prose with `openUtf8`
— the plain `open` was the mojibake: `lib/asn1.s7i`'s euro sign in its own `(** … *)` comment reached
hover as three characters — and `readln` on a `utf8File` raises `RANGE_ERROR` at the first byte sequence
that is not valid UTF-8. Re-measured here with no handler, reading `~/seed7/prg/err.sd7` the way
`readLinesOf` does: 88 lines, then `Uncaught exception RANGE_ERROR raised at ut8_rtl.c(771)`. The raiser
is therefore **line 89**, whose bytes are `ED 80 41` — a lead byte whose second continuation is missing,
which is that line's own labelled case (`*UTF-8 continuation byte expected found "A"*`). Re-take the
bytes:

    sed -n '86,89p' ~/seed7/prg/err.sd7 | od -An -tx1

The first group holds `c0 80` (line 86) and the last two hold `ed 80` then `41` (line 89, split across
`od`'s 16-byte rows); `~/seed7/src/striutl.c:850-930` — `utf8_to_stri` — is the decoder that decides
which of the two raises. It is **not** the `C0 80` at line 86, and the 88 clean lines cover lines 87 and
88 (`ED A0 80`, `F4 90 80 80`) too:
this decoder reads the overlong pair as `chr(0)` and does not raise on any of those three. No
library is like that — `iconv -f UTF-8 -t UTF-8` over all 266 `lib/*.s7i` (recursive) fails on none of
them — but one `prg/*.sd7` of 129 does, `err.sd7`, and a client may open anything inside its root. So
without `doc_index.sd7`'s `catch RANGE_ERROR` the hover of a symbol declared in such a file costs the
request a `-32603` (`main.sd7`'s `catch RANGE_ERROR` answers it through
`handlerFailed("range", body, msg)`, which is the observed answer), and the bullet's claim that no
input reaches the net would be false; with it, hover keeps the signature and
loses the prose, which is what an unreadable comment already answers. Two `doc_index` checks reach the
arm and they pin its two halves separately. The twelfth is a scratch file holding one `FF` byte, a lone
UTF-8 start byte, asked at the line the decoder raises on — neutralize the arm and the raise escapes,
the suite prints no graded line, and `make test` cannot pass. The thirteenth asks at a declaration
ABOVE the raising line, in a file whose `(** … *)` is clean UTF-8 with the `FF` below it: `readln`
accumulates the good lines and then raises, so the `lines := 0 times ""` reset inside the arm is what
makes the answer `""` — delete only that reset and the check answers its expected `""` against
`"Documents early."` while the other thirteen stay green. `doc_index`'s fourteenth is the control that
the same four lines are readable prose at all (`proseForText`, in memory, nothing erases them), so the
thirteenth cannot pass on a comment no walk would ever find. That is why AGENTS.md records the net as
reached-but-silent rather than unreachable, and why the next section exists.

## Do not "fix" these — the `-32603` net, reached by `readJson`

The rule is AGENTS.md's `-32603` bullet. Its premise — that no input reaches the net — was measured
wrong here, while the safety it asserts still holds, so both halves are recorded.

**The raiser is `readJson`, not `parseStri`.** `readJson` recurses, and a body nested deep enough
exhausts memory and raises `MEMORY_ERROR`. Probed with no handler, `s7 -q <file>`, where `nest(d)`
is `d` opens, `7`, `d` closes:

    depth  5 000 array -> PARSED        depth 11 000 array -> PARSED
    depth 11 500 array -> MEMORY_ERROR
    depth  7 500 object -> PARSED       depth  8 000 object -> MEMORY_ERROR

The bound is the interpreter running out of memory, so those rows are a property of this machine and
this build, not a language constant — re-measure before quoting them. Objects reach it sooner than
arrays because each level costs `{"a":` as well as `}`. `MAX_FRAME_BYTES` is 67 108 864, so the
30 000-deep array body used below — 60 057 bytes — is an ordinary, in-limits frame: nothing about
the transport refuses it.

**What the server does with it.** `s7 -q -l src src/main.sd7`, each session `initialize(id 1)`, then
the deep body with `"params"` holding `d` nested arrays and `"id":"deep<d>"`, then
`"id":"after"`, then `shutdown(id "s1")`, then `exit`:

    d =     500  1 055 bytes -> -32601 under "deep500",   code 0, junk 0
    d =   5 000 10 056 bytes -> -32601 under "deep5000",  code 0, junk 0
    d =  30 000 60 057 bytes -> NO FRAME for "deep30000", code 0, junk 0

At 30 000 the only trace is `handler failed (memory): {…}` on **stderr**; `"after"` and `"s1"` are
answered normally, so the session survives, and no non-frame byte reaches stdout.

**Why no `-32603` frame appears.** `parseMessage`'s guard wraps its own `readJson` call and names
`RANGE_ERROR`, `INDEX_ERROR`, `ILLEGAL_ACTION` — `MEMORY_ERROR` is not among them, so the raise
escapes to `main.sd7`'s block, whose `catch MEMORY_ERROR` calls `handlerFailed("memory", body, msg)`.
`handlerFailed` sends `-32603` through `sendError`, and `sendError` answers `msg.idJson` — but the
raise happened before any id was read, so `msg.idJson` is what the loop-carried reset left it:
`"null"`, which the guard answers with silence. Silence is the right outcome and it rests on one
line. Deleting `main.sd7`'s `msg := rpcMsg.value;` and re-running the 30 000 session produces

    {"jsonrpc":"2.0","id":1,"error":{"code":-32603,"message":"internal error: memory"}}

— a second response under `initialize`'s id, beside the result already sent: the four frames of
that session become five, and `1` answers twice. That mutation is what proves the comment above the
reset true; nothing in `tests/transcript.py` reaches it, so the proof lives here.

**A raise from the *id* read would behave the same way.** Mutating `idJsonOf`'s number arm back to a
Seed7 integer parse — `out := str(integer(str(idValue)));` — raises `RANGE_ERROR` inside
`parseMessage` but *outside* its guard, so on the server it lands in `catch RANGE_ERROR` and answers
`handler failed (range)` with the same null-id silence; in `tests/rpc_test.sd7` it dies before its
graded line (uncaught at `tests/rpc_test.sd7(36)`, the float-id check, which is the first non-integer
numeric id the suite reads). The caught version of the same mutant — `catch RANGE_ERROR: out := "0"`,
which is what the retired `intAt(root, "id", 0)` did — reddens three `rpc` checks, the new
`an id too wide for integer() echoes its own text` among them, and leaves the other 20 suites green.

## Protocol decisions — the exit code and the id on the wire, measured

The rules are AGENTS.md's `exit` bullet and its `-32700`/`-32002` bullet.

**The spec sentence, quoted.** *exit*: "The server should exit with **success code 0** if the
shutdown request has been received before; **otherwise with error code 1**." Provenance matters here:
that wording reaches us through this branch's LSP 3.18 spec notes (its *exit* section, citing
`L4885`–`L4891` of a plain-text extraction held at `/tmp/lsp318.txt`), and that file is no longer on
disk, so nobody in this tree has re-read it since. The behaviour is pinned by measurement and by two
`transcript` checks, not by the quotation — which is why `AGENTS.md` states the contract it measured
rather than citing a spec file it cannot open. Treat the quote as a pointer to verify against a live
copy before repeating it in new prose.

**Where the code is decided is `lsp_server.sd7`, not `main.sd7`.** The `exit` arm reads
`if gotInitialize and gotShutdown then exit(0); else exit(1); end if;` and `main.sd7`'s gate names
`exit` beside `initialize`, so the notification reaches that arm in every session shape. Measured
with well-framed sessions against `s7 -q -l src src/main.sd7`:

    hover(id "x1"), shutdown(id "s1"), exit        [no initialize]  -> code 1, 2 frames, stderr empty
    initialize, shutdown, exit                                      -> code 0, 3 frames
    initialize, exit                              [no shutdown]     -> code 1, 1 frame
    exit                                            [nothing before]  -> code 1, 0 frames

The first row is the one a client author reads: the two refusals are
`-32002` **carrying the ids that asked** — `"id":"x1"` and `"id":"s1"`, strings intact — with
`junk = 0`. `main.sd7`'s tail is a different ending, for a stream that stops without any `exit`
notification: `exit(0)` for a completed session, `exit(2)` for `framingFatal`, and otherwise no
`exit()` at all, which is **0** — measured, because a Seed7 `main` that merely returns reports 0,
both interpreted (`s7 -q`) and compiled (`s7c -O3`). So the two calls that must never be merged into
one `exit(0)` are `lsp_server.sd7`'s; `main.sd7`'s tail is where the framing-fatal `exit(2)` lives.
Already pinned by harness checks: `tests/transcript.py:168` (`exit` after `shutdown` is 0) and `:175`
and `:1056` (status 1 without it — sessions that have no `initialize` either).

**The tail tests the completed session BEFORE `framingFatal`, and that order is a decision.**
`src/main.sd7:52-56` reads `if gotInitialize and gotShutdown then exit(0); elsif framingFatal then
exit(2); end if;`, so a fatal frame that arrives after an answered `shutdown` ends the session at
**0**, not 2 — which is why every exit-2 promise in AGENTS.md and README carries the qualifier
"unless the session already answered `shutdown`, which earns 0". Measured with three sessions built
by `tests/transcript.py`'s own `frame`/`split_frames`/`run` and run by
`python3 ~/.cache/seed7-lsp-investigation/work/exit_order_recheck.py`, whose `SENTINEL sessions=3`
line is required before any row is read:

    initialize, shutdown, Content-Length: abc, stream closed   exit=0 junk=0  shutdown answered
    initialize, Content-Length: abc, shutdown, stream closed   exit=2 junk=0  shutdown NOT answered
    initialize, shutdown, Content-Length: abc, exit            exit=0 junk=0  (that one is the `exit` arm)

All three log `seed7-lsp: invalid Content-Length 'abc'` on stderr, so the framing line is not what
decides the status. Keep the order: `lsp_server.sd7`'s `exit` arm keys 0 on the same pair, so a tail
that tested `framingFatal` first would make ONE server give two answers to "was `shutdown` received?"
depending on whether the client sent `exit`. No `transcript` check pins the first row — the suite's
four hostile-framing sessions all send their fatal frame before any `shutdown` is answered, which is
why each of them exits 2 — so this paragraph and that probe are its record.

**Number and string ids on the wire.** `"id":99999999999999999999` is answered
`"id":99999999999999999999`, `code 0`, `junk 0` — the same literal that `integer()` refuses with
`RANGE_ERROR` (measured directly, as it refuses `"10.5"` and `"1e3"`), which is why the retired
`intAt(root, "id", 0)` answered id `0` and the text arm answers the client's own digits. An `"id"`
holding a surrogate pair is echoed **as it was sent**, not folded: a body whose id is the escapes
`\ud83d\ude00` answers the 14 ASCII bytes `22 5c 75 64 38 33 64 5c 75 64 65 30 30 22`, and a body
whose id is the raw character answers `22 f0 9f 98 80 22` — the same four UTF-8 bytes it came in.
`strAt` folds a pair to one character; the id path never does, and `tests/rpc_test.sd7`'s
14-against-3 length comparison is the pin (`idJsonOf`'s comment holds both numbers).

## Every change — the two `blockRegions` post-passes, measured (2026-10-31)

`blockRegions` cost two quadratic passes over its own region list after `walkRegions` returned: a
bubble sort by `startLine`, and a clause filter that scanned the list twice per clause region — once
for the enclosing control, once to count clauses in that window. Task 5 replaced them with an
insertion sort and a per-window clause count, memoised. `tools/regions_gate.sh` is the equivalence
check: `s7 -q -l src` over every `lib/*.s7i` and `prg/*.sd7`, one row per file,
`<path>\t<n>\t<start-end[:kind] …>`, the regions taken from `blockRegions` itself.

    sh tools/regions_gate.sh ~/.cache/seed7-lsp-investigation/work/gate/regions-before.txt   # at 311b34e
    # swap src/blocks.sd7 and nothing else, run again:
    sh tools/regions_gate.sh ~/.cache/seed7-lsp-investigation/work/gate/regions-final.txt
    diff ~/.cache/seed7-lsp-investigation/work/gate/regions-{before,final}.txt          # empty

SEED7 INTERPRETER Version 5.4.10, 215 `lib/*.s7i` + 129 `prg/*.sd7`, both sides
`SENTINEL files=344 regions=56492 skips=1`, 345 lines each (344 rows + the sentinel), diff empty. The
gate's own wall time went 41.4 s → 22.6 s. Two facts that run produced, both load-bearing:

- `prg/chkarr.sd7` holds **4 881** regions on this tree, not the 4 847 the plan quotes for
  `5d8b72c`. Task 4 moved the `pending` branch, so a construct keyword after `is <value>` now opens
  its own region; the plan's figure is history, and every before/after claim here is against this
  tree's own baseline. The largest `lib/*.s7i` is `lib/tiff.s7i` at **754**, not the 719 the plan
  quotes for `5d8b72c` (`docs/superpowers/plans/2026-10-31-transport-and-region-fixes.md:374` —
  history, and not re-measured here), and the mean across `lib/*.s7i` is 102 (21 975 regions over
  215 files), not the ~95 the deleted `ponytail:` note called a ceiling — it was always the mean,
  of a 213-file set. Both are read out of the artifact this gate already wrote, not out of a second
  run, in `~/.cache/seed7-lsp-investigation/work/gate/`:
  `awk -F'\t' '$1 ~ /\/lib\// {print $2 "\t" $1}' regions-final.txt | sort -nr | head -1` for the
  754, the same awk with `{n += $2; c++} END {printf "%.1f", n/c}` for the mean.
  `regions-before.txt`, `regions-final.txt` and `regions-round1.txt` there are one md5
  (`c6cabda22a9bcdea3571902dbf0a3b86`), which is the empty diff above restated as a checksum.
- `skips=1` is `prg/err.sd7`, the interpreter's own invalid-encoding test program: the one corpus
  file that is NOT valid UTF-8. `readln` over an `openUtf8` handle raises `RANGE_ERROR` at
  `ut8_rtl.c(771)` ("The file contains an invalid encoding") — a different raiser from the
  `gets(f, -1)` at `ut8_rtl.c(586)` AGENTS.md names. Uncaught, that trace prints to **stdout**, which
  is how the gate's first run appended five error lines to its own artifact; hence the catch and the
  labelled `SKIP:not-valid-utf8` row in `tools/regions_gate.sh`.

**Task 4's output change, gated by classification instead of an empty diff (merge-fix wave,
2026-10-31).** The run above compares two trees that must answer the SAME regions; Task 4 changed the
answers on purpose, so its gate asks a different question — did any fold disappear? The script did
not exist before `007812f`, and it resolves `SRC` from its own directory, so the pre-Task-4 run needs
it copied into that worktree (which is what makes it read the older `src/blocks.sd7`, byte-identical
to `5d8b72c`'s: both md5 `2cf7e55c27d6bfb04ddf5cb8a1f3e7e0`):

    git worktree add ~/.cache/seed7-lsp-investigation/work/wt-c1fc801 c1fc801
    cp tools/regions_gate.sh ~/.cache/seed7-lsp-investigation/work/wt-c1fc801/tools/
    (cd ~/.cache/seed7-lsp-investigation/work/wt-c1fc801 && sh tools/regions_gate.sh <pre>)
    sh tools/regions_gate.sh <head>

The pre-Task-4 run took 45.2 s — the quadratic post-passes Task 5 replaced, and the same shape as
the 41.4 s measured above — against the HEAD run's ~23 s. `SENTINEL files=344 regions=53629 skips=1`
pre-Task-4 against `files=344 regions=56492 skips=1` at HEAD, 345 lines each, so the two artifacts
cover the same corpus. Compared pair by pair with
`~/.cache/seed7-lsp-investigation/work/gate/foldloss.py <pre> <head>`, whose own last line is
`SENTINEL paths=344 changed=269 added=5394 removed=2531 lost=0`: 269 rows changed — 268 of them
gained regions, **none lost any**, and the 269th (`lib/stars.s7i`) changed one pair at an unchanged
count. All 2 531 vanished pairs have a same-start replacement at HEAD whose `end` moved down. That is
the `local`/section window ending at the `begin` Task 4 stopped swallowing instead of running to
`end func` — `lib/aes.s7i`'s 0-based 720-738 became 720-724, with the routine's body now its own
724-738 region beside it — and, for `lib/stars.s7i`, the `is new struct` window ending at its own
`end struct;` (35-40) instead of running to 35-1705. Nothing was lost. The run also closes the two
figures the bullet above calls history: pre-Task-4 `prg/chkarr.sd7` is exactly **4 847** and
`lib/tiff.s7i` exactly **719**, which is what the plan quoted for `5d8b72c`.

The wire sessions are the shapes the finding was measured in: `initialize` (rootUri null) +
`initialized` + `didOpen` of `prg/chkarr.sd7` (1 761 917 characters, 33 147 newlines) + N
`textDocument/foldingRange` + `shutdown` + `exit`, framed over stdin of
`s7 -q -l src src/main.sd7`. Best of two runs per row, one command
(`python3 ~/.cache/seed7-lsp-investigation/work/fold_timing.py <tree> 2`), whose sentinel is the
reply's own `folds=4881 frame_bytes=172338` — identical in every row below and in both trees, so the
sessions measure the same answer at different speeds.

| session shape | `311b34e` | filter fixed, sort still bubble | both fixed |
|---|---|---|---|
| `didOpen` only | 2.90 s | 2.77 s | 2.82 s |
| `didOpen` + 1 `foldingRange` | 17.08 s | 10.83 s | 6.87 s |
| `didOpen` + 3 `foldingRange` | 46.99 s | 27.12 s | 15.18 s |
| per `foldingRange` | 14.2–15.0 s | 8.1 s | 4.1 s |

The middle column is the same tree with only the clause filter replaced — the mutant that separates
the two halves, because the change as committed replaces both at once. The clause count is worth
~6.1–6.8 s of the ~14–15 s a request cost; the insertion sort a further ~4.0 s. What is left is not
quadratic either: a standalone driver calling `walkRegions` three times on the same text measured
4.71 s (1.57 s per pass, the file read costing 0.04 s), and `blockRegions` three times measured
11.92 s (3.97 s per call); stubbing the per-window counts took the call to 1.59 s, so those counts
are ~2.38 s of the remaining ~2.4 s and the sort, split, owner walk and appends share ~0.02 s.
`src/blocks.sd7`'s `ponytail:` note carries that split and its upgrade path.

Absolute seconds move between runs of identical binaries — the caveat at the top of
*Every change — the two hot paths, measured* applies to every row above, which is why each one names
its tree, its shape and its rep count.

## Protocol decisions — the framing outcomes, measured (2026-10-31)

The rules are AGENTS.md's framing bullet and the `getln`/`gets` raise trap beside it. Four wire
sessions, each pinned by the named checks in the last column; `python3 tests/transcript.py`
(`make transcript`, 227 checks) runs them. The reply lists quoted here were taken with
`~/.cache/seed7-lsp-investigation/work/gate/framing_probe.py`, which copies `frame`, `split_frames`
and `run` out of that suite verbatim and sends the same four sessions to `s7 -q -l src src/main.sd7`;
`python3 <that file>` prints one `exit= junk= replies=` line plus the stderr per session.

| input, after a good `initialize` | at `5d8b72c` (the audit — history, not re-taken) | at `3b64d54`, re-measured here | the checks that pin the third column |
|---|---|---|---|
| `Content-Length: 99999999999999999999999`, then `shutdown`, `exit` | `exit 0`, 2 frames, stderr `frame without Content-Length ignored` — 23 digits read as *absent*, so the session ended as though the client had closed it | `exit 2`, `junk 0`, one line `seed7-lsp: invalid Content-Length '99999999999999999999999'`, `shutdown` unanswered | `over-wide Content-Length: clean fatal exit, stdout uncorrupted`; `over-wide Content-Length prints one framing line, not two` |
| a frame body holding one raw `0xFF` | `exit 1`, stdout carrying `Uncaught exception … main.sd7(10)`, i.e. `junk 1` | `exit 2`, `junk 0`, stderr `seed7-lsp: frame body is not valid UTF-8`, and **one `-32700` answered first** (below) | `invalid UTF-8 in a body: exit 2 and only frames on stdout`; `and stderr names the frame body`; and for the `-32700` pair below, `a body whose prefix decoded answers one -32700 before exit 2` |
| a header line holding one raw `0xFF` | `exit 1`, the same trace on stdout (`junk 1`) | `exit 2`, `junk 0`, stderr `seed7-lsp: header line is not valid UTF-8`, nothing answered behind it | `invalid UTF-8 in a header line: exit 2 and only frames on stdout`; `and stderr names the header line`; and for a raise that lands *after* a parsed length, `invalid UTF-8 on a continuation header line: exit 2 and only frames on stdout` with `and the body behind a fatal header line is never answered` |
| a `Content-Type`-only header block, then `shutdown`, `exit` | `shutdown` never answered — 2 frames, ids `[1, null]` | `exit 0`, `junk 0`, stderr `seed7-lsp: frame without Content-Length ignored`, `shutdown` answered (`{"jsonrpc":"2.0","id":13,"result":null}`) | `frame lacking Content-Length is reported`; `the frame after a length-less header block is still answered`; `a length-less block does not end the session` |

The second column is the audit's measurement at `5d8b72c`, quoted from rows 1-4 of the Findings table
in `docs/superpowers/plans/2026-10-31-transport-and-region-fixes.md`. It is history and was not
re-taken: the fixes are in the tree, so that behaviour is no longer reachable from it. Rows 5-8 of
the same table (the three region fixtures and the folding cost) are answered by *Every change — the
two `blockRegions` post-passes, measured* above, which carries this tree's own counts — 4 881 for
`prg/chkarr.sd7`, not the table's 4 847.

**One `-32700`, then exit 2 — disclosed, not hidden, and only when a prefix decoded.** A fatal byte
in a *body* is found by `readFrameBody`'s own `gets` guard, which sets `chunk := ""`; that is the
loop's EOF-in-frame path, whose rule is "what arrived goes back to the caller". When at least one byte
decoded before the fatal one, the body that comes back is non-empty, `readMessage`'s
`okay := length(body) <> 0` is TRUE, `main.sd7` parses it, fails, and answers

    {"jsonrpc":"2.0","id":null,"error":{"code":-32700,"message":"Parse error: body is not JSON"}}

before `framingFatal` ends the session at 2. When the fatal byte is the body's FIRST byte — any
client can send `Content-Length: 4` and four `0xFF` — nothing decoded, `body` is `""`, `readMessage`
returns FALSE and there is no `-32700` at all: the stderr line, exit 2, and nothing answered behind
`initialize`. Both shapes were first measured with
`~/.cache/seed7-lsp-investigation/work/task6r1/body_shapes.py`, whose sessions are built by
`tests/transcript.py`'s own `frame`/`split_frames`/`run` and whose `SENTINEL shapes=2` line is
required before any count here is read: prefix decodes → `exit=2 junk=0`, answered
`[(1, None), (None, -32700)]`, one `-32700` frame; first byte fatal → `exit=2 junk=0`, answered
`[(1, None)]`, `-32700 frames=0`. Ruled acceptable: a body that arrived and does not parse *is* a
Parse error, and the id is null because no id was ever read. From outside the first shape looks like
a server that answers and then dies, which is why it is written down. Both halves are pinned in-tree
now, so that probe is no longer their only record: `tests/transcript.py`'s
`a body whose prefix decoded answers one -32700 before exit 2` grades the first on the `BAD_BODY`
session that already asserted the exit code, `junk` and the stderr string, and
`a body whose FIRST byte is fatal answers no -32700 at all` grades the second on a
`Content-Length: 4` + four `0xFF` session of its own. Both were added to code that already worked, so
each was proven by mutating the catch that produces it: assigning a NON-EMPTY `chunk` there reddens
only the first-byte check, and discarding what already decoded (`body := "";` in the same catch)
reddens only the prefix check — `transcript: 226 checks, 1 failed` each way, with
`src/transport.sd7` restored to its recorded sha256 after each. DELETING the `chunk := "";` reddens
nothing (227 checks, 0 failed): `chunk` is already `""` on the pass that raises when the fatal byte
is the body's first, and on a later pass `noteBadUtf8` has already set `framingFatal`, so the loop
ends either way and the mutant's only difference is the previous chunk appended twice to a body that
does not parse regardless. Same shape as the equivalent mutant in *Which clause is proven* below,
which is why the inverted assignment is the proof here and the deletion is not.

**"Refuses" names the reader's set, not every invalid sequence.** Measured at `ut8_rtl.c(771)` and
recorded in-tree at `src/doc_index.sd7:29-31`: a lone `FF`, the pair `FF FE`, `C3 28` and a lone `80`
raise `RANGE_ERROR`; the **overlong** pair `C0 80` does not — it decodes to `chr(0)` and is served
normally. So the honest phrasing of the rule is "the byte sequences the reader refuses", never "any
invalid UTF-8": a client can still put a `NUL` in a frame and get an answer.

**Do not build a standalone decode probe.** Two attempts at a program calling `gets`/`readln` on an
`openUtf8` handle over invalid UTF-8 hung this host and cost two tool results; the disabled probe is
at `~/.cache/seed7-lsp-investigation/work/DO-NOT-RUN-raise.sd7.freezes-os` and must stay unexecuted.
The wire suite is the replacement: it runs the real server under `communicate(timeout=90)`, so a hang
costs a timeout instead of a session.

**One framing line per fatal frame is the branch order, not the messages.** At `676ff57` a fatal
`Content-Length` printed `headerNumber`'s line *and* `frame without Content-Length ignored`, because
both states arrive as `contentLength = 0`. `a1753f1` put `if framingFatal then … elsif contentLength
= 0 then …` in front of the length-less arm, and the four `… prints one framing line, not two` checks
(one per hostile label) are what hold it there.

**Which clause is proven, and which is not any more.** Three `and not framingFatal` clauses sit on the
read path and they do not have the same status — one of them changed status on this branch. The clause
in `readFrameBody`'s loop (`src/transport.sd7:108`) WAS load-bearing, at `676ff57`: deleting it there
reddens exactly `and the body behind a fatal header line is never answered ([1, None])`, and the
suite's own line goes `transcript: 219 checks, 0 failed` → `218 checks, 1 failed`. Re-measured here
rather than inherited, by `git archive 676ff57 src tests | tar -x -C <dir>` and running that tree's
own `tests/transcript.py` against the mutated copy. At `aeefb98` the identical deletion reddens
nothing: `make transcript` prints `225 checks, 0 failed`. `a1753f1` turned it into an equivalent
mutant, and no black-box input can separate the two versions, because `readFrameBody`'s only call
site in `src/` (`:183`; the repo's other is `tests/transport_test.sd7:23`, a unit call on a plain
`open()` handle that never reaches `framingFatal`) now sits in the `else` of `if framingFatal then`
(`:174`), so the function is never entered with the flag set — and inside its loop the only setter is
`noteBadUtf8` in the catch, which also assigns `chunk := ""` → `remaining := 0` and ends the loop
anyway. The clause stays as the invariant its two
neighbours state, not as a guard anything can reach: an agent asked to reproduce the `676ff57` proof
at HEAD cannot, and per *Every change* would have to invent a synthetic trigger, which is why the
history is written down here instead of left as a claim to re-test.

The clause in the header loop (`:168`) is unreached by any fixture for a plainer reason: `getlnSafe`
returns an empty line on a raise, so `line <> ""` ends that loop first — `8d9e630` measured both
clauses together (removing either left 217 checks green and nothing hanging) and `676ff57` separated
them. The clause in `readMessage`'s outer loop (`:163`) reddens nothing and hangs nothing either
(measured at `a1753f1` and again at `8a6ef16`: 225 checks, 0 failed, no session reaching the
harness's 90 s timeout); what its absence does is drain the rest of the stream line by line to EOF,
answering nothing, so it states the policy "once fatal, stop reading" rather than guarding a spin.
The per-pass `contentLength := 0;` reset is required by
the loop — the variable is a local, so a length parsed for an earlier frame would read the next
frame's body with the wrong byte count — but it could not be proven by mutation: no wire input in the
suite reaches a second pass after a pass that parsed a length, because that needs an empty body with
`hasNext` still TRUE, and both EOF and a fatal read end the loop first.

## Seed7 traps — the exit code, re-measured (2026-10-31)

AGENTS.md's bullet said "`s7` reports analysis errors on stderr **and exits 0**". Against this
interpreter that was wrong, and wrong in the direction that makes a silent run look clean. Upstream
`da2feb38` ("Errors trigger an exit code of 1", 2026-09-25) is in the local checkout —
`git -C ~/seed7 log --oneline -1 da2feb38` prints it — and analysis errors now exit 1.

Probes: `sh ~/.cache/seed7-lsp-investigation/work/exitcode/run.sh`, which runs each of the twelve
shapes beside it — ten files as `s7 -q <file>`, two as bare invocations — prints `exit=` and
`stdout_bytes=` per shape, and ends with a `SENTINEL shapes=12` line that must be present before any
row below counts as a result. The byte count is stdout alone, stderr discarded, because the split *is*
the finding. `goodmain.sd7` is the positive control: a program that runs proves the probe can tell
exit 0 with its own output from exit 0 with a complaint. SEED7 INTERPRETER Version 5.4.10:

| probe | what it provokes | exit | bytes on stdout |
|---|---|---|---|
| `goodmain.sd7` | a `main` that declares and runs (`writeln(1)`) | **0** | **1** (its own `1`) |
| `raise.sd7` | an uncaught `raise RANGE_ERROR` | 1 | 200 (the trace; the path is part of it) |
| `truncated.sd7` | `"end" expected found "END OF FILE"` | 1 | 0 |
| `nosemi.sd7` | `";" expected found "END OF FILE"` | 1 | 0 |
| `comment.sd7` | `Unclosed comment` — an unterminated `(*` | 1 | 0 |
| `nomatch.sd7` | a `main` whose body matches nothing: `Match for nonsenseFn(n) failed` + `Declaration of "main" failed` | 1 | 0 |
| `badinclude.sd7` | `Include file "no_such_module.s7i" not found` | 1 | 0 |
| `dupmain.sd7` | `Redeclaration of "main"` + `Previous declaration of "main"` | 1 | 0 |
| `nomain.sd7` | declares no `main` at all: `*** Declaration for main missing` | **0** | **32** |
| `parammain.sd7` | a `main` with a parameter, which is not recognised as `main`: the same message | **0** | **32** |
| `s7 -q` with no sourcefile | `*** Sourcefile missing` | **0** | **22** |
| `s7 -q /nonexistent.sd7` | `*** File "/nonexistent.sd7" not found` | 1 | 37 |

The three exit-0 `***` shapes all print on **stdout**, and the reason they exit 0 is in the C: the
`printf` sits inside `if (!option.analyzeOnly && currentProg != NULL && (currentProg->error_count == 0
|| option.executeAlways))` — `~/seed7/src/s7.c:459-460`, with the message at `:467`, which
`grep -n "Declaration for main missing" ~/seed7/src/s7.c` finds — while `:485-486` is
`else if (currentProg == NULL || currentProg->error_count != 0) { returnCode = 1; }`. So
`*** Declaration for main missing` belongs to a program that analysed CLEAN and holds no `main` the
interpreter recognises — no `main` at all, or a parameterised one — and *not* to a `main` whose
declaration failed, which is the exit-1 row with 0 bytes on stdout. That collision with the repo's
own vocabulary is the point: AGENTS.md's `writeln` bullet has said for a long time that an argument
list failing to match inside `main` reports `Declaration of main failed`, and the first draft of this
rule (commit `775cde1`) called that shape the exit-0 one. Two more shapes write to
stdout and were never in dispute: an uncaught exception (the trace `uncaught_exception()` prints at
`:474`, with `returnCode = 1` at `:473`) and a command-line file that
does not exist (exit 1). What the old bullet got wrong is the analysis-error class: a syntax error,
a `NO_MATCH`, a redeclaration, an unclosed comment and a missing include all exit 1 with nothing on
stdout — a missing `include` complains on stderr, while a missing *command-line* file complains on
stdout — so "never judge a run by its status code" survives while "exits 0" does not.

Two consequences, both already true of the tree and now stated rather than assumed:

- `Makefile`'s `test-%` grading is unchanged and still load-bearing. A suite that fails to analyse
  still fails its recipe, and the mechanism is the grep, not `s7`'s status: the recipe merges
  `2>&1` into `out`, prints it, and the shell's exit status is the final `grep -q` on the total line
  — measured with a `tests/broken_test.sd7` holding that `NO_MATCH`, which printed the error text and
  exited 1. The exit-0 rows above are why the grep must stay: a suite that declares no `main` the
  interpreter recognises prints `*** Declaration for main missing` on stdout, exits 0, and has no
  total line either, so a recipe grading `s7`'s status would pass it unread — as it would the
  `*** Sourcefile missing` shape, 22 bytes on stdout and exit 0. Only the comment at `Makefile:13`
  was corrected here (it repeated "still exits 0"); the grading logic was not touched.
- `tools/keyword_gate.sh:62` already said 1 — "`|| true`: s7 exits 1 for an analysis error, and
  `set -e` would abort on the first refusal" — and was the only in-tree statement matching this
  interpreter. AGENTS.md and this file were the outliers, and `tools/regions_gate.sh`'s sentinel
  comment now names the same measurement for its two failure paths.

The shape to keep: an exit code without a stdout byte count is half a measurement. `1` with 0 bytes
is an analysis error, `0` with a `***` line on stdout is a run that never EXECUTED anything — a clean
program with no `main` the interpreter recognises, or no sourcefile at all (`s7.c:455`) — and `1` with
a trace on stdout is an uncaught exception.
Only the third is a defect in the server, and only the second can pass a recipe that grades the
status code.
