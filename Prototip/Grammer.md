# Radian — Gramer ve Dil Referansı

> **Versiyon:** 0.4
> **Durum:** Çalışan prototip — lexer + parser + yorumlayıcı
> Bu belge canonical BNF tanımını, anlamsal notları, çalışma zamanı
> davranışını, node tipi referansını ve genişletme rehberini içerir.
>
> Kod ile bu belge ayrıştığında **doğru kabul edilen koddur**
> (`lexer.py` / `parser.py` / `interpreter.py`); belge güncellenmelidir.
> `radian` etiketli kod blokları `tests/test_docs.py` tarafından gerçekten
> çalıştırılır — belge örnekleri bayatlayamaz.

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
   - 3.6 [Fonksiyon Çağrısı ve Postfix Zinciri](#36-fonksiyon-çağrısı-ve-postfix-zinciri)
   - 3.7 [Akış Denetimi](#37-akış-denetimi)
   - 3.7.1 [Artırma / Azaltma](#371-artırma--azaltma--ve---)
   - 3.8 [Diziler ve String'ler](#38-diziler-ve-stringler)
4. [Örnekler](#4-örnekler)
5. [Çalışma Zamanı Semantiği](#5-çalışma-zamanı-semantiği)
6. [Node Tipi Referansı](#6-node-tipi-referansı)
7. [Parser Metot Haritası](#7-parser-metot-haritası)
8. [Genişletme Rehberi](#8-genişletme-rehberi)
9. [Bilinen Eksikler / TODO](#9-bilinen-eksikler--todo)

---

## 1. Tam BNF Grameri

Canonical sürüm `Radian.ebnf` dosyasındadır; aşağıdaki özet onunla aynıdır.

```bnf
(* ──────────── PROGRAM ──────────── *)

Program       = { TopLevel }
TopLevel      = Statement

(* ──────────── STATEMENT ──────────── *)

Statement     = FuncDef
              | StructDef
              | "return" [ Expression ] ";"
              | "break" ";"
              | "continue" ";"
              | Expression [ ";" ]        (* ";" blok-kuyruklu ifadelerde opsiyonel *)

(* ──────────── FONKSİYON ──────────── *)

FuncDef       = T_IDENTIFIER [ FuncSignature ] Block
FuncSignature = "(" [ TypeParamList ] ")" "->" TypeExpr
StructDef     = "struct" T_IDENTIFIER "(" [ TypeParamList ] ")" ";"

(* ──────────── BLOK ──────────── *)

Block         = "{" { Statement } "}"

(* ──────────── İFADE HİYERARŞİSİ  (düşük → yüksek öncelik) ──────────── *)

Expression    = Assign
Assign        = TypeBind [ AssignOp Assign ]     (* sağ-çağrışımlı, lvalue *)
AssignOp      = "=" | "+=" | "-=" | "*=" | "/=" | "%="
              | "**=" | "<<=" | ">>=" | "&=" | "|=" | "^="
TypeBind      = Binary   [ ":" TypeExpr ]        (* sağ-çağrışımlı, lvalue *)
Binary        = BinaryLevel0                     (* 11 katman — bkz. §2 *)
Unary         = ( "++" | "--" ) Unary | [ UnaryOp ] Unary | Term
Term          = Primary { CallSuffix | MemberSuffix | IndexSuffix } [ "++" | "--" ]

CallSuffix    = "(" [ ArgumentList ] ")"
MemberSuffix  = "." T_IDENTIFIER
IndexSuffix   = "[" Expression "]"
ArgumentList  = Expression { "," Expression }

Primary       = "(" Expression ")"
              | Block
              | ArrayLiteral | MapLiteral
              | IfExpr | WhileExpr | ForExpr | ImportExpr
              | Literal

ArrayLiteral  = "[" [ Expression { "," Expression } [ "," ] ] "]"
MapLiteral    = "#" "[" [ MapEntry { "," MapEntry } [ "," ] ] "]"
MapEntry      = Binary ":" Expression
ImportExpr    = "import" Unary

(* ──────────── AKIŞ DENETİMİ (hepsi ifadedir) ──────────── *)

IfExpr        = "if" Expression Block [ "else" ( IfExpr | Block ) ]
WhileExpr     = "while" Expression Block
ForExpr       = "for" T_IDENTIFIER "in" Expression Block

(* ──────────── TİP DİLİ ──────────── *)

TypeExpr      = TupleTypeExpr "->" TypeExpr      (* sağ-çağrışımlı *)
              | TupleTypeExpr

TupleTypeExpr = "(" [ TypeParamList ] ")"
              | "[" TypeExpr "]"                 (* dizi tipi *)
              | T_IDENTIFIER

TypeParamList = TypeParam { "," TypeParam }
TypeParam     = T_IDENTIFIER ":" TypeExpr        (* isimli *)
              | TypeExpr                         (* isimsiz *)

(* ──────────── OPERATÖRLER ──────────── *)

Operator      = T_SYMBOL                         (* birleştirme YOK *)
UnaryOp       = "-" | "+" | "!" | "~"
IncDecOp      = "++" | "--"                      (* yalnızca lvalue üzerinde *)

(* ──────────── LİTERAL ──────────── *)

Literal       = T_STRING | T_CHAR | T_NUMBER
              | T_IDENTIFIER
              | "true" | "false"
              | PrimitiveType

PrimitiveType = "i8"  | "i16" | "i32" | "i64"
              | "u8"  | "u16" | "u32" | "u64"
              | "f32" | "f64" | "bool" | "char"
```

**Anahtar sözcükler:** `if else while for in return break continue true false
struct import`
Lexer bunları `T_IDENTIFIER` olarak üretir; ayrımı parser yapar.

**Yorumlar:** `// satır sonuna kadar` ve `/* blok */` — lexer'da atılır,
parser'a token ulaşmaz. Blok yorumları iç içe geçmez.

---

## 2. Öncelik Tablosu

| Seviye | Kural | Sembol / Tetikleyici | Çağrışım | Not |
|--------|-------|----------------------|----------|-----|
| 1 (en düşük) | `Assign` | `=` `+=` `-=` … | **Sağ** | lvalue döndürür |
| 2 | `TypeBind` | `:` | **Sağ** | Sağı TypeExpr |
| 3 | `Binary` | 11 katman (aşağıda) | **Sol** | `**` sağ-çağrışımlı |
| 4 | `Unary` | `-` `+` `!` `~` | — | Yalnızca önek |
| 4 | `IncDec` | `++` `--` | — | Önek ve sonek; hedef lvalue olmalı |
| 5 | `Term` | `f(x)` `a.b` `a[i]` | **Sol** | Postfix zinciri |
| 6 (en yüksek) | `Primary` | `()` `{}` `[]` literal | — | Gruplama |
| — (bağımsız) | `TypeExpr` | `->` | **Sağ** | Yalnızca `:` sağında |

### Binary katmanları (`parser.py: BINARY_LEVELS`)

| Katman | Operatörler | Açıklama |
|--------|-------------|----------|
| 0 | `\|\|` *(+ tabloda olmayan semboller)* | Mantıksal VEYA |
| 1 | `&&` | Mantıksal VE |
| 2 | `\|` | Bit VEYA |
| 3 | `^` | Bit XOR |
| 4 | `&` | Bit VE |
| 5 | `==` `!=` | Eşitlik |
| 6 | `<` `>` `<=` `>=` | Karşılaştırma |
| 7 | `<<` `>>` | Kaydırma |
| 8 | `+` `-` | Toplama / çıkarma |
| 9 | `*` `/` `%` | Çarpma / bölme / mod |
| 10 | `**` | Üs alma — **sağ-çağrışımlı** |

> `symbols.txt`'e eklenip bu tabloda yer almayan bir sembol **katman 0**'a
> düşer. Yani yeni bir operatör eklemek için parser'a dokunmak gerekmez;
> yalnızca özel bir öncelik isteniyorsa tablo güncellenir.

---

## 3. Anlamsal Notlar

### 3.1 Blok — Implicit Return

```
{ stmt₁; stmt₂; … stmtₙ; }
```

- **Son statement'ın değeri** blokun değeridir.
- Boş blok `{}` → `unit` (yazdırıldığında `()`).
- Her blok **yeni bir kapsam** açar.
- Blok hem fonksiyon gövdesi hem değer (Primary) olarak kullanılabilir.

```radian
// Fonksiyon gövdesi olarak
kare (x:i32) -> i32 {
    x * x;          // implicit return — son statement
}

// Değer olarak
sonuc = {
    a = 10;
    b = 20;
    a + b;          // blok = 30, sonuc = 30
};
assert(sonuc == 30);
```

---

### 3.2 `=` Operatörü — Atama ve lvalue

`a = b` → b'yi a'ya atar ve **a'yı** (lvalue) döndürür.

| İfade | AST | Anlam |
|-------|-----|-------|
| `a = b` | `ASSIGN(a, b)` | b'yi a'ya ata, a'yı döndür |
| `a = b = c` | `ASSIGN(a, ASSIGN(b, c))` | sağ-çağrışımlı zincir |
| `(a = b) + 2` | `BINARY(ASSIGN(a,b), +, 2)` | lvalue kullanımı |
| `a += 1` | `ASSIGN:'+='(a, 1)` | `a = a + 1` ile eşdeğer |
| `xs[0] = 9` | `ASSIGN(INDEX(xs,0), 9)` | dizi elemanına atama |

Atama hedefi yalnızca **IDENTIFIER**, **TYPEBIND** ya da **INDEX** olabilir;
diğerleri "Geçersiz atama hedefi" hatası verir.

Kapsam kuralı: `=` değişkeni kapsam zincirinde arar; bulursa **onu günceller**,
bulamazsa **geçerli kapsamda tanımlar**.

```radian
a = (b = 42) + 1;
assert(a == 43 && b == 42);

sayac = 0;
sayac += 5;
assert(sayac == 5);

xs = [1, 2, 3];
xs[0] = 9;
assert(xs == [9, 2, 3]);
```

---

### 3.3 `:` Operatörü — Tip Bağlama ve lvalue

`a : T` → a'yı T tipine bağlar ve **a'yı** (lvalue) döndürür.
`:` sağında her zaman **TypeExpr** gelir; expression değil.

| İfade | AST | Anlam |
|-------|-----|-------|
| `b : i32` | `TYPEBIND(b, i32)` | b'yi i32'ye bağla (yoksa sıfır değerle tanımla) |
| `a : i32 = b` | `ASSIGN(TYPEBIND(a,i32), b)` | a→i32 bağla, b'yi ata |
| `a = b : i32` | `ASSIGN(a, TYPEBIND(b,i32))` | b'yi i32 olarak doğrula, a'ya ata |
| `xs : [i32]` | `TYPEBIND(xs, ARRAY(i32))` | dizi tipi bağlama |

Bağlama **doğrulayıcıdır, dönüştürücü değildir**: `x : i32 = "abc";` hata verir,
string'i sayıya çevirmez. Bir kez bağlanan tip, sonraki atamalarda da denetlenir.

Değersiz bildirim tipin sıfır değerini verir:
`i*/u*` → `0`, `f32/f64` → `0.0`, `bool` → `false`, `str`/`char` → `""`, `[T]` → `[]`.

```radian
sayac : i32;
assert(sayac == 0);

yas : u8 = 42;
oran : f64 = 0.75;
kareler : [i32] = [1, 4, 9];
assert(kareler.len() == 3);
```

---

### 3.4 Fonksiyon Tanımı Formları

**Form 1 — Sadece gövde** *(parametresiz)*

```radian
sabit {
    42;
}
assert(sabit() == 42);
```

**Form 2 — İmza + gövde** *(tam tanım, önerilen)*

```radian
topla (x:i32, y:i32) -> i32 {
    x + y;
}
assert(topla(2, 3) == 5);
```

**Form 3 — Sadece imza bildirimi** *(Statement)*

```radian
topla : (x:i32, y:i32) -> i32;
```

**Parser ayrım kuralı** (`_is_funcdef_ahead`):

```
IDENTIFIER + "{"                 →  FuncDef (Form 1)
IDENTIFIER + "(" … ")" + "->"    →  FuncDef (Form 2)
IDENTIFIER + "(" … ")"           →  fonksiyon çağrısı
diğer                            →  Statement
```

Fonksiyon tanımı blok içinde de geçerlidir; iç fonksiyonlar tanımlandıkları
kapsamı taşır (closure).

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
| Primitive | `i32` `bool` `f64` `char` `str` | Yerleşik tipler |
| Dizi | `[i32]` `[[f64]]` | Eleman tipleri de denetlenir |
| Fonksiyon | `(x:i32) -> i32` | Giriş → çıkış |
| Curried | `(x:i32) -> (y:i32) -> bool` | Zincirleme fonksiyon |
| HOF | `(f:(x:i32)->i32, v:i32) -> i32` | Fonksiyon parametreli |
| İsimsiz | `(i32, i32) -> i32` | Yalnızca tip bildiriminde |

Fonksiyon **tanımında** parametre adı zorunludur (`(x:i32)`); isimsiz form
yalnızca tip bildiriminde kullanılabilir.

```radian
f : (x:i32) -> (y:i32) -> bool;
g : (i32, i32) -> i32;
matris : [[f64]] = [[1.0, 2.0], [3.0, 4.0]];

uygula (f:(x:i32) -> i32, v:i32) -> i32 { f(v); }
iki_kat (x:i32) -> i32 { x * 2; }
assert(uygula(iki_kat, 21) == 42);
```

---

### 3.6 Fonksiyon Çağrısı ve Postfix Zinciri

Çağrı, üye erişimi ve indeksleme aynı katmandadır ve soldan sağa zincirlenir.

| İfade | AST | Anlam |
|-------|-----|-------|
| `print(42)` | `CALL(print, 42)` | Basit çağrı |
| `add(1, 2, 3)` | `CALL(add, 1, 2, 3)` | Çok argümanlı çağrı |
| `apply(f, g(x))` | `CALL(apply, f, CALL(g, x))` | İç içe çağrı |
| `f(1)(2)` | `CALL(CALL(f,1), 2)` | Currying |
| `a.b` | `MEMBER:b(a)` | Üye erişimi |
| `xs[i]` | `INDEX(xs, i)` | İndeksleme |
| `obj.xs[0](z)` | `CALL(INDEX(MEMBER:xs(obj),0), z)` | Karışık zincir |

> `CALL` düğümünde `children[0]` **çağrılan ifadedir**, kalan çocuklar
> argümanlardır. Çağrılan bir isim olmak zorunda değildir.

```radian
// Currying: dış fonksiyon bir fonksiyon döndürür
ekleyici (a:i32) -> (b:i32) -> i32 {
    ekle (b:i32) -> i32 { a + b; }
    ekle;
}
assert(ekleyici(2)(3) == 5);

// Zincir: metot → indeks
assert("a,b,c".split(",")[1] == "b");
```

---

### 3.7 Akış Denetimi

`if`, `while` ve `for` birer **ifadedir**; değer döndürürler.

| Yapı | Değeri |
|------|--------|
| `if c { … } else { … }` | Seçilen dalın blok değeri |
| `if c { … }` *(else yok, c yanlış)* | `unit` |
| `while c { … }` | Son çalışan yinelemenin gövde değeri, hiç çalışmazsa `unit` |
| `for x in xs { … }` | Son yinelemenin gövde değeri, dizi boşsa `unit` |

- Koşullar **kesin olarak `bool`** olmalıdır; truthy dönüşümü yoktur.
- `return` yalnızca fonksiyon gövdesinden çıkar; `break` / `continue` yalnızca
  döngü içinde geçerlidir ve fonksiyon sınırını aşamaz.
- Blokla biten bir statement'ta `;` opsiyoneldir:
  `if x { 1; }` geçerli, `r = if x { 1; };` içinse `;` gereklidir.

```radian
mutlak (x:i32) -> i32 {
    if x < 0 { return -x; }
    x;
}
assert(mutlak(-4) == 4);

i = 0;
while true {
    i += 1;
    if i == 3 { break; }
}
assert(i == 3);

toplam = 0;
for n in range(1, 6) {
    if n % 2 == 0 { continue; }
    toplam += n;
}
assert(toplam == 9);          // 1 + 3 + 5

// if bir ifadedir → değer olarak kullanılabilir
etiket = if toplam > 5 { "büyük"; } else { "küçük"; };
assert(etiket == "büyük");
```

---

### 3.7.1 Artırma / Azaltma — `++` ve `--`

Hedef **lvalue** olmalıdır (değişken ya da dizi elemanı); literal ya da çağrı
sonucu üzerinde kullanmak sözdizimi hatasıdır. Önek biçimi yeni, sonek biçimi
eski değeri döndürür. Binary operatör değildirler: `a ++ b` geçersizdir.

```radian
x = 1;
assert(++x == 2);          // önce artır, yeni değeri döndür
assert(x++ == 2);          // eski değeri döndür
assert(x == 3);

xs = [1, 2];
xs[0]++;
assert(xs == [2, 2]);

i = 0;
while i < 3 { i++; }
assert(i == 3);
```

> `xs[f()]++` biçiminde indeks ifadesi iki kez değerlendirilir (okuma ve yazma
> için); yan etkili indeks kullanmaktan kaçının.

---

### 3.8 Diziler ve String'ler

```radian
xs = [1, 2, 3];      // dizi literali (sondaki virgül serbest)
assert(xs[0] == 1);  // indeksleme — 0 tabanlı
xs[0] = 9;           // eleman ataması
xs.push(4);          // yerinde değişiklik
assert(xs == [9, 2, 3, 4]);

// Diziler referans değerdir: kopya çıkmaz
ys = xs;
ys.push(5);
assert(xs.len() == 5);

// String'ler indekslenebilir ve gezilebilir
s = "radian";
assert(s[0] == "r");
harfler = "";
for c in s { harfler = c + harfler; }
assert(harfler == "naidar");
```

- Diziler **referans değerdir**: atama kopya çıkarmaz.
- İndeks tamsayı olmalı ve `0 <= i < uzunluk` aralığında bulunmalıdır;
  **negatif indeks hatadır** (sondan sayma yoktur).
- String'ler indekslenebilir ve `for` ile gezilebilir; `s[0]` tek karakterlik
  bir string döndürür.

### Modüller — `import`

`import "yol.rad"` bir **ifadedir**; dosyayı çalıştırıp modül değeri döndürür.
Modülün üst düzey tanımlarının tümü (değişken, fonksiyon, yapı) `modül.ad`
biçiminde görünür.

```
geo = import "lib/geometri.rad";
geo.daire_alani(2.0);
geo.Vektor(3.0, 4.0);
```

- Yol, **import eden dosyanın dizinine** göre çözülür; mutlak yol da verilebilir.
- Bir dosya **bir kez** çalıştırılır; sonuç gerçek yola göre önbelleğe alınır,
  ikinci `import` aynı modül nesnesini verir.
- Modül kendi kapsamında çalışır; yerleşiklere erişir ama import edenin
  değişkenlerini görmez ve onun kapsamını kirletmez.
- **Döngüsel import hatadır**; eksik dosya ve modül içi sözdizimi hataları
  import eden satırı işaret eder.

---

### Kayıt tipleri (struct)

`struct Ad (alan:Tip, …);` bir kayıt tipi tanımlar. Yapı adı hem tip hem
kurucudur; alanlara `.` ile erişilir ve yazılır.

```radian
struct Nokta (x:i32, y:i32);
struct Cember (merkez:Nokta, yaricap:f64);

p = Nokta(3, 4);
assert(p.x == 3);

p.y = 9;                           // alan yazma — tipi denetlenir
assert(p.y == 9);

// Yapı adı tip konumunda da geçerli
q : Nokta = p;
uzaklik_kare (a:Nokta) -> i32 { a.x * a.x + a.y * a.y; }
assert(uzaklik_kare(Nokta(3, 4)) == 25);

// İç içe yapı ve eşitlik
c = Cember(Nokta(0, 0), 5.0);
assert(c.merkez == Nokta(0, 0));
assert(Nokta(1, 2) == Nokta(1, 2));
```

- Kurucu **konumsaldır**; alan sayısı ve tipleri çağrıda denetlenir.
- Bilinmeyen alanı okumak/yazmak hatadır; alan adları yinelenemez.
- Yapılar **referans değerdir**; eşitlik aynı yapı tipi ve alan alan
  karşılaştırma demektir (`struct A (v:i32)` ile `struct B (v:i32)` asla eşit
  değildir).
- Yazdırıldığında `Nokta(x: 3, y: 9)` biçiminde görünür.

---

### Haritalar

Harita literali `#[anahtar: değer]` biçimindedir. `{` blok başlattığı ve
`{a: T}` tip bağlama ile çakıştığı için ayrı bir açılış işareti kullanılır.

```radian
m = #["a": 1, "b": 2];
assert(m["a"] == 1);

m["c"] = 3;                        // yoksa ekler
assert(m.len() == 3);
assert(m.has("c"));
assert(m.get("yok", 0) == 0);      // eksik anahtar okumak hatadır, get() güvenli

// Anahtarlar üzerinde gezinme
toplam = 0;
for k in m { toplam += m[k]; }
assert(toplam == 6);

// Anahtar sayı da olabilir
sayilar = #[1: "bir", 2: "iki"];
assert(sayilar[2] == "iki");

// İkililerden kurma ve birleştirme
kodlar = map([["tr", 90], ["jp", 81]]);
assert(kodlar["tr"] == 90);
birlesik = #["x": 1].merge(#["y": 2]);
assert(birlesik.keys() == ["x", "y"]);
```

- Anahtar `str`, `int` ya da `float` olabilir; **`bool` anahtar yasaktır**
  (Radian'da `1 == true` yanlıştır, oysa aynı anahtara düşerlerdi).
- Eksik anahtarı `m[k]` ile okumak hatadır; `m.get(k, varsayılan)` güvenlidir.
- Haritalar da diziler gibi **referans değerdir**; `merge` yeni harita döndürür.
- `for k in m` anahtarlar üzerinde gezer.

Metot listesi için bkz. [§5 Çalışma Zamanı Semantiği](#5-çalışma-zamanı-semantiği).

---

## 4. Örnekler

Çalışan tam programlar `examples/` altındadır (`radian.py examples/hello.rad`).

```radian
// Temel aritmetik
topla (x:i32, y:i32) -> i32 {
    x + y;
}

// Blok değer olarak + if ifadesi
clamp (x:i32, lo:i32, hi:i32) -> i32 {
    if x < lo { lo; } else if x > hi { hi; } else { x; }
}
assert(clamp(15, 0, 10) == 10);

// Tip bağlama
sayac : i32 = 0;
oran  : f64 = 0.75;
adlar : [str] = ["ada", "linus"];

// Closure
sayac_yap {
    n = 0;
    artir { n += 1; n; }
    artir;
}
c = sayac_yap();
c();
assert(c() == 2);

// Dizi işleme
kare (x:i32) -> i32 { x * x; }
tek  (x:i32) -> bool { x % 2 == 1; }
assert(range(1, 6).filter(tek).map(kare) == [1, 9, 25]);
```

`main` tanımlıysa üst düzey statement'lardan sonra otomatik çağrılır ve
`0..255` aralığındaki dönüş değeri süreç çıkış kodu olur:

```
main () -> i32 {
    print("Merhaba, Dünya!");
    0;
}
```

---

## 5. Çalışma Zamanı Semantiği

`interpreter.py` AST üzerinde doğrudan yürüyen bir yorumlayıcıdır.

### Değer tipleri

| Radian | Çalışma zamanı | `type()` çıktısı |
|--------|----------------|------------------|
| `i8`…`u64` | Python `int` | `"int"` |
| `f32` `f64` | Python `float` | `"float"` |
| `bool` | Python `bool` | `"bool"` |
| `char` `str` | Python `str` | `"char"` / `"str"` |
| `[T]` | Python `list` | `"array"` |
| `map` | Python `dict` | `"map"` |
| kayıt | `StructInstance` | yapının adı (örn. `"Nokta"`) |
| modül | `Module` | `"module"` |
| fonksiyon | `Function` / `Builtin` | `"func"` |
| unit | `UNIT` | `"unit"` |

### Operatör davranışı

- **Tamsayı bölmesi C semantiğindedir**: `7 / 2 == 3`, `-7 / 2 == -3`.
  `%` işareti bölünene uyar: `-7 % 3 == -1`. Taraflardan biri `float` ise
  sonuç `float`'tır. Sıfıra bölme hatadır.
- `+` string ve dizilerde birleştirme yapar; `"ab" * 3` ve `[0] * 3` tekrarlar.
- `&& || !` ve tüm koşullar **yalnızca `bool`** kabul eder; `&&` / `||`
  kısa devre yapar.
- `& | ^ << >>` yalnızca tamsayılarda geçerlidir.
- `==` tip duyarlıdır: `1 == true` → `false`.

```radian
assert(7 / 2 == 3);
assert(-7 / 2 == -3);
assert(-7 % 3 == -1);
assert(7.0 / 2 == 3.5);
assert("ab" * 2 == "abab");
assert((1 == true) == false);
assert(2 ** 3 ** 2 == 512);      // sağ-çağrışımlı
```

### Tip denetimi

Bağlama anında yapılır: tip uyuşmazlığı, tamsayı aralığı taşması
(`x : i8 = 200;`), işaretsiz tipe negatif değer, dizi eleman tipi, fonksiyon
parametre ve dönüş tipleri denetlenir.

### Yerleşik fonksiyonlar

| İsim | İmza | Açıklama |
|------|------|----------|
| `print(…)` | serbest | Argümanları boşlukla ayırıp satır sonuyla yazar |
| `write(…)` | serbest | Satır sonu eklemez |
| `len(x)` | str/dizi | Uzunluk |
| `str/int/float/bool(x)` | 1 | Tip dönüşümü |
| `type(x)` | 1 | Çalışma zamanı tip adı |
| `range(a[,b[,c]])` | 1–3 | Tamsayı dizisi |
| `map([ikililer])` | 0–1 | Boş harita ya da `[[k, v], …]` listesinden harita |
| `abs/min/max/sum` | — | Sayısal yardımcılar (dizi ya da çoklu argüman) |
| `assert(c[,msg])` | 1–2 | Koşul yanlışsa hata fırlatır |

### Metotlar

- **Dizi:** `len push pop insert remove contains index_of slice reverse join
  map filter reduce sort`
- **Harita:** `len has get set remove keys values pairs clear merge`
- **String:** `len upper lower trim split contains starts_with ends_with
  replace find slice chars repeat`
- **Sayı:** `abs to_str min max`

```radian
assert([3, 1, 2].sort() == [1, 2, 3]);
assert([1, 2].join("-") == "1-2");
assert("  Ab  ".trim().lower() == "ab");
assert("a,b".split(",").len() == 2);
assert((-3).abs() == 3);
assert(type([1]) == "array");
```

### Program akışı

Üst düzey statement'lar sırayla çalışır. Sonrasında **argümansız bir `main`**
tanımlıysa otomatik çağrılır ve dönüş değeri programın değeri olur; `0..255`
aralığındaki tamsayı değer süreç çıkış kodudur.

---

## 6. Node Tipi Referansı

| NodeType | Oluşturan Kural | `value` | `children` |
|----------|----------------|---------|-----------|
| `PROGRAM` | `parse()` | — | `[TopLevel …]` |
| `STATEMENT` | `_parse_statement` | — | `[Expression]` |
| `FUNC_DEF` | `_parse_funcdef` | isim token'ı | `[FuncSignature?] [Block]` |
| `BLOCK` | `_parse_block` | — | `[Statement …]` |
| `FUNC_TYPE` | `_parse_funcsig` / `_parse_type_expr` | `->` token'ı | `[TypeParam …, RetTypeParam]` |
| `TUPLE_TYPE` | `_parse_tuple_type_expr` | — | `[TypeParam …]` |
| `TYPE_PARAM` | `_parse_type_param` | isim (varsa) | `[TypeExpr]` |
| `ASSIGN` | `_parse_assign` | atama op. token'ı | `[lhs, rhs]` |
| `TYPEBIND` | `_parse_typebind` | `:` token'ı | `[lhs, TypeExpr]` |
| `BINARY_OP` | `_parse_binary` | — | `[lhs, OPERATOR, rhs]` |
| `UNARY_OP` | `_parse_unary` | — | `[OPERATOR, işlenen]` |
| `PRE_OP` | `_parse_unary` | `++` / `--` token'ı | `[hedef]` |
| `POST_OP` | `_parse_term` | `++` / `--` token'ı | `[hedef]` |
| `OPERATOR` | `_parse_operator` | operatör token'ı | — |
| `LITERAL` | `_parse_literal` | değer token'ı | — |
| `IDENTIFIER` | `_parse_literal` | isim token'ı | — |
| `CALL` | `_parse_call` | `(` token'ı | `[çağrılan, argüman …]` |
| `MEMBER` | `_parse_member` | üye adı token'ı | `[nesne]` |
| `INDEX` | `_parse_index` | `[` token'ı | `[nesne, indeks]` |
| `ARRAY` | `_parse_array` / `_parse_tuple_type_expr` | `[` token'ı | `[eleman …]` ya da `[eleman tipi]` |
| `MAP` | `_parse_map` | `#` token'ı | `[anahtar, değer, …]` (ikişerli) |
| `STRUCT_DEF` | `_parse_struct` | yapı adı token'ı | `[TYPE_PARAM …]` (alanlar) |
| `IMPORT` | `_parse_import` | `import` token'ı | `[yol ifadesi]` |
| `IF` | `_parse_if` | `if` token'ı | `[koşul, then, else?]` |
| `WHILE` | `_parse_while` | `while` token'ı | `[koşul, gövde]` |
| `FOR` | `_parse_for` | döngü değişkeni token'ı | `[dizi, gövde]` |
| `RETURN` | `_parse_return` | `return` token'ı | `[ifade?]` |
| `BREAK` / `CONTINUE` | `_parse_statement` | anahtar sözcük token'ı | — |

**Adlandırma kuralı:** değer üreten düğümlerde `_EXPR`, operasyonlarda `_OP`,
yapısal düğümlerde son ek yok.

---

## 7. Parser Metot Haritası

```
parse()
└─ _parse_toplevel()
   └─ _parse_statement()
      ├─ _is_funcdef_ahead() → _parse_funcdef()
      │   ├─ _parse_funcsig()
      │   │   └─ _parse_type_param()  ─→  _parse_type_expr()
      │   └─ _parse_block()
      ├─ _parse_return()
      └─ _parse_expression()
          └─ _parse_assign()
              └─ _parse_typebind()
                  ├─ [":"]  _parse_type_expr()
                  │   └─ _parse_tuple_type_expr()
                  │       └─ _parse_type_param()
                  └─ _parse_binary(level)        ← 11 katman, özyinelemeli
                      └─ _parse_unary()
                          └─ _parse_term()       ← postfix zinciri
                              ├─ _parse_call()
                              ├─ _parse_member()
                              ├─ _parse_index()
                              └─ _parse_primary()
                                  ├─ "("  _parse_expression()
                                  ├─ "{"  _parse_block()
                                  ├─ "["  _parse_array()
                                  ├─ if/while/for  _parse_if/_parse_while/_parse_for()
                                  └─ _parse_literal()
```

---

## 8. Genişletme Rehberi

Ayrıntılı, adım adım tarifler için `PARSER_UPDATE_GUIDE.md`.

### Yeni binary operatör eklemek

1. `symbols.txt`'e sembolü ekle (çok karakterliyse) — lexer değişmez.
2. Özel öncelik istiyorsan `parser.py: BINARY_LEVELS` tablosundaki uygun
   kümeye ekle; eklemezsen katman 0'a düşer.
3. `interpreter.py: _binary_values` içine davranışını yaz.
4. `tests/test_parser.py` ve `tests/test_interpreter.py`'ye test ekle.

### Yeni statement / ifade formu eklemek

1. `Radian.ebnf` + bu belgeyi güncelle.
2. `NodeType`'a değer ekle.
3. `_parse_*` metodunu yaz, `_parse_statement` ya da `_parse_primary`'den
   anahtar sözcük lookahead'iyle çağır.
4. `KEYWORDS` kümesine yeni anahtar sözcüğü ekle.
5. `Interpreter._DISPATCH` tablosuna değerlendirici ekle.
6. Test ekle; `python3 run_tests.py` yeşil olmalı.

### Yeni yerleşik fonksiyon / metot eklemek

- Genel fonksiyon: `interpreter.py` içinde `_bi_*` yaz, `_BUILTIN_SPECS`
  listesine `(isim, fn, arite)` olarak ekle.
- Metot: ilgili tabloya (`ARRAY_METHODS` / `STRING_METHODS` / `NUMBER_METHODS`)
  `_method(isim, arite)(fn)` girdisi ekle.

---

## 9. Bilinen Eksikler / TODO

Güncel durum ve öncelikler için depo kökündeki `PROGRESS.md`.

| # | Özellik | Öncelik | Not |
|---|---------|---------|-----|
| 2 | Statik tip denetleyicisi | 🟡 Orta | Şu an tüm denetim çalışma zamanında |
| 5 | Opsiyonel tip `T?` | 🟢 Düşük | TypeExpr genişletmesi |
| 6 | Generic tipler `T<A>` | ⚪ Uzak | TypeExpr büyük genişletme |
| 8 | Bytecode VM / kod üretimi | ⚪ Uzak | Yorumlayıcı referans gerçekleme olarak kalır |
