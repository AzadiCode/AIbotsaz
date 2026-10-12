# -*- coding: utf-8 -*-
"""
BotMaker Ultimate — ابر رباتساز هوشمند (نسخه‌ی نهایی)
نقطه‌ی ورود: gunicorn app:app   یا   python app.py

ساختار پروژه (۹ فایل)
  app.py            این فایل: مسیرهای HTTP مینی‌اپ و ادمین + راه‌اندازی برنامه
  core.py           هسته: تنظیمات، دیتابیس، ابزارهای پایه، احراز هویت، کیف توکن، اشتراک و ماموریت، ایموجی پرمیوم، رسانه
  ai.py             هوش مصنوعی: دستورالعمل طراحی، اعتبارسنج کانفیگ، ارتباط با مدل، قالب‌های آماده
  engine.py         موتور اجرای ربات‌ها: اکشن‌ها، ارسال بخش، فرم، تیکت، پرداخت، مدیریت گروه، وب‌هوک
  mother.py         ربات مادر، ساخت داخل چت، کار ساخت با AI، اعلان همگانی، عضویت اجباری، کارت‌به‌کارت، یوزربات
  index.html        اسکلت مینی‌اپ (فقط ساختار؛ استایل و کد جدا هستند)
  static/style.css  همه‌ی استایل‌ها
  static/app.js     پوسته‌ی مینی‌اپ: وضعیت، ارتباط با سرور، صفحه‌ها، حساب، ماموریت، مدیریت، یوزربات
  static/studio.js  ویرایشگر ربات: استودیوی گرافیکی و شیت‌های ویرایش

قاعده‌ی وابستگی (بک‌اند):  core ← ai ← engine ← mother ← app
  هر فایل فقط از فایل‌های قبل از خودش import می‌کنه؛ هیچ‌وقت برعکس (تا وابستگی دایره‌ای پیش نیاد).
  در بالای هر فایل، خط‌های import دقیقاً نشون می‌دن از کدوم فایل چی استفاده می‌شه.
قاعده‌ی فرانت: اسکریپت‌ها به ترتیبِ تگ‌های script توی index.html بارگذاری می‌شن (app.js بعد studio.js).

برای ارتقا: فقط فایلِ همون بخش (و اگه لازم بود index.html) رو بفرست؛ بخش‌ها با بنر «─── عنوان ───» جدا شدن.

────────────────────── توضیح کامل قابلیت‌ها (از نسخه‌ی تک‌فایل) ──────────────────────
Stack: Flask + MongoDB(pymongo) + مینی‌اپ (index.html + static/)

ربات مادر
  /start /help /invite /balance /daily /coupon — باز کردن مینی‌اپ، پرداخت با Telegram Stars
  ادمین: /give /stats /announce /setstartphoto (عکس، گیف یا ویدیوی پیام استارت)
مینی‌اپ
  ساخت و ارتقای ربات با هوش مصنوعی (کانفیگ JSON)، قالب‌های آماده، ویرایش دستی کامل، تست زنده،
  بررسی مسیرها، خروجی JSON، کتابخونه‌ی رسانه، پیام همگانی، آمار و نمودار،
  پاسخ فرم‌ها، ماموریت‌ها و اشتراک (Premium و Pro)، کیف توکن (روزانه، دعوت، کوپن، خرید با ستاره)،
  پنل ادمین (کاربران آنلاین، شارژ، کوپن، اعلان همگانی، آمار سیستم)
  یوزربات: اتصال اکانت شخصی تلگرام با شماره (Telethon)، پاسخ خودکار، پیام غیبت، پاسخ هوشمند و دستورهای شخصی
موتور ثابت و امن (send_node / run_actions)
  متغیر، شرط، اکشن، فرم‌های اعتبارسنجی‌شده، گفتگوی هوشمند با حافظه، دعوت و پاداش، عضویت اجباری،
  رسانه‌ی کتابخونه یا لینکی، کیبورد زیر چت، دکمه‌ی کپی و اشتراک — هیچ کد تولیدشده‌ای اجرا نمی‌شه
قابلیت‌های حرفه‌ای موتور (نسخه‌ی ارتقایافته)
  • میزکار پشتیبانی (تیکت): هر پیام/فرم تیکتی شماره می‌گیره و برای صاحب ربات و پشتیبان‌ها (desk.staff) می‌آد؛ زیرش دکمه‌ی
    «پاسخ / سابقه / بستن / مسدود کردن». پاسخ (متن، عکس، فایل، صدا) با دکمه یا reply به کاربر می‌رسه و کاربر دکمه‌ی «پاسخ به
    پشتیبانی» می‌گیره تا گفتگو توی همون تیکت ادامه پیدا کنه. دستورها: /tickets  (+ /payments /refund برای صاحب)  /paysupport (کاربر)
  • متغیر مشترک بین همه‌ی کاربرها (globals): شمارنده، رأی‌گیری، موجودی محدود، هدف جمعیِ جامعه — افزایش اتمیک
  • جدول برترین‌ها (board) بر اساس هر متغیر عددی یا تعداد دعوت‌ها
  • یادآور و پیام زمان‌بندی‌شده (اکشن remind، تا ۳۰ روز) با پردازشگر پس‌زمینه — انقضای اشتراک، پیگیری سفارش، یادآوری نوبت
  • پرداخت با ستاره‌ی تلگرام داخل رباتا (دکمه‌ی pay): فاکتور XTR، اعتبارسنجی pre_checkout، ثبت یک‌باره، اکشن بعد از پرداخت موفق
  • بازی تعاملی: اکشن dice (تاس انیمیشنی تلگرام 🎲🎯🏀⚽🎳🎰 با نتیجه‌ی واقعی توی متغیر) و pick (قرعه‌ی تصادفی از گزینه‌ها)
  • پایگاه داده‌ی دائمی هر ربات (جدول‌های رکوردی): اکشن‌های db_add / db_get / db_set / db_inc / db_del
    (سفارش‌ها، لیگ‌ها، آرشیو، دیوار پیام) + فیلد list برای نمایش رکوردها زیر هر بخش
  • اکشن fetch: وصل شدن رباتا به APIهای عمومی https (سکه، آب‌وهوا، قیمت؛ روزی EXT_API_DAILY بار هر ربات؛ EXT_API=0 خاموش)
  • هوش ساخت: پرامپت چندمرحله‌ای (تحلیل نقش‌ها ← نگاشت به قابلیت‌ها ← بازبینی) + بازخورد خودکار چیزهایی که اعتبارسنج حذف کرده
Environment اختیاری تازه: PAYMENTS (۰ = خاموش کردن دکمه‌ی پرداخت) SCHED (۰ = خاموش کردن یادآورها)

Environment: MOTHER_TOKEN BASE_URL AI_BASE_URL AI_API_KEY AI_MODEL (الزامی) | MONGO_URI SECRET_KEY ADMIN_IDS ADMIN_WEB_KEY
MOTHER_USERNAME AI_CHAT_MODEL BILLING(usage|fixed) START_TOKENS DAILY_BONUS REF_* PACKS MAX_BOTS ... (پایین‌تر)
"""

import os, re, json, time, hmac, secrets, math, threading
from urllib.parse import unquote
from datetime import timedelta

from flask import g, jsonify, request, Response, send_from_directory
from pymongo.errors import DuplicateKeyError
from bson import Binary, ObjectId
from bson.errors import InvalidId

from core import (
    activate_plan, ADMIN_IDS, admin_only, age_sec, AI_MSG_COST, AI_MSGS_PER_TOKEN, ai_per, app, authed, aware,
    balance, BILLING, BROADCAST_MAX, BROADCAST_PER_TOKEN, charge_up_to, CHUNK, claim_daily, credit,
    cut, DAILY_BONUS, db, dec, _DIG, EDIT_COST, ENHANCE_COST, ensure_user, est_tokens,
    emoji_image, emoji_list, emoji_sig, fj_chat, GEN_COST, get_bot, get_media, hold, JOB_TIMEOUT, log, MAX_BOTS,
    max_bots, MAX_MEDIA, MAX_NODES, MAX_PROMPT, MAX_VERSIONS, media_bytes, media_delete, media_kind,
    media_list, MEDIA_MAX_MB, MEDIA_QUOTA_MB, media_sig, MONGO_URI, mother_link, MOTHER_TOKEN, naive,
    now, ONLINE_SECS, PACKS, PLAN_BY_ID, PLAN_DAYS, PLAN_RANK, plan_info, plan_of, plans_public, perks_of, public, public_media, rate_ok, redeem, REF_INVITEE, REF_INVITER,
    REF_MAX_PER_USER, REF_MILESTONES, REF_ON, refund, SAFE_INLINE, SCHED_ON, send_rich, strip_fx_text,
    settle_referral, setup_mother, spend, task_metrics, task_steps, TASKS, tasks_state,
    TEMPLATE_FACTOR, TEMPLATE_MAX_COST, TEMPLATE_MIN_COST, TEMPLATE_UNIT_COST, tg, TOKEN_MIN_COST,
    TOKEN_OUT_RATE, TOKEN_SCALE, touch_user, wallet_info,
)
from ai import enhance_prompt, EXT_API, lint, reserve_cost, sanitize, TEMPLATES, typical_cost
from engine import PROMO_CONF, PROMO_DEF_LOCK, PROMO_DEF_TEXT, sched_loop, sync_commands
from mother import (
    audience_targets, card_public, do_activate, fj_parse, fj_str, gen_job, lint_fa, MAX_USERBOTS,
    new_bot_doc, recover_jobs, run_admin_send, scan_key, scan_state, start_announce, start_block_scan,
    ub_boot, ub_limit, ub_ready,
)



# ───────────────────────── API مینی‌اپ: پایه، حساب و کیف توکن ─────────────────────────
def own_media_ids(uid):
    return {str(m["_id"]) for m in db.media.find({"owner": uid}, {"_id": 1})}


def media_used(uid):
    return sum(int(m.get("size", 0)) for m in db.media.find({"owner": uid}, {"size": 1}))


def template_cost(t, uid=None):
    """هزینه‌ی قالب آماده، هم‌جهت با ساخت و ارتقا: ضریبی از «مقدار کار» و «حجم پرامپت/کانفیگ».
    کار = تعداد بخش‌ها + فرم، تیکت، منطق/شرط و گفتگوی هوشمند؛ حجم = توکنِ خروجیِ همین کانفیگ با نرخ خروجی مدل.
    هزینه همیشه کمی بیشتر از قبل و کمتر از ساخت با هوش مصنوعی می‌مونه."""
    nodes = t["config"]["nodes"]
    work = len(nodes)
    for n in nodes.values():
        if n.get("ai"):
            work += 2
        if n.get("fields"):
            work += 1
        if n.get("ticket"):
            work += 1
        if n.get("do") or n.get("route") or n.get("alt"):
            work += 1
    if TEMPLATE_UNIT_COST <= 0 and TEMPLATE_MIN_COST <= 0:
        return 0
    size = est_tokens(json.dumps(t["config"], ensure_ascii=False)) * TOKEN_OUT_RATE / 1000
    cost = max(TEMPLATE_MIN_COST, math.ceil((work * TEMPLATE_UNIT_COST + size) * TEMPLATE_FACTOR))
    cap = TEMPLATE_MAX_COST or max(TEMPLATE_MIN_COST, math.floor(typical_cost() * 0.8))
    return cut(uid, min(cost, cap))


def client_cfg(uid=None):
    pk = perks_of(uid)
    return {"billing": BILLING, "gen": cut(uid, GEN_COST), "edit": cut(uid, EDIT_COST), "typical": cut(uid, typical_cost()), "min": cut(uid, TOKEN_MIN_COST),
            "ai_per": ai_per(uid) if uid is not None else AI_MSGS_PER_TOKEN, "ai_cost": AI_MSG_COST, "bc_per": BROADCAST_PER_TOKEN, "scale": TOKEN_SCALE,
            "enhance": 0 if pk["free_enhance"] else ENHANCE_COST,
            "max_bots": MAX_BOTS + pk["bots"], "max_nodes": MAX_NODES, "max_prompt": MAX_PROMPT, "daily": DAILY_BONUS + pk["daily"],
            "ref_inviter": REF_INVITER, "ref_invitee": REF_INVITEE, "ref_max": REF_MAX_PER_USER, "ref_on": REF_ON,
            "milestones": REF_MILESTONES, "media_max_mb": MEDIA_MAX_MB, "media_quota_mb": MEDIA_QUOTA_MB + pk["mb"],
            "max_media": MAX_MEDIA + pk["files"], "disc": pk["disc"], "plans": plans_public(),
            "emoji_max": pk["emoji"], "btn_fx": 1 if pk["btn"] else 0,
            "games": 1, "db": 1, "ext_api": 1 if EXT_API else 0,
            "max_ub": ub_limit(uid), "ub_ok": 1 if ub_ready() else 0}


@app.errorhandler(413)
def too_big(_e):
    return jsonify(error=f"حجم فایل بیشتر از {MEDIA_MAX_MB} مگابایت نباید باشه"), 413


@app.after_request
def _secure(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/")
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "index.html")


@app.get("/healthz")
def healthz():
    try:
        db.command("ping") if MONGO_URI else None
        return jsonify(ok=True, t=now().isoformat())
    except Exception:
        return jsonify(ok=False), 503


@app.get("/api/me")
@authed
def api_me(uid):
    u = g.user
    m = re.fullmatch(r"ref_(\d{1,15})", u.get("_sp") or "")
    d, _ = ensure_user(uid, u.get("first_name", ""), int(m.group(1)) if m else None)
    touch_user(u)
    web = bool(u.get("_web"))
    me = {"id": uid, "name": (d.get("tg_name") or d.get("name") or "") if web else " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x),
          "username": (d.get("tg_user") or "") if web else (u.get("username") or ""), "web": web}
    bots = [public(b) for b in db.bots.find({"owner": uid}).sort("updated", -1)]
    items = media_list(uid)
    return jsonify(me=me, bots=bots, wallet=wallet_info(uid), cfg=client_cfg(uid), packs=PACKS, card=card_public(), media=items, plan=plan_info(uid), tasks=tasks_state(uid),
                   used=sum(i["size"] for i in items), admin=uid in ADMIN_IDS,
                   ref={"link": mother_link(uid), "count": int(d.get("refs", 0)), "earned": int(d.get("ref_earned", 0))},
                   joined=aware(d.get("created") or now()).isoformat(),
                   templates=[{"id": k, "icon": t["icon"], "title": t["title"], "desc": t["desc"], "feats": t.get("feats", []), "cost": template_cost(t, uid)} for k, t in TEMPLATES.items()])


@app.post("/api/ping")
@authed
def api_ping(uid):
    touch_user(g.user)
    return jsonify(ok=True)


@app.post("/api/daily")
@authed
def api_daily(uid):
    r = claim_daily(uid)
    if not r:
        return jsonify(error="جایزه‌ی امروز رو قبلاً گرفتی، فردا برگرد"), 400
    return jsonify(reward=r[0], streak=r[1], wallet=wallet_info(uid), cfg=client_cfg(uid), tasks=tasks_state(uid))


@app.get("/api/ledger")
@authed
def api_ledger(uid):
    rows = db.ledger.find({"uid": uid}).sort("t", -1).limit(30)
    return jsonify(items=[{"n": x.get("n", x.get("delta", 0)), "why": x.get("why", x.get("reason", "")), "t": aware(x["t"]).isoformat()} for x in rows])


@app.post("/api/coupon")
@authed
def api_coupon(uid):
    if not rate_ok(f"cp:{uid}", 8, 600):
        return jsonify(error="تعداد تلاش زیاد بود، چند دقیقه بعد امتحان کن"), 429
    ensure_user(uid)
    got, err = redeem(uid, (request.get_json(silent=True) or {}).get("code", ""))
    if err:
        return jsonify(error=err), 400
    return jsonify(got=got, wallet=wallet_info(uid))


@app.post("/api/buy")
@authed
def api_buy(uid):
    pid = str((request.get_json(silent=True) or {}).get("pack", ""))
    p = next((x for x in PACKS if x.get("id") == pid), None)
    if not p:
        return jsonify(error="بسته‌ی نامعتبر"), 400
    r = tg(MOTHER_TOKEN, "createInvoiceLink", title=f"{p['tokens']} توکن",
           description=f"بسته‌ی {p['tokens']} توکنی برای ساخت و ارتقای رباتا", payload=f"{pid}:{uid}",
           currency="XTR", prices=[{"label": f"{p['tokens']} توکن", "amount": int(p["stars"])}])
    if not r.get("ok"):
        log.warning("invoice failed: %s", r)
        return jsonify(error="ساخت فاکتور ناموفق بود، کمی بعد دوباره امتحان کن"), 502
    return jsonify(url=r["result"])


# ───────────────────────── ماموریت‌ها ─────────────────────────
@app.post("/api/tasks/<tid>/claim")
@authed
def api_task_claim(uid, tid):
    t = next((x for x in TASKS if x["id"] == tid), None)
    if not t:
        return jsonify(error="ماموریت پیدا نشد"), 404
    if not rate_ok(f"task:{uid}", 20, 60):
        return jsonify(error="کمی آروم‌تر؛ چند لحظه بعد دوباره امتحان کن"), 429
    d, _ = ensure_user(uid)
    done = set(d.get("tasks_done", []))
    st = next((x for x in task_steps(t) if x["key"] not in done), None)
    if not st:
        return jsonify(error="همه‌ی مرحله‌های این ماموریت کامل شده"), 400
    tk, sid = st["tokens"], st["key"]
    if task_metrics(uid, d)[st["metric"]] < st["goal"]:
        return jsonify(error="هنوز به هدف این مرحله نرسیدی"), 400
    if db.users.update_one({"_id": uid, "tasks_done": {"$ne": sid}}, {"$push": {"tasks_done": sid}}).modified_count != 1:
        return jsonify(error="این پاداش قبلاً دریافت شده"), 400
    if tk:
        credit(uid, tk, "task", key=f"task:{uid}:{sid}")
    return jsonify(gain={"tokens": tk}, tasks=tasks_state(uid), wallet=wallet_info(uid), cfg=client_cfg(uid))


# ───────────────────────── اشتراک و ایموجی پرمیوم ─────────────────────────
@app.post("/api/plan/buy")
@authed
def api_plan_buy(uid):
    pid = str((request.get_json(silent=True) or {}).get("plan", ""))
    p = PLAN_BY_ID.get(pid)
    if not p or pid == "free":
        return jsonify(error="پلن نامعتبر"), 400
    ensure_user(uid)
    cur = plan_of(db.users.find_one({"_id": uid}))
    if PLAN_RANK[pid] < PLAN_RANK[cur]:
        return jsonify(error=f"اشتراک {PLAN_BY_ID[cur]['title']} هنوز فعاله؛ بعد از پایانش می‌تونی این پلن رو بگیری"), 400
    r = tg(MOTHER_TOKEN, "createInvoiceLink", title=f"اشتراک {p['title']}"[:32],
           description=f"اشتراک {p['title']} برای {PLAN_DAYS} روز و {p['tokens']} توکن هدیه"[:255], payload=f"sub_{pid}:{uid}",
           currency="XTR", prices=[{"label": f"اشتراک {p['title']}", "amount": int(p["stars"])}])
    if not r.get("ok"):
        log.warning("plan invoice failed: %s", r)
        return jsonify(error="ساخت فاکتور ناموفق بود، کمی بعد دوباره امتحان کن"), 502
    return jsonify(url=r["result"])


@app.get("/api/emojis")
@authed
def api_emojis(uid):
    return jsonify(items=emoji_list(uid), max=perks_of(uid)["emoji"])


@app.delete("/api/emojis/<eid>")
@authed
def api_emoji_del(uid, eid):
    digits = re.sub(r"\D", "", eid)
    db.emojis.delete_one({"_id": f"{uid}:{digits}"})
    return jsonify(items=emoji_list(uid), max=perks_of(uid)["emoji"])


@app.get("/e/<eid>")
def emoji_img(eid):
    if not hmac.compare_digest(emoji_sig(eid), request.args.get("s", "")):
        return "", 403
    r = emoji_image(eid)
    if not r:
        return "", 404
    return Response(r[0], mimetype=r[1], headers={"Cache-Control": "public, max-age=86400"})


# ───────────────────────── ساخت و ارتقا با هوش مصنوعی: مسیرها ─────────────────────────
@app.post("/api/generate")
@authed
def api_generate(uid):
    body = request.get_json(silent=True) or {}
    prompt = str(body.get("prompt", "")).strip()[:MAX_PROMPT]
    if len(prompt) < 5:
        return jsonify(error="توضیح خیلی کوتاهه"), 400
    bot = None
    if body.get("bot_id"):
        bot = get_bot(body["bot_id"], uid)
        if not bot:
            return jsonify(error="ربات پیدا نشد"), 404
    elif db.bots.count_documents({"owner": uid}) >= max_bots(uid):
        return jsonify(error=f"حداکثر {max_bots(uid)} ربات می‌تونی داشته باشی. با خرید اشتراک Premium یا Pro، سقفت بیشتر می‌شه."), 400
    if not rate_ok(f"gen:{uid}", 10, 60):
        return jsonify(error="کمی آروم‌تر؛ چند لحظه بعد دوباره امتحان کن"), 429
    for j in db.jobs.find({"uid": uid, "status": {"$in": ["running", "saving"]}}):
        if age_sec(j["t"]) < JOB_TIMEOUT:
            return jsonify(error="یه کار دیگه‌ات هنوز در حال انجامه، چند لحظه صبر کن"), 409
    ensure_user(uid)
    reserve = reserve_cost(prompt, bot["config"] if bot else None, uid)
    if not hold(uid, reserve):
        msg = (f"توکن کافی نداری. این کار {reserve} توکن می‌خواد." if BILLING == "fixed"
               else f"توکن کافی نداری. برای این درخواست حداقل {reserve} توکن لازمه (هزینه‌ی واقعی معمولاً کمتره و فقط همون بعد از ساخت کم می‌شه).")
        return jsonify(error=msg, need=reserve, wallet=wallet_info(uid)), 402
    jid = secrets.token_hex(8)
    db.jobs.insert_one({"_id": jid, "uid": uid, "status": "running", "hold": 0, "t": now()})
    threading.Thread(target=gen_job, args=(jid, uid, str(bot["_id"]) if bot else None, prompt, reserve), daemon=True).start()
    return jsonify(job=jid, hold=reserve, wallet=wallet_info(uid))


@app.get("/api/jobs/<jid>")
@authed
def api_job(uid, jid):
    j = db.jobs.find_one({"_id": jid, "uid": uid})
    if not j:
        return jsonify(error="کار پیدا نشد"), 404
    if j["status"] == "running" and age_sec(j["t"]) > JOB_TIMEOUT:
        db.jobs.find_one_and_update({"_id": jid, "status": "running"}, {"$set": {
                "status": "error", "error": "ساخت بیش از حد طول کشید و چیزی از توکن‌هات کم نشد. دوباره امتحان کن."}})
        j = db.jobs.find_one({"_id": jid})
    out = {"status": "running" if j["status"] == "saving" else j["status"], "wallet": wallet_info(uid)}
    if j["status"] in ("running", "saving") and j.get("prog"):
        out["prog"] = {k: j["prog"].get(k) for k in ("p", "st", "n", "ti", "th", "att")}
    if j["status"] == "done":
        b = get_bot(j["bot"], uid)
        out.update(bot=public(b) if b else None, ideas=j.get("ideas", []), cost=j.get("cost", 0))
    elif j["status"] == "error":
        out["error"] = j.get("error", "ناموفق بود")
    return jsonify(out)


@app.post("/api/enhance")
@authed
def api_enhance(uid):
    """بازنویسی توضیح خام کاربر به یک شرح کامل و دقیق (ارزون)"""
    prompt = str((request.get_json(silent=True) or {}).get("prompt", "")).strip()[:MAX_PROMPT]
    if len(prompt) < 5:
        return jsonify(error="اول یه توضیح کوتاه بنویس"), 400
    if not rate_ok(f"enh:{uid}", 6, 60):
        return jsonify(error="کمی آروم‌تر؛ چند لحظه بعد دوباره امتحان کن"), 429
    ensure_user(uid)
    ecost = 0 if perks_of(uid)["free_enhance"] else ENHANCE_COST
    if ecost and not spend(uid, ecost, "enhance"):
        return jsonify(error=f"توکن کافی نداری. این کار {ecost} توکن می‌خواد.", need=ecost, wallet=wallet_info(uid)), 402
    try:
        text = enhance_prompt(prompt)
    except Exception:
        log.exception("enhance failed")
        if ecost:
            refund(uid, ecost)
        return jsonify(error="بهینه‌سازی ناموفق بود و توکنت برگشت. دوباره امتحان کن."), 502
    return jsonify(prompt=text, wallet=wallet_info(uid))


@app.post("/api/templates/<tid>/create")
@authed
def api_template_create(uid, tid):
    t = TEMPLATES.get(tid)
    if not t:
        return jsonify(error="قالب پیدا نشد"), 404
    ensure_user(uid)
    if db.bots.count_documents({"owner": uid}) >= max_bots(uid):
        return jsonify(error=f"حداکثر {max_bots(uid)} ربات می‌تونی داشته باشی. با خرید اشتراک Premium یا Pro، سقفت بیشتر می‌شه."), 400
    cost = template_cost(t, uid)
    cfg = sanitize(t["config"])
    if cost and not spend(uid, cost, "template"):
        return jsonify(error=f"توکن کافی نداری. این قالب {cost} توکن می‌خواهد.", need=cost, wallet=wallet_info(uid)), 402
    try:
        bot = new_bot_doc(uid, cfg, t["note"])
    except Exception:
        if cost:
            refund(uid, cost)
        raise
    if REF_ON == "create":
        settle_referral(uid)
    return jsonify(bot=public(bot), wallet=wallet_info(uid), cost=cost)


@app.post("/api/bots/<bot_id>/undo")
@authed
def api_undo(uid, bot_id):
    bot = get_bot(bot_id, uid)
    if not bot or not bot.get("versions"):
        return jsonify(error="نسخه‌ی قبلی وجود نداره"), 400
    prev = bot["versions"][-1]
    db.bots.update_one({"_id": bot["_id"]}, {
        "$set": {"config": prev, "name": prev["name"], "thinking": "", "updated": now()},
        "$pop": {"versions": 1}})
    bot = db.bots.find_one({"_id": bot["_id"]})
    sync_commands(bot, bot["config"])
    return jsonify(bot=public(bot))


def fx_use(cfg):
    """(تعداد ایموجی پرمیوم و آیکن دکمه، تعداد دکمه‌ی رنگی) داخل یک کانفیگ"""
    txt = json.dumps(cfg, ensure_ascii=False)
    btns = [b for nd in cfg.get("nodes", {}).values() for row in nd.get("buttons", []) for b in row]
    return txt.count("<tg-emoji") + sum(1 for b in btns if b.get("icon")), sum(1 for b in btns if b.get("style"))


@app.put("/api/bots/<bot_id>/config")
@authed
def api_save_config(uid, bot_id):
    """ذخیره‌ی ویرایش دستی (بدون مصرف توکن)"""
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    try:
        cfg = sanitize((request.get_json(silent=True) or {}).get("config"), strict=True, media=own_media_ids(uid))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    pk = perks_of(uid)
    ne, ns = fx_use(cfg)
    oe, os_ = fx_use(bot["config"])
    if (ne > oe and not pk["emoji"]) or (ns > os_ and not pk["btn"]):
        return jsonify(error="ایموجی پرمیوم و دکمه‌ی رنگی با اشتراک Premium یا Pro فعال می‌شن.", need_plan=True), 403
    if cfg != bot["config"]:
        lm = bot.get("last_manual")
        recent = lm and age_sec(lm) < 180
        upd = {"$set": {"config": cfg, "name": cfg["name"], "thinking": "", "updated": now(), "last_manual": now()}}
        if not recent:      # ویرایش‌های پشت‌سرهم یک نسخه‌ی برگشت حساب می‌شن
            upd["$push"] = {"versions": {"$each": [bot["config"]], "$slice": -(MAX_VERSIONS + perks_of(uid)["ver"])}}
        db.bots.update_one({"_id": bot["_id"]}, upd)
        bot = db.bots.find_one({"_id": bot["_id"]})
        sync_commands(bot, cfg)
    return jsonify(bot=public(bot))


@app.get("/api/bots/<bot_id>/export")
@authed
def api_export(uid, bot_id):
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    return jsonify(format="botmaker/2", config=bot["config"])


@app.get("/api/bots/<bot_id>/health")
@authed
def api_health(uid, bot_id):
    """چک سلامت مسیرها: بخش‌های گم‌شده، بن‌بست‌ها و متغیرهای بدون مقدار (رایگان)"""
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    try:
        issues = lint_fa(bot["config"], lint(bot["config"]))
    except Exception:
        issues = []
    return jsonify(issues=issues, nodes=len(bot["config"]["nodes"]))


@app.post("/api/bots/<bot_id>/activate")
@authed
def api_activate(uid, bot_id):
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    token = str((request.get_json(silent=True) or {}).get("token", "")).strip()
    doc, err = do_activate(bot, token)
    if err:
        return jsonify(error=err[0]), err[1]
    return jsonify(bot=public(doc))


@app.post("/api/bots/<bot_id>/deactivate")
@authed
def api_deactivate(uid, bot_id):
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    if bot.get("token_enc"):
        tg(dec(bot["token_enc"]), "deleteWebhook")
    db.bots.update_one({"_id": bot["_id"]}, {
        "$set": {"active": False, "updated": now()}, "$unset": {"token_enc": "", "token_hash": ""}})
    return jsonify(bot=public(db.bots.find_one({"_id": bot["_id"]})))


@app.delete("/api/bots/<bot_id>")
@authed
def api_delete(uid, bot_id):
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    if bot.get("token_enc"):
        tg(dec(bot["token_enc"]), "deleteWebhook")
    db.bots.delete_one({"_id": bot["_id"]})
    db.subs.delete_many({"bot": bot_id})
    db.submissions.delete_many({"bot_id": bot_id})
    db.nvis.delete_many({"bot": bot_id})
    for col in (db.states, db.rk, db.uvars, db.relay, db.mfid, db.aiuse):
        col.delete_many({"_id": {"$regex": f"^{bot_id}:"}})
    return jsonify(ok=True)


# ───────────────────────── آمار، پاسخ فرم‌ها و پیام همگانی ─────────────────────────
@app.get("/api/bots/<bot_id>/stats")
@authed
def api_stats(uid, bot_id):
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    q = {"bot": bot_id}
    try:
        t = naive()
        week, day = t - timedelta(days=7), t - timedelta(days=1)
        out = {"users": db.subs.count_documents(q),
               "active7": db.subs.count_documents({**q, "last": {"$gt": week}}),
               "new24": db.subs.count_documents({**q, "t": {"$gt": day}}),
               "blocked": db.subs.count_documents({**q, "blocked": True})}
        d0 = t.replace(hour=0, minute=0, second=0, microsecond=0)
        series = []
        for i in range(6, -1, -1):
            a, b = d0 - timedelta(days=i), d0 - timedelta(days=i - 1)
            series.append(db.subs.count_documents({**q, "t": {"$gte": a, "$lt": b}}))
        out["series"] = series
    except Exception:
        log.exception("stats failed")
        out = {"users": db.subs.count_documents(q), "active7": 0, "new24": 0, "blocked": 0, "series": [0] * 7}
    cfg_nodes = (bot.get("config") or {}).get("nodes", {})
    out["forms"] = db.submissions.count_documents({"bot_id": bot_id})
    out["ai_tokens"] = int(bot.get("ai_tokens", 0))
    out["top"] = [{"id": r["node"], "title": (cfg_nodes.get(r["node"]) or {}).get("title") or r["node"], "n": int(r.get("n", 0))}
                  for r in db.nvis.find({"bot": bot_id}).sort("n", -1).limit(5) if r["node"] in cfg_nodes]
    return jsonify(out)


@app.get("/api/bots/<bot_id>/submissions")
@authed
def api_submissions(uid, bot_id):
    if not get_bot(bot_id, uid):
        return jsonify(error="ربات پیدا نشد"), 404
    rows = db.submissions.find({"bot_id": bot_id}).sort("t", -1).limit(50)
    return jsonify(items=[{"title": r.get("title", ""), "name": r.get("name", ""), "un": r.get("un", ""), "qa": r.get("qa", []),
                           "text": r.get("text", ""), "t": aware(r["t"]).isoformat()} for r in rows])


def run_broadcast(bot, chats, text, mid, owner, fmt=""):
    bot_id, token, ok = str(bot["_id"]), dec(bot["token_enc"]), 0
    try:
        for chat in chats:
            sent, blocked = send_rich(token, bot_id, chat, text, mid, fmt)
            if blocked:
                db.subs.update_one({"_id": f"{bot_id}:{chat}"}, {"$set": {"blocked": True}})
            ok += 1 if sent else 0
            time.sleep(0.04)
    except Exception:
        log.exception("broadcast crashed")
    finally:
        db.bots.update_one({"_id": bot["_id"]}, {"$unset": {"bc_at": ""}})
    tg(MOTHER_TOKEN, "sendMessage", chat_id=owner,
       text=f"پیام همگانی ربات «{bot.get('name', '')}» تموم شد. به {ok} نفر از {len(chats)} نفر رسید.")


@app.post("/api/bots/<bot_id>/broadcast")
@authed
def api_broadcast(uid, bot_id):
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    if not (bot.get("active") and bot.get("token_enc")):
        return jsonify(error="اول ربات رو فعال کن"), 400
    b = request.get_json(silent=True) or {}
    text = str(b.get("text", "")).strip()[:3500]
    mid = str(b.get("media") or "")
    if mid and not get_media(mid, uid):
        mid = ""
    fmt = "html" if b.get("fmt") == "html" else ""
    if fmt and not perks_of(uid)["emoji"]:
        text = strip_fx_text(text)
    if not text and not mid:
        return jsonify(error="متن یا رسانه‌ی پیام رو وارد کن"), 400
    if bot.get("bc_at") and age_sec(bot["bc_at"]) < 1800:
        return jsonify(error="یه پیام همگانی دیگه هنوز در حال ارساله"), 409
    chats = [s["chat"] for s in db.subs.find({"bot": bot_id, "blocked": {"$ne": True}}, {"chat": 1})][:BROADCAST_MAX + perks_of(uid)["bc"]]
    if not chats:
        return jsonify(error="هنوز کاربری نداری که بهش پیام بدی"), 400
    cost = cut(uid, max(TOKEN_SCALE, math.ceil(len(chats) / BROADCAST_PER_TOKEN)))
    if not spend(uid, cost, "broadcast"):
        return jsonify(error=f"توکن کافی نداری. این ارسال {cost} توکن می‌خواد.", need=cost, wallet=wallet_info(uid)), 402
    db.bots.update_one({"_id": bot["_id"]}, {"$set": {"bc_at": now()}})
    threading.Thread(target=run_broadcast, args=(bot, chats, text, mid, uid, fmt), daemon=True).start()
    return jsonify(queued=len(chats), cost=cost, wallet=wallet_info(uid))


# ───────────────────────── رسانه ─────────────────────────
@app.get("/api/media")
@authed
def api_media_list(uid):
    items = media_list(uid)
    return jsonify(media=items, used=sum(i["size"] for i in items))


@app.post("/api/media")
@authed
def api_media_up(uid):
    data = request.get_data()
    if not data:
        return jsonify(error="فایل خالیه"), 400
    if len(data) > MEDIA_MAX_MB * 1024 * 1024:
        return jsonify(error=f"حجم فایل بیشتر از {MEDIA_MAX_MB} مگابایت نباید باشه"), 413
    name = re.sub(r"[\\/\x00-\x1f]", "_", unquote(request.headers.get("X-Filename", "file")).strip())[:80] or "file"
    existing = list(db.media.find({"owner": uid}, {"size": 1}))
    pk = perks_of(uid)
    if len(existing) >= MAX_MEDIA + pk["files"]:
        return jsonify(error=f"حداکثر {MAX_MEDIA + pk['files']} فایل می‌تونی داشته باشی"), 400
    if sum(int(x.get("size", 0)) for x in existing) + len(data) > (MEDIA_QUOTA_MB + pk["mb"]) * 1024 * 1024:
        return jsonify(error="فضای رسانه‌ات پر شده؛ چند فایل قدیمی رو پاک کن"), 400
    mime = (request.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    mid = ObjectId()
    for i in range(0, len(data), CHUNK):
        db.mchunks.insert_one({"_id": f"{mid}:{i // CHUNK}", "m": str(mid), "i": i // CHUNK, "d": Binary(data[i:i + CHUNK])})
    doc = {"_id": mid, "owner": uid, "name": name, "kind": media_kind(mime, name, len(data)), "mime": mime,
           "size": len(data), "created": now()}
    db.media.insert_one(doc)
    return jsonify(item=public_media(doc), used=media_used(uid))


@app.put("/api/media/<mid>")
@authed
def api_media_rename(uid, mid):
    m = get_media(mid, uid)
    if not m:
        return jsonify(error="فایل پیدا نشد"), 404
    name = re.sub(r"[\\/\x00-\x1f]", "_", str((request.get_json(silent=True) or {}).get("name", "")).strip())[:80]
    if not name:
        return jsonify(error="اسم فایل نباید خالی باشه"), 400
    db.media.update_one({"_id": m["_id"]}, {"$set": {"name": name}})
    return jsonify(item=public_media(get_media(mid, uid)))


@app.delete("/api/media/<mid>")
@authed
def api_media_del(uid, mid):
    m = get_media(mid, uid)
    if not m:
        return jsonify(error="فایل پیدا نشد"), 404
    media_delete(m)
    return jsonify(ok=True, used=media_used(uid))


@app.get("/m/<mid>")
def media_get(mid):
    """پیش‌نمایش عکس‌ها داخل مینی‌اپ (لینک امضاشده)"""
    if not hmac.compare_digest(request.args.get("s", ""), media_sig(mid)):
        return "forbidden", 403
    m = get_media(mid)
    if not m:
        return "not found", 404
    safe = m.get("mime") in SAFE_INLINE and m["kind"] in ("photo", "animation")
    resp = Response(media_bytes(m), mimetype=m["mime"] if safe else "application/octet-stream")
    resp.headers["Cache-Control"] = "private, max-age=86400"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    if not safe:
        resp.headers["Content-Disposition"] = "attachment"
    return resp


# ───────────────────────── پنل ادمین ─────────────────────────
@app.get("/api/admin/stats")
@admin_only
def api_admin_stats(uid):
    users = list(db.users.find({}, {"tokens": 1, "refs": 1, "seen": 1, "created": 1}))
    cut, day = naive() - timedelta(seconds=ONLINE_SECS), naive() - timedelta(days=1)
    return jsonify(users=len(users), bots=db.bots.count_documents({}), active=db.bots.count_documents({"active": True}),
                   circulation=sum(int(u.get("tokens", 0)) for u in users), referrals=sum(int(u.get("refs", 0)) for u in users),
                   bot_users=db.subs.count_documents({}), forms=db.submissions.count_documents({}),
                   online=sum(1 for u in users if u.get("seen") and naive(u["seen"]) >= cut),
                   new24=sum(1 for u in users if u.get("created") and naive(u["created"]) >= day))


@app.get("/api/admin/users")
@admin_only
def api_admin_users(uid):
    cut = naive() - timedelta(seconds=ONLINE_SECS)
    total = db.users.count_documents({})
    online = db.users.count_documents({"seen": {"$gte": cut}})
    users = list(db.users.find({}, {"seen": 1, "tg_user": 1, "tg_name": 1, "created": 1, "tokens": 1, "mb_blocked": 1}).sort("seen", -1).limit(300))
    by = {}
    for bt in db.bots.find({"owner": {"$in": [x["_id"] for x in users]}}, {"owner": 1, "username": 1, "name": 1, "active": 1}):
        by.setdefault(bt["owner"], []).append({"id": str(bt["_id"]), "name": bt.get("name", ""), "un": bt.get("username") or "", "on": bool(bt.get("active"))})
    out = []
    for x in users:
        seen = naive(x["seen"]) if x.get("seen") else None
        out.append({"id": x["_id"], "un": x.get("tg_user", ""), "name": x.get("tg_name", ""), "tokens": int(x.get("tokens", 0)),
                    "online": bool(seen and seen >= cut), "seen": seen.isoformat() + "Z" if seen else "", "bots": by.get(x["_id"], []),
                    "blocked": bool(x.get("mb_blocked"))})
    out.sort(key=lambda r: (not r["online"], r["seen"] == "", ""))
    return jsonify(items=out, total=total, online=online, blocked=db.users.count_documents({"mb_blocked": True}), scan=scan_state(scan_key()))


@app.post("/api/admin/grant")
@admin_only
def api_admin_grant(uid):
    b = request.get_json(silent=True) or {}
    try:
        target, amount = int(b.get("uid")), int(b.get("amount"))
    except (TypeError, ValueError):
        return jsonify(error="آیدی یا مقدار نامعتبره"), 400
    if not db.users.find_one({"_id": target}):
        return jsonify(error="کاربر پیدا نشد"), 404
    if amount > 0:
        credit(target, amount, "admin")
    elif amount < 0:
        charge_up_to(target, -amount, "admin")
    return jsonify(bal=balance(target))


@app.post("/api/admin/plan")
@admin_only
def api_admin_plan(uid):
    b = request.get_json(silent=True) or {}
    try:
        target, days = int(b.get("uid")), int(b.get("days") or 0)
    except (TypeError, ValueError):
        return jsonify(error="آیدی یا تعداد روز نامعتبره"), 400
    pid = str(b.get("plan", ""))
    if pid not in PLAN_BY_ID:
        return jsonify(error="پلن نامعتبره"), 400
    if not db.users.find_one({"_id": target}):
        return jsonify(error="کاربر پیدا نشد"), 404
    activate_plan(target, pid, days or None)
    return jsonify(plan=plan_info(target))


@app.post("/api/admin/coupon")
@admin_only
def api_admin_coupon(uid):
    b = request.get_json(silent=True) or {}
    try:
        tokens, mx, days = int(b.get("tokens")), int(b.get("max_uses") or 1), int(b.get("days") or 0)
    except (TypeError, ValueError):
        return jsonify(error="مقادیر نامعتبره"), 400
    code = re.sub(r"[^A-Za-z0-9_\-]", "", str(b.get("code") or "")).upper()[:32] or secrets.token_hex(4).upper()
    if tokens < 1 or mx < 1:
        return jsonify(error="مقادیر نامعتبره"), 400
    doc = {"_id": code, "tokens": tokens, "max": mx, "used": 0, "used_by": [], "created": now()}
    if days > 0:
        doc["exp"] = now() + timedelta(days=days)
    try:
        db.coupons.insert_one(doc)
    except DuplicateKeyError:
        return jsonify(error="این کد قبلاً ساخته شده"), 400
    return jsonify(code=code)


@app.post("/api/admin/announce")
@admin_only
def api_admin_announce(uid):
    b = request.get_json(silent=True) or {}
    ids = None
    if b.get("ids") is not None:
        try:
            ids = list({int(x) for x in b["ids"]})[:500]
        except (TypeError, ValueError):
            return jsonify(error="لیست کاربران نامعتبره"), 400
        if not ids:
            return jsonify(error="اول کاربرها رو انتخاب کن"), 400
    n, err = start_announce(b.get("text"), uid, builders=bool(b.get("builders", True)), audience=bool(b.get("audience", False)),
                            mid=b.get("media") or "", fmt="html" if b.get("fmt") == "html" else "", ids=ids)
    if err:
        return jsonify(error=err), 400
    return jsonify(queued=n)


# ───────────────────────── بررسی دوباره‌ی بلاک‌ها و مخاطبان (مسیرهای ادمین) ─────────────────────────
@app.post("/api/admin/users/refresh-blocks")
@admin_only
def api_admin_users_rb(uid):
    return jsonify(started=start_block_scan(None, uid))


def _admin_bot(bot_id):
    try:
        return db.bots.find_one({"_id": ObjectId(bot_id)})
    except InvalidId:
        return None


@app.get("/api/admin/bots/<bot_id>/audience")
@admin_only
def api_admin_bot_audience(uid, bot_id):
    bot = _admin_bot(bot_id)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    cut_on = naive() - timedelta(seconds=300)
    rows = list(db.subs.find({"bot": bot_id}).sort("last", -1).limit(500))
    known = {u["_id"]: u for u in db.users.find({"_id": {"$in": [r.get("uid") for r in rows]}}, {"tg_user": 1, "tg_name": 1})}
    items = []
    for r in rows:
        u = known.get(r.get("uid"), {})
        last = naive(r["last"]) if r.get("last") else None
        items.append({"id": r.get("uid"), "un": r.get("un") or u.get("tg_user", ""), "name": r.get("nm") or u.get("tg_name", ""),
                      "online": bool(last and last >= cut_on and not r.get("blocked")), "seen": last.isoformat() + "Z" if last else "",
                      "joined": naive(r["t"]).isoformat() + "Z" if r.get("t") else "", "blocked": bool(r.get("blocked")),
                      "owner": r.get("uid") == bot["owner"]})
    total = db.subs.count_documents({"bot": bot_id})
    return jsonify(bot={"id": bot_id, "name": bot.get("name", ""), "un": bot.get("username") or "", "on": bool(bot.get("active") and bot.get("token_enc")),
                        "owner": bot["owner"]},
                   items=items, total=total, blocked=db.subs.count_documents({"bot": bot_id, "blocked": True}),
                   online=sum(1 for x in items if x["online"]), scan=scan_state(scan_key(bot)))


@app.post("/api/admin/bots/<bot_id>/refresh-blocks")
@admin_only
def api_admin_bot_rb(uid, bot_id):
    bot = _admin_bot(bot_id)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    if not (bot.get("active") and bot.get("token_enc")):
        return jsonify(error="این ربات فعال نیست"), 400
    return jsonify(started=start_block_scan(bot, uid))


@app.post("/api/admin/bots/<bot_id>/send")
@admin_only
def api_admin_bot_send(uid, bot_id):
    bot = _admin_bot(bot_id)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    if not (bot.get("active") and bot.get("token_enc")):
        return jsonify(error="این ربات فعال نیست"), 400
    b = request.get_json(silent=True) or {}
    text = str(b.get("text", "")).strip()[:3500]
    mid = str(b.get("media") or "")
    if mid and not get_media(mid, uid):
        mid = ""
    fmt = "html" if b.get("fmt") == "html" else ""
    if not mid and len(text) < 2:
        return jsonify(error="متن یا رسانه‌ی پیام رو وارد کن"), 400
    scope = b.get("scope")
    if scope in ("one", "many"):
        raw = b.get("uids") if scope == "many" else [b.get("uid")]
        try:
            ids = list({int(x) for x in (raw or [])})[:500]
        except (TypeError, ValueError):
            return jsonify(error="کاربر نامعتبره"), 400
        if not ids:
            return jsonify(error="اول کاربرها رو انتخاب کن"), 400
        subs = list(db.subs.find({"bot": bot_id, "uid": {"$in": ids}}))
        if not subs:
            return jsonify(error="این کاربرها مخاطب این ربات نیستن"), 404
        if len(subs) == 1:
            sub = subs[0]
            sent, blocked = send_rich(dec(bot["token_enc"]), bot_id, sub["chat"], text, mid, fmt)
            if not sent:
                if blocked:
                    db.subs.update_one({"_id": sub["_id"]}, {"$set": {"blocked": True}})
                return jsonify(error="ارسال نشد؛ احتمالاً کاربر ربات رو بلاک کرده"), 502
            if sub.get("blocked"):
                db.subs.update_one({"_id": sub["_id"]}, {"$set": {"blocked": False}})
            return jsonify(queued=1)
        chats = [x["chat"] for x in subs]
    else:
        q = {"bot": bot_id, "blocked": {"$ne": True}}
        if scope == "except_owner":
            q["uid"] = {"$ne": bot["owner"]}
        elif scope != "all":
            return jsonify(error="نوع گیرنده نامعتبره"), 400
        chats = [x["chat"] for x in db.subs.find(q, {"chat": 1})]
    if not chats:
        return jsonify(error="گیرنده‌ای پیدا نشد"), 400
    try:
        db.locks.insert_one({"_id": f"abc:{bot_id}", "t": now()})
    except DuplicateKeyError:
        lk = db.locks.find_one({"_id": f"abc:{bot_id}"})
        if lk and age_sec(lk["t"]) < 1800:
            return jsonify(error="یه ارسال دیگه برای این ربات هنوز در حاله"), 409
        db.locks.update_one({"_id": f"abc:{bot_id}"}, {"$set": {"t": now()}})
    threading.Thread(target=run_admin_send, args=(bot, chats, text, uid, mid, fmt), daemon=True).start()
    return jsonify(queued=len(chats))


@app.get("/api/admin/audience")
@admin_only
def api_admin_audience(uid):
    return jsonify(builders=db.users.count_documents({}), bots=db.bots.count_documents({"active": True}),
                   audience=sum(len(c) for _, _, c in audience_targets()))


# ───────────────────────── تنظیمات تبلیغ روی ورودی‌های جدید (پنل ادمین) ─────────────────────────
def _clamp(v, lo, hi, d):
    try:
        return max(lo, min(hi, int(float(str(v).translate(_DIG).strip()))))
    except (TypeError, ValueError):
        return d


@app.get("/api/admin/promo")
@admin_only
def api_admin_promo_get(uid):
    d = db.settings.find_one({"_id": "promo"}) or {}
    st = db.settings.find_one({"_id": "promo_stats"}) or {}
    return jsonify(on=bool(d.get("on")), min_users=int(d.get("min_users", 10)), pct=int(d.get("pct", 30)), lock_pct=int(d.get("lock_pct", 20)),
                   channels=" ".join(fj_str(c) for c in d.get("channels", [])), text=d.get("text") or PROMO_DEF_TEXT,
                   lock_text=d.get("lock_text") or PROMO_DEF_LOCK, stats={k: int(st.get(k, 0)) for k in ("msg", "lock", "joined")})


@app.post("/api/admin/promo")
@admin_only
def api_admin_promo_set(uid):
    b = request.get_json(silent=True) or {}
    chans, err = fj_parse(b.get("channels"))
    if err:
        return jsonify(error=err), 400
    eff = chans or (db.settings.find_one({"_id": "force_join"}) or {}).get("channels") or []
    if b.get("on") and not eff:
        return jsonify(error="برای روشن کردن، یک کانال بنویس (یا اول عضویت اجباری ربات‌ساز را تنظیم کن)"), 400
    warn = []
    for c in eff:
        r = tg(MOTHER_TOKEN, "getChatMember", chat_id=fj_chat(c), user_id=uid)
        if not r.get("ok"):
            warn.append(f"{c['id']}: ربات مادر باید ادمین این کانال باشه (یا آیدی درست نیست)؛ تا اون موقع کسی قفل نمی‌شه")
    db.settings.update_one({"_id": "promo"}, {"$set": {
        "on": bool(b.get("on")) and bool(eff), "channels": chans,
        "min_users": _clamp(b.get("min_users"), 0, 10_000_000, 10), "pct": _clamp(b.get("pct"), 0, 100, 30),
        "lock_pct": _clamp(b.get("lock_pct"), 0, 100, 20),
        "text": str(b.get("text") or "").strip()[:1500] or PROMO_DEF_TEXT,
        "lock_text": str(b.get("lock_text") or "").strip()[:1500] or PROMO_DEF_LOCK, "by": uid, "t": time.time()}}, upsert=True)
    PROMO_CONF[0] = 0.0
    return jsonify(ok=True, warn=warn)


# ───────────────────────── راه‌اندازی ─────────────────────────
recover_jobs()
setup_mother()
if SCHED_ON:
    threading.Thread(target=sched_loop, daemon=True, name="sched").start()
if ub_ready():
    threading.Thread(target=ub_boot, daemon=True, name="ub-boot").start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
