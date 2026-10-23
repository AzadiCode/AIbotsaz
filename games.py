# -*- coding: utf-8 -*-
"""
games.py — مرکز بازی گروهی (B1): موتور بازی سمت سرور

اصل: همه‌ی شانس، زمان و پاسخ درست سمت سرور است؛ کلاینت فقط می‌کشد و لمس را می‌فرستد.
هیچ کد کاربری اجرا نمی‌شود؛ جلسه‌ی هر بازی یک سند Mongo با TTL است.

بخش‌ها:
  • اقتصاد سکه‌ی مجازی (db.gusers): سکه، بهترین رکورد، چک‌این روزانه با استریک، موجودی آیتم
  • جلسه‌ی بازی (db.gsess با TTL): ۹ بازی — کوییز، حافظه، لمس سریع، گردونه، حدس کلمه،
    ریاضی سریع، سرعت تایپ، پازل اعداد و دوئل XO دونفره
  • جدول‌های دوره‌ای (db.gscore): روزانه / هفتگی / فصل (ماهانه)
  • فروشگاه سکه‌ای (آیتم‌های کانفیگ ربات) و ضدتقلب (rate limit + یک پاسخ برای هر سؤال)
  • داخل گروه: دستور /play و /top و کارت نتیجه؛ داخل چت خصوصی همان دستورها
  • رانتایم مینی‌اپ: مسیرهای /rt/<bot_id>/game/* (احراز همان توکنِ ربات فرزند، مثل بقیه‌ی /rt)

وابستگی: core ← ai ← engine ← games (webapp و app می‌توانند import کنند)
"""
import re, json, random, time

from flask import jsonify, request
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core import app, db, log, naive, now, rate_ok, tehran_day, tg
from engine import tg_html

GAMES_FA = {"quiz": "کوییز", "memory": "حافظه", "tap": "لمس سریع", "wheel": "گردونه", "word": "حدس کلمه",
            "math": "ریاضی سریع", "typing": "سرعت تایپ", "puzzle": "پازل اعداد", "xo": "دوئل XO"}
GAME_IDS = tuple(GAMES_FA)
SESS_TTL = 1800          # جلسه‌ی هر بازی نیم ساعت بعد پاک می‌شود
DAILY_BASE = 15          # سکه‌ی پایه‌ی چک‌این روزانه
STREAK_MAX = 5           # سقف پاداش استریک
WIN_COINS = 12           # جایزه‌ی پایه‌ی برد (در ضریب سختی بازی ضرب می‌شود)
RATE_SEC = 2             # فاصله‌ی اجباری بین دو لمس بازی هر کاربر

QUIZ_BANK = [
    ("پایتخت ایران کدام شهر است؟", ["تهران", "اصفهان", "شیراز", "تبریز"], 0),
    ("بزرگ‌ترین سیاره‌ی منظومه‌ی شمسی؟", ["زمین", "مشتری", "مریخ", "زحل"], 1),
    ("عدد ۱۵ در چند ضرب‌شده در ۴ می‌شود؟", ["۴۵", "۶۰", "۵۵", "۶۴"], 1),
    ("کدام حرف فارسی نیست؟", ["گ", "چ", "X", "پ"], 2),
    ("آب در چند درجه می‌جوشد (سانتی‌گراد)؟", ["۸۰", "۹۰", "۱۰۰", "۱۲۰"], 2),
    ("مؤلف «مثنوی معنوی»؟", ["حافظ", "سعدی", "مولانا", "فردوسی"], 2),
    ("کدام یک رنگ گرم است؟", ["آبی", "سبز", "نارنجی", "بنفش"], 2),
    ("۵۰ درصد ۲۰۰ چقدر است؟", ["۸۰", "۹۰", "۱۰۰", "۱۲۰"], 2),
    ("نزدیک‌ترین ستاره به زمین؟", ["خورشید", "شباهت", "پروکسیما", "شعرای یمانی"], 0),
    ("کدام جانور پست‌دار نمی‌خوابد روی درخت؟", ["سنجاب", "خرس", "گربه", "خفاش"], 3),
    ("کلمه‌ی «کتاب» چند حرف دارد؟", ["۳", "۴", "۵", "۶"], 2),
    ("دوربین چند پا دارد؟", ["۱", "۲", "۳", "۴"], 2),
]
WORD_BANK = ["تلویزیون", "کتابخانه", "هواپیما", "دوچرخه", "خورشید", "دوستی", "برنامه‌ریزی", "کوهنورد",
             "گلاب", "بازیکن", "مدرسه", "کتابی", "آشپزخانه", "چراغ", "پنجره", "سالن"]
TYPING_LINES = ["ربات‌ساز هوشمند بهترین دوست کسب‌وکار توست", "هر روز یک قدم جلوتر از دیروزی",
                "بازی و تلاش همراه هم به موفقیت می‌رسند", "سرعت تایپ تو را همین امروز می‌سنجیم"]


def _idx():
    """ایندکس‌ها (یک‌بار در بوت)"""
    try:
        db.gusers.create_index([("bot", 1), ("u", 1)], unique=True)
        db.gsess.create_index("t", expireAfterSeconds=SESS_TTL)
        db.gscore.create_index([("bot", 1), ("g", 1), ("p", 1), ("n", -1)])
        db.gscore.create_index([("bot", 1), ("u", 1), ("g", 1), ("p", 1)], unique=True)
        db.grooms.create_index("t", expireAfterSeconds=SESS_TTL)
    except Exception as e:
        log.warning("games index: %s", e)


def gcfg(cfg):
    """کانفیگ بازی ربات؛ خاموش = None"""
    g = cfg.get("games")
    return g if isinstance(g, dict) and g.get("on") else None


def glist(cfg):
    g = gcfg(cfg) or {}
    ls = [str(x) for x in (g.get("list") if isinstance(g.get("list"), list) else []) if str(x) in GAME_IDS]
    return ls or list(GAME_IDS)


def coin(cfg):
    return str((gcfg(cfg) or {}).get("coin") or "سکه")


def _gu(bot_id, uid):
    d = db.gusers.find_one_and_update({"bot": bot_id, "u": uid}, {"$setOnInsert": {"coins": 0, "best": {}, "inv": {}, "daily": {}}},
                                      upsert=True, return_document=ReturnDocument.AFTER)
    return d or {}


def _coins(bot_id, uid, diff, why="game"):
    """کسر/افزودن اتمیک سکه؛ diff منفی = خرج (فقط تا سقف موجودی). برای کاربر تازه هم سند ساخته می‌شود"""
    if diff < 0:
        return db.gusers.find_one_and_update({"bot": bot_id, "u": uid, "coins": {"$gte": -diff}},
                                             {"$inc": {"coins": diff}}, return_document=ReturnDocument.AFTER)
    d = db.gusers.find_one_and_update({"bot": bot_id, "u": uid},
                                      {"$inc": {"coins": diff}, "$setOnInsert": {"best": {}, "inv": {}, "daily": {}}},
                                      upsert=True, return_document=ReturnDocument.AFTER)
    return d


def _score_up(bot_id, uid, name, g, n, periods):
    """بهترین رکورد کاربر در هر دوره ثبت می‌شود ($max؛ ضدتقلب سمت سرور)"""
    for p in periods:
        try:
            db.gscore.update_one({"bot": bot_id, "u": uid, "g": g, "p": p},
                                 {"$max": {"n": int(n)}, "$set": {"nm": (name or "کاربر")[:24], "t": now()}}, upsert=True)
        except DuplicateKeyError:
            pass


def periods():
    """کلید دوره‌ها: روز / هفته (شماره‌ی هفته) / فصل (ماه)"""
    import datetime
    d = datetime.datetime.utcnow()
    wk = d.strftime("%G-W%V")
    return [f"d:{tehran_day()}", f"w:{wk}", f"m:{d.strftime('%Y-%m')}"]


def _reward(cfg, g, base):
    mult = ((gcfg(cfg) or {}).get("reward") or {}).get(g)
    try:
        return max(1, int(base * float(mult))) if mult else int(base)
    except (TypeError, ValueError):
        return int(base)


# ───────────────────────── دستورهای ربات (گروه و خصوصی) ─────────────────────────
GAME_ICON = {"quiz": "🧠", "memory": "🃏", "tap": "⚡", "wheel": "🎡", "word": "🔤", "math": "➗", "typing": "⌨️", "puzzle": "🧩", "xo": "❌⭕"}


def _game_menu(cfg):
    rows = []
    ls = glist(cfg)
    for i in range(0, len(ls), 2):
        rows.append([{"text": f"{GAME_ICON[g]} {GAMES_FA[g]}", "callback_data": f"g:n:{g}"} for g in ls[i:i + 2]])
    rows.append([{"text": "🏆 رتبه‌ها", "callback_data": "g:top"}, {"text": "🎁 سکه‌ی روزانه", "callback_data": "g:daily"}])
    if ((gcfg(cfg) or {}).get("shop") or []):
        rows.append([{"text": "🛍 فروشگاه", "callback_data": "g:shop"}])
    return {"inline_keyboard": rows}


def cmd(bot, token, cfg, chat_id, user, text):
    """دستورهای بازی؛ True یعنی این پیام مال بازی بود و موتور نباید ادامه دهد"""
    g = gcfg(cfg)
    if not g:
        return False
    bot_id = str(bot["_id"])
    t = (text or "").strip().lower()
    if t in ("/play", "!بازی", "بازی"):
        _tour_check(bot_id, token, cfg, chat_id)             # اگر مسابقه‌ی قبلی تمام شده، همین‌جا برگندگان را اعلام و جایزه بده
        tg_html(token, "sendMessage", chat_id=chat_id,
                text=f"🎮 <b>مرکز بازی</b>\nیکی را انتخاب کن؛ سکه ببر، رکورد بزن!" +
                     (f"\nسکه‌های تو: <b>{_gu(bot_id, user['id'])['coins']}</b>" if chat_id == user["id"] else ""),
                reply_markup=_game_menu(cfg))
        return True
    if t in ("/top", "!رتبه", "رتبه"):
        board_send(bot_id, token, cfg, chat_id, g, "d")
        return True
    if t in ("/wallet", "!سکه"):
        d = _gu(bot_id, user["id"])
        tg(token, "sendMessage", chat_id=chat_id, text=f"💰 سکه‌های تو: {d['coins']} {coin(cfg)}")
        return True
    if t in ("/daily", "!روزانه"):
        daily_cb(bot_id, token, cfg, chat_id, user)
        return True
    if t in ("/tour", "!مسابقه", "مسابقه"):
        _tour_cmd(bot_id, token, cfg, chat_id, user)
        return True
    return False


# ───────────────────────── مسابقه‌ی ۲۴ ساعته (تورنمنت) ─────────────────────────
TOUR_PRIZE = (50, 30, 20)      # جایزه‌ی سکه‌ی مقام‌های ۱ تا ۳


def _tour_prize(cfg):
    try:
        p = int((gcfg(cfg) or {}).get("tour_prize") or 0)
        return p if p > 0 else TOUR_PRIZE[0]
    except (TypeError, ValueError):
        return TOUR_PRIZE[0]


def _tour_active(bot_id, chat_id):
    t = db.gtour.find_one({"_id": f"{bot_id}:{chat_id}"})
    return t if t and float(t.get("end") or 0) > time.time() else None


def _tour_check(bot_id, token, cfg, chat_id):
    """اگر مسابقه‌ی این چت تمام شده: برگندگان را اعلام و جایزه‌شان را بده"""
    t = db.gtour.find_one({"_id": f"{bot_id}:{chat_id}"})
    if not t or float(t.get("end") or 0) > time.time():
        return
    rows = list(db.gtourp.find({"_id": {"$regex": "^" + re.escape(f"{bot_id}:{chat_id}:")}}, sort=[("n", -1)]).limit(3))
    if rows:
        medals = ["🥇", "🥈", "🥉"]
        prize = (int(t.get("prize") or TOUR_PRIZE[0]), 30, 20)
        lines = [f"{medals[i]} <b>{(r.get('nm') or 'کاربر')[:24]}</b> — {_fn(r.get("n", 0))} امتیاز · {_fn(prize[i])} {coin(cfg)}"
                 for i, r in enumerate(rows)]
        tg_html(token, "sendMessage", chat_id=chat_id, text="🏁 <b>مسابقه تمام شد!</b>\n" + "\n".join(lines))
        for i, r in enumerate(rows):
            _coins(bot_id, r["u"], prize[i], "tour")
    db.gtourp.delete_many({"_id": {"$regex": "^" + re.escape(f"{bot_id}:{chat_id}:")}})
    db.gtour.delete_one({"_id": f"{bot_id}:{chat_id}"})


def _tour_cmd(bot_id, token, cfg, chat_id, user):
    _tour_check(bot_id, token, cfg, chat_id)
    if _tour_active(bot_id, chat_id):
        t = _tour_active(bot_id, chat_id)
        hrs = max(0, int((float(t["end"]) - time.time()) // 3600))
        rows = list(db.gtourp.find({"_id": {"$regex": "^" + re.escape(f"{bot_id}:{chat_id}:")}}, sort=[("n", -1)]).limit(5))
        lines = [f"{i + 1}. {(r.get('nm') or 'کاربر')[:24]} — {_fn(r.get("n", 0))}" for i, r in enumerate(rows)]
        tg_html(token, "sendMessage", chat_id=chat_id,
                text=f"🏆 <b>مسابقه در جریان است</b> ({_fn(hrs)} ساعت مانده)\nجایزه‌ی نفر اول: <b>{_fn(int(t.get('prize') or 50))}</b> {coin(cfg)}\n" +
                     ("\n".join(lines) if lines else "هنوز کسی امتیاز نگرفته؛ تو اول باش!"))
        return
    prize = _tour_prize(cfg)
    db.gtour.insert_one({"_id": f"{bot_id}:{chat_id}", "bot": bot_id, "chat": chat_id,
                         "start": time.time(), "end": time.time() + 24 * 3600, "prize": prize})
    tg_html(token, "sendMessage", chat_id=chat_id,
            text=f"🏆 <b>مسابقه‌ی ۲۴ ساعته شروع شد!</b>\nهر بازی که انجام بدهی، امتیازش به نمره‌ی مسابقه‌ات اضافه می‌شود.\nجایزه‌ی نفر اول: <b>{_fn(prize)}</b> {coin(cfg)} · دومی ۳۰ · سومی ۲۰\nبا <b>/tour</b> وضعیت را ببین.")


def _tour_point(bot_id, chat_id, uid, name, gain):
    """امتیاز پایان هر بازی به نمره‌ی مسابقه‌ی همان چت اضافه می‌شود (فقط گروه)"""
    if not _tour_active(bot_id, chat_id) or gain <= 0:
        return
    try:
        db.gtourp.update_one({"_id": f"{bot_id}:{chat_id}:{uid}"},
                             {"$inc": {"n": int(gain)}, "$set": {"u": uid, "nm": (name or "کاربر")[:24]}}, upsert=True)
    except Exception:
        pass


def on_text(bot, token, cfg, chat_id, user, text):
    """جواب متنی بازی‌های متنی (کلمه، ریاضی، تایپ)؛ True = همین پیام مصرف شد"""
    bot_id = str(bot["_id"])
    s = db.gsess.find_one({"bot": bot_id, "u": user["id"], "chat": chat_id})
    if not s or s.get("g") not in ("word", "math", "typing"):
        return False
    st = s["st"]
    ok = False
    if s["g"] == "word":
        ok = text.strip() == st["word"]
    elif s["g"] == "math":
        try:
            ok = int(re.sub(r"[۰-۹]", lambda m: str("۰۱۲۳۴۵۶۷۸۹".index(m.group(0))), text.strip())) == st["ans"]
        except (ValueError, TypeError):
            ok = False
    elif s["g"] == "typing":
        ok = text.strip() == st["line"]
    if not ok:
        db.gsess.delete_one({"_id": s["_id"]})
        tg(token, "sendMessage", chat_id=chat_id, text="❌ اشتباه بود؛ جواب درست: " + str(st.get("word") or st.get("ans") or st.get("line")))
        return True
    took = max(1, int(now().timestamp() - s["t"].timestamp()))
    if s["g"] == "typing":
        gain = _reward(cfg, "typing", max(2, 20 - took // 2))
    elif s["g"] == "math":
        gain = _reward(cfg, "math", max(3, 14 - took))
    else:
        gain = _reward(cfg, "word", max(4, 16 - took))
    finish(bot_id, token, cfg, chat_id, user, s["g"], gain, f"در {took} ثانیه")
    db.gsess.delete_one({"_id": s["_id"]})
    return True


def _fn(x):
    try:
        return str(int(x))
    except (TypeError, ValueError):
        return "0"


def finish(bot_id, token, cfg, chat_id, user, g, gain, extra=""):
    """پایان موفق یک بازی: سکه، رکورد دوره‌ای و کارت نتیجه (در گروه کارت زیبا می‌آید)"""
    _coins(bot_id, user["id"], gain)
    _score_up(bot_id, user["id"], user.get("first_name"), g, gain, periods())
    db.gusers.update_one({"bot": bot_id, "u": user["id"]}, {"$max": {f"best.{g}": gain}})
    if chat_id != user["id"]:
        _tour_point(bot_id, chat_id, user["id"], user.get("first_name"), gain)      # امتیاز مسابقه‌ی ۲۴ ساعته
    icon = GAME_ICON.get(g, "🎮")
    text = (f"{icon} <b>{user.get('first_name') or 'بازیکن'}</b> "
            f"{GAMES_FA.get(g, g)} را تمام کرد!\n+<b>{gain}</b> {coin(cfg)}"
            + (f"\n<i>{extra}</i>" if extra else ""))
    if chat_id != user["id"]:
        text += "\nبا /play تو هم بازی کن!"
    tg_html(token, "sendMessage", chat_id=chat_id, text=text)


# ───────────────────────── چک‌این روزانه و فروشگاه ─────────────────────────
def daily_cb(bot_id, token, cfg, chat_id, user):
    d = _gu(bot_id, user["id"])
    day = tehran_day()
    if d.get("daily", {}).get("day") == day:
        tg(token, "sendMessage", chat_id=chat_id, text="🎁 سکه‌ی امروز را قبلاً گرفتی؛ فردا بیا.")
        return
    streak = d.get("daily", {}).get("streak", 0) + 1 if d.get("daily", {}).get("yest") == tehran_day(1) else 1
    gain = DAILY_BASE + min(streak - 1, STREAK_MAX)
    _coins(bot_id, user["id"], gain)
    db.gusers.update_one({"bot": bot_id, "u": user["id"]}, {"$set": {"daily": {"day": day, "yest": day, "streak": streak}}})
    tg_html(token, "sendMessage", chat_id=chat_id,
            text=f"🎁 <b>+{gain} {coin(cfg)}</b> گرفتی! ({streak} روز پیاپی 🔥)")


def shop_items(cfg):
    g = gcfg(cfg) or {}
    out = []
    for x in (g.get("shop") or [])[:12]:
        if isinstance(x, dict) and str(x.get("id") or "").strip() and x.get("price") is not None:
            try:
                out.append({"id": str(x["id"])[:20], "title": str(x.get("title") or x["id"])[:30],
                            "price": max(1, int(x["price"])), "desc": str(x.get("desc") or "")[:60]})
            except (TypeError, ValueError):
                continue
    return out


def shop_cb(bot_id, token, cfg, chat_id, user, mid=None):
    items = shop_items(cfg)
    if not items:
        tg(token, "sendMessage", chat_id=chat_id, text="فروشگاه فعلاً خالی است.")
        return
    rows = [[{"text": f"{i['title']} — {i['price']} {coin(cfg)}", "callback_data": f"g:buy:{i['id']}"}] for i in items]
    d = _gu(bot_id, user["id"])
    if mid:
        tg_html(token, "editMessageText", chat_id=chat_id, message_id=mid,
                text=f"🛍 <b>فروشگاه</b>\n💰 سکه‌ی تو: <b>{d['coins']}</b>", reply_markup={"inline_keyboard": rows})
    else:
        tg_html(token, "sendMessage", chat_id=chat_id, text=f"🛍 <b>فروشگاه</b>\n💰 سکه‌ی تو: <b>{d['coins']}</b>",
                reply_markup={"inline_keyboard": rows})


def board_send(bot_id, token, cfg, chat_id, g, p="d", mid=None):
    label = {"d": "امروز", "w": "این هفته", "m": "این فصل"}.get(p, "امروز")
    rows = list(db.gscore.find({"bot": bot_id, "g": g, "p": {"$in": [x for x in periods() if x.startswith(p + ":")]}},
                               sort=[("n", -1)]).limit(10))
    if not rows:
        text = f"🏆 هنوز رکوردی در «{GAMES_FA.get(g, g)}» ثبت نشده؛ اولین نفر باش! (/play)"
    else:
        med = ["🥇", "🥈", "🥉"] + ["▫️"] * 7
        text = f"🏆 <b>{GAMES_FA.get(g, g)} — {label}</b>\n\n" + "\n".join(
            f"{med[i]} {r['nm']}: <b>{r['n']}</b>" for i, r in enumerate(rows))
    mk = {"inline_keyboard": [[{"text": "🎮 بازی‌ها", "callback_data": "g:menu"}]]}
    if mid:
        tg_html(token, "editMessageText", chat_id=chat_id, message_id=mid, text=text, reply_markup=mk)
    else:
        tg_html(token, "sendMessage", chat_id=chat_id, text=text, reply_markup=mk)


# ───────────────────────── شروع بازی‌ها (سرور) ─────────────────────────
def _sess_new(bot_id, uid, chat_id, g, st):
    db.gsess.delete_many({"bot": bot_id, "u": uid, "chat": chat_id})
    db.gsess.insert_one({"bot": bot_id, "u": uid, "chat": chat_id, "g": g, "st": st, "t": now()})


def start_game(bot, token, cfg, chat_id, user, g):
    bot_id, uid = str(bot["_id"]), user["id"]
    name = user.get("first_name") or "بازیکن"
    if g == "quiz":
        qs = random.sample(QUIZ_BANK, 4)
        st = {"qi": 0, "score": 0, "qs": [[q, a, c] for q, a, c in qs]}
        _sess_new(bot_id, uid, chat_id, "quiz", st)
        return quiz_show(bot, token, cfg, chat_id, st, uid)
    if g == "memory":
        emos = random.sample(["🍎", "🚀", "🐱", "⚽", "🎲", "🌈"], 3) * 2
        random.shuffle(emos)
        _sess_new(bot_id, uid, chat_id, "memory", {"emos": emos, "open": [], "done": [], "moves": 0})
        return tg_html(token, "sendMessage", chat_id=chat_id, text="🃏 <b>حافظه</b>\nجفت‌های یکسان را پیدا کن؛ با حرکت کمتر، سکه‌ی بیشتر!",
                       reply_markup={"inline_keyboard": memory_kb(emos, [], [])})
    if g == "tap":
        _sess_new(bot_id, uid, chat_id, "tap", {"n": 0, "end": now().timestamp() + 10})
        return tg_html(token, "sendMessage", chat_id=chat_id, text="⚡ <b>لمس سریع</b>\n۱۰ ثانیه وقت داری؛ هرچه می‌توانی بزن!",
                       reply_markup={"inline_keyboard": [[{"text": "⚡ بزن!", "callback_data": "g:tap"}]]})
    if g == "wheel":
        segs = [1, 3, 5, 10, 2, 20, 4, 50]
        pick = random.choices(range(8), weights=[24, 20, 16, 10, 18, 6, 14, 2])[0]
        gain = _reward(cfg, "wheel", segs[pick])
        _coins(bot_id, uid, gain)
        _score_up(bot_id, uid, name, "wheel", gain, periods())
        return tg_html(token, "sendMessage", chat_id=chat_id,
                       text=f"🎡 گردونه چرخید…\n\n🎯 جایزه‌ی تو: <b>+{gain} {coin(cfg)}</b>")
    if chat_id != uid and g in ("word", "math", "typing"):
        tg_html(token, "sendMessage", chat_id=chat_id,
                text=f"🔤 این بازی در چت خصوصی ربات انجام می‌شود؛ از دکمه‌ی زیر شروع کن 👇",
                reply_markup={"inline_keyboard": [[{"text": "▶️ شروع در چت خصوصی", "url": f"https://t.me/{bot.get('username') or 'bot'}"}]]})
        return True
    if g == "word":
        w = random.choice(WORD_BANK)
        sh = list(w); random.shuffle(sh)
        _sess_new(bot_id, uid, chat_id, "word", {"word": w})
        return tg_html(token, "sendMessage", chat_id=chat_id,
                       text=f"🔤 <b>حدس کلمه</b>\nحروف به‌هم‌ریخته: <b>{'، '.join(sh)}</b>\nکلمه را درست بنویس ({16} ثانیه اول = جایزه‌ی بیشتر)")
    if g == "math":
        a, b = random.randint(6, 40), random.randint(3, 25)
        op = random.choice([("+", a + b), ("-", a - b if a > b else b - a), ("×", a * b)])
        x, ans = (a, op[1]) if op[0] != "-" or a > b else (b, op[1])
        _sess_new(bot_id, uid, chat_id, "math", {"ans": op[1]})
        return tg_html(token, "sendMessage", chat_id=chat_id,
                       text=f"➗ <b>ریاضی سریع</b>\nحاصل <b>{a} {op[0]} {b}</b> چند است؟")
    if g == "typing":
        line = random.choice(TYPING_LINES)
        _sess_new(bot_id, uid, chat_id, "typing", {"line": line})
        return tg_html(token, "sendMessage", chat_id=chat_id,
                       text=f"⌨️ <b>سرعت تایپ</b>\nاین جمله را دقیق تایپ کن:\n\n<blockquote>{line}</blockquote>")
    if g == "puzzle":
        nums = list(range(1, 9)) + [0]
        for _ in range(60):
            i = nums.index(0)
            js = [j for j in (i - 1, i + 1, i - 3, i + 3) if 0 <= j < 9 and not (abs(i - j) == 1 and i % 3 == 0 and j == i - 1) and not (abs(i - j) == 1 and j % 3 == 0 and j == i + 1)]
            j = random.choice(js)
            nums[i], nums[j] = nums[j], nums[i]
        _sess_new(bot_id, uid, chat_id, "puzzle", {"nums": nums, "moves": 0})
        return tg_html(token, "sendMessage", chat_id=chat_id, text="🧩 <b>پازل اعداد</b>\n۱ تا ۸ را به ترتیب بچین!",
                       reply_markup={"inline_keyboard": puzzle_kb(nums)})
    if g == "xo":
        room = db.grooms.find_one({"bot": bot_id, "g": "xo", "open": True})
        if room and uid not in room["ps"] and len(room["ps"]) < 2:
            db.grooms.update_one({"_id": room["_id"]}, {"$set": {"ps": room["ps"] + [uid], "open": False}})
            ps = room["ps"] + [uid]
            nm0 = (db.gusers.find_one({"bot": bot_id, "u": ps[0]}) or {}).get("nm") or "بازیکن ۱"
            for pid in ps:
                tg_html(token, "sendMessage", chat_id=pid, text=f"⚔️ حریف پیدا شد! <b>{name}</b> بازی را شروع می‌کند.",
                        reply_markup={"inline_keyboard": xo_kb([""] * 9, "X")})
            db.grooms.update_one({"_id": room["_id"]}, {"$set": {"st": [""] * 9, "turn": 0, "open": False}})
            return True
        db.grooms.delete_many({"bot": bot_id, "u": uid})
        db.grooms.insert_one({"bot": bot_id, "u": uid, "g": "xo", "ps": [uid], "open": True, "st": [""] * 9, "turn": 0, "t": now()})
        return tg_html(token, "sendMessage", chat_id=chat_id,
                       text="⚔️ <b>دوئل XO</b>\nاتاق ساخته شد؛ منتظر حریف… (لینک را برای دوستت بفرست تا بپیوندد)",
                       reply_markup={"inline_keyboard": [[{"text": "لغو", "callback_data": "g:xocancel"}]]})
    tg(token, "sendMessage", chat_id=chat_id, text="این بازی فعلاً در دسترس نیست.")


def quiz_show(bot, token, cfg, chat_id, st, uid):
    i = st["qi"]
    q, a, c = st["qs"][i]
    rows = [[{"text": x, "callback_data": f"g:qa:{k}"}] for k, x in enumerate(a)]
    tg_html(token, "sendMessage", chat_id=chat_id,
            text=f"🧠 <b>کوییز</b> — سؤال {i + 1} از {len(st['qs'])}\nامتیاز: {st['score']}\n\n{q}",
            reply_markup={"inline_keyboard": rows})


def memory_kb(emos, open_i, done_i):
    rows = []
    for r in range(0, 6, 3):
        rows.append([{"text": emos[i] if i in open_i or i in done_i else "🂠", "callback_data": f"g:mm:{i}"} for i in range(r, r + 3)])
    return rows


def puzzle_kb(nums):
    rows = []
    for r in range(0, 9, 3):
        rows.append([{"text": str(nums[i]) if nums[i] else "⬜", "callback_data": f"g:pz:{i}"} for i in range(r, r + 3)])
    return rows


def xo_kb(st, turn):
    rows = []
    for r in range(0, 9, 3):
        rows.append([{"text": st[i] or "▫️", "callback_data": f"g:xm:{i}"} for i in range(r, r + 3)])
    return rows


def _who(bot_id, uid):
    return "بازیکن"


# ───────────────────────── دکمه‌های بازی (callback) ─────────────────────────
def cb(bot, token, cfg, chat_id, user, data, mid):
    bot_id, uid = str(bot["_id"]), user["id"]
    name = user.get("first_name") or "بازیکن"
    cq_id = None
    ans = lambda t=None, alert=False: None  # noqa: E731
    parts = data.split(":")
    kind = parts[1] if len(parts) > 1 else ""
    if kind == "menu":
        tg_html(token, "editMessageText", chat_id=chat_id, message_id=mid, text="🎮 <b>مرکز بازی</b>\nیکی را انتخاب کن!",
                reply_markup=_game_menu(cfg))
        return True
    if kind == "top":
        g = parts[2] if len(parts) > 2 else glist(cfg)[0]
        board_send(bot_id, token, cfg, chat_id, g, "d", mid=mid)
        return True
    if kind == "daily":
        daily_cb(bot_id, token, cfg, chat_id, user)
        return True
    if kind == "shop":
        shop_cb(bot_id, token, cfg, chat_id, user, mid=mid)
        return True
    if kind == "buy":
        items = {i["id"]: i for i in shop_items(cfg)}
        it = items.get(parts[2] if len(parts) > 2 else "")
        if not it:
            tg(token, "sendMessage", chat_id=chat_id, text="این آیتم دیگر موجود نیست.")
            return True
        d = _coins(bot_id, uid, -it["price"])
        if not d:
            tg(token, "sendMessage", chat_id=chat_id, text=f"💰 سکه کافی نداری؛ با /play سکه جمع کن!")
            return True
        db.gusers.update_one({"bot": bot_id, "u": uid}, {"$inc": {f"inv.{it['id']}": 1}})
        tg_html(token, "sendMessage", chat_id=chat_id, text=f"🎉 «{it['title']}» خریدی!\nموجودی: {d['coins']} {coin(cfg)}")
        return True
    if kind == "n":
        start_game(bot, token, cfg, chat_id, user, parts[2])
        return True
    if kind == "xocancel":
        db.grooms.delete_many({"bot": bot_id, "u": uid, "open": True})
        tg(token, "editMessageText", chat_id=chat_id, message_id=mid, text="اتاق بسته شد.")
        return True
    if kind == "xm":
        return xo_move(bot, token, cfg, chat_id, user, mid, int(parts[2] or -1))
    # ── بازی‌های فعال ──
    s = db.gsess.find_one({"bot": bot_id, "u": uid, "chat": chat_id})
    if not s:
        return True
    st = s["st"]
    if kind == "qa" and s["g"] == "quiz":
        i = st["qi"]
        c = st["qs"][i][2]
        good = int(parts[2] or -1) == c
        if good:
            st["score"] += 1
        st["qi"] += 1
        if st["qi"] >= len(st["qs"]):
            db.gsess.delete_one({"_id": s["_id"]})
            gain = _reward(cfg, "quiz", 3 + st["score"] * 3)
            finish(bot_id, token, cfg, chat_id, user, "quiz", gain, f"{st['score']} پاسخ درست از {len(st['qs'])}")
            return True
        db.gsess.update_one({"_id": s["_id"]}, {"$set": {"st": st}})
        return quiz_show(bot, token, cfg, chat_id, st, uid)
    if kind == "mm" and s["g"] == "memory":
        i = int(parts[2] or -1)
        if i < 0 or i in st["done"] or i in st["open"] or len(st["open"]) >= 2:
            return True
        st["open"].append(i)
        if len(st["open"]) == 2:
            st["moves"] += 1
            a, b = st["open"]
            if st["emos"][a] == st["emos"][b]:
                st["done"] += st["open"]
                st["open"] = []
        db.gsess.update_one({"_id": s["_id"]}, {"$set": {"st": st}})
        tg_html(token, "editMessageText", chat_id=chat_id, message_id=mid,
                text=f"🃏 <b>حافظه</b>\nحرکت‌ها: {st['moves']} · پیدا شده: {len(st['done']) // 2} از 3",
                reply_markup={"inline_keyboard": memory_kb(st["emos"], st["open"], st["done"])})
        if len(st["done"]) == 6:
            db.gsess.delete_one({"_id": s["_id"]})
            gain = _reward(cfg, "memory", max(3, 20 - st["moves"] * 2))
            finish(bot_id, token, cfg, chat_id, user, "memory", gain, f"{st['moves']} حرکت")
        return True
    if kind == "tap" and s["g"] == "tap":
        if now().timestamp() > st["end"]:
            db.gsess.delete_one({"_id": s["_id"]})
            gain = _reward(cfg, "tap", max(1, st["n"] // 4))
            finish(bot_id, token, cfg, chat_id, user, "tap", gain, f"{st['n']} لمس در ۱۰ ثانیه")
            return True
        st["n"] += 1
        db.gsess.update_one({"_id": s["_id"]}, {"$set": {"st": st}})
        left = max(0, int(st["end"] - now().timestamp()))
        try:
            tg(token, "editMessageText", chat_id=chat_id, message_id=mid,
               text=f"⚡ <b>{st['n']}</b> لمس · {left} ثانیه مانده",
               reply_markup={"inline_keyboard": [[{"text": "⚡ بزن!", "callback_data": "g:tap"}]]})
        except Exception:
            pass
        return True
    if kind == "pz" and s["g"] == "puzzle":
        i = int(parts[2] or -1)
        nums = st["nums"]
        zi = nums.index(0)
        if i < 0 or i == zi:
            return True
        adj = [j for j in (zi - 1, zi + 1, zi - 3, zi + 3) if 0 <= j < 9 and not (abs(zi - j) == 1 and zi % 3 == 0 and j == zi - 1) and not (abs(zi - j) == 1 and j % 3 == 0 and j == zi + 1)]
        if i not in adj:
            return True
        nums[zi], nums[i] = nums[i], nums[zi]
        st["nums"] = nums
        st["moves"] = st.get("moves", 0) + 1
        db.gsess.update_one({"_id": s["_id"]}, {"$set": {"st": st}})
        tg_html(token, "editMessageText", chat_id=chat_id, message_id=mid,
                text=f"🧩 <b>پازل اعداد</b>\nحرکت‌ها: {st['moves']}",
                reply_markup={"inline_keyboard": puzzle_kb(nums)})
        if nums[:8] == list(range(1, 9)):
            db.gsess.delete_one({"_id": s["_id"]})
            gain = _reward(cfg, "puzzle", max(4, 25 - st["moves"]))
            finish(bot_id, token, cfg, chat_id, user, "puzzle", gain, f"{st['moves']} حرکت")
        return True
    return True


def xo_move(bot, token, cfg, chat_id, user, mid, i):
    """یک خانه در دوئل XO"""
    bot_id, uid = str(bot["_id"]), user["id"]
    room = db.grooms.find_one({"bot": bot_id, "g": "xo", "ps": uid})
    if not room or room.get("open"):
        return True
    st = room["st"]
    if st[i] or room["ps"][room.get("turn", 0)] != uid:
        return True
    st[i] = "X" if room["ps"].index(uid) == 0 else "⭕"
    win, line = _xo_win(st)
    turn = (room.get("turn", 0) + 1) % 2
    db.grooms.update_one({"_id": room["_id"]}, {"$set": {"st": st, "turn": turn}})
    if win:
        db.grooms.delete_one({"_id": room["_id"]})
        for pid, r in ((room["ps"][0], "X"), (room["ps"][1], "⭕")):
            if pid == user["id"] and r == win:
                gain = _reward(cfg, "xo", 18)
                finish(bot_id, token, cfg, chat_id, {"id": pid, "first_name": user.get("first_name")}, "xo", gain, "برنده‌ی دوئل")
            else:
                _coins(bot_id, pid, _reward(cfg, "xo", 3))
                try:
                    tg(token, "sendMessage", chat_id=pid, text=f"⚔️ دوئل تمام شد؛ برنده: {win}")
                except Exception:
                    pass
        return True
    if all(x for x in st):
        db.grooms.delete_one({"_id": room["_id"]})
        tg_html(token, "sendMessage", chat_id=chat_id, text="⚔️ مساوی شد!")
        return True
    try:
        tg_html(token, "editMessageText", chat_id=chat_id, message_id=mid, text="⚔️ <b>دوئل XO</b>\nنوبت حریف…",
                reply_markup={"inline_keyboard": xo_kb(st, turn)})
    except Exception:
        pass
    return True


def _xo_win(st):
    L = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
    for a, b, c in L:
        if st[a] and st[a] == st[b] == st[c]:
            return st[a], (a, b, c)
    return None, None


# ───────────────────────── رانتایم مینی‌اپ ─────────────────────────
def _rt_ctx(bot_id):
    from webapp import _rt_auth
    bot, uid, user, err = _rt_auth(bot_id)
    return bot, uid, user, err


@app.post("/rt/<bot_id>/game/boot")
def rt_game_boot(bot_id):
    bot, uid, user, err = _rt_ctx(bot_id)
    if err:
        return err
    cfg = bot["config"]
    d = _gu(str(bot["_id"]), uid)
    day = tehran_day()
    shop = shop_items(cfg)
    return jsonify(coin=coin(cfg), coins=d.get("coins", 0), best=d.get("best") or {},
                   daily={"done": (d.get("daily") or {}).get("day") == day, "streak": (d.get("daily") or {}).get("streak", 0),
                          "next": DAILY_BASE + min((d.get("daily") or {}).get("streak", 0), STREAK_MAX)},
                   games=[{"k": g, "fa": GAMES_FA[g], "icon": GAME_ICON[g], "best": (d.get("best") or {}).get(g, 0)} for g in glist(cfg)],
                   shop=[{**i, "have": (d.get("inv") or {}).get(i["id"], 0)} for i in shop])


@app.post("/rt/<bot_id>/game/start")
def rt_game_start(bot_id):
    bot, uid, user, err = _rt_ctx(bot_id)
    if err:
        return err
    if not rate_ok(f"gm:{bot_id}:{uid}", 30, 60):
        return jsonify(error="کمی آروم‌تر"), 429
    g = (request.get_json(silent=True) or {}).get("game")
    if g not in GAME_IDS:
        return jsonify(error="بازی پیدا نشد"), 404
    cfg = bot["config"]
    bot_id2 = str(bot["_id"])
    name = user.get("first_name") or "بازیکن"
    if g == "quiz":
        qs = random.sample(QUIZ_BANK, 4)
        _sess_new(bot_id2, uid, uid, "quiz", {"qi": 0, "score": 0, "qs": [[q, a, c] for q, a, c in qs]})
        return jsonify(game="quiz", st={"q": qs[0][0], "opts": qs[0][1], "i": 0, "total": 4})
    if g == "memory":
        emos = random.sample(["🍎", "🚀", "🐱", "⚽", "🎲", "🌈"], 3) * 2
        random.shuffle(emos)
        _sess_new(bot_id2, uid, uid, "memory", {"emos": emos})
        return jsonify(game="memory", st={"n": 6})
    if g == "tap":
        db.gsess.delete_many({"bot": bot_id2, "u": uid})
        db.gsess.insert_one({"bot": bot_id2, "u": uid, "chat": uid, "g": "tap", "st": {"n": 0, "end": now().timestamp() + 10}, "t": now()})
        return jsonify(game="tap", st={"secs": 10})
    if g == "wheel":
        segs = [1, 3, 5, 10, 2, 20, 4, 50]
        pick = random.choices(range(8), weights=[24, 20, 16, 10, 18, 6, 14, 2])[0]
        gain = _reward(cfg, "wheel", segs[pick])
        _coins(bot_id2, uid, gain)
        _score_up(bot_id2, uid, name, "wheel", gain, periods())
        return jsonify(game="wheel", st={"i": pick, "gain": gain})
    if g == "word":
        w = random.choice(WORD_BANK)
        sh = list(w); random.shuffle(sh)
        _sess_new(bot_id2, uid, uid, "word", {"word": w})
        return jsonify(game="word", st={"letters": sh})
    if g == "math":
        a, b = random.randint(6, 40), random.randint(3, 25)
        if a < b:
            a, b = b, a
        op = random.choice("+−×")
        ans = a + b if op == "+" else (a - b if op == "−" else a * b)
        _sess_new(bot_id2, uid, uid, "math", {"ans": ans})
        return jsonify(game="math", st={"a": a, "b": b, "op": op})
    if g == "typing":
        line = random.choice(TYPING_LINES)
        _sess_new(bot_id2, uid, uid, "typing", {"line": line, "t0": now().timestamp()})
        return jsonify(game="typing", st={"line": line})
    if g == "puzzle":
        nums = list(range(1, 9)) + [0]
        for _ in range(80):
            i = nums.index(0)
            js = [j for j in (i - 1, i + 1, i - 3, i + 3) if 0 <= j < 9 and not (abs(i - j) == 1 and i % 3 == 0 and j == i - 1) and not (abs(i - j) == 1 and j % 3 == 0 and j == i + 1)]
            j = random.choice(js)
            nums[i], nums[j] = nums[j], nums[i]
        _sess_new(bot_id2, uid, uid, "puzzle", {"nums": nums, "moves": 0})
        return jsonify(game="puzzle", st={"nums": nums})
    if g == "xo":
        return jsonify(game="xo", st={}, error="دوئل داخل مینی‌اپ به‌زودی؛ فعلاً از گروه با /play")
    return jsonify(error="بازی پیدا نشد"), 404


@app.post("/rt/<bot_id>/game/act")
def rt_game_act(bot_id):
    bot, uid, user, err = _rt_ctx(bot_id)
    if err:
        return err
    if not rate_ok(f"ga:{bot_id}:{uid}", 120, 60):
        return jsonify(error="کمی آروم‌تر"), 429
    b = request.get_json(silent=True) or {}
    cfg = bot["config"]
    bot_id2, name = str(bot["_id"]), user.get("first_name") or "بازیکن"
    g = str(b.get("game") or "")
    if g == "quiz":
        s = db.gsess.find_one({"bot": bot_id2, "u": uid, "g": "quiz"})
        if not s:
            return jsonify(error="جلسه تمام شد؛ دوباره شروع کن"), 400
        st = s["st"]
        i, pick = int(b.get("i", 0)), int(b.get("pick", -1))
        if i != st.get("qi") or not (0 <= pick < len(st["qs"][i][1])):
            return jsonify(error="پاسخ نامعتبر"), 400
        if pick == st["qs"][i][2]:
            st["score"] += 1
        st["qi"] += 1
        if st["qi"] >= len(st["qs"]):
            db.gsess.delete_one({"_id": s["_id"]})
            gain = _reward(cfg, "quiz", 3 + st["score"] * 3)
            _coins(bot_id2, uid, gain)
            _score_up(bot_id2, uid, name, "quiz", gain, periods())
            db.gusers.update_one({"bot": bot_id2, "u": uid}, {"$max": {"best.quiz": gain}})
            return jsonify(ok=True, done=True, gain=gain, score=st["score"])
        db.gsess.update_one({"_id": s["_id"]}, {"$set": {"st": st}})
        q = st["qs"][st["qi"]]
        return jsonify(ok=True, st={"q": q[0], "opts": q[1], "i": st["qi"], "total": len(st["qs"])})
    if g == "tap":
        s = db.gsess.find_one({"bot": bot_id2, "u": uid, "g": "tap"})
        if not s:
            return jsonify(error="جلسه تمام شد"), 400
        st = s["st"]
        if now().timestamp() > st["end"]:
            db.gsess.delete_one({"_id": s["_id"]})
            gain = _reward(cfg, "tap", max(1, st["n"] // 4))
            _coins(bot_id2, uid, gain)
            _score_up(bot_id2, uid, name, "tap", gain, periods())
            return jsonify(ok=True, done=True, gain=gain, n=st["n"])
        st["n"] += 1
        db.gsess.update_one({"_id": s["_id"]}, {"$set": {"st": st}})
        return jsonify(ok=True, n=st["n"], left=max(0, int(st["end"] - now().timestamp())))
    if g in ("word", "math", "typing"):
        s = db.gsess.find_one({"bot": bot_id2, "u": uid, "g": g})
        if not s:
            return jsonify(error="جلسه تمام شد"), 400
        text = str(b.get("text") or "").strip()
        st = s["st"]
        ok = (g == "word" and text == st["word"]) or (g == "math" and text.lstrip() == str(st["ans"])) or (g == "typing" and text == st["line"])
        took = max(1, int(now().timestamp() - s["t"].timestamp()))
        db.gsess.delete_one({"_id": s["_id"]})
        if not ok:
            return jsonify(ok=False, answer=str(st.get("word") or st.get("ans") or st.get("line")))
        base = {"word": max(4, 16 - took), "math": max(3, 14 - took), "typing": max(2, 20 - took // 2)}[g]
        gain = _reward(cfg, g, base)
        _coins(bot_id2, uid, gain)
        _score_up(bot_id2, uid, name, g, gain, periods())
        return jsonify(ok=True, done=True, gain=gain, took=took)
    if g == "memory":
        s = db.gsess.find_one_and_delete({"bot": bot_id2, "u": uid, "g": "memory"})
        if not s:
            return jsonify(error="جلسه تمام شد"), 400
        took = max(4, int(now().timestamp() - s["t"].timestamp()))
        gain = _reward(cfg, "memory", max(3, min(18, 34 - took // 3)))   # هرچه سریع‌تر، بیشتر؛ حداقل ۶ جفت لازم است
        _coins(bot_id2, uid, gain)
        _score_up(bot_id2, uid, name, "memory", gain, periods())
        return jsonify(ok=True, done=True, gain=gain)
    if g == "puzzle":
        if not b.get("done"):
            return jsonify(ok=True)
        s = db.gsess.find_one_and_delete({"bot": bot_id2, "u": uid, "g": "puzzle"})
        if not s:
            return jsonify(error="جلسه تمام شد"), 400
        took = max(6, int(now().timestamp() - s["t"].timestamp()))
        gain = _reward(cfg, "puzzle", max(4, min(22, 34 - took // 3)))
        _coins(bot_id2, uid, gain)
        _score_up(bot_id2, uid, name, "puzzle", gain, periods())
        return jsonify(ok=True, done=True, gain=gain)
    return jsonify(error="بازی معتبر نیست"), 400


@app.post("/rt/<bot_id>/game/daily")
def rt_game_daily(bot_id):
    bot, uid, user, err = _rt_ctx(bot_id)
    if err:
        return err
    bot_id2 = str(bot["_id"])
    d = _gu(bot_id2, uid)
    day = tehran_day()
    if (d.get("daily") or {}).get("day") == day:
        return jsonify(error="سکه‌ی امروز را قبلاً گرفتی"), 400
    streak = (d.get("daily") or {}).get("streak", 0) + 1 if (d.get("daily") or {}).get("yest") == tehran_day(1) else 1
    gain = DAILY_BASE + min(streak - 1, STREAK_MAX)
    _coins(bot_id2, uid, gain)
    db.gusers.update_one({"bot": bot_id2, "u": uid}, {"$set": {"daily": {"day": day, "yest": day, "streak": streak}}})
    return jsonify(ok=True, gain=gain, streak=streak, coins=(_gu(bot_id2, uid)).get("coins", 0))


@app.get("/rt/<bot_id>/game/board")
def rt_game_board(bot_id):
    bot, uid, user, err = _rt_ctx(bot_id)
    if err:
        return err
    p = request.args.get("p", "d")
    if p not in ("d", "w", "m"):
        p = "d"
    g = request.args.get("g", "quiz")
    rows = list(db.gscore.find({"bot": str(bot["_id"]), "g": g if g in GAME_IDS else "quiz",
                                "p": {"$in": [x for x in periods() if x.startswith(p + ":")]}},
                               sort=[("n", -1)]).limit(10))
    me = next((r["n"] for r in rows if r["u"] == uid), None)
    return jsonify(label={"d": "امروز", "w": "این هفته", "m": "این فصل"}[p],
                   rows=[{"nm": r["nm"], "n": r["n"], "me": r["u"] == uid} for r in rows], my=me)


@app.post("/rt/<bot_id>/game/buy")
def rt_game_buy(bot_id):
    bot, uid, user, err = _rt_ctx(bot_id)
    if err:
        return err
    iid = (request.get_json(silent=True) or {}).get("id")
    it = next((i for i in shop_items(bot["config"]) if i["id"] == str(iid or "")), None)
    if not it:
        return jsonify(error="آیتم پیدا نشد"), 404
    d = _coins(str(bot["_id"]), uid, -it["price"])
    if not d:
        return jsonify(error="سکه کافی نداری"), 400
    db.gusers.update_one({"bot": str(bot["_id"]), "u": uid}, {"$inc": {f"inv.{it['id']}": 1}})
    return jsonify(ok=True, coins=d["coins"])


def selftest():
    """تست بدون شبکه: منطق دوره‌ها، سکه، برد XO و کوییز"""
    assert GAMES_FA["quiz"] == "کوییز"
    assert len(QUIZ_BANK) >= 10
    win, _ = _xo_win(["X", "X", "X", "⭕", "⭕", "", "", "", ""])
    assert win == "X"
    assert _xo_win(["X", "⭕", "X", "⭕", "X", "⭕", "⭕", "X", ""]) == (None, None)
    ps = periods()
    assert len(ps) == 3 and ps[0].startswith("d:")
    assert _reward({"games": {"on": 1, "reward": {"quiz": 2}}}, "quiz", 10) == 20
    print("games selftest ok")
