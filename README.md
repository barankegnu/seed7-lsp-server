# seed7-lsp-server

An LSP server for the [SEED7](https://seed7.net) language, written in Seed7.
Requires a working `s7` interpreter and its standard library.

    make test          # 8 suites, 66 checks, no editor needed
    make server        # speak LSP on stdin/stdout

Run `s7 -q -l src src/main.sd7` as the server command.

* VS Code: `"seed7-lsp.runtime": "s7"`, `"seed7-lsp.args": ["-q", "-l", "<repo>/src", "<repo>/src/main.sd7"]`
* Emacs: `(use-package lsp-mode :config (add-to-list 'lsp-language-id-configuration '(seed7-mode . "seed7")))`
  then `(lsp-register-client (make-lsp-client :new-process (lsp--start-server '("s7" "-q" "-l" "src" "src/main.sd7")) :major-modes seed7-mode :server-id 'seed7-lsp))`
* Neovim: `require("lspconfig").server_config_for_language("seed7", "seeds")` — or
  simply `vim.lsp.start({ name = "seed7-lsp", cmd = { "s7", "-q", "-l", "src", "src/main.sd7" }, root_dir = vim.fs.dirname(...) })`
  in an autocmd for `FileType seed7`.

Implements: base protocol, lifecycle, full text sync, interpreter diagnostics.
Not yet: definition, hover, completion, signatureHelp, symbols, folding,
semantic tokens, references, rename, workspace symbols (see the spec's milestones M3-M6).
