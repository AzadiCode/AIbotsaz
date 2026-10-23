# -*- coding: utf-8 -*-
"""
patcher.py — معمار پچ‌محور (مرحله ۵): ویرایش ربات با فهرست عملیات تایپ‌شده، نه بازتولید کامل.

apply_patch: اعمال عملیات روی کانفیگ (خروجی خام؛ اعتبارسنجی نهایی با sanitize در فراخوان)
patch_propose: درخواست کاربر → عملیات‌ها (با یک دور ترمیم) + sanitize
op_desc / patch_brief: توضیح فارسی عملیات و خلاصه‌ی فشرده‌ی کانفیگ برای مدل

از ai.py جدا شد تا ai.py زیر سقف اندازه بماند؛ ai.py در انتهای فایل این ماژول را re-export می‌کند
(الگوی templates.py). توجه: این ماژول به ai وابسته است — همیشه بعد از ai مصرف شود (import مستقیم
پیش از ai تودرتویی می‌کند). ارجاع به llm_post با صفت ماژول است تا پچ در تست‌ها (LLM ساختگی) دیده شود.
"""
import json
import re

import ai
from ai import (AI_MAX_TOKENS, BUILTINS, GRP_ON, ID_RE, LANG_GUARD, MAX_TRIGGERS, VAR_RE, VAR_TYPES,
                detect_lang, has_foreign, sanitize, scrub_deep)
from prompts import _SP_PATCH

# ═══════════════ مرحله ۵: معمار پچ‌محور — ویرایش با فهرست عملیات تایپ‌شده، نه بازتولید کامل ═══════════════
PATCH_MAX_OPS = 12
PATCH_OPS = ("add_node", "update_node", "delete_node", "set_text", "set_next", "add_button", "delete_button",
             "set_var", "del_var", "set_start", "set_fallback", "add_command", "del_command", "add_trigger")


def _free_node_id(nodes):
    i = 1
    while f"n{i}" in nodes:
        i += 1
    return f"n{i}"


def _patch_btn_rows(rows):
    """ردیف‌های دکمه‌ی مدل → [[{text, goto}]] با سقف‌های sanitize (۶ ردیف، ۳ ستون)"""
    out = []
    for row in (rows if isinstance(rows, list) else [])[:6]:
        r = []
        for b in (row if isinstance(row, list) else [row])[:3]:
            if isinstance(b, dict) and str(b.get("text") or "").strip() and str(b.get("goto") or "").strip():
                r.append({"text": str(b["text"]).strip()[:40], "goto": str(b["goto"]).strip()})
        if r:
            out.append(r)
    return out


def _cleanup_node_refs(cfg, rid):
    """بعد از حذف یک بخش، همه‌ی ارجاع‌های داخل کانفیگ به آن پاک می‌شود"""
    nodes = cfg.get("nodes") or {}
    for n in nodes.values():
        if not isinstance(n, dict):
            continue
        rows = n.get("buttons")
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, list):
                    row[:] = [b for b in row if not (isinstance(b, dict) and b.get("goto") == rid)]
            rows = [r for r in rows if r]
            if rows:
                n["buttons"] = rows
            else:
                n.pop("buttons", None)
        if n.get("next") == rid:
            n.pop("next", None)
        if isinstance(n.get("route"), list):
            keep = [r for r in n["route"] if isinstance(r, dict) and r.get("goto") != rid]
            if keep:
                n["route"] = keep
            else:
                n.pop("route", None)
        sw = n.get("switch")
        if isinstance(sw, dict) and isinstance(sw.get("cases"), list):
            keep = [c for c in sw["cases"] if isinstance(c, dict) and c.get("goto") != rid]
            if keep:
                sw["cases"] = keep
            else:
                sw.pop("cases", None)
        ab = n.get("ab")
        if isinstance(ab, dict):
            for k in ("goto_a", "goto_b"):
                if ab.get(k) == rid:
                    ab.pop(k, None)
        for k in ("menu", "on_error", "wait"):
            x = n.get(k)
            if isinstance(x, dict) and x.get("goto") == rid:
                x.pop("goto", None)
    cmds = cfg.get("commands")
    if isinstance(cmds, dict):
        keep = {c: t for c, t in cmds.items() if t != rid}
        if keep:
            cfg["commands"] = keep
        else:
            cfg.pop("commands", None)
    for k in ("start", "fallback"):
        if cfg.get(k) == rid:
            rest = [x for x in nodes if x != rid]
            if rest:
                cfg[k] = rest[0]
            else:
                cfg.pop(k, None)


def apply_patch(cfg, ops):
    """فهرست عملیات تایپ‌شده را به‌ترتیب روی کانفیگ اعمال می‌کند.
    خروجی: (کانفیگ خامِ پچ‌شده، نتیجه‌ی هر عملیات [{"i","op","ok","msg","node"}]).
    اعتبارسنجی عمیق با sanitize در فراخوان است؛ اینجا فقط شکل عملیات‌ها سخت‌گیری می‌شود."""
    cfg = json.loads(json.dumps(cfg, ensure_ascii=False))
    nodes = cfg.setdefault("nodes", {})
    results = []

    def one(i, op, ok, msg="", node=""):
        results.append({"i": i, "op": str(op.get("op") or "?") if isinstance(op, dict) else "?", "ok": ok, "msg": msg, "node": node})

    for i, op in enumerate(list(ops or [])[:PATCH_MAX_OPS]):
        if not isinstance(op, dict) or op.get("op") not in PATCH_OPS:
            one(i, op, False, "عملیات ناشناس است")
            continue
        kind = op["op"]
        nid = lambda k: str(op.get(k) or "").strip()
        try:
            if kind == "add_node":
                pid = nid("id")
                if pid:
                    if not ID_RE.match(pid):
                        one(i, op, False, f"شناسه‌ی «{pid}» معتبر نیست (حروف انگلیسی کوچک، عدد و _)")
                        continue
                    if pid in nodes:
                        one(i, op, False, f"بخش «{pid}» از قبل وجود دارد")
                        continue
                    newid = pid
                else:
                    newid = _free_node_id(nodes)
                n = {"title": nid("title")[:40] or "بخش تازه",
                     "text": str(op.get("text") or "").strip()[:3500] or "متن این بخش را اینجا بنویس"}
                if op.get("ask"):
                    n["ask"] = True
                nx = nid("next")
                if nx and nx not in nodes:
                    one(i, op, False, f"«next» به بخش ناشناس «{nx}» می‌رود")
                    continue
                if nx:
                    n["next"] = nx
                rows = _patch_btn_rows(op.get("buttons"))
                g = next((b["goto"] for row in rows for b in row if b["goto"] not in nodes), None)
                if g:
                    one(i, op, False, f"دکمه به بخش ناشناس «{g}» می‌رود")
                    continue
                if rows:
                    n["buttons"] = rows
                nodes[newid] = n
                op["_id"] = newid
                one(i, op, True, node=newid)
            elif kind == "update_node":
                p = nid("id")
                if p not in nodes:
                    one(i, op, False, f"بخش «{p}» پیدا نشد")
                    continue
                n = nodes[p]
                if nid("title"):
                    n["title"] = nid("title")[:40]
                if str(op.get("text") or "").strip():
                    n["text"] = str(op["text"]).strip()[:3500]
                nx = nid("next")
                if nx:
                    if nx not in nodes:
                        one(i, op, False, f"«next» به بخش ناشناس «{nx}» می‌رود")
                        continue
                    n["next"] = nx
                if "ask" in op:
                    if op["ask"]:
                        n["ask"] = True
                    else:
                        n.pop("ask", None)
                one(i, op, True, node=p)
            elif kind == "delete_node":
                p = nid("id")
                if p not in nodes:
                    one(i, op, False, f"بخش «{p}» پیدا نشد")
                    continue
                nodes.pop(p)
                _cleanup_node_refs(cfg, p)
                one(i, op, True, node=p)
            elif kind in ("set_text", "set_next", "add_button", "delete_button", "set_start", "set_fallback"):
                p = nid("node") if "node" in op else nid("id")
                if p not in nodes:
                    one(i, op, False, f"بخش «{p}» پیدا نشد")
                    continue
                n = nodes[p]
                if kind == "set_text":
                    t = str(op.get("text") or "").strip()
                    if not t:
                        one(i, op, False, "متن خالی است")
                        continue
                    n["text"] = t[:3500]
                elif kind == "set_next":
                    nx = nid("next")
                    if nx not in nodes:
                        one(i, op, False, f"مقصد «{nx}» پیدا نشد")
                        continue
                    n["next"] = nx
                elif kind == "add_button":
                    gt = nid("goto")
                    if gt not in nodes:
                        one(i, op, False, f"مقصد «{gt}» پیدا نشد")
                        continue
                    rows = n.setdefault("buttons", [])
                    if rows and len(rows[-1]) < 3:
                        rows[-1].append({"text": nid("text")[:40], "goto": gt})
                    elif len(rows) < 6:
                        rows.append([{"text": nid("text")[:40], "goto": gt}])
                    else:
                        one(i, op, False, "سقف دکمه‌های این بخش پر است")
                        continue
                elif kind == "delete_button":
                    t = nid("text")
                    hit = False
                    for row in n.get("buttons") or []:
                        for b in list(row):
                            if b.get("text", "").strip() == t:
                                row.remove(b)
                                hit = True
                    if not hit:
                        one(i, op, False, f"دکمه‌ی «{t}» پیدا نشد")
                        continue
                    rows = [r for r in (n.get("buttons") or []) if r]
                    if rows:
                        n["buttons"] = rows
                    else:
                        n.pop("buttons", None)
                else:
                    cfg["start" if kind == "set_start" else "fallback"] = p
                one(i, op, True, node=p)
            elif kind in ("set_var", "del_var"):
                name = nid("name").lower()
                if not VAR_RE.match(name) or name in BUILTINS:
                    one(i, op, False, f"نام متغیر «{name}» معتبر نیست")
                    continue
                if kind == "del_var":
                    if name not in (cfg.get("vars") or {}):
                        one(i, op, False, f"متغیر «{name}» تعریف نشده")
                        continue
                    cfg["vars"].pop(name)
                else:
                    ty = str(op.get("type") or "").strip().lower()
                    if ty:
                        if ty not in VAR_TYPES:
                            one(i, op, False, f"نوع «{ty}» معتبر نیست")
                            continue
                        d = {"type": ty}
                        for k, cap in (("default", 100), ("min", 20), ("max", 20)):
                            if str(op.get(k) or "").strip():
                                d[k] = str(op[k]).strip()[:cap]
                        sc = str(op.get("scope") or "user").lower()
                        if sc in ("user", "global", "chat"):
                            d["scope"] = sc
                        cfg.setdefault("vars", {})[name] = d
                    else:
                        cfg.setdefault("vars", {})[name] = str(op.get("value") if op.get("value") is not None else "").strip()[:100]
                one(i, op, True)
            elif kind in ("add_command", "del_command"):
                cmd = re.sub(r"^[^\w]+", "", nid("cmd").lower())[:30]
                if not re.match(r"^[a-z0-9_]{1,30}$", cmd or ""):
                    one(i, op, False, f"دستور «{cmd}» معتبر نیست")
                    continue
                if kind == "add_command":
                    p = nid("node")
                    if p not in nodes:
                        one(i, op, False, f"بخش «{p}» پیدا نشد")
                        continue
                    cmds = cfg.setdefault("commands", {})
                    if len(cmds) >= 10 and cmd not in cmds:
                        one(i, op, False, "سقف ۱۰ دستور پر است")
                        continue
                    cmds[cmd] = p
                else:
                    if cmd not in (cfg.get("commands") or {}):
                        one(i, op, False, f"دستور «{cmd}» تعریف نشده")
                        continue
                    cfg["commands"].pop(cmd)
                one(i, op, True)
            elif kind == "add_trigger":
                on = str(op.get("on") or "contains").lower()
                if on not in GRP_ON:
                    on = "contains"
                raw_ws = op.get("words") if isinstance(op.get("words"), list) else re.split(r"[,،\n]+", str(op.get("words") or ""))
                ws = []
                for w in raw_ws[:10]:
                    w = str(w).strip()[:40]
                    if on == "command":
                        w = re.sub(r"[^\w]", "", w.lstrip("/").lower())
                    if w and w not in ws:
                        ws.append(w)
                reply = str(op.get("reply") or "").strip()[:1500]
                if not ws or not reply:
                    one(i, op, False, "ماشه به کلمه و پاسخ نیاز دارد")
                    continue
                g = cfg.setdefault("group", {})
                trs = g.setdefault("triggers", [])
                if len(trs) >= MAX_TRIGGERS:
                    one(i, op, False, "سقف ماشه‌های گروه پر است")
                    continue
                trs.append({"on": on, "words": ws, "reply": reply})
                one(i, op, True)
        except Exception as e:                    # هر عملیات خراب فقط همان رد می‌شود، نه کل پچ
            one(i, op, False, f"خطا: {str(e)[:120]}")
    return cfg, results


def op_desc(op):
    """توضیح فارسی کوتاه هر عملیات برای فهرست پذیرش/رد فرانت"""
    k = str(op.get("op") or "?")
    t = str(op.get("title") or op.get("text") or op.get("name") or op.get("cmd") or "").strip()[:30]
    p = str(op.get("id") or op.get("node") or "").strip()
    if k == "add_node":
        return f"افزودن بخش «{t}»" + (f" (شناسه {p})" if p else "")
    if k == "update_node":
        ch = [x for x in ("title", "text", "next") if op.get(x)]
        return f"ویرایش بخش «{p}»" + (f" ({'، '.join(ch)})" if ch else "")
    if k == "delete_node":
        return f"حذف بخش «{p}» و همه‌ی ارجاع‌هایش"
    if k == "set_text":
        return f"تغییر متن بخش «{p}»"
    if k == "set_next":
        return f"ادامه‌ی بخش «{p}» به «{op.get('next')}»"
    if k == "add_button":
        return f"افزودن دکمه‌ی «{t}» به بخش «{p}»"
    if k == "delete_button":
        return f"حذف دکمه‌ی «{t}» از بخش «{p}»"
    if k == "set_var":
        return f"تعریف یا به‌روزرسانی متغیر «{op.get('name')}»"
    if k == "del_var":
        return f"حذف متغیر «{op.get('name')}»"
    if k == "set_start":
        return f"بخش شروع به «{p}»"
    if k == "set_fallback":
        return f"بخش بن‌بست به «{p}»"
    if k == "add_command":
        return f"دستور /{op.get('cmd')} به بخش «{p}»"
    if k == "del_command":
        return f"حذف دستور /{op.get('cmd')}"
    if k == "add_trigger":
        return "ماشه‌ی گروه برای " + "، ".join(str(x) for x in (op.get("words") or [])[:3])
    return k


def patch_brief(cfg, focus=None):
    """خلاصه‌ی فشرده‌ی کانفیگ برای مدل پچ (توکن کمتر)؛ نود انتخاب‌شده با متن کامل"""
    nodes = {}
    for nid, n in (cfg.get("nodes") or {}).items():
        if not isinstance(n, dict):
            continue
        nodes[nid] = {"title": n.get("title"), "text": (n.get("text") or "")[:110], "next": n.get("next"),
                      "ask": bool(n.get("ask") or n.get("fields")), "ai": bool(n.get("ai")),
                      "buttons": [[{"text": b.get("text"), "goto": b.get("goto") or ("pay" if b.get("pay") else b.get("url") or b.get("alert") or "…")}
                                   for b in row] for row in (n.get("buttons") or [])]}
    brief = {"name": cfg.get("name"), "start": cfg.get("start"), "fallback": cfg.get("fallback"),
             "vars": cfg.get("vars"), "globals": cfg.get("globals"), "commands": cfg.get("commands"),
             "tables": {t: sorted((td.get("fields") or {}).keys()) for t, td in (cfg.get("tables") or {}).items()},
             "nodes": nodes}
    if focus and isinstance((cfg.get("nodes") or {}).get(focus), dict):
        brief["focus"] = cfg["nodes"][focus]
    return brief


def patch_propose(prompt, cfg, focus=None, acc=None, guard_lang=True):
    """درخواست کاربر → فهرست عملیات پچ (با یک دور ترمیم اگر اعتبارسنجی رد شد).
    خروجی: (ops، نتیجه‌ها، کانفیگ پیشنهادیِ sanitize‌شده یا None، پیام خطا)"""
    acc = [] if acc is None else acc
    nodes = cfg.get("nodes") or {}
    if focus not in nodes:
        focus = None
    brief = json.dumps(patch_brief(cfg), ensure_ascii=False)
    full = json.dumps(nodes[focus], ensure_ascii=False) if focus else ""
    guard = guard_lang and detect_lang(prompt) == "fa" and not has_foreign(prompt)
    sysp = _SP_PATCH + (LANG_GUARD if guard else "")
    ops, results, last_err, feedback = [], [], "", ""
    for _ in (0, 1):
        parts = ["Current config summary:\n" + brief]
        if full:
            parts.append("Selected node (full):\n" + full)
        parts.append("Change request:\n" + prompt)
        if feedback:
            parts.append("Your previous ops were rejected: " + last_err[:300] + ". Fix them and return the JSON object again.")
        parts.append('Reminder: reply with one JSON object {"ops": [...]} only.')
        txt, usage = ai.llm_post([{"role": "system", "content": sysp}, {"role": "user", "content": "\n\n".join(parts)}],
                              min(AI_MAX_TOKENS, 1600), temperature=0.2, timeout=90)
        acc.append(usage)
        m = re.search(r"\{.*\}", txt, re.S)
        if not m:
            last_err = "پاسخ شامل JSON نبود"
            feedback = last_err
            continue
        try:
            raw = json.loads(m.group(0))
        except Exception:
            last_err = "JSON نامعتبر بود"
            feedback = last_err
            continue
        ops = raw.get("ops") if isinstance(raw, dict) else raw
        if not isinstance(ops, list):
            last_err = "«ops» فهرست نبود"
            feedback = last_err
            continue
        ops = [o for o in ops if isinstance(o, dict)][:PATCH_MAX_OPS]
        if guard:
            ops = scrub_deep(ops)
        new, results = apply_patch(cfg, ops)
        try:
            return ops, results, sanitize(new, strict=True), ""
        except ValueError as e:
            last_err = str(e)
            feedback = last_err
    return ops, results, None, last_err
