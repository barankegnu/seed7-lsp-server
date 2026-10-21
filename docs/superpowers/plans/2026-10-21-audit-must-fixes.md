# Audit must-fixes (trust gate + quadratic accumulators) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the server analysing a document that sits outside the project roots the client declared, and stop the three string accumulators that copy their whole left side on every append.

**Architecture:** One choke point already exists for every analysis in the server (`lsp_server.sd7`'s `ensureAnalyzed`), so the gate is one boolean consulted there plus one `window/logMessage` on `didOpen`; the containment arithmetic on decoded paths goes into `uris.sd7`, which is already the only module that understands the `file:` scheme. The performance half changes no behaviour: `out := out & X` becomes `out &:= X` at eight sites, which is the interpreter's in-place `STR_APPEND` instead of a fresh `STR_CAT` copy per append.

**Tech Stack:** Seed7 5.4.10 (`s7`, `s7c`), POSIX `sh`, python3 (transcript harness only). No new dependency, no build step other than the Makefile.

**Spec:** `docs/superpowers/specs/2026-09-10-seed7-lsp-server-design.md` — §9 risk 0 ("wants a trust gate in M3 (configured roots or an explicit `initializationOptions` acknowledgement)"), §8's M3 row ("Still open: the trust gate"), §4's "one analysis per document version", §3.5's full-sync rule. The performance half answers the note at `src/doc_store.sd7:100-103`, which asks for exactly this measurement with exactly this command.

## Global Constraints

- Red first: write the check, run it, see it fail for the claimed reason, then implement. `make test` before and after every task (AGENTS.md "Every change").
- When a check cannot fail from real input, delete the assertion rather than invent a synthetic trigger; prove a check can fail by mutating one production branch and naming the check that goes FAIL.
- Performance figures come from a profiled, optimized build (`s7c -p -O2 -l src <file>`, read `profile_out`) — never from `time`-ing the interpreter — and are recorded beside the command that produced them. A byte count comes from the artifact the product emits.
- A probe compiled by `s7c` leaves a binary beside its source plus `profile_out` in the cwd: delete both, and `git status --porcelain -uall` must be empty afterwards.
- Invariants that bind this plan: only `analysis.sd7` imports `progs.s7i` (1); only `doc_store.sd7` converts positions (2); only `utf8bytes.sd7` declares widths and `transport.sd7` owns every outbound byte count (3); only `src/*.sd7` and `src/features/*.sd7` build LSP shapes (4); capabilities stay static in `InitializeResult`, and a capability is advertised only once its method is answered (5); `renameDecision` is the only rename refusal predicate (6); outbound text goes through `jsonw.sd7` and `grep -rn 'addStr(w, str(' --include='*.sd7' src/` stays empty (7).
- Seed7 name refusals: never add a local or parameter named `step`, `key`, `len`, `range`, `line`, `sum`; `result`, `proc`, `type`, `enum`, `and`, `or`, `div` are legal. A `local` cannot be initialised from a parameter of the same function — declare with a constant, assign in `begin`.
- Seed7 idioms this plan uses: `&` concatenates strings and rejects an integer; `&:=` appends in place; a long `or`/`and` chain of parenthesised comparisons can fail to *match*, so each predicate is one comparison or a small chain of `elsif` arms; `in` has no array overload; `declare before use` (a `func` cannot call a helper defined later in the file).
- `docs/PROJECT_GRAPH.md` is generated and committed: after any `src/` change run `make graph` before `make test`, or the graph suite goes red.
- The design spec's risk 0 offers two gates: "configured roots **or** an explicit `initializationOptions` acknowledgement". This plan ships **configured roots only**, and deliberately leaves the acknowledgement unbuilt: a client that declares no root would then be refused everything, which breaks the single-file editing the README tells people to do today. The rootless case stays open and says so on the wire. Overturn this only with a client that actually needs the acknowledgement.
- `out` of scope for this plan (they get their own plans, in this order): the framing rule that contradicts `AGENTS.md` (absent `Content-Length` stops reading), string request ids, the `selectionRange` per-position rescan and short-array answer, `signatureHelp` counting commas inside `{ }`, incremental `didChange` replacing the store with a fragment, the now-reachable `-32603`, `SPECIAL_CHARS`' missing backslash, dead `SEV_WARNING`/`addNull`, and the drifted figures in `AGENTS.md`/`README.md`.

## File Structure

| File | Change | Responsibility after this plan |
|---|---|---|
| `src/uris.sd7` | modify | also owns the containment question: "is this decoded path inside one of these decoded roots?" — a pure predicate, no globals |
| `src/lsp_server.sd7` | modify | owns the declared roots (captured at `initialize`), the one gate consulted before any analysis, and the one log line that explains a refusal |
| `src/scan.sd7` | modify | `maskOf` unchanged in behaviour, its accumulator appends in place |
| `src/rpc.sd7` | modify | `joinSurrogates` unchanged in behaviour, its accumulator appends in place |
| `src/transport.sd7` | modify | `readFrameBody` accumulates in place |
| `src/doc_store.sd7` | modify | the note at `:100-103` is replaced by the measured figure with its command |
| `tests/uris_test.sd7` | modify | pins `underRoot`, including the sibling-prefix trap |
| `tests/lsp_server_test.sd7` | modify | pins the gate's unit-level answers (roots captured, `analysable`, no analysis, no publish) |
| `tests/transcript.py` | modify | pins the wire behaviour: an out-of-root `didOpen` analyses nothing, publishes no diagnostics, and says why once |
| `README.md`, `AGENTS.md`, `docs/seed7-cli.md`, `docs/superpowers/specs/2026-09-10-…-design.md` | modify | the trust-gate claims move from "planned, not implemented" to what ships, and the measured mask figure lands where the evidence lives |

No file is created and none is split. `uris.sd7` and `lsp_server.sd7` are the only two modules that gain a concept, and each gains exactly one.

## Review Focus

The spec is silent on these five inputs; each line is pinned by the named task.

1. **No root declared at all** (`rootUri: null`, no `workspaceFolders`) — a reasonable client (single-file editing) must still get diagnostics, and must be told once that it is running unguarded. → Task 3, Step 1.
2. **A root that is a string-prefix of another directory** (`/tmp/root` vs `/tmp/root2/x.sd7`) — must not match, or the gate is a prefix joke. → Task 2, Step 1.
3. **A percent-encoded root uri** (`file:///tmp/my%20dir`) vs a decoded document path — must match, because `pathOf` already decodes. → Task 2, Step 1.
4. **A request against an untrusted document** — hover/definition/outline answer their ordinary "nothing here" shapes, `references` answers `null`, `rename` answers `null` (never an error, per spec 12.1), and no `analyzed` line ever appears on stderr for that uri. → Task 3 and Task 4.
5. **The `&:=` rewrite on a document whose hidden text spans lines and holds an astral character** — the mask must still be the same length as the text with every newline kept. → Task 1, Step 1.

---

### Task 1: The accumulators append in place

**Files:**
- Modify: `src/scan.sd7:498,503,505,509,515` (`maskOf`), `src/rpc.sd7:65,72` (`joinSurrogates`), `src/transport.sd7:102` (`readFrameBody`)
- Modify: `src/doc_store.sd7:100-103` (the note that asks for the figure)
- Modify: `tests/scan_test.sd7` (one new check for Review Focus 5)
- Test: `make test-scan`, then `make test`

**Interfaces:**
- Consumes: nothing new.
- Produces: no new name, no signature change. `scan.maskOf`, `rpc.joinSurrogates`, `transport.readFrameBody` keep their exact signatures and byte-identical output; every later task may assume only that.

- [ ] **Step 1: Write the pin**

In `tests/scan_test.sd7`, add the check below to `main` before `report("scan")`, in that file's existing `check(title, got, expected)` style. `TEXT` is a `const string` in that file whose content is a `#`-comment line, then a line holding an astral character inside a string followed by code, then a `(* … *)` comment that spans a line break — the three shapes the mask must blank without disturbing anything else. `countChar` is not in the project, so write it in this test file above `main`: five lines, `for i range 1 to length(stri)` counting `stri[i] = ch` into `out`.

The assertion compares the mask against the text rather than against numbers the author counted, so it needs no derivation and cannot pass for the wrong reason:

```seed7
    check("the mask preserves length, newlines and its own result over astral text",
          str(length(maskOf(TEXT))) & "/" & str(countChar(maskOf(TEXT), '\n')) & "/" &
          str(maskOf(maskOf(TEXT)) = maskOf(TEXT)),
          str(length(TEXT)) & "/" & str(countChar(TEXT, '\n')) & "/TRUE");
```

- [ ] **Step 2: Run the pin, and prove it can fail**

Run: `make test-scan`
Expected: PASS on sight — the mask already preserves length and newlines, so this is an after-the-fact pin, and the commit must label it as one (AGENTS.md: a check added to code that already works proves nothing about whether it can fail). Prove it anyway: mutate `src/scan.sd7:503` (`out := out & text[i .. i]`, the newline branch of the blanking loop) to `out := out & " "` and confirm this exact check goes FAIL while the suite's graded line reads `scan: N checks, 1 failed`. Revert with `git checkout -- src/scan.sd7` only — never `git checkout -- .`, which restores from the index and would silently throw away the test you just wrote.

- [ ] **Step 3: Take the figure, before the change**

Write `/tmp/mask_cost.sd7` whose `main` calls `maskOf` once on the text of `~/seed7/lib/shiftjis.s7i` (read with a `readln` loop — `gets(f, -1)` raises `RANGE_ERROR`) and prints `length(text)`. Build and run it with the interpreter's library path pointed at this checkout so the profile names the shipped module:

```bash
s7c -p -O2 -l src /tmp/mask_cost.sd7 && /tmp/mask_cost
awk -F'\t' '$4=="maskOf"{print $1" usecs, "$2" calls"}' profile_out
```

Expected: one row, `maskOf` over ~375 000 characters, in the several-seconds range. Record the row verbatim. Delete `/tmp/mask_cost`, `/tmp/mask_cost.sd7`'s build by-products and `profile_out`, and confirm `git status --porcelain -uall` is empty.

- [ ] **Step 4: Change the eight append sites**

Each site becomes `&:=` with the same right-hand side. `out := out & X` → `out &:= X`; `body := body <& chunk` → `body &:= chunk`. No control flow, no comment churn beyond one line at the head of `maskOf` saying why the shape is load-bearing: Seed7's `&` copies its whole left side, so appending token by token is quadratic in document size, and `&:=` is `STR_APPEND`.

- [ ] **Step 5: Re-take the figure and verify the tests pass**

Run the Step 3 command pair again on the edited tree, then `make test-scan && make test-transport && make test-rpc && make test`.
Expected: the `maskOf` row is three orders of magnitude below Step 3's; every suite's graded line reads `0 failed`.

- [ ] **Step 6: Record the measurement where evidence lives**

Replace the note at `src/doc_store.sd7:100-103` (which currently says the rebuild cost is NOT measured) with two lines: the figure, its command, and the fact that the rewrite is what makes `didChange` cheap. Add a section `## Every change — the mask rebuild cost, measured` to `docs/seed7-cli.md` carrying both profile rows verbatim (before/after), the document's character count, and the exact command. Keep the `ponytail:` upgrade path (version stamp plus lazy fill) in the note if it still holds; if the numbers say it no longer matters, delete the promise and say why in one clause.

- [ ] **Step 7: Commit**

```bash
make graph
git add src/scan.sd7 src/rpc.sd7 src/transport.sd7 src/doc_store.sd7 tests/scan_test.sd7 \
        docs/seed7-cli.md docs/PROJECT_GRAPH.md
git commit -m "append in place: maskOf/joinSurrogates/readFrameBody, with the measured figure

The maskOf/scan/joinSurrogates checks are after-the-fact pins (they pass on
sight); mutated scan.sd7:503's newline branch and the new check went FAIL."
```

---

### Task 2: `uris.underRoot` — containment on decoded paths

**Files:**
- Modify: `src/uris.sd7` (append after `isLibraryBufferPath`)
- Test: `tests/uris_test.sd7`

**Interfaces:**
- Consumes: `pathOf` (already in this file, decodes a `file:` uri to a path).
- Produces: `const func boolean: underRoot (in string: path, in array string: roots) is func` — TRUE when `path` equals a root or starts with `root & "/"`; roots may be given with or without a trailing `/`; an empty `roots` array answers FALSE for every path (the caller decides what "no roots" means, because only the caller knows that trusting is the alternative). Task 3 is its only consumer.

- [ ] **Step 1: Write the failing tests**

Append six checks to `tests/uris_test.sd7` before `report("uris")` — the file's existing six make twelve, which Step 4 expects. They use `[]("…")` for the array literal (a brace form is a block, and `("a","b")` does not match):

```seed7
    check("a child of a declared root is under it",
          str(underRoot("/tmp/root/a/b.sd7", []("/tmp/root"))), "TRUE");
    check("the root itself is under it",
          str(underRoot("/tmp/root", []("/tmp/root"))), "TRUE");
    check("a trailing slash on the root changes nothing",
          str(underRoot("/tmp/root/a.sd7", []("/tmp/root/"))), "TRUE");
    check("a sibling whose name starts with the root is NOT under it",
          str(underRoot("/tmp/root2/a.sd7", []("/tmp/root"))), "FALSE");
    check("no roots means nothing is contained",
          str(underRoot("/tmp/root/a.sd7", 0 times "")), "FALSE");
```

Add one more, Review Focus 3: `pathOf("file:///tmp/my%20dir/a.sd7")` fed through `underRoot` against `[]("/tmp/my dir")` must answer `TRUE` — the predicate compares decoded strings, and this is the check that keeps Task 3 from percent-decoding one side only. (The empty-roots check uses `0 times ""`, not `[]("")`: a one-element array holding the empty string is a *root of ""*, and `startsWith(path, "" & "/")` would match every absolute path — which is why `underRoot` skips an empty root rather than matching on it, and Task 3's capture skips empty strings too.)

- [ ] **Step 2: Run test to verify it fails**

Run: `make test-uris`
Expected: the suite prints nothing and exits 0, and the Makefile recipe reports failure because no `uris: N checks, 0 failed` line appeared — `underRoot` does not exist, so the file does not analyse. Confirm the reason is the missing name by running `s7 -q -l src tests/uris_test.sd7` and reading stderr: expect a `NO_MATCH`/`expected found "underRoot"`-class report naming `underRoot`. This is the failure mode AGENTS.md warns about (a suite that cannot analyse is silent), so do not accept a red without that line.

- [ ] **Step 3: Implement `underRoot`**

Signature as in the Interfaces block; the body is one loop over `roots` with the two comparisons, a trailing `/` stripped from each root first, and `out` set only when it is still FALSE (Seed7 has no `exit`-from-loop idiom worth reaching for here, and each arm stays one comparison). Comment two lines: the rule is textual after `pathOf`, so it is case- and separator-exact; on Windows a drive letter's case would need folding, and Windows is untested and out of scope here — name that in one clause rather than adding a fold nobody can test.

- [ ] **Step 4: Run test to verify it passes**

Run: `make test-uris`
Expected: `uris: 12 checks, 0 failed`.

- [ ] **Step 5: Prove the checks can fail**

Mutate `src/uris.sd7`: replace `startsWith(path, root & "/")` with `startsWith(path, root)`. Run `make test-uris`.
Expected: FAIL on "a sibling whose name starts with the root is NOT under it" — that check is the whole point of the `/`. Revert with `git checkout -- src/uris.sd7`.

- [ ] **Step 6: Commit**

```bash
make graph
git add src/uris.sd7 tests/uris_test.sd7 docs/PROJECT_GRAPH.md
git commit -m "uris.underRoot: containment on decoded paths, one rule one place"
```

---

### Task 3: The gate — analyse only inside the declared roots

**Files:**
- Modify: `src/lsp_server.sd7` (globals near `:31`, the `initialize` branch near `:288`, a new `analysable` above `ensureAnalyzed` at `:170`, `refresh` near `:230`, `ensureAnalyzed`, the `didOpen` branch)
- Test: `tests/lsp_server_test.sd7`

**Interfaces:**
- Consumes: `uris.underRoot` (Task 2, exact signature above), `pathOf`, `atKey`/`strAt`/`boolAt`/`itemAt` from `rpc.sd7`, `logMessage` and `note` already in this file.
- Produces:
  - `var array string: projectRoots is 0 times "";` — decoded root paths, empty means none declared.
  - `var boolean: rootsDeclared is FALSE;` — TRUE iff `initialize` yielded at least one root.
  - `const func boolean: analysable (in string: uri) is func` — TRUE when `not rootsDeclared`, otherwise `underRoot(pathOf(uri), projectRoots)`.
  Task 4 reads only `analysable` (through the wire), never the globals.

- [ ] **Step 1: Write the failing tests**

In `tests/lsp_server_test.sd7`, following that file's existing helper style (it includes `lsp_server.sd7`, so it reads the dispatcher's globals and calls its functions directly). Above `main`, add the two helpers the checks below use: `uriInAnalysisCache` (`out := uri in analysisCache;`, two lines) and `openOutside` (`openDocs @:= [uri] lsDoc.value; setVersion(openDocs[uri], TEXT, 1);` on a uri outside the roots — reuse the fixture text the file already carries for "a document that analyses clean"; if it has none, use `"$ include \"seed7_05.s7i\";\n"`).

```seed7
    check("no declared roots means the gate is open",
          str(analysable("file:///anywhere/at/all.sd7")), "TRUE");
```

then, with the globals set the way `initialize` would set them — one root `/tmp/proj`, `rootsDeclared := TRUE`:

```seed7
    check("inside the declared root: analysable",
          str(analysable("file:///tmp/proj/src/a.sd7")), "TRUE");
    check("outside the declared root: refused",
          str(analysable("file:///tmp/other/b.sd7")), "FALSE");
    check("a sibling directory of the root is refused, not half-matched",
          str(analysable("file:///tmp/proj2/c.sd7")), "FALSE");
    check("a .s7i outside the roots is never analysed, so the driver never reads it",
          str(uriInAnalysisCache("file:///tmp/other/lib.s7i")), "FALSE");
    check("a .s7i INSIDE the roots is analysed, so the check above is not vacuous",
          str(uriInAnalysisCache("file:///tmp/proj/lib.s7i")), "TRUE");
    check("an untrusted document's outline is empty", documentSymbolResult(
          symbolsOfDocument("file:///tmp/other/b.sd7"), "/tmp/other/b.sd7"), "[]");
    check("an untrusted document cost no analysis",
          str(uriInAnalysisCache("file:///tmp/other/b.sd7")), "FALSE");
    check("a trusted document does cost one, and its outline is not empty",
          str(uriInAnalysisCache("file:///tmp/proj/src/a.sd7")) & "/" &
          (documentSymbolResult(symbolsOfDocument("file:///tmp/proj/src/a.sd7"),
                                "/tmp/proj/src/a.sd7") = "[]" ? "empty" : "filled"),
          "TRUE/filled");
```

Each of the cache checks is preceded by its own `openOutside(...)` / `openInside(...)` and a call to `ensureAnalyzed(uri)` — a check that the cache is empty proves nothing unless something was opened and analysed first, which is why the two `TRUE` checks sit in the same block as the `FALSE` ones. The `.s7i` pair is the arm that matters most: inside the roots, `driverFor` reads the file off disk and the cache fills; outside them it must not. `pathOf` and `projectRoots` are read directly where a check needs them.

- [ ] **Step 2: Run test to verify it fails**

Run: `make test-lsp_server`
Expected: the file does not analyse (`analysable` undefined) → no graded line → recipe fails. Confirm stderr names `analysable`, as in Task 2 Step 2.

- [ ] **Step 3: Implement the capture and the gate**

`initialize` branch, beside the existing `clientCanApplyEdits` read: take `workspaceFolders` first (a JSON array of objects each with `uri`), else `rootUri`; push every `pathOf(...)` result onto `projectRoots`, and set `rootsDeclared := TRUE` only if at least one survived. A non-array `workspaceFolders`, a missing `uri`, or an empty string is skipped, never fatal.

Gate at the single analysis point: in `ensureAnalyzed`, wrap the `fresh := analyzeAll(...)` / cache-fill / `note` block in `if analysable(uri) then`. `refresh` returns early for a non-`analysable` uri — publishing an empty diagnostics list would claim a clean document, which is the class of lie the spec's §4 already refuses for `parseStri`. The `didOpen` branch keeps storing the document (so `didClose` and later trust decisions work) and, when `not analysable(uri)`, sends exactly one `logMessage` so the client is told once per document and not once per keystroke — and the sentence is pinned, because Task 4's wire check greps it for the word `roots`:

```seed7
      "refusing to analyse " <& uri <& ": it is outside the project roots this client declared"
```

Keep it `MSG_INFO`: this is information, and `logMessage` is the channel that already exists.

Leave the scanner-backed features alone: `foldingRange`, `selectionRange` and `semanticTokens` read `doc.text` and cannot execute anything, so they keep answering for an untrusted buffer, and the hover/definition/outline/rename family answers from an empty symbol list. One comment at `ensureAnalyzed` says that in two lines, because the next reader will ask why some features work outside the roots.

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test-lsp_server && make test-uris && make test`
Expected: each graded line reads `0 failed`; the existing checks about capability advertisement are untouched, because no capability is added or removed (invariant 5).

- [ ] **Step 5: Prove the gate holds by mutation**

Mutate `src/lsp_server.sd7`: change `out := not rootsDeclared or underRoot(...)` to `out := TRUE`. Run `make test-lsp_server`.
Expected: FAIL on "outside the declared root: refused", "an untrusted document cost no analysis", "a .s7i outside the roots is never analysed" and the two wire checks Task 4 adds — and PASS on every positive control ("a trusted document does cost one", "a .s7i INSIDE the roots is analysed"), which is what makes the reds mean a gate failure rather than a broken suite. Revert with `git checkout -- src/lsp_server.sd7`.

- [ ] **Step 6: Commit**

```bash
make graph
git add src/lsp_server.sd7 tests/lsp_server_test.sd7 docs/PROJECT_GRAPH.md
git commit -m "trust gate: analyse only inside the roots initialize declared"
```

---

### Task 4: The gate on the wire, and the docs that claim it

**Files:**
- Modify: `tests/transcript.py`
- Modify: `README.md:22-33` (security section) and `README.md:133` (the not-working list)
- Modify: `AGENTS.md:231` and `AGENTS.md:249`
- Modify: `docs/seed7-cli.md` (Milestones section's "Still open from M3: … the trust gate")
- Modify: `docs/superpowers/specs/2026-09-10-seed7-lsp-server-design.md` §8 M3 row and §9 risk 0 (append what shipped; do not rewrite the decision)
- Test: `make transcript`, `make test-agents`, `make test`

**Interfaces:**
- Consumes: the wire behaviour Task 3 shipped (`initialize` roots → `didOpen` → no `analyzed` line, no `publishDiagnostics`, one `window/logMessage`).
- Produces: nothing for later code.

- [ ] **Step 1: Write the wire checks**

Two `run([...])` blocks in `tests/transcript.py`, using its existing `frame`/`notify`/`td` helpers and the `BROKEN` text it already defines. Block one: `initialize` with `rootUri: "file:///tmp/proj"`, then `didOpen` both `IN_URI = "file:///tmp/proj/in.sd7"` and `OUT_URI = "file:///tmp/outside.sd7"` (each with `BROKEN`), then one `didChange` on `OUT_URI`, then `shutdown`/`exit`; bind `replies, code, err, junk = run([...])` and `diag_notes = [r for r in replies if r.get("method") == "textDocument/publishDiagnostics"]` the way the file's other blocks already do. Assert:

```python
expect(not any(p["params"]["uri"] == OUT_URI for p in diag_notes),
       "a document outside the declared roots publishes nothing")
expect("analyzed " + OUT_URI not in err, "the outside document is never analysed")
expect(any(r.get("method") == "window/logMessage" and "roots" in r["params"]["message"]
           for r in replies), "the refusal names the declared roots")
expect(any(p["params"]["uri"] == IN_URI and p["params"]["diagnostics"]
           for p in diag_notes), "the inside document still gets its diagnostics")
```

Plus, in the same block, one check that the single `didChange` on `OUT_URI` added no second `window/logMessage` (once-per-document is the point of logging at `didOpen` rather than at the gate). Then block two: `initialize` with no root at all (`rootUri: null`, no `workspaceFolders`) and the same `OUT_URI` text, asserting it still analyses (`"analyzed " + OUT_URI in err`) and publishes one Error diagnostic — Review Focus 1. That second block is what stops the gate being tested only in its closed state.

- [ ] **Step 2: Run them, and prove they can fail**

Run: `make transcript`
Expected: PASS on sight — Task 3 already shipped the behaviour, so these are after-the-fact pins, and the commit must label them as such (AGENTS.md: a check added to code that already works proves nothing about whether it can fail). Prove them anyway: in `src/lsp_server.sd7`, change `analysable`'s body to `out := TRUE;`, run `make transcript`, and confirm the gate checks go FAIL while the rootless-client check stays green (it should: `out := TRUE` is the open behaviour it asserts). Then `git checkout -- src/lsp_server.sd7` — that reverts by file, never `git checkout -- .`, which would also throw away the tests you just wrote.

- [ ] **Step 3: Correct the documents that promise the gate**

README: the security section keeps the "this runs the code you open" rule as the single source of truth and gains the shipped fact — the server now analyses only inside `rootUri`/`workspaceFolders`, and a client that declares no root runs unguarded and is told so at `initialize`; "planned for M3 and **not implemented**" goes. Remove `the trust gate` from the *What does not work yet* list. `AGENTS.md` and `docs/seed7-cli.md`: the same claim in the two places the Milestones sections carry it. Append one dated line to design-spec §9 risk 0 recording what shipped and the rootless caveat — the spec argues, it does not hide.

- [ ] **Step 4: Run the gates over the docs**

Run: `make test-agents && make graph && make test`
Expected: `agents: 44 checks, 0 failed` (or the count it recomputes — the gate checks frozen tokens still appear, and `trust gate` is not one of them; if `make test-agents` goes red you deleted a frozen claim and must restore it, not substitute a synonym), and every suite line `0 failed`.

- [ ] **Step 5: Commit**

```bash
git add tests/transcript.py README.md AGENTS.md docs/seed7-cli.md \
        docs/superpowers/specs/2026-09-10-seed7-lsp-server-design.md docs/PROJECT_GRAPH.md
git commit -m "the trust gate on the wire, and the docs stop promising it"
```
