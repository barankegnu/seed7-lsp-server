S7      ?= s7
SRC     := src
# A suite that fails to analyse prints nothing on stdout and still exits 0, so a recipe
# must grade the suite's own total line, never s7's status.
G        := grep -E
S7TOTAL  := '^[a-z_]+: [0-9]+ checks, 0 failed$$'
TESTS   := jsonw uris transport doc_store rpc analysis diagnostics doc_index features lsp_server

.PHONY: test server $(addprefix test-,$(TESTS)) transcript

test: $(addprefix test-,$(TESTS)) transcript

$(addprefix test-,$(TESTS)): test-%:
	@out=$$($(S7) -q -l $(SRC) tests/$*_test.sd7 2>&1); \
	printf '%s\n' "$$out"; \
	printf '%s\n' "$$out" | $(G) -q $(S7TOTAL)

transcript:
	@python3 tests/transcript.py

server:
	@$(S7) -q -l $(SRC) $(SRC)/main.sd7
