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

# --- M3: hover on a symbol declared in the buffer, and an unimplemented method ---
replies, code, err, junk = run([
    frame(msgs[0]), frame(msgs[1]),
    frame({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params":
           {"textDocument": {"uri": "file:///tmp/tt_syms.sd7", "languageId": "seed7",
                             "version": 1, "text": SYMS}}}),
    # line 31 is `    writeln(totalSize(prototype, 2));`; character 16 is inside
    # "totalSize", so hover must report the func declared in this buffer.
    frame({"jsonrpc": "2.0", "id": 40, "method": "textDocument/hover", "params":
           {"textDocument": {"uri": "file:///tmp/tt_syms.sd7"},
            "position": {"line": 31, "character": 16}}}),
    frame({"jsonrpc": "2.0", "id": 41, "method": "textDocument/references", "params":
           {"textDocument": {"uri": "file:///tmp/tt_syms.sd7"},
            "position": {"line": 31, "character": 24}}}),
    frame({"jsonrpc": "2.0", "id": 42, "method": "shutdown"}),
    frame({"jsonrpc": "2.0", "method": "exit"}),
])
by_id = {r.get("id"): r for r in replies if "id" in r}
hv = (by_id.get(40, {}).get("result") or {}).get("contents", {}).get("value", "")
expect("func integer: totalSize" in hv, "hover on a buffer symbol shows its signature (%r)" % hv)
expect(hv.startswith("```seed7"), "hover body is a seed7 fence (%r)" % hv[:12])
expect(by_id.get(41, {}).get("error", {}).get("code") == -32601,
       "references is still unimplemented -> -32601")

# --- M3: completion after a typed prefix ---
COMP_TEXT = SYMS + "\nconst integer: totMarker is 1;\n"
COMP_LINE = COMP_TEXT.split("\n").index("const integer: totMarker is 1;")
COMP_CHAR = COMP_TEXT.split("\n")[COMP_LINE].index("totMarker") + 3   # "tot" typed
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
expect("totMarker" in labels and "totalSize" in labels,
       "completion offers the prefix matches, got %s" % labels[:6])
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

print("transcript: %d checks, %d failed" % (passed, len(fails)))
sys.exit(1 if fails else 0)
