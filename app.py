# -*- coding: utf-8 -*-
"""
AI BotMaker — رباتساز هوشمند ساده
Stack (مثل GramSaz): Flask + MongoDB(pymongo) + مینی‌اپ تک‌فایلی
- ربات مادر: فقط /start و دکمه‌ی باز کردن مینی‌اپ
- مینی‌اپ: کاربر توضیح می‌ده چه رباتی می‌خواد، هوش مصنوعی «کانفیگ JSON» می‌سازه
- موتور ثابت و امن (execute_node) کانفیگ رو اجرا می‌کنه؛ هیچ کد تولیدشده‌ای اجرا نمی‌شه
"""
import os, re, json, time, hmac, hashlib, base64, secrets, logging
from urllib.parse import parse_qsl
from datetime import datetime, timezone

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
DEBUG        = os.environ.get("DEBUG", "") == "1"   # علت دقیق خطا رو توی مینی‌اپ نشون می‌ده
MAX_PROMPT   = 1200
MAX_VERSIONS = 5
MAX_NODES    = 25

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aibot")

app = Flask(__name__)
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
SYSTEM_PROMPT = """You design Telegram bots as a JSON config. You think like a senior product designer, not a form-filler.

LANGUAGE RULE (strict, highest priority): the request states the OUTPUT LANGUAGE. Write "thinking" and EVERY user-facing text (node texts, button labels, bot name) in that language. If it says Persian, write natural Persian (فارسی) and NEVER English, even though this prompt, the JSON keys and the node_ids are English.

Output ONLY one valid JSON object, no markdown fences, no comments. Top-level shape:
{
 "thinking": "...",
 "config": { ...bot config as described below... }
}

"thinking" (string, 2-5 short sentences, in the OUTPUT LANGUAGE, natural first-person tone, like a sharp colleague briefly narrating their plan, not a formal report):
- Say what you understood the user wants.
- Name the key sections/flows you decided the bot needs and briefly why.
- If you made a judgment call, filled a gap, or used a placeholder (price, phone, channel id, link), say so and tell them they can edit it with the manual edit button.
- If this is an update to an existing bot, mention only what you're changing and why, not the whole bot again.
- No headers, no bullet points, no markdown, just natural flowing sentences.

"config" schema:
{
 "name": "short bot name",
 "start": "<node_id shown on /start>",
 "fallback": "<node_id shown for unknown messages>",
 "commands": {"help": "<node_id>"},
 "nodes": {
   "<node_id>": {
     "text": "message text",
     "buttons": [[{"text": "label", "goto": "<node_id>"}, {"text": "label", "url": "https://..."}]],
     "ask": false
   }
 }
}

Design rules:
- Think before you structure: identify the bot's real purpose, the natural user journeys, and the minimum set of nodes that cover them well. Don't pad with filler, but don't skip an obviously needed part (a shop bot needs a way to order, a business bot needs contact/support, a content bot usually needs a channel link).
- node_id: lowercase english letters, digits, underscore. Max 25 nodes, max 3 buttons per row, max 6 rows per node.
- A button has either "goto" (an existing node_id) or "url" (https only).
- Channel/group join button: {"text": "📢 عضویت در کانال", "url": "https://t.me/<username>"} (username without @). Use the username the user gave. If they gave none, use https://t.me/your_channel and say in "thinking" that the real channel id must be set via manual edit.
- If "ask" is true, the node's text asks the user something and their next message is delivered to the bot owner (use for contact, orders, feedback, support). Give ask nodes a cancel/home button too.
- Every "goto", "start", "fallback" and command target MUST exist in nodes. Every node must be reachable from start; no dead ends: every non-start node has a back/home button.
- Button labels short (max ~22 chars). Put at most 2 buttons in a row when labels are long.
- Never invent real-world facts (prices, phone numbers, addresses, links). Use obvious placeholders such as [قیمت] or [شماره تماس] and mention it in "thinking".
- Write all user-facing text in the OUTPUT LANGUAGE. Use emojis moderately.
- When an existing config is given, apply the user's change precisely and return the FULL updated config. Keep every untouched node, text and button exactly as it was (the user may have edited them by hand).
- Plain text only, no Markdown/HTML formatting characters in node texts."""

ID_RE = re.compile(r"^[a-z0-9_]{1,30}$")
CMD_RE = re.compile(r"^[a-z0-9_]{1,30}$")
TG_NAME_RE = re.compile(r"^@?[A-Za-z][A-Za-z0-9_]{4,31}$")


def norm_url(v):
    """@channel / t.me/x / https://... → https URL معتبر (یا None)"""
    v = str(v or "").strip()
    if TG_NAME_RE.match(v):
        return "https://t.me/" + v.lstrip("@")
    if re.match(r"^(t\.me|telegram\.me)/", v, re.I):
        v = "https://" + v
    if v.startswith("https://") and len(v) > 12 and not re.search(r"\s", v):
        return v[:500]
    return None


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
                g = str(b.get("goto") or "")
                if g:
                    if g in valid:
                        r.append({"text": label, "goto": g})
                    else:
                        bad(f"دکمه‌ی «{label}» به بخش ناموجود وصله")
                else:
                    u = norm_url(b.get("url"))
                    if u:
                        r.append({"text": label, "url": u})
                    else:
                        bad(f"لینک/آیدی دکمه‌ی «{label}» معتبر نیست (باید https:// یا @آیدی باشه)")
            if r:
                rows.append(r)
        nodes[nid] = {"text": text, "buttons": rows, "ask": bool(n.get("ask"))}

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
    return {"name": str(cfg.get("name") or "ربات من").strip()[:50] or "ربات من", "start": start,
            "fallback": fallback, "commands": cmds, "nodes": nodes}


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


def _call_llm(user, lang, final):
    r = requests.post(
        f"{AI_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {AI_API_KEY}"},
        json={"model": AI_MODEL, "max_tokens": 4000, "temperature": 0.4,
              "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                           {"role": "user", "content": user}]},
        timeout=90)
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


def build_user(prompt, current, lang, hard):
    if lang == "fa":
        note = "OUTPUT LANGUAGE: Persian (فارسی). The \"thinking\" field and all node texts/button labels MUST be written in Persian. Do not write them in English."
    else:
        note = "OUTPUT LANGUAGE: the same language as the user's request below (\"thinking\" included)."
    if hard:
        note += " (Your previous answer used the wrong language for \"thinking\". Fix that now.)"
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
    lang = detect_lang(prompt)
    saved, last = None, None
    for attempt in (0, 1):
        try:
            return _call_llm(build_user(prompt, current, lang, hard=attempt > 0), lang, final=attempt == 1)
        except ThinkLang as e:
            saved, last = e.cfg, e
            log.warning("thinking in wrong language, retrying")
        except (ValueError, KeyError, TypeError) as e:   # خروجی خراب → یک بار دیگه
            last = e
            log.warning("bad AI output, retrying once", exc_info=True)
    if saved:                       # کانفیگ سالم بود، فقط توضیح زبانش اشتباه بود
        return FALLBACK_THINKING, saved
    raise last


# ───────────────────────── API مینی‌اپ ─────────────────────────
@app.get("/")
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "index.html")


@app.get("/api/me")
def api_me():
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    bots = [public(b) for b in db.bots.find({"owner": uid}).sort("updated", -1)]
    return jsonify(bots=bots, quota=quota_left(uid), limit=DAILY_LIMIT, max_bots=MAX_BOTS)


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
    if body.get("bot_id"):
        bot = get_bot(body["bot_id"], uid)
        if not bot:
            return jsonify(error="ربات پیدا نشد"), 404
    elif db.bots.count_documents({"owner": uid}) >= MAX_BOTS:
        return jsonify(error=f"حداکثر {MAX_BOTS} ربات می‌تونی داشته باشی"), 400

    if not quota_take(uid):
        return jsonify(error="سهمیه‌ی امروزت تموم شده، فردا دوباره امتحان کن"), 429
    try:
        thinking, cfg = ask_llm(prompt, bot["config"] if bot else None)
    except Exception as e:
        quota_refund(uid)
        log.exception("generate failed")
        msg = "ساخت ربات ناموفق بود، دوباره امتحان کن یا توضیح رو ساده‌تر بنویس"
        if DEBUG:
            msg += f"\n[{type(e).__name__}] {str(e)[:300]}"
        return jsonify(error=msg), 502

    if bot:
        db.bots.update_one({"_id": bot["_id"]}, {
            "$set": {"config": cfg, "name": cfg["name"], "thinking": thinking, "updated": now()},
            "$push": {"versions": {"$each": [bot["config"]], "$slice": -MAX_VERSIONS}}})
        bot = db.bots.find_one({"_id": bot["_id"]})
        sync_commands(bot, cfg)
    else:
        doc = {"owner": uid, "name": cfg["name"], "config": cfg, "thinking": thinking, "versions": [],
               "active": False, "secret": secrets.token_hex(16), "created": now(), "updated": now()}
        doc["_id"] = db.bots.insert_one(doc).inserted_id
        bot = doc
    return jsonify(bot=public(bot), quota=quota_left(uid))


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
        db.bots.update_one({"_id": bot["_id"]}, {
            "$set": {"config": cfg, "name": cfg["name"], "thinking": "", "updated": now()},
            "$push": {"versions": {"$each": [bot["config"]], "$slice": -MAX_VERSIONS}}})
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
    db.states.delete_many({"bot": bot_id})
    return jsonify(ok=True)


# ───────────────────────── موتور اجرای کانفیگ ─────────────────────────
def send_node(token, chat_id, cfg, node_id, bot_id):
    node = cfg["nodes"].get(node_id) or cfg["nodes"][cfg["start"]]
    kb = []
    for row in node["buttons"]:
        kb.append([{"text": b["text"], **({"url": b["url"]} if "url" in b
                    else {"callback_data": f"n:{b['goto']}"})} for b in row])
    data = {"chat_id": chat_id, "text": node["text"]}
    if kb:
        data["reply_markup"] = {"inline_keyboard": kb}
    tg(token, "sendMessage", **data)
    sid = f"{bot_id}:{chat_id}"
    if node.get("ask"):
        db.states.update_one({"_id": sid}, {"$set": {"ask": True, "t": now()}}, upsert=True)
    else:
        db.states.delete_one({"_id": sid})


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
    try:
        cq = upd.get("callback_query")
        if cq:
            tg(token, "answerCallbackQuery", callback_query_id=cq["id"])
            data = cq.get("data", "")
            if data.startswith("n:") and data[2:] in cfg["nodes"]:
                send_node(token, cq["message"]["chat"]["id"], cfg, data[2:], bot_id)
            return "ok"
        msg = upd.get("message")
        if not msg or msg["chat"]["type"] != "private":
            return "ok"
        chat_id = msg["chat"]["id"]
        text = (msg.get("text") or "").strip()
        if text.startswith("/"):
            cmd = text[1:].split()[0].split("@")[0].lower()
            if cmd == "start":
                send_node(token, chat_id, cfg, cfg["start"], bot_id)
            elif cmd in cfg["commands"]:
                send_node(token, chat_id, cfg, cfg["commands"][cmd], bot_id)
            else:
                send_node(token, chat_id, cfg, cfg["fallback"], bot_id)
            return "ok"
        state = db.states.find_one({"_id": f"{bot_id}:{chat_id}"})
        if state and state.get("ask"):
            r = tg(token, "copyMessage", chat_id=bot["owner"], from_chat_id=chat_id,
                   message_id=msg["message_id"])
            u = msg["from"]
            if r.get("ok"):
                tg(token, "sendMessage", chat_id=bot["owner"],
                   text=f"👤 {u.get('first_name', '')} (@{u.get('username', '-')}) — {u['id']}")
            db.states.delete_one({"_id": f"{bot_id}:{chat_id}"})
            tg(token, "sendMessage", chat_id=chat_id, text="✅ پیامت ارسال شد.")
            send_node(token, chat_id, cfg, cfg["start"], bot_id)
        else:
            send_node(token, chat_id, cfg, cfg["fallback"], bot_id)
    except Exception:
        log.exception("sub_hook error")
    return "ok"


# ───────────────────────── ربات مادر ─────────────────────────
@app.post("/mother")
def mother_hook():
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != MOTHER_SECRET:
        return "forbidden", 403
    msg = (request.get_json(silent=True) or {}).get("message")
    if msg and msg.get("chat", {}).get("type") == "private":
        tg(MOTHER_TOKEN, "sendMessage", chat_id=msg["chat"]["id"],
           text="🤖 سلام! اینجا با هوش مصنوعی ربات تلگرام می‌سازی.\nفقط بگو چه رباتی می‌خوای.",
           reply_markup={"inline_keyboard": [[{"text": "🚀 ساخت ربات", "web_app": {"url": BASE_URL}}]]})
    return "ok"


def setup_mother():
    r = tg(MOTHER_TOKEN, "setWebhook", url=f"{BASE_URL}/mother", secret_token=MOTHER_SECRET,
           allowed_updates=["message"])
    tg(MOTHER_TOKEN, "setChatMenuButton",
       menu_button={"type": "web_app", "text": "ساخت ربات", "web_app": {"url": BASE_URL}})
    log.info("mother webhook: %s", r)


setup_mother()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
