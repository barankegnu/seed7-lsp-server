# Transport And Region Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** make the four must-fix defects from the 2026-10-31 repo audit impossible — an undecodable byte that writes an exception trace onto the protocol channel, a `Content-Length` that overflows and silently ends the session, a length-less header block that kills the session instead of being passed over, and a swallowed keyword in `blocks.sd7` that deletes folding regions — and cut the cost of one `foldingRange` on the largest file in the distribution.

**Architecture:** all four fixes stay inside two modules. `src/transport.sd7` owns every inbound and outbound byte count (AGENTS.md invariant 3), so the framing decisions change only there; `main.sd7`'s existing `framingFatal → exit(2)` arm already implements the "stop reading" policy and needs no edit. `src/blocks.sd7` owns the region machine, and its public answers (`blockRegions`, `walkRegions`) keep their signatures, so the two `blocks` fixes are invisible to every caller in `src/features/`.

**Tech Stack:** Seed7 5.4.10 (`s7 -q -l src`), no dependencies. Wire behaviour is graded by `tests/transcript.py`, which drives `src/main.sd7` over real `Content-Length` frames and counts stray stdout bytes as `junk`.

**Spec:** there is no design doc — it was deleted at `fca09be` and has no successor (AGENTS.md, top of file). The authority for this plan is, in order: (1) `AGENTS.md` §"Invariants" and §"Protocol decisions that are easy to undo by accident"; (2) the measured table below, taken from the audit against this tree at `5d8b72c`; (3) `docs/seed7-cli.md` for the figures those rules point at. Every task cites the AGENTS.md rule it serves.

**Worktree:** all paths are relative to `.worktrees/transport-and-region-fixes` (branch `transport-and-region-fixes`, baseline `5d8b72c`, `make test` = 21 graded suites, 1 108 checks, 0 failed).

## Global Constraints

- **Red first, every task.** Write the check, run it, confirm it FAILS for the reason named in the task, then implement. `make test` before and after (AGENTS.md §"Every change"). The measured FAIL output for each task is quoted below; if your run fails differently, stop — the premise moved.
- **Never let an exception reach stdout.** stdout *is* the JSON-RPC channel (AGENTS.md §"Seed7 traps"). Any new read or decode path needs a `block … exception` or it is a defect.
- **`framingFatal` means "the frame's end is unknowable" and nothing else.** It is set only in `src/transport.sd7`, and `src/main.sd7:54-55` turns it into `exit(2)`. Absent `Content-Length` is *not* fatal; a value whose bytes cannot become an integer is.
- **Log lines go to `STD_UTF8_ERR` with the prefix `seed7-lsp: `.** A server log is one line per event on stderr and must never appear in a response frame (AGENTS.md §"Protocol decisions — the notification is the frame"). Exact strings are pinned by tests; the two new ones are in Task 2.
- **Any task that edits `src/` also refreshes `docs/PROJECT_GRAPH.md`.** That file is a committed artifact and `tests/graph_test.sh` compares it against a fresh `make graph` run, so a `src/` edit without the refresh turns `make test` red (`FAIL committed artifact is fresh`). Run `make graph` and add `docs/PROJECT_GRAPH.md` to the same commit as the `src/` change.
- **`MAX_FRAME_BYTES` is 67 108 864** (`src/transport.sd7:5`). Do not change it.
- **Seed7 `catch` has no name before the exception**: `catch RANGE_ERROR:` — `catch e: RANGE_ERROR:` does not parse (`Priority <= 49 expected found "catch"`). Measured on this interpreter.
- **Seed7 strings escape a quote as `\"`, never `""`.** `"a ""b""` is an error, not a quoted `b`. Measured (`Use \" instead of "" to represent " in a string`).
- **Do not build a standalone probe that calls `gets`/`readln` on an `openUtf8` handle over invalid UTF-8.** Two attempts at exactly that hung this host and cost two tool results. Every undecodable-byte case is proven through `tests/transcript.py`, which runs the real server with `communicate(timeout=90)`. The disabled probe is at `~/.cache/seed7-lsp-investigation/work/DO-NOT-RUN-raise.sd7.freezes-os` — leave it unexecuted.
- **One analysis per version, one region scan per request** (AGENTS.md invariant 8). A fix in `blocks.sd7` may not add a second scan over the document.
- **Check counts at `5d8b72c`, measured, so each task's arithmetic is auditable:** `transcript` 212, `blocks` 71, `transport` 16, `folding` 4, `selection_range` 8, `features` 191, `occurrences` 94, `doc_store` 81, `analysis` 50; the whole `make test` is 21 graded suites and 1 108 checks. `tools/agents_gate.sh` requires the tokens in `tools/agents_required.txt` to survive in `AGENTS.md` *or* `docs/seed7-cli.md`; no `Content-Length` framing phrase is on that list, so Task 6's rewrite of the framing bullet cannot break the gate.
- **Commits:** one per task, message prefixed with the module it changes (`transport:`, `blocks:`, `docs:`), and the message names the check that went red and the reason. `git status --porcelain -uall` must be empty after `make clean-build`.

## Review Focus

The five input classes this plan's spec implies but no existing test exercises. Each is pinned by a task, named here and then in that task:

1. **A frame whose bytes are not valid UTF-8** — a client that sends a body with one raw `0xFF`, or a stream desynced by a miscounted length, must end the session at `exit(2)` with only frames on stdout. *(Task 2.)*
2. **A `Content-Length` that is all digits and too big for an integer** — a 23-digit value is as unknowable as `abc`; it must be fatal, not read as "absent". *(Task 1.)*
3. **A header block with no `Content-Length`, followed by a good frame** — the block is reported and the *next* frame is still answered; one malformed block must not cost the server. *(Task 3.)*
4. **A declaration whose `is <value>` is followed by a construct keyword** — `begin`, `local`, `if`, `struct` each still get their own region; the fold that covers the body must not be eaten. *(Task 4.)*
5. **A file with thousands of regions** — `prg/chkarr.sd7` has 4 847; a faster `blockRegions` must return byte-identical output for every file in `lib/*.s7i` and `prg/*.sd7`. *(Task 5, gate.)*

## Findings this plan implements — measured at `5d8b72c`

| # | Input | HEAD behaviour (measured) | Target |
|---|---|---|---|
| 1 | `Content-Length: 99999999999999999999999` (23 digits) then a good frame | `exit=0 frames=2`, stderr `seed7-lsp: frame without Content-Length ignored` | `exit=2`, stderr `seed7-lsp: invalid Content-Length '99999999999999999999999'` |
| 2 | a frame body holding one raw `0xFF` | `exit=1`, stdout carries `Uncaught exception … main.sd7(10)` (`junk=1`) | `exit=2 junk=0`, stderr `seed7-lsp: frame body is not valid UTF-8` |
| 3 | a header line holding one raw `0xFF` | `exit=1`, trace on stdout (`junk=1`) | `exit=2 junk=0`, stderr `seed7-lsp: header line is not valid UTF-8` |
| 4 | `Content-Type` block with no `Content-Length`, then `shutdown` | `shutdown` never answered (2 frames, ids `[1, null]`) | answered (3 frames, ids include `2`), `exit=0` |
| 5 | `const proc: q is func\nvar integer: a is 0;\nbegin…` | regions `0-4` — the `begin` block is gone | `0-4 2-4` |
| 6 | `const proc: p is func\n local\n var integer: a is 0;\n begin…` | regions `0-5 1-5` — `local` runs to the end | `0-5 1-3 3-5` |
| 7 | `const type: t is new struct\n var integer: a is 0;\n end struct;` | region `0-3` — `end struct` was consumed | `0-2` |
| 8 | `foldingRange` on `~/seed7/prg/chkarr.sd7` (1 761 917 chars, 33 148 lines, 4 847 regions) | `didOpen` 2.85 s; `+1 foldingRange` 16.96 s; `+3` 48.78 s → ~15 s per request | re-measured; the number goes in `docs/seed7-cli.md` |

---

### Task 1: `headerNumber` — an unparsable value is fatal even when it is all digits

**Files:**
- Modify: `src/transport.sd7:24-35` (the two `catch` arms at 28-29)
- Modify: `docs/PROJECT_GRAPH.md` (regenerated by `make graph`)
- Test: `tests/transcript.py:1425-1427` (the hostile-framing loop)

**Interfaces:**
- Consumes: nothing new.
- Produces: `headerNumber` returns `0` and leaves `framingFatal` TRUE for *any* value that is not a valid, in-range integer. Task 2 and Task 3 read that flag; neither changes it.

- [ ] **Step 1: add the fourth hostile label to the loop at `tests/transcript.py:1425`**

The loop already asserts the policy for three values; the digit-overflow case is the fourth of the same class:

```python
for label, hdr in [("non-numeric", b"Content-Length: abc"),
                   ("negative",    b"Content-Length: -5"),
                   ("oversized",   b"Content-Length: 999999999"),
                   ("over-wide",   b"Content-Length: 99999999999999999999999")]:
```

- [ ] **Step 2: run it and confirm it fails for the named reason**

Run: `make transcript`
Expected: `FAIL over-wide Content-Length: clean fatal exit, stdout uncorrupted` — measured at HEAD: `exit=0`, 2 frames, and the line on stderr is `seed7-lsp: frame without Content-Length ignored`, i.e. the value was read as *absent*. The other three labels still pass; if one of them fails, stop and re-read `headerNumber`.

- [ ] **Step 3: implement in `src/transport.sd7:24-35`**

Both `catch` arms must mark the value unparsable, because `integer(text)` raising on a digit string is the same event as a non-digit string: the frame's end is unknowable. Leave the `MAX_FRAME_BYTES` arm (31-34) exactly as it is.

```seed7
        catch RANGE_ERROR:
          n := 0;
          parsable := FALSE;
        catch NUMERIC_ERROR:
          n := 0;
          parsable := FALSE;
```

- [ ] **Step 4: run the suite and confirm green**

Run: `make transcript`
Expected: `transcript: 213 checks, 0 failed` — the loop holds one `expect` per label, so the fourth label adds exactly one check to the 212 measured at `5d8b72c`. What must change is `0 failed`.

Run: `make test`
Expected: `TOTAL` line per suite with `0 failed`, 21 suites.

- [ ] **Step 5: commit**

```bash
git add src/transport.sd7 tests/transcript.py docs/PROJECT_GRAPH.md
git commit -m "transport: a Content-Length whose digits overflow is fatal, not absent

integer() raises RANGE_ERROR on a 23-digit value and the catch arm returned 0 with
parsable still TRUE, so readMessage read it as a missing header and ended the session
at exit 0. The existing loop over hostile headers now covers it."
```

---

### Task 2: a byte the reader cannot decode must not reach stdout

**Files:**
- Modify: `src/transport.sd7` — insert `noteBadUtf8` before the comment at line 80; wrap the `gets` at line 95; add `getlnSafe` before `readMessage` (line 114) and use it at lines 122 and 127; add `not framingFatal` to the two `while` conditions.
- Test: `tests/transcript.py` — append after line 1446 (the `-32700` block), before the Task 1/2 wire-proof comment at 1448.

**Interfaces:**
- Consumes: `framingFatal` (`src/transport.sd7:9`), `MAX_FRAME_BYTES`, `headerNumber` from Task 1.
- Produces: `const proc: noteBadUtf8 (in string: where)` — sets `framingFatal`, logs `seed7-lsp: <where> is not valid UTF-8` to `STD_UTF8_ERR`. Task 3's rewrite of `readMessage` keeps calling it and keeps its two message strings, which are pinned by name below.

- [ ] **Step 1: write the failing checks**

```python
# --- a byte sequence that is not valid UTF-8 must never reach stdout (audit finding 1/2) ---
# utf8.s7i's getln/gets raise RANGE_ERROR at the first undecodable byte (measured:
# readln -> RANGE_ERROR ut8_rtl.c(771)); the read sits in transport, outside main.sd7's
# handler net, so today the trace lands on stdout. The frames are hand-built bytes because
# json.dumps cannot emit an invalid one.
BAD_BODY = b'{"jsonrpc":"2.0","id":9,"method":"textDocument/hover","params":{"a":"\xff"}}'
replies, code, err, junk = run([frame(msgs[0]),
                                b"Content-Length: %d\r\n\r\n" % len(BAD_BODY) + BAD_BODY,
                                frame({"jsonrpc": "2.0", "id": 13, "method": "shutdown"})])
expect(code == 2 and junk == 0,
       "invalid UTF-8 in a body: exit 2 and only frames on stdout (code=%d junk=%d)" % (code, junk))
expect("frame body is not valid UTF-8" in err, "and stderr names the frame body")
BAD_HDR = b"Content-Length: \xff7\r\n\r\n"
replies, code, err, junk = run([frame(msgs[0]), BAD_HDR,
                                frame({"jsonrpc": "2.0", "id": 14, "method": "shutdown"})])
expect(code == 2 and junk == 0,
       "invalid UTF-8 in a header line: exit 2 and only frames on stdout (code=%d junk=%d)" % (code, junk))
expect("header line is not valid UTF-8" in err, "and stderr names the header line")
```

- [ ] **Step 2: run it and confirm it fails for the named reason**

Run: `make transcript`
Expected: both `exit 2 and only frames on stdout` checks FAIL. Measured at HEAD: `exit=1`, `junk=1`, and stdout holds `Uncaught exception … at main.sd7(10)` — that trace is the defect, and `split_frames` counts it as junk. The two `stderr names …` checks also fail, because HEAD never prints those lines.

- [ ] **Step 3: add the two guards**

`noteBadUtf8` first — Seed7 cannot call a helper defined later in the file (AGENTS.md §"Seed7 traps — declare before use"). Place it directly above the `# Known limit of any character-based reader:` comment at line 80:

```seed7
# A byte sequence the reader cannot decode means the same thing as an unparsable
# Content-Length: the frame's end is unknowable. Say so once, set the same flag, and let
# main.sd7's framingFatal arm report it as exit 2 -- never onto stdout, which is the
# protocol channel (AGENTS.md: "never let an exception reach stdout").
const proc: noteBadUtf8 (in string: where) is func
  begin
    framingFatal := TRUE;
    writeln(STD_UTF8_ERR, "seed7-lsp: " <& where <& " is not valid UTF-8");
  end func;
```

Wrap the body read at line 95 — an empty `chunk` is already the loop's stop condition, so the catch only has to produce it:

```seed7
      block
        chunk := gets(source, max(1, remaining div 4));
      exception
        catch RANGE_ERROR:
          noteBadUtf8("frame body");
          chunk := "";
      end block;
```

Add `getlnSafe` immediately above `readMessage` (line 114) and use it for both header reads (currently lines 122 and 127). The parameter's static type is `file`, which dispatches to the UTF-8 reader — the same mechanism line 95 relies on.

```seed7
# One header line, with the decode failure reported the way a bad frame length is: the same
# raise reaches both reads, and a header line is where a desynced stream lands on a
# continuation byte.
const func string: getlnSafe (inout file: source) is func
  result
    var string: line is "";
  begin
    block
      line := getln(source);
    exception
      catch RANGE_ERROR:
        noteBadUtf8("header line");
    end block;
  end func;
```

Finally add `and not framingFatal` to both `while` conditions in `readMessage` (the block loop at line 123 and — after Task 3 restructures it — whichever loop encloses the header read), so a raise ends the pass instead of spinning on the same byte.

- [ ] **Step 4: run the suite and confirm green**

Run: `make transcript` then `make test`
Expected: `transcript: 217 checks, 0 failed` (213 + the four new checks). 21 suites `0 failed`. Measured at `8d9e630`: 1 113 checks across 21 suites (Task 1 moved the total to 1 109; four more here). One consequence worth knowing rather than fixing: after a fatal byte in a BODY the partial body is still handed to `main`, which answers one `-32700` frame and then exits 2 — `junk=0`, stdout frame-clean. The pre-existing check at line 184 (`frame lacking Content-Length is reported`) must still pass — it is the case this task does *not* touch.

- [ ] **Step 5: prove what is and is not load-bearing (mutation)**

Delete `and not framingFatal` from the inner header `while` only, and run `make transcript`; then do the same for the outer one. Record what actually happens for each — do not report a prediction.

Measured on this branch at `8d9e630`, so the expectation is a result rather than a guess: **neither clause hangs or reddens anything.** Removing either leaves 217 green. The reason is that a `getln` raise leaves `line` as `""`, which ends the inner block loop on its own; the clauses state the policy "once fatal, stop reading", they are not the thing that stops the spin. What IS mutation-proven in this task are the two `catch` arms — deleting either turns its pair of checks from `exit 2` to `exit 0`. RULING (ledger): keep both clauses as the policy statement Task 3's loop depends on, and say in the commit which parts are proven and which are not. The alternative — deleting the clauses — would make `readMessage` rely on an incidental `line <> ""` side effect to stop reading after a fatal byte, which is the kind of coupling AGENTS.md calls a defect.

- [ ] **Step 6: commit**

```bash
git add src/transport.sd7 tests/transcript.py docs/PROJECT_GRAPH.md
git commit -m "transport: an undecodable byte ends the session instead of corrupting stdout

gets/readln on a UTF-8 file raise RANGE_ERROR at the first byte that is not valid UTF-8,
and the reads live in transport, outside main.sd7's handler block: one 0xFF in a body put
an exception trace on stdout and exited 1. Both reads are now guarded, the stream is
declared fatal, and main.sd7's existing framingFatal arm exits 2."
```

---

### Task 3: a header block with no `Content-Length` is passed over, not fatal

**Files:**
- Modify: `src/transport.sd7` — `readMessage` (at `5d8b72c` lines 114-138; locate it by name, because Task 2's insertions shift the numbers)
- Test: `tests/transcript.py:177-184` (the existing length-less block case)

**Interfaces:**
- Consumes: `headerNumber` (Task 1), `getlnSafe`/`noteBadUtf8` (Task 2), `readFrameBody`.
- Produces: `readMessage` returns FALSE only at EOF, on an empty body, or once `framingFatal` is set. No signature change; `main.sd7:10` is untouched.

- [ ] **Step 1: extend the existing case**

The case at `tests/transcript.py:178` already sends a `Content-Type`-only block followed by a good frame and asserts the log line. Add the two assertions that HEAD fails:

```python
expect(any(r.get("id") == 9 and "result" in r for r in replies),
       "the frame after a length-less header block is still answered")
expect(code == 0, "a length-less block does not end the session (code=%d)" % code)
```

Then make the branch ORDER provable, in the hostile-framing loop Task 1 extended. At HEAD a fatal value prints TWO lines — `headerNumber` logs `invalid Content-Length '<text>'` and then `readMessage`'s `contentLength = 0` branch logs `frame without Content-Length ignored`, because both states arrive as `0`. Step 3's `if framingFatal` branch, placed before the length-less branch, is what separates them, so pin it:

```python
    expect("without Content-Length" not in err,
           "%s Content-Length prints one framing line, not two" % label)
```

- [ ] **Step 2: run it and confirm it fails for the named reason**

Run: `make transcript`
Expected: `FAIL the frame after a length-less header block is still answered`, and `FAIL non-numeric Content-Length prints one framing line, not two` (plus the same FAIL for `negative`, `oversized` and `over-wide`) — measured at `5d8b72c`: 2 frames with ids `[1, null]`, `shutdown` never read, and both framing lines on stderr for a fatal value.

- [ ] **Step 3: implement the pass-over**

Replace `readMessage`'s `begin` body so one header block is read per pass and a block with no length simply loops. Three decisions the test does not determine, and that must not be "improved":

- the outer condition is `while not okay and not framingFatal and hasNext(STD_UTF8_IN) do` — `framingFatal` states "once fatal, stop reading" for the whole request. The spin claim this bullet used to make is **measured wrong**: at `a1753f1`, deleting only this clause (inner clause and Task 2's guards left in place) leaves `transcript: 225 checks, 0 failed` in 5 s — no red, no hang, no timeout, no stray process. Neither is the reviewer's replacement mechanism true: the four `code == 2` checks do not redden, because the inner clause ends the header loop on the fatal pass and the fatal arm precedes the length-less and body arms, so a later pass cannot reach `readFrameBody` and nothing behind a fatal frame is ever answered; without the clause the stream is simply drained line by line to EOF. Keep the clause as the policy statement — the same status Step 5 of Task 2 recorded for the inner one — and do not invent a trigger for it.
- `contentLength := 0;` is the **first statement of each pass** — `contentLength` is a `local`, so a stale length from a previous pass would re-read the next frame's body with the wrong byte count (this is the bug a reviewer will not see in the diff);
- the length-less branch keeps today's exact log string `seed7-lsp: frame without Content-Length ignored`, because `tests/transcript.py:184` and `AGENTS.md` both name it.

- [ ] **Step 4: run the suites and confirm green**

Run: `make transcript` then `make test`
Expected: `transcript: 219 checks, 0 failed` (217 + the two new checks) and 21 suites `0 failed`. Two invariants to check by eye in the transcript output, because they are the neighbours this restructure could break: the `-32002` "request before initialize" case (line 174) and the "server keeps serving after a parse error" case (line 1442) must both still pass.

- [ ] **Step 5: prove the reset can fail (mutation)**

Delete the `contentLength := 0;` reset from the top of the pass. `make transcript` must go red — if it stays green, no wire input in the suite reaches the "second block after a short first frame" state, and the reset is then unproven: say so in the commit rather than claiming a proof.

- [ ] **Step 6: commit**

```bash
git add src/transport.sd7 tests/transcript.py docs/PROJECT_GRAPH.md
git commit -m "transport: one length-less header block no longer costs the session

A header block without Content-Length has no knowable end, and readMessage returned FALSE
after reporting it, so the well-formed frame behind it was never read and the process
exited 0. It now reports and keeps reading; the spec requires the header, not the stream."
```

---

### Task 4: `walkRegions` — the keyword after `is <value>` is not swallowed

**Files:**
- Modify: `src/blocks.sd7:237-244` (the `elsif pending = "func"` branch) — move it below the branch at 255-257
- Test: `tests/blocks_test.sd7:239` (fixture 15's expectation) and `tests/blocks_test.sd7:242` (two new fixtures)

**Interfaces:**
- Consumes: nothing.
- Produces: `blockRegions` answers one more region for every declaration written `is <non-name>;` followed by a construct keyword. `foldingRange`, `selectionRange` and `documentSymbol` consume the list through their existing calls; no signature changes.

- [ ] **Step 1: fix the wrong pinned value and add the two missing shapes**

Fixture 15 (`tests/blocks_test.sd7:239`) currently pins the defect: the file is `const type: t is new struct` / `var integer: a is 0;` / `end struct;`, and because `struct` is consumed by the `pending` branch the `end struct` closer never arrives, so the region runs to the last line. `0-2` is the correct answer.

```seed7
    f.text := "const type: t is new struct\n  var integer: a is 0;\nend struct;\n"; f.expected := "0-2"; out &:= f;
```

Then append two fixtures before the `demo()` entry (which stays last so its index and title do not move), pinned to the measured target from the Findings table, rows 5 and 6:

```seed7
    # A declaration whose `is' is followed by a value, not a name: the keyword that opens the
    # next block must still reach its own branch. At HEAD the `begin' branch never runs and
    # the body region is missing from the answer.
    f.text := "const proc: q is func\n  var integer: a is 0;\nbegin\n  writeln(a);\nend func;\n";
    f.expected := "0-4 2-4"; out &:= f;
    f.text := "const proc: p is func\n  local\n    var integer: a is 0;\n  begin\n    writeln(a);\n  end func;\n";
    f.expected := "0-5 1-3 3-5"; out &:= f;
```

- [ ] **Step 2: run it and confirm all three fail for the named reason**

Run: `make test-blocks`
Expected (measured against HEAD): `FAIL fixture 15 regions`, and the two new fixtures fail with `got "0-4"` / `got "0-5 1-5"`. If fixture 15 passes, the tree is not at `5d8b72c`.

- [ ] **Step 3: implement — move the branch, do not change its body**

Cut lines 237-244 (`elsif pending = "func" then … end if;`) and reinsert it immediately after the `isClause` branch (which ends at line 257, before the closing `end if;` of the chain). The branch body is unchanged. `pending` is deliberately *not* cleared by the construct branches: a stale `pending` costs at most one extra name examined at the bottom of the chain, while clearing it in a construct branch would put `const func … is func` back into the bug.

- [ ] **Step 4: run the suites and confirm green**

Run: `make test-blocks`, then `make test`
Expected: `blocks: 77 checks, 0 failed` — the table at line 256 emits three checks per fixture (`regions`, `invariant`, `linesIn`), so two new fixtures add exactly 6 to the 71 measured at `5d8b72c`. Then 21 suites, `0 failed`. Measured in a scratch copy of this tree with exactly this change: `folding 4/0`, `selection_range 8/0`, `occurrences 94/0`, `features 191/0`, `doc_store 81/0`, `analysis 50/0`, `transcript 212/0` — every suite but `blocks` was untouched, which is the evidence that the change is confined.

- [ ] **Step 5: commit**

```bash
git add src/blocks.sd7 tests/blocks_test.sd7 docs/PROJECT_GRAPH.md
git commit -m "blocks: a construct keyword after \`is <value>\` is no longer swallowed

The \`pending = \"func\"\` branch sat above the begin/end/if/section/clause branches, so any
name reaching it was consumed and matched only against func/struct/enum: \`var integer: a is
0;\` followed by \`begin\` answered no body region at all, and \`end struct\` was eaten. Fixture
15 had pinned the mangled answer 0-3; the correct region is 0-2."
```

---

### Task 5: `blockRegions` — the two post-passes, with the output held identical

**Files:**
- Modify: `src/blocks.sd7:296-308` (bubble sort → insertion sort), `src/blocks.sd7:309-341` (clause filter)
- Create: `tools/regions_gate.sh`
- Test: `tests/blocks_test.sd7` (unchanged — it is the behaviour gate), plus the corpus gate

**Interfaces:**
- Consumes: `walkRegions` (unchanged), `blockRef` (unchanged).
- Produces: `blockRegions(in string: text, in integer: lastLine)` returning the same array, in the same order, for every input. `tools/regions_gate.sh [OUTFILE] [SEED7_DIR]` writes one line per file: `<path>\t<n>\t<start-end[:kind] …>` for every `lib/*.s7i` and `prg/*.sd7`.

- [ ] **Step 1: write the gate tool**

Model it on `tools/corpus_scan.sh` (a spike, not a suite: the header must say so, and it must stay out of `make test`, which it does by being called only from `tools/`). Requirements, each one decided:

- read each file with `openUtf8(path, "r")` and a `readln` loop — the same decoded text the server sees; `gets(handle, -1)` raises `RANGE_ERROR` at `ut8_rtl.c(586)` (AGENTS.md), and a plain `open(path, "r")` yields one character per byte, which is the contamination `tools/rf10_probe.sh`'s header documents;
- line count is the text's own, matching `blocks_test.sd7`'s `linesIn` (`pred(linesIn(text))` is `blockRegions`'s `lastLine` argument);
- print `path`, region count, and the `start-end[:kind]` list joined by a space, one line per file, files in `ls` order;
- the region list must come from `blockRegions` in `src/blocks.sd7` — a retyped copy would gate a machine the server does not have.

- [ ] **Step 2: capture the baseline, and prove the gate can report a difference**

```bash
sh tools/regions_gate.sh /home/username/.cache/seed7-lsp-investigation/regions-before.txt
```

Expected: one line per file; `prg/chkarr.sd7` reports `4847` regions (measured) and the biggest `lib` file reports 719. Then, as the mutation that proves the gate is not decorative, change one `kind` string in the emitter, re-run to a second file, and `diff` — expect a non-empty diff — and restore the exact bytes.

- [ ] **Step 3: replace the sort**

Insertion sort over `raw` by `startLine`, replacing lines 296-308 including the `ponytail:` comment. Both sorts shift/swap only on a strictly-greater key, so both are stable and the answer order is unchanged for every input — the region *contents* stay byte-identical, and Step 4's diff is what proves it rather than the argument. Rewrite the comment to the measured truth, not the old average: the ceiling is **4 847 regions** for one file in `~/seed7` (`prg/chkarr.sd7`), and ~95 is the mean across the library set.

- [ ] **Step 4: replace the clause filter**

Current cost is two full scans of `raw` per clause region. Decided shape, which reproduces today's answers exactly:

- scan the sorted `raw` once, collecting the **non-clause** regions into `controls` (indices into `raw`) — this is the array the enclosing-control search needs;
- for each clause region, find its enclosing control by scanning `controls` **backwards from the last entry whose `startLine < clause.startLine`**, stopping at the first one with `endLine >= clause.endLine`. The old loop kept overwriting `controlStart`/`controlEnd` on every match, so it settled on the *last* match in document order — which for regions that are properly nested is the innermost one, i.e. the first hit walking backwards. Both answers are the same element whenever the region set is nested-or-disjoint, which is what `blockStack` guarantees for everything but `comment`/`imports` regions; those have `kind <> "clause"` and can interleave, so Step 5's whole-corpus diff is the check, not reasoning;
- keep the "no enclosing control" fallback exactly as the old code produces it (`controlStart := 0`, `controlEnd := lastLine`, which counts *every* clause in the document): an orphan clause is emitted when the document holds more than one clause;
- count clauses per control into an `array integer` indexed by control index in the same single pass, then emit only when `clauseCount > 1`, stripping the marker (`r.kind := ""`) as lines 332 and 337 do.

- [ ] **Step 5: gate the refactor against the baseline**

```bash
sh tools/regions_gate.sh /home/username/.cache/seed7-lsp-investigation/regions-after.txt
diff /home/username/.cache/seed7-lsp-investigation/regions-before.txt \
     /home/username/.cache/seed7-lsp-investigation/regions-after.txt
```

Expected: empty diff. A non-empty diff is a defect in this task, not an improvement to be pinned — unless the differing file is one of Task 4's `is <value>` shapes, which the earlier commit already accounts for; name the file and line in the commit either way.

- [ ] **Step 6: run the suites, then measure the answer**

Run: `make test` — 21 suites, `0 failed`.

Then reproduce the three wire sessions the finding was measured in (one `didOpen` of `~/seed7/prg/chkarr.sd7`; `didOpen` + one `foldingRange`; `didOpen` + three) against this branch's `src/main.sd7`, timed. HEAD, same session shape: **2.85 s / 16.96 s / 48.78 s**. Record the three new figures with the command and the interpreter version in `docs/seed7-cli.md` under a dated heading. If the new total is not meaningfully below 16.96 s for one `foldingRange`, do not claim the sort as the cause — say which pass dominates, and leave the `ponytail:` note in place with the measured ceiling so the next reader does not have to re-derive it.

- [ ] **Step 7: commit**

```bash
git add src/blocks.sd7 tools/regions_gate.sh docs/seed7-cli.md docs/PROJECT_GRAPH.md
git commit -m "blocks: an insertion sort and a per-control clause count replace two O(n^2) passes

The bubble sort and the clause filter's two nested scans per clause region dominated
foldingRange: ~15 s per request on prg/chkarr.sd7, which holds 4 847 regions (measured;
the deleted ponytail note called ~95 the ceiling, and it is the mean). tools/regions_gate.sh
prints blockRegions' answer for every lib/*.s7i and prg/*.sd7 file, and the before/after
diff is empty."
```

---

### Task 6: the two documents, corrected to the code you just wrote

**Files:**
- Modify: `AGENTS.md` §"Protocol decisions that are easy to undo by accident" (the `Content-Length` bullet) and §"Seed7 traps" (the exit-code bullet)
- Modify: `docs/seed7-cli.md` (new dated section)

**Interfaces:**
- Consumes: Tasks 1-5's measured outcomes, quoted above.
- Produces: nothing consumable; this task is what stops the next agent from re-introducing the defect.

- [ ] **Step 1: rewrite the framing bullet in `AGENTS.md`**

Replace the single sentence "An absent `Content-Length` logs and keeps reading. An unparsable, negative, or over-`MAX_FRAME_BYTES` value … exit **2**." with the three-way rule the code now implements, each clause naming its own wire check in `tests/transcript.py`:

- an absent `Content-Length` logs `frame without Content-Length ignored` and **keeps reading** — the frame behind it is still answered;
- an unparsable value — non-digits, negative, over `MAX_FRAME_BYTES`, **or digits too wide for `integer()`** — logs `invalid Content-Length '<value>'` and exits **2**;
- a byte sequence that is not valid UTF-8, in a header line or a body, logs `<where> is not valid UTF-8` and exits **2** — and this is the case that used to put an exception trace on stdout at exit 1.

- [ ] **Step 2: correct the exit-code trap, and add the raise-site trap**

The bullet "s7 reports analysis errors on stderr **and exits 0**" is now wrong against this interpreter: upstream `da2feb38` (2026-09-25, "Errors trigger an exit code of 1") makes analysis errors exit **1**, measured for `"end" expected`, `NO_MATCH`, `UNCLOSED_COMMENT` and a missing include. The exit-0 case that remains is `*** Declaration for main missing`, printed on **stdout** (`src/s7.c:467`). Rewrite it to name both, and keep the rule that a suite is graded by its own `N checks, M failed` line — that part still holds and is enforced by the `test-%` rule.

Add one trap line: `getln`/`gets` on a `STD_UTF8_IN` stream raise `RANGE_ERROR` at the first undecodable byte, and because those reads live in `transport.sd7` they are *outside* `main.sd7`'s handler block — a new inbound read must be guarded at its own site.

- [ ] **Step 3: write the measurement section in `docs/seed7-cli.md`**

One dated section holding, with the command beside every number: the Findings table above (HEAD vs branch), the four wire outcomes, the three `foldingRange` session timings, the region counts (4 847 `prg/chkarr.sd7`, 719 largest `lib`), and the `tools/regions_gate.sh` invocation. Also refresh the suite-totals row (`docs/seed7-cli.md:417`, which records `transcript 212` and `21 suites, 1 108 checks`) to the branch's final counts — review finding on Task 1: the row drifted by one check at `e24e464` and will drift again with Tasks 2-4. Note in the section that the standalone `gets`-over-invalid-UTF-8 probe hangs this host and that the wire suite is the replacement — the next reader will otherwise try it.

- [ ] **Step 4: gate the docs against the repo's own rule, then commit**

Run: `make test-agents`
Expected: `agents_gate` reports the required lines present — `tools/agents_gate.sh` greps `AGENTS.md` for named text, so if Step 1's rewrite deletes a phrase it checks, update the phrase in `tools/agents_required.txt` deliberately, in the same commit, and say which one and why.

```bash
git add AGENTS.md docs/seed7-cli.md tools/agents_required.txt
git commit -m "docs: the framing decisions as the code now implements them, and the exit code as 5.4.10 reports it"
```

---

## Self-review

**1. Spec coverage.** Findings 1, 2, 3, 4 from the audit map to Tasks 1+3 (framing policy), 2 (undecodable bytes), 4 (swallowed keyword), 5 (folding cost) — all four must-fixes, none of them split across tasks. The audit's should-fix list is *not* here on purpose: `$/cancelRequest` unanswered, `selectionRange` truncating the array, `prepareProvider` advertised unconditionally, and the dead declarations are separate branches; only finding 5's doc bullet (Task 6 Step 1) belongs to the framing work.

**2. Step scan.** Every step is one action. Two steps carry a body deliberately: Task 5 Steps 3-4 (the order-equivalence argument and the backwards-scan decision cannot be recovered from the signature or the suite) and Task 2 Step 3 (the two pinned message strings). Task 5 Step 6 is the one step whose "expected" is a judgement rather than a number — the fallback ("do not claim the sort as the cause") is the decision, so the step cannot be written as a pass/fail without inventing a timing assertion that would be flaky on this host.

**3. Type consistency.** `noteBadUtf8(in string: where)`, `getlnSafe(inout file: source)`, `headerNumber` unchanged, `readMessage(inout string: body)` unchanged, `blockRegions(in string: text, in integer: lastLine)` unchanged, `regions_gate.sh` output `<path>\t<n>\t<list>`. Task 3 consumes `getlnSafe` and the flag from Task 2; Task 5 consumes nothing from Tasks 1-4 but must come after Task 4, because Task 4 changes region output and the gate baseline must be captured from the post-Task-4 tree.

**4. Review Focus.** All five lines are pinned: (1) Task 2 body check, (2) Task 1 fourth label, (3) Task 3 Step 1, (4) Task 4 Step 1's two fixtures, (5) Task 5's corpus diff.

**5. Proportion.** Six tasks, ~40 lines of new production code, ~25 lines of new test code, one new gate tool. The plan is shorter than the diff it predicts only in the two places where an algorithm had to be argued.
