# Radian Language — Geliştirme İlerlemesi

Bu dosya otonom geliştirme oturumlarının hafızasıdır. Her adım tamamlandığında
güncellenir. Durum işaretleri: `[ ]` yapılacak · `[~]` devam ediyor · `[x]` tamam.

**Güncel durum:** lexer + parser + yorumlayıcı + CLI/REPL çalışıyor.
`cd Prototip && python3 run_tests.py` → **341 test, tümü yeşil**.

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
- Parser bitişik sembolleri birleştirdiği için `a + -b` ifadesi `a +- b` oluyordu.
- `++` / `--` `symbols.txt`'de tanımlıydı ama dilde karşılığı yoktu.

---

## 1. Yol haritası

### Faz 1 — Altyapı
- [x] `PROGRESS.md` oluştur, yol haritasını çıkar.
- [x] `assert` tabanlı test altyapısı (`Prototip/tests/`, stdlib `unittest`).
- [x] `run_tests.py` — tek komutla tüm testleri çalıştır.

### Faz 2 — Bilinen bug'lar / yarım kalan özellikler
- [x] Lexer: `//` satır ve `/* */` blok yorumları.
- [x] Lexer: kapatılmamış string/char hatası token başlangıcını göstersin.
- [x] Lexer: eksik/hatalı sayısal önek (`0x`, `1e`) için net hata.
- [x] Parser: `_parse_call` — `f(x, y)` → `CALL` düğümü (doküman driftı kapandı).
- [x] Parser: `_parse_literal` artık gelişigüzel sembolü literal kabul etmiyor.
- [x] Parser: operatör birleştirme kaldırıldı (`a + -b` düzeldi).
- [x] `++` / `--` gerçeklendi (`PRE_OP` / `POST_OP`, lvalue denetimi parse zamanında).

### Faz 3 — Dil özellikleri
- [x] Operatör öncelik katmanları (11 katman, `**` sağ-çağrışımlı).
- [x] Üye erişimi `a.b`, indeksleme `a[i]`, çağrı zinciri `a.b[0](x)`.
- [x] `if` / `else if` / `else`, `while`, `for … in` — hepsi ifade.
- [x] `return`, `break`, `continue`.
- [x] `true` / `false` boolean literalleri.
- [x] Tree-walking yorumlayıcı (`interpreter.py`).
- [x] CLI + REPL: `radian.py` (`-c`, `--ast`, `--tokens`).
- [x] Yerleşik fonksiyonlar (`print`, `len`, `range`, `assert`, …).
- [x] Dizi literalleri, dizi tipi `[T]`, dizi metotları (`map`/`filter`/`reduce`…).
- [x] Closure, özyineleme, yüksek mertebeden fonksiyonlar, currying.
- [x] String metotları ve `str`/`int`/`float`/`bool` dönüşümleri.
- [x] Harita (map) tipi: `#[k: v]` literali, indeksleme/atama, 10 metot.
- [x] `struct` / kayıt tipleri: kurucu, alan okuma/yazma, tip konumunda kullanım.
- [x] Modül / `import` sistemi (ifade biçiminde, önbellekli, döngü denetimli).

### Faz 4 — Test kapsamı
- [x] Lexer, parser, yorumlayıcı birim testleri.
- [x] Uçtan uca `examples/*.rad` + CLI testleri (alt süreçle).
- [x] Sağlamlık testi: bozuk girdiden yalnızca `ParseError`/`RadianError` çıkar.
- [x] Modül testleri (geçici dizinlerde gerçek dosyalarla).
- [x] Belge testleri: ` ```radian ` blokları gerçekten çalıştırılır.

### Faz 5 — Kalite / dokümantasyon
- [x] `Grammer.md` ve `Radian.ebnf` kodla senkron.
- [x] `PARSER_UPDATE_GUIDE.md` kodla senkron (sürüm 2.0).
- [x] Kök `README.md` gerçek içerik.
- [x] `CLAUDE.md` güncel mimariyi anlatıyor.

### Faz 6 — Sağlamlık
- [x] Döngüsel dizi/harita/yapı referansı yazdırılabiliyor, çökmüyor.
- [x] Özyineleme derinliği 162 → 1000 (kendi sayacımız + net Radian hatası).
- [x] Çalışma zamanı hatalarında çağrı yığını (`RadianError.frames`).

### Faz 7 — Örnekler ve sonraki adımlar
- [x] `ord` / `chr` yerleşikleri.
- [x] Deyim başındaki blok-kuyruklu yapı hatası düzeltildi (aşağıdaki karar 28).
- [x] Daha fazla örnek script: `algoritmalar`, `metin_isleme`, `veri_yapilari`,
      `oyun_hayat`, `matris` + `lib/liste.rad` (14 örnek, hepsi kendi kendini
      `assert` ile doğruluyor ve testlerde koşuluyor).
- [ ] **Statik tip denetleyicisi** — parse sonrası ayrı geçiş; şu an tüm denetim
      çalışma zamanında. En büyük ve en değerli sonraki adım.
- [ ] Opsiyonel tip `T?` ve `unit` tipinin dilde adlandırılması.
- [ ] Generic tipler `T<A>` (TypeExpr'de büyük genişletme).
- [ ] `else if` dışında `match` / desen eşleme.
- [ ] Yapılara metot bağlama (`impl` benzeri) — şu an yalnızca serbest fonksiyon.
- [ ] Standart kütüphane modülleri (`examples/lib/` yerine gerçek `lib/`).
- [ ] Bytecode VM / kod üretimi (yorumlayıcı referans gerçekleme olarak kalır).

---

## 2. Tasarım kararları

| # | Karar | Gerekçe |
|---|-------|---------|
| 1 | Binary operatör yalnızca `LITERAL_SYMB` olabilir; identifier operatör değildir. | `f (x)` çağrısı ile `a b` "operatörü" arasındaki belirsizliği kaldırır. Eski davranış zaten bozuktu (`a b;` anlamsız AST üretiyordu). |
| 2 | Öncelik tablosu sabit; tabloda olmayan semboller en düşük binary seviyeye düşer. | `symbols.txt`'e yeni sembol eklemek hâlâ parser değişikliği gerektirmiyor. |
| 3 | Yorumlar lexer seviyesinde tamamen atılır (token üretilmez). | Parser'ın yorumdan haberi olmasına gerek yok. |
| 4 | `if`/`while`/`for`/blok birer *expression*; değer döndürürler. | `Grammer.md` §3.1'deki "blok son statement'ın değerini döndürür" semantiğiyle tutarlı. |
| 5 | Yorumlayıcı dinamik tipli; `:` tip bağlama çalışma zamanında **doğrulanır**, zorlama yapmaz. | Statik tip denetleyicisi ayrı bir faz; erken tip zorlaması dili kullanılmaz hale getirirdi. |
| 6 | `return`/`break`/`continue` Python exception'ı ile taşınır; döngü sinyali fonksiyon sınırını aşamaz. | Tree-walking yorumlayıcıda standart ve en basit yöntem. |
| 7 | Keyword'ler ayrı bir `TokenType` değil; parser `LITERAL_IDEN` değerine bakar. | Lexer'ı dilden bağımsız tutar (mevcut konvansiyon). |
| 8 | Dizi indeksleme `a[i]` postfix zincirinde. | Çağrı/üye erişimiyle aynı katman → `a.b[0](x)` doğal çalışır. |
| 9 | Parser bitişik sembol token'larını birleştirmez; operatör = tek token. | Eski birleştirme `a + -b` ifadesini `a +- b` yapıyordu. Çok karakterli operatör = `symbols.txt` satırı. |
| 10 | Unary operatörler sabit bir kümeyle sınırlı (`- + ! ~`). | Eskiden "ardında terim olan her sembol" unary sayılıyordu; `* x` sessizce kabul ediliyordu. |
| 11 | `if`/`while`/`for`/blok ile biten statement'larda `;` opsiyonel. | Rust benzeri; `if a { … }` sonuna `;` koymak zorunda kalmamak. |
| 12 | Bileşik atamalar (`+=`, `<<=` …) Assign katmanında; yorumlayıcı `a = a op b` olarak çözer. | Binary katmanına düşseydi `a += 1` anlamsız bir binary düğüm üretirdi. |
| 13 | Diziler, haritalar ve yapılar referans değerdir; atama kopya çıkarmaz. | Yerinde değişen metotlar (`push`, alan ataması) için tek tutarlı semantik. |
| 14 | Tamsayı bölmesi C semantiğinde (sıfıra doğru kırpar), `%` işareti bölünene uyar. | Sistem dili hedefi; `7 / 2 == 3`, `-7 / 2 == -3`. |
| 15 | Negatif indeks hatadır (sondan sayma yok). | Sınır dışı erişimi sessizce başka bir elemana çevirmemek için. |
| 16 | `main` tanımlıysa otomatik çağrılır; 0..255 arası dönüş değeri süreç çıkış kodudur. | Dokümanlardaki `main () -> i32 { … }` örneğini anlamlı kılmak için. |
| 17 | İfade konumundaki primitive tip adı (`bool`, `char`) aynı adlı bir değer varsa ona çözülür. | `bool(x)` dönüşüm fonksiyonu ile `x : bool` tip adı çakışmasın diye. |
| 18 | Belgelerdeki çalıştırılabilir örnekler ` ```radian ` ile etiketlenir ve testlerde koşulur. | Doküman/kod ayrışması (bu depoda bir kez yaşandı) testle yakalanır. |
| 19 | `++` / `--` kaldırılmak yerine gerçeklendi; hedef yalnızca IDENTIFIER ya da INDEX, ihlal **parse zamanında** hata. | `symbols.txt` bunları zaten tanımlıyordu; kaldırmak ilan edilen token kümesini daraltırdı. |
| 20 | Radian çağrı derinliği yorumlayıcıda sayılır (`MAX_CALL_DEPTH = 1000`). | Python limiti Radian çağrısı başına ~6 kare tükettiği için sınır 162'ye düşüyordu ve hata mesajı dilin dışındaydı. |
| 21 | Harita literali `#[k: v]`; `{k: v}` kullanılmadı. | `{` blok başlatıyor ve `{a: T}` TypeBind ile çakışıyor — gerçek bir gramer belirsizliği. Anahtar `Binary` seviyesinde okunur. |
| 22 | Harita anahtarı `bool` olamaz. | Python sözlüğünde `true` ile `1` aynı anahtara düşerdi; Radian'da `1 == true` yanlış olduğu için tutarsız olurdu. |
| 23 | `struct Ad (alanlar);` fonksiyon imzasıyla aynı `TypeParamList` dilbilgisini kullanır; yapı adı aynı zamanda kurucudur. | Yeni sözdizimi yüzeyi en aza iner: mevcut `CALL` ve `MEMBER` düğümleri kullanılır. |
| 24 | Yapı eşitliği nominaldir: aynı `StructType` + alan alan karşılaştırma. | Yapı adı bir tip kimliğidir; alanları aynı olan iki farklı yapı eşit değildir. |
| 25 | `import` bir ifadedir ve modül değeri döndürür; ad alanı `modül.ad` üzerinden gelir. | Bildirim biçimi yeni sözdizimi ve isim çakışması getirirdi; ifade biçimi modülü birinci sınıf değer yapar. |
| 26 | Modül yolu import eden dosyanın dizinine göre çözülür; modüller gerçek yola göre önbelleğe alınır. | Kütüphane dosyaları komşularını çalışma dizininden bağımsız import edebilsin diye. |
| 28 | Bir statement blokla biten bir yapıyla başlıyorsa orada biter; operatör zinciri sürdürülmez (Rust'taki kural). | `while … { }` satırından sonra gelen `-1;` ifadesi sessizce `(while …) - 1` olarak okunuyordu — `examples/algoritmalar.rad` yazarken yakalandı. |
| 27 | Çalışma zamanı hataları çağrı yığınını hata yayılırken toplar (`RadianError.frames`). | Yığını raise anında kurmak her hata noktasında ek kod isterdi; `call()` içinde tek yerde yakalanıp zenginleştirilir. |

---

## 3. Oturum günlüğü

### Oturum 1 (2026-08-05)

Sırasıyla yapılanlar (her adım sonunda testler yeşil bırakıldı):

1. Depo incelendi, mevcut durum çıkarıldı, `PROGRESS.md` oluşturuldu.
2. Test altyapısı kuruldu: `tests/` + `run_tests.py` — 56 test.
3. Lexer: yorumlar, kapatılmamış sabit/yorum ve eksik sayısal önek/üs
   hataları — 67 test.
4. Parser yeniden yazıldı: fonksiyon çağrısı, postfix zinciri, 11 katmanlı
   öncelik, akış denetimi, dizi literali/tipi, bileşik atamalar — 114 test.
5. Yorumlayıcı + CLI + `examples/` — 223 test.
6. Tüm dokümanlar kodla senkronlandı; belge örnekleri test edilir oldu — 226 test.
7. `++` / `--` gerçeklendi — 244 test.
8. Sağlamlık taraması: döngüsel gösterim çökmesi ve düşük özyineleme sınırı
   düzeltildi, düşmanca girdi tablosu teste dönüştürüldü — 256 test.
9. Harita tipi — 283 test.
10. Kayıt tipleri (`struct`) — 306 test.
11. Modül sistemi (`import`) — 323 test.
12. Çalışma zamanı hatalarında çağrı yığını — 327 test.

**Sonraki oturum buradan devam etsin:** Faz 7'nin ilk maddesi (statik tip
denetleyicisi). Öneri: `checker.py` içinde AST üzerinde ayrı bir geçiş; önce
yalnızca *bildirilmiş* tipleri denetle (değişken, parametre, dönüş), çıkarım
(inference) ikinci adımda. Çalışma zamanı denetimleri kaldırılmamalı — ikisi
birbirini tamamlar.
