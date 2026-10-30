# Request-Id Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer a request with the `id` the client sent, so a client that uses a string `id` — which LSP 3.18 allows — gets a response it can match instead of waiting forever.

**Architecture:** `rpc.sd7`'s `rpcMsg` keeps the id as the JSON text to echo (`idJson`), produced by `jsonw` for a string and by `readJson`'s own source text for a number. `sendResult` and `sendError` take the message and write that text with `raw`, so the reply carries the client's id verbatim; a message with no usable `id` is a notification and gets no frame at all. `lsp_server.sd7` and `main.sd7` change only at the send call sites; no feature module, response shape or capability changes.

**Tech Stack:** Seed7 5.4.10 (`s7`, `s7c`), `tests/rpc_test.sd7` and `tests/transcript.py`, the latter driving the real process over real frames.

**Spec:** no spec file in this tree. Authority is LSP 3.18 Base Protocol: `RequestMessage.id: integer | string` (L1501-1520), `ResponseMessage.id: integer | string | null` (L1524-1547), "Every processed request must send a response back to the sender" (L1497), "A processed notification message must not send a response back. They work like events." (L1674), and a `$/`-prefixed request "must error the request with error code MethodNotFound" (L1690). Measured current behaviour against the real process: `{"id":"42","method":"textDocument/hover"}` is answered `{"id":0,…}`; `{"id":"x","method":"no/such"}` is answered with **nothing at all**, so the client waits forever.

## Global Constraints

- Red first: write the check, run it, confirm it fails for the reason named, then implement. `make test` before and after.
- Nothing on the request path may raise, and no raise may reach stdout (`AGENTS.md`). `idJsonOf` is total: every `jsonValue` category, including an absent id, returns text.
- `AGENTS.md` invariant 7: outbound text goes through `jsonw.sd7`. The string arm of `idJsonOf` produces its quotes **with `jsonw`**, not with a hand count of characters — see Task 1 Step 4.
- `AGENTS.md` invariant 3: `transport.sd7` owns every outbound byte count. This plan adds no byte arithmetic; `writeMessage` keeps counting.
- `src/features/*.sd7` is untouched. `docs/PROJECT_GRAPH.md` is generated and byte-compared by `tests/graph_test.sh`, so every commit that changes a `src/` line count regenerates it in the same commit.
- `-32700` keeps `id: null` (`sendParseError` is unchanged) — a body that is not JSON has no id to echo.
- Do not run `make -j` (`tests/graph_test.sh:17-19` uses fixed `/tmp/g1`, `/tmp/s1`).

## Review Focus

- A string id must come back quoted, a number id bare. Both are echoed as the JSON text the client sent, so `1e3` and `10.5` come back as `1e3` and `10.5` — the source text, not a re-formatted number. Pinned in Task 1.
- A non-ASCII string id must not echo Seed7's literal form. Measured: `str(jsonValue)` of `{"id":"Ид"}` is `"\1048;\1076;"` — not JSON, and printing it on a plain stdout raises `RANGE_ERROR` at `fil_rtl.c(2912)`. The string arm therefore goes through `jsonw`, which emits raw UTF-8. Pinned in Task 1.
- An id holding a client-escaped surrogate pair must round-trip as the same two escapes. Measured: `jsonw` turns the pair `("\ud83d\ude00"`) into `"\ud83d\ude00"` and a real astral character into raw UTF-8, so the reply is valid JSON either way. Pinned in Task 1.
- An unusable id (`true`, `null`, `[1]`, `{…}`, absent) must produce no frame — measured today a `textDocument/hover` **notification** with no `id`, and one with `"id":[1]`, are each answered `{"id":0,…}`, which LSP forbids (L1674: a notification must not be answered). Pinned in Task 1 and Task 2.
- An unknown method asked with a string id must produce `-32601`, not silence. That is the hang this plan exists to remove. Pinned in Task 2.

---

### Task 1: Carry the id's JSON text, and echo it

**Files:**
- Modify: `src/rpc.sd7` (`rpcMsg` at `53-59`, `parseMessage` at `175-193`, `sendResult` at `208-216`, `sendError` at `222-235`, the `ponytail:` note at `8-11`; one new `const func string: idJsonOf`)
- Modify: `src/lsp_server.sd7` (27 call sites: 25 `sendResult(msg.id,`, `sendError(msg.id, -32602, …)` at `:452`, `sendError(msg.id, -32601, …)` at `:538`, and `sendError(0, -32603, …)` in `handlerFailed` at `:74`)
- Modify: `src/main.sd7` (`:19`, `:23`)
- Test: `tests/rpc_test.sd7`
- Modify: `docs/PROJECT_GRAPH.md` (regenerated)

**Interfaces:**
- Consumes: `rpc.atKey`, `rpc.category`, `jsonw.jsonWriter` (its `buf` field), `jsonw.addStr`, `jsonw.trimComma`, `jsonw.raw`, `transport.writeMessage`.
- Produces:
  - `rpcMsg.var string: idJson is "null";` — the JSON text to echo, `"null"` when the message has no usable id. The `integer: id` field is **deleted**: its only reader was the echo.
  - `const func string: idJsonOf (in jsonValue: idValue)` — `str(idValue)` for a `JSON_NUMBER`, `jsonw`-quoted text for a `JSON_STRING`, `"null"` otherwise. Total; never raises.
  - `sendResult (in rpcMsg: msg, in string: resultJson)` and `sendError (in rpcMsg: msg, in integer: code, in string: message)`. Both write `field(w, "id"); raw(w, msg.idJson);` and both **return without writing any frame when `msg.idJson = "null"`** — that is the notification rule. `sendParseError` and `sendNotification` keep their signatures; neither carried an id.
  - `msg.isRequest := msg.idJson <> "null";`

- [ ] **Step 1: Write the failing checks**

In `tests/rpc_test.sd7`, beside the existing `parseMessage` checks. `m := parseMessage(…)` then grade the field; `idJsonOf` is also worth a direct call because two of its arms are about escaping, not parsing:

```seed7
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":7,\"method\":\"x\"}");
check("a number id echoes its own text", m.idJson, "7");
check("and it is a request",             str(m.isRequest), "TRUE");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":\"42\",\"method\":\"x\"}");
check("a string id echoes quoted",       m.idJson, "\"42\"");
check("and it too is a request",         str(m.isRequest), "TRUE");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":10.5,\"method\":\"x\"}");
check("a float id echoes the source text", m.idJson, "10.5");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":1e3,\"method\":\"x\"}");
check("an exponent id echoes the source text", m.idJson, "1e3");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":true,\"method\":\"x\"}");
check("a bool id is not a request",      str(m.isRequest), "FALSE");
check("and it echoes null",              m.idJson, "null");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":[1],\"method\":\"x\"}");
check("an array id is not a request",    str(m.isRequest), "FALSE");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"method\":\"x\"}");
check("an absent id echoes null",        m.idJson, "null");
check("not-a-JSON body echoes null",     (parseMessage("{oops")).idJson, "null");
check("escaped-dquote id re-escapes",
      idJsonOf(readJson("{\"s\":\"he\\\"llo\"}")["s"]), "\"he\\\"llo\"");   # measured: 9 characters
check("tab id escapes", idJsonOf(readJson("{\"s\":\"a\\tb\"}")["s"]), "\"a\\tb\"");
```

- [ ] **Step 2: Run it and read the red**

```bash
make test-rpc
```

Expected: FAIL with **no** graded line. `idJson` and `idJsonOf` do not exist, so the suite does not analyse, and an unanalysed suite prints nothing and exits 0 — `Makefile`'s `test-%` grades `^[a-z0-9_]+: [0-9]+ checks, 0 failed$` and finds none. That is a different red from a value mismatch, and Step 4's stub exists so Step 5 produces the value kind.

- [ ] **Step 3: Add the two non-ASCII checks, with their lengths**

Append to Step 1's block. `lsp_tst.sd7:11-16` prints on plain stdout, and measured, a non-ASCII print there raises `RANGE_ERROR` and costs the suite its graded line — so these two compare **lengths**, which is what makes the check printable and the mutant detectable:

```seed7
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":\"\\u0418\\u0434\",\"method\":\"x\"}");
check("a non-ASCII id is 4 characters, quoted, not Seed7's decimal literal form",
      str(length(m.idJson)) <& "/" <& m.idJson[1 .. 1], "4/\"");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":\"\\ud83d\\ude00\",\"method\":\"x\"}");
check("a surrogate-pair id escapes both halves", str(length(m.idJson)), "14");
```

Compare length AND the first character together: `length("null")` is itself 4, so a length-only
expectation would be a FALSE GREEN against the Step 4 stub. `4` is `"` + 2 characters + `"`
(measured: `quoted` length 4 for `Ид`), and `m.idJson[1 .. 1]` is the ASCII `"` that proves
the value is a quoted string rather than the word `null`. Corrected in Task 1: Seed7 5.4.10 has
no three-argument `substr` function — `string.s7i` offers `[start .. stop]`, `[.. stop]`,
`[start ..]` and `[start len n]` — so the call as briefed did not analyse, and the slice is shipped. `14` is `"` + `\ud83d` + `\ude00` + `"` — the pair arrives from `readJson` as two lone surrogates and `jsonw` escapes each, which is the behaviour `tests/jsonw_test.sd7:49-52` already pins for a written string. A mutant that used `str(idValue)` for the string arm answers 14 characters for that id — measured, `str()` of the two-character id is `"\1048;\1076;"`, one backslash escape per character — so it reddens this check on both halves of the comparison.

- [ ] **Step 4: Stub `idJsonOf`, so the checks run on values**

Add the signature with `out := "null";` as its only body line, replace `var integer: id is 0;` in `rpcMsg` with `var string: idJson is "null";`, set `msg.isRequest := FALSE;` unconditionally in `parseMessage`, and give `sendResult`/`sendError` the `rpcMsg` parameter with the body unchanged apart from `addInt(w, id)` → `raw(w, "0")`. `make test-rpc` → `rpc: 46 checks, 12 failed`: the six echo/request checks (number, number-is-request, string, string-is-request, float, exponent), the two escaping checks (dquote, tab), **both** length checks, and the two pre-existing `parseMessage` checks `isRequest` and `id` — the stub answers `FALSE` for the first and the stub's `idJson` is `"null"` for the second, and `id` must already read `idJson` at this step or the suite would not analyse at all. Corrected in Task 1's run, which wins over this arithmetic: the count briefed was 10. The other five new checks pass because the stub answers `"null"`, which is what they expect — which is why Step 7's mutants, not this stub, are what prove the bool/array/absent checks.

- [ ] **Step 5: Implement**

`idJsonOf`'s string arm must not count characters. The honest way to get one JSON string value out of `jsonw` is to write it and trim the comma the writer appends — `addStr` and `trimComma` are both public in `src/jsonw.sd7`, and `finishJson` is the writer's own "drop the trailing comma" step:

```seed7
# The JSON text to echo as this message's id. A number's is readJson's own source text
# (measured: str() of 10.5 is "10.5", of 1e3 is "1e3"), so it round-trips untouched. A
# string's must NOT be str(idValue): measured, str() of {"id":"Ид"} is Seed7's decimal
# literal form "\1048;\1076;", which is not JSON and raises RANGE_ERROR if printed. So the
# string arm goes through jsonw, whose escape rules the writer and the reader already agree
# on (AGENTS.md invariant 7). "null" means "no usable id" -- a notification, or a bool.
const func string: idJsonOf (in jsonValue: idValue) is func
  result
    var string: out is "null";
  local
    var jsonWriter: w is jsonWriter.value;
  begin
    if category(idValue) = JSON_NUMBER then
      out := str(idValue);
    elsif category(idValue) = JSON_STRING then
      addStr(w, string(idValue));
      trimComma(w.buf);
      out := w.buf;
    end if;
  end func;
```

`parseMessage`: `msg.idJson := idJsonOf(idValue); msg.isRequest := msg.idJson <> "null";` — one comparison, the same set as `integer | string` plus the float-shaped numbers that are JSON numbers and must be answered.

`sendResult` / `sendError`: keep the `in rpcMsg: msg` parameter from Step 4, wrap the existing body in `if msg.idJson <> "null" then … end if;` (`AGENTS.md`: a bare `return` in a `proc` is `PROC_EXPECTED`), and replace `addInt(w, id)` with `raw(w, msg.idJson)`.

`handlerFailed` (`lsp_server.sd7:69-75`) takes the message and passes it to `sendError`; `src/main.sd7:19,23` become `sendError(msg, -32002, …)` and `sendError(msg, -32600, …)`.

- [ ] **Step 6: Run, regenerate the graph**

```bash
make test-rpc && make graph && make test-graph
```

Expected: `rpc: 46 checks, 0 failed` (31 baseline, +13 in Step 1, +2 in Step 3), `graph: 21 checks, 0 failed`. `tests/rpc_test.sd7:17`'s existing `check("id", str(m.id), "7")` becomes `check("id", m.idJson, "7")` in this commit — it is the only reader of the deleted field besides `firstUnhandled`, which does not touch ids.

- [ ] **Step 7: Prove the checks can fail**

Four mutants, one at a time, each reverted with `git checkout HEAD -- src/rpc.sd7` (plus a fifth, supplementary, which Task 1 ran to find where the notification rule is reachable at all):

1. Number arm → `out := str(intAt(root…))` shape, i.e. parse to integer and back: `a float id echoes the source text` and `an exponent id echoes the source text` FAIL. This mutant is why the number arm is `str()` and not the integer.
2. String arm → `out := str(idValue)`: the two length checks FAIL (`14/"` against `4/"`, and `16` against `14`). Corrected in Task 1's run: `escaped-dquote id re-escapes` and `tab id escapes` stay GREEN, because Seed7's `str()` and `jsonw` agree on the ASCII escapes — measured, both give the 9 characters `"he\"llo"` and the 6 characters `"a\tb"`. Non-ASCII is the only thing that separates the two writers, which is why Step 3 compares lengths and is the real net.
3. `msg.isRequest := msg.idJson <> "null"` → `category(idValue) = JSON_NUMBER`: `and it too is a request` FAILs while the echo checks stay green. That pair is the bug — the text is kept, the dispatcher still treats the message as a notification.
4. `if msg.idJson <> "null"` removed from `sendError`: no unit check reddens (`rpc: 46 checks, 0 failed`), which is the finding — and neither does the existing wire suite (`transcript: 203 checks, 0 failed`). Measured further in Task 1: **no input reaches `sendError` with `idJson = "null"`**, because all four of its call sites sit behind `if msg.isRequest`, and `isRequest` is that same predicate — so this mutant is semantically identical from outside and no black-box check can redden it (AGENTS.md, mutation rule 1). Do not add a synthetic frame-capturing harness for it.
5. The reachable half of the notification rule is `sendResult`'s guard, and it is the one Task 2 must pin. Measured in Task 1 as a fifth, supplementary mutant: delete `if msg.idJson <> "null"` from `sendResult` alone and a `textDocument/hover` notification is answered with a `"id":null` frame — a 3rd response to 2 requests on a probe session — while `rpc: 46 checks, 0 failed` and `transcript: 203 checks, 0 failed` both stay green. Task 2's `ids ==` check is what sees it, since a reply with `"id": null` still has the key and lands in the list as `None`.

- [ ] **Step 8: Commit**

```bash
git add src/rpc.sd7 src/lsp_server.sd7 src/main.sd7 tests/rpc_test.sd7 docs/PROJECT_GRAPH.md
git commit -m "rpc: echo the request id the client sent, integer or string"
```

---

### Task 2: Prove it on the wire, including the two hangs

Task 1 changed 27 call sites and made "was this a request?" a property of the id. Only a frame can show that a client would now be answered, and that a notification is not.

**Files:**
- Modify: `tests/transcript.py` (one new scenario; nothing in `src/`)

**Interfaces:**
- Consumes: `frame` (`:10`), `run` (`:42`), `split_frames`/`junk` (`:14`), `expect` (`:50`), `one_answer_per_request` (`:405`), `answered_null` (`:395`), `initialize`/`opened`/`pos`/`shutdown`/`exit_`.
- Produces: the six check titles Step 2 prints.

- [ ] **Step 1: Add the scenario**

A whole session whose ids are strings, because a string id is legal at every step and `initialize` is where a wrong id is fatal. Place it after the lifecycle block:

```python
STR_IDS = [{"jsonrpc": "2.0", "id": "i1", "method": "initialize",
            "params": {"capabilities": {}, "rootUri": "file:///tmp"}},
           {"jsonrpc": "2.0", "method": "initialized", "params": {}},
           opened("/tmp/tt_strid.sd7", TRIVIAL),
           {"jsonrpc": "2.0", "id": "h1", "method": "textDocument/hover",
            "params": pos("/tmp/tt_strid.sd7", 3, 10)},
           {"jsonrpc": "2.0", "id": "u1", "method": "not/a/method", "params": {}},
           {"jsonrpc": "2.0", "method": "textDocument/hover",
            "params": pos("/tmp/tt_strid.sd7", 3, 10)},
           {"jsonrpc": "2.0", "id": "d1", "method": "textDocument/definition",
            "params": pos("/tmp/tt_strid.sd7", 3, 10)},
           {"jsonrpc": "2.0", "id": "s1", "method": "shutdown"},
           exit_()]
replies, code, err, junk = run([frame(m) for m in STR_IDS])
ids = [r.get("id") for r in replies if "id" in r or "method" in r]
expect(ids == ["i1", "h1", "u1", "d1", "s1"],
       "every reply carries the string id it answers (%s)" % ids)
expect(next(r for r in replies if r.get("id") == "u1")["error"]["code"] == -32601,
       "the unknown string-id method is answered with -32601, not with silence")
expect("capabilities" in next(r for r in replies if r.get("id") == "i1").get("result", {}),
       "and initialize answered under its own id, so the client finishes starting up")
expect(not any(r.get("id") == 0 for r in replies),
       "and nothing is answered under a borrowed integer id 0 (%s)" % ids)
expect(code == 0 and junk == 0, "the string-id session exits clean (code=%d junk=%d)" % (code, junk))
one_answer_per_request(STR_IDS, replies, "the string-id session")
```

The fourth check is the one that catches Task 1 Step 7's mutant 4 class of error, and the sixth is the balance check: the session contains two notifications (`initialized`, the idless hover) and five requests, and the idless hover must **not** be answered. Read `one_answer_per_request` (`:405-413`) before trusting that it counts that way; if it counts frames-with-`result` against messages-with-`id`, it is already right, and if it does not, fix the check to match its documented meaning — never the helper to match the check.

`frame` writes `json.dumps` with `ensure_ascii=True`, so every id here is ASCII and the harness's known blind spot (`transcript.py:1093-1102`) does not apply: this scenario is not testing byte framing.

- [ ] **Step 2: Run it**

```bash
make transcript
```

Expected: `transcript: 209 checks, 0 failed` — the measured baseline on this branch is **203** (`transcript: 203 checks, 0 failed` at `8d00014`: 196 pre-branch, +6 from R-F10 Task 3, +1 from its fix-wave hover check), plus the 6 here. Do not re-derive it from 196: that figure predates two merged tasks. If the first check reports `[1, 0, 0, 0, 0]` instead, Task 1 did not land — that is the shape of the bug, not a failure of this check.

- [ ] **Step 3: Prove the wire checks can fail**

Restore `raw(w, msg.idJson)` to `addInt(w, msg.id)` in `sendResult` alone and keep everything else: `make transcript` → `transcript: 209 checks, 3 failed` (the `ids ==` check, the borrowed-id check, and `one_answer_per_request`), while `code == 0 and junk == 0` **stays green**. That is the finding to record: a wrong id is invisible to every safety net the harness has except the id comparison itself — no stray byte, no short frame, no nonzero exit. Revert with `git checkout HEAD -- src/rpc.sd7`.

Then the second mutant: widen `isRequest` back to `category(idValue) = JSON_NUMBER` and rerun — the `ids ==` check and `-32601` check go red, because the unknown string-id request is once again dropped without a reply. That is the hang this plan exists to remove.

- [ ] **Step 4: Commit**

```bash
git add tests/transcript.py
git commit -m "transcript: pin string-id fidelity, the -32601 a string id used to lose, and no reply to a notification"
```

---

### Task 3: Retire the recorded shortcut

**Files:**
- Modify: `src/rpc.sd7` (the `ponytail: request ids are handled as integers only` note at `8-11`)
- Modify: `README.md` (§ *What works*)
- Modify: `docs/PROJECT_GRAPH.md` (only if a line count moved; Task 1 already regenerated it)

- [ ] **Step 1: Delete the note, and check nothing else repeats it**

The note records a limit that no longer exists, so it goes — replacing a `ponytail:` note with a rule is the expected end of that comment's life. Then:

```bash
grep -rn 'integers only\|echoes back as 0\|echoed back as' src/ tests/ README.md AGENTS.md docs/
```

Expected: no output. Any hit is a second place claiming the old behaviour, and `AGENTS.md`'s § *Every change* says a corrected claim is the finding, not a silent edit.

- [ ] **Step 2: README**

§ *What works*'s error-handling sentence gains one clause: a request is answered under the id the client sent, integer or string, and a notification is never answered. One sentence, spec cited, no new list.

- [ ] **Step 3: Run everything, confirm the tree is clean, commit**

```bash
make graph && make test && git status --porcelain -uall
git add src/rpc.sd7 README.md
git commit -m "docs: the integer-id shortcut is gone; state the id-fidelity rule in its place"
```

Expected: 21 graded lines each `0 failed`, `git status --porcelain -uall` empty (no `src/main`, no `profile_out`, no `.tmp`).

---

## Definition of done

- `{"id":"42"}` is answered `"id":"42"`, at every method including `initialize`; `{"id":10.5}` is answered `10.5`, not `10` and not `0`.
- A message with no usable id (`true`, `null`, `[1]`, `{…}`, absent) produces **no** frame, which also ends the spec violation where a `textDocument/hover` notification was answered `id: 0`.
- An unknown method asked with a string id produces `-32601`.
- Fifteen unit checks and six wire checks exist; four named mutants in Task 1 Step 7 (whose stub-step counterpart reddens 12, measured in Task 1's run) and two in Task 2 Step 3 each redden a named check, and Task 2 Step 3 records that `junk == 0` cannot see a wrong id.
- The `ponytail:` note at `src/rpc.sd7:8-11` is gone and `grep -rn 'integers only' src/ tests/ README.md AGENTS.md docs/` prints nothing.
- `make test` green; `git status --porcelain -uall` empty.

## Out of scope

- **A malformed position that reads as line 0.** Measured: `{"character":10.5}` answers `null` and `{"line":"3"}` answers `null`, because `intAt`/`strAt` return the fallback rather than raising — `integer("10.5")` is `RANGE_ERROR`, the one `intAt` already catches. So `hover` is about `(0,0)`, and `(0,0)` is a real position. Arguably it should be `-32602 InvalidParams`. That is a decision about answer shape, needs a choice about `positionEncoding`-adjacent tolerance, and is not required by any of the id work; it is deliberately not smuggled in here.
- **Ordering.** The server is single-threaded and answers in request order, which the spec accepts (`L1794`) and `main.sd7`'s loop guarantees.
- **Any new method answered.** `$/`-prefixed requests other than `$/cancelRequest` and `$/setTrace` fall through to the `-32601` arm exactly as before — with a numeric id they were already answered, and with a string id they now are too, which is the fix, not a new feature.

## Measured, and therefore NOT planned here

- **The `-32603` hunt.** A review claimed a float id or a `1e400` costs the request with `-32603`. Refuted by measurement against the real process: 24 well-framed hostile bodies and 12 hostile request shapes (float and string and `null` and array ids, `params` as array/string/`null`, `positions:null`, `context:null`, `newName` as an object, bodies that are a number/string/`null`/array/bool, positions past EOF, negative positions, `http:` and `untitled:` uris) produced **no `-32603` and no `handler failed` line**, and every session still ended `code == 0`, `junk == 0`. `AGENTS.md`'s "the `-32603` containment net is still unreachable" stands as written; nothing in this plan is that net's test.
- **`{"id":"42"}` → `id: 0`.** Measured, and it is the bug this plan fixes. It was recorded as a `ponytail:` decision on the grounds that every client tested sends integers; the spec allows strings, an unknown string-id method gets no reply at all, and the failure mode is a permanent hang rather than a cosmetic mismatch.

## Start here

`src/rpc.sd7:53-59` (`rpcMsg`), `:175-193` (`parseMessage`), `:208-235` (the two senders), then `src/main.sd7:11-30` (where `isRequest` gates the two lifecycle errors) and `src/lsp_server.sd7:69-75` (`handlerFailed`).
