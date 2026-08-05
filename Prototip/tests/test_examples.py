"""Uçtan uca testler — examples/*.rad dosyaları ve CLI.

Her örnek gerçekten çalıştırılır; hata vermemesi ve beklenen çıktı
parçalarını üretmesi denetlenir. Yeni bir örnek eklendiğinde buraya da
bir (dosya, beklenen parçalar) girdisi eklenmelidir.
"""

import io
import os
import subprocess
import sys
import unittest

from tests.helpers import EXAMPLES_DIR, PROTOTIP_DIR, SYMBOLS_FILE
from interpreter import Interpreter

RADIAN_CLI = os.path.join(PROTOTIP_DIR, "radian.py")

# ( dosya adı, çıktıda mutlaka geçmesi gereken parçalar )
EXAMPLES = [
    ("hello.rad",     ["Merhaba, Dünya!"]),
    ("fibonacci.rad", ["0 1 1 2 3 5 8 13 21 34", "doğrulandı"]),
    ("fizzbuzz.rad",  ["1 2 Fizz 4 Buzz Fizz 7 8 Fizz Buzz 11 Fizz 13 14 FizzBuzz"]),
    ("tipler.rad",    ["yas = 42", "kareler: [1, 4, 9]", "ikiyle_carp(21) = 42"]),
    ("diziler.rad",   ["toplam  : 55", "sesli harf sayısı: 3",
                       'kelimeler: ["radian", "dili", "hızlıdır"]']),
    ("closure.rad",   ["a: 1 2 3", "b: 1", "kasa: 110 115"]),
]


def run_example(filename: str) -> str:
    path = os.path.join(EXAMPLES_DIR, filename)
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    buffer = io.StringIO()
    Interpreter(out=buffer).run_source(source, symbols_file=SYMBOLS_FILE)
    return buffer.getvalue()


class TestExamples(unittest.TestCase):

    def test_tum_ornekler_kayitli(self):
        """examples/ içindeki her .rad dosyasının bir testi olmalı."""
        on_disk = {f for f in os.listdir(EXAMPLES_DIR) if f.endswith(".rad")}
        self.assertEqual(on_disk, {name for name, _ in EXAMPLES})


def _make_test(filename: str, expected: list[str]):
    def test(self):
        output = run_example(filename)
        for part in expected:
            self.assertIn(part, output)
    test.__name__ = f"test_{filename.replace('.', '_')}"
    return test


for _name, _expected in EXAMPLES:
    setattr(TestExamples, f"test_{_name.replace('.', '_')}",
            _make_test(_name, _expected))


class TestCLI(unittest.TestCase):
    """radian.py komut satırı arayüzü — gerçek alt süreçle."""

    def _cli(self, *args, cwd=None):
        return subprocess.run(
            [sys.executable, RADIAN_CLI, *args],
            capture_output=True, text=True,
            cwd=cwd or os.path.dirname(PROTOTIP_DIR),
        )

    def test_dosya_calistirma(self):
        proc = self._cli(os.path.join(EXAMPLES_DIR, "hello.rad"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Merhaba, Dünya!", proc.stdout)

    def test_c_secenegi(self):
        proc = self._cli("-c", 'print(6 * 7);')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "42")

    def test_cikis_kodu_program_degeridir(self):
        proc = self._cli("-c", "main () -> i32 { 3; }")
        self.assertEqual(proc.returncode, 3)

    def test_sozdizimi_hatasi_kodu(self):
        proc = self._cli("-c", "x = ;")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Sözdizimi hatası", proc.stderr)

    def test_calisma_zamani_hatasi_kodu(self):
        proc = self._cli("-c", "yok + 1;")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Çalışma zamanı hatası", proc.stderr)

    def test_sozcuksel_hata_kodu(self):
        proc = self._cli("--tokens", "-c", '"kapanmamış')
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Sözcüksel hata", proc.stderr)

    def test_tokens_secenegi(self):
        proc = self._cli("--tokens", "-c", "x = 1;")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("LITERAL_IDEN", proc.stdout)

    def test_ast_secenegi(self):
        proc = self._cli("--ast", "-c", "x = 1;")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("[ASSIGN]", proc.stdout)

    def test_olmayan_dosya(self):
        proc = self._cli("yok_boyle_bir_dosya.rad")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("bulunamadı", proc.stderr)

    def test_yardim(self):
        proc = self._cli("--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Kullanım", proc.stdout)

    def test_repl_stdin_ile(self):
        proc = subprocess.run(
            [sys.executable, RADIAN_CLI],
            input="1 + 2;\nexit\n", capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("3", proc.stdout)


if __name__ == "__main__":
    unittest.main()
