# Seed7 LSP M3 (symbol features) — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer `documentSymbol`, `definition`, `hover`, `completion` and `signatureHelp`
for Seed7 documents, using the objects the analyzer already put in the parsed `program`.

**Architecture:** One new primitive and one new record type carry the whole milestone.
`doc_store.wordAt` turns an LSP position into the identifier or operator under the cursor;
`analysis.analyzeSymbols` turns document text into a flat `array symRec` of every global
declaration the analyzer knows about — in the file **and in the libraries it includes** —
each with its absolute file, 1-based declaration line, reconstructed signature and parameter
list. The five features are then thin LSP-shape builders over those two, one file each under
`src/features/`. No caching: a request re-parses (20–45 ms measured in M2), which keeps the
document store the only state in the process.

**Tech Stack:** SEED7 5.4.x `s7` interpreter (its own `progs.s7i` reflection API), GNU Make,
python3 only as the end-to-end transcript driver.

**Spec:** `docs/superpowers/specs/2026-09-10-seed7-lsp-server-design.md` — §3.3 positions,
§4 analysis lifecycle, §5 feature data sources, §8 milestones. This plan is M3 minus two
items the spec also puts in M3, deliberately split out (see "Out of scope"): the trust gate
and the `.s7i` staleness fix.

## Global Constraints

Unchanged from the core plan; every task's requirements implicitly include this section.

- Language of the product: **Seed7 only.** No other runtime in the shipped server.
- Requires a working `s7` on `PATH`; tests run with `make test` and need no editor.
- Positions are 0-based line/character in **UTF-16 code units**. `getError` line/column are
  **1-based**; the conversion lives in `doc_store.sd7` and nowhere else.
- Only `analysis.sd7` may `include "progs.s7i"`. Only `doc_store.sd7` converts positions.
  Only `transport.sd7` computes or consumes byte lengths. Only `src/**.sd7` feature code
  builds LSP response shapes.
- Capabilities stay static in `InitializeResult`, no dynamic registration, **and a capability
  is only advertised once its method is answered**.
- Every outbound byte goes through `jsonw.sd7`. Never `str()` a `jsonValue` holding text
  (`€` → `\8364;`, invalid JSON). `grep -n 'addStr(w, str(' src/**.sd7` must stay empty.
- Nothing but frames may reach stdout: an uncaught Seed7 exception prints to stdout, exits 1,
  and corrupts the channel. Anything that can raise must be made total inside `src/`.
- Diagnostics stay from `errorCount`/`getError`, never from scraping stderr.
- Red first: write the check, run it, see it fail for the reason you claim, then implement.
  `make test` before and after every commit. Never judge a `s7` run by its exit status.
- Seed7 traps (each cost someone a cycle): `local` vars cannot be initialised from a
  parameter — declare with a constant and assign in `begin`. `key`, `len` and `line` are
  taken by the language. Strings are `"...\"..."`; there is no single-quoted string and
  `str(char)`/`char & string` do not exist — slice the source text (`stri[i .. i]`) instead.
  `&`/`<&` reject non-strings; `&:=` appends. `pos(a, b) <> 0` is containment. A long
  `or`/`and` chain with parenthesised comparisons can fail to *match* at parse time — split
  predicates into small `const func boolean:` one-liners. `s7` reports analysis errors on
  stderr **and exits 0**.

## Measured facts this plan relies on

All of these were measured on SEED7 5.4.10 with the fixtures in `tests/programs/`; they are
not assumptions. If a later Seed7 version contradicts one of them, the tests in this plan are
the ones that will say so.

1. `globalObjects(prog)` on a program that includes `console.s7i` returns **3322** references.
   Only 15 of them have `file(obj) = "?"` (compiler-internal objects); `s7xref.sd7` filters
   exactly those, and so do we.
2. For a declaration, `file(obj)`/`path(obj)` give the **absolute path** and `line(obj)` gives
   the **1-based declaration line** — including for standard-library objects
   (`writeln` → `/home/username/seed7/lib/enable_io.s7i:226`). This is what makes
   go-to-definition into the stdlib and stdlib hover possible without any index of our own.
3. Overloads appear as **separate entries with the same name**, and some entries repeat
   identically because a library is included twice. Any list built from `globalObjects` must
   dedupe on `(name, file, line)`.
4. `syobject(prog, name)` returns a `SYMBOLOBJECT` whose `file(obj)` is `"?"` and whose
   `line(obj)` is a use-site line. It is therefore **useless for a `Location`** — it is useful
   only as an existence check, and it does resolve *local* variables (`localCounter` → found),
   which nothing else in the API does.
5. `getType`, `formalParams` and `resultVar` **raise `RANGE_ERROR`** on real inputs
   (`getType` on a `SYMBOLOBJECT`, `resultVar` on a `proc`). The design's claim that "every
   accessor is total" stops being true the moment M3 reads a reference, so every one of those
   calls in this plan is wrapped in a `block … exception … end block;`.
6. `formalParams(obj)` lists the parameters **and one trailing self/result entry**; filter by
   `str(category(p))` containing `PARAMOBJECT`.
7. `str(obj)` is the declared name (operators included: `<&` prints as `<&`), and
   `str(category(obj))` gives `TYPEOBJECT`, `BLOCKOBJECT`, `DECLAREDOBJECT`, `STRUCTOBJECT`,
   `ACTOBJECT`, `ENUMLITERALOBJECT`, `SYMBOLOBJECT`, …
8. A program whose `$ include "seed7_05.s7i";` line is absent produces an 11–25 error cascade
   ending in `SYSTEM_MAIN_MISSING`; with the line present, a main-less program analyses
   clean. An empty buffer reports `EOF_ENCOUNTERED` + `SYSTEM_MAIN_MISSING`.
9. `parseFile` on a `.s7i` fails; `parseStri` of the two-line synthetic driver
   (`$ include "seed7_05.s7i";` + `  include "<absolute path>";`) analyses a real library with
   0 errors — already relied on by `analysis.driverFor`.
10. `toPercentEncoded` (in `encoding.s7i`) encodes **everything including `/`** and raises
    `RANGE_ERROR` on non-ASCII. It is not usable for `file://` URIs; Task 3 writes a small
    encoder instead.

## Out of scope (deliberate)

- **Trust gate** and **`.s7i` staleness (R-F10)**, which the spec also lists under M3. Both are
  orthogonal to these five features and each is its own plan; nothing here depends on them.
- `scan.sd7`, and with it foldingRange/selectionRange/semanticTokens (M4). `wordAt` is a
  line-local extractor, not a lexer; where it is knowingly wrong (inside a comment or a string
  literal) the code says so with a `ponytail:` comment.
- Struct-member completion after `.` — needs `structSymbols`, which is a different shape of
  problem. `references`/`rename` stay M6: the reflection API has no use sites.

## File structure

| File | Responsibility | Task |
|---|---|---|
| `src/doc_store.sd7` (modify) | `charIndexOf`, `wordAt`/`wordRef`, `lspRangePair` — the only position↔text functions | 1 |
| `src/analysis.sd7` (modify) | `symRec` + `analyzeSymbols`: the only code that touches `reference`s | 2 |
| `src/lsp_server.sd7` (modify) | `uriFor`, `symbolsOfDocument` (routes `.s7i` through the driver), dispatch, capabilities | 3, 5–9 |
| `tests/programs/symbols.sd7` (create) | fixture with a struct, a 2-param func, a proc, an overload, a local | 2 |
| `src/doc_index.sd7` (create) | `proseFor(path, line1)` — the `(** … *)` comment above a declaration | 4 |
| `src/features/document_symbol.sd7` (create) | `DocumentSymbol[]` for one document | 5 |
| `src/features/definition.sd7` (create) | `Location[]` for the word under the cursor | 6 |
| `src/features/hover.sd7` (create) | signature block + prose | 7 |
| `src/features/completion.sd7` (create) | prefix-filtered `CompletionItem[]` / `CompletionList` | 8 |
| `src/features/signature_help.sd7` (create) | overload candidates + active parameter | 9 |
| `tests/features_test.sd7` (create) | one suite for all five builders | 5–9 |
| `Makefile`, `AGENTS.md`, `README.md`, spec (modify) | targets, invariant greps that now span `src/features/`, docs | 1, 10 |

The spec's `features/` subdirectory is honoured: Seed7 resolves `include "features/x.sd7"`
against `-l src`, verified with a throwaway probe.

---

## Task 1: `wordAt` — the identifier under the cursor

Everything else in this milestone is wrong in the same way if this is wrong, so it comes
first. LSP 3.18, "Hover Request": *"the client typically sends position n (the position before
the character)"* — so hovering over `writeln` at column 4 arrives as `character: 4` with the
cursor **left** of the `w`. `wordAt` must therefore prefer the character to the left of the
position, and fall back to the one at it (that is the case where the cursor sits just before a
token). Completion needs the same rule: while typing `wri|` the prefix ends at the cursor.

**Files:**
- Modify: `src/doc_store.sd7` (append after `lspRange`, before `end` of file)
- Modify: `tests/doc_store_test.sd7`
- Modify: `AGENTS.md` ("Positions are 0-based…" bullet — record the left-of-character rule)
- Modify: `docs/superpowers/specs/2026-09-10-seed7-lsp-server-design.md` §3.3 — add:
  *"Position→token is left-of-character: a client hovering the identifier at column `n` sends
  `character: n`, so the token is the one ending at `n`, not starting at it. Owned by
  `doc_store.wordAt`."*

**Interfaces:**
- Consumes: `lsDoc` (`text`, `lineStart`), `lineCount`, `lineWidth`, `utf16Before` — all already in `doc_store.sd7`.
- Produces:
  - `const type: wordRef is new struct { var string: word is ""; var integer: line1 is 0; var integer: column1 is 0; var integer: width is 0; }`
    — `line1`/`column1` are the analyzer's convention (1-based line, 1-based column of the
    first character), so features can hand them straight to `lspRange`/`lspRangePair`.
    `word = ""` means "no token here".
  - `const func integer: charIndexOf (in lsDoc: doc, in integer: line0, in integer: character0)`
    → 1-based index into `doc.text` of the character **at** the position (the one to the right
    of the cursor). A position at or past the end of its line yields the index of that line's
    terminator; an out-of-range `line0` yields `length(doc.text) + 1`.
  - `const func wordRef: wordAt (in lsDoc: doc, in integer: line0, in integer: character0)`
  - `const func string: lspRangePair (in lsDoc: doc, in integer: line1, in integer: column1, in integer: width)`
    → `{"start":{"line":L,"character":C},"end":{"line":L,"character":C2}}`
  - `const func string: lspWholeLine (in integer: line1)` → `{"start":{"line":line1-1,
    "character":0},"end":{"line":line1,"character":0}}`. Needed because reflection has no
    columns, and because a symbol in **another** file cannot go through `lspRange` at all —
    that function needs the document's text. Still a position conversion, so it still lives
    here (invariant 2).
  - `nameChar`, `opChar`, `isAlpha`, `isDigit`, `tokenChar` are public: Task 9's backwards
    walk needs them, and a second copy of a character class is how the two drift apart.

- [ ] **Step 1: Write the failing tests** — append to `tests/doc_store_test.sd7` before its
  `report(...)` call. The document `"  const proc: main is func\n    writeln(x);\n"` has line 1
  starting at text index 1 and line 2 starting at index 30.

```sd7
    setVersion(doc2, "  const proc: main is func\n    writeln(x);\n", 1);
    w := wordAt(doc2, 1, 6);
    check("left-of-character wins", w.word, "writeln");
    check("word line is 1-based", str(w.line1), "2");
    check("word column is 1-based", str(w.column1), "5");
    check("word width", str(w.width), "7");
    check("cursor just left of the token", wordAt(doc2, 1, 4).word, "writeln");
    check("inside indentation there is no word", wordAt(doc2, 1, 1).word, "");
    check("mid-line word", wordAt(doc2, 0, 10).word, "proc");
    check("hover the end of const", wordAt(doc2, 0, 7).word, "const");
    check("hover past the line end still finds the token", wordAt(doc2, 0, 99).word, "func");
    check("a position past the line end stops at the terminator",
          str(charIndexOf(doc2, 1, 99)),
          str(doc2.lineStart[2] + lineWidth(doc2.text, doc2.lineStart[2])));
    check("an out-of-range line is one past the text", str(charIndexOf(doc2, 400, 0)),
          str(length(doc2.text) + 1));
    check("absurd line has no word", wordAt(doc2, 400, 0).word, "");
    setVersion(doc3, "a<&b\n", 1);
    check("operator run is one word", wordAt(doc3, 0, 2).word, "<&");
    check("name char before an operator", wordAt(doc3, 0, 1).word, "a");
    check("range pair", lspRangePair(doc3, 1, 1, 1),
          "{\"start\":{\"line\":0,\"character\":0},\"end\":{\"line\":0,\"character\":1}}");
    check("whole line range, no document needed", lspWholeLine(13),
          "{\"start\":{\"line\":12,\"character\":0},\"end\":{\"line\":13,\"character\":0}}");
```

  Declare `var lsDoc: doc2 is lsDoc.value;`, `var lsDoc: doc3 is lsDoc.value;` and
  `var wordRef: w is wordRef.value;` in the test's `local` block.

  The expectations are arithmetic, not guesses. Line 0 is 26 characters, so its terminator is
  at index 27 and line 1 starts at index 28. On line 1 the four spaces occupy 28–31 and
  `writeln` occupies 32–38, which is why `column1` is 5 (32 − 28 + 1): `wordAt(doc2, 1, 6)`
  resolves index 35 (`r`, left of the cursor) and grows to the whole name, while
  `wordAt(doc2, 1, 4)` has index 32 (`w`) to its *right* and reaches the same answer through
  the fallback branch. On line 0, `const` is 3–7 and `proc` is 9–12. If a check disagrees with
  the code, re-derive the indices before editing either — `column1` is relative to the line
  start, which is what makes the expectations independent of the fixture's exact length.

- [ ] **Step 2: Run them and confirm they fail because the symbols do not exist**

Run: `s7 -q -l src tests/doc_store_test.sd7`
Expected: `Declaration of "main" failed` plus `Match for wordAt(...)` — i.e. a compile error
naming `wordRef`/`wordAt`, not an assertion failure.

- [ ] **Step 3: Implement** — append to `src/doc_store.sd7`:

```sd7
const type: wordRef is new struct
    var string: word is "";
    var integer: line1 is 0;
    var integer: column1 is 0;
    var integer: width is 0;
  end struct;

const func boolean: isAlpha (in char: ch) is
  return (ch >= 'a' and ch <= 'z') or (ch >= 'A' and ch <= 'Z');

const func boolean: isDigit (in char: ch) is
  return ch >= '0' and ch <= '9';

const func boolean: nameChar (in char: ch) is
  return ch = '_' or isAlpha(ch) or isDigit(ch);

const set of char: OP_CHARS is {'+', '-', '*', '/', '<', '>', '=', ',', ':', ';',
                                '&', '%', '^', '|', '~', '!', '?', '@'};

const func boolean: opChar (in char: ch) is
  return ch in OP_CHARS;

# The character AT an LSP position -- positions are between characters, so this is
# the character to the RIGHT of the cursor. Past the end of the document it reports
# one past the last index, which callers treat as "no character here".
const func integer: charIndexOf (in lsDoc: doc, in integer: line0,
                                 in integer: character0) is func
  result
    var integer: idx is 0;
  local
    var integer: lineIdx is 0;
    var integer: start is 1;
    var integer: i is 1;
    var integer: units is 0;
  begin
    idx := length(doc.text) + 1;
    lineIdx := line0 + 1;
    if lineIdx >= 1 and lineIdx <= lineCount(doc) then
      start := doc.lineStart[lineIdx];
      i := start;
      units := 0;
      while i <= length(doc.text) and units < character0 and
            doc.text[i] <> '\n' and doc.text[i] <> '\r' do
        if ord(doc.text[i]) >= 65536 then
          units +:= 2;
        else
          units +:= 1;
        end if;
        i +:= 1;
      end while;
      idx := i;
    end if;
  end func;

# ponytail: no lexer. A run of OP_CHARS inside (* ... *) or "...\"..." is still
# returned as a "word", and `a<b` reads as one operator run. scan.sd7 (M4) owns
# that; every consumer here is a request for the token under a cursor.
const func wordRef: wordAt (in lsDoc: doc, in integer: line0,
                            in integer: character0) is func
  result
    var wordRef: out is wordRef.value;
  local
    var integer: lineIdx is 0;
    var integer: start is 1;
    var integer: right is 0;
    var integer: at is 0;
    var integer: first is 0;
    var integer: lastIdx is 0;
    var boolean: opRun is FALSE;
  begin
    lineIdx := line0 + 1;
    if lineIdx >= 1 and lineIdx <= lineCount(doc) then
      start := doc.lineStart[lineIdx];
      right := charIndexOf(doc, line0, character0);
      at := 0;
      if right > start and right <= length(doc.text) and onLine(doc, lineIdx, right) and
         tokenChar(doc.text[pred(right)]) then
        at := pred(right);
      elsif right >= start and right <= length(doc.text) and onLine(doc, lineIdx, right) and
            tokenChar(doc.text[right]) then
        at := right;
      end if;
      if at <> 0 then
        opRun := opChar(doc.text[at]);
        first := at;
        while pred(first) >= start and tokenKindAt(doc, pred(first), opRun) do
          first := pred(first);
        end while;
        lastIdx := at;
        while succ(lastIdx) >= start and tokenKindAt(doc, succ(lastIdx), opRun) do
          lastIdx := succ(lastIdx);
        end while;
        out.word := doc.text[first .. lastIdx];
        out.line1 := lineIdx;
        out.column1 := first - start + 1;
        out.width := lastIdx - first + 1;
      end if;
    end if;
  end func;
```

  The two helpers it names go in the same file, above `wordAt`:

```sd7
const func boolean: tokenChar (in char: ch) is
  return nameChar(ch) or opChar(ch);

const func boolean: onLine (in lsDoc: doc, in integer: lineIdx, in integer: idx) is func
  result
    var boolean: out is FALSE;
  begin
    out := idx >= doc.lineStart[lineIdx] and
           idx < doc.lineStart[lineIdx] + lineWidth(doc.text, doc.lineStart[lineIdx]);
  end func;

const func boolean: tokenKindAt (in lsDoc: doc, in integer: idx,
                                 in boolean: wantOp) is func
  result
    var boolean: out is FALSE;
  begin
    if idx >= 1 and idx <= length(doc.text) then
      if wantOp then
        out := opChar(doc.text[idx]);
      else
        out := nameChar(doc.text[idx]);
      end if;
    end if;
  end func;
```

  `lspRangePair` reuses the existing `lspRange` twice — the same composition
  `diagnosticsJson` already does:

```sd7
const func string: lspRangePair (in lsDoc: doc, in integer: line1, in integer: column1,
                                 in integer: width) is func
  result
    var string: out is "";
  begin
    out := "{\"start\":" <& lspRange(doc, line1, column1) <& ",\"end\":" &
           lspRange(doc, line1, succ(column1 + width) - 1) <& "}";
  end func;
```

  **Note on the end column:** `lspRange(doc, line1, column1 + width)` would overshoot by one
  because `column1` is already 1-based. `succ(column1 + width) - 1` is the last character of
  the token as a 1-based column; `lspRange` then clamps it to the line width. Verify against
  the `"a<&b"` case: start char 0, end char 1 for width 1.

```sd7
const func string: lspWholeLine (in integer: line1) is func
  result
    var string: out is "";
  begin
    out := "{\"start\":{\"line\":" <& line1 - 1 <& ",\"character\":0}," <&
           "\"end\":{\"line\":" <& line1 <& ",\"character\":0}}";
  end func;
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `s7 -q -l src tests/doc_store_test.sd7` — expected `doc_store: NN checks, 0 failed`.
If a check disagrees with the reasoning above, the reasoning is what is wrong: fix the code
and say so in the commit message.

- [ ] **Step 5: `make test`, then commit**

```bash
make test
git add src/doc_store.sd7 tests/doc_store_test.sd7 AGENTS.md docs/superpowers/
git commit -m "Add wordAt: the token under an LSP position, left-of-character"
```

---

## Task 2: `symRec` — declarations as plain data

The five features need the same six facts per declaration. Extracting them means calling the
reflection accessors that raise (measured fact 5), so this task also fixes the containment
question the spec left open: make the wrappers total and test the totals.

**Files:**
- Modify: `src/analysis.sd7`
- Create: `tests/programs/symbols.sd7`
- Modify: `tests/analysis_test.sd7`

**Interfaces:**
- Consumes: `parseStri`, `globalObjects`, `category`, `getType`, `formalParams`, `file`,
  `line`, `isVar`, `str(reference)` (all via `progs.s7i` / `reference.s7i` / `ref_list.s7i`,
  which `progs.s7i` already pulls in — confirm with the probe in Step 1b before writing).
- Produces:
  - `const type: symRec is new struct { var string: name is ""; var string: cat is "";
    var string: ty is ""; var string: file is ""; var integer: line1 is 0;
    var string: sign is ""; var array string: params is 0 times ""; }` — `ty` is
    `str(getType(obj))` (`"func integer"`, `"proc"`, `"Widget"`, `"type"`), kept because the
    kind maps in `features/kinds.sd7` cannot tell a function from a constant otherwise.
  - `const func array symRec: analyzeSymbols (in string: text, in array string: libraryDirs)`
    — every non-`"?"` global declaration reachable from `text`, deduped on
    `(name, file, line1)`, in `globalObjects` order. Empty array if the parse itself fails.

- [ ] **Step 1a: Create the fixture `tests/programs/symbols.sd7`** — it must contain one of
  each shape the mapper has to distinguish, plus the deliberate `main`-less-ness that keeps
  the analyzer honest:

```sd7
$ include "seed7_05.s7i";
  include "console.s7i";

const type: Widget is new struct
    var string: name is "";
    var integer: size is 0;
  end struct;

const func integer: totalSize (in Widget: w, in integer: times) is func
  result
    var integer: out is 0;
  begin
    out := w.size * times;
    return out;
  end func;

const proc: reportWidget (in string: label, inout integer: counter) is func
  begin
    writeln(label);
    counter +:= 1;
  end func;

const Widget: prototype is Widget.value;

const proc: main is func
  local
    var integer: hits is 0;
  begin
    reportWidget("proto", hits);
    writeln(totalSize(prototype, 2));
  end func;
```

- [ ] **Step 1b: Probe the accessor behaviour before writing the mapper.** Create
  `/tmp/sym_probe.sd7` (throwaway, do not commit) that parses the fixture with
  `parseFile("tests/programs/symbols.sd7")` and prints, per `globalObjects` entry whose
  `file(obj)` is that path: `str(obj)`, `str(category(obj))`, `line(obj)`, `isVar(obj)`,
  `str(getType(obj))` and each param's `str(category(p))` + `str(getType(p))`.

Run: `s7 -q /tmp/sym_probe.sd7`
Expected: entries for `Widget` (`TYPEOBJECT`, line 4), `totalSize`, `reportWidget`,
`prototype`; `resultVar` raises for the `proc`; the last element of `formalParams` is the
self entry described in measured fact 6. Write what you actually see into the code you are
about to write — where this plan's guess and the probe disagree, the probe wins, and the
commit message must record the correction.

- [ ] **Step 2: Write the failing tests** — append to `tests/analysis_test.sd7` (before
  `report("analysis")`), reading the fixture from disk so the test does not embed a copy:

```sd7
    var array symRec: syms is 0 times symRec.value;
    var string: fixPath is "tests/programs/symbols.sd7";

    syms := analyzeSymbols(readAll(fixPath), dirs);
    checkTrue("fixture yields symbols", length(syms) <> 0);
    check("own struct is listed", symsNamed(syms, "Widget")[1].cat, "TYPEOBJECT");
    check("declaration line is 1-based", str(symsNamed(syms, "reportWidget")[1].line1), "13");
    checkTrue("signature shows a parameter type and name",
              pos(symsNamed(syms, "reportWidget")[1].sign, "integer: counter") <> 0);
    checkTrue("signature of a func names its result type",
              pos(symsNamed(syms, "totalSize")[1].sign, "func integer") <> 0);
    checkTrue("stdlib writeln is listed with an absolute path",
              startsWith(symsNamed(syms, "writeln")[1].file, "/"));
    checkTrue("nothing keeps the ? file", pos(oneFile(syms), "?") = 0);
    check("dedupe collapses identical entries",
          str(countNameFile(syms, "writeln", symsNamed(syms, "writeln")[1].file)),
          str(countDistinctLines(syms, "writeln", symsNamed(syms, "writeln")[1].file)));
```

  Add `syms` and `fixPath` to the test's existing `local` block. The four helpers are test
  scaffolding, so they live in the test file, not in `src`:

```sd7
const func array symRec: symsNamed (in array symRec: syms, in string: nm) is func
  result
    var array symRec: out is 0 times symRec.value;
  local
    var integer: i is 0;
  begin
    for i range 1 to length(syms) do
      if syms[i].name = nm then
        out &:= syms[i];
      end if;
    end for;
  end func;

const func string: oneFile (in array symRec: syms) is func
  result
    var string: out is "";
  local
    var integer: i is 0;
  begin
    for i range 1 to length(syms) do
      out &:= syms[i].file;
    end for;
  end func;

const func integer: countNameFile (in array symRec: syms, in string: nm,
                                   in string: fname) is func
  result
    var integer: out is 0;
  local
    var integer: i is 0;
  begin
    for i range 1 to length(syms) do
      if syms[i].name = nm and syms[i].file = fname then
        out +:= 1;
      end if;
    end for;
  end func;

const func integer: countDistinctLines (in array symRec: syms, in string: nm,
                                        in string: fname) is func
  result
    var integer: out is 0;
  local
    var hash [string] integer: lines is hash [string] integer.EMPTY_HASH;
    var string: keyStr is "";
    var integer: i is 0;
  begin
    for i range 1 to length(syms) do
      if syms[i].name = nm and syms[i].file = fname then
        keyStr := str(syms[i].line1);
        if keyStr not in lines then
          lines @:= [keyStr] 1;
          out +:= 1;
        end if;
      end if;
    end for;
  end func;

const func string: readAll (in string: path) is func
  result
    var string: out is "";
  local
    var file: f is STD_NULL;
    var string: l is "";
  begin
    block
      f := open(path, "r");
      while not eof(f) do
        readln(f, l);
        out &:= l <& "\n";
      end while;
      close(f);
    exception
      catch FILE_ERROR:
        out := "";
    end block;
  end func;
```

  `readAll` is here because Seed7's `getFile` takes an `osFileSys` first argument and there is
  no plain `getFile(path)`; this is the same shape `doc_index.sd7` uses in Task 4. The test
  also needs `include "osfiles.s7i";` for `open`/`eof` and the named-hash form shown in
  AGENTS.md (`const type:` is required for a hash field, so write
  `const type: lineHash is hash [string] integer;` in the test file if the inline form above
  does not parse — it is the documented trap).

- [ ] **Step 3: Run to verify failure**

Run: `s7 -q -l src tests/analysis_test.sd7`
Expected: compile error naming `symRec` / `analyzeSymbols`.

- [ ] **Step 4: Implement in `src/analysis.sd7`** — after `include "progs.s7i";` add
  `include "ref_list.s7i";` if the Step 1b probe shows `for obj range objs` does not
  otherwise resolve.

```sd7
const type: symRec is new struct
    var string: name is "";
    var string: cat is "";
    var string: ty is "";
    var string: file is "";
    var integer: line1 is 0;
    var string: sign is "";
    var array string: params is 0 times "";
  end struct;

const func string: safeType (in reference: obj) is func
  result
    var string: out is "";
  begin
    block
      out := str(getType(obj));
    exception
      catch RANGE_ERROR:
        out := "";
    end block;
  end func;

# category(obj) is a plain string here ("VALUEPARAMOBJECT", ...). Anything whose name
# contains PARAMOBJECT is a declared parameter; the trailing self/result entry is not.
const func boolean: isParam (in reference: obj) is
  return pos(str(category(obj)), "PARAMOBJECT") <> 0;

const func string: paramText (in reference: obj) is func
  result
    var string: out is "";
  local
    var string: ty is "";
  begin
    ty := safeType(obj);
    if ty = "" then
      out := str(obj);
    else
      out := ty <& ": " <& str(obj);
    end if;
  end func;

const func array string: paramsOf (in reference: obj) is func
  result
    var array string: out is 0 times "";
  local
    var ref_list: pl is ref_list.EMPTY;
    var integer: i is 0;
  begin
    block
      pl := formalParams(obj);
      for i range 1 to length(pl) do
        if isParam(pl[i]) then
          out &:= paramText(pl[i]);
        end if;
      end for;
    exception
      catch RANGE_ERROR:
        out := 0 times "";
    end block;
  end func;

# The one place that knows what a Seed7 declaration looks like in prose. Kept separate
# so the tests can pin the text without touching reflection at all.
const func string: buildSign (in string: cat, in string: ty, in string: nm,
                              in array string: params) is func
  result
    var string: out is "";
  local
    var integer: i is 0;
  begin
    if cat = "TYPEOBJECT" then
      out := "const type: " <& nm;
    elsif cat = "ENUMLITERALOBJECT" then
      out := "const " <& ty <& ": " <& nm;
    elsif startsWith(ty, "proc") then
      out := "const proc: " <& nm;
    elsif startsWith(ty, "func ") then
      out := "const func " <& ty[6 ..] <& ": " <& nm;
    elsif cat = "BLOCKOBJECT" then
      out := "const proc: " <& nm;
    elsif cat = "DECLAREDOBJECT" then
      out := "const " <& ty <& ": " <& nm;
    else
      out := "const " <& ty <& ": " <& nm;
    end if;
    if length(params) <> 0 then
      out &:= " (";
      for i range 1 to length(params) do
        out &:= params[i];
        if i < length(params) then
          out &:= ", ";
        end if;
      end for;
      out &:= ")";
    end if;
  end func;
```

  and the walker:

```sd7
const type: seenNames is hash [string] integer;

const func array symRec: analyzeSymbols (in string: text,
                                         in array string: libraryDirs) is func
  result
    var array symRec: out is 0 times symRec.value;
  local
    var program: prog is program.EMPTY;
    var ref_list: objs is ref_list.EMPTY;
    var reference: obj is NIL;
    var seenNames: seen is seenNames.EMPTY_HASH;
    var string: keyStr is "";
    var symRec: rec is symRec.value;
  begin
    block
      prog := parseStri(text, parseOptions.value, libraryDirs);
      objs := globalObjects(prog);
      for obj range objs do
        rec.name := str(obj);
        rec.file := file(obj);
        if rec.file <> "?" and rec.file <> "" then
          rec.cat := str(category(obj));
          rec.ty := safeType(obj);
          rec.line1 := line(obj);
          rec.sign := signatureOf(obj);
          rec.params := paramsOf(obj);
          keyStr := rec.name <& "|" <& rec.file <& "|" <& str(rec.line1);
          if keyStr not in seen then
            seen @:= [keyStr] 1;
            out &:= rec;
          end if;
        end if;
      end for;
    exception
      # The per-object accessors are all total above, so reaching here means the walk
      # itself is unreliable: report nothing rather than a half-truth.
      catch RANGE_ERROR:    out := 0 times symRec.value;
      catch INDEX_ERROR:    out := 0 times symRec.value;
      catch ILLEGAL_ACTION: out := 0 times symRec.value;
    end block;
  end func;
```

  `paramsOf` is shared by the signature text and the `params` field so the two cannot drift,
  and it returns a fresh array every call. `rec` is re-used across iterations, so assign **every** field each time through, including
  `params := 0 times ""` before it is filled: a stale `params` from the previous object is a
  real hazard here and the reason `paramsOf` returns a fresh array.


const func string: signatureOf (in reference: obj) is func
  result
    var string: out is "";
  local
    var string: cat is "";
    var string: ty is "";
  begin
    cat := str(category(obj));
    ty := safeType(obj);
    out := buildSign(cat, ty, str(obj), paramsOf(obj));
  end func;

- [ ] **Step 5: Run to verify pass, then `make test` and commit**

```bash
s7 -q -l src tests/analysis_test.sd7
make test
git add src/analysis.sd7 tests/analysis_test.sd7 tests/programs/symbols.sd7
git commit -m "Add analyzeSymbols: global declarations as plain records"
```

---

## Task 3: `src/uris.sd7` and `symbolsOfDocument`

A `Location` needs a URI, and `pathOf` only goes one way. The feature modules cannot import
`lsp_server.sd7` to reach a URI builder (it imports them — a cycle), so the URI pair moves to
its own file, which is also where `pathOf` already belongs: a pure string function that happens
to know the `file://` scheme.

**Files:**
- Create: `src/uris.sd7` — `pathOf` copied out of `lsp_server.sd7`, plus `uriFor`
- Create: `tests/uris_test.sd7`; modify `Makefile` (`TESTS += uris`)
- Modify: `src/lsp_server.sd7` — drop its `pathOf`, include `uris.sd7`, add `symbolsOfDocument`
- Modify: `tests/lsp_server_test.sd7` — its two `pathOf` checks move to `tests/uris_test.sd7`

**Interfaces:**
- Consumes: `fromPercentEncoded` (`encoding.s7i`), `openDocs`, `driverFor`, `analyzeSymbols`,
  `libraryDirs`.
- Produces:
  - `const func string: pathOf (in string: uri)` — moved verbatim.
  - `const func string: uriFor (in string: path)` — `file://` + percent-encoding of the ASCII
    characters that would break a URI; everything else passes through, which round-trips
    exactly with the existing `pathOf`.
  - `const func array symRec: symbolsOfDocument (in string: uri)` — symbols for an open
    document, routing `.s7i` through `driverFor(pathOf(uri))`; empty for an unknown uri.

- [ ] **Step 1: Write the failing tests** — move the two existing `pathOf` checks out of
  `tests/lsp_server_test.sd7` into the new `tests/uris_test.sd7`, then add to it:

```sd7
    check("uriFor escapes the path separator survivors",
          uriFor("/tmp/a b/c#d.sd7"), "file:///tmp/a%20b/c%23d.sd7");
    check("uriFor keeps an ordinary path verbatim",
          uriFor("/home/user/seed7/lib/console.s7i"),
          "file:///home/user/seed7/lib/console.s7i");
    check("uriFor round-trips through pathOf",
          pathOf(uriFor("/tmp/a b/x.sd7")), "/tmp/a b/x.sd7");
    check("uriFor round-trips non-ascii",
          pathOf(uriFor("/tmp/日本/x.sd7")), "/tmp/日本/x.sd7");
    check("unknown uri has no symbols",
          str(length(symbolsOfDocument("file:///not/open/x.sd7"))), "0");
    openDocs @:= ["file:///tmp/x.sd7"] lsDoc.value;
    setVersion(openDocs["file:///tmp/x.sd7"],
               "$ include \"seed7_05.s7i\";\nconst proc: main is func\n  begin\n  end func;\n", 1);
    checkTrue("open document has symbols",
              length(symbolsOfDocument("file:///tmp/x.sd7")) <> 0);
```

  The non-ASCII case is a **documented ceiling, not a bug**: a raw non-ASCII code point inside
  a `file://` URI is not spec-clean, but our own `pathOf` accepts it back unchanged and so do
  eglot and Neovim. `uriFor` carries a `ponytail:` comment saying so and naming the upgrade
  path (encode UTF-8 bytes; `transport.sd7` owns byte counting, so that is a cross-module
  change and M4/M6 work).

- [ ] **Step 2: Run to verify failure** — `s7 -q -l src tests/uris_test.sd7` fails naming
  `uriFor`; `tests/lsp_server_test.sd7` keeps failing on `symbolsOfDocument`.

- [ ] **Step 3: Implement.** `src/uris.sd7` starts `include "encoding.s7i";` for the moved
  `pathOf`, then the encoder. `toPercentEncoded` is unusable (measured fact 10), so write the
  small one:

```sd7
$ include "seed7_05.s7i";
  include "encoding.s7i";

# moved verbatim from lsp_server.sd7
const func string: pathOf (in string: uri) is func
  result
    var string: path is "";
  begin
    if startsWith(uri, "file://") then
      path := fromPercentEncoded(uri[8 ..]);
    else
      path := uri;
    end if;
  end func;

const string: URI_SAFE is "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.~/";

const func string: hexEscape (in integer: cp) is func
  result
    var string: out is "";
  begin
    out := "%" <& str(cp radix 16 lpad0 2);
  end func;

# ponytail: ASCII specials only. Non-ASCII code points pass through raw; they round-trip
# with pathOf and every client we have tried. Full UTF-8 %-encoding needs the byte-length
# code that lives in transport.sd7 -- that is a deliberate cross-module change, not a line.
const func string: uriFor (in string: path) is func
  result
    var string: out is "file://";
  local
    var integer: i is 0;
    var integer: cp is 0;
  begin
    for i range 1 to length(path) do
      cp := ord(path[i]);
      if pos(URI_SAFE, path[i .. i]) <> 0 then
        out &:= path[i .. i];
      elsif cp < 32 or cp > 126 then
        out &:= path[i .. i];
      else
        out &:= hexEscape(cp);
      end if;
    end for;
  end func;
```

  `symbolsOfDocument` belongs in `lsp_server.sd7` — it needs `openDocs` and `libraryDirs`:

```sd7
const func array symRec: symbolsOfDocument (in string: uri) is func
  result
    var array symRec: out is 0 times symRec.value;
  local
    var lsDoc: doc is lsDoc.value;
  begin
    if uri in openDocs then
      doc := openDocs[uri];
      if endsWith(uri, ".s7i") then
        out := analyzeSymbols(driverFor(pathOf(uri)), libraryDirs);
      else
        out := analyzeSymbols(doc.text, libraryDirs);
      end if;
    end if;
  end func;
```

  It is the only place that decides whether a document is analysed directly or through
  `driverFor`, which keeps Task 5–9 free of the `.s7i` question.

- [ ] **Step 4: Add `uris` to the `TESTS` line of the `Makefile`, run `make test`, commit**
  `git commit -m "Add uriFor; move pathOf to uris.sd7 so features can reach it"`

---

## Task 4: `doc_index.sd7` — the `(** … *)` prose

Hover on `writeln` should say what the library says, not what we paraphrase. The comment is
already in the `.s7i`, immediately above the declaration, and measured fact 2 gives us the
file and line to look it up from.

**Files:**
- Create: `src/doc_index.sd7`
- Create: `tests/doc_index_test.sd7`
- Modify: `Makefile` (`TESTS += doc_index`)

**Interfaces:**
- Consumes: nothing but `seed7_05.s7i` and `osfiles.s7i`.
- Produces: `const func string: proseFor (in string: path, in integer: line1)` — the text of
  the `(** … *)` comment ending on the last non-blank line above `line1`, with the ` *  `
  decoration and `@param`/`@return`/`@exception` lines removed, or `""`.

- [ ] **Step 1: Write the failing test** `tests/doc_index_test.sd7`, using a fixture written
  to `/tmp` by the test itself (the same trick `analysis_test.sd7` uses for the driver probe),
  so the test never depends on where Seed7 is installed:

```sd7
$ include "seed7_05.s7i";
  include "lsp_tst.sd7";
  include "doc_index.sd7";

const proc: main is func
  local
    var string: path is "/tmp/seed7_lsp_docindex.sd7";
    var file: out is STD_NULL;
  begin
    out := open(path, "w");
    write(out, "const integer: a is 1;\n");
    write(out, "\n");
    write(out, "(**\n");
    write(out, " *  Adds two numbers.\n");
    write(out, " *  @param a First addend.\n");
    write(out, " *  @return the sum.\n");
    write(out, " *)\n");
    write(out, "const func integer: add (in integer: a, in integer: b) is\n");
    close(out);
    check("prose of the doc comment", proseFor(path, 8), "Adds two numbers.");
    check("no comment above", proseFor(path, 1), "");
    check("line inside the comment is not a declaration", proseFor(path, 4), "");
    check("absurd path is empty", proseFor("/tmp/seed7_lsp_absent.sd7", 3), "");
    report("doc_index");
  end func;
```

- [ ] **Step 2: Run to verify failure** — `s7 -q -l src tests/doc_index_test.sd7`.

- [ ] **Step 3: Implement** `src/doc_index.sd7`:

```sd7
$ include "seed7_05.s7i";
  include "osfiles.s7i";

const func array string: readLinesOf (in string: path) is func
  result
    var array string: lines is 0 times "";
  local
    var file: f is STD_NULL;
    var string: l is "";
  begin
    block
      f := open(path, "r");
      while not eof(f) do
        readln(f, l);
        lines &:= l;
      end while;
      close(f);
    exception
      catch FILE_ERROR:
        lines := 0 times "";
    end block;
  end func;

const func string: stripStar (in string: lineText) is func
  result
    var string: out is "";
  local
    var integer: first is 0;
  begin
    out := lineText;
    if startsWith(out, " ") then
      first := 1;
      while first <= length(out) and out[first] = ' ' do
        first +:= 1;
      end while;
      out := out[first ..];
    end if;
    if startsWith(out, "*") then
      out := out[2 ..];
    end if;
    if startsWith(out, " ") then
      out := out[2 ..];
    end if;
  end func;

const func boolean: blank (in string: lineText) is
  return stripStar(lineText) = "" or lineText = "";

# proseFor(path, declLine): the (** ... *) block whose last line is the last non-blank
# line before declLine. A file is re-read per hover; Seed7 stdlib sources are small and a
# hover request already costs a parse. ponytail: cache by (path, mtime) if it ever lags.
const func string: proseFor (in string: path, in integer: line1) is func
  result
    var string: out is "";
  local
    var array string: lines is 0 times "";
    var integer: idx is 0;
    var integer: stopIdx is 0;
    var integer: startIdx is 0;
    var string: body is "";
    var string: one is "";
  begin
    lines := readLinesOf(path);
    idx := pred(line1);
    while idx >= 1 and blank(lines[idx]) do
      idx := pred(idx);
    end while;
    if idx >= 1 and endsWith(stripStar(lines[idx]), "*)") then
      stopIdx := idx;
      startIdx := idx;
      while startIdx >= 1 and pos(lines[startIdx], "(**") = 0 do
        startIdx := pred(startIdx);
      end while;
      if startIdx >= 1 then
        for idx range succ(startIdx) to pred(stopIdx) do
          one := stripStar(lines[idx]);
          if one <> "" and not startsWith(one, "@") then
            if out <> "" then
              out &:= "\n";
            end if;
            out &:= one;
          end if;
        end for;
      end if;
    end if;
  end func;
```

  If `blank`/`stripStar` interact badly with the trailing empty element that `readln`-loop
  produces for a file ending in `\n` (measured: 7 source lines → 8 array entries), handle it
  in `blank` and say so in the commit.

- [ ] **Step 4: Add the suite to `Makefile`:** `TESTS := … doc_index` on the existing line.
- [ ] **Step 5: `make test`, commit** `git commit -m "Add doc_index: (** *) prose by file and line"`

---

## Task 5: `documentSymbol`

**Files:**
- Create: `src/features/document_symbol.sd7`, `src/features/kinds.sd7`
- Modify: `src/lsp_server.sd7` (include, dispatch, capability)
- Create: `tests/features_test.sd7`; modify `Makefile` (`TESTS += features`),
  `tests/transcript.py`

**Interfaces:**
- Consumes: `array symRec`, `lspWholeLine`, `jsonw`.
- Produces:
  - `const func integer: symbolKindOf (in string: cat, in string: ty)` — Seed7
    category/type → LSP `SymbolKind`.
  - `const func integer: completionKindOf (in string: cat, in string: ty)` — the same input →
    LSP `CompletionItemKind`. Both live in `kinds.sd7` because Task 8 needs the identical
    judgement and two copies of a mapping drift.
  - `const func string: documentSymbolResult (in array symRec: syms, in string: path)` →
    `DocumentSymbol[]`, flat, in declaration order. It takes a **path**, not a uri, because
    `symRec.file` is a path.

- [ ] **Step 1: Write the failing test** — create `tests/features_test.sd7` including
  `features/document_symbol.sd7`; feed it hand-built `symRec`s (no parsing here, Task 2 owns
  that) so a broken mapper cannot masquerade as a broken builder:

```sd7
    one.name := "Widget"; one.cat := "TYPEOBJECT"; one.ty := "type";
    one.file := "/p/a.sd7"; one.line1 := 4; one.sign := "const type: Widget";
    two.name := "go"; two.cat := "BLOCKOBJECT"; two.ty := "proc";
    two.file := "/p/a.sd7"; two.line1 := 9; two.sign := "const proc: go (string: s)";
    other.name := "far"; other.cat := "BLOCKOBJECT"; other.ty := "proc";
    other.file := "/p/b.sd7"; other.line1 := 2; other.sign := "const proc: far";
    syms &:= one;
    syms &:= two;
    syms &:= other;
    check("documentSymbol json", documentSymbolResult(syms, "/p/a.sd7"),
          "[{\"name\":\"Widget\",\"detail\":\"const type: Widget\",\"kind\":5,\"range\":" &
          "{\"start\":{\"line\":3,\"character\":0},\"end\":{\"line\":4,\"character\":0}}," &
          "\"selectionRange\":{\"start\":{\"line\":3,\"character\":0}," &
          "\"end\":{\"line\":4,\"character\":0}}}," &
          "{\"name\":\"go\",\"detail\":\"const proc: go (string: s)\",\"kind\":12,\"range\":" &
          "{\"start\":{\"line\":8,\"character\":0},\"end\":{\"line\":9,\"character\":0}}," &
          "\"selectionRange\":{\"start\":{\"line\":8,\"character\":0}," &
          "\"end\":{\"line\":9,\"character\":0}}}]");
    check("a document with nothing in it is an empty array",
          documentSymbolResult(syms, "/p/nowhere.sd7"), "[]");
```

  Field order is fixed by the writer, not by the reader's taste — that is the point of pinning
  the whole string. If the implementation you write emits a different order, change the code,
  not the expectation, and keep `name` first (every client displays it).

  `tests/features_test.sd7` is shared by Tasks 5–9, so declare its `local` block once here and
  let the later tasks add to it: `one`, `two`, `other`, `syms` (this task), `ea`, `eb`, `dup`,
  `wsyms`, `word` (Tasks 6–8), `docH` (Task 7), and `probe`, `active` (Task 9).

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3a: Implement `src/features/kinds.sd7`:**

```sd7
$ include "seed7_05.s7i";

# LSP SymbolKind, values from the 3.18 enumeration: Class=5, Function=12, Variable=13,
# Constant=14, EnumMember=22. Seed7 has no methods or fields to map onto, so Class stands
# for "declared type" and the mapping is deliberately lossy.
const func integer: symbolKindOf (in string: cat, in string: ty) is func
  result
    var integer: out is 13;
  begin
    if cat = "TYPEOBJECT" then
      out := 5;
    elsif cat = "ENUMLITERALOBJECT" then
      out := 22;
    elsif cat = "STRUCTOBJECT" then
      out := 14;
    elsif cat = "BLOCKOBJECT" or cat = "DECLAREDOBJECT" or cat = "ACTOBJECT" then
      out := 12;
    elsif startsWith(ty, "func ") or startsWith(ty, "proc") then
      out := 12;
    else
      out := 13;
    end if;
  end func;

# CompletionItemKind: Function=3, Class=7, EnumMember=20, Constant=21, Variable=6.
const func integer: completionKindOf (in string: cat, in string: ty) is func
  result
    var integer: out is 6;
  begin
    if cat = "TYPEOBJECT" then
      out := 7;
    elsif cat = "ENUMLITERALOBJECT" then
      out := 20;
    elsif cat = "STRUCTOBJECT" then
      out := 21;
    elsif cat = "BLOCKOBJECT" or cat = "DECLAREDOBJECT" or cat = "ACTOBJECT" then
      out := 3;
    elsif startsWith(ty, "func ") or startsWith(ty, "proc") then
      out := 3;
    else
      out := 6;
    end if;
  end func;
```

  Each `if` chain is one comparison per branch because a longer mixed `or`/`and` chain can
  fail to match at parse time (a trap this repo has already paid for once).

- [ ] **Step 3b: Implement `src/features/document_symbol.sd7`:**

```sd7
$ include "seed7_05.s7i";
  include "analysis.sd7";
  include "doc_store.sd7";
  include "features/kinds.sd7";
  include "jsonw.sd7";

const func string: documentSymbolResult (in array symRec: syms, in string: path) is func
  result
    var string: out is "";
  local
    var jsonWriter: w is jsonWriter.value;
    var integer: i is 0;
  begin
    openArray(w);
    for i range 1 to length(syms) do
      if syms[i].file = path then
        openObject(w);
          field(w, "name");   addStr(w, syms[i].name);
          field(w, "detail"); addStr(w, syms[i].sign);
          field(w, "kind");   addInt(w, symbolKindOf(syms[i].cat, syms[i].ty));
          # range and selectionRange are the same because reflection reports a declaration
          # line and no column. No children either: globalObjects lists globals only, so a
          # hierarchy would be invented, not read. The spec records this as the feature's
          # known gap (design §5), and `hierarchicalDocumentSymbolSupport` is therefore
          # never consulted.
          field(w, "range");            raw(w, lspWholeLine(syms[i].line1));
          field(w, "selectionRange");   raw(w, lspWholeLine(syms[i].line1));
        closeObject(w);
      end if;
    end for;
    out := finishJson(w);
  end func;
```

- [ ] **Step 4: Wire it up** — `handle` gains

```sd7
    elsif msg.method = "textDocument/documentSymbol" then
      uri := strAt(atKey(msg.params, "textDocument"), "uri", "");
      if uri <> "" and uri in openDocs then
        sendResult(msg.id, documentSymbolResult(symbolsOfDocument(uri), pathOf(uri)));
      else
        sendResult(msg.id, "null");
      end if;
```

  and `capabilitiesJson` gains `field(w, "documentSymbolProvider"); addBool(w, TRUE);`.
- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** — `symbolKindOf(cat, ty)` maps Seed7 categories to `SymbolKind`
  (values from LSP 3.18: Class=5, Function=12, Variable=13, Constant=14, Enum=10,
  EnumMember=22, Struct=23, Interface=11, Operator=25): `TYPEOBJECT` → 5,
  `ENUMLITERALOBJECT` → 22, `BLOCKOBJECT`/`DECLAREDOBJECT`/`ACTOBJECT` whose type starts with
  `func ` or `proc` → 12, `STRUCTOBJECT`/`REFOBJECT`/`CONSTENUMOBJECT` → 14 when `isVar` is
  false and 13 when true, everything else → 13. Ranges are line-based, and that is the
  spec's stated gap for this feature (`range` = the whole declaration line,
  `selectionRange` = the same, because reflection has no columns).
- [ ] **Step 4: Wire it up** — `handle` gains

```sd7
    elsif msg.method = "textDocument/documentSymbol" then
      uri := strAt(atKey(msg.params, "textDocument"), "uri", "");
      sendResult(msg.id, documentSymbolResult(openDocs[uri],
                   symbolsOfDocument(uri), pathOf(uri)));
```

  and `capabilitiesJson` gains `field(w, "documentSymbolProvider"); addBool(w, TRUE);`.
  A `didOpen` for a document that is not in `openDocs` must not raise: guard with
  `if uri in openDocs then … else sendResult(msg.id, "null")`.
- [ ] **Step 5: `make test`; add a transcript case** that opens `tests/programs/symbols.sd7`
  and expects a `documentSymbol` answer whose array is non-empty and contains `"Widget"`.
- [ ] **Step 6: Commit** `git commit -m "Add textDocument/documentSymbol"`

---

## Task 6: `definition`

**Files:**
- Create: `src/features/definition.sd7`
- Modify: `src/lsp_server.sd7` (include, dispatch, capability), `tests/features_test.sd7`,
  `tests/transcript.py`

**Interfaces:**
- Consumes: `array symRec`, `wordRef` (Task 1), `uriFor` (Task 3), `lspWholeLine` (Task 1),
  `jsonw`.
- Produces: `const func string: definitionResult (in array symRec: syms, in wordRef: word)`
  → `Location[]`, or `null` when there is no token under the cursor.

- [ ] **Step 1: Write the failing test** — append to `tests/features_test.sd7`. Build the
  input by hand (no parsing here; Task 2 owns that) so a broken mapper cannot masquerade as a
  broken builder:

```sd7
    var symRec: ea is symRec.value;
    var symRec: eb is symRec.value;
    var symRec: dup is symRec.value;
    var array symRec: wsyms is 0 times symRec.value;
    var wordRef: word is wordRef.value;

    ea.name := "writeln"; ea.cat := "BLOCKOBJECT"; ea.file := "/tmp/a.sd7";
    ea.line1 := 13; ea.sign := "const proc: writeln";
    eb.name := "writeln"; eb.cat := "ACTOBJECT"; eb.file := "/tmp/b c.s7i";
    eb.line1 := 1; eb.sign := "const proc: writeln";
    dup.name := "writeln"; dup.cat := "BLOCKOBJECT"; dup.file := "/tmp/a.sd7";
    dup.line1 := 13; dup.sign := "const proc: writeln";
    wsyms &:= ea;
    wsyms &:= eb;
    wsyms &:= dup;

    check("no token means null", definitionResult(wsyms, wordRef.value), "null");
    word.word := "nosuchname";
    check("unknown token is the empty array", definitionResult(wsyms, word), "[]");
    word.word := "writeln";
    check("locations dedupe and percent-encode",
          definitionResult(wsyms, word),
          "[{\"uri\":\"file:///tmp/a.sd7\",\"range\":" &
          "{\"start\":{\"line\":12,\"character\":0},\"end\":{\"line\":13,\"character\":0}}}," &
          "{\"uri\":\"file:///tmp/b%20c.s7i\",\"range\":" &
          "{\"start\":{\"line\":0,\"character\":0},\"end\":{\"line\":1,\"character\":0}}}]");
    check("locations are capped", str(uriCount(definitionResult(hundredSyms(), word))), "20");
```

  `uriCount` is test scaffolding: count `{"uri":` occurrences with a `pos` loop that moves
  past each hit. `hundredSyms` returns 25 records named `sym` on 25 distinct lines — define it
  here; Task 8's cap check reuses it.

- [ ] **Step 2: Run to verify failure** — `s7 -q -l src tests/features_test.sd7` fails naming
  `definitionResult`.

- [ ] **Step 3: Implement** `src/features/definition.sd7`:

```sd7
$ include "seed7_05.s7i";
  include "analysis.sd7";
  include "doc_store.sd7";
  include "uris.sd7";
  include "jsonw.sd7";

const integer: MAX_LOCATIONS is 20;

const type: locSeen is hash [string] integer;

const func string: definitionResult (in array symRec: syms, in wordRef: word) is func
  result
    var string: out is "null";
  local
    var jsonWriter: w is jsonWriter.value;
    var locSeen: seen is locSeen.EMPTY_HASH;
    var string: keyStr is "";
    var integer: emitted is 0;
    var integer: i is 0;
  begin
    if word.word <> "" then
      openArray(w);
      for i range 1 to length(syms) do
        if syms[i].name = word.word then
          keyStr := syms[i].file <& "|" <& str(syms[i].line1);
          if keyStr not in seen and emitted < MAX_LOCATIONS then
            seen @:= [keyStr] 1;
            emitted +:= 1;
            openObject(w);
              field(w, "uri"); addStr(w, uriFor(syms[i].file));
              # Reflection reports a declaration line and no column, so a location is
              # the whole line. The alternative is a second position function, and the
              # spec forbids that (AGENTS.md: ask lspRange to clamp instead).
              field(w, "range"); raw(w, lspWholeLine(syms[i].line1));
            closeObject(w);
          end if;
        end if;
      end for;
      out := finishJson(w);
    end if;
  end func;
```

  The named `locSeen` hash type is required (`hash [k] v` cannot be anonymous) and the name is
  per-file on purpose: `diagnostics.sd7` already owns a `seenHash`, and two files declaring the
  same type name is a redeclaration error the moment one includes the other.

- [ ] **Step 4: Dispatch and advertise** — in `lsp_server.sd7`, before `handle`:

```sd7
const func wordRef: wordOfRequest (in rpcMsg: msg) is func
  result
    var wordRef: out is wordRef.value;
  local
    var string: uri is "";
    var jsonValue: pos is jsonValue.value;
  begin
    uri := strAt(atKey(msg.params, "textDocument"), "uri", "");
    pos := atKey(msg.params, "position");
    if uri <> "" and uri in openDocs then
      out := wordAt(openDocs[uri], intAt(pos, "line", 0), intAt(pos, "character", 0));
    end if;
  end func;
```

  and in the dispatch chain:

```sd7
    elsif msg.method = "textDocument/definition" then
      uri := strAt(atKey(msg.params, "textDocument"), "uri", "");
      sendResult(msg.id, definitionResult(symbolsOfDocument(uri), wordOfRequest(msg)));
```

  plus `field(w, "definitionProvider"); addBool(w, TRUE);` in `capabilitiesJson`.
  `wordOfRequest` is shared with Tasks 7 and 8 for exactly the reason it exists: the uri check,
  the position accessors and the `wordAt` call must not be written three times.
- [ ] **Step 5: Transcript case** — open `tests/programs/symbols.sd7`, request definition on
  `reportWidget` (line 12 0-based, character 8) and assert one location whose `uri` ends in
  `symbols.sd7` and whose `start.line` is 12; then on `writeln` and assert the uri ends in
  `.s7i` (which library wins depends on the installed Seed7, so assert the suffix and nothing
  more).
- [ ] **Step 6: `make test`, commit** `git commit -m "Add textDocument/definition"`

---

## Task 7: `hover`

**Files:**
- Create: `src/features/hover.sd7`
- Modify: `src/lsp_server.sd7` (include, dispatch, capability), `tests/features_test.sd7`,
  `tests/transcript.py`

**Interfaces:**
- Consumes: `array symRec`, `wordRef`, `lsDoc`, `lspRangePair`, `proseFor` (Task 4), `jsonw`.
- Produces:
  - `const func string: hoverText (in array symRec: syms, in wordRef: word)` → the markdown
    body, or `""` when there is nothing to say. Separate from the envelope so the fence/prose
    rules are testable without JSON.
  - `const func string: hoverResult (in lsDoc: doc, in array symRec: syms, in wordRef: word)`
    → `Hover | null`.

- [ ] **Step 1: Write the failing test**

```sd7
    word.word := "writeln";
    check("hover body is one fence with both overloads",
          hoverText(wsyms, word),
          "```seed7\nconst proc: writeln\n```");
    ea.sign := "const func integer: totalSize (Widget: w, integer: times)";
    eb.sign := "const proc: totalSize (string: s)";
    check("hover lists distinct signatures",
          hoverText(wsyms, word),
          "```seed7\nconst func integer: totalSize (Widget: w, integer: times)\n" &
          "const proc: totalSize (string: s)\n```");
    check("hover of an unknown word is empty",
          hoverText(wsyms, wordRef.value), "");
    check("hover envelope carries the range",
          hoverResult(docH, wsyms, word),
          "{\"contents\":{\"kind\":\"markdown\",\"value\":" &
          "\"```seed7\\nconst func integer: totalSize (Widget: w, integer: times)\\n" &
          "const proc: totalSize (string: s)\\n```\"},\"range\":" &
          "{\"start\":{\"line\":0,\"character\":6},\"end\":{\"line\":0,\"character\":12}}}");
```

  `docH` is a document set to `"  x = writeln(y);\n"`, where `writeln` starts at 1-based
  column 7 and is 7 wide — so `word.line1 = 1`, `word.column1 = 7`, `word.width = 7`, and
  `lspRangePair` yields characters 6 and 12 (the end is the *last character* of the token as a
  0-based column, not one past it; `lspRangePair`'s formula explains why). The prose branch gets its own check against a
  temporary file written by the test — `proseFor` is Task 4's and is already covered there, so
  pin only that prose appears after the fence when it exists:

```sd7
    check("prose follows the fence",
          pos(hoverText(proseSyms, word), "\n\nAdds two numbers.") <> 0, "TRUE");
```

  with `proseSyms[1].file` pointing at the fixture `proseFor` can read. `checkTrue` is the
  harness form for a boolean; prefer it over comparing to `"TRUE"`.

- [ ] **Step 2: Run to verify failure** — naming `hoverText` / `hoverResult`.
- [ ] **Step 3: Implement** `src/features/hover.sd7`:

```sd7
$ include "seed7_05.s7i";
  include "analysis.sd7";
  include "doc_store.sd7";
  include "doc_index.sd7";
  include "jsonw.sd7";

const integer: MAX_HOVER_OVERLOADS is 5;

const func string: hoverText (in array symRec: syms, in wordRef: word) is func
  result
    var string: out is "";
  local
    var array string: shown is 0 times "";
    var string: prose is "";
    var integer: i is 0;
  begin
    for i range 1 to length(syms) do
      if syms[i].name = word.word and syms[i].sign not in shown and
         length(shown) < MAX_HOVER_OVERLOADS then
        shown &:= syms[i].sign;
        if prose = "" then
          prose := proseFor(syms[i].file, syms[i].line1);
        end if;
      end if;
    end for;
    if length(shown) <> 0 then
      out := "```seed7\n";
      for i range 1 to length(shown) do
        out &:= shown[i];
        if i < length(shown) then
          out &:= "\n";
        end if;
      end for;
      out := out <& "\n```";
      if prose <> "" then
        out := out <& "\n\n" <& prose;
      end if;
    end if;
  end func;

const func string: hoverResult (in lsDoc: doc, in array symRec: syms,
                                in wordRef: word) is func
  result
    var string: out is "null";
  local
    var jsonWriter: w is jsonWriter.value;
    var string: body is "";
  begin
    body := hoverText(syms, word);
    if body <> "" then
      openObject(w);
        field(w, "contents");
        openObject(w);
          field(w, "kind");  addStr(w, "markdown");
          field(w, "value"); addStr(w, body);
        closeObject(w);
        field(w, "range");
        raw(w, lspRangePair(doc, word.line1, word.column1, word.width));
      closeObject(w);
      out := finishJson(w);
    end if;
  end func;
```

  The fence is closed before any prose is appended, and `addStr` escapes the newlines — that
  ordering is why the test's expected string contains `\n` twice over: once as the literal
  newline inside a Seed7 string, once as the JSON `\n` in the compared output.
- [ ] **Step 4: Dispatch + capability** — in `handle`, next to the definition branch:

```sd7
    elsif msg.method = "textDocument/hover" then
      uri := strAt(atKey(msg.params, "textDocument"), "uri", "");
      if uri <> "" and uri in openDocs then
        sendResult(msg.id, hoverResult(openDocs[uri], symbolsOfDocument(uri),
                     wordOfRequest(msg)));
      else
        sendResult(msg.id, "null");
      end if;
```

  and `field(w, "hoverProvider"); addBool(w, TRUE);` in `capabilitiesJson`.
- [ ] **Step 5: Transcript case** — hover on `totalSize` in the fixture; assert the reply's
  `contents.value` contains `const func integer: totalSize`. Then hover `writeln` and assert
  the value is non-empty — its prose comes from whichever Seed7 is installed, so do not pin
  its text.
- [ ] **Step 6: `make test`, commit** `git commit -m "Add textDocument/hover with signatures and (** *) prose"`

---

## Task 8: `completion`

**Files:**
- Create: `src/features/completion.sd7`
- Modify: `src/lsp_server.sd7` (include, dispatch, capability), `tests/features_test.sd7`,
  `tests/transcript.py`

**Interfaces:**
- Consumes: `array symRec`, `wordRef`, `completionKindOf` (Task 5), `jsonw`.
- Produces:
  - `const func string: prefixOf (in wordRef: word, in integer: character0)`
  - `const func string: completionResult (in array symRec: syms, in wordRef: word,
    in integer: character0)` → `CompletionItem[]`, or a `CompletionList` when capped.

- [ ] **Step 1: Write the failing tests** — covering the four rules separately:

```sd7
    word.word := "tot"; word.line1 := 5; word.column1 := 12; word.width := 3;
    check("prefix is the part left of the cursor", prefixOf(word, 14), "to");
    check("prefix at the end of the word is the whole word", prefixOf(word, 15), "tot");
    check("cursor before the word gives an empty prefix", prefixOf(word, 11), "");
    checkTrue("completions include the matching symbol",
              pos(completionResult(wsymsNamed("totalSize"), word, 15),
                  "\"label\":\"totalSize\"") <> 0);
    checkTrue("completions never offer the exact word",
              pos(completionResult(wsymsNamed("totalSize"), exactWord("totalSize"), 20),
                  "\"label\":\"totalSize\"") = 0);
    checkTrue("keywords appear after symbols",
              startsWith(completionResult(0 times symRec.value, exactWord("co"), 4), "[") and
              pos(completionResult(0 times symRec.value, exactWord("co"), 4),
                  "\"label\":\"const\"") <> 0);
    checkTrue("items collapse across overloads",
              str(labelCount(completionResult(overloadedSyms(), exactWord("wri"), 6))) =
              str(labelCount(completionResult(wsymsNamed("writeln"), exactWord("wri"), 6))));
    checkTrue("a capped list becomes a CompletionList",
              startsWith(completionResult(hundredSyms(), exactWord("sy"), 5),
                         "{\"isIncomplete\":true,\"items\":["));
```

  `exactWord(nm)` and the `labelCount` loop are test scaffolding. `wsymsNamed(nm)` returns the
  hand-built fixture records renamed to `nm`.

- [ ] **Step 2: Run to verify failure** — naming `prefixOf` / `completionResult`.
- [ ] **Step 3: Implement** `src/features/completion.sd7`:

```sd7
$ include "seed7_05.s7i";
  include "analysis.sd7";
  include "doc_store.sd7";
  include "features/kinds.sd7";
  include "jsonw.sd7";

const integer: MAX_COMPLETIONS is 100;

const type: nameSeen is hash [string] integer;

# The base vocabulary only. Seed7 syntax is declared by $-pragmas in seed7_05.s7i, so this
# list can never be complete; it is copied from the vocabulary seed7-mode tests against
# (~/seed7-mode/seed7-mode.el, seed7--statement-enclosing-keywords and
# seed7--declaration-intro-keywords) rather than invented here.
const array string: SEED7_KEYWORDS is
  {"attr", "block", "by", "case", "catch", "const", "do", "else", "elsif", "end",
   "enum", "exception", "for", "func", "global", "if", "in", "inout", "interface",
   "is", "key", "local", "nested", "new", "otherwise", "out", "proc", "range",
   "ref", "repeat", "result", "return", "struct", "then", "type", "until", "val",
   "var", "varfunc", "while"};

const func string: prefixOf (in wordRef: word, in integer: character0) is func
  result
    var string: out is "";
  local
    var integer: left is 0;
  begin
    left := character0 - word.column1 + 1;
    if left > word.width then
      left := word.width;
    end if;
    if left > 0 then
      out := word.word[1 .. left];
    end if;
  end func;
```

  `left` counts UTF-16 units against a token that is by construction ASCII (an identifier or
  an operator run), so no conversion is needed; the day a non-ASCII identifier is legal in
  Seed7, this line is the one to change — put that as a comment above `prefixOf`.

  Then the builder. Emit a plain array, and re-wrap as a `CompletionList` only when the cap
  bites, because `isIncomplete` exists only on `CompletionList`:

```sd7
const func string: completionResult (in array symRec: syms, in wordRef: word,
                                     in integer: character0) is func
  result
    var string: out is "";
  local
    var jsonWriter: w is jsonWriter.value;
    var nameSeen: seen is nameSeen.EMPTY_HASH;
    var string: prefix is "";
    var string: nm is "";
    var integer: i is 0;
    var integer: emitted is 0;
    var boolean: capped is FALSE;
  begin
    prefix := prefixOf(word, character0);
    openArray(w);
    for i range 1 to length(syms) do
      nm := syms[i].name;
      if startsWith(nm, prefix) and nm <> prefix and nm not in seen and
         emitted < MAX_COMPLETIONS then
        seen @:= [nm] 1;
        emitted +:= 1;
        openObject(w);
          field(w, "label"); addStr(w, nm);
          field(w, "kind");  addInt(w, completionKindOf(syms[i].cat, syms[i].ty));
          field(w, "detail"); addStr(w, syms[i].sign);
          field(w, "sortText"); addStr(w, "0" <& nm);
        closeObject(w);
      end if;
    end for;
    for i range 1 to length(SEED7_KEYWORDS) do
      nm := SEED7_KEYWORDS[i];
      if startsWith(nm, prefix) and nm <> prefix and nm not in seen and
         emitted < MAX_COMPLETIONS then
        seen @:= [nm] 1;
        emitted +:= 1;
        openObject(w);
          field(w, "label"); addStr(w, nm);
          field(w, "kind"); addInt(w, 14);
          field(w, "sortText"); addStr(w, "1" <& nm);
        closeObject(w);
      end if;
    end for;
    out := finishJson(w);
    capped := emitted = MAX_COMPLETIONS;
    if capped then
      out := "{\"isIncomplete\":true,\"items\":" <& out <& "}";
    end if;
  end func;
```

  No `textEdit`: the client already holds the typed prefix and replaces it. No
  `additionalTextEdits`, no snippets, no `commitCharacters` — none of them can be got right
  without the M4 scanner, and a wrong `commitCharacters` is worse than none.
- [ ] **Step 4: Dispatch + capability** — in `handle`:

```sd7
    elsif msg.method = "textDocument/completion" then
      uri := strAt(atKey(msg.params, "textDocument"), "uri", "");
      if uri <> "" and uri in openDocs then
        sendResult(msg.id, completionResult(symbolsOfDocument(uri), wordOfRequest(msg),
                     intAt(atKey(msg.params, "position"), "character", 0)));
      else
        sendResult(msg.id, "[]");
      end if;
```

  and in `capabilitiesJson` an empty options object — `field(w, "completionProvider");
  openObject(w); closeObject(w);`. Identifier characters must not be listed as trigger
  characters (the client triggers on those itself), and `.` is left out because struct-member
  completion is out of scope.
- [ ] **Step 5: Transcript case** — after typing `total` on a line, completion contains
  `"label":"totalSize"`.
- [ ] **Step 6: `make test`, commit** `git commit -m "Add textDocument/completion"`

---

## Task 9: `signatureHelp`

**Files:**
- Create: `src/features/signature_help.sd7`
- Modify: `src/lsp_server.sd7` (include, dispatch, capability), `tests/features_test.sd7`,
  `tests/transcript.py`

**Interfaces:**
- Consumes: `array symRec`, `nameChar` (Task 1), `jsonw`.
- Produces:
  - `const func string: callContext (in string: text, in integer: offset,
    inout integer: active)` → the callee name (or `""`), with the 0-based argument index in
    `active`.
  - `const func string: signatureHelpResult (in array symRec: syms, in string: callee,
    in integer: active)` → `SignatureHelp | null`.

- [ ] **Step 1: Write the failing tests** — `callContext` is the interesting one and it is
  pure character work, so test it on literal strings with an explicit offset:

```sd7
    var string: probe is "go(x";
    active := 0;
    check("callee is the name before the owning paren",
          callContext(probe, length(probe) + 1, active), "go");
    check("no comma yet", str(active), "0");
    probe := "reportWidget(x, hits";
    active := 0;
    check("longer callee still resolves", callContext(probe, length(probe) + 1, active),
          "reportWidget");
    check("second argument is active", str(active), "1");
    probe := "f(a, (b, c";
    active := 0;
    check("a bare paren has no callee", callContext(probe, length(probe) + 1, active), "");
    check("commas before the inner paren do not count", str(active), "1");
    probe := "writeln done";
    active := 0;
    check("no unclosed paren to the left", callContext(probe, 13, active), "");
    check("nothing counted", str(active), "0");
    probe := "go(\"a, b\", x";
    active := 0;
    check("a comma inside a string literal counts", callContext(probe, 13, active), "go");
    check("the ceiling is pinned, not hoped away", str(active), "2");
```

  The last pair is deliberate: the rule is character-local, so a comma inside `"…"` is counted
  as an argument separator and `activeParameter` is wrong for that call. That is the price of
  shipping this before `scan.sd7` (M4), and the check exists so the regression is visible when
  the scanner lands. A call nested inside another call resolves to **no** callee when the
  inner parenthesis is a grouping `(...)` rather than a call — also correct behaviour, since a
  grouping paren has no signature to show.

  Then the envelope, with its own records so `params` is populated:

```sd7
    var symRec: h1 is symRec.value;
    var symRec: h2 is symRec.value;
    var array symRec: hsyms is 0 times symRec.value;
    h1.name := "writeln"; h1.cat := "BLOCKOBJECT"; h1.file := "/tmp/a.sd7";
    h1.line1 := 3; h1.sign := "const proc: writeln (string: s)";
    h1.params := {"string: s"};
    h2.name := "writeln"; h2.cat := "DECLAREDOBJECT"; h2.file := "/tmp/a.sd7";
    h2.line1 := 7; h2.sign := "const func integer: writeln (integer: n)";
    h2.params := {"integer: n"};
    hsyms &:= h1;
    hsyms &:= h2;
    check("no callee means null", signatureHelpResult(hsyms, "", 0), "null");
    check("one signature per overload, active parameter reported",
          signatureHelpResult(hsyms, "writeln", 1),
          "{\"signatures\":[{\"label\":\"const proc: writeln (string: s)\",\"parameters\":[" &
          "{\"label\":\"string: s\"}]},{\"label\":" &
          "\"const func integer: writeln (integer: n)\",\"parameters\":" &
          "[{\"label\":\"integer: n\"}]}],\"activeSignature\":0,\"activeParameter\":1}");
    checkTrue("an active parameter past the last one is reported, not dropped",
              pos(signatureHelpResult(hsyms, "writeln", 9),
                  "\"activeParameter\":9") <> 0);
```

  `params := {"string: s"}` uses Seed7's array literal; if the parser rejects it in a struct
  field assignment, build the array with `&:=` on a local and assign that.

- [ ] **Step 2: Run to verify failure** — naming `callContext` / `signatureHelpResult`.
- [ ] **Step 3: Implement** `src/features/signature_help.sd7`:

```sd7
$ include "seed7_05.s7i";
  include "analysis.sd7";
  include "doc_store.sd7";
  include "jsonw.sd7";

const integer: MAX_SIGNATURES is 10;

# Walking back from the cursor to the '(' that still owns it, counting commas on the way.
# ponytail: a comma inside a "..." or a (* *) counts, and a call split over lines works but
# is not nested-aware. scan.sd7 (M4) owns both; this is the difference between wrong in a
# rare case and absent in every case.
const func string: callContext (in string: text, in integer: offset,
                                inout integer: active) is func
  result
    var string: out is "";
  local
    var integer: i is 0;
    var integer: depth is 0;
    var integer: stop is 0;
    var integer: lastIdx is 0;
  begin
    active := 0;
    i := pred(offset);
    while i >= 1 and stop = 0 do
      if text[i] = ')' then
        depth +:= 1;
      elsif text[i] = '(' then
        if depth = 0 then
          stop := i;
        else
          depth := pred(depth);
        end if;
      elsif text[i] = ',' and depth = 0 then
        active +:= 1;
      end if;
      i := pred(i);
    end while;
    if stop <> 0 then
      i := pred(stop);
      while i >= 1 and text[i] = ' ' do
        i := pred(i);
      end while;
      if i >= 1 and nameChar(text[i]) then
        lastIdx := i;
        while pred(i) >= 1 and nameChar(text[pred(i)]) do
          i := pred(i);
        end while;
        out := text[i .. lastIdx];
      end if;
    end if;
  end func;

const func string: signatureHelpResult (in array symRec: syms, in string: callee,
                                        in integer: active) is func
  result
    var string: out is "null";
  local
    var jsonWriter: w is jsonWriter.value;
    var array string: shown is 0 times "";
    var integer: emitted is 0;
    var integer: i is 0;
    var integer: p is 0;
    var integer: activeIdx is 0;
  begin
    if callee <> "" then
      openObject(w);
        field(w, "signatures");
        openArray(w);
          for i range 1 to length(syms) do
            if syms[i].name = callee and syms[i].sign not in shown and
               emitted < MAX_SIGNATURES then
              shown &:= syms[i].sign;
              emitted +:= 1;
              openObject(w);
                field(w, "label"); addStr(w, syms[i].sign);
                field(w, "parameters");
                openArray(w);
                  for p range 1 to length(syms[i].params) do
                    openObject(w);
                      field(w, "label"); addStr(w, syms[i].params[p]);
                    closeObject(w);
                  end for;
                closeArray(w);
              closeObject(w);
            end if;
          end for;
        closeArray(w);
        if emitted <> 0 then
          field(w, "activeSignature"); addInt(w, 0);
          activeIdx := active;
          if activeIdx < 0 then
            activeIdx := 0;
          end if;
          field(w, "activeParameter"); addInt(w, activeIdx);
          out := finishJson(w);
        end if;
      closeObject(w);
    end if;
  end func;
```

  Note the `out` assignment *inside* the `if`: `finishJson` must not run when `signatures` came
  back empty, because a `SignatureHelp` with no signatures is indistinguishable from "no help"
  and `null` is what the client should see. That leaves an open object on the writer when
  `emitted = 0`, which is why `out` still reads `"null"` — the writer is discarded, not
  finished. If `jsonw` gives you trouble there, finish into a throwaway and assert the shape
  in the test rather than special-casing the string.
- [ ] **Step 4: Dispatch + capability**

```sd7
    elsif msg.method = "textDocument/signatureHelp" then
      uri := strAt(atKey(msg.params, "textDocument"), "uri", "");
      offset := 0;
      if uri <> "" and uri in openDocs then
        offset := charIndexOf(openDocs[uri],
                              intAt(atKey(msg.params, "position"), "line", 0),
                              intAt(atKey(msg.params, "position"), "character", 0));
      end if;
      callee := callContext(docTextOf(uri), offset, activeArg);
      sendResult(msg.id, signatureHelpResult(symbolsOfDocument(uri), callee, activeArg));
```

  with `var integer: activeArg is 0;`, `var integer: offset is 0;` and `var string: callee is
  "";` added to `handle`'s `local` block — `callContext` mutates `activeArg` through an `inout`
  parameter, so it must not be nested inside the call that reads it. a one-line
  `const func string: docTextOf (in string: uri)` next to `symbolsOfDocument`, and
  `field(w, "signatureHelpProvider"); openObject(w); field(w, "triggerCharacters");
  openArray(w); addStr(w, "("); addStr(w, ","); closeArray(w); closeObject(w);`.

  Do not emit `retriggerCharacters` (no client asks yet) and do not emit `activeParameter`
  as `null` (`noActiveParameterSupport` is a 3.18 client capability we do not read).
- [ ] **Step 5: Transcript case** — `signatureHelp` inside `reportWidget("proto", |` returns
  `activeParameter: 1` and one signature whose label contains `label`/`counter`; inside
  `totalSize(21, |` returns the `totalSize` label.
- [ ] **Step 6: `make test`, commit** `git commit -m "Add textDocument/signatureHelp"`

---

## Task 10: capabilities, invariants, documentation

**Files:** Modify `src/lsp_server.sd7`, `AGENTS.md`, `README.md`,
`docs/superpowers/specs/2026-09-10-seed7-lsp-server-design.md`.

- [ ] **Step 1: Assert the capability set is exactly the handled set** — in
  `tests/lsp_server_test.sd7`, replace the "no capability for an unhandled request" check with
  a table check: for each of `definitionProvider`, `hoverProvider`,
  `documentSymbolProvider`, `completionProvider`, `signatureHelpProvider`, `textDocumentSync`
  the capabilities JSON contains it, and for each of `referencesProvider`, `renameProvider`,
  `implementationProvider`, `typeDefinitionProvider`, `declarationProvider`,
  `foldingRangeProvider`, `selectionRangeProvider`, `semanticTokensProvider`,
  `diagnosticProvider`, `workspaceSymbolProvider` it does **not**. This is the guard that
  keeps the M2 mistake from recurring.
- [ ] **Step 2: Fix the invariant greps.** They are `src/*.sd7` patterns and feature files now
  live in `src/features/`. Update `AGENTS.md` invariants 1, 4 and 6 to
  `grep -rn 'progs.s7i' src/`, `grep -rn 'jsonw.sd7' src/features/` … and
  `grep -rn 'addStr(w, str(' --include='*.sd7' src/`, then re-run them and confirm the counts
  are unchanged (one `progs.s7i`, empty `addStr(w, str(`).
- [ ] **Step 3: Record the containment question honestly.** AGENTS.md currently claims the
  `-32603` net in `main.sd7` is unreachable because "every accessor is total". After this
  milestone that is nearly false — `getType`/`formalParams` raise, and Task 2 wrapped them. The
  net is still unreachable *from real input*, so do not invent a trigger: change the wording to
  say the reflection accessors raise and are made total in `analysis.sd7`, and that the net
  stays as defence in depth.
- [ ] **Step 4: README.** Move definition/hover/completion/`signatureHelp`/`documentSymbol`
  out of "What does not work yet", state that hover prose comes from the installed library's
  own `(** *)` comments, keep the note that `s7i` buffers analyse stale from disk (R-F10), and
  update the check count in the `make test` line.
- [ ] **Step 5: Spec.** In §5's table, mark the four "known gap" columns as realised (line-based
  ranges for symbols, whole-line definition range, `syobject` unused for `Location`,
  `match`-based hover still v2), and in §8 note that the trust gate and R-F10 were split out of
  M3 into their own plans, and that local-variable completion moved to a follow-up.
- [ ] **Step 6: `make test`, commit** `git commit -m "Advertise M3 capabilities; update docs and invariant greps"`

---

## Exit criteria (spec §8, M3 row, minus the two split-out items)

`documentSymbol` and `definition` work on a file that uses the stdlib and on a `.s7i` buffer
via the driver wrapper; hover shows a signature that matches the text in the `.s7i` plus the
library's own prose; completion offers the stdlib names under a prefix; `signatureHelp`
picks the right parameter for a two-argument call. All of it inside `make test` with no editor
attached, and every advertised capability answered.
