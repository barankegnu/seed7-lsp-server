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
expect(by_id.get(2, {}).get("error", {}).get("code") == -32601, "unimplemented hover -> -32601")
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
