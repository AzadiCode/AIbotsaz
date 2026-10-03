# -*- coding: utf-8 -*-
"""
Super BotMaker — ابر رباتساز هوشمند
Flask + MongoDB + MiniApp
- Token economy (توکن مصرفی برای ساخت/ارتقا با AI)
- Referral + Daily bonus + Shop (stub)
- Media upload (photo/video/voice/audio/document) + engine support
- Safe fixed engine (no generated code execution)
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

# ── Env ──
MOTHER_TOKEN = os.environ["MOTHER_TOKEN"]
MONGO_URI    = os.environ.get("MONGO_URI", "").strip()
BASE_URL     = os.environ["BASE_URL"].rstrip("/")
AI_BASE_URL  = re.sub(r"/chat/completions/?$", "", os.environ["AI_BASE_URL"].strip().rstrip("/"))
AI_API_KEY   = os.environ["AI_API_KEY"]
AI_MODEL     = os.environ["AI_MODEL"]
SECRET_KEY   = os.environ.get("SECRET_KEY", MOTHER_TOKEN)
DAILY_LIMIT  = int(os.environ.get("DAILY_LIMIT", "20"))
MAX_BOTS     = int(os.environ.get("MAX_BOTS", "5"))
AI_MAX_TOKENS = int(os.environ.get("AI_MAX_TOKENS", "6000"))
DEBUG        = os.environ.get("DEBUG", "") == "1"
MAX_PROMPT   = 2000
MAX_VERSIONS = 8
MAX_NODES    = 40

# ── Token economy ──
NEW_USER_TOKENS = int(os.environ.get("NEW_USER_TOKENS", "40"))
GENERATE_COST   = int(os.environ.get("GENERATE_COST", "12"))
UPGRADE_COST    = int(os.environ.get("UPGRADE_COST", "8"))
REFERRAL_BONUS  = int(os.environ.get("REFERRAL_BONUS", "25"))
DAILY_BONUS     = int(os.environ.get("DAILY_BONUS", "10"))
MOTHER_USERNAME = os.environ.get("MOTHER_USERNAME", "").strip().lstrip("@")
ADMIN_IDS       = {int(x) for x in os.environ.get("ADMIN_IDS", "").replace(",", " ").split() if x.strip().lstrip("-").isdigit()}

# ── Media ──
MEDIA_DIR = Path(os.environ.get("MEDIA_DIR", str(Path(__file__).parent / "media")))
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
MAX_MEDIA_MB = int(os.environ.get("MAX_MEDIA_MB", "20"))
MAX_MEDIA_BYTES = MAX_MEDIA_MB * 1024 * 1024
ALLOWED_EXT = {"jpg","jpeg","png","webp","gif","mp4","mov","m4a","mp3","ogg","oga","wav","pdf","zip","txt"}
MEDIA_KINDS = ("photo", "video", "animation", "voice", "audio", "document")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("superbot")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_MEDIA_BYTES + 1024 * 1024
if MONGO_URI:
    db = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000).get_database("aibot")
else:
    import mongomock
    db = mongomock.MongoClient().get_database("aibot")
    log.warning("MONGO_URI empty — using volatile memory")
db.bots.create_index("owner")
db.bots.create_index("token_hash", unique=True, sparse=True)

fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest()))
MOTHER_SECRET = hashlib.sha256(("mother" + SECRET_KEY).encode()).hexdigest()[:32]

# ── Telegram helper ──
def tg(token, method, **data):
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=data, timeout=20)
        return r.json()
    except Exception as e:
        log.warning("tg %s failed: %s", method, e)
        return {"ok": False, "description": str(e)}

def now():
    return datetime.now(timezone.utc)

def enc(s):  return fernet.encrypt(s.encode()).decode()
def dec(s):  return fernet.decrypt(s.encode()).decode()
def thash(t): return hashlib.sha256(t.encode()).hexdigest()

# ── Auth ──
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

# ═════════ Token economy ═════════
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
    """True if deducted."""
    r = db.users.find_one_and_update({"_id": uid, "tokens": {"$gte": amount}},
                                     {"$inc": {"tokens": -amount, "total_spent": amount}})
    if r is None:
        # maybe user doc missing (first run) — create then retry
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
    """code may be 'r_123' or '123'. Returns message."""
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
        # create referrer shell so link never dies (they get bonus when they arrive)
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

def public(b):
    return {
        "id": str(b["_id"]), "name": b.get("name", ""), "active": b.get("active", False),
        "username": b.get("username"), "config": b.get("config"),
        "versions": len(b.get("versions", [])), "updated": b["updated"].isoformat(),
        "thinking": b.get("thinking", ""),
    }

def sync_commands(bot, cfg):
    if bot.get("active") and bot.get("token_enc"):
        tg(dec(bot["token_enc"]), "setMyCommands", commands=[{"command": "start", "description": "Start"}] + [
            {"command": c, "description": c} for c in cfg["commands"]])

# ── Daily quota (anti-spam, alongside tokens) ──
def quota_key(uid):
    return f"{uid}:{now():%Y-%m-%d}"

def quota_take(uid):
    try:
        db.usage.find_one_and_update({"_id": quota_key(uid), "n": {"$lt": DAILY_LIMIT}},
                                     {"$inc": {"n": 1}}, upsert=True)
        return True
    except DuplicateKeyError:
        return False

def quota_refund(uid):
    db.usage.update_one({"_id": quota_key(uid)}, {"$inc": {"n": -1}})

def quota_left(uid):
    d = db.usage.find_one({"_id": quota_key(uid)})
    return max(0, DAILY_LIMIT - (d["n"] if d else 0))

# ═════════ AI ═════════
SYSTEM_PROMPT = """You design Telegram bots as a JSON config that a fixed, safe engine executes. You think like a senior product designer AND a bot-logic engineer.

LANGUAGE RULE (strict, highest priority): the request states the OUTPUT LANGUAGE. Write "thinking" and EVERY user-facing text (node texts, button labels, bot name) in that language. If it says Persian, write natural Persian and NEVER English, even though JSON keys, node_ids and variable names are English.

Output ONLY one valid JSON object, no markdown fences, no comments. Top-level shape:
{"thinking": "...", "config": {...}}

"thinking" (2-5 short sentences, OUTPUT LANGUAGE, first-person, sharp colleague tone):
- What you understood, key flows and why. Mention variables/conditions in one sentence. Mention placeholders the user can edit via manual edit. If update, mention only what changed.

"config" schema:
{"name": "short bot name", "start": "<node_id>", "fallback": "<node_id>",
 "commands": {"help": "<node_id>"},
 "join": {"channels": ["channel_username"], "text": "message asking to join"},
 "vars": {"coins": "0"},
 "nodes": {"<node_id>": {
   "title": "short label max 30 chars, OUTPUT LANGUAGE",
   "text": "message text (may contain {placeholders})",
   "media": {"kind": "photo|video|animation|voice|audio|document", "url": "https://..."},
   "buttons": [[{"text":"label","goto":"<node_id>"},{"text":"label","url":"https://..."},{"text":"label","alert":"popup"},{"text":"label","copy":"text"}]],
   "ask": false, "kb": "reply", "fields": ["Q1?"], "save": ["city"], "types": ["text"],
   "silent": false, "done": "thank-you", "next": "<node_id>",
   "do": [...], "route": [{"when": cond, "goto": "<node_id>"}], "alt": [{"when": cond, "text": "..."}]}}}

Buttons: goto / url / alert / copy. ask=true forwards next message to owner. fields=multi-step form (answers sent to owner). join=forced membership (usernames without @, only if requested). kb=reply shows buttons under chat input. media: ONLY include if user gave a media link, else omit entirely. Never invent media URLs.

VARIABLES: per-user storage. Name: lowercase english, max 20 chars, max 20 vars, declare in vars. {var} and {var|fallback} in texts/buttons/alerts. Built-ins (read-only): {name} {first_name} {last_name} {full_name} {username} {id} {lang} {premium} {is_owner} {bot_name} {bot_username} {text} {param} {visits} {date} {time} {hour} {weekday}.
CONDITIONS: {"var":"coins","op":">=","value":"10"}, ops == != > >= < <= contains empty filled. Combine all/any/not, max depth 3.
ACTIONS (max 6): set/add/clear/random/notify. notify sends message to owner.
node do runs on enter; route = first-true switch (max 5, max 5 hops, no loops); alt = first-true text replacement (max 4); button when = visibility cond; button do on goto/alert buttons.
FORMS: save same length as fields; types text/number/phone/email; silent=true skips owner copy.
Use logic only when genuinely better (points, quiz, memory, visits, hours, owner menu, lang, param, premium). Simple request = simple bot.
LIMITS: NO payments, inventory, APIs, schedules, shared-between-users counters. Approximate (order form -> sent to owner).
Design: min nodes covering real journeys; node_id lowercase; max 40 nodes, 3 btns/row, 6 rows; one action key per button; channel button url https://t.me/<username>; every node title; forms over ask for multi-info; every goto/start/fallback/next/route/command exists; every node reachable; no dead ends (back/home or next/route); short labels; placeholders like [price]; moderate emojis; preserve untouched nodes on update; plain text only."""

ID_RE = re.compile(r"^[a-z0-9_]{1,30}$")
CMD_RE = re.compile(r"^[a-z0-9_]{1,30}$")
TG_NAME_RE = re.compile(r"^@?[A-Za-z][A-Za-z0-9_]{4,31}$")
VAR_RE = re.compile(r"^[a-z][a-z0-9_]{0,19}$")
PH_RE = re.compile(r"\{([a-z][a-z0-9_]{0,19})(?:\|([^{}]{0,60}))?\}")
MAX_VARS = 20
MAX_HOPS = 5
BUILTINS = ("name", "first_name", "last_name", "full_name", "username", "id", "lang", "premium", "is_owner",
            "bot_name", "bot_username", "text", "param", "visits", "date", "time", "hour", "weekday")
OPS = ("==", "!=", ">", ">=", "<", "<=", "contains", "empty", "filled")
OP_ALIASES = {"=": "==", "eq": "==", "ne": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
ACT_OPS = ("set", "add", "clear", "random", "notify")
F_TYPES = ("text", "number", "phone", "email")
_DIG = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

def norm_url(v):
    v = str(v or "").strip()
    if TG_NAME_RE.match(v):
        return "https://t.me/" + v.lstrip("@")
    if re.match(r"^(t\.me|telegram\.me)/", v, re.I):
        v = "https://" + v
    if v.startswith("https://") and len(v) > 12 and not re.search(r"\s", v):
        return v[:1000]
    # allow relative /media/ urls (uploaded files) — expand to absolute
    if v.startswith("/media/") and len(v) < 200 and not re.search(r"\s", v):
        return (BASE_URL + v)[:1000]
    return None

def to_num(s):
    try:
        x = float(str(s).translate(_DIG).replace(",", "").replace("٫", ".").strip())
    except (ValueError, TypeError):
        return None
    return x if math.isfinite(x) else None

def fmt_num(x):
    x = max(-1e12, min(1e12, x))
    return str(int(x)) if x == int(x) else ("%.6f" % x).rstrip("0").rstrip(".")

def clean_cond(c, used, nums, bad, depth=0):
    if not isinstance(c, dict) or depth > 3:
        bad("invalid condition"); return None
    for key in ("all", "any"):
        if isinstance(c.get(key), list):
            subs = [x for x in (clean_cond(s, used, nums, bad, depth + 1) for s in c[key][:6]) if x]
            return {key: subs} if subs else None
    if "not" in c:
        s = clean_cond(c["not"], used, nums, bad, depth + 1)
        return {"not": s} if s else None
    name = str(c.get("var") or "").strip().lower()
    op = OP_ALIASES.get(str(c.get("op") or "==").strip(), str(c.get("op") or "==").strip())
    if not (name in BUILTINS or VAR_RE.match(name)):
        bad(f"bad variable in condition: {name}"); return None
    if op not in OPS:
        bad(f"bad operator: {op}"); return None
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
            bad(f"bad action: {op}"); continue
        if op == "notify":
            v = str(a.get("value") or "").strip()[:500]
            if v:
                out.append({"op": "notify", "value": v})
            else:
                bad("empty notify")
            continue
        name = str(a.get("var") or "").strip().lower()
        if not VAR_RE.match(name) or name in BUILTINS:
            bad(f"bad action var: {name}"); continue
        item = {"op": op, "var": name}
        if op != "clear":
            v = str(a.get("value", "")).strip()[:100]
            if op == "add":
                if v == "":
                    v = "1"
                elif to_num(v) is None and not PH_RE.search(v):
                    bad(f"add value must be number: {name}"); continue
            elif op == "random":
                m = re.fullmatch(r"(\d{1,9})\s*-\s*(\d{1,9})", v.translate(_DIG))
                if not m or int(m.group(1)) > int(m.group(2)):
                    bad(f"bad random range: {name}"); continue
                v = f"{int(m.group(1))}-{int(m.group(2))}"
            item["value"] = v
        used.add(name)
        if op in ("add", "random"):
            nums.add(name)
        out.append(item)
    return out

def clean_media(m, bad):
    if not isinstance(m, dict):
        return None
    kind = str(m.get("kind") or "photo").strip().lower()
    if kind not in MEDIA_KINDS:
        kind = "photo"
    u = norm_url(m.get("url"))
    if not u:
        bad("media url invalid (must be https or uploaded file)")
        return None
    return {"kind": kind, "url": u}

def sanitize(cfg, strict=False):
    if not isinstance(cfg, dict) or not isinstance(cfg.get("nodes"), dict):
        raise ValueError("bad structure")
    nodes_in = cfg["nodes"]
    if not (1 <= len(nodes_in) <= MAX_NODES):
        raise ValueError(f"nodes must be 1..{MAX_NODES}")
    def bad(msg):
        if strict:
            raise ValueError(msg)
    used, nums = set(), set()
    valid = {}
    for nid, n in nodes_in.items():
        nid = str(nid)
        if not ID_RE.match(nid) or not isinstance(n, dict):
            bad("bad section id"); continue
        text = str(n.get("text", "")).strip()[:3500]
        if not text:
            bad(f"section '{nid}' has no text"); continue
        valid[nid] = (n, text)
    if not valid:
        raise ValueError("no valid sections")
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
                    bad(f"section '{nid}' has button without label"); continue
                it = None
                g = str(b.get("goto") or "")
                if g:
                    if g in valid:
                        it = {"text": label, "goto": g}
                    else:
                        bad(f"button '{label}' points nowhere")
                elif str(b.get("alert") or "").strip():
                    it = {"text": label, "alert": str(b["alert"]).strip()[:200]}
                elif str(b.get("copy") or "").strip():
                    it = {"text": label, "copy": str(b["copy"]).strip()[:256]}
                else:
                    u = norm_url(b.get("url"))
                    if u:
                        it = {"text": label, "url": u}
                    else:
                        bad(f"button '{label}' link invalid")
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
                        bad(f"actions only on goto/alert buttons ('{label}')")
                r.append(it)
            if r:
                rows.append(r)
        node = {"text": text, "buttons": rows, "ask": bool(n.get("ask"))}
        title = str(n.get("title") or "").strip()[:30]
        if title:
            node["title"] = title
        # media (new) + legacy photo
        m = clean_media(n.get("media"), bad) if n.get("media") else None
        if not m and str(n.get("photo") or "").strip():
            u = norm_url(n.get("photo"))
            if u:
                m = {"kind": "photo", "url": u}
            else:
                bad(f"photo url invalid in '{nid}'")
        if m:
            node["media"] = m
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
                    bad(f"bad save var '{v}'"); v = ""
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
            node["kb"] = "reply"
        done = str(n.get("done") or "").strip()[:500]
        if done:
            node["done"] = done
        nxt = str(n.get("next") or "")
        if nxt:
            if nxt in valid:
                node["next"] = nxt
            else:
                bad(f"next of '{nid}' missing")
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
                bad(f"bad route rule in '{nid}'")
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
                bad(f"bad alt text in '{nid}'")
        if alt:
            node["alt"] = alt
        nodes[nid] = node
    start = str(cfg.get("start") or "")
    if start not in nodes:
        bad("bad start"); start = next(iter(nodes))
    fallback = str(cfg.get("fallback") or start)
    if fallback not in nodes:
        bad("bad fallback"); fallback = start
    cmds = {}
    for k, v in (cfg.get("commands") or {}).items():
        k = str(k).lstrip("/").lower()
        if not CMD_RE.match(k) or k == "start" or str(v) not in nodes:
            bad(f"bad command /{k}"); continue
        cmds[k] = str(v)
    out = {"name": str(cfg.get("name") or "My Bot").strip()[:50] or "My Bot",
           "start": start, "fallback": fallback, "commands": cmds, "nodes": nodes}
    declared = {}
    dv = cfg.get("vars")
    for k, v in (dv.items() if isinstance(dv, dict) else []):
        k = str(k).strip().lower()
        if VAR_RE.match(k) and k not in BUILTINS:
            declared[k] = str(v if v is not None else "")[:100]
        else:
            bad(f"bad var name '{k}'")
    for k in sorted(used):
        declared.setdefault(k, "0" if k in nums else "")
    if len(declared) > MAX_VARS:
        if strict:
            raise ValueError(f"max {MAX_VARS} variables")
        declared = dict(list(declared.items())[:MAX_VARS])
    if declared:
        out["vars"] = declared
    j = cfg.get("join")
    if isinstance(j, dict):
        chans = []
        raw = j.get("channels")
        for c in (raw if isinstance(raw, list) else [])[:3]:
            c = re.sub(r"^(https?://)?(t\.me|telegram\.me)/", "", str(c).strip(), flags=re.I).lstrip("@")
            if re.match(r"^[A-Za-z][A-Za-z0-9_]{4,31}$", c):
                chans.append(c)
            else:
                bad(f"bad channel '{c}'")
        if chans:
            out["join"] = {"channels": chans,
                           "text": str(j.get("text") or "Please join to use this bot").strip()[:500]}
    return out

def _count(s):
    return len(re.findall(r"[\u0600-\u06FF]", s)), len(re.findall(r"[A-Za-z]", s))

def detect_lang(s):
    fa, la = _count(s)
    return "fa" if fa >= la else "other"

class ThinkLang(ValueError):
    def __init__(self, cfg):
        super().__init__("thinking language mismatch")
        self.cfg = cfg

FALLBACK_THINKING = "Bot designed from your description. Tweak text, buttons or channel ids via Manual edit."

def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)

def lint(cfg):
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
        out.append("unreachable nodes: " + ", ".join(lost[:6]))
    dead = [i for i, n in nodes.items() if i in seen and i != cfg["start"] and not n.get("fields") and not n.get("ask")
            and not n.get("route") and not n.get("next") and not any("goto" in b for row in n["buttons"] for b in row)]
    if dead:
        out.append("dead-end nodes (add back/home button): " + ", ".join(dead[:6]))
    return out

def _call_llm(user, lang, final):
    r = requests.post(f"{AI_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {AI_API_KEY}"},
        json={"model": AI_MODEL, "max_tokens": AI_MAX_TOKENS, "temperature": 0.4,
              "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                           {"role": "user", "content": user}]}, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"AI HTTP {r.status_code}: {r.text[:300]}")
    try:
        txt = r.json()["choices"][0]["message"]["content"] or ""
    except Exception:
        raise RuntimeError(f"AI bad response: {r.text[:300]}")
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S)
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError(f"AI returned no JSON: {txt[:200]!r}")
    raw = json.loads(m.group(0))
    if not isinstance(raw, dict) or not isinstance(raw.get("config"), dict):
        raise ValueError("AI response missing config")
    cfg = sanitize(raw["config"])
    thinking = str(raw.get("thinking") or "").strip()[:900]
    if lang == "fa":
        fa, la = _count(thinking)
        if not thinking or la > fa:
            if not final:
                raise ThinkLang(cfg)
            thinking = "ربات را طبق توضیحت طراحی کردم. متن یا دکمه‌ای نیاز به تغییر داشت از ویرایش دستی درستش کن."
    return thinking, cfg

def build_user(prompt, current, lang, note_extra=""):
    note = ("OUTPUT LANGUAGE: Persian. thinking and all texts in Persian." if lang == "fa"
            else "OUTPUT LANGUAGE: same as user request.")
    if note_extra:
        note += " " + note_extra
    parts = [note]
    if current:
        parts += ["Current config:\n" + json.dumps(current, ensure_ascii=False), "Change request:\n" + prompt]
    else:
        parts += ["Bot request:\n" + prompt]
    return "\n\n".join(parts)

def ask_llm(prompt, current=None):
    lang = detect_lang(prompt)
    best, last, feedback = None, None, ""
    for attempt in (0, 1):
        try:
            thinking, cfg = _call_llm(build_user(prompt, current, lang, feedback), lang, final=attempt == 1)
        except ThinkLang as e:
            best, last = best or (None, e.cfg), e
            feedback = "(Previous thinking used wrong language. Fix it.)"
            continue
        except (ValueError, KeyError, TypeError) as e:
            last = e
            feedback = f"(Previous reply rejected: {str(e)[:200]}. Return one valid JSON.)"
            continue
        problems = lint(cfg)
        if problems and attempt == 0:
            best = (thinking, cfg)
            feedback = "(Fix logic problems, return FULL config: " + "; ".join(problems[:6]) + ")"
            continue
        return thinking, cfg
    if best:
        th, cfg = best
        return (th or FALLBACK_THINKING), cfg
    raise last

# ═════════ MiniApp API ═════════
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
        return jsonify(error="file missing"), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify(error="file missing"), 400
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_EXT:
        return jsonify(error=f"format not supported (max {MAX_MEDIA_MB}MB)"), 400
    data = f.read()
    if len(data) > MAX_MEDIA_BYTES:
        return jsonify(error=f"file too large (max {MAX_MEDIA_MB}MB)"), 400
    if len(data) < 16:
        return jsonify(error="empty file"), 400
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
    return jsonify(
        bots=bots, quota=quota_left(uid), limit=DAILY_LIMIT, max_bots=MAX_BOTS,
        joined=u["created"].isoformat(),
        tokens=u.get("tokens", 0), total_spent=u.get("total_spent", 0),
        referrals=u.get("referrals", 0),
        referral_link=referral_link(uid), referral_code=f"r_{uid}",
        daily_claimable=(u.get("daily") != today),
        costs={"build": GENERATE_COST, "upgrade": UPGRADE_COST,
               "daily": DAILY_BONUS, "referral": REFERRAL_BONUS},
        level=level_of(len(bots), u.get("total_spent", 0)),
    )

@app.post("/api/generate")
def api_generate():
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    body = request.get_json(silent=True) or {}
    prompt = str(body.get("prompt", "")).strip()[:MAX_PROMPT]
    if len(prompt) < 5:
        return jsonify(error="Describe your bot in more detail"), 400
    bot = None
    is_upgrade = False
    if body.get("bot_id"):
        bot = get_bot(body["bot_id"], uid)
        if not bot:
            return jsonify(error="bot not found"), 404
        is_upgrade = True
    elif db.bots.count_documents({"owner": uid}) >= MAX_BOTS:
        return jsonify(error=f"max {MAX_BOTS} bots"), 400
    cost = UPGRADE_COST if is_upgrade else GENERATE_COST
    u = get_user(uid)
    if u.get("tokens", 0) < cost:
        return jsonify(error="not_enough_tokens", need=cost, have=u.get("tokens", 0)), 402
    if not quota_take(uid):
        return jsonify(error="daily limit reached, try tomorrow"), 429
    if not spend_tokens(uid, cost, "generate" if not is_upgrade else "upgrade"):
        quota_refund(uid)
        return jsonify(error="not_enough_tokens", need=cost, have=get_user(uid).get("tokens", 0)), 402
    # optional media hint attached to prompt
    media_hint = ""
    mh = body.get("media")
    if isinstance(mh, dict) and mh.get("url"):
        media_hint = f" The user uploaded a {mh.get('kind','photo')} for the start screen: {mh['url']}. Attach it as start node media."
    try:
        thinking, cfg = ask_llm(prompt + media_hint, bot["config"] if bot else None)
    except Exception as e:
        add_tokens(uid, cost, "refund:generate_failed")
        quota_refund(uid)
        log.exception("generate failed")
        msg = "Build failed, simplify the description and retry"
        if DEBUG:
            msg += f" [{type(e).__name__}] {str(e)[:300]}"
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

@app.post("/api/bots/<bot_id>/undo")
def api_undo(bot_id):
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    bot = get_bot(bot_id, uid)
    if not bot or not bot.get("versions"):
        return jsonify(error="no previous version"), 400
    prev = bot["versions"][-1]
    db.bots.update_one({"_id": bot["_id"]}, {
        "$set": {"config": prev, "name": prev["name"], "thinking": "", "updated": now()},
        "$pop": {"versions": 1}})
    bot = db.bots.find_one({"_id": bot["_id"]})
    sync_commands(bot, bot["config"])
    return jsonify(bot=public(bot))

@app.put("/api/bots/<bot_id>/config")
def api_save_config(bot_id):
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="bot not found"), 404
    try:
        cfg = sanitize((request.get_json(silent=True) or {}).get("config"), strict=True)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    if cfg != bot["config"]:
        lm = bot.get("last_manual")
        recent = lm and (now().replace(tzinfo=None) - lm.replace(tzinfo=None)).total_seconds() < 180
        upd = {"$set": {"config": cfg, "name": cfg["name"], "thinking": "", "updated": now(), "last_manual": now()}}
        if not recent:
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
        return jsonify(error="bot not found"), 404
    token = str((request.get_json(silent=True) or {}).get("token", "")).strip()
    if not re.match(r"^\d{6,12}:[\w-]{30,50}$", token):
        return jsonify(error="bad token format"), 400
    me = tg(token, "getMe")
    if not me.get("ok"):
        return jsonify(error="invalid token"), 400
    th = thash(token)
    if db.bots.find_one({"token_hash": th, "_id": {"$ne": bot["_id"]}}):
        return jsonify(error="token already used"), 400
    r = tg(token, "setWebhook", url=f"{BASE_URL}/hook/{bot_id}", secret_token=bot["secret"],
           allowed_updates=["message", "callback_query"], drop_pending_updates=True)
    if not r.get("ok"):
        return jsonify(error="webhook failed"), 502
    tg(token, "setMyCommands", commands=[{"command": "start", "description": "Start"}] + [
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
        return jsonify(error="bot not found"), 404
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
        return jsonify(error="bot not found"), 404
    if bot.get("token_enc"):
        tg(dec(bot["token_enc"]), "deleteWebhook")
    db.bots.delete_one({"_id": bot["_id"]})
    db.states.delete_many({"_id": {"$regex": f"^{bot_id}:"}})
    db.rk.delete_many({"_id": {"$regex": f"^{bot_id}:"}})
    db.uvars.delete_many({"_id": {"$regex": f"^{bot_id}:"}})
    return jsonify(ok=True)

# ── Token endpoints ──
@app.post("/api/tokens/claim-daily")
def api_daily():
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    today = now().strftime("%Y-%m-%d")
    u = get_user(uid)
    if u.get("daily") == today:
        return jsonify(error="already claimed"), 400
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
        return jsonify(error="enter invite code"), 400
    res = apply_referral(uid, code)
    if res == "ok":
        try:
            ref = int(code.strip().lstrip("r_"))
            if ref in ADMIN_IDS or True:
                pass
        except Exception:
            pass
        return jsonify(ok=True, bonus=REFERRAL_BONUS, tokens=get_user(uid)["tokens"])
    if res == "already":
        return jsonify(error="referral already used"), 400
    return jsonify(error="invalid code"), 400

SHOP = [
    {"id": "s50", "tokens": 60, "title": "Starter pack", "desc": "60 tokens"},
    {"id": "s150", "tokens": 170, "title": "Maker pack", "desc": "170 tokens · popular"},
    {"id": "s400", "tokens": 450, "title": "Pro pack", "desc": "450 tokens · best value"},
]

@app.get("/api/tokens/shop")
def api_shop():
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    return jsonify(plans=SHOP, note="To buy, contact the admin. Payment gateway plug-in point: /api/tokens/buy")

@app.post("/api/tokens/buy")
def api_buy():
    uid = auth()
    if not uid:
        return jsonify(error="unauthorized"), 401
    pid = str((request.get_json(silent=True) or {}).get("plan", ""))
    plan = next((p for p in SHOP if p["id"] == pid), None)
    if not plan:
        return jsonify(error="unknown plan"), 400
    db.orders.insert_one({"uid": uid, "plan": pid, "tokens": plan["tokens"], "status": "pending", "t": now()})
    for a in ADMIN_IDS:
        try:
            tg(MOTHER_TOKEN, "sendMessage", chat_id=a,
               text=f"Buy request: user {uid} wants {plan['title']} ({plan['tokens']} tokens)")
        except Exception:
            pass
    return jsonify(ok=True, msg="Request sent. Tokens arrive after admin approval.")

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

# ═════════ Engine ═════════
_WEEK = {5: "شنبه", 6: "یکشنبه", 0: "دوشنبه", 1: "سه‌شنبه", 2: "چهارشنبه", 3: "پنجشنبه", 4: "جمعه"}
FORM_HINT = {"number": "Send digits only", "phone": "Send a valid phone, e.g. 09123456789", "email": "Send a valid email"}

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
        self._now = now() + timedelta(hours=3, minutes=30)

    def builtin(self, k):
        u = self.user
        if k == "name":
            return u.get("first_name") or "friend"
        if k == "first_name":
            return u.get("first_name") or ""
        if k == "last_name":
            return u.get("last_name") or ""
        if k == "full_name":
            return " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x) or "friend"
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
    declared = env.cfg.get("vars") or {}
    def rep(m):
        k = m.group(1)
        if k in BUILTINS or k in declared:
            v = env.get(k)
            return v if (v != "" or m.group(2) is None) else m.group(2)
        return m.group(0)
    return PH_RE.sub(rep, str(t))

def check(cond, env, depth=0):
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
    return f"User {u.get('first_name', '')} (@{u.get('username', '-')}) — {env.uid}"

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
            tg(env.token, "sendMessage", chat_id=env.owner,
               text=f"Update from {env.cfg.get('name', '')}\n{val}\n\n{who(env)}"[:4000])

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
    rows = [[{"text": fill(b["text"], env)[:64] or "·"} for b in row if visible(b, env)] for row in node["buttons"]]
    return {"keyboard": [r for r in rows if r], "resize_keyboard": True, "is_persistent": True}

def clear_reply_kb(env):
    if not db.rk.find_one({"_id": env.sid}):
        return
    r = tg(env.token, "sendMessage", chat_id=env.chat_id, text=".", reply_markup={"remove_keyboard": True})
    mid = (r.get("result") or {}).get("message_id")
    if mid:
        tg(env.token, "deleteMessage", chat_id=env.chat_id, message_id=mid)
    db.rk.delete_one({"_id": env.sid})

MEDIA_SEND = {"photo": "sendPhoto", "video": "sendVideo", "animation": "sendAnimation",
              "voice": "sendVoice", "audio": "sendAudio", "document": "sendDocument"}
MEDIA_FIELD = {"photo": "photo", "video": "video", "animation": "animation",
               "voice": "voice", "audio": "audio", "document": "document"}

def send_media_message(token, chat_id, media, caption, markup):
    kind = media.get("kind", "photo")
    method = MEDIA_SEND.get(kind, "sendPhoto")
    field = MEDIA_FIELD.get(kind, "photo")
    cap = (caption or "")[:1024]
    data = {"chat_id": chat_id, field: media["url"]}
    if cap:
        data["caption"] = cap
    if markup:
        data["reply_markup"] = markup
    r = tg(token, method, **data)
    return bool(r.get("ok"))

def send_node(env, node_id, edit=None, depth=0):
    cfg, token, chat_id = env.cfg, env.token, env.chat_id
    if node_id not in cfg["nodes"]:
        node_id = cfg["start"]
    node = cfg["nodes"][node_id]
    run_actions(node.get("do"), env)
    if depth < MAX_HOPS:
        for rule in node.get("route", []):
            if rule["goto"] in cfg["nodes"] and check(rule["when"], env):
                return send_node(env, rule["goto"], edit=edit, depth=depth + 1)
    text = node["text"]
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
    media = node.get("media")
    done = False
    if media and not edit:
        try:
            if len(text) <= 1024:
                done = send_media_message(token, chat_id, media, text, markup if kb else None)
            else:
                done = send_media_message(token, chat_id, media, "", markup if kb else None)
                if done:
                    tg(token, "sendMessage", chat_id=chat_id, text=text,
                       **({"reply_markup": markup} if kb else {}))
                    done = True
                else:
                    tg(token, "sendMessage", chat_id=chat_id, text=text,
                       **({"reply_markup": markup} if kb else {}))
                    done = True
        except Exception:
            log.exception("media send failed")
            done = False
        if not done:
            tg(token, "sendMessage", chat_id=chat_id, text=text, **({"reply_markup": markup} if kb else {}))
            done = True
    else:
        if edit and not use_reply and not media and not edit.get("photo"):
            r = tg(token, "editMessageText", chat_id=chat_id, message_id=edit["message_id"], text=text, reply_markup=markup)
            done = bool(r.get("ok")) or "not modified" in str(r.get("description", ""))
        if not done:
            if edit:
                tg(token, "deleteMessage", chat_id=chat_id, message_id=edit["message_id"])
            if media:
                # callback navigation onto media node: send fresh (can't edit media->text reliably)
                if not send_media_message(token, chat_id, media, text[:1024] if len(text) <= 1024 else "", markup if kb else None):
                    tg(token, "sendMessage", chat_id=chat_id, text=text, **({"reply_markup": markup} if kb else {}))
                if len(text) > 1024:
                    tg(token, "sendMessage", chat_id=chat_id, text=text, **({"reply_markup": markup} if kb else {}))
            else:
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
                   reply_markup={"inline_keyboard": [[{"text": "Copy", "copy_text": {"text": c}}]]})
            elif "url" in b:
                tg(env.token, "sendMessage", chat_id=env.chat_id, text="Open:",
                   reply_markup={"inline_keyboard": [[{"text": fill(b["text"], env)[:64], "url": b["url"]}]]})
            return True
    return False

def finish(env, node, default_done):
    tg(env.token, "sendMessage", chat_id=env.chat_id, text=fill(node.get("done") or default_done, env))
    send_node(env, node.get("next") or env.cfg["start"])

def valid_answer(kind, t):
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
    kb = [[{"text": f"@{c}", "url": f"https://t.me/{c}"}] for c in j["channels"]]
    kb.append([{"text": "Joined", "callback_data": "chk"}])
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
                    tg(token, "answerCallbackQuery", callback_query_id=cq["id"], text="Not joined yet", show_alert=True)
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
                       text="Not available", show_alert=True)
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
                tg(token, "sendMessage", chat_id=chat_id, text="Please reply with text")
                return "ok"
            idx = len(state.get("a") or [])
            types = node.get("types") or []
            ok, val = valid_answer(types[idx] if idx < len(types) else "text", text)
            if not ok:
                tg(token, "sendMessage", chat_id=chat_id, text=FORM_HINT.get(types[idx], "Invalid, retry"))
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
                    body = "\n\n".join(f"{q}\n> {a}" for q, a in zip(fields, ans))
                    tg(token, "sendMessage", chat_id=bot["owner"],
                       text=(f"New form — {cfg['name']}\n{who(env)}\n\n{body}")[:4000])
                finish(env, node, "Saved. Thanks!")
        elif state and state.get("ask"):
            r = tg(token, "copyMessage", chat_id=bot["owner"], from_chat_id=chat_id, message_id=msg["message_id"])
            if r.get("ok"):
                tg(token, "sendMessage", chat_id=bot["owner"], text=who(env))
            db.states.delete_one({"_id": sid})
            node = cfg["nodes"].get(state["ask"]) if isinstance(state["ask"], str) else None
            finish(env, node or {}, "Message sent.")
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
                log.exception("saving vars failed")
    return "ok"

# ── Mother ──
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
        tg(MOTHER_TOKEN, "sendMessage", chat_id=uid,
           text="Super BotMaker: describe any bot, AI builds it. Tokens pay for AI builds. Invite friends to earn.",
           reply_markup={"inline_keyboard": [[{"text": "Open Studio", "web_app": {"url": BASE_URL}}]]})
    return "ok"

def setup_mother():
    r = tg(MOTHER_TOKEN, "setWebhook", url=f"{BASE_URL}/mother", secret_token=MOTHER_SECRET,
           allowed_updates=["message"])
    tg(MOTHER_TOKEN, "setChatMenuButton",
       menu_button={"type": "web_app", "text": "Studio", "web_app": {"url": BASE_URL}})
    log.info("mother webhook: %s", r)

try:
    if MOTHER_TOKEN and BASE_URL:
        setup_mother()
except Exception as e:
    log.warning("setup_mother: %s", e)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
