#!/usr/bin/env python3
"""Radian test koşucusu.

Kullanım (Prototip/ dizininden veya depo kökünden):

    python3 Prototip/run_tests.py
    python3 run_tests.py
    python3 run_tests.py -v          # ayrıntılı çıktı
    python3 run_tests.py test_lexer  # tek modül
"""

import os
import sys
import unittest

PROTOTIP_DIR = os.path.dirname(os.path.abspath(__file__))
if PROTOTIP_DIR not in sys.path:
    sys.path.insert(0, PROTOTIP_DIR)


def main(argv: list[str]) -> int:
    verbosity = 2 if "-v" in argv else 1
    names     = [a for a in argv if not a.startswith("-")]

    loader = unittest.TestLoader()
    if names:
        suite = loader.loadTestsFromNames(
            [n if n.startswith("tests.") else f"tests.{n}" for n in names]
        )
    else:
        suite = loader.discover(start_dir=os.path.join(PROTOTIP_DIR, "tests"),
                                top_level_dir=PROTOTIP_DIR)

    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
