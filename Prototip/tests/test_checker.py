"""Statik denetleyici testleri (`checker.py`).

İki yönlü sözleşme:
  - Bildirilen her bulgu **gerçek** bir hata olmalı (yanlış alarm yok);
    `TestNoFalsePositives` bunu tüm örnekler ve geniş bir doğru program
    tablosu üzerinde denetler.
  - Yakalanabilecek hatalar gerçekten yakalanmalı (`TestDiagnostics`).
"""

import os
import unittest

from tests.helpers import EXAMPLES_DIR, SYMBOLS_FILE
from checker import CheckError, check_source


def check(src: str) -> list[CheckError]:
    return check_source(src, symbols_file=SYMBOLS_FILE)


def messages(src: str) -> str:
    return " | ".join(str(e) for e in check(src))


# Denetimden temiz geçmesi gereken programlar
TEMIZ = [
    "x = 1; y = x + 2;",
    'kare (x:i32) -> i32 { x * x; } kare(4);',
    "x : i32 = 42; x = 7;",
    "x : f64 = 3;",                                  # int → float genişlemesi
    "xs : [i32] = [1, 2, 3]; xs[0] + 1;",
    'm = #["a": 1]; m["a"]; m.keys();',
    "struct N (x:i32, y:i32); p = N(1, 2); p.x + p.y;",
    "struct N (x:i32); p = N(1); p.x = 5;",
    "f (a:i32) -> i32 { if a < 0 { return -a; } a; } f(-1);",
    "topla (a:i32, b:i32) -> i32 { a + b; } [1, 2].reduce(topla);",
    "sonra () -> i32 { once(); } once () -> i32 { 1; }",   # ileri başvuru
    "sayac { n = 0; artir { n += 1; n; } artir; } c = sayac(); c();",
    'g = import "yok.rad"; g.herhangi_bir_sey(1, 2, 3);',  # modül içi izlenmez
    "x = 1; x = 1.5;",                               # tip değişimi → bilinmiyor
    "for c in \"abc\" { print(c); }",
    "i = 0; while i < 3 { i++; } print(i);",
    'print("a", 1, true);',                          # serbest arite
    "s = str(42); s.upper();",
    "b = bool(1); if b { 1; }",
    "xs = []; xs.push(1); xs.len();",
    "t = 0; for x in [1, 2] { t += x; } t;",
    "f () -> i32 { i = 0; while i < 3 { i++; } 0; } f();",
    "struct V (x:f64); u (v:V) -> f64 { v.x; } u(V(1.0));",
    "yerel { ic (a:i32) -> i32 { a; } ic(1); } yerel();",
]


class TestNoFalsePositives(unittest.TestCase):

    def test_dogru_programlar_temiz_gecer(self):
        for src in TEMIZ:
            with self.subTest(kaynak=src[:48]):
                self.assertEqual(check(src), [], messages(src))

    def test_ornekler_temiz_gecer(self):
        """examples/ altındaki her program (lib/ dahil) denetimden geçmeli."""
        paths = [os.path.join(EXAMPLES_DIR, f)
                 for f in sorted(os.listdir(EXAMPLES_DIR)) if f.endswith(".rad")]
        lib = os.path.join(EXAMPLES_DIR, "lib")
        paths += [os.path.join(lib, f)
                  for f in sorted(os.listdir(lib)) if f.endswith(".rad")]

        for path in paths:
            with self.subTest(dosya=os.path.basename(path)):
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
                self.assertEqual(check(source), [],
                                 " | ".join(str(e) for e in check(source)))


class TestDiagnostics(unittest.TestCase):

    def assertBulgu(self, src: str, parca: str):
        found = messages(src)
        self.assertIn(parca, found, f"{src!r} → {found!r}")

    def test_tanimsiz_degisken(self):
        self.assertBulgu("x = yok + 1;", "Tanımsız değişken: 'yok'")

    def test_tanimsiz_fonksiyon(self):
        self.assertBulgu("yok_boyle(1);", "Tanımsız değişken: 'yok_boyle'")

    def test_arguman_sayisi(self):
        self.assertBulgu("f (a:i32) -> i32 { a; } f(1, 2);",
                         "'f' 1 argüman bekliyor, 2 verildi")

    def test_arguman_tipi(self):
        self.assertBulgu('f (a:i32) -> i32 { a; } f("abc");',
                         "'a' parametresi tamsayı ama str verildi")

    def test_donus_tipi(self):
        self.assertBulgu('f () -> i32 { "abc"; }',
                         "dönüş tipi tamsayı bildirilmiş ama str döndürülüyor")

    def test_return_deyimi_donus_tipiyle_denetlenir(self):
        self.assertBulgu('f () -> i32 { return "x"; }',
                         "dönüş tipi tamsayı bildirilmiş ama str döndürülüyor")

    def test_if_kosulu_bool_olmali(self):
        self.assertBulgu("if 1 { 2; }", "'if' bool bekler, tamsayı bulundu")

    def test_while_kosulu_bool_olmali(self):
        self.assertBulgu('while "a" { 1; }', "'while' bool bekler")

    def test_mantiksal_operator_bool_ister(self):
        self.assertBulgu("x = 1 && true;", "'&&' bool bekler")
        self.assertBulgu("x = !5;", "'!' bool bekler")

    def test_bildirilmis_tipe_uyumsuz_atama(self):
        self.assertBulgu('x : i32 = "abc";',
                         "'x' tamsayı olarak bildirilmiş ama str atanıyor")

    def test_bildirilmis_tip_sonraki_atamada_da_gecerli(self):
        self.assertBulgu('x : i32 = 1; x = "abc";', "'x' tamsayı")

    def test_dizi_tipi_uyumsuzlugu(self):
        self.assertBulgu('xs : [i32] = ["a"];', "'xs'")

    def test_aritmetik_operator_tipi(self):
        self.assertBulgu('y = 1 + "a";',
                         "'+' operatörü tamsayı ve str için tanımlı değil")

    def test_karsilastirma_operator_tipi(self):
        self.assertBulgu("y = true < 1;", "'<' operatörü")

    def test_bit_operatoru_tamsayi_ister(self):
        self.assertBulgu('y = "a" & 1;', "'&' operatörü tamsayı bekler")

    def test_bilinmeyen_yapi_alani(self):
        self.assertBulgu("struct N (x:i32); p = N(1); p.z;",
                         "'N' yapısının 'z' alanı yok")

    def test_yapi_alan_atamasi_tipi(self):
        self.assertBulgu('struct N (x:i32); p = N(1); p.x = "a";',
                         "'N.x' alanı tamsayı ama str atanıyor")

    def test_yapi_kurucu_arite(self):
        self.assertBulgu("struct N (x:i32, y:i32); N(1);",
                         "2 argüman bekliyor, 1 verildi")

    def test_bilinmeyen_metot(self):
        self.assertBulgu("xs = [1]; xs.yok();", "'yok' metodu yok")
        self.assertBulgu('s = "a"; s.push(1);', "'push' metodu yok")

    def test_indekslenemeyen_deger(self):
        self.assertBulgu("b = true; b[0];", "bool indekslenemez")

    def test_dizi_indeksi_tamsayi_olmali(self):
        self.assertBulgu('xs = [1]; xs["a"];', "Dizi indeksi tamsayı olmalı")

    def test_yerlesik_arite(self):
        self.assertBulgu("len();", "'len' 1 argüman bekliyor, 0 verildi")
        self.assertBulgu("range(1, 2, 3, 4);", "'range' 1..3 argüman bekliyor")

    def test_cagrilamaz_deger(self):
        self.assertBulgu("x = 1; x();", "çağrılabilir değil")

    def test_uzerinde_donulemeyen_deger(self):
        self.assertBulgu("for x in 42 { x; }", "üzerinde döngü kurulamaz")

    def test_bulgular_konum_tasir(self):
        errors = check("x = 1;\ny = yok;")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].line, 2)

    def test_bulgular_konuma_gore_sirali(self):
        errors = check("a = yok1;\nb = yok2;\nc = yok3;")
        self.assertEqual([e.line for e in errors], [1, 2, 3])

    def test_birden_fazla_bulgu_toplanir(self):
        # İlk hatada durmaz
        self.assertGreaterEqual(len(check('x : i32 = "a"; if 1 { yok; }')), 3)


if __name__ == "__main__":
    unittest.main()
