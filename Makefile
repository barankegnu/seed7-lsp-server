S7      ?= s7
SRC     := src
TESTS   := jsonw

.PHONY: test server $(addprefix test-,$(TESTS))

test: $(addprefix test-,$(TESTS))

$(addprefix test-,$(TESTS)): test-%:
	@$(S7) -q -l $(SRC) tests/$*_test.sd7 || exit 1

server:
	@$(S7) -q -l $(SRC) $(SRC)/main.sd7
