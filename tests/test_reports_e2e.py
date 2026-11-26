# -*- coding: utf-8 -*-
"""
tests/test_reports_e2e.py — بازسازی کامل جریان واقعی ۳ گزارش ادمین (BUILD 3.6.2)

گزارش‌های واقعی: 6b0809f29325 · 6b080a279325 · 6b080b0d9325
درخواست کاربر: «میخثام یه ربات مدیرت کامال بسازی که در سر زمان هاب مشخص پست مد نظرمو تو کانال پست کنه»
رفتار قدیمی (باگ): ۴ بار تست → ۳ گزارش متفاوت → «هیچ مدلی پاسخ معتبری برای برنامه‌ریزی Spec نداد» →
                   یک بار هم ساخته شد ولی خروجی ناقص بود (پست زمان‌بندی‌شده اجرا نمی‌شد و رسانده شد!)
رفتار درست:
  ۱) پیش‌بررسی قطعی قبل از صرف توکن: پست‌گذاری زمان‌بندی‌شده در کانال → ENGINE_LIMIT (channel.auto_post)
  ۲) تصمیم با کاربر: پذیرش محدودیت یا لغو؛ بدون ربات ناقص و بدون کسر توکن
  ۳) بعد از پذیرش: فقط بخش قابل‌اجرا (مدیریت) ساخته می‌شود و خواستهٔ اجرانشدنی صادقانه در گزارش پوشش می‌ماند
  ۴) اگر مدل قابلیتی خارج از کاتالوگ بسازد → salvage قطعی؛ کل ساخت دیگر نمی‌شکند
اجرا:  python3 tests/test_reports_e2e.py
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


REQUEST = "میخثام یه ربات مدیرت کامال بسازی که در سر زمان هاب مشخص پست مد نظرمو تو کانال پست کنه"


class _Stub:
    """جایگزین ai.llm_post؛ پاسخ‌های از پیش تعیین‌شده به‌ترتیب."""

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


def _spec_json(name, feats, reqs):
    return json.dumps({"version": 1, "intent": "create", "name": name, "emoji": False, "payments": False,
                       "requirements": reqs, "features": feats, "texts": {}}, ensure_ascii=False)


def _mk_user(uid, tokens=5000):
    core.db.users.update_one({"_id": uid}, {"$set": {"tokens": tokens, "spent": 0}}, upsert=True)


def _mk_job(jid, uid, prompt):
    core.db.jobs.insert_one({"_id": jid, "uid": uid, "status": "running", "kind": "bot_build", "hold": 0,
                             "prompt": prompt, "t": core.now()})


# ── گزارش ۱: قابلیت «scheduler» خارج از کاتالوگ ──
@T("report-1 scheduler -> preflight first, salvage after accept, honest partial build")
def _():
    import mother, ai
    uid, jid = "u_rep1", "job_rep1"
    _mk_user(uid)
    _mk_job(jid, uid, REQUEST)

    # گام ۱: جریان واقعی — پیش‌بررسی قطعی باید قبل از هر فراخوانی مدل بایستد
    stub = _Stub([])   # هیچ پاسخی لازم نیست؛ نباید به مدل برسد
    orig = ai.llm_post
    ai.llm_post = stub
    try:
        mother.gen_job(jid, uid, None, REQUEST, 100)
        j = core.db.jobs.find_one({"_id": jid})
        assert stub.calls == 0, f"پیش‌بررسی باید قبل از توکن می‌ایستاد؛ {stub.calls} فراخوانی مدل شد"
        assert j["status"] == "review" and j.get("preflight"), f"وضعیت: {j['status']}"
        g0 = (j.get("gaps") or [{}])[0]
        assert g0.get("kind") == "ENGINE_LIMIT" and g0.get("feature") == "channel.auto_post", g0
        assert "زمان‌بندی" in (g0.get("want") or ""), g0
        assert core.db.bots.count_documents({"owner": uid}) == 0, "قبل از پذیرش رباتی ساخته شد"
        assert (core.db.users.find_one({"_id": uid}).get("tokens") or 0) == 5000, "توکن کسر شد"

        # گام ۲: کاربر محدودیت را می‌پذیرد → مدل خروجی واقعی گزارش ۱ را می‌دهد (scheduler + group_manager)
        core.db.jobs.update_one({"_id": jid}, {"$set": {
            "status": "running", "preflight_ok": True, "accepted_gaps": [g0["want"]]}})
        model_out = _spec_json(
            "ربات مدیریت کانال",
            [{"type": "scheduler", "params": {}, "req": ["r1"], "note": "در سر وقت‌های مشخص پست در کانال"},
             {"type": "group_manager", "params": {}, "req": ["r2"]}],
            [{"id": "r1", "want": "در سر وقت‌های مشخص پست مورد نظر کاربر به کانال ارسال شود",
              "part": "کانال", "status": "covered", "features": ["scheduler"]},
             {"id": "r2", "want": "ابزار مدیریت گروه و اعضا", "part": "منو", "status": "covered",
              "features": ["group_manager"]}])
        stub2 = _Stub([model_out])
        ai.llm_post = stub2
        mother.gen_job(jid, uid, None, REQUEST, 100)
        j2 = core.db.jobs.find_one({"_id": jid})
        assert j2["status"] == "done", f"بعد از پذیرش باید ساخته می‌شد: {j2.get('status')} {j2.get('error', '')}"
        bot = core.db.bots.find_one({"_id": core.ObjectId(j2["bot"])})
        assert bot and ("gm_help" in bot["config"]["nodes"]), "بخش قابل‌اجرا ساخته نشد"
        th = bot.get("thinking") or ""
        assert "پوشش درخواست" in th, "گزارش پوشش در متن تحویل نیست"
        assert "1 از 2" in th, f"شمار پوشش نادرست: {th[-300:]}"
        # گزارش پوشش باید همان خواستهٔ اجرانشدنی را صادقانه بنامد
        assert "پست" in th, "خواستهٔ اجرانشدنی در گزارش پوشش نیامد"
    finally:
        ai.llm_post = orig


# ── گزارش ۲: قابلیت «scheduled_posts» + خروجی دوم ناقص (مدل فقط قابلیت نامعتبر می‌دهد) ──
@T("report-2 scheduled_posts-only model output -> honest retry then honest error, no delivery")
def _():
    import mother, ai
    uid, jid = "u_rep2", "job_rep2"
    _mk_user(uid)
    _mk_job(jid, uid, REQUEST)
    orig = ai.llm_post
    try:
        # کاربر قبلاً محدودیت را پذیرفته؛ ولی مدل هر بار فقط قابلیت خارج از کاتالوگ می‌دهد
        core.db.jobs.update_one({"_id": jid}, {"$set": {
            "status": "running", "preflight_ok": True,
            "accepted_gaps": ["پست‌گذاری خودکار یا زمان‌بندی‌شده در کانال/گروه در زمان‌های مشخص"]}})
        only_bad = _spec_json(
            "ربات مدیریت کانال",
            [{"type": "scheduled_posts", "params": {"channel": "@mychannel"}, "req": ["r1"]}],
            [{"id": "r1", "want": "پست‌گذاری زمان‌بندی‌شده در کانال", "part": "کانال",
              "status": "covered", "features": ["scheduled_posts"]}])
        stub = _Stub([only_bad, only_bad])          # تلاش اول و جایگزین هر دو نامعتبر
        ai.llm_post = stub
        mother.gen_job(jid, uid, None, REQUEST, 100)
        j = core.db.jobs.find_one({"_id": jid})
        assert stub.calls == 2, f"یک تلاش جایگزین کنترل‌شده: {stub.calls}"
        # بازخورد قابل‌اقدام به تلاش دوم رسیده باشد
        last = stub.msgs[-1]["content"]
        assert "کاتالوگ" in last and "catalog_missing" in last, "بازخورد دقیق به تلاش دوم نرسید"
        assert j["status"] == "error", f"وضعیت: {j['status']}"
        assert "هیچ قابلیت واقعی کاتالوگ" in (j.get("error") or "") or "features" in (j.get("error") or ""), \
            f"خطا باید علت واقعی را بگوید: {j.get('error')}"
        assert core.db.bots.count_documents({"owner": uid}) == 0, "ربات ناقص تحویل شد"
        assert (core.db.users.find_one({"_id": uid}).get("tokens") or 0) == 5000, "توکن کسر شد"
    finally:
        ai.llm_post = orig


# ── گزارش ۳: «features خالی یا نامعتبر است» ──
@T("report-3 empty features -> actionable feedback retry; converges when model fixes it")
def _():
    import mother, ai
    uid, jid = "u_rep3", "job_rep3"
    _mk_user(uid)
    _mk_job(jid, uid, REQUEST)
    orig = ai.llm_post
    try:
        core.db.jobs.update_one({"_id": jid}, {"$set": {
            "status": "running", "preflight_ok": True,
            "accepted_gaps": ["پست‌گذاری خودکار یا زمان‌بندی‌شده در کانال/گروه در زمان‌های مشخص"]}})
        empty = _spec_json(
            "ربات مدیریت",
            [],
            [{"id": "r1", "want": "در سر وقت‌های مشخص پست در کانال بگذارد", "part": "کانال",
              "status": "covered", "features": []}])
        fixed = _spec_json(
            "ربات مدیریت",
            [{"type": "group_manager", "params": {}, "req": ["r2"]}],
            [{"id": "r1", "want": "در سر وقت‌های مشخص پست در کانال بگذارد", "part": "کانال",
              "status": "catalog_missing", "why": "زمان‌بند پست کانال در کاتالوگ نیست", "features": []},
             {"id": "r2", "want": "ابزار مدیریت گروه", "part": "منو", "status": "covered",
              "features": ["group_manager"]}])
        stub = _Stub([empty, fixed])               # تلاش اول خالی؛ تلاش دوم با بازخورد درست می‌شود
        ai.llm_post = stub
        mother.gen_job(jid, uid, None, REQUEST, 100)
        j = core.db.jobs.find_one({"_id": jid})
        assert stub.calls == 2, f"دو تلاش: {stub.calls}"
        assert j["status"] == "done", f"بعد از اصلاح مدل باید ساخته می‌شد: {j.get('status')} {j.get('error', '')}"
        bot = core.db.bots.find_one({"_id": core.ObjectId(j["bot"])})
        assert bot and ("gm_help" in bot["config"]["nodes"])
        th = bot.get("thinking") or ""
        assert "پوشش درخواست" in th and "1 از 2" in th, th[-300:]
    finally:
        ai.llm_post = orig


# ── ادعای پوشش دروغین با قابلیت غیرعمومی: جلوگیری از «ساخته شد ولی ناقص بود» ──
@T("report-x fake covered claim with group_manager cannot hide unsupported scheduling")
def _():
    """اگر مدل ادعا کند group_manager پست زمان‌بندی‌شده را پوشش می‌دهد، اثبات قطعی _STATIC_LIMITS ادعا را باطل می‌کند؛
    (دقیقاً همان «یک بار ساخت ولی خروجی ناقص بود مطابق درخواست»)"""
    import coverage as _cov
    sp = {
        "version": 1, "intent": "create", "name": "x",
        "features": [{"type": "group_manager", "params": {}, "req": ["r1"]}],
        "requirements": [{"id": "r1", "want": "در سر وقت‌های مشخص پست مد نظرمو تو کانال پست کنه",
                          "part": "کانال", "status": "covered", "features": ["group_manager"]}],
    }
    unmet = _cov.unmet_items(sp, REQUEST)
    assert unmet and unmet[0]["kind"] == "ENGINE_LIMIT", unmet
    assert unmet[0]["want"] == "پست‌گذاری خودکار یا زمان‌بندی‌شده در کانال/گروه در زمان‌های مشخص", unmet[0]


if __name__ == "__main__":
    ok = 0
    for name, fn in R:
        try:
            fn()
            print("PASS:", name)
            ok += 1
        except Exception:
            import traceback
            print("FAIL:", name)
            traceback.print_exc()
            sys.exit(1)
    print(f"\nALL PASSED ({ok} scenarios)")
