# -*- coding: utf-8 -*-
"""
caps.py — رجیستری قابلیت‌ها (منبع واحد همه‌ی چیزهایی که موتور بلده)

همه‌ی برچسب‌های فارسی «وقتی … اگه … آنگاه»، انواع دکمه، بلوک‌های مینی‌اپ و بازی‌ها همین‌جاست؛
استودیو، صفحه‌ی شروع و پرامپت هوش مصنوعی همه از همین می‌سازند تا هیچ‌وقت قابلیت ناموجود نمایش داده نشود.
سازندگان:  CAPS_EVENTS (وقتی)، CAPS_IF (اگه)، CAPS_DO (آنگاه)، CAPS_BTNS (دکمه)، CAPS_BLOCKS (بلوک)،
           CAPS_GAMES (بازی)، LIMITS (سقف پلن‌محور)، caps_public()، caps_ai_text()، limit_of()
"""

BUILD = "3.6.1"

# سقف پلن‌محور: هر کلید با perks اشتراک جمع یا مقایسه می‌شود. مقدار «free» پایه است.
# nodes = بخش‌های ربات، blocks = بلوک‌های مینی‌اپ، tables = جدول داده، screens/گروه‌های دیگر در PLANS perks هستند.
LIMITS = {
    "nodes":  {"free": 200, "premium": 400, "pro": 800},
    "blocks": {"free": 120, "premium": 200, "pro": 350},
    "tables": {"free": 6, "premium": 10, "pro": 16},
    "screens": {"free": 12, "premium": 16, "pro": 24},
}

# ───────────────────────── «وقتی» — رویدادهایی که جریان را شروع می‌کنند ─────────────────────────
# هر رویداد: کلید موتور + برچسب فارسی + توضیح + سطح‌هایی که در آن‌ها کار می‌کند.
CAPS_EVENTS = [
    {"k": "start",      "fa": "وقتی کاربر /start زد یا ربات را باز کرد", "hint": "اولین برخورد کاربر با ربات", "scopes": ["pv"]},
    {"k": "command",    "fa": "وقتی یک دستور فرستاد (مثل /help)", "hint": "دستورها را در تنظیمات ربات می‌سازی", "scopes": ["pv"]},
    {"k": "text",       "fa": "وقتی پیام داد و ربات متوجه نشد", "hint": "بخش «پاسخ به پیام‌های ناشناس»", "scopes": ["pv"]},
    {"k": "button",     "fa": "وقتی روی یک دکمه لمس کرد", "hint": "هر دکمه می‌تواند کار خودش را داشته باشد", "scopes": ["pv", "group"]},
    {"k": "form",       "fa": "وقتی فرمی را پر کرد", "hint": "پاسخ‌ها در متغیر و جدول ذخیره می‌شوند", "scopes": ["pv"]},
    {"k": "join",       "fa": "وقتی عضو جدید وارد گروه شد", "hint": "خوش‌آمد، کپچا و قفل ورود", "scopes": ["group"]},
    {"k": "leave",      "fa": "وقتی کسی گروه را ترک کرد", "hint": "پیام خروج و پاک‌سازی", "scopes": ["group"]},
    {"k": "channel_post","fa": "وقتی پستی در کانال ثبت شد", "hint": "کپی، دکمه یا یادداشت روی پست کانال", "scopes": ["channel"]},
    {"k": "pin",        "fa": "وقتی پیامی سنجاق شد", "hint": "پیام سنجاق را در گروه اعلام کن", "scopes": ["group"]},
    {"k": "pay",        "fa": "وقتی پرداخت با ستاره انجام شد", "hint": "بعد از پرداختِ موفق، پاداش یا دسترسی بده", "scopes": ["pv"]},
    {"k": "timer",      "fa": "وقتی زمان یک یادآور رسید", "hint": "با اکشن «یادآوری» ساخته می‌شود", "scopes": ["pv"]},
    {"k": "word",       "fa": "وقتی کلمه یا دستوری در گروه نوشت", "hint": "ماشه‌های گروه: پاسخ، امتیاز و بازی", "scopes": ["group"]},
    {"k": "bot_added",  "fa": "وقتی ربات به گروه/کانال اضافه شد", "hint": "خودت خبردار می‌شوی", "scopes": ["group", "channel"]},
    {"k": "reaction", "fa": "وقتی کسی به پیام واکنش داد", "hint": "ایموجی ماشه؛ پاسخ و امتیاز", "scopes": ["group"]},
    {"k": "mention",  "fa": "وقتی ربات منشن شد", "hint": "عامل هوشمند جواب می‌دهد", "scopes": ["group"]},
    {"k": "inline_query", "fa": "وقتی کسی جستجوی اینلاین کرد", "hint": "پاسخ از جدول داده", "scopes": ["pv"]},
    {"k": "webhook", "fa": "وقتی وب‌هوک بیرونی رسید", "hint": "رخداد سایت/اپ در جدول ذخیره می‌شود", "scopes": ["pv"]},
]

# ───────────────────────── «اگه» — شرط‌ها ─────────────────────────
CAPS_IF = [
    {"k": "==",       "fa": "برابر بود با"},
    {"k": "!=",       "fa": "برابر نبود با"},
    {"k": ">",        "fa": "بیشتر بود از"},
    {"k": ">=",       "fa": "بیشتر یا مساوی بود با"},
    {"k": "<",        "fa": "کمتر بود از"},
    {"k": "<=",       "fa": "کمتر یا مساوی بود با"},
    {"k": "contains", "fa": "شامل این متن بود"},
    {"k": "empty",    "fa": "هنوز پر نشده بود"},
    {"k": "filled",   "fa": "پر شده بود"},
    {"k": "sub",      "fa": "اشتراک دوره‌اش فعال بود", "hint": "اگر پلن را خالی بگذاری هر اشتراکی قبول است"},
]

# ───────────────────────── «آنگاه» — کارها (اکشن‌ها) ─────────────────────────
# op هایی که موتور واقعاً اجرا می‌کند + برچسب آدمیزاد.
CAPS_DO = [
    {"k": "set",     "fa": "یک اطلاعات را ذخیره کن", "hint": "مثل: اسم انتخابی کاربر", "args": ["var", "value"]},
    {"k": "add",     "fa": "امتیاز یا سکه اضافه/کم کن", "hint": "عدد بده یا بازه مثل 5-10", "args": ["var", "value"]},
    {"k": "clear",   "fa": "یک اطلاعات را پاک کن", "args": ["var"]},
    {"k": "random",  "fa": "عدد تصادفی بساز", "hint": "مثل 1-6", "args": ["var", "value"]},
    {"k": "pick",    "fa": "یکی از چند گزینه را تصادفی انتخاب کن", "hint": "گزینه‌ها با | جدا می‌شوند", "args": ["var", "value"]},
    {"k": "dice",    "fa": "تاس بینداز", "args": ["var", "emoji"]},
    {"k": "notify",  "fa": "به من خبر بده", "args": ["value"]},
    {"k": "remind",  "fa": "یادآوری زمان‌دار بساز", "args": ["minutes", "value", "goto"]},
    {"k": "db_add",  "fa": "یک ردیف به لیست اضافه کن", "args": ["table", "data"]},
    {"k": "db_get",  "fa": "از لیست بخوان", "args": ["table", "var"]},
    {"k": "db_set",  "fa": "یک ردیف لیست را ویرایش کن", "args": ["table", "data"]},
    {"k": "db_inc",  "fa": "یک عدد در لیست زیاد کن", "args": ["table", "var", "value"]},
    {"k": "db_del",  "fa": "از لیست حذف کن", "args": ["table"]},
    {"k": "fetch",   "fa": "از یک سایت عدد یا متن بگیر", "args": ["url", "var"]},
    {"k": "game_play","fa": "یک بازی را شروع کن", "hint": "بازی‌های مرکز بازی", "args": ["game"]},
    {"k": "calc",    "fa": "یک عبارت حسابی را حساب کن", "hint": "مثل {price} * {qty} یا (5+3)*2", "args": ["var", "value"]},
    {"k": "disc",    "fa": "کد تخفیف را بررسی و اعمال کن", "hint": "بعدش: {code_off} = قیمت بعد تخفیف، {code_save} = سود، {code_err} = دلیل رد", "args": ["var", "price"]},
    {"k": "sub_add", "fa": "اشتراک دوره‌ی کاربر را فعال/تمدید کن", "hint": "پلن مثل vip؛ بعدش شرط «اشتراک فعال بود» کار می‌کنه", "args": ["plan", "days", "var"]},
    {"k": "sub_del", "fa": "اشتراک دوره‌ی کاربر را لغو کن", "args": ["plan"]},
]

# ───────────────────────── انواع دکمه ─────────────────────────
CAPS_BTNS = [
    {"k": "goto",    "fa": "رفتن به یک بخش"},
    {"k": "channel", "fa": "کانال یا گروه تلگرام"},
    {"k": "url",     "fa": "لینک وب"},
    {"k": "alert",   "fa": "پیام پاپ‌آپ"},
    {"k": "copy",    "fa": "کپی کردن متن"},
    {"k": "share",   "fa": "اشتراک‌گذاری با لینک دعوت"},
    {"k": "pay",     "fa": "پرداخت با ستاره"},
    {"k": "app",     "fa": "باز کردن مینی‌اپ"},
    {"k": "contact", "fa": "درخواست شماره تماس"},
    {"k": "location", "fa": "درخواست موقعیت"},
    {"k": "inline",  "fa": "جستجوی اینلاین"},
]

# ───────────────────────── بلوک‌های مینی‌اپ ─────────────────────────
CAPS_BLOCKS = [
    {"k": "hero", "fa": "سربرگ"}, {"k": "text", "fa": "متن"}, {"k": "image", "fa": "تصویر"},
    {"k": "gallery", "fa": "گالری"}, {"k": "video", "fa": "ویدیو"}, {"k": "audio", "fa": "صدا"},
    {"k": "buttons", "fa": "دکمه‌ها"}, {"k": "cards", "fa": "کارت‌ها"}, {"k": "list", "fa": "فهرست داده"},
    {"k": "form", "fa": "فرم"}, {"k": "stat", "fa": "آماره"}, {"k": "board", "fa": "جدول برترین‌ها"},
    {"k": "faq", "fa": "سؤالات متداول"}, {"k": "banner", "fa": "اطلاعیه"}, {"k": "countdown", "fa": "شمارش معکوس"},
    {"k": "pay", "fa": "پرداخت"}, {"k": "ai", "fa": "گفتگوی هوشمند"}, {"k": "links", "fa": "لینک‌ها"},
    {"k": "divider", "fa": "جداکننده"}, {"k": "spacer", "fa": "فاصله"},
    {"k": "accordion", "fa": "آکاردئون"}, {"k": "tabs", "fa": "تب‌ها"}, {"k": "steps", "fa": "مراحل"},
    {"k": "timeline", "fa": "خط زمان"}, {"k": "quote", "fa": "نقل‌قول"}, {"k": "tags", "fa": "برچسب‌ها"},
    {"k": "table", "fa": "جدول"}, {"k": "copytext", "fa": "متن کپی‌شدنی"}, {"k": "slider", "fa": "اسلایدر تصویر"},
    {"k": "stories", "fa": "استوری"}, {"k": "logos", "fa": "لوگوها"}, {"k": "before_after", "fa": "قبل و بعد"},
    {"k": "quicklinks", "fa": "میان‌برها"}, {"k": "searchbar", "fa": "نوار جستجو"}, {"k": "product", "fa": "کارت محصول"},
    {"k": "catalog", "fa": "کاتالوگ با فیلتر"}, {"k": "cart", "fa": "سبد خرید"}, {"k": "pricing", "fa": "جدول قیمت"},
    {"k": "orders", "fa": "سفارش‌های من"}, {"k": "multiform", "fa": "فرم چندمرحله‌ای"}, {"k": "rating", "fa": "امتیاز ستاره‌ای"},
    {"k": "poll", "fa": "نظرسنجی"}, {"k": "chart", "fa": "نمودار"}, {"k": "progress", "fa": "نوار پیشرفت"},
    {"k": "calendar", "fa": "تقویم رویداد"}, {"k": "wheel", "fa": "گردونه‌ی شانس"}, {"k": "scratch", "fa": "کارت خراشیدنی"},
    {"k": "checkin", "fa": "چک‌این روزانه"}, {"k": "missions", "fa": "ماموریت‌ها"}, {"k": "badges", "fa": "نشان‌ها"},
    {"k": "xpbar", "fa": "نوار سطح و امتیاز"}, {"k": "invite", "fa": "دعوت دوستان"}, {"k": "profile", "fa": "پروفایل"},
    {"k": "reviews", "fa": "نظرات"}, {"k": "games", "fa": "مرکز بازی"}, {"k": "gamesboard", "fa": "رتبه‌ی بازی‌ها"},
    {"k": "wallet", "fa": "کیف سکه"}, {"k": "shopcoins", "fa": "فروشگاه سکه‌ای"},
]

# ───────────────────────── بازی‌های مرکز بازی (۹ بازی آماده) ─────────────────────────
CAPS_GAMES = [
    {"k": "quiz",   "fa": "کوییز",           "hint": "سؤال‌های چهارگزینه‌ای؛ بانک سؤال خودت یا آماده", "duel": True},
    {"k": "memory", "fa": "حافظه",           "hint": "جفت‌های یکسان را پیدا کن", "duel": False},
    {"k": "tap",    "fa": "لمس سریع",        "hint": "در ۱۰ ثانیه بیشترین ضربه را بزن", "duel": True},
    {"k": "wheel",  "fa": "گردونه",          "hint": "شانسی؛ جایزه از صندوق سکه", "duel": False},
    {"k": "word",   "fa": "حدس کلمه",        "hint": "کلمه‌ی جابجاشده را درست کن", "duel": False},
    {"k": "xo",     "fa": "دوئل XO",         "hint": "دونفره در گروه یا با حریف لابی", "duel": True},
    {"k": "typing", "fa": "سرعت تایپ",       "hint": "جمله را سریع و درست تایپ کن", "duel": True},
    {"k": "math",   "fa": "ریاضی سریع",      "hint": "محاسبه‌های ذهنی با زمان", "duel": True},
    {"k": "puzzle", "fa": "پازل اعداد",      "hint": "جدول ۳×۳ را مرتب کن", "duel": False},
]


def limit_of(plan_id, key):
    """سقف یک قابلیت برای یک پلن (پلن ناشناخته = free)"""
    return (LIMITS.get(key) or {}).get(plan_id if plan_id in ("free", "premium", "pro") else "free") or 200


# ───────────────────────── قرارداد قابلیت‌های موتور (BUILD 3.6.0) ─────────────────────────
# مرجع استاندارد و متمرکز توانایی‌های واقعی موتور. هر قابلیت با:
#   شناسه یکتا، وضعیت پشتیبانی، نسخهٔ معرفی، ورودی/خروجی، محدودیت، وابستگی،
#   قابلیت‌های مرتبط، API/اکشن‌های موردنیاز، تست پذیرش و وضعیت سازگاری.
#
# status:
#   ready       → ماژول کاتالوگ + تولیدکننده + تست پذیرش موجود است (ساخت خودکار ممکن)
#   engine_only → موتور توانایی اجرا را دارد اما ماژول آماده در کاتالوگ نیست (CATALOG_MISSING)
#   unsupported → موتور واقعاً پشتیبانی نمی‌کند (ENGINE_LIMIT) + نقشهٔ توسعه
#
# قانون: ثبت قابلیت به‌تنهایی به معنای آماده‌بودن نیست؛ ready فقط پس از پیاده‌سازی
# و موفقیت تست پذیرش ثبت می‌شود (tests/test_modules.py + engine_accept).

def _cap(cid, title, status, since, engine, inputs, outputs, limits, requires, related,
         module="", acceptance=(), compat="سازگار با کانفیگ‌های قبلی؛ بدون تغییر کار می‌کنند.",
         proposal=None):
    return {"id": cid, "title": title, "status": status, "since": since, "module": module,
            "engine": engine, "inputs": inputs, "outputs": outputs, "limits": limits,
            "requires": requires, "related": related, "acceptance": list(acceptance),
            "compat": compat, "proposal": proposal or {}}


_A = ["random", "set", "add"]          # اکشن‌های پرکاربرد بازی‌ها

CAPS_CONTRACT = {}


def _reg_contract(c):
    CAPS_CONTRACT[c["id"]] = c


# ── قابلیت‌های آمادهٔ کاتالوگ (ready) ──
_reg_contract(_cap("bot.start_menu", "منوی اصلی و نقطهٔ ورود", "ready", "3.6.0",
                  {"nodes": ["start"], "buttons": ["goto"], "commands": True},
                  {"name": "نام ربات", "welcome": "متن خوش‌آمد"},
                  {"nodes": ["start"]}, ["—"], ["—"], ["wallet", "daily"],
                  module="start_menu", acceptance=["tests/test_modules.py::start_menu"],
                  compat="تغییر متن شروع اثر جانبی روی سایر بخش‌ها ندارد."))
_reg_contract(_cap("wallet", "کیف پول و موجودی سکه", "ready", "3.5.0",
                  {"actions": ["set", "add"], "vars": ["coins"], "placeholders": ["{coins}"]},
                  {"coin": "نام واحد", "start_bonus": "عدد ≥ 0"},
                  {"vars": ["coins"]}, ["سقف ۴۰ متغیر در هر ربات"], ["—"],
                  ["daily", "referral", "game.dice", "game.guess", "game.coinbet", "game.wheel"],
                  module="wallet", acceptance=["tests/test_modules.py::wallet", "engine_accept._s_wallet"],
                  compat="متغیر coins مالکیت ماژول wallet است؛ سایر ماژول‌ها فقط می‌خوانند/می‌افزایند."))
_reg_contract(_cap("daily", "پاداش روزانه", "ready", "3.5.0",
                  {"actions": ["set", "add"], "conditions": ["==", "!="], "builtins": ["{date}"]},
                  {"amount": "عدد > 0"}, {"vars": ["last_daily"]},
                  ["فقط یک بار در هر روز تهران"], ["wallet"], ["wheel (بلیت روزانه)"],
                  module="daily", acceptance=["tests/test_modules.py::daily", "engine_accept._s_daily"]))
_reg_contract(_cap("game.dice", "بازی تاس", "ready", "3.6.0",
                  {"actions": _A, "conditions": [">", "<="]},
                  {"sides": "int 2..20"}, {"vars": ["dice_val", "dice_best"]},
                  ["دامنهٔ ۲ تا ۲۰"], ["wallet"], ["game.guess", "game.coinbet"],
                  module="dice", acceptance=["tests/test_modules.py::dice", "engine_accept._s_dice"]))
_reg_contract(_cap("game.guess", "حدس عدد", "ready", "3.6.0",
                  {"actions": _A, "conditions": ["==", "!="], "forms": ["fields", "save"]},
                  {"max_num": "int 2..100", "rounds": "int 1..20", "reward": "num > 0"},
                  {"vars": ["g_pick", "g_target", "g_score"]}, ["بیش از ۱۰ گزینه به فرم متنی می‌رود"],
                  ["wallet"], ["game.quiz"],
                  module="guess", acceptance=["tests/test_modules.py::guess", "engine_accept._s_guess"]))
_reg_contract(_cap("game.coinbet", "شرط‌بندی داخلی با سکه", "ready", "3.6.0",
                  {"actions": ["calc", "add", "random"], "conditions": ["<", ">=", "=="]},
                  {"amounts": "فهرست اعداد مثبت"}, {"vars": ["bet_amt", "bet_back", "bet_res"]},
                  ["شرط بیش از موجودی مجاز نیست؛ موجودی منفی نمی‌شود"], ["wallet"], ["game.dice"],
                  module="coinbet", acceptance=["tests/test_modules.py::coinbet", "engine_accept._s_coinbet"]))
_reg_contract(_cap("game.quiz", "کوییز و مسابقه", "ready", "3.5.0",
                  {"actions": ["add", "set"], "buttons": ["goto + do"]},
                  {"items": "سؤال + گزینه‌ها"}, {"vars": ["qscore"]},
                  ["گزینهٔ درست فقط یک بار امتیاز می‌دهد"], ["—"], ["game.guess", "leaderboard"],
                  module="quiz", acceptance=["tests/test_modules.py::quiz", "engine_accept._s_quiz"]))
_reg_contract(_cap("game.wheel", "گردونهٔ شانس", "ready", "3.5.0",
                  {"actions": ["random", "add", "calc", "set"], "conditions": ["==", ">=", "<"]},
                  {"prizes": "فهرست جایزه‌ها", "per_joins": "int", "per_refs": "int", "daily_ticket": "bool"},
                  {"vars": ["roll", "tk_used", "tk_left"]},
                  ["حداکثر ۱۲ خانه؛ هر چرخش یک بلیت"], ["wallet"], ["daily", "referral", "sponsor"],
                  module="wheel", acceptance=["tests/test_modules.py::wheel", "engine_accept._s_wheel"]))
_reg_contract(_cap("leaderboard", "رتبه‌بندی", "ready", "3.6.0",
                  {"nodes": ["board"], "db": ["uvars"]},
                  {"var": "coins|qscore|g_score|refs|puzzle", "top": "int 3..50"},
                  {"board_text": "متن جدول"}, ["کش ۴۵ ثانیه؛ اسکن BOARD_SCAN"],
                  ["—"], ["wallet", "referral", "game.quiz"],
                  module="leaderboard", acceptance=["tests/test_modules.py::leaderboard", "engine_accept._s_leaderboard"]))
_reg_contract(_cap("referral", "دعوت دوستان", "ready", "3.5.0",
                  {"events": ["on_ref"], "builtins": ["{refs}", "{ref_link}"]},
                  {"reward": "num > 0"}, {"on_ref": ["add coins"]},
                  ["پاداش فقط یک بار برای هر دعوت"], ["wallet"], ["leaderboard", "miner"],
                  module="referral", acceptance=["tests/test_modules.py::referral"]))
_reg_contract(_cap("economy.family", "اقتصاد کامل (ماینر/پازل/اسپانسر/فروش سکه)", "ready", "3.5.0",
                  {"actions": ["set", "add", "calc"], "join": ["channels gate"], "pay": ["stars"]},
                  {"packs, rewards, channels": "..."}, {"vars": ["joins", "puzzle", "tk_*"]},
                  ["ربات باید ادمین کانال‌های پاداش باشد"], ["wallet", "referral"], ["game.wheel"],
                  module="miner/sponsor/puzzle/coin_shop/member_orders",
                  acceptance=["tests/test_modules.py (اقتصاد)"]))
_reg_contract(_cap("shop.orders", "فروشگاه و ثبت سفارش", "ready", "3.5.0",
                  {"forms": ["fields", "save", "ticket"], "db": ["db_add"], "desk": ["تیکت مالک"]},
                  {"items": "محصولات"}, {"orders": "جدول سفارش‌ها"},
                  ["پرداخت فقط با ستارهٔ تلگرام یا تیکت تأیید دستی"], ["—"], ["support.tickets", "pay.stars"],
                  module="shop", acceptance=["tests/test_modules.py::shop"]))
_reg_contract(_cap("support.tickets", "پشتیبانی و تیکت", "ready", "3.5.0",
                  {"forms": ["ask", "ticket"], "desk": ["reply", "closed"]},
                  {"text": "متن بالای فرم"}, {"tickets": "تیکت‌ها"},
                  ["حداکثر MAX_STAFF پشتیبان"], ["—"], ["shop.orders"],
                  module="support", acceptance=["tests/test_modules.py::support"]))
_reg_contract(_cap("group.moderation", "مدیریت گروه و کانال", "ready", "3.5.0",
                  {"mod": ["captcha", "lock", "flood", "warn"], "commands": ["/ban /mute /warn /pin"]},
                  {"welcome": "text", "rules": "text"}, {"mod": "کانفیگ مدیریتی"},
                  ["ربات باید ادمین گروه باشد"], ["—"], ["join.gate"],
                  module="group_manager", acceptance=["tests/test_modules.py::test_group_manager", "engine_accept.run_acceptance:group_manager"]))
_reg_contract(_cap("group.settings.private", "تنظیمات خصوصی گروه", "ready", "3.6.2",
                  {"commands": ["/groups", "/group_settings"],
                   "telegram_api": ["getMe", "getChatMember"],
                   "storage": ["db.groups.mod_settings"]},
                  {"group": "شناسه گروهی که مدیر آن است", "settings": ["captcha", "flood", "lock", "report", "welcome", "rules"]},
                  {"private_menu": "انتخاب گروه و تنظیمات مستقل هر گروه"},
                  ["ربات باید ادمین گروه و کاربر باید مدیر همان گروه باشد"], ["—"], ["group.moderation"],
                  module="group_manager", acceptance=["tests/test_group_settings.py::test_group_settings_are_isolated",
                  "tests/test_group_settings.py::test_group_settings_authorization_contract",
                  "tests/test_group_settings.py::test_group_list_only_exposes_authorized_groups",
                  "tests/test_group_settings.py::test_group_settings_edit_accepts_mongo_utc_naive_timestamp",
                  "engine_accept.run_acceptance:group_manager"]))
_reg_contract(_cap("join.gate", "جوین اجباری", "ready", "3.5.0",
                  {"join": ["channels", "text"], "tg": ["getChatMember"]},
                  {"channels": "کانال‌ها"}, {"join": "دروازهٔ عضویت"},
                  ["ربات باید ادمین کانال‌ها باشد"], ["—"], ["group.moderation"],
                  module="forced_join", acceptance=["tests/test_modules.py::forced_join"]))
_reg_contract(_cap("ai.chat", "گفتگوی هوش مصنوعی", "ready", "3.5.0",
                  {"nodes": ["ai"], "api": ["AI_CHAT_MODEL"]},
                  {"prompt": "دستور دستیار", "daily": "سقف پیام"}, {"ai": "تنظیمات"},
                  ["وابسته به در دسترس بودن مدل"], ["—"], ["—"],
                  module="ai_assistant", acceptance=["tests/test_modules.py::ai_assistant"]))

# ── موتور دارد، ماژول کاتالوگ ندارد (engine_only → CATALOG_MISSING) ──
_reg_contract(_cap("games.center", "مرکز بازی ۹گانهٔ سمت سرور", "engine_only", "3.5.0",
                  {"actions": ["game_play"], "games": ["quiz", "memory", "tap", "wheel", "word", "xo", "typing", "math", "puzzle"]},
                  {"games.list": "بازی‌های فعال", "games.coin": "واحد"},
                  {"games": "کانفیگ مرکز بازی"}, ["ضدتقلب سمت سرور"], ["wallet"], ["game.*"],
                  acceptance=["ساخت دستی در استودیو با بلوک games"],
                  compat="فعال‌سازی با config.games.on در sanitize موجود است."))
_reg_contract(_cap("pay.stars", "پرداخت با ستارهٔ تلگرام", "engine_only", "3.5.0",
                  {"buttons": ["pay"], "events": ["pay"]},
                  {"stars": "قیمت"}, {"pay": "دکمهٔ پرداخت"},
                  ["فقط XTR؛ بدون درگاه بانکی"], ["—"], ["shop.orders"],
                  acceptance=["ساخت دستی دکمهٔ پرداخت در استودیو"]))
_reg_contract(_cap("db.tables", "جدول‌های داده", "engine_only", "3.5.0",
                  {"actions": ["db_add", "db_get", "db_set", "db_inc", "db_del"], "nodes": ["list"]},
                  {"table": "نام جدول"}, {"tables": "داده‌ها"},
                  ["سقف پلن‌محور LIMITS.tables"], ["—"], ["—"]))
_reg_contract(_cap("inline.search", "جستجوی اینلاین از جدول", "engine_only", "3.5.0",
                  {"events": ["inline_query"], "inline": ["table", "fields"]},
                  {"table": "جدول منبع"}, {"inline": "پاسخ اینلاین"},
                  ["فعال‌سازی inline در BotFather لازم است"], ["db.tables"], ["—"]))
_reg_contract(_cap("webhook.in", "وب‌هوک ورودی", "engine_only", "3.5.0",
                  {"webin": ["table", "notify"]}, {"url": "نشانی"}, {"رکورد رویداد"},
                  ["هر رخداد یک رکورد"], ["db.tables"], ["—"]))
_reg_contract(_cap("channelpost.flow", "پست کانال با تأیید مالک", "engine_only", "3.5.0",
                  {"channelpost": ["chat", "approve", "post /post"]},
                  {"chat": "کانال مقصد"}, {"channelpost": "کانفیگ"},
                  ["انتشار نهایی با دستور /post مالک"], ["—"], ["rss.feed"]))
_reg_contract(_cap("rss.feed", "خوراک RSS به کانال", "engine_only", "3.5.0",
                  {"rss": ["url", "chat", "mins"]}, {"url": "منبع"}, {"rss": "کانفیگ"},
                  ["بازهٔ حداقل ۱۰ دقیقه"], ["channelpost.flow"], ["—"]))
_reg_contract(_cap("discount.codes", "کدهای تخفیف", "engine_only", "3.5.0",
                  {"actions": ["disc"], "vars": ["code_off", "code_save", "code_err"]},
                  {"price": "مبلغ"}, {"vars": "نتیجهٔ بررسی"},
                  ["اعتبار و سقف مصرف در پنل مالک"], ["shop.orders"], ["—"]))
_reg_contract(_cap("subscriptions", "اشتراک دوره‌ای", "engine_only", "3.5.0",
                  {"actions": ["sub_add", "sub_del"], "conditions": ["sub"]},
                  {"plan": "نام پلن", "days": "مدت"}, {"subs": "اشتراک کاربر"},
                  ["بررسی sub_active در موتور"], ["—"], ["—"]))
_reg_contract(_cap("reminders", "یادآور زمان‌دار", "engine_only", "3.5.0",
                  {"actions": ["remind"], "events": ["timer"]},
                  {"minutes": "مدت", "goto": "بخش هدف"}, {"sched": "کار زمان‌بندی"},
                  ["حداکثر MAX_PENDING_REMIND همزمان"], ["—"], ["—"]))

# ── موتور پشتیبانی نمی‌کند (unsupported → ENGINE_LIMIT + نقشهٔ توسعه) ──
_reg_contract(_cap("pay.bank_gateway", "درگاه پرداخت بانکی", "unsupported", "—",
                  {"pay": ["فقط XTR ستارهٔ تلگرام"]}, {"amount": "مبلغ"}, {},
                  ["تأیید خودکار پرداخت بانکی وجود ندارد"], ["—"], ["pay.stars"],
                  proposal={
                      "reason": "موتور فقط Stars (XTR) تلگرام را با createInvoiceLink/answerPreCheckout پشتیبانی می‌کند؛ درگاه بانکی خارجی نیاز به callback امن، تأیید تراکنش و ledger تخصصی دارد.",
                      "missing": ["پل پرداخت مستقیم (PaymentProvider)", "دروازهٔ webhook بانک", "تأیید دو‌مرحله‌ای سفارش"],
                      "files": ["core.py (tg/createInvoiceLink)", "engine.py (act_pay)", "app.py (api_buy)"],
                      "api": "Payment gateway callback + transaction ledger",
                      "deps": ["wallet", "shop.orders"],
                      "impact": "ربات‌های فعلی ستاره‌ای دست‌نخورده می‌مانند؛ تغییر فقط افزودنی است.",
                      "plan": ["افزودن ماژول payments/bridge.py", "webhook /pay/cb با امضا", "تست پذیرش: سفارش تستی + refund"],
                      "acceptance": ["پرداخت آزمایشی موفق/ناموفق", "بازگشت وجه در شکست", " سازگاری Stars"],
                  }))
_reg_contract(_cap("game.realtime_multiplayer", "بازی آنلاین لحظه‌ای چندنفره", "unsupported", "—",
                  {"game_play": ["نوبتی محلی"]}, {"—": "—"}, {},
                  ["حالت دوئل XO محلی موجود است؛ هم‌زمانی زنده نه"], ["—"], ["games.center"],
                  proposal={
                      "reason": "موتور رویدادمحور تک‌کاربره است؛ حالت Real-time نیاز به session هم‌زمان، همگام‌سازی state و websocket دارد.",
                      "missing": ["Room/Session manager", "state sync", "پیام‌رسانی بین دو Env"],
                      "files": ["engine.py (act_game_play)", "games.py (duel loop)"],
                      "api": "Bot API هم‌زمان کافی نیست؛ نیاز به state سرور",
                      "deps": ["games.center", "wallet"],
                      "impact": "بدون تخریب؛ قابلیت جدید است.",
                      "plan": ["مدل room در db", "join/move/leave events", "تست دوئل زنده XO"],
                      "acceptance": ["دو کاربر آزمایشی هم‌زمان", "پایان بازی و اعطای جایزه یک‌بار"],
                  }))
_reg_contract(_cap("vision.photo_reading", "خواندن محتوای تصویر کاربر", "unsupported", "—",
                  {"forms": ["photo (فایل ذخیره می‌شود)"]}, {"—": "—"}, {},
                  ["عکس فقط ذخیره و برای مالک ارسال می‌شود؛ تحلیل محتوا نیست"], ["—"], ["ai.chat"],
                  proposal={
                      "reason": "موتور مدل چندوجهی ندارد و getFile فقط فایل را ذخیره می‌کند.",
                      "missing": ["VLM provider", "pipeline عکس → متن", "سقف هزینه"],
                      "files": ["engine.py (save_submission)", "ai.py (llm_post)"],
                      "api": "Vision API",
                      "deps": ["ai.chat"],
                      "impact": "قابلیت جدید؛ ربات‌های فعلی بی‌تغییر.",
                      "plan": ["اکشن vision_read", "صف پردازش", "تست تصویر نمونه"],
                      "acceptance": ["متن استخراج‌شده درست", "خطا بدون کسر توکن"],
                  }))
_reg_contract(_cap("wallet.cross_user", "انتقال/اهدای سکه بین کاربران و توسط مالک", "unsupported", "—",
                  {"add": ["فقط Env خود کاربر"]}, {"—": "—"}, {},
                  ["اکشن‌ها فقط روی کیف کاربرِ جاری کار می‌کنند"], ["wallet"], ["referral"],
                  proposal={
                      "reason": "run_actions روی Env تک‌کاربر اجرا می‌شود؛ تغییر موجودی کاربر دیگر نیاز به تراکنش امن بین دو uvars دارد.",
                      "missing": ["اکشن transfer(var, amount, to)", "قفل دو‌فازی تراکنش"],
                      "files": ["engine.py (run_actions)", "core.py (db.uvars)"],
                      "api": "—",
                      "deps": ["wallet", "leaderboard"],
                      "impact": "افزودنی؛ جلوگیری از منفی‌شدن موجودی الزامی است.",
                      "plan": ["اکشن transfer با کسر+افزودن اتمیک", "تست هم‌زمانی", "ثبت در ledger ربات"],
                      "acceptance": ["انتقال موفق", "موجودی منفی نمی‌شود", "دوباره‌شماری ندارد"],
                  }))
_reg_contract(_cap("channel.auto_post", "انتشار خودکار بدون تأیید مالک", "unsupported", "—",
                  {"channelpost": ["approve=True"]}, {"—": "—"}, {},
                  ["فعلاً انتشار نهایی با دستور /post مالک انجام می‌شود"], ["channelpost.flow"], ["—"],
                  proposal={
                      "reason": "جریان فعلی برای جلوگیری از انتشار محتوای تأییدنشده، دکمهٔ تأیید مالک دارد.",
                      "missing": ["سیاست سانسور/قوانین محتوا", "صف انتشار خودکار"],
                      "files": ["engine.py (_post_publish)"],
                      "api": "—",
                      "deps": ["channelpost.flow"],
                      "impact": "تنها فعال‌سازی opt-in؛ ربات‌های فعلی با approve می‌مانند.",
                      "plan": ["گزینهٔ approve=false در sanitize", "تست انتشار آزمایشی"],
                      "acceptance": ["پست بدون تأیید منتشر شود", "به‌روزرسانی کانفیگ قدیمی ایمن باشد"],
                  }))
_reg_contract(_cap("referral.commission", "پورسانت از خرید زیرمجموعه", "unsupported", "—",
                  {"on_ref": ["پاداش ثابت"]}, {"—": "—"}, {},
                  ["تغییر موجودی کاربری بر اثر عمل کاربر دیگر پشتیبانی نمی‌شود"], ["wallet"], ["referral"],
                  proposal={
                      "reason": "وابسته به wallet.cross_user؛ موتور تراکنش بین‌کاربری ندارد.",
                      "missing": ["رویداد purchase_referenced", "transfer"],
                      "files": ["engine.py (run_actions)", "growth.py"],
                      "api": "—",
                      "deps": ["wallet.cross_user"],
                      "impact": "افزودنی.",
                      "plan": ["پس از transfer؛ hook روی pay موفق", "درصد پورسانت پارامتر ماژول"],
                      "acceptance": ["پورسانت دقیق یک‌بار برای هر خرید"],
                  }))
_reg_contract(_cap("voice.video_call", "تماس صوتی/تصویری", "unsupported", "—",
                  {}, {"—": "—"}, {},
                  ["Bot API تماس برای ربات‌ها ارائه نمی‌شود"], ["—"], ["ai.chat"],
                  proposal={
                      "reason": "محدودیت پلتفرم تلگرام برای Bot API.",
                      "missing": ["—"],
                      "files": [],
                      "api": "Telegram Bot API فاقد تماس",
                      "deps": [],
                      "impact": "—",
                      "plan": ["در صورت عرضهٔ رسمی API، اکشن call اضافه شود"],
                      "acceptance": ["—"],
                  }))
_reg_contract(_cap("members.inject", "افزودن خودکار عضو به کانال دیگران", "unsupported", "—",
                  {}, {"—": "—"}, {},
                  ["ربات‌ساز تبادل عضو و لفت‌شمارسی دیگران را اجرا نمی‌کند"], ["—"], ["economy.family"],
                  proposal={
                      "reason": "افزودن کاربر به کانال دیگر با Bot API ممکن نیست و بررسی خروج از کانال دیگران نیز رویداد ندارد؛ خطوط قرمز اسپم.",
                      "missing": ["—"],
                      "files": [],
                      "api": "Telegram Bot API افزودن کاربر به chat دیگر را ندارد",
                      "deps": [],
                      "impact": "—",
                      "plan": ["جایگزین فعلی: سفارش عضو به‌صورت تیکت مالک (ماژول member_orders)"],
                      "acceptance": ["—"],
                  }))


def capability(cid):
    """قرارداد یک قابلیت + تطبیق زنده با کاتالوگ (آماده بودن ماژول)."""
    c = CAPS_CONTRACT.get(str(cid or ""))
    if not c:
        return {"id": str(cid or ""), "status": "unknown"}
    out = dict(c)
    if out.get("module"):
        try:
            import modules, modlib  # noqa: F401
            out["catalog_ready"] = all(m in modules.MODULES for m in out["module"].split("/"))
        except Exception:
            out["catalog_ready"] = False
    else:
        out["catalog_ready"] = False
    return out


def caps_contract_public():
    """فهرست قراردادها برای API و استودیو."""
    return [capability(k) for k in sorted(CAPS_CONTRACT)]


def caps_status_counts():
    """شمارش وضعیت‌ها برای پایش سلامت کاتالوگ."""
    out = {"ready": 0, "engine_only": 0, "unsupported": 0, "unknown": 0}
    for k in CAPS_CONTRACT:
        out[CAPS_CONTRACT[k]["status"]] = out.get(CAPS_CONTRACT[k]["status"], 0) + 1
    return out


def engine_roadmap_seed():
    """نقشهٔ توسعهٔ اولیه از موارد unsupported (برای گزارش ENGINE_LIMIT)."""
    out = []
    for k in CAPS_CONTRACT:
        c = CAPS_CONTRACT[k]
        if c["status"] == "unsupported" and c.get("proposal"):
            out.append({"capability": k, "title": c["title"], **c["proposal"]})
    return out


def caps_public():
    """آنچه رابط کاربری لازم دارد: رویدادها، شرط‌ها، کارها، دکمه‌ها، بلوک‌ها و بازی‌ها با برچسب فارسی"""
    return {"build": BUILD,
            "events": CAPS_EVENTS, "if": CAPS_IF, "do": CAPS_DO, "btns": CAPS_BTNS,
            "blocks": CAPS_BLOCKS, "games": CAPS_GAMES, "limits": LIMITS,
            "contract": caps_contract_public(), "status_counts": caps_status_counts()}


# پرامپت هوش مصنوعی از همین ساخته می‌شود تا AI قابلیت ناموجود نسازد.
def caps_ai_text():
    ev = "؛ ".join(f"{e['fa']} ({e['k']})" for e in CAPS_EVENTS)
    ac = "؛ ".join(f"{a['fa']} — op={a['k']}" + (f" با {' و '.join(a.get('args', []))}" if a.get("args") else "") for a in CAPS_DO)
    gm = "، ".join(g["k"] for g in CAPS_GAMES)
    return (f"رویدادهای موتور: {ev}\n"
            f"اکشن‌های موتور (فقط این‌ها): {ac}\n"
            f"بازی‌های آماده (کلیدها برای config.games.list): {gm}\n"
            f"اگر چیزی از این فهرست نبود، صادقانه بگو و نزدیک‌ترین قابلیت موجود را پیشنهاد بده.")
