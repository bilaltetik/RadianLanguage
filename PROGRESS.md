# Radian Language — Geliştirme İlerlemesi

Bu dosya otonom geliştirme oturumlarının hafızasıdır. Her adım tamamlandığında
güncellenir. Durum işaretleri: `[ ]` yapılacak · `[~]` devam ediyor · `[x]` tamam.

---

## 0. Başlangıç durumu (oturum 1'de tespit edildi)

Depoda yalnızca `Prototip/lexer.py` (elle yazılmış lexer) ve `Prototip/parser.py`
(recursive-descent parser) vardı. Semantik analiz, yorumlayıcı, CLI ve test
altyapısı yoktu. Tespit edilen somut sorunlar:

- `Grammer.md` fonksiyon çağrısını "✅ Tamamlandı" gösteriyor ama `parser.py`'de
  `_parse_call` **yok**; `main () -> i32 { builtin_print("..."); 0; }` örneği
  `ParseError` veriyordu.
- `_parse_binary` tek düz öncelik katmanı: `+` ve `*` aynı öncelikte.
- Yorum satırı (`//`, `/* */`) desteği yok.
- `assert` tabanlı test yok; "test" = elle çıktı okuma.
- `_parse_literal` her `LITERAL_SYMB` token'ını literal kabul ediyor; bu yüzden
  `a b;` gibi hatalı girdiler anlamsız AST üretip sonra kafa karıştırıcı hata veriyordu.

---

## 1. Yol haritası

### Faz 1 — Altyapı
- [x] `PROGRESS.md` oluştur, yol haritasını çıkar.
- [x] `assert` tabanlı test altyapısı (`Prototip/tests/`, stdlib `unittest`).
- [x] `run_tests.py` — tek komutla tüm testleri çalıştır.

### Faz 2 — Bilinen bug'lar / yarım kalan özellikler
- [x] Lexer: `//` satır ve `/* */` blok yorumları.
- [x] Lexer: kapatılmamış string/char hatasının satır/sütun bilgisi token başlangıcını göstersin.
- [x] Lexer: eksik/hatalı sayısal önek (`0x`, `1e`) için net hata.
- [x] Parser: `_parse_call` — `f(x, y)` → `CALL` düğümü (dokümandaki drift kapandı).
- [x] Parser: `_parse_literal` artık gelişigüzel sembolü literal kabul etmesin.

### Faz 3 — Eksik dil özellikleri
- [x] Operatör öncelik katmanları (`*` > `+` > karşılaştırma > `&&` > `||`).
- [x] Üye erişimi `a.b` (postfix, `MEMBER` düğümü).
- [x] `if` / `else` — expression (değer döndürür).
- [x] `while` — expression.
- [x] `return` — statement.
- [x] `true` / `false` boolean literalleri.
- [ ] Tree-walking yorumlayıcı (`interpreter.py`).
- [ ] CLI: `radian.py <dosya.rad>`.
- [ ] Yerleşik fonksiyonlar (`print`, `len`, ...).
- [x] Dizi/liste literalleri `[1, 2, 3]` ve indeksleme `a[i]`.
- [x] `for ... in` döngüsü (parser).
- [x] `break` / `continue` (parser).
- [ ] Kullanıcı fonksiyonlarında closure + özyineleme.
- [ ] String yerleşikleri ve `str`/`int`/`float` dönüşümleri.

### Faz 4 — Test kapsamı
- [x] Lexer birim testleri.
- [x] Parser birim testleri.
- [ ] Yorumlayıcı birim testleri.
- [ ] Uçtan uca (`examples/*.rad`) testleri.

### Faz 5 — Kalite / dokümantasyon
- [ ] `Grammer.md`, `Radian.ebnf`, `PARSER_UPDATE_GUIDE.md` kodla senkron.
- [ ] Kök `README.md` gerçek içerik.

---

## 2. Tasarım kararları (oturum içinde verildi)

| # | Karar | Gerekçe |
|---|-------|---------|
| 1 | Binary operatör yalnızca `LITERAL_SYMB` olabilir; identifier operatör değildir. | `f (x)` çağrısı ile `a b` "operatörü" arasındaki belirsizliği kaldırır. Eski davranış zaten bozuktu (`a b;` anlamsız AST üretiyordu). |
| 2 | Öncelik tablosu sabit; tabloda olmayan semboller "özel operatör" seviyesine (en düşük binary) düşer. | `symbols.txt`'e yeni sembol eklemek hâlâ parser değişikliği gerektirmiyor. |
| 3 | Yorumlar lexer seviyesinde tamamen atılır (token üretilmez). | Parser'ın yorumdan haberi olmasına gerek yok. |
| 4 | `if`/`while`/blok birer *expression*; değer döndürürler. | `Grammer.md` §3.1'deki "blok son statement'ın değerini döndürür" semantiğiyle tutarlı. |
| 5 | Yorumlayıcı dinamik tipli; `:` tip bağlama şimdilik çalışma zamanında **doğrulanır** ama zorlama (coercion) yapmaz. | Statik tip denetleyicisi ayrı bir faz; erken tip zorlaması dili kullanılmaz hale getirirdi. |
| 6 | `return` fonksiyon gövdesinden erken çıkış için Python exception'ı ile taşınır. | Tree-walking yorumlayıcıda standart ve en basit yöntem. |
| 7 | Keyword'ler ayrı bir `TokenType` değil; parser `LITERAL_IDEN` değerine bakar. | Lexer'ı dilden bağımsız tutar (mevcut konvansiyon). |
| 9 | Parser artık bitişik sembol token'larını birleştirmiyor; operatörler lexer'ın ürettiği tek token'dır. | Eski birleştirme `a + -b` ifadesini `a +- b` yapıyordu. Çok karakterli operatör = `symbols.txt` satırı. |
| 10 | Unary operatörler sabit bir kümeyle sınırlı (`- + ! ~`). | Eskiden "ardında terim olan her sembol" unary sayılıyordu; `* x` gibi anlamsız girdiler sessizce kabul ediliyordu. |
| 11 | `if`/`while`/`for`/blok ile biten statement'larda `;` opsiyonel. | Rust benzeri; `if a { … }` sonuna `;` koymak zorunda kalmamak. |
| 12 | Bileşik atamalar (`+=`, `<<=` …) Assign katmanında; yorumlayıcı `a = a op b` olarak çözer. | Binary katmanına düşseydi `a += 1` ifadesi anlamsız bir binary düğüm üretirdi. |
| 8 | Dizi indeksleme `a[i]` postfix zincirinde; `[` tek karakterli sembol olarak zaten lexleniyor. | Çağrı/üye erişimiyle aynı katman → `a.b[0](x)` doğal çalışır. |

---

## 3. Oturum günlüğü

### Oturum 1 (2026-08-05)
- Depo incelendi, mevcut durum çıkarıldı, `PROGRESS.md` oluşturuldu.
- Test altyapısı kuruldu: `Prototip/tests/` + `run_tests.py` (56 test, tümü yeşil).
- Lexer: `//` ve `/* */` yorumları, kapatılmamış sabit/yorum ve eksik sayısal
  önek/üs için doğru konumlu net hatalar (67 test yeşil).
- Parser: fonksiyon çağrısı + postfix zinciri (`a.b[0](x)`), 11 katmanlı
  operatör önceliği, `if`/`else if`/`while`/`for`/`return`/`break`/`continue`,
  dizi literali ve dizi tipi, bileşik atamalar, iç fonksiyon tanımı (114 test yeşil).
