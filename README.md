# Radian Language

Elle yazılmış bir programlama dili prototipi: lexer, recursive-descent parser
ve AST üzerinde yürüyen bir yorumlayıcı. **Saf Python standart kütüphanesi** —
dış bağımlılık, derleme adımı ya da paket yöneticisi yok.

```radian
// examples/fizzbuzz.rad
fizzbuzz (n:i32) -> str {
    if n % 15 == 0 { "FizzBuzz"; }
    else if n % 3 == 0 { "Fizz"; }
    else if n % 5 == 0 { "Buzz"; }
    else { str(n); }
}

main () -> i32 {
    satirlar = [];
    for n in range(1, 16) { satirlar.push(fizzbuzz(n)); }
    print(satirlar.join(" "));
    0;
}
```

## Hızlı başlangıç

```bash
cd Prototip

python3 radian.py examples/fizzbuzz.rad   # bir programı çalıştır
python3 radian.py -c 'print(2 ** 10);'    # tek satır çalıştır
python3 radian.py                          # REPL
python3 radian.py --ast examples/hello.rad # AST'yi yazdır
python3 radian.py --tokens -c 'x = 1;'     # token akışını yazdır

python3 run_tests.py                       # tüm testler
```

## Dilin özeti

| Alan | Destek |
|------|--------|
| Değerler | tamsayı (`0xFF`, `0b1010`, `1_000`), ondalık, `str`, `char`, `bool`, dizi, harita, kayıt |
| Tipler | `i8…i64`, `u8…u64`, `f32/f64`, `bool`, `char`, `str`, `[T]`, `map`, `struct`, fonksiyon tipleri |
| Tip bağlama | `x : i32 = 42;` — çalışma zamanında doğrulanır (aralık denetimi dahil) |
| Operatörler | 11 öncelik katmanı, `**` sağ-çağrışımlı, bileşik atamalar (`+=`, `<<=`, …), `++`/`--` |
| Akış denetimi | `if`/`else if`/`else`, `while`, `for … in`, `break`, `continue`, `return` |
| Fonksiyonlar | özyineleme, closure, yüksek mertebeden fonksiyonlar, currying |
| Veri işleme | dizi/harita/string metotları: `map` `filter` `reduce` `sort` `split` `join` `keys` … |
| Modüller | `import "lib/geometri.rad"` — bir ifadedir, modül değeri döndürür |
| Diğer | `//` ve `/* */` yorumları, blok = ifade (son statement'ın değeri) |

Kendi veri tiplerini `struct` ile tanımlarsın; yapı adı hem tip hem kurucudur:

```radian
struct Nokta (x:f64, y:f64);

uzaklik (a:Nokta, b:Nokta) -> f64 {
    dx = a.x - b.x;
    dy = a.y - b.y;
    (dx * dx + dy * dy) ** 0.5;
}

assert(uzaklik(Nokta(0.0, 0.0), Nokta(3.0, 4.0)) == 5.0);
```

Her şey bir **ifadedir**: bloklar, `if`, `while` ve `for` değer döndürür.

```radian
r = { a = 1; a + 2; };                 // blok değeri → 3
etiket = if r > 2 { "büyük"; } else { "küçük"; };
assert(etiket == "büyük");
```

## Depo düzeni

```
Prototip/
├── lexer.py                 karakter karakter lexer (regex yok)
├── parser.py                recursive-descent parser → AST
├── interpreter.py           AST üzerinde yürüyen yorumlayıcı
├── radian.py                komut satırı aracı + REPL
├── symbols.txt              çok karakterli operatörler (çalışma anında yüklenir)
├── Radian.ebnf              canonical BNF grameri
├── Grammer.md               dil referansı: öncelik, semantik, node tipleri
├── PARSER_UPDATE_GUIDE.md   parser'ı genişletme rehberi
├── examples/*.rad           çalışan örnek programlar (lib/ altı import edilir)
├── tests/                   unittest paketi (lexer/parser/yorumlayıcı/uçtan uca/belge)
└── run_tests.py             test koşucusu
```

Geliştirme durumu, yol haritası ve verilen tasarım kararları: [`PROGRESS.md`](PROGRESS.md).

## Dile bir özellik eklemek

1. `Radian.ebnf` ve `Grammer.md`'de grameri güncelle.
2. `parser.py`: `NodeType` + `_parse_*` metodu, uygun üst kuraldan çağır.
3. `interpreter.py`: `_DISPATCH` tablosuna değerlendiriciyi ekle.
4. `tests/` altına test yaz; `python3 run_tests.py` yeşil olmalı.

Adım adım tarifler ve çalışılmış örnekler `PARSER_UPDATE_GUIDE.md` içindedir.

> Belgelerdeki `radian` etiketli kod blokları test koşusunda gerçekten
> çalıştırılır (`tests/test_docs.py`), dolayısıyla örnekler her zaman günceldir.

## Notlar

- Dokümantasyon ve kod içi yorumlar Türkçe; sınıf/metot/token adları İngilizcedir.
- Bu bir prototiptir: statik tip denetleyicisi, modül sistemi ve kod üretimi
  henüz yoktur (bkz. `PROGRESS.md` — Faz 6).
