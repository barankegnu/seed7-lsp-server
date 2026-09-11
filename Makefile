S7      ?= s7
SRC     := src
TESTS   := jsonw uris transport doc_store rpc analysis diagnostics doc_index lsp_server

.PHONY: test server $(addprefix test-,$(TESTS)) transcript

test: $(addprefix test-,$(TESTS)) transcript

$(addprefix test-,$(TESTS)): test-%:
	@$(S7) -q -l $(SRC) tests/$*_test.sd7 || exit 1

transcript:
	@python3 tests/transcript.py

server:
	@$(S7) -q -l $(SRC) $(SRC)/main.sd7
