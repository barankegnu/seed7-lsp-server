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
                   ("oversized",   b"Content-Length: 999999999")]:
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

print("transcript: %d checks, %d failed" % (passed, len(fails)))
sys.exit(1 if fails else 0)
