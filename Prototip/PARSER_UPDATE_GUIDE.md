# Parser Güncelleme Rehberi — Radian Language

> **Versiyon:** 2.0
> **Durum:** Aktif geliştirme
> Bu belge Radian'a yeni dil özelliği ekleme, hata düzeltme ve yapıyı
> genişletme konusunda adım adım rehberlik sağlar.
>
> Örnekler mevcut koda karşı yazılmıştır (`lexer.py` / `parser.py` /
> `interpreter.py`). `radian` etiketli kod blokları `tests/test_docs.py`
> tarafından gerçekten çalıştırılır.

---

## İçindekiler

1. [Mimari](#1-mimari)
   - 1.1 [Boru hattı](#11-boru-hattı)
   - 1.2 [Recursive descent](#12-recursive-descent)
   - 1.3 [Bileşenler](#13-bileşenler)
2. [Temel kavramlar](#2-temel-kavramlar)
   - 2.1 [Node](#21-node)
   - 2.2 [NodeType](#22-nodetype)
   - 2.3 [Hata yönetimi](#23-hata-yönetimi)
3. [Değişiklik ekleme süreci](#3-değişiklik-ekleme-süreci)
   - 3.1 [6 adımlı yaklaşım](#31-6-adımlı-yaklaşım)
   - 3.2 [Gramer kuralını belirleme](#32-gramer-kuralını-belirleme)
   - 3.3 [Parse metodu yazma](#33-parse-metodu-yazma)
   - 3.4 [Yorumlayıcıya bağlama](#34-yorumlayıcıya-bağlama)
   - 3.5 [Test yazma](#35-test-yazma)
4. [Yaygın görevler](#4-yaygın-görevler)
   - 4.1 [Yeni binary operatör](#41-yeni-binary-operatör)
   - 4.2 [Yeni unary operatör](#42-yeni-unary-operatör)
   - 4.3 [Yeni yerleşik fonksiyon / metot](#43-yeni-yerleşik-fonksiyon--metot)
   - 4.4 [Yeni postfix biçimi](#44-yeni-postfix-biçimi)
   - 4.5 [Yeni statement / ifade biçimi](#45-yeni-statement--ifade-biçimi)
   - 4.6 [Tip diline ekleme](#46-tip-diline-ekleme)
5. [Operatör önceliği](#5-operatör-önceliği)
   - 5.1 [Mevcut hiyerarşi](#51-mevcut-hiyerarşi)
   - 5.2 [Öncelik değiştirme](#52-öncelik-değiştirme)
   - 5.3 [Çağrışımlılık](#53-çağrışımlılık)
6. [Debugging ve test](#6-debugging-ve-test)
   - 6.1 [AST ve token yazdırma](#61-ast-ve-token-yazdırma)
   - 6.2 [Test yazma biçimi](#62-test-yazma-biçimi)
   - 6.3 [Yaygın hatalar](#63-yaygın-hatalar)
7. [Workflow şablonu](#7-workflow-şablonu)
   - 7.1 [Checklist](#71-checklist)
   - 7.2 [Uçtan uca örnek senaryo](#72-uçtan-uca-örnek-senaryo)

---

## 1. Mimari

### 1.1 Boru hattı

```
┌─────────────────────────────────────────────────┐
│  LEXER (lexer.py)                               │
│  Giriş : kaynak kod dizesi                      │
│  Çıkış : list[Token]  ya da  hata sözlüğü       │
│  Yorumları atar; symbols.txt'i okur             │
└─────────────────────────┬───────────────────────┘
                          ▼
┌─────────────────────────────────────────────────┐
│  PARSER (parser.py)                             │
│  ├─ NodeType   (AST düğüm tipleri)              │
│  ├─ Node       (AST düğüm sınıfı)               │
│  ├─ Parser     (recursive descent)              │
│  └─ ParseError (konumlu hata)                   │
│  Giriş : list[Token]     Çıkış : AST            │
└─────────────────────────┬───────────────────────┘
                          ▼
┌─────────────────────────────────────────────────┐
│  YORUMLAYICI (interpreter.py)                   │
│  ├─ Environment (kapsam zinciri)                │
│  ├─ _DISPATCH   (NodeType → değerlendirici)     │
│  └─ RadianError (konumlu çalışma zamanı hatası) │
│  Giriş : AST             Çıkış : değer + etki   │
└─────────────────────────┬───────────────────────┘
                          ▼
┌─────────────────────────────────────────────────┐
│  CLI / REPL (radian.py)                         │
│  STATİK TİP DENETLEYİCİ, KOD ÜRETİMİ (gelecek)  │
└─────────────────────────────────────────────────┘
```

`parse_source(kaynak)` lexer + parser adımlarını birleştirir ve sözcüksel
hatayı da `ParseError` olarak yükseltir — yeni araç yazarken bunu kullan.

### 1.2 Recursive descent

Her gramer kuralına bir metot karşılık gelir:

```
Gramer kuralı          →  Parser metodu
─────────────────         ───────────────
Statement              →  _parse_statement()
Expression             →  _parse_expression()
Assign                 →  _parse_assign()
TypeBind               →  _parse_typebind()
Binary(n)              →  _parse_binary(level)
Unary                  →  _parse_unary()
Term                   →  _parse_term()      (postfix zinciri)
Primary                →  _parse_primary()
Literal                →  _parse_literal()
```

**Çalışma prensibi:**

1. Mevcut token'a bak — `self.current()`
2. Gerekiyorsa ileri bak — `self.peek(n)`
3. Token tüket — `self.advance()`
4. Zorunlu token'ı doğrula — `self.expect(değer)`
5. Alt kuralı çağır — yukarıdan aşağı inme
6. Sol-çağrışım için `while`, sağ-çağrışım için özyineleme

```python
def _parse_assign(self) -> Node:
    left = self._parse_typebind()                # alt kural
    tok  = self.current()
    if tok is not None and tok.value in ASSIGN_OPS:
        op_tok = self.advance()                  # "=" / "+=" …
        right  = self._parse_assign()            # sağ-çağrışımlı
        node   = Node(NodeType.ASSIGN, op_tok)
        node.add(left).add(right)
        return node
    return left
```

> **Sol özyineleme yasak.** `Binary = Binary op Unary` yazarsan parser
> sonsuz döngüye girer. Sol-çağrışımı `while` ile kur.

### 1.3 Bileşenler

| Bileşen | Dosya | Açıklama |
|---------|-------|----------|
| `lexer()` | `lexer.py` | Kaynağı token'lara ayırır; hata → `dict` |
| `Token` | `lexer.py` | Tür, değer, satır, sütun |
| `Node` | `parser.py` | AST düğümü: tip, value token'ı, çocuklar |
| `NodeType` | `parser.py` | Düğüm tipleri enum'u |
| `Parser` | `parser.py` | `_parse_*` metotları |
| `ParseError` | `parser.py` | `"{mesaj} [satır:sütun]"` |
| `parse_source()` | `parser.py` | lexer + parser tek adımda |
| `Interpreter` | `interpreter.py` | `eval(node, env)` + `_DISPATCH` |
| `Environment` | `interpreter.py` | Kapsam zinciri (değerler + tipler) |
| `RadianError` | `interpreter.py` | Konumlu çalışma zamanı hatası |

---

## 2. Temel kavramlar

### 2.1 Node

```python
class Node:
    type: NodeType             # düğüm türü
    value: Token | None        # ilgili token (operatör, isim, anahtar sözcük)
    children: list[Node]       # alt düğümler
```

`value` alanı **her zaman bir Token'dır**, ham string değil — konum bilgisi
hata mesajlarında kullanılır.

```
Kaynak: a = 5 + 3;

AST:
  STATEMENT
    └─ ASSIGN (value='=')
       ├─ IDENTIFIER (value='a')
       └─ BINARY_OP                 ← value yok
          ├─ LITERAL  (value='5')
          ├─ OPERATOR (value='+')   ← operatör ayrı bir çocuk
          └─ LITERAL  (value='3')
```

> Dikkat: `BINARY_OP` operatörü `value`'da değil, **ortadaki çocukta**
> tutar (`children = [sol, OPERATOR, sağ]`). `UNARY_OP` da aynı biçimde
> `[OPERATOR, işlenen]` tutar.

Tam liste için `Grammer.md` §6 (Node Tipi Referansı).

### 2.2 NodeType

Yeni bir kural eklerken ilk adım enum'a değer eklemektir:

```python
class NodeType(Enum):
    # … mevcut tipler
    MEMBER   = auto()  # value = üye adı, children = [nesne]   →  a.b
    INDEX    = auto()  # children = [nesne, indeks]            →  a[i]
    FOR      = auto()  # value = döngü değişkeni, children = [dizi, gövde]
```

**Adlandırma:** değer üreten düğümlerde `_EXPR`, operasyonlarda `_OP`,
yapısal düğümlerde son ek yok.

### 2.3 Hata yönetimi

```python
raise ParseError("'(' beklendi", self.current())
# → ParseError: '(' beklendi [5:12]
```

- `self.expect("(")` zaten bu hatayı üretir; elle yazmaya çoğu kez gerek yok.
- Token'ı **mutlaka** geçir: konumsuz hata mesajı kullanıcıya yardımcı olmaz.
- Dosya sonunda `self.current()` `None` döner; mesajı buna göre yaz.

Çalışma zamanı tarafında karşılığı `RadianError(msg, node)`'dur; konumu
düğümden (ya da ilk token taşıyan çocuğundan) kendisi çıkarır.

---

## 3. Değişiklik ekleme süreci

### 3.1 6 adımlı yaklaşım

```
1. GRAMER      →  Radian.ebnf + Grammer.md güncelle
2. NODETYPE    →  parser.py: NodeType'a değer ekle
3. PARSE       →  _parse_* metodunu yaz
4. ENTEGRE     →  üst kuraldan lookahead ile çağır (+ KEYWORDS)
5. YORUMLA     →  interpreter.py: _eval_* + _DISPATCH girdisi
6. TEST        →  tests/ altına test ekle, run_tests.py yeşil olsun
```

Adım 1 atlanırsa belge ile kod ayrışır — bu depoda bir kez yaşandı
(fonksiyon çağrısı "tamamlandı" yazıyordu ama kodda yoktu). Adım 6
atlanırsa aynı şey testler için geçerli olur.

### 3.2 Gramer kuralını belirleme

Önce **hangi katmana** ait olduğuna karar ver:

| Yeni özellik | Katman | Nereye bağlanır |
|--------------|--------|-----------------|
| Operatör | Binary / Unary | `BINARY_LEVELS` / `UNARY_OPS` |
| `f(x)`, `a.b`, `a[i]` | Postfix | `_parse_term` döngüsü |
| `[1,2]`, `if`, `while` | Primary | `_parse_primary` |
| `return`, `break` | Statement | `_parse_statement` |
| `[T]`, `T?` | Tip dili | `_parse_tuple_type_expr` |

Sonra kuralı EBNF olarak yaz ve **belirsizlik** olup olmadığına bak:

```
(* Belirsiz: "a { … }" hem çağrı hem fonksiyon tanımı olabilir mi? *)
FuncDef = T_IDENTIFIER [ FuncSignature ] Block
```

Belirsizliği lookahead ile çöz — `_is_funcdef_ahead()` bunu yapar:
`IDENT {` fonksiyon tanımıdır; `IDENT ( … )` yalnızca ardından `->`
geliyorsa tanımdır, aksi halde çağrıdır.

### 3.3 Parse metodu yazma

İskelet:

```python
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
    node.add(self._parse_expression())               # gezilecek dizi
    node.add(self._parse_block())                    # gövde
    return node
```

Kurallar:

- Metodun üstüne kuralı EBNF olarak yaz (mevcut biçimi koru).
- Anahtar sözcüğü `KEYWORDS` kümesine ekle, yoksa değişken adı olarak da
  kullanılabilir kalır ve gramer belirsizleşir.
- Çocukların **sırası sözleşmedir**; yorumlayıcı buna göre okur.
- Konum bilgisi için düğüme anlamlı bir token ver (`value`).

### 3.4 Yorumlayıcıya bağlama

Parser bir düğüm üretiyorsa yorumlayıcı onu tanımalıdır, yoksa
"Yorumlanamayan düğüm tipi" hatası alırsın.

```python
def _eval_for(self, node: Node, env: Environment):
    iterable = self.eval(node.children[0], env)
    body     = node.children[1]
    var_name = node.value.value
    ...

# Sınıf tanımından sonra:
Interpreter._DISPATCH = {
    ...
    NodeType.FOR: Interpreter._eval_for,
}
```

Değer üretmeyen ifadelerde `UNIT` döndür — `None` **döndürme**.

### 3.5 Test yazma

Testler `tests/` altındadır ve stdlib `unittest` kullanır:

| Modül | Kapsam |
|-------|--------|
| `test_lexer.py` | token'lar, sayısal biçimler, yorumlar, hata konumları |
| `test_parser.py` | AST biçimi, öncelik, hata durumları |
| `test_interpreter.py` | değerlendirme, kapsam, tip denetimi, yerleşikler |
| `test_examples.py` | `examples/*.rad` + CLI (alt süreçle) |
| `test_docs.py` | belgelerdeki ` ```radian ` blokları |

```bash
python3 run_tests.py              # hepsi
python3 run_tests.py test_parser  # tek modül
python3 run_tests.py -v           # ayrıntılı
```

`parser.py` ve `lexer.py` içindeki `__main__` blokları **demo**'dur, test
değildir; yeni davranış için mutlaka `tests/` altına assert yaz.

---

## 4. Yaygın görevler

### 4.1 Yeni binary operatör

Örnek: `//` tamsayı bölmesi eklemek *(varsayımsal — `//` şu an yorum işareti)*.

**Adım 1 — sembolü tanıt.** Çok karakterliyse `symbols.txt`'e bir satır ekle;
tek karakterliyse `SYMBOL_CHARS`'ta zaten vardır. Lexer kodu değişmez.

```
# symbols.txt
<=>
```

**Adım 2 — öncelik.** Hiçbir şey yapmazsan operatör **katman 0**'a düşer
(en düşük binary öncelik). Özel öncelik istiyorsan `BINARY_LEVELS`'a ekle:

```python
BINARY_LEVELS: list[set[str]] = [
    {"||"},
    {"&&"},
    ...
    {"*", "/", "%"},        # ← buraya ekle
    {"**"},
]
```

**Adım 3 — anlam.** `interpreter.py: _binary_values` içine davranışı yaz:

```python
if op == "<=>":
    if not (_is_number(left) and _is_number(right)):
        raise RadianError(f"'{op}' sayı bekler", node)
    return (left > right) - (left < right)
```

**Adım 4 — test.** Parser tarafında öncelik, yorumlayıcı tarafında sonuç:

```python
def test_karsilastirma_operatoru(self):
    self.assertEqual(run("2 <=> 1;"), 1)
```

`_parse_binary`, `_parse_operator` ya da `_is_operator_start` metotlarına
**dokunmak gerekmez**.

### 4.2 Yeni unary operatör

`UNARY_OPS` kümesine ekle ve `_eval_unary`'ye dalı yaz:

```python
UNARY_OPS = {"-", "+", "!", "~"}          # parser.py
```

```python
if op == "?":                              # interpreter.py: _eval_unary
    return value is not UNIT
```

`UNARY_OPS` üyeleri yalnızca **önek** konumundadır. Sonek biçimi istiyorsan
bu bir postfix eklentisidir → §4.4; çalışılmış örneği `++` / `--`'dır
(`PRE_OP` ve `POST_OP` düğümleri).

### 4.3 Yeni yerleşik fonksiyon / metot

Gramer değişikliği gerekmez; yalnızca `interpreter.py`.

**Genel fonksiyon:**

```python
def _bi_clamp(interp, args, node):
    value, low, high = args
    for a in args:
        if not _is_number(a):
            raise RadianError("clamp() sayı bekler", node)
    return min(max(value, low), high)

_BUILTIN_SPECS = [
    ...
    ("clamp", _bi_clamp, 3),               # arite: int, (min,max) ya da None
]
```

**Metot** (bir değere `.` ile bağlanan):

```python
def _m_array_first(interp, xs, args, node):
    if not xs:
        raise RadianError("first(): dizi boş", node)
    return xs[0]

ARRAY_METHODS = dict([
    ...
    _method("first", 0)(_m_array_first),
])
```

Metot imzası `(interp, alıcı, args, node)`; yerleşik imzası
`(interp, args, node)`. Arite denetimi `_check_arity` tarafından yapılır.

### 4.4 Yeni postfix biçimi

Çağrı / üye erişimi / indeksleme `_parse_term` içindeki tek bir döngüde
zincirlenir. Yeni bir sonek eklemek bu döngüye bir dal eklemektir:

```python
def _parse_term(self) -> Node:
    node = self._parse_primary()
    while True:
        if self.match("("):
            node = self._parse_call(node)
        elif self.match("."):
            node = self._parse_member(node)
        elif self.match("["):
            node = self._parse_index(node)
        elif self.match("?"):                     # ← yeni sonek
            node = self._parse_optional(node)
        else:
            break
    return node
```

Sonek metodu **her zaman sol taraftaki düğümü parametre alır** ve onu
yeni düğümün çocuğu yapar; zincir böylece soldan sağa kurulur. `++` / `--`
bu kalıbın çalışan örneğidir: `_parse_term` içinde `POST_OP` üretilir,
`_parse_unary` içinde `PRE_OP`, ve hedefin lvalue olduğu `_require_lvalue`
ile parse zamanında doğrulanır.

```radian
// a.b[0](x) zinciri: MEMBER → INDEX → CALL
kutu = ["yok", "var"];
assert(kutu.slice(1)[0] == "var");
```

### 4.5 Yeni statement / ifade biçimi

Örnek: `do { … } while c;` eklemek.

```python
# 1. NodeType
DO_WHILE = auto()

# 2. KEYWORDS'e "do" ekle

# 3. Parse metodu
def _parse_do_while(self) -> Node:
    tok  = self.advance()                    # "do"
    node = Node(NodeType.DO_WHILE, tok)
    node.add(self._parse_block())            # gövde
    if not self.match_keyword("while"):
        raise ParseError("'while' beklendi", self.current())
    self.advance()
    node.add(self._parse_expression())       # koşul
    return node

# 4. Entegrasyon — ifade olacaksa _parse_primary, statement olacaksa
#    _parse_statement içinde anahtar sözcük kontrolü:
if self.match_keyword("do"):
    return self._parse_do_while()

# 5. Yorumlayıcı
def _eval_do_while(self, node, env):
    body, cond_node = node.children
    result = UNIT
    while True:
        try:
            result = self.eval(body, env)
        except BreakSignal:
            break
        except ContinueSignal:
            pass
        cond = self.eval(cond_node, env)
        self._require_bool(cond, "do-while", node)
        if not cond:
            break
    return result
```

Gövdesi blokla biten bir ifade eklediysen `BLOCK_TAILED` kümesine de ekle;
böylece sonundaki `;` opsiyonel olur.

### 4.6 Tip diline ekleme

Tip dili expression'dan bağımsızdır; giriş noktaları `_parse_type_expr` ve
`_parse_tuple_type_expr`'dir. Örnek: opsiyonel tip `T?`.

```python
def _parse_type_expr(self) -> Node:
    left = self._parse_tuple_type_expr()

    if self.match("?"):                       # ← yeni: T?
        tok  = self.advance()
        node = Node(NodeType.OPTIONAL_TYPE, tok)
        node.add(left)
        left = node

    if self.match("->"):
        ...
```

Yeni tip biçimi eklendiğinde `interpreter.py`'deki üç yeri de güncelle:
`check_type` (doğrulama), `type_repr` (hata mesajı) ve `zero_value`
(değersiz bildirimin başlangıç değeri).

---

## 5. Operatör önceliği

### 5.1 Mevcut hiyerarşi

```
_parse_expression
└─ _parse_assign        =  +=  -=  …        sağ-çağrışımlı, lvalue
   └─ _parse_typebind   :                   sağ-çağrışımlı, sağı TypeExpr
      └─ _parse_binary(0..10)               tablo güdümlü
         └─ _parse_unary    -  +  !  ~      önek
            └─ _parse_term  f(x)  a.b  a[i] postfix zinciri
               └─ _parse_primary            ()  {}  []  if/while/for  literal
```

Binary katmanları (`BINARY_LEVELS`, index 0 = en düşük):

| Katman | Operatörler |
|--------|-------------|
| 0 | `\|\|` *(+ tabloda olmayan tüm semboller)* |
| 1 | `&&` |
| 2 | `\|` |
| 3 | `^` |
| 4 | `&` |
| 5 | `==` `!=` |
| 6 | `<` `>` `<=` `>=` |
| 7 | `<<` `>>` |
| 8 | `+` `-` |
| 9 | `*` `/` `%` |
| 10 | `**` *(sağ-çağrışımlı)* |

Katmanlı çözüm tek bir özyinelemeli metotla sağlanır:

```python
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
```

### 5.2 Öncelik değiştirme

Tabloyu düzenlemek yeterlidir; metot değişmez.

```radian
// Mevcut davranış: * , + 'dan önce bağlar
assert(1 + 2 * 3 == 7);

// Karşılaştırma aritmetikten sonra bağlar
assert((1 + 1 < 3) == true);

// ** sağ-çağrışımlı
assert(2 ** 3 ** 2 == 512);
```

Yeni bir katman **araya** eklemek istiyorsan listenin uygun yerine bir küme
ekle: `RIGHT_ASSOC_LEVELS` index tabanlı olduğu için, `**` katmanının indeksi
kayarsa o kümeyi de güncelle (varsayılan tanım `{len(BINARY_LEVELS) - 1}`
olduğundan sona ekleme yapmadığın sürece kendiliğinden doğru kalır).

### 5.3 Çağrışımlılık

| İstediğin | Nasıl |
|-----------|-------|
| Sol-çağrışım (`a - b - c` → `(a-b)-c`) | Varsayılan; `while` döngüsü |
| Sağ-çağrışım (`a ** b ** c` → `a**(b**c)`) | Katmanı `RIGHT_ASSOC_LEVELS`'a ekle |
| Zincirlenemez (`a < b < c` hata) | Döngü yerine tek `if` kullan (şu an yok) |

```radian
assert(10 - 3 - 2 == 5);        // sol-çağrışım
assert(2 ** 2 ** 3 == 256);     // sağ-çağrışım
```

---

## 6. Debugging ve test

### 6.1 AST ve token yazdırma

```bash
python3 radian.py --tokens -c 'x = 1 + 2;'
python3 radian.py --ast    -c 'x = 1 + 2;'
```

```python
from parser import parse_source
print(parse_source("x = 1 + 2;"))     # girintili ağaç
```

Testlerde tek satırlık s-expression daha kullanışlıdır:

```python
from tests.helpers import parse_expr, sexp

sexp(parse_expr("1 + 2 * 3;"))
# '(BINARY_OP LITERAL:1 OPERATOR:+ (BINARY_OP LITERAL:2 OPERATOR:* LITERAL:3))'
```

Yorumlayıcı tarafını hızlı denemek için REPL:

```bash
python3 radian.py
radian> [1,2,3].map(str);
["1", "2", "3"]
```

### 6.2 Test yazma biçimi

**Parser testi** — AST biçimini s-expression ile sabitlemek:

```python
class TestPrecedence(unittest.TestCase):

    def test_carpma_toplamadan_once_baglar(self):
        self.assertEqual(
            sexp(parse_expr("1 + 2 * 3;")),
            "(BINARY_OP LITERAL:1 OPERATOR:+ "
            "(BINARY_OP LITERAL:2 OPERATOR:* LITERAL:3))")
```

**Yorumlayıcı testi** — sonucu ya da çıktıyı doğrulamak:

```python
def test_for_dongusu(self):
    self.assertEqual(run("t = 0; for x in [1, 2, 3] { t += x; } t;"), 6)

def test_print(self):
    self.assertEqual(output('print("a", 1, true);'), "a 1 true\n")
```

**Hata testi** — hatanın *türü* ve mesaj parçası:

```python
def test_sinir_disi_indeks(self):
    with self.assertRaises(RadianError) as ctx:
        run("xs = [1]; xs[5];")
    self.assertIn("sınır dışı", str(ctx.exception))
```

Yeni bir `examples/*.rad` eklediysen `tests/test_examples.py` içindeki
`EXAMPLES` listesine de ekle — bir test iki kümenin eşit olmasını zorunlu kılar.

### 6.3 Yaygın hatalar

| Belirti | Olası neden |
|---------|-------------|
| Sonsuz döngü / `RecursionError` | Sol özyineleme ya da token tüketmeyen bir dal |
| "Beklenmeyen token" | `_parse_primary` yeni biçimi tanımıyor |
| Anahtar sözcük değişken gibi davranıyor | `KEYWORDS` kümesine eklenmemiş |
| "Yorumlanamayan düğüm tipi" | `_DISPATCH` girdisi eksik |
| Yanlış öncelik | Operatör `BINARY_LEVELS`'ta yok → katman 0'a düşmüş |
| `a + -b` yanlış çözümleniyor | Operatör birleştirme geri gelmiş (olmamalı) |
| Çağrı fonksiyon tanımı sanılıyor | `_is_funcdef_ahead` lookahead'i bozulmuş |
| Test yeşil ama örnek bozuk | Belge bloku ` ```radian ` etiketli değil |

Parse ederken token tüketmeyen bir dal yazdıysan döngü ilerlemez; her
`_parse_*` metodunun **en az bir token tükettiğinden** emin ol.

---

## 7. Workflow şablonu

### 7.1 Checklist

```
[ ] 1. Radian.ebnf'e kuralı ekle
[ ] 2. Grammer.md'yi güncelle (gramer + node tablosu + metot haritası)
[ ] 3. parser.py: NodeType değeri
[ ] 4. parser.py: _parse_* metodu (üstünde EBNF yorumu)
[ ] 5. parser.py: üst kuraldan çağrı (+ KEYWORDS / BLOCK_TAILED)
[ ] 6. interpreter.py: _eval_* + _DISPATCH girdisi
[ ] 7. tests/: parser + yorumlayıcı testleri
[ ] 8. Gerekiyorsa examples/ + test_examples.py girdisi
[ ] 9. python3 run_tests.py  →  yeşil
[ ] 10. PROGRESS.md'yi güncelle
```

### 7.2 Uçtan uca örnek senaryo

**Hedef:** `unless c { … }` — koşul yanlışsa gövdeyi çalıştıran ifade.

**Adım 1 — Gramer** (`Radian.ebnf`):

```
UnlessExpr = "unless" Expression Block
```

**Adım 2 — NodeType** (`parser.py`):

```python
UNLESS = auto()   # children = [koşul, gövde]
```

**Adım 3 — Anahtar sözcük:**

```python
KEYWORDS = {..., "unless"}
BLOCK_TAILED = {..., NodeType.UNLESS}
```

**Adım 4 — Parse metodu:**

```python
# ------------------------------------------------------------------
# UnlessExpr = "unless" Expression Block
# ------------------------------------------------------------------

def _parse_unless(self) -> Node:
    tok  = self.advance()                    # "unless"
    node = Node(NodeType.UNLESS, tok)
    node.add(self._parse_expression())       # koşul
    node.add(self._parse_block())            # gövde
    return node
```

**Adım 5 — Entegrasyon** (`_parse_primary` içinde):

```python
if self.match_keyword("unless"):
    return self._parse_unless()
```

**Adım 6 — Yorumlayıcı:**

```python
def _eval_unless(self, node: Node, env: Environment):
    cond = self.eval(node.children[0], env)
    self._require_bool(cond, "unless", node)
    return UNIT if cond else self.eval(node.children[1], env)

# _DISPATCH tablosuna:  NodeType.UNLESS: Interpreter._eval_unless,
```

**Adım 7 — Testler:**

```python
# tests/test_parser.py
def test_unless(self):
    node = parse_expr("unless x { 1; }")
    self.assertEqual(node.type, NodeType.UNLESS)
    self.assertEqual(len(node.children), 2)

# tests/test_interpreter.py
def test_unless_kosul_yanlissa_calisir(self):
    self.assertEqual(run("unless false { 42; }"), 42)
    self.assertIs(run("unless true { 42; }"), UNIT)
```

**Adım 8 — Belge:** `Grammer.md` §3.7'ye satır ekle, çalışan bir örnek
bloku ` ```radian ` ile etiketle.

**Adım 9:** `python3 run_tests.py` → yeşil.

**Adım 10:** `PROGRESS.md`'de maddeyi `[x]` yap, tasarım kararını not düş.

---

## Özet

- Her gramer kuralı bir `_parse_*` metodu, her düğüm tipi bir `_eval_*`.
- Sol özyineleme yok; sol-çağrışım `while`, sağ-çağrışım özyineleme.
- Operatör eklemek çoğu zaman yalnızca `symbols.txt` + tablo + yorumlayıcı
  dalı demektir; parser metotlarına dokunulmaz.
- Belirsizlikleri lookahead ile çöz, sezgiye güvenme.
- Kod ile belge birlikte güncellenir; testler ikisini de bağlar.
