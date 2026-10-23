# -*- coding: utf-8 -*-
"""patch13: ابزارفراخوانی عامل (جستجوی جدول‌های ربات با فهرست سفید) — دو مرحله‌ای، در چت و مینی‌اپ و تست"""
import io

# ── ai.py: فهرست سفید ابزارها در اعتبارسنج ──
p = "ai.py"
s = io.open(p, encoding="utf-8").read()
old = '''                sc = str(ai.get("scope") or "").strip()[:200]
                if sc:
                    node["ai"]["scope"] = sc          # گارد موضوعی: فقط این موضوع‌ها'''
assert old in s, "scope anchor"
s = s.replace(old, old + '''
                tls = []                              # ابزارها: جستجو در همین جدول‌های ربات (حداکثر ۳)
                for x in (ai.get("tools") if isinstance(ai.get("tools"), list) else [])[:3]:
                    t2 = str(x).strip().lower()
                    if TAB_RE.match(t2) and t2 not in tls:
                        _reg_tab(tables, t2, [])
                        tls.append(t2)
                if tls:
                    node["ai"]["tools"] = tls''', 1)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("ai tools ok")

# ── engine.py: پروتکل ابزار ──
p = "engine.py"
s = io.open(p, encoding="utf-8").read()
old = "import re, time, hashlib, random, threading"
assert old in s, "imports"
s = s.replace(old, "import re, time, hashlib, random, threading, json", 1)

old = '''def kb_for(bot_id):'''
assert old in s, "kb anchor"
s = s.replace(old, '''def agent_tools_block(node, cfg):
    """پرومپت ابزارها: عامل می‌تواند پیش از جواب، در جدول‌های مجاز جستجو کند (فهرست سفید)"""
    tools = (node.get("ai") or {}).get("tools") or []
    if not tools:
        return "", []
    lines = []
    for t in tools:
        fs = (cfg.get("dbfields") or {}).get(t) or []
        lines.append("جدول «" + t + "» فیلدها: " + (", ".join(fs) if fs else "(آزاد)"))
    return ("TOOLS: You may search the bot's data tables before answering. To search, reply ONLY with one JSON object: "
            '{"tool": "search_table", "table": "<نام جدول>", "query": "<عبارت>"} — available: '
            + "؛ ".join(lines) + ". If you do not need the data, answer normally in Persian."), tools


def _try_tool_call(txt):
    m = re.search(r"\\{[\\s\\S]*\\}", str(txt or ""))
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
    except Exception:
        return None
    if isinstance(j, dict) and j.get("tool") == "search_table":
        return j
    return None


def agent_tool_search(bot_id, tools, table, query, limit=5):
    """جستجوی واقعی در جدول (فقط جدول‌های فهرست سفید) → خط‌های خوانا"""
    if table not in (tools or []):
        return None
    try:
        docs = list(db.recs.find({"bot": bot_id, "t": table}).sort("n", -1).limit(200))
    except Exception:
        log.exception("agent_tool_search failed")
        docs = []
    qq = str(query or "").strip().casefold()
    out = []
    for d in docs:
        dd = {k: v for k, v in (d.get("d") or {}).items() if str(v).strip()}
        hay = " ".join(str(v) for v in dd.values()).casefold()
        if qq and qq not in hay:
            continue
        out.append(" · ".join(f"{k}: {v}" for k, v in list(dd.items())[:6])[:200])
        if len(out) >= limit:
            break
    return out


def agent_tool_round(bot_id, system, hist, text, reply, pt, ct, tools, max_tokens=600):
    """اگر جواب مدل درخواست ابزار بود: جستجوی واقعی و مرحله‌ی دوم برای جواب نهایی"""
    tc = _try_tool_call(reply)
    if not tc or not tools:
        return reply, pt, ct
    rows = agent_tool_search(bot_id, tools, str(tc.get("table") or "")[:20], str(tc.get("query") or "")[:60])
    tm = "نتیجه‌ی جستجوی داده‌های ربات:\\n" + ("\\n".join(rows) if rows else "(چیزی پیدا نشد)")
    from ai import llm_post, AI_CHAT_MODEL
    r2, (pt2, ct2) = llm_post([{"role": "system", "content": system}, *hist,
                               {"role": "user", "content": text[:1500]},
                               {"role": "assistant", "content": reply[:600]},
                               {"role": "user", "content": tm + "\\n\\nحالا جواب نهایی را فارسی و کوتاه بده؛ فقط بر اساس این نتیجه‌ها و اگر کافی نیست صادقانه بگو."}],
                              max_tokens, temperature=0.5, timeout=60, model=AI_CHAT_MODEL)
    return r2, pt + pt2, ct + ct2


def kb_for(bot_id):''', 1)

# اتصال در ai_chat
old = '''        if ai.get("scope"):
            system += "\\n\\nمحدوده‌ی موضوعی: فقط درباره‌ی موضوع‌های زیر جواب بده؛ اگر سؤال بیرون از این‌ها بود، مؤدبانه بگو خارج از حوزه‌ی توست: " + str(ai["scope"])'''
assert old in s, "scope inject"
s = s.replace(old, old + '''
        tools_block, tools = agent_tools_block(node, cfg)
        if tools_block:
            system += "\\n\\n" + tools_block''', 1)
old = '''        if guard and has_foreign(reply):                                   # یک بار دوباره با تأکید؛ اگه باز نشد حذف می‌کنیم'''
assert old in s, "foreign check"
s = s.replace(old, '''        reply, pt, ct = agent_tool_round(bot_id, system, hist, text, reply, pt, ct, tools, AI_NODE_MAX_TOKENS)
        if guard and has_foreign(reply):                                   # یک بار دوباره با تأکید؛ اگه باز نشد حذف می‌کنیم''', 1)

# اتصال در مینی‌اپ (_rt_ai)
old = '''    try:
        from engine import kb_search as _kb_search
        know = _kb_search(bot_id, text, 2)
        if know:
            system += "\\n\\nدانش کسب‌وکار (فقط بر اساس این جواب بده و از دانش بیرون چیز نساز):\\n" + \\
                "\\n".join(f"- {t}: {x}" for t, x in know)
    except Exception:
        log.exception("app kb inject failed")'''
assert old in s, "rt kb"
s = s.replace(old, old + '''
    tools = []
    try:
        from engine import agent_tools_block
        tb, tools = agent_tools_block({"t": el}, bot["config"])
        if tb:
            system += "\\n\\n" + tb
    except Exception:
        log.exception("app tools block failed")''', 1)
old = '''    ai_postcharge(bot["owner"], bot_id, pt, ct)
    reply = scrub_foreign(reply) if has_foreign(reply) else reply'''
assert old in s, "rt postcharge"
s = s.replace(old, '''    try:
        from engine import agent_tool_round
        reply, pt, ct = agent_tool_round(bot_id, system, hist, text, reply, pt, ct, tools, AI_NODE_MAX_TOKENS)
    except Exception:
        log.exception("app tool round failed")
    ai_postcharge(bot["owner"], bot_id, pt, ct)
    reply = scrub_foreign(reply) if has_foreign(reply) else reply''', 1)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("engine tools ok")

# ── app.py: تست عامل هم ابزارها را بفهمد ──
p = "app.py"
s = io.open(p, encoding="utf-8").read()
old = '''    from engine import kb_search, AI_CHILD_PROMPT
    from ai import has_foreign, scrub_foreign, llm_post, AI_CHAT_MODEL
    know = kb_search(bot_id, text, 3)
    system = AI_CHILD_PROMPT.replace("{bot}", bot["config"].get("name", "")) + ai.get("prompt", "")
    if know:
        system += "\\n\\nدانش کسب‌وکار (فقط بر اساس این جواب بده و از دانش بیرون چیز نساز):\\n" + \\
            "\\n".join(f"- {t}: {x}" for t, x in know)
    try:
        reply, (pt, ct) = llm_post([{"role": "system", "content": system}, {"role": "user", "content": text}],
                                   500, temperature=0.5, timeout=60, model=AI_CHAT_MODEL)
    except Exception:
        return jsonify(error="اتصال به هوش مصنوعی برقرار نشد؛ کمی بعد دوباره امتحان کن"), 502'''
assert old in s, "agent test anchor"
s = s.replace(old, '''    from engine import kb_search, AI_CHILD_PROMPT, agent_tools_block, agent_tool_round
    from ai import has_foreign, scrub_foreign, llm_post, AI_CHAT_MODEL
    know = kb_search(bot_id, text, 3)
    system = AI_CHILD_PROMPT.replace("{bot}", bot["config"].get("name", "")) + ai.get("prompt", "")
    if know:
        system += "\\n\\nدانش کسب‌وکار (فقط بر اساس این جواب بده و از دانش بیرون چیز نساز):\\n" + \\
            "\\n".join(f"- {t}: {x}" for t, x in know)
    tb, tools = agent_tools_block(node, bot["config"])
    if tb:
        system += "\\n\\n" + tb
    try:
        reply, (pt, ct) = llm_post([{"role": "system", "content": system}, {"role": "user", "content": text}],
                                   500, temperature=0.5, timeout=60, model=AI_CHAT_MODEL)
        reply, pt, ct = agent_tool_round(bot_id, system, [], text, reply, pt, ct, tools, 500)
    except Exception:
        return jsonify(error="اتصال به هوش مصنوعی برقرار نشد؛ کمی بعد دوباره امتحان کن"), 502''', 1)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("app tools ok")
