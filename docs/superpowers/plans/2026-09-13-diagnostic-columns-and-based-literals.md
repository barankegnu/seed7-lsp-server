# Diagnostic Columns and Based Literals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every range we publish land on the character the user means, and stop a based integer literal from hiding the rest of its line.

**Architecture:** Two independent fixes in the position/lexical seam. `columnNumber` from the Seed7 analyzer is a 1-based **UTF-8 byte** offset, so `doc_store.sd7` gains the byte→character mapping (it is the only module allowed to convert positions) fed by one new byte-width helper in `transport.sd7` (the only module allowed to count bytes). Separately, `doc_store.codeText`'s single state machine learns that `#` between a digit and an extended digit is a radix marker, not a line comment — which fixes hover, completion, definition and signatureHelp together, because all four read through `codeText`.

**Tech Stack:** Seed7 (`s7` 5.4.10) for the server; `python3` for the golden transcript runner; `make` for the suites. No other dependency.

**Spec:** `docs/superpowers/specs/2026-09-10-seed7-lsp-server-design.md` (§3.3 positions, §4.4 diagnostic mapping). Findings behind this plan are cited in `AGENTS.md` and §"Where the numbers come from" at the end.

**Worktree:** Execute in `/home/username/seed7-lsp-server/.worktrees/fix/positions-and-based-literals` (branch `fix/positions-and-based-literals`, from `f56ac31`). Baseline verified: `make test` exits 0 — 223 unit checks + 45 transcript checks, 0 failures.

## Global Constraints

- Run everything from the worktree root. Suites: `make test`, `make test-transport`, `make test-doc_store`, `make test-diagnostics`, `make transcript`. All must stay green.
- Invariant 2: **only `src/doc_store.sd7` converts LSP positions to string offsets.** Do not add a second position function and do not change `lspRange`'s signature or its character-based meaning.
- Invariant 3: **only `src/transport.sd7` computes or consumes byte lengths.** The UTF-8 code-point width table lives there; `doc_store.sd7` imports it.
- Red first: write the check, run it, confirm it fails **for the reason named in this plan**, then implement. A check that cannot fail is worse than no check.
- Mutation proof is part of the task, not optional: after the commit, mutate the one named production branch, require the one named check to go `FAIL`, then revert **that file only** with `git checkout -- <file>`. Never `git checkout -- .` (it restores from the index and silently undoes uncommitted work).
- Never let an exception reach stdout: it corrupts the protocol channel. Anything new must not raise on out-of-range lines or absurd columns (Task 1 Step 5 proves this).
- `grep -rn 'addStr(w, str(' --include='*.sd7' src/` must stay empty. `grep -rn 'progs.s7i' src/` must stay one line (`src/analysis.sd7:2`).
- Seed7 traps that bite this plan: a `local` variable cannot be initialised from a parameter of the same function — declare with a constant, assign in `begin`; declare before use (a `func` cannot call a helper defined later in the file); `key`, `len`, `line`, `sum` are taken; there is no `SIZE_ERROR`; string literals are `"...\"..."` and `'\9;'` is a tab; a char literal cannot hold a backslash (`BACKSLASH`/`SINGLE_QUOTE` in `doc_store.sd7` are the named constants); a long `and`/`or` chain of parenthesised comparisons can fail to *match*, so predicates are small `const func boolean:` one-liners.
- Positions on the wire are 0-based line/character in **UTF-16 code units**; `Content-Length` is a byte count, `length()` is a character count.
- Out of scope, on purpose (do not "improve" them here): the analyzer's column points **one past** the found token and we highlight one character wide from it, matching `s7check.sd7`'s own caret — a choice, not a defect; `utf-8` position negotiation; answering notifications; the `.s7i` driver reading from disk (R-F10). The last two get their own plans.

---

## File Structure

| File | Change | Responsibility after the change |
|---|---|---|
| `src/transport.sd7` | Modify | Owns every byte-length computation: new `utf8CharLength(ch)`; `utf8Length(stri)` now calls it, so the `ord()` thresholds exist once. |
| `src/doc_store.sd7` | Modify | Owns position conversion: new `lineIndexOf` (clamped line), `charColumnForBytes` (byte→character within one line), `lspRangeBytes` (analyzer-column → LSP range); `codeText` learns the radix-`#` rule; `lspRange` stops open-coding its own line clamp. |
| `src/diagnostics.sd7` | Modify | Nothing about bytes: swaps two `lspRange` calls for `lspRangeBytes`, because a `parseError` column arrives in bytes. |
| `tests/transport_test.sd7` | Modify | Character-width checks. |
| `tests/doc_store_test.sd7` | Modify | Byte→character checks and the based-literal masking checks. |
| `tests/diagnostics_test.sd7` | Modify | One golden-JSON check that a byte column lands on the character it names. |
| `tests/transcript.py` | Modify | Two client-visible checks over real frames: a non-ASCII diagnostic range, and hover/definition after a based literal. |
| `AGENTS.md`, `README.md`, spec | Modify (Task 3) | Record that `columnNumber` is a byte offset, correct the `columnNumber = 0` half-truth, and note the two protocol findings this reading pass proved. |

---

## Task 1: The analyzer counts columns in bytes

**Files:**
- Modify: `src/transport.sd7` (add above `utf8Length`, and simplify `utf8Length`)
- Modify: `src/doc_store.sd7` (add after `lspRange`, near line 116)
- Modify: `src/diagnostics.sd7:53-60`
- Test: `tests/transport_test.sd7`, `tests/doc_store_test.sd7`, `tests/diagnostics_test.sd7`, `tests/transcript.py`

**Interfaces:**
- Consumes: `lsDoc` struct (`text`, `lineStart` 1-based indices), `lineCount(doc)`, `lspRange(doc, line1, column1)` (character column, unchanged), `doc_store.isDigit`/`isAlpha`.
- Produces:
  - `const func integer: utf8CharLength (in char: ch)` — UTF-8 byte width of one code point (1..4). `src/transport.sd7`.
  - `const func integer: lineIndexOf (in lsDoc: doc, in integer: line1)` — line 1-based, clamped into range. `src/doc_store.sd7`.
  - `const func integer: charColumnForBytes (in string: text, in integer: start, in integer: byteCol)` — 1-based character column containing the 1-based byte offset. `src/doc_store.sd7`.
  - `const func string: lspRangeBytes (in lsDoc: doc, in integer: line1, in integer: byteCol)` — `{"line":…,"character":…}`, never raises. `src/doc_store.sd7`. **This is what `diagnostics.sd7` calls for an analyzer column.**

- [ ] **Step 1: Write the failing character-width check.** `tests/transport_test.sd7`'s `main` has no `local` block and needs none: add these four lines immediately before its `report("transport")` line. The numeric-escape form of each literal is deliberate — it is the spelling proven to compile, and it names the code point:

```sd7
    check("ascii char is 1 byte", str(utf8CharLength('a')), "1");
    check("greek char is 2 bytes", str(utf8CharLength("\960;"[1])), "2");
    check("euro char is 3 bytes", str(utf8CharLength("\8364;"[1])), "3");
    check("astral char is 4 bytes", str(utf8CharLength("\128169;"[1])), "4");
```

Run: `make test-transport`
Expected: FAIL — the suite does not analyse, because the name does not exist yet. On this build (`s7` 5.4.10) the analyzer says `Match for utf8CharLength(...) failed` and `Declaration of "main" failed`; the wording is not `Name … not defined`. Either way the point of the failure is the missing name, not a wrong number.

- [ ] **Step 2: Add the helper and fold the duplicate thresholds into it.** In `src/transport.sd7`, insert **above** `utf8Length` (Seed7 cannot call a function defined later in the file):

```sd7
# The UTF-8 byte width of one code point. The only place the thresholds live:
# `utf8Length` below counts a whole string with it, and `doc_store` needs it to read the
# analyzer's byte-valued column back as a character.
const func integer: utf8CharLength (in char: ch) is func
  result
    var integer: n is 0;
  local
    var integer: cp is 0;
  begin
    cp := ord(ch);
    if cp < 128 then
      n := 1;
    elsif cp < 2048 then
      n := 2;
    elsif cp < 65536 then
      n := 3;
    else
      n := 4;
    end if;
  end func;
```

Then replace the body of `utf8Length` so the thresholds are not stated twice:

```sd7
const func integer: utf8Length (in string: stri) is func
  result
    var integer: n is 0;
  local
    var integer: i is 0;
  begin
    for i range 1 to length(stri) do
      n +:= utf8CharLength(stri[i]);
    end for;
  end func;
```

Run: `make test-transport`
Expected: PASS — 11 checks, 0 failed (7 existing + 4 new).

- [ ] **Step 3: Write the failing range check.** Add to `tests/diagnostics_test.sd7`. Extend `main`'s `local` block with:

```sd7
    var lsDoc: uniDoc is lsDoc.value;
    var array lspDiag: one is 0 times lspDiag.value;
```

and insert these lines **after** the existing `check("json", …)` and **before** `report("diagnostics")`:

```sd7
    # The analyzer's columnNumber is a 1-based UTF-8 BYTE offset from the line start.
    # Measured on this exact line: ILLEGAL_STRING_ESCAPE reports column 26, and the
    # character at byte 26 is the 24th, i.e. 0-based character 23. Handing the byte count
    # to lspRange as a character index published 25 and put the squiggle two characters
    # right of the bad escape.
    setVersion(uniDoc, "const string: s is \"ππ\\z\";\n", 1);
    d.line1 := 1;
    d.column1 := 26;
    d.message := "Illegal string escape";
    d.atEof := FALSE;
    one &:= d;
    check("a byte column lands on the character it names",
          diagnosticsJson("file:///u.sd7", uniDoc, one),
          "{\"uri\":\"file:///u.sd7\",\"diagnostics\":[" &
          "{\"range\":{\"start\":{\"line\":0,\"character\":23},\"end\":{\"line\":0,\"character\":24}}," &
          "\"severity\":1,\"source\":\"seed7\",\"message\":\"Illegal string escape\"}]}");
```

Run: `make test-diagnostics`
Expected: FAIL `a byte column lands on the character it names` with `got: … "character":25 … "character":26`. Both ends are wrong by the two extra bytes the `π` pair costs.

- [ ] **Step 4: Write the failing byte-mapping check in `doc_store`.** Extend `main`'s `local` block in `tests/doc_store_test.sd7` with `var string: bLine is "";` and add before `report("doc_store")`:

```sd7
    # charColumnForBytes is the mapping the analyzer's columns need; the astral case is
    # the one that separates a character index from a UTF-16 unit index, because the LSP
    # position must be counted in units.
    setVersion(doc, "const string: s is \"ππ\\z\";\n", 1);
    bLine := lspRangeBytes(doc, 1, 26);
    check("byte 26 of a line with two 2-byte chars -> character 23", bLine,
          "{\"line\":0,\"character\":23}");
    bLine := lspRangeBytes(doc, 1, 2147483647);
    check("an absurd byte column clamps to the line length", bLine,
          "{\"line\":0,\"character\":26}");
    setVersion(doc, "const string: s is \"\128169;\\z\";\n", 1);
    bLine := lspRangeBytes(doc, 1, 26);
    check("byte 26 after an astral char -> character 23 (utf-16 units)", bLine,
          "{\"line\":0,\"character\":23}");
```

Run: `make test-doc_store`
Expected: FAIL — the suite does not analyse: on this build, `Match for lspRangeBytes(...) failed` plus the `Declaration of "main" failed` that follows it. The new names do not exist yet.

- [ ] **Step 5: Implement the mapping in `doc_store.sd7`.** Add `include "transport.sd7";` to its include list (`doc_store` currently includes only `seed7_05.s7i`; this is the seam where byte widths are allowed to enter). Then add after `lspRange`, and change `lspRange`'s own clamp to use the shared helper:

```sd7
# The line index for a 1-based line number, clamped. Written once because lspRange and
# lspRangeBytes both start from an analyzer-supplied line that can be past the buffer.
const func integer: lineIndexOf (in lsDoc: doc, in integer: line1) is func
  result
    var integer: lineIdx is 1;
  begin
    lineIdx := line1;
    if lineIdx < 1 then
      lineIdx := 1;
    elsif lineIdx > lineCount(doc) then
      lineIdx := lineCount(doc);
    end if;
  end func;
```

Inside `lspRange`, replace its four-line clamp (`lineIdx := line1; if lineIdx < 1 …`) with:

```sd7
    lineIdx := lineIndexOf(doc, line1);
```

Then:

```sd7
# The 1-based character column that holds the 1-based UTF-8 byte offset `byteCol`.
# A byte in the middle of a multi-byte character names that character, and a byte past
# the line's end names the character just after it, which lspRange clamps to the line
# length -- the same way it already clamps an absurd character column.
const func integer: charColumnForBytes (in string: text, in integer: start,
                                        in integer: byteCol) is func
  result
    var integer: ch is 1;
  local
    var integer: i is 0;
    var integer: cum is 0;
    var boolean: found is FALSE;
  begin
    i := start;
    ch := 1;
    cum := 0;
    found := FALSE;
    while i <= length(text) and text[i] <> '\n' and text[i] <> '\r' and not found do
      if cum + utf8CharLength(text[i]) >= byteCol then
        found := TRUE;
      else
        cum +:= utf8CharLength(text[i]);
        i +:= 1;
        ch +:= 1;
      end if;
    end while;
  end func;

# lspRange for a column that arrives from the analyzer, which counts bytes. Every other
# caller of lspRange hands it a character column it computed itself.
const func string: lspRangeBytes (in lsDoc: doc, in integer: line1,
                                  in integer: byteCol) is func
  result
    var string: out is "";
  local
    var integer: lineIdx is 0;
  begin
    lineIdx := lineIndexOf(doc, line1);
    out := lspRange(doc, lineIdx, charColumnForBytes(doc.text, doc.lineStart[lineIdx],
                                                     byteCol));
  end func;
```

Run: `make test-doc_store`
Expected: PASS — 51 checks, 0 failed.

- [ ] **Step 6: Route diagnostics through it.** In `src/diagnostics.sd7`, the three `lspRange(doc, diags[i]…)` calls inside `diagnosticsJson` become `lspRangeBytes`:

```sd7
            field(w, "range");
            openObject(w);
              field(w, "start"); raw(w, lspRangeBytes(doc, diags[i].line1, diags[i].column1));
              field(w, "end");
              if diags[i].column1 > 0 then
                raw(w, lspRangeBytes(doc, diags[i].line1, diags[i].column1 + 1));
              else
                raw(w, lspRangeBytes(doc, diags[i].line1, 2147483647));
              end if;
            closeObject(w);
```

(The `column1 = 0` branch keeps asking for an absurd column and letting it clamp; that is the documented protocol decision, and Step 4 proves it cannot raise now that the line is clamped first.)

Run: `make test`
Expected: PASS — every suite green, `transcript: 45 checks, 0 failed`. If `test-lsp_server` or the transcript complains about a column, read the value before changing it: the existing transcript cases sit on ASCII lines, where byte and character counts agree.

- [ ] **Step 7: Commit.**

```bash
git add src/transport.sd7 src/doc_store.sd7 src/diagnostics.sd7 \
        tests/transport_test.sd7 tests/doc_store_test.sd7 tests/diagnostics_test.sd7
git commit -m "Count the analyzer's column in bytes before mapping it to a character"
```

- [ ] **Step 8: Mutation proof.** Two mutations, each reverted separately.

(a) In `src/doc_store.sd7`, change `charColumnForBytes`'s test from `>= byteCol` to `> byteCol`.
Run: `make test-doc_store` → Expected: FAIL `byte 26 of a line with two 2-byte chars -> character 23` (it lands one character late).
Revert: `git checkout -- src/doc_store.sd7`

(b) In `src/transport.sd7`, change `elsif cp < 2048 then` to `elsif cp < 128 then`, so a two-byte character falls through to the three-byte branch.
Run: `make test-diagnostics` → Expected: FAIL `a byte column lands on the character it names`.
Revert: `git checkout -- src/transport.sd7`

(An earlier revision of this step said to change `cp < 2048` to `cp < 65536`; the first Task 1 implementer proved that mutation leaves `test-diagnostics` green, because it demotes three-byte characters and the fixture's `π` pair still measures 2. The mutation above is the faithful one; the same wrong edit is still caught by `make test-transport`.)

If either mutation leaves the suite green, the check is decorative: fix the check before continuing.

---

## Task 2: A based literal must not hide its line

**Files:**
- Modify: `src/doc_store.sd7` (`codeText`'s `#` branch, plus one new predicate near `isDigit`)
- Test: `tests/doc_store_test.sd7`, `tests/transcript.py`

**Interfaces:**
- Consumes: `doc_store.isDigit`, `isAlpha`, `codeText`, `wordAt`.
- Produces: `const func boolean: isRadixHash (in string: text, in integer: i)` — TRUE when the `#` at `i` is the radix separator of a based literal (`16#beef`, `8#77`). `const func string: codeText (in lsDoc: doc)` — signature unchanged; its output length is unchanged and stays a character-for-character mask.

**Why this is one fix, not four:** `wordAt` (hover, definition, completion) and `signature_help.callContextOf` both read the document through `codeText`. Today `16#beef + afterThis;` masks everything from the `#` to end of line, so the tail of the line is invisible to all four features. Verified against the real server: on a clean program (0 diagnostics), hover **and** definition at line 6 character 26 of `    total := 16#beef + afterThis;` both return `null`. `lib/aes.s7i` has 691 lines with based literals and `lib/shiftjis.s7i` 1770, so this is not a corner.

- [ ] **Step 1: Write the failing masking checks.** Extend `main`'s `local` block in `tests/doc_store_test.sd7` with `var string: radixMask is "";` and add before `report("doc_store")`:

The prefix lengths below are measured, not counted by hand (`;` is the 28th character of the second fixture, the 33rd of the third). Nothing asserts a run of spaces: a space-count literal is a fixture waiting to be wrong.

```sd7
    # '#' between a digit and an extended digit is the radix separator of a based
    # literal (manual/tokens.htm: based_integer ::= '#' extended_digit { extended_digit }).
    # Masking it as a line comment hid the rest of every line that contains 16#beef.
    setVersion(doc, "const integer: y is 16#beef + afterThis;\n", 1);
    check("a name after a based literal is still code", wordAt(doc, 0, 35).word,
          "afterThis");
    check("a line of pure code masks to itself", codeText(doc),
          "const integer: y is 16#beef + afterThis;\n");
    setVersion(doc, "const integer: y is 16#beef; # hiddenWord\n", 1);
    check("a real comment after a based literal still hides",
          str(pos(codeText(doc), "hiddenWord")), "0");
    check("the code before that comment survives", codeText(doc)[1 .. 28],
          "const integer: y is 16#beef;");
    radixMask := codeText(doc);
    check("and the mask is still the length of the text", str(length(radixMask)),
          str(length(doc.text)));
    setVersion(doc, "const integer: w is 16#ff + 8#77; # tail\n", 1);
    check("two based literals on one line", codeText(doc)[1 .. 33],
          "const integer: w is 16#ff + 8#77;");
    check("and the comment is still a comment", str(pos(codeText(doc), "tail")), "0");
    setVersion(doc, "const integer: v is 1#;\n", 1);
    check("a hash with no extended digit after it is a comment", codeText(doc),
          "const integer: v is 1  \n");
    setVersion(doc, "# hashFirst\nconst integer: keepMe is 1;\n", 1);
    check("a hash that opens the line is still a comment",
          str(pos(codeText(doc), "hashFirst")), "0");
    check("and the next line is still code", wordAt(doc, 1, 21).word, "keepMe");
```

Run: `make test-doc_store`
Expected: FAIL — `a name after a based literal is still code` (expected `afterThis`, got `''`), and the four `codeText` checks that show `16#beef` blanked out. This is the check that must be able to fail: it is the assertion that the mask keeps code the old rule destroyed.

- [ ] **Step 2: Add the predicate.** In `src/doc_store.sd7`, immediately after `isDigit`:

```sd7
# TRUE when the '#' at index `i` of a line is the radix separator of a based literal.
# Seed7's '#'-terminated line comment and its `16#beef` share a character, and the
# grammar decides by what surrounds it: a digit before, an extended digit (0-9, A-Z,
# a-z) after. Its own function because a mixed and/or chain of these comparisons can
# fail to match at analysis time.
const func boolean: isRadixHash (in string: text, in integer: i) is func
  result
    var boolean: out is FALSE;
  begin
    out := i > 1 and i < length(text) and isDigit(text[pred(i)]) and
           (isAlpha(text[succ(i)]) or isDigit(text[succ(i)]));
  end func;
```

- [ ] **Step 3: Use it in `codeText`.** Change only the `#` branch:

```sd7
      elsif ch = '#' and not isRadixHash(doc.text, i) then
        out &:= " ";
        inLine := TRUE;
```

Run: `make test-doc_store`
Expected: PASS — 59 checks, 0 failed (48 baseline + 3 from Task 1 + 8 here).

- [ ] **Step 4: Confirm nothing else moved.** Run `make test`
Expected: PASS, all suites, including `transcript: 45 checks, 0 failed`. `features_test` exercises `codeText` through `signature_help` and `wordAt`; a green run there is the evidence that the mask did not start leaking comment text as code.

- [ ] **Step 5: Commit.**

```bash
git add src/doc_store.sd7 tests/doc_store_test.sd7
git commit -m "Stop a based literal from hiding the rest of its line"
```

- [ ] **Step 6: Mutation proof.** In `src/doc_store.sd7`, drop the guard so every `#` is a comment again — change `elsif ch = '#' and not isRadixHash(doc.text, i) then` to `elsif ch = '#' then`.
Run: `make test-doc_store` → Expected: FAIL `a name after a based literal is still code`.
Revert: `git checkout -- src/doc_store.sd7`

Second mutation, the other direction: in `isRadixHash`, weaken the left-hand guard from `i > 1` to `i > 0`, so a `#` as the first character of a line reads `text[0]`.
Run: `make test-doc_store` → Expected: FAIL or abort on `a hash that opens the line is still a comment` — a Seed7 string index of 0 raises, and a raise inside the suite is a failed run, not a pass.
Revert: `git checkout -- src/doc_store.sd7`

The remaining disjunct, `isDigit(text[succ(i)])` in the `or`, is **not** independently covered: every fixture with a digit after the `#` also has a letter, so deleting that disjunct leaves all eight checks green. Either add a fixture that needs it (a digit-only based literal followed by code that must survive) and prove the mutation fails, or state plainly in the final report that this branch is unproven. Do not claim a proof you do not have.

---

## Task 3: Client-visible checks and the corrected facts

**Files:**
- Modify: `tests/transcript.py`
- Modify: `AGENTS.md`, `README.md`, `docs/superpowers/specs/2026-09-10-seed7-lsp-server-design.md`

**Interfaces:**
- Consumes: `expect(label, condition)`, `frame(msg)`, `run(frames)`, `split_frames` — all already in `tests/transcript.py`; the `publishDiagnostics` notifications collected as `notes`.
- Produces: nothing imported by later tasks. This task is the harness proof plus the documentation the next reader needs.

- [ ] **Step 1: Add the transcript case for both fixes.** In `tests/transcript.py`, after the existing `msgs = [...]` block and its assertions (so the original lifecycle run is untouched), append a second run. Every value below is measured: the byte column comes from `ILLEGAL_STRING_ESCAPE` on the `ππ` line, and the hover position is inside `afterThis`:

```python
# A line whose error sits behind two 2-byte characters: the analyzer counts bytes,
# the client counts UTF-16 units, and the range must arrive in the client's units.
PI = '$ include "seed7_05.s7i";\nconst proc: main is func\n  begin\n    writeln("\u03c0\u03c0\\z");\n  end func;\n'
RADIX = ('$ include "seed7_05.s7i";\nconst integer: afterThis is 1;\n'
         'const proc: main is func\n  local\n    var integer: total is 0;\n  begin\n'
         '    total := 16#beef + afterThis;\n    writeln(total);\n  end func;\n')
msgs2 = [
    {"jsonrpc": "2.0", "id": 10, "method": "initialize", "params": {"capabilities": {}}},
    {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params":
        {"textDocument": {"uri": "file:///tmp/tt_pi.sd7", "languageId": "seed7",
                          "version": 1, "text": PI}}},
    {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params":
        {"textDocument": {"uri": "file:///tmp/tt_radix.sd7", "languageId": "seed7",
                          "version": 1, "text": RADIX}}},
    {"jsonrpc": "2.0", "id": 11, "method": "textDocument/hover", "params":
        {"textDocument": {"uri": "file:///tmp/tt_radix.sd7"},
         "position": {"line": 6, "character": 26}}},
    {"jsonrpc": "2.0", "id": 12, "method": "textDocument/definition", "params":
        {"textDocument": {"uri": "file:///tmp/tt_radix.sd7"},
         "position": {"line": 6, "character": 26}}},
    {"jsonrpc": "2.0", "id": 13, "method": "shutdown"},
    {"jsonrpc": "2.0", "method": "exit"},
]
replies2, code2, err2, junk2 = run([frame(m) for m in msgs2])
by_id2 = {r.get("id"): r for r in replies2 if "id" in r}
notes2 = [r for r in replies2 if r.get("method") == "textDocument/publishDiagnostics"]
pi_notes = [n for n in notes2 if n["params"]["uri"] == "file:///tmp/tt_pi.sd7"]
expect(len(pi_notes) == 1, "the escape fixture publishes one diagnostic")
if pi_notes:
    pr = pi_notes[0]["params"]["diagnostics"][0]["range"]
    expect(pr["start"] == {"line": 3, "character": 16} and
           pr["end"] == {"line": 3, "character": 17},
           "diagnostic range is in characters, not bytes (%r)" % pr)
hov2 = by_id2.get(11, {}).get("result") or {}
expect("afterThis" in hov2.get("contents", {}).get("value", ""),
       "hover reaches a name written after a based literal (%r)" % hov2)
defn2 = by_id2.get(12, {}).get("result") or []
expect(len(defn2) == 1 and defn2[0]["range"]["start"]["line"] == 1,
       "definition reaches it too (%r)" % defn2)
expect(code2 == 0, "exit after shutdown is status 0 for the second run")
```

- [ ] **Step 2: Run the harness.** These are confirmation checks for code already committed in Tasks 1–2, not a red-first cycle: the values were measured against the pre-fix server (it published `start.character: 18` and answered `null` to both requests), so a pass here is the evidence that the two fixes reach the wire.

```bash
python3 tests/transcript.py
```
Expected: `transcript: 50 checks, 0 failed` (45 + 5). If `diagnostic range is in characters, not bytes` fails, do not edit the expectation to match the output — re-derive it: the analyzer's `columnNumber` for that line is 19 bytes, byte 19 falls inside the 17th character, and the 16 UTF-16 units before it are 16 characters, because nothing before the position is astral. A mismatch means one of the two fixes is incomplete.

- [ ] **Step 3: Commit the harness.**

```bash
git add tests/transcript.py
git commit -m "Prove the column and based-literal fixes over real frames"
```

- [ ] **Step 4: Correct the recorded facts.** Three edits, all text, no code.

In `AGENTS.md`, under **Protocol decisions that are easy to undo by accident**, replace:

```
- Semantic errors arrive with `columnNumber = 0`. Ask `lspRange` for an absurd column
  and let it clamp, rather than adding a second position function.
```

with:

```
- `parseError.columnNumber` is a 1-based **UTF-8 byte** offset from the line start, and
  it names the last byte of the offending token. `lspRange` takes a character column, so
  analyzer columns go through `lspRangeBytes` and nothing else does. Measured: the same
  token reports column 29 with `"x"`, 30 with `"π"`, 32 with `"ππ"` or an astral
  character.
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
```

In `README.md`, in **What works**, extend the sentence about `Ranges are line-based.` with: "Where the analyzer reports a column, it counts bytes and the server converts — see `doc_store.lspRangeBytes`." Do not add a new section.

In the design spec, correct §5's claim about library docs, which this reading pass refuted: `Seed7Home/libraries/*.htm` **does** carry per-declaration anchors (2992 of them, one per overload signature) and `subject_index.htm` is a 512 KB declaration catalogue with 3248 entries — usable, but spelled with abstract type variables (`inout_arrayType`), so mapping a resolved type to that spelling is the work. Also note that the scanner milestone is called M4 in `AGENTS.md` and M5 in the spec's milestone table, and pick one label in the next commit that touches either file.

- [ ] **Step 5: Commit and report.**

```bash
git add AGENTS.md README.md docs/superpowers/specs/2026-09-10-seed7-lsp-server-design.md
git commit -m "Record that analyzer columns are byte offsets and what the reading pass proved"
make test
```
Expected: `make test` exit 0. Report the final check counts per suite and the two mutation proofs you actually ran, plus anything you could not make fail.

---

## Where the numbers come from

Everything asserted above was measured on this machine, `s7` 5.4.10, in this repo's worktree:

| Claim | Measurement |
|---|---|
| `columnNumber` is a byte offset | Same token, same character position, different text before it: `"x"`→29, `"π"`→30, `"ππ"`→32, astral→32. |
| Byte 26 of `const string: s is "ππ\z";` is character 24 | `parseStri` reports `ILLEGAL_STRING_ESCAPE col=26`; `lspRangeBytes` → `{"line":0,"character":23}`; today's code publishes 25. |
| Astral byte 26 → `character` 23, not 22 | UTF-16 units: the astral character before the position counts twice, which is exactly the point of `utf16Before`. |
| Real server, real frames | `writeln("ππ\z")` publishes `start.character: 18` today; 16 is correct. |
| Hover after a based literal | Real program, 0 diagnostics, hover and definition at line 6 char 26 → both `null` today. |
| `codeText` fix keeps code | Masked output before: `const integer: y is 16                  `; after: `const integer: y is 16#beef + afterThis;`. |
| Based literals are common | `grep -c` over the distribution: `lib/shiftjis.s7i` 1770 lines, `lib/aes.s7i` 691, 12.7k occurrences in `lib/*.s7i`. |
