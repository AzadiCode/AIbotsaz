# -*- coding: utf-8 -*-
"""
engine_accept.py — تست پذیرش Headless روی موتور واقعی (BUILD 3.6.0)

هدف: ممیزی نهایی بدون LLM. هر کانفیگ پیش از تحویل، روی توابع واقعی engine.py اجرا می‌شود:
  • ساخت کاربر آزمایشی (Env) روی دیتابیس تستی
  • اجرای واقعی اکشن‌ها (run_actions) و شرط‌ها (check)
  • شبیه‌سازی فشردن دکمه‌ها و طی‌کردن routeها
  • مشاهدهٔ متغیر قبل/بعد و تأیید نتیجه

منطق موتور دوباره پیاده‌سازی نشده؛ فقط همان توابع واقعی با Fake tg/DB اجرا می‌شوند (بدون اتصال تلگرام).

نام‌های پایدار: run_acceptance(), acceptance_ok(), walk_all_nodes()
"""

import engine
import defects


class _FakeTG:
    """کلاینت تلگرام جعلی: هیچ شبکه‌ای صدا زده نمی‌شود."""

    def __call__(self, token, method, **data):
        return {"ok": True, "result": {"message_id": 1, "dice": {"value": 4}}}


def _install_fake_tg():
    engine.tg = _FakeTG()


# ───────────────────────── ابزار داخلی ─────────────────────────
def _fresh_env(cfg, bot_id, uid):
    """کاربر آزمایشی تازه برای هر سناریو (متغیرها از مقدار اولیهٔ کانفیگ شروع می‌شوند)."""
    bot = {"_id": bot_id, "owner": "accept_owner", "config": cfg, "username": "accept_bot"}
    return engine.Env(bot, "T-ACCEPT", uid, {"id": uid, "first_name": "کاربر تست"}, "", "")


def _vars_of(cfg):
    return set((cfg.get("vars") or {}).keys()) | set((cfg.get("globals") or {}).keys())


def _all_buttons(node):
    out = []
    for row in node.get("buttons") or []:
        for b in row if isinstance(row, list) else [row]:
            if isinstance(b, dict):
                out.append(b)
    return out


def _pick_route(node, env):
    """اولین rule منطبق روی env (شبیه رفتار موتور)."""
    for r in node.get("route") or []:
        if engine.check(r.get("when") or {}, env):
            return r
    return None


def _walk(env, cfg, start, max_hops=12):
    """طی‌کردن مسیر اجرایی از یک نود با اجرای واقعی doها و routeها؛ خروجی: (مسیر، خطا)."""
    path, seen = [], set()
    nid = start
    for _ in range(max_hops):
        if nid in seen:
            break
        seen.add(nid)
        node = (cfg.get("nodes") or {}).get(nid)
        if node is None:
            return path, f"مسیر به بخش ناموجود ختم می‌شود: {nid}"
        path.append(nid)
        try:
            engine.run_actions(node.get("do"), env)
        except Exception as e:
            return path, f"اجرای اکشن‌های «{nid}» خطا داد: {type(e).__name__}: {e}"
        env.save()
        r = _pick_route(node, env)
        if r is None:
            return path, None
        nid = r.get("goto")
    return path, None


# ───────────────────────── تست عمومی هر کانفیگ ─────────────────────────
def walk_all_nodes(cfg, bot_id):
    """هر نود با do/route از همان نود اجرا می‌شود؛ خطای runtime یا مسیر شکسته = BUILD_DEFECT."""
    from ai import PH_RE, BUILTINS
    out = []
    nodes = cfg.get("nodes") or {}
    for nid, node in nodes.items():
        env = _fresh_env(cfg, bot_id, 900000 + hash(nid) % 100000)
        # متن نود با متغیرهای واقعی پر می‌شود؛ placeholder ناشناخته باقی می‌ماند = نقص
        try:
            engine.fill(str(node.get("text") or ""), env)
        except Exception as e:
            out.append(defects.build_defect("", f"اجرای بخش «{nid}»",
                                            f"fill خطا داد: {e}", stage="acceptance_test"))
            continue
        for m in PH_RE.finditer(str(node.get("text") or "")):
            k = m.group(1)
            if k not in BUILTINS and k not in _vars_of(cfg):
                out.append(defects.build_defect("", f"متغیر {k} در بخش «{nid}» استفاده شده ولی تعریف نشده است",
                                                "placeholder استفاده‌شده در متن، در vars/globals تعریف نشده",
                                                stage="acceptance_test"))
        # دکمه‌ها: اکشن‌هایشان باید اجرا شوند و مقصدشان موجود باشد
        for b in _all_buttons(node):
            try:
                engine.run_actions(b.get("do"), env)
            except Exception as e:
                out.append(defects.build_defect("", f"اکشن دکمه «{b.get('text')}» در «{nid}» اجرا نشد",
                                                f"{type(e).__name__}: {e}", stage="acceptance_test"))
            g = b.get("goto")
            if g and g not in nodes:
                out.append(defects.build_defect("", f"دکمه «{b.get('text')}» به بخش ناموجود «{g}» وصل است",
                                                "مقصد دکمه در nodes نیست", stage="acceptance_test"))
        # route: با env واقعی باید نتیجهٔ معتبر بدهد
        for r in node.get("route") or []:
            try:
                engine.check(r.get("when") or {}, env)
            except Exception as e:
                out.append(defects.build_defect("", f"شرط route «{nid}» ارزیابی نشد",
                                                f"{type(e).__name__}: {e}", stage="acceptance_test"))
            if r.get("goto") and r["goto"] not in nodes:
                out.append(defects.build_defect("", f"route «{nid}» به بخش ناموجود «{r['goto']}» می‌رود",
                                                "مقصد route در nodes نیست", stage="acceptance_test"))
        # اجرای ترکیبی do+route مثل رفتار موتور
        _, err = _walk(env, cfg, nid)
        if err:
            out.append(defects.build_defect("", f"اجرای زندهٔ بخش «{nid}» شکست خورد", err, stage="acceptance_test"))
    return out


# ───────────────────────── سناریوهای قابلیت‌محور ─────────────────────────
def _s_dice(cfg, bot_id):
    """تاس: مقدار تصادفی واقعی در دامنه؛ ثبت در متغیر؛ مسیر نتیجه معتبر."""
    out, nodes = [], cfg.get("nodes") or {}
    if "dice_roll" not in nodes:
        return out
    env = _fresh_env(cfg, bot_id, 910001)
    engine.run_actions(nodes["dice_roll"].get("do"), env)
    v = engine.to_num(env.get("dice_val"))
    if v is None or not (1 <= v <= 20):
        out.append(defects.build_defect("dice", "تولید مقدار تصادفی تاس و ثبت آن در متغیر",
                                        f"dice_val={env.get('dice_val')} خارج از دامنه است"))
    r = _pick_route(nodes["dice_roll"], env)
    if not r or r.get("goto") not in nodes:
        out.append(defects.build_defect("dice", "مسیر نتیجهٔ تاس",
                                        "route بعد از پرتاب به نود معتبر نمی‌رسد"))
    return out


def _s_guess(cfg, bot_id):
    """حدس عدد: بررسی واقعی انتخاب کاربر با مقدار هدف؛ امتیاز فقط برای حدس درست."""
    out, nodes = [], cfg.get("nodes") or {}
    if "guess_roll" not in nodes:
        return out
    env = _fresh_env(cfg, bot_id, 910002)
    env.set("g_pick", "1")
    engine.run_actions(nodes["guess_roll"].get("do"), env)
    target = env.get("g_target")
    if not target:
        out.append(defects.build_defect("guess", "تولید عدد هدف", "g_target بعد از random خالی است"))
        return out
    env.set("g_pick", str(target))
    if not engine.check({"var": "g_pick", "op": "==", "value": "{g_target}"}, env):
        out.append(defects.build_defect("guess", "بررسی انتخاب کاربر با مقدار هدف",
                                        "شرط برابری pick==target وقتی برابرند True نمی‌شود"))
    env.set("g_pick", str(int(target) + 1000))
    if not engine.check({"var": "g_pick", "op": "!=", "value": "{g_target}"}, env):
        out.append(defects.build_defect("guess", "بررسی انتخاب نادرست", "شرط نابرابری کار نمی‌کند"))
    win = nodes.get("guess_win")
    if not win:
        out.append(defects.build_defect("guess", "نمایش نتیجهٔ واقعی و ثبت امتیاز",
                                        "گرهٔ برد guess_win وجود ندارد"))
    elif not any(a.get("op") == "add" and a.get("var") == "g_score" for a in win.get("do") or []):
        out.append(defects.build_defect("guess", "ثبت امتیاز واقعی",
                                        "گرهٔ برد اکشن افزایش g_score ندارد"))
    return out


def _s_coinbet(cfg, bot_id):
    """شرط‌بندی: بررسی موجودی؛ کسر صحیح؛ بدون منفی‌شدن؛ کنترل نتیجه."""
    out, nodes = [], cfg.get("nodes") or {}
    if "bet_go" not in nodes or "bet_check" not in nodes:
        return out
    env = _fresh_env(cfg, bot_id, 910003)
    env.set("coins", "10")
    env.set("bet_amt", "4")
    env.save()
    r = _pick_route(nodes["bet_check"], env)
    if not r or r.get("goto") != "bet_go":
        out.append(defects.build_defect("coinbet", "بررسی موجودی و جلوگیری از شرط بیشتر از موجودی",
                                        f"با coins=10 و bet=4 مسیر به {r and r.get('goto')} رفت (انتظار bet_go)"))
    engine.run_actions(nodes["bet_go"].get("do"), env)
    c = engine.to_num(env.get("coins"))
    if c is None or abs(c - 6.0) > 1e-9:
        out.append(defects.build_defect("coinbet", "کسر صحیح مبلغ شرط",
                                        f"موجودی بعد از شرط ۴ از ۱۰ برابر {c} شد (انتظار ۶)"))
    r = _pick_route(nodes["bet_go"], env)
    if not r or r.get("goto") not in ("bet_win", "bet_lose"):
        out.append(defects.build_defect("coinbet", "کنترل نتیجهٔ شرط",
                                        f"route به {r and r.get('goto')} می‌رود"))
    env2 = _fresh_env(cfg, bot_id, 910004)
    env2.set("coins", "2")
    env2.set("bet_amt", "4")
    env2.save()
    r2 = _pick_route(nodes["bet_check"], env2)
    if not r2 or r2.get("goto") != "bet_no":
        out.append(defects.build_defect("coinbet", "جلوگیری از شرط بیشتر از موجودی",
                                        f"با coins=2 و bet=4 مسیر به {r2 and r2.get('goto')} رفت (انتظار bet_no)"))
        engine.run_actions(nodes["bet_go"].get("do"), env2)
        c2 = engine.to_num(env2.get("coins"))
        if c2 is not None and c2 < 0:
            out.append(defects.build_defect("coinbet", "جلوگیری از منفی‌شدن موجودی",
                                            f"موجودی {c2} شد"))
    return out


def _s_quiz(cfg, bot_id):
    """کوییز: جواب درست امتیاز می‌گیرد؛ نادرست نمی‌گیرد؛ مقصد سؤال بعدی موجود است."""
    out, nodes = [], cfg.get("nodes") or {}
    if "quiz" not in nodes:
        return out
    env = _fresh_env(cfg, bot_id, 910005)
    btns = _all_buttons(nodes["quiz"])
    scored = [b for b in btns if any(a.get("op") == "add" and a.get("var") == "qscore" for a in b.get("do") or [])]
    plain = [b for b in btns if not any(a.get("op") == "add" for a in b.get("do") or [])]
    if not scored:
        out.append(defects.build_defect("quiz", "افزایش امتیاز واقعی برای جواب درست",
                                        "هیچ گزینه‌ای اکشن افزایش qscore ندارد"))
    if not plain:
        out.append(defects.build_defect("quiz", "جواب نادرست نباید امتیاز بگیرد",
                                        "همهٔ گزینه‌ها امتیاز می‌گیرند"))
    env.set("qscore", "0")
    if scored:
        engine.run_actions(scored[0].get("do"), env)
        if engine.to_num(env.get("qscore")) != 1:
            out.append(defects.build_defect("quiz", "امتیاز یک‌بار افزایش می‌یابد",
                                            f"qscore={env.get('qscore')}"))
    for b in plain:
        if b.get("goto") and b["goto"] not in nodes:
            out.append(defects.build_defect("quiz", "رفتن به سؤال بعدی یا نتیجه",
                                            f"گزینه به «{b['goto']}» می‌رود که وجود ندارد"))
    return out


def _s_wheel(cfg, bot_id):
    """گردونه: مسیر واقعی از wheel_go دنبال می‌شود؛ جایزه واقعاً اعطا می‌شود."""
    out, nodes = [], cfg.get("nodes") or {}
    if "wheel_go" not in nodes:
        return out
    env = _fresh_env(cfg, bot_id, 910006)
    # منابع بلیت واقعی را می‌کاریم: دعوت‌های واقعی (refs) و بلیت روزانه (اگر بخشی از طرح است)
    env.refs = 4
    if "tk_bonus" in _vars_of(cfg):
        env.set("tk_bonus", "1")
        env.save()
    engine.run_actions(nodes["wheel_go"].get("do"), env)
    r = _pick_route(nodes["wheel_go"], env)
    if not r or r.get("goto") not in nodes:
        out.append(defects.build_defect("wheel", "بررسی بلیت و اجازهٔ چرخش",
                                        f"route از wheel_go به {r and r.get('goto')} می‌رود (نامعتبر یا None)"))
        return out
    nid = r["goto"]
    # حداکثر ۴ گام در زنجیرهٔ چرخش (wheel_pre → wheel_spin → …) با اجرای واقعی
    coins_before = engine.to_num(env.get("coins"))
    awarded = False
    for _ in range(4):
        node = nodes.get(nid)
        if node is None:
            out.append(defects.build_defect("wheel", "مسیر چرخش به بخش ناموجود می‌رسد",
                                            f"{nid} در nodes نیست"))
            return out
        engine.run_actions(node.get("do"), env)
        env.save()
        if any(a.get("op") == "add" and a.get("var") == "coins" for a in node.get("do") or []):
            awarded = True
        rr = _pick_route(node, env)
        if rr is None:
            break
        nid = rr.get("goto")
    coins_after = engine.to_num(env.get("coins"))
    if not awarded:
        out.append(defects.build_defect("wheel", "اعطای واقعی جایزه در انتهای زنجیرهٔ چرخش",
                                        "هیچ گره‌ای در مسیر، اکشن add coins ندارد"))
    elif coins_after is not None and coins_before is not None and coins_after <= coins_before:
        out.append(defects.build_defect("wheel", "اعطای واقعی جایزه",
                                        f"coins از {coins_before} به {coins_after} تغییر نکرد"))
    return out


def _s_daily(cfg, bot_id):
    """روزانه: اولین دریافت هدیه؛ دوباره در همان روز نمی‌گیرد."""
    out, nodes = [], cfg.get("nodes") or {}
    if "daily" not in nodes:
        return out
    env = _fresh_env(cfg, bot_id, 910007)
    r = _pick_route(nodes["daily"], env)
    if not r or r.get("goto") != "daily_get":
        out.append(defects.build_defect("daily", "دریافت هدیه روزانه یک‌بار در روز",
                                        f"روز اول مسیر به {r and r.get('goto')} رفت (انتظار daily_get)"))
    engine.run_actions(nodes.get("daily_get", {}).get("do"), env)
    today = env.get("last_daily")
    if not today:
        out.append(defects.build_defect("daily", "کنترل روز و تاریخ",
                                        "last_daily بعد از دریافت ثبت نشد"))
    else:
        r2 = _pick_route(nodes["daily"], env)
        if not r2 or r2.get("goto") != "daily_done":
            out.append(defects.build_defect("daily", "جلوگیری از دریافت چندباره در همان روز",
                                            f"دومین بار مسیر به {r2 and r2.get('goto')} رفت (انتظار daily_done)"))
    return out


def _s_wallet(cfg, bot_id):
    """کیف پول: متغیر موجودی تعریف؛ تغییرات موجودی صحیح ثبت می‌شود."""
    out, nodes = [], cfg.get("nodes") or {}
    if "wallet" not in nodes:
        return out
    if "coins" not in _vars_of(cfg):
        out.append(defects.build_defect("wallet", "تعریف متغیر موجودی", "coins در vars/globals نیست"))
    env = _fresh_env(cfg, bot_id, 910008)
    engine.run_actions([{"op": "add", "var": "coins", "value": "3"}], env)
    if engine.to_num(env.get("coins")) != 3:
        out.append(defects.build_defect("wallet", "ثبت صحیح تغییرات موجودی",
                                        f"add coins=3 → {env.get('coins')}"))
    return out


def _s_leaderboard(cfg, bot_id):
    """رتبه‌بندی: بر اساس متغیر معتبر با board واقعی موتور."""
    out, nodes = [], cfg.get("nodes") or {}
    board_node = next((n for n in nodes.values() if isinstance(n.get("board"), dict)), None)
    if not board_node:
        return out
    var = board_node["board"].get("var")
    if var not in _vars_of(cfg) and var != "refs":
        out.append(defects.build_defect("leaderboard", "رتبه‌بندی بر اساس متغیر معتبر",
                                        f"متغیر {var} تعریف نشده"))
    env = _fresh_env(cfg, bot_id, 910009)
    try:
        txt = engine.board_text(env, board_node["board"])
        if not txt:
            out.append(defects.build_defect("leaderboard", "نمایش جدول برترین‌ها",
                                            "خروجی board_text خالی است"))
    except Exception as e:
        out.append(defects.build_defect("leaderboard", "نمایش جدول برترین‌ها",
                                        f"{type(e).__name__}: {e}"))
    return out


def _s_group_manager(cfg, bot_id):
    """قرارداد قطعی ماژول مدیر گروه و اتصال مسیرهای واقعی پردازش گروه."""
    out = []
    mod = cfg.get("mod") or {}
    required = ("captcha", "lock", "flood", "warns", "clean")
    missing = [k for k in required if k not in mod]
    if missing:
        out.append(defects.build_defect("group_manager", "تولید تنظیمات پایه مدیریت گروه",
                                        "کلیدهای کانفیگ مدیریتی تولید نشدند: " + ", ".join(missing),
                                        stage="acceptance_test"))
    for name in ("mod_group", "mod_command", "mod_join", "mod_captcha_cb", "mod_kick",
                 "mod_restrict", "_group_settings_callback", "_group_settings_message",
                 "_group_settings_list", "_group_settings_values", "_group_settings_authorized",
                 "_group_settings_required_permission", "group_mod_config", "sync_commands"):
        if not callable(getattr(engine, name, None)):
            out.append(defects.build_defect("group_manager", f"اتصال هندلر {name}",
                                            "هندلر اجرایی مدیریت گروه در موتور موجود نیست",
                                            stage="acceptance_test"))
    if "group_manager" not in __import__("modules").MODULES:
        out.append(defects.build_defect("group_manager", "ثبت ماژول مدیریت گروه",
                                        "ماژول در کاتالوگ ثبت نشده", stage="acceptance_test"))
    if "my_chat_member" not in engine.allowed_updates(cfg):
        out.append(defects.build_defect("group_manager", "دریافت رخداد عضویت/ارتقای ربات در گروه",
                                        "my_chat_member در allowed_updates فعال نیست",
                                        stage="acceptance_test"))
    return out


_SCENARIOS = {"dice": _s_dice, "guess": _s_guess, "coinbet": _s_coinbet, "quiz": _s_quiz,
              "wheel": _s_wheel, "daily": _s_daily, "wallet": _s_wallet,
              "leaderboard": _s_leaderboard, "group_manager": _s_group_manager}


# ───────────────────────── نقطهٔ ورود ─────────────────────────
def run_acceptance(cfg, feature_ids=(), bot_id=None):
    """اجرای تست پذیرش روی موتور واقعی → فهرست BUILD_DEFECT (خالی = پذیرفته)."""
    import core
    bot_id = bot_id or core.ObjectId()
    _install_fake_tg()
    out = walk_all_nodes(cfg, bot_id)
    try:
        core.db.uvars.delete_many({"bot": str(bot_id)})
    except Exception:
        pass
    for fid in feature_ids or []:
        fn = _SCENARIOS.get(fid)
        if fn:
            out += fn(cfg, bot_id)
    # حذف موارد تکراری
    seen, uniq = set(), []
    for d in out:
        k = (d.get("feature"), d.get("want"), d.get("evidence"))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(d)
    return uniq


def acceptance_ok(defects_list):
    return not defects_list
