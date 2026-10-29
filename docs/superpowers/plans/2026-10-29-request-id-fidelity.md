# Request-Id Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer a request with the `id` the client sent, so a client that uses string ids — which LSP 3.18 allows — gets a response it can match instead of waiting forever.

**Architecture:** `rpc.sd7`'s `rpcMsg` keeps the id twice: the integer it always kept, and the JSON text to echo (`idJson`). The three senders take the message instead of an integer and write that text with `raw`, so the response carries the client's own id, quoted or bare as it arrived. `lsp_server.sd7` and `main.sd7` change only at the call sites; no feature module, no response shape and no capability changes.

**Tech Stack:** Seed7 5.4.10 (`s7`, `s7c`), `tests/rpc_test.sd7` and `tests/lsp_server_test.sd7` graded from their `N checks, M failed` line, `tests/transcript.py` driving the real process over real frames.

**Spec:** no spec file in this tree. Authority: LSP 3.18 Base Protocol — `RequestMessage.id: integer | string` (L1501-1520), `ResponseMessage.id: integer | string | null` (L1524-1547), "Every processed request must send a response back to the sender" (L1497), "a request starting with `$/` … must error the request with error code MethodNotFound" (L1690). Current behaviour measured against the real process: `{"id":"42","method":"textDocument/hover"}` is answered with `{"id":0,…}`, and `{"id":"x","method":"no/such"}` is answered with **nothing at all**.

## Global Constraints

- Red first: write the check, run it, confirm it fails for the reason named, then implement. `make test` before and after.
- Nothing on the request path may raise, and no raise may reach stdout (`AGENTS.md`). Every new accessor stays total.
- `AGENTS.md` invariant 7: outbound text goes through `jsonw.sd7`, and `grep -rn 'addStr(w, str(' --include='*.sd7' src/` must stay empty. This plan adds no such call — see Task 1 Step 3 for why `str(jsonValue)` on a string is exactly the thing that rule refuses.
- `AGENTS.md` invariant 3: `transport.sd7` owns every outbound byte count. `writeMessage` keeps counting; nothing here emits a `Content-Length`.
- `src/features/*.sd7` is untouched. `docs/PROJECT_GRAPH.md` is generated and byte-compared, so every commit that changes a `src/` line count regenerates it in the same commit.
- `-32700` keeps `id: null` (a body that is not JSON has no id to echo) and `-32603`'s net keeps its behaviour; `handlerFailed` gains the id from the message it is handed, which is `"null"` when parsing never finished.
- Do not run `make -j` (`tests/graph_test.sh:17-19` uses fixed `/tmp` names).

## Review Focus

- A string id must come back **as a string**. `idJson` for `"42"` is the text `"42"` with the quotes, so `1e400`-style text is the only thing that could make a client's `by_id` map miss. Pinned in Task 1 and Task 2.
- A non-ASCII string id must not echo Seed7's literal form. Measured: `str(jsonValue)` of `{"id":"Ид"}` answers `"\\1048;\\1076;"` — not JSON. The string arm therefore re-escapes through `jsonw`. Pinned in Task 1.
- A message with an unusable id (`true`, `null`, `[1]`, absent) is a notification: it gets **no** frame, exactly as today, so nothing that works now breaks. Pinned in Task 1.
- An unknown method asked with a string id must produce `-32601`, not silence — that is the hang this plan exists to remove. Pinned in Task 2.
- `initialize` asked with a string id must answer with that id, or the client never finishes starting up. Pinned in Task 2.

---

### Task 1: Carry the id's JSON text, and echo it

**Files:**
- Modify: `src/rpc.sd7` (`rpcMsg` at `53-59`, `parseMessage` at `175-193`, `sendResult` at `208-216`, `sendError` at `222-235`, `sendParseError` untouched, one new `const func string:`)
- Modify: `src/lsp_server.sd7` (27 call sites: 25 `sendResult(msg.id,`, `sendError(msg.id, -32602, …)` at `:452`, `sendError(msg.id, -32601, …)` at `:538`, and `sendError(0, -32603, …)` inside `handlerFailed` at `:74`)
- Modify: `src/main.sd7` (`:19` and `:23`)
- Test: `tests/rpc_test.sd7`
- Modify: `docs/PROJECT_GRAPH.md` (regenerated)

**Interfaces:**
- Consumes: `rpc.category`, `rpc.atKey`, `jsonw.jsonWriter`, `jsonw.openObject`, `jsonw.field`, `jsonw.raw`, `jsonw.addStr`, `jsonw.closeObject`, `jsonw.finishJson`, `transport.writeMessage`.
- Produces:
  - `rpcMsg` gains `var string: idJson is "null";` — the exact JSON text to echo, or `"null"`.
  - `const func string: idJsonOf (in jsonValue: idValue)` in `src/rpc.sd7` — the only new proc. Returns `str(idValue)` for a `JSON_NUMBER`, a `jsonw`-written quoted string for a `JSON_STRING`, and `"null"` for anything else.
  - `sendResult (in rpcMsg: msg, in string: resultJson)` and `sendError (in rpcMsg: msg, in integer: code, in string: message)` — the integer-first forms are gone; there is no third sender to keep, because `sendParseError` and `sendNotification` never carried an id.
  - `msg.id` stays as it is (the integer, `0` when the id is a string), because `handlerFailed`'s log and four unit checks read it.

- [ ] **Step 1: Write the failing checks**

In `tests/rpc_test.sd7`, beside the existing `parseMessage` checks. `m := parseMessage(…)` then `check("…", m.idJson, "…")`:

```seed7
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":7,\"method\":\"x\"}");
check("a number id echoes its own text",   m.idJson, "7");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":\"42\",\"method\":\"x\"}");
check("a string id echoes quoted",          m.idJson, "\"42\"");
check("and it is a request",                str(m.isRequest), "TRUE");
check("its integer id is still 0",          str(m.id), "0");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":\"\\u0418\\u0434\",\"method\":\"x\"}");
check("a non-ASCII string id is not Seed7's literal form", m.idJson, "\"Ид\"");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":10.5,\"method\":\"x\"}");
check("a float id echoes the source text",  m.idJson, "10.5");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":1e3,\"method\":\"x\"}");
check("an exponent id echoes the source text", m.idJson, "1e3");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":true,\"method\":\"x\"}");
check("a bool id is not a request",         str(m.isRequest), "FALSE");
check("and it echoes null",                 m.idJson, "null");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":[1],\"method\":\"x\"}");
check("an array id echoes null",            m.idJson, "null");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"method\":\"x\"}");
check("an absent id echoes null",           m.idJson, "null");
check("not-a-JSON body leaves id null",     (parseMessage("{oops")) .idJson, "null");
```

`"Ид"` in the expectation is written as the two literal characters: `tests/rpc_test.sd7` is UTF-8 source and Seed7 compares characters, not bytes. The check compares strings, so nothing prints those characters — a FAIL line WOULD print them, and `lsp_tst.sd7:11-16` says a non-ASCII print on plain stdout raises `RANGE_ERROR` and costs the suite its graded line. Task 1 Step 5's mutant is what proves the check can fail *without* relying on that print: it compares lengths too, so `check("…", str(length(m.idJson)), "4")` (the `"` + 2 chars + `"`) is the ASCII-safe twin of the same claim. Write BOTH: the value check for the reader, the length check for the grading line.

- [ ] **Step 2: Run it and confirm the reason**

```bash
make test-rpc
```

Expected: FAIL to analyse — `idJson` is not a field yet. The `test-%` rule grades the total line, and a suite that fails to analyse prints nothing and exits 0, so `make test-rpc` must fail with **no** `rpc: N checks, 0 failed` line. That is a different red from a value mismatch, and it is the honest first red here.

- [ ] **Step 3: Add the field, the text reader, and the two senders**

`idJsonOf`'s string arm must not be `str(idValue)`. Measured against the interpreter: `readJson` keeps a JSON *number*'s source text, so `str()` of `10.5` is `"10.5"` and of `1e3` is `"1e3"` — both valid JSON, so the number arm is a one-liner. A JSON *string* is the other case: `str()` of `{"id":"Ид"}` answers `"\"\\1048;\\1076;\"`" — Seed7's own decimal escape form, which no JSON decoder accepts, and which is precisely the bug invariant 7 exists to stop. So the string arm re-escapes through `jsonw`:

```seed7
# The JSON text to echo back as this message's id. readJson keeps a number's source
# text, so str() round-trips; a string does NOT -- str(jsonValue) of {"id":"Ид"} is
# Seed7's "\1048;\1076;" form, which is not JSON -- so the string arm goes through
# jsonw, whose escape rules rpc and jsonw already agree on (AGENTS.md invariant 7).
const func string: idJsonOf (in jsonValue: idValue) is func
  result
    var string: out is "null";
  local
    var jsonWriter: w is jsonWriter.value;
  begin
    if category(idValue) = JSON_NUMBER then
      out := str(idValue);
    elsif category(idValue) = JSON_STRING then
      openObject(w);
      field(w, "id");
      addStr(w, string(idValue));
      closeObject(w);
      out := finishJson(w);
      out := out[8 .. pred(length(out))];
    end if;
  end func;
```

The slice peels `{"id":` (7 characters) and the trailing `}` off a one-field object — `out[8 .. pred(length(out))]` — because `jsonw` has no "write one value" proc and adding one for a single caller would be the second way to emit JSON. Verify the arithmetic in Step 4's check rather than trusting it: `{"id":7}`'s own text is what the number arm returns, and the string arm's output must start with `"`.

`parseMessage`: set `msg.idJson := idJsonOf(idValue);` and make `msg.isRequest` TRUE for a string id too — `category(idValue) = JSON_NUMBER or category(idValue) = JSON_STRING`, written as two comparisons in a `const func boolean: echoable (…)` if the chain fails to match (`AGENTS.md`: a long `or` chain of parenthesised comparisons can fail to match at analysis time).

`sendResult` / `sendError`: take `in rpcMsg: msg` first, and replace `addInt(w, id)` with `raw(w, msg.idJson)`. `handlerFailed` (`lsp_server.sd7:69-75`) takes the message as well and passes it on; `main.sd7:19,23` become `sendError(msg, -32002, …)` and `sendError(msg, -32600, …)`.

- [ ] **Step 4: Run the suite and the tree**

```bash
make test-rpc && make test-lsp_server && make graph && make test-graph
```

Expected: `rpc: 44 checks, 0 failed` (31 baseline + 13 here), `lsp_server: 82 checks, 0 failed` if Task 2 of the R-F10 plan has landed on this branch, otherwise 79 with no new checks (this task adds none there), and `graph: 21 checks, 0 failed` with the regenerated `docs/PROJECT_GRAPH.md` rows for `rpc.sd7` and `lsp_server.sd7`.

- [ ] **Step 5: Prove the new checks can fail**

Three mutants, one at a time, reverted with `git checkout HEAD -- src/rpc.sd7`:

1. Number arm → `out := addInt-form` (i.e. `out := str(intAt(root…))`, losing the source text): `a float id echoes the source text` and `an exponent id echoes the source text` FAIL. This mutant is the reason the number arm is `str()` and not the integer.
2. String arm → `out := str(idValue)`: the length check (`str(length(m.idJson)) = "4"`) FAILs while the value check's FAIL may not print — which is the point of writing the length twin in Step 1.
3. `msg.isRequest := category(idValue) = JSON_NUMBER;` left un-widened: `a string id echoes quoted` stays green and `and it is a request` FAILs. That pair is the whole bug — the text is kept but the dispatcher still treats the message as a notification.

- [ ] **Step 6: Commit**

```bash
git add src/rpc.sd7 src/lsp_server.sd7 src/main.sd7 tests/rpc_test.sd7 docs/PROJECT_GRAPH.md
git commit -m "rpc: echo the request id the client sent, integer or string"
```

---

### Task 2: Prove it on the wire, including the two hangs

**Files:**
- Modify: `tests/transcript.py` (one new scenario; no change to `src/`)

**Interfaces:**
- Consumes: `frame`, `run`, `split_frames` (`junk == 0`), `expect`, `answered_null`, `one_answer_per_request` (`405-413`), `initialize`, `opened`, `pos`, `req`, `shutdown`, `exit_`.
- Produces: five check titles and the string-id session other scenarios can copy.

- [ ] **Step 1: Add the scenario**

A whole session whose ids are all strings, because a string id is legal at every step and `initialize` is where a wrong id is fatal. Send `initialize` with `"id":"i1"`, a `textDocument/hover` with `"id":"h1"`, an unknown method with `"id":"u1"`, `shutdown` with `"id":"s1"`, then `exit`:

```python
STR_IDS = [{"jsonrpc": "2.0", "id": "i1", "method": "initialize",
            "params": {"capabilities": {}, "rootUri": "file:///tmp"}},
           {"jsonrpc": "2.0", "method": "initialized", "params": {}},
           opened("/tmp/tt_strid.sd7", TRIVIAL),
           {"jsonrpc": "2.0", "id": "h1", "method": "textDocument/hover",
            "params": pos("/tmp/tt_strid.sd7", 3, 10)},
           {"jsonrpc": "2.0", "id": "u1", "method": "not/a/method", "params": {}},
           {"jsonrpc": "2.0", "id": "s1", "method": "shutdown"},
           exit_()]
replies, code, err, junk = run([frame(m) for m in STR_IDS])
ids = [r.get("id") for r in replies]
expect(ids == ["i1", "h1", "u1", "s1"], "every reply carries the string id it answers (%s)" % ids)
expect(next(r for r in replies if r.get("id") == "u1")["error"]["code"] == -32601,
       "the unknown string-id method is answered with -32601, not with silence")
expect("capabilities" in next(r for r in replies if r.get("id") == "i1").get("result", {}),
       "and initialize answered under its own id, so the client finishes starting up")
expect(code == 0 and junk == 0, "the string-id session exits clean (code=%d junk=%d)" % (code, junk))
one_answer_per_request(STR_IDS, replies, "the string-id session")
```

`frame` writes `json.dumps` with the default `ensure_ascii=True` (`transcript.py:1093-1102`), so a non-ASCII id would arrive as `\uXXXX` escapes and be a different test. Keep this scenario ASCII; the non-ASCII claim is pinned in Task 1, where the comparison never prints.

- [ ] **Step 2: Run it**

```bash
make transcript
```

Expected: `transcript: 205 checks, 0 failed` (200 after the R-F10 plan's three, else 196 — plus the 5 here; take the number from the run). If the first check reports `ids == [0, 0, 0, 0]`, Task 1 did not land; that is the shape of the bug, not a failure of this check.

- [ ] **Step 3: Prove the wire checks can fail**

Revert `sendResult`/`sendError` to `addInt(w, msg.id)` and keep everything else: `make transcript` → `transcript: 205 checks, 3 failed` — the `ids ==` check, the `-32601` check (which now reads `id: 0` and misses), and `one_answer_per_request`. `code == 0 and junk == 0` stays green, which is the finding worth recording: **a wrong id is invisible to every safety net the harness has except the id comparison itself** — no `junk`, no raise, no extra frame. Revert with `git checkout HEAD -- src/rpc.sd7`.

- [ ] **Step 4: Full run and commit**

```bash
make test && git status --porcelain -uall
git add tests/transcript.py
git commit -m "transcript: pin string-id fidelity, and the -32601 that a string id used to lose"
```

Expected: 21 graded lines each `0 failed`; `git status --porcelain -uall` empty.

---

### Task 3: Record the decision where the rules live

**Files:**
- Modify: `README.md` (§ *What works*)
- Modify: `AGENTS.md` (§ *Protocol decisions that are easy to undo by accident*)
- Modify: `docs/seed7-cli.md` (new section under *AGENTS.md provenance*)

- [ ] **Step 1: Check which frozen tokens the edits touch**

```bash
grep -nFf tools/agents_required.txt AGENTS.md | head -50
grep -n 'id' tools/agents_required.txt
```

`tools/agents_gate.sh` greps 44 frozen tokens over the union of `AGENTS.md` and `docs/seed7-cli.md`, and a token whose only host sentence is being reworded prints `MISSING`. If a token sits in the sentence this plan reword, substitute it in the new wording — do not add a token to the list to paper over a moved sentence (`AGENTS.md` § *Citation defect, counted and closed* records what a documentation file propping up its own guard did).

- [ ] **Step 2: The two sentences**

`README.md` § *What works*: the error-handling list ("`-32002` before initialize, … `-32601` for unimplemented methods") gains one clause: a request is answered under the id the client sent, integer or string. `AGENTS.md` § *Protocol decisions that are easy to undo by accident* gains the rule and its cost in one bullet — echo `idJson`, never the integer, because a reply under a borrowed id is a client that waits forever with nothing on the wire to show it.

- [ ] **Step 3: The provenance section**

`docs/seed7-cli.md`: a section `Protocol decisions — the request id`, holding the three measurements this plan was written from, each with the command that produced it: the 24-body hostile probe and its `PROBE -32603 cases: none` result (which is what refuted the `-32603` premise); `{"id":"42"}` answered `id: 0`, and `{"id":"x","method":"no/such"}` answered with no frame at all; and `str(jsonValue)` of `{"id":"Ид"}` = `"Ид"` for a number-shaped string but `"\\1048;\\1076;"` for a real one — the reason the string arm re-escapes.

- [ ] **Step 4: Run the gate, then commit**

```bash
make test-agents && make test
git add README.md AGENTS.md docs/seed7-cli.md
git commit -m "docs: record the request-id rule, with the measurements behind it"
```

Expected: `agents: 44 checks, 0 failed` and 21 graded lines each `0 failed`.

---

## Definition of done

- A string id is echoed as a string at every step of a session, `initialize` included; an unknown method asked with a string id gets `-32601`.
- `idJsonOf`'s two arms are each proven by a mutant, and the non-ASCII claim is pinned by a length check that cannot corrupt the graded line.
- The `ponytail:` note at `src/rpc.sd7:8-11` is gone (its limit no longer exists), and `grep -rn 'integers only' src/ tests/ README.md AGENTS.md docs/` prints nothing.
- `make test` green; `git status --porcelain -uall` empty.

## Out of scope

- **A malformed position that reads as `line 0`.** Measured: `{"character":10.5}` → `intAt` catches `RANGE_ERROR` and returns the fallback, so hover answers `null` about line 0 rather than the intended line; `{"line":"3"}` does the same. `-32602 InvalidParams` is the arguable answer, and silently falling back is the current one. It is a decision, not a bug fix, and it is the one left over from the `-32603` hunt.
- **The `-32603` net.** Re-measured, not refuted: 24 well-framed hostile bodies against the real process (float and string and `null` and array ids, `params` as array/string/`null`, `positions:null`, `context:null`, `newName` as object, bodies that are a number/string/`null`/array/bool, a 5-deep nest) → **`PROBE -32603 cases: none`**. A review had claimed `integer(str(v))` on a float raises `NUMERIC_ERROR`; it raises `RANGE_ERROR`, the one `intAt` already catches. `AGENTS.md`'s "keep the net, it is unreachable" stands as written, and Task 3 records the probe that says so.
- **`$/`-prefixed requests other than the two handled.** With `isRequest` widened, `$/anything` asked as a request now correctly reaches the `-32601` arm — no new code, and no new method answered.

## Start here

`src/rpc.sd7:53-59` (`rpcMsg`), `:175-193` (`parseMessage`), `:208-235` (the two senders), `src/main.sd7:11-30` (where `isRequest` gates the two lifecycle errors).
