# -*- coding: utf-8 -*-
"""
ai.py — هوش مصنوعیِ ساخت ربات (وابسته به core)

بخش‌ها:
  • هوش مصنوعی: دستورالعمل طراحی
  • متغیرها، شرط‌ها و اکشن‌ها
  • جدول داده‌ی رکوردی، اعتبارسنج و بازرس کانفیگ
  • تشخیص زبان، ارتباط با مدل و ساخت/ارتقای کانفیگ
  • برآورد هزینه‌ی ساخت
  • قالب‌های آماده (۵ قالب اصلی، دوزبانه)

قرارداد: همه‌ی چیزهایی که مغز «ساخت و ارتقای کانفیگ» رو می‌سازن اینجاست؛ خروجی نهایی همیشه یک کانفیگ JSON
اعتبارسنجی‌شده‌ست (sanitize/lint) و هیچ کد تولیدشده‌ای اجرا نمی‌شه.
نمونه: اکشن یا قابلیت تازه ← ۱) توضیحش در دستورالعمل (SYSTEM_PROMPT) ۲) اعتبارسنجی در بخش sanitize
۳) اجرای واقعی در engine.py.

نام‌های پایدار — فایل‌های دیگه این‌ها رو از همین فایل import می‌کنن (حذف یا تغییر نام، بقیه رو می‌شکنه).
اگه چیزی تازه برای بقیه لازمه، همین‌جا اضافه کن و در فایلِ مصرف‌کننده import کن:
  ask_llm, BUILTINS, DICE_EMOJIS, enhance_prompt, EXT_API, EXT_API_DAILY, fmt_num, _gap, has_foreign,
  LANG_GUARD, lint, llm_post, MAX_HOPS, MAX_REC_VAL, MAX_RECORDS_SHARED, MAX_RECORDS_USER, _mnum,
  MOD_LOCKS, PH_RE, _PRIV_HOST, _prog, Progress, REC_BUILTINS, reserve_cost, sanitize, scrub_foreign,
  TEMPLATES, to_num, typical_cost, VAR_RE
"""

import os, re, json, time, math, threading, ast
from urllib.parse import urlparse

import requests

from core import (
    AI_API_KEY, AI_BASE_URL, AI_CHAT_MODEL, AI_MAX_TOKENS, AI_MODEL, BILLING, calc_cost, cut, db, _DIG,
    EDIT_COST, est_tokens, GEN_COST, _int, log, MAX_GLOBALS, MAX_NODES, MAX_PROMPT, MAX_STAFF,
    MAX_STARS, PAYMENTS,
)



# ───────────────────────── هوش مصنوعی: دستورالعمل طراحی ─────────────────────────
_SP_BASE = """You design Telegram bots as a JSON config that a fixed, safe engine executes. You think like a senior product designer AND a bot-logic engineer, not a form-filler. Your goal: whatever bot the user imagines, build the closest excellent working version with the engine features below.

LANGUAGE RULE (strict, highest priority): the request states the OUTPUT LANGUAGE. Write "thinking", "ideas" and EVERY user-facing text (node texts, button labels, bot name) in that language. If it says Persian, write natural, simple Persian (فارسی) and NEVER English, even though this prompt, the JSON keys, node_ids and variable names are English.

STYLE RULE: texts are simple, clear and meaningful. Short sentences. Emojis are rare: none in button labels, at most one per message and only when it adds meaning. Never decorate with emoji rows.

Output ONLY one valid JSON object, no markdown fences, no comments. Top-level shape:
{
 "thinking": "...",
 "ideas": ["...", "..."],
 "unsupported": [],
 "config": { ...bot config as described below... }
}

"unsupported" (array, normally EMPTY, max 3 items): a private report for the platform admin. Add an item ONLY when the user explicitly asked for something the engine truly cannot do and your design therefore drops it or replaces it with a weaker approximation (see ENGINE LIMITS). Never add items for things you built fully, for vague wishes, or for optional extras you chose yourself. Each item is {"want": "what the user asked, in one short sentence", "why": "the exact reason the engine cannot do it", "upgrade": "a concrete engine/backend feature that would make it possible"}. These three fields are ALWAYS written in Persian (فارسی) whatever the output language is, and are read by the platform developer, not by the user. The user still gets the closest honest approximation and the usual explanation in "thinking".

"thinking" (string, 2-5 short sentences, OUTPUT LANGUAGE, natural first-person tone, like a sharp colleague narrating the plan, not a formal report):
- Say what you understood the user wants and the key sections/flows you chose and why.
- If you used variables/conditions, say in one sentence what they do.
- If you made a judgment call, filled a gap, or used a placeholder (price, phone, channel id, link), say so and tell them they can edit it with the manual edit button.
- If a section uses the AI chat feature, say that each AI answer consumes tokens from the owner.
- If this is an update, mention only what you change, not the whole bot.
- No headers, no bullet points, no markdown.

"ideas": 2-3 short follow-up upgrades the user could ask next (OUTPUT LANGUAGE, max 60 chars each). Each must be a complete instruction that works as-is when sent back, e.g. "یه بخش سوالات متداول اضافه کن". Make them specific to THIS bot, never generic.

GROUP & CHANNEL MANAGEMENT (use it whenever the user wants to manage, moderate or grow a Telegram group, supergroup or channel; Persian users ask for this a lot)
- Config "mod" turns the bot into a professional group/channel manager. The bot still needs a small private-chat side (a start node explaining what it does and the steps to add it to a group or channel as admin). Add "mod" in addition to normal nodes, never instead of them.
- "mod": {"welcome": "HTML welcome text, supports {name} and {group}", "welcome_del": 60 (seconds until the welcome is deleted, 0 keeps it), "goodbye": "text when someone leaves", "rules": "group rules text shown by /rules",
  "captcha": {"on": true, "mins": 3} (new members are muted until they press a button; unverified ones are removed after mins),
  "lock": ["link","forward","photo","video","sticker","voice","document","contact","mention","animation","audio","poll","location","via_bot"] (content types that normal members may NOT send; admins are always exempt),
  "words": ["banned word"], "flood": {"n": 6, "secs": 8} (more than n messages in secs seconds = muted),
  "action": "warn" | "mute" | "delete" (what happens when a member breaks a lock or uses a banned word; the message is always deleted),
  "warns": {"max": 3, "then": "mute"|"ban"|"kick", "mins": 60},
  "clean": ["join","leave","pin","title"] (service messages the bot deletes), "report": true (members can report with /report),
  "channel": {"id": "@mychannel" or "-100...", "button": {"text": "label", "url": "https://t.me/..."}, "react": "👍"} (optional; for channels: the bot adds the button under every new post and reacts to it; the owner can also reply to any message in the bot chat with /post to publish it in the channel, or /post 30 to schedule it 30 minutes later)}
- Admin commands inside groups (work for group admins and the bot owner): /ban /unban /kick /mute [minutes] /unmute /warn /unwarn /warns (reply to the user's message), /del, /pin /unpin (reply), /lock <type> /unlock <type> /locks. Everyone: /rules, /report.
- A strong default for an anti-spam manager: captcha on, lock ["link","forward","via_bot"], flood {"n":6,"secs":8}, action "warn", warns {"max":3,"then":"mute","mins":60}, clean ["join","leave"], plus a clear welcome and rules written in the output language. Adapt every value to what the user asked; do not enable what they did not ask for unless it is part of a sensible default for their goal.
- In "thinking" ALWAYS tell the owner: add the bot to the group/channel and make it ADMIN (delete messages, restrict users, pin messages; for channels: post/edit messages), because without admin rights Telegram hides messages from the bot and blocks moderation. Mention that the owner is notified in the bot chat when the bot is added.
- GROUP TRIGGERS (games, points, keyword replies INSIDE a group; use it whenever the user wants the bot to react to words or commands that members write in a group/supergroup, e.g. "when someone sends the word random give them random points", a lucky-draw game, a points/score game, keyword auto-replies, a /top ranking). It works with or without "mod". Config "group": {"triggers": [ {"on": "contains"|"exact"|"starts"|"command", "words": ["رندوم"] (max 10; for "command" write the command without the slash), "reply": "HTML text sent in the group as a reply, supports {name} {points} and any declared variable", "do": [actions], "when": cond (optional), "cooldown": 60 (seconds per member between uses, optional), "to": "replied" (optional: actions and {name} apply to the member whose message was replied to; the sender must reply to someone), "board": {"var": "points", "top": 10, "label": "جدول برترین‌ها"} (optional ranking appended to the reply), "ttl": 30 (delete the bot reply after N seconds, optional), "delete": true (delete the member's trigger message, optional)} ] } (max 20 triggers; only the FIRST matching trigger runs for each message).
  Variables are the normal per-member variables (declare them in "vars"; the same points are shared with the private chat). Random points: {"op": "add", "var": "points", "value": "1-10"} adds a random whole number in that range; "random" + "set" also work. Example: {"on": "exact", "words": ["رندوم"], "do": [{"op":"add","var":"points","value":"1-10"}], "reply": "{name} امتیاز گرفتی! مجموع: {points}", "cooldown": 3600}.
  In "thinking" ALWAYS tell the owner: add the bot to the group and make it ADMIN, otherwise Telegram hides normal messages from the bot (it only sees /commands); alternatively turn off "Group Privacy" for the bot in BotFather. Add a small private-chat start node that explains the game.
- For channels only the button, the reaction and /post publishing exist (Telegram offers no other control over channel posts). Never promise features outside this list, like auto-banning by AI judgement, member exports, or editing old posts.

"config" schema:
{
 "name": "short bot name",
 "start": "<node_id shown on /start>",
 "fallback": "<node_id shown for unknown messages>",
 "commands": {"help": "<node_id>"},
 "join": {"channels": ["channel_username"], "text": "message asking to join"},      (optional, whole bot; prefer per-section/per-button join below)
 "vars": {"coins": "0", "city": ""},                                                 (optional, declare EVERY custom variable with its default value)
 "globals": {"votes_a": "0"},                                                       (optional, variables SHARED by all users, see GLOBALS)
 "desk": {"staff": [123456789], "closed": "text sent when a ticket is closed", "reply_btn": "label"},   (optional, see SUPPORT DESK)
 "mod": {...},                                                                       (optional, group/channel manager, see GROUP & CHANNEL MANAGEMENT)
 "on_ref": [ ...actions... ],                                                        (optional, see REFERRALS)
 "ref_text": "message sent to the inviter",                                          (optional, see REFERRALS)
 "nodes": {
   "<node_id>": {
     "title": "short human label of this section, max 30 chars, OUTPUT LANGUAGE",
     "text": "message text (may contain {placeholders}, see VARIABLES)",
     "media": "<media_id from the MEDIA LIBRARY>",                                 (optional, see MEDIA)
     "photo": "https://direct-image-link",                                          (optional, only if the user gave a link)
     "buttons": [[ {"text": "label", "goto": "<node_id>"},
                   {"text": "label", "url": "https://..."},
                   {"text": "label", "alert": "popup text shown when tapped"},
                   {"text": "label", "copy": "text copied to clipboard when tapped"},
                   {"text": "label", "share": "message sent along with the user's invite link"},
                   {"text": "label", "goto": "<node_id>", "kb": "reply"} ]],      ("kb": "reply" optional on ANY button, see below)
     "ask": false,
     "fields": ["Question 1?", "Question 2?"],                                       (optional, multi-step form)
     "save": ["city", ""],                                                           (optional, see FORMS)
     "types": ["text", "number"],                                                    (optional, see FORMS)
     "silent": false,                                                                (optional, see FORMS)
     "done": "message shown after the user finished ask/form",                      (optional)
     "done_media": "<media_id>",                                                    (optional, sent with the done message)
     "next": "<node_id shown after finishing>",                                      (optional, default start)
     "ai": {"prompt": "instructions for the AI assistant", "daily": 15, "memory": 3},             (optional, see AI CHAT)
     "ticket": true,  "tag": "فروش",                                                 (optional, on ask/fields nodes only, see SUPPORT DESK)
     "board": {"var": "coins", "top": 10, "label": "برترین‌ها"},                       (optional, see LEADERBOARD)
     "list": {"table": "orders", "scope": "my", "limit": 5, "line": "#{n} · {item}"},  (optional, records list, see DATABASE)
     "join": {"channels": ["channel_username"], "text": "message asking to join"},  (optional, forced membership ONLY for this section)
     "do": [ ...actions... ],                                                        (optional, see LOGIC)
     "route": [ {"when": <cond>, "goto": "<node_id>"} ],                             (optional, see LOGIC)
     "alt": [ {"when": <cond>, "text": "..."} ]                                      (optional, see LOGIC)
   }
 }
}

BASIC ENGINE FEATURES
- Buttons: goto a section, open a link, show a popup message (alert), copy text (promo code, card number), share (opens Telegram's share dialog with the user's personal invite link of this bot plus your message).
- "ask": true = the user's next message (ANY type: text, photo, video, voice, file) is forwarded to the bot owner. The owner can answer by replying to it inside the bot chat and the answer reaches the user. Good for simple one-way notes. For anything where the owner must answer users personally, add "ticket": true (see SUPPORT DESK), which gives numbered tickets and a Reply button.
- "fields": a multi-step form. The bot asks each question in order and sends all answers to the owner as one summary (the owner can reply to it too). Use for orders, registration, applications, surveys. Node "text" is the intro, fields are the questions. Use "done" for the thank-you message.
- "join": force membership of public channels (usernames without @). Only if the user asks for forced/mandatory join. Put it on the specific node (the section the user must unlock) or on a goto/alert/pay button ({"text": "...", "goto": "vip", "join": {"channels": ["x"], "text": "..."}}) so only that part is locked; use the top-level "join" only when the user wants the WHOLE bot locked. In "thinking" remind that the bot must be admin in that channel.
- "kb": "reply" on a BUTTON = that button is shown in the keyboard under the chat input box instead of a glass button under the message. Each button chooses by itself, so one section can have both kinds (glass buttons under the message + a main-menu keyboard under the chat). Only if the user asks for a keyboard under the chat / a main-menu keyboard. Never on sections with "ask", "fields" or "ai". Link/popup/copy/share buttons still work inside it.
- "photo": only if the user gave an image link. Never invent image URLs.

MEDIA
- The request may contain a MEDIA LIBRARY: files the user uploaded, each with id, kind (photo, video, animation, audio, voice, document) and name. Attach them with "media": "<id>" on a node (shown above/with the node text; node text becomes the caption) or "done_media" (sent with the thank-you message).
- Use ONLY ids that appear in the library, exactly as written. Never invent ids. Match files to sections by their name and by what the user said (logo/banner on the start page, a catalog PDF on the products page, a voice greeting on the welcome page).
- If the user asks for media but the library has none (or none fits), build the bot without it and say in "thinking" that they can upload files in the media tab and then ask you to attach them.
- A node has at most one media item. For several files make several sections.

AI CHAT (powerful, costs tokens, use deliberately)
- "ai": {"prompt": "...", "daily": 15} turns the section into a live conversation: after the section text is shown, every message the user writes is answered by an AI assistant that follows "prompt". "daily" = max AI messages per user per day (1-100, default 15). "memory" = how many previous exchanges the assistant remembers (0-6, default 3).
- Use it when the user wants a smart assistant, consultant, tutor, translator, writer, fortune-teller, character, support agent that answers free-form questions, or anything where fixed menus cannot work. NEVER use it for plain menus or fixed information.
- "prompt" is written in the bot's language as instructions TO the assistant: its role and name, tone, what it may and may not do, and every real fact the user gave (prices, hours, products, rules). Max 1500 characters. If it should sell or support a business, include that business's facts and say "if you don't know, say so and offer the contact button". Never invent facts.
- The section text is the greeting. ALWAYS add a back/home button so users can leave the conversation (the buttons are shown under every AI answer).
- Not combinable with "ask", "fields" or buttons with "kb": "reply" in the same section.
- A bot can combine normal sections with one or several AI sections (e.g. a shop menu plus an "ask the expert" AI section).

REFERRALS
- Every user has {ref_link}, a personal invite link of this bot, and {refs}, the number of people who joined through it. Link looks like t.me/bot?start=ref_<id>.
- "on_ref": actions that run for the INVITER when a new person starts the bot via the inviter's link, e.g. [{"op":"add","var":"coins","value":"5"}]. "ref_text": message sent to the inviter then (may use their variables like {coins}).
- Typical invite system: a "share" button, a section showing "{refs}" invites and "{coins}" coins, on_ref adding coins. Use only if the user wants invites/rewards/viral growth.

VARIABLES (this is what makes a bot feel professional)
- Custom variables are stored PER USER (each Telegram user has their own values). Name: lowercase english letters/digits/underscore, starts with a letter, max 20 chars, max 40 variables per bot. Declare each one in config.vars with a default string ("0" for counters, "" for text). Values are strings; math and numeric comparison work when they look like numbers.
- Use {var} in node texts, button labels, alert/copy/share text, form questions, "done", notify texts, ai prompts and condition values. {var|fallback} prints fallback when the value is empty, e.g. {city|ثبت نشده}. Every variable you put in a {placeholder} MUST be declared in config.vars (built-ins excepted).
- Built-in read-only variables (always available in texts AND conditions):
  {name} first name (falls back to "دوست من"), {first_name}, {last_name}, {full_name}, {username} (with @, empty if none), {id} Telegram user id, {lang} Telegram language code like fa / en, {premium} "1" if the user has Telegram Premium else "0", {is_owner} "1" if the user is the bot owner else "0", {bot_name}, {bot_username}, {text} the last text message the user sent, {param} the payload of /start (deep link t.me/bot?start=xxx), {visits} how many times this user pressed /start (1 on the first time), {refs} number of successful invites of this user, {ref_link} this user's invite link, {date} today's Jalali date like 1405/07/11, {time} HH:MM Tehran time, {hour} 0-23 Tehran, {weekday} Persian weekday name.

CONDITIONS ("cond" object)
- {"var": "coins", "op": ">=", "value": "10"}. op is one of: == != > >= < <= contains empty filled ("empty"/"filled" take no value). "var" is a custom or built-in variable. "value" may contain {placeholders}. Numbers compare numerically, text compares case-insensitively.
- Combine with {"all": [cond, cond]} (AND), {"any": [cond, cond]} (OR), {"not": cond}. Max 3 levels deep.

ACTIONS ("action" object, max 6 per list)
- {"op": "set", "var": "city", "value": "تهران"}            store a value (value may use {placeholders})
- {"op": "add", "var": "coins", "value": "5"}               add a number; negative to subtract ("-3"); default 1
- {"op": "clear", "var": "city"}                            back to the default
- {"op": "random", "var": "dice", "value": "1-6"}           random whole number in a range
- {"op": "notify", "value": "text"}                         sends a message to the bot owner (may use {placeholders}; the user's name and id are appended; the owner can reply to it)
- {"op": "remind", "minutes": 60, "value": "text", "goto": "<node_id>", "key": "cart"}   schedule a message for later, see REMINDERS
- {"op": "dice", "var": "roll", "emoji": "🎲"}              animated Telegram dice; the REAL result lands in the variable after the animation. emoji one of 🎲 🎯 🏀 ⚽ 🎳 (1-6) or 🎰 (1-64). see GAMES
- {"op": "pick", "var": "prize", "value": "gold|silver|bronze"}   draws one option at random into the variable. see GAMES
- {"op": "db_add", "table": "orders", "data": {...}, "scope": "my"}   append a permanent record, see DATABASE
- {"op": "db_get", "table": "orders", "when": {...}, "var": "o"}     load matching record(s) into variables, see DATABASE
- {"op": "db_set", "table": "orders", "when": {...}, "data": {...}}  update matching record(s), see DATABASE
- {"op": "db_inc", "table": "orders", "var": "plays", "value": "1"}  increment a numeric field of the latest record, see DATABASE
- {"op": "db_del", "table": "orders", "when": {...}}        delete matching record(s), see DATABASE
- {"op": "fetch", "var": "rate", "url": "https://...", "pick": "usd.price"}   GET a public https API and store part of the JSON in a variable, see EXTERNAL API@@APION@@

GAMES (interactive games — the engine has real building blocks for them)
- {"op": "dice"} sends an ANIMATED Telegram dice/casino animation, waits for it to finish, and stores the genuine Telegram result in "var" (user cannot cheat it). Use for board-game moves, lucky draws, betting with coins, "roll to win" shops.
- {"op": "pick"} picks one of the |-separated options at random (loot boxes, fortune telling, random name/reward/task/prize).
- Combine with variables, "add" for scores/coins/health, "route"/"alt" for rules ("roll >= 5 wins"), pay buttons for entry fees, globals for shared jackpots, "board" for rankings, db tables for game history/leagues. A typical turn: one node whose button "do" has dice/add actions, then "goto" a result node whose "route" compares the roll and branches to win/lose nodes.
- Example lucky-draw button: {"text": "بچرخون", "goto": "result", "do": [{"op":"add","var":"coins","value":"-5"},{"op":"dice","var":"roll","emoji":"🎰"},{"op":"add","var":"spins","value":"1"}]}
- Example result node: {"title": "نتیجه", "text": "عددت: {roll}", "route": [{"when": {"var":"roll","op":">=","value":"40"}, "goto": "jackpot"}, {"when": {"var":"coins","op":"<","value":"5"}, "goto": "broke"}]}
- Quiz/trivia is built with buttons + "add" score + route (no dice needed). For real-time two-player games or timed competitions say honestly in "thinking" that Telegram bots cannot do them and build the closest single-player version.

DATABASE (a real permanent data store per bot — for lists, records, archives that must survive and grow)
- Actions "db_add"/"db_get"/"db_set"/"db_inc"/"db_del" work on named tables ("table": lowercase id). "data" = {"field": "value"} with value supporting {placeholders} (e.g. store form answers). Field names: english lowercase like variable names.
- "scope": "my" (default) = each user only sees/edits their OWN records (order history, my scores). "scope": "all" = one shared collection for everyone (public wall, shared archive, league history); use deliberately.
- {"op": "db_add", "table": "notes", "data": {"text": "{text}", "cat": "public"}, "scope": "all"} — appends record #N (numbered automatically).
- {"op": "db_get", "table": "orders", "when": {"var": "status", "op": "==", "value": "paid"}, "var": "o"} — loads the LATEST matching record; every field f of the table becomes variable "o_f" ({"var": "o"} → {o_text}, {o_cat}; empty prefix → the field name itself). "when" is a simple condition on record fields, optional.
- {"op": "db_set", "table": "orders", "when": {"var": "status", "op": "==", "value": "new"}, "data": {"status": "shipped"}} — updates ALL matching records. WITHOUT "when" and with scope "my" it updates the user's own records only.
- {"op": "db_inc", "table": "scores", "var": "wins", "value": "1", "upsert": true} — adds a number to field "var" of the user's latest record; "upsert": true creates the record on first use.
- {"op": "db_del", "table": "carts", "when": {...}} — deletes matching records.
- To SHOW records to users add to a node: "list": {"table": "notes", "scope": "all", "limit": 5, "line": "#{n} · {text}", "empty": "هنوز چیزی ثبت نشده.", "order": "new"}. It appends the rendered lines under the node text. In "line": {n} = record number, {u} = creator's telegram id, {field} = any field. limit 1-10, order "new" (newest first, default) or "old".
- Typical uses: order history (form saves → db_add → "my orders" list node), suggestion wall / guestbook (ask node → db_add scope all → list node), game history & leagues (db_add per match → db_inc wins → board), library/catalog of user-submitted content, appointment log. Max 6 tables, 12 fields per record. Do NOT use db tables for simple counters — a variable or global is lighter.

EXTERNAL API (connect the bot to outside services; costs a moment, use deliberately)@@APION@@
- {"op": "fetch", "var": "price", "url": "https://api.example.com/rate.json", "pick": "data.usd"} — the engine GETs the URL (must be a public https link, no auth headers) and stores JSON path "pick" into the variable ("a.b.0.c" walks objects/arrays; non-string leaves are stringified). Then use {price} in texts, alt, route.
- Use for exchange rates, coin prices, weather, quotes, sports results, hijri/shamsi date APIs — anything with a public JSON endpoint. Never invent URLs: use the well-known public endpoint the user gave; if they gave none, use https://api.example.com/... as an obvious placeholder and say so in "thinking".
- Each bot is limited per day; on failure the variable keeps its old value. Put fetch in node "do" of the page that shows the value, then show {price} in the text or an "alt".@@APIOFF@@

WHERE LOGIC GOES
- node "do": [actions] runs every time a user enters the node, before anything is shown.
- node "route": [{"when": cond, "goto": "<node_id>"}] (max 5). After "do", the FIRST rule whose condition is true sends the user to that node instead (like a switch). Use for gates, level-ups, opening hours, owner-only menus, first visit vs returning user. Because the node's own text is then skipped, still write a sensible text. Chains are followed up to 5 hops; never create loops.
- node "alt": [{"when": cond, "text": "..."}] (max 4). The first true condition replaces the node's text (buttons stay). Use for personalised messages ("you have {coins} coins").
- button "when": cond. The button is only shown to users for whom it is true (admin button, premium-only, hide "buy" when coins are not enough).
- button "do": [actions]. Only on goto and alert buttons. Runs when the button is tapped, before the goto/alert. Alert text is evaluated AFTER the actions, so a "my balance" alert shows fresh numbers.
- FORMS: "save": ["city", ""] has the same length as "fields" and stores each answer in that variable ("" = don't store). "types": ["text","number","phone","email"] (same length) validates each answer; the engine re-asks until valid and normalises digits to english. "silent": true = don't send the finished form to the owner (default: it is sent). Later questions and texts can use earlier answers, e.g. "{city} درسته؟".

WHEN TO USE LOGIC
- Use variables/conditions when they make the bot genuinely better: points/coins/loyalty, quizzes and scoring, bots that remember answers and reuse them, personalised greetings (first visit vs returning via {visits}), opening hours via {hour}/{weekday}, an owner-only admin menu via {is_owner}, language-aware replies via {lang}, campaign tracking via {param}, invites via {refs}, premium-only perks via {premium}.
- Do NOT add logic when a plain menu is enough. A simple request deserves a simple, clean bot.
- Small examples of the constructs (not a full bot):
  "vars": {"score": "0"}
  {"text": "تهران", "goto": "q2", "do": [{"op": "add", "var": "score", "value": "1"}]}
  {"title": "نتیجه", "text": "تموم شد.", "route": [{"when": {"var": "score", "op": ">=", "value": "3"}, "goto": "win"}]}
  {"text": "پنل مدیر", "goto": "admin", "when": {"var": "is_owner", "op": "==", "value": "1"}}
  {"text": "سلام {name}", "alt": [{"when": {"var": "visits", "op": ">", "value": "1"}, "text": "خوش برگشتی {name}"}]}
  {"title": "دستیار", "text": "هر سوالی داری بپرس.", "ai": {"prompt": "تو دستیار فروشگاه ... هستی. ...", "daily": 15}, "buttons": [[{"text": "بازگشت", "goto": "home"}]]}

SUPPORT DESK (tickets with a Reply button; use it for every support, contact, complaint, feedback, ticket, order-with-receipt flow, or any request where the owner must answer users personally)
- Add "ticket": true to a node that has "ask": true or "fields". Every message or finished form becomes a numbered ticket (#1, #2, ...). The owner (and optional staff) receive it inside the bot chat with buttons under it: Reply, History, Close ticket, Block user. Tapping Reply puts them in reply mode: the next message they send (text, photo, voice, file) is delivered to the user. Under that answer the user gets a "reply to support" button, so the conversation continues inside the same ticket. The owner can also list open tickets with /tickets.
- Optional "tag" (max 20 chars) is shown on the ticket. For departments make one ask node per department with its own tag, e.g. "فروش", "فنی", "پرداخت".
- {ticket_no} is the number of the user's latest ticket. Use it in "done", e.g. "پیامت ثبت شد (تیکت #{ticket_no}). به‌زودی جواب می‌دیم." If "done" is missing a good default is used.
- Config "desk": {"staff": [numeric telegram ids], "closed": "text sent to the user when a ticket is closed", "reply_btn": "label of the user's reply button"}. Add "staff" ONLY with numeric ids the user gave; never invent ids. Otherwise just mention in "thinking" that extra support staff ids can be added with manual edit (the owner always receives tickets).
- Always prefer "ticket": true over plain "ask" when a human answers. A ticket form ("fields") is the best way to take orders, bookings, applications and complaints: the owner gets one clean message and can reply to the customer right there.
- A good support bot: FAQ sections for common questions, a "contact support" ask node with ticket, a cancel button, and optionally an AI section for free questions. In "thinking" tell the owner they will see tickets in the bot chat with a Reply button and can use /tickets.

GLOBALS (data shared by ALL users)
- config "globals": {"votes_a": "0", "stock": "20"} declares variables that exist once per bot and are shared by every user: counters, polls, limited stock, raffle entries, community goals. Use them exactly like normal variables in texts ({votes_a}), conditions and actions (add/set/clear). "add" on a global is atomic, so simultaneous users are counted correctly.
- Never list the same name in "vars" too. Max 20 globals.
- Poll: buttons with "do": [{"op":"add","var":"votes_a","value":"1"}] plus a results node that shows {votes_a}. One vote per user: a normal variable "voted" set to "1" by the vote buttons, and the vote buttons get "when": voted == 0.
- Limited stock: global "stock" starts at the real number; the buy button has "when": stock > 0 and "do" add -1; show {stock} left.
- Community goal: show "{total} از ۱۰۰۰" and add to it from a button or form completion node.

LEADERBOARD
- node "board": {"var": "coins", "top": 10, "label": "برترین‌ها"} appends a ranking (name — value) and the viewer's own rank under the node text. "var" is a normal numeric per-user variable that some action increases, or the built-in "refs" (top inviters). top is 3-20. Use it for contests, points, quizzes, referral competitions.

REMINDERS AND FOLLOW-UPS
- Action {"op": "remind", "minutes": 60, "value": "text", "goto": "<node_id>", "key": "cart"} schedules something for later: after N minutes (1-43200 = up to 30 days) the bot sends "value" to the same user and, if "goto" is set, shows that node (its "do" actions run, so a node can expire a perk). "key" prevents duplicates while one is waiting. Max 5 waiting per user. {placeholders} in "value" are filled when scheduled.
- Use for: follow-up after an order or form, "complete your registration" nudges, appointment reminders, trial-end offers, daily-habit nudges, and subscription expiry (pay button "do" sets vip=1 and remind 43200 minutes with goto an "expired" node whose "do" clears vip).
@@PAY@@
MULTI-LANGUAGE BOTS (only when the user wants the bot in several languages)
- Declare a variable "ui" (default ""). The START node is the language picker: one goto button per language, each with "do": [{"op":"set","var":"ui","value":"en"}] that goes to that language's home, plus "route": [{"when": {"var":"ui","op":"==","value":"fa"}, "goto":"home"}, {"when": {"var":"ui","op":"==","value":"en"}, "goto":"en_home"}] so returning users skip the picker.
- Build a separate copy of the sections for every language (ids like home, menu / en_home, en_menu); every goto, next and route stays inside its own language branch. Form questions, "done" texts and alerts cannot switch language by themselves, so they live in the per-language copies.
- Add a language button in every home that goes to a node whose "do" is [{"op":"clear","var":"ui"}] and which shows the same picker as the start node (a /lang command can point to it).
- For AI sections write one prompt per language branch (or tell the assistant to answer in the user's language). Max 60 nodes in total, so keep each language branch compact.
- {lang} is only Telegram's language code; an explicit picker is better.

PATTERNS (pick what fits, combine freely)
- Shop/catalog: home, categories, product pages with media, order form with ticket (owner replies to the customer inside the ticket), order history with db_add + a "list" node, contact. Store/service business: services, prices (placeholders if unknown), booking form with ticket, location, support.
- Support/helpdesk: FAQ sections, contact node with "ticket": true (departments via tags), optional AI assistant for free questions, closing message in desk.closed.
- Content/channel promoter: welcome with media, forced join, latest content links, share button.
- Games: dice/pick actions for luck, variables + route/alt for rules and scores, coins economy with "add" and pay buttons for entry fees, globals for a shared jackpot, db tables for match history/leagues, a "board" for rankings.
- Quiz/trivia/loyalty/contest: variables + route + alt, scores, levels, daily-style rewards via {date}, a "board" for the ranking, globals for community goals.
- Community/viral: invites with {refs}, {ref_link}, on_ref rewards, a "board" on "refs" for top inviters; suggestion wall or guestbook with db_add scope "all" + a "list" node.
- AI products: assistant, tutor, translator, writer, consultant, character chat: AI section(s) with a strong prompt plus a small menu around it.
- Sales funnel: lead form with ticket, remind-based follow-up, offers; owner replies personally.
- Polls, votes, raffles, limited-stock drops: globals + per-user guard variable.
- Live data (rates, weather, coin prices, quotes): fetch action in node "do" + the variable shown in text/alt.

ENGINE LIMITS (be honest about them in "thinking" and build the closest working approximation)
- CANNOT do: card or bank-gateway payments @@PAYLIM@@, reading the CONTENT of files or photos users send (they can be forwarded to the owner), managing groups/channels beyond the mod toolkit and group triggers, inline mode, calls, real-time two-player games.
- CAN do: permanent record storage (db tables + list), public JSON APIs (fetch), luck games (dice/pick), shared counters (globals), rankings (board), delayed messages and expiry (remind), human support (ticket), subscriptions and paid access (pay + vip flag + remind)@@DBMAP@@.
- Example approximation: an order form with ticket (the owner sees the order and replies to the customer with the payment instructions) instead of an online checkout; a dice+coins single-player game instead of a real-time multiplayer game.

REASONING PROTOCOL (think through this silently before you write the JSON)
1. Actors: end user, owner, optional staff. What does each of them need from this bot?
2. List every requirement the user stated, then add what a professional would add without being asked: a way back, a way to reach a human, an owner notification, confirmation messages, clear errors.
3. Map each requirement to the engine feature that implements it: ticket for human answers, forms+types for data, vars/route/alt/when for logic, db tables for records/history, dice/pick for games, fetch for live data, globals for shared counters, board for rankings, remind for follow-ups, ai for free-form questions@@PAYMAP@@.
4. If something is impossible, pick the closest honest approximation and say so in "thinking".
5. Verify before answering: every goto/next/route/remind/pay target exists; every {placeholder} is declared; every ask/form/ticket node has a cancel or home button; texts are in the output language; no invented facts; the JSON is valid and complete.

Design rules:
- Think before you structure: identify the bot's real purpose, the natural user journeys, and the minimum set of nodes that cover them well. Don't pad with filler, but don't skip an obviously needed part (a shop bot needs a way to order, a business bot needs contact/support).
- node_id: lowercase english letters, digits, underscore. Max 60 nodes, max 3 buttons per row, max 6 rows per node.
- A button has exactly one of: "goto" (an existing node_id), "url" (https only), "alert", "copy", "share".
- Channel/group join button: {"text": "عضویت در کانال", "url": "https://t.me/<username>"} (username without @). Use the username the user gave. If they gave none, use https://t.me/your_channel and say in "thinking" that the real channel id must be set via manual edit.
- Always give every node a short "title". Prefer a form ("fields") over a single "ask" when you need several pieces of info. Give ask/form/ai nodes a cancel/home button too.
- Every "goto", "start", "fallback", "next", route target and command target MUST exist in nodes. Every node must be reachable from start; no dead ends: every non-start node has a back/home button (or a "next"/"route").
- Button labels short (max ~22 chars). At most 2 buttons in a row when labels are long.
- Never invent real-world facts (prices, phone numbers, addresses, links). Use obvious placeholders such as [قیمت] or [شماره تماس] and mention it in "thinking".
- Write all user-facing text in the OUTPUT LANGUAGE.
- When an existing config is given, apply the user's change precisely and return the FULL updated config. Keep every untouched node, text, media, button, variable and rule exactly as it was (the user may have edited them by hand).
- Node texts, form questions, "done" texts and reminder texts support Telegram HTML: <b>bold</b>, <i>italic</i>, <u>underline</u>, <s>strike</s>, <code>copyable code</code>, <blockquote>highlighted quote</blockquote>, <tg-spoiler>spoiler</tg-spoiler> and links <a href="https://...">text</a>. Use it so the bot looks professional: a bold first line as the heading, a blockquote for key info or benefits, <code> for codes and numbers the user may copy, a few well-chosen emoji. Close every tag. Never use Markdown (** or #). Write a literal < > & as &lt; &gt; &amp;. Escape the double quotes of attributes inside the JSON. Button labels, alert/copy/share texts and AI prompts stay plain text (no tags). The owner may have put premium emoji tags <tg-emoji emoji-id=\"123\">🙂</tg-emoji> inside texts and optional \"style\" (primary/success/danger) and \"icon\" (digits) keys on buttons: when editing an existing config keep them exactly as they are, and never invent new ones."""
SYSTEM_PROMPT = (_SP_BASE.replace("@@PAY@@", ("\n" + """
PAYMENTS (Telegram Stars)
- A button can take payment in Telegram Stars (digital goods, VIP access, paid content, tips, donations, credits inside the bot): {"text": "خرید اشتراک", "pay": {"stars": 50, "title": "اشتراک ویژه", "desc": "دسترسی یک‌ماهه", "text": "پرداخت انجام شد، ممنون!", "goto": "vip_home"}, "do": [{"op": "set", "var": "vip", "value": "1"}]}
- "stars": whole number 1-10000. "do" runs ONLY after the payment succeeded (set a vip flag, add credits...). "text" is shown after success, "goto" is the node shown next. A pay button has no goto/url of its own. Use "when" on content and buttons so only paid users see them. Each product or plan is one pay button.
- Use the price the user gave; if none, use a placeholder number and say so in "thinking". In "thinking" mention that Stars go to the owner's Telegram balance, that the owner sees every payment in the bot chat, can list them with /payments and refund with /refund CODE, and that users reach payment support with /paysupport.
- Do not use pay buttons for physical goods; for those use an order form with ticket.
""") if PAYMENTS else "")
                 .replace("@@PAYLIM@@", "(only Telegram Stars)" if PAYMENTS else "of any kind")
                 .replace("@@PAYMAP@@", ", pay for Telegram Stars payments" if PAYMENTS else "")
                 .replace("@@DBMAP@@", ""))

# رجیستری قابلیت‌ها به دستورالعمل چسبانده می‌شود تا AI فقط قابلیت‌های واقعی موتور را بسازد
import caps as _caps_mod
SYSTEM_PROMPT += "\n\nCAPABILITIES REGISTRY (single source of truth — build ONLY with these):\n" + _caps_mod.caps_ai_text()
EXT_API = os.environ.get("EXT_API", "1").strip() != "0"     # اکشن fetch (اتصال به API بیرونی)؛ ۰ = خاموش
EXT_API_DAILY = _int("EXT_API_DAILY", 200)                  # سقف روزانه‌ی fetch هر ربات
if EXT_API:
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("@@APION@@", "").replace("@@APIOFF@@", "")
else:
    # سرویس خاموشه: خطِ اکشن fetch و کل بخش EXTERNAL API از دستورالعمل حذف می‌شه
    SYSTEM_PROMPT = re.sub(r"\nEXTERNAL API \(.*?@@APIOFF@@", "",
                           "\n".join(l for l in SYSTEM_PROMPT.splitlines() if "see EXTERNAL API" not in l), flags=re.S)


ID_RE = re.compile(r"^[a-z0-9_]{1,30}$")
CMD_RE = re.compile(r"^[a-z0-9_]{1,30}$")
TG_NAME_RE = re.compile(r"^@?[A-Za-z][A-Za-z0-9_]{4,31}$")


# ───────────────────────── متغیرها، شرط‌ها و اکشن‌ها ─────────────────────────
VAR_RE = re.compile(r"^[a-z][a-z0-9_]{0,19}$")
PH_RE = re.compile(r"\{([a-z][a-z0-9_]{0,19})(?:\|([^{}]{0,60}))?\}")
MAX_VARS = 40
MAX_HOPS = 5
# متغیرهای آماده‌ی تلگرام (فقط‌خواندنی)
BUILTINS = ("name", "first_name", "last_name", "full_name", "username", "id", "lang", "premium", "is_owner",
            "bot_name", "bot_username", "text", "param", "visits", "refs", "ref_link", "date", "time", "hour", "weekday", "ticket_no")
OPS = ("==", "!=", ">", ">=", "<", "<=", "contains", "empty", "filled", "sub")
OP_ALIASES = {"=": "==", "eq": "==", "ne": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
ACT_OPS = ("set", "add", "clear", "random", "notify", "remind",
           "dice", "pick", "db_add", "db_get", "db_set", "db_inc", "db_del", "fetch", "game_play",
           "calc", "disc", "sub_add", "sub_del")
F_TYPES = ("text", "number", "phone", "email")


# ───────────────────────── جدول داده‌ی رکوردی، اعتبارسنج و بازرس کانفیگ ─────────────────────────
TAB_RE = re.compile(r"^[a-z][a-z0-9_]{0,15}$")
DICE_EMOJIS = {"🎲": 6, "🎯": 6, "🏀": 5, "⚽": 5, "🎳": 6, "🎰": 64}   # سقف عدد هر تاس تلگرام
REC_BUILTINS = ("n", "u")      # فیلدهای آماده‌ی رکورد: شماره‌ی ردیف و آیدی صاحبش
MAX_TABLES = 6                 # حداکثر جدول داده‌ی هر ربات
MAX_REC_FIELDS = 12            # حداکثر فیلد هر رکورد
MAX_REC_VAL = 200              # سقف طول هر مقدار
MAX_RECORDS_USER = 100         # حداکثر رکورد هر کاربر در هر جدول
MAX_RECORDS_SHARED = 500       # حداکثر رکورد مشترک هر جدول
_PRIV_HOST = re.compile(r"^(localhost|.*\.local|.*\.internal|127\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.|0\.|::1)")


def norm_url(v):
    """@channel / t.me/x / https://... → https URL معتبر (یا None)"""
    v = str(v or "").strip()
    if TG_NAME_RE.match(v):
        return "https://t.me/" + v.lstrip("@")
    if re.match(r"^(t\.me|telegram\.me)/", v, re.I):
        v = "https://" + v
    if v.startswith("https://") and len(v) > 12 and not re.search(r"\s", v):
        return v[:500]
    return None


def to_num(s):
    """رشته → عدد (ارقام فارسی/عربی هم قبول)؛ نامعتبر = None"""
    try:
        x = float(str(s).translate(_DIG).replace(",", "").replace("٫", ".").strip())
    except (ValueError, TypeError):
        return None
    return x if math.isfinite(x) else None


def fmt_num(x):
    x = max(-1e12, min(1e12, x))
    return str(int(x)) if x == int(x) else ("%.6f" % x).rstrip("0").rstrip(".")


# ───────────────────────── ارزیاب امنِ عبارت حسابی (بدون eval) ─────────────────────────
_CALC_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)


def safe_calc(expr):
    """عبارت حسابی امن: فقط عدد، + - * / // % ** و پرانتز (بدون eval و بدون نام و تابع). خطا/حمله = None"""
    def ev(n, d):
        if d > 24:
            return None
        if isinstance(n, ast.Expression):
            return ev(n.body, d + 1)
        if isinstance(n, ast.Constant):
            return n.value if isinstance(n.value, (int, float)) and not isinstance(n.value, bool) else None
        if isinstance(n, ast.BinOp) and type(n.op) in _CALC_OPS:
            x, y = ev(n.left, d + 1), ev(n.right, d + 1)
            if x is None or y is None:
                return None
            try:
                if type(n.op) in (ast.Div, ast.FloorDiv, ast.Mod) and y == 0:
                    return None
                if type(n.op) is ast.Pow and abs(y) > 64:
                    return None
                if type(n.op) is ast.Add:
                    v = x + y
                elif type(n.op) is ast.Sub:
                    v = x - y
                elif type(n.op) is ast.Mult:
                    v = x * y
                elif type(n.op) is ast.Div:
                    v = x / y
                elif type(n.op) is ast.FloorDiv:
                    v = x // y
                elif type(n.op) is ast.Mod:
                    v = x % y
                else:
                    v = x ** y
            except (OverflowError, ZeroDivisionError, ValueError):
                return None
            return v if math.isfinite(v) else None
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            x = ev(n.operand, d + 1)
            if x is None:
                return None
            return -x if isinstance(n.op, ast.USub) else x
        return None

    try:
        tree = ast.parse(str(expr or "").strip(), mode="eval")
    except (SyntaxError, ValueError, RecursionError):
        return None
    v = ev(tree, 0)
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer() and abs(v) <= 1e15:
        v = int(v)
    return fmt_num(v)


def clean_cond(c, used, nums, bad, depth=0):
    """شرط رو پاک‌سازی می‌کنه؛ نامعتبر = None"""
    if not isinstance(c, dict) or depth > 3:
        bad("یکی از شرط‌ها ساختار معتبری نداره")
        return None
    for key in ("all", "any"):
        if isinstance(c.get(key), list):
            subs = [x for x in (clean_cond(s, used, nums, bad, depth + 1) for s in c[key][:6]) if x]
            return {key: subs} if subs else None
    if "not" in c:
        s = clean_cond(c["not"], used, nums, bad, depth + 1)
        return {"not": s} if s else None
    name = str(c.get("var") or "").strip().lower()
    op = str(c.get("op") or "==").strip()
    op = OP_ALIASES.get(op, op)
    if op == "sub":                      # شرط اشتراک دوره: پلن لازم است، متغیر نه
        return {"op": "sub", "plan": re.sub(r"[^a-z0-9_]", "", str(c.get("plan") or "").lower())[:16]}
    if not (name in BUILTINS or VAR_RE.match(name)):
        bad(f"نام متغیر «{name}» در شرط معتبر نیست (حروف انگلیسی کوچک، عدد و _)")
        return None
    if op not in OPS:
        bad(f"عملگر شرط «{op}» معتبر نیست")
        return None
    if name not in BUILTINS:
        used.add(name)
        if op in (">", ">=", "<", "<="):
            nums.add(name)
    out = {"var": name, "op": op}
    if op not in ("empty", "filled"):
        out["value"] = str(c.get("value", ""))[:100]
    return out


def _reg_tab(tables, tab, fields):
    """ثبت جدول و فیلدهایش (برای سقف تعداد جدول‌ها و متغیرهای db_get)"""
    fs = tables["tabs"].setdefault(tab, set())
    fs.update(f for f in fields if VAR_RE.match(f) and f not in BUILTINS)


def clean_rec_cond(c, bad):
    """شرط ساده روی فیلدهای رکورد (when برای db_* و list)؛ نامعتبر = None"""
    if c is None:
        return None
    if not isinstance(c, dict) or c.get("all") or c.get("any") or c.get("not"):
        bad("شرطِ جدول داده باید یه شرط ساده باشه (فیلد، عملگر، مقدار)")
        return None
    f = str(c.get("var") or "").strip().lower()
    op = str(c.get("op") or "==").strip()
    op = OP_ALIASES.get(op, op)
    if op == "sub":
        bad("شرط «اشتراک دوره» فقط در «وقتی/اگه» جریان کار می‌کنه، نه در شرط جدول")
        return None
    if not (VAR_RE.match(f) or f in REC_BUILTINS):
        bad(f"نام فیلد «{f}» در شرط جدول داده معتبر نیست")
        return None
    if op not in OPS:
        bad(f"عملگر شرط «{op}» معتبر نیست")
        return None
    out = {"var": f, "op": op}
    if op not in ("empty", "filled"):
        out["value"] = str(c.get("value", ""))[:100]
    return out


def _clean_new_action(op, a, used, nums, bad, tables):
    """اکشن‌های بازی و پایگاه داده‌ی رکوردی (dice / pick / fetch / db_*)؛ نامعتبر = None"""
    def var_of():
        name = str(a.get("var") or "").strip().lower()
        if not VAR_RE.match(name) or name in BUILTINS:
            bad(f"نام متغیر «{name}» برای اکشن معتبر نیست (حروف انگلیسی کوچک، عدد و _ و نباید اسم متغیرهای آماده باشه)")
            return None
        return name
    if op == "dice":
        name = var_of()
        if not name:
            return None
        em = str(a.get("emoji") or "🎲").strip()
        if em not in DICE_EMOJIS:
            bad("ایموجی تاس باید یکی از 🎲 🎯 🏀 ⚽ 🎳 🎰 باشه")
            return None
        used.add(name)
        nums.add(name)
        return {"op": "dice", "var": name, "emoji": em}
    if op == "pick":
        name = var_of()
        if not name:
            return None
        v = str(a.get("value") or "").strip()[:300]
        if len([x for x in v.split("|") if x.strip()]) < 2:
            bad("گزینه‌های انتخاب تصادفی رو با | از هم جدا کن (حداقل دو گزینه)")
            return None
        used.add(name)
        return {"op": "pick", "var": name, "value": v}
    if op == "game_play":
        # شروع یکی از بازی‌های آماده (مرکز بازی)؛ فقط بازی‌های موجود در رجیستری
        import caps as _caps_mod
        gids = {g["k"] for g in _caps_mod.CAPS_GAMES}
        gm = str(a.get("game") or "").strip().lower()
        if gm not in gids:
            bad("بازی «%s» وجود نداره؛ بازی‌های موجود: %s" % (gm or "؟", "، ".join(sorted(gids))))
            return None
        return {"op": "game_play", "game": gm}
    if op == "fetch":
        if not EXT_API:
            bad("اتصال به API بیرونی در این سرویس فعال نیست")
            return None
        name = var_of()
        if not name:
            return None
        u = str(a.get("url") or "").strip()[:500]
        host = ""
        try:
            host = (urlparse(u).hostname or "").lower()
        except Exception:
            host = ""
        if not u.startswith("https://") or not host or ":" in host or _PRIV_HOST.match(host):
            bad("آدرس fetch باید یه لینک https عمومی باشه (نه آدرس داخلی)")
            return None
        used.add(name)
        it = {"op": "fetch", "var": name, "url": u}
        pk = re.sub(r"[^A-Za-z0-9_.\-]", "", str(a.get("pick") or ""))[:80]
        if pk:
            it["pick"] = pk
        return it
    # ── اکشن‌های جدول داده ──
    tab = str(a.get("table") or "").strip().lower()
    if not TAB_RE.match(tab):
        bad(f"نام جدول «{tab}» معتبر نیست (حروف انگلیسی کوچک، عدد و _)")
        return None
    if tab not in tables["tabs"] and len(tables["tabs"]) >= MAX_TABLES:
        bad(f"حداکثر {MAX_TABLES} جدول داده می‌تونی داشته باشی")
        return None
    scope = "all" if a.get("scope") in ("all", "shared", True) else "my"
    when = clean_rec_cond(a.get("when"), bad)
    it = {"op": op, "table": tab}
    if scope == "all":
        it["scope"] = "all"
    if when:
        it["when"] = when
    if op == "db_get":
        pfx = str(a.get("var") or "").strip().lower()
        if pfx and (not VAR_RE.match(pfx) or pfx in BUILTINS):
            bad(f"پیشوند متغیر «{pfx}» برای خواندن جدول معتبر نیست")
            return None
        if pfx:
            it["var"] = pfx
        tables["gets"].append((pfx, tab))
        _reg_tab(tables, tab, [])
        return it
    if op == "db_del":
        _reg_tab(tables, tab, [])
        return it
    if op == "db_inc":
        k = str(a.get("var") or a.get("field") or "").strip().lower()
        if not VAR_RE.match(k) or k in BUILTINS:
            bad(f"نام فیلد عددی «{k}» معتبر نیست")
            return None
        v = (str(a.get("value", a.get("by", "1"))).strip()[:100]) or "1"
        if v != "1" and to_num(v) is None and not PH_RE.search(v):
            bad(f"مقدار افزایش فیلد «{k}» باید عدد باشه")
            return None
        it["var"], it["value"] = k, v
        if a.get("upsert"):
            it["upsert"] = True
        _reg_tab(tables, tab, [k])
        return it
    # db_add / db_set
    data = {}
    raw = a.get("data") if isinstance(a.get("data"), dict) else {}
    for k, v in list(raw.items())[:MAX_REC_FIELDS]:
        k = str(k).strip().lower()
        if not VAR_RE.match(k) or k in BUILTINS:
            bad(f"نام فیلد «{k}» در جدول «{tab}» معتبر نیست")
            continue
        data[k] = str(v if v is not None else "").strip()[:MAX_REC_VAL]
    if not data:
        bad(f"اکشن {op} باید حداقل یک فیلد داشته باشه: «data»: {{\"نام‌فیلد\": \"مقدار\"}}")
        return None
    it["data"] = data
    if op == "db_set" and a.get("upsert"):
        it["upsert"] = True
    _reg_tab(tables, tab, data.keys())
    return it


def clean_actions(lst, used, nums, bad, valid=None, tables=None):
    tables = tables if tables is not None else {"tabs": {}, "gets": []}
    out = []
    for a in (lst if isinstance(lst, list) else [])[:6]:
        if not isinstance(a, dict):
            continue
        op = str(a.get("op") or "").strip().lower()
        if op not in ACT_OPS:
            bad(f"نوع اکشن «{op}» معتبر نیست")
            continue
        if op in ("dice", "pick", "fetch", "db_add", "db_get", "db_set", "db_inc", "db_del"):
            it = _clean_new_action(op, a, used, nums, bad, tables)
            if it:
                out.append(it)
            continue
        if op == "calc":                     # محاسبه‌ی امن عبارت حسابی (بدون eval)
            name = str(a.get("var") or "").strip().lower()
            if not VAR_RE.match(name) or name in BUILTINS:
                bad(f"نام متغیر «{name}» برای محاسبه معتبر نیست")
                continue
            v = str(a.get("value", "")).strip()[:80]
            if not v or safe_calc(PH_RE.sub("1", v)) is None:
                bad(f"عبارت محاسبه برای «{name}» معتبر نیست؛ فقط عدد، + - * / و پرانتز (متغیر با {{}})")
                continue
            used.add(name)
            nums.add(name)
            out.append({"op": "calc", "var": name, "value": v})
            continue
        if op == "disc":                     # بررسی کد تخفیف: {var}_off قیمت بعد تخفیف، {var}_save سود
            name = str(a.get("var") or "").strip().lower()
            if not VAR_RE.match(name) or name in BUILTINS:
                bad(f"نام متغیر «{name}» برای کد تخفیف معتبر نیست")
                continue
            price = str(a.get("price", "")).strip()[:40]
            if to_num(price) is None and not PH_RE.search(price):
                bad("قیمت پایه‌ی کد تخفیف باید عدد یا متغیر (مثل {price}) باشه")
                continue
            used.add(name)
            nums.add(name)
            out.append({"op": "disc", "var": name, "price": price or "0"})
            continue
        if op in ("sub_add", "sub_del"):     # اشتراک دوره
            plan = re.sub(r"[^a-z0-9_]", "", str(a.get("plan") or "vip").lower())[:16] or "vip"
            item = {"op": op, "plan": plan}
            name = str(a.get("var") or "").strip().lower()
            if VAR_RE.match(name) and name not in BUILTINS:
                item["var"] = name
                if op == "sub_add":
                    used.add(name)
            if op == "sub_add":
                days = str(a.get("days", 30)).strip()[:20]
                if to_num(days) is None and not PH_RE.search(days):
                    days = "30"
                item["days"] = days or "30"
            out.append(item)
            continue
        if op == "notify":
            v = str(a.get("value") or "").strip()[:500]
            if v:
                out.append({"op": "notify", "value": v})
            else:
                bad("متن اعلان (notify) خالیه")
            continue
        if op == "remind":
            v = str(a.get("value") or "").strip()[:500]
            try:
                mins = int(str(a.get("minutes", a.get("after", 60))).translate(_DIG))
            except (TypeError, ValueError):
                mins = 0
            if not 1 <= mins <= 43200:
                bad("زمان یادآور (minutes) باید بین ۱ تا ۴۳۲۰۰ دقیقه (۳۰ روز) باشه")
                continue
            g = str(a.get("goto") or "")
            if g and not (valid and g in valid):
                bad(f"بخش مقصد یادآور «{g}» وجود نداره")
                g = ""
            if not v and not g:
                bad("یادآور باید متن یا بخش مقصد داشته باشه")
                continue
            item = {"op": "remind", "minutes": mins}
            if v:
                item["value"] = v
            if g:
                item["goto"] = g
            key = re.sub(r"[^a-z0-9_]", "", str(a.get("key") or "").lower())[:20]
            if key:
                item["key"] = key
            out.append(item)
            continue
        name = str(a.get("var") or "").strip().lower()
        if not VAR_RE.match(name) or name in BUILTINS:
            bad(f"نام متغیر «{name}» برای اکشن معتبر نیست (حروف انگلیسی کوچک، عدد و _ و نباید اسم متغیرهای آماده باشه)")
            continue
        item = {"op": op, "var": name}
        if op != "clear":
            v = str(a.get("value", "")).strip()[:100]
            if op == "add":
                rg = re.fullmatch(r"(\d{1,9})\s*-\s*(\d{1,9})", v.translate(_DIG))
                if rg and int(rg.group(1)) <= int(rg.group(2)):
                    v = f"{int(rg.group(1))}-{int(rg.group(2))}"          # امتیاز تصادفی در بازه
                elif v == "":
                    v = "1"
                elif to_num(v) is None and not PH_RE.search(v):
                    bad(f"مقدار اکشن جمع برای «{name}» باید عدد باشه")
                    continue
            elif op == "random":
                m = re.fullmatch(r"(\d{1,9})\s*-\s*(\d{1,9})", v.translate(_DIG))
                if not m or int(m.group(1)) > int(m.group(2)):
                    bad(f"بازه‌ی عدد تصادفی «{name}» باید مثل 1-6 باشه")
                    continue
                v = f"{int(m.group(1))}-{int(m.group(2))}"
            item["value"] = v
        used.add(name)
        if op in ("add", "random"):
            nums.add(name)
        out.append(item)
    return out


def clean_pay(pay, label, valid, bad):
    """دکمه‌ی پرداخت با ستاره‌ی تلگرام (XTR)؛ نامعتبر = None"""
    if not PAYMENTS:
        bad("پرداخت با ستاره در این سرویس فعال نیست")
        return None
    try:
        stars = int(str(pay.get("stars", 0)).translate(_DIG))
    except (TypeError, ValueError):
        stars = 0
    if not 1 <= stars <= MAX_STARS:
        bad(f"مبلغ دکمه‌ی پرداخت «{label}» باید عدد صحیح بین ۱ تا {MAX_STARS} ستاره باشه")
        return None
    title = (str(pay.get("title") or "").strip() or label)[:32]
    p = {"stars": stars, "title": title, "desc": (str(pay.get("desc") or "").strip() or title)[:255]}
    tx = str(pay.get("text") or "").strip()[:300]
    if tx:
        p["text"] = tx
    g = str(pay.get("goto") or "")
    if g:
        if g in valid:
            p["goto"] = g
        else:
            bad(f"بخش بعد از پرداختِ «{label}» وجود نداره")
    return {"text": label, "pay": p}


def clean_join(j, bad, where=""):  # متن پیام عضویت: HTML تلگرام مجازه
    """عضویت اجباری (سراسری، روی یک بخش یا روی یک دکمه): تا ۳ کانال عمومی + پیام درخواست"""
    if not isinstance(j, dict):
        return None
    chans, raw = [], j.get("channels")
    for c in (raw if isinstance(raw, list) else [])[:3]:
        c = re.sub(r"^(https?://)?(t\.me|telegram\.me)/", "", str(c).strip(), flags=re.I).lstrip("@")
        if re.match(r"^[A-Za-z][A-Za-z0-9_]{4,31}$", c):
            if c not in chans:
                chans.append(c)
        else:
            bad(f"آیدی کانال «{c}» معتبر نیست{where}")
    if not chans:
        return None
    return {"channels": chans,
            "text": str(j.get("text") or "برای استفاده از ربات اول باید عضو کانال بشی.").strip()[:500]}


MOD_LOCKS = {"link": "لینک", "forward": "فوروارد", "photo": "عکس", "video": "ویدیو", "sticker": "استیکر", "voice": "ویس", "document": "فایل",
             "contact": "مخاطب", "mention": "منشن @", "animation": "گیف", "audio": "موزیک", "poll": "نظرسنجی", "location": "موقعیت", "via_bot": "ربات اینلاین"}
MOD_CLEAN = {"join": "پیام ورود", "leave": "پیام خروج", "pin": "پیام سنجاق", "title": "تغییر نام و عکس گروه"}
MOD_ACTIONS = ("warn", "mute", "delete")
MOD_THEN = ("mute", "ban", "kick")
CHAN_RE = re.compile(r"^(@[A-Za-z][A-Za-z0-9_]{4,31}|-100\d{5,15})$")


def _mnum(v, lo, hi, d):
    try:
        return max(lo, min(hi, int(float(str(v).translate(_DIG).strip()))))
    except (TypeError, ValueError):
        return d


def clean_mod(m, bad):
    """تنظیمات مدیریت گروه و کانال (cfg["mod"]) رو تمیز می‌کنه"""
    if not isinstance(m, dict):
        return None
    o = {}
    for k, lim in (("welcome", 1000), ("goodbye", 500), ("rules", 2000)):
        v = str(m.get(k) or "").strip()[:lim]
        if v:
            o[k] = v
    if o.get("welcome"):
        o["welcome_del"] = _mnum(m.get("welcome_del"), 0, 3600, 60)
    cp = m.get("captcha")
    if isinstance(cp, dict) and cp.get("on"):
        o["captcha"] = {"on": True, "mins": _mnum(cp.get("mins"), 1, 30, 3)}
    lk = [x for x in (m.get("lock") if isinstance(m.get("lock"), list) else []) if x in MOD_LOCKS]
    if lk:
        o["lock"] = list(dict.fromkeys(lk))
    ws = []
    for w in (m.get("words") if isinstance(m.get("words"), list) else [])[:60]:
        w = str(w).strip().lower()[:30]
        if w and w not in ws:
            ws.append(w)
    if ws:
        o["words"] = ws
    fl = m.get("flood")
    if isinstance(fl, dict) and _mnum(fl.get("n"), 0, 20, 0) >= 2:
        o["flood"] = {"n": _mnum(fl.get("n"), 2, 20, 6), "secs": _mnum(fl.get("secs"), 2, 60, 8)}
    o["action"] = m.get("action") if m.get("action") in MOD_ACTIONS else "warn"
    w = m.get("warns") if isinstance(m.get("warns"), dict) else {}
    o["warns"] = {"max": _mnum(w.get("max"), 1, 10, 3), "then": w.get("then") if w.get("then") in MOD_THEN else "mute", "mins": _mnum(w.get("mins"), 1, 10080, 60)}
    cl = [x for x in (m.get("clean") if isinstance(m.get("clean"), list) else []) if x in MOD_CLEAN]
    if cl:
        o["clean"] = list(dict.fromkeys(cl))
    o["report"] = m.get("report") is not False
    ch = m.get("channel")
    if isinstance(ch, dict):
        cid = str(ch.get("id") or "").strip()
        if cid and not CHAN_RE.match(cid):
            bad(f"آیدی کانال «{cid}» معتبر نیست؛ مثل @mychannel یا -1001234567890")
            cid = ""
        c = {}
        if cid:
            c["id"] = cid
        bt = ch.get("button") if isinstance(ch.get("button"), dict) else {}
        url = norm_url(bt.get("url"))
        txt = str(bt.get("text") or "").strip()[:30]
        if txt and url:
            c["button"] = {"text": txt, "url": url}
        rc = str(ch.get("react") or "").strip()[:8]
        if rc:
            c["react"] = rc
        if c:
            o["channel"] = c
    return o


BTN_STYLES = ("primary", "success", "danger")   # آبی، سبز، قرمز
GRP_ON = ("contains", "exact", "starts", "command")
# reaction: واکنش ایموجی؛ mention: منشن‌کردن ربات — بعد از ماشه‌های معمولی اجرا می‌شوند
MAX_TRIGGERS = 20


def clean_group(g, used, nums, bad, valid, tables, gl):
    """ماشه‌های گروه (cfg["group"]): وقتی عضوی توی گروه کلمه یا دستور خاصی فرستاد ← پاسخ + اکشن (امتیاز، رندوم، جدول برترین‌ها)"""
    if not isinstance(g, dict):
        return None
    out = []
    for t in (g.get("triggers") if isinstance(g.get("triggers"), list) else [])[:MAX_TRIGGERS]:
        if not isinstance(t, dict):
            continue
        k = str(t.get("on") or "contains").strip().lower()
        k = k if k in GRP_ON + ("reaction", "mention") else "contains"
        raw = t.get("words") if isinstance(t.get("words"), list) else re.split(r"[,،\n]+", str(t.get("words") or ""))
        ws = []
        for w in raw[:10]:
            w = str(w).strip()[:40]
            if k == "command":
                w = re.sub(r"[^\w]", "", w.lstrip("/").lower())
            if w and w not in ws:
                ws.append(w)
        if not ws and k != "mention":          # منشن بدون کلمه هم معتبر است (منشن‌کردن خود ربات)
            bad("یکی از ماشه‌های گروه کلمه یا دستور نداره")
            continue
        o = {"on": k, "words": ws}
        reply = str(t.get("reply") or "").strip()[:1500]
        if reply:
            o["reply"] = reply
        acts = clean_actions(t.get("do"), used, nums, bad, valid, tables) if t.get("do") else []
        if acts:
            o["do"] = acts
        bd = t.get("board")
        if isinstance(bd, dict):
            bv = str(bd.get("var") or "").strip().lower()
            if bv == "refs" or (VAR_RE.match(bv) and bv not in BUILTINS and bv not in gl):
                o["board"] = {"var": bv, "top": _mnum(bd.get("top"), 3, 20, 10)}
                lab = str(bd.get("label") or "").strip()[:30]
                if lab:
                    o["board"]["label"] = lab
                if bv != "refs":
                    used.add(bv)
                    nums.add(bv)
            else:
                bad("متغیر جدول برترین‌های یک ماشه‌ی گروه باید یه متغیر شخصیِ عددی باشه")
        if t.get("ai"):
            na = str(t.get("ai") or "")
            if na in valid and valid[na][0].get("ai"):
                o["ai"] = na
            else:
                bad("فراخوانی عاملِ یک ماشه باید به بخشِ گفتگوی هوشمند وصل باشد")
        if not (o.get("reply") or o.get("do") or o.get("board") or o.get("ai")):
            bad("یکی از ماشه‌های گروه نه پاسخ داره نه اکشن")
            continue
        if t.get("when"):
            w = clean_cond(t["when"], used, nums, bad)
            if w:
                o["when"] = w
        cd = _mnum(t.get("cooldown"), 0, 86400, 0)
        if cd:
            o["cooldown"] = cd
        ttl = _mnum(t.get("ttl"), 0, 3600, 0)
        if ttl:
            o["ttl"] = ttl
        if str(t.get("to") or "") == "replied":
            o["to"] = "replied"
        if t.get("delete"):
            o["delete"] = True
        out.append(o)
    return {"triggers": out} if out else None


def sanitize(cfg, strict=False, media=None, warns=None, nodes_cap=None):
    """strict=True (ویرایش دستی): خطا می‌ده.  strict=False (خروجی AI): تا جای ممکن خودش درست می‌کنه.
    media = مجموعه‌ی شناسه‌ی رسانه‌هایی که مال خود کاربره؛ بقیه بی‌صدا حذف می‌شن
    nodes_cap = سقف بخش‌ها (پلن‌محور)؛ خالی = MAX_NODES"""
    media = media or set()
    if not isinstance(cfg, dict) or not isinstance(cfg.get("nodes"), dict):
        raise ValueError("ساختار خروجی معتبر نیست")
    try:
        cap_n = max(1, int(nodes_cap)) if nodes_cap else MAX_NODES
    except (TypeError, ValueError):
        cap_n = MAX_NODES
    nodes_in = cfg["nodes"]
    if not (1 <= len(nodes_in) <= cap_n):
        raise ValueError(f"تعداد بخش‌ها باید بین ۱ تا {cap_n} باشه")

    def bad(msg):
        if strict:
            raise ValueError(msg)
        if warns is not None and len(warns) < 12 and msg not in warns:
            warns.append(msg)            # چیزی که بی‌صدا حذف/اصلاح شد؛ برای بازخورد به هوش مصنوعی

    # متغیرهای مشترک بین همه‌ی کاربرها (شمارنده‌ها، رأی‌گیری، موجودی مشترک)
    gl = {}
    gd = cfg.get("globals")
    for k, v in (gd.items() if isinstance(gd, dict) else []):
        k = str(k).strip().lower()
        if VAR_RE.match(k) and k not in BUILTINS and len(gl) < MAX_GLOBALS:
            gl[k] = str(v if v is not None else "")[:100]
        else:
            bad(f"نام یا تعداد متغیر مشترک «{k}» معتبر نیست (حروف انگلیسی کوچک، عدد و _، حداکثر {MAX_GLOBALS} تا)")

    used, nums = set(), set()      # متغیرهایی که جایی استفاده شدن / مقدار عددی دارن
    tables = {"tabs": {}, "gets": []}      # جدول‌های داده (db_*) و جای خواندن‌هاشون
    valid = {}
    for nid, n in nodes_in.items():
        nid = str(nid)
        if not ID_RE.match(nid) or not isinstance(n, dict):
            bad("شناسه‌ی یکی از بخش‌ها نامعتبره"); continue
        text = str(n.get("text", "")).strip()[:3500]
        if not text:
            bad(f"بخش «{nid}» متن نداره"); continue
        valid[nid] = (n, text)
    if not valid:
        raise ValueError("هیچ بخش معتبری وجود نداره")

    nodes = {}
    for nid, (n, text) in valid.items():
        rows = []
        for row in (n.get("buttons") or [])[:6]:
            r = []
            for b in (row if isinstance(row, list) else [row])[:3]:
                if not isinstance(b, dict):
                    continue
                label = str(b.get("text", "")).strip()[:40]
                if not label:
                    bad(f"بخش «{nid}» یه دکمه‌ی بدون متن داره"); continue
                it = None
                g = str(b.get("goto") or "")
                if isinstance(b.get("pay"), dict):
                    it = clean_pay(b["pay"], label, valid, bad)
                elif str(b.get("contact") or ""):
                    it = {"text": label, "contact": True, "kb": "reply"}       # تلگرام: فقط در کیبورد پایین چت
                elif str(b.get("location") or ""):
                    it = {"text": label, "location": True, "kb": "reply"}
                elif str(b.get("inline") or "").strip():
                    it = {"text": label, "inline": str(b["inline"]).strip()[:64]}
                elif b.get("app") is not None:      # دکمه‌ی «باز کردن مینی‌اپ»؛ مقدار = صفحه‌ی شروع اختیاری
                    ap = b.get("app")
                    ap = "1" if ap in (True, 1, "1", "") else str(ap).strip()
                    if ap and not ID_RE.match(ap):
                        bad(f"صفحه‌ی دکمه‌ی «{label}» معتبر نیست (شناسه‌ی صفحه‌ی مینی‌اپ)")
                        ap = "1"
                    it = {"text": label, "app": ap or "1"}
                elif g:
                    if g in valid:
                        it = {"text": label, "goto": g}
                    else:
                        bad(f"دکمه‌ی «{label}» به بخش ناموجود وصله")
                elif str(b.get("alert") or "").strip():
                    it = {"text": label, "alert": str(b["alert"]).strip()[:200]}
                elif str(b.get("copy") or "").strip():
                    it = {"text": label, "copy": str(b["copy"]).strip()[:256]}
                elif b.get("share"):
                    sv = b["share"]
                    sv = sv.strip() if isinstance(sv, str) and sv.strip().lower() != "true" else ""
                    it = {"text": label, "share": (sv or "بیا این ربات رو ببین")[:200]}
                else:
                    u = norm_url(b.get("url"))
                    if u:
                        it = {"text": label, "url": u}
                    else:
                        bad(f"لینک/آیدی دکمه‌ی «{label}» معتبر نیست (باید https:// یا @آیدی باشه)")
                if it is None:
                    continue
                if b.get("when"):
                    w = clean_cond(b["when"], used, nums, bad)
                    if w:
                        it["when"] = w
                if b.get("join"):
                    if "goto" in it or "alert" in it or "pay" in it:
                        bj = clean_join(b["join"], bad, f" (دکمه‌ی «{label}»)")
                        if bj:
                            it["join"] = bj
                    else:
                        bad(f"عضویت اجباری فقط روی دکمه‌های «رفتن به بخش»، «پیام پاپ‌آپ» و «پرداخت» کار می‌کنه (دکمه‌ی «{label}»)")
                if b.get("do"):
                    if "goto" in it or "alert" in it or "pay" in it:
                        acts = clean_actions(b["do"], used, nums, bad, valid, tables)
                        if acts:
                            it["do"] = acts
                    else:
                        bad(f"اکشن فقط روی دکمه‌های «رفتن به بخش»، «پیام پاپ‌آپ» و «پرداخت» کار می‌کنه (دکمه‌ی «{label}»)")
                if "app" not in it and (b.get("kb") == "reply" or n.get("kb") == "reply"):      # دکمه‌ی مینی‌اپ فقط شیشه‌ای می‌شود؛ کیبورد پایین چت web_app ندارد
                    it["kb"] = "reply"                                    # کیبورد پایین چت؛ بدونش = دکمه‌ی شیشه‌ای
                bst = str(b.get("style") or "").strip().lower()           # رنگ دکمه و ایموجی پرمیوم (اشتراک پرمیوم/پرو)
                if bst in BTN_STYLES:
                    it["style"] = bst
                bic = str(b.get("icon") or "").strip()
                if bic.isdigit() and len(bic) <= 32:
                    it["icon"] = bic
                r.append(it)
            if r:
                rows.append(r)
        node = {"text": text, "buttons": rows, "ask": bool(n.get("ask"))}
        title = str(n.get("title") or "").strip()[:30]
        if title:
            node["title"] = title
        ph = str(n.get("photo") or "").strip()
        if ph:
            if ph.startswith("https://") and not re.search(r"\s", ph) and len(ph) <= 500:
                node["photo"] = ph
            else:
                bad(f"آدرس عکس بخش «{nid}» معتبر نیست (باید لینک مستقیم https باشه)")
        raw_m = n.get("media")
        if isinstance(raw_m, dict) and norm_url(raw_m.get("url")) and "photo" not in node:
            node["photo"] = norm_url(raw_m["url"])          # سازگاری با کانفیگ‌های نسخه‌ی قبلی (media با لینک)
        mid = str(raw_m if isinstance(raw_m, str) else "").strip()
        if mid in media:
            node["media"] = mid

        # فرم: سؤال‌ها + ذخیره در متغیر + نوع پاسخ
        fl_raw = n.get("fields") if isinstance(n.get("fields"), list) else []
        sv_raw = n.get("save") if isinstance(n.get("save"), list) else []
        ty_raw = n.get("types") if isinstance(n.get("types"), list) else []
        qs, svs, tys = [], [], []
        for i, f in enumerate(fl_raw):
            q = str(f).strip()[:200]
            if not q or len(qs) >= 6:
                continue
            v = str(sv_raw[i]).strip().lower() if i < len(sv_raw) and sv_raw[i] else ""
            if v:
                if VAR_RE.match(v) and v not in BUILTINS:
                    used.add(v)
                else:
                    bad(f"نام متغیر «{v}» برای ذخیره‌ی پاسخ معتبر نیست"); v = ""
            t = str(ty_raw[i]).strip().lower() if i < len(ty_raw) else "text"
            if t not in F_TYPES:
                t = "text"
            if t == "number" and v:
                nums.add(v)
            qs.append(q); svs.append(v); tys.append(t)
        if qs:
            node["fields"], node["ask"] = qs, False
            if any(svs):
                node["save"] = svs
            if any(t != "text" for t in tys):
                node["types"] = tys
            if n.get("silent"):
                node["silent"] = True
        ai = n.get("ai")
        if isinstance(ai, dict) and str(ai.get("prompt") or "").strip():
            if node.get("fields") or node["ask"]:
                bad(f"بخش «{nid}» نمی‌تونه هم فرم/دریافت پیام باشه هم گفتگوی هوشمند")
            else:
                try:
                    dly = int(ai.get("daily", 15))
                except (TypeError, ValueError):
                    dly = 15
                try:
                    mem = max(0, min(6, int(ai.get("memory", 3))))
                except (TypeError, ValueError):
                    mem = 3
                node["ai"] = {"prompt": str(ai["prompt"]).strip()[:1500], "daily": max(1, min(100, dly)), "memory": mem}
                sc = str(ai.get("scope") or "").strip()[:200]
                if sc:
                    node["ai"]["scope"] = sc          # گارد موضوعی: فقط این موضوع‌ها
                tls = []                              # ابزارها: جستجو در همین جدول‌های ربات (حداکثر ۳)
                for x in (ai.get("tools") if isinstance(ai.get("tools"), list) else [])[:3]:
                    t2 = str(x).strip().lower()
                    if TAB_RE.match(t2) and t2 not in tls:
                        _reg_tab(tables, t2, [])
                        tls.append(t2)
                if tls:
                    node["ai"]["tools"] = tls
        # تیکت: هر پیام/فرم این بخش یک تیکت شماره‌دار می‌شه با دکمه‌ی «پاسخ» برای صاحب ربات و پشتیبان‌ها
        tk = n.get("ticket")
        if tk:
            if node.get("fields") or node["ask"]:
                node["ticket"] = True
                tag = str(n.get("tag") or (tk if isinstance(tk, str) and tk.strip().lower() != "true" else "")).strip()[:20]
                if tag:
                    node["tag"] = tag
            else:
                bad(f"بخش «{nid}» تیکت می‌خواد ولی «دریافت پیام» (ask) یا فرم (fields) نداره")
        # نظرسنجی خودکار بعد از پیام این بخش
        pl = n.get("poll")
        if isinstance(pl, dict) and str(pl.get("q") or "").strip():
            opts = [str(x).strip()[:30] for x in (pl.get("opts") if isinstance(pl.get("opts"), list) else []) if str(x).strip()][:10]
            if len(opts) >= 2:
                node["poll"] = {"q": str(pl["q"]).strip()[:255], "opts": opts}
            else:
                bad(f"نظرسنجی بخش «{nid}» حداقل دو گزینه لازم دارد")
        # دکمه‌ها از یک لیست (با صفحه‌بندی خودکار)
        bl = n.get("btnlist")
        if isinstance(bl, dict):
            tab = str(bl.get("table") or "").strip().lower()
            if not TAB_RE.match(tab):
                bad(f"نام جدول دکمه‌های «{nid}» معتبر نیست")
            else:
                _reg_tab(tables, tab, [str(bl.get("text_f") or "text").lower()])
                o = {"table": tab, "text_f": str(bl.get("text_f") or "text").lower(), "goto": str(bl.get("goto") or "")}
                if o["goto"] not in valid:
                    bad(f"دکمه‌های لیستی بخش «{nid}» باید به یک بخش معتبر وصل باشند")
                else:
                    if bl.get("scope") in ("all", "shared", True):
                        o["scope"] = "all"
                    try:
                        o["per"] = max(2, min(5, int(float(str(bl.get("per", 4)).translate(_DIG)))))
                    except (TypeError, ValueError):
                        o["per"] = 4
                    node["btnlist"] = o
        # یادداشت خصوصی و قاب رنگی کارت (فقط داخل استودیو دیده می‌شود)
        note = str(n.get("note") or "").strip()[:100]
        if note:
            node["note"] = note
        frame = str(n.get("frame") or "").strip()
        if frame in ("red", "green", "blue", "amber", "violet"):
            node["frame"] = frame
        # جدول برترین‌ها زیر متن بخش
        bd = n.get("board")
        if isinstance(bd, dict):
            bv = str(bd.get("var") or "").strip().lower()
            if bv == "refs" or (VAR_RE.match(bv) and bv not in BUILTINS and bv not in gl):
                try:
                    topn = max(3, min(20, int(bd.get("top", 10))))
                except (TypeError, ValueError):
                    topn = 10
                node["board"] = {"var": bv, "top": topn}
                lab = str(bd.get("label") or "").strip()[:30]
                if lab:
                    node["board"]["label"] = lab
                if bv != "refs":
                    used.add(bv)
                    nums.add(bv)
            else:
                bad(f"متغیر جدول برترین‌ها در بخش «{nid}» باید یه متغیر شخصیِ عددی (یا refs) باشه")
        # فهرست رکوردهای جدول داده، زیر متن بخش (آرشیو سفارش‌ها، دیوار پیشنهادها، آخرین بازی‌ها)
        ls = n.get("list")
        if isinstance(ls, dict):
            tab = str(ls.get("table") or "").strip().lower()
            if not TAB_RE.match(tab):
                bad(f"نام جدول فهرست در بخش «{nid}» معتبر نیست (حروف انگلیسی کوچک، عدد و _)")
            else:
                _reg_tab(tables, tab, [])
                o = {"table": tab}
                if ls.get("scope") in ("all", "shared", True):
                    o["scope"] = "all"
                try:
                    o["limit"] = max(1, min(10, int(ls.get("limit", 5))))
                except (TypeError, ValueError):
                    o["limit"] = 5
                line = str(ls.get("line") or "").strip()[:200]
                if line:
                    o["line"] = line
                emp = str(ls.get("empty") or "").strip()[:200]
                if emp:
                    o["empty"] = emp
                if str(ls.get("order") or "").strip().lower() == "old":
                    o["order"] = "old"
                w = clean_rec_cond(ls.get("when"), bad)
                if w:
                    o["when"] = w
                node["list"] = o
        elif ls:
            bad(f"فهرست داده‌ی بخش «{nid}» معتبر نیست")
        if (node.get("fields") or node["ask"] or node.get("ai")) and any(b.get("kb") == "reply" for row in rows for b in row):
            for row in rows:                # کیبورد پایین چت فقط برای بخش‌های بدون ask/form/ai
                for b in row:
                    b.pop("kb", None)
            bad(f"کیبورد پایین چت روی بخش «{nid}» کار نمی‌کنه (فرم/دریافت پیام/هوش مصنوعی)؛ دکمه‌ها شیشه‌ای شدن")
        done = str(n.get("done") or "").strip()[:500]
        if done:
            node["done"] = done
        dm = str(n.get("done_media") or "").strip()
        if dm in media and (node.get("fields") or node["ask"]):
            node["done_media"] = dm
        nxt = str(n.get("next") or "")
        if nxt:
            if nxt in valid:
                node["next"] = nxt
            else:
                bad(f"بخش بعدیِ «{nid}» وجود نداره")

        # منطق: اکشن‌ها، هدایت شرطی، متن جایگزین
        acts = clean_actions(n.get("do"), used, nums, bad, valid, tables)
        if acts:
            node["do"] = acts
        route = []
        for rule in (n.get("route") if isinstance(n.get("route"), list) else [])[:5]:
            if not isinstance(rule, dict):
                continue
            w, g = clean_cond(rule.get("when"), used, nums, bad), str(rule.get("goto") or "")
            if w and g in valid:
                route.append({"when": w, "goto": g})
            else:
                bad(f"یکی از قانون‌های هدایت شرطیِ بخش «{nid}» کامل نیست")
        if route:
            node["route"] = route
        alt = []
        for rule in (n.get("alt") if isinstance(n.get("alt"), list) else [])[:4]:
            if not isinstance(rule, dict):
                continue
            w, t = clean_cond(rule.get("when"), used, nums, bad), str(rule.get("text") or "").strip()[:3500]
            if w and t:
                alt.append({"when": w, "text": t})
            else:
                bad(f"یکی از متن‌های جایگزینِ بخش «{nid}» کامل نیست")
        if alt:
            node["alt"] = alt
        nj = clean_join(n.get("join"), bad, f" (بخش «{nid}»)")
        if nj:
            node["join"] = nj
        nodes[nid] = node

    # متغیرهایی که اکشن db_get پر می‌کنه: برای هر فیلد شناخته‌شده‌ی جدول یک متغیر (پیشوند_فیلد)
    for pfx, tab in tables["gets"]:
        for f in tables["tabs"].get(tab, ()):
            v = f"{pfx}_{f}" if pfx else f
            if VAR_RE.match(v) and v not in BUILTINS:
                used.add(v)
    if len(tables["tabs"]) > MAX_TABLES:
        bad(f"حداکثر {MAX_TABLES} جدول داده می‌تونی داشته باشی")

    start = str(cfg.get("start") or "")
    if start not in nodes:
        bad("بخش شروع معتبر نیست")
        start = next(iter(nodes))
    fallback = str(cfg.get("fallback") or start)
    if fallback not in nodes:
        bad("بخش پیام‌های ناشناس معتبر نیست")
        fallback = start
    cmds = {}
    for k, v in (cfg.get("commands") or {}).items():
        k = str(k).lstrip("/").lower()
        if not CMD_RE.match(k) or k == "start" or str(v) not in nodes:
            bad(f"دستور «/{k}» معتبر نیست (فقط حروف انگلیسی کوچک/عدد/_ و غیر از start)")
            continue
        cmds[k] = str(v)
    out = {"name": str(cfg.get("name") or "ربات من").strip()[:50] or "ربات من", "start": start,
           "fallback": fallback, "commands": cmds, "nodes": nodes}

    # پاداش دعوت: اکشن‌هایی که برای دعوت‌کننده اجرا می‌شن
    on_ref = clean_actions(cfg.get("on_ref"), used, nums, bad, None, tables)
    if on_ref:
        out["on_ref"] = on_ref
        rt = str(cfg.get("ref_text") or "").strip()[:500]
        if rt:
            out["ref_text"] = rt
    elif str(cfg.get("ref_text") or "").strip():
        out["ref_text"] = str(cfg["ref_text"]).strip()[:500]

    gp = clean_group(cfg.get("group"), used, nums, bad, valid, tables, gl)
    if gp:
        out["group"] = gp
        for tr in gp["triggers"]:              # متغیرهای داخل پاسخ ماشه‌ها هم باید اعلام بشن
            for m in PH_RE.finditer(tr.get("reply") or ""):
                if VAR_RE.match(m.group(1)) and m.group(1) not in BUILTINS and m.group(1) not in gl:
                    used.add(m.group(1))

    # متغیرهای اعلام‌شده (+ هر متغیری که جایی استفاده شده ولی اعلام نشده، خودکار اضافه می‌شه)
    declared = {}
    dv = cfg.get("vars")
    for k, v in (dv.items() if isinstance(dv, dict) else []):
        k = str(k).strip().lower()
        if VAR_RE.match(k) and k not in BUILTINS:
            declared[k] = str(v if v is not None else "")[:100]
        else:
            bad(f"نام متغیر «{k}» معتبر نیست (حروف انگلیسی کوچک، عدد و _ و نباید اسم متغیرهای آماده باشه)")
    for k in sorted(used):
        if k not in gl:
            declared.setdefault(k, "0" if k in nums else "")
    for k in list(declared):
        if k in gl:
            declared.pop(k)              # اسم مشترک، متغیر شخصی نیست
    if len(declared) > MAX_VARS:
        if strict:
            raise ValueError(f"حداکثر {MAX_VARS} متغیر می‌تونی داشته باشی")
        declared = dict(list(declared.items())[:MAX_VARS])
    if declared:
        out["vars"] = declared
    if gl:
        for k in gl:
            if k in nums and gl[k] == "":
                gl[k] = "0"
        out["globals"] = gl

    # میزکار پشتیبانی: پشتیبان‌های اضافه، پیام بستن تیکت و برچسب دکمه‌ی پاسخ کاربر
    dk = cfg.get("desk")
    if isinstance(dk, dict):
        d, staff = {}, []
        for x in (dk.get("staff") if isinstance(dk.get("staff"), list) else [])[:MAX_STAFF]:
            sx = re.sub(r"\D", "", str(x).translate(_DIG))
            if 5 <= len(sx) <= 15:
                if int(sx) not in staff:
                    staff.append(int(sx))
            else:
                bad(f"آیدی عددی پشتیبان «{x}» معتبر نیست")
        if staff:
            d["staff"] = staff
        for key, lim in (("closed", 300), ("reply_btn", 30)):
            v = str(dk.get(key) or "").strip()[:lim]
            if v:
                d[key] = v
        if d:
            out["desk"] = d

    # مرکز بازی (B1): روشن/خاموش، برچسب سکه، فهرست بازی‌ها، پاداش و فروشگاه سکه‌ای
    gm = cfg.get("games")
    if isinstance(gm, dict) and gm.get("on"):
        import caps as _caps_mod
        gids = {g["k"] for g in _caps_mod.CAPS_GAMES}
        ls = [str(x) for x in (gm.get("list") if isinstance(gm.get("list"), list) else []) if str(x) in gids][:9]
        try:
            dly = max(0, min(1000, int(float(str(gm.get("daily", 15)).translate(_DIG)))))
        except (TypeError, ValueError):
            dly = 15
        shop = []
        for x in (gm.get("shop") if isinstance(gm.get("shop"), list) else [])[:12]:
            if not isinstance(x, dict) or not str(x.get("id") or "").strip():
                continue
            try:
                price = max(1, int(float(str(x.get("price", 10)).translate(_DIG))))
            except (TypeError, ValueError):
                price = 10
            shop.append({"id": re.sub(r"[^a-z0-9_]", "", str(x["id"]).lower())[:20], "title": str(x.get("title") or x["id"])[:30],
                         "price": price, "desc": str(x.get("desc") or "")[:60]})
        rw = {}
        for k, v in (gm.get("reward") or {}).items() if isinstance(gm.get("reward"), dict) else []:
            try:
                rw[str(k)[:10]] = max(0.2, min(20.0, float(v)))
            except (TypeError, ValueError):
                pass
        out["games"] = {"on": True, "coin": str(gm.get("coin") or "سکه")[:12], "daily": dly,
                        "list": ls, "shop": shop, "reward": rw}
    # ربات رشد (B4): گروه هدف، پاداش، متغیر، سقف روزانه و کسر در خروج
    gr = cfg.get("growth")
    if isinstance(gr, dict) and gr.get("on"):
        chat = str(gr.get("chat") or "").strip()
        if not CHAN_RE.match(chat):
            bad("برای رشد، شناسه‌ی گروه/کانال معتبر لازم است (@نام یا -100…)")
        else:
            var = str(gr.get("var") or "points").strip().lower()
            if not VAR_RE.match(var) or var in BUILTINS:
                var = "points"
            used.add(var)
            nums.add(var)
            out["growth"] = {"on": True, "chat": chat, "var": var, "reward": _mnum(gr.get("reward"), 0, 1000, 10),
                             "per_day": _mnum(gr.get("per_day"), 0, 200, 20),
                             "clawback": gr.get("clawback", True) is not False,
                             "wallet": bool(gr.get("wallet"))}
    # پست کانال: مقصد، تأیید مدیریتی، دکمه و نظرسنجی خودکار زیر پست
    cpst = cfg.get("channelpost")
    if isinstance(cpst, dict) and cpst.get("on"):
        chat = str(cpst.get("chat") or "").strip()
        if not CHAN_RE.match(chat):
            bad("برای پست کانال، شناسه‌ی کانال معتبر لازم است (@نام یا -100…)")
        else:
            o = {"on": True, "chat": chat, "approve": cpst.get("approve") is not False}
            bu = norm_url(cpst.get("btn_url"))
            if bu and str(cpst.get("btn_text") or "").strip():
                o["btn_text"], o["btn_url"] = str(cpst["btn_text"]).strip()[:24], bu
            if str(cpst.get("poll_q") or "").strip():
                po = [str(x).strip()[:30] for x in (cpst.get("poll_opts") if isinstance(cpst.get("poll_opts"), list) else []) if str(x).strip()][:10]
                if len(po) >= 2:
                    o["poll_q"], o["poll_opts"] = str(cpst["poll_q"]).strip()[:255], po
            out["channelpost"] = o
    # RSS: منبع، مقصد و بازه‌ی چک
    rss = cfg.get("rss")
    if isinstance(rss, dict) and rss.get("on"):
        u2 = norm_url(rss.get("url"))
        chat = str(rss.get("chat") or "").strip()
        if not u2 or not CHAN_RE.match(chat):
            bad("برای RSS، آدرس https منبع و شناسه‌ی مقصد معتبر لازم است")
        else:
            out["rss"] = {"on": True, "url": u2, "chat": chat, "mins": _mnum(rss.get("mins"), 10, 1440, 30)}
    # جستجوی اینلاین ربات: پاسخ از یک جدول (عنوان/توضیح/لینک)
    inl = cfg.get("inline")
    if isinstance(inl, dict) and inl.get("on"):
        tab = str(inl.get("table") or "").strip().lower()
        if not TAB_RE.match(tab):
            bad("نام جدول جستجوی اینلاین معتبر نیست")
        else:
            _reg_tab(tables, tab, [str(inl.get("title_f") or "title").lower()])
            out["inline"] = {"on": True, "table": tab, "title_f": str(inl.get("title_f") or "title").lower(),
                             "desc_f": str(inl.get("desc_f") or "").lower()[:20], "url_f": str(inl.get("url_f") or "").lower()[:20]}
    # وب‌هوک ورودی: هر رخداد بیرونی یک رکورد در جدول می‌شود (+ خبر اختیاری به صاحب)
    wb = cfg.get("webin")
    if isinstance(wb, dict) and wb.get("on"):
        tab = str(wb.get("table") or "").strip().lower()
        if not TAB_RE.match(tab):
            bad("نام جدول وب‌هوک ورودی معتبر نیست")
        else:
            _reg_tab(tables, tab, ["event"])
            out["webin"] = {"on": True, "table": tab, "notify": wb.get("notify") is not False}
    # خلاصه‌ساز روزانه گروه: مقصد، ساعت و بخش عامل
    dg = cfg.get("digest")
    if isinstance(dg, dict) and dg.get("on"):
        chat = str(dg.get("chat") or "").strip()
        na = str(dg.get("node") or "")
        if not CHAN_RE.match(chat) or na not in valid or not valid[na][0].get("ai"):
            bad("خلاصه‌ی روزانه به مقصد معتبر و یک بخشِ گفتگوی هوشمند نیاز دارد")
        else:
            out["digest"] = {"on": True, "chat": chat, "node": na, "hour": _mnum(dg.get("hour"), 0, 23, 21)}
    jn = clean_join(cfg.get("join"), bad)
    if jn:
        out["join"] = jn
    md = clean_mod(cfg.get("mod"), bad)
    if md:
        out["mod"] = md
    # فیلدهای شناخته‌شده‌ی هر جدول داده؛ موتور موقع خواندن (db_get) و پاک‌کردن متغیرها ازش استفاده می‌کنه
    dbf = {t: sorted(fs) for t, fs in tables["tabs"].items() if fs}
    if dbf:
        out["dbfields"] = dbf
    return out


def bm25_top(query, docs, k=2):
    """جستجوی BM25 خالص پایتون روی قطعه‌های دانش؛ docs = [{"t": عنوان, "x": متن}] → [(عنوان، متن)]"""
    import math as _math
    toks = lambda s2: re.findall(r"[\w\u0600-\u06FF]{2,}", str(s2 or "").lower())  # noqa: E731
    N = max(1, len(docs))
    avg = (sum(len(d["x"].split()) for d in docs) / N) or 1
    df, dts = {}, []
    for d in docs:
        ts = toks(d["t"] + " " + d["x"])
        dts.append(ts)
        for w in set(ts):
            df[w] = df.get(w, 0) + 1
    qt = toks(query)
    out = []
    for i, ts in enumerate(dts):
        tf = {}
        for w in ts:
            tf[w] = tf.get(w, 0) + 1
        dl = len(ts) or 1
        sc = 0.0
        for w in qt:
            if w not in tf:
                continue
            idf = _math.log(1 + (N - df.get(w, 0) + 0.5) / (df.get(w, 0) + 0.5))
            sc += idf * (tf[w] * 2.2) / (tf[w] + 1.2 * 0.25 + 0.75 * dl / avg)
        if sc > 0:
            out.append((sc, i))
    out.sort(reverse=True)
    return [(docs[i]["t"], docs[i]["x"][:400]) for _, i in out[:k]]


# ───────────────────────── تشخیص زبان، ارتباط با مدل و ساخت/ارتقای کانفیگ ─────────────────────────
def _count(s):
    return len(re.findall(r"[\u0600-\u06FF]", s)), len(re.findall(r"[A-Za-z]", s))


def detect_lang(s):
    fa, la = _count(s)
    return "fa" if fa >= la else "other"


# اسکریپت‌های ناخواسته: چینی/ژاپنی/کره‌ای، سیریلیک، تایی، دواناگری، عبری، یونانی و ...
FOREIGN_RE = re.compile(
    "[\u0370-\u03FF\u0400-\u052F\u0590-\u05FF\u0900-\u0DFF\u0E00-\u0EFF\u1100-\u11FF\u1780-\u17FF"
    "\u2E80-\u2FDF\u3000-\u303F\u3040-\u30FF\u3100-\u312F\u3130-\u318F\u31A0-\u31FF\u3200-\u33FF\u3400-\u4DBF"
    "\u4E00-\u9FFF\uA960-\uA97F\uAC00-\uD7FF\uF900-\uFAFF\uFE30-\uFE4F\uFF00-\uFFEF"
    "\U00020000-\U0002FA1F]+")

LANG_GUARD = ("\n\nSTRICT LANGUAGE RULE: write every user-facing text only in Persian (Farsi, Arabic script), "
              "using Latin letters only for brand names, URLs, commands and ids. NEVER output Chinese, Japanese, Korean, "
              "Russian, Thai, Hindi or any other script, not even a single character or word.")


def has_foreign(s):
    return bool(FOREIGN_RE.search(s if isinstance(s, str) else ""))


def scrub_foreign(s):
    """حذف نویسه‌های غیرفارسیِ ناخواسته و مرتب‌کردن فاصله‌ها"""
    if not isinstance(s, str) or not FOREIGN_RE.search(s):
        return s
    out = FOREIGN_RE.sub(" ", s)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r" +([،.؟!:؛)])", r"\1", out)
    return out.strip()


def scrub_deep(o):
    """همین کار برای همه‌ی رشته‌های داخل کانفیگ (متن بخش‌ها، دکمه‌ها، پرامپت‌ها، ...)"""
    if isinstance(o, str):
        return scrub_foreign(o)
    if isinstance(o, list):
        return [scrub_deep(x) for x in o]
    if isinstance(o, dict):
        return {k: scrub_deep(v) for k, v in o.items()}
    return o


def foreign_in(o):
    if isinstance(o, str):
        return has_foreign(o)
    if isinstance(o, list):
        return any(foreign_in(x) for x in o)
    if isinstance(o, dict):
        return any(foreign_in(v) for v in o.values())
    return False


FALLBACK_THINKING = "ربات رو طبق توضیحت طراحی کردم. اگه متن، دکمه یا آیدی کانال چیزی نیاز به تغییر داشت، از «ویرایش دستی» درستش کن."


def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def lint(cfg):
    """مشکل‌های منطقی کانفیگ تمیزشده رو پیدا می‌کنه (برای اینکه AI یک بار خودش درستشون کنه)"""
    nodes, out = cfg["nodes"], []
    seen, stack = set(), [cfg["start"], cfg["fallback"], *cfg["commands"].values()]
    while stack:
        i = stack.pop()
        if i in seen or i not in nodes:
            continue
        seen.add(i)
        n = nodes[i]
        stack += [b["goto"] for row in n["buttons"] for b in row if "goto" in b]
        stack += [r["goto"] for r in n.get("route", [])]
        if n.get("next"):
            stack.append(n["next"])
        for d in _walk(n):                                   # مقصدِ یادآور و بعد از پرداخت هم مسیر حساب می‌شه
            if d.get("op") == "remind" and d.get("goto"):
                stack.append(d["goto"])
            if isinstance(d.get("pay"), dict) and d["pay"].get("goto"):
                stack.append(d["pay"]["goto"])
    lost = [i for i in nodes if i not in seen]
    if lost:
        out.append("unreachable nodes (link them from a goto button / route / next, or remove them): " + ", ".join(lost[:6]))
    dead = [i for i, n in nodes.items() if i in seen and i != cfg["start"] and not n.get("fields") and not n.get("ask")
            and not n.get("route") and not n.get("next") and not any("goto" in b for row in n["buttons"] for b in row)]
    if dead:
        out.append("dead-end nodes with no goto/back button (add a back or home button): " + ", ".join(dead[:6]))
    reads, writes = set(), set()
    for d in _walk(nodes):
        for v in d.values():
            if isinstance(v, str):
                reads.update(m.group(1) for m in PH_RE.finditer(v))
        op = d.get("op")
        if op in OPS and d.get("var"):
            reads.add(d["var"])
        if op in ACT_OPS and op != "notify" and d.get("var"):
            writes.add(d["var"])
        if isinstance(d.get("save"), list):
            writes.update(x for x in d["save"] if x)
    unset = sorted((reads & (set(cfg.get("vars", {})) | set(cfg.get("globals", {})))) - writes)
    for i, n in nodes.items():
        bv = (n.get("board") or {}).get("var")
        if bv and bv != "refs" and bv not in writes:
            out.append(f"leaderboard variable '{bv}' in node '{i}' is never increased by any action (add an 'add'/'set' action that changes it, or remove the board)")
    for i, n in nodes.items():
        if n.get("ticket") and not any("goto" in b for row in n["buttons"] for b in row) and not n.get("next"):
            out.append(f"ticket node '{i}' has no cancel/home button and no 'next' (users cannot leave it)")
    if unset:
        out.append("variables that are read but never set by any action or form 'save' (set them somewhere or remove them): " + ", ".join(unset[:6]))
    return out


class ThinkLang(ValueError):
    def __init__(self, cfg, ideas):
        super().__init__("thinking language mismatch")
        self.cfg, self.ideas = cfg, ideas


def llm_post(messages, max_tokens, temperature=0.4, timeout=120, model=None):
    """یک فراخوانی چت؛ (متن، (توکن ورودی، توکن خروجی)) برمی‌گردونه"""
    r = requests.post(
        f"{AI_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {AI_API_KEY}"},
        json={"model": model or AI_MODEL, "max_tokens": max_tokens, "temperature": temperature, "messages": messages},
        timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"AI HTTP {r.status_code}: {r.text[:300]}")
    try:
        j = r.json()
        txt = j["choices"][0]["message"]["content"] or ""
    except Exception:
        raise RuntimeError(f"AI پاسخ غیرمنتظره داد: {r.text[:300]}")
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()
    u = j.get("usage") or {}
    pt = int(u.get("prompt_tokens") or est_tokens("".join(str(m["content"]) for m in messages)))
    ct = int(u.get("completion_tokens") or est_tokens(txt))
    return txt, (pt, ct)


AI_STREAM = _int("AI_STREAM", 1)         # ۱ = ساخت ربات با استریم و پیشرفت زنده؛ ۰ = مثل قبل (یک درخواست بدون استریم)
_prog = threading.local()                # پیشرفت کار پس‌زمینه‌ی جاری (هر ترد مال خودش)


class _NoStream(Exception):
    """سرویس‌دهنده استریم رو قبول نکرد؛ بدون استریم ادامه می‌دیم"""


def live_info(text, fa_only):
    """از متنِ نیمه‌کاره‌ی JSON، توضیحِ در حال نوشته‌شدن و تعداد/عنوان بخش‌های ساخته‌شده رو درمیاره"""
    out = {"n": 0, "ti": "", "th": ""}
    m = re.search(r'"thinking"\s*:\s*"((?:[^"\\]|\\.)*)', text)
    if m:
        raw = m.group(1)
        if raw.endswith("\\"):
            raw = raw[:-1]
        try:
            th = json.loads('"' + raw + '"')
        except Exception:
            th = raw.replace("\\n", " ").replace('\\"', '"')
        th = th.strip()[:700]
        fa, la = _count(th)
        if th and not has_foreign(th) and not (fa_only and la > fa):
            out["th"] = th
    i = text.find('"nodes"')
    if i >= 0:
        titles = re.findall(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', text[i:])
        out["n"] = len(titles)
        if titles:
            try:
                t = json.loads('"' + titles[-1] + '"')
            except Exception:
                t = titles[-1]
            if t and not has_foreign(t):
                out["ti"] = t[:40]
    return out


class Progress:
    """پیشرفت زنده‌ی ساخت: متنِ در حال استریم رو تحلیل می‌کنه و (حداکثر هر ۰٫۷ ثانیه) توی job می‌نویسه تا مینی‌اپ نشون بده.
    درصد تخمینیه (بر پایه‌ی طول خروجی) و هیچ‌وقت قبل از تموم‌شدن واقعی به ۱۰۰ نمی‌رسه"""

    def __init__(self, jid):
        self.jid, self.fa, self.att, self.last = jid, False, 1, 0.0
        self.d = {"p": 2.0, "st": "analyze", "n": 0, "ti": "", "th": "", "att": 1}

    def flush(self, force=False):
        t = time.time()
        if not force and t - self.last < 0.7:
            return
        self.last = t
        try:
            db.jobs.update_one({"_id": self.jid, "status": {"$in": ["running", "saving"]}}, {"$set": {"prog": dict(self.d)}})
        except Exception:
            pass

    def stage(self, st, p=None):
        self.d["st"] = st
        if p is not None:
            self.d["p"] = max(self.d["p"], p)
        self.flush(True)

    def attempt(self, n):
        self.att = self.d["att"] = n
        self.d["st"] = "analyze" if n == 1 else "review"
        if n > 1:
            self.d["p"] = max(self.d["p"], 60.0)
        self.flush(True)

    def feed(self, text, reasoning=0):
        if time.time() - self.last < 0.7:
            return
        vis = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
        if "<think>" in vis:                       # مدل هنوز داخل بلوک فکر کردنه
            vis, reasoning = "", reasoning + len(text)
        info = live_info(vis, self.fa)
        tok = est_tokens(vis) if vis else 0
        sat = tok / (tok + 1800.0)
        if self.att == 1:
            p = 4 + 84 * sat if tok else 3 + min(8.0, reasoning / 900.0)
        else:
            p = 62 + 30 * sat
        self.d["p"] = round(max(self.d["p"], min(p, 94.0)), 1)
        self.d["n"] = max(self.d["n"], info["n"])
        if info["ti"]:
            self.d["ti"] = info["ti"]
        if info["th"]:
            self.d["th"] = info["th"]
        self.d["st"] = "review" if self.att > 1 else ("build" if self.d["n"] else "analyze")
        self.flush(True)


def llm_stream(messages, max_tokens, temperature, cb, timeout=225, model=None):
    """مثل llm_post ولی با استریم (SSE)؛ هر تکه‌ی رسیده به cb.feed داده می‌شه"""
    t0 = time.time()
    r = requests.post(
        f"{AI_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {AI_API_KEY}"},
        json={"model": model or AI_MODEL, "max_tokens": max_tokens, "temperature": temperature, "messages": messages,
              "stream": True, "stream_options": {"include_usage": True}},
        timeout=(10, 90), stream=True)
    try:
        if r.status_code >= 400:
            raise _NoStream(f"HTTP {r.status_code}: {r.text[:200]}")
        if "event-stream" not in (r.headers.get("content-type") or "").lower():     # سرویس‌دهنده استریم نکرد و جواب کامل داد
            j = r.json()
            txt = j["choices"][0]["message"]["content"] or ""
            u = j.get("usage") or {}
            txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()
            return txt, (int(u.get("prompt_tokens") or est_tokens("".join(str(m["content"]) for m in messages))),
                         int(u.get("completion_tokens") or est_tokens(txt)))
        parts, reasoning, usage = [], 0, None
        for raw in r.iter_lines():
            if time.time() - t0 > timeout:
                raise RuntimeError("AI timeout")
            if not raw:
                continue
            line = raw.decode("utf-8", "ignore")
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                j = json.loads(data)
            except Exception:
                continue
            if j.get("usage"):
                usage = j["usage"]
            d = ((j.get("choices") or [{}])[0].get("delta")) or {}
            piece = d.get("content")
            if piece:
                parts.append(piece)
            elif d.get("reasoning_content") or d.get("reasoning"):
                reasoning += len(d.get("reasoning_content") or d.get("reasoning") or "")
            cb.feed("".join(parts) if parts else "", reasoning)
    finally:
        r.close()
    txt = re.sub(r"<think>.*?</think>", "", "".join(parts), flags=re.S).strip()
    if not txt:
        raise RuntimeError("AI پاسخ خالی داد")
    u = usage or {}
    return txt, (int(u.get("prompt_tokens") or est_tokens("".join(str(m["content"]) for m in messages))),
                 int(u.get("completion_tokens") or est_tokens(txt)))


def llm_run(messages, max_tokens, temperature=0.4):
    """فراخوانی ساخت ربات: اگه پیشرفت زنده فعاله استریم می‌کنه، وگرنه (یا اگه استریم پشتیبانی نشه) مثل قبل"""
    cb = getattr(_prog, "cb", None)
    if not (cb and AI_STREAM):
        return llm_post(messages, max_tokens, temperature)
    try:
        return llm_stream(messages, max_tokens, temperature, cb)
    except _NoStream as e:
        log.warning("استریم پشتیبانی نشد، بدون استریم ادامه می‌دیم: %s", e)
        return llm_post(messages, max_tokens, temperature)


_gap = threading.local()          # گزارش «چیزی که ربات‌ساز نتونست»؛ هر کار پس‌زمینه در ترد خودش می‌خونه


def _take_gaps(raw):
    out = []
    for x in (raw if isinstance(raw, list) else [])[:3]:
        if isinstance(x, dict) and str(x.get("want") or "").strip():
            out.append({"want": str(x["want"]).strip()[:300], "why": str(x.get("why") or "").strip()[:500],
                        "upgrade": str(x.get("upgrade") or "").strip()[:600]})
    return out


def _call_llm(user, lang, final, media_ids, acc, guard=False, check_cfg=False, nodes_cap=None):
    txt, usage = llm_run([{"role": "system", "content": SYSTEM_PROMPT + (LANG_GUARD if guard else "")}, {"role": "user", "content": user}], AI_MAX_TOKENS)
    acc.append(usage)
    cb = getattr(_prog, "cb", None)
    if cb:
        cb.stage("validate", 95.0)
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError(f"پاسخ AI شامل JSON نبود: {txt[:200]!r}")
    raw = json.loads(m.group(0))
    if not isinstance(raw, dict) or not isinstance(raw.get("config"), dict):
        raise ValueError("پاسخ AI فاقد بخش config بود")
    gaps = _take_gaps(raw.get("unsupported"))
    warns = []
    cfg_foreign = guard and check_cfg and foreign_in(raw["config"])
    if guard:                                   # قبل از اعتبارسنجی پاک می‌کنیم تا دکمه/متن نیمه‌کاره نمونه
        raw["config"] = scrub_deep(raw["config"])
    cfg = sanitize(raw["config"], media=media_ids, warns=warns, nodes_cap=nodes_cap)
    thinking = str(raw.get("thinking") or "").strip()[:900]
    ideas = [str(x).strip()[:80] for x in (raw.get("ideas") if isinstance(raw.get("ideas"), list) else []) if str(x).strip()][:3]
    if lang == "fa":
        fa, la = _count(thinking)
        bad_lang = not thinking or la > fa or has_foreign(thinking)          # توضیح انگلیسی/خالی/چینی و ...
        if guard:
            bad_lang = bad_lang or foreign_in([ideas, gaps]) or cfg_foreign
        if bad_lang:
            if not final:
                raise ThinkLang(cfg, ideas)
            thinking = scrub_foreign(thinking) if (thinking and la <= fa) else ""
            if _count(thinking)[0] < 12:
                thinking = FALLBACK_THINKING
        if guard:                               # آخرین خط دفاعی: هر نویسه‌ی غیرفارسی باقی‌مونده حذف می‌شه
            ideas, gaps = [x for x in scrub_deep(ideas) if x], [g for g in scrub_deep(gaps) if g.get("want")]
    _gap.items = gaps
    return thinking, cfg, ideas, warns


def media_brief(items):
    """فهرست رسانه‌های کاربر برای هوش مصنوعی"""
    return json.dumps([{"id": m["id"], "kind": m["kind"], "name": m["name"]} for m in items], ensure_ascii=False)


def build_user(prompt, current, lang, media_items, note_extra=""):
    if lang == "fa":
        note = "OUTPUT LANGUAGE: Persian (فارسی). The \"thinking\" and \"ideas\" fields and all node texts/button labels MUST be written in Persian. Do not write them in English."
    else:
        note = "OUTPUT LANGUAGE: the same language as the user's request below (\"thinking\" and \"ideas\" included)."
    if note_extra:
        note += " " + note_extra
    parts = [note, "MEDIA LIBRARY (ids you may use in node.media / node.done_media): " + (media_brief(media_items) if media_items else "empty")]
    if current:
        parts.append("Current config:\n" + json.dumps(current, ensure_ascii=False))
        parts.append("Change request:\n" + prompt)
    else:
        parts.append("Bot request:\n" + prompt)
    parts.append("Reminder: reply with the JSON object only; " +
                 ("\"thinking\" and \"ideas\" in Persian." if lang == "fa" else "\"thinking\" and \"ideas\" in the request's language."))
    return "\n\n".join(parts)


def ask_llm(prompt, current=None, media_items=(), acc=None, nodes_cap=None):
    """یک بار تلاش اول؛ اگه خروجی خراب بود، زبان توضیح اشتباه بود یا کانفیگ مشکل منطقی داشت، یک بار با بازخورد دوباره.
    acc = فهرست مصرف (توکن ورودی/خروجی) هر فراخوانی؛ برای محاسبه‌ی هزینه‌ی واقعی
    nodes_cap = سقف بخش‌های ربات (پلن‌محور)"""
    acc = [] if acc is None else acc
    lang = detect_lang(prompt)
    guard = lang == "fa" and not has_foreign(prompt)          # کاربر خودش متن غیرفارسی ننوشته → خروجی فقط فارسی
    check_cfg = guard and not foreign_in(current)             # اگه ربات فعلی از قبل نویسه‌ی بیگانه داره، فقط پاکش می‌کنیم
    media_ids = {m["id"] for m in media_items}
    best, last, feedback = None, None, ""
    cb = getattr(_prog, "cb", None)
    if cb:
        cb.fa = lang == "fa"
    for attempt in (0, 1):
        if cb:
            cb.attempt(attempt + 1)
        try:
            thinking, cfg, ideas, warns = _call_llm(build_user(prompt, current, lang, media_items, feedback), lang, attempt == 1, media_ids, acc, guard, check_cfg, nodes_cap)
        except ThinkLang as e:
            best, last = best or ("", e.cfg, e.ideas), e
            feedback = "(Your previous answer used the wrong language or contained foreign-script characters (Chinese/Japanese/Korean/Russian...) in \"thinking\", \"ideas\", \"unsupported\" or node texts. Rewrite EVERYTHING in Persian only, with no foreign characters.)"
            log.warning("thinking in wrong language, retrying")
            continue
        except (ValueError, KeyError, TypeError) as e:   # خروجی خراب → یک بار دیگه
            last = e
            feedback = f"(Your previous reply was rejected: {str(e)[:200]}. Return one valid JSON object.)"
            log.warning("bad AI output, retrying once", exc_info=True)
            continue
        problems = lint(cfg) + [f"the validator dropped or changed something: {w}" for w in warns]
        if problems and attempt == 0:
            best = (thinking, cfg, ideas)
            feedback = "(Your previous config had logic problems, fix them and return the FULL config again: " + "; ".join(problems[:6]) + ")"
            log.info("lint problems, retrying: %s", problems)
            continue
        return thinking, cfg, ideas
    if best:                        # کانفیگ سالمِ تلاش اول رو نگه می‌داریم
        th, cfg, ideas = best
        return (th or FALLBACK_THINKING), cfg, ideas
    raise last


ENHANCE_PROMPT = ("You are a product designer who briefs a Telegram-bot builder. Rewrite the user's rough bot idea into a clear, concrete brief "
                  "in the SAME language as the idea (Persian stays Persian). Structure it in plain sentences: purpose, sections/menus, forms or data to collect, "
                  "smart features worth adding (AI assistant, points, invites, forced channel join, media) only if they fit. "
                  "Keep every fact the user gave (names, prices, links). Never invent prices, phone numbers or links; use placeholders like [قیمت]. "
                  "Max 900 characters. No markdown, no headings, no lists with symbols. Output only the brief.")


def enhance_prompt(prompt):
    guard = detect_lang(prompt) == "fa" and not has_foreign(prompt)
    txt, _ = llm_post([{"role": "system", "content": ENHANCE_PROMPT + (LANG_GUARD if guard else "")}, {"role": "user", "content": prompt[:MAX_PROMPT]}],
                      700, temperature=0.6, timeout=60, model=AI_CHAT_MODEL)
    txt = (scrub_foreign(txt) if guard else txt).strip().strip('"').strip()
    if len(txt) < 10:
        raise ValueError("empty enhance")
    return txt[:MAX_PROMPT]


# ───────────────────────── برآورد هزینه‌ی ساخت ─────────────────────────
def reserve_cost(prompt, current, uid=None):
    """مبلغی که قبل از شروع کار رزرو می‌شه؛ هزینه‌ی نهایی از این بیشتر نمی‌شه"""
    if BILLING == "fixed":
        return cut(uid, EDIT_COST if current else GEN_COST)
    p = est_tokens(SYSTEM_PROMPT) + est_tokens(prompt) + (est_tokens(json.dumps(current, ensure_ascii=False)) if current else 0) + 600
    return calc_cost(p * 2, min(AI_MAX_TOKENS, 5000), uid=uid)      # ×۲ چون ممکنه یک بار دوباره‌کاری بشه


def typical_cost():
    return GEN_COST if BILLING == "fixed" else calc_cost(est_tokens(SYSTEM_PROMPT) + 400, 2400)


# ───────────────────────── قالب‌های آماده (۵ قالب اصلی، دوزبانه) ─────────────────────────
def _b(text, goto=None, **kw):
    d = {"text": text}
    if goto:
        d["goto"] = goto
    d.update(kw)
    return d


def _L(fa, en):
    """متن دوزبانه: (فارسی، انگلیسی)؛ _bilingual برای هر زبان یک شاخه‌ی جدا می‌سازه"""
    return (fa, en)


SHARED_IDS = ("start", "lang")


def _tr(x, i, pre):
    if isinstance(x, tuple):
        return x[i]
    if isinstance(x, list):
        return [_tr(v, i, pre) for v in x]
    if isinstance(x, dict):
        o = {}
        for k, v in x.items():
            if k in ("goto", "next") and isinstance(v, str) and v not in SHARED_IDS:
                v = pre + v                       # مقصد دکمه/مسیر/یادآور در شاخه‌ی همین زبان
            o[k] = _tr(v, i, pre)
        return o
    return x


_UI = lambda v: {"var": "ui", "op": "==", "value": v}
_PICK_TEXT = "<b>🌐 زبان خودت رو انتخاب کن</b>\n<b>Please choose your language</b>"


def _picker():
    return [[_b("🇮🇷 فارسی", "home", do=[{"op": "set", "var": "ui", "value": "fa"}])],
            [_b("🇬🇧 English", "en_home", do=[{"op": "set", "var": "ui", "value": "en"}])]]


def _bilingual(name, nodes, vars=None, **extra):
    out = {}
    for nid, n in nodes.items():
        out[nid] = _tr(n, 0, "")
        out["en_" + nid] = _tr(n, 1, "en_")
    out["start"] = {"title": "Language · زبان", "text": _PICK_TEXT, "buttons": _picker(),
                    "route": [{"when": _UI("fa"), "goto": "home"}, {"when": _UI("en"), "goto": "en_home"}]}
    out["lang"] = {"title": "Language · زبان", "text": _PICK_TEXT, "buttons": _picker(), "do": [{"op": "clear", "var": "ui"}]}
    cfg = {"name": name, "start": "start", "fallback": "start", "commands": {"menu": "start", "lang": "lang"},
           "vars": dict({"ui": ""}, **(vars or {}))}
    cfg.update(extra)
    cfg["nodes"] = out
    return cfg


def _home():
    return [_b(_L("↩️ منوی اصلی", "↩️ Main menu"), "home")]


_LANGBTN = lambda: _b(_L("🌐 زبان", "🌐 Language"), "lang")
_CH = "https://t.me/your_channel"
_NOTE_LANG = " ربات دوزبانه‌ست (فارسی و English)؛ اگه فقط یه زبان لازم داری، شاخه‌ی زبان دیگه (بخش‌هایی که با en_ شروع می‌شن) و دکمه‌ی «زبان» رو حذف کن."

# ═══════════ ۱) فروشگاه ═══════════
_SHOP = {
    "home": {"title": _L("منوی اصلی", "Main menu"),
        "text": _L("<b>🛍 به [نام فروشگاه] خوش اومدی، {name}!</b>\n\nاینجا بهترین‌ها رو با ارسال سریع و ضمانت اصالت پیدا می‌کنی.\n\n<blockquote>🚚 ارسال به سراسر کشور\n✅ ضمانت اصالت کالا\n💬 پشتیبانی همیشه کنارته</blockquote>\nاز منوی زیر شروع کن 👇",
                   "<b>🛍 Welcome to [Store name], {name}!</b>\n\nFind the best products with fast delivery and guaranteed authenticity.\n\n<blockquote>🚚 Nationwide delivery\n✅ Authenticity guaranteed\n💬 Support always at your side</blockquote>\nStart from the menu below 👇"),
        "alt": [{"when": {"var": "visits", "op": ">", "value": "1"},
                 "text": _L("<b>خوش برگشتی {name}! 👋</b>\n\nامروز دنبال چی هستی؟ تازه‌ترین‌ها و تخفیف‌ها منتظرتن.\n\n<blockquote>🚚 ارسال سریع · ✅ ضمانت اصالت · 💬 پشتیبانی</blockquote>",
                            "<b>Welcome back, {name}! 👋</b>\n\nWhat are you looking for today? New arrivals and deals are waiting.\n\n<blockquote>🚚 Fast delivery · ✅ Authentic · 💬 Support</blockquote>")}],
        "buttons": [[_b(_L("🛍 محصولات", "🛍 Products"), "products"), _b(_L("🧾 ثبت سفارش", "🧾 Place order"), "order")],
                    [_b(_L("📦 پیگیری سفارش", "📦 Track order"), "track"), _b(_L("❓ سؤالات متداول", "❓ FAQ"), "faq")],
                    [_b(_L("☎️ تماس با ما", "☎️ Contact"), "contact"), _LANGBTN()]]},
    "products": {"title": _L("محصولات", "Products"),
        "text": _L("<b>🛍 محصولات ما</b>\n\nیک دسته رو انتخاب کن:", "<b>🛍 Our products</b>\n\nPick a category:"),
        "buttons": [[_b(_L("🔥 پرفروش‌ها", "🔥 Best sellers"), "best"), _b(_L("🏷 تخفیف‌ها", "🏷 Deals"), "deals")],
                    [_b(_L("🆕 جدیدترین‌ها", "🆕 New arrivals"), "fresh")], _home()]},
    "best": {"title": _L("پرفروش‌ها", "Best sellers"),
        "text": _L("<b>🔥 پرفروش‌ها</b>\n\n1️⃣ [نام محصول اول] — <b>[قیمت] تومان</b>\n2️⃣ [نام محصول دوم] — <b>[قیمت] تومان</b>\n3️⃣ [نام محصول سوم] — <b>[قیمت] تومان</b>\n\n<i>برای خرید، «ثبت سفارش» رو بزن و اسم محصول رو بنویس.</i>",
                   "<b>🔥 Best sellers</b>\n\n1️⃣ [Product one] — <b>[price]</b>\n2️⃣ [Product two] — <b>[price]</b>\n3️⃣ [Product three] — <b>[price]</b>\n\n<i>To buy, tap “Place order” and write the product name.</i>"),
        "buttons": [[_b(_L("🧾 ثبت سفارش", "🧾 Place order"), "order")], [_b(_L("↩️ دسته‌ها", "↩️ Categories"), "products"), _home()[0]]]},
    "deals": {"title": _L("تخفیف‌ها", "Deals"),
        "text": _L("<b>🏷 تخفیف‌های ویژه</b>\n\n1️⃣ [محصول] — <s>[قیمت قبل]</s> ➜ <b>[قیمت جدید] تومان</b>\n2️⃣ [محصول] — <s>[قیمت قبل]</s> ➜ <b>[قیمت جدید] تومان</b>\n\n<blockquote>⏳ تا [تاریخ پایان] فرصت داری.</blockquote>",
                   "<b>🏷 Special deals</b>\n\n1️⃣ [Product] — <s>[old price]</s> ➜ <b>[new price]</b>\n2️⃣ [Product] — <s>[old price]</s> ➜ <b>[new price]</b>\n\n<blockquote>⏳ Offer ends [end date].</blockquote>"),
        "buttons": [[_b(_L("🧾 ثبت سفارش", "🧾 Place order"), "order")], [_b(_L("↩️ دسته‌ها", "↩️ Categories"), "products"), _home()[0]]]},
    "fresh": {"title": _L("جدیدترین‌ها", "New arrivals"),
        "text": _L("<b>🆕 تازه رسیده‌ها</b>\n\n1️⃣ [محصول جدید] — <b>[قیمت] تومان</b>\n2️⃣ [محصول جدید] — <b>[قیمت] تومان</b>\n3️⃣ [محصول جدید] — <b>[قیمت] تومان</b>",
                   "<b>🆕 Just arrived</b>\n\n1️⃣ [New product] — <b>[price]</b>\n2️⃣ [New product] — <b>[price]</b>\n3️⃣ [New product] — <b>[price]</b>"),
        "buttons": [[_b(_L("🧾 ثبت سفارش", "🧾 Place order"), "order")], [_b(_L("↩️ دسته‌ها", "↩️ Categories"), "products"), _home()[0]]]},
    "order": {"title": _L("ثبت سفارش", "Place order"),
        "text": _L("<b>🧾 ثبت سفارش</b>\n\nچند تا سؤال کوتاه ازت می‌پرسم تا سفارشت ثبت بشه.", "<b>🧾 Place your order</b>\n\nI'll ask a few short questions to register your order."),
        "fields": _L(["اسم و فامیلت؟", "شماره تماست؟", "چه محصولی می‌خوای؟ (اسم، تعداد، رنگ یا سایز)", "آدرس کامل برای ارسال؟"],
                     ["Your full name?", "Your phone number?", "What would you like to order? (name, quantity, colour or size)", "Full delivery address?"]),
        "save": ["cname", "cphone", "", ""], "types": ["text", "phone", "text", "text"], "ticket": True, "tag": "سفارش",
        "done": _L("<b>✅ سفارشت ثبت شد</b>\nشماره پیگیری: <code>#{ticket_no}</code>\nبه‌زودی برای تأیید و پرداخت باهات تماس می‌گیریم.",
                   "<b>✅ Your order is registered</b>\nTracking number: <code>#{ticket_no}</code>\nWe'll contact you shortly to confirm and arrange payment."),
        "next": "thanks", "buttons": [[_b(_L("↩️ انصراف", "↩️ Cancel"), "home")]]},
    "thanks": {"title": _L("ممنون از سفارشت", "Thank you"),
        "text": _L("<b>🙏 ممنون از اعتمادت، {cname|دوست من}!</b>\n\nسفارشت در صف بررسیه و پاسخ رو همین‌جا برات می‌فرستیم.", "<b>🙏 Thank you for trusting us, {cname|friend}!</b>\n\nYour order is being reviewed and we'll reply right here."),
        "do": [{"op": "remind", "minutes": 2880, "key": "fb", "goto": "feedback",
                "value": _L("سلام {name} 👋 سفارشت چطور بود؟ یه امتیاز بده تا بهتر بشیم.", "Hi {name} 👋 how was your order? Rate us so we can improve.")}],
        "buttons": [[_b(_L("📦 پیگیری سفارش", "📦 Track order"), "track")], _home()]},
    "feedback": {"title": _L("امتیاز به فروشگاه", "Rate us"),
        "text": _L("<b>⭐ نظرت درباره‌ی خریدت؟</b>\n\nیه امتیاز بده:", "<b>⭐ How was your purchase?</b>\n\nGive us a rating:"),
        "buttons": [[_b("⭐⭐⭐⭐⭐", "rated", do=[{"op": "notify", "value": "امتیاز ۵ از ۵ از طرف {name}"}]),
                     _b("⭐⭐⭐⭐", "rated", do=[{"op": "notify", "value": "امتیاز ۴ از ۵ از طرف {name}"}])],
                    [_b("⭐⭐⭐", "rated", do=[{"op": "notify", "value": "امتیاز ۳ از ۵ از طرف {name}"}]),
                     _b("⭐⭐", "rated", do=[{"op": "notify", "value": "امتیاز ۲ از ۵ از طرف {name}"}]),
                     _b("⭐", "rated", do=[{"op": "notify", "value": "امتیاز ۱ از ۵ از طرف {name}"}])]]},
    "rated": {"title": _L("ممنون از نظرت", "Thanks for rating"),
        "text": _L("<b>💚 ممنون از بازخوردت!</b>\nبرای مشکل یا پیشنهاد، همین‌جا پیام بده.", "<b>💚 Thanks for your feedback!</b>\nFor any issue or suggestion, message us right here."),
        "buttons": [[_b(_L("💬 ارسال پیام", "💬 Send a message"), "msg")], _home()]},
    "track": {"title": _L("پیگیری سفارش", "Track order"),
        "text": _L("<b>📦 پیگیری سفارش</b>\n\nشماره‌ی پیگیری سفارشت (مثل <code>#12</code>) یا شماره تماست رو بفرست تا وضعیتش رو بررسی کنیم.",
                   "<b>📦 Track your order</b>\n\nSend your tracking number (like <code>#12</code>) or your phone number and we'll check its status."),
        "ask": True, "ticket": True, "tag": "پیگیری",
        "done": _L("درخواستت ثبت شد (تیکت #{ticket_no}). نتیجه رو همین‌جا می‌فرستیم.", "Request received (ticket #{ticket_no}). We'll reply right here."),
        "next": "home", "buttons": [[_b(_L("↩️ انصراف", "↩️ Cancel"), "home")]]},
    "faq": {"title": _L("سؤالات متداول", "FAQ"),
        "text": _L("<b>❓ سؤالات متداول</b>\n\nروی هر مورد بزن:", "<b>❓ Frequently asked questions</b>\n\nTap any item:"),
        "buttons": [[_b(_L("🚚 زمان و هزینه‌ی ارسال", "🚚 Delivery time and cost"), alert=_L("[زمان تحویل و هزینه‌ی ارسال رو اینجا بنویس]", "[Write delivery time and cost here]"))],
                    [_b(_L("💳 روش‌های پرداخت", "💳 Payment methods"), alert=_L("[روش‌های پرداخت رو اینجا بنویس]", "[Write payment methods here]"))],
                    [_b(_L("🔄 مرجوعی و تعویض", "🔄 Returns and exchanges"), alert=_L("[شرایط مرجوعی رو اینجا بنویس]", "[Write your return policy here]"))],
                    _home()]},
    "contact": {"title": _L("تماس با ما", "Contact"),
        "text": _L("<b>☎️ تماس با ما</b>\n\n📞 [شماره تماس]\n📍 [آدرس]\n🕘 [ساعت کاری]\n\n<i>پشتیبانی تلگرامی هم همین‌جاست؛ «ارسال پیام» رو بزن.</i>",
                   "<b>☎️ Contact us</b>\n\n📞 [Phone]\n📍 [Address]\n🕘 [Working hours]\n\n<i>Telegram support is right here too; tap “Send a message”.</i>"),
        "buttons": [[_b(_L("📋 کپی شماره", "📋 Copy phone"), copy="[شماره تماس]"), _b(_L("📣 کانال ما", "📣 Our channel"), url=_CH)],
                    [_b(_L("💬 ارسال پیام", "💬 Send a message"), "msg")], _home()]},
    "msg": {"title": _L("پیام به پشتیبانی", "Message support"),
        "text": _L("<b>💬 پیام به پشتیبانی</b>\n\nسؤال یا مشکلت رو بنویس؛ مستقیم برای تیم ما می‌رسه.", "<b>💬 Message support</b>\n\nWrite your question or issue; it goes straight to our team."),
        "ask": True, "ticket": True, "tag": "پشتیبانی",
        "done": _L("پیامت ثبت شد (تیکت #{ticket_no}). به‌زودی همین‌جا جواب می‌دیم.", "Message received (ticket #{ticket_no}). We'll reply right here soon."),
        "next": "home", "buttons": [[_b(_L("↩️ انصراف", "↩️ Cancel"), "home")]]},
}

# ═══════════ ۲) پشتیبانی ═══════════
_OPEN = {"all": [{"var": "hour", "op": ">=", "value": "9"}, {"var": "hour", "op": "<", "value": "21"}]}


def _faq_page(title_fa, title_en, qa_fa, qa_en):
    return {"title": _L(title_fa, title_en),
            "text": _L(f"<b>{title_fa}</b>\n\n{qa_fa}", f"<b>{title_en}</b>\n\n{qa_en}"),
            "buttons": [[_b(_L("🎫 هنوز جواب نگرفتم", "🎫 Still need help"), "ticket")],
                        [_b(_L("↩️ دسته‌ها", "↩️ Topics"), "faq"), _home()[0]]]}


def _dept(tag, fa, en):
    return {"title": _L(fa, en), "text": _L(f"<b>🎫 {fa}</b>\n\nمشکل یا سؤالت رو کامل بنویس؛ هر چی جزئیات بیشتر، سریع‌تر جواب می‌گیری. عکس و فایل هم می‌تونی بفرستی.",
                                             f"<b>🎫 {en}</b>\n\nDescribe your issue in detail; the more detail, the faster the answer. You can send photos and files too."),
            "ask": True, "ticket": True, "tag": tag,
            "done": _L("<b>✅ درخواستت ثبت شد</b>\nکد پیگیری: <code>#{ticket_no}</code>\nجواب رو همین‌جا برات می‌فرستیم.",
                       "<b>✅ Your request is registered</b>\nReference: <code>#{ticket_no}</code>\nWe'll reply right here."),
            "next": "home", "buttons": [[_b(_L("↩️ انصراف", "↩️ Cancel"), "ticket")]]}


def _rate(n, fa, en):
    return _b(_L(fa, en), "rated", do=[{"op": "notify", "value": "رضایت از پشتیبانی: " + n + " (از طرف {name})"}])


_SUPPORT = {
    "home": {"title": _L("منوی اصلی", "Main menu"),
        "text": _L("<b>🎧 مرکز پشتیبانی</b>\nسلام {name}! 👋\n\n🔴 <b>الان خارج از ساعت کاری هستیم</b> (۹ تا ۲۱)؛ پیامت رو بذار، اولین فرصت جواب می‌دیم.\n\nچطور می‌تونیم کمکت کنیم؟",
                   "<b>🎧 Support center</b>\nHi {name}! 👋\n\n🔴 <b>We're outside working hours</b> (9:00–21:00 Tehran); leave your message and we'll reply as soon as we can.\n\nHow can we help you?"),
        "alt": [{"when": _OPEN, "text": _L("<b>🎧 مرکز پشتیبانی</b>\nسلام {name}! 👋\n\n🟢 <b>الان آنلاین هستیم</b> و معمولاً ظرف چند دقیقه جواب می‌دیم.\n\nچطور می‌تونیم کمکت کنیم؟",
                                            "<b>🎧 Support center</b>\nHi {name}! 👋\n\n🟢 <b>We're online</b> and usually reply within minutes.\n\nHow can we help you?")}],
        "buttons": [[_b(_L("❓ سؤالات متداول", "❓ FAQ"), "faq"), _b(_L("🎫 ارسال درخواست", "🎫 New request"), "ticket")],
                    [_b(_L("🔎 پیگیری درخواست", "🔎 Track request"), "status"), _b(_L("📞 راه‌های تماس", "📞 Contact"), "contact")],
                    [_b(_L("⭐ نظرسنجی", "⭐ Feedback"), "rate"), _LANGBTN()]]},
    "faq": {"title": _L("سؤالات متداول", "FAQ"),
        "text": _L("<b>❓ سؤالات متداول</b>\n\nموضوع مورد نظرت رو انتخاب کن:", "<b>❓ Frequently asked questions</b>\n\nChoose a topic:"),
        "buttons": [[_b(_L("💳 پرداخت و فاکتور", "💳 Payment and invoices"), "faq_pay")],
                    [_b(_L("🚚 ارسال و تحویل", "🚚 Delivery"), "faq_ship")],
                    [_b(_L("🔧 مشکلات فنی", "🔧 Technical issues"), "faq_tech")], _home()]},
    "faq_pay": _faq_page("💳 پرداخت و فاکتور",
        "💳 Payment and invoices",
        "<b>چه روش‌هایی برای پرداخت دارید؟</b>\n[پاسخ رو اینجا بنویس]\n\n<b>فاکتور رسمی صادر می‌کنید؟</b>\n[پاسخ رو اینجا بنویس]\n\n<b>اگه پرداخت ناموفق بود چی؟</b>\n[بازه‌ی برگشت وجه و راهنمای پیگیری]",
        "<b>Which payment methods do you accept?</b>\n[Write the answer here]\n\n<b>Do you issue official invoices?</b>\n[Write the answer here]\n\n<b>What if a payment fails?</b>\n[Refund window and how to follow up]"),
    "faq_ship": _faq_page("🚚 ارسال و تحویل",
        "🚚 Delivery",
        "<b>ارسال چقدر طول می‌کشه؟</b>\n[پاسخ رو اینجا بنویس]\n\n<b>هزینه‌ی ارسال چقدره؟</b>\n[پاسخ رو اینجا بنویس]\n\n<b>کد رهگیری کجا می‌آد؟</b>\n[پاسخ رو اینجا بنویس]",
        "<b>How long does delivery take?</b>\n[Write the answer here]\n\n<b>How much is shipping?</b>\n[Write the answer here]\n\n<b>Where do I get the tracking code?</b>\n[Write the answer here]"),
    "faq_tech": _faq_page("🔧 مشکلات فنی",
        "🔧 Technical issues",
        "<b>وارد حسابم نمی‌شم، چیکار کنم؟</b>\n[پاسخ رو اینجا بنویس]\n\n<b>برنامه یا سرویس درست کار نمی‌کنه.</b>\n[پاسخ رو اینجا بنویس]\n\n<i>اگه مشکلت حل نشد، درخواست ثبت کن؛ تیم فنی بررسی می‌کنه.</i>",
        "<b>I can't log in, what should I do?</b>\n[Write the answer here]\n\n<b>The app or service isn't working properly.</b>\n[Write the answer here]\n\n<i>If it's still not solved, open a request; our technical team will look into it.</i>"),
    "ticket": {"title": _L("ارسال درخواست", "New request"),
        "text": _L("<b>🎫 ارسال درخواست</b>\n\nدرخواستت مربوط به کدوم بخشه؟", "<b>🎫 New request</b>\n\nWhich team is your request for?"),
        "buttons": [[_b(_L("💰 فروش و قیمت", "💰 Sales and pricing"), "t_sales")], [_b(_L("🔧 فنی", "🔧 Technical"), "t_tech")],
                    [_b(_L("🧾 مالی و پرداخت", "🧾 Billing"), "t_bill")], _home()]},
    "t_sales": _dept("فروش", "فروش و قیمت", "Sales and pricing"),
    "t_tech": _dept("فنی", "پشتیبانی فنی", "Technical support"),
    "t_bill": _dept("مالی", "مالی و پرداخت", "Billing"),
    "status": {"title": _L("پیگیری درخواست", "Track request"),
        "text": _L("<b>🔎 پیگیری درخواست</b>\n\nکد درخواستت (مثل <code>#12</code>) رو بفرست تا وضعیتش رو بررسی کنیم.", "<b>🔎 Track your request</b>\n\nSend your reference (like <code>#12</code>) and we'll check its status."),
        "ask": True, "ticket": True, "tag": "پیگیری",
        "done": _L("ثبت شد (تیکت #{ticket_no}). نتیجه رو همین‌جا می‌فرستیم.", "Received (ticket #{ticket_no}). We'll reply right here."),
        "next": "home", "buttons": [[_b(_L("↩️ انصراف", "↩️ Cancel"), "home")]]},
    "contact": {"title": _L("راه‌های تماس", "Contact"),
        "text": _L("<b>📞 راه‌های تماس</b>\n\n📞 [شماره تماس]\n✉️ [ایمیل]\n🕘 [ساعت کاری: ۹ تا ۲۱]\n\n<i>سریع‌ترین راه، ثبت درخواست همین‌جاست.</i>",
                   "<b>📞 Contact</b>\n\n📞 [Phone]\n✉️ [Email]\n🕘 [Working hours: 9:00–21:00]\n\n<i>The fastest way is to open a request right here.</i>"),
        "buttons": [[_b(_L("📋 کپی ایمیل", "📋 Copy email"), copy="[ایمیل]"), _b(_L("📣 کانال ما", "📣 Our channel"), url=_CH)],
                    [_b(_L("🎫 ارسال درخواست", "🎫 New request"), "ticket")], _home()]},
    "rate": {"title": _L("نظرسنجی", "Feedback"),
        "text": _L("<b>⭐ از پشتیبانی راضی بودی؟</b>\n\nبازخوردت به ما کمک می‌کنه بهتر بشیم:", "<b>⭐ Happy with our support?</b>\n\nYour feedback helps us improve:"),
        "buttons": [[_rate("عالی", "😍 عالی", "😍 Great"), _rate("خوب", "🙂 خوب", "🙂 Good"), _rate("ضعیف", "😕 ضعیف", "😕 Poor")], _home()]},
    "rated": {"title": _L("ممنون", "Thanks"),
        "text": _L("<b>💚 ممنون از بازخوردت!</b>", "<b>💚 Thanks for your feedback!</b>"), "buttons": [_home()]},
}

# ═══════════ ۳) رزرو نوبت ═══════════
_BOOKING = {
    "home": {"title": _L("منوی اصلی", "Main menu"),
        "text": _L("<b>📅 رزرو آنلاین نوبت</b>\nسلام {name}! 👋\n\nبدون معطلی و تماس تلفنی، نوبتت رو همین‌جا رزرو کن.\n\n<blockquote>🕘 [ساعت کاری]\n📍 [آدرس کوتاه]</blockquote>",
                   "<b>📅 Online booking</b>\nHi {name}! 👋\n\nBook your appointment right here, no phone calls and no waiting.\n\n<blockquote>🕘 [Working hours]\n📍 [Short address]</blockquote>"),
        "alt": [{"when": {"var": "cname", "op": "filled"},
                 "text": _L("<b>📅 رزرو آنلاین نوبت</b>\nخوش برگشتی {cname}! 👋\n\nآماده‌ای نوبت بعدی رو رزرو کنی؟\n\n<blockquote>🕘 [ساعت کاری]\n📍 [آدرس کوتاه]</blockquote>",
                            "<b>📅 Online booking</b>\nWelcome back, {cname}! 👋\n\nReady to book your next appointment?\n\n<blockquote>🕘 [Working hours]\n📍 [Short address]</blockquote>")}],
        "buttons": [[_b(_L("💈 خدمات و تعرفه", "💈 Services and prices"), "services"), _b(_L("📅 رزرو نوبت", "📅 Book now"), "book")],
                    [_b(_L("📍 آدرس و ساعت کاری", "📍 Location and hours"), "location"), _b(_L("✏️ لغو یا تغییر نوبت", "✏️ Cancel or change"), "change")],
                    [_LANGBTN()]]},
    "services": {"title": _L("خدمات و تعرفه", "Services and prices"),
        "text": _L("<b>💈 خدمات و تعرفه</b>\n\n1️⃣ [خدمت اول] — ⏱ [مدت] — <b>[قیمت] تومان</b>\n2️⃣ [خدمت دوم] — ⏱ [مدت] — <b>[قیمت] تومان</b>\n3️⃣ [خدمت سوم] — ⏱ [مدت] — <b>[قیمت] تومان</b>\n\n<i>قیمت‌ها ممکنه بسته به شرایط کمی تغییر کنه.</i>",
                   "<b>💈 Services and prices</b>\n\n1️⃣ [Service one] — ⏱ [duration] — <b>[price]</b>\n2️⃣ [Service two] — ⏱ [duration] — <b>[price]</b>\n3️⃣ [Service three] — ⏱ [duration] — <b>[price]</b>\n\n<i>Prices may vary slightly depending on the case.</i>"),
        "buttons": [[_b(_L("📅 رزرو نوبت", "📅 Book now"), "book")], [_b(_L("📜 قوانین رزرو", "📜 Booking rules"), "rules"), _home()[0]]]},
    "rules": {"title": _L("قوانین رزرو", "Booking rules"),
        "text": _L("<b>📜 قوانین رزرو</b>\n\n<blockquote>• لطفاً ۱۰ دقیقه زودتر برسید.\n• لغو نوبت حداقل [مدت] ساعت قبل اعلام بشه.\n• [قانون دیگر]</blockquote>",
                   "<b>📜 Booking rules</b>\n\n<blockquote>• Please arrive 10 minutes early.\n• Cancel at least [hours] hours in advance.\n• [Another rule]</blockquote>"),
        "buttons": [[_b(_L("📅 رزرو نوبت", "📅 Book now"), "book")], _home()]},
    "book": {"title": _L("رزرو نوبت", "Book now"),
        "text": _L("<b>📅 رزرو نوبت</b>\n\nچند تا سؤال کوتاه ازت می‌پرسم تا نوبتت ثبت بشه.", "<b>📅 Book your appointment</b>\n\nI'll ask a few short questions to register your booking."),
        "fields": _L(["اسم و فامیلت؟", "شماره تماست؟", "کدوم خدمت رو می‌خوای؟", "چه روزی برات مناسبه؟ (مثلاً شنبه ۱۰ آبان)", "چه ساعتی؟ (مثلاً ۱۷:۳۰)"],
                     ["Your full name?", "Your phone number?", "Which service would you like?", "Which day suits you? (e.g. Saturday, 1 Nov)", "What time? (e.g. 5:30 pm)"]),
        "save": ["cname", "cphone", "", "", ""], "types": ["text", "phone", "text", "text", "text"], "ticket": True, "tag": "رزرو",
        "done": _L("<b>✅ درخواست نوبتت ثبت شد</b>\nکد پیگیری: <code>#{ticket_no}</code>\nبعد از هماهنگی زمان، تأیید رو همین‌جا می‌فرستیم.",
                   "<b>✅ Your booking request is registered</b>\nReference: <code>#{ticket_no}</code>\nOnce the time is confirmed we'll message you right here."),
        "next": "booked", "buttons": [[_b(_L("↩️ انصراف", "↩️ Cancel"), "home")]]},
    "booked": {"title": _L("ثبت شد", "Booked"),
        "text": _L("<b>🎉 {cname|دوست من} عزیز، درخواستت رسید!</b>\n\nهمکارهای ما زمان رو چک می‌کنن و برات تأیید می‌فرستن. اگه لازم شد تغییری بدی، از «لغو یا تغییر نوبت» استفاده کن.",
                   "<b>🎉 Got it, {cname|friend}!</b>\n\nOur team is checking the time slot and will confirm shortly. If you need to change something, use “Cancel or change”."),
        "buttons": [[_b(_L("📍 آدرس و ساعت کاری", "📍 Location and hours"), "location")], _home()]},
    "location": {"title": _L("آدرس و ساعت کاری", "Location and hours"),
        "text": _L("<b>📍 آدرس و ساعت کاری</b>\n\n📍 [آدرس کامل]\n🕘 [ساعت کاری]\n📞 [شماره تماس]\n\n<i>پارکینگ و راهنمای مسیر: [توضیح]</i>",
                   "<b>📍 Location and hours</b>\n\n📍 [Full address]\n🕘 [Working hours]\n📞 [Phone]\n\n<i>Parking and directions: [details]</i>"),
        "buttons": [[_b(_L("📋 کپی شماره", "📋 Copy phone"), copy="[شماره تماس]"), _b(_L("🗺 مسیریابی", "🗺 Directions"), url="https://maps.google.com")], _home()]},
    "change": {"title": _L("لغو یا تغییر نوبت", "Cancel or change"),
        "text": _L("<b>✏️ لغو یا تغییر نوبت</b>\n\nکد پیگیری نوبتت (یا شماره تماست) و تغییر مورد نظرت رو بنویس.", "<b>✏️ Cancel or change a booking</b>\n\nWrite your reference (or phone number) and the change you need."),
        "ask": True, "ticket": True, "tag": "لغو/تغییر",
        "done": _L("درخواستت ثبت شد (تیکت #{ticket_no}). به‌زودی همین‌جا جواب می‌دیم.", "Request received (ticket #{ticket_no}). We'll reply right here soon."),
        "next": "home", "buttons": [[_b(_L("↩️ انصراف", "↩️ Cancel"), "home")]]},
}

# ═══════════ ۴) باشگاه مشتریان ═══════════
_TODAY = {"var": "lastday", "op": "==", "value": "{date}"}
_NOTTODAY = {"var": "lastday", "op": "!=", "value": "{date}"}
_CLUB_HOME = ("<b>🏅 باشگاه مشتریان</b>\nسلام {name}! 👋\n\n⭐ امتیاز تو: <b>{points}</b>\n🎖 سطح: <b>%s</b>\n👥 دعوت‌های موفق: <b>{refs}</b>",
              "<b>🏅 Loyalty club</b>\nHi {name}! 👋\n\n⭐ Your points: <b>{points}</b>\n🎖 Level: <b>%s</b>\n👥 Successful invites: <b>{refs}</b>")


def _club_home(lv):
    return _L(_CLUB_HOME[0] % lv[0], _CLUB_HOME[1] % lv[1])


def _redeem(pts, fa, en):
    return _b(_L(f"🎟 {fa} ({pts} امتیاز)", f"🎟 {en} ({pts} pts)"), "redeemed",
              when={"var": "points", "op": ">=", "value": str(pts)},
              do=[{"op": "add", "var": "points", "value": "-" + str(pts)}, {"op": "notify", "value": f"درخواست جایزه: {fa} ({pts} امتیاز کسر شد)"}])


_CLUB = {
    "home": {"title": _L("منوی اصلی", "Main menu"), "text": _club_home(("برنزی 🥉", "Bronze 🥉")),
        "alt": [{"when": {"var": "points", "op": ">=", "value": "200"}, "text": _club_home(("طلایی 🥇", "Gold 🥇"))},
                {"when": {"var": "points", "op": ">=", "value": "100"}, "text": _club_home(("نقره‌ای 🥈", "Silver 🥈"))}],
        "buttons": [[_b(_L("🎁 جایزه‌ی امروز", "🎁 Daily reward"), "daily"), _b(_L("🏆 جوایز", "🏆 Rewards"), "rewards")],
                    [_b(_L("👥 دعوت دوستان", "👥 Invite friends"), "invite"), _b(_L("🥇 برترین‌ها", "🥇 Leaderboard"), "top")],
                    [_LANGBTN()]]},
    "daily": {"title": _L("جایزه‌ی روزانه", "Daily reward"),
        "text": _L("<b>🎁 جایزه‌ی روزانه</b>\n\nهر روز یک بار می‌تونی <b>۱۰ امتیاز</b> هدیه بگیری.", "<b>🎁 Daily reward</b>\n\nOnce a day you can claim <b>10 free points</b>."),
        "alt": [{"when": _TODAY, "text": _L("<b>✅ جایزه‌ی امروزت رو گرفتی</b>\n\nفردا دوباره بیا و امتیاز بگیر.", "<b>✅ You've claimed today's reward</b>\n\nCome back tomorrow for more points.")}],
        "buttons": [[_b(_L("🎁 دریافت ۱۰ امتیاز", "🎁 Claim 10 points"), "claimed", when=_NOTTODAY,
                        do=[{"op": "set", "var": "lastday", "value": "{date}"}, {"op": "add", "var": "points", "value": "10"}])], _home()]},
    "claimed": {"title": _L("امتیاز گرفتی", "Points claimed"),
        "text": _L("<b>🎉 ۱۰ امتیاز گرفتی!</b>\n\nمجموع امتیازهات: <b>{points}</b>", "<b>🎉 You got 10 points!</b>\n\nYour total: <b>{points}</b>"),
        "buttons": [[_b(_L("🥇 برترین‌ها", "🥇 Leaderboard"), "top")], _home()]},
    "rewards": {"title": _L("جوایز", "Rewards"),
        "text": _L("<b>🏆 جوایز باشگاه</b>\n\n<blockquote>🎟 ۵۰ امتیاز: [جایزه‌ی اول]\n🎟 ۱۰۰ امتیاز: [جایزه‌ی دوم]</blockquote>\n\nامتیاز تو: <b>{points}</b>\n<i>دکمه‌ی جایزه وقتی فعال می‌شه که امتیاز کافی داشته باشی.</i>",
                   "<b>🏆 Club rewards</b>\n\n<blockquote>🎟 50 points: [First reward]\n🎟 100 points: [Second reward]</blockquote>\n\nYour points: <b>{points}</b>\n<i>A reward button appears once you have enough points.</i>"),
        "buttons": [[_redeem(50, "جایزه‌ی اول", "First reward")], [_redeem(100, "جایزه‌ی دوم", "Second reward")], _home()]},
    "redeemed": {"title": _L("درخواست جایزه", "Reward requested"),
        "text": _L("<b>✅ درخواست جایزه‌ات ثبت شد</b>\n\nتیم ما برای هماهنگی بهت پیام می‌ده.\nامتیاز باقی‌مانده: <b>{points}</b>", "<b>✅ Reward requested</b>\n\nOur team will message you to arrange it.\nPoints left: <b>{points}</b>"),
        "buttons": [_home()]},
    "invite": {"title": _L("دعوت دوستان", "Invite friends"),
        "text": _L("<b>👥 دعوت دوستان</b>\n\nبه ازای هر دوستی که با لینک تو وارد بشه، <b>۲۰ امتیاز</b> می‌گیری.\n\n🔗 لینک اختصاصی تو:\n<code>{ref_link}</code>\n\nدعوت‌های موفق: <b>{refs}</b>",
                   "<b>👥 Invite friends</b>\n\nFor every friend who joins with your link you get <b>20 points</b>.\n\n🔗 Your personal link:\n<code>{ref_link}</code>\n\nSuccessful invites: <b>{refs}</b>"),
        "buttons": [[_b(_L("📤 ارسال لینک دعوت", "📤 Share invite link"), share=_L("بیا این باشگاه رو ببین؛ با ثبت‌نام امتیاز و جایزه می‌گیری 🎁", "Check out this club; join and earn points and rewards 🎁"))],
                    [_b(_L("📋 کپی لینک", "📋 Copy link"), copy="{ref_link}"), _b(_L("🏅 برترین دعوت‌کننده‌ها", "🏅 Top inviters"), "inv_top")], _home()]},
    "top": {"title": _L("برترین‌ها", "Leaderboard"),
        "text": _L("<b>🥇 برترین‌های باشگاه</b>", "<b>🥇 Club leaderboard</b>"),
        "board": {"var": "points", "top": 10, "label": _L("بیشترین امتیاز", "Most points")},
        "buttons": [[_b(_L("🎁 جایزه‌ی امروز", "🎁 Daily reward"), "daily")], _home()]},
    "inv_top": {"title": _L("برترین دعوت‌کننده‌ها", "Top inviters"),
        "text": _L("<b>🏅 برترین دعوت‌کننده‌ها</b>", "<b>🏅 Top inviters</b>"),
        "board": {"var": "refs", "top": 10, "label": _L("بیشترین دعوت", "Most invites")},
        "buttons": [[_b(_L("👥 دعوت دوستان", "👥 Invite friends"), "invite")], _home()]},
}

# ═══════════ ۵) دستیار هوشمند ═══════════
_AI_FA = ("تو دستیار هوشمند و مشاور [نام کسب‌وکار] هستی. مؤدب، گرم و حرفه‌ای باش.\n"
          "قوانین: ۱) به فارسی و کوتاه جواب بده (حداکثر ۵ جمله)؛ اگه کاربر زبان دیگه‌ای نوشت به همون زبان. "
          "۲) فقط درباره‌ی خدمات و محصولات همین کسب‌وکار کمک کن؛ سؤال بی‌ربط رو مؤدبانه به موضوع برگردون. "
          "۳) اگه جواب رو نمی‌دونی صادقانه بگو و پیشنهاد بده با پشتیبانی انسانی صحبت کنه؛ هرگز قیمت، شماره یا اطلاعات نساز. "
          "۴) وقتی مناسبه، یک سؤال کوتاه بپرس تا مشتری رو به ثبت درخواست یا خرید هدایت کنی. "
          "۵) بدون Markdown و بدون فرمت‌بندی خاص بنویس.\n"
          "نام کاربر: {name}\nاطلاعات کسب‌وکار: [خدمات، قیمت‌ها، ساعت کاری، آدرس و شرایط رو اینجا بنویس]")
_AI_EN = ("You are the smart assistant and advisor of [Business name]. Be polite, warm and professional.\n"
          "Rules: 1) Answer in English and keep it short (max 5 sentences); if the user writes in another language, reply in that language. "
          "2) Only help with this business's services and products; politely steer unrelated questions back. "
          "3) If you don't know the answer, say so honestly and suggest talking to a human; never invent prices, numbers or facts. "
          "4) When appropriate, ask one short question to guide the customer toward a request or purchase. "
          "5) Write plain text, no Markdown or special formatting.\n"
          "User name: {name}\nBusiness info: [write services, prices, hours, address and terms here]")

_AIBOT = {
    "home": {"title": _L("منوی اصلی", "Main menu"),
        "text": _L("<b>🤖 دستیار هوشمند [نام کسب‌وکار]</b>\nسلام {name}! 👋\n\nهر سؤالی داری بپرس؛ شبانه‌روز جواب می‌دم.\n\n<blockquote>💡 قیمت‌ها، خدمات، پیشنهاد مناسب و راهنمایی خرید</blockquote>",
                   "<b>🤖 [Business name] smart assistant</b>\nHi {name}! 👋\n\nAsk me anything; I answer around the clock.\n\n<blockquote>💡 Prices, services, tailored suggestions and buying advice</blockquote>"),
        "buttons": [[_b(_L("💬 شروع گفتگو", "💬 Start chatting"), "chat")],
                    [_b(_L("💡 چی بپرسم؟", "💡 What can I ask?"), "ideas"), _b(_L("ℹ️ درباره‌ی ما", "ℹ️ About us"), "about")],
                    [_b(_L("📩 صحبت با انسان", "📩 Talk to a human"), "human")], [_LANGBTN()]]},
    "chat": {"title": _L("گفتگو", "Chat"),
        "text": _L("<b>💬 گفتگو با دستیار</b>\n\nسلام! سؤالت رو بنویس؛ برای خروج «پایان گفتگو» رو بزن.", "<b>💬 Chat with the assistant</b>\n\nHello! Type your question; tap “End chat” to leave."),
        "ai": {"prompt": _L(_AI_FA, _AI_EN), "daily": 25, "memory": 4},
        "buttons": [[_b(_L("📩 صحبت با انسان", "📩 Talk to a human"), "human"), _b(_L("🏠 پایان گفتگو", "🏠 End chat"), "home")]]},
    "ideas": {"title": _L("نمونه سؤال‌ها", "Example questions"),
        "text": _L("<b>💡 چی می‌تونی بپرسی؟</b>\n\n<blockquote>• «برای [نیاز من] چی پیشنهاد می‌کنی؟»\n• «قیمت [خدمت] چنده؟»\n• «ساعت کاری و آدرس شما کجاست؟»\n• «تفاوت [گزینه ۱] و [گزینه ۲] چیه؟»</blockquote>",
                   "<b>💡 What can you ask?</b>\n\n<blockquote>• “What do you recommend for [my need]?”\n• “How much is [service]?”\n• “What are your hours and address?”\n• “What's the difference between [option 1] and [option 2]?”</blockquote>"),
        "buttons": [[_b(_L("💬 شروع گفتگو", "💬 Start chatting"), "chat")], _home()]},
    "human": {"title": _L("صحبت با انسان", "Talk to a human"),
        "text": _L("<b>📩 صحبت با تیم ما</b>\n\nپیامت رو بنویس؛ مستقیم برای یکی از همکارهامون می‌رسه.", "<b>📩 Talk to our team</b>\n\nWrite your message; it goes straight to one of our team members."),
        "ask": True, "ticket": True, "tag": "انسانی",
        "done": _L("پیامت ثبت شد (تیکت #{ticket_no}). به‌زودی همین‌جا جواب می‌دیم.", "Message received (ticket #{ticket_no}). We'll reply right here soon."),
        "next": "home", "buttons": [[_b(_L("↩️ انصراف", "↩️ Cancel"), "home")]]},
    "about": {"title": _L("درباره‌ی ما", "About us"),
        "text": _L("<b>ℹ️ درباره‌ی ما</b>\n\n[چند خط درباره‌ی کسب‌وکارت]\n\n📞 [شماره تماس]", "<b>ℹ️ About us</b>\n\n[A few lines about your business]\n\n📞 [Phone]"),
        "buttons": [[_b(_L("📣 کانال ما", "📣 Our channel"), url=_CH)], _home()]},
}

TEMPLATES = {
    "shop": {"icon": "bag", "title": "فروشگاه حرفه‌ای", "desc": "کاتالوگ محصولات، ثبت سفارش، پیگیری و نظرسنجی خودکار",
        "feats": ["دوزبانه", "فرم سفارش + تیکت", "پیگیری سفارش", "نظرسنجی بعد از خرید"],
        "note": "فروشگاه کامل ساختم: دسته‌های محصول، فرم سفارش، پیگیری، سؤالات متداول و تماس. هر سفارش یه تیکت می‌شه که با دکمه‌ی «پاسخ» زیرش به مشتری جواب می‌دی؛ دو روز بعد از سفارش هم خودکار نظرسنجی می‌فرسته. متن‌های داخل [ ] جای‌نگه‌دارن؛ از «ویرایش دستی» عوضشون کن." + _NOTE_LANG,
        "config": _bilingual("فروشگاه من", _SHOP, {"cname": "", "cphone": ""})},
    "support": {"icon": "headset", "title": "پشتیبانی مشتری", "desc": "سؤالات متداول، تیکت بخش‌بندی‌شده و نمایش آنلاین یا آفلاین بودن",
        "feats": ["دوزبانه", "تیکت به‌تفکیک بخش", "وضعیت آنلاین", "نظرسنجی رضایت"],
        "note": "مرکز پشتیبانی ساختم: سؤالات متداول در سه دسته، ثبت درخواست برای فروش، فنی و مالی (هر کدوم با برچسب جدا)، پیگیری و نظرسنجی. بر اساس ساعت تهران، صفحه‌ی اصلی آنلاین یا خارج از ساعت کاری رو نشون می‌ده (۹ تا ۲۱؛ از ویرایش بخش اصلی عوض کن). تیکت‌ها داخل همین چت با دکمه‌ی «پاسخ» می‌رسن و با /tickets هم می‌بینیشون." + _NOTE_LANG,
        "config": _bilingual("پشتیبانی", _SUPPORT, desk={"closed": "✅ درخواستت بسته شد · Your request has been closed. اگه مشکلی هست دوباره پیام بده · Message us again if needed.", "reply_btn": "💬 پاسخ · Reply"})},
    "booking": {"icon": "cal", "title": "رزرو نوبت", "desc": "خدمات و تعرفه، رزرو، لغو یا تغییر و قوانین؛ مناسب کلینیک، سالن و آموزشگاه",
        "feats": ["دوزبانه", "رزرو با تیکت", "لغو یا تغییر", "شناخت مشتری تکراری"],
        "note": "ربات رزرو نوبت ساختم: خدمات و تعرفه، فرم رزرو (نام، شماره، خدمت، روز و ساعت)، لغو یا تغییر نوبت، قوانین و آدرس. درخواست‌ها برات تیکت می‌شن و با دکمه‌ی «پاسخ» تأیید زمان رو می‌فرستی؛ مشتری تکراری با اسمش خوشامد می‌شنوه. خدمت‌ها، قیمت‌ها و آدرس جای‌نگه‌دارن؛ از «ویرایش دستی» عوضشون کن." + _NOTE_LANG,
        "config": _bilingual("رزرو نوبت", _BOOKING, {"cname": "", "cphone": ""})},
    "club": {"icon": "medal", "title": "باشگاه مشتریان", "desc": "امتیاز، جایزه‌ی روزانه، سطح‌بندی، دعوت دوستان و جدول برترین‌ها",
        "feats": ["دوزبانه", "جایزه‌ی روزانه", "سطح برنزی تا طلایی", "دعوت و جدول برترین‌ها"],
        "note": "باشگاه مشتریان ساختم: هر نفر روزی یک بار ۱۰ امتیاز می‌گیره، با ۱۰۰ و ۲۰۰ امتیاز سطح نقره‌ای و طلایی می‌شه، با دعوت هر دوست ۲۰ امتیاز می‌گیره و جدول برترین‌ها و برترین دعوت‌کننده‌ها هست. جایزه‌های ۵۰ و ۱۰۰ امتیازی درخواستشون برات می‌آد. جایزه‌ها رو از «ویرایش دستی» بنویس." + _NOTE_LANG,
        "config": _bilingual("باشگاه مشتریان", _CLUB, {"points": "0", "lastday": ""}, on_ref=[{"op": "add", "var": "points", "value": "20"}],
                             ref_text="🎉 یه نفر با لینک تو وارد شد و ۲۰ امتیاز گرفتی! امتیاز تو: {points} · Someone joined with your link: +20 points! Total: {points}")},
    "ai": {"icon": "bot", "title": "دستیار هوشمند", "desc": "چت‌بات هوش مصنوعی با پیشنهاد سؤال و انتقال به انسان",
        "feats": ["دوزبانه", "هوش مصنوعی با حافظه", "نمونه سؤال", "انتقال به انسان"],
        "note": "دستیار هوشمند ساختم: گفتگوی آزاد با هوش مصنوعی (حافظه‌ی ۴ پیام و حداکثر ۲۵ پیام در روز برای هر نفر)، نمونه سؤال‌ها و دکمه‌ی صحبت با انسان که تیکت می‌شه. حتماً اطلاعات واقعی کسب‌وکارت رو (خدمات، قیمت، ساعت کاری) توی دستورالعمل بخش «گفتگو» بنویس تا جواب‌ها دقیق باشن. هر پیام کاربر حدود ۱ توکن از حساب تو مصرف می‌کنه." + _NOTE_LANG,
        "config": _bilingual("دستیار هوشمند", _AIBOT)},
}
