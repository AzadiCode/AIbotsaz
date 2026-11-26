# -*- coding: utf-8 -*-
"""
defects.py — طبقه‌بندی قطعی نقص‌ها و گزارش‌دهی ساخت‌یافته (BUILD 3.6.0)

سه وضعیت مستقل و جدا از هم:
  BUILD_DEFECT    → نقص در سیستم ساخت (متغیر تعریف‌نشده، route اشتباه، کامپایل نامعتبر، …)
                    این هرگز به کاربر به‌عنوان «محدودیت موتور» گزارش نمی‌شود.
  ENGINE_LIMIT    → موتور واقعاً توانایی اجرا را ندارد؛ فقط با بررسی کد/کاتالوگ (caps.py) اثبات می‌شود.
  CATALOG_MISSING → موتور توانایی دارد اما تولیدکنندهٔ آماده در کاتالوگ نیست؛ با ENGINE_LIMIT اشتباه گرفته نشود.

سازنده‌ها: DEFECT_KINDS, defect(), build_defect(), engine_limit(), catalog_missing(),
           DEFECTS_STAGE_FA, defects_report(), aggregate_key()
"""

# وضعیت‌های مستقل؛ رشته‌ها قرارداد ثابت گزارش‌ها هستند
DEFECT_KINDS = ("BUILD_DEFECT", "ENGINE_LIMIT", "CATALOG_MISSING")

# مراحل خط ساخت (برای گزارش ادمین)
DEFECTS_STAGE_FA = {
    "spec": "تولید/اعتبارسنجی Spec",
    "compile": "کامپایل قطعی",
    "sanitize": "اعتبارسنجی ساختاری",
    "lint": "بازرس منطقی",
    "acceptance_test": "تست پذیرش موتور",
    "save": "ذخیره نهایی",
    "model": "فراخوانی مدل زبانی",
}

_SEVERITIES = ("low", "medium", "high")


def defect(kind, feature="", want="", evidence="", severity="medium", stage="compile",
           suggested_capability="", acceptance_criteria=(), upgrade=""):
    """یک رکورد نقص استاندارد. kind باید یکی از DEFECT_KINDS باشد."""
    if kind not in DEFECT_KINDS:
        kind = "BUILD_DEFECT"
    return {
        "kind": kind,
        "feature": str(feature or "")[:60],
        "want": str(want or "")[:300],
        "evidence": str(evidence or "")[:600],
        "severity": severity if severity in _SEVERITIES else "medium",
        "stage": str(stage or "compile")[:40],
        "suggested_capability": str(suggested_capability or "")[:60],
        "acceptance_criteria": [str(x)[:200] for x in (acceptance_criteria or [])][:6],
        "upgrade": str(upgrade or "")[:600],
    }


def build_defect(feature, want, evidence, severity="high", stage="compile", suggested_capability="", acceptance_criteria=(), upgrade=""):
    """نقص داخلی خط ساخت؛ هرگز نباید به‌عنوان محدودیت موتور به کاربر گزارش شود."""
    return defect("BUILD_DEFECT", feature, want, evidence, severity, stage,
                  suggested_capability, acceptance_criteria, upgrade or "اصلاح تولیدکننده و اجرای مجدد تست")


def engine_limit(want, evidence, upgrade, feature=""):
    """محدودیت واقعی و اثبات‌شدهٔ موتور؛ فقط بر پایهٔ caps.py و بررسی کد."""
    return defect("ENGINE_LIMIT", feature, want, evidence, "high", "compile", "", (), upgrade)


def catalog_missing(feature, want, evidence="موتور این قابلیت را اجرا می‌کند اما ماژول آمادهٔ آن هنوز در کاتالوگ نیست."):
    """قابلیت با ماژول آماده؛ با ENGINE_LIMIT اشتباه گرفته نشود."""
    return defect("CATALOG_MISSING", feature, want, evidence, "low", "spec", feature,
                  ("پیاده‌سازی تولیدکنندهٔ قطعی", "ثبت در کاتالوگ", "تست پذیرش"),
                  "این قابلیت در نقشهٔ توسعهٔ کاتالوگ قرار می‌گیرد؛ فعلاً ساخت دستی در استودیو پشتیبانی می‌شود.")


def aggregate_key(d):
    """کلید تجمیع برای شناسایی مشکل‌های تکرارشونده (همان feature+kind+stage)."""
    return f"{d.get('kind')}|{d.get('feature')}|{d.get('stage')}"


def defects_report(defects, prompt="", bot_id="", job_id="", model="", provider="", tries=0):
    """گزارش کامل برای ادمین؛ متن کامل درخواست بدون حذف."""
    out = {
        "prompt": str(prompt or "")[:1500],
        "report_id": str(job_id or ""),
        "bot_id": str(bot_id or ""),
        "t": __import__("core").now().isoformat() if _core_ok() else "",
        "tries": int(tries or 0),
        "items": [],
    }
    if model:
        out["model"] = str(model)[:80]
        out["provider"] = str(provider)[:80]
    for d in defects or []:
        if not isinstance(d, dict):
            continue
        item = dict(d)
        item["stage_fa"] = DEFECTS_STAGE_FA.get(item.get("stage"), item.get("stage"))
        out["items"].append(item)
    return out


def _core_ok():
    try:
        import core  # noqa: F401
        return True
    except Exception:
        return False


def user_summary(defects):
    """خلاصهٔ فارسیِ ساده برای کاربر: چه ساخته شد، چه نه، جایگزین چیست، ادامه یا لغو."""
    lines = []
    for d in defects or []:
        k = d.get("kind")
        if k == "ENGINE_LIMIT":
            lines.append(("❌", f"{d.get('want') or ''} — موتور پشتیبانی نمی‌کند. {d.get('upgrade') or ''}"))
        elif k == "CATALOG_MISSING":
            lines.append(("🧩", f"{d.get('want') or ''} — موتور آن را اجرا می‌کند ولی ماژول آماده هنوز ساخته نشده؛ در استودیو دستی قابل ساخت است."))
        elif k == "BUILD_DEFECT":
            lines.append(("⚠️", "یک نقص داخلی در خط ساخت ثبت شد و خروجی تحویل داده نشد؛ هزینه‌ای کسر نشد."))
    return lines


KIND_FA = {
    "BUILD_DEFECT": "نقص خط ساخت",
    "ENGINE_LIMIT": "محدودیت موتور",
    "CATALOG_MISSING": "نبود ماژول آماده",
}


# ───────────────────────── تبدیل گزارش به نقشهٔ توسعه ─────────────────────────
def engine_roadmap(d, count=1):
    """ENGINE_LIMIT → پیشنهاد توسعهٔ قابل اجرا (بر اساس قرارداد caps.py).
    هر گزارش محدودیت موتور باید به یک مسیر فنی مشخص ختم شود؛ هیچ نقصی بدون نقشه باقی نمی‌ماند."""
    from caps import capability
    want = str(d.get("want") or "")
    cid = (d.get("feature") or d.get("suggested_capability") or "").strip()
    if not cid:
        # تطبیق با عنوان خواسته روی قراردادها
        seed = [x for x in __import__("caps").engine_roadmap_seed()
                if want and (want[:30] in x.get("title", "") or x.get("title", "")[:12] in want)]
        cid = seed[0]["capability"] if seed else ""
    c = capability(cid)
    prop = c.get("proposal") or {}
    return {
        "capability": c.get("id") or cid,
        "title": c.get("title") or want,
        "want": d.get("want"),
        "expected_behavior": d.get("want") or prop.get("behavior"),
        "reason": prop.get("reason") or d.get("evidence"),
        "missing_primitive": prop.get("missing", []),
        "files": prop.get("files", []),
        "api_needed": prop.get("api"),
        "engine_deps": prop.get("deps", []),
        "impact_existing": prop.get("impact", ""),
        "plan": prop.get("plan", []),
        "acceptance": prop.get("acceptance", []) or d.get("acceptance_criteria", []),
        "kind": "ENGINE_LIMIT",
        "request_count": int(count or 1),
        "priority": roadmap_priority(count),
        "source_report": d,
    }


def catalog_path(d):
    """CATALOG_MISSING → مسیر افزودن ماژول به کاتالوگ (توسعهٔ کاتالوگ، نه موتور).
    افزودن قابلیت جدید = قرارداد caps + Schema ماژول + تولیدکننده modlib + تست پذیرش؛ بدون بازنویسی ai.py."""
    return {
        "kind": "CATALOG_MISSING",
        "module": d.get("suggested_capability") or d.get("feature"),
        "want": d.get("want"),
        "steps": [
            "ثبت قرارداد قابلیت در caps.CAPS_CONTRACT با status=ready پس از تست",
            "تعریف ماژول در modlib._reg (params + compile + triggers + requires)",
            "نام‌گذاری فضای‌نام مستقل نودها/متغیرها (prefix ماژول)",
            "سناریوی تست پذیرش در engine_accept._SCENARIOS",
            "ثبت در tests/test_modules.py؛ فعال‌سازی status=ready فقط پس از PASS",
        ],
        "note": "موتور توانایی اجرا را دارد؛ فقط تولیدکنندهٔ آماده ساخته شود. کامپایلر و ai.py تغییری نمی‌خواهند.",
    }


def roadmap_priority(count):
    """اولویت بر اساس تعداد درخواست‌های مشابه: ۱ (کم) تا ۵ (بحرانی)."""
    try:
        n = int(count or 1)
    except (TypeError, ValueError):
        n = 1
    return max(1, min(5, 1 + n // 5))


def aggregate_defects(defects_list):
    """تجمیع بر اساس قابلیت و علت ریشه‌ای → فهرست (کلید، نوع، قابلیت، تعداد، نمونه)."""
    out = {}
    for d in defects_list or []:
        if not isinstance(d, dict):
            continue
        key = aggregate_key(d)
        root = (d.get("evidence") or d.get("why") or "")[:60]
        if key not in out:
            out[key] = {"key": key, "kind": d.get("kind"), "feature": d.get("feature"),
                        "root": root, "count": 0, "sample": d}
        out[key]["count"] += 1
    return sorted(out.values(), key=lambda x: -x["count"])


def roadmap_from_gaps(items):
    """گزارش‌های ثبت‌شده → (نقشه‌های توسعهٔ موتور، مسیرهای کاتالوگ، نقص‌های ساخت).
    اصل: هر درخواست ناموفق یا اصلاح خط ساخت است، یا افزودن کاتالوگ، یا نقشهٔ ارتقای موتور."""
    engine, catalog, build = [], [], []
    for d in items or []:
        if not isinstance(d, dict):
            continue
        k = d.get("kind")
        if k == "ENGINE_LIMIT":
            engine.append(engine_roadmap(d))
        elif k == "CATALOG_MISSING":
            catalog.append(catalog_path(d))
        else:
            build.append(d)
    return engine, catalog, build
