# Parser Güncelleme Rehberi -- Radian Language

> **Versiyon:** 1.0  
> **Durum:** Aktif Geliştirme  
> Bu belge, Radian Language parser'ına yeni özellik ekleme, hata düzeltme  
> ve yapıyı genişletme konusunda adım-adım rehberlik sağlar.

---

## İçindekiler

1. [Parser Mimarisi](#1-parser-mimarisi)
   - 1.1 [Genel Yapı](#11-genel-yapı)
   - 1.2 [Recursive Descent Parsing](#12-recursive-descent-parsing)
   - 1.3 [Önemli Bileşenler](#13-önemli-bileşenler)
2. [Temel Kavramlar](#2-temel-kavramlar)
   - 2.1 [Node Nedir?](#21-node-nedir)
   - 2.2 [NodeType Enumu](#22-nodetype-enumu)
   - 2.3 [Hata Yönetimi](#23-hata-yönetimi)
3. [Parser'a Değişiklik Ekleme Süreci](#3-parsera-değişiklik-ekleme-süreci)
   - 3.1 [5 Adımlı Yaklaşım](#31-5-adımlı-yaklaşım)
   - 3.2 [Gramer Kuralını Belirleme](#32-gramer-kuralını-belirleme)
   - 3.3 [NodeType Ekleme](#33-nodetype-ekleme)
   - 3.4 [Parse Metodu Yazma](#34-parse-metodu-yazma)
   - 3.5 [Entegrasyon ve Test](#35-entegrasyon-ve-test)
4. [Yaygın Görevler](#4-yaygın-görevler)
   - 4.1 [Yeni Binary Operatör Ekleme](#41-yeni-binary-operatör-ekleme)
   - 4.2 [Yeni Unary Operatör Ekleme](#42-yeni-unary-operatör-ekleme)
   - 4.3 [Fonksiyon Çağrısı `f(x, y)` Ekleme](#43-fonksiyon-çağrısı-fx-y-ekleme)
   - 4.4 [İf/Else Expression Ekleme](#44-ifelse-expression-ekleme)
   - 4.5 [While Loop Ekleme](#45-while-loop-ekleme)
   - 4.6 [Return Statement Ekleme](#46-return-statement-ekleme)
   - 4.7 [Üye Erişimi `a.b` Ekleme](#47-üye-erişimi-ab-ekleme)
5. [Operatör Önceliği ve Çağrışımlılık](#5-operatör-önceliği-ve-çağrışımlılık)
   - 5.1 [Mevcut Öncelik Hiyerarşisi](#51-mevcut-öncelik-hiyerarşisi)
   - 5.2 [Öncelik Değiştirme](#52-öncelik-değiştirme)
   - 5.3 [Yeni Katman Ekleme](#53-yeni-katman-ekleme)
6. [Debugging ve Test Etme](#6-debugging-ve-test-etme)
   - 6.1 [AST Yazdırma](#61-ast-yazdırma)
   - 6.2 [Test Case'ler Yazma](#62-test-casepler-yazma)
   - 6.3 [Yaygın Hatalar](#63-yaygın-hatalar)
7. [Workflow Şablonu](#7-workflow-şablonu)
   - 7.1 [Hızlı Referans Checklist](#71-hızlı-referans-checklist)
   - 7.2 [Örnek Senaryo](#72-örnek-senaryo)

---

## 1. Parser Mimarisi

### 1.1 Genel Yapı

```
┌─────────────────────────────────────────────────┐
│  LEXER (lexer.py)                               │
│  Giriş: Kaynak kod dizesi                       │
│  Çıkış: Token listesi                           │
└─────────────────────────┬───────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────┐
│  PARSER (parser.py)                             │
│  ├─ NodeType (AST düğüm tipleri)               │
│  ├─ Node (AST düğüm sınıfı)                    │
│  ├─ Parser (recursive descent yazıcı)          │
│  └─ ParseError (hata yönetimi)                 │
│  Giriş: Token listesi                           │
│  Çıkış: AST (Abstract Syntax Tree)             │
└─────────────────────────┬───────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────┐
│  SEMANTIC ANALYSIS / CODE GEN (gelecek)        │
│  Giriş: AST                                     │
│  Çıkış: Ara kod / İcra planı                   │
└─────────────────────────────────────────────────┘
```

### 1.2 Recursive Descent Parsing

Recursive descent parser, **her gramer kuralına karşılık bir metot** yazarak çalışır:

```
Gramer Kuralı          →  Parser Metodu
─────────────────         ───────────────
Expression             →  _parse_expression()
Assign                 →  _parse_assign()
Binary                 →  _parse_binary()
Unary                  →  _parse_unary()
Term                   →  _parse_term()
Literal                →  _parse_literal()
```

**Çalışma Prensibi:**

1. **Mevcut token'ı kontrol** (`self.current()`)
2. **Lookahead yap** (`self.peek(n)`) — kaç token ileride bakma
3. **Token tüket** (`self.advance()`) — sonraki token'a git
4. **Beklenen token kontrol** (`self.expect()`) — tam eşleşme garantisi
5. **Alt kuralları çağır** — yukarıdan aşağı inme

Örnek:
```python
def _parse_assign(self) -> Node:
    left = self._parse_typebind()           # Alt kural: TypeBind parse et
    if self.match("="):                     # Mevcut = mi?
        self.advance()                      # "=" tüket
        right = self._parse_assign()        # Sağ tarafı (sağ-çağrışımlı) parse et
        node = Node(NodeType.ASSIGN)
        node.value = self.tokens[self.pos - 1]  # "=" token'ı sakla
        node.add(left).add(right)
        return node
    return left
```

### 1.3 Önemli Bileşenler

| Bileşen | Dosya | Açıklama |
|---------|-------|----------|
| **Lexer** | `lexer.py` | Kaynak kodu token'lara ayırır |
| **Token** | `lexer.py` | Tür, değer, satır, sütun bilgisi |
| **Node** | `parser.py` | AST düğümü; tip, değer, çocuk listesi |
| **NodeType** | `parser.py` | Enum; olası düğüm tipleri |
| **Parser** | `parser.py` | Ana yazıcı sınıfı; _parse_* metodları |
| **ParseError** | `parser.py` | Ayrıntılı hata mesajları |

---

## 2. Temel Kavramlar

### 2.1 Node Nedir?

`Node`, AST'nin temel yapı taşıdır. Her `Node`:

```python
class Node:
    type: NodeType              # Düğüm türü (ASSIGN, BINARY_OP, vb.)
    value: Token | None        # İsteğe bağlı token (operatör, isim, vb.)
    children: list[Node]       # Alt düğümler (sol, sağ, argümanlar, vb.)
```

**Örnek:**

```
Kaynak: a = 5 + 3;

AST:
  STATEMENT
    └─ ASSIGN (value='=')
       ├─ IDENTIFIER (value='a')
       └─ BINARY_OP (value='+')
          ├─ LITERAL (value='5')
          └─ LITERAL (value='3')
```

### 2.2 NodeType Enumu

Yeni bir kuralı parser'a eklerken **ilk adım** bu enuma yeni bir tür eklemektir:

```python
class NodeType(Enum):
    # Mevcut tipler...
    PROGRAM    = auto()
    STATEMENT  = auto()
    BINARY_OP  = auto()
    
    # YENİ TİP EKLEME
    CALL       = auto()    # Fonksiyon çağrısı f(x, y)
    IF_EXPR    = auto()    # if koşulu then blok else blok
    ARRAY      = auto()    # [1, 2, 3]
```

### 2.3 Hata Yönetimi

`ParseError`, ayrıntılı konum bilgisi içerir:

```python
class ParseError(Exception):
    def __init__(self, msg: str, token: Token | None = None):
        loc = f" [{token.line}:{token.column}]" if token else ""
        super().__init__(f"{msg}{loc}")
```

**Fırlatma Örneği:**

```python
if not self.match("("):
    raise ParseError("'(' beklendi", self.current())
```

**Çıktı:**

```
ParseError: '(' beklendi [5:12]
```

---

## 3. Parser'a Değişiklik Ekleme Süreci

### 3.1 5 Adımlı Yaklaşım

Herhangi bir yeni özellik eklerken bu süreci izle:

```
┌──────────────────────────────────────────────────────┐
│ ADIM 1: Gramer Kuralını Belirleme                   │
│  • Radian.ebnf veya Grammer.md'de tanımla           │
│  • Diğer kurallarla nasıl bağlantılı olduğunu anla  │
└──────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────┐
│ ADIM 2: NodeType Ekleme                             │
│  • parser.py: NodeType Enum'a yeni tür ekle         │
│  • Grammer.md: Node Tipi Referansı'na ekle          │
└──────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────┐
│ ADIM 3: Parse Metodu Yazma                          │
│  • _parse_* metodunu yaz                            │
│  • Lookahead ve token kontrolleri yerleştir         │
│  • Alt kuralları çağır                              │
└──────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────┐
│ ADIM 4: Entegrasyon                                 │
│  • Uygun üst kuraldan _parse_* çağırısını ekle      │
│  • Lookahead/match ile doğru yere yönlendir         │
└──────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────┐
│ ADIM 5: Test Etme                                   │
│  • Test case'ler ekle                               │
│  • AST yapısını kontrol et                          │
│  • Hata durumları test et                           │
└──────────────────────────────────────────────────────┘
```

### 3.2 Gramer Kuralını Belirleme

**Soru:** Eklemek istediğin özellik gramer açısından nereye yerleşir?

Mevcut hiyerarşi (düşük → yüksek öncelik):

```
Expression  ← En düşük (root)
  Assign
    TypeBind
      Binary
        Unary
          Term      ← En yüksek (yaprak)
```

**Tablo:**

| Yeni Özellik | Konum | Kural |
|--------------|-------|-------|
| `if` / `else` | Expression | Atamadan önce |
| Operatör | Binary | Arasında katman? |
| Fonksiyon çağrısı | Term/Unary | Term sonrası postfix |
| Tablo indeksi `a[i]` | Term/Unary | Term sonrası postfix |
| Üye erişimi `a.b` | Term/Unary | Term sonrası postfix |
| `while` loop | Statement | Ifadeden önce |

### 3.3 NodeType Ekleme

`parser.py` dosyasının başında:

```python
class NodeType(Enum):
    # ... mevcut tipler ...
    
    # YENİ ÖZELLİK İÇİN EKLE
    CALL       = auto()  # Fonksiyon çağrısı
    IF_EXPR    = auto()  # if/else expression
    WHILE_LOOP = auto()  # while koşulu blok
```

**Kurallı Adlandırma:**
- `_EXPR` suffiksi: değer döndüren (expression)
- `_STMT` suffiksi: statement (opsiyonel)
- `_OP` suffiksi: operatör veya işlem

### 3.4 Parse Metodu Yazma

Temel şablon:

```python
def _parse_MY_FEATURE(self) -> Node:
    """
    MyFeature = kaçıklamalar ...
    
    Örnek parse ağacı:
      ...
    """
    # Başlangıç token'ını al
    start_tok = self.current()
    
    # Gerekli token'ı bekle / kontrol et
    self.expect("keyword")
    
    # NodeType nesnesi oluştur
    node = Node(NodeType.MY_FEATURE, start_tok)
    
    # Alt kuralları parse et
    node.add(self._parse_...())
    
    # Bitiriş token'ını bekle
    self.expect("end_marker")
    
    return node
```

**Metodun Başında Yapılması Gerekenler:**

1. **Lookahead yapma** — hangi token tiyle karşılaştığını bileme
   ```python
   tok = self.current()
   nxt = self.peek(1)
   if tok and tok.value == "if" and nxt and nxt.value == "(":
       # Bu bizim kurala uyuyor
   ```

2. **Başlangıç token'ını sakla**
   ```python
   start_tok = self.advance()  # "if" tüket
   ```

3. **Hata ihtimali düşün**
   ```python
   if not self.match(")"):
       raise ParseError("')' beklendi", self.current())
   ```

### 3.5 Entegrasyon ve Test

#### Adım A: Üst Kural İçerisine Entegrasyonu

Eğer `if` expression'ını eklemek istiyorsan, `_parse_expression` içine kondsayıonal ekle:

```python
def _parse_expression(self) -> Node:
    # if keyword'ü varsa if expression parse et
    if self.match("if"):
        return self._parse_if_expr()
    
    # Değilse normal assign → expr zinciri devam
    return self._parse_assign()
```

#### Adım B: Lookahead Tutarlılığı

Örneğin `IDENTIFIER + "("` → fonksiyon çağrısı, bu Pattern'ı tutarlı kullan:

```python
def _parse_term(self) -> Node:
    tok = self.current()
    nxt = self.peek(1)
    
    # Fonksiyon çağrısı: IDEN (
    if (tok and tok.type == TokenType.LITERAL_IDEN
            and nxt and nxt.value == "("):
        return self._parse_call()
    
    # ...
```

#### Adım C: Test Yazma

Mevcut test yapısını kullan:

```python
if __name__ == "__main__":
    cases = [
        ("Fonksiyon çağrısı", "print(42);"),
        ("Nested çağrı", "apply(f, g(x));"),
    ]
    
    for label, src in cases:
        print(f"Test: {label}")
        print(f"  Kaynak: {src}")
        tokens = lexer(src)
        parser = Parser(tokens)
        ast = parser.parse()
        print(ast)
        print()
```

---

## 4. Yaygın Görevler

### 4.1 Yeni Binary Operatör Ekleme

**Amaç:** `<<` (sol bit kaydırma) operatörü eklemek

**Adım 1: symbols.txt'e ekle**

```bash
# symbols.txt (bitwise operatörler)
<<
>>
&
|
^
```

> Lexer otomatik olarak çok karakterli sembolleri tanıyacak.

**Adım 2: Test et**

Lexer tarafını test et:

```python
from lexer import lexer

tokens = lexer("a << 2")
for tok in tokens:
    print(tok)
# Output:
# Token(LITERAL_IDEN, 'a', ...)
# Token(LITERAL_SYMB, '<<', ...)
# Token(LITERAL_NUM, '2', ...)
```

**Senaryo Sonuç:**

Parser zaten **tüm binary operatörleri** `Binary` kuralında dinamik olarak işler:

```python
def _parse_binary(self) -> Node:
    left = self._parse_unary()
    while self._is_binary_operator():
        op_node = self._parse_operator()
        right = self._parse_unary()
        node = Node(NodeType.BINARY_OP)
        node.add(left).add(op_node).add(right)
        left = node
    return left
```

✅ **Başka değişiklik gerekmez!** Operatör otomatik tanınır.

---

### 4.2 Yeni Unary Operatör Ekleme

**Amaç:** `~` (bitwise NOT) ekleme

**Adım 1: symbols.txt'e ekle** (zaten var mı kontrol et)

```
~
```

**Adım 2: Test et**

```python
tokens = lexer("~x")
for tok in tokens:
    print(tok)
```

**Senaryo Sonuç:**

Parser zaten unary operatörleri dinamik tanır:

```python
def _parse_unary(self) -> Node:
    if self._is_unary_operator():
        op_node = self._parse_operator()
        term = self._parse_term()
        node = Node(NodeType.UNARY_OP)
        node.add(op_node).add(term)
        return node
    return self._parse_term()
```

✅ **Başka değişiklik gerekmez!** Otomatik tanınır.

> **Not:** Operatör önceliğini ayarlamak istersen bkz. [Bölüm 5.2](#52-öncelik-değiştirme)

---

### 4.3 Fonksiyon Çağrısı `f(x, y)` Ekleme

**Amaç:** `f(arg1, arg2, ...)` çağrısı parse etmek

**Adım 1: NodeType ekleme**

```python
class NodeType(Enum):
    # ...
    CALL = auto()  # Fonksiyon çağrısı
```

**Adım 2: Grammer.md veya Radian.ebnf'e ekleme**

```bnf
Term = "(" Expression ")"
     | Block
     | Literal
     | FunctionCall    ← YENİ

FunctionCall = T_IDENTIFIER "(" [ ArgumentList ] ")"
ArgumentList = Expression { "," Expression }
```

**Adım 3: Parse metodu yazma**

```python
def _parse_call(self) -> Node:
    """
    FunctionCall = T_IDENTIFIER "(" [ ArgumentList ] ")"
    """
    name_tok = self.advance()          # Fonksiyon ismi tüket
    node = Node(NodeType.CALL, name_tok)
    
    self.expect("(")
    
    # Argüman listesi (virgülle ayrılmış)
    if not self.match(")"):
        node.add(self._parse_expression())
        while self.match(","):
            self.advance()              # "," tüket
            node.add(self._parse_expression())
    
    self.expect(")")
    return node
```

**Adım 4: _parse_term'e entegrasyon**

```python
def _parse_term(self) -> Node:
    tok = self.current()
    nxt = self.peek(1)
    
    # Fonksiyon çağrısı: IDEN "("
    if (tok and tok.type == TokenType.LITERAL_IDEN
            and nxt and nxt.value == "("):
        return self._parse_call()
    
    if self.match("("):
        self.advance()
        node = self._parse_expression()
        self.expect(")")
        return node
    
    if self.match("{"):
        return self._parse_block()
    
    return self._parse_literal()
```

**Adım 5: Test**

```python
cases = [
    ("Basit çağrı", "print(42);"),
    ("Çok arg", "add(1, 2, 3);"),
    ("Nested", "apply(f, g(x));"),
]

for label, src in cases:
    print(f"\n{label}: {src}")
    tokens = lexer(src)
    parser = Parser(tokens)
    ast = parser.parse()
    print(ast)
```

---

### 4.4 İf/Else Expression Ekleme

**Amaç:** `if koşul then blok else blok` parse etmek; değer döndürsün

**Adım 1: NodeType ekleme**

```python
class NodeType(Enum):
    # ...
    IF_EXPR = auto()
```

**Adım 2: Grammer ekleme**

```bnf
Expression = IfExpr | Assign

IfExpr = "if" "(" Expression ")" Block [ "else" Block ]
```

**Adım 3: Parse metodu yazma**

```python
def _parse_if_expr(self) -> Node:
    """
    IfExpr = "if" "(" Expression ")" Block [ "else" Block ]
    
    Örnek:
      if (x > 0) { x; } else { -x; }
      →  IF_EXPR
         ├─ BINARY_OP (>)
         │  ├─ x
         │  └─ 0
         ├─ BLOCK (then)
         └─ BLOCK (else)
    """
    if_tok = self.advance()             # "if" tüket
    node = Node(NodeType.IF_EXPR, if_tok)
    
    self.expect("(")
    condition = self._parse_expression()
    self.expect(")")
    
    then_block = self._parse_block()
    
    # else opsiyonel
    else_block = None
    if self.match("else"):
        self.advance()                  # "else" tüket
        else_block = self._parse_block()
    
    node.add(condition)
    node.add(then_block)
    if else_block:
        node.add(else_block)
    
    return node
```

**Adım 4: _parse_expression'a entegrasyon**

```python
def _parse_expression(self) -> Node:
    if self.match("if"):
        return self._parse_if_expr()
    return self._parse_assign()
```

**Adım 5: Test**

```python
cases = [
    ("Basit if", "r = if (true) { 1; };"),
    ("if-else", "r = if (x > 0) { x; } else { 0; };"),
    ("Nested", "r = if (a) { if (b) { 1; } else { 2; } } else { 3; };"),
]
```

---

### 4.5 While Loop Ekleme

**Amaç:** `while koşul blok` parse etmek

**Adım 1: NodeType ekleme**

```python
class NodeType(Enum):
    # ...
    WHILE_LOOP = auto()
```

**Adım 2: Grammer ekleme**

```bnf
Statement = WhileStatement | Expression ";"

WhileStatement = "while" "(" Expression ")" Block
```

**Adım 3: Parse metodu yazma**

```python
def _parse_while(self) -> Node:
    """
    WhileStatement = "while" "(" Expression ")" Block
    """
    while_tok = self.advance()          # "while" tüket
    node = Node(NodeType.WHILE_LOOP, while_tok)
    
    self.expect("(")
    condition = self._parse_expression()
    self.expect(")")
    
    body = self._parse_block()
    
    node.add(condition)
    node.add(body)
    
    return node
```

**Adım 4: _parse_statement'a entegrasyon**

```python
def _parse_statement(self) -> Node:
    if self.match("while"):
        return self._parse_while()
    
    node = Node(NodeType.STATEMENT)
    node.add(self._parse_expression())
    self.expect(";")
    return node
```

**Adım 5: Test**

```python
cases = [
    ("Basit while", "while (x > 0) { x = x - 1; }"),
    ("Iç içe", "while (a) { while (b) { c; } }"),
]
```

---

### 4.6 Return Statement Ekleme

**Amaç:** `return expr;` parse etmek (fonksiyon içinden erken çıkış)

**Adım 1: NodeType ekleme**

```python
class NodeType(Enum):
    # ...
    RETURN = auto()
```

**Adım 2: Grammer ekleme**

```bnf
Statement = ReturnStatement | Expression ";"

ReturnStatement = "return" [ Expression ] ";"
```

**Adım 3: Parse metodu yazma**

```python
def _parse_return(self) -> Node:
    """
    ReturnStatement = "return" [ Expression ] ";"
    """
    return_tok = self.advance()         # "return" tüket
    node = Node(NodeType.RETURN, return_tok)
    
    # İsteğe bağlı expression
    if not self.match(";"):
        node.add(self._parse_expression())
    
    self.expect(";")
    
    return node
```

**Adım 4: _parse_statement'a entegrasyon**

```python
def _parse_statement(self) -> Node:
    if self.match("return"):
        return self._parse_return()
    
    if self.match("while"):
        return self._parse_while()
    
    node = Node(NodeType.STATEMENT)
    node.add(self._parse_expression())
    self.expect(";")
    return node
```

**Adım 5: Test**

```python
cases = [
    ("Yapı döndür", "return 42;"),
    ("Boş döndür", "return;"),
]
```

---

### 4.7 Üye Erişimi `a.b` Ekleme

**Amaç:** `a.field` parse etmek (postfix operatör)

**Challenge:** `.` zaten binary operator olarak geçiyor. Doğru parse etmek için  
**postfix zinciri** oluşturmalısın.

**Adım 1: NodeType ekleme**

```python
class NodeType(Enum):
    # ...
    MEMBER_ACCESS = auto()
```

**Adım 2: Grammer ekleme**

```bnf
Unary = [ UnaryOp ] Postfix
Postfix = Term { PostfixOp }
PostfixOp = "." T_IDENTIFIER       (* üye erişimi *)
         | "[" Expression "]"      (* indeks *)
         | "(" [ ArgumentList ] ")" (* metod çağrısı *)
```

**Adım 3: Parse metotları yazma**

```python
def _parse_postfix(self, base: Node) -> Node:
    """Postfix operatörleri işle: . [ ("""
    while True:
        if self.match("."):
            self.advance()              # "." tüket
            field_tok = self.current()
            if not field_tok or field_tok.type != TokenType.LITERAL_IDEN:
                raise ParseError("Üye ismi beklendi", field_tok)
            self.advance()
            
            node = Node(NodeType.MEMBER_ACCESS, field_tok)
            node.add(base)
            base = node
        
        elif self.match("["):
            # İndeks: a[i]
            self.advance()              # "[" tüket
            index_expr = self._parse_expression()
            self.expect("]")
            
            node = Node(NodeType.INDEX_ACCESS)
            node.add(base).add(index_expr)
            base = node
        
        else:
            break
    
    return base
```

**Adım 4: _parse_unary'de kullanım**

```python
def _parse_unary(self) -> Node:
    if self._is_unary_operator():
        op_node = self._parse_operator()
        term = self._parse_term()
        term = self._parse_postfix(term)    # ← Postfix döngüsü
        node = Node(NodeType.UNARY_OP)
        node.add(op_node).add(term)
        return node
    
    base = self._parse_term()
    return self._parse_postfix(base)        # ← Postfix döngüsü
```

**Adım 5: Test**

```python
cases = [
    ("Üye erişimi", "r = obj.field;"),
    ("Zincir erişim", "r = a.b.c;"),
    ("İndeks sonrası üye", "r = arr[0].field;"),
    ("Karma postfix", "r = matrix[i].get(j);"),
]
```

---

## 5. Operatör Önceliği ve Çağrışımlılık

### 5.1 Mevcut Öncelik Hiyerarşisi

Parser'da mevcut hiyerarşi (metot çağrı sırası):

```
_parse_expression
  ↓
_parse_assign           ← Seviye 1: = (sağ-çağrışımlı)
  ↓
_parse_typebind         ← Seviye 2: : (sağ-çağrışımlı, tip dili)
  ↓
_parse_binary           ← Seviye 3: + - * / % == != < > ...
  ↓
_parse_unary            ← Seviye 4: - ! ~ ...
  ↓
_parse_term             ← Seviye 5: () {} literal
  ↓
_parse_literal
```

**Not:** Daha aşağı = daha yüksek öncelik (daha sıkı bağlanma)

### 5.2 Öncelik Değiştirme

### Senaryo: `*` ve `+` farklı önceliğe sahip olmalı

Mevcut parser'da **tüm binary operatörler** aynı seviyede.

**Çözüm:** Binary katmanları böl:

```python
def _parse_binary(self) -> Node:
    """Binary = Additive"""
    return self._parse_additive()

def _parse_additive(self) -> Node:
    """Additive = Multiplicative { ("+" | "-") Multiplicative }"""
    left = self._parse_multiplicative()
    while self.match("+", "-"):
        op_node = self._parse_operator()
        right = self._parse_multiplicative()
        node = Node(NodeType.BINARY_OP)
        node.add(left).add(op_node).add(right)
        left = node
    return left

def _parse_multiplicative(self) -> Node:
    """Multiplicative = Unary { ("*" | "/" | "%") Unary }"""
    left = self._parse_unary()
    while self.match("*", "/", "%"):
        op_node = self._parse_operator()
        right = self._parse_unary()
        node = Node(NodeType.BINARY_OP)
        node.add(left).add(op_node).add(right)
        left = node
    return left
```

**Sonuç:**

```
2 + 3 * 4  →  BINARY(2, +, BINARY(3, *, 4))
             (2 + (3 * 4)) = 14  ✓
```

### 5.3 Yeni Katman Ekleme

**Senaryo:** Üs alma `**` operatörü, sağ-çağrışımlı, en yüksek öncelik

**Adım 1:** Katman oluştur

```python
def _parse_binary(self) -> Node:
    return self._parse_additive()

def _parse_additive(self) -> Node:
    # ... + -

def _parse_multiplicative(self) -> Node:
    # ... * / %
    left = self._parse_power()  # ← Yeni katman
    while self.match("*", "/", "%"):
        ...

def _parse_power(self) -> Node:
    """Power = Unary { "**" Power }    ← Sağ-çağrışımlı"""
    left = self._parse_unary()
    if self.match("**"):
        op_node = self._parse_operator()
        right = self._parse_power()  # ← Sağ-çağrışımlı für recursively çağır
        node = Node(NodeType.BINARY_OP)
        node.add(left).add(op_node).add(right)
        return node
    return left
```

**Sonuç:**

```
2 ** 3 ** 2  →  BINARY(2, **, BINARY(3, **, 2))
             (2 ** (3 ** 2)) = 512  ✓ (sağ-çağrışımlı)
```

---

## 6. Debugging ve Test Etme

### 6.1 AST Yazdırma

`Node.__repr__()` otomatik indent yapıcı ağaç gösterir:

```python
from lexer import lexer
from parser import Parser

src = "a = (b + 1) * 2;"
tokens = lexer(src)
parser = Parser(tokens)
ast = parser.parse()
print(ast)
```

**Çıktı:**
```
[PROGRAM]
  [STATEMENT]
    [ASSIGN] '='
      [IDENTIFIER] 'a'
      [BINARY_OP]
        [BINARY_OP]
          [IDENTIFIER] 'b'
          [OPERATOR] '+'
          [LITERAL] '1'
        [OPERATOR] '*'
        [LITERAL] '2'
```

### 6.2 Test Case'ler Yazma

Mevcut test yapısını genişlet:

```python
if __name__ == "__main__":
    test_cases = [
        ("Basit atama", "x = 5;", should_parse=True),
        ("Binary op", "a + b * c;", should_parse=True),
        ("Fonk çağrısı", "print(42);", should_parse=True),
        ("Eksik parantez", "print(42;", should_parse=False),
    ]
    
    for label, src, should_parse in test_cases:
        print(f"\nTest: {label}")
        print(f"  Kaynak: {src!r}")
        
        try:
            tokens = lexer(src)
            if isinstance(tokens, dict):
                print(f"  ✗ Lexer hatası: {tokens['error']}")
                assert not should_parse, f"Expected parse failure"
                continue
            
            parser = Parser(tokens)
            ast = parser.parse()
            
            if should_parse:
                print(f"  ✓ Başarılı")
                print(ast)
            else:
                print(f"  ✗ Parse başarısız olmalıydı ama oldu")
        
        except Exception as e:
            if not should_parse:
                print(f"  ✓ Beklenen hata: {e}")
            else:
                print(f"  ✗ Hata: {e}")
                raise
```

### 6.3 Yaygın Hatalar

| Hata | Sebebi | Çözüm |
|------|--------|-------|
| `TokenType.WS` token'ları gözüküyor | Lexer WS filtresi unutuldu | `_Token'ları filter` etme `parser.__init__` içinde kontrol et |
| Infinite loop | `self.advance()` untölmedi | `while` döngüsünde token tüketme |
| AST'de boş children | `node.add()` unutuldu | Tüm alt kuralları ekle |
| `peek(offset)` out of bounds | Boundary check yok | `self.peek(n) is None` kontrol et |
| Yanlış AST yapısı | Token sırası yanlış | Lookahead ve match() düzeltme |
| Left-recursion | Recursive descent'te yasak | `while` döngüsüne dönüştür |

**Örnek Debug:**

```python
def _parse_something(self) -> Node:
    print(f"DEBUG: _parse_something başladı")
    print(f"  current token: {self.current()}")
    print(f"  peek(1): {self.peek(1)}")
    # ...
```

---

## 7. Workflow Şablonu

### 7.1 Hızlı Referans Checklist

Yeni özellik eklemeye başlamadan önce:

- [ ] **Gramer yazıldı** (Radian.ebnf veya Grammer.md)
- [ ] **NodeType eklendi** (parser.py)
- [ ] **Parse metodu yazıldı** (_parse_*)
- [ ] **Entegrasyon yapıldı** (lookahead + üst kural çağrısı)
- [ ] **Test case'ler yazıldı** (__main__)
- [ ] **AST doğrulandı** (correct structure)
- [ ] **Özel durumlar test edildi** (empty, nested, invalid)
- [ ] **Hata mesajları anlaşılır** (ParseError)
- [ ] **Grammer.md güncelandi** (Node/Metot referans)
- [ ] **Documentation yazıldı** (_parse_ docstring)

### 7.2 Örnek Senaryo

**Görev:** Array literal `[1, 2, 3]` parser'a eklemek

#### **Adım 1: Gramer**

```bnf
Term = ...
     | Array

Array = "[" [ ExpressionList ] "]"
ExpressionList = Expression { "," Expression }
```

#### **Adım 2: NodeType**

```python
class NodeType(Enum):
    # ...
    ARRAY = auto()  # Array literal
```

#### **Adım 3: Parse Metodu**

```python
def _parse_array(self) -> Node:
    """
    Array = "[" [ ExpressionList ] "]"
    """
    self.expect("[")
    node = Node(NodeType.ARRAY)
    
    if not self.match("]"):
        node.add(self._parse_expression())
        while self.match(","):
            self.advance()              # "," tüket
            node.add(self._parse_expression())
    
    self.expect("]")
    return node
```

#### **Adım 4: Entegrasyon**

```python
def _parse_term(self) -> Node:
    if self.match("["):
        return self._parse_array()
    
    # ... diğer term'ler
```

#### **Adım 5: Test**

```python
cases = [
    ("Boş array", "a = [];"),
    ("Sayı array", "a = [1, 2, 3];"),
    ("Karışık array", "a = [x, 42, y + z];"),
    ("İç içe array", "a = [[1, 2], [3, 4]];"),
]

for label, src in cases:
    print(f"\n{label}: {src}")
    tokens = lexer(src)
    parser = Parser(tokens)
    ast = parser.parse()
    print(ast)
```

---

## Özet

Parser güncellemeleri **sistematik** ve **planlanmış** yapılmalıdır:

1. **Gramer** tanımla
2. **NodeType** ekle
3. **Parse metodu** yaz
4. **Entegrasyon** yap (lookahead + üst kural)
5. **Test** et (test case'ler + AST doğrulama)
6. **Dokument** güncelle

Ek kaynaklar:
- [Grammer.md](Grammer.md) — Detaylı gramer referans
- [Radian.ebnf](Radian.ebnf) — Canonical BNF tanımı
- [parser.py](parser.py) — Tam implementasyon
- [lexer.py](lexer.py) — Token üretimi
