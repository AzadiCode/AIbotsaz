# -*- coding: utf-8 -*-
"""
webapp.py — مینی‌اپ‌ساز: سازنده، رانتایم امن، تولید با هوش مصنوعی و قالب‌ها (وابسته به core، ai و engine)

بخش‌ها:
  • ثابت‌ها و ابزارهای مینی‌اپ (رنگ، امنیت، رویداد)
  • اعتبارسنجی کانفیگ مینی‌اپ (sanitize_app) و بازرس منطقی (lint_app)
  • قالب‌های آماده (۵ قالب)
  • مسیرهای سازنده: پیش‌نویس، انتشار، نسخه‌ها، دکمه‌ی ربات، آمار
  • ساخت مینی‌اپ با هوش مصنوعی (کار پس‌زمینه با همان الگوی gen_job)
  • رانتایم عمومی: صفحه‌ی /a و مسیرهای /rt (بوت، اکشن، فرم، داده)
  • گفتگوی هوشمند و پرداخت با ستاره داخل مینی‌اپ

اصل بنیادی: هیچ کد کاربر اجرا نمی‌شود. کانفیگ مینی‌اپ فقط JSON اعتبارسنجی‌شده است و
رانتایم یک رندرر ثابت است که آن را می‌کشد؛ اکشن‌های حالت‌دار همیشه از سرور اجرا می‌شوند.
نمونه: بلوک تازه ← ۱) پاک‌سازی در sanitize_app  ۲) رندر در mapp.js (جدول BLOCKS)  ۳) اکشن سرورش در rt_act.
"""

import os, re, json, time, gzip, secrets, threading

from flask import jsonify, request, Response, send_from_directory
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from bson.errors import InvalidId

from core import (
    AI_MAX_TOKENS, app, asset_v, assets_stamp, authed, aware, BASE_URL, BILLING, BUILD, calc_cost, charge_up_to, cut, db, _DIG,
    est_tokens, get_bot, hold, _int, JOB_TIMEOUT, log, MAX_STARS, MAX_VERSIONS, media_list, naive, now, PAYMENTS,
    perks_of, rate_ok, refund, spend, tehran_day, tg, TOKEN_MIN_COST, TOKEN_SCALE, touch_user,
    verify_init_data, dec, wallet_info,
)
from ai import (
    ACT_OPS, BUILTINS, ID_RE, PH_RE, TAB_RE, VAR_RE, _PRIV_HOST, clean_actions, clean_cond,
    clean_rec_cond, llm_post, llm_run, MAX_RECORDS_SHARED, MAX_RECORDS_USER, norm_url, Progress, _prog,
    to_num,
)
from engine import (
    Env, ai_postcharge, ai_precheck, board_text, fill, rec_line, run_actions, save_submission,
    send_node, sync_commands, ticket_open, to_owner, who, _rec_query,
)


# ───────────────────────── ثابت‌ها و ابزارهای مینی‌اپ ─────────────────────────
APP_DIR = os.path.dirname(os.path.abspath(__file__))
APP_MAX_SCREENS = 12          # حداکثر صفحه
APP_MAX_BLOCKS_SCREEN = 40    # حداکثر بلوک در هر صفحه
APP_MAX_BLOCKS = 150          # حداکثر بلوک کل
APP_MAX_BYTES = 150 * 1024    # حداکثر حجم JSON کانفیگ
APP_MAX_FIELDS = 12           # حداکثر فیلد فرم
APP_MAX_NAV = 6               # حداکثر آیتم ناوبری پایین
APP_MAX_CARDS = 50            # حداکثر کارت در بلوک کارت‌ها
APP_MAX_GALLERY = 10
APP_MAX_FAQ = 20
APP_MAX_LINKS = 20
APP_MAX_ROWS = 4              # حداکثر ردیف دکمه در بلوک دکمه‌ها
APP_MAX_BTN_ROW = 3
APP_MAX_HAND = 8              # حداکثر اکشن هر هندلر
APP_F_TYPES = ("text", "number", "phone", "email", "select", "date")
APP_ICONS = ("home", "shop", "form", "star", "info", "users", "phone", "image", "chat", "gift", "clock", "trophy")
APP_FONTS = ("vazir", "oxanium_vazir", "system")
APP_GEN_COST = _int("APP_GEN_COST", 2 * TOKEN_SCALE)      # ساخت مینی‌اپ با هوش مصنوعی (حالت fixed)
APP_TPL_COST = _int("APP_TPL_COST", 1 * TOKEN_SCALE)      # هر قالب آماده‌ی مینی‌اپ
APP_DAILY_BOOT = _int("APP_DAILY_BOOT", 6000)             # سقف روزانه‌ی باز شدن هر مینی‌اپ
APP_DAILY_ACT = _int("APP_DAILY_ACT", 20000)              # سقف روزانه‌ی اکشن هر مینی‌اپ
APP_DAILY_FORM = _int("APP_DAILY_FORM", 2000)             # سقف روزانه‌ی ثبت فرم هر مینی‌اپ

# CSP فقط برای رانتایم (/a و /rt)؛ صفحات دیگر مثل قبل بدون CSP می‌مانند
_CSP_BASE = ("default-src 'self'; script-src 'self' https://telegram.org; "
             "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
             "img-src 'self' data: blob: https:; media-src 'self' blob: https:; connect-src 'self'; "
             "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org https://telegram.org")
# iframe پیش‌نمایش سازنده با sandbox بدون allow-same-origin مبدأ opaque دارد؛ 'self' برای چنین سندی هیچ چیزی را نمی‌پذیرد،
# پس هاست خود سرویس هم صریح داخل CSP می‌آید تا mapp.js و رسانه‌ی هم‌دامنه داخل پیش‌نمایش هم لود شوند
_CSP_TMPL = ("default-src 'self' https://{h} http://{h}; "
             "script-src 'self' https://{h} http://{h} https://telegram.org; "
             "style-src 'self' https://{h} http://{h} 'unsafe-inline' https://fonts.googleapis.com; "
             "font-src https://fonts.gstatic.com; "
             "img-src 'self' https://{h} http://{h} data: blob: https:; "
             "media-src 'self' https://{h} http://{h} blob: https:; "
             "connect-src 'self' https://{h} http://{h}; "
             "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org https://telegram.org")


def _csp():
    h = request.host or ""
    if not re.fullmatch(r"[A-Za-z0-9.\-]+(:\d{1,5})?", h):
        return _CSP_BASE
    return _CSP_TMPL.format(h=h)
_GZIP_TYPES = ("text/html", "application/json", "application/javascript", "text/css", "image/svg+xml")


@app.after_request
def _app_secure(resp):
    """هدرهای امنیتی و فشرده‌سازی سبک فقط برای رانتایم مینی‌اپ (X-Frame-Options عمداً ست نمی‌شود)"""
    p = request.path
    if p.startswith("/a/") or p.startswith("/rt/") or p == "/static/mapp.js":
        resp.headers.setdefault("Content-Security-Policy", _csp())
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        try:
            if (resp.status_code == 200 and not resp.direct_passthrough
                    and resp.mimetype in _GZIP_TYPES and "gzip" in (request.headers.get("Accept-Encoding") or "")
                    and len(resp.get_data()) > 600):
                body = gzip.compress(resp.get_data(), 5)
                resp.set_data(body)
                resp.headers["Content-Encoding"] = "gzip"
                resp.headers["Content-Length"] = str(len(body))
                resp.headers.setdefault("Vary", "Accept-Encoding")
        except Exception:
            pass
    return resp


def _ev(bot_id, kind, key=""):
    """شمارنده‌ی روزانه‌ی رویداد مینی‌اپ (باز شدن، کلیک بلوک، فرم، پرداخت)؛ با TTL پاک می‌شود"""
    try:
        up = {"$inc": {"n": 1}, "$setOnInsert": {"t": now()}}
        if key:
            up["$setOnInsert"]["b"] = key[:40]
        db.app_ev.update_one({"_id": f"{bot_id}:{kind}:{tehran_day()}" + (f":{key[:40]}" if key else "")}, up, upsert=True)
    except Exception:
        pass


def _daily_cap(bot_id, kind, cap):
    """سقف روزانه‌ی هر ربات؛ False یعنی سقف پر شده"""
    try:
        d = db.app_ev.find_one_and_update(
            {"_id": f"{bot_id}:cap:{kind}:{tehran_day()}"},
            {"$inc": {"n": 1}, "$setOnInsert": {"t": now()}}, upsert=True, return_document=True)
        return int(d.get("n", 1)) <= cap
    except Exception:
        return True


def own_app_media(uid):
    return {str(m["_id"]) for m in db.media.find({"owner": uid}, {"_id": 1})}


def _lum(hx):
    r, g, b = (int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)


def _accent(v, bad):
    """رنگ اصلی + رنگ متنِ روی آن (کنتراست خودکار حداقل ۴٫۵)"""
    m = re.fullmatch(r"#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})", str(v or "").strip())
    if not m:
        bad("رنگ اصلی باید یک کد هکس باشد، مثل #3CCFE3")
        return "#3CCFE3", "#04141A"
    h = m.group(1).lower()
    if len(h) == 3:
        h = "".join(x * 2 for x in h)
    hx = "#" + h
    L = _lum(hx)
    cw, cb = 1.05 / (L + .05), (L + .05) / .05
    return hx, ("#FFFFFF" if cw >= cb else "#04141A")


def _txt(v, n):
    return str(v if v is not None else "").strip()[:n]


# متن‌های HTML-دار بلوک‌ها فقط زیرمجموعه‌ی امن تلگرام هستند؛ تگ‌های خطرناک همین‌جا (سمت سرور) حذف می‌شوند
_BAD_TAGS = re.compile(r"(?i)<\s*/?\s*(script|iframe|object|embed|style|svg|math|form|link|meta|base|input|button|textarea|select)\b[^>]*>")
_BAD_SCHEME = re.compile(r"(?i)\b(javascript|vbscript)\s*:")


def _rich(s):
    """(متن پاک‌شده، آیا چیزی حذف شد؟)"""
    src = str(s if s is not None else "")
    out = _BAD_TAGS.sub("", _BAD_SCHEME.sub("", src))
    return out, out != src


def _media_ref(b, media, bad):
    """رسانه‌ی بلوک: شناسه‌ی کتابخانه‌ی خود سازنده یا لینک https عمومی؛ نامعتبر = None"""
    mid = _txt(b.get("media"), 40)
    u = _txt(b.get("url"), 500)
    if mid:
        if mid in media:
            return {"media": mid}
        bad("رسانه‌ی انتخابی از کتابخانه‌ی خودت نیست")
        return None
    if u:
        host = ""
        try:
            from urllib.parse import urlparse
            host = (urlparse(u).hostname or "").lower()
        except Exception:
            host = ""
        if not u.startswith("https://") or not host or ":" in host or _PRIV_HOST.match(host) or re.search(r"\s", u):
            bad("لینک رسانه باید یک آدرس https عمومی باشد")
            return None
        return {"url": u}
    return None



def _itemsb(b, cap, spec, bad):
    """فهرست آیتم‌های یک بلوک: spec = {کلید: سقف طول}؛ فقط کلیدهای مجاز می‌مانند"""
    out = []
    for x in (b.get("items") if isinstance(b.get("items"), list) else [])[:cap]:
        if isinstance(x, str):
            if "t" in spec and _txt(x, spec["t"]):
                out.append({"t": _txt(x, spec["t"])})
            continue
        if not isinstance(x, dict):
            continue
        it = {}
        for k, n in spec.items():
            if k == "ic":
                v = _txt(x.get("ic"), 8)
                if v:
                    it["ic"] = v
            elif k == "hi":
                if x.get("hi"):
                    it["hi"] = True
            elif k == "url":
                u = norm_url(x.get("url"))
                if u:
                    it["url"] = u
            else:
                v = _txt(x.get(k), n)
                if v:
                    it[k] = v
        if it:
            out.append(it)
    if not out:
        bad("این بلوک حداقل یک آیتم معتبر لازم دارد")
        return None
    return out


def _st_clean(b, bad):
    """تنظیمات چیدمان بصری هر بلوک (ستون، فاصله، پس‌زمینه، گردی، سایه، انیمیشن، طرح) — همه با کنترل بصری، بدون CSS خام"""
    st = b.get("st") if isinstance(b.get("st"), dict) else None
    if not st:
        return None
    o = {}
    if st.get("cols") in (1, 2, 3):
        o["cols"] = st["cols"]
    try:
        g = max(0, min(24, int(float(str(st.get("gap", 0)).translate(_DIG)))))
        if g:
            o["gap"] = g
    except (TypeError, ValueError):
        pass
    if st.get("align") in ("start", "center"):
        o["align"] = st["align"]
    if st.get("bg") in ("soft", "card", "grad"):
        o["bg"] = st["bg"]
    try:
        r = max(0, min(28, int(float(str(st.get("rad", 0)).translate(_DIG)))))
        if r:
            o["rad"] = r
    except (TypeError, ValueError):
        pass
    if st.get("shadow"):
        o["shadow"] = True
    if st.get("anim") in ("fade", "up"):
        o["anim"] = st["anim"]
    if st.get("v") in ("rows", "grid", "mini", "cover", "chips"):
        o["v"] = st["v"]
    return o or None


# ───────────────────────── اعتبارسنجی کانفیگ مینی‌اپ ─────────────────────────
def sanitize_app(app_in, strict=False, media=None, warns=None, blocks_cap=None, node_ids=None):
    """strict=True (ویرایش دستی سازنده): خطای فارسی می‌دهد. strict=False (خروجی AI): اصلاح می‌کند و حذفیات در warns می‌رود.
    blocks_cap = سقف بلوک بر اساس اشتراک؛ node_ids = بخش‌های ربات (برای اکشن send و مقصد یادآور)"""
    media = media or set()
    node_ids = node_ids or set()
    warns = warns if warns is not None else []
    blocks_cap = max(1, int(blocks_cap or APP_MAX_BLOCKS))
    used, nums = set(), set()
    tables = {"tabs": {}, "gets": []}
    n_blocks = [0]

    def bad(msg):
        if strict:
            raise ValueError(msg)
        if len(warns) < 14 and msg not in warns:
            warns.append(msg)

    def _richtext(v, n):
        """متن HTML-دار: تگ‌های خطرناک همیشه پاک می‌شوند؛ هشدار فقط برای خروجی AI"""
        s, flagged = _rich(v)
        if flagged and not strict:
            bad("تگ‌های خطرناک از متن حذف شد")
        return s[:n]

    if not isinstance(app_in, dict):
        raise ValueError("ساختار مینی‌اپ معتبر نیست")
    try:
        if len(json.dumps(app_in, ensure_ascii=False)) > APP_MAX_BYTES:
            raise ValueError(f"حجم مینی‌اپ نباید از {APP_MAX_BYTES // 1024} کیلوبایت بیشتر باشد")
    except TypeError:
        raise ValueError("ساختار مینی‌اپ معتبر نیست")

    # ── تم ──
    th = app_in.get("theme") if isinstance(app_in.get("theme"), dict) else {}
    mode = th.get("mode") if th.get("mode") in ("auto", "dark", "light") else "auto"
    acc, on_acc = _accent(th.get("accent"), bad)
    try:
        rad = max(0, min(28, int(float(str(th.get("radius", 16)).translate(_DIG)))))
    except (TypeError, ValueError):
        rad = 16
    font = th.get("font") if th.get("font") in APP_FONTS else "vazir"
    digits = th.get("digits") if th.get("digits") in ("latin", "fa") else "latin"
    theme = {"mode": mode, "accent": acc, "on_accent": on_acc, "radius": rad, "font": font, "digits": digits}

    # ── صفحه‌ها: شناسه‌ها ──
    scr_in = app_in.get("screens")
    if not isinstance(scr_in, dict) or not scr_in:
        raise ValueError("حداقل یک صفحه لازم است")
    if len(scr_in) > APP_MAX_SCREENS:
        raise ValueError(f"حداکثر {APP_MAX_SCREENS} صفحه می‌تونی داشته باشی")
    screens = {}
    for sid, s in scr_in.items():
        sid = str(sid)
        if ID_RE.match(sid) and isinstance(s, dict):
            screens[sid] = s
        else:
            bad(f"شناسه‌ی صفحه «{sid}» معتبر نیست (حروف انگلیسی کوچک، عدد و _)")
    if not screens:
        raise ValueError("هیچ صفحه‌ی معتبری وجود نداره")

    home = str(app_in.get("home") or "")
    if home not in screens:
        home = next(iter(screens))

    nav_raw = app_in.get("nav") if isinstance(app_in.get("nav"), dict) else {}
    nav_items = []
    for it in (nav_raw.get("items") if isinstance(nav_raw.get("items"), list) else [])[:APP_MAX_NAV]:
        it = str(it)
        if it in screens and it not in nav_items:
            nav_items.append(it)
        else:
            bad(f"آیتم ناوبری «{it}» به صفحه‌ی معتبری وصل نیست")
    nav_type = nav_raw.get("type", "tabs") if nav_items else "none"
    if nav_type not in ("tabs", "top", "none"):
        nav_type = "tabs"
    nav_style = nav_raw.get("style") if nav_raw.get("style") in ("simple", "glass", "round", "island") else "simple"

    def clean_do(lst, where):
        """اکشن‌های یک هندلر: اکشن‌های موتور ربات + اکشن‌های رابط؛ حداکثر APP_MAX_HAND"""
        out = []
        for a in (lst if isinstance(lst, list) else [])[:APP_MAX_HAND]:
            if not isinstance(a, dict):
                continue
            op = str(a.get("op") or "").strip().lower()
            if op in ACT_OPS:
                r = clean_actions([a], used, nums, bad, node_ids, tables)
                out.extend(r)
            elif op == "goto":
                s = str(a.get("screen") or "")
                if s in screens:
                    out.append({"op": "goto", "screen": s})
                else:
                    bad(f"مقصد «رفتن به صفحه» در {where} معتبر نیست")
            elif op == "url":
                u = norm_url(a.get("url"))
                if u:
                    out.append({"op": "url", "url": u})
                else:
                    bad(f"لینک در {where} باید https یا آیدی تلگرام باشد")
            elif op in ("copy", "share", "toast"):
                t = _txt(a.get("text"), 200 if op != "toast" else 150)
                if t:
                    out.append({"op": op, "text": t})
                else:
                    bad(f"متن اکشن {op} در {where} خالیه")
            elif op in ("close", "back", "refresh"):
                out.append({"op": op})
            elif op == "send":
                nid = str(a.get("node") or "")
                if nid in node_ids:
                    out.append({"op": "send", "node": nid})
                else:
                    bad(f"اکشن «ارسال به چت» در {where} باید به یکی از بخش‌های ربات وصل باشد")
            else:
                bad(f"اکشن «{op}» در {where} معتبر نیست")
        return out[:APP_MAX_HAND]

    def clean_when(c):
        return clean_cond(c, used, nums, bad) if c else None

    used_hids = set()

    def clean_block(b, sid):
        """یک بلوک را پاک‌سازی و شناسه‌اش را تضمین می‌کند؛ نامعتبر = None"""
        if not isinstance(b, dict):
            return None
        t = str(b.get("t") or "").strip()
        bid = _txt(b.get("id"), 30)
        if not ID_RE.match(bid) or bid in used_hids:
            bid = ""
        if n_blocks[0] >= blocks_cap:
            bad(f"سقف بلوک‌های اشتراک تو {blocks_cap} تاست؛ بقیه حذف شد")
            return None
        o = {}
        if t == "hero":
            o = {"t": t, "title": _txt(b.get("title"), 80), "text": _richtext(b.get("text"), 300)}
            m = _media_ref(b, media, bad)
            if m:
                o.update(m)
            cta = b.get("cta") if isinstance(b.get("cta"), dict) else {}
            acts = clean_do(cta.get("do"), "دکمه‌ی اصلی")
            if acts and _txt(cta.get("text"), 24):
                o["cta"] = {"text": _txt(cta.get("text"), 24), "do": acts}
        elif t == "text":
            o = {"t": t, "text": _richtext(b.get("text"), 2000)}
            if not o["text"]:
                return None
        elif t == "image":
            m = _media_ref(b, media, bad)
            if not m:
                return None
            o = {"t": t, "caption": _txt(b.get("caption"), 200), **m}
        elif t == "gallery":
            items = []
            for x in (b.get("items") if isinstance(b.get("items"), list) else [])[:APP_MAX_GALLERY]:
                m = _media_ref(x if isinstance(x, dict) else {}, media, bad)
                if m:
                    items.append(m)
            if len(items) < 2:
                bad("گالری حداقل به دو تصویر نیاز دارد")
                return None
            o = {"t": t, "items": items}
        elif t in ("video", "audio"):
            m = _media_ref(b, media, bad)
            if not m:
                return None
            o = {"t": t, "caption": _txt(b.get("caption"), 200), **m}
        elif t == "buttons":
            rows = []
            for row in (b.get("rows") if isinstance(b.get("rows"), list) else [])[:APP_MAX_ROWS]:
                r = []
                for x in (row if isinstance(row, list) else [])[:APP_MAX_BTN_ROW]:
                    if not isinstance(x, dict):
                        continue
                    lb = _txt(x.get("text"), 24)
                    acts = clean_do(x.get("do"), f"دکمه‌ی «{lb}»")
                    if lb and acts:
                        r.append({"text": lb, "do": acts})
                if r:
                    rows.append(r)
            if not rows:
                return None
            o = {"t": t, "rows": rows}
        elif t == "cards":
            items = []
            for c in (b.get("items") if isinstance(b.get("items"), list) else [])[:APP_MAX_CARDS]:
                if not isinstance(c, dict):
                    continue
                it = {"title": _txt(c.get("title"), 60), "text": _txt(c.get("text"), 200)}
                m = _media_ref(c, media, bad)
                if m:
                    it.update(m)
                acts = clean_do(c.get("do"), f"کارت «{it['title']}»")
                if acts:
                    it["do"] = acts
                if it["title"] or it["text"]:
                    items.append(it)
            if not items:
                return None
            o = {"t": t, "items": items}
        elif t == "list":
            tab = _txt(b.get("table"), 20).lower()
            if not TAB_RE.match(tab):
                bad(f"نام جدول بلوک فهرست «{tab}» معتبر نیست")
                return None
            tables["tabs"].setdefault(tab, set())
            o = {"t": t, "table": tab, "scope": "all" if b.get("scope") in ("all", "shared", True) else "my"}
            try:
                o["limit"] = max(1, min(20, int(float(str(b.get("limit", 10)).translate(_DIG)))))
            except (TypeError, ValueError):
                o["limit"] = 10
            o["line"] = _txt(b.get("line"), 200) or "#{n} · {text}"
            o["empty"] = _txt(b.get("empty"), 100) or "هنوز چیزی ثبت نشده."
            w = clean_rec_cond(b.get("when"), bad)
            if w:
                o["when"] = w
        elif t == "form":
            fs = []
            for f in (b.get("fields") if isinstance(b.get("fields"), list) else [])[:APP_MAX_FIELDS]:
                if not isinstance(f, dict):
                    continue
                k = _txt(f.get("k"), 20).lower()
                ty = f.get("type") if f.get("type") in APP_F_TYPES else "text"
                if not VAR_RE.match(k):
                    bad(f"نام فیلد فرم «{k}» معتبر نیست")
                    continue
                it = {"k": k, "label": _txt(f.get("label"), 60) or k, "type": ty, "req": bool(f.get("req"))}
                if ty == "select":
                    opts = [_txt(x, 40) for x in (f.get("opts") if isinstance(f.get("opts"), list) else [])[:20] if _txt(x, 40)]
                    if len(opts) < 2:
                        bad("هر فیلد انتخابی حداقل دو گزینه لازم دارد")
                        continue
                    it["opts"] = opts
                fs.append(it)
            if not fs:
                bad("فرم حداقل یک فیلد معتبر لازم دارد")
                return None
            o = {"t": t, "fields": fs}
            sv = b.get("save") if isinstance(b.get("save"), dict) else {}
            tab = _txt(sv.get("table"), 20).lower()
            if tab and TAB_RE.match(tab):
                o["save"] = {"table": tab}
                tables["tabs"].setdefault(tab, set()).update(x["k"] for x in fs if VAR_RE.match(x["k"]))
            vv = {k: v for k, v in (sv.get("vars") if isinstance(sv.get("vars"), dict) else {}).items()
                  if VAR_RE.match(str(k)) and str(k) not in BUILTINS and VAR_RE.match(str(v))}
            if vv:
                for k in vv:
                    used.add(str(vv[k]))
                o.setdefault("save", {})["vars"] = vv
            o["notify"] = b.get("notify") is not False
            o["ticket"] = bool(b.get("ticket"))
            if o["ticket"]:
                tg_ = _txt(b.get("tag"), 20)
                if tg_:
                    o["tag"] = tg_
            o["done"] = _txt(b.get("done"), 200) or "ثبت شد. ممنون!"
            o["title"] = _txt(b.get("title"), 40)
        elif t == "stat":
            v = _txt(b.get("var"), 20).lower()
            if not (v in BUILTINS or VAR_RE.match(v)):
                bad(f"نام متغیر بلوک آماره «{v}» معتبر نیست")
                return None
            if v not in BUILTINS:
                used.add(v)
                nums.add(v)
            o = {"t": t, "var": v, "label": _txt(b.get("label"), 40)}
        elif t == "board":
            v = _txt(b.get("var"), 20).lower()
            if not (v == "refs" or (VAR_RE.match(v) and v not in BUILTINS)):
                bad(f"متغیر جدول برترین‌ها باید عددی (یا refs) باشد")
                return None
            if v != "refs":
                used.add(v)
                nums.add(v)
            try:
                top = max(3, min(20, int(float(str(b.get("top", 10)).translate(_DIG)))))
            except (TypeError, ValueError):
                top = 10
            o = {"t": t, "var": v, "top": top, "label": _txt(b.get("label"), 40) or "برترین‌ها"}
        elif t == "faq":
            items = []
            for x in (b.get("items") if isinstance(b.get("items"), list) else [])[:APP_MAX_FAQ]:
                if isinstance(x, dict) and _txt(x.get("q"), 120) and _txt(x.get("a"), 500):
                    items.append({"q": _txt(x.get("q"), 120), "a": _txt(x.get("a"), 500)})
            if not items:
                return None
            o = {"t": t, "items": items}
        elif t == "banner":
            o = {"t": t, "text": _richtext(b.get("text"), 300)}
            if not o["text"]:
                return None
            o["style"] = b.get("style") if b.get("style") in ("info", "ok", "warn") else "info"
            w = clean_when(b.get("when"))
            if w:
                o["when"] = w
        elif t == "countdown":
            try:
                to = int(float(str(b.get("to", 0)).translate(_DIG)))
            except (TypeError, ValueError):
                to = 0
            if not (now().timestamp() < to <= 4102444800):
                bad("زمان شمارش معکوس باید یک زمان آینده به‌صورت unix باشد")
                return None
            o = {"t": t, "to": to, "title": _txt(b.get("title"), 80), "done": _txt(b.get("done"), 200) or "تمام شد"}
        elif t == "pay":
            if not PAYMENTS:
                bad("پرداخت با ستاره در این سرویس فعال نیست")
                return None
            try:
                stars = int(float(str(b.get("stars", 0)).translate(_DIG)))
            except (TypeError, ValueError):
                stars = 0
            if not 1 <= stars <= MAX_STARS:
                bad(f"قیمت بلوک پرداخت باید بین ۱ تا {MAX_STARS} ستاره باشد")
                return None
            o = {"t": t, "stars": stars, "title": _txt(b.get("title"), 32) or "خرید",
                 "desc": _txt(b.get("desc"), 255) or "خرید داخل مینی‌اپ",
                 "text": _txt(b.get("text"), 300) or "پرداخت انجام شد. ممنون!"}
            acts = clean_do(b.get("do"), "بلوک پرداخت")
            if acts:
                o["do"] = acts
        elif t == "ai":
            p = _txt(b.get("prompt"), 1500)
            if not p:
                bad("بلوک گفتگوی هوشمند دستور دستیار لازم دارد")
                return None
            try:
                dly = int(float(str(b.get("daily", 15)).translate(_DIG)))
            except (TypeError, ValueError):
                dly = 15
            try:
                mem = max(0, min(6, int(float(str(b.get("memory", 3)).translate(_DIG)))))
            except (TypeError, ValueError):
                mem = 3
            o = {"t": t, "prompt": p, "daily": max(1, min(100, dly)), "memory": mem,
                 "greeting": _txt(b.get("greeting"), 200) or "سؤالت رو بنویس."}
        elif t == "links":
            items = []
            for x in (b.get("items") if isinstance(b.get("items"), list) else [])[:APP_MAX_LINKS]:
                if not isinstance(x, dict):
                    continue
                u = norm_url(x.get("url"))
                if u and _txt(x.get("label"), 40):
                    items.append({"label": _txt(x.get("label"), 40), "url": u})
            if not items:
                return None
            o = {"t": t, "items": items}
        elif t == "games":
            o = {"t": t}
        elif t == "wallet":
            o = {"t": t}
        elif t == "gamesboard":
            gm = str(b.get("game") or "").strip().lower()
            o = {"t": t, "game": gm if gm in ("quiz", "memory", "tap", "wheel", "word", "math", "typing", "puzzle", "xo") else "quiz"}
        elif t == "shopcoins":
            o = {"t": t}
        elif t == "accordion" or t == "tabs" or t == "steps" or t == "timeline":
            items = _itemsb(b, 20 if t == "accordion" else 12, {"t": 80, "d": 400}, bad)
            if not items:
                return None
            o = {"t": t, "items": items}
            if t == "tabs" and b.get("first"):
                o["first"] = True      # تب اول به‌صورت پیش‌فرض باز است
        elif t == "quote":
            o = {"t": t, "text": _richtext(b.get("text"), 500)}
            if not o["text"]:
                return None
            if _txt(b.get("by"), 60):
                o["by"] = _txt(b.get("by"), 60)
        elif t == "tags":
            items = _itemsb(b, 24, {"t": 24}, bad)
            if not items:
                return None
            o = {"t": t, "items": items}
        elif t == "table":
            head = [_txt(x, 30) for x in (b.get("head") if isinstance(b.get("head"), list) else [])[:6]]
            head = [x for x in head if x]
            rows = []
            for r in (b.get("rows") if isinstance(b.get("rows"), list) else [])[:30]:
                if isinstance(r, list):
                    cells = [_txt(x, 60) for x in r[:len(head) or 6]]
                    if any(cells):
                        rows.append(cells)
            if not head or not rows:
                bad("جدول حداقل یک سرستون و یک ردیف لازم دارد")
                return None
            o = {"t": t, "head": head, "rows": rows}
        elif t == "copytext":
            o = {"t": t, "text": _txt(b.get("text"), 300)}
            if not o["text"]:
                return None
        elif t == "article":
            o = {"t": t, "title": _txt(b.get("title"), 80), "text": _richtext(b.get("text"), 3000)}
            if not o["text"]:
                return None
        elif t == "heading":
            o = {"t": t, "text": _txt(b.get("text"), 120)}
            if not o["text"]:
                return None
            try:
                o["size"] = max(1, min(3, int(float(str(b.get("size", 1)).translate(_DIG)))))
            except (TypeError, ValueError):
                o["size"] = 1
        elif t in ("bullets", "numberlist"):
            items = _itemsb(b, 20, {"t": 140}, bad)
            if not items:
                return None
            o = {"t": t, "items": items}
        elif t == "marquee":
            o = {"t": t, "text": _txt(b.get("text"), 200)}
            if not o["text"]:
                return None
        elif t == "consent":
            o = {"t": t, "text": _richtext(b.get("text"), 1000), "label": _txt(b.get("label"), 40) or "می‌پذیرم"}
            acts = clean_do(b.get("do"), "بلوک پذیرش")
            if acts:
                o["do"] = acts
            if not o["text"]:
                return None
        elif t == "slider":
            items = []
            for x in (b.get("items") if isinstance(b.get("items"), list) else [])[:10]:
                m = _media_ref(x if isinstance(x, dict) else {}, media, bad)
                if m:
                    it = dict(m)
                    if _txt(x.get("label"), 60):
                        it["label"] = _txt(x.get("label"), 60)
                    items.append(it)
            if len(items) < 2:
                bad("اسلایدر حداقل به دو تصویر نیاز دارد")
                return None
            o = {"t": t, "items": items}
            o["auto"] = bool(b.get("auto"))
        elif t == "stories":
            items = []
            for x in (b.get("items") if isinstance(b.get("items"), list) else [])[:12]:
                m = _media_ref(x if isinstance(x, dict) else {}, media, bad)
                if m:
                    it = dict(m)
                    if _txt(x.get("label"), 30):
                        it["label"] = _txt(x.get("label"), 30)
                    items.append(it)
            if not items:
                return None
            o = {"t": t, "items": items}
        elif t == "logos" or t == "imagegrid":
            items = []
            for x in (b.get("items") if isinstance(b.get("items"), list) else [])[:12]:
                m = _media_ref(x if isinstance(x, dict) else {}, media, bad)
                if m:
                    items.append(m)
            if not items:
                return None
            o = {"t": t, "items": items}
        elif t == "before_after":
            ma = _media_ref({"media": b.get("media"), "url": b.get("url")}, media, bad)
            mb2 = _media_ref({"media": b.get("media2"), "url": b.get("url2")}, media, bad)
            if not ma or not mb2:
                bad("قبل و بعد به دو تصویر نیاز دارد")
                return None
            o = {"t": t, **ma, **{("media2" if k == "media" else "url2"): v for k, v in mb2.items()}}
            if _txt(b.get("la"), 20):
                o["la"] = _txt(b.get("la"), 20)
            if _txt(b.get("lb"), 20):
                o["lb"] = _txt(b.get("lb"), 20)
        elif t == "file":
            m = _media_ref(b, media, bad)
            if not m:
                return None
            o = {"t": t, "label": _txt(b.get("label"), 60) or "دانلود فایل", **m}
        elif t == "floatbtn":
            acts = clean_do(b.get("do"), "دکمه‌ی شناور")
            if not acts or not _txt(b.get("text"), 24):
                return None
            o = {"t": t, "text": _txt(b.get("text"), 24), "do": acts}
        elif t in ("quicklinks", "gridmenu"):
            items = _itemsb(b, 12, {"t": 24, "ic": 8, "url": 300}, bad)
            if not items:
                return None
            acts_map = {}
            for i, x in enumerate((b.get("items") if isinstance(b.get("items"), list) else [])[:12]):
                if isinstance(x, dict):
                    acts_map[i] = clean_do(x.get("do"), f"آیتم {i + 1}")
            o = {"t": t, "items": items}
            for i, acts in acts_map.items():
                if acts and i < len(o["items"]):
                    o["items"][i]["do"] = acts
            for i, it in enumerate(o["items"]):
                if it.get("do"):
                    it["hid"] = (bid or f"b{n_blocks[0] + 1}") + "q" + str(i)
        elif t == "searchbar":
            items = _itemsb(b, 50, {"t": 40, "d": 120}, bad)
            if not items:
                return None
            o = {"t": t, "items": items}
        elif t == "product":
            o = {"t": t, "title": _txt(b.get("title"), 60), "price": _txt(b.get("price"), 20)}
            if not o["title"]:
                return None
            if _txt(b.get("old"), 20):
                o["old"] = _txt(b.get("old"), 20)
            if _txt(b.get("badge"), 20):
                o["badge"] = _txt(b.get("badge"), 20)
            if _txt(b.get("text"), 300):
                o["text"] = _txt(b.get("text"), 300)
            m = _media_ref(b, media, bad)
            if m:
                o.update(m)
            acts = clean_do(b.get("do"), "دکمه‌ی محصول")
            if acts and _txt(b.get("btn"), 24):
                o["btn"] = _txt(b.get("btn"), 24)
                o["do"] = acts
                o["hid"] = (bid or "bp") + "p"
        elif t == "catalog":
            items = _itemsb(b, 30, {"t": 60, "price": 20, "tag": 20, "text": 120, "url": 400}, bad)
            if not items:
                return None
            o = {"t": t, "items": items}
            for x in (b.get("items") if isinstance(b.get("items"), list) else [])[:30]:
                if isinstance(x, dict) and isinstance(x.get("media"), str) and x["media"] in media:
                    for it in o["items"]:
                        if it.get("t") == x.get("t") and "media" not in it:
                            it["media"] = x["media"]
                            break
        elif t == "cart":
            items = _itemsb(b, 20, {"t": 40, "price": 20}, bad)
            if not items:
                return None
            o = {"t": t, "items": items, "cur": _txt(b.get("cur"), 10) or "تومان", "btn": _txt(b.get("btn"), 24) or "ثبت سفارش"}
            acts = clean_do(b.get("do"), "سبد خرید")
            if acts:
                o["do"] = acts
                o["hid"] = (bid or "bc") + "c"
        elif t == "pricing":
            items = _itemsb(b, 6, {"t": 40, "price": 20, "d": 200, "hi": True}, bad)
            if not items:
                return None
            o = {"t": t, "items": items}
            for i, x in enumerate((b.get("items") if isinstance(b.get("items"), list) else [])[:6]):
                if isinstance(x, dict):
                    acts = clean_do(x.get("do"), f"پلن {i + 1}")
                    if acts and i < len(o["items"]):
                        o["items"][i]["do"] = acts
                        o["items"][i]["hid"] = (bid or "bz") + "z" + str(i)
        elif t == "discount":
            o = {"t": t, "code": _txt(b.get("code"), 40), "text": _txt(b.get("text"), 200)}
            if not o["code"]:
                return None
        elif t == "invoice":
            items = _itemsb(b, 15, {"t": 40, "price": 20}, bad)
            if not items:
                return None
            o = {"t": t, "items": items, "cur": _txt(b.get("cur"), 10) or "تومان"}
            if _txt(b.get("note"), 200):
                o["note"] = _txt(b.get("note"), 200)
        elif t == "orders":
            tab = _txt(b.get("table"), 20).lower()
            if not TAB_RE.match(tab):
                bad("نام جدول سفارش‌ها معتبر نیست")
                return None
            tables["tabs"].setdefault(tab, set()).update(["item", "status"])
            o = {"t": t, "table": tab, "scope": "all" if b.get("scope") in ("all", "shared", True) else "my"}
            try:
                o["limit"] = max(1, min(20, int(float(str(b.get("limit", 10)).translate(_DIG)))))
            except (TypeError, ValueError):
                o["limit"] = 10
            o["empty"] = _txt(b.get("empty"), 100) or "هنوز سفارشی نداری."
        elif t == "chart":
            kind = b.get("kind") if b.get("kind") in ("line", "bar", "donut") else "bar"
            tab = _txt(b.get("table"), 20).lower()
            fld = _txt(b.get("field"), 20).lower()
            if not TAB_RE.match(tab) or not VAR_RE.match(fld):
                bad("برای نمودار، نام جدول و فیلد عددی لازم است")
                return None
            tables["tabs"].setdefault(tab, set()).add(fld)
            o = {"t": t, "kind": kind, "table": tab, "field": fld}
            if _txt(b.get("label"), 40):
                o["label"] = _txt(b.get("label"), 40)
            if _txt(b.get("key"), 20).lower() and VAR_RE.match(_txt(b.get("key"), 20).lower()):
                o["key"] = _txt(b.get("key"), 20).lower()
                tables["tabs"][tab].add(o["key"])
        elif t == "progress" or t == "xpbar":
            v = _txt(b.get("var"), 20).lower()
            if not VAR_RE.match(v):
                bad(f"نام متغیر بلوک «{t}» معتبر نیست")
                return None
            if v not in BUILTINS:
                used.add(v)
                nums.add(v)
            o = {"t": t, "var": v, "label": _txt(b.get("label"), 40)}
            if t == "progress":
                try:
                    o["max"] = max(1, min(100000, int(float(str(b.get("max", 100)).translate(_DIG)))))
                except (TypeError, ValueError):
                    o["max"] = 100
            if t == "xpbar":
                try:
                    o["per"] = max(10, min(100000, int(float(str(b.get("per", 100)).translate(_DIG)))))
                except (TypeError, ValueError):
                    o["per"] = 100
        elif t == "statrow":
            items = []
            for x in (b.get("items") if isinstance(b.get("items"), list) else [])[:4]:
                if not isinstance(x, dict):
                    continue
                v = _txt(x.get("var"), 20).lower()
                if not (v in BUILTINS or VAR_RE.match(v)):
                    bad(f"نام متغیر آماره «{v}» معتبر نیست")
                    continue
                if v not in BUILTINS:
                    used.add(v)
                    nums.add(v)
                items.append({"var": v, "label": _txt(x.get("label"), 30)})
            if not items:
                return None
            o = {"t": t, "items": items}
        elif t == "countup":
            v = _txt(b.get("var"), 20).lower()
            if not VAR_RE.match(v):
                bad("نام متغیر شمارنده معتبر نیست")
                return None
            if v not in BUILTINS:
                used.add(v)
                nums.add(v)
            o = {"t": t, "var": v, "label": _txt(b.get("label"), 40)}
        elif t == "events" or t == "calendar":
            items = _itemsb(b, 20, {"t": 60, "d": 200, "date": 20}, bad)
            if not items:
                return None
            items.sort(key=lambda x: x.get("date") or "")
            o = {"t": t, "items": items}
        elif t == "inbox":
            o = {"t": t}
            try:
                o["limit"] = max(1, min(20, int(float(str(b.get("limit", 8)).translate(_DIG)))))
            except (TypeError, ValueError):
                o["limit"] = 8
        elif t == "checkin":
            o = {"t": t}
        elif t == "badges":
            items = _itemsb(b, 12, {"t": 30, "ic": 8}, bad)
            if not items:
                return None
            o = {"t": t, "items": items}
        elif t == "invite":
            o = {"t": t, "text": _txt(b.get("text"), 200) or "دوستات رو دعوت کن و جایزه بگیر!", "btn": _txt(b.get("btn"), 24) or "📤 ارسال لینک دعوت"}
        elif t == "profile":
            items = []
            for x in (b.get("items") if isinstance(b.get("items"), list) else [])[:4]:
                if isinstance(x, dict):
                    v = _txt(x.get("var"), 20).lower()
                    if v in BUILTINS or VAR_RE.match(v):
                        if v not in BUILTINS:
                            used.add(v)
                        items.append({"var": v, "label": _txt(x.get("label"), 30)})
            o = {"t": t, "items": items}
            if _txt(b.get("bio"), 200):
                o["bio"] = _txt(b.get("bio"), 200)
        elif t == "reviews":
            items = _itemsb(b, 20, {"t": 40, "d": 300, "ic": 4}, bad)
            if not items:
                return None
            o = {"t": t, "items": items}
        elif t in ("team", "services"):
            items = _itemsb(b, 12, {"t": 40, "d": 120, "ic": 8}, bad)
            if not items:
                return None
            o = {"t": t, "items": items}
            if t == "team":
                for x in (b.get("items") if isinstance(b.get("items"), list) else [])[:12]:
                    if isinstance(x, dict) and isinstance(x.get("media"), str) and x["media"] in media:
                        for it in o["items"]:
                            if it.get("t") == x.get("t") and "media" not in it:
                                it["media"] = x["media"]
                                break
        elif t == "menu":
            items = _itemsb(b, 30, {"t": 40, "price": 20, "d": 120}, bad)
            if not items:
                return None
            o = {"t": t, "items": items, "cur": _txt(b.get("cur"), 10) or "تومان"}
        elif t == "contact":
            items = _itemsb(b, 6, {"t": 40, "d": 120, "url": 300}, bad)
            if not items:
                return None
            o = {"t": t, "items": items}
        elif t == "social":
            items = _itemsb(b, 8, {"t": 20, "ic": 8, "url": 300}, bad)
            if not items:
                return None
            o = {"t": t, "items": items}
        elif t == "map":
            o = {"t": t, "addr": _txt(b.get("addr"), 160)}
            u = norm_url(b.get("url"))
            if u:
                o["url"] = u
            m = _media_ref(b, media, bad)
            if m:
                o.update(m)
            if not o.get("addr") and not o.get("url"):
                return None
        elif t == "scratch":
            o = {"t": t, "text": _txt(b.get("text"), 200) or "🎉 جایزه بردی!"}
            acts = clean_do(b.get("do"), "کارت خراشیدنی")
            if acts:
                o["do"] = acts
                o["hid"] = (bid or "bs") + "s"
        elif t == "linktree":
            items = _itemsb(b, 12, {"t": 40, "url": 300}, bad)
            if not items:
                return None
            o = {"t": t, "items": items}
            if _txt(b.get("title"), 40):
                o["title"] = _txt(b.get("title"), 40)
        elif t == "pollstat":
            items = _itemsb(b, 8, {"t": 40, "var": 20}, bad)
            if not items:
                return None
            for it in items:
                if it.get("var") and VAR_RE.match(it["var"]):
                    used.add(it["var"])
            o = {"t": t, "items": items}
        elif t == "player":
            m = _media_ref(b, media, bad)
            if not m:
                return None
            o = {"t": t, "title": _txt(b.get("title"), 60) or "پخش", **m}
            if _txt(b.get("by"), 40):
                o["by"] = _txt(b.get("by"), 40)
        elif t == "hours" or t == "changelog":
            items = _itemsb(b, 12 if t == "hours" else 20, {"t": 40, "d": 300}, bad)
            if not items:
                return None
            o = {"t": t, "items": items}
        elif t == "booking":
            items = _itemsb(b, 12, {"t": 30, "d": 60}, bad)
            if not items:
                return None
            o = {"t": t, "items": items}
            for i, x in enumerate((b.get("items") if isinstance(b.get("items"), list) else [])[:12]):
                if isinstance(x, dict):
                    acts = clean_do(x.get("do"), f"نوبت {i + 1}")
                    if acts and i < len(o["items"]):
                        o["items"][i]["do"] = acts
                        o["items"][i]["hid"] = (bid or "bb") + "k" + str(i)
        elif t == "divider":
            o = {"t": t}
        elif t == "spacer":
            try:
                h = max(8, min(80, int(float(str(b.get("h", 16)).translate(_DIG)))))
            except (TypeError, ValueError):
                h = 16
            o = {"t": t, "h": h}
        else:
            bad(f"نوع بلوک «{t}» معتبر نیست")
            return None
        w = clean_when(b.get("when"))
        if w and t not in ("form",):
            o["when"] = w
        stl = _st_clean(b, bad)
        if stl:
            o["st"] = stl
        if not o.get("id"):
            o["id"] = bid or f"b{len(used_hids) + 1}"
        while o["id"] in used_hids:
            o["id"] += "x"
        used_hids.add(o["id"])
        n_blocks[0] += 1
        return o

    out_screens = {}
    for sid, s in screens.items():
        raw_blocks = s.get("blocks") if isinstance(s.get("blocks"), list) else []
        if len(raw_blocks) > APP_MAX_BLOCKS_SCREEN:
            bad(f"صفحه‌ی «{sid}» بیشتر از {APP_MAX_BLOCKS_SCREEN} بلوک نمی‌تواند داشته باشد")
        blocks = []
        for b in raw_blocks[:APP_MAX_BLOCKS_SCREEN]:
            cb = clean_block(b, sid)
            if cb:
                blocks.append(cb)
        sc = {"title": _txt(s.get("title"), 40) or "صفحه", "blocks": blocks}
        ic = _txt(s.get("icon"), 20)
        if ic in APP_ICONS:
            sc["icon"] = ic
        w = clean_when(s.get("when"))
        if w:
            sc["when"] = w
        out_screens[sid] = sc

    # شناسه‌ی هندلرها (hid) بعد از تثبیت شناسه‌ی بلوک‌ها ساخته می‌شود؛ سرور فقط همین‌ها را اجرا می‌کند
    for s in out_screens.values():
        for b in s["blocks"]:
            bid = b["id"]
            if b["t"] == "hero" and b.get("cta"):
                b["cta"]["hid"] = bid + "c"
            elif b["t"] == "buttons":
                for ri, row in enumerate(b["rows"]):
                    for ci, x in enumerate(row):
                        x["hid"] = f"{bid}r{ri}c{ci}"
            elif b["t"] == "cards":
                for i, c in enumerate(b["items"]):
                    if c.get("do"):
                        c["hid"] = f"{bid}k{i}"

    # متغیرهای db_get که داخل اکشن‌ها خوانده می‌شوند
    for pfx, tab in tables["gets"]:
        for f in tables["tabs"].get(tab, ()):
            v = f"{pfx}_{f}" if pfx else f
            if VAR_RE.match(v) and v not in BUILTINS:
                used.add(v)

    out = {"v": 1, "theme": theme, "nav": {"type": nav_type, "items": nav_items, "style": nav_style,
                                           "icons": bool(nav_raw.get("icons"))}, "home": home, "screens": out_screens}
    return out


def _app_goto_targets(blocks):
    out = []
    for b in blocks:
        sources = []
        if b.get("cta"):
            sources.append(b["cta"])
        sources += [x for row in b.get("rows", []) for x in row] if b.get("t") == "buttons" else []
        sources += b.get("items", []) if b.get("t") == "cards" else []
        for s in sources:
            for a in s.get("do") or []:
                if a.get("op") == "goto":
                    out.append(a["screen"])
    return out


def lint_app(app_cfg, bot_cfg=None):
    """مشکل‌های منطقی مینی‌اپ تمیزشده؛ پیام‌ها فارسی و کوتاه"""
    bot_cfg = bot_cfg or {}
    out = []
    screens = app_cfg.get("screens") or {}
    home = app_cfg.get("home")
    seen, stack = set(), [home] + list((app_cfg.get("nav") or {}).get("items") or [])
    while stack:
        i = stack.pop()
        if i in seen or i not in screens:
            continue
        seen.add(i)
        stack += _app_goto_targets(screens[i].get("blocks") or [])
    lost = [i for i in screens if i not in seen]
    if lost:
        out.append("صفحه‌های بدون مسیر ورود (با اکشن «رفتن به صفحه» به آن‌ها وصل کن یا حذفشان کن): " + "، ".join(lost[:6]))
    declared_vars = set((bot_cfg.get("vars") or {}).keys()) | set((bot_cfg.get("globals") or {}).keys()) | set(BUILTINS)
    declared_tables = set((bot_cfg.get("dbfields") or {}).keys())
    writes = set()
    for a in _walk(app_cfg):
        op = a.get("op")
        if op in ACT_OPS and op != "notify" and a.get("var"):
            writes.add(str(a["var"]))
    for sid, s in screens.items():
        for b in s.get("blocks") or []:
            if b.get("t") == "form" and not b.get("save"):
                out.append(f"فرم صفحه‌ی «{sid}» نه در جدول ذخیره می‌شود نه در متغیر (هدف ذخیره را تعیین کن)")
            if b.get("t") == "list" and b.get("table") not in declared_tables:
                out.append(f"بلوک فهرست صفحه‌ی «{sid}» به جدول «{b['table']}» وصل است که هیچ اکشنی در ربات آن را پر نمی‌کند")
            for bt in ("stat", "board"):
                v = (b.get("var") or "") if b.get("t") == bt else ""
                if v and v != "refs" and v not in declared_vars:
                    out.append(f"بلوک {('آماره' if bt == 'stat' else 'برترین‌ها')} صفحه‌ی «{sid}» متغیر «{v}» را نشان می‌دهد که در ربات تعریف نشده")
    for v in sorted((reads_of(app_cfg) - declared_vars - writes)):
        pass  # متغیرهای استفاده‌شده موقع ذخیره به‌صورت خودکار به config ربات اضافه می‌شوند؛ اینجا فقط جدول‌ها و فرم‌ها مهم‌اند
    if not PAYMENTS and any(b.get("t") == "pay" for s in screens.values() for b in s.get("blocks") or []):
        out.append("بلوک پرداخت داری ولی پرداخت با ستاره روی این سرور خاموش است")
    return [x for x in out if x]


def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def reads_of(app_cfg):
    out = set()
    for d in _walk(app_cfg):
        for v in d.values():
            if isinstance(v, str):
                out.update(m.group(1) for m in PH_RE.finditer(v))
    return out


# ───────────────────────── قالب‌های آماده (۵ قالب مینی‌اپ) ─────────────────────────
def _T(name, desc, feats, app_cfg):
    return {"id": name, "title": name, "desc": desc, "feats": feats, "app": app_cfg}


_TPL_SHOP = {
    "v": 1,
    "theme": {"mode": "auto", "accent": "#3CCFE3", "radius": 16, "font": "vazir", "digits": "latin"},
    "nav": {"type": "tabs", "items": ["home", "shop", "form"]},
    "home": "home",
    "screens": {
        "home": {"title": "خانه", "icon": "home", "blocks": [
            {"t": "hero", "id": "hero1", "title": "[نام فروشگاه]", "text": "بهترین‌ها با ارسال سریع و ضمانت اصالت؛ از منوی پایین شروع کن.",
             "cta": {"text": "دیدن محصولات", "do": [{"op": "goto", "screen": "shop"}]}},
            {"t": "banner", "id": "bn1", "style": "ok", "text": "ارسال به سراسر کشور · ضمانت اصالت · پشتیبانی پاسخ‌گو"},
            {"t": "links", "id": "lk1", "items": [
                {"label": "کانال ما", "url": "https://t.me/your_channel"},
                {"label": "تماس", "url": "https://t.me/your_id"}]},
        ]},
        "shop": {"title": "محصولات", "icon": "shop", "blocks": [
            {"t": "cards", "id": "cards1", "items": [
                {"title": "[محصول اول]", "text": "[توضیح کوتاه و قیمت]"},
                {"title": "[محصول دوم]", "text": "[توضیح کوتاه و قیمت]"},
                {"title": "[محصول سوم]", "text": "[توضیح کوتاه و قیمت]"}]},
            {"t": "buttons", "id": "btn1", "rows": [[{"text": "ثبت سفارش", "do": [{"op": "goto", "screen": "form"}]}]]},
        ]},
        "form": {"title": "سفارش", "icon": "form", "blocks": [
            {"t": "text", "id": "tx1", "text": "فرم سفارش را پر کن؛ به‌زودی برای تأیید باهات تماس می‌گیریم."},
            {"t": "form", "id": "form1", "title": "سفارش", "notify": True, "ticket": True, "tag": "سفارش",
             "done": "سفارشت ثبت شد. به‌زودی جواب می‌دیم.",
             "fields": [
                 {"k": "name", "label": "نام و نام خانوادگی", "type": "text", "req": True},
                 {"k": "phone", "label": "شماره تماس", "type": "phone", "req": True},
                 {"k": "item", "label": "محصول مورد نظر", "type": "text", "req": True},
                 {"k": "note", "label": "توضیحات (اختیاری)", "type": "text"}],
             "save": {"table": "orders"}},
            {"t": "list", "id": "ls1", "table": "orders", "scope": "my", "limit": 5,
             "line": "#{n} · {item}", "empty": "هنوز سفارشی ثبت نکرده‌ای."},
        ]},
    },
}

_TPL_BOOK = {
    "v": 1,
    "theme": {"mode": "auto", "accent": "#6C5CE7", "radius": 20, "font": "vazir", "digits": "latin"},
    "nav": {"type": "tabs", "items": ["home", "book"]},
    "home": "home",
    "screens": {
        "home": {"title": "خانه", "icon": "home", "blocks": [
            {"t": "hero", "id": "hero1", "title": "رزرو نوبت", "text": "بدون تماس تلفنی، نوبتت را همین‌جا رزرو کن.",
             "cta": {"text": "رزرو نوبت", "do": [{"op": "goto", "screen": "book"}]}},
            {"t": "cards", "id": "cards1", "items": [
                {"title": "[خدمت اول]", "text": "[مدت] دقیقه · [قیمت] تومان"},
                {"title": "[خدمت دوم]", "text": "[مدت] دقیقه · [قیمت] تومان"}]},
            {"t": "banner", "id": "bn1", "style": "info", "text": "ساعت کاری: [۹ تا ۲۱] · آدرس: [آدرس کوتاه]"},
        ]},
        "book": {"title": "رزرو", "icon": "clock", "blocks": [
            {"t": "form", "id": "form1", "title": "رزرو نوبت", "notify": True, "ticket": True, "tag": "رزرو",
             "done": "درخواست نوبتت ثبت شد؛ تأیید زمان همین‌جا اعلام می‌شود.",
             "fields": [
                 {"k": "name", "label": "نام", "type": "text", "req": True},
                 {"k": "phone", "label": "شماره تماس", "type": "phone", "req": True},
                 {"k": "service", "label": "خدمت", "type": "select", "req": True, "opts": ["[خدمت اول]", "[خدمت دوم]"]},
                 {"k": "day", "label": "روز", "type": "date", "req": True},
                 {"k": "hour", "label": "ساعت پیشنهادی", "type": "text"}],
             "save": {"table": "booking"}},
            {"t": "list", "id": "ls1", "table": "booking", "scope": "my", "limit": 5,
             "line": "#{n} · {service} — {day}", "empty": "نوبتی ثبت نکرده‌ای."},
        ]},
    },
}

_TPL_BIZ = {
    "v": 1,
    "theme": {"mode": "auto", "accent": "#168A5B", "radius": 14, "font": "vazir", "digits": "latin"},
    "nav": {"type": "tabs", "items": ["home", "about", "contact"]},
    "home": "home",
    "screens": {
        "home": {"title": "خانه", "icon": "home", "blocks": [
            {"t": "hero", "id": "hero1", "title": "[نام کسب‌وکار]", "text": "[یک جمله درباره‌ی کاری که می‌کنی]"},
            {"t": "text", "id": "tx1", "text": "<b>چرا ما؟</b>\n[دو سه خط درباره‌ی مزیت‌هایت بنویس.]"},
            {"t": "buttons", "id": "btn1", "rows": [
                [{"text": "درباره‌ی ما", "do": [{"op": "goto", "screen": "about"}]},
                 {"text": "تماس", "do": [{"op": "goto", "screen": "contact"}]}]]},
        ]},
        "about": {"title": "درباره‌ی ما", "icon": "info", "blocks": [
            {"t": "text", "id": "tx1", "text": "[داستان کسب‌وکار، سابقه و تخصص‌ها]"},
            {"t": "gallery", "id": "gl1", "items": [{"url": "https://example.com/1.jpg"}, {"url": "https://example.com/2.jpg"}]},
            {"t": "faq", "id": "fq1", "items": [
                {"q": "[سؤال رایج اول]", "a": "[پاسخ]"},
                {"q": "[سؤال رایج دوم]", "a": "[پاسخ]"}]},
        ]},
        "contact": {"title": "تماس", "icon": "phone", "blocks": [
            {"t": "links", "id": "lk1", "items": [
                {"label": "تلگرام", "url": "https://t.me/your_id"},
                {"label": "وب‌سایت", "url": "https://example.com"}]},
            {"t": "form", "id": "form1", "title": "پیام", "notify": True, "ticket": True, "tag": "تماس",
             "done": "پیامت رسید؛ به‌زودی جواب می‌دیم.",
             "fields": [
                 {"k": "name", "label": "نام", "type": "text", "req": True},
                 {"k": "msg", "label": "پیام", "type": "text", "req": True}],
             "save": {"table": "messages"}},
        ]},
    },
}

_TPL_CLUB = {
    "v": 1,
    "theme": {"mode": "auto", "accent": "#E39A00", "radius": 18, "font": "vazir", "digits": "latin"},
    "nav": {"type": "tabs", "items": ["home", "rank"]},
    "home": "home",
    "screens": {
        "home": {"title": "باشگاه", "icon": "star", "blocks": [
            {"t": "hero", "id": "hero1", "title": "باشگاه مشتریان", "text": "با هر خرید امتیاز جمع کن و جایزه بگیر."},
            {"t": "stat", "id": "st1", "var": "points", "label": "امتیاز تو"},
            {"t": "buttons", "id": "btn1", "rows": [
                [{"text": "ثبت خرید امروز", "do": [{"op": "add", "var": "points", "value": "10"},
                                                   {"op": "toast", "text": "۱۰ امتیاز اضافه شد"}]}],
                [{"text": "جدول برترین‌ها", "do": [{"op": "goto", "screen": "rank"}]}]]},
            {"t": "banner", "id": "bn1", "style": "ok", "text": "هر ۱۰۰ امتیاز = [یک جایزه]"},
        ]},
        "rank": {"title": "برترین‌ها", "icon": "trophy", "blocks": [
            {"t": "board", "id": "bd1", "var": "points", "top": 10, "label": "بیشترین امتیاز"},
            {"t": "form", "id": "form1", "title": "درخواست جایزه", "notify": True,
             "done": "درخواست جایزه‌ات ثبت شد.",
             "fields": [{"k": "gift", "label": "جایزه‌ی مورد نظر", "type": "text", "req": True}],
             "save": {"table": "rewards"}},
        ]},
    },
}

_TPL_QUIZ = {
    "v": 1,
    "theme": {"mode": "auto", "accent": "#CC3547", "radius": 16, "font": "vazir", "digits": "latin"},
    "nav": {"type": "none", "items": []},
    "home": "q1",
    "screens": {
        "q1": {"title": "سؤال ۱", "icon": "chat", "blocks": [
            {"t": "text", "id": "tx1", "text": "<b>سؤال ۱ از ۳</b>\n[سؤال اول را اینجا بنویس]"},
            {"t": "buttons", "id": "btn1", "rows": [
                [{"text": "گزینه ۱", "do": [{"op": "add", "var": "score", "value": "1"}, {"op": "goto", "screen": "q2"}]}],
                [{"text": "گزینه ۲", "do": [{"op": "goto", "screen": "q2"}]}]]},
        ]},
        "q2": {"title": "سؤال ۲", "icon": "chat", "blocks": [
            {"t": "text", "id": "tx1", "text": "<b>سؤال ۲ از ۳</b>\n[سؤال دوم]"},
            {"t": "buttons", "id": "btn1", "rows": [
                [{"text": "گزینه ۱", "do": [{"op": "add", "var": "score", "value": "1"}, {"op": "goto", "screen": "q3"}]}],
                [{"text": "گزینه ۲", "do": [{"op": "goto", "screen": "q3"}]}]]},
        ]},
        "q3": {"title": "سؤال ۳", "icon": "chat", "blocks": [
            {"t": "text", "id": "tx1", "text": "<b>سؤال آخر</b>\n[سؤال سوم]"},
            {"t": "buttons", "id": "btn1", "rows": [
                [{"text": "گزینه ۱", "do": [{"op": "add", "var": "score", "value": "1"}, {"op": "goto", "screen": "end"}]}],
                [{"text": "گزینه ۲", "do": [{"op": "goto", "screen": "end"}]}]]},
        ]},
        "end": {"title": "نتیجه", "icon": "trophy", "blocks": [
            {"t": "stat", "id": "st1", "var": "score", "label": "امتیاز تو از ۳"},
            {"t": "banner", "id": "bn1", "style": "ok", "when": {"var": "score", "op": ">=", "value": "3"},
             "text": "عالی بود! تو یک حرفه‌ای هستی."},
            {"t": "buttons", "id": "btn1", "rows": [[{"text": "بازی دوباره", "do": [{"op": "clear", "var": "score"}, {"op": "goto", "screen": "q1"}]}]]},
        ]},
    },
}

APP_TEMPLATES = {
    "shop": _T("فروشگاه", "محصولات، فرم سفارش با تیکت و تاریخچه‌ی سفارش", ["کارت محصول", "فرم سفارش", "تاریخچه"], _TPL_SHOP),
    "booking": _T("رزرو نوبت", "خدمات، رزرو با روز و ساعت و تاریخچه‌ی نوبت", ["انتخاب خدمت", "تقویم", "تاریخچه"], _TPL_BOOK),
    "biz": _T("معرفی کسب‌وکار", "درباره‌ی ما، گالری، سؤالات متداول و فرم تماس", ["گالری", "سؤالات متداول", "تماس"], _TPL_BIZ),
    "club": _T("باشگاه مشتریان", "امتیاز، جدول برترین‌ها و درخواست جایزه", ["امتیاز", "برترین‌ها", "جایزه"], _TPL_CLUB),
    "quiz": _T("مسابقه و امتیاز", "سه سؤال، امتیازگیری و صفحه‌ی نتیجه", ["امتیاز", "نتیجه شرطی"], _TPL_QUIZ),
    "restaurant": _T("منوی رستوران", "منوی غذا با قیمت، ساعات کاری، نظرات مشتری و رزرو", ["منوی قیمت‌دار", "ساعات کاری", "نظرات", "رزرو"], {
        "v": 1, "home": "home",
        "theme": {"mode": "auto", "accent": "#F0742E", "radius": 18, "font": "vazir", "digits": "latin"},
        "nav": {"type": "tabs", "items": ["home", "book"], "style": "island"},
        "screens": {
            "home": {"title": "منو", "icon": "shop", "blocks": [
                {"id": "b1", "t": "hero", "title": "🍕 رستوران [نام]", "text": "تازه و گرم، درِ خانه‌ی شما"},
                {"id": "b2", "t": "menu", "items": [{"t": "پیتزا مارگاریتا", "price": "۲۴۵", "d": "با پنیر موزارلای اصل"},
                                                     {"t": "پاستا آلفردو", "price": "۲۱۰"},
                                                     {"t": "سالاد سزار", "price": "۱۶۵"}], "cur": "هزار تومان"},
                {"id": "b3", "t": "hours", "items": [{"t": "شنبه تا چهارشنبه", "d": "۱۲ تا ۲۳"}, {"t": "پنجشنبه و جمعه", "d": "۱۲ تا ۲۴"}]},
                {"id": "b4", "t": "reviews", "items": [{"t": "سارا", "ic": "5", "d": "خمیرش عالی بود!"}, {"t": "امیر", "ic": "4", "d": "ارسال سریع"}]}]},
            "book": {"title": "رزرو میز", "icon": "cal", "blocks": [
                {"id": "c1", "t": "booking", "items": [{"t": "میز ۲ نفره - ۱۹:۰۰"}, {"t": "میز ۴ نفره - ۲۱:۰۰"}]},
                {"id": "c2", "t": "contact", "items": [{"t": "تلفن رزرو", "d": "۰۲۱-۱۲۳۴۵۶۷۸", "url": "tel:02112345678"}]}]},
        }}),
    "school": _T("آموزشگاه", "دوره‌ها، مدرس‌ها، ثبت‌نام و سؤالات متداول", ["دوره‌ها", "مدرس‌ها", "فرم ثبت‌نام"], {
        "v": 1, "home": "home",
        "theme": {"mode": "auto", "accent": "#2F7CF6", "radius": 16, "font": "vazir", "digits": "latin"},
        "nav": {"type": "tabs", "items": ["home", "reg"]},
        "screens": {
            "home": {"title": "دوره‌ها", "icon": "star", "blocks": [
                {"id": "b1", "t": "hero", "title": "🎓 آموزشگاه [نام]", "text": "مسیر یادگیری‌ات را همین‌جا شروع کن"},
                {"id": "b2", "t": "services", "items": [{"ic": "💻", "t": "برنامه‌نویسی", "d": "از صفر تا پروژه‌محور"},
                                                         {"ic": "🗣", "t": "زبان انگلیسی", "d": "گفت‌وگومحور"},
                                                         {"ic": "📐", "t": "ریاضی", "d": "کنکور و المپیاد"}]},
                {"id": "b3", "t": "team", "items": [{"t": "استاد رضایی", "d": "۱۰ سال سابقه"}, {"t": "استاد کریمی", "d": "مدرس زبان"}]},
                {"id": "b4", "t": "faq", "items": [{"q": "کلاس‌ها حضوریه؟", "a": "هم حضوری هم آنلاین."}]}]},
            "reg": {"title": "ثبت‌نام", "icon": "form", "blocks": [
                {"id": "c1", "t": "form", "title": "فرم پیش‌ثبت‌نام",
                 "fields": [{"k": "name", "label": "نام و نام خانوادگی", "type": "text", "req": True},
                            {"k": "phone", "label": "شماره تماس", "type": "phone", "req": True},
                            {"k": "course", "label": "دوره موردنظر", "type": "select", "opts": ["برنامه‌نویسی", "زبان", "ریاضی"]}],
                 "save": {"table": "regs"}, "notify": True, "done": "ثبت شد؛ برای هماهنگی تماس می‌گیریم."}]},
        }}),
    "portfolio": _T("نمونه‌کار", "معرفی، نمونه‌ها، قیمت خدمات و نظرات مشتری", ["شبکه‌ی تصویر", "خدمات", "نظرات"], {
        "v": 1, "home": "home",
        "theme": {"mode": "auto", "accent": "#6C5CE7", "radius": 20, "font": "vazir", "digits": "latin"},
        "nav": {"type": "tabs", "items": ["home"]},
        "screens": {
            "home": {"title": "نمونه‌کار", "icon": "image", "blocks": [
                {"id": "b1", "t": "hero", "title": "👋 من [نام] هستم", "text": "طراح و سازنده‌ی تجربه‌های دیجیتال", "st": {"bg": "grad"}},
                {"id": "b2", "t": "imagegrid", "items": []},
                {"id": "b3", "t": "pricing", "items": [{"t": "لندینگ", "price": "۵ میلیون", "d": "یک صفحه معرفی"}, {"t": "مینی‌اپ", "price": "۱۲ میلیون", "d": "ربات + مینی‌اپ", "hi": True}]},
                {"id": "b4", "t": "reviews", "items": [{"t": "شرکت الف", "ic": "5", "d": "دقیق و خلاق"}]},
                {"id": "b5", "t": "contact", "items": [{"t": "سفارش پروژه", "d": "تلگرام", "url": "https://t.me/your_id"}]}]},
        }}),
    "realestate": _T("املاک", "فهرست ملک با دسته، نوبت بازدید و مسیریابی", ["کاتالوگ ملک", "بازدید", "نقشه"], {
        "v": 1, "home": "home",
        "theme": {"mode": "auto", "accent": "#0E9F7E", "radius": 14, "font": "vazir", "digits": "latin"},
        "nav": {"type": "tabs", "items": ["home", "visit"]},
        "screens": {
            "home": {"title": "فهرست ملک", "icon": "home", "blocks": [
                {"id": "b1", "t": "hero", "title": "🏠 املاک [نام]", "text": "خانه‌ی بعدی‌ات را اینجا پیدا کن"},
                {"id": "b2", "t": "catalog", "items": [{"t": "آپارتمان ۸۰ متری", "price": "۴.۲ میلیارد", "tag": "فروش", "text": "۲ خواب، نورگیر"},
                                                        {"t": "مسترخانه", "price": "۳۵ میلیون", "tag": "رهن", "text": "بازیرگاها"}]},
                {"id": "b3", "t": "contact", "items": [{"t": "مشاور", "d": "۰۹۱۲۱۲۳۴۵۶۷", "url": "tel:09121234567"}]}]},
            "visit": {"title": "بازدید", "icon": "cal", "blocks": [
                {"id": "c1", "t": "booking", "items": [{"t": "صبح ۱۰ تا ۱۲"}, {"t": "عصر ۱۶ تا ۱۹"}]},
                {"id": "c2", "t": "map", "addr": "دفتر: تهران، خیابان ولیعصر", "url": "https://maps.google.com"}]},
        }}),
    "clinic": _T("کلینیک", "خدمات پزشکی، پزشکان، نوبت‌دهی و ساعات کاری", ["خدمات", "نوبت", "ساعات"], {
        "v": 1, "home": "home",
        "theme": {"mode": "auto", "accent": "#47D79B", "radius": 16, "font": "vazir", "digits": "latin"},
        "nav": {"type": "tabs", "items": ["home", "nobat"]},
        "screens": {
            "home": {"title": "کلینیک", "icon": "info", "blocks": [
                {"id": "b1", "t": "hero", "title": "🩺 کلینیک [نام]", "text": "سلامت شما، اولویت ما"},
                {"id": "b2", "t": "services", "items": [{"ic": "🦷", "t": "دندانپزشکی"}, {"ic": "🧪", "t": "آزمایشگاه"}, {"ic": "💉", "t": "واکسیناسیون"}]},
                {"id": "b3", "t": "team", "items": [{"t": "دکتر احمدی", "d": "متخصص دندان"}, {"t": "دکتر موسوی", "d": "پزشک عمومی"}]},
                {"id": "b4", "t": "hours", "items": [{"t": "شنبه تا سه‌شنبه", "d": "۹ تا ۲۰"}, {"t": "چهارشنبه", "d": "۹ تا ۱۴"}]}]},
            "nobat": {"title": "نوبت", "icon": "cal", "blocks": [
                {"id": "c1", "t": "booking", "items": [{"t": "۱۰:۰۰"}, {"t": "۱۱:۳۰"}, {"t": "۱۷:۰۰"}]},
                {"id": "c2", "t": "form", "title": "مشاوره‌ی تلفنی",
                 "fields": [{"k": "name", "label": "نام", "type": "text", "req": True},
                            {"k": "phone", "label": "شماره", "type": "phone", "req": True}],
                 "save": {"table": "visits"}, "notify": True, "done": "ثبت شد؛ تماس می‌گیریم."}]},
        }}),
    "gym": _T("باشگاه ورزشی", "کلاس‌ها، مربی‌ها، اشتراک و چالش هفتگی", ["کلاس‌ها", "مربی‌ها", "اشتراک"], {
        "v": 1, "home": "home",
        "theme": {"mode": "auto", "accent": "#CC3547", "radius": 18, "font": "vazir", "digits": "latin"},
        "nav": {"type": "tabs", "items": ["home", "sub"]},
        "screens": {
            "home": {"title": "کلاس‌ها", "icon": "star", "blocks": [
                {"id": "b1", "t": "hero", "title": "🏋️ باشگاه [نام]", "text": "قوی‌تر از دیروز", "st": {"bg": "grad"}},
                {"id": "b2", "t": "gridmenu", "items": [{"ic": "🥊", "t": "بوکس"}, {"ic": "🧘", "t": "یوگا"}, {"ic": "🤸", "t": "کراس‌فیت"}]},
                {"id": "b3", "t": "team", "items": [{"t": "مربی کریمی", "d": "بدنساز حرفه‌ای"}]},
                {"id": "b4", "t": "countdown", "to": 4102444800, "title": "شروع چالش ۳۰ روزه"}]},
            "sub": {"title": "اشتراک", "icon": "gift", "blocks": [
                {"id": "c1", "t": "pricing", "items": [{"t": "ماهانه", "price": "۹۰۰", "d": "دسترسی کامل"}, {"t": "سه‌ماهه", "price": "۲۴۰۰", "d": "با مربی شخصی", "hi": True}]},
                {"id": "c2", "t": "form", "title": "ثبت‌نام",
                 "fields": [{"k": "name", "label": "نام", "type": "text", "req": True},
                            {"k": "phone", "label": "شماره", "type": "phone", "req": True}],
                 "save": {"table": "members"}, "notify": True, "done": "خوش آمدی!"}]},
        }}),
    "event": _T("رویداد و بلیت", "معرفی رویداد، شمارش معکوس، برنامه و خرید بلیت", ["شمارش معکوس", "برنامه", "بلیت"], {
        "v": 1, "home": "home",
        "theme": {"mode": "auto", "accent": "#E39A00", "radius": 20, "font": "vazir", "digits": "latin"},
        "nav": {"type": "tabs", "items": ["home", "ticket"]},
        "screens": {
            "home": {"title": "رویداد", "icon": "cal", "blocks": [
                {"id": "b1", "t": "hero", "title": "🎤 رویداد [نام]", "text": "یک شب متفاوت"},
                {"id": "b2", "t": "countdown", "to": 4102444800, "title": "شروع رویداد"},
                {"id": "b3", "t": "steps", "items": [{"t": "پذیرش", "d": "۱۷:۰۰"}, {"t": "سخنرانی اول", "d": "۱۸:۰۰"}, {"t": "پرسش‌وپاسخ", "d": "۲۰:۰۰"}]},
                {"id": "b4", "t": "map", "addr": "سالن همایش‌ها، تهران"}]},
            "ticket": {"title": "بلیت", "icon": "gift", "blocks": [
                {"id": "c1", "t": "pricing", "items": [{"t": "عادی", "price": "۲۵۰", "d": "صندلی آزاد"}, {"t": "ویژه", "price": "۴۵۰", "d": "ردیف جلو + پذیرایی", "hi": True}]},
                {"id": "c2", "t": "pay", "stars": 50, "title": "بلیت رویداد", "desc": "پرداخت با ستاره‌ی تلگرام", "text": "بلیت شما رزرو شد!"}]},
        }}),
    "support": _T("پشتیبانی", "پرسش‌های متداول، تیکت، پیگیری سفارش و تماس", ["پرسش‌ها", "تیکت", "پیگیری"], {
        "v": 1, "home": "home",
        "theme": {"mode": "auto", "accent": "#274690", "radius": 14, "font": "vazir", "digits": "latin"},
        "nav": {"type": "tabs", "items": ["home", "track"]},
        "screens": {
            "home": {"title": "پشتیبانی", "icon": "headset", "blocks": [
                {"id": "b1", "t": "hero", "title": "🎧 چطور کمکت کنیم؟", "text": "سریع‌ترین جواب‌ها همین‌جاست"},
                {"id": "b2", "t": "accordion", "items": [{"t": "سفارشم کِی می‌رسد؟", "d": "۲ تا ۳ روز کاری بعد از تأیید."},
                                                          {"t": "مرجوعی چطور است؟", "d": "تا ۷ روز، با سالم بودن کالا."},
                                                          {"t": "روش‌های پرداخت؟", "d": "ستاره‌ی تلگرام و کارت‌به‌کارت."}]},
                {"id": "b3", "t": "banner", "style": "info", "text": "جواب سؤالت نبود؟ تیکت بزن؛ سریع رسیدگی می‌کنیم."}]},
            "track": {"title": "پیگیری", "icon": "inbox", "blocks": [
                {"id": "c1", "t": "form", "title": "ثبت تیکت",
                 "fields": [{"k": "order", "label": "شماره سفارش", "type": "text", "req": True},
                            {"k": "msg", "label": "توضیح مشکل", "type": "text", "req": True}],
                 "save": {"table": "tickets2"}, "ticket": True, "tag": "پشتیبانی", "done": "تیکت شما ثبت شد."},
                {"id": "c2", "t": "contact", "items": [{"t": "تماس مستقیم", "d": "۰۲۱-۱۲۳۴۵۶۷۸", "url": "tel:02112345678"}]}]},
        }}),
}


# ───────────────────────── ذخیره، کش و ابزارهای سند مینی‌اپ ─────────────────────────
_PUB_CACHE = {}          # bot_id -> (etag, pub, lookup, t)
_TOK_CACHE = {}          # bot_id -> (token, t) — برای dec() ارزان‌تر


def app_doc(bot_id):
    return db.apps.find_one({"_id": bot_id})


def app_export_doc(bot_id):
    d = app_doc(bot_id) or {}
    return {"draft": d.get("draft"), "pub": d.get("pub"), "ver": int(d.get("ver", 0)),
            "versions": [{"ver": v.get("ver"), "t": aware(v["t"]).isoformat() + "Z" if v.get("t") else ""} for v in (d.get("versions") or [])]}


def delete_app_data(bot_id):
    """با حذف ربات: سند مینی‌اپ و همه‌ی رویدادهایش پاک می‌شوند (شناسه‌ها hex هستند و «:» ندارند؛ پیشوند امن است)"""
    db.apps.delete_one({"_id": bot_id})
    db.app_ev.delete_many({"_id": {"$regex": "^" + re.escape(bot_id + ":")}})
    db.appai.delete_many({"_id": {"$regex": "^" + re.escape(bot_id + ":")}})
    db.appfm.delete_many({"_id": {"$regex": "^" + re.escape(bot_id + ":")}})
    _PUB_CACHE.pop(bot_id, None)
    _TOK_CACHE.pop(bot_id, None)


def _pub(bot_id):
    """کانفیگ منتشرشده + جدول هندلرها، با کش و ETag؛ pub حاوی ver است"""
    hit = _PUB_CACHE.get(bot_id)
    if hit and time.time() - hit[3] < 20:
        return hit[0], hit[1], hit[2]
    d = db.apps.find_one({"_id": bot_id, "pub": {"$exists": True, "$ne": None}}) or {}
    pub = d.get("pub")
    if not pub:
        _PUB_CACHE.pop(bot_id, None)
        return None, None, None
    lk = {}
    for s in (pub.get("screens") or {}).values():
        for b in s.get("blocks") or []:
            bid = b.get("id") or ""
            if b.get("t") in ("pay", "ai", "form", "list", "board") and bid:
                lk[bid] = b
            if b.get("t") == "hero" and (b.get("cta") or {}).get("hid"):
                lk[b["cta"]["hid"]] = b["cta"]
            if b.get("t") == "buttons":
                for row in b.get("rows") or []:
                    for x in row:
                        if x.get("hid"):
                            lk[x["hid"]] = x
            if b.get("t") == "cards":
                for c in b.get("items") or []:
                    if c.get("hid"):
                        lk[c["hid"]] = c
    etag = f'W/"{bot_id[:8]}-{int(d.get("ver", pub.get("ver", 1)))}"'
    if len(_PUB_CACHE) > 300:
        _PUB_CACHE.clear()
    _PUB_CACHE[bot_id] = (etag, pub, lk, time.time())
    return etag, pub, lk


def _pub_invalidate(bot_id):
    _PUB_CACHE.pop(bot_id, None)


def _child_token(bot):
    hit = _TOK_CACHE.get(str(bot["_id"]))
    if hit and time.time() - hit[1] < 600:
        return hit[0]
    tok = dec(bot["token_enc"])
    if len(_TOK_CACHE) > 300:
        _TOK_CACHE.clear()
    _TOK_CACHE[str(bot["_id"])] = (tok, time.time())
    return tok


def _vars_snapshot(bot_id, uid, cfg):
    """تصویر متغیرهای کاربر + متغیرهای مشترک برای رندر اولیه"""
    d = db.uvars.find_one({"_id": f"{bot_id}:{uid}"}) or {}
    vars_ = {k: str(v)[:200] for k, v in (d.get("v") or {}).items()}
    # متغیرهای آماده که بلوک آماره می‌خواند (visits/refs) باید در تصویر باشند وگرنه همیشه صفر می‌بینند
    vars_.setdefault("visits", str(int(d.get("visits", 0) or 0)))
    vars_.setdefault("refs", str(int(d.get("refs", 0) or 0)))
    if (cfg.get("growth") or {}).get("on"):
        try:
            from growth import stats as _gstats
            vars_.setdefault("invites", str(_gstats(bot_id, uid)[1]))
        except Exception:
            log.exception("invites snapshot failed")
    gv = (db.gvars.find_one({"_id": bot_id}) or {}).get("v") or {}
    glo = {}
    for k, dv in (cfg.get("globals") or {}).items():
        glo[k] = str(gv.get(k, dv))[:200]
    for k, v in gv.items():
        glo[str(k)[:30]] = str(v)[:200]
    return vars_, glo


def _rt_auth(bot_id):
    """احراز هویت رانتایم: initData امضاشده با توکنِ همان ربات فرزند. (bot, uid, user, None) یا (None, None, None, resp)"""
    try:
        bot = db.bots.find_one({"_id": ObjectId(bot_id)})
    except (InvalidId, TypeError):
        bot = None
    if not bot or not bot.get("active") or not bot.get("token_enc"):
        return None, None, None, (jsonify(status="off", error="این ربات فعلاً خاموش است."), 200)
    u = verify_init_data(request.headers.get("X-Init-Data") or (request.get_json(silent=True) or {}).get("init_data") or "",
                         _child_token(bot))
    if not u:
        return None, None, None, (jsonify(status="guest", error="برای باز کردن این مینی‌اپ، از داخل تلگرام وارد شو."), 401)
    touch_user(u)
    return bot, u["id"], u, None


# ───────────────────────── مسیرهای سازنده ─────────────────────────
def _app_caps(uid):
    p = perks_of(uid)
    used = db.apps.count_documents({"owner": uid, "pub": {"$exists": True, "$ne": None}})
    return {"blocks": int(p.get("blocks", 30)), "apps": int(p.get("apps", 1)), "apps_used": used}


@app.get("/api/myapps")
@authed
def api_myapps(uid):
    docs = {str(d["_id"]): d for d in db.apps.find({"owner": uid})}
    items = []
    for b in db.bots.find({"owner": uid}).sort("updated", -1):
        bid = str(b["_id"])
        d = docs.get(bid) or {}
        items.append({"id": bid, "name": b.get("name", ""), "username": b.get("username") or "",
                      "active": bool(b.get("active")), "on": bool(d.get("pub")),
                      "blocks": sum(len(s.get("blocks") or []) for s in ((d.get("draft") or {}).get("screens") or {}).values())})
    return jsonify(items=items, caps=_app_caps(uid))


@app.get("/api/app/templates")
@authed
def api_app_templates(uid):
    items = []
    for k, t in APP_TEMPLATES.items():
        home = t["app"].get("home") or next(iter(t["app"].get("screens") or {}), None)
        first = (t["app"].get("screens") or {}).get(home) or {}
        blocks = []
        for b in (first.get("blocks") or [])[:5]:
            slim = {"t": b.get("t")}
            for f in ("title", "text", "price", "cur"):
                if b.get(f):
                    slim[f] = str(b[f])[:60]
            if isinstance(b.get("items"), list):
                slim["items"] = [{k2: str(v)[:40] for k2, v in (it or {}).items() if k2 in ("t", "d", "price", "title")}
                                 for it in b["items"][:3]]
            blocks.append(slim)
        items.append({"id": k, "title": t["title"], "desc": t["desc"], "feats": t["feats"],
                      "blocks": sum(len(s.get("blocks") or []) for s in t["app"]["screens"].values()),
                      "preview": {"accent": (t["app"].get("theme") or {}).get("accent") or "#3CCFE3",
                                  "title": (first.get("title") or "").strip(), "blocks": blocks},
                      "cost": cut(uid, APP_TPL_COST) if APP_TPL_COST else 0})
    return jsonify(items=items)


@app.get("/api/bots/<bot_id>/app")
@authed
def api_app_get(uid, bot_id):
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    d = app_doc(bot_id) or {}
    return jsonify(draft=d.get("draft"), pub=bool(d.get("pub")), ver=int(d.get("ver", 0)),
                   updated=aware(d["updated"]).isoformat() + "Z" if d.get("updated") else None,
                   versions=[{"ver": v.get("ver"), "t": aware(v["t"]).isoformat() + "Z" if v.get("t") else ""}
                             for v in (d.get("versions") or [])],
                   caps=_app_caps(uid), username=bot.get("username") or "", active=bool(bot.get("active")))


@app.put("/api/bots/<bot_id>/app")
@authed
def api_app_put(uid, bot_id):
    """ذخیره‌ی پیش‌نویس؛ همیشه کانفیگ پاک‌شده برمی‌گردد تا کلاینت با سرور هم‌گام بماند"""
    if not rate_ok(f"apps:{uid}", 60, 60):
        return jsonify(error="کمی آروم‌تر؛ چند لحظه بعد دوباره امتحان کن"), 429
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    warns = []
    try:
        cleaned = sanitize_app((request.get_json(silent=True) or {}).get("app"), strict=True,
                               media=own_app_media(uid), warns=warns,
                               blocks_cap=_app_caps(uid)["blocks"], node_ids=set(bot["config"]["nodes"].keys()))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    db.apps.update_one({"_id": bot_id}, {"$set": {"draft": cleaned, "owner": uid, "updated": now()}}, upsert=True)
    return jsonify(ok=True, draft=cleaned, warns=warns)


@app.post("/api/bots/<bot_id>/app/ai")
@authed
def api_app_ai(uid, bot_id):
    """طراح هوشمند مینی‌اپ — «بهتر کن»: کل پیش‌نویس با هوش مصنوعی بهتر می‌شود و بعد از اعتبارسنجی جایگزین می‌شود"""
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    d = app_doc(bot_id) or {}
    draft = d.get("draft")
    if not draft:
        return jsonify(error="اول یک مینی‌اپ بساز"), 400
    if not rate_ok(f"appai:{uid}", 6, 600):
        return jsonify(error="کمی آروم‌تر؛ چند دقیقه بعد دوباره امتحان کن"), 429
    cfg_json = json.dumps(draft, ensure_ascii=False)
    if len(cfg_json) > 12000:
        return jsonify(error="این مینی‌اپ خیلی بزرگ است؛ چند بلوک را کم کن و دوباره امتحان کن"), 400
    if not hold(uid, cut(uid, TOKEN_MIN_COST)):
        return jsonify(error="موجودی توکن کافی نیست", need=TOKEN_MIN_COST, wallet=wallet_info(uid)), 402
    from ai import llm_post, AI_CHAT_MODEL
    sys = ("تو طراح مینی‌اپ فارسی هستی. کانفیگ JSON مینی‌اپ را بهتر کن:\n"
           "- عنوان‌ها و متن‌ها را جذاب‌تر، حرفه‌ای‌تر و بی‌غلط کن\n"
           "- ترتیب بلوک‌های هر صفحه را برای تجربه‌ی کاربری بهتر بچین (سربرگ اول، فرم/پرداخت در دسترس)\n"
           "- متن ناقص یا گم‌شده را با محتوای مناسب و واقع‌گرایانه پر کن؛ چیزی که هست را حذف نکن\n"
           "- ساختار کلی، نوع بلوک‌ها، تم و صفحات را همان نگه دار\n"
           "فقط JSON کامل بر گردان؛ بدون توضیح و بدون ```")
    try:
        txt, (pt, ct) = llm_post([{"role": "system", "content": sys}, {"role": "user", "content": cfg_json}],
                                 3000, temperature=0.4, timeout=150, model=AI_CHAT_MODEL)
    except Exception:
        return jsonify(error="اتصال به هوش مصنوعی برقرار نشد؛ کمی بعد دوباره امتحان کن"), 502
    cost = charge_up_to(uid, cut(uid, calc_cost(pt, ct, minimum=TOKEN_MIN_COST, uid=uid)), "edit", daily_key=True)
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return jsonify(error="خروجی قابل استفاده‌ای برنگشت؛ دوباره امتحان کن"), 502
    warns = []
    try:
        cleaned = sanitize_app(json.loads(m.group(0)), strict=False, media=own_app_media(uid), warns=warns,
                               blocks_cap=_app_caps(uid)["blocks"], node_ids=set(bot["config"]["nodes"].keys()))
    except (ValueError, TypeError, KeyError):
        return jsonify(error="خروجی اعتبارسنجی نشد؛ دوباره امتحان کن"), 502
    db.apps.update_one({"_id": bot_id}, {"$set": {"draft": cleaned, "owner": uid, "updated": now()}}, upsert=True)
    return jsonify(ok=True, draft=cleaned, warns=warns, cost=cost, wallet=wallet_info(uid))


@app.post("/api/bots/<bot_id>/app/publish")
@authed
def api_app_publish(uid, bot_id):
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    d = app_doc(bot_id) or {}
    if not d.get("draft"):
        return jsonify(error="اول یک مینی‌اپ بساز"), 400
    caps = _app_caps(uid)
    was_on = bool(d.get("pub"))
    if not was_on and caps["apps_used"] >= caps["apps"]:
        return jsonify(error=f"با اشتراک فعلی‌ت می‌تونی {caps['apps']} مینی‌اپ فعال داشته باشی. یکی را لغو انتشار کن یا اشتراکت را ارتقا بده.", need_plan=True), 403
    warns = []
    try:
        cleaned = sanitize_app(d["draft"], strict=True, media=own_app_media(uid), warns=warns,
                               blocks_cap=caps["blocks"], node_ids=set(bot["config"]["nodes"].keys()))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    ver = int(d.get("ver", 0)) + 1
    pub = dict(cleaned, ver=ver)
    upd = {"draft": cleaned, "pub": pub, "ver": ver, "owner": uid, "updated": now()}
    if was_on and d.get("pub"):
        upd["versions"] = (d.get("versions") or [])[-(MAX_VERSIONS + perks_of(uid)["ver"]):] + \
                          [{"ver": int(d["pub"].get("ver", 0)), "app": d["pub"], "t": now()}]
    db.apps.update_one({"_id": bot_id}, {"$set": upd}, upsert=True)
    _pub_invalidate(bot_id)
    _ev(bot_id, "pub")
    if bot.get("active") and bot.get("token_enc"):
        try:
            tg(_child_token(bot), "setChatMenuButton", menu_button={"type": "web_app", "text": "مینی‌اپ",
                                                                    "web_app": {"url": f"{BASE_URL}/a/{bot_id}"}})
        except Exception:
            log.exception("set menu button failed")
    link = f"https://t.me/{bot.get('username')}?startapp" if bot.get("username") else ""
    return jsonify(ok=True, ver=ver, link=link, warns=warns)


@app.post("/api/bots/<bot_id>/app/unpublish")
@authed
def api_app_unpublish(uid, bot_id):
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    db.apps.update_one({"_id": bot_id}, {"$unset": {"pub": ""}, "$set": {"updated": now()}})
    _pub_invalidate(bot_id)
    if bot.get("active") and bot.get("token_enc"):
        try:
            tg(_child_token(bot), "setChatMenuButton", menu_button={"type": "commands"})
        except Exception:
            log.exception("unset menu button failed")
    return jsonify(ok=True)


@app.get("/api/bots/<bot_id>/app/lint")
@authed
def api_app_lint(uid, bot_id):
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    d = app_doc(bot_id) or {}
    return jsonify(issues=lint_app(d.get("draft") or {}, bot["config"]))


@app.get("/api/bots/<bot_id>/app/versions")
@authed
def api_app_versions(uid, bot_id):
    if not get_bot(bot_id, uid):
        return jsonify(error="ربات پیدا نشد"), 404
    d = app_doc(bot_id) or {}
    return jsonify(items=[{"ver": v.get("ver"), "t": aware(v["t"]).isoformat() + "Z" if v.get("t") else ""}
                          for v in (d.get("versions") or [])])


@app.post("/api/bots/<bot_id>/app/undo")
@authed
def api_app_undo(uid, bot_id):
    """برگرداندن آخرین نسخه‌ی منتشرشده به پیش‌نویس"""
    if not get_bot(bot_id, uid):
        return jsonify(error="ربات پیدا نشد"), 404
    d = app_doc(bot_id) or {}
    vs = d.get("versions") or []
    if not vs:
        return jsonify(error="نسخه‌ی قبلی وجود نداره"), 400
    prev = vs[-1]
    db.apps.update_one({"_id": bot_id}, {"$set": {"draft": prev["app"], "updated": now()},
                                         "$pop": {"versions": 1}})
    return jsonify(ok=True, draft=prev["app"])


@app.post("/api/bots/<bot_id>/app/link")
@authed
def api_app_link(uid, bot_id):
    """افزودن دکمه‌ی «باز کردن مینی‌اپ» به بخش شروع ربات (از مسیر رسمی کانفیگ با sanitize)"""
    from ai import sanitize
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    cfg = json.loads(json.dumps(bot["config"]))
    start = cfg["nodes"].get(cfg["start"])
    if not start:
        return jsonify(error="بخش شروع پیدا نشد"), 400
    rows = start.get("buttons") or []
    label = "باز کردن مینی‌اپ"
    for row in rows:
        for b in row:
            if b.get("app") is not None:
                return jsonify(ok=True, added=False)
    placed = False
    for row in rows:
        if len(row) < 3 and not any(b.get("kb") == "reply" for b in row):
            row.insert(0, {"text": label, "app": "1"})
            placed = True
            break
    if not placed:
        if len(rows) >= 6:
            return jsonify(error="بخش شروع به سقف دکمه رسیده؛ اول جای خالی بساز"), 400
        rows.insert(0, [{"text": label, "app": "1"}])
    start["buttons"] = rows
    cfg = sanitize(cfg, strict=True, media=own_app_media(uid), nodes_cap=limits_of(uid)["nodes"])
    db.bots.update_one({"_id": bot["_id"]}, {"$set": {"config": cfg, "updated": now()}})
    sync_commands(bot, cfg)
    return jsonify(ok=True, added=True)


@app.get("/api/bots/<bot_id>/app/stats")
@authed
def api_app_stats(uid, bot_id):
    if not get_bot(bot_id, uid):
        return jsonify(error="ربات پیدا نشد"), 404
    day = tehran_day()
    d = app_doc(bot_id) or {}

    def get(kind):
        doc = db.app_ev.find_one({"_id": f"{bot_id}:{kind}:{day}"}) or {}
        return {"n": int(doc.get("n", 0)), "u": len(doc.get("u") or {})}
    opens = get("open")
    tops = []
    for r in db.app_ev.find({"_id": {"$regex": f"^{re.escape(bot_id)}:cb:"}}):
        parts = str(r["_id"]).split(":")
        if len(parts) >= 4:
            tops.append({"block": parts[-1], "n": int(r.get("n", 0))})
    tops.sort(key=lambda x: -x["n"])
    dpub = d.get("pub") or {}
    names = {}
    for s in (dpub.get("screens") or {}).values():
        for b in s.get("blocks") or []:
            names[b.get("id") or ""] = b.get("title") or b.get("text", "")[:24] or b.get("t", "")
    return jsonify(on=bool(d.get("pub")), ver=int(d.get("ver", 0)),
                   today={"open": opens["n"], "uniq": opens["u"], "form": get("form")["n"], "pay": get("pay")["n"]},
                   top=[{**t, "name": names.get(t["block"], t["block"])} for t in tops[:5]])


@app.post("/api/bots/<bot_id>/app/template")
@authed
def api_app_template(uid, bot_id):
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    t = APP_TEMPLATES.get(str((request.get_json(silent=True) or {}).get("id") or ""))
    if not t:
        return jsonify(error="قالب پیدا نشد"), 404
    cost = cut(uid, APP_TPL_COST)
    if cost and not spend(uid, cost, "app_tpl"):
        return jsonify(error=f"توکن کافی نداری. این قالب {cost} توکن می‌خواهد.", need=cost, wallet=wallet_info(uid)), 402
    warns = []
    try:
        cleaned = sanitize_app(t["app"], strict=True, media=own_app_media(uid), warns=warns,
                               blocks_cap=_app_caps(uid)["blocks"], node_ids=set(bot["config"]["nodes"].keys()))
    except ValueError as e:
        if cost:
            refund(uid, cost)
        return jsonify(error=str(e)), 400
    db.apps.update_one({"_id": bot_id}, {"$set": {"draft": cleaned, "owner": uid, "updated": now()}}, upsert=True)
    return jsonify(ok=True, draft=cleaned, wallet=wallet_info(uid))


# ───────────────────────── ساخت مینی‌اپ با هوش مصنوعی ─────────────────────────
_SP_APP = """You design Telegram Mini Apps as a JSON config that a fixed, safe renderer displays. No code is ever executed; you only fill a declarative schema.

LANGUAGE RULE (strict): write "thinking", "ideas" and EVERY user-facing text in Persian (فارسی). JSON keys, screen ids and variable names stay English.

STYLE RULE: texts are short, clear and meaningful. No emoji decoration; at most one where it truly helps. Use [براکت] placeholders for unknown facts (prices, names, links) and mention them in "thinking".

Output ONLY one valid JSON object:
{
 "thinking": "2-4 short Persian sentences: what you built and what the owner should edit (placeholders, missing media).",
 "ideas": ["...upgrade idea in Persian, max 60 chars", "..."],
 "app": { ...mini-app config below... }
}

"app" schema:
{
 "v": 1,
 "theme": {"mode": "auto"|"dark"|"light", "accent": "#RRGGBB", "radius": 0-28, "font": "vazir"|"oxanium_vazir"|"system", "digits": "latin"|"fa"},
 "nav": {"type": "tabs"|"none", "items": ["screen_id", ...] (max 6)},
 "home": "screen_id",
 "screens": {
   "<screen_id>": {
     "title": "short Persian label", "icon": "home|shop|form|star|info|users|phone|image|chat|gift|clock|trophy",
     "blocks": [ ...max 40 blocks, unique lowercase ids like b1, hero1... ]
   }
 }
}

BLOCKS (field "t"):
- {"t":"hero","title":"≤80","text":"≤300","cta":{"text":"≤24","do":[actions]}}  (cta optional)
- {"t":"text","text":"HTML subset of Telegram: <b> <i> <u> <s> <code> <blockquote> <a href=\"https://...\">; close every tag"}
- {"t":"image","caption":"≤200","url":"https://..."} or "media":"<media_id>"
- {"t":"gallery","items":[{"url":"https://..."} x2-10]} | {"t":"video"/"audio","url":"https://..."}
- {"t":"buttons","rows":[[{"text":"≤24","do":[actions]} x≤3] x≤4]}
- {"t":"cards","items":[{"title":"≤60","text":"≤200","url":"https://image","do":[actions](optional)} x≤50]}
- {"t":"list","table":"orders","scope":"my"|"all","limit":1-20,"line":"#{n} · {field}","empty":"..."}
- {"t":"form","title":"","fields":[{"k":"english_name","label":"Persian","type":"text|number|phone|email|select|date","req":true,"opts":["..",".."]}] max 12,
    "save":{"table":"orders"} or {"vars":{"field":"varname"}}, "notify":true, "ticket":true(optional),"tag":"≤20","done":"Persian thanks"}
- {"t":"stat","var":"points","label":"≤40"} | {"t":"board","var":"points"|"refs","top":3-20,"label":"≤40"}
- {"t":"faq","items":[{"q":"≤120","a":"≤500"}]} | {"t":"banner","style":"info|ok|warn","text":"≤300","when":cond(optional)}
- {"t":"countdown","to":unix_seconds_future,"title":"","done":""} | {"t":"links","items":[{"label":"≤40","url":"https://t.me/..."}]}
- {"t":"pay","stars":1-10000,"title":"≤32","desc":"≤255","text":"Persian success message","do":[actions after payment]} (only if the user wants payment)
- {"t":"ai","prompt":"assistant instructions in Persian ≤1500","daily":15,"memory":3,"greeting":"≤200"} (smart chat; costs the owner tokens; use only when fixed menus cannot work)
- {"t":"divider"} | {"t":"spacer","h":8-80}

ACTIONS ("do", max 8 per handler; mix freely):
Engine (state stored in the SAME variables as the owner's bot, shared memory):
 {"op":"set"/"add"/"clear"/"random","var":"name","value":"..."} (add value numeric like "1" or "-3"; random like "1-6")
 {"op":"notify","value":"text to the owner"} | {"op":"remind","minutes":60,"value":"text","goto":"<bot node_id>"} (optional)
 {"op":"dice","var":"roll","emoji":"🎲"} | {"op":"pick","var":"prize","value":"a|b|c"}
 {"op":"db_add","table":"orders","data":{"field":"{...}"}} | {"op":"db_get","table":"orders","var":"o"} | {"op":"db_set"/"db_inc"/"db_del",...}
UI: {"op":"goto","screen":"screen_id"} | {"op":"url","url":"https://..."} | {"op":"copy","text":"..."} | {"op":"share","text":"..."}
    {"op":"toast","text":"..."} | {"op":"close"} | {"op":"back"} | {"op":"refresh"} | {"op":"send","node":"<bot node_id>"} (sends one of the bot's sections to the user's chat)

VARIABLES: {var} and {var|fallback} placeholders work exactly like the bot engine ({name} = the user's first name). Use the CURRENT VARS/TABLES given to you when they fit (shared memory with the chat bot), otherwise declare new ones in thinking so the owner adds them.

RULES: every "goto" screen must exist; home must be a screen; give each screen a title; a shop needs products + an order path; never invent image URLs — use the MEDIA LIBRARY ids if provided, else omit media and say so in "thinking"; keep the total under 60 blocks; 2-5 screens is usually right. Persian texts everywhere."""

_FALLBACK_APP_THINK = "مینی‌اپ رو طبق توضیحت چیدم. متن‌ها و جای [براکت]‌ها رو توی تب مینی‌اپ می‌تونی عوض کنی."


def _app_brief(uid, bot):
    """خلاصه‌ی ربات و رسانه برای هوش مصنوعی"""
    cfg = bot["config"]
    parts = ["CURRENT BOT CONTEXT (reuse these names so the mini-app shares memory with the chat bot):"]
    ctx = {"name": cfg.get("name", ""), "vars": cfg.get("vars", {}), "globals": cfg.get("globals", {}),
           "dbfields": cfg.get("dbfields", {}),
           "nodes": [{"id": k, "title": v.get("title", "")} for k, v in cfg.get("nodes", {}).items()]}
    parts.append(json.dumps(ctx, ensure_ascii=False))
    ms = [{"id": m["id"], "kind": m["kind"], "name": m["name"]} for m in media_list(uid)]
    parts.append("MEDIA LIBRARY (use ids only): " + (json.dumps(ms, ensure_ascii=False) if ms else "empty"))
    return "\n".join(parts)


def _app_gen_cost(prompt, uid):
    if BILLING == "fixed":
        return cut(uid, APP_GEN_COST)
    p = est_tokens(_SP_APP) + est_tokens(prompt) + 400
    return calc_cost(p, min(AI_MAX_TOKENS, 4000), uid=uid)


@app.post("/api/bots/<bot_id>/app/generate")
@authed
def api_app_generate(uid, bot_id):
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    prompt = str((request.get_json(silent=True) or {}).get("prompt", "")).strip()[:4000]
    if len(prompt) < 5:
        return jsonify(error="توضیح خیلی کوتاهه"), 400
    if not rate_ok(f"appgen:{uid}", 6, 60):
        return jsonify(error="کمی آروم‌تر؛ چند لحظه بعد دوباره امتحان کن"), 429
    for j in db.jobs.find({"uid": uid, "kind": "app", "status": {"$in": ["running", "saving"]}}):
        if (naive() - naive(j["t"])).total_seconds() < 240:
            return jsonify(error="یه کار دیگه‌ات هنوز در حال انجامه، چند لحظه صبر کن"), 409
    reserve = _app_gen_cost(prompt, uid)
    if not hold(uid, reserve):
        return jsonify(error=f"توکن کافی نداری. این ساخت تا سقف {reserve} توکن هزینه دارد.", need=reserve, wallet=wallet_info(uid)), 402
    jid = secrets.token_hex(8)
    db.jobs.insert_one({"_id": jid, "uid": uid, "kind": "app", "status": "running", "t": now()})
    threading.Thread(target=app_gen_job, args=(jid, uid, bot_id, prompt, reserve), daemon=True).start()
    return jsonify(job=jid, hold=reserve, wallet=wallet_info(uid))


@app.get("/api/appjobs/<jid>")
@authed
def api_app_job(uid, jid):
    j = db.jobs.find_one({"_id": jid, "uid": uid, "kind": "app"})
    if not j:
        return jsonify(error="کار پیدا نشد"), 404
    if j["status"] == "running" and (naive() - naive(j["t"])).total_seconds() > JOB_TIMEOUT:      # مثل api_job: کار رهاشده بعد از ری‌استارت منقضی می‌شود
        db.jobs.find_one_and_update({"_id": jid, "status": "running"},
                                    {"$set": {"status": "error", "error": "ساخت بیش از حد طول کشید و چیزی از توکن‌هات کم نشد. دوباره امتحان کن."}})
        j = db.jobs.find_one({"_id": jid})
    out = {"status": j["status"], "wallet": wallet_info(uid)}
    if j.get("prog"):
        out["prog"] = {k: j["prog"].get(k) for k in ("p", "st", "th") if k in j["prog"]}
    if j["status"] == "done":
        out.update(app=j.get("app"), ideas=j.get("ideas", []), cost=j.get("cost", 0), thinking=j.get("thinking", ""))
    elif j["status"] == "error":
        out["error"] = j.get("error", "ناموفق بود")
    return jsonify(out)


def app_gen_job(jid, uid, bot_id, prompt, reserve):
    """کار پس‌زمینه‌ی ساخت مینی‌اپ: استریم با پیشرفت زنده، پاک‌سازی، یک بار بازخورد lint و کسر هزینه‌ی واقعی"""
    acc = []
    _prog.cb = Progress(jid)
    try:
        bot = db.bots.find_one({"_id": ObjectId(bot_id), "owner": uid})
        if not bot:
            raise ValueError("ربات پیدا نشد")
        node_ids = set(bot["config"]["nodes"].keys())
        media_ids = own_app_media(uid)
        blocks_cap = _app_caps(uid)["blocks"]
        user_msg = f"MINI-APP REQUEST:\n{prompt}\n\n" + _app_brief(uid, bot)
        best, last, feedback = None, None, ""
        for attempt in (0, 1):
            try:
                txt, usage = llm_run([{"role": "system", "content": _SP_APP + feedback},
                                      {"role": "user", "content": user_msg}], AI_MAX_TOKENS)
                acc.append(usage)
                _prog.cb.stage("validate", 92.0)
                m = re.search(r"\{.*\}", txt, re.S)
                if not m:
                    raise ValueError("پاسخ هوش مصنوعی شامل JSON نبود")
                raw = json.loads(m.group(0))
                if not isinstance(raw, dict) or not isinstance(raw.get("app"), dict):
                    raise ValueError("پاسخ فاقد بخش app بود")
                warns = []
                app_cfg = sanitize_app(raw["app"], strict=False, media=media_ids, warns=warns,
                                       blocks_cap=blocks_cap, node_ids=node_ids)
                thinking = str(raw.get("thinking") or "").strip()[:900]
                ideas = [str(x).strip()[:80] for x in (raw.get("ideas") if isinstance(raw.get("ideas"), list) else []) if str(x).strip()][:3]
            except (ValueError, KeyError, TypeError) as e:
                last = e
                feedback = "\nYour previous reply was rejected: " + str(e)[:200] + " Return one valid JSON object."
                continue
            problems = lint_app(app_cfg, bot["config"]) + [f"اعتبارسنج چیزی را حذف یا اصلاح کرد: {w}" for w in warns]
            if problems and attempt == 0:
                best = (thinking, app_cfg, ideas)
                feedback = "\nFix these logic problems and return the FULL config again: " + "؛ ".join(problems[:6])
                continue
            best = (thinking, app_cfg, ideas)
            break
        if not best:
            raise last or ValueError("ناموفق بود")
        thinking, app_cfg, ideas = best
        _prog.cb.stage("save", 98.0)
        cost = reserve if BILLING == "fixed" else min(reserve, calc_cost(sum(x[0] for x in acc), sum(x[1] for x in acc), uid=uid))
        cost = charge_up_to(uid, cost, "app_gen")
        db.jobs.update_one({"_id": jid, "status": {"$in": ["running", "saving"]}},
                           {"$set": {"status": "done", "app": app_cfg, "ideas": ideas, "cost": cost,
                                     "thinking": thinking or _FALLBACK_APP_THINK}})
    except Exception as e:
        log.exception("app generate failed")
        db.jobs.find_one_and_update({"_id": jid, "status": {"$in": ["running", "saving"]}},
                                    {"$set": {"status": "error", "error": "ساخت مینی‌اپ ناموفق بود و چیزی از توکن‌هات کم نشد. دوباره امتحان کن."}})
    finally:
        _prog.cb = None


# ───────────────────────── رانتایم عمومی: صفحه و مسیرهای /rt ─────────────────────────
_MAPP_CACHE = ["", ""]


@app.get("/a/<bot_id>")
def app_page(bot_id):
    """صفحه‌ی مینی‌اپ برای کاربر نهایی (و ?preview=1 برای پیش‌نمایش سازنده)؛ اسکریپت با پارامتر نسخه (کش قدیمی نمی‌ماند)"""
    if _MAPP_CACHE[0] != BUILD + str(assets_stamp()):
        try:
            with open(os.path.join(APP_DIR, "mapp.html"), encoding="utf-8") as f:
                html = f.read()
        except OSError:
            html = ""
        html = re.sub(r'(src)="(/static/[^"]+)"',
                      lambda m: m.group(1) + '="' + m.group(2) + "?v=" + asset_v(m.group(2).lstrip("/")) + '"', html)

        _MAPP_CACHE[:] = [BUILD + str(assets_stamp()), html]
    resp = Response(_MAPP_CACHE[1], mimetype="text/html")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


def _run_do(acts, env, dirs):
    """اکشن‌های هندلر: موتور ربات همین‌جا اجرا می‌شود، اکشن‌های رابط به‌صورت دستور برای کلاینت برمی‌گردند"""
    for a in acts or []:
        op = a.get("op")
        if op in ACT_OPS:
            run_actions([a], env)
        elif op == "goto":
            dirs.append({"a": "goto", "screen": a["screen"]})
        elif op == "url":
            dirs.append({"a": "url", "url": a["url"]})
        elif op == "copy":
            dirs.append({"a": "copy", "text": fill(a["text"], env)})
        elif op == "share":
            dirs.append({"a": "share", "text": fill(a["text"], env)})
        elif op == "toast":
            dirs.append({"a": "toast", "text": fill(a["text"], env)})
        elif op in ("close", "back", "refresh"):
            dirs.append({"a": op})
        elif op == "send":
            try:
                send_node(env, a["node"])
            except Exception:
                log.exception("app send_node failed")
    try:
        env.save()
    except Exception:
        log.exception("app env save failed")


@app.post("/rt/<bot_id>/boot")
def rt_boot(bot_id):
    """شروع مینی‌اپ: راستی‌آزمایی initData با توکن همان ربات + کانفیگ منتشرشده + متغیرهای کاربر"""
    bot, uid, user, err = _rt_auth(bot_id)
    if err:
        return err
    if not rate_ok(f"rtb:{bot_id}:{uid}", 30, 60):
        return jsonify(error="کمی آروم‌تر"), 429
    if not _daily_cap(bot_id, "boot", APP_DAILY_BOOT):
        return jsonify(error="مینی‌اپ این ربات امروز به سقف استفاده رسید. فردا دوباره امتحان کن."), 429
    etag, pub, lk = _pub(bot_id)
    if not pub:
        return jsonify(status="none", error="این مینی‌اپ هنوز منتشر نشده.")
    _ev(bot_id, "open")
    try:
        db.app_ev.update_one({"_id": f"{bot_id}:open:{tehran_day()}"},
                             {"$inc": {"n": 1}, "$setOnInsert": {"t": now(), "u": {}}}, upsert=True)
        if (db.app_ev.find_one({"_id": f"{bot_id}:open:{tehran_day()}"}) or {}).get("n", 0) <= 3000:
            db.app_ev.update_one({"_id": f"{bot_id}:open:{tehran_day()}"}, {"$set": {f"u.{uid}": 1}}, upsert=True)
    except Exception:
        pass
    vars_, glo = _vars_snapshot(bot_id, uid, bot["config"])
    return jsonify(status="ok", ver=int(pub.get("ver", 1)), app=pub, media=_media_map(pub, bot.get("owner")),
                   vars=vars_, globals=glo,
                   user={"id": uid, "first_name": user.get("first_name") or "", "username": user.get("username") or "",
                         "is_owner": 1 if uid == bot["owner"] else 0},
                   bot={"name": bot.get("name", ""), "username": bot.get("username") or ""})


def _media_map(pub, owner):
    """شناسه‌ی رسانه‌های کانفیگ منتشرشده → لینک امضاشده (فقط مال خودِ سازنده؛ بدون امضا باز نمی‌شود)"""
    from core import media_sig
    ids = set()

    def take(b):
        if isinstance(b, dict) and b.get("media"):
            ids.add(str(b["media"]))
    for s in (pub.get("screens") or {}).values():
        for b in s.get("blocks") or []:
            take(b)
            for it in b.get("items") or []:
                take(it if isinstance(it, dict) else {})
    out = {}
    for mid in list(ids)[:60]:
        try:
            m = db.media.find_one({"_id": ObjectId(mid), "owner": owner}, {"kind": 1, "mime": 1})
        except (InvalidId, TypeError):
            m = None
        if m:
            out[mid] = {"url": f"/m/{mid}?s={media_sig(mid)}", "kind": m.get("kind", "")}
    return out


@app.post("/rt/<bot_id>/act")
def rt_act(bot_id):
    """اجرای یک اکشن: کلاینت فقط شناسه‌ی هندلر (hid) می‌فرستد؛ اکشن از کانفیگ منتشرشده خوانده می‌شود"""
    bot, uid, user, err = _rt_auth(bot_id)
    if err:
        return err
    if not rate_ok(f"rta:{bot_id}:{uid}", 40, 60):
        return jsonify(error="کمی آروم‌تر"), 429
    if not _daily_cap(bot_id, "act", APP_DAILY_ACT):
        return jsonify(error="مینی‌اپ این ربات امروز به سقف استفاده رسید."), 429
    body = request.get_json(silent=True) or {}
    hid = str(body.get("h") or "")[:40]
    etag, pub, lk = _pub(bot_id)
    if not pub:
        return jsonify(error="این مینی‌اپ الان در دسترس نیست."), 404
    el = lk.get(hid)
    if not el:
        return jsonify(error="این کنش در دسترس نیست."), 400
    env = Env(bot, _child_token(bot), uid, {"id": uid, "first_name": user.get("first_name") or "",
                                            "username": user.get("username") or "", "language_code": user.get("language_code") or ""},
              text=str(body.get("text") or "")[:1000])
    dirs = []
    if el.get("t") == "pay":
        r = tg(_child_token(bot), "createInvoiceLink", title=el.get("title") or "خرید",
               description=(el.get("desc") or "خرید داخل مینی‌اپ")[:255],
               payload=f"ap|{el.get('id')}|{uid}", currency="XTR",
               prices=[{"label": (el.get("title") or "خرید")[:32], "amount": int(el.get("stars", 1))}])
        if not r.get("ok"):
            log.warning("app invoice failed: %s", r.get("description"))
            return jsonify(error="ساخت فاکتور ناموفق بود، کمی بعد دوباره امتحان کن"), 502
        return jsonify(ok=True, invoice=r["result"], ver=int(pub.get("ver", 1)))
    if el.get("t") == "ai":
        return _rt_ai(bot, bot_id, uid, user, el, body)
    _run_do(el.get("do"), env, dirs)
    _ev(bot_id, "clk", el.get("id") or hid)
    db.app_ev.update_one({"_id": f"{bot_id}:cb:{tehran_day()}:{(el.get('id') or hid)[:40]}"},
                         {"$inc": {"n": 1}, "$setOnInsert": {"t": now(), "b": (el.get("id") or hid)[:40]}}, upsert=True)
    vars_, glo = _vars_snapshot(bot_id, uid, bot["config"])
    return jsonify(ok=True, dirs=dirs, vars=vars_, globals=glo, ver=int(pub.get("ver", 1)))


def _rt_ai(bot, bot_id, uid, user, el, body):
    """گفتگوی هوشمند بلوک ai: سقف روزانه، حافظه‌ی یک‌روزه، هزینه از صاحب ربات"""
    from core import AI_CHAT_MODEL, AI_NODE_MAX_TOKENS
    from ai import has_foreign, scrub_foreign
    from engine import AI_CHILD_PROMPT
    text = str(body.get("text") or "").strip()[:1500]
    if not text:
        return jsonify(error="پیامت را بنویس"), 400
    day = tehran_day()
    try:
        d = db.aiuse.find_one_and_update({"_id": f"{bot_id}:app:{uid}:{day}"}, {"$inc": {"n": 1}}, upsert=True,
                                         return_document=True)
        if int(d.get("n", 1)) > int(el.get("daily", 15)):
            return jsonify(error="سقف پیام‌های امروزت در این بخش پر شده."), 429
    except Exception:
        pass
    if not ai_precheck(bot["owner"]):
        return jsonify(error="این بخش فعلاً در دسترس نیست. کمی بعد دوباره امتحان کن."), 402
    key = f"{bot_id}:{uid}"
    st = db.appai.find_one({"_id": key}) or {}
    hist = (st.get("h") or [])[-int(el.get("memory", 3)) * 2:]
    env = Env(bot, _child_token(bot), uid, {"id": uid, "first_name": user.get("first_name") or "",
                                            "username": user.get("username") or ""}, text=text)
    system = AI_CHILD_PROMPT.replace("{bot}", bot.get("name", "")) + fill(el["prompt"], env)
    try:
        from engine import kb_search as _kb_search
        know = _kb_search(bot_id, text, 2)
        if know:
            system += "\n\nدانش کسب‌وکار (فقط بر اساس این جواب بده و از دانش بیرون چیز نساز):\n" + \
                "\n".join(f"- {t}: {x}" for t, x in know)
    except Exception:
        log.exception("app kb inject failed")
    tools = []
    try:
        from engine import agent_tools_block
        tb, tools = agent_tools_block({"t": el}, bot["config"])
        if tb:
            system += "\n\n" + tb
    except Exception:
        log.exception("app tools block failed")
    try:
        reply, (pt, ct) = llm_post([{"role": "system", "content": system}, *hist, {"role": "user", "content": text}],
                                   AI_NODE_MAX_TOKENS, temperature=0.6, timeout=60, model=AI_CHAT_MODEL)
    except Exception:
        log.exception("app ai failed")
        return jsonify(error="الان نتونستم جواب بدم. دوباره امتحان کن."), 502
    try:
        from engine import agent_tool_round
        reply, pt, ct = agent_tool_round(bot_id, system, hist, text, reply, pt, ct, tools, AI_NODE_MAX_TOKENS)
    except Exception:
        log.exception("app tool round failed")
    ai_postcharge(bot["owner"], bot_id, pt, ct)
    reply = scrub_foreign(reply) if has_foreign(reply) else reply
    reply = (reply or "").strip()[:1500] or "نتونستم جوابی پیدا کنم، یه جور دیگه بپرس."
    hist = (hist + [{"role": "user", "content": text[:500]}, {"role": "assistant", "content": reply[:500]}])[-12:]
    try:
        db.appai.update_one({"_id": key}, {"$set": {"h": hist, "t": now()}}, upsert=True)
    except Exception:
        pass
    _ev(bot_id, "clk", el.get("id") or "ai")
    return jsonify(ok=True, reply=reply, ver=int((_pub(bot_id)[1] or {}).get("ver", 1)))


@app.post("/rt/<bot_id>/form")
def rt_form(bot_id):
    """ثبت فرم مینی‌اپ: اعتبارسنجی فیلدها، ذخیره در جدول/متغیر، خبر به صاحب (تیکت یا notify)، یک‌بار ثبت"""
    bot, uid, user, err = _rt_auth(bot_id)
    if err:
        return err
    if not rate_ok(f"rtf:{bot_id}:{uid}", 20, 60):
        return jsonify(error="کمی آروم‌تر"), 429
    if not _daily_cap(bot_id, "form", APP_DAILY_FORM):
        return jsonify(error="مینی‌اپ این ربات امروز به سقف استفاده رسید."), 429
    body = request.get_json(silent=True) or {}
    bid = str(body.get("block") or "")[:40]
    etag, pub, lk = _pub(bot_id)
    if not pub:
        return jsonify(error="این مینی‌اپ الان در دسترس نیست."), 404
    el = lk.get(bid)
    if not el or el.get("t") != "form":
        return jsonify(error="این فرم در دسترس نیست."), 400
    k = str(body.get("k") or "")
    if not re.fullmatch(r"[A-Za-z0-9_\-]{6,40}", k):
        return jsonify(error="درخواست نامعتبر است"), 400
    try:
        db.appfm.insert_one({"_id": f"{bot_id}:{uid}:{k}", "t": now()})
    except DuplicateKeyError:
        return jsonify(ok=True, done=el.get("done") or "ثبت شد. ممنون!", dup=True)
    values = body.get("values") if isinstance(body.get("values"), dict) else {}
    qa, clean = [], {}
    for f in el.get("fields") or []:
        kk, ty = f["k"], f.get("type", "text")
        v = str(values.get(kk) or "").strip()[:200]
        if ty == "number" and v and to_num(v) is None:
            return jsonify(error=f"«{f['label']}» باید عدد باشد"), 400
        if ty == "phone" and v and not re.fullmatch(r"\+?\d{8,15}", re.sub(r"[\s\-()]", "", v.translate(_DIG))):
            return jsonify(error=f"«{f['label']}» شماره‌ی تماس درستی نیست"), 400
        if ty == "email" and v and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]{2,}", v):
            return jsonify(error=f"«{f['label']}» ایمیل درستی نیست"), 400
        if ty == "select" and v and v not in (f.get("opts") or []):
            v = ""
        if ty == "date" and v and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            v = ""
        if f.get("req") and not v:
            return jsonify(error=f"«{f['label']}» را پر کن"), 400
        clean[kk] = v
        qa.append([f["label"], v])
    env = Env(bot, _child_token(bot), uid, {"id": uid, "first_name": user.get("first_name") or "",
                                            "username": user.get("username") or "", "language_code": user.get("language_code") or ""})
    sv = el.get("save") or {}
    tab = sv.get("table")
    if tab and TAB_RE.match(tab):
        shared = False
        try:
            cap = MAX_RECORDS_SHARED if shared else MAX_RECORDS_USER
            q = {"bot": bot_id, "t": tab} if shared else {"bot": bot_id, "t": tab, "u": uid}
            if db.recs.count_documents(q) < cap:
                mx = db.recs.find_one(q, sort=[("n", -1)], projection={"n": 1})
                db.recs.insert_one({"bot": bot_id, "t": tab, "u": uid, "n": int((mx or {}).get("n", 0)) + 1,
                                    "d": {kk: v[:200] for kk, v in clean.items()}, "ct": now()})
        except Exception:
            log.exception("app form db_add failed")
    for fk, var in (sv.get("vars") or {}).items():
        env.set(var, clean.get(fk, ""))
    title = el.get("title") or "فرم مینی‌اپ"
    body_txt = "\n".join(f"{q}\n» {a}" for q, a in qa)
    tk_no = None
    if el.get("ticket"):
        try:
            tk_no, _sent = ticket_open(env, bid, {"tag": el.get("tag") or "مینی‌اپ", "title": title}, body=f"{title}\n\n{body_txt}")
        except Exception:
            log.exception("app form ticket failed")
    elif el.get("notify", True):
        try:
            to_owner(env, text=f"فرم مینی‌اپ — {title}\n{who(env)}\n\n{body_txt}"[:3900])
        except Exception:
            log.exception("app form notify failed")
    try:
        save_submission(env, bid, {"title": title}, qa=qa)
    except Exception:
        pass
    _ev(bot_id, "form")
    env.save()
    vars_, glo = _vars_snapshot(bot_id, uid, bot["config"])
    return jsonify(ok=True, done=fill(el.get("done") or "ثبت شد. ممنون!", env), vars=vars_, globals=glo,
                   ticket=tk_no, ver=int(pub.get("ver", 1)))


@app.get("/rt/<bot_id>/data")
def rt_data(bot_id):
    """داده‌ی زنده: متغیرهای کاربر (با ETag) یا محتوای محاسبه‌شده‌ی بلوک list/board"""
    bot, uid, user, err = _rt_auth(bot_id)
    if err:
        return err
    if not rate_ok(f"rtd:{bot_id}:{uid}", 60, 60):
        return jsonify(error="کمی آروم‌تر"), 429
    etag, pub, lk = _pub(bot_id)
    env = Env(bot, _child_token(bot), uid, {"id": uid, "first_name": user.get("first_name") or "",
                                            "username": user.get("username") or ""})
    b = request.args.get("b", "")
    if b and pub:
        el = lk.get(b)
        if el and el.get("t") == "list":
            try:
                q = _rec_query(env, {"table": el["table"], "scope": el.get("scope", "my"), "when": el.get("when")})
                cur = db.recs.find(q, projection={"n": 1, "u": 1, "d": 1})
                cur = cur.sort("n", 1 if el.get("order") == "old" else -1).limit(int(el.get("limit", 10)))
                lines = [rec_line(env, r, el.get("line") or "#{n} · {text}") for r in cur]
            except Exception:
                log.exception("app list failed")
                lines = []
            return jsonify(items=lines, empty=el.get("empty") or "هنوز چیزی ثبت نشده.")
        if el and el.get("t") == "board":
            try:
                return jsonify(text=board_text(env, {"var": el["var"], "top": el.get("top", 10), "label": el.get("label") or "برترین‌ها"}))
            except Exception:
                log.exception("app board failed")
                return jsonify(text=el.get("label") or "برترین‌ها")
        if el and el.get("t") == "chart":
            key, fld = el.get("key") or "", el["field"]
            try:
                agg, order = {}, []
                for r in db.recs.find({"bot": bot_id, "t": el["table"]}, projection={"d": 1}).limit(300):
                    d = r.get("d") or {}
                    k = (str(d.get(key, "کل"))[:24] if key else "کل") or "کل"
                    v = to_num(d.get(fld)) or 0
                    if k not in agg:
                        agg[k] = 0
                        order.append(k)
                    agg[k] += v
                rows = [{"k": k, "n": agg[k]} for k in order[:8]]
            except Exception:
                log.exception("app chart failed")
                rows = []
            return jsonify(rows=rows, kind=el.get("kind", "bar"), label=el.get("label") or "")
        if el and el.get("t") == "inbox":
            if uid != bot.get("owner"):
                return jsonify(items=[], empty="این بخش فقط برای صاحب ربات است.")
            docs = list(db.submissions.find({"bot_id": bot_id}).sort("t", -1).limit(int(el.get("limit", 8))))
            items = []
            for d in docs:
                qa = " | ".join(f"{a}: {b}" for a, b in (d.get("qa") or [])[:4])[:180]
                who = (d.get("name") or "") + ((" @" + d["un"]) if d.get("un") else "")
                items.append({"t": (d.get("title") or "فرم")[:40], "d": (who + ": " + (qa or (d.get("text") or "")))[:220]})
            return jsonify(items=items, empty="هنوز پاسخی ثبت نشده.")
        return jsonify(items=[], empty="") if el else (jsonify(error="بلوک پیدا نشد"), 404)
    uv = db.uvars.find_one({"_id": f"{bot_id}:{uid}"}) or {}
    et = f'W/"{str(int((_pub(bot_id)[1] or {}).get("ver", 1)))}-{int((uv.get("t") or naive()).timestamp())}"'
    if request.headers.get("If-None-Match") == et:
        return "", 304
    vars_, glo = _vars_snapshot(bot_id, uid, bot["config"])
    resp = jsonify(vars=vars_, globals=glo, ver=int((pub or {}).get("ver", 1)))
    resp.headers["ETag"] = et
    return resp


# ───────────────────────── تست خودکار (بدون شبکه) ─────────────────────────
def selftest():
    """تست سریع هسته: پاک‌سازی، رد ورودی خراب، lint و قالب‌ها"""
    ok = lambda name: print("ok —", name)
    app1 = sanitize_app(json.loads(json.dumps(APP_TEMPLATES["shop"]["app"])), strict=True)
    assert app1["home"] == "home" and app1["screens"]["form"]["blocks"][1]["t"] == "form"
    ok("sanitize_app قالب فروشگاه")
    try:
        sanitize_app({"screens": {"home": {"blocks": [{"t": "text", "text": "<script>x</script>"}]}}}, strict=True)
        raise AssertionError("script passed")
    except ValueError:
        ok("رد تگ اسکریپت (نوع بلوک ناشناس)")
    dirty = {"screens": {"home": {"blocks": [{"t": "text", "text": "hi"}, {"t": "pay", "stars": "5", "title": "p"}]}}}
    warns = []
    cleaned = sanitize_app(dirty, strict=False, warns=warns)
    assert warns and cleaned["screens"]["home"]["blocks"]
    ok(f"strict=False اصلاح می‌کند ({len(warns)} هشدار)")
    li = lint_app(APP_TEMPLATES["club"]["app"], {"vars": {"points": "0"}})
    ok(f"lint_app ({len(li)} مورد)")
    u = verify_init_data("hash=bad")
    assert u is None
    ok("initData نامعتبر رد شد")
    print("selftest passed")


if __name__ == "__main__":
    selftest()
