# -*- coding: utf-8 -*-
"""
catalog.py — کاتالوگ قابلیت‌ها + کامپایلر Spec ← کانفیگ (قطعی، بدون LLM)

معماری «Spec ← Compiler»:
  درخواست کاربر ← انتخاب قابلیت‌ها (LLM فقط یک Spec کوچک JSON از enum بسته انتخاب می‌کند؛
  در نبود LLM روتر کلیدواژه‌ای همین کار را می‌کند) ← کامپایلر قطعی ← کانفیگ معتبر موتور.

  • هر قابلیت: پارامترها (P از modules)، تولیدکننده (تابع compile)، تست پذیرش (tests/test_catalog.py،
    روی موتور واقعی به‌صورت headless)، متن‌های قابل‌سفارشی (texts).
  • خروجی کامپایلر همیشه سازگار است: متغیرِ استفاده‌شده همیشه اعلان می‌شود، نود بدون مسیر/اکشن
    وجود ندارد؛ تداخل نام‌ها در حالت ادغام با ربات موجود با پیشوند حل می‌شود.
  • هیچ خروجی LLM بدون اعتبارسنجی (enum بسته + پارامترها + sanitize در ai.py) به موتور نمی‌رسد.

وابستگی: modules (Builder) ← modlib برای قالب‌های ماژولی. از ai و engine import نمی‌شود (جلوگیری از دور).

نام‌های پایدار (برای ai.py / app.py / mother.py / tests):
  CATALOG, FEATURE_ORDER, parse_spec, keyword_spec, compile_spec, preview_spec,
  catalog_missing, repair_config, build_templates, spec_prompt, SpecError, merge_spec_config
"""

import re
from modules import Builder, Module, P, register, _btn, _group, _h, _clean_text, fmt, _num, BuildError, MODULES
import modlib  # noqa: F401  (ثبت ماژول‌های مسیر قدیمی برای قالب‌ها)


# ───────────────────────── ابزارهای کوچک ─────────────────────────
_EQ = lambda var, val: {"var": var, "op": "==", "value": str(val)}      # noqa: E731
_NE = lambda var, val: {"var": var, "op": "!=", "value": str(val)}      # noqa: E731
_GE = lambda var, val: {"var": var, "op": ">=", "value": str(val)}      # noqa: E731
_GT = lambda var, val: {"var": var, "op": ">", "value": str(val)}       # noqa: E731
_LT = lambda var, val: {"var": var, "op": "<", "value": str(val)}       # noqa: E731
_ADD = lambda var, val: {"op": "add", "var": var, "value": str(val)}    # noqa: E731
_SET = lambda var, val: {"op": "set", "var": var, "value": str(val)}     # noqa: E731
_PH = re.compile(r"\{([a-z][a-z0-9_]{0,19})(?:\|([^{}]{0,60}))?\}")   # جای‌نگهدار {var} در متن‌ها


class SpecError(ValueError):
    """Spec نامعتبر؛ هرگز به موتور نمی‌رسد."""


# ───────────────────────── قابلیت‌های کاتالوگ (enum بسته) ─────────────────────────
class Feature:
    def __init__(self, fid, fa, desc, compile_fn, params=None, texts=None, requires_coin=False, prio=50):
        self.id, self.fa, self.desc = fid, fa, desc
        self.compile = compile_fn
        self.params = params or []
        self.texts = texts or {}          # key → متن پیش‌فرض قابل‌سفارشی
        self.requires_coin = requires_coin
        self.prio = prio


FEATURES = {}


def _feature(f):
    FEATURES[f.id] = f
    return f


def T(texts, key, default):
    """متن سفارشی کاربر یا پیش‌فرض؛ همیشه پاک‌سازی‌شده."""
    v = texts.get(key)
    v = _clean_text(v, 900) if v else ""
    return v or default


# ═══════════════════════ اقتصاد ═══════════════════════
def c_wallet(b, p, texts):
    b.coin, b.coin_emoji = p["coin"], p["emoji"]
    b.var("coins", "0")
    t_body = T(texts, "body", "موجودی تو: {coins} {coin}\nدعوت‌های موفق: {refs}").replace("{coin}", _h(b.coin))
    b.node("wallet", f"<b>{b.E(b.coin_emoji)}کیف {_h(b.coin)}</b>\n\n" + t_body, [b.back()], title="کیف پول")
    b.menu_add(10, f"{b.E(b.coin_emoji)}کیف {b.coin}", "wallet")
    b.cmd("wallet", "wallet")
    b.cmd("balance", "wallet")
    if p["start_bonus"] > 0:
        b.var("welcomed", "0")
        t_gift = T(texts, "bonus", "خوش اومدی {name}!\n{bonus} {coin} هدیهٔ ورود به کیفت اضافه شد.\nموجودی: {coins} {coin}") \
            .replace("{coin}", _h(b.coin)).replace("{bonus}", fmt(p["start_bonus"]))
        b.node("w_welcome", t_gift, [[_btn("ادامه", goto="start")]], title="هدیه ورود",
               do=[_SET("welcomed", 1), _ADD("coins", fmt(p["start_bonus"]))])
        b.start_routes.append({"when": {"all": [_EQ("visits", 1), _NE("welcomed", 1)]}, "goto": "w_welcome"})


def c_daily(b, p, texts):
    b.var("coins", "0")
    b.var("last_daily", "")
    amount = fmt(p["amount"])
    t_gift = T(texts, "gift", "هدیهٔ امروزت: {amount} {coin}").replace("{coin}", _h(b.coin)).replace("{amount}", amount)
    t_done = T(texts, "done", "امروز هدیه‌ات را گرفته‌ای. فردا دوباره بیا!")
    b.node("daily", T(texts, "title", "هدیهٔ روزانه"), [], title="هدیه روزانه",
           route=[{"when": _EQ("last_daily", "{date}"), "goto": "daily_done"},
                  {"when": _NE("last_daily", "{date}"), "goto": "daily_get"}])
    b.node("daily_get", t_gift + f"\nموجودی: {{coins}} {_h(b.coin)}", [b.back()], title="هدیه امروز",
           do=[_SET("last_daily", "{date}"), _ADD("coins", amount)])
    b.node("daily_done", t_done, [b.back()], title="هدیه گرفته شد")
    b.menu_add(15, f"{b.E('🎁')}هدیهٔ روزانه", "daily")
    b.cmd("daily", "daily")


def c_referral(b, p, texts):
    b.var("coins", "0")
    reward = fmt(p["reward"])
    t_body = T(texts, "body", "هر کسی با لینک تو وارد ربات شود، {reward} {coin} می‌گیری.\n"
                              "دعوت‌های موفق تو: {refs}\n\nلینک اختصاصی تو:\n{ref_link}") \
        .replace("{coin}", _h(b.coin)).replace("{reward}", reward)
    b.node("invite", f"<b>{b.E('👥')}دعوت دوستان</b>\n\n" + t_body,
           [[_btn("ارسال لینک دعوت", share=f"با این ربات {_h(b.coin)} جمع کن و جایزه بگیر!"),
             _btn("کپی لینک", copy="{ref_link}")],
            [_btn("برترین دعوت‌کننده‌ها", goto="invite_top")], b.back()], title="دعوت دوستان")
    b.node("invite_top", "برترین دعوت‌کننده‌ها:", [[_btn("دعوت دوستان", goto="invite")], b.back()], title="برترین‌ها",
           board={"var": "refs", "top": 10, "label": "دعوت‌های موفق"})
    b.on_ref = [_ADD("coins", reward)]
    b.ref_text = f"یک نفر با لینک تو وارد ربات شد! {reward} {b.coin} گرفتی. موجودی: {{coins}} {b.coin}"
    b.menu_add(40, f"{b.E('👥')}دعوت دوستان", "invite")
    b.cmd("invite", "invite")


def c_leaderboard(b, p, texts):
    var = "coins" if "wallet" in b.have_or_planned() else "refs"
    label = T(texts, "label", f"بیشترین {b.coin}" if var == "coins" else "بیشترین دعوت")
    t_body = T(texts, "body", "برترین کاربران:" if var == "coins" else "برترین دعوت‌کننده‌ها:")
    b.node("top", t_body, [b.back()], title="برترین‌ها",
           board={"var": var, "top": int(p["top"]), "label": label})
    b.menu_add(48, f"{b.E('🏆')}برترین‌ها", "top")
    b.cmd("top", "top")


# ═══════════════════════ بازی‌ها (همه با اکشن‌های واقعی موتور) ═══════════════════════
def c_game_dice(b, p, texts):
    b.var("coins", "0")
    b.var("die_val", "0")
    bet, win_at, prize = int(p["bet"]), int(p["win_at"]), fmt(p["prize"])
    emoji = p["emoji"]
    t_intro = T(texts, "intro", "تاس بینداز؛ اگر {win} یا بیشتر بیاید، {prize} {coin} می‌گیری!") \
        .replace("{win}", str(win_at)).replace("{prize}", prize).replace("{coin}", _h(b.coin))
    b.node("dice", f"<b>{b.E('🎲')}بازی تاس {emoji}</b>\n\n" + t_intro,
           [[_btn("بازی کن", goto="dice_bet" if bet > 0 else "dice_roll")], b.back()], title="بازی تاس")
    if bet > 0:
        b.node("dice_bet", "بررسی موجودی…", [], title="بررسی شرط",
               route=[{"when": _LT("coins", fmt(bet)), "goto": "dice_no"},
                      {"when": _GE("coins", fmt(bet)), "goto": "dice_roll"}])
        b.node("dice_no", f"برای این بازی {fmt(bet)} {_h(b.coin)} لازم داری.\nموجودی: {{coins}} {_h(b.coin)}",
               [[_btn("بازی تاس", goto="dice")], b.back()], title="سکه کم است")
    pre = ([_ADD("coins", fmt(-bet))] if bet > 0 else []) + [{"op": "dice", "var": "die_val", "emoji": emoji}]
    b.node("dice_roll", "در حال انداختن تاس…", [], title="انداختن تاس", do=pre,
           route=[{"when": _GE("die_val", str(win_at)), "goto": "dice_win"},
                  {"when": _GE("die_val", "0"), "goto": "dice_lose"}])
    t_win = T(texts, "win", "آفرین! تاس {die_val} آمد؛ {prize} {coin} گرفتی!").replace("{prize}", prize).replace("{coin}", _h(b.coin))
    t_lose = T(texts, "lose", "تاس {die_val} آمد؛ دفعهٔ بعد!")
    b.node("dice_win", f"{b.E('🎉')}" + t_win + f"\nموجودی: {{coins}} {_h(b.coin)}",
           [[_btn("یک بار دیگر", goto="dice_bet" if bet > 0 else "dice_roll")], b.back()],
           title="بردی!", do=[_ADD("coins", prize)])
    b.node("dice_lose", t_lose, [[_btn("یک بار دیگر", goto="dice_bet" if bet > 0 else "dice_roll")], b.back()], title="باختی")
    b.menu_add(30, f"{b.E('🎲')}بازی تاس", "dice")


def c_game_guess(b, p, texts):
    b.var("coins", "0")
    for v in ("guess_num", "guess_tries", "pick"):
        b.var(v, "0")
    mx, rounds, reward = int(p["max"]), int(p["rounds"]), fmt(p["reward"])
    t_intro = T(texts, "intro", "یک عدد بین ۱ تا {max} انتخاب کن. {rounds} حدس داری؛ با هر برد {reward} {coin} می‌گیری.") \
        .replace("{max}", str(mx)).replace("{rounds}", str(rounds)).replace("{reward}", reward).replace("{coin}", _h(b.coin))
    b.node("guess", f"<b>{b.E('🎯')}حدس عدد</b>\n\n" + t_intro,
           [[_btn("شروع بازی", goto="guess_start")], b.back()], title="حدس عدد")
    b.node("guess_start", "آماده‌سازی بازی…", [], title="شروع حدس",
           do=[{"op": "random", "var": "guess_num", "value": f"1-{mx}"}, _SET("guess_tries", 0)],
           route=[{"when": _GE("guess_num", "1"), "goto": "guess_pick"}])
    nums = [_btn(str(i), goto="guess_check", do=[_SET("pick", i), _ADD("guess_tries", 1)]) for i in range(1, mx + 1)]
    t_pick = T(texts, "pick", "عددت را انتخاب کن:")
    b.node("guess_pick", t_pick, _group(nums, 3) + [b.back()], title="انتخاب عدد")
    b.node("guess_check", "بررسی حدس…", [], title="بررسی حدس",
           route=[{"when": _EQ("guess_num", "{pick}"), "goto": "guess_win"},
                  {"when": _GE("guess_tries", str(rounds)), "goto": "guess_end"},
                  {"when": _GT("guess_num", "{pick}"), "goto": "guess_hi"},
                  {"when": _LT("guess_num", "{pick}"), "goto": "guess_lo"}])
    t_win = T(texts, "win", "درست حدس زدی! عدد {guess_num} بود. +{reward} {coin}").replace("{reward}", reward).replace("{coin}", _h(b.coin))
    t_end = T(texts, "end", "حدس‌هایت تمام شد؛ عدد درست {guess_num} بود.")
    t_hi = T(texts, "hint_hi", "عدد بزرگ‌تر از حدست است.")
    t_lo = T(texts, "hint_lo", "عدد کوچک‌تر از حدست است.")
    b.node("guess_win", f"{b.E('🎉')}" + t_win + f"\nموجودی: {{coins}} {_h(b.coin)}",
           [[_btn("دوباره", goto="guess_start")], b.back()], title="بردی!", do=[_ADD("coins", reward)])
    b.node("guess_end", t_end, [[_btn("دوباره", goto="guess_start")], b.back()], title="پایان دست")
    b.node("guess_hi", t_hi, [[_btn("ادامهٔ حدس", goto="guess_pick")], b.back()], title="راهنما")
    b.node("guess_lo", t_lo, [[_btn("ادامهٔ حدس", goto="guess_pick")], b.back()], title="راهنما")
    b.menu_add(31, f"{b.E('🎯')}حدس عدد", "guess")


def c_game_coinbet(b, p, texts):
    b.var("coins", "0")
    b.var("flip", "0")
    bet = int(p["bet"])
    t_intro = T(texts, "intro", "شیر یا خط؛ {bet} {coin} شرط ببند. شیر بیاید دو برابرش را می‌گیری.") \
        .replace("{bet}", fmt(bet)).replace("{coin}", _h(b.coin))
    b.node("coinbet", f"<b>{b.E('🪙')}شیر یا خط</b>\n\n" + t_intro,
           [[_btn("شرط ببند", goto="cb_check")], b.back()], title="شیر یا خط")
    b.node("cb_check", "بررسی موجودی…", [], title="بررسی شرط",
           route=[{"when": _LT("coins", fmt(bet)), "goto": "cb_no"},
                  {"when": _GE("coins", fmt(bet)), "goto": "cb_flip"}])
    b.node("cb_no", f"برای این شرط {fmt(bet)} {_h(b.coin)} لازم داری.\nموجودی: {{coins}} {_h(b.coin)}",
           [[_btn("شیر یا خط", goto="coinbet")], b.back()], title="سکه کم است")
    b.node("cb_flip", "در حال پرتاب سکه…", [], title="پرتاب سکه",
           do=[_ADD("coins", fmt(-bet)), {"op": "random", "var": "flip", "value": "0-1"}],
           route=[{"when": _EQ("flip", "1"), "goto": "cb_win"},
                  {"when": _GE("flip", "0"), "goto": "cb_lose"}])
    t_win = T(texts, "win", "شیر اومد! {got} {coin} گرفتی.").replace("{got}", fmt(bet * 2)).replace("{coin}", _h(b.coin))
    t_lose = T(texts, "lose", "خط اومد؛ {bet} {coin} شرط باختی.").replace("{bet}", fmt(bet)).replace("{coin}", _h(b.coin))
    b.node("cb_win", f"{b.E('🎉')}" + t_win + f"\nموجودی: {{coins}} {_h(b.coin)}",
           [[_btn("دوباره", goto="cb_check")], b.back()], title="بردی!", do=[_ADD("coins", fmt(bet * 2))])
    b.node("cb_lose", t_lose, [[_btn("دوباره", goto="cb_check")], b.back()], title="باختی")
    b.menu_add(32, f"{b.E('🪙')}شیر یا خط", "coinbet")


def c_game_quiz(b, p, texts):
    items = p["items"]
    b.var("qscore", "0")
    for i, it in enumerate(items, 1):
        opts = it.get("opts") or []
        if len(opts) < 2:
            continue
        nxt = f"quiz_{i + 1}" if i < len(items) else "quiz_end"
        btns = []
        for j, o in enumerate(opts):
            do = [_ADD("qscore", 1)] if j == 0 else None
            btns.append(_btn(o, goto=nxt, **({"do": do} if do else {})))
        k = i % len(btns)                       # جای گزینهٔ درست ثابت نباشد
        btns = btns[k:] + btns[:k]
        nid = "quiz" if i == 1 else f"quiz_{i}"
        b.node(nid, f"<b>سؤال {i} از {len(items)}</b>\n\n{_h(it['q'], 300)}", _group(btns, 1), title=f"سؤال {i}")
    t_end = T(texts, "end", "مسابقه تمام شد!\nامتیاز تو: {qscore} از {total}").replace("{total}", str(len(items)))
    b.node("quiz_end", f"{b.E('🏁')}" + t_end, [[_btn("دوباره", goto="quiz_again")], b.back()], title="نتیجه")
    b.node("quiz_again", "شروع دوباره…", [], title="شروع دوباره", do=[_SET("qscore", 0)],
           route=[{"when": _EQ("qscore", "0"), "goto": "quiz"}])
    b.menu_add(33, f"{b.E('🏁')}مسابقه", "quiz")


def c_game_wheel(b, p, texts):
    b.var("coins", "0")
    b.var("last_spin", "")
    b.var("roll", "0")
    prizes = p["prizes"]
    n = len(prizes)
    shown = "، ".join(fmt(x) for x in prizes)
    t_intro = T(texts, "intro", "هر روز یک چرخش رایگان داری. جایزه‌ها: {items}").replace("{items}", shown)
    b.node("wheel", f"<b>{b.E('🎡')}گردونهٔ شانس</b>\n\n" + t_intro,
           [[_btn("بچرخان", goto="wheel_go")], b.back()], title="گردونه شانس")
    b.node("wheel_go", "بررسی چرخش…", [], title="بررسی چرخش",
           route=[{"when": _EQ("last_spin", "{date}"), "goto": "wheel_none"},
                  {"when": _NE("last_spin", "{date}"), "goto": "wheel_pre"}])
    t_none = T(texts, "none", "چرخش رایگان امروزت را انجام داده‌ای. فردا دوباره بیا!")
    b.node("wheel_none", t_none, [[_btn("گردونه", goto="wheel")], b.back()], title="چرخیدی")
    b.node("wheel_pre", "در حال چرخش…", [], title="چرخش گردونه",
           do=[_SET("last_spin", "{date}"), {"op": "random", "var": "roll", "value": f"1-{n}"}],
           route=[{"when": _GE("roll", "1"), "goto": "wheel_c1"}])
    chain = ["wheel_c1"] + [f"wheel_c{i}" for i in range(2, 5)]
    for gi, nid in enumerate(chain):
        lo, hi = gi * 4 + 1, min(n, gi * 4 + 4)
        if lo > n:
            break
        rules = [{"when": _EQ("roll", str(i)), "goto": f"wheel_r{i}"} for i in range(lo, hi + 1)]
        if hi < n:
            rules.append({"when": _GT("roll", str(hi)), "goto": chain[gi + 1]})
        b.node(nid, "در حال چرخش…", [], title="نتیجه چرخش", route=rules)
    for i, pr in enumerate(prizes, 1):
        t_win = T(texts, "win", "برنده شدی: {prize} {coin}!").replace("{prize}", fmt(pr)).replace("{coin}", _h(b.coin))
        b.node(f"wheel_r{i}", f"{b.E('🎉')}" + t_win + f"\nموجودی: {{coins}} {_h(b.coin)}",
               [[_btn("یک بار دیگر", goto="wheel_go")], b.back()], title=f"جایزه {fmt(pr)}", do=[_ADD("coins", fmt(pr))])
    b.menu_add(34, f"{b.E('🎡')}گردونهٔ شانس", "wheel")


# ───────────────────────── ثبت کاتالوگ ─────────────────────────
_feature(Feature("wallet", "کیف سکه", "واحد پول ربات با موجودی هر کاربر و هدیهٔ اولین ورود", c_wallet,
                 [P("coin", "نام واحد پول", "text", "سکه", max=20), P("emoji", "ایموجی واحد پول", "text", "💰", max=4),
                  P("start_bonus", "هدیهٔ اولین ورود", "num", 0, min=0, max=100000)], prio=10))
_feature(Feature("daily", "هدیهٔ روزانه", "هر کاربر روزی یک بار هدیه می‌گیرد", c_daily,
                 [P("amount", "مقدار هدیه", "num", 1, min=0.01, max=100000)], requires_coin=True, prio=15))
_feature(Feature("referral", "دعوت دوستان", "لینک دعوت اختصاصی و پاداش هر دعوت", c_referral,
                 [P("reward", "پاداش هر دعوت", "num", 5, min=0.01, max=100000)], requires_coin=True, prio=20))
_feature(Feature("leaderboard", "برترین‌ها", "جدول برترین کاربران (سکه یا دعوت)", c_leaderboard,
                 [P("top", "نفرات برتر", "int", 10, min=3, max=50)], prio=25))
_feature(Feature("game.dice", "بازی تاس", "تاس واقعی تلگرام با شرط و جایزه", c_game_dice,
                 [P("emoji", "نوع تاس", "text", "🎲", max=4),
                  P("bet", "شرط هر دست (۰=رایگان)", "int", 0, min=0, max=100000),
                  P("win_at", "آستانهٔ برد (عدد تاس)", "int", 5, min=1, max=64),
                  P("prize", "جایزهٔ برد (سکه)", "num", 10, min=0, max=100000)], requires_coin=True, prio=30))
_feature(Feature("game.guess", "حدس عدد", "حدس عدد با راهنمای بزرگ‌تر/کوچک‌تر و جایزه", c_game_guess,
                 [P("max", "بازهٔ عدد (۱ تا N)", "int", 10, min=2, max=12),
                  P("rounds", "تعداد حدس هر دست", "int", 3, min=1, max=10),
                  P("reward", "جایزهٔ برد (سکه)", "num", 10, min=0, max=100000)], requires_coin=True, prio=31))
_feature(Feature("game.coinbet", "شیر یا خط", "شرط سکه با پرتاب سکه", c_game_coinbet,
                 [P("bet", "مبلغ شرط (سکه)", "num", 5, min=1, max=100000)], requires_coin=True, prio=32))
_feature(Feature("game.quiz", "مسابقه", "سؤال‌های چندگزینه‌ای با امتیاز نهایی", c_game_quiz,
                 [P("items", "سؤال‌ها (گزینهٔ اول همیشه درست است)", "items",
                   [{"q": "پایتخت ایران کدام است؟", "opts": ["تهران", "شیراز", "تبریز"]},
                    {"q": "۲ + ۲ چند می‌شود؟", "opts": ["۴", "۳", "۵"]}],
                   keys={"q": 300, "opts": 0}, need=["q", "opts"], n=8)], prio=33))
_feature(Feature("game.wheel", "گردونهٔ شانس", "هر روز یک چرخش رایگان با جایزه‌های دلخواه", c_game_wheel,
                 [P("prizes", "جایزه‌ها (سکه)", "prizes", [1, 2, 3, 5, 10, 20], n=12)], requires_coin=True, prio=34))

FEATURE_ORDER = ["wallet", "daily", "referral", "leaderboard",
                 "game.dice", "game.guess", "game.coinbet", "game.quiz", "game.wheel"]
CATALOG = {fid: FEATURES[fid] for fid in FEATURE_ORDER}


# ───────────────────────── Spec: اعتبارسنجی (enum بسته) ─────────────────────────
def _coerce_params(feature, raw):
    from modules import clean_params
    raw = raw if isinstance(raw, dict) else {}
    return clean_params(_as_module(feature), raw)


def _as_module(feature):
    """قابلیت کاتالوگ را موقتاً به‌شکل Module (برای clean_params) درمی‌آورد."""
    m = Module(feature.id, feature.fa, feature.desc, feature.compile, params=feature.params, prio=feature.prio)
    return m


def parse_spec(raw):
    """متن/دیکتی که LLM (یا ویزارد) داده → Spec اعتبارسنجی‌شده. هر خطا: SpecError. هیچ مقدار خام عبور نمی‌کند."""
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            raise SpecError("Spec خالی است")
        try:
            import json
            raw = json.loads(raw)
        except ValueError as e:
            raise SpecError("JSON نامعتبر: %s" % str(e)[:120])
    if not isinstance(raw, dict):
        raise SpecError("Spec باید یک شیء JSON باشد")
    name = _clean_text(raw.get("name"), 40) or "ربات من"
    raw_feats = raw.get("features")
    if not isinstance(raw_feats, list) or not raw_feats:
        raise SpecError("فهرست features خالی یا نامعتبر است")
    feats, seen = [], set()
    for item in raw_feats[:12]:
        if not isinstance(item, dict):
            raise SpecError("هر قابلیت باید یک شیء باشد")
        fid = str(item.get("type") or "").strip()
        if fid not in CATALOG:
            raise SpecError("نوع ناشناخته: %s (فقط قابلیت‌های enum مجازند)" % fid[:60])
        if fid in seen:
            continue                        # تکراری: یکی کافی است
        seen.add(fid)
        feats.append((fid, _coerce_params(CATALOG[fid], item)))
    texts = {}
    raw_texts = raw.get("texts")
    if isinstance(raw_texts, dict):
        for fid, tv in raw_texts.items():
            fid = str(fid or "").strip()
            if fid in CATALOG and isinstance(tv, dict):
                texts[fid] = {str(k)[:20]: _clean_text(v, 900) for k, v in tv.items()
                              if isinstance(k, str) and isinstance(v, str) and _clean_text(v, 900)}
    return {"name": name, "features": feats, "texts": texts}


def spec_public():
    """فهرست کاتالوگ برای پرامپت LLM و رابط کاربری."""
    out = []
    for fid in FEATURE_ORDER:
        f = CATALOG[fid]
        out.append({"type": fid, "fa": f.fa, "desc": f.desc,
                    "params": [{"k": s["k"], "fa": s["fa"], "kind": s["kind"], "default": s["default"]}
                               for s in f.params]})
    return out


def spec_prompt():
    """دستورالعمل کوچک انتخاب Spec؛ LLM فقط از enum بسته انتخاب می‌کند، نه ساخت کانفیگ."""
    import json
    listing = json.dumps(spec_public(), ensure_ascii=False, separators=(",", ":"))
    return (
        "You select features for a Telegram bot from a CLOSED catalog. "
        "Read the user's Persian request and return ONLY a small JSON spec (20-40 lines): "
        '{"name":"bot name in Persian","features":[{"type":"<catalog type>", PARAMS...}],"texts":{"<type>":{"win":"..."}}}\n'
        "Rules: every `type` MUST be one of the catalog types below; copy param values from the request when "
        "explicitly given, else omit them (defaults apply). Do NOT invent types or params. Add `wallet` when any "
        "coin-based feature is used. `texts` is optional: only keys you want to customize. "
        "If the request matches NOTHING in the catalog, return {\"features\":[]}. No prose, JSON only.\n"
        "CATALOG: " + listing
    )


# ───────────────────────── روتر کلیدواژه‌ای (بدون LLM) ─────────────────────────
_KW = [
    ("wallet", r"(کیف پول|واحد پول|سکه|الماس|کوین|امتیاز|جم|اعتبار|wallet|coin)"),
    ("daily", r"(هدیه|جایزه|پاداش)\s*روزانه|چک ?این|daily"),
    ("referral", r"(رفرال|زیر ?مجموعه|لینک دعوت|دعوت (کرد|کنه|کند|کنن|کنند|دوست)|invite|referral)"),
    ("leaderboard", r"(برترین|جدول (بیشترین|رتبه)|لیدربورد|رتبه ?بندی|leaderboard)"),
    ("game.dice", r"(تاس|شانس با تاس|dice)"),
    ("game.guess", r"(حدس( ?عدد)?|gues?s)"),
    ("game.coinbet", r"(شیر یا خط|دودو|شرط( ?سکه)?|coin ?flip|bet)"),
    ("game.quiz", r"(کوی?[ی]?ز|آزمون|مسابقه|quiz)"),
    ("game.wheel", r"(گردونه|چرخ شانس|wheel)"),
]


def _near_num(text, kw, default, lo, hi):
    m = re.search(kw, text)
    if not m:
        return default
    seg = text[m.end():m.end() + 40] + " " + text[max(0, m.start() - 30):m.start()]
    n = re.search(r"(\d+(?:[.,]\d+)?)", seg)
    if not n:
        return default
    v = _num(n.group(1), default)
    return max(lo, min(hi, v))


def keyword_spec(prompt):
    """در نبود LLM: از کلیدواژه‌ها قابلیت‌ها و پارامترهای اصلی را درمی‌آورد. خروجی: Spec یا None."""
    from modules import normalize_text
    t = normalize_text(prompt)
    chosen = [fid for fid, pat in _KW if re.search(pat, t)]
    if not chosen:
        return None
    feats = []
    for fid in chosen:
        p = {}
        if fid == "wallet":
            for w in ("سکه", "الماس", "کوین", "امتیاز", "جم", "اعتبار"):
                if w in t:
                    p["coin"] = w
                    break
            p["start_bonus"] = _near_num(t, r"(هدیه|جایزه|پاداش|بونوس)\s*(ی\s*)?(ورود|شروع|استارت|ثبت ?نام)", 0, 0, 100000)
        elif fid == "daily":
            p["amount"] = _near_num(t, r"(هدیه|جایزه|پاداش) روزانه", 1, 0.01, 100000)
        elif fid == "referral":
            p["reward"] = _near_num(t, r"(هر|به ازای) (دعوت|رفرال|نفر)|پاداش (دعوت|رفرال)", 5, 0.01, 100000)
        elif fid == "game.dice":
            p["bet"] = _near_num(t, r"شرط", 0, 0, 100000)
            p["prize"] = _near_num(t, r"(جایزه|برد)( تاس)?", 10, 0, 100000)
        elif fid == "game.guess":
            m = re.search(r"حدس( ?عدد)?\D{0,20}(\d{1,2})", t)
            p["max"] = int(_num(m.group(2), 10)) if m else 10
            p["max"] = max(2, min(12, p["max"]))
        elif fid == "game.coinbet":
            p["bet"] = _near_num(t, r"شرط( بندی)?|شیر یا خط", 5, 1, 100000)
        elif fid == "game.wheel":
            w = t[max(0, t.find("گردونه")):t.find("گردونه") + 400] if "گردونه" in t else t
            prizes = [_num(x, None) for x in re.findall(r"(\d+(?:\.\d+)?)", w)]
            prizes = [x for x in prizes if x is not None and 0 < x <= 100000][:12]
            if len(prizes) >= 2:
                p["prizes"] = prizes
        feats.append((fid, _coerce_params(CATALOG[fid], p)))
    name = _bot_name(t, chosen)
    return {"name": name, "features": feats, "texts": {}}


def _bot_name(t, chosen):
    for pat in (r"(?:اسم|نام) ربات\s*[:：]?\s*[«\"']?([^\n«»\"'،.]{2,25})",):
        m = re.search(pat, t)
        if m:
            n = _clean_text(m.group(1), 25).strip()
            if n and len(n.split()) <= 4:
                return n
    if chosen and chosen[0].startswith("game."):
        return "ربات بازی"
    if "wallet" in chosen or "daily" in chosen or "referral" in chosen:
        return "ربات سکه"
    return "ربات من"


# ───────────────────────── کامپایلر قطعی ─────────────────────────
def _auto_wallet(feats):
    """هر قابلیتِ سکه‌محور کیف سکه را می‌خواهد؛ در نبودش خودکار اضافه می‌شود."""
    ids = {fid for fid, _ in feats}
    if not ids & {fid for fid, f in CATALOG.items() if f.requires_coin}:
        return feats
    if "wallet" in ids:
        return feats
    return [("wallet", _coerce_params(CATALOG["wallet"], {}))] + feats


def compile_spec(spec, current=None, notes=None):
    """Spec اعتبارسنجی‌شده → (thinking, cfg, ideas). اگر current داده شود قابلیت‌ها با پیشوند به ربات موجود اضافه می‌شوند."""
    notes = notes if notes is not None else []
    has_coin = current is not None and "coins" in (current.get("vars") or {})
    feats = list(spec["features"]) if has_coin else _auto_wallet(list(spec["features"]))
    # ربات از قبل سکه دارد → کیفِ خودکار دوباره ساخته نمی‌شود (کیف صریحِ کاربر با پیشوند اضافه می‌ماند)
    ids = [fid for fid, _ in feats]
    if "wallet" in ids and "wallet" not in [fid for fid, _ in spec["features"]]:
        notes.append("کیف سکه برای اقتصاد بازی‌ها خودکار اضافه شد.")
    b = Builder(spec["name"], emoji=False, payments=False)
    b.shared["plans"] = {fid: p for fid, p in feats}
    for fid, p in feats:
        b.have.add(fid)
        texts = dict(spec.get("texts", {}).get(fid) or {})
        CATALOG[fid].compile(b, p, texts)
        b.titles.append(CATALOG[fid].fa)
    cfg = b.finish()
    ideas = []
    if "wallet" in ids and "daily" not in ids:
        ideas.append("«هدیهٔ روزانه» را هم اضافه کن تا کاربرها هر روز برگردند")
    if "referral" not in ids:
        ideas.append("با «دعوت دوستان» ربات خودش رشد می‌کند")
    if ids and ids[0].startswith("game"):
        ideas.append("متن و جایزهٔ بازی‌ها را از ویرایش دستی عوض کن")
    thinking = f"ربات «{spec['name']}» با کامپایلر قطعی از قابلیت‌های تست‌شده ساخته شد: " + \
        "، ".join(CATALOG[fid].fa for fid in ids) + ". ساخت همیشه معتبر است (متغیرها اعلان شده و همهٔ بخش‌ها مسیر دارند)."
    if notes:
        thinking += "\n" + "\n".join("• " + n for n in notes[:4])
    if current is not None:
        cfg = merge_spec_config(current, cfg)
        thinking = "این قابلیت‌ها بدون تغییر بخش‌های قبلی به ربات اضافه شد: " + \
            "، ".join(CATALOG[fid].fa for fid in ids) + "."
    return thinking, cfg, ideas[:3]


def merge_spec_config(current, new_cfg, ns=None):
    """افزودن کانفیگ تازه به ربات موجود با پیشوند نام‌گذاری (تداخل نام‌ها حل می‌شود)."""
    import copy
    if ns is None:
        ns = _free_ns(current)
    cfg = copy.deepcopy(current)
    nodes = cfg.setdefault("nodes", {})
    start_id = cfg.get("start") or "start"
    if start_id not in nodes:
        raise BuildError("ربات فعلی گره شروع ندارد")
    rename = {}
    for nid in new_cfg["nodes"]:
        if nid == "start":
            continue
        new = f"{ns}{nid}"[:30]
        while new in nodes or new in rename.values():
            new = (new[:27] + "_x")[:30]
        rename[nid] = new
    rename["start"] = start_id

    def rw(o):
        if isinstance(o, dict):
            return {k: (rename.get(v, v) if k in ("goto", "next") and isinstance(v, str) else rw(v)) for k, v in o.items()}
        if isinstance(o, list):
            return [rw(x) for x in o]
        return o

    for nid, n in new_cfg["nodes"].items():
        if nid != "start":
            nodes[rename[nid]] = rw(n)
    ns_start = rw(new_cfg["nodes"]["start"])
    btns = [b for row in ns_start.get("buttons", []) for b in row]
    st = nodes[start_id]
    rows = st.setdefault("buttons", [])
    need = (len(btns) + 1) // 2
    if len(rows) + need <= 6:
        for i in range(0, len(btns), 2):
            rows.append(btns[i:i + 2])
    else:
        raise BuildError("منوی اصلی ربات پر است؛ از استودیو جای خالی باز کن")
    for k in ("vars", "globals"):
        for kk, vv in (new_cfg.get(k) or {}).items():
            cfg.setdefault(k, {}).setdefault(kk, vv)
    for kk, vv in (new_cfg.get("commands") or {}).items():
        cfg.setdefault("commands", {}).setdefault(kk, rename.get(vv, vv))
    if new_cfg.get("on_ref"):
        cfg["on_ref"] = list(dict.fromkeys((cfg.get("on_ref") or []) + new_cfg["on_ref"]))[:6]
        if new_cfg.get("ref_text"):
            cfg.setdefault("ref_text", new_cfg["ref_text"])
    return cfg


def _free_ns(current):
    """پیشوند کوتاه تکرارنشده برای نودهای تازه (مثل f2_)"""
    nodes = set((current or {}).get("nodes") or {})
    i = 1
    while f"f{i}_" in nodes:
        i += 1
    return f"f{i}_"


# ───────────────────────── پیش‌نمایش: ✔ / 🟡 / ❌ ─────────────────────────
def preview_spec(spec):
    """قبل از ساخت: هر قابلیت ✔ ساخته می‌شود؛ کیف خودکار ✔؛ چیزهای نزدیک 🟡."""
    feats = _auto_wallet(list(spec["features"]))
    ids = [fid for fid, _ in feats]
    out = []
    for fid in ids:
        auto = fid == "wallet" and fid not in [f for f, _ in spec["features"]]
        out.append({"status": "ok", "text": CATALOG[fid].fa + (" (خودکار برای اقتصاد بازی)" if auto else "")})
    return out


# ───────────────────────── CATALOG_MISSING: موتور می‌تواند ولی کاتالوگ ندارد ─────────────────────────
_OUT_CATALOG = [
    # (الگو، خواستهٔ کوتاه، قابلیت پیشنهادی برای کاتالوگ)
    (r"(فروشگاه|محصول(ات)?|کاتالوگ|سفارش (محصول|غذا|کالا)|shop)", "فروشگاه و سفارش محصول", "shop — افزودن ماژول فروشگاه به کاتالوگ"),
    (r"(پشتیبانی|تیکت|ارتباط با (ما|مدیر)|support)", "پشتیبانی و تیکت", "support — افزودن فرم پشتیبانی به کاتالوگ"),
    (r"(سوالات? متداول|پرسش(های)? پرتکرار|faq)", "سؤال‌های پرتکرار", "faq — افزودن به کاتالوگ"),
    (r"(آگهی|نیازمندی)", "آگهی و نیازمندی", "ads — افزودن به کاتالوگ"),
    (r"(ماینر|miner)", "ماینر سکه", "miner — افزودن به کاتالوگ"),
    (r"(پازل|puzzle)", "قطعه‌های پازل", "puzzle — افزودن به کاتالوگ"),
    (r"(جوین|عضویت) (اجباری|الزامی)|forced join", "جوین اجباری کانال", "forced_join — افزودن به کاتالوگ"),
    (r"(کسب سکه|پاداش).{0,20}(عضویت|جوین)|عضویت.{0,15}(کانال).{0,15}(سکه|پاداش)", "کسب سکه با عضویت در کانال", "sponsor — افزودن به کاتالوگ"),
    (r"(مینی ?اپ|miniapp|وی ?اپ)", "مینی‌اپ", "app — ساخت مینی‌اپ (webapp.py) به کاتالوگ"),
    (r"(مدیریت گروه|ضد ?اسپم|کپچا|قفل (لینک|گروه))", "مدیریت گروه", "group_manager — افزودن به کاتالوگ"),
    (r"(دستیار هوشمند|گفتگو با هوش|چت ?بات|gpt)", "دستیار گفتگوی هوشمند", "ai_assistant — افزودن به کاتالوگ"),
]


def catalog_missing(prompt, spec=None):
    """چیزهایی که موتور می‌تواند ولی در enum کاتالوگ نیست → گزارش توسعه (kind=CATALOG_MISSING)."""
    from modules import normalize_text
    t = normalize_text(prompt)
    ids = {fid for fid, _ in (spec or {}).get("features", [])} if spec else set()
    out = []
    for pat, want, feature in _OUT_CATALOG:
        if re.search(pat, t) and not any(pat in _covered(fid) for fid in ids):
            out.append({"want": want, "why": "موتور این قابلیت را پشتیبانی می‌کند ولی هنوز در کاتالوگ Spec نیست؛ در این ساخت ساخته نمی‌شود.",
                        "upgrade": feature, "kind": "CATALOG_MISSING", "severity": "low",
                        "feature": feature, "criterion": "پس از افزودن به کاتالوگ، تست پذیرش همان قابلیت پاس شود."})
    return out[:4]


def _covered(fid):
    return set()


# ───────────────────────── ترمیم قطعی بدون LLM ─────────────────────────
def repair_config(cfg):
    """ترمیم ساختاری قطعی: اعلان متغیرهای استفاده‌شده، حذف نود یتیم، مسیر پیش‌فرض. خروجی: فهرست اصلاحات."""
    repairs = []
    nodes = cfg.get("nodes") or {}
    if not nodes:
        return repairs
    # ۱) متغیرهای استفاده‌شده که اعلان نشده‌اند → اعلان (وگرنه موتور نوشتنشان را بی‌صدا رد می‌کند)
    used = set()

    def _scan(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("var", "save") and isinstance(v, str) and v:
                    used.add(v)
                elif k == "save" and isinstance(v, list):
                    used.update(x for x in v if x)
                _scan(v)
        elif isinstance(o, list):
            for x in o:
                _scan(x)

    for n in nodes.values():
        for m in _PH.finditer(str(n.get("text") or "")):
            used.add(m.group(1))
        for row in n.get("buttons") or []:
            for b in row:
                if isinstance(b, dict):
                    for m in _PH.finditer(str(b.get("alert") or "")):
                        used.add(m.group(1))
                    _scan(b.get("do") or [])
        for r in n.get("route") or []:
            for m in _PH.finditer(str(r.get("when", {}).get("value") or "")):
                used.add(m.group(1))
        _scan(n.get("do") or [])
        if n.get("fields"):
            _scan(n.get("save") or [])
    declared = set(cfg.get("vars") or {})
    builtin = {"name", "first_name", "last_name", "full_name", "username", "id", "lang", "premium",
               "is_owner", "is_admin", "bot_name", "bot_username", "text", "param", "visits", "refs",
               "ticket_no", "invite_link", "invites", "ref_link", "date", "time", "hour", "weekday"}
    missing = sorted(v for v in used if v not in declared and v not in builtin and re.match(r"^[a-z][a-z0-9_]{0,19}$", v))
    if missing:
        cfg.setdefault("vars", {}).update({v: "0" for v in missing[:20]})
        repairs.append("متغیرهای استفاده‌شده اعلان شدند: " + ", ".join(missing[:6]))
    # ۲) نود یتیم (بدون مسیر ورودی) → حذف؛ دکمه/دستور به نود ناموجود → پاک
    seen, stack = set(), [cfg.get("start"), cfg.get("fallback"), *(cfg.get("commands") or {}).values()]
    while stack:
        nid = stack.pop()
        if nid in seen or nid not in nodes:
            continue
        seen.add(nid)
        n = nodes[nid]
        for row in n.get("buttons") or []:
            for b in row:
                if isinstance(b, dict) and b.get("goto"):
                    stack.append(b["goto"])
        for r in n.get("route") or []:
            if isinstance(r, dict) and r.get("goto"):
                stack.append(r["goto"])
        if n.get("next"):
            stack.append(n["next"])
    orphans = [nid for nid in nodes if nid not in seen and nid not in (cfg.get("start"), cfg.get("fallback"))]
    for nid in orphans:
        nodes.pop(nid)
        repairs.append("بخش یتیم حذف شد: " + nid)
    for cmd, nid in list((cfg.get("commands") or {}).items()):
        if nid not in nodes:
            cfg["commands"].pop(cmd)
            repairs.append("دستور /%s به بخش ناموجود اشاره می‌کرد؛ حذف شد" % cmd)
    # ۳) مسیر پیش‌فرض: نود بدون هیچ خروجی → دکمهٔ بازگشت به منو
    start = cfg.get("start")
    for nid, n in nodes.items():
        has_out = bool(n.get("next") or n.get("route") or any(
            isinstance(b, dict) and b.get("goto") for row in n.get("buttons") or [] for b in row))
        if nid != start and not has_out and not n.get("fields") and not n.get("ask"):
            n.setdefault("buttons", []).append([{"text": "منوی اصلی", "goto": start}])
            repairs.append("دکمهٔ بازگشت به بخش «%s» اضافه شد" % nid)
    # ۴) دکمه‌های goto به نود حذف‌شده → بدون مقصد نمی‌مانند
    for nid, n in nodes.items():
        rows = n.get("buttons") or []
        for row in rows:
            keep = []
            for b in row:
                if isinstance(b, dict) and b.get("goto") and b["goto"] not in nodes:
                    b = {k: v for k, v in b.items() if k != "goto"}
                    repairs.append("دکمهٔ بی‌مقصد در «%s» اصلاح شد" % nid)
                if isinstance(b, dict) and b.get("text"):
                    keep.append(b)
            row[:] = keep
    return repairs


# ───────────────────────── قالب‌های جامع (۳ قالب) ─────────────────────────
def _module_config(ids):
    """کانفیگ قطعی از ماژول‌های مسیر قدیمی (برای قالب فروشگاه/مدیریت)."""
    b = Builder("قالب", emoji=False, payments=False)
    b.shared["plans"] = {i: MODULES[i].params and {p["k"]: p["default"] for p in MODULES[i].params} or {} for i in ids}
    for mid in ids:
        m = MODULES[mid]
        b.have.add(mid)
        from modules import clean_params
        m.compile(b, clean_params(m, {}))
        b.titles.append(m.fa)
    return b.finish()


_GAME_SPEC = parse_spec({
    "name": "ربات بازی",
    "features": [
        {"type": "wallet", "start_bonus": 5},
        {"type": "daily", "amount": 1},
        {"type": "referral", "reward": 5},
        {"type": "leaderboard"},
        {"type": "game.dice", "bet": 2, "win_at": 5, "prize": 5},
        {"type": "game.guess", "max": 10, "rounds": 3, "reward": 8},
        {"type": "game.coinbet", "bet": 5},
        {"type": "game.quiz"},
        {"type": "game.wheel"},
    ],
})


def build_templates():
    """۳ قالب جامع و قطعی: ۱) فروشگاه و کسب‌وکار ۲) بازی و اقتصاد سکه ۳) مدیر گروه/کانال + پشتیبانی."""
    out = {}
    shop = _module_config(["shop", "support", "faq", "links"])
    shop["name"] = "فروشگاه من"
    out["shop"] = {
        "icon": "bag", "title": "فروشگاه و کسب‌وکار",
        "desc": "محصولات، سفارش، پشتیبانی تیکتی و سؤال‌های متداول",
        "feats": ["فهرست محصول و ثبت سفارش", "پشتیبانی و تیکت", "سؤال‌های متداول", "لینک‌ها"],
        "note": "این قالب با کامپایلر قطعی ساخته شده و همیشه معتبر است. محصولات و متن‌ها را از ویرایش دستی عوض کن.",
        "config": shop,
    }
    game_cfg = compile_spec(_GAME_SPEC)[1]
    out["game"] = {
        "icon": "medal", "title": "بازی و اقتصاد سکه",
        "desc": "کیف سکه، هدیهٔ روزانه، دعوت، ۵ بازی و برترین‌ها",
        "feats": ["کیف سکه و هدیهٔ ورود", "هدیهٔ روزانه و دعوت", "تاس، حدس عدد، شیر یا خط، مسابقه، گردونه", "برترین‌ها"],
        "note": "این قالب با کامپایلر قطعی از قابلیت‌های تست‌شدهٔ کاتالوگ ساخته شده است؛ جایزه‌ها و شرط‌ها را از ویرایش دستی عوض کن.",
        "config": game_cfg,
    }
    manage = _module_config(["group_manager", "support", "faq", "links"])
    manage["name"] = "مدیر گروه"
    out["manage"] = {
        "icon": "shield", "title": "مدیر گروه/کانال + پشتیبانی",
        "desc": "مدیریت گروه، پشتیبانی و سؤال‌های متداول",
        "feats": ["مدیریت گروه (کپچا، قفل، ضد اسپم)", "پشتیبانی و تیکت", "سؤال‌های متداول", "لینک‌ها"],
        "note": "این قالب با کامپایلر قطعی ساخته شده است. ربات را در گروه ادمین کن تا مدیریتش کار کند.",
        "config": manage,
    }
    return out
