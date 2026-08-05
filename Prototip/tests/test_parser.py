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


class TestPrecedence(unittest.TestCase):

    def test_carpma_toplamadan_once_baglar(self):
        self.assertEqual(
            sexp(parse_expr("1 + 2 * 3;")),
            "(BINARY_OP LITERAL:1 OPERATOR:+ "
            "(BINARY_OP LITERAL:2 OPERATOR:* LITERAL:3))")

    def test_bolme_ve_carpma_soldan_saga(self):
        self.assertEqual(
            sexp(parse_expr("8 / 4 * 2;")),
            "(BINARY_OP (BINARY_OP LITERAL:8 OPERATOR:/ LITERAL:4) "
            "OPERATOR:* LITERAL:2)")

    def test_us_sag_cagrisimli(self):
        self.assertEqual(
            sexp(parse_expr("2 ** 3 ** 2;")),
            "(BINARY_OP LITERAL:2 OPERATOR:** "
            "(BINARY_OP LITERAL:3 OPERATOR:** LITERAL:2))")

    def test_karsilastirma_aritmetikten_sonra(self):
        self.assertEqual(
            sexp(parse_expr("a + 1 < b * 2;")),
            "(BINARY_OP (BINARY_OP IDENTIFIER:a OPERATOR:+ LITERAL:1) OPERATOR:< "
            "(BINARY_OP IDENTIFIER:b OPERATOR:* LITERAL:2))")

    def test_mantiksal_ve_veya_dan_once_baglar(self):
        self.assertEqual(
            sexp(parse_expr("a || b && c;")),
            "(BINARY_OP IDENTIFIER:a OPERATOR:|| "
            "(BINARY_OP IDENTIFIER:b OPERATOR:&& IDENTIFIER:c))")

    def test_esitlik_karsilastirmadan_sonra(self):
        self.assertEqual(
            sexp(parse_expr("a < b == c > d;")),
            "(BINARY_OP (BINARY_OP IDENTIFIER:a OPERATOR:< IDENTIFIER:b) OPERATOR:== "
            "(BINARY_OP IDENTIFIER:c OPERATOR:> IDENTIFIER:d))")

    def test_binary_ardindan_unary_birlestirilmez(self):
        # Eski parser '+' ve '-' token'larını '+-' operatörüne yapıştırıyordu.
        self.assertEqual(
            sexp(parse_expr("a + -b;")),
            "(BINARY_OP IDENTIFIER:a OPERATOR:+ (UNARY_OP OPERATOR:- IDENTIFIER:b))")

    def test_bilinmeyen_sembol_en_dusuk_seviyeye_duser(self):
        # '...' symbols.txt'de var ama öncelik tablosunda yok → CUSTOM_LEVEL
        self.assertEqual(
            sexp(parse_expr("a ... b + c;")),
            "(BINARY_OP IDENTIFIER:a OPERATOR:... "
            "(BINARY_OP IDENTIFIER:b OPERATOR:+ IDENTIFIER:c))")

    def test_zincirlenmis_unary(self):
        self.assertEqual(
            sexp(parse_expr("!!x;")),
            "(UNARY_OP OPERATOR:! (UNARY_OP OPERATOR:! IDENTIFIER:x))")


class TestAssignOps(unittest.TestCase):

    def test_bilesik_atama(self):
        self.assertEqual(sexp(parse_expr("a += 1;")),
                         "(ASSIGN:+= IDENTIFIER:a LITERAL:1)")

    def test_tum_bilesik_operatorler(self):
        for op in ("+=", "-=", "*=", "/=", "%=", "**=", "<<=", ">>="):
            node = parse_expr(f"a {op} 1;")
            self.assertEqual(node.type, NodeType.ASSIGN, op)
            self.assertEqual(node.value.value, op)

    def test_indeks_hedefine_atama(self):
        self.assertEqual(
            sexp(parse_expr("xs[0] = 9;")),
            "(ASSIGN:= (INDEX:[ IDENTIFIER:xs LITERAL:0) LITERAL:9)")


class TestIncDec(unittest.TestCase):

    def test_onek_artirma(self):
        self.assertEqual(sexp(parse_expr("++x;")), "(PRE_OP:++ IDENTIFIER:x)")

    def test_sonek_artirma(self):
        self.assertEqual(sexp(parse_expr("x++;")), "(POST_OP:++ IDENTIFIER:x)")

    def test_onek_azaltma(self):
        self.assertEqual(sexp(parse_expr("--x;")), "(PRE_OP:-- IDENTIFIER:x)")

    def test_dizi_elemani_hedef_olabilir(self):
        self.assertEqual(sexp(parse_expr("xs[0]++;")),
                         "(POST_OP:++ (INDEX:[ IDENTIFIER:xs LITERAL:0))")

    def test_ifade_icinde(self):
        self.assertEqual(
            sexp(parse_expr("y = x++ + 1;")),
            "(ASSIGN:= IDENTIFIER:y (BINARY_OP (POST_OP:++ IDENTIFIER:x) "
            "OPERATOR:+ LITERAL:1))")

    def test_literal_hedef_olamaz(self):
        with self.assertRaises(ParseError) as ctx:
            parse("--5;")
        self.assertIn("yalnızca değişken", str(ctx.exception))

    def test_cagri_sonucu_hedef_olamaz(self):
        with self.assertRaises(ParseError):
            parse("f()++;")

    def test_binary_operator_degildir(self):
        with self.assertRaises(ParseError):
            parse("a ++ b;")


class TestCalls(unittest.TestCase):

    def test_tek_argumanli_cagri(self):
        self.assertEqual(sexp(parse_expr("print(42);")),
                         "(CALL:( IDENTIFIER:print LITERAL:42)")

    def test_argumansiz_cagri(self):
        self.assertEqual(sexp(parse_expr("now();")),
                         "(CALL:( IDENTIFIER:now)")

    def test_cok_argumanli_cagri(self):
        node = parse_expr("add(1, 2, 3);")
        self.assertEqual(node.type, NodeType.CALL)
        self.assertEqual(len(node.children), 4)          # çağrılan + 3 argüman

    def test_ic_ice_cagri(self):
        self.assertEqual(
            sexp(parse_expr("apply(f, g(x));")),
            "(CALL:( IDENTIFIER:apply IDENTIFIER:f (CALL:( IDENTIFIER:g IDENTIFIER:x))")

    def test_currying_zinciri(self):
        self.assertEqual(
            sexp(parse_expr("f(1)(2);")),
            "(CALL:( (CALL:( IDENTIFIER:f LITERAL:1) LITERAL:2)")

    def test_argumanlarda_oncelik_korunur(self):
        self.assertEqual(
            sexp(parse_expr("f(1 + 2 * 3);")),
            "(CALL:( IDENTIFIER:f (BINARY_OP LITERAL:1 OPERATOR:+ "
            "(BINARY_OP LITERAL:2 OPERATOR:* LITERAL:3)))")

    def test_cagri_ifade_icinde(self):
        self.assertEqual(
            sexp(parse_expr("x = f(1) + 2;")),
            "(ASSIGN:= IDENTIFIER:x (BINARY_OP (CALL:( IDENTIFIER:f LITERAL:1) "
            "OPERATOR:+ LITERAL:2))")

    def test_kapatilmamis_arguman_listesi(self):
        with self.assertRaises(ParseError):
            parse("f(1, 2;")


class TestMemberAndIndex(unittest.TestCase):

    def test_uye_erisimi(self):
        self.assertEqual(sexp(parse_expr("a.b;")),
                         "(MEMBER:b IDENTIFIER:a)")

    def test_zincirli_uye_erisimi(self):
        self.assertEqual(sexp(parse_expr("a.b.c;")),
                         "(MEMBER:c (MEMBER:b IDENTIFIER:a))")

    def test_metot_cagrisi(self):
        self.assertEqual(sexp(parse_expr("s.len();")),
                         "(CALL:( (MEMBER:len IDENTIFIER:s))")

    def test_indeksleme(self):
        self.assertEqual(
            sexp(parse_expr("xs[i + 1];")),
            "(INDEX:[ IDENTIFIER:xs (BINARY_OP IDENTIFIER:i OPERATOR:+ LITERAL:1))")

    def test_karisik_zincir(self):
        self.assertEqual(
            sexp(parse_expr("obj.items[0](arg);")),
            "(CALL:( (INDEX:[ (MEMBER:items IDENTIFIER:obj) LITERAL:0) IDENTIFIER:arg)")

    def test_uye_adi_zorunlu(self):
        with self.assertRaises(ParseError):
            parse("a.1;")


class TestArrays(unittest.TestCase):

    def test_dizi_literali(self):
        self.assertEqual(sexp(parse_expr("[1, 2, 3];")),
                         "(ARRAY:[ LITERAL:1 LITERAL:2 LITERAL:3)")

    def test_bos_dizi(self):
        self.assertEqual(sexp(parse_expr("[];")), "ARRAY:[")

    def test_sondaki_virgul_serbest(self):
        self.assertEqual(sexp(parse_expr("[1, 2,];")),
                         "(ARRAY:[ LITERAL:1 LITERAL:2)")

    def test_ic_ice_dizi(self):
        self.assertEqual(sexp(parse_expr("[[1], [2]];")),
                         "(ARRAY:[ (ARRAY:[ LITERAL:1) (ARRAY:[ LITERAL:2))")

    def test_eksik_virgul_hata(self):
        with self.assertRaises(ParseError):
            parse("[1 2];")

    def test_dizi_tipi(self):
        self.assertEqual(sexp(parse_expr("xs : [i32];")),
                         "(TYPEBIND:: IDENTIFIER:xs (ARRAY:[ LITERAL:i32))")


class TestMaps(unittest.TestCase):

    def test_harita_literali(self):
        self.assertEqual(sexp(parse_expr('#["a": 1];')),
                         '(MAP:# LITERAL:"a" LITERAL:1)')

    def test_bos_harita(self):
        self.assertEqual(sexp(parse_expr("#[];")), "MAP:#")

    def test_cok_girdili(self):
        node = parse_expr('#["a": 1, "b": 2];')
        self.assertEqual(node.type, NodeType.MAP)
        self.assertEqual(len(node.children), 4)        # ikişerli: k, v, k, v

    def test_sondaki_virgul_serbest(self):
        self.assertEqual(len(parse_expr('#["a": 1,];').children), 2)

    def test_anahtar_ifade_olabilir(self):
        node = parse_expr("#[1 + 1: 'x'];")
        self.assertEqual(node.children[0].type, NodeType.BINARY_OP)

    def test_deger_tam_ifadedir(self):
        node = parse_expr('#["a": 1 + 2 * 3];')
        self.assertEqual(node.children[1].type, NodeType.BINARY_OP)

    def test_ic_ice_harita(self):
        node = parse_expr('#["a": #["b": 1]];')
        self.assertEqual(node.children[1].type, NodeType.MAP)

    def test_eksik_iki_nokta(self):
        with self.assertRaises(ParseError):
            parse('#["a" 1];')

    def test_eksik_virgul(self):
        with self.assertRaises(ParseError):
            parse('#["a": 1 "b": 2];')

    def test_blok_ile_karistirilmaz(self):
        # "{" hâlâ blok; harita için "#[" gerekir
        self.assertEqual(parse_expr("x = {};").children[1].type, NodeType.BLOCK)


class TestControlFlow(unittest.TestCase):

    def test_if_else(self):
        node = parse_expr("if x { 1; } else { 0; };")
        self.assertEqual(node.type, NodeType.IF)
        self.assertEqual(len(node.children), 3)

    def test_else_siz_if(self):
        node = parse_expr("if x { 1; };")
        self.assertEqual(len(node.children), 2)

    def test_else_if_zinciri(self):
        node = parse_expr("if a { 1; } else if b { 2; } else { 3; };")
        self.assertEqual(node.children[2].type, NodeType.IF)

    def test_if_deger_olarak(self):
        node = parse_expr("r = if x { 1; } else { 0; };")
        self.assertEqual(node.type, NodeType.ASSIGN)
        self.assertEqual(node.children[1].type, NodeType.IF)

    def test_blok_kuyruklu_ifadede_noktali_virgul_opsiyonel(self):
        program = parse("if x { 1; }")
        self.assertEqual(program.children[0].children[0].type, NodeType.IF)

    def test_while(self):
        node = parse_expr("while i < 10 { i += 1; }")
        self.assertEqual(node.type, NodeType.WHILE)
        self.assertEqual(node.children[0].type, NodeType.BINARY_OP)
        self.assertEqual(node.children[1].type, NodeType.BLOCK)

    def test_for_in(self):
        node = parse_expr("for x in xs { print(x); }")
        self.assertEqual(node.type, NodeType.FOR)
        self.assertEqual(node.value.value, "x")
        self.assertEqual(node.children[0].type, NodeType.IDENTIFIER)

    def test_for_in_eksik_in(self):
        with self.assertRaises(ParseError):
            parse("for x xs { 1; }")

    def test_return(self):
        node = parse_expr("return 42;")
        self.assertEqual(node.type, NodeType.RETURN)
        self.assertEqual(sexp(node.children[0]), "LITERAL:42")

    def test_degersiz_return(self):
        node = parse_expr("return;")
        self.assertEqual(node.type, NodeType.RETURN)
        self.assertEqual(node.children, [])

    def test_break_continue(self):
        self.assertEqual(parse_expr("break;").type, NodeType.BREAK)
        self.assertEqual(parse_expr("continue;").type, NodeType.CONTINUE)

    def test_bool_literalleri(self):
        self.assertEqual(sexp(parse_expr("true;")), "LITERAL:true")
        self.assertEqual(sexp(parse_expr("false;")), "LITERAL:false")

    def test_anahtar_sozcuk_degisken_olamaz(self):
        with self.assertRaises(ParseError):
            parse("while = 1;")


class TestNestedFuncDef(unittest.TestCase):

    def test_blok_icinde_fonksiyon_tanimi(self):
        program = parse("dis () -> i32 { ic (x:i32) -> i32 { x; } ic(1); }")
        outer = program.children[0]
        body  = outer.children[1]
        self.assertEqual(body.children[0].type, NodeType.FUNC_DEF)

    def test_cagri_fonksiyon_tanimiyla_karistirilmaz(self):
        program = parse("topla(1, 2);")
        self.assertEqual(program.children[0].type, NodeType.STATEMENT)
        self.assertEqual(program.children[0].children[0].type, NodeType.CALL)


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
