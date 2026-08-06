"""
Radian yorumlayıcısı — AST üzerinde doğrudan yürüyen (tree-walking) evaluator.

Kullanım:

    from interpreter import Interpreter
    from parser import parse_source

    Interpreter().run(parse_source(kaynak))

Tasarım notları (ayrıntı için PROGRESS.md §2):
  - Değerler Python nesneleridir: int, float, str, bool, list, Function, UNIT.
  - Her blok yeni bir kapsam (Environment) açar; "=" mevcut değişkeni zincirde
    arar, bulamazsa geçerli kapsamda tanımlar.
  - Tipler ":" ile bağlanır; bağlama anında *doğrulanır*, zorlanmaz.
  - Koşullar ve mantıksal operatörler kesin olarak bool ister.
"""

import os
import sys

from parser import Node, NodeType, ParseError, parse_source


# ---------------------------------------------------------------------------
# Çalışma zamanı hatası
# ---------------------------------------------------------------------------

class RadianError(Exception):
    """Çalışma zamanı hatası — kaynak konumu ve çağrı yığınıyla birlikte."""

    def __init__(self, msg: str, node: "Node | None" = None):
        self.line, self.column = _node_position(node)
        loc = f" [{self.line}:{self.column}]" if self.line else ""
        super().__init__(f"{msg}{loc}")
        self.msg = msg
        # Hata yayılırken en içteki çağrıdan dışa doğru doldurulur:
        # [(fonksiyon adı, çağrı satırı), …]
        self.frames: list[tuple[str, int]] = []

    def traceback_text(self) -> str:
        """Çağrı yığınını okunabilir metne çevirir (boşsa boş dize)."""
        if not self.frames:
            return ""
        lines = ["  çağrı yığını (içten dışa):"]
        for name, line in self.frames:
            where = f" (satır {line})" if line else ""
            lines.append(f"    {name}{where}")
        return "\n".join(lines)


def _node_position(node: "Node | None") -> tuple[int, int]:
    """Düğümün (ya da ilk token taşıyan çocuğunun) satır/sütun bilgisi."""
    while node is not None:
        if node.value is not None:
            return node.value.line, node.value.column
        node = node.children[0] if node.children else None
    return 0, 0


# ---------------------------------------------------------------------------
# Unit — değer üretmeyen ifadelerin sonucu (boş blok, print, while …)
# ---------------------------------------------------------------------------

class UnitType:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "()"


UNIT = UnitType()


# ---------------------------------------------------------------------------
# Akış denetimi sinyalleri — Python exception'ı olarak taşınır
# ---------------------------------------------------------------------------

class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


# ---------------------------------------------------------------------------
# Fonksiyon değerleri
# ---------------------------------------------------------------------------

class Function:
    """Kullanıcı tanımlı fonksiyon — tanımlandığı kapsamı (closure) taşır."""

    def __init__(self, name: str, params: list[tuple[str, Node | None]],
                 body: Node, closure: "Environment",
                 return_type: Node | None = None):
        self.name        = name
        self.params      = params            # [(isim, tip düğümü | None), …]
        self.body        = body
        self.closure     = closure
        self.return_type = return_type

    @property
    def arity(self) -> int:
        return len(self.params)

    def __repr__(self):
        return f"<fonksiyon {self.name}/{self.arity}>"


class Builtin:
    """Yerleşik fonksiyon — Python callable sarmalayıcısı."""

    def __init__(self, name: str, fn, arity=None):
        self.name  = name
        self.fn    = fn
        self.arity = arity                   # int, (min, max) ya da None (serbest)

    def __repr__(self):
        return f"<yerleşik {self.name}>"


class BoundMethod:
    """Bir değere bağlanmış yerleşik metot: xs.push, s.upper …"""

    def __init__(self, receiver, builtin: Builtin):
        self.receiver = receiver
        self.builtin  = builtin

    @property
    def name(self) -> str:
        return self.builtin.name

    def __repr__(self):
        return f"<metot {self.builtin.name}>"


class StructType:
    """Kullanıcı tanımlı kayıt tipi. Adı hem tip hem kurucu fonksiyondur."""

    def __init__(self, name: str, fields: list[tuple[str, Node | None]]):
        self.name   = name
        self.fields = fields                 # [(alan adı, tip düğümü | None), …]

    @property
    def arity(self) -> int:
        return len(self.fields)

    def field_names(self) -> list[str]:
        return [name for name, _ in self.fields]

    def __repr__(self):
        return f"<yapı {self.name}/{self.arity}>"


class StructInstance:
    """Bir StructType örneği — alanları sözlükte tutar (referans değer)."""

    def __init__(self, struct_type: StructType, values: dict):
        self.struct_type = struct_type
        self.values      = values

    @property
    def name(self) -> str:
        return self.struct_type.name

    def __repr__(self):
        inner = ", ".join(f"{k}: {v!r}" for k, v in self.values.items())
        return f"{self.name}({inner})"


class Module:
    """`import` ile yüklenen bir dosyanın üst düzey tanımları."""

    def __init__(self, path: str, values: dict):
        self.path   = path
        self.values = values

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    def __repr__(self):
        return f"<modül {self.name}>"


CALLABLE_TYPES = (Function, Builtin, BoundMethod, StructType)


# ---------------------------------------------------------------------------
# Kapsam (Environment)
# ---------------------------------------------------------------------------

class Environment:
    """Zincirlenmiş kapsam: değişken değerleri + bildirilen tipleri."""

    def __init__(self, parent: "Environment | None" = None):
        self.values: dict[str, object]      = {}
        self.types:  dict[str, Node | None] = {}
        self.parent = parent

    # --- tanımlama / arama ------------------------------------------------

    def define(self, name: str, value, type_node: Node | None = None) -> None:
        self.values[name] = value
        if type_node is not None:
            self.types[name] = type_node

    def lookup_scope(self, name: str) -> "Environment | None":
        env = self
        while env is not None:
            if name in env.values:
                return env
            env = env.parent
        return None

    def get(self, name: str, node: Node | None = None):
        env = self.lookup_scope(name)
        if env is None:
            raise RadianError(f"Tanımsız değişken: '{name}'", node)
        return env.values[name]

    def assign(self, name: str, value, node: Node | None = None) -> None:
        """Zincirde varsa mevcut değişkeni günceller, yoksa burada tanımlar."""
        env = self.lookup_scope(name) or self
        declared = env.types.get(name)
        if declared is not None:
            check_type(value, declared, name, node, env)
        env.values[name] = value

    def declared_type(self, name: str) -> Node | None:
        env = self.lookup_scope(name)
        return env.types.get(name) if env else None


# ---------------------------------------------------------------------------
# Tip doğrulama  (bkz. PROGRESS.md §2, karar 5)
# ---------------------------------------------------------------------------

INT_RANGES = {
    "i8":  (-2**7,  2**7  - 1),
    "i16": (-2**15, 2**15 - 1),
    "i32": (-2**31, 2**31 - 1),
    "i64": (-2**63, 2**63 - 1),
    "u8":  (0, 2**8  - 1),
    "u16": (0, 2**16 - 1),
    "u32": (0, 2**32 - 1),
    "u64": (0, 2**64 - 1),
}

FLOAT_TYPES = {"f32", "f64"}


def type_name(value) -> str:
    """Değerin çalışma zamanı tip adı — hata mesajlarında kullanılır."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "char" if len(value) == 1 else "str"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "map"
    if isinstance(value, StructInstance):
        return value.name
    if isinstance(value, StructType):
        return "struct"
    if isinstance(value, Module):
        return "module"
    if isinstance(value, CALLABLE_TYPES):
        return "func"
    if value is UNIT:
        return "unit"
    return "unknown"


def type_repr(type_node: Node | None) -> str:
    """Tip düğümünün okunabilir gösterimi."""
    if type_node is None:
        return "?"
    if type_node.type == NodeType.LITERAL:
        return type_node.value.value
    if type_node.type == NodeType.ARRAY:
        inner = type_repr(type_node.children[0]) if type_node.children else "?"
        return f"[{inner}]"
    if type_node.type == NodeType.FUNC_TYPE:
        return "fonksiyon tipi"
    if type_node.type == NodeType.TUPLE_TYPE:
        return "demet tipi"
    if type_node.type == NodeType.TYPE_PARAM and type_node.children:
        return type_repr(type_node.children[0])
    return "?"


def check_type(value, type_node: Node | None, name: str = "",
               node: Node | None = None, env: "Environment | None" = None) -> None:
    """Değer bildirilen tiple uyumlu değilse RadianError fırlatır.

    `env` verilirse bilinmeyen tip adları çevrede aranır; bir StructType'a
    çözülüyorsa değerin o yapının örneği olması gerekir.
    """
    if type_node is None:
        return

    if type_node.type == NodeType.TYPE_PARAM:
        if type_node.children:
            check_type(value, type_node.children[0], name, node, env)
        return

    where = f" ('{name}')" if name else ""

    # --- dizi tipi: [T] ---
    if type_node.type == NodeType.ARRAY:
        if not isinstance(value, list):
            raise RadianError(
                f"Tip uyuşmazlığı{where}: {type_repr(type_node)} bekleniyordu, "
                f"{type_name(value)} bulundu", node)
        if type_node.children:
            for item in value:
                check_type(item, type_node.children[0], name, node, env)
        return

    # --- fonksiyon tipi ---
    if type_node.type in (NodeType.FUNC_TYPE, NodeType.TUPLE_TYPE):
        if not isinstance(value, CALLABLE_TYPES):
            raise RadianError(
                f"Tip uyuşmazlığı{where}: fonksiyon bekleniyordu, "
                f"{type_name(value)} bulundu", node)
        return

    if type_node.type != NodeType.LITERAL or type_node.value is None:
        return                                    # bilinmeyen tip → serbest

    tname = type_node.value.value

    if tname in INT_RANGES:
        if isinstance(value, bool) or not isinstance(value, int):
            raise RadianError(
                f"Tip uyuşmazlığı{where}: {tname} bekleniyordu, "
                f"{type_name(value)} bulundu", node)
        low, high = INT_RANGES[tname]
        if not (low <= value <= high):
            raise RadianError(
                f"Değer {tname} aralığının dışında{where}: {value} "
                f"(izin verilen: {low}..{high})", node)
        return

    if tname in FLOAT_TYPES:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RadianError(
                f"Tip uyuşmazlığı{where}: {tname} bekleniyordu, "
                f"{type_name(value)} bulundu", node)
        return

    if tname == "bool":
        if not isinstance(value, bool):
            raise RadianError(
                f"Tip uyuşmazlığı{where}: bool bekleniyordu, "
                f"{type_name(value)} bulundu", node)
        return

    if tname == "char":
        if not isinstance(value, str) or len(value) != 1:
            raise RadianError(
                f"Tip uyuşmazlığı{where}: char bekleniyordu, "
                f"{type_name(value)} bulundu", node)
        return

    if tname == "str":
        if not isinstance(value, str):
            raise RadianError(
                f"Tip uyuşmazlığı{where}: str bekleniyordu, "
                f"{type_name(value)} bulundu", node)
        return

    if tname == "map":
        if not isinstance(value, dict):
            raise RadianError(
                f"Tip uyuşmazlığı{where}: map bekleniyordu, "
                f"{type_name(value)} bulundu", node)
        return

    # Kullanıcı tanımlı yapı adı → çevrede ara
    if env is not None:
        scope = env.lookup_scope(tname)
        declared = scope.values.get(tname) if scope else None
        if isinstance(declared, StructType):
            if not isinstance(value, StructInstance) or value.struct_type is not declared:
                raise RadianError(
                    f"Tip uyuşmazlığı{where}: {tname} bekleniyordu, "
                    f"{type_name(value)} bulundu", node)
            return

    # Bilinmeyen tip adı → şimdilik serbest


def map_key(value, node: Node | None = None):
    """Harita anahtarı olarak geçerli mi? Değilse RadianError.

    bool kabul edilmez: Python sözlüğünde `true` ile `1` aynı anahtara
    düşerdi, oysa Radian'da `1 == true` yanlıştır.
    """
    if isinstance(value, bool):
        raise RadianError("Harita anahtarı bool olamaz", node)
    if isinstance(value, (str, int, float)):
        return value
    raise RadianError(
        f"Harita anahtarı sayı ya da str olmalı, {type_name(value)} bulundu",
        node)


def zero_value(type_node: Node | None):
    """Değersiz bildirimin (`x : i32;`) başlangıç değeri."""
    if type_node is None:
        return UNIT
    if type_node.type == NodeType.ARRAY:
        return []
    if type_node.type == NodeType.LITERAL and type_node.value is not None:
        tname = type_node.value.value
        if tname in INT_RANGES:
            return 0
        if tname in FLOAT_TYPES:
            return 0.0
        if tname == "bool":
            return False
        if tname in ("str", "char"):
            return ""
        if tname == "map":
            return {}
    return UNIT


# ---------------------------------------------------------------------------
# Değer gösterimi
# ---------------------------------------------------------------------------

def to_display(value, _seen: set | None = None) -> str:
    """print() çıktısındaki gösterim — string'ler tırnaksızdır.

    Diziler referans değer olduğu için kendini içerebilirler
    (`x = [1]; x[0] = x;`); döngü `[...]` ile kesilir.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is UNIT:
        return "()"
    if isinstance(value, str):
        return value
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, list):
        seen = _seen or set()
        if id(value) in seen:
            return "[...]"                        # döngüsel referans
        seen = seen | {id(value)}
        return "[" + ", ".join(to_repr(v, seen) for v in value) + "]"
    if isinstance(value, Module):
        return f"<modül {value.name}>"
    if isinstance(value, StructInstance):
        seen = _seen or set()
        if id(value) in seen:
            return f"{value.name}(...)"
        seen = seen | {id(value)}
        inner = ", ".join(f"{k}: {to_repr(v, seen)}"
                          for k, v in value.values.items())
        return f"{value.name}({inner})"
    if isinstance(value, dict):
        seen = _seen or set()
        if id(value) in seen:
            return "#[...]"
        seen = seen | {id(value)}
        inner = ", ".join(f"{to_repr(k, seen)}: {to_repr(v, seen)}"
                          for k, v in value.items())
        return "#[" + inner + "]"
    return repr(value)


def to_repr(value, _seen: set | None = None) -> str:
    """Dizi içi gösterim — string'ler tırnaklıdır."""
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return to_display(value, _seen)


# ---------------------------------------------------------------------------
# Kaçış dizisi çözümü
# ---------------------------------------------------------------------------

ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "0": "\0",
    "\\": "\\", '"': '"', "'": "'",
}


def decode_string(raw: str, node: Node | None = None) -> str:
    """Lexer'ın tırnaklarıyla verdiği ham sabiti gerçek değere çevirir."""
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        raw = raw[1:-1]

    out    = []
    i      = 0
    length = len(raw)
    while i < length:
        ch = raw[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue

        i += 1
        if i >= length:
            raise RadianError("Dize sonunda yarım kaçış dizisi", node)
        esc = raw[i]
        if esc in ESCAPES:
            out.append(ESCAPES[esc])
            i += 1
        elif esc == "x":                              # \xNN
            hexpart = raw[i + 1:i + 3]
            if len(hexpart) < 2 or any(c not in "0123456789abcdefABCDEF"
                                       for c in hexpart):
                raise RadianError("Geçersiz \\x kaçış dizisi", node)
            out.append(chr(int(hexpart, 16)))
            i += 3
        else:
            raise RadianError(f"Bilinmeyen kaçış dizisi: '\\{esc}'", node)
    return "".join(out)


def decode_number(raw: str, node: Node | None = None):
    """Sayısal sabiti int ya da float'a çevirir."""
    try:
        if raw.startswith(("0x", "0X")):
            return int(raw, 16)
        if raw.startswith(("0b", "0B")):
            return int(raw, 2)
        if raw.startswith(("0o", "0O")):
            return int(raw, 8)
        if "." in raw or "e" in raw or "E" in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        raise RadianError(f"Geçersiz sayısal sabit: '{raw}'", node) from None


# ---------------------------------------------------------------------------
# Aritmetik yardımcıları — tamsayı bölmesi C semantiği (sıfıra doğru kırpma)
# ---------------------------------------------------------------------------

def int_div(a: int, b: int) -> int:
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def int_mod(a: int, b: int) -> int:
    return a - int_div(a, b) * b


# ---------------------------------------------------------------------------
# Yorumlayıcı
# ---------------------------------------------------------------------------

# Radian çağrı yığını sınırı. Python'un kendi limiti (varsayılan 1000) bir
# Radian çağrısı başına birkaç Python karesi tükettiği için ~160 seviyesinde
# devreye giriyordu; kendi sayacımızla hem sınırı yükseltiyor hem de düzgün
# bir RadianError üretiyoruz.
MAX_CALL_DEPTH   = 1000
PYTHON_REC_LIMIT = 20000


class Interpreter:

    def __init__(self, out=None, max_depth: int = MAX_CALL_DEPTH,
                 base_dir: str | None = None,
                 symbols_file: str = "symbols.txt"):
        self.out       = out if out is not None else sys.stdout
        self.globals   = Environment()
        self.max_depth = max_depth
        self.depth     = 0
        self.base_dir  = base_dir or os.getcwd()   # göreli import kökü
        self.symbols_file = symbols_file           # import edilen dosyalar için
        self.modules: dict[str, Module] = {}       # önbellek: gerçek yol → modül
        self._loading: set[str] = set()            # döngüsel import denetimi
        if sys.getrecursionlimit() < PYTHON_REC_LIMIT:
            sys.setrecursionlimit(PYTHON_REC_LIMIT)
        self._install_builtins()

    # ------------------------------------------------------------------
    # Genel giriş noktaları
    # ------------------------------------------------------------------

    def run(self, program: Node):
        """PROGRAM düğümünü çalıştırır.

        Tüm üst düzey statement'lar sırayla yürütülür. Sonrasında argümansız
        bir `main` fonksiyonu tanımlıysa otomatik çağrılır ve dönüş değeri
        programın değeri olur; yoksa son statement'ın değeri döner.
        """
        result = UNIT
        try:
            for child in program.children:
                result = self.eval(child, self.globals)
        except ReturnSignal:
            raise RadianError("Fonksiyon dışında 'return'") from None
        except (BreakSignal, ContinueSignal):
            raise RadianError("Döngü dışında 'break' / 'continue'") from None
        except RecursionError:
            # Çağrı sayacına takılmayan derin özyineleme (örn. iç içe ifade)
            raise RadianError("Yorumlayıcı yığını taştı") from None

        main = self.globals.values.get("main")
        if isinstance(main, Function) and main.arity == 0:
            result = self.call(main, [], None)
        return result

    def run_source(self, source: str, symbols_file: str | None = None):
        if symbols_file is not None:
            self.symbols_file = symbols_file       # import'lar da bunu kullanır
        return self.run(parse_source(source, symbols_file=self.symbols_file))

    def run_file(self, path: str, symbols_file: str | None = None):
        """Bir dosyayı çalıştırır; göreli import'lar dosyanın dizinine göredir."""
        path = os.path.abspath(path)
        self.base_dir = os.path.dirname(path)
        with open(path, encoding="utf-8") as fh:
            return self.run_source(fh.read(), symbols_file=symbols_file)

    # ------------------------------------------------------------------
    # Dağıtıcı
    # ------------------------------------------------------------------

    def eval(self, node: Node, env: Environment):
        method = self._DISPATCH.get(node.type)
        if method is None:
            raise RadianError(
                f"Yorumlanamayan düğüm tipi: {node.type.name}", node)
        return method(self, node, env)

    # ------------------------------------------------------------------
    # Yapısal düğümler
    # ------------------------------------------------------------------

    def _eval_program(self, node: Node, env: Environment):
        return self.run(node)

    def _eval_statement(self, node: Node, env: Environment):
        return self.eval(node.children[0], env) if node.children else UNIT

    def _eval_block(self, node: Node, env: Environment):
        """Blok yeni kapsam açar; değeri son statement'ın değeridir."""
        scope  = Environment(env)
        result = UNIT
        for stmt in node.children:
            result = self.eval(stmt, scope)
        return result

    def _eval_funcdef(self, node: Node, env: Environment):
        name = node.value.value

        signature   = node.children[0] if node.children[0].type == NodeType.FUNC_TYPE else None
        body        = node.children[-1]
        params      = []
        return_type = None

        if signature is not None:
            *param_nodes, ret_node = signature.children
            for p in param_nodes:
                if p.value is None:
                    raise RadianError(
                        f"'{name}' tanımında parametre adı zorunlu", p)
                ptype = p.children[0] if p.children else None
                params.append((p.value.value, ptype))
            return_type = ret_node.children[0] if ret_node.children else None

        func = Function(name, params, body, env, return_type)
        env.define(name, func)
        return func

    def _eval_struct_def(self, node: Node, env: Environment):
        """struct Nokta (x:i32, y:i32);  →  çevrede Nokta adlı kurucu tanımlar."""
        name   = node.value.value
        fields = []
        seen   = set()
        for param in node.children:
            if param.value is None:
                raise RadianError(
                    f"'{name}' yapısında alan adı zorunlu", param)
            fname = param.value.value
            if fname in seen:
                raise RadianError(
                    f"'{name}' yapısında yinelenen alan: '{fname}'", param)
            seen.add(fname)
            ftype = param.children[0] if param.children else None
            fields.append((fname, ftype))

        struct = StructType(name, fields)
        env.define(name, struct)
        return struct

    # ------------------------------------------------------------------
    # Atama ve tip bağlama
    # ------------------------------------------------------------------

    def _eval_assign(self, node: Node, env: Environment):
        target, value_node = node.children
        op = node.value.value

        if op == "=":
            value = self.eval(value_node, env)
        else:
            # Bileşik atama: a op= b  →  a = a op b
            current = self.eval(target, env)
            value   = self._binary_values(op[:-1], current,
                                          self.eval(value_node, env), node)

        return self._store(target, value, env, node)

    def _store(self, target: Node, value, env: Environment, node: Node):
        """Atamanın sol tarafını çözer ve değeri yazar; lvalue'yu döndürür."""
        if target.type == NodeType.IDENTIFIER:
            env.assign(target.value.value, value, target)
            return value

        if target.type == NodeType.TYPEBIND:
            # x : i32 = 42  →  önce tip bağla, sonra değeri yaz
            inner, type_node = target.children
            if inner.type != NodeType.IDENTIFIER:
                raise RadianError("Tip yalnızca değişkene bağlanabilir", inner)
            name = inner.value.value
            check_type(value, type_node, name, node, env)
            scope = env.lookup_scope(name) or env
            scope.define(name, value, type_node)
            return value

        if target.type == NodeType.INDEX:
            obj_node, index_node = target.children
            obj   = self.eval(obj_node, env)
            index = self.eval(index_node, env)
            if isinstance(obj, dict):
                obj[map_key(index, target)] = value     # yoksa ekler
                return value
            if not isinstance(obj, list):
                raise RadianError(
                    f"İndeksle atama yalnızca dizi ve haritalarda geçerli, "
                    f"{type_name(obj)} bulundu", target)
            self._check_index(obj, index, target)
            obj[index] = value
            return value

        if target.type == NodeType.MEMBER:
            obj   = self.eval(target.children[0], env)
            fname = target.value.value
            if not isinstance(obj, StructInstance):
                raise RadianError(
                    f"{type_name(obj)} değerine üye ataması yapılamaz", target)
            if fname not in obj.values:
                raise RadianError(
                    f"'{obj.name}' yapısının '{fname}' alanı yok", target)
            ftype = dict(obj.struct_type.fields).get(fname)
            check_type(value, ftype, f"{obj.name}.{fname}", target, self.globals)
            obj.values[fname] = value
            return value

        raise RadianError("Geçersiz atama hedefi", target)

    def _eval_typebind(self, node: Node, env: Environment):
        """`x : i32;` — değişkeni tipiyle bildirir, mevcut değeri doğrular."""
        target, type_node = node.children

        if target.type != NodeType.IDENTIFIER:
            # (a + b) : i32 gibi kullanım → yalnızca doğrulama
            value = self.eval(target, env)
            check_type(value, type_node, "", node, env)
            return value

        name  = target.value.value
        scope = env.lookup_scope(name)
        if scope is None:
            value = zero_value(type_node)
            env.define(name, value, type_node)
            return value

        value = scope.values[name]
        check_type(value, type_node, name, node, env)
        scope.types[name] = type_node
        return value

    # ------------------------------------------------------------------
    # Operatörler
    # ------------------------------------------------------------------

    def _eval_binary(self, node: Node, env: Environment):
        left_node, op_node, right_node = node.children
        op = op_node.value.value

        # Kısa devre: sağ taraf gerekmeden karar verilebilir
        if op in ("&&", "||"):
            left = self.eval(left_node, env)
            self._require_bool(left, op, node)
            if op == "&&" and not left:
                return False
            if op == "||" and left:
                return True
            right = self.eval(right_node, env)
            self._require_bool(right, op, node)
            return right

        return self._binary_values(op,
                                   self.eval(left_node, env),
                                   self.eval(right_node, env), node)

    def _binary_values(self, op: str, left, right, node: Node):
        if op == "==":
            return self._equals(left, right)
        if op == "!=":
            return not self._equals(left, right)

        # --- string / dizi birleştirme ---
        if op == "+" and isinstance(left, str) and isinstance(right, str):
            return left + right
        if op == "+" and isinstance(left, list) and isinstance(right, list):
            return left + right
        if op == "*" and isinstance(left, str) and _is_int(right):
            return left * max(right, 0)
        if op == "*" and isinstance(left, list) and _is_int(right):
            return left * max(right, 0)

        # --- karşılaştırma: sayılar ve string'ler ---
        if op in ("<", ">", "<=", ">="):
            if isinstance(left, str) and isinstance(right, str):
                pass
            elif _is_number(left) and _is_number(right):
                pass
            else:
                raise RadianError(
                    f"'{op}' operatörü {type_name(left)} ve {type_name(right)} "
                    f"için tanımlı değil", node)
            return {"<":  left <  right,
                    ">":  left >  right,
                    "<=": left <= right,
                    ">=": left >= right}[op]

        # --- bit operatörleri: yalnızca tamsayı ---
        if op in ("&", "|", "^", "<<", ">>"):
            if not (_is_int(left) and _is_int(right)):
                raise RadianError(
                    f"'{op}' operatörü tamsayı bekler, {type_name(left)} ve "
                    f"{type_name(right)} bulundu", node)
            if op in ("<<", ">>") and right < 0:
                raise RadianError("Negatif kaydırma miktarı", node)
            return {"&":  left &  right,
                    "|":  left |  right,
                    "^":  left ^  right,
                    "<<": left << right,
                    ">>": left >> right}[op]

        # --- aritmetik ---
        if op in ("+", "-", "*", "/", "%", "**"):
            if not (_is_number(left) and _is_number(right)):
                raise RadianError(
                    f"'{op}' operatörü {type_name(left)} ve {type_name(right)} "
                    f"için tanımlı değil", node)
            if op == "+":
                return left + right
            if op == "-":
                return left - right
            if op == "*":
                return left * right
            if op == "**":
                return left ** right
            if right == 0:
                raise RadianError("Sıfıra bölme", node)
            both_int = _is_int(left) and _is_int(right)
            if op == "/":
                return int_div(left, right) if both_int else left / right
            return int_mod(left, right) if both_int else left % right

        raise RadianError(f"Bilinmeyen operatör: '{op}'", node)

    def _eval_pre_op(self, node: Node, env: Environment):
        """++x / --x — önce güncelle, *yeni* değeri döndür."""
        _, new = self._step(node, env)
        return new

    def _eval_post_op(self, node: Node, env: Environment):
        """x++ / x-- — önce güncelle, *eski* değeri döndür."""
        old, _ = self._step(node, env)
        return old

    def _step(self, node: Node, env: Environment):
        """Hedefi 1 artırır/azaltır; (eski, yeni) döndürür.

        Not: `xs[f()]++` biçiminde indeks ifadesi iki kez değerlendirilir
        (bir kez okuma, bir kez yazma için) — yan etkili indeks kullanma.
        """
        target = node.children[0]
        delta  = 1 if node.value.value == "++" else -1

        old = self.eval(target, env)
        if not _is_number(old):
            raise RadianError(
                f"'{node.value.value}' sayı bekler, {type_name(old)} bulundu",
                node)

        new = old + delta
        self._store(target, new, env, node)
        return old, new

    def _eval_unary(self, node: Node, env: Environment):
        op_node, operand_node = node.children
        op    = op_node.value.value
        value = self.eval(operand_node, env)

        if op == "-":
            if not _is_number(value):
                raise RadianError(
                    f"'-' operatörü sayı bekler, {type_name(value)} bulundu", node)
            return -value
        if op == "+":
            if not _is_number(value):
                raise RadianError(
                    f"'+' operatörü sayı bekler, {type_name(value)} bulundu", node)
            return value
        if op == "!":
            self._require_bool(value, "!", node)
            return not value
        if op == "~":
            if not _is_int(value):
                raise RadianError(
                    f"'~' operatörü tamsayı bekler, {type_name(value)} bulundu",
                    node)
            return ~value

        raise RadianError(f"Bilinmeyen tekli operatör: '{op}'", node)

    @staticmethod
    def _equals(left, right) -> bool:
        if isinstance(left, StructInstance) or isinstance(right, StructInstance):
            if not (isinstance(left, StructInstance)
                    and isinstance(right, StructInstance)):
                return False
            if left.struct_type is not right.struct_type:
                return False
            return all(Interpreter._equals(left.values[k], right.values[k])
                       for k in left.values)
        if isinstance(left, bool) != isinstance(right, bool):
            return False
        if left is UNIT or right is UNIT:
            return left is right
        try:
            return bool(left == right)
        except TypeError:
            return False

    @staticmethod
    def _require_bool(value, op: str, node: Node) -> None:
        if not isinstance(value, bool):
            raise RadianError(
                f"'{op}' operatörü bool bekler, {type_name(value)} bulundu", node)

    # ------------------------------------------------------------------
    # Değer üreten temel düğümler
    # ------------------------------------------------------------------

    def _eval_literal(self, node: Node, env: Environment):
        tok = node.value
        if tok.type.name == "LITERAL_NUM":
            return decode_number(tok.value, node)
        if tok.type.name in ("LITERAL_STR", "LITERAL_CHAR"):
            text = decode_string(tok.value, node)
            if tok.type.name == "LITERAL_CHAR" and len(text) != 1:
                raise RadianError(
                    f"char sabiti tek karakter olmalı: {tok.value}", node)
            return text
        if tok.value == "true":
            return True
        if tok.value == "false":
            return False

        # Primitive tip adı ifade konumunda: aynı adlı bir değer (örn. `bool`
        # dönüşüm fonksiyonu) tanımlıysa onu kullan, değilse hata ver.
        scope = env.lookup_scope(tok.value)
        if scope is not None:
            return scope.values[tok.value]
        raise RadianError(f"'{tok.value}' bir değer değil, bir tip adı", node)

    def _eval_identifier(self, node: Node, env: Environment):
        return env.get(node.value.value, node)

    def _eval_array(self, node: Node, env: Environment):
        return [self.eval(child, env) for child in node.children]

    def _eval_map(self, node: Node, env: Environment):
        result: dict = {}
        children = node.children
        for i in range(0, len(children), 2):
            key   = map_key(self.eval(children[i], env), node)
            value = self.eval(children[i + 1], env)
            result[key] = value
        return result

    def _eval_index(self, node: Node, env: Environment):
        obj_node, index_node = node.children
        obj   = self.eval(obj_node, env)
        index = self.eval(index_node, env)

        if isinstance(obj, dict):
            key = map_key(index, node)
            if key not in obj:
                raise RadianError(
                    f"Haritada anahtar yok: {to_repr(key)}", node)
            return obj[key]

        if isinstance(obj, (list, str)):
            self._check_index(obj, index, node)
            return obj[index]

        raise RadianError(
            f"{type_name(obj)} indekslenemez", node)

    @staticmethod
    def _check_index(seq, index, node: Node) -> None:
        if not _is_int(index):
            raise RadianError(
                f"İndeks tamsayı olmalı, {type_name(index)} bulundu", node)
        if index < 0 or index >= len(seq):
            raise RadianError(
                f"İndeks sınır dışı: {index} (uzunluk {len(seq)})", node)

    def _eval_member(self, node: Node, env: Environment):
        obj  = self.eval(node.children[0], env)
        name = node.value.value

        if isinstance(obj, Module):
            if name not in obj.values:
                raise RadianError(
                    f"'{obj.name}' modülünde '{name}' tanımı yok", node)
            return obj.values[name]

        if isinstance(obj, StructInstance):
            if name not in obj.values:
                raise RadianError(
                    f"'{obj.name}' yapısının '{name}' alanı yok "
                    f"(alanlar: {', '.join(obj.struct_type.field_names())})",
                    node)
            return obj.values[name]

        table = _method_table(obj)
        if name not in table:
            raise RadianError(
                f"{type_name(obj)} değerinin '{name}' üyesi yok", node)
        return BoundMethod(obj, table[name])

    # ------------------------------------------------------------------
    # Çağrı
    # ------------------------------------------------------------------

    def _eval_call(self, node: Node, env: Environment):
        callee_node, *arg_nodes = node.children
        callee = self.eval(callee_node, env)
        args   = [self.eval(a, env) for a in arg_nodes]
        return self.call(callee, args, node)

    def call(self, callee, args: list, node: Node | None):
        if isinstance(callee, BoundMethod):
            self._check_arity(callee.builtin, len(args), node)
            return callee.builtin.fn(self, callee.receiver, args, node)

        if isinstance(callee, Builtin):
            self._check_arity(callee, len(args), node)
            return callee.fn(self, args, node)

        if isinstance(callee, StructType):
            if len(args) != callee.arity:
                raise RadianError(
                    f"'{callee.name}' {callee.arity} alan bekliyor, "
                    f"{len(args)} verildi", node)
            values = {}
            for (fname, ftype), value in zip(callee.fields, args):
                check_type(value, ftype, f"{callee.name}.{fname}", node,
                           self.globals)
                values[fname] = value
            return StructInstance(callee, values)

        if isinstance(callee, Function):
            if len(args) != callee.arity:
                raise RadianError(
                    f"'{callee.name}' {callee.arity} argüman bekliyor, "
                    f"{len(args)} verildi", node)

            if self.depth >= self.max_depth:
                raise RadianError(
                    f"Özyineleme derinliği aşıldı ({self.max_depth}): "
                    f"'{callee.name}'", node)

            scope = Environment(callee.closure)
            for (pname, ptype), value in zip(callee.params, args):
                check_type(value, ptype, pname, node, callee.closure)
                scope.define(pname, value, ptype)

            self.depth += 1
            try:
                result = self._eval_block_in(callee.body, scope)
            except ReturnSignal as signal:
                result = signal.value
            except RadianError as err:
                # Yığın çerçevesini ekleyip aynı hatayı yükselt
                err.frames.append((callee.name, node.value.line
                                   if node is not None and node.value else 0))
                raise
            except (BreakSignal, ContinueSignal):
                # Döngü sinyali fonksiyon sınırını aşamaz.
                raise RadianError(
                    f"'{callee.name}' içinde döngü dışında break/continue",
                    node) from None
            finally:
                self.depth -= 1

            if callee.return_type is not None:
                check_type(result, callee.return_type,
                           f"{callee.name} dönüş değeri", node, callee.closure)
            return result

        raise RadianError(f"{type_name(callee)} çağrılabilir değil", node)

    def _eval_block_in(self, block: Node, scope: Environment):
        """Bloku *verilen* kapsamda çalıştırır (fonksiyon gövdesi için)."""
        result = UNIT
        for stmt in block.children:
            result = self.eval(stmt, scope)
        return result

    @staticmethod
    def _check_arity(builtin: Builtin, count: int, node: Node | None) -> None:
        arity = builtin.arity
        if arity is None:
            return
        if isinstance(arity, tuple):
            low, high = arity
            if count < low or (high is not None and count > high):
                expected = f"{low}..{high if high is not None else '*'}"
                raise RadianError(
                    f"'{builtin.name}' {expected} argüman bekliyor, "
                    f"{count} verildi", node)
            return
        if count != arity:
            raise RadianError(
                f"'{builtin.name}' {arity} argüman bekliyor, {count} verildi",
                node)

    # ------------------------------------------------------------------
    # Akış denetimi
    # ------------------------------------------------------------------

    def _eval_import(self, node: Node, env: Environment):
        """import "yol.rad"  →  dosyayı bir kez çalıştırır, modül değeri döner."""
        raw = self.eval(node.children[0], env)
        if not isinstance(raw, str):
            raise RadianError(
                f"import bir dosya yolu (str) bekler, {type_name(raw)} bulundu",
                node)

        path = raw if os.path.isabs(raw) else os.path.join(self.base_dir, raw)
        path = os.path.realpath(path)

        if path in self.modules:
            return self.modules[path]                # önbellek
        if path in self._loading:
            raise RadianError(f"Döngüsel import: {raw}", node)
        if not os.path.exists(path):
            raise RadianError(f"Modül bulunamadı: {raw}", node)

        try:
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
        except OSError as err:
            raise RadianError(f"Modül okunamadı: {raw} ({err})", node) from None

        try:
            program = parse_source(source, symbols_file=self.symbols_file)
        except ParseError as err:
            raise RadianError(f"'{raw}' içinde sözdizimi hatası: {err}",
                              node) from None

        # Modül kendi kapsamında çalışır; yerleşiklere globals üzerinden erişir.
        scope     = Environment(self.globals)
        prev_dir  = self.base_dir
        self._loading.add(path)
        self.base_dir = os.path.dirname(path)
        try:
            for child in program.children:
                self.eval(child, scope)
        finally:
            self.base_dir = prev_dir
            self._loading.discard(path)

        module = Module(path, scope.values)
        self.modules[path] = module
        return module

    def _eval_if(self, node: Node, env: Environment):
        cond = self.eval(node.children[0], env)
        self._require_bool(cond, "if", node)

        if cond:
            return self.eval(node.children[1], env)
        if len(node.children) > 2:
            return self.eval(node.children[2], env)
        return UNIT

    def _eval_while(self, node: Node, env: Environment):
        cond_node, body = node.children
        result = UNIT
        while True:
            cond = self.eval(cond_node, env)
            self._require_bool(cond, "while", node)
            if not cond:
                break
            try:
                result = self.eval(body, env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue
        return result

    def _eval_for(self, node: Node, env: Environment):
        iterable = self.eval(node.children[0], env)
        body     = node.children[1]
        var_name = node.value.value

        if isinstance(iterable, str):
            items = list(iterable)
        elif isinstance(iterable, list):
            items = list(iterable)
        elif isinstance(iterable, dict):
            items = list(iterable.keys())            # harita → anahtarlar
        else:
            raise RadianError(
                f"{type_name(iterable)} üzerinde döngü kurulamaz", node)

        result = UNIT
        for item in items:
            scope = Environment(env)
            scope.define(var_name, item)
            try:
                result = self._eval_block_in(body, Environment(scope))
            except BreakSignal:
                break
            except ContinueSignal:
                continue
        return result

    def _eval_return(self, node: Node, env: Environment):
        value = self.eval(node.children[0], env) if node.children else UNIT
        raise ReturnSignal(value)

    def _eval_break(self, node: Node, env: Environment):
        raise BreakSignal()

    def _eval_continue(self, node: Node, env: Environment):
        raise ContinueSignal()

    # ------------------------------------------------------------------
    # Yerleşikler
    # ------------------------------------------------------------------

    def _install_builtins(self) -> None:
        for name, fn, arity in _BUILTIN_SPECS:
            self.globals.define(name, Builtin(name, fn, arity))

    # Dağıtım tablosu — sınıf gövdesinin sonunda tanımlanır.
    _DISPATCH = {}


Interpreter._DISPATCH = {
    NodeType.PROGRAM:    Interpreter._eval_program,
    NodeType.STATEMENT:  Interpreter._eval_statement,
    NodeType.BLOCK:      Interpreter._eval_block,
    NodeType.FUNC_DEF:   Interpreter._eval_funcdef,
    NodeType.ASSIGN:     Interpreter._eval_assign,
    NodeType.TYPEBIND:   Interpreter._eval_typebind,
    NodeType.BINARY_OP:  Interpreter._eval_binary,
    NodeType.UNARY_OP:   Interpreter._eval_unary,
    NodeType.PRE_OP:     Interpreter._eval_pre_op,
    NodeType.POST_OP:    Interpreter._eval_post_op,
    NodeType.LITERAL:    Interpreter._eval_literal,
    NodeType.IDENTIFIER: Interpreter._eval_identifier,
    NodeType.ARRAY:      Interpreter._eval_array,
    NodeType.MAP:        Interpreter._eval_map,
    NodeType.STRUCT_DEF: Interpreter._eval_struct_def,
    NodeType.IMPORT:     Interpreter._eval_import,
    NodeType.INDEX:      Interpreter._eval_index,
    NodeType.MEMBER:     Interpreter._eval_member,
    NodeType.CALL:       Interpreter._eval_call,
    NodeType.IF:         Interpreter._eval_if,
    NodeType.WHILE:      Interpreter._eval_while,
    NodeType.FOR:        Interpreter._eval_for,
    NodeType.RETURN:     Interpreter._eval_return,
    NodeType.BREAK:      Interpreter._eval_break,
    NodeType.CONTINUE:   Interpreter._eval_continue,
}


# ---------------------------------------------------------------------------
# Tip yardımcıları (bool, int'in alt tipi olduğu için ayrı kontrol gerekir)
# ---------------------------------------------------------------------------

def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# Genel yerleşik fonksiyonlar
# ---------------------------------------------------------------------------

def _bi_print(interp: Interpreter, args, node):
    interp.out.write(" ".join(to_display(a) for a in args) + "\n")
    return UNIT


def _bi_write(interp: Interpreter, args, node):
    interp.out.write("".join(to_display(a) for a in args))
    return UNIT


def _bi_len(interp, args, node):
    value = args[0]
    if isinstance(value, (str, list, dict)):
        return len(value)
    raise RadianError(f"len() {type_name(value)} için tanımlı değil", node)

def _bi_str(interp, args, node):
    return to_display(args[0])


def _bi_int(interp, args, node):
    value = args[0]
    if isinstance(value, bool):
        return 1 if value else 0
    if _is_int(value):
        return value
    if isinstance(value, float):
        return int(value)                     # sıfıra doğru kırpar
    if isinstance(value, str):
        try:
            return int(value.strip(), 0)
        except ValueError:
            raise RadianError(f"int() dönüştüremedi: '{value}'", node) from None
    raise RadianError(f"int() {type_name(value)} için tanımlı değil", node)


def _bi_float(interp, args, node):
    value = args[0]
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if _is_number(value):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            raise RadianError(f"float() dönüştüremedi: '{value}'", node) from None
    raise RadianError(f"float() {type_name(value)} için tanımlı değil", node)


def _bi_bool(interp, args, node):
    value = args[0]
    if isinstance(value, bool):
        return value
    if _is_number(value):
        return value != 0
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return value is not UNIT


def _bi_type(interp, args, node):
    return type_name(args[0])


def _bi_map(interp, args, node):
    """map()  →  boş harita;  map(ikililer)  →  [[k, v], …] listesinden."""
    if not args:
        return {}
    pairs = args[0]
    if not isinstance(pairs, list):
        raise RadianError(
            f"map() [anahtar, değer] ikilileri bekler, "
            f"{type_name(pairs)} bulundu", node)
    result: dict = {}
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2:
            raise RadianError(
                "map() her girdide tam olarak [anahtar, değer] bekler", node)
        result[map_key(pair[0], node)] = pair[1]
    return result


def _bi_range(interp, args, node):
    for a in args:
        if not _is_int(a):
            raise RadianError(
                f"range() tamsayı bekler, {type_name(a)} bulundu", node)
    if len(args) == 1:
        start, stop, step = 0, args[0], 1
    elif len(args) == 2:
        start, stop, step = args[0], args[1], 1
    else:
        start, stop, step = args
    if step == 0:
        raise RadianError("range() adımı sıfır olamaz", node)
    return list(range(start, stop, step))


def _bi_abs(interp, args, node):
    value = args[0]
    if not _is_number(value):
        raise RadianError(f"abs() sayı bekler, {type_name(value)} bulundu", node)
    return abs(value)


def _bi_min(interp, args, node):
    return _fold_extreme(args, node, "min", min)


def _bi_max(interp, args, node):
    return _fold_extreme(args, node, "max", max)


def _fold_extreme(args, node, name, fn):
    values = args[0] if len(args) == 1 and isinstance(args[0], list) else args
    if not values:
        raise RadianError(f"{name}() boş dizi ile çağrıldı", node)
    for v in values:
        if not _is_number(v):
            raise RadianError(
                f"{name}() sayı bekler, {type_name(v)} bulundu", node)
    return fn(values)


def _bi_sum(interp, args, node):
    values = args[0] if len(args) == 1 and isinstance(args[0], list) else args
    total = 0
    for v in values:
        if not _is_number(v):
            raise RadianError(
                f"sum() sayı bekler, {type_name(v)} bulundu", node)
        total += v
    return total


def _bi_assert(interp, args, node):
    cond = args[0]
    if not isinstance(cond, bool):
        raise RadianError(
            f"assert() bool bekler, {type_name(cond)} bulundu", node)
    if not cond:
        message = to_display(args[1]) if len(args) > 1 else "assert başarısız"
        raise RadianError(message, node)
    return UNIT


_BUILTIN_SPECS = [
    ("print",  _bi_print,  None),
    ("write",  _bi_write,  None),
    ("len",    _bi_len,    1),
    ("str",    _bi_str,    1),
    ("int",    _bi_int,    1),
    ("float",  _bi_float,  1),
    ("bool",   _bi_bool,   1),
    ("type",   _bi_type,   1),
    ("map",    _bi_map,    (0, 1)),
    ("range",  _bi_range,  (1, 3)),
    ("abs",    _bi_abs,    1),
    ("min",    _bi_min,    (1, None)),
    ("max",    _bi_max,    (1, None)),
    ("sum",    _bi_sum,    (1, None)),
    ("assert", _bi_assert, (1, 2)),
]


# ---------------------------------------------------------------------------
# Metotlar — a.b(…) biçiminde çağrılan yerleşikler
# ---------------------------------------------------------------------------

def _method(name, arity):
    """Metot tablosu girdisi üreten dekoratör."""
    def wrap(fn):
        return name, Builtin(name, fn, arity)
    return wrap


# --- dizi metotları ---------------------------------------------------------

def _m_array_len(interp, xs, args, node):
    return len(xs)


def _m_array_push(interp, xs, args, node):
    xs.extend(args)
    return xs


def _m_array_pop(interp, xs, args, node):
    if not xs:
        raise RadianError("pop(): dizi boş", node)
    return xs.pop()


def _m_array_insert(interp, xs, args, node):
    index, value = args
    if not _is_int(index):
        raise RadianError("insert(): indeks tamsayı olmalı", node)
    if index < 0 or index > len(xs):
        raise RadianError(f"insert(): indeks sınır dışı: {index}", node)
    xs.insert(index, value)
    return xs


def _m_array_remove(interp, xs, args, node):
    index = args[0]
    Interpreter._check_index(xs, index, node)
    return xs.pop(index)


def _m_array_contains(interp, xs, args, node):
    return any(Interpreter._equals(x, args[0]) for x in xs)


def _m_array_index_of(interp, xs, args, node):
    for i, x in enumerate(xs):
        if Interpreter._equals(x, args[0]):
            return i
    return -1


def _m_array_slice(interp, xs, args, node):
    start = args[0]
    stop  = args[1] if len(args) > 1 else len(xs)
    if not (_is_int(start) and _is_int(stop)):
        raise RadianError("slice(): sınırlar tamsayı olmalı", node)
    return xs[max(start, 0):max(stop, 0)]


def _m_array_reverse(interp, xs, args, node):
    return list(reversed(xs))


def _m_array_join(interp, xs, args, node):
    sep = args[0] if args else ""
    if not isinstance(sep, str):
        raise RadianError("join(): ayraç str olmalı", node)
    return sep.join(to_display(x) for x in xs)


def _m_array_map(interp, xs, args, node):
    fn = args[0]
    return [interp.call(fn, [x], node) for x in xs]


def _m_array_filter(interp, xs, args, node):
    fn  = args[0]
    out = []
    for x in xs:
        keep = interp.call(fn, [x], node)
        if not isinstance(keep, bool):
            raise RadianError(
                f"filter(): fonksiyon bool döndürmeli, {type_name(keep)} döndü",
                node)
        if keep:
            out.append(x)
    return out


def _m_array_reduce(interp, xs, args, node):
    fn = args[0]
    if len(args) > 1:
        acc, rest = args[1], xs
    elif xs:
        acc, rest = xs[0], xs[1:]
    else:
        raise RadianError("reduce(): boş dizi ve başlangıç değeri yok", node)
    for x in rest:
        acc = interp.call(fn, [acc, x], node)
    return acc


def _m_array_sort(interp, xs, args, node):
    if all(_is_number(x) for x in xs) or all(isinstance(x, str) for x in xs):
        return sorted(xs)
    raise RadianError("sort(): dizi tümüyle sayı ya da tümüyle str olmalı", node)


ARRAY_METHODS = dict([
    _method("len",      0)(_m_array_len),
    _method("push",     (1, None))(_m_array_push),
    _method("pop",      0)(_m_array_pop),
    _method("insert",   2)(_m_array_insert),
    _method("remove",   1)(_m_array_remove),
    _method("contains", 1)(_m_array_contains),
    _method("index_of", 1)(_m_array_index_of),
    _method("slice",    (1, 2))(_m_array_slice),
    _method("reverse",  0)(_m_array_reverse),
    _method("join",     (0, 1))(_m_array_join),
    _method("map",      1)(_m_array_map),
    _method("filter",   1)(_m_array_filter),
    _method("reduce",   (1, 2))(_m_array_reduce),
    _method("sort",     0)(_m_array_sort),
])


# --- string metotları -------------------------------------------------------

def _m_str_len(interp, s, args, node):
    return len(s)


def _m_str_upper(interp, s, args, node):
    return s.upper()


def _m_str_lower(interp, s, args, node):
    return s.lower()


def _m_str_trim(interp, s, args, node):
    return s.strip()


def _m_str_split(interp, s, args, node):
    sep = args[0] if args else " "
    if not isinstance(sep, str):
        raise RadianError("split(): ayraç str olmalı", node)
    return s.split(sep) if sep else list(s)


def _m_str_contains(interp, s, args, node):
    return _require_str(args[0], "contains", node) in s


def _m_str_starts_with(interp, s, args, node):
    return s.startswith(_require_str(args[0], "starts_with", node))


def _m_str_ends_with(interp, s, args, node):
    return s.endswith(_require_str(args[0], "ends_with", node))


def _m_str_replace(interp, s, args, node):
    old = _require_str(args[0], "replace", node)
    new = _require_str(args[1], "replace", node)
    return s.replace(old, new)


def _m_str_find(interp, s, args, node):
    return s.find(_require_str(args[0], "find", node))


def _m_str_slice(interp, s, args, node):
    start = args[0]
    stop  = args[1] if len(args) > 1 else len(s)
    if not (_is_int(start) and _is_int(stop)):
        raise RadianError("slice(): sınırlar tamsayı olmalı", node)
    return s[max(start, 0):max(stop, 0)]


def _m_str_chars(interp, s, args, node):
    return list(s)


def _m_str_repeat(interp, s, args, node):
    count = args[0]
    if not _is_int(count):
        raise RadianError("repeat(): sayı tamsayı olmalı", node)
    return s * max(count, 0)


def _require_str(value, name, node) -> str:
    if not isinstance(value, str):
        raise RadianError(
            f"{name}(): str bekleniyordu, {type_name(value)} bulundu", node)
    return value


STRING_METHODS = dict([
    _method("len",         0)(_m_str_len),
    _method("upper",       0)(_m_str_upper),
    _method("lower",       0)(_m_str_lower),
    _method("trim",        0)(_m_str_trim),
    _method("split",       (0, 1))(_m_str_split),
    _method("contains",    1)(_m_str_contains),
    _method("starts_with", 1)(_m_str_starts_with),
    _method("ends_with",   1)(_m_str_ends_with),
    _method("replace",     2)(_m_str_replace),
    _method("find",        1)(_m_str_find),
    _method("slice",       (1, 2))(_m_str_slice),
    _method("chars",       0)(_m_str_chars),
    _method("repeat",      1)(_m_str_repeat),
])


# --- harita metotları -------------------------------------------------------

def _m_map_len(interp, m, args, node):
    return len(m)


def _m_map_has(interp, m, args, node):
    return map_key(args[0], node) in m


def _m_map_get(interp, m, args, node):
    key = map_key(args[0], node)
    if key in m:
        return m[key]
    if len(args) > 1:
        return args[1]
    raise RadianError(f"Haritada anahtar yok: {to_repr(key)}", node)


def _m_map_set(interp, m, args, node):
    m[map_key(args[0], node)] = args[1]
    return m


def _m_map_remove(interp, m, args, node):
    key = map_key(args[0], node)
    if key not in m:
        raise RadianError(f"Haritada anahtar yok: {to_repr(key)}", node)
    return m.pop(key)


def _m_map_keys(interp, m, args, node):
    return list(m.keys())


def _m_map_values(interp, m, args, node):
    return list(m.values())


def _m_map_pairs(interp, m, args, node):
    return [[k, v] for k, v in m.items()]


def _m_map_clear(interp, m, args, node):
    m.clear()
    return m


def _m_map_merge(interp, m, args, node):
    other = args[0]
    if not isinstance(other, dict):
        raise RadianError(
            f"merge(): map bekleniyordu, {type_name(other)} bulundu", node)
    merged = dict(m)
    merged.update(other)
    return merged


MAP_METHODS = dict([
    _method("len",    0)(_m_map_len),
    _method("has",    1)(_m_map_has),
    _method("get",    (1, 2))(_m_map_get),
    _method("set",    2)(_m_map_set),
    _method("remove", 1)(_m_map_remove),
    _method("keys",   0)(_m_map_keys),
    _method("values", 0)(_m_map_values),
    _method("pairs",  0)(_m_map_pairs),
    _method("clear",  0)(_m_map_clear),
    _method("merge",  1)(_m_map_merge),
])


# --- sayı metotları ---------------------------------------------------------

def _m_num_abs(interp, n, args, node):
    return abs(n)


def _m_num_to_str(interp, n, args, node):
    return to_display(n)


def _m_num_min(interp, n, args, node):
    other = args[0]
    if not _is_number(other):
        raise RadianError("min(): sayı bekleniyordu", node)
    return min(n, other)


def _m_num_max(interp, n, args, node):
    other = args[0]
    if not _is_number(other):
        raise RadianError("max(): sayı bekleniyordu", node)
    return max(n, other)


NUMBER_METHODS = dict([
    _method("abs",    0)(_m_num_abs),
    _method("to_str", 0)(_m_num_to_str),
    _method("min",    1)(_m_num_min),
    _method("max",    1)(_m_num_max),
])


def _method_table(value) -> dict:
    if isinstance(value, list):
        return ARRAY_METHODS
    if isinstance(value, dict):
        return MAP_METHODS
    if isinstance(value, str):
        return STRING_METHODS
    if _is_number(value):
        return NUMBER_METHODS
    return {}


# ---------------------------------------------------------------------------
# Hızlı test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    DEMO = """
    // Faktöriyel — özyineleme
    fakt (n:i32) -> i32 {
        if n <= 1 { return 1; }
        n * fakt(n - 1);
    }

    main () -> i32 {
        print("5! =", fakt(5));

        kareler = [];
        for i in range(1, 6) { kareler.push(i * i); }
        print("kareler:", kareler);

        toplam = kareler.reduce(topla);
        print("toplam:", toplam);
        0;
    }

    topla (a:i32, b:i32) -> i32 { a + b; }
    """

    try:
        result = Interpreter().run_source(DEMO)
        print("program değeri:", to_display(result))
    except (ParseError, RadianError) as err:
        print("HATA:", err)
