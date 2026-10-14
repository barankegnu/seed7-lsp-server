# Seed7 LSP server — M5: the occurrence index, references, and file-local rename

Date: 2026-10-12 · Status: for review · Spec: LSP 3.18 · Analysis engine: SEED7 5.4.10 ·
Authority: `2026-09-10-seed7-lsp-server-design.md`; this document amends that file at §5
(references/rename row), §8 (the M5 exit criterion) and the README's "What does not work
yet". It is subordinate to it elsewhere, and to `AGENTS.md` on invariants.

## 1. What this milestone is

One new lexical machine — an occurrence index over the token stream of a single document —
and the two methods that answer from it: `textDocument/references` and
`textDocument/rename` with its `prepareRename` gate.

This is the milestone the design table promised. It shrank once one fact was measured (§11.1):
the reflection API cannot enumerate a use site. There is no walkable body — `body()` returns a
`CALLOBJECT` and `getValue(ref, attr reference)` does not match for it — and no
`firstDefinition`/`secondDefinition` equivalent is exposed at Seed7 level. So an occurrence
index is the only route, and the design's "later: references, rename" was always a scanner
feature wearing a semantic name.

The prior art confirms the shape rather than the ambition: `seed7-mode`'s cross-referencer
(`tools/s7xref.sd7`, by Thomas Mertes, adapted by Pierre Rouleau) iterates `globalObjects`,
prints `<id>\t<file>\t<line>`, drops entries whose `file` is `"?"`, and builds the same
synthetic `$ include` driver for a library buffer that `analysis.sd7` builds. It yields
declarations only, and Emacs hardcodes column 0 because it has none
(`seed7-mode.el:9829`). What this milestone adds over it is the column — `scan.sd7` already
carries a UTF-16 column per token.

## 2. Decisions, with the question each answers

Marked **(partner)** for what was decided in conversation, **(builder's call)** for what I
settled and they can overturn.

| question | decision | why it was a question |
|---|---|---|
| Debt or shelf — is this protocol conformance or new capability? | **(partner)** the owed milestone: M5 as the design table scopes it | The design promised references, rename and `workspace/symbol` under M5; the conformance list was real but not what was owed |
| All three? | **(partner)** all three were wanted | asked whether one would do; the answer was "all" |
| Does `workspace/symbol` belong here? | **(partner)** no — it waits for a project index with its own spec | it is the only one of the three that needs files the editor never opened, and with them file watching and staleness |
| References: this file, or the project? | **(partner)** "what uses this name in the file I'm editing" | this is the decision that deletes the directory walk, `didChangeWatchedFiles`, and a second R-F10 |
| The design's M5 criterion says "rename in a 2-file project updates both" | **(partner)** amend it: rename is file-local, and refuses when the declaration is not in the buffer | a rename that updates one file while others keep the old name is a server showing a falsehood; the honest alternative to refusing is the project index just declined |
| When a token's binding cannot be proved, references returns | **(partner)** every occurrence of that name in the file, plus a `window/logMessage` saying the binding was unresolved | an empty list reads as "unused", and that is a lie you would act on |
| Where does scope data come from? | **(builder's call)** `analysis.sd7` collects it into `symRec`; no new module reads `progs.s7i` | invariant 1 |
| Overloads | **(builder's call)** name-based: a rename renames the name, references lists uses of all overloads of that name | matches what `definition` and `hover` already do (`definition.sd7` emits every declaration with the same name, deduped on `(file, line)`) |
| Occurrences inside comments and strings | **(builder's call)** never | the scanner's `hiddenKind` set already names them, and `codeText` was the first draft's answer — see the correction below |
| Occurrences measured on the mask or on the text? | **(builder's call, correcting the first draft)** `doc.text`, skipping `hiddenKind` tokens | the mask replaces one character with one space, so a masked astral character costs a UTF-16 unit; measured 13 vs 11 on one line (§11.6) |
| A global's scope | **(builder's call)** the document minus the regions of same-named locals, parameters and result variables | "whole document" would silently rename a shadowing local and its declaration, and the result would still compile |
| `includeDeclaration` when the declaration is in a library | **(builder's call)** not emitted | this method answers the file being edited; cross-file declaration jumps are what `definitionProvider` already does |
| `newName` collision test | **(builder's call)** scope-aware; a same-named routine elsewhere in the file, and any overload sibling, are not collisions | a file-wide test would reject renames that compile cleanly, and the feature is already overload-blind |
| The `selectionRange` UTF-16 defect found on the way (§11.8) | **(builder's call)** fixed here, not left owed | the fix is the same new `doc_store.sd7` entry point §5 requires, and shipping a known wrong range beside the correct one is a choice nobody makes on purpose |

## 3. The occurrence index

`src/occurrences.sd7` — one module, no LSP shapes in it (invariant 4), no `progs.s7i`
(invariant 1). It includes `scan.sd7` and takes the document's own text plus the cached
`array symRec`.

```
const type: occurrence is new struct
    var integer: line0 is 0;      # 0-based, as every token record
    var integer: col16 is 0;      # UTF-16 column, carried by nextToken
    var integer: width16 is 0;    # in UTF-16 units, so a range needs no re-scan
    var integer: kind is 0;       # TK_NAME or TK_OP — nothing else is indexable
  end struct;

const func array occurrence: occurrencesOf (in string: text, in string: name) is func
```

`occurrencesOf` is a single pass of `nextToken` over **`doc.text`**, collecting name and
operator tokens whose text equals `name` and whose `kind` is not `hiddenKind`. It is not a
stored table: `scan.sd7` is O(document) per pass and the M4 decision was "stream; cache only
the mask", which this keeps. One request costs one pass over one document; `didChange`
invalidates nothing because nothing was cached, so the M4 one-analysis-per-version cache is
untouched.

Carrying `TK_OP` makes an operator *referenceable*, and it does not make it renameable — §6 owns
that refusal and states why a read can list what a write cannot rewrite.

**Why not `codeText`, corrected:** the first draft of this section claimed columns measured on
the mask "transfer to the real document unchanged". They do not. `scan.maskOf` replaces a hidden
token with one space **per character** (`src/scan.sd7:503-509`), and an astral character is one
character but two UTF-16 units, so every unit lost shifts the rest of the line left. Measured on
`x := "😀😀"; count := 1;`: `count` reports `col16 = 13` scanning `doc.text` and `11` scanning
`codeText` (§11.6). A rename built on the mask would write its edits two columns left, which is
the class of defect this server's whole `utf8bytes.sd7` existence is about. Skipping
`hiddenKind` tokens off the real text gives the same behaviour — an occurrence in a comment or
string stays impossible, not filtered by luck — with honest columns.

`MAX_OCCURRENCES` is 2000, applied after the pass, and hitting the cap is a
`window/logMessage` line, never a silent truncation — same rule as diagnostics.

## 4. Binding resolution

To answer "whose name is this", the index needs the set of names visible at a position. The
analyzer gives that per declaration, and it is a fact of this design rather than an assumption
(§11.1): a global `const proc`/`const func` object is a `BLOCKOBJECT`, and `BLOCKOBJECT` is
exactly the category `formalParams` / `localConsts` / `localVars` / `resultVar` accept. Each of
those inner objects carries `file()` and `line()` — a local's declaration line, inside the
buffer.

`analysis.sd7` grows two functions beside the existing `paramsOf` (`src/analysis.sd7:100`):
`constsOf` and `varsOf`, same shape, same `RANGE_ERROR` guard.

**Scope is not a list of names.** A `string` array like `params` cannot support either half of
what §4 needs: shadowing subtraction wants the *region* a local lives in, and
`includeDeclaration` on a local wants its own range. So scope is a record, not a name list:

```
const type: scopeRec is new struct
    var string: name is "";
    var integer: line1 is 0;      # declaration line, from the object's own line()
    var string: cat is "";        # REFPARAMOBJECT / VALUEPARAMOBJECT / LOCALVOBJECT / RESULTOBJECT
  end struct;
```

and `symRec` grows `locals` (an `array scopeRec`) beside its existing `array string` `params`.
`params` stays as it is — `buildSign` consumes it and renaming it drags hover, completion,
signatureHelp and documentSymbol into this milestone for no reason.

They are filled for buffer declarations only — `file = BUFFER_FILE` or the document's own path —
because a library local can shadow nothing visible in this file. That guard matters for cost:
`collectSyms` currently walks every `globalObjects` entry whose `file <> "?"`, which measured
3053 objects for a hello-world program, and three extra accessor walks per entry on every
analysis is the one place this milestone could make `didChange` slower. The plan's first task
measures `analyzeAll` before and after; if the buffer-only guard does not hold the cost, scope
becomes a lazy second call made only by `references`/`rename`, and the plan says so rather than
hoping.

Resolution, for the token at the request position:

| the name at the cursor is… | binding | scope of that symbol |
|---|---|---|
| a `locals`/`params`/`results` name of the enclosing declaration | that local | the enclosing declaration's `blockRef` region from `blocks.enclosingRegions` |
| the name of a declaration whose `file` is this buffer | that global | whole document **minus the regions of any local, parameter or result variable of the same name** |
| neither, but some `symRec` carries it | the library's | not renameable; references answers for this file |
| nothing (unresolvable, or the buffer's analysis is incomplete) | **unknown** | every occurrence of the name in the file, plus the log line |

The enclosing declaration is found with `blocks.blockRegions` innermost-first. The first draft
of this section said "the first region of a declaration kind", and that is not implementable:
`blocks.sd7` strips the kind to `""` for routine bodies and for `result`/`local`/`begin` sections
(`src/blocks.sd7:310` and `:314-315`, both `# Strip internal marker`), so `blockRef.kind` carries
only `"comment"`, `"imports"` and `"clause"` by the time a caller sees it — and those three
values are what `foldingRange` serialises, so they cannot be repurposed. `blockRef` grows a
separate field naming the *closer* (`"func"`/`"proc"`/`"type"`/control), which the stack in
`pushBlock` already knows. The stripping itself stays: this server must not change a shipped
response shape as a side effect of a new feature.

The mapping is not a line-containment test either. Reflection reports a multi-line header at its
**name line** while its region begins at the `is func` line — measured: `bigHeader` reports
`line = 5` and its body region starts at 8 — so a declaration record's `line1` will not fall
inside its own region. The index pairs a `symRec` to a region by the region that *starts* at or
after the declaration line and is closed by `end func;`/`end proc;`/`end` as appropriate, and the
plan must treat that pairing as its own tested unit, because every scope answer in this milestone
sits on it.

Nested routines are one level deeper than the table admits and stay that way: a `const func`
inside a `const func` resolves against the innermost routine's scope first, then the file's
globals. A struct body is not a scope with routines in it — a `const type … end struct` holds
fields only, and putting a routine inside its `begin` section does not parse (§11.7) — so field
access is a separate case, and an open question (§12).

## 5. `textDocument/references`

Request `ReferenceParams { textDocument, position, context { includeDeclaration } }`. Response
`Location[]` or `null`.

- One location per occurrence: exact `[col16, col16 + width16]` — this is the first feature in
  the server whose ranges are not line-based, and `documentSymbol`/`definition` stay line-based
  (M4 §2, "changing every existing response shape alongside a new lexer makes a regression
  unattributable"). Building it needs a new `doc_store.sd7` entry point taking
  `(line0, col16, width16)` directly — invariant 2 says only `doc_store` converts positions, and
  copying `selection_range.sd7:60`'s `lspRange(doc, succ(tk.line0), succ(tk.col16))` would be
  wrong: `lspRange` treats its `column1` as a *character* column and converts it with
  `utf16Before`, so feeding it a UTF-16 column double-converts on any line with a multi-byte
  character ahead of the token (§11.8, and it means `selectionRange` has that bug today).
- The declaration is emitted when `includeDeclaration` is true **and the declaration is in this
  buffer**, using the same whole-line range `definition` uses, because reflection has no column
  for a declaration. A declaration that lives in `seed7_05.s7i` is not emitted: this method
  answers "what uses this name in the file I'm editing", and cross-file declaration jumps are
  what the `definitionProvider` we already ship is for.
- A position in a comment or string, on whitespace, or on a suppressed operator character
  (`.`, `$`, `` ` ``, which `wordAt` already refuses), or on a **number or bracket token** yields
  `null`. The first draft listed only the first three, and the gap matters: a cursor on `16#beef`
  or on `(` otherwise reaches §4's row 4 and searches for the literal name `16#beef`, finds
  nothing, and returns an empty list — the "reads as unused" answer §2 calls a lie. Row 4 applies
  only to a name-shaped token that §4 could not bind (§11.11).
- A word that cannot be a declared identifier yields `null` — the keyword test runs after LOCAL and
  GLOBAL resolution and before the LIBRARY row (§11.11, R28 refined by R36). Ordering after rows 1–2
  is what protects a declared symbol named `type`; ordering before row 3 is what stops `references`
  on `for`, `in`, `is` or `to` from listing every occurrence in the file, since `globalObjects`
  reports 52 `for` records and no user declaration can carry that name. Seed7 has no reserved words
  (`Seed7Home/manual/intro.htm:230`), so `type`, `proc`, `result` and `enum` are legal names, and a
  program that declares `const func integer: type (in integer: n)` has a real symbol that
  `documentSymbol` and `hover` already list; gating on the word first would answer `null` for it.
- A name bound to nothing yields every occurrence plus the log line (§2, §4). For a rename the
  same state is an open question (§12.1).
- No capability key is needed: `referencesProvider` is a boolean.

## 6. `prepareRename` and `rename`

`renameProvider` becomes an object: `{"prepareProvider": true}`. That is the one place this
milestone must read the client's `initialize` params: the response shape is a `WorkspaceEdit`,
which is only usable when the client declares `workspace.applyEdit`. Absent that, the server
answers `null` and logs why, rather than returning an edit the client will ignore — the rule
from the design §6, "a capability is advertised only once its method is answered", applied one
level down.

**`prepareRename`** returns `{range, placeholder}` or `null`. It runs the resolution of §4 and
refuses, with a log line naming the reason, when: the binding is a library symbol; the token is
a keyword or a `$ syntax` operator (none of `if`, `then`, `do`, `:=`, `&` is renameable —
`seed7_05.s7i` declares them); the token's name is not a name at all; or the client cannot apply
edits. Refusal is `null`, not an error, which is what makes an editor grey out the menu item
instead of showing a failure.

Operators are refused by the "not a name at all" clause, not by the keyword arm, and what refuses
them is the token's KIND, not the symbol's provenance: `occurrenceAt` takes a record only when
`kind = TK_NAME`, so an operator cursor leaves `slot` at 0 whatever the index otherwise knows.
Two shapes reach that gate and `tests/features_test.sd7` pins both. A library operator — the `+`
in `counter := left + right;` — binds through the library row to `owner = "library"` with
`declLine1 = 0`, publishes one real location (§5) to `references`, and answers
`prepareRename: + is not a name`. An operator this buffer DECLARES is the case the kind gate alone
decides, because row 2 matches `syms[i].name` for any spelling: `<+`, declared as
`const func integer: (in integer: x) <+ (in integer: y)`, measures `owner = "global"`, resolved,
`declLine1 = 5`, `scopeUncertain = FALSE` — the arms that speak for a bound name are silent for
it — and `slot` is still 0, with all three of its records `TK_OP`, so the answer is the
same sentence, `prepareRename: <+ is not a name`, and `rename` answers it with its own name in
front. Take the kind gate away and this cursor is refused by NOTHING: measured after §12.2's
disclosure learned to count names only, `prepareRename` answers a range for `<+` and `rename`
answers three edits, one of them inside the `$ syntax` rule itself. It used to be caught one arm
later, by the `.` that the `$ syntax` rule writes immediately before the operator token, and the
kind test in `scopeHasFieldAccess` closed that backstop — which is why the refusal, not merely its
sentence, is now the proof that the gate fired. (Seed7 needs a `$ syntax expr:` rule before a new
operator symbol parses; measured, without one the analyzer answers "is" expected found "<+".) An operator handed in as `newName` is the
other half of the asymmetry and a `-32602` rejection rather than a refusal, because `scan.nameStart`
rejects `<` before any document is consulted; the two identifier rejections emit the identical
sentence, so the pin is on the words `rename: <+> is not a Seed7 identifier`, not on which arm
spoke them. `references` may publish the locations of a symbol whose spelling is punctuation,
because a list needs only the tokens, and `rename` may not rewrite one, because the cursor rule of
the write path admits `TK_NAME` and nothing else. M5 renames names.

**`rename`** re-runs resolution — `prepareRename` is not trusted to have happened, and the spec
does not require it — and answers `WorkspaceEdit { changes: { <uri>: [TextEdit] } }` with one
document entry and one `TextEdit` per occurrence. The array is in document order BY CONSTRUCTION, not by luck: the
declaration add-back can fire only when the declaration line lies OUTSIDE the scope window (a
local's header sits above its own region; a global's declaration is never inside a routine body),
and `inScope` returns scan order — so the add-back is always first. `holdsRecord` compares line
AND column, which is what makes the two paths mutually exclusive instead of overlapping. Two shapes are deliberately not used:
`documentChanges` (an optional-array form for a single file is a worse reader) and
`changeAnnotation` (3.18 optional, no editor needs it for a local rename).

`newName` validation is the cheap, high-value half of this feature and it happens before the
pass, against the scope §4 resolved to rather than against the whole file:

- reject an empty name, and a name that is not a Seed7 identifier — decided by
  `scan.nameStart`/`nameMore`, so the rule is not re-derived;
- reject a keyword or `$ syntax` operator;
- reject a name that collides **in the symbol's own scope**: for a buffer global, any global
  declaration of that name in this buffer; for a local, parameter or result variable, any name in
  its routine's `scopeRec`s plus its own routine's declaration name. A same-named routine in a
  *different* routine is not a collision and must not block the rename — that is the case
  `params`-as-strings could not see;
- **not** a collision: a legitimate overload. Seed7 accepts `foo(integer)` beside `foo(string)`,
  and §2 already made this feature overload-blind, so renaming one overload onto its sibling's
  name is a normal request that compiles; the check compares names, not signatures, and says so.
- the name must not be a stdlib name — `symRec`s whose `file` is not this buffer are excluded
  from the collision set, or nothing could be renamed to `count2`, which the standard library
  certainly has.

Each rejection answers the JSON-RPC error `-32602 InvalidParams`, which is what spec §Rename asks
for a bad name. Overwriting a sibling declaration in the same scope is a rename that compiles
into a `REDECLARATION` wall, and the client cannot warn about it.

`MAX_OCCURRENCES` caps both methods. Past the cap `references` truncates with the log line, and
`rename` refuses with `-32602`: a silently partial rename is the exact failure mode §2 refused.

**`.s7i` buffers are an open question (§12.3).** A library buffer is analysed through the
driver, which reads from disk, so its `symRec` lines are the *disk* lines (R-F10). Today
staleness only makes a diagnostic or a jump wrong; here stale lines would feed a scope decision
and an edit range, so a rename in an unsaved-edited `.s7i` can write TextEdits to the wrong
lines.

## 7. Protocol surface changes

- `InitializeResult.capabilities` gains `referencesProvider: true`,
  `renameProvider: {prepareProvider: true}`. Nothing else changes, and invariant 5 holds: still
  static, still no dynamic registration.
- `initialize` params are read for the first time: `workspace.applyEdit` (boolean) and nothing
  else. Everything else in that payload stays ignored, and that debt is recorded, not hidden —
  §10.
- `$/cancelRequest` stays ignored. A rename pass over one document is milliseconds; the design's
  "server-cancelable" claim is not one we make.

## 8. Amendment to the parent design

§8's M5 row reads *"occurrence index → references, rename, workspace/symbol — rename in a 2-file
project updates both"*. That row becomes:

| | Deliverable | Exit criterion |
|---|---|---|
| M5 | occurrence index → references, rename (file-local) | references names every occurrence of the bound symbol in the open file, with exact columns; a rename in one file updates that file completely and refuses anything declared elsewhere; a rename to an existing local's name is refused |

`workspace/symbol`, the project index and file watching move to a still-unscheduled M6 with the
note that the analyzer answers library declarations for free (§11.2), so M6's real cost is only
the files the editor never opened.

## 9. Testing and acceptance

Red first, one named check per rule, each mutation-provable — a branch no fixture reaches is a
missing fixture, not an equivalent mutant (AGENTS.md).

Unit (`tests/occurrences_test.sd7`, new suite in `Makefile`'s `TESTS`):

- a local and a global sharing a name resolve apart, and the global's references exclude the
  local's occurrences — the check that makes §4 row 2's "minus shadowing locals" real rather
  than a phrase;
- a local and a global sharing a name in a file where the global is used *before* the routine
  that shadows it, so the subtraction cannot be done by line order alone;
- two same-named locals in two routines resolve apart (this is the fixture that makes the
  2-file criterion's replacement meaningful — the shadowing bug is inside one file);
- a parameter, a `result` variable and a `local var` each bind; a `var` and a `const` local of
  the same name in one routine both bind (`localConsts` and `localVars` are separate lists);
- a multi-line routine header: the declaration record's line is the name line and its region
  starts at `is func`, so the pairing check is a fixture, not an assumption (§4, §11.9);
- `occurrencesOf` on a line whose earlier text holds an astral character inside a string, where
  the mask loses a UTF-16 unit: `x := "😀😀"; count := 1;` must answer column 13, not 11
  (§11.6). The BMP `"ππ"` fixture that was here would not have caught it, which is why it moved;
- a rename refused while the buffer is truncated — §12.1's answer, whichever it is;
- a cursor on `16#beef`, on `(` and on `end` answers `null` from `references`, not an empty list
  (§5);
- `newName` rejects: empty, `1abc`, a local's name inside that local's own routine, `:=`, `if`,
  and a legal new name accepts; a name that exists as a *different* routine's local and as an
  overload sibling accepts;
- a name bound to the library is not renameable but is referenceable;
- `occurrencesOf` finds nothing for `count` inside a `prg/calc7.sd7`-style continuation string,
  and nothing inside `{'"'}` in `lib/chartype.s7i` — the two cases `hiddenKind` skipping exists
  for, now proved from the real text rather than from the mask. **Pinned** in
  `tests/occurrences_test.sd7`: "a name inside a continued string literal is not an occurrence"
  (killed by letting the string arm end at the backslash) and "one name survives the continuation,
  and it is the one after the closing quote" (killed by dropping `scanLineBreak` inside
  `skipContinuation`, which leaves the literal spanning lines but reports the later token on the
  line it started on). For the char literal the two checks are not equal: "and what follows it on
  ITS OWN line is still code" is the discriminating input — an arm that fails to read the quote as
  the literal's element opens a string there, and the name on that line leaves the index — while
  "what follows a quote char literal on the next line is still code", the spelling this section
  asked for, survives every mutation OF THE CHAR ARM, because a string opened at that quote stops
  at its own line break (`scan.sd7:295` with `lineEnd` at `:182-183`) and a name below it is code
  either way. The claim is scoped to that arm: the check pins the following token's LINE, so a
  scanner that let a string cross a break would redden it. It is kept because this section measured
  that input, and it records a real answer, but it is a redundancy of the char arm, not a proof.
  "the numeric spelling of the same element is hidden the same way" exercises the escape arm
  (`scan.sd7:340-344`), which the quote spelling never reaches, yet no deletion of that branch
  reddens it — the leftovers re-tokenise and the total column advance is unchanged, so this suite
  stayed green while `scan_test.sd7` went red four times. Its value is the escape arm's WIDTH
  (`scan.sd7:343`): a fixed count moves `count` from `0:34:5` to `0:31:5` and reddens this check
  alone. The same regression is already pinned in `tests/scan_test.sd7` (`:351`, `:358`, and the
  mask `:449` for the deletion), so this is a duplicate seen from the occurrence index, not a new
  proof — and not the cannot-fail class either, since the width mutant kills it.
- a truncated buffer (the normal state mid-typing) resolves to *unknown* and `references` answers
  over-inclusive plus the log line — this is the check that keeps §4's fourth row honest;
- a field access `w.pix` where `pix` exists in two structs in one file — §12.2's answer.
  **Pinned** in `tests/features_test.sd7` on a fresh inline fixture (two structs each declaring
  `pix`, a global `pix`, and a routine whose own local is `pix`): "references over-includes across
  both structs, and lists them in document order" answers six locations for the cursor on `x.pix`
  and the list holds BOTH structs' field declarations, at lines 4 and 8; "and it says the list
  holds both structs' fields" sets `unresolved` with the field sentence rather than the unbound
  one, because the global row binds the spelling before §4's fourth row is reached; "prepareRename
  refuses a field access inside the symbol's window" and "and rename answers null with no error,
  refusing to half-rewrite two structs" state the write's side; "the field access inside a local
  of the same name answers its own window only" and "and it says so, with the field sentence for
  its own window" give the same ruling, disclosure included, for a cursor inside the routine that
  declares `pix` itself, where the window holds one field of each struct. The list is in DOCUMENT
  order: the
  six ranges descend 17, 17, 13, 6, 6, 4 as the lines rise, so nothing here is a column sort.
- a name that is a keyword, a number or a bracket yields `null` from `prepareRename`.

Wire (`tests/transcript.py`): initialize advertises both providers; `references` on an opened
fixture decodes to exact ranges; `prepareRename` on a library symbol answers `null`;
`rename` answers a `WorkspaceEdit` whose `changes` has one uri; a client *without*
`workspace.applyEdit` gets `null` and the server still answers everything else normally; the
log line for an unresolved binding arrives as a `window/logMessage` notification, not on
stdout.

Corpus, free and new: `seed7` ships 213 `lib/*.s7i` and 129 `prg/*.sd7`. A throwaway loop that
builds the occurrence index for every one of them, printing only failures, is the check that
`scan.sd7` + `occurrencesOf` do not fall over on real code — the same gate `seed7-mode` set for
its own release. It is not a suite and does not enter `make test`; it belongs to the spike.

## 10. Known limits, and what this leaves owed

- Rename and references are single-file, by decision (§2). Renaming a project's own symbol
  across its other files is M6.
- Overload-blind (§2): a name with two overloads in one file cannot be referenced "just for the
  second one". The analyzer's matching is not reachable from a position.
- `workspace/didChangeWatchedFiles`, `workspace/configuration`, `client/registerCapability`, and
  every other server→client request except the two above stay unbuilt; `workspace/configuration`
  is now a decision to *cut* for a personal setup, not an omission — settings come in on argv.
- `utf-8` position negotiation stays cut: we declare `utf-16`, which every client must support.
- Still owed and still not paid, unchanged from before this milestone, each its own spec: the
  trust gate (ten lines once `rootUri` is read, deferred deliberately — the user is the only
  operator and the README states the risk), R-F10 (an open `.s7i` is read from disk, which is a
  spec "must not"), and the response shapes that depend on unread client capabilities
  (`hierarchicalDocumentSymbolSupport`, `SymbolKind` `valueSet`).
- Nested `documentSymbol` hierarchy, local-variable completion, formatting, Windows: untouched.
- `selectionRange` reports the wrong UTF-16 range on a line with multi-byte text ahead of the
  token (§11.8) — a defect found by this design, fixed by it, with a wire check that goes red on
  the mutation.

## 11. Measured facts this design rests on

1. **No use sites.** `progs.s7i` exposes 53 actions; `body()`/`localConsts()`/`localVars()`/
   `resultVar()` raise `RANGE_ERROR` unless `category = BLOCKOBJECT` (their docstring precondition,
   `seed7/lib/progs.s7i:641-687`), and on a global routine that category holds. `formalParams`
   does NOT raise — measured on a real buffer: it raised on 0 of 3 328 objects, answering a list
   for anything that has none (`/tmp/m2_count_probe.sd7`, cited by Task 2's fix report), and
   `resultVar` on a `proc` returns ` *NULL_OBJECT* ` rather than raising; it is `line()` and
   `category()` of that reference which raise. `body` of a real routine reports `CALLOBJECT`, and
   `getValue(b, attr reference)` on it **fails to match**. `globalObjects` for a hello-world
   program: 3053 entries, 0 of category `SYMBOLOBJECT`. `globalObjects` is documented to return
   definitions in source declaration order (`progs.s7i:533`), which is what makes a
   declaration-order-dependent test meaningful at all — see §12.4.
2. **Scope is reachable.** On `/tmp/m5_scope.sd7`: `double` at line 3 → formals
   `count(REFPARAMOBJECT)`, `limit(VALUEPARAMOBJECT)` plus a trailing `double(SYMBOLOBJECT)`;
   `localVars` → `hidden(LOCALVOBJECT)`; `resultVar` → `total`. `main` at line 12 → `localVars`
   → `count(LOCALVOBJECT)`. Every one of those carries `file()` (the buffer path) and `line()`
   (3, 7, 12, 14). The trailing `SYMBOLOBJECT` is already excluded by `analysis.isParam`.
3. **Keywords are not objects.** `:=`, `&`, `+`, `func`, `proc`, `const`, `for` appear in
   `globalObjects` as `ACTOBJECT`/`TYPEOBJECT` with real file+line and many overloads (`for` has
   10). `if`, `while`, `then`, `do`, `begin`, `end`, `result`, `local`, `otherwise` do **not**
   appear — they are pure `$ syntax` symbols. `s7 -i` resolves them (`if → syntax.s7i(211)`),
   but that is a CLI dump, not an in-process query, so "is this a keyword" has no runtime
   answer from the analyzer and §6's keyword check is a list, owned by `completion.sd7`'s
   existing copied one until a real source exists.
4. **The error cap does not apply to us.** `parseFile`/`parseStri` report `errorCount = 26` on a
   20-line broken file with and without `NO_ERROR_LIMIT`; `error_maximum = 10`
   (`seed7/src/analyze.c:526-530`) limits *displayed* errors only. Our 100-diagnostic cap is a
   policy cap and is reachable.
5. **`globalObjects` cannot enumerate syntax declarations**, so a keyword list remains a build
   step against `lib/syntax.s7i` (194 `$ syntax` declarations), not a call. Recorded because it
   is the second time this branch has wanted a generated keyword list and failed to find one at
   runtime; the seven independent hand-written lists (FAQ, `seed7-mode`, six editor files in
   `seed7/doc`) still disagree with each other. One consequence is load-bearing and new: the
   keyword gate in §5/§6 would have reused `completion.sd7`'s copied list, which holds **39**
   entries and is missing nine words the language owns — `begin`, `when`, `static`, `forward`,
   `member`, `switch`, `leave`, `exit`, `include` (measured by extracting the array). A gap that
   was cosmetic for completion is a gate on a destructive operation the moment M5 lands.
   Re-measured as a source: the 90 bare identifiers appearing in the `$ syntax` templates of
   `lib/syntax.s7i` are the conservative keyword set — a superset that includes dot-selector
   words like `key` and `len`, which is the right direction of error for a gate that refuses
   renames and the wrong one for a completion list, so §5/§6's predicate and `completion`'s
   candidates are two sets, not one.
6. **`maskOf` loses UTF-16 units.** Measured on `x := "😀😀"; count := 1;`: `count` at
   `col16 = 13` from `doc.text`, `11` from `codeText`. Both scans agree on lines with no masked
   astral character ahead of them, which is why the BMP tests never saw it.
7. **A struct body holds fields only.** A `const func` inside a `const type … begin … end struct`
   does not analyse: `"end" expected found "begin"`, then `Declaration of "twice (val integer:
   n)" failed`. The first draft's fixture for a nested scope was impossible.
8. **`lspRange` takes a character column, not a UTF-16 column** (`src/doc_store.sd7:104-125`,
   which converts with `utf16Before`), while `src/features/selection_range.sd7:60` passes
   `succ(tk.col16)` into it. On a line with multi-byte text ahead of the token that is a
   double conversion, and it OVERSHOOTS: measured on `x := "😀😀"; count := 1;` the shipped code
   answers `15..20` where the token really sits at `13..18`, because the first 13 CHARACTERS
   expand to 15 UNITS. `selectionRange` therefore reports wrong ranges today, and M5 must not
   copy the pattern. Measured during Task 4: the same branch's sibling (the no-token else-branch,
   which passes the client's own UTF-16 `char0` through `lspRange`) is wrong the same way — a
   request at character 10 answers 12 — so both branches are fixed together, each with its own
   falsifiable astral check.
9. **Declaration line ≠ region start.** For a multi-line header, reflection reports the name line
   and `blocks` reports the body region from the `is func` line (measured: `bigHeader` at
   `line = 5`, region start 8). Scope pairing cannot be a containment test on the declaration
   record's own `line1`.
10. **Struct fields have no declaration source we can reach.** Re-measured on a two-field struct
    `Widget{pix, name}`: `globalObjects` reports only `Widget(TYPEOBJECT)` and `main(BLOCKOBJECT)`
    for the buffer — no `pix`, no `name` — and `structToList` on the `TYPEOBJECT` **raises
    `RANGE_ERROR`**. The builder check adds that `structSymbols` returns generated anonymous
    structs named by their field with `file = "?"`, which `collectSyms`' existing filter drops;
    that half I did not re-run. Either way there is no declaration source for a field, so a
    "find references" cursor on `pix` in `w.pix` is a permanent row-4 case on well-formed code —
    not the truncated-buffer exception §9 pins — and it is §12.2's question.
11. **"Is this a keyword?" is answerable only behaviourally, and the answer is 63 — which is also a
    correction to this document.** Seed7 has no reserved words (`Seed7Home/manual/intro.htm:230`),
    so a word's status is a property of the interpreter, not of any list, and the interpreter
    answers directly: declare `var integer: <WORD> is 1;` in one program per word and check whether
    `s7 -q -a` reports errors. Task 5 shipped that probe as `tools/keyword_gate.sh`, which prints
    the current set and exits 1 if `src/keywords.sd7` ever drifts from it — RUN IT rather than
    copying an answer out of here.
    My first hand sweep reported **48**, and it was wrong twice over: my `words.txt` listed `while`
    with no program behind it, and `raise` and `syntax` were never candidates at all, so an
    incomplete superset produced a confidently wrong count. The measured answer is **63**. The three
    additions were re-verified independently: `while`, `raise` and `syntax` each fail to analyse,
    while `type` and `value` analyse clean (`const func integer: type (in integer: n)` prints `3`).
    Three consequences, all carried into the plan: §5's gate runs after resolution (R28); the §11.5
    template extraction is a *vocabulary* list and must not be used as a gate, because over-refusal
    would deny a rename of a legal symbol rather than protect the user; and `completion`'s 39-word
    candidate list and this gate are different products that must not be merged. The meta-lesson is
    the R29 one: a number transcribed out of a probe is already stale, so the document points at
    the generator instead of at itself.
12. **Two records of one name on the declaration line refuse a rename — a shared header line is
    one shape of it, not the rule.** The rule is not the one-line-header special case I first
    measured. A routine `show` and a parameter
    `show` are both reported at that header line's `line1` whether the header is one line or two,
    and the collision reaches `rename` from three directions: a single-line header with a multi-line
    body (the shared line IS the line the body region opens on, so `inScope` over-includes and no
    add-back happens at all), a two-line header (the shared line is above the region, so the
    declaration add-back picks the wrong record), and a cursor on a call site (the routine resolves
    through the global row, whose `declLine1` is that same header line). A whole-routine-on-one-line
    body is a fourth case and is refused by `scopeUncertain`, not by this arm. Three of the four
    would edit a symbol the user did not name, so §6's refusal keys on the shared line in the
    PREDICATE, not on whether the add-back is the path in use — Task 9 measured the narrower rule
    and it left the over-inclusion live. Measured on `/tmp/ambig3.sd7`, `/tmp/ambig4.sd7` and
    Task 9's `/tmp/probe_shape.sd7`.

    **The arm's real trigger is the line, not the parameter shape, and that is a cost, not just a
    guard.** Two same-word records on a declaration line also arise with no parameter involved:
    `const integer: x is 1; const integer: y is x;` — reproduced on a clean buffer
    (`/tmp/r9probe.sd7`, `diags=0`), where `prepareRename` and `rename` BOTH refuse a perfectly
    legal rename of `x`. Over-refusal, safe direction, and the correct alternative is column-aware
    declaration identity, not another arm.

    **Both consequences of that are paid on `m5-review-fixes`, and the way they were tested is the
    finding.** The refusal sentence now says only what the arm counted — "shares its declaration
    line with another record of the same name" — and `features_test.sd7` proves it by *absence*:
    the `x`/`y` file has no routine and no parameter, and two assertions go red if the sentence
    names either word. The first version of that check compared `why` to a constant spelled in the
    same test file, so it passed green against the wrong sentence and moved with production instead
    of questioning it; it was rewritten before it was trusted. The "§12's boundary statement"
    this note cited does not exist in §12 — the phrase was this item's own title, now corrected
    above — so a reader no longer hunts §12 for a rule that lives here.
13. **`globalObjects` has no ordering contract in its signature, but does in prose**
    (`progs.s7i:533`: definitions are returned "in the same order as the definitions of the source
    program"). Task 2's `else`-reset witness, Task 3's pairing and Task 9's declaration add-back all
    depend on it. Two of the three pin it with a value that would change under a reordering; the
    dependency is stated here because no in-suite check can enforce an interpreter promise.

14. **The occurrence pass holds on the whole Seed7 corpus.** `tools/corpus_scan.sh` takes the
    first 12 indexable tokens off each file and asks `occurrencesOf` for each — a positive control,
    since the name came from the same scanner, so a zero is a bug in the index and not a missing
    fixture. Over every file in the checkout (`lib/*.s7i` 213, `prg/*.sd7` 129):
    `files=342 names_probed=4104 occurrences=516044 misses=0`. Cost, measured on the same run:
    about **40 ms per full-document pass** at an average of ~126 occurrences per name — the figure
    behind "one request, one pass" in §3. It checks termination and finding, NOT columns; those are
    pinned by the astral checks in Tasks 1, 4 and 9.
16. **A lone surrogate left the server as three bytes that are not valid UTF-8, and the fold was
    copying every string on the request path.** Two findings, one bound. (a) Task 13 made
    `joinSurrogates` total by construction — a stray high, a stray low and a high followed by a
    non-low all pass through, each pinned in `rpc_test.sd7`. Total on the *inside*, raw on the
    *outside*: `jsonw` wrote any character ≥ 32 as it stood, and Seed7's UTF-8 writer encodes a
    surrogate as its CESU-8 form. Measured by writing `chr(55296)` to `STD_UTF8_OUT`: bytes
    `41 ED A0 80 42` for `"A" & chr(55296) & "B"` — 5 bytes, which is exactly what
    `utf8bytes.utf8CharLength` claims for it, so `Content-Length` agreed, nothing raised and the
    stream stayed framed while the bytes stayed undecodable. `jsonw` now escapes `55296..57343` as
    `\udXXX`; everything outside the range still leaves as itself, which `jsonw_test.sd7` pins at
    55295, 57344 and 128512 so the branch cannot be widened by accident. The bounds live in
    `utf8bytes` (invariant 3 extended), because the writer and the folder must not disagree about
    where the range is. No crash was ever at stake — the Standards review's `RANGE_ERROR` worry was
    disproved by measurement — but a mangled name in a refusal line is a bug the client cannot fix.
    (b) `strAt` folded unconditionally, so a document-sized body paid one allocation per character
    on every `didChange`. Measured with `s7c -p -O2 -l src`, 50 `strAt` calls on the `text` of a
    234-line didOpen body (11 466 characters, no surrogate anywhere): **4 529 µs per call**
    folding, **478 µs per call** for the scan that skips it. A guard whose two paths are the same
    function — no input separates them, so no check can redden it and it is labelled as such; the
    pair-fold check at `rpc_test.sd7:76-77` is what would catch a guard that skipped too eagerly.

15. **`blocks.enclosingDeclarations` and `blocks.declarationRegion` were dead on arrival.** Task 3
    produced them for Task 6, and Task 6 grew its own pairing instead: `resolveBinding` scans
    `blockRegions` once and calls `routineRegionFor` per candidate, then `regionOwner`/`ownsRegion`
    decide whether the pair belongs to the record — one list, one sort, a field an `enclosing-
    Declarations` chain could not carry. So `declarationRegion` was `routineRegionFor` over a fresh
    scan with no caller, and `enclosingDeclarations` was a `closer <> ""` filter with no caller.
    Both deleted on `m5-review-fixes`, with the wrapper-only checks: `grep -rn
    'enclosingDeclarations|declarationRegion' src/` is empty, and `regionOfDeclaration` in
    `blocks_test.sd7` now calls the surviving pair directly so the seven pairing checks still test
    production. What did NOT move is the closer filter — "a non-routine region is not a scope" is
    pinned where it runs, at `occurrences_test.sd7`'s phantom-region check (a carrier with no
    region must not be handed the region at line 0), and the `closer` field itself stays pinned by
    this suite's `closerAt` checks. The pairing rule the deleted pair was supposed to own lives in
    §11.9's adjacency note and in `occurrences.regionOwner`, not here.

## 12. Open questions put to the partner

These three are forks where both branches are buildable, the answer changes what gets built, and
the wrong one either damages text or silently drops a use case. Everything else the builder check
raised is settled above or in §2 as a builder's call.

1. **What does `rename`/`prepareRename` do on an unprovable binding (§4 row 4)?** Refuse with
   `null`, or rename every same-named token in the file as `references` would list them. The
   over-inclusive rule was chosen for a *read*, where an empty list is the lie; on a *write* the
   over-inclusive answer rewrites locals the user did not mean. A refusal costs a daily friction
   — a truncated buffer is the normal state while typing, so rename would do nothing in the exact
   moment rename is asked for.
2. **Struct fields:** over-inclusive (every `pix` token in the file, including other structs'
   fields), refused (`null`, which needs a machine to recognise a field access at all), or a new
   token-level index over `const type … end struct` regions. Field names repeat across structs,
   and `w.pix` is pervasive in real Seed7, so this is a permanent row-4 case on well-formed code,
   not the truncated-buffer exception §9 pins.
   **Answered on `m5-review-fixes`, by measurement first.** A `pix` token that follows a `.` is
   now recognised — `occurrence.dotPrev`, stamped in `occurrencesOf`'s existing walk, which is the
   only place the previous token is known. The **write refuses** on it, in `renameDecision`, when
   the field access lies inside the symbol's own scope window: measured on `Widget` with a field
   `counter` read as `box.counter` by the routine whose local is also `counter`, the pre-state
   answered `prepareRename` accepted and `rename` six edits, two of them the field access; the
   field's declaration is at line 3 and the window is 10..15, so applying those edits renames the
   field's uses and leaves the field, and the renamed text raises `Match for {box . amount }`.
   The **read stays over-inclusive** — §9's count is unchanged — but it no longer claims certainty:
   the same cursor answered six locations with `unresolved FALSE` and no log line before, and now
   sets `unresolved` with its own sentence. **That sentence speaks about names, and the kind test
   in `scopeHasFieldAccess` is what makes it true.** Seed7 will not parse a new operator symbol
   without its `$ syntax expr: .(). <+ .()` rule, and that rule writes a `.` immediately before the
   operator token — so the occurrence the rule itself contains carries `dotPrev`, while the
   declaration's header and the use in `main` do not, and an operator is never a record field.
   Measured before the conjunction was added, on the `<+` of `tests/features_test.sd7`'s
   operator-declaring fixture: three records, only the first (the `$ syntax` line) dot-preceded,
   and the answer was three locations with `unresolved` TRUE and the field sentence — a disclosure
   naming a thing that cannot exist. The suite now pins the corrected answer as "the field
   disclosure speaks of names, so a declared operator discloses nothing". The write path never
   showed the defect, and shows no change from fixing it: an operator cursor leaves `slot` at 0, so
   `renameDecision` refuses on its not-a-name arm before this predicate is consulted — "a
   buffer-declared operator is refused, null, on the not-a-name arm" and "and rename refuses the
   identical cursor with the identical sentence" stay green. Two costs, both recorded rather than
   argued away: a **global** refuses on a field access anywhere in the file, because a global's
   window *is* the document (measured: `total` declared at line 8, read as `b.total` at line 31);
   and the fork's third branch — a token-level index over `const type … end struct` regions, which
   would rename the field and its uses together — is still unbuilt, so a user wanting that gets a
   refusal, not a wrong answer. §9's `pix` in TWO structs is now a fixture, added on
   `m5-review-fixes` and pinned in `tests/features_test.sd7` (§9 names the checks): `dotPrev`
   recognises the access but nothing here separates the two fields, so both spellings stay one
   symbol — measured, the cursor on `x.pix` answers six locations and two of them are the field
   declarations of the two different structs.
3. **Does M5 answer `rename` on a `.s7i` buffer?** Ship it and document the staleness, refuse
   there until R-F10 is paid, or match only `BUFFER_FILE` as "this buffer" (which quietly makes
   every library file a row-4 case).
