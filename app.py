# -*- coding: utf-8 -*-
"""
BotMaker Ultimate — ابر رباتساز هوشمند (نسخه‌ی نهایی)
نقطه‌ی ورود: gunicorn app:app   یا   python app.py

ساختار پروژه (۱۳ فایل)
  app.py            این فایل: مسیرهای HTTP مینی‌اپ و ادمین + راه‌اندازی برنامه
  core.py           هسته: تنظیمات، دیتابیس، ابزارهای پایه، احراز هویت، کیف توکن، اشتراک و ماموریت، ایموجی پرمیوم، رسانه
  ai.py             هوش مصنوعی: دستورالعمل طراحی، اعتبارسنج کانفیگ، ارتباط با مدل، قالب‌های آماده
  engine.py         موتور اجرای ربات‌ها: اکشن‌ها، ارسال بخش، فرم، تیکت، پرداخت، مدیریت گروه، وب‌هوک
  webapp.py         مینی‌اپ‌ساز: اسکیما و sanitize_app، مسیرهای سازنده، رانتایم /a و /rt، ساخت با AI، قالب‌ها
  mother.py         ربات مادر، ساخت داخل چت، کار ساخت با AI، اعلان همگانی، عضویت اجباری، کارت‌به‌کارت، یوزربات
  index.html        اسکلت مینی‌اپ سازنده (فقط ساختار؛ استایل و کد جدا هستند)
  mapp.html         صفحه‌ی رانتایم مینی‌اپ‌های ساخته‌شده (استایل داخلی؛ بدون اسکریپت inline به‌خاطر CSP)
  static/style.css  همه‌ی استایل‌های سازنده
  static/app.js     پوسته‌ی مینی‌اپ سازنده: وضعیت، ارتباط با سرور، صفحه‌ها، حساب، ماموریت، مدیریت، یوزربات
  static/studio.js  ویرایشگر ربات: استودیوی گرافیکی و شیت‌های ویرایش
  static/builder.js تب «مینی‌اپ»: ویرایشگر بلوکی، پیش‌نمایش زنده، انتشار، نسخه‌ها، آمار
  static/mapp.js    رانتایم ثابت مینی‌اپ کاربر نهایی: رندر کانفیگ JSON بدون اجرای هیچ کدی

قاعده‌ی وابستگی (بک‌اند):  core ← ai ← engine ← webapp ← mother ← app
  هر فایل فقط از فایل‌های قبل از خودش import می‌کنه؛ هیچ‌وقت برعکس (تا وابستگی دایره‌ای پیش نیاد).
  در بالای هر فایل، خط‌های import دقیقاً نشون می‌دن از کدوم فایل چی استفاده می‌شه.
قاعده‌ی فرانت: اسکریپت‌ها به ترتیبِ تگ‌های script توی index.html بارگذاری می‌شن (app.js بعد studio.js بعد builder.js).

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
  یوزربات: اتصال اکانت شخصی تلگرام با شماره (Telethon)، پاسخ خودکار، پیام غیبت، پاسخ هوشمند، دستورهای شخصی،
           پاسخ در گروه‌های انتخابی و پیام زمان‌بندی‌شده برای گروه/کانال با سطح ایمنی و صف
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
    activate_plan, ADMIN_IDS, admin_only, age_sec, AI_MSG_COST, AI_MSGS_PER_TOKEN, ai_per, app, asset_v, assets_stamp, authed, aware, BASE_URL, dec,
    balance, BILLING, BROADCAST_MAX, BROADCAST_PER_TOKEN, BUILD, caps_public, charge_up_to, CHUNK, claim_daily, credit,
    cut, DAILY_BONUS, db, _DIG, EDIT_COST, ENHANCE_COST, ensure_user, est_tokens, FEATURES_ON,
    emoji_image, emoji_list, emoji_sig, fj_chat, GEN_COST, get_bot, get_media, hold, JOB_TIMEOUT, BOT_BUILD_TIMEOUT, log, limits_of, MAX_BOTS,
    max_bots, MAX_MEDIA, MAX_NODES, MAX_PROMPT, MAX_VERSIONS, media_bytes, media_delete, media_kind,
    media_list, MEDIA_MAX_MB, MEDIA_QUOTA_MB, media_sig, MONGO_URI, mother_link, MOTHER_TOKEN, naive,
    now, ONLINE_SECS, PACKS, PLAN_BY_ID, PLAN_DAYS, PLAN_RANK, plan_info, plan_of, plans_public, perks_of, public, public_media, rate_ok, redeem, REF_INVITEE, REF_INVITER,
    REF_MAX_PER_USER, REF_MILESTONES, REF_ON, refund, SAFE_INLINE, SCHED_ON, send_rich, strip_fx_text,
    settle_referral, setup_mother, spend, task_metrics, task_steps, TASKS, tasks_state,
    TEMPLATE_FACTOR, TEMPLATE_MAX_COST, TEMPLATE_MIN_COST, TEMPLATE_UNIT_COST, tg, TOKEN_MIN_COST,
    SECRET_KEY, TOKEN_OUT_RATE, TOKEN_SCALE, touch_user, wallet_info,
)
from ai import enhance_prompt, EXT_API, lint, MAX_RECORDS_SHARED, reserve_cost, sanitize, TEMPLATES, typical_cost, _task_hash
from engine import PROMO_CONF, PROMO_DEF_LOCK, PROMO_DEF_TEXT, sched_loop, sync_commands
from mother import (
    ann_new, audience_targets, card_public, do_activate, fj_parse, fj_str, gen_job, lint_fa, MAX_USERBOTS,
    new_bot_doc, recover_jobs, run_admin_send, run_multi_send, scan_key, scan_state, start_announce, start_block_scan,
    ub_boot, ub_limit, ub_ready,
)
import webapp                                    # مینی‌اپ‌ساز: مسیرهای سازنده و رانتایم /a و /rt
from webapp import app_export_doc, delete_app_data, lint_app
import blueprints                                # نقشه‌های آماده (ربات + مینی‌اپ)
import architect                                 # معمار: تشخیص، ساخت، خودآزمایی و پچ
import games                                     # مرکز بازی گروهی (B1): مسیرهای /rt game + موتور



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
    lim = limits_of(uid)
    return {"billing": BILLING, "gen": cut(uid, GEN_COST), "edit": cut(uid, EDIT_COST), "typical": cut(uid, typical_cost()), "min": cut(uid, TOKEN_MIN_COST),
            "ai_per": ai_per(uid) if uid is not None else AI_MSGS_PER_TOKEN, "ai_cost": AI_MSG_COST, "bc_per": BROADCAST_PER_TOKEN, "scale": TOKEN_SCALE,
            "enhance": 0 if pk["free_enhance"] else ENHANCE_COST,
            "max_bots": MAX_BOTS + pk["bots"], "max_nodes": lim["nodes"], "max_prompt": MAX_PROMPT, "daily": DAILY_BONUS + pk["daily"],
            "ref_inviter": REF_INVITER, "ref_invitee": REF_INVITEE, "ref_max": REF_MAX_PER_USER, "ref_on": REF_ON,
            "milestones": REF_MILESTONES, "media_max_mb": MEDIA_MAX_MB, "media_quota_mb": MEDIA_QUOTA_MB + pk["mb"],
            "max_media": MAX_MEDIA + pk["files"], "disc": pk["disc"], "plans": plans_public(),
            "emoji_max": pk["emoji"], "btn_fx": 1 if pk["btn"] else 0,
            "games": 1, "db": 1, "ext_api": 1 if EXT_API else 0,
            "build": BUILD, "limits": lim, "features": FEATURES_ON,
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
    elif request.path.startswith("/static/"):
        # URL هر فایل اثر انگشت محتوایش را دارد؛ کش یک‌ساله امن است و آپلود جدید خودکار می‌شکند
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


_INDEX_CACHE = ["", ""]


def _index_html():
    """index.html با اثر انگشت محتوای هر فایل استاتیک (?v=hash)؛ هر فایل قدیمی روی سرور خودش URL تازه می‌گیرد"""
    stamp = str(assets_stamp())
    if _INDEX_CACHE[0] != BUILD + stamp:
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"), encoding="utf-8") as f:
                html = f.read()
        except OSError:
            html = ""
        html = re.sub(r'(src|href)="(static/[^"]+)"',
                      lambda m: m.group(1) + '="' + m.group(2) + "?v=" + asset_v(m.group(2)) + '"', html)
        html = html.replace("__BUILD__", BUILD)   # نسخه‌ی نمایش داده‌شده در نوار خطا

        _INDEX_CACHE[:] = [BUILD + stamp, html]
    return _INDEX_CACHE[1]


@app.get("/")
def index():
    resp = Response(_index_html(), mimetype="text/html")
    resp.headers["Cache-Control"] = "no-cache"      # خود index.html هم کش تلگرام/مرورگر را نگه نمی‌دارد
    return resp


@app.get("/api/caps")
@authed
def api_caps(uid):
    """رجیستری قابلیت‌ها برای رابط کاربری (رویدادها، کارها، دکمه‌ها، بلوک‌ها، بازی‌ها) با برچسب فارسی"""
    return jsonify(caps_public())


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


# ───────────────────────── معمار هوشمند (نقشه‌های آماده) ─────────────────────────
@app.get("/api/blueprints")
@authed
def api_blueprints(uid):
    """کارت‌های صفحه‌ی «چی می‌خوای بسازی؟» — فقط نقشه‌هایی که واقعاً کار می‌کنند"""
    return jsonify(items=blueprints.blueprint_public())


@app.post("/api/arch/start")
@authed
def api_arch_start(uid):
    """تشخیص نقشه از توضیح کاربر؛ اگر نقشه‌ای نخورد، رابط به ساختِ هوشمندِ همیشگی برمی‌گردد"""
    idea = str((request.get_json(silent=True) or {}).get("idea") or "").strip()[:MAX_PROMPT]
    if len(idea) < 5:
        return jsonify(error="توضیح بیشتری بنویس"), 400
    bid, questions, title = architect.start(uid, idea)
    return jsonify(matched=bool(bid), bid=bid or "", title=title, questions=questions)


@app.post("/api/arch/build")
@authed
def api_arch_build(uid):
    """ساخت ربات + مینی‌اپ از نقشه با پاسخ‌های شخصی‌سازی (بدون مصرف توکن — نقشه تست‌شده است)"""
    b = request.get_json(silent=True) or {}
    bid, answers = str(b.get("bid") or ""), b.get("answers") if isinstance(b.get("answers"), dict) else {}
    extra = [str(x)[:8] for x in b.get("extra") if str(x)[:8] in blueprints.BLUEPRINTS][:2] if isinstance(b.get("extra"), list) else []
    if rate_ok(f"arch:{uid}", 10, 3600) is False:
        return jsonify(error="کمی آروم‌تر؛ چند دقیقه بعد دوباره"), 429
    if db.bots.count_documents({"owner": uid}) >= max_bots(uid):
        return jsonify(error=f"به سقف {MAX_BOTS + perks_of(uid)['bots']} ربات رسیدی؛ یکی را حذف کن یا اشتراکت را ارتقا بده", need_plan=True), 402
    try:
        cfg, app_cfg, cards, steps, title = architect.build(uid, bid, answers, extra=extra)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    bot = architect.save_new(uid, cfg, app_cfg, title, cards)
    botpub = public(db.bots.find_one({"_id": bot["_id"]}))
    return jsonify(bot=botpub, cards=cards, steps=steps, title=title, app=bool(app_cfg), wallet=wallet_info(uid))


@app.post("/api/bots/<bot_id>/archedit")
@authed
def api_arch_edit(uid, bot_id):
    """تغییر ربات با گفتگو — مرحله‌ی پیش‌نویس: کارت‌های تغییر فارسی + عملیات‌ها برمی‌گردند، هنوز ذخیره نمی‌شود"""
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    req = str((request.get_json(silent=True) or {}).get("request") or "").strip()[:1500]
    if len(req) < 4:
        return jsonify(error="تغییر موردنظر را بنویس"), 400
    if not hold(uid, cut(uid, EDIT_COST)):
        return jsonify(error="موجودی توکن برای این تغییر کافی نیست", need=EDIT_COST, wallet=wallet_info(uid)), 402
    try:
        ops, cards = architect.plan_edit(uid, bot, req)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    cost = charge_up_to(uid, cut(uid, EDIT_COST), "edit")
    return jsonify(ops=ops, cards=cards, cost=cost, wallet=wallet_info(uid))


@app.post("/api/bots/<bot_id>/archedit/apply")
@authed
def api_arch_apply(uid, bot_id):
    """اعمال فقط کارت‌های تاییدشده‌ی کاربر (هر کارت مستقل رد یا قبول می‌شود)"""
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    ops = (request.get_json(silent=True) or {}).get("ops")
    if not isinstance(ops, list) or not ops or len(ops) > 8 or not all(isinstance(o, dict) for o in ops):
        return jsonify(error="تغییری برای اعمال انتخاب نشده"), 400
    try:
        cfg, applied = architect.apply_selected(uid, bot, ops)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    bot2 = db.bots.find_one({"_id": bot["_id"]})
    return jsonify(bot=public(bot2), cards=applied, wallet=wallet_info(uid))


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
        if age_sec(j["t"]) < BOT_BUILD_TIMEOUT:
            return jsonify(error="یه کار دیگه‌ات هنوز در حال انجامه، چند لحظه صبر کن"), 409
    ensure_user(uid)
    reserve = reserve_cost(prompt, bot["config"] if bot else None, uid)
    if not hold(uid, reserve):
        msg = (f"توکن کافی نداری. این کار {reserve} توکن می‌خواد." if BILLING == "fixed"
               else f"توکن کافی نداری. برای این درخواست حداقل {reserve} توکن لازمه (هزینه‌ی واقعی معمولاً کمتره و فقط همون بعد از ساخت کم می‌شه).")
        return jsonify(error=msg, need=reserve, wallet=wallet_info(uid)), 402
    jid = secrets.token_hex(8)
    bot_id = str(bot["_id"]) if bot else None
    # Save the immutable request/bot identity with the job so a failed build can resume its durable task checkpoint.
    db.jobs.insert_one({"_id": jid, "uid": uid, "status": "running", "kind": "bot_build", "hold": 0,
                        "prompt": prompt, "bot_id": bot_id, "reserve": int(reserve), "t": now()})
    threading.Thread(target=gen_job, args=(jid, uid, bot_id, prompt, reserve), daemon=True).start()
    return jsonify(job=jid, hold=reserve, wallet=wallet_info(uid))


@app.get("/api/jobs/<jid>")
@authed
def api_job(uid, jid):
    j = db.jobs.find_one({"_id": jid, "uid": uid})
    if not j:
        return jsonify(error="کار پیدا نشد"), 404
    if j["status"] in ("running", "saving") and age_sec(j["t"]) > BOT_BUILD_TIMEOUT:
        db.jobs.find_one_and_update({"_id": jid, "status": {"$in": ["running", "saving"]}}, {"$set": {
                "status": "error", "error": "مهلت ساخت تمام شد؛ خروجی تأییدنشده ذخیره نشد و توکنی کسر نشد. گزارش خطای مرحله‌ای برای بررسی ثبت می‌شود."}})
        j = db.jobs.find_one({"_id": jid})
    out = {"status": "running" if j["status"] == "saving" else j["status"], "wallet": wallet_info(uid)}
    if j["status"] in ("running", "saving") and j.get("prog"):
        out["prog"] = {k: j["prog"].get(k) for k in ("p", "st", "n", "ti", "th", "att", "model_try", "model_total", "model_label", "task_i", "task_n", "task_title")}
    if j["status"] == "done":
        b = get_bot(j["bot"], uid)
        out.update(bot=public(b) if b else None, ideas=j.get("ideas", []), cost=j.get("cost", 0))
    elif j["status"] == "error":
        out["error"] = j.get("error", "ناموفق بود")
        state = j.get("build_state") or {}
        can_resume = bool(j.get("kind") == "bot_build" and j.get("prompt")
                          and state.get("version") == 1 and isinstance(state.get("plan"), list)
                          and isinstance(state.get("cfg"), dict)
                          and state.get("request_hash") == _task_hash(j.get("prompt")))
        out["can_resume"] = can_resume
        if can_resume:
            out["completed_tasks"] = len(state.get("completed") or [])
            out["total_tasks"] = len(state.get("plan") or [])
            out["build_phase"] = str(state.get("phase") or "")[:60]
    elif j["status"] == "review":
        out.update(gaps=j.get("gaps", []), cost=int(j.get("cost") or 0), prompt=j.get("prompt", ""), preflight=bool(j.get("preflight")))
    elif j["status"] == "cancelled":
        out["message"] = "درخواست لغو شد؛ توکنی کسر نشد."
    return jsonify(out)


@app.post("/api/jobs/<jid>/resume")
@authed
def api_job_resume(uid, jid):
    """Resume only unfinished tasks from the most recent durable checkpoint; no bot/token is committed on failure."""
    job = db.jobs.find_one({"_id": jid, "uid": uid, "status": "error", "kind": "bot_build"})
    if not job:
        return jsonify(error="کار ناموفق و قابل‌ادامه پیدا نشد؛ ممکن است قبلاً ادامه یافته باشد."), 409
    state = job.get("build_state") or {}
    prompt = str(job.get("prompt") or "")
    if (state.get("version") != 1 or not prompt or not isinstance(state.get("plan"), list)
            or not isinstance(state.get("cfg"), dict) or state.get("request_hash") != _task_hash(prompt)):
        return jsonify(error="checkpoint معتبر برای ادامه وجود ندارد. درخواست جدید بساز؛ برای این شکست هزینه‌ای کسر نشده است."), 409
    bot_id = job.get("bot_id")
    current = None
    if bot_id:
        bot = get_bot(bot_id, uid)
        if not bot:
            return jsonify(error="ربات اصلی برای ارتقا پیدا نشد؛ checkpoint روی نسخهٔ دیگری اعمال نمی‌شود."), 409
        current = bot.get("config")
        if state.get("base_hash") != _task_hash(current):
            return jsonify(error="نسخهٔ اصلی ربات از زمان این تلاش تغییر کرده؛ برای جلوگیری از بازنویسی تغییرات جدید، ارتقا باید از نو ثبت شود."), 409
    elif state.get("base_hash") != "new":
        return jsonify(error="checkpoint متعلق به ساخت/ارتقای دیگری است؛ ادامه متوقف شد."), 409
    reserve = max(0, int(job.get("reserve") or 0))
    if reserve <= 0:
        reserve = int(reserve_cost(prompt, current, uid))
    if not hold(uid, reserve):
        return jsonify(error=f"موجودی کافی نیست؛ برای تکمیل این کار تا سقف {reserve} توکن لازم است.", need=reserve, wallet=wallet_info(uid)), 402
    changed = db.jobs.find_one_and_update(
        {"_id": jid, "uid": uid, "status": "error"},
        {"$set": {"status": "running", "t": now(), "resume_count": int(job.get("resume_count") or 0) + 1}, "$unset": {"error": ""}},
    )
    if not changed:
        return jsonify(error="این کار هم‌زمان توسط درخواست دیگری ادامه داده شده است."), 409
    threading.Thread(target=gen_job, args=(jid, uid, bot_id, prompt, reserve), daemon=True).start()
    return jsonify(job=jid, resumed=True, wallet=wallet_info(uid))


@app.post("/api/jobs/<jid>/review")
@authed
def api_job_review(uid, jid):
    """اجازه‌ی ساخت نسخه‌ی محدودشده فقط پس از تأیید صریح کاربر؛ لغو بدون هزینه."""
    body = request.get_json(silent=True) or {}
    decision = str(body.get("decision") or "").lower()
    job = db.jobs.find_one({"_id": jid, "uid": uid, "status": "review"})
    if not job:
        return jsonify(error="این درخواست منقضی شده یا قبلاً بررسی شده است."), 409
    if decision == "no":
        changed = db.jobs.find_one_and_update({"_id": jid, "uid": uid, "status": "review"},
                                               {"$set": {"status": "cancelled", "cancelled_at": now()}})
        if not changed:
            return jsonify(error="وضعیت درخواست تغییر کرده است."), 409
        return jsonify(status="cancelled", wallet=wallet_info(uid))
    if decision != "yes":
        return jsonify(error="انتخاب نامعتبر است."), 400
    if job.get("preflight"):
        prompt = str(job.get("prompt") or "")
        reserve = max(0, int(reserve_cost(prompt, None, uid)))
        if not hold(uid, reserve):
            return jsonify(error=f"موجودی کافی نیست؛ برای ساخت تا سقف {reserve} توکن لازم است.", need=reserve, wallet=wallet_info(uid)), 402
        changed = db.jobs.find_one_and_update({"_id": jid, "uid": uid, "status": "review"},
                                              {"$set": {"status": "running", "preflight_ok": True, "t": now()}, "$unset": {"error": ""}})
        if not changed:
            return jsonify(error="این درخواست قبلاً پردازش شده است."), 409
        threading.Thread(target=gen_job, args=(jid, uid, job.get("bot_id"), prompt, reserve), daemon=True).start()
        return jsonify(status="running", job=jid, wallet=wallet_info(uid))
    if not isinstance(job.get("cfg"), dict) or not job["cfg"].get("nodes"):
        return jsonify(error="پیش‌نویس معتبر پیدا نشد؛ هیچ هزینه‌ای کسر نشد."), 409
    changed = db.jobs.find_one_and_update({"_id": jid, "uid": uid, "status": "review"},
                                           {"$set": {"status": "saving", "approved_at": now()}})
    if not changed:
        return jsonify(error="این درخواست قبلاً پردازش شده است."), 409
    cost = max(0, int(job.get("cost") or 0))
    charged = False
    try:
        if cost and not spend(uid, cost, "gen"):
            db.jobs.update_one({"_id": jid, "status": "saving"}, {"$set": {"status": "review"}, "$unset": {"approved_at": ""}})
            return jsonify(error=f"موجودی کافی نیست؛ برای این نسخه {cost} توکن لازم است. هیچ رباتی ساخته نشد.", need=cost, wallet=wallet_info(uid)), 402
        charged = cost > 0
        bot = new_bot_doc(uid, job["cfg"], job.get("thinking") or "")
        db.jobs.update_one({"_id": jid, "status": "saving"}, {"$set": {"status": "done", "bot": str(bot["_id"]), "cost": cost, "approved_at": now()}})
        if REF_ON == "create":
            settle_referral(uid)
        fresh = get_bot(str(bot["_id"]), uid)
        return jsonify(status="done", bot=public(fresh) if fresh else None, ideas=job.get("ideas", []), cost=cost, wallet=wallet_info(uid))
    except Exception:
        log.exception("approved partial build failed in mini app")
        if charged:
            refund(uid, cost, "gen_rollback")
        db.jobs.update_one({"_id": jid, "status": "saving"}, {"$set": {"status": "review", "error": "ذخیره‌سازی ناموفق بود"}, "$unset": {"approved_at": ""}})
        return jsonify(error="ذخیره‌سازی ناموفق بود؛ هزینه برگشت داده شد و رباتی تحویل نشد."), 500


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
        cfg = sanitize((request.get_json(silent=True) or {}).get("config"), strict=True, media=own_media_ids(uid),
                       nodes_cap=limits_of(uid)["nodes"])
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
    d = app_export_doc(bot_id)
    return jsonify(format="botmaker/2", config=bot["config"], app=d if d.get("draft") or d.get("pub") else None)


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
    try:      # مشکلات منطقی مینی‌اپ هم همین‌جا گزارش می‌شود
        d = db.apps.find_one({"_id": bot_id}) or {}
        if d.get("draft"):
            issues += [f"مینی‌اپ: {x}" for x in lint_app(d["draft"], bot["config"])]
    except Exception:
        pass
    return jsonify(issues=issues, nodes=len(bot["config"]["nodes"]))


# ───────────────────────── وب‌هوک ورودی هر ربات (امضاشده) ─────────────────────────
def _webin_key(bot_id):
    import hashlib as _h
    return _h.sha256((SECRET_KEY + "webin" + bot_id).encode()).hexdigest()[:24]


@app.get("/api/bots/<bot_id>/webin")
@authed
def api_webin(uid, bot_id):
    """آدرس وب‌هوک ورودی برای صاحب ربات"""
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    on = bool(bot["config"].get("webin"))
    return jsonify(on=on, url=f"{BASE_URL}/hook-in/{bot_id}?k={_webin_key(str(bot['_id']))}")


@app.post("/hook-in/<bot_id>")
def hook_in(bot_id):
    """وب‌هوک ورودی امضاشده: هر رخداد بیرونی یک رکورد در جدول ربات می‌شود (+ خبر اختیاری)"""
    bot = None
    try:
        bot = db.bots.find_one({"_id": ObjectId(bot_id)})
    except (InvalidId, TypeError):
        return jsonify(error="not found"), 404
    if not bot or not bot.get("active") or not bot.get("token_enc"):
        return jsonify(error="not found"), 404
    cfg = bot.get("config") or {}
    wb = cfg.get("webin") or {}
    if not wb.get("on"):
        return jsonify(error="disabled"), 404
    if request.args.get("k") != _webin_key(str(bot["_id"])):
        return jsonify(error="forbidden"), 403
    if not rate_ok(f"wb:{bot_id}", 120, 60):
        return jsonify(error="slow down"), 429
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {"event": request.get_data(as_text=True)[:300]}
    data = {str(k)[:20]: str(v)[:200] for k, v in list(body.items())[:20]}
    data.setdefault("event", "hook")
    tab = wb["table"]
    mx = db.recs.find_one({"bot": str(bot["_id"]), "t": tab}, sort=[("n", -1)], projection={"n": 1})
    n = int((mx or {}).get("n", 0)) + 1
    if db.recs.count_documents({"bot": str(bot["_id"]), "t": tab}) < MAX_RECORDS_SHARED:
        db.recs.insert_one({"bot": str(bot["_id"]), "t": tab, "u": bot["owner"], "n": n, "d": data, "ct": now()})
    if wb.get("notify"):
        tg(dec(bot["token_enc"]), "sendMessage", chat_id=bot["owner"],
           text=f"🔗 وب‌هوک رسید: {json.dumps(data, ensure_ascii=False)[:800]}")
    return jsonify(ok=True)


# ───────────────────────── حالت‌های هوش مصنوعی: توضیح بده / بهتر کن / ترجمه کن ─────────────────────────
_EXPLAIN_PROMPT = ("You are reviewing a Telegram bot config (JSON). Explain to its NON-TECHNICAL owner, in Persian, what this bot does "
                   "and how a user flows through it: sections, buttons, forms, rewards, groups. Max 12 short lines, plain Persian, no JSON, no technical terms.")
_IMPROVE_PROMPT = ("You are a UX auditor for a Telegram bot config (JSON). In Persian, list concrete problems only from these categories: "
                   "dead ends (no way back), missing fallback answers, overly long texts, too many buttons in one section, unclear button labels, "
                   "missing confirmation after forms. For each: one line: [مشکل] بخش «نام»: توضیح کوتاه + پیشنهاد. Max 8 lines. If nothing serious, say «ساختار سالم است».")
_TRANSLATE_PROMPT = ("Translate EVERY user-facing text in this Telegram bot config JSON (node texts, titles, button labels, alerts, form questions, "
                     "done texts, alt texts, group trigger replies, reminder values) from Persian to fluent English, or from English to fluent Persian "
                     "(detect direction automatically; keep {variables} and <b>/<i>/<code>/<blockquote> HTML tags exactly as-is; keep ids and structure unchanged). "
                     "Return ONLY the full updated JSON object in the same shape.")


@app.post("/api/bots/<bot_id>/ai/mode")
@authed
def api_ai_mode(uid, bot_id):
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    b = request.get_json(silent=True) or {}
    mode = str(b.get("mode") or "")
    if mode not in ("explain", "improve", "translate"):
        return jsonify(error="حالت معتبر نیست"), 400
    if not rate_ok(f"aim:{uid}", 10, 600):
        return jsonify(error="کمی آروم‌تر؛ چند دقیقه بعد دوباره"), 429
    cfg_json = json.dumps(bot["config"], ensure_ascii=False)
    if len(cfg_json) > 14000:
        return jsonify(error="این ربات خیلی بزرگ است؛ برای این کار اول چند بخش را حذف کن"), 400
    if not hold(uid, cut(uid, TOKEN_MIN_COST)):
        return jsonify(error="موجودی توکن کافی نیست", need=TOKEN_MIN_COST, wallet=wallet_info(uid)), 402
    from ai import llm_post, AI_CHAT_MODEL, has_foreign, scrub_foreign
    prompts = {"explain": _EXPLAIN_PROMPT, "improve": _IMPROVE_PROMPT, "translate": _TRANSLATE_PROMPT}
    try:
        txt, (pt, ct) = llm_post([{"role": "system", "content": prompts[mode]},
                                  {"role": "user", "content": cfg_json}], 2000, temperature=0.3, timeout=120, model=AI_CHAT_MODEL)
    except Exception:
        return jsonify(error="اتصال به هوش مصنوعی برقرار نشد؛ کمی بعد دوباره امتحان کن"), 502
    cost = charge_up_to(uid, cut(uid, calc_cost(pt, ct, minimum=TOKEN_MIN_COST, uid=uid)), "edit", daily_key=True)
    if has_foreign(txt):
        txt = scrub_foreign(txt)
    txt = txt.strip()
    if mode == "translate":
        m = re.search(r"\{.*\}", txt, re.S)
        if not m:
            return jsonify(error="ترجمه‌ی قابل استفاده‌ای برنگشت؛ دوباره امتحان کن"), 502
        try:
            from ai import sanitize
            newcfg = sanitize(json.loads(m.group(0)), strict=False, nodes_cap=limits_of(uid)["nodes"])
        except (ValueError, TypeError, KeyError):
            return jsonify(error="ترجمه اعتبارسنجی نشد؛ دوباره امتحان کن"), 502
        db.bots.update_one({"_id": bot["_id"]}, {"$set": {"config": newcfg, "name": newcfg["name"], "thinking": "", "updated": now()},
                                                 "$push": {"versions": {"$each": [bot["config"]], "$slice": -(MAX_VERSIONS + perks_of(uid)["ver"])}}})
        try:
            sync_commands(db.bots.find_one({"_id": bot["_id"]}), newcfg)
        except Exception:
            pass
        return jsonify(mode=mode, applied=True, cost=cost, wallet=wallet_info(uid),
                       bot=public(db.bots.find_one({"_id": bot["_id"]})))
    return jsonify(mode=mode, text=txt[:2500], cost=cost, wallet=wallet_info(uid))


# ───────────────────────── نسخه‌ها، لیست‌ها و دکتر ربات ─────────────────────────
def cfg_diff_fa(old, new):
    """تفاوت دو کانفیگ به‌صورت جمله‌های فارسی خوانا (بدون JSON)"""
    lines = []
    on, nn = (old or {}).get("nodes") or {}, (new or {}).get("nodes") or {}

    def title(cfg, nid):
        n = cfg.get(nid) or {}
        return n.get("title") or (n.get("text") or "").replace("\n", " ").strip()[:20] or nid
    for nid in nn:
        if nid not in on:
            lines.append("اضافه شد: بخش «%s»" % title(nn, nid))
    for nid in on:
        if nid not in nn:
            lines.append("حذف شد: بخش «%s»" % title(on, nid))
    for nid in nn:
        if nid not in on:
            continue
        a, b = on[nid], nn[nid]
        t = title(nn, nid)
        if (a.get("text") or "") != (b.get("text") or ""):
            lines.append("متن بخش «%s» عوض شد" % t)
        ba = sum(len(r) for r in a.get("buttons") or [])
        bb = sum(len(r) for r in b.get("buttons") or [])
        if ba != bb:
            lines.append("دکمه‌های «%s» عوض شد (%s ← %s دکمه)" % (t, ba, bb))
        elif a.get("buttons") != b.get("buttons"):
            lines.append("مقصد یا کارِ دکمه‌های «%s» عوض شد" % t)
        if (a.get("ai") or {}).get("prompt") != (b.get("ai") or {}).get("prompt") and b.get("ai"):
            lines.append("دستور دستیارِ «%s» عوض شد" % t)
        if (a.get("fields") or []) != (b.get("fields") or []):
            lines.append("سؤال‌های فرمِ «%s» عوض شد" % t)
        if (a.get("do") or []) != (b.get("do") or []):
            lines.append("کارهای خودکارِ «%s» عوض شد" % t)
    oa, na = (old or {}).get("commands") or {}, (new or {}).get("commands") or {}
    for c in na:
        if oa.get(c) != na[c]:
            lines.append("دستور /%s %s" % (c, "ساخته شد" if c not in oa else "عوض شد"))
    for c in oa:
        if c not in na:
            lines.append("دستور /%s حذف شد" % c)
    if (old or {}).get("group") != (new or {}).get("group"):
        lines.append("قانون‌های گروه عوض شد")
    if (old or {}).get("mod") != (new or {}).get("mod"):
        lines.append("تنظیمات مدیریت گروه/کانال عوض شد")
    return lines[:14]


@app.get("/api/bots/<bot_id>/versions")
@authed
def api_versions_diff(uid, bot_id):
    """فهرست نسخه‌های برگشتی ربات با تفاوت قابل‌فهم هر کدام"""
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    vs = bot.get("versions") or []
    items = [{"i": i + 1, "lines": cfg_diff_fa(v, bot["config"] if i == len(vs) - 1 else vs[i + 1])}
             for i, v in enumerate(vs)]
    return jsonify(items=items)


def _tables_of(bot):
    cfg = bot["config"]
    names = set((cfg.get("dbfields") or {}).keys())
    for n in cfg.get("nodes", {}).values():
        for a in n.get("do") or []:
            if str(a.get("op", "")).startswith("db_") and a.get("table"):
                names.add(a["table"])
        ls = n.get("list")
        if isinstance(ls, dict) and ls.get("table"):
            names.add(ls["table"])
    for m in db.tmeta.find({"bot": str(bot["_id"])}):
        names.add(m["t"])
    return sorted(names)


def _table_fields(bot, t):
    m = db.tmeta.find_one({"_id": "%s:%s" % (bot["_id"], t)})
    if m and m.get("fields"):
        return [str(x)[:30] for x in m["fields"]][:12]
    return [str(x) for x in (bot["config"].get("dbfields") or {}).get(t, [])][:12]


@app.get("/api/bots/<bot_id>/tables")
@authed
def api_tables(uid, bot_id):
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    items = [{"t": t, "fields": _table_fields(bot, t),
              "rows": min(db.recs.count_documents({"bot": str(bot["_id"]), "t": t}), 500)} for t in _tables_of(bot)]
    return jsonify(items=items)


@app.get("/api/bots/<bot_id>/tables/<t>")
@authed
def api_table_rows(uid, bot_id, t):
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    t = re.sub(r"[^a-z0-9_]", "", (t or "").lower())[:20]
    if not t:
        return jsonify(error="نام جدول معتبر نیست"), 400
    fields = _table_fields(bot, t) or ["ستون ۱"]
    rows = []
    for r in db.recs.find({"bot": str(bot["_id"]), "t": t}).sort("n", 1).limit(300):
        d = r.get("d") or {}
        rows.append([str(d.get(f, ""))[:200] for f in fields])
    return jsonify(t=t, fields=fields, rows=rows)


@app.post("/api/bots/<bot_id>/tables/<t>")
@authed
def api_table_save(uid, bot_id, t):
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    t = re.sub(r"[^a-z0-9_]", "", (t or "").lower())[:20]
    if not t:
        return jsonify(error="نام جدول معتبر نیست"), 400
    body = request.get_json(silent=True) or {}
    fields = [str(x).strip()[:30] for x in (body.get("fields") or []) if str(x).strip()][:12]
    if not fields:
        return jsonify(error="حداقل یک ستون لازم است"), 400
    raw_rows = body.get("rows") if isinstance(body.get("rows"), list) else []
    if len(raw_rows) > MAX_RECORDS_SHARED:
        return jsonify(error="حداکثر %s ردیف در هر جدول" % MAX_RECORDS_SHARED), 400
    rows = []
    for r in raw_rows[:MAX_RECORDS_SHARED]:
        if not isinstance(r, list):
            continue
        row = [str(x)[:200] for x in r[:len(fields)]]
        row += [""] * (len(fields) - len(row))
        rows.append(row)
    key = str(bot["_id"])
    db.recs.delete_many({"bot": key, "t": t})
    if rows:
        db.recs.insert_many([{"bot": key, "t": t, "u": uid, "n": i + 1,
                              "d": {fields[j]: rows[i][j] for j in range(len(fields)) if rows[i][j]},
                              "ct": now()} for i in range(len(rows))])
    db.tmeta.update_one({"_id": "%s:%s" % (key, t)}, {"$set": {"bot": key, "t": t, "fields": fields}}, upsert=True)
    return jsonify(ok=True, rows=len(rows))



# ───────────────────────── دانش عامل هوشمند ─────────────────────────
@app.get("/api/bots/<bot_id>/kb")
@authed
def api_kb(uid, bot_id):
    if not get_bot(bot_id, uid):
        return jsonify(error="ربات پیدا نشد"), 404
    items = [{"id": str(d["_id"]), "t": d.get("t") or "دانش", "x": d.get("x") or ""}
             for d in db.kbdoc.find({"bot": bot_id}).sort("n", 1).limit(200)]
    return jsonify(items=items)


@app.post("/api/bots/<bot_id>/kb")
@authed
def api_kb_add(uid, bot_id):
    if not get_bot(bot_id, uid):
        return jsonify(error="ربات پیدا نشد"), 404
    if db.kbdoc.count_documents({"bot": bot_id}) >= 200:
        return jsonify(error="حداکثر ۲۰۰ قطعه دانش"), 400
    b = request.get_json(silent=True) or {}
    title = str(b.get("title") or "دانش").strip()[:60]
    text = str(b.get("text") or "").strip()
    if len(text) < 4:
        return jsonify(error="متن دانش را بنویس"), 400
    n = db.kbdoc.find_one({"bot": bot_id}, sort=[("n", -1)]) or {}
    chunks, cur = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            if cur:
                chunks.append(" ".join(cur)); cur = []
        else:
            cur.append(line)
    if cur:
        chunks.append(" ".join(cur))
    chunks = [c[:600] for c in chunks if len(c) >= 3][:20]
    if not chunks:
        return jsonify(error="متن معتبر نیست"), 400
    base = int(n.get("n", 0))
    db.kbdoc.insert_many([{"bot": bot_id, "t": title, "x": c, "n": base + i + 1} for i, c in enumerate(chunks)])
    return jsonify(ok=True, added=len(chunks))


@app.delete("/api/bots/<bot_id>/kb/<kid>")
@authed
def api_kb_del(uid, bot_id, kid):
    if not get_bot(bot_id, uid):
        return jsonify(error="ربات پیدا نشد"), 404
    try:
        r = db.kbdoc.delete_one({"_id": ObjectId(kid), "bot": bot_id})
    except (InvalidId, TypeError):
        return jsonify(error="پیدا نشد"), 404
    return jsonify(ok=bool(r.deleted_count))


# ───────────────────────── قطعه‌های آماده‌ی مینی‌اپ (sync بین دستگاه‌ها) ─────────────────────────
_COMP_MAX = 12


@app.get("/api/comps")
@authed
def api_comps(uid):
    items = [{"id": str(d["_id"]), "name": d.get("name") or "قطعه", "b": d.get("b") or {}}
             for d in db.comps.find({"owner": uid}).sort("t", 1).limit(_COMP_MAX)]
    return jsonify(items=items)


@app.post("/api/comps")
@authed
def api_comps_add(uid):
    if not rate_ok(f"comps:{uid}", 20, 60):
        return jsonify(error="کمی آروم‌تر؛ چند لحظه بعد دوباره"), 429
    if db.comps.count_documents({"owner": uid}) >= _COMP_MAX:
        return jsonify(error=f"حداکثر {_COMP_MAX} قطعه می‌توانی ذخیره کنی؛ یکی را پاک کن"), 400
    b = request.get_json(silent=True) or {}
    blk = b.get("b")
    if not isinstance(blk, dict) or not isinstance(blk.get("t"), str):
        return jsonify(error="بلوک معتبر نیست"), 400
    if len(json.dumps(blk)) > 4000:
        return jsonify(error="این بلوک برای ذخیره خیلی بزرگ است"), 400
    name = str(b.get("name") or "قطعه").strip()[:40]
    db.comps.insert_one({"owner": uid, "name": name, "b": blk, "t": now()})
    return jsonify(ok=True)


@app.delete("/api/comps/<cid>")
@authed
def api_comps_del(uid, cid):
    try:
        r = db.comps.delete_one({"_id": ObjectId(cid), "owner": uid})
    except (InvalidId, TypeError):
        return jsonify(error="پیدا نشد"), 404
    return jsonify(ok=bool(r.deleted_count))


# ───────────────────────── کدهای تخفیف (اکشن disc) ─────────────────────────
_DCODE_MAX = 100


@app.get("/api/bots/<bot_id>/dcodes")
@authed
def api_dcodes(uid, bot_id):
    if not get_bot(bot_id, uid):
        return jsonify(error="ربات پیدا نشد"), 404
    nowts = time.time()
    items = [{"code": d["code"], "kind": d.get("kind") or "pct", "value": d.get("value", 0),
              "max": int(d.get("max") or 0), "used": int(d.get("used", 0)),
              "exp": d.get("exp"), "dead": bool(d.get("exp") and float(d["exp"]) < nowts)}
             for d in db.dcodes.find({"bot": bot_id}).sort("_id", 1).limit(_DCODE_MAX)]
    return jsonify(items=items)


@app.post("/api/bots/<bot_id>/dcodes")
@authed
def api_dcodes_add(uid, bot_id):
    if not rate_ok(f"dcodes:{uid}", 20, 60):
        return jsonify(error="کمی آروم‌تر؛ چند لحظه بعد دوباره"), 429
    if not get_bot(bot_id, uid):
        return jsonify(error="ربات پیدا نشد"), 404
    if db.dcodes.count_documents({"bot": bot_id}) >= _DCODE_MAX:
        return jsonify(error=f"حداکثر {_DCODE_MAX} کد تخفیف"), 400
    b = request.get_json(silent=True) or {}
    code = re.sub(r"[^A-Za-z0-9_-]", "", str(b.get("code") or "")).upper()[:24]
    if len(code) < 3:
        return jsonify(error="کد باید حداقل ۳ حرف انگلیسی/عدد باشد"), 400
    kind = "amt" if str(b.get("kind") or "pct") == "amt" else "pct"
    try:
        value = float(str(b.get("value", 0)).replace("٫", "."))
    except (TypeError, ValueError):
        return jsonify(error="مقدار تخفیف عدد نیست"), 400
    if kind == "pct" and not 0 < value <= 100:
        return jsonify(error="درصد تخفیف بین ۱ تا ۱۰۰"), 400
    if kind == "amt" and not 0 < value <= 10 ** 9:
        return jsonify(error="مبلغ تخفیف معتبر نیست"), 400
    try:
        mx = max(0, int(str(b.get("max", 0)) or 0))
    except (TypeError, ValueError):
        mx = 0
    try:
        days = max(0, int(str(b.get("days", 0)) or 0))
    except (TypeError, ValueError):
        days = 0
    doc = {"_id": f"{bot_id}:{code}", "bot": bot_id, "code": code, "kind": kind,
           "value": value, "max": mx, "used": 0, "exp": (time.time() + days * 86400) if days else None}
    try:
        db.dcodes.insert_one(doc)
    except DuplicateKeyError:
        return jsonify(error="این کد قبلاً ساخته شده"), 400
    return jsonify(ok=True)


@app.delete("/api/bots/<bot_id>/dcodes/<code>")
@authed
def api_dcodes_del(uid, bot_id, code):
    if not get_bot(bot_id, uid):
        return jsonify(error="ربات پیدا نشد"), 404
    code = re.sub(r"[^A-Za-z0-9_-]", "", code).upper()[:24]
    r = db.dcodes.delete_one({"_id": f"{bot_id}:{code}", "bot": bot_id})
    return jsonify(ok=bool(r.deleted_count))


@app.post("/api/bots/<bot_id>/agent/test")
@authed
def api_agent_test(uid, bot_id):
    """تست زنده‌ی عامل: با دانش ربات جواب می‌دهد و می‌گوید از کدام دانش استفاده کرد"""
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    b = request.get_json(silent=True) or {}
    text = str(b.get("text") or "").strip()[:1000]
    nid = str(b.get("node") or "")
    node = bot["config"]["nodes"].get(nid) or {}
    ai = node.get("ai")
    if not text:
        return jsonify(error="سؤال را بنویس"), 400
    if not ai:
        return jsonify(error="این بخش گفتگوی هوشمند ندارد؛ اول در ویرایش بخش، حالت «گفتگو با هوش مصنوعی» را فعال کن"), 400
    if not rate_ok(f"agt:{uid}", 12, 300):
        return jsonify(error="کمی آروم‌تر؛ چند دقیقه بعد دوباره"), 429
    if not hold(uid, cut(uid, TOKEN_MIN_COST)):
        return jsonify(error="موجودی توکن برای تست کافی نیست", need=TOKEN_MIN_COST, wallet=wallet_info(uid)), 402
    from engine import kb_search, AI_CHILD_PROMPT, agent_tools_block, agent_tool_round
    from ai import has_foreign, scrub_foreign, llm_post, AI_CHAT_MODEL
    know = kb_search(bot_id, text, 3)
    system = AI_CHILD_PROMPT.replace("{bot}", bot["config"].get("name", "")) + ai.get("prompt", "")
    if know:
        system += "\n\nدانش کسب‌وکار (فقط بر اساس این جواب بده و از دانش بیرون چیز نساز):\n" + \
            "\n".join(f"- {t}: {x}" for t, x in know)
    tb, tools = agent_tools_block(node, bot["config"])
    if tb:
        system += "\n\n" + tb
    try:
        reply, (pt, ct) = llm_post([{"role": "system", "content": system}, {"role": "user", "content": text}],
                                   500, temperature=0.5, timeout=60, model=AI_CHAT_MODEL)
        reply, pt, ct = agent_tool_round(bot_id, system, [], text, reply, pt, ct, tools, 500)
    except Exception:
        return jsonify(error="اتصال به هوش مصنوعی برقرار نشد؛ کمی بعد دوباره امتحان کن"), 502
    cost = charge_up_to(uid, cut(uid, calc_cost(pt, ct, minimum=TOKEN_MIN_COST, uid=uid)), "ai_chat", daily_key=True)
    if has_foreign(reply):
        reply = scrub_foreign(reply)
    return jsonify(reply=(reply or "").strip()[:1200] or "جوابی نیامد؛ دوباره بپرس.",
                   used=[{"t": t, "x": x[:120]} for t, x in know], cost=cost, wallet=wallet_info(uid))


@app.get("/api/bots/<bot_id>/doctor")
@authed
def api_doctor(uid, bot_id):
    """دکتر ربات: توکن، وب‌هوک، دسترسی در کانال‌ها و مینی‌اپ را چک می‌کند و راه‌حل ساده می‌دهد"""
    bot = get_bot(bot_id, uid)
    if not bot:
        return jsonify(error="ربات پیدا نشد"), 404
    cfg = bot["config"]
    items = []

    def add(ok, fa, fix=""):
        items.append({"ok": bool(ok), "warn": bool(not ok and not fix), "fa": fa, "fix": fix})

    if not bot.get("active") or not bot.get("token_enc"):
        add(False, "ربات هنوز فعال نشده است.",
            "توکن ربات را از @BotFather بگیر و در تب «انتشار» همین ربات بگذار.")
    else:
        tok = dec(bot["token_enc"])
        me = tg(tok, "getMe")
        if not me.get("ok"):
            add(False, "توکن ربات دیگر معتبر نیست (مثلاً بازسازی شده).",
                "در @BotFather با /revoke توکن تازه بگیر و در تب «انتشار» بگذار.")
        else:
            r = me.get("result") or {}
            bid = r.get("id")
            add(True, "ربات @%s وصل است و پیام می‌فرستد." % r.get("username"))
            wh = tg(tok, "getWebhookInfo")
            res = (wh.get("result") or {}) if wh.get("ok") else {}
            if not res.get("url"):
                add(False, "پیام‌های کاربرها به سرور نمی‌رسند (اتصال قطع است).",
                    "یک بار ربات را در تب «انتشار» خاموش و دوباره روشن کن تا وصل شود.")
            elif res.get("last_error_message"):
                add(False, "آخرین تلاش برای رسیدن پیام خطا داشت: %s" % str(res.get("last_error_message"))[:80],
                    "چند دقیقه صبر کن؛ خودش دوباره تلاش می‌کند. اگر تکرار شد، ربات را خاموش و روشن کن.")
            else:
                add(True, "پیام‌های کاربرها بی‌وقفه به ربات می‌رسند.")
            cmds = cfg.get("commands") or {}
            if cmds:
                mc = tg(tok, "getMyCommands")
                have = {c["command"] for c in ((mc.get("result") or {}).get("commands") or [])} if mc.get("ok") else set()
                miss = [c for c in cmds if c not in have]
                if miss:
                    add(False, "دستور /%s در منوی ربات ثبت نشده." % " و /".join(miss),
                        "یک بار ربات را خاموش و روشن کن؛ خودکار ثبت می‌شود.")
                else:
                    add(True, "هر %s دستور در منوی ربات ثبت است." % len(cmds))
            for ch in (cfg.get("join") or {}).get("channels") or []:
                r2 = tg(tok, "getChatMember", chat_id=ch, user_id=bid) if bid else {"ok": False}
                stt = (r2.get("result") or {}).get("status") if r2.get("ok") else None
                if stt in ("administrator", "member", "creator"):
                    add(True, "ربات در کانال %s عضو است و عضویت کاربرها را می‌سنجد." % ch)
                else:
                    add(False, "ربات نمی‌تواند عضویت کانال %s را بسنجد." % ch,
                        "ربات را ادمین کانال %s کن تا قفل عضویت کار بکند." % ch)
    if (cfg.get("growth") or {}).get("on"):
        g = cfg["growth"]
        me_ok = items and items[0]["ok"]
        if me_ok:
            bid2 = (tg(dec(bot["token_enc"]), "getMe").get("result") or {}).get("id")
            r3 = tg(dec(bot["token_enc"]), "getChatMember", chat_id=g["chat"], user_id=bid2) if bid2 else {"ok": False}
            st3 = (r3.get("result") or {}).get("status") if r3.get("ok") else None
            if st3 == "administrator":
                add(True, "ربات ادمین گروه/کانال رشد است و لینک دعوت می‌سازد.")
            else:
                add(False, "ربات نمی‌تواند لینک دعوت بسازد.",
                    f"ربات را با اجازه‌ی «دعوت کاربران» ادمین {g['chat']} کن تا لینک‌های دعوت کار بکند.")
        else:
            add(False, "ربات روشن نیست؛ قابلیت رشد هم کار نمی‌کند.", "اول ربات را فعال کن.")
    d = db.apps.find_one({"_id": str(bot["_id"])}) or {}
    pub = bool(d.get("pub"))
    has_btn = any(b.get("app") is not None for n in cfg.get("nodes", {}).values() for row in n.get("buttons") or [] for b in row)
    if has_btn and pub:
        add(True, "دکمه‌ی مینی‌اپ در ربات هست و مینی‌اپ منتشر شده.")
    elif has_btn and not pub:
        add(False, "دکمه‌ی مینی‌اپ هست ولی مینی‌اپ منتشر نشده.",
            "به تب «مینی‌اپ» برو و انتشار را بزن.")
    elif pub:
        add(True, "مینی‌اپ منتشر شده؛ برای باز شدن راحت، دکمه‌ی «باز کردن مینی‌اپ» را در تب مینی‌اپ به ربات اضافه کن.")
    else:
        add(True, "این ربات مینی‌اپ ندارد (لازم ندارد).")
    return jsonify(items=items)


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
    delete_app_data(bot_id)     # سند مینی‌اپ و رویدادهایش هم پاک می‌شوند
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
    q = str(request.args.get("q", "")).strip().lstrip("@")[:40]
    flt = {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        flt = {"$or": [{"tg_user": rx}, {"tg_name": rx}] + ([{"_id": int(q)}] if q.isdigit() else [])}
    users = list(db.users.find(flt, {"seen": 1, "tg_user": 1, "tg_name": 1, "created": 1, "tokens": 1, "mb_blocked": 1}).sort("seen", -1).limit(300))
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
    if not _abc_lock(bot_id):
        return jsonify(error="یه ارسال دیگه برای این ربات هنوز در حاله"), 409
    rec = ann_new("bot", uid, text, len(chats), "@" + (bot.get("username") or bot.get("name", "")), mid)
    threading.Thread(target=run_admin_send, args=(bot, chats, text, uid, mid, fmt, rec), daemon=True).start()
    return jsonify(queued=len(chats))


@app.get("/api/admin/audience")
@admin_only
def api_admin_audience(uid):
    return jsonify(builders=db.users.count_documents({}), bots=db.bots.count_documents({"active": True}),
                   audience=sum(len(c) for _, _, c in audience_targets()))


def _abc_lock(bot_id):
    """قفل ارسال اطلاعیه برای یک ربات؛ True یعنی گرفته شد"""
    try:
        db.locks.insert_one({"_id": f"abc:{bot_id}", "t": now()})
        return True
    except DuplicateKeyError:
        lk = db.locks.find_one({"_id": f"abc:{bot_id}"})
        if lk and age_sec(lk["t"]) < 1800:
            return False
        db.locks.update_one({"_id": f"abc:{bot_id}"}, {"$set": {"t": now()}})
        return True


# ───────────────────────── آمار ربات‌ها: رتبه‌بندی، فعال‌ترین‌ها و نمای کلی (پنل ادمین) ─────────────────────────
_BR = {"t": 0.0, "rows": []}


def _bot_rows(fresh=False):
    """همه‌ی ربات‌ها + آمار مخاطب (کش ۲۰ ثانیه‌ای تا با هزار ربات هم سرور درگیر نشه)"""
    if not fresh and time.time() - _BR["t"] < 20:
        return _BR["rows"]
    cut_on, d1 = naive() - timedelta(seconds=300), naive() - timedelta(days=1)

    def cnt(cond):
        return {"$sum": {"$cond": [cond, 1, 0]}}
    st = {r["_id"]: r for r in db.subs.aggregate([{"$group": {
        "_id": "$bot", "total": {"$sum": 1}, "blocked": cnt({"$eq": ["$blocked", True]}),
        "online": cnt({"$and": [{"$gte": ["$last", cut_on]}, {"$ne": ["$blocked", True]}]}),
        "act24": cnt({"$and": [{"$gte": ["$last", d1]}, {"$ne": ["$blocked", True]}]}),
        "new24": cnt({"$gte": ["$t", d1]}), "last": {"$max": "$last"}}}], allowDiskUse=True)}
    bots = list(db.bots.find({}, {"name": 1, "username": 1, "owner": 1, "active": 1, "token_enc": 1, "created": 1}))
    owners = {u["_id"]: u for u in db.users.find({"_id": {"$in": list({b.get("owner") for b in bots})}}, {"tg_user": 1, "tg_name": 1})}
    rows = []
    for bt in bots:
        bid, s, o = str(bt["_id"]), st.get(str(bt["_id"]), {}), owners.get(bt.get("owner"), {})
        rows.append({"id": bid, "name": bt.get("name", ""), "un": bt.get("username") or "", "on": bool(bt.get("active") and bt.get("token_enc")),
                     "owner": {"id": bt.get("owner"), "un": o.get("tg_user", ""), "name": o.get("tg_name", "")},
                     "total": int(s.get("total", 0)), "blocked": int(s.get("blocked", 0)), "online": int(s.get("online", 0)),
                     "act24": int(s.get("act24", 0)), "new24": int(s.get("new24", 0)),
                     "last": naive(s["last"]).isoformat() + "Z" if s.get("last") else "",
                     "created": naive(bt["created"]).isoformat() + "Z" if bt.get("created") else ""})
    _BR["t"], _BR["rows"] = time.time(), rows
    return rows


_BSORT = {"subs": lambda r: (r["total"] - r["blocked"], r["act24"]), "act24": lambda r: (r["act24"], r["online"], r["total"]),
          "online": lambda r: (r["online"], r["act24"], r["total"]), "new24": lambda r: (r["new24"], r["total"]),
          "recent": lambda r: r["created"]}


@app.get("/api/admin/bots")
@admin_only
def api_admin_bots(uid):
    rows = _bot_rows(bool(request.args.get("fresh")))
    summary = {"bots": len(rows), "active": sum(1 for r in rows if r["on"]), "subs": sum(r["total"] for r in rows),
               "online": sum(r["online"] for r in rows)}
    q = str(request.args.get("q", "")).strip().lower().lstrip("@")[:40]
    status = request.args.get("st", "all")
    if status in ("on", "off"):
        rows = [r for r in rows if r["on"] == (status == "on")]
    if q:
        rows = [r for r in rows if q in r["name"].lower() or q in r["un"].lower() or q == str(r["owner"]["id"])
                or q in (r["owner"]["un"] or "").lower() or q in (r["owner"]["name"] or "").lower()]
    rows = sorted(rows, key=_BSORT.get(request.args.get("sort"), _BSORT["subs"]), reverse=True)
    lim = _clamp(request.args.get("limit"), 10, 100, 40)
    off = _clamp(request.args.get("offset"), 0, 100000, 0)
    return jsonify(items=rows[off:off + lim], matched=len(rows), more=off + lim < len(rows), summary=summary)


@app.get("/api/admin/overview")
@admin_only
def api_admin_overview(uid):
    cut, day = naive() - timedelta(seconds=ONLINE_SECS), naive() - timedelta(days=1)
    agg = list(db.users.aggregate([{"$group": {"_id": None, "tok": {"$sum": {"$ifNull": ["$tokens", 0]}}, "refs": {"$sum": {"$ifNull": ["$refs", 0]}}}}]))
    rows = _bot_rows()
    top = lambda key, n=5: sorted([r for r in rows if r[key] > 0], key=_BSORT[key], reverse=True)[:n]
    return jsonify(users=db.users.count_documents({}), online=db.users.count_documents({"seen": {"$gte": cut}}),
                   new24=db.users.count_documents({"created": {"$gte": day}}), builders_blocked=db.users.count_documents({"mb_blocked": True}),
                   bots=len(rows), active=sum(1 for r in rows if r["on"]), subs=sum(r["total"] for r in rows),
                   subs_blocked=sum(r["blocked"] for r in rows), subs_online=sum(r["online"] for r in rows),
                   subs_act24=sum(r["act24"] for r in rows), subs_new24=sum(r["new24"] for r in rows),
                   forms=db.submissions.count_documents({}), circulation=int(agg[0]["tok"]) if agg else 0,
                   referrals=int(agg[0]["refs"]) if agg else 0,
                   top_subs=sorted(rows, key=_BSORT["subs"], reverse=True)[:5], top_act=top("act24"), top_new=top("new24", 3))


@app.get("/api/admin/announces")
@admin_only
def api_admin_announces(uid):
    items = []
    for x in db.announces.find({}).sort("t", -1).limit(20):
        done = bool(x.get("done"))
        stale = not done and age_sec(x["t"]) > 7200
        items.append({"id": x["_id"], "kind": x.get("kind", ""), "label": x.get("label", ""), "text": x.get("text", ""), "media": bool(x.get("media")),
                      "total": int(x.get("total", 0)), "ok": int(x.get("ok", 0)), "sent": int(x.get("sent", 0)),
                      "state": "done" if done else "stale" if stale else "run", "t": naive(x["t"]).isoformat() + "Z"})
    lk = db.locks.find_one({"_id": "announce"})
    return jsonify(items=items, busy=bool(lk and age_sec(lk["t"]) < 3600))


@app.post("/api/admin/bots/broadcast")
@admin_only
def api_admin_bots_broadcast(uid):
    """اطلاعیه از طریق چند ربات انتخاب‌شده (حداکثر ۳۰ ربات) برای مخاطب‌های همان ربات‌ها"""
    b = request.get_json(silent=True) or {}
    ids = []
    for x in (b.get("bots") or [])[:60]:
        try:
            ids.append(ObjectId(str(x)))
        except InvalidId:
            pass
    ids = list(dict.fromkeys(ids))[:30]
    if not ids:
        return jsonify(error="اول چند ربات انتخاب کن"), 400
    text = str(b.get("text", "")).strip()[:3500]
    mid = str(b.get("media") or "")
    if mid and not get_media(mid, uid):
        mid = ""
    fmt = "html" if b.get("fmt") == "html" else ""
    if not mid and len(text) < 2:
        return jsonify(error="متن یا رسانه‌ی پیام رو وارد کن"), 400
    with_owner = bool(b.get("with_owner"))
    pairs, busy = [], 0
    for bt in db.bots.find({"_id": {"$in": ids}, "active": True, "token_enc": {"$exists": True}}):
        bid = str(bt["_id"])
        q = {"bot": bid, "blocked": {"$ne": True}}
        if not with_owner:
            q["uid"] = {"$ne": bt["owner"]}
        chats = [x["chat"] for x in db.subs.find(q, {"chat": 1})]
        if not chats:
            continue
        if not _abc_lock(bid):
            busy += 1
            continue
        pairs.append((bt, chats))
    if not pairs:
        return jsonify(error="ارسال دیگه‌ای در حاله" if busy else "گیرنده‌ای پیدا نشد (ربات‌ها غیرفعال‌ان یا مخاطب ندارن)"), 409 if busy else 400
    total = sum(len(c) for _, c in pairs)
    rec = ann_new("bots", uid, text, total, f"{len(pairs)} ربات", mid)
    threading.Thread(target=run_multi_send, args=(pairs, text, uid, mid, fmt, rec), daemon=True).start()
    return jsonify(queued=total, bots=len(pairs), skipped=busy)


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
                   lock_text=d.get("lock_text") or PROMO_DEF_LOCK, stats={k: int(st.get(k, 0)) for k in ("tgt", "msg", "lock", "joined", "err", "terr")}, last_err=st.get("last_err", ""), test=bool(d.get("test")),
                   trace=[{"t": x["t"], "s": x["s"]} for x in ((db.settings.find_one({"_id": "promo_trace"}) or {}).get("items") or [])[-15:]][::-1])


@app.post("/api/admin/promo/reset")
@admin_only
def api_admin_promo_reset(uid):
    db.settings.delete_one({"_id": "promo_stats"})
    db.settings.delete_one({"_id": "promo_trace"})
    return jsonify(ok=True)


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
        "on": bool(b.get("on")) and bool(eff), "test": bool(b.get("test")), "channels": chans,
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

games._idx()      # ایندکس‌های مجموعه‌های بازی

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
