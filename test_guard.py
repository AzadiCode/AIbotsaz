"""
تست شبیه‌سازی‌شده (بدون تلگرام و بدون شبکه) برای نگهبان یوزربات و زمان‌بند.
توابع واقعی از mother.py با AST بیرون کشیده و با ساعت جعلی و کلاینت جعلی اجرا می‌شوند.
"""
import ast, asyncio as real_asyncio, html as _html, io, logging, random, re, types, sys
from collections import deque
from datetime import datetime, timedelta, timezone

SRC = open("mother.py", encoding="utf-8").read()
TREE = ast.parse(SRC)

FUNCS = """_ub_dur _ub_hhmm _ub_ev _ub_snap _ub_pen _ub_ramp _ub_eff _ub_day_n _ub_next_hour _ub_ps_save _ub_flood _ub_fatal _ub_dead _ub_catch
_ub_end_cycle _ub_post_state _ub_acct_view _ub_ps_view _ub_sched_tick _ub_send_post _ub_cmap _ub_hour _ub_in_window _ub_errs _ub_learned _ub_learn _ub_caps
_ub_media_banned _ub_sk _ub_pick_reply _ub_forward _ub_has_links _ub_strip_links _ub_fwd_clean _ub_fwd_parse""".split()
ASSIGNS = "UB_PROF UB_FATAL UB_NETERR UB_FATAL_T UB_RAMP _UB_URL_RE _UB_ID_RE _UB_MEDIA_BAN".split()


class Clock:
    t = 1_800_000_000.0     # یک نقطه‌ی ثابت (۱۲:۰۰ تهران تقریباً؛ پایین‌تر تنظیم می‌شود)


clk = Clock()


class FakeTime:
    @staticmethod
    def time():
        return clk.t


async def fake_sleep(sec):
    clk.t += sec
    if HOOKS.get("sleep"):
        HOOKS["sleep"](sec)


HOOKS = {}

# ── استثناهای جعلی هم‌نام Telethon ──
class RPC(Exception):
    pass


def mk(name, base=RPC):
    return type(name, (base,), {})


class FloodWaitError(RPC):
    def __init__(self, seconds):
        self.seconds = seconds


class SlowModeWaitError(RPC):
    def __init__(self, seconds):
        self.seconds = seconds


tl_err = types.SimpleNamespace(FloodWaitError=FloodWaitError, SlowModeWaitError=SlowModeWaitError)
for n in ("PeerFloodError ChatWriteForbiddenError UserBannedInChannelError ChatAdminRequiredError ChannelPrivateError ChatRestrictedError "
          "ChatGuestSendForbiddenError UserNotParticipantError UserDeactivatedBanError UserDeactivatedError AuthKeyUnregisteredError "
          "AuthKeyDuplicatedError SessionRevokedError SessionExpiredError TimedOutError ServerError MessageIdInvalidError").split():
    setattr(tl_err, n, mk(n))


def now():
    return datetime.fromtimestamp(clk.t, timezone.utc)


def tehran_day(back=0):
    return (now() + timedelta(hours=3, minutes=30) - timedelta(days=back)).strftime("%Y-%m-%d")


NOTES, LOGS, DBSETS, EXEC = [], [], [], []


class FakeDB:
    class userbots:
        @staticmethod
        def update_one(q, u, **k):
            DBSETS.append(u)

        @staticmethod
        def find_one(q):
            return None


async def _ub_db(fn, *a):
    return fn(*a)


def ub_notify(owner, ubid, key, text):
    NOTES.append((key, text))


def ub_log(ubid, kind, who="", inc="n_out"):
    LOGS.append((kind, who))


def ub_pause_chat(ubid, st, cid, reason):
    for h in st["cfg"]["chats"]:
        if h["id"] == cid:
            h["err"] = reason


class Loop:
    def run_in_executor(self, ex, fn, *a):
        EXEC.append((fn.__name__, a))


class FakeAsyncio:
    sleep = staticmethod(fake_sleep)
    TimeoutError = real_asyncio.TimeoutError

    @staticmethod
    def get_running_loop():
        return Loop()

    wait_for = staticmethod(lambda c, t: c)


NS = dict(time=FakeTime, asyncio=FakeAsyncio, random=random, timedelta=timedelta, now=now, tehran_day=tehran_day, deque=deque, io=io, re=re, _html=_html,
          UB_LIB=True, tl_err=tl_err, db=FakeDB, ObjectId=lambda x: x, log=logging.getLogger("t"), _ub_db=_ub_db, ub_notify=ub_notify, ub_log=ub_log,
          ub_pause_chat=ub_pause_chat, ub_fill=lambda text, name="", chat="": text, MOTHER_TOKEN="x", tg=lambda *a, **k: None, ub_stop=lambda d: None,
          _ub_live={}, _ub_media=None)
NS["__builtins__"] = __builtins__
for node in TREE.body:
    nm = None
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in FUNCS:
        nm = node.name
    elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ASSIGNS for t in node.targets):
        nm = "assign"
    if nm:
        exec(compile(ast.get_source_segment(SRC, node), "mother_extract", "exec"), NS)
missing = [f for f in FUNCS if f not in NS]
assert not missing, missing
for k in list(NS):
    globals().setdefault(k, NS[k])


# ── کلاینت جعلی ──
class FakeClient:
    def __init__(self):
        self.script = []       # هر عنصر: None=موفق | Exception=پرتاب
        self.sent = []         # (chat, text, زمان)

    async def get_input_entity(self, cid):
        return cid

    def action(self, ent, kind):
        class _A:
            async def __aenter__(s): return s
            async def __aexit__(s, *a): return False
        return _A()

    async def send_message(self, ent, body, **kw):
        r = self.script.pop(0) if self.script else None
        if isinstance(r, BaseException):
            raise r
        self.sent.append((ent, body, clk.t))
        return types.SimpleNamespace(id=len(self.sent))


def mkpost(pid="aaaa1111", chats=(-1001, -1002, -1003), texts=("A", "B", "C"), **kw):
    p = {"id": pid, "name": "بنر", "chats": list(chats), "texts": list(texts), "mode": "seq", "every_min": 60, "media": "", "fmt": "html", "from_h": 0, "to_h": 24,
         "daily": 10, "on": True, "rp": False, "rwin": 30, "rnone": "plain", "mg": False, "lg": False, "lgs": "both", "fb": "text", "fwd": "", "nl": False}
    p.update(kw)
    return p


def mkst(safe="safe", posts=None, nchats=3, **kw):
    posts = posts if posts is not None else [mkpost(chats=[-1001 - i for i in range(nchats)])]
    chats = [{"id": -1001 - i, "title": f"گروه{i + 1}", "kind": "group", "on": True, "reply": "off", "ai": False, "err": "", "guard": "auto"} for i in range(nchats)]
    cfg = {"safe": safe, "chats": chats, "posts": posts}
    c = FakeClient()
    st = {"c": c, "owner": 1, "cfg": cfg, "ps": {}, "psent": deque(), "hold": 0, "clast": {}, "cblock": {}, "fails": {}, "lastout": {}, "mc": {}, "me": None, "dlg_ok": True}
    st.update(kw)
    return st, c


def run(coro):
    return real_asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def reset():
    NOTES.clear(); LOGS.clear(); DBSETS.clear(); EXEC.clear(); HOOKS.clear()
    clk.t = 1_800_000_000.0
    # ساعت را روی ۱۲:۰۰ تهران می‌گذاریم تا ساعت سکوت دخالت نکند
    loc = now() + timedelta(hours=3, minutes=30)
    clk.t += ((12 - (loc.hour + loc.minute / 60 + loc.second / 3600)) % 24) * 3600
    NS["UB_PROF"].update({"safe": dict(post_h=12, post_d=120, gap=3600, dmin=30, dmax=90, g_h=10, g_cd=60, u_cd=180)})


ok_n = 0


def check(cond, msg):
    global ok_n
    if not cond:
        print("FAIL:", msg)
        sys.exit(1)
    ok_n += 1


def stt(st, i=0):
    p = st["cfg"]["posts"][i]
    eff = NS["_ub_eff"](st, st["cfg"])[0]
    return NS["_ub_post_state"](st, st["cfg"], p, st["ps"].get(p["id"], {}), eff, clk.t)


# ───────────────────────── T1: دور عادی، متن متفاوت برای هر مقصد، مکث‌ها ─────────────────────────
reset()
st, c = mkst()
run(NS["_ub_sched_tick"]("u1", st))
check(len(c.sent) == 0, "اولین دور نباید فوری بفرستد (next آینده است)")
clk.t += 3700
run(NS["_ub_sched_tick"]("u1", st))
check(len(c.sent) == 3, f"باید ۳ ارسال شود، شد {len(c.sent)}")
check([x[1] for x in c.sent] == ["A", "B", "C"], f"هر مقصد نسخه‌ی خودش: {[x[1] for x in c.sent]}")
gaps = [c.sent[i + 1][2] - c.sent[i][2] for i in range(2)]
check(all(g >= 30 for g in gaps), f"مکث بین ارسال‌ها ≥ ۳۰ثانیه: {gaps}")
ps = st["ps"]["aaaa1111"]
check(ps["ok"] == 3 and ps["n"] == 1 and not ps.get("pend") and ps["next"] > clk.t, "پایان دوره درست ثبت شود")
check(NS["_ub_day_n"](st)["n"] == 3, "شمارنده‌ی روزانه‌ی اکانت")
check(any(e["k"] == "ok" for e in ps["ev"]) and ps["ev"][-1]["m"].startswith("نوبت تمام شد"), "رویدادها ثبت شوند")
s_ = stt(st)
check(s_["c"] == "ok" and s_["u"] == int(ps["next"]), f"وضعیت: منتظر نوبت بعدی با شمارنده؛ {s_}")
print("T1 ok")

# ───────────────────────── T2: FloodWait وسط دور؛ صبر دقیق، بدون ارسال در حین صبر، ادامه با سرعت کمتر ─────────────────────────
reset()
st, c = mkst()
st["ps"]["aaaa1111"] = {"next": clk.t - 1}
c.script = [None, FloodWaitError(120), None, None]
run(NS["_ub_sched_tick"]("u1", st))
check(len(c.sent) == 1, "بعد از FloodWait ارسال دیگری نباید بشود")
check(abs(st["hold"] - (clk.t - 0 + 0)) > 0 and st["hold"] >= clk.t + 100, "hold ثبت شود")
t_hold = st["hold"]
check("FloodWait" in stt(st)["m"] and stt(st)["c"] == "tok" and stt(st)["u"] == int(t_hold), f"وضعیت کارت در صبر: {stt(st)}")
check(st["pen"] > 1.2, f"ضریب احتیاط بالا رفت: {st['pen']}")
check(st["ps"]["aaaa1111"]["tg"]["-1002"]["s"] == "w" and "FloodWait" in st["ps"]["aaaa1111"]["tg"]["-1002"]["m"], "مقصد در حالت انتظار با دلیل")
check(any("acct" in u["$set"] for u in DBSETS) and DBSETS[-1]["$set"]["acct"]["hold"] > 0, "وضعیت نگهبان ذخیره شود (برای ری‌استارت)")
n_before = len(c.sent)
for _ in range(3):                      # در حین صبر تیک‌ها هیچ کاری نکنند
    clk.t += 30
    run(NS["_ub_sched_tick"]("u1", st))
check(len(c.sent) == n_before, "در حین صبر هیچ ارسالی نباید انجام شود")
clk.t = t_hold + 1
pen_after = NS["_ub_pen"](st)
run(NS["_ub_sched_tick"]("u1", st))
check(any(e["k"] == "info" and "تمام شد" in e["m"] for e in st["aev"]), "رویداد پایان محدودیت ثبت شود")
check(len(c.sent) >= 2, "بعد از صبر ادامه می‌دهد")
last_gap = c.sent[-1][2] - c.sent[-2][2] if len(c.sent) >= 3 else None
check(NOTES == [] or NOTES[0][0] == "flood", "اعلان فقط برای محدودیت‌های طولانی/تکراری")
print("T2 ok  pen=%.2f" % pen_after)

# ───────────────────────── T3: تکرار فلود → استراحت طولانی‌تر ─────────────────────────
reset()
st, _ = mkst()
for i in range(3):
    run(NS["_ub_flood"]("u1", st, 10, "FloodWait"))
    clk.t += 20
check(st["hold"] - clk.t > 1500, f"سومین فلود در ۶ ساعت باید ≥۳۰ دقیقه استراحت بدهد: {st['hold'] - clk.t}")
check(any(k == "flood2" for k, _ in NOTES), "اعلان تشدید")
print("T3 ok")

# ───────────────────────── T4: PeerFlood ─────────────────────────
reset()
st, c = mkst()
st["ps"]["aaaa1111"] = {"next": clk.t - 1}
c.script = [NS["tl_err"].PeerFloodError()]
run(NS["_ub_sched_tick"]("u1", st))
check(st["hold"] - clk.t >= 86000, "۲۴ ساعت توقف")
check(st["pen"] >= 3.9 or NS["_ub_pen"](st) > 3.0, f"ضریب احتیاط بالا: {st['pen']}")
check(any(k == "peerflood" for k, _ in NOTES), "اعلان PeerFlood")
a = NS["_ub_acct_view"](st, st["cfg"])
check(a["c"] == "tok" and "PeerFlood" in a["m"], f"وضعیت اکانت: {a}")
print("T4 ok")

# ───────────────────────── T5: SlowMode روی یک گروه؛ بقیه ادامه ─────────────────────────
reset()
st, c = mkst()
st["ps"]["aaaa1111"] = {"next": clk.t - 1}
c.script = [SlowModeWaitError(600), None, None]
run(NS["_ub_sched_tick"]("u1", st))
check([x[0] for x in c.sent] == [-1002, -1003], f"گروه اسلو‌مود رد می‌شود و بقیه می‌روند: {[x[0] for x in c.sent]}")
check(st["cblock"][-1001] > clk.t, "اسلو‌مود ثبت شود")
check(st["ps"]["aaaa1111"]["pend"] == [-1001], "مقصد اسلو‌مودی در صف می‌ماند")
s_ = stt(st)
check(s_["c"] == "tok" and "اسلو" in s_["t"] and s_["u"] == int(st["cblock"][-1001]), f"وضعیت: {s_}")
clk.t = st["cblock"][-1001] + 1
run(NS["_ub_sched_tick"]("u1", st))
check(-1001 in [x[0] for x in c.sent], "بعد از اسلو‌مود ارسال می‌شود")
print("T5 ok")

# ───────────────────────── T6: اکانت مسدود → خاموش‌شدن کامل ─────────────────────────
reset()
st, c = mkst()
st["ps"]["aaaa1111"] = {"next": clk.t - 1}
c.script = [NS["tl_err"].UserDeactivatedBanError()]
run(NS["_ub_sched_tick"]("u1", st))
check(st.get("dead") and "Ban" in st["dead"], "dead ثبت شود")
check(EXEC and EXEC[0][0] == "_ub_fatal", "خاموش‌سازی در ترد جدا درخواست شود")
n = len(c.sent)
run(NS["_ub_sched_tick"]("u1", st))
check(len(c.sent) == n, "بعد از مرگ اکانت هیچ تلاشی نشود")
check(stt(st)["c"] == "bad", "کارت قرمز")
print("T6 ok")

# ───────────────────────── T7: خطای اتصال مقصد را متوقف نمی‌کند ─────────────────────────
reset()
st, c = mkst()
st["ps"]["aaaa1111"] = {"next": clk.t - 1}
c.script = [real_asyncio.TimeoutError()]
run(NS["_ub_sched_tick"]("u1", st))
check(not any(h["err"] for h in st["cfg"]["chats"]), "مقصد نباید به‌خاطر خطای شبکه متوقف شود")
check(st["hold"] > clk.t and "اتصال" in st["hold_why"], "مکث اتصال")
h1 = st["hold"] - clk.t
clk.t = st["hold"] + 1
c.script = [real_asyncio.TimeoutError()]
run(NS["_ub_sched_tick"]("u1", st))
check(st["hold"] - clk.t > h1, "مکث فزاینده")
print("T7 ok")

# ───────────────────────── T8: بسته‌شدن دسترسی ارسال در یک گروه ─────────────────────────
reset()
st, c = mkst()
st["ps"]["aaaa1111"] = {"next": clk.t - 1}
c.script = [NS["tl_err"].ChatWriteForbiddenError(), None, None]
run(NS["_ub_sched_tick"]("u1", st))
ps = st["ps"]["aaaa1111"]
check(st["cfg"]["chats"][0]["err"] and ps["tg"]["-1001"]["s"] == "x" and "اجازه" in ps["tg"]["-1001"]["m"], "دلیل مقصد ناموفق ثبت شود")
check(ps["ok"] == 2 and ps["bad"] == 1, f"آمار: {ps['ok']}/{ps['bad']}")
print("T8 ok")

# ───────────────────────── T9: سقف روزانه‌ی اکانت ─────────────────────────
reset()
NS["UB_PROF"]["safe"]["post_d"] = 3          # کف مؤثر ۳ است
st, c = mkst(nchats=5)
st["ps"]["aaaa1111"] = {"next": clk.t - 1}
run(NS["_ub_sched_tick"]("u1", st))
check(len(c.sent) == 3, f"سقف روزانه ۳: ارسال شد {len(c.sent)}")
s_ = stt(st)
check(s_["c"] == "tok" and "روزانه" in s_["t"] and s_["u"] > clk.t, f"وضعیت سقف روزانه: {s_}")
check(any(e["k"] == "cap" for e in st["aev"]), "رویداد سقف")
clk.t += 26 * 3600                            # نوبت نیمه‌کاره‌ی بیش از ۶ ساعت بسته می‌شود
run(NS["_ub_sched_tick"]("u1", st))
check(not st["ps"]["aaaa1111"].get("pend") and any("رها شد" in e["m"] for e in st["ps"]["aaaa1111"]["ev"]), "نوبت قدیمی رها شود")
clk.t += 4000
run(NS["_ub_sched_tick"]("u1", st))
check(len(c.sent) > 3, f"روز بعد (شمارنده ریست) دوباره ارسال می‌کند: {len(c.sent)}")
print("T9 ok")

# ───────────────────────── T10: سقف ساعتی ─────────────────────────
reset()
NS["UB_PROF"]["safe"]["post_h"] = 2
st, c = mkst()
st["ps"]["aaaa1111"] = {"next": clk.t - 1}
run(NS["_ub_sched_tick"]("u1", st))
check(len(c.sent) == 2, "سقف ساعتی ۲")
s_ = stt(st)
check("ساعتی" in s_["t"] and s_["u"] > clk.t, f"{s_}")
print("T10 ok")

# ───────────────────────── T11: ساعت سکوت و یوزربات خاموش ─────────────────────────
reset()
st, c = mkst(posts=[mkpost(from_h=1, to_h=2)])
st["ps"]["aaaa1111"] = {"next": clk.t - 1}
run(NS["_ub_sched_tick"]("u1", st))
check(len(c.sent) == 0, "خارج از بازه ارسال نمی‌شود")
s_ = stt(st)
check(s_["c"] == "vio" and "سکوت" in s_["t"] and 0 < s_["u"] - clk.t <= 24 * 3600, f"{s_}")
off = NS["_ub_post_state"](None, st["cfg"], st["cfg"]["posts"][0], {}, NS["UB_PROF"]["safe"], clk.t)
check(off["c"] == "off" and "خاموش" in off["m"], "یوزربات خاموش شفاف نمایش داده شود")
print("T11 ok")

# ───────────────────────── T12: غیرفعال‌کردن زمان‌بندی وسط نوبت ─────────────────────────
reset()
st, c = mkst()
st["ps"]["aaaa1111"] = {"next": clk.t - 1}
HOOKS["sleep"] = lambda s: st["cfg"]["posts"][0].__setitem__("on", False)
run(NS["_ub_sched_tick"]("u1", st))
check(len(c.sent) == 1, f"بعد از غیرفعال‌شدن ادامه ندهد: {len(c.sent)}")
ps = st["ps"]["aaaa1111"]
check(not ps.get("pend") and ps.get("n", 0) == 0 and any("غیرفعال" in e["m"] for e in ps["ev"]), "نوبت بسته شود و شمرده نشود")
print("T12 ok")

# ───────────────────────── T13: تغییر تنظیمات وسط دور اعمال شود ─────────────────────────
reset()
st, c = mkst()
st["ps"]["aaaa1111"] = {"next": clk.t - 1}
HOOKS["sleep"] = lambda s: st["cfg"]["chats"][1].__setitem__("on", False)
run(NS["_ub_sched_tick"]("u1", st))
check([x[0] for x in c.sent] == [-1001, -1003], f"گروه غیرفعال‌شده وسط دور نباید پیام بگیرد: {[x[0] for x in c.sent]}")
print("T13 ok")

# ───────────────────────── T14: گرم‌کردن اکانت تازه + زوال ضریب احتیاط ─────────────────────────
reset()
st, _ = mkst()
st["born"] = clk.t - 3600
eff, pen, ramp = NS["_ub_eff"](st, st["cfg"])
check(ramp == 0.4 and eff["post_h"] == 4 and eff["post_d"] == 48, f"گرم‌کردن روز اول: {eff['post_h']}/{eff['post_d']}")
st["born"] = clk.t - 10 * 86400
check(NS["_ub_ramp"](st, st["cfg"]) == 1.0, "بعد از یک هفته کامل")
run(NS["_ub_flood"]("u1", st, 700, "FloodWait"))
p0 = st["pen"]
clk.t = st["hold"] + 2 * 3600
check(abs(NS["_ub_pen"](st) - (p0 - 0.5)) < 0.01, f"زوال ۰٫۲۵ در ساعت بعد از پایان محدودیت: {p0} → {NS['_ub_pen'](st)}")
clk.t = st["hold"] + 30 * 3600
check(NS["_ub_pen"](st) == 1.0, "کاملاً برمی‌گردد")
eff2 = NS["_ub_eff"](st, st["cfg"])[0]
check(eff2["gap"] == 3600 and eff2["post_h"] == 12, "پروفایل عادی بعد از زوال")
a = NS["_ub_acct_view"](st, st["cfg"])
check(a["c"] == "ok" and a["fw"] == 0, f"{a}")   # بیش از ۲۴ ساعت گذشته
print("T14 ok")

# ───────────────────────── T15: ps_view و فیلدهای خروجی پنل ─────────────────────────
reset()
st, c = mkst()
NS["_ub_live"]["u9"] = st
st["ps"]["aaaa1111"] = {"next": clk.t - 1}
c.script = [None, FloodWaitError(30), None]
run(NS["_ub_sched_tick"]("u9", st))
v = NS["_ub_ps_view"]("u9", {}, st["cfg"])["aaaa1111"]
check(v["stt"]["c"] == "tok" and v["tg"]["-1001"]["s"] == "ok" and v["tg"]["-1002"]["s"] == "w" and v["ev"] and v["pend"] == 2, f"{v}")
import json
json.dumps(v)  # باید قابل سریال‌سازی باشد
json.dumps(NS["_ub_acct_view"](st, st["cfg"]))
print("T15 ok")

print(f"\nALL PASSED ({ok_n} checks)")
