# Audit Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the six code and documentation defects the 2026-11-02 repo audit left open, and add the two gates that make the remaining class of defect (a figure or claim no command reproduces) mechanically detectable.

**Architecture:** The server stays as it is — one module per responsibility in `src/`, LSP shapes only in `src/features/`, the analyzer behind `src/analysis.sd7`, one occurrence pass per request. Three tasks change a behaviour that a client can observe; one corrects citations and deletes a dead constant; two add gates under `tools/` in the shape `tools/regions_gate.sh` and `tools/agents_gate.sh` already establish (sentinel line, labelled SKIP, verdict line in `make test`'s graded form).

**Tech Stack:** Seed7 5.4.10 (`s7 -q -l src` for the shipped interpreted server, `s7c -p -O2 -l src` for any measurement), POSIX sh, python3 (standard library only, for `tests/transcript.py`).

**Spec:** there is no design document — `docs/superpowers/specs/2026-09-10-seed7-lsp-server-design.md` was deleted in `fca09be` with no successor. The authority for each task is named in that task, and is one of: `AGENTS.md`, `docs/seed7-cli.md`, `~/seed7` (the interpreter, the parser of record), `~/Seed7Home/manual` (the prose), and the LSP 3.18 specification at <https://microsoft.github.io/language-server-protocol/specifications/lsp/3.18/specification/>. The findings themselves are the numbered items of the audit report given to the implementer on 2026-11-02 (finding 1 — the `parseError.fileName` guard — already shipped as `7f691ee` and is not re-opened here).

## Global Constraints

- Red first. Write the check, run it, confirm it fails for the reason you claim, then implement. `make test` before and after every task.
- A check that cannot fail is worse than no check. For every new assertion, mutate one production branch and name the check that goes FAIL; before demanding a mutation, confirm the mutant is not semantically identical.
- A test written after code that already works passes on sight: label it in the commit and prove it by mutation.
- Never judge an `s7` run by its exit status alone: analysis errors print on stderr and exit 1 with 0 bytes on stdout; `*** Declaration for main missing` prints on stdout and exits 0. A probe prints a sentinel the harness requires before any payload counts as a result.
- A byte count comes from the artifact the product emits — the wire `Content-Length` — never from re-serialising a parsed copy.
- Never let an exception reach stdout: stdout is the protocol channel. Any new inbound read is guarded at its own site.
- Invariants a violation of which is a defect: only `src/analysis.sd7` imports `progs.s7i`; only `src/doc_store.sd7` converts positions to offsets; only `src/utf8bytes.sd7` declares width rules and `src/transport.sd7` emits every outbound byte count; only `src/*.sd7` and `src/features/*.sd7` build LSP shapes; `renameDecision` is the only rename refusal predicate and `inScope` the only place scope is applied; outbound text goes through `jsonw.sd7` (`grep -rn 'addStr(w, str(' --include='*.sd7' src/` stays empty); a position conversion walks its own line, never the document.
- A refusal on the write path is `null`, never an error; a rejected `newName` is `-32602`.
- Never guess an `s7`/`s7c` flag: they are in `docs/seed7-cli.md` and `~/seed7/doc/s7c.1`.
- Any task that edits `src/` refreshes the committed artifact: `make graph`.
- The suite-totals row in `docs/seed7-cli.md` (the row that begins `| suite totals |`) carries every check-count delta, in the established `N → M is <wave>: <suite> A → B` form, and the claim that no other suite moved must be backed by `git diff --name-only`, not by arithmetic.
- No new dependencies. Seed7 standard library and the python standard library only.
- Figures about `~/seed7` and `~/Seed7Home` are re-measured with the same glob the tool uses (`lib/*.s7i` and `prg/*.sd7`, not `find`). A row recorded as measured at a named commit or date stays as history; only a present-tense claim is restated.

## Review Focus

The classes below are what the audit says a user hits and no existing task tests. Each line gets its assertion added to the task named.

1. **A signature list where the active overload has fewer parameters than the cursor's argument index** (T1) — the user expects the last parameter highlighted, not the first, and never an index a client is obliged to rewrite to 0.
2. **A `positions` array of exactly 32, exactly 33, and one that is not an array** (T2) — the user expects a full chain at the boundary, and a truncation that is *said* rather than silently missing at the 33rd cursor.
3. **A backslash adjacent to other special characters, and a backslash inside an unterminated string** (T3) — the user expects the token to grow like the interpreter's does and the mask to stay byte-for-byte aligned.
4. **A machine with no `~/seed7` or `~/Seed7Home` checkout, and a figure that is wrong because the document is wrong rather than because the tree moved** (T5, T6) — the gate must SKIP and say so when it cannot see the tree, and must FAIL loudly when it can.
5. **A corpus file the probe cannot decode** (`prg/err.sd7`) (T6) — the run must count it in `skips`, print its sentinel, and never append a trace line to its own artifact.

---

### Task 1: `signatureHelp` reports an active parameter a client will not rewrite

**Authority:** LSP 3.18, `SignatureHelp.activeParameter` — "If omitted or the value lies outside the range of `signatures[activeSignature].parameters`, it defaults to 0 if the active signature has parameters."

**Files:**
- Modify: `src/features/signature_help.sd7` (the claim at `:60-63`, the emit loop at `:80-100`, the `if emitted <> 0` tail at `:103-112`)
- Modify: `tests/features_test.sd7:818-827` — the existing check `an active parameter past the last one is reported, not dropped` pins the behaviour this task reverses; it is a real pin on a real call, so the commit must say the spec, not the test, wins
- Test: `tests/features_test.sd7`, `tests/transcript.py` (one wire check beside the `signatureHelp` pins at `transcript.py:1345-1360`)

**Interfaces:**
- Consumes: nothing new — `signatureHelpResult(in array symRec: syms, in string: callee, in integer: active)`, unchanged signature.
- Produces: identical JSON shape; only the value of `activeParameter` moves. No caller changes.

- [ ] **Step 1: Write the failing unit checks** in `tests/features_test.sd7`, replacing the
  existing `checkTrue("an active parameter past the last one is reported, not dropped", ...)`
  pair at `:825-826`. `hsyms` is the fixture's symbol array; every `writeln` overload in it has
  exactly 1 parameter, and `checkTrue(title, boolean)` is `src/lsp_tst.sd7`'s helper, already
  used by this suite for `pos(...)` pins (`:612`, `:626`):

```seed7
    checkTrue("an active parameter past the last one clamps to the last",
              pos(signatureHelpResult(hsyms, "writeln", 9), "\"activeParameter\":1") <> 0);
    checkTrue("and the clamped answer carries no out-of-range index",
              pos(signatureHelpResult(hsyms, "writeln", 9), "\"activeParameter\":9") = 0);
    checkTrue("index 0 survives when the active signature has one parameter",
              pos(signatureHelpResult(hsyms, "writeln", 0), "\"activeParameter\":0") <> 0);
```

The exact-string pin `one signature per overload, active parameter reported` (`:818-824`) stays
untouched: `active: 1` against a 1-parameter first signature is already in range, and it is the
check that stops the clamp from degrading into "always 0".

- [ ] **Step 2: Run the suite and confirm the named checks fail for the claimed reason**

Run: `s7 -q -l src tests/features_test.sd7 2>&1 | grep -A2 '^FAIL'`
Expected: FAIL on the first two clamp checks (`got: FALSE` — the reply still carries
`"activeParameter":9`); the third passes on sight today and is the non-regression
half, labelled as such in the commit.

- [ ] **Step 3: Implement the clamp** in `src/features/signature_help.sd7`. Stamp the first emitted signature's parameter count inside the existing loop (right after `emitted +:= 1;`), guarded so only signature 0 sets it:

```seed7
              if emitted = 1 then
                firstParams := length(syms[i].params);
              end if;
```

and use it in the tail block, replacing `activeIdx := active;` and its single negative guard:

```seed7
          activeIdx := active;
          if activeIdx < 0 then
            activeIdx := 0;
          elsif activeIdx > firstParams - 1 then
            activeIdx := max(0, firstParams - 1);
          end if;
```

Declare `var integer: firstParams is 0;` with the other locals. Rewrite the `:60-63` comment: the field is clamped to the active signature because a value past its range is normalised to 0 by the client, so reporting the raw index hides nothing but achieves nothing either. `activeSignature` stays `0` and stays explicit.

- [ ] **Step 4: Add the wire check** in `tests/transcript.py`, in the M3 signatureHelp session: request `signatureHelp` with the cursor on an argument index past every parameter of the first listed overload, and assert `"activeParameter"` is present and `<= len(signatures[0]["parameters"]) - 1`, plus `junk == 0`.
- [ ] **Step 5: Run the suites, then the whole thing**

Run: `s7 -q -l src tests/features_test.sd7 | tail -1` → `features: 193 checks, 0
failed` (191, minus the deleted `checkTrue`, plus three). Then `make test` → every
suite `0 failed`. If the run disagrees with 193, the run wins: restate the number,
never bend the suite to it.
- [ ] **Step 6: Prove the guard can fail.** Mutate `elsif activeIdx > firstParams - 1 then` to `elsif FALSE then`; the named clamp check must go FAIL. Restore by rewriting those exact bytes (`git checkout HEAD -- src/features/signature_help.sd7` would discard this task's uncommitted work in the same file).
- [ ] **Step 7: `make graph`, update the suite-totals row, commit** with the spec sentence quoted and the reversal of the old pin stated.

---

### Task 2: `selectionRange` says when it truncates

**Authority:** LSP 3.18, `textDocument/selectionRange` — "positions\[i\] must be contained in result\[i\].range"; and `AGENTS.md`'s established split: a read may over- or under-include provided it says so (`references`' `unresolved`/`why` pair, `src/features/references.sd7:22-26` and `src/lsp_server.sd7:458-459`).

**Files:**
- Modify: `src/features/selection_range.sd7` (`selectionResult` at `:107-129` returns a struct now; the `MAX_SELECT_POSITIONS` note at `:9-12` loses the false folding analogy)
- Modify: `src/lsp_server.sd7` (the `textDocument/selectionRange` arm, `:537-543`)
- Test: `tests/selection_range_test.sd7` (the existing cap pin at `:100-106` keeps its assertion — the cap is not moving), `tests/transcript.py`
- Note: `tests/graph_test.sh` counts feature *files* (`:75`) and maps suites to modules (`:212`) — it reads no signature, so the return-type change lands inside `make graph` alone and no test file other than the two above changes.

**Interfaces:**
- Consumes: `blockRegions`, `enclosingRegionsFrom`, `charIndexOf`, `tokenAt`, `lspRange`, `lspRange`-vs-`lspRangeUnits` provenance rule — all unchanged.
- Produces: `const type: selAnswer is new struct var string: json is "[]"; var boolean: truncated is FALSE; var string: why is ""; end struct;` and `const func selAnswer: selectionResult (in lsDoc: doc, in jsonValue: positions)`. `MAX_SELECT_POSITIONS` stays in this file and is read nowhere else.

- [ ] **Step 1: Write the failing unit checks.** `selOf`/`answerCount` in `tests/selection_range_test.sd7` currently call `selectionResult` and read a string; add a `selOf2` that returns the three dimensions of the answer in one row (the `diagPin` idiom), and assert:

```seed7
    # <answers>|<truncated>|<why names the cap>
    check("32 positions answers 32 and discloses nothing",
          selOf2(text, manyPositions(32)), "32|FALSE|FALSE");
    check("33 positions answers 32 and discloses the cap",
          selOf2(text, manyPositions(33)), "32|TRUE|TRUE");
    check("a non-array positions answers [] and discloses nothing",
          selOf2(text, "{}"), "0|FALSE|FALSE");
```

`selOf2` returns `str(answerCount(...)) & "|" & str(out.truncated) & "|" & str(pos(out.why, "dropped") <> 0)`. The sentence itself is pinned by the wire check in Step 5, not here, so the unit rows test the flag and the presence of an explanation. Keep `selOf` and `answerCount` for the existing rows and add `selOf2` beside them.

- [ ] **Step 2: Run it and confirm the three named checks fail** (the file does not compile against a struct yet is the expected first failure — say so in the commit rather than pretending a red assertion).

Run: `s7 -q -l src tests/selection_range_test.sd7 2>&1 | tail -4`
Expected: a `Match for` / declaration failure, then, once `selAnswer` exists, FAIL on the `32|TRUE|no` row.
- [ ] **Step 3: Implement `selAnswer`.** Keep every byte of `chainForPosition` and the hoisted `blockRegions` call. Set `out.truncated` / `out.why` on the existing `if n > MAX_SELECT_POSITIONS` branch, and make the non-array branch set `out.json := "[]"` with `truncated FALSE`. Rewrite the `:9-12` note: the cap bounds per-position work (`tokenAt` and the chain walk cost O(document) each), and unlike `foldingRange`'s `rangeLimit` this one is not a client hint, so the drop is disclosed.
- [ ] **Step 4: Wire the disclosure in the dispatcher**, in the same order as `references` — log before answer:

```seed7
        sel := selectionResult(openDocs[uri], atKey(msg.params, "positions"));
        if sel.truncated then
          logMessage(MSG_INFO, sel.why);
        end if;
        sendResult(msg, sel.json);
```

Declare `var selAnswer: sel is selAnswer.value;` in `handle`'s local block beside `refs`/`prep`/`ren`.
- [ ] **Step 5: Add the wire check** in `tests/transcript.py`: one session, a `selectionRange` request carrying 33 positions, asserting the log frame (`window/logMessage`, type 3) arrives **before** the result frame for that id, that the result holds 32 entries, and that `junk == 0`.
- [ ] **Step 6: Run the owning suites, then all of them**

Run: `make test-selection_range test-lsp_server transcript` → each prints
`0 failed`; then `make test`.
- [ ] **Step 7: Mutation proof:** delete the `if sel.truncated then` block in `src/lsp_server.sd7` → the new wire check must go FAIL; set `out.truncated := FALSE;` in the feature → the unit row `32|TRUE|no` must go FAIL. Restore exact bytes after each.
- [ ] **Step 8: `make graph`, totals row, commit.**

---

### Task 3: `\` is an operator character, as the language says it is

**Authority:** `~/Seed7Home/manual/tokens.htm` 10.2.2 (the 22 special characters include `\`) and `~/seed7/src/scanner.c:361-364` (the `SPECIALCHAR` case list includes `'\\'`). Measured on this interpreter: `s7 -q -a` on `writeln(1 \ 2)` reports `")" expected found "\"` — the analyzer read `\` as a symbol.

**Files:**
- Modify: `src/scan.sd7:50-51` (`SPECIAL_CHARS`) and the `:44-49` note (see Task 4 for the note's wording — this task only adds the character; do not rewrite the paragraph twice)
- Test: `tests/scan_test.sd7`; equivalence run: `tools/regions_gate.sh` + `tools/corpus_scan.sh` (demand-run, not in `make test`)

**Interfaces:**
- Consumes: nothing.
- Produces: `nextToken` answers `TK_OP` for a token starting at `\`; `hiddenKind`, `maskOf`, `doc_store.wordAt`'s suppression (`src/doc_store.sd7:355`, which tests `doc_store.OP_CHARS`, a set that still excludes `\`) are unchanged, so hover on a bare `\` keeps answering nothing while `occurrencesOf` now indexes it.

- [ ] **Step 1: Write the failing checks** in `tests/scan_test.sd7`, using that suite's own helpers
  (`kindName` at `:5`, `firstKindOf` at `:33`, `firstWidthOf` at `:47`):

```seed7
    check("a lone backslash is an operator token, per tokens.htm 10.2.2",
          kindName(firstKindOf("\\")), "op");
    check("and it grows a run with its neighbours, as scanner.c does",
          str(firstWidthOf("\\+ := 3")), "2");
    check("a backslash inside an unterminated string stays inside the string",
          kindName(firstKindOf("\"abc \\")), "string");
```

The escapes are Seed7 source, not markdown: the first fixture is the two characters
backslash-backslash inside quotes, which is the one character the language scans; the second adds
`+ := 3`; the third is an escaped double quote, `abc `, a backslash, and no closing quote.
`firstWidthOf` answers 2 on the second because the run is the backslash and the `+`, and the space
terminates it. Add the mask pin Review Focus line 3 asks for: over a line holding a based literal
and then a backslash in code, `length(maskOf(text))` equals the input length, every newline keeps
its position, and the backslash is not blanked, because `TK_OP` is never a hidden kind.

- [ ] **Step 2: Run to confirm the named checks fail** — today the first answers `0` (`TK_ILLEGAL`).

Run: `s7 -q -l src tests/scan_test.sd7 2>&1 | grep -A2 '^FAIL'`
- [ ] **Step 3: Add `'\\'` to `SPECIAL_CHARS`** in `src/scan.sd7:50-51`. Nothing else: the run-growing loop, `hiddenKind` and `maskOf` read the same set.
- [ ] **Step 4: Run the scanner suite and the corpus equivalence gates**

Run: `make test-scan test-blocks test-occurrences test-selection_range test-semantic_tokens`, then
`sh tools/regions_gate.sh ~/.cache/seed7-lsp-investigation/work/tokens-before.txt && …` — take the baseline BEFORE Step 3 and the after-run after it, and `diff` them.
Expected: identical, or every difference explained by a corpus file whose code (not a string or comment) holds a `\`. Report the count either way; `SENTINEL files=` must read 345 on both sides (the corpus is one library larger than the 344 the gate's header quotes — Task 5 restates that).
- [ ] **Step 5: Mutation proof:** delete `'\\'` from the set again → the first named check goes FAIL (`2` → `0`). That is the same edit as Step 2 run backwards, so record it as such.
- [ ] **Step 6: `make graph`, totals row, commit.**

---

### Task 4: citations that do not resolve, and one constant nothing reads

**Authority:** each claim is restated only after the command beside it is run on this machine — the rule in `docs/seed7-cli.md` ("re-measure from there before you restate a number").

**Files and the measurement each one needs:**
- Modify: `src/blocks.sd7:6` — `manual/stats.htm 5` → `manual/stats.htm 4`. Verified: `stats.htm` headings are `4. PREDEFINED STATEMENTS` and `4.1`–`4.12` only, in `~/Seed7Home/manual/stats.htm` and live at seed7.net; section 5 is `types.htm`.
- Modify: `src/scan.sd7:44-49` — the paragraph says `doc_store`'s set "is the character-run logic behind codeText and wordAt; Task 8 replaces that … Until then, do not merge the two." Task 8 landed: `codeText` returns the mask from `scan.maskOf` (`src/doc_store.sd7:288-292`) and `wordAt` uses `tokenAt` (`:344-372`). Restate it as: the two sets differ on purpose, `doc_store.opChar` survives only for `wordAt`'s operator suppression (`src/doc_store.sd7:355`), and merging them moves that suppression.
- Modify: `tests/scan_test.sd7:62` — `tokenColOf`'s comment says the helper "does not need
  tokenAt, which only arrives with Task 8". `tokenAt` shipped (`src/scan.sd7:438`, read by
  `src/doc_store.sd7:353` and `src/features/selection_range.sd7:57`), so the sentence describes a
  machine that exists. Restate it: a test helper may walk tokens linearly, and `tokenAt` is the
  production path and needs no second implementation there.
- Leave: `tests/features_test.sd7:924`'s "Task 8 inherits". That cites a task of the plan that
  shipped rename, which is how this repo names a landed wave (compare `docs/seed7-cli.md`'s
  "Task 4's two `is <value>` fixtures"); it points at shipped code, not at a deleted machine.
- Modify: `src/keywords.sd7:49-56` — "copied from ~/seed7-mode/seed7-mode.el's `seed7--statement-enclosing-keywords` and `seed7--declaration-intro-keywords`, kept verbatim" is not what the sets say. Measured with `python3` set arithmetic over the two lists plus `seed7--in-middle-statement-keywords`: 9 of the 39 (`by end interface is nested new out return type`) are in none of them, and 12 that are in them (`begin default downto key len of param step to when`, plus the `end <word>` forms) are not in the 39. Restate as a hand-picked typist vocabulary cross-checked against those lists; `when` reaching the user comes from `CANDIDATES_GAP`, which stays.
- Modify: `src/rpc.sd7:8-10` — replace "(RequestMessage.id, L1501-1520)" with the spec anchor `<https://microsoft.github.io/language-server-protocol/specifications/lsp/3.18/specification/#requestMessage>`, `id: integer | string`.
- Modify: `docs/seed7-cli.md:805-812` — same for "L4885–L4891 of a plain-text extraction held at `/tmp/lsp318.txt`": cite `#exit` and keep the note that the file is gone, because the sentence itself re-verifies verbatim against the live page.
- Modify: `src/diagnostics.sd7:10` — delete `const integer: SEV_WARNING is 2;`.
- Test: none of these can carry a red assertion. `tools/agents_gate.sh` (already in `make test`) holds the frozen tokens, so the run that matters is Step 2.

**Interfaces:** Consumes/produces: no behaviour, no signature, no JSON.

- [ ] **Step 1: Take the measurements and paste them into the commit message.**
  `grep -o '<h[0-9][^>]*>[^<]*' ~/Seed7Home/manual/stats.htm | head -3`; the three keyword lists in
  `~/seed7-mode/seed7-mode.el` (`seed7--statement-enclosing-keywords` at `:1154`,
  `seed7--declaration-intro-keywords` at `:1181`, `seed7--in-middle-statement-keywords`) diffed
  against `CANDIDATES_BASE`, counting the multi-word `end <keyword>` entries rather than dropping
  them; `grep -rn tokenAt src/`, which is the evidence the two Task-8 comments need; and
  `grep -rn SEV_WARNING src tests tools`, which must print only the declaration line.

- [ ] **Step 2: Run `make test-agents` before editing** and confirm `agents: 53 checks, 0 failed`, then again after: still 53. If a token goes MISSING, the citation moved a frozen string — fix the citation, do not add a second token beside it (the rule in `docs/seed7-cli.md`'s R26 note).
- [ ] **Step 3: Apply the six edits.** Keep every measured number that is still true; delete the dead constant only (no rename, no new comment about it).
- [ ] **Step 4: `make graph` (line counts move in `blocks.sd7`, `scan.sd7`, `keywords.sd7`, `rpc.sd7`, `diagnostics.sd7`), then `make test`** → 21 suites, unchanged check counts, `0 failed`.
- [ ] **Step 5: Prove the deletion was safe:** `grep -rn 'SEV_WARNING' src tests tools` prints nothing, and `make test` still passes — there is no assertion that can fail for an unreachable symbol, and the plan says so rather than inventing a trigger.
- [ ] **Step 6: Commit**, listing each correction with the command that produced it.

---

### Task 5: a gate that re-derives the present-tense figures

**Authority:** `AGENTS.md`'s provenance discipline and `tools/keyword_gate.sh`'s pattern (probe the interpreter, exit 1 on drift, never hand-edit the derived list).

**Files:**
- Create: `tools/figures_expected.tsv` — one row per live claim: `<figure-name>\t<derivation-command>\t<expected>\t<host file:line>`
- Create: `tools/figures_gate.sh` — runs each command, compares, prints `figures: N checks, M failed` in the graded shape `Makefile`'s `test-%` recipe greps for
- Modify: `Makefile:27` — `TESTS_SH := agents graph figures`
- Modify: the host documents the rows point at (below)
- Test: the gate *is* the test; its own failure path is proven by mutation in Step 5

**Rows the first version carries** — values are the ones measured on 2026-11-02 on this machine, and the gate's job is to make them stop being stale rather than to keep them fixed:

| name | command | today |
|---|---|---|
| `corpus_files` | `ls "$SEED7"/lib/*.s7i "$SEED7"/prg/*.sd7 \| wc -l` | 345 |
| `lib_top` | `ls "$SEED7"/lib/*.s7i \| wc -l` | 216 |
| `prg_top` | `ls "$SEED7"/prg/*.sd7 \| wc -l` | 129 |
| `lib_recursive` | `find "$SEED7"/lib -name '*.s7i' \| wc -l` | 267 |
| `corpus_bytes` | `LC_ALL=C wc -c "$SEED7"/lib/*.s7i "$SEED7"/prg/*.sd7 \| tail -1` (field 1) | 24995434 |
| `syntax_lines` | `grep -c '^\$ syntax' "$SEED7"/lib/syntax.s7i` | 194 |
| `lib_first_line_empty` | `find "$SEED7"/lib -name '*.s7i' -exec sh -c 'head -1 "$1" \| wc -c' _ {} \; \| sort -u` (must print exactly `1`) | `1` |
| `home_lib_anchors` | `LC_ALL=C grep -ho '<a name="[^"]*"' "$HOME_DIR"/libraries/*.htm \| wc -l` | 3039 |
| `home_lib_anchors_distinct` | same piped through `sort -u \| wc -l` | 2961 |
| `home_librefs` | `grep -c '<li><a href="libraries/' "$HOME_DIR"/subject_index.htm` | 3216 |
| `home_li_all` | `LC_ALL=C grep -oE '<li><a href="[^"]+"' "$HOME_DIR"/subject_index.htm \| wc -l` | 3547 |
| `home_index_bytes` | `wc -c < "$HOME_DIR"/subject_index.htm` | 532702 |

The `home_li_all` row is the correction for the audit's finding 7: the command `docs/seed7-cli.md:411` records uses `grep -o` with `[^"]+`, which in basic grep treats `+` as a literal and prints **0**. The gate carries `grep -oE`, and the table row gets the same fix plus today's number.

**Hosts to restate** (the gate's `host` column points here): `README.md:202-204` (`344`, `51`), `AGENTS.md:60` (`266` recursive), `AGENTS.md:340` (`184 of the 214`) — **excluded from the gate**, restatable only by re-running `sh tools/rf10_probe.sh` (one analyze phase per library per route; minutes, deliberately outside `make test`) — `docs/seed7-cli.md` rows at `:409-416`, `:426-429`, `:390`, `:694`, `:729`, and `tools/regions_gate.sh:7-9,25` plus `tools/corpus_scan.sh`'s "over 340 files".

- [ ] **Step 1: Write the failing gate.** `tools/figures_gate.sh` reads the TSV, and for a missing `$SEED7` (`/home/username/seed7`, overridable as `$1`) or missing `$HOME_DIR` prints `figures: 0 checks, 0 failed` plus a `SKIP:no-seed7-checkout` line and exits 0 — a machine without the siblings must not fail the suite. Run it against the current documents *before* restating them.

Run: `sh tools/figures_gate.sh; echo "exit=$?"`
Expected: FAIL rows for every figure the audit says moved (344 vs 345, 215 vs 216, 266 vs 267, 24 981 055 vs 24 995 434, the five `Seed7Home` rows), non-zero exit.
- [ ] **Step 2: Restate each host line** with the value the gate printed, keeping the "measured 2026-11-02 against `~/seed7 <sha>` / `~/Seed7Home <sha>`" shape the table already uses. Record both HEADs from `git -C ~/seed7 log --oneline -1` and `git -C ~/Seed7Home log --oneline -1` in the commit.
- [ ] **Step 3: Wire it:** `Makefile:27` becomes `TESTS_SH := agents graph figures`. `make test-figures` → `figures: 12 checks, 0 failed`.
- [ ] **Step 4: Fix the two claims that are about a run rather than a tree:** in `src/blocks.sd7:286` ("86 of the 344 corpus files") and `docs/seed7-cli.md:877-881` the figures belong to a named artifact of `regions_gate.sh`; re-run the gate (`sh tools/regions_gate.sh <new baseline>`) so the sentinel reads `files=345`, and update the header counts in `tools/regions_gate.sh` (344→345, 215→216) and `tools/corpus_scan.sh`. Report the new `regions=` and `skips=` from the run — do not compute them.
- [ ] **Step 5: Mutation-proof the gate twice, in opposite directions.** (a) Put a wrong number in one TSV row → that named check prints FAIL and the exit is non-zero, and `make test` cannot pass. (b) Delete the SKIP branch and run with `SEED7=/nonexistent` → the script must fail loudly, which is what proves branch (a) is a real comparison and not a script that always prints zero. Restore exact bytes after each.
- [ ] **Step 6: `make graph` if any `src/` file moved, `make test`, totals row (the new suite joins the enumeration, so say so in the row's prose: 22 suites from here on), commit.**

---

### Task 6: a corpus gate for the scanner's columns

**Authority:** `tools/corpus_scan.sh:4-7` states its own limit — it "does NOT check columns, scopes, or bindings". This is that missing check, as a demand-run gate beside `regions_gate.sh`.

**Files:**
- Create: `tools/tokens_gate.sh` — shell wrapper plus embedded Seed7 probe, modelled line for line on `tools/regions_gate.sh` (`set -eu`, `LC_ALL=C`, `mktemp -d` + trap, sentinel grep, exit 3 with no artifact on a missing sentinel, `SKIP:not-valid-utf8` row for `prg/err.sd7`)
- Not in `make test`: it walks the external corpus and takes ~83 s for `prg/*.sd7` alone (measured); say so in the header, in the same words regions_gate uses.

**Interfaces:**
- Consumes: `skipWhitespace`, `nextToken`, `maskOf`, `tok`, `scanCursor` from `src/scan.sd7`; `utf16CharLength` from `src/utf8bytes.sd7` — the gate calls the shipped machine, never a retyped copy.
- Produces: one row per file `<path>\t<tokens>\t<mismatches>`, and the sentinel `SENTINEL files=<n> tokens=<n> mismatches=<n> skips=<n>`. Exit 1 when `mismatches <> 0`.

- [ ] **Step 1: Write the gate** from the probe already measured this session: for every token, `wantCol` = UTF-16 units from the start of its own line to `tk.start`, `wantWidth` = units from `tk.start` to the last character before the first line break inside the token, both compared with `tk.col16` / `tk.width16`; plus `length(maskOf(text)) = length(text)` and a newline-position comparison between `text` and its mask. Compile with `s7c -O2 -l "$SRC"` and run the binary — the interpreted form is too slow for 4 066 131 tokens.
- [ ] **Step 2: Run it and record the figures** — measured on 2026-11-02 at `7f691ee`: `SENTINEL files=344 tokens=4066131 mismatches=0` (216 `lib/*.s7i` in 1.3 s with the mask checks, 128 `prg/*.sd7` in 82 s). Expect 345 files after `lib/lzip.s7i`, so take the run's own numbers, not these.
- [ ] **Step 3: Handle the one file that cannot be decoded — and record why the handling is a SKIP, not a catch.** `prg/err.sd7` raises `RANGE_ERROR` mid-read; the probe that kept a loop-carried buffer string across the raise then aborted later with `MEMORY_ERROR` at `sigutl.c(355)` (reproduced with `err.sd7` followed by any second file, in both orders). The shipped reader is NOT implicated: 200 `proseFor` calls over an invalid-UTF-8 library, interleaved with clean reads, against the running server, ended with exit 0 and only frames on stdout. So the gate pre-checks decodability (the way `regions_gate.sh` labels its SKIP row) and never reads that file in the same process as another. State both facts in the header, with the commands.
- [ ] **Step 4: Prove the gate can fail** — mutate `out.col16 := cur.col16;` in `src/scan.sd7` to `out.col16 := 0;` and run the gate over 5 small files: it must report non-zero mismatches and exit 1. Restore exact bytes and re-run clean.
- [ ] **Step 5: Run the gate before and after Task 3's `\` change** (that is the equivalence evidence Task 3 Step 4 asks for on the token axis, where `regions_gate.sh` supplies it on the region axis) and keep both artifacts under `~/.cache/seed7-lsp-investigation/work/gate/`.
- [ ] **Step 6: Commit** (no `src/` change, so no `make graph`), with the sentinel line pasted verbatim.

---

## Not in this plan

- **Finding 1** (the `parseError.fileName` guard) shipped as `7f691ee`; it is not re-opened.
- **Finding 12** — `Content-Type`'s charset is ignored. The spec says a non-`utf-8` charset "should respond with an error", but no client this repo documents sends one, and honouring it means a second framing outcome to pin in `tests/transcript.py` and `AGENTS.md` for a case nobody produces. Named, not fixed.
- **Finding 13** — `publishDiagnostics` carries no `version`. The right fix for the staleness a 1-4 s analysis causes on a large file, and it deserves its own plan because it touches the `analysisCache` invalidation rule (`src/lsp_server.sd7:44-62`, validity by presence), not just the JSON.

## Order and cost

Tasks 1, 2, 4 are independent. Task 3 and Task 6 pair: run `tokens_gate.sh` before and after the `\` change. Task 5 changes the corpus figures that Tasks 3 and 6's artifacts quote, so do it before them if the gate runs after it, or accept the 344/345 difference and restate in Task 5. Suggested sequence: **4 → 1 → 2 → 5 → 6 → 3**, so the cheap honest-documentation work lands first and the gates exist before the behaviour change that needs to prove equivalence.

Every task ends with `make test` green, the `docs/seed7-cli.md` suite-totals row carrying its delta, and a commit that names the mutation which reddened its new check.
