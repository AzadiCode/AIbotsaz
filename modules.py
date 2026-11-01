# -*- coding: utf-8 -*-
"""
modules.py — سیستم ساخت ماژولی (کامپایلر قطعی)

ایده: به‌جای اینکه هوش مصنوعی کل ساختار ربات را بنویسد (کند، پرخطا، غیرقابل‌پیش‌بینی)، هر قابلیت یک بار
به‌صورت «ماژول» دقیق و تست‌شده نوشته شده؛ ربات = فهرستی از ماژول‌ها + پارامترها. کامپایلر آن‌ها را به همان
کانفیگ JSON موتور تبدیل می‌کند؛ خروجی همیشه معتبر است، بدون توکن و در چند میلی‌ثانیه ساخته می‌شود.

  درخواست ← روتر (کلیدواژه/الگو، در صورت نیاز هوش مصنوعیِ کوچک) ← ماژول‌ها + پارامترها ← کامپایلر ← کانفیگ ربات

نقش هوش مصنوعی: فقط «انتخاب ماژول و پر کردن پارامتر» (چند صد توکن) و آن هم فقط وقتی روتر قطعی مطمئن نیست.
هیچ چیز اجرا نمی‌شود؛ خروجی با sanitize/lint همان موتور اعتبارسنجی می‌شود (در ai.py).

افزودن ماژول تازه: یک تابع compile(b, p) بنویس و با register(Module(...)) ثبت کن؛ تست خودکار
(tests/test_modules.py) هر ماژول را با پارامترهای پیش‌فرض و ترکیب‌های مختلف می‌سازد و با اعتبارسنج اصلی می‌سنجد.

نام‌های پایدار برای فایل‌های دیگر:
  MODULES, plan_request, compile_plan, catalog, clean_params, normalize_text, PlanResult
"""

import re
import json
import html as _html
import hashlib
import random

# ───────────────────────── ابزارهای کوچک ─────────────────────────
_DIG = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_ID_RE = re.compile(r"^[a-z0-9_]{1,30}$")
_VAR_RE = re.compile(r"^[a-z][a-z0-9_]{0,19}$")
_TG_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")
MAX_VARS = 40
MAX_NODES_HARD = 200


def normalize_text(t):
    """نرمال‌سازی متن فارسی برای تطبیق الگو: ی/ک عربی، ارقام، نیم‌فاصله و فاصله‌های اضافه"""
    t = str(t or "").translate(_DIG)
    t = t.replace("ي", "ی").replace("ك", "ک").replace("ۀ", "ه").replace("ة", "ه")
    t = t.replace("‌", " ").replace("‏", "").replace("‎", "").replace(" ", " ")
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()


def _num(x, default=0.0):
    try:
        v = float(str(x).translate(_DIG).replace(",", "").replace("٬", "").replace("٫", ".").strip())
        return v if v == v and abs(v) < 1e12 else default
    except (TypeError, ValueError):
        return default


def fmt(x):
    """عدد → متن کوتاه (۵ نه ۵.۰)"""
    x = _num(x)
    return str(int(x)) if x == int(x) else ("%.4f" % x).rstrip("0").rstrip(".")


def _clean_text(s, mx=200):
    """متن کاربر برای قرار گرفتن در کانفیگ: بدون آکولاد (جای‌نگهدار)، بدون HTML خام"""
    s = re.sub(r"[{}]", "", str(s or ""))
    s = re.sub(r"[\x00-\x08\x0b-\x1f]", "", s).strip()
    return s[:mx]


def _h(s, mx=200):
    return _html.escape(_clean_text(s, mx), quote=False)


def _btn(text, **kw):
    return {"text": str(text)[:40], **kw}


def _group(buttons, per=2):
    """فهرست دکمه‌ها → ردیف‌های حداکثر per‌تایی (سقف موتور: ۶ ردیف × ۳)"""
    rows = []
    for i in range(0, len(buttons), per):
        rows.append(list(buttons[i:i + per]))
    return rows


# ───────────────────────── پارامترها ─────────────────────────
def P(k, fa, kind, default, **kw):
    """تعریف یک پارامتر ماژول. kind: int num text list prizes channels items bool"""
    d = {"k": k, "fa": fa, "kind": kind, "default": default}
    d.update(kw)
    return d


def _coerce(spec, raw):
    kind, default = spec["kind"], spec["default"]
    if raw is None:
        return json.loads(json.dumps(default))
    try:
        if kind == "int":
            v = int(round(_num(raw, default)))
            return max(spec.get("min", 0), min(spec.get("max", 10 ** 9), v))
        if kind == "num":
            v = _num(raw, default)
            return max(spec.get("min", 0.0), min(spec.get("max", 1e9), v))
        if kind == "bool":
            if isinstance(raw, str):
                return raw.strip().lower() in ("1", "true", "yes", "on", "بله", "آره")
            return bool(raw)
        if kind == "text":
            v = _clean_text(raw, spec.get("max", 400))
            return v or default
        if kind == "list":
            arr = raw if isinstance(raw, list) else re.split(r"[\n|،;]+", str(raw))
            out = [_clean_text(x, spec.get("item", 80)) for x in arr]
            out = [x for x in out if x][:spec.get("n", 10)]
            return out or json.loads(json.dumps(default))
        if kind == "prizes":
            arr = raw if isinstance(raw, list) else re.split(r"[\s,،|;]+", str(raw))
            out = []
            for x in arr:
                if isinstance(x, str) and x.strip().lower() in ("puzzle", "پازل"):
                    out.append("puzzle")
                else:
                    v = _num(x, None)
                    if v is not None and 0 < v <= 100000:
                        out.append(v)
            out = out[:spec.get("n", 12)]
            return out if len(out) >= 2 else json.loads(json.dumps(default))
        if kind == "channels":
            arr = raw if isinstance(raw, list) else re.split(r"[\s,،;]+", str(raw))
            out = []
            for x in arr:
                x = str(x).strip().lstrip("@")
                x = re.sub(r"^https?://t\.me/", "", x)
                if _TG_NAME.match(x) and x not in out:
                    out.append(x)
            return out[:spec.get("n", 10)] or json.loads(json.dumps(default))
        if kind == "items":
            keys = spec["keys"]
            out = []
            for it in (raw if isinstance(raw, list) else []):
                if not isinstance(it, dict):
                    continue
                row = {k: (_clean_text(it.get(k), mx) if k != "opts" else
                           [_clean_text(o, 40) for o in (it.get(k) or []) if _clean_text(o, 40)][:4])
                       for k, mx in keys.items()}
                if all(row.get(k) for k in spec.get("need", list(keys)[:1])):
                    out.append(row)
            return out[:spec.get("n", 8)] or json.loads(json.dumps(default))
    except Exception:
        pass
    return json.loads(json.dumps(default))


def clean_params(mod, raw):
    raw = raw if isinstance(raw, dict) else {}
    return {s["k"]: _coerce(s, raw.get(s["k"])) for s in mod.params}


# ───────────────────────── سازندهٔ کانفیگ ─────────────────────────
class BuildError(Exception):
    pass


class Builder:
    """جمع‌کنندهٔ همهٔ تکه‌های ربات؛ ماژول‌ها فقط با همین رابط می‌نویسند."""

    def __init__(self, name, emoji=False, payments=False):
        self.name = _clean_text(name, 30) or "ربات من"
        self.emoji = bool(emoji)
        self.payments = bool(payments)
        self.coin = "سکه"
        self.coin_emoji = "💰"
        self.nodes, self.vars, self.globals, self.commands = {}, {}, {}, {}
        self.menu = []                  # (prio, label, goto, when)
        self.on_ref, self.ref_text = [], ""
        self.desk, self.join, self.mod, self.group = {}, None, None, None
        self.start_routes = []          # قانون‌های route اضافه برای start (مثل هدیه‌ی اولین ورود)
        self.start_text = ""            # متن معرفی اختیاری
        self.notes, self.ideas = [], []
        self.have = set()               # شناسهٔ ماژول‌های فعال
        self.shared = {}                # داده‌ی مشترک بین ماژول‌ها
        self.titles = []                # عنوان فارسی ماژول‌ها (برای متن start)

    # --- ایموجی: فقط وقتی کاربر خواسته ---
    def E(self, emo):
        return (emo + " ") if self.emoji else ""

    def c(self, n):
        """«۵ سکه» با واحد پول ربات"""
        return f"{fmt(n)} {self.coin}"

    # --- متغیرها ---
    def var(self, k, default="0"):
        if not _VAR_RE.match(k):
            raise BuildError(f"نام متغیر نامعتبر: {k}")
        if k in self.globals:
            raise BuildError(f"متغیر {k} هم شخصی هم مشترک است")
        if k not in self.vars:
            if len(self.vars) >= MAX_VARS:
                raise BuildError("تعداد متغیرها از سقف ۴۰ گذشت")
            self.vars[k] = str(default)
        return k

    def glob(self, k, default="0"):
        if not _VAR_RE.match(k) or k in self.vars:
            raise BuildError(f"نام متغیر مشترک نامعتبر: {k}")
        self.globals[k] = str(default)
        return k

    # --- بخش‌ها ---
    def node(self, nid, text, buttons=None, **kw):
        if not _ID_RE.match(nid):
            raise BuildError(f"شناسه‌ی بخش نامعتبر: {nid}")
        if nid in self.nodes:
            raise BuildError(f"شناسه‌ی بخش تکراری: {nid}")
        if len(self.nodes) >= MAX_NODES_HARD:
            raise BuildError("تعداد بخش‌ها از سقف گذشت")
        n = {"text": text, "buttons": buttons or []}
        n.update(kw)
        self.nodes[nid] = n
        return nid

    def back(self, to="start", text="بازگشت"):
        return [_btn(text, goto=to)]

    def menu_add(self, prio, label, goto, when=None):
        self.menu.append((prio, label, goto, when))

    def cmd(self, name, nid):
        if re.match(r"^[a-z0-9_]{1,30}$", name) and name not in self.commands and nid in self.nodes:
            self.commands[name] = nid

    # --- ساخت نهایی ---
    def finish(self):
        menu = sorted(self.menu, key=lambda x: x[0])
        btns = []
        for _, label, goto, when in menu:
            b = _btn(label, goto=goto)
            if when:
                b["when"] = when
            btns.append(b)
        extra = []
        if len(btns) > 11:                      # سقف ۶ ردیف × ۲؛ بقیه در صفحهٔ «بیشتر»
            extra, btns = btns[10:], btns[:10]
        rows = _group(btns, 2)
        if extra:
            more_rows = _group(extra, 2) + [self.back()]
            self.node("more", "گزینه‌های بیشتر:", more_rows, title="بیشتر")
            rows.append([_btn("گزینه‌های بیشتر", goto="more")])
        intro = self.start_text or self._default_intro()
        start = {"text": intro, "buttons": rows, "title": "منوی اصلی"}
        if self.start_routes:
            start["route"] = list(self.start_routes)[:5]
        self.nodes = {"start": start, **self.nodes}
        cfg = {"name": self.name, "start": "start", "fallback": "start", "commands": dict(self.commands),
               "nodes": self.nodes}
        if self.vars:
            cfg["vars"] = dict(self.vars)
        if self.globals:
            cfg["globals"] = dict(self.globals)
        if self.desk:
            cfg["desk"] = dict(self.desk)
        if self.join:
            cfg["join"] = dict(self.join)
        if self.mod:
            cfg["mod"] = dict(self.mod)
        if self.group:
            cfg["group"] = dict(self.group)
        if self.on_ref:
            cfg["on_ref"] = list(self.on_ref)[:6]
            if self.ref_text:
                cfg["ref_text"] = self.ref_text
        return cfg

    def _default_intro(self):
        t = f"<b>{_h(self.name)}</b>\n\nسلام {{name}} عزیز، خوش اومدی."
        if self.coin_used():
            t += f"\nموجودی تو: {{coins}} {self.coin}"
        return t + "\nیکی از گزینه‌ها را انتخاب کن:"

    def coin_used(self):
        return "coins" in self.vars

    def have_or_planned(self):
        return set(self.have) | set(self.shared.get("plans", {}))


# ───────────────────────── ثبت ماژول‌ها ─────────────────────────
class Module:
    def __init__(self, mid, fa, desc, compile_fn, params=None, triggers=None, requires=(), prio=50,
                 cat="عمومی", extract=None, title=""):
        self.id, self.fa, self.desc = mid, fa, desc
        self.compile = compile_fn
        self.params = params or []
        self.triggers = triggers or []        # [(regex, وزن)]
        self.requires = tuple(requires)
        self.prio = prio
        self.cat = cat
        self.extract = extract                # extract(text, ctx) → پارامترهای استخراج‌شده از متن درخواست
        self.title = title or fa


MODULES = {}


def register(mod):
    if mod.id in MODULES:
        raise BuildError("ماژول تکراری: " + mod.id)
    MODULES[mod.id] = mod
    return mod


def catalog():
    """فهرست عمومی ماژول‌ها برای رابط کاربری و روتر هوش مصنوعی"""
    out = []
    for m in sorted(MODULES.values(), key=lambda x: x.prio):
        out.append({"id": m.id, "fa": m.fa, "desc": m.desc, "cat": m.cat, "requires": list(m.requires),
                    "params": [{k: v for k, v in s.items() if k in ("k", "fa", "kind", "default")} for s in m.params]})
    return out
