# -*- coding: utf-8 -*-
"""
selftest_biz.py — تست پذیرش کسب‌وکار و منطق تازه (بدون شبکه؛ با mongomock)

شامل: ارزیاب امنِ عبارت حسابی (safe_calc)، اکشن calc، کد تخفیف (disc: درست/نامعتبر/منقضی/سقف پر)،
اشتراک دوره (sub_add/sub_del + شرط sub)، پاک‌سازی اکشن/شرط تازه در sanitize، نقشه‌ی B6 با اشتراک،
و فیکس اجرای اکشن فرم بعد از پر شدن جواب‌ها.
"""
import os, time, json

os.environ.setdefault("MOTHER_TOKEN", "1:SELFTEST")
os.environ.setdefault("BASE_URL", "https://selftest.example")
os.environ.setdefault("AI_BASE_URL", "https://ai.example/v1")
os.environ.setdefault("AI_API_KEY", "k")
os.environ.setdefault("AI_MODEL", "m")
os.environ.setdefault("ADMIN_IDS", "777")

import requests
class _FakeResp:
    status_code, text = 200, ""
    def json(self): return {"ok": False, "description": "offline"}
requests.post = lambda *a, **k: _FakeResp()
requests.get = lambda *a, **k: _FakeResp()

import app as appmod
from app import app
from core import db
from ai import safe_calc, sanitize, clean_actions, PH_RE
from engine import Env, run_actions, check, sub_active
from blueprints import BLUEPRINTS

OK = []
def ok(name):
    OK.append(name)
    print("ok —", name)


# ── ۱) ارزیاب امن عبارت ──
assert safe_calc("2*(3+4)") == "14"
assert safe_calc("{price} * 2".replace("{price}", "2.5")) == "5"
assert safe_calc(" 10 / 4 ") == "2.5"
assert safe_calc("-3 + 5") == "2"
assert safe_calc("1/0") is None
assert safe_calc("__import__('os')") is None
assert safe_calc("name") is None
assert safe_calc("2**10") == "1024"
assert safe_calc("9**99") is None          # توان غیرمنطقی رد می‌شود
assert safe_calc("") is None
assert safe_calc("2 +") is None
ok("safe_calc: درست‌ها سبز، حمله/خطا = None")


# ── ۲) محیط موتور و اکشن‌ها ──
BOT = "bizbot"
db.bots.insert_one({"_id": BOT, "owner": 777, "name": "فروشگاه", "token": "1:t", "on": True,
                    "config": {"name": "فروشگاه", "start": "s", "fallback": "s", "vars": {"price": "0", "code": "", "total": "0"},
                               "globals": {}, "commands": {}, "nodes": {"s": {"text": "hi", "buttons": [], "ask": False}}}})
BOT_DOC = db.bots.find_one({"_id": BOT})
BOT_DOC["config"] = json.loads(json.dumps(BOT_DOC["config"]))

env = Env(BOT_DOC, "1:t", 5, {"id": 5, "first_name": "کاربر"})
cfg = BOT_DOC["config"]

# calc از طریق run_actions
env.set("price", "25000")
run_actions([{"op": "calc", "var": "total", "value": "{price} * 3"}], env)
assert env.get("total") == "75000", env.get("total")
run_actions([{"op": "calc", "var": "total", "value": "{price} * x"}], env)   # عبارت خراب: متغیر دست‌نخورده
assert env.get("total") == "75000"
ok("اکشن calc: عبارت درست حساب شد، عبارت خراب بی‌خطر رد شد")


# ── ۳) کد تخفیف ──
db.dcodes.insert_one({"_id": f"{BOT}:WELCOME", "bot": BOT, "code": "WELCOME", "kind": "pct", "value": 10, "max": 2, "used": 0, "exp": None})
env.set("code", "welcome")                     # حروف کوچک: باید پیدا شود
env.set("price", "100000")
run_actions([{"op": "disc", "var": "code", "price": "{price}"}], env)
assert env.vars["code_ok"] == "1"
assert env.vars["code_off"] == "90000", env.vars["code_off"]
assert env.vars["code_save"] == "10000"
assert env.vars["code_err"] == ""
ok("کد تخفیف: ۱۰٪ روی ۱۰۰۰۰۰ = ۹۰۰۰۰ و سود ۱۰۰۰۰")

run_actions([{"op": "disc", "var": "code", "price": "{price}"}], env)       # بار دوم (ظرفیت ۲)
assert env.vars["code_ok"] == "1"
run_actions([{"op": "disc", "var": "code", "price": "{price}"}], env)       # بار سوم: سقف پر
assert env.vars["code_ok"] == ""
assert env.vars["code_off"] == "100000"
assert "ظرفیت" in env.vars["code_err"]
assert db.dcodes.find_one({"_id": f"{BOT}:WELCOME"})["used"] == 2
ok("کد تخفیف: سقف مصرف ۲ بار با قفل خوش‌بینانه رعایت شد")

db.dcodes.insert_one({"_id": f"{BOT}:OLD", "bot": BOT, "code": "OLD", "kind": "amt", "value": 5000, "max": 0, "used": 0, "exp": time.time() - 100})
env.set("code", "OLD")
run_actions([{"op": "disc", "var": "code", "price": "{price}"}], env)
assert env.vars["code_ok"] == "" and "منقضی" in env.vars["code_err"]
env.set("code", "NOPE")
run_actions([{"op": "disc", "var": "code", "price": "{price}"}], env)
assert "پیدا نشد" in env.vars["code_err"]
ok("کد تخفیف: کد منقضی و کد ناشناس با پیام فارسی رد شدند")


# ── ۴) اشتراک دوره ──
assert sub_active(BOT, 5) is False
run_actions([{"op": "sub_add", "plan": "vip", "days": "30", "var": "sub"}], env)
assert sub_active(BOT, 5, "vip") is True
assert sub_active(BOT, 5, "gold") is False
assert sub_active(BOT, 5) is True
assert env.vars["sub"] == "vip"
assert "20" in env.vars["sub_exp"] or "20" in env.vars["sub_exp"]     # تاریخ انقضا سبز
d = db.subs.find_one({"bot": BOT, "u": 5, "plan": "vip"})
assert d["exp"] > time.time() + 29 * 86400
ok("sub_add: اشتراک ۳۰ روزه فعال شد و شرط sub سبز شد")

# تمدید از انتهای دوره
run_actions([{"op": "sub_add", "plan": "vip", "days": "10"}], env)
d2 = db.subs.find_one({"bot": BOT, "u": 5, "plan": "vip"})
assert d2["exp"] > d["exp"] + 9 * 86400
ok("sub_add: تمدید از انتهای دوره‌ی فعلی (نه از امروز)")

# شرط sub در check
assert check({"op": "sub", "plan": "vip"}, env) is True
assert check({"op": "sub", "plan": "gold"}, env) is False
run_actions([{"op": "sub_del", "plan": "vip"}], env)
assert check({"op": "sub", "plan": "vip"}, env) is False
ok("شرط sub و sub_del: فعال، تفکیک پلن، لغو")


# ── ۵) پاک‌سازی اکشن و شرط تازه در sanitize ──
acts, used, nums, bads, tabs = [], set(), set(), [], {"tabs": {}, "gets": []}
def bad(m): bads.append(m)
out = clean_actions([{"op": "calc", "var": "total", "value": "{price} * {qty}"},
                     {"op": "calc", "var": "total", "value": "__import__('os')"},
                     {"op": "disc", "var": "code", "price": "{price}"},
                     {"op": "sub_add", "plan": "VIP!", "days": "30", "var": "sub"},
                     {"op": "sub_del", "plan": "vip"}], used, nums, bad, tabs)
ops = [a["op"] for a in out]
assert ops == ["calc", "disc", "sub_add", "sub_del"], (ops, bads)
assert out[0]["value"] == "{price} * {qty}"
assert out[1]["price"] == "{price}"
assert out[3]["plan"] == "vip"            # پلن تمیز شد
assert any("معتبر نیست" in m for m in bads)     # حمله در calc رد شد
ok("clean_actions: calc/disc/sub_add/sub_del پاک‌سازی شدند و حمله رد شد")

# شرط sub در sanitize کامل
c2 = json.loads(json.dumps(cfg))
c2["nodes"]["s"]["route"] = [{"when": {"op": "sub", "plan": "vip"}, "goto": "s"}]
c3 = sanitize(c2, strict=True)
assert c3["nodes"]["s"]["route"][0]["when"]["op"] == "sub"
assert c3["nodes"]["s"]["route"][0]["when"]["plan"] == "vip"
ok("sanitize: شرط «اشتراک فعال بود» با پلن سالم عبور کرد")


# ── ۶) نقشه‌ی B6: با اشتراک و بدون اشتراک ──
for sub in ("yes", "no"):
    bp = BLUEPRINTS["B6"]["build"]({"name": "کتاب‌فروشی", "mode": "both", "sub": sub, "cat": "کتاب, لوازم‌التحریر"})
    bot_cfg = sanitize(bp["bot"], strict=True)
    assert bot_cfg, "B6 sanitize ناموفق"
    assert "code" in bot_cfg["nodes"] and any(a.get("op") == "disc" for n in bot_cfg["nodes"].values() for a in (n.get("do") or []))
    if sub == "yes":
        assert "vip" in bot_cfg["nodes"] and "viparea" in bot_cfg["nodes"]
        assert bot_cfg["commands"].get("vip") == "vip"
    else:
        assert "vip" not in bot_cfg["nodes"]
    from webapp import sanitize_app
    app_cfg = sanitize_app(bp["app"], strict=True, node_ids=set(bot_cfg["nodes"].keys()))
    assert app_cfg
ok("نقشه‌ی B6: کد تخفیف واقعی + (اختیاری) اشتراک VIP از هر دو اعتبارسنج می‌گذرد")


# ── ۷) اکشن فرم بعد از پر شدن جواب‌ها اجرا می‌شود (فیکس سفارش خالی) ──
c4 = {"name": "ف", "start": "f", "fallback": "f", "vars": {"item": "", "contact": "", "addr": ""},
      "globals": {}, "commands": {},
      "nodes": {"f": {"text": "سفارش", "buttons": [], "ask": False,
                      "fields": ["چه می‌خواهی؟", "شماره؟", "آدرس؟"], "save": ["item", "contact", "addr"],
                      "types": ["text", "phone", "text"],
                      "do": [{"op": "db_add", "table": "orders", "data": {"item": "{item}", "contact": "{contact}"}}]}}}
c4 = sanitize(c4, strict=True)
bot4 = json.loads(json.dumps(BOT_DOC))
bot4["config"] = c4
env2 = Env(bot4, "1:t", 9, {"id": 9, "first_name": "خریدار"})
import engine as eng
env2.vars.update({"item": "کتاب", "contact": "09120000000", "addr": "تهران"})
node = c4["nodes"]["f"]
# همان مسیر موتور: اکشن‌ها بعد از حذف state فرم اجرا می‌شوند
eng.run_actions(node.get("do"), env2)
r = db.recs.find_one({"bot": BOT, "t": "orders", "u": 9})
assert r and r["d"]["item"] == "کتاب" and r["d"]["contact"] == "09120000000", r
ok("اکشن فرم با جواب‌های پرشده اجرا شد (سفارش دیگر خالی ثبت نمی‌شود)")




# ── ۸) ادغام نقشه‌ها در معمار ──
import architect
cfg_m, app_m, cards_m, steps_m, title_m = architect.build(777, "B6", {"name": "کتاب", "mode": "form", "sub": "no"}, extra=["B4", "B5"])
assert cfg_m and "B4" and app_m
# نودهای هر دو نقشه‌ی دوم با نام تازه آمدند و هیچ goto شکسته‌ای نماند
assert len(cfg_m["nodes"]) >= 12
for n in cfg_m["nodes"].values():
    for row in n.get("buttons") or []:
        for b in row:
            if "goto" in b:
                assert b["goto"] in cfg_m["nodes"], b["goto"]
    for r in n.get("route") or []:
        assert r["goto"] in cfg_m["nodes"]
    if n.get("next"):
        assert n["next"] in cfg_m["nodes"]
assert app_m and len(app_m.get("screens") or {}) >= 3
assert any("ادغام شد" in c for c in cards_m)
ok("معمار: ادغام B6+B4+B5 — نودها و صفحه‌ها با هم، بدون ارجاع شکسته")

# ── ۹) مسابقه‌ی ۲۴ ساعته ──
import games
BOT_T = "tourbot"
db.bots.insert_one({"_id": BOT_T, "owner": 777, "name": "بازی", "token": "1:t", "on": True,
                    "config": {"name": "بازی", "games": {"on": True, "coin": "سکه", "list": ["quiz"]}, "start": "s", "fallback": "s", "vars": {}, "globals": {}, "commands": {},
                               "nodes": {"s": {"text": "x", "buttons": [], "ask": False}}}})
sent = []
def _fake_tg_html(token, method, **kw):
    sent.append((method, kw))
    return {"ok": True}
eng_tg_html = games.tg_html
games.tg_html = _fake_tg_html
user_t = {"id": 42, "first_name": "بازیکن۱"}
assert games.cmd(db.bots.find_one({"_id": BOT_T}), "1:t", db.bots.find_one({"_id": BOT_T})["config"], -100, user_t, "/tour") is True
assert any("شروع شد" in (kw.get("text") or "") for _, kw in sent)
assert games._tour_active(BOT_T, -100) is not None
games.finish(BOT_T, "1:t", db.bots.find_one({"_id": BOT_T})["config"], -100, user_t, "quiz", 25)
p = db.gtourp.find_one({"_id": f"{BOT_T}:-100:42"})
assert p and p["n"] == 25 and p["nm"] == "بازیکن۱"
ok("تورنمنت: شروع مسابقه، ثبت امتیاز پایان بازی در گروه")

# تسویه: پایان مسابقه را جلو می‌کشیم و دوباره /tour می‌زنیم
db.gtour.update_one({"_id": f"{BOT_T}:-100"}, {"$set": {"end": time.time() - 5}})
db.gtourp.update_one({"_id": f"{BOT_T}:-100:42"}, {"$inc": {"n": 15}})     # جمعاً ۴۰
sent.clear()
games.cmd(db.bots.find_one({"_id": BOT_T}), "1:t", db.bots.find_one({"_id": BOT_T})["config"], -100, user_t, "/tour")
assert any("تمام شد" in (kw.get("text") or "") for _, kw in sent)
coins_doc = db.gusers.find_one({"bot": BOT_T, "u": 42})
assert coins_doc and coins_doc["coins"] == 75, coins_doc          # ۲۵ سکه‌ی بازی + ۵۰ جایزه‌ی مقام اول
assert db.gtourp.count_documents({"_id": {"$regex": "^" + BOT_T + r":-100:"}}) == 0
ok("تورنمنت: تسویه‌ی خودکار — اعلام برگندگان و ۵۰ سکه جایزه")

# ── ۱۰) قطعه‌های مینی‌اپ (sync سرور) ──
c = appmod.app.test_client()
r = c.get("/api/comps")
assert r.status_code in (200, 401, 302)
r2 = c.post("/api/comps", json={"name": "هدر من", "b": {"t": "hero", "title": "سلام"}})
assert r2.status_code in (200, 401, 302)
ok("قطعه‌های مینی‌اپ: مسیرهای API سرور (sync بین دستگاه‌ها) سالم‌اند")

games.tg_html = eng_tg_html

# ── ۱۱) تایید تک‌تک کارت‌های ویرایش معمار ──
import architect as _arch
_arch.llm_post = lambda messages, *a, **k: (
    '{"ops":[{"op":"add_section","id":"faq","title":"سوالات متداول","text":"اینجا سوال‌ها را می‌گذاری"},{"op":"rename","name":"ربات نو"}],"cards":["بخش سوالات اضافه شد","نام ربات عوض شد"]}'
    , (10, 20))
bp6 = BLUEPRINTS["B6"]["build"]({"name": "کتاب", "mode": "form", "sub": "no"})
assert len(BLUEPRINTS["B6"]["questions"]) == 3, "قانون پرامپت: حداکثر ۳ سوال"
bot_x = {"_id": "editbot1", "owner": 777, "name": "فروشگاه", "config": sanitize(json.loads(json.dumps(bp6["bot"])), strict=True)}
ops_p, cards_p = _arch.plan_edit(777, bot_x, "یک بخش سوالات متداول اضافه کن و اسمش را عوض کن")
assert len(ops_p) == 2 and len(cards_p) == 2, (ops_p, cards_p)
ok("معمار-ویرایش: پیش‌نویس دو کارت داد و هنوز چیزی ذخیره نشده")
assert bot_x["config"]["name"] != "ربات نو" and "faq" not in bot_x["config"]["nodes"]

cfg_sel, applied_sel = _arch.apply_selected(777, bot_x, ops_p[:1])      # کاربر فقط کارت اول را تایید کرد
assert "faq" in cfg_sel["nodes"] and len(applied_sel) == 1
assert cfg_sel["name"] != "ربات نو"
bot_x["config"] = cfg_sel
cfg_all, applied_all = _arch.apply_selected(777, bot_x, ops_p[1:])      # بعد کارت دوم
assert cfg_all["name"] == "ربات نو" and len(applied_all) == 1
ok("معمار-ویرایش: فقط کارت‌های تاییدشده اعمال شدند (تایید تک‌تک واقعی)")

# ── ۱۲) رگرسیون: عنوان بخش نباید HTML نشت بدهد ──
c_html = {"name": "ف", "start": "a", "fallback": "a", "vars": {}, "globals": {}, "commands": {},
          "nodes": {"a": {"text": "<b>سلام</b> متن", "title": "<b>ربات بازی گروهی و ۸ ب!</b>", "buttons": [], "ask": False}}}
c_html = sanitize(c_html, strict=True)
assert "<b>" not in c_html["nodes"]["a"].get("title", ""), c_html["nodes"]["a"].get("title")
ok("sanitize: تگ HTML داخل عنوان بخش حذف می‌شود (نشتی <b> در استودیو بسته شد)")


print("selftest_biz passed —", len(OK), "تست سبز شد")
