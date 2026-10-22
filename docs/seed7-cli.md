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
| `corpus_scan.sh`'s file set | 342 (213 `lib/*.s7i` + 129 `prg/*.sd7`, unchanged) | `ls lib/*.s7i prg/*.sd7 \| wc -l` |
| suite totals | 21 suites, 1040 checks: `scan` 66, `features` 186, `lsp_server` 79, `transcript` 192 | `make test` |

Two measurement traps found while taking these, both of which produce a confidently wrong number:

- **A case-limited character class silently undercounts the keyword set.** `"[a-z_0-9]+"` finds
  62 entries in `src/keywords.sd7`, not 63, because one word is `fixLen`. The array is correct;
  the regex was wrong. Count mixed-case words with `[A-Za-z_0-9]+` or verify against
  `sh tools/keyword_gate.sh`, which re-derives the set from the interpreter itself.
- **`find` recurses where the tool's glob does not.** `find ~/seed7/lib ~/seed7/prg -name '*.s7i'
  -o -name '*.sd7'` reports 394 files, because `lib` holds 264 `.s7i` counting its
  subdirectories, while `tools/corpus_scan.sh` passes `"$SEED7"/lib/*.s7i "$SEED7"/prg/*.sd7`
  and so sees 342. A drift claim against that number was an artifact of the measuring command,
  not of the checkout; re-derive a file count with the same glob the tool uses.

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
