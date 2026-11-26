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
import copy

from modules import MODULES, BuildError, normalize_text, clean_params, _clean_text


def _norm_requirements(raw):
    """نرمال‌سازی نیازمندی‌ها با coverage.py (ایمپورت دیرهنگام برای پرهیز از چرخه)."""
    import coverage as _cov
    return _cov.norm_requirements(raw)

SPEC_VERSION = 1

# شناسه‌های استاندارد قابلیت‌ها در Spec ←→ شناسهٔ ماژول در کاتالوگ داخلی
ALIASES = {
    "game.quiz": "quiz",
    "game.wheel": "wheel",
    "bot.start_menu": "start_menu",
    # نام‌های نزدیک رایجِ مدل‌ها به ماژول‌های واقعی کاتالوگ (ترمیم قطعی نام؛ هیچ قابلیت تازه‌ای اضافه نمی‌شود)
    "start": "start_menu",
    "menu": "start_menu",
    "main_menu": "start_menu",
    "about_us": "about",
    "store": "shop",
    "market": "shop",
    "balance": "wallet",
    "coin_wallet": "wallet",
    "wallet_coins": "wallet",
    "daily_gift": "daily",
    "gift_daily": "daily",
    "daily_reward": "daily",
    "invite": "referral",
    "referrals": "referral",
    "ref": "referral",
    "ranking": "leaderboard",
    "rank": "leaderboard",
    "group_admin": "group_manager",
    "group_manage": "group_manager",
    "support_ticket": "support",
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


def _salvage_requirement_rows(reqs, salvaged):
    """قابلیت‌های خارج از کاتالوگ → ردیف نیازمندی صادقانهٔ catalog_missing (قطعی؛ بدون LLM).
    قاعده: هیچ خواسته‌ای به‌خاطر «نام قابلیت نادرستِ مدل» نباید کل ساخت را بشکند و هیچ خواسته‌ای هم بی‌صدا حذف نشود.
      • ردیف نیازمندی که همهٔ ادعاهایش قابلیت‌های خارج از کاتالوگ بود → catalog_missing صادقانه می‌شود.
      • برای قابلیت salvage‌شده که ردیف شناخته‌شده‌ای نداشت → ردیف تازه با want از note مدل ساخته می‌شود.
    خروجی: فهرست ردیف‌های تازه (reqs درجا هم اصلاح می‌شود)."""
    stypes = {s["type"] for s in salvaged if s.get("type") and s["type"] != "؟"}
    rows = []
    seen_ids = {r.get("id") for r in reqs}
    if stypes:
        for r in reqs:
            if r.get("status") != "covered":
                continue
            claimed = {str(x) for x in (r.get("features") or [])}
            if claimed and claimed <= stypes:
                r["status"] = "catalog_missing"
                r["why"] = r.get("why") or (
                    "قابلیت‌های «" + "، ".join(sorted(claimed)) + "» در کاتالوگ ربات‌ساز وجود ندارند؛ "
                    "این خواسته در خروجی اجرا نمی‌شود و صادقانه ثبت شد.")
                r["features"] = []
    n = 0
    for s in salvaged:
        ftype = s.get("type") or "؟"
        linked = [rid for rid in (s.get("req") or []) if rid in seen_ids]
        if linked and any(r.get("id") in linked and r.get("status") == "catalog_missing" for r in reqs):
            continue          # خواستهٔ همین قابلیت از قبل به‌صورت صادقانه ثبت شده است
        want = s.get("note") or f"قابلیت «{ftype}»"
        if any(r.get("want") == want for r in reqs):
            continue
        n += 1
        rid = f"s{n}"
        while rid in seen_ids:
            n += 1
            rid = f"s{n}"
        seen_ids.add(rid)
        rows.append({"id": rid, "want": want, "part": "—", "status": "catalog_missing",
                     "features": [],
                     "why": f"قابلیت «{ftype}» در کاتالوگ ربات‌ساز وجود ندارد؛ به‌جای رد کل درخواست، "
                            "این خواسته صادقانه ثبت شد و در خروجی اجرا نمی‌شود.",
                     "upgrade": "", "source": "salvage"})
    return rows


def validate_spec(obj, require_requirements=False, expected_intent=None, request_context=""):
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
    # Validation and normalization must not mutate caller-owned LLM payloads.
    # The same decoded response may be evaluated under different request contexts
    # (retry, checkpoint restore, unit tests); leaking reconciled links/statuses
    # from one pass into the next can falsely mark unrelated requirements covered.
    obj = copy.deepcopy(obj)
    errors = []

    # 1) ساختار کلی
    if set(obj) - {"version", "intent", "name", "emoji", "payments", "features", "texts", "requirements"}:
        errors.append("کلیدهای ناشناخته در Spec؛ فقط version/intent/name/emoji/payments/features/texts/requirements مجاز است")
        obj = {k: v for k, v in obj.items() if k in ("version", "intent", "name", "emoji", "payments", "features", "texts", "requirements")}

    # 2) نسخه و نیت
    # نسخهٔ Spec بخشی از قرارداد داخلی برنامه است، نه یک نیازمندی معنایی که
    # مدل باید دقیقاً serialize کند. مدل‌های مختلف ممکن است 1، 1.0، "1"،
    # "v1" یا حتی متن توضیحی برگردانند. هیچ‌یک نباید یک Spec سالم را رد کند.
    # پس از بررسی سایر فیلدهای واقعی، نسخه را همیشه به نسخهٔ جاری نرمال می‌کنیم.
    # این کار اعتبارسنجی features/requirements/params را تضعیف نمی‌کند.
    obj["version"] = SPEC_VERSION
    model_intent = str(obj.get("intent") or "").strip().lower()
    # Operation mode is owned by the application, not the LLM. When a current
    # bot document is supplied, the save path is an edit/merge; when no current
    # bot exists, it is a create. A model interpreting the user's verb «بساز»
    # as create must not invalidate an otherwise correct edit Spec.
    if expected_intent in ("create", "edit"):
        intent = expected_intent
    else:
        intent = model_intent if model_intent in ("create", "edit") else "create"
    obj["intent"] = intent

    # 3) نام ربات
    name = _clean_text(obj.get("name") or "", 30)
    obj["name"] = name or "ربات من"

    # 4) قابلیت‌ها: Enum + پارامترها
    feats = obj.get("features")
    if feats is None and require_requirements and isinstance(obj.get("requirements"), list):
        # Some models express the requirement-to-module relation only on each
        # requirement and omit the top-level feature array. Recover it below from
        # the canonical catalogue before deciding that the Spec is incomplete.
        feats = []
    if not isinstance(feats, list):
        raise SpecError("فهرست قابلیت‌ها نامعتبر است", ["features باید فهرست JSON باشد"])
    if len(feats) > 12:
        raise SpecError("تعداد قابلیت‌های Spec بیش از حد است", ["حداکثر ۱۲ قابلیت در یک ساخت مجاز است؛ هیچ قابلیتی نباید بی‌صدا حذف شود"])
    out_feats, seen, salvaged = [], [], []
    for f in feats:
        if not isinstance(f, dict):
            errors.append("هر قابلیت باید شیء JSON باشد")
            continue
        t = _feature_type(f.get("type"))
        if not t:
            # ترمیم قطعی: قابلیت خارج از کاتالوگ کل Spec را نمی‌شکند؛ خواستهٔ آن صادقانه catalog_missing می‌شود.
            # (ریشهٔ واقعی «هیچ مدلی پاسخ معتبری نداد»: مدل قابلیتی می‌ساخت که در کاتالوگ نیست و کل خروجی رد می‌شد)
            raw_unknown_type = str(f.get("type") or "؟").strip()
            raw_unknown_req = [str(x).strip() for x in (f.get("req") if isinstance(f.get("req"), list) else [])
                               if str(x).strip()]
            if len(raw_unknown_type) > 40 or any(len(x) > 20 for x in raw_unknown_req) or len(raw_unknown_req) > 6:
                errors.append("شناسه یا تعداد پیوندهای قابلیت ناشناخته از محدوده مجاز خارج است؛ هیچ مقداری بی‌صدا کوتاه یا حذف نمی‌شود")
                continue
            salvaged.append({
                "type": raw_unknown_type,
                "note": _clean_text(f.get("note") or "", 300),
                "req": raw_unknown_req,
            })
            continue
        mod = MODULES[t]
        allowed = _allowed_param_keys(mod)
        raw_params = f.get("params", {})
        if raw_params is None:
            raw_params = {}
        if not isinstance(raw_params, dict):
            errors.append(f"پارامترهای {t} باید شیء JSON باشد")
            params = {}
        else:
            params = raw_params
        extra = set(params) - allowed
        if extra:
            # Unknown optional keys from weaker LLMs are dropped deterministically;
            # they must never reach the compiler, but should not invalidate an otherwise
            # complete and valid Spec. Requirement coverage still decides whether intent is met.
            params = {k: v for k, v in params.items() if k in allowed}
        # نیازمندی‌های متصل به این قابلیت (ردیابی تا خروجی) + note صادقانهٔ مدل حفظ می‌شود
        raw_f_reqs = f.get("req") if isinstance(f.get("req"), list) else []
        f_reqs = [str(x).strip() for x in raw_f_reqs if str(x).strip()]
        if any(len(x) > 20 for x in f_reqs):
            errors.append(f"شناسه نیازمندی متصل به قابلیت {t} بیش از ۲۰ نویسه است")
        if len(f_reqs) > 6:
            errors.append(f"تعداد نیازمندی‌های متصل به قابلیت {t} بیش از ۶ است؛ هیچ پیوندی بی‌صدا حذف نمی‌شود")
        f_note = _clean_text(f.get("note") or "", 300)
        out_feats.append({"type": t, "params": params, "req": f_reqs, "note": f_note})
        if t in seen and t not in ("start_menu",):
            dup = out_feats.pop()
            kept = next(x for x in out_feats if x["type"] == t)
            if params != kept.get("params"):
                errors.append(f"قابلیت {t} دوبار با تنظیمات متفاوت درخواست شده، اما کامپایلر فعلی فقط یک نمونه از این ماژول را پشتیبانی می‌کند")
            kept["req"] = list(dict.fromkeys(kept["req"] + dup["req"]))[:6]
        seen.append(t)
    if not out_feats:
        # A requirement-complete Spec may legitimately contain no ready modules when
        # every requested behavior is unavailable. Let coverage/preflight report this
        # honestly; do not discard the model's gap explanation at the schema stage.
        raw_requirements = obj.get("requirements")
        if not (require_requirements and isinstance(raw_requirements, list) and raw_requirements):
            if salvaged:
                errors.append("هیچ قابلیت آماده‌ای انتخاب نشده؛ خواسته‌های پشتیبانی‌نشده باید به‌صورت نیازمندی مستقل ثبت شوند")
            raise SpecError("هیچ قابلیت آماده و قابل کامپایل در Spec نبود", errors)

    # 5) وابستگی‌ها: قابلیت‌های لازم خودکار و بی‌صدا اضافه می‌شوند (رفع قطعی، نه خطا)
    chosen = [f["type"] for f in out_feats]
    need = []
    for t in chosen:
        for r in MODULES[t].requires:
            if r not in chosen and r not in need:
                need.append(r)
    for r in need:
        out_feats.append({"type": r, "params": {}, "req": [], "note": ""})
    obj["features"] = out_feats

    # 5.5) نیازمندی‌ها (Requirement Coverage): نرمال‌سازی + سازگاری با قابلیت‌های انتخابی
    reqs_raw = obj.get("requirements")
    if isinstance(reqs_raw, list) and reqs_raw:
        reqs, req_errs = _norm_requirements(reqs_raw)
        errors += req_errs
    else:
        reqs = None
        if require_requirements:
            errors.append("Spec مدل باید requirements کامل داشته باشد؛ حذف نیازمندی‌های درخواست مجاز نیست")
    # پیوندهای req به نیازمندی ناموجود: ترمیم قطعی بی‌صدا (حذف پیوند)؛ شکاندن کل Spec کارکرد ندارد
    if reqs is not None:
        valid_rids = {x["id"] for x in reqs}
        for r in reqs:
            normalized = []
            for raw_id in r.get("features") or []:
                canon = _feature_type(raw_id)
                normalized.append(canon or raw_id)
            r["features"] = list(dict.fromkeys(normalized))
        for f in out_feats:
            unknown_links = [rid for rid in f["req"] if rid not in valid_rids]
            if unknown_links:
                errors.append(f"قابلیت {f['type']} به شناسه نیازمندی ناموجود وصل شده: {', '.join(unknown_links[:4])}")
            f["req"] = [rid for rid in f["req"] if rid in valid_rids]
    # Reconcile before enforcing bidirectional feature links. This ordering is
    # essential: previously a Spec with a valid requirement but an omitted/missing
    # feature link was rejected here, so the later catalog reconciliation in
    # ask_spec() never got a chance to recover an already-registered module.
    if reqs is not None:
        try:
            import coverage as _coverage
            repairable = {"features": out_feats, "requirements": reqs}
            _coverage.reconcile_spec(repairable, request_context)
            out_feats = repairable.get("features") or out_feats
            reqs = repairable.get("requirements") or reqs
        except Exception:
            # Recovery is best-effort. It must never hide schema or compiler errors;
            # the normal coverage gate will classify remaining requirements.
            pass

        # Re-run transitive dependency closure after recovery: a module recovered
        # from a requirement must receive the same dependencies as a model-selected
        # module before it reaches the compiler.
        chosen_after_recovery = {f["type"] for f in out_feats}
        changed = True
        while changed:
            changed = False
            for mid in list(chosen_after_recovery):
                for dep in MODULES[mid].requires:
                    if dep not in chosen_after_recovery:
                        out_feats.append({"type": dep, "params": {}, "req": [], "note": ""})
                        chosen_after_recovery.add(dep)
                        changed = True

    selected = {f["type"] for f in out_feats}
    backref = {}
    for f in out_feats:
        for rid in f["req"]:
            backref.setdefault(rid, []).append(f["type"])
    if reqs is None:
        # Spec بدون نیازمندی (روتر/قالب/مدل قدیمی): هر قابلیت = یک نیازمندی قابل‌ردیابی
        reqs = [{"id": f"r{i}", "want": f"فعال‌سازی قابلیت «{MODULES[t].fa}»", "part": "منوی اصلی ربات",
                 "status": "covered", "features": [t], "why": "", "upgrade": "", "source": "auto"}
                for i, t in enumerate(dict.fromkeys(selected), 1)]
    # 5.6) salvage: قابلیت‌های خارج از کاتالوگ → ردیف نیازمندی صادقانهٔ catalog_missing (ترمیم قطعی؛ بدون شکستن Spec)
    reqs += _salvage_requirement_rows(reqs, salvaged)
    for r in reqs:
        mapped = set(r.get("features") or []) | set(backref.get(r["id"]) or [])
        if r["status"] == "covered":
            hit = mapped & selected
            if not hit:
                # Do not turn a missing feature link into a fatal Spec parse error.
                # A parseable Spec must reach deterministic coverage classification:
                # it can recover an existing module, retry a BUILD_DEFECT, or ask the
                # user to review a genuine CATALOG_MISSING item. It can never be built
                # as covered without a selected executable module.
                r["status"] = "catalog_missing"
                r["why"] = (r.get("why") or
                    "مدل این نیازمندی را پوشش‌داده‌شده اعلام کرده بود، اما هیچ قابلیت اجرایی به آن متصل نشده است؛ پوشش باید توسط کاتالوگ و اعتبارسنجی قطعی تعیین شود.")
                r["features"] = []
            else:
                r["features"] = sorted(hit)
        else:
            r["features"] = sorted(mapped & selected)
    obj["requirements"] = reqs

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
    """خروجی روتر قطعی (PlanResult) → Spec؛ بدون هیچ فراخوانی مدل.
    نیازمندی‌ها از کلیدواژه‌های واقعاً منطبق در درخواست ساخته می‌شوند تا ردیابی «خواسته ← قابلیت» قطعی باشد."""
    from modules import MODULES as _M
    feats = [{"type": i, "params": p} for i, p in pr.items]
    reqs = []
    for i, (mid, _p) in enumerate(pr.items, 1):
        hit = "، ".join((getattr(pr, "matched", None) or {}).get(mid) or [])[:80]
        fa = _M[mid].fa if mid in _M else mid
        reqs.append({"id": f"r{i}",
                     "want": (f"«{hit}» — " if hit else "") + f"فعال‌سازی قابلیت «{fa}»",
                     "part": "منوی اصلی ربات", "status": "covered", "features": [mid],
                     "why": "", "upgrade": "", "source": "router"})
    return {"version": SPEC_VERSION, "intent": "create", "name": pr.name or "ربات من",
            "emoji": bool(pr.emoji), "payments": bool(pr.payments), "features": feats,
            "texts": {}, "requirements": reqs}


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
    """Build a requirement-complete prompt against the actual registered catalog."""
    from modules import catalog
    from caps import CAPS_CONTRACT
    lines = ["-" * 60]
    for m in catalog():
        ps = ", ".join(f"{s['k']}({s['kind']}, پیش‌فرض={str(s['default'])[:60]})" for s in m["params"]) or "بدون پارامتر"
        aliases = "، ".join(m.get("aliases") or []) or "—"
        lines.append(f"type={m['id']} | نام={m['fa']} | شرح رفتار واقعی={m['desc']} | عبارت‌های معادل درخواست={aliases} | دسته={m['cat']} | وابستگی={','.join(m['requires']) or 'هیچ'} | پارامترها={ps}")
    cats = "\n".join(lines)
    engine_only = [f"{c.get('id')} | {c.get('title')} | status={c.get('status')} | limits={'; '.join(map(str, c.get('limits') or []))[:180]}"
                   for c in CAPS_CONTRACT.values() if c.get("status") in ("engine_only", "unsupported")]
    engine_knowledge = "\n".join(engine_only[:40]) or "—"
    editing = bool(current_summary)
    intent = "edit" if editing else "create"
    ask = (
        "فقط قابلیت‌های ثبت‌شده در کاتالوگ زیر قابل انتخاب‌اند. قابلیت خارج از کاتالوگ را در features جعل نکن.\n"
        "درخواست را به کوچک‌ترین نیازمندی‌های مستقل و قابل مشاهده برای کاربر تفکیک کن؛ هر رفتار، مقصد، شرط، ورودی و خروجی خواسته‌شده باید ردیف جداگانه داشته باشد.\n"
        "فیلد part فقط محل قرارگیری/اجرای قابلیت (مثلاً منوی شروع یا پیوی) است و به‌تنهایی یک قابلیت نیست؛ انتخاب ماژول باید از روی want انجام شود.\n"
        "هر نیازمندی باید دقیقاً به قابلیت‌هایی متصل شود که شرح رفتار واقعی آن‌ها همان نیازمندی را اجرا می‌کند. شباهت کلی موضوع کافی نیست.\n"
        "قابلیت عمومی مانند منوی شروع، درباره ما، لینک، پشتیبانی و FAQ را فقط وقتی انتخاب کن که کاربر همان قابلیت را خواسته باشد؛ هرگز آن را جایگزین رفتار تخصصی نکن.\n"
        "اگر قابلیت موجود در کاتالوگ دقیقاً مرتبط است، آن را انتخاب کن؛ حتی اگر نام کاربر با نام ماژول متفاوت باشد. اگر هیچ ماژول مرتبطی نیست، catalog_missing ثبت کن. ENGINE_LIMIT فقط وقتی مجاز است که در اطلاعات توانایی موتور، عدم پشتیبانی صریح ثبت شده باشد.\n"
        "برای status=covered، دست‌کم یک feature مرتبط لازم است و همان feature باید با req به شناسه نیازمندی وصل شود. برای catalog_missing/engine_limit، features خالی باشد.\n"
    )
    if editing:
        ask += ("این درخواست ویرایش/توسعهٔ ربات موجود است، نه ساخت دوبارهٔ آن. فقط قابلیت‌هایی را در features بیاور که همین درخواست می‌خواهد اضافه یا توسعه دهد؛ ")
        ask += ("قابلیت‌های موجود در خلاصه، زمینه و محدودیت نام‌گذاری هستند و نباید دوباره بی‌دلیل تولید شوند. شناسه‌ها و رفتارهای موجود را حفظ کن.\n")
    cur = f"\nوضعیت ساختاری ربات فعلی (مرجع الزامی برای intent=edit):\n{current_summary[:6000]}\n" if editing else ""
    sys_part = (
        "تو معمار و برنامه‌ریز ربات تلگرام هستی. فقط Spec JSON معتبر تولید کن؛ کد یا کانفیگ موتور ننویس.\n" + ask +
        "\nکاتالوگ ماژول‌های آماده و قابل تولید:\n" + cats +
        "\n\nدانش قراردادی موتور درباره توانایی‌های بدون ماژول آماده:\n" + engine_knowledge +
        "\nقاعده وضعیت: ready یعنی ماژول آماده؛ engine_only یعنی موتور primitive دارد اما ماژول آماده ندارد (catalog_missing)؛ unsupported فقط یعنی موتور صریحاً پشتیبانی نمی‌کند (engine_limit).\n"
        "\nنسخهٔ Spec را تولید نکن؛ این فیلد را حذف کن چون برنامه آن را هنگام اعتبارسنجی تنظیم می‌کند.\n"
        "\nقالب خروجی (فقط JSON):\n" +
        '{"intent":"' + intent + '","name":"نام کوتاه ربات","emoji":false,"payments":false,'
        '"requirements":[{"id":"r1","want":"رفتار دقیق موردنظر کاربر","part":"محل/بخش","status":"covered","features":["شناسه واقعی قابلیت"]}],'
        '"features":[{"type":"شناسه واقعی کاتالوگ","params":{},"req":["r1"],"note":""}],'
        '"texts":{}}\n'
        "قوانین اجباری:\n"
        "1) تعداد requirements با تعداد خواسته‌های مستقل کاربر برابر باشد؛ هیچ خواسته‌ای حذف، ادغام مبهم یا خلاصه نشود.\n"
        "2) `want` باید رفتار قابل اجرا را توصیف کند، نه نام کلی مثل «ربات حرفه‌ای».\n"
        "3) اگر یک جمله چند کار مستقل می‌خواهد، آن را به چند requirement تفکیک کن.\n"
        "4) هر feature فقط به requirementهایی وصل شود که واقعاً همان feature اجرا می‌کند.\n"
        "5) برای هر قابلیت، پارامترهای لازم را از متن درخواست استخراج کن؛ مقدار ساختگی یا محتوای نمونه را به‌عنوان داده واقعی کاربر نساز.\n"
        "6) بخش/منوی عمومی یا قالب پیش‌فرض را برای پرکردن خروجی اضافه نکن، مگر برای شروع فنی لازم باشد؛ شروع فنی نباید به‌عنوان پوشش نیازمندی شمرده شود.\n"
        "7) قابلیت موجود را به اشتباه catalog_missing اعلام نکن؛ ابتدا شناسه‌ها، نام فارسی، شرح و رفتار کاتالوگ را تطبیق بده.\n"
        "8) برای هر بخش ناموجود، دلیل مشخص و راهکار واقعی بده؛ از عبارت‌های کلی خودداری کن.\n"
        + cur
    )
    user_part = f"درخواست کاربر (متن کامل و مرجع اصلی):\n{str(prompt_text or '')[:6000]}"
    return [{"role": "system", "content": sys_part}, {"role": "user", "content": user_part}]


def parse_llm_spec(text, require_requirements=False, expected_intent=None, request_context=""):
    """پاسخ مدل → Spec اعتبارسنجی‌شده. در مسیر AI، requirements و intent اجباری‌اند."""
    from ai import _extract_json_object
    raw = _extract_json_object(str(text or ""))
    if not raw:
        raise SpecError("پاسخ مدل JSON نداشت")
    return validate_spec(raw, require_requirements=require_requirements, expected_intent=expected_intent,
                         request_context=request_context)
