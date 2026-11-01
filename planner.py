# -*- coding: utf-8 -*-
"""
planner.py — روتر قطعی + کامپایلر طرح

plan_request(prompt)  → PlanResult (ماژول‌ها + پارامترها + اطمینان)   [بدون هوش مصنوعی، چند میلی‌ثانیه]
compile_plan(plan)    → (thinking, cfg, ideas)                           [کانفیگ آمادهٔ sanitize]
هوش مصنوعی فقط وقتی لازم است که روتر هیچ ماژولی پیدا نکند (آن‌وقت ai.py مسیر قدیمی را اجرا می‌کند).
"""
import re
from modules import (MODULES, Builder, BuildError, normalize_text, clean_params, _num, fmt, _clean_text, catalog)
import modlib  # noqa: F401  (ثبت ماژول‌ها)

COIN_WORDS = ["سکه", "الماس", "کوین", "امتیاز", "جم", "اعتبار"]
HANDLE = re.compile(r"@([A-Za-z][A-Za-z0-9_]{4,31})")


class PlanResult:
    def __init__(self):
        self.items = []          # [(module_id, params)]
        self.name = ""
        self.emoji = False
        self.payments = False
        self.scores = {}
        self.confidence = 0.0

    @property
    def ids(self):
        return [i for i, _ in self.items]


def _near(text, kw, pat=r"(\d+(?:[.,]\d+)?)", after=40, before=25):
    """اولین عدد نزدیک کلیدواژه؛ اول بعد از آن، بعد قبل از آن"""
    m = re.search(kw, text)
    if not m:
        return None
    seg = text[m.end():m.end() + after]
    n = re.search(pat, seg)
    if n:
        return n.group(1).replace(",", ".")
    seg = text[max(0, m.start() - before):m.start()]
    ns = re.findall(pat, seg)
    return ns[-1].replace(",", ".") if ns else None


def _window(text, kw, size=700):
    m = re.search(kw, text)
    return text[m.start():m.start() + size] if m else ""


def _extract(text, ids):
    P = {i: {} for i in ids}
    t = text
    coin = None
    best = 0
    for w in COIN_WORDS:
        c = len(re.findall(w, t))
        if c > best:
            best, coin = c, w
    if "wallet" in P:
        if coin:
            P["wallet"]["coin"] = coin
        if coin in ("الماس", "جم"):
            P["wallet"]["emoji"] = "💎"
        v = _near(t, r"(هدیه|جایزه|پاداش|بونوس)\s*(ی\s*)?(ورود|شروع|استارت|اولین ورود|ثبت ?نام)", after=30, before=25)
        if v:
            P["wallet"]["start_bonus"] = v
    if "daily" in P:
        v = _near(t, r"(هدیه|جایزه|پاداش) روزانه", after=30, before=20)
        if v:
            P["daily"]["amount"] = v
    if "referral" in P:
        v = _near(t, r"(هر|به ازای) (دعوت|رفرال|نفر)", after=40, before=0) or _near(t, r"پاداش (دعوت|رفرال)", after=30, before=0)
        if v:
            P["referral"]["reward"] = v
    if "miner" in P:
        w = _window(t, r"ماینر", 260)
        m = re.search(r"(\d+)\s*(?:نفر|دعوت)", w)
        if m:
            P["miner"]["need_refs"] = m.group(1)
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:" + "|".join(COIN_WORDS) + r")\S*\s*(?:روزانه|هر روز|در روز)", w) \
            or re.search(r"(?:روزانه|هر روز)\D{0,15}(\d+(?:\.\d+)?)", w)
        if m:
            P["miner"]["daily"] = m.group(1)
    if "sponsor" in P:
        v = _near(t, r"(جوین|عضو) (شد|شو|بشه|بشی|شدن|شود)", after=60, before=40) or _near(t, r"(جوین|عضو)", after=60, before=0)
        if v and 0 < float(v) < 1000:
            P["sponsor"]["reward"] = v
        hs = list(dict.fromkeys(HANDLE.findall(t)))
        if hs:
            P["sponsor"]["channels"] = hs
    if "forced_join" in P:
        w = _window(t, r"اجباری", 200)
        hs = list(dict.fromkeys(HANDLE.findall(w))) or list(dict.fromkeys(HANDLE.findall(t)))
        if hs:
            P["forced_join"]["channels"] = hs
    if "wheel" in P:
        w = _window(t, r"گردونه|چرخ شانس", 900)
        segs = [re.sub(r"^\s*\d+\s*[:：\-]\s*", "", re.split(r"[\n،.؛;]", x)[0]) for x in re.split(r"حالت", w)[1:]]
        prizes = []
        for s in segs:
            if "پازل" in s:
                prizes.append("puzzle")
            else:
                m = re.search(r"(\d+(?:\.\d+)?)", s)
                if m:
                    prizes.append(m.group(1))
        if len(prizes) >= 2:
            P["wheel"]["prizes"] = prizes[:12]
        m = re.search(r"هر\s*(\d+)\s*(?:کانال|جوین|عضو)", w)
        if m:
            P["wheel"]["per_joins"] = m.group(1)
        m = re.search(r"هر\s*(\d+)\s*(?:دعوت|نفر)", w)
        if m:
            P["wheel"]["per_refs"] = m.group(1)
        if "sponsor" not in P and "referral" not in P and "daily" not in P:
            P["wheel"]["daily_ticket"] = True
        elif "daily" in P and not (m or P["wheel"].get("per_joins")):
            P["wheel"]["daily_ticket"] = True
    if "puzzle" in P:
        w = _window(t, r"پازل", 250)
        m = re.search(r"(\d+)\s*(?:قطعه|تکه|پازل)", w)
        if m:
            P["puzzle"]["need"] = m.group(1)
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:" + "|".join(COIN_WORDS) + ")", w)
        if m:
            P["puzzle"]["reward"] = m.group(1)
    if "coin_shop" in P:
        m = re.search(r"(\d+)\s*(?:" + "|".join(COIN_WORDS) + r")\S*[^\d\n]{0,25}?(\d[\d.,]*)\s*(هزار)?\s*(?:تومان|تومن)", t)
        if m:
            P["coin_shop"]["pack"] = m.group(1)
            pr = _num(m.group(2), 0) * (1000 if m.group(3) else 1)
            if pr:
                P["coin_shop"]["price_toman"] = pr
    return P


def _bot_name(t, ids):
    for pat in (r"(?:اسم|نام) ربات\s*[:：]?\s*[«\"']?([^\n«»\"'،.]{2,25})", r"ربات\s+([^\n،.:]{2,22}?)\s+(?:بساز|درست کن|می ?خوام|میخوام)"):
        m = re.search(pat, t)
        if m:
            n = _clean_text(m.group(1), 25).strip()
            if n and len(n.split()) <= 4:
                return n
    if "member_orders" in ids:
        return "ممبرگیر"
    if "ads" in ids:
        return "نیازمندی‌ها"
    if "shop" in ids:
        return "فروشگاه من"
    if "group_manager" in ids:
        return "مدیر گروه"
    return "ربات من"


def plan_request(prompt, name=None, emoji=None, payments=False):
    t = normalize_text(prompt)
    pr = PlanResult()
    scores = {}
    for mid, m in MODULES.items():
        s = 0.0
        for rx, w in m.triggers:
            n = len(re.findall(rx, t, flags=re.I))
            if n:
                s += w * min(n, 3) / (1 if n == 1 else 1.6)
        if s:
            scores[mid] = s
    chosen = {i for i, s in scores.items() if s >= 1.0}
    # وابستگی‌ها
    changed = True
    while changed:
        changed = False
        for i in list(chosen):
            for r in MODULES[i].requires:
                if r not in chosen and (r in ("wallet", "referral") or scores.get(r, 0) >= 0.5):
                    chosen.add(r)
                    changed = True
    # کیف تنها بدون قابلیتی که از آن استفاده کند بی‌معنی است
    if chosen == {"wallet"}:
        chosen = set()
    pr.scores = scores
    ordered = sorted(chosen, key=lambda i: MODULES[i].prio)
    ex = _extract(t, set(ordered))
    for i in ordered:
        pr.items.append((i, clean_params(MODULES[i], ex.get(i))))
    plans = {i: p for i, p in pr.items}
    # پلن‌ها به هم وصل می‌شوند (مثلاً گردونه می‌داند بلیت از کجا می‌آید)
    if "wheel" in plans and "daily" in plans and plans["wheel"].get("per_joins", 0) == 0 and plans["wheel"].get("per_refs", 0) == 0:
        plans["wheel"]["daily_ticket"] = True
    if "wheel" in plans and "sponsor" in plans and plans["wheel"]["per_joins"] == 0:
        plans["wheel"]["per_joins"] = 40 if re.search(r"هر\s*40\s*(کانال|جوین)", t) else 10
    pr.name = _clean_text(name, 30) if name else _bot_name(t, ordered)
    pr.emoji = bool(emoji) if emoji is not None else (bool(re.search(r"ایموجی", t)) and not re.search(r"بدون ایموجی|ایموجی نذار|ایموجی نداشته", t))
    pr.payments = bool(payments or re.search(r"ستاره|stars|پرداخت (آنی|درون)", t))
    pr.confidence = min(1.0, sum(min(scores.get(i, 0.6), 2.0) for i in ordered if i != "wallet") / 2.0) if ordered else 0.0
    return pr


def compile_plan(pr):
    """PlanResult → (thinking, cfg, ideas). خطا: BuildError"""
    if not pr.items:
        raise BuildError("هیچ ماژولی انتخاب نشده")
    b = Builder(pr.name, pr.emoji, pr.payments)
    plans = {i: p for i, p in pr.items}
    b.shared["plans"] = plans
    b.shared["daily_ticket"] = bool("daily" in plans and plans.get("wheel", {}).get("daily_ticket"))
    for mid, p in pr.items:                       # ترتیب: کیف اول چون نام واحد پول را می‌گذارد
        m = MODULES[mid]
        b.have.add(mid)
        m.compile(b, p)
        b.titles.append(m.fa)
    cfg = b.finish()
    names = "، ".join(MODULES[i].fa for i in pr.ids)
    thinking = f"ربات «{pr.name}» با ماژول‌های آماده و تست‌شده ساخته شد: {names}. ساخت قطعی است و ساختار همیشه معتبر خروجی می‌شود."
    if b.notes:
        thinking += "\n" + "\n".join("• " + n for n in b.notes[:6])
    ideas = []
    if "sponsor" in plans and plans["sponsor"]["channels"] == ["your_channel"]:
        ideas.append("آیدی واقعی کانال‌های پاداش را در بخش «کسب سکه» ویرایش کن")
    if "forced_join" in plans and plans["forced_join"]["channels"] == ["your_channel"]:
        ideas.append("آیدی کانال جوین اجباری را در تنظیمات ربات عوض کن")
    if "coin_shop" in plans:
        ideas.append("شماره کارت را در بخش «خرید سکه» بگذار")
    if "wheel" in plans:
        ideas.append("جایزه‌های گردونه را با ویرایش بخش‌های «جایزه» عوض کن")
    ideas += ["یک بنر یا عکس برای منوی اصلی بگذار", "برای هر بخش دکمهٔ لینک کانال خودت را اضافه کن"]
    return thinking, cfg, ideas[:4]
