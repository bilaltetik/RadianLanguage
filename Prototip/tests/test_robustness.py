"""Sağlamlık testleri.

Sözleşme: Radian kaynağı ne kadar bozuk olursa olsun, dışarıya **yalnızca**
`ParseError` ya da `RadianError` çıkmalıdır. Ham bir Python istisnası
(TypeError, IndexError, RecursionError…) kullanıcıya sızarsa bu bir hatadır.

Aşağıdaki tablo hem sözdizimsel hem çalışma zamanı sınır durumlarını tarar.
Yeni bir dil özelliği eklerken buraya birkaç bozuk girdi eklemek iyi olur.
"""

import io
import unittest

from tests.helpers import SYMBOLS_FILE
from interpreter import Interpreter, RadianError
from parser import ParseError

# Hepsi ya çalışmalı ya da düzgün bir Radian hatası vermelidir.
HOSTILE_SOURCES = [
    # --- sözdizimi sınırları ---
    "", ";", "}", ")", "]", "{", "(", "[", ".", ",", ":", "=",
    "x", "x =", "= 1;", "f(;", "[1,;", "a.;", "a[];",
    "if;", "if x;", "while;", "for;", "for x in;",
    "return", "break", "continue", "x : ;", "x : (;",
    "f () -> {}", "f (x) -> i32 { x; }", "f (:i32) -> i32 { 1; }",
    "x = {;", "-;", "!;", "1 +;", "* 1;", "a b;", "a ++ b;", "--5;", "f()++;",
    "'ab';", "''", '"a" "b";', '"kapanmamış', "/* kapanmamış",
    "0x;", "1e;", "1.2.3;", "1_x;",

    # --- çalışma zamanı sınırları ---
    "xs = []; xs[0];", "xs = []; xs.pop();", "xs = []; xs.reduce(len);",
    "[1, 'a'].sort();", "print.len();", "1();", "true[0];",
    "x = 1; x.yok;", "[].max();", "min([]);", "range(1, 2, 0);",
    "int('abc');", "float('x');", "1 / 0;", "1 % 0;", "1 << -1;",
    "s = 'a'; s[1];", "[1][true];", "[1]['a'];", "[1][-1];",
    "assert(false);", "type();", "len();", "len(1);",
    "if 1 { 2; };", "while 1 { 2; };", "for x in 1 { 2; };",
    "1 && true;", "!1;", "~1.5;", "'a' + 1;", "[1] - [2];",
    "x : i8 = 200;", "x : u8 = -1;", "x : i32 = true;", 'x : [i32] = [1, "a"];',
    "break;", "continue;", "return 1;",
    "f { break; } f();", "f (a:i32) -> i32 { a; } f();",
    "f { f(); } f();",                       # sonsuz özyineleme
    "x = [1]; x[0] = x; print(x);",          # döngüsel referans

    # --- çalışması beklenenler (yine de çökmemeli) ---
    "((((1))));", "x = 1; x++; ++x;", "main () -> i32 { 0; } main();",
    "f = print; f(1);", "range(0);", "x : yok_tip = 1; x;",
]


class TestHostileInputs(unittest.TestCase):

    def test_yalnizca_radian_hatalari_disari_cikar(self):
        for source in HOSTILE_SOURCES:
            with self.subTest(kaynak=source[:40]):
                try:
                    Interpreter(out=io.StringIO()).run_source(
                        source, symbols_file=SYMBOLS_FILE)
                except (ParseError, RadianError):
                    pass                      # beklenen: düzgün hata
                except Exception as err:      # noqa: BLE001 — kasıtlı geniş yakalama
                    self.fail(f"{type(err).__name__} sızdı: {err!r} "
                              f"(kaynak: {source!r})")

    def test_hata_mesajlari_konum_tasir(self):
        """Konumu bilinen hatalar [satır:sütun] eki taşımalı."""
        cases = ["yok + 1;", "1 / 0;", "xs = []; xs[0];", "1();"]
        for source in cases:
            with self.subTest(kaynak=source):
                with self.assertRaises(RadianError) as ctx:
                    Interpreter(out=io.StringIO()).run_source(
                        source, symbols_file=SYMBOLS_FILE)
                self.assertRegex(str(ctx.exception), r"\[\d+:\d+\]")

    def test_bos_program_unit_dondurur(self):
        from interpreter import UNIT
        result = Interpreter(out=io.StringIO()).run_source(
            "", symbols_file=SYMBOLS_FILE)
        self.assertIs(result, UNIT)

    def test_yalnizca_yorumdan_olusan_program(self):
        from interpreter import UNIT
        result = Interpreter(out=io.StringIO()).run_source(
            "// yalnızca yorum\n/* ve blok */", symbols_file=SYMBOLS_FILE)
        self.assertIs(result, UNIT)

    def test_uzun_ifade_zinciri(self):
        """Derin ifade iç içeliği yorumlayıcı yığınını taşırmamalı."""
        source = "x = " + " + ".join(str(i) for i in range(500)) + ";"
        result = Interpreter(out=io.StringIO()).run_source(
            source, symbols_file=SYMBOLS_FILE)
        self.assertEqual(result, sum(range(500)))

    def test_derin_parantez(self):
        source = "(" * 100 + "1" + ")" * 100 + ";"
        result = Interpreter(out=io.StringIO()).run_source(
            source, symbols_file=SYMBOLS_FILE)
        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
