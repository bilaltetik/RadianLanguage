#!/usr/bin/env python3
"""
Radian komut satırı aracı.

Kullanım:

    python3 radian.py dosya.rad         # dosyayı çalıştır
    python3 radian.py -c "print(1);"    # tek satırlık kaynağı çalıştır
    python3 radian.py                   # REPL (etkileşimli kabuk)

    python3 radian.py --tokens dosya.rad   # yalnızca token akışını yazdır
    python3 radian.py --ast    dosya.rad   # yalnızca AST'yi yazdır
    python3 radian.py --check  dosya.rad   # statik denetim (çalıştırmadan)

Çıkış kodu: programın değeri 0..255 aralığında bir tamsayıysa o değer,
hata durumunda 1, aksi halde 0.
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from checker import check_source                                     # noqa: E402
from interpreter import Interpreter, RadianError, UNIT, to_display   # noqa: E402
from lexer import lexer                                              # noqa: E402
from parser import ParseError, Parser, parse_source                  # noqa: E402

SYMBOLS_FILE = os.path.join(SCRIPT_DIR, "symbols.txt")

USAGE = __doc__.strip()


# ---------------------------------------------------------------------------
# Alt komutlar
# ---------------------------------------------------------------------------

def dump_tokens(source: str, base_dir: str | None = None) -> int:
    result = lexer(source, symbols_file=SYMBOLS_FILE)
    if isinstance(result, dict):
        print(f"Sözcüksel hata [{result['line']}:{result['column']}]: "
              f"{result['error']}", file=sys.stderr)
        return 1
    for tok in result:
        print(tok)
    return 0


def dump_ast(source: str, base_dir: str | None = None) -> int:
    try:
        print(parse_source(source, symbols_file=SYMBOLS_FILE), end="")
    except ParseError as err:
        print(f"Sözdizimi hatası: {err}", file=sys.stderr)
        return 1
    return 0


def check_only(source: str, base_dir: str | None = None) -> int:
    """Statik denetim — programı çalıştırmaz."""
    try:
        bulgular = check_source(source, symbols_file=SYMBOLS_FILE)
    except ParseError as err:
        print(f"Sözdizimi hatası: {err}", file=sys.stderr)
        return 1

    for bulgu in bulgular:
        print(f"Tip hatası: {bulgu}", file=sys.stderr)
    if bulgular:
        print(f"\n{len(bulgular)} bulgu", file=sys.stderr)
        return 1
    print("Denetim temiz")
    return 0


def run_source(source: str, base_dir: str | None = None) -> int:
    interp = Interpreter(base_dir=base_dir, symbols_file=SYMBOLS_FILE)
    try:
        value = interp.run_source(source)
    except ParseError as err:
        print(f"Sözdizimi hatası: {err}", file=sys.stderr)
        return 1
    except RadianError as err:
        print(f"Çalışma zamanı hatası: {err}", file=sys.stderr)
        trace = err.traceback_text()
        if trace:
            print(trace, file=sys.stderr)
        return 1
    except RecursionError:
        print("Çalışma zamanı hatası: özyineleme derinliği aşıldı",
              file=sys.stderr)
        return 1

    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 255:
        return value
    return 0


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------

def _is_complete(source: str) -> bool:
    """Girdi tamamlanmış mı? (parantez/blok dengesi ve sonlandırıcı)"""
    depth   = 0
    in_str  = None
    escaped = False
    for ch in source:
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in "\"'":
            in_str = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
    if in_str or depth > 0:
        return False
    return source.rstrip().endswith((";", "}"))


def repl() -> int:
    interp = Interpreter(symbols_file=SYMBOLS_FILE)
    print("Radian REPL — çıkmak için Ctrl-D (ya da 'exit')")
    buffer = ""

    while True:
        prompt = "radian> " if not buffer else "   ...> "
        try:
            line = input(prompt)
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print("\n(iptal edildi)")
            buffer = ""
            continue

        if not buffer and line.strip() in ("exit", "quit"):
            return 0

        buffer += line + "\n"
        if not _is_complete(buffer):
            continue

        source, buffer = buffer, ""
        try:
            value = interp.run_source(source)
            if value is not UNIT:
                print(to_display(value))
        except ParseError as err:
            print(f"Sözdizimi hatası: {err}", file=sys.stderr)
        except RadianError as err:
            print(f"Çalışma zamanı hatası: {err}", file=sys.stderr)
            trace = err.traceback_text()
            if trace:
                print(trace, file=sys.stderr)
        except RecursionError:
            print("Çalışma zamanı hatası: özyineleme derinliği aşıldı",
                  file=sys.stderr)


# ---------------------------------------------------------------------------
# Giriş noktası
# ---------------------------------------------------------------------------

MODES = {
    "run":    run_source,
    "tokens": dump_tokens,
    "ast":    dump_ast,
    "check":  check_only,
}

def main(argv: list[str]) -> int:
    mode = "run"
    args = list(argv)

    while args and args[0].startswith("-"):
        flag = args.pop(0)
        if flag in ("-h", "--help"):
            print(USAGE)
            return 0
        if flag == "--tokens":
            mode = "tokens"
        elif flag == "--ast":
            mode = "ast"
        elif flag == "--check":
            mode = "check"
        elif flag == "-c":
            if not args:
                print("-c seçeneği bir kaynak metin bekler", file=sys.stderr)
                return 1
            source = args.pop(0)
            return MODES[mode](source)
        else:
            print(f"Bilinmeyen seçenek: {flag}\n\n{USAGE}", file=sys.stderr)
            return 1

    if not args:
        if mode != "run":
            print("Bu seçenek bir dosya ya da -c bekler", file=sys.stderr)
            return 1
        return repl()

    path = args[0]
    if not os.path.exists(path):
        print(f"Dosya bulunamadı: {path}", file=sys.stderr)
        return 1

    with open(path, encoding="utf-8") as fh:
        source = fh.read()

    # Göreli import'lar çalıştırılan dosyanın dizinine göre çözülür.
    base_dir = os.path.dirname(os.path.abspath(path))
    return MODES[mode](source, base_dir)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
