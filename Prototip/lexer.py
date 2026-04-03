import os
from enum import Enum, auto


# Tek başına sembol karakteri olarak tanınan karakterler.
# Çok karakterli semboller symbols.txt'den yüklenir.
SYMBOL_CHARS  = set("+-*/%=();:,.[]<>{}&|!~^?@#")
NUMBER_EXTRAS = set("._Eebxo")


# ---------------------------------------------------------------------------
# Yardımcı fonksiyonlar
# ---------------------------------------------------------------------------

def is_symbol_char(char: str) -> bool:
    return char in SYMBOL_CHARS

def is_whitespace(char: str) -> bool:
    return char in " \t\n\r"

def is_digit(char: str) -> bool:
    return '0' <= char <= '9'

def is_uident(char: str) -> bool:
    """Tanımlayıcı (identifier) içinde geçebilecek 'serbest' karakter mi?"""
    return not (is_symbol_char(char) or is_whitespace(char)
                or is_digit(char) or char in ("'", '"'))


def load_multi_char_symbols(filepath: str = "symbols.txt") -> list[str]:
    """
    symbols.txt dosyasından çok karakterli sembolleri yükler.
    Yorum satırları ('#') ve boş satırlar atlanır.
    Greedy (en uzun eşleşme) için uzunluğa göre azalan sırada döner.
    """
    if not os.path.exists(filepath):
        return []
    with open(filepath, encoding="utf-8") as fh:
        symbols = [
            line.strip()
            for line in fh
            if line.strip() and not line.strip().startswith("#")
        ]
    # En uzun sembol önce → greedy eşleşme garantisi
    return sorted(symbols, key=len, reverse=True)


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

class TokenType(Enum):
    NULL         = auto()
    WS           = auto()
    LITERAL_UNKN = auto()
    LITERAL_NUM  = auto()
    LITERAL_STR  = auto()
    LITERAL_CHAR = auto()
    LITERAL_IDEN = auto()
    LITERAL_SYMB = auto()



class Token:
    def __init__(self, type: TokenType, value: str,
                 line: int = 0, column: int = 0):
        self.type   = type
        self.value  = value
        self.line   = line
        self.column = column

    def __str__(self):
        return f"Token({self.type}, {self.value!r}, {self.line}:{self.column})"

    def __repr__(self):
        return self.__str__()


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------

def lexer(
    input_str: str,
    symbols_file: str = "symbols.txt",
) -> list[Token] | dict:
    """
    Girdi dizisini Token listesine çevirir.
    Hata durumunda {"line": ..., "column": ..., "error": ...} döner.
    """

    multi_symbols: list[str] = load_multi_char_symbols(symbols_file)

    tokens: list[Token]  = []
    index  = 0
    length = len(input_str)

    # Aktif yığın
    stack      = ""
    stack_type = TokenType.NULL
    tok_line   = 1          # token'ın başladığı satır
    tok_col    = 0          # token'ın başladığı sütun

    # Genel konum takibi
    line   = 1
    column = 0

    # Durum bayrakları
    is_escaped   = False
    has_dot      = False
    has_exponent = False
    has_prefix   = False

    # ------------------------------------------------------------------
    # İç yardımcılar
    # ------------------------------------------------------------------

    def advance() -> str:
        """Geçerli karakteri tüket; satır/sütun sayacını güncelle."""
        nonlocal index, line, column
        ch = input_str[index]
        index += 1
        if ch == "\n":
            line  += 1
            column = 0
        else:
            column += 1
        return ch

    def flush(stype: TokenType | None = None):
        """Yığını token olarak kaydet, durumu sıfırla."""
        nonlocal stack, stack_type, is_escaped
        nonlocal has_dot, has_exponent, has_prefix
        if stack:
            tokens.append(Token(stype or stack_type, stack, tok_line, tok_col))
        stack        = ""
        stack_type   = TokenType.NULL
        is_escaped   = False
        has_dot      = False
        has_exponent = False
        has_prefix   = False

    def error(msg: str) -> dict:
        return {"line": line, "column": column, "error": msg}

    # ------------------------------------------------------------------
    # Ana döngü
    # ------------------------------------------------------------------

    while index < length:
        char = input_str[index]

        # ==============================================================
        # NULL — yeni token bekleniyor
        # ==============================================================
        if stack_type == TokenType.NULL:

            # Boşluk karakterleri
            if is_whitespace(char):
                advance()
                continue

            # Çok karakterli sembol denemesi (greedy)
            matched_sym = None
            for sym in multi_symbols:
                end = index + len(sym)
                if input_str[index:end] == sym:
                    matched_sym = sym
                    break

            if matched_sym is not None:
                tok_line, tok_col = line, column + 1
                for _ in matched_sym:
                    advance()
                tokens.append(Token(TokenType.LITERAL_SYMB, matched_sym,
                                    tok_line, tok_col))
                continue

            # Tek karakterli sembol
            if is_symbol_char(char):
                tok_line, tok_col = line, column + 1
                advance()
                tokens.append(Token(TokenType.LITERAL_SYMB, char,
                                    tok_line, tok_col))
                continue

            # Yeni token başlatılıyor
            tok_line, tok_col = line, column + 1

            if is_digit(char):
                stack_type = TokenType.LITERAL_NUM
            elif char == "_":
                stack_type = TokenType.LITERAL_IDEN
            elif char == "'":
                stack_type = TokenType.LITERAL_CHAR
            elif char == '"':
                stack_type = TokenType.LITERAL_STR
            elif is_uident(char):
                stack_type = TokenType.LITERAL_IDEN
            else:
                advance()
                tokens.append(Token(TokenType.LITERAL_UNKN, char,
                                    tok_line, tok_col))
                continue

            stack += advance()
            continue

        # ==============================================================
        # LITERAL_NUM — sayısal sabit
        # ==============================================================
        if stack_type == TokenType.LITERAL_NUM:

            # Önek sonrası geçerli rakam mı?
            is_prefixed_digit = False
            if has_prefix:
                prefix_char = stack[1] if len(stack) > 1 else ""
                if prefix_char == "x" and char in "0123456789abcdefABCDEF":
                    is_prefixed_digit = True
                elif prefix_char == "b" and char in "01":
                    is_prefixed_digit = True
                elif prefix_char == "o" and char in "01234567":
                    is_prefixed_digit = True

            if is_digit(char) or is_prefixed_digit:
                stack += advance()

            elif char in NUMBER_EXTRAS and not has_prefix:

                if char == "_":                         # sayısal ayraç: 1_000
                    if index + 1 >= length or not is_digit(input_str[index + 1]):
                        return error("Sayıda geçersiz alt çizgi")
                    advance()                               # '_' atla, stack'e ekleme

                elif char == ".":
                    if has_dot or has_exponent or has_prefix:
                        return error("Sayıda geçersiz nokta")
                    has_dot = True
                    stack  += advance()

                elif char in ("E", "e"):
                    if has_exponent or has_prefix:
                        return error("Sayıda geçersiz üs gösterimi")
                    has_exponent = True
                    stack += advance()
                    if index < length and input_str[index] in "+-":
                        stack += advance()

                elif char in ("b", "x", "o"):
                    # Sadece "0" yığınındayken önek kabul edilir
                    if stack == "0":
                        has_prefix = True
                        stack += advance()
                    else:
                        return error("Geçersiz sayısal önek")

            else:
                flush()
                # char tüketilmedi; döngü yeniden bu karakteri işler

            continue

        # ==============================================================
        # LITERAL_IDEN — tanımlayıcı / anahtar sözcük
        # ==============================================================
        if stack_type == TokenType.LITERAL_IDEN:
            if is_uident(char) or is_digit(char) or char == "_":
                stack += advance()
            else:
                flush()
                # char tüketilmedi
            continue

        # ==============================================================
        # LITERAL_STR — çift tırnaklı dizgi
        # ==============================================================
        if stack_type == TokenType.LITERAL_STR:
            ch = advance()
            stack += ch

            if is_escaped:
                is_escaped = False
            elif ch == "\\":
                is_escaped = True
            elif ch == '"':
                flush()

            continue

        # ==============================================================
        # LITERAL_CHAR — tek tırnaklı karakter sabiti
        # ==============================================================
        if stack_type == TokenType.LITERAL_CHAR:
            ch = advance()
            stack += ch

            if is_escaped:
                is_escaped = False
            elif ch == "\\":
                is_escaped = True
            elif ch == "'":
                flush()

            continue

    # ------------------------------------------------------------------
    # Dosya sonu: yığında bekleyen token varsa kaydet
    # ------------------------------------------------------------------
    if stack:
        if stack_type in (TokenType.LITERAL_STR, TokenType.LITERAL_CHAR):
            # Kapanmamış string/char → hata
            return {"line": line, "column": column,
                    "error": "Kapatılmamış dize veya karakter sabiti"}
        flush()

    return tokens


# ---------------------------------------------------------------------------
# Hızlı test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    samples = [
        'x == 10 && y != 0',
        'ptr->field',
        'a <<= 3',
        'fn :: () -> int',
        'x += 1_000_000',
        '0xFF + 3.14e-2',
        '"merhaba\\ndünya"',
        "x ... y",
        'a ** b **= c',
    ]

    for src in samples:
        print(f"\nGirdi : {src!r}")
        result = lexer(src)
        if isinstance(result, dict):
            print(f"  HATA: {result}")
        else:
            for tok in result:
                print(f"  {tok}")
