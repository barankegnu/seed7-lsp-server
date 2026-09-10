# AGENTS.md

Work here as a careful maintainer of a language server, not an author of Seed7
tutorials. This file holds what no config confesses. The layout is `ls src`, the
commands are in the `Makefile`, and the design authority is
`docs/superpowers/specs/2026-09-10-seed7-lsp-server-design.md` — read it before
changing behaviour, since the plan argues from it and conflicts resolve in its favour.

## Every change

Red first. Write the check, run it, confirm it fails for the reason you claim, then
implement. `make test` before and after. A check that cannot fail is worse than no
check: when a safety net becomes unreachable from real input, delete the assertion
rather than inventing a synthetic trigger. When a review or a probe contradicts a
commit message, correct the message in the next commit — the correction is the finding.

## Seed7 traps

Each of these cost a debugging cycle. Seed7 is not Python and will not warn you first.

- A `local` variable cannot be initialised from a parameter of the same function.
  Declare with a constant, then assign in `begin`.
- `key`, `len` and `line` are taken by the language and library. Choose other names.
- Strings are `"...\"..."`. There are no single quotes, and `""` is not escaping.
  Tab inside a literal is `\9;`.
- At statement level `<&` writes to the output stream; assignment is `&:=`. Worse,
  `A <& B < C` parses as a *comparison* and quietly yields `FALSE` — which is how a
  capabilities payload once shipped `{"capabilities":FALSE}`. Compose JSON with
  `jsonw.sd7`, never by concatenation.
- `&` concatenates strings and rejects an integer; use `str(n)`. `startsWith`, not
  `beginsWith`; `length`, not `strlen`; `pos(a, b) <> 0` for containment;
  `integer(stri)` and `integer(stri, base)` to parse.
- The catchable exceptions are the 14 in `seed7_05.s7i:277-291`. `SIZE_ERROR` does not
  exist. `string(jsonValue)` on a non-string raises `ILLEGAL_ACTION`, so switch on
  `category(v)` instead of catching.
- `hash [k] v` needs a named type: `const type: h is hash [k] v;`, empty value
  `h.EMPTY_HASH`, removal `excl(h, key)`, assignment `h @:= [k] v`.
- A file that defines `main` cannot be included by a test (redeclaration). That is why
  `main.sd7` and `lsp_server.sd7` are separate files.
- `s7` reports analysis errors on stderr **and exits 0**; uncaught exceptions print to
  **stdout** and exit 1. Never judge a run by its status code, and never let an
  exception reach stdout — it corrupts the protocol channel.
- `include` of our own modules needs `-l src`. Seed7 has no module system, so every
  file repeats `$ include "seed7_05.s7i";` and the includes it uses.

## Invariants — a violation is a defect, not a style preference

1. Only `src/analysis.sd7` imports `progs.s7i`. `grep -rn 'progs.s7i' src/` must show
   one line.
2. Only `src/doc_store.sd7` converts LSP positions to string offsets.
3. Only `src/transport.sd7` computes or consumes byte lengths.
4. Only `src/*.sd7` feature code builds LSP response shapes; `analysis.sd7` returns
   Seed7-shaped data and knows nothing about LSP.
5. Capabilities are static in `InitializeResult`. No dynamic registration.
6. Outbound text goes through `jsonw.sd7`. `str()` on a `jsonValue` is the `literal()`
   path that emits `\8364;` for `€` — invalid JSON. `grep -n 'addStr(w, str(' src/*.sd7`
   must stay empty.

## Protocol decisions that are easy to undo by accident

- Positions are 0-based line/character in **UTF-16 code units**; `utf8.s7i`'s
  `STD_UTF8_IN/OUT/ERR` are mandatory (plain `STD_OUT` raises `RANGE_ERROR` on
  non-ASCII), and `Content-Length` is the **byte** count while `length()` counts
  characters.
- An absent `Content-Length` logs and keeps reading. An unparsable, negative, or
  over-`MAX_FRAME_BYTES` value makes the frame's end unknowable: log, stop reading,
  exit **2**. Recovering a desynced byte-counted stream is not possible.
- `-32700` with a `null` id for a non-JSON body; `-32600` for a request after
  `shutdown`; `-32002` for traffic before `initialize`; `-32601` for an unknown
  request, and silence for an unknown notification.
- Full text sync: the **last** `contentChanges` element holds the whole text.
- A truncated buffer is the normal state while typing, so `END OF FILE`-class analyzer
  messages publish as `DiagnosticSeverity.Information`. Match by substring: those
  messages end in a quote character, so a suffix test never fires.
- Semantic errors arrive with `columnNumber = 0`. Ask `lspRange` for an absurd column
  and let it clamp, rather than adding a second position function.

## Do not "fix" these

- Analysis executes the analysed code. It is a property of using the interpreter as the
  parser, not a bug to route around — see the README's security section, which is the
  single source of truth for it. The M3 answer is a trust gate, not stderr scraping.
- A `.s7i` buffer is analysed through a synthetic driver that reads the file from disk,
  so unsaved library edits report stale diagnostics. Known, recorded as R-F10, M3 work.
- The `-32603` containment net in `main.sd7` is currently unreachable because every
  accessor is total. Keep it. When you add a handler that can raise, add the check that
  reaches it.

## Milestones

M1+M2 (base protocol, lifecycle, sync, diagnostics) are merged-ready on this branch.
M3 is definition, hover, completion, signatureHelp, documentSymbol, plus the trust gate
and the `.s7i` staleness fix. M4 folding/selectionRange/semanticTokens need `scan.sd7`,
which does not exist yet — the reflection API yields declarations only, never use sites,
and that is also why references and rename are M6.
