# R-F10 Disclosure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tell the user, in the document they are looking at, that an open `.s7i` buffer is analysed from the file on disk — so an unsaved library edit no longer reads as a clean document.

**Architecture:** The server keeps its current route for libraries (`analysis.sd7`'s `driverFor(path)`, which makes the interpreter read the file), because the interpreter will not analyse a library from its own text once that library is already inside `seed7_05.s7i`'s include closure — the buffer's declarations then re-declare the closure's. One `Information` diagnostic is appended in `lsp_server.sd7`'s `refresh`, on the same predicate the existing write refusals already read, and the measured reason for the limitation is recorded as a re-runnable probe in `tools/`.

**Tech Stack:** Seed7 5.4.10 (`s7`, `s7c`), the repo's own suites in `tests/` graded from their `N checks, M failed` line, and `tests/transcript.py` driving the real process over real frames.

**Spec:** no spec file in this tree. The authority is LSP 3.18 `textDocument/didOpen` ("the server must not try to read the document's content using the document's Uri"), `AGENTS.md` § *Do not "fix" these* (R-F10), and `README.md` § *What does not work yet*. The measurements that decide the shape are in this plan's Task 1.

## Global Constraints

- Red first: write the check, run it, confirm it fails for the reason named, then implement. `make test` before and after.
- `AGENTS.md` invariant 5: a capability is advertised only once its method is answered. This plan advertises nothing new.
- `AGENTS.md` invariant 7: outbound text goes through `jsonw.sd7`. No `addStr(w, str(` anywhere.
- `AGENTS.md` invariant 3: `transport.sd7` owns every outbound byte count. This plan emits none.
- The `-32603` net in `main.sd7` stays unreachable. Nothing in this plan may raise, and no raise may reach stdout.
- Severity for a truncated-buffer class message stays `Information` (3): `diagnostics.sd7` already defines `SEV_INFORMATION`.
- `docs/PROJECT_GRAPH.md` is generated and byte-compared by `tests/graph_test.sh`, so any line-count change in `src/` requires `make graph` in the same commit.
- `tools/agents_required.txt` holds 44 frozen tokens grepped over `AGENTS.md` + `docs/seed7-cli.md`. Adding prose is safe; deleting or rewording a token's host sentence reddens `make test-agents`.
- Do not run `make -j`: `tests/graph_test.sh:17-19` uses fixed `/tmp/g1`, `/tmp/s1` names.

## Review Focus

- A `.sd7` buffer must never receive the disclosure — it is analysed from the text the client sent, so the statement would be false. Pinned in Task 2.
- An untrusted `.s7i` outside the declared roots must still publish nothing: `refresh` returns early on `analysable`, so the new call must sit inside that existing `if analysable(uri)` body, never before it. Pinned by the existing trust checks (`lsp_server_test.sd7:460-476`, `transcript.py` scenario 31); Task 2 Step 5's mutant 1 is what proves the disclosure is reached only through that gate.
- `didClose` must clear the document and must not re-emit the disclosure. It is a different path — `didClose` publishes `0 times lspDiag.value` straight through `publish` and never reaches `discloseStaleLibrary` — so Task 3 adds the close frame to the `.s7i` scenario and pins that the last publish for that uri is empty.
- A repeated `didChange` must not accumulate disclosures: `refresh` maps fresh from `a.diags` on every call, so `discloseStaleLibrary` only ever appends to a freshly-mapped list. Pinned per publish in Task 3 — `len(x) == 1` for every publish, not once per session.
- The disclosure must not be counted as a *code* error by a client that shows an error badge: it carries `severity 3`, the same class `mapDiagnostics` already uses for `END OF FILE` and `SYSTEM_MAIN_MISSING`. Pinned in Task 2 and Task 3.

---

### Task 1: Record why the buffer text cannot be analysed

The plan's shape rests on one measurement. It must be re-runnable from the repo, not from a `/tmp` scratch file, or the figures in Task 4 are unciteable.

**Files:**
- Create: `tools/rf10_probe.sh`
- Create: `docs/rf10-measurement.md` (output of the probe, committed)

**Interfaces:**
- Consumes: `s7c`, the interpreter's own `lib/` directory.
- Produces: the figures Task 4 quotes. No `src/` symbol.

- [ ] **Step 1: Write the probe**

`tools/rf10_probe.sh` runs one Seed7 program over the same file list `tools/corpus_scan.sh` passes — `"$SEED7"/lib/*.s7i "$SEED7"/prg/*.sd7` — and prints, per file, both routes of the same analysis:

```
SENTINEL files=<N> leadClean=<N> leadNoisy=<N> recordsSame=<N>
```

Exit non-zero if `$SEED7/lib` is unreadable or the compile fails. Wrap the program in a heredoc into `mktemp -d` with `trap 'rm -rf "$WORK"' EXIT`, compile with `s7c -O2 -l "$SEED7/lib"`, and run the binary over the file list. It is **not** wired into `make test` — same policy as `tools/corpus_scan.sh` (`13-14`: "Not wired into `make test`, and it must not be"), for the same reason: two analyze phases per file over 343 files takes minutes (`shiftjis.s7i` alone reports `199529` errors on the `LEAD` route, measured). State that in the header comment.

- [ ] **Step 2: Run it and capture the output**

```bash
sh tools/rf10_probe.sh > docs/rf10-measurement.md.tmp && mv docs/rf10-measurement.md.tmp docs/rf10-measurement.md
```

Expected: the last line is a `SENTINEL` row, and `lib/basearray.s7i` and `lib/null_file.s7i` appear with `DRIVER 0 errors` against `LEAD` `2` and `44` redeclaration errors — `Redeclaration of "array [ (val integer: minIdx) .. ] (val type: baseType)"` and `Redeclaration of "null_file"`. `lib/strifile.s7i`, `lib/json.s7i` and `lib/bigint.s7i` must show `DRIVER 0` / `LEAD 0` with `STRING` counts of 17, 92 and 66: the routes agree there, and only there the buffer's own records would rank first.

- [ ] **Step 3: Confirm the probe can fail**

Edit the probe's `LEAD` string once, to a text that cannot redeclare (the file's own text *without* the essential include, i.e. pass `textOf(path)` alone). Re-run. Expected: `leadNoisy` jumps to 343 — `strifile.s7i` reports `1731` errors, first `Expression expected found const`, and `STRING=0` everywhere. That is the positive control: the harness grades a difference, not a tautology. Restore the `LEAD` line and re-run before committing.

- [ ] **Step 4: Commit**

```bash
git add tools/rf10_probe.sh docs/rf10-measurement.md
git commit -m "rf10: record the measured reason a library buffer cannot be analysed from its text"
```

Label the commit honestly: these are measurements of code that already works, written after the fact (`AGENTS.md` § *Every change*).

---

### Task 2: Publish the disclosure on an open `.s7i`

**Files:**
- Modify: `src/lsp_server.sd7` (`refresh`, plus one new `const string:` and one new `const func array lspDiag:` above it)
- Test: `tests/lsp_server_test.sd7`
- Modify: `docs/PROJECT_GRAPH.md` (regenerated — the module line counts change)

**Interfaces:**
- Consumes: `uris.isLibraryBufferPath(path)` and `uris.pathOf` (existing; `isLibraryBufferPath` is the one spelling of "is this a library buffer", read today by `textToAnalyze` and by `features/prepare_rename.sd7`'s refusal arm), `diagnostics.SEV_INFORMATION`, `analysis.lspDiag` fields `line1` / `column1` / `message` / `severity`.
- Produces: `discloseStaleLibrary (in array lspDiag: mapped, in string: uri) -> array lspDiag` in `src/lsp_server.sd7`, and its message text `LIB_STALE_MESSAGE`. Task 2's unit suite calls `discloseStaleLibrary` directly; Task 3 reads the frame `refresh` publishes.

`refresh` is not observable from a unit suite — it writes to the protocol channel, which `lsp_server_test.sd7` cannot capture — so the decision is one pure function that both the suite and `refresh` can call.

- [ ] **Step 1: Write the failing check**

Append to `tests/lsp_server_test.sd7`'s existing `.s7i` block (`libPath`/`libUri` at `183-184`). Build an `array lspDiag` of one Error record, run the function for a library uri and for a `.sd7` uri, and grade the aggregate as `severity|message-prefix` per record:

```seed7
check("a .s7i buffer gains exactly the disclosure",
      describe(discloseStaleLibrary(oneError(), libUri)), "1|syntax error|3|unsaved edits");
check("a .sd7 document gains nothing",
      describe(discloseStaleLibrary(oneError(), "file:///tmp/seed7_lsp_syms.sd7")),
      "1|syntax error");
check("and the disclosure is Information, not Error",
      describe(discloseStaleLibrary(0 times lspDiag.value, libUri)), "3|unsaved edits");
```

`describe` joins records as `severity|` + the first TWO words of each message, separated by `|`; `oneError()` is one `lspDiag` with `severity := SEV_ERROR` and `message := "syntax error and more"`. Two words, because the graded line must stay ASCII: `lsp_tst.sd7` prints on plain `stdout`, and a longer excerpt of a message carrying the analyzer's quote characters can hold a byte Seed7's writer refuses. No check indexes the returned array — a mutant that drops the append would then raise `INDEX_ERROR` onto stdout and cost the suite its graded line instead of naming one FAIL. All three helpers live in the suite.

- [ ] **Step 2: Add the function as a stub, so the suite can run**

A Seed7 suite that does not analyse prints nothing and exits 0 (`AGENTS.md`), so "write the test, watch it fail" needs the callee to exist first. Add the signature with the body `out := mapped;` and nothing else, then:

```bash
make test-lsp_server
```

Expected: `lsp_server: 82 checks, 2 failed` — `a .s7i buffer gains exactly the disclosure` (prints `1|syntax error`) and `and the disclosure is Information, not Error` (prints the empty `describe` of an empty list) go red on their VALUES, and `a .sd7 document gains nothing` is green for the wrong-but-harmless reason: the stub adds nothing to any document. That green is what Step 5's mutant 1 kills.

- [ ] **Step 3: Implement the decision**

Fill in the stub above `refresh`:

```seed7
# The one sentence R-F10 owes the user. A .s7i buffer is analysed through analysis.sd7's
# driverFor(path) because the interpreter refuses a library's own text -- measured, in
# docs/rf10-measurement.md: strifile/json/bigint analyse clean either way, basearray
# redeclares 2 names and null_file 44. So the symbols, ranges and prose an open .s7i gets
# are the file's, not the editor's, and an unsaved edit is invisible. Saying so is the
# whole task; the write path already refuses on the same predicate.
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

One comparison decides it; do not re-derive the `.s7i` test from the extension anywhere else (`uris.isLibraryBufferPath` is that one spelling, and `features/prepare_rename.sd7`'s refusal arm already reads it).

- [ ] **Step 4: Wire it into `refresh`, then regenerate the graph**

One call between the mapping and the publish, so the disclosure rides the same frame as the analyzer's own results and inherits the `analysable` gate above it:

```seed7
      mapped := mapDiagnostics(a.diags, MAX_DIAGNOSTICS);
      publish(uri, openDocs[uri], discloseStaleLibrary(mapped, uri));
```

It lands AFTER `mapDiagnostics`, so `MAX_DIAGNOSTICS` (100) caps the analyzer's rows and the disclosure is the one record a capped document always sees.

`src/lsp_server.sd7` grew, so the generated artifact is now stale and `make test-graph` reddens:

```bash
make graph && make test-lsp_server && make test-graph
```

Expected: `lsp_server: 82 checks, 0 failed`, `graph: 21 checks, 0 failed`, and `docs/PROJECT_GRAPH.md`'s `lsp_server.sd7` row carrying the new line count.

- [ ] **Step 5: Prove the new assertion can fail**

Mutate production twice, separately, and name the check that goes red each time:
1. `if isLibraryBufferPath(pathOf(uri)) then` → `if TRUE then`: `a .sd7 document gains nothing` FAILs.
2. `SEV_INFORMATION` → `SEV_ERROR`: `and the disclosure is Information, not Error` FAILs, and `a .s7i buffer gains exactly the disclosure` FAILs with it (`3|` becomes `1|`).

Revert per file with `git checkout HEAD -- src/lsp_server.sd7` — never `git checkout -- .`, which restores from the index and silently undoes uncommitted work.

- [ ] **Step 6: Commit**

```bash
git add src/lsp_server.sd7 tests/lsp_server_test.sd7 docs/PROJECT_GRAPH.md
git commit -m "rf10: publish an Information diagnostic when a .s7i buffer is analysed from disk"
```

---

### Task 3: Pin it on the wire

A unit check proves the function; the wire proves the frame the editor reads. The disclosure must arrive on `publishDiagnostics`, exactly once per publish, and it must not follow a `.sd7` document into the same session.

**Files:**
- Modify: `tests/transcript.py` (the `.s7i` scenario at `870-954`: it writes `/tmp/seed7_lsp_transcript_rn_lib.s7i`, opens it, asks `references`/`prepareRename`/`rename`, and asserts the two refusal-log orderings; `S7I_MSGS` today ends `shutdown(123), exit_()` with **no `didClose`**)
- Modify: nothing in `src/`

**Interfaces:**
- Consumes: `replies` / `split_frames` (`junk == 0`), the scenario's existing `RN_LIB_URI`, `expect`, `one_answer_per_request`, `closed(uri)` (`108-109`, which sends `textDocument/didClose` with `td(uri)`), and `lib_log()` (`924-937`).
- Produces: the four check titles Step 2 prints.

- [ ] **Step 1: Add the close frame and the checks**

Insert `closed(RN_LIB_URI)` before `shutdown(123)` in `S7I_MSGS`. Then grade the *frames*, not `LIB_MSGS` (log text only), the way `lib_log()` grades the refusal — by what the client receives. Group by publish notification so "exactly once" means once per publish, not once per session:

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
expect(RN_PUBS and RN_PUBS[-1] == [],
       "and didClose still clears the buffer, disclosure included (%s)" % RN_PUBS[-1:])
expect(all("unsaved edits" not in d.get("message", "")
           for r in replies if r.get("method") == "textDocument/publishDiagnostics"
           and r["params"]["uri"] != RN_LIB_URI for d in r["params"]["diagnostics"]),
       "and no other document in the run receives it")
```

The first check asserts `>= 2` publishes because the run now publishes twice: the `didOpen` (and the driver analyses a file whose text the client also sent, so it is clean) and the `didClose` empty frame. The fourth check is the load-bearing one: `S7I_MSGS` opens a `.sd7` document (`msgs[1]`) in the same session, so a disclosure that leaked onto a buffer analysed from the client's own text reddens it. Do not touch the existing `lib_log()` ordering checks; they pin the refusal half, which stays.

- [ ] **Step 2: Run it**

```bash
make transcript
```

Expected: `transcript: 200 checks, 0 failed` (196 + 4), `code == 0` (the scenario now closes before it shuts down, so the `exit` path is unchanged), and `junk == 0` on every scenario, the astral ones included.

- [ ] **Step 3: Prove the wire checks can fail**

Three mutants, one at a time, each reverted with `git checkout HEAD -- <file>`:

1. Pass `mapped` to `publish` in `refresh` (drop the `discloseStaleLibrary` call). `make transcript` → `transcript: 200 checks, 1 failed` (the once-per-publish check), **and** `make test-lsp_server` red in the same run (all three of Task 2's checks). If only the wire reddens, the two suites grade different things and the wire check is not pinning the product.
2. `discloseStaleLibrary`'s guard → `if TRUE then` → the "no other document" check goes red while the first three stay green.
3. Route `didClose`'s empty publish through `discloseStaleLibrary` (i.e. `publish(uri, openDocs[uri], discloseStaleLibrary(0 times lspDiag.value, uri))`) → the "didClose still clears" check goes red, which is the check that exists to keep that edit from looking like an improvement.

- [ ] **Step 4: Commit**

```bash
git add tests/transcript.py
git commit -m "rf10: pin the .s7i disclosure on the wire, with a .sd7 control and didClose's clear"
```

---

### Task 4: Say it in the docs, with the figures beside it

**Files:**
- Modify: `README.md` (§ *What works*, § *What does not work yet*)
- Modify: `AGENTS.md` (§ *Do not "fix" these*)
- Modify: `docs/seed7-cli.md` (new section under *AGENTS.md provenance*)

- [ ] **Step 1: README**

Move R-F10 from the unqualified list to a stated disclosure: the `.s7i` bullet gains "and the server now says so in the document" + the severity, and the *What works* line about diagnostics gains one clause naming the disclosure. Keep the "unscheduled, split out of the M3 plan" wording — the limitation is still open; only the silence is closed.

- [ ] **Step 2: AGENTS.md**

In the § *Do not "fix" these* bullet (`AGENTS.md:269-272`), replace "so unsaved library edits report stale diagnostics" with "so unsaved library edits report stale diagnostics, and `refresh` publishes one `Information` diagnostic saying so", and add the one-line reason with the two figures: `basearray.s7i` redeclares 2 names and `null_file.s7i` 44 when analysed from their own text.

This edit is gate-safe, and that is measured rather than assumed: `grep -n 'R-F10\|s7i' tools/agents_required.txt` returns only `seed7_05.s7i:280-294` (`:27`) and `utf8.s7i:132` (`:32`) — no frozen token lives in the R-F10 sentences, so rewording them cannot redden `make test-agents`. If the list has grown since this plan was written, re-run that grep before editing.

- [ ] **Step 3: docs/seed7-cli.md**

Add a section `R-F10 — the two routes, measured` holding: the exact `sh tools/rf10_probe.sh` command, the six `DRIVER`/`LEAD` rows quoted at the top of this plan, the `SENTINEL` line from `docs/rf10-measurement.md`, and the temp-copy result (a scratch path holding the buffer text gives the same `2`/`44`, because the real library is already inside `seed7_05.s7i`'s closure).

- [ ] **Step 4: Regenerate and run everything**

```bash
make graph && make test
```

Expected: 21 graded lines, each `0 failed`, summing to **1 071** checks — the 1 064 baseline plus Task 2's three unit checks and Task 3's four wire checks. If the run disagrees with that arithmetic, the run wins: correct this line, not the suites, and say so in the commit body.

- [ ] **Step 5: Commit**

```bash
git add README.md AGENTS.md docs/seed7-cli.md
git commit -m "docs: record the R-F10 disclosure and the measured reason the driver stays"
```

---

## Definition of done

- An open `.s7i` publishes exactly one `Information` diagnostic per publish saying the analysis is the file on disk; no other document does, on the unit suite and on the wire; `didClose` publishes the empty list.
- `docs/rf10-measurement.md` is in the tree, produced by `tools/rf10_probe.sh`, and the probe is proven to distinguish the routes (Task 1 Step 3).
- Two mutants in Task 2 Step 5 and three in Task 3 Step 3 each redden a named check, and Task 3 Step 3's mutant 1 reddens both suites.
- `make test` green (21 graded lines, `0 failed` each); `git status --porcelain -uall` empty.

## Out of scope

- Changing `textToAnalyze`, `driverFor`, or any analysis route. The driver stays because the interpreter refuses the alternative; Task 1 is the evidence for that sentence.
- Lifting the `rename`/`prepareRename` refusal inside a `.s7i`. That arm keys on `uris.isLibraryBufferPath` and its reason still holds.
- The raw-`id`-text question (`{"id":"42"}` answered with `id: 0`): no measured client needs it, so it stays the documented `ponytail:` decision in `src/rpc.sd7`.

## Measured, and therefore NOT planned

Two candidate changes were killed by probe before this plan was written. Both belong here so nobody re-litigates them from the review notes:

- **`intAt` is already total; the `-32603` net is still unreachable.** A review claimed a float in an integer slot costs the request (`integer(str(v))` raising `NUMERIC_ERROR`). Refuted: `readJson` keeps a number's **source text**, so `str(jsonNumber)` of `10.5` is `"10.5"`, and `integer("10.5")` raises `RANGE_ERROR` — the one `intAt` already catches. Measured against the real process: 24 well-framed hostile bodies (`"character":10.5`, `"line":"3"`, `"line":1e999`, `"id":0.5/true/null/[1]/"42"`, `params` as array/string/`null`, `positions:null`, `context:null`, `newName` as object, bodies that are a number/string/`null`/array/bool, a 5-deep nest), each followed by `shutdown`/`exit` → **`PROBE -32603 cases: none`**. Answers were `-32602`, `-32601`, `-32700`, `null`, `[]` or a result. `AGENTS.md`'s "keep the net, it is unreachable" stands as written.
- **Raw-`id` text (`{"id":"42"}` answered as `id: 0`).** Measured: the request is answered, and answered with the wrong id, so a string-id client never resolves it. This is the documented `ponytail:` decision at `src/rpc.sd7:8-11` ("every client tested … sends integers"), and no client that does it has been named. Adding the raw-id channel would be inventing a trigger, so it stays out — see Out of scope.
- **A `.s7i` analysis from the buffer's own text.** Task 1 measures it; the numbers say the interpreter re-declares (`basearray.s7i` 2 names, `null_file.s7i` 44) because the real library is already inside `seed7_05.s7i`'s closure, and a scratch copy of the buffer text does the same. So `driverFor` stays and only the silence is fixed.

---

## Start here

`src/lsp_server.sd7`'s `refresh` and `uris.sd7`'s `isLibraryBufferPath`, then `docs/rf10-measurement.md` for why nothing else changes.
