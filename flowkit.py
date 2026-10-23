# -*- coding: utf-8 -*-
"""
flowkit.py — جریان‌های پیشرفته: صف کار با دوام و زیرساخت شبیه‌سازی (وابسته به core؛ بالاتر از ai)

بخش‌ها:
  • صف کار با دوام (db.queue): enqueue/lease/complete/fail/reclaim با lease و backoff نمایی و dead-letter؛
    بعد از ری‌استارت سرویس ادامه پیدا می‌کند (پایه‌ی wait، کمپین، drip و ارسال همگانی در مراحل بعد).
  • رجیستری شبیه‌سازی: simulate(cfg, events, state) بدون تماس با تلگرام؛ موتور (engine) اجراکننده‌ی واقعی را
    با register_runner ثبت می‌کند (تزریق وابستگی به‌جای import برعکس — flowkit قبل از engine است).

قرارداد صف: هر کار {"kind"، "payload"، "run_at"، "attempts"، "max_attempts"، "status": wait|run|dead}.
هندلر هر kind با register_handler ثبت می‌شود؛ worker فقط kindهای دارای هندلر را برمی‌دارد.
"""

import re, time, threading
from datetime import timedelta

from core import db, naive, now, _int, log

QUEUE_MAX_ATTEMPTS = _int("QUEUE_MAX_ATTEMPTS", 4)
QUEUE_LEASE_TTL = _int("QUEUE_LEASE_TTL", 120)          # ثانیه؛ بعدش کار دوباره اجاره می‌شود (سرویس ری‌استارت شده)
QUEUE_BACKOFF = _int("QUEUE_BACKOFF", 60)               # پایه‌ی backoff نمایی (ثانیه)
QUEUE_BATCH = _int("QUEUE_BATCH", 5)                    # حداکثر کار همزمان هر دور
QUEUE_CONCURRENCY = _int("QUEUE_CONCURRENCY", 2)        # سقف همزمانی برای Render رایگان

_indexed = [False]


def _ensure_index():
    if _indexed[0]:
        return
    from core import _index
    _index(db.queue, [("status", 1), ("run_at", 1)])
    _index(db.queue, [("status", 1), ("kind", 1), ("run_at", 1)])
    _index(db.queue, "dead_at", expireAfterSeconds=7 * 86400)      # dead-letter هفت‌روزه
    _indexed[0] = True


# ───────────────────────── صف کار با دوام ─────────────────────────
def enqueue(kind, payload=None, delay=0, key=None, max_attempts=0):
    """کار تازه؛ با key تکراری ثبت نمی‌شود (idempotency). خروجی: شناسه‌ی کار یا None"""
    _ensure_index()
    doc = {"kind": str(kind)[:40], "payload": payload or {}, "status": "wait",
           "run_at": naive(now() + timedelta(seconds=max(0, int(delay)))),
           "attempts": 0, "max_attempts": int(max_attempts) or QUEUE_MAX_ATTEMPTS, "t": now()}
    if key:
        doc["_id"] = f"{kind}:{str(key)[:80]}"
    try:
        r = db.queue.insert_one(doc)
        return str(r.inserted_id)
    except Exception as e:
        if "DuplicateKeyError" in type(e).__name__ or "duplicate" in str(e).lower():
            return None                      # همین کار از قبل در صف است
        log.exception("queue enqueue failed")
        return None


def lease(kinds, worker, ttl=0):
    """بر داشتن یک کار آماده (اتمیک) برای kindهای دارای هندلر؛ None یعنی کاری نبود"""
    _ensure_index()
    ttl = int(ttl) or QUEUE_LEASE_TTL
    d = db.queue.find_one_and_update(
        {"status": "wait", "run_at": {"$lte": naive()}, "kind": {"$in": list(kinds)[:50]}},
        {"$set": {"status": "run", "lease_until": naive(now() + timedelta(seconds=ttl)),
                  "worker": str(worker)[:40], "leased": now()}, "$inc": {"attempts": 1}},
        sort=[("run_at", 1)], return_document=True)
    return d


def complete(jid):
    db.queue.delete_one({"_id": jid})


def fail(job, err="", handler_retry=None):
    """شکست کار: تا سقف تلاش، با backoff نمایی برمی‌گردد؛ بعدش dead-letter (۷ روز نگه داشته می‌شود)"""
    attempts = int(job.get("attempts", 1))
    mx = int(job.get("max_attempts") or QUEUE_MAX_ATTEMPTS)
    delay = handler_retry if handler_retry is not None else min(QUEUE_BACKOFF * (2 ** max(0, attempts - 1)), 6 * 3600)
    if attempts < mx:
        db.queue.update_one({"_id": job["_id"], "status": "run"},
                            {"$set": {"status": "wait", "run_at": naive(now() + timedelta(seconds=delay)),
                                      "last_err": str(err)[:300]}})
    else:
        db.queue.update_one({"_id": job["_id"], "status": "run"},
                            {"$set": {"status": "dead", "dead_at": now(), "last_err": str(err)[:300]}})


def reclaim():
    """کارهایی که lease‌شان تمام شده (سرویس ری‌استارت شده) به صف برمی‌گردند"""
    _ensure_index()
    try:
        db.queue.update_many({"status": "run", "lease_until": {"$lt": naive()}}, {"$set": {"status": "wait"}})
    except Exception:
        log.exception("queue reclaim failed")


def queue_stats():
    _ensure_index()
    agg = {}
    for d in db.queue.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
        agg[d["_id"]] = int(d.get("n", 0))
    return {"wait": agg.get("wait", 0), "run": agg.get("run", 0), "dead": agg.get("dead", 0)}


# ── هندلرها و worker ──
HANDLERS = {}


def register_handler(kind, fn):
    """fn(job_payload, job) کار می‌کند؛ خطای آن یعنی retry"""
    HANDLERS[str(kind)[:40]] = fn


def _run_job(job):
    fn = HANDLERS.get(job.get("kind"))
    try:
        if fn:
            fn(job.get("payload") or {}, job)
        complete(job["_id"])
    except Exception as e:
        log.warning("queue job %s failed: %s", job.get("kind"), e)
        fail(job, err=e)


def queue_loop():
    """حلقه‌ی پس‌زمینه‌ی صف: reclaim، اجاره، اجرا با سقف همزمانی؛ فقط وقتی فلگ queue روشن است بالا می‌آید"""
    _ensure_index()
    log.info("durable queue worker started (%d handlers)", len(HANDLERS))
    sem = threading.Semaphore(QUEUE_CONCURRENCY)
    while True:
        try:
            time.sleep(3)
            reclaim()
            if not HANDLERS:
                continue
            for _ in range(QUEUE_BATCH):
                if not sem.acquire(blocking=False):
                    break
                job = lease(list(HANDLERS), worker="q1")
                if not job:
                    sem.release()
                    break
                threading.Thread(target=_worker, args=(job, sem), daemon=True).start()
        except Exception:
            log.exception("queue loop error")
            time.sleep(5)


def _worker(job, sem):
    try:
        _run_job(job)
    finally:
        sem.release()


# ───────────────────────── تریگرهای جریان (خالص؛ engine مصرف می‌کند) ─────────────────────────
TRIGGER_TYPES = ("join", "text", "media", "location", "contact", "callback", "webhook")
MAX_TRIGGERS = 20


def trigger_match(triggers, kind, value):
    """اولین تریگرِ مطابق رویداد؛ خروجی خود تریگر یا None. text = کلمه‌کلیدی با «,» یا re:الگو؛
    webhook = رشته‌ی match اگر داخل بدنه باشد (شامل)"""
    for t in (triggers if isinstance(triggers, list) else [])[:MAX_TRIGGERS]:
        w = t.get("when") or {}
        if w.get("type") != kind:
            continue
        m = str(w.get("match") or "")
        v = str(value or "")
        if kind == "text":
            if m.startswith("re:"):
                try:
                    if re.search(m[3:], v, re.I):
                        return t
                except re.error:
                    continue
            elif m:
                if any(kw.strip().casefold() and kw.strip().casefold() in v.casefold() for kw in m.split(",")):
                    return t
            else:
                return t
        elif kind == "webhook":
            if not m or m.strip().casefold() in v.casefold():
                return t
        elif not m or m.strip().casefold() == v.strip().casefold():
            return t
    return None


# ───────────────────────── شبیه‌سازی (dry-run) ─────────────────────────
_RUNNERS = {}


def register_runner(name, fn):
    """موتور اجراکننده‌ی واقعی شبیه‌سازی را ثبت می‌کند (engine هنگام import این کار را می‌کند)"""
    _RUNNERS[str(name)[:30]] = fn


class SimTrace:
    """ردپای اجرای شبیه‌سازی: نودها، پیام‌های خروجی، تغییر متغیرها و خطاها"""
    def __init__(self):
        self.nodes = []          # [("نود", یادداشت)]
        self.msgs = []           # [("text"/"media"/..., متن، دکمه‌ها)]
        self.var_changes = []    # [(کلید، قبلی، تازه)]
        self.errors = []

    def node(self, nid, note=""):
        self.nodes.append((str(nid)[:40], str(note)[:120]))

    def msg(self, kind, text, buttons=None):
        self.msgs.append((str(kind)[:12], str(text)[:2000], buttons or []))

    def var(self, key, old, new):
        self.var_changes.append((str(key)[:40], str(old)[:80], str(new)[:80]))

    def error(self, where, err):
        self.errors.append(f"{where}: {str(err)[:200]}")

    def out(self):
        return {"msgs": self.msgs, "trace": self.nodes, "vars": self.var_changes, "errors": self.errors}


def simulate(cfg, events, state=None):
    """اجرای خشک جریان: خروجی فهرست پیام‌ها، trace نودها، تغییر متغیرها و خطاها.
    بدون runner ثبت‌شده (مثلاً قبل از import engine) ساختار «در دسترس نیست» برمی‌گردد — نه خطا."""
    fn = _RUNNERS.get("engine")
    if not fn:
        return {"ok": False, "error": "موتور شبیه‌سازی هنوز ثبت نشده", **SimTrace().out()}
    try:
        return fn(cfg, events, state)
    except Exception as e:
        log.exception("simulate failed")
        tr = SimTrace()
        tr.error("simulate", e)
        return {"ok": False, "error": str(e)[:200], **tr.out()}


def selftest():
    """تست صف و رجیستری با mongomock (بدون شبکه)"""
    ok = lambda name: print("ok —", name)
    _ensure_index()
    # idempotency و شمارش
    j1 = enqueue("t1", {"n": 1}, key="k1")
    assert j1 and enqueue("t1", {"n": 1}, key="k1") is None
    st = queue_stats()
    assert st["wait"] == 1 and st["dead"] == 0
    ok("enqueue + idempotency با key")
    # اجاره و اجرای موفق
    ran = []
    register_handler("t1", lambda p, j: ran.append(p["n"]))
    job = lease(["t1"], worker="test")
    assert job and job["attempts"] == 1 and job["status"] == "run"
    _run_job(job)
    assert ran == [1] and not db.queue.find_one({"_id": j1})
    ok("lease → اجرا → complete")
    # شکست و backoff و dead-letter
    enqueue("t2", {}, key="k2", max_attempts=2)
    register_handler("t2", lambda p, j: (_ for _ in ()).throw(RuntimeError("boom")))
    job = lease(["t2"], worker="test")
    _run_job(job)
    d = db.queue.find_one({"_id": "t2:k2"})
    assert d["status"] == "wait" and d["attempts"] == 1 and d["last_err"], d
    db.queue.update_one({"_id": "t2:k2"}, {"$set": {"run_at": naive() - timedelta(seconds=1)}})
    job = lease(["t2"], worker="test")
    assert job["attempts"] == 2
    _run_job(job)                                   # تلاش دوم هم شکست → attempts==2 == max → dead
    d = db.queue.find_one({"_id": "t2:k2"})
    assert d["status"] == "dead" and d.get("dead_at"), d
    ok("fail → backoff → dead-letter")
    # reclaim کارهای lease‌گم‌شده (شبیه‌سازی ری‌استارت سرویس)
    enqueue("t3", {}, key="k3")
    job = lease(["t3"], worker="ghost", ttl=-1)     # lease بلافاصله منقضی
    assert job["status"] == "run"
    reclaim()
    d = db.queue.find_one({"_id": "t3:k3"})
    assert d["status"] == "wait", d
    ok("reclaim بعد از ری‌استارت")
    # simulate: بدون runner و با runner قلابی
    r = simulate({}, [])
    assert r["ok"] is False and "trace" in r
    register_runner("engine", lambda cfg, events, state: {"ok": True, "msgs": [("text", "سلام", [])], "trace": [("home", "")], "vars": [], "errors": []})
    r = simulate({}, ["start"])
    assert r["ok"] is True and r["msgs"][0][1] == "سلام"
    ok("simulate: قرارداد بدون runner + اجرا با runner ثبت‌شده")
    print("flowkit selftest passed")


if __name__ == "__main__":
    selftest()
