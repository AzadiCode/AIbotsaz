# -*- coding: utf-8 -*-
"""
modlib.py — کتابخانهٔ ماژول‌های ربات‌ساز (هر ماژول یک قابلیت کامل و تست‌شده)

دسته‌ها: اقتصاد سکه (کیف، هدیه، دعوت، ماینر، گردونه، پازل، کانال اسپانسر، سفارش عضو، فروش سکه)،
فروشگاه و فرم، پشتیبانی و محتوا، گروه و کانال، مسابقه و نظرسنجی، هوش مصنوعی.
قانون: هیچ ماژولی چیزی را وعده نمی‌دهد که موتور (engine.py) واقعاً اجرا نکند.
الگوی امن: وقتی اکشنِ «ورود» نباید بدون شرط اجرا شود، از «گره‌ی بررسی» (route) و بعد «گره‌ی اجرا» استفاده می‌شود
(موتور اول do، بعد route را اجرا می‌کند؛ پس do فقط در گره‌ای که به آن رسیده‌ایم امن است).
"""

from modules import (Module, P, register, _btn, _group, _h, _clean_text, fmt, _num, BuildError)

_NOT = lambda var, val: {"var": var, "op": "!=", "value": str(val)}    # noqa: E731
_EQ = lambda var, val: {"var": var, "op": "==", "value": str(val)}     # noqa: E731
_GE = lambda var, val: {"var": var, "op": ">=", "value": str(val)}     # noqa: E731
_LT = lambda var, val: {"var": var, "op": "<", "value": str(val)}      # noqa: E731
_ADD = lambda var, val: {"op": "add", "var": var, "value": str(val)}   # noqa: E731
_SET = lambda var, val: {"op": "set", "var": var, "value": str(val)}   # noqa: E731


def _again(b, to, text="دوباره"):
    return [_btn(text, goto=to)]


# ═════════════════════════════ اقتصاد سکه ═════════════════════════════
def c_wallet(b, p):
    b.coin, b.coin_emoji = p["coin"], p["emoji"]
    b.var("coins", "0")
    b.node("wallet", f"<b>{b.E(b.coin_emoji)}کیف {_h(b.coin)}</b>\n\nموجودی تو: {{coins}} {_h(b.coin)}\nدعوت‌های موفق: {{refs}}",
           [b.back()], title="کیف پول")
    b.menu_add(10, f"{b.E(b.coin_emoji)}کیف {b.coin}", "wallet")
    b.cmd("wallet", "wallet")
    b.cmd("balance", "wallet")
    if p["start_bonus"] > 0:
        b.var("welcomed", "0")
        b.node("w_welcome", f"خوش اومدی {{name}}!\n{fmt(p['start_bonus'])} {_h(b.coin)} هدیهٔ ورود به کیفت اضافه شد.\nموجودی: {{coins}} {_h(b.coin)}",
               [[_btn("ادامه", goto="start")]], title="هدیه ورود",
               do=[_SET("welcomed", 1), _ADD("coins", fmt(p["start_bonus"]))])
        b.start_routes.append({"when": {"all": [_EQ("visits", 1), _NOT("welcomed", 1)]}, "goto": "w_welcome"})
        b.notes.append(f"با اولین ورود {fmt(p['start_bonus'])} {b.coin} هدیه داده می‌شود (فقط یک‌بار برای هر کاربر).")


def c_daily(b, p):
    b.var("coins", "0")
    b.var("last_daily", "")
    amount = fmt(p["amount"])
    extra = []
    if b.shared.get("daily_ticket"):
        b.var("tk_bonus", "0")
        extra = [_ADD("tk_bonus", 1)]
    b.node("daily", "هدیهٔ روزانه", [], title="هدیه روزانه",
           route=[{"when": _EQ("last_daily", "{date}"), "goto": "daily_done"},
                  {"when": _NOT("last_daily", "{date}"), "goto": "daily_get"}])
    b.node("daily_get", f"{b.E('🎁')}هدیهٔ امروزت: {amount} {_h(b.coin)}" + ("\nیک بلیت گردونه هم گرفتی." if extra else "") +
           f"\nموجودی: {{coins}} {_h(b.coin)}", [b.back()], title="هدیه امروز",
           do=[_SET("last_daily", "{date}"), _ADD("coins", amount)] + extra)
    b.node("daily_done", "امروز هدیه‌ات را گرفته‌ای. فردا دوباره بیا!", [b.back()], title="هدیه گرفته شد")
    b.menu_add(15, f"{b.E('🎁')}هدیهٔ روزانه", "daily")
    b.cmd("daily", "daily")


def c_referral(b, p):
    b.var("coins", "0")
    reward = fmt(p["reward"])
    b.node("invite", f"<b>{b.E('👥')}دعوت دوستان</b>\n\nهر کسی با لینک تو وارد ربات شود، {reward} {_h(b.coin)} می‌گیری.\n"
           "دعوت‌های موفق تو: {refs}\n\nلینک اختصاصی تو:\n{ref_link}",
           [[_btn("ارسال لینک دعوت", share=f"با این ربات {_h(b.coin)} جمع کن و جایزه بگیر!"), _btn("کپی لینک", copy="{ref_link}")],
            [_btn("برترین دعوت‌کننده‌ها", goto="invite_top")], b.back()], title="دعوت دوستان")
    b.node("invite_top", "برترین دعوت‌کننده‌ها:", [[_btn("دعوت دوستان", goto="invite")], b.back()], title="برترین‌ها",
           board={"var": "refs", "top": 10, "label": "دعوت‌های موفق"})
    b.on_ref = [_ADD("coins", reward)]
    b.ref_text = f"یک نفر با لینک تو وارد ربات شد! {reward} {b.coin} گرفتی. موجودی: {{coins}} {b.coin}"
    b.menu_add(40, f"{b.E('👥')}دعوت دوستان", "invite")
    b.cmd("invite", "invite")


def c_miner(b, p):
    b.var("coins", "0")
    b.var("last_mine", "")
    need, amount = p["need_refs"], fmt(p["daily"])
    b.node("miner", f"<b>{b.E('⛏')}ماینر {_h(b.coin)}</b>", [], title="ماینر",
           route=[{"when": _LT("refs", need), "goto": "miner_lock"},
                  {"when": _EQ("last_mine", "{date}"), "goto": "miner_done"},
                  {"when": _NOT("last_mine", "{date}"), "goto": "miner_get"}])
    lock_btns = [[_btn("دعوت دوستان", goto="invite")]] if "referral" in b.have_or_planned() else []
    b.node("miner_lock", f"ماینر وقتی فعال می‌شود که {need} نفر را دعوت کرده باشی.\nدعوت‌های تو: {{refs}} از {need}",
           lock_btns + [b.back()], title="ماینر قفل است")
    b.node("miner_get", f"{b.E('⛏')}ماینر امروز {amount} {_h(b.coin)} برایت استخراج کرد.\nموجودی: {{coins}} {_h(b.coin)}",
           [b.back()], title="برداشت ماینر", do=[_SET("last_mine", "{date}"), _ADD("coins", amount)])
    b.node("miner_done", "امروز برداشت کرده‌ای. فردا دوباره بیا تا ماینر دوباره سکه بدهد.", [b.back()], title="برداشت شده")
    b.menu_add(35, f"{b.E('⛏')}ماینر", "miner")


def c_wheel(b, p):
    b.var("coins", "0")
    prizes = p["prizes"]
    n = len(prizes)
    plans = b.shared.get("plans", {})
    b.var("tk_used", "0")
    b.var("tk_left", "0")
    b.var("roll", "0")
    if "puzzle" in prizes:
        b.var("puzzle", "0")
    parts, how = [], []
    if "sponsor" in plans and p["per_joins"] > 0:
        b.var("joins", "0")
        parts.append(f"{{joins}} // {p['per_joins']}")
        how.append(f"با هر {p['per_joins']} کانال که عضو شوی یک بلیت می‌گیری")
    if p["per_refs"] > 0:
        parts.append(f"{{refs}} // {p['per_refs']}")
        how.append(f"با هر {p['per_refs']} دعوت موفق یک بلیت می‌گیری")
    if b.shared.get("daily_ticket"):
        b.var("tk_bonus", "0")
        parts.append("{tk_bonus}")
        how.append("هر روز با «هدیهٔ روزانه» یک بلیت می‌گیری")
    free = not parts                       # هیچ منبع بلیتی نیست → هر روز یک چرخش رایگان
    if free:
        b.var("last_spin", "")
        how.append("هر روز یک چرخش رایگان داری")
    expr = (" + ".join(parts) if parts else "0") + " - {tk_used}"
    shown = "، ".join(("پازل 🧩" if x == "puzzle" else fmt(x)) for x in prizes)
    b.node("wheel", f"<b>{b.E('🎡')}گردونهٔ شانس</b>\n\n{n} خانه با احتمال برابر: {shown}\n" + "\n".join(how) + ".\nبرای چرخاندن یک بلیت لازم است." if not free
           else f"<b>{b.E('🎡')}گردونهٔ شانس</b>\n\n{n} خانه با احتمال برابر: {shown}\nهر روز یک چرخش رایگان داری.",
           [[_btn("بچرخان", goto="wheel_go")], b.back()], title="گردونه شانس")
    if free:
        b.node("wheel_go", "بررسی چرخش…", [], title="بررسی چرخش",
               route=[{"when": _EQ("last_spin", "{date}"), "goto": "wheel_none"}, {"when": _NOT("last_spin", "{date}"), "goto": "wheel_pre"}])
        pre_do = [_SET("last_spin", "{date}"), {"op": "random", "var": "roll", "value": f"1-{n}"}]
        none_txt = "چرخش رایگان امروزت را انجام داده‌ای. فردا دوباره بیا!"
    else:
        b.node("wheel_go", "بررسی بلیت…", [], title="بررسی بلیت", do=[{"op": "calc", "var": "tk_left", "value": expr}],
               route=[{"when": _LT("tk_left", 1), "goto": "wheel_none"}, {"when": _GE("tk_left", 1), "goto": "wheel_pre"}])
        pre_do = [_ADD("tk_used", 1), {"op": "random", "var": "roll", "value": f"1-{n}"}]
        none_txt = "بلیت نداری.\n" + "\n".join(how) + "."
    b.node("wheel_none", none_txt, [[_btn("گردونه", goto="wheel")], b.back()], title="بلیت ندارید")
    b.node("wheel_pre", "در حال چرخش…", [], title="چرخش گردونه", do=pre_do, route=[{"when": _GE("roll", 1), "goto": "wheel_spin"}])
    chain = ["wheel_spin"] + [f"wheel_s{i}" for i in range(2, 5)]
    for gi, nid in enumerate(chain):
        lo, hi = gi * 4 + 1, min(n, gi * 4 + 4)
        if lo > n:
            break
        rules = [{"when": _EQ("roll", i), "goto": f"wheel_r{i}"} for i in range(lo, hi + 1)]
        if hi < n:
            rules.append({"when": {"var": "roll", "op": ">", "value": str(hi)}, "goto": chain[gi + 1]})
        b.node(nid, "در حال چرخش…", [], title="نتیجه چرخش", route=rules)
    for i, pr in enumerate(prizes, 1):
        if pr == "puzzle":
            b.node(f"wheel_r{i}", f"{b.E('🧩')}یک قطعه پازل گرفتی!\nقطعه‌های پازل تو: {{puzzle}}", [_again(b, "wheel", "یک بار دیگر"), b.back()],
                   title="قطعه پازل", do=[_ADD("puzzle", 1)])
        else:
            b.node(f"wheel_r{i}", f"{b.E('🎉')}برنده شدی: {fmt(pr)} {_h(b.coin)}!\nموجودی: {{coins}} {_h(b.coin)}",
                   [_again(b, "wheel", "یک بار دیگر"), b.back()], title=f"جایزه {fmt(pr)}"[:30], do=[_ADD("coins", fmt(pr))])
    b.menu_add(30, f"{b.E('🎡')}گردونهٔ شانس", "wheel")


def c_puzzle(b, p):
    b.var("coins", "0")
    b.var("puzzle", "0")
    need, reward = p["need"], fmt(p["reward"])
    b.node("puzzle", f"<b>{b.E('🧩')}قطعه‌های پازل</b>\n\nقطعه‌های تو: {{puzzle}}\nبا {need} قطعه می‌توانی آن‌ها را به {reward} {_h(b.coin)} تبدیل کنی.",
           [[_btn("تبدیل قطعه‌ها به " + b.coin, goto="puz_check")], b.back()], title="پازل")
    b.node("puz_check", "بررسی قطعه‌ها…", [], title="بررسی پازل",
           route=[{"when": _LT("puzzle", need), "goto": "puz_no"}, {"when": _GE("puzzle", need), "goto": "puz_do"}])
    b.node("puz_no", f"برای تبدیل {need} قطعه لازم است. قطعه‌های تو: {{puzzle}}", [[_btn("پازل", goto="puzzle")], b.back()], title="قطعه کم است")
    b.node("puz_do", f"{b.E('🎉')}{need} قطعه به {reward} {_h(b.coin)} تبدیل شد.\nموجودی: {{coins}} {_h(b.coin)}",
           [[_btn("پازل", goto="puzzle")], b.back()], title="تبدیل شد", do=[_ADD("puzzle", -need), _ADD("coins", reward)])
    b.menu_add(45, f"{b.E('🧩')}پازل", "puzzle")


def c_sponsor(b, p):
    b.var("coins", "0")
    reward = fmt(p["reward"])
    chans = p["channels"]
    b.var("joins", "0")
    per_page = 5
    pages = [chans[i:i + per_page] for i in range(0, len(chans), per_page)]
    for pi, page in enumerate(pages):
        nid = "earn" if pi == 0 else f"earn{pi + 1}"
        rows = []
        for ch in page:
            i = chans.index(ch) + 1
            rows.append([_btn(f"عضویت در @{ch}"[:40], url=f"https://t.me/{ch}"), _btn("دریافت پاداش", goto=f"earn_c{i}")])
        if pi + 1 < len(pages):
            rows.append([_btn("کانال‌های بیشتر", goto=f"earn{pi + 2}")])
        rows.append(b.back())
        head = f"<b>{b.E('📣')}کسب {_h(b.coin)} با عضویت</b>\n\nدر کانال زیر عضو شو و بعد «دریافت پاداش» را بزن. برای هر کانال {reward} {_h(b.coin)} می‌گیری." \
            if pi == 0 else "کانال‌های بیشتر:"
        b.node(nid, head, rows, title="کسب سکه با عضویت")
    for i, ch in enumerate(chans, 1):
        flag = b.var(f"claimed_{i}", "0")
        b.node(f"earn_c{i}", "بررسی عضویت…", [], title=f"بررسی @{ch}"[:30],
               join={"channels": [ch], "text": f"اول در کانال @{ch} عضو شو، بعد دوباره «دریافت پاداش» را بزن."},
               route=[{"when": _EQ(flag, 1), "goto": f"earn_c{i}_d"}, {"when": _NOT(flag, 1), "goto": f"earn_c{i}_ok"}])
        b.node(f"earn_c{i}_ok", f"{b.E('✅')}عضویت در @{ch} تأیید شد. {reward} {_h(b.coin)} گرفتی.\nموجودی: {{coins}} {_h(b.coin)}",
               [[_btn("کانال‌ها", goto="earn")], b.back()], title="پاداش عضویت",
               do=[_SET(flag, 1), _ADD("coins", reward), _ADD("joins", 1)])
        b.node(f"earn_c{i}_d", f"پاداش @{ch} را قبلاً گرفته‌ای.", [[_btn("کانال‌ها", goto="earn")], b.back()], title="قبلاً گرفتی")
    b.menu_add(20, f"{b.E('📣')}کسب {b.coin}", "earn")
    b.notes.append("ربات باید در همهٔ کانال‌های پاداش «ادمین» باشد تا عضویت را بررسی کند؛ فهرست کانال‌ها را از ویرایش دستی عوض کن.")


def c_forced(b, p):
    b.join = {"channels": p["channels"], "text": p["text"]}
    b.notes.append("ربات باید در کانال‌های جوین اجباری ادمین باشد؛ بدون آن عضویت بررسی نمی‌شود.")


def c_member_orders(b, p):
    b.var("coins", "0")
    b.var("ord_link", "")
    packs = p["packs"]
    rows, btns = [], []
    for i, (qty, price) in enumerate(packs, 1):
        pass
    for i, row in enumerate(packs, 1):
        qty, price = int(row[0]), _num(row[1])
        lab = f"{qty} عضو ({fmt(price)} {b.coin})"
        btns.append(_btn(lab, goto=f"mo_p{i}", when=_GE("coins", fmt(price))))
        btns.append(_btn(lab, alert=f"موجودی کافی نیست؛ برای این بسته {fmt(price)} {b.coin} لازم است.", when=_LT("coins", fmt(price))))
        b.node(f"mo_p{i}", f"سفارش {qty} عضو برای کانال یا گروه تو.\nهزینه: {fmt(price)} {_h(b.coin)}.\n\n"
               "قبل از ثبت: ربات را در کانال/گروه خودت ادمین کن و دسترسی «دعوت کاربران با لینک» را بده.", [], title=f"سفارش {qty} عضو",
               fields=["لینک کانال یا گروه (برای خصوصی: لینک دعوت)"], save=["ord_link"], ticket=True, tag="سفارش عضو",
               done=f"سفارش ثبت شد (تیکت #{{ticket_no}}). تا تکمیل سفارش، وضعیت را در «سفارش‌های من» ببین.", next="mo_my",
               do=[_ADD("coins", fmt(-price)),
                   {"op": "db_add", "table": "morders", "data": {"link": "{ord_link}", "qty": str(qty), "status": "ثبت شد"}}])
    rows = _group(btns, 2)
    b.node("mo_home", f"<b>{b.E('📥')}سفارش عضو</b>\n\nبا {_h(b.coin)} برای کانال یا گروه خودت عضو سفارش بده.\nموجودی تو: {{coins}} {_h(b.coin)}",
           rows + [[_btn("سفارش‌های من", goto="mo_my")], b.back()], title="سفارش عضو")
    b.node("mo_my", "سفارش‌های من:", [[_btn("سفارش عضو", goto="mo_home")], b.back()], title="سفارش‌های من",
           list={"table": "morders", "scope": "my", "limit": 5, "line": "#{n} · {link} · {qty} عضو · {status}", "empty": "هنوز سفارشی ثبت نکرده‌ای."})
    b.menu_add(50, f"{b.E('📥')}سفارش عضو", "mo_home")
    b.notes.append("سفارش عضو به‌صورت تیکت برای مالک ثبت می‌شود و مالک انجام آن را پیگیری می‌کند (موتور فعلی افزودن خودکار عضو به کانال‌های دیگران را ندارد).")
    b.desk.setdefault("closed", "سفارش شما تکمیل و بسته شد. ممنون!")


def c_coin_shop(b, p):
    b.var("coins", "0")
    b.var("cs_qty", "0")
    pack, price = p["pack"], _num(p["price_toman"])
    lines = [f"<b>{b.E('🛒')}خرید {_h(b.coin)}</b>\n", f"هر {pack} {_h(b.coin)}: {int(price):,} تومان".replace(",", "٬")]
    btns = []
    if b.payments:
        stars = max(1, int(p["stars"]))
        lines.append(f"پرداخت آنی با ستارهٔ تلگرام: {pack} {_h(b.coin)} = {stars} ستاره")
        btns.append([_btn(f"خرید {pack} {b.coin} ({stars} ستاره)"[:40],
                          pay={"stars": stars, "title": f"{pack} {b.coin}"[:32], "desc": f"افزودن {pack} {b.coin} به کیف شما"[:120],
                               "text": f"پرداخت انجام شد؛ {pack} {b.coin} به کیفت اضافه شد.", "goto": "wallet" if "wallet" in b.nodes else "start"},
                          do=[_ADD("coins", pack)])])
    lines.append("\nپرداخت کارت‌به‌کارت: مبلغ را واریز کن و «ثبت رسید» را بزن؛ بعد از بررسی مالک، " + _h(b.coin) + " به کیفت اضافه می‌شود.")
    lines.append("شماره کارت: [شماره کارت مالک را از ویرایش دستی بگذار]")
    btns.append([_btn("ثبت رسید پرداخت", goto="cs_card")])
    b.node("cs_home", "\n".join(lines), btns + [b.back()], title="خرید سکه")
    b.node("cs_card", f"چند {_h(b.coin)} خریدی و رسید پرداخت را بفرست:", [], title="ثبت رسید",
           fields=[f"تعداد {b.coin} که خریده‌ای (عدد)", "عکس رسید پرداخت"], types=["number", "photo"], save=["cs_qty", ""],
           ticket=True, tag="خرید سکه", done="رسید ثبت شد (تیکت #{ticket_no}). بعد از بررسی، موجودی‌ات اضافه می‌شود.", next="start")
    b.menu_add(55, f"{b.E('🛒')}خرید {b.coin}", "cs_home")
    b.notes.append("شمارهٔ کارت را از ویرایش دستی در بخش «خرید سکه» بگذار. اضافه‌کردن دستی سکه به کاربر در موتور فعلی نیست؛ پرداخت با ستاره خودکار است.")


def c_owner(b, p):
    rows = []
    lines = [f"<b>{b.E('🛠')}پنل مدیریت</b>\n", "• تیکت‌ها و سفارش‌ها: دستور /tickets"]
    if b.payments:
        lines.append("• پرداخت‌ها: /payments و برگشت پرداخت: /refund")
    earners = {"referral", "daily", "miner", "sponsor", "wheel", "puzzle", "wallet"} & set(b.have)
    if b.payments and "coin_shop" in b.have:
        earners.add("coin_shop")
    if "coins" in b.vars and (earners - {"wallet"}):
        rows.append([_btn("برترین‌ها", goto="own_top")])
        b.node("own_top", f"برترین کاربران بر اساس {_h(b.coin)}:", [[_btn("پنل مدیریت", goto="owner")], b.back()], title="برترین‌ها",
               board={"var": "coins", "top": 10, "label": f"بیشترین {b.coin}"})
    rows.append([_btn("باز کردن مینی‌اپ مدیریت", app="1")])
    b.node("owner", "\n".join(lines), rows + [b.back()], title="پنل مدیریت",
           route=[{"when": _NOT("is_admin", 1), "goto": "start"}])
    b.menu_add(99, f"{b.E('🛠')}پنل مدیریت", "owner", when=_EQ("is_admin", 1))
    b.cmd("panel", "owner")


# ───────────────────────── تعریف و ثبت ─────────────────────────
def _reg():
    register(Module("wallet", "کیف سکه", "واحد پول ربات با موجودی هر کاربر و هدیهٔ اولین ورود", c_wallet,
                    [P("coin", "نام واحد پول", "text", "سکه", max=20), P("emoji", "ایموجی واحد پول", "text", "💰", max=4),
                     P("start_bonus", "هدیهٔ اولین ورود", "num", 0, min=0, max=100000)],
                    [(r"(واحد پول|کیف پول|سکه|الماس|امتیاز|اعتبار)", 0.6)], prio=10, cat="اقتصاد سکه"))
    register(Module("daily", "هدیهٔ روزانه", "هر کاربر روزی یک بار هدیه می‌گیرد", c_daily,
                    [P("amount", "مقدار هدیه", "num", 1, min=0.01, max=100000)],
                    [(r"(هدیه|جایزه|پاداش) روزانه|چک ?این|daily (bonus|reward)", 1.0)], ("wallet",), 15, "اقتصاد سکه"))
    register(Module("referral", "دعوت دوستان", "لینک دعوت اختصاصی، پاداش دعوت و جدول برترین دعوت‌کننده‌ها", c_referral,
                    [P("reward", "پاداش هر دعوت", "num", 5, min=0.01, max=100000)],
                    [(r"رفرال|زیر ?مجموعه|لینک دعوت|دعوت (کرد|کنه|کند|کنن|کنند|دوست)|invite|referral", 1.0)], ("wallet",), 40, "اقتصاد سکه"))
    register(Module("miner", "ماینر روزانه", "با دعوت تعداد مشخصی نفر، هر روز مقداری سکه می‌گیرد", c_miner,
                    [P("need_refs", "تعداد دعوت لازم", "int", 5, min=1, max=1000), P("daily", "مقدار روزانه", "num", 1, min=0.01, max=100000)],
                    [(r"ماینر|miner", 1.5)], ("wallet", "referral"), 35, "اقتصاد سکه"))
    register(Module("wheel", "گردونهٔ شانس", "چرخش با احتمال برابر و جایزه‌های دلخواه (سکه یا قطعهٔ پازل)", c_wheel,
                    [P("prizes", "جایزه‌های گردونه", "prizes", [1, 2, 3, 5, 10, 20], n=12),
                     P("per_joins", "یک بلیت به‌ازای هر چند عضویت (۰=خاموش)", "int", 0, min=0, max=1000),
                     P("per_refs", "یک بلیت به‌ازای هر چند دعوت (۰=خاموش)", "int", 0, min=0, max=1000),
                     P("daily_ticket", "هر روز یک بلیت رایگان", "bool", False)],
                    [(r"گردونه|چرخ شانس|wheel of|lucky wheel|fortune wheel", 1.5)], ("wallet",), 30, "اقتصاد سکه"))
    register(Module("puzzle", "تبدیل قطعهٔ پازل", "تبدیل چند قطعهٔ پازل به سکه (جایگزین پورسانت)", c_puzzle,
                    [P("need", "تعداد قطعه", "int", 5, min=1, max=1000), P("reward", "پاداش (سکه)", "num", 10, min=0.01, max=100000)],
                    [(r"پازل", 1.0)], ("wallet", "wheel"), 45, "اقتصاد سکه"))
    register(Module("sponsor", "کسب سکه با عضویت در کانال", "عضویت در کانال‌های تعیین‌شده با بررسی واقعی عضویت و پاداش یک‌باره", c_sponsor,
                    [P("reward", "پاداش هر کانال", "num", 1, min=0.01, max=100000),
                     P("channels", "کانال‌ها (بدون @)", "channels", ["your_channel"], n=10)],
                    [(r"(جوین|عضو) (شی|بشی|شد|شو|بشه|شدن|شوند|بشن)|جوین (کنی|کند)|عضو.{0,15}کانال.{0,20}(سکه|امتیاز)|سکه.{0,30}(جوین|عضو)", 1.0)],
                    ("wallet",), 20, "اقتصاد سکه"))
    register(Module("forced_join", "جوین اجباری", "کاربر قبل از استفادهٔ ربات باید در کانال‌ها عضو شود", c_forced,
                    [P("channels", "کانال‌ها (بدون @)", "channels", ["your_channel"], n=5),
                     P("text", "پیام درخواست عضویت", "text", "برای استفاده از ربات اول در کانال‌های زیر عضو شو.", max=200)],
                    [(r"(جوین|عضویت) اجباری|forced join|اجباری.{0,20}(جوین|عضو)", 2.0)], (), 5, "اقتصاد سکه"))
    register(Module("member_orders", "سفارش عضو", "کاربر با سکه برای کانال/گروه خودش عضو سفارش می‌دهد (تیکت برای مالک)", c_member_orders,
                    [P("packs", "بسته‌ها (تعداد عضو، قیمت)", "list", [[5, 5], [10, 10], [25, 25], [50, 50]], n=6)],
                    [(r"سفارش (عضو|ممبر)|(ممبر|عضو) ?گیر|عضو بگیر|ممبر بگیر|(عضو|ممبر) (سفارش|بخر)", 1.5)], ("wallet",), 50, "اقتصاد سکه"))
    register(Module("coin_shop", "فروش سکه", "فروش سکه با ستارهٔ تلگرام یا رسید کارت‌به‌کارت (تأیید دستی)", c_coin_shop,
                    [P("pack", "تعداد سکه در هر بسته", "int", 100, min=1, max=1000000), P("price_toman", "قیمت هر بسته (تومان)", "num", 40000, min=1, max=1e9),
                     P("stars", "قیمت هر بسته (ستاره)", "int", 50, min=1, max=10000)],
                    [(r"(بفروش|فروش|خرید|بخر)\S* ?(\S+ ){0,3}(سکه|الماس|امتیاز)|(سکه|الماس).{0,25}(بفروش|فروش|تومن|تومان)", 1.5)], ("wallet",), 55, "اقتصاد سکه"))
    register(Module("owner_panel", "پنل مالک", "منوی ویژهٔ مالک و مدیران (تیکت، برترین‌ها، مینی‌اپ)", c_owner, [],
                    [(r"مالک|صاحب ربات|پنل (مدیر|مالک|ادمین)|کنترل (همه|کل)|بازدهی|آمار ربات", 1.0)], (), 99, "مدیریت"))


_reg()


# ═════════════════════════════ ماژول‌های عمومی ═════════════════════════════
def c_support(b, p):
    b.node("support", f"<b>{b.E('💬')}پشتیبانی</b>\n\n{_h(p['text'], 300)}", [], title="پشتیبانی", fields=["پیام شما"], save=[""],
           ticket=True, tag="پشتیبانی", done="پیامت ثبت شد (تیکت #{ticket_no}). به‌زودی پاسخ می‌دهیم.", next="start")
    b.menu_add(60, f"{b.E('💬')}پشتیبانی", "support")
    b.cmd("support", "support")


def c_faq(b, p):
    items = p["items"]
    rows = []
    for i, it in enumerate(items, 1):
        b.node(f"faq_{i}", f"<b>{_h(it['q'], 100)}</b>\n\n{_h(it['a'], 800)}", [[_btn("سؤال‌ها", goto="faq")], b.back()], title=f"سؤال {i}")
        rows.append([_btn(it["q"][:40], goto=f"faq_{i}")])
    b.node("faq", f"<b>{b.E('❓')}سؤال‌های پرتکرار</b>", rows[:6] + [b.back()], title="سؤال‌های پرتکرار")
    b.menu_add(70, f"{b.E('❓')}سؤال‌های پرتکرار", "faq")
    b.cmd("faq", "faq")


def c_about(b, p):
    b.node("about", f"<b>{b.E('ℹ️')}دربارهٔ ما</b>\n\n{_h(p['text'], 800)}", [b.back()], title="درباره ما")
    b.menu_add(80, f"{b.E('ℹ️')}دربارهٔ ما", "about")
    b.cmd("about", "about")


def c_links(b, p):
    rows = []
    for it in p["items"]:
        u = it.get("url", "")
        if u.startswith("@"):
            u = "https://t.me/" + u[1:]
        rows.append([_btn(it["text"], url=u)])
    b.node("links", f"<b>{b.E('🔗')}لینک‌ها</b>", rows[:6] + [b.back()], title="لینک‌ها")
    b.menu_add(75, f"{b.E('🔗')}لینک‌ها", "links")


def c_shop(b, p):
    items = p["items"]
    rows = []
    b.var("o_note", "")
    for i, it in enumerate(items, 1):
        price = _num(it.get("price"), 0)
        pt = f"\nقیمت: {_h(it['price'], 30)}" if it.get("price") else ""
        b.node(f"shop_{i}", f"<b>{_h(it['name'], 60)}</b>\n{_h(it.get('desc', ''), 500)}{pt}",
               [[_btn("ثبت سفارش", goto=f"shop_o{i}")], [_btn("محصولات", goto="shop")], b.back()], title=_clean_text(it["name"], 30))
        b.node(f"shop_o{i}", f"سفارش «{_h(it['name'], 60)}»", [], title="ثبت سفارش", fields=["نام و شمارهٔ تماس", "آدرس یا توضیحات سفارش"],
               save=["", "o_note"], ticket=True, tag="سفارش", done="سفارش ثبت شد (تیکت #{ticket_no}). به‌زودی تماس می‌گیریم.", next="start",
               do=[{"op": "db_add", "table": "orders", "data": {"item": _clean_text(it["name"], 60), "note": "{o_note}", "status": "ثبت شد"}}])
        rows.append([_btn(it["name"][:40], goto=f"shop_{i}")])
    b.node("shop", f"<b>{b.E('🛍')}محصولات</b>", rows[:6] + [[_btn("سفارش‌های من", goto="shop_my")], b.back()], title="محصولات")
    b.node("shop_my", "سفارش‌های من:", [[_btn("محصولات", goto="shop")], b.back()], title="سفارش‌های من",
           list={"table": "orders", "scope": "my", "limit": 5, "line": "{item} · {status}", "empty": "هنوز سفارشی نداری."})
    b.menu_add(25, f"{b.E('🛍')}محصولات", "shop")
    b.desk.setdefault("closed", "سفارش شما بسته شد. ممنون!")


def c_ai(b, p):
    b.node("assistant", f"<b>{b.E('🤖')}دستیار هوشمند</b>\n\nهر سؤالی داری بپرس.", [b.back()], title="دستیار هوشمند",
           ai={"prompt": p["prompt"], "daily": p["daily"], "memory": 3})
    b.menu_add(65, f"{b.E('🤖')}دستیار هوشمند", "assistant")


def c_quiz(b, p):
    items = p["items"]
    b.var("qscore", "0")
    for i, it in enumerate(items, 1):
        opts = it.get("opts") or []
        if len(opts) < 2:
            continue
        nxt = f"quiz_{i + 1}" if i < len(items) else "quiz_end"
        btns = []
        for j, o in enumerate(opts):
            if j == 0:
                btns.append(_btn(o, goto=nxt, do=[_ADD("qscore", 1)]))
            else:
                btns.append(_btn(o, goto=nxt))
        # گزینهٔ درست همیشه اولی است؛ برای جلوگیری از ثابت‌بودن جای آن، ردیف‌ها را بر اساس شماره‌ی سؤال می‌چرخانیم
        k = i % len(btns)
        btns = btns[k:] + btns[:k]
        nid = "quiz" if i == 1 else f"quiz_{i}"
        b.node(nid, f"<b>سؤال {i} از {len(items)}</b>\n\n{_h(it['q'], 300)}", _group(btns, 1), title=f"سؤال {i}")
    b.node("quiz_end", f"{b.E('🏁')}مسابقه تمام شد!\nامتیاز تو: {{qscore}} از {len(items)}", [[_btn("دوباره", goto="quiz_again")], b.back()], title="نتیجه")
    b.node("quiz_again", "شروع دوباره…", [], title="شروع دوباره", do=[_SET("qscore", 0)], route=[{"when": {"var": "qscore", "op": "==", "value": "0"}, "goto": "quiz"}])
    b.menu_add(85, f"{b.E('🏆')}مسابقه", "quiz")


def c_group(b, p):
    b.mod = {"welcome": _clean_text(p["welcome"], 300), "welcome_del": 60, "rules": _clean_text(p["rules"], 500),
             "captcha": {"on": True, "mins": 3}, "lock": ["link", "forward", "via_bot"], "flood": {"n": 6, "secs": 8},
             "action": "warn", "warns": {"max": 3, "then": "mute", "mins": 60}, "clean": ["join", "leave"], "report": True}
    b.node("gm_help", f"<b>{b.E('🛡')}مدیریت گروه</b>\n\n۱) ربات را به گروه اضافه کن\n۲) آن را «ادمین» کن (حذف پیام، محدودکردن کاربر، سنجاق)\n"
           "قفل لینک و فوروارد، کپچا، ضد اسپم و اخطار خودکار فعال می‌شود.\nدستورها: /ban /mute /warn /del /pin /rules", [b.back()], title="راهنمای گروه")
    b.menu_add(5, f"{b.E('🛡')}مدیریت گروه", "gm_help")
    b.notes.append("ربات را در گروه ادمین کن تا قفل‌ها و کپچا کار کنند.")


def c_ads(b, p):
    for v in ("ad_title", "ad_desc", "ad_price", "ad_contact"):
        b.var(v, "")
    b.node("ad_new", f"<b>{b.E('📝')}ثبت آگهی</b>\n\nاطلاعات آگهی را مرحله‌به‌مرحله بفرست.", [], title="ثبت آگهی",
           fields=["نام کالا", "توضیحات کالا", "قیمت (به تومان)", "عکس کالا", "اطلاعات تماس (شماره یا آیدی تلگرام)"],
           types=["text", "text", "text", "photo", "text"], save=["ad_title", "ad_desc", "ad_price", "", "ad_contact"],
           ticket=True, tag="آگهی جدید", done="آگهی ثبت شد (تیکت #{ticket_no}) و در فهرست آگهی‌ها قرار گرفت.", next="ad_all",
           do=[{"op": "db_add", "table": "ads", "data": {"title": "{ad_title}", "price": "{ad_price}", "contact": "{ad_contact}", "desc": "{ad_desc}"}}])
    line = "{title} · {price} تومان · تماس: {contact}"
    b.node("ad_all", f"<b>{b.E('🛍')}آگهی‌های تازه</b>", [[_btn("ثبت آگهی", goto="ad_new")], [_btn("آگهی‌های من", goto="ad_my")], b.back()], title="آگهی‌ها",
           list={"table": "ads", "scope": "all", "limit": 8, "line": line, "empty": "هنوز آگهی‌ای ثبت نشده؛ اولین نفر باش!"})
    b.node("ad_my", "آگهی‌های من:", [[_btn("ثبت آگهی", goto="ad_new")], [_btn("همهٔ آگهی‌ها", goto="ad_all")], b.back()], title="آگهی‌های من",
           list={"table": "ads", "scope": "my", "limit": 8, "line": line, "empty": "هنوز آگهی‌ای نداری."})
    b.menu_add(10, f"{b.E('📝')}ثبت آگهی", "ad_new")
    b.menu_add(11, f"{b.E('🛍')}دیدن آگهی‌ها", "ad_all")
    b.notes.append("آگهی‌ها داخل ربات نمایش داده می‌شوند و همراه عکس برای مالک می‌آیند؛ انتشار خودکار در کانال را موتور ندارد، مالک با پاسخ به پیام و دستور /post آن را در کانال می‌گذارد.")


def _reg2():
    register(Module("ads", "آگهی و نیازمندی", "ثبت آگهی با فرم (نام، توضیح، قیمت، عکس، تماس)، فهرست عمومی آگهی‌ها و آگهی‌های من", c_ads, [],
                    [(r"آگهی|نیازمندی|خرید و فروش (کالا)?|فروش کالا", 1.2)], (), 10, "فروش"))
    register(Module("support", "پشتیبانی", "فرم پیام به مالک (تیکت) و پاسخ از داخل ربات", c_support, [P("text", "متن بالای فرم", "text", "پیامت را بنویس تا تیم پشتیبانی پاسخ بدهد.", max=300)],
                    [(r"پشتیبانی|تیکت|support|ارتباط با (ما|مدیر|ادمین)", 1.0)], (), 60, "عمومی"))
    register(Module("faq", "سؤال‌های پرتکرار", "فهرست پرسش و پاسخ", c_faq,
                    [P("items", "پرسش و پاسخ", "items", [{"q": "این ربات چه کاری می‌کند؟", "a": "اینجا می‌توانی از امکانات ربات استفاده کنی."}], keys={"q": 100, "a": 800}, need=["q", "a"], n=6)],
                    [(r"سوالات متداول|سؤال(ات|های) (متداول|پرتکرار)|faq|پرسش و پاسخ", 1.0)], (), 70, "عمومی"))
    register(Module("about", "دربارهٔ ما", "صفحهٔ معرفی", c_about, [P("text", "متن معرفی", "text", "این ربات برای خدمات‌رسانی سریع ساخته شده است.", max=800)],
                    [(r"درباره (ما|ی ما)|معرفی (ما|مجموعه|کسب)|about us", 1.0)], (), 80, "عمومی"))
    register(Module("links", "لینک‌ها", "دکمه‌های لینک (کانال، سایت، شبکه‌های اجتماعی)", c_links,
                    [P("items", "لینک‌ها", "items", [{"text": "کانال ما", "url": "https://t.me/telegram"}], keys={"text": 40, "url": 200}, need=["text", "url"], n=6)],
                    [(r"لینک (ها|های)|شبکه (ها)?ی? اجتماعی|اینستاگرام|وبسایت|وب سایت", 0.8)], (), 75, "عمومی"))
    register(Module("shop", "فروشگاه", "فهرست محصول، صفحهٔ هر محصول، ثبت سفارش به‌صورت تیکت و سفارش‌های من", c_shop,
                    [P("items", "محصولات", "items", [{"name": "محصول نمونه", "price": "۱۰۰٬۰۰۰ تومان", "desc": "توضیحات محصول را ویرایش کن."}], keys={"name": 60, "price": 30, "desc": 500}, need=["name"], n=6)],
                    [(r"فروشگاه|محصول(ات)?|کاتالوگ|منو( غذا)?|سفارش (غذا|محصول|کالا)|shop|catalog", 1.0)], (), 25, "فروش"))
    register(Module("ai_assistant", "دستیار هوشمند", "گفت‌وگوی زنده با هوش مصنوعی (محدودیت روزانه)", c_ai,
                    [P("prompt", "دستور دستیار", "text", "تو دستیار مفید و مودب این ربات هستی. کوتاه و دقیق به فارسی پاسخ بده.", max=1500), P("daily", "سقف پیام روزانه", "int", 15, min=1, max=100)],
                    [(r"هوش مصنوعی|چت ?بات|دستیار (هوشمند)?|gpt|ai assistant", 1.0)], (), 65, "هوش مصنوعی"))
    register(Module("quiz", "مسابقه", "سؤال‌های چندگزینه‌ای با امتیاز نهایی", c_quiz,
                    [P("items", "سؤال‌ها", "items", [{"q": "پایتخت ایران کدام است؟", "opts": ["تهران", "شیراز", "تبریز"]}, {"q": "۲ + ۲ چند می‌شود؟", "opts": ["۴", "۳", "۵"]}], keys={"q": 300, "opts": 0}, need=["q", "opts"], n=8)],
                    [(r"مسابقه|کوییز|آزمون|quiz", 1.0)], (), 85, "سرگرمی"))
    register(Module("group_manager", "مدیر گروه", "کپچا، قفل لینک/فوروارد، ضد اسپم، اخطار و خوش‌آمد", c_group,
                    [P("welcome", "پیام خوش‌آمد", "text", "سلام {name}! به {group} خوش آمدی.", max=300), P("rules", "قوانین", "text", "۱) احترام بگذارید ۲) تبلیغ ممنوع ۳) لینک‌فرستادن ممنوع", max=500)],
                    [(r"مدیریت گروه|ضد ?اسپم|قفل (لینک|گروه)|کپچا|گروه.{0,15}مدیر|مدیر.{0,10}گروه", 1.5)], (), 5, "گروه"))


_reg2()
