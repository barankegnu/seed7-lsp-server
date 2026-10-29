# seed7-lsp-server

An LSP 3.18 server for the [SEED7](https://seed7.net) language, written in Seed7.
It drives the real Seed7 analyzer rather than a paraphrase of it, so the diagnostics you
see are the ones `s7` itself would produce.

Requires a working `s7` on `PATH` plus its standard library; built and tested against
SEED7 5.4.10 on Linux. No `SEED7_LIBRARY` needed — the interpreter resolves its own
libraries.

    make test          # 21 suites, every one reporting 0 failed, no editor required
    make server        # speak LSP on stdin/stdout

## Security: opening a file runs its code

Seed7 evaluates constant expressions during **analysis**, and analysis is what a
language server does on every keystroke. So this server runs arbitrary Seed7 from the
document it is analysing, with your own user privileges — file writes, spawned
processes, sockets. `s7 -a` ("analyze only") is not a defence; it evaluates too, and
there is no interpreter switch to turn that off.

Compiling is not an escape either. The Seed7 compiler produces its program by running
*the same analyze phase* — `s7c` "uses the analyze phase of the interpreter to convert a
program to call-code" and then emits C to be built
([faq.htm#compile](https://seed7.net/faq.htm#compile)) — so there is no second, lazier
front end to point at a document, and no build flag that makes analysis inert.

Treat opening an untrusted `.sd7` the way you would treat running it: point this server
only at code you trust, and at one project per editor window. A trust gate now ships: the
server analyses only documents inside the `rootUri`/`workspaceFolders` a client declared at
`initialize`, and an untrusted `didOpen` sends no diagnostics notification and logs the reason
once. A client that declares no root runs unguarded by design — the single-file editing this
README recommends must not break — and is told so at `initialize`. The gate is a
*containment* control on top of the rule above, not a sandbox: analysis still executes
code inside the roots, `s7 -a` is not a defence, and compiling is not an escape. The
comparison is textual on decoded paths: `..` segments are not resolved and symlinks are
not followed, so a path that escapes by name still matches — canonicalising would need
filesystem access per document and would still not stop a symlink inside a root.

Startup may also print two `Authorization required, but no authorization protocol
specified` lines. Those come from the X11-linked Seed7 runtime, not from this server;
stderr is the server's log channel, so they are harmless.

## Running it

The server is one command, over stdio:

    s7 -q -l src src/main.sd7

Replace `src` with the absolute path to this checkout's `src` directory. Logs and
diagnostics of the server itself go to stderr; the LSP stream is stdout.

To run it compiled instead — same protocol, measured to build in about 7 s and to answer
`initialize`, `didOpen` and `shutdown` with only frames on stdout:

    make build && ./src/main

Do not add `-te`, or `-tefs`, to that build: it puts caught-exception traces on stdout, and
this server catches exceptions on the request path by design. `make build-debug` is the traced
variant, safe because it traces with `-tfs`; `make clean-build` removes the artifacts either one
leaves in `src/`. The flag sets and the measurements are in *Build — the two flag sets* in
`docs/seed7-cli.md`.

The two flag lines, for a compile by hand instead of through `make` — `s7c` takes no `-o`, so the
executable lands beside its source (`src/main`) and `profile_out` lands in the cwd:

    release: -O3 -flto -oc3 -w2
    debug:   -O3 -flto -oc3 -w2 -e -g-debug_c -p -tefs

The debug line is a probe you run by hand to find a crash, and it is the line as handed down by
`~/seed7/doc/s7c.1`. Do not serve it: its `-te` writes every **caught** exception to stdout, and
`rpc.sd7` catches exceptions on the request path deliberately, so measured on this tree the stream
began with 642 bytes of non-frame text before the first frame. The traced build that may serve is
this one, which is what `make build-debug` runs:

    -O3 -flto -oc3 -w2 -e -g-debug_c -p -tfs

* **Emacs (eglot)** — real API, works today:

      (add-to-list 'eglot-server-programs
                   '(seed7-mode ("/usr/local/bin/s7" "-q" "-l" "/abs/src" "/abs/src/main.sd7")))

* **Neovim** — built-in client, works today:

      vim.lsp.start({
        name = "seed7-lsp",
        cmd = { "s7", "-q", "-l", "/abs/src", "/abs/src/main.sd7" },
        root_dir = vim.fn.expand("%:p:h"),
      })

* **Emacs (lsp-mode)** or any other client that can launch a custom stdio server: use
  the same argv. No `languageId` filtering happens server-side today, so the client's
  language id is cosmetic.

* **VS Code** — no extension ships in this repository. You need a "custom language
  client" style extension to supply the command above; none of it is tested here, so
  consider VS Code unsupported until someone actually runs it.

## What works

Base protocol framing, lifecycle (`initialize`/`initialized`/`shutdown`/`exit`), full
text synchronisation (`didOpen`/`didChange`/`didClose`), and diagnostics from the
analyzer: deduplicated, landed on characters even when the line ahead of it holds
non-ASCII text, and with a based literal in the line no longer hiding what follows
it; whole-line where the analyzer reports no column, capped, and with
truncation-during-typing downgraded to Information instead of a wall of red. Error
handling is spec-shaped: `-32002` before initialize, `-32600` after shutdown, `-32700`
for a non-JSON body, `-32601` for unimplemented methods, and a fatal exit (status `2`) on
a frame whose `Content-Length` cannot be trusted.

On top of that, the symbol features, all read from the analyzer's own object table:
`documentSymbol` for the declarations in the open file, `definition` — including jumps
into the standard library, because reflection reports an absolute path and declaration
line for every library object — `hover`, which shows the reconstructed signature of every
overload plus the `(** … *)` comment the library author wrote, `completion` for
declarations and the base keywords, and `signatureHelp` with the active parameter counted
from the call site. Where a name exists both in the open file and in the library — overloading
a stdlib name is ordinary Seed7 — these answer about *your* declaration: reflection yields the
library's records first, so the server ranks the document's own ahead of them and the features
that truncate a list (definition's 20 locations, completion's 100 items, the semantic-token
class tables) re-rank in their own passes.

Cross-reference features, all answered by one occurrence pass over the open document:
`references` — every location of the symbol under the cursor inside that file, with exact
UTF-16 columns (the first ranges this server does not widen to whole lines), the declaration
included when asked and only when it is declared in this buffer; `prepareRename` and `rename`
for the same symbol, refusing rather than guessing — a library symbol, a keyword, a binding it
cannot prove, a scope it cannot fully see (a nested routine's locals are invisible to
reflection), a `.s7i` buffer while R-F10 stands, or a client that did not declare
`workspace.applyEdit`. A refusal is `null`, never an error, so editors grey the item out; a bad
new name is `-32602`. Rename is file-local by decision: it will not half-rename a project. A
symbol whose scope also holds the same spelling after a `.' — a record field, `w.counter` beside
a local `counter` — is refused rather than rewritten, because the field's declaration is a
different symbol the window does not hold; `references` keeps listing those tokens but says the
list may include a field.

Scanner-backed features: `foldingRange` for declaration bodies, control blocks, comments,
and include runs (no fold for a single-line construct); `selectionRange` enclosing by line
(a position in a region's leading whitespace still nests inside it); and `semanticTokens`
with seven name/literal types and no `keyword` or `parameter` class. The keyword gap is now
answerable rather than merely unsolved — `src/keywords.sd7`'s `CANNOT_BE_NAME` is a set the
interpreter itself certified (`tools/keyword_gate.sh` re-derives it and exits 1 on drift), where
the seven hand-written lists disagreed — but adding it would change a legend clients already
consume, so it is its own change, not a docs edit. The `parameter` gap stands: `paramsOf` returns
strings, so a parameter has no position to highlight.

Framing is byte-exact both ways: inbound `Content-Length` is counted in bytes (the interpreter's
`gets` counts characters, which silently desynced every body containing a non-ASCII character until
M5 fixed it), and `\ud83d\ude00`-style escapes are folded back into one character before they reach
the document store. Both had shipped unnoticed because the test harness escapes non-ASCII.

Requests stay silent inside a string literal, a char literal or a comment:
`scan.sd7`'s `maskOf` projects those regions — same length as the text, newlines preserved,
every non-code character a space — so a position inside `"..."` reports nothing rather
than the signature of some unrelated call — a real risk in files like `prg/calc7.sd7`, whose
continuation strings span lines, and in `lib/chartype.s7i`, where `{'"'}` opened a phantom
string in any rule that does not know char literals exist.

Symbol-feature ranges are line-based. Reflection reports a declaration's line and never
a column, so a definition range is the whole line. A symbol's *extent* (where it ends)
is not available from the analyzer at all. Where the analyzer reports a column, it counts
bytes and the server converts — see `doc_store.lspRangeBytes`. The function that still
uses this rule is `lspWholeLine`.

## What does not work yet

`workspace/symbol`, project-wide rename and anything else needing an index of files the
editor never opened (M6, unscheduled), nested and local `documentSymbol` hierarchy,
completion of local variables, pull diagnostics, formatting, `.s7i`
staleness (R-F10: an unsaved library edit reports a stale outline, hover and completion
as well as stale diagnostics, because a library is analysed through a driver that reads
the file back from disk, which also breaks the spec's rule that an open document must not
be read through its uri (and `rename`/`prepareRename` therefore refuse inside a `.s7i` buffer)),
`utf-8`/`utf-32` position encoding (the server announces `"positionEncoding":"utf-16"` in
`src/lsp_server.sd7`'s `capabilitiesJson` and honours no client preference), `workspace/configuration`, and
Windows. Asking for an unimplemented method returns `-32601 Method not found`, which
editors display as "no data" rather than as a failure — and a capability is advertised
only once its method is answered.

## Layout and further reading

`src/` is one module per responsibility — transport, JSON-RPC, JSON writing, document
store, the lexical scanner and its construct regions (`scan.sd7`, `blocks.sd7`), the code-point
width tables (`utf8bytes.sd7`), the occurrence index and binding resolution (`occurrences.sd7`), the
measured keyword gate (`keywords.sd7`, regenerated by `tools/keyword_gate.sh`), analysis,
diagnostics, dispatch, entry point —
with the LSP features themselves in `src/features/`, one file per method plus `kinds.sd7`
for the shared symbol/type mappings. `tests/` has one suite each, plus
`tests/transcript.py`, which drives the real process over real frames.
`tools/` holds the generators and gates that keep the docs honest — `keyword_gate.sh` (the refused-name set,
re-derived from the interpreter), `corpus_scan.sh` (the occurrence pass run over all 342 files the
scan is actually given — `lib/*.s7i` plus `prg/*.sd7`, which is fewer than every `*.sd7`/`*.s7i`
`find` recurses to, since `lib` holds another 51 `.s7i` below its top level), and the two the
suite runs: `project_graph.sh` and `agents_gate.sh`.

`docs/PROJECT_GRAPH.md` is that shape in one read — modules, includes, methods answered against
methods advertised, suites and the module each is named after. Regenerate with `make graph`.

- `AGENTS.md` — constraints for anyone editing this code: the Seed7 traps, the invariants, and
  the recipe for performance claims (profile a compiled, optimized build with `s7c -p -l src`
  and read `profile_out`; never `time` the interpreter. Every flag there is cited to the Seed7 FAQ
  in section *Seed7 traps*).

- `docs/superpowers/specs/` — held the design, its measurements, and its risk register. Deleted
  in `fca09be`, with no successor: `AGENTS.md` keeps the rules and `docs/seed7-cli.md` keeps the
  figures, citations and decision history.
- `docs/superpowers/plans/` — the task-by-task plans as they were executed; each describes the
  tree before it landed, so read its status line first.
