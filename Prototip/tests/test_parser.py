"""Parser birim testleri."""

import unittest

from tests.helpers import NodeType, ParseError, Parser, parse, parse_expr, sexp, tokenize


class TestVariables(unittest.TestCase):

    def test_tip_tanimlama(self):
        self.assertEqual(sexp(parse_expr("x : i32;")),
                         "(TYPEBIND:: IDENTIFIER:x LITERAL:i32)")

    def test_atama(self):
        self.assertEqual(sexp(parse_expr("x = 42;")),
                         "(ASSIGN:= IDENTIFIER:x LITERAL:42)")

    def test_tip_ve_atama(self):
        self.assertEqual(
            sexp(parse_expr("x : i32 = 42;")),
            "(ASSIGN:= (TYPEBIND:: IDENTIFIER:x LITERAL:i32) LITERAL:42)")

    def test_zincirleme_atama_sag_cagrisimli(self):
        self.assertEqual(
            sexp(parse_expr("a = b = c;")),
            "(ASSIGN:= IDENTIFIER:a (ASSIGN:= IDENTIFIER:b IDENTIFIER:c))")

    def test_atama_sonrasi_tip(self):
        self.assertEqual(
            sexp(parse_expr("a = b : i32;")),
            "(ASSIGN:= IDENTIFIER:a (TYPEBIND:: IDENTIFIER:b LITERAL:i32))")


class TestExpressions(unittest.TestCase):

    def test_binary_sol_cagrisimli(self):
        self.assertEqual(
            sexp(parse_expr("a + b + c;")),
            "(BINARY_OP (BINARY_OP IDENTIFIER:a OPERATOR:+ IDENTIFIER:b) "
            "OPERATOR:+ IDENTIFIER:c)")

    def test_unary_eksi(self):
        self.assertEqual(sexp(parse_expr("-5;")),
                         "(UNARY_OP OPERATOR:- LITERAL:5)")

    def test_unary_not(self):
        self.assertEqual(sexp(parse_expr("!flag;")),
                         "(UNARY_OP OPERATOR:! IDENTIFIER:flag)")

    def test_gruplama(self):
        self.assertEqual(
            sexp(parse_expr("(x + y) * 2;")),
            "(BINARY_OP (BINARY_OP IDENTIFIER:x OPERATOR:+ IDENTIFIER:y) "
            "OPERATOR:* LITERAL:2)")

    def test_lvalue_expression(self):
        self.assertEqual(
            sexp(parse_expr("(a = b) + 1;")),
            "(BINARY_OP (ASSIGN:= IDENTIFIER:a IDENTIFIER:b) OPERATOR:+ LITERAL:1)")

    def test_ic_ice_unary(self):
        self.assertEqual(
            sexp(parse_expr("-(x + 1);")),
            "(UNARY_OP OPERATOR:- (BINARY_OP IDENTIFIER:x OPERATOR:+ LITERAL:1))")

    def test_primitive_tip_literal_olur(self):
        self.assertEqual(parse_expr("i32;").type, NodeType.LITERAL)

    def test_normal_isim_identifier_olur(self):
        self.assertEqual(parse_expr("sayac;").type, NodeType.IDENTIFIER)


class TestBlocks(unittest.TestCase):

    def test_blok_deger_olarak(self):
        node = parse_expr("r = { a = 1; a + 2; };")
        self.assertEqual(node.type, NodeType.ASSIGN)
        self.assertEqual(node.children[1].type, NodeType.BLOCK)
        self.assertEqual(len(node.children[1].children), 2)

    def test_bos_blok(self):
        node = parse_expr("r = {};")
        self.assertEqual(node.children[1].type, NodeType.BLOCK)
        self.assertEqual(node.children[1].children, [])

    def test_kapatilmamis_blok(self):
        with self.assertRaises(ParseError):
            parse("f { a = 1;")


class TestTypeExpressions(unittest.TestCase):

    def test_fonksiyon_imzasi(self):
        self.assertEqual(
            sexp(parse_expr("topla : (x:i32, y:i32) -> i32;")),
            "(TYPEBIND:: IDENTIFIER:topla "
            "(FUNC_TYPE:-> (TYPE_PARAM:x LITERAL:i32) (TYPE_PARAM:y LITERAL:i32) "
            "(TYPE_PARAM LITERAL:i32)))")

    def test_isimsiz_parametre(self):
        self.assertEqual(
            sexp(parse_expr("g : (i32, i32) -> i32;")),
            "(TYPEBIND:: IDENTIFIER:g "
            "(FUNC_TYPE:-> (TYPE_PARAM LITERAL:i32) (TYPE_PARAM LITERAL:i32) "
            "(TYPE_PARAM LITERAL:i32)))")

    def test_curried_tip_sag_cagrisimli(self):
        node = parse_expr("f : (x:i32) -> (y:i32) -> bool;")
        func_type = node.children[1]
        self.assertEqual(func_type.type, NodeType.FUNC_TYPE)
        # Dönüş tipi yine bir FUNC_TYPE olmalı → sağ çağrışım
        ret = func_type.children[-1]
        self.assertEqual(ret.type, NodeType.TYPE_PARAM)
        self.assertEqual(ret.children[0].type, NodeType.FUNC_TYPE)

    def test_yuksek_mertebeden_fonksiyon_tipi(self):
        node = parse_expr("apply : (f:(x:i32) -> i32, v:i32) -> i32;")
        func_type = node.children[1]
        first_param = func_type.children[0]
        self.assertEqual(first_param.value.value, "f")
        self.assertEqual(first_param.children[0].type, NodeType.FUNC_TYPE)


class TestFuncDef(unittest.TestCase):

    def test_imzasiz_govde(self):
        program = parse("topla { result = x + y; result; }")
        func = program.children[0]
        self.assertEqual(func.type, NodeType.FUNC_DEF)
        self.assertEqual(func.value.value, "topla")
        self.assertEqual(len(func.children), 1)
        self.assertEqual(func.children[0].type, NodeType.BLOCK)

    def test_satir_ici_imza(self):
        program = parse("topla (x:i32, y:i32) -> i32 { x + y; }")
        func = program.children[0]
        self.assertEqual(func.type, NodeType.FUNC_DEF)
        self.assertEqual(func.children[0].type, NodeType.FUNC_TYPE)
        self.assertEqual(func.children[1].type, NodeType.BLOCK)

    def test_parametresiz_fonksiyon(self):
        program = parse("main () -> i32 { 0; }")
        self.assertEqual(program.children[0].type, NodeType.FUNC_DEF)


class TestErrors(unittest.TestCase):

    def test_eksik_noktali_virgul(self):
        with self.assertRaises(ParseError):
            parse("x = 1")

    def test_eof_sonrasi_literal(self):
        with self.assertRaises(ParseError):
            parse("x = ;")

    def test_hata_mesajinda_konum_var(self):
        with self.assertRaises(ParseError) as ctx:
            parse("x = 1 y = 2;")
        self.assertRegex(str(ctx.exception), r"\[\d+:\d+\]")

    def test_ws_tokenlari_atilir(self):
        # Parser WS token'larını süzer; lexer zaten üretmiyor ama sözleşme korunmalı.
        parser = Parser(tokenize("x = 1;"))
        self.assertTrue(all(t.value.strip() for t in parser.tokens))


if __name__ == "__main__":
    unittest.main()
