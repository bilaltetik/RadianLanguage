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
    ASSIGN     = auto()  # lhs AssignOp rhs   → lvalue döndürür
    TYPEBIND   = auto()  # lhs ":" TypeExpr → lvalue döndürür
    BINARY_OP  = auto()  # Unary Operator Unary  — öncelik katmanlı
    UNARY_OP   = auto()  # UnaryOp Term
    OPERATOR   = auto()  # Operatör düğümü (value = token)
    LITERAL    = auto()  # Sayı / string / char / bool / PrimitiveType sembolü
    IDENTIFIER = auto()  # Kullanıcı tanımlı isim

    # --- 0.2 yaması: çağrı ---
    CALL       = auto()  # children[0] = çağrılan, children[1:] = argümanlar

    # --- 0.4 yaması: artırma/azaltma ---
    PRE_OP     = auto()  # value = "++"/"--", children = [hedef]  →  ++x
    POST_OP    = auto()  # value = "++"/"--", children = [hedef]  →  x++

    # --- 0.3 yaması: postfix erişim, dizi, akış denetimi ---
    MEMBER     = auto()  # value = üye adı, children = [nesne]        →  a.b
    INDEX      = auto()  # children = [nesne, indeks]                 →  a[i]
    ARRAY      = auto()  # children = elemanlar                       →  [1, 2]
    MAP        = auto()  # children = [anahtar, değer, …] ikişerli    →  #["a": 1]

    # --- 0.5 yaması: kayıt tipleri ve modüller ---
    STRUCT_DEF = auto()  # value = yapı adı, children = [TYPE_PARAM …]
    IMPORT     = auto()  # value = "import", children = [yol ifadesi]
    IF         = auto()  # children = [koşul, then-Block, else?]
    WHILE      = auto()  # children = [koşul, gövde-Block]
    FOR        = auto()  # value = döngü değişkeni, children = [dizi, gövde]
    RETURN     = auto()  # children = [ifade?]
    BREAK      = auto()  # —
    CONTINUE   = auto()  # —


# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

PRIMITIVE_TYPES = {
    "i8",  "i16", "i32", "i64",
    "u8",  "u16", "u32", "u64",
    "f32", "f64", "bool", "char",
}

# Bu değerler operatör veya unary başlatamaz
TERMINATORS = {";", "(", ")", "{", "}", "[", "]", ","}

# Anahtar sözcükler — lexer bunları LITERAL_IDEN üretir, ayrım parser'da yapılır.
KEYWORDS = {
    "if", "else", "while", "for", "in",
    "return", "break", "continue",
    "true", "false", "struct", "import",
}

# Değer üreten anahtar sözcükler (LITERAL düğümü olurlar)
KEYWORD_LITERALS = {"true", "false"}

# Atama operatörleri — Assign katmanında yakalanır, Binary'ye düşmez.
# "op=" biçimindekiler yorumlayıcıda `a = a op b` olarak çözülür.
ASSIGN_OPS = {"=", "+=", "-=", "*=", "/=", "%=", "**=", "<<=", ">>=", "&=", "|=", "^="}

# Önek (unary) operatörleri
UNARY_OPS = {"-", "+", "!", "~"}

# Artırma / azaltma — hem önek hem sonek; binary operatör değildirler.
INCDEC_OPS = {"++", "--"}

# ++ / -- yalnızca bu düğümlere uygulanabilir (lvalue)
LVALUE_TYPES = {NodeType.IDENTIFIER, NodeType.INDEX}

# Binary operatör öncelik katmanları — index 0 en düşük öncelik.
# symbols.txt'e eklenen ama burada yer almayan semboller "özel operatör"
# sayılır ve en düşük binary seviyeye (CUSTOM_LEVEL) düşer.
BINARY_LEVELS: list[set[str]] = [
    {"||"},                          # 0  mantıksal VEYA
    {"&&"},                          # 1  mantıksal VE
    {"|"},                           # 2  bit VEYA
    {"^"},                           # 3  bit XOR
    {"&"},                           # 4  bit VE
    {"==", "!="},                    # 5  eşitlik
    {"<", ">", "<=", ">="},          # 6  karşılaştırma
    {"<<", ">>"},                    # 7  kaydırma
    {"+", "-"},                      # 8  toplama / çıkarma
    {"*", "/", "%"},                 # 9  çarpma / bölme / mod
    {"**"},                          # 10 üs alma  (sağ çağrışımlı)
]

CUSTOM_LEVEL = 0                                   # tabloda olmayan semboller
RIGHT_ASSOC_LEVELS = {len(BINARY_LEVELS) - 1}      # yalnızca "**"

# Gövdesi blokla biten ifadeler — statement sonunda ";" opsiyoneldir.
BLOCK_TAILED = {NodeType.IF, NodeType.WHILE, NodeType.FOR, NodeType.BLOCK}


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

    def match_keyword(self, *words: str) -> bool:
        """Geçerli token bu anahtar sözcüklerden biri mi?"""
        tok = self.current()
        return (tok is not None
                and tok.type == TokenType.LITERAL_IDEN
                and tok.value in words)

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
    # Ayrım _parse_statement içinde (_is_funcdef_ahead) yapılır; böylece
    # fonksiyon tanımı blok içinde de (iç fonksiyon) geçerlidir.
    # ------------------------------------------------------------------

    def _parse_toplevel(self) -> Node:
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

    def _is_funcdef_ahead(self) -> bool:
        """
        Fonksiyon tanımı mı yoksa ifade mi?

          topla { ... }                → FuncDef  (IDENT + "{")
          topla (x:i32) -> i32 { ... } → FuncDef  (IDENT + "(" … ")" + "->")
          topla(x, y);                 → çağrı ifadesi ("->" yok)
        """
        tok = self.current()
        nxt = self.peek(1)

        if (tok is None or nxt is None
                or tok.type != TokenType.LITERAL_IDEN
                or tok.value in KEYWORDS):
            return False

        if nxt.value == "{":
            return True

        if nxt.value == "(":
            close = self._matching_paren(self.pos + 1)
            after = self.peek(close - self.pos + 1) if close is not None else None
            return after is not None and after.value == "->"

        return False

    def _matching_paren(self, open_index: int) -> int | None:
        """open_index'teki '(' ile eşleşen ')' token'ının indeksini döndürür."""
        depth = 0
        i     = open_index
        while i < len(self.tokens):
            value = self.tokens[i].value
            if value == "(":
                depth += 1
            elif value == ")":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return None

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
    # Boş blok → unit / void.
    # ------------------------------------------------------------------

    def _parse_block(self) -> Node:
        open_tok = self.expect("{")
        node = Node(NodeType.BLOCK)
        while not self.match("}"):
            if self.current() is None:
                raise ParseError("Kapatılmamış blok; '}' beklendi", open_tok)
            node.add(self._parse_statement())
        self.expect("}")
        return node

    # ------------------------------------------------------------------
    # Statement = FuncDef
    #           | "return" [ Expression ] ";"
    #           | "break" ";"
    #           | "continue" ";"
    #           | Expression [ ";" ]
    #
    # ";" yalnızca gövdesi blokla biten ifadelerde (if/while/for/blok)
    # opsiyoneldir; diğer tüm ifadelerde zorunludur.
    # ------------------------------------------------------------------

    def _parse_statement(self) -> Node:
        if self._is_funcdef_ahead():
            return self._parse_funcdef()

        if self.match_keyword("struct"):
            return self._wrap_statement(self._parse_struct())

        if self.match_keyword("return"):
            return self._wrap_statement(self._parse_return())

        if self.match_keyword("break", "continue"):
            tok  = self.advance()
            ntype = NodeType.BREAK if tok.value == "break" else NodeType.CONTINUE
            node = Node(ntype, tok)
            self.expect(";")
            return self._wrap_statement(node, terminated=True)

        expr = self._parse_expression()
        if expr.type in BLOCK_TAILED:
            if self.match(";"):                          # ";" serbest ama zorunlu değil
                self.advance()
            return self._wrap_statement(expr, terminated=True)

        self.expect(";")
        return self._wrap_statement(expr, terminated=True)

    def _wrap_statement(self, expr: Node, terminated: bool = False) -> Node:
        if not terminated:
            self.expect(";")
        node = Node(NodeType.STATEMENT)
        node.add(expr)
        return node

    # ------------------------------------------------------------------
    # StructDef = "struct" IDENTIFIER "(" [ TypeParamList ] ")" ";"
    #
    # Alan listesi fonksiyon imzasıyla aynı dilbilgisini kullanır; alan adı
    # zorunludur. Yapı adı hem tip hem de kurucu fonksiyondur:
    #
    #   struct Nokta (x:i32, y:i32);
    #   p = Nokta(3, 4);
    #   p.x;
    # ------------------------------------------------------------------

    def _parse_struct(self) -> Node:
        self.advance()                                   # "struct"

        name_tok = self.current()
        if (name_tok is None
                or name_tok.type != TokenType.LITERAL_IDEN
                or name_tok.value in KEYWORDS):
            raise ParseError("'struct' sonrası yapı adı beklendi", name_tok)
        self.advance()

        node = Node(NodeType.STRUCT_DEF, name_tok)
        self.expect("(")
        if not self.match(")"):
            node.add(self._parse_type_param())
            while self.match(","):
                self.advance()
                node.add(self._parse_type_param())
        self.expect(")")
        return node

    # ------------------------------------------------------------------
    # ReturnStmt = "return" [ Expression ] ";"
    # ------------------------------------------------------------------

    def _parse_return(self) -> Node:
        tok  = self.advance()                            # "return"
        node = Node(NodeType.RETURN, tok)
        if not self.match(";"):
            node.add(self._parse_expression())
        return node

    # ------------------------------------------------------------------
    # Expression = Assign
    # ------------------------------------------------------------------

    def _parse_expression(self) -> Node:
        return self._parse_assign()

    # ------------------------------------------------------------------
    # Assign = TypeBind [ AssignOp Assign ]
    #
    # Sağ-çağrışımlı — lvalue döndürür.
    #   a = b = c     →   ASSIGN(a, ASSIGN(b, c))
    #   a += 1        →   ASSIGN:'+=' (a, 1)  — yorumlayıcı a = a + 1 yapar
    # ------------------------------------------------------------------

    def _parse_assign(self) -> Node:
        left = self._parse_typebind()
        tok  = self.current()
        if tok is not None and tok.value in ASSIGN_OPS:
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
    # Binary — BINARY_LEVELS tablosuna göre katmanlı
    #
    #   Binary(n) = Binary(n+1) { Op(n) Binary(n+1) }      sol-çağrışımlı
    #   Binary(son) = Unary
    #
    # "**" sağ-çağrışımlıdır (RIGHT_ASSOC_LEVELS).
    # "=" ve ":" bu katmanlara düşmez; üst kurallarda yakalanır.
    # ------------------------------------------------------------------

    def _parse_binary(self, level: int = 0) -> Node:
        if level >= len(BINARY_LEVELS):
            return self._parse_unary()

        left = self._parse_binary(level + 1)

        while self._operator_level() == level:
            op = self._parse_operator()
            if level in RIGHT_ASSOC_LEVELS:
                right = self._parse_binary(level)        # sağ-çağrışım
            else:
                right = self._parse_binary(level + 1)
            node = Node(NodeType.BINARY_OP)
            node.add(left).add(op).add(right)
            left = node
            if level in RIGHT_ASSOC_LEVELS:
                break
        return left

    # ------------------------------------------------------------------
    # Unary = ( "++" | "--" ) Unary          — önek artırma/azaltma
    #       | [ UnaryOp ] Unary
    #       | Term
    #
    # UnaryOp ∈ UNARY_OPS ve ardından bir Term başlamalı.
    # ------------------------------------------------------------------

    def _parse_unary(self) -> Node:
        if self.match(*INCDEC_OPS):
            op_tok = self.advance()
            target = self._parse_unary()
            self._require_lvalue(target, op_tok)
            node = Node(NodeType.PRE_OP, op_tok)
            node.add(target)
            return node

        if self._is_unary_operator():
            op_tok  = self.advance()
            op_node = Node(NodeType.OPERATOR, op_tok)
            operand = self._parse_unary()                # -(-x) zincirlenebilir
            node    = Node(NodeType.UNARY_OP)
            node.add(op_node).add(operand)
            return node
        return self._parse_term()

    # ------------------------------------------------------------------
    # Term = Primary { CallSuffix | MemberSuffix | IndexSuffix }
    #
    #   f(x)      → CALL(f, x)
    #   a.b       → MEMBER:b(a)
    #   a[i]      → INDEX(a, i)
    #   f(x)(y)   → CALL(CALL(f, x), y)      currying doğal çalışır
    #   a.b[0](c) → zincir soldan sağa
    # ------------------------------------------------------------------

    def _parse_term(self) -> Node:
        node = self._parse_primary()

        while True:
            if self.match("("):
                node = self._parse_call(node)
            elif self.match("."):
                node = self._parse_member(node)
            elif self.match("["):
                node = self._parse_index(node)
            elif self.match(*INCDEC_OPS):
                op_tok = self.advance()
                self._require_lvalue(node, op_tok)
                post = Node(NodeType.POST_OP, op_tok)
                post.add(node)
                return post                          # zincir burada biter
            else:
                break
        return node

    def _require_lvalue(self, node: Node, op_tok: Token) -> None:
        """'++' / '--' hedefi değişken ya da dizi elemanı olmalıdır."""
        if node.type not in LVALUE_TYPES:
            raise ParseError(
                f"'{op_tok.value}' yalnızca değişken ya da dizi elemanına "
                f"uygulanabilir", op_tok)

    # ------------------------------------------------------------------
    # Primary = "(" Expression ")"
    #         | Block | IfExpr | WhileExpr | ForExpr | ArrayLiteral
    #         | Literal
    # ------------------------------------------------------------------

    def _parse_primary(self) -> Node:
        if self.match("("):
            self.advance()
            expr = self._parse_expression()
            self.expect(")")
            return expr

        if self.match("{"):
            return self._parse_block()

        if self.match("["):
            return self._parse_array()

        # Harita literali: #["a": 1, "b": 2]
        # "{" blok/TypeBind ile çakıştığı için ayrı bir açılış işareti kullanılır.
        if self.match("#") and self.peek(1) is not None and self.peek(1).value == "[":
            return self._parse_map()

        if self.match_keyword("import"):
            return self._parse_import()

        if self.match_keyword("if"):
            return self._parse_if()

        if self.match_keyword("while"):
            return self._parse_while()

        if self.match_keyword("for"):
            return self._parse_for()

        return self._parse_literal()

    # ------------------------------------------------------------------
    # CallSuffix = "(" [ ArgumentList ] ")"
    #
    # children[0] = çağrılan ifade, children[1:] = argümanlar.
    # ------------------------------------------------------------------

    def _parse_call(self, callee: Node) -> Node:
        open_tok = self.expect("(")
        node     = Node(NodeType.CALL, open_tok)
        node.add(callee)

        if not self.match(")"):
            node.add(self._parse_expression())
            while self.match(","):
                self.advance()
                node.add(self._parse_expression())

        self.expect(")")
        return node

    # ------------------------------------------------------------------
    # MemberSuffix = "." IDENTIFIER
    # ------------------------------------------------------------------

    def _parse_member(self, obj: Node) -> Node:
        self.expect(".")
        tok = self.current()
        if tok is None or tok.type != TokenType.LITERAL_IDEN:
            raise ParseError("'.' sonrası üye adı beklendi", tok)
        self.advance()
        node = Node(NodeType.MEMBER, tok)
        node.add(obj)
        return node

    # ------------------------------------------------------------------
    # IndexSuffix = "[" Expression "]"
    # ------------------------------------------------------------------

    def _parse_index(self, obj: Node) -> Node:
        open_tok = self.expect("[")
        node     = Node(NodeType.INDEX, open_tok)
        node.add(obj)
        node.add(self._parse_expression())
        self.expect("]")
        return node

    # ------------------------------------------------------------------
    # ArrayLiteral = "[" [ Expression { "," Expression } [ "," ] ] "]"
    # ------------------------------------------------------------------

    def _parse_array(self) -> Node:
        open_tok = self.expect("[")
        node     = Node(NodeType.ARRAY, open_tok)

        while not self.match("]"):
            node.add(self._parse_expression())
            if self.match(","):
                self.advance()
            elif not self.match("]"):
                raise ParseError("Dizi elemanları arasında ',' beklendi",
                                 self.current())
        self.expect("]")
        return node

    # ------------------------------------------------------------------
    # MapLiteral = "#" "[" [ MapEntry { "," MapEntry } [ "," ] ] "]"
    # MapEntry   = Binary ":" Expression
    #
    # Anahtar Binary seviyesinde okunur; aksi halde ":" TypeBind olarak
    # yorumlanırdı. Çocuklar ikişerli sırayla [anahtar, değer, …] durur.
    # ------------------------------------------------------------------

    def _parse_map(self) -> Node:
        hash_tok = self.advance()                        # "#"
        self.expect("[")
        node = Node(NodeType.MAP, hash_tok)

        while not self.match("]"):
            node.add(self._parse_binary())               # anahtar (":" yemez)
            self.expect(":")
            node.add(self._parse_expression())           # değer
            if self.match(","):
                self.advance()
            elif not self.match("]"):
                raise ParseError("Harita girdileri arasında ',' beklendi",
                                 self.current())

        self.expect("]")
        return node

    # ------------------------------------------------------------------
    # ImportExpr = "import" Unary
    #
    # Bir ifadedir; modül değeri döndürür:
    #   mat = import "matematik.rad";
    #   mat.kare(3);
    # ------------------------------------------------------------------

    def _parse_import(self) -> Node:
        tok  = self.advance()                            # "import"
        node = Node(NodeType.IMPORT, tok)
        node.add(self._parse_unary())                    # yol ifadesi
        return node

    # ------------------------------------------------------------------
    # IfExpr = "if" Expression Block [ "else" ( IfExpr | Block ) ]
    #
    # Değer döndürür: seçilen dalın blok değeri.
    # Koşul parantezsiz yazılabilir; gövde blok olmak zorundadır.
    # ------------------------------------------------------------------

    def _parse_if(self) -> Node:
        tok  = self.advance()                            # "if"
        node = Node(NodeType.IF, tok)
        node.add(self._parse_expression())               # koşul
        node.add(self._parse_block())                    # then dalı

        if self.match_keyword("else"):
            self.advance()
            if self.match_keyword("if"):
                node.add(self._parse_if())               # else-if zinciri
            else:
                node.add(self._parse_block())
        return node

    # ------------------------------------------------------------------
    # WhileExpr = "while" Expression Block
    #
    # Değeri: son çalışan yinelemenin gövde değeri; hiç dönmezse unit.
    # ------------------------------------------------------------------

    def _parse_while(self) -> Node:
        tok  = self.advance()                            # "while"
        node = Node(NodeType.WHILE, tok)
        node.add(self._parse_expression())               # koşul
        node.add(self._parse_block())                    # gövde
        return node

    # ------------------------------------------------------------------
    # ForExpr = "for" IDENTIFIER "in" Expression Block
    # ------------------------------------------------------------------

    def _parse_for(self) -> Node:
        self.advance()                                   # "for"
        var_tok = self.current()
        if (var_tok is None
                or var_tok.type != TokenType.LITERAL_IDEN
                or var_tok.value in KEYWORDS):
            raise ParseError("'for' sonrası döngü değişkeni beklendi", var_tok)
        self.advance()

        if not self.match_keyword("in"):
            raise ParseError("'in' beklendi", self.current())
        self.advance()

        node = Node(NodeType.FOR, var_tok)
        node.add(self._parse_expression())               # üzerinde gezilecek dizi
        node.add(self._parse_block())                    # gövde
        return node

    # ------------------------------------------------------------------
    # Literal = T_STRING | T_CHAR | T_NUMBER | T_IDENTIFIER
    #         | "true" | "false" | PrimitiveType
    # ------------------------------------------------------------------

    def _parse_literal(self) -> Node:
        tok = self.current()
        if tok is None:
            raise ParseError("İfade beklendi, dosya sonu bulundu")

        if tok.type in (TokenType.LITERAL_STR,
                        TokenType.LITERAL_CHAR,
                        TokenType.LITERAL_NUM):
            return Node(NodeType.LITERAL, self.advance())

        if tok.type == TokenType.LITERAL_IDEN:
            if tok.value in KEYWORDS and tok.value not in KEYWORD_LITERALS:
                raise ParseError(
                    f"'{tok.value}' burada kullanılamaz", tok)
            self.advance()
            ntype = (NodeType.LITERAL
                     if tok.value in PRIMITIVE_TYPES or tok.value in KEYWORD_LITERALS
                     else NodeType.IDENTIFIER)
            return Node(ntype, tok)

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
    #               | "[" TypeExpr "]"          — dizi tipi
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

        if self.match("["):
            open_tok = self.advance()
            node     = Node(NodeType.ARRAY, open_tok)    # eleman tipi çocukta
            node.add(self._parse_type_expr())
            self.expect("]")
            return node

        tok = self.current()
        if tok and tok.type == TokenType.LITERAL_IDEN and tok.value not in KEYWORDS:
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
    # Operator = T_SYMBOL
    #
    # Lexer çok karakterli sembolleri symbols.txt'e göre tek token üretir;
    # parser ayrıca birleştirme yapmaz. Yeni bir operatör için symbols.txt'e
    # satır eklemek yeterlidir (öncelik tablosunda yoksa CUSTOM_LEVEL'a düşer).
    # ------------------------------------------------------------------

    def _parse_operator(self) -> Node:
        tok = self.current()
        if tok is None or not self._is_operator_start(tok):
            raise ParseError("Operatör beklendi", tok)
        self.advance()
        return Node(NodeType.OPERATOR, tok)

    # ------------------------------------------------------------------
    # Yardımcı kontroller
    # ------------------------------------------------------------------

    def _is_operator_start(self, tok: Token) -> bool:
        """Token bir binary operatör başlatabilir mi?"""
        return (tok.type == TokenType.LITERAL_SYMB
                and tok.value not in TERMINATORS
                and tok.value not in ASSIGN_OPS
                and tok.value not in INCDEC_OPS
                and tok.value != ":")

    def _operator_level(self) -> int | None:
        """
        Geçerli token'ın binary öncelik seviyesi; operatör değilse None.
        Tabloda bulunmayan semboller CUSTOM_LEVEL'a düşer.
        """
        tok = self.current()
        if tok is None or not self._is_operator_start(tok):
            return None
        for level, ops in enumerate(BINARY_LEVELS):
            if tok.value in ops:
                return level
        return CUSTOM_LEVEL

    def _is_unary_operator(self) -> bool:
        """Tekli önek operatörü: UNARY_OPS üyesi ve ardında bir işlenen var."""
        tok = self.current()
        nxt = self.peek(1)
        if tok is None or nxt is None:
            return False
        if tok.type != TokenType.LITERAL_SYMB or tok.value not in UNARY_OPS:
            return False
        return (nxt.type in (TokenType.LITERAL_NUM,
                             TokenType.LITERAL_STR,
                             TokenType.LITERAL_CHAR,
                             TokenType.LITERAL_IDEN)
                or nxt.value in ("(", "{", "[")
                or (nxt.type == TokenType.LITERAL_SYMB and nxt.value in UNARY_OPS))


# ---------------------------------------------------------------------------
# Kolaylık fonksiyonu — lexer + parser tek adımda
# ---------------------------------------------------------------------------

def parse_source(source: str, symbols_file: str = "symbols.txt") -> Node:
    """Kaynak metni AST'ye çevirir. Lexer hatası da ParseError olarak yükselir."""
    tokens = lexer(source, symbols_file=symbols_file)
    if isinstance(tokens, dict):
        raise ParseError(
            f"Sözcüksel hata: {tokens['error']}",
            Token(TokenType.NULL, "", tokens["line"], tokens["column"]),
        )
    return Parser(tokens).parse()


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
        ("Bileşik atama",         "a += 1;"),

        # --- İfade ---
        ("Aritmetik",             "z = x + y * 2;"),
        ("Öncelik zinciri",       "z = 1 + 2 * 3 - 4 / 2;"),
        ("Üs sağ çağrışım",       "z = 2 ** 3 ** 2;"),
        ("Karşılaştırma + mantık","b = x < 1 && y >= 2 || !z;"),
        ("Unary eksi",            "n = -5;"),
        ("Unary not",             "f = !flag;"),
        ("Gruplama",              "r = (x + y) * 2;"),
        ("lvalue expression",     "r = (a = b) + 1;"),
        ("İç içe unary",          "r = -(x + 1);"),
        ("Binary + unary",        "r = a + -b;"),

        # --- Çağrı / erişim / dizi ---
        ("Fonksiyon çağrısı",     "print(42);"),
        ("Çok argümanlı çağrı",   "add(1, 2, 3);"),
        ("İç içe çağrı",          "apply(f, g(x));"),
        ("Currying",              "f(1)(2);"),
        ("Üye erişimi",           "a.b.c;"),
        ("Dizi literali",         "xs = [1, 2, 3];"),
        ("İndeksleme",            "v = xs[i + 1];"),
        ("Zincir",                "obj.items[0](arg);"),

        # --- Harita / yapı / modül ---
        ("Harita literali",       'm = #["a": 1, "b": 2];'),
        ("Harita erişimi",        'v = m["a"];'),
        ("Yapı tanımı",           "struct Nokta (x:i32, y:i32);"),
        ("Yapı kurma + alan",     "p = Nokta(3, 4); p.x;"),
        ("Modül import",          'geo = import "lib/geometri.rad";'),
        ("Artır / azalt",         "x++; ++y; xs[0]--;"),

        # --- Blok ---
        ("Blok değer",            "r = { a = 1; a + 2; };"),

        # --- Akış denetimi ---
        ("if / else",             "r = if x > 0 { 1; } else { 0; };"),
        ("if / else if",          "if a { 1; } else if b { 2; } else { 3; }"),
        ("while",                 "while i < 10 { i += 1; }"),
        ("for",                   "for x in xs { print(x); }"),

        # --- Tip imzası ---
        ("Fonk imzası (stmt)",    "topla : (x:i32, y:i32) -> i32;"),
        ("Isimsiz parametre",     "g : (i32, i32) -> i32;"),
        ("Curried fonk tipi",     "f : (x:i32) -> (y:i32) -> bool;"),
        ("HOF tipi",              "apply : (f:(x:i32) -> i32, v:i32) -> i32;"),
        ("Dizi tipi",             "xs : [i32];"),
    ]

    func_cases = [
        # ( etiket, kaynak kod )
        ("Gövde (imzasız)",
         "topla { result = x + y; result; }"),

        ("Satır içi imza + gövde",
         "topla (x:i32, y:i32) -> i32 { result = x + y; result; }"),

        ("main",
         'main () -> i32 { print("Hello, World!\\n"); 0; }'),

        ("return ile erken çıkış",
         "mutlak (x:i32) -> i32 { if x < 0 { return -x; } x; }"),
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
