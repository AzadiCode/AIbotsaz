# -*- coding: utf-8 -*-
"""
templates.py — قالب‌های آماده‌ی ربات (۵ قالب اصلی دوزبانه) و هلپرهای ساخت آن‌ها.

از ai.py جدا شد (مرحله ۴) تا ai.py زیر سقف اندازه بیاید؛ خروجی یکسان است و
ai.py برای سازگاری مسیرهای قدیمی (mother و …) همان TEMPLATES را re-export می‌کند.
"""

# ───────────────────────── قالب‌های آماده (۵ قالب اصلی، دوزبانه) ─────────────────────────
def _b(text, goto=None, **kw):
    d = {"text": text}
    if goto:
        d["goto"] = goto
    d.update(kw)
    return d


def _L(fa, en):
    """متن دوزبانه: (فارسی، انگلیسی)؛ _bilingual برای هر زبان یک شاخه‌ی جدا می‌سازه"""
    return (fa, en)


SHARED_IDS = ("start", "lang")


def _tr(x, i, pre):
    if isinstance(x, tuple):
        return x[i]
    if isinstance(x, list):
        return [_tr(v, i, pre) for v in x]
    if isinstance(x, dict):
        o = {}
        for k, v in x.items():
            if k in ("goto", "next") and isinstance(v, str) and v not in SHARED_IDS:
                v = pre + v                       # مقصد دکمه/مسیر/یادآور در شاخه‌ی همین زبان
            o[k] = _tr(v, i, pre)
        return o
    return x


_UI = lambda v: {"var": "ui", "op": "==", "value": v}
_PICK_TEXT = "<b>🌐 زبان خودت رو انتخاب کن</b>\n<b>Please choose your language</b>"


def _picker():
    return [[_b("🇮🇷 فارسی", "home", do=[{"op": "set", "var": "ui", "value": "fa"}])],
            [_b("🇬🇧 English", "en_home", do=[{"op": "set", "var": "ui", "value": "en"}])]]


def _bilingual(name, nodes, vars=None, **extra):
    out = {}
    for nid, n in nodes.items():
        out[nid] = _tr(n, 0, "")
        out["en_" + nid] = _tr(n, 1, "en_")
    out["start"] = {"title": "Language · زبان", "text": _PICK_TEXT, "buttons": _picker(),
                    "route": [{"when": _UI("fa"), "goto": "home"}, {"when": _UI("en"), "goto": "en_home"}]}
    out["lang"] = {"title": "Language · زبان", "text": _PICK_TEXT, "buttons": _picker(), "do": [{"op": "clear", "var": "ui"}]}
    cfg = {"name": name, "start": "start", "fallback": "start", "commands": {"menu": "start", "lang": "lang"},
           "vars": dict({"ui": ""}, **(vars or {}))}
    cfg.update(extra)
    cfg["nodes"] = out
    return cfg


def _home():
    return [_b(_L("↩️ منوی اصلی", "↩️ Main menu"), "home")]


_LANGBTN = lambda: _b(_L("🌐 زبان", "🌐 Language"), "lang")
_CH = "https://t.me/your_channel"
_NOTE_LANG = " ربات دوزبانه‌ست (فارسی و English)؛ اگه فقط یه زبان لازم داری، شاخه‌ی زبان دیگه (بخش‌هایی که با en_ شروع می‌شن) و دکمه‌ی «زبان» رو حذف کن."

# ═══════════ ۱) فروشگاه ═══════════
_SHOP = {
    "home": {"title": _L("منوی اصلی", "Main menu"),
        "text": _L("<b>🛍 به [نام فروشگاه] خوش اومدی، {name}!</b>\n\nاینجا بهترین‌ها رو با ارسال سریع و ضمانت اصالت پیدا می‌کنی.\n\n<blockquote>🚚 ارسال به سراسر کشور\n✅ ضمانت اصالت کالا\n💬 پشتیبانی همیشه کنارته</blockquote>\nاز منوی زیر شروع کن 👇",
                   "<b>🛍 Welcome to [Store name], {name}!</b>\n\nFind the best products with fast delivery and guaranteed authenticity.\n\n<blockquote>🚚 Nationwide delivery\n✅ Authenticity guaranteed\n💬 Support always at your side</blockquote>\nStart from the menu below 👇"),
        "alt": [{"when": {"var": "visits", "op": ">", "value": "1"},
                 "text": _L("<b>خوش برگشتی {name}! 👋</b>\n\nامروز دنبال چی هستی؟ تازه‌ترین‌ها و تخفیف‌ها منتظرتن.\n\n<blockquote>🚚 ارسال سریع · ✅ ضمانت اصالت · 💬 پشتیبانی</blockquote>",
                            "<b>Welcome back, {name}! 👋</b>\n\nWhat are you looking for today? New arrivals and deals are waiting.\n\n<blockquote>🚚 Fast delivery · ✅ Authentic · 💬 Support</blockquote>")}],
        "buttons": [[_b(_L("🛍 محصولات", "🛍 Products"), "products"), _b(_L("🧾 ثبت سفارش", "🧾 Place order"), "order")],
                    [_b(_L("📦 پیگیری سفارش", "📦 Track order"), "track"), _b(_L("❓ سؤالات متداول", "❓ FAQ"), "faq")],
                    [_b(_L("☎️ تماس با ما", "☎️ Contact"), "contact"), _LANGBTN()]]},
    "products": {"title": _L("محصولات", "Products"),
        "text": _L("<b>🛍 محصولات ما</b>\n\nیک دسته رو انتخاب کن:", "<b>🛍 Our products</b>\n\nPick a category:"),
        "buttons": [[_b(_L("🔥 پرفروش‌ها", "🔥 Best sellers"), "best"), _b(_L("🏷 تخفیف‌ها", "🏷 Deals"), "deals")],
                    [_b(_L("🆕 جدیدترین‌ها", "🆕 New arrivals"), "fresh")], _home()]},
    "best": {"title": _L("پرفروش‌ها", "Best sellers"),
        "text": _L("<b>🔥 پرفروش‌ها</b>\n\n1️⃣ [نام محصول اول] — <b>[قیمت] تومان</b>\n2️⃣ [نام محصول دوم] — <b>[قیمت] تومان</b>\n3️⃣ [نام محصول سوم] — <b>[قیمت] تومان</b>\n\n<i>برای خرید، «ثبت سفارش» رو بزن و اسم محصول رو بنویس.</i>",
                   "<b>🔥 Best sellers</b>\n\n1️⃣ [Product one] — <b>[price]</b>\n2️⃣ [Product two] — <b>[price]</b>\n3️⃣ [Product three] — <b>[price]</b>\n\n<i>To buy, tap “Place order” and write the product name.</i>"),
        "buttons": [[_b(_L("🧾 ثبت سفارش", "🧾 Place order"), "order")], [_b(_L("↩️ دسته‌ها", "↩️ Categories"), "products"), _home()[0]]]},
    "deals": {"title": _L("تخفیف‌ها", "Deals"),
        "text": _L("<b>🏷 تخفیف‌های ویژه</b>\n\n1️⃣ [محصول] — <s>[قیمت قبل]</s> ➜ <b>[قیمت جدید] تومان</b>\n2️⃣ [محصول] — <s>[قیمت قبل]</s> ➜ <b>[قیمت جدید] تومان</b>\n\n<blockquote>⏳ تا [تاریخ پایان] فرصت داری.</blockquote>",
                   "<b>🏷 Special deals</b>\n\n1️⃣ [Product] — <s>[old price]</s> ➜ <b>[new price]</b>\n2️⃣ [Product] — <s>[old price]</s> ➜ <b>[new price]</b>\n\n<blockquote>⏳ Offer ends [end date].</blockquote>"),
        "buttons": [[_b(_L("🧾 ثبت سفارش", "🧾 Place order"), "order")], [_b(_L("↩️ دسته‌ها", "↩️ Categories"), "products"), _home()[0]]]},
    "fresh": {"title": _L("جدیدترین‌ها", "New arrivals"),
        "text": _L("<b>🆕 تازه رسیده‌ها</b>\n\n1️⃣ [محصول جدید] — <b>[قیمت] تومان</b>\n2️⃣ [محصول جدید] — <b>[قیمت] تومان</b>\n3️⃣ [محصول جدید] — <b>[قیمت] تومان</b>",
                   "<b>🆕 Just arrived</b>\n\n1️⃣ [New product] — <b>[price]</b>\n2️⃣ [New product] — <b>[price]</b>\n3️⃣ [New product] — <b>[price]</b>"),
        "buttons": [[_b(_L("🧾 ثبت سفارش", "🧾 Place order"), "order")], [_b(_L("↩️ دسته‌ها", "↩️ Categories"), "products"), _home()[0]]]},
    "order": {"title": _L("ثبت سفارش", "Place order"),
        "text": _L("<b>🧾 ثبت سفارش</b>\n\nچند تا سؤال کوتاه ازت می‌پرسم تا سفارشت ثبت بشه.", "<b>🧾 Place your order</b>\n\nI'll ask a few short questions to register your order."),
        "fields": _L(["اسم و فامیلت؟", "شماره تماست؟", "چه محصولی می‌خوای؟ (اسم، تعداد، رنگ یا سایز)", "آدرس کامل برای ارسال؟"],
                     ["Your full name?", "Your phone number?", "What would you like to order? (name, quantity, colour or size)", "Full delivery address?"]),
        "save": ["cname", "cphone", "", ""], "types": ["text", "phone", "text", "text"], "ticket": True, "tag": "سفارش",
        "done": _L("<b>✅ سفارشت ثبت شد</b>\nشماره پیگیری: <code>#{ticket_no}</code>\nبه‌زودی برای تأیید و پرداخت باهات تماس می‌گیریم.",
                   "<b>✅ Your order is registered</b>\nTracking number: <code>#{ticket_no}</code>\nWe'll contact you shortly to confirm and arrange payment."),
        "next": "thanks", "buttons": [[_b(_L("↩️ انصراف", "↩️ Cancel"), "home")]]},
    "thanks": {"title": _L("ممنون از سفارشت", "Thank you"),
        "text": _L("<b>🙏 ممنون از اعتمادت، {cname|دوست من}!</b>\n\nسفارشت در صف بررسیه و پاسخ رو همین‌جا برات می‌فرستیم.", "<b>🙏 Thank you for trusting us, {cname|friend}!</b>\n\nYour order is being reviewed and we'll reply right here."),
        "do": [{"op": "remind", "minutes": 2880, "key": "fb", "goto": "feedback",
                "value": _L("سلام {name} 👋 سفارشت چطور بود؟ یه امتیاز بده تا بهتر بشیم.", "Hi {name} 👋 how was your order? Rate us so we can improve.")}],
        "buttons": [[_b(_L("📦 پیگیری سفارش", "📦 Track order"), "track")], _home()]},
    "feedback": {"title": _L("امتیاز به فروشگاه", "Rate us"),
        "text": _L("<b>⭐ نظرت درباره‌ی خریدت؟</b>\n\nیه امتیاز بده:", "<b>⭐ How was your purchase?</b>\n\nGive us a rating:"),
        "buttons": [[_b("⭐⭐⭐⭐⭐", "rated", do=[{"op": "notify", "value": "امتیاز ۵ از ۵ از طرف {name}"}]),
                     _b("⭐⭐⭐⭐", "rated", do=[{"op": "notify", "value": "امتیاز ۴ از ۵ از طرف {name}"}])],
                    [_b("⭐⭐⭐", "rated", do=[{"op": "notify", "value": "امتیاز ۳ از ۵ از طرف {name}"}]),
                     _b("⭐⭐", "rated", do=[{"op": "notify", "value": "امتیاز ۲ از ۵ از طرف {name}"}]),
                     _b("⭐", "rated", do=[{"op": "notify", "value": "امتیاز ۱ از ۵ از طرف {name}"}])]]},
    "rated": {"title": _L("ممنون از نظرت", "Thanks for rating"),
        "text": _L("<b>💚 ممنون از بازخوردت!</b>\nبرای مشکل یا پیشنهاد، همین‌جا پیام بده.", "<b>💚 Thanks for your feedback!</b>\nFor any issue or suggestion, message us right here."),
        "buttons": [[_b(_L("💬 ارسال پیام", "💬 Send a message"), "msg")], _home()]},
    "track": {"title": _L("پیگیری سفارش", "Track order"),
        "text": _L("<b>📦 پیگیری سفارش</b>\n\nشماره‌ی پیگیری سفارشت (مثل <code>#12</code>) یا شماره تماست رو بفرست تا وضعیتش رو بررسی کنیم.",
                   "<b>📦 Track your order</b>\n\nSend your tracking number (like <code>#12</code>) or your phone number and we'll check its status."),
        "ask": True, "ticket": True, "tag": "پیگیری",
        "done": _L("درخواستت ثبت شد (تیکت #{ticket_no}). نتیجه رو همین‌جا می‌فرستیم.", "Request received (ticket #{ticket_no}). We'll reply right here."),
        "next": "home", "buttons": [[_b(_L("↩️ انصراف", "↩️ Cancel"), "home")]]},
    "faq": {"title": _L("سؤالات متداول", "FAQ"),
        "text": _L("<b>❓ سؤالات متداول</b>\n\nروی هر مورد بزن:", "<b>❓ Frequently asked questions</b>\n\nTap any item:"),
        "buttons": [[_b(_L("🚚 زمان و هزینه‌ی ارسال", "🚚 Delivery time and cost"), alert=_L("[زمان تحویل و هزینه‌ی ارسال رو اینجا بنویس]", "[Write delivery time and cost here]"))],
                    [_b(_L("💳 روش‌های پرداخت", "💳 Payment methods"), alert=_L("[روش‌های پرداخت رو اینجا بنویس]", "[Write payment methods here]"))],
                    [_b(_L("🔄 مرجوعی و تعویض", "🔄 Returns and exchanges"), alert=_L("[شرایط مرجوعی رو اینجا بنویس]", "[Write your return policy here]"))],
                    _home()]},
    "contact": {"title": _L("تماس با ما", "Contact"),
        "text": _L("<b>☎️ تماس با ما</b>\n\n📞 [شماره تماس]\n📍 [آدرس]\n🕘 [ساعت کاری]\n\n<i>پشتیبانی تلگرامی هم همین‌جاست؛ «ارسال پیام» رو بزن.</i>",
                   "<b>☎️ Contact us</b>\n\n📞 [Phone]\n📍 [Address]\n🕘 [Working hours]\n\n<i>Telegram support is right here too; tap “Send a message”.</i>"),
        "buttons": [[_b(_L("📋 کپی شماره", "📋 Copy phone"), copy="[شماره تماس]"), _b(_L("📣 کانال ما", "📣 Our channel"), url=_CH)],
                    [_b(_L("💬 ارسال پیام", "💬 Send a message"), "msg")], _home()]},
    "msg": {"title": _L("پیام به پشتیبانی", "Message support"),
        "text": _L("<b>💬 پیام به پشتیبانی</b>\n\nسؤال یا مشکلت رو بنویس؛ مستقیم برای تیم ما می‌رسه.", "<b>💬 Message support</b>\n\nWrite your question or issue; it goes straight to our team."),
        "ask": True, "ticket": True, "tag": "پشتیبانی",
        "done": _L("پیامت ثبت شد (تیکت #{ticket_no}). به‌زودی همین‌جا جواب می‌دیم.", "Message received (ticket #{ticket_no}). We'll reply right here soon."),
        "next": "home", "buttons": [[_b(_L("↩️ انصراف", "↩️ Cancel"), "home")]]},
}

# ═══════════ ۲) پشتیبانی ═══════════
_OPEN = {"all": [{"var": "hour", "op": ">=", "value": "9"}, {"var": "hour", "op": "<", "value": "21"}]}


def _faq_page(title_fa, title_en, qa_fa, qa_en):
    return {"title": _L(title_fa, title_en),
            "text": _L(f"<b>{title_fa}</b>\n\n{qa_fa}", f"<b>{title_en}</b>\n\n{qa_en}"),
            "buttons": [[_b(_L("🎫 هنوز جواب نگرفتم", "🎫 Still need help"), "ticket")],
                        [_b(_L("↩️ دسته‌ها", "↩️ Topics"), "faq"), _home()[0]]]}


def _dept(tag, fa, en):
    return {"title": _L(fa, en), "text": _L(f"<b>🎫 {fa}</b>\n\nمشکل یا سؤالت رو کامل بنویس؛ هر چی جزئیات بیشتر، سریع‌تر جواب می‌گیری. عکس و فایل هم می‌تونی بفرستی.",
                                             f"<b>🎫 {en}</b>\n\nDescribe your issue in detail; the more detail, the faster the answer. You can send photos and files too."),
            "ask": True, "ticket": True, "tag": tag,
            "done": _L("<b>✅ درخواستت ثبت شد</b>\nکد پیگیری: <code>#{ticket_no}</code>\nجواب رو همین‌جا برات می‌فرستیم.",
                       "<b>✅ Your request is registered</b>\nReference: <code>#{ticket_no}</code>\nWe'll reply right here."),
            "next": "home", "buttons": [[_b(_L("↩️ انصراف", "↩️ Cancel"), "ticket")]]}


def _rate(n, fa, en):
    return _b(_L(fa, en), "rated", do=[{"op": "notify", "value": "رضایت از پشتیبانی: " + n + " (از طرف {name})"}])


_SUPPORT = {
    "home": {"title": _L("منوی اصلی", "Main menu"),
        "text": _L("<b>🎧 مرکز پشتیبانی</b>\nسلام {name}! 👋\n\n🔴 <b>الان خارج از ساعت کاری هستیم</b> (۹ تا ۲۱)؛ پیامت رو بذار، اولین فرصت جواب می‌دیم.\n\nچطور می‌تونیم کمکت کنیم؟",
                   "<b>🎧 Support center</b>\nHi {name}! 👋\n\n🔴 <b>We're outside working hours</b> (9:00–21:00 Tehran); leave your message and we'll reply as soon as we can.\n\nHow can we help you?"),
        "alt": [{"when": _OPEN, "text": _L("<b>🎧 مرکز پشتیبانی</b>\nسلام {name}! 👋\n\n🟢 <b>الان آنلاین هستیم</b> و معمولاً ظرف چند دقیقه جواب می‌دیم.\n\nچطور می‌تونیم کمکت کنیم؟",
                                            "<b>🎧 Support center</b>\nHi {name}! 👋\n\n🟢 <b>We're online</b> and usually reply within minutes.\n\nHow can we help you?")}],
        "buttons": [[_b(_L("❓ سؤالات متداول", "❓ FAQ"), "faq"), _b(_L("🎫 ارسال درخواست", "🎫 New request"), "ticket")],
                    [_b(_L("🔎 پیگیری درخواست", "🔎 Track request"), "status"), _b(_L("📞 راه‌های تماس", "📞 Contact"), "contact")],
                    [_b(_L("⭐ نظرسنجی", "⭐ Feedback"), "rate"), _LANGBTN()]]},
    "faq": {"title": _L("سؤالات متداول", "FAQ"),
        "text": _L("<b>❓ سؤالات متداول</b>\n\nموضوع مورد نظرت رو انتخاب کن:", "<b>❓ Frequently asked questions</b>\n\nChoose a topic:"),
        "buttons": [[_b(_L("💳 پرداخت و فاکتور", "💳 Payment and invoices"), "faq_pay")],
                    [_b(_L("🚚 ارسال و تحویل", "🚚 Delivery"), "faq_ship")],
                    [_b(_L("🔧 مشکلات فنی", "🔧 Technical issues"), "faq_tech")], _home()]},
    "faq_pay": _faq_page("💳 پرداخت و فاکتور",
        "💳 Payment and invoices",
        "<b>چه روش‌هایی برای پرداخت دارید؟</b>\n[پاسخ رو اینجا بنویس]\n\n<b>فاکتور رسمی صادر می‌کنید؟</b>\n[پاسخ رو اینجا بنویس]\n\n<b>اگه پرداخت ناموفق بود چی؟</b>\n[بازه‌ی برگشت وجه و راهنمای پیگیری]",
        "<b>Which payment methods do you accept?</b>\n[Write the answer here]\n\n<b>Do you issue official invoices?</b>\n[Write the answer here]\n\n<b>What if a payment fails?</b>\n[Refund window and how to follow up]"),
    "faq_ship": _faq_page("🚚 ارسال و تحویل",
        "🚚 Delivery",
        "<b>ارسال چقدر طول می‌کشه؟</b>\n[پاسخ رو اینجا بنویس]\n\n<b>هزینه‌ی ارسال چقدره؟</b>\n[پاسخ رو اینجا بنویس]\n\n<b>کد رهگیری کجا می‌آد؟</b>\n[پاسخ رو اینجا بنویس]",
        "<b>How long does delivery take?</b>\n[Write the answer here]\n\n<b>How much is shipping?</b>\n[Write the answer here]\n\n<b>Where do I get the tracking code?</b>\n[Write the answer here]"),
    "faq_tech": _faq_page("🔧 مشکلات فنی",
        "🔧 Technical issues",
        "<b>وارد حسابم نمی‌شم، چیکار کنم؟</b>\n[پاسخ رو اینجا بنویس]\n\n<b>برنامه یا سرویس درست کار نمی‌کنه.</b>\n[پاسخ رو اینجا بنویس]\n\n<i>اگه مشکلت حل نشد، درخواست ثبت کن؛ تیم فنی بررسی می‌کنه.</i>",
        "<b>I can't log in, what should I do?</b>\n[Write the answer here]\n\n<b>The app or service isn't working properly.</b>\n[Write the answer here]\n\n<i>If it's still not solved, open a request; our technical team will look into it.</i>"),
    "ticket": {"title": _L("ارسال درخواست", "New request"),
        "text": _L("<b>🎫 ارسال درخواست</b>\n\nدرخواستت مربوط به کدوم بخشه؟", "<b>🎫 New request</b>\n\nWhich team is your request for?"),
        "buttons": [[_b(_L("💰 فروش و قیمت", "💰 Sales and pricing"), "t_sales")], [_b(_L("🔧 فنی", "🔧 Technical"), "t_tech")],
                    [_b(_L("🧾 مالی و پرداخت", "🧾 Billing"), "t_bill")], _home()]},
    "t_sales": _dept("فروش", "فروش و قیمت", "Sales and pricing"),
    "t_tech": _dept("فنی", "پشتیبانی فنی", "Technical support"),
    "t_bill": _dept("مالی", "مالی و پرداخت", "Billing"),
    "status": {"title": _L("پیگیری درخواست", "Track request"),
        "text": _L("<b>🔎 پیگیری درخواست</b>\n\nکد درخواستت (مثل <code>#12</code>) رو بفرست تا وضعیتش رو بررسی کنیم.", "<b>🔎 Track your request</b>\n\nSend your reference (like <code>#12</code>) and we'll check its status."),
        "ask": True, "ticket": True, "tag": "پیگیری",
        "done": _L("ثبت شد (تیکت #{ticket_no}). نتیجه رو همین‌جا می‌فرستیم.", "Received (ticket #{ticket_no}). We'll reply right here."),
        "next": "home", "buttons": [[_b(_L("↩️ انصراف", "↩️ Cancel"), "home")]]},
    "contact": {"title": _L("راه‌های تماس", "Contact"),
        "text": _L("<b>📞 راه‌های تماس</b>\n\n📞 [شماره تماس]\n✉️ [ایمیل]\n🕘 [ساعت کاری: ۹ تا ۲۱]\n\n<i>سریع‌ترین راه، ثبت درخواست همین‌جاست.</i>",
                   "<b>📞 Contact</b>\n\n📞 [Phone]\n✉️ [Email]\n🕘 [Working hours: 9:00–21:00]\n\n<i>The fastest way is to open a request right here.</i>"),
        "buttons": [[_b(_L("📋 کپی ایمیل", "📋 Copy email"), copy="[ایمیل]"), _b(_L("📣 کانال ما", "📣 Our channel"), url=_CH)],
                    [_b(_L("🎫 ارسال درخواست", "🎫 New request"), "ticket")], _home()]},
    "rate": {"title": _L("نظرسنجی", "Feedback"),
        "text": _L("<b>⭐ از پشتیبانی راضی بودی؟</b>\n\nبازخوردت به ما کمک می‌کنه بهتر بشیم:", "<b>⭐ Happy with our support?</b>\n\nYour feedback helps us improve:"),
        "buttons": [[_rate("عالی", "😍 عالی", "😍 Great"), _rate("خوب", "🙂 خوب", "🙂 Good"), _rate("ضعیف", "😕 ضعیف", "😕 Poor")], _home()]},
    "rated": {"title": _L("ممنون", "Thanks"),
        "text": _L("<b>💚 ممنون از بازخوردت!</b>", "<b>💚 Thanks for your feedback!</b>"), "buttons": [_home()]},
}

# ═══════════ ۳) رزرو نوبت ═══════════
_BOOKING = {
    "home": {"title": _L("منوی اصلی", "Main menu"),
        "text": _L("<b>📅 رزرو آنلاین نوبت</b>\nسلام {name}! 👋\n\nبدون معطلی و تماس تلفنی، نوبتت رو همین‌جا رزرو کن.\n\n<blockquote>🕘 [ساعت کاری]\n📍 [آدرس کوتاه]</blockquote>",
                   "<b>📅 Online booking</b>\nHi {name}! 👋\n\nBook your appointment right here, no phone calls and no waiting.\n\n<blockquote>🕘 [Working hours]\n📍 [Short address]</blockquote>"),
        "alt": [{"when": {"var": "cname", "op": "filled"},
                 "text": _L("<b>📅 رزرو آنلاین نوبت</b>\nخوش برگشتی {cname}! 👋\n\nآماده‌ای نوبت بعدی رو رزرو کنی؟\n\n<blockquote>🕘 [ساعت کاری]\n📍 [آدرس کوتاه]</blockquote>",
                            "<b>📅 Online booking</b>\nWelcome back, {cname}! 👋\n\nReady to book your next appointment?\n\n<blockquote>🕘 [Working hours]\n📍 [Short address]</blockquote>")}],
        "buttons": [[_b(_L("💈 خدمات و تعرفه", "💈 Services and prices"), "services"), _b(_L("📅 رزرو نوبت", "📅 Book now"), "book")],
                    [_b(_L("📍 آدرس و ساعت کاری", "📍 Location and hours"), "location"), _b(_L("✏️ لغو یا تغییر نوبت", "✏️ Cancel or change"), "change")],
                    [_LANGBTN()]]},
    "services": {"title": _L("خدمات و تعرفه", "Services and prices"),
        "text": _L("<b>💈 خدمات و تعرفه</b>\n\n1️⃣ [خدمت اول] — ⏱ [مدت] — <b>[قیمت] تومان</b>\n2️⃣ [خدمت دوم] — ⏱ [مدت] — <b>[قیمت] تومان</b>\n3️⃣ [خدمت سوم] — ⏱ [مدت] — <b>[قیمت] تومان</b>\n\n<i>قیمت‌ها ممکنه بسته به شرایط کمی تغییر کنه.</i>",
                   "<b>💈 Services and prices</b>\n\n1️⃣ [Service one] — ⏱ [duration] — <b>[price]</b>\n2️⃣ [Service two] — ⏱ [duration] — <b>[price]</b>\n3️⃣ [Service three] — ⏱ [duration] — <b>[price]</b>\n\n<i>Prices may vary slightly depending on the case.</i>"),
        "buttons": [[_b(_L("📅 رزرو نوبت", "📅 Book now"), "book")], [_b(_L("📜 قوانین رزرو", "📜 Booking rules"), "rules"), _home()[0]]]},
    "rules": {"title": _L("قوانین رزرو", "Booking rules"),
        "text": _L("<b>📜 قوانین رزرو</b>\n\n<blockquote>• لطفاً ۱۰ دقیقه زودتر برسید.\n• لغو نوبت حداقل [مدت] ساعت قبل اعلام بشه.\n• [قانون دیگر]</blockquote>",
                   "<b>📜 Booking rules</b>\n\n<blockquote>• Please arrive 10 minutes early.\n• Cancel at least [hours] hours in advance.\n• [Another rule]</blockquote>"),
        "buttons": [[_b(_L("📅 رزرو نوبت", "📅 Book now"), "book")], _home()]},
    "book": {"title": _L("رزرو نوبت", "Book now"),
        "text": _L("<b>📅 رزرو نوبت</b>\n\nچند تا سؤال کوتاه ازت می‌پرسم تا نوبتت ثبت بشه.", "<b>📅 Book your appointment</b>\n\nI'll ask a few short questions to register your booking."),
        "fields": _L(["اسم و فامیلت؟", "شماره تماست؟", "کدوم خدمت رو می‌خوای؟", "چه روزی برات مناسبه؟ (مثلاً شنبه ۱۰ آبان)", "چه ساعتی؟ (مثلاً ۱۷:۳۰)"],
                     ["Your full name?", "Your phone number?", "Which service would you like?", "Which day suits you? (e.g. Saturday, 1 Nov)", "What time? (e.g. 5:30 pm)"]),
        "save": ["cname", "cphone", "", "", ""], "types": ["text", "phone", "text", "text", "text"], "ticket": True, "tag": "رزرو",
        "done": _L("<b>✅ درخواست نوبتت ثبت شد</b>\nکد پیگیری: <code>#{ticket_no}</code>\nبعد از هماهنگی زمان، تأیید رو همین‌جا می‌فرستیم.",
                   "<b>✅ Your booking request is registered</b>\nReference: <code>#{ticket_no}</code>\nOnce the time is confirmed we'll message you right here."),
        "next": "booked", "buttons": [[_b(_L("↩️ انصراف", "↩️ Cancel"), "home")]]},
    "booked": {"title": _L("ثبت شد", "Booked"),
        "text": _L("<b>🎉 {cname|دوست من} عزیز، درخواستت رسید!</b>\n\nهمکارهای ما زمان رو چک می‌کنن و برات تأیید می‌فرستن. اگه لازم شد تغییری بدی، از «لغو یا تغییر نوبت» استفاده کن.",
                   "<b>🎉 Got it, {cname|friend}!</b>\n\nOur team is checking the time slot and will confirm shortly. If you need to change something, use “Cancel or change”."),
        "buttons": [[_b(_L("📍 آدرس و ساعت کاری", "📍 Location and hours"), "location")], _home()]},
    "location": {"title": _L("آدرس و ساعت کاری", "Location and hours"),
        "text": _L("<b>📍 آدرس و ساعت کاری</b>\n\n📍 [آدرس کامل]\n🕘 [ساعت کاری]\n📞 [شماره تماس]\n\n<i>پارکینگ و راهنمای مسیر: [توضیح]</i>",
                   "<b>📍 Location and hours</b>\n\n📍 [Full address]\n🕘 [Working hours]\n📞 [Phone]\n\n<i>Parking and directions: [details]</i>"),
        "buttons": [[_b(_L("📋 کپی شماره", "📋 Copy phone"), copy="[شماره تماس]"), _b(_L("🗺 مسیریابی", "🗺 Directions"), url="https://maps.google.com")], _home()]},
    "change": {"title": _L("لغو یا تغییر نوبت", "Cancel or change"),
        "text": _L("<b>✏️ لغو یا تغییر نوبت</b>\n\nکد پیگیری نوبتت (یا شماره تماست) و تغییر مورد نظرت رو بنویس.", "<b>✏️ Cancel or change a booking</b>\n\nWrite your reference (or phone number) and the change you need."),
        "ask": True, "ticket": True, "tag": "لغو/تغییر",
        "done": _L("درخواستت ثبت شد (تیکت #{ticket_no}). به‌زودی همین‌جا جواب می‌دیم.", "Request received (ticket #{ticket_no}). We'll reply right here soon."),
        "next": "home", "buttons": [[_b(_L("↩️ انصراف", "↩️ Cancel"), "home")]]},
}

# ═══════════ ۴) باشگاه مشتریان ═══════════
_TODAY = {"var": "lastday", "op": "==", "value": "{date}"}
_NOTTODAY = {"var": "lastday", "op": "!=", "value": "{date}"}
_CLUB_HOME = ("<b>🏅 باشگاه مشتریان</b>\nسلام {name}! 👋\n\n⭐ امتیاز تو: <b>{points}</b>\n🎖 سطح: <b>%s</b>\n👥 دعوت‌های موفق: <b>{refs}</b>",
              "<b>🏅 Loyalty club</b>\nHi {name}! 👋\n\n⭐ Your points: <b>{points}</b>\n🎖 Level: <b>%s</b>\n👥 Successful invites: <b>{refs}</b>")


def _club_home(lv):
    return _L(_CLUB_HOME[0] % lv[0], _CLUB_HOME[1] % lv[1])


def _redeem(pts, fa, en):
    return _b(_L(f"🎟 {fa} ({pts} امتیاز)", f"🎟 {en} ({pts} pts)"), "redeemed",
              when={"var": "points", "op": ">=", "value": str(pts)},
              do=[{"op": "add", "var": "points", "value": "-" + str(pts)}, {"op": "notify", "value": f"درخواست جایزه: {fa} ({pts} امتیاز کسر شد)"}])


_CLUB = {
    "home": {"title": _L("منوی اصلی", "Main menu"), "text": _club_home(("برنزی 🥉", "Bronze 🥉")),
        "alt": [{"when": {"var": "points", "op": ">=", "value": "200"}, "text": _club_home(("طلایی 🥇", "Gold 🥇"))},
                {"when": {"var": "points", "op": ">=", "value": "100"}, "text": _club_home(("نقره‌ای 🥈", "Silver 🥈"))}],
        "buttons": [[_b(_L("🎁 جایزه‌ی امروز", "🎁 Daily reward"), "daily"), _b(_L("🏆 جوایز", "🏆 Rewards"), "rewards")],
                    [_b(_L("👥 دعوت دوستان", "👥 Invite friends"), "invite"), _b(_L("🥇 برترین‌ها", "🥇 Leaderboard"), "top")],
                    [_LANGBTN()]]},
    "daily": {"title": _L("جایزه‌ی روزانه", "Daily reward"),
        "text": _L("<b>🎁 جایزه‌ی روزانه</b>\n\nهر روز یک بار می‌تونی <b>۱۰ امتیاز</b> هدیه بگیری.", "<b>🎁 Daily reward</b>\n\nOnce a day you can claim <b>10 free points</b>."),
        "alt": [{"when": _TODAY, "text": _L("<b>✅ جایزه‌ی امروزت رو گرفتی</b>\n\nفردا دوباره بیا و امتیاز بگیر.", "<b>✅ You've claimed today's reward</b>\n\nCome back tomorrow for more points.")}],
        "buttons": [[_b(_L("🎁 دریافت ۱۰ امتیاز", "🎁 Claim 10 points"), "claimed", when=_NOTTODAY,
                        do=[{"op": "set", "var": "lastday", "value": "{date}"}, {"op": "add", "var": "points", "value": "10"}])], _home()]},
    "claimed": {"title": _L("امتیاز گرفتی", "Points claimed"),
        "text": _L("<b>🎉 ۱۰ امتیاز گرفتی!</b>\n\nمجموع امتیازهات: <b>{points}</b>", "<b>🎉 You got 10 points!</b>\n\nYour total: <b>{points}</b>"),
        "buttons": [[_b(_L("🥇 برترین‌ها", "🥇 Leaderboard"), "top")], _home()]},
    "rewards": {"title": _L("جوایز", "Rewards"),
        "text": _L("<b>🏆 جوایز باشگاه</b>\n\n<blockquote>🎟 ۵۰ امتیاز: [جایزه‌ی اول]\n🎟 ۱۰۰ امتیاز: [جایزه‌ی دوم]</blockquote>\n\nامتیاز تو: <b>{points}</b>\n<i>دکمه‌ی جایزه وقتی فعال می‌شه که امتیاز کافی داشته باشی.</i>",
                   "<b>🏆 Club rewards</b>\n\n<blockquote>🎟 50 points: [First reward]\n🎟 100 points: [Second reward]</blockquote>\n\nYour points: <b>{points}</b>\n<i>A reward button appears once you have enough points.</i>"),
        "buttons": [[_redeem(50, "جایزه‌ی اول", "First reward")], [_redeem(100, "جایزه‌ی دوم", "Second reward")], _home()]},
    "redeemed": {"title": _L("درخواست جایزه", "Reward requested"),
        "text": _L("<b>✅ درخواست جایزه‌ات ثبت شد</b>\n\nتیم ما برای هماهنگی بهت پیام می‌ده.\nامتیاز باقی‌مانده: <b>{points}</b>", "<b>✅ Reward requested</b>\n\nOur team will message you to arrange it.\nPoints left: <b>{points}</b>"),
        "buttons": [_home()]},
    "invite": {"title": _L("دعوت دوستان", "Invite friends"),
        "text": _L("<b>👥 دعوت دوستان</b>\n\nبه ازای هر دوستی که با لینک تو وارد بشه، <b>۲۰ امتیاز</b> می‌گیری.\n\n🔗 لینک اختصاصی تو:\n<code>{ref_link}</code>\n\nدعوت‌های موفق: <b>{refs}</b>",
                   "<b>👥 Invite friends</b>\n\nFor every friend who joins with your link you get <b>20 points</b>.\n\n🔗 Your personal link:\n<code>{ref_link}</code>\n\nSuccessful invites: <b>{refs}</b>"),
        "buttons": [[_b(_L("📤 ارسال لینک دعوت", "📤 Share invite link"), share=_L("بیا این باشگاه رو ببین؛ با ثبت‌نام امتیاز و جایزه می‌گیری 🎁", "Check out this club; join and earn points and rewards 🎁"))],
                    [_b(_L("📋 کپی لینک", "📋 Copy link"), copy="{ref_link}"), _b(_L("🏅 برترین دعوت‌کننده‌ها", "🏅 Top inviters"), "inv_top")], _home()]},
    "top": {"title": _L("برترین‌ها", "Leaderboard"),
        "text": _L("<b>🥇 برترین‌های باشگاه</b>", "<b>🥇 Club leaderboard</b>"),
        "board": {"var": "points", "top": 10, "label": _L("بیشترین امتیاز", "Most points")},
        "buttons": [[_b(_L("🎁 جایزه‌ی امروز", "🎁 Daily reward"), "daily")], _home()]},
    "inv_top": {"title": _L("برترین دعوت‌کننده‌ها", "Top inviters"),
        "text": _L("<b>🏅 برترین دعوت‌کننده‌ها</b>", "<b>🏅 Top inviters</b>"),
        "board": {"var": "refs", "top": 10, "label": _L("بیشترین دعوت", "Most invites")},
        "buttons": [[_b(_L("👥 دعوت دوستان", "👥 Invite friends"), "invite")], _home()]},
}

# ═══════════ ۵) دستیار هوشمند ═══════════
_AI_FA = ("تو دستیار هوشمند و مشاور [نام کسب‌وکار] هستی. مؤدب، گرم و حرفه‌ای باش.\n"
          "قوانین: ۱) به فارسی و کوتاه جواب بده (حداکثر ۵ جمله)؛ اگه کاربر زبان دیگه‌ای نوشت به همون زبان. "
          "۲) فقط درباره‌ی خدمات و محصولات همین کسب‌وکار کمک کن؛ سؤال بی‌ربط رو مؤدبانه به موضوع برگردون. "
          "۳) اگه جواب رو نمی‌دونی صادقانه بگو و پیشنهاد بده با پشتیبانی انسانی صحبت کنه؛ هرگز قیمت، شماره یا اطلاعات نساز. "
          "۴) وقتی مناسبه، یک سؤال کوتاه بپرس تا مشتری رو به ثبت درخواست یا خرید هدایت کنی. "
          "۵) بدون Markdown و بدون فرمت‌بندی خاص بنویس.\n"
          "نام کاربر: {name}\nاطلاعات کسب‌وکار: [خدمات، قیمت‌ها، ساعت کاری، آدرس و شرایط رو اینجا بنویس]")
_AI_EN = ("You are the smart assistant and advisor of [Business name]. Be polite, warm and professional.\n"
          "Rules: 1) Answer in English and keep it short (max 5 sentences); if the user writes in another language, reply in that language. "
          "2) Only help with this business's services and products; politely steer unrelated questions back. "
          "3) If you don't know the answer, say so honestly and suggest talking to a human; never invent prices, numbers or facts. "
          "4) When appropriate, ask one short question to guide the customer toward a request or purchase. "
          "5) Write plain text, no Markdown or special formatting.\n"
          "User name: {name}\nBusiness info: [write services, prices, hours, address and terms here]")

_AIBOT = {
    "home": {"title": _L("منوی اصلی", "Main menu"),
        "text": _L("<b>🤖 دستیار هوشمند [نام کسب‌وکار]</b>\nسلام {name}! 👋\n\nهر سؤالی داری بپرس؛ شبانه‌روز جواب می‌دم.\n\n<blockquote>💡 قیمت‌ها، خدمات، پیشنهاد مناسب و راهنمایی خرید</blockquote>",
                   "<b>🤖 [Business name] smart assistant</b>\nHi {name}! 👋\n\nAsk me anything; I answer around the clock.\n\n<blockquote>💡 Prices, services, tailored suggestions and buying advice</blockquote>"),
        "buttons": [[_b(_L("💬 شروع گفتگو", "💬 Start chatting"), "chat")],
                    [_b(_L("💡 چی بپرسم؟", "💡 What can I ask?"), "ideas"), _b(_L("ℹ️ درباره‌ی ما", "ℹ️ About us"), "about")],
                    [_b(_L("📩 صحبت با انسان", "📩 Talk to a human"), "human")], [_LANGBTN()]]},
    "chat": {"title": _L("گفتگو", "Chat"),
        "text": _L("<b>💬 گفتگو با دستیار</b>\n\nسلام! سؤالت رو بنویس؛ برای خروج «پایان گفتگو» رو بزن.", "<b>💬 Chat with the assistant</b>\n\nHello! Type your question; tap “End chat” to leave."),
        "ai": {"prompt": _L(_AI_FA, _AI_EN), "daily": 25, "memory": 4},
        "buttons": [[_b(_L("📩 صحبت با انسان", "📩 Talk to a human"), "human"), _b(_L("🏠 پایان گفتگو", "🏠 End chat"), "home")]]},
    "ideas": {"title": _L("نمونه سؤال‌ها", "Example questions"),
        "text": _L("<b>💡 چی می‌تونی بپرسی؟</b>\n\n<blockquote>• «برای [نیاز من] چی پیشنهاد می‌کنی؟»\n• «قیمت [خدمت] چنده؟»\n• «ساعت کاری و آدرس شما کجاست؟»\n• «تفاوت [گزینه ۱] و [گزینه ۲] چیه؟»</blockquote>",
                   "<b>💡 What can you ask?</b>\n\n<blockquote>• “What do you recommend for [my need]?”\n• “How much is [service]?”\n• “What are your hours and address?”\n• “What's the difference between [option 1] and [option 2]?”</blockquote>"),
        "buttons": [[_b(_L("💬 شروع گفتگو", "💬 Start chatting"), "chat")], _home()]},
    "human": {"title": _L("صحبت با انسان", "Talk to a human"),
        "text": _L("<b>📩 صحبت با تیم ما</b>\n\nپیامت رو بنویس؛ مستقیم برای یکی از همکارهامون می‌رسه.", "<b>📩 Talk to our team</b>\n\nWrite your message; it goes straight to one of our team members."),
        "ask": True, "ticket": True, "tag": "انسانی",
        "done": _L("پیامت ثبت شد (تیکت #{ticket_no}). به‌زودی همین‌جا جواب می‌دیم.", "Message received (ticket #{ticket_no}). We'll reply right here soon."),
        "next": "home", "buttons": [[_b(_L("↩️ انصراف", "↩️ Cancel"), "home")]]},
    "about": {"title": _L("درباره‌ی ما", "About us"),
        "text": _L("<b>ℹ️ درباره‌ی ما</b>\n\n[چند خط درباره‌ی کسب‌وکارت]\n\n📞 [شماره تماس]", "<b>ℹ️ About us</b>\n\n[A few lines about your business]\n\n📞 [Phone]"),
        "buttons": [[_b(_L("📣 کانال ما", "📣 Our channel"), url=_CH)], _home()]},
}

TEMPLATES = {
    "shop": {"icon": "bag", "title": "فروشگاه حرفه‌ای", "desc": "کاتالوگ محصولات، ثبت سفارش، پیگیری و نظرسنجی خودکار",
        "feats": ["دوزبانه", "فرم سفارش + تیکت", "پیگیری سفارش", "نظرسنجی بعد از خرید"],
        "note": "فروشگاه کامل ساختم: دسته‌های محصول، فرم سفارش، پیگیری، سؤالات متداول و تماس. هر سفارش یه تیکت می‌شه که با دکمه‌ی «پاسخ» زیرش به مشتری جواب می‌دی؛ دو روز بعد از سفارش هم خودکار نظرسنجی می‌فرسته. متن‌های داخل [ ] جای‌نگه‌دارن؛ از «ویرایش دستی» عوضشون کن." + _NOTE_LANG,
        "config": _bilingual("فروشگاه من", _SHOP, {"cname": "", "cphone": ""})},
    "support": {"icon": "headset", "title": "پشتیبانی مشتری", "desc": "سؤالات متداول، تیکت بخش‌بندی‌شده و نمایش آنلاین یا آفلاین بودن",
        "feats": ["دوزبانه", "تیکت به‌تفکیک بخش", "وضعیت آنلاین", "نظرسنجی رضایت"],
        "note": "مرکز پشتیبانی ساختم: سؤالات متداول در سه دسته، ثبت درخواست برای فروش، فنی و مالی (هر کدوم با برچسب جدا)، پیگیری و نظرسنجی. بر اساس ساعت تهران، صفحه‌ی اصلی آنلاین یا خارج از ساعت کاری رو نشون می‌ده (۹ تا ۲۱؛ از ویرایش بخش اصلی عوض کن). تیکت‌ها داخل همین چت با دکمه‌ی «پاسخ» می‌رسن و با /tickets هم می‌بینیشون." + _NOTE_LANG,
        "config": _bilingual("پشتیبانی", _SUPPORT, desk={"closed": "✅ درخواستت بسته شد · Your request has been closed. اگه مشکلی هست دوباره پیام بده · Message us again if needed.", "reply_btn": "💬 پاسخ · Reply"})},
    "booking": {"icon": "cal", "title": "رزرو نوبت", "desc": "خدمات و تعرفه، رزرو، لغو یا تغییر و قوانین؛ مناسب کلینیک، سالن و آموزشگاه",
        "feats": ["دوزبانه", "رزرو با تیکت", "لغو یا تغییر", "شناخت مشتری تکراری"],
        "note": "ربات رزرو نوبت ساختم: خدمات و تعرفه، فرم رزرو (نام، شماره، خدمت، روز و ساعت)، لغو یا تغییر نوبت، قوانین و آدرس. درخواست‌ها برات تیکت می‌شن و با دکمه‌ی «پاسخ» تأیید زمان رو می‌فرستی؛ مشتری تکراری با اسمش خوشامد می‌شنوه. خدمت‌ها، قیمت‌ها و آدرس جای‌نگه‌دارن؛ از «ویرایش دستی» عوضشون کن." + _NOTE_LANG,
        "config": _bilingual("رزرو نوبت", _BOOKING, {"cname": "", "cphone": ""})},
    "club": {"icon": "medal", "title": "باشگاه مشتریان", "desc": "امتیاز، جایزه‌ی روزانه، سطح‌بندی، دعوت دوستان و جدول برترین‌ها",
        "feats": ["دوزبانه", "جایزه‌ی روزانه", "سطح برنزی تا طلایی", "دعوت و جدول برترین‌ها"],
        "note": "باشگاه مشتریان ساختم: هر نفر روزی یک بار ۱۰ امتیاز می‌گیره، با ۱۰۰ و ۲۰۰ امتیاز سطح نقره‌ای و طلایی می‌شه، با دعوت هر دوست ۲۰ امتیاز می‌گیره و جدول برترین‌ها و برترین دعوت‌کننده‌ها هست. جایزه‌های ۵۰ و ۱۰۰ امتیازی درخواستشون برات می‌آد. جایزه‌ها رو از «ویرایش دستی» بنویس." + _NOTE_LANG,
        "config": _bilingual("باشگاه مشتریان", _CLUB, {"points": "0", "lastday": ""}, on_ref=[{"op": "add", "var": "points", "value": "20"}],
                             ref_text="🎉 یه نفر با لینک تو وارد شد و ۲۰ امتیاز گرفتی! امتیاز تو: {points} · Someone joined with your link: +20 points! Total: {points}")},
    "ai": {"icon": "bot", "title": "دستیار هوشمند", "desc": "چت‌بات هوش مصنوعی با پیشنهاد سؤال و انتقال به انسان",
        "feats": ["دوزبانه", "هوش مصنوعی با حافظه", "نمونه سؤال", "انتقال به انسان"],
        "note": "دستیار هوشمند ساختم: گفتگوی آزاد با هوش مصنوعی (حافظه‌ی ۴ پیام و حداکثر ۲۵ پیام در روز برای هر نفر)، نمونه سؤال‌ها و دکمه‌ی صحبت با انسان که تیکت می‌شه. حتماً اطلاعات واقعی کسب‌وکارت رو (خدمات، قیمت، ساعت کاری) توی دستورالعمل بخش «گفتگو» بنویس تا جواب‌ها دقیق باشن. هر پیام کاربر حدود ۱ توکن از حساب تو مصرف می‌کنه." + _NOTE_LANG,
        "config": _bilingual("دستیار هوشمند", _AIBOT)},
}
