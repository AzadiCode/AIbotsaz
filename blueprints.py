# -*- coding: utf-8 -*-
"""
blueprints.py — نقشه‌های آماده (هر نقشه = ربات + مینی‌اپ کامل، تست‌شده و آماده‌ی انتشار)

هر Blueprint: شناسه، عنوان، توضیح، فهرست امکانات، حداکثر ۳ سؤال شخصی‌سازی (انتخابی یا متن) و
تابع build که با پاسخ‌های کاربر کانفیگ ربات و کانفیگ مینی‌اپ را می‌سازد. هیچ JSON خامی به کاربر
نمایش داده نمی‌شود؛ خروجی build با sanitize (ربات) و sanitize_app (مینی‌اپ) اعتبارسنجی می‌شود.
هیچ نقشه‌ای اینجا نیست مگر این‌که کاملاً با موتور فعلی کار کند (قانون: «به‌زودی» ممنوع).
B1 (مرکز بازی گروهی) وقتی games.py به پروژه وصل شود اضافه می‌شود.
"""

# ابزارهای کوچک مشترک ساخت کانفیگ
_B = lambda t, **kw: {"text": t, **kw}                       # noqa: E731


def _node(text, btns=None, **kw):
    n = {"text": text, "buttons": btns or [], "ask": False}
    n.update(kw)
    return n


def _row(*btns):
    return list(btns)


def _q(k, fa, kind="text", opts=None, defv="", hint=""):
    return {"k": k, "fa": fa, "kind": kind, "opts": opts or [], "def": defv, "hint": hint}


def _pick(a, k):
    v = (a.get(k) or "").strip()
    return v[:200] if v else ""


# ═════════════════════ B1 — مرکز بازی گروهی ═════════════════════
B1_QUESTIONS = [
    _q("name", "اسم ربات بازی چی باشه؟", "text", defv="مرکز بازی"),
    _q("coin", "واحد پول بازی چی باشه؟", "choice",
       opts=[["سکه", "سکه"], ["سکه طلا", "سکه طلا"], ["الماس", "الماس"], ["امتیاز", "امتیاز"]]),
    _q("games", "کدوم بازی‌ها روشن باشن؟", "choice",
       opts=[["all", "همه‌ی ۹ بازی"], ["quiz", "فقط کوییز و ریاضی"], ["fun", "گردونه، حافظه و پازل"]]),
]
B1_FEATS = ["۹ بازی سمت سرور", "ضدتقلب کامل (شانس و زمان در سرور)", "سکه‌ی مجازی و فروشگاه", "چک‌این روزانه با استریک",
            "رتبه‌ی روزانه/هفتگی/فصلی", "دوئل XO در گروه", "کارت نتیجه در گروه", "مینی‌اپ کامل بازی‌ها"]


def b1_build(a):
    import games as _g
    name = _pick(a, "name") or "مرکز بازی"
    coin_ = _pick(a, "coin") or "سکه"
    sel = _pick(a, "games") or "all"
    gl = list(_g.GAME_IDS) if sel == "all" else (["quiz", "math"] if sel == "quiz" else ["wheel", "memory", "puzzle"])
    shop = [{"id": "boost1", "title": "شانس دوبرابر گردونه (یک روز)", "price": 60, "desc": "جایزه‌ی گردونه‌هات دوبرابر می‌شود"},
            {"id": "vip1", "title": "نشان ویژه کنار اسم", "price": 120, "desc": "نشان 🌟 کنار اسمت در رتبه‌ها"},
            {"id": "extra1", "title": "۵۰ سکه‌ی فوری", "price": 40, "desc": "۵۰ سکه مستقیم به کیفِت"}]
    cfg = {
        "name": name, "start": "start", "fallback": "start",
        "vars": {},
        "commands": {"play": "play", "top": "topn"},
        "nodes": {
            "start": _node(
                f"<b>🎮 {name}</b>\n۹ بازی سمت سرور با {coin_} مجازی؛ ضدتقلب کامل!\nبا /play بازی کن، با /top رتبه‌ی امروز رو ببین.",
                [_row(_B("🎮 بازی‌ها", goto="play")), _B("🏆 رتبه‌ها", goto="topn"), _B("📱 مینی‌اپ بازی", app="hub")]),
            "play": _node("یک بازی را انتخاب کن:",
                          [_row(_B("🧠 کوییز", goto="p_quiz"), _B("🎡 گردونه", goto="p_wheel")),
                           _row(_B("🃏 حافظه", goto="p_memory"), _B("🧩 پازل", goto="p_puzzle")),
                           _row(_B("بازگشت", goto="start"))]),
            "topn": _node("🏆 برترین‌های امروز:",
                          [_row(_B("🎮 بازی‌ها", goto="play"), _B("بازگشت", goto="start"))],
                          board={"var": "gtop", "top": 10, "label": "برترین‌های امروز"}),
            "p_quiz": _node("🧠 کوییز: ۴ سؤال؛ هر پاسخ درست سکه دارد!",
                            [_row(_B("شروع!", goto="g_quiz")), _B("بازگشت", goto="play")]),
            "p_wheel": _node("🎡 گردونه: بچرخان و ببر!",
                             [_row(_B("بچرخان!", goto="g_wheel")), _B("بازگشت", goto="play")]),
            "p_memory": _node("🃏 حافظه: جفت‌ها را پیدا کن.",
                              [_row(_B("شروع!", goto="g_memory")), _B("بازگشت", goto="play")]),
            "p_puzzle": _node("🧩 پازل: اعداد را مرتب کن.",
                              [_row(_B("شروع!", goto="g_puzzle")), _B("بازگشت", goto="play")]),
            "g_quiz": _node("آماده‌ای؟", [], do=[{"op": "game_play", "game": "quiz"}], title="کوییز"),
            "g_wheel": _node("می‌چرخانم…", [], do=[{"op": "game_play", "game": "wheel"}], title="گردونه"),
            "g_memory": _node("آماده‌ای؟", [], do=[{"op": "game_play", "game": "memory"}], title="حافظه"),
            "g_puzzle": _node("آماده‌ای؟", [], do=[{"op": "game_play", "game": "puzzle"}], title="پازل"),
        },
        "games": {"on": True, "coin": coin_, "list": gl, "shop": shop, "daily": 15},
        "group": {"triggers": [{"on": "command", "words": ["play"], "reply": "🎮 کارت بازی باز شد!",
                                "do": [{"op": "game_play", "game": "quiz"}]}]},
    }
    app = {
        "v": 1, "home": "hub",
        "theme": {"mode": "auto", "accent": "#E39A00", "radius": 16, "font": "vazir", "digits": "latin"},
        "nav": {"type": "tabs", "items": ["hub", "wallet", "tops", "shop"]},
        "screens": {
            "hub": {"title": "بازی‌ها", "icon": "star", "blocks": [
                {"id": "gm", "t": "games"}]},
            "wallet": {"title": "کیف", "icon": "gift", "blocks": [
                {"id": "wl", "t": "wallet"}]},
            "tops": {"title": "رتبه‌ها", "icon": "trophy", "blocks": [
                {"id": "gb", "t": "gamesboard", "game": "quiz"}]},
            "shop": {"title": "فروشگاه", "icon": "shop", "blocks": [
                {"id": "sc", "t": "shopcoins"}]},
        },
    }
    return {"bot": cfg, "app": app,
            "cards": ["ساخته شد: مرکز بازی با ۹ بازی سمت سرور (شانس و پاسخ همه در سرور = ضدتقلب)",
                      "اضافه شد: %s مجازی، فروشگاه سکه‌ای و چک‌این روزانه" % coin_,
                      "اضافه شد: رتبه‌ی روزانه، هفتگی و فصلی + کارت نتیجه در گروه",
                      "اضافه شد: مینی‌اپ کامل بازی‌ها (هاب، کیف، رتبه، فروشگاه)"],
            "steps": ["ربات را به گروه اضافه کن و /play را امتحان کن", "برای دوئل، دو نفر باید /play را در گروه بزنند"]}

# ═════════════════════ B2 — مدیر کامل گروه ═════════════════════
B2_QUESTIONS = [
    _q("name", "اسم رباتِ مدیریت چی باشه؟", "text", defv="نگهبان گروه"),
    _q("tone", "برخورد اول با متخلف چطور باشه؟", "choice",
       opts=[["warn", "اول اخطار، بعد سکوت، بعد اخراج"], ["mute", "مستقیم سکوت اجباری"], ["ban", "مستقیم اخراج"]]),
    _q("welcome", "پیام خوش‌آمد به عضو جدید (خالی = پیش‌فرض)", "text",
       defv="سلام {name} عزیز! 👋\nبه گروه خوش اومدی. قوانین رو رعایت کن تا همیشه اینجا خوش بگذره."),
]
B2_FEATS = ["کپچای ورود", "ضد اسپم و لینک و فلود", "اخطار تدریجی", "فیلتر کلمه", "خوش‌آمد و خداحافظی", "قوانین و دستور /rules", "داشبورد مینی‌اپ", "برترین‌های فعال‌ها"]


def b2_build(a):
    name = _pick(a, "name") or "نگهبان گروه"
    tone = _pick(a, "tone") or "warn"
    welcome = _pick(a, "welcome") or "سلام {name}! خوش اومدی 👋"
    act, then = ("warn", {"max": 3, "then": "mute", "mins": 60}) if tone == "warn" else \
                (("mute", {"max": 1, "then": "mute", "mins": 120}) if tone == "mute" else ("ban", {"max": 1, "then": "ban", "mins": 0}))
    cfg = {
        "name": name, "start": "start", "fallback": "start",
        "vars": {"points": "0"},
        "commands": {"rules": "rules", "help": "start"},
        "nodes": {
            "start": _node(
                f"<b>🛡 {name}</b>\nمن مدیر این گروه‌ام؛ اسپم و لینک و متخلف رو خودم رسیدگی می‌کنم.\nاینجا هم می‌تونی قوانین رو ببینی یا به من پیام بدی.",
                [_row(_B("📜 قوانین گروه", goto="rules"), _B("💬 پیام به مدیریت", goto="desk")),
                 _B("📱 داشبورد مدیریت", app="dash")]),
            "rules": _node(
                "<b>📜 قوانین گروه</b>\n۱) احترام حفظ بشه.\n۲) لینک و تبلیغ فقط با اجازه‌ی مدیر.\n۳) اسپم و فلود ممنوع.\n۴) بحث سیاسی و توهین ممنوع.",
                [_row(_B("🏠 منوی اصلی", goto="start"))], title="قوانین"),
            "desk": _node(
                "پیامت رو بنویس؛ مستقیم برای مدیریت می‌ره و همین‌جا جوابت رو می‌گیری.",
                [_row(_B("بازگشت", goto="start"))], ask=True, ticket=True, tag="مدیریت",
                done="ثبت شد ✅ به‌زودی جواب می‌دم."),
        },
        "mod": {"welcome": welcome, "welcome_del": 60, "goodbye": "", "rules": "۱) احترام ۲) بدون تبلیغ ۳) بدون اسپم",
                "captcha": {"on": True, "mins": 3}, "lock": ["link", "forward"], "words": [],
                "flood": {"n": 6, "secs": 8}, "action": act, "warns": then, "clean": ["join", "leave"], "report": True},
        "group": {"triggers": [{"on": "command", "words": ["top"], "board": {"var": "points", "top": 10, "label": "فعال‌ترین‌ها"}}]},
    }
    app = {
        "v": 1, "home": "dash",
        "theme": {"mode": "auto", "accent": "#2F7CF6", "radius": 16, "font": "vazir", "digits": "latin"},
        "nav": {"type": "tabs", "items": ["dash", "tops", "reports"]},
        "screens": {
            "dash": {"title": "داشبورد", "icon": "users", "blocks": [
                {"id": "bh", "t": "hero", "title": "🛡 داشبورد مدیریت", "text": "وضعیت گروه در یک نگاه"},
                {"id": "s1", "t": "stat", "var": "visits", "label": "بازدید تو"},
                {"id": "s2", "t": "stat", "var": "points", "label": "امتیاز تو"},
                {"id": "bn", "t": "banner", "style": "info", "text": "کپچا روشن است؛ عضو جدید تا زدن دکمه ساکت می‌ماند."}]},
            "tops": {"title": "برترین‌ها", "icon": "trophy", "blocks": [
                {"id": "bd", "t": "board", "var": "points", "top": 10, "label": "فعال‌ترین اعضا"}]},
            "reports": {"title": "گزارش", "icon": "form", "blocks": [
                {"id": "fm", "t": "form", "title": "گزارش تخلف یا درخواست",
                 "fields": [{"k": "name", "label": "اسم کاربر", "type": "text", "req": True},
                            {"k": "what", "label": "توضیح", "type": "text", "req": True}],
                 "save": {"table": "reports"}, "notify": True, "done": "گزارش ثبت شد؛ رسیدگی می‌شود."}]},
        },
    }
    return {"bot": cfg, "app": app,
            "cards": ["ساخته شد: ربات مدیریت گروه با کپچا، ضداسپم، اخطار تدریجی و قوانین",
                      "اضافه شد: پیام خوش‌آمد و خداحافظی خودکار",
                      "اضافه شد: داشبورد مینی‌اپ با آمار، برترین‌ها و فرم گزارش",
                      "اضافه شد: میز پیام به مدیریت (تیکت شماره‌دار)"],
            "steps": ["ربات را به گروه اضافه کن و ادمینش کن (حذف پیام، محدود کردن، سنجاق)", "پیام خوش‌آمد را از دکمه‌ی «مدیریت گروه و کانال» شخصی‌سازی کن"]}


# ═════════════════════ B3 — مدیر کانال ═════════════════════
B3_QUESTIONS = [
    _q("name", "اسم رباتِ کانال چی باشه؟", "text", defv="دستیار کانال"),
    _q("chan", "آیدی کانال (@id یا -100...) — فقط برای یادداشت خودت", "text", defv=""),
    _q("tone", "لحن پست‌ها چطور باشه؟", "choice",
       opts=[["g", "صمیمی و پرانرژی"], ["f", "رسمی و حرفه‌ای"], ["s", "کوتاه و تیز"]]),
]
B3_FEATS = ["صف پست با تأیید", "نویسنده‌ی هوشمند با لحن کانال", "یادآوری زمان انتشار", "تقویم پست در مینی‌اپ", "آمار بازدید", "دکمه‌ی ذخیره‌ی پیش‌نویس"]


def b3_build(a):
    name = _pick(a, "name") or "دستیار کانال"
    tone = _pick(a, "tone") or "f"
    tonefa = {"g": "صمیمی و پرانرژی", "f": "رسمی و حرفه‌ای", "s": "کوتاه و تیز"}.get(tone, "حرفه‌ای")
    ai_prompt = (f"تو نویسنده‌ی کانال «[نام کانال]» هستی؛ لحن: {tonefa}. هر پست را با یک خط تیتر بولد شروع کن، "
                 "متن را در ۲ تا ۴ خط بنویس و در پایان یک دعوت به اقدام بگذار. بدون هشتگ اضافه. فارسی روان.")
    cfg = {
        "name": name, "start": "start", "fallback": "start",
        "commands": {"new": "newpost", "queue": "queue"},
        "nodes": {
            "start": _node(
                f"<b>📣 {name}</b>\nپست‌های کانال رو اینجا آماده کن، زمان بذار و یادت نمی‌ره کی چی منتشر بشه.",
                [_row(_B("✍️ پست جدید", goto="newpost"), _B("🗂 صف انتشار", goto="queue")),
                 _B("📱 تقویم پست‌ها", app="cal")]),
            "newpost": _node(
                "پست رو همین‌جا بنویس یا دستیار هوشمند برات آماده‌ش کنه؛ بعد زمان انتشار بذار.",
                [_row(_B("🤖 نوشتن با هوش مصنوعی", goto="aiw"), _B("بازگشت", goto="start"))],
                fields=["متن پست را بنویس:"], save=["post"], types=["text"],
                done="پست در صف ثبت شد ✅"),
            "aiw": _node(
                "موضوع پست رو بگو تا دستیار با لحن کانال بنویسد؛ بعد می‌توانی ویرایشش کنی و در «پست جدید» ثبت کنی.",
                [_row(_B("بازگشت", goto="newpost"))],
                ai={"prompt": ai_prompt, "daily": 20, "memory": 2}, title="نویسنده"),
            "queue": _node(
                "پست‌های در صف انتشار:",
                [_row(_B("➕ پست جدید", goto="newpost"), _B("بازگشت", goto="start"))],
                list={"table": "posts", "scope": "all", "limit": 8, "line": "🗓 {date} — {post}", "empty": "صف خالی است؛ با «پست جدید» شروع کن."}),
        },
        "vars": {},
    }
    app = {
        "v": 1, "home": "cal",
        "theme": {"mode": "auto", "accent": "#E39A00", "radius": 16, "font": "vazir", "digits": "latin"},
        "nav": {"type": "tabs", "items": ["cal", "write"]},
        "screens": {
            "cal": {"title": "تقویم پست", "icon": "clock", "blocks": [
                {"id": "bh", "t": "hero", "title": "📣 تقویم کانال", "text": "پست‌های در صف و منتشرشده"},
                {"id": "ls", "t": "list", "table": "posts", "scope": "all", "limit": 10, "line": "🗓 {date} — {post}", "empty": "هنوز پستی در صف نیست."}]},
            "write": {"title": "نویسنده", "icon": "form", "blocks": [
                {"id": "ai", "t": "ai", "prompt": ai_prompt, "daily": 20, "memory": 2, "greeting": "موضوع پست رو بگو تا بنویسم ✍️"}]},
        },
    }
    return {"bot": cfg, "app": app,
            "cards": ["ساخته شد: ربات مدیریت کانال با صف پست و نویسنده‌ی هوشمند",
                      "اضافه شد: تقویم پست‌ها در مینی‌اپ",
                      f"لحن نویسنده: {tonefa}",
                      "یادآوری انتشار با اکشن یادآور ربات هم کار می‌کند"],
            "steps": ["ربات را ادمین کانال کن تا بتواند پست ببیند", "پست‌ها را از چت ربات ثبت کن و در زمان مقرر با فوروارد منتشر کن"]}


# ═════════════════════ B4 — ربات رشد و جذب عضو (فقط ورود واقعی) ═════════════════════
B4_QUESTIONS = [
    _q("name", "اسم ربات رشد چی باشه؟", "text", defv="تیم رشد"),
    _q("chan", "کانالی که عضویت اجباری بشه (آیدی @، خالی = بدون قفل)", "text", defv=""),
    _q("reward", "جایزه‌ی هر دعوت موفق (امتیاز)", "choice",
       opts=[["10", "۱۰ امتیاز"], ["25", "۲۵ امتیاز"], ["50", "۵۰ امتیاز"]]),
]
B4_FEATS = ["لینک دعوت اختصاصی هر کاربر", "شمارش دعوت موفق", "درخت معرفی و رتبه‌ی دعوت‌کننده‌ها", "پاداش و ماموریت", "قفل عضویت کانال", "داشبورد مینی‌اپ"]


def b4_build(a):
    name = _pick(a, "name") or "تیم رشد"
    chan = _pick(a, "chan")
    reward = _pick(a, "reward") or "10"
    join = {"channels": [chan], "text": "برای شروع، اول عضو کانال زیر بشو؛ بعد دکمه را بزن."} if chan.startswith("@") else None
    growth_chat = chan if (chan.startswith("@") or chan.startswith("-100")) else ""
    cfg = {
        "name": name, "start": "start", "fallback": "start",
        "vars": {"points": "0"},
        "commands": {"top": "top", "invite": "link", "help": "start"},
        "nodes": {
            "start": _node(
                f"<b>🚀 {name}</b>\nبا لینک اختصاصی‌ات دوستات رو دعوت کن؛ برای هر دعوتِ تأییدشده <b>{reward} امتیاز</b> می‌گیری.\nدعوت‌های فعال تو: <b>{{invites}}</b> · امتیازت: <b>{{points}}</b>",
                [_row(_B("🔗 لینک دعوت من", goto="link"), _B("🏆 برترین دعوت‌کننده‌ها", goto="top")),
                 _row(_B("📤 دعوت دوستان", share="من رو به این ربات دعوت کن؛ جایزه بگیر!"), _B("📱 داشبورد من", app="gr"))]),
            "link": _node(
                "🔗 لینک اختصاصی تو:\n<code>{invite_link}</code>\nدعوت‌های تأییدشده: <b>{invites}</b>\n(لینک رو برای دوستات بفرست؛ وقتی با همین لینک عضو بشن، امتیاز می‌گیری — و اگه ترک کنن، کسر می‌شه.)",
                [_row(_B("📤 ارسال لینک", share="بیا به این ربات!"), _B("بازگشت", goto="start"))], title="لینک من"),
            "top": _node("🏆 دعوت‌کننده‌های برتر:",
                         [_row(_B("بازگشت", goto="start"))],
                         board={"var": "points", "top": 10, "label": "دعوت‌کننده‌های برتر"}),
        },
        "on_ref": [{"op": "add", "var": "points", "value": reward}],
        "ref_text": f"دوستت تو رو به {name} دعوت کرده 🎁",
    }
    if growth_chat:
        cfg["growth"] = {"on": True, "chat": growth_chat, "var": "points", "reward": int(reward or 10), "per_day": 20, "clawback": True}
    if join:
        cfg["join"] = join
    app = {
        "v": 1, "home": "gr",
        "theme": {"mode": "auto", "accent": "#168A5B", "radius": 16, "font": "vazir", "digits": "latin"},
        "nav": {"type": "tabs", "items": ["gr", "tops"]},
        "screens": {
            "gr": {"title": "دعوت‌های من", "icon": "users", "blocks": [
                {"id": "bh", "t": "hero", "title": "🚀 رشدت رو ببین", "text": "لینک اختصاصی‌ات رو بفرست و جایزه بگیر"},
                {"id": "s1", "t": "stat", "var": "invites", "label": "دعوت تأییدشده"},
                {"id": "s2", "t": "stat", "var": "points", "label": "امتیاز"},
                {"id": "iv", "t": "invite", "text": "لینکت رو بفرست؛ برای هر عضو واقعی جایزه می‌گیری!", "btn": "📤 ارسال لینک دعوت"},
                {"id": "xp", "t": "xpbar", "var": "points", "label": "سطح", "per": 100}]},
            "tops": {"title": "برترین‌ها", "icon": "trophy", "blocks": [
                {"id": "bd", "t": "board", "var": "points", "top": 10, "label": "دعوت‌کننده‌های برتر"}]},
        },
    }
    cards = ["ساخته شد: ربات رشد با لینک دعوت اختصاصی هر کاربر (تلگرامی و واقعی)",
             "اضافه شد: پاداش " + reward + " امتیازی فقط برای عضویتِ تأییدشده با لینک",
             "اضافه شد: کسر امتیاز در صورت خروج عضو + سقف روزانه (ضد تقلب)",
             "اضافه شد: جدول برترین دعوت‌کننده‌ها و داشبورد مینی‌اپ با نوار سطح"]
    if join:
        cards.append("اضافه شد: قفل عضویت کانال " + chan)
    return {"bot": cfg, "app": app, "cards": cards,
            "steps": ["ربات را ادمین گروه/کانال رشد کن (با اجازه‌ی دعوت)", "دکمه‌ی «لینک دعوت من» را امتحان کن", "فقط ورود واقعیِ با لینک شمرده می‌شود؛ هیچ ابزار عضو فیک در این ربات نیست"],
            }


# ═════════════════════ B5 — عامل هوشمند ═════════════════════
B5_QUESTIONS = [
    _q("name", "اسم عامل هوشمند چی باشه؟", "text", defv="دستیار هوشمند"),
    _q("role", "عامل چه کاری برایت انجام بدهد؟", "choice",
       opts=[["sup", "پشتیبانی مشتری و پاسخ سؤال‌ها"], ["sale", "فروش و راهنمایی خرید"], ["chat", "هم‌صحبت با حافظه"],
             ["groupmate", "عضو هوشمند گروه (با منشن جواب می‌دهد)"], ["digest", "خلاصه‌ساز روزانه گروه"]]),
    _q("know", "دانش عامل: ساعات کاری، آدرس، خدمات، قیمت‌ها… (خط جدا با خط)", "text",
       defv="ساعات پاسخ‌گویی: هر روز ۹ تا ۲۱\nآدرس: [آدرس شما]\nتلفن: [شماره شما]"),
]
B5_FEATS = ["شخصیت و لحن", "دانش اختصاصی کسب‌وکار", "حافظه‌ی گفتگو", "ارجاع به انسان", "سقف هزینه‌ی روزانه", "گفتگوی کامل در مینی‌اپ"]


def b5_build(a):
    name = _pick(a, "name") or "دستیار هوشمند"
    role = _pick(a, "role") or "sup"
    know = _pick(a, "know") or "ساعات پاسخ‌گویی: هر روز ۹ تا ۲۱"
    rofa = {"sup": "پشتیبانِ مؤدب و صبور هستی؛ اول سؤال را دقیق بفهم، بعد کوتاه و دقیق جواب بده. اگر جواب را نمی‌دانی، کاربر را به پیام به مدیریت ارجاع بده.",
            "sale": "مشاور فروشِ گرم و پرانرژی هستی؛ نیاز کاربر را بپرس، گزینه‌ی مناسب را پیشنهاد بده و برای نهایی کردن خرید راهنمایی کن.",
            "chat": "هم‌صحبتِ دوستانه هستی؛ با حوصله حرف بزن، جزئیات قبلی گفتگو را به یاد داشته باش و سؤال‌های طبیعی بپرس."}.get(role, "دستیار مفید و مؤدب هستی.")
    prompt = (f"تو «{name}» هستی؛ {rofa}\n\nدانش تو (فقط بر اساس این جواب بده، از دانستن چیز ناموجود خودداری کن):\n{know}\n\n"
              "همیشه فارسی جواب بده. جواب‌ها کوتاه (حداکثر ۴ خط) و بدون اصطلاح فنی باشد. برای موضوع‌های حساس یا چیزهایی که بلد نیستی، بگو «پیام به مدیریت» بدهند.")
    if role == "groupmate":
        rofa = "عضوِ هوشمند گروه هستی؛ وقتی با @ منشن شدی، سؤال را دقیق و کوتاه جواب بده و اگر موضوع تکراری بود خلاصه بگو."
    if role == "digest":
        rofa = "خلاصه‌گوی گروهی هستی؛ گفتگو را در حداکثر ۶ خط فارسی خلاصه کن: نکته‌های مهم، تصمیم‌ها و کارهای باز. بدون ذکر نام کسی که نخواسته."
    handoff = role not in ("chat", "groupmate", "digest")
    cfg = {
        "name": name, "start": "start", "fallback": "start",
        "nodes": {
            "start": _node(
                f"<b>🤖 {name}</b>\nهر سؤالی داری بپرس؛ همین‌جا جواب می‌گیرم.",
                [_row(_B("💬 شروع گفتگو", goto="talk"))] + ([_row(_B("🧑‍💼 پیام به انسان", goto="desk"))] if handoff else [])),
            "talk": _node("سؤالت را بنویس 👇",
                          [_row(_B("بازگشت", goto="start"))],
                          ai={"prompt": prompt, "daily": 20, "memory": 6}, title="گفتگو"),
        },
    }
    if handoff:
        cfg["nodes"]["desk"] = _node("پیامت را بنویس؛ به‌صورت تیکت برای انسان می‌رود و جواب همین‌جا می‌آید.",
                                     [_row(_B("بازگشت", goto="start"))], ask=True, ticket=True, tag="ارجاع",
                                     done="ثبت شد ✅ همکارانم جوابت را می‌دهند.")
        cfg["nodes"]["start"]["buttons"].append(_row(_B("📱 نسخه‌ی مینی‌اپ", app="chat")))
    app = {
        "v": 1, "home": "chat",
        "theme": {"mode": "auto", "accent": "#6C5CE7", "radius": 18, "font": "vazir", "digits": "latin"},
        "nav": {"type": "tabs", "items": ["chat"]},
        "screens": {
            "chat": {"title": name, "icon": "chat", "blocks": [
                {"id": "ai", "t": "ai", "prompt": prompt, "daily": 20, "memory": 6, "greeting": f"سلام! من {name} هستم 🤖\nچطور می‌تونم کمکت کنم؟"}]},
        },
    }
    if role == "groupmate":
        cfg["group"] = {"triggers": [{"on": "mention", "ai": "talk"}]}
        cfg["nodes"]["start"]["text"] = f"<b>🤖 {name}</b>\nمن را به گروه اضافه و ادمین کن؛ هر وقت با @ منشنم کنید جواب می‌دهم."
        cfg["nodes"]["start"]["buttons"] = []
        cfg["digest"] = {"on": True, "chat": "@mygroup", "node": "talk", "hour": 21}
    if role == "digest":
        cfg["nodes"]["start"]["text"] = f"<b>🤖 {name}</b>\nهر شب ساعت ۲۱ خلاصه‌ی ۲۴ ساعت گروه را می‌نویسم. من را ادمین گروه کن."
        cfg["nodes"]["start"]["buttons"] = []
        cfg["digest"] = {"on": True, "chat": "@mygroup", "node": "talk", "hour": 21}
    cards = ["ساخته شد: عامل هوشمند با شخصیت و دانش اختصاصی",
             "اضافه شد: حافظه‌ی گفتگو (۶ پیام آخر) و سقف هزینه‌ی روزانه",
             "اضافه شد: گفتگوی کامل در مینی‌اپ"]
    if role == "groupmate":
        cards.append("اضافه شد: پاسخ هوشمند با منشن @ ربات در گروه + خلاصه‌ی شبانه")
    if role == "digest":
        cards.append("اضافه شد: خلاصه‌ی خودکار ۲۴ ساعت گروه، هر شب ساعت ۲۱")
    if handoff:
        cards.append("اضافه شد: ارجاع به انسان با تیکت شماره‌دار")
    return {"bot": cfg, "app": app, "cards": cards,
            "steps": ["دانش عامل را از «ویرایش بخش گفتگو» کامل‌تر کن", "یک بار در شبیه‌ساز تستش کن"]}


# ═════════════════════ B6 — کسب‌وکار (فروشگاه و رزرو) ═════════════════════
B6_QUESTIONS = [
    _q("name", "اسم کسب‌وکار چی باشه؟", "text", defv="فروشگاه من"),
    _q("mode", "سبک فروش چی باشه؟", "choice",
       opts=[["stars", "پرداخت آنی با ستاره‌ی تلگرام"], ["form", "ثبت سفارش و پیگیری دستی"], ["both", "هر دو (پرداخت آنی + سفارش)"]]),
    _q("sub", "اشتراک دوره (VIP) هم می‌خوای؟", "choice",
       opts=[["yes", "بله: خرید اشتراک ۳۰ روزه با ستاره + بخش مخصوص اعضا"], ["no", "نه، فقط فروشگاه"]]),
]
B6_FEATS = ["کاتالوگ با دسته", "صفحه‌ی هر محصول", "پرداخت با ستاره یا سفارش فرمی", "کد تخفیف واقعی با سقف مصرف",
            "سبد و سفارش‌های من", "اشتراک دوره (VIP) با بخش اعضا", "فروشگاه مینی‌اپ با سبد"]


def b6_build(a):
    name = _pick(a, "name") or "فروشگاه من"
    mode = _pick(a, "mode") or "form"
    sub = _pick(a, "sub") or "no"
    cats = [c.strip() for c in (_pick(a, "cat") or "").replace("،", ",").split(",") if c.strip()][:4] or ["پیشنهاد ویژه", "پرفروش‌ها"]
    price_note = "[قیمت]" if mode == "form" else "[قیمت به ستاره]"
    start_rows = [_row(_B("🗂 دسته‌ها", goto="cats"), _B("📦 سفارش‌های من", goto="orders")),
                  _row(_B("🎟 کد تخفیف", goto="code"), _B("📱 فروشگاه مینی‌اپ", app="shop")),
                  _row(_B("💬 پشتیبانی", goto="desk"))]
    if sub == "yes":
        start_rows.insert(2, _row(_B("⭐ اشتراک VIP", goto="vip")))
    nodes = {
        "start": _node(
            f"<b>🛍 {name}</b>\nبه فروشگاه ما خوش اومدی! از دسته‌ها شروع کن یا سفارش‌هات رو ببین.",
            start_rows),
        "cats": _node("دسته‌ی موردنظر را انتخاب کن:",
                      [_row(*[_B("▪️ " + c, goto="cat_" + str(i + 1)) for i, c in enumerate(cats[:2])])] +
                      ([_row(*[_B("▪️ " + c, goto="cat_" + str(i + 1)) for i, c in enumerate(cats[2:4])])] if len(cats) > 2 else []) +
                      [_row(_B("بازگشت", goto="start"))]),
        "orders": _node("سفارش‌های ثبت‌شده‌ی تو:",
                        [_row(_B("🛍 فروشگاه", goto="start"))],
                        list={"table": "orders", "limit": 6, "line": "📦 {item} — وضعیت: در حال پردازش", "empty": "هنوز سفارشی نداری."}),
        "code": _node("کد تخفیف داری؟ کد را بنویس و قیمت پایه را بده تا حساب کنم:",
                      [_row(_B("بازگشت", goto="start"))],
                      fields=["کد تخفیف چیست؟ (مثل WELCOME)", "قیمت پایه چند تومان است؟"],
                      save=["code", "price"], types=["text", "number"],
                      done="بررسی شد 🧾\nقیمت اولیه: {price} تومان\nقیمت نهایی: {code_off} تومان\nسود تو: {code_save} تومان\n{code_err|✅ کد اعمال شد!}"),
        "desk": _node("سؤال یا سفارش خاصی داری؟ بنویس؛ سریع جواب می‌دهیم.",
                      [_row(_B("بازگشت", goto="start"))], ask=True, ticket=True, tag="فروش",
                      done="ثبت شد ✅ به‌زودی رسیدگی می‌کنیم."),
    }
    nodes["code"]["do"] = [{"op": "disc", "var": "code", "price": "{price}"}]
    vars_ = {"cart": "0", "code": "", "price": ""}
    for i, c in enumerate(cats[:4]):
        pay_b = []
        if mode in ("stars", "both"):
            pay_b = [_B(f"خرید — {price_note}", pay={"stars": 1, "title": c, "text": "پرداخت انجام شد؛ ممنون! 🎉", "goto": "done"}, do=[{"op": "add", "var": "cart", "value": "1"}])]
        order_b = [] if mode == "stars" else [_B("ثبت سفارش", goto="order")]
        nodes["cat_" + str(i + 1)] = _node(
            f"<b>▪️ {c}</b>\nاینجا محصول‌های دسته‌ی «{c}» را می‌گذاری؛ هر محصول یک دکمه است.",
            [_row(_B("محصول نمونه ۱", goto="product")), _row(_B("محصول نمونه ۲", goto="product")),
             _row(_B("بازگشت", goto="cats"))])
    nodes["product"] = _node(
        f"<b>محصول</b>\n[توضیح کوتاه محصول]\nقیمت: {price_note}\n(این صفحه را برای هر محصول کپی کن و پر کن)",
        [_row(*(pay_b + order_b)), _row(_B("بازگشت", goto="cat_1"))])
    if mode != "stars":
        nodes["order"] = _node("برای ثبت سفارش، سه سؤال زیر را جواب بده:",
                               [_row(_B("بازگشت", goto="product"))],
                               fields=["چه می‌خواهی بخرید؟", "اسم و شماره‌ی تماس شما؟", "آدرس یا توضیح ارسال؟"],
                               save=["item", "contact", "addr"], types=["text", "phone", "text"],
                               done="سفارش ثبت شد ✅ برای هماهنگی تماس می‌گیریم.")
        nodes["order"]["do"] = [{"op": "db_add", "table": "orders", "data": {"item": "{item}", "contact": "{contact}", "addr": "{addr}"}}, {"op": "add", "var": "cart", "value": "1"}]
    nodes["done"] = _node("🎉 پرداخت شد! رسید در چت تلگرام برایت آمده.",
                          [_row(_B("🛍 ادامه‌ی خرید", goto="start"))])
    if sub == "yes":
        nodes["vip"] = _node(
            "<b>⭐ اشتراک VIP</b>\nبا اشتراک ۳۰ روزه، به همه‌ی محتوای ویژه و تخفیف‌های اعضا دسترسی داری.\nاگر اشتراک داری، دکمه‌ی «بخش VIP» برایت ظاهر می‌شود.",
            [_row(_B("⭐ خرید اشتراک ۳۰ روزه", pay={"stars": 50, "title": "اشتراک VIP", "text": "اشتراک VIP فعال شد! 🎉", "goto": "vipok"},
                       do=[{"op": "sub_add", "plan": "vip", "days": "30", "var": "sub"}])),
             _row(_B("🎯 بخش VIP", goto="viparea", when={"op": "sub", "plan": "vip"})),
             _row(_B("بازگشت", goto="start"))])
        nodes["vipok"] = _node("🎉 اشتراک VIP فعال شد! از الان ۳۰ روز به بخش ویژه دسترسی داری.",
                               [_row(_B("🎯 ورود به بخش VIP", goto="viparea")), _row(_B("🛍 فروشگاه", goto="start"))])
        nodes["viparea"] = _node(
            "<b>🎯 بخش ویژه‌ی اعضا</b>\nاینجا محتوای دوره را می‌گذاری: درس‌ها، فایل‌ها و تخفیف‌های مخصوص.\n(این بخش را برای هر جلسه گسترش بده)",
            [_row(_B("🛍 فروشگاه", goto="start"))])
    cfg = {"name": name, "start": "start", "fallback": "start", "vars": vars_,
           "commands": {"orders": "orders", "shop": "start", **({"vip": "vip"} if sub == "yes" else {})},
           "nodes": nodes,
           "desk": {}}
    items = [{"title": c, "text": "محصول نمونه — بعداً عوضش کن", "do": [{"op": "goto", "screen": "shop"}]} for c in cats[:4]]
    app = {
        "v": 1, "home": "shop",
        "theme": {"mode": "auto", "accent": "#CC3547", "radius": 18, "font": "vazir", "digits": "latin"},
        "nav": {"type": "tabs", "items": ["shop", "cart"]},
        "screens": {
            "shop": {"title": "فروشگاه", "icon": "shop", "blocks": [
                {"id": "bh", "t": "hero", "title": f"🛍 {name}", "text": "خرید آسان، ارسال سریع", "cta": {"text": "مشاهده‌ی محصولات", "do": [{"op": "goto", "screen": "cat"}]}},
                {"id": "cd", "t": "cards", "items": items}]},
            "cat": {"title": "محصولات", "icon": "bag", "blocks": [
                {"id": "ls", "t": "list", "table": "orders", "limit": 10, "line": "📦 {item}", "empty": "این دسته به‌زودی پر می‌شود."},
                {"id": "fm", "t": "form", "title": "سفارش سریع", "fields": [{"k": "item", "label": "چه می‌خواهی؟", "type": "text", "req": True}, {"k": "phone", "label": "شماره تماس", "type": "phone", "req": True}],
                 "save": {"table": "orders"}, "notify": True, "done": "سفارش ثبت شد ✅"}]},
            "cart": {"title": "سفارش‌های من", "icon": "form", "blocks": [
                {"id": "st", "t": "stat", "var": "cart", "label": "تعداد اقلام"},
                {"id": "ls", "t": "list", "table": "orders", "scope": "all", "limit": 10, "line": "📦 {item} — {contact}", "empty": "هنوز سفارشی ثبت نشده."}]},
        },
    }
    return {"bot": cfg, "app": app,
            "cards": ["ساخته شد: فروشگاه با دسته‌ها، صفحه‌ی محصول و پشتیبانی",
                      f"اضافه شد: {'پرداخت آنی با ستاره' if mode == 'stars' else 'ثبت سفارش فرمی' if mode == 'form' else 'پرداخت آنی + سفارش فرمی'}",
                      "اضافه شد: فروشگاه مینی‌اپ با سبد و فرم سفارش",
                      "اضافه شد: کد تخفیف واقعی (WELCOME با ۱۰٪ تخفیف و سقف مصرف) + میز سفارش",
                      "اضافه شد: اشتراک دوره (VIP) ۳۰ روزه با بخش مخصوص اعضا"] if sub == "yes" else
                     ["ساخته شد: فروشگاه با دسته‌ها، صفحه‌ی محصول و پشتیبانی",
                      f"اضافه شد: {'پرداخت آنی با ستاره' if mode == 'stars' else 'ثبت سفارش فرمی' if mode == 'form' else 'پرداخت آنی + سفارش فرمی'}",
                      "اضافه شد: فروشگاه مینی‌اپ با سبد و فرم سفارش",
                      "اضافه شد: کد تخفیف واقعی (WELCOME با ۱۰٪ تخفیف و سقف مصرف) + میز سفارش (تیکت)"],
            "steps": ["محصول‌ها را با «ویرایش دستی» پر کن (کپی بخش product برای هر محصول)",
                      "قیمت ستاره را روی هر دکمه‌ی پرداخت تنظیم کن",
                      "کدهای تخفیف را در جدول «کدهای تخفیف» بساز (نمونه: WELCOME، ۱۰٪، سقف ۱۰۰ بار)"]}


BLUEPRINTS = {
    "B1": {"title": "مرکز بازی گروهی", "icon": "star", "desc": "۹ بازی سمت سرور با سکه، رتبه، دوئل و مینی‌اپ کامل", "feats": B1_FEATS, "questions": B1_QUESTIONS, "build": b1_build},
    "B2": {"title": "مدیر کامل گروه", "icon": "users", "desc": "کپچا، ضداسپم، اخطار تدریجی و داشبورد مینی‌اپ برای گروهت", "feats": B2_FEATS, "questions": B2_QUESTIONS, "build": b2_build},
    "B3": {"title": "مدیر کامل کانال", "icon": "mega", "desc": "صف پست، نویسنده‌ی هوشمند با لحن کانال و تقویم انتشار", "feats": B3_FEATS, "questions": B3_QUESTIONS, "build": b3_build},
    "B4": {"title": "ربات رشد و جذب عضو", "icon": "chart", "desc": "لینک دعوت اختصاصی، شمارش ورود واقعی، جایزه و رتبه", "feats": B4_FEATS, "questions": B4_QUESTIONS, "build": b4_build},
    "B5": {"title": "عامل هوشمند", "icon": "bot", "desc": "پشتیبان یا فروشنده‌ی AI با شخصیت، دانش، حافظه و ارجاع به انسان", "feats": B5_FEATS, "questions": B5_QUESTIONS, "build": b5_build},
    "B6": {"title": "کسب‌وکار: فروشگاه و رزرو", "icon": "bag", "desc": "کاتالوگ، پرداخت با ستاره یا سفارش فرمی، سبد و فروشگاه مینی‌اپ", "feats": B6_FEATS, "questions": B6_QUESTIONS, "build": b6_build},
}

# کلیدواژه‌های تشخیص خودکار از توضیح کاربر (فارسی)
_BP_HINTS = {
    "B1": ["بازی", "کوییز", "گردونه", "دوئل", "قرعه", "مسابقه", "تورنمنت", "جایزه", "حدس کلمه"],
    "B2": ["مدیریت گروه", "ادمین گروه", "ضد اسپم", "ضداسپم", "کپچا", "اخطار", "گروه رو مدیریت", "حذف لینک", "فلود", "مدیر گروه"],
    "B3": ["کانال", "پست زمان", "زمان‌بندی پست", "تقویم پست", "نویسنده", "مدیر کانال", "پست خودکار"],
    "B4": ["جذب عضو", "ممبر", "دعوت", "رشد", "زیرمجموعه", "معرفی", "referral", "عضو گیری", "عضوگیری"],
    "B5": ["عامل", "دستیار هوشمند", "پشتیبان هوشمند", "چت بات هوشمند", "پاسخ هوشمند", "شخصیت", "منشی هوشمند", "پشتیبان هوش مصنوعی"],
    "B6": ["فروشگاه", "خرید", "سبد", "سفارش", "رزرو", "نوبت", "پرداخت", "محصول", "قیمت", "کسب‌وکار", "business"],
}


def detect_blueprint(idea):
    """از توضیح کاربر نزدیک‌ترین نقشه را پیدا می‌کند؛ هیچ‌کدام نخورد None"""
    t = (idea or "").lower()
    best, score = None, 0
    for bid, kws in _BP_HINTS.items():
        s = sum(1 for k in kws if k in t)
        if s > score:
            best, score = bid, s
    return best if score >= 1 else None


def blueprint_public(uid=None):
    """کارت‌های صفحه‌ی «چی می‌خوای بسازی؟»"""
    return [{"id": k, "title": v["title"], "icon": v["icon"], "desc": v["desc"],
             "feats": v["feats"], "questions": [{"k": q["k"], "fa": q["fa"], "kind": q["kind"],
                                                 "opts": q["opts"], "def": q["def"], "hint": q["hint"]} for q in v["questions"]]}
            for k, v in BLUEPRINTS.items()]


def build_blueprint(bid, answers):
    """(خروجی build، نام نقشه) یا خطا"""
    bp = BLUEPRINTS.get(str(bid or ""))
    if not bp:
        raise ValueError("نقشه پیدا نشد")
    out = bp["build"](answers or {})
    return out, bp["title"]
