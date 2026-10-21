S7      ?= s7
S7C     ?= s7c
SRC     := src
# The two compiled builds. The release line is the one that may serve. The debug line as handed
# down ends in -tefs; every flag in it is documented in ~/seed7/doc/s7c.1 (`-t` takes the letters
# e f s, one per option, and the combination is theirs, not the man page's) -- but -te prints every
# CAUGHT exception to stdout, and rpc.sd7's atKey raises and catches INDEX_ERROR/ILLEGAL_ACTION on
# the request path by design, so a -te server writes non-frame bytes into the LSP stream. Bisected
# and measured; per-flag meanings and the evidence live in "Build -- the two flag sets" in
# docs/seed7-cli.md, so build-debug traces with -tfs instead.
RELEASE_FLAGS := -O3 -flto -oc3 -w2
DEBUG_FLAGS   := $(RELEASE_FLAGS) -e -g-debug_c -p -tfs
# A suite that fails to analyse prints nothing on stdout and still exits 0, so a recipe
# must grade the suite's own total line, never s7's status. The name class admits digits
# because src/utf8bytes.sd7 is a module named with one: with [a-z_]+ the recipe could
# never grade that suite, so a missing or failing utf8bytes suite would look like a
# passing run of the rest.
G        := grep -E
S7TOTAL  := '^[a-z0-9_]+: [0-9]+ checks, 0 failed$$'
TESTS   := jsonw uris utf8bytes scan occurrences keywords blocks folding selection_range semantic_tokens transport doc_store rpc analysis diagnostics doc_index features lsp_server
# Suites that are a shell script rather than an s7 program. There is ONE test-% rule below: with
# two same-stem pattern rules, which one matches depends on file order and on what already exists,
# so a suite can silently stop running while `make test` prints green lines (ledger R1).
TESTS_SH := agents graph

.PHONY: test graph server build build-debug clean-build $(addprefix test-,$(TESTS) $(TESTS_SH)) transcript

test: $(addprefix test-,$(TESTS) $(TESTS_SH)) transcript

# The suite file is resolved by convention -- tests/<name>_test.sd7, then tests/<name>_test.sh,
# then tools/<name>_gate.sh -- so adding a suite adds a name, never a rule.
$(addprefix test-,$(TESTS) $(TESTS_SH)): test-%:
	@f=tests/$*_test.sd7; [ -f "$$f" ] || f=tests/$*_test.sh; [ -f "$$f" ] || f=tools/$*_gate.sh; \
	 case "$$f" in *.sd7) out=$$($(S7) -q -l $(SRC) $$f 2>&1);; *) out=$$(sh $$f 2>&1);; esac; \
	 printf '%s\n' "$$out"; \
	 printf '%s\n' "$$out" | $(G) -q $(S7TOTAL)

transcript:
	@python3 tests/transcript.py

# The artifact is generated, committed, and compared against a fresh run by tests/graph_test.sh,
# so editing src/ without running this turns `make test` red. The run goes to a .tmp first: the
# generator writes the whole artifact on stdout and dies on a missing input, so a plain redirect
# would truncate docs/PROJECT_GRAPH.md before the failure and leave a half artifact behind. The
# `rm -f' is there because .gitignore holds no `*.tmp' pattern (only .tmp_versions/), so a leftover
# is an untracked file a broad `git add -A' would commit. The `exit 1' is load-bearing: `|| rm -f ...'
# alone swallows the generator's failure and makes the recipe SUCCEED, which un-does the atomicity.
# tests/graph_test.sh's leftover-tmp check trips the generator in a sandbox and requires all three:
# non-zero exit, no .tmp left, artifact byte-identical.
graph:
	@sh tools/project_graph.sh > docs/PROJECT_GRAPH.md.tmp && mv docs/PROJECT_GRAPH.md.tmp docs/PROJECT_GRAPH.md || { rm -f docs/PROJECT_GRAPH.md.tmp; exit 1; }

server:
	@$(S7) -q -l $(SRC) $(SRC)/main.sd7

# s7c has no -o, so the executable lands beside its source: src/main. Both that and the
# -g-debug_c temporary C that build-debug leaves (src/tmp_main.c, ~5 MB) are gitignored, and
# clean-build exists because `git status --porcelain -uall' must be empty after any build -- an
# untracked file also disqualifies the checkout as an isolated worktree, and a broad `git add -A'
# would otherwise commit a 5 MB generated file.
build:
	@$(S7C) $(RELEASE_FLAGS) -l $(SRC) $(SRC)/main.sd7
	@echo "built $(SRC)/main -- run it with ./$(SRC)/main"

# -p writes profile_out in the CURRENT directory when the program finishes, and -g-debug_c keeps
# the generated C beside the source, so this recipe says where both land rather than leaving the
# reader to look for them.
build-debug:
	@$(S7C) $(DEBUG_FLAGS) -l $(SRC) $(SRC)/main.sd7
	@echo "built $(SRC)/main (profiling: profile_out lands in the cwd on exit; $(SRC)/tmp_main.c stays)"

clean-build:
	@rm -f $(SRC)/main $(SRC)/tmp_*.c profile_out
	@echo "removed $(SRC)/main, $(SRC)/tmp_*.c and profile_out"
