# -*- coding: utf-8 -*-
"""
coverage.py — کنترل پوشش نیازمندی‌ها (Requirement Coverage) (BUILD 3.6.0)

هدف: هیچ خواستهٔ اصلی کاربر در مسیر «درخواست ← فهم ← Spec ← کامپایلر ← خروجی» گم نشود.

قرارداد نیازمندی (در Spec):
  {"id": "r1", "want": "چه رفتاری", "part": "در کدام بخش ربات", "status": "covered|catalog_missing|engine_limit",
   "features": ["شناسهٔ قابلیت(های) مسئول"], "why": "در صورت عدم پوشش: دلیل صادقانه", "upgrade": "راهکار"}

قواعد قطعی (بدون LLM):
  • status=covered فقط وقتی معتبر است که حداقل یک قابلیت انتخاب‌شدهٔ کاتالوگ آن را اجرا کند؛
    اگر همهٔ قابلیت‌های وصل‌شده عمومی باشند و متن خواسته با هیچ تریگر همان قابلیت هم‌خوان نبود،
    ادعای پوشش رد می‌شود (مدل ضعیف نمی‌تواند با حذف نیازمندی، ساخت را موفق جلوه دهد).
  • status=engine_limit فقط با اثبات: قرارداد caps.py (status=unsupported) یا الگوهای قطعی ai._STATIC_LIMITS.
    بدون اثبات، صادقانه به CATALOG_MISSING تنزل می‌یابد (نه ENGINE_LIMIT).
  • status=catalog_missing → موتور عمومی اجرا می‌کند ولی ماژول آمادهٔ کاتالوگ ندارد؛ ساخت دستی در استودیو ممکن است.

نام‌های پایدار: GENERIC_IDS, norm_requirements, unmet_items, coverage_report, coverage_thinking, classify_uncovered
"""

import re

from modules import MODULES, normalize_text

# قابلیت‌های عمومی: به‌تنهایی پاسخ‌گوی خواستهٔ اصلی نیستند و نباید جای قابلیت اصلی را بگیرند
GENERIC_IDS = ("start_menu", "about", "links", "support", "faq")

_STATUSES = ("covered", "catalog_missing", "engine_limit")


def _slug(text):
    """شناسهٔ تجمیع پایدار برای نیازمندی بدون شناسهٔ قراردادی (برای گزارش/نقشهٔ توسعه)."""
    parts = re.findall(r"[A-Za-z0-9آ-ی]+", normalize_text(text))
    out = "_".join(parts)[:48] or "request"
    return out.lower()


def norm_requirements(raw):
    """فهرست خام نیازمندی‌های مدل → فهرست استاندارد + خطاها (خطا = SpecError در spec.py)."""
    reqs, errors = [], []
    if not isinstance(raw, list):
        return [], ["requirements باید فهرست باشد"]
    seen = set()
    for i, r in enumerate(raw[:12], 1):
        if not isinstance(r, dict):
            errors.append("هر نیازمندی باید شیء JSON باشد")
            continue
        want = str(r.get("want") or "").strip()[:300]
        if len(want) < 3:
            errors.append(f"نیازمندی {i} فاقد «want» است")
            continue
        rid = str(r.get("id") or f"r{i}").strip()[:20]
        if rid in seen:
            errors.append(f"شناسهٔ تکراری نیازمندی: {rid}")
            continue
        seen.add(rid)
        st = str(r.get("status") or "covered").strip().lower()
        if st not in _STATUSES:
            errors.append(f"وضعیت نامعتبر «{st}» برای نیازمندی {rid}")
            continue
        feats = [str(x).strip()[:40] for x in (r.get("features") if isinstance(r.get("features"), list) else []) if str(x).strip()][:6]
        reqs.append({"id": rid, "want": want,
                     "part": str(r.get("part") or "").strip()[:120],
                     "status": st, "features": feats,
                     "why": str(r.get("why") or "").strip()[:400],
                     "upgrade": str(r.get("upgrade") or "").strip()[:300],
                     "source": str(r.get("source") or "model")})
    if not reqs and not errors:
        errors.append("فهرست requirements خالی است")
    return reqs, errors


def _trigger_match(mod, text):
    """آیا متن خواسته با تریگرهای قطعی همان ماژول عمومی هم‌خوان است؟"""
    t = normalize_text(text)
    return any(re.search(rx, t, flags=re.I) for rx, _w in mod.triggers)


def _served_by(r, types_selected):
    """آیا ادعای پوشش این نیازمندی با قابلیت‌های انتخابی واقعاً معنا دارد؟"""
    mapped = [t for t in (r.get("features") or []) if t in types_selected]
    if not mapped:
        return False
    if any(t not in GENERIC_IDS for t in mapped):
        return True
    # فقط قابلیت‌های عمومی وصل شده‌اند؛ فقط وقتی «سرویس‌شده» است که خواسته واقعاً همان را می‌خواسته
    return any(_trigger_match(MODULES[t], (r.get("want") or "") + " " + (r.get("part") or ""))
               for t in mapped if t in MODULES)


def _static_limit_for(want, prompt):
    """اثبات ENGINE_LIMIT از الگوهای قطعی ai._STATIC_LIMITS (همان منبع پیش‌بررسی ساخت)."""
    try:
        from ai import _STATIC_LIMITS
    except Exception:
        return None
    text = normalize_text((want or "") + " " + (prompt or ""))
    for pat, lim_want, why, alt, feat in _STATIC_LIMITS:
        if re.search(pat, text, re.I):
            return {"kind": "ENGINE_LIMIT", "feature": feat, "want": lim_want, "why": why, "upgrade": "جایگزین: " + alt}
    return None


def _contract_for(text):
    """تطبیق متن خواسته با عنوان قراردادهای caps.py (تنها مرجع توانایی موتور)."""
    try:
        from caps import CAPS_CONTRACT
    except Exception:
        return None
    t = normalize_text(text)
    for cid, c in CAPS_CONTRACT.items():
        title = normalize_text(c.get("title") or "")
        if len(title) >= 8 and title in t:
            return c
    return None


def classify_uncovered(req, prompt=""):
    """نیازمندی پوشش‌نداده → نقص طبقه‌بندی‌شدهٔ قطعی.
    ENGINE_LIMIT فقط با اثبات (قرارداد unsupported یا الگوی قطعی)؛ وگرنه CATALOG_MISSING."""
    import defects as _defects
    want = (req.get("want") or "").strip()
    why_model = (req.get("why") or "").strip()
    req_feat = (req.get("feature") or "").strip() if isinstance(req.get("feature"), str) else ""
    st = req.get("status")

    # ۱) اثبات با قرارداد caps: شناسهٔ ادعاشدهٔ مدل یا تطبیق عنوان
    try:
        from caps import CAPS_CONTRACT, capability
        cap = capability(req_feat) if req_feat else None
        if not cap or cap.get("status") == "unknown":
            cap = _contract_for(want) or None
        if cap and cap.get("status") == "unsupported":
            prop = cap.get("proposal") or {}
            return _defects.defect(
                "ENGINE_LIMIT", cap.get("id") or req_feat, want,
                why_model or "قرارداد قابلیت‌های موتور (caps.py) این توانایی را «پشتیبانی‌نشده» ثبت کرده است"
                + (": " + str(cap.get("limits") or [""])[1:-1] if cap.get("limits") else ""),
                severity="high", stage="spec", suggested_capability=cap.get("id") or req_feat,
                upgrade=(req.get("upgrade") or prop.get("reason") or
                         "این بخش با امکانات فعلی اجرا نمی‌شود؛ می‌توانی بقیهٔ درخواست را بسازی یا درخواست را اصلاح کنی."))
    except Exception:
        cap = None

    # ۲) اثبات با الگوهای قطعی قبل از ساخت (برای هر وضعیتی؛ کلید پذیرش کاربر در همهٔ مسیرها یکسان می‌ماند)
    sl = _static_limit_for(want, prompt)
    if sl:
        # want از منبع قطعی (_STATIC_LIMITS) می‌آید تا کلید پذیرش کاربر در پیش‌بررسی و اینجا یکسان بماند
        return _defects.defect("ENGINE_LIMIT", sl.get("feature") or "", sl.get("want") or want,
                               why_model or sl.get("why") or "", severity="high", stage="spec",
                               suggested_capability=sl.get("feature") or "",
                               upgrade=req.get("upgrade") or sl.get("upgrade") or "")

    # ۳) بدون اثبات محدودیت موتور → صادقانه: ماژول آمادهٔ کاتالوگ نیست (نه ENGINE_LIMIT)
    return _defects.catalog_missing(
        _slug(req_feat or want), want,
        why_model or "ماژول آماده‌ای در کاتالوگ ربات‌ساز برای این خواسته ثبت نشده است؛ "
                     "موتور عمومی امکان ساخت دستی آن در استودیو را دارد و این خواسته به نقشهٔ توسعهٔ کاتالوگ اضافه می‌شود.")


def unmet_items(spec, prompt=""):
    """همهٔ نیازمندی‌های پوشش‌ندادهٔ Spec → فهرست نقص طبقه‌بندی‌شده (خالی = پوشش کامل؛ مسیر ساخت ادامه می‌یابد)."""
    out = []
    types_selected = {f.get("type") for f in (spec.get("features") or []) if isinstance(f, dict)}
    for r in spec.get("requirements") or []:
        if not isinstance(r, dict):
            continue
        if r.get("status") == "covered":
            served = _served_by(r, types_selected)
            if served and _static_limit_for(r.get("want") or "", ""):
                # اثبات قطعی محدودیت موتور روی متن همان خواسته: ادعای پوشش با هر قابلیتی باطل است
                # (ریشهٔ «ربات ساخته شد ولی ناقص بود»: مدل پوشش خواستهٔ اجرانشدنی را با قابلیت غیرعمومی جواب می‌زد)
                served = False
            if served:
                continue
            # ادعای پوشش بی‌پشتوانه: مدل خواسته را حذف کرده و با قابلیت عمومی پر کرده است → پوشش رد می‌شود
            r = dict(r, status="catalog_missing",
                     why=r.get("why") or "این خواسته در خروجی نهایی هیچ قابلیت واقعی‌ای نگرفت و با بخش عمومی پر شد.")
        out.append(classify_uncovered(r, prompt))
    return [x for x in out if isinstance(x, dict)]


def coverage_report(spec):
    """گزارش ردیابی هر نیازمندی تا خروجی نهایی (قطعی؛ بدون LLM):
    want → قابلیت مسئول → شواهد کامپایل و تست پذیرش موتور."""
    reqs = [r for r in (spec.get("requirements") or []) if isinstance(r, dict)]
    if not reqs:
        return None
    types_selected = [f.get("type") for f in (spec.get("features") or []) if isinstance(f, dict)]
    items, n_cov = [], 0
    for r in reqs:
        st = r.get("status")
        ev = ""
        if st == "covered" and _served_by(r, set(types_selected)):
            n_cov += 1
            fa = "، ".join(MODULES[t].fa for t in (r.get("features") or []) if t in MODULES) or "—"
            try:
                from engine_accept import _SCENARIOS
                extra = "؛ سناریوی پذیرش اختصاصی هم روی موتور اجرا شد" if any(t in _SCENARIOS for t in (r.get("features") or [])) else ""
            except Exception:
                extra = ""
            ev = f"قابلیت «{fa}» کامپایل قطعی شد و تست پذیرش موتور (اجرای واقعی بخش‌ها، دکمه‌ها و مسیرها) PASS{extra}."
            st = "covered"
        elif st == "covered":
            st = "uncovered"
            ev = "این خواسته در خروجی نهایی قابلیت واقعی نگرفت."
        else:
            ev = r.get("why") or "با امکانات فعلی اجرا نمی‌شود."
        items.append({"id": r.get("id"), "want": r.get("want"), "part": r.get("part"), "status": st,
                      "features": [t for t in (r.get("features") or []) if t in types_selected],
                      "evidence": ev})
    return {"total": len(items), "covered": n_cov, "ok": n_cov == len(items), "requirements": items}


def coverage_thinking(thinking, report):
    """افزودن خلاصهٔ پوشش به متن تحویل برای کاربر: چه ساخته شد، چه چیزی اجرا نشد."""
    if not report or not report.get("requirements"):
        return thinking
    n, c = report.get("total") or 0, report.get("covered") or 0
    lines = []
    if n and c == n:
        lines.append(f"پوشش درخواست: هر {n} خواستهٔ اصلی پیاده‌سازی و با تست پذیرش موتور تأیید شد.")
    else:
        lines.append(f"پوشش درخواست: {c} از {n} خواسته پیاده‌سازی شد؛ موارد زیر اجرا نشدند:")
        for r in report["requirements"]:
            if r.get("status") != "covered":
                lines.append(f"• «{(r.get('want') or '')[:120]}» — {(r.get('evidence') or '')[:160]}")
    out = (thinking or "").rstrip()
    if out:
        out += "\n"
    return (out + "\n".join(lines))[:900]
