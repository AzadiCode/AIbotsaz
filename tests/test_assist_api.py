# -*- coding: utf-8 -*-
"""
test_assist_api.py — تست سرتاسری دستیار استودیو (API) و مسیرهای مرتبط

با initData جعلی (verify_init_data پچ‌شده) همان مسیرهای واقعی Flask را صدا می‌زند:
  • POST /api/bots/<id>/assist      — پیش‌نمایش قطعی/رایگان پچ روی کانفیگ فعلی
  • POST /api/bots/<id>/assist/apply — اعمال + نسخه‌ی برگشت (versions)
  • POST /api/plan                  — پیش‌نمایش آنی (قابلیت‌های کاتالوگ + ماژول‌ها)

اجرا (از ریشهٔ پروژه):  python tests/test_assist_api.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import get_engine  # noqa: E402

get_engine()

import core  # noqa: E402
from modules import Builder  # noqa: E402
from ai import sanitize  # noqa: E402

UID = 555001


def setup():
    core.verify_init_data = lambda d: {"id": UID, "first_name": "تست", "username": "tester"} if d else None
    core.ensure_user(UID)
    b = Builder("ربات من", False, False)
    b.node("about", "درباره ما", [b.back()], title="درباره")
    b.menu_add(10, "درباره ما", "about")
    cfg = sanitize(b.finish(), strict=False)
    return str(core.db.bots.insert_one({"owner": UID, "name": "ربات من", "config": cfg, "thinking": "",
                                        "versions": [], "active": False, "secret": "s", "token_enc": "x",
                                        "created": core.now(), "updated": core.now()}).inserted_id)


def t_assist_flow():
    bot_id = setup()
    c = core.app.test_client()
    H = {"X-Init-Data": "fake"}
    r = c.post(f"/api/bots/{bot_id}/assist", json={"request": "گردونه و بازی تاس اضافه کن"}, headers=H)
    d = r.get_json()
    assert r.status_code == 200 and d.get("mode") == "spec", d
    assert d.get("free") is True
    assert any("خودکار" in p["text"] for p in d["preview"]), d["preview"]
    assert d["count"] >= 10 and d["new_nodes"]
    r2 = c.post(f"/api/bots/{bot_id}/assist/apply", json={"spec": d["spec"]}, headers=H)
    d2 = r2.get_json()
    assert r2.status_code == 200 and d2.get("cards"), d2
    bot = core.db.bots.find_one({"_id": core.ObjectId(bot_id)})
    labels = [btn["text"] for row in bot["config"]["nodes"]["start"]["buttons"] for btn in row]
    assert "درباره ما" in labels and "بازی تاس" in labels and "گردونهٔ شانس" in labels, labels
    assert len(bot["versions"]) == 1, "نسخه‌ی برگشت ثبت نشد"
    assert not sanitize(bot["config"], strict=False).get("nodes") is None


def t_assist_no_match():
    bot_id = setup()
    c = core.app.test_client()
    r = c.post(f"/api/bots/{bot_id}/assist", json={"request": "رنگ دکمه‌ها را عوض کن"}, headers={"X-Init-Data": "fake"})
    d = r.get_json()
    assert r.status_code == 200 and d.get("mode") == "none", d


def t_assist_invalid_spec():
    bot_id = setup()
    c = core.app.test_client()
    r = c.post(f"/api/bots/{bot_id}/assist/apply", json={"spec": {"features": [{"type": "bank.gateway"}]}},
               headers={"X-Init-Data": "fake"})
    d = r.get_json()
    assert r.status_code == 400, (r.status_code, d)          # enum بسته: ورودی خام رد می‌شود


def t_plan():
    c = core.app.test_client()
    r = c.post("/api/plan", json={"prompt": "ربات بازی تاس و حدس عدد بساز"}, headers={"X-Init-Data": "fake"})
    d = r.get_json()
    assert r.status_code == 200 and d.get("instant") is True, d
    assert "بازی تاس" in d.get("spec", []) and "حدس عدد" in d.get("spec", []), d


TESTS = [
    ("دستیار: پیش‌نمایش + اعمال + نسخهٔ برگشت", t_assist_flow),
    ("دستیار: بدون تطابق → mode=none", t_assist_no_match),
    ("دستیار: Spec خارج از enum رد می‌شود", t_assist_invalid_spec),
    ("/api/plan: کاتالوگ + ماژول‌ها", t_plan),
]

if __name__ == "__main__":
    PASS, FAIL = [], []
    for name, fn in TESTS:
        try:
            fn()
            PASS.append(name)
            print("PASS  " + name)
        except Exception as e:  # noqa: BLE001
            FAIL.append((name, e))
            print("FAIL  " + name + "  ←  " + repr(e)[:200])
    print("\n%d PASS / %d FAIL" % (len(PASS), len(FAIL)))
    if FAIL:
        sys.exit(1)
