# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Radian Language is a hand-rolled programming language prototype written in
pure-stdlib Python: lexer → recursive-descent parser → tree-walking interpreter,
plus a CLI/REPL. There is no static type checker, module system, or code
generator yet. All real content lives under `Prototip/` ("Prototype" in Turkish).

Documentation and in-code comments are written in Turkish; class/method/token
names are English. Preserve this convention when editing existing files.

Roadmap, task status, and the log of design decisions live in `PROGRESS.md` at
the repo root — read it before starting work, and update it as you go.

## Repository layout

- `Prototip/lexer.py` — hand-written character-by-character lexer (no regex).
- `Prototip/parser.py` — recursive-descent parser producing an AST of `Node` objects.
- `Prototip/interpreter.py` — tree-walking evaluator: scopes, closures, type checks, builtins.
- `Prototip/checker.py` — optional static checker (`radian.py --check`).
- `Prototip/radian.py` — CLI: run a file, `-c`, `--ast`, `--tokens`, `--check`, REPL.
- `Prototip/symbols.txt` — source of truth for multi-character operator symbols, loaded at runtime.
- `Prototip/Radian.ebnf` — canonical formal BNF grammar (comments only, no prose).
- `Prototip/Grammer.md` — language reference: precedence table, semantics, runtime behaviour, node-type reference, parser method map.
- `Prototip/PARSER_UPDATE_GUIDE.md` — step-by-step recipes for extending the parser.
- `Prototip/examples/*.rad` — runnable example programs.
- `Prototip/tests/` — `unittest` suite; `Prototip/run_tests.py` runs everything.

There is no build system and no dependency file (`requirements.txt`/`pyproject.toml`) — stdlib only.

## Running / testing

Scripts are meant to be run with `Prototip/` as the working directory
(`parser.py` does a plain `from lexer import ...`, no package structure).
`radian.py` and `run_tests.py` also work from anywhere, since they resolve
`symbols.txt` and `sys.path` relative to their own file.

```bash
cd Prototip

python3 run_tests.py              # full suite (~373 tests)
python3 run_tests.py -v           # verbose
python3 run_tests.py test_parser  # one module

python3 radian.py examples/fizzbuzz.rad
python3 radian.py -c 'print(2 ** 10);'
python3 radian.py --ast -c 'x = 1;'

python3 lexer.py                  # demo: tokenizes sample strings
python3 parser.py                 # demo: prints ASTs for a case table
python3 interpreter.py            # demo: runs a small program
```

**Always run `python3 run_tests.py` after a change; it must stay green.**
New behaviour needs a test in `tests/` — the `__main__` case tables in
`lexer.py`/`parser.py` are demos, not tests.

Test modules: `test_lexer`, `test_parser`, `test_interpreter`, `test_examples`
(runs every `examples/*.rad` end to end plus the CLI via subprocess),
`test_robustness` (asserts that only ParseError/RadianError can escape, for a
table of hostile inputs), `test_modules` (import semantics in temp dirs),
`test_checker` (static checker: diagnostics + no false positives), and
`test_docs` (executes every ` ```radian ` block in `Grammer.md`, `README.md`,
and `PARSER_UPDATE_GUIDE.md`). Consequences worth knowing:

- Adding a file to `examples/` **requires** adding an entry to `EXAMPLES` in
  `tests/test_examples.py` — a test asserts the two sets match.
- A ` ```radian ` fenced block in the docs must actually run. Leave schematic
  or intentionally-failing snippets untagged.

`tests/helpers.py` provides `tokenize`, `parse`, `parse_expr`, and `sexp` — the
last renders an AST as a one-line s-expression, which is how parser assertions
are written.

## Architecture

### Lexer (`lexer.py`)

A stateful, stack-accumulating lexer (no regex, single pass over the input string):

- `TokenType` covers `LITERAL_NUM`, `LITERAL_STR`, `LITERAL_CHAR`, `LITERAL_IDEN`, `LITERAL_SYMB`, plus `WS`/`NULL`/`LITERAL_UNKN`.
- Multi-character symbols (`->`, `==`, `<<=`, `**=`, etc.) are loaded from `symbols.txt` at call time via `load_multi_char_symbols()`, sorted longest-first for greedy matching. Single-character symbol chars are hardcoded in the `SYMBOL_CHARS` set. **To add a new multi-char operator, just add a line to `symbols.txt`** — no lexer code change needed.
- `lexer(input_str, symbols_file=...)` returns `list[Token]` on success or a `dict` (`{"line", "column", "error"}`) on failure — callers must check `isinstance(result, dict)`, not catch an exception. (`parse_source()` in `parser.py` wraps this and raises `ParseError` instead.)
- `//` line comments and `/* */` block comments are skipped in the lexer; no token reaches the parser.
- Numeric literals support `_` separators, `.`/exponent, and `0x`/`0b`/`0o` prefixes, tracked via the `has_dot`/`has_exponent`/`has_prefix` flags reset in `flush()`. Incomplete forms (`0x`, `1e`) are lexical errors.
- Keywords are **not** a token type: the lexer emits them as `LITERAL_IDEN` and the parser distinguishes them via its `KEYWORDS` set.

### Parser (`parser.py`)

Classic recursive descent, one method per grammar rule, no left recursion (left-associative
chains use `while` loops instead). The expression hierarchy, low to high:

```
_parse_expression → _parse_assign (=, +=, …, right-assoc, returns lvalue)
                  → _parse_typebind (:, right-assoc, RHS is TypeExpr not Expression)
                  → _parse_binary(level) (table-driven, 11 levels from BINARY_LEVELS)
                  → _parse_unary (prefix - + ! ~)
                  → _parse_term (postfix chain: call / member / index)
                  → _parse_primary (parens / block / array / map / if / while / for / literal)
```

- `BINARY_LEVELS` is the precedence table; a symbol that is in `symbols.txt` but
  not in the table falls to `CUSTOM_LEVEL` (0). `**` is the only right-associative
  level (`RIGHT_ASSOC_LEVELS`).
- An operator is exactly one `LITERAL_SYMB` token — the parser does **not** glue
  adjacent symbols together (that would turn `a + -b` into `a +- b`).
- `_parse_term` builds `CALL`/`MEMBER`/`INDEX` suffixes in a loop, so `a.b[0](x)`
  and curried `f(1)(2)` work. In a `CALL` node, `children[0]` is the callee.
- FuncDef vs. call is decided by `_is_funcdef_ahead()`: `IDENT {` or
  `IDENT ( … ) ->`. Function definitions are therefore legal inside blocks.
- `if`/`while`/`for`/blocks are expressions; `_parse_statement` makes the trailing
  `;` optional for them (`BLOCK_TAILED`).
- `TypeExpr` (`_parse_type_expr` / `_parse_tuple_type_expr` / `_parse_type_param`) is a
  **separate grammar from Expression**, entered only via `:` in `TypeBind` or inside a
  `FuncSignature`. It is right-associative over `->`, which gives curried function
  types (`(x:i32) -> (y:i32) -> bool`) for free; `[T]` is an array type.
- `Parser.__init__` strips `WS` tokens. Errors are `ParseError(msg, token)`,
  rendered as `"{msg} [{line}:{col}]"`.

### Interpreter (`interpreter.py`)

`Interpreter.eval(node, env)` dispatches through the `_DISPATCH` dict keyed by
`NodeType` — adding a node type means adding an entry there.

- Values are plain Python objects (`int`, `float`, `str`, `bool`, `list`, `dict`)
  plus `Function`, `Builtin`, `BoundMethod`, and the `UNIT` singleton.
- `import "path.rad"` is an expression returning a `Module`; paths resolve
  against the importing file's directory (`Interpreter.base_dir`, set by
  `run_file`), modules are cached by realpath, and cycles are an error.
- `struct Ad (alan:Tip, …);` defines a `StructType`, which is callable as a
  positional constructor and usable as a type name; instances are
  `StructInstance`. `check_type` takes an optional `env` so a struct name in
  type position can be resolved.
- Maps use `#[k: v]` literals — `{` was unavailable (blocks) and `{a: T}`
  collides with TypeBind. Keys go through `map_key()`, which rejects `bool`.
- `Environment` is a parent-linked scope holding both values and declared types.
  `=` updates the nearest binding in the chain, or defines in the current scope.
- Type binding validates without coercing (`check_type`), including sized-int
  range checks; `zero_value` backs valueless declarations (`x : i32;`).
- `return`/`break`/`continue` are Python exceptions (`ReturnSignal`, …); loop
  signals cannot cross a function boundary.
- `RadianError.frames` accumulates (function, call line) as the error unwinds
  through `call()`; `traceback_text()` renders it and the CLI prints it.
- Conditions and `&&`/`||`/`!` require real `bool`s — no truthiness.
- Integer `/` truncates toward zero and `%` follows the dividend's sign (C-style).
- Builtins live in `_BUILTIN_SPECS`; methods in `ARRAY_METHODS` / `MAP_METHODS` /
  `STRING_METHODS` / `NUMBER_METHODS`, reached via `_method_table()`.
- Radian call depth is counted by the interpreter (`MAX_CALL_DEPTH`), not left
  to Python's `RecursionError`.
- `Interpreter(out=...)` redirects `print`/`write`, which is how tests capture output.
- After the top-level statements, a zero-arg `main` is called automatically.

### Checker (`checker.py`)

A separate pass over the AST, run only via `--check` — it never runs as part
of `radian.py file.rad`.

- The contract is **no false positives**: `_infer` returns `UNKNOWN` whenever
  it cannot be certain, and `assignable()` treats `UNKNOWN` as compatible, so
  a diagnostic always indicates a real error. `tests/test_checker.py` enforces
  this against every `examples/*.rad` plus a table of correct programs.
- Integer widths collapse to one `int` type; range checking stays at runtime.
- Function and struct names are hoisted per block before bodies are checked,
  matching the interpreter's late name resolution.
- Module members are deliberately untracked (`import` yields `MODULE`, member
  access on it is `UNKNOWN`).
- Builtin names/arities come from `interpreter.BUILTIN_NAMES` /
  `BUILTIN_ARITIES`; method names from the same method tables the interpreter
  uses, so the two cannot drift.

### Extending the grammar

Workflow (also in `Grammer.md` §8 and `PARSER_UPDATE_GUIDE.md` §3.1): update the
grammar text (`Radian.ebnf` and `Grammer.md`) → add a `NodeType` member → write the
`_parse_*` method → wire it into the appropriate caller via lookahead
(`self.current()` / `self.peek(n)`) → add an `_eval_*` and a `_DISPATCH` entry →
add tests under `tests/` → update `Grammer.md`'s node-type/parser-method tables.

`NodeType` naming convention: `_EXPR` suffix for value-producing nodes, `_OP` for
operators/operations, no suffix for structural nodes (`BLOCK`, `FUNC_DEF`, etc.).

New keywords must be added to `KEYWORDS` in `parser.py`, otherwise they stay
usable as ordinary identifiers.
