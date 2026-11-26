# -*- coding: utf-8 -*-
"""Requirement coverage and honest defect classification.

The coverage gate is deliberately independent from an LLM. It verifies that each
user requirement is connected to a registered module whose declared behavior is
relevant to that requirement. A syntactically valid Spec is not proof of semantic
coverage.
"""
import re

from modules import MODULES, normalize_text

GENERIC_IDS = ("start_menu", "about", "links", "support", "faq")
_STATUSES = ("covered", "catalog_missing", "engine_limit")
_STOP = {
    "ربات", "بساز", "بسازید", "ساخت", "کن", "کنه", "کنند", "باشد", "باشه", "میخوام", "میخواد",
    "می", "یه", "یک", "و", "یا", "در", "از", "به", "برای", "که", "را", "رو", "هم", "روی",
    "با", "تا", "اگر", "بعد", "بخش", "قسمت", "داخل", "توی", "روی", "خود", "من", "کاربر",
    "کاربران", "مورد", "میشه", "بشه", "شود", "شده", "انجام", "کنم", "کند", "کنید", "دارد",
    "داشته", "اضافه", "افزودن", "افزوده", "افزود", "ایجاد", "ساختن", "جدید", "قابلیت", "امکان", "سیستم", "مربوط", "موردنظر", "موردی",
    "گروه", "مدیریت", "مدیر", "منو", "شروع", "ربات", "پیوی", "خصوصی", "عمومی", "دکمه", "اعضا",
    "محیط", "کردن", "کرد", "کنه", "کنند", "امکان", "قابلیت", "مختلف", "خودکار", "مستقل", "اعضای", "منوی",
}
_WEAK_TRIGGER_HITS = {"منو", "گروه", "ربات", "شروع", "مدیر", "مدیریت", "بخش", "دکمه", "پیوی", "خصوصی"}


def _slug(text):
    parts = re.findall(r"[A-Za-z0-9آ-ی]+", normalize_text(text))
    return "_".join(parts)[:48].lower() or "request"


def norm_requirements(raw):
    """Normalize requirements without silently truncating or discarding them."""
    reqs, errors = [], []
    if not isinstance(raw, list):
        return [], ["requirements باید فهرست باشد"]
    if len(raw) > 12:
        return [], ["تعداد نیازمندی‌ها از سقف ۱۲ بیشتر است؛ هیچ موردی نباید بی‌صدا حذف شود"]
    seen = set()
    for i, r in enumerate(raw, 1):
        if not isinstance(r, dict):
            errors.append(f"نیازمندی {i} باید شیء JSON باشد")
            continue
        want = str(r.get("want") or "").strip()
        if len(want) < 3:
            errors.append(f"نیازمندی {i} فاقد «want» معتبر است")
            continue
        if len(want) > 300:
            errors.append(f"متن نیازمندی {i} بیش از ۳۰۰ نویسه است؛ برای جلوگیری از حذف جزئیات، آن را بی‌صدا کوتاه نمی‌کنیم")
            continue
        rid = str(r.get("id") or f"r{i}").strip()
        if len(rid) > 20:
            errors.append(f"شناسهٔ نیازمندی {i} بیش از ۲۰ نویسه است")
            continue
        if not rid or rid in seen:
            errors.append(f"شناسهٔ خالی یا تکراری نیازمندی: {rid or i}")
            continue
        seen.add(rid)
        st = str(r.get("status") or "covered").strip().lower()
        if st not in _STATUSES:
            errors.append(f"وضعیت نامعتبر «{st}» برای نیازمندی {rid}")
            continue
        raw_feats = r.get("features", [])
        if raw_feats is None:
            raw_feats = []
        if not isinstance(raw_feats, list):
            errors.append(f"features نیازمندی {rid} باید فهرست باشد")
            raw_feats = []
        raw_feat_ids = [str(x).strip() for x in raw_feats if str(x).strip()]
        if any(len(x) > 60 for x in raw_feat_ids):
            errors.append(f"شناسهٔ قابلیت در نیازمندی {rid} بیش از ۶۰ نویسه است")
        feats = list(dict.fromkeys(raw_feat_ids))
        if len(feats) > 8:
            errors.append(f"تعداد قابلیت‌های متصل به نیازمندی {rid} بیش از ۸ است؛ هیچ موردی بی‌صدا حذف نمی‌شود")
        part = str(r.get("part") or "").strip()
        if len(part) > 120:
            errors.append(f"محل/بخش نیازمندی {rid} بیش از ۱۲۰ نویسه است")
            continue
        reqs.append({
            "id": rid, "want": want, "part": part,
            "status": st, "features": feats,
            "why": str(r.get("why") or "").strip()[:400],
            "upgrade": str(r.get("upgrade") or "").strip()[:300],
            "source": str(r.get("source") or "model")[:30],
        })
    if not reqs and not errors:
        errors.append("فهرست requirements خالی است")
    return reqs, errors


def _ensure_catalog():
    """Make coverage independent of import order; modules are registered by modlib."""
    try:
        import modlib  # noqa: F401
    except Exception:
        pass


def _trigger_score(mod, text):
    """Score a module against a requirement using its own registered triggers."""
    t = normalize_text(text)
    score, hits = 0.0, []
    for rx, weight in (getattr(mod, "triggers", None) or []):
        try:
            matches = list(re.finditer(rx, t, flags=re.I))
        except re.error:
            continue
        if matches:
            accepted = []
            for match in matches[:2]:
                hit = normalize_text(match.group(0)).strip()
                words = _tokens(hit)
                if hit in _WEAK_TRIGGER_HITS or (not words and len(hit) < 5):
                    continue
                accepted.append(hit)
            if accepted:
                score += float(weight or 0.5) * min(len(accepted), 2)
                hits.extend(accepted)
    return score, hits


def _tokens(text):
    vals = re.findall(r"[a-zA-Z0-9_]+|[\u0600-\u06FF]+", normalize_text(text).casefold())
    return {x for x in vals if len(x) >= 3 and x not in _STOP}


def _module_relevance(mid, text):
    """Conservative semantic relevance using module name/description and explicit triggers."""
    mod = MODULES.get(mid)
    if not mod:
        return 0.0, []
    trig, hits = _trigger_score(mod, text)
    req_tokens = _tokens(text)
    desc_tokens = _tokens(" ".join((mod.id, mod.fa, mod.title, mod.desc)))
    hit_tokens = _tokens(" ".join(hits))
    overlap = req_tokens & desc_tokens
    score = trig + min(len(overlap), 3) * 0.35
    if normalize_text(mod.fa) and normalize_text(mod.fa) in normalize_text(text):
        score += 1.0
    return score, hits + sorted(overlap)


def _module_match(mid, text, minimum=0.75):
    """Require the module to explain the meaningful terms, not just one broad keyword."""
    score, hits = _module_relevance(mid, text)
    if score < minimum:
        return False, score, hits
    mod = MODULES.get(mid)
    req_terms = _tokens(text)
    supported_terms = _tokens(" ".join((mod.id, mod.fa, mod.title, mod.desc, *hits))) if mod else set()
    def explained(term):
        return any(term == known or term.startswith(known) or known.startswith(term) for known in supported_terms)
    unexplained = {term for term in req_terms if not explained(term)}
    if req_terms and len(unexplained) / max(1, len(req_terms)) >= 0.25:
        return False, score, hits
    return True, score, hits


def catalog_candidates(text, minimum=0.75):
    """Return only modules that explain the requirement's meaningful terms."""
    _ensure_catalog()
    found = []
    for mid, mod in MODULES.items():
        ok, score, hits = _module_match(mid, text, minimum)
        if ok:
            found.append({"id": mid, "score": round(score, 3), "hits": hits[:6], "module": mod})
    return sorted(found, key=lambda x: (-x["score"], x["id"]))


def _trigger_match(mod, text):
    return _trigger_score(mod, text)[0] > 0


def _canonical_feature_id(value):
    value = str(value or "").strip()
    if value in MODULES:
        return value
    try:
        import spec
        value = spec.ALIASES.get(value, value)
    except Exception:
        pass
    if value in MODULES:
        return value
    try:
        from caps import CAPS_CONTRACT
        cap = CAPS_CONTRACT.get(value)
        if cap:
            mods = str(cap.get("module") or "").split("/")
            for mid in mods:
                if mid in MODULES:
                    return mid
    except Exception:
        pass
    return value


def _raw_feature_ids(req):
    raw = list(req.get("features") or [])
    if isinstance(req.get("feature"), str):
        raw.append(req.get("feature"))
    return list(dict.fromkeys(str(x).strip() for x in raw if str(x).strip()))


def _mapped_ids(req):
    out = []
    for item in _raw_feature_ids(req):
        mid = _canonical_feature_id(item)
        if mid in MODULES and mid not in out:
            out.append(mid)
    return out


def _req_match_text(req):
    """Match the requested behavior, not the UI location where it should appear.

    `part` is placement/context (e.g. "منوی شروع"), not a feature by itself. It is
    used only when `want` contains no meaningful behavioral terms.
    """
    want = str(req.get("want") or "").strip()
    if _tokens(want):
        return want
    return (want + " " + str(req.get("part") or "")).strip()


def _served_by(req, types_selected):
    """Coverage requires both an actual selected module and semantic relevance."""
    mapped = [mid for mid in _mapped_ids(req) if mid in types_selected]
    text = _req_match_text(req)
    return any(_module_match(mid, text)[0] for mid in mapped)


def _static_limit_for(want, prompt):
    try:
        from ai import _STATIC_LIMITS
    except Exception:
        return None
    # Static limits belong to this requirement only. Scanning the whole request here
    # can incorrectly copy one unsupported clause onto every other requirement.
    text = normalize_text(want or "")
    for pat, lim_want, why, alt, feat in _STATIC_LIMITS:
        if re.search(pat, text, re.I):
            return {"kind": "ENGINE_LIMIT", "feature": feat, "want": lim_want, "why": why,
                    "upgrade": "جایگزین: " + alt}
    return None


def _contract_matches(text):
    """Find relevant capability contracts beyond fragile title-substring matching."""
    try:
        from caps import CAPS_CONTRACT
    except Exception:
        return []
    t = normalize_text(text)
    out = []
    for cid, c in CAPS_CONTRACT.items():
        title = normalize_text(c.get("title") or "")
        module_names = str(c.get("module") or "").split("/")
        score = 0.0
        if title and (title in t or t in title):
            score += 1.5
        if any(mid in MODULES and _module_match(mid, t)[0] for mid in module_names):
            score += 1.5
        title_overlap = _tokens(title) & _tokens(t)
        score += min(len(title_overlap), 3) * 0.25
        if score >= 1.0:
            out.append((score, c))
    return [c for _, c in sorted(out, key=lambda x: -x[0])]


def _classify_catalog_candidate(req, prompt, selected=()):
    """An existing matching module means a Spec/planning defect, never catalog-missing."""
    import defects as _defects
    text = _req_match_text(req)
    candidates = catalog_candidates(text)
    mapped = _mapped_ids(req)
    selected = set(selected or ())
    mapped_hits = [mid for mid in mapped if _module_match(mid, text)[0]]
    if mapped_hits:
        chosen = mapped_hits[0]
        return _defects.build_defect(
            chosen, req.get("want"),
            "Spec نیازمندی را به ماژول موجود متصل کرده، اما پوشش آن در مرحلهٔ کنترل نیازمندی‌ها تأیید نشده است.",
            stage="spec", severity="high", suggested_capability=chosen,
            acceptance_criteria=("ماژول مسئول در Spec انتخاب شود", "رفتار موردنظر با تست پذیرش تأیید شود"),
            upgrade="اصلاح نگاشت نیازمندی و اجرای مجدد مسیر Spec → Compiler")
    if candidates:
        top = candidates[0]
        # A near-tie usually means the requirement contains multiple concerns or is ambiguous.
        tied = [x for x in candidates if top["score"] - x["score"] < 0.25]
        if len(tied) == 1:
            mid = top["id"]
            return _defects.build_defect(
                mid, req.get("want"),
                f"قابلیت موجود «{MODULES[mid].fa}» با این نیازمندی تطبیق دارد، اما در Spec به‌درستی انتخاب/متصل نشده است. تطبیق: {', '.join(top['hits'][:4])}",
                stage="spec", severity="high", suggested_capability=mid,
                acceptance_criteria=("قابلیت موجود در Spec انتخاب شود", "نیازمندی در خروجی نهایی پوشش داده شود"),
                upgrade="اصلاح استخراج نیازمندی و نگاشت آن به کاتالوگ موجود؛ افزودن قابلیت جدید لازم نیست")
        names = "، ".join(MODULES[x["id"]].fa for x in tied[:4])
        return _defects.build_defect(
            "", req.get("want"), f"نیازمندی با چند ماژول موجود تطبیق دارد ({names})؛ تجزیهٔ نیازمندی یا انتخاب ماژول مبهم است.",
            stage="spec", severity="high", acceptance_criteria=("نیازمندی به اجزای مستقل تفکیک شود", "هر جزء به ماژول مسئول متصل شود"),
            upgrade="اصلاح تحلیل نیازمندی/Planner؛ این مورد CATALOG_MISSING نیست")

    # A requirement may bundle a known behavior with another clause. Do not call the
    # entire bundle catalog-missing; report a planning/decomposition defect instead.
    partial = []
    req_terms = _tokens(text)
    for mid, mod in MODULES.items():
        score, hits = _module_relevance(mid, text)
        hit_terms = _tokens(" ".join(hits))
        supported_terms = _tokens(" ".join((mod.id, mod.fa, mod.title, mod.desc, *hits)))
        unexplained = req_terms - supported_terms
        if score >= 0.75 and hits and unexplained:
            partial.append((score, mid, hits, unexplained))
    if partial:
        partial.sort(key=lambda x: (-x[0], x[1]))
        best = partial[0]
        if len(partial) == 1 or best[0] - partial[1][0] >= 0.25:
            mid = best[1]
            return _defects.build_defect(
                mid, req.get("want"),
                f"این ردیف چند خواسته را با هم ترکیب کرده است؛ بخشی با ماژول موجود «{MODULES[mid].fa}» تطبیق دارد ({', '.join(best[2][:4])}) و لازم است نیازمندی‌ها جدا و تفکیک شوند.",
                stage="spec", severity="high", suggested_capability=mid,
                acceptance_criteria=("خواسته به نیازمندی‌های مستقل تفکیک شود", "برای هر بخش، قابلیت مرتبط یا محدودیت مستند ثبت شود"),
                upgrade="اصلاح تجزیهٔ درخواست در مرحلهٔ Spec؛ این مورد به‌تنهایی CATALOG_MISSING نیست")
    return None


def classify_uncovered(req, prompt="", selected=()):
    """Classify an uncovered requirement using actual module and engine contracts."""
    import defects as _defects
    want = (req.get("want") or "").strip()
    mapped = _mapped_ids(req)

    # An existing relevant module takes precedence over a model's ENGINE_LIMIT/CATALOG_MISSING claim.
    existing = _classify_catalog_candidate(req, prompt, selected)
    if existing:
        return existing

    # A directly referenced contract is authoritative; engine_only is catalog-missing, not engine-limit.
    contracts = []
    try:
        from caps import CAPS_CONTRACT
        for fid in _raw_feature_ids(req):
            direct = CAPS_CONTRACT.get(fid)
            if direct:
                contracts.append(direct)
            canonical = _canonical_feature_id(fid)
            for cap in CAPS_CONTRACT.values():
                if canonical and canonical in str(cap.get("module") or "").split("/"):
                    contracts.append(cap)
    except Exception:
        pass
    contracts.extend(_contract_matches(_req_match_text(req)))
    seen_contracts = set()
    for cap in contracts:
        cid = cap.get("id")
        if cid in seen_contracts:
            continue
        seen_contracts.add(cid)
        if cap.get("status") == "unsupported":
            prop = cap.get("proposal") or {}
            return _defects.defect("ENGINE_LIMIT", cid, want,
                str(req.get("why") or "قرارداد توانایی موتور این قابلیت را صریحاً پشتیبانی‌نشده ثبت کرده است."),
                severity="high", stage="spec", suggested_capability=cid,
                upgrade=req.get("upgrade") or prop.get("reason") or "نیازمند توسعهٔ موتور")
        if cap.get("status") == "engine_only":
            return _defects.catalog_missing(cid, want,
                "زیرساخت موتور در قرارداد قابلیت وجود دارد، اما تولیدکنندهٔ خودکار آماده برای آن ثبت نشده است.")

    static = _static_limit_for(want, "")
    if static:
        return _defects.defect("ENGINE_LIMIT", static.get("feature") or "", static.get("want") or want,
            static.get("why") or req.get("why") or "محدودیت در قرارداد موتور ثبت شده است.",
            severity="high", stage="spec", suggested_capability=static.get("feature") or "",
            upgrade=req.get("upgrade") or static.get("upgrade") or "")

    return _defects.catalog_missing(
        _slug((mapped[0] if mapped else "") + " " + want), want,
        "ماژول منطبق در کاتالوگ پیدا نشد و محدودیت قطعی موتور نیز اثبات نشده است؛ این مورد باید به‌عنوان نیاز توسعه/بررسی ثبت شود، نه ناتوانی قطعی موتور.")


def reconcile_spec(spec, prompt=""):
    """Recover existing catalog modules omitted or misclassified by the model.

    This does not add capabilities: it only selects already registered modules when
    a unique, strong trigger match exists, and links that module to the requirement.
    """
    from modules import clean_params
    features = spec.setdefault("features", [])
    requirements = spec.setdefault("requirements", [])
    selected = {f.get("type") for f in features if isinstance(f, dict)}
    changed = []
    for req in requirements:
        if not isinstance(req, dict):
            continue
        text = _req_match_text(req)
        if _served_by(req, selected):
            continue
        mapped = _mapped_ids(req)
        candidates = catalog_candidates(text)
        if mapped:
            mapped_candidates = [x for x in candidates if x["id"] in mapped]
            if mapped_candidates:
                candidates = mapped_candidates + [x for x in candidates if x["id"] not in mapped]
        if not candidates:
            continue
        top = candidates[0]
        tied = [x for x in candidates if top["score"] - x["score"] < 0.25]
        if len(tied) != 1:
            continue
        mid = top["id"]
        if mid not in selected:
            features.append({"type": mid, "params": clean_params(MODULES[mid], {}), "req": [], "note": ""})
            selected.add(mid)
        f = next((x for x in features if isinstance(x, dict) and x.get("type") == mid), None)
        if f is not None:
            f["req"] = list(dict.fromkeys((f.get("req") or []) + [req.get("id")]))
        req["features"] = [mid]
        req["status"] = "covered"
        req["why"] = ""
        req["upgrade"] = ""
        req["source"] = "catalog_reconciliation"
        changed.append(mid)
    return list(dict.fromkeys(changed))


def covered_requirements(spec):
    """Return only request requirements backed by a semantically relevant selected module."""
    selected = {f.get("type") for f in (spec.get("features") or []) if isinstance(f, dict)}
    return [r for r in (spec.get("requirements") or [])
            if isinstance(r, dict) and r.get("status") == "covered" and _served_by(r, selected)]


def has_meaningful_coverage(spec):
    """A general shell/menu alone is not evidence that the user's core request was built."""
    return bool(covered_requirements(spec))


def unmet_items(spec, prompt=""):
    out = []
    selected = {f.get("type") for f in (spec.get("features") or []) if isinstance(f, dict)}
    for r in spec.get("requirements") or []:
        if not isinstance(r, dict):
            continue
        if r.get("status") == "covered" and _served_by(r, selected):
            if not _static_limit_for(r.get("want") or "", ""):
                continue
        out.append(classify_uncovered(r, prompt, selected))
    return [x for x in out if isinstance(x, dict)]


def coverage_report(spec):
    reqs = [r for r in (spec.get("requirements") or []) if isinstance(r, dict)]
    if not reqs:
        return None
    types_selected = {f.get("type") for f in (spec.get("features") or []) if isinstance(f, dict)}
    items, n_cov = [], 0
    for r in reqs:
        dedicated = False
        covered = r.get("status") == "covered" and _served_by(r, types_selected)
        if covered:
            n_cov += 1
            mapped = [mid for mid in _mapped_ids(r) if mid in types_selected and _module_match(mid, _req_match_text(r))[0]]
            fa = "، ".join(MODULES[t].fa for t in mapped) or "—"
            try:
                from engine_accept import _SCENARIOS
                dedicated = any(t in _SCENARIOS for t in mapped)
            except Exception:
                dedicated = False
            evidence = (f"قابلیت «{fa}» در Spec انتخاب شد و تست پذیرش اختصاصی آن PASS شد."
                        if dedicated else f"قابلیت «{fa}» به‌صورت معنایی به این نیازمندی نگاشت شد و ساختار خروجی معتبر است؛ تست رفتاری اختصاصی برای این ماژول ثبت نشده و اجرای کامل آن مستقلاً اثبات نشده است.")
            status = "covered"
        else:
            status = "uncovered"
            evidence = "برای این نیازمندی، ماژول مرتبط و منتخب با شواهد کافی در خروجی پیدا نشد."
        items.append({"id": r.get("id"), "want": r.get("want"), "part": r.get("part"), "status": status,
                      "verification": "behavioral_test" if covered and dedicated else ("structural_only" if covered else "not_covered"),
                      "features": [mid for mid in _mapped_ids(r) if mid in types_selected], "evidence": evidence})
    verified = sum(1 for item in items if item.get("verification") == "behavioral_test")
    return {"total": len(items), "covered": n_cov, "verified": verified,
            "all_behavior_verified": bool(items) and verified == len(items),
            "ok": n_cov == len(items), "requirements": items}


def coverage_thinking(thinking, report):
    if not report or not report.get("requirements"):
        return thinking
    n, c = report.get("total") or 0, report.get("covered") or 0
    lines = []
    if n and c == n:
        verified = sum(1 for r in report["requirements"] if r.get("verification") == "behavioral_test")
        lines.append(f"پوشش درخواست: هر {n} خواسته به قابلیت مرتبط نگاشت شد؛ تست رفتاری اختصاصی برای {verified} مورد PASS شد. موارد دیگر فقط از نظر ساختاری بررسی شده‌اند.")
    else:
        lines.append(f"پوشش درخواست: {c} از {n} خواسته پوشش داده شد؛ موارد زیر اجرا نشدند:")
        for r in report["requirements"]:
            if r.get("status") != "covered":
                lines.append(f"• «{(r.get('want') or '')[:120]}» — {(r.get('evidence') or '')[:160]}")
    out = (thinking or "").rstrip()
    if out:
        out += "\n"
    return (out + "\n".join(lines))[:900]
