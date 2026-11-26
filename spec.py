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


def _salvage_requirement_rows(reqs, salvaged, selected_features=(), selected_req_links=()):
    """Never turn model-authored feature notes into user requirements.

    Unknown feature IDs are diagnostics about the model's proposed implementation.
    The only source of user intent is the explicit, source-grounded requirements
    array. A genuine unsupported user request must already exist there as a row.
    """
    return []


def _grounding_tokens(value):
    text = normalize_text(value).casefold()
    return re.findall(r"[a-z0-9_]+|[\u0600-\u06FF]+", text)


def _quote_is_grounded(quote, request):
    """Require a verbatim contiguous phrase from the user's original request."""
    q = _grounding_tokens(quote)
    source = _grounding_tokens(request)
    if not q or not source or len(q) > len(source):
        return False
    for i in range(len(source) - len(q) + 1):
        if source[i:i + len(q)] == q:
            return True
    return False


def validate_spec(obj, require_requirements=False, expected_intent=None, request_context="", require_grounded_quotes=False):
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
    dropped_requirement_ids = set()
    if isinstance(reqs_raw, list) and reqs_raw:
        reqs, req_errs = _norm_requirements(reqs_raw)
        errors += req_errs
        if require_grounded_quotes and request_context:
            quote_owner = {}
            grounded_reqs = []
            dropped_requirement_ids = set()
            import coverage as _coverage
            import logging as _logging
            _spec_log = _logging.getLogger("aibot")
            for req in reqs:
                quote = str(req.get("source_quote") or "").strip()
                rid = req.get("id")
                if not quote:
                    errors.append(f"نیازمندی {rid} فاقد source_quote است؛ هر خواسته باید به عبارت واقعی درخواست کاربر مستند باشد")
                    continue
                if not _quote_is_grounded(quote, request_context):
                    errors.append(f"source_quote نیازمندی {rid} در متن اصلی کاربر وجود ندارد؛ احتمالاً نیازمندی ساختگی یا جزئیات فنی تولیدشده توسط مدل است")
                    continue
                unsupported = _coverage.unsupported_technical_terms(req.get("want") or "", request_context)
                if unsupported:
                    # The user did not ask for these implementation details. Do not
                    # turn a model's explanation (database/connection/custom module)
                    # into a fake user requirement or let it poison an otherwise valid
                    # Spec. Drop only this contaminated row; its original source quote
                    # remains available to a separately grounded behavioral requirement.
                    _spec_log.warning(
                        "Dropped model-invented Spec requirement %s; unsupported technical terms=%s",
                        rid, unsupported)
                    dropped_requirement_ids.add(str(rid))
                    continue
                signature = " ".join(_grounding_tokens(quote))
                if signature in quote_owner:
                    errors.append(f"نیازمندی‌های {quote_owner[signature]} و {rid} از یک source_quote تکراری استفاده کرده‌اند؛ هر رفتار مستقل باید مستند جداگانه داشته باشد")
                else:
                    quote_owner[signature] = rid
                    grounded_reqs.append(req)
            reqs = grounded_reqs
            if not reqs:
                errors.append("هیچ نیازمندی رفتاریِ معتبر و مستند از متن کاربر باقی نماند؛ توضیحات فنی مدل جای خواسته کاربر را نمی‌گیرد")
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
            unknown_links = [rid for rid in f["req"] if rid not in valid_rids and rid not in dropped_requirement_ids]
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
    # 5.6) Unknown feature ids may only affect a real, linked request requirement.
    # Model-authored notes must never become fabricated user requirements.
    selected_req_links = {rid for feature in out_feats for rid in (feature.get("req") or [])}
    _salvage_requirement_rows(reqs, salvaged, selected_features=selected,
                              selected_req_links=selected_req_links)
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
    """Build a compact, grounded requirement prompt from the actual catalogue."""
    from modules import catalog
    from caps import CAPS_CONTRACT

    lines = []
    for module in catalog():
        params = ",".join(f"{p['k']}:{p['kind']}" for p in (module.get("params") or []))
        aliases = "،".join((module.get("aliases") or [])[:16])
        desc = str(module.get("desc") or "")[:150]
        lines.append(
            f"{module['id']}|{module['fa']}|{desc}|alias:{aliases or '-'}|params:{params or '-'}"
        )
    catalog_text = "\n".join(lines)
    contracts = []
    for contract in CAPS_CONTRACT.values():
        status = contract.get("status")
        if status in ("engine_only", "unsupported"):
            contracts.append(
                f"{contract.get('id')}|{contract.get('title')}|{status}|" +
                ";".join(map(str, contract.get("limits") or []))[:90]
            )
    engine_text = "\n".join(contracts[:20]) or "-"
    editing = bool(current_summary)
    intent = "edit" if editing else "create"

    instructions = (
        "تو فقط برنامه‌ریز هستی؛ کد یا کانفیگ اجرایی تولید نکن. خروجی فقط یک JSON مطابق قرارداد زیر باشد.\n"
        "درخواست کاربر را به نیازمندی‌های مستقل و قابل مشاهده برای کاربر تقسیم کن. هر requirement باید دقیقاً یک source_quote داشته باشد که عیناً، پیوسته و بدون بازنویسی از متن درخواست کاربر کپی شده باشد.\n"
        "source_quote تنها مدرک مجاز برای اثبات اینکه خواسته واقعاً از کاربر آمده است. عبارت‌های نمونه، متن این دستور، شناسه‌های نمونه و توضیحات فنی خودت را هرگز به‌عنوان خواسته کاربر وارد نکن.\n"
        "در requirements فقط رفتار یا نتیجه‌ای را ثبت کن که کاربر واقعاً خواسته است؛ تحلیل داخلی مثل نیاز به دیتابیس، اتصال، توسعه اختصاصی، Compiler، کاتالوگ یا شناسه ماژول، requirement کاربر نیست مگر صریحاً خودش خواسته باشد.\n"
        "هر source_quote باید کوتاه‌ترین عبارت دقیق و مستقل از متن کاربر باشد؛ دو requirement نباید یک quote تکراری داشته باشند. want نباید مفهوم فنی یا رفتاری تازه‌ای اضافه کند که در درخواست کاربر نیست.\n"
        "اگر یک بند دو رفتار مستقل دارد، آن را تفکیک کن و برای هرکدام quote دقیق و جداگانه بده. محل اجرا را فقط در part بنویس؛ محل اجرا را به رفتار جدید تبدیل نکن.\n"
        "features فقط شناسه واقعی ماژول‌های فهرست‌شده باشد. هر feature باید req را به شناسه requirement مربوط وصل کند و هر requirement با وضعیت covered باید حداقل یک feature واقعی و مرتبط داشته باشد.\n"
        "قابلیت عمومی مثل start_menu/about/support/faq جایگزین رفتار تخصصی نیست. اگر قابلیت آماده مرتبط وجود دارد حتماً همان را انتخاب کن. اگر وجود ندارد، فقط همان requirement مستند را catalog_missing ثبت کن. engine_limit فقط وقتی مجاز است که قرارداد موتور صریحاً unsupported اعلام کرده باشد.\n"
        "فیلدهای ریشه: intent, name, emoji, payments, requirements, features, texts. intent باید همین مقدار از پیش تعیین‌شده باشد: " + intent + ".\n"
        "هر عنصر requirements: id, want, source_quote, part, status, features, why, upgrade. هر عنصر features: type, params, req, note. نسخه Spec را ننویس.\n"
        "نسخهٔ Spec را تولید نکن؛ برنامه آن را تنظیم می‌کند. پاسخ باید JSON معتبر باشد؛ هیچ توضیح یا Markdown بیرون JSON ننویس."
    )
    if editing:
        instructions += (
            "\nاین توسعه ربات موجود است. فقط قابلیت‌های درخواست فعلی را در features قرار بده؛"
            " ساختارهای فعلی صرفاً زمینه‌اند و نباید بی‌دلیل دوباره تولید یا حذف شوند."
        )
    current = ""
    if editing and current_summary:
        # The bot summary is already compact JSON. Never slice serialized JSON at an
        # arbitrary character boundary: a truncated object makes the model infer a
        # malformed or incomplete current project. Prune whole low-priority entries.
        try:
            summary_obj = json.loads(current_summary) if isinstance(current_summary, str) else current_summary
        except Exception:
            summary_obj = {"summary_text": str(current_summary)[:1200]}
        if isinstance(summary_obj, dict):
            def _pack_summary():
                return json.dumps(summary_obj, ensure_ascii=False, separators=(",", ":"))
            for key in ("relevant_nodes", "node_index", "vars", "globals", "commands"):
                values = summary_obj.get(key)
                while len(_pack_summary()) > 2300 and isinstance(values, list) and values:
                    values.pop()
                if key == "node_index" and isinstance(values, list):
                    summary_obj["node_index_truncated"] = max(
                        int(summary_obj.get("node_index_truncated") or 0),
                        int(summary_obj.get("node_count") or 0) - len(values), 0)
            current_json = _pack_summary()
        else:
            current_json = json.dumps(str(summary_obj)[:1200], ensure_ascii=False)
        current = "\nخلاصهٔ ساختاری فعلی به‌صورت JSON معتبر (فقط زمینه، نه نیازمندی جدید):\n" + current_json
    system = (
        instructions + "\n\nکاتالوگ واقعی ماژول‌های آماده (فقط این شناسه‌ها مجازند):\n" +
        catalog_text + "\n\nقرارداد توانایی‌های بدون ماژول آماده:\n" + engine_text + current
    )
    user = "متن اصلی درخواست کاربر؛ تنها منبع استخراج نیازمندی و source_quote:\n" + str(prompt_text or "")[:6000]
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_llm_spec(text, require_requirements=False, expected_intent=None, request_context=""):
    """پاسخ مدل → Spec اعتبارسنجی‌شده. در مسیر AI، requirements و intent اجباری‌اند."""
    from ai import _extract_json_object
    raw = _extract_json_object(str(text or ""))
    if not raw:
        raise SpecError("پاسخ مدل JSON نداشت")
    return validate_spec(raw, require_requirements=require_requirements, expected_intent=expected_intent,
                         request_context=request_context,
                         require_grounded_quotes=bool(require_requirements and request_context))
