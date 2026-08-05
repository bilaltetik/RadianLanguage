"""Lexer birim testleri."""

import unittest

from tests.helpers import TokenType, lex_error, token_pairs, tokenize

NUM  = TokenType.LITERAL_NUM
STR  = TokenType.LITERAL_STR
CHR_ = TokenType.LITERAL_CHAR
IDEN = TokenType.LITERAL_IDEN
SYMB = TokenType.LITERAL_SYMB


class TestBasicTokens(unittest.TestCase):

    def test_bos_girdi(self):
        self.assertEqual(token_pairs(""), [])

    def test_sadece_bosluk(self):
        self.assertEqual(token_pairs("   \t\n  "), [])

    def test_identifier(self):
        self.assertEqual(token_pairs("abc"), [(IDEN, "abc")])

    def test_alt_cizgi_ile_baslayan_identifier(self):
        self.assertEqual(token_pairs("_gizli_1"), [(IDEN, "_gizli_1")])

    def test_identifier_rakamla_bitebilir(self):
        self.assertEqual(token_pairs("x1 y2"), [(IDEN, "x1"), (IDEN, "y2")])

    def test_unicode_identifier(self):
        self.assertEqual(token_pairs("değişken"), [(IDEN, "değişken")])


class TestNumbers(unittest.TestCase):

    def test_tamsayi(self):
        self.assertEqual(token_pairs("42"), [(NUM, "42")])

    def test_ondalik(self):
        self.assertEqual(token_pairs("3.14"), [(NUM, "3.14")])

    def test_us_gosterimi(self):
        self.assertEqual(token_pairs("3.14e-2"), [(NUM, "3.14e-2")])
        self.assertEqual(token_pairs("1E+9"), [(NUM, "1E+9")])

    def test_alt_cizgi_ayraci_atilir(self):
        self.assertEqual(token_pairs("1_000_000"), [(NUM, "1000000")])

    def test_onekler(self):
        self.assertEqual(token_pairs("0xFF"), [(NUM, "0xFF")])
        self.assertEqual(token_pairs("0b1010"), [(NUM, "0b1010")])
        self.assertEqual(token_pairs("0o755"), [(NUM, "0o755")])

    def test_sayi_ardindan_sembol(self):
        self.assertEqual(token_pairs("42+1"),
                         [(NUM, "42"), (SYMB, "+"), (NUM, "1")])

    def test_ikinci_nokta_hata(self):
        self.assertIn("nokta", lex_error("1.2.3")["error"])

    def test_ciftlenmis_us_hata(self):
        self.assertIn("üs", lex_error("1e2e3")["error"])

    def test_gecersiz_alt_cizgi(self):
        self.assertIn("alt çizgi", lex_error("1_x")["error"])

    def test_gecersiz_onek(self):
        self.assertIn("önek", lex_error("12x3")["error"])

    def test_rakamsiz_onek_hata(self):
        self.assertIn("rakam", lex_error("0x")["error"])
        self.assertIn("rakam", lex_error("0b + 1")["error"])

    def test_rakamsiz_us_hata(self):
        self.assertIn("rakam", lex_error("1e")["error"])
        self.assertIn("rakam", lex_error("1e+ 2")["error"])


class TestStringsAndChars(unittest.TestCase):

    def test_basit_string(self):
        self.assertEqual(token_pairs('"merhaba"'), [(STR, '"merhaba"')])

    def test_kacis_dizisi(self):
        self.assertEqual(token_pairs(r'"a\nb"'), [(STR, r'"a\nb"')])

    def test_kacan_tirnak_stringi_bitirmez(self):
        self.assertEqual(token_pairs(r'"a\"b"'), [(STR, r'"a\"b"')])

    def test_char_literal(self):
        self.assertEqual(token_pairs("'x'"), [(CHR_, "'x'")])

    def test_kapatilmamis_string(self):
        self.assertIn("Kapatılmamış", lex_error('"abc')["error"])

    def test_kapatilmamis_char(self):
        self.assertIn("Kapatılmamış", lex_error("'a")["error"])

    def test_kapatilmamis_string_konumu_baslangici_gosterir(self):
        err = lex_error('x = "abc\ndef')
        self.assertEqual((err["line"], err["column"]), (1, 5))


class TestSymbols(unittest.TestCase):

    def test_tek_karakterli(self):
        self.assertEqual(token_pairs("+"), [(SYMB, "+")])

    def test_cok_karakterli_greedy(self):
        self.assertEqual(token_pairs("<<="), [(SYMB, "<<=")])
        self.assertEqual(token_pairs("<<"), [(SYMB, "<<")])

    def test_ok_operatoru(self):
        self.assertEqual(token_pairs("a->b"),
                         [(IDEN, "a"), (SYMB, "->"), (IDEN, "b")])

    def test_uc_nokta(self):
        self.assertEqual(token_pairs("x ... y"),
                         [(IDEN, "x"), (SYMB, "..."), (IDEN, "y")])

    def test_yildiz_ve_yildiz_esittir(self):
        self.assertEqual(token_pairs("a ** b **= c"),
                         [(IDEN, "a"), (SYMB, "**"), (IDEN, "b"),
                          (SYMB, "**="), (IDEN, "c")])


class TestComments(unittest.TestCase):

    def test_satir_yorumu_atilir(self):
        self.assertEqual(token_pairs("a // yorum\nb"),
                         [(IDEN, "a"), (IDEN, "b")])

    def test_satir_yorumu_dosya_sonunda(self):
        self.assertEqual(token_pairs("a // yorum"), [(IDEN, "a")])

    def test_satir_yorumu_tek_basina(self):
        self.assertEqual(token_pairs("// yalnızca yorum"), [])

    def test_blok_yorumu_atilir(self):
        self.assertEqual(token_pairs("a /* yorum */ + b"),
                         [(IDEN, "a"), (SYMB, "+"), (IDEN, "b")])

    def test_cok_satirli_blok_yorumu(self):
        toks = tokenize("a /* bir\niki */ b")
        self.assertEqual([t.value for t in toks], ["a", "b"])
        self.assertEqual(toks[1].line, 2)          # satır sayacı korunmalı

    def test_yorum_isaretleri_string_icinde_yorum_degildir(self):
        self.assertEqual(token_pairs('"// yorum değil"'),
                         [(STR, '"// yorum değil"')])

    def test_bolme_operatoru_bozulmaz(self):
        self.assertEqual(token_pairs("a / b"),
                         [(IDEN, "a"), (SYMB, "/"), (IDEN, "b")])

    def test_kapatilmamis_blok_yorumu(self):
        self.assertIn("blok yorumu", lex_error("a /* açık")["error"])


class TestPositions(unittest.TestCase):

    def test_satir_ve_sutun(self):
        toks = tokenize("a\n  bc")
        self.assertEqual((toks[0].line, toks[0].column), (1, 1))
        self.assertEqual((toks[1].line, toks[1].column), (2, 3))

    def test_sembol_konumu(self):
        toks = tokenize("xy == 1")
        self.assertEqual((toks[1].value, toks[1].line, toks[1].column),
                         ("==", 1, 4))


if __name__ == "__main__":
    unittest.main()
