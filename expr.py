# -*- coding: utf-8 -*-
"""
expr.py — ارزیاب امنِ عبارت برای «{=عبارت}» (وابسته به core؛ بالاتر از core و پایین‌تر از flowkit/ai)

عبارت‌ها در متن‌ها، شرط‌ها و مقدار اکشن‌ها نوشته می‌شوند: {=score * 2 + bonus} و {=points >= 100 ? ... } —
سینتکس شرطی سه‌تایی به سبک پایتون است: {=a if cond else b}.
اصل امنیتی: هیچ eval/exec/import/دسترسی به attribute پایتون وجود ندارد؛ توکنایزر و پارسر و ارزیاب
کاملاً دست‌نویس‌اند و فقط روی مقدارهای ساده (str، int/float، bool، None، list، dict و DateVal) کار می‌کنند.

سقف‌ها: طول عبارت EXPR_MAX_LEN، عمق تودرتو EXPR_MAX_DEPTH، بودجه‌ی گام EXPR_MAX_STEPS.
هر خطا فقط مقدار پیش‌فرض برمی‌گرداند (ربات هرگز نمی‌خوابد) و لاگ می‌شود.

توابع:
  متن:   upper lower len replace split join contains trim slice
  عدد:   round floor ceil min max abs clamp random
  تاریخ: now today date_add date_diff format (تقویم شمسی و میلادی)
  فهرست: len first last sort sum unique
دسترسی: a[0] روی فهرست، o.k و o["k"] روی شیء (کلیدهای شروع‌شونده با __ ممنوع)، op «in».

selftest این ماژول تست طلایی + fuzz دارد (ورودی‌های خراب هرگز exception بیرون نمی‌دهند).
"""

import re, time, math
import random as _rnd
from datetime import datetime, timedelta

from core import _DIG, _int, log, now, to_jalali

EXPR_MAX_LEN = _int("EXPR_MAX_LEN", 500)
EXPR_MAX_DEPTH = _int("EXPR_MAX_DEPTH", 12)
EXPR_MAX_STEPS = _int("EXPR_MAX_STEPS", 200)
EXPR_RE = re.compile(r"\{=([^{}]*)\}")          # یافتن {=...} در متن‌ها (برای fill در مرحله ۱)


class ExprError(ValueError):
    """خطای داخلی ارزیاب؛ بیرون نشت نمی‌کند (safe_eval به پیش‌فرض تبدیلش می‌کند)"""


# ───────────────────────── مقدارها و کمکی‌ها ─────────────────────────
class DateVal:
    """تاریخ/ساعت منطقه‌ی تهران (ناویف)؛ با str به شکل YYYY-MM-DD HH:MM درمی‌آید"""
    __slots__ = ("dt",)

    def __init__(self, dt):
        self.dt = dt

    def __str__(self):
        d = self.dt
        return f"{d.year:04d}-{d.month:02d}-{d.day:02d} {d.hour:02d}:{d.minute:02d}"


def _tehran():
    return datetime.utcnow() + timedelta(hours=3, minutes=30)


def num(v):
    """عددِ امن: bool/int/float همان؛ رشته‌ی عددی (با ارقام فارسی و ٫) تبدیل؛ بقیه خطا"""
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip().translate(_DIG).replace("٫", ".").replace(",", "")
        if s == "":
            raise ExprError("رشته‌ی خالی عدد نیست")
        try:
            f = float(s)
        except ValueError:
            raise ExprError("رشته عدد نیست")
        return int(f) if f == int(f) and "." not in s and "e" not in s.lower() else f
    raise ExprError("این مقدار عدد نیست")


def _plain(v):
    """فقط نوع‌های مجاز؛ بقیه (مثلاً شیء ناشناخته از vars) رد می‌شود"""
    if v is None or isinstance(v, (bool, int, float, str, DateVal)):
        return v
    if isinstance(v, list):
        return [_plain(x) for x in v[:200]]
    if isinstance(v, dict):
        return {str(k)[:40]: _plain(x) for k, x in list(v.items())[:100] if not str(k).startswith("__")}
    raise ExprError("نوع مقدار مجاز نیست")


def _key_ok(k):
    k = str(k)
    return bool(k) and not k.startswith("__") and len(k) <= 60


def _truthy(v):
    if isinstance(v, str):
        return v.strip() != ""
    return bool(v)


# ───────────────────────── توکنایزر ─────────────────────────
_TOK_RE = re.compile(r"""
    \s*(?:
      (?P<num>\d+(?:\.\d+)?)
    | (?P<str>'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")
    | (?P<name>[A-Za-z_\u0600-\u06FF][A-Za-z0-9_\u0600-\u06FF]*)
    | (?P<op>\*\*|==|!=|<=|>=|[+\-*/%<>\(\)\[\],\.])
    )""", re.X)
_STR_ESC = {"n": "\n", "t": "\t", "'": "'", '"': '"', "\\": "\\"}


def _tokenize(s):
    out, i = [], 0
    while i < len(s):
        m = _TOK_RE.match(s, i)
        if not m or m.end() == i:
            if s[i:].strip() == "":
                break
            raise ExprError(f"نویسه‌ی ناشناخته near {s[i:i + 8]!r}")
        i = m.end()
        if m.group("num") is not None:
            t = m.group("num")
            out.append(("num", float(t) if "." in t else int(t)))
        elif m.group("str") is not None:
            raw = m.group("str")[1:-1]
            out.append(("str", re.sub(r"\\(.)", lambda x: _STR_ESC.get(x.group(1), x.group(1)), raw)))
        elif m.group("name") is not None:
            out.append(("name", m.group("name")))
        else:
            out.append(("op", m.group("op")))
    out.append(("end", None))
    return out


# ───────────────────────── پارسر (بازگشتی نزولی) ─────────────────────────
_CMP_OPS = ("==", "!=", "<", "<=", ">", ">=")
_KEYWORDS = ("and", "or", "not", "in", "if", "else", "true", "false", "none", "null")


class _Parser:
    def __init__(self, toks, max_depth):
        self.toks, self.i, self.depth, self.max_depth = toks, 0, 0, max_depth

    def peek(self):
        return self.toks[self.i]

    def take(self, op=None):
        k, v = self.toks[self.i]
        if op is not None and (k != "op" or v != op):
            raise ExprError(f"انتظار {op}")
        self.i += 1
        return (k, v)

    def at_op(self, *ops):
        k, v = self.peek()
        return v if k == "op" and v in ops else None

    def at_name(self, *names):
        k, v = self.peek()
        return v if k == "name" and v in names else None

    def parse(self):
        e = self.ternary()
        if self.peek()[0] != "end":
            raise ExprError("عبارت تمام نشد")
        return e

    def ternary(self):
        self.depth += 1
        if self.depth > self.max_depth:
            raise ExprError("عمق زیاد")
        try:
            then = self.or_()
            if self.at_name("if"):                       # سینتکس پایتون: مقدار if شرط else مقدار
                self.take()
                c = self.or_()
                if not self.at_name("else"):
                    raise ExprError("انتظار else")
                self.take()
                b = self.ternary()
                return ("if", c, then, b)
            return then
        finally:
            self.depth -= 1

    def or_(self):
        l = self.and_()
        while self.at_name("or"):
            self.take()
            l = ("or", l, self.and_())
        return l

    def and_(self):
        l = self.not_()
        while self.at_name("and"):
            self.take()
            l = ("and", l, self.not_())
        return l

    def not_(self):
        if self.at_name("not"):
            self.take()
            return ("not", self.not_())
        return self.cmp()

    def cmp(self):
        l = self.arith()
        op = self.at_op(*_CMP_OPS)
        if op:
            self.take()
            return ("cmp", op, l, self.arith())
        if self.at_name("in"):
            self.take()
            return ("in", l, self.arith())
        if self.at_name("not") and self.toks[self.i + 1] == ("name", "in"):
            self.take(); self.take()
            return ("not", ("in", l, self.arith()))
        return l

    def arith(self):
        l = self.term()
        while True:
            op = self.at_op("+", "-")
            if not op:
                return l
            self.take()
            l = ("bin", op, l, self.term())

    def term(self):
        l = self.unary()
        while True:
            op = self.at_op("*", "/", "%")
            if not op:
                return l
            self.take()
            l = ("bin", op, l, self.unary())

    def unary(self):
        if self.at_op("-"):
            self.take()
            return ("neg", self.unary())
        if self.at_op("+"):
            self.take()
            return self.unary()
        return self.power()

    def power(self):
        b = self.postfix()
        if self.at_op("**"):
            self.take()
            return ("bin", "**", b, self.unary())       # راست‌گرا
        return b

    def postfix(self):
        e = self.atom()
        while True:
            if self.at_op("["):
                self.take()
                ix = self.ternary()
                self.take("]")
                e = ("idx", e, ix)
            elif self.at_op("."):
                self.take()
                k, v = self.take()
                if k != "name" or v in _KEYWORDS:
                    raise ExprError("نام کلید نامعتبر")
                e = ("idx", e, ("lit", v))
            else:
                return e

    def atom(self):
        k, v = self.peek()
        if k == "num" or k == "str":
            self.take()
            return ("lit", v)
        if k == "op" and v == "(":
            self.take()
            e = self.ternary()
            self.take(")")
            return e
        if k == "name":
            if v == "true":
                self.take(); return ("lit", True)
            if v == "false":
                self.take(); return ("lit", False)
            if v in ("none", "null"):
                self.take(); return ("lit", None)
            self.take()
            if self.at_op("("):
                self.take()
                args = []
                if not self.at_op(")"):
                    args.append(self.ternary())
                    while self.at_op(","):
                        self.take()
                        args.append(self.ternary())
                self.take(")")
                return ("call", v, args)
            return ("var", v)
        raise ExprError("مقدار انتظارمی‌رفت")


# ───────────────────────── توابع مجاز ─────────────────────────
def _f_len(x):
    if isinstance(x, (str, list, dict)):
        return len(x)
    raise ExprError("len روی این نوع کار نمی‌کند")


def _f_replace(s, a, b):
    return str(s).replace(str(a), str(b))


def _f_split(s, sep=" "):
    s = str(s)
    sep = str(sep)
    return s.split() if sep.strip() == "" else [p for p in s.split(sep)]


def _f_join(l, sep=" "):
    if not isinstance(l, list):
        raise ExprError("join به فهرست نیاز دارد")
    return str(sep).join("" if v is None else str(v) for v in l)


def _f_contains(h, n):
    h, n = str(h), str(n)
    return n.casefold() in h.casefold()


def _f_trim(s):
    return str(s).strip()


def _f_slice(x, a, b=None):
    if not isinstance(x, (str, list)):
        raise ExprError("slice روی این نوع کار نمی‌کند")
    a, b = int(num(a)), (int(num(b)) if b is not None else None)
    return x[a:b]


def _f_round(x, nd=0):
    return float(round(float(num(x)), int(nd))) if nd else int(round(float(num(x))))


def _expand(args):
    """آرگومان‌های min/max: هر فهرست به آیتم‌هایش باز می‌شود (max(tags, 9) کار می‌کند)"""
    out = []
    for x in args:
        if isinstance(x, list):
            out.extend(x[:500])
        else:
            out.append(x)
    if not out:
        raise ExprError("حداقل یک مقدار لازم است")
    return out


def _f_min(*a):
    return min(num(x) for x in _expand(a))


def _f_max(*a):
    return max(num(x) for x in _expand(a))


def _f_clamp(x, lo, hi):
    return max(num(lo), min(num(hi), num(x)))


def _f_random(a=None, b=None):
    if a is None and b is None:
        return round(_rnd.random(), 6)
    lo, hi = int(num(a)), int(num(b))
    return _rnd.randint(min(lo, hi), max(lo, hi))


def _f_now():
    return DateVal(_tehran())


def _f_today():
    d = _tehran()
    return DateVal(d.replace(hour=0, minute=0, second=0, microsecond=0))


def _as_date(d):
    if isinstance(d, DateVal):
        return d.dt
    if isinstance(d, str):
        s = d.strip().translate(_DIG)
        for f in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M", "%Y/%m/%d"):
            try:
                return datetime.strptime(s, f)
            except ValueError:
                continue
    raise ExprError("تاریخ نامعتبر")


_UNITS = {"day": "days", "days": "days", "hour": "hours", "hours": "hours", "minute": "minutes",
          "minutes": "minutes", "week": "weeks", "weeks": "weeks"}


def _f_date_add(d, n, unit="day"):
    u = _UNITS.get(str(unit).strip().lower())
    if not u:
        raise ExprError("واحد تاریخ نامعتبر")
    return DateVal(_as_date(d) + timedelta(**{u: float(num(n))}))


def _f_date_diff(a, b, unit="day"):
    u = _UNITS.get(str(unit).strip().lower())
    if not u:
        raise ExprError("واحد تاریخ نامعتبر")
    secs = (_as_date(a) - _as_date(b)).total_seconds()
    div = {"days": 86400, "hours": 3600, "minutes": 60, "weeks": 604800}[u]
    return int(secs // div) if secs >= 0 else -int((-secs) // div)


def _f_format(d, fmt="%Y/%m/%d", cal="fa"):
    dt = _as_date(d)
    fmt = str(fmt)
    if str(cal).lower() in ("fa", "jalali", "shamsi"):
        jy, jm, jd = to_jalali(dt.year, dt.month, dt.day)
        reps = {"YYYY": f"{jy:04d}", "MM": f"{jm:02d}", "DD": f"{jd:02d}", "HH": f"{dt.hour:02d}", "mm": f"{dt.minute:02d}"}
    else:
        reps = {"YYYY": f"{dt.year:04d}", "MM": f"{dt.month:02d}", "DD": f"{dt.day:02d}", "HH": f"{dt.hour:02d}", "mm": f"{dt.minute:02d}"}
    out = fmt
    for k, v in reps.items():
        out = out.replace(k, v)
    return out


def _f_first(l):
    if not isinstance(l, list) or not l:
        return None
    return l[0]


def _f_last(l):
    if not isinstance(l, list) or not l:
        return None
    return l[-1]


def _f_sort(l, desc=False):
    if not isinstance(l, list):
        raise ExprError("sort به فهرست نیاز دارد")
    return sorted(l, key=num, reverse=bool(desc)) if all(not isinstance(x, (str, bool)) or isinstance(x, str) for x in l[:50]) and all(not isinstance(x, str) for x in l[:50]) else sorted([str(x) for x in l], reverse=bool(desc))


def _f_sum(l):
    if not isinstance(l, list):
        raise ExprError("sum به فهرست نیاز دارد")
    t = 0
    for x in l[:500]:
        t = t + num(x)
    return t


def _f_unique(l):
    if not isinstance(l, list):
        raise ExprError("unique به فهرست نیاز دارد")
    out, seen = [], set()
    for x in l[:500]:
        k = (type(x).__name__, x if not isinstance(x, str) else x.casefold())
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


FUNCS = {
    "upper": (1, 1, lambda s: str(s).upper()),
    "lower": (1, 1, lambda s: str(s).lower()),
    "len": (1, 1, _f_len),
    "replace": (3, 3, _f_replace),
    "split": (1, 2, _f_split),
    "join": (1, 2, _f_join),
    "contains": (2, 2, _f_contains),
    "trim": (1, 1, _f_trim),
    "slice": (2, 3, _f_slice),
    "round": (1, 2, _f_round),
    "floor": (1, 1, lambda x: int(math.floor(num(x)))),
    "ceil": (1, 1, lambda x: int(math.ceil(num(x)))),
    "min": (1, 12, _f_min),
    "max": (1, 12, _f_max),
    "abs": (1, 1, lambda x: abs(num(x))),
    "clamp": (3, 3, _f_clamp),
    "random": (0, 2, _f_random),
    "now": (0, 0, _f_now),
    "today": (0, 0, _f_today),
    "date_add": (2, 3, _f_date_add),
    "date_diff": (2, 3, _f_date_diff),
    "format": (1, 3, _f_format),
    "first": (1, 1, _f_first),
    "last": (1, 1, _f_last),
    "sort": (1, 2, _f_sort),
    "sum": (1, 1, _f_sum),
    "unique": (1, 1, _f_unique),
}


# ───────────────────────── ارزیاب ─────────────────────────
class _Eval:
    def __init__(self, vars_, steps):
        self.vars, self.steps = vars_, steps

    def tick(self):
        self.steps -= 1
        if self.steps < 0:
            raise ExprError("بودجه‌ی گام تمام شد")

    def run(self, e):
        self.tick()
        k = e[0]
        if k == "lit":
            return e[1]
        if k == "var":
            if e[1] in self.vars:
                return _plain(self.vars[e[1]])
            raise ExprError(f"متغیر «{e[1]}» تعریف نشده")
        if k == "neg":
            return -num(self.run(e[1]))
        if k == "if":
            return self.run(e[2]) if _truthy(self.run(e[1])) else self.run(e[3])
        if k == "or":
            return self.run(e[1]) if _truthy(self.run(e[1])) else self.run(e[2])
        if k == "and":
            return self.run(e[2]) if _truthy(self.run(e[1])) else self.run(e[1])
        if k == "not":
            return not _truthy(self.run(e[1]))
        if k == "cmp":
            return self._cmp(e[1], self.run(e[2]), self.run(e[3]))
        if k == "in":
            hay = self.run(e[2])
            nd = self.run(e[1])
            if isinstance(hay, str):
                return str(nd).casefold() in hay.casefold()
            if isinstance(hay, list):
                return any(str(x).casefold() == str(nd).casefold() for x in hay[:500])
            if isinstance(hay, dict):
                return str(nd) in hay
            raise ExprError("عملگر in روی این نوع کار نمی‌کند")
        if k == "bin":
            return self._bin(e[1], self.run(e[2]), self.run(e[3]))
        if k == "idx":
            return self._idx(self.run(e[1]), self.run(e[2]))
        if k == "call":
            return self._call(e[1], [self.run(a) for a in e[2]])
        raise ExprError("گره ناشناخته")

    def _cmp(self, op, a, b):
        if op == "==":
            x, y = _cmp_pair(a, b)
            return x == y
        if op == "!=":
            x, y = _cmp_pair(a, b)
            return x != y
        x, y = num(a), num(b)
        return {"<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y}[op]

    def _bin(self, op, a, b):
        if op == "+":
            if isinstance(a, str) and isinstance(b, str):
                return (a + b)[:4000]
            if isinstance(a, list) and isinstance(b, list):
                return (a + b)[:500]
            return num(a) + num(b)
        x, y = num(a), num(b)
        if op == "-":
            return x - y
        if op == "*":
            return x * y
        if op == "/":
            if y == 0:
                raise ExprError("تقسیم بر صفر")
            r = x / y
            return int(r) if isinstance(x, int) and isinstance(y, int) and x % y == 0 else r
        if op == "%":
            if y == 0:
                raise ExprError("باقیمانده بر صفر")
            return x % y
        if op == "**":
            if abs(y) > 64:
                raise ExprError("توان بزرگ")
            r = x ** y
            return r if isinstance(r, (int, float)) and math.isfinite(r) else ExprError("نتیجه‌ی توان نامعتبر")
        raise ExprError("عملگر ناشناخته")

    def _idx(self, base, ix):
        if isinstance(base, dict):
            k = str(ix)
            if not _key_ok(k):
                raise ExprError("کلید نامعتبر")
            return base.get(k, "")
        if isinstance(base, list):
            i = int(num(ix))
            if -len(base) <= i < len(base):
                return base[i]
            raise ExprError("اندیس خارج از محدوده")
        if isinstance(base, str):
            i = int(num(ix))
            if -len(base) <= i < len(base):
                return base[i]
            raise ExprError("اندیس خارج از محدوده")
        raise ExprError("اندیس‌گذاری روی این نوع کار نمی‌کند")

    def _call(self, name, args):
        f = FUNCS.get(name)
        if not f:
            raise ExprError(f"تابع «{name}» وجود ندارد")
        lo, hi, fn = f
        if not (lo <= len(args) <= hi):
            raise ExprError(f"تعداد آرگومان «{name}» درست نیست")
        r = fn(*args)
        return _plain(r)


def _cmp_pair(a, b):
    """مقایسه‌ی == و != : عددها عددی، بقیه متنیِ بی‌حس‌وحال (هم‌معنای موتور)"""
    try:
        return num(a), num(b)
    except ExprError:
        return str(a).strip().casefold(), str(b).strip().casefold()


# ───────────────────────── ورودی عمومی ─────────────────────────
def compile_check(expr):
    """فقط بررسی نحوی (بدون ارزیابی): خطا = متن خطا، سالم = None؛ برای sanitize و lint"""
    s = str(expr or "").strip()
    try:
        if not s:
            raise ExprError("عبارت خالیه")
        if len(s) > EXPR_MAX_LEN:
            raise ExprError(f"عبارت بلندتر از {EXPR_MAX_LEN} نویسه")
        _Parser(_tokenize(s), EXPR_MAX_DEPTH).parse()
        return None
    except ExprError as e:
        return str(e)
    except Exception as e:
        return f"عبارت نامعتبر ({type(e).__name__})"


def eval_expr(expr, vars=None, steps=0):
    """ارزیابی با پرتاب ExprError (برای تست و مصرف‌کننده‌های آگاه)؛ خروجی همیشه نوع ساده"""
    s = str(expr or "").strip()
    if not s:
        raise ExprError("عبارت خالیه")
    if len(s) > EXPR_MAX_LEN:
        raise ExprError(f"عبارت بلندتر از {EXPR_MAX_LEN} نویسه")
    ast = _Parser(_tokenize(s), EXPR_MAX_DEPTH).parse()
    return _plain(_Eval(dict(vars or {}), int(steps) or EXPR_MAX_STEPS).run(ast))


def safe_eval(expr, vars=None, default="", steps=0, log_err=False):
    """ارزیابی امن: هر خطا مقدار پیش‌فرض برمی‌گرداند و ربات را نمی‌خواباند"""
    try:
        return eval_expr(expr, vars, steps)
    except ExprError as e:
        if log_err:
            log.info("expr: %s — %s", str(expr)[:80], e)
        return default
    except Exception as e:
        if log_err:
            log.warning("expr unexpected: %s — %r", str(expr)[:80], e)
        return default


def fill_expr(text, vars=None, default="", steps=0):
    """جای‌گذاری همه‌ی {=...}های یک متن؛ خطای هر عبارت فقط همان‌جا default می‌شود"""
    if not isinstance(text, str) or "{=" not in text:
        return text
    return EXPR_RE.sub(lambda m: "" if (v := safe_eval(m.group(1), vars, default, steps)) is None else str(v), text)


# ───────────────────────── selftest (طلایی + fuzz، بدون شبکه) ─────────────────────────
def selftest():
    ok = lambda name: print("ok —", name)
    V = {"score": "12", "name": "علی", "tags": ["a", "b", "c"], "nums": [3, 1, 2], "o": {"k": "v", "n": "7"}, "n": 4, "flag": True}
    cases = [
        ("1 + 2 * 3", 7), ("(1 + 2) * 3", 9), ("2 ** 10", 1024), ("10 % 3", 1),
        ("score * 2", 24), ("score + n", 16), ("\"a\" + \"b\"", "ab"),
        ("1 < 2", True), ("score >= 12", True), ("score == \"12\"", True),
        ("n > 3 and n < 5", True), ("not flag", False), ("flag or false", True),
        ("1 if score >= 10 else 0", 1), ("\"زیاد\" if score * 1 > 100 else \"کم\"", "کم"),
        ("\"x\" in \"axb\"", True), ("\"b\" in tags", True), ("\"z\" not in tags", True),
        ("tags[0]", "a"), ("tags[-1]", "c"), ("o.k", "v"), ("o[\"n\"]", "7"),
        ("upper(name)", "علی".upper()), ("len(tags)", 3), ("len(name)", len("علی")),
        ("replace(name, \"ع\", \"ا\")", "الی"), ("join(split(\"a,b,c\", \",\"), \"-\")", "a-b-c"),
        ("contains(\"سلام دنیا\", \"دنیا\")", True), ("trim(\"  x  \")", "x"), ("slice(\"abcd\", 1, 3)", "bc"),
        ("round(3.6)", 4), ("floor(3.9)", 3), ("ceil(3.1)", 4), ("min(3, 1, 2)", 1), ("max(nums, 9)", 9), ("min(nums)", 1),
        ("abs(0 - 5)", 5), ("clamp(15, 0, 10)", 10),
        ("sum(split(\"1,2,3\", \",\"))", 6), ("unique(split(\"a,a,b\", \",\"))", ["a", "b"]),
        ("first(tags)", "a"), ("last(tags)", "c"), ("len(unique(tags))", 3),
        ("format(now(), \"YYYY/MM/DD\", \"fa\")", _f_format(_f_now(), "YYYY/MM/DD", "fa")),
        ("date_diff(date_add(today(), 3), today())", 3),
        ("clamp(score, 0, 10) * 2", 20),
    ]
    for expr, want in cases:
        got = safe_eval(expr, V, default=("ERR",))
        assert got == want, f"{expr!r} → {got!r} ≠ {want!r}"
    ok(f"تست طلایی ({len(cases)} عبارت)")

    # سقف‌ها و خطاها: هرگز exception بیرون نمی‌دهد
    assert safe_eval("1 + " * 400 + "1", V, default="D") == "D"          # طول و پارسر
    assert safe_eval("x", V, default="") == ""                            # متغیر ناشناس
    assert safe_eval("1/0", V, default=-1) == -1                          # تقسیم بر صفر
    assert safe_eval("o.__class__", V, default="D") == "D"                # کلید ممنوع
    assert safe_eval("__import__", V, default="D") == "D"                 # نام ممنوع = متغیر ناشناس
    assert safe_eval("sort(tags) == tags", V, default=False) is True
    deep = "(" * 20 + "1" + ")" * 20
    assert safe_eval(deep, V, default="D") == "D"                         # عمق > ۱۲
    assert safe_eval("random(1, 1)", V) == 1
    assert isinstance(safe_eval("random()", V), float)
    ok("سقف طول/عمق/گام و خطاها → پیش‌فرض")

    # fuzz: ۵۰۰ رشته‌ی تصادفی خراب هرگز exception بیرون نمی‌دهد
    alphabet = "1a+*(\")[]{}., امتیاز<>=!andornotinifelse\\#$%^\x00"
    seed = 123456
    for i in range(500):
        seed = (seed * 1103515245 + 12345) % (2 ** 31)
        n = seed % 60
        s = "".join(alphabet[(seed >> j) % len(alphabet)] for j in range(n))
        safe_eval(s, V, default="D")
    ok("fuzz: ۵۰۰ ورودی خراب بدون exception")
    print("expr selftest passed")


if __name__ == "__main__":
    selftest()
