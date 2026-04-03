from enum import Enum, auto
from lexer import Token, TokenType, lexer


# ---------------------------------------------------------------------------
# NodeType
# ---------------------------------------------------------------------------

class NodeType(Enum):
    PROGRAM    = auto()  # Kök düğüm — { TopLevel }
    STATEMENT  = auto()  # Expression ";"
    FUNC_DEF   = auto()  # IDENTIFIER [ FuncSignature ] Block
    BLOCK      = auto()  # "{" { Statement } "}"  — son stmt değeri döner
    FUNC_TYPE  = auto()  # "(" TypeParamList ")" "->" TypeExpr
    TUPLE_TYPE = auto()  # "(" TypeParamList ")"  — ok tipi öncesi
    TYPE_PARAM = auto()  # [IDENTIFIER ":"] TypeExpr
    ASSIGN     = auto()  # lhs "=" rhs   → lvalue döndürür
    TYPEBIND   = auto()  # lhs ":" TypeExpr → lvalue döndürür
    BINARY_OP  = auto()  # Unary Operator Unary  — sol çağrışımlı
    UNARY_OP   = auto()  # UnaryOp Term
    OPERATOR   = auto()  # Operatör düğümü (value = token)
    LITERAL    = auto()  # Sayı / string / char / PrimitiveType sembolü
    IDENTIFIER = auto()  # Kullanıcı tanımlı isim
    
    #yeni 0.2 yaması
    CALL       = auto() # fonksiyon çağırma


# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

PRIMITIVE_TYPES = {
    "i8",  "i16", "i32", "i64",
    "u8",  "u16", "u32", "u64",
    "f32", "f64", "bool", "char",
}

# Bu değerler operatör veya unary başlatamaz
TERMINATORS = {";", "(", ")", "{", "}", ","}


# ---------------------------------------------------------------------------
# AST Node
# ---------------------------------------------------------------------------

class Node:
    def __init__(self, type: NodeType, value: Token | None = None):
        self.type:     NodeType      = type
        self.value:    Token | None  = value
        self.children: list["Node"] = []          # instance değişkeni — paylaşım yok

    def add(self, child: "Node") -> "Node":
        self.children.append(child)
        return self

    def __repr__(self, indent: int = 0) -> str:
        pad = "  " * indent
        val = f" {self.value.value!r}" if self.value else ""
        s   = f"{pad}[{self.type.name}]{val}\n"
        for child in self.children:
            s += child.__repr__(indent + 1)
        return s


# ---------------------------------------------------------------------------
# ParseError
# ---------------------------------------------------------------------------

class ParseError(Exception):
    def __init__(self, msg: str, token: Token | None = None):
        loc = f" [{token.line}:{token.column}]" if token else ""
        super().__init__(f"{msg}{loc}")
        self.token = token


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class Parser:
    """
    Recursive descent parser.

    Her gramer kuralı bir _parse_* metoduna karşılık gelir.
    Yeni kural eklemek için:
      1. NodeType'a değer ekle.
      2. _parse_* metodunu yaz.
      3. Uygun üst kuraldan çağır.
    """

    def __init__(self, tokens: list[Token]):
        self.tokens: list[Token] = [t for t in tokens
                                     if t.type != TokenType.WS]
        self.pos:  int  = 0
        self.root: Node = Node(NodeType.PROGRAM)

    # ------------------------------------------------------------------
    # Temel yardımcılar
    # ------------------------------------------------------------------

    def peek(self, offset: int = 0) -> Token | None:
        i = self.pos + offset
        return self.tokens[i] if i < len(self.tokens) else None

    def current(self) -> Token | None:
        return self.peek(0)

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, value: str) -> Token:
        tok = self.current()
        got = tok.value if tok else "EOF"
        if got != value:
            raise ParseError(f"'{value}' beklendi, '{got}' bulundu", tok)
        return self.advance()

    def match(self, *values: str) -> bool:
        tok = self.current()
        return tok is not None and tok.value in values

    def match_type(self, *types: TokenType) -> bool:
        tok = self.current()
        return tok is not None and tok.type in types

    # ------------------------------------------------------------------
    # Program = { TopLevel }
    # ------------------------------------------------------------------

    def parse(self) -> Node:
        while self.current() is not None:
            self.root.add(self._parse_toplevel())
        return self.root

    # ------------------------------------------------------------------
    # TopLevel = FuncDef | Statement
    #
    # Ayrım kuralı:
    #   IDENT + "{"  → gövdeli FuncDef (imzasız)
    #   IDENT + "("  → gövdeli FuncDef (satır içi imzalı)
    #   diğer        → Statement
    # ------------------------------------------------------------------

    def _parse_toplevel(self) -> Node:
        tok = self.current()
        nxt = self.peek(1)

        if (tok is not None
                and tok.type == TokenType.LITERAL_IDEN
                and nxt is not None
                and nxt.value in ("{", "(")):
            return self._parse_funcdef()

        return self._parse_statement()

    # ------------------------------------------------------------------
    # FuncDef = IDENTIFIER [ FuncSignature ] Block
    #
    # Geçerli formlar:
    #   topla { ... }
    #   topla (x:i32, y:i32) -> i32 { ... }
    # ------------------------------------------------------------------

    def _parse_funcdef(self) -> Node:
        name_tok = self.advance()                        # IDENTIFIER
        node     = Node(NodeType.FUNC_DEF, name_tok)

        # Satır içi imza varsa parse et
        if self.match("("):
            node.add(self._parse_funcsig())

        node.add(self._parse_block())
        return node

    # ------------------------------------------------------------------
    # FuncSignature = "(" [ TypeParamList ] ")" "->" TypeExpr
    #
    # Örnek: (x:i32, y:i32) -> i32
    # ------------------------------------------------------------------

    def _parse_funcsig(self) -> Node:
        node = Node(NodeType.FUNC_TYPE)
        self.expect("(")

        if not self.match(")"):
            node.add(self._parse_type_param())
            while self.match(","):
                self.advance()
                node.add(self._parse_type_param())

        self.expect(")")
        arrow_tok  = self.expect("->")
        node.value = arrow_tok                           # "->" token'ı value'da

        ret_wrapper = Node(NodeType.TYPE_PARAM)          # dönüş tipi — isimsiz
        ret_wrapper.add(self._parse_type_expr())
        node.add(ret_wrapper)
        return node

    # ------------------------------------------------------------------
    # Block = "{" { Statement } "}"
    #
    # Son statement'ın değeri blokun değeridir (implicit return).
    # Tüm statement'lar ";" ile biter.
    # Boş blok → unit / void (semantik katmanda çözülecek).
    # ------------------------------------------------------------------

    def _parse_block(self) -> Node:
        self.expect("{")
        node = Node(NodeType.BLOCK)
        while not self.match("}"):
            if self.current() is None:
                raise ParseError("Kapatılmamış blok; '}' beklendi")
            node.add(self._parse_statement())
        self.expect("}")
        return node

    # ------------------------------------------------------------------
    # Statement = Expression ";"
    # ------------------------------------------------------------------

    def _parse_statement(self) -> Node:
        node = Node(NodeType.STATEMENT)
        node.add(self._parse_expression())
        self.expect(";")
        return node

    # ------------------------------------------------------------------
    # Expression = Assign
    # ------------------------------------------------------------------

    def _parse_expression(self) -> Node:
        return self._parse_assign()

    # ------------------------------------------------------------------
    # Assign = TypeBind [ "=" Assign ]
    #
    # Sağ-çağrışımlı — lvalue döndürür.
    #   a = b = c   →   ASSIGN(a, ASSIGN(b, c))
    #   (a = b) + 2 geçerli; parantez içinde tam expression işlenir.
    # ------------------------------------------------------------------

    def _parse_assign(self) -> Node:
        left = self._parse_typebind()
        if self.match("="):
            op_tok = self.advance()
            right  = self._parse_assign()                # sağ-çağrışımlı
            node   = Node(NodeType.ASSIGN, op_tok)
            node.add(left).add(right)
            return node
        return left

    # ------------------------------------------------------------------
    # TypeBind = Binary [ ":" TypeExpr ]
    #
    # Sağ-çağrışımlı — lvalue döndürür.
    # ":" sağında expression değil, tip dili geçerlidir.
    #
    #   b : i32               → TYPEBIND(b, i32)
    #   a : i32 = b           → ASSIGN(TYPEBIND(a,i32), b)
    #   a = b : i32           → ASSIGN(a, TYPEBIND(b,i32))
    #   a : i32 = b : f64     → ASSIGN(TYPEBIND(a,i32), TYPEBIND(b,f64))
    # ------------------------------------------------------------------

    def _parse_typebind(self) -> Node:
        left = self._parse_binary()
        if self.match(":"):
            op_tok = self.advance()
            right  = self._parse_type_expr()             # tip dili katmanı
            node   = Node(NodeType.TYPEBIND, op_tok)
            node.add(left).add(right)
            return node
        return left

    # ------------------------------------------------------------------
    # Binary = Unary { Operator Unary }
    #
    # Sol-çağrışımlı.
    # "=" ve ":" bu seviyeye düşmez; üst katmanlarda yakalanır.
    # ------------------------------------------------------------------

    def _parse_binary(self) -> Node:
        left = self._parse_unary()
        while self._is_binary_operator():
            op    = self._parse_operator()
            right = self._parse_unary()
            node  = Node(NodeType.BINARY_OP)
            node.add(left).add(op).add(right)
            left = node
        return left

    # ------------------------------------------------------------------
    # Unary = [ UnaryOp ] Term
    #
    # UnaryOp: LITERAL_SYMB token'ı ve hemen ardında Term başlıyorsa.
    # ------------------------------------------------------------------

    def _parse_unary(self) -> Node:
        if self._is_unary_operator():
            op_tok  = self.advance()
            op_node = Node(NodeType.OPERATOR, op_tok)
            term    = self._parse_term()
            node    = Node(NodeType.UNARY_OP)
            node.add(op_node).add(term)
            return node
        return self._parse_term()

    # ------------------------------------------------------------------
    # Term = "(" Expression ")"
    #      | Block
    #      | Literal
    #
    # Parantez içinde tam Expression işlenir →
    #   (a = b) + 2   geçerli (lvalue kullanımı)
    #   { a = 1; a; } blok değer olarak kullanılabilir
    # ------------------------------------------------------------------

    def _parse_term(self) -> Node:
        if self.match("("):
            self.advance()
            expr = self._parse_expression()
            self.expect(")")
            return expr

        if self.match("{"):
            return self._parse_block()

        return self._parse_literal()

    # ------------------------------------------------------------------
    # Literal = T_STRING | T_CHAR | T_NUMBER | T_IDENTIFIER
    #         | T_SYMBOL | PrimitiveType
    # ------------------------------------------------------------------

    def _parse_literal(self) -> Node:
        tok = self.current()
        if tok is None:
            raise ParseError("Literal beklendi, EOF bulundu")

        if tok.type in (TokenType.LITERAL_STR,
                        TokenType.LITERAL_CHAR,
                        TokenType.LITERAL_NUM):
            return Node(NodeType.LITERAL, self.advance())

        if tok.type == TokenType.LITERAL_IDEN:
            self.advance()
            ntype = (NodeType.LITERAL
                     if tok.value in PRIMITIVE_TYPES
                     else NodeType.IDENTIFIER)
            return Node(ntype, tok)

        if tok.type == TokenType.LITERAL_SYMB:
            return Node(NodeType.LITERAL, self.advance())

        raise ParseError(f"Beklenmeyen token: '{tok.value}'", tok)

    # ------------------------------------------------------------------
    # TypeExpr = TupleTypeExpr [ "->" TypeExpr ]
    #
    # Sağ-çağrışımlı:
    #   (x:i32) -> (y:i32) -> bool  →  FUNC_TYPE((x:i32), FUNC_TYPE((y:i32), bool))
    # ------------------------------------------------------------------

    def _parse_type_expr(self) -> Node:
        left = self._parse_tuple_type_expr()

        if self.match("->"):
            arrow_tok = self.advance()
            ret       = self._parse_type_expr()          # sağ-çağrışımlı
            node      = Node(NodeType.FUNC_TYPE, arrow_tok)
            for child in left.children:                  # parametre çocuklarını taşı
                node.add(child)
            ret_wrapper = Node(NodeType.TYPE_PARAM)      # dönüş tipi
            ret_wrapper.add(ret)
            node.add(ret_wrapper)
            return node

        return left

    # ------------------------------------------------------------------
    # TupleTypeExpr = "(" [ TypeParamList ] ")"
    #               | IDENTIFIER
    # ------------------------------------------------------------------

    def _parse_tuple_type_expr(self) -> Node:
        if self.match("("):
            self.advance()
            node = Node(NodeType.TUPLE_TYPE)

            if not self.match(")"):
                node.add(self._parse_type_param())
                while self.match(","):
                    self.advance()
                    node.add(self._parse_type_param())

            self.expect(")")
            return node

        tok = self.current()
        if tok and tok.type == TokenType.LITERAL_IDEN:
            self.advance()
            return Node(NodeType.LITERAL, tok)

        raise ParseError("Tip ifadesi beklendi", tok)

    # ------------------------------------------------------------------
    # TypeParam = IDENTIFIER ":" TypeExpr    (isimli)
    #           | TypeExpr                   (isimsiz)
    # ------------------------------------------------------------------

    def _parse_type_param(self) -> Node:
        tok = self.current()
        nxt = self.peek(1)
        node = Node(NodeType.TYPE_PARAM)

        # İsimli parametre: IDENT ":" TypeExpr
        if (tok is not None
                and tok.type == TokenType.LITERAL_IDEN
                and nxt is not None
                and nxt.value == ":"):
            node.value = self.advance()                  # parametre ismi
            self.advance()                               # ":" tüket
            node.add(self._parse_type_expr())
        else:
            node.add(self._parse_type_expr())

        return node

    # ------------------------------------------------------------------
    # Operator = ( T_SYMBOL | T_IDENTIFIER ) { T_SYMBOL }
    #
    # Lexer çok karakterli sembolleri tek token olarak üretir (symbols.txt).
    # Bu metot bitişik sembol token'larını birleştirir; lexer yakaladıysa
    # while döngüsü hiç çalışmaz.
    # ------------------------------------------------------------------

    def _parse_operator(self) -> Node:
        tok = self.current()
        if tok is None or not self._is_operator_start(tok):
            raise ParseError("Operatör beklendi", tok)

        value = tok.value
        start = tok
        self.advance()

        # Bitişik sembol token'larını birleştir
        while True:
            nxt = self.current()
            if (nxt is None
                    or nxt.value in TERMINATORS | {"=", ":"}
                    or nxt.type  != TokenType.LITERAL_SYMB):
                break
            value += nxt.value
            self.advance()

        merged = Token(start.type, value, start.line, start.column)
        return Node(NodeType.OPERATOR, merged)

    # ------------------------------------------------------------------
    # Yardımcı kontroller
    # ------------------------------------------------------------------

    def _is_operator_start(self, tok: Token) -> bool:
        """Token bir operatör başlatabilir mi?"""
        return (tok.type in (TokenType.LITERAL_IDEN, TokenType.LITERAL_SYMB)
                and tok.value not in TERMINATORS | {"=", ":"})

    def _is_binary_operator(self) -> bool:
        """
        İkili operatör adayı: terminator olmayan SYMB veya IDEN token'ı
        ve sağında en az bir token daha var (operatörün sağında Unary başlamalı).
        """
        tok = self.current()
        nxt = self.peek(1)
        return (tok is not None
                and nxt is not None
                and self._is_operator_start(tok))

    def _is_unary_operator(self) -> bool:
        """
        Tekli operatör: SYMB token'ı ve hemen ardında Term başlatıcısı varsa.
        Genişletmek için IDEN kontrolü de eklenebilir.
        """
        tok = self.current()
        nxt = self.peek(1)
        if tok is None or nxt is None:
            return False
        if tok.type != TokenType.LITERAL_SYMB:
            return False
        if tok.value in TERMINATORS | {"=", ":"}:
            return False
        # Ardında literal veya "(" veya "{" varsa unary operatördür
        return (nxt.type in (TokenType.LITERAL_NUM,
                              TokenType.LITERAL_STR,
                              TokenType.LITERAL_CHAR,
                              TokenType.LITERAL_IDEN)
                or nxt.value in ("(", "{"))


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cases = [
        # ( etiket, kaynak kod )

        # --- Değişken ---
        ("Tip tanımlama",         "x : i32;"),
        ("Atama",                 "x = 42;"),
        ("Tip + atama",           "x : i32 = 42;"),
        ("Atama + tip dönüşüm",   "a = b : i32;"),
        ("Çift tip zinciri",      "a : i32 = b : f64;"),
        ("Zincirleme atama",      "a = b = c;"),

        # --- İfade ---
        ("Aritmetik",             "z = x + y * 2;"),
        ("Unary eksi",            "n = -5;"),
        ("Unary not",             "f = !flag;"),
        ("Gruplama",              "r = (x + y) * 2;"),
        ("lvalue expression",     "r = (a = b) + 1;"),
        ("İç içe unary",          "r = -(x + 1);"),

        # --- Blok ---
        ("Blok değer",            "r = { a = 1; a + 2; };"),

        # --- Tip imzası ---
        ("Fonk imzası (stmt)",    "topla : (x:i32, y:i32) -> i32;"),
        ("Isimsiz parametre",     "g : (i32, i32) -> i32;"),
        ("Curried fonk tipi",     "f : (x:i32) -> (y:i32) -> bool;"),
        ("HOF tipi",              "apply : (f:(x:i32) -> i32, v:i32) -> i32;"),
    ]

    func_cases = [
        # ( etiket, kaynak kod )
        ("Gövde (imzasız)",
         "topla { result = x + y; result; }"),

        ("Satır içi imza + gövde",
         "topla (x:i32, y:i32) -> i32 { result = x + y; result; }"),

        ("main",
         'main () -> i32 { builtin_print("Hello, World!\\n"); 0; }'),
    ]

    SEP = "─" * 58

    print("╔══ STATEMENT TESTLERİ ══════════════════════════════════╗\n")
    for label, src in cases:
        print(SEP)
        print(f"  {label}")
        print(f"  {src!r}")
        print(SEP)
        toks = lexer(src)
        if isinstance(toks, dict):
            print(f"  Lexer HATA: {toks}\n")
            continue
        try:
            print(Parser(toks).parse())
        except ParseError as e:
            print(f"  Parser HATA: {e}\n")

    print("╔══ FUNCDEF TESTLERİ ════════════════════════════════════╗\n")
    for label, src in func_cases:
        print(SEP)
        print(f"  {label}")
        print(f"  {src!r}")
        print(SEP)
        toks = lexer(src)
        if isinstance(toks, dict):
            print(f"  Lexer HATA: {toks}\n")
            continue
        try:
            print(Parser(toks).parse())
        except ParseError as e:
            print(f"  Parser HATA: {e}\n")
            