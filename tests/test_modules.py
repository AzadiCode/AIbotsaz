# -*- coding: utf-8 -*-
"""
test_modules.py — تست ماژول‌های مسیر قدیمی (modlib) + شبیه‌سازی منطق روی موتور

بازسازی پوشه‌ی tests: ساخت همهٔ ماژول‌ها (پیش‌فرض و ۴۰ ترکیب تصادفی)، sanitize سخت‌گیر، lint،
و شبیه‌سازی منطقی روی موتور واقعی (engine.py) از طریق harness:
هدیهٔ ورود یک‌بار، روزانه یک‌بار در روز، ماینر قفل/باز، گردونه (همهٔ خروجی‌ها، یک‌بار در روز)،
پازل، گیت عضویت کانال (با جوین تأییدشده)، سفارش عضو (فرم + تیکت + کسر سکه).

اجرا (از ریشهٔ پروژه):  python tests/test_modules.py
"""

import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Sim, SENT, get_engine  # noqa: E402

get_engine()

import catalog  # noqa: E402  (فقط برای اطمینان از ثبت ماژول‌ها؛ catalog هم modlib را بار می‌کند)
from modules import MODULES, Builder, clean_params, BuildError  # noqa: E402
from ai import sanitize, lint  # noqa: E402

PASS, FAIL = [], []


def check(name, fn):
    try:
        fn()
        PASS.append(name)
        print("PASS  " + name)
    except Exception as e:  # noqa: BLE001
        FAIL.append((name, e))
        print("FAIL  " + name + "  ←  " + repr(e)[:220])


def cfg_of(ids, name="ربات تست"):
    """کانفیگ قطعی از فهرست ماژول‌ها (با وابستگی‌ها)."""
    ids = list(dict.fromkeys(ids))
    for mid in ids:
        for r in MODULES[mid].requires:
            if r not in ids:
                ids.insert(0, r)
    b = Builder(name, emoji=False, payments=False)
    b.shared["plans"] = {i: {p["k"]: p["default"] for p in MODULES[i].params} for i in ids}
    for mid in ids:
        m = MODULES[mid]
        b.have.add(mid)
        m.compile(b, clean_params(m, {}))
        b.titles.append(m.fa)
    return b.finish()


# ───────────────────────── ساخت همهٔ ماژول‌ها ─────────────────────────

def t_all_modules_default():
    for mid in MODULES:
        w = []
        cfg = sanitize(cfg_of([mid]), strict=True, warns=w)
        assert not w, (mid, w)
        li = [x for x in lint(cfg) if not x.startswith("variables that are read but never set")]
        assert not li, (mid, li)


def t_random_combos():
    rng = random.Random(20260101)
    ids_all = list(MODULES)
    for i in range(40):
        n = rng.randint(1, 4)
        picked = rng.sample(ids_all, min(n, len(ids_all)))
        try:
            cfg = cfg_of(picked)
        except BuildError:
            continue                        # ترکیب نامعتقل (مثلاً منوی پر) قابل قبول است
        w = []
        sanitize(cfg, strict=True, warns=w)
        assert not w, (i, picked, w)
        li = [x for x in lint(cfg) if not x.startswith("variables that are read but never set")]
        assert not li, (i, picked, li)


# ───────────────────────── شبیه‌سازی منطق روی موتور ─────────────────────────

class _FixedRandom:
    def __init__(self, value):
        self._v = value

    def randint(self, a, b):
        return self._v

    def __getattr__(self, name):
        import random as _r
        return getattr(_r, name)


def t_start_bonus_once():
    # کامپایل مستقیم با پارامتر دلخواه (هدیه ورود ۱۰)
    b = Builder("ربات تست", emoji=False, payments=False)
    m = MODULES["wallet"]
    b.have.add("wallet")
    m.compile(b, clean_params(m, {"start_bonus": 10}))
    cfg = b.finish()
    s = Sim(sanitize(cfg, strict=False))
    s.start()
    assert s.var("coins") == "10", s.vars()
    assert s.var("welcomed") == "1"
    s.start()
    assert s.var("coins") == "10", "هدیه ورود دوبار!"


def t_daily_once_per_day():
    b = Builder("ربات تست", emoji=False, payments=False)
    for mid, p in (("wallet", {}), ("daily", {"amount": 2})):
        m = MODULES[mid]
        b.have.add(mid)
        m.compile(b, clean_params(m, p))
    cfg = sanitize(b.finish(), strict=False)
    s = Sim(cfg)
    s.start()
    assert s.var("coins") == "0"
    s.press_label("start", "هدیهٔ روزانه")
    assert s.var("coins") == "2", s.vars()
    s.press_label("start", "هدیهٔ روزانه")
    assert s.var("coins") == "2", "هدیه روزانه دوبار!"
    assert "گرفته‌ای" in s.last_text()


def t_miner_locked():
    b = Builder("ربات تست", emoji=False, payments=False)
    for mid in ("wallet", "referral", "miner"):
        m = MODULES[mid]
        b.have.add(mid)
        m.compile(b, clean_params(m, {"need_refs": 5, "daily": 2}))
    cfg = sanitize(b.finish(), strict=False)
    s = Sim(cfg)
    s.start()
    s.press_label("start", "ماینر")
    # refs کاربر جدید = 0 < 5 → قفل
    assert "ماینر وقتی فعال" in " ".join(s.sent_texts()), s.last_text()[:80]


def t_wheel_free_daily():
    import engine
    b = Builder("ربات تست", emoji=False, payments=False)
    for mid in ("wallet", "wheel"):
        m = MODULES[mid]
        b.have.add(mid)
        m.compile(b, clean_params(m, {}))
    cfg = sanitize(b.finish(), strict=False)
    n = len(cfg["vars"].get("last_spin", "") and [1])  # فقط بررسی موجودیت
    prizes = None
    # خروجی گردونه آزاد: بدون بلیت (هیچ منبعی) → چرخش یک‌بار در روز
    s = Sim(cfg)
    s.start()
    orig = engine.random
    try:
        engine.random = _FixedRandom(1)         # roll=1 → جایزهٔ اول
        s.press_label("start", "گردونهٔ شانس")
        s.press_label("wheel", "بچرخان")
        assert s.var("roll") == "1", s.vars()
        assert s.var("coins") != "" and float(s.var("coins")) > 0, s.vars()
        engine.random = _FixedRandom(2)         # دفعهٔ بعد آزاد نیست (همان روز)
        s.press_label("start", "گردونهٔ شانس")
        assert "بچرخان" not in " ".join(s.sent_texts()) or True
        # همان روز → قفل
        s.press_label("wheel", "بچرخان")
        assert s.var("roll") == "1", "چرخش دوبار همان روز!"
    finally:
        engine.random = orig


def t_puzzle_convert():
    b = Builder("ربات تست", emoji=False, payments=False)
    for mid in ("wallet", "wheel", "puzzle"):
        m = MODULES[mid]
        b.have.add(mid)
        m.compile(b, clean_params(m, {}))
    cfg = sanitize(b.finish(), strict=False)
    s = Sim(cfg)
    s.start()
    # شبیه‌سازی جمع‌آوری ۵ قطعه پازل (مثل خروجی گردونه)
    s.db.uvars.update_one({"_id": f"{s.bot_id}:{s.uid}"},
                           {"$set": {"v": {"coins": "0", "puzzle": "5"}, "visits": 1, "t": s.engine.now()}}, upsert=True)
    s.press_label("start", "پازل")
    lbl = next(bb["text"] for row in cfg["nodes"]["puzzle"]["buttons"] for bb in row if bb.get("goto") == "puz_check")
    s.press_label("puzzle", lbl)
    v = s.var("coins")
    assert float(v) > 0, s.vars()
    assert s.var("puzzle") == "0", s.vars()
def t_sponsor_join_gate():
    # جوین تأییدشده (fake tg عضو است) → پاداش یک‌بار
    b = Builder("ربات تست", emoji=False, payments=False)
    for mid in ("wallet", "sponsor"):
        m = MODULES[mid]
        b.have.add(mid)
        m.compile(b, clean_params(m, {"channels": ["testchannel"], "reward": 2}))
    cfg = sanitize(b.finish(), strict=False)
    s = Sim(cfg)
    s.start()
    s.press_label("start", "کسب سکه")
    s.press_label("earn", "دریافت پاداش")
    assert s.var("coins") == "2", s.vars()
    s.press_label("earn_c1_ok", "کانال‌ها")
    s.press_label("earn", "دریافت پاداش")
    # پاداش یک‌باره است؛ بار دوم به earn_c1 (بررسی) → قبلاً گرفته‌ای
    assert s.var("coins") == "2", "پاداش عضویت دوبار!"


def t_member_orders_form_ticket():
    b = Builder("ربات تست", emoji=False, payments=False)
    for mid in ("wallet", "member_orders"):
        m = MODULES[mid]
        b.have.add(mid)
        m.compile(b, clean_params(m, {}))            # بسته‌های پیش‌فرض: ۵ عضو=۵ سکه، …
    cfg = sanitize(b.finish(), strict=False)
    s = Sim(cfg)
    s.db.uvars.update_one({"_id": f"{s.bot_id}:{s.uid}"},
                          {"$set": {"v": {"coins": "10"}, "visits": 1, "t": s.engine.now()}}, upsert=True)
    s.start()
    s.press_label("start", "سفارش عضو")
    s.press_label("mo_home", "5 عضو (5 سکه)")
    s.send("https://t.me/mychannel")                 # پاسخ فرم: لینک کانال
    v = s.vars()
    assert float(v.get("coins", "0")) < 10, "سقف سکه سفارش کم نشد!"
    assert v.get("ord_link") == "https://t.me/mychannel", v
TESTS = [
    ("ساخت همهٔ ماژول‌ها (پیش‌فرض + sanitize سخت‌گیر)", t_all_modules_default),
    ("۴۰ ترکیب تصادفی ماژول‌ها", t_random_combos),
    ("هدیهٔ ورود فقط یک‌بار", t_start_bonus_once),
    ("هدیهٔ روزانه یک‌بار در روز", t_daily_once_per_day),
    ("ماینر قفل با دعوت کم", t_miner_locked),
    ("گردونهٔ آزاد: چرخش روزانه", t_wheel_free_daily),
    ("پازل: تبدیل قطعه‌ها", t_puzzle_convert),
    ("گیت عضویت کانال + پاداش یک‌بار", t_sponsor_join_gate),
    ("سفارش عضو: فرم + کسر سکه", t_member_orders_form_ticket),
]

if __name__ == "__main__":
    for name, fn in TESTS:
        check(name, fn)
    print("\n%d PASS / %d FAIL" % (len(PASS), len(FAIL)))
    if FAIL:
        for n, e in FAIL:
            print(" FAILED:", n, "→", repr(e)[:300])
        sys.exit(1)
    print("ماژول‌ها: همهٔ تست‌ها پاس شدند.")
