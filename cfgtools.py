# -*- coding: utf-8 -*-
"""
cfgtools.py — ابزارهای تحلیل کانفیگ برای استودیو (مرحله ۴).

vars_report: پنل متغیر — همه‌ی متغیرها با نوع/پیش‌فرض/محل استفاده، استفاده‌نشده و تعریف‌نشده.
diff_cfg: تفاوت دو کانفیگ در سطح نود (اضافه/حذف/تغییر) و تنظیمات؛ برای نسخه‌های نام‌دار.

هر دو فقط خواندنی‌اند (بدون تغییر کانفیگ) و جایگزین sanitize نیستند.
"""
import json
import re

from ai import BUILTINS, PH_RE, VAR_RE
from expr import EXPR_RE, FUNCS

VAR_TYPES_FA = {"text": "متن", "number": "عدد", "bool": "بله/خیر", "date": "تاریخ", "list": "فهرست", "object": "شیء"}

NODE_FIELD_FA = {
    "title": "نام بخش", "text": "متن", "photo": "عکس", "media": "رسانه", "buttons": "دکمه‌ها",
    "do": "اکشن‌ها", "route": "هدایت شرطی", "alt": "متن جایگزین", "next": "ادامه", "ask": "دریافت پیام",
    "ai": "دستیار هوشمند", "fields": "سؤال‌های فرم", "types": "نوع فیلدها", "save": "ذخیره‌ی فرم",
    "choices": "گزینه‌ها", "minmax": "حداقل/حداکثر", "hints": "راهنما", "wizard": "ویزارد", "confirm": "تأیید",
    "skippable": "رد شدن", "retry": "تعداد تلاش", "timeout": "انقضا", "done": "پیام تشکر", "done_media": "رسانه‌ی تشکر",
    "ticket": "تیکت", "tag": "برچسب", "silent": "ساکت", "board": "جدول برترین‌ها", "join": "عضویت اجباری",
    "switch": "سوئیچ", "wait": "مکث", "typing": "تایپینگ", "ab": "آزمون A/B", "on_error": "مدیریت خطا",
    "menu": "منوی فهرست‌دار", "protect": "حفاظت", "spoiler": "اسپویلر",
}
CFG_FIELD_FA = {
    "name": "نام ربات", "start": "بخش شروع", "fallback": "بخش بن‌بست", "vars": "متغیرها", "globals": "متغیرهای مشترک",
    "commands": "دستورها", "join": "عضویت اجباری", "desk": "پشتیبانی و تیکت", "mod": "مدیریت گروه و کانال",
    "group": "ماشه‌های گروه", "tables": "جدول‌های داده", "drips": "دنباله‌های زمانی", "segments": "سگمنت‌ها",
    "i18n": "ترجمه‌ها", "i18n_lang": "متغیر زبان", "secrets": "رازها", "outhooks": "وب‌هوک خروجی",
    "on_ref": "پاداش دعوت", "ref_text": "متن دعوت", "payments": "پرداخت‌ها", "note": "یادداشت",
}
_CFG_SKIP = {"nodes", "dbfields", "schema_version"}
_IDENT = re.compile(r"[a-z_][a-z0-9_]*")
_EXPR_SKIP = set(FUNCS) | {"and", "or", "not", "in", "true", "false", "int", "str", "float"}


def _expr_names(e):
    """نام متغیرهای داخل یک عبارت {=…} (بدون نام تابع و فیلدِ بعد از نقطه)"""
    e = re.sub(r"\.\s*[a-z_][a-z0-9_]*", "", e or "")
    return {t for t in _IDENT.findall(e) if t not in _EXPR_SKIP and VAR_RE.match(t)}


def _scan_str(s, found):
    if not isinstance(s, str) or not s:
        return
    for m in PH_RE.finditer(s):
        n = m.group(1)
        if VAR_RE.match(n) and n not in BUILTINS:
            found.add(n)
    for m in EXPR_RE.finditer(s):
        found.update(_expr_names(m.group(1)))


def _scan_cond(c, reads):
    """شرط ساده یا ترکیبی (all/any/not) بازگشتی"""
    if not isinstance(c, dict):
        return
    if c.get("all") or c.get("any"):
        for x in c.get("all") or []:
            _scan_cond(x, reads)
        for x in c.get("any") or []:
            _scan_cond(x, reads)
    if c.get("not"):
        _scan_cond(c["not"], reads)
        return
    v = c.get("var")
    if isinstance(v, str) and VAR_RE.match(v) and v not in BUILTINS:
        reads.add(v)
    _scan_str(str(c.get("value") or ""), reads)


def _scan_actions(acts, reads, writes):
    for a in acts or []:
        if not isinstance(a, dict):
            continue
        op = a.get("op")
        v = a.get("var")
        if isinstance(v, str) and VAR_RE.match(v) and v not in BUILTINS:
            (writes if op in ("set", "add", "clear", "random", "cart_add", "cart_del", "cart_clear",
                              "checkout", "db_add", "db_del") else reads).add(v)
        if op in ("cart_add", "cart_del", "cart_clear", "checkout"):
            for k in ("cart", "wallet", "pfx"):
                x = a.get(k)
                if isinstance(x, str) and VAR_RE.match(x) and x not in BUILTINS:
                    writes.add(x)
        _scan_str(str(a.get("value") or ""), reads)
        _scan_str(str(a.get("key") or ""), reads)
        _scan_str(str(a.get("coupon") or ""), reads)
        _scan_str(str(a.get("text") or ""), reads)          # notify/remind/outwh
        _scan_str(str(a.get("list") or ""), reads)          # منوی فهرست‌دار
        _scan_cond(a.get("when"), reads)


def _scan_node(n, reads, writes):
    for k in ("text", "done", "jtext", "photo"):
        _scan_str(n.get(k), reads)
    for r in n.get("alt") or []:
        _scan_str(r.get("text"), reads)
        _scan_cond(r.get("when"), reads)
    for r in n.get("route") or []:
        _scan_cond(r.get("when"), reads)
    for row in n.get("buttons") or []:
        for b in row:
            if not isinstance(b, dict):
                continue
            _scan_str(b.get("text"), reads)
            for k in ("alert", "copy", "share", "jtext"):
                _scan_str(b.get(k), reads)
            if isinstance(b.get("pay"), dict):
                _scan_str(str(b["pay"].get("add") or ""), writes)
                _scan_str(str(b["pay"].get("text") or ""), reads)
            _scan_cond(b.get("when"), reads)
            _scan_actions(b.get("do"), reads, writes)
    _scan_actions(n.get("do"), reads, writes)
    for k in ("save",):
        for v in n.get(k) or []:
            if isinstance(v, str) and VAR_RE.match(v) and v not in BUILTINS:
                writes.add(v)
    for k in ("board", "ab", "menu"):
        x = n.get(k)
        if isinstance(x, dict):
            v = x.get("var")
            if isinstance(v, str) and VAR_RE.match(v) and v not in BUILTINS:
                (reads if k == "board" else writes).add(v)
            _scan_str(str(x.get("list") or ""), reads)
    _scan_str(str((n.get("ai") or {}).get("prompt") or ""), reads)
    sw = n.get("switch")
    if isinstance(sw, dict):
        v = sw.get("value")
        if isinstance(v, str) and VAR_RE.match(v) and v not in BUILTINS:
            reads.add(v)
        _scan_str(str(v or ""), reads)


def vars_report(cfg):
    """گزارش متغیرهای کانفیگ: تعریف‌شده‌ها با محل استفاده، استفاده‌نشده، فقط‌نوشتنی و تعریف‌نشده"""
    reads, writes, locs = set(), set(), {}
    nodes = cfg.get("nodes") or {}
    for nid, n in nodes.items():
        if not isinstance(n, dict):
            continue
        r0, w0 = set(reads), set(writes)
        _scan_node(n, reads, writes)
        loc = (n.get("title") or nid).strip()[:40]
        for v in (reads - r0) | (writes - w0):
            locs.setdefault(v, []).append(loc)
    gt = ((cfg.get("group") or {}).get("triggers")) or []
    for t in gt:
        r0, w0 = set(reads), set(writes)
        _scan_str(t.get("reply"), reads)
        _scan_cond(t.get("when"), reads)
        v = t.get("var")
        if t.get("op") in ("add", "set") and isinstance(v, str) and VAR_RE.match(v) and v not in BUILTINS:
            writes.add(v)
        _scan_actions(t.get("do"), reads, writes)
        for v in (reads - r0) | (writes - w0):
            locs.setdefault(v, []).append("ماشه‌های گروه")
    for k in ("ref_text", "jtext"):
        _scan_str(cfg.get(k), reads)
        if k in cfg:
            locs.setdefault(k, []).append("تنظیمات ربات")
    for st in ((cfg.get("drips") or {}).values()):
        for s in st.get("steps") or []:
            _scan_str(s.get("text"), reads)
    for v in (cfg.get("i18n") or {}).values():
        for s in (v.values() if isinstance(v, dict) else []):
            _scan_str(s, reads)

    defined, glo = {}, {}
    dv = cfg.get("vars")
    for k, v in (dv.items() if isinstance(dv, dict) else []):
        if isinstance(v, dict):
            defined[k] = {"type": str(v.get("type") or "text").lower(), "default": str(v.get("default") or ""),
                          "scope": str(v.get("scope") or "user").lower()}
        else:
            defined[k] = {"type": "text", "default": str(v or ""), "scope": "user"}
    gv = cfg.get("globals")
    for k, v in (gv.items() if isinstance(gv, dict) else []):
        glo[k] = str(v or "")

    def row(k, scope, ty, dflt):
        ls = locs.get(k) or []
        seen, uniq = set(), []
        for x in ls:
            if x not in seen:
                seen.add(x)
                uniq.append(x)
        return {"name": k, "type": ty, "default": dflt, "scope": scope,
                "read": k in reads, "write": k in writes, "locs": uniq[:4], "nlocs": len(ls)}

    out_vars = [row(k, d["scope"], VAR_TYPES_FA.get(d["type"], d["type"]), d["default"]) for k, d in sorted(defined.items())]
    out_glo = [row(k, "shared", "متن", v) for k, v in sorted(glo.items())]
    known = set(defined) | set(glo)
    unused = sorted(k for k in known if k not in reads and k not in writes)
    writeonly = sorted(k for k in known if k in writes and k not in reads)
    undef = sorted(v for v in reads - known - writes)
    return {"vars": out_vars, "globals": out_glo, "unused": unused, "writeonly": writeonly,
            "undefined": [{"name": k, "locs": (locs.get(k) or [])[:4]} for k in undef]}


def _fields_diff(x, y):
    out = []
    for k in sorted(set(x) | set(y), key=str):
        if k in _CFG_SKIP:
            continue
        if json.dumps(x.get(k), ensure_ascii=False, sort_keys=True, default=str) != \
           json.dumps(y.get(k), ensure_ascii=False, sort_keys=True, default=str):
            out.append(NODE_FIELD_FA.get(k, CFG_FIELD_FA.get(k, k)))
    return out


def diff_cfg(a, b):
    """تفاوت کانفیگ a (مبنا) با b در سطح نود و تنظیمات؛ خروجی برای نمایش در استودیو"""
    na, nb = a.get("nodes") or {}, b.get("nodes") or {}
    title = lambda cfg, nid: str((cfg.get("nodes", {}).get(nid) or {}).get("title") or nid)[:40]
    added = [{"id": k, "title": title(b, k)} for k in nb if k not in na]
    removed = [{"id": k, "title": title(a, k)} for k in na if k not in nb]
    changed = [{"id": k, "title": title(b, k), "fields": _fields_diff(na[k], nb[k])}
               for k in nb if k in na and _fields_diff(na[k], nb[k])]
    ka, kb = set(a) - _CFG_SKIP, set(b) - _CFG_SKIP
    settings = [CFG_FIELD_FA.get(k, k) for k in sorted(ka | kb, key=str)
                if json.dumps(a.get(k), ensure_ascii=False, sort_keys=True, default=str) !=
                json.dumps(b.get(k), ensure_ascii=False, sort_keys=True, default=str)]
    return {"added": added, "removed": removed, "changed": changed, "settings": settings,
            "same": not (added or removed or changed or settings)}
