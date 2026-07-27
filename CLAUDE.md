# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Radian Language (internally also called "MyLang" in the docs) is an early-stage,
hand-rolled programming language prototype. The repository currently contains
only a lexer and a recursive-descent parser written in pure-stdlib Python — there
is no semantic analyzer, interpreter, or code generator yet. All real content
lives under `Prototip/` ("Prototype" in Turkish); the root `README.md` is a
one-line stub.

Documentation and in-code comments are written in Turkish; class/method/token
names are English. Preserve this convention when editing existing files.

## Repository layout

- `Prototip/lexer.py` — hand-written character-by-character lexer (no regex).
- `Prototip/parser.py` — recursive-descent parser producing an AST of `Node` objects.
- `Prototip/symbols.txt` — source of truth for multi-character operator symbols, loaded at runtime.
- `Prototip/Radian.ebnf` — canonical formal BNF grammar (comments only, no prose).
- `Prototip/Grammer.md` — grammar reference: precedence table, semantics, node-type reference, parser method map, extension guide.
- `Prototip/PARSER_UPDATE_GUIDE.md` — step-by-step recipes for extending the parser (new operators, function calls, `if`/`while`/`return`, member access, precedence layering).

There is no build system, no dependency file (`requirements.txt`/`pyproject.toml`), and no test framework — see "Running / testing" below.

## Running / testing

Both scripts are meant to be run with `Prototip/` as the working directory,
since `parser.py` does a plain `from lexer import ...` (no package structure)
and `lexer()` defaults to loading `symbols.txt` via a relative path.

```bash
cd Prototip

# Lexer: tokenizes a fixed list of sample strings and prints tokens/errors
python3 lexer.py

# Parser: runs built-in statement/funcdef test cases and prints the resulting AST
python3 parser.py
```

There are no `assert`-based unit tests. "Testing" means adding `(label, source)` pairs
to the `cases` / `func_cases` lists in the `if __name__ == "__main__":` block at the
bottom of `parser.py` (or the `samples` list in `lexer.py`) and eyeballing the printed
AST / token stream / `ParseError` output. Follow the existing case-table style when
adding new ones.

## Architecture

### Lexer (`lexer.py`)

A stateful, stack-accumulating lexer (no regex, single pass over the input string):

- `TokenType` covers `LITERAL_NUM`, `LITERAL_STR`, `LITERAL_CHAR`, `LITERAL_IDEN`, `LITERAL_SYMB`, plus `WS`/`NULL`/`LITERAL_UNKN`.
- Multi-character symbols (`->`, `==`, `<<=`, `**=`, etc.) are loaded from `symbols.txt` at call time via `load_multi_char_symbols()`, sorted longest-first for greedy matching. Single-character symbol chars are hardcoded in the `SYMBOL_CHARS` set. **To add a new multi-char operator, just add a line to `symbols.txt`** — no lexer code change needed.
- `lexer(input_str, symbols_file=...)` returns `list[Token]` on success or a `dict` (`{"line", "column", "error"}`) on failure — callers must check `isinstance(result, dict)`, not catch an exception.
- Numeric literals support `_` separators, `.`/exponent, and `0x`/`0b`/`0o` prefixes, tracked via the `has_dot`/`has_exponent`/`has_prefix` flags reset in `flush()`.

### Parser (`parser.py`)

Classic recursive descent, one method per grammar rule, no left recursion (left-associative
chains use `while` loops instead). The expression precedence hierarchy, low to high:

```
_parse_expression → _parse_assign (=, right-assoc, returns lvalue)
                  → _parse_typebind (:, right-assoc, returns lvalue, RHS is TypeExpr not Expression)
                  → _parse_binary (all operators, left-assoc, single flat precedence level — `+` and `*` bind equally, see Grammer.md §8 TODO)
                  → _parse_unary (prefix only)
                  → _parse_term (parens / block / literal)
                  → _parse_literal
```

`TypeExpr` (`_parse_type_expr` / `_parse_tuple_type_expr` / `_parse_type_param`) is a
**separate grammar from Expression**, entered only via `:` in `TypeBind` or inside a
`FuncSignature`. It is right-associative over `->`, which is what gives curried function
types (`(x:i32) -> (y:i32) -> bool`) for free.

`Parser.__init__` strips `WS` tokens before parsing begins. Errors are raised as
`ParseError(msg, token)`, which renders as `"{msg} [{line}:{col}]"`.

`Operator` tokens are merged in `_parse_operator`: the lexer already emits multi-char
symbols as one token via `symbols.txt`, but this method additionally glues adjacent
`LITERAL_SYMB` tokens together (stopping at `TERMINATORS | {"=", ":"}`) as a fallback.

**Known doc/code drift:** `Grammer.md` and `PARSER_UPDATE_GUIDE.md` describe function-call
parsing (`f(x, y)` → `CALL` node via `_parse_call`) as "✅ Tamamlandı" (done), and
`NodeType.CALL` exists in `parser.py`. However, `parser.py` has **no `_parse_call` method**
and `_parse_term` does not dispatch to it — a call-shaped expression like `print(42)`
currently parses as a parenthesized expression, not a `CALL` node. Don't trust the docs'
"done" status over the actual code; verify against `parser.py` directly.

### Extending the grammar

Follow the workflow documented in `PARSER_UPDATE_GUIDE.md` (§3.1) and mirrored in
`Grammer.md` §7: update the grammar text (`Radian.ebnf` and/or `Grammer.md`) → add a
`NodeType` member → write the `_parse_*` method → wire it into the appropriate caller
via lookahead (`self.current()` / `self.peek(n)`) → add test cases to `parser.py`'s
`__main__` block → update `Grammer.md`'s node-type/parser-method tables. `PARSER_UPDATE_GUIDE.md`
has worked examples for each common extension (new binary/unary operator, function calls,
`if`/`while`/`return`, member access `a.b`, splitting `_parse_binary` into precedence layers).

`NodeType` naming convention: `_EXPR` suffix for value-producing nodes, `_OP` for
operators/operations, no suffix for structural nodes (`BLOCK`, `FUNC_DEF`, etc.).
