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
 "join": {"channels": ["channel_username"], "text": "message asking to join"},      (optional, see below)
"nodes": {
    "<node_id>": {
      "title": "short human label of this section, max 30 chars, OUTPUT LANGUAGE",
      "text": "message text (you may use {name} for the user's first name)",
      "photo": "https://direct-image-link",                                          (optional)
      "keyboard_type": "inline",                                                    (optional, "inline" or "reply")
      "buttons": [[ {"text": "label", "goto": "<node_id>"},
                    {"text": "label", "url": "https://..."},
                    {"text": "label", "alert": "popup text shown when tapped"},
                    {"text": "label", "copy": "text copied to clipboard when tapped"} ]],
      "ask": false,
      "fields": ["Question 1?", "Question 2?"],                                       (optional, multi-step form)
      "done": "message shown after the user finished ask/form",                      (optional)
      "next": "<node_id shown after finishing>"                                       (optional, default start)
    }
  }
}

What the engine can do (use these freely when they fit the request):
- Buttons: goto a section, open a link, show a popup message (alert), copy text (e.g. card number, promo code).
- "keyboard_type": "inline" (default) = buttons appear below the message (inline keyboard). "reply" = buttons appear below the chat input as a persistent keyboard (reply keyboard). Reply keyboards only support simple text buttons (no goto, url, alert, copy); tapping sends the button text as a message.
- "ask": true = the user's next message (any type) is forwarded to the bot owner. Good for support/feedback.
- "fields": a multi-step form. The bot asks each question in order and sends all answers to the owner as one summary. Use for orders, registration, applications, surveys. Node "text" is the intro, fields are the questions. Use "done" for the thank-you message.
- "join": force membership: before using the bot the user must be a member of these public channels (usernames without @). Only add it if the user asks for forced/mandatory join. In "thinking" remind that the bot must be admin in that channel.
- "photo": only if the user gave an image link. Never invent image URLs.
- The engine CANNOT do: payments, databases/inventory, external APIs, scheduled messages, sending files. If the user asks for something like that, say so honestly in "thinking" and build the closest working approximation (e.g. order form that is sent to the owner instead of online payment).

Design rules:
- Think before you structure: identify the bot's real purpose, the natural user journeys, and the minimum set of nodes that cover them well. Don't pad with filler, but don't skip an obviously needed part (a shop bot needs a way to order, a business bot needs contact/support, a content bot usually needs a channel link).
- node_id: lowercase english letters, digits, underscore. Max 25 nodes, max 3 buttons per row, max 6 rows per node.
- A button has exactly one of: "goto" (an existing node_id), "url" (https only), "alert", "copy".
- Channel/group join button: {"text": "📢 عضویت در کانال", "url": "https://t.me/<username>"} (username without @). Use the username the user gave. If they gave none, use https://t.me/your_channel and say in "thinking" that the real channel id must be set via manual edit.
- Always give every node a short "title". Prefer a form ("fields") over a single "ask" when you need several pieces of info. Give ask/form nodes a cancel/home button too.
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
                elif str(b.get("alert") or "").strip():
                    r.append({"text": label, "alert": str(b["alert"]).strip()[:200]})
                elif str(b.get("copy") or "").strip():
                    r.append({"text": label, "copy": str(b["copy"]).strip()[:256]})
                else:
                    u = norm_url(b.get("url"))
                    if u:
                        r.append({"text": label, "url": u})
                    else:
                        bad(f"لینک/آیدی دکمه‌ی «{label}» معتبر نیست (باید https:// یا @آیدی باشه)")
            if r:
                rows.append(r)
        node = {"text": text, "buttons": rows, "ask": bool(n.get("ask"))}
        title = str(n.get("title") or "").strip()[:30]
        if title:
            node["title"] = title
        kb_type = str(n.get("keyboard_type") or "inline").strip().lower()
        if kb_type not in ("inline", "reply"):
            kb_type = "inline"
        node["keyboard_type"] = kb_type
        ph = str(n.get("photo") or "").strip()
        if ph:
            if ph.startswith("https://") and not re.search(r"\s", ph) and len(ph) <= 500:
                node["photo"] = ph
            else:
                bad(f"آدرس عکس بخش «{nid}» معتبر نیست (باید لینک مستقیم https باشه)")
        fl = n.get("fields")
        fl = [str(f).strip()[:200] for f in fl if str(f).strip()][:6] if isinstance(fl, list) else []
        if fl:
            node["fields"], node["ask"] = fl, False
        done = str(n.get("done") or "").strip()[:500]
        if done:
            node["done"] = done
        nxt = str(n.get("next") or "")
        if nxt:
            if nxt in valid:
                node["next"] = nxt
            else:
                bad(f"بخش بعدیِ «{nid}» وجود نداره")
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
            "$push": {"versions": {"$each": [bot["config"]], "$slice": -MAX_VERSIONS}},
            "$unset": {"last_manual": ""}})
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
    db.states.delete_many({"bot": bot_id})
    return jsonify(ok=True)


# ───────────────────────── موتور اجرای کانفیگ ─────────────────────────
def fill(t, user):
    u = user or {}
    return (t.replace("{name}", u.get("first_name") or "دوست من")
             .replace("{username}", ("@" + u["username"]) if u.get("username") else ""))


def keyboard(node, node_id):
    kb = []
    for ri, row in enumerate(node["buttons"]):
        r = []
        for ci, b in enumerate(row):
            if "url" in b:
                r.append({"text": b["text"], "url": b["url"]})
            elif "goto" in b:
                r.append({"text": b["text"], "callback_data": f"n:{b['goto']}"})
            elif "alert" in b:
                r.append({"text": b["text"], "callback_data": f"a:{node_id}:{ri}:{ci}"})
            elif "copy" in b:
                r.append({"text": b["text"], "copy_text": {"text": b["copy"]}})
            else:
                r.append({"text": b["text"]})
        if r:
            kb.append(r)
    return kb


def keyboard_markup(node, node_id):
    """Return the appropriate keyboard markup based on node's keyboard_type."""
    kb = keyboard(node, node_id)
    if node.get("keyboard_type") == "reply":
        # Reply keyboard (below chat input)
        return {"keyboard": kb, "resize_keyboard": True, "one_time_keyboard": False}
    else:
        # Inline keyboard (below message)
        return {"inline_keyboard": kb}


def send_node(token, chat_id, cfg, node_id, bot_id, user=None, edit=None):
    """edit = پیام قبلی (callback) → اگه ممکن باشه همون پیام ویرایش می‌شه، نه اینکه پیام جدید بیاد"""
    if node_id not in cfg["nodes"]:
        node_id = cfg["start"]
    node = cfg["nodes"][node_id]
    text = fill(node["text"], user)
    markup = keyboard_markup(node, node_id)
    photo = node.get("photo")
    done = False
    if edit and not photo and not edit.get("photo"):
        r = tg(token, "editMessageText", chat_id=chat_id, message_id=edit["message_id"], text=text, reply_markup=markup)
        done = bool(r.get("ok")) or "not modified" in str(r.get("description", ""))
    if not done:
        if edit:
            tg(token, "deleteMessage", chat_id=chat_id, message_id=edit["message_id"])
        if photo:
            data = {"chat_id": chat_id, "photo": photo}
            if len(text) <= 1000:
                data.update(caption=text, **({"reply_markup": markup} if kb else {}))
                done = bool(tg(token, "sendPhoto", **data).get("ok"))
            else:
                tg(token, "sendPhoto", **data)
                done = False   # متن بلند جداگونه می‌ره
        if not done:
            tg(token, "sendMessage", chat_id=chat_id, text=text, **({"reply_markup": markup} if kb else {}))
    sid = f"{bot_id}:{chat_id}"
    if node.get("fields"):
        db.states.replace_one({"_id": sid}, {"_id": sid, "form": node_id, "a": [], "t": now()}, upsert=True)
        tg(token, "sendMessage", chat_id=chat_id, text=fill(node["fields"][0], user))
    elif node.get("ask"):
        db.states.replace_one({"_id": sid}, {"_id": sid, "ask": node_id, "t": now()}, upsert=True)
    else:
        db.states.delete_one({"_id": sid})


def finish(token, chat_id, cfg, node, bot_id, user, default_done):
    tg(token, "sendMessage", chat_id=chat_id, text=fill(node.get("done") or default_done, user))
    send_node(token, chat_id, cfg, node.get("next") or cfg["start"], bot_id, user)


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
    try:
        cq = upd.get("callback_query")
        if cq:
            data, user, m = cq.get("data", ""), cq.get("from", {}), cq.get("message") or {}
            chat_id = (m.get("chat") or {}).get("id")
            if not chat_id:
                tg(token, "answerCallbackQuery", callback_query_id=cq["id"])
                return "ok"
            if not gate_ok(token, cfg, user["id"]):
                if data == "chk":
                    tg(token, "answerCallbackQuery", callback_query_id=cq["id"], text="هنوز عضو نشدی 🙂", show_alert=True)
                else:
                    tg(token, "answerCallbackQuery", callback_query_id=cq["id"])
                    send_gate(token, chat_id, cfg)
                return "ok"
            if data.startswith("a:"):
                try:
                    _, nid, ri, ci = data.split(":")
                    b = cfg["nodes"][nid]["buttons"][int(ri)][int(ci)]
                    tg(token, "answerCallbackQuery", callback_query_id=cq["id"], text=b["alert"][:200], show_alert=True)
                except Exception:
                    tg(token, "answerCallbackQuery", callback_query_id=cq["id"])
                return "ok"
            tg(token, "answerCallbackQuery", callback_query_id=cq["id"])
            if data == "chk":
                send_node(token, chat_id, cfg, cfg["start"], bot_id, user, edit=m)
            elif data.startswith("n:") and data[2:] in cfg["nodes"]:
                send_node(token, chat_id, cfg, data[2:], bot_id, user, edit=m)
            return "ok"
        msg = upd.get("message")
        if not msg or msg["chat"]["type"] != "private":
            return "ok"
        chat_id, user = msg["chat"]["id"], msg.get("from", {})
        if not gate_ok(token, cfg, user.get("id", chat_id)):
            send_gate(token, chat_id, cfg)
            return "ok"
        text = (msg.get("text") or "").strip()
        sid = f"{bot_id}:{chat_id}"
        if text.startswith("/"):
            cmd = text[1:].split()[0].split("@")[0].lower()
            if cmd == "start":
                send_node(token, chat_id, cfg, cfg["start"], bot_id, user)
            elif cmd in cfg["commands"]:
                send_node(token, chat_id, cfg, cfg["commands"][cmd], bot_id, user)
            else:
                send_node(token, chat_id, cfg, cfg["fallback"], bot_id, user)
            return "ok"
        state = db.states.find_one({"_id": sid})
        who = f"👤 {user.get('first_name', '')} (@{user.get('username', '-')}) — {user.get('id', '')}"
        if state and state.get("form") in cfg["nodes"] and cfg["nodes"][state["form"]].get("fields"):
            node = cfg["nodes"][state["form"]]
            fields = node["fields"]
            if not text:
                tg(token, "sendMessage", chat_id=chat_id, text="لطفاً جوابت رو به‌صورت متن بفرست 🙏")
                return "ok"
            ans = (state.get("a") or []) + [text[:500]]
            if len(ans) < len(fields):
                db.states.update_one({"_id": sid}, {"$set": {"a": ans}})
                tg(token, "sendMessage", chat_id=chat_id, text=fill(fields[len(ans)], user))
            else:
                db.states.delete_one({"_id": sid})
                body = "\n\n".join(f"{q}\n» {a}" for q, a in zip(fields, ans))
                tg(token, "sendMessage", chat_id=bot["owner"],
                   text=(f"📝 فرم جدید — {cfg['name']}\n{who}\n\n{body}")[:4000])
                finish(token, chat_id, cfg, node, bot_id, user, "✅ اطلاعاتت ثبت شد، ممنون!")
        elif state and state.get("ask"):
            r = tg(token, "copyMessage", chat_id=bot["owner"], from_chat_id=chat_id, message_id=msg["message_id"])
            if r.get("ok"):
                tg(token, "sendMessage", chat_id=bot["owner"], text=who)
            db.states.delete_one({"_id": sid})
            node = cfg["nodes"].get(state["ask"]) if isinstance(state["ask"], str) else None
            finish(token, chat_id, cfg, node or {}, bot_id, user, "✅ پیامت ارسال شد.")
        else:
            send_node(token, chat_id, cfg, cfg["fallback"], bot_id, user)
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
