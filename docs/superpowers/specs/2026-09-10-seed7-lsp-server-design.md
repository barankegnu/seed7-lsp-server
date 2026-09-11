# Seed7 LSP server — design

Date: 2026-09-10 · Status: for review · Spec: LSP 3.18 · Analysis engine: SEED7 5.4.x

## 1. Locked decisions

| Question | Decision |
|---|---|
| Purpose | A tool used daily on real Seed7 code. |
| Runtime dependency | **Requires a working `s7` + stdlib.** Full-fidelity analysis is worth the dependency. |
| Implementation | **Seed7 only, one process** (approach B). Deliberate: one language to maintain beats two, even though it means hand-owning LSP plumbing. |
| Client | Client-agnostic. Editors get launch snippets only; no extension code in this repo. |
| v1 | diagnostics, go-to-definition, hover, completion, signatureHelp, documentSymbol. |
| v1 cheap | foldingRange, selectionRange, semanticTokens. |
| Later | references, rename, `workspace/symbol`, workspace index, file watching. |
| Cut | formatting (Emacs already indents; nothing else is served by us owning it). |

Why the interpreter is not optional: Seed7's syntax is *declared*, not hard-coded — `include`, `if`, `for`, `::=` and operator precedences come from `$`-pragmas in `seed7_05.s7i`, executed by the parser. Only the analyzer knows what Seed7 is, and only its overload resolution can produce `Match for ... failed`.

## 2. Architecture

One long-lived process: `s7 -q server.sd7`. stdin/stdout is LSP; stderr is logs. `server.sd7` is the only entry point.

```
server.sd7        initialize, capability negotiation, dispatch, shutdown/exit
transport.sd7     Content-Length framing; only file that counts bytes
rpc.sd7           JSON-RPC objects, ids, error codes, cancellation
lsp_types.sd7     LSP shapes we use, as Seed7 structs + declare_json_serde
doc_store.sd7     uri -> {version, text, line table}; only position converter
scan.sd7          Seed7 lexical scanner (tokens, comments, blocks, token-at-offset)
analysis.sd7      only file allowed to include "progs.s7i"
doc_index.sd7     (** ... *) hover prose, keyed by lib + line
features/         diagnostics, definition, hover, signature_help, completion,
                  document_symbol, folding, semantic_tokens, selection_range
tests/            per-module assert programs + golden transcript runner
```

Invariants — a violation of any of these is a defect, not a style preference:

1. Only `analysis.sd7` imports `progs.s7i`.
2. Only `doc_store.sd7` converts LSP positions to string offsets.
3. Only `transport.sd7` computes or consumes byte lengths.
4. Only `features/*.sd7` build LSP responses; `analysis.sd7` returns Seed7-shaped data and knows nothing about LSP.
5. No dynamic capability registration; everything is advertised statically in `InitializeResult`.

## 3. Contracts

### 3.1 Transport (verified)

Use `utf8.s7i`'s `STD_UTF8_IN` / `STD_UTF8_OUT` / `STD_UTF8_ERR`. Plain `write(STD_OUT, ...)` raises `RANGE_ERROR` on non-ASCII in a C locale, so the non-UTF8 std files are unusable for payload.

- Headers: `getln(STD_UTF8_IN)` yields header lines with `\r\n` already stripped; an empty line terminates the header block.
- Body: `gets(STD_UTF8_IN, n)` counts **bytes**, so `n` is `Content-Length` verbatim; a 104-byte body with multibyte URIs returns 97 characters, correctly decoded.
- Outbound: `Content-Length` must be the UTF-8 byte length of the payload, which Seed7's `length()` does not give (it counts characters). `transport.sd7` provides `utf8Length(stri)` — 1/2/3/4 bytes per code point by `ord(c)` thresholds — and writes `"Content-Length: " <& utf8Length(payload) <& "\r\n\r\n" <& payload` to `STD_UTF8_OUT` then flushes.

### 3.2 JSON (verified, one trap)

- Inbound: `readJson(body)`, values via `string(v)`, `integer(str(v))`, `v["k"]`. Never `str(v)` on a value that may be a `jsonString`; `jsonNumber`'s `str(v)` is its digits and is safe.
- Outbound: `declare_json_serde(Type)` + `toJson(value)`.
- **Trap:** `json.s7i`'s `str(jsonValue)`/`str(jsonString)` serialise strings with Seed7's `literal()`, which emits `\8364;` for `€` — not valid JSON. `json_serde.s7i`'s `toJson` is correct (raw UTF-8, `\t`, `\n`, `\"`, `\\`). Every outbound frame therefore goes through `toJson` on a typed struct.
- Missing/`jsonValue`-typed keys raise (`RANGE_ERROR`/`INDEX_ERROR`/`SIZE_ERROR`), so all key access is either guarded by `succeeds`/`in` or inside the handler's `exception` block.

### 3.3 Positions

- Negotiate `positionEncoding`; honour `utf-16` (mandatory in all clients, our default) and `utf-8` when offered. `doc_store.sd7` owns the three-way map: LSP (line, character) ↔ Seed7 character index ↔ byte offset, backed by a per-document line-start table rebuilt on `didChange`.
- 0-based line/character in, 1-based `lineNumber`/`columnNumber` from `getError` out.
- A character value past the line length clamps to the line length. `\r|\n` positions are never emitted.
- Position→token is left-of-character. LSP 3.18 ("Hover Request"): *"the client typically
  sends position n (the position before the character)"*. `doc_store.wordAt` resolves the
  token **ending** at the position and falls back to the one starting there; completion uses
  the same function and truncates its result at the cursor.

### 3.4 Lifecycle

`initialize` → `InitializeResult{capabilities, serverInfo}` → `initialized` → work → `shutdown` (answer `null`, refuse later requests with `InvalidRequest`) → `exit` (status 0 if shutdown was seen, else 1). Any request before `initialize` errors with `-32002`; notifications are dropped except `exit`. During `initialize` only `window/showMessage`, `window/logMessage`, `telemetry/event`, `window/showMessageRequest` and `$/progress` on the client's token may be sent.

### 3.5 Synchronisation

`textDocumentSync = { openClose: true, change: Full }`. Full sync is not laziness, it is the cheaper correct choice: one `parseStri` of a real program costs 20–45 ms, so a rope buys nothing and incremental `didChange` ranges would be a second position bug surface.

## 4. Analysis lifecycle

For each `didOpen`/`didChange` of a `.sd7`/`.s7i`:

1. Take the newest version only. The loop is single-threaded, so an obsolete version is simply never reached.
2. `prog := parseStri(text, parseOptions.value, libraryDirs)`. `libraryDirs` comes from settings, then cwd, then `SEED7_LIBRARY`; the interpreter's own `../lib` fallback stays untouched.
3. Read diagnostics with `errorCount` + `getError(i)` → `{error, fileName, lineNumber, columnNumber, message, errorLine}`. Then let `prog` go.
4. Mapping rules:
   - `columnNumber = 0` (all semantic errors) → range spans the whole line; a syntax error gets `[col, col+1]` of the offending token start.
   - Deduplicate on `(line, column, message)`. A single missing terminator produced 13 raw errors.
   - Messages containing `END OF FILE` are downgraded to `DiagnosticSeverity.Information` when the document does not end in a complete program. While typing, an unterminated buffer is the normal state, not an error worth red squiggles.
   - Publish at most 100, ordered by line.
5. Pull diagnostics (`textDocument/diagnostic`) is **not advertised and not handled**;
the capability shipped in error during M2 and is removed until the handler exists. When
it lands, it goes behind the client capability and both paths call one function.

`.s7i` buffers: a library file is not analysable alone, so `analysis.sd7` parses the synthetic driver

```
$ include "seed7_05.s7i";
  include "<absolute path of buffer>";
```

as `s7xref.sd7` does, and reports diagnostics against the real file by dropping the 2 prefix lines and remapping paths. The driver's own `globalObjects` are still usable for symbols because `file(obj)`/`line(obj)` name the real file.

Crash containment: an uncaught exception kills the process (observed, and once silently). Every request handler runs inside

```
block  <handler>
exception
  catch MEMORY_ERROR: ...  catch NUMERIC_ERROR: ...  catch OVERFLOW_ERROR: ...
  catch INDEX_ERROR: ...   catch RANGE_ERROR: ...    catch FILE_ERROR: ...
  catch DATABASE_ERROR: ... catch GRAPHIC_ERROR: ... catch ASSERTION_ERROR: ...
end block;
```

which converts a crash into a JSON-RPC internal error plus a stderr line, and a live
server. Since every accessor is total, no crafted input currently reaches this net; it
stays as defence in depth and is deliberately **not** claimed as test coverage. The catchable set is fixed by `seed7_05.s7i:277-291`: MEMORY_ERROR,
ASSERTION_ERROR, NUMERIC_ERROR, OVERFLOW_ERROR, RANGE_ERROR, INDEX_ERROR, FILE_ERROR,
DATABASE_ERROR, GRAPHIC_ERROR, ILLEGAL_ACTION, CREATE_ERROR, DESTROY_ERROR, COPY_ERROR,
IN_ERROR. There is no `SIZE_ERROR` and no catch-all clause, so `ILLEGAL_ACTION` must be
listed explicitly — it is what `string(jsonValue)` raises on a non-string value.

Caching: none. `ponytail:` the ceiling is a re-parse per keystroke-debounce at ~25 ms; upgrade path is one cached `program` per document version if typing ever measurably lags.

## 5. Where each feature's data comes from

| Feature | Source | Known gap |
|---|---|---|
| diagnostics | `errorCount` / `getError` | semantic errors carry no column (§4.4) — **realised** |
| documentSymbol | `globalObjects(prog)` filtered by `file(obj)` | **realised, with two corrections:** a buffer's own declarations report `file = "STRING"` (so the filter is `path OR "STRING"`), and only globals are listed, so there is no hierarchy and `selectionRange == range` |
| definition | **not `syobject`** — it returns a `SYMBOLOBJECT` whose `file` is `"?"`, so it can never name a file. Scans `globalObjects` by name instead | **realised:** `Location[]` over all overloads, deduped on `(file, line)`, capped at 20; range is the whole declaration line |
| hover | v1 realised: every overload's reconstructed signature + `doc_index` prose (`proseForText` when the declaration is in the buffer) | v2 (`match(prog, expr)` for the exact overload the cursor is in) is still unbuilt — v1 turned out to be good enough without it |
| signatureHelp | candidates by name from `globalObjects`; active parameter counted by walking back to the owning `(` | **realised** for the common case: the walk is character-local, so a comma inside `"..."` counts (pinned by a test); `match` disambiguation still unbuilt |
| completion | `globalObjects` filtered by prefix and `category` → `CompletionItemKind`, plus a copied keyword list | **locals still missing:** the spec's "enclosing function found by line range" was dropped rather than guessed at; it needs its own short plan |
| folding / selectionRange / semanticTokens | `scan.sd7` only, no interpreter | ours to maintain |
| references / rename | **no source in the reflection API** | needs an occurrence index over `scan.sd7` tokens; that is the "later" milestone |

`str(reference)` returns a bare name. Signatures are reconstructed in `analysis.sd7` from `category` + `formalParams` + `getType` + `resultVar` (~50 lines) and are the single source for hover, completion detail, and signatureHelp.

Hover prose comes from the `(** ... *)` comment immediately preceding a declaration in a `.s7i`, read lazily by `doc_index.sd7`. `Seed7Home/libraries/*.htm` has the same text but no per-function anchors, so it is not a usable data source; linking to `seed7.net` in hover is acceptable alongside prose.

## 6. Errors, config, logging

- Protocol errors from `rpc.sd7`: `-32700` for a body that is not JSON (id `null`),
  `-32600` for a request after `shutdown`, `-32601` for an unknown method, `-32603` for
  an unexpected exception inside a handler, `-32002` for traffic before `initialize`.
- Framing errors are separated by recoverability: a header block with no
  `Content-Length` is logged and reading continues; an unparsable, negative, or
  over-limit (`MAX_FRAME_BYTES` = 64 MiB) `Content-Length` makes the frame's end
  unknowable, so it is logged, the read loop stops, and the process exits **2** —
  desyncing silently would corrupt every later message. Never write anything but
  frames to stdout: an uncaught Seed7 exception prints to stdout and pollutes the
  channel.
- Missing/unusable `s7`, or an analysis failure that is not our bug: one `window/showMessage` Error at startup, then `window/logMessage` only. The server never dies because the toolchain is broken.
- Settings via `workspace/configuration` (client capability permitting) with `initializationOptions` fallback: `seed7.interpreterPath`, `seed7.libraryPaths[]`, `seed7.maxDiagnostics` (100), `seed7.logLevel`.
- Logging goes to stderr, level-gated; never to stdout.

## 7. Testing

No editor is required to test any of this, which is the point of the module split.

- `tests/<module>_test.sd7` — assert-based unit checks, run by `make test`, printing `ok`/`FAIL` and exiting non-zero on failure. Coverage where the logic is: `utf8Length` (ascii/latin/CJK/emoji boundaries), `doc_store` position round-trips including astral characters and CRLF, `scan` on nested `(* (* *) *)`, `#` comments, string/char escapes, radix numbers, `$`/`#` pragma lines; diagnostics mapping (dedupe, col=0, EOF downgrade, cap).
- `tests/transcript.py` — golden runner (python3, so no child-process plumbing in
  Seed7; the product itself stays Seed7-only): feed a scripted frame stream (initialize → didOpen → didChange → hover/definition/completion → shutdown → exit) through `transport.sd7`+`rpc.sd7`+dispatch, compare normalised JSON to `tests/golden/*.json`. This is the conformance harness every client-facing change must pass.
- `tests/programs/` — tiny `.sd7`/`.s7i` fixtures with expected diagnostics, including a truncated file and one with a deliberate type error.
- One explicit check that `str()` never appears in serialization paths, so the §3.2 trap cannot regress.

## 8. Milestones, each with an exit test

| | Deliverable | Exit criterion |
|---|---|---|
| M0 | risk spikes | done — §3/§4/§5 above are measurements, not assumptions |
| M1 | transport + rpc + lifecycle + doc store | transcript: `initialize` answers with our capabilities; unknown method → `-32601`; request before initialize → `-32002`; `shutdown`/`exit` codes correct |
| M2 | diagnostics | `didOpen` of a broken file publishes the expected diagnostics; a truncated file publishes none at Error severity |
| M3 | documentSymbol + definition | both work on a file that uses the stdlib, and on a `.s7i` buffer via the driver wrapper. **Merged on `m3`, except the trust gate and R-F10 (split to their own plans), and local-variable completion (follows).** |
| M4 | hover + signatureHelp + completion | signature text matches the declaration in the `.s7i`; `(** *)` prose appears in hover |
| M5 | folding + selectionRange + semanticTokens | scanner-only, no interpreter involved |
| M6 | occurrence index → references, rename, workspace/symbol | rename in a 2-file project updates both |

## 9. Risks

0. **Analysis executes the analysed code (accept, then gate).** Seed7 folds constant
   expressions at analysis time, so `parseStri` runs user code from the buffer with the
   user's privileges — proven: a buffer whose `const` initializer opens a file created
   it under `s7 -a` and under `parseFile`, with 0 errors. There is no interpreter flag
   against it. This is inherent to decisions (a) and B, must be documented at the top of
   the README, and wants a trust gate in M3 (configured roots or an explicit
   `initializationOptions` acknowledgement). Cost of ignoring it: "open a cloned repo"
   becomes "execute a cloned repo".
1. **Long-session memory.** Each analysis allocates a full `program`. Refcount destruction should make this a non-issue, but it is unmeasured over hours. Mitigation: `s7 -a` on a loop while watching RSS is an afternoon; if it grows, restart-on-idle is honest and invisible to the client.
2. **Version skew with the interpreter.** `getError` fields and `errorType` names are the interface we depend on. Pinning a minimum 5.4.x and reporting the interpreter version in `serverInfo` makes mismatches visible instead of mysterious.
3. **`globalObjects` is global to the program**, thousands of entries; per-keystroke filtering must stay cheap. Measure before optimising; a name-prefix hash is the obvious fix.
4. **`scan.sd7` correctness** decides semanticTokens, folding, and the later reference index. It is the largest genuinely new code in the plan and the part `seed7-mode.el`'s regexes most directly inform.
5. **Windows untested.** Seed7 builds there; `utf8File` and `getln` framing should follow, but nobody has tried.

## 10. Seed7 language notes (learned the slow way — keep them here)

No single-quoted strings (only `"...\"..."`). `key` is reserved. Tab in a literal is `\9;`, not `\t`. `<&` appends to output and takes any type; `&` concatenates strings and will not accept an `integer` — use `str(n)`. `startsWith`, not `beginsWith`; `length`, not `strlen`; `integer(stri)` to parse. `block ... exception catch E: ...; end block;` is the try form. `s7` writes analysis errors to **stderr and still exits 0**, which is why diagnostics come from `getError` and never from scraping.
