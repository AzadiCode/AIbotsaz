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

Output ONLY one valid JSON object, no markdown fences, no comments. Top-level shape:
{
 "thinking": "...",
 "config": { ...bot config as described below... }
}

"thinking" (string, 2-5 short sentences, written in the SAME language as the user's request, natural first-person tone — like a sharp colleague briefly narrating their plan, not a formal report):
- Say what you understood the user wants.
- Name the key sections/flows you decided the bot needs and briefly why.
- If you made a judgment call or filled a gap the user didn't specify, say so.
- If this is an update to an existing bot, mention what you're changing and why, not the whole bot again.
- No headers, no bullet points, no markdown — just natural flowing sentences.

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
- Think before you structure: identify the bot's real purpose, the natural user journeys through it, and the minimum set of nodes that cover them well — don't pad with filler nodes, don't skip an obviously-needed one (e.g. a shop bot without an "order" path is incomplete).
- node_id: lowercase english letters, digits, underscore. Max 25 nodes, max 3 buttons per row, max 6 rows per node.
- A button has either "goto" (an existing node_id) or "url" (https only).
- If "ask" is true, the node's text asks the user something and their next message is delivered to the bot owner (use for contact, orders, feedback, support).
- Every "goto", "start", "fallback" and command target MUST exist in nodes. Add a back/home button on non-start nodes.
- Write all user-facing text in the same language as the user's request (default Persian). Use emojis moderately.
- When an existing config is given, apply the user's change to it precisely and return the FULL updated config, keeping everything else intact.
- Plain text only, no Markdown/HTML formatting characters in node texts."""

ID_RE = re.compile(r"^[a-z0-9_]{1,30}$")
CMD_RE = re.compile(r"^[a-z0-9_]{1,30}$")


def sanitize(cfg):
    if not isinstance(cfg, dict) or not isinstance(cfg.get("nodes"), dict):
        raise ValueError("ساختار خروجی معتبر نیست")
    nodes_in = cfg["nodes"]
    if not (1 <= len(nodes_in) <= 25):
        raise ValueError("تعداد بخش‌ها نامعتبر است")
    nodes = {}
    for nid, n in nodes_in.items():
        if not ID_RE.match(str(nid)) or not isinstance(n, dict):
            raise ValueError("شناسه‌ی بخش نامعتبر است")
        text = str(n.get("text", "")).strip()[:3500]
        if not text:
            raise ValueError(f"بخش {nid} متن ندارد")
        rows = []
        for row in (n.get("buttons") or [])[:6]:
            r = []
            for b in (row if isinstance(row, list) else [row])[:3]:
                if not isinstance(b, dict) or not str(b.get("text", "")).strip():
                    continue
                btn = {"text": str(b["text"]).strip()[:40]}
                if b.get("goto"):
                    btn["goto"] = str(b["goto"])
                elif str(b.get("url", "")).startswith("https://"):
                    btn["url"] = str(b["url"])[:500]
                else:
                    continue
                r.append(btn)
            if r:
                rows.append(r)
        nodes[nid] = {"text": text, "buttons": rows, "ask": bool(n.get("ask"))}

    def ref(x):
        x = str(x or "")
        if x not in nodes:
            raise ValueError(f"ارجاع به بخش ناموجود: {x}")
        return x

    for n in nodes.values():
        for row in n["buttons"]:
            for b in row:
                if "goto" in b:
                    ref(b["goto"])
    start = ref(cfg.get("start"))
    fallback = str(cfg.get("fallback") or start)
    fallback = fallback if fallback in nodes else start
    cmds = {}
    for k, v in (cfg.get("commands") or {}).items():
        k = str(k).lstrip("/").lower()
        if CMD_RE.match(k) and str(v) in nodes and k != "start":
            cmds[k] = str(v)
    return {"name": str(cfg.get("name") or "ربات من")[:50], "start": start,
            "fallback": fallback, "commands": cmds, "nodes": nodes}


def _call_llm(user):
    r = requests.post(
        f"{AI_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {AI_API_KEY}"},
        json={"model": AI_MODEL, "max_tokens": 3500, "temperature": 0.4,
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
    thinking = str(raw.get("thinking") or "").strip()[:900]
    return thinking, sanitize(raw["config"])


def ask_llm(prompt, current=None):
    user = prompt
    if current:
        user = f"Current config:\n{json.dumps(current, ensure_ascii=False)}\n\nChange request:\n{prompt}"
    try:
        return _call_llm(user)
    except (ValueError, KeyError, TypeError):   # خروجی خراب → یک بار دیگه
        log.warning("bad AI output, retrying once", exc_info=True)
        return _call_llm(user)


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
    return jsonify(bot=public(db.bots.find_one({"_id": bot["_id"]})))


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
