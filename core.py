# -*- coding: utf-8 -*-
"""
core.py — هسته‌ی مشترک (پایین‌ترین لایه)

این فایل به هیچ ماژول دیگری از پروژه وابسته نیست؛ همه‌ی فایل‌های دیگر از اینجا import می‌کنند.
بخش‌ها:
  • تنظیمات (Environment) و پایگاه داده
  • ابزارهای پایه
  • احراز هویت مینی‌اپ
  • کیف توکن
  • سطح، ماموریت‌ها و دعوت
  • کتابخونه‌ی رسانه
  • عضویت اجباری ربات‌ساز: خواندن تنظیمات و بررسی عضویت

قرارداد: هر چیزی که چند بخش مختلف لازم دارند (تنظیمات، دیتابیس، توکن/کیف پول، رسانه، احراز هویت) همین‌جاست.
نمونه: ثابت تازه‌ی Environment ← بخش «تنظیمات»؛ تابع تازه‌ی کیف توکن ← بخش «کیف توکن».
نکته: مقدار MOTHER_USERNAME بعد از راه‌اندازی عوض می‌شه؛ بیرون از core با core.MOTHER_USERNAME بخونش.

نام‌های پایدار — فایل‌های دیگه این‌ها رو از همین فایل import می‌کنن (حذف یا تغییر نام، بقیه رو می‌شکنه).
اگه چیزی تازه برای بقیه لازمه، همین‌جا اضافه کن و در فایلِ مصرف‌کننده import کن:
  add_xp, ADMIN_IDS, admin_only, age_sec, AI_API_KEY, AI_BASE_URL, AI_CHAT_MODEL, AI_MAX_TOKENS,
  AI_MODEL, AI_MSG_COST, AI_MSGS_PER_TOKEN, AI_NODE_MAX_TOKENS, ai_per, ai_tick, app, authed, aware,
  balance, BASE_URL, BILLING, BOARD_SCAN, BROADCAST_MAX, BROADCAST_PER_TOKEN, calc_cost, charge_up_to,
  CHUNK, claim_daily, credit, cut, DAILY_BONUS, DAILY_XP, db, DEBUG, dec, _DIG, EDIT_COST, enc,
  ENHANCE_COST, ensure_user, est_tokens, FJ_CACHE, fj_chat, FJ_CONF, fj_conf, FJ_DEFAULT_TEXT,
  fj_missing, fj_public, GEN_COST, get_bot, get_media, hold, _int, is_block_err, JOB_TIMEOUT,
  levels_public, link_referral, log, low_balance_notice, lv_info, MAX_BOTS, max_bots, MAX_GLOBALS,
  MAX_MEDIA, MAX_NODES, MAX_PENDING_REMIND, MAX_PROMPT, MAX_STAFF, MAX_STARS, MAX_VERSIONS, media_bytes,
  media_delete, MEDIA_KEYS, media_kind, media_list, MEDIA_MAX_MB, MEDIA_QUOTA_MB, media_sig, MONGO_URI,
  mother_link, MOTHER_SECRET, MOTHER_TOKEN, naive, now, ONLINE_SECS, PACKS, parse_err, PAYMENTS,
  perks_of, plain_html, public, public_media, rate_ok, redeem, REF_INVITEE, REF_INVITER,
  REF_MAX_PER_USER, REF_MILESTONES, REF_ON, refund, request_user, SAFE_INLINE, SCHED_ON, send_rich,
  settle_referral, setup_mother, spend, task_metrics, task_steps, TASKS, tasks_state, tehran_day,
  TEMPLATE_FACTOR, TEMPLATE_MAX_COST, TEMPLATE_MIN_COST, TEMPLATE_UNIT_COST, tg, tg_html, tg_media,
  thash, TOKEN_MIN_COST, TOKEN_OUT_RATE, TOKEN_SCALE, touch_user, up_dict, wallet_info
"""

import html as _html
import os, re, json, time, hmac, hashlib, base64, logging, math, threading, functools
from urllib.parse import parse_qsl
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, g, jsonify, request
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from bson.errors import InvalidId
from cryptography.fernet import Fernet



# ───────────────────────── تنظیمات (Environment) و پایگاه داده ─────────────────────────
MOTHER_TOKEN = os.environ["MOTHER_TOKEN"]            # توکن ربات مادر
MONGO_URI    = os.environ.get("MONGO_URI", "").strip()  # خالی = حافظه‌ی موقت (ذخیره نمی‌شه)
BASE_URL     = os.environ["BASE_URL"].rstrip("/")    # مثلا https://yourapp.onrender.com
AI_BASE_URL  = re.sub(r"/chat/completions/?$", "", os.environ["AI_BASE_URL"].strip().rstrip("/"))
AI_API_KEY   = os.environ["AI_API_KEY"]
AI_MODEL     = os.environ["AI_MODEL"]
AI_CHAT_MODEL = os.environ.get("AI_CHAT_MODEL", "").strip() or AI_MODEL   # مدل گفتگوی داخل رباتا (می‌تونه سبک‌تر باشه)
SECRET_KEY   = os.environ.get("SECRET_KEY", MOTHER_TOKEN)
ADMIN_IDS    = {int(x) for x in re.findall(r"\d+", os.environ.get("ADMIN_IDS", ""))}
ADMIN_WEB_KEY = os.environ.get("ADMIN_WEB_KEY", "123456").strip()   # کلید ورود ادمین از مرورگر برای تست (خالی = خاموش)
MOTHER_USERNAME = os.environ.get("MOTHER_USERNAME", "").strip().lstrip("@")   # اگه خالی باشه از getMe گرفته می‌شه


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _float(name, default):
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


# ضریب اقتصاد: همه‌ی توکن‌ها (هدیه‌ها، پاداش‌ها، هزینه‌ها، بسته‌ها) و XP با این ضریب بالا می‌رن.
# هدیه‌ی ثبت‌نام = ۱۰۰ × TOKEN_SCALE = ۱۰۰۰ توکن؛ بقیه دقیقاً با همین نسبت.
TOKEN_SCALE = max(1, _int("TOKEN_SCALE", 10))
XP_SCALE    = max(1, _int("XP_SCALE", 13))

MAX_BOTS      = _int("MAX_BOTS", 1)            # سقف ربات هر کاربر
AI_MAX_TOKENS = _int("AI_MAX_TOKENS", 9000)     # سقف طول خروجی هوش مصنوعی ساخت ربات
AI_NODE_MAX_TOKENS = _int("AI_NODE_MAX_TOKENS", 600)   # سقف طول جواب هوش مصنوعیِ داخل رباتا
DEBUG         = os.environ.get("DEBUG", "") == "1"

# اقتصاد توکن
#  BILLING=usage → هزینه‌ی ساخت/ارتقا و پیام‌های هوشمند از روی مصرف واقعیِ مدل حساب می‌شه (پیش‌فرض)
#  BILLING=fixed → هزینه‌ی ثابت: GEN_COST / EDIT_COST و هر AI_MSGS_PER_TOKEN پیام = ۱ توکن
BILLING           = "fixed" if os.environ.get("BILLING", "usage").strip().lower() == "fixed" else "usage"
TOKEN_IN_RATE     = _float("TOKEN_IN_RATE", 0.7 * TOKEN_SCALE)      # توکن به‌ازای هر ۱۰۰۰ توکن ورودی مدل
TOKEN_OUT_RATE    = _float("TOKEN_OUT_RATE", 1.9 * TOKEN_SCALE)     # توکن به‌ازای هر ۱۰۰۰ توکن خروجی مدل
TOKEN_MIN_COST    = _int("TOKEN_MIN_COST", 5 * TOKEN_SCALE)       # حداقل هزینه‌ی هر ساخت/ارتقا (حالت usage)
GEN_COST          = _int("GEN_COST", 5 * TOKEN_SCALE)            # ساخت ربات جدید (حالت fixed)
EDIT_COST         = _int("EDIT_COST", 2 * TOKEN_SCALE)            # ارتقای ربات (حالت fixed)
AI_MSGS_PER_TOKEN = max(1, _int("AI_MSGS_PER_TOKEN", 3))        # حالت fixed: هر چند پیام هوشمند = ۱ توکن
ENHANCE_COST      = _int("ENHANCE_COST", 1 * TOKEN_SCALE)         # بهینه‌سازی توضیحِ ربات با هوش مصنوعی
TEMPLATE_UNIT_COST = _float("TEMPLATE_UNIT_COST", 0.8 * TOKEN_SCALE)   # قالب آماده: هزینه به‌ازای هر «واحد کار» (هر بخش = ۱، فرم/منطق/تیکت = ۱، گفتگوی هوشمند = ۲)
TEMPLATE_FACTOR   = _float("TEMPLATE_FACTOR", 1.1)       # ضریب کلی قیمت قالب‌ها (۱ = پیش‌فرض؛ ۱.۵ = ۵۰٪ گرون‌تر)
TEMPLATE_MIN_COST = _int("TEMPLATE_MIN_COST", 3 * TOKEN_SCALE)         # حداقل هزینه‌ی قالب آماده (۰ = رایگان)
TEMPLATE_MAX_COST = _int("TEMPLATE_MAX_COST", 0)         # سقف هزینه‌ی قالب (۰ = خودکار: کمی کمتر از ساخت با هوش مصنوعی)
BROADCAST_PER_TOKEN = max(1, _int("BROADCAST_PER_TOKEN", max(1, 50 // TOKEN_SCALE)))   # پخش همگانی: هر چند گیرنده = ۱ توکن
BROADCAST_MAX     = _int("BROADCAST_MAX", 5000)
START_TOKENS      = _int("START_TOKENS", _int("WELCOME_TOKENS", 100 * TOKEN_SCALE))   # هدیه‌ی ثبت‌نام
DAILY_BONUS       = _int("DAILY_BONUS", 5 * TOKEN_SCALE)          # جایزه‌ی روزانه (با استریک تا +۴ بیشتر)
REF_INVITER       = _int("REF_INVITER", _int("REF_BONUS_INVITER", 60 * TOKEN_SCALE))   # پاداش دعوت‌کننده
REF_INVITEE       = _int("REF_INVITEE", _int("REF_BONUS_NEW", 40 * TOKEN_SCALE))       # هدیه‌ی دعوت‌شده
REF_MAX_PER_USER  = _int("REF_MAX_PER_USER", 100)   # سقف دعوت پاداش‌دار هر نفر
REF_ON            = "create" if os.environ.get("REF_ON", "activate").strip().lower() == "create" else "activate"
REF_MILESTONES    = [(5, 50 * TOKEN_SCALE), (15, 150 * TOKEN_SCALE), (50, 500 * TOKEN_SCALE)]   # (تعداد دعوت موفق، پاداش اضافه)
LOW_TOKENS        = _int("LOW_TOKENS", 10 * TOKEN_SCALE)          # زیر این مقدار به صاحب ربات هشدار می‌دیم
try:
    PACKS = json.loads(os.environ.get("PACKS", "")) or []
except ValueError:
    PACKS = []
if not PACKS:   # بسته‌های خرید با Telegram Stars
    PACKS = [{"id": "p1", "tokens": 200 * TOKEN_SCALE, "stars": 50},
             {"id": "p2", "tokens": 700 * TOKEN_SCALE, "stars": 150},
             {"id": "p3", "tokens": 2000 * TOKEN_SCALE, "stars": 380}]

# رسانه
MEDIA_MAX_MB   = _int("MEDIA_MAX_MB", 15)       # سقف حجم هر فایل
MEDIA_QUOTA_MB = _int("MEDIA_QUOTA_MB", 60)     # سقف کل فایل‌های هر کاربر
MAX_MEDIA      = _int("MAX_MEDIA", 60)          # سقف تعداد فایل هر کاربر

# سطح و ماموریت‌ها (جدول سطح‌ها و ماموریت‌ها پایین‌تر، بخش «سطح و ماموریت‌ها»)
DAILY_XP     = 2 * XP_SCALE   # XP هر بار دریافت جایزه‌ی روزانه
MAX_DISCOUNT = 20          # سقف کاهش نرخ مصرف توکن از راه سطح (درصد)

MAX_PROMPT   = 4000
MAX_VERSIONS = 6
MAX_NODES    = 60
JOB_TIMEOUT  = 240
PAYMENTS     = os.environ.get("PAYMENTS", "1").strip() != "0"       # دکمه‌ی پرداخت با ستاره‌ی تلگرام داخل رباتا (۰ = خاموش)
SCHED_ON     = os.environ.get("SCHED", "1").strip() != "0"          # پیام‌های زمان‌بندی‌شده (یادآور)
MAX_STAFF    = 5            # حداکثر پشتیبان علاوه بر صاحب ربات
MAX_GLOBALS  = 20           # حداکثر متغیر مشترک بین همه‌ی کاربرها
MAX_PENDING_REMIND = 5      # حداکثر یادآورِ منتظرِ هر کاربر در هر ربات
MAX_STARS    = 10000        # سقف قیمت هر دکمه‌ی پرداخت (ستاره)
BOARD_SCAN   = 3000         # حداکثر کاربری که برای جدول برترین‌ها بررسی می‌شه
ONLINE_SECS  = 70           # کاربری که توی این بازه پینگ داده باشه «آنلاین» حساب می‌شه

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aibot")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = (MEDIA_MAX_MB + 1) * 1024 * 1024
if MONGO_URI:
    db = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000).get_database("aibot")
else:
    import mongomock
    db = mongomock.MongoClient().get_database("aibot")
    log.warning("MONGO_URI تنظیم نشده؛ از حافظه‌ی موقت استفاده می‌شه و با هر ری‌استارت همه‌چی پاک می‌شه")


def _index(col, key, **kw):
    try:
        col.create_index(key, **kw)
    except Exception as e:
        log.warning("index %s failed: %s", key, str(e)[:300])


_index(db.bots, "owner")
_index(db.userbots, "owner")
_index(db.ubaway, "t", expireAfterSeconds=73 * 3600)
_index(db.bots, "token_hash", unique=True, sparse=True)
_index(db.subs, "bot")
_index(db.submissions, "bot_id")
_index(db.media, "owner")
_index(db.mchunks, "m")
_index(db.ledger, "key", unique=True, sparse=True)
_index(db.ledger, "uid")
_index(db.jobs, "uid")
_index(db.jobs, "t", expireAfterSeconds=86400)
_index(db.mstate, "t", expireAfterSeconds=7200)
_index(db.relay, "t", expireAfterSeconds=30 * 86400)
_index(db.nvis, "bot")
_index(db.tickets, "bot")
_index(db.tickets, [("bot", 1), ("uid", 1)])
_index(db.sched, "due")
_index(db.uvars, "bot")
_index(db.payments, "charge", unique=True, sparse=True)
_index(db.payments, "bot")
_index(db.blocked, "bot")
_index(db.groups, "bot")
_index(db.modp, "t", expireAfterSeconds=3600)
_index(db.recs, [("bot", 1), ("t", 1), ("u", 1), ("n", -1)])
_index(db.recs, [("bot", 1), ("t", 1), ("n", -1)])
try:
    db.bots.update_many({"xp_on": {"$exists": True}}, {"$unset": {k: "" for k in (
        "xp_on", "xp_desc", "xp_v", "xp_l", "xp_s", "xp_since", "xp_hasav", "xp_avts", "xp_av", "xp_avct", "xp_hidden", "xp_rep")}})
    for _old in ("xp_ev", "xp_views"):
        db.drop_collection(_old)
except Exception:
    log.warning("legacy cleanup skipped")

fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest()))
MOTHER_SECRET = hashlib.sha256(("mother" + SECRET_KEY).encode()).hexdigest()[:32]


# ───────────────────────── ابزارهای پایه ─────────────────────────
def tg(token, method, **data):
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=data, timeout=15)
        return r.json()
    except Exception as e:
        log.warning("tg %s failed: %s", method, e)
        return {"ok": False, "description": str(e)}


def now():
    return datetime.now(timezone.utc)


def naive(dt=None):
    """UTC بدون tzinfo؛ برای کوئری‌های مونگو"""
    return (dt or now()).replace(tzinfo=None)


def aware(d):
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


def age_sec(dt):
    return (naive() - naive(dt)).total_seconds()


def tehran_day(back=0):
    return (now() + timedelta(hours=3, minutes=30) - timedelta(days=back)).strftime("%Y-%m-%d")


def enc(s):  return fernet.encrypt(s.encode()).decode()


def dec(s):  return fernet.decrypt(s.encode()).decode()


def thash(t): return hashlib.sha256(t.encode()).hexdigest()


_rl, _rl_lock = {}, threading.Lock()


def rate_ok(key, n, window):
    """محدودیت ساده‌ی تعداد درخواست در بازه‌ی زمانی (در حافظه)"""
    t = time.time()
    with _rl_lock:
        q = [x for x in _rl.get(key, []) if t - x < window]
        if len(q) >= n:
            _rl[key] = q
            return False
        q.append(t)
        _rl[key] = q
        if len(_rl) > 5000:
            for k in [k for k, v in _rl.items() if not v or t - v[-1] > 3600]:
                _rl.pop(k, None)
    return True


_DIG = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


# ───────────────────────── احراز هویت مینی‌اپ ─────────────────────────
def verify_init_data(init_data):
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        got = pairs.pop("hash", None)
        if not got:
            return None
        check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        key = hmac.new(b"WebAppData", MOTHER_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(key, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, got):
            return None
        if time.time() - int(pairs.get("auth_date", 0)) > 86400:
            return None
        u = json.loads(pairs["user"])
        u["_sp"] = str(pairs.get("start_param", ""))[:64]      # لینک دعوتِ مستقیمِ مینی‌اپ (startapp=ref_123)
        return u
    except Exception:
        return None


def request_user():
    """کاربر درخواست: initData تلگرام؛ یا (فقط برای ادمین) کلید ADMIN_WEB_KEY از مرورگر"""
    u = verify_init_data(request.headers.get("X-Init-Data", ""))
    if u:
        return u
    k = request.headers.get("X-Admin-Key", "")
    if ADMIN_WEB_KEY and ADMIN_IDS and k and hmac.compare_digest(k.encode(), ADMIN_WEB_KEY.encode()):
        return {"id": min(ADMIN_IDS), "first_name": "Admin", "username": "admin", "_sp": "", "_web": True}
    return None


def authed(fn):
    @functools.wraps(fn)
    def wrapper(*a, **k):
        u = request_user()
        if not u:
            return jsonify(error="unauthorized"), 401
        g.user = u
        if not u.get("_web") and u["id"] not in ADMIN_IDS:
            conf = fj_conf()
            miss = fj_missing(u["id"], conf) if conf else []
            if miss:
                return jsonify(error="برای ادامه باید عضو کانال بشی.", fj=fj_public(conf, miss)), 403
        return fn(u["id"], *a, **k)
    return wrapper


def admin_only(fn):
    @functools.wraps(fn)
    def wrapper(*a, **k):
        u = request_user()
        if not u:
            return jsonify(error="unauthorized"), 401
        if u["id"] not in ADMIN_IDS:
            return jsonify(error="forbidden"), 403
        g.user = u
        return fn(u["id"], *a, **k)
    return wrapper


def get_bot(bot_id, owner):
    try:
        return db.bots.find_one({"_id": ObjectId(bot_id), "owner": owner})
    except (InvalidId, TypeError):
        return None


def public(b):
    return {
        "id": str(b["_id"]), "name": b.get("name", ""), "active": b.get("active", False),
        "username": b.get("username"), "config": b.get("config"),
        "versions": len(b.get("versions", [])), "updated": aware(b["updated"]).isoformat(),
        "thinking": b.get("thinking", ""),
    }


def touch_user(u):
    """آخرین حضور و مشخصات تلگرامی کاربر (برای وضعیت آنلاین و فهرست ادمین)"""
    if u.get("_web"):      # ورود ادمین از مرورگر: اطلاعات واقعی تلگرام ادمین رو بازنویسی نکن
        return
    try:
        name = " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x)[:80]
        db.users.update_one({"_id": u["id"]}, {"$set": {"seen": naive(), "tg_user": (u.get("username") or "")[:40], "tg_name": name}})
    except Exception:
        log.exception("touch_user failed")


# ───────────────────────── کیف توکن ─────────────────────────
def log_ledger(uid, n, why, key=None):
    doc = {"uid": uid, "n": n, "why": why, "t": now()}
    if key:
        doc["key"] = key
    db.ledger.insert_one(doc)


def ensure_user(uid, name="", ref=None):
    """(سند کاربر، تازه ساخته شد؟) — کاربرهای نسخه‌های قبلی (فیلد bal) خودکار مهاجرت می‌کنن"""
    defaults = {"tokens": START_TOKENS, "spent": 0, "streak": 0, "refs": 0, "ai_n": 0}
    prev = db.users.find_one_and_update(
        {"_id": uid}, {"$setOnInsert": {"created": now(), "name": str(name or "")[:60], **defaults}},
        upsert=True, return_document=ReturnDocument.BEFORE)
    created = prev is None
    if created:
        log_ledger(uid, START_TOKENS, "signup")
    elif "tokens" not in prev:
        fix = {k: v for k, v in defaults.items() if k != "tokens" and k not in prev}
        if prev.get("bal") is not None:                      # مهاجرت از نسخه‌ی قدیمی
            fix["tokens"] = int(prev["bal"])
            if "refs" not in prev and prev.get("ref_count") is not None:
                fix["refs"] = int(prev["ref_count"])
        else:
            fix["tokens"] = START_TOKENS
            log_ledger(uid, START_TOKENS, "signup")
        db.users.update_one({"_id": uid, "tokens": {"$exists": False}}, {"$set": fix})
    if created and ref:
        link_referral(uid, ref)
    return db.users.find_one({"_id": uid}), created


def balance(uid):
    return int((db.users.find_one({"_id": uid}) or {}).get("tokens", 0))


def spend(uid, n, why):
    """کم کردنِ اتمیک و ثبت؛ اگه موجودی کافی نباشه False"""
    d = db.users.find_one_and_update(
        {"_id": uid, "tokens": {"$gte": n}}, {"$inc": {"tokens": -n, "spent": n}},
        return_document=ReturnDocument.AFTER)
    if d:
        log_ledger(uid, -n, why)
    return d is not None


def credit(uid, n, why, key=None):
    """اضافه کردن توکن؛ با key تکراری نمی‌شه (برای پرداخت، دعوت و کوپن)"""
    n = int(n)
    if n <= 0:
        return False
    try:
        log_ledger(uid, n, why, key)
    except DuplicateKeyError:
        return False
    db.users.update_one({"_id": uid}, {"$inc": {"tokens": n}})
    return True


def refund(uid, n, why="refund"):
    db.users.update_one({"_id": uid}, {"$inc": {"tokens": n, "spent": -n}})
    log_ledger(uid, n, why)


def hold(uid, n):
    """فقط بررسی می‌کنه موجودی برای سقف هزینه کافیه؛ چیزی از موجودی کم نمی‌شه (هزینه‌ی واقعی آخر کار کسر می‌شه)"""
    return balance(uid) >= int(n)


def release(uid, n):
    """سازگاری با کد قبلی: دیگه چیزی رزرو نمی‌شه که برگرده"""
    return None


def settle(uid, n, why):
    """هزینه‌ی نهایی‌ی یک کار رزروشده رو توی تاریخچه ثبت می‌کنه"""
    if n > 0:
        db.users.update_one({"_id": uid}, {"$inc": {"spent": int(n)}})
        log_ledger(uid, -int(n), why)


def charge_up_to(uid, n, why, daily_key=False):
    """تا سقف موجودی کسر می‌کنه (هیچ‌وقت منفی نمی‌شه). daily_key=True: همه‌ی کسرهای یک روز یک ردیف تاریخچه می‌شن"""
    take = min(int(n), max(0, balance(uid)))
    if take <= 0:
        return 0
    ok = db.users.update_one({"_id": uid, "tokens": {"$gte": take}}, {"$inc": {"tokens": -take, "spent": take}}).modified_count == 1
    if not ok:
        return 0
    if daily_key:
        k = f"{why}:{uid}:{tehran_day()}"
        try:
            if db.ledger.update_one({"uid": uid, "key": k}, {"$inc": {"n": -take}}, upsert=False).matched_count == 0:
                log_ledger(uid, -take, why, key=k)
        except DuplicateKeyError:
            db.ledger.update_one({"uid": uid, "key": k}, {"$inc": {"n": -take}})
    else:
        log_ledger(uid, -take, why)
    return take


def est_tokens(s):
    return max(1, len(str(s)) // 3)


def calc_cost(p, c, minimum=None, uid=None):
    m = TOKEN_MIN_COST if minimum is None else minimum
    return cut(uid, max(m, math.ceil((p * TOKEN_IN_RATE + c * TOKEN_OUT_RATE) / 1000)))


def claim_daily(uid):
    d, _ = ensure_user(uid)
    today, yest = tehran_day(), tehran_day(1)
    streak = d.get("streak", 0) + 1 if d.get("last_claim") == yest else 1
    reward = DAILY_BONUS + min(streak - 1, 4) * TOKEN_SCALE + perks_at(lvl_of(int(d.get("xp", 0))))["daily"]
    r = db.users.find_one_and_update(
        {"_id": uid, "last_claim": {"$ne": today}},
        {"$set": {"last_claim": today, "streak": streak}, "$inc": {"tokens": reward}, "$max": {"best_streak": streak}},
        return_document=ReturnDocument.AFTER)
    if not r:
        return None
    log_ledger(uid, reward, "daily")
    return reward, streak, add_xp(uid, DAILY_XP)


def wallet_info(uid):
    d = db.users.find_one({"_id": uid}) or {}
    last = d.get("last_claim")
    streak = d.get("streak", 0) if last in (tehran_day(), tehran_day(1)) else 0
    return {"tokens": int(d.get("tokens", 0)), "streak": streak, "can_claim": last != tehran_day(),
            "next_reward": DAILY_BONUS + min(streak, 4) * TOKEN_SCALE + perks_at(lvl_of(int(d.get("xp", 0))))["daily"], "refs": int(d.get("refs", 0)), "spent": int(d.get("spent", 0))}


def redeem(uid, code):
    """(تعداد توکن، پیام خطا)"""
    code = re.sub(r"[^A-Za-z0-9_\-]", "", str(code)).upper()[:32]
    c = db.coupons.find_one({"_id": code}) if code else None
    if not c:
        return 0, "کد معتبر نیست"
    if c.get("exp") and naive(c["exp"]) < naive():
        return 0, "این کد منقضی شده"
    ok = db.coupons.update_one({"_id": code, "used_by": {"$ne": uid}, "used": {"$lt": c.get("max", 1)}},
                               {"$inc": {"used": 1}, "$push": {"used_by": uid}}).modified_count == 1
    if not ok:
        return 0, "این کد قبلاً استفاده شده یا ظرفیتش تموم شده"
    credit(uid, c["tokens"], "coupon", key=f"coupon:{code}:{uid}")
    return int(c["tokens"]), ""


# ───────────────────────── سطح، ماموریت‌ها و دعوت ─────────────────────────
# هر سطح: XP لازم، عنوان، توکنِ هدیه‌ی رسیدن به سطح و مزایای ماندگار (مزایای سطح‌ها روی هم جمع می‌شن)
#   bots = + سقف ساخت ربات      disc = ٪ کاهش نرخ مصرف توکن   daily = + جایزه‌ی روزانه
#   mb / files = + فضا و تعداد رسانه   ver = + نسخه‌ی قابل بازگشت   bc = + سقف گیرنده‌ی پیام همگانی
#   free_enhance = «کامل‌ترش کن» رایگان
def _lx(base_xp, slow):
    """آستانه‌ی XP هر سطح: مقدار پایه × XP_SCALE × ضریب کندی (سطح‌های بالاتر کندتر می‌رسن)، رُند به مضرب ۵۰"""
    return int(round(base_xp * XP_SCALE * slow / 50.0)) * 50 if base_xp else 0


T = TOKEN_SCALE
LEVELS = [
    {"xp": _lx(0, 1),     "title": "تازه‌کار",  "tokens": 0,       "perks": {}},
    {"xp": _lx(50, 1.5),  "title": "کاوشگر",    "tokens": 10 * T,  "perks": {"bots": 2}},
    {"xp": _lx(130, 1.6), "title": "سازنده",    "tokens": 15 * T,  "perks": {"disc": 5}},
    {"xp": _lx(250, 1.7), "title": "حرفه‌ای",    "tokens": 20 * T,  "perks": {"mb": 40, "files": 20}},
    {"xp": _lx(430, 1.8), "title": "ناظر",      "tokens": 30 * T,  "perks": {"bots": 3, "daily": 2 * T}},
    {"xp": _lx(680, 1.9), "title": "Ai منیجر",     "tokens": 40 * T,  "perks": {"disc": 5, "ver": 4}},
    {"xp": _lx(1000, 2.0), "title": "نخبه",      "tokens": 50 * T,  "perks": {"bc": 5000, "free_enhance": True}},
    {"xp": _lx(1400, 2.1), "title": "لجند",  "tokens": 80 * T,  "perks": {"bots": 5, "disc": 10, "daily": 3 * T}},
]

# ماموریت‌ها زنجیره‌ای‌ان؛ هر مرحله (هدف، توکن، XP) بعد از دریافت جایزه‌ی قبلی باز می‌شه
TASKS = [
    # rich=True: کارت مرحله‌ای؛ هر مرحله می‌تونه معیار و عنوان مخصوص خودش رو داشته باشه: (هدف، توکن، XP, معیار, کلید, عنوان, توضیح)
    {"id": "bots",     "icon": "bot",    "title": "ساخت ربات",        "metric": "bots",     "text": "ساخت {n} ربات", "rich": True,
     "desc": "از ایده تا ربات حرفه‌ای در سه قدم",
     "steps": [(1, 5, 20, "bots", "bots:1", "ساخت ربات", "اولین ربات خودت رو بساز"),
               (1, 10, 40, "live", "bots:live", "فعال‌سازی", "ربات رو با توکن BotFather فعال کن"),
               (1, 15, 60, "edits", "bots:edit", "توسعه و ارتقا", "ربات رو یک بار با هوش مصنوعی ارتقا بده")]},
    {"id": "audience", "icon": "users",  "title": "رشد مخاطب",       "metric": "audience", "text": "رسیدن مجموع کاربران ربات‌هات به {n} نفر", "rich": True,
     "desc": "مجموع کاربران همه‌ی ربات‌هات", "names": ["اولین رشد کاربران", "محله‌ی پرجمعیت", "شهرت محلی", "کانون توجه", "ستاره‌ی تلگرام"],
     "steps": [(10, 10, 30), (50, 20, 60), (100, 40, 100), (500, 80, 200), (1000, 150, 350)]},
    {"id": "refs",     "icon": "medal",  "title": "تشکیل ناوگان",          "metric": "refs",     "text": "دعوت موفق {n} دوست", "rich": True,
     "desc": "دوستات رو دعوت کن و با هم رشد کنید", "names": ["رشد ناوگان", "تیم کوچک", "ناخدا"],
     "steps": [(1, 5, 30), (5, 15, 80), (15, 40, 150)]},
    {"id": "edits",    "icon": "spark",  "title": "ارتقا با هوش مصنوعی", "metric": "edits",  "text": "ارتقای ربات با هوش مصنوعی {n} بار", "rich": True,
     "desc": "ربات‌هات رو با هوش مصنوعی کامل‌تر کن", "names": ["توسعه", "هم‌فکر هوشمند"],
     "steps": [(5, 15, 50), (15, 30, 100)]},
    {"id": "streak",   "icon": "flame",  "title": "استمرار",         "metric": "streak",   "text": "{n} روز متوالی دریافت پاداش روزانه ", "rich": True,
     "desc": "هر روز جایزه‌ی روزانه رو بگیر", "names": ["کسب اولین پاداش روزانه", "هفته‌ی طلایی", "باشگاه سی‌روزه"],
     "steps": [(3, 5, 20), (7, 15, 50), (30, 60, 150)]},
]


def task_steps(t):
    out = []
    for st in t["steps"]:
        g, tk, x = st[:3]
        tk, x = tk * TOKEN_SCALE, x * XP_SCALE
        if len(st) > 3:
            metric, key, label, hint = st[3], st[4], st[5], st[6]
        else:
            metric, key = t["metric"], f"{t['id']}:{g}"
            hint = t["text"].format(n=f"{g:,}")
            label = t["names"][len(out)] if t.get("names") else hint
        out.append({"goal": g, "tokens": tk, "xp": x, "metric": metric, "key": key, "label": label, "hint": hint})
    return out


def lvl_of(xp):
    n = 1
    for i, L in enumerate(LEVELS, 1):
        if xp >= L["xp"]:
            n = i
    return n


def perks_at(level):
    p = {"bots": 0, "disc": 0, "daily": 0, "mb": 0, "files": 0, "ver": 0, "bc": 0, "free_enhance": False}
    for L in LEVELS[:level]:
        for k, v in L["perks"].items():
            p[k] = (p[k] or v) if isinstance(v, bool) else p[k] + v
    p["disc"] = min(p["disc"], MAX_DISCOUNT)
    return p


def perks_of(uid):
    if uid is None:
        return perks_at(1)
    d = db.users.find_one({"_id": uid}, {"xp": 1}) or {}
    return perks_at(lvl_of(int(d.get("xp", 0))))


def perk_texts(p):
    out = []
    if p.get("bots"):
        out.append(f"سقف ساخت ربات +{p['bots']}")
    if p.get("disc"):
        out.append(f"{p['disc']}٪ کاهش نرخ مصرف توکن")
    if p.get("daily"):
        out.append(f"جایزه‌ی روزانه +{p['daily']} توکن")
    if p.get("mb"):
        out.append(f"فضای رسانه +{p['mb']} مگابایت و +{p.get('files', 0)} فایل")
    if p.get("ver"):
        out.append(f"+{p['ver']} نسخه‌ی قابل بازگشت برای هر ربات")
    if p.get("bc"):
        out.append(f"سقف پیام همگانی +{p['bc']} نفر")
    if p.get("free_enhance"):
        out.append("«کامل‌ترش کن» رایگان")
    return out


def max_bots(uid):
    return MAX_BOTS + perks_of(uid)["bots"]


def cut(uid, n):
    """نرخ مصرف توکن بعد از تخفیف سطح (هزینه‌ی ۱ توکنی دست نمی‌خوره)"""
    pct = perks_of(uid)["disc"] if uid is not None else 0
    return n if pct <= 0 or n <= 1 else max(1, int(n * (100 - pct) / 100 + 0.5))


AI_MSG_COST = TOKEN_SCALE      # حالت fixed: هزینه‌ی هر «بسته‌ی» پیام هوشمند (هر ai_per پیام = AI_MSG_COST توکن)


def ai_per(uid):
    """حالت fixed: هر چند پیام هوشمند = یک بسته‌ی AI_MSG_COST توکنی (با تخفیف سطح بیشتر می‌شه)"""
    return max(1, round(AI_MSGS_PER_TOKEN * 100 / (100 - perks_of(uid)["disc"])))


def add_xp(uid, n):
    """XP اضافه می‌کنه و پاداش توکنِ هر سطحِ تازه رو (فقط یک بار) می‌ده؛ خروجی: (سطح قبلی، سطح جدید)"""
    n = int(n)
    if n <= 0:
        return None
    d = db.users.find_one_and_update({"_id": uid}, {"$inc": {"xp": n}}, return_document=ReturnDocument.BEFORE)
    if not d:
        return None
    old = lvl_of(int(d.get("xp", 0)))
    new = lvl_of(int(d.get("xp", 0)) + n)
    for lv in range(old + 1, new + 1):
        if LEVELS[lv - 1]["tokens"]:
            credit(uid, LEVELS[lv - 1]["tokens"], "levelup", key=f"lv:{uid}:{lv}")
    return old, new


def up_dict(up):
    if not up or up[1] <= up[0]:
        return None
    return {"from": up[0], "to": up[1], "title": LEVELS[up[1] - 1]["title"],
            "tokens": sum(LEVELS[i - 1]["tokens"] for i in range(up[0] + 1, up[1] + 1)),
            "perks": [t for i in range(up[0] + 1, up[1] + 1) for t in perk_texts(LEVELS[i - 1]["perks"])]}


def lv_info(uid):
    d = db.users.find_one({"_id": uid}, {"xp": 1}) or {}
    xp = int(d.get("xp", 0))
    n = lvl_of(xp)
    nxt = LEVELS[n] if n < len(LEVELS) else None
    return {"xp": xp, "level": n, "title": LEVELS[n - 1]["title"], "from": LEVELS[n - 1]["xp"],
            "to": nxt["xp"] if nxt else None, "next_title": nxt["title"] if nxt else None,
            "next_perks": perk_texts(nxt["perks"]) if nxt else [], "next_tokens": nxt["tokens"] if nxt else 0}


def levels_public():
    return [{"n": i, "xp": L["xp"], "title": L["title"], "tokens": L["tokens"], "perks": perk_texts(L["perks"])}
            for i, L in enumerate(LEVELS, 1)]


def task_metrics(uid, d):
    bots = list(db.bots.find({"owner": uid}, {"active": 1}))
    ids = [str(b["_id"]) for b in bots]
    return {
        "bots": len(bots),
        "live": sum(1 for b in bots if b.get("active")),
        "audience": db.subs.count_documents({"bot": {"$in": ids}, "blocked": {"$ne": True}, "chat": {"$ne": uid}}) if ids else 0,
        "edits": db.ledger.count_documents({"uid": uid, "why": "edit"}),
        "bc": db.ledger.count_documents({"uid": uid, "why": "broadcast"}),
        "media": db.media.count_documents({"owner": uid}),
        "streak": max(int(d.get("best_streak", 0)), int(d.get("streak", 0))),
        "refs": int(d.get("refs", 0)),
        "tpl": db.ledger.count_documents({"uid": uid, "why": "template"}),
        "forms": db.submissions.count_documents({"bot_id": {"$in": ids}}) if ids else 0,
        "spent": int(d.get("spent", 0)),
    }


def tasks_state(uid):
    d = db.users.find_one({"_id": uid}) or {}
    done = set(d.get("tasks_done", []))
    m = task_metrics(uid, d)
    items = []
    for t in TASKS:
        steps = [dict(s, done=s["key"] in done, value=min(m[s["metric"]], s["goal"])) for s in task_steps(t)]
        nxt = next((s for s in steps if not s["done"]), None)
        cur = nxt or steps[-1]
        for s in steps:
            s["ready"] = s is nxt and m[s["metric"]] >= s["goal"]
        v = m[cur["metric"]]
        items.append({"id": t["id"], "icon": t["icon"], "title": t["title"], "text": t["text"].format(n=cur["goal"]),
                      "rich": bool(t.get("rich")), "desc": t.get("desc", ""),
                      "steps": [{"label": s["label"], "hint": s["hint"], "goal": s["goal"], "value": s["value"], "tokens": s["tokens"], "xp": s["xp"],
                                 "done": s["done"], "ready": s["ready"]} for s in steps],
                      "value": v, "goal": cur["goal"], "tokens": cur["tokens"], "xp": cur["xp"],
                      "stage": sum(1 for s in steps if s["done"]), "total": len(steps),
                      "done": nxt is None, "ready": nxt is not None and v >= cur["goal"]})
    return items


def mother_link(uid):
    return f"https://t.me/{MOTHER_USERNAME}?start=ref_{uid}" if MOTHER_USERNAME else ""


def link_referral(new_uid, ref_uid):
    """موقع ورود کاربر تازه با لینک دعوت: هدیه‌ی دعوت‌شده همین الان، پاداش دعوت‌کننده بعد از اولین ربات"""
    if ref_uid == new_uid or not db.users.find_one({"_id": ref_uid}):
        return
    r = db.users.update_one({"_id": new_uid, "ref_by": {"$exists": False}}, {"$set": {"ref_by": ref_uid}})
    if r.modified_count:
        credit(new_uid, REF_INVITEE, "invited", key=f"inv:{new_uid}")


def settle_referral(uid):
    d = db.users.find_one_and_update(
        {"_id": uid, "ref_by": {"$exists": True}, "ref_paid": {"$ne": True}}, {"$set": {"ref_paid": True}})
    if not d or not d.get("ref_by"):
        return
    ref = d["ref_by"]
    cur = db.users.find_one({"_id": ref})
    if not cur or int(cur.get("refs", 0)) >= REF_MAX_PER_USER:
        return
    r = db.users.find_one_and_update({"_id": ref}, {"$inc": {"refs": 1}}, return_document=ReturnDocument.AFTER)
    if not r:
        return
    credit(ref, REF_INVITER, "referral", key=f"ref:{ref}:{uid}")
    n_ref = int(r.get("refs", 0))
    bonus = dict(REF_MILESTONES).get(n_ref)
    if bonus:
        credit(ref, bonus, "milestone", key=f"ms:{ref}:{n_ref}")
    db.users.update_one({"_id": ref}, {"$inc": {"ref_earned": REF_INVITER + (bonus or 0)}})
    extra = f" و پاداش ویژه‌ی {bonus} توکن" if bonus else ""
    tg(MOTHER_TOKEN, "sendMessage", chat_id=ref,
       text=f"یکی از دوستانت اولین رباتش رو ساخت. {REF_INVITER} توکن{extra} به حسابت اضافه شد.")


def ai_tick(owner):
    """حالت fixed: هر AI_MSGS_PER_TOKEN پیام هوش مصنوعی داخل ربات = ۱ توکن از صاحب ربات؛ False یعنی موجودی تموم شده"""
    d = db.users.find_one_and_update({"_id": owner}, {"$inc": {"ai_n": 1}}, return_document=ReturnDocument.AFTER)
    if not d:
        return False
    if (int(d.get("ai_n", 1)) - 1) % ai_per(owner) == 0 and not charge_up_to(owner, AI_MSG_COST, "ai_chat", daily_key=True):
        db.users.update_one({"_id": owner}, {"$inc": {"ai_n": -1}})
        return False
    return True


def low_balance_notice(owner):
    """وقتی موجودی کم می‌شه، روزی یک بار از طریق ربات مادر خبر می‌دیم"""
    try:
        if balance(owner) > LOW_TOKENS:
            return
        db.aiuse.insert_one({"_id": f"low:{owner}:{tehran_day()}"})
        tg(MOTHER_TOKEN, "sendMessage", chat_id=owner, reply_markup={"inline_keyboard": [[{"text": "شارژ توکن", "web_app": {"url": BASE_URL}}]]},
           text="موجودی توکنت داره تموم می‌شه. وقتی تموم بشه بخش‌های هوشمند رباتات از کار می‌افتن.")
    except DuplicateKeyError:
        pass
    except Exception:
        log.exception("low_balance_notice failed")


# ───────────────────────── کتابخونه‌ی رسانه ─────────────────────────
MEDIA_METHOD = {"photo": "sendPhoto", "video": "sendVideo", "animation": "sendAnimation",
                "audio": "sendAudio", "voice": "sendVoice", "document": "sendDocument"}
MEDIA_KEYS = ("photo", "video", "animation", "audio", "voice", "document", "sticker", "video_note")
SAFE_INLINE = {"image/jpeg", "image/png", "image/webp", "image/gif"}
CHUNK = 1_000_000


def media_kind(mime, fname, size):
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
    mime = (mime or "").split(";")[0].strip().lower()
    if mime == "image/gif" or ext == "gif":
        return "animation"
    if mime in ("image/jpeg", "image/png", "image/webp") or ext in ("jpg", "jpeg", "png", "webp"):
        return "photo" if size <= 10 * 1024 * 1024 else "document"
    if mime == "video/mp4" or ext in ("mp4", "m4v"):
        return "video"
    if mime in ("audio/mpeg", "audio/mp3", "audio/mp4", "audio/x-m4a") or ext in ("mp3", "m4a"):
        return "audio"
    if mime in ("audio/ogg", "audio/opus") or ext in ("ogg", "oga", "opus"):
        return "voice"
    return "document"


def media_sig(mid):
    return hmac.new(SECRET_KEY.encode(), f"media:{mid}".encode(), hashlib.sha256).hexdigest()[:24]


def public_media(m):
    mid = str(m["_id"])
    return {"id": mid, "name": m.get("name", ""), "kind": m["kind"], "size": m.get("size", 0),
            "url": f"/m/{mid}?s={media_sig(mid)}"}


def media_list(uid):
    return [public_media(m) for m in db.media.find({"owner": uid}).sort("created", -1)]


def get_media(mid, owner=None):
    try:
        q = {"_id": ObjectId(mid)}
    except (InvalidId, TypeError):
        return None
    if owner is not None:
        q["owner"] = owner
    return db.media.find_one(q)


def media_bytes(m):
    parts = db.mchunks.find({"m": str(m["_id"])}).sort("i", 1)
    return b"".join(bytes(c["d"]) for c in parts)


def media_delete(m):
    mid = str(m["_id"])
    db.mchunks.delete_many({"m": mid})
    db.mfid.delete_many({"mid": mid})
    db.media.delete_one({"_id": m["_id"]})


def plain_html(s):
    """متن HTML رو به متن ساده تبدیل می‌کنه (وقتی تلگرام تگ‌ها رو قبول نکنه)"""
    return _html.unescape(re.sub(r"<[^>]+>", "", s or ""))


def is_block_err(r):
    return bool(r.get("error_code") == 403 or re.search(r"blocked|deactivated|chat not found", str(r.get("description", "")), re.I))


def tg_html(token, method, **data):
    """ارسال/ویرایش با parse_mode=HTML (بولد، لینک و…)؛ اگه تلگرام تگ‌ها رو نپذیرفت همون متن بدون تگ می‌ره"""
    key = "caption" if "caption" in data else "text"
    r = tg(token, method, parse_mode="HTML", **data)
    if not r.get("ok") and parse_err(r):
        data[key] = plain_html(data.get(key, ""))
        r = tg(token, method, **data)
    return r


def parse_err(r):
    return bool(re.search(r"parse entities|can't parse|unsupported start tag", str(r.get("description", "")), re.I))


def tg_media(token, bot_id, chat_id, mid, caption="", markup=None, parse=None):
    """رسانه‌ی کتابخونه رو برای کاربر می‌فرسته. بار اول آپلود می‌شه و file_id همون ربات ذخیره می‌شه؛ بعدش فوری می‌ره.
    parse='HTML' یعنی کپشن با فرمت HTML؛ اگه تلگرام تگ‌ها رو نپذیرفت، همون کپشن بدون تگ فرستاده می‌شه."""
    m = get_media(mid)
    if not m:
        return False
    kind, method = m["kind"], MEDIA_METHOD[m["kind"]]
    base = {"chat_id": chat_id}
    if caption:
        base["caption"] = caption[:1024]
        if parse:
            base["parse_mode"] = parse
    if markup:
        base["reply_markup"] = markup
    ck = f"{bot_id}:{mid}"
    c = db.mfid.find_one({"_id": ck})
    if c:
        r = tg(token, method, **base, **{kind: c["fid"]})
        if r.get("ok"):
            return True
        if parse and caption and parse_err(r):
            return tg_media(token, bot_id, chat_id, mid, plain_html(caption), markup, None)
        db.mfid.delete_one({"_id": ck})
    form = {k: (json.dumps(v) if isinstance(v, (dict, list)) else str(v)) for k, v in base.items()}
    if kind == "video":
        form["supports_streaming"] = "true"
    try:
        resp = requests.post(f"https://api.telegram.org/bot{token}/{method}", data=form, timeout=120,
                             files={kind: (m.get("name") or "file", media_bytes(m), m.get("mime") or "application/octet-stream")}).json()
    except Exception as e:
        log.warning("media upload failed: %s", e)
        return False
    if not resp.get("ok"):
        if parse and caption and parse_err(resp):
            return tg_media(token, bot_id, chat_id, mid, plain_html(caption), markup, None)
        log.warning("media send rejected: %s", resp.get("description"))
        return False
    res = resp["result"]
    if kind == "photo":
        fid = (res.get("photo") or [{}])[-1].get("file_id")
    else:
        fid = (res.get(kind) or res.get("document") or res.get("video") or {}).get("file_id")
    if fid:
        db.mfid.replace_one({"_id": ck}, {"_id": ck, "mid": mid, "fid": fid}, upsert=True)
    return True


def send_rich(token, bot_id, chat, text, mid="", fmt="", markup=None):
    """ارسال یک اطلاعیه (متن با HTML اختیاری + رسانه‌ی اختیاری) به یک مخاطب.
    خروجی: (فرستاده شد؟، کاربر ربات رو بلاک کرده؟)"""
    pm = "HTML" if fmt == "html" else None
    text = text or ""

    def send_text(t):
        extra = {"reply_markup": markup} if markup else {}
        r = tg(token, "sendMessage", chat_id=chat, text=t, **({"parse_mode": pm} if pm else {}), **extra)
        if not r.get("ok") and pm and parse_err(r):
            r = tg(token, "sendMessage", chat_id=chat, text=plain_html(t), **extra)
        return r

    if mid:
        short = len(text) <= 1000
        if tg_media(token, bot_id, chat, mid, text if short else "", markup if short else None, pm):
            if text and not short:
                send_text(text)
            return True, False
    if text:
        r = send_text(text)
        return bool(r.get("ok")), (not r.get("ok")) and is_block_err(r)
    r = tg(token, "sendChatAction", chat_id=chat, action="typing")
    return False, (not r.get("ok")) and is_block_err(r)


# ───────────────────────── عضویت اجباری ربات‌ساز: خواندن تنظیمات و بررسی عضویت ─────────────────────────
FJ_DEFAULT_TEXT = "برای استفاده از ربات‌ساز اول باید عضو کانال زیر بشی 👇\nبعد از عضویت روی «عضو شدم» بزن."
FJ_CACHE, FJ_LOCK, FJ_CONF = {}, threading.Lock(), [0.0, None]


def fj_conf():
    """تنظیمات فعال عضویت اجباری یا None؛ ۱۵ ثانیه کش می‌شه"""
    t = time.time()
    if t - FJ_CONF[0] > 15:
        d = db.settings.find_one({"_id": "force_join"}) or {}
        FJ_CONF[:] = [t, d if d.get("on") and d.get("channels") else None]
    return FJ_CONF[1]


def fj_chat(c):
    return int(c["id"]) if re.fullmatch(r"-?\d+", c["id"]) else c["id"]


def fj_missing(uid, conf):
    """کانال‌هایی که کاربر عضوشون نیست. اگه ربات مادر ادمین کانال نباشه (یا خطا بشه) مانع کاربر نمی‌شیم"""
    if uid in ADMIN_IDS:
        return []
    t = time.time()
    if FJ_CACHE.get(uid, 0) > t:
        return []
    miss = []
    for c in conf["channels"]:
        r = tg(MOTHER_TOKEN, "getChatMember", chat_id=fj_chat(c), user_id=uid)
        res = r.get("result") or {}
        if r.get("ok") and (res.get("status") in ("left", "kicked") or (res.get("status") == "restricted" and not res.get("is_member", True))):
            miss.append(c)
    if not miss:
        with FJ_LOCK:
            if len(FJ_CACHE) > 5000:
                FJ_CACHE.clear()
            FJ_CACHE[uid] = t + 120
    return miss


def fj_label(c, i):
    return c["id"] if c["id"].startswith("@") else f"کانال {i}"


def fj_public(conf, miss):
    return {"text": conf.get("text") or FJ_DEFAULT_TEXT,
            "channels": [{"label": fj_label(c, i), "url": c["url"]} for i, c in enumerate(miss or conf["channels"], 1)]}


def setup_mother():
    global MOTHER_USERNAME
    if not MOTHER_USERNAME:
        MOTHER_USERNAME = ((tg(MOTHER_TOKEN, "getMe").get("result") or {}).get("username") or "")
    r = tg(MOTHER_TOKEN, "setWebhook", url=f"{BASE_URL}/mother", secret_token=MOTHER_SECRET,
           allowed_updates=["message", "callback_query", "pre_checkout_query"])
    tg(MOTHER_TOKEN, "setChatMenuButton",
       menu_button={"type": "web_app", "text": "ساخت ربات", "web_app": {"url": BASE_URL}})
    tg(MOTHER_TOKEN, "setMyCommands", commands=[{"command": "start", "description": "شروع"}])
    log.info("mother webhook: %s (@%s)", r, MOTHER_USERNAME)
