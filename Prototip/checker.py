"""
Radian statik denetleyicisi — çalıştırmadan önce AST üzerinde yapılan denetim.

Kullanım:

    from checker import check_source
    hatalar = check_source(kaynak)          # [CheckError, …]  (boşsa temiz)

Tasarım ilkesi — **yanlış alarm vermemek**:

  Denetleyici yalnızca *emin olduğu* durumları bildirir. Bir ifadenin tipi
  çıkarılamıyorsa `UNKNOWN` döner ve o dal üzerinde hiçbir hata üretilmez.
  Bu yüzden burada "temiz" çıkan bir program yine de çalışma zamanında hata
  verebilir; ama denetleyicinin bildirdiği her hata gerçek bir hatadır.

Denetlenenler:
  1. Tanımsız değişken / fonksiyon (yerleşikler ve tanım öne alma dahil)
  2. Çağrı argüman sayısı (kullanıcı fonksiyonları, yapı kurucuları, yerleşikler)
  3. Argüman tipleri — parametre tipi bildirilmişse
  4. Dönüş tipi — imzada bildirilmişse (`return` ve gövde kuyruk değeri)
  5. `if`/`while` koşulu ve `!`, `&&`, `||` işlenenleri bool olmalı
  6. Bildirilmiş tipe uyumsuz atama (`x : i32 = "a"`)
  7. Yapı alanları: bilinmeyen alan, alan tipi uyumsuzluğu
  8. Aritmetik/karşılaştırma işlenen tipleri (ikisi de biliniyorsa)
  9. İndeksleme: indekslenemeyen değer, dizi indeksinin tamsayı olması
 10. Bilinmeyen metot adı (alıcının tipi kesin biliniyorsa)

Çalışma zamanı denetimleri kaldırılmadı; ikisi birbirini tamamlar
(bkz. PROGRESS.md — karar 29).
"""

from parser import Node, NodeType, ParseError, parse_source
from interpreter import (
    ARRAY_METHODS, BUILTIN_ARITIES, BUILTIN_NAMES, INT_RANGES,
    MAP_METHODS, NUMBER_METHODS, STRING_METHODS,
)


# ---------------------------------------------------------------------------
# Tanı (diagnostic)
# ---------------------------------------------------------------------------

class CheckError:
    """Statik denetim bulgusu — konumuyla birlikte."""

    def __init__(self, msg: str, node: Node | None = None):
        self.msg = msg
        self.line, self.column = _position(node)

    def __str__(self):
        loc = f" [{self.line}:{self.column}]" if self.line else ""
        return f"{self.msg}{loc}"

    def __repr__(self):
        return f"CheckError({str(self)!r})"


def _position(node: Node | None) -> tuple[int, int]:
    while node is not None:
        if node.value is not None:
            return node.value.line, node.value.column
        node = node.children[0] if node.children else None
    return 0, 0


# ---------------------------------------------------------------------------
# Tip gösterimi
#
# Statik katmanda tamsayı genişlikleri ayrıştırılmaz (i8 ile i64 aynı `int`
# sayılır); aralık denetimi çalışma zamanının işidir.
# ---------------------------------------------------------------------------

class Type:
    def __init__(self, kind: str, elem: "Type | None" = None,
                 name: str = "", params=None, ret: "Type | None" = None):
        self.kind   = kind          # ? int float bool str array map unit func struct module
        self.elem   = elem          # array eleman tipi
        self.name   = name          # struct adı
        self.params = params        # func: [(ad, Type)] ya da None
        self.ret    = ret           # func dönüş tipi

    def __eq__(self, other):
        return (isinstance(other, Type) and self.kind == other.kind
                and self.name == other.name and self.elem == other.elem)

    def __hash__(self):
        return hash((self.kind, self.name))

    def __str__(self):
        if self.kind == "array":
            return f"[{self.elem}]" if self.elem else "[?]"
        if self.kind == "struct":
            return self.name
        if self.kind == "func":
            return "fonksiyon"
        return {"?": "bilinmiyor", "int": "tamsayı", "float": "ondalık",
                "bool": "bool", "str": "str", "map": "map",
                "unit": "unit", "module": "modül"}.get(self.kind, self.kind)


UNKNOWN = Type("?")
INT     = Type("int")
FLOAT   = Type("float")
BOOL    = Type("bool")
STR     = Type("str")
MAP     = Type("map")
UNIT    = Type("unit")
MODULE  = Type("module")


def array_of(elem: Type | None = None) -> Type:
    return Type("array", elem=elem or UNKNOWN)


def struct_of(name: str) -> Type:
    return Type("struct", name=name)


def func_type(params=None, ret: Type | None = None) -> Type:
    return Type("func", params=params, ret=ret or UNKNOWN)


NUMERIC = {"int", "float"}


def is_unknown(t: Type | None) -> bool:
    return t is None or t.kind == "?"


def assignable(target: Type | None, value: Type | None) -> bool:
    """value, target'a atanabilir mi? Emin olunamıyorsa True (yanlış alarm yok)."""
    if is_unknown(target) or is_unknown(value):
        return True
    if target.kind == "float" and value.kind == "int":
        return True                                  # int → float genişlemesi
    if target.kind != value.kind:
        return False
    if target.kind == "struct":
        return target.name == value.name
    if target.kind == "array":
        return assignable(target.elem, value.elem)
    return True


# ---------------------------------------------------------------------------
# Kapsam
# ---------------------------------------------------------------------------

class Scope:
    def __init__(self, parent: "Scope | None" = None):
        self.names: dict[str, Type] = {}
        self.declared: set[str]     = set()    # ':' ile tipi bildirilenler
        self.parent = parent

    def define(self, name: str, type_: Type, declared: bool = False) -> None:
        self.names[name] = type_
        if declared:
            self.declared.add(name)

    def find(self, name: str) -> "Scope | None":
        scope = self
        while scope is not None:
            if name in scope.names:
                return scope
            scope = scope.parent
        return None

    def lookup(self, name: str) -> Type | None:
        scope = self.find(name)
        return scope.names[name] if scope else None


# ---------------------------------------------------------------------------
# Denetleyici
# ---------------------------------------------------------------------------

class Checker:

    def __init__(self):
        self.errors: list[CheckError] = []
        self.structs: dict[str, list[tuple[str, Type]]] = {}
        self.global_scope = Scope()
        for name in BUILTIN_NAMES:
            self.global_scope.define(name, func_type())

    # ------------------------------------------------------------------
    # Giriş noktası
    # ------------------------------------------------------------------

    def check(self, program: Node) -> list[CheckError]:
        self._check_block_body(program.children, self.global_scope)
        self.errors.sort(key=lambda e: (e.line, e.column))
        return self.errors

    def error(self, msg: str, node: Node | None) -> None:
        self.errors.append(CheckError(msg, node))

    # ------------------------------------------------------------------
    # Deyim listesi — önce tanımları öne al (hoisting)
    # ------------------------------------------------------------------

    def _check_block_body(self, statements: list[Node], scope: Scope) -> Type:
        # 1. geçiş: fonksiyon ve yapı adlarını kapsama tanıt.
        # Yorumlayıcı da gövdeleri çağrı anında çözdüğü için, aynı blokta
        # sonra tanımlanan bir fonksiyona başvurmak geçerlidir.
        for stmt in statements:
            node = self._unwrap(stmt)
            if node is None:
                continue
            if node.type == NodeType.FUNC_DEF:
                scope.define(node.value.value, self._function_type(node))
            elif node.type == NodeType.STRUCT_DEF:
                self._declare_struct(node, scope)

        # 2. geçiş: gövdeler
        last = UNIT
        for stmt in statements:
            last = self._check_statement(stmt, scope)
        return last

    @staticmethod
    def _unwrap(stmt: Node) -> Node | None:
        if stmt.type == NodeType.STATEMENT:
            return stmt.children[0] if stmt.children else None
        return stmt

    def _check_statement(self, stmt: Node, scope: Scope) -> Type:
        node = self._unwrap(stmt)
        if node is None:
            return UNIT
        return self._check_node(node, scope)

    def _check_node(self, node: Node, scope: Scope) -> Type:
        if node.type == NodeType.FUNC_DEF:
            return self._check_funcdef(node, scope)
        if node.type == NodeType.STRUCT_DEF:
            return UNIT                              # 1. geçişte tanıtıldı
        if node.type == NodeType.RETURN:
            value = (self._infer(node.children[0], scope)
                     if node.children else UNIT)
            self._check_return(value, node)
            return UNIT
        if node.type in (NodeType.BREAK, NodeType.CONTINUE):
            return UNIT
        return self._infer(node, scope)

    # ------------------------------------------------------------------
    # Tanımlar
    # ------------------------------------------------------------------

    def _declare_struct(self, node: Node, scope: Scope) -> None:
        name   = node.value.value
        fields = []
        for param in node.children:
            if param.value is None:
                continue
            fields.append((param.value.value,
                           self._type_from_node(param.children[0]
                                                if param.children else None)))
        self.structs[name] = fields
        scope.define(name, func_type([(f, t) for f, t in fields],
                                     struct_of(name)))

    def _function_type(self, node: Node) -> Type:
        signature = (node.children[0]
                     if node.children and node.children[0].type == NodeType.FUNC_TYPE
                     else None)
        if signature is None:
            return func_type([], UNKNOWN)

        *param_nodes, ret_node = signature.children
        params = []
        for param in param_nodes:
            pname = param.value.value if param.value else ""
            ptype = self._type_from_node(param.children[0]
                                         if param.children else None)
            params.append((pname, ptype))
        ret = self._type_from_node(ret_node.children[0]
                                   if ret_node.children else None)
        return func_type(params, ret)

    def _check_funcdef(self, node: Node, scope: Scope) -> Type:
        ftype = self._function_type(node)
        scope.define(node.value.value, ftype)

        body  = node.children[-1]
        inner = Scope(scope)
        for pname, ptype in (ftype.params or []):
            if pname:
                inner.define(pname, ptype, declared=not is_unknown(ptype))

        previous, self._return_type = getattr(self, "_return_type", None), ftype.ret
        previous_name, self._func_name = getattr(self, "_func_name", ""), node.value.value
        try:
            tail = self._check_block_body(body.children, inner)
            # Gövdenin kuyruk değeri de dönüş tipine uymalı
            if body.children:
                self._check_return(tail, body.children[-1])
        finally:
            self._return_type = previous
            self._func_name   = previous_name
        return ftype

    def _check_return(self, value: Type, node: Node) -> None:
        expected = getattr(self, "_return_type", None)
        if expected is None or is_unknown(expected) or is_unknown(value):
            return
        # Kuyruk değeri unit ise (örn. son deyim bir while) bilgi vermez
        if value.kind == "unit":
            return
        if not assignable(expected, value):
            name = getattr(self, "_func_name", "")
            self.error(
                f"'{name}' dönüş tipi {expected} bildirilmiş ama {value} "
                f"döndürülüyor", node)

    # ------------------------------------------------------------------
    # Tip düğümünden statik tip
    # ------------------------------------------------------------------

    def _type_from_node(self, node: Node | None) -> Type:
        if node is None:
            return UNKNOWN
        if node.type == NodeType.TYPE_PARAM:
            return self._type_from_node(node.children[0] if node.children else None)
        if node.type == NodeType.ARRAY:
            return array_of(self._type_from_node(node.children[0])
                            if node.children else UNKNOWN)
        if node.type in (NodeType.FUNC_TYPE, NodeType.TUPLE_TYPE):
            return func_type()
        if node.type == NodeType.LITERAL and node.value is not None:
            name = node.value.value
            if name in INT_RANGES:
                return INT
            if name in ("f32", "f64"):
                return FLOAT
            if name == "bool":
                return BOOL
            if name in ("str", "char"):
                return STR
            if name == "map":
                return MAP
            if name in self.structs:
                return struct_of(name)
        return UNKNOWN

    # ------------------------------------------------------------------
    # İfade tipi çıkarımı  (emin değilsek UNKNOWN)
    # ------------------------------------------------------------------

    def _infer(self, node: Node, scope: Scope) -> Type:
        method = self._INFER.get(node.type)
        if method is None:
            return UNKNOWN
        return method(self, node, scope)

    def _infer_literal(self, node: Node, scope: Scope) -> Type:
        tok = node.value
        kind = tok.type.name
        if kind == "LITERAL_NUM":
            text = tok.value
            if text.startswith(("0x", "0b", "0o", "0X", "0B", "0O")):
                return INT
            return FLOAT if ("." in text or "e" in text or "E" in text) else INT
        if kind in ("LITERAL_STR", "LITERAL_CHAR"):
            return STR
        if tok.value in ("true", "false"):
            return BOOL
        # Tip adı ifade konumunda (bool, char …) → çalışma zamanı çözer
        return UNKNOWN

    def _infer_identifier(self, node: Node, scope: Scope) -> Type:
        name = node.value.value
        found = scope.lookup(name)
        if found is None:
            self.error(f"Tanımsız değişken: '{name}'", node)
            return UNKNOWN
        return found

    def _infer_array(self, node: Node, scope: Scope) -> Type:
        elem: Type | None = None
        for child in node.children:
            child_type = self._infer(child, scope)
            if is_unknown(child_type):
                return array_of(UNKNOWN)
            if elem is None:
                elem = child_type
            elif elem != child_type:
                return array_of(UNKNOWN)             # karışık → bilinmiyor
        return array_of(elem or UNKNOWN)

    def _infer_map(self, node: Node, scope: Scope) -> Type:
        for child in node.children:
            self._infer(child, scope)
        return MAP

    def _infer_block(self, node: Node, scope: Scope) -> Type:
        return self._check_block_body(node.children, Scope(scope))

    def _infer_assign(self, node: Node, scope: Scope) -> Type:
        target, value_node = node.children
        value_type = self._infer(value_node, scope)

        if node.value.value != "=":                  # bileşik atama
            current = self._infer(target, scope)
            return self._binary_result(node.value.value[:-1], current,
                                       value_type, node)

        # x : T = deger
        if target.type == NodeType.TYPEBIND:
            inner, type_node = target.children
            declared = self._type_from_node(type_node)
            if inner.type == NodeType.IDENTIFIER:
                name = inner.value.value
                if not assignable(declared, value_type):
                    self.error(
                        f"'{name}' {declared} olarak bildirilmiş ama "
                        f"{value_type} atanıyor", node)
                (scope.find(name) or scope).define(name, declared, declared=True)
            return declared

        if target.type == NodeType.IDENTIFIER:
            name  = target.value.value
            owner = scope.find(name)
            if owner is not None and name in owner.declared:
                declared = owner.names[name]
                if not assignable(declared, value_type):
                    self.error(
                        f"'{name}' {declared} olarak bildirilmiş ama "
                        f"{value_type} atanıyor", node)
                return declared
            # Bildirilmemiş: çıkarılan tiple tanımla, çelişirse bilinmiyene düş
            if owner is None:
                scope.define(name, value_type)
            elif owner.names[name] != value_type:
                owner.names[name] = UNKNOWN
            return value_type

        if target.type == NodeType.MEMBER:
            self._check_member_assign(target, value_type, scope)
            return value_type

        if target.type == NodeType.INDEX:
            self._infer(target, scope)
            return value_type

        return value_type

    def _infer_typebind(self, node: Node, scope: Scope) -> Type:
        target, type_node = node.children
        declared = self._type_from_node(type_node)
        if target.type == NodeType.IDENTIFIER:
            name = target.value.value
            (scope.find(name) or scope).define(name, declared, declared=True)
            return declared
        value = self._infer(target, scope)
        if not assignable(declared, value):
            self.error(f"{declared} bekleniyordu ama {value} bulundu", node)
        return declared

    def _infer_binary(self, node: Node, scope: Scope) -> Type:
        left_node, op_node, right_node = node.children
        op = op_node.value.value

        left  = self._infer(left_node, scope)
        right = self._infer(right_node, scope)

        if op in ("&&", "||"):
            self._require_bool(left, op, left_node)
            self._require_bool(right, op, right_node)
            return BOOL
        return self._binary_result(op, left, right, node)

    def _binary_result(self, op: str, left: Type, right: Type, node: Node) -> Type:
        if op in ("==", "!="):
            return BOOL

        if op in ("<", ">", "<=", ">="):
            if not (is_unknown(left) or is_unknown(right)):
                ok = ((left.kind in NUMERIC and right.kind in NUMERIC)
                      or (left.kind == "str" and right.kind == "str"))
                if not ok:
                    self.error(
                        f"'{op}' operatörü {left} ve {right} için tanımlı değil",
                        node)
            return BOOL

        if op in ("&", "|", "^", "<<", ">>"):
            for side in (left, right):
                if not is_unknown(side) and side.kind != "int":
                    self.error(f"'{op}' operatörü tamsayı bekler, {side} bulundu",
                               node)
            return INT

        if op in ("+", "-", "*", "/", "%", "**"):
            if is_unknown(left) or is_unknown(right):
                return UNKNOWN
            if op == "+" and left.kind == "str" and right.kind == "str":
                return STR
            if op == "+" and left.kind == "array" and right.kind == "array":
                return left if left == right else array_of(UNKNOWN)
            if op == "*" and left.kind in ("str", "array") and right.kind == "int":
                return left
            if left.kind in NUMERIC and right.kind in NUMERIC:
                if left.kind == "float" or right.kind == "float":
                    return FLOAT
                return INT
            self.error(f"'{op}' operatörü {left} ve {right} için tanımlı değil",
                       node)
            return UNKNOWN

        return UNKNOWN                               # özel operatör

    def _infer_unary(self, node: Node, scope: Scope) -> Type:
        op_node, operand = node.children
        op    = op_node.value.value
        value = self._infer(operand, scope)

        if op == "!":
            self._require_bool(value, "!", node)
            return BOOL
        if op == "~":
            if not is_unknown(value) and value.kind != "int":
                self.error(f"'~' operatörü tamsayı bekler, {value} bulundu", node)
            return INT
        if not is_unknown(value) and value.kind not in NUMERIC:
            self.error(f"'{op}' operatörü sayı bekler, {value} bulundu", node)
            return UNKNOWN
        return value

    def _infer_incdec(self, node: Node, scope: Scope) -> Type:
        value = self._infer(node.children[0], scope)
        if not is_unknown(value) and value.kind not in NUMERIC:
            self.error(
                f"'{node.value.value}' sayı bekler, {value} bulundu", node)
        return value

    def _infer_if(self, node: Node, scope: Scope) -> Type:
        cond = self._infer(node.children[0], scope)
        self._require_bool(cond, "if", node.children[0])

        then_type = self._infer(node.children[1], scope)
        if len(node.children) < 3:
            return UNIT
        else_type = self._infer(node.children[2], scope)
        return then_type if then_type == else_type else UNKNOWN

    def _infer_while(self, node: Node, scope: Scope) -> Type:
        cond = self._infer(node.children[0], scope)
        self._require_bool(cond, "while", node.children[0])
        self._infer(node.children[1], scope)
        return UNKNOWN                               # hiç dönmeyebilir → unit

    def _infer_for(self, node: Node, scope: Scope) -> Type:
        iterable = self._infer(node.children[0], scope)
        item = UNKNOWN
        if not is_unknown(iterable):
            if iterable.kind == "array":
                item = iterable.elem or UNKNOWN
            elif iterable.kind == "str":
                item = STR
            elif iterable.kind == "map":
                item = UNKNOWN                       # anahtar tipi izlenmiyor
            else:
                self.error(f"{iterable} üzerinde döngü kurulamaz",
                           node.children[0])

        inner = Scope(scope)
        inner.define(node.value.value, item)
        self._check_block_body(node.children[1].children, Scope(inner))
        return UNKNOWN

    def _infer_index(self, node: Node, scope: Scope) -> Type:
        obj   = self._infer(node.children[0], scope)
        index = self._infer(node.children[1], scope)

        if is_unknown(obj):
            return UNKNOWN
        if obj.kind == "array":
            if not is_unknown(index) and index.kind != "int":
                self.error(f"Dizi indeksi tamsayı olmalı, {index} bulundu",
                           node.children[1])
            return obj.elem or UNKNOWN
        if obj.kind == "str":
            if not is_unknown(index) and index.kind != "int":
                self.error(f"String indeksi tamsayı olmalı, {index} bulundu",
                           node.children[1])
            return STR
        if obj.kind == "map":
            return UNKNOWN
        self.error(f"{obj} indekslenemez", node)
        return UNKNOWN

    def _infer_member(self, node: Node, scope: Scope) -> Type:
        obj  = self._infer(node.children[0], scope)
        name = node.value.value

        if is_unknown(obj) or obj.kind == "module":
            return UNKNOWN
        if obj.kind == "struct":
            fields = self.structs.get(obj.name)
            if fields is None:
                return UNKNOWN
            for fname, ftype in fields:
                if fname == name:
                    return ftype
            alanlar = ", ".join(f for f, _ in fields)
            self.error(
                f"'{obj.name}' yapısının '{name}' alanı yok (alanlar: {alanlar})",
                node)
            return UNKNOWN

        table = {"array": ARRAY_METHODS, "map": MAP_METHODS,
                 "str": STRING_METHODS, "int": NUMBER_METHODS,
                 "float": NUMBER_METHODS}.get(obj.kind)
        if table is None:
            self.error(f"{obj} değerinin '{name}' üyesi yok", node)
            return UNKNOWN
        if name not in table:
            self.error(f"{obj} değerinin '{name}' metodu yok", node)
            return UNKNOWN
        return self._method_result(obj, name)

    @staticmethod
    def _method_result(obj: Type, name: str) -> Type:
        """Bilinen metotların dönüş tipi — bilinmeyenler UNKNOWN."""
        if name == "len":
            return func_type([], INT)
        if obj.kind == "array":
            if name in ("push", "insert", "reverse", "sort", "slice", "filter"):
                return func_type(None, obj)
            if name == "index_of":
                return func_type(None, INT)
            if name == "contains":
                return func_type(None, BOOL)
            if name == "join":
                return func_type(None, STR)
            if name == "pop":
                return func_type([], obj.elem or UNKNOWN)
        if obj.kind == "str":
            if name in ("upper", "lower", "trim", "replace", "slice", "repeat"):
                return func_type(None, STR)
            if name in ("contains", "starts_with", "ends_with"):
                return func_type(None, BOOL)
            if name == "find":
                return func_type(None, INT)
            if name in ("split", "chars"):
                return func_type(None, array_of(STR))
        if obj.kind == "map":
            if name == "has":
                return func_type(None, BOOL)
            if name in ("keys", "values", "pairs"):
                return func_type(None, array_of(UNKNOWN))
            if name in ("set", "clear", "merge"):
                return func_type(None, MAP)
        if obj.kind in NUMERIC:
            if name in ("abs", "min", "max"):
                return func_type(None, obj)
            if name == "to_str":
                return func_type(None, STR)
        return func_type()

    def _check_member_assign(self, target: Node, value: Type, scope: Scope) -> None:
        obj  = self._infer(target.children[0], scope)
        name = target.value.value
        if is_unknown(obj) or obj.kind != "struct":
            return
        fields = self.structs.get(obj.name)
        if fields is None:
            return
        for fname, ftype in fields:
            if fname == name:
                if not assignable(ftype, value):
                    self.error(
                        f"'{obj.name}.{name}' alanı {ftype} ama {value} atanıyor",
                        target)
                return
        alanlar = ", ".join(f for f, _ in fields)
        self.error(
            f"'{obj.name}' yapısının '{name}' alanı yok (alanlar: {alanlar})",
            target)

    def _infer_call(self, node: Node, scope: Scope) -> Type:
        callee_node, *arg_nodes = node.children
        callee = self._infer(callee_node, scope)
        args   = [self._infer(a, scope) for a in arg_nodes]

        # Yerleşik: yalnızca arite denetlenir
        if (callee_node.type == NodeType.IDENTIFIER
                and callee_node.value.value in BUILTIN_ARITIES
                and scope.find(callee_node.value.value) is self.global_scope):
            self._check_builtin_arity(callee_node.value.value, len(args), node)
            return UNKNOWN

        if is_unknown(callee):
            return UNKNOWN
        if callee.kind != "func":
            self.error(f"{callee} çağrılabilir değil", node)
            return UNKNOWN

        params = callee.params
        if params is not None:
            adi = (callee_node.value.value
                   if callee_node.type == NodeType.IDENTIFIER else "fonksiyon")
            if len(args) != len(params):
                self.error(
                    f"'{adi}' {len(params)} argüman bekliyor, "
                    f"{len(args)} verildi", node)
            else:
                for (pname, ptype), (arg_type, arg_node) in zip(
                        params, zip(args, arg_nodes)):
                    if not assignable(ptype, arg_type):
                        self.error(
                            f"'{adi}' fonksiyonunun '{pname}' parametresi "
                            f"{ptype} ama {arg_type} verildi", arg_node)
        return callee.ret or UNKNOWN

    def _check_builtin_arity(self, name: str, count: int, node: Node) -> None:
        arity = BUILTIN_ARITIES.get(name)
        if arity is None:
            return
        if isinstance(arity, tuple):
            low, high = arity
            if count < low or (high is not None and count > high):
                beklenen = f"{low}..{high if high is not None else '*'}"
                self.error(f"'{name}' {beklenen} argüman bekliyor, "
                           f"{count} verildi", node)
        elif count != arity:
            self.error(f"'{name}' {arity} argüman bekliyor, {count} verildi",
                       node)

    def _infer_import(self, node: Node, scope: Scope) -> Type:
        self._infer(node.children[0], scope)
        return MODULE                                # içeriği statik izlenmiyor

    def _require_bool(self, value: Type, what: str, node: Node) -> None:
        if not is_unknown(value) and value.kind != "bool":
            self.error(f"'{what}' bool bekler, {value} bulundu", node)

    _INFER = {}


Checker._INFER = {
    NodeType.LITERAL:    Checker._infer_literal,
    NodeType.IDENTIFIER: Checker._infer_identifier,
    NodeType.ARRAY:      Checker._infer_array,
    NodeType.MAP:        Checker._infer_map,
    NodeType.BLOCK:      Checker._infer_block,
    NodeType.ASSIGN:     Checker._infer_assign,
    NodeType.TYPEBIND:   Checker._infer_typebind,
    NodeType.BINARY_OP:  Checker._infer_binary,
    NodeType.UNARY_OP:   Checker._infer_unary,
    NodeType.PRE_OP:     Checker._infer_incdec,
    NodeType.POST_OP:    Checker._infer_incdec,
    NodeType.IF:         Checker._infer_if,
    NodeType.WHILE:      Checker._infer_while,
    NodeType.FOR:        Checker._infer_for,
    NodeType.INDEX:      Checker._infer_index,
    NodeType.MEMBER:     Checker._infer_member,
    NodeType.CALL:       Checker._infer_call,
    NodeType.IMPORT:     Checker._infer_import,
    NodeType.STATEMENT:  lambda self, node, scope: (
        self._infer(node.children[0], scope) if node.children else UNIT),
    NodeType.FUNC_DEF:   Checker._check_funcdef,
}


# ---------------------------------------------------------------------------
# Kolaylık fonksiyonları
# ---------------------------------------------------------------------------

def check(program: Node) -> list[CheckError]:
    """AST'yi denetler; bulgu listesi döndürür (boşsa temiz)."""
    return Checker().check(program)


def check_source(source: str, symbols_file: str = "symbols.txt") -> list[CheckError]:
    """Kaynağı parse edip denetler. Sözdizimi hatası ParseError olarak yükselir."""
    return check(parse_source(source, symbols_file=symbols_file))


# ---------------------------------------------------------------------------
# Hızlı test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ORNEKLER = [
        ("temiz",            'kare (x:i32) -> i32 { x * x; } kare(4);'),
        ("tanımsız değişken", "x = yok + 1;"),
        ("argüman sayısı",    "f (a:i32) -> i32 { a; } f(1, 2);"),
        ("argüman tipi",      'f (a:i32) -> i32 { a; } f("abc");'),
        ("dönüş tipi",        'f () -> i32 { "abc"; } f();'),
        ("koşul bool değil",  "if 1 { 2; }"),
        ("bildirilmiş tip",   'x : i32 = "abc";'),
        ("operatör tipi",     'y = 1 + "a";'),
        ("bilinmeyen alan",   "struct N (x:i32); p = N(1); p.z;"),
        ("bilinmeyen metot",  'xs = [1]; xs.yok();'),
        ("indeksleme",        "b = true; b[0];"),
    ]

    for etiket, kaynak in ORNEKLER:
        print(f"\n{etiket}: {kaynak}")
        try:
            bulgular = check_source(kaynak)
        except ParseError as err:
            print(f"  sözdizimi hatası: {err}")
            continue
        if not bulgular:
            print("  temiz")
        for bulgu in bulgular:
            print(f"  → {bulgu}")
