"""Dokümantasyon testleri.

Markdown belgelerindeki ```radian etiketli kod blokları gerçekten
çalıştırılır. Böylece belge örnekleri koddan sessizce ayrışamaz:
bir örnek bozulduğunda test kırmızıya döner.

Bir örnek çalıştırılabilir *olmamalıysa* (şematik gösterim, hata örneği)
bloku etiketsiz bırakın.
"""

import io
import os
import unittest

from tests.helpers import PROTOTIP_DIR, SYMBOLS_FILE
from interpreter import Interpreter

REPO_ROOT = os.path.dirname(PROTOTIP_DIR)

DOCS = [
    os.path.join(PROTOTIP_DIR, "Grammer.md"),
    os.path.join(PROTOTIP_DIR, "PARSER_UPDATE_GUIDE.md"),
    os.path.join(REPO_ROOT, "README.md"),
]

FENCE = "```"
RADIAN_FENCE = "```radian"


def radian_blocks(path: str) -> list[tuple[int, str]]:
    """(başlangıç satırı, kaynak) çiftleri — yalnızca ```radian blokları."""
    blocks: list[tuple[int, str]] = []
    inside  = False
    capture = False
    start   = 0
    body: list[str] = []

    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            if line.startswith(FENCE):
                if inside:
                    if capture:
                        blocks.append((start, "".join(body)))
                    inside, capture, body = False, False, []
                else:
                    inside  = True
                    capture = line.strip() == RADIAN_FENCE
                    start   = lineno + 1
                continue
            if capture:
                body.append(line)
    return blocks


class TestDocExamples(unittest.TestCase):

    def test_belgelerdeki_ornekler_calisir(self):
        checked = 0
        for path in DOCS:
            if not os.path.exists(path):
                continue
            for lineno, source in radian_blocks(path):
                where = f"{os.path.basename(path)}:{lineno}"
                with self.subTest(blok=where):
                    Interpreter(out=io.StringIO()).run_source(
                        source, symbols_file=SYMBOLS_FILE)
                checked += 1
        self.assertGreater(checked, 0, "Hiç ```radian bloku bulunamadı")

    def test_grammer_md_ornek_iceriyor(self):
        blocks = radian_blocks(os.path.join(PROTOTIP_DIR, "Grammer.md"))
        self.assertGreaterEqual(len(blocks), 10)


class TestBlockExtractor(unittest.TestCase):
    """Çıkarıcının kendisi — yanlış blok toplarsa testler sessizce boşa döner."""

    def test_etiketsiz_bloklar_atlanir(self):
        path = os.path.join(PROTOTIP_DIR, "Grammer.md")
        for _, source in radian_blocks(path):
            self.assertNotIn("BinaryLevel0", source)   # BNF bloku sızmamalı
            self.assertNotIn("_parse_", source)        # metot haritası sızmamalı


if __name__ == "__main__":
    unittest.main()
