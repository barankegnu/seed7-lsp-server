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
expect(any(r.get("error", {}).get("code") == -32603 for r in replies),
       "malformed frame answered with an internal error")
expect("handler failed" in err, "the failure is logged to stderr, not swallowed")

print("transcript: %d checks, %d failed" % (passed, len(fails)))
sys.exit(1 if fails else 0)
