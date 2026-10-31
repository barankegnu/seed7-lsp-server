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

def split_frames(out):
    """Return (frames, junk) where junk counts stray non-frame bytes on stdout.

    A server that dies mid-request writes its runtime error text to stdout, which
    corrupts the JSON-RPC channel; that must be visible, not a KeyError here."""
    frames, junk, pos = [], 0, 0
    while True:
        i = out.find(b"Content-Length: ", pos)
        if i < 0:
            if out[pos:].strip():
                junk += 1
            break
        if out[pos:i].strip():
            junk += 1
        j = out.find(b"\r\n\r\n", i)
        if j < 0:
            junk += 1
            break
        n = int(out[i + 16:j].decode())
        body = out[j + 4:j + 4 + n]
        if len(body) != n:
            junk += 1
            break
        frames.append(json.loads(body.decode("utf-8")))
        pos = j + 4 + n
    return frames, junk


def run(frames):
    p = subprocess.Popen(CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, cwd="/tmp")
    out, err = p.communicate(b"".join(frames), timeout=90)
    replies, junk = split_frames(out)
    return replies, p.returncode, err.decode("utf-8", "replace"), junk


def expect(cond, label):
    global passed
    print(("ok   " if cond else "FAIL ") + label)
    if cond:
        passed += 1
    else:
        fails.append(label)


# Frame builders, shared by every check that needs more than one request. Written once here
# because Tasks 10-12 add foldingRange/selectionRange/semanticTokens checks on top of them.
def req(rid, method, params):
    return {"jsonrpc": "2.0", "id": rid, "method": method, "params": params}


def notify(method, params):
    return {"jsonrpc": "2.0", "method": method, "params": params}


def pos(uri, line, character):
    return {"textDocument": {"uri": uri},
            "position": {"line": line, "character": character}}


def td(uri, version=None):
    """The `textDocument` member a notification or DocumentSymbol request carries."""
    doc = {"uri": uri}
    if version is not None:
        doc["version"] = version
    return {"textDocument": doc}


def initialize(rid=1):
    return req(rid, "initialize", {"capabilities": {}, "processId": None, "rootUri": None})


def opened(uri, text, version=1):
    return notify("textDocument/didOpen",
                  {"textDocument": {"uri": uri, "languageId": "seed7",
                                    "version": version, "text": text}})


def changed(uri, text, version):
    return notify("textDocument/didChange",
                  dict(td(uri, version), contentChanges=[{"text": text}]))


def changed_no_version(uri, text):
    """A didChange whose `textDocument` has no `version` member at all.

    LSP 3.18 makes `version` REQUIRED on VersionedTextDocumentIdentifier (the type didChange
    names), so this is a malformed frame. The server answers it rather than rejecting it, and
    `intAt` invents a default for the missing number -- which is why the analysis cache may not
    key its invalidation on that number."""
    return notify("textDocument/didChange",
                  dict(td(uri), contentChanges=[{"text": text}]))


def closed(uri):
    return notify("textDocument/didClose", td(uri))


def shutdown(rid):
    return req(rid, "shutdown", {})


def exit_():
    return notify("exit", {})


def analyses(err):
    """How many analyses the server logged. `note()` writes to stderr, so the log line in
    the miss path is the observable and no counter variable enters the product. Counted by
    its full prefix: this number is the exit criterion, and a uri or a later phrasing is free
    to contain the shorter "analyzed "."""
    return err.count("seed7-lsp: analyzed ")

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
replies, code, err, junk = run([frame(m) for m in msgs])
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
hov = by_id.get(2, {}).get("result") or {}
expect("writeln" in hov.get("contents", {}).get("value", ""),
       "hover over writeln reports its signature, got %r" % hov)
expect(hov.get("range") == {"start": {"line": 3, "character": 4},
                            "end": {"line": 3, "character": 11}},
       "hover range is the token, 0-based and end-exclusive (%r)" % hov.get("range"))
expect(by_id.get(2, {}).get("error") is None, "hover is answered, not -32601")
expect("result" in by_id.get(3, {}) and by_id[3]["result"] is None, "shutdown answers null")
expect(code == 0, "exit after shutdown is status 0, got %d" % code)

replies, code, err, junk = run([frame({"jsonrpc": "2.0", "id": 9, "method": "textDocument/hover",
                            "params": {"textDocument": {"uri": "file:///tmp/x.sd7"},
                                       "position": {"line": 0, "character": 0}}}),
                     frame({"jsonrpc": "2.0", "method": "exit"})])
expect(replies and replies[0]["error"]["code"] == -32002, "request before initialize -> -32002")
expect(code == 1, "exit without shutdown is status 1, got %d" % code)

# --- a frame with no Content-Length has no knowable end: report it ---
replies, code, err, junk = run([
    frame(msgs[0]),
    b"Content-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n",
    frame({"jsonrpc": "2.0", "id": 9, "method": "shutdown"}),
    frame({"jsonrpc": "2.0", "method": "exit"}),
])
expect("without Content-Length" in err, "frame lacking Content-Length is reported")

# --- spec 3.4: after shutdown, later requests are refused as InvalidRequest ---
replies, code, err, junk = run([
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
replies, code, err, junk = run([
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

# --- M3: documentSymbol answers from the analyzer's own global objects ---
with open(os.path.join(ROOT, "tests/programs/symbols.sd7")) as f:
    SYMS = f.read()
replies, code, err, junk = run([
    frame(msgs[0]), frame(msgs[1]),
    frame({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params":
           {"textDocument": {"uri": "file:///tmp/tt_syms.sd7", "languageId": "seed7",
                             "version": 1, "text": SYMS}}}),
    frame({"jsonrpc": "2.0", "id": 20, "method": "textDocument/documentSymbol", "params":
           {"textDocument": {"uri": "file:///tmp/tt_syms.sd7"}}}),
    frame({"jsonrpc": "2.0", "id": 21, "method": "textDocument/documentSymbol", "params":
           {"textDocument": {"uri": "file:///tmp/tt_not_open.sd7"}}}),
    frame({"jsonrpc": "2.0", "id": 22, "method": "shutdown"}),
    frame({"jsonrpc": "2.0", "method": "exit"}),
])
by_id = {r.get("id"): r for r in replies if "id" in r}
syms = by_id.get(20, {}).get("result", [])
expect(isinstance(syms, list) and bool(syms), "documentSymbol returns a non-empty array")
expect(any(s.get("name") == "Widget" and s.get("kind") == 5 for s in syms or []),
       "documentSymbol lists the fixture's struct as a Class")
expect(any(s.get("name") == "reportWidget" and
           s["selectionRange"]["start"]["line"] == s["range"]["start"]["line"] == 18
           for s in syms or []), "documentSymbol reports the 0-based declaration line")
expect(by_id.get(21, {}).get("result") is None, "documentSymbol for an unopened uri is null")

# --- M3: definition, both to the same buffer and into the installed library ---
replies, code, err, junk = run([
    frame(msgs[0]), frame(msgs[1]),
    frame({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params":
           {"textDocument": {"uri": "file:///tmp/tt_syms.sd7", "languageId": "seed7",
                             "version": 1, "text": SYMS}}}),
    frame({"jsonrpc": "2.0", "id": 30, "method": "textDocument/definition", "params":
           {"textDocument": {"uri": "file:///tmp/tt_syms.sd7"},
            "position": {"line": 30, "character": 8}}}),
    # line 31 (0-based) is `    writeln(totalSize(prototype, 2));`; character 6 is
    # inside "writeln", which the left-of-character rule resolves to the name.
    frame({"jsonrpc": "2.0", "id": 31, "method": "textDocument/definition", "params":
           {"textDocument": {"uri": "file:///tmp/tt_syms.sd7"},
            "position": {"line": 31, "character": 6}}}),
    frame({"jsonrpc": "2.0", "id": 32, "method": "textDocument/definition", "params":
           {"textDocument": {"uri": "file:///tmp/tt_syms.sd7"},
            "position": {"line": 0, "character": 0}}}),
    frame({"jsonrpc": "2.0", "id": 33, "method": "shutdown"}),
    frame({"jsonrpc": "2.0", "method": "exit"}),
])
by_id = {r.get("id"): r for r in replies if "id" in r}
own = by_id.get(30, {}).get("result", [])
lib = by_id.get(31, {}).get("result", [])
expect(isinstance(own, list) and any(
       l["uri"] == "file:///tmp/tt_syms.sd7" and l["range"]["start"]["line"] == 18
       for l in own or []),
       "definition jumps to the declaration in the same buffer (%s)" % own[:1])
expect(isinstance(lib, list) and bool(lib) and
       all(l["uri"].startswith("file:///") and l["uri"].endswith(".s7i") for l in lib),
       "definition into the library returns .s7i locations, got %d" % len(lib or []))
expect(by_id.get(32, {}).get("result") is None, "definition on punctuation is null")

# --- Task 1: the analysed buffer's own overload of a stdlib name ranks first ---
OWN_RANK = '$ include "seed7_05.s7i";\nconst type: Widget is new struct\n'
OWN_RANK += '  var integer: size is 0;\nend struct;\n'
OWN_RANK += 'const func integer: length (in Widget: w) is func\n  result\n'
OWN_RANK += '    var integer: out is 0;\n  begin\n    out := w.size;\n  end func;\n'
OWN_RANK += 'const proc: main is func\n  begin\n'
OWN_RANK += '    writeln(length(Widget.value));\n  end func;\n'
replies, code, err, junk = run([frame(m) for m in [
    initialize(),
    opened("file:///tmp/tt_ownrank.sd7", OWN_RANK),
    req(61, "textDocument/definition", pos("file:///tmp/tt_ownrank.sd7", 12, 18)),
    # Column 18 sits just past `length' in `writeln(length(Widget.value));', so the
    # left-of-character rule resolves hover to the callee. Column 19 is one further in, inside
    # the call's parens, which is where callContextOf has to be to name a callee at all.
    req(63, "textDocument/hover", pos("file:///tmp/tt_ownrank.sd7", 12, 18)),
    req(64, "textDocument/signatureHelp", pos("file:///tmp/tt_ownrank.sd7", 12, 19)),
    shutdown(62), exit_()]])
by_id = {r.get("id"): r for r in replies if "id" in r}
defs = by_id.get(61, {}).get("result") or []
expect(isinstance(defs, list) and bool(defs) and
       defs[0].get("uri") == "file:///tmp/tt_ownrank.sd7",
       "definition on an own overload of a stdlib name lists the buffer first")
# The two strings below were read off a run, not composed. The fixture declares
# `const func integer: length (in Widget: w)' and reflection prints it without the `in'. The
# stdlib's `length' overloads follow it, headed by
# `const func integer: length (string: stri)'. Which signature comes FIRST is the whole point,
# so hover is pinned on the first line inside its fence and signatureHelp on signatures[0].
hv_rank = (by_id.get(63, {}).get("result") or {}).get("contents", {}).get("value", "")
hv_rank_lines = hv_rank.split("\n")
expect(len(hv_rank_lines) > 1 and
       hv_rank_lines[1] == "const func integer: length (Widget: w)",
       "hover lists the buffer's own overload of a stdlib name first (%r)" % hv_rank_lines[:2])
sig_rank = (by_id.get(64, {}).get("result") or {}).get("signatures") or []
expect(isinstance(sig_rank, list) and bool(sig_rank) and
       sig_rank[0].get("label") == "const func integer: length (Widget: w)",
       "signatureHelp lists the buffer's own overload first (%r)" %
       [s.get("label") for s in sig_rank[:2]])
expect(junk == 0, "the own-rank session put only frames on stdout")

# --- M5: references, and the log line an unproved binding owes the client ---
# The cursor is on the struct field declaration `var integer: pix is 0;', whose name no
# declaration source reaches (spec 11.10), so the binding is unproved: the answer is every
# `pix' token in the file AND a window/logMessage that arrives BEFORE the answer. The
# positions come from the fixture text, as everywhere else here, so editing symbols.sd7
# cannot silently move them.
REF_LINES = SYMS.split("\n")
REF_DECL = REF_LINES.index("    var integer: pix is 0;")
REF_USE = REF_LINES.index("    total := w.pix * factor;")
REF_CHAR = REF_LINES[REF_DECL].index("pix") + 1        # inside the three letters
REF_EXPECT = [(REF_DECL, REF_LINES[REF_DECL].index("pix"),
               REF_LINES[REF_DECL].index("pix") + 3),
              (REF_USE, REF_LINES[REF_USE].index("pix"),
               REF_LINES[REF_USE].index("pix") + 3)]
REF_MSGS = [
    msgs[0], msgs[1],
    notify("textDocument/didOpen",
           {"textDocument": {"uri": "file:///tmp/tt_syms.sd7", "languageId": "seed7",
                             "version": 1, "text": SYMS}}),
    # line 31 is `    writeln(totalSize(prototype, 2));`; character 16 is inside
    # "totalSize", so hover must report the func declared in this buffer.
    req(40, "textDocument/hover", pos("file:///tmp/tt_syms.sd7", 31, 16)),
    req(41, "textDocument/references", pos("file:///tmp/tt_syms.sd7", REF_DECL, REF_CHAR)),
    # The dispatcher's unknown-method branch needs a method that stays unimplemented for the
    # whole of M5: typeDefinition is not on this milestone's list, so this pin cannot go
    # falsely red two tasks from now. (rename/prepareRename are Tasks 8-9 -- do NOT pin those.)
    req(43, "textDocument/typeDefinition", pos("file:///tmp/tt_syms.sd7", REF_DECL, REF_CHAR)),
    # The other half of the same rule: an unknown NOTIFICATION is answered with silence.
    notify("$/unknownThing", {}),
    shutdown(42),
    exit_(),
]
replies, code, err, junk = run([frame(m) for m in REF_MSGS])
by_id = {r.get("id"): r for r in replies if "id" in r}
hv = (by_id.get(40, {}).get("result") or {}).get("contents", {}).get("value", "")
expect("func integer: totalSize" in hv, "hover on a buffer symbol shows its signature (%r)" % hv)
expect(hv.startswith("```seed7"), "hover body is a seed7 fence (%r)" % hv[:12])
refs = by_id.get(41, {}).get("result")
expect(isinstance(refs, list) and
       [(l["range"]["start"]["line"], l["range"]["start"]["character"],
         l["range"]["end"]["character"]) for l in refs] == REF_EXPECT and
       all(l["uri"] == "file:///tmp/tt_syms.sd7" for l in refs),
       "references answers this file's occurrences with exact columns (%s)" % refs)
log_at = next((i for i, r in enumerate(replies)
               if r.get("method") == "window/logMessage" and
               r.get("params", {}).get("type") == 3 and
               "pix" in r["params"].get("message", "")), None)
ans_at = next((i for i, r in enumerate(replies) if r.get("id") == 41), None)
expect(log_at is not None and ans_at is not None and log_at < ans_at,
       "an unproved binding logs to the client before the answer (%s, %s)" % (log_at, ans_at))
expect(junk == 0, "the references run put only frames on stdout (junk=%d)" % junk)
# The capability that lets a client ask at all. Every other M5 capability is pinned somewhere
# (renameProvider, foldingRangeProvider, selectionRangeProvider, semanticTokensProvider, and
# workspaceSymbolProvider ABSENT) and this one was the only M5 name with no wire check.
expect(replies[0].get("result", {}).get("capabilities", {}).get("referencesProvider") is True,
       "initialize advertises referencesProvider (%r)"
       % replies[0].get("result", {}).get("capabilities", {}).get("referencesProvider"))
expect(by_id.get(43, {}).get("error", {}).get("code") == -32601,
       "a method not implemented in M5 is -32601, got %r" % by_id.get(43, {}))
# An answer to a notification would be a frame carrying result or error, so the number of
# answers must equal the number of requests sent. Counted from the messages, so adding a
# request to the run cannot silently move the number -- and one answer too many is the red.
REQUESTS = len([m for m in REF_MSGS if "id" in m])
answered = [r for r in replies if "result" in r or "error" in r]
expect(len(answered) == REQUESTS,
       "an unknown notification gets no reply (%d requests, %d answers)"
       % (REQUESTS, len(answered)))

# --- M5 Task 8: prepareRename, and the first capability the server READS ----------
# The symbol is reportWidget's `counter' parameter: buffer-declared, resolved, its routine owns
# its region, so NOTHING on the refusal list applies except the capability the client declares.
PR_LINES = SYMS.split("\n")
PR_USE = PR_LINES.index("    counter +:= 1;")
PR_CHAR = PR_LINES[PR_USE].index("counter") + 1          # inside the seven letters
PR_EXPECT = {"range": {"start": {"line": PR_USE, "character": PR_LINES[PR_USE].index("counter")},
                       "end": {"line": PR_USE,
                               "character": PR_LINES[PR_USE].index("counter") + 7}},
             "placeholder": "counter"}
PR_LIB = PR_LINES.index("    writeln(label);")
PR_LIB_CHAR = PR_LINES[PR_LIB].index("writeln") + 1
PR_KW = PR_LINES.index("  begin")     # the first `begin' in the file, main's is further down
PR_KW_CHAR = 4


def answered_null(by_id, rid):
    """True when the frame for `rid' carries `result: null'.

    A refusal must be null, NEVER an error (spec 6): an editor greys the menu item out on null and
    shows the user a failure on an error frame. `"result" not in frame' is what an error frame
    looks like, so the key has to be PRESENT -- checking the value alone would pass a -32603."""
    reply = by_id.get(rid, {})
    return "result" in reply and reply["result"] is None and "error" not in reply


def one_answer_per_request(messages, replies, label):
    """Every request of `messages' answered exactly once, and nothing answers a notification.

    The idiom of the references run (REQUESTS) and the rename run (REQUESTS9), applied to the runs
    added later, which had no such pin: an answer to `initialized' or `textDocument/didOpen' in
    one of them would pass every other check in the block unnoticed."""
    sent = len([m for m in messages if "id" in m])
    got = len([r for r in replies if "result" in r or "error" in r])
    expect(got == sent, "%s answers every request and nothing else (%d requests, %d answers)"
           % (label, sent, got))


def pr_msgs(init):
    """One framed session: initialize, open the fixture, ask prepareRename four times."""
    return [frame(m) for m in [init, msgs[1], opened("file:///tmp/tt_syms.sd7", SYMS),
            req(60, "textDocument/prepareRename", pos("file:///tmp/tt_syms.sd7",
                                                      PR_USE, PR_CHAR)),
            req(61, "textDocument/prepareRename", pos("file:///tmp/tt_syms.sd7",
                                                      PR_LIB, PR_LIB_CHAR)),
            req(62, "textDocument/prepareRename", pos("file:///tmp/tt_syms.sd7",
                                                      PR_KW, PR_KW_CHAR)),
            req(63, "textDocument/prepareRename", pos("file:///tmp/tt_not_open.sd7", 0, 0)),
            shutdown(64), exit_()]]


# A client that never declared workspace.applyEdit: the promise of a WorkspaceEdit is one this
# server must not make, so the answer is null AND the reason goes to the client as a
# window/logMessage before it. msgs[0] is that client -- its params have no `workspace' at all.
replies, code, err, junk = run(pr_msgs(msgs[0]))
by_id = {r.get("id"): r for r in replies if "id" in r}
init_caps = replies[0].get("result", {}).get("capabilities", {})
expect(init_caps.get("renameProvider") == {"prepareProvider": True},
       "initialize advertises renameProvider as {\"prepareProvider\": true} (%r)"
       % init_caps.get("renameProvider"))
expect("workspaceSymbolProvider" not in init_caps,
       "workspace/symbol stays unadvertised (%s)"
       % [k for k in init_caps if k.startswith("workspace")])
expect(answered_null(by_id, 60),
       "no workspace.applyEdit -> prepareRename answers null (%r)" % by_id.get(60, {}))
expect(all(answered_null(by_id, i) for i in (61, 62, 63)),
       "and the library, keyword and unopened-uri cursors also answer null (%s)"
       % [i for i in (61, 62, 63) if not answered_null(by_id, i)])
log_at = next((i for i, r in enumerate(replies) if r.get("method") == "window/logMessage"
               and "applyEdit" in r.get("params", {}).get("message", "")), None)
ans_at = next((i for i, r in enumerate(replies) if r.get("id") == 60), None)
expect(log_at is not None and ans_at is not None and log_at < ans_at,
       "the refusal is explained to the client before the null (%s, %s)" % (log_at, ans_at))
expect("prepareRename" in err and "applyEdit" in err,
       "and the same line is mirrored to stderr")
expect(junk == 0, "the refusal run put only frames on stdout (junk=%d)" % junk)

# The same session with the capability declared: the accepted symbol, and the two refusals that
# are about the SYMBOL rather than the client.
replies, code, err, junk = run(pr_msgs(req(1, "initialize",
                                           {"capabilities": {}, "processId": None,
                                            "rootUri": "file:///tmp",
                                            "workspace": {"applyEdit": True}})))
by_id = {r.get("id"): r for r in replies if "id" in r}
expect(by_id.get(60, {}).get("result") == PR_EXPECT,
       "workspace.applyEdit -> prepareRename answers the token's range and name (%r)"
       % by_id.get(60, {}).get("result"))
expect(answered_null(by_id, 61),
       "a library symbol still refuses, one file is the milestone (%r)" % by_id.get(61, {}))
expect("writeln is declared outside this buffer" in err,
       "and says so on the log")
expect(answered_null(by_id, 62), "a keyword refuses as syntax, not as an unbound name")
expect("begin is a Seed7 keyword" in err, "and says which it is")
expect(answered_null(by_id, 63), "prepareRename for an unopened uri is null, not an error")
# 60 is accepted and 63 never reaches the feature, so only the library and the keyword refusals
# owe the client a sentence. An accept that logs is the user reading a log they did not ask for.
expect(len([r for r in replies if r.get("method") == "window/logMessage"]) == 2,
       "only the refusals speak (%d log frames)"
       % len([r for r in replies if r.get("method") == "window/logMessage"]))
expect(junk == 0, "the accepted run put only frames on stdout (junk=%d)" % junk)

# A client that declares applyEdit as something that is not a boolean has not declared it.
replies, code, err, junk = run(pr_msgs(req(1, "initialize",
                                           {"capabilities": {}, "processId": None,
                                            "rootUri": None,
                                            "workspace": {"applyEdit": "yes"}})))
by_id = {r.get("id"): r for r in replies if "id" in r}
expect(answered_null(by_id, 60),
       "a non-boolean applyEdit leaves the flag down (%r)" % by_id.get(60, {}))
# --- M5 Task 9: rename, the one method here that WRITES to the user's file ----------
# The symbol is reportWidget's `counter' parameter: one use inside the body and its declaration
# on the header line -- which IS the line its body region opens on, because `is func' sits on it,
# so both edits come from inScope and one document carries them. The header-above-the-region case,
# where inScope's window does not hold the declaration, is pinned in tests/features_test.sd7.
RN_URI = "file:///tmp/tt_syms.sd7"
RN_HEAD = PR_LINES.index("const proc: reportWidget (in string: label, "
                         "inout integer: counter) is func")
RN_USE = PR_LINES.index("    counter +:= 1;")
RN_CHAR = PR_LINES[RN_USE].index("counter") + 1          # inside the seven letters


def rn_edit(line, new):
    col = PR_LINES[line].index("counter")
    return {"range": {"start": {"line": line, "character": col},
                      "end": {"line": line, "character": col + 7}},
            "newText": new}


RN_EXPECT = {"changes": {RN_URI: [rn_edit(RN_HEAD, "count2"), rn_edit(RN_USE, "count2")]}}


def rn_msgs(init):
    """The messages of one framed session: the accept, the two -32602 rejections, a refusal, and
    the two dispatcher rules that must survive a new branch in the chain. Kept as messages, not
    frames, so the checks can count the requests in the run they came from."""
    return [init, msgs[1], opened(RN_URI, SYMS),
            req(70, "textDocument/rename",
                dict(pos(RN_URI, RN_USE, RN_CHAR), newName="count2")),
            req(71, "textDocument/rename",
                dict(pos(RN_URI, RN_USE, RN_CHAR), newName="1bad")),
            req(72, "textDocument/rename",
                dict(pos(RN_URI, RN_USE, RN_CHAR), newName="label")),
            req(73, "textDocument/rename",
                dict(pos(RN_URI, PR_LINES.index("    total := w.pix * factor;"),
                     PR_LINES[PR_LINES.index("    total := w.pix * factor;")].index("pix") + 1),
                     newName="pixels")),
            req(74, "textDocument/rename", pos(RN_URI, RN_USE, RN_CHAR)),
            req(75, "textDocument/typeDefinition", pos(RN_URI, RN_USE, RN_CHAR)),
            notify("$/unknownThing", {}),
            shutdown(76), exit_()]


APPLY = req(1, "initialize", {"capabilities": {}, "processId": None,
                              "rootUri": "file:///tmp", "workspace": {"applyEdit": True}})
RN_RUN = rn_msgs(APPLY)
replies, code, err, junk = run([frame(m) for m in RN_RUN])
by_id = {r.get("id"): r for r in replies if "id" in r}
edit = by_id.get(70, {}).get("result")
expect(isinstance(edit, dict) and list(edit.get("changes", {})) == [RN_URI],
       "rename edits exactly one document, the requested uri (%r)"
       % (list(edit.get("changes", {})) if isinstance(edit, dict) else edit))
expect(isinstance(edit, dict) and len(edit["changes"].get(RN_URI, [])) == 2,
       "and two TextEdits, one per occurrence in scope (%r)" % edit)
expect(edit == RN_EXPECT, "with the header declaration and the use, at their own columns (%r)" % edit)
expect(all(e["newText"] == "count2" for e in edit.get("changes", {}).get(RN_URI, [])),
       "every edit carries the newName, not the word under the cursor")
expect(by_id.get(70, {}).get("error") is None, "the accepted rename is a result, not an error")
LOGS9 = [r for r in replies if r.get("method") == "window/logMessage"]
expect(len(LOGS9) == 4,
       "one sentence for each rejection and refusal, none for the accept (%d log frames)"
       % len(LOGS9))
expect(not [r for r in LOGS9 if "count2" in r.get("params", {}).get("message", "")],
       "and nothing in the log is about the rename that worked")
# A rejected newName is -32602 InvalidParams, an event a refusal is not.
expect(by_id.get(71, {}).get("error", {}).get("code") == -32602,
       "a name that is not an identifier is -32602, not null (%r)" % by_id.get(71, {}))
expect("1bad is not a Seed7 identifier" in err,
       "and the rejection is mirrored to stderr")
expect("rename: 1bad is not a Seed7 identifier" in
       " ".join(r.get("params", {}).get("message", "")
                for r in replies if r.get("method") == "window/logMessage"),
       "and reaches the client as a logMessage too")
expect(by_id.get(72, {}).get("error", {}).get("code") == -32602,
       "a name already declared in the symbol's scope is -32602 (%r)" % by_id.get(72, {}))
expect("label is already declared in the scope of counter" in err,
       "and says which scope it collides in")
# A refusal is null, never an error frame: `pix' is a struct field, which binds to no
# declaration this server has.
expect(answered_null(by_id, 73),
       "an unprovable symbol answers null, not an error (%r)" % by_id.get(73, {}))
expect("pix does not bind to one declaration of this file" in err,
       "and the reason is on the log")
# The client-side half of the same rule, which the two lines above do not pin: the sentence has
# to ARRIVE AS A window/logMessage BEFORE the null that grey the menu item out. Counted on the
# frames this run already produced, so no request is added and no request/answer count moves.
PIX_LOG = next((i for i, r in enumerate(replies) if r.get("method") == "window/logMessage"
                and "pix does not bind to one declaration" in
                r.get("params", {}).get("message", "")), None)
PIX_ANS = next((i for i, r in enumerate(replies) if r.get("id") == 73), None)
expect(PIX_LOG is not None and PIX_ANS is not None and PIX_LOG < PIX_ANS,
       "an unresolved rename speaks the reason to the client before its null (%s, %s)"
       % (PIX_LOG, PIX_ANS))
# A request with no newName at all: strAt falls back to the empty string, which is a rejected
# name rather than a crash -- and the frame must still be an answer, not a -32603.
expect(by_id.get(74, {}).get("error", {}).get("code") == -32602,
       "a rename frame with no newName is -32602, not an internal error (%r)" % by_id.get(74, {}))
# The dispatch chain, unchanged around the new branch.
expect(by_id.get(75, {}).get("error", {}).get("code") == -32601,
       "the unknown request beside rename is still -32601 (%r)" % by_id.get(75, {}))
REQUESTS9 = len([m for m in RN_RUN if "id" in m])
answered = [r for r in replies if "result" in r or "error" in r]
expect(len(answered) == REQUESTS9,
       "and the unknown notification is still silent (%d requests, %d answers)"
       % (REQUESTS9, len(answered)))
expect(junk == 0, "the rename run put only frames on stdout (junk=%d)" % junk)
expect(replies[0].get("result", {}).get("capabilities", {}).get("renameProvider") ==
       {"prepareProvider": True},
       "renameProvider is still {\"prepareProvider\":true} with the handler wired (%r)"
       % replies[0].get("result", {}).get("capabilities", {}).get("renameProvider"))

# Without workspace.applyEdit the same request is a refusal, and a refusal is null: the client
# that cannot apply an edit must not be handed an error it would show as a failed rename.
replies, code, err, junk = run([frame(m) for m in rn_msgs(msgs[0])])
by_id = {r.get("id"): r for r in replies if "id" in r}
expect(answered_null(by_id, 70),
       "no applyEdit -> rename answers null (%r)" % by_id.get(70, {}))
expect("workspace.applyEdit" in err, "and says the capability it did not declare")
# NOT COVERED, written down so a reader does not count the two lines above as covering it: that
# sentence is checked on STDERR only. prepareRename's capability refusal is also pinned as a
# CLIENT frame ("the refusal is explained to the client before the null") and rename's
# unresolved-binding refusal is too ("an unresolved rename speaks the reason to the client before
# its null"), but nothing here requires rename's CAPABILITY refusal to arrive as a
# window/logMessage. The LOGS9 count above cannot see it: that run GRANTS the capability, so this
# refusal never happens there. Left unpinned on purpose -- the client-frame ordering it would need
# is the machinery the library-buffer block repairs further down, and standing it up here would
# mean new request traffic for one more sentence.

# --- M5 Task 9 R47: a capped document refuses instead of half-editing ----------------
# 2 002 uses of one global plus its declaration: occurrencesOf stops at its 2 001st record, so
# the cursor on the FIRST use IS in the list and a range exists -- the gap that made prepareRename
# accept a document rename could only edit partially. Both methods must refuse the same cursor.
CAP_TEXT = ('$ include "seed7_05.s7i";\n  include "console.s7i";\n'
            'var integer: count is 0;\n\n'
            'const proc: main is func\n  begin\n' +
            '    count := 1;\n' * 2001 + '  end func;\n')
CAP_URI = "file:///tmp/tt_cap_wire.sd7"
CAP_CURSOR = CAP_TEXT.split("\n").index("    count := 1;")
replies, code, err, junk = run([frame(m) for m in [
    APPLY, msgs[1], opened(CAP_URI, CAP_TEXT),
    req(80, "textDocument/rename", dict(pos(CAP_URI, CAP_CURSOR, 5), newName="total")),
    req(81, "textDocument/prepareRename", pos(CAP_URI, CAP_CURSOR, 5)),
    req(82, "textDocument/rename", dict(pos(CAP_URI, CAP_CURSOR, 5), newName="1bad")),
    shutdown(83), exit_()]])
by_id = {r.get("id"): r for r in replies if "id" in r}
expect(answered_null(by_id, 80),
       "rename refuses a capped document whose cursor IS listed (%r)" % by_id.get(80, {}))
expect(answered_null(by_id, 81),
       "and prepareRename refuses the very same cursor (%r)" % by_id.get(81, {}))
expect("count has more occurrences than this server lists" in err,
       "both under the sentence that says an edit would be incomplete (%r)" % err[-200:])
expect("so a rename could not rewrite all of them" in err and
       "the token under the cursor is not among" not in err,
       "and not the other truncation sentence, which speaks about the cursor")
# The order still holds at the cap: a rejected name costs -32602 even where the document would
# be refused anyway, because the name is checked before anything is scanned.
expect(by_id.get(82, {}).get("error", {}).get("code") == -32602,
       "a bad name is still -32602 on a capped document (%r)" % by_id.get(82, {}))
expect(junk == 0, "the capped run put only frames on stdout (junk=%d)" % junk)

# --- M5 Task 9 R51: a declaration line with two name records is refused ------------------
# `const proc: show (in integer: show)' is legal Seed7 (measured: no analysis error, and running
# the file prints 3) and reflection reports the routine and its parameter at the SAME line1, so
# the line the declaration lives on holds two candidates and a write that finds the declaration by
# line cannot prove which token to edit. Both methods must refuse the identical cursor: a rename
# measured before the arm rewrote the ROUTINE's name and its body use while `show(3);' kept the
# old one. `samples' is the control in the same document -- one record on its parameter's
# declaration line, so it is still offered.
AMB_TEXT = ('$ include "seed7_05.s7i";\n'
            '  include "console.s7i";\n'
            '\n'
            'const proc: show (in integer: show) is func\n'
            '  begin\n'
            '    writeln(show);\n'
            '  end func;\n'
            '\n'
            'const proc: samples (in integer: total) is func\n'
            '  begin\n'
            '    writeln(total);\n'
            '  end func;\n'
            '\n'
            'const proc: main is func\n'
            '  begin\n'
            '    show(3);\n'
            '    samples(4);\n'
            '  end func;\n')
AMB_URI = "file:///tmp/tt_ambig_wire.sd7"
AMB_LINES = AMB_TEXT.split("\n")
AMB_HEAD = AMB_LINES.index("const proc: show (in integer: show) is func")
# The SECOND `show' on that line is the parameter; +1 sits inside the token, the way PR_CHAR does.
AMB_HEAD_TEXT = AMB_LINES[AMB_HEAD]
AMB_PARAM = AMB_HEAD_TEXT.index("show", AMB_HEAD_TEXT.index("show") + 1) + 1
AMB_CTRL = AMB_LINES.index("const proc: samples (in integer: total) is func")
AMB_CTRL_TEXT = AMB_LINES[AMB_CTRL]
AMB_CTRL_CHAR = AMB_CTRL_TEXT.index("total") + 1
replies, code, err, junk = run([frame(m) for m in [
    APPLY, msgs[1], opened(AMB_URI, AMB_TEXT),
    req(90, "textDocument/prepareRename", pos(AMB_URI, AMB_HEAD, AMB_PARAM)),
    req(91, "textDocument/rename", dict(pos(AMB_URI, AMB_HEAD, AMB_PARAM), newName="amount")),
    req(92, "textDocument/prepareRename", pos(AMB_URI, AMB_CTRL, AMB_CTRL_CHAR)),
    shutdown(93), exit_()]])
by_id = {r.get("id"): r for r in replies if "id" in r}
expect(answered_null(by_id, 90),
       "prepareRename refuses a cursor whose declaration line holds two records (%r)"
       % by_id.get(90, {}))
expect(answered_null(by_id, 91),
       "and rename refuses the identical cursor, so nothing is half-rewritten (%r)"
       % by_id.get(91, {}))
expect("show shares its declaration line with another record of the same name" in err,
       "and the refusal says what it counted (%r)" % err[-260:])
expect("could rewrite a record the cursor did not name" in err,
       "in the sentence that names the corruption it prevents -- and no shape the file need not"
       " contain")
expect(by_id.get(92, {}).get("result") ==
       {"range": {"start": {"line": AMB_CTRL,
                           "character": AMB_CTRL_TEXT.index("total")},
                  "end": {"line": AMB_CTRL,
                          "character": AMB_CTRL_TEXT.index("total") + 5}},
        "placeholder": "total"},
       "the unambiguous parameter of the same document is still offered (%r)"
       % by_id.get(92, {}).get("result"))
expect(junk == 0, "the shared-name run put only frames on stdout (junk=%d)" % junk)

# --- M5 Task 10: the columns an LSP client can only be right about in UTF-16 ----------
# Every range pinned above comes from tests/programs/symbols.sd7, which is pure ASCII, so
# `str.index` and a UTF-16 count are the same number there and the wire could not tell an
# lspRangeUnits answer from an lspRange one. This fixture puts three different answers on the
# table for the token the cursor is on: 19 characters, 21 UTF-16 units, 25 bytes. Only the
# middle one is a column a client can act on, and the second document below (13/18/19 units,
# 13/19/21 bytes) is the BMP control that separates the byte rule from the other two.
#
# Expectations are computed from the fixture text with `u16`, never from anything the server
# sent, so a server that answers BYTE columns is red -- measured again in this round with mutant
# M8 (`utf16CharLength := utf8CharLength'): it answers line 8's `tally' at column 29, and the BMP
# control's three at [13, 19, 21]. 29 is not the client's own byte count (25), because the two
# astral characters arrive as FOUR CESU-8 surrogate characters of 3 bytes each -- see the pin
# below. What this run provably CANNOT see: an astral character never reaches doc.text as one
# character, so the server's own character column IS 21 here too, and a regression from col16 to a
# character count stays invisible to every frame this suite can send -- the F1 pin further down
# sends a raw body and shows that the transport, not the column, is what breaks first.
def u16(stri):
    """UTF-16 code units in `stri` -- the count an LSP position calls a `character'.

    Python indexes a str by CHARACTER, so the harness's usual `line.index(word)` is the client's
    column only while the text stays in the BMP. One helper, used by every expectation below."""
    return len(stri.encode("utf-16-le")) // 2


U16_TEXT = ('$ include "seed7_05.s7i";\n'
            '  include "console.s7i";\n'
            '\n'
            'var integer: tally is 0;\n'
            '\n'
            'const proc: main is func\n'
            '  begin\n'
            '    writeln("\u03c0"); tally := 1;\n'
            '    writeln("\U0001F600\U0001F600"); tally := 2;\n'
            '  end func;\n')
U16_URI = "file:///tmp/tt_u16_wire.sd7"
U16_BMP_URI = "file:///tmp/tt_u16_bmp.sd7"
U16_BMP_TEXT = U16_TEXT.replace("\U0001F600\U0001F600", "\u03c0\u03c0")
U16_LINES = U16_TEXT.split("\n")
U16_DECL = U16_LINES.index("var integer: tally is 0;")
U16_NARROW = U16_LINES.index('    writeln("\u03c0"); tally := 1;')
U16_AST = U16_LINES.index('    writeln("\U0001F600\U0001F600"); tally := 2;')
U16_TALLY = "tally"


def u16_col(lines, line):
    """The UTF-16 column at which this fixture's `tally' starts on `line'."""
    return u16(lines[line][:lines[line].index(U16_TALLY)])


U16_COL = {ln: u16_col(U16_LINES, ln) for ln in (U16_DECL, U16_NARROW, U16_AST)}
U16_PREFIX = U16_LINES[U16_AST][:U16_LINES[U16_AST].index(U16_TALLY)]
expect(U16_COL[U16_AST] != len(U16_PREFIX) and
       U16_COL[U16_AST] != len(U16_PREFIX.encode("utf-8")),
       "the astral fixture's UTF-16 column (%d) differs from its character count (%d) and its "
       "byte count (%d) -- if this reddens, the fixture stopped separating the three rules and "
       "the checks below are vacuous" % (U16_COL[U16_AST], len(U16_PREFIX),
                                          len(U16_PREFIX.encode("utf-8"))))


def u16_loc(uri, line, start):
    # The width is a UTF-16 count, not len(): production emits `width16', so an ASCII-only
    # fixture name is the only reason the two agree today.
    return {"uri": uri,
            "range": {"start": {"line": line, "character": start},
                      "end": {"line": line, "character": start + u16(U16_TALLY)}}}


def ref_cols(result):
    """The (line, start, end) triples of a references answer, for the checks that pin them.

    The shape every references check in this file compares against; end LINE is left out because
    a references answer is one line per location -- except a whole-line declaration, which is
    pinned by full JSON equality instead."""
    return [(l["range"]["start"]["line"], l["range"]["start"]["character"],
             l["range"]["end"]["character"]) for l in result]


U16_EXPECT = [u16_loc(U16_URI, ln, U16_COL[ln]) for ln in (U16_DECL, U16_NARROW, U16_AST)]
U16_EDIT = [{"range": loc["range"], "newText": "count2"} for loc in U16_EXPECT]
U16_BMP_LINES = U16_BMP_TEXT.split("\n")
U16_BMP_COL = {ln: u16_col(U16_BMP_LINES, ln) for ln in (U16_DECL, U16_NARROW, U16_AST)}
U16_BMP_EDIT = [{"range": u16_loc(U16_BMP_URI, ln, U16_BMP_COL[ln])["range"],
                 "newText": "count2"} for ln in (U16_DECL, U16_NARROW, U16_AST)]
# The same three columns counted in UTF-8 bytes, for the failure message only.
U16_BMP_BYTES = [len(U16_BMP_LINES[ln][:U16_BMP_LINES[ln].index(U16_TALLY)].encode("utf-8"))
                 for ln in (U16_DECL, U16_NARROW, U16_AST)]
U16_MSGS = [APPLY, msgs[1], opened(U16_URI, U16_TEXT), opened(U16_BMP_URI, U16_BMP_TEXT),
            req(110, "textDocument/references",
                dict(pos(U16_URI, U16_NARROW, U16_COL[U16_NARROW] + 2),
                     context={"includeDeclaration": True})),
            req(111, "textDocument/prepareRename", pos(U16_URI, U16_AST, U16_COL[U16_AST] + 2)),
            req(112, "textDocument/rename",
                dict(pos(U16_URI, U16_AST, U16_COL[U16_AST] + 2), newName="count2")),
            req(113, "textDocument/rename",
                dict(pos(U16_BMP_URI, U16_AST, U16_BMP_COL[U16_AST] + 2), newName="count2")),
            # The brief's third references cursor: a name this buffer does not declare. The
            # library row resolves it, declLine1 stays 0, and the answer is this file's tokens.
            req(115, "textDocument/references",
                  dict(pos(U16_URI, U16_NARROW, 7), context={"includeDeclaration": True})),
            shutdown(114), exit_()]
replies, code, err, junk = run([frame(m) for m in U16_MSGS])
by_id = {r.get("id"): r for r in replies if "id" in r}
u16_refs = by_id.get(110, {}).get("result")
U16_LOGS = [r["params"]["message"] for r in replies
                 if r.get("method") == "window/logMessage"]
expect(isinstance(u16_refs, list) and u16_refs == U16_EXPECT,
       "references on non-ASCII lines answers the UTF-16 locations %s, got %s"
       % ([(l["range"]["start"]["line"], l["range"]["start"]["character"],
           l["range"]["end"]["character"]) for l in U16_EXPECT], u16_refs))
expect(by_id.get(111, {}).get("result") ==
       {"range": u16_loc(U16_URI, U16_AST, U16_COL[U16_AST])["range"],
        "placeholder": U16_TALLY},
       "prepareRename's range is the same UTF-16 span, not the cursor it was asked with (%r)"
       % by_id.get(111, {}).get("result"))
expect((by_id.get(112, {}).get("result") or {}).get("changes", {}).get(U16_URI) == U16_EDIT,
       "rename edits all three occurrences at their UTF-16 columns (%s)"
       % (by_id.get(112, {}).get("result"),))
# A library name: declared outside this buffer, so declLine1 is 0 and no whole-line location is
# added -- the two `writeln' tokens of this file and nothing else, no disclosure log either.
lib_name_refs = by_id.get(115, {}).get("result")
expect(isinstance(lib_name_refs, list) and
       ref_cols(lib_name_refs) == [(U16_NARROW, 4, 11), (U16_AST, 4, 11)],
       "references on a library name lists this file's two tokens (%s)" % lib_name_refs)
expect(len(U16_LOGS) == 0,
       "and a library-resolved name says nothing extra (%s)" % U16_LOGS)
# The BMP control: the same shape with 2-byte characters instead of 4-byte ones. Its column is
# its character count, so this is the arm that rules out "the feature emits byte columns".
expect((by_id.get(113, {}).get("result") or {}).get("changes", {}).get(U16_BMP_URI) ==
       U16_BMP_EDIT,
       "the BMP control document edits at its UTF-16 columns %s, not its byte columns %s (%s)"
       % ([e["range"]["start"]["character"] for e in U16_BMP_EDIT], U16_BMP_BYTES,
          by_id.get(113, {}).get("result")))
expect(junk == 0, "the astral run put only frames on stdout (junk=%d)" % junk)
one_answer_per_request(U16_MSGS, replies, "the astral run")

# --- M5 Task 10 found it, Task 13 fixed it: an escaped astral character arrives as ONE ----
# HISTORY (kept, not rewritten): json.dumps writes one astral character as the escape pair
# \ud83d\ude00 and readJson turned EACH escape into its own char, so doc.text held two code points
# (U+d83d, U+de00) where the client sent one. Task 10 measured four analyzer Errors for the two
# astral characters of U16_TEXT and pinned that as a defect record. rpc.joinSurrogates now folds
# the pair in every string strAt reads, so the analyzer sees the text the client sent and
# publishes nothing. The BMP control stays: without it, "no diagnostics" would also be satisfied
# by a server that never analyses at all.
# Still true after the fix, and the reason the wire cannot grade the UTF-16 rule: a surrogate PAIR
# is 2 chars and 2 units while the joined character is 1 char and 2 units, so a build that counted
# CHARACTERS as columns could not be told apart from one counting units by anything that arrives
# through an escaped body. Measured that way in Task 10: the mutant `utf16CharLength always 1`
# reddened 18 unit checks and ZERO wire ones.
U16_DIAGS = [d for r in replies if r.get("method") == "textDocument/publishDiagnostics"
             for d in r["params"]["diagnostics"] if r["params"]["uri"] == U16_URI]
U16_BMP_DIAGS = [d for r in replies if r.get("method") == "textDocument/publishDiagnostics"
                 for d in r["params"]["diagnostics"] if r["params"]["uri"] == U16_BMP_URI]
expect(len(U16_DIAGS) == 0 and len(U16_BMP_DIAGS) == 0,
       "GAP: an astral character in didOpen text reaches the analyzer as a surrogate pair -- "
       "%d surrogate errors on the astral document, %d diagnostics on the BMP control (%s)"
       % (len([d for d in U16_DIAGS if "surrogate" in d["message"]]),
          len(U16_BMP_DIAGS), [d["message"] for d in U16_DIAGS]))

# --- M5 Task 10 gap 2: a .s7i buffer on the wire -- the read answers, the writes refuse --
# The library buffer is analysed through the synthetic driver, which reads the file back from
# DISK while the client's unsaved edits live only in doc_store (R-F10). So a symbol line the
# edit would use can be the wrong line: spec 12.3 settles it as a split, not a gate -- a READ
# still answers, because over-including with a log line is honest, and a WRITE refuses, because
# a half-applied edit is not. Both halves need the wire, because the frame path is where the
# uri's `.s7i' suffix is decided.
RN_LIB_PATH = "/tmp/seed7_lsp_transcript_rn_lib.s7i"
# The first line is EMPTY because that is the shape of every real library: `find ~/seed7/lib
# -name '*.s7i' -exec sh -c 'head -1 "$1" | wc -c' _ {} \; | sort -u' prints only `1' -- a bare
# newline -- for all 265 of them. A range anchored on a blank line collapses to (0,0)->(0,0) in
# the `lspRangeBytes' clamp, so it must land on the first line that holds a character. Whether a
# client drops a zero-width range or merely draws no squiggle was NOT measured -- no client exists
# in this environment -- so this fixture pins the wire property, not a rendering.
RN_LIB_TEXT = ('\n'
               'const type: Counter is new struct\n'
               '    var integer: amount is 0;\n'
               '  end struct;\n'
               '\n'
               'var integer: ticks is 0;\n'
               '\n'
               'const proc: bump (inout integer: total) is func\n'
               '  begin\n'
               '    ticks +:= 1;\n'
               '    writeln(total);\n'
               '  end func;\n')
with open(RN_LIB_PATH, "w") as f:
    f.write(RN_LIB_TEXT)
RN_LIB_URI = "file://" + RN_LIB_PATH
# The whole sentence the user reads, verbatim as src/lsp_server.sd7's LIB_STALE_MESSAGE spells it.
# The Seed7 unit suite prints ASCII, so it can only compare two words of it; this is the one place
# the tail is pinned.
LIB_STALE = ("unsaved edits in this library are not analysed: the outline, hover, completion"
             " and the diagnostics come from the file on disk")
RL = RN_LIB_TEXT.split("\n")
# The 0-based line the disclosure must be drawn on: the first one that is not empty.
RN_LIB_ANCHOR = next(idx for idx, text in enumerate(RL) if text != "")
RN_LIB_DECL = RL.index("var integer: ticks is 0;")
RN_LIB_USE = RL.index("    ticks +:= 1;")
RN_LIB_DECL_COL = u16(RL[RN_LIB_DECL][:RL[RN_LIB_DECL].index("ticks")])
RN_LIB_USE_COL = u16(RL[RN_LIB_USE][:RL[RN_LIB_USE].index("ticks")])
RN_LIB_COL = RN_LIB_USE_COL + 2
# msgs[2] and msgs[3] -- the .sd7 didOpen/didChange of /tmp/tt_a.sd7 -- are the control document
# for the disclosure's negative check: with no second uri publishing in this very run, "no other
# document receives it" could only pass, and the `disclose to every buffer' mutant that proves it
# can fail would redden nothing here.
S7I_MSGS = [APPLY, msgs[1], msgs[2], msgs[3], opened(RN_LIB_URI, RN_LIB_TEXT),
            req(120, "textDocument/references",
                dict(pos(RN_LIB_URI, RN_LIB_USE, RN_LIB_COL),
                     context={"includeDeclaration": True})),
            req(121, "textDocument/prepareRename", pos(RN_LIB_URI, RN_LIB_USE, RN_LIB_COL)),
            req(122, "textDocument/rename",
                 dict(pos(RN_LIB_URI, RN_LIB_USE, RN_LIB_COL), newName="beats")),
            closed(RN_LIB_URI), shutdown(123), exit_()]
replies, code, err, junk = run([frame(m) for m in S7I_MSGS])
by_id = {r.get("id"): r for r in replies if "id" in r}
lib_refs = by_id.get(120, {}).get("result")
expect(isinstance(lib_refs, list) and
       [(l["range"]["start"]["line"], l["range"]["start"]["character"],
         l["range"]["end"]["character"]) for l in lib_refs] ==
       [(RN_LIB_DECL, RN_LIB_DECL_COL, RN_LIB_DECL_COL + 5),
        (RN_LIB_USE, RN_LIB_USE_COL, RN_LIB_USE_COL + 5)],
       "references still ANSWERS inside a .s7i buffer, with the declaration and the use (%s)"
       % lib_refs)
expect(answered_null(by_id, 121),
       "prepareRename refuses the same cursor in a .s7i buffer (%r)" % by_id.get(121, {}))
expect(answered_null(by_id, 122),
       "and rename refuses it too, so no edit can land on a stale line (%r)" % by_id.get(122, {}))

# Graded from the frames, not from LIB_MSGS, which holds log text only. Grouped per publish
# notification, so "once" means once per publish rather than once per session. The three checks
# below that grade RN_DIS use all(), which is TRUE over an empty list, so they say nothing until
# the >= 2 / == 1 holds -- the same vacuity the astral fixture's guard names for its own checks.
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
# The anchor expectations below are DERIVED from the fixture, so the fixture's shape is a premise
# and not a coincidence: delete the leading blank line and every range check stays green with the
# production anchor reverted. This check passed on sight when it was written (the fixture already had
# the blank line) and is here because the original zero-width defect survived for want of it.
expect(RL[0] == "",
       "and the fixture opens like every real library does: an empty line 1 (%r)" % RL[0])
# `all()' is TRUE over an empty list, so the count is repeated as a conjunct in the two checks
# below: without it both range checks pass on a build that discloses nothing at all.
expect(all(len(x) == 1 for x in RN_DIS[:-1]) and
       all(d["range"]["end"]["character"] > d["range"]["start"]["character"]
           for x in RN_DIS[:-1] for d in x),
       "and its range has the width a squiggle needs (%s)"
       % [d["range"] for x in RN_DIS for d in x])
expect(all(len(x) == 1 for x in RN_DIS[:-1]) and
       all(d["range"] == {"start": {"line": RN_LIB_ANCHOR, "character": 0},
                          "end": {"line": RN_LIB_ANCHOR,
                                   "character": u16(RL[RN_LIB_ANCHOR])}}
           for x in RN_DIS for d in x),
       "and its range is the whole first NON-EMPTY line of the buffer -- line %d, not the blank "
       "line 1 every real .s7i opens with (%s)"
       % (RN_LIB_ANCHOR, [d["range"] for x in RN_DIS for d in x]))
expect(RN_PUBS and RN_PUBS[-1] == [],
       "and didClose still clears the buffer, disclosure included (%s)" % RN_PUBS[-1:])
# Per uri and per publish, and requiring the control to have published: the disclosure is a property
# of a .s7i path, never of a buffer analysed from the client's own text, and a third document that
# never published cannot make this pass.
RN_STALE_BY_URI = [(r["params"]["uri"],
                    len([d for d in r["params"]["diagnostics"]
                         if "unsaved edits in this library" in d.get("message", "")]))
                   for r in replies if r.get("method") == "textDocument/publishDiagnostics"]
expect(all(n == 0 for uri, n in RN_STALE_BY_URI if uri != RN_LIB_URI)
       and any(uri != RN_LIB_URI for uri, _ in RN_STALE_BY_URI),
       "and no other document in the run receives it: the disclosure is a property of a .s7i path, "
       "never of a buffer analysed from the client's own text (%s)" % RN_STALE_BY_URI)
LIB_MSGS = [r.get("params", {}).get("message", "") for r in replies
            if r.get("method") == "window/logMessage"]
LIB_WHY = " is a library buffer whose symbols come from disk while R-F10"


def lib_log(method):
    """The index IN `replies' of the one log frame that refuses this buffer under `method'.

    Both sides of the ordering below have to be reply indices. An index into LIB_MSGS counts log
    frames only -- a different space, where the log is always 0 or 1 and the answer is always
    further on -- so `log < answer' would hold even in a build that answers FIRST and logs after,
    which is the regression this check exists to catch."""
    for i, r in enumerate(replies):
        m = r.get("params", {}).get("message", "")
        if (r.get("method") == "window/logMessage" and
                m.startswith(method + ": " + RN_LIB_PATH) and LIB_WHY in m and
                "so an edit could land on the wrong line" in m):
            return i
    return None


LIB_PREP_LOG = lib_log("prepareRename")
LIB_RENAME_LOG = lib_log("rename")
LIB_PREP_ANS = next((i for i, r in enumerate(replies) if r.get("id") == 121), None)
LIB_RENAME_ANS = next((i for i, r in enumerate(replies) if r.get("id") == 122), None)
expect(LIB_PREP_LOG is not None and LIB_PREP_ANS is not None and LIB_PREP_LOG < LIB_PREP_ANS,
       "the prepareRename refusal names the buffer by its disk path and R-F10 in a log that "
       "arrives before its null (reply %s before reply %s: %s)"
       % (LIB_PREP_LOG, LIB_PREP_ANS, LIB_MSGS))
expect(LIB_RENAME_LOG is not None and LIB_RENAME_ANS is not None and
       LIB_RENAME_LOG < LIB_RENAME_ANS,
       "and the rename refusal does the same (reply %s before reply %s: %s)"
       % (LIB_RENAME_LOG, LIB_RENAME_ANS, LIB_MSGS))
expect(junk == 0, "the library-buffer run put only frames on stdout (junk=%d)" % junk)
one_answer_per_request(S7I_MSGS, replies, "the library-buffer run")

# --- Task 5's reader, on the wire: a library comment's non-ASCII arrives whole ----------------
# The defect was in a DISK read, not in a request body, so no frame this suite can send carries a
# `€' the server would then degrade: `frame' escapes non-ASCII on the way IN and jsonw escapes only
# control chars and lone surrogates -- `€' goes out as raw UTF-8. So the pin goes on the DECODED
# hover prose from a real library -- lib/asn1.s7i's `(** ... *)' above `genAsn1String' (line 372)
# holds a euro at 369. It is the one cover for reader -> prose -> raw UTF-8 out -> Content-Length,
# all four in play, so the wire value is characters, not bytes. Decoded, the euro is one
# character (U+20AC); read one byte per character it becomes three (U+00E2 U+0082 U+00AC) and no
# U+20AC survives, while U+0082 -- which no decoded Seed7 source holds -- appears. Measured, the
# decoded value is 372 characters with three above U+007F; the byte read is 376 with seven.
ASN1_URI = "file:///tmp/tt_asn1_prose.sd7"
ASN1_TEXT = ('$ include "seed7_05.s7i";\n  include "asn1.s7i";\n\n'
             'const proc: main is func\n  begin\n'
             '    writeln(genAsn1String("abc"));\n  end func;\n')
ASN1_LINES = ASN1_TEXT.split("\n")
ASN1_USE = ASN1_LINES.index('    writeln(genAsn1String("abc"));')
ASN1_MSGS = [initialize(), opened(ASN1_URI, ASN1_TEXT),
             req(170, "textDocument/hover",
                 pos(ASN1_URI, ASN1_USE,
                     ASN1_LINES[ASN1_USE].index("genAsn1String") + len("genAsn1String"))),
             shutdown(171), exit_()]
replies, code, err, junk = run([frame(m) for m in ASN1_MSGS])
by_id = {r.get("id"): r for r in replies if "id" in r}
ASN1_HOVER = (by_id.get(170, {}).get("result") or {}).get("contents", {}).get("value", "")
# The column is the token's END, computed from the fixture: `wordAt' is left-of-character, so on
# this text genAsn1String occupies 0-based columns 12..24 and 25 is the cursor that names it --
# measured, 12 and 26 answer null. The index + len(word) form is used, as in the other hovers, so
# a reformatted fixture cannot silently drift onto a position that answers nothing.
ASN1_ABOVE127 = sum(1 for ch in ASN1_HOVER if ord(ch) > 127)
expect("\u20ac" in ASN1_HOVER and ASN1_ABOVE127 == 3 and "\u0082" not in ASN1_HOVER,
       "hover prose read from lib/asn1.s7i arrives as characters, not bytes: the euro sign is ONE "
       "character, the comment's three above-U+007F codepoints (U+20AC, U+00E2, U+00AC) are three, "
       "and no C1 decomposition appears (%d chars, above-U+007F %d, U+20AC x%d, U+0082 x%d)"
       % (len(ASN1_HOVER), ASN1_ABOVE127, ASN1_HOVER.count("\u20ac"),
          ASN1_HOVER.count("\u0082")))

# --- M5 Task 10 gap 3: the two lifecycle edges, per method --------------------------
# main.sd7 gates before handle(), so it cannot tell a new method from an old one -- and a pin
# on `hover' alone cannot see a method that joins the chain on the other side of the gate. All
# three of M5's methods, both edges, in their own runs.
LIFE_PARAMS = [(130, "textDocument/references",
                dict(pos(RN_URI, RN_USE, RN_CHAR), context={"includeDeclaration": True})),
               (131, "textDocument/prepareRename", pos(RN_URI, RN_USE, RN_CHAR)),
               (132, "textDocument/rename",
                dict(pos(RN_URI, RN_USE, RN_CHAR), newName="count2"))]
LIFE_PRE = [req(i, meth, p) for i, meth, p in LIFE_PARAMS] + [exit_()]
replies, code, err, junk = run([frame(m) for m in LIFE_PRE])
by_id = {r.get("id"): r for r in replies if "id" in r}
expect([by_id.get(i, {}).get("error", {}).get("code") for i, _, _ in LIFE_PARAMS] ==
       [-32002, -32002, -32002],
       "references, prepareRename and rename before initialize are each -32002 (%s)"
       % [(i, by_id.get(i, {}).get("error")) for i, _, _ in LIFE_PARAMS])
# Read BEFORE the next run(), which overwrites `junk'. This is the one path where a raise could
# reach stdout before any handler exists, so the bytes on the channel are the observable here.
expect(junk == 0, "the before-initialize run put only frames on stdout (junk=%d)" % junk)
expect(code == 1, "and the session ends on `exit' with no shutdown as status 1, not a crash (%d)"
       % code)
one_answer_per_request(LIFE_PRE, replies, "the before-initialize run")
LIFE_POST = ([APPLY, msgs[1], opened(RN_URI, SYMS), shutdown(139)] +
             [req(i, meth, p) for i, meth, p in LIFE_PARAMS] + [exit_()])
replies, code, err, junk = run([frame(m) for m in LIFE_POST])
by_id = {r.get("id"): r for r in replies if "id" in r}
expect([by_id.get(i, {}).get("error", {}).get("code") for i, _, _ in LIFE_PARAMS] ==
       [-32600, -32600, -32600],
       "the same three after shutdown are each -32600 (%s)"
       % [(i, by_id.get(i, {}).get("error")) for i, _, _ in LIFE_PARAMS])
expect(junk == 0, "the after-shutdown run put only frames on stdout (junk=%d)" % junk)
one_answer_per_request(LIFE_POST, replies, "the after-shutdown run")

# --- Task 2: string ids on the wire, the -32601 a string id used to lose, and silence ---------
# Task 1 made "was this a request?" a property of the id, and 27 call sites follow from that.
# Only frames can show a client would now be answered -- and that a notification still is not.
# The whole session uses string ids because a wrong id in `initialize' is fatal to a client, and
# it holds four notifications (`initialized', `didOpen', the idless hover, and a rename whose
# newName is rejected) beside its five requests. `frame' writes json.dumps with ensure_ascii=True,
# so every id here is ASCII and the byte-framing blind spot noted above does not apply to it.
TRIVIAL = ('$ include "seed7_05.s7i";\n'
           'const proc: main is func\n'
           '  begin\n'
           '    writeln("trivial");\n'
           '  end func;\n')
STR_IDS = [{"jsonrpc": "2.0", "id": "i1", "method": "initialize",
            "params": {"capabilities": {}, "rootUri": "file:///tmp"}},
           {"jsonrpc": "2.0", "method": "initialized", "params": {}},
           opened("/tmp/tt_strid.sd7", TRIVIAL),
           {"jsonrpc": "2.0", "id": "h1", "method": "textDocument/hover",
            "params": pos("/tmp/tt_strid.sd7", 3, 10)},
           {"jsonrpc": "2.0", "id": "u1", "method": "not/a/method", "params": {}},
           {"jsonrpc": "2.0", "method": "textDocument/hover",
            "params": pos("/tmp/tt_strid.sd7", 3, 10)},
           {"jsonrpc": "2.0", "method": "textDocument/rename",
            "params": dict(pos("/tmp/tt_strid.sd7", 3, 10), newName="1bad")},
           {"jsonrpc": "2.0", "id": "d1", "method": "textDocument/definition",
            "params": pos("/tmp/tt_strid.sd7", 3, 10)},
           {"jsonrpc": "2.0", "id": "s1", "method": "shutdown"},
           exit_()]
replies, code, err, junk = run([frame(m) for m in STR_IDS])
# Only RESPONSES: `publishDiagnostics' and `window/logMessage' are frames with a `method' and
# no `id', so collecting on "id" or "method" would put bare `None' entries in the list and the
# equality below could never hold. Measured on this branch: a session with two notification-only
# method calls yields responses exactly ['i1', 's1'].
# Line 3 character 10 lands inside `writeln', so the hover carries its signature and `definition'
# its library locations (measured). The id checks need only that a frame arrives, but a reader who
# trims TRIVIAL to a bare main gets a null hover and a scenario that reads as broken while it is not.
ids = [r.get("id") for r in replies if "result" in r or "error" in r]
by_id = {r.get("id"): r for r in replies if "result" in r or "error" in r}
expect(ids == ["i1", "h1", "u1", "d1", "s1"],
       "every reply carries the string id it answers (%s)" % ids)
# `next' without a default is not an option here: a mutant that drops the -32601 frame, or answers
# it under another id, would abort the whole suite on StopIteration and no graded line would print.
# The `.get(id, {})' idiom of the lifecycle block (:1049) fails the named check instead.
expect((by_id.get("u1", {}).get("error") or {}).get("code") == -32601,
       "the unknown string-id method is answered with -32601, not with silence")
expect("capabilities" in (by_id.get("i1", {}).get("result") or {}),
       "and initialize answered under its own id, so the client finishes starting up")
expect(not any(r.get("id") == 0 for r in replies if "result" in r or "error" in r),
       "and nothing is answered under a borrowed integer id 0 (%s)" % ids)
expect(not any("error" in r and r["error"]["code"] == -32602 and r.get("id") is None
               for r in replies),
       "and the rename notification with a rejected newName is not answered either (%s)"
       % [r for r in replies if "error" in r])
expect(code == 0 and junk == 0, "the string-id session exits clean (code=%d junk=%d)" % (code, junk))
one_answer_per_request(STR_IDS, replies, "the string-id session")

# --- M5 Task 10 gap 4: `workspace': null, the malformed client shape ----------------
# A missing `workspace' key is pinned by the refusal runs above (msgs[0] has no such key). This
# is the other shape: the key PRESENT and its value JSON null. atKey must hand the null back and
# boolAt must fall through to FALSE rather than calling `boolean(jsonValue)', which raises
# ILLEGAL_ACTION -- and a raise that reaches stdout corrupts the protocol channel, so the run
# has to end with the ordinary answers and a clean exit.
NULL_WS = req(1, "initialize", {"capabilities": {}, "processId": None, "rootUri": None,
                                "workspace": None})
NW_URI = "file:///tmp/tt_syms_nullws.sd7"
NW_HOVER = REF_LINES.index("    writeln(totalSize(prototype, 2));")
NW_HCHAR = REF_LINES[NW_HOVER].index("totalSize") + 4
NW_MSGS = [NULL_WS, msgs[1], opened(NW_URI, SYMS),
           req(140, "textDocument/prepareRename", pos(NW_URI, RN_USE, RN_CHAR)),
           req(141, "textDocument/rename", dict(pos(NW_URI, RN_USE, RN_CHAR), newName="count2")),
           req(142, "textDocument/references",
               dict(pos(NW_URI, RN_USE, RN_CHAR), context={"includeDeclaration": True})),
           req(143, "textDocument/references",
                dict(pos(NW_URI, RN_USE, RN_CHAR), context=None)),
           req(144, "textDocument/hover", pos(NW_URI, NW_HOVER, NW_HCHAR)),
           shutdown(145), exit_()]
replies, code, err, junk = run([frame(m) for m in NW_MSGS])
by_id = {r.get("id"): r for r in replies if "id" in r}
expect(answered_null(by_id, 140),
       "workspace: null -> prepareRename answers null, not an error frame (%r)"
       % by_id.get(140, {}))
expect(answered_null(by_id, 141),
       "and rename answers null, not an error frame (%r)" % by_id.get(141, {}))
# The VALUES, not "is a list": `[]' satisfies isinstance(x, list) twice over, so a build that
# dropped every occurrence through a null context would have passed the type test. Measured on
# this cursor: the two answers are the SAME list, because reportWidget's `counter' is declared on
# the header line, which IS the line its body region opens on, so the declaration is already one
# of the occurrences and includeDeclaration has nothing to add (features_test.sd7's "a declaration
# already in the list is not published twice" says the same for the unit fixture). If the null
# context ever cost the client its locations, the first check below stays green and this one
# reddens on `[18, 59, 66], [21, 4, 11]` -> `[]'.
NW_EXPECT = [(l, PR_LINES[l].index("counter"), PR_LINES[l].index("counter") + 7)
             for l in (RN_HEAD, RN_USE)]
nw_obj = by_id.get(142, {}).get("result")
nw_null = by_id.get(143, {}).get("result")
expect(isinstance(nw_obj, list) and ref_cols(nw_obj) == NW_EXPECT,
       "references with a context object answers exactly %s (%s)" % (NW_EXPECT, nw_obj))
expect(isinstance(nw_null, list) and ref_cols(nw_null) == NW_EXPECT,
       "and a JSON null context answers the same %s, not an empty list (%s)"
       % (NW_EXPECT, nw_null))
hv_nw = (by_id.get(144, {}).get("result") or {}).get("contents", {}).get("value", "")
expect("totalSize" in hv_nw, "the same session still answers hover (%r)" % hv_nw)
expect(code == 0 and junk == 0,
       "nothing raised to stdout and the session shut down normally (code=%d, junk=%d)"
       % (code, junk))
one_answer_per_request(NW_MSGS, replies, "the workspace-null run")

# --- M5 Task 10 fix round 1: the one cursor where includeDeclaration decides ----------
# Every other wire references request sends TRUE (ids 110, 115, 120, 130, 142) or sends no
# `context' at all (id 41, which defaults to FALSE and is not asked about the flag), so a
# production regression that ignored the flag entirely was visible only in units. This document is
# the shape the flag exists for: a TWO-LINE routine header puts the first parameter's declaration
# on the line ABOVE the one the body region opens on, so inScope does not hold it and
# includeDeclaration is the only thing that can add it (spec 11.9; the unit pins are
# features_test.sd7's "without includeDeclaration the declaration above the region stays out" and
# "includeDeclaration adds it as a whole line, because reflection has no column", and they never
# crossed a frame). The whole-line location is what production emits -- start of the declaration
# line to start of the next -- because reflection gives a declaration no column.
HDR_TEXT = ('$ include "seed7_05.s7i";\n'
            '  include "console.s7i";\n'
            '\n'
            'const proc: pair (in integer: left,\n'
            '                   in integer: right) is func\n'
            '  begin\n'
            '    writeln(left + right);\n'
            '  end func;\n'
            '\n'
            'const proc: main is func\n'
            '  begin\n'
            '    pair(2, 3);\n'
            '  end func;\n')
HDR_URI = "file:///tmp/tt_hdr_wire.sd7"
HDR_LINES = HDR_TEXT.split("\n")
HDR_DECL = HDR_LINES.index("const proc: pair (in integer: left,")
HDR_USE = HDR_LINES.index("    writeln(left + right);")
HDR_COL = HDR_LINES[HDR_USE].index("left")
HDR_EXPECT = [{"uri": HDR_URI,
               "range": {"start": {"line": HDR_DECL, "character": 0},
                         "end": {"line": HDR_DECL + 1, "character": 0}}},
              {"uri": HDR_URI,
               "range": {"start": {"line": HDR_USE, "character": HDR_COL},
                         "end": {"line": HDR_USE, "character": HDR_COL + 4}}}]
HDR_MSGS = [APPLY, msgs[1], opened(HDR_URI, HDR_TEXT),
            req(150, "textDocument/references",
                dict(pos(HDR_URI, HDR_USE, HDR_COL + 2), context={"includeDeclaration": True})),
            req(151, "textDocument/references",
                 dict(pos(HDR_URI, HDR_USE, HDR_COL + 2), context={"includeDeclaration": False})),
            shutdown(152), exit_()]
replies, code, err, junk = run([frame(m) for m in HDR_MSGS])
by_id = {r.get("id"): r for r in replies if "id" in r}
hdr_true = by_id.get(150, {}).get("result")
hdr_false = by_id.get(151, {}).get("result")
expect(hdr_true == HDR_EXPECT,
       "includeDeclaration: true adds the declaration that sits above the region (%s)" % hdr_true)
expect(hdr_false == HDR_EXPECT[1:],
       "and the identical cursor asked with FALSE answers just the use -- the flag decides, it is "
       "not ignored (%s; true was %s)" % (hdr_false, hdr_true))
one_answer_per_request(HDR_MSGS, replies, "the includeDeclaration run")
expect(junk == 0, "the includeDeclaration run put only frames on stdout (junk=%d)" % junk)

# --- M5 Task 10 F1 / FIXED by Task 12: a frame body is read by BYTE, not by character ---
# HISTORY (kept, not rewritten): Task 10 found that `transport.sd7' handed Content-Length -- a BYTE
# count -- to `gets' on a UTF-8 file, which counts CHARACTERS, so any body holding a non-ASCII
# character read past its own frame and ate the first byte of the next header. Measured with the
# defect live: answered ids were [1] of 3 requests, the hover and shutdown behind the body never
# came back, and stderr logged the mangled header. It had hid for four milestones because `frame'
# writes json.dumps' DEFAULT ensure_ascii=True, so no body this suite sent ever held a byte over
# 127 -- which is why the control below is the SAME hand-built raw framing with a BMP-free body:
# without it, a build that answered nothing at all would pass either pin.
# Task 12 flipped this pin on purpose. The strongest form is the file's own idiom below, so the run
# is now asserted request-for-answer rather than by a hand-listed id set.
def raw_frame(obj):
    """One frame with the body a real client sends: raw UTF-8, Content-Length its BYTE length.

    `frame' is left alone -- it computes Content-Length from the encoded body too, but json.dumps'
    escaping means that body is ASCII, so the two numbers always agreed there."""
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    return b"Content-Length: %d\r\n\r\n" % len(body) + body


def raw_msgs(text, uri):
    """initialize, didOpen, hover, shutdown, exit -- as messages, so the run can count them."""
    return [initialize(1), opened(uri, text),
            req(160, "textDocument/hover", pos(uri, 2, 6)), shutdown(161), exit_()]


def raw_seq(msgs_):
    """Frame every message, EXCEPT the didOpen, which goes out raw: the byte-counted body is the
    only difference between the two runs below, so a boundary error cannot be blamed on the
    builder. Before Task 12 that one difference was the whole defect."""
    return [raw_frame(m) if m.get("method") == "textDocument/didOpen" else frame(m)
            for m in msgs_]


RAW_URI = "file:///tmp/tt_raw_utf8.sd7"
RAW_TEXT = 'const proc: main is func\n  begin\n    writeln("\u03c0");\n  end func;\n'
RAW_CTRL_URI = "file:///tmp/tt_raw_ascii.sd7"
RAW_CTRL_TEXT = RAW_TEXT.replace("\u03c0", "p")
RAW_MSGS = raw_msgs(RAW_TEXT, RAW_URI)
replies, code, err, junk = run(raw_seq(RAW_MSGS))
raw_answered = sorted(r["id"] for r in replies if "id" in r and
                      ("result" in r or "error" in r))
expect(raw_answered == [1, 160, 161],
       "FIXED F1: a didOpen body whose Content-Length counts BYTES while its text holds a "
       "multi-byte character no longer swallows the next header -- ids answered %s of the 3 "
       "requests (%s)" % (raw_answered, err[-160:]))
expect("frame without Content-Length" not in err,
       "and no mangled header reaches the transport at all now (%r)" % err[-160:])
expect(junk == 0, "the F1 run put only frames on stdout (junk=%d)" % junk)
one_answer_per_request(RAW_MSGS, replies, "the fixed-F1 run")
CTRL_MSGS = raw_msgs(RAW_CTRL_TEXT, RAW_CTRL_URI)
replies, code, err, junk = run(raw_seq(CTRL_MSGS))
ctrl_answered = sorted(r["id"] for r in replies if "id" in r and
                       ("result" in r or "error" in r))
expect(ctrl_answered == [1, 160, 161],
       "positive control: the same raw framing, BMP-free, is answered end to end (%s)"
       % ctrl_answered)
one_answer_per_request(CTRL_MSGS, replies, "the F1 control run")
expect(junk == 0, "the F1 control run put only frames on stdout (junk=%d)" % junk)

# --- M3: completion after a typed prefix ---
# Type "tot" on a line the fixture does not have. The position is derived from the text
# so editing the fixture cannot silently move it -- and one attempt at this check had
# landed on "prototype" instead, which is why it is computed twice over.
COMP_TYPED = "const integer: tot"
COMP_TEXT = SYMS + "\n" + COMP_TYPED + "Marker is 1;\n"
COMP_LINES = COMP_TEXT.split("\n")
COMP_LINE = COMP_LINES.index(COMP_TYPED + "Marker is 1;")
COMP_CHAR = len(COMP_TYPED)          # cursor right after the typed "tot"
replies, code, err, junk = run([
    frame(msgs[0]), frame(msgs[1]),
    frame({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params":
           {"textDocument": {"uri": "file:///tmp/tt_syms.sd7", "languageId": "seed7",
                             "version": 1, "text": COMP_TEXT}}}),
    frame({"jsonrpc": "2.0", "id": 50, "method": "textDocument/completion", "params":
           {"textDocument": {"uri": "file:///tmp/tt_syms.sd7"},
            "position": {"line": COMP_LINE, "character": COMP_CHAR}}}),
    frame({"jsonrpc": "2.0", "id": 51, "method": "shutdown"}),
    frame({"jsonrpc": "2.0", "method": "exit"}),
])
by_id = {r.get("id"): r for r in replies if "id" in r}
comp = by_id.get(50, {}).get("result") or {}
labels = [i.get("label") for i in (comp.get("items", comp) if isinstance(comp, dict) else comp)]
expect(set(labels[:2]) == {"totalSize", "totMarker"},
       "completion offers the prefix matches from this file first, got %s" % labels[:6])
expect(not isinstance(comp, dict) or comp.get("isIncomplete") is not True,
       "a short completion list stays a plain array")

# --- M3: signatureHelp inside a call, second argument ---
SIG_TEXT = SYMS + "\nconst integer: totMarker is 1;\n"
SIG_LINES = SIG_TEXT.split("\n")
SIG_LINE = SIG_LINES.index('    reportWidget("proto", hits);')
SIG_CHAR = SIG_LINES[SIG_LINE].index("hits")
replies, code, err, junk = run([
    frame(msgs[0]), frame(msgs[1]),
    frame({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params":
           {"textDocument": {"uri": "file:///tmp/tt_syms.sd7", "languageId": "seed7",
                             "version": 1, "text": SIG_TEXT}}}),
    frame({"jsonrpc": "2.0", "id": 60, "method": "textDocument/signatureHelp", "params":
           {"textDocument": {"uri": "file:///tmp/tt_syms.sd7"},
            "position": {"line": SIG_LINE, "character": SIG_CHAR}}}),
    frame({"jsonrpc": "2.0", "id": 61, "method": "textDocument/signatureHelp", "params":
           {"textDocument": {"uri": "file:///tmp/tt_syms.sd7"},
            "position": {"line": SIG_LINE, "character": SIG_CHAR - 15}}}),
    frame({"jsonrpc": "2.0", "id": 62, "method": "shutdown"}),
    frame({"jsonrpc": "2.0", "method": "exit"}),
])
by_id = {r.get("id"): r for r in replies if "id" in r}
sig = by_id.get(60, {}).get("result") or {}
sigs = [x.get("label", "") for x in sig.get("signatures", [])]
expect(len(sigs) == 1 and "reportWidget" in sigs[0],
       "signatureHelp names the callee, got %s" % sigs)
expect(sig.get("activeParameter") == 1,
       "second argument is active, got %r" % sig.get("activeParameter"))
expect([x.get("label") for x in sig.get("signatures", [{}])[0].get("parameters", [])] ==
       ["string: label", "integer: counter"], "parameters listed in order")
expect(by_id.get(61, {}).get("result") is None,
       "signatureHelp outside a call is null")

# --- spec §8 M3 exit test: the features must also work on a .s7i buffer, which is
# --- analysed through the synthetic driver because a library cannot be parsed alone ---
LIB_PATH = "/tmp/seed7_lsp_transcript_lib.s7i"
LIB_TEXT = ("const func integer: libDouble (in integer: n) is func\n"
            "  result\n"
            "    var integer: twice is 0;\n"
            "  begin\n"
            "    twice := n * 2;\n"
            "  end func;\n\n"
            "const proc: libTell (in string: msg) is func\n"
            "  begin\n"
            "    writeln(msg);\n"
            "  end func;\n")
with open(LIB_PATH, "w") as f:
    f.write(LIB_TEXT)
LIB_URI = "file://" + LIB_PATH
replies, code, err, junk = run([
    frame(msgs[0]), frame(msgs[1]),
    frame({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params":
           {"textDocument": {"uri": LIB_URI, "languageId": "seed7",
                             "version": 1, "text": LIB_TEXT}}}),
    frame({"jsonrpc": "2.0", "id": 70, "method": "textDocument/documentSymbol", "params":
           {"textDocument": {"uri": LIB_URI}}}),
    frame({"jsonrpc": "2.0", "id": 71, "method": "textDocument/definition", "params":
           {"textDocument": {"uri": LIB_URI},
            "position": {"line": 7, "character": 16}}}),
    frame({"jsonrpc": "2.0", "id": 72, "method": "textDocument/hover", "params":
           {"textDocument": {"uri": LIB_URI},
            "position": {"line": 9, "character": 8}}}),
    frame({"jsonrpc": "2.0", "id": 74, "method": "textDocument/hover", "params":
           {"textDocument": {"uri": LIB_URI},
            "position": {"line": 9, "character": 15}}}),
    frame({"jsonrpc": "2.0", "id": 73, "method": "shutdown"}),
    frame({"jsonrpc": "2.0", "method": "exit"}),
])
by_id = {r.get("id"): r for r in replies if "id" in r}
lib_syms = by_id.get(70, {}).get("result") or []
expect([x["name"] for x in lib_syms] == ["libDouble", "libTell"],
       "documentSymbol works on a .s7i buffer via the driver, got %s" % [x.get("name") for x in lib_syms])
lib_def = by_id.get(71, {}).get("result") or []
expect(any(d["uri"] == LIB_URI and d["range"]["start"]["line"] == 7 for d in lib_def),
       "definition on a .s7i buffer points at its own declaration (%s)" % lib_def[:1])
lib_hov = ((by_id.get(72, {}).get("result") or {}).get("contents") or {}).get("value", "")
expect("proc: writeln" in lib_hov,
       "hover from a .s7i buffer still reaches the stdlib (%r)" % lib_hov[:60])
# The parameter "msg" on the same line is not a global, and reflection has no local
# symbols for a declaration in another file -- this pins the gap the follow-up plan for
# local-variable completion has to close.
expect(by_id.get(74, {}).get("result") is None,
       "hover of a parameter is null: locals are not in the reflection table")

# --- hostile framing must cost a request, never the server (review I1) ---
for label, hdr in [("non-numeric", b"Content-Length: abc"),
                   ("negative",    b"Content-Length: -5"),
                   ("oversized",   b"Content-Length: 999999999"),
                   ("over-wide",   b"Content-Length: 99999999999999999999999")]:
    replies, code, err, junk = run([frame(msgs[0]),
                              hdr + b"\r\n\r\n",
                              frame({"jsonrpc": "2.0", "id": 11, "method": "shutdown"}),
                              frame({"jsonrpc": "2.0", "method": "exit"})])
    expect(code == 2 and junk == 0 and "invalid Content-Length" in err,
           "%s Content-Length: clean fatal exit, stdout uncorrupted" % label)

# --- malformed JSON body is a Parse error (-32700), not an internal error ---
replies, code, err, junk = run([frame(msgs[0]),
                          b"Content-Length: 16\r\n\r\n{not json at all",
                          frame({"jsonrpc": "2.0", "id": 12, "method": "shutdown"}),
                          frame({"jsonrpc": "2.0", "method": "exit"})])
expect(any(r.get("error", {}).get("code") == -32700 for r in replies),
       "malformed JSON answered with -32700")
expect(any(r.get("id") == 12 and "result" in r for r in replies) and code == 0 and junk == 0,
       "server keeps serving after a parse error, stdout uncorrupted")
expect(all(r.get("id") is None or "method" in r for r in replies
           if r.get("error", {}).get("code") == -32700),
       "parse error carries a null id, per JSON-RPC")

# --- Task 1/2 wire proofs: analyzer byte columns arrive as UTF-16 character ranges,
# --- and code after a based literal is visible to wordAt again ---
# A line whose error sits behind two 2-byte characters: the analyzer counts bytes,
# the client counts UTF-16 units, and the range must arrive in the client's units.
PI = '$ include "seed7_05.s7i";\nconst proc: main is func\n  begin\n    writeln("\u03c0\u03c0\\z");\n  end func;\n'
RADIX = ('$ include "seed7_05.s7i";\nconst integer: afterThis is 1;\n'
         'const proc: main is func\n  local\n    var integer: total is 0;\n  begin\n'
         '    total := 16#beef + afterThis;\n    writeln(total);\n  end func;\n')
msgs2 = [
    {"jsonrpc": "2.0", "id": 10, "method": "initialize", "params": {"capabilities": {}}},
    {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params":
        {"textDocument": {"uri": "file:///tmp/tt_pi.sd7", "languageId": "seed7",
                          "version": 1, "text": PI}}},
    {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params":
        {"textDocument": {"uri": "file:///tmp/tt_radix.sd7", "languageId": "seed7",
                          "version": 1, "text": RADIX}}},
    {"jsonrpc": "2.0", "id": 11, "method": "textDocument/hover", "params":
        {"textDocument": {"uri": "file:///tmp/tt_radix.sd7"},
         "position": {"line": 6, "character": 26}}},
    {"jsonrpc": "2.0", "id": 12, "method": "textDocument/definition", "params":
        {"textDocument": {"uri": "file:///tmp/tt_radix.sd7"},
         "position": {"line": 6, "character": 26}}},
    {"jsonrpc": "2.0", "id": 13, "method": "shutdown"},
    {"jsonrpc": "2.0", "method": "exit"},
]
replies2, code2, err2, junk2 = run([frame(m) for m in msgs2])
by_id2 = {r.get("id"): r for r in replies2 if "id" in r}
notes2 = [r for r in replies2 if r.get("method") == "textDocument/publishDiagnostics"]
pi_notes = [n for n in notes2 if n["params"]["uri"] == "file:///tmp/tt_pi.sd7"]
expect(len(pi_notes) == 1, "the escape fixture publishes one diagnostic")
if pi_notes:
    pid = pi_notes[0]["params"]["diagnostics"]
    expect(len(pid) == 1,
           "the escape notification carries exactly one diagnostic, got %d" % len(pid))
    if len(pid) == 1:
        pr = pid[0]["range"]
        expect(pr["start"] == {"line": 3, "character": 16} and
               pr["end"] == {"line": 3, "character": 17},
               "diagnostic range is in characters, not bytes (%r)" % pr)
        expect(pid[0]["message"] == 'Illegal string escape "\\z"',
               "diagnostic message is the analyzer's own (%r)" % pid[0]["message"])
radix_notes = [n for n in notes2 if n["params"]["uri"] == "file:///tmp/tt_radix.sd7"]
expect(len(radix_notes) == 1 and radix_notes[0]["params"]["diagnostics"] == [],
       "the based-literal fixture publishes no diagnostics (%r)" % radix_notes)
hov2 = by_id2.get(11, {}).get("result") or {}
expect("afterThis" in hov2.get("contents", {}).get("value", ""),
       "hover reaches a name written after a based literal (%r)" % hov2)
defn2 = by_id2.get(12, {}).get("result") or []
expect(len(defn2) == 1 and defn2[0]["range"]["start"]["line"] == 1,
       "definition reaches it too (%r)" % defn2)
expect(code2 == 0 and junk2 == 0,
       "exit after shutdown is status 0 and stdout held only frames for the second run (%d, junk=%d)"
       % (code2, junk2))

# --- Task 10: foldingRange -------------------------------------------------
FOLD_URI = "file:///tmp/tt_fold.sd7"
FOLD_TEXT = "const proc: a is func\nbegin\n  if TRUE then\n    noop;\n  end if;\nend func;\n"
replies, code, err, junk = run([frame(initialize(1)), frame(msgs[1]),
                                frame(opened(FOLD_URI, FOLD_TEXT)),
                                frame(req(2, "textDocument/foldingRange",
                                          {"textDocument": {"uri": FOLD_URI}})),
                                frame(req(3, "textDocument/foldingRange",
                                          {"textDocument": {"uri": "file:///tmp/not_open.sd7"}})),
                                frame(shutdown(4)), frame(exit_())])
by_id = {r.get("id"): r for r in replies if "id" in r}
folds = by_id.get(2, {}).get("result") or []
expect(isinstance(folds, list) and len(folds) == 3,
       "foldingRange returns 3 regions for the fixture, got %d" % len(folds))
if len(folds) == 3:
    expect(folds[0] == {"startLine": 0, "endLine": 5},
           "first fold is the function body (%r)" % folds[0])
    expect(folds[1] == {"startLine": 1, "endLine": 5},
           "second fold is the begin block (%r)" % folds[1])
    expect(folds[2] == {"startLine": 2, "endLine": 4},
           "third fold is the if block (%r)" % folds[2])
expect(by_id.get(3, {}).get("result") == [],
       "foldingRange for an unopened uri is []")
expect("foldingRangeProvider" in replies[0].get("result", {}).get("capabilities", {}),
       "initialize advertises foldingRangeProvider")

# --- Task 11: selectionRange -------------------------------------------------
SEL_URI = "file:///tmp/tt_sel.sd7"
SEL_TEXT = "$ include \"seed7_05.s7i\";\nconst proc: main is func\n  begin\n    writeln(1);\n  end func;"
replies, code, err, junk = run([frame(initialize(1)), frame(msgs[1]),
                                frame(opened(SEL_URI, SEL_TEXT)),
                                frame(req(2, "textDocument/selectionRange",
                                          {"textDocument": {"uri": SEL_URI},
                                           "positions": [{"line": 3, "character": 4}]})),
                                frame(req(3, "textDocument/selectionRange",
                                          {"textDocument": {"uri": "file:///tmp/not_open.sd7"},
                                           "positions": [{"line": 0, "character": 0}]})),
                                frame(shutdown(4)), frame(exit_())])
by_id = {r.get("id"): r for r in replies if "id" in r}
sel = by_id.get(2, {}).get("result") or []
# The extraction loop indexes the result per position; an IndexError here is load-bearing —
# a regression in dispatch/capability would otherwise pass silently.
expect(isinstance(sel, list) and len(sel) == 1,
       "selectionRange returns one result per position, got %d" % len(sel))
if len(sel) == 1:
    expect("range" in sel[0] and "parent" in sel[0],
           "selectionRange result has range and parent keys")
    # Walk the chain to verify it's nested correctly.
    node = sel[0]
    depth = 0
    while "parent" in node:
        depth += 1
        node = node["parent"]
    expect(depth == 3,
           "selectionRange chain has 3 parent levels (token->region->region->document), got %d" % depth)
    expect("parent" not in node,
           "outermost selectionRange has no parent key")
expect(by_id.get(3, {}).get("result") == [],
       "selectionRange for an unopened uri is []")
expect("selectionRangeProvider" in replies[0].get("result", {}).get("capabilities", {}),
       "initialize advertises selectionRangeProvider")

# --- Task 9 / spec §4.2: one analysis per document version -------------------
CACHE_URI = "file:///tmp/tt_cache.sd7"
CACHE_LINES = SYMS.split("\n")
CACHE_LINE = CACHE_LINES.index("    writeln(totalSize(prototype, 2));")
CACHE_CHAR = CACHE_LINES[CACHE_LINE].index("totalSize") + 4   # inside "totalSize"
CACHE_TAIL = "\nconst integer: onlyAfterChange is 1;\n"

# Hover and definition on the same version: both are served from one analysis.
replies, code, err, junk = run([frame(initialize(1)), frame(msgs[1]),
                                frame(opened(CACHE_URI, SYMS)),
                                frame(req(2, "textDocument/hover",
                                          pos(CACHE_URI, CACHE_LINE, CACHE_CHAR))),
                                frame(req(3, "textDocument/definition",
                                          pos(CACHE_URI, CACHE_LINE, CACHE_CHAR))),
                                frame(shutdown(4)), frame(exit_())])
by_id = {r.get("id"): r for r in replies if "id" in r}
expect(analyses(err) == 1,
       "hover + definition on one version cost one analysis (saw %d)" % analyses(err))
cache_hov = (by_id.get(2, {}).get("result") or {}).get("contents", {}).get("value", "")
expect("totalSize" in cache_hov, "the cached records answer the hover (%r)" % cache_hov)
cache_def = by_id.get(3, {}).get("result") or []
expect(bool(cache_def) and cache_def[0]["range"]["start"]["line"] == 8,
       "the cached records answer the definition (%s)" % cache_def[:1])

# A didChange must cost exactly one more analysis, and the new version's own declaration must
# reach the outline: the same assertion against a cache that never misses is the whole point.
replies, code, err, junk = run([frame(initialize(1)), frame(msgs[1]),
                                frame(opened(CACHE_URI, SYMS)),
                                frame(req(2, "textDocument/documentSymbol", td(CACHE_URI))),
                                frame(changed(CACHE_URI, SYMS + CACHE_TAIL, 2)),
                                frame(req(3, "textDocument/hover",
                                          pos(CACHE_URI, CACHE_LINE, CACHE_CHAR))),
                                frame(req(4, "textDocument/definition",
                                          pos(CACHE_URI, CACHE_LINE, CACHE_CHAR))),
                                frame(req(5, "textDocument/documentSymbol", td(CACHE_URI))),
                                frame(shutdown(6)), frame(exit_())])
by_id = {r.get("id"): r for r in replies if "id" in r}
expect(analyses(err) == 2,
       "a didChange costs exactly one more analysis, not three (saw %d)" % analyses(err))
before_names = [s["name"] for s in by_id.get(2, {}).get("result") or []]
after_names = [s["name"] for s in by_id.get(5, {}).get("result") or []]
expect("onlyAfterChange" not in before_names, "the first outline is the first version's")
expect("onlyAfterChange" in after_names,
       "the changed version's own declaration reaches the outline (%s)" % after_names)

# didClose drops the entry: reopened at the *same* version, the document must not inherit the
# previous session's records. Version equality alone cannot save this one.
replies, code, err, junk = run([frame(initialize(1)), frame(msgs[1]),
                                frame(opened(CACHE_URI, SYMS)),
                                frame(closed(CACHE_URI)),
                                frame(opened(CACHE_URI, SYMS +
                                             "\nconst integer: reopenedMarker is 1;\n")),
                                frame(req(2, "textDocument/documentSymbol", td(CACHE_URI))),
                                frame(shutdown(3)), frame(exit_())])
by_id = {r.get("id"): r for r in replies if "id" in r}
reopen_names = [s["name"] for s in by_id.get(2, {}).get("result") or []]
expect("reopenedMarker" in reopen_names,
       "a document reopened after close re-analyses (%s)" % reopen_names)

# --- round 1, finding 1: invalidation may not depend on a client-supplied number ---
# A versionless didChange. The document opens broken, the change replaces it with a valid
# program that declares something new, and the frame carries no version. Answering it from the
# previous entry would publish the old file's errors and an outline missing the new declaration.
replies, code, err, junk = run([frame(initialize(1)), frame(msgs[1]),
                                frame(opened(CACHE_URI, BROKEN, 1)),
                                frame(changed_no_version(CACHE_URI, SYMS + CACHE_TAIL)),
                                frame(req(2, "textDocument/documentSymbol", td(CACHE_URI))),
                                frame(shutdown(3)), frame(exit_())])
by_id = {r.get("id"): r for r in replies if "id" in r}
vless_notes = [r for r in replies if r.get("method") == "textDocument/publishDiagnostics"
               and r["params"]["uri"] == CACHE_URI]
expect(analyses(err) == 2,
       "a didChange with no version is a new version (saw %d analyses)" % analyses(err))
vless_last = vless_notes[-1]["params"]["diagnostics"] if vless_notes else None
expect(bool(vless_notes) and vless_last == [],
       "the versionless change publishes the NEW text's diagnostics (%s)" % vless_last)
vless_names = [s["name"] for s in by_id.get(2, {}).get("result") or []]
expect("onlyAfterChange" in vless_names,
       "the versionless change's declaration reaches the outline (%s)" % vless_names)

# A didOpen with no didClose in between, same version number. Also malformed (LSP says a client
# must not), also answered here -- so the entry the first open left must not survive it.
replies, code, err, junk = run([frame(initialize(1)), frame(msgs[1]),
                                frame(opened(CACHE_URI, SYMS, 1)),
                                frame(opened(CACHE_URI, SYMS +
                                             "\nconst integer: reopenedWithoutClose is 1;\n", 1)),
                                frame(req(2, "textDocument/documentSymbol", td(CACHE_URI))),
                                frame(shutdown(3)), frame(exit_())])
by_id = {r.get("id"): r for r in replies if "id" in r}
reopen2 = [s["name"] for s in by_id.get(2, {}).get("result") or []]
expect("reopenedWithoutClose" in reopen2,
       "a didOpen that follows no didClose re-analyses (%s)" % reopen2)

# --- Task 12: semanticTokens -----------------------------------------------
def decode_semantic_tokens(data):
    """Turn the 5-int relative array back into absolute (line, col, length, type, mods)."""
    out, line, col = [], 0, 0
    for i in range(0, len(data), 5):
        dline, dcol, length, ty, mods = data[i:i + 5]
        line += dline
        col = dcol if dline else col + dcol
        out.append((line, col, length, ty, mods))
    return out

ST_URI = "file:///tmp/tt_sem.sd7"
ST_TEXT = '$ include "seed7_05.s7i";\nconst integer: x is 0;\n"\U00010000" (x)\n'
replies, code, err, junk = run([frame(initialize(1)), frame(msgs[1]),
                                frame(opened(ST_URI, ST_TEXT)),
                                frame(req(2, "textDocument/semanticTokens/full",
                                          {"textDocument": {"uri": ST_URI}})),
                                frame(req(3, "textDocument/semanticTokens/range",
                                          {"textDocument": {"uri": ST_URI},
                                           "range": {"start": {"line": 1, "character": 0},
                                                     "end": {"line": 1, "character": 10}}})),
                                frame(req(4, "textDocument/semanticTokens/full",
                                          {"textDocument": {"uri": "file:///tmp/not_open.sd7"}})),
                                frame(shutdown(5)), frame(exit_())])
by_id = {r.get("id"): r for r in replies if "id" in r}
init_caps = replies[0].get("result", {}).get("capabilities", {})
expect("semanticTokensProvider" in init_caps,
       "initialize advertises semanticTokensProvider")
st_cap = init_caps.get("semanticTokensProvider", {})
expect(st_cap.get("full") is True and st_cap.get("range") is True,
       "semanticTokensProvider advertises full and range (%r)" % st_cap)
legend = st_cap.get("legend", {})
expect(legend.get("tokenTypes") == ["comment", "string", "number", "function", "type",
       "variable", "enumMember"],
       "legend tokenTypes are the seven types in index order (%r)" % legend.get("tokenTypes"))
expect(legend.get("tokenModifiers") == ["declaration", "defaultLibrary"],
       "legend tokenModifiers are the two modifiers (%r)" % legend.get("tokenModifiers"))

full = by_id.get(2, {}).get("result") or {}
full_data = full.get("data", [])
full_decoded = decode_semantic_tokens(full_data)
# Line 0: $ include "seed7_05.s7i"; -> include (function, defaultLibrary) + string
# Line 1: const integer: x is 0; -> const (function,lib), integer (type,lib), x (variable,declaration), 0 (number)
# Line 2: "\U00010000" (x) -> string width=4 (astral=2 UTF-16 units), x (variable, no mods)
expect(full_decoded == [(0, 2, 7, 3, 2), (0, 10, 14, 1, 0),
                        (1, 0, 5, 3, 2), (1, 6, 7, 4, 2), (1, 15, 1, 5, 1), (1, 20, 1, 2, 0),
                        (2, 0, 4, 1, 0), (2, 6, 1, 5, 0)],
       "semanticTokens/full decoded tuples with astral char (%r)" % full_decoded)

rng = by_id.get(3, {}).get("result") or {}
rng_data = rng.get("data", [])
rng_decoded = decode_semantic_tokens(rng_data)
expect(rng_decoded == [(1, 0, 5, 3, 2), (1, 6, 7, 4, 2), (1, 15, 1, 5, 1), (1, 20, 1, 2, 0)],
       "semanticTokens/range decoded tuples for line 1 only (%r)" % rng_decoded)

expect(by_id.get(4, {}).get("result") is None,
       "semanticTokens/full for an unopened uri is null")

# --- Task 4: the trust gate on the wire ----------------------------------------
# After-the-fact pins: Task 3 shipped the gate (analysable gates ensureAnalyzed and refresh,
# and an untrusted didOpen sends one window/logMessage whose sentence contains "roots").
# Block one: a client that declared file:///tmp/proj as its root opens one file inside it and
# one outside; the outside file is never analysed, publishes nothing, and the refusal names the
# roots. Block two: a client that declared NO root runs unguarded and still gets diagnostics.
IN_URI = "file:///tmp/seed7_lsp_proj/in.sd7"
OUT_URI = "file:///tmp/outside.sd7"
GATE_INIT = req(1, "initialize",
                  {"capabilities": {}, "processId": None,
                   "rootUri": "file:///tmp/seed7_lsp_proj"})
replies, code, err, junk = run([frame(GATE_INIT), frame(msgs[1]),
                                frame(opened(IN_URI, BROKEN)),
                                frame(opened(OUT_URI, BROKEN)),
                                frame(changed(OUT_URI, BROKEN, 2)),
                                frame(closed(OUT_URI)),
                                frame(shutdown(2)), frame(exit_())])
diag_notes = [r for r in replies if r.get("method") == "textDocument/publishDiagnostics"]
expect(not any(p["params"]["uri"] == OUT_URI for p in diag_notes),
       "a document outside the declared roots publishes nothing")
expect("analyzed " + OUT_URI not in err,
       "the outside document is never analysed")
expect(any(r.get("method") == "window/logMessage" and "roots" in r["params"]["message"]
           for r in replies),
       "the refusal names the declared roots")
expect(any(r.get("method") == "window/logMessage" and "roots" in r["params"]["message"]
           and r["params"]["type"] == 3
           for r in replies),
       "the per-document refusal stays at Info (type 3)")
expect(any(p["params"]["uri"] == IN_URI and p["params"]["diagnostics"]
           for p in diag_notes),
       "the inside document still gets its diagnostics")
expect(len([r for r in replies if r.get("method") == "window/logMessage"]) == 1,
       "a didChange on the outside document adds no second logMessage (once-per-document)")
expect(junk == 0, "the gate run put only frames on stdout (junk=%d)" % junk)

# Block two: no root at all -- the gate is open by design, so single-file editing works.
replies, code, err, junk = run([frame(initialize(1)), frame(msgs[1]),
                                frame(opened(OUT_URI, BROKEN)),
                                frame(shutdown(2)), frame(exit_())])
expect("analyzed " + OUT_URI in err,
       "a rootless client still analyses the document")
expect(any(r.get("method") == "window/logMessage" and
           "no project roots" in r.get("params", {}).get("message", "")
           for r in replies),
       "a rootless client is told once that it runs unguarded")
expect(any(r.get("method") == "window/logMessage" and
           "no project roots" in r.get("params", {}).get("message", "") and
           r.get("params", {}).get("type") == 2
           for r in replies),
       "the rootless notice is a Warning (type 2), not Info")
rootless_notes = [r for r in replies if r.get("method") == "textDocument/publishDiagnostics"
                  and r["params"]["uri"] == OUT_URI]
expect(bool(rootless_notes) and
       any(d["severity"] == 1 for d in rootless_notes[-1]["params"]["diagnostics"]),
       "and publishes one Error diagnostic (%s)"
       % [d.get("severity") for d in (rootless_notes[-1]["params"]["diagnostics"]
                                      if rootless_notes else [])])
expect(junk == 0, "the rootless run put only frames on stdout (junk=%d)" % junk)

print("transcript: %d checks, %d failed" % (passed, len(fails)))
sys.exit(1 if fails else 0)
