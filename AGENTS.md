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
rather than inventing a synthetic trigger. To prove an assertion can fail, mutate one
production branch and require that named check to go FAIL; this found four assertions that
passed for unrelated reasons and one branch no input could ever reach. Do it after
committing, and revert per file — `git checkout -- .` restores from the index and will
silently undo work you have not committed yet. When a review or a probe contradicts a
commit message, correct the message in the next commit — the correction is the finding.

## Seed7 traps

Each of these cost a debugging cycle. Seed7 is not Python and will not warn you first.

- A `local` variable cannot be initialised from a parameter of the same function.
  Declare with a constant, then assign in `begin`.
- `key`, `len` and `line` are taken by the language and library. Choose other names.
  So is `sum` — and a result variable that collides with a library function is worse than a
  warning, the whole declaration silently fails (`DECL_FAILED` after a `NO_MATCH`).
- A `func` with a `result` clause **assigns** its result variable; Seed7 returns it
  implicitly. Writing `res := x; return res;` does not match at analysis time, and a bare
  `return` in a `proc` raises `PROC_EXPECTED`. `is return expr;` is the other correct form.
- Strings are `"...\"..."`. There are no single quotes, and `""` is not escaping.
  Tab inside a literal is `\9;`. A char literal cannot hold the escape character
  (`'\'` does not parse — the escape eats the closing quote): write `chr(92)` and name it.
  `doc_store.BACKSLASH` is that name.
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
  file repeats `$ include "seed7_05.s7i";` and the includes it uses. Subdirectories work
  (`include "features/hover.sd7"` resolves against `-l src`), which is how `src/features/`
  stays out of the dispatcher's way.
- There is no char-to-string conversion: `str(ch)`, `string(ch)` and `ch & ""` all fail to
  match. Slice the source text instead — `stri[i .. i]` — which is what `jsonw.sd7` does.
- A Seed7 array literal is `[]("a", "b")`. `("a","b","c")` does not match and `{...}` is a
  block, so a brace-form array declaration fails somewhere far away in the error tree.
- `x not in arr` does not parse when `x` is a struct-field select (`syms[i].sign not in
  shown`); `analysis.listed()` exists because of it.
- Declare before use: a `func` cannot call a helper defined later in the file, so the small
  total wrappers in `analysis.sd7` sit above the walker that uses them.
- Seed7's `and`/`or` short-circuit, but a long `or`/`and` chain of parenthesised
  comparisons can fail to *match* — split the predicate into small `const func boolean:`
  one-liners (see `doc_store.isAlpha`/`isDigit`/`nameChar`).
- A char literal cannot hold the escape character or a quote the way you expect: `'\'` does
  not parse. Use `chr(92)`/`chr(39)` and name them — `doc_store.BACKSLASH`/`SINGLE_QUOTE`.
  The quote character is written `'''` — open, the quote as content, close — and `''''` is
  the parse error ("Character literal exceeds source line"). Verify a spelling with `s7`
  before coding to it; two of this session's test fixtures were wrong because I guessed.

## Invariants — a violation is a defect, not a style preference

1. Only `src/analysis.sd7` imports `progs.s7i`. `grep -rn 'progs.s7i' src/` must show
   one line. Feature files receive `symRec` records; the temptation to read a `reference`
   directly is why this one is here.
2. Only `src/doc_store.sd7` converts LSP positions to string offsets.
3. Only `src/transport.sd7` owns UTF-8 byte widths: it holds the width table
   (`utf8CharLength`) and computes or consumes every outbound byte count.
   `src/doc_store.sd7` may consume a byte-valued column only to convert it into a
   character column (`charColumnForBytes`/`lspRangeBytes`), and never emits a byte count.
   `doc_store` includes `transport.sd7` to reach that one helper, which inverts the
   layering — a merge-time decision, not an accident: §2 of the design spec lists the
   intended module layout, and the helper's next consumer is `scan.sd7` in the milestone
   after this one, so the `src/utf8bytes.sd7` extraction belongs to the `scan.sd7` plan.
4. Only `src/*.sd7` and `src/features/*.sd7` build LSP response shapes; `analysis.sd7`
   returns Seed7-shaped data and knows nothing about LSP.
5. Capabilities are static in `InitializeResult`. No dynamic registration. And a
   capability is only advertised once its method is answered: `diagnosticProvider`
   shipped ahead of `textDocument/diagnostic`, which told pull-capable clients to
   ignore the push diagnostics we really did send.
6. Outbound text goes through `jsonw.sd7`. `str()` on a `jsonValue` is the `literal()`
   path that emits `\8364;` for `€` — invalid JSON.
   `grep -rn 'addStr(w, str(' --include='*.sd7' src/` must stay empty. The greps are
   recursive (`src/`, not `src/*.sd7`) because M3 put feature code in `src/features/`.

## Protocol decisions that are easy to undo by accident

- Position→token is **left-of-character**: a client hovering the identifier that starts at
  column `n` sends `character: n`, so the token is the one *ending* at `n`, not starting at
  it. `doc_store.wordAt` owns that rule; do not re-derive it in a feature.
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
  messages publish as `DiagnosticSeverity.Information`. Match that class by substring:
  those messages end in a quote character, so a suffix test never fires — and
  `errorType` cannot key it either, because EOF also appears *inside* the message of
  `EXPECTED_SYMBOL` (`";" expected found "END OF FILE"`), not as its own member.
- An empty buffer — the first state of a new file — reports `SYSTEM_MAIN_MISSING`, so
  that one kind is downgraded to Information too, keyed on `parseError.error`. Do not
  expect the member on a file that has its `$ include "seed7_05.s7i";` line: with the
  essential include present, a main-less program analyses clean.
- `parseError.columnNumber` is a 1-based **UTF-8 byte** offset from the line start — the
  scanner's *current position at raise time* (`IN_FILE_TELL()` minus the line start in
  Seed7's `src/error.c`), so it names the byte just **after** a token-level error's
  offending token, and only a mid-token raise like `ILLEGAL_STRING_ESCAPE` names a byte
  inside the token. `lspRange` takes a character column, so analyzer columns go through
  `lspRangeBytes` and nothing else does. Consequence: `[col, col+1]` marks the character
  *after* the token for `EXPECTED_SYMBOL` and the illegal-character class, and inside the
  escape for `ILLEGAL_STRING_ESCAPE`. Pinned by three checks in
  `tests/analysis_test.sd7`, each carrying the diagnostic count, kind, line and message: `Illegal string escape "\z"` reports column 26 both after
  `"ππ"` (the `z` there is the 24th character) and after one astral character (there it is
  the 23rd); and the first diagnostic on `    writeln(1) writeln(2);` — **with its
  four-space indent**, the byte arithmetic is not the same without it — is
  `EXPECTED_SYMBOL` at line 4 column 23, one byte past a `writeln` spanning bytes 16-22.
  Change the interpreter's convention and those checks go red.
- Column 0 is the *object-form* error path (`storePositionedErrorLine`), not "all
  semantic errors": `NO_MATCH`, `DECL_FAILED`, `REDECLARATION`, `PREVIOUS_DECLARATION`
  and `UNCLOSED_COMMENT` arrive with 0, and `UNCLOSED_COMMENT` carries the line the
  comment *opened*. Ask `lspRangeBytes` for an absurd column and let it clamp.
- `errorType` has 67 identifiers in the interpreter's C enum; the 14 catchable
  `EXCEPTION`s in `seed7_05.s7i:277-291` are a different set (15 names, one of them
  `OKAY_NO_ERROR`). Both counts are right; do not "reconcile" them.
- `#` is both the line-comment introducer and the radix marker of `16#beef`.
  `doc_store.isRadixHash` decides by context, and `codeText` is the only place that
  decides. `lib/aes.s7i` has 691 lines with based literals, so this is not theoretical.

## Do not "fix" these

- Analysis executes the analysed code. It is a property of using the interpreter as the
  parser, not a bug to route around — see the README's security section, which is the
  single source of truth for it. The M3 answer is a trust gate, not stderr scraping.
- A `.s7i` buffer is analysed through a synthetic driver that reads the file from disk,
  so unsaved library edits report stale diagnostics. Known, recorded as R-F10; it was
  scheduled for M3 and split into its own plan, so it is still open.
- The `-32603` containment net in `main.sd7` is still unreachable, for a narrower reason
  than before: the two reflection accessors this server actually calls, `getType` and
  `formalParams`, *do* raise `RANGE_ERROR` on real references (`resultVar` also raises but
  is never called), and `analysis.sd7` wraps each in a total (`safeType`, `paramsOf`), so
  nothing is left for the net to catch. Keep it. When you add a handler that can raise, add
  the check that reaches it — and never let the raise find stdout.

## Milestones

M1+M2 (base protocol, lifecycle, sync, diagnostics) are merged-ready. M3's five symbol
features (documentSymbol, definition, hover, completion, signatureHelp) are in on this
branch; the trust gate, the `.s7i` staleness fix (R-F10) and local-variable completion were
split out of it and remain open.

Masking already exists — `doc_store.codeText` blanks string literals, char literals,
`(* *)` and `#` comments, `wordAt` answers nothing inside masked text, and
`signature_help.callContextOf` counts arguments over it — so M4's `scan.sd7` is no longer
"does this position mean anything" but token *spans*: foldingRange, selectionRange and
semanticTokens, plus the extents and parameter specifiers reflection cannot give. The
reflection API yields declarations only, never use sites, which is why references and
rename stay M5.
