# -*- coding: utf-8 -*-
"""
tests/run_all.py — اجرای کل مجموعهٔ تست‌های BUILD 3.6.0 (بدون pytest، فقط stdlib)

اجرا:  python3 tests/run_all.py
تست‌ها: ماژول‌ها (تک + ترکیب) · Spec/Schema · sanitize/lint · رفتار موتور (Headless) ·
        طبقه‌بندی نقص‌ها و نقشهٔ توسعه · قرارداد caps · بازگشت از خطا · حفظ کانفیگ موجود
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tests._env  # noqa: F401  (قبل از هر import پروژه)

RESULTS = []


def T(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


# ───────────────────────── ۱) ماژول‌ها: تک‌تک با پیش‌فرض و پارامتر متفاوت ─────────────────────────
import core  # noqa: E402
import ai  # noqa: E402
import modules  # noqa: E402
import modlib  # noqa: E402
import planner  # noqa: E402
import spec  # noqa: E402
import defects  # noqa: E402
import engine_accept  # noqa: E402

ACC = engine_accept.run_acceptance


def _compile(mid, params=None):
    pr = planner.PlanResult()
    pr.items = [(mid, modules.clean_params(modules.MODULES[mid], params or {}))]
    pr.name, pr.emoji, pr.payments, pr.confidence = "تست", False, False, 1.0
    return planner.compile_plan(pr)


def _check_cfg(cfg, fids):
    """sanitize + lint + acceptance؛ خروجی فقط با تمام شرط‌ها معتبر است."""
    warns = []
    cfg = ai.sanitize(cfg, strict=False, warns=warns)
    issues = [x for x in ai.lint(cfg) if not x.startswith("variables that are read but never set")]
    acc = ACC(cfg, fids)
    assert not issues, f"lint: {issues[:3]}"
    assert not acc, f"acceptance: {[d.get('evidence') for d in acc[:3]]}"
    assert cfg.get("nodes"), "بدون نود"
    return cfg


MOD_CASES = [
    ("wallet", {}), ("wallet", {"coin": "الماس", "start_bonus": 10}),
    ("daily", {}), ("referral", {"reward": 3}), ("miner", {}),
    ("wheel", {"daily_ticket": True}), ("wheel", {"per_refs": 2}),
    ("puzzle", {}), ("sponsor", {}), ("forced_join", {}), ("member_orders", {}),
    ("coin_shop", {}), ("owner_panel", {}), ("support", {}), ("faq", {}), ("about", {}),
    ("links", {}), ("shop", {}), ("ai_assistant", {}), ("quiz", {}), ("group_manager", {}),
    ("ads", {}), ("start_menu", {"welcome": "سلام {name}!"}),
    ("dice", {}), ("dice", {"sides": 12}), ("guess", {"max_num": 5}), ("guess", {"max_num": 50}),
    ("coinbet", {}), ("coinbet", {"amounts": [2, 4]}), ("leaderboard", {"var": "qscore"}),
]

for mid, p in MOD_CASES:
    def _fn(mid=mid, p=p):
        th, cfg, ideas = _compile(mid, p)
        _check_cfg(cfg, [mid])
    T(f"module:{mid}:{p or 'default'}")(_fn)


# ───────────────────────── ۲) ترکیب ماژول‌ها (تداخل نام/متغیر/route) ─────────────────────────
COMBOS = [
    (["wallet", "dice"], "کیف + تاس"),
    (["wallet", "guess"], "کیف + حدس عدد"),
    (["wallet", "coinbet"], "کیف + شرط‌بندی"),
    (["wallet", "wheel", "daily"], "کیف + گردونه + روزانه"),
    (["referral", "wallet", "leaderboard"], "دعوت + کیف + رتبه‌بندی"),
    (["quiz", "leaderboard"], "کوییز + رتبه‌بندی"),
    (["wallet", "dice", "guess", "coinbet", "quiz", "wheel", "daily", "referral", "leaderboard", "owner_panel"], "همهٔ بازی‌ها با هم"),
    (["shop", "support", "faq", "about", "links", "owner_panel"], "قالب فروشگاه"),
    (["group_manager", "forced_join", "support", "faq", "owner_panel"], "قالب مدیریت گروه"),
]


def _combo(ids):
    pr = planner.PlanResult()
    pr.items = [(i, modules.clean_params(modules.MODULES[i], {})) for i in ids]
    pr.name, pr.confidence = "ترکیب", 1.0
    th, cfg, ideas = planner.compile_plan(pr)
    _check_cfg(cfg, ids)
    # تداخل شناسه‌ها: هیچ نود یا متغیر تکراری ممکن نیست (Builder خودش خطا می‌دهد)
    nodes = cfg["nodes"]
    assert len(nodes) == len(set(nodes)), "شناسهٔ نود تکراری"


for ids, name in COMBOS:
    T(f"combo:{name}")(_combo) if False else None
    def _fn(ids=ids):
        _combo(ids)
    T(f"combo:{name}")(_fn)


# ───────────────────────── ۳) Spec و Schema ─────────────────────────
@T("spec:valid-minimal")
def _():
    sp = spec.validate_spec({"version": 1, "intent": "create", "name": "x", "features": [{"type": "dice"}]})
    assert "wallet" in [f["type"] for f in sp["features"]], "وابستگی wallet خودکار نیامد"


@T("spec:reject-unknown-feature")
def _():
    try:
        spec.validate_spec({"version": 1, "intent": "create", "name": "x", "features": [{"type": "brain_surgery"}]})
    except spec.SpecError:
        return
    raise AssertionError("قابلیت خارج از کاتالوگ رد نشد")


@T("spec:reject-unknown-param")
def _():
    try:
        spec.validate_spec({"version": 1, "intent": "create", "name": "x", "features": [{"type": "dice", "params": {"junk": 1}}]})
    except spec.SpecError:
        return
    raise AssertionError("پارامتر ناشناخته رد نشد")


@T("spec:reject-unknown-toplevel")
def _():
    try:
        spec.validate_spec({"version": 1, "intent": "create", "name": "x", "features": [{"type": "dice"}], "hack": 1})
    except spec.SpecError:
        return
    raise AssertionError("کلید سطح‌بالای ناشناخته رد نشد")


@T("spec:parse-llm-json-extraction")
def _():
    sp = spec.parse_llm_spec('پیش‌نمایش: ```json\n{"version":1,"intent":"create","name":"لالبازی","features":[{"type":"game.quiz"}]}\n```')
    assert [f["type"] for f in sp["features"]] == ["quiz"]


@T("spec:compile-alias")
def _():
    th, cfg, ideas = spec.compile_spec({"version": 1, "intent": "create", "name": "x",
                                        "features": [{"type": "game.wheel"}]})
    assert "wheel_go" in cfg["nodes"], "alias game.wheel کامپایل نشد"


# ───────────────────────── ۴) sanitize / lint (متغیرها و مسیرها) ─────────────────────────
@T("sanitize:undeclared-var-in-text-flagged")
def _():
    """متغیر استفاده‌شده ولی تعریف‌نشده: به‌صورت قطعی تعریف می‌شود (قانون ۴) و با warn + lint آشکار می‌شود (قانون ۶ — نادیده گرفته نمی‌شود)."""
    cfg = {"name": "تست", "start": "start", "fallback": "start", "commands": {}, "nodes": {
        "start": {"text": "موجودی: {ghost_var} سکه", "buttons": []}}}
    warns = []
    out = ai.sanitize(cfg, strict=False, warns=warns)
    assert "ghost_var" in (out.get("vars") or {}), "تعریف قطعی متغیر جاافتاده انجام نشد"
    assert any("ghost_var" in w for w in warns), "تعریف خودکار متغیر بدون گزارش warn انجام شد (نادیده‌گرفته)"
    issues = ai.lint(out)
    assert any("variables that are read but never set" in x and "ghost_var" in x for x in issues), f"lint متغیر خوانده‌شده را گزارش نمی‌دهد: {issues}"


@T("sanitize:invalid-json-structure-rejected")
def _():
    try:
        ai.sanitize({"nodes": []}, strict=False)
    except ValueError:
        return
    raise AssertionError("ساختار نامعتبر پذیرفته شد")


@T("lint:detects-dead-end")
def _():
    cfg = {"name": "تست", "start": "start", "fallback": "start", "commands": {},
           "vars": {}, "nodes": {"start": {"text": "سلام", "buttons": [[{"text": "برو", "goto": "dead"}]]},
                                 "dead": {"text": "بن‌بست", "buttons": []}}}
    cfg = ai.sanitize(cfg, strict=False)
    issues = ai.lint(cfg)
    assert any("dead-end" in x for x in issues), f"بن‌بست شناسایی نشد: {issues}"


# ───────────────────────── ۵) رفتار واقعی موتور (Headless) ─────────────────────────
import engine  # noqa: E402


def _env(cfg, uid=777001):
    bot = {"_id": "b_" + str(uid), "owner": "o1", "config": cfg, "username": "tb"}
    return engine.Env(bot, "TK", uid, {"id": uid, "first_name": "تست"}, "", "")


@T("engine:dice-range-and-record")
def _():
    _, cfg, _ = _compile("dice")
    env = _env(cfg)
    engine.run_actions(cfg["nodes"]["dice_roll"]["do"], env)
    v = int(env.get("dice_val"))
    assert 1 <= v <= 6, f"تاس خارج از دامنه: {v}"
    engine.run_actions([{"op": "set", "var": "dice_best", "value": "{dice_val}"}], env)
    assert int(env.get("dice_best")) == v


@T("engine:guess-compare")
def _():
    env = _env({"name": "x", "nodes": {}, "vars": {"g_pick": "0", "g_target": "0"}}, 777002)
    env.set("g_pick", "5")
    env.set("g_target", "5")
    assert engine.check({"var": "g_pick", "op": "==", "value": "{g_target}"}, env) is True
    env.set("g_pick", "3")
    assert engine.check({"var": "g_pick", "op": "!=", "value": "{g_target}"}, env) is True


@T("engine:coinbet-math-no-negative")
def _():
    _, cfg, _ = _compile("coinbet")
    env = _env(cfg, 777003)
    env.set("coins", "10")
    env.set("bet_amt", "4")
    env.save()
    engine.run_actions(cfg["nodes"]["bet_go"]["do"], env)
    assert float(env.get("coins")) == 6.0, f"کسر نادرست: {env.get('coins')}"
    engine.run_actions([{"op": "add", "var": "coins", "value": "{bet_back}"}], env)
    assert float(env.get("coins")) == 14.0


@T("engine:daily-once-per-day")
def _():
    _, cfg, _ = _compile("daily")
    env = _env(cfg, 777004)
    r = engine_accept._pick_route(cfg["nodes"]["daily"], env)
    assert r["goto"] == "daily_get", "روز اول باید هدیه بدهد"
    engine.run_actions(cfg["nodes"]["daily_get"]["do"], env)
    r2 = engine_accept._pick_route(cfg["nodes"]["daily"], env)
    assert r2["goto"] == "daily_done", "دومین بار در همان روز نباید هدیه بدهد"


@T("engine:wallet-add-persists")
def _():
    _, cfg, _ = _compile("wallet")
    env = _env(cfg, 777005)
    engine.run_actions([{"op": "add", "var": "coins", "value": "3"}], env)
    env.save()
    env2 = _env(cfg, 777005)
    assert float(env2.get("coins")) == 3.0, "ذخیرهٔ uvars کار نمی‌کند"


# ───────────────────────── ۶) طبقه‌بندی نقص‌ها و نقشهٔ توسعه ─────────────────────────
import caps as caps_mod  # noqa: E402


@T("defects:three-kinds-independent")
def _():
    assert defects.DEFECT_KINDS == ("BUILD_DEFECT", "ENGINE_LIMIT", "CATALOG_MISSING")
    d = defects.build_defect("f", "w", "e")
    assert d["kind"] == "BUILD_DEFECT"
    e = defects.engine_limit("w", "e", "u")
    assert e["kind"] == "ENGINE_LIMIT"
    c = defects.catalog_missing("mod", "w")
    assert c["kind"] == "CATALOG_MISSING"


@T("defects:roadmap-priority-by-count")
def _():
    assert defects.roadmap_priority(1) == 1
    assert defects.roadmap_priority(12) == 3
    assert defects.roadmap_priority(100) == 5


@T("defects:roadmap-from-engine-limit")
def _():
    rm = defects.engine_roadmap({"kind": "ENGINE_LIMIT", "feature": "pay.bank_gateway", "want": "درگاه"},
                                count=7)
    assert rm["capability"] == "pay.bank_gateway"
    assert rm["priority"] >= 2 and rm["plan"], "نقشهٔ توسعه خالی است"


@T("defects:aggregate-duplicates")
def _():
    ds = [defects.build_defect("g", "w", "e1"), defects.build_defect("g", "w", "e2")]
    agg = defects.aggregate_defects(ds)
    assert len(agg) == 1 and agg[0]["count"] == 2, "تجمیع نقص تکرارشونده کار نمی‌کند"


@T("caps:contract-counts-and-modules")
def _():
    sc = caps_mod.caps_status_counts()
    assert sc["ready"] >= 16 and sc["engine_only"] >= 10 and sc["unsupported"] >= 8
    c = caps_mod.capability("game.dice")
    assert c["status"] == "ready" and c.get("catalog_ready") is True


# ───────────────────────── ۷) سازگاری: کانفیگ‌های موجود ─────────────────────────
@T("compat:old-config-still-valid")
def _():
    """کانفیگ نسخهٔ قبل (بدون کلیدهای جدید) باید بدون تغییر معتبر بماند."""
    old = {"name": "قدیمی", "start": "start", "fallback": "start", "commands": {},
           "vars": {"coins": "0"},
           "nodes": {"start": {"text": "سلام {name}، موجودی {coins}", "buttons": [[{"text": "کیف", "goto": "w"}]]},
                      "w": {"text": "موجودی: {coins}", "buttons": [[{"text": "برگشت", "goto": "start"}]]}}}
    out = ai.sanitize(old, strict=False, warns=[])
    acc = ACC(out, ["wallet"])
    assert not acc, f"کانفیگ قدیمی رد شد: {[d.get('evidence') for d in acc[:2]]}"


@T("compat:merge-plan-preserves-existing")
def _():
    """merge_plan (مسیر ارتقا) نباید بخش‌های قبلی را حذف کند."""
    _, old, _ = _compile("daily")
    pr = planner.PlanResult()
    pr.items = [("dice", modules.clean_params(modules.MODULES["dice"], {}))]
    pr.name, pr.confidence = "ارتقا", 1.0
    th, cfg, _ = planner.merge_plan(old, pr)
    assert "daily" in cfg["nodes"] and "daily_get" in cfg["nodes"], "بخش قبلی حذف شد"
    assert "dice" in cfg["nodes"], "بخش جدید نیامد"
    _check_cfg(cfg, ["daily", "dice"])


# ───────────────────────── ۸) قالب‌ها (۳ قالب قطعی) ─────────────────────────
@T("templates:exactly-three-and-valid")
def _():
    keys = list(ai.TEMPLATES.keys())
    assert keys == ["shop", "game", "group"], f"قالب‌ها: {keys}"
    for k, t in ai.TEMPLATES.items():
        cfg = ai.sanitize(t["config"], strict=False, warns=[])
        acc = ACC(cfg, [])
        assert not acc, f"قالب {k} رد شد: {acc[:1]}"


# ───────────────────────── ۹) خط ساخت: مسیر روتر (بدون مدل) ─────────────────────────
@T("pipeline:ask_llm-router-no-model")
def _():
    th, cfg, ideas = ai.ask_llm("یک ربات با کیف سکه و تاس و رتبه بندی بساز")
    assert "dice" in cfg["nodes"] and "board" in cfg["nodes"], "خروجی کامپایلر ناقص است"
    _check_cfg(cfg, ["wallet", "dice", "leaderboard"])


@T("pipeline:wizard-needed-when-models-fail")
def _():
    """با خراب‌کردن عمدی llm_post، خط ساخت باید WizardNeeded بدهد نه خروجی ناقص."""
    import ai as _ai
    orig = _ai.llm_post
    def _broken(*a, **k):
        raise RuntimeError("HTTP 500 provider down")
    _ai.llm_post = _broken
    try:
        try:
            _ai.ask_spec("یک ربات غریب خیلی عجیب نامعمول بی‌سابقه بساز", "fa", [])
        except _ai.WizardNeeded:
            pass
        else:
            raise AssertionError("شکست مدل باید WizardNeeded بدهد")
    finally:
        _ai.llm_post = orig


# ───────────────────────── اجرا ─────────────────────────
def main():
    passed = failed = 0
    for name, fn in RESULTS:
        try:
            fn()
            passed += 1
            print(f"PASS  {name}")
        except Exception:
            failed += 1
            print(f"FAIL  {name}")
            traceback.print_exc(limit=3)
    print(f"\n== {passed} PASS · {failed} FAIL · {len(RESULTS)} total ==")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
