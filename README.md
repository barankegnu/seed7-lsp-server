# seed7-lsp-server

An LSP server for the [SEED7](https://seed7.net) language, written in Seed7.
Requires a working `s7` interpreter and its standard library.

    make test          # 8 suites, 72 checks, no editor needed
    make server        # speak LSP on stdin/stdout

Run `s7 -q -l src src/main.sd7` as the server command.

## Security: opening a file runs its code

Seed7 evaluates constant expressions during **analysis**, and analysis is what a
language server does on every keystroke. So this server runs arbitrary Seed7 from the
document it is analysing, with your own user privileges — file writes, spawned
processes, sockets. `s7 -a` ("analyze only") is not a defence; it evaluates too, and
there is no interpreter switch to turn that off.

Treat opening an untrusted `.sd7` the way you would treat running it. Point this
server only at code you trust, and at a single project per editor window. A trust
gate (analyse only inside configured roots, or require an explicit acknowledgement at
`initialize`) is planned for M3, not implemented.

Startup also prints two `Authorization required, but no authorization protocol
specified` lines on some systems. Those come from the X11-linked Seed7 runtime, not
from this server; stderr is the server's log channel, so they are harmless.

* VS Code: `"seed7-lsp.runtime": "s7"`, `"seed7-lsp.args": ["-q", "-l", "<repo>/src", "<repo>/src/main.sd7"]`
* Emacs: `(use-package lsp-mode :config (add-to-list 'lsp-language-id-configuration '(seed7-mode . "seed7")))`
  then `(lsp-register-client (make-lsp-client :new-process (lsp--start-server '("s7" "-q" "-l" "src" "src/main.sd7")) :major-modes seed7-mode :server-id 'seed7-lsp))`
* Neovim: `require("lspconfig").server_config_for_language("seed7", "seeds")` — or
  simply `vim.lsp.start({ name = "seed7-lsp", cmd = { "s7", "-q", "-l", "src", "src/main.sd7" }, root_dir = vim.fs.dirname(...) })`
  in an autocmd for `FileType seed7`.

Implements: base protocol, lifecycle, full text sync, interpreter diagnostics.
Not yet: definition, hover, completion, signatureHelp, symbols, folding,
semantic tokens, references, rename, workspace symbols (see the spec's milestones M3-M6).
