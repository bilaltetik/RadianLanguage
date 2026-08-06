"""Yorumlayıcı birim testleri."""

import io
import unittest

from tests.helpers import SYMBOLS_FILE
from interpreter import UNIT, Interpreter, RadianError, to_display


def run(src: str):
    """Kaynağı çalıştır, program değerini döndür."""
    return Interpreter(out=io.StringIO()).run_source(src, symbols_file=SYMBOLS_FILE)


def output(src: str) -> str:
    """Kaynağı çalıştır, print çıktısını döndür."""
    buffer = io.StringIO()
    Interpreter(out=buffer).run_source(src, symbols_file=SYMBOLS_FILE)
    return buffer.getvalue()


class TestLiterals(unittest.TestCase):

    def test_tamsayi(self):
        self.assertEqual(run("42;"), 42)

    def test_ondalik(self):
        self.assertEqual(run("3.5;"), 3.5)

    def test_onekli_sayilar(self):
        self.assertEqual(run("0xFF;"), 255)
        self.assertEqual(run("0b1011;"), 11)
        self.assertEqual(run("0o17;"), 15)

    def test_bilimsel_gosterim(self):
        self.assertEqual(run("1.5e3;"), 1500.0)

    def test_string(self):
        self.assertEqual(run('"merhaba";'), "merhaba")

    def test_kacis_dizileri(self):
        self.assertEqual(run(r'"a\nb\tc";'), "a\nb\tc")
        self.assertEqual(run(r'"tırnak: \"";'), 'tırnak: "')
        self.assertEqual(run(r'"\x41";'), "A")

    def test_char(self):
        self.assertEqual(run("'x';"), "x")

    def test_bool(self):
        self.assertIs(run("true;"), True)
        self.assertIs(run("false;"), False)

    def test_bilinmeyen_kacis_hatasi(self):
        with self.assertRaises(RadianError):
            run(r'"\q";')

    def test_tip_adi_deger_degildir(self):
        with self.assertRaises(RadianError):
            run("i32 + 1;")


class TestArithmetic(unittest.TestCase):

    def test_dort_islem(self):
        self.assertEqual(run("2 + 3 * 4;"), 14)
        self.assertEqual(run("(2 + 3) * 4;"), 20)
        self.assertEqual(run("10 - 3 - 2;"), 5)

    def test_tamsayi_bolmesi_sifira_dogru_kirpar(self):
        self.assertEqual(run("7 / 2;"), 3)
        self.assertEqual(run("-7 / 2;"), -3)

    def test_ondalikli_bolme(self):
        self.assertEqual(run("7.0 / 2;"), 3.5)

    def test_mod(self):
        self.assertEqual(run("7 % 3;"), 1)
        self.assertEqual(run("-7 % 3;"), -1)          # işaret bölünene uyar

    def test_us(self):
        self.assertEqual(run("2 ** 10;"), 1024)
        self.assertEqual(run("2 ** 3 ** 2;"), 512)    # sağ çağrışım

    def test_sifira_bolme(self):
        with self.assertRaises(RadianError):
            run("1 / 0;")

    def test_bit_operatorleri(self):
        self.assertEqual(run("6 & 3;"), 2)
        self.assertEqual(run("6 | 3;"), 7)
        self.assertEqual(run("6 ^ 3;"), 5)
        self.assertEqual(run("1 << 4;"), 16)
        self.assertEqual(run("16 >> 2;"), 4)
        self.assertEqual(run("~0;"), -1)

    def test_unary(self):
        self.assertEqual(run("-5;"), -5)
        self.assertEqual(run("-(-5);"), 5)
        self.assertIs(run("!true;"), False)

    def test_string_birlestirme(self):
        self.assertEqual(run('"ab" + "cd";'), "abcd")
        self.assertEqual(run('"ab" * 3;'), "ababab")

    def test_dizi_birlestirme(self):
        self.assertEqual(run("[1, 2] + [3];"), [1, 2, 3])

    def test_uyumsuz_tipte_operator(self):
        with self.assertRaises(RadianError):
            run('1 + "a";')

    def test_mantiksal_operatorler_bool_ister(self):
        with self.assertRaises(RadianError):
            run("1 && true;")


class TestComparison(unittest.TestCase):

    def test_sayisal_karsilastirma(self):
        self.assertIs(run("1 < 2;"), True)
        self.assertIs(run("2 <= 2;"), True)
        self.assertIs(run("3 > 4;"), False)

    def test_esitlik(self):
        self.assertIs(run("1 == 1;"), True)
        self.assertIs(run('"a" == "a";'), True)
        self.assertIs(run("[1, 2] == [1, 2];"), True)
        self.assertIs(run("1 == true;"), False)       # bool ve int ayrı tiptir

    def test_string_karsilastirma(self):
        self.assertIs(run('"a" < "b";'), True)

    def test_kisa_devre(self):
        # sağ taraf çalışsaydı tanımsız değişken hatası verirdi
        self.assertIs(run("false && bilinmeyen;"), False)
        self.assertIs(run("true || bilinmeyen;"), True)


class TestVariables(unittest.TestCase):

    def test_atama_ve_okuma(self):
        self.assertEqual(run("x = 5; x * 2;"), 10)

    def test_zincirleme_atama(self):
        self.assertEqual(run("a = b = 3; a + b;"), 6)

    def test_bilesik_atama(self):
        self.assertEqual(run("x = 5; x += 3; x;"), 8)
        self.assertEqual(run("x = 5; x *= 3; x;"), 15)
        self.assertEqual(run("x = 5; x -= 3; x;"), 2)
        self.assertEqual(run("x = 8; x /= 2; x;"), 4)

    def test_tanimsiz_degisken(self):
        with self.assertRaises(RadianError) as ctx:
            run("yok + 1;")
        self.assertIn("Tanımsız değişken", str(ctx.exception))

    def test_atama_lvalue_dondurur(self):
        self.assertEqual(run("(x = 4) + 1;"), 5)


class TestIncDec(unittest.TestCase):

    def test_onek_yeni_degeri_dondurur(self):
        self.assertEqual(run("x = 1; ++x;"), 2)

    def test_sonek_eski_degeri_dondurur(self):
        self.assertEqual(run("x = 1; x++;"), 1)

    def test_sonek_degiskeni_gunceller(self):
        self.assertEqual(run("x = 1; x++; x;"), 2)

    def test_azaltma(self):
        self.assertEqual(run("x = 5; --x;"), 4)
        self.assertEqual(run("x = 5; x--; x;"), 4)

    def test_dizi_elemani(self):
        self.assertEqual(run("xs = [1, 2]; xs[0]++; xs;"), [2, 2])

    def test_ondalik_deger(self):
        self.assertEqual(run("x = 1.5; ++x;"), 2.5)

    def test_dongude_sayac(self):
        self.assertEqual(run("i = 0; while i < 3 { i++; } i;"), 3)

    def test_ifade_icinde_sirasi(self):
        self.assertEqual(run("x = 1; a = x++; [a, x];"), [1, 2])

    def test_tip_araligi_denetlenir(self):
        with self.assertRaises(RadianError) as ctx:
            run("x : i8 = 127; x++;")
        self.assertIn("aralığının dışında", str(ctx.exception))

    def test_sayisal_olmayan_hedef(self):
        with self.assertRaises(RadianError) as ctx:
            run('s = "a"; s++;')
        self.assertIn("sayı bekler", str(ctx.exception))


class TestTypes(unittest.TestCase):

    def test_tip_bagli_atama(self):
        self.assertEqual(run("x : i32 = 42; x;"), 42)

    def test_tip_ihlali(self):
        with self.assertRaises(RadianError) as ctx:
            run('x : i32 = "abc";')
        self.assertIn("Tip uyuşmazlığı", str(ctx.exception))

    def test_tip_sonraki_atamalarda_da_gecerli(self):
        with self.assertRaises(RadianError):
            run('x : i32 = 1; x = "abc";')

    def test_tamsayi_araligi(self):
        with self.assertRaises(RadianError) as ctx:
            run("x : i8 = 200;")
        self.assertIn("aralığının dışında", str(ctx.exception))

    def test_isaretsiz_negatif_alamaz(self):
        with self.assertRaises(RadianError):
            run("x : u8 = -1;")

    def test_float_tamsayi_kabul_eder(self):
        self.assertEqual(run("x : f64 = 3; x;"), 3)

    def test_degersiz_bildirim_sifir_deger_alir(self):
        self.assertEqual(run("x : i32; x;"), 0)
        self.assertEqual(run("s : str; s;"), "")
        self.assertIs(run("b : bool; b;"), False)
        self.assertEqual(run("xs : [i32]; xs;"), [])

    def test_dizi_tipi_eleman_denetimi(self):
        with self.assertRaises(RadianError):
            run('xs : [i32] = [1, "a"];')

    def test_bool_int_ile_karistirilmaz(self):
        with self.assertRaises(RadianError):
            run("x : i32 = true;")


class TestBlocks(unittest.TestCase):

    def test_blok_son_degeri_dondurur(self):
        self.assertEqual(run("r = { a = 1; a + 2; }; r;"), 3)

    def test_bos_blok_unit(self):
        self.assertIs(run("{};"), UNIT)

    def test_blok_yeni_kapsam_acar(self):
        self.assertEqual(run("x = 1; { y = 5; }; x;"), 1)
        with self.assertRaises(RadianError):
            run("{ y = 5; }; y;")

    def test_blok_dis_degiskeni_gunceller(self):
        self.assertEqual(run("x = 1; { x = 9; }; x;"), 9)


class TestControlFlow(unittest.TestCase):

    def test_if_deger_dondurur(self):
        self.assertEqual(run("if true { 1; } else { 2; };"), 1)
        self.assertEqual(run("if false { 1; } else { 2; };"), 2)

    def test_else_siz_if_unit_dondurur(self):
        self.assertIs(run("if false { 1; };"), UNIT)

    def test_else_if_zinciri(self):
        src = "x = 5; if x < 3 { 'a'; } else if x < 10 { 'b'; } else { 'c'; };"
        self.assertEqual(run(src), "b")

    def test_kosul_bool_olmali(self):
        with self.assertRaises(RadianError):
            run("if 1 { 2; };")

    def test_while_dongusu(self):
        self.assertEqual(run("i = 0; while i < 5 { i += 1; } i;"), 5)

    def test_for_dongusu(self):
        self.assertEqual(run("t = 0; for x in [1, 2, 3] { t += x; } t;"), 6)

    def test_for_string_uzerinde(self):
        self.assertEqual(run('s = ""; for c in "abc" { s = c + s; } s;'), "cba")

    def test_break(self):
        self.assertEqual(run("i = 0; while true { i += 1; if i == 3 { break; } } i;"), 3)

    def test_continue(self):
        src = "t = 0; for x in range(1, 6) { if x % 2 == 0 { continue; } t += x; } t;"
        self.assertEqual(run(src), 9)                 # 1 + 3 + 5

    def test_dongu_sonrasi_negatif_sabit_ayri_deyimdir(self):
        # Regresyon: "while … { } -1;" ifadesi (while …) - 1 oluyordu
        src = "ara () -> i32 { i = 0; while i < 3 { i++; } -1; } ara();"
        self.assertEqual(run(src), -1)

    def test_if_sonrasi_negatif_sabit_ayri_deyimdir(self):
        self.assertEqual(run("f () -> i32 { if false { 1; } -2; } f();"), -2)

    def test_for_dongu_degiskeni_disariya_sizmaz(self):
        with self.assertRaises(RadianError):
            run("for x in [1] { x; } x;")

    def test_dongu_disinda_break_hatasi(self):
        with self.assertRaises(RadianError):
            run("break;")


class TestFunctions(unittest.TestCase):

    def test_basit_fonksiyon(self):
        self.assertEqual(run("topla (a:i32, b:i32) -> i32 { a + b; } topla(2, 3);"), 5)

    def test_imzasiz_fonksiyon(self):
        self.assertEqual(run("sabit { 7; } sabit();"), 7)

    def test_ozyineleme(self):
        src = """
        fakt (n:i32) -> i32 {
            if n <= 1 { return 1; }
            n * fakt(n - 1);
        }
        fakt(6);
        """
        self.assertEqual(run(src), 720)

    def test_erken_return(self):
        src = "mutlak (x:i32) -> i32 { if x < 0 { return -x; } x; } mutlak(-4);"
        self.assertEqual(run(src), 4)

    def test_degersiz_return(self):
        self.assertIs(run("f { return; } f();"), UNIT)

    def test_closure(self):
        src = """
        sayac_yap {
            n = 0;
            artir { n += 1; n; }
            artir;
        }
        c = sayac_yap();
        c(); c(); c();
        """
        self.assertEqual(run(src), 3)

    def test_fonksiyon_deger_olarak_gecirilir(self):
        src = """
        iki_kat (x:i32) -> i32 { x * 2; }
        uygula (f:(x:i32) -> i32, v:i32) -> i32 { f(v); }
        uygula(iki_kat, 21);
        """
        self.assertEqual(run(src), 42)

    def test_arguman_sayisi_denetimi(self):
        with self.assertRaises(RadianError) as ctx:
            run("f (a:i32) -> i32 { a; } f(1, 2);")
        self.assertIn("argüman", str(ctx.exception))

    def test_parametre_tipi_denetimi(self):
        with self.assertRaises(RadianError):
            run('f (a:i32) -> i32 { a; } f("x");')

    def test_donus_tipi_denetimi(self):
        with self.assertRaises(RadianError):
            run('f () -> i32 { "x"; } f();')

    def test_cagrilamaz_deger(self):
        with self.assertRaises(RadianError):
            run("x = 1; x();")

    def test_main_otomatik_calisir(self):
        self.assertEqual(output('main () -> i32 { print("selam"); 0; }'), "selam\n")

    def test_ic_ice_fonksiyon(self):
        src = """
        dis (x:i32) -> i32 {
            ic (y:i32) -> i32 { y * y; }
            ic(x) + 1;
        }
        dis(4);
        """
        self.assertEqual(run(src), 17)


class TestArraysAndStrings(unittest.TestCase):

    def test_dizi_literali_ve_indeksleme(self):
        self.assertEqual(run("xs = [10, 20, 30]; xs[1];"), 20)

    def test_indeksle_atama(self):
        self.assertEqual(run("xs = [1, 2]; xs[0] = 9; xs;"), [9, 2])

    def test_sinir_disi_indeks(self):
        with self.assertRaises(RadianError) as ctx:
            run("xs = [1]; xs[5];")
        self.assertIn("sınır dışı", str(ctx.exception))

    def test_negatif_indeks_hatadir(self):
        with self.assertRaises(RadianError):
            run("xs = [1]; xs[-1];")

    def test_string_indeksleme(self):
        self.assertEqual(run('"merhaba"[0];'), "m")

    def test_dizi_metotlari(self):
        self.assertEqual(run("xs = [1, 2]; xs.push(3); xs;"), [1, 2, 3])
        self.assertEqual(run("[1, 2, 3].len();"), 3)
        self.assertEqual(run("[1, 2, 3].reverse();"), [3, 2, 1])
        self.assertIs(run("[1, 2].contains(2);"), True)
        self.assertEqual(run("[3, 1, 2].sort();"), [1, 2, 3])
        self.assertEqual(run('[1, 2].join("-");'), "1-2")
        self.assertEqual(run("[1, 2, 3].slice(1);"), [2, 3])
        self.assertEqual(run("[1, 2, 3].index_of(3);"), 2)

    def test_dizi_hof_metotlari(self):
        src = """
        kare (x:i32) -> i32 { x * x; }
        tek (x:i32) -> bool { x % 2 == 1; }
        topla (a:i32, b:i32) -> i32 { a + b; }
        [1, 2, 3, 4].filter(tek).map(kare).reduce(topla);
        """
        self.assertEqual(run(src), 10)                # 1 + 9

    def test_string_metotlari(self):
        self.assertEqual(run('"  ab  ".trim();'), "ab")
        self.assertEqual(run('"ab".upper();'), "AB")
        self.assertEqual(run('"a,b,c".split(",");'), ["a", "b", "c"])
        self.assertIs(run('"merhaba".starts_with("mer");'), True)
        self.assertEqual(run('"abc".replace("b", "X");'), "aXc")
        self.assertEqual(run('"abc".chars();'), ["a", "b", "c"])
        self.assertEqual(run('"ab".repeat(2);'), "abab")

    def test_sayi_metotlari(self):
        self.assertEqual(run("(-3).abs();"), 3)
        self.assertEqual(run("(3).max(5);"), 5)

    def test_bilinmeyen_uye(self):
        with self.assertRaises(RadianError) as ctx:
            run("[1].yok();")
        self.assertIn("üyesi yok", str(ctx.exception))


class TestMaps(unittest.TestCase):

    def test_literal_ve_okuma(self):
        self.assertEqual(run('m = #["a": 1, "b": 2]; m["a"];'), 1)

    def test_bos_harita_ve_ekleme(self):
        self.assertEqual(run('m = #[]; m["x"] = 5; m["x"];'), 5)

    def test_map_yerlesigi(self):
        self.assertEqual(run('m = map([["x", 1], ["y", 2]]); m["y"];'), 2)
        self.assertEqual(run("len(map());"), 0)

    def test_sayisal_anahtar(self):
        self.assertEqual(run('m = #[1: "bir", 2: "iki"]; m[2];'), "iki")

    def test_eksik_anahtar_hata(self):
        with self.assertRaises(RadianError) as ctx:
            run('m = #["a": 1]; m["yok"];')
        self.assertIn("anahtar yok", str(ctx.exception))

    def test_bool_anahtar_yasak(self):
        with self.assertRaises(RadianError) as ctx:
            run("m = #[true: 1];")
        self.assertIn("bool olamaz", str(ctx.exception))

    def test_dizi_anahtar_yasak(self):
        with self.assertRaises(RadianError):
            run("m = #[[1]: 2];")

    def test_metotlar(self):
        self.assertIs(run('#["a": 1].has("a");'), True)
        self.assertIs(run('#["a": 1].has("z");'), False)
        self.assertEqual(run('#["a": 1].get("z", 0);'), 0)
        self.assertEqual(run('#["a": 1, "b": 2].keys();'), ["a", "b"])
        self.assertEqual(run('#["a": 1, "b": 2].values();'), [1, 2])
        self.assertEqual(run('#["a": 1].pairs();'), [["a", 1]])
        self.assertEqual(run('#["a": 1].len();'), 1)
        self.assertEqual(run('m = #["a": 1]; m.remove("a"); m.len();'), 0)
        self.assertEqual(run('m = #["a": 1]; m.clear().len();'), 0)

    def test_merge_yeni_harita_dondurur(self):
        self.assertEqual(run('a = #["x": 1]; b = a.merge(#["y": 2]); '
                             '[a.len(), b.len()];'), [1, 2])

    def test_for_anahtarlar_uzerinde_gezer(self):
        self.assertEqual(
            run('m = #["a": 1, "b": 2]; t = 0; for k in m { t += m[k]; } t;'), 3)

    def test_esitlik(self):
        self.assertIs(run('#["a": 1] == #["a": 1];'), True)
        self.assertIs(run('#["a": 1] == #["a": 2];'), False)

    def test_tip_bagi(self):
        self.assertEqual(run("m : map; m.len();"), 0)
        with self.assertRaises(RadianError):
            run("m : map = [1];")

    def test_referans_degerdir(self):
        self.assertEqual(run('a = #["x": 1]; b = a; b["y"] = 2; a.len();'), 2)

    def test_gosterim(self):
        self.assertEqual(output('print(#["a": 1, "b": [1, 2]]);'),
                         '#["a": 1, "b": [1, 2]]\n')

    def test_dongusel_gosterim(self):
        self.assertEqual(output('m = #[]; m["k"] = m; print(m);'),
                         '#["k": #[...]]\n')

    def test_type_adi(self):
        self.assertEqual(run("type(#[]);"), "map")


class TestStructs(unittest.TestCase):

    NOKTA = "struct Nokta (x:i32, y:i32); "

    def test_kurucu_ve_alan_okuma(self):
        self.assertEqual(run(self.NOKTA + "p = Nokta(3, 4); p.x;"), 3)

    def test_alan_atamasi(self):
        self.assertEqual(run(self.NOKTA + "p = Nokta(3, 4); p.y = 9; p.y;"), 9)

    def test_gosterim(self):
        self.assertEqual(output(self.NOKTA + "print(Nokta(1, 2));"),
                         "Nokta(x: 1, y: 2)\n")

    def test_esitlik_alanlara_gore(self):
        self.assertIs(run(self.NOKTA + "Nokta(1, 2) == Nokta(1, 2);"), True)
        self.assertIs(run(self.NOKTA + "Nokta(1, 2) == Nokta(1, 3);"), False)

    def test_farkli_yapilar_esit_degildir(self):
        self.assertIs(run("struct A (v:i32); struct B (v:i32); A(1) == B(1);"),
                      False)

    def test_tip_olarak_kullanilabilir(self):
        self.assertEqual(run(self.NOKTA + "p : Nokta = Nokta(1, 2); p.x;"), 1)
        with self.assertRaises(RadianError):
            run(self.NOKTA + "p : Nokta = 5;")

    def test_fonksiyon_parametresi_denetlenir(self):
        src = "struct P (x:i32); uzaklik (p:P) -> i32 { p.x; } "
        self.assertEqual(run(src + "uzaklik(P(7));"), 7)
        with self.assertRaises(RadianError):
            run(src + "uzaklik(5);")

    def test_alan_sayisi_denetimi(self):
        with self.assertRaises(RadianError) as ctx:
            run(self.NOKTA + "Nokta(1);")
        self.assertIn("alan bekliyor", str(ctx.exception))

    def test_alan_tipi_denetimi(self):
        with self.assertRaises(RadianError):
            run(self.NOKTA + 'Nokta("a", 2);')
        with self.assertRaises(RadianError):
            run(self.NOKTA + 'p = Nokta(1, 2); p.x = "a";')

    def test_bilinmeyen_alan(self):
        with self.assertRaises(RadianError) as ctx:
            run(self.NOKTA + "Nokta(1, 2).z;")
        self.assertIn("alanı yok", str(ctx.exception))
        with self.assertRaises(RadianError):
            run(self.NOKTA + "p = Nokta(1, 2); p.z = 3;")

    def test_yinelenen_alan_adi(self):
        with self.assertRaises(RadianError) as ctx:
            run("struct Q (x:i32, x:i32);")
        self.assertIn("yinelenen alan", str(ctx.exception))

    def test_referans_degerdir(self):
        self.assertEqual(run("struct N (x:i32); a = N(1); b = a; b.x = 9; a.x;"),
                         9)

    def test_ic_ice_veri_yapilari(self):
        self.assertEqual(run("struct L (n:[i32]); L([1, 2]).n.len();"), 2)
        self.assertEqual(run('struct S (m:map); S(#["a": 1]).m["a"];'), 1)

    def test_type_yapi_adini_dondurur(self):
        self.assertEqual(run("struct Kutu (ic:i32); type(Kutu(1));"), "Kutu")

    def test_yapi_dizisi(self):
        src = (self.NOKTA +
               "ps = [Nokta(1, 2), Nokta(3, 4)]; t = 0; "
               "for p in ps { t += p.x; } t;")
        self.assertEqual(run(src), 4)

    def test_dongusel_referans_yazdirilabilir(self):
        src = ("struct Dugum (deger:i32, sonraki:Dugum); "
               "d = Dugum(1, 0); ")
        # sonraki alanı Dugum bekliyor → 0 vermek hata olmalı
        with self.assertRaises(RadianError):
            run(src)


class TestBuiltins(unittest.TestCase):

    def test_print(self):
        self.assertEqual(output('print("a", 1, true);'), "a 1 true\n")

    def test_write_satir_sonu_eklemez(self):
        self.assertEqual(output('write("a"); write("b");'), "ab")

    def test_len(self):
        self.assertEqual(run('len("abcd");'), 4)
        self.assertEqual(run("len([1, 2]);"), 2)

    def test_donusumler(self):
        self.assertEqual(run('int("42");'), 42)
        self.assertEqual(run("int(3.9);"), 3)
        self.assertEqual(run('float("1.5");'), 1.5)
        self.assertEqual(run("str(42);"), "42")
        self.assertEqual(run("str(true);"), "true")

    def test_range(self):
        self.assertEqual(run("range(3);"), [0, 1, 2])
        self.assertEqual(run("range(1, 4);"), [1, 2, 3])
        self.assertEqual(run("range(0, 10, 3);"), [0, 3, 6, 9])

    def test_toplama_yardimcilari(self):
        self.assertEqual(run("sum([1, 2, 3]);"), 6)
        self.assertEqual(run("min([4, 2, 9]);"), 2)
        self.assertEqual(run("max(1, 7);"), 7)
        self.assertEqual(run("abs(-3);"), 3)

    def test_ord_ve_chr(self):
        self.assertEqual(run("ord('A');"), 65)
        self.assertEqual(run("chr(65);"), "A")
        self.assertEqual(run('ord("ş");'), 351)
        self.assertEqual(run("chr(ord('a') + 1);"), "b")

    def test_ord_tek_karakter_ister(self):
        with self.assertRaises(RadianError):
            run('ord("ab");')

    def test_chr_araligi(self):
        with self.assertRaises(RadianError):
            run("chr(-1);")
        with self.assertRaises(RadianError):
            run("chr(1.5);")

    def test_type(self):
        self.assertEqual(run("type(1);"), "int")
        self.assertEqual(run("type(1.0);"), "float")
        self.assertEqual(run("type(true);"), "bool")
        self.assertEqual(run('type("ab");'), "str")
        self.assertEqual(run("type([1]);"), "array")

    def test_assert(self):
        self.assertIs(run("assert(1 == 1);"), UNIT)
        with self.assertRaises(RadianError) as ctx:
            run('assert(1 == 2, "olmadı");')
        self.assertIn("olmadı", str(ctx.exception))

    def test_yerlesik_arguman_sayisi(self):
        with self.assertRaises(RadianError):
            run("len();")


class TestDisplay(unittest.TestCase):

    def test_bool_gosterimi(self):
        self.assertEqual(to_display(True), "true")

    def test_dizi_gosteriminde_stringler_tirnakli(self):
        self.assertEqual(output('print(["a", 1]);'), '["a", 1]\n')

    def test_unit_gosterimi(self):
        self.assertEqual(to_display(UNIT), "()")


class TestRobustness(unittest.TestCase):
    """Çökme yerine düzgün hata üretilmesi gereken sınır durumları."""

    def test_kendine_referans_veren_dizi_yazdirilabilir(self):
        self.assertEqual(output("x = [1]; x[0] = x; print(x);"), "[[...]]\n")

    def test_dolayli_dongusel_referans(self):
        self.assertEqual(output("a = []; b = [a]; a.push(b); print(a);"),
                         "[[[...]]]\n")

    def test_derin_ozyineleme_calisir(self):
        src = "say (n:i32) -> i32 { if n <= 0 { return 0; } say(n - 1); } say(900);"
        self.assertEqual(run(src), 0)

    def test_sonsuz_ozyineleme_radian_hatasi_verir(self):
        with self.assertRaises(RadianError) as ctx:
            run("f { f(); } f();")
        self.assertIn("Özyineleme derinliği", str(ctx.exception))

    def test_derinlik_siniri_ayarlanabilir(self):
        interp = Interpreter(out=io.StringIO(), max_depth=10)
        with self.assertRaises(RadianError):
            interp.run_source(
                "say (n:i32) -> i32 { if n <= 0 { return 0; } say(n - 1); } say(50);",
                symbols_file=SYMBOLS_FILE)

    def test_derinlik_sayaci_geri_sarilir(self):
        # Sınıra dayanan bir çağrıdan sonra yenisi hâlâ çalışabilmeli
        src = ("say (n:i32) -> i32 { if n <= 0 { return 0; } say(n - 1); } "
               "say(500); say(500);")
        self.assertEqual(run(src), 0)


class TestTracebacks(unittest.TestCase):

    SRC = ("bol (a:i32, b:i32) -> i32 { a / b; }\n"
           "orta (x:i32) -> i32 { bol(10, x); }\n"
           "dis () -> i32 { orta(0); }\n"
           "dis();")

    def _error(self, src: str) -> RadianError:
        with self.assertRaises(RadianError) as ctx:
            run(src)
        return ctx.exception

    def test_cagri_yigini_ictan_disa_dolar(self):
        err = self._error(self.SRC)
        self.assertEqual([name for name, _ in err.frames], ["bol", "orta", "dis"])

    def test_cerceveler_cagri_satirini_tasir(self):
        err = self._error(self.SRC)
        self.assertEqual(err.frames[0][1], 2)          # bol çağrısı 2. satırda
        self.assertEqual(err.frames[1][1], 3)          # orta çağrısı 3. satırda

    def test_metin_gosterimi(self):
        text = self._error(self.SRC).traceback_text()
        self.assertIn("çağrı yığını", text)
        self.assertIn("bol (satır 2)", text)

    def test_fonksiyon_disinda_yigin_bostur(self):
        err = self._error("1 / 0;")
        self.assertEqual(err.frames, [])
        self.assertEqual(err.traceback_text(), "")


class TestErrorPositions(unittest.TestCase):

    def test_hata_satir_sutun_tasir(self):
        with self.assertRaises(RadianError) as ctx:
            run("x = 1;\ny = yok + 2;")
        self.assertRegex(str(ctx.exception), r"\[2:\d+\]")


if __name__ == "__main__":
    unittest.main()
