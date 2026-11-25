# -*- coding: utf-8 -*-
"""
test_manual_new.py — تست ساخت دستی ربات خالی (POST /api/bots/new)

استودیو از همان اول کامل باز می‌شود؛ این مسیر بدون هوش مصنوعی و بدون مصرف توکن،
اسکلت ربات (شروع + درباره + پاسخ پیش‌فرض) را می‌سازد تا کاربر دستی شروع کند.

بررسی‌ها:
  • ربات بدون توکن ساخته می‌شود (cost=0 و کیف دست نمی‌خورد)
  • کانفیگ خروجی sanitize کامل و معتبر است (start/fallback معتبر، ۳ بخش)
  • سقف تعداد ربات رعایت می‌شود
  • نام دلخواه هم اعمال می‌شود

اجرا (از ریشهٔ پروژه):  python tests/test_manual_new.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import get_engine  # noqa: E402

get_engine()

import core  # noqa: E402
from ai import sanitize  # noqa: E402

UID = 557701
H = {"X-Init-Data": "fake"}


def setup():
    core.verify_init_data = lambda d: {"id": UID, "first_name": "تست", "username": "tester"} if d else None
    core.ensure_user(UID)


def t_manual_new_free():
    setup()
    before = core.wallet_info(UID)["tokens"]
    c = core.app.test_client()
    r = c.post("/api/bots/new", json={"name": "فروشگاه تست"}, headers=H)
    d = r.get_json()
    assert r.status_code == 200, (r.status_code, d)
    assert d.get("cost") == 0, d
    assert core.wallet_info(UID)["tokens"] == before, "توکنی کسر شد"
    bot = d["bot"]
    cfg = sanitize(bot["config"], strict=True)
    assert len(cfg["nodes"]) == 3, cfg["nodes"].keys()
    assert cfg["start"] in cfg["nodes"] and cfg["fallback"] in cfg["nodes"], cfg
    assert cfg["name"] == "فروشگاه تست", cfg["name"]
    # بخش شروع باید دکمه‌ی مسیر داشته باشد تا از اول بن‌بست نباشد
    btns = [b for row in cfg["nodes"][cfg["start"]]["buttons"] for b in row]
    assert btns and all(b["goto"] in cfg["nodes"] for b in btns), btns


def t_manual_new_cap():
    setup()
    c = core.app.test_client()
    lim = core.limits_of(UID)["nodes"]
    assert lim >= 3, lim
    # تا سقف ربات پر می‌کنیم
    have = core.db.bots.count_documents({"owner": UID})
    for _ in range(core.max_bots(UID) - have):
        core.db.bots.insert_one({"owner": UID, "name": "پرکن", "config": sanitize(
            {"name": "پرکن", "start": "start", "fallback": "fallback",
             "nodes": {"start": {"title": "شروع", "text": "سلام", "buttons": []}}}, strict=True),
            "thinking": "", "versions": [], "active": False, "secret": "s", "created": core.now(), "updated": core.now()})
    r = c.post("/api/bots/new", json={}, headers=H)
    d = r.get_json()
    assert r.status_code == 400 and "حداکثر" in d.get("error", ""), (r.status_code, d)


TESTS = [
    ("ساخت دستی: رایگان و معتبر", t_manual_new_free),
    ("ساخت دستی: سقف تعداد ربات", t_manual_new_cap),
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
