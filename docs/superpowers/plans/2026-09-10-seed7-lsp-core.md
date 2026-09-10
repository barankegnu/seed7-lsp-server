# Seed7 LSP server core — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Seed7-language server that speaks LSP 3.18 over stdio and reports real
interpreter diagnostics for open documents.

**Architecture:** One long-lived `s7` process. `transport.sd7` does Content-Length
framing over UTF-8 stdio, `rpc.sd7` does JSON-RPC, `doc_store.sd7` is the only
position converter, `analysis.sd7` is the only file that imports `progs.s7i`
(`parseStri`/`getError`), and `lsp_server.sd7` dispatches. Every module is a plain
Seed7 program testable with no editor attached.

**Tech Stack:** SEED7 5.4.x interpreter (`s7`, on PATH), its standard library,
GNU Make, and one python3 script used only as the end-to-end transcript driver.

**Spec:** `docs/superpowers/specs/2026-09-10-seed7-lsp-server-design.md`

## Global Constraints

- Language of the product: **Seed7 only.** No other runtime in the shipped server.
- Requires a working `s7` on `PATH` and a resolvable Seed7 standard library.
- Protocol: LSP 3.18, JSON-RPC 2.0, `Content-Length` framing, CRLF (`\r\n`) header terminator.
- Positions are 0-based line/character, **UTF-16 code units**; announce
  `"positionEncoding": "utf-16"` and omit negotiation.
- Text sync: `TextDocumentSyncKind.Full` (1). Never incremental in this plan. The
  **last** element of `contentChanges` carries the whole text, not the first.
- Diagnostics come from `errorCount`/`getError`, never from scraping `s7` stderr
  (which goes to stderr and still exits 0).
- Only `analysis.sd7` may `include "progs.s7i"`. Only `doc_store.sd7` converts
  positions. Only `transport.sd7` counts bytes.
- Cap published diagnostics at 100 (`MAX_DIAGNOSTICS`).
- Source files are `.sd7`, live in `src/`, tests in `tests/`, both found via `-l src`.
- Every outbound frame goes through `jsonw.sd7`/`toJson`-style escaping. **Never**
  `str()` a `jsonValue` holding text: `json.s7i` serialises strings with Seed7
  `literal()` (`€` → `\8364;`), which is not valid JSON.

## File structure

| File | Responsibility | Built in |
|---|---|---|
| `src/lsp_tst.sd7` | `check`/`checkTrue`/`report` assert helpers, exit 1 on failure | Task 1 |
| `src/jsonw.sd7` | `jsonWriter`: emit correct JSON text, omit optionals by construction | Task 1 |
| `Makefile` | `make test`, `make server` | Task 1 |
| `src/transport.sd7` | `utf8Length`, `readMessage`, `writeMessage` | Task 2 |
| `src/doc_store.sd7` | `lsDoc`, line table, UTF-16 offsets, `lspRange` | Task 3 |
| `src/rpc.sd7` | `rpcMsg`, safe JSON accessors, result/error/notification send | Task 4 |
| `src/analysis.sd7` | `analyzeText` → `lspDiag` records, `.s7i` driver wrapper | Task 5 |
| `src/diagnostics.sd7` | dedupe/severity/cap, `publishDiagnostics` payload | Task 6 |
| `src/lsp_server.sd7` | capabilities, dispatch, document handlers, containment | Task 7 |
| `src/main.sd7` | `main`: the read loop and process exit codes | Task 7 |
| `tests/*.sd7`, `tests/transcript.py` | one suite per module + end-to-end frames | each task |

Tasks are strictly ordered: each consumes the interfaces of the tasks before it.

---

## Task 1: Test harness, JSON writer, build entry

**Files:**
- Create: `src/lsp_tst.sd7`, `src/jsonw.sd7`, `tests/jsonw_test.sd7`, `Makefile`
- Modify: `.gitignore` (append `*.sd7` artefact-free note: nothing to add — it already
  ignores object files; leave it alone)

**Interfaces:**
- Consumes: nothing.
- Produces: `jsonWriter` struct with `buf: string`;
  `openObject/closeObject/openArray/closeArray/field/addStr/addInt/addBool/addNull/raw`
  (all `(inout jsonWriter: w, ...)`), `finishJson(inout jsonWriter): string`;
  `check(in string, in string, in string)`, `checkTrue(in string, in boolean)`,
  `report(in string)`; globals `checksRun`, `checksFailed`.

**Why a hand-rolled writer instead of `declare_json_serde`:** LSP objects are full of
optional members. A Seed7 struct serialises *every* field, so an unset `range` would
ship as `null` and clients choke. Building objects field-by-field omits what is absent,
and puts correct escaping in one place we can test.

- [ ] **Step 1: Create the harness helper `src/lsp_tst.sd7`**

```seed7
$ include "seed7_05.s7i";
  include "stdio.s7i";

var integer: checksRun is 0;
var integer: checksFailed is 0;

const proc: check (in string: title, in string: got, in string: expected) is func
  begin
    checksRun +:= 1;
    if got = expected then
      writeln("ok   " <& title);
    else
      checksFailed +:= 1;
      writeln("FAIL " <& title);
      writeln("     expected: " <& expected);
      writeln("     got     : " <& got);
    end if;
  end func;

const proc: checkTrue (in string: title, in boolean: value) is func
  begin
    check(title, str(value), "TRUE");
  end func;

const proc: report (in string: suite) is func
  begin
    writeln(suite & ": " <& checksRun <& " checks, " <& checksFailed <& " failed");
    if checksFailed <> 0 then
      exit(1);
    end if;
  end func;
```

- [ ] **Step 2: Create `tests/jsonw_test.sd7` — it must fail before the writer exists**

```seed7
$ include "seed7_05.s7i";
  include "stdio.s7i";
  include "lsp_tst.sd7";
  include "jsonw.sd7";

const proc: main is func
  local
    var jsonWriter: w is jsonWriter.value;
  begin
    openObject(w);
      field(w, "message"); addStr(w, "ä€ 日本 \" \\ \n \9; end");
      field(w, "line");   addInt(w, 0);
      field(w, "ok");     addBool(w, TRUE);
      field(w, "ctrl");   addStr(w, "\1;\7;");
      field(w, "arr");
      openArray(w); addInt(w, 1); addInt(w, 2); closeArray(w);
      field(w, "nul"); addNull(w);
    closeObject(w);
    check("emit", finishJson(w),
          "{\"message\":\"ä€ 日本 \\\" \\\\ \\n \\t end\",\"line\":0,\"ok\":true," &
          "\"ctrl\":\"\\u0001\\u0007\",\"arr\":[1,2],\"nul\":null}");
    report("jsonw");
  end func;
```

- [ ] **Step 3: Run it and confirm it fails**

Run: `s7 -q -l src tests/jsonw_test.sd7`
Expected: FAIL — `*** tests/jsonw_test.sd7(4):5: Include file "jsonw.sd7" not found`
(the include at line 4 is the missing module; `lsp_tst.sd7` already resolves).

- [ ] **Step 4: Write `src/jsonw.sd7`**

```seed7
$ include "seed7_05.s7i";

const type: jsonWriter is new struct
    var string: buf is "";
  end struct;

const func string: hexByte (in integer: value) is
  return str(value radix 16 lpad0 2);

const proc: jsonEscape (inout string: buf, in string: stri) is func
  local
    var integer: i is 0;
    var char: ch is ' ';
  begin
    buf &:= "\"";
    for i range 1 to length(stri) do
      ch := stri[i];
      if ch = '"' then
        buf &:= "\\\"";
      elsif ch = '\\' then
        buf &:= "\\" & "\\";
      elsif ch = '\n' then
        buf &:= "\\n";
      elsif ch = '\r' then
        buf &:= "\\r";
      elsif ch = '\9;' then
        buf &:= "\\t";
      elsif ord(ch) < 32 then
        buf &:= "\\" <& "u00" <& hexByte(ord(ch));
      else
        buf &:= stri[i .. i];
      end if;
    end for;
    buf &:= "\"";
  end func;

const proc: trimComma (inout string: buf) is func
  begin
    if endsWith(buf, ",") then
      buf := buf[1 .. pred(length(buf))];
    end if;
  end func;

const proc: openObject (inout jsonWriter: w) is func
  begin
    w.buf &:= "{";
  end func;

const proc: closeObject (inout jsonWriter: w) is func
  begin
    trimComma(w.buf);
    w.buf &:= "}";
    w.buf &:= ",";
  end func;

const proc: openArray (inout jsonWriter: w) is func
  begin
    w.buf &:= "[";
  end func;

const proc: closeArray (inout jsonWriter: w) is func
  begin
    trimComma(w.buf);
    w.buf &:= "]";
    w.buf &:= ",";
  end func;

const proc: field (inout jsonWriter: w, in string: name) is func
  begin
    trimComma(w.buf);
    if endsWith(w.buf, "{") then
    else
      w.buf &:= ",";
    end if;
    jsonEscape(w.buf, name);
    w.buf &:= ":";
  end func;

const proc: addStr (inout jsonWriter: w, in string: value) is func
  begin
    jsonEscape(w.buf, value);
    w.buf &:= ",";
  end func;

const proc: addInt (inout jsonWriter: w, in integer: value) is func
  begin
    w.buf &:= str(value);
    w.buf &:= ",";
  end func;

const proc: addBool (inout jsonWriter: w, in boolean: value) is func
  begin
    if value then
      w.buf &:= "true";
    else
      w.buf &:= "false";
    end if;
    w.buf &:= ",";
  end func;

const proc: addNull (inout jsonWriter: w) is func
  begin
    w.buf &:= "null";
    w.buf &:= ",";
  end func;

const func string: finishJson (inout jsonWriter: w) is func
  result
    var string: out is "";
  begin
    trimComma(w.buf);
    out := w.buf;
  end func;

const proc: raw (inout jsonWriter: w, in string: text) is func
  begin
    w.buf &:= text;
    w.buf &:= ",";
  end func;
```

- [ ] **Step 5: Run the test and confirm it passes**

Run: `s7 -q -l src tests/jsonw_test.sd7`
Expected: `ok   emit` then `jsonw: 1 checks, 0 failed`.

- [ ] **Step 6: Add the Makefile**

`TESTS` grows one name per task; adding a name before its suite exists makes
`make test` fail for the wrong reason.

```make
S7      ?= s7
SRC     := src
TESTS   := jsonw

.PHONY: test server $(addprefix test-,$(TESTS))

test: $(addprefix test-,$(TESTS))

$(addprefix test-,$(TESTS)): test-%:
	@$(S7) -q -l $(SRC) tests/$*_test.sd7 || exit 1

server:
	@$(S7) -q -l $(SRC) $(SRC)/main.sd7
```

Run: `make test`
Expected: `ok   emit` and `jsonw: 1 checks, 0 failed`.
Note: the `server` target in this Makefile refers to `src/main.sd7`, which does not
exist until Task 7. `make test` never touches it, so leave the target alone.

- [ ] **Step 7: Commit**

```bash
git add src/lsp_tst.sd7 src/jsonw.sd7 tests/jsonw_test.sd7 Makefile
git commit -m "Add Seed7 assert harness and a JSON writer that escapes correctly"
```

---

## Task 2: Content-Length framing over UTF-8 stdio

**Files:**
- Create: `src/transport.sd7`, `tests/transport_test.sd7`
- Modify: `Makefile` (`TESTS := jsonw transport`)

**Interfaces:**
- Consumes: `lsp_tst.sd7` (test only).
- Produces: `utf8Length(in string): integer`; `writeMessage(in string)`;
  `readMessage(inout string): boolean` (FALSE at EOF or on a zero-length body).

**Facts this task encodes** (all measured, see spec §3.1): `utf8.s7i`'s
`STD_UTF8_IN/OUT/ERR` are mandatory — plain `write(STD_OUT, ...)` raises
`RANGE_ERROR` on non-ASCII. `gets(STD_UTF8_IN, n)` counts **bytes** (a 104-byte
body came back as 97 characters), so `Content-Length` is the byte count, which
Seed7's `length()` does not give.

- [ ] **Step 1: Write the failing test `tests/transport_test.sd7`**

```seed7
$ include "seed7_05.s7i";
  include "lsp_tst.sd7";
  include "transport.sd7";

const proc: main is func
  begin
    check("ascii",     str(utf8Length("hello")),  "5");
    check("latin",     str(utf8Length("ä")),      "2");
    check("euro",      str(utf8Length("€")),      "3");
    check("cjk",       str(utf8Length("日本")),    "6");
    check("astral",    str(utf8Length("𐐀")),       "4");
    check("mixed",     str(utf8Length("ä€ 日本")), "12");
    check("empty",     str(utf8Length("")),       "0");
    report("transport");
  end func;
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `s7 -q -l src tests/transport_test.sd7`
Expected: FAIL — `Include file "transport.sd7" not found`.

- [ ] **Step 3: Write `src/transport.sd7`**

```seed7
$ include "seed7_05.s7i";
  include "utf8.s7i";

const func integer: utf8Length (in string: stri) is func
  result
    var integer: n is 0;
  local
    var integer: i is 0;
    var integer: cp is 0;
  begin
    for i range 1 to length(stri) do
      cp := ord(stri[i]);
      if cp < 128 then
        n +:= 1;
      elsif cp < 2048 then
        n +:= 2;
      elsif cp < 65536 then
        n +:= 3;
      else
        n +:= 4;
      end if;
    end for;
  end func;

const proc: writeMessage (in string: body) is func
  begin
    write(STD_UTF8_OUT, "Content-Length: " <& utf8Length(body) <& "\r\n\r\n" <& body);
    flush(STD_UTF8_OUT);
  end func;

const func boolean: readMessage (inout string: body) is func
  result
    var boolean: okay is FALSE;
  local
    var string: line is "";
    var integer: contentLength is 0;
  begin
    if hasNext(STD_UTF8_IN) then
      line := getln(STD_UTF8_IN);
      while line <> "" and hasNext(STD_UTF8_IN) do
        if startsWith(line, "Content-Length: ") then
          contentLength := integer(line[17 ..]);
        end if;
        line := getln(STD_UTF8_IN);
      end while;
      if contentLength = 0 then
        # A header block with no Content-Length has no knowable end; report it
        # rather than swallowing the messages behind it in silence.
        writeln(STD_UTF8_ERR, "seed7-lsp: frame without Content-Length ignored");
      else
        body := gets(STD_UTF8_IN, contentLength);
        okay := length(body) <> 0;
      end if;
    end if;
  end func;
```

- [ ] **Step 4: Run the test and confirm it passes**

Run: `s7 -q -l src tests/transport_test.sd7`
Expected: `transport: 7 checks, 0 failed` (the astral case is the one that proves
characters ≠ bytes: `𐐀` is 4 bytes, 2 UTF-16 units, 1 Seed7 character).

- [ ] **Step 5: Commit**

```bash
git add src/transport.sd7 tests/transport_test.sd7 Makefile
git commit -m "Add LSP base protocol framing with UTF-8 byte lengths"
```

---

## Task 3: Document store and the only position converter

**Files:**
- Create: `src/doc_store.sd7`, `tests/doc_store_test.sd7`
- Modify: `Makefile` (`TESTS := jsonw transport doc_store`)

**Interfaces:**
- Consumes: `lsp_tst.sd7`.
- Produces: `lsDoc { text: string, version: integer, lineStart: array integer }`;
  `lineStarts(in string): array integer`; `utf16Before(in string, in integer): integer`;
  `lineWidth(in string, in integer): integer`;
  `setVersion(inout lsDoc, in string, in integer)`; `lineCount(in lsDoc): integer`;
  `lspRange(in lsDoc, in integer line1, in integer column1): string` — a JSON
  `{"line":n,"character":m}` object, 0-based, UTF-16 counted, clamped to the
  document on both axes.

`lspRange` returning JSON text rather than a struct is deliberate: callers embed it
straight into a `jsonWriter` with `raw()`, and there is exactly one place that formats
a position.

- [ ] **Step 1: Write the failing test `tests/doc_store_test.sd7`**

```seed7
$ include "seed7_05.s7i";
  include "lsp_tst.sd7";
  include "doc_store.sd7";

const proc: main is func
  local
    var lsDoc: doc is lsDoc.value;
    var lsDoc: crlf is lsDoc.value;
  begin
    check("lineStarts count", str(length(lineStarts("a\nbb\r\nccc"))), "3");
    check("lineStarts third", str(lineStarts("a\nbb\r\nccc")[3]), "7");
    setVersion(doc, "abc\nä€ 日本\nx", 1);
    check("line1 char0",   lspRange(doc, 1, 1), "{\"line\":0,\"character\":0}");
    check("line2 col1",    lspRange(doc, 2, 1), "{\"line\":1,\"character\":0}");
    check("line2 after 3 chars", lspRange(doc, 2, 4), "{\"line\":1,\"character\":3}");
    check("col past eol clamps", lspRange(doc, 1, 99), "{\"line\":0,\"character\":3}");
    check("line past eof clamps", lspRange(doc, 99, 1), "{\"line\":2,\"character\":0}");
    check("col 0 from semantic errors", lspRange(doc, 0, 0), "{\"line\":0,\"character\":0}");
    setVersion(crlf, "ab\r\ncd", 1);
    check("crlf second line start", lspRange(crlf, 2, 1), "{\"line\":1,\"character\":0}");
    check("astral counts twice", str(utf16Before("a𐐀b", 3) - utf16Before("a𐐀b", 1)), "3");
    check("trailing b counted", str(utf16Before("a𐐀b", 4) - utf16Before("a𐐀b", 1)), "4");
    check("version stored", str(crlf.version), "1");
    report("doc_store");
  end func;
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `s7 -q -l src tests/doc_store_test.sd7`
Expected: FAIL — `Include file "doc_store.sd7" not found`.

- [ ] **Step 3: Write `src/doc_store.sd7`**

```seed7
$ include "seed7_05.s7i";

const type: lsDoc is new struct
    var string: text is "";
    var integer: version is 0;
    var array integer: lineStart is 1 times 1;
  end struct;

const func array integer: lineStarts (in string: text) is func
  result
    var array integer: starts is 1 times 1;
  local
    var integer: i is 0;
  begin
    starts := 1 times 1;
    for i range 1 to length(text) do
      if text[i] = '\n' then
        if i = 1 or text[pred(i)] <> '\r' then
          starts &:= succ(i);
        end if;
      elsif text[i] = '\r' then
        if i < length(text) and text[succ(i)] = '\n' then
          starts &:= succ(succ(i));
        else
          starts &:= succ(i);
        end if;
      end if;
    end for;
  end func;

const func integer: utf16Before (in string: text, in integer: stop) is func
  result
    var integer: units is 0;
  local
    var integer: i is 0;
  begin
    for i range 1 to pred(stop) do
      if i > length(text) then
        units +:= 0;
      elsif ord(text[i]) >= 65536 then
        units +:= 2;
      else
        units +:= 1;
      end if;
    end for;
  end func;

const func integer: lineWidth (in string: text, in integer: start) is func
  result
    var integer: n is 0;
  local
    var integer: i is 0;
  begin
    i := start;
    while i <= length(text) and text[i] <> '\n' and text[i] <> '\r' do
      i +:= 1;
      n +:= 1;
    end while;
  end func;

const proc: setVersion (inout lsDoc: doc, in string: text, in integer: version) is func
  begin
    doc.text := text;
    doc.version := version;
    doc.lineStart := lineStarts(text);
  end func;

const func integer: lineCount (in lsDoc: doc) is
  return length(doc.lineStart);

const func string: lspRange (in lsDoc: doc, in integer: line1, in integer: column1) is func
  result
    var string: out is "";
  local
    var integer: lineIdx is 0;
    var integer: start is 1;
    var integer: ch is 0;
    var integer: width is 0;
  begin
    lineIdx := line1;
    if lineIdx < 1 then
      lineIdx := 1;
    elsif lineIdx > lineCount(doc) then
      lineIdx := lineCount(doc);
    end if;
    start := doc.lineStart[lineIdx];
    width := lineWidth(doc.text, start);
    ch := column1 - 1;
    if ch < 0 then
      ch := 0;
    elsif ch > width then
      ch := width;
    end if;
    out := "{\"line\":" <& lineIdx - 1 <& ",\"character\":" <&
           utf16Before(doc.text, start + ch) - utf16Before(doc.text, start) <& "}";
  end func;
```

- [ ] **Step 4: Run the test and confirm it passes**

Run: `s7 -q -l src tests/doc_store_test.sd7`
Expected: `doc_store: 12 checks, 0 failed`.

- [ ] **Step 5: Commit**

```bash
git add src/doc_store.sd7 tests/doc_store_test.sd7 Makefile
git commit -m "Add document store with clamped UTF-16 position mapping"
```

---

## Task 4: JSON-RPC layer with total accessors

**Files:**
- Create: `src/rpc.sd7`, `tests/rpc_test.sd7`
- Modify: `Makefile` (`TESTS := jsonw transport doc_store rpc`)

**Interfaces:**
- Consumes: `jsonw.sd7` (Task 1), `transport.sd7` (Task 2), `json.s7i`, `strifile.s7i`.
- Produces: `rpcMsg { method: string, id: integer, isRequest: boolean, params: jsonValue }`;
  `atKey(in jsonValue, in string): jsonValue` (never raises);
  `strAt(in jsonValue, in string, in string): string`;
  `intAt(in jsonValue, in string, in integer): integer`;
  `itemAt(in jsonValue, in integer): jsonValue`;
  `parseMessage(in string): rpcMsg`;
  `sendResult(in integer, in string)`, `sendError(in integer, in integer, in string)`,
  `sendNotification(in string, in string)`.

Two rules that are not negotiable, both learned the hard way:
`string(jsonValue)` raises **`ILLEGAL_ACTION`** (not RANGE_ERROR) when the value is not
a string, so accessors switch on `category(v)` against `JSON_NULL/BOOLEAN/NUMBER/STRING/
ARRAY/OBJECT` instead of catching their way out of everything; and request ids are
handled as integers (see the `ponytail:` comment in the file).

- [ ] **Step 1: Write the failing test `tests/rpc_test.sd7`**

```seed7
$ include "seed7_05.s7i";
  include "lsp_tst.sd7";
  include "rpc.sd7";

const proc: main is func
  local
    var rpcMsg: m is rpcMsg.value;
    var jsonValue: p is jsonValue.value;
  begin
    m := parseMessage("{\"jsonrpc\":\"2.0\",\"id\":7,\"method\":\"textDocument/hover\"," &
                     "\"params\":{\"textDocument\":{\"uri\":\"file:///a.sd7\"}," &
                     "\"position\":{\"line\":3,\"character\":12}}}");
    check("method",   m.method, "textDocument/hover");
    check("isRequest", str(m.isRequest), "TRUE");
    check("id",       str(m.id), "7");
    p := atKey(m.params, "textDocument");
    check("nested uri", strAt(p, "uri", "MISSING"), "file:///a.sd7");
    check("nested line", str(intAt(atKey(m.params, "position"), "line", -1)), "3");
    check("absent key falls back", strAt(m.params, "nope", "FB"), "FB");
    check("missing nested falls back", strAt(atKey(m.params, "nothere"), "uri", "FB"), "FB");
    m := parseMessage("{\"jsonrpc\":\"2.0\",\"method\":\"exit\"}");
    check("notification", str(m.isRequest), "FALSE");
    check("params absent", str(category(atKey(m.params, "x"))), str(JSON_NULL));
    check("number not string", strAt(m.params, "id", "FB"), "FB");
    check("array item text", str(category(itemAt(readJson("[\"t\"]"), 1))), str(JSON_STRING));
    report("rpc");
  end func;
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `s7 -q -l src tests/rpc_test.sd7`
Expected: FAIL — `Include file "rpc.sd7" not found`.

- [ ] **Step 3: Write `src/rpc.sd7`**

```seed7
$ include "seed7_05.s7i";
  include "json.s7i";
  include "strifile.s7i";
  include "jsonw.sd7";
  include "transport.sd7";

# ponytail: request ids are handled as integers only; every client tested
# (VS Code, eglot, lsp-mode, nvim) sends integers. A string id echoes back as
# 0, which the client ignores. Add raw-id text if a client ever needs it.

const type: rpcMsg is new struct
    var string: method is "";
    var integer: id is 0;
    var boolean: isRequest is FALSE;
    var jsonValue: params is jsonValue.value;
  end struct;

const func jsonValue: atKey (in jsonValue: obj, in string: name) is func
  result
    var jsonValue: value is jsonValue.value;
  begin
    block
      value := obj[name];
    exception
      catch RANGE_ERROR:     value := jsonValue(NULL);
      catch INDEX_ERROR:     value := jsonValue(NULL);
      catch ILLEGAL_ACTION:  value := jsonValue(NULL);
    end block;
  end func;

const func string: strAt (in jsonValue: obj, in string: name,
                          in string: fallback) is func
  result
    var string: value is "";
  local
    var jsonValue: found is jsonValue.value;
  begin
    found := atKey(obj, name);
    if category(found) = JSON_STRING then
      value := string(found);
    else
      value := fallback;
    end if;
  end func;

const func integer: intAt (in jsonValue: obj, in string: name,
                           in integer: fallback) is func
  result
    var integer: value is 0;
  local
    var jsonValue: found is jsonValue.value;
  begin
    value := fallback;
    found := atKey(obj, name);
    if category(found) = JSON_NUMBER then
      block
        value := integer(str(found));
      exception
        catch RANGE_ERROR: value := fallback;
      end block;
    end if;
  end func;

const func jsonValue: itemAt (in jsonValue: arr, in integer: index) is func
  result
    var jsonValue: value is jsonValue.value;
  begin
    if category(arr) = JSON_ARRAY then
      block
        value := arr[index];
      exception
        catch RANGE_ERROR:    value := jsonValue(NULL);
        catch INDEX_ERROR:    value := jsonValue(NULL);
      end block;
    end if;
  end func;

const func rpcMsg: parseMessage (in string: body) is func
  result
    var rpcMsg: msg is rpcMsg.value;
  local
    var jsonValue: root is jsonValue.value;
    var jsonValue: idValue is jsonValue.value;
  begin
    root := readJson(body);
    msg.method := strAt(root, "method", "");
    msg.params := atKey(root, "params");
    idValue := atKey(root, "id");
    msg.isRequest := category(idValue) = JSON_NUMBER;
    if msg.isRequest then
      msg.id := intAt(root, "id", 0);
    end if;
  end func;

const proc: sendResult (in integer: id, in string: resultJson) is func
  local
    var jsonWriter: w is jsonWriter.value;
  begin
    openObject(w);
      field(w, "jsonrpc"); addStr(w, "2.0");
      field(w, "id");      addInt(w, id);
      field(w, "result");  raw(w, resultJson);
    closeObject(w);
    writeMessage(finishJson(w));
  end func;

const proc: sendError (in integer: id, in integer: code, in string: message) is func
  local
    var jsonWriter: w is jsonWriter.value;
  begin
    openObject(w);
      field(w, "jsonrpc"); addStr(w, "2.0");
      field(w, "id");      addInt(w, id);
      field(w, "error");
      openObject(w);
        field(w, "code");    addInt(w, code);
        field(w, "message"); addStr(w, message);
      closeObject(w);
    closeObject(w);
    writeMessage(finishJson(w));
  end func;

const proc: sendNotification (in string: method, in string: paramsJson) is func
  local
    var jsonWriter: w is jsonWriter.value;
  begin
    openObject(w);
      field(w, "jsonrpc"); addStr(w, "2.0");
      field(w, "method");  addStr(w, method);
      field(w, "params");  raw(w, paramsJson);
    closeObject(w);
    writeMessage(finishJson(w));
  end func;
```

- [ ] **Step 4: Run the test and confirm it passes**

Run: `s7 -q -l src tests/rpc_test.sd7`
Expected: `rpc: 11 checks, 0 failed`.

- [ ] **Step 5: Commit**

```bash
git add src/rpc.sd7 tests/rpc_test.sd7 Makefile
git commit -m "Add JSON-RPC framing layer with non-raising param accessors"
```

---

## Task 5: Analysis through the interpreter

**Files:**
- Create: `src/analysis.sd7`, `tests/analysis_test.sd7`
- Modify: `Makefile` (`TESTS := jsonw transport doc_store rpc analysis`)

**Interfaces:**
- Consumes: `progs.s7i` (stdlib), `lsp_tst.sd7`.
- Produces: `lspDiag { line1: integer, column1: integer, message: string,
  atEof: boolean, severity: integer }`;
  `analysisResult { completed: boolean, diags: array lspDiag }`;
  `driverFor(in string): string`;
  `analyzeText(in string, in array string): analysisResult`.

`severity` is carried but **not decided** here — mapping is Task 6's job. `line1`/
`column1` stay 1-based as the interpreter reports them; `column1 = 0` means the
analyzer gave no column (every semantic error) and survives to Task 6.

The one thing to get right: `parseStri` accepts the buffer **text**, so no temp file
is ever written, and errors come from `errorCount` + `getError`, not from stderr.

- [ ] **Step 1: Write the failing test `tests/analysis_test.sd7`**

The lib path is the *installed* library directory, resolved from the interpreter
(`s7` finds it itself, so an empty `dirs` also works; it is passed explicitly to keep
the test independent of cwd).

```seed7
$ include "seed7_05.s7i";
  include "stdio.s7i";
  include "filesys.s7i";
  include "lsp_tst.sd7";
  include "analysis.sd7";

const proc: main is func
  local
    var analysisResult: a is analysisResult.value;
    var array string: dirs is 0 times "";
    var string: libPath is "/tmp/seed7_lsp_probe.s7i";
    var file: out is STD_NULL;
  begin
    # Empty libraryDirs is enough: the interpreter resolves its own stdlib,
    # so the test does not depend on where Seed7 happens to be installed.
    a := analyzeText("$ include \"seed7_05.s7i\";\nconst proc: main is func\n  begin\n    writeln(1 + \"a\");\n  end func;\n", dirs);
    check("semantic error count", str(length(a.diags)), "2");
    check("first error has no column", str(a.diags[1].column1), "0");
    check("not flagged as EOF", str(a.diags[1].atEof), "FALSE");
    a := analyzeText("$ include \"seed7_05.s7i\";\nconst proc: main is func\n  begin\n", dirs);
    check("truncated file has EOF class", str(a.diags[length(a.diags)].atEof), "TRUE");
    a := analyzeText("$ include \"seed7_05.s7i\";\nconst proc: main is func\n  begin\n    writeln(\"ok\");\n  end func;\n", dirs);
    check("valid file is clean", str(length(a.diags)), "0");
    checkTrue("driver wraps a library", pos(driverFor(libPath), "include \"/tmp/seed7_lsp_probe.s7i\";") <> 0);

    # A library file is not analysable alone -- prove the synthetic driver works
    # against a real .s7i rather than only checking the text of the wrapper.  The
    # probe file lives under /tmp and is truncated by "w" on every run.
    out := open(libPath, "w");
    write(out, "const func integer: probeDouble (in integer: n) is\n  return n * 2;\n");
    close(out);
    a := analyzeText(driverFor(libPath), dirs);
    check("driver analyses a real .s7i cleanly", str(length(a.diags)), "0");
    a := analyzeText(driverFor("/tmp/seed7_lsp_missing.s7i"), dirs);
    checkTrue("missing include is reported", length(a.diags) <> 0);
    report("analysis");
  end func;
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `s7 -q -l src tests/analysis_test.sd7`
Expected: FAIL — `Include file "analysis.sd7" not found`.

- [ ] **Step 3: Write `src/analysis.sd7`**

```seed7
$ include "seed7_05.s7i";
  include "progs.s7i";

const type: lspDiag is new struct
    var integer: line1 is 1;
    var integer: column1 is 0;
    var string: message is "";
    var boolean: atEof is FALSE;
    var integer: severity is 1;
  end struct;

const type: analysisResult is new struct
    var boolean: completed is FALSE;
    var array lspDiag: diags is 0 times lspDiag.value;
  end struct;

const func string: driverFor (in string: path) is
  return "$ include \"seed7_05.s7i\";\n  include " <& literal(path) <& ";\n";

const func analysisResult: analyzeText (in string: text,
                                        in array string: libraryDirs) is func
  result
    var analysisResult: out is analysisResult.value;
  local
    var program: prog is program.EMPTY;
    var parseError: err is parseError.value;
    var integer: i is 0;
    var lspDiag: diag is lspDiag.value;
  begin
    prog := parseStri(text, parseOptions.value, libraryDirs);
    out.completed := TRUE;
    for i range 1 to errorCount(prog) do
      err := getError(prog, i);
      diag.line1 := err.lineNumber;
      diag.column1 := err.columnNumber;
      diag.message := err.message;
      diag.atEof := err.message <> "" and pos(err.message, "END OF FILE") <> 0;
      out.diags &:= diag;
    end for;
  end func;
```

- [ ] **Step 4: Run the test and confirm it passes**

Run: `s7 -q -l src tests/analysis_test.sd7`
Expected: `analysis: 8 checks, 0 failed`. If `semantic error count` reports more
than 2, the interpreter version differs — record the version in the commit message
rather than weakening the assertion.

- [ ] **Step 5: Commit**

```bash
git add src/analysis.sd7 tests/analysis_test.sd7 Makefile
git commit -m "Add interpreter-backed analysis returning structured errors"
```

---

## Task 6: Diagnostic mapping and publication

**Files:**
- Create: `src/diagnostics.sd7`, `tests/diagnostics_test.sd7`
- Modify: `Makefile` (`TESTS := jsonw transport doc_store rpc analysis diagnostics`)

**Interfaces:**
- Consumes: `analysis.sd7` (`lspDiag`), `doc_store.sd7` (`lspRange`), `jsonw.sd7`,
  `rpc.sd7` (`sendNotification`).
- Produces: `seenHash` type, `SEV_ERROR`/`SEV_WARNING`/`SEV_INFORMATION`,
  `mapDiagnostics(in array lspDiag, in integer maxPublish): array lspDiag`,
  `diagnosticsJson(in string uri, in lsDoc, in array lspDiag): string`,
  `publish(in string uri, in lsDoc, in array lspDiag)`.

The three mapping rules (spec §4.4), each with a check: dedupe on
`(line, column, message)` because one missing terminator produced 13 raw errors;
downgrade `END OF FILE`-class messages to Information because a truncated buffer is
the normal state while typing; clamp the count to `maxPublish`. Semantic errors
(`column1 = 0`) get the whole line by asking `lspRange` for an absurd column and
letting it clamp — no second position function.

- [ ] **Step 1: Write the failing test `tests/diagnostics_test.sd7`**

```seed7
$ include "seed7_05.s7i";
  include "lsp_tst.sd7";
  include "diagnostics.sd7";

const proc: main is func
  local
    var array lspDiag: raw is 0 times lspDiag.value;
    var array lspDiag: mapped is 0 times lspDiag.value;
    var lsDoc: doc is lsDoc.value;
    var lspDiag: d is lspDiag.value;
  begin
    setVersion(doc, "abc\nä€ 日本\nx", 1);
    d.line1 := 1; d.column1 := 3; d.message := "Expr expected"; d.atEof := FALSE;
    raw &:= d;
    raw &:= d;
    d.line1 := 3; d.column1 := 0; d.message := "Match failed"; d.atEof := FALSE;
    raw &:= d;
    d.line1 := 3; d.column1 := 0; d.message := "\"end\" expected found \"END OF FILE\""; d.atEof := TRUE;
    raw &:= d;
    mapped := mapDiagnostics(raw, 100);
    check("dedupe drops the repeat", str(length(mapped)), "3");
    check("syntax error is Error", str(mapped[1].severity), "1");
    check("EOF class is Information", str(mapped[3].severity), "3");
    check("cap respected", str(length(mapDiagnostics(raw, 2))), "2");
    check("empty list", str(length(mapDiagnostics(0 times lspDiag.value, 100))), "0");
    check("json", diagnosticsJson("file:///a.sd7", doc, mapped),
          "{\"uri\":\"file:///a.sd7\",\"diagnostics\":[" &
          "{\"range\":{\"start\":{\"line\":0,\"character\":2},\"end\":{\"line\":0,\"character\":3}},\"severity\":1,\"source\":\"seed7\",\"message\":\"Expr expected\"}," &
          "{\"range\":{\"start\":{\"line\":2,\"character\":0},\"end\":{\"line\":2,\"character\":1}},\"severity\":1,\"source\":\"seed7\",\"message\":\"Match failed\"}," &
          "{\"range\":{\"start\":{\"line\":2,\"character\":0},\"end\":{\"line\":2,\"character\":1}},\"severity\":3,\"source\":\"seed7\",\"message\":\"\\\"end\\\" expected found \\\"END OF FILE\\\"\"}]}");
    report("diagnostics");
  end func;
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `s7 -q -l src tests/diagnostics_test.sd7`
Expected: FAIL — `Include file "diagnostics.sd7" not found`.

- [ ] **Step 3: Write `src/diagnostics.sd7`**

```seed7
$ include "seed7_05.s7i";
  include "analysis.sd7";
  include "doc_store.sd7";
  include "jsonw.sd7";
  include "rpc.sd7";

const type: seenHash is hash [string] integer;

const integer: SEV_ERROR is 1;
const integer: SEV_WARNING is 2;
const integer: SEV_INFORMATION is 3;

const func array lspDiag: mapDiagnostics (in array lspDiag: raw,
                                          in integer: maxPublish) is func
  result
    var array lspDiag: out is 0 times lspDiag.value;
  local
    var seenHash: seen is seenHash.EMPTY_HASH;
    var integer: i is 0;
    var lspDiag: diag is lspDiag.value;
    var string: keyStr is "";
  begin
    for i range 1 to length(raw) do
      diag := raw[i];
      keyStr := str(diag.line1) & ":" <& diag.column1 <& ":" <& diag.message;
      if keyStr in seen then
        # duplicate from the analyzer's error recovery, drop it
      elsif diag.message = "" then
      elsif length(out) >= maxPublish then
      else
        seen @:= [keyStr] 1;
        if diag.atEof then
          diag.severity := SEV_INFORMATION;
        else
          diag.severity := SEV_ERROR;
        end if;
        out &:= diag;
      end if;
    end for;
  end func;

const func string: diagnosticsJson (in string: uri, in lsDoc: doc,
                                    in array lspDiag: diags) is func
  result
    var string: out is "";
  local
    var jsonWriter: w is jsonWriter.value;
    var integer: i is 0;
  begin
    openObject(w);
      field(w, "uri"); addStr(w, uri);
      field(w, "diagnostics");
      openArray(w);
        for i range 1 to length(diags) do
          openObject(w);
            field(w, "range");
            openObject(w);
              field(w, "start"); raw(w, lspRange(doc, diags[i].line1, diags[i].column1));
              field(w, "end");
              if diags[i].column1 > 0 then
                raw(w, lspRange(doc, diags[i].line1, diags[i].column1 + 1));
              else
                raw(w, lspRange(doc, diags[i].line1, 2147483647));
              end if;
            closeObject(w);
            field(w, "severity"); addInt(w, diags[i].severity);
            field(w, "source");   addStr(w, "seed7");
            field(w, "message");  addStr(w, diags[i].message);
          closeObject(w);
        end for;
      closeArray(w);
    closeObject(w);
    out := finishJson(w);
  end func;

const proc: publish (in string: uri, in lsDoc: doc,
                     in array lspDiag: diags) is func
  begin
    sendNotification("textDocument/publishDiagnostics",
                     diagnosticsJson(uri, doc, diags));
  end func;
```

- [ ] **Step 4: Run the test and confirm it passes**

Run: `s7 -q -l src tests/diagnostics_test.sd7`
Expected: `diagnostics: 6 checks, 0 failed`.

- [ ] **Step 5: Commit**

```bash
git add src/diagnostics.sd7 tests/diagnostics_test.sd7 Makefile
git commit -m "Add diagnostic dedupe, severity mapping and publication"
```

---

## Task 7: Dispatch, lifecycle, exit codes

**Files:**
- Create: `src/lsp_server.sd7`, `src/main.sd7`, `tests/lsp_server_test.sd7`
- Modify: `Makefile` (`TESTS := jsonw transport doc_store rpc analysis diagnostics lsp_server`)

**Interfaces:**
- Consumes: every earlier module.
- Produces: `MAX_DIAGNOSTICS`, `capabilitiesJson`, `initializeResultJson`,
  `pathOf(in string): string`, `analyzeDocument(in string): analysisResult`,
  `refresh(in string)`, `handleChange(in rpcMsg)`, `handle(in rpcMsg)`;
  globals `openDocs`, `libraryDirs`, `gotInitialize`, `gotShutdown`;
  `src/main.sd7` provides `main`.

`main` lives in its own file **because** a file defining `main` cannot be included by a
test (redeclaration). Dispatch is one `if/elsif` chain over `msg.method`; a
`handler` table would be a factory for one product.

Behaviour pinned by the transcript in Task 8: `initialize` answers capabilities and
sets the flag; any request before it answers `-32002` (except `exit`); unknown
*requests* get `-32601` while unknown *notifications* are dropped; `shutdown` answers
`null` and later requests are refused; `exit` is 0 only if initialize+shutdown were
both seen, else 1. Every handler body runs inside `block ... exception` over the
real errcode set — an uncaught exception kills the process (once with no message at
all), and a dead server is worse than a wrong answer.

- [ ] **Step 1: Write the failing test `tests/lsp_server_test.sd7`**

```seed7
$ include "seed7_05.s7i";
  include "lsp_tst.sd7";
  include "lsp_server.sd7";

const proc: main is func
  begin
    check("space decoded",  pathOf("file:///tmp/my%20dir/a.sd7"), "/tmp/my dir/a.sd7");
    check("plain uri kept", pathOf("/tmp/a.sd7"), "/tmp/a.sd7");
    checkTrue("caps announce full sync",
              pos(capabilitiesJson, "\"textDocumentSync\":{\"openClose\":true,\"change\":1}") <> 0);
    checkTrue("caps are valid json wrapper", startsWith(capabilitiesJson, "{") and
              endsWith(capabilitiesJson, "}"));
    report("lsp_server");
  end func;
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `s7 -q -l src tests/lsp_server_test.sd7`
Expected: FAIL — `Include file "lsp_server.sd7" not found`.

- [ ] **Step 3: Write `src/lsp_server.sd7`**

```seed7
$ include "seed7_05.s7i";
  include "stdio.s7i";
  include "utf8.s7i";
  include "transport.sd7";
  include "rpc.sd7";
  include "doc_store.sd7";
  include "analysis.sd7";
  include "diagnostics.sd7";
  include "encoding.s7i";

const integer: MAX_DIAGNOSTICS is 100;

const type: docMap is hash [string] lsDoc;

var docMap: openDocs is docMap.EMPTY_HASH;
var array string: libraryDirs is 0 times "";
var boolean: gotInitialize is FALSE;
var boolean: gotShutdown is FALSE;

const proc: note (in string: text) is func
  begin
    writeln(STD_UTF8_ERR, "seed7-lsp: " <& text);
  end func;

# A handler that raises must cost the request, never the server: log enough to
# reproduce it, answer a JSON-RPC internal error, and keep reading.
const proc: handlerFailed (in string: kind, in string: body) is func
  begin
    note("handler failed (" <& kind <& "): " <& body);
    sendError(0, -32603, "internal error: " <& kind);
  end func;

const func string: capabilitiesJson is func
  result
    var string: out is "";
  local
    var jsonWriter: w is jsonWriter.value;
  begin
    openObject(w);
      field(w, "textDocumentSync");
      openObject(w);
        field(w, "openClose"); addBool(w, TRUE);
        field(w, "change");    addInt(w, 1);
      closeObject(w);
      field(w, "diagnosticProvider");
      openObject(w);
        field(w, "interFileDependencies"); addBool(w, FALSE);
        field(w, "workspaceDiagnostics");  addBool(w, FALSE);
      closeObject(w);
      field(w, "positionEncoding"); addStr(w, "utf-16");
    closeObject(w);
    out := finishJson(w);
  end func;

const func string: initializeResultJson is func
  result
    var string: out is "";
  local
    var jsonWriter: w is jsonWriter.value;
  begin
    openObject(w);
      field(w, "capabilities"); raw(w, capabilitiesJson);
      field(w, "serverInfo");
      openObject(w);
        field(w, "name");    addStr(w, "seed7-lsp");
        field(w, "version"); addStr(w, "0.1");
      closeObject(w);
    closeObject(w);
    out := finishJson(w);
  end func;

const func string: pathOf (in string: uri) is func
  result
    var string: path is "";
  begin
    if startsWith(uri, "file://") then
      path := fromPercentEncoded(uri[8 ..]);
    else
      path := uri;
    end if;
  end func;

const func analysisResult: analyzeDocument (in string: uri) is func
  result
    var analysisResult: out is analysisResult.value;
  local
    var lsDoc: doc is lsDoc.value;
    var string: text is "";
  begin
    if uri in openDocs then
      doc := openDocs[uri];
      if endsWith(uri, ".s7i") then
        out := analyzeText(driverFor(pathOf(uri)), libraryDirs);
      else
        out := analyzeText(doc.text, libraryDirs);
      end if;
    end if;
  end func;

const proc: refresh (in string: uri) is func
  local
    var analysisResult: a is analysisResult.value;
    var array lspDiag: mapped is 0 times lspDiag.value;
  begin
    a := analyzeDocument(uri);
    mapped := mapDiagnostics(a.diags, MAX_DIAGNOSTICS);
    publish(uri, openDocs[uri], mapped);
  end func;

const proc: handleChange (in rpcMsg: msg) is func
  local
    var string: uri is "";
    var jsonValue: changes is jsonValue.value;
    var jsonValue: last is jsonValue.value;
  begin
    uri := strAt(atKey(msg.params, "textDocument"), "uri", "");
    if uri <> "" and uri in openDocs then
      # Full sync: the last change object holds the whole text (LSP 3.18).
      changes := atKey(msg.params, "contentChanges");
      if category(changes) = JSON_ARRAY then
        last := itemAt(changes, length(changes));
      end if;
      if category(last) = JSON_OBJECT then
        setVersion(openDocs[uri], strAt(last, "text", openDocs[uri].text),
                   intAt(atKey(msg.params, "textDocument"), "version",
                         openDocs[uri].version));
      end if;
      refresh(uri);
    end if;
  end func;

const proc: handle (in rpcMsg: msg) is func
  local
    var string: uri is "";
  begin
    if msg.method = "initialize" then
      gotInitialize := TRUE;
      sendResult(msg.id, initializeResultJson);
    elsif msg.method = "initialized" then
    elsif msg.method = "$/setTrace" then
    elsif msg.method = "$/cancelRequest" then
    elsif msg.method = "shutdown" then
      gotShutdown := TRUE;
      sendResult(msg.id, "null");
    elsif msg.method = "exit" then
      if gotInitialize and gotShutdown then
        exit(0);
      else
        exit(1);
      end if;
    elsif msg.method = "textDocument/didOpen" then
      uri := strAt(atKey(msg.params, "textDocument"), "uri", "");
      if uri <> "" then
        openDocs @:= [uri] lsDoc.value;
        setVersion(openDocs[uri], strAt(atKey(msg.params, "textDocument"), "text", ""),
                   intAt(atKey(msg.params, "textDocument"), "version", 0));
        refresh(uri);
      end if;
    elsif msg.method = "textDocument/didChange" then
      handleChange(msg);
    elsif msg.method = "textDocument/didClose" then
      uri := strAt(atKey(msg.params, "textDocument"), "uri", "");
      if uri in openDocs then
        publish(uri, openDocs[uri], 0 times lspDiag.value);
        excl(openDocs, uri);
      end if;
    else
      if msg.isRequest then
        sendError(msg.id, -32601, "Method not found: " <& msg.method);
      end if;
    end if;
  end func;
```

- [ ] **Step 4: Write the entry point `src/main.sd7`**

```seed7
$ include "seed7_05.s7i";
  include "lsp_server.sd7";

const proc: main is func
  local
    var string: body is "";
    var rpcMsg: msg is rpcMsg.value;
  begin
    libraryDirs &:= ".";
    while readMessage(body) do
      if body = "" then
      else
        block
          msg := parseMessage(body);
          if not gotInitialize and msg.method <> "initialize" and msg.method <> "exit" then
            if msg.isRequest then
              sendError(msg.id, -32002, "Server was not initialized");
            end if;
          elsif gotShutdown and msg.method <> "exit" then
            if msg.isRequest then
              sendError(msg.id, -32600, "InvalidRequest: server is shut down");
            end if;
          else
            handle(msg);
          end if;
        exception
          catch MEMORY_ERROR:    handlerFailed("memory", body);
          catch ASSERTION_ERROR: handlerFailed("assertion", body);
          catch NUMERIC_ERROR:   handlerFailed("numeric", body);
          catch OVERFLOW_ERROR:  handlerFailed("overflow", body);
          catch RANGE_ERROR:     handlerFailed("range", body);
          catch INDEX_ERROR:     handlerFailed("index", body);
          catch FILE_ERROR:      handlerFailed("file", body);
          catch DATABASE_ERROR:  handlerFailed("database", body);
          catch GRAPHIC_ERROR:   handlerFailed("graphic", body);
          catch ILLEGAL_ACTION:  handlerFailed("illegal action", body);
          catch CREATE_ERROR:    handlerFailed("create", body);
          catch DESTROY_ERROR:   handlerFailed("destroy", body);
          catch COPY_ERROR:      handlerFailed("copy", body);
          catch IN_ERROR:        handlerFailed("input", body);
        end block;
      end if;
    end while;
    if gotInitialize and gotShutdown then
      exit(0);
    end if;
  end func;
```

- [ ] **Step 5: Run the unit test and confirm it passes**

Run: `s7 -q -l src tests/lsp_server_test.sd7`
Expected: `lsp_server: 4 checks, 0 failed`.

- [ ] **Step 6: Smoke the binary by hand**

Run: `printf '' | make -s server; echo $?`
Expected: no output, no crash, and **exit status 0**. Falling off the read loop at EOF
is not the `exit` notification: status 1 comes from handling `exit` when `shutdown`
was never seen, which Task 8's transcript asserts. Corrected from the plan's first
draft, which claimed status 1 here — the behaviour is 0, because `main` ends without
calling `exit` when the loop simply runs out of input.

- [ ] **Step 7: Commit**

```bash
git add src/lsp_server.sd7 src/main.sd7 tests/lsp_server_test.sd7 Makefile
git commit -m "Add LSP dispatch, capability set and crash containment"
```

---

## Task 8: End-to-end transcript and client launch snippets

**Files:**
- Create: `tests/transcript.py`, `README.md`
- Modify: `Makefile` — final form:

```make
S7      ?= s7
SRC     := src
TESTS   := jsonw transport doc_store rpc analysis diagnostics lsp_server

.PHONY: test server $(addprefix test-,$(TESTS)) transcript

test: $(addprefix test-,$(TESTS)) transcript

$(addprefix test-,$(TESTS)): test-%:
	@$(S7) -q -l $(SRC) tests/$*_test.sd7 || exit 1

transcript:
	@python3 tests/transcript.py

server:
	@$(S7) -q -l $(SRC) $(SRC)/main.sd7
```

**Interfaces:**
- Consumes: the whole server, run as a child process.
- Produces: `make test` covering the full request path, and documented launch
  commands for VS Code, Emacs and Neovim.

This is the conformance gate for every later feature. python3 drives it rather than
Seed7 (`s7` spawning a child and feeding it frames needs `process.s7i` plumbing for no
gain, and the spec's §7 said `tests/transcript.sd7` — **amend the spec to name
`tests/transcript.py`** when committing this task).

- [ ] **Step 1: Write `tests/transcript.py`**

```python
#!/usr/bin/env python3
"""Drives src/main.sd7 over stdio with real LSP frames and checks the replies."""
import json, subprocess, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CMD = ["s7", "-q", "-l", os.path.join(ROOT, "src"), os.path.join(ROOT, "src", "main.sd7")]
fails = []
passed = 0

def frame(obj):
    body = json.dumps(obj).encode("utf-8")
    return b"Content-Length: %d\r\n\r\n" % len(body) + body

def read_frames(stream, count):
    out = []
    while len(out) < count:
        line = stream.readline()
        if not line:
            break
        headers = {}
        while line.strip():
            k, _, v = line.decode().partition(":")
            headers[k.strip().lower()] = v.strip()
            line = stream.readline()
        n = int(headers["content-length"])
        buf = b""
        while len(buf) < n:
            chunk = stream.read(n - len(buf))
            if not chunk:
                break
            buf += chunk
        out.append(json.loads(buf.decode("utf-8")))
    return out

def run(frames):
    p = subprocess.Popen(CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, cwd="/tmp")
    out, err = p.communicate(b"".join(frames), timeout=60)
    import io
    replies = read_frames(io.BytesIO(out), 10 ** 6) if out else []
    return replies, p.returncode, err.decode("utf-8", "replace")

def expect(cond, label):
    global passed
    print(("ok   " if cond else "FAIL ") + label)
    if cond:
        passed += 1
    else:
        fails.append(label)

BROKEN = '$ include "seed7_05.s7i";\nconst proc: main is func\n  begin\n    writeln(1 + "a");\n  end func;\n'
FIXED = '$ include "seed7_05.s7i";\nconst proc: main is func\n  begin\n    writeln("日本");\n  end func;\n'

msgs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"capabilities": {}, "processId": None, "rootUri": None}},
    {"jsonrpc": "2.0", "method": "initialized", "params": {}},
    {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params":
        {"textDocument": {"uri": "file:///tmp/tt_a.sd7", "languageId": "seed7", "version": 1, "text": BROKEN}}},
    {"jsonrpc": "2.0", "method": "textDocument/didChange", "params":
        {"textDocument": {"uri": "file:///tmp/tt_a.sd7", "version": 2},
         "contentChanges": [{"text": FIXED}]}},
    {"jsonrpc": "2.0", "id": 2, "method": "textDocument/hover", "params":
        {"textDocument": {"uri": "file:///tmp/tt_a.sd7"}, "position": {"line": 3, "character": 4}}},
    {"jsonrpc": "2.0", "id": 3, "method": "shutdown"},
    {"jsonrpc": "2.0", "method": "exit"},
]
replies, code, err = run([frame(m) for m in msgs])
by_id = {r.get("id"): r for r in replies if "id" in r}
notes = [r for r in replies if r.get("method") == "textDocument/publishDiagnostics"]

init = by_id.get(1, {})
expect("capabilities" in init.get("result", {}), "initialize returns capabilities")
expect(init["result"]["capabilities"]["textDocumentSync"]["change"] == 1, "sync kind is Full")
expect(init["result"]["capabilities"]["positionEncoding"] == "utf-16", "positionEncoding utf-16")
expect(len(notes) == 2, "two publishDiagnostics (broken then fixed), got %d" % len(notes))
if len(notes) == 2:
    first = notes[0]["params"]["diagnostics"]
    second = notes[1]["params"]["diagnostics"]
    expect(any(d["severity"] == 1 for d in first), "broken file publishes an Error")
    expect(first[0]["range"]["start"]["line"] == 3, "diagnostic points at line index 3")
    expect(first[0]["range"]["start"]["character"] == 0, "semantic error starts at char 0")
    expect(second == [], "fixed file clears diagnostics, got %s" % second)
    expect(notes[0]["params"]["uri"] == "file:///tmp/tt_a.sd7", "diagnostics carry the uri")
expect(by_id.get(2, {}).get("error", {}).get("code") == -32601, "unimplemented hover -> -32601")
expect("result" in by_id.get(3, {}) and by_id[3]["result"] is None, "shutdown answers null")
expect(code == 0, "exit after shutdown is status 0, got %d" % code)

replies, code, err = run([frame({"jsonrpc": "2.0", "id": 9, "method": "textDocument/hover",
                            "params": {"textDocument": {"uri": "file:///tmp/x.sd7"},
                                       "position": {"line": 0, "character": 0}}}),
                     frame({"jsonrpc": "2.0", "method": "exit"})])
expect(replies and replies[0]["error"]["code"] == -32002, "request before initialize -> -32002")
expect(code == 1, "exit without shutdown is status 1, got %d" % code)

# --- crash containment: one bad frame must cost a request, not the server ---
replies, code, err = run([
    frame(msgs[0]),
    b"Content-Length: 16\r\n\r\n{not json at all",
    frame({"jsonrpc": "2.0", "id": 5, "method": "shutdown"}),
    frame({"jsonrpc": "2.0", "method": "exit"}),
])
by_id = {r.get("id"): r for r in replies if "id" in r}
expect(by_id.get(5, {}).get("result") is None, "server still answers after a malformed frame")
expect("handler failed" in err, "the handler failure names itself on stderr")
expect(any(r.get("error", {}).get("code") == -32603 for r in replies),
       "malformed frame answered with an internal error")
expect("handler failed" in err, "the failure is logged to stderr, not swallowed")

# --- a frame with no Content-Length has no knowable end: report it ---
replies, code, err = run([
    frame(msgs[0]),
    b"Content-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n",
    frame({"jsonrpc": "2.0", "id": 9, "method": "shutdown"}),
    frame({"jsonrpc": "2.0", "method": "exit"}),
])
expect("without Content-Length" in err, "frame lacking Content-Length is reported")

# --- spec 3.4: after shutdown, later requests are refused as InvalidRequest ---
replies, code, err = run([
    frame(msgs[0]),
    frame({"jsonrpc": "2.0", "id": 6, "method": "shutdown"}),
    frame({"jsonrpc": "2.0", "id": 7, "method": "textDocument/hover",
           "params": {"textDocument": {"uri": "file:///tmp/tt_a.sd7"},
                      "position": {"line": 0, "character": 0}}}),
    frame({"jsonrpc": "2.0", "method": "exit"}),
])
expect(any(r.get("id") == 7 and r.get("error", {}).get("code") == -32600 for r in replies),
       "request after shutdown refused with -32600")

# --- full sync: the LAST contentChanges element wins ---
replies, code, err = run([
    frame(msgs[0]), frame(msgs[1]),
    frame({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params":
           {"textDocument": {"uri": "file:///tmp/tt_b.sd7", "languageId": "seed7",
                             "version": 1, "text": BROKEN}}}),
    frame({"jsonrpc": "2.0", "method": "textDocument/didChange", "params":
           {"textDocument": {"uri": "file:///tmp/tt_b.sd7", "version": 3},
            "contentChanges": [{"text": FIXED}, {"text": BROKEN}]}}),
    frame({"jsonrpc": "2.0", "id": 8, "method": "shutdown"}),
    frame({"jsonrpc": "2.0", "method": "exit"}),
])
bnotes = [r for r in replies if r.get("method") == "textDocument/publishDiagnostics"
          and r["params"]["uri"] == "file:///tmp/tt_b.sd7"]
expect(bool(bnotes) and any(d["severity"] == 1 for d in bnotes[-1]["params"]["diagnostics"]),
       "last of several contentChanges wins")

print("transcript: %d checks, %d failed" % (passed, len(fails)))
sys.exit(1 if fails else 0)
```

- [ ] **Step 2: Run it and confirm the lifecycle assertions pass**

Run: `python3 tests/transcript.py`
Expected: 14 `ok` lines then `transcript: 21 checks, 0 failed`. Failures seen while
writing this plan, for orientation: a `" <& x < "` typo emitted
`{"capabilities":FALSE}` (comparison instead of append), and a missing separator comma
in `raw()` produced `}{` between objects.

- [ ] **Step 3: Guard the serialisation trap from spec §3.2**

Run: `grep -n 'addStr(w, str(' src/*.sd7`
Expected: no output. `str()` on a `jsonValue` is the `literal()` path that emits
`\8364;` for `€`; strings must reach `addStr` as Seed7 strings, so the combination
above must never appear. Numbers go through `intAt`, which checks
`category(v) = JSON_NUMBER` before `integer(str(v))`.

Run: `grep -rn 'progs.s7i' src/*.sd7`
Expected: `src/analysis.sd7` only — invariant 1 of the spec's §2.

- [ ] **Step 4: Run the whole suite**

Run: `make test`
Expected: 8 suites, 70 checks, 0 failed.

- [ ] **Step 4: Write the client launch snippets into `README.md`**

```markdown
# seed7-lsp-server

An LSP server for the [SEED7](https://seed7.net) language, written in Seed7.
Requires a working `s7` interpreter and its standard library.

    make test          # 8 suites, 70 checks, no editor needed
    make server        # speak LSP on stdin/stdout

Run `s7 -q -l src src/main.sd7` as the server command.

* VS Code: `"seed7-lsp.runtime": "s7"`, `"seed7-lsp.args": ["-q", "-l", "<repo>/src", "<repo>/src/main.sd7"]`
* Emacs: `(use-package lsp-mode :config (add-to-list 'lsp-language-id-configuration '(seed7-mode . "seed7")))`
  then `(lsp-register-client (make-lsp-client :new-process (lsp--start-server '("s7" "-q" "-l" "src" "src/main.sd7")) :major-modes seed7-mode :server-id 'seed7-lsp))`
* Neovim: `require("lspconfig").server_config_for_language("seed7", "seeds")` — or
  simply `vim.lsp.start({ name = "seed7-lsp", cmd = { "s7", "-q", "-l", "src", "src/main.sd7" }, root_dir = vim.fs.dirname(...) })`
  in an autocmd for `FileType seed7`.

Implements: base protocol, lifecycle, full text sync, interpreter diagnostics.
Not yet: definition, hover, completion, signatureHelp, symbols, folding,
semantic tokens, references, rename, workspace symbols (see the spec's milestones M3-M6).
```

- [ ] **Step 5: Commit**

```bash
git add tests/transcript.py README.md
git commit -m "Add end-to-end LSP transcript test and client launch notes"
```

---

## Plan self-review notes for the executor

Read before starting; each is a Seed7 rule that cost a debugging cycle here.

- `const proc:` bodies still end with `end func;`.
- A `local` variable cannot be initialised from a parameter of the same function:
  `var integer: m is n;` fails; write `var integer: m is 0;` then `m := n;`.
- `key`, `len` and `line` are taken by the language/library — `key(...)` as a
  parameter name and `var integer: len` both fail to parse. `field` and `width` /
  `lineIdx` are the names used here.
- At statement level `<&` appends to the *output*, so `buf <& x;` is not an
  assignment. Use `&:=`. Inside expressions `x <& y` is fine (that is how
  `writeln("a=" <& 1)` works).
- String literals are `"..."` only. `''` is not a quoting style, `\9;` is a tab,
  and there is no `\t`. Integer→hex text is `n radix 16 lpad0 2`.
- `SIZE_ERROR` does not exist. The catchable set is `MEMORY_ERROR`,
  `ASSERTION_ERROR`, `NUMERIC_ERROR`, `OVERFLOW_ERROR`, `RANGE_ERROR`,
  `INDEX_ERROR`, `FILE_ERROR`, `DATABASE_ERROR`, `GRAPHIC_ERROR`,
  `ILLEGAL_ACTION`, `CREATE_ERROR`, `DESTROY_ERROR`, `COPY_ERROR`, `IN_ERROR`
  (`seed7_05.s7i:277-291`).
- A declared `hash` type is built with `const type: h is hash [k] v;` and emptied
  with `h.EMPTY_HASH`; removal is the proc `excl(h, key)`, not `h EXCL key`.
- `include` resolution for our own modules uses `s7 -l src`, so every test and the
  server itself is launched with `-l src`.
- `s7` prints analysis errors on stderr and **exits 0**; never judge a run by its
  status code.

## Out of scope for this plan

Everything below is in the spec but deliberately not in this plan; carry each into the
next plan rather than dropping it.

- Spec §5/§8 M3-M6: definition, hover, completion, signatureHelp, documentSymbol
  (M3/M4); scanner-backed folding/selectionRange/semanticTokens (M5, the `scan.sd7`
  module does not exist yet); references/rename/workspace symbols (M6, needs the
  occurrence index the reflection API cannot provide).
- Spec §6 configuration: `workspace/configuration` for `seed7.interpreterPath`,
  `seed7.libraryPaths`, `seed7.maxDiagnostics`, `seed7.logLevel`. This plan hard-codes
  `libraryDirs := "."` and `MAX_DIAGNOSTICS = 100`, and logs to stderr via `note()`
  instead of `window/logMessage`. The server is usable without it; it is not usable
  without diagnostics.
- Spec §6 startup check (one `window/showMessage` when the stdlib is unresolvable) —
  currently an unresolvable stdlib surfaces as an `INCLUDE_FILE_NOT_FOUND` diagnostic
  on every open document, which is visible but noisy.
- Spec §3.3 `utf-8` position negotiation (utf-16 is announced and always correct),
  pull diagnostics (§4 `textDocument/diagnostic`), Windows, and the long-session
  memory measurement in §9.1.
