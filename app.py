# -*- coding: utf-8 -*-
"""
AI BotMaker — رباتساز هوشمند ساده
Stack (مثل GramSaz): Flask + MongoDB(pymongo) + مینی‌اپ تک‌فایلی
- ربات مادر: فقط /start و دکمه‌ی باز کردن مینی‌اپ
- مینی‌اپ: کاربر توضیح می‌ده چه رباتی می‌خواد، هوش مصنوعی «کانفیگ JSON» می‌سازه
- موتور ثابت و امن (execute_node) کانفیگ رو اجرا می‌کنه؛ هیچ کد تولیدشده‌ای اجرا نمی‌شه
"""
import os, re, json, time, hmac, hashlib, base64, secrets, logging, math, random, uuid, mimetypes
from urllib.parse import parse_qsl
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from flask import Flask, request, jsonify, send_from_directory
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from bson.errors import InvalidId
from cryptography.fernet import Fernet

# ───────────────────────── تنظیمات (Environment) ─────────────────────────
MOTHER_TOKEN = os.environ["MOTHER_TOKEN"]            # توکن ربات مادر
MONGO_URI    = os.environ.get("MONGO_URI", "").strip()  # خالی = حافظه‌ی موقت (ذخیره نمی‌شه)
BASE_URL     = os.environ["BASE_URL"].rstrip("/")    # مثلا https://yourapp.onrender.com
AI_BASE_URL  = re.sub(r"/chat/completions/?$", "", os.environ["AI_BASE_URL"].strip().rstrip("/"))  # با یا بدون /chat/completions کار می‌کنه
AI_API_KEY   = os.environ["AI_API_KEY"]
AI_MODEL     = os.environ["AI_MODEL"]
SECRET_KEY   = os.environ.get("SECRET_KEY", MOTHER_TOKEN)  # برای رمزنگاری توکن رباتا
DAILY_LIMIT  = int(os.environ.get("DAILY_LIMIT", "5"))     # تعداد ساخت/ارتقا در روز برای هر کاربر
MAX_BOTS     = int(os.environ.get("MAX_BOTS", "3"))        # سقف ربات هر کاربر
AI_MAX_TOKENS = int(os.environ.get("AI_MAX_TOKENS", "6000"))   # سقف طول خروجی هوش مصنوعی
DEBUG        = os.environ.get("DEBUG", "") == "1"   # علت دقیق خطا رو توی مینی‌اپ نشون می‌ده
MAX_PROMPT   = 2000
MAX_VERSIONS = 8
MAX_NODES    = 40

# ── Token economy (ابر رباتساز: هزینه‌ی توکنی هوش مصنوعی) ──
NEW_USER_TOKENS = int(os.environ.get("NEW_USER_TOKENS", "40"))
GENERATE_COST   = int(os.environ.get("GENERATE_COST", "12"))
UPGRADE_COST    = int(os.environ.get("UPGRADE_COST", "8"))
REFERRAL_BONUS  = int(os.environ.get("REFERRAL_BONUS", "25"))
DAILY_BONUS     = int(os.environ.get("DAILY_BONUS", "10"))
MOTHER_USERNAME = os.environ.get("MOTHER_USERNAME", "").strip().lstrip("@")
ADMIN_IDS       = {int(x) for x in os.environ.get("ADMIN_IDS", "").replace(",", " ").split() if x.strip().lstrip("-").isdigit()}

# ── Media (آپلود عکس/ویدیو/صوت/سند برای بخش‌های ربات) ──
MEDIA_DIR = Path(os.environ.get("MEDIA_DIR", str(Path(__file__).parent / "media")))
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
MAX_MEDIA_MB = int(os.environ.get("MAX_MEDIA_MB", "20"))
MAX_MEDIA_BYTES = MAX_MEDIA_MB * 1024 * 1024
ALLOWED_EXT = {"jpg","jpeg","png","webp","gif","mp4","mov","m4a","mp3","ogg","oga","wav","pdf","zip","txt"}
MEDIA_KINDS = ("photo", "video", "animation", "voice", "audio", "document")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aibot")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_MEDIA_BYTES + 1024 * 1024
if MONGO_URI:
    db = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000).get_database("aibot")
else:
    import mongomock
    db = mongomock.MongoClient().get_database("aibot")
    log.warning("MONGO_URI تنظیم نشده؛ از حافظه‌ی موقت استفاده می‌شه و با هر ری‌استارت همه‌چی پاک می‌شه")
db.bots.create_index("owner")
db.bots.create_index("token_hash", unique=True, sparse=True)

fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest()))
MOTHER_SECRET = hashlib.sha256(("mother" + SECRET_KEY).encode()).hexdigest()[:32]


# ───────────────────────── ابزارهای تلگرام ─────────────────────────
def tg(token, method, **data):
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=data, timeout=15)
        return r.json()
    except Exception as e:
        log.warning("tg %s failed: %s", method, e)
        return {"ok": False, "description": str(e)}


def now():
    return datetime.now(timezone.utc)


def enc(s):  return fernet.encrypt(s.encode()).decode()
def dec(s):  return fernet.decrypt(s.encode()).decode()
def thash(t): return hashlib.sha256(t.encode()).hexdigest()


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
        return json.loads(pairs["user"])
    except Exception:
        return None


def auth():
    u = verify_init_data(request.headers.get("X-Init-Data", ""))
    return u["id"] if u else None


def get_bot(bot_id, owner):
    try:
        return db.bots.find_one({"_id": ObjectId(bot_id), "owner": owner})
    except InvalidId:
        return None


def public(b):
    return {
        "id": str(b["_id"]), "name": b.get("name", ""), "active": b.get("active", False),
        "username": b.get("username"), "config": b.get("config"),
        "versions": len(b.get("versions", [])), "updated": b["updated"].isoformat(),
        "thinking": b.get("thinking", ""),
    }


# ── Token economy ──
def get_user(uid):
    u = db.users.find_one({"_id": uid})
    if not u:
        u = {"_id": uid, "tokens": NEW_USER_TOKENS, "created": now(),
             "total_earned": NEW_USER_TOKENS, "total_spent": 0,
             "referred_by": None, "referrals": 0, "daily": ""}
        db.users.insert_one(u)
    return u


def add_tokens(uid, amount, reason=""):
    get_user(uid)
    db.users.update_one({"_id": uid}, {"$inc": {"tokens": amount,
        "total_earned": amount if amount > 0 else 0, "total_spent": -amount if amount < 0 else 0}})
    try:
        db.ledger.insert_one({"uid": uid, "amount": amount, "reason": reason, "t": now()})
    except Exception:
        pass


def spend_tokens(uid, amount, reason=""):
    r = db.users.find_one_and_update({"_id": uid, "tokens": {"$gte": amount}},
                                     {"$inc": {"tokens": -amount, "total_spent": amount}})
    if r is None:
        get_user(uid)
        r = db.users.find_one_and_update({"_id": uid, "tokens": {"$gte": amount}},
                                         {"$inc": {"tokens": -amount, "total_spent": amount}})
        return r is not None
    try:
        db.ledger.insert_one({"uid": uid, "amount": -amount, "reason": reason, "t": now()})
    except Exception:
        pass
    return True


def referral_link(uid):
    if MOTHER_USERNAME:
        return f"https://t.me/{MOTHER_USERNAME}?start=r_{uid}"
    return f"r_{uid}"


def apply_referral(new_uid, code):
    try:
        ref = int(str(code).strip().lstrip("r_").strip())
    except ValueError:
        return None
    if ref == new_uid:
        return None
    me = get_user(new_uid)
    if me.get("referred_by"):
        return "already"
    if not db.users.find_one({"_id": ref}):
        db.users.insert_one({"_id": ref, "tokens": NEW_USER_TOKENS, "created": now(),
                             "total_earned": NEW_USER_TOKENS, "total_spent": 0,
                             "referred_by": None, "referrals": 0, "daily": ""})
    db.users.update_one({"_id": new_uid}, {"$set": {"referred_by": ref}})
    db.users.update_one({"_id": ref}, {"$inc": {"referrals": 1}})
    add_tokens(ref, REFERRAL_BONUS, f"referral:{new_uid}")
    add_tokens(new_uid, REFERRAL_BONUS, f"referred_by:{ref}")
    return "ok"


def level_of(bots_count, spent):
    if bots_count >= 5 or spent >= 200:
        return "Master"
    if bots_count >= 3 or spent >= 100:
        return "Pro"
    if bots_count >= 1 or spent >= 20:
        return "Maker"
    return "Starter"


def sync_commands(bot, cfg):
    """منوی دستورهای ربات فرزند رو با کانفیگ هم‌گام می‌کنه (فقط اگه فعاله)"""
    if bot.get("active") and bot.get("token_enc"):
        tg(dec(bot["token_enc"]), "setMyCommands", commands=[{"command": "start", "description": "شروع"}] + [
            {"command": c, "description": c} for c in cfg["commands"]])


# ───────────────────────── سهمیه ─────────────────────────
def quota_key(uid):
    return f"{uid}:{now():%Y-%m-%d}"


def quota_take(uid):
    try:
        db.usage.find_one_and_update(
            {"_id": quota_key(uid), "n": {"$lt": DAILY_LIMIT}},
            {"$inc": {"n": 1}}, upsert=True)
        return True
    except DuplicateKeyError:
        return False


def quota_refund(uid):
    db.usage.update_one({"_id": quota_key(uid)}, {"$inc": {"n": -1}})


def quota_left(uid):
    d = db.usage.find_one({"_id": quota_key(uid)})
    return max(0, DAILY_LIMIT - (d["n"] if d else 0))


# ───────────────────────── هوش مصنوعی ─────────────────────────
SYSTEM_PROMPT = """You design Telegram bots as a JSON config that a fixed, safe engine executes. You think like a senior product designer AND a bot-logic engineer, not a form-filler.

LANGUAGE RULE (strict, highest priority): the request states the OUTPUT LANGUAGE. Write "thinking" and EVERY user-facing text (node texts, button labels, bot name) in that language. If it says Persian, write natural Persian (فارسی) and NEVER English, even though this prompt, the JSON keys, node_ids and variable names are English.

Output ONLY one valid JSON object, no markdown fences, no comments. Top-level shape:
{
 "thinking": "...",
 "config": { ...bot config as described below... }
}

"thinking" (string, 2-5 short sentences, in the OUTPUT LANGUAGE, natural first-person tone, like a sharp colleague briefly narrating their plan, not a formal report):
- Say what you understood the user wants.
- Name the key sections/flows you decided the bot needs and briefly why.
- If you used variables/conditions, say in one short sentence what they do (e.g. "امتیاز هر کاربر جداگونه شمرده می‌شه").
- If you made a judgment call, filled a gap, or used a placeholder (price, phone, channel id, link), say so and tell them they can edit it with the manual edit button.
- If this is an update to an existing bot, mention only what you're changing and why, not the whole bot again.
- No headers, no bullet points, no markdown, just natural flowing sentences.

"config" schema:
{
 "name": "short bot name",
 "start": "<node_id shown on /start>",
 "fallback": "<node_id shown for unknown messages>",
 "commands": {"help": "<node_id>"},
 "join": {"channels": ["channel_username"], "text": "message asking to join"},      (optional)
 "vars": {"coins": "0", "city": ""},                                                 (optional, declare EVERY custom variable with its default value)
 "nodes": {
   "<node_id>": {
     "title": "short human label of this section, max 30 chars, OUTPUT LANGUAGE",
     "text": "message text (may contain {placeholders}, see VARIABLES)",
     "photo": "https://direct-image-link",                                          (optional)
     "buttons": [[ {"text": "label", "goto": "<node_id>"},
                   {"text": "label", "url": "https://..."},
                   {"text": "label", "alert": "popup text shown when tapped"},
                   {"text": "label", "copy": "text copied to clipboard when tapped"} ]],
     "ask": false,
     "kb": "reply",                                                                 (optional)
     "fields": ["Question 1?", "Question 2?"],                                       (optional, multi-step form)
     "save": ["city", ""],                                                           (optional, see FORMS)
     "types": ["text", "number"],                                                    (optional, see FORMS)
     "silent": false,                                                                (optional, see FORMS)
     "done": "message shown after the user finished ask/form",                      (optional)
     "next": "<node_id shown after finishing>",                                      (optional, default start)
     "do": [ ...actions... ],                                                        (optional, see LOGIC)
     "route": [ {"when": <cond>, "goto": "<node_id>"} ],                             (optional, see LOGIC)
     "alt": [ {"when": <cond>, "text": "..."} ]                                      (optional, see LOGIC)
   }
 }
}

BASIC ENGINE FEATURES
- Buttons: goto a section, open a link, show a popup message (alert), copy text (e.g. card number, promo code).
- "ask": true = the user's next message (any type) is forwarded to the bot owner. Good for support/feedback.
- "fields": a multi-step form. The bot asks each question in order and sends all answers to the owner as one summary. Use for orders, registration, applications, surveys. Node "text" is the intro, fields are the questions. Use "done" for the thank-you message.
- "join": force membership: before using the bot the user must be a member of these public channels (usernames without @). Only add it if the user asks for forced/mandatory join. In "thinking" remind that the bot must be admin in that channel.
- "kb": "reply" = show this node's buttons as a keyboard under the chat input box instead of glass buttons under the message. Omit it (default) for normal inline buttons. Use it only if the user asks for a keyboard under the chat / a main-menu keyboard. Never use it on nodes with "ask" or "fields". Link/popup/copy buttons still work inside it.
- "photo": only if the user gave an image link. Never invent image URLs.
- "media" (NEW, preferred over photo): {"kind": "photo|video|animation|voice|audio|document", "url": "https://..."} — ONLY include if the user gave a media link (the Studio may pass an uploaded /media/ file URL in the request). Never invent media URLs. photo/video/animation show with caption, voice/audio/document are sent as files.

VARIABLES (this is what makes a bot feel professional)
- Custom variables are stored PER USER (each Telegram user has their own values). Name: lowercase english letters/digits/underscore, starts with a letter, max 20 chars, max 20 variables per bot. Declare each one in config.vars with a default string ("0" for counters, "" for text). Values are strings; math and numeric comparison work when they look like numbers.
- Use {var} in node texts, button labels, alert/copy text, form questions, "done", notify texts and condition values. {var|fallback} prints fallback when the value is empty, e.g. {city|ثبت نشده}. Every variable you put in a {placeholder} MUST be declared in config.vars (built-ins excepted).
- Built-in read-only variables (always available in texts AND conditions):
  {name} first name (falls back to "دوست من"), {first_name}, {last_name}, {full_name}, {username} (with @, empty if none), {id} Telegram user id, {lang} Telegram language code like fa / en, {premium} "1" if the user has Telegram Premium else "0", {is_owner} "1" if the user is the bot owner else "0", {bot_name}, {bot_username}, {text} the last text message the user sent, {param} the payload of /start (deep link t.me/bot?start=xxx), {visits} how many times this user pressed /start (1 on the first time), {date} today's Jalali date like 1405/07/11, {time} HH:MM Tehran time, {hour} 0-23 Tehran, {weekday} Persian weekday name.

CONDITIONS ("cond" object)
- {"var": "coins", "op": ">=", "value": "10"}. op is one of: == != > >= < <= contains empty filled ("empty"/"filled" take no value). "var" is a custom or built-in variable. "value" may contain {placeholders}. Numbers compare numerically, text compares case-insensitively.
- Combine with {"all": [cond, cond]} (AND), {"any": [cond, cond]} (OR), {"not": cond}. Max 3 levels deep.

ACTIONS ("action" object, max 6 per list)
- {"op": "set", "var": "city", "value": "تهران"}            store a value (value may use {placeholders})
- {"op": "add", "var": "coins", "value": "5"}               add a number; negative to subtract ("-3"); default 1
- {"op": "clear", "var": "city"}                            back to the default
- {"op": "random", "var": "dice", "value": "1-6"}           random whole number in a range
- {"op": "notify", "value": "text"}                         sends a message to the bot owner (may use {placeholders}; the user's name and id are appended automatically)

WHERE LOGIC GOES
- node "do": [actions] runs every time a user enters the node, before anything is shown.
- node "route": [{"when": cond, "goto": "<node_id>"}] (max 5). After "do", the FIRST rule whose condition is true sends the user to that node instead (like a switch). Use for gates, level-ups, opening hours, owner-only menus, first visit vs returning user. Because the node's own text is then skipped, still write a sensible text. Chains are followed up to 5 hops; never create loops.
- node "alt": [{"when": cond, "text": "..."}] (max 4). The first true condition replaces the node's text (buttons stay). Use for personalised messages ("you have {coins} coins").
- button "when": cond. The button is only shown to users for whom it is true (admin button, premium-only, hide "buy" when coins are not enough).
- button "do": [actions]. Only on goto and alert buttons. Runs when the button is tapped, before the goto/alert. Alert text may use {placeholders} and is evaluated AFTER the actions, so a "💰 my balance" alert shows fresh numbers.
- FORMS: "save": ["city", ""] has the same length as "fields" and stores each answer in that variable ("" = don't store). "types": ["text","number","phone","email"] (same length) validates each answer; the engine re-asks until valid and normalises digits to english. "silent": true = don't send the finished form to the owner (default: it is sent). Later questions and texts can use earlier answers, e.g. "{city} درسته؟".

WHEN TO USE LOGIC
- Use variables/conditions when they make the bot genuinely better: points/coins/loyalty, quizzes and scoring, bots that remember answers and reuse them ("{city}" in later messages), personalised greetings (first visit vs returning via {visits}), opening hours via {hour}/{weekday}, an owner-only admin menu via {is_owner}, language-aware replies via {lang}, referral/campaign tracking via {param}, premium-only perks via {premium}.
- Do NOT add logic when a plain menu is enough. A simple request deserves a simple, clean bot.
- Small examples of the constructs (not a full bot):
  "vars": {"score": "0"}
  {"text": "تهران", "goto": "q2", "do": [{"op": "add", "var": "score", "value": "1"}]}
  {"title": "نتیجه", "text": "تموم شد!", "route": [{"when": {"var": "score", "op": ">=", "value": "3"}, "goto": "win"}]}
  {"text": "🛠 پنل مدیر", "goto": "admin", "when": {"var": "is_owner", "op": "==", "value": "1"}}
  {"text": "سلام {name}", "alt": [{"when": {"var": "visits", "op": ">", "value": "1"}, "text": "خوش برگشتی {name} 👋"}]}

ENGINE LIMITS (be honest about them in "thinking" and build the closest working approximation)
- CANNOT do: payments, real inventory/databases, external APIs, scheduled messages, sending files, data shared BETWEEN users (no global counters, leaderboards, or real referral counting; variables are per user).
- Example approximation: an order form whose answers are sent to the owner instead of online payment.

Design rules:
- Think before you structure: identify the bot's real purpose, the natural user journeys, and the minimum set of nodes that cover them well. Don't pad with filler, but don't skip an obviously needed part (a shop bot needs a way to order, a business bot needs contact/support, a content bot usually needs a channel link).
- node_id: lowercase english letters, digits, underscore. Max 30 nodes, max 3 buttons per row, max 6 rows per node.
- A button has exactly one of: "goto" (an existing node_id), "url" (https only), "alert", "copy".
- Channel/group join button: {"text": "📢 عضویت در کانال", "url": "https://t.me/<username>"} (username without @). Use the username the user gave. If they gave none, use https://t.me/your_channel and say in "thinking" that the real channel id must be set via manual edit.
- Always give every node a short "title". Prefer a form ("fields") over a single "ask" when you need several pieces of info. Give ask/form nodes a cancel/home button too.
- Every "goto", "start", "fallback", "next", route target and command target MUST exist in nodes. Every node must be reachable from start; no dead ends: every non-start node has a back/home button (or a "next"/"route").
- Button labels short (max ~22 chars). Put at most 2 buttons in a row when labels are long.
- Never invent real-world facts (prices, phone numbers, addresses, links). Use obvious placeholders such as [قیمت] or [شماره تماس] and mention it in "thinking".
- Write all user-facing text in the OUTPUT LANGUAGE. Use emojis moderately.
- When an existing config is given, apply the user's change precisely and return the FULL updated config. Keep every untouched node, text, button, variable and rule exactly as it was (the user may have edited them by hand).
- Plain text only, no Markdown/HTML formatting characters in node texts."""


ID_RE = re.compile(r"^[a-z0-9_]{1,30}$")
CMD_RE = re.compile(r"^[a-z0-9_]{1,30}$")
TG_NAME_RE = re.compile(r"^@?[A-Za-z][A-Za-z0-9_]{4,31}$")

# ───── متغیرها، شرط‌ها و اکشن‌ها ─────
VAR_RE = re.compile(r"^[a-z][a-z0-9_]{0,19}$")
PH_RE = re.compile(r"\{([a-z][a-z0-9_]{0,19})(?:\|([^{}]{0,60}))?\}")
MAX_VARS = 20
MAX_HOPS = 5
# متغیرهای آماده‌ی تلگرام (فقط‌خواندنی)
BUILTINS = ("name", "first_name", "last_name", "full_name", "username", "id", "lang", "premium", "is_owner",
            "bot_name", "bot_username", "text", "param", "visits", "date", "time", "hour", "weekday")
OPS = ("==", "!=", ">", ">=", "<", "<=", "contains", "empty", "filled")
OP_ALIASES = {"=": "==", "eq": "==", "ne": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
ACT_OPS = ("set", "add", "clear", "random", "notify")
F_TYPES = ("text", "number", "phone", "email")
_DIG = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def norm_url(v):
    """@channel / t.me/x / https://... → https URL معتبر (یا None)"""
    v = str(v or "").strip()
    if TG_NAME_RE.match(v):
        return "https://t.me/" + v.lstrip("@")
    if re.match(r"^(t\.me|telegram\.me)/", v, re.I):
        v = "https://" + v
    if v.startswith("https://") and len(v) > 12 and not re.search(r"\s", v):
        return v[:500]
    # uploaded files served by the Studio itself
    if v.startswith("/media/") and len(v) < 200 and not re.search(r"\s", v):
        return (BASE_URL + v)[:1000]
    return None


def to_num(s):
    """رشته → عدد (ارقام فارسی/عربی هم قبول)؛ نامعتبر = None"""
    try:
        x = float(str(s).translate(_DIG).replace(",", "").replace("٫", ".").strip())
    except (ValueError, TypeError):
        return None
    return x if math.isfinite(x) else None


def fmt_num(x):
    x = max(-1e12, min(1e12, x))
    return str(int(x)) if x == int(x) else ("%.6f" % x).rstrip("0").rstrip(".")


def clean_cond(c, used, nums, bad, depth=0):
    """شرط رو پاک‌سازی می‌کنه؛ نامعتبر = None"""
    if not isinstance(c, dict) or depth > 3:
        bad("یکی از شرط‌ها ساختار معتبری نداره")
        return None
    for key in ("all", "any"):
        if isinstance(c.get(key), list):
            subs = [x for x in (clean_cond(s, used, nums, bad, depth + 1) for s in c[key][:6]) if x]
            return {key: subs} if subs else None
    if "not" in c:
        s = clean_cond(c["not"], used, nums, bad, depth + 1)
        return {"not": s} if s else None
    name = str(c.get("var") or "").strip().lower()
    op = str(c.get("op") or "==").strip()
    op = OP_ALIASES.get(op, op)
    if not (name in BUILTINS or VAR_RE.match(name)):
        bad(f"نام متغیر «{name}» در شرط معتبر نیست (حروف انگلیسی کوچک، عدد و _)")
        return None
    if op not in OPS:
        bad(f"عملگر شرط «{op}» معتبر نیست")
        return None
    if name not in BUILTINS:
        used.add(name)
        if op in (">", ">=", "<", "<="):
            nums.add(name)
    out = {"var": name, "op": op}
    if op not in ("empty", "filled"):
        out["value"] = str(c.get("value", ""))[:100]
    return out


def clean_actions(lst, used, nums, bad):
    out = []
    for a in (lst if isinstance(lst, list) else [])[:6]:
        if not isinstance(a, dict):
            continue
        op = str(a.get("op") or "").strip().lower()
        if op not in ACT_OPS:
            bad(f"نوع اکشن «{op}» معتبر نیست")
            continue
        if op == "notify":
            v = str(a.get("value") or "").strip()[:500]
            if v:
                out.append({"op": "notify", "value": v})
            else:
                bad("متن اعلان (notify) خالیه")
            continue
        name = str(a.get("var") or "").strip().lower()
        if not VAR_RE.match(name) or name in BUILTINS:
            bad(f"نام متغیر «{name}» برای اکشن معتبر نیست (حروف انگلیسی کوچک، عدد و _ و نباید اسم متغیرهای آماده باشه)")
            continue
        item = {"op": op, "var": name}
        if op != "clear":
            v = str(a.get("value", "")).strip()[:100]
            if op == "add":
                if v == "":
                    v = "1"
                elif to_num(v) is None and not PH_RE.search(v):
                    bad(f"مقدار اکشن جمع برای «{name}» باید عدد باشه")
                    continue
            elif op == "random":
                m = re.fullmatch(r"(\d{1,9})\s*-\s*(\d{1,9})", v.translate(_DIG))
                if not m or int(m.group(1)) > int(m.group(2)):
                    bad(f"بازه‌ی عدد تصادفی «{name}» باید مثل 1-6 باشه")
                    continue
                v = f"{int(m.group(1))}-{int(m.group(2))}"
            item["value"] = v
        used.add(name)
        if op in ("add", "random"):
            nums.add(name)
        out.append(item)
    return out


def clean_media(m, bad):
    """مدیای بخش: {kind, url} — نامعتبر = None"""
    if not isinstance(m, dict):
        return None
    kind = str(m.get("kind") or "photo").strip().lower()
    if kind not in MEDIA_KINDS:
        kind = "photo"
    u = norm_url(m.get("url"))
    if not u:
        bad("آدرس مدیای بخش معتبر نیست (باید لینک https یا فایل آپلودشده باشه)")
        return None
    return {"kind": kind, "url": u}


def sanitize(cfg, strict=False):
    """strict=True (ویرایش دستی): خطا می‌ده.  strict=False (خروجی AI): تا جای ممکن خودش درست می‌کنه."""
    if not isinstance(cfg, dict) or not isinstance(cfg.get("nodes"), dict):
        raise ValueError("ساختار خروجی معتبر نیست")
    nodes_in = cfg["nodes"]
    if not (1 <= len(nodes_in) <= MAX_NODES):
        raise ValueError(f"تعداد بخش‌ها باید بین ۱ تا {MAX_NODES} باشه")

    def bad(msg):
        if strict:
            raise ValueError(msg)

    used, nums = set(), set()      # متغیرهایی که جایی استفاده شدن / مقدار عددی دارن
    valid = {}
    for nid, n in nodes_in.items():
        nid = str(nid)
        if not ID_RE.match(nid) or not isinstance(n, dict):
            bad("شناسه‌ی یکی از بخش‌ها نامعتبره"); continue
        text = str(n.get("text", "")).strip()[:3500]
        if not text:
            bad(f"بخش «{nid}» متن نداره"); continue
        valid[nid] = (n, text)
    if not valid:
        raise ValueError("هیچ بخش معتبری وجود نداره")

    nodes = {}
    for nid, (n, text) in valid.items():
        rows = []
        for row in (n.get("buttons") or [])[:6]:
            r = []
            for b in (row if isinstance(row, list) else [row])[:3]:
                if not isinstance(b, dict):
                    continue
                label = str(b.get("text", "")).strip()[:40]
                if not label:
                    bad(f"بخش «{nid}» یه دکمه‌ی بدون متن داره"); continue
                it = None
                g = str(b.get("goto") or "")
                if g:
                    if g in valid:
                        it = {"text": label, "goto": g}
                    else:
                        bad(f"دکمه‌ی «{label}» به بخش ناموجود وصله")
                elif str(b.get("alert") or "").strip():
                    it = {"text": label, "alert": str(b["alert"]).strip()[:200]}
                elif str(b.get("copy") or "").strip():
                    it = {"text": label, "copy": str(b["copy"]).strip()[:256]}
                else:
                    u = norm_url(b.get("url"))
                    if u:
                        it = {"text": label, "url": u}
                    else:
                        bad(f"لینک/آیدی دکمه‌ی «{label}» معتبر نیست (باید https:// یا @آیدی باشه)")
                if it is None:
                    continue
                if b.get("when"):
                    w = clean_cond(b["when"], used, nums, bad)
                    if w:
                        it["when"] = w
                if b.get("do"):
                    if "goto" in it or "alert" in it:
                        acts = clean_actions(b["do"], used, nums, bad)
                        if acts:
                            it["do"] = acts
                    else:
                        bad(f"اکشن فقط روی دکمه‌های «رفتن به بخش» و «پیام پاپ‌آپ» کار می‌کنه (دکمه‌ی «{label}»)")
                r.append(it)
            if r:
                rows.append(r)
        node = {"text": text, "buttons": rows, "ask": bool(n.get("ask"))}
        title = str(n.get("title") or "").strip()[:30]
        if title:
            node["title"] = title
        # مدیا (جدید) + سازگاری با photo قدیمی
        m = clean_media(n.get("media"), bad) if n.get("media") else None
        if not m:
            ph = str(n.get("photo") or "").strip()
            if ph:
                u = norm_url(ph)
                if u:
                    m = {"kind": "photo", "url": u}
                else:
                    bad(f"آدرس عکس بخش «{nid}» معتبر نیست (باید لینک مستقیم https باشه)")
        if m:
            node["media"] = m
        if n.get("photo") and not m:
            pass  # خطاش بالا ثبت شد

        # فرم: سؤال‌ها + ذخیره در متغیر + نوع پاسخ
        fl_raw = n.get("fields") if isinstance(n.get("fields"), list) else []
        sv_raw = n.get("save") if isinstance(n.get("save"), list) else []
        ty_raw = n.get("types") if isinstance(n.get("types"), list) else []
        qs, svs, tys = [], [], []
        for i, f in enumerate(fl_raw):
            q = str(f).strip()[:200]
            if not q or len(qs) >= 6:
                continue
            v = str(sv_raw[i]).strip().lower() if i < len(sv_raw) and sv_raw[i] else ""
            if v:
                if VAR_RE.match(v) and v not in BUILTINS:
                    used.add(v)
                else:
                    bad(f"نام متغیر «{v}» برای ذخیره‌ی پاسخ معتبر نیست"); v = ""
            t = str(ty_raw[i]).strip().lower() if i < len(ty_raw) else "text"
            if t not in F_TYPES:
                t = "text"
            if t == "number" and v:
                nums.add(v)
            qs.append(q); svs.append(v); tys.append(t)
        if qs:
            node["fields"], node["ask"] = qs, False
            if any(svs):
                node["save"] = svs
            if any(t != "text" for t in tys):
                node["types"] = tys
            if n.get("silent"):
                node["silent"] = True
        if n.get("kb") == "reply" and rows and not node.get("fields") and not node["ask"]:
            node["kb"] = "reply"          # کیبورد زیر صفحه‌ی چت (فقط برای بخش‌های بدون ask/form)
        done = str(n.get("done") or "").strip()[:500]
        if done:
            node["done"] = done
        nxt = str(n.get("next") or "")
        if nxt:
            if nxt in valid:
                node["next"] = nxt
            else:
                bad(f"بخش بعدیِ «{nid}» وجود نداره")

        # منطق: اکشن‌ها، هدایت شرطی، متن جایگزین
        acts = clean_actions(n.get("do"), used, nums, bad)
        if acts:
            node["do"] = acts
        route = []
        for rule in (n.get("route") if isinstance(n.get("route"), list) else [])[:5]:
            if not isinstance(rule, dict):
                continue
            w, g = clean_cond(rule.get("when"), used, nums, bad), str(rule.get("goto") or "")
            if w and g in valid:
                route.append({"when": w, "goto": g})
            else:
                bad(f"یکی از قانون‌های هدایت شرطیِ بخش «{nid}» کامل نیست")
        if route:
            node["route"] = route
        alt = []
        for rule in (n.get("alt") if isinstance(n.get("alt"), list) else [])[:4]:
            if not isinstance(rule, dict):
                continue
            w, t = clean_cond(rule.get("when"), used, nums, bad), str(rule.get("text") or "").strip()[:3500]
            if w and t:
                alt.append({"when": w, "text": t})
            else:
                bad(f"یکی از متن‌های جایگزینِ بخش «{nid}» کامل نیست")
        if alt:
            node["alt"] = alt
        nodes[nid] = node

    start = str(cfg.get("start") or "")
    if start not in nodes:
        bad("بخش شروع معتبر نیست")
        start = next(iter(nodes))
    fallback = str(cfg.get("fallback") or start)
    if fallback not in nodes:
        bad("بخش پیام‌های ناشناس معتبر نیست")
        fallback = start
    cmds = {}
    for k, v in (cfg.get("commands") or {}).items():
        k = str(k).lstrip("/").lower()
        if not CMD_RE.match(k) or k == "start" or str(v) not in nodes:
            bad(f"دستور «/{k}» معتبر نیست (فقط حروف انگلیسی کوچک/عدد/_ و غیر از start)")
            continue
        cmds[k] = str(v)
    out = {"name": str(cfg.get("name") or "ربات من").strip()[:50] or "ربات من", "start": start,
           "fallback": fallback, "commands": cmds, "nodes": nodes}

    # متغیرهای اعلام‌شده (+ هر متغیری که جایی استفاده شده ولی اعلام نشده، خودکار اضافه می‌شه)
    declared = {}
    dv = cfg.get("vars")
    for k, v in (dv.items() if isinstance(dv, dict) else []):
        k = str(k).strip().lower()
        if VAR_RE.match(k) and k not in BUILTINS:
            declared[k] = str(v if v is not None else "")[:100]
        else:
            bad(f"نام متغیر «{k}» معتبر نیست (حروف انگلیسی کوچک، عدد و _ و نباید اسم متغیرهای آماده باشه)")
    for k in sorted(used):
        declared.setdefault(k, "0" if k in nums else "")
    if len(declared) > MAX_VARS:
        if strict:
            raise ValueError(f"حداکثر {MAX_VARS} متغیر می‌تونی داشته باشی")
        declared = dict(list(declared.items())[:MAX_VARS])
    if declared:
        out["vars"] = declared

    j = cfg.get("join")
    if isinstance(j, dict):
        chans, raw = [], j.get("channels")
        for c in (raw if isinstance(raw, list) else [])[:3]:
            c = re.sub(r"^(https?://)?(t\.me|telegram\.me)/", "", str(c).strip(), flags=re.I).lstrip("@")
            if re.match(r"^[A-Za-z][A-Za-z0-9_]{4,31}$", c):
                chans.append(c)
            else:
                bad(f"آیدی کانال «{c}» معتبر نیست")
        if chans:
            out["join"] = {"channels": chans,
                           "text": str(j.get("text") or "برای استفاده از ربات اول باید عضو کانال بشی 👇").strip()[:500]}
    return out


# ───── تشخیص زبان (برای اینکه «thinking» و متن‌ها هیچ‌وقت انگلیسی نشن) ─────
def _count(s):
    return len(re.findall(r"[\u0600-\u06FF]", s)), len(re.findall(r"[A-Za-z]", s))


def detect_lang(s):
    fa, la = _count(s)
    return "fa" if fa >= la else "other"


class ThinkLang(ValueError):
    def __init__(self, cfg):
        super().__init__("thinking language mismatch")
        self.cfg = cfg


FALLBACK_THINKING = "ربات رو طبق توضیحت طراحی کردم. اگه متن، دکمه یا آیدی کانال چیزی نیاز به تغییر داشت، از «ویرایش دستی» درستش کن."


def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def lint(cfg):
    """مشکل‌های منطقی کانفیگ تمیزشده رو پیدا می‌کنه (برای اینکه AI یک بار خودش درستشون کنه)"""
    nodes, out = cfg["nodes"], []
    seen, stack = set(), [cfg["start"], cfg["fallback"], *cfg["commands"].values()]
    while stack:
        i = stack.pop()
        if i in seen or i not in nodes:
            continue
        seen.add(i)
        n = nodes[i]
        stack += [b["goto"] for row in n["buttons"] for b in row if "goto" in b]
        stack += [r["goto"] for r in n.get("route", [])]
        if n.get("next"):
            stack.append(n["next"])
    lost = [i for i in nodes if i not in seen]
    if lost:
        out.append("unreachable nodes (link them from a goto button / route / next, or remove them): " + ", ".join(lost[:6]))
    dead = [i for i, n in nodes.items() if i in seen and i != cfg["start"] and not n.get("fields") and not n.get("ask")
            and not n.get("route") and not n.get("next") and not any("goto" in b for row in n["buttons"] for b in row)]
    if dead:
        out.append("dead-end nodes with no goto/back button (add a back or home button): " + ", ".join(dead[:6]))
    reads, writes = set(), set()
    for d in _walk(nodes):
        for v in d.values():
            if isinstance(v, str):
                reads.update(m.group(1) for m in PH_RE.finditer(v))
        op = d.get("op")
        if op in OPS and d.get("var"):
            reads.add(d["var"])
        if op in ACT_OPS and op != "notify" and d.get("var"):
            writes.add(d["var"])
        if isinstance(d.get("save"), list):
            writes.update(x for x in d["save"] if x)
    unset = sorted((reads & set(cfg.get("vars", {}))) - writes)
    if unset:
        out.append("variables that are read but never set by any action or form 'save' (set them somewhere or remove them): " + ", ".join(unset[:6]))
    return out


def _call_llm(user, lang, final):
    r = requests.post(
        f"{AI_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {AI_API_KEY}"},
        json={"model": AI_MODEL, "max_tokens": AI_MAX_TOKENS, "temperature": 0.4,
              "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                           {"role": "user", "content": user}]},
        timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"AI HTTP {r.status_code}: {r.text[:300]}")
    try:
        txt = r.json()["choices"][0]["message"]["content"] or ""
    except Exception:
        raise RuntimeError(f"AI پاسخ غیرمنتظره داد: {r.text[:300]}")
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S)
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError(f"پاسخ AI شامل JSON نبود: {txt[:200]!r}")
    raw = json.loads(m.group(0))
    if not isinstance(raw, dict) or not isinstance(raw.get("config"), dict):
        raise ValueError("پاسخ AI فاقد بخش config بود")
    cfg = sanitize(raw["config"])
    thinking = str(raw.get("thinking") or "").strip()[:900]
    if lang == "fa":
        fa, la = _count(thinking)
        if not thinking or la > fa:            # توضیح انگلیسی/خالی شده
            if not final:
                raise ThinkLang(cfg)
            thinking = FALLBACK_THINKING
    return thinking, cfg


def build_user(prompt, current, lang, note_extra=""):
    if lang == "fa":
        note = "OUTPUT LANGUAGE: Persian (فارسی). The \"thinking\" field and all node texts/button labels MUST be written in Persian. Do not write them in English."
    else:
        note = "OUTPUT LANGUAGE: the same language as the user's request below (\"thinking\" included)."
    if note_extra:
        note += " " + note_extra
    parts = [note]
    if current:
        parts.append("Current config:\n" + json.dumps(current, ensure_ascii=False))
        parts.append("Change request:\n" + prompt)
    else:
        parts.append("Bot request:\n" + prompt)
    parts.append("Reminder: reply with the JSON object only; " +
                 ("\"thinking\" in Persian." if lang == "fa" else "\"thinking\" in the request's language."))
    return "\n\n".join(parts)


def ask_llm(prompt, current=None):
    """یک بار تلاش اول؛ اگه خروجی خراب بود، زبان توضیح اشتباه بود یا کانفیگ مشکل منطقی داشت، یک بار با بازخورد دوباره"""
    lang = detect_lang(prompt)
    best, last, feedback = None, None, ""
    for attempt in (0, 1):
        try:
            thinking, cfg = _call_llm(build_user(prompt, current, lang, feedback), lang, final=attempt == 1)
        except ThinkLang as e:
            best, last = best or (None, e.cfg), e
            feedback = "(Your previous answer used the wrong language for \"thinking\". Fix that now.)"
            log.warning("thinking in wrong language, retrying")
            continue
        except (ValueError, KeyError, TypeError) as e:   # خروجی خراب → یک بار دیگه
            last = e
            feedback = f"(Your previous reply was rejected: {str(e)[:200]}. Return one valid JSON object.)"
            log.warning("bad AI output, retrying once", exc_info=True)
            continue
        problems = lint(cfg)
        if problems and attempt == 0:
            best = (thinking, cfg)
            feedback = "(Your previous config had logic problems, fix them and return the FULL config again: " + "; ".join(problems[:6]) + ")"
            log.info("lint problems, retrying: %s", problems)
            continue
        return thinking, cfg
    if best:                        # کانفیگ سالمِ تلاش اول رو نگه می‌داریم
        th, cfg = best
        return (th or FALLBACK_THINKING), cfg
    raise last


# ───────────────────────── API مینی‌اپ ─────────────────────────
@app.get("/")
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "index.html")


@app.get("/media/<name>")
def serve_media(name):
    if ".." in name or "/" in name:
        return "bad", 400
    return send_from_directory(str(MEDIA_DIR), name)


def kind_from_filename(fname, mime):
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
    mime = (mime or "").lower()
    if ext in ("jpg", "jpeg", "png", "webp") or mime.startswith("image/"):
        return "animation" if ext == "gif" else "photo"
    if ext in ("mp4", "mov") or mime.startswith("video/"):
        return "video"
    if ext in ("ogg", "oga") or "voice" in mime:
        return "voice"
    if ext in ("mp3", "m4a", "wav") or mime.startswith("audio/"):
        return "audio"
    return "document"


@app.post("/api/upload")
def api_upload():
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    if "file" not in request.files:
        return jsonify(error="فایل پیدا نشد"), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify(error="فایل پیدا نشد"), 400
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_EXT:
        return jsonify(error=f"این فرمت پشتیبانی نمی‌شه (حداکثر {MAX_MEDIA_MB} مگ)"), 400
    data = f.read()
    if len(data) > MAX_MEDIA_BYTES:
        return jsonify(error=f"فایل خیلی بزرگه (حداکثر {MAX_MEDIA_MB} مگ)"), 400
    if len(data) < 16:
        return jsonify(error="فایل خالیه"), 400
    name = f"{uuid.uuid4().hex}.{ext}"
    (MEDIA_DIR / name).write_bytes(data)
    kind = kind_from_filename(f.filename, f.mimetype or mimetypes.guess_type(f.filename)[0] or "")
    return jsonify(url=f"{BASE_URL}/media/{name}", kind=kind, name=name)


@app.get("/api/me")
def api_me():
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    u = get_user(uid)
    bots = [public(b) for b in db.bots.find({"owner": uid}).sort("updated", -1)]
    today = now().strftime("%Y-%m-%d")
    return jsonify(bots=bots, quota=quota_left(uid), limit=DAILY_LIMIT, max_bots=MAX_BOTS,
                   joined=u["created"].isoformat(),
                   tokens=u.get("tokens", 0), total_spent=u.get("total_spent", 0),
                   referrals=u.get("referrals", 0),
                   referral_link=referral_link(uid), referral_code=f"r_{uid}",
                   daily_claimable=(u.get("daily") != today),
                   costs={"build": GENERATE_COST, "upgrade": UPGRADE_COST,
                          "daily": DAILY_BONUS, "referral": REFERRAL_BONUS},
                   level=level_of(len(bots), u.get("total_spent", 0)))


@app.post("/api/generate")
def api_generate():
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    body = request.get_json(silent=True) or {}
    prompt = str(body.get("prompt", "")).strip()[:MAX_PROMPT]
    if len(prompt) < 5:
        return jsonify(error="توضیح خیلی کوتاهه"), 400

    bot = None
    is_upgrade = False
    if body.get("bot_id"):
        bot = get_bot(body["bot_id"], uid)
        if not bot:
            return jsonify(error="ربات پیدا نشد"), 404
        is_upgrade = True
    elif db.bots.count_documents({"owner": uid}) >= MAX_BOTS:
        return jsonify(error=f"حداکثر {MAX_BOTS} ربات می‌تونی داشته باشی"), 400

    cost = UPGRADE_COST if is_upgrade else GENERATE_COST
    if get_user(uid).get("tokens", 0) < cost:
        return jsonify(error="not_enough_tokens", need=cost,
                       have=get_user(uid).get("tokens", 0),
                       msg=f"توکن کافی نداری (لازم: {cost})"), 402
    if not quota_take(uid):
        return jsonify(error="سهمیه‌ی امروزت تموم شده، فردا دوباره امتحان کن"), 429
    if not spend_tokens(uid, cost, "upgrade" if is_upgrade else "generate"):
        quota_refund(uid)
        return jsonify(error="not_enough_tokens", need=cost,
                       have=get_user(uid).get("tokens", 0)), 402
    mh = body.get("media")
    media_hint = ""
    if isinstance(mh, dict) and mh.get("url"):
        media_hint = f" The user uploaded a {mh.get('kind','photo')} for the start screen: {mh['url']}. Attach it as the start node's media."
    try:
        thinking, cfg = ask_llm(prompt + media_hint, bot["config"] if bot else None)
    except Exception as e:
        add_tokens(uid, cost, "refund:generate_failed")
        quota_refund(uid)
        log.exception("generate failed")
        msg = "ساخت ربات ناموفق بود، دوباره امتحان کن یا توضیح رو ساده‌تر بنویس"
        if DEBUG:
            msg += f"\n[{type(e).__name__}] {str(e)[:300]}"
        return jsonify(error=msg), 502

    if bot:
        db.bots.update_one({"_id": bot["_id"]}, {
            "$set": {"config": cfg, "name": cfg["name"], "thinking": thinking, "updated": now()},
            "$push": {"versions": {"$each": [bot["config"]], "$slice": -MAX_VERSIONS}},
            "$unset": {"last_manual": ""}})
        bot = db.bots.find_one({"_id": bot["_id"]})
        sync_commands(bot, cfg)
    else:
        doc = {"owner": uid, "name": cfg["name"], "config": cfg, "thinking": thinking, "versions": [],
               "active": False, "secret": secrets.token_hex(16), "created": now(), "updated": now()}
        doc["_id"] = db.bots.insert_one(doc).inserted_id
        bot = doc
    return jsonify(bot=public(bot), quota=quota_left(uid), tokens=get_user(uid).get("tokens", 0))


SHOP = [
    {"id": "s50", "tokens": 60, "title": "بسته‌ی شروع", "desc": "60 توکن"},
    {"id": "s150", "tokens": 170, "title": "بسته‌ی سازنده", "desc": "170 توکن · محبوب"},
    {"id": "s400", "tokens": 450, "title": "بسته‌ی حرفه‌ای", "desc": "450 توکن · به‌صرفه"},
]


@app.get("/api/tokens/shop")
def api_shop():
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    return jsonify(plans=SHOP)


@app.post("/api/tokens/claim-daily")
def api_daily():
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    today = now().strftime("%Y-%m-%d")
    if get_user(uid).get("daily") == today:
        return jsonify(error="پاداش امروز رو گرفتی"), 400
    db.users.update_one({"_id": uid}, {"$set": {"daily": today}})
    add_tokens(uid, DAILY_BONUS, "daily")
    return jsonify(tokens=get_user(uid)["tokens"], bonus=DAILY_BONUS)


@app.post("/api/tokens/referral")
def api_referral():
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    code = str((request.get_json(silent=True) or {}).get("code", "")).strip()
    if not code:
        return jsonify(error="کد دعوت رو وارد کن"), 400
    res = apply_referral(uid, code)
    if res == "ok":
        return jsonify(ok=True, bonus=REFERRAL_BONUS, tokens=get_user(uid)["tokens"])
    if res == "already":
        return jsonify(error="قبلاً از کد دعوت استفاده کردی"), 400
    return jsonify(error="کد معتبر نیست"), 400


@app.post("/api/tokens/buy")
def api_buy():
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    pid = str((request.get_json(silent=True) or {}).get("plan", ""))
    plan = next((p for p in SHOP if p["id"] == pid), None)
    if not plan:
        return jsonify(error="پلن نامعتبره"), 400
    db.orders.insert_one({"uid": uid, "plan": pid, "tokens": plan["tokens"], "status": "pending", "t": now()})
    for a in ADMIN_IDS:
        try:
            tg(MOTHER_TOKEN, "sendMessage", chat_id=a,
               text=f"درخواست خرید: کاربر {uid} بسته‌ی {plan['title']} ({plan['tokens']} توکن)")
        except Exception:
            pass
    return jsonify(ok=True, msg="درخواست ثبت شد؛ بعد از تأیید ادمین توکن واریز می‌شه")


@app.post("/api/admin/grant")
def api_grant():
    uid = auth()
    if uid not in ADMIN_IDS:
        return jsonify(error="forbidden"), 403
    body = request.get_json(silent=True) or {}
    try:
        target = int(body.get("user"))
        amount = int(body.get("amount"))
    except Exception:
        return jsonify(error="bad params"), 400
    add_tokens(target, amount, f"admin_grant by {uid}")
    db.orders.update_many({"uid": target, "status": "pending"}, {"$set": {"status": "granted"}})
    return jsonify(ok=True, tokens=db.users.find_one({"_id": target}).get("tokens", 0))


@app.post("/api/bots/<bot_id>/undo")
def api_undo(bot_id):
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    bot = get_bot(bot_id, uid)
    if not bot or not bot.get("versions"):
        return jsonify(error="نسخه‌ی قبلی وجود نداره"), 400
    prev = bot["versions"][-1]
    db.bots.update_one({"_id": bot["_id"]}, {
        "$set": {"config": prev, "name": prev["name"], "thinking": "", "updated": now()},
        "$pop": {"versions": 1}})
    bot = db.bots.find_one({"_id": bot["_id"]})
    sync_commands(bot, bot["config"])
    return jsonify(bot=public(bot))


@app.put("/api/bots/<bot_id>/config")
def api_save_config(bot_id):
    """ذخیره‌ی ویرایش دستی (بدون مصرف سهمیه)"""
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    try:
        cfg = sanitize((request.get_json(silent=True) or {}).get("config"), strict=True)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    if cfg != bot["config"]:
        lm = bot.get("last_manual")
        recent = lm and (now().replace(tzinfo=None) - lm.replace(tzinfo=None)).total_seconds() < 180
        upd = {"$set": {"config": cfg, "name": cfg["name"], "thinking": "", "updated": now(), "last_manual": now()}}
        if not recent:      # ویرایش‌های پشت‌سرهم یک نسخه‌ی برگشت حساب می‌شن
            upd["$push"] = {"versions": {"$each": [bot["config"]], "$slice": -MAX_VERSIONS}}
        db.bots.update_one({"_id": bot["_id"]}, upd)
        bot = db.bots.find_one({"_id": bot["_id"]})
        sync_commands(bot, cfg)
    return jsonify(bot=public(bot))


@app.post("/api/bots/<bot_id>/activate")
def api_activate(bot_id):
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    token = str((request.get_json(silent=True) or {}).get("token", "")).strip()
    if not re.match(r"^\d{6,12}:[\w-]{30,50}$", token):
        return jsonify(error="فرمت توکن درست نیست"), 400
    me = tg(token, "getMe")
    if not me.get("ok"):
        return jsonify(error="توکن معتبر نیست"), 400
    th = thash(token)
    if db.bots.find_one({"token_hash": th, "_id": {"$ne": bot["_id"]}}):
        return jsonify(error="این توکن قبلاً برای ربات دیگه‌ای ثبت شده"), 400
    r = tg(token, "setWebhook", url=f"{BASE_URL}/hook/{bot_id}", secret_token=bot["secret"],
           allowed_updates=["message", "callback_query"], drop_pending_updates=True)
    if not r.get("ok"):
        return jsonify(error="اتصال وبهوک ناموفق بود"), 502
    tg(token, "setMyCommands", commands=[{"command": "start", "description": "شروع"}] + [
        {"command": c, "description": c} for c in bot["config"]["commands"]])
    db.bots.update_one({"_id": bot["_id"]}, {"$set": {
        "token_enc": enc(token), "token_hash": th, "username": me["result"]["username"],
        "active": True, "updated": now()}})
    return jsonify(bot=public(db.bots.find_one({"_id": bot["_id"]})))


@app.post("/api/bots/<bot_id>/deactivate")
def api_deactivate(bot_id):
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    if bot.get("token_enc"):
        tg(dec(bot["token_enc"]), "deleteWebhook")
    db.bots.update_one({"_id": bot["_id"]}, {
        "$set": {"active": False, "updated": now()}, "$unset": {"token_enc": "", "token_hash": ""}})
    return jsonify(bot=public(db.bots.find_one({"_id": bot["_id"]})))


@app.delete("/api/bots/<bot_id>")
def api_delete(bot_id):
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    if bot.get("token_enc"):
        tg(dec(bot["token_enc"]), "deleteWebhook")
    db.bots.delete_one({"_id": bot["_id"]})
    db.states.delete_many({"_id": {"$regex": f"^{bot_id}:"}})
    db.rk.delete_many({"_id": {"$regex": f"^{bot_id}:"}})
    db.uvars.delete_many({"_id": {"$regex": f"^{bot_id}:"}})
    return jsonify(ok=True)


# ───────────────────────── موتور اجرای کانفیگ ─────────────────────────
_WEEK = {5: "شنبه", 6: "یکشنبه", 0: "دوشنبه", 1: "سه‌شنبه", 2: "چهارشنبه", 3: "پنجشنبه", 4: "جمعه"}
FORM_HINT = {"number": "فقط عدد بفرست 🔢", "phone": "یه شماره‌ی تماس معتبر بفرست، مثل 09123456789 📱",
             "email": "یه ایمیل معتبر بفرست 📧"}


def to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + g_d_m[gm - 1]
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


class Env:
    """همه‌ی اطلاعات یک رویداد: ربات، کاربر و متغیرهای ذخیره‌شده‌ی همون کاربر"""

    def __init__(self, bot, token, chat_id, user, text="", param=""):
        self.bot, self.token, self.chat_id = bot, token, chat_id
        self.cfg, self.bot_id, self.owner = bot["config"], str(bot["_id"]), bot["owner"]
        self.user = user or {}
        self.uid = self.user.get("id", chat_id)
        self.text, self.param = text or "", param or ""
        self.sid = f"{self.bot_id}:{chat_id}"
        self._key = f"{self.bot_id}:{self.uid}"
        doc = db.uvars.find_one({"_id": self._key}) or {}
        self.vars = {k: str(v) for k, v in (doc.get("v") or {}).items()}
        self.visits = int(doc.get("visits", 0))
        self.dirty = False
        self._now = now() + timedelta(hours=3, minutes=30)      # ساعت تهران

    def builtin(self, k):
        u = self.user
        if k == "name":
            return u.get("first_name") or "دوست من"
        if k == "first_name":
            return u.get("first_name") or ""
        if k == "last_name":
            return u.get("last_name") or ""
        if k == "full_name":
            return " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x) or "دوست من"
        if k == "username":
            return ("@" + u["username"]) if u.get("username") else ""
        if k == "id":
            return str(self.uid)
        if k == "lang":
            return u.get("language_code") or ""
        if k == "premium":
            return "1" if u.get("is_premium") else "0"
        if k == "is_owner":
            return "1" if self.uid == self.owner else "0"
        if k == "bot_name":
            return self.cfg.get("name", "")
        if k == "bot_username":
            return ("@" + self.bot["username"]) if self.bot.get("username") else ""
        if k == "text":
            return self.text
        if k == "param":
            return self.param
        if k == "visits":
            return str(self.visits)
        n = self._now
        if k == "date":
            jy, jm, jd = to_jalali(n.year, n.month, n.day)
            return f"{jy}/{jm:02d}/{jd:02d}"
        if k == "time":
            return n.strftime("%H:%M")
        if k == "hour":
            return str(n.hour)
        if k == "weekday":
            return _WEEK[n.weekday()]
        return ""

    def get(self, k):
        if k in BUILTINS:
            return self.builtin(k)
        if k in self.vars:
            return self.vars[k]
        return str((self.cfg.get("vars") or {}).get(k, ""))

    def set(self, k, v):
        if k in BUILTINS or not VAR_RE.match(k or "") or k not in (self.cfg.get("vars") or {}):
            return
        self.vars[k] = str(v)[:200]
        self.dirty = True

    def reset(self, k):
        if self.vars.pop(k, None) is not None:
            self.dirty = True

    def save(self):
        if self.dirty:
            db.uvars.update_one({"_id": self._key},
                                {"$set": {"v": self.vars, "visits": self.visits, "t": now()}}, upsert=True)
            self.dirty = False


def fill(t, env):
    """{name} / {coins} / {city|پیش‌فرض} رو با مقدار جایگزین می‌کنه (اسم ناشناس دست‌نخورده می‌مونه)"""
    declared = env.cfg.get("vars") or {}

    def rep(m):
        k = m.group(1)
        if k in BUILTINS or k in declared:
            v = env.get(k)
            return v if (v != "" or m.group(2) is None) else m.group(2)
        return m.group(0)
    return PH_RE.sub(rep, str(t))


def check(cond, env, depth=0):
    """ارزیابی شرط"""
    if not isinstance(cond, dict) or depth > 3:
        return False
    if "all" in cond:
        return all(check(c, env, depth + 1) for c in cond["all"])
    if "any" in cond:
        return any(check(c, env, depth + 1) for c in cond["any"])
    if "not" in cond:
        return not check(cond["not"], env, depth + 1)
    a, op = env.get(cond.get("var", "")), cond.get("op", "==")
    if op == "empty":
        return a.strip() == ""
    if op == "filled":
        return a.strip() != ""
    b = fill(cond.get("value", ""), env)
    if op == "contains":
        return b.casefold() in a.casefold()
    x, y = to_num(a), to_num(b)
    if op in ("==", "!="):
        eq = (x == y) if (x is not None and y is not None) else a.strip().casefold() == b.strip().casefold()
        return eq if op == "==" else not eq
    if x is None or y is None:
        return False
    return {">": x > y, ">=": x >= y, "<": x < y, "<=": x <= y}.get(op, False)


def who(env):
    u = env.user
    return f"👤 {u.get('first_name', '')} (@{u.get('username', '-')}) — {env.uid}"


def run_actions(acts, env):
    for a in acts or []:
        op, name = a.get("op"), a.get("var", "")
        val = fill(a.get("value", ""), env)
        if op == "set":
            env.set(name, val)
        elif op == "add":
            env.set(name, fmt_num((to_num(env.get(name)) or 0) + (to_num(val) or 0)))
        elif op == "clear":
            env.reset(name)
        elif op == "random":
            m = re.fullmatch(r"(\d+)-(\d+)", val.translate(_DIG).strip())
            if m and int(m.group(1)) <= int(m.group(2)):
                env.set(name, str(random.randint(int(m.group(1)), int(m.group(2)))))
        elif op == "notify" and val.strip():
            tg(env.token, "sendMessage", chat_id=env.owner, text=f"🔔 {env.cfg.get('name', '')}\n{val}\n\n{who(env)}"[:4000])


def visible(b, env):
    return not b.get("when") or check(b["when"], env)


def keyboard(node, node_id, env):
    kb = []
    for ri, row in enumerate(node["buttons"]):
        r = []
        for ci, b in enumerate(row):
            if not visible(b, env):
                continue
            label = fill(b["text"], env)[:64] or "·"
            if "url" in b:
                r.append({"text": label, "url": b["url"]})
            elif "goto" in b:
                cd = f"g:{node_id}:{ri}:{ci}" if b.get("do") else f"n:{b['goto']}"
                r.append({"text": label, "callback_data": cd})
            elif "alert" in b:
                r.append({"text": label, "callback_data": f"a:{node_id}:{ri}:{ci}"})
            elif "copy" in b:
                r.append({"text": label, "copy_text": {"text": fill(b["copy"], env)[:256]}})
        if r:
            kb.append(r)
    return kb


def reply_markup(node, env):
    """کیبورد زیر صفحه‌ی چت (Reply Keyboard)"""
    rows = [[{"text": fill(b["text"], env)[:64] or "·"} for b in row if visible(b, env)] for row in node["buttons"]]
    return {"keyboard": [r for r in rows if r], "resize_keyboard": True, "is_persistent": True}


def clear_reply_kb(env):
    """کیبورد قبلی زیر چت رو برمی‌داره (با یه پیام موقت که فوراً پاک می‌شه)"""
    if not db.rk.find_one({"_id": env.sid}):
        return
    r = tg(env.token, "sendMessage", chat_id=env.chat_id, text="⏳", reply_markup={"remove_keyboard": True})
    mid = (r.get("result") or {}).get("message_id")
    if mid:
        tg(env.token, "deleteMessage", chat_id=env.chat_id, message_id=mid)
    db.rk.delete_one({"_id": env.sid})


MEDIA_SEND = {"photo": "sendPhoto", "video": "sendVideo", "animation": "sendAnimation",
              "voice": "sendVoice", "audio": "sendAudio", "document": "sendDocument"}
MEDIA_FIELD = {"photo": "photo", "video": "video", "animation": "animation",
               "voice": "voice", "audio": "audio", "document": "document"}


def send_media_message(token, chat_id, media, caption, markup):
    """ارسال مدیای بخش (ویدیو/صوت/سند/...)"""
    kind = (media or {}).get("kind", "photo")
    method = MEDIA_SEND.get(kind, "sendPhoto")
    field = MEDIA_FIELD.get(kind, "photo")
    data = {"chat_id": chat_id, field: media["url"]}
    if caption:
        data["caption"] = (caption or "")[:1024]
    if markup:
        data["reply_markup"] = markup
    try:
        return bool(tg(token, method, **data).get("ok"))
    except Exception:
        log.exception("media send failed")
        return False


def send_node(env, node_id, edit=None, depth=0):
    """edit = پیام قبلی (callback) → اگه ممکن باشه همون پیام ویرایش می‌شه، نه اینکه پیام جدید بیاد"""
    cfg, token, chat_id = env.cfg, env.token, env.chat_id
    if node_id not in cfg["nodes"]:
        node_id = cfg["start"]
    node = cfg["nodes"][node_id]
    run_actions(node.get("do"), env)                       # ۱) اکشن‌های ورود
    if depth < MAX_HOPS:                                   # ۲) هدایت شرطی
        for rule in node.get("route", []):
            if rule["goto"] in cfg["nodes"] and check(rule["when"], env):
                return send_node(env, rule["goto"], edit=edit, depth=depth + 1)
    text = node["text"]                                    # ۳) متن جایگزین شرطی
    for alt in node.get("alt", []):
        if check(alt["when"], env):
            text = alt["text"]
            break
    text = fill(text, env)[:4000]
    kb = keyboard(node, node_id, env)
    use_reply = node.get("kb") == "reply" and bool(kb)
    if not use_reply:
        clear_reply_kb(env)
    markup = reply_markup(node, env) if use_reply else {"inline_keyboard": kb}
    # مدیا: فرمت جدید media + سازگاری با photo قدیمی
    media = node.get("media")
    if not media and node.get("photo"):
        media = {"kind": "photo", "url": node["photo"]}
    photo = media["url"] if media and media.get("kind") == "photo" else None
    done = False
    if edit and not use_reply and not media and not edit.get("photo"):
        r = tg(token, "editMessageText", chat_id=chat_id, message_id=edit["message_id"], text=text, reply_markup=markup)
        done = bool(r.get("ok")) or "not modified" in str(r.get("description", ""))
    if not done:
        if edit:
            tg(token, "deleteMessage", chat_id=chat_id, message_id=edit["message_id"])
        if media and (not photo or media.get("kind") != "photo"):
            # ویدیو/صوت/سند: ارسال فایل + متن
            if not send_media_message(token, chat_id, media, text[:1024] if len(text) <= 1024 else "", markup if kb else None):
                tg(token, "sendMessage", chat_id=chat_id, text=text, **({"reply_markup": markup} if kb else {}))
            elif len(text) > 1024:
                tg(token, "sendMessage", chat_id=chat_id, text=text, **({"reply_markup": markup} if kb else {}))
            done = True
        elif photo:
            data = {"chat_id": chat_id, "photo": photo}
            if len(text) <= 1000:
                data.update(caption=text, **({"reply_markup": markup} if kb else {}))
                done = bool(tg(token, "sendPhoto", **data).get("ok"))
            else:
                tg(token, "sendPhoto", **data)
                done = False   # متن بلند جداگونه می‌ره
        if not done:
            tg(token, "sendMessage", chat_id=chat_id, text=text, **({"reply_markup": markup} if kb else {}))
    sid = env.sid
    if use_reply:
        db.rk.replace_one({"_id": sid}, {"_id": sid, "node": node_id, "t": now()}, upsert=True)
    if node.get("fields"):
        db.states.replace_one({"_id": sid}, {"_id": sid, "form": node_id, "a": [], "t": now()}, upsert=True)
        tg(token, "sendMessage", chat_id=chat_id, text=fill(node["fields"][0], env))
    elif node.get("ask"):
        db.states.replace_one({"_id": sid}, {"_id": sid, "ask": node_id, "t": now()}, upsert=True)
    else:
        db.states.delete_one({"_id": sid})


def reply_press(env, rk, text):
    """وقتی کاربر یکی از دکمه‌های کیبورد زیر چت رو می‌زنه (متن دکمه به‌صورت پیام میاد)"""
    node = env.cfg["nodes"].get(rk.get("node"))
    if not node:
        return False
    for row in node["buttons"]:
        for b in row:
            if not visible(b, env) or text not in (fill(b["text"], env), b["text"]):
                continue
            run_actions(b.get("do"), env)
            if "goto" in b:
                send_node(env, b["goto"])
            elif "alert" in b:
                tg(env.token, "sendMessage", chat_id=env.chat_id, text=fill(b["alert"], env))
            elif "copy" in b:
                c = fill(b["copy"], env)[:256]
                tg(env.token, "sendMessage", chat_id=env.chat_id, text=c,
                   reply_markup={"inline_keyboard": [[{"text": "📋 کپی", "copy_text": {"text": c}}]]})
            elif "url" in b:
                tg(env.token, "sendMessage", chat_id=env.chat_id, text="👇",
                   reply_markup={"inline_keyboard": [[{"text": fill(b["text"], env)[:64], "url": b["url"]}]]})
            return True
    return False


def finish(env, node, default_done):
    tg(env.token, "sendMessage", chat_id=env.chat_id, text=fill(node.get("done") or default_done, env))
    send_node(env, node.get("next") or env.cfg["start"])


def valid_answer(kind, t):
    """اعتبارسنجی جواب فرم؛ (درست؟، مقدار تمیزشده)"""
    t = t.strip()
    if kind == "number":
        n = to_num(t)
        return (True, fmt_num(n)) if n is not None else (False, t)
    if kind == "phone":
        d = re.sub(r"[\s\-()]", "", t.translate(_DIG))
        return bool(re.fullmatch(r"\+?\d{8,15}", d)), d
    if kind == "email":
        return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]{2,}", t)), t
    return True, t


def gate_ok(token, cfg, uid):
    """عضویت اجباری؛ اگه ربات ادمین کانال نباشه (یا خطا بشه) مانع کاربر نمی‌شیم"""
    j = cfg.get("join")
    if not j:
        return True
    for ch in j["channels"]:
        r = tg(token, "getChatMember", chat_id="@" + ch, user_id=uid)
        if r.get("ok") and r["result"].get("status") in ("left", "kicked"):
            return False
    return True


def send_gate(token, chat_id, cfg):
    j = cfg["join"]
    kb = [[{"text": f"📢 @{c}", "url": f"https://t.me/{c}"}] for c in j["channels"]]
    kb.append([{"text": "✅ عضو شدم", "callback_data": "chk"}])
    tg(token, "sendMessage", chat_id=chat_id, text=j["text"], reply_markup={"inline_keyboard": kb})


@app.post("/hook/<bot_id>")
def sub_hook(bot_id):
    try:
        bot = db.bots.find_one({"_id": ObjectId(bot_id)})
    except InvalidId:
        return "ok"
    if not bot or not bot.get("active") or not bot.get("token_enc"):
        return "ok"
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != bot["secret"]:
        return "forbidden", 403
    upd = request.get_json(silent=True) or {}
    token, cfg = dec(bot["token_enc"]), bot["config"]
    env = None
    try:
        cq = upd.get("callback_query")
        if cq:
            data, user, m = cq.get("data", ""), cq.get("from", {}), cq.get("message") or {}
            chat_id = (m.get("chat") or {}).get("id")
            if not chat_id:
                tg(token, "answerCallbackQuery", callback_query_id=cq["id"])
                return "ok"
            env = Env(bot, token, chat_id, user)
            if not gate_ok(token, cfg, user["id"]):
                if data == "chk":
                    tg(token, "answerCallbackQuery", callback_query_id=cq["id"], text="هنوز عضو نشدی 🙂", show_alert=True)
                else:
                    tg(token, "answerCallbackQuery", callback_query_id=cq["id"])
                    send_gate(token, chat_id, cfg)
                return "ok"
            if data.startswith(("a:", "g:")):
                try:
                    kind, nid, ri, ci = data.split(":")
                    b = cfg["nodes"][nid]["buttons"][int(ri)][int(ci)]
                except Exception:
                    tg(token, "answerCallbackQuery", callback_query_id=cq["id"])
                    return "ok"
                if not visible(b, env):
                    tg(token, "answerCallbackQuery", callback_query_id=cq["id"],
                       text="این گزینه الان در دسترس نیست", show_alert=True)
                    return "ok"
                run_actions(b.get("do"), env)
                if kind == "a":
                    tg(token, "answerCallbackQuery", callback_query_id=cq["id"],
                       text=fill(b.get("alert", ""), env)[:200], show_alert=True)
                else:
                    tg(token, "answerCallbackQuery", callback_query_id=cq["id"])
                    send_node(env, b["goto"], edit=m)
                return "ok"
            tg(token, "answerCallbackQuery", callback_query_id=cq["id"])
            if data == "chk":
                send_node(env, cfg["start"], edit=m)
            elif data.startswith("n:") and data[2:] in cfg["nodes"]:
                send_node(env, data[2:], edit=m)
            return "ok"
        msg = upd.get("message")
        if not msg or msg["chat"]["type"] != "private":
            return "ok"
        chat_id, user = msg["chat"]["id"], msg.get("from", {})
        text = (msg.get("text") or "").strip()
        env = Env(bot, token, chat_id, user, text=text)
        if not gate_ok(token, cfg, user.get("id", chat_id)):
            send_gate(token, chat_id, cfg)
            return "ok"
        sid = env.sid
        if text.startswith("/"):
            parts = text[1:].split(maxsplit=1)
            cmd = parts[0].split("@")[0].lower() if parts else ""
            env.param = parts[1].strip()[:64] if len(parts) > 1 else ""
            if cmd == "start":
                env.visits += 1
                env.dirty = True
                send_node(env, cfg["start"])
            elif cmd in cfg["commands"]:
                send_node(env, cfg["commands"][cmd])
            else:
                send_node(env, cfg["fallback"])
            return "ok"
        state = db.states.find_one({"_id": sid})
        if state and state.get("form") in cfg["nodes"] and cfg["nodes"][state["form"]].get("fields"):
            node = cfg["nodes"][state["form"]]
            fields = node["fields"]
            if not text:
                tg(token, "sendMessage", chat_id=chat_id, text="لطفاً جوابت رو به‌صورت متن بفرست 🙏")
                return "ok"
            idx = len(state.get("a") or [])
            types = node.get("types") or []
            ok, val = valid_answer(types[idx] if idx < len(types) else "text", text)
            if not ok:
                tg(token, "sendMessage", chat_id=chat_id, text=FORM_HINT.get(types[idx], "جواب معتبر نیست، دوباره بفرست 🙏"))
                return "ok"
            sv = node.get("save") or []
            if idx < len(sv) and sv[idx]:
                env.set(sv[idx], val)
            ans = (state.get("a") or []) + [val[:500]]
            if len(ans) < len(fields):
                db.states.update_one({"_id": sid}, {"$set": {"a": ans}})
                tg(token, "sendMessage", chat_id=chat_id, text=fill(fields[len(ans)], env))
            else:
                db.states.delete_one({"_id": sid})
                if not node.get("silent"):
                    body = "\n\n".join(f"{q}\n» {a}" for q, a in zip(fields, ans))
                    tg(token, "sendMessage", chat_id=bot["owner"],
                       text=(f"📝 فرم جدید — {cfg['name']}\n{who(env)}\n\n{body}")[:4000])
                finish(env, node, "✅ اطلاعاتت ثبت شد، ممنون!")
        elif state and state.get("ask"):
            r = tg(token, "copyMessage", chat_id=bot["owner"], from_chat_id=chat_id, message_id=msg["message_id"])
            if r.get("ok"):
                tg(token, "sendMessage", chat_id=bot["owner"], text=who(env))
            db.states.delete_one({"_id": sid})
            node = cfg["nodes"].get(state["ask"]) if isinstance(state["ask"], str) else None
            finish(env, node or {}, "✅ پیامت ارسال شد.")
        else:
            rk = db.rk.find_one({"_id": sid}) if text else None
            if not (rk and reply_press(env, rk, text)):
                send_node(env, cfg["fallback"])
    except Exception:
        log.exception("sub_hook error")
    finally:
        if env:
            try:
                env.save()
            except Exception:
                log.exception("saving user vars failed")
    return "ok"


# ───────────────────────── ربات مادر ─────────────────────────
@app.post("/mother")
def mother_hook():
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != MOTHER_SECRET:
        return "forbidden", 403
    msg = (request.get_json(silent=True) or {}).get("message")
    if msg and msg.get("chat", {}).get("type") == "private":
        uid = msg["chat"]["id"]
        get_user(uid)
        text = (msg.get("text") or "").strip()
        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            if len(parts) > 1 and parts[1].strip().lower().startswith("r_"):
                apply_referral(uid, parts[1].strip())
        tg(MOTHER_TOKEN, "sendMessage", chat_id=msg["chat"]["id"],
           text="سلام! اینجا با هوش مصنوعی ربات تلگرام می‌سازی.\nفقط بگو چه رباتی می‌خوای. ساخت و ارتقا با توکنه؛ با دعوت دوستات توکن بگیر.",
           reply_markup={"inline_keyboard": [[{"text": "ساخت ربات", "web_app": {"url": BASE_URL}}]]})
    return "ok"


def setup_mother():
    r = tg(MOTHER_TOKEN, "setWebhook", url=f"{BASE_URL}/mother", secret_token=MOTHER_SECRET,
           allowed_updates=["message"])
    tg(MOTHER_TOKEN, "setChatMenuButton",
       menu_button={"type": "web_app", "text": "ساخت ربات", "web_app": {"url": BASE_URL}})
    log.info("mother webhook: %s", r)


try:
    if MOTHER_TOKEN and BASE_URL:
        setup_mother()
except Exception as e:
    log.warning("setup_mother: %s", e)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
