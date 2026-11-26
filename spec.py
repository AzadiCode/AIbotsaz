# -*- coding: utf-8 -*-
"""
spec.py — استاندارد Spec: قرارداد کوچک و قابل پیش‌بینی بین «درک هوش مصنوعی» و «کامپایلر قطعی» (BUILD 3.6.0)

معماری:  درخواست کاربر ← (روتر قطعی یا یک فراخوانی مدل) ← Spec استاندارد و کوچک
        ← اعتبارسنجی (JSON → Schema → Enum → پارامترها → وابستگی‌ها) ← کامپایلر قطعی ← کانفیگ موتور

قانون‌ها:
  • خروجی مدل زبانی هرگز مستقیم وارد موتور نمی‌شود؛ فقط Spec اعتبارسنجی‌شده.
  • نوع قابلیت فقط از Enum بستهٔ کاتالوگ انتخاب می‌شود (MODULES + ALIASES).
  • کلیدهای ناشناخته، قابلیت خارج از کاتالوگ و مقادیر نامعتبر رد می‌شوند.
  • کامپایلر قطعی (modules/planner/modlib) تمام منطق اجرایی را می‌سازد.

نام‌های پایدار: SPEC_VERSION, validate_spec, spec_from_plan, compile_spec, spec_to_plan,
                spec_prompt, parse_llm_spec, preview_spec, spec_feature_ids, SpecError
"""

import json
import re

from modules import MODULES, BuildError, normalize_text, clean_params, _clean_text

SPEC_VERSION = 1

# شناسه‌های استاندارد قابلیت‌ها در Spec ←→ شناسهٔ ماژول در کاتالوگ داخلی
ALIASES = {
    "game.quiz": "quiz",
    "game.wheel": "wheel",
    "bot.start_menu": "start_menu",
}
# هر ماژول ثبت‌شده به‌همراه نام استانداردش قابل انتخاب است
def _ensure_catalog():
    """ثبت ماژول‌ها در کاتالوگ (idempotent)؛ بدون آن MODULES خالی است."""
    try:
        import modlib  # noqa: F401
    except Exception:
        pass


def spec_feature_ids():
    _ensure_catalog()
    out = []
    for mid in MODULES:
        out.append(mid)
    for alias in ALIASES:
        out.append(alias)
    return sorted(out)


class SpecError(ValueError):
    """Spec نامعتبر؛ متن خطا برای کاربر/مدل قابل گزارش است."""
    def __init__(self, msg, errors=None):
        super().__init__(msg)
        self.errors = list(errors or [])


# ───────────────────────── اعتبارسنجی مرحله‌به‌مرحله ─────────────────────────
def _feature_type(raw):
    """نوع قابلیت → شناسهٔ ماژول؛ ناشناخته رد می‌شود."""
    if not isinstance(raw, str):
        return None
    t = raw.strip().lower()
    if not re.fullmatch(r"[a-z0-9_.]{1,40}", t):
        return None
    if t in MODULES:
        return t
    if t in ALIASES:
        return ALIASES[t]
    return None


def _allowed_param_keys(mod):
    return {s["k"] for s in mod.params}


def validate_spec(obj):
    """
    JSON خام → Spec اعتبارسنجی‌شده.
    مراحل: ساختار → نسخه/نیت → نام → قابلیت‌ها (Enum + پارامترها) → وابستگی‌ها → متن‌ها.
    خروجی: dict استاندارد. خطا: SpecError با فهرست خطاها.
    """
    _ensure_catalog()
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except Exception as e:
            raise SpecError("خروجی مدل JSON معتبر نیست", [f"json: {e}"])
    if not isinstance(obj, dict):
        raise SpecError("Spec باید یک شیء JSON باشد")
    errors = []

    # 1) ساختار کلی
    if set(obj) - {"version", "intent", "name", "emoji", "payments", "features", "texts"}:
        errors.append("کلیدهای ناشناخته در Spec؛ فقط version/intent/name/emoji/payments/features/texts مجاز است")
        obj = {k: v for k, v in obj.items() if k in ("version", "intent", "name", "emoji", "payments", "features", "texts")}

    # 2) نسخه و نیت (اصلاح قطعی بی‌صدا؛ نه رد)
    if int(obj.get("version") or 0) != SPEC_VERSION:
        obj["version"] = SPEC_VERSION
    intent = str(obj.get("intent") or "create").strip().lower()
    if intent not in ("create", "edit"):
        intent = "create"
    obj["intent"] = intent

    # 3) نام ربات
    name = _clean_text(obj.get("name") or "", 30)
    obj["name"] = name or "ربات من"

    # 4) قابلیت‌ها: Enum + پارامترها
    feats = obj.get("features")
    if not isinstance(feats, list) or not feats:
        raise SpecError("حداقل یک قابلیت لازم است", ["features خالی یا نامعتبر است"])
    if len(feats) > 12:
        errors.append("حداکثر ۱۲ قابلیت در یک ساخت")
        feats = feats[:12]
    out_feats, seen = [], []
    for f in feats:
        if not isinstance(f, dict):
            errors.append("هر قابلیت باید شیء JSON باشد")
            continue
        t = _feature_type(f.get("type"))
        if not t:
            errors.append(f"قابلیت «{f.get('type')}» خارج از کاتالوگ است")
            continue
        mod = MODULES[t]
        allowed = _allowed_param_keys(mod)
        params = f.get("params") if isinstance(f.get("params"), dict) else {}
        if not isinstance(params, dict):
            params = {}
            errors.append(f"پارامترهای {t} باید شیء JSON باشد")
        extra = set(params) - allowed
        if extra:
            errors.append(f"پارامترهای ناشناخته در {t}: {', '.join(sorted(extra))}")
            params = {k: v for k, v in params.items() if k in allowed}
        out_feats.append({"type": t, "params": params})
        if t in seen and t not in ("start_menu",):
            errors.append(f"قابلیت {t} تکراری است")
        seen.append(t)
        # کلیدهای اضافه روی خود قابلیت رد می‌شود (قرارداد: params فقط زیر کلید params)
        if set(f) - {"type", "params", "note"}:
            errors.append(f"کلیدهای اضافه روی قابلیت {t} رد شد")
    if not out_feats:
        raise SpecError("هیچ قابلیت معتبری در Spec نبود", errors)

    # 5) وابستگی‌ها: قابلیت‌های لازم خودکار و بی‌صدا اضافه می‌شوند (رفع قطعی، نه خطا)
    chosen = [f["type"] for f in out_feats]
    need = []
    for t in chosen:
        for r in MODULES[t].requires:
            if r not in chosen and r not in need:
                need.append(r)
    for r in need:
        out_feats.append({"type": r, "params": {}})
    obj["features"] = out_feats

    # 6) متن‌ها
    texts = obj.get("texts") if isinstance(obj.get("texts"), dict) else {}
    if set(texts) - {"welcome", "success", "fail", "start", "notes"}:
        errors.append("کلیدهای متن فقط welcome/success/fail/start/notes است")
        texts = {k: v for k, v in texts.items() if k in ("welcome", "success", "fail", "start", "notes")}
    obj["texts"] = {k: _clean_text(v, 400) for k, v in texts.items()}

    obj["emoji"] = bool(obj.get("emoji"))
    obj["payments"] = bool(obj.get("payments"))
    if errors:
        raise SpecError("Spec اعتبارسنجی نشد", errors)
    return obj


def spec_from_plan(pr):
    """خروجی روتر قطعی (PlanResult) → Spec؛ بدون هیچ فراخوانی مدل."""
    feats = [{"type": i, "params": p} for i, p in pr.items]
    return {"version": SPEC_VERSION, "intent": "create", "name": pr.name or "ربات من",
            "emoji": bool(pr.emoji), "payments": bool(pr.payments), "features": feats, "texts": {}}


def spec_to_plan(spec):
    """Spec معتبر → (items, name, emoji, payments) برای کامپایلر موجود."""
    items = []
    for f in spec["features"]:
        t = f.get("type")
        if t not in MODULES:
            raise BuildError(f"قابلیت نامعتبر: {t}")
        items.append((t, clean_params(MODULES[t], f.get("params") or {})))
    return items, spec.get("name") or "ربات من", bool(spec.get("emoji")), bool(spec.get("payments"))


def compile_spec(spec):
    """Spec اعتبارسنجی‌شده → (thinking, cfg, ideas) با کامپایلر قطعی موجود. خطا: BuildError."""
    import planner
    spec = validate_spec(spec)
    items, name, emoji, payments = spec_to_plan(spec)
    pr = planner.PlanResult()
    pr.items = items
    pr.name = name
    pr.emoji = emoji
    pr.payments = payments
    pr.confidence = 1.0
    return planner.compile_plan(pr)


# ───────────────────────── نقشهٔ پیش‌نمایش ─────────────────────────
def _texts_of(mod, params, spec_texts):
    """متن‌های قابل ویرایش هر قابلیت → پیش‌نمایش شفاف برای کاربر."""
    return [{"k": s["k"], "fa": s["fa"], "default": s["default"]} for s in mod.params if s["kind"] == "text"]


def preview_spec(spec):
    """بررسی توان موتور قبل از کامپایل: قابل اجرا / تقریبی / غیرقابل اجرا / بدون ماژول آماده."""
    _ensure_catalog()
    from ai import _static_limits
    out = {"ok": [], "approx": [], "engine_limit": [], "catalog_missing": [], "features": []}
    spec = validate_spec(spec)
    prompt_text = json.dumps([f.get("note") or f.get("type") for f in spec["features"]], ensure_ascii=False)
    limits = _static_limits(prompt_text + " " + (spec.get("name") or ""))
    for f in spec["features"]:
        mod = MODULES[f["type"]]
        out["ok"].append({"id": f["type"], "fa": mod.fa})
        out["features"].append({"id": f["type"], "fa": mod.fa, "desc": mod.desc,
                                "params": [{k: v for k, v in s.items() if k in ("k", "fa", "kind", "default")} for s in mod.params]})
    for l in limits:
        out["engine_limit"].append({"want": l.get("want"), "why": l.get("why"), "upgrade": l.get("upgrade")})
    return out


# ───────────────────────── تولید Spec با مدل (یک فراخوانی) ─────────────────────────
def spec_prompt(prompt_text, current_summary="", lang="fa"):
    """پرامپت کوچک و قراردادی: مدل فقط قابلیت‌ها و پارامترها را از کاتالوگ انتخاب می‌کند."""
    from modules import catalog
    import caps as _caps
    lines = ["-" * 60]
    for m in catalog():
        ps = ", ".join(f"{s['k']}({s['kind']})" for s in m["params"]) or "بدون پارامتر"
        lines.append(f"type={m['id']} | {m['fa']} | نیازها: {','.join(m['requires']) or 'هیچ'} | پارامترها: {ps}")
    cats = "\n".join(lines)
    ask = ("فقط و فقط همین قابلیت‌ها از کاتالوگ قابل انتخاب‌اند. قابلیت خارج از کاتالوگ انتخاب ممنوع."
           " برای خواسته‌های خارج از کاتالوگ، نزدیک‌ترین قابلیت را انتخاب کن و در note بنویس چه چیز قابل پیاده‌سازی نیست.")
    cur = f"\nوضعیت پروژهٔ فعلی (فقط برای intent=edit):\n{current_summary[:900]}\n" if current_summary else ""
    sys_part = (
        "تو برنامه‌ریز ربات‌ساز هستی. کارت: درخواست کاربر را بخوان و یک Spec JSON کوچک بساز. "
        + ask +
        "\n\nکاتالوگ قابلیت‌ها:\n" + cats +
        "\n\nقالب خروجی (فقط JSON، بدون هیچ متن دیگری):\n"
        '{"version": 1, "intent": "create", "name": "نام کوتاه ربات", "emoji": false, "payments": false,'
        ' "features": [{"type": "شناسه از کاتالوگ", "params": {"کلید": مقدار}, "note": "توضیح کوتاه اختیاری"}],'
        ' "texts": {"welcome": "متن خوش‌آمد", "success": "متن موفقیت", "fail": "متن شکست"}}\n'
        "قوانین: params فقط کلیدهای همان قابلیت. مقادیر متن فارسی ساده. عدد برای پارامتر عددی. "
        "ویژگی‌های وابسته (مثل کیف پول برای بازی‌های سکه‌ای) خودکار اضافه می‌شوند؛ لازم نیست تکرار کنی مگر کاربر خواسته."
        + cur
    )
    user_part = f"درخواست کاربر:\n{prompt_text[:6000]}"
    return [{"role": "system", "content": sys_part}, {"role": "user", "content": user_part}]


def parse_llm_spec(text):
    """پاسخ مدل → Spec اعتبارسنجی‌شده. خطا: SpecError."""
    from ai import _extract_json_object
    raw = _extract_json_object(str(text or ""))
    if not raw:
        raise SpecError("پاسخ مدل JSON نداشت")
    return validate_spec(raw)
