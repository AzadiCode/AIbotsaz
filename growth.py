# -*- coding: utf-8 -*-
"""
growth.py — ربات رشد (B4): فقط ورود واقعی

• هر کاربر با دکمه/متغیر {invite_link} لینک دعوت اختصاصی خودش را می‌گیرد (createChatInviteLink با نام ref<uid>؛ یک لینک برای هر کاربر، قابل استفاده‌ی مکرر)
• عضویت واقعی با رویداد chat_member تأیید می‌شود: فقط وقتی کاربر با «لینک دعوتِ» کسی وارد شده باشد پاداش می‌گیرد (هیچ ابزار عضو فیک وجود ندارد)
• خروج عضو → کسر پاداش از دعوت‌کننده (یک بار)؛ ورود دوباره → پاداش دوباره نمی‌گیرد (ضد churn)
• سقف پاداش روزانه برای هر دعوت‌کننده + اشتراک درخواست عضویت (chat_join_request → تأیید خودکار)
وابستگی: core ← growth (engine با import تنبل استفاده می‌کند)
"""
import re, time

from core import db, log, now, tehran_day, tg, tg_html

_CHAT_CACHE = {}


def gconf(cfg):
    g = cfg.get("growth")
    return g if isinstance(g, dict) and g.get("on") else None


def _chat_id(token, ref):
    """@نام یا -100... به شناسه‌ی عددی؛ ۱۵ دقیقه کش"""
    key = str(ref)
    t = time.time()
    if key in _CHAT_CACHE and t - _CHAT_CACHE[key][0] < 900:
        return _CHAT_CACHE[key][1]
    r = tg(token, "getChat", chat_id=ref)
    cid = (r.get("result") or {}).get("id") if r.get("ok") else None
    _CHAT_CACHE[key] = (t, cid)
    if cid is None:
        log.warning("growth chat resolve failed: %s", ref)
    return cid


def stats(bot_id, uid):
    """(لینک، تعداد دعوت تأییدشده‌ی فعال)"""
    d = db.invlink.find_one({"bot": bot_id, "u": uid}) or {}
    joins = db.growth.count_documents({"bot": bot_id, "by": uid, "clawed": {"$ne": True}})
    return d.get("link") or "", joins


def link_for(bot, token, uid):
    """لینک دعوت اختصاصی کاربر (یک بار ساخته و ذخیره می‌شود)"""
    bot_id = str(bot["_id"])
    d = db.invlink.find_one({"bot": bot_id, "u": uid})
    if d and d.get("link"):
        return d["link"]
    g = gconf(bot.get("config") or {})
    if not g:
        return ""
    r = tg(token, "createChatInviteLink", chat_id=g["chat"], name=f"ref{uid}"[:32])
    link = (r.get("result") or {}).get("invite_link") if r.get("ok") else None
    if not link:
        log.warning("growth invite link failed: %s", r.get("description"))
        return ""
    db.invlink.update_one({"bot": bot_id, "u": uid}, {"$set": {"link": link, "t": now()}}, upsert=True)
    return link


def _add_points(bot_id, uid, var, diff):
    """افزایش/کاهش متغیر عددی دعوت‌کننده (کف صفر)"""
    d = db.uvars.find_one({"_id": f"{bot_id}:{uid}"}) or {}
    v = d.get("v") or {}
    try:
        cur = int(float(str(v.get(var, "0"))))
    except (TypeError, ValueError):
        cur = 0
    new = max(0, cur + diff)
    db.uvars.update_one({"_id": f"{bot_id}:{uid}"}, {"$set": {f"v.{var}": str(new), "t": now(), "bot": bot_id}}, upsert=True)
    return new


def _reward(bot, token, cfg, inviter, invited, name):
    bot_id = str(bot["_id"])
    g = gconf(cfg)
    var = g.get("var") or "points"
    reward = int(g.get("reward", 10))
    cap = int(g.get("per_day", 20))
    key = f"{bot_id}:{invited}"
    if db.growth.find_one({"_id": key}):
        return                                   # قبلاً پاداش گرفته؛ ورود دوباره پاداش ندارد (ضد churn)
    if cap and db.growth.count_documents({"bot": bot_id, "by": inviter, "day": tehran_day()}) >= cap:
        return
    try:
        db.growth.insert_one({"_id": key, "bot": bot_id, "by": inviter, "day": tehran_day(), "clawed": False, "t": now()})
    except Exception:
        return                                    # race: همین الان ثبت شده
    if reward:
        _add_points(bot_id, inviter, var, reward)
        if g.get("wallet"):
            try:
                import games as _gm
                if _gm.gcfg(cfg):
                    _gm._coins(bot_id, inviter, reward)
            except Exception:
                log.exception("growth wallet reward failed")
    try:
        tg_html(token, "sendMessage", chat_id=inviter,
                text=f"🎉 <b>{name or 'یک کاربر'}</b> با لینک تو عضو شد!\n+{reward} {var} به حسابت اضافه شد.")
    except Exception:
        pass


def _clawback(bot, token, cfg, invited):
    bot_id = str(bot["_id"])
    g = gconf(cfg)
    d = db.growth.find_one({"_id": f"{bot_id}:{invited}"})
    if not d or d.get("clawed") or not g.get("clawback", True):
        return
    var = g.get("var") or "points"
    reward = int(g.get("reward", 10))
    _add_points(bot_id, d["by"], var, -reward)
    if g.get("wallet"):
        try:
            import games as _gm
            if _gm.gcfg(cfg):
                _gm._coins(bot_id, d["by"], -reward)
        except Exception:
            log.exception("growth wallet clawback failed")
    db.growth.update_one({"_id": d["_id"]}, {"$set": {"clawed": True}})
    try:
        tg_html(token, "sendMessage", chat_id=d["by"],
                text=f"← کاربری که با لینک تو عضو شده بود گروه را ترک کرد؛ {reward} {var} کسر شد.")
    except Exception:
        pass


def on_member(bot, token, cfg, cm):
    """رویداد chat_member: عضویت با لینک دعوت = پاداش؛ خروج = کسر. خروجی True اگر مصرف شد"""
    g = gconf(cfg)
    if not g:
        return False
    u = cm.get("new_chat_member") or {}
    uid = (u.get("user") or {}).get("id")
    if not uid or (u.get("user") or {}).get("is_bot"):
        return False
    chat_ok = _chat_ok(bot, token, g, cm.get("chat"))
    if not chat_ok:
        return False
    status = u.get("status")
    if status == "kicked":
        _clawback(bot, token, cfg, uid)
        return True
    if status in ("member", "administrator", "restricted") and not (u.get("user") or {}).get("is_bot"):
        old = ((cm.get("old_chat_member") or {}).get("status") or "")
        if old in ("left", "kicked"):
            link = ((cm.get("invite_link") or {}).get("invite_link") or "")
            if not link:
                return True                       # ورود بدون لینک دعوت: بدون پاداش (فقط ورود واقعیِ دعوتی)
            d = db.invlink.find_one({"bot": str(bot["_id"]), "link": link})
            if not d or d.get("u") == uid:
                return True
            _reward(bot, token, cfg, d["u"], uid, (u.get("user") or {}).get("first_name"))
        return True
    if status == "left":
        _clawback(bot, token, cfg, uid)
        return True
    return True


def on_request(bot, token, cfg, req):
    """درخواست عضویت (کانال/گروه با تأیید): خودکار تأیید و پاداش اگر با لینک دعوت باشد"""
    g = gconf(cfg)
    if not g:
        return False
    uid = (req.get("from") or {}).get("id")
    if not uid or (req.get("from") or {}).get("is_bot"):
        return False
    if not _chat_ok(bot, token, g, req.get("chat")):
        return False
    link = ((req.get("invite_link") or {}).get("invite_link") or "")
    tg(token, "approveChatJoinRequest", chat_id=req["chat"]["id"], user_id=uid)
    if link:
        d = db.invlink.find_one({"bot": str(bot["_id"]), "link": link})
        if d and d.get("u") != uid:
            _reward(bot, token, cfg, d["u"], uid, (req.get("from") or {}).get("first_name"))
    return True


def _chat_ok(bot, token, g, chat):
    if not chat:
        return False
    want = _chat_id(token, g.get("chat"))
    return bool(want) and int(chat.get("id") or 0) == int(want)


def selftest():
    """تست منطق (بدون شبکه): کف صفر امتیاز و کلید ضدتکرار"""
    assert gconf({}) is None
    assert gconf({"growth": {"on": 1}})["on"]
    print("growth selftest ok")
