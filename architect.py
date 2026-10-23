# -*- coding: utf-8 -*-
"""
architect.py — معمار هوشمند: از توضیح کاربر نوع ربات را تشخیص می‌دهد، نزدیک‌ترین نقشه‌ی
تست‌شده (Blueprint) را انتخاب می‌کند، حداکثر ۳ سؤال می‌پرسد، ربات و مینی‌اپ را با هم می‌سازد،
خودش را با بازرس منطقی تست می‌کند (تا ۲ دور ترمیم خودکار) و نتیجه را با کارت‌های فارسی برمی‌گرداند.

ویرایش بعدی هم همین‌جاست: مدلِ عملیاتِ کوچکِ تایپ‌شده (add_section / set_text / add_button / …)
اعمال می‌شود و هر عملیات به‌صورت کارت فارسی به کاربر نشان داده می‌شود؛ هیچ JSON خامی دیده نمی‌شود.
وابستگی: core ← ai ← engine ← webapp ← blueprints ← architect (app آن را بارگذاری می‌کند)
"""

import re, json

from core import db, now, log, limits_of, MAX_VERSIONS
from ai import sanitize, lint, llm_post, AI_CHAT_MODEL
from engine import sync_commands
import blueprints


# ───────────────────────── تشخیص و سؤال‌ها ─────────────────────────
def start(uid, idea):
    """تشخیص نقشه از توضیح؛ خروجی: (شناسه نقشه یا None، سؤال‌ها، عنوان)"""
    bid = blueprints.detect_blueprint(idea)
    if not bid:
        return None, [], ""
    bp = blueprints.BLUEPRINTS[bid]
    return bid, bp["questions"], bp["title"]


# ───────────────────────── خودآزمایی و ترمیم ─────────────────────────
def _selftest(bot_cfg, app_cfg, node_ids):
    """همه‌چیز سالم است؟ (بازرس منطقی ربات + مینی‌اپ + بررسی سیم‌ها) → فهرست مشکل فارسی"""
    problems = []
    try:
        problems += lint(bot_cfg)
    except Exception as e:
        problems.append(f"بازرس ربات: {e}")
    if app_cfg:
        try:
            from webapp import lint_app
            problems += lint_app(app_cfg, bot_cfg)
        except Exception as e:
            problems.append(f"بازرس مینی‌اپ: {e}")
    # دکمه‌ی بی‌مقصد = باید همیشه صفر باشد؛ sanitize قبلاً حذفش می‌کند، اینجا فقط صفرِ دوباره‌چک
    nodes = bot_cfg.get("nodes") or {}
    for nid, n in nodes.items():
        for row in (n.get("buttons") or []):
            for b in (row if isinstance(row, list) else [row]):
                if isinstance(b, dict) and b.get("goto") and b["goto"] not in nodes:
                    problems.append("دکمه‌ی «%s» به بخش ناموجود وصل است" % b.get("text"))
    return problems


def _repair(cfg, problems):
    """ترمیم خودکار: وصل‌های شکسته را می‌بُرد تا ربات همیشه سالم منتشر شود (حداکثر ۲ دور از بیرون صدا زده می‌شود)"""
    changed = False
    nodes = cfg.get("nodes") or {}
    for nid, n in nodes.items():
        rows = n.get("buttons") or []
        new_rows = []
        for row in rows:
            items = row if isinstance(row, list) else [row]
            nr = []
            for b in items:
                if not isinstance(b, dict):
                    continue
                g = b.get("goto")
                if g and g not in nodes:
                    b = {k: v for k, v in b.items() if k != "goto"}
                    changed = True
                if b.get("text"):
                    nr.append(b)
            if nr:
                new_rows.append(nr)
        if new_rows != rows:
            n["buttons"] = new_rows
        if n.get("next") and n["next"] not in nodes:
            n.pop("next", None); changed = True
        if n.get("route"):
            keep = [r for r in n["route"] if r.get("goto") in nodes]
            if keep != n["route"]:
                n["route"] = keep or None
                if not n.get("route"):
                    n.pop("route")
                changed = True
    for cmd, nid in list((cfg.get("commands") or {}).items()):
        if nid not in nodes:
            cfg["commands"].pop(cmd); changed = True
    if cfg.get("start") not in nodes and nodes:
        cfg["start"] = next(iter(nodes)); changed = True
    return changed


# ───────────────────────── ساخت نهایی ─────────────────────────
def _rename_nodes(cfg, pfx, taken):
    """همه‌ی نودهای یک کانفیگ با پسوند تازه نام‌گذاری و همه‌ی ارجاع‌ها (goto/route/next/remind/pay) اصلاح می‌شوند"""
    mapping = {}
    for nid in list(cfg["nodes"].keys()):
        new = nid if nid not in taken and not nid.startswith(pfx) else f"{pfx}_{nid}"[:30]
        while new in taken or new in mapping.values():
            new = new[:28] + "_x"
        mapping[nid] = new
    nodes = {}
    for old, n in cfg["nodes"].items():
        n = json.loads(json.dumps(n))
        for row in n.get("buttons") or []:
            for b in row:
                if "goto" in b:
                    b["goto"] = mapping.get(b["goto"], b["goto"])
                if isinstance(b.get("pay"), dict) and b["pay"].get("goto"):
                    b["pay"]["goto"] = mapping.get(b["pay"]["goto"], b["pay"]["goto"])
        for r in n.get("route") or []:
            r["goto"] = mapping.get(r["goto"], r["goto"])
        if n.get("next"):
            n["next"] = mapping.get(n["next"], n["next"])
        for d in [n] + [x for row in n.get("buttons") or [] for x in row]:
            for a in d.get("do") or []:
                if a.get("op") == "remind" and a.get("goto"):
                    a["goto"] = mapping.get(a["goto"], a["goto"])
        nodes[mapping[old]] = n
    cfg["nodes"] = nodes
    cfg["start"] = mapping.get(cfg.get("start"), cfg.get("start"))
    cfg["fallback"] = mapping.get(cfg.get("fallback"), cfg.get("fallback"))
    cfg["commands"] = {c: mapping.get(nid, nid) for c, nid in (cfg.get("commands") or {}).items()}
    return mapping


def _merge_cfg(base, sub):
    """نودهای نقشه‌ی دوم را با نام تازه به نقشه‌ی اول می‌چسباند؛ دکمه‌ی ورود در شروعِ نقشه‌ی اول اضافه می‌شود"""
    if not isinstance(base, dict) or not isinstance(sub, dict) or not sub.get("nodes"):
        return None
    taken = set(base.get("nodes") or {})
    mapping = _rename_nodes(sub, "sub", taken)
    base["nodes"].update(sub["nodes"])
    for c, nid in (sub.get("commands") or {}).items():
        base.setdefault("commands", {}).setdefault(c, nid)
    for v, dv in (sub.get("vars") or {}).items():
        base.setdefault("vars", {}).setdefault(v, dv)
    entry = mapping.get(sub.get("start"), sub.get("start"))
    st = base["nodes"].get(base.get("start"))
    if st is not None and entry in base["nodes"]:
        title = (sub.get("name") or "بخش تازه")[:16]
        for row in st.get("buttons") or []:
            if len(row) < 3:
                row.append({"text": "➕ " + title, "goto": entry})
                break
        else:
            st["buttons"].append([{"text": "➕ " + title, "goto": entry}])
    return base, mapping


def _merge_app(base, sub):
    """صفحه‌های مینی‌اپ نقشه‌ی دوم را (با نام تازه در صورت برخورد) به مینی‌اپ اول و منو اضافه می‌کند"""
    if not isinstance(base, dict) or not isinstance(sub, dict):
        return
    sub_nav = set(sub.get("nav", {}).get("items") or [])
    for sid, s in (sub.get("screens") or {}).items():
        new = sid if sid not in (base.get("screens") or {}) else f"sub_{sid}"[:20]
        base.setdefault("screens", {})[new] = json.loads(json.dumps(s))
        nav = base.setdefault("nav", {"type": "tabs", "items": []})
        items = nav.setdefault("items", [])
        if sid in sub_nav and new not in items and len(items) < 6:
            items.append(new)


def build(uid, bid, answers, extra=()):
    """ساخت ربات + مینی‌اپ از نقشه (+ حداکثر ۲ نقشه‌ی دیگر که به همین ربات ادغام می‌شوند)؛ خروجی: (bot_cfg، app_cfg، کارت‌ها، مراحل، عنوان)"""
    out, title = blueprints.build_blueprint(bid, answers)
    lim = limits_of(uid)
    cards = list(out.get("cards") or [])
    steps = list(out.get("steps") or [])

    # ادغام نقشه‌های اضافه: نودها با نام تازه، دکمه‌ی ورود در «شروع»، دستورها و متغیرها و صفحه‌های مینی‌اپ
    for sid in (extra or [])[:2]:
        if not sid or sid == bid or sid not in blueprints.BLUEPRINTS:
            continue
        try:
            sub, sub_title = blueprints.build_blueprint(sid, {})
            merged = _merge_cfg(out["bot"], sub["bot"])
            if merged:
                out["bot"] = merged[0]
                if sub.get("app") and out.get("app"):
                    _merge_app(out["app"], sub["app"])
                cards += [f"ادغام شد: {sub_title}"] + (sub.get("cards") or [])[:2]
                steps.append(f"بخش «{sub_title}» را از دکمه‌ای که در شروع اضافه شد پیدا کن")
        except Exception:
            log.exception("blueprint merge failed for %s", sid)
            cards.append(f"ادغام «{blueprints.BLUEPRINTS.get(sid, {}).get('title') or sid}» انجام نشد و رد شد")

    # خودآزمایی + ترمیم (تا ۲ دور) قبل از اعتبارسنجی نهایی
    raw_bot = out["bot"]
    for _ in range(2):
        probs = _selftest(raw_bot, out.get("app"), set(raw_bot.get("nodes") or {}))
        if not probs:
            break
        if not _repair(raw_bot, probs):
            break
    cfg = sanitize(raw_bot, strict=False, nodes_cap=lim["nodes"])
    app_cfg = None
    if out.get("app"):
        from webapp import sanitize_app
        warns = []
        try:
            app_cfg = sanitize_app(out["app"], strict=False, blocks_cap=lim["blocks"],
                                   node_ids=set(cfg["nodes"].keys()), warns=warns)
        except ValueError as e:
            log.warning("blueprint app skipped: %s", e)
            cards.append("مینی‌اپ این نقشه ساخته نشد: " + str(e)[:80])
    return cfg, app_cfg, cards, steps, title


def save_new(uid, cfg, app_cfg, title, cards):
    """ساخت سند ربات تازه + ذخیره‌ی پیش‌نویس مینی‌اپ؛ خروجی: bot doc"""
    from mother import new_bot_doc
    bot = new_bot_doc(uid, cfg, f"این ربات از نقشه‌ی آماده‌ی «{title}» ساخته شد؛ همه‌ی بخش‌هایش تست‌شده است و می‌توانی همین حالا تغییرش بدهی.")
    if app_cfg:
        try:
            db.apps.update_one({"_id": str(bot["_id"])},
                               {"$set": {"draft": app_cfg, "owner": uid, "updated": now()}}, upsert=True)
        except Exception:
            log.exception("blueprint app save failed")
    return bot


# ───────────────────────── ویرایش با پچ (کارت‌های تغییر) ─────────────────────────
_PATCH_PROMPT = """You are a precise bot-config patcher. Given a bot config (JSON) and a Persian change request, output ONLY a JSON object:
{"ops": [{"op": "add_section", "id": "new_id", "title": "...", "text": "...", "back_to": "start"},
         {"op": "update_text", "node": "node_id", "text": "..."},
         {"op": "add_button", "node": "node_id", "text": "label", "goto": "node_id"},
         {"op": "set_ai_prompt", "node": "node_id", "prompt": "..."},
         {"op": "set_welcome", "text": "..."},
         {"op": "add_group_trigger", "words": ["..."], "reply": "..."},
         {"op": "rename", "name": "..."},
         {"op": "add_command", "cmd": "help", "node": "node_id"}], "cards": ["تغییر اول به فارسی", "تغییر دوم به فارسی"]}
Rules: ids in ^[a-z0-9_]{1,30}$; "goto"/"back_to" must be an existing node id (or the new one of add_section); max 8 ops; cards in Persian describing each change for a non-technical user; no other keys."""


def apply_edit(uid, bot, request_text, media_ids=()):
    """ویرایش با پچ: مدل عملیات می‌دهد، apply_patch اعمال می‌کند، sanitize تأیید می‌کند. خروجی: (bot جدید، کارت‌ها، خطا)"""
    cfg_in = json.loads(json.dumps(bot["config"]))
    user = "Change request:\n" + request_text[:1500] + "\n\nCurrent config:\n" + json.dumps(cfg_in, ensure_ascii=False)[:12000]
    txt, _ = llm_post([{"role": "system", "content": _PATCH_PROMPT}, {"role": "user", "content": user}],
                      1200, temperature=0.2, timeout=90, model=AI_CHAT_MODEL)
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError("پاسخ هوش مصنوعی قابل خواندن نبود؛ دوباره امتحان کن")
    data = json.loads(m.group(0))
    ops = data.get("ops") if isinstance(data.get("ops"), list) else []
    cards = [str(x).strip()[:120] for x in (data.get("cards") if isinstance(data.get("cards"), list) else []) if str(x).strip()][:8]
    if not ops:
        raise ValueError("هیچ تغییری از درخواستت فهمیدم؛ دقیق‌تر بنویس")
    nodes = cfg_in.setdefault("nodes", {})
    applied = []
    for op in ops[:8]:
        if not isinstance(op, dict):
            continue
        k = str(op.get("op") or "")
        try:
            if k == "add_section":
                nid = re.sub(r"[^a-z0-9_]", "", str(op.get("id") or "new"))[:30] or "new"
                base = nid; i = 1
                while nid in nodes:
                    i += 1; nid = f"{base}{i}"
                nodes[nid] = {"text": str(op.get("text") or "متن این بخش")[:3500], "title": str(op.get("title") or "")[:30],
                              "buttons": [[{"text": "منوی اصلی", "goto": cfg_in.get("start") or "start"}]], "ask": False}
                back = str(op.get("back_to") or "")
                if back in nodes:
                    nodes[nid]["buttons"][0][0]["goto"] = back
                applied.append("اضافه شد: بخش «" + (nodes[nid].get("title") or nid) + "»")
            elif k == "update_text" and str(op.get("node")) in nodes:
                n = nodes[str(op["node"])]
                old_t = n.get("text", "")
                n["text"] = str(op.get("text") or old_t)[:3500]
                applied.append("متن «" + (n.get("title") or str(op["node"])) + "» عوض شد")
            elif k == "add_button" and str(op.get("node")) in nodes and str(op.get("goto")) in nodes:
                n = nodes[str(op["node"])]
                rows = n.setdefault("buttons", [])
                lbl = str(op.get("text") or "دکمه")[:40]
                if not rows or len(rows[-1]) >= 3:
                    if len(rows) >= 6:
                        continue
                    rows.append([{"text": lbl, "goto": str(op["goto"])}])
                else:
                    rows[-1].append({"text": lbl, "goto": str(op["goto"])})
                applied.append(f"دکمه‌ی «{lbl}» به «{(n.get('title') or op['node'])}» اضافه شد")
            elif k == "set_ai_prompt" and str(op.get("node")) in nodes:
                n = nodes[str(op["node"])]
                n.pop("ask", None); n.pop("fields", None)
                n["ai"] = {"prompt": str(op.get("prompt") or "")[:1500], "daily": int(n.get("ai", {}).get("daily", 15)), "memory": int(n.get("ai", {}).get("memory", 3))}
                applied.append("دستور دستیارِ «" + (n.get("title") or str(op["node"])) + "» عوض شد")
            elif k == "set_welcome":
                md = cfg_in.get("mod") or {}
                md["welcome"] = str(op.get("text") or "")[:1000]
                cfg_in["mod"] = md
                applied.append("پیام خوش‌آمد عوض شد")
            elif k == "add_group_trigger":
                words = [w.strip()[:40] for w in (op.get("words") or [])[:10] if str(w).strip()]
                reply = str(op.get("reply") or "")[:1500]
                if words and reply:
                    g = cfg_in.get("group") or {"triggers": []}
                    g.setdefault("triggers", []).append({"on": "contains", "words": words, "reply": reply})
                    cfg_in["group"] = g
                    applied.append("قانون گروه اضافه شد: «" + "، ".join(words[:3]) + "»")
            elif k == "rename":
                applied.append("نام ربات عوض شد")
                cfg_in["name"] = str(op.get("name") or cfg_in.get("name"))[:50]
            elif k == "add_command":
                cmd = re.sub(r"[^a-z0-9_]", "", str(op.get("cmd") or "").lstrip("/").lower())[:30]
                if cmd and cmd != "start" and str(op.get("node")) in nodes:
                    cfg_in.setdefault("commands", {})[cmd] = str(op["node"])
                    applied.append("دستور /" + cmd + " ساخته شد")
        except Exception:
            continue
    if not applied:
        raise ValueError("این تغییر با ابزارهای فعلی ربات ممکن نیست؛ دقیق‌تر بنویس")
    cfg = sanitize(cfg_in, strict=False, nodes_cap=limits_of(uid)["nodes"])
    return cfg, (cards or applied), applied


def save_edit(uid, bot, cfg):
    """ذخیره‌ی ویرایش پچی با نسخه‌ی برگشت"""
    from core import perks_of
    db.bots.update_one({"_id": bot["_id"]}, {
        "$set": {"config": cfg, "name": cfg["name"], "thinking": "", "updated": now()},
        "$push": {"versions": {"$each": [bot["config"]], "$slice": -(MAX_VERSIONS + perks_of(uid)["ver"])}}})
    doc = db.bots.find_one({"_id": bot["_id"]})
    try:
        sync_commands(doc, cfg)
    except Exception:
        log.exception("sync_commands failed")
    return doc
