# M5 Review Burn-down Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pay the eight obligations the whole-branch review of M5 left open — two passes a request cannot justify, one dead re-walk, one false claim about operators, three §9 fixtures that were asked for and never written, three recorded figures with no command behind them, and two §12 rulings that live only in commit messages.

**Architecture:** No new modules. Every change lands in the four files M5's review branch already touched: `src/occurrences.sd7` (the index, the binding, the scope), `src/features/{references,prepare_rename,rename}.sd7` (the three readers), and the design document, which is the authority and must agree with the code by the end. The work is ordered so the document corrections come *after* the code they describe.

**Tech Stack:** Seed7 (`s7` / `s7c` 5.4.10) only; LSP 3.18 over stdio; Python 3 for the wire harness; bash for the corpus gate.

**Spec:** `docs/superpowers/specs/2026-10-12-seed7-lsp-m5-references-and-rename-design.md` — §3 (the pass claim), §4 row 4, §6 (the refusal list), §9 (the check list), §11.12, §11.14, §12. Sections 11/12 of that document are where measurements and rulings belong, and two tasks here exist only to write them down. `AGENTS.md` is the standing contract; its invariants 1–7 and the *Every change* rules bind every task.

**Branch and worktree:** continue on `m5-review-fixes` in `.worktrees/m5-review-fixes`, which already carries the four commits `d39ac9d`, `1316d4a`, `fa8bf93`, `3fef4f6`. Do not branch again and do not push without your human partner's word.

## Global Constraints

* **Red first.** Write the check, run it, see it fail for the reason you named, then implement. `make test` before and after every task. A check added to code that already works must be labelled in the commit and proved by mutation.
* **Prove by mutation after committing**, and stage or commit before reverting: `git checkout -- <file>` restores from the index, which silently discards uncommitted work. One file per revert, never `git checkout -- .`.
* Before demanding a mutant, check the mutant is not **semantically identical** (`if n > MAX` vs `if n >= MAX` where the assignment is a no-op at `MAX`). Where no input can separate the two paths, say so out loud and justify the change with a measurement instead of a check.
* Only `src/analysis.sd7` imports `progs.s7i`. Only `src/doc_store.sd7` converts LSP positions to offsets. Only `src/utf8bytes.sd7` declares code-point rules — widths *and* the surrogate bounds. Only `src/transport.sd7` emits an outbound byte count. Only `src/*.sd7` and `src/features/*.sd7` build LSP shapes; `occurrences.sd7` returns Seed7-shaped data and knows nothing about LSP. `renameDecision` is the only rename refusal predicate; `inScope`/`inScopeLine` are the only place scope is applied. `grep -rn 'addStr(w, str(' --include='*.sd7' src/` stays empty.
* Never let an exception reach stdout — it corrupts the protocol channel. A test suite that prints a lone surrogate raises `RANGE_ERROR` at `fil_rtl.c(2912)`; assert on `pos()`/`length()` for anything that may hold one.
* **No performance number reaches a file without its command.** `s7c -p -O2 -l src <probe>`, run the binary, read `profile_out`. `-p` measures; `-O2` optimises; `s7 -p` is a different flag (trace protocol). Compiled probes leave a binary beside the source and `profile_out` in the cwd — probes live in `/tmp`, and `git status --porcelain -uall` must be empty at the end of the task.
* Seed7 traps that bite this plan specifically: declare before use (a helper sits above its caller); `in`/`not in` have no array overload, so `scopeIndexOf` spells its scan out; a slice whose low bound exceeds its high bound is the empty string, so a bounds guard can look unreachable and be merely harmless; `<&` between two comparisons parses as a comparison; a loop-carried record must re-stamp every field it owns; `str(ch)` works, `string(ch)` and `"" & ch` do not; `writeln` takes exactly one argument.
* The suite is graded on its own line: `make test` must end with every suite printing `N checks, 0 failed`, and `sh tools/corpus_scan.sh` must print `CORPUS … misses=0`. Both are gates, not suggestions.
* Commit-message voice: lower-case, states the finding, names the measured pre-state. This branch's history is the template (`git log master..HEAD --oneline`).

## Review Focus

The failure modes the design implies that no single task's happy path would catch. Each line gets its test in the task that owns the code.

1. **A `box.` that ends a line and a `counter` that starts the next** — the field test is line-granular by decision. After Task 1 the answer must still be "not a field", because a rename that *refuses* on a shape the scanner cannot see is the failure the shortcut comment exists to permit, not one to widen. (Task 1.)
2. **The cursor on an operator the user declared** (`<+`) — indexed, referenceable, and refused for rename. Expected: `null` with the reason naming it as not-a-name, never a half-edit and never an error frame. (Task 4.)
3. **An unbound name that appears both bare and after a dot on one line** — Task 1 replaces a line-wide test with a cursor-token test, so the two must be pinned separately or the change is untested in exactly the case it alters. (Task 1.)
4. **A capped document being renamed** (2 001 occurrences of one name) — the refusal arms and the truncation disclosure must survive the pass-shaving, because `capped` is read off the array the caller hands in, not recomputed. (Tasks 2, 3.)
5. **A figure a reader cannot reproduce** — three numbers currently sit in files with no command beside them, and one of them (`40 ms per full-document pass`) is cited as the basis for §3's pass claim. Expected: a command and a table, or the number is gone. (Task 6.)

---

### Task 1: The cursor's own record, so field detection costs no second walk

**Files:**
- Modify: `src/occurrences.sd7` (`dotSelected` at :224 is deleted; `resolveBinding` signature at :270 and its row 4 at :382)
- Modify: `src/features/prepare_rename.sd7` (`cursorName` at :60-73 becomes a call; :162 passes the slot)
- Modify: `src/features/references.sd7:72-74` (pass the slot)
- Test: `tests/occurrences_test.sd7`, `tests/features_test.sd7`

**Interfaces:**
- Consumes: `occurrence.dotPrev` (already produced by `occurrencesOf`, `d39ac9d`), `wordRef.line1` / `wordRef.character1` (from `doc_store.wordAt`).
- Produces: `const func integer: occurrenceAt (in array occurrence: oc, in integer: line0, in integer: col16) → integer` — the 1-based index of the record that IS the cursor's token, 0 when the cursor is not on an indexable **name**. The `kind = TK_NAME` test from `cursorName` moves into it unchanged: operators are found by neither.
- Produces: `resolveBinding (…, in string: docPath, in integer: slot)` — one new trailing parameter. Row 4's third answer becomes `slot <> 0 and oc[slot].dotPrev` instead of `dotSelected(text, name, line0)`.

Why the shape: `dotSelected` walks the whole document — measured at 20.7 ms of a 66 ms request on `lib/shiftjis.s7i` (375 KB, 3 634 lines) — to ask a question the caller already knows the answer to, because it holds the cursor's record. The new form is also *more* precise: today a bare `pix` on a line that also contains `box.pix` is labelled `field` for the bare token.

- [ ] **Step 1: Write the failing tests — the two shapes separately.** In `tests/occurrences_test.sd7`, next to the phantom-region checks (`:427-440`), using a NEW helper beside `bind` (`:65`) — `bind` is called 23 times in this suite and Seed7 has no default arguments, so giving `bind` an eighth parameter means 23 mechanical edits for no added coverage. Add `bindAt` with the slot and leave `bind` calling it with `0`; that keeps every existing check untouched:

```seed7
    text := "    pix := 1;\n  box.pix := 2;\n";
    check("the bare pix, on a line that also holds a field access, is not labelled field",
          str(bind(text, noSyms, "pix", 0, 1, DOC, 1).owner = "field"), "FALSE");
    check("while the one after the dot is",
          str(bind(text, noSyms, "pix", 1, 1, DOC, 3).owner), "field");
```

  Measured on that text with the shipped scanner: `occurrencesOf(text, "pix")` answers TWO records — slot 1 at `line0=0 col16=4 dotPrev=FALSE` (the bare `pix`) and slot 2 at `line0=1 col16=6 dotPrev=TRUE` (the one after `box.`). `box` is not a record, because the pass keeps only tokens equal to the name. The slot arguments above are therefore 1 and 2; `at(oc, i)` prints them if you want to re-verify.

- [ ] **Step 2: Run them to verify they fail for the reason you claim.** Run: `s7 -q -l src tests/occurrences_test.sd7`. Expected first: **no `N checks, 0 failed` line at all**, because an 8-argument `resolveBinding` does not match a 7-argument one — `make test-occurrences` grades that FAIL, which is a red about the interface, not the behaviour. To get the behaviour red, re-run the first check against the CURRENT signature (drop the trailing `1`): expected FAIL `... = "field"` got `TRUE`, which is the false label this task removes. Both runs go in the commit.

- [ ] **Step 3: Move `cursorName` into `occurrences.sd7` as `occurrenceAt`** with the signature above — same early-exit scan (`if out = 0 and …`), same `kind = TK_NAME` gate, `line0`/`col16` taken as parameters instead of unwrapped from `wordRef` so the index module keeps knowing nothing about client records. Delete `cursorName` from `prepare_rename.sd7` and call `occurrenceAt(out.oc, pred(word.line1), word.character1)` where it used to compute `out.slot`.
- [ ] **Step 4: Add the trailing `slot` parameter to `resolveBinding`** and replace row 4's `elsif dotSelected(text, name, line0) then` with `elsif slot <> 0 and oc[slot].dotPrev then`. Delete `dotSelected`, and take its comment with it — but the comment is not only about that function, so two facts must survive the deletion:
  * **§11.10's measurement** ("struct fields have no declaration source: `globalObjects` reports the struct and never its fields, and `structToList` raises `RANGE_ERROR`") moves to the `binding` struct's `owner` field note, where the `field` answer is explained. Losing it would lose the reason row 4 exists.
  * **the line-granular limit** is already stated on `occurrence.dotPrev` (`:33-35`), whose comment currently points at "dotSelected's shortcut" — re-point it at `binding.scopeUncertain` or state it standalone, because after this step the sentence names a function that no longer exists. Grep for `dotSelected` across `src/` and `docs/` and leave no dangling reference; the `binding` struct's `owner` comment at `:96-100` is one such reader.
- [ ] **Step 5: Update every caller** to pass the slot: `references.sd7:72-74` computes `slot := occurrenceAt(oc, pred(word.line1), word.character1)` and passes it; `prepare_rename.sd7:162` passes `out.slot`. `features_test.sd7:809,814` and `occurrences_test.sd7:71,313` gain the extra argument — `0` where the test is not on a token, the literal slot where it is.
- [ ] **Step 6: Run to green.** Run: `make test`. Expected: 19 suites, `0 failed`. `wire` stays 180; if a wire check moves, say which in the commit.
- [ ] **Step 7: Commit, then prove both legs by mutation.** Stage first (`git add -A`), then revert per file:
  * `slot := 0` at the two feature call sites — Step 1's "while the one after the dot is" check must go FAIL.
  * `one.dotPrev := FALSE` in `occurrencesOf` — Step 1's field check **and** the `features_test.sd7` refusals (`a field access inside the scope refuses prepareRename`, `references still lists every token of this spelling`) must go FAIL together. `d39ac9d` ran this mutant once; run it again because this task moves the flag's only other reader.

### Task 1b: One cursor resolution, so the two readers cannot drift

**Files:**
- Modify: `src/occurrences.sd7` (new `cursorBinding`), `src/features/references.sd7:72-74`, `src/features/prepare_rename.sd7:143-163`
- Test: `tests/features_test.sd7` (existing checks only — this task adds no behaviour)

**Interfaces:**
- Consumes: `occurrencesOf`, `occurrenceAt` (Task 1), `resolveBinding` (Task 1's signature), `doc_store.lineCount`, `uris.pathOf`.
- Produces: `cursorRefs` (`oc`, `slot`, `b`) and `cursorAt (text, syms, name, line0, col16, lastLine, docPath) → cursorRefs` — the triple from ONE `occurrencesOf` pass and ONE `resolveBinding`, taken by both `references.sd7` and `prepare_rename.sd7` instead of each assembling it. The record type lives in `occurrences.sd7` and carries no LSP shape (invariant 4). Signature as written in Step 1.

This is the review's finding 9: two features assemble the same three calls today, and invariant 6's whole argument is that a rule spelled twice eventually disagrees with itself. `renameCheck` already carries that triple for the rename pair; `references` builds its own copy.

- [ ] **Step 1: Move the assembly.** Add, above `inScope` in `occurrences.sd7`:

```seed7
const type: cursorRefs is new struct
    var array occurrence: oc is 0 times occurrence.value;
    var integer: slot is 0;
    var binding: b is binding.value;
  end struct;

const func cursorRefs: cursorAt (in string: text, in array symRec: syms, in string: name,
                                 in integer: line0, in integer: col16, in integer: lastLine,
                                 in string: docPath) is func
```

  Its body is the three calls the two features write today, in the same order: `occurrencesOf`, `occurrenceAt`, `resolveBinding` with the slot it just found. The parameters are primitives, NOT a `wordRef`, because `occurrences.sd7` must go on not including `doc_store.sd7` (invariant 2) — each feature converts its own word. `renameCheck` keeps its own `oc`/`slot`/`b` fields and copies them from the returned `cursorRefs`; do not collapse the two records. Ruling, so a reviewer does not spend a round on it: `renameCheck` exists to carry a *refusal* (`refused`, `reason`) out of the one predicate (invariant 6, R45), and `cursorRefs` exists to carry an *assembly* — merging them would put the refusal decision inside the index module. `references.sd7` stops assembling. No expectation changes anywhere in the suites — that IS the requirement.
- [ ] **Step 2: Run to green.** `make test`; expected: counts identical to Task 1's end state (features 162 + Task 4's later additions, wire 180, 0 failed). If any answer moved, the extraction changed semantics — stop and report which.
- [ ] **Step 3: Prove the seam holds.** Mutate the new function so `capped` is recomputed from the text instead of the array (`out.b.capped := length(text) > ...`) and require that `capped follows the array handed in, not the text` and `a capped document is refused even when the cursor is listed` go FAIL. That is the check that keeps a future caller from quietly re-passing the document.
- [ ] **Step 4: Commit.**

### Task 2: No region scan for a name the buffer does not mention

**Files:**
- Modify: `src/occurrences.sd7:282-285` (`regions := blockRegions(text, lastLine)`)
- Test: `tests/occurrences_test.sd7`

**Interfaces:**
- Consumes: `symRec.file` / `symRec.name` / `symRec.locals` (already read by rows 1 and 2), `isBufferFile` from `analysis.sd7`.
- Produces: `const func boolean: bufferCouldBind (in array symRec: syms, in string: name, in string: docPath) → boolean` — TRUE when some record of this buffer is *named* `name` or carries `name` among its scope entries. Internal to `occurrences.sd7`; no caller outside.

`blockRegions` is 22.1 ms of the same 66 ms request. It exists only so rows 1 and 2 can pair declarations with regions; a gated keyword, a library name and an unbound name never reach those rows, so the scan is paid for nothing.

**One trap in this task, stated because the reasoning is not obvious:** row 1 sets `scopeElsewhere` — the flag row 4 reads to answer `field` without a dot test — and row 4 also runs for a name no buffer record mentions. Gating rows 1-2 is still safe, because `scopeElsewhere` is only ever set when some buffer record carries `name` in its scope entries, which is exactly when `bufferCouldBind` is TRUE and the rows run. Verify that sentence by mutating the guard to `return FALSE` and reading Step 3's expected reds: if a `field` answer goes missing there, the equivalence is wrong and the task must gate only `blockRegions`, not the rows. Skipping is not observable — the same `binding` comes back either way — so this task is justified by measurement and labelled as such, and the check it must not break is named.

- [ ] **Step 1: Write the guard and the pre-scan.** `bufferCouldBind` is a single `for i range 1 to length(syms)` with `isBufferFile(syms[i].file, docPath)` and either `syms[i].name = name` or `scopeIndexOf(syms[i].locals, name) <> 0` — reuse `scopeIndexOf`, do not write a second scan. Rows 1 and 2 then run only when it is TRUE, and `blockRegions` moves inside that branch.
- [ ] **Step 2: Verify nothing changed.** Run: `make test`. Expected: 19 suites, `0 failed`, every suite's count identical to the baseline (features 162, occurrences 75 + whatever Task 1 added, wire 180). If a count moved, Task 1's tests changed it — not this task.
- [ ] **Step 3: Prove the guard is reachable, not decorative.** Mutate `bufferCouldBind` to `return TRUE;` and confirm the suites still pass (they must — that is what "not observable" means); mutate it to `return FALSE;` and require that the `local`/`global` rows go red: expected named reds are `a local's references are its own region only`, `the global loses the shadowing routine's occurrences, with exact columns`, and the Task 1 field checks. Report which checks reddened in the commit; that is the proof this branch asks for. Review Focus 4 is checked in the same run: `a capped document is refused rather than half-edited` and `one more occurrence truncates the list, and says so` must stay GREEN, because `capped` is read off the array handed in and this task must not recompute it.
- [ ] **Step 4: Measure the saving** with the shared probe recipe (Task 6 Step 1) over `shiftjis.s7i` for an unbound name, before and after. Record `usecs / calls / file(line) / name` lines, the command, and the body size in `occurrences.sd7`'s comment beside the branch. If the saving is not visible in the table, revert the task and say so in the commit instead of shipping an unmeasured claim.
- [ ] **Step 5: Commit.**

### Task 3: The binding remembers the record it found

**Files:**
- Modify: `src/occurrences.sd7` (`binding` struct, row 1)
- Modify: `src/features/rename.sd7` (`localOwner` at :92-115 deleted; `collides` at :156)
- Test: `tests/features_test.sd7` (the collision checks at the `R51`/collision block)

**Interfaces:**
- Consumes: row 1's `i` (the routine record) and `scopeIdx`.
- Produces: `binding.ownerSym` — `var integer: ownerSym is 0;`, "the `symRec` index whose scope holds the bound local, 0 unless `owner = \"local\"`". `collides` reads `syms[b.ownerSym]` and `localOwner` is deleted.

`localOwner` re-walks every buffer record and every scope entry to find the record `resolveBinding` had already located. It is ~20 lines plus an O(records × entries) search per rename, and it is a second spelling of "whose local is this".

- [ ] **Step 1: Write the test.** `tests/features_test.sd7` already pins the collisions; add the assertion that makes `ownerSym` load-bearing rather than a copy of a readable fact — the record the binding names must be the routine that owns the local, identified **by name**, never by an index that shifts when a task adds a record above it:

```seed7
    bl := resolveBinding(rtext, rsyms, occurrencesOf(rtext, "counter"), "counter",
                         14, 27, refPath, 0);
    check("the local binding carries the record whose scope holds it",
          syms[bl.ownerSym].name <& "/" <& str(syms[bl.ownerSym].line1), "show/10");
```

  `show/10` is `refsText()`'s routine and its 1-based name line; confirm both halves with a probe and put the probe's output in the commit.

- [ ] **Step 2: Run it, and be honest about which red you got.** Expected: no total line, because `ownerSym` does not exist yet — an interface red. There is no behaviour red available: the field is new, so this check is written after working code, is labelled that way in the commit, and is proved by Step 4's mutant rather than by an earlier failure.

- [ ] **Step 3: Add `ownerSym`, set it in row 1** where `declLine1` is already set, **and delete `localOwner`.** `collides` becomes `owner := b.ownerSym; if owner <> 0 then …`. Keep the "0 is a degradation, not a raise" behaviour: an unset `ownerSym` means no collision test, which is what `localOwner` returned 0 for.
- [ ] **Step 4: Run to green and mutate.** `make test` → `0 failed`. Mutant: `out.ownerSym := 0;` in row 1 — expected reds: the four collision checks (`a local collides with its own routine's parameter`, `… the routine's name`, and the two `Widget`/`show` global cases that must stay *green* to prove the branch is not simply always-refusing). Revert per file.
- [ ] **Step 5: Commit.**

### Task 4: Operators are indexed and referenceable, and not renameable — said, then pinned

**Files:**
- Modify: `tests/occurrences_test.sd7:516` (the comment `an operator run is indexable, so rename can reach a user-declared operator name`)
- Modify: `docs/superpowers/specs/2026-10-12-…-design.md` §3 and §6 (one sentence each)
- Test: `tests/features_test.sd7` (rename section)

**Interfaces:**
- Consumes: `cursorName`/`occurrenceAt`'s `TK_NAME` gate (Task 1), `newNameProblem` (unchanged).
- Produces: no new signature. The decision recorded is that M5 renames *names*: a `TK_OP` cursor is refused and an operator `newName` is `-32602` `invalid`, because `newNameProblem` requires an identifier and the two halves must agree in one direction.

- [ ] **Step 1: Write the tests.** In `tests/features_test.sd7`, on the cursor the suite already proves answers `+` — `wordAt(rdoc, 14, 20)`, the operator reference check at line ~704:

```seed7
    pc := prepareRenameAnswer(rdoc, rsyms, wordAt(rdoc, 14, 20), refUri, TRUE);
    check("an operator cursor is refused by prepareRename", str(pc.refused), "TRUE");
    check("and the reason is the not-a-name arm, which speaks truly now",
          pc.why, "prepareRename: + is not a name");
    rn := renameResult(rdoc, rsyms, wordAt(rdoc, 14, 10), refUri, "<+>", TRUE);
    check("an operator NEW name is a rejection, not a refusal", rn.error, "invalid");
```

  Run: `s7 -q -l src tests/features_test.sd7`. Expected: **all three PASS on sight** — the behaviour exists and the claim did not. Label them written-after-code in the commit, and prove them with Step 3's mutants; this task buys a statement its tests can defend, not a behaviour it reddens into existence.

- [ ] **Step 2: Fix the two claims.** Replace the `occurrences_test.sd7:516` comment with one that says what is measured: `# an operator run is indexable, so references finds it; rename refuses it (Task 4)`. In the design, §3's index row keeps `TK_NAME or TK_OP` and §6's refusal list gains the line naming operators as refused-with-a-reason rather than silently unreachable.
- [ ] **Step 3: Prove the three checks can fail.** Mutants, one at a time, each reverted per file after staging: (a) drop `kind = TK_NAME` from `occurrenceAt` → the two refusal checks must go red; (b) relax `newNameProblem`'s `allNameChars` → the third check reds. If a mutant survives, the check is decorative: report it and delete the check rather than adding another.
- [ ] **Step 4: Run `make test`, commit.**

### Task 5: The three §9 fixtures that were asked for and never written

**Files:**
- Test: `tests/occurrences_test.sd7` (three new checks), plus `tests/programs/binding.sd7` (one extra struct sharing a field name)
- Modify only if a check finds a bug: `src/occurrences.sd7` / `src/features/*` (say so in the commit)

**Interfaces:**
- Consumes: `occurrencesOf`, `resolveBinding` (Task 1's slot), `inScope`.
- Produces: fixtures. The design §9's list is the requirement; three of its lines have no text in any suite.

§9 asks: nothing for `count` inside a `prg/calc7.sd7`-style continuation string; nothing inside `{'"'}` in `lib/chartype.s7i`; a field access `w.pix` where `pix` exists in **two** structs in one file. The first two are the reason `hiddenKind` skipping exists; the third is §12.2's "field names repeat across structs" claim, which no input has yet touched.

- [ ] **Step 1: Continuation string.** `prg/calc7.sd7:57-58` is the shape §9 means: a literal continued across a line break by a backslash AT THE END OF THE LINE inside the quotes (`parseStri("` then a `\` then the next line). The fixture a test must therefore build is a Seed7 string whose contents are a real backslash followed by a real newline — `"x := \"abc \\\n  count\";\n"`. Measured on a probe against the shipped scanner: that text is `x := "abc ` + backslash + newline + `  count";` and `occurrencesOf(t1, "count")` answers **0**, with the control `"x := count;\n"` answering **1**. Use those two numbers as the expectations. The escape spelling above is the one that PARSES (`\"` for the quote, `\\` for one backslash, `\n` for the newline) — the first draft of this fixture used `"\" <& chr(92)` at statement level and Seed7 refused the file with "String literal exceeds source line", so build the fixture with escapes, not with concatenation.
- [ ] **Step 2: `{'"'}`.** `lib/chartype.s7i:45` is the real instance: `const set of char: double_quotation_char is {'"'};`. Measured: `occurrencesOf("const set of char: q is {'\"'};\ncount := 1;\n", "count")` answers **1** — the char literal is hidden and what follows is code. Use that as the expectation. The failure this pins is a scanner that treats the quote char literal as opening a string and swallows the rest, which would answer `0` and silently un-index every name after it. The `{'"'}` spelling parses and was measured as above; `{'\42;'}` is the same character numerically and is the fallback if the quote form ever stops parsing.
- [ ] **Step 3: Two structs, one field name.** Add a second struct to `tests/programs/binding.sd7` (or a fresh inline fixture) declaring `pix` where one already declares it, with `a.pix` and `b.pix` uses in a routine that also holds a local `pix`. Pin three things: `references` answers every same-spelled token **and** the disclosure sentence (`b.resolved` TRUE + field access ⇒ the new `why`), `prepareRename` refuses, and `rename` answers `null` with `error` empty. Expected before you run it, from §12.2's answer: the read over-includes across both structs — there is no machine here to separate them, and the design says so.
- [ ] **Step 4: Run `make test`.** If any check goes red in a way that is a real defect rather than a wrong expectation, stop and report it with the input, the expected value and the got value before changing production code — do not "fix" an expectation to match the bug.
- [ ] **Step 5: Update §9** of the design to mark the three lines pinned (name the suite and the check title), then commit.

### Task 6: Three figures that no command can produce

**Files:**
- Modify: `src/transport.sd7:56-62`, `src/doc_store.sd7:78-83`
- Modify: `docs/superpowers/specs/2026-10-12-…-design.md` §11.14

**Interfaces:**
- Consumes: nothing. Produces: reproduced numbers, or their absence.

The rule is standing on this branch: a figure carries its command and its table. Three do not — `transport.sd7`'s `5.0 ms per read` / `80 ms` / `0.03 ms` / `0.161 s → 0.177 s`, `doc_store.sd7`'s `7.9 s`, and the design's `~40 ms per full-document pass`, which is the figure §3's "one pass per request" rests on. The Standards review flagged all three; the session figure in particular was a wall-clock number, not a profiled one.

- [ ] **Step 1: Write the probe recipe once.** A `/tmp` file that builds the input, calls the function N times, and prints a sentinel *before* any payload is counted (a probe whose entry point never ran reports a result it did not compute — the sentinel is the guard). Pattern:

```seed7
    body := buildText(34319);           # print chars= so the sentinel proves the run
    for k range 1 to 50 do
      sink := readFrameBody(source, n); # or lspRangeUnits(doc, …) / occurrencesOf(text, name)
    end for;
    writeln("sentinel chars=" <& str(length(sink)));
```
  Then: `s7c -p -O2 -l src <probe>`, run it, read `profile_out` (`usecs  calls  file(line)  name`).
- [ ] **Step 2: `readFrameBody`.** Measure the chunked loop against one-character reads on the 34 319-byte ASCII frame, and **count the passes** (that part is structural, not timed: `37 passes` is derivable from `remaining div 4`). Replace the µs figures with the measured ones plus the command; delete the `0.161 s → 0.177 s` session figure — a whole-session wall clock is dominated by process start-up and cannot be attributed to this loop. If the re-measured numbers do not support the comment's claim that chunking pays, say what the table shows and rewrite the claim.
- [ ] **Step 3: `lspRangeUnits`' `7.9 s`.** Reproduce on the capped references answer (2 000 ranges in a 22 000-character document, as the comment states) with the old `utf16Before(start + lineWidth) - utf16Before(start)` form restored in a scratch copy. If it does not reproduce, delete the number and describe the shape (O(document) per range) instead — a figure that cannot be reproduced is worse than none.
- [ ] **Step 4: §11.14's `~40 ms`.** Re-measure through `tools/corpus_scan.sh`'s own walk (profiled build), record the command and the table line in the design, and check it still agrees with `516044 occurrences over 4104 names`. §3's pass claim gets corrected in Task 7 using this number.
- [ ] **Step 5: Clean and commit.** `rm` the binaries and `profile_out`; `git status --porcelain -uall` must be empty. Commit with the tables in the message body, not only in the files.

### Task 7: Say what the code does, in the document that governs it

**Files:**
- Modify: `docs/superpowers/specs/2026-10-12-…-design.md` §3, §6, §12 items 1 and 3
- Modify: `README.md` (only if a refusal the README lists changed)

**Interfaces:**
- Consumes: the outcome of Tasks 1–3 (what a request costs now) and Task 6's measured figures.
- Produces: a design document with no open question that the code already answered, and no cost claim the suites contradict.

Three statements are stale: §3's "one request costs one pass over one document" (Tasks 1 and 2 make it *closer* to true — name what remains, with the figure from Task 6); §12.1's unprovable-binding fork, which `renameDecision` answered in `1f6d72c` and the branch shipped; §12.3's `.s7i` fork, which `uris.isLibraryBufferPath` answered in `8f3465f`. Code comments already cite "12.2's ruling" and "the controller's 12.2 ruling" for answers that are not in the document — which is how the next reader re-opens them.

- [ ] **Step 1: Answer §12.1 and §12.3 in place**, in the style §12.2 now carries: the decision, the commit that made it, the measured cost, and what is still not built. No new file, no new section.
- [ ] **Step 2: Correct §3's cost claim** with Task 6's figure and what Tasks 1–2 removed: `occurrencesOf` once, `blockRegions` once and only when a buffer record mentions the name. Name the remaining second scan if any survived; if none did, say the claim is now true and point at the checks.
- [ ] **Step 3: Re-read §6's refusal list against `renameDecision`'s arms** — one line per arm, in order, including `capped` and the field arm. Where the code's comment and the document disagree, the document wins unless the code is measured and the document is stale; then correct the document and quote the measurement. This step decides nothing new: if you find an arm with no document line, stop and report it.
- [ ] **Step 3b: correct two sentences that Task 1b's comments got wrong.** Both were found by its reviewer and verified independently by the controller; both are exactly the class of claim this repo treats as a defect on its own.
  * `src/occurrences.sd7` — the `cursorAt` cost note says the region scan on a number/bracket cursor is something "the callers did not pay before". False for `references`, which already called `resolveBinding` unconditionally on every non-empty word; only `prepareRename`'s `slot = 0` path is new cost. Name the one caller that gained work and say the other already paid it.
  * `src/features/prepare_rename.sd7` — the note defending the un-merged records says "`rename.sd7` already reads `no.oc` / `no.b` / `no.slot`". `rename.sd7` reads `no.refused`, `no.reason`, `no.b`, `no.oc` — never `no.slot` (verify with `grep -o 'no\.[a-z]*' src/features/rename.sd7 | sort -u`). The `slot` consumer is `prepareRenameAnswer`, which takes its range from `no.oc[no.slot]`. Fix the sentence to name the real reader; a future maintainer will use exactly this line to decide whether `renameCheck.slot` is load-bearing.
  Both are wording-only. If either sentence is actually TRUE of the code by the time you get here, say so in the commit instead of "fixing" it.
- [ ] **Step 3c: make call-site drift structurally impossible, or record why not.** Task 1b's reviewer noted the two `cursorAt` call sites are pinned only indirectly: nothing asserts they derive `line0`/`col16` the same way. One check comparing the range `references` publishes for a cursor against the range `prepareRename` publishes for the SAME cursor would make drift fail loudly instead of collapsing into "is not a name". Decide it, do not hedge: either add the check or write one line here saying the existing exact-range pins were judged sufficient.
- [ ] **Step 4: `README.md:11` — drop the check count, keep the command.** It reads `863 checks (683 unit + 180 wire)`; the true total on this branch is 893 (713 unit + 180 wire) as of `3fef4f6`, so the line is already wrong, and it was wrong on arrival (the PR body said 865). A number that moves with every committed check cannot be maintained in prose — the same reasoning that made the branch delete the references fixture's line-count assertion. Replace it with `make test # 18 suites + transcript, every suite reporting 0 failed`. If you would rather keep a count, put beside it the command that prints it (`make test 2>&1 | grep -E 'checks, [0-9]+ failed'` and sum), and know it goes stale the next time a check lands.
- [ ] **Step 5: Run `make test` and `sh tools/corpus_scan.sh`,** then commit. The corpus line must still read `files=342 names_probed=4104 occurrences=516044 misses=0`.

---

## Order and why

1 → 1b → 2 → 3 touch the same function (`resolveBinding`) and must land in that order, or the argument list moves under a reviewer's feet. 4 depends on 1 (the `TK_NAME` gate it pins lives in `occurrenceAt`). 5 depends on 1 and 3 for the two-struct slot. 6 and 7 are last because both quote numbers produced by the shipped shape.
