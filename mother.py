# -*- coding: utf-8 -*-
"""
mother.py — ربات مادر و سیستم‌های اطرافش (وابسته به core، ai و engine)

بخش‌ها:
  • ربات مادر
  • ساخت ربات مستقیم داخل چت ربات مادر
  • ساخت و ارتقا با هوش مصنوعی (کار پس‌زمینه) و فعال‌سازی
  • اعلان همگانی، بررسی بلاک‌ها و پیام ادمین به مخاطبان
  • عضویت اجباری ربات‌ساز: پیام قفل و پنل ادمین
  • کارت‌به‌کارت (تنظیمات از پنل ادمین، تأیید دستی با دکمه)
  • یوزربات (اتصال اکانت شخصی تلگرام)

هر سیستم مسیرهای HTTP و منطق خودش رو همین‌جا دارد. مسیرهای عمومیِ مینی‌اپ (حساب، ساخت، آمار، رسانه، ادمین) در app.py هستند.
نمونه: سیستم پرداخت یا دعوت تازه ← یک بلوک تازه با بنر مخصوص خودش اینجا (یا فایل جدید و import آن در app.py).

نام‌های پایدار — فایل‌های دیگه این‌ها رو از همین فایل import می‌کنن (حذف یا تغییر نام، بقیه رو می‌شکنه).
اگه چیزی تازه برای بقیه لازمه، همین‌جا اضافه کن و در فایلِ مصرف‌کننده import کن:
  audience_targets, card_public, do_activate, fj_parse, fj_str, gen_job, lint_fa, MAX_USERBOTS, ub_limit,
  new_bot_doc, recover_jobs, run_admin_send, scan_key, scan_state, start_announce, start_block_scan,
  ub_boot, ub_ready
"""

import html as _html
import os, re, time, secrets, random, threading, asyncio
from collections import deque
from urllib.parse import quote
from datetime import timedelta

import requests
from flask import jsonify, request
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from bson.errors import InvalidId

import core
from core import (
    ADMIN_IDS, admin_only, age_sec, AI_CHAT_MODEL, AI_MSG_COST, AI_NODE_MAX_TOKENS, ai_per, app,
    authed, aware, balance, BASE_URL, BILLING, calc_cost, charge_up_to, claim_daily, credit, db, DEBUG,
    dec, _DIG, enc, ensure_user, FJ_CACHE, fj_chat, FJ_CONF, fj_conf, FJ_DEFAULT_TEXT, fj_missing,
    fj_public, get_bot, get_media, hold, _int, is_block_err, JOB_TIMEOUT, limits_of, link_referral, log, max_bots,
    MAX_PROMPT, MAX_VERSIONS, media_list, mother_link, MOTHER_SECRET, MOTHER_TOKEN, naive, now,
    ONLINE_SECS, PACKS, parse_err, perks_of, plain_html, rate_ok, redeem, REF_INVITEE, REF_INVITER,
    REF_ON, request_user, send_rich, settle_referral, tehran_day, tg, tg_html, thash, touch_user,
    APP_URL, wallet_info, activate_plan, emoji_add, plan_from_payload, plan_info, PLAN_BY_ID, PLAN_RANK, plan_of, PLANS,
)
from ai import (
    ask_llm, _gap, has_foreign, llm_post, _prog, Progress, reserve_cost, scrub_foreign, typical_cost,
)
from engine import ai_postcharge, ai_precheck, allowed_updates, sync_commands, to_jalali



# ───────────────────────── ربات مادر ─────────────────────────
def pack_from_payload(payload, uid):
    try:
        pid, owner = str(payload).split(":")
        if int(owner) != uid:
            return None
    except ValueError:
        return None
    return next((p for p in PACKS if p.get("id") == pid), None)


START_TEXT = (
    "<b>🧠 AI Engine: Ready for Evolution</b>\n"
    "<blockquote>ابزار شما برای اتوماسیون، رشد فروش و ساخت ربات‌های فوق‌هوشمند آماده‌ست.\n"
    "هیچ حد و مرزی برای رشد وجود نداره؛ همین امروز سیستم خودت رو بنا کن!</blockquote>\n"
    "​​<b>🦿 یک گام تا جهش کسب‌وکارت...</b>\n"
    "<code>​👇🏻 ورود به استودیو هوشمند (vpn روشن!)</code>"
)


def start_keyboard():
    return {"inline_keyboard": [[{"text": "Ai ساخت ربات در چت", "callback_data": "mk:new"}],
                                [{"text": "ورود به مینی‌اپ حرفه‌ای🪄", "web_app": {"url": APP_URL}, "style": "primary"}]]}


def start_media():
    d = db.settings.find_one({"_id": "start_media"})
    if d and d.get("fid"):
        return d
    old = db.settings.find_one({"_id": "start_photo"})        # سازگاری با نسخه‌ی قبلی (فقط عکس)
    return {"kind": "photo", "fid": old["fid"]} if old and old.get("fid") else None


def send_start(uid):
    """پیام استارت: اگه ادمین عکس، گیف یا ویدیو گذاشته باشه با همون، وگرنه فقط متن؛ همیشه فقط یک دکمه‌ی ورود"""
    m = start_media()
    if m:
        method, field = {"photo": ("sendPhoto", "photo"), "animation": ("sendAnimation", "animation"),
                         "video": ("sendVideo", "video")}.get(m.get("kind"), ("sendPhoto", "photo"))
        extra = {"supports_streaming": True} if method == "sendVideo" else {}
        r = tg_html(MOTHER_TOKEN, method, chat_id=uid, caption=START_TEXT, reply_markup=start_keyboard(), **{field: m["fid"]}, **extra)
        if r.get("ok"):
            return r
        log.warning("start media failed: %s", r.get("description"))
    return tg_html(MOTHER_TOKEN, "sendMessage", chat_id=uid, text=START_TEXT, reply_markup=start_keyboard(), disable_web_page_preview=True)


def fit_photo(file_id, uid):
    """تلگرام عکس‌های خیلی بلند یا خیلی عریض رو توی پیام برش می‌زنه. اینجا نسبت رو بین ۱:۱ و ۲:۱ نگه می‌داریم؛
    اگه بیرون این بازه بود، با حاشیه‌ی مشکی پد می‌شه تا کامل دیده بشه. بدون Pillow دست نمی‌زنیم. خروجی: file_id جدید یا None"""
    try:
        from PIL import Image
    except ImportError:
        log.warning("Pillow نصب نیست؛ عکس استارت بدون تغییر ذخیره شد")
        return None
    try:
        import io
        path = tg(MOTHER_TOKEN, "getFile", file_id=file_id)["result"]["file_path"]
        raw = requests.get(f"https://api.telegram.org/file/bot{MOTHER_TOKEN}/{path}", timeout=30).content
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        w, h = im.size
        ratio = w / h
        if 1.0 <= ratio <= 2.0:
            return None
        nw, nh = (h, h) if ratio < 1.0 else (w, int(w / 2.0))
        canvas = Image.new("RGB", (nw, nh), (0, 0, 0))
        canvas.paste(im, ((nw - w) // 2, (nh - h) // 2))
        canvas.thumbnail((1280, 1280))
        buf = io.BytesIO()
        canvas.save(buf, "JPEG", quality=90)
        r = requests.post(f"https://api.telegram.org/bot{MOTHER_TOKEN}/sendPhoto", data={"chat_id": uid},
                          files={"photo": ("start.jpg", buf.getvalue(), "image/jpeg")}, timeout=60).json()
        if r.get("ok"):
            tg(MOTHER_TOKEN, "deleteMessage", chat_id=uid, message_id=r["result"]["message_id"])
            return r["result"]["photo"][-1]["file_id"]
    except Exception:
        log.exception("fit_photo failed")
    return None


def _media_of(m):
    if not m:
        return None
    if m.get("animation"):          # گیف‌ها هم animation دارن هم document؛ اول animation چک می‌شه
        return "animation", m["animation"]["file_id"]
    if m.get("video"):
        return "video", m["video"]["file_id"]
    if m.get("photo"):
        return "photo", m["photo"][-1]["file_id"]
    return None


SET_MEDIA_CMDS = ("/setstartphoto", "/setstartmedia")


def mother_media(msg):
    """ادمین: /setstartphoto — عکس، گیف یا ویدیوی کوتاهِ استارت. سه روش: کپشنِ خودِ فایل، ریپلای روی فایل،
    یا دستور و بعدش ارسال فایل. اگه پیام رو مصرف کرد True برمی‌گردونه"""
    uid = msg["from"]["id"]
    if uid not in ADMIN_IDS:
        return False
    text = (msg.get("text") or msg.get("caption") or "").strip()
    cmd = text.split()[0].split("@")[0].lower() if text else ""
    media = _media_of(msg) or _media_of(msg.get("reply_to_message"))
    key = f"await_media:{uid}"
    waiting = db.settings.find_one({"_id": key})
    if waiting and time.time() - waiting.get("t", 0) > 600:
        db.settings.delete_one({"_id": key})
        waiting = None
    say = lambda t: tg(MOTHER_TOKEN, "sendMessage", chat_id=uid, text=t)
    if cmd in SET_MEDIA_CMDS and not media:
        db.settings.update_one({"_id": key}, {"$set": {"t": time.time()}}, upsert=True)
        say("عکس، گیف یا ویدیوی کوتاه استارت رو همین‌جا بفرست (به‌صورت عکس/ویدیو/گیف، نه فایل). برای انصراف /cancel")
        return True
    if waiting and cmd == "/cancel":
        db.settings.delete_one({"_id": key})
        say("لغو شد.")
        return True
    if media and (cmd in SET_MEDIA_CMDS or waiting):
        db.settings.delete_one({"_id": key})
        kind, fid = media
        note = ""
        if kind == "photo":
            nf = fit_photo(fid, uid)
            if nf:
                fid, note = nf, " (برای دیده‌شدن کامل، با حاشیه‌ی مشکی به نسبت مناسب تنظیم شد)"
        db.settings.update_one({"_id": "start_media"}, {"$set": {"kind": kind, "fid": fid, "by": uid, "t": time.time()}}, upsert=True)
        say("استارت ذخیره شد" + note + ". پیش‌نمایش:")
        send_start(uid)
        return True
    if waiting and not cmd:
        say("فقط عکس، گیف یا ویدیو قبول می‌کنم. بفرست یا /cancel بزن.")
        return True
    return False


def mother_keyboard(uid):
    rows = [[{"text": "Ai ساخت ربات در چت", "callback_data": "mk:new"}],
            [{"text": "ساخت و مدیریت ربات", "web_app": {"url": APP_URL}}]]
    link = mother_link(uid)
    if link:
        share = "https://t.me/share/url?url=" + quote(link, safe="") + "&text=" + quote("با این ربات هر رباتی که بخوای رو با هوش مصنوعی بساز", safe="")
        rows.append([{"text": "دعوت دوستان", "url": share}])
    return {"inline_keyboard": rows}


def plan_paid(sp, uid, pl):
    """پرداخت موفق اشتراک: پلن فعال یا تمدید می‌شه و هدیه‌ی توکنِ پلن اضافه می‌شه (هر پرداخت فقط یک بار)"""
    if sp.get("currency") != "XTR" or int(sp.get("total_amount", 0)) != int(pl["stars"]):
        log.warning("plan payment mismatch: %s", sp)
        return
    ensure_user(uid)
    charge = sp["telegram_payment_charge_id"]
    try:
        db.payments.insert_one({"charge": charge, "kind": "plan", "uid": uid, "plan": pl["id"], "stars": int(pl["stars"]), "t": now()})
    except DuplicateKeyError:
        return
    activate_plan(uid, pl["id"])
    credit(uid, int(pl["tokens"]), "plan", key=f"plan:{charge}")
    left = plan_info(uid)["days_left"]
    tg(MOTHER_TOKEN, "sendMessage", chat_id=uid,
       text=f"اشتراک {pl['title']} فعال شد ({left} روز اعتبار) و {pl['tokens']} توکن هدیه به حسابت اضافه شد.")


def mother_paid(msg):
    sp, uid = msg["successful_payment"], msg["from"]["id"]
    pl = plan_from_payload(sp.get("invoice_payload"), uid)
    if pl:
        return plan_paid(sp, uid, pl)
    p = pack_from_payload(sp.get("invoice_payload"), uid)
    if not p or sp.get("currency") != "XTR" or int(sp.get("total_amount", 0)) != int(p["stars"]):
        log.warning("payment mismatch: %s", sp)
        return
    ensure_user(uid)
    if credit(uid, int(p["tokens"]), "buy", key=f"pay:{sp['telegram_payment_charge_id']}"):
        tg(MOTHER_TOKEN, "sendMessage", chat_id=uid, text=f"پرداخت انجام شد و {p['tokens']} توکن به حسابت اضافه شد.")


HELP_TEXT = ("راهنمای ابر رباتساز\n\n"
             "/start باز کردن منو\n/balance موجودی توکن\n/daily جایزه‌ی روزانه\n"
             "/invite لینک دعوت (هر دعوت موفق = توکن رایگان)\n/coupon CODE ثبت کد هدیه\n/plan وضعیت اشتراک\n\n"
             "برای ساخت سریع ربات داخل همین چت، «ساخت ربات» رو بزن؛ برای مدیریت و توسعه‌ی حرفه‌ای وارد مینی‌اپ شو.")


def _u16(text, off, ln):
    """تلگرام آفست‌ها رو بر اساس UTF-16 می‌ده"""
    return (text or "").encode("utf-16-le")[off * 2:(off + ln) * 2].decode("utf-16-le", "ignore")


def mother_emoji(msg):
    """کاربر ایموجی پرمیوم (متن یا استیکر) فرستاده؛ شناسه‌ش رو توی کتابخونه‌ی ایموجی‌های خودش ذخیره می‌کنیم.
    اگه پیام رو مصرف کرد True برمی‌گردونه"""
    uid = msg["from"]["id"]
    items = []
    st = msg.get("sticker") or {}
    if st.get("custom_emoji_id"):
        items.append((st["custom_emoji_id"], st.get("emoji") or "⭐"))
    for tk, ek in (("text", "entities"), ("caption", "caption_entities")):
        for e in msg.get(ek) or []:
            if e.get("type") == "custom_emoji" and e.get("custom_emoji_id"):
                items.append((e["custom_emoji_id"], _u16(msg.get(tk), e.get("offset", 0), e.get("length", 0)) or "⭐"))
    if not items:
        return False
    ensure_user(uid)
    say = lambda t, kb=None: tg(MOTHER_TOKEN, "sendMessage", chat_id=uid, text=t, **({"reply_markup": kb} if kb else {}))
    cap = perks_of(uid)["emoji"]
    if not cap:
        say("ذخیره‌ی ایموجی پرمیوم برای اشتراک Premium و Pro فعاله. از تب «ارتقا» توی مینی‌اپ می‌تونی فعالش کنی.",
            {"inline_keyboard": [[{"text": "اشتراک", "web_app": {"url": APP_URL}}]]})
        return True
    added, full = emoji_add(uid, items)
    if added:
        say(f"{added} ایموجی به کتابخونه‌ات اضافه شد." + (f" {full} تای دیگه جا نشد (سقف {cap} ایموجی)." if full else "")
            + "\nتوی ادیتور متن و دکمه‌ها با دکمه‌ی ✨ می‌تونی ازشون استفاده کنی.")
    elif full:
        say(f"کتابخونه‌ی ایموجی‌هات پر شده (سقف {cap} ایموجی). از مینی‌اپ چندتا رو حذف کن یا اشتراکت رو ارتقا بده.")
    else:
        say("این ایموجی‌ها از قبل توی کتابخونه‌ت هستن.")
    return True


def mother_command(msg):
    uid, name = msg["from"]["id"], msg["from"].get("first_name", "")
    cmd, _, arg = (msg.get("text") or "").strip().partition(" ")
    cmd, arg = cmd.split("@")[0].lower(), arg.strip()
    d, created = ensure_user(uid, name)
    touch_user(msg["from"])
    if cmd == "/start" and created and arg.startswith("ref_") and arg[4:].isdigit():
        link_referral(uid, int(arg[4:]))
    say = lambda t, kb=True: tg(MOTHER_TOKEN, "sendMessage", chat_id=uid, text=t, **({"reply_markup": mother_keyboard(uid)} if kb else {}))
    if uid in ADMIN_IDS:
        if cmd == "/give":
            m = re.fullmatch(r"(\d+)\s+(-?\d+)", arg)
            if m and db.users.find_one({"_id": int(m.group(1))}):
                n = int(m.group(2))
                credit(int(m.group(1)), n, "admin") if n > 0 else charge_up_to(int(m.group(1)), -n, "admin")
                return say(f"{n} توکن برای {m.group(1)} ثبت شد.", False)
            return say("فرمت: /give آیدی_عددی تعداد", False)
        if cmd == "/plan":
            m = re.fullmatch(r"(\d+)\s+(free|premium|pro)(?:\s+(\d+))?", arg.lower())
            if m and db.users.find_one({"_id": int(m.group(1))}):
                activate_plan(int(m.group(1)), m.group(2), int(m.group(3) or 0) or None)
                return say(f"اشتراک {m.group(1)} روی «{PLAN_BY_ID[m.group(2)]['title']}» تنظیم شد.", False)
            return say("فرمت: /plan آیدی_عددی free|premium|pro [تعداد_روز]", False)
        if cmd == "/stats":
            t = naive()
            return say(f"کاربرها: {db.users.count_documents({})}\nآنلاین: {db.users.count_documents({'seen': {'$gte': t - timedelta(seconds=ONLINE_SECS)}})}\n"
                       f"ربات‌ها: {db.bots.count_documents({})}\nربات‌های فعال: {db.bots.count_documents({'active': True})}\n"
                       f"مخاطب ربات‌های ساخته‌شده: {db.subs.count_documents({})}", False)
        if cmd == "/announce":
            n, err = start_announce(arg, uid)
            return say(err or f"اعلان برای {n} نفر در حال ارساله.", False)
    if cmd == "/start" and arg.startswith("rcpt_") and arg[5:].isdigit():
        return card_ask_receipt(uid, int(arg[5:]))
    if cmd == "/start":
        return send_start(uid)
    tokens = wallet_info(uid)["tokens"]
    if cmd == "/balance":
        return say(f"موجودی تو: {tokens} توکن.")
    if cmd == "/help":
        return say(HELP_TEXT)
    if cmd == "/plan":
        pi = plan_info(uid)
        return say(f"اشتراک فعلی: {pi['title']}" + (f" ({pi['days_left']} روز مانده)" if pi["id"] != "free" else "")
                   + "\nبرای خرید یا تمدید Premium و Pro وارد مینی‌اپ شو و تب «ارتقا» رو باز کن.")
    if cmd == "/daily":
        r = claim_daily(uid)
        return say(f"{r[0]} توکن جایزه گرفتی. {r[1]} روز پشت‌سرهم. موجودی: {balance(uid)} توکن." if r else "جایزه‌ی امروز رو قبلاً گرفتی، فردا برگرد.")
    if cmd == "/coupon":
        if not arg:
            return say("فرمت: /coupon CODE")
        if not rate_ok(f"cp:{uid}", 8, 600):
            return say("تعداد تلاش زیاد بود، چند دقیقه بعد امتحان کن.", False)
        got, err = redeem(uid, arg)
        return say(err or f"{got} توکن اضافه شد. موجودی: {balance(uid)} توکن.")
    if cmd == "/invite":
        return say(f"لینک دعوت تو:\n{mother_link(uid)}\n\nهر دوستی که با این لینک بیاد و اولین رباتش رو بسازه، "
                   f"{REF_INVITER} توکن می‌گیری و اون هم {REF_INVITEE} توکن هدیه می‌گیره.")
    send_start(uid)


# ───────────────────────── ساخت ربات مستقیم داخل چت ربات مادر ─────────────────────────
# یک پیام واحد برای کل مسیر که فقط ویرایش می‌شود: توکن ← توضیح ← تأیید ← ساخت ← فعال‌سازی و نتیجه
_mk_watch, _mk_lock = set(), threading.Lock()
MK_STAGE = {"analyze": "تحلیل توضیحات", "build": "طراحی ساختار و بخش‌ها", "review": "بازبینی و بهینه‌سازی", "save": "ذخیره‌سازی نهایی"}
MK_TITLE = "<b>ساخت ربات جدید</b>"


def hx(t):
    return _html.escape(str(t or ""), quote=False)


def mk_btn(text, data):
    return {"text": text, "callback_data": data}


def mk_app(text, path=""):
    return {"text": text, "web_app": {"url": APP_URL + path}}


def mk_kb(*rows):
    return {"inline_keyboard": [list(r) for r in rows]}


MK_CANCEL = mk_kb([mk_btn("انصراف", "mk:x")])
MK_NEW = mk_kb([mk_btn("ساخت ربات جدید", "mk:new")])


def mk_home(chat, mid):
    """بازگشت به منوی اصلی (همان متن و دکمه‌های استارت) داخل همین پیام، بدون ساخت پیام تازه"""
    return mk_edit(chat, mid, START_TEXT, start_keyboard())


def mk_say(chat, text, kb=None):
    d = {"chat_id": chat, "text": text[:4000], "parse_mode": "HTML", "disable_web_page_preview": True}
    if kb:
        d["reply_markup"] = kb
    r = tg(MOTHER_TOKEN, "sendMessage", **d)
    if not r.get("ok") and parse_err(r):                 # تگ‌های HTML پذیرفته نشد؛ همان متن بدون تگ
        d.pop("parse_mode")
        d["text"] = plain_html(text)[:4000]
        r = tg(MOTHER_TOKEN, "sendMessage", **d)
    return r


def mk_edit(chat, mid, text, kb=None):
    """ویرایش پیام؛ اگه پیام پیدا نشد پیام تازه می‌فرسته. خروجی: message_id فعلی"""
    if not mid:
        return (mk_say(chat, text, kb).get("result") or {}).get("message_id")
    d = {"chat_id": chat, "message_id": mid, "text": text[:4000], "parse_mode": "HTML", "disable_web_page_preview": True}
    if kb:
        d["reply_markup"] = kb
    r = tg(MOTHER_TOKEN, "editMessageText", **d)
    if r.get("ok") or "not modified" in str(r.get("description", "")):
        return mid
    if r.get("error_code") == 429:
        time.sleep(min(int((r.get("parameters") or {}).get("retry_after", 2)), 10))
        return mid
    return (mk_say(chat, text, kb).get("result") or {}).get("message_id") or mid


def mk_get(uid):
    return db.mstate.find_one({"_id": uid})


def mk_put(uid, **kw):
    kw["t"] = now()
    db.mstate.update_one({"_id": uid}, {"$set": kw}, upsert=True)


def mk_fresh(uid, **kw):
    db.mstate.replace_one({"_id": uid}, {"_id": uid, "t": now(), **kw}, upsert=True)


def mk_clear(uid):
    db.mstate.delete_one({"_id": uid})


def mk_del(chat, mid):
    if mid:
        tg(MOTHER_TOKEN, "deleteMessage", chat_id=chat, message_id=mid)


def mk_show(uid, chat, text, kb=None, mid=None):
    """متن و دکمه‌های مرحله‌ی فعلی رو توی همون یک پیام می‌نویسه"""
    st = mk_get(uid) or {}
    cur = mk_edit(chat, mid or st.get("mid"), text, kb)
    if st and cur and cur != st.get("mid"):
        db.mstate.update_one({"_id": uid}, {"$set": {"mid": cur}})
    return cur


def mk_view(uid, st, note=""):
    """(متن، دکمه‌ها) برای مرحله‌ی فعلی"""
    step, user = st.get("step"), f"@{hx(st.get('username'))}"
    tail = f"\n\n⚠️ {note}" if note else ""
    if step == "token":
        rows = mk_kb([{"text": "🤖 رفتن به BotFather", "url": "https://t.me/BotFather"},
                      {"text": "باز کردن دستور /newbot", "url": "https://t.me/BotFather?start=/newbot"}],
                     [mk_btn("انصراف", "mk:x")])
        return (f"{MK_TITLE}\nمرحله 1 از 3: دریافت توکن (ویزارد قدم‌به‌قدم)\n\n"
                "1. با دکمه‌ی زیر به @BotFather برو.\n"
                "2. دستور /newbot را بفرست و یک اسم برای رباتت انتخاب کن.\n"
                "3. یک آیدی (username) که به «bot» ختم می‌شود بده، مثل <code>my_shop_bot</code>.\n"
                "4. BotFather یک توکن می‌فرستد (مثل <code>123456:ABC-xyz…</code>)؛ همان را کپی کن و همین‌جا بفرست.\n\n"
                "توکن به‌صورت رمزنگاری‌شده ذخیره می‌شود و پیام تو بلافاصله از گفتگو پاک می‌شود." + tail), rows
    if step == "desc":
        return (f"{MK_TITLE}\nمرحله 2 از 3: توضیح ربات\nربات: {user}\n\n"
                "بنویسید ربات باید چه کاری انجام دهد و چه بخش‌ها و دکمه‌هایی داشته باشد. "
                "هر چه توضیح کامل‌تر باشد، ربات دقیق‌تری ساخته می‌شود.\n\n"
                "لطفاً توضیح را در قالب یک پیام متنی ارسال کنید." + tail), MK_CANCEL
    if step == "confirm":
        prompt = st.get("prompt", "")
        reserve, have = reserve_cost(prompt, None, uid), wallet_info(uid)["tokens"]
        shown = prompt if len(prompt) <= 800 else prompt[:800] + "…"
        rows = [[mk_btn("تأیید و شروع ساخت", "mk:ok")], [mk_btn("ویرایش توضیح", "mk:edit"), mk_btn("انصراف", "mk:x")]]
        extra = ""
        if have < reserve:
            extra = "\nموجودی شما برای ساخت کافی نیست. ابتدا موجودی خود را افزایش دهید."
            rows.insert(0, [mk_app("افزایش موجودی")])
        return (f"<b>تأیید نهایی</b>\nمرحله 3 از 3\nربات: {user}\n\n<blockquote>{hx(shown)}</blockquote>\n"
                f"آیا از این توضیح اطمینان دارید؟\n\nسقف هزینه: {reserve} توکن | موجودی شما: {have} توکن\n"
                f"اگر ساخت با خطا مواجه شود، هزینه‌ای از شما کسر نمی‌شود.{extra}" + tail), mk_kb(*rows)
    if step == "activate":
        return ("<b>فعال‌سازی ربات انجام نشد</b>\nربات ساخته و ذخیره شده است، اما فعال‌سازی آن با خطا مواجه شد.\n\n"
                "اگر توکن را تغییر داده‌اید، توکن جدید را بفرستید؛ در غیر این صورت دوباره تلاش کنید." + tail,
                mk_kb([mk_btn("فعال‌سازی دوباره", "mk:act")], [mk_app("باز کردن در مینی‌اپ", f"?bot={st.get('bot')}")]))
    return "", None


def mk_render(uid, chat, note="", mid=None):
    st = mk_get(uid)
    if not st:
        return None
    text, kb = mk_view(uid, st, note)
    return mk_show(uid, chat, text, kb, mid) if text else None


def mk_begin(uid, chat):
    st = mk_get(uid)
    if st and st.get("step") == "building":
        return mk_resume(uid, chat)
    if db.bots.count_documents({"owner": uid}) >= max_bots(uid):
        return mk_say(chat, f"{MK_TITLE}\n\nسقف ربات‌های شما {max_bots(uid)} عدد است و امکان ساخت ربات جدید وجود ندارد. "
                            "با خرید اشتراک Premium یا Pro، این سقف بیشتر می‌شود. برای مدیریت یا حذف ربات‌ها وارد مینی‌اپ شوید.",
                      mk_kb([mk_app("ورود به مینی‌اپ")]))
    have, need = wallet_info(uid)["tokens"], typical_cost()
    if have < need:
        return mk_say(chat, f"{MK_TITLE}\n\nموجودی شما ({have} توکن) برای ساخت ربات کافی نیست و حداقل به حدود {need} توکن نیاز دارید. "
                            "از مینی‌اپ می‌توانید توکن بخرید، جایزه روزانه دریافت کنید یا دوستان خود را دعوت کنید.",
                      mk_kb([mk_app("افزایش موجودی")]))
    if st:
        mk_del(chat, st.get("mid"))                      # پیام قبلی مسیر؛ همیشه فقط یک پیام فعال می‌ماند
    mk_fresh(uid, step="token")
    return mk_render(uid, chat)


def mother_flow(msg):
    """پیام‌های متنیِ کاربری که وسط Ai ساخت ربات در چته. اگه پیام رو مصرف کرد True"""
    uid, chat = msg["from"]["id"], msg["chat"]["id"]
    st = mk_get(uid)
    if not st:
        return False
    text = (msg.get("text") or "").strip()
    step = st.get("step")
    if text.startswith("/"):
        cmd = text.split()[0].split("@")[0].lower()
        if cmd in ("/start", "/cancel") and step != "building":
            mk_clear(uid)
            if cmd == "/cancel":
                mk_del(chat, msg.get("message_id"))
                mk_home(chat, st.get("mid"))
                return True
            mk_del(chat, st.get("mid"))
        return False
    mk_del(chat, msg.get("message_id"))                  # پیام کاربر پاک می‌شه تا چت تمیز بمونه
    if step == "building":
        mk_resume(uid, chat)
        return True
    if step in ("token", "activate"):
        m = re.search(r"\d{6,12}:[\w-]{30,50}", text)
        if not m:
            mk_render(uid, chat, "متنی که فرستادید شبیه توکن ربات نیست. لطفاً توکن را مستقیماً از BotFather کپی کنید.")
            return True
        tok = m.group(0)
        if not rate_ok(f"mkt:{uid}", 8, 600):
            mk_render(uid, chat, "تعداد تلاش‌ها زیاد بود. لطفاً چند دقیقه بعد دوباره امتحان کنید.")
            return True
        me = tg(tok, "getMe")
        if not me.get("ok"):
            mk_render(uid, chat, "این توکن معتبر نیست یا باطل شده است. لطفاً توکن درست را ارسال کنید.")
            return True
        th, uname = thash(tok), (me.get("result") or {}).get("username", "")
        dup = db.bots.find_one({"token_hash": th})
        if dup and str(dup["_id"]) != st.get("bot"):
            mk_render(uid, chat, "این توکن قبلاً برای ربات دیگری ثبت شده است. لطفاً در BotFather یک ربات جدید بسازید.")
            return True
        if step == "activate":
            mk_put(uid, token_enc=enc(tok), token_hash=th, username=uname)
            return mk_activate(uid, chat)
        mk_put(uid, step="desc", token_enc=enc(tok), token_hash=th, username=uname)
        mk_render(uid, chat)
        return True
    if step in ("desc", "confirm"):
        if not text:
            mk_render(uid, chat, "فقط توضیح متنی پذیرفته می‌شود.")
            return True
        if len(text) < 10:
            mk_render(uid, chat, "توضیح شما بسیار کوتاه است. لطفاً کمی کامل‌تر بنویسید.")
            return True
        mk_put(uid, step="confirm", prompt=text[:MAX_PROMPT])
        mk_render(uid, chat)
        return True
    return False


def mk_progress_text(j, tick):
    pr = j.get("prog") or {}
    p = max(2.0, min(float(pr.get("p") or 2), 99.0))
    on = int(p / 100 * 12)
    out = ["<b>در حال ساخت ربات</b>", "",
           f"مرحله: {MK_STAGE.get(pr.get('st') or 'analyze', 'پردازش')}{'.' * (tick % 3 + 1)}",
           f"{'▰' * on}{'▱' * (12 - on)}  {int(p)}%"]
    if pr.get("n"):
        out.append(f"بخش‌های طراحی‌شده: {pr['n']}" + (f" | آخرین بخش: «{hx(pr['ti'])}»" if pr.get("ti") else ""))
    out += ["", "نتیجه در همین پیام اعلام می‌شود."]
    return "\n".join(out)


def mk_watch(uid, chat, jid):
    """پیام پیشرفت رو زنده ویرایش می‌کنه تا کار تموم بشه، بعد ربات رو فعال می‌کنه"""
    with _mk_lock:
        if uid in _mk_watch:
            return
        _mk_watch.add(uid)
    try:
        last, tick, t0 = "", 0, time.time()
        while time.time() - t0 < JOB_TIMEOUT + 90:
            j = db.jobs.find_one({"_id": jid})
            if not j or j["status"] in ("done", "error"):
                break
            tg(MOTHER_TOKEN, "sendChatAction", chat_id=chat, action="typing")      # بالای چت «در حال نوشتن…» تا پایان ساخت
            txt = mk_progress_text(j, tick)
            tick += 1
            if txt != last:
                mk_show(uid, chat, txt)
                last = txt
            time.sleep(2.6)
        j = db.jobs.find_one({"_id": jid}) or {}
        if j.get("status") == "done" and j.get("bot"):
            mk_put(uid, step="activate", bot=j["bot"], cost=j.get("cost", 0))
            mk_activate(uid, chat)
        else:
            mk_put(uid, step="confirm")
            mk_render(uid, chat, "ساخت ربات ناموفق بود. " + hx(j.get("error") or "زمان ساخت بیش از حد طول کشید.") + " هزینه‌ای از شما کسر نشد.")
    except Exception:
        log.exception("chat build watcher crashed")
    finally:
        with _mk_lock:
            _mk_watch.discard(uid)


def mk_resume(uid, chat):
    """اگه سرور وسط ساخت ری‌استارت شده یا ناظر قطع شده، پیگیری رو دوباره شروع می‌کنه"""
    st = mk_get(uid) or {}
    if uid not in _mk_watch and st.get("job"):
        threading.Thread(target=mk_watch, args=(uid, chat, st["job"]), daemon=True).start()


def mk_activate(uid, chat):
    st = mk_get(uid) or {}
    mid = st.get("mid")
    bot = get_bot(st.get("bot"), uid)
    if not bot:
        mk_clear(uid)
        return mk_edit(chat, mid, "ربات ساخته‌شده پیدا نشد. لطفاً وضعیت را از مینی‌اپ بررسی کنید.", mk_kb([mk_app("ورود به مینی‌اپ")]))
    try:
        token = dec(st["token_enc"])
    except Exception:
        token = ""
    doc, err = do_activate(bot, token)
    if err:
        mk_put(uid, step="activate")
        return mk_render(uid, chat, "خطا: " + hx(err[0]))
    mk_clear(uid)
    cfg = doc.get("config") or {}
    titles = [str(n.get("title") or "") for n in (cfg.get("nodes") or {}).values() if isinstance(n, dict) and n.get("title")]
    t = f"✅ <b>ربات شما ساخته و فعال شد</b>\n@{hx(doc.get('username'))} | «{hx(doc.get('name'))}»\n"
    if titles:
        t += f"\nبخش‌ها ({len(titles)}): " + "، ".join(hx(x[:30]) for x in titles[:5]) + ("، …" if len(titles) > 5 else "") + "\n"
    think = (doc.get("thinking") or "").strip()
    if think:
        t += f"\n<blockquote expandable>{hx(think[:500])}</blockquote>\n"
    t += (f"\nهزینه‌ی ساخت: {int(st.get('cost') or 0)} توکن | موجودی: {wallet_info(uid)['tokens']} توکن\n\n"
          "ادامه‌ی توسعه، ویرایش با هوش مصنوعی، رسانه، پیام همگانی و آمار ربات فقط از طریق مینی‌اپ امکان‌پذیر است.\n"
          "برای دریافت پیام کاربران، یک بار ربات خود را استارت کنید.")
    kb = mk_kb([{"text": "ورود به ربات", "url": f"https://t.me/{doc.get('username')}"}],
               [mk_app("ارتقا و ادامه توسعه در مینی‌اپ", f"?bot={bot['_id']}")],
               [mk_btn("ساخت ربات جدید", "mk:new")])
    return mk_edit(chat, mid, t, kb)


def mk_build(uid, chat):
    """تأیید نهایی: بررسی‌ها، شروع کار هوش مصنوعی و ناظر پیشرفت"""
    st = mk_get(uid)
    if not st or st.get("step") != "confirm" or not st.get("prompt") or not st.get("token_enc"):
        return None
    if not db.mstate.find_one_and_update({"_id": uid, "step": "confirm"}, {"$set": {"step": "building", "t": now()}}):
        return None                                           # کلیک دوباره‌ی همزمان
    prompt, reserve, note = st["prompt"], 0, ""
    if db.bots.count_documents({"owner": uid}) >= max_bots(uid):
        note = f"سقف ربات‌های شما {max_bots(uid)} عدد است و امکان ساخت ربات جدید وجود ندارد."
    elif not rate_ok(f"gen:{uid}", 10, 60):
        note = "درخواست‌ها زیاد بود. لطفاً چند لحظه بعد دوباره تلاش کنید."
    elif any(age_sec(j["t"]) < JOB_TIMEOUT for j in db.jobs.find({"uid": uid, "status": {"$in": ["running", "saving"]}})):
        note = "کار دیگری از شما هنوز در حال انجام است. لطفاً کمی صبر کنید."
    else:
        ensure_user(uid)
        reserve = reserve_cost(prompt, None, uid)
        if not hold(uid, reserve):
            note = f"موجودی شما کافی نیست. این ساخت تا سقف {reserve} توکن هزینه دارد."
    if note:
        mk_put(uid, step="confirm")
        return mk_render(uid, chat, note)
    jid = secrets.token_hex(8)
    db.jobs.insert_one({"_id": jid, "uid": uid, "status": "running", "hold": 0, "t": now()})
    mk_put(uid, job=jid)
    threading.Thread(target=gen_job, args=(jid, uid, None, prompt, reserve), daemon=True).start()
    mk_show(uid, chat, mk_progress_text({}, 0))
    threading.Thread(target=mk_watch, args=(uid, chat, jid), daemon=True).start()


def mother_callback(cq):
    uid, data = cq["from"]["id"], str(cq.get("data") or "")
    m = cq.get("message") or {}
    chat, cmid = (m.get("chat") or {}).get("id"), m.get("message_id")

    def ack(text="", alert=False):
        d = {"callback_query_id": cq["id"]}
        if text:
            d.update(text=text, show_alert=alert)
        tg(MOTHER_TOKEN, "answerCallbackQuery", **d)

    if not data.startswith("mk:") or not chat or (m.get("chat") or {}).get("type") != "private":
        return ack()
    ensure_user(uid, cq["from"].get("first_name", ""))
    touch_user(cq["from"])
    act, st = data[3:], mk_get(uid)
    if act == "new":
        ack()
        return mk_begin(uid, chat)
    if act == "x":
        if st and st.get("step") == "building":
            return ack("ساخت در حال انجام است و قابل لغو نیست.", True)
        mk_clear(uid)
        ack()
        return mk_home(chat, (st or {}).get("mid") or cmid)
    if not st:
        ack()
        return mk_home(chat, cmid)
    if act == "edit" and st.get("step") == "confirm":
        mk_put(uid, step="desc")
        ack()
        return mk_render(uid, chat)
    if act == "ok":
        ack("ساخت شروع شد")
        return mk_build(uid, chat)
    if act == "act" and st.get("step") == "activate":
        ack()
        return mk_activate(uid, chat)
    ack()


# ───────────────────────── ساخت و ارتقا با هوش مصنوعی (کار پس‌زمینه) و فعال‌سازی ─────────────────────────
def new_bot_doc(uid, cfg, thinking):
    doc = {"owner": uid, "name": cfg["name"], "config": cfg, "thinking": thinking, "versions": [],
           "active": False, "secret": secrets.token_hex(16), "created": now(), "updated": now()}
    doc["_id"] = db.bots.insert_one(doc).inserted_id
    return doc


def report_gaps(uid, bot, prompt, items):
    """وقتی کاربر چیزی خواسته که موتور واقعاً نمی‌تونه: متن گزارشِ نوشته‌شده‌ی خودِ هوش مصنوعی برای ادمین ربات‌ساز فرستاده و ذخیره می‌شه"""
    if not items:
        return
    try:
        u = db.users.find_one({"_id": uid}) or {}
        who = f"{u.get('tg_name') or ''} {('@' + u['tg_user']) if u.get('tg_user') else ''}".strip() or "بدون نام"
        db.gaps.insert_one({"uid": uid, "bot": str(bot["_id"]) if bot else "", "prompt": prompt[:1500], "items": items, "t": now()})
        lines = [f"گزارش هوش مصنوعی: درخواستی که ربات‌ساز کامل نتونست انجام بده",
                 f"کاربر: {who} (آیدی {uid})",
                 f"ربات: {(bot or {}).get('name') or 'جدید'}" + (f" (@{bot['username']})" if bot and bot.get("username") else ""),
                 "", "متن درخواست کاربر:", prompt[:700]]
        for i, x in enumerate(items, 1):
            lines += ["", f"{i}) خواسته: {x['want']}", f"چرا نشد: {x['why'] or '-'}", f"راه ارتقا: {x['upgrade'] or '-'}"]
        text = "\n".join(lines)[:3900]
        for admin in ADMIN_IDS:
            tg(MOTHER_TOKEN, "sendMessage", chat_id=admin, text=text)
    except Exception:
        log.exception("report_gaps failed")


def gen_job(jid, uid, bot_id, prompt, reserve):
    """کار پس‌زمینه: تا پایان کار چیزی از موجودی کم نمی‌شه؛ در پایان فقط هزینه‌ی واقعی (حداکثر سقف رزرو) کسر می‌شه"""
    acc = []
    _gap.items = []
    _prog.cb = Progress(jid)
    try:
        bot = db.bots.find_one({"_id": ObjectId(bot_id)}) if bot_id else None
        thinking, cfg, ideas = ask_llm(prompt, bot["config"] if bot else None, media_list(uid), acc, nodes_cap=limits_of(uid)["nodes"])
        cost = reserve if BILLING == "fixed" else min(reserve, calc_cost(sum(x[0] for x in acc), sum(x[1] for x in acc), uid=uid))
        if not db.jobs.find_one_and_update({"_id": jid, "status": "running"}, {"$set": {"status": "saving"}}):
            return                                  # کار منقضی شده و توکن‌ها برگشته؛ نتیجه رو دور می‌ریزیم
        _prog.cb.stage("save", 98.0)
        if bot:
            db.bots.update_one({"_id": bot["_id"]}, {
                "$set": {"config": cfg, "name": cfg["name"], "thinking": thinking, "updated": now()},
                "$push": {"versions": {"$each": [bot["config"]], "$slice": -(MAX_VERSIONS + perks_of(uid)["ver"])}},
                "$unset": {"last_manual": ""}})
            bot = db.bots.find_one({"_id": bot["_id"]})
            sync_commands(bot, cfg)
        else:
            bot = new_bot_doc(uid, cfg, thinking)
        cost = charge_up_to(uid, cost, "edit" if bot_id else "gen")      # فقط هزینه‌ی واقعی، همین الان کسر می‌شه
        db.jobs.update_one({"_id": jid}, {"$set": {"status": "done", "bot": str(bot["_id"]), "ideas": ideas, "cost": cost}})
        if REF_ON == "create":
            settle_referral(uid)
        report_gaps(uid, bot, prompt, getattr(_gap, "items", []))
    except Exception as e:
        log.exception("generate failed")
        msg = "ساخت ربات ناموفق بود و چیزی از توکن‌هات کم نشد. دوباره امتحان کن یا توضیح رو ساده‌تر بنویس."
        if DEBUG:
            msg += f"\n[{type(e).__name__}] {str(e)[:300]}"
        db.jobs.find_one_and_update({"_id": jid, "status": {"$in": ["running", "saving"]}}, {"$set": {"status": "error", "error": msg}})
    finally:
        _prog.cb = None


def recover_jobs():
    """بعد از ری‌استارت: کارهای نیمه‌کاره‌ی قدیمی رو می‌بنده (چیزی کسر نشده بود)"""
    try:
        for j in db.jobs.find({"status": {"$in": ["running", "saving"]}}):
            db.jobs.find_one_and_update({"_id": j["_id"], "status": j["status"]}, {"$set": {"status": "error", "error": "سرور ری‌استارت شد و چیزی از توکن‌هات کم نشد. دوباره امتحان کن."}})
    except Exception:
        log.exception("recover_jobs failed")


def lint_fa(cfg, issues):
    """همان خروجی lint را به فارسیِ ساده برای نمایش به کاربر برمی‌گرداند (lint خودش برای AI انگلیسی می‌ماند)"""
    nodes = cfg.get("nodes", {})
    name = lambda i: "«" + (nodes.get(i, {}).get("title") or i) + "»"
    names = lambda tail: "، ".join(name(x.strip()) for x in tail.split(",") if x.strip())
    out = []
    for m in issues:
        try:
            if m.startswith("unreachable nodes"):
                out.append("این بخش‌ها از هیچ‌جا قابل‌دسترس نیستند: " + names(m.rsplit("): ", 1)[1])
                           + ". آن‌ها را با یک دکمه یا مسیر به بخش دیگری وصل کن، یا حذفشان کن.")
            elif m.startswith("dead-end nodes"):
                out.append("بعد از این بخش‌ها کاربر راهی برای ادامه ندارد: " + names(m.rsplit("): ", 1)[1])
                           + ". یک دکمه‌ی «بازگشت» یا «منوی اصلی» به آن‌ها اضافه کن.")
            elif m.startswith("leaderboard variable"):
                v = m.split("'")[1]; i = m.split("'")[3]
                out.append(f"جدول برترین‌های بخش {name(i)} بر پایه‌ی متغیر «{v}» است، اما هیچ اقدامی این متغیر را زیاد نمی‌کند. یک اقدام «افزودن» یا «تنظیم» برایش بگذار یا جدول را بردار.")
            elif m.startswith("ticket node"):
                i = m.split("'")[1]
                out.append(f"بخشِ تیکتِ {name(i)} دکمه‌ی بازگشت و بخش بعدی ندارد؛ کاربر نمی‌تواند از آن بیرون بیاید.")
            elif m.startswith("variables that are read"):
                out.append("این متغیرها در متن‌ها یا شرط‌ها استفاده شده‌اند، ولی هیچ اقدام یا فرمی مقدارشان را نمی‌نویسد: "
                           + "، ".join(x.strip() for x in m.rsplit("): ", 1)[1].split(",") if x.strip()))
            else:
                out.append(m)
        except Exception:
            out.append(m)
    return out


def do_activate(bot, token):
    """فعال‌سازی ربات با توکن (مشترک بین مینی‌اپ و چت). خروجی: (سند ربات، None) یا (None، (پیام، کد وضعیت))"""
    bot_id, uid = str(bot["_id"]), bot["owner"]
    if not re.match(r"^\d{6,12}:[\w-]{30,50}$", token):
        return None, ("فرمت توکن درست نیست", 400)
    me = tg(token, "getMe")
    if not me.get("ok"):
        return None, ("توکن معتبر نیست", 400)
    th = thash(token)
    if db.bots.find_one({"token_hash": th, "_id": {"$ne": bot["_id"]}}):
        return None, ("این توکن قبلاً برای ربات دیگه‌ای ثبت شده", 400)
    r = tg(token, "setWebhook", url=f"{BASE_URL}/hook/{bot_id}", secret_token=bot["secret"],
           allowed_updates=allowed_updates(bot["config"]), drop_pending_updates=True)
    if not r.get("ok"):
        return None, ("اتصال وبهوک ناموفق بود", 502)
    tg(token, "setMyCommands", commands=[{"command": "start", "description": "شروع"}] + [
        {"command": c, "description": c} for c in bot["config"]["commands"]])
    db.bots.update_one({"_id": bot["_id"]}, {"$set": {
        "token_enc": enc(token), "token_hash": th, "username": me["result"]["username"],
        "active": True, "wh_pay": True, "wh_mod": bool(bot["config"].get("mod")), "updated": now()}})
    try:
        sync_commands(db.bots.find_one({"_id": bot["_id"]}), bot["config"])
    except Exception:
        log.exception("sync after activate failed")
    if REF_ON == "activate":
        settle_referral(uid)
    return db.bots.find_one({"_id": bot["_id"]}), None


# ───────────────────────── اعلان همگانی، بررسی بلاک‌ها و پیام ادمین به مخاطبان ─────────────────────────
def audience_targets():
    """ربات‌های فعال و مخاطب‌هاشون، بدون خودِ سازنده‌ی هر ربات"""
    for bt in db.bots.find({"active": True, "token_enc": {"$exists": True}}):
        bid = str(bt["_id"])
        chats = [x["chat"] for x in db.subs.find({"bot": bid, "blocked": {"$ne": True}, "chat": {"$ne": bt["owner"]}}, {"chat": 1})]
        if chats:
            yield bt, bid, chats


def ann_new(kind, admin, text, total, label="", mid=""):
    """رکورد تاریخچه‌ی یک ارسال؛ آیدی رکورد برگردونده می‌شه (خالی اگه ثبت نشد)"""
    rid = secrets.token_hex(6)
    try:
        db.announces.insert_one({"_id": rid, "kind": kind, "by": admin, "text": str(text or "")[:300], "media": bool(mid), "label": label,
                                 "total": int(total), "ok": 0, "sent": 0, "done": False, "t": now()})
    except Exception:
        log.exception("ann_new failed")
        return ""
    return rid


def ann_prog(rid, ok, sent, done=False):
    if not rid:
        return
    try:
        s = {"ok": int(ok), "sent": int(sent)}
        if done:
            s.update(done=True, fin=now())
        db.announces.update_one({"_id": rid}, {"$set": s})
    except Exception:
        pass


def run_announce(text, admin, builders=True, audience=False, mid="", fmt="", ids=None, rec=""):
    ok_b = tot_b = ok_a = tot_a = 0
    sent_n = 0
    try:
        if builders:
            kb = {"inline_keyboard": [[{"text": "باز کردن ابر رباتساز", "web_app": {"url": APP_URL}}]]}
            targets = ids if ids is not None else [u["_id"] for u in db.users.find({}, {"_id": 1})]
            tot_b = len(targets)
            for u_id in targets:
                sent, blocked = send_rich(MOTHER_TOKEN, "mother", u_id, text, mid, fmt, kb)
                ok_b += 1 if sent else 0
                sent_n += 1
                if sent_n % 25 == 0:
                    ann_prog(rec, ok_b + ok_a, sent_n)
                if blocked:
                    db.users.update_one({"_id": u_id}, {"$set": {"mb_blocked": True}})
                elif sent:
                    db.users.update_one({"_id": u_id, "mb_blocked": True}, {"$set": {"mb_blocked": False}})
                time.sleep(0.05)
        if audience:
            for bt, bid, chats in audience_targets():
                token = dec(bt["token_enc"])
                tot_a += len(chats)
                for chat in chats:
                    sent, blocked = send_rich(token, bid, chat, text, mid, fmt)
                    ok_a += 1 if sent else 0
                    sent_n += 1
                    if sent_n % 25 == 0:
                        ann_prog(rec, ok_b + ok_a, sent_n)
                    if blocked:
                        db.subs.update_one({"_id": f"{bid}:{chat}"}, {"$set": {"blocked": True}})
                    time.sleep(0.04)
    except Exception:
        log.exception("announce crashed")
    finally:
        db.locks.delete_one({"_id": "announce"})
        ann_prog(rec, ok_b + ok_a, sent_n, done=True)
    parts = []
    if builders:
        parts.append(f"سازنده‌ها: {ok_b} از {tot_b} نفر")
    if audience:
        parts.append(f"مخاطب ربات‌های فعال: {ok_a} از {tot_a} نفر")
    tg(MOTHER_TOKEN, "sendMessage", chat_id=admin, text="اعلان تموم شد.\n" + "\n".join(parts))


def start_announce(text, admin, builders=True, audience=False, mid="", fmt="", ids=None):
    """(تعداد گیرنده، پیام خطا). ids: فقط همین سازنده‌ها (انتخاب دستی)؛ mid: رسانه‌ی کتابخونه‌ی ادمین؛ fmt: 'html' یا ''"""
    text = str(text or "").strip()[:3500]
    mid = str(mid or "")
    if mid and not get_media(mid, admin):
        mid = ""
    if not text and not mid:
        return 0, "متن یا رسانه‌ی اعلان رو وارد کن"
    if not mid and len(text) < 3:
        return 0, "متن اعلان رو بنویس"
    if ids is not None:
        ids = [x["_id"] for x in db.users.find({"_id": {"$in": list(ids)}}, {"_id": 1})]
        if not ids:
            return 0, "کاربری برای ارسال انتخاب نشده"
        builders, audience = True, False
    if not (builders or audience):
        return 0, "حداقل یکی از گیرنده‌ها رو انتخاب کن"
    try:
        db.locks.insert_one({"_id": "announce", "t": now()})
    except DuplicateKeyError:
        lk = db.locks.find_one({"_id": "announce"})
        if lk and age_sec(lk["t"]) < 3600:
            return 0, "یه اعلان دیگه هنوز در حال ارساله"
        db.locks.update_one({"_id": "announce"}, {"$set": {"t": now()}})
    if ids is not None:
        n, kind, label = len(ids), "users", f"{len(ids)} کاربر انتخاب‌شده"
    else:
        n = db.users.count_documents({}) if builders else 0
        if audience:
            n += sum(len(c) for _, _, c in audience_targets())
        kind = "both" if builders and audience else "builders" if builders else "audience"
        label = {"both": "سازنده‌ها + مخاطبان ربات‌ها", "builders": "سازنده‌های ربات‌ساز", "audience": "مخاطبان ربات‌های فعال"}[kind]
    rec = ann_new(kind, admin, text, n, label, mid)
    threading.Thread(target=run_announce, args=(text, admin, builders, audience, mid, fmt, ids, rec), daemon=True).start()
    return n, ""


def scan_key(bot=None):
    return f"rb:{bot['_id']}" if bot else "rb:mother"


def scan_state(key):
    lk = db.locks.find_one({"_id": key})
    if lk and age_sec(lk["t"]) < 3600:
        return {"done": int(lk.get("done", 0)), "total": int(lk.get("total", 0))}
    return None


def run_block_scan(bot, admin):
    key = scan_key(bot)
    blocked_n = total = 0
    try:
        if bot:
            token, bot_id = dec(bot["token_enc"]), str(bot["_id"])
            rows = [(x["_id"], x["chat"]) for x in db.subs.find({"bot": bot_id}, {"chat": 1})]
        else:
            token = MOTHER_TOKEN
            rows = [(x["_id"], x["_id"]) for x in db.users.find({}, {"_id": 1})]
        total = len(rows)
        db.locks.update_one({"_id": key}, {"$set": {"total": total, "done": 0}})
        for i, (rid, chat) in enumerate(rows, 1):
            r = tg(token, "sendChatAction", chat_id=chat, action="typing")
            if r.get("error_code") == 429:
                time.sleep(min(int((r.get("parameters") or {}).get("retry_after", 1)), 30))
                r = tg(token, "sendChatAction", chat_id=chat, action="typing")
            state = False if r.get("ok") else (True if is_block_err(r) else None)   # None = خطای موقت؛ وضعیت قبلی بمونه
            if state is not None:
                if bot:
                    db.subs.update_one({"_id": rid}, {"$set": {"blocked": state}})
                else:
                    db.users.update_one({"_id": rid}, {"$set": {"mb_blocked": state}})
                blocked_n += 1 if state else 0
            if i % 20 == 0:
                db.locks.update_one({"_id": key}, {"$set": {"done": i}})
            time.sleep(0.04)
    except Exception:
        log.exception("block scan crashed")
    finally:
        db.locks.delete_one({"_id": key})
    who = f"ربات @{bot.get('username') or bot.get('name', '')}" if bot else "کاربران ربات‌ساز"
    tg(MOTHER_TOKEN, "sendMessage", chat_id=admin, text=f"بررسی بلاک‌ها ({who}) تموم شد. از {total} نفر، {blocked_n} نفر بلاک کرده‌ن.")


def start_block_scan(bot, admin):
    key = scan_key(bot)
    try:
        db.locks.insert_one({"_id": key, "t": now(), "total": 0, "done": 0})
    except DuplicateKeyError:
        lk = db.locks.find_one({"_id": key})
        if lk and age_sec(lk["t"]) < 3600:
            return False
        db.locks.update_one({"_id": key}, {"$set": {"t": now(), "total": 0, "done": 0}})
    threading.Thread(target=run_block_scan, args=(bot, admin), daemon=True).start()
    return True


def run_admin_send(bot, chats, text, admin, mid="", fmt="", rec=""):
    bot_id, token, ok, n = str(bot["_id"]), dec(bot["token_enc"]), 0, 0
    try:
        for chat in chats:
            sent, blocked = send_rich(token, bot_id, chat, text, mid, fmt)
            n += 1
            if sent:
                ok += 1
                db.subs.update_one({"_id": f"{bot_id}:{chat}", "blocked": True}, {"$set": {"blocked": False}})
            elif blocked:
                db.subs.update_one({"_id": f"{bot_id}:{chat}"}, {"$set": {"blocked": True}})
            if n % 25 == 0:
                ann_prog(rec, ok, n)
            time.sleep(0.04)
    except Exception:
        log.exception("admin send crashed")
    finally:
        db.locks.delete_one({"_id": f"abc:{bot_id}"})
        ann_prog(rec, ok, n, done=True)
    tg(MOTHER_TOKEN, "sendMessage", chat_id=admin, text=f"اطلاعیه‌ی ربات @{bot.get('username') or bot.get('name', '')} تموم شد. به {ok} نفر از {len(chats)} نفر رسید.")


def run_multi_send(pairs, text, admin, mid="", fmt="", rec=""):
    """ارسال اطلاعیه از چند ربات پشت‌سرهم. pairs = [(bot_doc, [chat, ...]), ...]؛ قفل abc:<bot> را خودش آزاد می‌کنه"""
    ok = n = 0
    try:
        for bot, chats in pairs:
            bot_id, token = str(bot["_id"]), dec(bot["token_enc"])
            try:
                for chat in chats:
                    sent, blocked = send_rich(token, bot_id, chat, text, mid, fmt)
                    n += 1
                    if sent:
                        ok += 1
                        db.subs.update_one({"_id": f"{bot_id}:{chat}", "blocked": True}, {"$set": {"blocked": False}})
                    elif blocked:
                        db.subs.update_one({"_id": f"{bot_id}:{chat}"}, {"$set": {"blocked": True}})
                    if n % 25 == 0:
                        ann_prog(rec, ok, n)
                    time.sleep(0.04)
            finally:
                db.locks.delete_one({"_id": f"abc:{bot_id}"})
    except Exception:
        log.exception("multi send crashed")
    finally:
        for bot, _ in pairs:
            db.locks.delete_one({"_id": f"abc:{bot['_id']}"})
        ann_prog(rec, ok, n, done=True)
    tg(MOTHER_TOKEN, "sendMessage", chat_id=admin, text=f"اطلاعیه‌ی {len(pairs)} ربات تموم شد. به {ok} نفر از {n} نفر رسید.")


# ───────────────────────── عضویت اجباری ربات‌ساز: پیام قفل و پنل ادمین ─────────────────────────
def fj_send(chat, conf, miss):
    rows = [[{"text": "عضویت در " + x["label"], "url": x["url"]}] for x in fj_public(conf, miss)["channels"]]
    rows.append([{"text": "✅ عضو شدم", "callback_data": "fj:chk"}])
    tg_html(MOTHER_TOKEN, "sendMessage", chat_id=chat, text=(conf.get("text") or FJ_DEFAULT_TEXT)[:4000],
            reply_markup={"inline_keyboard": rows}, disable_web_page_preview=True)


def fj_gate_msg(msg):
    """پیام کاربر عضو نیست؟ پیام عضویت می‌فرسته و True برمی‌گردونه. /start (با لینک دعوت) یادش می‌مونه"""
    conf = fj_conf()
    if not conf:
        return False
    uid = msg["from"]["id"]
    miss = fj_missing(uid, conf)
    if not miss:
        return False
    text = (msg.get("text") or "").strip()
    if text.startswith("/start"):
        db.fjp.replace_one({"_id": uid}, {"_id": uid, "text": text[:200], "t": now()}, upsert=True)
    fj_send(msg["chat"]["id"], conf, miss)
    return True


def fj_gate_cb(cq):
    conf, uid, data = fj_conf(), cq["from"]["id"], str(cq.get("data") or "")
    ans = lambda **kw: tg(MOTHER_TOKEN, "answerCallbackQuery", callback_query_id=cq["id"], **kw)
    if data == "fj:chk":
        FJ_CACHE.pop(uid, None)
        if conf and fj_missing(uid, conf):
            ans(text="هنوز عضو نشدی.", show_alert=True)
            return True
        ans()
        m = cq.get("message") or {}
        if m.get("message_id"):
            tg(MOTHER_TOKEN, "deleteMessage", chat_id=m["chat"]["id"], message_id=m["message_id"])
        p = db.fjp.find_one_and_delete({"_id": uid})
        mother_command({"from": cq["from"], "chat": {"id": uid, "type": "private"}, "text": (p or {}).get("text") or "/start"})
        return True
    if not conf:
        return False
    miss = fj_missing(uid, conf)
    if not miss:
        return False
    ans(text="اول عضو کانال شو", show_alert=True)
    fj_send(uid, conf, miss)
    return True


def fj_parse(raw):
    """«@a t.me/b -1001234=https://t.me/+abc» → [{id, url}] (حداکثر ۳ تا)"""
    items = [x for x in re.split(r"[\s,،]+", str(raw or "").strip()) if x][:3]
    out = []
    for it in items:
        cid, _, link = it.partition("=")
        if re.fullmatch(r"-?\d{5,20}", cid):
            if not re.match(r"^https://t\.me/\S+$", link):
                return None, f"برای کانال خصوصی «{cid}» لینک دعوت هم بده؛ مثل {cid}=https://t.me/+abc"
            out.append({"id": cid, "url": link})
            continue
        u = re.sub(r"^(https?://)?(t\.me|telegram\.me)/", "", it, flags=re.I).lstrip("@")
        if not re.match(r"^[A-Za-z][A-Za-z0-9_]{4,31}$", u):
            return None, f"آیدی کانال «{it}» معتبر نیست"
        if not any(c["id"] == "@" + u for c in out):
            out.append({"id": "@" + u, "url": "https://t.me/" + u})
    return out, ""


def fj_str(c):
    return c["id"] if c["id"].startswith("@") else f'{c["id"]}={c["url"]}'


@app.get("/api/fj")
def api_fj_state():
    u = request_user()
    if not u:
        return jsonify(error="unauthorized"), 401
    conf = fj_conf()
    if not conf:
        return jsonify(required=False)
    if not rate_ok(f"fj:{u['id']}", 20, 60):
        return jsonify(error="تعداد تلاش زیاد بود، کمی صبر کن."), 429
    FJ_CACHE.pop(u["id"], None)
    miss = fj_missing(u["id"], conf)
    return jsonify(required=bool(miss), **(fj_public(conf, miss) if miss else {}))


@app.get("/api/admin/force-join")
@admin_only
def api_admin_fj_get(uid):
    d = db.settings.find_one({"_id": "force_join"}) or {}
    return jsonify(on=bool(d.get("on")), channels=" ".join(fj_str(c) for c in d.get("channels", [])), text=d.get("text") or FJ_DEFAULT_TEXT)


@app.post("/api/admin/force-join")
@admin_only
def api_admin_fj_set(uid):
    b = request.get_json(silent=True) or {}
    chans, err = fj_parse(b.get("channels"))
    if err:
        return jsonify(error=err), 400
    if b.get("on") and not chans:
        return jsonify(error="برای روشن کردن، حداقل یک کانال بنویس"), 400
    text = str(b.get("text") or "").strip()[:1500] or FJ_DEFAULT_TEXT
    warn = []
    for c in chans:
        r = tg(MOTHER_TOKEN, "getChatMember", chat_id=fj_chat(c), user_id=uid)
        if not r.get("ok"):
            warn.append(f"{c['id']}: ربات مادر باید ادمین این کانال باشه (یا آیدی درست نیست)؛ تا اون موقع کسی قفل نمی‌شه")
    db.settings.update_one({"_id": "force_join"}, {"$set": {"on": bool(b.get("on")) and bool(chans), "channels": chans, "text": text, "by": uid, "t": time.time()}}, upsert=True)
    FJ_CONF[0] = 0.0
    FJ_CACHE.clear()
    return jsonify(ok=True, warn=warn)


# ───────────────────────── کارت‌به‌کارت (تنظیمات از پنل ادمین، تأیید دستی با دکمه) ─────────────────────────
CARD_DEFAULT_TEXT = "مبلغ را دقیقاً به شماره کارت بالا واریز کن، بعد «ارسال رسید» را بزن و عکس رسید را در ربات بفرست.\nبعد از بررسی، توکن‌ها به حسابت اضافه می‌شود."
CARD_CONF = [0.0, None]


def card_conf():
    """تنظیمات فعال کارت‌به‌کارت یا None؛ ۱۵ ثانیه کش می‌شه"""
    t = time.time()
    if t - CARD_CONF[0] > 15:
        d = db.settings.find_one({"_id": "card"}) or {}
        CARD_CONF[:] = [t, d if d.get("on") and d.get("number") else None]
    return CARD_CONF[1]


def card_price(conf, pid):
    try:
        return max(0, int(((conf or {}).get("prices") or {}).get(pid) or 0))
    except (TypeError, ValueError):
        return 0


def card_public():
    """چیزی که به مینی‌اپ می‌ره: فقط روشن/خاموش و قیمت بسته‌ها (مشخصات کارت بعد از ثبت سفارش نشون داده می‌شه)"""
    c = card_conf()
    pr = {p["id"]: card_price(c, p["id"]) for p in PACKS if c and card_price(c, p["id"]) > 0}
    pr.update({"plan_" + p["id"]: card_price(c, "plan_" + p["id"]) for p in PLANS if p["id"] != "free" and c and card_price(c, "plan_" + p["id"]) > 0})
    return {"on": bool(pr), "prices": pr}


def luhn_ok(n):
    tot = 0
    for i, ch in enumerate(reversed(n)):
        d = int(ch) * (2 if i % 2 else 1)
        tot += d - 9 if d > 9 else d
    return tot % 10 == 0


def card_fmt(n):
    return " ".join(n[i:i + 4] for i in range(0, len(n), 4))


def card_say(uid, text, **kw):
    return tg_html(MOTHER_TOKEN, "sendMessage", chat_id=uid, text=text, **kw)


@app.post("/api/card/order")
@authed
def api_card_order(uid):
    conf = card_conf()
    body = request.get_json(silent=True) or {}
    plan_id = str(body.get("plan") or "")
    if plan_id:                                   # خرید اشتراک با کارت‌به‌کارت
        pl = PLAN_BY_ID.get(plan_id)
        if not pl or plan_id == "free":
            return jsonify(error="پلن نامعتبر"), 400
        if PLAN_RANK[plan_id] < PLAN_RANK[plan_of(db.users.find_one({"_id": uid}))]:
            return jsonify(error="اشتراک بالاتری هنوز فعاله؛ بعد از پایانش می‌تونی این پلن رو بگیری"), 400
        pid, p = "plan_" + plan_id, {"tokens": pl["tokens"]}
    else:
        pid = str(body.get("pack", ""))
        p = next((x for x in PACKS if x.get("id") == pid), None)
    toman = card_price(conf, pid) if (conf and p) else 0
    if not toman:
        return jsonify(error="پرداخت کارت‌به‌کارت برای این مورد فعال نیست"), 400
    since = time.time() - 86400
    o = db.card_orders.find_one({"uid": uid, "pack": pid, "status": "wait", "toman": toman, "t": {"$gt": since}})
    if not o:
        if not rate_ok(f"cardo:{uid}", 6, 3600):
            return jsonify(error="تعداد تلاش زیاد بود، کمی صبر کن."), 429
        if db.card_orders.count_documents({"uid": uid, "status": {"$in": ["wait", "sent"]}, "t": {"$gt": since}}) >= 3:
            return jsonify(error="چند سفارش باز داری؛ اول رسید اون‌ها رو بفرست یا صبر کن بررسی بشن."), 429
        no = db.counters.find_one_and_update({"_id": "card"}, {"$inc": {"n": 1}}, upsert=True,
                                             return_document=ReturnDocument.AFTER)["n"] + 1000
        o = {"_id": no, "uid": uid, "pack": pid, "tokens": int(p["tokens"]), "toman": toman, "status": "wait", "t": time.time()}
        if plan_id:
            o["plan"] = plan_id
        db.card_orders.insert_one(o)
    link = f"https://t.me/{core.MOTHER_USERNAME}?start=rcpt_{o['_id']}" if core.MOTHER_USERNAME else ""
    return jsonify(order=o["_id"], tokens=o["tokens"], toman=o["toman"], plan=PLAN_BY_ID[o["plan"]]["title"] if o.get("plan") else "", number=card_fmt(conf["number"]), raw=conf["number"],
                   holder=conf.get("holder") or "", bank=conf.get("bank") or "", text=conf.get("text") or CARD_DEFAULT_TEXT, link=link)


def card_ask_receipt(uid, no):
    o = db.card_orders.find_one({"_id": no, "uid": uid})
    if not o or o["status"] != "wait" or o["t"] < time.time() - 86400:
        return card_say(uid, "این سفارش دیگه باز نیست. از مینی‌اپ یک سفارش تازه ثبت کن.")
    db.settings.replace_one({"_id": f"rcpt:{uid}"}, {"_id": f"rcpt:{uid}", "no": no, "t": time.time()}, upsert=True)
    card_say(uid, f"عکس رسید واریز سفارش <b>#{no}</b> ({o['toman']:,} تومان) را همین‌جا بفرست.")


def card_receipt(msg):
    """عکس رسید کاربر → برای ادمین‌ها با دکمه‌ی تأیید/رد. اگه پیام رو مصرف کرد True"""
    uid = msg["from"]["id"]
    ph, doc = msg.get("photo"), msg.get("document")
    if ph:
        fid, kind = ph[-1]["file_id"], "photo"
    elif doc and str(doc.get("mime_type", "")).startswith("image/"):
        fid, kind = doc["file_id"], "document"
    else:
        return False
    since = time.time() - 86400
    ptr = db.settings.find_one({"_id": f"rcpt:{uid}"})
    o = None
    if ptr and time.time() - ptr.get("t", 0) < 86400:
        o = db.card_orders.find_one({"_id": ptr["no"], "uid": uid, "status": "wait", "t": {"$gt": since}})
    if not o:
        opens = list(db.card_orders.find({"uid": uid, "status": "wait", "t": {"$gt": since}}).limit(2))
        if len(opens) > 1:
            card_say(uid, "چند سفارش باز داری؛ از مینی‌اپ دکمه‌ی «ارسال رسید» همون سفارش رو بزن.")
            return True
        o = opens[0] if opens else None
    if not o:
        return False
    if not db.card_orders.update_one({"_id": o["_id"], "status": "wait"}, {"$set": {"status": "sent", "rcpt": fid, "ts": time.time()}}).modified_count:
        return True
    db.settings.delete_one({"_id": f"rcpt:{uid}"})
    f = msg["from"]
    who = _html.escape(f"{f.get('first_name') or ''} {('@' + f['username']) if f.get('username') else ''}".strip() or "بدون نام")
    cap = f"💳 رسید کارت‌به‌کارت #{o['_id']}\nکاربر: {who} ({uid})\nمورد: {('اشتراک ' + PLAN_BY_ID[o['plan']]['title']) if o.get('plan') else str(o['tokens']) + ' توکن'}\nمبلغ: {o['toman']:,} تومان"
    kb = {"inline_keyboard": [[{"text": "✅ تأیید و شارژ", "callback_data": f"cd:ok:{o['_id']}"},
                               {"text": "❌ رد", "callback_data": f"cd:no:{o['_id']}"}]]}
    sent = []
    for a in ADMIN_IDS:
        r = tg_html(MOTHER_TOKEN, "sendPhoto" if kind == "photo" else "sendDocument", chat_id=a, caption=cap, reply_markup=kb, **{kind: fid})
        if r.get("ok"):
            sent.append([a, r["result"]["message_id"]])
    if not sent:
        log.warning("card receipt not delivered to any admin (order %s)", o["_id"])
    db.card_orders.update_one({"_id": o["_id"]}, {"$set": {"adm": sent, "cap": cap}})
    card_say(uid, f"رسید سفارش <b>#{o['_id']}</b> گرفته شد. بعد از بررسی، نتیجه همین‌جا بهت اعلام می‌شه.")
    return True


def card_decide(no, ok, by):
    """تأیید/رد سفارش (فقط یک بار؛ از دکمه‌ی ربات یا پنل ادمین). اگه سفارش قبلاً رسیدگی شده بود None"""
    o = db.card_orders.find_one_and_update({"_id": no, "status": {"$in": ["wait", "sent"]}},
                                           {"$set": {"status": "ok" if ok else "no", "by": by, "t2": time.time()}},
                                           return_document=ReturnDocument.AFTER)
    if not o:
        return None
    if ok and o.get("plan") in PLAN_BY_ID:
        activate_plan(o["uid"], o["plan"])
        credit(o["uid"], o["tokens"], "card", key=f"card:{no}")
        card_say(o["uid"], f"✅ پرداخت سفارش <b>#{no}</b> تأیید شد؛ اشتراک <b>{PLAN_BY_ID[o['plan']]['title']}</b> فعال شد و <b>{o['tokens']}</b> توکن هدیه به حسابت اضافه شد.")
    elif ok:
        credit(o["uid"], o["tokens"], "card", key=f"card:{no}")
        card_say(o["uid"], f"✅ پرداخت سفارش <b>#{no}</b> تأیید شد و <b>{o['tokens']}</b> توکن به حسابت اضافه شد.")
    else:
        card_say(o["uid"], f"❌ رسید سفارش <b>#{no}</b> تأیید نشد. اگه واریز انجام شده، یک سفارش تازه ثبت کن و رسید واضح بفرست.")
    for a, mid in o.get("adm") or []:
        tg_html(MOTHER_TOKEN, "editMessageCaption", chat_id=a, message_id=mid, reply_markup={"inline_keyboard": []},
                caption=(o.get("cap") or "") + ("\n\n✅ تأیید شد" if ok else "\n\n❌ رد شد"))
    return o


def card_cb(cq):
    uid, data = cq["from"]["id"], str(cq.get("data") or "")

    def ans(t="", alert=False):
        tg(MOTHER_TOKEN, "answerCallbackQuery", callback_query_id=cq["id"], **({"text": t, "show_alert": alert} if t else {}))
    if uid not in ADMIN_IDS:
        return ans("فقط ادمین", True)
    m = re.fullmatch(r"cd:(ok|no):(\d{1,12})", data)
    if not m:
        return ans()
    ok = m.group(1) == "ok"
    o = card_decide(int(m.group(2)), ok, uid)
    ans(("تأیید شد و توکن اضافه شد" if ok else "رد شد") if o else "قبلاً رسیدگی شده", not o)


@app.get("/api/admin/card")
@admin_only
def api_admin_card_get(uid):
    d = db.settings.find_one({"_id": "card"}) or {}
    rows = list(db.card_orders.find().sort("_id", -1).limit(40))
    names = {u["_id"]: (u.get("tg_name") or u.get("name") or "") + ((" @" + u["tg_user"]) if u.get("tg_user") else "")
             for u in db.users.find({"_id": {"$in": list({r["uid"] for r in rows})}}, {"tg_name": 1, "name": 1, "tg_user": 1})}
    return jsonify(on=bool(d.get("on")), number=d.get("number", ""), holder=d.get("holder", ""), bank=d.get("bank", ""),
                   text=d.get("text") or CARD_DEFAULT_TEXT, prices=d.get("prices") or {},
                   orders=[{"id": r["_id"], "uid": r["uid"], "name": names.get(r["uid"], "").strip(), "tokens": r["tokens"],
                            "toman": r["toman"], "status": r["status"], "t": r["t"],
                            "plan": PLAN_BY_ID[r["plan"]]["title"] if r.get("plan") in PLAN_BY_ID else ""} for r in rows])


@app.post("/api/admin/card")
@admin_only
def api_admin_card_set(uid):
    b = request.get_json(silent=True) or {}
    number = re.sub(r"\D", "", str(b.get("number") or "").translate(_DIG))
    if number and not (len(number) == 16 and luhn_ok(number)):
        return jsonify(error="شماره کارت درست نیست (۱۶ رقم)"), 400
    prices = {}
    for p in list(PACKS) + [{"id": "plan_" + x["id"]} for x in PLANS if x["id"] != "free"]:
        try:
            v = int(re.sub(r"\D", "", str((b.get("prices") or {}).get(p["id"]) or "0").translate(_DIG)) or 0)
        except ValueError:
            v = 0
        if not 0 <= v <= 1_000_000_000:
            return jsonify(error="قیمت بسته معتبر نیست"), 400
        if v:
            prices[p["id"]] = v
    on = bool(b.get("on"))
    if on and not number:
        return jsonify(error="برای روشن کردن، شماره کارت را بنویس"), 400
    if on and not prices:
        return jsonify(error="قیمت (تومان) حداقل یک بسته را بنویس"), 400
    db.settings.update_one({"_id": "card"}, {"$set": {
        "on": on, "number": number, "holder": str(b.get("holder") or "").strip()[:60], "bank": str(b.get("bank") or "").strip()[:40],
        "text": str(b.get("text") or "").strip()[:1200] or CARD_DEFAULT_TEXT, "prices": prices, "by": uid, "t": time.time()}}, upsert=True)
    CARD_CONF[0] = 0.0
    return jsonify(ok=True)


@app.post("/api/admin/card-orders/<int:oid>")
@admin_only
def api_admin_card_decide(uid, oid):
    if not card_decide(oid, bool((request.get_json(silent=True) or {}).get("ok")), uid):
        return jsonify(error="این سفارش قبلاً رسیدگی شده یا پیدا نشد"), 409
    return jsonify(ok=True)


# ───────────────────────── یوزربات (اتصال اکانت شخصی تلگرام) ─────────────────────────
# کاربر با شماره‌ی خودش وارد می‌شه (کد تلگرام + رمز دومرحله‌ای)، سشن رمزنگاری‌شده ذخیره می‌شه و یک «دستیار» روی همون اکانت
# کار می‌کنه: پاسخ خودکار با کلمه‌ی کلیدی، پیام غیبت، پاسخ هوشمند (کسر از توکن) و دستورهای شخصی (.ping .time ...).
# هیچ کدی اجرا نمی‌شه؛ همه‌چی کانفیگ JSON اعتبارسنجی‌شده‌ست. ارسال همگانی/جوین/اد کردن عمداً وجود نداره.
# نیازمندی: pip install telethon  |  Environment: TG_API_ID TG_API_HASH (از my.telegram.org) MAX_USERBOTS USERBOTS(۰=خاموش)
try:
    from telethon import TelegramClient, events, errors as tl_err
    from telethon.sessions import StringSession
    UB_LIB = True
except Exception:   # telethon نصب نیست؛ بقیه‌ی برنامه عادی کار می‌کنه
    UB_LIB = False

UB_ON        = os.environ.get("USERBOTS", "1").strip() != "0"
TG_API_ID    = _int("TG_API_ID", 0)
TG_API_HASH  = os.environ.get("TG_API_HASH", "").strip()
MAX_USERBOTS = _int("MAX_USERBOTS", 2)           # سقف یوزربات هر کاربر
def ub_limit(uid):
    """سقف یوزربات این کاربر: مزیت اشتراکش (رایگان = ۰)، حداکثر تا MAX_USERBOTS"""
    return min(MAX_USERBOTS, perks_of(uid)["ub"])


UB_HOURLY    = _int("UB_HOURLY_REPLIES", 120)     # سقف پاسخ خودکار در ساعت برای هر یوزربات (جلوگیری از اسپم و ریپورت)
UB_MAX_RULES = 30
UB_DEV = dict(device_model="Azadi Userbot", system_version="Linux", app_version="1.0", lang_code="fa", system_lang_code="fa")

_ub_lp, _ub_lp_lock = None, threading.Lock()
_ub_pend = {}      # uid -> ورود نیمه‌کاره (کلاینت، شماره، هش کد)
_ub_live = {}      # ubid -> وضعیت زنده‌ی یوزربات روشن (کلاینت، کانفیگ، حافظه‌ی کوتاه)
_UB_ERR = {}
if UB_LIB:
    _UB_ERR = {
        tl_err.PhoneNumberInvalidError: "شماره‌ی تلفن درست نیست. با کد کشور بنویس، مثل 989121234567+",
        tl_err.PhoneNumberBannedError: "این شماره توسط تلگرام مسدود شده",
        tl_err.PhoneNumberFloodError: "برای این شماره درخواست زیادی ثبت شده، چند ساعت بعد دوباره امتحان کن",
        tl_err.PhoneCodeInvalidError: "کد اشتباهه. دوباره از پیام تلگرام کپی کن",
        tl_err.PhoneCodeExpiredError: "کد منقضی شده. دوباره شماره رو بفرست تا کد جدید بیاد",
        tl_err.PhoneCodeEmptyError: "کد را وارد کن",
        tl_err.PasswordHashInvalidError: "رمز دومرحله‌ای اشتباهه",
        tl_err.ApiIdInvalidError: "API ID / API Hash معتبر نیست",
    }


def ub_loop():
    """یک لوپ asyncio جدا توی یک ترد (برنامه‌ی اصلی Flask همگامه)"""
    global _ub_lp
    with _ub_lp_lock:
        if _ub_lp is None:
            lp = asyncio.new_event_loop()
            threading.Thread(target=lp.run_forever, daemon=True, name="userbots").start()
            _ub_lp = lp
        return _ub_lp


def ub_run(coro, timeout=60):
    f = asyncio.run_coroutine_threadsafe(coro, ub_loop())
    try:
        return f.result(timeout)
    except BaseException:
        f.cancel()          # اگه تلگرام جواب نداد، کار نیمه‌کاره توی لوپ جا نمی‌مونه
        raise


def ub_err(e):
    if isinstance(e, tl_err.FloodWaitError):
        s = int(getattr(e, "seconds", 60))
        return f"تلگرام موقتاً محدود کرده؛ {s // 60 + 1} دقیقه‌ی دیگه امتحان کن"
    for k, v in _UB_ERR.items():
        if isinstance(e, k):
            return v
    if isinstance(e, (asyncio.TimeoutError, TimeoutError, ConnectionError, OSError)):
        return "ارتباط با تلگرام برقرار نشد، دوباره امتحان کن"
    log.warning("userbot error: %r", e)
    return "خطا در ارتباط با تلگرام، دوباره امتحان کن"


def ub_creds(doc=None):
    if doc and doc.get("api_id") and doc.get("api_hash_enc"):
        return int(doc["api_id"]), dec(doc["api_hash_enc"])
    return TG_API_ID, TG_API_HASH


def ub_default_cfg():
    return {"who": "all", "away": {"on": False, "text": "سلام {name} 👋 الان در دسترس نیستم، به‌محض اینکه آنلاین شدم جواب می‌دم.", "gap_h": 6},
            "rules": [], "ai": {"on": False, "prompt": "", "daily": 20, "disclose": True}, "cmds": {"on": True}}


def ub_clean_cfg(c):
    d, c = ub_default_cfg(), (c if isinstance(c, dict) else {})
    out = {"who": c.get("who") if c.get("who") in ("all", "contacts", "others") else "all"}
    a = c.get("away") if isinstance(c.get("away"), dict) else {}
    out["away"] = {"on": bool(a.get("on")), "text": str(a.get("text") or d["away"]["text"])[:1000].strip() or d["away"]["text"],
                   "gap_h": max(1, min(72, int(a.get("gap_h") or 6)))}
    rules = []
    for r in (c.get("rules") if isinstance(c.get("rules"), list) else [])[:UB_MAX_RULES]:
        if not isinstance(r, dict):
            continue
        kw = r.get("kw")
        kw = [str(k).strip()[:60] for k in (kw if isinstance(kw, list) else re.split(r"[,،\n]", str(kw or ""))) if str(k).strip()][:8]
        text = str(r.get("text") or "").strip()[:1000]
        if kw and text:
            rules.append({"kw": kw, "mode": r.get("mode") if r.get("mode") in ("has", "exact", "start") else "has", "text": text, "on": r.get("on") is not False})
    out["rules"] = rules
    ai = c.get("ai") if isinstance(c.get("ai"), dict) else {}
    out["ai"] = {"on": bool(ai.get("on")), "prompt": str(ai.get("prompt") or "").strip()[:1500],
                 "daily": max(1, min(100, int(ai.get("daily") or 20))), "disclose": ai.get("disclose") is not False}
    out["cmds"] = {"on": (c.get("cmds") or {}).get("on") is not False if isinstance(c.get("cmds"), dict) else True}
    return out


def ub_mask(phone):
    p = re.sub(r"\D", "", phone or "")
    return f"+{p[:2]}•••••{p[-3:]}" if len(p) > 6 else "•••"


def ub_public(d):
    ubid = str(d["_id"])
    live = ubid in _ub_live
    st = "running" if live else ("revoked" if d.get("revoked") else "stopped")
    return {"id": ubid, "name": d.get("tg_name", ""), "username": d.get("tg_user", ""), "phone": d.get("phone", ""), "status": st,
            "active": bool(d.get("active")), "config": d.get("config") or ub_default_cfg(),
            "stats": {"in": int(d.get("n_in", 0)), "out": int(d.get("n_out", 0)), "ai": int(d.get("n_ai", 0))},
            "log": list(reversed(d.get("log") or []))[:20], "created": aware(d["created"]).isoformat() if d.get("created") else ""}


def get_ub(ubid, owner):
    try:
        return db.userbots.find_one({"_id": ObjectId(ubid), "owner": owner})
    except (InvalidId, TypeError):
        return None


def ub_log(ubid, kind, who="", inc="n_out"):
    try:
        db.userbots.update_one({"_id": ObjectId(ubid)}, {"$push": {"log": {"$each": [{"t": now().isoformat(), "k": kind, "w": str(who)[:40]}], "$slice": -30}},
                                                           "$inc": {inc: 1}, "$set": {"last": naive()}})
    except Exception:
        pass


def ub_fill(text, name=""):
    t = now() + timedelta(hours=3, minutes=30)
    jy, jm, jd = to_jalali(t.year, t.month, t.day)
    return (text.replace("{name}", name or "دوست من").replace("{time}", t.strftime("%H:%M")).replace("{date}", f"{jy}/{jm:02d}/{jd:02d}"))[:3800]


def ub_match(rule, text):
    t = text.lower()
    for k in rule["kw"]:
        k = k.lower()
        if (rule["mode"] == "exact" and t == k) or (rule["mode"] == "start" and t.startswith(k)) or (rule["mode"] == "has" and k in t):
            return True
    return False


def ub_ai_sync(owner, ubid, ai, name, hist):
    """پاسخ هوشمند (توی ترد جدا): هزینه از توکن صاحب اکانت، سقف روزانه برای هر چت. خروجی: متن یا None"""
    if not ai_precheck(owner):
        if db.aiuse.find_one_and_update({"_id": f"ub:{ubid}:warn:{tehran_day()}"}, {"$inc": {"n": 1}}, upsert=True,
                                         return_document=ReturnDocument.AFTER)["n"] == 1:
            tg(MOTHER_TOKEN, "sendMessage", chat_id=owner, text="توکن‌هات تموم شده و پاسخ هوشمند یوزربات فعلاً کار نمی‌کنه.",
               reply_markup={"inline_keyboard": [[{"text": "شارژ توکن", "web_app": {"url": APP_URL}}]]})
        return None
    sysm = ("You answer private Telegram messages on behalf of the account owner while they are away. Reply briefly (1-3 sentences), natural, polite, "
            "in the sender's language (default Persian). Never invent facts, prices, promises or appointments; if unsure say the owner will answer later. "
            "Never ask for or repeat passwords, login codes or card numbers. If the sender sincerely asks whether you are a human or an AI, say honestly that you are the owner's automatic assistant.\n"
            f"Owner instructions: {ai.get('prompt') or 'Be a friendly assistant.'}\nSender first name: {name or '-'}")
    reply, (pt, ct) = llm_post([{"role": "system", "content": sysm}, *hist], AI_NODE_MAX_TOKENS, temperature=0.6, timeout=60, model=AI_CHAT_MODEL)
    ai_postcharge(owner, ubid, pt, ct)
    reply = scrub_foreign(reply) if has_foreign(reply) and not has_foreign(hist[-1]["content"]) else reply
    reply = reply.strip()[:1500]
    return ("🤖 " + reply) if (reply and ai.get("disclose", True)) else (reply or None)


async def _ub_db(fn, *a):
    return await asyncio.get_running_loop().run_in_executor(None, fn, *a)


async def _ub_handle_in(ubid, st, ev):
    try:
        cfg, c = st["cfg"], st["c"]
        if not ev.is_private or ev.out or ev.message.action:
            return
        s = await ev.get_sender()
        if not s or getattr(s, "bot", False) or s.id in (st["me"].id, 777000):
            return
        who = cfg.get("who", "all")
        isc = bool(getattr(s, "contact", False))
        if (who == "contacts" and not isc) or (who == "others" and isc):
            return
        text = (ev.message.raw_text or "").strip()
        name = (getattr(s, "first_name", "") or "").strip()
        await _ub_db(lambda: db.userbots.update_one({"_id": ObjectId(ubid)}, {"$inc": {"n_in": 1}}))
        t0 = time.time()
        sent = st["sent"]
        while sent and t0 - sent[0] > 3600:
            sent.popleft()
        if len(sent) >= UB_HOURLY:
            return
        chat, kind, out = ev.chat_id, "", ""
        ic = await ev.get_input_chat()
        for i, r in enumerate(cfg.get("rules", [])):
            if r.get("on", True) and text and ub_match(r, text):
                if t0 - st["cool"].get((chat, i), 0) < 20:
                    return
                st["cool"][(chat, i)] = t0
                kind, out = f"قانون {i + 1}", ub_fill(r["text"], name)
                break
        if not out and cfg["ai"]["on"] and text:
            h = st["hist"].setdefault(chat, [])
            h.append({"role": "user", "content": text[:800]})
            del h[:-6]
            day = tehran_day()
            n = await _ub_db(lambda: db.aiuse.find_one_and_update({"_id": f"ub:{ubid}:{chat}:{day}"}, {"$inc": {"n": 1}}, upsert=True,
                                                                  return_document=ReturnDocument.AFTER)["n"])
            if n <= cfg["ai"]["daily"]:
                async with c.action(ic, "typing"):
                    try:
                        out = await _ub_db(ub_ai_sync, st["owner"], ubid, cfg["ai"], name, list(h))
                    except Exception:
                        log.exception("userbot ai failed")
                        out = ""
                if out:
                    h.append({"role": "assistant", "content": out[:800]})
                    del h[:-6]
                    kind = "پاسخ هوشمند"
        if not out and cfg["away"]["on"]:
            k, gap = f"{ubid}:{chat}", cfg["away"]["gap_h"] * 3600

            def _gate():
                d = db.ubaway.find_one({"_id": k})
                if d and age_sec(d["t"]) < gap:
                    return False
                db.ubaway.update_one({"_id": k}, {"$set": {"t": naive()}}, upsert=True)
                return True
            if await _ub_db(_gate):
                kind, out = "پیام غیبت", ub_fill(cfg["away"]["text"], name)
        if not out:
            return
        await asyncio.sleep(random.uniform(1.2, 3.2))     # شبیه آدم؛ و فاصله از محدودیت تلگرام
        await ev.respond(out)
        sent.append(time.time())
        await _ub_db(ub_log, ubid, kind, name, "n_ai" if kind == "پاسخ هوشمند" else "n_out")
    except Exception as e:
        log.warning("userbot in-handler: %r", e)


async def _ub_handle_out(ubid, st, ev):
    """دستورهای شخصی: صاحب اکانت پیام خودش رو با نقطه شروع می‌کنه؛ پیام ویرایش می‌شه و نتیجه همون‌جا میاد"""
    try:
        if not st["cfg"]["cmds"]["on"]:
            return
        t = (ev.message.raw_text or "").strip()
        if not t.startswith("."):
            return
        cmd = t.split()[0].lower()
        n = now() + timedelta(hours=3, minutes=30)
        jy, jm, jd = to_jalali(n.year, n.month, n.day)
        if cmd == ".ping":
            t0 = time.time()
            await ev.edit("🏓 pong")
            await ev.edit(f"🏓 pong · {int((time.time() - t0) * 1000)}ms")
        elif cmd == ".time":
            await ev.edit(f"🕒 {n.strftime('%H:%M:%S')}\n📅 {jy}/{jm:02d}/{jd:02d}")
        elif cmd == ".id":
            r = await ev.get_reply_message()
            await ev.edit(f"🆔 چت: `{ev.chat_id}`" + (f"\n👤 کاربر پیام ریپلای‌شده: `{r.sender_id}`" if r and r.sender_id else ""))
        elif cmd == ".help":
            await ev.edit("📋 دستورها:\n`.ping` سرعت\n`.time` ساعت و تاریخ\n`.id` شناسه‌ی چت (روی پیام ریپلای کن تا شناسه‌ی کاربر هم بیاد)")
        else:
            return
        ub_log(ubid, f"دستور {cmd}", "", "n_out")
    except Exception as e:
        log.warning("userbot out-handler: %r", e)


async def _ub_a_stop(ubid):
    st = _ub_live.pop(ubid, None)
    if st:
        try:
            await st["c"].disconnect()
        except Exception:
            pass


async def _ub_a_start(d):
    ubid = str(d["_id"])
    await _ub_a_stop(ubid)
    api = ub_creds(d)
    c = TelegramClient(StringSession(dec(d["session_enc"])), api[0], api[1], **UB_DEV)
    await c.connect()
    if not await c.is_user_authorized():
        await c.disconnect()
        raise PermissionError("revoked")
    st = {"c": c, "owner": d["owner"], "cfg": ub_clean_cfg(d.get("config")), "cool": {}, "sent": deque(), "hist": {}, "me": await c.get_me()}

    async def _in(ev): await _ub_handle_in(ubid, st, ev)
    async def _out(ev): await _ub_handle_out(ubid, st, ev)
    c.add_event_handler(_in, events.NewMessage(incoming=True))
    c.add_event_handler(_out, events.NewMessage(outgoing=True))
    _ub_live[ubid] = st


def ub_revoked(d):
    """سشن از تلگرام بسته شده (کاربر Terminate کرده یا اکانت حذف شده): خاموش و خبر به صاحب"""
    ubid = str(d["_id"])
    try:
        ub_run(_ub_a_stop(ubid), 20)
    except Exception:
        pass
    db.userbots.update_one({"_id": d["_id"]}, {"$set": {"active": False, "revoked": True}})
    tg(MOTHER_TOKEN, "sendMessage", chat_id=d["owner"], text=f"دسترسی یوزربات «{d.get('tg_name', '')}» از تلگرام قطع شده (سشن بسته شد). از تب یوزربات دوباره وصلش کن.")


def ub_start(d):
    """روشن کردن؛ خروجی: (True، None) یا (False، پیام)"""
    try:
        ub_run(_ub_a_start(d), 45)
        db.userbots.update_one({"_id": d["_id"]}, {"$set": {"active": True, "revoked": False}})
        return True, None
    except PermissionError:
        ub_revoked(d)
        return False, "دسترسی این اکانت از تلگرام قطع شده؛ دوباره وصلش کن"
    except Exception as e:
        if UB_LIB and isinstance(e, (tl_err.AuthKeyUnregisteredError, tl_err.UserDeactivatedError, tl_err.UserDeactivatedBanError,
                                     tl_err.SessionRevokedError, tl_err.SessionExpiredError)):
            ub_revoked(d)
            return False, "دسترسی این اکانت از تلگرام قطع شده؛ دوباره وصلش کن"
        return False, ub_err(e)


def ub_stop(d, keep_active=False):
    try:
        ub_run(_ub_a_stop(str(d["_id"])), 20)
    except Exception:
        pass
    if not keep_active:
        db.userbots.update_one({"_id": d["_id"]}, {"$set": {"active": False}})


async def _ub_a_drop(uid):
    p = _ub_pend.pop(uid, None)
    if p:
        try:
            await p["c"].disconnect()
        except Exception:
            pass


async def _ub_a_send_code(uid, phone, api):
    await _ub_a_drop(uid)
    c = TelegramClient(StringSession(), api[0], api[1], connection_retries=1, timeout=15, **UB_DEV)
    ok = False
    try:
        await asyncio.wait_for(c.connect(), 20)
        r = await asyncio.wait_for(c.send_code_request(phone), 20)
        _ub_pend[uid] = {"c": c, "phone": phone, "hash": r.phone_code_hash, "api": api, "own": api != (TG_API_ID, TG_API_HASH), "t": time.time()}
        ok = True
    finally:
        if not ok:
            await c.disconnect()


async def _ub_a_finish(uid):
    p = _ub_pend.pop(uid)
    c = p["c"]
    try:
        me = await c.get_me()
        sess = c.session.save()
    finally:
        await c.disconnect()
    return me, sess, p


async def _ub_a_code(uid, code):
    p = _ub_pend[uid]
    try:
        await p["c"].sign_in(p["phone"], code, phone_code_hash=p["hash"])
    except tl_err.SessionPasswordNeededError:
        return None
    return await _ub_a_finish(uid)


async def _ub_a_pw(uid, pw):
    await _ub_pend[uid]["c"].sign_in(password=pw)
    return await _ub_a_finish(uid)


def ub_ready():
    return UB_ON and UB_LIB


def ub_pending(uid):
    p = _ub_pend.get(uid)
    if p and time.time() - p["t"] > 600:
        try:
            ub_run(_ub_a_drop(uid), 15)
        except Exception:
            pass
        return None
    return p


def ub_attach(uid, res):
    """بعد از ورود موفق: ساخت (یا به‌روزرسانی) یوزربات و روشن کردن"""
    me, sess, p = res
    fields = {"owner": uid, "tg_id": me.id, "tg_name": " ".join(x for x in (me.first_name, me.last_name) if x)[:60], "tg_user": me.username or "",
              "phone": ub_mask(p["phone"]), "session_enc": enc(sess), "revoked": False, "updated": naive()}
    if p["own"]:
        fields.update(api_id=int(p["api"][0]), api_hash_enc=enc(p["api"][1]))
    old = db.userbots.find_one({"owner": uid, "tg_id": me.id})
    if old:
        db.userbots.update_one({"_id": old["_id"]}, {"$set": fields})
        d = db.userbots.find_one({"_id": old["_id"]})
    else:
        fields.update(config=ub_default_cfg(), active=True, created=naive(), n_in=0, n_out=0, n_ai=0, log=[])
        d = db.userbots.find_one({"_id": db.userbots.insert_one(fields).inserted_id})
    ok, err = ub_start(d)
    return db.userbots.find_one({"_id": d["_id"]}), err


def ub_loop_health():
    """هر ۵ دقیقه: سشن‌های بسته‌شده رو خاموش می‌کنه و ورودهای نیمه‌کاره‌ی قدیمی رو پاک می‌کنه"""
    while True:
        time.sleep(300)
        try:
            for uid in [u for u, p in list(_ub_pend.items()) if time.time() - p["t"] > 600]:
                ub_run(_ub_a_drop(uid), 15)
            for ubid, st in list(_ub_live.items()):
                try:
                    ok = ub_run(st["c"].is_user_authorized(), 30)
                except Exception as e:
                    ok = not isinstance(e, (tl_err.AuthKeyUnregisteredError, tl_err.UserDeactivatedError, tl_err.UserDeactivatedBanError,
                                            tl_err.SessionRevokedError, tl_err.SessionExpiredError))
                if not ok:
                    d = db.userbots.find_one({"_id": ObjectId(ubid)})
                    if d:
                        ub_revoked(d)
        except Exception:
            log.exception("userbot health")


def ub_boot():
    """بعد از ری‌استارت سرور همه‌ی یوزربات‌های روشن دوباره وصل می‌شن (فقط روی یک نمونه‌ی سرور اجرا کن)"""
    time.sleep(6)
    for d in list(db.userbots.find({"active": True})):
        try:
            ub_start(d)
        except Exception:
            log.exception("userbot boot")
        time.sleep(0.6)
    ub_loop_health()


def ub_guard(uid):
    if not ub_ready():
        return jsonify(error="بخش یوزربات روی این سرور فعال نیست"), 503
    if not rate_ok(f"ub:{uid}", 40, 600):
        return jsonify(error="تعداد درخواست زیاد بود، چند دقیقه بعد امتحان کن"), 429
    return None


@app.get("/api/userbots")
@authed
def api_ub_list(uid):
    items = [ub_public(d) for d in db.userbots.find({"owner": uid}).sort("created", 1)]
    return jsonify(items=items, max=ub_limit(uid), ok=ub_ready(), own_api=not (TG_API_ID and TG_API_HASH), pending=bool(ub_pending(uid)),
                   cost=AI_MSG_COST, per=ai_per(uid))


@app.post("/api/userbots/login/start")
@authed
def api_ub_login_start(uid):
    bad = ub_guard(uid)
    if bad:
        return bad
    if not ub_limit(uid):
        return jsonify(error="یوزربات با اشتراک Premium یا Pro فعال می‌شه", need_plan=True), 403
    if not rate_ok(f"ubl:{uid}", 5, 3600):
        return jsonify(error="درخواست کد زیاد بود، یک ساعت بعد دوباره امتحان کن"), 429
    j = request.get_json(silent=True) or {}
    phone = re.sub(r"[\s\-()]", "", str(j.get("phone", "")).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")))
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    if phone.startswith("09") and len(phone) == 11:
        phone = "+98" + phone[1:]
    if not phone.startswith("+"):
        phone = "+" + phone
    if not re.fullmatch(r"\+\d{8,15}", phone):
        return jsonify(error="شماره‌ی تلفن درست نیست. با کد کشور بنویس، مثل 989121234567+"), 400
    api = (TG_API_ID, TG_API_HASH)
    if not (TG_API_ID and TG_API_HASH):
        try:
            api = (int(j.get("api_id")), str(j.get("api_hash", "")).strip())
        except (TypeError, ValueError):
            api = (0, "")
        if api[0] <= 0 or not re.fullmatch(r"[0-9a-f]{32}", api[1]):
            return jsonify(error="API ID و API Hash را از my.telegram.org بگیر و وارد کن"), 400
    if db.userbots.count_documents({"owner": uid}) >= ub_limit(uid) and not db.userbots.find_one({"owner": uid, "phone": ub_mask(phone)}):
        return jsonify(error=f"با اشتراک فعلی‌ت حداکثر {ub_limit(uid)} یوزربات می‌تونی داشته باشی", need_plan=True), 403
    try:
        ub_run(_ub_a_send_code(uid, phone, api), 40)
    except Exception as e:
        return jsonify(error=ub_err(e)), 400
    return jsonify(ok=True, step="code")


@app.post("/api/userbots/login/code")
@authed
def api_ub_login_code(uid):
    bad = ub_guard(uid)
    if bad:
        return bad
    if not ub_pending(uid):
        return jsonify(error="زمان ورود تموم شده، از اول شروع کن", reset=True), 410
    code = re.sub(r"\D", "", str((request.get_json(silent=True) or {}).get("code", "")).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
    if not 4 <= len(code) <= 8:
        return jsonify(error="کد را درست وارد کن"), 400
    try:
        res = ub_run(_ub_a_code(uid, code), 40)
    except Exception as e:
        if UB_LIB and isinstance(e, (tl_err.PhoneCodeExpiredError,)):
            ub_run(_ub_a_drop(uid), 15)
        return jsonify(error=ub_err(e)), 400
    if res is None:
        return jsonify(ok=True, step="password")
    d, err = ub_attach(uid, res)
    return jsonify(ok=True, step="done", item=ub_public(d), warn=err)


@app.post("/api/userbots/login/password")
@authed
def api_ub_login_pw(uid):
    bad = ub_guard(uid)
    if bad:
        return bad
    if not ub_pending(uid):
        return jsonify(error="زمان ورود تموم شده، از اول شروع کن", reset=True), 410
    pw = str((request.get_json(silent=True) or {}).get("password", ""))
    if not pw or len(pw) > 256:
        return jsonify(error="رمز را وارد کن"), 400
    try:
        res = ub_run(_ub_a_pw(uid, pw), 40)
    except Exception as e:
        return jsonify(error=ub_err(e)), 400
    d, err = ub_attach(uid, res)
    return jsonify(ok=True, step="done", item=ub_public(d), warn=err)


@app.post("/api/userbots/login/cancel")
@authed
def api_ub_login_cancel(uid):
    if UB_LIB:
        try:
            ub_run(_ub_a_drop(uid), 15)
        except Exception:
            pass
    return jsonify(ok=True)


@app.get("/api/userbots/<ubid>")
@authed
def api_ub_get(uid, ubid):
    d = get_ub(ubid, uid)
    return jsonify(item=ub_public(d)) if d else (jsonify(error="یوزربات پیدا نشد"), 404)


@app.put("/api/userbots/<ubid>/config")
@authed
def api_ub_config(uid, ubid):
    d = get_ub(ubid, uid)
    if not d:
        return jsonify(error="یوزربات پیدا نشد"), 404
    cfg = ub_clean_cfg((request.get_json(silent=True) or {}).get("config"))
    db.userbots.update_one({"_id": d["_id"]}, {"$set": {"config": cfg, "updated": naive()}})
    st = _ub_live.get(ubid)
    if st:
        st["cfg"] = cfg
    return jsonify(item=ub_public(db.userbots.find_one({"_id": d["_id"]})))


@app.post("/api/userbots/<ubid>/start")
@authed
def api_ub_start(uid, ubid):
    bad = ub_guard(uid)
    if bad:
        return bad
    d = get_ub(ubid, uid)
    if not d:
        return jsonify(error="یوزربات پیدا نشد"), 404
    if not ub_limit(uid):
        return jsonify(error="اشتراکت تموم شده؛ برای روشن کردن یوزربات Premium یا Pro رو تمدید کن", need_plan=True), 403
    ok, err = ub_start(d)
    if not ok:
        return jsonify(error=err), 400
    return jsonify(item=ub_public(db.userbots.find_one({"_id": d["_id"]})))


@app.post("/api/userbots/<ubid>/stop")
@authed
def api_ub_stop(uid, ubid):
    d = get_ub(ubid, uid)
    if not d:
        return jsonify(error="یوزربات پیدا نشد"), 404
    ub_stop(d)
    return jsonify(item=ub_public(db.userbots.find_one({"_id": d["_id"]})))


@app.delete("/api/userbots/<ubid>")
@authed
def api_ub_delete(uid, ubid):
    d = get_ub(ubid, uid)
    if not d:
        return jsonify(error="یوزربات پیدا نشد"), 404

    async def _bye():                         # سشن رو از خود تلگرام هم می‌بندیم (Log out) تا هیچ دسترسی‌ای نمونه
        st = _ub_live.pop(ubid, None)
        c = st["c"] if st else None
        try:
            if c is None and UB_LIB:
                api = ub_creds(d)
                c = TelegramClient(StringSession(dec(d["session_enc"])), api[0], api[1], **UB_DEV)
                await c.connect()
            if c is not None:
                await c.log_out()
        except Exception:
            pass
        try:
            if c is not None:
                await c.disconnect()
        except Exception:
            pass
    if UB_LIB:
        try:
            ub_run(_bye(), 30)
        except Exception:
            pass
    db.userbots.delete_one({"_id": d["_id"]})
    db.ubaway.delete_many({"_id": {"$regex": f"^{ubid}:"}})
    db.aiuse.delete_many({"_id": {"$regex": f"^ub:{ubid}:"}})
    return jsonify(ok=True)


@app.post("/mother")
def mother_hook():
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != MOTHER_SECRET:
        return "forbidden", 403
    upd = request.get_json(silent=True) or {}
    try:
        pcq = upd.get("pre_checkout_query")
        if pcq:
            ok = (pack_from_payload(pcq.get("invoice_payload"), pcq["from"]["id"]) is not None
                  or plan_from_payload(pcq.get("invoice_payload"), pcq["from"]["id"]) is not None) and pcq.get("currency") == "XTR"
            tg(MOTHER_TOKEN, "answerPreCheckoutQuery", pre_checkout_query_id=pcq["id"], ok=ok,
               **({} if ok else {"error_message": "این بسته معتبر نیست"}))
            return "ok"
        cq = upd.get("callback_query")
        if cq:
            if fj_gate_cb(cq):
                return "ok"
            if str(cq.get("data") or "").startswith("cd:"):
                card_cb(cq)
                return "ok"
            mother_callback(cq)
            return "ok"
        msg = upd.get("message")
        if not msg or msg.get("chat", {}).get("type") != "private":
            return "ok"
        if not msg.get("successful_payment") and (msg.get("from") or {}).get("id") and fj_gate_msg(msg):
            return "ok"
        if (msg.get("from") or {}).get("id"):
            db.users.update_one({"_id": msg["from"]["id"], "mb_blocked": True}, {"$set": {"mb_blocked": False}})
        if msg.get("successful_payment"):
            mother_paid(msg)
        elif mother_media(msg):
            pass
        elif card_receipt(msg):
            pass
        elif mother_flow(msg):
            pass
        elif mother_emoji(msg):
            pass
        else:
            mother_command(msg)
    except Exception:
        log.exception("mother hook error")
    return "ok"
