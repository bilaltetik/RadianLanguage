# MyLang — Gramer Referans Dökümanı

> **Versiyon:** 0.3  
> **Durum:** Geliştirme aşamasında  
> Bu belge canonical BNF tanımını, anlamsal notları, örnekleri,  
> node tipi referansını ve genişletme rehberini içerir.

---

## İçindekiler

1. [Tam BNF Grameri](#1-tam-bnf-grameri)
2. [Öncelik Tablosu](#2-öncelik-tablosu)
3. [Anlamsal Notlar](#3-anlamsal-notlar)
   - 3.1 [Blok — Implicit Return](#31-blok--implicit-return)
   - 3.2 [= Operatörü — Atama ve lvalue](#32--operatörü--atama-ve-lvalue)
   - 3.3 [: Operatörü — Tip Bağlama ve lvalue](#33--operatörü--tip-bağlama-ve-lvalue)
   - 3.4 [Fonksiyon Tanımı Formları](#34-fonksiyon-tanımı-formları)
   - 3.5 [Tip Dili](#35-tip-dili)
   - 3.6 [Fonksiyon Çağrısı](#36-fonksiyon-çağrısı)
4. [Örnekler](#4-örnekler)
5. [Node Tipi Referansı](#5-node-tipi-referansı)
6. [Parser Metot Haritası](#6-parser-metot-haritası)
7. [Genişletme Rehberi](#7-genişletme-rehberi)
8. [Bilinen Eksikler / TODO](#8-bilinen-eksikler--todo)

---

## 1. Tam BNF Grameri

```bnf
(* ──────────── PROGRAM ──────────── *)

Program       = { TopLevel }
TopLevel      = FuncDef | Statement

(* ──────────── FONKSİYON ──────────── *)

FuncDef       = T_IDENTIFIER [ FuncSignature ] Block
FuncSignature = "(" [ TypeParamList ] ")" "->" TypeExpr

(* ──────────── BLOK ──────────── *)

Block         = "{" { Statement } "}"

(* ──────────── STATEMENT ──────────── *)

Statement     = Expression ";"

(* ──────────── İFADE HİYERARŞİSİ  (düşük → yüksek öncelik) ──────────── *)

Expression    = Assign
Assign        = TypeBind [ "=" Assign ]          (* sağ-çağrışımlı, lvalue *)
TypeBind      = Binary   [ ":" TypeExpr ]        (* sağ-çağrışımlı, lvalue *)
Binary        = Unary { Operator Unary }         (* sol-çağrışımlı *)
Unary         = [ UnaryOp ] Term
Term          = FunctionCall
              | "(" Expression ")"
              | Block
              | Literal

FunctionCall  = T_IDENTIFIER "(" [ ArgumentList ] ")"
ArgumentList  = Expression { "," Expression }

(* ──────────── TİP DİLİ ──────────── *)

TypeExpr      = TupleTypeExpr "->" TypeExpr      (* sağ-çağrışımlı *)
              | TupleTypeExpr

TupleTypeExpr = "(" [ TypeParamList ] ")"
              | T_IDENTIFIER

TypeParamList = TypeParam { "," TypeParam }
TypeParam     = T_IDENTIFIER ":" TypeExpr        (* isimli *)
              | TypeExpr                         (* isimsiz *)

(* ──────────── OPERATÖRLER ──────────── *)

Operator      = ( T_SYMBOL | T_IDENTIFIER ) { T_SYMBOL }
UnaryOp       = T_SYMBOL

(* ──────────── LİTERAL ──────────── *)

Literal       = T_STRING | T_CHAR | T_NUMBER
              | T_IDENTIFIER | T_SYMBOL
              | PrimitiveType

PrimitiveType = "i8"  | "i16" | "i32" | "i64"
              | "u8"  | "u16" | "u32" | "u64"
              | "f32" | "f64" | "bool" | "char"
```

---

## 2. Öncelik Tablosu

| Seviye | Kural | Sembol / Tetikleyici | Çağrışım | Not |
|--------|-------|----------------------|----------|-----|
| 1 (en düşük) | `Assign` | `=` | **Sağ** | lvalue döndürür |
| 2 | `TypeBind` | `:` | **Sağ** | Sağı TypeExpr |
| 3 | `Binary` | Tüm operatörler | **Sol** | `=` `:` dahil değil |
| 4 | `Unary` | `!` `-` `~` … | — | Yalnızca önek |
| 5 (en yüksek) | `Term` | `()` `{}` literal | — | Gruplama |
| — (bağımsız) | `TypeExpr` | `->` | **Sağ** | Yalnızca `:` sağında |

> `TypeExpr` expression öncelik hiyerarşisinin **dışındadır**.  
> Yalnızca `TypeBind`'ın sağında ve `FuncSignature` içinde devreye girer.

---

## 3. Anlamsal Notlar

### 3.1 Blok — Implicit Return

```
{ stmt₁; stmt₂; … stmtₙ; }
```

- **Son statement'ın değeri** blokun değeridir.
- Tüm statement'lar (son dahil) `";"` ile biter.
- Boş blok `{}` → `unit` döndürür *(semantik katmanda tanımlanacak)*.
- Blok hem fonksiyon gövdesi hem değer (Term) olarak kullanılabilir.

```
(* Fonksiyon gövdesi olarak *)
kare (x:i32) -> i32 {
    x * x;          (* implicit return — son statement *)
}

(* Değer olarak *)
sonuc = {
    a = 10;
    b = 20;
    a + b;          (* blok = 30, sonuc = 30 *)
};
```

---

### 3.2 `=` Operatörü — Atama ve lvalue

`a = b` → b'yi a'ya atar ve **a'yı** (lvalue) döndürür.

| İfade | AST | Anlam |
|-------|-----|-------|
| `a = b` | `ASSIGN(a, b)` | b'yi a'ya ata, a'yı döndür |
| `a = b = c` | `ASSIGN(a, ASSIGN(b, c))` | sağ-çağrışımlı zincir |
| `(a = b) + 2` | `BINARY(ASSIGN(a,b), +, 2)` | lvalue kullanımı |

---

### 3.3 `:` Operatörü — Tip Bağlama ve lvalue

`a : T` → a'yı T tipine bağlar ve **a'yı** (lvalue) döndürür.  
`:` sağında her zaman **TypeExpr** gelir; expression değil.

| İfade | AST | Anlam |
|-------|-----|-------|
| `b : i32` | `TYPEBIND(b, i32)` | b'yi i32'ye dönüştür |
| `a : i32 = b` | `ASSIGN(TYPEBIND(a,i32), b)` | a→i32 sabitle, b'yi ata |
| `a = b : i32` | `ASSIGN(a, TYPEBIND(b,i32))` | b→i32 yap, a'ya eşitle |
| `a : i32 = b : f64` | `ASSIGN(TYPEBIND(a,i32), TYPEBIND(b,f64))` | iki taraf dönüşüm |

---

### 3.4 Fonksiyon Tanımı Formları

Üç geçerli yazım biçimi vardır:

**Form 1 — Sadece imza** *(Statement)*
```
topla : (x:i32, y:i32) -> i32;
```

**Form 2 — Sadece gövde** *(imza ayrıca bildirilmiş)*
```
topla {
    result = x + y;
    result;
}
```

**Form 3 — Birleşik** *(tam tanım, önerilen)*
```
topla (x:i32, y:i32) -> i32 {
    result = x + y;
    result;
}
```

**Parser ayrım kuralı** (`_parse_toplevel`):

```
IDENTIFIER + "{"  →  FuncDef (Form 2)
IDENTIFIER + "("  →  FuncDef (Form 3)
diğer             →  Statement
```

---

### 3.5 Tip Dili

Tip dili, expression dilinden **tamamen bağımsız** bir katmandır.  
Yalnızca `:` sağında ve `FuncSignature` içinde devreye girer.

```
TypeExpr →  sağ-çağrışımlı "->":
  (x:i32) -> (y:i32) -> bool
  =   (x:i32) -> ((y:i32) -> bool)
```

| Tip | Örnek | Açıklama |
|-----|-------|----------|
| Primitive | `i32` `bool` `f64` | Yerleşik tipler |
| Fonksiyon | `(x:i32) -> i32` | Giriş → çıkış |
| Curried | `(x:i32) -> (y:i32) -> bool` | Zincirleme fonksiyon |
| HOF | `(f:(x:i32)->i32, v:i32) -> i32` | Fonksiyon parametreli |
| Isimsiz | `(i32, i32) -> i32` | Parametre isimsiz |

---

### 3.6 Fonksiyon Çağrısı

`f(arg1, arg2, ...)` → fonksiyon çağrısı, argümanlar virgülle ayrılmış.

| İfade | AST | Anlam |
|-------|-----|-------|
| `print(42)` | `CALL(print, 42)` | print fonksiyonunu 42 ile çağır |
| `add(1, 2, 3)` | `CALL(add, 1, 2, 3)` | Çok argümanlı çağrı |
| `apply(f, g(x))` | `CALL(apply, f, CALL(g, x))` | İç içe çağrı |

**Öneriler:**
- Argüman listesi boş olabilir: `print()` → `CALL(print)`
- Parantez içinde tam Expression işlenir, operatör önceliği korunur
- Fonksiyon ismi T_IDENTIFIER olmalı (hiçbir operatör olmaz)

---

## 4. Örnekler

```
(*
  C karşılığı:
    #include <stdio.h>
    int main() {
        printf("Hello, World!\n");
        return 0;
    }
*)
main () -> i32 {
    builtin.print("Hello, World!\n");
    0;
}

(* Temel aritmetik *)
topla (x:i32, y:i32) -> i32 {
    x + y;
}

(* Blok değer olarak *)
clamp (x:i32, lo:i32, hi:i32) -> i32 {
    result = {
        x < lo ? lo
               ? x > hi ? hi
                         ? x;
    };
    result;
}

(* lvalue zinciri *)
a = (b = 42) + 1;      (* b=42, a=43 *)

(* Çoklu tip bağlama *)
a : i32 = b : f64;     (* b→f64 dönüşümü, a→i32 sabitlendi, atama yapıldı *)

(* Curried fonksiyon tipi *)
f : (x:i32) -> (y:i32) -> bool;

(* Yüksek dereceli fonksiyon *)
apply : (f:(x:i32) -> i32, v:i32) -> i32;

(* Fonksiyon çağrısı *)
print(42);                    (* basit çağrı *)
add(1, 2, 3);                 (* çok argüman *)
apply(f, g(x));               (* iç içe çağrı *)
r = max(x, min(y, z));        (* kompleks zincir *)
```

---

## 5. Node Tipi Referansı

| NodeType | Oluşturan Kural | `value` | `children` |
|----------|----------------|---------|-----------|
| `PROGRAM` | `parse()` | — | `[TopLevel …]` |
| `STATEMENT` | `_parse_statement` | — | `[Expression]` |
| `FUNC_DEF` | `_parse_funcdef` | isim token'ı | `[FuncSignature?] [Block]` |
| `BLOCK` | `_parse_block` | — | `[Statement …]` |
| `FUNC_TYPE` | `_parse_funcsig` / `_parse_type_expr` | `->` token'ı | `[TypeParam …, RetTypeParam]` |
| `TUPLE_TYPE` | `_parse_tuple_type_expr` | — | `[TypeParam …]` |
| `TYPE_PARAM` | `_parse_type_param` | isim (varsa) | `[TypeExpr]` |
| `ASSIGN` | `_parse_assign` | `=` token'ı | `[lhs, rhs]` |
| `TYPEBIND` | `_parse_typebind` | `:` token'ı | `[lhs, TypeExpr]` |
| `BINARY_OP` | `_parse_binary` | — | `[lhs, OPERATOR, rhs]` |
| `UNARY_OP` | `_parse_unary` | — | `[OPERATOR, Term]` |
| `OPERATOR` | `_parse_operator` | operatör token'ı | — |
| `LITERAL` | `_parse_literal` | değer token'ı | — |
| `IDENTIFIER` | `_parse_literal` | isim token'ı | — |
| `CALL` | `_parse_call` | fonksiyon ismi token'ı | `[Expression …]` (argümanlar) |

---

## 6. Parser Metot Haritası

```
parse()
└─ _parse_toplevel()
   ├─ _parse_funcdef()
   │   ├─ _parse_funcsig()
   │   │   └─ _parse_type_param()  ─→  _parse_type_expr()
   │   └─ _parse_block()
   │       └─ _parse_statement()  ─→  _parse_expression()
   └─ _parse_statement()
       └─ _parse_expression()
           └─ _parse_assign()
               └─ _parse_typebind()
                   ├─ [":"]  _parse_type_expr()
                   │   └─ _parse_tuple_type_expr()
                   │       └─ _parse_type_param()
                   └─ _parse_binary()
                       └─ _parse_unary()
                           └─ _parse_term()
                               ├─ _parse_call()  ← YENİ: IDENT "(" args ")"
                               ├─ "("  _parse_expression()
                               ├─ "{"  _parse_block()
                               └─ _parse_literal()
```

---

## 7. Genişletme Rehberi

### Yeni binary operatör eklemek

`symbols.txt`'e sembolü ekle — parser değişmez.  
Özel öncelik/çağrışım istiyorsan `_parse_binary`'yi katmanlara böl:

```python
# Önce çarpar/böler, sonra toplar/çıkarır
def _parse_binary(self):
    return self._parse_additive()

def _parse_additive(self):
    left = self._parse_multiplicative()
    while self.match("+", "-"):
        ...

def _parse_multiplicative(self):
    left = self._parse_unary()
    while self.match("*", "/", "%"):
        ...
```

---

### Fonksiyon çağrısı eklemek `f(x, y)`

`_parse_term` içine `IDENT + "("` lookahead'i ekle:

```python
def _parse_term(self):
    tok = self.current()
    nxt = self.peek(1)

    # Fonksiyon çağrısı: IDENT "(" … ")"
    if (tok and tok.type == TokenType.LITERAL_IDEN
            and nxt and nxt.value == "("):
        return self._parse_call()

    if self.match("("):
        ...
```

```python
def _parse_call(self):
    name_tok = self.advance()          # IDENTIFIER
    node     = Node(NodeType.CALL, name_tok)
    self.expect("(")
    if not self.match(")"):
        node.add(self._parse_expression())
        while self.match(","):
            self.advance()
            node.add(self._parse_expression())
    self.expect(")")
    return node
```

---

### Yeni statement formu eklemek (`if`, `while`, `return`)

`_parse_expression` başına keyword dallanması ekle:

```python
def _parse_expression(self):
    if self.match("if"):     return self._parse_if()
    if self.match("while"):  return self._parse_while()
    if self.match("return"): return self._parse_return()
    return self._parse_assign()
```

`if` expression olduğu için bir değer döndürür:

```python
def _parse_if(self):
    tok = self.advance()          # "if"
    node = Node(NodeType.IF_EXPR, tok)
    node.add(self._parse_expression())   # koşul
    node.add(self._parse_block())        # then
    if self.match("else"):
        self.advance()
        node.add(self._parse_block())    # else
    return node
```

---

### Yeni tip yapısı eklemek

`_parse_tuple_type_expr` içine yeni dal ekle:

```python
def _parse_tuple_type_expr(self):
    # Dizi tipi: [T]
    if self.match("["):
        self.advance()
        inner = self._parse_type_expr()
        self.expect("]")
        node = Node(NodeType.ARRAY_TYPE)
        node.add(inner)
        return node

    # Opsiyonel tip: T?  →  _parse_type_expr sonrasında kontrol
    ...
```

---

### Üye erişimi eklemek `a.b`

Şu an `.` binary operatör olarak geçiyor.  
Düzgün AST için `_parse_term` sonrasına postfix zinciri ekle:

```python
def _parse_postfix(self, base):
    while True:
        if self.match("."):
            self.advance()
            field = self.advance()    # IDENTIFIER
            node  = Node(NodeType.MEMBER_ACCESS, field)
            node.add(base)
            base  = node
        else:
            break
    return base
```

`_parse_unary` içinde `self._parse_term()` çağrısını  
`self._parse_postfix(self._parse_term())` ile değiştir.

---

## 8. Bilinen Eksikler / TODO

| # | Özellik | Öncelik | Not |
|---|---------|---------|-----|
| 1 | **Fonksiyon çağrısı** `f(x,y)` | ✅ Tamamlandı | Parser'da ve Node tipi tanımlandı |
| 2 | **Üye erişimi** `a.b` | 🔴 Yüksek | `.` binary op olarak geçiyor |
| 3 | Operatör öncelik katmanları | 🟡 Orta | Binary tek düz katman; `+` ve `*` aynı öncelikte |
| 4 | `if` / `while` ifadeleri | 🟡 Orta | Expression olarak — değer döndürür |
| 5 | `return` statement'ı | 🟡 Orta | Erken çıkış için |
| 6 | Dizi tipi `[T]` | 🟢 Düşük | TypeExpr genişletmesi |
| 7 | Opsiyonel tip `T?` | 🟢 Düşük | TypeExpr genişletmesi |
| 8 | `unit` / `void` tipi | 🟢 Düşük | Boş blok dönüş değeri |
| 9 | Generic tipler `T<A>` | ⚪ Uzak | TypeExpr büyük genişletme |
| 10 | Import / modül sistemi | ⚪ Uzak | `builtin.print` geçici çözüm |