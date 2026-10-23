# -*- coding: utf-8 -*-
"""
crm.py — بسته‌های E و F: CRM پایه، کمپین و دنباله (وابسته به core و flowkit؛ پایین‌تر از ai و engine)

بخش‌ها:
  • پروفایل و رویدادها: timeline هر کاربر (db.tl)، تگ، امتیاز سرنخ
  • کمپین: سند کمپین (db.camps) + شمارنده‌ی روزانه (db.campday)؛ ارسالِ خودش (throttle، A/B،
    retry_after، گزارش) در هندلری که engine با دسترسی به Env/fill ثبت می‌کند — اینجا فقط داده و آمار.
  • دنباله‌ی خودکار (drip): تعریف در کانفیگ ربات، اجرا با صف دوام (هندلر در engine)؛ اینجا کمکی‌های شمارش.
  • CSV: خروجی/ورودی رکوردهای جدول (برای API استودیو در app.py)
  • پاک‌سازی سندهای شبیه‌سازی (پیشوند sim-)

قرارداد فهرست‌های کانفیگ:
  tables  = {نام: {fields: {فیلد: {type: text|number, req, default}}, scope: user|all, unique: [فیلد]}}
  drips   = {نام: {steps: [{delay, text?, goto?}], exit?: شرط}}
  segments= {نام: [شرط‌ها (clean_cond)]}   ← سگمنت پویا؛ ارزیابی با check() موتور هنگام کمپین
"""

import csv
import io
import re
import time
from datetime import timedelta

from core import db, MAX_REC_FIELDS, MAX_REC_VAL, naive, now, tehran_day, log

CAMP_BATCH = 25                 # مخاطب در هر تیک کمپین (با فاصله‌ی تیک ≈ ۱۶ پیام در ثانیه؛ زیر سقف تلگرام)
CAMP_TICK_DELAY = 2             # ثانیه بین تیک‌ها
CAMP_MAX_STATS = 0              # بدون سقف آمار
TL_MAX = 50                     # رویداد نگه‌داشته‌شده برای هر کاربر
TAGS_MAX = 20
DRIPS_PER_USER = 10             # حداکثر دنباله‌ی در انتظار هر کاربر

_indexed = [False]


def _ensure_index():
    if _indexed[0]:
        return
    from core import _index
    _index(db.tl, "t", expireAfterSeconds=180 * 86400)             # timeline شش‌ماهه
    _index(db.camps, [("bot", 1), ("t", -1)])
    _index(db.subs, [("bot", 1), ("blocked", 1)])                  # پیمایش کمپین
    _indexed[0] = True


# ───────────────────────── پروفایل، رویداد و تگ (بسته E) ─────────────────────────
def track(bot_id, uid, kind, text="", score=0):
    """ثبت رویداد در timeline کاربر + امتیاز سرنخ اختیاری"""
    _ensure_index()
    try:
        db.tl.update_one({"_id": f"{bot_id}:{uid}"},
                         {"$push": {"items": {"$each": [{"k": str(kind)[:20], "s": str(text or "")[:200], "t": now()}],
                                                 "$slice": -TL_MAX}},
                          "$setOnInsert": {"bot": bot_id, "uid": uid}},
                         upsert=True)
        score = int(score or 0)
        if score:
            db.subs.update_one({"_id": f"{bot_id}:{uid}"}, {"$inc": {"score": score}, "$setOnInsert": {"bot": bot_id, "uid": uid}}, upsert=True)
        return True
    except Exception:
        log.exception("crm.track failed")
        return False


def tag_add(bot_id, uid, tag):
    tag = str(tag or "").strip()[:30]
    if not tag:
        return False
    try:
        d = db.subs.find_one({"_id": f"{bot_id}:{uid}"}, {"tags": 1}) or {}
        if tag in (d.get("tags") or []):
            return True
        if len(d.get("tags") or []) >= TAGS_MAX:
            return False
        db.subs.update_one({"_id": f"{bot_id}:{uid}"},
                           {"$addToSet": {"tags": tag}, "$setOnInsert": {"bot": bot_id, "uid": uid, "t": now()}}, upsert=True)
        return True
    except Exception:
        log.exception("crm.tag_add failed")
        return False


def tag_del(bot_id, uid, tag):
    try:
        db.subs.update_one({"_id": f"{bot_id}:{uid}"}, {"$pull": {"tags": str(tag or "").strip()[:30]}})
        return True
    except Exception:
        return False


def user_card(bot_id, uid):
    """کارت کاربر برای پنل CRM (مرحله ۷): پروفایل، تگ‌ها و آخرین رویدادها"""
    s = db.subs.find_one({"_id": f"{bot_id}:{uid}"}) or {}
    tl = (db.tl.find_one({"_id": f"{bot_id}:{uid}"}) or {}).get("items") or []
    return {"uid": uid, "name": s.get("nm", ""), "un": s.get("un", ""), "tags": s.get("tags") or [],
            "score": int(s.get("score", 0)), "blocked": bool(s.get("blocked")), "last": s.get("last"),
            "timeline": tl[-20:]}


# ───────────────────────── کمپین (بسته F) ─────────────────────────
def camp_create(bot_id, text, media="", fmt="", seg="", ab_b="", split=50):
    """ساخت سند کمپین؛ خروجی شناسه‌ی کوتاه"""
    _ensure_index()
    cid = f"{int(time.time() * 10) % 10 ** 9:x}{abs(hash(f'{bot_id}{text}{time.time()}')) % 4096:03x}"
    db.camps.insert_one({"_id": cid[:24], "bot": bot_id, "text": str(text or "")[:3500],
                         "media": str(media or "")[:80], "fmt": "html" if fmt == "html" else "",
                         "seg": str(seg or "")[:30], "ab_b": str(ab_b or "")[:3500],
                         "split": max(5, min(95, int(split or 50))), "status": "run",
                         "stats": {"sent": 0, "fail": 0, "skip": 0, "a": 0, "b": 0},
                         "cursor": "", "t": now()})
    return cid[:24]


def camp_get(bot_id, cid):
    try:
        return db.camps.find_one({"_id": str(cid)[:24], "bot": bot_id})
    except Exception:
        return None


def camp_status(bot_id, cid, st):
    db.camps.update_one({"_id": str(cid)[:24], "bot": bot_id}, {"$set": {"status": st}})


def camp_stat(bot_id, cid, key):
    try:
        db.camps.update_one({"_id": str(cid)[:24], "bot": bot_id}, {"$inc": {f"stats.{key}": 1}})
    except Exception:
        pass


def camp_cursor(bot_id, cid, cur):
    db.camps.update_one({"_id": str(cid)[:24], "bot": bot_id}, {"$set": {"cursor": str(cur)[:80]}})


def camp_finish(bot_id, cid):
    db.camps.update_one({"_id": str(cid)[:24], "bot": bot_id}, {"$set": {"status": "done", "done_at": now()}})
    db.bots.update_one({"_id": _oid(bot_id)}, {"$unset": {"bc_at": ""}})


def bc_day_add(bot_id, n, cap):
    """شمارنده‌ی ارسال همگانی روز؛ False یعنی سقف روزانه‌ی پلن پر شده"""
    key = f"{bot_id}:{tehran_day()}"
    try:
        d = db.campday.find_one_and_update({"_id": key}, {"$inc": {"n": int(n)}}, upsert=True, return_document=True)
        if int(d.get("n", 0)) > int(cap):
            db.campday.update_one({"_id": key}, {"$inc": {"n": -int(n)}})      # برگرداندن شمارش ناموفق
            return False
        return True
    except Exception:
        log.exception("bc_day_add failed")
        return True                       # خطای شمارش نباید ارسال را ببندد


def _oid(bot_id):
    from bson import ObjectId
    try:
        return ObjectId(str(bot_id))
    except Exception:
        return None


# ───────────────────────── CSV (بسته E) ─────────────────────────
def table_csv(bot_id, table):
    """رکوردهای جدول به CSV (UTF-8 با BOM برای اکسل فارسی)"""
    recs = list(db.recs.find({"bot": bot_id, "t": table}).sort("n", 1).limit(20000))
    fields = []
    for r in recs:
        for k in (r.get("d") or {}):
            if k not in fields:
                fields.append(k)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["n", "u", *fields])
    for r in recs:
        d = r.get("d") or {}
        w.writerow([r.get("n", ""), r.get("u", ""), *[d.get(f, "") for f in fields]])
    return "\ufeff" + buf.getvalue()


def csv_import(bot_id, table, text, uid=0, schema=None, cap_user=100, cap_shared=500):
    """ورودی CSV رکوردها؛ خروجی (اضافه‌شده، رد‌شده). فیلدها با اسکیمای جدول (اگر باشد) هماهنگ می‌شوند"""
    try:
        rows = list(csv.reader(io.StringIO(str(text or "").lstrip("\ufeff"))))
    except Exception:
        return 0, 0
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if len(rows) < 2:
        return 0, 0
    head = [str(c).strip().lower() for c in rows[0]]
    fields = [h for h in head if h not in ("n", "u")][:MAX_REC_FIELDS]
    if not fields:
        return 0, 0
    shared = bool((schema or {}).get("scope") == "all")
    cap = cap_shared if shared else cap_user
    q = {"bot": bot_id, "t": table}
    if not shared:
        q["u"] = uid
    try:
        base = int((db.recs.find_one(q, sort=[("n", -1)], projection={"n": 1}) or {}).get("n", 0))
    except Exception:
        base = 0
    added = skipped = 0
    for row in rows[1:]:
        if base + added >= cap:
            break
        vals = dict(zip(head, row))
        d = {}
        okrow = True
        for f in fields:
            v = str(vals.get(f, "")).strip()[:MAX_REC_VAL]
            spec = ((schema or {}).get("fields") or {}).get(f) or {}
            if spec.get("type") == "number":
                from core import to_num
                n = to_num(v)
                if n is None:
                    n = to_num(spec.get("default") or 0) or 0
                d[f] = int(n) if n == int(n) else n          # عددی ذخیره می‌شود (سازگار با $inc)
            else:
                if spec.get("req") and not v:
                    okrow = False
                    break
                d[f] = v
        if not okrow or not d:
            skipped += 1
            continue
        try:
            db.recs.insert_one({"bot": bot_id, "t": table, "u": uid, "n": base + added + 1, "d": d, "ct": now()})
            added += 1
        except Exception:
            skipped += 1
    return added, skipped


# ───────────────────────── پاک‌سازی شبیه‌سازی ─────────────────────────
_SIM_COLLS = ("uvars", "gvars", "cvars", "states", "rk", "nvis", "abstats", "subs", "tl", "relay", "mfid")


def purge_sim(hours=6):
    """حذف سندهای ساختگی شبیه‌سازی‌های قدیمی (bot_id با پیشوند sim-)؛ بهترین‌تلاش"""
    n = 0
    edge = naive(now() - timedelta(hours=max(1, int(hours))))
    for c in _SIM_COLLS:
        try:
            try:
                r = getattr(db, c).delete_many(
                    {"_id": {"$regex": r"^sim-"}, "$or": [{"t": {"$lt": edge}}, {"t": {"$exists": False}}]})
                n += r.deleted_count
            except Exception:      # mongomock قدیمی $or روی _id regex را نمی‌فهمد: بدون شرط زمان
                r = getattr(db, c).delete_many({"_id": {"$regex": r"^sim-"}})
                n += r.deleted_count
        except Exception:
            pass
    for c, f in (("recs", "bot"), ("submissions", "bot_id"), ("camps", "bot"), ("campday", "_id")):
        try:
            r = getattr(db, c).delete_many({f: {"$regex": r"^sim-"}, "t": {"$lt": edge}} if f != "campday" else {"_id": {"$regex": r"^sim-"}})
            n += r.deleted_count
        except Exception:
            pass
    try:
        db.queue.delete_many({"payload.bid": {"$regex": r"^sim-"}})
    except Exception:
        pass
    return n


def selftest():
    """تست CRM/کمپین/CSV با mongomock (بدون شبکه)"""
    ok = lambda name: print("ok —", name)
    _ensure_index()
    bid, uid = "testbot", 111
    # track/tag/امتیاز سرنخ
    assert track(bid, uid, "buy", "خرید بسته", score=10)
    assert track(bid, uid, "form", "فرم تماس")
    tag_add(bid, uid, "vip")
    tag_add(bid, uid, "vip")
    card = user_card(bid, uid)
    assert card["tags"] == ["vip"] and card["score"] == 10 and len(card["timeline"]) == 2
    tag_del(bid, uid, "vip")
    assert user_card(bid, uid)["tags"] == []
    ok("track/timeline + tag + امتیاز سرنخ")
    # کمپین: ساخت/آمار/پایان
    cid = camp_create(bid, "سلام {name}", seg="", ab_b="", split=50)
    assert camp_get(bid, cid) and camp_get(bid, cid)["status"] == "run"
    camp_stat(bid, cid, "sent")
    camp_stat(bid, cid, "a")
    camp_cursor(bid, cid, f"{bid}:999")
    camp_finish(bid, cid)
    d = camp_get(bid, cid)
    assert d["status"] == "done" and d["stats"]["sent"] == 1 and d["cursor"] == f"{bid}:999"
    ok("کمپین: سند، آمار، نشانگر پیمایش و پایان")
    # شمارنده‌ی روزانه
    assert bc_day_add(bid, 10, 100)
    assert not bc_day_add(bid, 200, 100)          # سقف پر شد
    ok("سقف روزانه‌ی ارسال همگانی")
    # CSV رفت و برگشت
    from core import to_num
    db.recs.insert_one({"bot": bid, "t": "orders", "u": uid, "n": 1, "d": {"item": "کتاب", "price": "120"}, "ct": now()})
    db.recs.insert_one({"bot": bid, "t": "orders", "u": uid, "n": 2, "d": {"item": "قلم", "price": "35"}, "ct": now()})
    csv_text = table_csv(bid, "orders")
    assert "کتاب" in csv_text and "price" in csv_text
    db.recs.delete_many({"bot": bid, "t": "orders"})
    added, skipped = csv_import(bid, "orders", csv_text, uid=uid,
                                schema={"fields": {"item": {"type": "text", "req": True}, "price": {"type": "number"}}})
    assert added == 2 and skipped == 0, (added, skipped)
    r = db.recs.find_one({"bot": bid, "t": "orders", "n": 2})
    assert r["d"]["price"] == 35
    added2, skipped2 = csv_import(bid, "orders", "item,price\n,50\n", uid=uid,
                                  schema={"fields": {"item": {"type": "text", "req": True}}})
    assert added2 == 0 and skipped2 == 1          # فیلد اجباری خالی رد می‌شود
    ok("CSV: خروجی/ورودی با اسکیما و رد ردیف ناقص")
    # purge_sim بدون خطا
    purge_sim(1)
    ok("purge_sim (پاک‌سازی سندهای شبیه‌سازی)")
    print("crm selftest passed")


if __name__ == "__main__":
    selftest()
