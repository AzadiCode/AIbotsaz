# -*- coding: utf-8 -*-
"""
test_catalog.py — تست پذیرش کاتالوگ Spec ← Compiler

هر قابلیت کاتالوگ یک تست پذیرش دارد که «روی موتور واقعی» (engine.py) اجرا می‌شود:
دکمه واقعی می‌زنیم (callback مثل تلگرام به /hook می‌رسد) و تغییر متغیر/ارسال پیام را
در db شبیه‌سازی‌شده می‌بینیم. pass/fail یک واقعیت قابل‌اجراست، نه قضاوت LLM.

اجرا (از ریشه‌ی پروژه):  python tests/test_catalog.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Sim, SENT, get_engine  # noqa: E402

get_engine()  # موتور + همه‌ی مسیرها پیش از تست‌ها بالا می‌آیند

import catalog  # noqa: E402
from ai import sanitize, lint  # noqa: E402

PASS, FAIL = [], []


def check(name, fn):
    try:
        fn()
        PASS.append(name)
        print("PASS  " + name)
    except Exception as e:  # noqa: BLE001
        FAIL.append((name, e))
        print("FAIL  " + name + "  ←  " + repr(e)[:200])


def spec_of(features_json):
    return catalog.parse_spec('{"name":"ربات تست","features":%s}' % features_json)


def built(features_json, extra=None):
    spec = spec_of(features_json)
    if extra:
        spec.update(extra)
    th, cfg, ideas = catalog.compile_spec(spec)
    return spec, sanitize(cfg, strict=False)


# ───────────────────────── تست‌های پذیرش روی موتور ─────────────────────────

def t_wallet():
    _, cfg = built('[{"type":"wallet","start_bonus":10}]')
    s = Sim(cfg)
    s.start()
    assert s.var("coins") == "10", s.vars()
    assert s.var("welcomed") == "1"
    s.start()                                   # ورود دوم: هدیه دوباره نمی‌آید
    assert s.var("coins") == "10", "هدیه ورود دوبار اعمال شد!"
    assert "10" in s.last_text()
    s.press_label("start", "کیف سکه")
    assert s.var("coins") == "10" and "کیف" in s.last_text()


def t_daily():
    _, cfg = built('[{"type":"wallet","start_bonus":0},{"type":"daily","amount":2}]')
    s = Sim(cfg)
    s.start()
    assert s.var("coins") == "0"
    s.press_label("start", "هدیهٔ روزانه")
    assert s.var("coins") == "2", s.vars()
    assert s.var("last_daily") != ""
    s.press_label("start", "هدیهٔ روزانه")       # همان روز: فقط یک‌بار
    assert s.var("coins") == "2", "هدیه روزانه دوبار اعمال شد!"
    assert "گرفته‌ای" in s.last_text()


def t_referral():
    _, cfg = built('[{"type":"wallet","start_bonus":0},{"type":"referral","reward":3}]')
    assert cfg.get("on_ref") and cfg["on_ref"][0]["op"] == "add"
    board = (cfg["nodes"].get("invite_top") or {}).get("board") or {}
    assert board.get("var") == "refs" and board.get("top") == 10, board
    s = Sim(cfg)
    s.start()
    s.press_label("start", "دعوت دوستان")
    assert "{ref_link}" in cfg["nodes"]["invite"]["text"]
    assert "دعوت دوستان" in " ".join(s.sent_texts())
    assert cfg.get("ref_text") and "3" in cfg["ref_text"]


def t_leaderboard():
    _, cfg = built('[{"type":"wallet","start_bonus":7},{"type":"leaderboard","top":10}]')
    s = Sim(cfg)
    s.start()                                   # +7 سکه
    s.press_label("start", "برترین‌ها")
    txt = s.last_text()
    assert "تست" in txt or "برترین" in txt, txt[:100]      # جدول واقعی از db خوانده شد


def t_game_dice():
    _, cfg = built('[{"type":"wallet","start_bonus":50},{"type":"game.dice","bet":2,"win_at":5,"prize":6}]')
    s = Sim(cfg)
    s.start()
    assert s.var("coins") == "50"
    SENT.dice_value = 6                          # تاس جعلی: برد (>= 5)
    s.press_label("start", "بازی تاس")
    s.press_label("dice", "بازی کن")
    assert s.var("die_val") == "6", s.vars()
    assert s.var("coins") == "54", s.vars()      # -2 شرط + 6 جایزه
    assert "گرفتی" in " ".join(s.sent_texts())
    SENT.dice_value = 1                          # باخت
    s.press_label("dice_win", "یک بار دیگر")
    assert s.var("coins") == "52", s.vars()      # فقط -2 شرط
    SENT.dice_value = 6


def t_game_dice_free():
    _, cfg = built('[{"type":"wallet","start_bonus":5},{"type":"game.dice","bet":0,"win_at":5,"prize":3}]')
    s = Sim(cfg)
    s.start()
    SENT.dice_value = 6
    s.press_label("start", "بازی تاس")
    s.press_label("dice", "بازی کن")             # بدون شرط: مستقیم می‌چرخد
    assert s.var("coins") == "8", s.vars()      # 5 + 3 جایزه
    SENT.dice_value = 6


def t_game_dice_no_coins():
    _, cfg = built('[{"type":"wallet","start_bonus":1},{"type":"game.dice","bet":20,"win_at":5,"prize":6}]')
    s = Sim(cfg)
    s.start()
    SENT.dice_value = 6
    s.press_label("start", "بازی تاس")
    s.press_label("dice", "بازی کن")
    assert s.var("coins") == "1", "شرط با موجودی کم نباید اجرا شود"
    assert "لازم داری" in " ".join(s.sent_texts())
    SENT.dice_value = 6


def t_game_guess():
    _, cfg = built('[{"type":"wallet","start_bonus":0},{"type":"game.guess","max":10,"rounds":3,"reward":8}]')
    s = Sim(cfg)
    s.start()
    s.press_label("start", "حدس عدد")
    s.press_label("guess", "شروع بازی")
    secret = int(s.var("guess_num"))
    assert 1 <= secret <= 10
    assert s.var("guess_tries") == "0"
    # حدس درست → برد
    s.press_label("guess_pick", str(secret))
    assert s.var("coins") == "8", s.vars()
    assert "درست حدس زدی" in " ".join(s.sent_texts())


def t_game_guess_hints_and_end():
    _, cfg = built('[{"type":"wallet","start_bonus":0},{"type":"game.guess","max":10,"rounds":2,"reward":8}]')
    s = Sim(cfg)
    s.start()
    s.press_label("start", "حدس عدد")
    s.press_label("guess", "شروع بازی")
    secret = int(s.var("guess_num"))
    wrong = 1 if secret != 1 else 2
    s.press_label("guess_pick", str(wrong))      # حدس غلط اول → راهنما
    assert s.var("guess_tries") == "1"
    assert ("بزرگ‌تر" in " ".join(s.sent_texts())) or ("کوچک‌تر" in " ".join(s.sent_texts()))
    # از صفحهٔ راهنما ادامه بده؛ حدس غلط دوم → پایان (2 حدس تمام شد)
    s.press_label("guess_hi", "ادامهٔ حدس") if "guess_hi" in cfg["nodes"] else s.press_label("guess_lo", "ادامهٔ حدس")
    s.press_label("guess_pick", str(wrong))
    assert s.var("coins") == "0", "نباید جایزه می‌گرفت"
    assert "تمام شد" in " ".join(s.sent_texts())


def t_game_coinbet():
    _, cfg = built('[{"type":"wallet","start_bonus":10},{"type":"game.coinbet","bet":4}]')
    s = Sim(cfg)
    s.start()
    assert s.var("coins") == "10"
    import engine
    orig_random = engine.random
    try:
        engine.random = _FixedRandom(1)         # شیر → برد
        s.press_label("start", "شیر یا خط")
        s.press_label("coinbet", "شرط ببند")
        assert s.var("flip") == "1", s.vars()
        assert s.var("coins") == "14", s.vars()  # -4 شرط + 8 برد
        engine.random = _FixedRandom(0)         # خط → باخت
        s.press_label("cb_win", "دوباره")
        assert s.var("coins") == "10", s.vars()  # -4 شرط
        assert "باختی" in " ".join(s.sent_texts())
    finally:
        engine.random = orig_random


class _FixedRandom:
    def __init__(self, value):
        self._v = value

    def randint(self, a, b):
        return self._v

    def __getattr__(self, name):
        import random as _r
        return getattr(_r, name)


def t_game_quiz():
    _, cfg = built('[{"type":"wallet","start_bonus":0},{"type":"game.quiz"}]')
    s = Sim(cfg)
    s.start()
    s.press_label("start", "مسابقه")
    q1 = cfg["nodes"]["quiz"]
    right = q1["buttons"][0][0] if not q1["buttons"][0][0].get("do") else _find_do(q1)
    # گزینهٔ درست = آن که do دارد (qscore + 1)
    label = _correct_label(cfg, "quiz")
    s.press_label("quiz", label)
    assert s.var("qscore") == "1", s.vars()
    label2 = _correct_label(cfg, "quiz_2")
    s.press_label("quiz_2", label2)
    assert s.var("qscore") == "2"
    assert "2" in s.last_text()                 # امتیاز نهایی


def _correct_label(cfg, nid):
    for row in cfg["nodes"][nid]["buttons"]:
        for b in row:
            if b.get("do"):
                return b["text"]
    raise AssertionError("گزینهٔ درست پیدا نشد")


def _find_do(node):
    for row in node["buttons"]:
        for b in row:
            if b.get("do"):
                return b
    return None


def t_game_wheel():
    _, cfg = built('[{"type":"wallet","start_bonus":3},{"type":"game.wheel","prizes":[1,2,3,5,10,20]}]')
    s = Sim(cfg)
    s.start()
    import engine
    orig_random = engine.random
    try:
        engine.random = _FixedRandom(1)         # roll=1 → جایزهٔ اول
        s.press_label("start", "گردونهٔ شانس")
        s.press_label("wheel", "بچرخان")
        assert s.var("coins") == "4", s.vars()   # 3 + 1
        assert s.var("roll") == "1"
        assert s.var("last_spin") != ""
        s.press_label("wheel_r1", "یک بار دیگر")  # همان روز: چرخش دوباره نه
        assert s.var("coins") == "4", "چرخش دوبار همان روز!"
        assert "فردا" in " ".join(s.sent_texts())
        # از منو هم دوباره می‌رویم و باز همان روز قفل است
        s.press_label("start", "گردونهٔ شانس")
        s.press_label("wheel", "بچرخان")
        assert s.var("coins") == "4"
        assert "فردا" in " ".join(s.sent_texts())
    finally:
        engine.random = orig_random


# ───────────────────────── sanitize/lint همه‌ی ترکیب‌ها ─────────────────────────

def t_sanitize_all_features():
    for fid in catalog.FEATURE_ORDER:
        _, cfg = built('[{"type":"%s"}]' % fid)
        w = []
        sanitize(cfg, strict=False, warns=w)
        assert not w, (fid, w)
        li = [x for x in lint(cfg) if not x.startswith("variables that are read but never set")]
        assert not li, (fid, li)


def t_sanitize_full_game():
    feats = [{"type": fid} for fid in catalog.FEATURE_ORDER]
    _, cfg = built(json_feats(feats))
    w = []
    sanitize(cfg, strict=False, warns=w)
    assert not w, w
    li = [x for x in lint(cfg) if not x.startswith("variables that are read but never set")]
    assert not li, li


def json_feats(feats):
    import json
    return json.dumps(feats)


def t_templates():
    t = catalog.build_templates()
    assert set(t) == {"shop", "game", "manage"}, set(t)
    for k, v in t.items():
        w = []
        sanitize(v["config"], strict=False, warns=w)
        assert not w, (k, w)
        assert not lint(v["config"]), (k, lint(v["config"]))
    # پذیرش قالب بازی روی موتور: منو کامل بالا می‌آید
    s = Sim(t["game"]["config"])
    s.start()
    btns = s.buttons("start")
    for want in ("کیف سکه", "هدیهٔ روزانه", "دعوت دوستان", "برترین‌ها", "بازی تاس", "حدس عدد", "شیر یا خط", "مسابقه", "گردونهٔ شانس"):
        assert want in btns, (want, btns)


# ───────────────────────── Spec: اعتبارسنجی enum بسته ─────────────────────────

def t_parse_spec():
    s = catalog.parse_spec('{"features":[{"type":"game.guess","rounds":3,"reward":10},{"type":"wallet"},{"type":"leaderboard"}]}')
    assert [f for f, _ in s["features"]] == ["game.guess", "wallet", "leaderboard"]
    p = dict(s["features"])[0] if False else dict(s["features"])["game.guess"]
    assert p["rounds"] == 3 and p["reward"] == 10 and p["max"] == 10
    # متن قابل‌سفارشی
    s2 = catalog.parse_spec('{"features":[{"type":"game.dice"}],"texts":{"game.dice":{"win":"برد بزرگ!"}}}')
    _, cfg2 = built('[{"type":"game.dice"}]', extra={"texts": s2["texts"]})
    assert "برد بزرگ!" in cfg2["nodes"]["dice_win"]["text"]


def t_parse_spec_rejects():
    for bad in ('{"features":[{"type":"bank.gateway"}]}',                # enum بسته
                '{"features":[]}',                                        # خالی
                'not json at all',                                        # نحوی
                '{"features":"nope"}',                                    # نوع اشتباه
                '{"features":[{}]}'):                                     # بدون type
        try:
            catalog.parse_spec(bad)
            raise AssertionError("باید رد می‌شد: " + bad)
        except catalog.SpecError:
            pass
    # پارامتر خارج از بازه → به سقف/کف بریده می‌شود، هرگز خام عبور نمی‌کند
    s = catalog.parse_spec('{"features":[{"type":"game.guess","max":99,"rounds":-2}]}')
    p = dict(s["features"])["game.guess"]
    assert p["max"] == 12 and p["rounds"] == 1, p


def t_keyword_router():
    s = catalog.keyword_spec("یک ربات بازی بساز با گردونه و هدیه روزانه 5 سکه")
    assert s and {f for f, _ in s["features"]} >= {"game.wheel", "daily"}
    p = dict(s["features"])
    assert p["daily"]["amount"] == 5, p
    s2 = catalog.keyword_spec("ربات فروشگاه بساز")
    assert s2 is None or not s2["features"]      # فروشگاه در کاتالوگ نیست → مسیر fallback


def t_auto_wallet():
    spec = spec_of('[{"type":"daily"}]')
    th, cfg, _ = catalog.compile_spec(spec)
    assert "coins" in cfg["vars"]
    assert any(b["text"].startswith("کیف") for row in cfg["nodes"]["start"]["buttons"] for b in row)


def t_texts_no_html():
    s = catalog.parse_spec('{"features":[{"type":"game.dice"}],"texts":{"game.dice":{"win":"<script>x</script> برد {injected} <b>OK</b>"}}}')
    th, cfg, _ = catalog.compile_spec(s)
    txt = cfg["nodes"]["dice_win"]["text"]
    assert "{injected}" not in txt, txt          # جای‌نگهدار تزریقی حذف می‌شود
    from core import plain_html
    assert "<script" not in plain_html(txt)    # زمان ارسال، تگ نامعتبر حذف و متن امن می‌رسد


# ───────────────────────── ترمیم قطعی ─────────────────────────

def t_repair_config():
    import copy
    _, cfg = built('[{"type":"wallet","start_bonus":3},{"type":"daily"}]')
    bad = copy.deepcopy(cfg)
    # متغیر استفاده‌شده اما اعلان‌نشده
    bad["nodes"]["daily"]["text"] += "\nموجودی: {ghost_var}"
    # نود یتیم
    bad["nodes"]["orphan1"] = {"text": "یتیم", "buttons": []}
    # نود بن‌بست
    bad["nodes"]["daily_done"]["buttons"] = []
    bad["vars"].pop("welcomed", None)            # متغیر اعلان‌نشده
    bad["nodes"]["daily"]["text"] += " {welcomed}"
    repairs = catalog.repair_config(bad)
    joined = " ".join(repairs)
    assert "ghost_var" in joined or "welcomed" in joined, repairs
    assert "orphan1" not in bad["nodes"]
    assert bad["vars"].get("welcomed") == "0" or bad["vars"].get("ghost_var") == "0"
    has_back = any(b.get("goto") for row in bad["nodes"]["daily_done"]["buttons"] for b in row)
    assert has_back, "نود بن‌بست دکمهٔ بازگشت نگرفت"
    w = []
    sanitize(bad, strict=False, warns=w)
    assert not w, w


def t_repair_idempotent():
    _, cfg = built('[{"type":"wallet"},{"type":"game.quiz"}]')
    first = catalog.repair_config(cfg)
    second = catalog.repair_config(cfg)
    assert first == second == [] or first == second


# ───────────────────────── ادغام با ربات موجود (پیشوند) ─────────────────────────

def t_merge_prefix():
    spec, cfg1 = built('[{"type":"wallet","start_bonus":2},{"type":"daily"}]')
    # ربات موجود با نود هم‌نام (daily هم那儿 هست) → پیشوند بدون برخورد
    spec2, cfg2 = built('[{"type":"game.guess"},{"type":"game.wheel"}]')
    merged = catalog.merge_spec_config(cfg1, cfg2)
    w = []
    merged2 = sanitize(merged, strict=False, warns=w)
    assert not w, w
    assert not lint(merged2), lint(merged2)
    assert "daily" in merged2["nodes"] and any(n.startswith("f1_") or n.startswith("f2_") for n in merged2["nodes"])
    # دکمهٔ ورود به قابلیت تازه در منو هست
    labels = [b["text"] for row in merged2["nodes"]["start"]["buttons"] for b in row]
    assert any("حدس عدد" in x for x in labels), labels
    # اجرای موتور: بازی تازه داخل ربات ادغام‌شده کار می‌کند
    s = Sim(merged2)
    s.start()
    s.press_label("start", "حدس عدد")
    s.press_label(_node_of(merged2, "guess"), "شروع بازی")
    assert s.var("guess_num") != ""


def _node_of(cfg, suffix):
    for nid in cfg["nodes"]:
        if nid == suffix or nid.endswith("_" + suffix) or nid.endswith(suffix):
            return nid
    raise AssertionError("نود پیدا نشد: " + suffix)


# ───────────────────────── CATALOG_MISSING / پیش‌نمایش ─────────────────────────

def t_catalog_missing():
    spec = spec_of('[{"type":"wallet"}]')
    items = catalog.catalog_missing("ربات فروشگاه با پشتیبانی و ماینر", spec)
    wants = {x["want"] for x in items}
    assert "فروشگاه و سفارش محصول" in wants, wants
    assert all(x["kind"] == "CATALOG_MISSING" and x["severity"] and x["feature"] and x["criterion"] for x in items)
    # چیزی که کاتالوگ دارد نباید MISSING گزارش شود
    items2 = catalog.catalog_missing("ربات گردونه و تاس بساز", spec_of('[{"type":"game.wheel"},{"type":"game.dice"}]'))
    assert not any("گردونه" in x["want"] or "تاس" in x["want"] for x in items2), items2


def t_preview():
    pv = catalog.preview_spec(spec_of('[{"type":"game.guess"}]'))
    assert all(x["status"] == "ok" for x in pv)
    labels = " ".join(x["text"] for x in pv)
    assert "حدس عدد" in labels and "خودکار" in labels      # کیف خودکار اعلام شد


def t_spec_prompt_closed():
    txt = catalog.spec_prompt()
    for fid in catalog.FEATURE_ORDER:
        assert fid in txt
    assert "game.dice" in txt and "wallet" in txt


# ───────────────────────── اجرا ─────────────────────────
TESTS = [
    ("wallet", t_wallet),
    ("daily", t_daily),
    ("referral", t_referral),
    ("leaderboard", t_leaderboard),
    ("game.dice (win/lose/bet)", t_game_dice),
    ("game.dice (free)", t_game_dice_free),
    ("game.dice (insufficient coins)", t_game_dice_no_coins),
    ("game.guess (win)", t_game_guess),
    ("game.guess (hints + end)", t_game_guess_hints_and_end),
    ("game.coinbet (win/lose)", t_game_coinbet),
    ("game.quiz (score)", t_game_quiz),
    ("game.wheel (prize + once per day)", t_game_wheel),
    ("sanitize: هر قابلیت جدا", t_sanitize_all_features),
    ("sanitize: همه با هم", t_sanitize_full_game),
    ("templates: 3 قالب + اجرای قالب بازی", t_templates),
    ("parse_spec (enum + پارامتر + متن)", t_parse_spec),
    ("parse_spec: رد ورودی خراب", t_parse_spec_rejects),
    ("روتر کلیدواژه‌ای", t_keyword_router),
    ("کیف خودکار", t_auto_wallet),
    ("متن‌ها بدون HTML خام", t_texts_no_html),
    ("repair_config (متغیر/یتیم/بن‌بست)", t_repair_config),
    ("repair_config: پایداری", t_repair_idempotent),
    ("ادغام با ربات موجود (پیشوند)", t_merge_prefix),
    ("CATALOG_MISSING", t_catalog_missing),
    ("preview ✔", t_preview),
    ("پرامپت Spec", t_spec_prompt_closed),
]

if __name__ == "__main__":
    for name, fn in TESTS:
        check(name, fn)
    print("\n%d PASS / %d FAIL" % (len(PASS), len(FAIL)))
    if FAIL:
        for n, e in FAIL:
            print(" FAILED:", n, "→", repr(e)[:300])
        sys.exit(1)
    print("کاتالوگ: همه‌ی تست‌های پذیرش روی موتور پاس شدند.")
