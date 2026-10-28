# Own Records First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** executed 2026-10-28 — Tasks 1-4 and the final fix wave are on this branch, so Facts 1 and 2 below describe the PRE-fix state the branch deleted. They are the reproduction each task starts from, not the behaviour of the merged tree. Facts 3-5 are pre-wave too: the three inlined copies Fact 3 lists were replaced by Task 3, and the `tests/features_test.sd7` line numbers it cites shifted when the new fixtures were added, so locate those checks by title.

**Goal:** Make every feature that truncates a symbol list, or takes the first record for a name, answer about the analysed document's own declarations before the standard library's.

**Architecture:** Two layers, deliberately. `analysis.collectSyms` appends the document's own records first, so the list the server holds is ranked once, at the producer. Then each consumer whose answer depends on *selection* — `definitionResult`'s 20-location cap, `buildClasses`' first-record-wins type table, `completion.emitSyms`' 100-item cap — makes that selection order-independent by calling one body twice with a `wantOwn` boolean, so a fabricated or differently-ordered list cannot change a user-visible answer. In the consumers, no array is copied and no loop body is duplicated: the shape to copy is `completion.sd7:102-103`. (At the producer the record list is deliberately buffered into two groups, which copies each surviving record twice — see the retraction recorded in `docs/seed7-cli.md`.)

**Tech Stack:** Seed7 5.4.10 (`s7`, `s7c`), GNU `make`, POSIX `sh`, `python3` for the wire suite. No third-party dependency; the server imports only `seed7_05.s7i`, standard libraries, and its own modules.

**Spec:** none in this tree. The design authority `docs/superpowers/specs/2026-09-10-seed7-lsp-server-design.md` was deleted in `fca09be` and `AGENTS.md:6` still points at it — that dangling pointer is a separate finding and is **out of scope here**. This plan argues from *Facts this plan rests on* below, each reproducible with the command beside it.

## Global Constraints

Every task's requirements include this section.

- Red first: write the check, run it, confirm it fails for the stated reason, then implement. `make test` before and after every task.
- Baseline for this branch: **21 graded lines, 1 049 checks, every suite reporting `0 failed`** at `22ea2fc`. `make test` prints one graded line per suite; it is always 21.
- Only `src/analysis.sd7` imports `progs.s7i`. Enforced by `tests/graph_test.sh:59-60` (`test $(sh tools/project_graph.sh | grep -c "progs.s7i") -eq 1`). None of these tasks may add an include.
- `analysis.sd7` returns Seed7 data and knows nothing about LSP (invariant 4): the reorder must emit no JSON and no `jsonValue`.
- Only `src/*.sd7` and `src/features/*.sd7` build LSP response shapes (invariant 4); only `doc_store.sd7` converts positions (invariant 2). Neither is touched here.
- Nothing may raise onto stdout (`AGENTS.md`): every new accessor stays total, and `src/transport.sd7` still owns every outbound byte count.
- Seed7 traps that bite this change, verbatim from `AGENTS.md`: `&` copies its whole left side, `&:=` grows in place; `in`/`not in` have no array overload; declare before use (a `func` cannot call a helper defined later in the file); a `local` cannot be initialised from a parameter of the same function; `writeln` takes exactly ONE argument; strings escape as `"...\"..."`; an array literal is `[]("a", "b")`.
- Mutation proof after **each** commit: mutate one production branch, run the suite, name the check that goes FAIL, then revert **per file** with `git checkout -- src/<file>.sd7`. Never `git checkout -- .` — it silently undoes uncommitted work.
- `docs/PROJECT_GRAPH.md` is a **generated, committed artifact** that records each module's line count as well as its includes. `make test-graph` (21 checks) fails if the committed file differs from a fresh `make graph` run, so adding comment lines to `src/` legitimately changes it: regenerate with `make graph` and commit the artifact in the same commit. What may NOT change is the include set — `progs.s7i` must still appear exactly once.

## Facts this plan rests on

Re-measure before restating any of these; they were taken on 2026-10-28 against `s7` 5.4.10 and `~/seed7` at `c93282a6`.

1. **`globalObjects` yields library records before the buffer's.** A buffer that declares `const func integer: length (in Widget: w)` and calls it answers `textDocument/definition` with 10 locations: `string.s7i:336`, `ref_list.s7i:191`, `basearray.s7i:196`, `struct.s7i:37`, `array.s7i:228`, `file.s7i:195`, `null_file.s7i:274`, `clib_file.s7i:247`, `external_file.s7i:266`, and the buffer's own `st2.sd7:4` **last**. Reproduce with the fixture in *Task 1 Step 1* driven over real frames.
2. **`semanticTokens/full` marks that same declaration a library symbol.** Its token (line index 4, column 20, length 6) came back as tokenType `function`, tokenModifiers `defaultLibrary`, with **no** `declaration`. `src/features/semantic_tokens.sd7:44-53` (`buildClasses`) takes the first record per name, so `declLines["length"]` is the library's line and the equality test `tk.line0 + 1 = declLines[word]` in `tokensIn` can never fire for the buffer.
3. **`analysis.isBufferFile(fname, docPath)` (`src/analysis.sd7:53`, with `BUFFER_FILE` at `:46`) is already the one "declared in this document" rule** — `BUFFER_FILE` for text handed to `parseStri`, the document's own path for an open `.s7i`. Three consumers inline it anyway: `src/features/document_symbol.sd7:22`, `src/features/semantic_tokens.sd7:49`, `src/features/completion.sd7:68`.
4. **`completion` already compensates for fact 1** and says so (`src/features/completion.sd7:57-63`), pinned by `tests/features_test.sd7:22-45` (`ownLastSyms`: 200 library records then the buffer's, with "own-file symbols win the cap" at `:690`). That is the pattern this plan extends, not a workaround to delete.
5. **Two cap counts must not move:** `tests/features_test.sd7:647-648` pins `uriCount = 20` for `MAX_LOCATIONS`; `tests/features_test.sd7:687-689` pins `labelCount = 100` for `MAX_COMPLETIONS`.
6. **Frozen tokens are unaffected by this work.** `tools/agents_required.txt` (44 tokens) holds no suite count, no 342 and no 192, so adding checks cannot redden `make test-agents`. It does make `docs/seed7-cli.md:394` stale — Task 4 restates it.

## File structure

| File | Responsibility | Task |
|---|---|---|
| `src/analysis.sd7` | modify `collectSyms` (`:272`, append at `:308`) so own records are appended first | 1 |
| `tests/analysis_test.sd7` | add the record-order pins beside the existing `symsNamed` checks (`:249-260`) and the `.s7i` driver checks (`:338-344`) | 1 |
| `tests/transcript.py` | add a wire check group (one answer check, one frames-only control) after the existing `definition` checks (`:246-260`) | 1 |
| `src/features/definition.sd7` | modify `definitionResult` (`:21`) to two passes, own first | 2 |
| `tests/features_test.sd7` | add the `libFirstLength` fixture near `ownLastSyms` (`:22-45`) and its checks in the `definition` block (`:598-648`) | 2 |
| `src/features/{document_symbol,semantic_tokens,completion}.sd7` | replace the three inlined buffer tests with `isBufferFile` | 3 |
| `src/features/semantic_tokens.sd7` | modify `buildClasses` (`:35`) to fill the tables own-first | 4 |
| `tests/semantic_tokens_test.sd7` | add the `libThenOwn` fixture beside `twoWriteln` (`:26`) and its check | 4 |
| `docs/seed7-cli.md` | restate the suite-totals row (`:394`) from a fresh `make test` | 4 |

`src/features/hover.sd7:12` and `src/features/signature_help.sd7:64` also truncate (`MAX_HOVER_OVERLOADS` 5, `MAX_SIGNATURES` 10). They are fixed by the producer in Task 1 and get a `shortcut:` comment naming the dependency, not a fourth two-pass: their `syms` argument arrives only from `analysisCache`, so nothing else can hand them a library-first list.

## Review Focus

The spec is silent on these; each line gets its test in the named task.

1. **An open `.s7i` buffer** reports its own declarations under the file's real path, not `BUFFER_FILE` (`analysis.sd7:53` covers both) — ranking must treat it as own. → Task 1, check `"an .s7i buffer's own record of a stdlib name ranks first"`.
2. **A truncated buffer mid-typing**, where every declaration failed, has no own records — every answer must be exactly what it is today, not an empty list or a shifted cap. The input that exercises it is a `syms` array with no `BUFFER_FILE` record at all: Task 2's control `the cap still totals MAX_LOCATIONS` (21 library records reached the cap in the pre-fix run, so the cap does move when a pass double-counts), plus the existing `locations dedupe and percent-encode` (`tests/features_test.sd7:603`, an all-library fixture) and `unknown token is the empty array` (`:601`).
3. **One name declared twice in the same buffer** — the *first* own record's class and line win, as they already do for fresh names. → Task 4, existing check `"a name declared twice takes the first declaration's class"` (`tests/semantic_tokens_test.sd7:71`) must stay green.
4. **Cap arithmetic across a pass boundary**: two passes must total exactly the cap, never cap × 2, and the running count must cross the boundary as `emitSyms` already does. → Task 2 checks `"the document's own overload is the first definition"` and `"the cap still totals MAX_LOCATIONS"`.
5. **The premise is an interpreter property, not a constant**: if a future `s7` yields buffer records first, nothing may break. Every new assertion states the *answer* ("the buffer's own location is first"), never the array index of a library record. → Task 1's wire check and Task 2's unit checks.

---

## Task 1: Rank the analysed document's own records first

**Files:**
- Modify: `src/analysis.sd7:272-312` (`collectSyms`)
- Test: `tests/analysis_test.sd7` (insert after `:260`, and after `:338`)
- Test: `tests/transcript.py` (a new check group after the `definition` checks at `:246-260`)

**Interfaces:**
- Consumes: `analysis.isBufferFile` (`:53`), `analysis.BUFFER_FILE` (`:45`), the loop-carried `rec` in `collectSyms`, and the existing dedupe hash `seen` keyed `name <& "|" <& file <& "|" <& str(line1)`.
- Produces: a contract on `analyzeAll(...).syms` — *every record for which `isBufferFile(rec.file, docPath)` holds precedes every record for which it does not; relative order inside each group is unchanged.* Consumers in Tasks 2-4 and `lsp_server.sd7` rely on this sentence; it is also what `hoverText` and `signatureHelpResult` rely on through the `shortcut:` note added here. No line number is quoted for `analyzeAll`, because this branch moved it once already and a citation with no gate behind it goes stale silently.

- [ ] **Step 1: Write the failing record-order checks.** In `tests/analysis_test.sd7`, after `:260` (`stdlib writeln is listed with an absolute path`), analyse the buffer fixture — this exact text, proven to analyse with 0 diagnostics through the real server:

```seed7
syms := symsOf("$ include \"seed7_05.s7i\";\n" <&
               "const type: Widget is new struct\n" <&
               "  var integer: size is 0;\n" <&
               "end struct;\n" <&
               "const func integer: length (in Widget: w) is func\n" <&
               "  result\n    var integer: out is 0;\n" <&
               "  begin\n    out := w.size;\n  end func;\n" <&
               "const proc: main is func\n" <&
               "  begin\n    writeln(length(Widget.value));\n  end func;\n",
               dirs, "");
check("the document's own record of a stdlib name ranks first",
      symsNamed(syms, "length")[1].file, BUFFER_FILE);
checkTrue("the library records of that name still follow it",
          startsWith(symsNamed(syms, "length")[2].file, "/"));
```

  `symsNamed` is `tests/analysis_test.sd7:35` and returns matches in array order. `dirs` is `0 times ""` (`:207`); `parseStri` resolves the standard library itself.

- [ ] **Step 2: Write the failing `.s7i` check** (Review Focus 1), after `:344`. Declare `var string: lib2Path is "/tmp/seed7_lsp_probe2.s7i";` beside `libPath` (`:208`), write a second temp library with the same `open(..., "w")` idiom, and assert with the narrowing the file already has (`symsNamed`, `:35`):

```seed7
out := open(lib2Path, "w");
write(out, "const func integer: length (in integer: n) is\n  return n + 1;\n");
close(out);
syms := symsOf(driverFor(lib2Path), dirs, lib2Path);
check("an .s7i buffer's own record of a stdlib name ranks first",
      symsNamed(syms, "length")[1].file, lib2Path);
```

  That file analyses with 0 errors through the driver (measured with `parseStri(driverFor(lib2Path), parseOptions.value, []("."))`). The `.s7i` case is the one that matters here: its own records carry `lib2Path`, not `BUFFER_FILE`, so a ranking written as `file = BUFFER_FILE` would miss them — which is why the predicate is `isBufferFile` and why `AGENTS.md` keeps that rule.

- [ ] **Step 3: Run both suites and confirm they fail for the stated reason.**

Run: `make test-analysis`
Expected: FAIL — `the document's own record of a stdlib name ranks first` reports `got: /home/…/string.s7i` (an absolute path), `expected: STRING`; `an .s7i buffer's own record of a stdlib name ranks first` reports the same kind of absolute path against `lib2Path`. `the library records of that name still follow it` passes — it is a control, not a proof. The suite still prints its graded line (a suite that fails to analyse prints nothing and exits 0 — `AGENTS.md`).

- [ ] **Step 4: Implement the ranking in `collectSyms`.** Keep the single `for obj range objs` pass and the `seen` dedupe exactly as they are; route the surviving record into one of two local arrays and append them to `syms` after the loop, own first. Signatures do not change.

```seed7
  result ... local
    var array symRec: ownAdds is 0 times symRec.value;
    var array symRec: otherAdds is 0 times symRec.value;
  begin
    ... existing pass; at :308 replace `syms &:= rec;' with
      if isBufferFile(rec.file, docPath) then
        ownAdds &:= rec;
      else
        otherAdds &:= rec;
      end if;
    end for;
    syms &:= ownAdds;
    syms &:= otherAdds;
  end func;
```

  Both arrays are appended by value, so the loop-carried `rec` (and the `rec.locals` reset at `:302`) behave as before. Add one line above `collectSyms` stating the contract from *Produces*, because four consumers now read it.

- [ ] **Step 5: Add the two `shortcut:` notes.** One line each, in the style of `AGENTS.md`'s convention: above `hoverText` (`src/features/hover.sd7:12`) and above `signatureHelpResult` (`src/features/signature_help.sd7:64`) — `shortcut: relies on analysis.collectSyms ranking own records first; a caller that builds syms another way shows library overloads first. Upgrade when a consumer needs order-independence.`

- [ ] **Step 6: Add the wire check** (proves the premise against the real interpreter, not a fabricated array). In `tests/transcript.py`, after the `definition` group at `:246-260`, add a session of its own with the builders the file already defines — `initialize()` (`:100`), `opened(uri, text)` (`:78`), `req(rid, method, params)` (`:61`), `pos(uri, line, character)` (`:70`), `shutdown(rid)`, `exit_()`, and `run(frames)` (`:105`):

```python
OWN_RANK = '$ include "seed7_05.s7i";\nconst type: Widget is new struct\n'
OWN_RANK += '  var integer: size is 0;\nend struct;\n'
OWN_RANK += 'const func integer: length (in Widget: w) is func\n  result\n'
OWN_RANK += '    var integer: out is 0;\n  begin\n    out := w.size;\n  end func;\n'
OWN_RANK += 'const proc: main is func\n  begin\n'
OWN_RANK += '    writeln(length(Widget.value));\n  end func;\n'
replies, code, err, junk = run([frame(m) for m in [
    initialize(),
    opened("file:///tmp/tt_ownrank.sd7", OWN_RANK),
    req(61, "textDocument/definition", pos("file:///tmp/tt_ownrank.sd7", 12, 18)),
    shutdown(62), exit_()]])
defs = {r.get("id"): r for r in replies}.get(61, {}).get("result") or []
expect(bool(defs) and defs[0]["uri"] == "file:///tmp/tt_ownrank.sd7",
       "definition on an own overload of a stdlib name lists the buffer first")
expect(junk == 0, "the own-rank session put only frames on stdout")
```

  Line 12 is `    writeln(length(Widget.value));` and character 18 sits one past the `length` token — `wordAt` is left-of-character, so 18 selects it; both were verified against the running server. `run` starts one process per session, so request ids need only be unique inside that reply map. Assert the *answer*, never an index in `syms` (Review Focus 5).

- [ ] **Step 7: Run the full suite.**

Run: `make test`
Expected: 21 graded lines, every one `0 failed`; the three analysis checks and the two transcript checks are present and green (the controls among them were green before the fix), and the totals rise above 1 049.

- [ ] **Step 8: Commit.**

```bash
git add src/analysis.sd7 src/features/hover.sd7 src/features/signature_help.sd7 \
        tests/analysis_test.sd7 tests/transcript.py
git commit -m "Rank the analysed document's own records before the library's

collectSyms appended records in globalObjects order, which is include order, so
a buffer that overloads a stdlib name sat behind every library overload of it.
definition/hover/signatureHelp take the first N, so the user's own declaration
came last or fell off the cap."
```

- [ ] **Step 9: Prove the checks can fail.** Revert the production branch in place — make the append unconditional (`syms &:= rec;`, i.e. delete the `if isBufferFile` split and the two arrays).

Run: `make test-analysis && make transcript`
Expected: FAIL — name the three: `the document's own record of a stdlib name ranks first`, `an .s7i buffer's own record of a stdlib name ranks first`, `definition on an own overload of a stdlib name lists the buffer first`. Then `git checkout -- src/analysis.sd7` and confirm `make test` is green again.

---

## Task 2: Make `definitionResult`'s cap order-independent

**Files:**
- Modify: `src/features/definition.sd7:21-53`
- Test: `tests/features_test.sd7` (fixture beside `ownLastSyms` at `:22-45`; checks in the `definition` block at `:598-648`)

**Interfaces:**
- Consumes: `analysis.isBufferFile` (`src/analysis.sd7:53`), `uris.pathOf` (already included), `MAX_LOCATIONS` (`src/features/definition.sd7:7`), the `seen` dedupe keyed `file <& "|" <& str(line1)`, and `uriCount` (`tests/features_test.sd7:398`).
- Produces: same signature — `definitionResult (in array symRec: syms, in wordRef: word, in string: docUri) is func string`. Behaviour: the document's own locations are emitted before library ones **whatever order `syms` arrives in**, and the answer is still at most `MAX_LOCATIONS` locations.

- [ ] **Step 1: Write the failing checks.** Add the fixture below beside `ownLastSyms` (`tests/features_test.sd7:22-45`) — 21 library records then the buffer's own, i.e. `globalObjects` order, which is exactly the case Task 1's producer fix cannot help once the array is fabricated:

```seed7
const func array symRec: libFirstLength is func
  result
    var array symRec: out is 0 times symRec.value;
  local
    var symRec: rec is symRec.value;
    var integer: k is 0;
  begin
    rec.cat := "ACTOBJECT"; rec.ty := "func integer";
    for k range 1 to 21 do
      rec.name := "length";
      rec.file := "/home/user/seed7/lib/string.s7i";
      rec.line1 := k;
      rec.sign := "const func integer: length";
      out &:= rec;
    end for;
    rec.name := "length"; rec.cat := "ACTOBJECT"; rec.ty := "func integer";
    rec.file := BUFFER_FILE; rec.line1 := 5;
    rec.sign := "const func integer: length (Widget: w)";
    out &:= rec;
  end func;
```

  Then, in the `definition` block (`:598-648`), set `word.word := "length"` and assert the three checks below. Do **not** pin the whole 20-location string: which library lines a fixture invents is not the point, and a pinned 20-element string would have to be rewritten every time the fixture grows.

```seed7
checkTrue("the document's own overload is the first definition",
          startsWith(definitionResult(libFirstLength(), word, "file:///tmp/tt_own.sd7"),
                     "[{\"uri\":\"file:///tmp/tt_own.sd7\""));
checkTrue("the own declaration survives the cap",
          pos(definitionResult(libFirstLength(), word, "file:///tmp/tt_own.sd7"),
              "tt_own.sd7") <> 0);
check("the cap still totals MAX_LOCATIONS",
      str(uriCount(definitionResult(libFirstLength(), word, "file:///tmp/tt_own.sd7"))), "20");
```

  The third is the control (Review Focus 2 and 4): it must pass before and after.

- [ ] **Step 2: Run the suite and confirm it fails.**

Run: `make test-features`
Expected: FAIL — both own checks report `FALSE`; the `MAX_LOCATIONS` control passes. If the first two pass, the fixture is not in library-first order and the check is decorative — fix the fixture before continuing.

- [ ] **Step 3: Implement two passes.** Extract the record loop body into one helper and call it twice, own pass first, exactly as `completion.sd7:102-103` calls `emitSyms` twice with a `wantOwn` boolean. The helper takes `inout jsonWriter`, `inout locSeen`, the running `emitted` count, `syms`, the word, the document's uri and path, and `wantOwn`, and returns the new count; it selects records with `isBufferFile(syms[i].file, docPath) = wantOwn`. Do **not** copy the loop body into two loops — a duplicated logic block is a review defect, and one body called twice is the shape this codebase already uses. Define the helper above `definitionResult` (Seed7 cannot call a function defined later in the file). Keep the `BUFFER_FILE` → `docUri` rewrite inside the helper unchanged — it is what makes the own location openable.

- [ ] **Step 4: Run the suite.**

Run: `make test-features` then `make test`
Expected: all three new checks pass; `locations dedupe and percent-encode`, `a declaration from the buffer itself resolves to the buffer's uri` and `locations are capped at MAX_LOCATIONS` (`:603`, `:615`, `:647`) stay green — those three are the equivalence net, and the first of them is the one that catches a pass emitting a record twice.

- [ ] **Step 5: Commit**, then **Step 6: prove it** — collapse the two passes into one list-order pass.

Run: `make test-features`
Expected: FAIL — `the document's own overload is the first definition` and `the own declaration survives the cap`. Then `git checkout -- src/features/definition.sd7`.

---

## Task 3: One buffer-trust predicate, three call sites

**Files:**
- Modify: `src/features/document_symbol.sd7:22`, `src/features/semantic_tokens.sd7:49`, `src/features/completion.sd7:68`
- Test: no new checks; the existing suites are the net.
- Modify: `src/features/hover.sd7:29` — NOT a substitution: see the note in Step 1.

**Interfaces:**
- Consumes: `analysis.isBufferFile(fname, docPath)`.
- Produces: three fewer copies of the rule, plus a note that `hover.sd7`'s BUFFER_FILE test is a different question. No signature changes; no behaviour changes.

- [ ] **Step 1: Replace each inlined test** with `isBufferFile(syms[i].file, <the path the function already takes>)` — `path` in `documentSymbolResult`, `ownPath` in `buildClasses`, `ownFile` in `emitSyms`. All three files already include `analysis.sd7`, so no include list changes (check with `make test-graph`, which fails on a changed include set).

  `hover.sd7:29` is **not** one of these copies and must keep its narrower test. It asks `syms[i].file = BUFFER_FILE` to decide *where to read the `(** … *)` prose from* — the buffer's own text, or the file on disk — which is a different question from "did this document declare it", and `hoverText` has no `docPath` to pass. Rewriting it as `isBufferFile` would change behaviour for an open `.s7i` buffer (prose would come from the buffer instead of from disk, while R-F10 still analyses that buffer from disk). Add one comment line at `hover.sd7:29` naming the deliberate narrowness and the fact that `isBufferFile` is wider, so a future widening cannot silently diverge.

- [ ] **Step 2: Run the full suite and compare every count.**

Run: `make test`
Expected: same totals as after Task 2, all `0 failed`. A changed total means a check was edited here — it must not be.

- [ ] **Step 3: Commit** with the message stating plainly that this task adds no check: *"Use analysis.isBufferFile at the three consumers that inlined it — no behaviour change, so no new check; the existing documentSymbol/semantic_tokens/features suites are the net."*

- [ ] **Step 4: Prove the predicate is load-bearing anyway.** Mutate `isBufferFile` to drop the second arm (`out := fname = BUFFER_FILE;`) — the `.s7i` case.

Run: `make test-features && make test-analysis`
Expected: FAIL — the outline and scope checks that pass a real `docPath` go red (`the document's own path fills the scope`, `tests/analysis_test.sd7:339`). Restore with `git checkout -- src/analysis.sd7`.

---

## Task 4: Make `buildClasses` prefer the document's own record

**Files:**
- Modify: `src/features/semantic_tokens.sd7:35-58` (the `wantOwn` two passes)
- Test: `tests/semantic_tokens_test.sd7` (fixtures beside `twoWriteln` at `:26`, checks beside `:71`)
- Modify: `src/analysis.sd7:51-52` — one comment line: the predicate's own doc sentence says "the collectSyms guard below and occurrences' binding rows **both** ask through this one function", which under-reports its reach now that eight sites in six files do. Replace with a sentence that names no count and no file: every consumer that asks "did this document declare it" asks through this one function. (Carried in from the Task 3 review as a controller ruling; it is a comment, so no check moves, but `docs/PROJECT_GRAPH.md`'s `analysis.sd7` line count changes and must be regenerated with the rest.)
- Modify: `docs/seed7-cli.md:394` (suite totals)

**Interfaces:**
- Consumes: `isBufferFile` (from Task 3), the three tables `classes` / `declLines` / `fromLib`, and `STMOD_DECLARATION` / `STMOD_DEFAULT_LIBRARY` (`src/features/kinds.sd7:20-23`).
- Produces: unchanged signature `buildClasses (in array symRec: syms, in string: ownPath, inout classHash: classes, inout classHash: declLines, inout classHash: fromLib)`; for every name the tables hold **the buffer's own record if one exists**, else the first library record. Order of `syms` no longer decides the answer.

- [ ] **Step 1: Write the failing check.** New fixture — the order `globalObjects` really yields, and the own record is a data name so the tokenType itself moves, not just the modifiers:

```seed7
const func array symRec: libThenOwn is func
  result
    var array symRec: out is 0 times symRec.value;
  local
    var symRec: rec is symRec.value;
  begin
    rec.name := "length";
    rec.cat := "ACTOBJECT"; rec.ty := "func integer";
    rec.file := "/home/user/seed7/lib/string.s7i"; rec.line1 := 336;
    out &:= rec;
    rec.cat := "VAROBJECT"; rec.ty := "integer";
    rec.file := BUFFER_FILE; rec.line1 := 1;
    out &:= rec;
  end func;
```

  Then, beside `:71` in `main`, the check itself:

```seed7
check("an own declaration of a library name keeps its own class and marker",
      tokensIn(docOf("length"), libThenOwn, "/p/a.sd7", 0, 0),
      "{\"data\":[0,0,6,5,1]}");
```

  Expected-by-construction: tokenType `variable` (legend index 5) and tokenModifiers `declaration` (bit 0) only. `A Seed7 routine name and a data name live in different overload spaces` — that measurement is `src/features/rename.sd7:88-97`, so a `var` and a `func` both named `length` is a legal fixture, and it makes the tokenType itself move rather than only the modifiers.

- [ ] **Step 1b: Write the second failing check — the `docPath` arm of the rule.** The Task 3 review verified that the `file = docPath` arm of `isBufferFile` is discriminated for `documentSymbolResult`, `collectSyms` and occurrences, but NOT for `buildClasses` or `emitSyms`. Since this task makes `buildClasses` depend on that arm, it must pin it here: the same fixture, except the own record carries the document's path rather than `BUFFER_FILE`, which is exactly what an open `.s7i` produces.

```seed7
const func array symRec: pathThenOwn is func
  result
    var array symRec: out is 0 times symRec.value;
  local
    var symRec: rec is symRec.value;
  begin
    rec.name := "length";
    rec.cat := "ACTOBJECT"; rec.ty := "func integer";
    rec.file := "/home/user/seed7/lib/string.s7i"; rec.line1 := 336;
    out &:= rec;
    rec.cat := "VAROBJECT"; rec.ty := "integer";
    rec.file := "/p/a.sd7"; rec.line1 := 1;
    out &:= rec;
  end func;

check("an .s7i buffer's own declaration wins the class tables too",
      tokensIn(docOf("length"), pathThenOwn, "/p/a.sd7", 0, 0),
      "{\"data\":[0,0,6,5,1]}");
```

  Both checks fail before Step 3 for the same reason and both must pass after it. `emitSyms`' identical gap is NOT this task's: a mixed own/library set there would re-derive pinned outputs, so it goes to the final review as a deferred finding.

- [ ] **Step 2: Run and confirm it fails.**

Run: `make test-semantic_tokens`
Expected: FAIL with `got: {"data":[0,0,6,3,2]}` — the library record's `function` and `defaultLibrary`. If it passes, the fixture is not library-first and the check is decorative.

- [ ] **Step 3: Implement two passes** by calling the existing fill body twice with a `wantOwn` boolean, own pass first — the `emitSyms` shape, one body and two calls (`completion.sd7:102-103`), never two copies of the loop. Keep `if not (syms[i].name in classes)` as the single guard so the own record wins and a name with no own record keeps today's answer, and select with `isBufferFile(syms[i].file, ownPath) = wantOwn`. No copy, no new array. Update the comment at `:32-33` to name the rule (`isBufferFile`) rather than "first declaration wins".

- [ ] **Step 4: Run the full suite.**

Run: `make test`
Expected: all green; `a name declared twice takes the first declaration's class` (`:71`) and `modifiers and the cross-line delta rule, in one array` (`:66`, the `oneWriteln` library-only case) stay green — the first is Review Focus 3, the second proves `defaultLibrary` still fires when no own record exists.

- [ ] **Step 5: Restate the figure the branch made stale.** Read the real totals from a fresh run; never compute a sum by hand and never predict it:

```
make test 2>&1 | grep -E '^[a-z0-9_]+: [0-9]+ checks, [0-9]+ failed$' > /tmp/totals.txt
awk '{s += $2} END{print NR" suites, "s" checks"}' /tmp/totals.txt
grep -E '^(scan|features|lsp_server|transcript):' /tmp/totals.txt
```

  Then rewrite `docs/seed7-cli.md:394`'s row to `21 suites, <sum> checks: scan <n>, features <n>, lsp_server <n>, transcript <n>` and leave its command column `make test`. Add one clause saying the previous row was measured 2026-10-21 on this suite set before these checks existed. The `342` and `Seed7Home` rows above it (`:391-393`) are a different finding and are **not** to be touched here.

- [ ] **Step 6: Commit** Tasks 4's code and docs together, message naming the measured `got:` value from Step 2 as the reason the check was written first.

- [ ] **Step 7: Prove the checks.** Three mutations, each with the named checks that go FAIL, restored per file:
  1. Collapse the two passes into one list-order call — both new checks must redden.
  2. Drop the `docPath` arm at the selection site (`isBufferFile(syms[i].file, ownPath)` → `syms[i].file = BUFFER_FILE`) — `an .s7i buffer's own declaration wins the class tables too` must redden while the `BUFFER_FILE` check stays green. That difference is the proof the second check is not a copy of the first.
  3. Reverse the own pass's iteration (`for i range length(syms) downto 1`) — the pre-existing `a name declared twice takes the first declaration's class` must redden. Task 1's lesson is that within-group order is already user-visible here, and that check is the only thing pinning it.

Run: `make test-semantic_tokens` for each, then `git checkout -- src/features/semantic_tokens.sd7` and confirm `make test` green again.

---

## Definition of done

- `make test` green: 21 suites, every graded line `0 failed`, totals restated in `docs/seed7-cli.md:394`.
- `make test-graph` green (no include added; `progs.s7i` still appears once).
- `git status --porcelain -uall` empty in the worktree — no `profile_out`, no compiled binary beside a source (the suites build nothing; if you profiled, run `make clean-build`).
- Twelve new checks, taken per suite from `make test`: Task 1 six (`analysis` 46 → 50, `transcript` 192 → 194), Task 2 three (`features` 186 → 189), Task 3 none, Task 4 two (`semantic_tokens` 8 → 10), the final fix wave one (`features` 186 + 3 + 1 = 190; the fix wave also *replaced* the decorative `the own declaration survives the cap`, which moves no total). Each task check was red-for-the-stated-reason before its implementation and each has a named mutation that reddens it — except the fix wave's two, written against code that already worked, which are after-the-fact nets proven by mutation alone (collapse/invert, and the `BUFFER_FILE`-only arm). The controls (`the library records of that name still follow it`, `the cap still totals MAX_LOCATIONS`, `a name declared twice takes the first declaration's class`, `locations dedupe and percent-encode`) pass before and after, which is what makes them controls rather than proofs. Branch totals after the fix wave: 21 graded lines, 1 049 → 1 061 checks. That sentence read "nine", then "Ten … (5 in Task 1 …) … 1 060": the split summed to 10 against a measured 11, so the count is written as an addition a reader can check.
- `AGENTS.md` untouched. If you judge "own records are ranked first at every truncation point" a rule a later agent must not undo, that is an `AGENTS.md` edit plus a `tools/agents_required.txt` append with the gate's own R26 admission test — a separate change, not part of this plan.
