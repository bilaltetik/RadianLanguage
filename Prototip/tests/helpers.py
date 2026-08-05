"""Test yardımcıları — tüm test modülleri buradan içe aktarır."""

import os
import sys

# Prototip/ dizinini import yoluna ekle; parser.py düz 'from lexer import ...'
# kullandığı için testler nereden çalıştırılırsa çalıştırılsın gerekli.
PROTOTIP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROTOTIP_DIR not in sys.path:
    sys.path.insert(0, PROTOTIP_DIR)

SYMBOLS_FILE = os.path.join(PROTOTIP_DIR, "symbols.txt")
EXAMPLES_DIR = os.path.join(PROTOTIP_DIR, "examples")

from lexer import Token, TokenType, lexer          # noqa: E402
from parser import Node, NodeType, ParseError, Parser  # noqa: E402


def tokenize(src: str) -> list:
    """Kaynağı lexle; lexer hata dönerse AssertionError fırlat."""
    result = lexer(src, symbols_file=SYMBOLS_FILE)
    assert not isinstance(result, dict), f"Beklenmeyen lexer hatası: {result}"
    return result


def lex_error(src: str) -> dict:
    """Kaynağı lexle; hata *beklenir*, token listesi dönerse AssertionError."""
    result = lexer(src, symbols_file=SYMBOLS_FILE)
    assert isinstance(result, dict), f"Lexer hatası bekleniyordu, {result} döndü"
    return result


def token_pairs(src: str) -> list[tuple]:
    """(TokenType, value) çiftleri — token karşılaştırmalarını kısaltır."""
    return [(t.type, t.value) for t in tokenize(src)]


def parse(src: str) -> Node:
    """Kaynağı parse et, PROGRAM kökünü döndür."""
    return Parser(tokenize(src)).parse()


def parse_expr(src: str) -> Node:
    """Tek statement'lık kaynağı parse et, ifade düğümünü döndür.

    'x + 1;' → BINARY_OP düğümü (PROGRAM ve STATEMENT sarmalayıcıları atlanır).
    """
    program = parse(src)
    assert len(program.children) == 1, "Tek bir top-level düğüm bekleniyordu"
    stmt = program.children[0]
    assert stmt.type == NodeType.STATEMENT, f"STATEMENT bekleniyordu, {stmt.type} bulundu"
    return stmt.children[0]


def sexp(node: Node) -> str:
    """AST'yi tek satırlık s-expression'a çevirir — kolay assert için.

    BINARY_OP(a + b) → '(BINARY_OP IDENTIFIER:a OPERATOR:+ IDENTIFIER:b)'
    """
    head = node.type.name
    if node.value is not None:
        head += f":{node.value.value}"
    if not node.children:
        return head
    inner = " ".join(sexp(c) for c in node.children)
    return f"({head} {inner})"
