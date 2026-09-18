# M4 — Scanner and Token-Backed Features: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the server one Seed7 lexical machine (`src/scan.sd7`), make the text mask and every
token question a consumer of it, and build `textDocument/foldingRange`, `selectionRange` and
`semanticTokens` on the resulting stream.

**Architecture:** `scan.sd7` owns Seed7's lexical grammar and exposes a cursor plus `nextToken`;
callers stream it and keep only what their answer needs, so no token array is ever held. The
mask lives in `doc_store.lsDoc` as one cached string, and one analysis per document version is
cached beside `openDocs` for the symbol features and the token name classes.

**Tech Stack:** Seed7 (s7 5.4.10) only; LSP 3.18 over stdio; Python 3 for the transcript harness.
No new dependencies, none available to add.

**Spec:** `docs/superpowers/specs/2026-09-18-seed7-lsp-m4-scanner-and-token-features-design.md`
— read it before Task 1. It carries the measurements that justify every shape here, and the
decisions Q1–Q7 that this plan must not quietly revisit. Work happens in the existing worktree
`.worktrees/m4-scan-and-token-features` on branch `m4-scan-and-token-features`.

## Global Constraints

Applies to every task. Values are copied from the spec and the repo's own rules.

* Seed7 only, one process. Nothing in `src/` may be replaced by a shell-out or a second language.
* **Red first.** Write the check, run it, see it fail for the reason you named, then implement.
  `make test` before and after every task.
* Only `src/analysis.sd7` imports `progs.s7i`. `grep -rn 'progs.s7i' src/` must show one line.
* Only `src/doc_store.sd7` converts LSP positions to string offsets, and only
  `src/utf8bytes.sd7` (Task 1) knows code-point widths. `transport.sd7` owns outbound byte counts.
* Only `src/*.sd7` and `src/features/*.sd7` build LSP shapes; `scan.sd7` returns Seed7 data.
* Capabilities stay static in `InitializeResult`, and a capability is advertised only once its
  method is answered. No dynamic registration.
* Every outbound byte goes through `jsonw.sd7`. `grep -rn 'addStr(w, str(' --include='*.sd7' src/`
  stays empty. Never `str()` on a `jsonValue`.
* Never let an exception reach stdout — it corrupts the protocol channel. A scanner branch that
  can raise needs a check that reaches it (spec §7).
* A suite that fails to analyse prints nothing and exits 0. Grade the `N checks, M failed` line;
  `make test-<module>` already does.
* Seed7 traps this plan's code is written around, each met while compiling the snippets below:
  a body opened `is func` closes `end func` — never `end proc`, and no `end proc;` exists
  anywhere in `lib/*.s7i`; a `for` loop bound is `range a to b`, since `range a .. b` does not
  parse (`..` is the set/array range operator, not a loop bound); declare before use, so `maskOf`
  and `tokenAt` sit *after* `nextToken` in the file; `key`, `len`, `line`, `sum`, `pos`, `at`,
  `idx`, `NL` are taken names, and a struct field named `pos`/`at`/`idx` cannot be selected at all
  (`c.at` parses as `at(c, .)`); a `func` with a `result` clause assigns its result and never
  `return`s it; an `inout` result cannot be nested inside the call that reads it; strings are
  `"...\"..."`, a tab is `'\9;'`, the quote character is `'''`, `''''` is a parse error and a
  backslash char literal does not parse (`chr(92)`, named `BACKSLASH`); an array literal is
  `[]("a", "b")`; split long `and`/`or` chains into small `const func boolean:` one-liners; `s7`
  reports analysis errors on stderr **and exits 0**; and `writeln` of a string holding a
  non-ASCII character raises `RANGE_ERROR` on a plain stdout, which is why the fixtures below
  assert on numbers, lengths and bracket counts rather than on printed token text.
* No visitor API. Probed: an `in proc:` parameter is evaluated in the **caller's** scope, so a
  scanner cannot hand its current token to a caller-supplied handler. Every consumer therefore
  writes its own `skipWhitespace`/`nextToken` loop, and what is shared is the *machine*, not the
  walk. Do not "fix" the duplicated loop.
* `make test` at HEAD must stay green. Task 7 and Task 9 rewrite code other features read;
  their exit criterion is that the existing 203 unit checks and 53 wire checks pass unchanged,
  except where a check is listed below as deliberately re-pinned.

## File Structure

| file | task | responsibility |
|---|---|---|
| `src/utf8bytes.sd7` | 1 | code-point widths: bytes per char (UTF-8) and units per char (UTF-16), plus whole-string forms |
| `src/transport.sd7` | 1 | modified — framing and outbound byte counts only; the width table moves out |
| `src/doc_store.sd7` | 1, 7, 8 | modified — consumes widths; owns the mask cache; `wordAt` reads tokens |
| `src/scan.sd7` | 2–7 | the one lexical machine: kinds, `tok`, `scanCursor`, `nextToken`, `skipWhitespace`, `maskOf` |
| `tests/scan_test.sd7` | 2–7 | the lexical contract, one check per rule |
| `tests/doc_store_test.sd7` | 7, 8 | mask as projection; `wordAt` boundaries |
| `src/lsp_server.sd7` | 9, 10, 11, 12 | caches, dispatch, capabilities |
| `src/analysis.sd7` | 9 | modified only where a total wrapper must be added for the classifier |
| `src/features/folding_range.sd7` | 10 | region stack → `FoldingRange[]` |
| `src/features/selection_range.sd7` | 11 | enclosing chain → `SelectionRange[]` |
| `src/features/semantic_tokens.sd7` | 12 | legend, relative 5-int encoding → `SemanticTokens` |
| `src/features/signature_help.sd7` | 8 | modified only if `callContextOf` moves from mask to tokens |
| `tests/features_test.sd7` | 10–12 | the three builders |
| `tests/transcript.py` | 13 | the three methods over real frames |
| `AGENTS.md`, `README.md`, design spec | 7, 13 | the corrections spec §11 obliges |

**Invariants the layout keeps testable:** `scan.sd7` includes `utf8bytes.sd7` and nothing else;
it never includes `doc_store.sd7`, so it cannot learn about positions, and it never includes
`jsonw.sd7`, so it cannot learn about LSP.

---

## Task 1: `src/utf8bytes.sd7` — the width tables move out

AGENTS.md's "step 1". Pure relocation: behaviour must not change, so the existing checks are the
test. The one addition is the UTF-16 rule, which today is written out twice inside
`doc_store.sd7` (lines 55 and 306).

**Files:**
- Create: `src/utf8bytes.sd7`
- Create: `tests/utf8bytes_test.sd7`
- Modify: `src/transport.sd7` (delete `utf8CharLength`, add the include), `src/doc_store.sd7`
  (delete the two inline `ord(...) >= 65536` tests, drop the `transport.sd7` include, add
  `utf8bytes.sd7`), `Makefile` (`TESTS += utf8bytes`)
- Modify: `AGENTS.md` invariant 3 (last bullet of "Invariants")

**Interfaces:**
- Consumes: nothing.
- Produces: `utf8CharLength (in char: ch) → integer`, `utf8Length (in string: stri) → integer`,
  `utf16CharLength (in char: ch) → integer`, `utf16Length (in string: stri) → integer`.

- [ ] **Step 1: Write the failing suite.** New file `tests/utf8bytes_test.sd7`. The four UTF-8
  cases are the ones already in `tests/transport_test.sd7:14-17`, and the UTF-16 cases are the
  ones at `tests/doc_store_test.sd7:54-55`, moved here where the rule lives:

```seed7
$ include "seed7_05.s7i";
  include "lsp_tst.sd7";
  include "utf8bytes.sd7";

const proc: main is func
  begin
    check("ascii char is 1 byte",    str(utf8CharLength('a')),             "1");
    check("greek char is 2 bytes",   str(utf8CharLength("\960;"[1])),      "2");
    check("euro char is 3 bytes",    str(utf8CharLength("\8364;"[1])),     "3");
    check("astral char is 4 bytes",  str(utf8CharLength("\128169;"[1])),   "4");
    check("ascii string bytes",      str(utf8Length("abc")),               "3");
    check("astral string bytes",     str(utf8Length("a\128169;b")),        "6");
    check("ascii char is 1 unit",    str(utf16CharLength('a')),            "1");
    check("bmp char is 1 unit",      str(utf16CharLength("\8364;"[1])),    "1");
    check("astral char is 2 units",  str(utf16CharLength("\128169;"[1])),  "2");
    check("utf16 units of a slice",  str(utf16Length("a\128169;b")),       "4");
    report("utf8bytes");
  end func;
```

- [ ] **Step 2: Run it, and read the failure.**

```
make TESTS=utf8bytes test-utf8bytes
```
Expected: FAIL — `utf8bytes.sd7` does not exist, so the suite analyses to nothing, prints
nothing, exits 0, and the recipe's `grep` finds no `utf8bytes: N checks, 0 failed` line. That
silent shape is exactly why the Makefile grades the total line rather than the status.

- [ ] **Step 3: Write the module.** `src/utf8bytes.sd7`, with `utf8CharLength` and `utf8Length`
  copied verbatim from `transport.sd7` and the unit rule expressed once:

```seed7
$ include "seed7_05.s7i";

# Code-point widths. The only place in this server that knows how wide a character is:
# utf8Length for the bytes a Content-Length must count, utf16Length for the units an LSP
# position counts under the negotiated "utf-16" encoding. transport.sd7 owns every outbound
# byte count; doc_store.sd7 owns every position conversion; both call here rather than
# re-deriving a threshold, because the two rules differ on purpose (2048 and 65536 are not
# the same boundary) and a copy of one of them is a bug waiting for the other to move.

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

const func integer: utf16CharLength (in char: ch) is func
  result
    var integer: units is 1;
  begin
    if ord(ch) >= 65536 then
      units := 2;
    end if;
  end func;

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

const func integer: utf16Length (in string: stri) is func
  result
    var integer: units is 0;
  local
    var integer: i is 0;
  begin
    for i range 1 to length(stri) do
      units +:= utf16CharLength(stri[i]);
    end for;
  end func;
```

- [ ] **Step 4: Repoint the two callers.** In `transport.sd7`, delete the `utf8CharLength`
  definition and add `include "utf8bytes.sd7"`; `utf8Length` also moves out, so
  `writeMessage` reads `write(STD_UTF8_OUT, "Content-Length: " <& utf8Length(body) <& ...)`.
  In `doc_store.sd7`, replace the include of `transport.sd7` with `utf8bytes.sd7`, and make the
  two unit-count loops read `units +:= utf16CharLength(text[i])` (`utf16Before`) and
  `if ord(doc.text[i]) >= 65536 then units +:= 2 else units +:= 1` → the same helper
  (`charIndexOf`). Do not change `charColumnForBytes`, which counts *bytes* on purpose.

- [ ] **Step 5: Run everything.** `make test`. Expected: green, with `utf8bytes: 10 checks,
  0 failed` as a new graded line and the totals of `transport` and `doc_store` unchanged —
  the two moved checks leave `doc_store_test.sd7`, so its count drops by two; correct the
  count in the commit message rather than padding the suite back.

- [ ] **Step 6: Prove the check can fail.** In `src/utf8bytes.sd7`, change `cp < 2048` to
  `cp < 2047`. Run `make test-utf8bytes`. Expected: FAIL `greek char is 2 bytes`. Revert with
  `git checkout src/utf8bytes.sd7` (this is after a commit, so the index holds the good file).

- [ ] **Step 7: Amend invariant 3 in `AGENTS.md`.** Delete the sentence that apologises for
  `doc_store` including `transport.sd7` and the sentence scheduling the extraction; state the
  new rule: only `utf8bytes.sd7` knows code-point widths, `transport.sd7` owns outbound byte
  counts, `doc_store.sd7` owns position conversion, `scan.sd7` may consume widths and emit no
  byte count.

- [ ] **Step 8: Commit.**

```
git add src/utf8bytes.sd7 tests/utf8bytes_test.sd7 src/transport.sd7 src/doc_store.sd7 Makefile AGENTS.md tests/doc_store_test.sd7
git commit -m "Move the code-point width tables into utf8bytes.sd7, as M4 step 1"
```

---

## Task 2: `scan.sd7` — token model, cursor, names, operators, brackets

The machine's trunk: the three lexical classes that need no lookahead beyond one character, plus
the cursor that carries `(line0, col16)` forward so no later task has to count units per token.

**Files:**
- Create: `src/scan.sd7`
- Create: `tests/scan_test.sd7`
- Modify: `Makefile` (`TESTS += scan`)

**Interfaces:**
- Consumes: `utf16CharLength` from Task 1.
- Produces: `TK_ILLEGAL`, `TK_NAME`, `TK_OP`, `TK_BRACKET`, `TK_NUMBER`, `TK_STRING`, `TK_CHAR`,
  `TK_COMMENT`, `TK_LINE_COMMENT` (integers 0–8); `tok` struct of `kind, line0, col16, width16,
  start, stop`; `scanCursor` struct of `offset, line0, col16` (all integers);
  `skipWhitespace (in string: text, inout scanCursor: cur)`;
  `nextToken (in string: text, inout scanCursor: cur) → tok`, valid only when
  `cur.offset <= length(text)` and the character there is not whitespace.

- [ ] **Step 1: Write the failing suite.** `tests/scan_test.sd7` holds a local driver that turns
  a whole text into one readable string, because a check on a token *list* is the only way to
  see a wrong boundary:

```seed7
$ include "seed7_05.s7i";
  include "lsp_tst.sd7";
  include "scan.sd7";

const func string: kindName (in integer: kind) is func
  result
    var string: out is "?";
  begin
    if kind = TK_NAME then
      out := "name";
    elsif kind = TK_OP then
      out := "op";
    elsif kind = TK_BRACKET then
      out := "bracket";
    elsif kind = TK_NUMBER then
      out := "number";
    elsif kind = TK_STRING then
      out := "string";
    elsif kind = TK_CHAR then
      out := "char";
    elsif kind = TK_COMMENT then
      out := "comment";
    elsif kind = TK_LINE_COMMENT then
      out := "lineComment";
    else
      out := "illegal";
    end if;
  end func;

# ASCII-only views of a scan, for the fixtures that involve non-ASCII characters. A check whose
# got or expected string contains an astral character raises RANGE_ERROR in writeln and the suite
# dies without a graded line -- which reads as a broken rule rather than a broken print.
const func integer: firstKindOf (in string: text) is func
  result
    var integer: out is -1;
  local
    var scanCursor: cur is scanCursor.value;
    var tok: tk is tok.value;
  begin
    skipWhitespace(text, cur);
    if cur.offset <= length(text) then
      tk := nextToken(text, cur);
      out := tk.kind;
    end if;
  end func;

const func integer: firstWidthOf (in string: text) is func
  result
    var integer: out is -1;
  local
    var scanCursor: cur is scanCursor.value;
    var tok: tk is tok.value;
  begin
    skipWhitespace(text, cur);
    if cur.offset <= length(text) then
      tk := nextToken(text, cur);
      out := tk.width16;
    end if;
  end func;

# The column of the token covering UTF-16 unit `col16` of line 0, or -1. Linear: a test helper
# does not need tokenAt, which only arrives with Task 8.
const func integer: tokenColOf (in string: text, in integer: col16) is func
  result
    var integer: out is -1;
  local
    var scanCursor: cur is scanCursor.value;
    var tok: tk is tok.value;
    var boolean: more is TRUE;
  begin
    while more and cur.offset <= length(text) do
      skipWhitespace(text, cur);
      if cur.offset > length(text) then
        more := FALSE;
      else
        tk := nextToken(text, cur);
        if tk.col16 <= col16 and col16 <= tk.col16 + tk.width16 then
          out := tk.col16;
          more := FALSE;
        end if;
      end if;
    end while;
  end func;

# "kind line:col:width [text]" joined by " | " -- the shape every check below pins.
const func string: kindsOf (in string: text) is func
  result
    var string: out is "";
  local
    var scanCursor: cur is scanCursor.value;
    var tok: tk is tok.value;
    var string: piece is "";
  begin
    while cur.offset <= length(text) do
      skipWhitespace(text, cur);
      if cur.offset > length(text) then
      else
        tk := nextToken(text, cur);
        piece := kindName(tk.kind) & " " & str(tk.line0) & ":" & str(tk.col16) & ":" &
                 str(tk.width16) & " [" & text[tk.start .. tk.stop] & "]";
        if out <> "" then
          out := out & " | ";
        end if;
        out := out & piece;
      end if;
    end while;
  end func;

const proc: main is func
  begin
    check("name, op, bracket",
          kindsOf("a := (b)"),
          "name 0:0:1 [a] | op 0:2:2 [:=] | bracket 0:5:1 [(] | name 0:6:1 [b] " &
          "| bracket 0:7:1 [)]");
    check("an operator run is maximal, brackets cut it",
          kindsOf("c<&d[e]"),
          "name 0:0:1 [c] | op 0:1:2 [<&] | name 0:3:1 [d] | bracket 0:4:1 [[] " &
          "| name 0:5:1 [e] | bracket 0:6:1 []]");
    check("a '<' does not absorb the name after it",
          kindsOf("if a<b then"),
          "name 0:0:2 [if] | name 0:3:1 [a] | op 0:4:1 [<] | name 0:5:1 [b] " &
          "| name 0:7:4 [then]");
    check("a name may start with an underscore",
          kindsOf("_end x5"),
          "name 0:0:4 [_end] | name 0:5:2 [x5]");
    # An astral character must never reach a check's expected or got string: lsp_tst prints with
    # writeln on plain stdout, which raises RANGE_ERROR on non-ASCII. Assert the numbers instead
    # -- that is all "counts UTF-16 units, not characters" actually claims.
    check("an astral character is one illegal token two units wide",
          str(firstKindOf("\128169;")) & "/" & str(firstWidthOf("\128169;")),
          str(TK_ILLEGAL) & "/2");
    check("the name after an astral character sits at unit 2",
          str(tokenColOf("\128169; a", 2)), "2");
    check("a newline resets line and column",
          kindsOf("a\n  b"),
          "name 0:0:1 [a] | name 1:2:1 [b]");
    check("an unknown character is one illegal token and advances",
          kindsOf("a " & "\8;" & " b"),
          "name 0:0:1 [a] | illegal 0:2:1 [" & "\8;" & "] | name 0:4:1 [b]");
    # a control character prints nothing, so the check above cannot be reviewed by eye; this one
    # asserts the shape that matters -- that exactly one token was produced and it advanced.
    checkTrue("an illegal token is one character wide",
              length(kindsOf("\8;\8;")) > 0 and
              kindsOf("\8;\8;") = "illegal 0:0:1 [\8;] | illegal 0:1:1 [\8;]");
    report("scan");
  end func;
```

- [ ] **Step 2: Run it, and read the failure.** `make test-scan`. Expected: FAIL, no graded
  line, because `src/scan.sd7` does not exist yet.

- [ ] **Step 3: Write the trunk.** `src/scan.sd7`. The declaration order is not free: Seed7
  cannot call a function defined later, so the sets and one-character predicates come first,
  then the cursor walkers, then `nextToken`.

```seed7
$ include "seed7_05.s7i";
  include "utf8bytes.sd7";

# Seed7's lexical grammar -- the one machine in this server that knows what a token is.
# Rules follow scanner.c's scan_symbol, and manual/tokens.htm 10 is the prose. It returns
# Seed7 data only: no positions (doc_store owns those), no jsonValue, no LSP shape.
#
# A token may span lines -- only (* *) does, and a string continued with '\' + newline. Such
# a token reports the line and column it STARTS on and a width16 of 0; a consumer that needs
# the end takes 'stop'. semanticTokens clips to that first line, which is what a client
# without multilineTokenSupport would do anyway (spec 6.2).

const integer: TK_ILLEGAL is 0;
const integer: TK_NAME is 1;
const integer: TK_OP is 2;
const integer: TK_BRACKET is 3;
const integer: TK_NUMBER is 4;
const integer: TK_STRING is 5;
const integer: TK_CHAR is 6;
const integer: TK_COMMENT is 7;
const integer: TK_LINE_COMMENT is 8;

const type: tok is new struct
    var integer: kind is 0;
    var integer: line0 is 0;
    var integer: col16 is 0;
    var integer: width16 is 0;
    var integer: start is 0;
    var integer: stop is 0;
  end struct;

const type: scanCursor is new struct
    var integer: offset is 1;
    var integer: line0 is 0;
    var integer: col16 is 0;
  end struct;

const char: BACKSLASH is chr(92);
const char: APOSTROPHE is chr(39);

const set of char: OP_CHARS is {'!', '$', '%', '&', '*', '+', ',', '-', '.', '/',
                                ':', ';', '<', '=', '>', '?', '@', '^', '`', '|', '~'};
const set of char: BRACKETS is {'(', ')', '[', ']', '{', '}'};
const set of char: DIGITS is {'0','1','2','3','4','5','6','7','8','9'};
const set of char: SPACES is {' ', '\9;', '\r'};
const set of char: LETTERS is {'a','b','c','d','e','f','g','h','i','j','k','l','m',
                               'n','o','p','q','r','s','t','u','v','w','x','y','z',
                               'A','B','C','D','E','F','G','H','I','J','K','L','M',
                               'N','O','P','Q','R','S','T','U','V','W','X','Y','Z'};

const func boolean: nameStart (in char: ch) is
  return ch in LETTERS or ch = '_';

const func boolean: nameMore (in char: ch) is
  return ch in LETTERS or ch in DIGITS or ch = '_';

const proc: skipWhitespace (in string: text, inout scanCursor: cur) is func
  local
    var char: ch is ' ';
    var boolean: more is TRUE;
  begin
    while more and cur.offset <= length(text) do
      ch := text[cur.offset];
      if ch = '\n' then
        cur.line0 := succ(cur.line0);
        cur.col16 := 0;
        cur.offset := succ(cur.offset);
      elsif ch in SPACES then
        cur.col16 +:= utf16CharLength(ch);
        cur.offset := succ(cur.offset);
      else
        more := FALSE;
      end if;
    end while;
  end func;

const func tok: nextToken (in string: text, inout scanCursor: cur) is func
  result
    var tok: out is tok.value;
  local
    var char: ch is ' ';
    var integer: j is 0;
    var integer: units is 0;
  begin
    ch := text[cur.offset];
    out.kind := TK_ILLEGAL;
    out.line0 := cur.line0;
    out.col16 := cur.col16;
    out.start := cur.offset;
    units := utf16CharLength(ch);
    j := succ(cur.offset);
    if nameStart(ch) then
      while j <= length(text) and nameMore(text[j]) do
        units +:= utf16CharLength(text[j]);
        j := succ(j);
      end while;
      out.kind := TK_NAME;
    elsif ch in BRACKETS then
      out.kind := TK_BRACKET;
    elsif ch in OP_CHARS then
      while j <= length(text) and text[j] in OP_CHARS do
        units +:= utf16CharLength(text[j]);
        j := succ(j);
      end while;
      out.kind := TK_OP;
    end if;
    out.stop := pred(j);
    out.width16 := units;
    cur.col16 +:= units;
    cur.offset := j;
  end func;
```

The last `else`-less case matters: an unrecognised character keeps `TK_ILLEGAL`, advances one
character and counts its units, which is what makes the "unknown character" check pass and what
stops a malformed document from looping. Do not add a `while TRUE` guard for it; the
single-character advance *is* the guard.

Non-ASCII letters do not join a name here, and that is a decision, not an omission: spec §3.4
measured the pragma that would allow it (`$ names unicode;`) at zero uses across 213 `lib/*.s7i`
and every `prg/*.sd7`, so the rule has no input in this distribution that it would change. The
comment in `scan.sd7` says so, so a later reader meets the ceiling before tripping over it.

- [ ] **Step 4: Add the two class constants the tests need but the trunk does not use yet.**
  `TK_NUMBER`, `TK_STRING`, `TK_CHAR`, `TK_COMMENT`, `TK_LINE_COMMENT` are declared in Step 3 so
  `kindName` compiles; Tasks 3–6 give them behaviour. Leaving them declared-but-unproduced is
  deliberate: the enum order is part of the module's contract with `semanticTokens`.

- [ ] **Step 5: Run and confirm green.** `make test-scan` → `scan: 7 checks, 0 failed`. Then
  `make test`.

- [ ] **Step 6: Prove two branches fail.** (i) In `nextToken`, delete the inner `while` of the
  `TK_OP` branch so a run is one character; expected FAIL `an operator run is maximal, brackets
  cut it` and `a '<' does not absorb...` must still pass — if they do not, the second check does
  not pin what it claims. (ii) In `skipWhitespace`, drop the `'\n'` arm; expected FAIL `a newline
  resets line and column`. Revert both per file from the commit.

- [ ] **Step 7: Commit.**

```
git add src/scan.sd7 tests/scan_test.sd7 Makefile
git commit -m "Add scan.sd7: the cursor, and names, operators and brackets"
```

---

## Task 3: numbers, and the `#` that is not a comment

Closes two recorded holes in one branch: `16#be|ef` answering `beef`, and `x[1 .. 5]` fusing
`1`, `..` and `5`. It also deletes the need for `isRadixHash`, which Task 7 removes.

**Files:**
- Modify: `src/scan.sd7` (add the number branch and its helpers, above `nextToken`)
- Modify: `tests/scan_test.sd7`

**Interfaces:**
- Consumes: `DIGITS`, `nextToken`'s locals.
- Produces: `TK_NUMBER` for `12345`, `12345_`, `16#beef`, `2#0001_`, `12.3`, `12.3e-4`, `1e+3`.
  `pastNumber (in string: text, in integer: first) → integer` (index just past the literal).

- [ ] **Step 1: Write the failing checks.** Append to the `main` of `tests/scan_test.sd7`,
  before `report`:

```seed7
    check("integer, bigInteger, based, float, exponent",
          kindsOf("12345 12345_ 16#beef 2#0001_ 12.3e-4 1e+3"),
          "number 0:0:5 [12345] | number 0:6:6 [12345_] | number 0:13:7 [16#beef] " &
          "| number 0:21:7 [2#0001_] | number 0:29:7 [12.3e-4] | number 0:37:4 [1e+3]");
    check("a range is number, op, number",
          kindsOf("1 .. 5"),
          "number 0:0:1 [1] | op 0:2:2 [..] | number 0:5:1 [5]");
    check("a dot needs digits both sides to be a float",
          kindsOf("1 . 5"),
          "number 0:0:1 [1] | op 0:2:1 [.] | number 0:4:1 [5]");
    check("a hash with nothing extendable after it is a line comment",
          kindsOf("1 # not a number\n2"),
          "number 0:0:1 [1] | lineComment 0:2:14 [# not a number] | number 1:0:1 [2]");
    check("an e that starts no exponent ends the number",
          kindsOf("1e; 2"),
          "number 0:0:1 [1] | name 0:1:1 [e] | op 0:2:1 [;] | number 0:4:1 [2]");
```

- [ ] **Step 2: Run, and name the failure.** `make test-scan`. Expected: five FAILs in which the
  numbers come back as `name`/`op`/`illegal` pieces — e.g. `12345` as
  `number`-absent, `1` `2` `3` `4` `5` fused with the `op` branch — because no branch claims a
  digit yet and `TK_NUMBER` is never produced. That specific shape is the point: it shows the
  branch is missing, not that a threshold is off by one.

- [ ] **Step 3: Write the branch.** Add above `nextToken`, in this order (helpers before users):

```seed7
const func boolean: extDigit (in char: ch) is
  return ch in LETTERS or ch in DIGITS;

# TRUE when index j holds the E/e that starts an exponent: a sign is optional, a digit is not.
const func boolean: startsExponent (in string: text, in integer: j) is func
  result
    var boolean: out is FALSE;
  local
    var integer: k is 0;
  begin
    out := FALSE;
    if j <= length(text) and (text[j] = 'E' or text[j] = 'e') then
      k := succ(j);
      if k <= length(text) and (text[k] = '+' or text[k] = '-') then
        k := succ(k);
      end if;
      out := k <= length(text) and text[k] in DIGITS;
    end if;
  end func;

const proc: skipDigits (in string: text, inout integer: j) is func
  begin
    while j <= length(text) and text[j] in DIGITS do
      j := succ(j);
    end while;
  end func;

const proc: skipExtDigits (in string: text, inout integer: j) is func
  begin
    while j <= length(text) and extDigit(text[j]) do
      j := succ(j);
    end while;
  end func;

const proc: skipExponent (in string: text, inout integer: j) is func
  begin
    j := succ(j);
    if j <= length(text) and (text[j] = '+' or text[j] = '-') then
      j := succ(j);
    end if;
    skipDigits(text, j);
  end func;

# lit_number's dispatch order, in index terms. Seed7 allows at most one of '.', '_', '#' or an
# exponent after the decimal digits, which is why these are elsif arms and not a loop:
# 16#1.5 is a based number and then a dot, not a float.
const func integer: pastNumber (in string: text, in integer: first) is func
  result
    var integer: out is 0;
  local
    var integer: j is 0;
  begin
    j := succ(first);
    skipDigits(text, j);
    if j <= length(text) and text[j] = '.' and succ(j) <= length(text) and
       text[succ(j)] in DIGITS then
      j := succ(j);
      skipDigits(text, j);
      if startsExponent(text, j) then
        skipExponent(text, j);
      end if;
    elsif j <= length(text) and text[j] = '_' then
      j := succ(j);
    elsif j <= length(text) and text[j] = '#' and succ(j) <= length(text) and
          extDigit(text[succ(j)]) then
      j := succ(j);
      skipExtDigits(text, j);
      if j <= length(text) and text[j] = '_' then
        j := succ(j);
      end if;
    elsif startsExponent(text, j) then
      skipExponent(text, j);
    end if;
    out := j;
  end func;
```

and inside `nextToken`, as the arm before `elsif ch in BRACKETS`:

```seed7
    elsif ch in DIGITS then
      j := pastNumber(text, cur.offset);
      # digits, base markers and signs are all ASCII, so a number is as wide in units as in
      # characters -- stated here because the next arms cannot say it.
      units := j - cur.offset;
      out.kind := TK_NUMBER;
```

- [ ] **Step 4: Run to green.** `make test-scan` → `scan: 12 checks, 0 failed`; `make test`.

- [ ] **Step 5: Prove the three guards can fail.** (i) `extDigit(text[succ(j)])` → `TRUE`:
  expected FAIL `a hash with nothing extendable after it is a line comment`. (ii) the float arm's
  `text[succ(j)] in DIGITS` → `TRUE`: expected FAIL `a dot needs digits both sides to be a
  float`. (iii) `startsExponent`'s digit test → `TRUE`: expected FAIL `an e that starts no
  exponent ends the number`. Each named check, each reverted per file.

- [ ] **Step 6: Commit.**

```
git add src/scan.sd7 tests/scan_test.sd7
git commit -m "Separate number tokens from name tokens, which is what the hash rule needed"
```

---

## Task 4: string literals, escapes, and the continuation that crosses a line

Spec §5's string row. The continuation rule is the one a naive mask gets wrong: two backslashes
with whitespace, newlines and `#` comments between them are ignored entirely, so a string really
can occupy several lines.

**Files:**
- Modify: `src/scan.sd7` (add `pastEscape`, the string arm, and a `counting` local)
- Modify: `tests/scan_test.sd7`

**Interfaces:**
- Consumes: `SPACES`, `DIGITS`, `skipDigits`, `skipExtDigits`, `BACKSLASH`.
- Produces: `pastEscape (in string: text, in integer: j) → integer`, taking the index of a
  `BACKSLASH` to the index just past the escape body. `TK_STRING`.

- [ ] **Step 1: Write the failing checks.**

```seed7
    check("escapes do not end a string",
          kindsOf("\"a\\n\\9;b\""),
          "string 0:0:9 [\"a\\n\\9;b\"]");
    check("a based numeric escape is one token",
          kindsOf("\"\\16#ff;\""),
          "string 0:0:9 [\"\\16#ff;\"]");
    check("a continuation crosses the newline and stays one token",
          kindsOf("\"ab\\\n        \\cd\";"),
          "string 0:0:0 [\"ab\\\n        \\cd\"] | op 0:20:1 [;]");
    check("an unterminated string ends at EOF and raises nothing",
          kindsOf("const string: s is \"abc"),
          "name 0:0:5 [const] | name 0:6:6 [string] | op 0:12:1 [:] | name 0:14:1 [s] " &
          "| name 0:16:2 [is] | string 0:19:4 [\"abc]");
    # same reason as Task 2's astral checks: the character stays out of the printed strings
    check("an astral character inside a string counts two units",
          str(firstWidthOf("\"x\128169;y\"")), "6");
```

The continuation check expects `width16` of **0**, because the token ends on a later line and a
multi-line token reports no width (Task 2's contract). If a future change makes that number
meaningful, this is the check that says so.

- [ ] **Step 2: Run, and name the failure.** `make test-scan`. Expected: five FAILs where the
  string comes back as `op`/`name`/`illegal` fragments starting at the quote — no arm claims `'"'`
  yet, so it falls through to `TK_ILLEGAL` one character at a time.

- [ ] **Step 3: Add `pastEscape`,** above `nextToken`:

```seed7
# literal.c's escape_sequence in index terms, from the BACKSLASH at j. Three shapes: a
# continuation ('\' + blanks/newlines/'#'-comment + '\'), a numeric escape ('\123;' or
# '\16#ff;' -- an integer literal then ';'), and a one-character escape ('\"', '\\', '\'',
# '\a'..'\v', '\A'..'\Z'). An escape that matches none of them is the analyzer's error to
# report; this only has to not lose the rest of the line.
const func integer: pastEscape (in string: text, in integer: j) is func
  result
    var integer: out is 0;
  begin
    out := succ(j);
    if out > length(text) then
    elsif text[out] = '\n' or text[out] in SPACES then
      while out <= length(text) and text[out] <> BACKSLASH and text[out] <> '"' do
        out := succ(out);
      end while;
      if out <= length(text) and text[out] = BACKSLASH then
        out := succ(out);
      end if;
    elsif text[out] in DIGITS then
      skipDigits(text, out);
      if out <= length(text) and text[out] = '#' then
        out := succ(out);
        skipExtDigits(text, out);
      end if;
      if out <= length(text) and text[out] = ';' then
        out := succ(out);
      end if;
    else
      out := succ(out);
    end if;
  end func;
```

- [ ] **Step 4: Add the string arm,** before `elsif ch in DIGITS`, and declare
  `var boolean: counting is TRUE;` and `var integer: before is 0;` in `nextToken`'s `local` part:

```seed7
    elsif ch = '"' then
      counting := TRUE;
      while j <= length(text) and text[j] <> '"' do
        if text[j] = '\n' then
          # a bare newline is STRING_EXCEEDS territory for the analyzer; keep the token on the
          # line it started on so the mask and the columns of the rest of the file survive.
          if counting then
            units := 0;
            counting := FALSE;
          end if;
          cur.line0 := succ(cur.line0);
          cur.col16 := 0;
          j := succ(j);
        elsif text[j] = BACKSLASH and succ(j) <= length(text) and
              (text[succ(j)] = '\n' or text[succ(j)] in SPACES) then
          j := succ(j);
          while j <= length(text) and text[j] <> BACKSLASH and text[j] <> '"' do
            if text[j] = '\n' then
              counting := FALSE;
              cur.line0 := succ(cur.line0);
              cur.col16 := 0;
            end if;
            j := succ(j);
          end while;
          if j <= length(text) and text[j] = BACKSLASH then
            j := succ(j);
          end if;
        elsif text[j] = BACKSLASH then
          before := j;
          j := pastEscape(text, j);
          if counting then
            units +:= j - before;
          end if;
        else
          if counting then
            units +:= utf16CharLength(text[j]);
          end if;
          j := succ(j);
        end if;
      end while;
      if j <= length(text) and text[j] = '"' then
        j := succ(j);
        if cur.line0 = out.line0 then
          units +:= 1;
        end if;
      end if;
      out.kind := TK_STRING;
```

- [ ] **Step 5: Make the multi-line rule explicit in `nextToken`'s tail.** The current
  `out.width16 := units;` must not silently report a stale count for a token that ended on a
  later line. Replace the tail with:

```seed7
    out.stop := pred(j);
    if cur.line0 <> out.line0 then
      units := 0;
    end if;
    out.width16 := units;
    cur.col16 +:= units;
    cur.offset := j;
```

- [ ] **Step 6: Run to green.** `make test-scan` → `scan: 17 checks, 0 failed`. Then `make test`
  — `doc_store_test` must be untouched: the mask is still the old machine until Task 7.

- [ ] **Step 7: Prove three guards.** (i) delete the `text[j] <> '"'` from the `while` condition:
  expected FAIL on `escapes do not end a string`. (ii) delete the `';'` consumption inside
  `pastEscape`: expected FAIL on `a based numeric escape is one token`. (iii) delete the
  `'\n'` handling in the continuation walk: expected FAIL `a continuation crosses the newline and
  stays one token`. Revert per file.

- [ ] **Step 8: Commit.**

```
git add src/scan.sd7 tests/scan_test.sd7
git commit -m "Scan string literals, including the continuation that crosses a line"
```

---

## Task 5: char literals, whose length is not a constant

Closes README's recorded mask hole. `lit_char` reads exactly one `char_literal_element`, and
`escape_sequence` calls `lit_number` for a digit — so `'\16#ff;'` is nine characters and
`'''` is three. Any machine that assumes a fixed count is wrong by the difference, and the wrong
count is what loses the characters *after* the closing quote.

**Files:**
- Modify: `src/scan.sd7` (the char arm), `tests/scan_test.sd7`

**Interfaces:**
- Consumes: `pastEscape`, `APOSTROPHE`.
- Produces: `TK_CHAR`.

- [ ] **Step 1: Write the failing checks.** The last one is the hole, stated as the boundary it
  must not cross:

```seed7
    check("the five char spellings and their widths",
          kindsOf("'a' ''' '\\n' '\\9;' '\\16#ff;'"),
          "char 0:0:3 ['a'] | char 0:4:3 ['''] | char 0:8:4 ['\\n'] " &
          "| char 0:13:5 ['\\9;'] | char 0:19:9 ['\\16#ff;']");
    check("a double quote is ordinary char-literal content",
          kindsOf("'\"'"),
          "char 0:0:3 ['\"']");
    check("the name after a numeric-escape char literal is still code",
          kindsOf("const char: q is '\\9;'; const integer: afterThis is 1;"),
          "name 0:0:5 [const] | name 0:6:4 [char] | op 0:10:1 [:] | name 0:12:1 [q] " &
          "| name 0:14:2 [is] | char 0:17:5 ['\\9;'] | op 0:22:1 [;] " &
          "| name 0:24:5 [const] | name 0:30:7 [integer] | op 0:37:1 [:] " &
          "| name 0:39:9 [afterThis] | name 0:49:2 [is] | number 0:52:1 [1] | op 0:53:1 [;]");
```

- [ ] **Step 2: Run, and name the failure.** Expected: three FAILs where `'a'` comes back as
  `illegal 0:0:1 [']` twice with `a` as a name between them — the quote is not yet claimed.

- [ ] **Step 3: Add the char arm,** before `elsif ch in DIGITS`:

```seed7
    elsif ch = APOSTROPHE then
      # one element, then the closing quote. The element is an escape (variable length), the
      # quote character itself ('''), or any single character (which may be two UTF-16 units).
      if j <= length(text) and text[j] = BACKSLASH then
        before := j;
        j := pastEscape(text, j);
        units +:= j - before;
      elsif j <= length(text) and text[j] = APOSTROPHE then
        units +:= 1;
        j := succ(j);
      elsif j <= length(text) then
        units +:= utf16CharLength(text[j]);
        j := succ(j);
      end if;
      if j <= length(text) and text[j] = APOSTROPHE then
        units +:= 1;
        j := succ(j);
      end if;
      out.kind := TK_CHAR;
```

- [ ] **Step 4: Run to green.** `make test-scan` → `scan: 20 checks, 0 failed`; `make test`.

- [ ] **Step 5: Prove it.** Replace `units +:= j - before;` with `units +:= 1;` — the fixed-count
  assumption that produced the recorded hole. Expected: FAIL `the five char spellings and their
  widths` and FAIL `the name after a numeric-escape char literal is still code`, because the
  following `op` and `name` tokens shift. Revert per file.

- [ ] **Step 6: Commit.**

```
git add src/scan.sd7 tests/scan_test.sd7
git commit -m "Give char literals their real length, which is what the mask was losing"
```

---

## Task 6: comments — nested, multi-line, and EOF-safe

**Files:**
- Modify: `src/scan.sd7` (comment and line-comment arms), `tests/scan_test.sd7`

**Interfaces:**
- Consumes: nothing new.
- Produces: `TK_COMMENT`, `TK_LINE_COMMENT`.

- [ ] **Step 1: Write the failing checks.**

```seed7
    check("comments nest",
          kindsOf("(* a (* b *) c *)"),
          "comment 0:0:17 [(* a (* b *) c *)]");
    check("a multi-line comment reports its first line only",
          kindsOf("(* one\n   two *)"),
          "comment 0:0:6 [(* one\n   two *)]");
    check("the line comment starts at the hash and stops before the newline",
          kindsOf("x := 1; # trailing\ny := 2;"),
          "name 0:0:1 [x] | op 0:2:2 [:=] | number 0:5:1 [1] | op 0:6:1 [;] " &
          "| lineComment 0:8:10 [# trailing] | name 1:0:1 [y] | op 1:2:2 [:=] " &
          "| number 1:5:1 [2] | op 1:6:1 [;]");
    check("an unclosed comment ends at EOF and raises nothing",
          kindsOf("(* unclosed\nmore;"),
          "comment 0:0:11 [(* unclosed\nmore;]");
    check("a comment cannot open inside a string",
          kindsOf("\"(* not a comment *)\" writeln(1);"),
          "string 0:0:24 [\"(* not a comment *)\"] | name 0:25:7 [writeln] " &
          "| bracket 0:32:1 [(] | number 0:33:1 [1] | bracket 0:34:1 [)] | op 0:35:1 [;]");
```

- [ ] **Step 2: Run, and name the failure.** Expected: FAILs of two shapes — `(*` reported as
  `bracket` + `op`, and `#` as `illegal` — because neither arm exists yet.

- [ ] **Step 3: Add both arms,** before `elsif ch in DIGITS`, and declare
  `var integer: depth is 0;` in the `local` part:

```seed7
    elsif ch = '(' and succ(cur.offset) <= length(text) and
          text[succ(cur.offset)] = '*' then
      # scan_comment's nesting, and the same first-line-only width rule as a continued string.
      depth := 1;
      j := succ(succ(cur.offset));
      units := 2;
      counting := TRUE;
      while j <= length(text) and depth > 0 do
        if text[j] = '(' and succ(j) <= length(text) and text[succ(j)] = '*' then
          depth +:= 1;
          j := succ(succ(j));
          if counting then
            units +:= 2;
          end if;
        elsif text[j] = '*' and succ(j) <= length(text) and text[succ(j)] = ')' then
          depth := pred(depth);
          j := succ(succ(j));
          if counting then
            units +:= 2;
          end if;
        elsif text[j] = '\n' then
          cur.line0 := succ(cur.line0);
          cur.col16 := 0;
          counting := FALSE;
          j := succ(j);
        else
          if counting then
            units +:= utf16CharLength(text[j]);
          end if;
          j := succ(j);
        end if;
      end while;
      out.kind := TK_COMMENT;
    elsif ch = '#' then
      while j <= length(text) and text[j] <> '\n' do
        units +:= utf16CharLength(text[j]);
        j := succ(j);
      end while;
      out.kind := TK_LINE_COMMENT;
```

- [ ] **Step 4: Run to green.** `make test-scan` → `scan: 25 checks, 0 failed`; `make test`.

- [ ] **Step 5: Prove it twice.** (i) `depth := 1` → `depth := 9` … better: replace `depth := 1`
  with `depth := 1` and then make the `*)` arm not decrement (`depth := pred(depth)` deleted);
  expected FAIL `comments nest` and FAIL `an unclosed comment ends at EOF and raises nothing`.
  (ii) In the line-comment arm, change `text[j] <> '\n'` to `TRUE`: expected FAIL
  `the line comment starts at the hash and stops before the newline`, and the suite must still
  terminate — if it hangs, the EOF bound is doing work that should be documented, so add a
  comment saying which bound is the loop's real end. Revert per file.

- [ ] **Step 6: Commit.**

```
git add src/scan.sd7 tests/scan_test.sd7
git commit -m "Scan comments, nested and line, so a keyword inside one cannot open a block"
```

---

## Task 7: the mask becomes a projection of the scan

The step Q2 was about. One machine, and `codeText`'s contract — same length as the text,
newlines kept, non-code characters blanked — is kept exactly, so no caller notices. This is the
task where the char-literal hole closes for real, because the mask can no longer disagree with
the token stream.

Built **eagerly in `setVersion`**, not lazily behind a version stamp: it keeps
`codeText (in lsDoc: doc)`'s signature, so `wordAt` and `callContextOf` and every test that
calls them stay untouched, and it keeps one derived value with no invalidation logic. Cost is
the measured ~130 ms on the largest stdlib file, and the `ponytail:` note says what to do if
that ever shows up in a profile.

**Files:**
- Modify: `src/scan.sd7` (add `maskOf`)
- Modify: `src/doc_store.sd7` (add `include "scan.sd7"` — `setVersion` calls `maskOf`, so the
  include lands *here*, not in Task 8; `lsDoc` gains `mask`; `codeText` returns it; delete the old
  state machine, `isRadixHash` and `nextIs`)
- Modify: `tests/doc_store_test.sd7`, `Makefile` if a suite name changes
- Modify: `AGENTS.md` (the `#`-is-both entry, the mask-hole entry), `README.md` (the hole
  paragraph)

**Interfaces:**
- Consumes: `nextToken`, `skipWhitespace`, `scanCursor`, `tok`.
- Produces: `maskOf (in string: text) → string`; `lsDoc` gains `var string: mask is ""`;
  `codeText (in lsDoc: doc) → string` unchanged in signature and contract.

- [ ] **Step 1: Write the failing checks** in `tests/scan_test.sd7`, where the mask belongs once
  the mask is a scan product. Every expectation below is **measured** output of `maskOf` (see
  `§Measured mask fixtures` at the end of this task), annotated with `_` for a space and `$NL` for
  a newline, because a run of spaces in a literal cannot be reviewed by eye:

```seed7
    # measured: len 22/22  a_:=______;_________b$NL
    check("the mask keeps length and newlines and blanks the literals",
          maskOf("a := \"x\ty\"; (* c *) b\n"),
          "a :=      ;        b\n");
    # the literal '\9;' is FIVE characters; the old fixed-count machine masked seven, which is
    # the hole README records. measured: len 54/54
    #   const_char:_q_is______;_const_integer:_afterThis_is_1;
    check("a numeric-escape char literal masks exactly itself",
          maskOf("const char: q is '\\9;'; const integer: afterThis is 1;"),
          "const char: q is     ; const integer: afterThis is 1;");
    # a based literal is code and survives; only the comment goes.
    # measured: len 43/43  const_integer:_c_is_16#beef;_______$NLx_:=_1;
    check("a based literal is code, its comment tail is not",
          maskOf("const integer: c is 16#beef; # tail\nx := 1;"),
          "const integer: c is 16#beef;       \nx := 1;");
    check("length never changes",
          str(length(maskOf("s := \"a\\\"b\"; # c\n"))),
          "17");
```

- [ ] **Step 2: Run, and name the failure.** `make test-scan`. Expected: FAILs saying
  `maskOf` is unknown — and if the suite instead prints nothing at all, that is the analysis
  failing, which is the same failure by this repo's measuring: the recipe cannot find a total
  line.

- [ ] **Step 3: Write `maskOf`** in `src/scan.sd7`, after `nextToken`:

```seed7
const func boolean: hiddenKind (in integer: kind) is func
  result
    var boolean: out is FALSE;
  begin
    out := FALSE;
    if kind = TK_STRING then
      out := TRUE;
    elsif kind = TK_CHAR then
      out := TRUE;
    elsif kind = TK_COMMENT then
      out := TRUE;
    elsif kind = TK_LINE_COMMENT then
      out := TRUE;
    end if;
  end func;

# The same text with every string, char and comment character replaced by a space. Newlines and
# length survive, so an offset into the result is an offset into the document -- that is
# doc_store's contract for codeText, and this is the only place the machine that implements it
# lives. One boolean per comparison because a long or/and chain of them can fail to match.
const func string: maskOf (in string: text) is func
  result
    var string: out is "";
  local
    var scanCursor: cur is scanCursor.value;
    var tok: tk is tok.value;
    var integer: copied is 1;
    var integer: i is 0;
  begin
    copied := 1;
    while cur.offset <= length(text) do
      skipWhitespace(text, cur);
      if cur.offset > length(text) then
      else
        tk := nextToken(text, cur);
        out := out & text[copied .. pred(tk.start)];
        if hiddenKind(tk.kind) then
          for i range tk.start .. tk.stop do
            if text[i] = '\n' or text[i] = '\r' then
              out := out & text[i .. i];
            else
              out := out & " ";
            end if;
          end for;
        else
          out := out & text[tk.start .. tk.stop];
        end if;
        copied := succ(tk.stop);
      end if;
    end while;
    if copied <= length(text) then
      out := out & text[copied .. length(text)];
    end if;
  end func;
```

- [ ] **Step 4: Rewire `doc_store.sd7`.** Add `var string: mask is "";` to `lsDoc`; make
  `setVersion` end with `doc.mask := maskOf(text);`; replace the body of `codeText` with
  `return doc.mask;` keeping the `in lsDoc: doc` signature; delete `codeText`'s state machine,
  `isRadixHash`, and `nextIs` if nothing else calls it (`grep -n 'nextIs\|isRadixHash' src/`).
  Leave `isAlpha`, `isDigit`, `nameChar`, `opChar`, `OP_CHARS`, `tokenChar`, `codeKindAt` in
  place — Task 8 removes the ones `wordAt` no longer needs, and deleting them here would make
  this commit's blast radius two things at once.

- [ ] **Step 5: Run the whole suite, unchanged, as the equivalence proof.** `make test`.
  Expected: green. Every existing `codeText` check in `tests/doc_store_test.sd7` and every
  transcript check that depends on the mask now runs against the projection; a difference in
  behaviour is a difference in this task, not in a feature. If `the based-literal fixture
  publishes no diagnostics` or `hover reaches a name written after a based literal` changes
  answer, stop and read the diff — the mask got *better*, and the check that now sees through a
  comment is the one to update with a comment saying why.

- [ ] **Step 6: Prove the projection is load-bearing.** In `hiddenKind`, return `FALSE` for
  `TK_CHAR`. Expected: FAIL `a numeric-escape char literal masks exactly itself` in
  `tests/scan_test.sd7` **and** at least one existing mask check in `tests/doc_store_test.sd7`,
  which is the proof that the two machines were answering the same question. Revert per file.

- [ ] **Step 7: Add the `ponytail:` note** above `setVersion`:
  `ponytail: mask rebuilt on every didChange (measured ~130 ms on the stdlib's largest file);
  upgrade path is a version stamp and a lazy fill if a change burst ever shows it.`

- [ ] **Step 8: Correct the documents** that record the hole this closes. `README.md`: delete the
  "One hole in that mask" paragraph and the `16#be|ef` entry in "What does not work yet".
  `AGENTS.md`: the `#` is both… entry becomes "the scanner decides, because it knows whether it is
  inside a number token", and the mask-hole entry in "Invariants"/"Protocol decisions" is deleted
  rather than reworded.

- [ ] **Step 9: Commit.**

```
git add src/scan.sd7 src/doc_store.sd7 tests/scan_test.sd7 README.md AGENTS.md
git commit -m "Make codeText a projection of scan.sd7, which deletes the second lexical machine"
```

---

## Task 8: `wordAt` answers tokens, so a name stops being a character run

Closes the `a<b` over-reach and the based-literal-as-a-name, both recorded as unsolved in
`doc_store`'s own comment. `tokenAt` is a *prefix* scan: it stops as soon as it is past the
requested position, which is cheaper than what `codeText` does today for a cursor near the top of
a big file (the mask always scans the whole document; this one does not).

**Files:**
- Modify: `src/scan.sd7` (add `tokenAt`)
- Modify: `src/doc_store.sd7` (`wordAt` reads tokens through `tokenAt`; drop `tokenChar`,
  `codeKindAt` and `onLine` if nothing calls them). No new include — `include "scan.sd7"` arrived
  with Task 7, and `scan.sd7` still includes only `utf8bytes.sd7`, so the direction stays one way.
- Modify: `tests/scan_test.sd7`, `tests/doc_store_test.sd7`

**Interfaces:**
- Consumes: `nextToken`, `skipWhitespace`, `lsDoc.lineStart`, `lineWidth`.
- Produces: `tokenAt (in string: text, in integer: line0, in integer: col16) → tok`, where a
  `start` of 0 means "no token here"; `wordRef` unchanged in shape.

- [ ] **Step 1: Write the failing checks** in `tests/scan_test.sd7`:

```seed7
    # measured: "+" at col16 3 width 1; position 4 is its end, so left-of wins over "cd"
    check("left-of-character wins over the token that starts here",
          tokenTextOf("ab + cd", 0, 4), "+");
    # measured: nothing ends at 5, so the fallback names "cd" (col16 5 width 2)
    check("a position that ends nothing falls back to the token starting there",
          tokenTextOf("ab + cd", 0, 5), "cd");
    # measured: "a" (0:1) -- the old character run answered "a<"
    check("a '<' is not part of the name on either side of it",
          tokenTextOf("a<b", 0, 1), "a");
    check("a position one past a name's last character still names it",
          tokenTextOf("writeln(1)", 0, 7), "writeln");
    check("the middle of a based literal is a number, not a name",
          tokenTextOf("16#beef", 0, 4), "16#beef");
    check("inside a comment there is no token",
          tokenTextOf("(* hidden *)", 0, 5), "");
    check("a position past the line answers nothing",
          tokenTextOf("ab", 0, 9), "");
```
`tokenTextOf` joins the helpers Task 2 already put in this same file — Tasks 3–6 and 8 all
extend `tests/scan_test.sd7`, which is why nothing is redefined here:
```seed7
# The text of the token an LSP position resolves to, or "" for nothing.
const func string: tokenTextOf (in string: text, in integer: line0,
                                in integer: col16) is func
  result
    var string: out is "";
  local
    var tok: tk is tok.value;
  begin
    tk := tokenAt(text, line0, col16);
    if tk.start > 0 then
      out := text[tk.start .. tk.stop];
    end if;
  end func;
```

- [ ] **Step 2: Run, and name the failure.** Expected: six FAILs of the shape `""` or a fragment,
  because `tokenAt` does not exist — and if the suite fails to analyse instead, the check list is
  right and the function is missing, which is the same red.

- [ ] **Step 3: Write `tokenAt`** in `src/scan.sd7`:

```seed7
# The token an LSP position resolves to. Positions sit between characters, so the rule is
# left-of-character: the position before character n names the token ENDING at n, and only if
# nothing ends there does it name the token starting at n. doc_store.wordAt owned this rule
# when it derived runs from characters; now the run comes from the scanner and only the
# preference is decided here.
#
# Returns a tok with start = 0 when the position is outside every token, including inside a
# comment or a literal, which is what makes a request inside "..." answer nothing.
const func tok: tokenAt (in string: text, in integer: line0, in integer: col16) is func
  result
    var tok: out is tok.value;
  local
    var scanCursor: cur is scanCursor.value;
    var tok: tk is tok.value;
    var boolean: after is FALSE;
  begin
    out.start := 0;
    out.stop := 0;
    out.kind := TK_ILLEGAL;
    after := FALSE;
    while cur.offset <= length(text) and not after do
      skipWhitespace(text, cur);
      if cur.offset > length(text) then
        after := TRUE;
      else
        tk := nextToken(text, cur);
        if tk.line0 > line0 then
          after := TRUE;
        elsif tk.line0 = line0 and hiddenKind(tk.kind) and col16 >= tk.col16 and
              col16 <= tk.col16 + tk.width16 then
          out.start := 0;
          after := TRUE;
        elsif tk.line0 = line0 and col16 > tk.col16 and
              col16 <= tk.col16 + tk.width16 then
          out := tk;
          after := TRUE;
        elsif tk.line0 = line0 and col16 = tk.col16 and out.start = 0 then
          out := tk;
        end if;
      end if;
    end while;
  end func;
```

The last `elsif` keeps the *starts-here* token as a candidate without stopping the walk, so a
token ending at the same column wins. `out.start = 0` is the guard that makes the first such
candidate the one that is kept.

- [ ] **Step 4: Rewrite `wordAt`** in `src/doc_store.sd7` as a thin adapter, because every feature
  already reads a `wordRef`:

```seed7
# The token under an LSP position, as the shape the symbol features have always taken. The
# column is a CHARACTER column (see the note on wordRef) and the width counts characters, so
# completion's prefixOf and hover's range need no change.
const func wordRef: wordAt (in lsDoc: doc, in integer: line0,
                            in integer: character0) is func
  result
    var wordRef: out is wordRef.value;
  local
    var integer: lineIdx is 0;
    var integer: start is 1;
    var tok: tk is tok.value;
  begin
    lineIdx := line0 + 1;
    if lineIdx >= 1 and lineIdx <= lineCount(doc) then
      start := doc.lineStart[lineIdx];
      tk := tokenAt(doc.text, line0, character0);
      if tk.start > 0 and not hiddenKind(tk.kind) and
         onLine(doc, lineIdx, tk.start) then
        out.word := doc.text[tk.start .. tk.stop];
        out.line1 := succ(tk.line0);
        out.column1 := tk.start - start + 1;
        out.character1 := tk.col16;
        out.width := tk.stop - tk.start + 1;
      end if;
    end if;
  end func;
```

Note what disappeared: the `codeText` call, the `pred(right)` arithmetic, and the two character
run loops. `out.character1` now comes from the scan, which is why it is right on a line that holds
an astral character before the token — today it is computed over the masked text, where the
astral character inside a string literal has already been flattened to one space. Add a check for
exactly that to `tests/doc_store_test.sd7`:

```seed7
    check("a name after an astral string keeps its real UTF-16 column",
          str(wordAt(astralDoc, 0, 13).character1), "13");
```
where `astralDoc` is set to `"\"x" & "\128169;" & "y\" zzz"` — the token `zzz` starts at UTF-16
unit 13 and, under the old masked computation, answered 12.

- [ ] **Step 5: Run to green.** `make test-scan`, `make test-doc_store`, `make test`. Expected:
  one existing `doc_store_test.sd7` check may change answer — a position that used to resolve
  through an operator run now resolves to a shorter token. Read it, confirm the new answer is
  what `scanner.c` would call, and re-pin it with a comment naming the mutation.

- [ ] **Step 6: Prove the left-of-character rule.** In `tokenAt`, swap `col16 > tk.col16` for
  `col16 >= tk.col16`. Expected: FAIL `left-of-character wins over the token that starts here`
  and FAIL `a '<' is not part of the name on either side of it`. Revert per file.

- [ ] **Step 7: Delete what nothing calls.** `grep -n 'tokenChar\|codeKindAt' src/ tests/` and
  remove the survivors only if the list is empty outside `doc_store.sd7` itself.

- [ ] **Step 8: Commit.**

```
git add src/scan.sd7 src/doc_store.sd7 tests/scan_test.sd7 tests/doc_store_test.sd7
git commit -m "Resolve a position to a token, which retires the character-run guess"
```

### Measured mask fixtures

Produced by running Task 7's `maskOf` over Task 2–6's fixtures, so the expectations above are
observations and not arithmetic. `_` is a space, `$NL` a newline, `$TAB` a tab:

| input | length in/out | mask |
|---|---|---|
| `a := "x<tab>y"; (* c *) b` + NL | 22/22 | `a_:=______;_________b$NL` |
| `const char: q is '\9;'; const integer: afterThis is 1;` | 54/54 | `const_char:_q_is______;_const_integer:_afterThis_is_1;` |
| `const integer: c is 16#beef; # tail` + NL + `x := 1;` | 43/43 | `const_integer:_c_is_16#beef;_______$NLx_:=_1;` |
| `s := "a\"b"; # c` + NL | 17/17 | `s_:=______;____$NL` |
| `(* a (* b *) c *) "x" '\9;' # c` + NL | 33/33 | `______________________     ____$NL` |

Row 2 is the recorded hole: the old machine spent three characters on `'\9;'` and then ate the
`;` and the following space, so `afterThis` was masked and unreachable. Row 3 is the `#` case:
`16#beef` is code, `# tail` is not, and no neighbour heuristic has an opinion about it.

---

## Task 9: one analysis per document version

Spec §4.2. The win is measurable and it is not subtle: `symbolsOfDocument(uri)` is a
`parseStri` call sitting inside five request branches, so a client that asks for a hover and a
definition on one version pays 41 ms twice for identical output.

**Files:**
- Modify: `src/lsp_server.sd7` (cache struct, hash, `symbolsOfDocument`, `didClose`)
- Modify: `tests/transcript.py` (the log-count check)

**Interfaces:**
- Consumes: `analyzeSymbols`, `textToAnalyze`, `openDocs`, `note`.
- Produces: `symCache` struct of `syms` + `version`; `var symCacheHash: symbolCache`;
  `symbolsOfDocument (in string: uri) → array symRec` unchanged in signature.

- [ ] **Step 1: Add the failing transcript check first.** In `tests/transcript.py`, after the
  existing `initialize`/`didOpen` frames, add a run that opens a document, then asks for
  `textDocument/hover` and `textDocument/definition` on the same version, and count the analysis
  lines on **stderr**:

```python
def test_symbols_are_analysed_once_per_version():
    frames = [init(1), opened(URI, SRC),
              req(2, "textDocument/hover", pos(URI, 6, 25)),
              req(3, "textDocument/definition", pos(URI, 6, 25)),
              shutdown(4), exit_(5)]
    replies, rc, err, junk = run(frames)
    n = err.count("analyzed ")
    expect(n == 1, "two symbol requests on one version cost one analysis (saw %d)" % n)
```
Match the helper names already in the file (`frame`, `run`, `expect`) — if it has no `req`/`pos`
helpers, add them there rather than inlining dicts, because Tasks 10–12 need them too.

- [ ] **Step 2: Run it and see it fail.** `make transcript`. Expected: FAIL saying `saw 2` — one
  analysis for the hover, one for the definition. That number is the task's whole point; if it
  says `saw 0`, the log line does not exist yet and Step 3 adds it too early to be evidence.

- [ ] **Step 3: Implement the cache** in `src/lsp_server.sd7`, beside `openDocs`:

```seed7
# One analysis per document version, replaced on each didChange -- never one per version, which
# would grow by the measured ~1.4 MiB a keystroke. symbolsOfDocument is called from five request
# branches, so without this a hover followed by a definition costs two parseStri calls that
# return the same records.
const type: symCache is new struct
    var array symRec: syms is 0 times symRec.value;
    var integer: version is -1;
  end struct;

const type: symCacheHash is hash [string] symCache;

var symCacheHash: symbolCache is symCacheHash.EMPTY_HASH;
```

and replace the body of `symbolsOfDocument`:

```seed7
const func array symRec: symbolsOfDocument (in string: uri) is func
  result
    var array symRec: out is 0 times symRec.value;
  local
    var symCache: cached is symCache.value;
  begin
    out := 0 times symRec.value;
    if uri in openDocs then
      if uri in symbolCache and symbolCache[uri].version = openDocs[uri].version then
        out := symbolCache[uri].syms;
      else
        cached.syms := analyzeSymbols(textToAnalyze(uri), libraryDirs);
        cached.version := openDocs[uri].version;
        symbolCache @:= [uri] cached;
        note("analyzed " <& uri <& " version " <& str(cached.version) <&
             " records " <& str(length(cached.syms)));
        out := cached.syms;
      end if;
    end if;
  end func;
```

The `note` line is what Step 1 counts: the log is the observable, so no test-only counter enters
the product. In `setVersion`'s callers nothing changes — the version stamp *is* the invalidation.
In the `didClose` branch, add `excl(symbolCache, uri);` next to `excl(openDocs, uri);`.

- [ ] **Step 4: Run to green.** `make transcript` → the new check passes and the existing 53 stay
  green; `make test`. Then measure the claim: from the worktree, run
  `python3 - <<'EOF' …` timing two symbol requests after one change, and put the before/after
  milliseconds in the commit message.

- [ ] **Step 5: Prove invalidation.** Change `cached.version = openDocs[uri].version` to
  `cached.version >= 0` (a cache that never misses) and add a `didChange` frame before the hover
  in a scratch run: expected — the hover answers with the *previous* version's records, which the
  existing outline checks should catch. If nothing catches it, the check that should has no
  teeth: add one (a document whose own declaration appears only after the change) before
  continuing, and revert the mutation per file.

- [ ] **Step 6: Commit.**

```
git add src/lsp_server.sd7 tests/transcript.py
git commit -m "Analyse a document once per version, which a symbol request no longer repeats"
```

---

## Task 10: `src/blocks.sd7` — the construct stack read off the tokens

Spec §5. Design §2 lists `scan.sd7` as owning "tokens, comments, blocks, token-at-offset"; that
line is amended here, because which names open a block is a question about Seed7's *constructs*,
not its lexicon, and folding, selection ranges and later local scope all need the same answer. One
module holds the rules; `scan.sd7` stays a lexicon that cannot know keywords (spec §3.3), and no
construct rule is written twice.

**Files:**
- Create: `src/blocks.sd7`
- Create: `src/features/folding_range.sd7` (serialiser only)
- Create: `tests/blocks_test.sd7`
- Modify: `src/lsp_server.sd7` (include, dispatch branch, capability), `Makefile`
  (`TESTS += blocks folding`), `tests/transcript.py`

**Interfaces:**
- Consumes: `skipWhitespace`, `nextToken`, `tok`, `TK_NAME`, `TK_OP`, `TK_COMMENT`,
  `TK_LINE_COMMENT` from `scan.sd7`; `lineCount` from `doc_store.sd7`.
- Produces:
  - `const type: blockRef is new struct { integer: startLine; integer: endLine; string: kind }`
    — `startLine`/`endLine` are 0-based inclusive, `kind` is `""`, `"comment"` or `"imports"`.
  - `const func array blockRef: blockRegions (in string: text, in integer: lastLine)` — every
    region, document order, innermost first inside one close, each already valid
    (`endLine > startLine`, `endLine <= lastLine`).
  - `const func array blockRef: enclosingRegions (in string: text, in integer: line0,
     in integer: lastLine)` — the chain containing that line, innermost first. `length` 0 means
     "nothing encloses it". The column is deliberately absent: block regions are line-granular,
     and the column-precise level comes from `tokenAt`.
- Both walk the whole text in one pass, and `enclosingRegions` is the same walk filtered: one set
  of construct rules in the repository, which is what lets Task 11 and the later local-scope spec
  reuse them without re-deriving anything.

- [ ] **Step 1: Write the failing suite for the rules themselves.** Testing the rules here, rather
  than only through a JSON serialiser, is what lets Task 11 reuse them without re-pinning them:

```seed7
$ include "seed7_05.s7i";
  include "lsp_tst.sd7";
  include "blocks.sd7";

# "start-end:kind" joined by " ", so a whole answer fits on one reviewable line.
const func string: regionsOf (in string: text) is func
  result
    var string: out is "";
  local
    var array blockRef: rs is 0 times blockRef.value;
    var integer: i is 0;
    var integer: lastLine is 0;
    var string: tag is "";
  begin
    lastLine := pred(linesIn(text));
    rs := blockRegions(text, lastLine);
    for i range 1 to length(rs) do
      tag := str(rs[i].startLine) & "-" & str(rs[i].endLine);
      if rs[i].kind <> "" then
        tag := tag & ":" & rs[i].kind;
      end if;
      if out <> "" then
        out := out & " ";
      end if;
      out := out & tag;
    end for;
  end func;

const func string: chainOf (in string: text, in integer: line0) is func
  result
    var string: out is "";
  local
    var array blockRef: rs is 0 times blockRef.value;
    var integer: i is 0;
  begin
    rs := enclosingRegions(text, line0, pred(linesIn(text)));
    for i range 1 to length(rs) do
      if out <> "" then
        out := out & " ";
      end if;
      out := out & str(rs[i].startLine) & "-" & str(rs[i].endLine);
    end for;
  end func;

# Line count without a document, so the rules are testable without doc_store.
const func integer: linesIn (in string: text) is func
  result
    var integer: out is 1;
  local
    var integer: i is 0;
  begin
    for i range 1 to length(text) do
      if text[i] = '\n' then
        out +:= 1;
      end if;
    end for;
  end func;

const proc: main is func
  begin
    check("an empty text folds nothing", regionsOf(""), "");
    check("a one-line body is not a region",
          regionsOf("const proc: a is func\nbegin\n  noop;\nend func;\n"), "0-3 1-3");
    check("if/end if nests inside the callable body",
          regionsOf("const proc: a is func\nbegin\n  if TRUE then\n    noop;\n  end if;\nend func;\n"),
          "0-5 1-5 2-4");
    check("repeat closes at until",
          regionsOf("repeat\n  noop;\nuntil TRUE;\nwriteln(1);\n"), "0-2");
    check("a clause region ends at its sibling",
          regionsOf("if a then\n  x := 1;\nelsif b then\n  x := 2;\nend if;\n"), "0-4 1-2 3-4");
    check("a comment region is the comment",
          regionsOf("(* one\n   two *)\nwriteln(1);\n"), "0-1:comment");
    check("a run of line comments is one region, a single one is none",
          regionsOf("# a\n# b\n# c\nwriteln(1);\n"), "0-2:comment");
    check("a lone line comment yields nothing", regionsOf("# only one\nwriteln(1);\n"), "");
    check("a run of includes is an imports region",
          regionsOf("$ include \"seed7_05.s7i\";\n  include \"stdio.s7i\";\nwriteln(1);\n"),
          "0-1:imports");
    check("a keyword inside a comment opens no region",
          regionsOf("(* if\n  still comment\n *)\nwriteln(1);\n"), "0-2:comment");
    check("an unclosed construct ends on the last line",
          regionsOf("const proc: a is func\nbegin\n  if TRUE then\n"), "0-2 1-2");
    check("a struct type body is a region",
          regionsOf("const type: t is new struct\n  var integer: a is 0;\nend struct;\n"), "0-2");
    check("the chain at a position runs innermost first",
          chainOf("const proc: a is func\nbegin\n  if TRUE then\n    noop;\n  end if;\nend func;\n",
                  3), "2-4 1-5 0-5");
    check("a line outside every construct has no chain",
          chainOf("writeln(1);\n", 0), "");
    report("blocks");
  end func;
```

- [ ] **Step 2: Run it, and name the failure.** `make test-blocks`. Expected: no graded line —
  `blocks.sd7` does not exist, so the suite analyses to nothing, prints nothing and exits 0, and
  the recipe's grep fails to find `blocks: N checks, 0 failed`.

- [ ] **Step 3: Write the machine.** `src/blocks.sd7`. The declaration order is forced: predicates,
  then stack ops, then the walk, then the two exported functions.

```seed7
$ include "seed7_05.s7i";
  include "scan.sd7";

# Seed7's block structure, read off the token stream. The construct inventory is
# seed7-mode.el's seed7-block-start-regexp / seed7-block-end-regexp cross-checked against
# manual/stats.htm 5 and decls.htm 3.2. A construct keyword inside a comment or a string cannot
# reach this, because those are TK_COMMENT/TK_STRING tokens and never TK_NAME -- which is why
# this file reads the scanner and not the source lines.
#
# Nothing here knows positions: a region is a pair of LINES. LSP ranges are built by the feature
# that asks (invariant 2), and the later local-scope spec needs exactly the same pairs.

const type: blockRef is new struct
    var integer: startLine is 0;
    var integer: endLine is 0;
    var string: kind is "";
  end struct;

const integer: MAX_BLOCK_DEPTH is 64;

const type: blockStack is new struct
    var array string: closer is 0 times "";
    var array integer: openLine is 0 times 0;
    var array string: kind is 0 times "";
  end struct;

const func boolean: isControl (in string: nm) is
  return nm = "if" or nm = "for" or nm = "while" or nm = "case" or
         nm = "block" or nm = "global";

const func boolean: isSection (in string: nm) is
  return nm = "result" or nm = "local" or nm = "begin" or nm = "exception";

const func boolean: isClause (in string: nm) is
  return nm = "when" or nm = "otherwise" or nm = "elsif" or nm = "else";

const func boolean: isTypeBody (in string: nm) is
  return nm = "struct" or nm = "enum";

const func integer: topWithCloser (in blockStack: st, in string: closer) is func
  result
    var integer: out is 0;
  local
    var integer: i is 0;
  begin
    out := 0;
    for i range 1 to length(st.closer) do
      if st.closer[i] = closer then
        out := i;
      end if;
    end for;
  end func;

const proc: pushBlock (inout blockStack: st, in string: closer,
                       in integer: line0, in string: kind) is func
  begin
    if length(st.closer) < MAX_BLOCK_DEPTH then
      st.closer &:= closer;
      st.openLine &:= line0;
      st.kind &:= kind;
    end if;
  end proc;

# Closes every region from `index` up, innermost last, and pops them.
const proc: closeFrom (inout blockStack: st, inout array blockRef: out,
                       in integer: index, in integer: endLine) is func
  local
    var integer: i is 0;
    var blockRef: r is blockRef.value;
  begin
    if index > 0 then
      for i range index to length(st.closer) do
        if st.openLine[i] < endLine then
          r.startLine := st.openLine[i];
          r.endLine := endLine;
          r.kind := st.kind[i];
          out &:= r;
        end if;
      end for;
      while length(st.closer) >= index and length(st.closer) > 0 do
        remove(st.closer, length(st.closer), 1);
        remove(st.openLine, length(st.openLine), 1);
        remove(st.kind, length(st.kind), 1);
      end while;
    end if;
  end func;
```

`closeFrom`'s `st.openLine[i] < endLine` test is the "emit only when `endLine > startLine`" rule,
and it lives here so no serialiser has to remember it. Then the walk, complete — the ten rules of
spec §5 as its branches, and the three runs (comment, line-comment, include) flushed after the
loop:

```seed7
const proc: walkRegions (in string: text, inout array blockRef: out,
                         in integer: lastLine) is func
  local
    var scanCursor: cur is scanCursor.value;
    var blockStack: st is blockStack.value;
    var tok: tk is tok.value;
    var tok2 is tok.value;
    var integer: index is 0;
    var string: pending is "";
    var string: word is "";
    var integer: runStart is 0;
    var integer: runStop is 0;
    var boolean: inRun is FALSE;
    var integer: impStart is 0;
    var integer: impStop is 0;
    var boolean: inImp is FALSE;
    var blockRef: r is blockRef.value;
  begin
    while cur.offset <= length(text) do
      skipWhitespace(text, cur);
      if cur.offset > length(text) then
      else
        tk := nextToken(text, cur);
        if tk.kind = TK_COMMENT then
          # rule 7: the cursor is left on the line the comment ended on, which is the
          # only place a multi-line token's end is ever needed.
          if cur.line0 > tk.line0 then
            r.startLine := tk.line0; r.endLine := cur.line0; r.kind := "comment";
            out &:= r;
          end if;
        elsif tk.kind = TK_LINE_COMMENT then
          # rule 9: a run of consecutive # lines, one region.
          if inRun and tk.line0 = succ(runStop) then
            runStop := tk.line0;
          else
            if inRun and runStop > runStart then
              r.startLine := runStart; r.endLine := runStop; r.kind := "comment";
              out &:= r;
            end if;
            runStart := tk.line0; runStop := tk.line0; inRun := TRUE;
          end if;
        elsif tk.kind = TK_OP then
          # rule 10: a $ pragma, which may be an include line.
          word := text[tk.start .. tk.stop];
          if word = "$" then
            skipWhitespace(text, cur);
            if cur.offset <= length(text) then
              tok2 := nextToken(text, cur);
              if tok2.kind = TK_NAME and text[tok2.start .. tok2.stop] = "include" then
                if inImp and tk.line0 <= succ(impStop) then
                  impStop := tk.line0;
                else
                  if inImp and impStop > impStart then
                    r.startLine := impStart; r.endLine := impStop; r.kind := "imports";
                    out &:= r;
                  end if;
                  impStart := tk.line0; impStop := tk.line0; inImp := TRUE;
                end if;
              end if;
            end if;
          end if;
        elsif tk.kind = TK_NAME then
          word := text[tk.start .. tk.stop];
          if pending = "func" then
            pending := "";
            if word = "func" then
              pushBlock(st, "end func", tk.line0, "");
            elsif isTypeBody(word) then
              pushBlock(st, "end " & word, tk.line0, "");
            end if;
          elsif isControl(word) then
            pushBlock(st, "end " & word, tk.line0, "");
          elsif word = "repeat" then
            pushBlock(st, "until", tk.line0, "");
          elsif word = "until" then
            closeFrom(st, out, topWithCloser(st, "until"), tk.line0);
          elsif word = "end" then
            closeFrom(st, out, endIndexOf(text, cur, st), tk.line0);
          elsif isSection(word) then
            closeFrom(st, out, firstAtOrAbove(st, "section"), tk.line0);
            pushBlock(st, "section", tk.line0, "");
          elsif isClause(word) then
            closeFrom(st, out, firstAtOrAbove(st, "clause"), tk.line0);
            pushBlock(st, "clause", tk.line0, "");
          elsif word = "is" or word = "new" or word = "sub" then
            pending := "func";
          end if;
        end if;
        if tk.kind <> TK_LINE_COMMENT and inRun then
          if runStop > runStart then
            r.startLine := runStart; r.endLine := runStop; r.kind := "comment";
            out &:= r;
          end if;
          inRun := FALSE;
        end if;
      end if;
    end while;
    if inRun and runStop > runStart then
      r.startLine := runStart; r.endLine := runStop; r.kind := "comment";
      out &:= r;
    end if;
    if inImp and impStop > impStart then
      r.startLine := impStart; r.endLine := impStop; r.kind := "imports";
      out &:= r;
    end if;
    closeFrom(st, out, 1, lastLine);
  end func;
```

Two helpers the walk calls, both above it:

```seed7
# The stack index an `end <word>` closes: 0 to close nothing. An unbalanced end, or an
# `end` for something never opened, is the analyzer's error to report -- folding invents
# nothing, which is why 0 is the answer rather than the innermost region.
const func integer: endIndexOf (in string: text, inout scanCursor: cur,
                                in blockStack: st) is func
  result
    var integer: out is 0;
  local
    var tok: tk is tok.value;
    var string: word is "";
  begin
    out := 0;
    skipWhitespace(text, cur);
    if cur.offset <= length(text) then
      tk := nextToken(text, cur);
      if tk.kind = TK_NAME then
        word := text[tk.start .. tk.stop];
        if word = "func" or word = "if" or word = "for" or word = "while" or
           word = "case" or word = "block" or word = "global" or word = "struct" or
           word = "enum" then
          out := topWithCloser(st, "end " & word);
          if out = 0 and word = "block" then
            out := topWithCloser(st, "end block");
          end if;
        end if;
      end if;
    end if;
  end func;
```

`endIndexOf` consumes the construct word, which is what the walk wants — the name after `end`
must not be seen again as a control opener, and `if`/`for`/`while`/`case` are openers in
`isControl`. That consumption is also why the helper takes `inout scanCursor`.

```seed7
# The first open region of this kind at or above the innermost body region, or 0. A section or
# a clause ends at its next sibling, not at the end of the document, and it must not close the
# callable body that contains it -- so the search starts below the innermost "end func".
const func integer: firstAtOrAbove (in blockStack: st, in string: kind) is func
  result
    var integer: out is 0;
  local
    var integer: body is 0;
    var integer: i is 0;
  begin
    out := 0;
    body := topWithCloser(st, "end func");
    for i range succ(body) to length(st.kind) do
      if out = 0 and st.kind[i] = kind then
        out := i;
      end if;
    end for;
  end func;
```

`walkRegions`' last act is `closeFrom(st, out, 1, lastLine)`, which is what makes a truncated
buffer fold what it started, and `lastLine` comes from the caller's line table — never derived
from `length(text)` here, because that would make this file a position module.

The two exported functions, after `walkRegions`:

```seed7
const func array blockRef: blockRegions (in string: text,
                                         in integer: lastLine) is func
  result
    var array blockRef: out is 0 times blockRef.value;
  begin
    walkRegions(text, out, lastLine);
  end func;

# The chain containing a position, innermost first. A chain is a FILTER over regions, not a
# second machine: walkRegions appends outermost-of-a-group first as it closes, so the sweep here
# runs backwards to put the innermost first.
const func array blockRef: enclosingRegions (in string: text, in integer: line0,
                                             in integer: lastLine) is func
  result
    var array blockRef: out is 0 times blockRef.value;
  local
    var array blockRef: all is 0 times blockRef.value;
    var integer: i is 0;
    var blockRef: r is blockRef.value;
  begin
    walkRegions(text, all, lastLine);
    for i range length(all) downto 1 do
      if line0 >= all[i].startLine and line0 <= all[i].endLine then
        r := all[i];
        out &:= r;
      end if;
    end for;
  end func;
```

`enclosingRegions` takes no column: a *line* is the unit of a block region, and the column matters
only for the token level, which Task 11 gets from `tokenAt`. Passing a column here would imply a
precision the data does not have.

- [ ] **Step 4: Run to green.** `make test-blocks` → `blocks: 14 checks, 0 failed`. Then
  `make test`.

- [ ] **Step 5: Prove five rules.** (i) rule 6's `index := 0` → `index := 1` (a bare `end` pops
  the stack): expected FAIL `an unclosed construct ends on the last line`. (ii) rule 3 → drop
  rule 5's `topWithCloser(st, "until")` to `topWithCloser(st, "end repeat")`, a closer nothing
  ever pushes: expected FAIL `repeat closes at until`. (iii) rule 7 → treat `begin` as a control
  opener: expected FAIL `a one-line body is not a region`. (iv) rule 9's `succ(prevLine)` →
  `prevLine`: expected FAIL `a run of line comments is one region, a single one is none` and FAIL
  `a lone line comment yields nothing`. (v) the `st.openLine[i] < endLine` guard in `closeFrom` →
  delete it: expected FAIL `an empty text folds nothing` stays green (no regions at all) — so the
  guard's real check is `a one-line body is not a region`; if that also passes, the guard is
  unreachable from any fixture, and per AGENTS.md the assertion is deleted rather than defended.
  Revert each per file.

- [ ] **Step 6: The serialiser.** `src/features/folding_range.sd7`:

```seed7
$ include "seed7_05.s7i";
  include "blocks.sd7";
  include "doc_store.sd7";
  include "jsonw.sd7";

# FoldingRange[]. startCharacter/endCharacter are omitted on purpose: they default to whole
# lines, and that is all a lineFoldingOnly client honours. rangeLimit is ignored -- the spec
# calls it a hint, and the client that sets one is the client that can cope without it.
# ponytail: no cap on regions; upgrade path is honouring rangeLimit from the client capability.
const func string: foldingResult (in lsDoc: doc) is func
  result
    var string: out is "";
  local
    var jsonWriter: w is jsonWriter.value;
    var array blockRef: rs is 0 times blockRef.value;
    var integer: i is 0;
  begin
    rs := blockRegions(doc.text, pred(lineCount(doc)));
    openArray(w);
    for i range 1 to length(rs) do
      openObject(w);
        field(w, "startLine"); addInt(w, rs[i].startLine);
        field(w, "endLine");   addInt(w, rs[i].endLine);
        if rs[i].kind <> "" then
          field(w, "kind"); addStr(w, rs[i].kind);
        end if;
      closeObject(w);
    end for;
    closeArray(w);
    out := finishJson(w);
  end func;
```

- [ ] **Step 7: Write its checks** in `tests/folding_test.sd7`, over the same fixtures, so the
  JSON shape is pinned separately from the rules:

```seed7
$ include "seed7_05.s7i";
  include "lsp_tst.sd7";
  include "doc_store.sd7";
  include "features/folding_range.sd7";

const func string: foldsOf (in string: text) is func
  result
    var string: out is "";
  local
    var lsDoc: doc is lsDoc.value;
  begin
    setVersion(doc, text, 1);
    out := foldingResult(doc);
  end func;

const proc: main is func
  begin
    check("empty document answers an empty array", foldsOf(""), "[]");
    check("a comment region carries its kind",
          foldsOf("(* one\n   two *)\nwriteln(1);\n"),
          "[{\"startLine\":0,\"endLine\":1,\"kind\":\"comment\"}]");
    check("a plain region omits kind entirely",
          foldsOf("repeat\n  noop;\nuntil TRUE;\n"),
          "[{\"startLine\":0,\"endLine\":2}]");
    check("line count clamps the last line",
          foldsOf("const proc: a is func\nbegin\n  if TRUE then"),
          "[{\"startLine\":0,\"endLine\":2},{\"startLine\":1,\"endLine\":2}]");
    report("folding");
  end func;
```

The last check is the clamp: the fixture has no trailing newline, so `lineCount` is 3 and
`endLine` 2 is the last valid line. A one-off in `lineStarts`' trailing-newline handling shows up
here and nowhere else.

- [ ] **Step 8: Wire it.** In `src/lsp_server.sd7` add `include "features/folding_range.sd7";`,
  the branch before the `else`, and the capability line `field(w, "foldingRangeProvider");
  addBool(w, TRUE);` after `documentSymbolProvider`.

```seed7
    elsif msg.method = "textDocument/foldingRange" then
      uri := uriOfRequest(msg);
      if uri <> "" and uri in openDocs then
        sendResult(msg.id, foldingResult(openDocs[uri]));
      else
        sendResult(msg.id, "[]");
      end if;
```

- [ ] **Step 9: Run everything, then the transcript checks.** `make test` green; in
  `tests/transcript.py`: `initialize` advertises `foldingRangeProvider`; `didOpen` then
  `textDocument/foldingRange` returns the fixture's regions; the same request for an unopened uri
  answers `[]`.

- [ ] **Step 10: Commit.**

```
git add src/blocks.sd7 src/features/folding_range.sd7 tests/blocks_test.sd7 tests/folding_test.sd7 src/lsp_server.sd7 Makefile tests/transcript.py
git commit -m "Read Seed7's block structure off the token stream, and fold it"
```

---

## Task 11: `textDocument/selectionRange`

Spec §6.1. The rules already exist and are already checked in Task 10; this task adds one
serialiser and one level the region list does not carry — the token itself.

**Files:**
- Create: `src/features/selection_range.sd7`
- Create: `tests/selection_range_test.sd7`
- Modify: `src/blocks.sd7` (export the document region only if needed), `src/lsp_server.sd7`,
  `Makefile` (`TESTS += selection_range`), `tests/transcript.py`

**Interfaces:**
- Consumes: `enclosingRegions(text, line0, lastLine)` (Task 10) for the chain, `tokenAt` (Task 8)
  for the innermost level, and `lspRangePair`/`lspRange`/`lineWidth`/`lineCount` from
  `doc_store.sd7`. `blockRegions` is Task 10's other export and this feature does not call it: a
  chain wants the regions *containing a line*, innermost first, which is `enclosingRegions`.
- Produces: `selectionResult (in lsDoc: doc, in jsonValue: positions) → string`, a
  `SelectionRange[]` with `parent` chains, one entry per requested position, in the order asked.

- [ ] **Step 1: Write the failing suite.**

```seed7
$ include "seed7_05.s7i";
  include "lsp_tst.sd7";
  include "doc_store.sd7";
  include "features/selection_range.sd7";

const func string: selectionsOf (in string: text, in string: positionsJson) is func
  result
    var string: out is "";
  local
    var lsDoc: doc is lsDoc.value;
  begin
    setVersion(doc, text, 1);
    out := selectionResult(doc, readJson(positionsJson));
  end func;

const proc: main is func
  begin
    check("no positions answers an empty array",
          selectionsOf("writeln(1);\n", "[]"), "[]");
    check("on a name the chain is token then enclosing body",
          selectionsOf("const proc: a is func\nbegin\n  writeln(1);\nend func;\n",
                       "[{\"line\":2,\"character\":3}]"),
          "[{\"range\":{\"start\":{\"line\":2,\"character\":2}," &
          "\"end\":{\"line\":2,\"character\":9}}," &
          "\"parent\":{\"range\":{\"start\":{\"line\":0,\"character\":0}," &
          "\"end\":{\"line\":3,\"character\":9}}}}]");
    check("a position on whitespace answers the empty range at that position",
          selectionsOf("writeln(1);\n\n", "[{\"line\":1,\"character\":0}]"),
          "[{\"range\":{\"start\":{\"line\":1,\"character\":0}," &
          "\"end\":{\"line\":1,\"character\":0}}}]");
    # measured by construction: "a b" has no constructs, so each chain is its token plus the
    # document; the first entry must be for the FIRST requested position (0,2) -> "b".
    check("two positions answer in the order asked",
          selectionsOf("a b\n",
                       "[{\"line\":0,\"character\":2},{\"line\":0,\"character\":0}]"),
          "[{\"range\":{\"start\":{\"line\":0,\"character\":2},"
          "\"end\":{\"line\":0,\"character\":3}},\"parent\":{\"range\":"
          "{\"start\":{\"line\":0,\"character\":0},\"end\":{\"line\":1,\"character\":0}}}}"
          ",{\"range\":{\"start\":{\"line\":0,\"character\":0},"
          "\"end\":{\"line\":0,\"character\":1}},\"parent\":{\"range\":"
          "{\"start\":{\"line\":0,\"character\":0},\"end\":{\"line\":1,\"character\":0}}}}]");
    report("selection_range");
  end func;
```
Each expected string is a concatenation of Seed7 string literals, which is what the `&` at the
end of a line means; the fourth check is the ordering contract and is written out in full because
`positions[i]` must belong to `result[i]`, and a chain answered in the wrong order selects the
wrong text without any client noticing. The suite needs `json.s7i` for the `readJson` in
`selectionsOf`, which is why it is in the include list below.

- [ ] **Step 2: Run it, and name the failure.** `make test-selection_range` → no graded line, the
  module is absent.

- [ ] **Step 3: Write it.** `rangeOfRegion` first, then the chain builder, then the request
  handler — Seed7 cannot call what is declared later, and all three are in one file.

```seed7
$ include "seed7_05.s7i";
  include "json.s7i";
  include "blocks.sd7";
  include "scan.sd7";
  include "doc_store.sd7";
  include "rpc.sd7";
  include "jsonw.sd7";

const integer: MAX_SELECT_POSITIONS is 32;

# The region's LSP range, from line numbers to positions. Every position in this file is built by
# doc_store, which owns conversion; rangeOfRegion only says which two positions bound it.
# The end is "one character past the line's last", which lspRange clamps to the line length --
# the same absurd-column trick lspRangeBytes uses for a diagnostic with no column.
const func string: rangeOfRegion (in lsDoc: doc, in blockRef: r) is func
  result
    var string: out is "";
  local
    var integer: endIdx is 1;
  begin
    endIdx := succ(r.endLine);
    out := "{\"start\":" <& lspRange(doc, succ(r.startLine), 1) <& ",\"end\":" &
           lspRange(doc, endIdx, lineWidth(doc.text, doc.lineStart[endIdx]) + 1) <& "}";
  end func;

# SelectionRange nests by wrapping, and the OUTERMOST range is the deepest object, so the wrap
# runs outermost first: {"range":token} is wrapped by each region in turn.
const func string: wrapRange (in string: rangeJson,
                              in string: childJson) is func
  result
    var string: out is "";
  begin
    if childJson = "" then
      out := "{\"range\":" & rangeJson & "}";
    else
      out := "{\"range\":" & rangeJson & ",\"parent\":" & childJson & "}";
    end if;
  end func;

# The whole-document level, which no construct provides: enclosingRegions answers only what the
# source encloses, and spec 6.1 ends every chain at the document.
const func string: documentRange is func
  result
    var string: out is "";
  local
    var integer: lastLine is 0;
  begin
    lastLine := pred(lineCount(doc));
    out := "{\"start\":{\"line\":0,\"character\":0},\"end\":{\"line\":" <&
           lastLine <& ",\"character\":0}}";
  end func;

const func string: selectionResult (in lsDoc: doc, in jsonValue: positions) is func
  result
    var string: out is "";
  local
    var jsonWriter: w is jsonWriter.value;
    var array blockRef: chain is 0 times blockRef.value;
    var integer: lastLine is 0;
    var integer: p is 0;
    var integer: count is 0;
    var integer: i is 0;
    var jsonValue: at is jsonValue.value;
    var integer: line0 is 0;
    var integer: character0 is 0;
    var tok: tk is tok.value;
    var string: acc is "";
  begin
    out := "[]";
    if category(positions) = JSON_ARRAY and length(positions) > 0 then
      lastLine := pred(lineCount(doc));
      openArray(w);
      count := length(positions);
      if count > MAX_SELECT_POSITIONS then
        count := MAX_SELECT_POSITIONS;
      end if;
      for p range 1 to count do
        at := itemAt(positions, p);
        line0 := intAt(at, "line", 0);
        character0 := intAt(at, "character", 0);
        if line0 > lastLine then
          line0 := lastLine;
        end if;
        tk := tokenAt(doc.text, line0, character0);
        if tk.start > 0 then
          acc := wrapRange(lspRangePair(doc, succ(tk.line0),
                                        tk.start - doc.lineStart[succ(tk.line0)] + 1,
                                        tk.stop - tk.start + 1), "");
        else
          acc := wrapRange(singlePositionRange(line0, character0), "");
        end if;
        chain := enclosingRegions(doc.text, line0, lastLine);
        # enclosingRegions answers innermost first, and the wrap needs outermost first
        for i range length(chain) downto 1 do
          acc := wrapRange(rangeOfRegion(doc, chain[i]), acc);
        end for;
        acc := wrapRange(documentRange, acc);
        raw(w, acc);
      end for;
      closeArray(w);
      out := finishJson(w);
    end if;
  end func;
```

`singlePositionRange` is the empty range at the position, which spec §6.1 allows explicitly and
this server prefers to a guessed selection:

```seed7
# Both positions are the requested one, so both numbers are already UTF-16 units straight from
# the request -- no conversion happens here, and nothing but whole numbers reaches <&.
const func string: singlePositionRange (in integer: line0,
                                        in integer: character0) is func
  result
    var string: out is "";
  begin
    out := "{\"start\":{\"line\":" <& line0 <& ",\"character\":" <& character0 <&
           "},\"end\":{\"line\":" <& line0 <& ",\"character\":" <& character0 <& "}}";
  end func;
```

`positions[i]` is contained in `result[i].range` on all three paths: the token range comes from the
token that contains the position, the empty range *is* the position, and the `line0 > lastLine`
clamp keeps a request for a line the document does not have inside the document.

- [ ] **Step 4: Run to green.** `make test-selection_range`, `make test`.

- [ ] **Step 5: Prove the three answers.** (i) delete the `else` arm of `wrapRange` so no level
  ever carries `"parent"`: expected FAIL the name-chain check, which is the only one that asserts
  a `parent`. (ii) iterate `chain` ascending instead of descending: expected FAIL the same check,
  because the nesting turns inside-out while the text stays plausible — this is the check that
  earns its keep. (iii) iterate positions in reverse (`count - p + 1`): expected FAIL `two
  positions answer in the order asked`. (iv) return `""` from `documentRange`: expected FAIL the
  whitespace check, whose chain is document-only and so disappears entirely. Revert each per
  file.

- [ ] **Step 6: Wire it** — `selectionRangeProvider: true`, and the branch, which reads
  `positions` as an array (`atKey(msg.params, "positions")`), not a single position; every other
  textDocument branch in this server takes one position, so this is the one place that must not
  be copy-pasted.

- [ ] **Step 7: Commit.**

```
git add src/features/selection_range.sd7 tests/selection_range_test.sd7 src/lsp_server.sd7 Makefile tests/transcript.py
git commit -m "selectionRange: the token, then the regions that contain it"
```

---

## Task 12: `textDocument/semanticTokens`

Spec §6.2, with two of the nine legend entries removed. That removal is a measurement, not a
taste call, and it is the first thing this task must record.

**Amendment to spec §6.2, made by this plan.** Two sources for Seed7's keyword vocabulary were
compared, and they disagree by forty words:

* `lib/syntax.s7i`'s `$ syntax` declarations yield **77** terminal words — including `and`, `or`,
  `not`, `array`, `set`, `hash`, `class`, `cast`, `assert`, `mod`, `div`, `mult`, `rem`, `times`,
  `value`, `getfunc`, `lpad`, `radix`, `sci`, `tuple`, `conv`, `digits`, `elem`, `find`, `parse`,
  `subtype`, `subrange`, `symb`, `symb`.
* `seed7-mode.el`'s seven curated keyword lists union to **50**, and 13 of those — `DYNAMIC`,
  `default`, `enum`, `fixLen`, `forward`, `len`, `noop`, `param`, `proc`, `result`, `end`, `begin`
  as a section, `local` as a section — appear in neither list at all, while `result`, `local` and
  `proc` are keywords the server's own README asks users to colour.

So neither source is complete, `array`/`mod`/`value` are simultaneously declared terminals and
ordinary-looking names, and the language is *extensible by design* (design §1: only the analyzer
knows what Seed7 is). A `keyword` token type would therefore be a guess that overrides a client
whose own grammar is not wrong. **`keyword` is dropped from the legend.** The same argument in
weaker form removes `parameter`: `analysis.sd7`'s `paramsOf` returns *strings* (`"integer: a"`),
so a parameter has no `symRec`, no declaration line and no position — reflection cannot say which
name in the text is a parameter.

Final legend, and the indices are load-bearing because the payload is integers:

```
STT_COMMENT 0   STT_STRING 1   STT_NUMBER 2   STT_FUNCTION 3
STT_TYPE 4      STT_VARIABLE 5 STT_ENUM_MEMBER 6
STMOD_DECLARATION 0             STMOD_DEFAULT_LIBRARY 1
```

`comment`, `string` and `number` stay: they come from the scanner, which is not guessing, and
`eglot`/TextMate disagree with nothing about them.

**Files:**
- Create: `src/features/semantic_tokens.sd7`
- Create: `tests/semantic_tokens_test.sd7`
- Modify: `src/features/kinds.sd7` (add `semanticTypeOf`), `src/lsp_server.sd7`,
  `Makefile` (`TESTS += semantic_tokens`), `tests/transcript.py`
- Modify: the spec's §6.2 and §8 legend, with the two-list comparison written in

**Interfaces:**
- Consumes: `skipWhitespace`, `nextToken`, `tok`, `TK_*`, the cached `array symRec`,
  `utf16CharLength` from `utf8bytes.sd7`.
- Produces: `semanticTokensLegend` (a nullary `const func string:` — Seed7 calls it **without**
  parentheses) and `tokensIn (in lsDoc: doc, in array symRec: syms, in string: ownPath,
  in integer: fromLine, in integer: toLine) → string`. `textDocument/semanticTokens/full` calls
  it with `0, lineCount(doc) - 1`; `/range` with the two requested lines. Both answer a
  `SemanticTokens` object; an unopened uri answers `null` from the dispatcher, not from here.

- [ ] **Step 1: Write the failing suite.** The expected arrays are written out flat, because a
  wrong delta in a relative encoding is a wrong *number* in the middle of a list and nothing else.

```seed7
$ include "seed7_05.s7i";
  include "lsp_tst.sd7";
  include "doc_store.sd7";
  include "analysis.sd7";
  include "features/semantic_tokens.sd7";

const func lsDoc: docOf (in string: text) is func
  result
    var lsDoc: out is lsDoc.value;
  begin
    setVersion(out, text, 1);
  end func;

const proc: main is func
  begin
    check("the legend is the seven types and two modifiers, in index order",
          semanticTokensLegend,
          "{\"tokenTypes\":[\"comment\",\"string\",\"number\",\"function\",\"type\"," &
          "\"variable\",\"enumMember\"]," &
          "\"tokenModifiers\":[\"declaration\",\"defaultLibrary\"]}");
    check("an empty document answers an empty data array",
          tokensIn(docOf(""), 0 times symRec.value, "/p/a.sd7", 0, 0),
          "{\"data\":[]}");
    # comment "(* note *)" is ten units at 0:0 -> 0,0,10,0,0; "42" starts at unit 11 on the same
    # line -> deltaStart 11 - 0, so 0,11,2,2,0; "q" is not declared anywhere and is not emitted.
    check("a comment and a number emit, and an unknown name does not",
          tokensIn(docOf("(* note *) 42 q"), 0 times symRec.value, "/p/a.sd7", 0, 0),
          "{\"data\":[0,0,10,0,0,0,11,2,2,0]}");
    check("punctuation emits nothing at all",
          tokensIn(docOf("a := (b) + c[1]"), 0 times symRec.value, "/p/a.sd7", 0, 0),
          "{\"data\":[]}");
    # One declaration, "writeln", reported by reflection at line1 = 2 (Seed7's 1-based line) in
    # a library. Line 0 is not the declaration line: mods = defaultLibrary = 2. Line 1 is:
    # mods = declaration(1) + defaultLibrary(2) = 3. The second token is on a later line, so its
    # deltaLine is 1 and its start is an absolute column, not a delta.
    check("modifiers and the cross-line delta rule, in one array",
          tokensIn(docOf("writeln\nwriteln"), oneWriteln(), "/p/a.sd7", 0, 1),
          "{\"data\":[0,0,7,3,2,1,0,7,3,3]}");
    # asking for line 1 only: emission is bounded, and the first emitted token's deltaLine is
    # still relative to the document start, so it is the absolute line.
    check("a range request rebases its first delta",
          tokensIn(docOf("writeln\nwriteln"), oneWriteln(), "/p/a.sd7", 1, 1),
          "{\"data\":[1,0,7,3,3]}");
    report("semantic_tokens");
  end func;
```

The two helpers, above `main` — Seed7 cannot call what is declared later:

```seed7
const func array symRec: oneWriteln is func
  result
    var array symRec: out is 0 times symRec.value;
  local
    var symRec: rec is symRec.value;
  begin
    rec.name := "writeln";
    rec.cat := "BLOCKOBJECT";
    rec.ty := "proc";
    rec.file := "/home/username/seed7/lib/stdio.s7i";
    rec.line1 := 2;
    rec.sign := "const proc: writeln";
    out &:= rec;
  end func;
```

`semanticTypeOf("BLOCKOBJECT", "proc")` is `STT_FUNCTION` = 3, the fourth number in both arrays;
`file` is neither the document path nor `BUFFER_FILE` ("STRING"), so `STMOD_DEFAULT_LIBRARY` = 2
is the fifth number of the first token.

- [ ] **Step 2: Run it, and name the failure.** `make test-semantic_tokens` → no graded line; the
  module does not exist.

- [ ] **Step 3: Add the class table to `kinds.sd7`,** beside the two mappings already there, and
  extend that file's header comment to say it now serves three consumers:

The seven `STT_*` and two `STMOD_*` constants move *into* `kinds.sd7`, because `semanticTypeOf`
returns them and a module may not include the module that includes it. `semantic_tokens.sd7`
therefore declares only `NO_CLASS` and uses the nine names from here:

```seed7
const integer: STT_COMMENT is 0;
const integer: STT_STRING is 1;
const integer: STT_NUMBER is 2;
const integer: STT_FUNCTION is 3;
const integer: STT_TYPE is 4;
const integer: STT_VARIABLE is 5;
const integer: STT_ENUM_MEMBER is 6;

const integer: STMOD_DECLARATION is 1;
const integer: STMOD_DEFAULT_LIBRARY is 2;
```

```seed7
# SemanticTokenType index for a declaration, the same lossy map as symbolKindOf: Seed7 has no
# methods or fields, so a type is STT_TYPE and everything callable is STT_FUNCTION.
# Returns -1 for nothing classifiable, which means the name is not emitted at all.
const func integer: semanticTypeOf (in string: cat, in string: ty) is func
  result
    var integer: out is -1;
  begin
    if cat = "TYPEOBJECT" then
      out := STT_TYPE;
    elsif cat = "ENUMLITERALOBJECT" then
      out := STT_ENUM_MEMBER;
    elsif startsWith(ty, "func ") or startsWith(ty, "proc") or
          cat = "BLOCKOBJECT" or cat = "ACTOBJECT" then
      out := STT_FUNCTION;
    elsif cat = "STRUCTOBJECT" then
      out := STT_TYPE;
    elsif cat = "VAROBJECT" or cat = "LOCALVOBJECT" then
      out := STT_VARIABLE;
    else
      out := STT_VARIABLE;
    end if;
  end func;
```

- [ ] **Step 4: Write the writer.** The classifier is built per request from the cached records,
  and three parallel hashes rather than one hash of records: a `symRec` in a hash value would copy
  its `sign` and `params` strings for all 3 048 names, and the classifier needs three integers,
  not a record.

```seed7
$ include "seed7_05.s7i";
  include "scan.sd7";
  include "doc_store.sd7";
  include "analysis.sd7";
  include "features/kinds.sd7";
  include "jsonw.sd7";

const integer: NO_CLASS is -1;

const type: classHash is hash [string] integer;

  end struct;

const func integer: literalType (in integer: kind) is func
  result
    var integer: out is NO_CLASS;
  begin
    out := NO_CLASS;
    if kind = TK_COMMENT or kind = TK_LINE_COMMENT then
      out := STT_COMMENT;
    elsif kind = TK_STRING or kind = TK_CHAR then
      out := STT_STRING;
    elsif kind = TK_NUMBER then
      out := STT_NUMBER;
    end if;
  end func;
```

`TK_OP`, `TK_BRACKET` and `TK_ILLEGAL` answer `NO_CLASS` because they are never emitted — Q4's
rule, stated once, in the function that decides. `TK_CHAR` joins `STT_STRING` because
`SemanticTokenTypes` has no character type.

```seed7
# name -> class index, first declaration wins for an overload set; name -> declaration line and
# name -> library flag for the two modifiers. Measured free: 3 048 inserts and 15 000 lookups cost
# nothing beside one parseStri.
const proc: buildClasses (in array symRec: syms, in string: ownPath,
                          inout classHash: classes, inout classHash: declLines,
                          inout classHash: library) is func
  local
    var integer: i is 0;
    var integer: idx is 0;
    var boolean: own is FALSE;
  begin
    for i range 1 to length(syms) do
      idx := semanticTypeOf(syms[i].cat, syms[i].ty);
      if idx >= 0 and not (syms[i].name in classes) then
        classes @:= [syms[i].name] idx;
        declLines @:= [syms[i].name] syms[i].line1;
        own := FALSE;
        if syms[i].file = ownPath or syms[i].file = BUFFER_FILE then
          own := TRUE;
        end if;
        if own then
          library @:= [syms[i].name] 0;
        else
          library @:= [syms[i].name] STMOD_DEFAULT_LIBRARY;
        end if;
      end if;
    end for;
  end func;
```

Two `if`s rather than `own and 0 or STMOD_DEFAULT_LIBRARY`, which is what it was first: Seed7's
`and`/`or` take booleans and yield booleans, so an integer on the right of one of them does not
match — a trap worth recording in `AGENTS.md` alongside the long-chain one.

```seed7
# One scan, five integers per token straight into the writer, nothing kept. The previous token's
# line and column are the only state, which is exactly what the relative encoding asks for.
# ponytail: O(document) per request; the upgrade path is the cached token array, which spec 4.3
# prices at 189-265 bytes per token.
const func string: tokensIn (in lsDoc: doc, in array symRec: syms, in string: ownPath,
                             in integer: fromLine, in integer: toLine) is func
  result
    var string: out is "";
  local
    var jsonWriter: w is jsonWriter.value;
    var classHash: classes is classHash.EMPTY_HASH;
    var classHash: declLines is classHash.EMPTY_HASH;
    var classHash: library is classHash.EMPTY_HASH;
    var scanCursor: cur is scanCursor.value;
    var tok: tk is tok.value;
    var string: word is "";
    var integer: kind is NO_CLASS;
    var integer: mods is 0;
    var integer: prevLine is 0;
    var integer: prevCol is 0;
  begin
    buildClasses(syms, ownPath, classes, declLines, library);
    openObject(w);
      field(w, "data");
      openArray(w);
      while cur.offset <= length(doc.text) do
        skipWhitespace(doc.text, cur);
        if cur.offset > length(doc.text) then
        else
          tk := nextToken(doc.text, cur);
          kind := literalType(tk.kind);
          mods := 0;
          if kind = NO_CLASS and tk.kind = TK_NAME then
            word := doc.text[tk.start .. tk.stop];
            if word in classes then
              kind := classes[word];
              if tk.line0 + 1 = declLines[word] then
                mods +:= STMOD_DECLARATION;
              end if;
              mods +:= library[word];
            end if;
          end if;
          if kind <> NO_CLASS and tk.width16 > 0 and tk.line0 >= fromLine and
             tk.line0 <= toLine then
            addInt(w, tk.line0 - prevLine);
            if tk.line0 = prevLine then
              addInt(w, tk.col16 - prevCol);
            else
              addInt(w, tk.col16);
            end if;
            addInt(w, tk.width16);
            addInt(w, kind);
            addInt(w, mods);
            prevLine := tk.line0;
            prevCol := tk.col16;
          end if;
        end if;
      end while;
      closeArray(w);
    closeObject(w);
    out := finishJson(w);
  end func;
```

A slice, not a helper: a function taking `lsDoc` would belong to `doc_store`, and this is text
extraction rather than position conversion.
`fromLine`/`toLine` bound *emission*, never scanning: `semanticTokens/range` MAY answer more than
it was asked, and a token that starts before the requested line is still correct to include.

- [ ] **Step 5: The Python-side decode check,** which is the one that proves the relative
  encoding rather than restating it. In `tests/transcript.py`:

```python
def decode_semantic_tokens(data):
    """Turn the 5-int relative array back into absolute (line, col, length, type, mods)."""
    out, line, col = [], 0, 0
    for i in range(0, len(data), 5):
        dline, dcol, length, ty, mods = data[i:i + 5]
        line += dline
        col = dcol if dline else col + dcol
        out.append((line, col, length, ty, mods))
    return out
```
Then a check on a fixture whose first line is `"π" writeln(x);` — an astral character before a
token — asserting the decoded tuple list equals
`[(0, 0, 5, 1, 0), (0, 7, 7, 3, 2), (0, 15, 1, 5, 0)]`-shaped values computed by hand from the
fixture. `expect(cond, label)` style as the rest of the file. This is the only check that runs the
encoding through the live UTF-16 path, so it must fail if a future change routes a token column
through `utf16Before`.

- [ ] **Step 6: Wire `full` and `range`,** and the capability — as an object, not `true`, because
  the legend is required:

```seed7
      field(w, "semanticTokensProvider");
      openObject(w);
        field(w, "legend"); raw(w, semanticTokensLegend);
        field(w, "range"); addBool(w, TRUE);
        field(w, "full");  addBool(w, TRUE);
      closeObject(w);
```

```seed7
    elsif msg.method = "textDocument/semanticTokens/full" then
      uri := uriOfRequest(msg);
      if uri <> "" and uri in openDocs then
        sendResult(msg.id, tokensIn(openDocs[uri], symbolsOfDocument(uri),
                                    pathOf(uri), 0, lineCount(openDocs[uri])));
      else
        sendResult(msg.id, "null");
      end if;
    elsif msg.method = "textDocument/semanticTokens/range" then
      uri := uriOfRequest(msg);
      if uri <> "" and uri in openDocs then
        span := atKey(msg.params, "range");
        # a missing or malformed bound falls back to the whole document: a client that asks for a
        # range it cannot describe still wants tokens.
        fromLine := intAt(atKey(span, "start"), "line", 0);
        toLine := intAt(atKey(span, "end"), "line", lineCount(openDocs[uri]) - 1);
        sendResult(msg.id, tokensIn(openDocs[uri], symbolsOfDocument(uri), pathOf(uri),
                                    fromLine, toLine));
      else
        sendResult(msg.id, "null");
      end if;
```

- [ ] **Step 7: Run to green.** `make test-semantic_tokens`, `make test`.
- [ ] **Step 8: Prove three rules.** (i) emit `TK_BRACKET` as `STT_VARIABLE`: expected FAIL on the
  two-token check, and the decoded transcript check goes FAIL too, which is the point of having
  both. (ii) drop the `not (name in out)` guard in `classOf` so a later overload wins: expected
  FAIL on the declaration-modifier check. (iii) remove the `dline` condition from the delta-start
  branch: expected FAIL the transcript decode check on the astral fixture. Revert per file.
- [ ] **Step 9: Commit.**

```
git add src/features/semantic_tokens.sd7 src/features/kinds.sd7 tests/semantic_tokens_test.sd7 src/lsp_server.sd7 tests/transcript.py Makefile
git commit -m "semanticTokens, and drop the keyword class the two authoritative lists disagree about"
```

---

## Task 13: the documents, the invariants, and the two numbers

**Files:** `AGENTS.md`, `README.md`,
`docs/superpowers/specs/2026-09-10-seed7-lsp-server-design.md`,
`docs/superpowers/specs/2026-09-18-…-m4-…-design.md`, `tests/analysis_test.sd7` (if a pinned
count moves).

- [ ] **Step 1: `AGENTS.md`.** Delete the Milestones paragraph that prescribes the cumulative
  UTF-16 column table and replace it with what shipped: columns carried forward by
  `nextToken`, and the measurement that made the table unnecessary (`utf16Before` ~31 ms per call
  at 200 000 characters). Rewrite invariant 3 for `utf8bytes.sd7` and delete the
  `doc_store`→`transport` apology. Move the `#`-is-both entry from "`doc_store.isRadixHash`
  decides" to "the scanner decides, because it knows whether it is inside a number token". Add
  the traps this plan met: `end func` and never `end proc`; `range a to b` in a `for` header and
  never `range a .. b`; `pos`, `at` and `idx` unusable as struct field names; no visitor API,
  because `in proc:` evaluates in the caller's scope; `writeln` of non-ASCII raises unless the
  destination is `STD_UTF8_OUT`.

- [ ] **Step 2: `README.md`.** Move folding, selectionRange and semanticTokens into "What works",
  each with the one sentence that says what it will not do — no region for a single-line comment,
  no `keyword`/`parameter` token and why, empty range where nothing encloses. Delete the
  char-escape hole paragraph and the `16#be|ef` entry, and narrow "Ranges are line-based" to the
  symbol features, naming `lspWholeLine` as the function that still uses it.

- [ ] **Step 3: The design authority.** `2026-09-10-…-design.md`: §2's file list gains
  `utf8bytes.sd7`, `blocks.sd7` and the three feature files, and loses `lsp_types.sd7` with the
  reason; §4's "Caching: none" becomes the §6 contract with its measurements; §5's row for the
  three features changes from "scan.sd7 only, no interpreter" to "tokens from `scan.sd7`, name
  classes from the cached symbol table"; §9 risk 4 gets its verdict — retired or confirmed, with
  the fixture count that says which.

- [ ] **Step 4: Re-grep the invariants** and paste the output into the commit message:

```
grep -rn 'progs.s7i' src/                                  # exactly one line
grep -rn 'addStr(w, str(' --include='*.sd7' src/           # empty
grep -rn 'utf8CharLength' src/ | grep 'const func'          # exactly one, in utf8bytes
grep -rn 'isRadixHash' src/                                 # empty, deleted by Task 7
grep -rn '65536' src/                                       # exactly one, in utf8bytes
```

- [ ] **Step 5: Measure the two claims** and put the numbers in this commit's message: a hover
  arriving after a `didChange` (was 82 ms across two analyses) and the largest
  `semanticTokens/full` frame for `lib/aes.s7i` with the punctuation rule in place.

- [ ] **Step 6: Final gate.** `make test` — every suite graded by its own total line, including
  `utf8bytes`, `scan`, `blocks`, `folding`, `selection_range`, `semantic_tokens` and the
  transcript. Then push the branch and open the pull request against `master`.
