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
- [x] Tree-walking yorumlayıcı (`interpreter.py`).
- [x] CLI: `radian.py <dosya.rad>`.
- [x] Yerleşik fonksiyonlar (`print`, `len`, ...).
- [x] Dizi/liste literalleri `[1, 2, 3]` ve indeksleme `a[i]`.
- [x] `for ... in` döngüsü.
- [x] `break` / `continue`.
- [x] Kullanıcı fonksiyonlarında closure + özyineleme.
- [x] String yerleşikleri ve `str`/`int`/`float` dönüşümleri.

### Faz 4 — Test kapsamı
- [x] Lexer birim testleri.
- [x] Parser birim testleri.
- [x] Yorumlayıcı birim testleri.
- [x] Uçtan uca (`examples/*.rad`) testleri.

### Faz 6 — Sağlamlık ve sonraki adaylar
- [x] Çalışma zamanı hatalarında çağrı yığını (`RadianError.frames`).
- [x] `++` / `--` gerçeklendi (önek `PRE_OP`, sonek `POST_OP`; hedef lvalue
      olmalı, parse zamanında doğrulanır).
- [x] Sağlamlık taraması: bozuk girdiden yalnızca `ParseError`/`RadianError`
      çıkması `tests/test_robustness.py` ile garanti altında.
- [x] Döngüsel dizi referansı yazdırılabiliyor (`[...]`), çökmüyor.
- [x] Özyineleme derinliği 162 → 1000 (kendi sayacımız + net Radian hatası).
- [ ] Statik tip denetleyicisi (çalışma zamanı yerine parse sonrası).
- [x] Harita (map) tipi: `#[k: v]` literali, indeksleme/atama, 10 metot.
- [x] `struct` / kayıt tipleri (`struct Ad (alan:Tip);`, kurucu + alan erişimi).
- [x] Modül / `import` sistemi (ifade biçiminde, önbellekli, döngü denetimli).

### Faz 5 — Kalite / dokümantasyon
- [x] `Grammer.md` ve `Radian.ebnf` kodla senkron; belge örnekleri testlerde çalışıyor.
- [x] `PARSER_UPDATE_GUIDE.md` kodla senkron (sürüm 2.0).
- [x] Kök `README.md` gerçek içerik.
- [x] `CLAUDE.md` güncel mimariyi anlatıyor.

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
| 13 | Diziler referans değerdir; atama kopya çıkarmaz. | `xs.push(…)` gibi yerinde değişen metotlar için tek tutarlı semantik. |
| 14 | Tamsayı bölmesi C semantiğinde (sıfıra doğru kırpar), `%` işareti bölünene uyar; iki taraf da tamsayıysa sonuç tamsayıdır. | Sistem dili hedefi; `7 / 2 == 3`, `-7 / 2 == -3`. |
| 15 | Negatif indeks hatadır (Python'daki sondan sayma yok). | Sınır dışı erişimi sessizce başka bir elemana çevirmemek için. |
| 16 | `main` tanımlıysa üst düzey statement'lardan sonra otomatik çağrılır; 0..255 arası dönüş değeri süreç çıkış kodudur. | `main () -> i32 { … }` örneğinin dokümanlardaki anlamını gerçeklemek için. |
| 17 | İfade konumundaki primitive tip adı (`bool`, `char`) aynı adlı bir değer tanımlıysa o değere çözülür. | `bool(x)` dönüşüm fonksiyonu ile `x : bool` tip adı çakışmasın diye. |
| 25 | `import` bir ifadedir ve modül değeri döndürür; ad alanı `modül.ad` üzerinden gelir. | Bildirim biçimi (`import x from "y"`) yeni sözdizimi ve isim çakışması getirirdi; ifade biçimi mevcut `MEMBER` düğümünü kullanır ve modülü birinci sınıf değer yapar. |
| 26 | Modül yolu, import eden dosyanın dizinine göre çözülür; modüller gerçek yola göre önbelleğe alınır. | Kütüphane dosyaları kendi komşularını çalışma dizininden bağımsız olarak import edebilsin diye. |
| 23 | `struct Ad (alanlar);` bildirimi fonksiyon imzasıyla aynı `TypeParamList` dilbilgisini kullanır; yapı adı aynı zamanda kurucudur. | Yeni sözdizimi yüzeyi en aza iner: mevcut `CALL` ve `MEMBER` düğümleri olduğu gibi kullanılır. |
| 24 | Yapı eşitliği: aynı `StructType` nesnesi + alan alan karşılaştırma. Alanları aynı olan iki farklı yapı asla eşit değildir. | Yapı adı bir tip kimliğidir; yapısal değil nominal eşitlik. |
| 21 | Harita literali `#[k: v]`; `{k: v}` kullanılmadı. | `{` blok başlatıyor ve `{a: T}` TypeBind ile çakışıyor — gramerde gerçek bir belirsizlik. Anahtar `Binary` seviyesinde okunur, böylece `:` TypeBind sanılmaz. |
| 22 | Harita anahtarı `bool` olamaz. | Python sözlüğünde `true` ile `1` aynı anahtara düşerdi; Radian'da `1 == true` yanlış olduğu için bu tutarsız olurdu. |
| 20 | Radian çağrı derinliği yorumlayıcıda sayılır (`MAX_CALL_DEPTH = 1000`), Python'un `RecursionError`'ına bırakılmaz. | Python limiti Radian çağrısı başına ~6 kare tükettiği için sınır 162'ye düşüyordu ve hata mesajı dilin dışındaydı. |
| 19 | `++` / `--` kaldırılmak yerine gerçeklendi: hedef yalnızca IDENTIFIER ya da INDEX olabilir, ihlal **parse zamanında** hata verir. | `symbols.txt` bunları zaten tanımlıyordu; kaldırmak ilan edilen token kümesini daraltırdı. Lvalue denetimini parse zamanında yapmak `--5` gibi girdilere net mesaj verir. |
| 18 | Belgelerdeki çalıştırılabilir örnekler ` ```radian ` ile etiketlenir ve `tests/test_docs.py` tarafından koşulur. | Doküman/kod ayrışması (bu depoda bir kez yaşandı) testle yakalanır. |
| 8 | Dizi indeksleme `a[i]` postfix zincirinde; `[` tek karakterli sembol olarak zaten lexleniyor. | Çağrı/üye erişimiyle aynı katman → `a.b[0](x)` doğal çalışır. |

---

## 3. Oturum günlüğü

### Oturum 1 (2026-08-05)
- Depo incelendi, mevcut durum çıkarıldı, `PROGRESS.md` oluşturuldu.
- Test altyapısı kuruldu: `Prototip/tests/` + `run_tests.py` (56 test, tümü yeşil).
- Lexer: `//` ve `/* */` yorumları, kapatılmamış sabit/yorum ve eksik sayısal
  önek/üs için doğru konumlu net hatalar (67 test yeşil).
- Yorumlayıcı (`interpreter.py`): kapsam zinciri, closure, özyineleme, tip
  doğrulama (tamsayı aralıkları dahil), 14 genel yerleşik + dizi/string/sayı
  metotları, akış denetimi sinyalleri.
- CLI (`radian.py`): dosya çalıştırma, `-c`, `--ast`, `--tokens`, REPL.
- `examples/` altında 6 çalışan örnek program + uçtan uca testler (223 test yeşil).
- Parser: fonksiyon çağrısı + postfix zinciri (`a.b[0](x)`), 11 katmanlı
  operatör önceliği, `if`/`else if`/`while`/`for`/`return`/`break`/`continue`,
  dizi literali ve dizi tipi, bileşik atamalar, iç fonksiyon tanımı (114 test yeşil).
- `Grammer.md`, `Radian.ebnf`, `PARSER_UPDATE_GUIDE.md`, `README.md` ve
  `CLAUDE.md` kodla senkronlandı; belge örnekleri `tests/test_docs.py` ile
  çalıştırılır hale getirildi.
- `++` / `--` gerçeklendi (244 test yeşil).
- Sağlamlık taraması: döngüsel dizi yazdırma çökmesi ve düşük özyineleme
  sınırı düzeltildi; düşmanca girdi tablosu teste dönüştürüldü (256 test yeşil).
- Çalışma zamanı hataları artık çağrı yığını gösteriyor (327 test yeşil).
- Modül sistemi eklendi: `import` ifadesi, göreli yol çözümü, önbellek,
  döngüsel import denetimi, `examples/moduller.rad` + `examples/lib/`
  (323 test yeşil).
- Kayıt tipleri (`struct`) eklendi: kurucu, alan okuma/yazma, tip konumunda
  kullanım, nominal eşitlik, `examples/yapilar.rad` (306 test yeşil).
- Harita tipi eklendi: `#[k: v]` literali, `map()` yerleşiği, 10 metot,
  `for` ile anahtar gezinme, `examples/haritalar.rad` (283 test yeşil).
