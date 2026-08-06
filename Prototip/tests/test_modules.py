"""Modül sistemi testleri — `import` ifadesi."""

import io
import os
import tempfile
import unittest

from tests.helpers import EXAMPLES_DIR, SYMBOLS_FILE
from interpreter import Interpreter, Module, RadianError


class ModuleTestCase(unittest.TestCase):
    """Her test kendi geçici modül dizininde çalışır."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir  = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def write(self, name: str, source: str) -> str:
        path = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(source)
        return path

    def run_main(self, source: str, out=None):
        path = self.write("ana.rad", source)
        interp = Interpreter(out=out or io.StringIO(),
                             symbols_file=SYMBOLS_FILE)
        return interp.run_file(path)


class TestImport(ModuleTestCase):

    def test_modul_degeri_dondurur(self):
        self.write("mat.rad", "kare (x:i32) -> i32 { x * x; }")
        result = self.run_main('m = import "mat.rad"; m;')
        self.assertIsInstance(result, Module)

    def test_fonksiyon_cagirma(self):
        self.write("mat.rad", "kare (x:i32) -> i32 { x * x; }")
        self.assertEqual(self.run_main('m = import "mat.rad"; m.kare(5);'), 25)

    def test_degisken_okuma(self):
        self.write("sabitler.rad", "PI = 3.5;")
        self.assertEqual(self.run_main('s = import "sabitler.rad"; s.PI;'), 3.5)

    def test_yapi_kurucusu_disari_acilir(self):
        self.write("tipler.rad", "struct Nokta (x:i32, y:i32);")
        self.assertEqual(
            self.run_main('t = import "tipler.rad"; t.Nokta(1, 2).y;'), 2)

    def test_modulun_kendi_kapsami_vardir(self):
        self.write("m.rad", "gizli = 42; ac (x:i32) -> i32 { gizli + x; }")
        # Modül içi 'gizli' import edene sızmaz, ama modül üzerinden görünür
        self.assertEqual(self.run_main('m = import "m.rad"; m.ac(1);'), 43)
        with self.assertRaises(RadianError):
            self.run_main('m = import "m.rad"; gizli;')

    def test_yerlesikler_modulde_gorunur(self):
        self.write("m.rad", 'yaz () -> i32 { len("abcd"); }')
        self.assertEqual(self.run_main('m = import "m.rad"; m.yaz();'), 4)

    def test_alt_dizin_yolu(self):
        self.write("lib/yardim.rad", "iki () -> i32 { 2; }")
        self.assertEqual(
            self.run_main('m = import "lib/yardim.rad"; m.iki();'), 2)

    def test_ic_ice_import_kendi_dizinine_gore_cozulur(self):
        self.write("lib/taban.rad", "bir () -> i32 { 1; }")
        self.write("lib/ust.rad",
                   't = import "taban.rad"; iki () -> i32 { t.bir() + 1; }')
        self.assertEqual(
            self.run_main('m = import "lib/ust.rad"; m.iki();'), 2)

    def test_onbellek_ayni_nesneyi_verir(self):
        self.write("sayac.rad", "n = [0]; n.push(1);")
        # İki import bir kez çalıştırmalı → dizi tek bir kez uzar
        self.assertEqual(
            self.run_main('a = import "sayac.rad"; b = import "sayac.rad"; '
                          "a.n.len();"), 2)

    def test_dongusel_import_hatasi(self):
        self.write("a.rad", 'b = import "b.rad";')
        self.write("b.rad", 'a = import "a.rad";')
        with self.assertRaises(RadianError) as ctx:
            self.run_main('m = import "a.rad";')
        self.assertIn("Döngüsel import", str(ctx.exception))

    def test_olmayan_modul(self):
        with self.assertRaises(RadianError) as ctx:
            self.run_main('m = import "yok.rad";')
        self.assertIn("bulunamadı", str(ctx.exception))

    def test_modulde_sozdizimi_hatasi_raporlanir(self):
        self.write("bozuk.rad", "x = ;")
        with self.assertRaises(RadianError) as ctx:
            self.run_main('m = import "bozuk.rad";')
        self.assertIn("sözdizimi hatası", str(ctx.exception))

    def test_yol_str_olmali(self):
        with self.assertRaises(RadianError) as ctx:
            self.run_main("m = import 42;")
        self.assertIn("dosya yolu", str(ctx.exception))

    def test_bilinmeyen_tanim(self):
        self.write("m.rad", "a = 1;")
        with self.assertRaises(RadianError) as ctx:
            self.run_main('m = import "m.rad"; m.yok;')
        self.assertIn("tanımı yok", str(ctx.exception))

    def test_modul_yazdirilabilir(self):
        self.write("m.rad", "a = 1;")
        buffer = io.StringIO()
        self.run_main('m = import "m.rad"; print(m);', out=buffer)
        self.assertIn("<modül m.rad>", buffer.getvalue())

    def test_ornek_kutuphanesi_calisir(self):
        """examples/lib/geometri.rad gerçekten import edilebilmeli."""
        path = os.path.join(EXAMPLES_DIR, "moduller.rad")
        interp = Interpreter(out=io.StringIO(), symbols_file=SYMBOLS_FILE)
        self.assertEqual(interp.run_file(path), 0)


if __name__ == "__main__":
    unittest.main()
