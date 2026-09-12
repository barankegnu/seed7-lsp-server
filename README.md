# seed7-lsp-server

An LSP 3.18 server for the [SEED7](https://seed7.net) language, written in Seed7.
It drives the real Seed7 analyzer rather than a paraphrase of it, so the diagnostics you
see are the ones `s7` itself would produce.

Requires a working `s7` on `PATH` plus its standard library; built and tested against
SEED7 5.4.10 on Linux. No `SEED7_LIBRARY` needed — the interpreter resolves its own
libraries.

    make test          # 10 suites + transcript, 223 checks, no editor required
    make server        # speak LSP on stdin/stdout

## Security: opening a file runs its code

Seed7 evaluates constant expressions during **analysis**, and analysis is what a
language server does on every keystroke. So this server runs arbitrary Seed7 from the
document it is analysing, with your own user privileges — file writes, spawned
processes, sockets. `s7 -a` ("analyze only") is not a defence; it evaluates too, and
there is no interpreter switch to turn that off.

Treat opening an untrusted `.sd7` the way you would treat running it: point this server
only at code you trust, and at one project per editor window. A trust gate (analyse only
inside configured roots, or require an explicit acknowledgement at `initialize`) is
planned for M3 and **not implemented**.

Startup may also print two `Authorization required, but no authorization protocol
specified` lines. Those come from the X11-linked Seed7 runtime, not from this server;
stderr is the server's log channel, so they are harmless.

## Running it

The server is one command, over stdio:

    s7 -q -l src src/main.sd7

Replace `src` with the absolute path to this checkout's `src` directory. Logs and
diagnostics of the server itself go to stderr; the LSP stream is stdout.

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
analyzer: deduplicated, whole-line where the analyzer reports no column, capped, and with
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
from the call site.

Requests stay silent inside a string literal, a char literal or a comment:
`doc_store.codeText` masks those regions, so a position inside `"..."` reports nothing rather
than the signature of some unrelated call — a real risk in files like `prg/calc7.sd7`, whose
continuation strings span lines, and in `lib/chartype.s7i`, where `{'"'}` opened a phantom
string in any rule that does not know char literals exist.

Ranges are line-based. Reflection reports a declaration's line and never a column, so a
definition range is the whole line and `selectionRange` equals `range`. A symbol's
*extent* (where it ends) is not available from the analyzer at all.

## What does not work yet

`references` and rename (the reflection API yields declarations only, never use sites),
`workspace/symbol`, folding ranges, selection ranges, semantic tokens, `documentSymbol`
hierarchy for nested and local declarations, completion of local variables, pull
diagnostics, formatting, the trust gate, `.s7i` staleness (R-F10: an unsaved library edit reports a stale outline, hover
and completion as well as stale diagnostics, because a library is analysed through a driver
that reads the file back from disk, not from the editor buffer), `utf-8` position negotiation, `workspace/configuration`, and Windows. Asking
for an unimplemented method returns `-32601 Method not found`, which editors display as
"no data" rather than as a failure — and a capability is advertised only once its method
is answered.

## Layout and further reading

`src/` is one module per responsibility — transport, JSON-RPC, JSON writing, document
store, analysis, diagnostics, dispatch, entry point — and `tests/` has one suite each,
plus `tests/transcript.py`, which drives the real process over real frames.

- `AGENTS.md` — constraints for anyone editing this code, including the Seed7 traps.
- `docs/superpowers/specs/` — the design, its measurements, and its risk register.
- `docs/superpowers/plans/` — the task-by-task plan this branch implements.
