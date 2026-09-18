# Seed7 LSP server — M4: the scanner and the token-backed features

Date: 2026-09-18 · Status: design agreed in review; spec for review ·
Spec: LSP 3.18 · Analysis engine: SEED7 5.4.10 ·
Authority: `2026-09-10-seed7-lsp-server-design.md`; this document amends it at §2, §4, §5 and §9
and is subordinate to it elsewhere.

## 1. What this milestone is

`src/scan.sd7` becomes the server's only Seed7 lexical machine, `doc_store.codeText` becomes a
projection of it, and the three `v1 cheap` features — `textDocument/foldingRange`,
`textDocument/selectionRange`, `textDocument/semanticTokens` — are built on the token stream.
Two prerequisites land first: the width tables move to `src/utf8bytes.sd7`, and per-token
UTF-16 columns stop going through a function that scans from index 1.

Not here, each with its own spec: local-variable completion (which the scanner unblocks),
R-F10, the trust gate, `semanticTokens` delta, `documentSymbol`/`definition` real ranges.

## 2. Decisions, with the question each answers

| question | decision | why it was a question |
|---|---|---|
| Do locals wait for the scanner? | yes | reflection reaches local *declarations* but not the enclosing scope; guessing the scope would ship a wrong feature |
| Does `scan.sd7` replace the mask or sit beside it? | **replace** | two lexical machines drift, and the drift is invisible until a table file is opened |
| Cache tokens per version, or stream? | **stream; cache only the mask** | a token record costs ~260 B in Seed7 (§4.3) — 21 MiB for `shiftjis.s7i` |
| Cumulative UTF-16 column table? | **no** | the scan carries `(line0, col16)` forward, so there is nothing to look up |
| Legend size? | **no bracket or operator tokens** | punctuation is 38–67 % of the stream depending on the file, and the client already colors it |
| May `semanticTokens` consult the analyzer? | **yes, via the cached symbol table** | a lexical-only legend restates what `eglot`/TextMate already derive |
| Does M4 fix the line-based ranges of `documentSymbol`/`definition`? | **no** | changing every existing response shape alongside a new lexer makes a regression unattributable |

## 3. The lexer

`src/scan.sd7` knows Seed7's lexical grammar and nothing else. It imports no `progs.s7i`
(invariant 1 holds), builds no LSP shape (invariant 4 holds), and includes `utf8bytes.sd7` for
UTF-16 unit counting.

### 3.1 Types

Kinds are integer constants, not an enum. Measured: Seed7 has no `Type.MEMBER` select — an
enum's members are introduced unqualified into scope, so `tokenKind.NAME` does not match, and
members named `NAME`, `NUMBER`, `STRI` or `CHAR` would collide with the library.

```
const integer: TK_ILLEGAL is 0;      const integer: TK_NAME is 1;
const integer: TK_OP is 2;           const integer: TK_BRACKET is 3;
const integer: TK_NUMBER is 4;       const integer: TK_STRING is 5;
const integer: TK_CHAR is 6;         const integer: TK_COMMENT is 7;
const integer: TK_LINE_COMMENT is 8;

const type: tok is new struct
    var integer: kind is 0;
    var integer: line0 is 0;      # 0-based, like every LSP line
    var integer: col16 is 0;      # UTF-16 units from the line start
    var integer: width16 is 0;    # UTF-16 units in the token
    var integer: start is 0;      # 1-based character index, first char
    var integer: stop is 0;       # 1-based character index, last char
  end struct;

const type: scanCursor is new struct
    var integer: offset is 1;     # next character index to scan
    var integer: line0 is 0;
    var integer: col16 is 0;
  end struct;

const func tok: nextToken (in string: text, inout scanCursor: cur) is func
```

Field names are load-bearing: `at`, `pos` and `idx` all fail to match as field names, because
`pos(c, .)`/`at(c, .)` resolves the select as a library attribute call first. `offset`, `start`,
`stop`, `line0`, `col16`, `width16`, `kind` are free — each verified with `s7`.

`nextToken` assumes `cur.offset` sits on a non-whitespace character, and advances `cur` past the
token it returns: `cur.offset` to one past `tok.stop`, `cur.line0`/`cur.col16` to the position
after the token. The caller owns whitespace and newline skipping, which is four comparisons.
The token's `col16` is the cursor's column *before* the token — the LSP `startCharacter`.

### 3.2 The rules, and the source of each

Every rule is `scanner.c` / `literal.c` / `numlit.c` behaviour, and `manual/tokens.htm` §10 is
the prose. The "closes" column is a defect recorded in README or AGENTS.md that this design
removes rather than works around.

| rule | source | closes |
|---|---|---|
| `#` is a line comment **unless** the scanner is inside a number token that has just read a decimal integer | `scanner.c` `case '#': scan_line_comment()`; `lit_number` → `basedInteger` | `doc_store.isRadixHash`, which guesses from the two neighbouring characters and so mis-decides `1# foo` and any `#` adjacent to a digit-final name |
| a name is `[A-Za-z_][A-Za-z0-9_]*` | `scan_symbol`'s letter/underline branch | — |
| an operator is a maximal run of special characters; brackets are single-character tokens and are *not* special characters | `scanner.c` `case '!'…` vs `case '('`, `case ')'…`; `manual/tokens.htm` §10.2.2–3 | `a<b` reading as one token, which `doc_store` records as *"What is still unsolved is the shape of a token"* |
| number: decimal digits, then **at most one of** `.` + digits (float, only when a digit follows), `_` (bigInteger), `#` + extended digits (based), `E`/`e` ± digits (exponent) | `lit_number`'s dispatch order | `16#be\|ef` hovering `beef`; `x[1 .. 5]` fusing `1`, `..`, `5` |
| string escapes: `\"` `\\` `\a\b\e\f\n\r\t\v` `\A`–`\Z`, `\<digits>;` where the digits may be a based literal, and `\` + whitespace/line-comment + `\` as a continuation that may cross newlines | `literal.c` `esc_tab`, `escape_sequence` (which calls `lit_number` for a digit), `skip_lines` | — |
| char: exactly **one** element then `'`, where an element may be variable length — `'x'`, `'''` (three apostrophes: open, content, close), `'\n'`, `'\9;'`, `'\16#ff;'` | `lit_char` | README's recorded mask hole: a numeric escape inside a char literal is counted as two characters, so the mask loses the two following its closing quote (`lib/jpeg.s7i` clusters the based form) |
| `(` immediately followed by `*` opens a comment, nesting counted; a lone `(` is a bracket | `scanner.c` `case '('` | — (already right, but in one machine instead of two) |
| EOF inside a string, char or comment ends the token at EOF; the scanner never raises | `CHAR_EXCEEDS`, `STRING_EXCEEDS`, `UNCLOSED_COMMENT` are analyzer errors, not scanner errors | a truncated buffer is the normal state while typing, so this path is the common case, not the edge case |
| non-ASCII letters join a name only under `$ names unicode;` (`symbol.unicodeNames`) | `scan_symbol_utf8` | see §3.4 |

### 3.3 What the scanner deliberately does not do

It does not resolve `::=`, `<&` or `&` into distinct tokens (a run is a run), it does not know
keywords (they are `TK_NAME` tokens; §6 classifies them), and it does not attempt the
`$`-pragma grammar beyond treating `$` as the start of an operator run. All three are fine for
folding, selection ranges and a name/literal legend, and each is stated here so nobody
later reads the scanner as a parser.

### 3.4 The one knowingly-wrong rule

`$ names unicode;` lets non-ASCII letters into names. The scanner will not implement it.
Measured census over `~/seed7/lib/*.s7i` (213 files) and `~/seed7/prg/*.sd7`: the pragma appears
as a pragma **nowhere** — the only textual matches are in `prg/chkerr.sd7`, inside string
literals the test feeds to the analyzer as source text. For scale, the same census counts 212
`$ syntax` and 152 `$ include` pragmas in `lib/`, so `$`-lines are ordinary and `$ names` is not
used at all. A file that does use it will see a name split at the first non-ASCII letter — a
wrong token boundary in one construct, in a pragma the whole distribution does not use. If real
code arrives that uses it, the scanner reads the pragma line and sets a flag; that is a feature,
not an oversight.

## 4. Derived state: what is held, what is streamed

### 4.1 Held, in `lsDoc`, per version

The **masked text** only: same length as `doc.text`, newlines preserved, every non-code
character replaced by a space. It is built by one scan and invalidated by `setVersion`.
`codeText` keeps its name, signature and contract, so `wordAt` and
`signature_help.callContextOf` are untouched — but it becomes a *projection of the scanner*
(the mask is "keep `TK_NAME`/`TK_OP`/`TK_BRACKET`/`TK_NUMBER` characters, blank the rest"),
which is what makes it one machine rather than two.

Cost: ~1 byte per character with copy-on-write, so the worst measured document costs 375 KB.

### 4.2 Held, beside `openDocs`, per version

The **`array symRec`**, one per document, replaced on each version. The saving is bigger than
"one double parse": today *every* symbol feature re-parses, because `lsp_server.sd7` calls
`symbolsOfDocument(uri)` inside the `documentSymbol`, `definition`, `hover`, `completion` and
`signatureHelp` branches, and that function is `analyzeSymbols(textToAnalyze(uri), libraryDirs)`
— one `parseStri` each. Measured at 41 ms a parse, a client that asks for a hover and a
definition on the same version spends 82 ms building the same 1 060 records twice, and a
`didChange` spends one more. The cache is the fix for all of them.

The cache cannot live in `lsDoc`, because `symRec` is declared in `analysis.sd7` and
`doc_store.sd7` must not come to include it: that would drag `progs.s7i` into the position
module through a side door and break invariant 1's intent.

### 4.3 Streamed, never held

`foldingRange`, `selectionRange` and `semanticTokens` each take **one fresh forward pass** and
write their answer as they go. The reason is Seed7's cost per value:

| representation, 100 000 tokens | RSS delta | per token |
|---|---|---|
| `array tok` (six integer fields) | 10.3 → 35.3 MiB | ~260 B |
| six parallel `array integer` | 10.2 → 29.1 MiB | ~200 B |
| `hash [string] integer` of 3 048 names | +488 KiB | — |
| one `array symRec` (1 060 records) | +1.15 MiB | — |

A full-document token array is therefore ~21 MiB for `lib/shiftjis.s7i` (85 155 tokens) and
~4.5 MiB for `lib/aes.s7i` (17 908) — per open document. Streaming the same file holds nothing
and measures 249 ms including process start and file read, with **RSS unchanged before and
after the scan**.

### 4.4 No cumulative UTF-16 table, and AGENTS.md changes

AGENTS.md's Milestones section says to "give each document a cumulative UTF-16 column table in
`setVersion` before semanticTokens exists". Its premise is correct and measured —
`utf16Before` scans from index 1 and costs ~31 ms for 200 000 characters, so per-token use is
quadratic — but its conclusion is not: a table is the fix for random access, and the scan is
sequential. `(line0, col16)` is carried forward by `nextToken` and stored in the token, so no
table is built, none is invalidated, and no second source of truth for column arithmetic
appears next to `utf16Length` and `charColumnForBytes`. Random access keeps what it has:
`charIndexOf` walks one line per incoming position, `charColumnForBytes` walks one line per
diagnostic, both bounded by line length. That paragraph of AGENTS.md is replaced, not
implemented.

If a future feature needs *character→offset* lookups repeatedly inside long lines — a token
range request over a 2000-column line, say — the table is then the right fix, in that feature's
plan.

### 4.5 `src/utf8bytes.sd7`

AGENTS.md's step 1. `utf8CharLength` moves out of `transport.sd7`; `utf16Before` and the
astral-unit rule move out of `doc_store.sd7` (its two `ord(ch) >= 65536` tests at lines 55 and
306 become one function); the new module owns both width rules and nothing else. `transport`
keeps every outbound byte count, `doc_store` keeps position conversion and consumes widths,
`scan` consumes the UTF-16 width of one character. Invariant 3's apology — *"`doc_store`
includes `transport.sd7` … a merge-time decision, not an accident"* — is deleted, because the
inversion it apologises for is gone.

## 5. `textDocument/foldingRange`

`result: FoldingRange[] | null`. `startCharacter`/`endCharacter` are **omitted**: they default
to the end of their line, which is what a whole-line fold means, and `lineFoldingOnly` clients
ignore them anyway. A region is emitted only when `endLine > startLine`, and both ends are
clamped into `0 ≤ line < lineCount`, because "clients are free to ignore invalid ranges" is a
permission the server should not take advantage of. `rangeLimit` is treated as the hint the
spec calls it and ignored; that is a `ponytail:` ceiling, upgrade path: honour it from the
client capability.

The construct inventory is `seed7-mode.el`'s `seed7-block-start-regexp` /
`seed7-block-end-regexp`, cross-checked against `manual/stats.htm` §5 and `decls.htm` §3.2.
Stack discipline, not line matching: `(* *)` comments are tokens, so a keyword inside one can
never open a region.

| region | opens (a `TK_NAME` token) | closes | kind |
|---|---|---|---|
| declaration | `const` / `var` at the start of a top-level statement | the `;` that ends the declaration, or `end func` / `end struct` / `end enum` | — |
| callable body | `is` followed by `func` | `end func` | — |
| section | `result` / `local` / `begin` / `exception` | the next section keyword or the enclosing closer | — |
| control | `if` `for` `while` `case` `block` `global` | matching `end if` … `end global` | — |
| loop without `end` | `repeat` | `until` | — |
| clause | `when` / `otherwise` / `elsif` / `else` | next sibling clause or the parent's closer | — |
| comment | `TK_COMMENT` spanning lines | — | `comment` |
| comment run | consecutive `TK_LINE_COMMENT` tokens on consecutive lines | last of the run | `comment` |
| include run | consecutive `$`-pragma `include` lines | last of the run | `imports` |

`end func` closes both the body and, with its terminating `;`, the declaration — so a nested
pair of regions, which is what an editor wants: fold the body, or fold the whole declaration.

Where the construct rules live: `src/blocks.sd7`, not `scan.sd7` and not a feature. Design §2
lists `scan.sd7` as owning "tokens, comments, blocks, token-at-offset", and that line is amended
here. Which names open a block is a claim about Seed7's *constructs*; `scan.sd7` is the lexicon,
and §3.3's "this is not a parser" is only true while construct keywords never appear in it.
Folding, selection ranges and the deferred local-scope spec all ask one question — what encloses
this line — and a single module answering it is what stops the three from disagreeing the way the
mask and the scanner were about to. `blocks.sd7` consumes tokens and exports line pairs: it takes
no position, converts nothing and builds no LSP shape, so invariants 2, 3 and 4 are untouched.

## 6. `textDocument/selectionRange` and `textDocument/semanticTokens`

### 6.1 selectionRange

Request carries `positions: Position[]`, so the answer is one `SelectionRange[]` in the same
order, and `positions[i]` must be contained in `result[i].range`. A single pass answers all
positions. The chain, innermost first through `parent`:

> token → clause → control block → section → callable body → declaration → whole document

A position on whitespace, inside a comment, or past the last token answers **the empty range at
that position**, which the spec permits explicitly, rather than a guessed range.

### 6.2 semanticTokens

Legend, registered up front, as the capability requires:

```
tokenTypes:     comment, string, number, function, type, variable, enumMember
tokenModifiers: declaration, defaultLibrary
range: true     full: true            # no delta: no resultId, no previousResultId state
```

Two entries that stood in this legend during review are gone, removed by measurement rather than
taste, and §8's capability must match. **`keyword`**: the terminals Seed7 declares for itself —
`grep -h '^\$ syntax' lib/syntax.s7i | grep -o '\.[a-z_][a-z_0-9]*\.' | tr -d '.' | sort -u` —
are 77 words, and they include `and`, `or`, `not`, `array`, `set`, `hash`, `class`, `cast`, `mod`,
`div`, `mult`, `rem`, `times`, `value`, `radix`, `sci`, `conv`, `digits`, `elem`, `find`, `parse`
and `tuple`: terminals of the declared syntax that are also ordinary-looking names. The curated
keyword lists in `seed7-mode.el` (seven of them, the source `completion.sd7` already copies) union
to 50, and the two sets differ by forty words in each direction — `result`, `local`, `proc`,
`enum`, `noop`, `DYNAMIC`, `forward`, `default`, `param`, `fixLen` and `len` are curated but appear
in no `$ syntax` declaration, while `array`, `set`, `hash`, `mod`, `div`, `value`, `class` and
`cast` are declared but in no curated list. Neither set is the truth about a language whose own
design says only the analyzer knows what Seed7 is; advertising a `keyword` class would let the
server override a client grammar that is not wrong, in the one way Q4's rule exists to avoid.
**`parameter`**: `analysis.sd7`'s `paramsOf` returns `array string` — a parameter has no `symRec`,
no declaration line and no position, so reflection cannot say which name in the text is a
parameter.

- **No `TK_BRACKET` or `TK_OP` token is emitted.** The rule, not a knob: a Seed7 operator is a
  `special_identifier` run whose meaning only the analyzer knows, and every client colors
  punctuation syntactically. Measured effect on the payload, with the 5-int encoding:

  | file | all tokens | emitted (punctuation dropped) | ints | JSON |
  |---|---|---|---|---|
  | `src/doc_store.sd7` | 2 367 | 1 467 | 7 335 | 44 KB |
  | `lib/jpeg.s7i` | 10 999 | 6 532 | 32 660 | 196 KB |
  | `lib/aes.s7i` | 17 908 | 7 559 | 37 795 | 226 KB |
  | `lib/shiftjis.s7i` | 85 155 | 28 515 | 142 575 | 850 KB |

  The 850 KB worst case is why `range` is advertised: a client coloring a visible window asks for
  a window.

- **Name classes come from the cached `symRec` list** through a `hash [string] integer` built
  beside it (§4.2). `features/kinds.sd7`, which already maps `category`+`type` to
  `SymbolKind`/`CompletionItemKind`, is the same table and is extended, not re-derived. A name
  matching no declaration is **not emitted** — absence means "client, keep your own view",
  while inventing `variable` for every identifier overrides a highlighter that is not wrong.
  Overloaded names carry one class: the first declaration's, since the legend cannot express
  "depends on the call".
- `keyword` needs the reserved list, and in Seed7 that list is *declared*. Measured source:
  `lib/syntax.s7i`'s 192 `$ syntax` lines, from which
  `grep -h '^\$ syntax' syntax.s7i | grep -o '\.[a-z_][a-z_0-9]*\.' | tr -d '.' | sort -u`
  yields 77 candidates — `and array assert attr begin block case … const … elsif end exception
  … if in include inout is … struct sub subrange subtype … until val value var varfunc when
  while`. That set is a superset: it mixes declared statement keywords with attribute and
  special-identifier names (`.conv.`, `.digits.`, `.elem.`, `.lpad.`, `.radix.`, `.sci.`), so it
  is filtered against the statement heads in `seed7_05.s7i:408-427`, which is where `if`, `while`,
  `for`, `case`, `repeat`, `block` and `exception` are actually declared. The result is a
  checked-in constant whose comment names the file, the command and the filter, so a later
  reader can re-derive it instead of trusting it. `completion.sd7:SEED7_KEYWORDS`, whose
  provenance is a copy of `seed7-mode.el`'s lists, stays as it is — it is a completion list, not
  a lexer table, and unifying the two is not this milestone's business.
- Multi-line `(* *)` comments are clipped to the line they start on unless the client advertises
  `multilineTokenSupport`, because a token whose length passes its line end is truncated by
  clients that lack it, and clipping ourselves is smaller than depending on that.
- `textDocument/semanticTokens/range` scans from the document start (the analyzer allows a
  broader answer) and emits tokens intersecting the requested range.

## 7. Error handling

- The scanner never raises: every branch terminates at EOF, and `nextToken` on an
  unrecognised character returns a one-character `TK_ILLEGAL` token and advances one character,
  so a malformed document cannot loop forever. `ILLEGAL_CHARACTER`-class input is the analyzer's
  to report; the scanner's job is to keep walking.
- The §4 crash-containment net in `main.sd7` stays unreachable. A new branch that *can* raise
  must arrive with a check that reaches it (AGENTS.md, "Do not fix these").
- A document that was never opened, or a position past its last line, answers like every other
  feature in this server: `null` for folding and semanticTokens, an empty array where the
  response is an array, and `-32601` is reserved for methods we do not implement.
- Frames: `Content-Length` counts the *bytes* of the payload, and an 850 KB token array is a
  850 KB frame — `MAX_FRAME_BYTES` guards inbound only, so outbound size is a design
  responsibility, which is what §6.2's legend rule exists to bound.
- `utf8CharLength` stays the single width rule (§4.5); a token's `width16` comes from
  `utf8bytes.sd7`, never from a fresh comparison.

## 8. Capabilities added

Static, per invariant 5, and each advertised only with its method answered:

```
foldingRangeProvider: true
selectionRangeProvider: true
semanticTokensProvider: { legend: {7 types, 2 modifiers as in §6.2}, range: true, full: true }
```

`positionEncoding` stays `"utf-16"`. `textDocument/diagnostic` stays unadvertised (design §4.5).

## 9. Testing

- **`tests/scan_test.sd7`** — one check per row of §3.2, fixtures lifted from
  `manual/tokens.htm` §10, whose own error transcripts are the oracle: nested
  `(* (* *) *)`; `'''`, `'\''`, `'\9;'`, `'\16#ff;'`; `"\` + newline + `\` continuation;
  `16#beef`, `2#0001_`, `12345_`, `12.3e-4`, `1e20`; `a<b`, `a <& b`, `x[1 .. 5]`; a `$`-pragma
  line; unterminated string, char and comment at EOF; astral characters inside a comment and
  inside a string, asserting `col16`/`width16` against hand-computed UTF-16 units.
- **`tests/features_test.sd7`** — the three builders as pure functions over a document:
  a region whose `endLine` clamps; two positions answered in order, one of them empty; the
  5-int relative array decoded by hand back to `(line, col, length, type)` and compared to the
  expected tokens; an unknown name emitting nothing.
- **`tests/transcript.py`** — `initialize` carries the three new capabilities; a real
  `didOpen` → `textDocument/semanticTokens/full` over a fixture with an astral character before
  a token, so the relative encoding is proved through the live position path and not only in a
  unit check; `foldingRange` and `selectionRange` round-trip; `-32601` no longer for them.
- **Mutation proof** per AGENTS.md, one production branch per check that is supposed to be able
  to fail: the radix-`#` rule, the variable-length char escape, `repeat`/`until`, the
  empty-range answer, the "unknown name emits nothing" rule, the `defaultLibrary` modifier, the
  astral column carry. Each mutation must make a *named* check FAIL, and is reverted per file
  from the commit, never with `git checkout -- .`.
- **Invariants re-grepped**: `grep -rn 'progs.s7i' src/` one line; `grep -rn 'str(' …` in
  serialization paths empty; `utf8CharLength` defined in exactly one file; `isRadixHash` gone.

## 10. Exit criteria

1. `make test` green, with `scan_test`, `features_test` and `transcript` all carrying new checks.
2. The five recorded holes closed and each pinned by a check that goes FAIL when its rule is
   mutated: the char-escape mask hole, `16#be|ef`, `a<b`, the two-machine drift, and the
   `isRadixHash` heuristic.
3. A request that arrives after a change costs one analysis, not two (measured, in the commit
   message).
4. `initialize` answers with the three capabilities; every new method is implemented before it
   is advertised.
5. The name-classifier's hash is built once per document version, not per token — the check that
   pins this is the `semanticTokens` timing recorded in exit criterion 6.
6. Two numbers measured before and after, in the commit messages: a hover arriving after a
   change, and the largest `semanticTokens/full` frame produced for `lib/aes.s7i`.
5. Design §2, §4 ("Caching: none"), §5 ("scan.sd7 only, no interpreter") and §9 (risk 4) and the
   AGENTS.md/README paragraphs named in §4.4 and §4.5 are corrected in the same branch, not
   after it.

## 11. Risks this spec accepts, stated

- **A lexical scanner paraphrases the analyzer.** Design §1 says only the analyzer knows what
  Seed7 is. That is true of the *grammar* and false of the *lexicon*: token boundaries do not
  depend on `$ syntax` declarations, except for `$ names unicode;` (§3.4). The scanner is
  therefore sound for folding, selection and a name/literal legend, and is not a parser
  and never used as one.
- **No keyword colouring at all**, for the reason in §6.2: a fixed list cannot be right in a
  language where constructs are declared, and the two available lists disagree by forty words.
  Folding is unaffected — it reads construct keywords as tokens, where a wrong guess costs a
  missing region rather than a wrong colour.
- **850 KB frames exist.** Bounded by the legend rule and `range`, not by a cap. If a client
  measurably suffers, the upgrade is a documented token ceiling, and the `ponytail:` comment
  says so in the file that would grow it.
- **`selectionRange` over a stream is O(document) per request.** Accepted for the same reason
  `codeText` already is; the upgrade path is §4.3's cached array, priced in that table.

## 12. Plan decomposition

Thirteen tasks, in the order that keeps `make test` green at every commit: the width-table
extraction, then the scanner one lexical class at a time (names/operators/brackets, numbers,
strings, chars, comments), then the two rewires that make it the only machine (mask, `wordAt`),
then the symbol cache, then the three features, then the documents. Each task ends red-first:
its own check is written, seen to fail for the stated reason, and only then implemented; each
mutation-provable branch is named in §9.
