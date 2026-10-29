# Request-Id Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer a request with the `id` the client sent, and answer nothing at all when the message was a notification — so a client that uses a string `id` stops waiting for a reply that never carries its own key.

**Architecture:** `rpc.sd7` keeps the id as the JSON text to echo (`idJson`) instead of squeezing it into an `integer`, and `sendResult`/`sendError` return silently when that text is `"null"` — which is the spec's rule that a notification must not be answered. `lsp_server.sd7` and `main.sd7` pass the message to the senders instead of `msg.id`; no feature file changes, and no response shape changes.

**Tech Stack:** Seed7 5.4.10 (`s7`, `s7c`), the unit suites in `tests/` graded from their `N checks, M failed` line, `tests/transcript.py` driving the real process over real frames.

**Spec:** no spec file in this tree. The authority is LSP 3.18 Base Protocol: `RequestMessage.id` is `integer | string` (L1501-1520), `ResponseMessage.id` is `integer | string | null` and "`result` … REQUIRED on success" (L1524-1547), "A processed notification message must not send a response back. They work like events." (L1674), and for a `$/`-prefixed request "it must error the request with error code MethodNotFound" (L1690).

## Global Constraints

- Red first: write the check, run it, confirm it fails for the reason named, then implement. `make test` before and after.
- Nothing on the request path may raise onto stdout. Every accessor in `rpc.sd7` stays total, and no new code may print a non-ASCII character through `writeln` on plain stdout (`AGENTS.md`, `lsp_tst.sd7` grades on that stream).
- `AGENTS.md` invariant 7: outbound text goes through `jsonw.sd7`. `grep -rn 'addStr(w, str(' --include='*.sd7' src/` must stay empty — and the same rule forbids pasting `str(jsonValue)` of a *string* into a frame, because `str()` renders non-ASCII as `"\1048;"`, which is not valid JSON.
- `AGENTS.md` invariant 3: `transport.sd7` owns every outbound byte count. This plan emits no new byte arithmetic; `writeMessage` keeps counting.
- `docs/PROJECT_GRAPH.md` is generated and byte-compared by `tests/graph_test.sh`, so every commit that changes a `src/` line count regenerates it in the same commit.
- `-32700` keeps its `id: null` (a body that is not JSON has no id to echo). That path already exists as `sendParseError` and does not change.
- Do not run `make -j`: `tests/graph_test.sh:17-19` uses fixed `/tmp/g1`, `/tmp/s1` names.

## Review Focus

- A notification for a method that has a response (`textDocument/hover` with no `id`) must produce **no frame**. Measured today: it produces `{"id":0,"result":…}`. Pinned in Task 2.
- An unknown method asked as a **string-id request** must produce `-32601` with that id. Measured today: it produces nothing, so the client waits forever. Pinned in Task 2.
- A non-ASCII string id must come back as valid JSON. `str(jsonValue)` on `{"id":"Ид"}` answers `"a\1048;\1076;"`-style text, which no JSON decoder accepts — so the id is re-escaped through `jsonw`, not pasted. Pinned in Task 1.
- A string id that holds a client-escaped surrogate pair (`"\ud83d\ude00"`) must round-trip as the same two escapes, not as raw bytes no decoder is obliged to accept. Pinned in Task 1.
- An unusable id (`true`, `null`, `[1]`, `{"a":1}`) must not be answered as if it were a request. Measured today: `true` and `null` ids are answered `id: 0`; `[1]` and objects are silently dropped. After this plan all four are answered nothing, which is what the spec's "no response to a notification" allows. Pinned in Task 1 and Task 2.

---

### Task 1: Keep the id as the text to echo

**Files:**
- Modify: `src/rpc.sd7` (the `rpcMsg` struct at `53-59`, `parseMessage` at `175-193`, `sendResult` at `208-216`, `sendError` at `222-235`, and one new `const func string:`)
- Test: `tests/rpc_test.sd7`

**Interfaces:**
- Consumes: `rpc.atKey`, `rpc.category`, `jsonw.jsonEscape (inout string: buf, in string: stri)` (public in `src/jsonw.sd7:19`), `jsonw.finishJson`, `jsonw.raw`, `jsonw.field`, `jsonw.addStr`, `transport.writeMessage`.
- Produces in `rpc.sd7`:
  - `rpcMsg` field `var string: idJson is "null";` — the exact JSON text to echo, or `"null"`.
  - `const func string: idJsonOf (in jsonValue: idValue)` — returns the echo text for a `JSON_NUMBER` or `JSON_STRING`, and `"null"` for anything else, including an absent id.
  - `sendResult (in rpcMsg: msg, in string: resultJson)` and `sendError (in rpcMsg: msg, in integer: code, in string: message)` — both return without writing when `msg.idJson = "null"`.
  - The `integer: id` field is **deleted**. Its only reader was the echo.

- [ ] **Step 1: Write the failing checks**

Append to `tests/rpc_test.sd7` before `report("rpc")`. `parseMessage` is the unit under test; grade the field, never a frame:

```seed7
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":\"42\",\"method\":\"textDocument/hover\"}");
check("a string id is a request", str(m.isRequest), "TRUE");
check("and its id text is echoed quoted", m.idJson, "\"42\"");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":\"a\\u0040b\",\"method\":\"x\"}");
check("an escaped string id keeps its decoded text", m.idJson, "\"a@b\"");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":\"\\u0418\\u0434\",\"method\":\"x\"}");
check("and a non-ASCII id is re-escaped, not pasted", m.idJson, "\"Ид\"");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":\"\\ud83d\\ude00\",\"method\":\"x\"}");
check("and a lone-surrogate id escapes rather than ships 3-byte CESU", m.idJson, "\"\\ud83d\\ude00\"");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":10.5,\"method\":\"x\"}");
check("a float id echoes its own source text", m.idJson, "10.5");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":1e3,\"method\":\"x\"}");
check("and so does an exponent form", m.idJson, "1e3");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":true,\"method\":\"x\"}");
check("a bool id is not a request", str(m.isRequest), "FALSE");
check("and echoes null", m.idJson, "null");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":[1],\"method\":\"x\"}");
check("an array id is not a request", str(m.isRequest), "FALSE");
m := parseMessage("{\"jsonrpc\":\"2.0\",\"method\":\"textDocument/didOpen\"}");
check("a notification has no id text", m.idJson, "null");
check("and is not a request", str(m.isRequest), "FALSE");
```

The `"Ид"` expectation is written as the literal two characters (the source file is UTF-8, which `s7` reads as characters) — `src/jsonw.sd7` emits BMP text raw, and `lsp_tst.sd7`'s `check` compares strings, so the compare never prints it. Keep it that way: a FAIL print of this expectation would put non-ASCII on stdout, which is the class of thing `AGENTS.md` says corrupts the graded line. The check can still go red — `check` prints `expected:` / `got:` for the *length-safe* checks only if the message stays ASCII; see Step 5's note on the print.

- [ ] **Step 2: Run and confirm the reason**

```bash
make test-rpc
```

Expected: the suite no longer compiles — `rpcMsg` has no `idJson` field, so `str(m.isRequest)` lines pass and the `m.idJson` lines fail to analyse. The `Makefile`'s `test-%` rule grades the `N checks, 0 failed` line, and a suite that fails to analyse prints nothing and exits 0, so `make test-rpc` must FAIL with no graded line. That is the red; it is a different red from a value mismatch, and Step 4 is what turns it into the value kind.

- [ ] **Step 3: Work out the escape route for the non-ASCII expectation**

Before implementing, confirm `jsonw.jsonEscape` produces `"Ид"` (raw UTF-8 between quotes) for those two characters and `"\ud83d\ude00"` for a lone surrogate — both are already pinned in `tests/jsonw_test.sd7:49-52` and `:72-74`, so read those two checks rather than re-measuring. If `jsonEscape`'s output for a BMP non-ASCII character were an escape rather than the raw bytes, Step 1's `"\"Ид\""` expectation would have to be the escape form; the existing jsonw pins say it is raw, so the expectation stands.

- [ ] **Step 4: Implement**

`rpcMsg`: replace `var integer: id is 0;` with `var string: idJson is "null";`. Above `parseMessage`, add `idJsonOf` — a `number` answers `str(idValue)` (`readJson` keeps the source text, so `1e3` and `10.5` echo exactly what was sent), a `string` answers a buffer run through `jsonEscape` so non-ASCII and lone surrogates go out as JSON requires, and anything else answers `"null"`:

```seed7
const func string: idJsonOf (in jsonValue: idValue) is func
  result
    var string: out is "null";
  local
    var jsonWriter: w is jsonWriter.value;
  begin
    if category(idValue) = JSON_NUMBER then
      out := str(idValue);
    elsif category(idValue) = JSON_STRING then
      jsonEscape(w.buf, string(idValue));
      out := finishJson(w);
    end if;
  end func;
```

`jsonEscape` appends the quoted text and no trailing comma, so `finishJson` is the identity there — use it, because it is what the module already hands back, and do not add a second writer helper for one field.

`parseMessage`: replace `msg.isRequest := category(idValue) = JSON_NUMBER;` / `msg.id := intAt(root, "id", 0);` with

```seed7
      msg.idJson := idJsonOf(idValue);
      msg.isRequest := msg.idJson <> "null";
```

which makes a request "a message whose id is echoable" — the same set as `integer | string`, plus `10.5` and `1e3`, which are JSON numbers and must be answered too.

`sendResult` / `sendError`: take `in rpcMsg: msg`, start the body with `if msg.idJson = "null" then return; end if;` — no, `return` in a `proc` is `PROC_EXPECTED` (`AGENTS.md`); wrap the existing body in `if msg.idJson <> "null" then … end if;` instead — and replace `field(w, "id"); addInt(w, id);` with `field(w, "id"); raw(w, msg.idJson);`.

`src/main.sd7`: `sendError(msg.id, …)` → `sendError(msg, …)` (two sites, `:19` and `:23`). `sendParseError` does not change.

- [ ] **Step 5: Make the suite analyse, then run it**

```bash
make test-rpc
```

Expected: `rpc: 42 checks, 0 failed` (31 + the 11 new checks above; if the run says a different N, the run wins — correct the number in this line and say so in the commit body). `tests/rpc_test.sd7:17`'s existing `check("id", str(m.id), "7")` must be rewritten to `check("id", m.idJson, "7")` in the same commit — it reads the deleted field.

- [ ] **Step 6: Prove the checks can fail**

Three mutants, one at a time, each reverted with `git checkout HEAD -- src/rpc.sd7`:

1. `raw(w, msg.idJson)` → `addStr(w, string(idValue))`-equivalent paste (i.e. `out := str(idValue)` in the `JSON_STRING` arm): the `non-ASCII id is re-escaped` check FAILs — and if that FAIL's print corrupts the graded line, that is itself the finding; report it instead of editing the check.
2. `msg.isRequest := msg.idJson <> "null"` → `category(idValue) = JSON_NUMBER`: `a string id is a request` and `and its id text is echoed quoted` FAIL together (the field is still set, so the echo checks stay green and the *request* check goes red).
3. `idJsonOf`'s `elsif` arm deleted: the four string-id checks FAIL, `a float id echoes its own source text` stays green.

- [ ] **Step 7: Commit**

```bash
git add src/rpc.sd7 tests/rpc_test.sd7
git commit -m "rpc: keep the request id as the JSON text to echo, and answer no notification"
```

---

### Task 2: Pass the message, not the integer, through the dispatcher

`src/lsp_server.sd7` has 25 `sendResult(msg.id, …)` sites, one `sendError(msg.id, -32602, …)`, one `sendError(msg.id, -32601, …)` and `handlerFailed`'s `sendError(0, -32603, …)`. Task 1 changed the signatures, so this task is what makes the tree compile — it is deliberately one commit with no behaviour decision of its own.

**Files:**
- Modify: `src/lsp_server.sd7` (`handlerFailed` at `69-75`, and every `send` call in `handle`)
- Modify: `src/main.sd7:19,23` (already done in Task 1 Step 4 if the tree must compile there; if Task 1 was committed alone, `make test` stays red until this task lands — do not split them across PRs)
- Test: `tests/transcript.py`, `tests/lsp_server_test.sd7`

**Interfaces:**
- Consumes: Task 1's `sendResult (in rpcMsg: msg, …)` / `sendError (in rpcMsg: msg, …)`.
- Produces: `handlerFailed (in rpcMsg: msg, in string: kind, in string: body)`.

- [ ] **Step 1: Write the failing wire checks**

New scenario in `tests/transcript.py`, after the lifecycle block, using the harness's existing `frame` (ASCII, so its `Content-Length` equals its character count — `transcript.py:1093-1102` says why that matters and why it is fine *here*):

```python
STR_ID = [initialize(1),
          opened("/tmp/tt_strid.sd7", TRIVIAL),
          {"jsonrpc": "2.0", "id": "hover-1", "method": "textDocument/hover",
           "params": {"textDocument": {"uri": "/tmp/tt_strid.sd7"},
                      "position": {"line": 3, "character": 10}}},
          {"jsonrpc": "2.0", "id": "nope-1", "method": "not/a/method", "params": {}},
          {"jsonrpc": "2.0", "method": "textDocument/hover",
           "params": {"textDocument": {"uri": "/tmp/tt_strid.sd7"},
                      "position": {"line": 3, "character": 10}}},
          shutdown(9), exit_()]
replies, code, err, junk = run([frame(m) for m in STR_ID])
ids = [r.get("id") for r in replies]
expect("hover-1" in ids, "a string-id hover is answered with its own id (%s)" % ids)
expect("nope-1" in ids, "a string-id unknown method is answered, not dropped (%s)" % ids)
expect(0 not in ids, "and nothing is answered under a borrowed id 0 (%s)" % ids)
expect(next((r for r in replies if r.get("id") == "nope-1"), {}).get("error", {}).get("code")
       == -32601, "the unknown string-id request carries -32601")
expect(not any("id" in r and r["id"] is None and "result" in r for r in replies),
       "the idless hover produced no response frame at all")
expect(junk == 0, "the string-id run put only frames on stdout (junk=%d)" % junk)
one_answer_per_request(STR_ID, replies, "the string-id run")
```

`one_answer_per_request` counts frames carrying `result` or `error` against messages carrying an `id`. With the idless hover it must still balance: that message has no `id`, so it is not counted, and it must not be answered. Read the helper (`transcript.py:405-413`) before trusting that claim, and if it counts differently, fix the *check* to match the helper's documented meaning — not the helper.

- [ ] **Step 2: Run it**

```bash
make transcript
```

Expected: FAIL. Today the hover answers under `id: 0`, the unknown string-id request is dropped, and the idless hover is answered — so checks 1, 2, 3 and 5 all go red. `make test-lsp_server` also goes red, because `handlerFailed` still calls `sendError(0, …)` against Task 1's signature.

- [ ] **Step 3: Mechanise the call sites**

In `src/lsp_server.sd7`: `sendResult(msg.id,` → `sendResult(msg,` (25 sites) and `sendError(msg.id,` → `sendError(msg,` (2 sites). One `sed`, then read the diff:

```bash
sed -i 's/sendResult(msg\.id,/sendResult(msg,/g; s/sendError(msg\.id,/sendError(msg,/g' src/lsp_server.sd7
git diff --stat src/lsp_server.sd7
```

Expected: 27 changed lines, nothing else. Then `handlerFailed`: add `in rpcMsg: msg` as its first parameter, pass it to `sendError`, and keep the log line. In `src/main.sd7`, reset `msg := rpcMsg.value;` as the first statement inside the `while readMessage(body) do` body, before the `block`, so a raise inside `handle` can never echo the *previous* message's id — `msg` is loop-carried, and without the reset an idless malformed frame would answer with whatever id came before it.

- [ ] **Step 4: Run everything the tree can run**

```bash
make test-rpc && make test-lsp_server && make transcript
```

Expected: `rpc: 42 checks, 0 failed`, `lsp_server: 79 checks, 0 failed` (Task 2 adds no unit check), `transcript: 202 checks, 0 failed` (196 baseline + the 6 checks in Step 1). If this branch also carries the R-F10 plan, that baseline is 200 and the total is 206 — take the number from the run, not from this line.

- [ ] **Step 5: Prove the wire checks can fail**

1. Revert one site only — `sendResult(msg, initializeResultJson)` back to `sendResult(msg.id, …)` — and confirm the tree no longer compiles, which is the point: the integer field is gone, so a stale call site cannot survive silently. (`main.sd7` is where a missed site shows up first.)
2. Remove `msg := rpcMsg.value;` from `main.sd7` and hand-feed `{"id":"x","method":"nope"}` after an answered `initialize`: `transcript: 202 checks, 1 failed` — the borrowed-id check. This is the mutant that matters, because it is the failure the loop-carried record makes possible.

- [ ] **Step 6: Commit**

```bash
git add src/lsp_server.sd7 src/main.sd7 tests/transcript.py
git commit -m "rpc: thread the message to every sender; a request is answered under its own id"
```

---

### Task 3: Delete the recorded shortcut and say what changed

**Files:**
- Modify: `src/rpc.sd7` (the `ponytail: request ids are handled as integers only` comment at `8-11`)
- Modify: `README.md` (§ *What works*, the "Error handling is spec-shaped" sentence)
- Modify: `docs/PROJECT_GRAPH.md` (regenerated)

- [ ] **Step 1: Replace the comment with the rule**

The comment records a limit that no longer exists, so it goes. In its place, one line above `rpcMsg`: `# A request is a message whose id is echoable (integer or string); idJson carries the JSON
# text to echo and "null" means "notification -- answer nothing" (LSP 3.18 L1674).` Then grep for the old phrasing so no other file repeats a now-false claim: `grep -rn 'integers only\|echoes back as 0' src/ tests/ README.md AGENTS.md docs/`.

- [ ] **Step 2: README**

The *What works* sentence listing `-32002`/`-32600`/`-32700`/`-32601` gains one clause: requests are answered under the id the client sent, integer or string, and a notification is never answered. Keep it to one sentence — the spec lines are the authority, cited in the plan.

- [ ] **Step 3: Regenerate, run, check the tree is clean**

```bash
make graph && make test && git status --porcelain -uall
```

Expected: 21 graded lines, each `0 failed`; `git status --porcelain -uall` prints nothing (no `src/main`, no `profile_out`, no `.tmp`).

- [ ] **Step 4: Commit**

```bash
git add src/rpc.sd7 README.md docs/PROJECT_GRAPH.md
git commit -m "docs: the integer-id shortcut is gone; state the id-fidelity rule in its place"
```

---

## Definition of done

- A request with a string, float-valued or exponent id is answered under exactly the text the client sent; `{"id":"42"}` no longer produces `{"id":0,…}`.
- No notification — including a notification whose method happens to be `textDocument/hover` — produces a response frame.
- An unknown method asked with a string id produces `-32601`, not silence.
- Five wire checks and eleven unit checks exist, and each of the two suites reddens from a named production mutant.
- `make test` green; `git status --porcelain -uall` empty.

## Out of scope

- Ordering: responses stay in request order because the server is single-threaded. Nothing to do.
- `completionItem/resolve`, `$/progress`, and work-done tokens: not implemented, not advertised. A `$/`-prefixed **request** now correctly gets `-32601` because it reaches the `else` arm with an echoable id; no new method is answered here.
- The malformed-*position* question. `intAt` on `{"line":10.5}` answers `RANGE_ERROR` to the fallback, i.e. it reads the request as `line 0` — measured: hover returns `null` where `line 1` was meant, and `{"character":"8"}` reads as `character 0`. `-32602 InvalidParams` would be the honest answer. It is a deliberate choice, not an oversight: `strAt`/`boolAt`/`intAt` are all total on purpose, because an exception on the request path is the class of bug that puts bytes on the protocol channel. It needs its own decision and its own plan; nothing here depends on it.

## Measured, and therefore NOT planned

- **The `-32603` claim.** A review said a float in an integer slot or a `1e400` id costs the request. Refuted against the real process: 24 well-framed hostile bodies (`"character":10.5`, `"line":"3"`, `"line":1e999`, `"id":0.5/true/null/[1]`, `params` as array/string/`null`, `positions:null`, `context:null`, `newName` as object, bodies that are a number/string/`null`/array/bool, a 5-deep nest) → **`PROBE -32603 cases: none`**. `readJson` keeps a number's source text, and `integer("10.5")` raises `RANGE_ERROR` — the one `intAt` already catches. `AGENTS.md`'s "keep the net, it is unreachable" stands.
- **`{"id":"42"}` answered with `id: 0`** — this *is* the bug, and Task 1-3 fix it. The earlier `ponytail:` note claimed no client sends string ids; the LSP spec allows them, and the failure mode is a permanent hang, not a cosmetic mismatch.

## Start here

`src/rpc.sd7:53-59` (the struct), `:175-193` (`parseMessage`), `:208-235` (the two senders), then `src/main.sd7:11-30` for the loop-carried `msg`.
