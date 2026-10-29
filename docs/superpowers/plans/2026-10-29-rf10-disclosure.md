# R-F10 Disclosure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Say, in the open `.s7i` buffer itself, that its outline / hover / completion / diagnostics come from the file on disk — so an unsaved library edit stops reading as a clean document.

**Architecture:** The analysis route for libraries does not change: `analysis.sd7`'s `driverFor(path)` stays, because the interpreter re-declares a library's names when its text is pasted into an analysed string (measured: 29 of the 214 top-level libraries redeclare, and `multiscr.s7i` fails on both routes). One pure function in `lsp_server.sd7` decides whether the disclosure is due, `refresh` calls it on the way to `publish`, and `tools/rf10_probe.sh` makes the measurement re-runnable from the repo.

**Tech Stack:** Seed7 5.4.10 (`s7`, `s7c`), the 18 unit suites in `tests/` graded from their `N checks, M failed` line, and `tests/transcript.py` driving the real process over real frames.

**Spec:** no spec file in this tree (the design doc was deleted in `fca09be` and has no successor). Authority is LSP 3.18 `textDocument/didOpen` — "The document's content is now managed by the client and **the server must not try to read the document's content using the document's Uri**" — `AGENTS.md` § *Do not "fix" these* (R-F10), and `README.md` § *What does not work yet*.

## Global Constraints

- Red first: write the check, run it, confirm it fails for the reason named, then implement. `make test` before and after.
- `AGENTS.md` invariant 1: only `src/analysis.sd7` imports `progs.s7i`. No new file may.
- `AGENTS.md` invariant 4: `analysis.sd7` returns Seed7-shaped data and builds no LSP shape; the disclosure is a `Diagnostic` payload, so it is decided in `lsp_server.sd7` and serialised by `diagnostics.sd7`'s existing `diagnosticsJson`.
- `AGENTS.md` invariant 7: outbound text goes through `jsonw.sd7`. The message is ASCII and reaches the writer as `addStr(w, LIB_STALE_MESSAGE)`, which `diagnosticsJson` already does for every message.
- Nothing new may raise on the request path; no raise may reach stdout.
- `docs/PROJECT_GRAPH.md` is generated and byte-compared by `tests/graph_test.sh`, so any `src/` line-count change regenerates it in the same commit.
- `tools/agents_required.txt` freezes 44 tokens grepped over `AGENTS.md` + `docs/seed7-cli.md`; tokens whose host sentence is reworded print MISSING — and `## `-prefixed tokens are checked in `AGENTS.md` alone.
- Do not run `make -j`: `tests/graph_test.sh:17-19` uses fixed `/tmp/g1`, `/tmp/s1`.

## Review Focus

- A `.sd7` buffer must never receive the disclosure — it is analysed from the text the client sent, so the sentence would be false. Pinned in Task 2's unit checks and Task 3's second wire check.
- A `.s7i` buffer whose text already matches disk still gets it. That is deliberate: the analysis is the disk's either way, and "differs from disk" would also be a per-keystroke read of the file. Recorded in Task 2 Step 4.
- An untrusted `.s7i` outside the declared roots must publish nothing at all. `refresh`'s existing `if analysable(uri)` gate wraps the new call, and that placement is checked after editing, not assumed.
- Repeats: one disclosure per publish, never two in the same list. `mapDiagnostics` dedupes on `line:column:message`, and the new record is appended after that map, so the dedupe is not what makes this true — Task 3's per-publish grouping is.
- The disclosure is `Information` (3), not `Error` (1): a client that badges errors would otherwise show a code fault the user did not write. Same severity class `mapDiagnostics` already uses for `END OF FILE` and `SYSTEM_MAIN_MISSING`.

---

### Task 1: Put the measurement in the repo, where it can be re-run

The plan's shape rests on one figure: an open library's own text is not analysable for a large minority of libraries. That was measured in `/tmp` on 2026-10-29, so today it is unciteable.

**Files:**
- Create: `tools/rf10_probe.sh`
- Create: `docs/rf10-measurement.md` (the probe's output, committed)

**Interfaces:**
- Consumes: `s7c`, and the interpreter's own `lib/` (default `/home/username/seed7/lib`, overridable as `$1` the way `tools/corpus_scan.sh` does).
- Produces: the figures `docs/seed7-cli.md` quotes in Task 4. No `src/` symbol, nothing wired into `make test`.

- [ ] **Step 1: Write the probe**

`tools/rf10_probe.sh` runs one Seed7 program over every top-level `"$SEED7"/lib/*.s7i` — the domain of the claim, since `textToAnalyze` reaches the driver only for a `.s7i` path — plus one `prg/*.sd7` file as a labelled `CONTROL` row outside the aggregate. It prints, per file, both routes of the same analysis:

- `DRIVER` — the result of calling `analysis.sd7`'s own `driverFor(path)`, which the probe obtains by including that module with `-l src` (the same way `tools/corpus_scan.sh`'s driver includes `scan.sd7` and `occurrences.sd7`). What the server does today, word for word: the interpreter opens the document's own path. **Do not retype the driver string in the probe** — a hand copy stops describing the server the moment `driverFor` changes, silently.
- `LEAD` — `$ include "seed7_05.s7i";` followed by the file's own text. The buffer's text, no uri involved.

For each, print `CLEAN`/`NOISY`, `errorCount`, `length(globalObjects(prog))`, the count of records whose `file(obj)` is `"STRING"`, and the first error's `message` when there is one. Read files with a `readln` loop — `gets(f, -1)` raises `RANGE_ERROR` (`AGENTS.md`). End with the sentinel line, which is what the harness requires before any payload counts as a result:

```
SENTINEL files=<N> leadClean=<N> leadNoisy=<N> recordsSame=<N>
```

Exit non-zero if the `lib` directory is unreadable or the compile fails. Heredoc the program into `mktemp -d` with `trap 'rm -rf "$WORK"' EXIT`, compile `s7c -O2 -l "$SEED7/lib"`, run the binary. Header comment states it is deliberately **not** in `make test` — two analyze phases per library file — same policy as `tools/corpus_scan.sh:13-14`. Measured cost of the full run: 40 s wall for the 214 libraries plus the control (22 s of that is the analysis loop, ~5 s the compile), so it is minutes-scale only on a slower machine; say "one analyze phase per library per route", not a wall figure.

- [ ] **Step 2: Run it over the libraries**

```bash
sh tools/rf10_probe.sh > docs/rf10-measurement.md.tmp && mv docs/rf10-measurement.md.tmp docs/rf10-measurement.md
tail -1 docs/rf10-measurement.md
```

Expected `SENTINEL`, the `CONTROL` row, and these rows among the output (all measured 2026-10-29 against `~/seed7` at `c93282a6`):

| file | `DRIVER` | `LEAD` |
|---|---|---|
| `lib/strifile.s7i` | 0 errors | 0 errors, 17 records report `STRING` |
| `lib/json.s7i` | 0 errors | 0 errors, 92 `STRING` |
| `lib/bigint.s7i` | 0 errors | 0 errors, 66 `STRING` |
| `lib/basearray.s7i` | 0 errors | **2** errors, first `Redeclaration of "array [ (val integer: minIdx) .. ] (val type: baseType)"` |
| `lib/null_file.s7i` | 0 errors | **44** errors, first `Redeclaration of "null_file"` |
| aggregate over the 214 top-level libraries | — | **184 clean / 30 noisy**, of which **29 are the `Redeclaration` split**; records agree for 213 (the disagreement is `seed7_05.s7i`: 3060 against 3061) |

Two figures were refuted on the way here and must not be re-restated: the scratch probe's
`recordsSame=178` came from comparing formatted rows at a fixed byte position, and the first UTF-8
run's `leadNoisy=46` counted 16 rows the probe's own byte-per-character file read produced. Both are
in `docs/rf10-measurement.md`'s history, not in its current numbers. |

If the new run disagrees, the new run wins: put the fresh numbers in `docs/seed7-cli.md` (Task 4) and correct the table above in the same commit.

- [ ] **Step 3: Prove the probe distinguishes the routes**

One edit: make `LEAD` pass the file's text **without** the essential include (`probe(textOf(path), dirs)`). Re-run and expect `leadNoisy` to jump — `lib/strifile.s7i` then reports `1731` errors, first `Expression expected found const`, `STRING=0`, while `prg/hello.sd7` stays clean, because a program is a whole program and a library is not. That contrast is the control: it shows the probe grades the route, not the file list. Restore, re-run, confirm the `SENTINEL` row is back to Step 2's figures.

- [ ] **Step 4: Commit**

```bash
git add tools/rf10_probe.sh docs/rf10-measurement.md
git commit -m "rf10: make the reason driverFor stays a re-runnable measurement"
```
Say in the body that these are measurements of code that already works, taken after the fact, with the mutation that proves the probe can tell the routes apart (`AGENTS.md` § *Every change*).

---

### Task 2: Decide and publish the disclosure

**Files:**
- Modify: `src/lsp_server.sd7` (one `const string:`, one `const func array lspDiag:` above `refresh`, one call inside `refresh`)
- Modify: `src/diagnostics.sd7` only if Step 3's aggregate comparison turns out to need a `severity`-aware printer — it should not
- Test: `tests/lsp_server_test.sd7`
- Modify: `docs/PROJECT_GRAPH.md` (regenerated)

**Interfaces:**
- Consumes: `uris.isLibraryBufferPath(path)` and `uris.pathOf` — `isLibraryBufferPath` is the one spelling of "is this a library buffer", read today by `textToAnalyze` and by `features/prepare_rename.sd7`'s refusal arm. `diagnostics.SEV_INFORMATION`. `analysis.lspDiag` fields `line1` / `column1` / `message` / `severity`.
- Produces: `discloseStaleLibrary (in array lspDiag: mapped, in string: uri) -> array lspDiag` in `src/lsp_server.sd7`, and `const string: LIB_STALE_MESSAGE` in the same file. Task 2's suite calls `discloseStaleLibrary` directly; Task 3 reads the frame `refresh` publishes.

`refresh` writes to the protocol channel, which a unit suite cannot capture — so the decision is one pure function that both `refresh` and the suite can call. That is why this task splits the decision from the publish.

- [ ] **Step 1: Write the checks**

In `tests/lsp_server_test.sd7`, near the existing `.s7i` block (`libPath`/`libUri` at `:183-184`). Helpers are suite-local: `describe` renders an `array lspDiag` as `severity|` + the first TWO words of each message joined by `|`; `oneError()` is a ONE-RECORD `array lspDiag` — one row with `severity := SEV_ERROR` and `message := "syntax error and more"` — not a bare `lspDiag`, because Seed7 converts no scalar to an array and the parameter is `in array lspDiag: mapped`. Measured with a ten-line probe (a `const func integer: take (in array rec: rows)` called with a single `rec`): `*** p1.sd7(24):57: Match for take(one) failed`, then `Declaration of "main" failed`; `take([](one))` returns 1. `tests/diagnostics_test.sd7:11-13` is the house precedent for a one-record list. Found while implementing Task 2, which is why the brief's original gloss ("one `lspDiag`") is corrected here rather than in the code.

Two words, because `lsp_tst.sd7:11-16` prints on plain `stdout` and a longer excerpt — or the analyzer's own quote-bearing text — can hold a byte Seed7's writer refuses, which would cost the suite its graded line rather than name one FAIL. No check indexes the returned array, for the same reason: a mutant that drops the append would raise `INDEX_ERROR` on stdout instead of failing a check.

```seed7
check("a .s7i buffer gains exactly the disclosure",
      describe(discloseStaleLibrary(oneError(), libUri)), "1|syntax error|3|unsaved edits");
check("a .sd7 document gains nothing",
      describe(discloseStaleLibrary(oneError(), "file:///tmp/seed7_lsp_syms.sd7")),
      "1|syntax error");
check("and the disclosure is Information, not Error",
      describe(discloseStaleLibrary(0 times lspDiag.value, libUri)), "3|unsaved edits");
```

- [ ] **Step 2: Run it and read the failure**

```bash
make test-lsp_server
```

Expected: the recipe's `grep -E '^[a-z0-9_]+: [0-9]+ checks, 0 failed$'` finds no match, because the suite does not analyse — `discloseStaleLibrary` is undeclared — so it prints nothing and exits 0, and the grade is what fails. That is the red, and it is a *different* red from a value mismatch: Step 3's stub exists precisely so Step 4 produces the value kind.

- [ ] **Step 3: Stub the function so the checks run**

Add the signature with the body `out := mapped;` and nothing else, then `make test-lsp_server`. Expected: `lsp_server: 82 checks, 2 failed` — `a .s7i buffer gains exactly the disclosure` (prints `1|syntax error`) and `and the disclosure is Information, not Error` (prints the empty `describe` of an empty list) FAIL on their values; `a .sd7 document gains nothing` passes for the wrong reason, which is the check Step 5's mutant 1 kills.

- [ ] **Step 4: Implement**

```seed7
# The one sentence R-F10 owes the user. analysis.sd7's driverFor(path) is how a library
# gets analysed, because the interpreter will not take a library's own text once that
# library is inside seed7_05.s7i's include closure -- measured in docs/rf10-measurement.md:
# 184 of the 214 top-level libraries analyse clean from text and 29 redeclare (basearray 2
# names, null_file 44); the 30th, multiscr.s7i, is NOISY on either route, so it is not a split.
# So the symbols, ranges and prose an open .s7i shows are the
# FILE's, and an unsaved edit is invisible -- including when the buffer already matches disk,
# which is why no comparison is made and no second read is paid per keystroke. The write path
# already refuses on this same predicate.
const string: LIB_STALE_MESSAGE is
  "unsaved edits in this library are not analysed: the outline, hover, completion"
  <& " and the diagnostics come from the file on disk";

const func array lspDiag: discloseStaleLibrary (in array lspDiag: mapped,
                                                in string: uri) is func
  result
    var array lspDiag: out is 0 times lspDiag.value;
  local
    var lspDiag: stale is lspDiag.value;
  begin
    out := mapped;
    if isLibraryBufferPath(pathOf(uri)) then
      stale.line1 := 1;
      stale.column1 := 0;
      stale.message := LIB_STALE_MESSAGE;
      stale.severity := SEV_INFORMATION;
      out &:= stale;
    end if;
  end func;
```

In `refresh`, inside the existing `if analysable(uri)` body, one call between the mapping and the publish:

```seed7
      mapped := mapDiagnostics(a.diags, MAX_DIAGNOSTICS);
      publish(uri, openDocs[uri], discloseStaleLibrary(mapped, uri));
```

Two placements are load-bearing and are read back out of the file after the edit, not assumed: the call stays inside `if analysable(uri)` (an untrusted buffer must still publish nothing), and `didClose`'s `publish(uri, openDocs[uri], 0 times lspDiag.value)` is left alone (a close clears the disclosure instead of re-adding it).

Landing after `mapDiagnostics` means `MAX_DIAGNOSTICS` caps the analyzer's rows and the disclosure is the one record a capped document always sees.

- [ ] **Step 5: Run, regenerate, prove the checks can fail**

```bash
make test-lsp_server && make graph && make test-graph
```

Expected: `lsp_server: 82 checks, 0 failed`, `graph: 21 checks, 0 failed`, and the `lsp_server.sd7` row carrying the new line count. Then two mutants, one at a time, each reverted with `git checkout HEAD -- src/lsp_server.sd7` (never `git checkout -- .`, which reads the index):

1. Guard → `if TRUE then`: `a .sd7 document gains nothing` FAILs.
2. `SEV_INFORMATION` → `SEV_ERROR`: `and the disclosure is Information, not Error` FAILs, and the first check FAILs with it (`3|` becomes `1|`).

- [ ] **Step 6: Commit**

```bash
git add src/lsp_server.sd7 tests/lsp_server_test.sd7 docs/PROJECT_GRAPH.md
git commit -m "rf10: tell an open .s7i buffer that its analysis is the file on disk"
```

---

### Task 3: Pin the frame the editor reads

The unit suite proves the decision. The wire proves the notification: that the disclosure arrives on `textDocument/publishDiagnostics`, once per publish, that `didClose` clears it, and that a `.sd7` document in the same session never sees it.

**Files:**
- Modify: `tests/transcript.py` (the `.s7i` scenario at `:870-954`, which writes `/tmp/seed7_lsp_transcript_rn_lib.s7i`, opens it, asks `references`/`prepareRename`/`rename`, and asserts the two refusal-log orderings). `S7I_MSGS` at `:897-906` ends `shutdown(123), exit_()` with **no `didClose`**.
- Modify: nothing in `src/`

**Interfaces:**
- Consumes: `replies` / `split_frames` (`junk == 0`), `RN_LIB_URI`, `expect`, `one_answer_per_request` (`:405-413`), `closed(uri)` (`:108-109`, which sends `textDocument/didClose` with `td(uri)`), `lib_log()` (`:924-937`).
- Produces: the six check titles Step 2 prints. `LIB_STALE` is the module-level constant holding the
  full sentence, verbatim as `src/lsp_server.sd7` spells it: `"unsaved edits in this library are not
  analysed: the outline, hover, completion and the diagnostics come from the file on disk"`. Define it
  once beside `RN_LIB_TEXT`, measured value:
  `"unsaved edits in this library are not analysed: the outline, hover, completion and the diagnostics
  come from the file on disk"`. A substring check would let the tail of the sentence rot unnoticed,
  and this is the only place the whole text can be asserted — the Seed7 suite must print ASCII and
  therefore compares two words, and `tools/agents_gate.sh` greps only `AGENTS.md` and
  `docs/seed7-cli.md`, so quoting the sentence in Task 4 pins nothing against the constant.

  The range is measured, not assumed: `line1 := 1` / `column1 := 0` reach `diagnosticsJson`, whose
  zero-column arm asks `lspRangeBytes` for `2147483647` and lets it clamp, so the published range is
  `{"start":{"line":0,"character":0},"end":{"line":0,"character":33}}` for this fixture — `RL[0]` is
  `const type: Counter is new struct`, 33 ASCII characters. Do not write `{"line":1,"character":0}`
  here: that is what a whole-line *range* looks like in `lspWholeLine`, and this row does not go
  through `lspWholeLine`.

- [ ] **Step 1: Add the close frame and the checks**

Insert `closed(RN_LIB_URI)` before `shutdown(123)` in `S7I_MSGS`, and insert `msgs[2]`, `msgs[3]` — the `.sd7` `didOpen`/`didChange` of `/tmp/tt_a.sd7` — before `opened(RN_LIB_URI, RN_LIB_TEXT)` as the control document for the disclosure's negative check. Then grade the frames — not `LIB_MSGS`, which holds log text only — grouped per publish notification, so "once" means once per publish rather than once per session:

```python
RN_PUBS = [r["params"]["diagnostics"] for r in replies
           if r.get("method") == "textDocument/publishDiagnostics"
           and r["params"]["uri"] == RN_LIB_URI]
RN_DIS = [[d for d in p if "unsaved edits in this library" in d.get("message", "")]
          for p in RN_PUBS]
expect(len(RN_PUBS) >= 2 and all(len(x) == 1 for x in RN_DIS[:-1]),
       "the .s7i buffer is told once per publish that its analysis is the file on disk (%s)"
       % [len(x) for x in RN_DIS])
expect(all(d["severity"] == 3 for x in RN_DIS for d in x),
       "and the disclosure is Information, so a client does not badge it as a code error")
expect(all(d["message"] == LIB_STALE for x in RN_DIS for d in x),
       "and it is the whole sentence the user reads, not a prefix of it (%s)"
       % [d["message"] for x in RN_DIS for d in x])
expect(all(d["range"] == {"start": {"line": 0, "character": 0},
                          "end": {"line": 0, "character": len(RL[0])}}
           for x in RN_DIS for d in x),
       "and its range is the whole first line of the buffer (%s)"
       % [d["range"] for x in RN_DIS for d in x])
expect(RN_PUBS and RN_PUBS[-1] == [],
       "and didClose still clears the buffer, disclosure included (%s)" % RN_PUBS[-1:])
RN_STALE_BY_URI = [(r["params"]["uri"],
                    len([d for d in r["params"]["diagnostics"]
                         if "unsaved edits in this library" in d.get("message", "")]))
                   for r in replies if r.get("method") == "textDocument/publishDiagnostics"]
expect(all(n == 0 for uri, n in RN_STALE_BY_URI if uri != RN_LIB_URI)
       and any(uri != RN_LIB_URI for uri, _ in RN_STALE_BY_URI),
       "and no other document in the run receives it: the disclosure is a property of a .s7i path, "
       "never of a buffer analysed from the client's own text (%s)" % RN_STALE_BY_URI)
```

The sixth check is the load-bearing one, and it was vacuous as first briefed: this plan credited `msgs[1]` with opening a `.sd7` document, but `msgs[1]` is the `initialized` notification, so the run held no second uri and `all(...)` over "everything that is not `RN_LIB_URI`" could only pass — Step 3's mutant 2 reddened nothing. The control frames are `msgs[2]`/`msgs[3]` and are added to this scenario deliberately, and the check is per uri and per publish, requiring the control to have published, so a future third document cannot make it vacuous again. Leave the `lib_log()` ordering checks alone — they pin the refusal half, which this plan does not touch.

- [ ] **Step 2: Run it**

```bash
make transcript
```

Expected: `transcript: 202 checks, 0 failed` (196 + 6), `code == 0` (the scenario still shuts down before `exit`), and `junk == 0` on every scenario — the astral and surrogate ones included, because a new byte on the protocol channel is the failure class those checks exist to catch.

- [ ] **Step 3: Prove the wire checks can fail**

Three mutants, one at a time, each reverted with `git checkout HEAD -- <file>`:

1. Pass `mapped` to `publish` in `refresh` (drop the `discloseStaleLibrary` call): `transcript: 201 checks, 1 failed` — the once-per-publish check. Measured on this branch, and the wire reddens **alone**: `make test-lsp_server` stayed `82 checks, 0 failed`, because Task 2's suite calls the pure `discloseStaleLibrary` and cannot see its call site in `refresh`. So the cross-suite proof this step wanted is mutant 2, which reddens both suites.
2. Guard → `if TRUE then`: the "no other document" check FAILs, and five pre-existing empty-list pins FAIL with it (`fixed file clears diagnostics`, the astral GAP, the escape notification, the based-literal fixture, the versionless change) — that is what a disclosure sent to every buffer looks like on this wire — while `make test-lsp_server` reads `82 checks, 1 failed` (`a .sd7 document gains nothing`). The disclosure's own five checks stay green. This needs the `msgs[2]`/`msgs[3]` control frames in the run: a build that discloses to every buffer has to have a non-library publish to disclose to.
3. `stale.column1 := 0` → `stale.column1 := 7`. Nothing in the Seed7 suite can see it — `describe` prints severity and two words — so this is the mutant that justifies the range assertion above: the range check FAILs, `transcript: 201 checks, 1 failed`, the failing row reporting `0:6 → 0:7`. Revert per file; anchor any `sed` you use, because an unanchored pattern has already matched `textToAnalyze` once in this branch's history.

(`didClose` cannot be given the disclosure as a fourth mutant without editing the close path, which is out of scope here; the `RN_PUBS[-1] == []` check is what stands guard over it.)

Read the totals as the harness prints them: `transcript.py:1656` prints the count of **passing** checks, so a 202-check run with one failure reads `201 checks, 1 failed`. `make transcript` gates on the exit code, not on the number.

- [ ] **Step 4: Commit**

```bash
git add tests/transcript.py docs/superpowers/plans/2026-10-29-rf10-disclosure.md
git commit -m "rf10: pin the .s7i disclosure on the wire, with a .sd7 control and didClose's clear"
```

---

### Task 4: Put the sentences where the rules live

**Files:**
- Modify: `README.md` (§ *What works* diagnostics sentence, § *What does not work yet* R-F10 bullet)
- Modify: `AGENTS.md` (§ *Protocol decisions that are easy to undo by accident* and § *Do not "fix" these*)
- Modify: `docs/seed7-cli.md` (new section under *AGENTS.md provenance*)

- [ ] **Step 1: Check which frozen tokens the edits touch**

```bash
grep -nFf tools/agents_required.txt AGENTS.md | head -50
```

`tools/agents_gate.sh` greps its 44 tokens over the union of `AGENTS.md` and `docs/seed7-cli.md`, and `## `-prefixed tokens in `AGENTS.md` alone. A token whose only host sentence is being reworded prints MISSING and reddens `make test-agents` — `docs/seed7-cli.md` § *Citation defect, counted and closed* records what happened last time a document about a wrong citation propped up the net that guards it. Substitute into the new wording; do not add a token beside a stale one.

- [ ] **Step 2: The two rule sentences**

`AGENTS.md` § *Do not "fix" these*, the R-F10 bullet: keep the sentence, and add that `refresh` publishes one `Information` diagnostic saying it, plus the measured reason the route stays — `basearray.s7i` redeclares 2 names and `null_file.s7i` 44 when analysed from their own text; 184 of the 214 libraries are clean and 30 are not, of which 29 are the redeclaration split. `README.md` § *What does not work yet*: the `.s7i` staleness clause gains "and the server says so in the buffer". § *What works*: the diagnostics sentence gains one clause naming the disclosure. The limitation stays open; only the silence closes.

- [ ] **Step 3: The per-suite figure in the same row**

`docs/seed7-cli.md:394` is one row carrying four per-suite figures *and* a total: `21 suites, 1064 checks:
scan 66, features 191, lsp_server 79, transcript 196`. This branch moves three of them — `lsp_server` 79 →
**82** (Task 2), `transcript` 196 → **202** (Task 3), `doc_index` 10 → **11** (Task 5) — and the total
1064 → **1074**. Correct all four in one edit, leave `scan` and `features` alone, and keep the row's
parenthetical explaining that the older `1040`/`1061` figures measured an earlier tree: that sentence is
what a reader needs when the numbers do not add up to memory. Re-read the row afterwards — a totals row
disagreeing with its own per-suite list is the class of wrong number this file already documents twice.

- [ ] **Step 4: The provenance section**

`docs/seed7-cli.md`: `R-F10 — the two routes, measured`, holding the `sh tools/rf10_probe.sh` command, the six rows of Task 1's table, the `SENTINEL` line as it came out of the committed `docs/rf10-measurement.md`, and the temp-copy result — a scratch path holding the buffer text gives the same `2` and `44`, because the real library is already inside `seed7_05.s7i`'s closure.

- [ ] **Step 5: Run everything**

```bash
make test
```

Expected: 21 graded lines, each `0 failed`, totalling **1 074** checks — the 1 064 recorded at `docs/seed7-cli.md:394`, plus Task 2's three unit checks, Task 3's six wire checks and Task 5's one `doc_index` check. This task runs **last**, after Task 5, which is why its arithmetic includes a check from a task that comes after it in the file. If the run disagrees with that number, the run wins: correct this line, not the suites, and say so in the commit body.

- [ ] **Step 6: Commit**

```bash
git add README.md AGENTS.md docs/seed7-cli.md
git commit -m "docs: record the R-F10 disclosure and the measured reason driverFor stays"
```

---

## Definition of done

- An open `.s7i` publishes exactly one `Information` diagnostic per publish saying the analysis is the file on disk; no other document does; `didClose` publishes the empty list.
- `docs/rf10-measurement.md` is in the tree, produced by `tools/rf10_probe.sh`, and Task 1 Step 3 proves the probe distinguishes the two routes.
- Two mutants in Task 2 Step 5 and three in Task 3 Step 3 each redden a named check; Task 3 Step 3's mutant 1 reddens both suites.
- `make test` green — 21 graded lines, `0 failed` each; `git status --porcelain -uall` empty.

## Out of scope

- Any change to `textToAnalyze`, `driverFor` or an analysis route. Task 1 is the evidence for that sentence, and it is now re-runnable.
- Lifting the `rename` / `prepareRename` refusal inside a `.s7i`. That arm reads the same `isLibraryBufferPath` and its reason stands.
- Comparing the buffer to disk before disclosing. It would buy silence for a pristine buffer at the cost of a read and a comparison per keystroke, and the analysis is the disk's either way.
- Request-`id` fidelity (`{"id":"42"}` is answered with `id: 0`, and an unknown string-id method is answered not at all). Measured, and it is a hang rather than a cosmetic mismatch, so it is planned in its own file, `2026-10-29-request-id-fidelity.md`. Nothing here depends on it.

## Measured, and therefore NOT planned

- **The reachable `-32603`.** A review claimed a float in an integer slot costs the request because `integer(str(v))` raises `NUMERIC_ERROR`. Refuted by measurement: `readJson` keeps a number's **source text** (`str(jsonValue)` of `10.5` is `"10.5"`, not `"10.500000"`), and `integer("10.5")` raises `RANGE_ERROR` — the one `intAt` already catches. Against the real process: 24 well-framed hostile bodies (`"character":10.5`, `"line":"3"`, `"line":1e999`, ids `0.5/true/null/[1]/"42"`, `params` as array/string/`null`, `positions:null`, `context:null`, `newName` as an object, bodies that are a number/string/`null`/array/bool, a 5-deep nest) and 12 hostile request shapes (positions past EOF, negative positions, `semanticTokens/range` to line 100000, an empty document, an unclosed `if` with no trailing newline, `http:` and `untitled:` uris, no `rootUri`) → **`-32603` in none of them**, `junk == 0` in all, exit status always 0. `AGENTS.md`'s "keep the net, it is unreachable" stands as written.
- **Analysing an open library from its own text.** Task 1 measures it and 29 of 214 libraries say no, `null_file.s7i` among them with 44 redeclarations.
- **Hovering the character after an identifier.** `wordAt` is left-of-character and `transcript.py` pins it; probing eglot's exact bounds produced correct answers, so there is nothing to fix and no task here.

## Start here

`src/lsp_server.sd7`'s `refresh` and `uris.sd7`'s `isLibraryBufferPath`, then `docs/rf10-measurement.md` for why nothing else changes.

---

### Task 5: Read the library's prose as UTF-8 (found while verifying Task 1's fix)

**Why this task exists:** the same byte-per-character read that contaminated Task 1's probe is in the
product. `src/doc_index.sd7:14-16` reads a library with `open(path, "r")`, so `(** … *)` documentation
holding non-ASCII reaches hover as latin-1 decompositions. Measured on real input: `proseFor` of
`/home/username/seed7/lib/asn1.s7i` line 372 (the comment above `genAsn1String`) returns 314
characters containing the runs `U+00E2 U+0082 U+00AC` and `U+00C3 U+00A2` — the same probe on a
two-character fixture (`¡` and `€` in a `(** … *)` comment) answers `34/5` where the honest answer is
`31/2` — the bytes of an
`–` and a `¢` read one per character. Five libraries carry non-ASCII inside a `(** … *)` comment:
`asn1.s7i`, `bytedata.s7i`, `lzma.s7i`, `scanjson.s7i`, `unicode.s7i`.

**Files:**
- Modify: `src/doc_index.sd7` (`readLinesOf`, `:10-28`)
- Test: `tests/doc_index_test.sd7`
- Modify: `docs/PROJECT_GRAPH.md` (regenerated)

**Interfaces:**
- Consumes: `utf8.s7i`'s `openUtf8 (in string: path, in string: mode) is func file` (`lib/utf8.s7i:91`).
- Produces: no new symbol. `proseFor` and `proseForText` keep their signatures; the change is which
  reader `readLinesOf` uses, and the fix must not disturb the `proseIn` walk over an in-memory string.

- [ ] **Step 1: Write the failing check**

`tests/doc_index_test.sd7` builds its fixture with 20 `write(out, …)` calls on a plain file; that cannot
produce the defect, because a plain Seed7 write emits one byte per character and the round trip is
self-consistent. So write a *second* fixture with `openUtf8(path, "w")` containing a `(** … *)` comment
whose body holds one non-ASCII character (`'¡'`, `chr(161)`), one declaration below it, then assert the
prose that comes back is the same character:

```seed7
check("prose keeps a non-ASCII character as one character",
      str(length(proseFor(nonAsciiPath, declLine1))) <& "/" <&
      str(countCharsAbove127(proseFor(nonAsciiPath, declLine1))), "<N>/1");
```

Both numbers are measured, on the fixture above: the buggy reader answers **`34/5`** and the fixed
reader answers **`31/2`** — `€` is three bytes, so the broken read contributes three characters in
`U+0080`–`U+00BF` where the fixed read contributes one, and `¡` contributes two where it should
contribute one. `countCharsAbove127` is a suite-local loop, one comparison per character (`AGENTS.md`:
a long `and`/`or` chain can fail to match). Note the line number the fixture needs: with the four-line
body above, the declaration is line **4**, and `proseFor(path, 5)` answers `""` because line 5 is past
it — the empty answer would make the check pass for the wrong reason, so assert the fixed pair, never
merely "no non-ASCII".

- [ ] **Step 2: Run it and confirm the reason**

```bash
make test-doc_index
```

Expected: `doc_index: 11 checks, 1 failed` (10 baseline + 1), the new check's `got:` reading `34/5`. If the suite prints no graded line, the fixture write or the helper does not compile —
fix that before claiming the red.

- [ ] **Step 3: Implement, then run the whole gate**

`include "utf8.s7i";` in `src/doc_index.sd7` and `f := openUtf8(path, "r");` at `:14`. Nothing else: the
`eof`/`readln`/`close` loop is already correct, and `proseForText` must stay as it is because it walks
text that never touched a file.

```bash
make test-doc_index && make graph && make test-graph && make test
```

Expected: `doc_index: 11 checks, 0 failed`, `graph: 21 checks, 0 failed`, 21 graded lines each
`0 failed` — and check `docs/PROJECT_GRAPH.md`'s `doc_index.sd7` row carries the new line count.

- [ ] **Step 4: Prove the check can fail, both ways**

1. Revert the reader to `open(path, "r")` with the UTF-8 fixture: the new check FAILs on its count.
   Revert per file with `git checkout HEAD -- src/doc_index.sd7`.
2. Feed `proseFor` a path that does not exist: it must still answer `""`, proving the
   `catch FILE_ERROR` arm in `readLinesOf` is intact after the reader swap — that arm is what keeps a
   missing library off the protocol channel, and it is reachable (unlike Task 1's, because here the
   path comes from reflection about a file the client may have deleted).

- [ ] **Step 5: Commit**

```bash
git add src/doc_index.sd7 tests/doc_index_test.sd7 docs/PROJECT_GRAPH.md
git commit -m "fix: read library documentation as UTF-8, so hover prose is not latin-1 bytes"
```
