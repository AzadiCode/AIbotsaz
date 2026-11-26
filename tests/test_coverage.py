# -*- coding: utf-8 -*-
"""
tests/test_coverage.py — سناریوهای هدفمند «اصلاحیه بنیادی کیفیت» (Requirement Coverage)

اجرا:  python3 tests/test_coverage.py
سناریوها (بدون شبکه و بدون تلگرام؛ mongomock + llm_post جعلی):
  ۰) واحدِ طبقه‌بندی قطعی: ENGINE_LIMIT فقط با اثبات؛ وگرنه CATALOG_MISSING
  ۱) درخواست ساده با چند نیازمندی مشخص (روتر قطعی) → همهٔ خواسته‌ها در خروجی + گزارش پوشش در متن تحویل
  ۲) درخواست پیچیدهٔ چندقابلیت وابسته → وابستگی‌ها خودکار + پذیرش موتور + پوشش کامل
  ۳) ارتقای ربات موجود بدون تخریب (بازی جدید روی رباتی که همین قابلیت را دارد) → شناسهٔ یکتا + حفظ کامل بخش‌های قبلی
  ۴) درخواست با قابلیت واقعاً پشتیبانی‌نشده:
     ۴-الف) الگوی قطعی (درگاه بانکی) → ENGINE_LIMIT قبل از صرف توکن؛ گزارش ادمین؛ بدون ربات و بدون کسر
     ۴-ب) اعلام صادقانهٔ مدل (CATALOG_MISSING) → توقف پیش از ساخت؛ پس از پذیرش کاربر فقط بقیه ساخته می‌شود
     ۴-ج) نگهبان عمومی‌سازی: ادعای پوشش با قابلیت‌های عمومی رد می‌شود؛ تحویل ربات عمومی ممنوع
     ۴-د) مدل نیازمندی را حذف کند → SpecError → تلاش جایگزین با بازخورد → خطای صادقانه (بدون تحویل ناقص)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tests._env  # noqa: F401
import core

R = []


def T(name):
    def deco(fn):
        R.append((name, fn))
        return fn
    return deco


def _spec_json(name, feats, reqs, texts=None):
    return json.dumps({"version": 1, "intent": "create", "name": name, "emoji": False, "payments": False,
                       "requirements": reqs, "features": feats, "texts": texts or {}}, ensure_ascii=False)


class _Stub:
    """جایگزین ai.llm_post با پاسخ‌های از پیش تعیین‌شده؛ تعداد فراخوانی‌ها شمرده می‌شود."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.msgs = None

    def __call__(self, msgs, max_tokens, **kw):
        self.calls += 1
        self.msgs = msgs
        if not self.responses:
            raise RuntimeError("HTTP 503 stub exhausted")
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        txt = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
        return txt, (120, 60)


def _patch_llm(stub):
    import ai
    orig = ai.llm_post
    ai.llm_post = stub
    return orig


def _mk_user(uid, tokens=5000):
    core.db.users.update_one({"_id": uid}, {"$set": {"tokens": tokens, "spent": 0}}, upsert=True)


def _mk_job(jid, uid, prompt, bot_id=None):
    core.db.jobs.insert_one({"_id": jid, "uid": uid, "status": "running", "kind": "bot_build", "hold": 0,
                             "prompt": prompt, "bot_id": bot_id, "t": core.now()})


# ── ۰) واحدِ طبقه‌بندی قطعی ──
@T("00 classify: engine_limit only with proof, else catalog_missing")
def _():
    import coverage
    # اثبات با قرارداد caps (پشتیبانی‌نشدهٔ ثبت‌شده)
    d = coverage.classify_uncovered({"id": "r1", "want": "پرداخت با درگاه بانکی زرین پال", "status": "engine_limit"})
    assert d["kind"] == "ENGINE_LIMIT" and d["feature"] == "pay.bank_gateway", d
    # اثبات با الگوی قطعی قبل از ساخت
    d2 = coverage.classify_uncovered({"id": "r2", "want": "افزودن خودکار پست در کانال", "status": "covered"})
    assert d2["kind"] == "ENGINE_LIMIT", d2
    # بدون اثبات → صادقانه CATALOG_MISSING (نه ENGINE_LIMIT)
    d3 = coverage.classify_uncovered({"id": "r3", "want": "مدیریت نظرات زیر پست‌های کانال", "status": "catalog_missing"})
    assert d3["kind"] == "CATALOG_MISSING", d3
    d4 = coverage.classify_uncovered({"id": "r4", "want": "یکی چیزی خیلی خاص", "status": "engine_limit"})
    assert d4["kind"] == "CATALOG_MISSING", d4


# ── ۱) درخواست ساده با چند نیازمندی مشخص ──
@T("01 simple multi-requirement via deterministic router")
def _():
    import ai
    stub = _Stub([])                       # هیچ فراخوانی مدل نباید اتفاق بیفتد
    orig = _patch_llm(stub)
    try:
        th, cfg, ideas = ai.ask_llm("ربات فروشگاه با پشتیبانی و سؤالات متداول بساز")
    finally:
        ai.llm_post = orig
    assert stub.calls == 0, "روتر قطعی باید بدون مدل جواب بدهد"
    nodes = cfg["nodes"]
    assert "shop" in nodes, "قابلیت فروشگاه در خروجی نیست"
    assert "support" in nodes, "قابلیت پشتیبانی در خروجی نیست"
    assert "faq" in nodes, "قابلیت سؤالات متداول در خروجی نیست"
    assert "پوشش درخواست" in th and "پیاده‌سازی" in th, "گزارش پوشش به کاربر تحویل نشد"
    # تست پذیرش موتور روی خروجی نهایی (مثل خود خط ساخت)
    import engine_accept
    assert not engine_accept.run_acceptance(cfg, ["shop", "support", "faq"]), "پذیرش موتور شکست خورد"


# ── ۲) درخواست پیچیدهٔ چندقابلیت وابسته ──
@T("02 complex request with dependent capabilities")
def _():
    import ai
    stub = _Stub([])
    orig = _patch_llm(stub)
    try:
        th, cfg, ideas = ai.ask_llm("ربات بازی با گردونه و رتبه بندی و دعوت دوستان و کیف سکه بساز")
    finally:
        ai.llm_post = orig
    nodes = cfg["nodes"]
    assert "wallet" in nodes and "wheel_go" in nodes and "invite" in nodes, "قابلیت‌های اصلی ناقص است"
    assert cfg.get("on_ref"), "پاداش دعوت (on_ref) تنظیم نشده"
    assert any(n.get("board") for n in nodes.values()), "رتبه‌بندی با board واقعی نیست"
    assert "coins" in (cfg.get("vars") or {}), "متغیر کیف تعریف نشده"
    import engine_accept
    acc = engine_accept.run_acceptance(cfg, ["wallet", "wheel", "leaderboard", "referral"])
    assert not acc, f"پذیرش موتور شکست خورد: {acc[:1]}"
    assert "پوشش درخواست" in th


# ── ۳) ارتقای ربات موجود بدون تخریب (همان مورد واقعی «بخش تکراری: quiz») ──
@T("03 upgrade existing bot without destroying previous parts")
def _():
    import ai
    # پایه: رباتی که مسابقه (کوییز) و گردونه و کیف دارد — روتر قطعی
    _, base, _ = ai.ask_llm("ربات با مسابقه و گردونه بساز")
    base_nodes = set(base["nodes"])
    assert "quiz" in base_nodes and "wheel_go" in base_nodes, "ربات پایه درست ساخته نشد"
    quiz_text_before = base["nodes"]["quiz"]["text"]

    # ارتقا: «یه بازی جدید هم به بخش شروع ربات اضافه کن» → مدل دوباره کوییز می‌دهد (بازی جدید از کاتالوگ)
    stub = _Stub([_spec_json(
        "ربات من",
        [{"type": "quiz", "params": {}, "req": ["r1"]}],
        [{"id": "r1", "want": "یه بازی جدید به بخش شروع اضافه شود", "part": "بخش شروع",
          "status": "covered", "features": ["quiz"]}])])
    orig = _patch_llm(stub)
    try:
        th, merged, _ = ai.ask_llm("یه بازی جدید هم به بخش شروع ربات اضافه کن", base)
    finally:
        ai.llm_post = orig
    assert stub.calls == 1, "درخواست نیمه‌منطبق باید با مدل فهمیده شود"
    nodes = merged["nodes"]
    # هیچ بخش قبلی حذف یا بازنویسی نشده
    assert base_nodes <= set(nodes), f"بخش‌های قبلی تخریب شد: {base_nodes - set(nodes)}"
    assert nodes["quiz"]["text"] == quiz_text_before, "بخش قبلی کوییز بازنویسی شد"
    # نمونهٔ تازه با شناسهٔ یکتا اضافه شد (نه برخورد «بخش تکراری»)؛ دکمهٔ منوی شروع به همان نمونهٔ تازه وصل است
    new_goto = None
    for row in nodes["start"]["buttons"]:
        for b in row:
            if b.get("goto") and b["goto"] not in base_nodes:
                new_goto = b["goto"]
    assert new_goto and new_goto in nodes, "بازی جدید به منوی شروع وصل نشد"
    assert new_goto != "quiz", "نمونهٔ تازه شناسهٔ یکتا نگرفت"
    assert str(th).count("شناسهٔ جدید") >= 1, "ادغام باید تازه‌نام‌شدن را شفاف بگوید"
    # پذیرش موتور روی کانفیگ ادغام‌شده
    import engine_accept
    acc = engine_accept.run_acceptance(merged, ["quiz", "wheel", "wallet"])
    assert not acc, f"پذیرش موتور بعد از ادغام شکست خورد: {acc[:1]}"


# ── ۴-الف) قابلیت واقعاً پشتیبانی‌نشده: توقف قبل از توکن + گزارش ادمین ──
@T("04a unsupported capability -> honest ENGINE_LIMIT before build")
def _():
    import mother
    uid = "u_cov_a"
    _mk_user(uid)
    jid = "job_cov_a"
    _mk_job(jid, uid, "ربات پرداخت با درگاه بانکی زرین پال بساز")
    mother.gen_job(jid, uid, None, "ربات پرداخت با درگاه بانکی زرین پال بساز", 100)
    j = core.db.jobs.find_one({"_id": jid})
    assert j["status"] == "review", f"وضعیت: {j['status']}"
    assert j.get("preflight"), "پیش‌بررسی ثبت نشد"
    g0 = (j.get("gaps") or [{}])[0]
    assert g0.get("kind") == "ENGINE_LIMIT", g0
    assert "بانکی" in (g0.get("want") or ""), g0
    # گزارش ادمین ثبت شده (db.gaps) و به نقشهٔ توسعه رفته
    assert core.db.gaps.find_one({"uid": uid}), "گزارش ادمین ثبت نشد"
    assert core.db.roadmap.find_one({"_id": "engine:pay.bank_gateway"}), "نقشهٔ توسعه ثبت نشد"
    # هیچ رباتی ساخته نشده و توکنی کسر نشده
    u = core.db.users.find_one({"_id": uid})
    assert (u.get("tokens") or 0) == 5000, "توکن کسر شد"
    assert core.db.bots.count_documents({"owner": uid}) == 0, "ربات ناقص ساخته شد"
    # لغو کاربر → بدون هزینه
    core.db.jobs.update_one({"_id": jid}, {"$set": {"status": "cancelled"}})


# ── ۴-ب) اعلام صادقانهٔ مدل → تأیید کاربر → فقط بقیهٔ درخواست ساخته می‌شود ──
@T("04b model-declared catalog_missing -> review then partial honest build")
def _():
    import mother, ai
    uid = "u_cov_b"
    _mk_user(uid)
    prompt = "ربات فروشگاه بساز با مدیریت نظرات زیر پست‌های کانال"
    stub = _Stub([_spec_json(
        "فروشگاه من",
        [{"type": "shop", "params": {}, "req": ["r1"]}],
        [{"id": "r1", "want": "فروشگاه با ثبت سفارش", "part": "منو", "status": "covered", "features": ["shop"]},
         {"id": "r2", "want": "مدیریت نظرات زیر پست‌های کانال", "part": "—",
          "status": "catalog_missing", "why": "ماژول آمادهٔ نظرات کانال در کاتالوگ نیست", "features": []}])])
    orig = _patch_llm(stub)
    try:
        jid = "job_cov_b"
        _mk_job(jid, uid, prompt)
        mother.gen_job(jid, uid, None, prompt, 100)
        j = core.db.jobs.find_one({"_id": jid})
        assert j["status"] == "review" and j.get("preflight"), f"وضعیت: {j['status']}"
        kinds = [x.get("kind") for x in (j.get("gaps") or [])]
        assert "CATALOG_MISSING" in kinds, kinds
        assert core.db.bots.count_documents({"owner": uid}) == 0, "قبل از تأیید، رباتی ذخیره شد"
        # تأیید کاربر: همان محدودیت پذیرفته می‌شود و فقط بقیه ساخته می‌شود
        core.db.jobs.update_one({"_id": jid}, {"$set": {
            "status": "running", "preflight_ok": True, "accepted_gaps": ["مدیریت نظرات زیر پست‌های کانال"]}})
        mother.gen_job(jid, uid, None, prompt, 100)
        j2 = core.db.jobs.find_one({"_id": jid})
        assert j2["status"] == "done", f"وضعیت بعد از تأیید: {j2.get('status')} {j2.get('error', '')}"
        bot = core.db.bots.find_one({"_id": core.ObjectId(j2["bot"])})
        assert bot and "shop" in bot["config"]["nodes"], "بخش قابل‌اجرا ساخته نشد"
        assert "پوشش درخواست" in (bot.get("thinking") or ""), "گزارش پوشش در متن تحویل نیست"
        assert "1 از 2" in (bot.get("thinking") or ""), "شمار پوشش نادرست است"
    finally:
        ai.llm_post = orig


# ── ۴-ج) نگهبان عمومی‌سازی: ربات عمومی جای درخواست واقعی تحویل داده نمی‌شود ──
@T("04c generic-only guard: covered claim with generic features is rejected")
def _():
    import mother, ai
    uid = "u_cov_c"
    _mk_user(uid)
    prompt = "ربات مدیریت کانال با آمار اعضا بساز"
    # مدل خواستهٔ اصلی را حذف و با منوی عمومی پر کرده است
    stub = _Stub([_spec_json(
        "ربات من",
        [{"type": "start_menu", "params": {}, "req": ["r1"]}, {"type": "about", "params": {}, "req": ["r1"]}],
        [{"id": "r1", "want": "مدیریت کانال با آمار اعضا", "part": "منو", "status": "covered",
          "features": ["start_menu", "about"]}])])
    orig = _patch_llm(stub)
    try:
        jid = "job_cov_c"
        _mk_job(jid, uid, prompt)
        mother.gen_job(jid, uid, None, prompt, 100)
        j = core.db.jobs.find_one({"_id": jid})
        assert j["status"] == "review", f"وضعیت: {j['status']}"
        g0 = (j.get("gaps") or [{}])[0]
        assert g0.get("kind") in ("CATALOG_MISSING", "ENGINE_LIMIT"), g0
        assert "مدیریت کانال" in (g0.get("want") or ""), g0
        assert core.db.bots.count_documents({"owner": uid}) == 0, "ربات عمومی به‌جای درخواست واقعی ساخته شد"
    finally:
        ai.llm_post = orig


# ── ۴-د) مدل نیازمندی را حذف کند: retry با بازخورد → خطای صادقانه؛ بدون تحویل ناقص ──
@T("04d dropped requirement -> retry with feedback -> honest error, no partial delivery")
def _():
    import ai, mother
    uid = "u_cov_d"
    _mk_user(uid)
    prompt = "یه ربات فروشگاه لوازم جانبی موبایل با فرم سفارش اختصاصی بساز"          # rest کم → مسیر مدل
    # پاسخ ناقص: ادعای پوشش r2 بدون هیچ قابلیت اجرایی
    bad = _spec_json(
        "فروشگاه من",
        [{"type": "shop", "params": {}, "req": ["r1"]}, {"type": "about", "params": {}, "req": ["r1"]}],
        [{"id": "r1", "want": "فروشگاه لوازم جانبی با فرم سفارش", "part": "منو", "status": "covered", "features": ["shop"]},
         {"id": "r2", "want": "پشتیبانی اختصاصی", "part": "منو", "status": "covered", "features": []}])
    stub = _Stub([bad, bad])               # تلاش اول و جایگزین هر دو ناقص
    orig = _patch_llm(stub)
    try:
        jid = "job_cov_d"
        _mk_job(jid, uid, prompt)
        mother.gen_job(jid, uid, None, prompt, 100)
        j = core.db.jobs.find_one({"_id": jid})
        assert stub.calls == 2, f"باید دو تلاش با بازخورد می‌شد: {stub.calls}"
        assert len(stub.msgs) == 3 and "ایرادها" in stub.msgs[-1]["content"], "بازخورد خطاها به تلاش دوم نرسید"
        assert j["status"] == "error", f"وضعیت: {j['status']}"
        assert "پوشش داده شد ادعا شده" in (j.get("error") or ""), "خطای کاربر باید علت واقعی (حذف نیازمندی) را بگوید"
        assert core.db.bots.count_documents({"owner": uid}) == 0, "نسخهٔ ناقص تحویل شد"
        u = core.db.users.find_one({"_id": uid})
        assert (u.get("tokens") or 0) == 5000, "توکن کسر شد"
    finally:
        ai.llm_post = orig


if __name__ == "__main__":
    ok = 0
    for name, fn in R:
        try:
            fn()
            print("PASS:", name)
            ok += 1
        except Exception as e:
            import traceback
            print("FAIL:", name)
            traceback.print_exc()
            sys.exit(1)
    print(f"\nALL PASSED ({ok} scenarios)")
