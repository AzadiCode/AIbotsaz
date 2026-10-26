# -*- coding: utf-8 -*-
"""
core.py — هسته‌ی مشترک (پایین‌ترین لایه)

این فایل به هیچ ماژول دیگری از پروژه وابسته نیست؛ همه‌ی فایل‌های دیگر از اینجا import می‌کنند.
بخش‌ها:
  • تنظیمات (Environment) و پایگاه داده
  • ابزارهای پایه
  • احراز هویت مینی‌اپ
  • کیف توکن
  • اشتراک (Premium و Pro)، ایموجی پرمیوم، ماموریت‌ها و دعوت
  • کتابخونه‌ی رسانه
  • عضویت اجباری ربات‌ساز: خواندن تنظیمات و بررسی عضویت

قرارداد: هر چیزی که چند بخش مختلف لازم دارند (تنظیمات، دیتابیس، توکن/کیف پول، رسانه، احراز هویت) همین‌جاست.
نمونه: ثابت تازه‌ی Environment ← بخش «تنظیمات»؛ تابع تازه‌ی کیف توکن ← بخش «کیف توکن».
نکته: مقدار MOTHER_USERNAME بعد از راه‌اندازی عوض می‌شه؛ بیرون از core با core.MOTHER_USERNAME بخونش.

نام‌های پایدار — فایل‌های دیگه این‌ها رو از همین فایل import می‌کنن (حذف یا تغییر نام، بقیه رو می‌شکنه).
اگه چیزی تازه برای بقیه لازمه، همین‌جا اضافه کن و در فایلِ مصرف‌کننده import کن:
  activate_plan, ADMIN_IDS, admin_only, age_sec, AI_API_KEY, AI_BASE_URL, AI_CHAT_MODEL, AI_MAX_TOKENS,
  AI_MODEL, AI_MSG_COST, AI_MSGS_PER_TOKEN, AI_NODE_MAX_TOKENS, ai_per, ai_tick, app, authed, aware,
  balance, BASE_URL, BILLING, BOARD_SCAN, BROADCAST_MAX, BROADCAST_PER_TOKEN, calc_cost, charge_up_to,
  CHUNK, claim_daily, credit, cut, DAILY_BONUS, db, DEBUG, dec, _DIG, EDIT_COST, enc,
  ENHANCE_COST, ensure_user, est_tokens, FJ_CACHE, fj_chat, FJ_CONF, fj_conf, FJ_DEFAULT_TEXT,
  fj_missing, fj_public, GEN_COST, get_bot, get_media, hold, _int, is_block_err, JOB_TIMEOUT,
  link_referral, log, low_balance_notice, MAX_BOTS, max_bots, MAX_GLOBALS,
  MAX_MEDIA, MAX_NODES, emoji_add, emoji_image, emoji_info, emoji_list, emoji_sig, fx_in, PLAN_BY_ID, PLAN_DAYS, PLAN_RANK, plan_from_payload, plan_info, plan_of, PLANS,
  plans_public, strip_fx, strip_fx_markup, strip_fx_text, MAX_NODES, MAX_PENDING_REMIND, MAX_PROMPT, MAX_STAFF, MAX_STARS, MAX_VERSIONS, media_bytes,
  media_delete, MEDIA_KEYS, media_kind, media_list, MEDIA_MAX_MB, MEDIA_QUOTA_MB, media_sig, MONGO_URI,
  mother_link, MOTHER_SECRET, MOTHER_TOKEN, naive, now, ONLINE_SECS, PACKS, parse_err, PAYMENTS,
  perks_at, perks_of, plain_html, public, public_media, rate_ok, redeem, REF_INVITEE, REF_INVITER,
  REF_MAX_PER_USER, REF_MILESTONES, REF_ON, refund, request_user, SAFE_INLINE, SCHED_ON, send_rich,
  settle_referral, setup_mother, spend, task_metrics, task_steps, TASKS, tasks_state, tehran_day,
  TEMPLATE_FACTOR, TEMPLATE_MAX_COST, TEMPLATE_MIN_COST, TEMPLATE_UNIT_COST, tg, tg_html, tg_media,
  thash, TOKEN_MIN_COST, TOKEN_OUT_RATE, TOKEN_SCALE, touch_user, wallet_info
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
ADMIN_WEB_KEY = os.environ.get("ADMIN_WEB_KEY", "").strip()   # کلید ورود ادمین از مرورگر برای تست (خالی = خاموش)
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


# ضریب اقتصاد: همه‌ی توکن‌ها (هدیه‌ها، پاداش‌ها، هزینه‌ها، بسته‌ها) با این ضریب بالا می‌رن.
# هدیه‌ی ثبت‌نام = ۱۰۰ × TOKEN_SCALE = ۱۰۰۰ توکن؛ بقیه دقیقاً با همین نسبت.
TOKEN_SCALE = max(1, _int("TOKEN_SCALE", 10))

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
REF_INVITER       = _int("REF_INVITER", _int("REF_BONUS_INVITER", 30 * TOKEN_SCALE))   # پاداش دعوت‌کننده
REF_INVITEE       = _int("REF_INVITEE", _int("REF_BONUS_NEW", 20 * TOKEN_SCALE))       # هدیه‌ی دعوت‌شده
REF_MAX_PER_USER  = _int("REF_MAX_PER_USER", 1000)   # سقف دعوت پاداش‌دار هر نفر
REF_ON            = "create" if os.environ.get("REF_ON", "activate").strip().lower() == "create" else "activate"
REF_MILESTONES    = [(5, 50 * TOKEN_SCALE), (15, 150 * TOKEN_SCALE), (50, 500 * TOKEN_SCALE)]   # (تعداد دعوت موفق، پاداش اضافه)
LOW_TOKENS        = _int("LOW_TOKENS", 10 * TOKEN_SCALE)          # زیر این مقدار به صاحب ربات هشدار می‌دیم
try:
    PACKS = json.loads(os.environ.get("PACKS", "")) or []
except ValueError:
    PACKS = []
if not PACKS:   # بسته‌های خرید با Telegram Stars
    PACKS = [{"id": "p1", "tokens": 200 * TOKEN_SCALE, "stars": 20},
             {"id": "p2", "tokens": 700 * TOKEN_SCALE, "stars": 45},
             {"id": "p3", "tokens": 2000 * TOKEN_SCALE, "stars": 120}]

# رسانه
MEDIA_MAX_MB   = _int("MEDIA_MAX_MB", 15)       # سقف حجم هر فایل
MEDIA_QUOTA_MB = _int("MEDIA_QUOTA_MB", 60)     # سقف کل فایل‌های هر کاربر
MAX_MEDIA      = _int("MAX_MEDIA", 60)          # سقف تعداد فایل هر کاربر

# اشتراک و ماموریت‌ها (جدول پلن‌ها و ماموریت‌ها پایین‌تر، بخش «اشتراک» و «ماموریت‌ها»)
MAX_DISCOUNT = 20          # سقف کاهش نرخ مصرف توکن از راه اشتراک (درصد)

MAX_PROMPT   = 4000
MAX_VERSIONS = 6
MAX_NODES    = _int("MAX_NODES", 200)      # پایه‌ی سقف بخش‌ها؛ سقف واقعی هر کاربر پلن‌محور است (limits_of)
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
if ADMIN_WEB_KEY and len(ADMIN_WEB_KEY) < 8:
    log.warning("ADMIN_WEB_KEY ضعیفه؛ برای ورود ادمین از مرورگر یه کلید بلندتر بذار یا خالی بذار (خاموش).")

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
_index(db.emojis, "owner")
_index(db.emojis, "eid")
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
_index(db.apps, "owner")                                  # مینی‌اپ‌ساز: سند هر ربات (پیش‌نویس + منتشرشده)
_index(db.app_ev, "t", expireAfterSeconds=90 * 86400)     # شمارنده‌ی روزانه‌ی باز شدن/کلیک مینی‌اپ (۹۰ روز)
_index(db.appai, "t", expireAfterSeconds=86400)           # حافظه‌ی گفتگوی هوشمند مینی‌اپ (یک روز)
_index(db.invlink, [("bot", 1), ("u", 1)], unique=True)   # لینک دعوت اختصاصی هر کاربر (ربات رشد)
_index(db.invlink, [("bot", 1), ("link", 1)])             # یافتن دعوت‌کننده از لینک
_index(db.growth, [("bot", 1), ("by", 1), ("day", 1)])    # سقف روزانه و شمارش دعوت‌های فعال
_index(db.kbdoc, "bot")                                   # دانش عامل هوشمند
_index(db.cvars, [("bot", 1), ("chat", 1)], unique=True)  # متغیرهای دامنه‌ی گروه (هر چت یک سند)
_index(db.aicache, "t", expireAfterSeconds=7 * 86400)     # کش پاسخ تکراری گفتگوی هوشمند
_index(db.spost, "t", expireAfterSeconds=7 * 86400)       # پست‌های در انتظار تأیید کانال
_index(db.glog, "t", expireAfterSeconds=2 * 86400)        # پیام‌های گروه برای خلاصه‌ی روزانه
_index(db.subs, [("bot", 1), ("u", 1)])                   # اشتراک دوره‌ی کاربرها (اکشن sub_add / شرط sub)
_index(db.dcodes, [("bot", 1), ("used", 1)])              # کدهای تخفیف (اکشن disc)
_index(db.comps, "owner")                                 # قطعه‌های آماده‌ی مینی‌اپ (sync بین دستگاه‌ها)
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
        j = r.json()
        # محدودیت نرخ تلگرام: اگر تلگرام گفت کمی صبر کن (تا ۵ ثانیه)، همان یک بار دوباره تلاش می‌کنیم
        if r.status_code == 429 and not j.get("ok"):
            import time as _t
            wait = min(5.0, float((j.get("parameters") or {}).get("retry_after", 0)) or 0.5)
            _t.sleep(wait)
            r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=data, timeout=15)
            j = r.json()
        return j
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
def verify_init_data(init_data, token=MOTHER_TOKEN):
    """راستی‌آزمایی امضای initData تلگرام با توکنِ داده‌شده (پیش‌فرض: ربات مادر؛ رانتایم مینی‌اپ توکن همان ربات فرزند را می‌دهد)"""
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        got = pairs.pop("hash", None)
        if not got:
            return None
        check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
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
    reward = DAILY_BONUS + min(streak - 1, 4) * TOKEN_SCALE + perks_at(plan_of(d))["daily"]
    r = db.users.find_one_and_update(
        {"_id": uid, "last_claim": {"$ne": today}},
        {"$set": {"last_claim": today, "streak": streak}, "$inc": {"tokens": reward}, "$max": {"best_streak": streak}},
        return_document=ReturnDocument.AFTER)
    if not r:
        return None
    log_ledger(uid, reward, "daily")
    return reward, streak


def wallet_info(uid):
    d = db.users.find_one({"_id": uid}) or {}
    last = d.get("last_claim")
    streak = d.get("streak", 0) if last in (tehran_day(), tehran_day(1)) else 0
    return {"tokens": int(d.get("tokens", 0)), "streak": streak, "can_claim": last != tehran_day(),
            "next_reward": DAILY_BONUS + min(streak, 4) * TOKEN_SCALE + perks_at(plan_of(d))["daily"], "refs": int(d.get("refs", 0)), "spent": int(d.get("spent", 0))}


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


# ───────────────────────── اشتراک (Premium و Pro)، ماموریت‌ها و دعوت ─────────────────────────
# هر پلن یک ماه (PLAN_DAYS روز) اعتبار داره و با ستاره‌ی تلگرام خریده می‌شه. «tokens» هدیه‌ی توکن هر بار خرید یا تمدیده.
# مزایای هر پلن (مقدارها برای خودِ همون پلنِ فعال‌ان، نه روی هم جمع‌شونده):
#   bots = + سقف ساخت ربات      disc = ٪ کاهش نرخ مصرف توکن   daily = + جایزه‌ی روزانه
#   mb / files = + فضا و تعداد رسانه   ver = + نسخه‌ی قابل بازگشت   bc = + سقف گیرنده‌ی پیام همگانی
#   ub = تعداد یوزربات (۰ = بسته)   emoji = سقف کتابخونه‌ی ایموجی پرمیوم (۰ = بسته)   btn = دکمه‌ی رنگی
#   free_enhance = «کامل‌ترش کن» رایگان
PLAN_DAYS = max(1, _int("PLAN_DAYS", 30))
T = TOKEN_SCALE
# perks مینی‌اپ: apps = چند ربات می‌تونن مینی‌اپ داشته باشن، blocks = سقف کل بلوک‌های هر مینی‌اپ
PLANS = [
    {"id": "free", "title": "Free", "stars": 0, "tokens": 0, "perks": {}},
    {"id": "premium", "title": "Premium", "stars": _int("PREMIUM_STARS", 80), "tokens": 300 * T,
     "perks": {"bots": 3, "disc": 10, "daily": 2 * T, "mb": 60, "files": 40, "ver": 4, "bc": 5000, "ub": 1, "emoji": 30, "btn": True,
               "apps": 3, "blocks": 100}},
    {"id": "pro", "title": "Pro", "stars": _int("PRO_STARS", 150), "tokens": 1000 * T,
     "perks": {"bots": 8, "disc": 20, "daily": 5 * T, "mb": 200, "files": 120, "ver": 8, "bc": 20000, "ub": 2, "emoji": 200, "btn": True, "free_enhance": True,
               "apps": 8, "blocks": 150}},
]
PLAN_BY_ID = {p["id"]: p for p in PLANS}
PLAN_RANK = {p["id"]: i for i, p in enumerate(PLANS)}


# ماموریت‌ها زنجیره‌ای‌ان؛ هر مرحله (هدف، توکن) بعد از دریافت جایزه‌ی قبلی باز می‌شه. پاداش همه‌ی مرحله‌ها توکنه.
TASKS = [
    # rich=True: کارت مرحله‌ای؛ هر مرحله می‌تونه معیار و عنوان مخصوص خودش رو داشته باشه: (هدف، توکن، معیار, کلید, عنوان, توضیح)
    {"id": "bots",     "icon": "bot",    "title": "ساخت ربات",        "metric": "bots",     "text": "ساخت {n} ربات", "rich": True,
     "desc": "از ایده تا ربات حرفه‌ای در سه قدم",
     "steps": [(1, 5, "bots", "bots:1", "ساخت ربات", "اولین ربات خودت رو بساز"),
               (1, 10, "live", "bots:live", "فعال‌سازی", "ربات رو با توکن BotFather فعال کن"),
               (1, 15, "edits", "bots:edit", "توسعه و ارتقا", "ربات رو یک بار با هوش مصنوعی ارتقا بده")]},
    {"id": "audience", "icon": "users",  "title": "رشد مخاطب",       "metric": "audience", "text": "رسیدن مجموع کاربران ربات‌هات به {n} نفر", "rich": True,
     "desc": "مجموع کاربران همه‌ی ربات‌هات", "names": ["اولین رشد کاربران", "محله‌ی پرجمعیت", "شهرت محلی", "کانون توجه", "ستاره‌ی تلگرام"],
     "steps": [(10, 10), (50, 20), (100, 40), (500, 80), (1000, 150)]},
    {"id": "refs",     "icon": "medal",  "title": "تشکیل ناوگان",          "metric": "refs",     "text": "دعوت موفق {n} دوست", "rich": True,
     "desc": "دوستات رو دعوت کن و با هم رشد کنید", "names": ["رشد ناوگان", "تیم کوچک", "ناخدا"],
     "steps": [(1, 5), (5, 15), (15, 40)]},
    {"id": "edits",    "icon": "spark",  "title": "ارتقا با هوش مصنوعی", "metric": "edits",  "text": "ارتقای ربات با هوش مصنوعی {n} بار", "rich": True,
     "desc": "ربات‌هات رو با هوش مصنوعی کامل‌تر کن", "names": ["توسعه", "هم‌فکر هوشمند"],
     "steps": [(5, 15), (15, 30)]},
    {"id": "streak",   "icon": "flame",  "title": "استمرار",         "metric": "streak",   "text": "{n} روز متوالی دریافت پاداش روزانه ", "rich": True,
     "desc": "هر روز جایزه‌ی روزانه رو بگیر", "names": ["کسب اولین پاداش روزانه", "هفته‌ی طلایی", "باشگاه سی‌روزه"],
     "steps": [(3, 5), (7, 15), (30, 60)]},
    {"id": "miniapp",  "icon": "layers", "title": "مینی‌اپ",          "metric": "apps",     "text": "برای {n} ربات مینی‌اپ منتشر کن",
     "desc": "یک مینی‌اپ بساز، منتشر کن و با یک دکمه از داخل ربات بازش کن",
     "steps": [(1, 15)]},
]


def task_steps(t):
    out = []
    for st in t["steps"]:
        g, tk = st[:2]
        tk = tk * TOKEN_SCALE
        if len(st) > 2:
            metric, key, label, hint = st[2], st[3], st[4], st[5]
        else:
            metric, key = t["metric"], f"{t['id']}:{g}"
            hint = t["text"].format(n=f"{g:,}")
            label = t["names"][len(out)] if t.get("names") else hint
        out.append({"goal": g, "tokens": tk, "metric": metric, "key": key, "label": label, "hint": hint})
    return out


def plan_of(d):
    """شناسه‌ی پلنِ فعالِ کاربر (سند کاربر)؛ اگه اشتراک تموم شده باشه free"""
    d = d or {}
    p, exp = d.get("plan"), d.get("plan_exp")
    return p if p in PLAN_BY_ID and p != "free" and exp and naive(exp) > naive() else "free"


def perks_at(plan_id):
    p = {"bots": 0, "disc": 0, "daily": 0, "mb": 0, "files": 0, "ver": 0, "bc": 0, "ub": 0, "emoji": 0, "btn": False, "free_enhance": False,
         "apps": 1, "blocks": 30}
    for k, v in (PLAN_BY_ID.get(plan_id) or PLANS[0])["perks"].items():
        p[k] = v
    p["disc"] = min(p["disc"], MAX_DISCOUNT)
    return p


def perks_of(uid):
    if uid is None:
        return perks_at("free")
    return perks_at(plan_of(db.users.find_one({"_id": uid}, {"plan": 1, "plan_exp": 1})))


def perk_texts(p):
    out = []
    if p.get("btn"):
        out.append("دکمه‌های رنگی (آبی، سبز، قرمز)")
    if p.get("emoji"):
        out.append(f"ایموجی پرمیوم در متن و دکمه‌ها (تا {p['emoji']} ایموجی)")
    if p.get("ub"):
        out.append(f"یوزربات: {p['ub']} اکانت")
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
    if p.get("apps", 0) > 1:
        out.append(f"مینی‌اپ برای {p['apps']} ربات (تا {p.get('blocks', 30)} بلوک)")
    return out


def plans_public():
    return [{"id": p["id"], "title": p["title"], "stars": p["stars"], "tokens": p["tokens"], "days": PLAN_DAYS,
             "perks": perk_texts(perks_at(p["id"]))} for p in PLANS]


def plan_info(uid):
    d = db.users.find_one({"_id": uid}, {"plan": 1, "plan_exp": 1}) or {}
    pid = plan_of(d)
    exp = naive(d["plan_exp"]) if pid != "free" else None
    return {"id": pid, "title": PLAN_BY_ID[pid]["title"], "exp": exp.isoformat() + "Z" if exp else None,
            "days_left": max(0, math.ceil((exp - naive()).total_seconds() / 86400)) if exp else 0}


def activate_plan(uid, plan_id, days=None):
    """فعال‌سازی یا تمدید اشتراک. تمدیدِ همون پلن از انتهای زمان فعلی حساب می‌شه؛ پلن دیگه از همین الان شروع می‌شه.
    plan_id = free یعنی لغو. خروجی: زمان پایان (یا None)"""
    if plan_id == "free":
        db.users.update_one({"_id": uid}, {"$unset": {"plan": "", "plan_exp": ""}})
        return None
    if plan_id not in PLAN_BY_ID:
        return None
    d = db.users.find_one({"_id": uid}) or {}
    base = naive(d["plan_exp"]) if plan_of(d) == plan_id else naive()
    exp = base + timedelta(days=int(days or PLAN_DAYS))
    db.users.update_one({"_id": uid}, {"$set": {"plan": plan_id, "plan_exp": exp}})
    return exp


def plan_from_payload(payload, uid):
    """payload فاکتور اشتراک: sub_<plan>:<uid>"""
    try:
        pid, owner = str(payload).split(":")
        if int(owner) != uid or not pid.startswith("sub_"):
            return None
    except ValueError:
        return None
    p = PLAN_BY_ID.get(pid[4:])
    return p if p and p["id"] != "free" else None


def max_bots(uid):
    return MAX_BOTS + perks_of(uid)["bots"]


# ───────────────────────── نسخه‌ی ساخت، قابلیت‌های روشن و سقف پلن‌محور ─────────────────────────
# caps.py پایین‌ترین لایه است (هیچ importی ندارد)؛ رابط کاربری، استودیو و پرامپت AI همه از همین می‌سازند.
from caps import BUILD, LIMITS, caps_public, limit_of   # noqa: E402
APP_URL = BASE_URL + "/?v=" + BUILD                # دکمه‌ی مینی‌اپ با نسخه: کش چسبیده‌ی وب‌ویو را هم می‌شکند
APP_DIR = os.path.dirname(os.path.abspath(__file__))
_ASSET_V = {}                                      # rel path -> (mtime, اثر انگشت ۸ رقمی)


def asset_v(rel):
    """اثر انگشت محتوای فایل استاتیک برای cache-bust خودکار؛ فایل جدید روی سرور = URL جدید، بدون دست بردن در BUILD"""
    p = os.path.join(APP_DIR, rel.replace("/", os.sep))
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return BUILD
    c = _ASSET_V.get(rel)
    if not c or c[0] != mt:
        try:
            with open(p, "rb") as f:
                c = (mt, hashlib.sha1(f.read()).hexdigest()[:8])
        except OSError:
            return BUILD
        _ASSET_V[rel] = c
    return c[1]


def assets_stamp():
    """بزرگ‌ترین mtime بین index/mapp و فایل‌های static — کلید بازسازی کش HTML صفحه‌ها"""
    st = []
    for fn in ("index.html", "mapp.html"):
        try:
            st.append(os.path.getmtime(os.path.join(APP_DIR, fn)))
        except OSError:
            pass
    try:
        for fn in os.listdir(os.path.join(APP_DIR, "static")):
            try:
                st.append(os.path.getmtime(os.path.join(APP_DIR, "static", fn)))
            except OSError:
                pass
    except OSError:
        pass
    return max(st) if st else 0.0

FEATURES_ON = {
    "blueprint": True,     # صفحه‌ی «چی می‌خوای بسازی؟» + معمار هوشمند
    "whenthen": True,      # سازنده‌ی «وقتی … آنگاه» در استودیو
    "simulator": True,     # شبیه‌ساز چت (خصوصی و گروه)
    "lists": True,         # ویرایشگر لیست‌ها شبیه اکسل
    "games": True,         # مرکز بازی گروهی
    "doctor": True,        # دکتر ربات
    "growth": True,        # رشد واقعی با لینک دعوت تلگرام
    "agent": True,         # استودیوی عامل هوشمند (دانش + تست)
}


def limits_of(uid):
    """سقف‌های پلن‌محور کاربر: بخش‌های ربات، بلوک‌های مینی‌اپ، جدول‌ها و صفحه‌ها"""
    if uid is None:
        return {k: limit_of("free", k) for k in LIMITS}
    d = db.users.find_one({"_id": uid}, {"plan": 1, "plan_exp": 1}) or {}
    pid = plan_of(d)
    return {k: limit_of(pid, k) for k in LIMITS}


def cut(uid, n):
    """نرخ مصرف توکن بعد از تخفیف اشتراک (هزینه‌ی ۱ توکنی دست نمی‌خوره)"""
    pct = perks_of(uid)["disc"] if uid is not None else 0
    return n if pct <= 0 or n <= 1 else max(1, int(n * (100 - pct) / 100 + 0.5))


AI_MSG_COST = TOKEN_SCALE      # حالت fixed: هزینه‌ی هر «بسته‌ی» پیام هوشمند (هر ai_per پیام = AI_MSG_COST توکن)


def ai_per(uid):
    """حالت fixed: هر چند پیام هوشمند = یک بسته‌ی AI_MSG_COST توکنی (با تخفیف اشتراک بیشتر می‌شه)"""
    return max(1, round(AI_MSGS_PER_TOKEN * 100 / (100 - perks_of(uid)["disc"])))


# ───────────────────────── ایموجی پرمیوم (کتابخونه‌ی هر کاربر) ─────────────────────────
# کاربر ایموجی پرمیوم رو برای ربات مادر می‌فرسته؛ شناسه‌ش اینجا ذخیره می‌شه و تو ادیتور داخل متن و دکمه‌ها قابل انتخابه.
def emoji_sig(eid):
    return hmac.new(SECRET_KEY.encode(), f"emoji:{eid}".encode(), hashlib.sha256).hexdigest()[:24]


def emoji_public(e):
    return {"id": e["eid"], "char": e.get("char") or "⭐", "url": f"/e/{e['eid']}?s={emoji_sig(e['eid'])}" if e.get("thumb") else ""}


def emoji_list(uid):
    return [emoji_public(e) for e in db.emojis.find({"owner": uid}).sort("t", -1)]


def emoji_info(ids):
    """{شناسه: (ایموجی معمولی، فایل پیش‌نمایش)} از تلگرام"""
    out, ids = {}, [str(i) for i in ids]
    for i in range(0, len(ids), 50):
        r = tg(MOTHER_TOKEN, "getCustomEmojiStickers", custom_emoji_ids=ids[i:i + 50])
        for st in r.get("result") or []:
            th = (st.get("thumbnail") or {}).get("file_id") or ("" if st.get("is_animated") or st.get("is_video") else st.get("file_id", ""))
            out[str(st.get("custom_emoji_id"))] = (st.get("emoji") or "⭐", th)
    return out


def emoji_add(uid, items):
    """items = [(emoji_id, ایموجی معمولی)]؛ خروجی: (چندتا اضافه شد، چندتا جا نشد)"""
    cap = perks_of(uid)["emoji"]
    have = db.emojis.count_documents({"owner": uid})
    new = [(str(e), c) for e, c in items if str(e).isdigit() and not db.emojis.find_one({"_id": f"{uid}:{e}"})]
    seen, uniq = set(), []
    for e, c in new:
        if e not in seen:
            seen.add(e); uniq.append((e, c))
    take, full = uniq[:max(0, cap - have)], max(0, len(uniq) - max(0, cap - have))
    info = emoji_info([e for e, _ in take]) if take else {}
    for e, c in take:
        ch, th = info.get(e, (c or "⭐", ""))
        db.emojis.insert_one({"_id": f"{uid}:{e}", "owner": uid, "eid": e, "char": (c or ch)[:8], "thumb": th, "t": now()})
    return len(take), full


_EMJ_IMG, _EMJ_LOCK = {}, threading.Lock()


def emoji_image(eid):
    """(بایت‌ها، نوع فایل) پیش‌نمایش کوچک ایموجی؛ از تلگرام گرفته و در حافظه کش می‌شه"""
    with _EMJ_LOCK:
        if eid in _EMJ_IMG:
            return _EMJ_IMG[eid]
    e = db.emojis.find_one({"eid": eid, "thumb": {"$nin": ["", None]}})
    if not e:
        return None
    path = (tg(MOTHER_TOKEN, "getFile", file_id=e["thumb"]).get("result") or {}).get("file_path")
    if not path:
        return None
    try:
        r = requests.get(f"https://api.telegram.org/file/bot{MOTHER_TOKEN}/{path}", timeout=15)
    except Exception:
        return None
    if r.status_code != 200 or len(r.content) > 400_000:
        return None
    res = (r.content, "image/webp" if path.endswith(".webp") else "image/png" if path.endswith(".png") else "image/jpeg")
    with _EMJ_LOCK:
        if len(_EMJ_IMG) > 300:
            _EMJ_IMG.clear()
        _EMJ_IMG[eid] = res
    return res


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
        "apps": db.apps.count_documents({"owner": uid, "pub": {"$exists": True, "$ne": None}}),
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
                      "steps": [{"label": s["label"], "hint": s["hint"], "goal": s["goal"], "value": s["value"], "tokens": s["tokens"],
                                 "done": s["done"], "ready": s["ready"]} for s in steps],
                      "value": v, "goal": cur["goal"], "tokens": cur["tokens"],
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
        tg(MOTHER_TOKEN, "sendMessage", chat_id=owner, reply_markup={"inline_keyboard": [[{"text": "شارژ توکن", "web_app": {"url": APP_URL}}]]},
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


# ایموجی پرمیوم در متن (<tg-emoji>) و ظاهر دکمه‌ها (style / icon_custom_emoji_id)
TGE_RE = re.compile(r"<tg-emoji\s+emoji-id=[\"']?\d+[\"']?\s*>(.*?)</tg-emoji>", re.S)


def strip_fx_text(t):
    """تگ ایموجی پرمیوم رو برمی‌داره و همون ایموجی معمولی داخلش می‌مونه"""
    return TGE_RE.sub(r"\1", t) if isinstance(t, str) and "<tg-emoji" in t else t


def strip_fx_markup(mk, style=False):
    """آیکن ایموجیِ دکمه‌ها (و اگه style=True رنگشون) رو از کیبورد برمی‌داره"""
    if not isinstance(mk, dict):
        return mk
    out = {}
    for k, v in mk.items():
        if k in ("inline_keyboard", "keyboard"):
            out[k] = [[{a: b for a, b in btn.items() if a != "icon_custom_emoji_id" and not (style and a == "style")}
                       if isinstance(btn, dict) else btn for btn in row] for row in v]
        else:
            out[k] = v
    return out


def fx_in(data):
    """توی این درخواست ایموجی پرمیوم یا آیکن دکمه هست؟"""
    for k in ("text", "caption"):
        if "<tg-emoji" in str(data.get(k) or ""):
            return True
    mk = data.get("reply_markup")
    if isinstance(mk, dict):
        for row in (mk.get("inline_keyboard") or mk.get("keyboard") or []):
            if any(isinstance(b, dict) and "icon_custom_emoji_id" in b for b in row):
                return True
    return False


def strip_fx(data):
    d = dict(data)
    for k in ("text", "caption"):
        if k in d:
            d[k] = strip_fx_text(d[k])
    if "reply_markup" in d:
        d["reply_markup"] = strip_fx_markup(d["reply_markup"])
    return d


def tg_html(token, method, **data):
    """ارسال/ویرایش با parse_mode=HTML (بولد، لینک و…)؛ اگه تلگرام تگ‌ها رو نپذیرفت همون متن بدون تگ می‌ره.
    اگه ایموجی پرمیوم/آیکن دکمه پذیرفته نشد (مثلاً صاحب ربات پرمیوم تلگرام نیست) بدون اونا دوباره می‌فرسته"""
    key = "caption" if "caption" in data else "text"
    orig = dict(data)
    r = tg(token, method, parse_mode="HTML", **data)
    if not r.get("ok") and fx_in(orig) and "not modified" not in str(r.get("description", "")) and not is_block_err(r):
        data = strip_fx(orig)
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
        if fx_in({"caption": caption, "reply_markup": markup}):
            return tg_media(token, bot_id, chat_id, mid, strip_fx_text(caption), strip_fx_markup(markup), parse)
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
        if fx_in({"caption": caption, "reply_markup": markup}):
            return tg_media(token, bot_id, chat_id, mid, strip_fx_text(caption), strip_fx_markup(markup), parse)
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
    tg(MOTHER_TOKEN, "setChatMenuButton", menu_button={"type": "commands"})     # دکمه‌ی کنار کادر چت = منوی دستورها (نه مینی‌اپ)
    tg(MOTHER_TOKEN, "setMyCommands", commands=[{"command": "start", "description": "شروع"}])
    log.info("mother webhook: %s (@%s)", r, MOTHER_USERNAME)
