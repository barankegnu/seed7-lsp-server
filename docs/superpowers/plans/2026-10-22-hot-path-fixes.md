# Hot-Path Fixes (line-bounded columns + one selection scan) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans (required if you are a subagent) this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the two hottest conversions in the server cost what the design already promised — a UTF-16 column bounded by its own line, and one `blockRegions` scan per `selectionRange` request — without moving a single answer.

**Architecture:** `doc_store.sd7` owns position conversion (invariant 2) and already holds the fix's shape: `lineUnits` counts one line's UTF-16 units so `lspRangeUnits` never walks the document. `lspRange` is the same arithmetic with the document-length version of that walk, so it gets the line-local helper and `utf16Before` retires. `blocks.sd7` owns "what encloses this line" (M4 §5); `selectionRange` asks it once per position today, so the scan moves up into `selectionResult` and the per-position work becomes a filter over a list the caller already holds — the shape `routineRegionFor` already uses for the same reason.

**Tech Stack:** Seed7 5.4.10 (`s7`, `s7c`), POSIX `sh`, python3 (wire harness only). No new dependency, no new file, no build step beyond the Makefile.

**Spec:** `docs/superpowers/specs/2026-09-18-seed7-lsp-m4-scanner-and-token-features-design.md` — §4.4 ("`utf16Before` scans from index 1 and costs ~31 ms for 200 000 characters"; "Random access keeps what it has … both bounded by line length"), §4.3 ("`foldingRange`, `selectionRange` and `semanticTokens` each take **one fresh forward pass**"), §6.1 ("the answer is one `SelectionRange[]` in the same order … **A single pass answers all positions**"), §7 accepted risk ("`selectionRange` over a stream is O(document) per **request**"). Also `AGENTS.md` invariants 2 and 3, and its cost rule "one analysis per version".

## Global Constraints

- Red first: write the check, run it, confirm it fails **for the reason named in the step**, then implement. `make test` before and after every task.
- A check that cannot fail from real input is deleted, never given a synthetic trigger. Prove each plan-named assertion can fail by mutating one production branch and naming the check that goes FAIL.
- Check the mutant is not semantically identical before demanding it redden anything; and "no fixture reaches it" is not "no input reaches it".
- Performance figures come from a profiled optimized build only: `s7c -p -O2 -l <src> <probe>`, run it, read `profile_out`. Never `time` the interpreter. Record the command beside every figure that lands in a file or a commit message.
- A probe must print a sentinel the harness requires before any payload counts as a result. Probe sources and their binaries live under `/tmp`, never in the repo; a compiled probe leaves its binary beside its source and `profile_out` in the cwd — delete all of it, and `git status --porcelain -uall` must be empty afterwards.
- Any change under `src/` regenerates the committed graph **before** the suite runs: `make graph`, then `make test`. Skipping it turns `make test-graph` red.
- Invariants that bind this plan: only `src/doc_store.sd7` converts LSP positions (2); only `src/utf8bytes.sd7` declares the width rules and only `src/transport.sd7` emits an outbound byte count (3); only `src/*.sd7` and `src/features/*.sd7` build LSP shapes (4); `grep -rn 'addStr(w, str(' --include='*.sd7' src/` stays empty (7).
- Seed7 refusals: never name a local or parameter `step`, `key`, `len`, `range`, `line`, `sum`, or anything in `src/keywords.sd7`'s `CANNOT_BE_NAME`; `count`, `units`, `text`, `idx`, `n`, `i`, `start`, `stop` are legal here (measured by the gate, not guessed).
- Seed7 idioms: a `func` assigns its `result` variable (no `return x;`); `local` variables are initialised with constants, never from a parameter of the same function; a helper must be **declared above** the function that calls it; `&:=` appends in place, `&` copies; integer division is `div`; `writeln` takes exactly one argument; a newline inside a string literal is `\n`, a tab is `\9;`, an astral character is `\128512;`.
- No behaviour moves. Every figure in this plan was taken against `master` at `50833bb`; the whole suite (21 graded lines, 1 040 checks, plus `transcript: 192 checks`) is green before and after each task.

**Not in this plan** (each is a separate decision, listed so nobody reads their absence as approval): the `selectionRange` short-array deviation, the frame that ends the session on a header block with no `Content-Length`, `signatureHelp` counting commas inside `{ }`, an incremental `didChange` replacing the store with a fragment, `-32603` answering id 0, `prepareProvider` advertised unconditionally, and the `AGENTS.md` `getl` bullet. Findings 1 and 4 are here because they are the two costs a keystroke pays.

## Review Focus

The spec implies these five inputs; no task's existing tests cover all of them, and each line gets its check in the named step.

1. **A character column that sits behind an astral character** — the answer must still be the UTF-16 unit, not the character index. → Task 1 Step 1 (`col7`/`col8`).
2. **A column past the end of its own line** (`lspRange(doc, 1, 99)`, and the analyzer's absurd byte columns that arrive through `lspRangeBytes`) — must clamp to the line, not read on into the next one. → Task 1 Step 1 (`past-eol clamp`, `stopNL`).
3. **A CR-only or CRLF buffer** — `\r` is a line break for this server, so a line-local walk must stop at it too. → Task 1 Step 1 (`stopCR`).
4. **Two positions in one `selectionRange` request that fall inside the same region** — both must get the region in their chain, in request order, from the one scan. → Task 2 Step 1.
5. **A document that encloses nothing** (`"a  b"`) — the filter must answer the empty list, and the chain must still carry exactly token + document, which existing check (c) pins. → Task 2 Step 1 (`a held list with nothing enclosing it`).

---

### Task 1: `unitsOfPrefix` — a UTF-16 column bounded by its line

**Files:**
- Modify: `src/doc_store.sd7` (new helper above `lspRange` at `:131`; the two-walk expression at `:149-150`; delete `utf16Before` at `:48-58`)
- Modify: `tests/doc_store_test.sd7` (the two `utf16Before` checks at `:78-79` move; new checks)
- Modify: `docs/PROJECT_GRAPH.md` (generated: `make graph`)
- Read-only reference: `src/utf8bytes.sd7:48` (`utf16CharLength`), `src/doc_store.sd7:88` (`lineUnits`, the shape to copy), `docs/superpowers/specs/2026-09-18-…-design.md` §4.4

**Interfaces:**
- Consumes: `utf8bytes.utf16CharLength(char) -> integer`; `doc_store.lineIndexOf(lsDoc, integer) -> integer`; `doc_store.lineWidth(string, integer) -> integer` (unchanged, still the character clamp).
- Produces: `const func integer: unitsOfPrefix (in string: text, in integer: start, in integer: count) is func` in `src/doc_store.sd7` — the UTF-16 units carried by the first `count` characters of the line that begins at index `start`, stopping at `\n` or `\r`. Returns `0` for `count = 0`. `utf16Before` no longer exists; `lspRange`, `lspRangeBytes`, `lspRangeUnits` and `lspWholeLine` keep their exact signatures.

- [ ] **Step 1: Write the failing checks in `tests/doc_store_test.sd7`**

Replace the two checks that call the doomed `utf16Before` and add five. Values below were printed by a probe against `master`; the astral fixture is `u := "<U+1F400>"; v := 1;` + `\n`, 18 characters, character 7 being the astral one.

```seed7
    # (was) utf16Before's two astral checks, re-aimed at the line-local helper.
    check("astral counts twice", str(unitsOfPrefix("a\128512;b", 1, 2)), "3");
    check("trailing b counted", str(unitsOfPrefix("a\128512;b", 1, 3)), "4");
    # The guard the caller's clamp cannot reach: the walk stops at its own line break.
    check("count stops at the newline",  str(unitsOfPrefix("ab\ncd", 1, 4)), "2");
    check("count stops at a CR",         str(unitsOfPrefix("a\r\nb", 1, 4)), "1");
    # Equivalence pins through the product function, on a line holding an astral
    # character ahead of the column, and the past-the-end clamp of the same line.
    setVersion(astral, "u := " <& chr(34) <& chr(128512) <& chr(34) <&
                       "; v := 1;" <& chr(10), 1);
    check("lspRange before the astral", lspRange(astral, 1, 7),
          "{\"line\":0,\"character\":6}");
    check("lspRange past the astral",   lspRange(astral, 1, 8),
          "{\"line\":0,\"character\":8}");
    check("lspRange past eol on an astral line", lspRange(astral, 1, 99),
          "{\"line\":0,\"character\":18}");
```

Add `var lsDoc: astral is lsDoc.value;` to `main`'s `local` part (Seed7 declares with a constant, then assigns in `begin`).

- [ ] **Step 2: Run the suite and confirm it fails for the stated reason**

Run: `make test-doc_store`
Expected: the recipe fails — the suite cannot analyse because `unitsOfPrefix` is not declared, so **no** graded line is printed and the `grep -q '^[a-z0-9_]+: [0-9]+ checks, 0 failed$'` finds nothing. If it instead prints a line with a non-zero count, the check is red for the wrong reason; fix the check before going on.

- [ ] **Step 3: Implement `unitsOfPrefix` and repoint `lspRange`**

Put the function immediately above `lspRange` (a `func` cannot call a helper declared later in the file). It mirrors `lineUnits`: same walk, same two break tests, bounded by `count` as well. Then replace the whole-document subtraction in `lspRange` — `utf16Before(doc.text, start + ch) - utf16Before(doc.text, start)` — with one call to `unitsOfPrefix(doc.text, start, ch)`, and delete `utf16Before`.

Extend the comment above `lspRange` with why this is not a new idea: the file already deleted this shape once, for `lspRangeUnits`, and M4 §4.4's promise that random access is "bounded by line length" was true of every converter except this one. Record the measured figures (Step 7) beside that note, in the house style of `lineUnits`' comment.

- [ ] **Step 4: Run the suite and confirm it passes**

Run: `make test-doc_store`
Expected: `doc_store: 77 checks, 0 failed` (72 today, +5: the two moved checks replace their originals, three `lspRange` pins and two helper-boundary checks are new)

- [ ] **Step 5: Prove the new checks can fail**

Mutate `src/doc_store.sd7` one line at a time and revert each by file (`git checkout -- src/doc_store.sd7` restores from the index, so commit nothing yet or revert per hunk). Name the check that reddens; a mutant that reddens nothing is a check that cannot fail:

| mutant | must redden |
|---|---|
| `n < count` → `n <= count` | `astral counts twice`, `trailing b counted`, and the three `lspRange …` pins |
| drop the `text[i] <> '\n'` test | `count stops at the newline` |
| drop the `text[i] <> '\r'` test | `count stops at a CR` |
| `i := start` → `i := succ(start)` | `lspRange before the astral` |

- [ ] **Step 6: Measure it, the way this repo measures**

Build the probe outside the repo (`/tmp/probe_perf/probe_diag.sd7`): read `~/seed7/lib/shiftjis.s7i` with a `readln` loop into one string, `setVersion` it, build 100 `lspDiag` records at `line1 := 30 + i * 36`, `column1 := 7`, run them through `mapDiagnostics(…, 100)`, call `diagnosticsJson` 5 times, and print `PROBE_DONE publishes=5 bytes_per_publish=<n>` — the sentinel gates the payload. Then:

```
s7c -p -O2 -l src /tmp/probe_perf/probe_diag.sd7 && /tmp/probe_perf/probe_diag
awk -F'\t' '$4=="diagnosticsJson"||$4=="unitsOfPrefix"||$4=="utf16Before"{print $1,$2,$4}' profile_out
```

Expected, from the run behind this plan (`utf16Before` row present = before, `unitsOfPrefix` row = after):

| figure | before | after |
|---|---|---|
| `diagnosticsJson`, 5 publishes on `shiftjis.s7i` (375 354 chars, 3 635 lines) | 16 697 357 µs | 3 440 µs |
| one publish of the same | 3 339 471 µs | 688 µs |
| a 2 004-line / 113 005-char document, 100 diagnostics | 225 355 µs / 5 | 3 477 µs / 5 |
| `profile_out` rows for the walk | `utf16Before` 16 687 763 µs / 2 000 calls | `unitsOfPrefix` 276 µs / 1 000 calls |

Delete the probe binary and `profile_out`; `git status --porcelain -uall` must be empty.

- [ ] **Step 7: Regenerate the graph, run everything, commit**

```bash
make graph && make test
git status --porcelain -uall   # empty apart from the files being committed
git add src/doc_store.sd7 tests/doc_store_test.sd7 docs/PROJECT_GRAPH.md
git commit -m "doc_store: bound a UTF-16 column by its own line

lspRange asked utf16Before twice, so every range walked from index 1:
16 697 357 us for 5 publishes of 100 diagnostics on lib/shiftjis.s7i
(375 354 chars), 225 355 us on a 2 004-line document. unitsOfPrefix
walks the line instead -- the lineUnits shape this file already has --
and the same runs cost 3 440 us and 3 477 us, with byte-identical JSON.
profiled with s7c -p -O2 -l src; rows read from profile_out.
utf16Before's last caller is gone, so it goes with its two checks, which
move to the new helper."
```

---

### Task 2: One `blockRegions` per `selectionRange` request

**Files:**
- Modify: `src/blocks.sd7` (add `enclosingRegionsFrom` where `enclosingRegions` sits at `:347`; delete `enclosingRegions`)
- Modify: `src/features/selection_range.sd7` (`chainForPosition:31-99`, `selectionResult:101-126`)
- Modify: `tests/blocks_test.sd7:53` and `:120` (the two `enclosingRegions` call sites), plus new checks
- Modify: `tests/selection_range_test.sd7` (one new check; the seven existing answers must come back byte-identical)
- Modify: `docs/PROJECT_GRAPH.md` (generated), `docs/superpowers/specs/2026-10-12-seed7-lsp-m5-references-and-rename-design.md:164` (prose names `blocks.enclosingRegions`, which this task deletes)

**Interfaces:**
- Consumes: `blocks.blockRegions(text, lastLine) -> array blockRef` (unchanged; already document-ordered).
- Produces: `const func array blockRef: enclosingRegionsFrom (in array blockRef: all, in integer: line0) is func` in `src/blocks.sd7` — the members of `all` that enclose `line0`, sorted **innermost first** (`startLine` descending), the exact order `enclosingRegions` returned. `enclosingRegions` no longer exists.
- Produces: `chainForPosition (in lsDoc: doc, in jsonValue: posObj, in integer: lastLine, in array blockRef: allRegions)` — one more parameter, same answer.

- [ ] **Step 1: Write the failing checks**

In `tests/blocks_test.sd7`, keep the existing helpers working by calling the new pair, and add one check that filters a list held by the caller — Review Focus 4 and 5 in one document, one position inside a `func` body and one in a file that encloses nothing:

Both expected strings below were printed by running `blockRegions`/`enclosingRegions` against `master` on exactly these inputs — paste them as written.

```seed7
    text := "$ include \"seed7_05.s7i\";" <& chr(10) <& "const proc: main is func" <& chr(10)
            <& "  begin" <& chr(10) <& "    writeln(1);" <& chr(10) <& "  end func;";
    # blockRegions(text, 4) holds exactly two regions, 1-4 and 2-4; line0 3 sits in both.
    rs := blockRegions(text, pred(linesIn(text)));
    check("filter of a held list, innermost first",
          chainOfRegions(rs, 3), "2-4 1-4");
    check("a held list with nothing enclosing it",
          chainOfRegions(blockRegions("a  b", pred(linesIn("a  b"))), 0), "");
```

`chainOfRegions (in array blockRef: rs, in integer: line0)` is the existing `chainOf` body with the `blockRegions` call removed, the list passed in and `enclosingRegionsFrom(rs, line0)` filtered inside it — it renders `startLine-endLine` pairs separated by a space, as `chainOf` already does. Update `chainOf` and `closerAt` (`:53`, `:120`) to `enclosingRegionsFrom(blockRegions(text, pred(linesIn(text))), line0)`.

In `tests/selection_range_test.sd7`, add the request-order check that proves the shared list is still filtered per position — two cursors inside the same `begin … end func` region, identical parents, different token ranges:

```seed7
    text := "$ include \"seed7_05.s7i\";\nconst proc: main is func\n  begin\n"
            "    writeln(1);\n  end func;";
    expected := "[{\"range\":{\"start\":{\"line\":3,\"character\":4},\"end\":{\"line\":3,\"character\":11}}," <&
                "\"parent\":{\"range\":{\"start\":{\"line\":2,\"character\":0},\"end\":{\"line\":4,\"character\":11}}," <&
                "\"parent\":{\"range\":{\"start\":{\"line\":1,\"character\":0},\"end\":{\"line\":4,\"character\":11}}," <&
                "\"parent\":{\"range\":{\"start\":{\"line\":0,\"character\":0},\"end\":{\"line\":4,\"character\":11}}}}}," <&
                "{\"range\":{\"start\":{\"line\":3,\"character\":11},\"end\":{\"line\":3,\"character\":12}}," <&
                "\"parent\":{\"range\":{\"start\":{\"line\":2,\"character\":0},\"end\":{\"line\":4,\"character\":11}}," <&
                "\"parent\":{\"range\":{\"start\":{\"line\":1,\"character\":0},\"end\":{\"line\":4,\"character\":11}}," <&
                "\"parent\":{\"range\":{\"start\":{\"line\":0,\"character\":0},\"end\":{\"line\":4,\"character\":11}}}}}]";
    check("two positions in one region share the chain, in order",
          selOf(text, "[{\"line\":3,\"character\":4},{\"line\":3,\"character\":12}]"),
          expected);
```

The point of the check is that it does **not** move when the scan is hoisted: its two chains share all three region levels and differ only in the innermost token range (`11-12` is the `1` of `writeln(1);`, one unit left of the requested column 12).

- [ ] **Step 2: Run both suites and confirm they fail for the stated reason**

Run: `make test-blocks`
Expected: no graded line — `blocks_test.sd7` cannot analyse `enclosingRegionsFrom`.
Run: `make test-selection_range`
Expected: green at `selection_range: 8 checks, 0 failed` — the new check names no new function, so it passes on `master` and its job is to prove the answers do not move when the scan is hoisted. Only `test-blocks` is red at this point, and it is red because of the undeclared `enclosingRegionsFrom`.

- [ ] **Step 3: Implement `enclosingRegionsFrom` in `src/blocks.sd7`**

Move `enclosingRegions`' filter-and-sort body under the new name, taking the already-scanned list instead of the text; the document-order guarantee of `blockRegions` is what makes the descending sort correct, so say so in one line of comment and keep `routineRegionFor`'s comment honest: it exists because a caller pairing several declarations pays one scan, and this is the same rule for several positions. Delete `enclosingRegions`.

- [ ] **Step 4: Hoist the scan in `src/features/selection_range.sd7`**

`selectionResult` computes `allRegions := blockRegions(doc.text, lastLine);` once, before the position loop, and passes it to `chainForPosition`; `chainForPosition` calls `enclosingRegionsFrom(allRegions, line0)` instead of `enclosingRegions(doc.text, line0, lastLine)`. Declare the local as `var array blockRef: allRegions is 0 times blockRef.value;` in `selectionResult`'s `local` part (a `local` may not be initialised from a parameter), and assign in `begin`. Rewrite the file's cap comment to say what the cap now buys — one chain build per position, not one scan per position.

- [ ] **Step 5: Run both suites and confirm they pass**

Run: `make test-blocks && make test-selection_range`
Expected: `blocks: 70 checks, 0 failed` and `selection_range: 8 checks, 0 failed`

- [ ] **Step 6: Prove the new checks can fail**

| mutant (one at a time, then revert) | must redden |
|---|---|
| sort comparator `<` → `>` in `enclosingRegionsFrom` (outermost first) | `filter of a held list, innermost first`, and `two positions yield answers in request order` (existing check (d)) |
| `line0 <= all[i].endLine` → `line0 < all[i].endLine` | `filter of a held list, innermost first` |
| pass an empty `allRegions` from `selectionResult` | `two positions in one region share the chain, in order` and (b), (d), (f) |

- [ ] **Step 7: Measure the hoist the same way**

Probe: `/tmp/probe_perf/probe_sel.sd7` — `shiftjis.s7i` text, `setVersion`, 32 positions spread over lines `500 + i * 12`, three `selectionResult` calls, sentinel `PROBE_DONE selectionRange x3 bytes_each=<n>`; then `s7c -p -O2 -l src`, run, and read `profile_out`:

```
awk -F'\t' '$4=="selectionResult"||$4=="blockRegions"{print $1,$2,$4}' profile_out
```

Expected, from the runs behind this plan. All four rows come from the same probe on the same text, `profile_out` rows only; the middle row isolates the hoist by measuring after Task 1 alone, and `bytes_each` came back 5 441 on both sides of every run:

| figure | before | after |
|---|---|---|
| `selectionResult`, one 32-position request, `shiftjis.s7i` | 1 948 799 µs | 195 080 µs |
| same, after Task 1's fix alone (the hoist's own share: 962 963 → 195 080) | 962 963 µs | 195 080 µs |
| `selectionResult`, one 32-position request, the 2 004-line document | 788 603 µs | 126 737 µs |
| `blockRegions` calls for 3 such requests (`shiftjis.s7i`) | 99 | 6 |

The `bytes_each` sentinel must be identical on both sides of the change: 5 441 for the 32-position request on `shiftjis.s7i`, 5 409 for the 32-position request on the 2 004-line document (both measured). Deleting the second product caller of `enclosingRegions` is what the `blockRegions` call row proves; the answer itself is proved by the seven unchanged checks.

- [ ] **Step 8: Regenerate the graph, fix the stale spec reference, run everything, commit**

`make graph`, then the one-line edit at `docs/superpowers/specs/2026-10-12-…-design.md:164` naming `blocks.enclosingRegionsFrom` over a `blockRegions` list instead of `blocks.enclosingRegions`, then `make test`.

```bash
git add src/blocks.sd7 src/features/selection_range.sd7 tests/blocks_test.sd7 \
        tests/selection_range_test.sd7 docs/PROJECT_GRAPH.md \
        docs/superpowers/specs/2026-10-12-seed7-lsp-m5-references-and-rename-design.md
git commit -m "selectionRange: scan the regions once per request, not per position

M4 6.1 promised 'a single pass answers all positions' and 7 accepted
O(document) per request; what shipped was O(document) per position,
because enclosingRegions ran blockRegions inside chainForPosition.
selectionResult now holds the list and enclosingRegionsFrom filters it:
1 948 799 us -> 195 080 us for a 32-position request on
lib/shiftjis.s7i, blockRegions 99 calls -> 6, byte-identical answers.
profiled with s7c -p -O2 -l src; rows read from profile_out."
```
