# M5 — Occurrence Index, References and File-Local Rename: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the server an occurrence index over one document's tokens and answer `textDocument/references`, `textDocument/prepareRename` and `textDocument/rename` from it, with rename confined to the buffer that declares the symbol.

**Architecture:** One new machine, `src/occurrences.sd7`, streams `scan.sd7` tokens over `doc.text` and resolves a name to a *binding* — a local/parameter/result of the enclosing routine, a declaration in this buffer, a library symbol, or nothing. `src/blocks.sd7` supplies the routine region a local lives in, `src/analysis.sd7` supplies the names in that scope (the analyzer's `formalParams`/`localConsts`/`localVars`/`resultVar`, which only a `BLOCKOBJECT` accepts), and `src/doc_store.sd7` gains the one position converter that takes a UTF-16 column directly. Feature modules return a record carrying both the JSON and an "unresolved" flag; only the dispatcher sends notifications.

**Tech Stack:** Seed7 (`s7` 5.4.10) only; LSP 3.18 over stdio; Python 3 for the transcript harness. No new dependencies, none available to add.

**Spec:** `docs/superpowers/specs/2026-10-12-seed7-lsp-m5-references-and-rename-design.md` — read it before Task 1. It carries the eleven measurements that justify every shape here, and the §12 decisions this plan must not quietly revisit. Work happens in the worktree `.worktrees/m5-references-and-rename` on branch `m5-references-and-rename`.

## Global Constraints

Applies to every task. Values are copied from the spec and the repo's own rules.

* Seed7 only, one process. Nothing in `src/` may be replaced by a shell-out or a second language.
* **Red first.** Write the check, run it, see it fail for the reason you named, then implement. `make test` before and after every task. Proving an assertion can fail means mutating one production branch after committing, then reverting per file — `git checkout -- .` restores from the index and will undo uncommitted work.
* Only `src/analysis.sd7` imports `progs.s7i`. `grep -rn 'progs.s7i' src/` must show one line at the end of every task.
* Only `src/doc_store.sd7` converts LSP positions to string offsets; only `src/utf8bytes.sd7` declares code-point widths; only `src/transport.sd7` emits an outbound byte count. `doc_store` may consume a byte-valued column only to make it a character column.
* Only `src/*.sd7` and `src/features/*.sd7` build LSP response shapes. `occurrences.sd7` returns Seed7-shaped data and knows nothing about LSP.
* Capabilities stay static in `InitializeResult`, and a capability is advertised only once its method is answered. No dynamic registration.
* Every outbound byte goes through `jsonw.sd7`. `grep -rn 'addStr(w, str(' --include='*.sd7' src/` stays empty. Never `str()` on a `jsonValue`.
* Never let an exception reach stdout — it corrupts the protocol channel. Every new accessor that can raise is wrapped the way `paramsOf` is (`src/analysis.sd7:100-117`) and answers the empty value.
* A suite that fails to analyse prints nothing and exits 0. Grade the `N checks, M failed` line; `make test-<module>` already does.
* Seed7 traps this plan's code is written around: a body opened `is func` closes `end func` — `end proc` does not exist; a loop bound is `range a to b`, not `range a .. b`; declare before use, so a helper sits above the function that calls it; `key`, `len`, `line`, `sum`, `pos`, `at`, `idx`, `count` are taken or shadow-prone names — a test here may still call a Seed7 fixture's local `count`, which is legal in the fixture and not in the server; `in`/`not in` work for hashes and sets but never for arrays; a `func` with a `result` clause assigns its result and never `return`s it; strings are `"...\"..."`, a tab inside one is `\9;`, a backslash char literal does not parse (`chr(92)`, named `BACKSLASH` in `doc_store`); an array literal is `[]("a", "b")`; split long `and`/`or` chains of comparisons into small `const func boolean:` one-liners or they fail to *match*; and `writeln` of a string holding a non-ASCII character raises `RANGE_ERROR` on the plain stdout a test suite uses, which is why every check below asserts on integers, lengths and bracket counts, never on printed text containing an astral character.
* `s7` reports analysis errors on stderr **and exits 0**; never judge a run by its status code.
* `make test` at HEAD stays green. The baseline is a moving total, not the plan's number: **350 unit + 83 wire = 433** when this plan was written, **360 unit + 83 wire = 443** after Task 1 (its suite went from the brief's 8 checks to 10, because ruling R16 added the number-token proof). What must not change is that no pre-existing check goes red except where a task says it intentionally re-pins one.

## Review Focus

The failure modes the spec implies that no single task's happy-path test would catch, most likely to bite first. Each line gets its test in the task that owns the code.

1. **A rename requested while the buffer is truncated** — the normal state mid-typing — must refuse (`null`), not rewrite every same-named token. Expected of a good server: the editor says "cannot rename"; the text is untouched. (Tasks 6, 9.)
2. **A local that shadows a global of the same name** must keep the global's references and its rename out of the local's region, including the local's own declaration line. Expected: renaming the global leaves the local alone. (Task 6.)
3. **An astral character earlier on the same edited line** must not move the column: `x := "😀😀"; count := 1;` names `count` at UTF-16 column 13, and the mask would say 11. Expected: the edit lands on `count`, not on `:=`. (Tasks 1, 4, 9.)
4. **A struct field access `w.pix`** has no declaration source at all, so it must answer over-inclusive with a log line, never an empty list that reads as "unused". Expected: the other structs' `pix` tokens appear too, and the log says why. (Tasks 6, 7.)
5. **A client that did not declare `workspace.applyEdit`** must get `null` from `prepareRename`, not a `WorkspaceEdit` it will silently drop. Expected: rename is greyed out, everything else keeps working. (Task 8.)

## File Structure

* `src/occurrences.sd7` — **new.** `occurrence`/`binding` records, `occurrencesOf`, `resolveBinding`. Includes `scan.sd7`, `analysis.sd7`, `blocks.sd7`. No `progs.s7i`, no `jsonw.sd7`, no LSP shapes.
* `src/analysis.sd7` — grows `scopeRec`, `localsOf`, and `symRec.locals`, filled for buffer declarations only.
* `src/blocks.sd7` — grows `blockRef.closer` (a new field; the stripped `kind` values `comment`/`imports`/`clause` stay exactly as `foldingRange` sees them), `enclosingDeclarations`, and `declarationRegion`.
* `src/doc_store.sd7` — grows `lspRangeUnits (line0, col16, width16)`, the only position converter that takes a UTF-16 column as given.
* `src/keywords.sd7` — **new.** the keyword/operator predicate every gate shares, replacing `completion.sd7`'s private 36-entry list.
* `src/features/references.sd7`, `src/features/rename.sd7` — **new.** `refsAnswer` / `renameAnswer` records: JSON plus the unresolved flag.
* `src/lsp_server.sd7` — reads `workspace.applyEdit` for the first time, dispatches the three methods, sends the `window/logMessage` a feature flagged.
`src/features/selection_range.sd7` — TWO calls changed to `lspRangeUnits`: the token branch and the no-token branch (the shipped UTF-16 defect, spec §11.8, R25). The document-range calls just below them keep `lspRange`, because their integer is a character count (R26).
* `tests/occurrences_test.sd7` — **new suite**, added to `Makefile`'s `TESTS`; `tests/analysis_test.sd7`, `tests/blocks_test.sd7`, `tests/doc_store_test.sd7`, `tests/features_test.sd7`, `tests/transcript.py` — extended.

---

## Task 1: `src/occurrences.sd7` — the token pass, and a suite to hold it

The index is a stream, not a table: M4 decided "stream; cache only the mask", and a pass over one document is the whole cost of one request. It reads `doc.text` and skips `hiddenKind` tokens, which gives the mask's behaviour with the mask's column error removed (spec §3, §11.6).

**Files:**
- Create: `src/occurrences.sd7`
- Create: `tests/occurrences_test.sd7`
- Modify: `Makefile` (`TESTS := … occurrences` — insert after `scan`; the grading name class `[a-z0-9_]+` admits it unchanged)

**Interfaces:**
- Consumes: `nextToken`, `skipWhitespace`, `scanCursor`, `tok`, `hiddenKind`, `TK_NAME`, `TK_OP` from `scan.sd7`.
- Produces: `occurrence` record `{integer line0, integer col16, integer width16, integer kind}`; `MAX_OCCURRENCES is 2000`; `occurrencesOf (in string: text, in string: name) → array occurrence`, in document order, `kind` always `TK_NAME` or `TK_OP`.

- [ ] **Step 1: Write the failing checks** in `tests/occurrences_test.sd7`. `first`/`n` helpers keep every assertion ASCII:

```seed7
$ include "seed7_05.s7i";
  include "lsp_tst.sd7";
  include "occurrences.sd7";

# "line0:col16:width16" of the i'th occurrence, or "none".
const func string: at (in array occurrence: oc, in integer: i) is func
  result
    var string: out is "none";
  begin
    if i >= 1 and i <= length(oc) then
      out := str(oc[i].line0) & ":" & str(oc[i].col16) & ":" & str(oc[i].width16);
    end if;
  end func;

const proc: main is func
  local
    var array occurrence: oc is 0 times occurrence.value;
  begin
    oc := occurrencesOf("count := 1;\nwriteln(count);\n", "count");
    check("two occurrences of count", str(length(oc)), "2");
    check("first is the declaration", at(oc, 1), "0:0:5");
    check("second is the use inside the call", at(oc, 2), "1:8:5");
    report("occurrences");
  end func;
```

- [ ] **Step 2: Run, and name the failure.** `make test-occurrences`. Expected: the recipe prints nothing gradeable and the run reports `Match for … failed` on stderr for `occurrencesOf` — the module does not exist. That, not an exit code, is the red.

- [ ] **Step 3: Write `src/occurrences.sd7`** — the header includes, the record, the cap, and `occurrencesOf` as one `skipWhitespace`/`nextToken` loop copied in shape from `src/features/semantic_tokens.sd7:87-116` (the duplicated loop is `scan.sd7`'s documented design, not a defect). Keep a token when `kind <> TK_BRACKET`, `kind <> TK_NUMBER`, `kind <> TK_STRING`, `kind <> TK_CHAR`, `kind <> TK_COMMENT`, `kind <> TK_LINE_COMMENT`, `kind <> TK_ILLEGAL`, and `not hiddenKind(kind)`, and when `text[tk.start .. tk.stop] = name`. Stop appending at `MAX_OCCURRENCES` but keep scanning only until the count is known — the truncation flag is Task 6's `binding`, this task returns the array plus sets nothing else.

- [ ] **Step 4: Extend the same file's checks** for the four rules this module owns, each measured first with `s7` on the snippet:

```seed7
    # an occurrence inside a comment or string is impossible, not filtered by luck
    oc := occurrencesOf("writeln(count); # count\n", "count");
    check("a name in a line comment does not count", str(length(oc)), "1");
    oc := occurrencesOf("writeln(\"count\");\n", "count");
    check("a name inside a string does not count", str(length(oc)), "0");
    # measured: two astral characters inside a masked literal cost two UTF-16 units,
    # so the mask would answer 11 and doc.text answers 13. Review Focus 3.
    oc := occurrencesOf("x := \"\128512;\128512;\"; count := 1;\n", "count");
    check("the column counts the astral characters in the literal before it",
          at(oc, 1), "0:13:5");
    # an operator run is indexable, so rename can reach a user-declared operator name
    oc := occurrencesOf("a := b <+ c;\nd := b <+ c;\n", "<+");
    check("an operator token is an occurrence", str(length(oc)), "2");
    oc := occurrencesOf("abracadabra", "count");
    check("a name that is a fragment of a longer name is not an occurrence",
          str(length(oc)), "0");
```

- [ ] **Step 5: Run to green.** `make test-occurrences`; expected graded line `occurrences: 8 checks, 0 failed`. Then `make test` and confirm no other suite moved.

- [ ] **Step 6: Prove the assertions can fail.** Mutate `occurrencesOf` once per branch and require the named check to go FAIL: keep `hiddenKind` tokens (both hidden checks must go red), compare with `pos(name) <> 0` instead of equality (the fragment check must go red), and drop the astral fixture by feeding `codeText` (the 13 check must read 11). Revert per file.

- [ ] **Step 7: Commit.**

```bash
git add src/occurrences.sd7 tests/occurrences_test.sd7 Makefile
git commit -m "the occurrence pass over the real text, so a column stops lying"
```

## Task 2: `src/analysis.sd7` — the names inside a routine's scope

`BLOCKOBJECT` is the category the scope accessors require and it is exactly what a global `const proc`/`const func` reports (spec §11.1, §11.2). Scope is a record and not a name list, because a local's own declaration line is what `includeDeclaration` will need (spec §4).

**Files:**
- Modify: `src/analysis.sd7` (add `scopeRec`, `localsOf` above `collectSyms`; grow `symRec`; give `collectSyms` and `analyzeAll` a `docPath` parameter)
- Modify: `src/lsp_server.sd7` (the two `analyzeAll` call sites pass `pathOf(uri)`)
- Modify: `tests/analysis_test.sd7` (`symsOf(text, libraryDirs)` at `tests/analysis_test.sd7:125` grows the `docPath` parameter, and every existing call to it is updated in the same commit — its checks must not change value)

**Interfaces:**
- Consumes: `progs.s7i` — `category`, `file`, `line`, `str`, `formalParams`, `localConsts`, `localVars`, `resultVar`.
- Produces: `scopeRec {string name, integer line1, string cat}`; `symRec` gains `array scopeRec: locals`; `localsOf (in reference: obj) → array scopeRec`, total (empty on any raise); `isParam` unchanged; `paramText` reused for the name.

- [ ] **Step 1: Write the failing checks** in `tests/analysis_test.sd7`. The fixture must contain a routine whose local shadows a global:

```seed7
    # fixture "count" shadows a global "count"; the result var and a const local are separate
    syms := symbolsOf("$ include \"seed7_05.s7i\";\n" &
        "const proc: main is func\n" &
        "  local\n" &
        "    var integer: count is 0;\n" &
        "  begin\n" &
        "    writeln(count);\n" &
        "  end func;\n");
    check("one buffer declaration is listed", str(length(syms)), "1");
    check("its own name is not in its locals", str(length(syms[1].locals)), "1");
    check("the local var carries its name", syms[1].locals[1].name, "count");
    check("the local var carries its declaration line",
          str(syms[1].locals[1].line1), "4");
    check("the local var carries its category", syms[1].locals[1].cat, "LOCALVOBJECT");
```

Add the two cases the accessors can raise on: `localsOf` for a `TYPEOBJECT` answers empty, and a routine with a `result` variable lists it with `cat = "RESULTOBJECT"`.

**Corrected by ruling R17 after this task was reviewed:** a `const local` does NOT report
`LOCALVOBJECT`. Measured twice on `s7` 5.4.10, `localConsts` reports the *value* category —
`ci=INTOBJECT`, `cs=STRIOBJECT`, `cset=SETOBJECT` — while `localVars` reports `LOCALVOBJECT`. So
`scopeRec.cat` stores `str(category(obj))` verbatim, with no mapping and no invented category
(Task 6 may need to tell `REFPARAMOBJECT` from `VALUEPARAMOBJECT`), and the `localConsts` READ is
proved instead by a total-length check over consts + vars + result + params. `resultVar` on a
`proc` answers ` *NULL_OBJECT* ` and is skipped; the trailing `SYMBOLOBJECT` in `formalParams` is
already excluded by the existing `isParam`.

- [ ] **Step 2: Run, and name the failure.** `make test-analysis`. Expected: FAILs of the shape `0` where `1` was asked, because `symRec` has no `locals` field yet — if the suite fails to analyse instead, the field is misspelled, which is the same red with a different cause.

- [ ] **Step 3: Implement `scopeRec` and `localsOf`.** Order inside the record: parameters first, then `localConsts`, then `localVars`, then `resultVar` — the plan's later subtraction does not depend on the order, but a check on `length(locals)` reads best against that grouping. Skip a `resultVar` whose `str(r)` is `" *NULL_OBJECT* "` or empty (measured on `main`, which has none). Guard the whole body in one `block … exception catch RANGE_ERROR: catch INDEX_ERROR: catch ILLEGAL_ACTION: end block;` returning the empty array, exactly as `paramsOf` does.

- [ ] **Step 4: Fill `locals` only for buffer declarations.** In `collectSyms`, call `localsOf(obj)` only when `rec.file = BUFFER_FILE or rec.file = docPath` — thread the document path in as a new parameter of `collectSyms` and `analyzeAll`, from `lsp_server`'s `pathOf(uri)` (`pathOf` already decodes the `file://` spelling the analyzer reports, so the guard compares identical strings). A library local can shadow nothing visible in this file, so filling it is pure cost.

**Corrected by ruling R21, a Critical found in review of the first attempt:** `rec` is one `symRec`
variable carried across the loop, so the guard alone is not the "only" — on the non-buffer path
`rec.locals` must be reset (`else rec.locals := 0 times scopeRec.value;`), or a library record
following a filled buffer record is appended carrying that routine's scope. Reproduced: a buffer
whose `const proc: bufferShow` (one local) is declared *before* `$ include "c1lib.s7i"` yields
`LEAK lateShow file=c1lib.s7i locals=1` with `DIAGS=0`. Order matters — an include before the
declarations leaks nothing, and so does a library `seed7_05.s7i` already loaded. The suite must
assert the aggregate invariant (no record outside `BUFFER_FILE`/`docPath` carries locals) rather
than pinning one named record, because a named record's category or position can make it pass for
the wrong reason — which is exactly what happened to the first proof of this guard.

- [ ] **Step 5: Measure the cost of the guard, and write the number down.** `analyzeAll` on `lib/shiftjis.s7i` and on `prg/calc7.sd7`, before and after, timed with `time(NOW)` and `toMicroSeconds` (corrected after review: there is no `cpuTime` in the standard library; `time(NOW)` is at `time.s7i:1098`). *No in-suite timing check exists or should be written* — a wall-clock assertion in a suite is flaky and proves nothing about the guard; the numbers belong in the task report:

```bash
s7 -q -l src tests/analysis_test.sd7
```

Expected: the buffered-only guard keeps the per-analysis increase under the noise of one `parseStri` (20–45 ms today). If it does not, stop and change `locals` to a lazy second call made by `references`/`rename` only, then re-run Task 2 Step 1 with `analyzeAll` unchanged — the spec §4 promises this fork rather than hoping.

- [ ] **Step 6: Run to green, prove the mutation, commit.** Deleting the `resultVar` append must fail its named check; so must deleting the buffer-only guard, proved by the aggregate check of R21 — not by a `TYPEOBJECT`-empty check, which passes whether or not the guard holds (ruling R18: with the guard deleted `localsOf` is simply never called on that record). The `TYPEOBJECT`-empty check is still worth keeping, with honest evidence: deleting `localsOf`'s own `RANGE_ERROR` catch makes `analyzeAll`'s outer net empty the whole symbol list, so the graded `N checks, M failed` line never prints — which the Makefile recipe grades as failure.

```bash
git add src/analysis.sd7 tests/analysis_test.sd7
git commit -m "scope records: the analyzer's own params, locals and result vars"
```

## Task 3: `src/blocks.sd7` — which region is a routine, and where does it end

`blockRef.kind` is stripped to `""` for routine bodies and sections, so "the region of a declaration" does not exist yet, and reflection reports a multi-line header at its **name** line while the region starts at `is func` (spec §4, §11.9). The stripping stays: three shipped response values depend on it.

**Files:**
- Modify: `src/blocks.sd7` (new `closer` field, new `enclosingDeclarations`, new `declarationRegion`)
- Modify: `tests/blocks_test.sd7`

**Interfaces:**
- Consumes: `pushBlock`'s existing `closer` argument (it already receives `func`/`proc`/`type`/control words), `blockRegions`, the sort in `enclosingRegions`.
- Produces: `blockRef` gains `string closer` (`"func"`, `"proc"`, `""` for anything not a routine body); `enclosingDeclarations (in string: text, in integer: line0, in integer: lastLine) → array blockRef`, innermost-first, routine bodies only; `declarationRegion (in string: text, in integer: lastLine, in integer: declLine1) → blockRef`, whose `startLine` is 0 when nothing matches.

- [ ] **Step 1: Write the failing checks** in `tests/blocks_test.sd7`, on a fixture whose second routine has a multi-line header:

```seed7
    # fixture lines: bigHeader name at 5, "is func" at 7, body region 8..11, twice at 13
    check("the routine region carries its closer", closerAt(text, 8), "func");
    check("a control body carries no closer", closerAt(text, 9), "");
    check("a declaration line above its own region still pairs",
          regionOf(text, 5), "8..11");
    check("enclosingDeclarations is innermost first",
          str(depthAt(text, 10)), "2");
    check("a line outside every routine pairs with nothing",
          regionOf(text, 1), "none");
```

`closerAt`, `regionOf`, `depthAt` join the helpers this suite already keeps. `regionOf` returns `"none"` for an unpaired line, which is the answer Task 6 reads as *unresolved*.

- [ ] **Step 2: Run, and name the failure.** `make test-blocks`. Expected: FAILs where every `closer` reads `""` and `regionOf` reads `none`, because the field is not recorded and the pairing function does not exist.

- [ ] **Step 3: Record the closer without touching `kind`.** In `pushBlock`, append the closer word to a parallel `array string: closerName` in `blockStack` alongside the existing `closer`/`openLine`/`kind` arrays, and in `closeFrom` write `r.closer := st.closerName[i]` beside `r.kind := st.kind[i]`. Leave lines `src/blocks.sd7:310` and `:314-315` — the `# Strip internal marker` assignments — exactly as they are. A routine body's `kind` must stay `""` for `foldingRange`.

- [ ] **Step 4: Implement `declarationRegion`** as: the region whose `closer <> ""` and whose `openLine` is the first line at or after `declLine1` where the scan reports `is` followed by `func`/`proc`. The pairing rule is a name-line → body-region map, and a routine whose `is func` sits on the name line must pair with itself (one fixture each).

- [ ] **Step 5: Run to green, prove the mutation, commit.** Removing the `closer` append must fail the closer check; moving the `>` to `>=` in `declarationRegion`'s line test must fail the "a line outside every routine" check.

```bash
git add src/blocks.sd7 tests/blocks_test.sd7
git commit -m "blocks records which region is a routine, so scope has a floor and a ceiling"
```

## Task 4: `src/doc_store.sd7` — a range from a UTF-16 column, and the shipped defect it fixes

`lspRange` treats `column1` as a *character* column and converts with `utf16Before`, so `selection_range.sd7:60`'s `succ(tk.col16)` double-converts (spec §11.8). Invariant 2 says the fix is one new `doc_store` entry point, not a second position function in a feature.

**Files:**
- Modify: `src/doc_store.sd7` (add `lspRangeUnits`)
- Modify: `src/features/selection_range.sd7:60`
- Modify: `tests/doc_store_test.sd7`, `tests/selection_range_test.sd7`

**Interfaces:**
- Consumes: `lsDoc.lineStart`, `lineWidth`, `utf16CharLength`.
- Produces: `lspRangeUnits (in lsDoc: doc, in integer: line0, in integer: col16, in integer: width16) → string`, emitting `{"start":{"line":L,"character":C16},"end":{"line":L,"character":C16+W16}}` with no conversion of `col16`, clamped to the line's UTF-16 width.

- [ ] **Step 1: Write the failing checks** in `tests/doc_store_test.sd7`:

```seed7
    # the astral literal is 2 characters / 4 UTF-16 units, so "count" starts at unit 13
    check("a UTF-16 column is used as given", lspRangeUnits(doc, 0, 13, 5),
          "{\"start\":{\"line\":0,\"character\":13},\"end\":{\"line\":0,\"character\":18}}");
    # that line is 22 characters but 24 UTF-16 units: an absurd column clamps to 24, twice
    check("an absurd column clamps to the line width", lspRangeUnits(doc, 0, 999, 5),
          "{\"start\":{\"line\":0,\"character\":24},\"end\":{\"line\":0,\"character\":24}}");
    check("a column of 0 names the line start", lspRangeUnits(doc, 0, 0, 1),
          "{\"start\":{\"line\":0,\"character\":0},\"end\":{\"line\":0,\"character\":1}}");
```

- [ ] **Step 2: Run, and name the failure.** `make test-doc_store`. Expected: FAIL, function missing.

- [ ] **Step 3: Implement `lspRangeUnits`, then point `selection_range.sd7:60` at it** with `lspRangeUnits(doc, tk.line0, tk.col16, tk.width16)`. Do not delete `lspRange`: diagnostics and the analyzer's byte columns still use `lspRangeBytes` → `lspRange`, and that path is pinned by three existing checks.

- [ ] **Step 4: Add the regression check the defect deserves** in `tests/selection_range_test.sd7`: a `selectionRange` request on the line `x := "😀😀"; count := 1;` at the column of `count` must report `13..18`. Run it before Step 3 and see it fail; that is Review Focus 3 pinned on shipped code.

  *Corrected after Task 4 measured it:* the pre-fix answer is `15..20`, not the `11..16` this step
  predicted, and the direction is the point. Feeding a UTF-16 column into a parameter documented
  as a character column makes `lspRange` expand the first 13 **characters** into 15 **units**, so
  the defect **overshoots**. My prediction assumed a loss, which is the same unit confusion as the
  defect itself.
- [ ] **Step 4b: The same defect exists twice in `selection_range.sd7`** (found by Task 4's
  implementer, ruled in scope): the else-branch for a position with no token builds
  `lspRange(doc, succ(line0), succ(char0))`, and `char0` is the client's UTF-16 column, so it
  double-converts identically — measured as answering 12 for a request at character 10 on the
  astral line. Fix both branches with `lspRangeUnits`, one falsifiable astral check per branch,
  because "there is a token here" and "there is no token here" are different rules that happen to
  share a bug. Leaving the second means the shipped behaviour differs by branch and the only way
  to learn is a later defect report.

- [ ] **Step 5: Run to green, commit.**

```bash
git add src/doc_store.sd7 src/features/selection_range.sd7 tests/doc_store_test.sd7 tests/selection_range_test.sd7
git commit -m "a range from a UTF-16 column, and selectionRange stops double-converting"
```

## Task 5: `src/keywords.sd7` — one list, and the word it was missing

The keyword gate decides whether a destructive operation runs, and the list it would have inherited from `completion.sd7` holds 39 entries and is missing nine words the language owns — `begin`, `when`, `static`, `forward`, `member`, `switch`, `leave`, `exit`, `include` (spec §11.5). A gate on a destructive op cannot share a convenience list. And because Seed7 declares **no** reserved words (`Seed7Home/manual/intro.htm:230`), the gate's membership is established behaviourally — one probe per word — not copied from any list, which is what Task 5's Step 3 now does.

**Files:**
- Create: `src/keywords.sd7`
- Modify: `src/features/completion.sd7` (its private `SEED7_KEYWORDS` becomes a call)
- Create: `tests/keywords_test.sd7`, added to `Makefile`'s `TESTS`

**Interfaces:**
- Consumes: nothing outside the module.
- Produces: `const func boolean: isKeyword (in string: nm)`; `const func array string: keywordList` (the completion candidates).

- [ ] **Step 1: Write the failing checks** in `tests/keywords_test.sd7`:

```seed7
    # every word spec §11.3 lists as a PURE syntax symbol -- the ones globalObjects cannot see
    check("begin is a keyword", str(isKeyword("begin")), "TRUE");
    check("end is a keyword", str(isKeyword("end")), "TRUE");
    check("then is a keyword", str(isKeyword("then")), "TRUE");
    check("otherwise is a keyword", str(isKeyword("otherwise")), "TRUE");
    check("otherwise is not a renameable name", str(isKeyword("::=")), "TRUE");
    check("a library name is not a keyword", str(isKeyword("writeln")), "FALSE");
    check("an empty word is not a keyword", str(isKeyword("")), "FALSE");
    check("the keyword list is not shorter than the 36 completion had",
          str(length(keywordList) >= 36), "TRUE");
```

- [ ] **Step 2: Run, and name the failure.** `make test-keywords`. Expected: `FALSE` where `TRUE` was asked for `begin` — the exact gap, and the reason this task exists before the gate.
- [ ] **Step 3: Write the two lists from measurement, not from a hand-built union.** There is no runtime enumeration (spec §11.5) and Seed7 has **no reserved words** at all
  (`Seed7Home/manual/intro.htm:230`: words are syntax symbols, not reserved identifiers), so the
  only honest criterion is behavioural: a word is gate-worthy exactly when it cannot be a declared
  name. Measured by probing one word per program (`const proc: main is func local
  var integer: <WORD> is 1; ... end func;` analysed with `s7 -q -a`, reserved iff it reports
  errors). The answer for `s7` 5.4.10 is **63 words** — and this step deliberately does not
  transcribe them, because my own first hand sweep transcribed **48** and was wrong twice over
  (`while` appeared in the candidate file with no program behind it; `raise` and `syntax` were never
  candidates at all). `tools/keyword_gate.sh` IS the list: it prints the set and exits 1 when
  `src/keywords.sd7` drifts from it, so the array is regenerated per interpreter release rather than
  copied from a document.

```seed7
const array string: CANNOT_BE_NAME is /* the generator's output, verbatim */;

const func boolean: isKeyword (in string: nm) is func
  result
    var boolean: out is FALSE;
  local
    var integer: i is 0;
  begin
    for i range 1 to length(CANNOT_BE_NAME) do
      if CANNOT_BE_NAME[i] = nm then
        out := TRUE;
      end if;
    end for;
  end func;
```

  The words this probe **rejected** from the gate are the interesting half: `type`, `proc`,
  `result`, `enum`, `switch`, `static`, `member`, `exit`, `leave`, `forward`, `and`, `or`, `div`,
  `mod`, `rem`, `exp`, `times`, `cast`, `conv`, `parse`, `find`, `value`, `nested`, `out` and the
  dot-selector fragments (`ceilDiv`, `divRem`, `mdiv`, `lpad`, `lpad0`, `rpad`, `sci`, `digits`,
  `radix`, `mult`, `sub`, `conj`, `elem`, `symb`, `tuple`, `param`, `class`, `array`, `hash`,
  `struct2`, `varConv`, `getobj`, `getfunc`, `fixLen` excepted) are all LEGAL identifiers —
  `const func integer: type (in integer: n)` analyses and prints `3`. A gate that refused them
  would refuse renames of real symbols for a reason the language does not have.
  Put the probe itself in the module's comment: which command produced the list, and the fact that
  a word's status is measured per interpreter release rather than derived from any of the seven
  hand-written lists.

  `keywordList` — the *completion* candidates, a different product with a different standard — is
  `SEED7_KEYWORDS`'s existing 39 words plus `begin`, `when`, `include`, `switch`, `leave`, `exit`,
  `static`, `member`, `forward`: the words a typist wants offered. It is NOT the gate, and a
  comment above each array must say which product it serves, because the two lists drift apart on
  purpose.
- [ ] **Step 4: Point `completion.sd7` at it** and delete its private list. Its checks must pass unchanged — if a completion candidate disappears, the list you built is wrong, and that is this task's real test.

```bash
git add src/keywords.sd7 src/features/completion.sd7 tests/keywords_test.sd7 Makefile
git commit -m "one keyword list, with the words the analyzer cannot report"
```

## Task 6: `resolveBinding` — whose name is this

The four rows of spec §4, with shadowing subtraction, and the only place that sets `resolved`.

**Files:**
- Modify: `src/occurrences.sd7` (add `binding`, `resolveBinding`)
- Modify: `tests/occurrences_test.sd7`

**Interfaces:**
- Consumes: `occurrencesOf`, `symRec` (with `locals` from Task 2), `enclosingDeclarations`/`declarationRegion` (Task 3), `isKeyword` (Task 5).
- Produces: `binding {string name, string owner, integer scopeStart, integer scopeStop, boolean resolved, boolean keyword, boolean capped}` where `owner` is `"local"`, `"global"`, `"library"`, `"field"` or `""`; `keyword` separates "this is a word of the language" from "this is a name we cannot bind", which is the difference between refusing a rename and over-including one; `scopeStart`/`scopeStop` are 0-based line bounds, `0`/`lastLine` for a global; `capped` says `MAX_OCCURRENCES` was hit. `resolveBinding (in string: text, in array symRec: syms, in string: name, in integer: line0, in integer: lastLine, in string: docPath) → binding`.

- [ ] **Step 1: Write the failing checks** in `tests/occurrences_test.sd7`. The fixture is one file with a global `count`, two routines each with a local `count`, and a `Widget`-typed field use:

```seed7
    b := resolveBinding(text, syms, "count", 4, 20, DOC);      # inside routine A's body
    check("inside a routine, its own local wins", b.owner, "local");
    check("the local's scope is the routine region",
          str(b.scopeStart) & ".." & str(b.scopeStop), "2..8");
    b := resolveBinding(text, syms, "count", 15, 20, DOC);    # outside both routines
    check("outside a routine a buffer declaration is the answer", b.owner, "global");
    check("a global's scope is the document",
          str(b.scopeStart) & ".." & str(b.scopeStop), "0..20");
    check("the subtraction is real: a shadowing local is not in a global's scope",
          str(length(shadowing(syms, "count", DOC))), "2");
    b := resolveBinding(text, syms, "writeln", 15, 20, DOC);
    check("a name only the library declares is a library symbol", b.owner, "library");
    check("a library symbol is still a resolved binding", str(b.resolved), "TRUE");
    b := resolveBinding(text, syms, "pix", 15, 20, DOC);
    check("a field name is unprovable, and says so", b.owner, "field");
    check("an unprovable binding is not resolved", str(b.resolved), "FALSE");
    check("the keyword case is not the mystery case", str(b.resolved), "FALSE");
    b := resolveBinding(text, syms, "begin", 15, 20, DOC);
    check("a keyword binds to nothing at all", b.owner, "");
    check("a keyword is marked as one, so rename can tell it from a mystery",
          str(b.keyword), "TRUE");
    b := resolveBinding(text, syms, "mysteryName", 15, 20, DOC);
    check("an unknown name is unresolved but not a keyword", str(b.keyword), "FALSE");
    # the same name, in a buffer whose analysis reported nothing: Review Focus 1's read side
    b := resolveBinding(truncated, symsOf(truncated, LIBS, DOC), "count", 3, 3, DOC);
    check("a truncated buffer leaves the binding unresolved", str(b.resolved), "FALSE");
    check("but it still answers the whole document", str(b.scopeStop), "3");
```

`shadowing(syms, name, docPath)` is a test-only helper in this suite: it lists the routines whose
`locals` carry the name, which is the number the subtraction has to exclude.

- [ ] **Step 2: Run, and name the failure.** `make test-occurrences`. Expected: every `owner` reads `""`, because `resolveBinding` does not exist.

- [ ] **Step 3: Implement the resolution in this order** — the order is the decision, the body is the implementer's:

1. Resolution runs FIRST (R28, corrected by Task 6's measurement). The keyword predicate is consulted only after resolution fails, because the gate is the list of words that CANNOT be a declared name — so if a word is in it, nothing in the file can have declared it, and resolution failing first costs nothing. The reason the order still matters is `for`, `in` and `is`: they are in the gate AND are reported by `globalObjects` as `ACTOBJECT` records (52 of them for `for`), so gating first turns a library-symbol binding into `""` and a `references` answer into `null`. The original justification for R28 — that gating first would answer `null` for a user-declared symbol named `type` — is WRONG and was measured wrong by me: `type` is not in the gate (the probe analyses `const func integer: type (in integer: n)` cleanly), so `isKeyword("type")` is FALSE and gate-first would not have hidden it. The check that pins the ordering is the `for` one, not the `type` one.
2. `enclosingDeclarations(text, line0, lastLine)` innermost-first. For the innermost routine region, if `name` appears in that routine's `symRec.locals` → `owner = "local"`, scope = that region.
3. Else a `symRec` whose `file` is `BUFFER_FILE` or the document path and whose `name = name` → `owner = "global"`, scope = whole document **minus** every region of every routine whose `locals` carry the same name. Keep the subtraction as a list of excluded regions on the `binding`, not as a pre-filtered occurrence array: Task 7 needs both the regions and the declaration's own line.

   **Corrected by Task 6's review (R34, R35).** *Ownership* of a paired region is not free:
   `closeFrom` emits a region only when `openLine < endLine`, so a one-line routine yields no region and
   its name line pairs with the NEXT routine below (`src/blocks.sd7:405-412` says so in its own
   `shortcut:` comment). A record that does not own its pair must not claim its scope and must not
   contribute to `excluded` — a region belongs to the buffer record with the greatest `line1` at or
   before `region.startLine`. Left unverified, a cursor on a global inside `main` bound `local` with a
   one-line `tiny`'s parameter line as its declaration: the rename edits tiny and main's uses, never the
   global, and the program stops compiling.
3a. **Before** the library row and after rows 1–2, the gate (R36): a name in `CANNOT_BE_NAME` →
    `owner = ""`, `keyword = TRUE`, `resolved = FALSE`. Rationale: nothing a user declared can be
    named `for` — that is what the probe measured — while `globalObjects` reports 52 `for` records,
    so gating after the library row made `references` on `for`, `in`, `is` or `to` list every
    occurrence in the file, which is precisely the noise row 6 exists to suppress. R28 is NOT
    weakened: `type`, `proc`, `result` and `enum` are not in the gate, so a program declaring
    `const func integer: type (...)` still resolves as a global.

4. Else any `symRec` with that name → `owner = "library"`, `resolved = TRUE`, scope = whole document.
5. Else the name appears as a `locals` entry of some routine that does not enclose `line0`, or the token follows a `.` (a field use) → `owner = "field"`, `resolved = FALSE`, scope = whole document.
6. Else the name is in `CANNOT_BE_NAME` → `owner = ""`, `keyword = TRUE`, `resolved = FALSE` — language furniture, so `references` answers `null` rather than listing every `begin` in the file, and `rename` refuses.
7. Else `owner = ""`, `keyword = FALSE`, `resolved = FALSE`, scope = whole document — the over-inclusive row.

- [ ] **Step 4: Set `capped`** when the occurrence pass reached `MAX_OCCURRENCES`.

- [ ] **Step 5: Run to green, prove the mutations.** Four named mutations, four named reds: skip step 2 (local case must go red), skip the subtraction (the shadow check must go red), invert step 4 (the library case), and drop the `.`-precedes test (the field case). Review Focus 1 and 2 live in these checks.

```bash
git add src/occurrences.sd7 tests/occurrences_test.sd7
git commit -m "binding resolution: the analyzer's scope, minus what shadows it"
```

## Task 7: `textDocument/references`

**Files:**
- Create: `src/features/references.sd7`
- Modify: `src/rpc.sd7` (add `boolAt` — the store has `atKey`/`strAt`/`intAt` and no boolean reader, and two of this milestone's three methods need one)
- Modify: `src/lsp_server.sd7` (dispatch, `referencesProvider: true`, the `window/logMessage`)
- Modify: `tests/features_test.sd7`, `tests/rpc_test.sd7`, `tests/lsp_server_test.sd7`, `tests/transcript.py`

**Re-pins an existing check, on purpose:** `tests/lsp_server_test.sd7` keeps an `UNHANDLED` array that *asserts `referencesProvider` is not advertised* (`firstMissing`/`firstUnhandled`, lines 9–45). Move the name from `UNHANDLED` to `HANDLED` in the same commit that adds the capability, or the suite goes red for a reason the next reader cannot tell from the failure line.

**Interfaces:**
- Consumes: `resolveBinding`, `occurrencesOf`, `lspRangeUnits` (Task 4), `lspWholeLine`, `jsonw.sd7`, `wordRef`, `uris.sd7`'s `pathOf` (so the feature derives the document path itself, exactly as `definition.sd7` already includes `uris.sd7`).
- Produces: `boolAt (in jsonValue: obj, in string: name, in boolean: fallback) → boolean` in `rpc.sd7`, total like `intAt`; `refsAnswer {string json, boolean unresolved, string why}`; `referencesAnswer (in lsDoc: doc, in array symRec: syms, in wordRef: word, in string: docUri, in boolean: includeDeclaration) → refsAnswer`. The feature computes `resolveBinding(doc.text, syms, word.word, word.line1 - 1, lineCount(doc) - 1, pathOf(docUri))`.

- [ ] **Step 1: Write the failing checks** in `tests/features_test.sd7`:

```seed7
    a := referencesAnswer(doc, syms, atLine("count", 5, 9), URI, FALSE);
    check("a local's references are its own region only", str(uriCount(a.json)), "3");
    check("every location carries an exact character range", str(endCount(a.json)), "3");
    a := referencesAnswer(doc, syms, atLine("count", 16, 1), URI, TRUE);
    check("includeDeclaration adds the declaration line", str(uriCount(a.json)), "5");
    a := referencesAnswer(doc, syms, atLine("pix", 16, 5), URI, FALSE);
    check("a field answers every same-named token", str(uriCount(a.json)), "4");
    check("a field says the binding was unresolved", str(a.unresolved), "TRUE");
    a := referencesAnswer(doc, syms, atLine("begin", 16, 3), URI, FALSE);
    check("a keyword answers null, not an empty list", a.json, "null");
    a := referencesAnswer(doc, syms, emptyWord, URI, FALSE);
    check("a position with no token answers null", a.json, "null");
```

`uriCount` already exists in this suite (`tests/features_test.sd7:89`) and counts `{"uri":`;
`endCount` is its sibling counting `"end":{"line":`. `atLine(nm, line1, column1)` extends the
existing `exact(nm)` helper by carrying a position instead of pinning one, and `emptyWord` is
`wordRef.value` — the record whose `word` is `""`.

Add the `boolAt` checks to `tests/rpc_test.sd7` in the same commit: a present `TRUE`, a present
`FALSE`, a missing key answering the fallback, and a `jsonNumber` at that key answering the
fallback rather than raising — `rpc.sd7`'s other readers are total, and a non-boolean in a boolean
slot is reachable from a real client.

- [ ] **Step 2: Run, and name the failure.** `make test-features`. Expected: FAIL on the first check, `referencesAnswer` unmatched; the suite still analyses because the test file's `include` list gains `features/references.sd7` in Step 3 — add it and see the analysis error name the missing file, which is the red.

- [ ] **Step 3: Implement `boolAt` first** (`src/rpc.sd7`, beside `intAt`), then the references shape. Locations are `{"uri": docUri, "range": lspRangeUnits(doc, line0, col16, width16)}` per occurrence inside `binding`'s scope; a declaration location, when `includeDeclaration`, is `lspWholeLine(line1)` for the `symRec` found, and **only when that record is a buffer declaration** (spec §5 — a library declaration is `definition`'s job). `null` when `word.word = ""`, when the token is a keyword, or when `resolveBinding` returned `owner = ""` for a keyword.
- [ ] **Step 4: Wire the dispatch and the capability.** `referencesProvider: true` in `capabilitiesJson`; the method branch reads `context.includeDeclaration` with `boolAt`, defaulting to `FALSE`, and sends `window/logMessage` (severity 3, `why` as the body) when `unresolved` — the notification is sent before the response, and the log goes to stderr as well.
- [ ] **Step 5: Run to green, commit.**

```bash
git add src/features/references.sd7 src/lsp_server.sd7 tests/features_test.sd7
git commit -m "textDocument/references, with exact columns for the first time"
```

## Task 8: `initialize` learns to read, and `prepareRename`

The first client capability this server ever consults (spec §6, §7): a `WorkspaceEdit` is only a promise if the client can apply one.

**Files:**
- Modify: `src/lsp_server.sd7` (store `clientCanApplyEdits`, `renameProvider` object, `prepareRename` branch)
- Modify: `tests/lsp_server_test.sd7`, `tests/transcript.py`

**Files:**
- Modify: `src/lsp_server.sd7` (store `clientCanApplyEdits`, `renameProvider` object, `prepareRename` branch)
- Modify: `tests/lsp_server_test.sd7`, `tests/transcript.py`

**Re-pins an existing check, on purpose:** `renameProvider` sits in `UNHANDLED` in
`tests/lsp_server_test.sd7:14-16`, asserted *not* advertised. Move it to `HANDLED` in this commit.

**Interfaces:**
- Consumes: `rpc.sd7`'s `atKey`/`boolAt` (Task 7), `resolveBinding`, `occurrencesOf`, `lspRangeUnits`, `uris.sd7`'s `pathOf`.
- Produces: `var boolean: clientCanApplyEdits is FALSE;` set from `workspace.applyEdit` during `initialize`; `prepareAnswer {string json, boolean refused, string why}`; `const func prepareAnswer: prepareRenameAnswer (in lsDoc: doc, in array symRec: syms, in wordRef: word, in string: docUri, in boolean: canApplyEdits) → prepareAnswer`, whose `json` is `{range, placeholder}` or `null`. **Moved by ruling R45 into `src/features/prepare_rename.sd7`** (it lived in `lsp_server.sd7` because it read the module-global capability flag, which `src/features/rename.sd7` cannot reach), with `canApplyEdits` passed in by the dispatcher — so Task 9 calls the SAME predicate instead of restating its eight arms.

- [ ] **Step 1: Write the failing checks** in `tests/lsp_server_test.sd7` — capability shapes first:

```seed7
    check("referencesProvider is advertised", str(advertised("referencesProvider")), "TRUE");
    check("renameProvider is an object with prepareProvider",
          str(pos(capabilitiesJson, "\"renameProvider\":{\"prepareProvider\":true}") <> 0),
          "TRUE");
    check("positionEncoding is still utf-16",
          str(pos(capabilitiesJson, "\"positionEncoding\":\"utf-16\"") <> 0), "TRUE");
    check("workspace/symbol stays unadvertised", str(advertised("workspaceSymbolProvider")), "FALSE");
    p := prepareRenameAnswer(doc, syms, atLine("writeln", 16, 3), URI);
    check("a library symbol refuses", str(p.refused), "TRUE");
    check("a refusal answers null, not an error", p.json, "null");
    p := prepareRenameAnswer(doc, syms, atLine("mysteryName", 16, 1), URI);
    check("an unbound name refuses rather than rewriting the file", str(p.refused), "TRUE");
    p := prepareRenameAnswer(truncatedDoc, syms, atLine("count", 3, 1), URI);
    check("a truncated buffer refuses, so the text cannot be damaged", str(p.refused), "TRUE");
    check("a bound local is accepted", str(prepareRenameAnswer(doc, syms,
          atLine("count", 5, 9), URI).refused), "FALSE");
    p := prepareRenameAnswer(doc, syms, atLine("count", 5, 9), S7I_URI);
    check("rename refuses inside a .s7i buffer while R-F10 stands", str(p.refused), "TRUE");
```

`advertised` exists at `tests/lsp_server_test.sd7:21`. The last check is the M5/M6 line held in
code: `workspace/symbol` is *not* in this milestone and must not be advertised for it.

- [ ] **Step 2: Run, and name the failure.** `make test-lsp_server`. Expected: `FALSE` for the rename object — it is still a bare `true` today — and every `prepareRenameAnswer` check unmatched, because that function is written in Step 4. `advertised`, `capabilitiesJson` and `HANDLED`/`UNHANDLED` are the suite's existing machinery; `prepareRenameAnswer` is reached because `lsp_server_test.sd7:3` already includes `lsp_server.sd7`, and the feature include arrives with Step 4.
- [ ] **Step 3: Read the capability.** In the `initialize` branch, before answering, walk `params.workspace.applyEdit` through the existing guarded `atKey` chain and store the boolean; a missing key leaves it `FALSE`. One comment line: this is the only client capability the server reads, and the reason the rest of the debt is listed in spec §10 rather than paid here.
- [ ] **Step 4: Write `prepareRenameAnswer`** refusing `null`, with a `why` the dispatcher logs, when: `clientCanApplyEdits` is `FALSE` (Review Focus 5); `binding.owner` is `"library"`; `binding.keyword` is `TRUE`; `binding.resolved` is `FALSE` for any other reason (spec §12.1 — a write refuses where a read over-includes); the document path ends `.s7i` (`endsWith(docPath, ".s7i")`, spec §12.3); or the token is not a name. The success shape is `{"range": lspRangeUnits(doc, line0, col16, width16), "placeholder": name}`.
- [ ] **Step 5: Run to green, prove the mutations.** Five named mutations, five named reds: `clientCanApplyEdits` default `TRUE`, the `.s7i` test removed, the unresolved-vs-keyword states conflated, `placeholder` dropped, the capability object flattened back to `true`.

```bash
git add src/lsp_server.sd7 tests/lsp_server_test.sd7
git commit -m "prepareRename, and the first client capability the server reads"
```

## Task 9: `textDocument/rename`

**Files:**
- Create: `src/features/rename.sd7`
- Modify: `src/lsp_server.sd7` (dispatch, `-32602` path)
- Modify: `tests/features_test.sd7`, `tests/transcript.py`

**Interfaces:**
- Consumes: `renameDecision (doc, syms, word, docUri, canApplyEdits) → renameCheck {refused, reason, oc, slot, b}` from `src/features/prepare_rename.sd7` — **the shared refusal predicate (R45)**, not `prepareRenameAnswer` and never a copied arm list — plus `inScope (oc, b)`, `lspRangeUnits`, `isKeyword`, `nameStart`/`nameMore`, `symRec` name sets, `rpc.sd7`'s `sendError`.

  **R45 sharpens this line:** Task 9 calls `renameDecision` and branches on `refused`/`reason`,
  reusing the `oc`/`slot`/`b` it hands back rather than resolving a second time. Spec §6's "rename
  re-runs resolution, trusts nothing" is satisfied by re-CALLING the shared predicate — a second
  copy of eight rules is the divergence that turns into "accepted by `prepareRename`, edited by
  `rename`". `inScope (oc, b)` is Task 9's to call: `prepareRename` never needed it, because a
  one-token range has no scope to filter, so each request filters the list exactly once.
- Produces: `renameAnswer {string json, string error, string why}` where `error` is `""` or `"invalid"`; `renameResult (in lsDoc: doc, in array symRec: syms, in wordRef: word, in string: docUri, in string: newName, in boolean: canApplyEdits) → renameAnswer` — the sixth parameter arrives because `renameDecision` needs the capability flag and a feature may not read the dispatcher's global (R45). `editCount` counts `"{\"range\":{"` in the same idiom as `uriCount`.

- [ ] **Step 1: Write the failing checks** — the collision and shape rules, from spec §6:

```seed7
    a := renameResult(doc, syms, word, URI, "total");
    check("a clean rename edits every occurrence in scope", str(editCount(a.json)), "3");
    check("a rename touches exactly one document", str(uriCount(a.json)), "1");
    check("an edit carries start and end", str(editCount(a.json) + 0), "3");
    a := renameResult(doc, syms, word, URI, "count");
    check("renaming a global onto a local of its own name is refused", a.error, "invalid");
    a := renameResult(doc, syms, word, URI, "1bad");
    check("a name that is not an identifier is refused", a.error, "invalid");
    a := renameResult(doc, syms, word, URI, "");
    check("an empty name is refused", a.error, "invalid");
    a := renameResult(doc, syms, word, URI, "begin");
    check("a keyword is refused", a.error, "invalid");
    a := renameResult(doc, syms, word, URI, "writeln");
    check("a stdlib name is not a collision", a.error, "");
    a := renameResult(doc, syms, word, URI, "other");
    check("a same-named routine elsewhere is not a collision", a.error, "");
```

- [ ] **Step 2: Run, and name the failure.** `make test-features`. Expected: FAIL, `renameResult` unmatched.
- [ ] **Step 3: Implement validation before the pass**, in the order spec §6 lists, reading `binding.owner` to pick the scope the collision test runs against (routine's `locals` plus the routine's own name for a local; buffer `symRec` names for a global; nothing for `"library"`). An overload sibling is not a collision (spec §2). `MAX_OCCURRENCES` overflow → `error = "invalid"` with `why` naming the cap, never a truncated edit (Review Focus 1).
- [ ] **Step 4: Emit `WorkspaceEdit { changes: { <docUri>: [TextEdit] } }`**, one `TextEdit` per occurrence, `newText` written through `addStr` (never `str()` on a `jsonValue`), and the dispatcher answering `-32602 InvalidParams` when `error = "invalid"` and `null` on any refusal that came from `prepareRename`'s rules.
- [ ] **Step 5: Run to green, prove the mutations.** Run the astral fixture from Review Focus 3 through `rename` too: mutate `lspRangeUnits` back to `lspRange` and require that named check to go FAIL on column 13 — that is the mutation that proves a rename would have written two columns left.

```bash
git add src/features/rename.sd7 src/lsp_server.sd7 tests/features_test.sd7
git commit -m "textDocument/rename: one document, refused rather than partial"
```

## Task 10: the wire surface, end to end

Nothing in Tasks 7–9 is believed until it has been through a real frame with a real client-shaped `initialize`.

**Files:**
- Modify: `tests/transcript.py`

**Interfaces:**
- Consumes: the running server, unchanged.
- Produces: the golden transcript checks named below; no production file is touched by this task, and if one must be, that is a defect found here.

- [ ] **Step 1: Write the failing run.** *(Partly superseded — Tasks 7–9 shipped wire checks as they went and Task 10 closed the remainder; its report's inventory is the authority. What survives here is the astral/UTF-16 case, which Task 12 unblocks.)* Add to `tests/transcript.py`, in the existing `req`/`notify` idiom and against the fixture already open:

```python
expect(caps["referencesProvider"] is True, "initialize advertises referencesProvider")
expect(caps["renameProvider"] == {"prepareProvider": True},
       "renameProvider is the object with prepareProvider, got %s" % caps.get("renameProvider"))
# references on the open fixture's local, then on the global, then on a library name
refs = call(idSeq(), "textDocument/references",
            {"textDocument": td(URI), "position": pos(URI, 4, 8),
             "context": {"includeDeclaration": False}})
expect(all(l["range"]["start"]["character"] != l["range"]["end"]["character"] for l in refs),
       "references carry non-empty ranges")
prep = call(idSeq(), "textDocument/prepareRename", {"textDocument": td(URI),
                                                    "position": pos(URI, 15, 4)})
expect(prep is None, "prepareRename on a library symbol answers null")
edit = call(idSeq(), "textDocument/rename", {"textDocument": td(URI),
              "position": pos(URI, 4, 8), "newName": "tally"})
expect(list(edit["changes"].keys()) == [URI], "the WorkspaceEdit names one uri")
```

- [ ] **Step 2: Add the two client-shape runs** the spec's §7 requires: an `initialize` **without** `workspace.applyEdit` must get `null` from `prepareRename` and still answer hover and diagnostics normally; an `initialize` whose `workspace` key is absent must not raise and must not close the stream.
- [ ] **Step 3: Add the log-line check:** the unresolved-binding request (`pix`) must be preceded by a `window/logMessage` notification whose `message` names the reason, and nothing but frames may appear on stdout.

  *Already shipped by Task 7* (`tests/transcript.py:316-323` pins the log notification ordering and
  `junk == 0`; `:325-333` pins `-32601` for `typeDefinition` and silence for an unknown
  notification). Task 10 must NOT duplicate it — its job is the two client-capability shapes and
  the rename path end to end.
- [ ] **Step 4: Run and read the totals.** `python3 tests/transcript.py`; expected: FAILs naming the methods as unimplemented, then green after Tasks 7–9 are in place. If any earlier task already made these pass, the check is not proving what it claims — re-read that check before moving on.
- [ ] **Step 5: Commit.**

```bash
git add tests/transcript.py
git commit -m "the M5 surface, driven through real frames"
```

## Task 11: the documents, the invariants, and the corpus gate

**Files:**
- Modify: `docs/superpowers/specs/2026-09-10-seed7-lsp-server-design.md` (the §8 M5 row, §5's references/rename row, the §4 note that `parseStri` is not capped at 10)
- Modify: `README.md` ("What works", "What does not work yet")
- Modify: `AGENTS.md` (the M5 line in Milestones; the keyword-list finding; the two corrected numbers)
- Create: `tools/corpus_scan.sh` — the throwaway gate, not a suite

**Interfaces:**
- Consumes: everything.
- Produces: documents that match the code, and a measured number for the whole-library corpus.

- [ ] **Step 1: Amend the parent design's M5 row** to exactly the text in spec §8, and its §5 references/rename row to "no source in the reflection API; answered by the occurrence index over one document". Do not delete the old 2-file criterion silently — replace it and note the replacement is dated 2026-10-12 and why.
- [ ] **Step 2: Record the two measurements that contradict the repo's own notes**: `errorCount` is not capped at 10 by `parseStri` (spec §11.4), and `globalObjects` cannot enumerate `$ syntax` symbols so a keyword list stays a copy (spec §11.5). Put the second one where the semanticTokens `keyword`-class decision lives, in `AGENTS.md`'s protocol-decision list, because that is where the next reader will look.
- [ ] **Step 3: Write the corpus gate** as `tools/corpus_scan.sh`: for each of `lib/*.s7i` (213) and `prg/*.sd7` (129) in the Seed7 checkout, run a one-file Seed7 driver that calls `occurrencesOf` on the file's text for its first 20 name tokens and prints a line only when the pass returns zero occurrences for a name the file's own `globalObjects` declares. It is a spike: no suite entry, no `make test` dependency, and a `shortcut:` comment naming the limit (it does not check columns, only that the pass terminates and finds its own declarations).
- [ ] **Step 4: Run it, and write down the count it reports**, in the spec's §11 as measurement 12. A nonzero count is a defect in `occurrencesOf` and gets fixed here, not deferred.
- [ ] **Step 5: Run the invariant greps and the whole suite**, then update the README's totals to the measured ones:

```bash
grep -rn 'progs.s7i' src/                       # exactly one line
grep -rn 'addStr(w, str(' --include='*.sd7' src/  # empty
make test                                        # 0 failed, and the new totals
```

- [ ] **Step 6: Commit.**

```bash
git add docs/ README.md AGENTS.md tools/corpus_scan.sh
git commit -m "M5 shipped: the design's M5 row, two corrected numbers, and a corpus gate"
```

---

## Task 12: `src/transport.sd7` — read a frame body by BYTE, as `Content-Length` says

Found by Task 10 and reproduced by the controller. `src/transport.sd7:73` does
`body := gets(STD_UTF8_IN, contentLength)`, and `gets` on a `utf8File` (`seed7/lib/utf8.s7i:132` →
`utf8_gets`) counts **characters**. Measured: reading 3 from a buffer holding `éa` consumes 5 bytes
and leaves the remainder unread, so any inbound body with a non-ASCII byte reads past its own frame
and the next header read is garbage. It hid for four milestones because `tests/transcript.py` writes
bodies with `json.dumps`, which escapes non-ASCII to `\uXXXX` unless `ensure_ascii=False` is passed —
so no test body was ever non-ASCII. Real clients do not escape. The parent design's §3.1 claimed the
opposite and called it verified; that sentence is corrected in this plan's history. Do not
re-litigate it.

**Files:** Modify: `src/transport.sd7`; Modify: `tests/transport_test.sd7`; Modify:
`tests/transcript.py` (raw-UTF-8 bodies become sendable here, which closes the wire gap Task 10
reported as unreachable).
**Interfaces:** Consumes: `utf8bytes.utf8Length`, the outbound byte count this module already owns.
Produces: `readMessage` with an unchanged signature, returning a body whose bytes were consumed
exactly.

- [ ] **Step 1: Write the failing check.** Two frames in one stream where the first body contains a
  2-byte and a 4-byte character; the second frame must be parsed and answered. Expected red: the
  answer for the second id is absent, because the reader resyncs mid-frame. Name that red.
- [ ] **Step 2: Find the byte-exact route by measurement, not by assumption.** Candidates to probe
  before trusting: read `STD_IN` as bytes and decode (measure whether `string(bstring)` at
  `seed7/lib/bstring.s7i:59` performs UTF-8 decoding or a byte-per-character copy — the controller
  could not even construct a `bstring` from `chr(195) & chr(165)`, `Match for
  {CHR_ICONV1(chr(195)) & chr(165) } failed`, so the construction itself needs measuring); or read
  characters and consume the residual bytes the frame arithmetic implies. Record in the module
  comment how many bytes each candidate consumes for the fixture string. `utf8_gets` has no proven
  byte mode; do not assume one.
- [ ] **Step 3: Implement and prove both directions.** `make test-transport` green with every
  existing check unchanged in value, plus the new two-frame check. Reverting to
  `gets(STD_UTF8_IN, contentLength)` must redden it; so must a decode that emits one character per
  byte. State the value each produces.
- [ ] **Step 4: Close Task 10's unreachable wire gap.** With raw bodies surviving, add the wire
  check Task 10 could not write: an astral character delivered raw in `didOpen` text, arriving as
  ONE character, with a `references` or `rename` column that separates UTF-16 from characters
  (`x := "é😀"; amount := 1;` → char 11, UTF-16 12, byte 15). Leave Task 10's defect pin where it
  is; Task 13 flips it.
- [ ] **Step 5: Commit.** Report: bytes consumed per candidate, both proofs, and whether the
  README's client snippets may now claim non-ASCII documents.

## Task 13: the RPC string readers join surrogate pairs, so `"\ud83d\ude00"` is one character

Also from Task 10, measured by the controller: `readJson` expands `"\uD83D\uDE00"` into TWO
characters (`ord` = 55357, a lone surrogate), so an astral character sent in JSON escape form arrives
as two code points. `doc_store` then counts 2 characters and 2 UTF-16 units where the client meant 1
character and 2 units — the columns coincidentally agree, which is the only reason the wire could not
see the `lspRange` bug class in Tasks 4 and 9. The user-visible damage is worse than a column: the
analyzer's scanner rejects each lone surrogate, so a file containing an emoji publishes bogus Errors —
measured as 4 diagnostics for 2 astral characters.

**Files:** Modify: `src/rpc.sd7` (`strAt` and any sibling that reads a string out of a parsed
value); Modify: `tests/rpc_test.sd7`; Modify: `tests/transcript.py` — the F2 defect pin at
`tests/transcript.py:786-791` MUST flip in this commit; that flip is the acceptance test.
**Interfaces:** Consumes `readJson`'s output. Produces `const func string: joinSurrogates (in
string: stri) is func`, total — a stray lone surrogate passes through unchanged rather than raising,
because an exception in this module reaches the protocol channel.

- [ ] **Step 1: Write the failing checks.** `joinSurrogates` over: a valid pair, two pairs, a lone
  high, a lone low, a BMP-only string, and the empty string. Build the pair from the value
  `readJson` actually produced (55357 / 0xD83D), not from a `\uD83D` literal typed into the test
  file — the typed literal is a different input and would test the wrong thing.
- [ ] **Step 2: Implement** the arithmetic `(high − 0xD800) × 0x400 + (low − 0xDC00) + 0x10000` in
  one pass, with the totality rule above, and call it from the string readers so the fix lands where
  every caller benefits.
- [ ] **Step 3: Flip the pin.** Task 10's F2 expectation becomes "the astral document publishes NO
  diagnostics". Keep its comment and history rather than rewriting it as if the bug never existed.
  Prove the flip: revert `joinSurrogates` to identity and require the wire check to go red.
- [ ] **Step 4: Commit.** Then report whether `hover`'s reconstructed signatures and the analyzer's
  byte-column diagnostics now agree about astral text. If they do not, that is a finding for the
  whole-branch review, not a change to make here.
