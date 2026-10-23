# -*- coding: utf-8 -*-
"""
simrun.py — اجراکننده‌ی شبیه‌سازی خشک موتور (وابسته به core و engine؛ بالاتر از همه)

flowkit.simulate(cfg, events, state) اجرای خشک جریان را از رجیستری برمی‌دارد؛ این ماژول
اجراکننده‌ی واقعی را با register_runner ثبت می‌کند: همان handle_update موتور اجرا می‌شود ولی
هیچ تماسی با تلگرام/شبکه نمی‌رود — tg/tg_html/tg_media و requests با ضبط‌کننده جایگزین می‌شوند.

خروجی: {"ok": True, "msgs": [(نوع، متن، دکمه‌ها)], "trace": [(نود، یادداشت)], "vars": [(کلید، قبلی، تازه)], "errors": [...]}
هشدار: در سرویس واقعی، سندهای نوشته‌شده با bot_id ساختگی (sim-…) در چند کالکشن می‌مانند؛
پاک‌سازی دوره‌ای‌شان در مرحله ۴ (استودیو/شبیه‌ساز رابطی) اضافه می‌شود.
"""

import json
import threading

import flowkit
from core import log

_lock = threading.Lock()


class _SimReq:
    """جایگزین requests در شبیه‌سازی (اکشن fetch بدون شبکه)"""
    status_code, text = 200, ""

    def json(self):
        return {}

    def get(self, *a, **k):
        return self


def _sim_tg(token, method, **data):
    """جایگزین tg/tg_html: هیچ تماسی نمی‌رود؛ پیام‌ها در trace ضبط می‌شوند"""
    tr = getattr(flowkit, "_SIMTRACE", None)
    if method in ("answerCallbackQuery", "answerPreCheckoutQuery", "sendChatAction", "deleteMessage", "setMyCommands"):
        return {"ok": True}
    if method == "sendDice":
        return {"ok": True, "result": {"dice": {"value": 3, "emoji": data.get("emoji", "🎲")}}}
    if method == "getChatMember":
        return {"ok": True, "result": {"status": "member"}}
    if method in ("sendPoll", "sendMediaGroup"):
        if tr:
            tr.msg("poll" if method == "sendPoll" else "album", str(data.get("question") or ""),
                   [[o] for o in (data.get("options") or [])] if method == "sendPoll" else [])
        return {"ok": True, "result": {"message_id": 1}}
    text = str(data.get("text") or data.get("caption") or "")
    kb = data.get("reply_markup") or {}
    buttons = [[{"t": str(b.get("text", "")), "d": str(b.get("callback_data", ""))} for b in row]
               for row in kb.get("inline_keyboard", [])] \
        if isinstance(kb, dict) else []
    if tr:
        tr.msg("text", text, buttons)
    return {"ok": True, "result": {"message_id": 1, "chat": {"id": data.get("chat_id")}}}


def _sim_tg_media(token, bot_id, chat_id, mid, caption="", markup=None, parse=None, protect=False):
    """جایگزین tg_media: رسانه‌ی کتابخانه به‌صورت ضبط‌شده «ارسال» می‌شود"""
    tr = getattr(flowkit, "_SIMTRACE", None)
    if tr:
        kb = markup.get("inline_keyboard", []) if isinstance(markup, dict) else []
        tr.msg("media", str(caption or ""), [[str(b.get("text", "")) for b in row] for row in kb])
    return True


def _sim_ai_chat(bot_id, token, chat_id, user, node_id, text):
    """گفتگوی هوشمند در شبیه‌سازی: پاسخ ساختگی (بدون هزینه و شبکه)"""
    tr = getattr(flowkit, "_SIMTRACE", None)
    if tr:
        tr.msg("text", "پاسخ نمونه‌ی هوش مصنوعی (در شبیه‌سازی واقعی پاسخ می‌آید).", [])
    return "mock"


def simulate_runner(cfg, events, state=None):
    """اجرای خشک: برای هر رویداد همان handle_update موتور اجرا می‌شود (بدون تلگرام)"""
    if not isinstance(cfg, dict) or not isinstance(cfg.get("nodes"), dict) or cfg.get("start") not in cfg.get("nodes", {}):
        out = flowkit.SimTrace()
        out.error("simulate", "کانفیگ معتبر نیست (بخش شروع وجود ندارد)")
        return {"ok": False, "error": "کانفیگ معتبر نیست", **out.out()}
    try:
        import crm
        crm.purge_sim(6)          # سندهای شبیه‌سازی‌های قدیمی پاک می‌شوند (بهترین‌تلاش)
    except Exception:
        pass
    events = [e for e in (events if isinstance(events, list) else []) if e][:30]
    tr = flowkit.SimTrace()
    bid = f"sim-{abs(hash(json.dumps(cfg, sort_keys=True, default=str))) % 10 ** 12}"
    bot = {"_id": bid, "config": cfg, "owner": 0, "username": "simbot", "active": True, "token_enc": ""}
    with _lock:
        engine_mod = _engine()
        old = (engine_mod.tg, engine_mod.tg_html, engine_mod.tg_media, engine_mod.requests, engine_mod.ai_chat)
        engine_mod.tg = _sim_tg
        engine_mod.tg_html = _sim_tg
        engine_mod.tg_media = _sim_tg_media
        engine_mod.requests = _SimReq()
        engine_mod.ai_chat = _sim_ai_chat
        flowkit._SIMTRACE = tr
        engine_mod._SIM.on = True            # هوک‌های ردپا در Env.set و send_node روشن می‌شوند
        engine_mod._SIM.tr = tr
        try:
            for i, ev in enumerate(events):
                ev = ev if isinstance(ev, dict) else {"text": str(ev)}
                try:
                    if ev.get("goto"):                       # پرش مستقیم (فقط شبیه‌سازی)
                        env = engine_mod.Env(bot, "", 111, {"id": 111, "first_name": "کاربر"})
                        engine_mod.send_node(env, str(ev["goto"]))
                        env.save()
                        continue
                    if ev.get("data") is None and ev.get("text"):
                        tr.msg("user", str(ev.get("text"))[:500], [])     # حباب کاربر در روایت
                    upd = {"message": {"message_id": 100 + i, "from": {"id": 111, "first_name": "کاربر"},
                                       "chat": {"id": 111, "type": "private"}, "text": str(ev.get("text") or "")}}
                    if ev.get("data") is not None:
                        upd = {"callback_query": {"id": "c", "data": str(ev["data"])[:64],
                                                  "from": {"id": 111, "first_name": "کاربر"},
                                                  "message": {"message_id": 100 + i, "chat": {"id": 111}}}}
                    engine_mod.handle_update(bot, "", upd)
                except Exception as e:
                    log.exception("sim event failed")
                    tr.error(f"event {i}", e)
        finally:
            engine_mod.tg, engine_mod.tg_html, engine_mod.tg_media, engine_mod.requests, engine_mod.ai_chat = old
            engine_mod._SIM.on = False
            flowkit._SIMTRACE = None
    return {"ok": True, **tr.out()}


def _engine():
    import engine
    return engine


flowkit.register_runner("engine", simulate_runner)
