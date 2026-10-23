# -*- coding: utf-8 -*-
"""
selftest_app.py — تست پذیرش مینی‌اپ‌ساز (بدون شبکه و بدون MONGO_URI؛ با mongomock)

اجرا:  python selftest_app.py
شامل: سازگاری کانفیگ قدیمی، sanitize_app (ورودی خراب/حجیم/اسکریپت)، امضای initData (درست و غلط)،
جریان کامل انتشار/بوت/اکشن/فرم/داده، ایزوله‌ی کاربر B، سقف اشتراک، undo و نسخه‌ها، دکمه‌ی app
در sanitize و keyboard، خاموش شدن ربات و پاک‌سازی با حذف ربات.
"""
import os, time, json, hmac, hashlib
from urllib.parse import urlencode

os.environ.setdefault("MOTHER_TOKEN", "1:SELFTEST")
os.environ.setdefault("BASE_URL", "https://selftest.example")
os.environ.setdefault("AI_BASE_URL", "https://ai.example/v1")
os.environ.setdefault("AI_API_KEY", "k")
os.environ.setdefault("AI_MODEL", "m")
os.environ.setdefault("ADMIN_IDS", "777")
os.environ.setdefault("ADMIN_WEB_KEY", "test-admin-key-123")

# تلگرام آفلاین: هر درخواست HTTP یک جواب ناموفق فوری (بدون شبکه)
import requests
class _FakeResp:
    status_code, text = 200, ""
    def json(self): return {"ok": False, "description": "offline"}
requests.post = lambda *a, **k: _FakeResp()
requests.get = lambda *a, **k: _FakeResp()

import app as appmod
from app import app
from core import db, enc, now
from ai import sanitize
import engine as eng
from engine import Env, keyboard
from webapp import sanitize_app, lint_app, APP_TEMPLATES

OK = []
def ok(name):
    OK.append(name)
    print("ok —", name)


def forge(token, uid, first="کاربر"):
    """initData واقعیِ امضاشده با توکن داده‌شده (طبق مشخصات تلگرام)"""
    user = json.dumps({"id": uid, "first_name": first, "username": f"u{uid}", "language_code": "fa"}, separators=(",", ":"))
    data = {"auth_date": str(int(time.time())), "query_id": "AAA", "user": user}
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(key, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


TOKEN = "123456:AAHkq7P_test-token-1234567890"
c = app.test_client()
AH = {"X-Admin-Key": "test-admin-key-123"}

# ── ۱) کانفیگ ربات قدیمی بدون تغییر سالم ذخیره می‌شود ──
old_cfg = {"name": "قدیمی", "start": "home", "fallback": "home", "commands": {"help": "home"},
           "vars": {"coins": "0"},
           "nodes": {"home": {"title": "خانه", "text": "سلام {name}، سکه‌هات: {coins}",
                              "buttons": [[{"text": "افزایش", "goto": "home", "do": [{"op": "add", "var": "coins", "value": "1"}]}]]}}}
clean = sanitize(old_cfg, strict=True)
assert clean["nodes"]["home"]["text"] == old_cfg["nodes"]["home"]["text"]
ok("sanitize کانفیگ قدیمی بدون تغییر")

# ── ۲) ربات صاحب + توکن ──
bid = db.bots.insert_one({"owner": 777, "name": "ربات تست", "username": "test_bot", "config": old_cfg,
                          "active": True, "token_enc": enc(TOKEN), "secret": "s", "versions": [],
                          "created": now(), "updated": now()}).inserted_id
BOT = str(bid)

# ── ۳) sanitize_app: ورودی خراب، اسکریپت، لینک javascript، حجم و سقف بلوک ──
try:
    sanitize_app({"screens": {"home": {"blocks": [{"t": "text", "text": "x"}]}}}, strict=True, node_ids=set())
    raise AssertionError("screens بدون blocks باید مشکل بدهد")  # text بدون text
except ValueError:
    ok("رد ساختار خراب")
dirty = {"screens": {"home": {"blocks": [
    {"t": "text", "text": "<script>alert(1)</script>"},
    {"t": "links", "items": [{"label": "x", "url": "javascript:alert(1)"}]},
    {"t": "image", "url": "http://insecure.example/x.jpg"},
    {"t": "pay", "stars": "5"},
    {"t": "buttons", "rows": [[{"text": "برو", "do": [{"op": "goto", "screen": "nope"}]}]]},
]}}}
warns = []
cleaned = sanitize_app(dirty, strict=False, warns=warns, node_ids=set())
blocks = cleaned["screens"]["home"]["blocks"]
assert not any("<script>" in b.get("text", "") for b in blocks if b["t"] == "text"), "اسکریپت باید رد شود"
assert not any(b["t"] == "links" for b in blocks), "لینک javascript باید حذف شود"
assert not any(b["t"] == "image" for b in blocks), "عکس http (غیر https) باید حذف شود"
assert any(b["t"] == "pay" for b in blocks), "پرداخت سالم می‌ماند"
assert not any(b["t"] == "buttons" for b in blocks), "دکمه با مقصد ناموجود حذف می‌شود"
assert warns, "هشدارها ثبت شوند"
ok(f"strict=False: اسکریپت/لینک خطرناک حذف ({len(warns)} هشدار)")
try:
    big = {"screens": {"home": {"blocks": [{"t": "text", "text": "x" * (160 * 1024)}]}}}
    sanitize_app(big, strict=True, node_ids=set())
    raise AssertionError("حجم زیاد رد نشد")
except ValueError:
    ok("رد حجم بیش از سقف (۱۵۰KB)")
many = {"screens": {"home": {"blocks": [{"t": "text", "text": "s"} for _ in range(160)]}}}
try:
    sanitize_app(many, strict=True, node_ids=set())
    raise AssertionError("سقف بلوک رد نشد")
except ValueError:
    ok("رد سقف بلوک (۱۵۰)")

# ── ۴) ذخیره‌ی پیش‌نویس قالب + انتشار ──
draft = json.loads(json.dumps(APP_TEMPLATES["shop"]["app"]))
# کاربر غیرمالک (با initData ربات مادر) نباید پیش‌نویس ربات دیگری را ببیند/ذخیره کند
from core import MOTHER_TOKEN as MT
GH = {"X-Init-Data": forge(MT, 555)}
assert c.get(f"/api/bots/{BOT}/app", headers=GH).status_code == 404
assert c.put(f"/api/bots/{BOT}/app", json={"app": draft}, headers=GH).status_code == 404
assert c.post(f"/api/bots/{BOT}/app/publish", json={}, headers=GH).status_code == 404
ok("مالکیت: کاربر غیرمالک به سازنده‌ی مینی‌اپ ربات دیگر دسترسی ندارد")
r = c.put(f"/api/bots/{BOT}/app", json={"app": draft}, headers=AH)
assert r.status_code == 200, r.get_json()
assert r.get_json()["draft"]["screens"]["form"]["blocks"][1]["t"] == "form"
ok("PUT پیش‌نویس (قالب فروشگاه) و برگشت کانفیگ تمیز")
r = c.post(f"/api/bots/{BOT}/app/publish", json={}, headers=AH)
assert r.status_code == 200 and r.get_json()["ver"] == 1, r.get_json()
ok("انتشار نسخه‌ی ۱")

# ── ۵) صفحه‌ی /a با CSP ──
r = c.get(f"/a/{BOT}")
assert r.status_code == 200 and b"mapp.js" in r.data
csp = r.headers.get("Content-Security-Policy", "")
assert "frame-ancestors" in csp and "https://localhost" in csp, csp      # هاست صریح: پیش‌نمایش سندباکس‌شده mapp.js را می‌تواند لود کند
assert "X-Frame-Options" not in r.headers
ok("صفحه‌ی رانتایم با CSP (هاست صریح برای iframe پیش‌نمایش، بدون X-Frame-Options)")
# قرارداد بوت: فقط POST (کلاینت باید با body صدا بزند)
assert c.get(f"/rt/{BOT}/boot").status_code == 405
ok("بوت فقط POST (GET → 405)")

# ── ۶) بوت با initData درست و غلط ──
r = c.post(f"/rt/{BOT}/boot", headers={"X-Init-Data": forge(TOKEN, 777)})
j = r.get_json()
assert j["status"] == "ok" and j["ver"] == 1 and j["user"]["id"] == 777 and "media" in j and "vars" in j
ok("بوت با initData امضای توکن ربات فرزند")
r = c.post(f"/rt/{BOT}/boot", headers={"X-Init-Data": forge("999:WRONG-token-wrong-token-wrong-1234", 777)})
assert r.status_code == 401 and r.get_json()["status"] == "guest"
ok("رد initData با توکن اشتباه")

# ── ۷) اکشن (hid از کانفیگ منتشرشده) + فرم + ایزوله‌ی کاربر B ──
pub = db.apps.find_one({"_id": BOT})["pub"]
cta = next(b for s in pub["screens"].values() for b in s["blocks"] if b.get("cta"))
r = c.post(f"/rt/{BOT}/act", json={"h": cta["cta"]["hid"]}, headers={"X-Init-Data": forge(TOKEN, 777)})
assert r.get_json()["ok"] and any(d["a"] == "goto" for d in r.get_json()["dirs"])
ok("اکشن goto با hid (اکشن دلخواه پذیرفته نمی‌شود)")
r = c.post(f"/rt/{BOT}/act", json={"h": "b999x", "op": "set", "var": "x", "value": "1"}, headers={"X-Init-Data": forge(TOKEN, 777)})
assert r.status_code == 400
ok("رد hid ناموجود")
form_blk = next(b for s in pub["screens"].values() for b in s["blocks"] if b["t"] == "form")
vals = {f["k"]: ("علی" if f["k"] == "name" else "09123456789" if f["k"] == "phone" else "کتاب" if f["k"] == "item" else "") for f in form_blk["fields"]}
r = c.post(f"/rt/{BOT}/form", json={"block": form_blk["id"], "values": vals, "k": "abcdef123456"},
           headers={"X-Init-Data": forge(TOKEN, 777)})
assert r.get_json()["ok"], r.get_json()
r2 = c.post(f"/rt/{BOT}/form", json={"block": form_blk["id"], "values": vals, "k": "abcdef123456"},
            headers={"X-Init-Data": forge(TOKEN, 777)})
assert r2.get_json().get("dup"), "فرم دوبار ثبت نشود"
assert db.recs.count_documents({"bot": BOT, "t": form_blk["save"]["table"], "u": 777}) == 1
assert db.submissions.count_documents({"bot_id": BOT}) == 1
ok("ثبت فرم در جدول + پاسخ فرم‌ها + idempotency")
r = c.post(f"/rt/{BOT}/act", json={"h": "bad"}, headers={"X-Init-Data": forge(TOKEN, 555)})
assert r.status_code in (400, 401)
# فرم کاربر B: رکوردش جداست
vals_b = dict(vals)
vals_b["item"] = "قلم"
c.post(f"/rt/{BOT}/form", json={"block": form_blk["id"], "values": vals_b, "k": "bbbbbb123456"},
       headers={"X-Init-Data": forge(TOKEN, 555)})
assert db.recs.count_documents({"bot": BOT, "t": form_blk["save"]["table"], "u": 555}) == 1
ls_blk = next(b for s in pub["screens"].values() for b in s["blocks"] if b["t"] == "list")
rA = c.get(f"/rt/{BOT}/data?b={ls_blk['id']}", headers={"X-Init-Data": forge(TOKEN, 777)})
rB = c.get(f"/rt/{BOT}/data?b={ls_blk['id']}", headers={"X-Init-Data": forge(TOKEN, 555)})
assert len(rA.get_json()["items"]) == 1 and len(rB.get_json()["items"]) == 1
assert "کتاب" not in rB.get_json()["items"][0], "کاربر B نباید داده‌ی کاربر A را ببیند"
assert "قلم" not in rA.get_json()["items"][0], "کاربر A نباید داده‌ی کاربر B را ببیند"
ok("ایزوله‌ی scope=my (کاربر B داده‌ی کاربر A را نمی‌بیند)")

# ── ۸) دکمه‌ی app: sanitize و keyboard ──
cfg_app = {"name": "t", "start": "home", "fallback": "home", "commands": {},
           "nodes": {"home": {"text": "سلام", "buttons": [[{"text": "اپ", "app": "shop"}, {"text": "ک", "app": "x", "kb": "reply"}]]}}}
c2 = sanitize(cfg_app, strict=True)
btns = c2["nodes"]["home"]["buttons"][0]
assert btns[0] == {"text": "اپ", "app": "shop"}
assert "kb" not in btns[1] and btns[1]["app"] == "x"
ok("sanitize دکمه‌ی app (kb=reply روی آن نادیده گرفته می‌شود)")
db.bots.update_one({"_id": bid}, {"$set": {"config": c2}})      # کانفیگ با دکمه‌ی app روی ربات
botdoc = db.bots.find_one({"_id": bid})
env = Env(botdoc, TOKEN, 777, {"id": 777, "first_name": "ع"})
eng._APP_ON.clear()
db.apps.update_one({"_id": BOT}, {"$unset": {"pub": ""}})       # حالت «قبل از انتشار»
kb = keyboard(botdoc["config"]["nodes"]["home"], "home", env)
assert not any("web_app" in b for row in kb for b in row), "قبل از انتشار دکمه‌ی web_app نباید باشد"
db.apps.update_one({"_id": BOT}, {"$set": {"pub": pub}})
eng._APP_ON.clear()
kb = keyboard(botdoc["config"]["nodes"]["home"], "home", env)
wb = [b for row in kb for b in row if "web_app" in b]
assert wb and wb[0]["web_app"]["url"] == f"https://selftest.example/a/{BOT}?s=shop"
ok("keyboard: دکمه‌ی web_app فقط بعد از انتشار، با صفحه‌ی مقصد")

# ── ۹) سقف اشتراک: مینی‌اپ دوم برای کاربر رایگان رد می‌شود ──
bid2 = db.bots.insert_one({"owner": 777, "name": "دو", "username": "t2", "config": old_cfg, "active": False,
                           "secret": "s", "versions": [], "created": now(), "updated": now()}).inserted_id
BOT2 = str(bid2)
c.put(f"/api/bots/{BOT2}/app", json={"app": draft}, headers=AH)
r = c.post(f"/api/bots/{BOT2}/app/publish", json={}, headers=AH)
assert r.status_code == 403 and r.get_json().get("need_plan")
ok("سقف اشتراک: رایگان فقط یک مینی‌اپ فعال")

# ── ۱۰) انتشار دوباره، نسخه‌ها و undo ──
r = c.post(f"/api/bots/{BOT}/app/publish", json={}, headers=AH)
assert r.get_json()["ver"] == 2
r = c.get(f"/api/bots/{BOT}/app/versions", headers=AH)
assert len(r.get_json()["items"]) == 1, r.get_json()
r = c.post(f"/api/bots/{BOT}/app/undo", json={}, headers=AH)
assert r.get_json()["ok"]
ok("انتشار دوباره + نسخه‌ی قابل بازگشت + undo")

# ── ۱۱) خاموشی ربات و حذف ──
db.bots.update_one({"_id": bid}, {"$set": {"active": False}})
r = c.post(f"/rt/{BOT}/boot", headers={"X-Init-Data": forge(TOKEN, 777)})
assert r.get_json()["status"] == "off"
ok("ربات خاموش → رانتایم پیام «خاموش» می‌دهد")
r = c.delete(f"/api/bots/{BOT}", headers=AH)
assert r.status_code == 200
assert db.apps.find_one({"_id": BOT}) is None
assert db.app_ev.count_documents({"_id": {"$regex": f"^{BOT}:"}}) == 0
ok("حذف ربات: سند مینی‌اپ و رویدادها پاک می‌شوند")

# ── ۱۲) lint_app ──
bad_app = {"home": "home", "nav": {"type": "tabs", "items": []}, "screens": {"home": {"title": "خانه", "blocks": [
    {"t": "form", "id": "f1", "fields": [{"k": "a", "label": "الف", "type": "text"}]}]}}}
issues = lint_app(bad_app, old_cfg)
assert any("فرم" in x for x in issues)
ok(f"lint_app: فرم بدون ذخیره گزارش می‌شود ({len(issues)} مورد)")

# ── ۱۳) بلوک گفتگوی هوشمند (با مدل قلابی؛ بدون شبکه) ──
import webapp as W
draft2 = {"v": 1, "theme": {"mode": "auto", "accent": "#3CCFE3", "radius": 16, "font": "vazir", "digits": "latin"},
          "nav": {"type": "none", "items": []}, "home": "home",
          "screens": {"home": {"title": "خانه", "blocks": [
              {"t": "ai", "id": "aichat", "prompt": "دستیار تست", "daily": 5, "memory": 2, "greeting": "سلام"}]}}}
assert c.put(f"/api/bots/{BOT2}/app", json={"app": draft2}, headers=AH).status_code == 200
r = c.post(f"/api/bots/{BOT2}/app/publish", json={}, headers=AH)      # سقف بعد از حذف BOT آزاد شده
assert r.status_code == 200, r.get_json()
db.bots.update_one({"_id": bid2}, {"$set": {"active": True, "token_enc": enc(TOKEN)}})
W.llm_post = lambda msgs, mt, **kw: ("پاسخ قلابی", (10, 5))
W.ai_precheck = lambda owner: True
W.ai_postcharge = lambda *a, **k: 0
r = c.post(f"/rt/{BOT2}/act", json={"h": "aichat", "text": "سلام"}, headers={"X-Init-Data": forge(TOKEN, 777)})
assert r.get_json().get("ok") and r.get_json()["reply"] == "پاسخ قلابی", r.get_json()
assert db.appai.find_one({"_id": f"{BOT2}:777"})["h"][0]["content"] == "سلام"
ok("بلوک گفتگوی هوشمند: پاسخ، حافظه و هزینه (مدل قلابی)")

print(f"\nselftest_app passed — {len(OK)} تست سبز شد")
