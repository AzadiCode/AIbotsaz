/* ═══════════════════════════════════════════════════════════════
   app.js — پوسته‌ی مینی‌اپ: وضعیت، ارتباط با سرور، آیکن‌ها، رندر صفحه‌ها (ساخت، ربات‌ها، رسانه،
   حساب)، اکشن‌های صفحه، اشتراک و ماموریت، ابزارهای ربات، پنل مدیریت و یوزربات.
   ترتیب بارگذاری (index.html): app.js ← studio.js ← load()
   این فایل اول اجرا می‌شود؛ هر چیزی که فوراً (هنگام بارگذاری) به studio.js نیاز دارد نباید اینجا باشد.
   ═══════════════════════════════════════════════════════════════ */
/* ═════════ اتصال به تلگرام ═════════ */
const tg = window.Telegram?.WebApp;
tg?.ready(); tg?.expand();
const INIT = tg?.initData || "";
/* ورود ادمین از مرورگر برای تست: یک بار با  ‎/?key=ADMIN_WEB_KEY  باز کن؛ کلید توی مرورگر می‌مونه */
const WK = (() => { try{
  if(tg?.initData) return "";
  const q = new URLSearchParams(location.search).get("key");
  if(q){ localStorage.setItem("wk", q); history.replaceState(null, "", location.pathname); }
  return localStorage.getItem("wk") || "";
}catch(_){ return ""; } })();
// خالی = همون دامنه‌ای که این صفحه ازش لود شده. فقط اگه index.html رو جدا هاست کردی آدرس بک‌اند رو بذار:
const API_BASE = "";

let S = {
  view: "create", btab: "ai", atab: "wallet", sbot: null,
  bots: [], wallet: { tokens: 0, streak: 0, can_claim: false, next_reward: 2, refs: 0 }, cfg: {}, packs: [], media: [], used: 0,
  ref: { link: "", count: 0 }, joined: null, templates: [], admin: false, subs: [], cur: null, busy: false, fresh: false,
  ideas: [], sheet: null, uploads: [], stats: null, pickKey: null, tasks: [], plan: null, emojis: undefined
};
let D = null;   // پیش‌نویس فرمِ باز

/* ═════════ ابزارهای کوچک ═════════ */
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const N = x => `<span class="n">${esc(x)}</span>`;
const digitsHTML = s => String(s ?? "").split(/(\d+)/).map((p, i) => i % 2 ? `<span class="n">${p}</span>` : esc(p)).join("");
const sleep = ms => new Promise(r => setTimeout(r, ms));
const cp = o => JSON.parse(JSON.stringify(o));
const fa = n => Number(n || 0).toLocaleString("en-US");
const haptic = k => { try{ k === "ok" ? tg?.HapticFeedback?.notificationOccurred("success") : tg?.HapticFeedback?.selectionChanged(); }catch(_){} };
const reduced = () => matchMedia("(prefers-reduced-motion:reduce)").matches;
const openLink = u => tg?.openTelegramLink ? tg.openTelegramLink(u) : window.open(u, "_blank");
const confirmQ = (q, go) => tg?.showConfirm ? tg.showConfirm(q, go) : go(confirm(q));

/* ═════════ تم ═════════ */
function applyTheme(){
  const dark = (tg?.initData ? (tg.colorScheme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) : "dark") === "dark";   // بیرون از تلگرام: همیشه تیره
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  try{ tg?.setHeaderColor?.(dark ? "#081116" : "#E8ECEE"); tg?.setBackgroundColor?.(dark ? "#081116" : "#E8ECEE"); }catch(_){}
}
applyTheme(); tg?.onEvent?.("themeChanged", applyTheme);

function toast(m){ const t = $("#toast"); const msg = String(m ?? ""); t.innerHTML = digitsHTML(msg); t.classList.add("show"); clearTimeout(toast.t); /* پیام‌های خطا/طولانی زمان بیشتری برای خواندن دارند */ const duration = /(ناموفق|خطا|نشد|کسر نشد|دوباره امتحان|گزارش)/i.test(msg) || msg.length > 90 ? 5000 : 4000; toast.t = setTimeout(() => t.classList.remove("show"), duration); }

/* ═════════ ارتباط با سرور ═════════ */
async function api(path, method = "GET", body){
  const r = await fetch(API_BASE + path, { method, headers: {"Content-Type":"application/json","X-Init-Data":INIT, ...(WK ? {"X-Admin-Key": WK} : {})}, body: body ? JSON.stringify(body) : undefined });
  const d = await r.json().catch(() => ({}));
  if(!r.ok){ const e = new Error(d.error || "خطا در ارتباط با سرور"); e.status = r.status; e.data = d; throw e; }
  return d;
}
function uploadFile(file, onp){
  return new Promise((res, rej) => {
    const x = new XMLHttpRequest();
    x.open("POST", API_BASE + "/api/media");
    x.setRequestHeader("X-Init-Data", INIT); if(WK) x.setRequestHeader("X-Admin-Key", WK);
    x.setRequestHeader("Content-Type", file.type || "application/octet-stream");
    x.setRequestHeader("X-Filename", encodeURIComponent(file.name));
    x.upload.onprogress = e => e.lengthComputable && onp(e.loaded / e.total);
    x.onload = () => { let d = {}; try{ d = JSON.parse(x.responseText); }catch(_){} x.status < 300 ? res(d) : rej(new Error(d.error || "آپلود ناموفق بود")); };
    x.onerror = () => rej(new Error("ارتباط با سرور قطع شد"));
    x.send(file);
  });
}
async function busy(btn, fn){
  if(S.busy) return; S.busy = true;
  const old = btn?.innerHTML; if(btn){ btn.disabled = true; btn.innerHTML = old + '<span class="spin"></span>'; }
  try{ await fn(); }catch(e){ toast(e.message); }
  S.busy = false; if(btn?.isConnected){ btn.disabled = false; btn.innerHTML = old; }
}

/* ═════════ آیکن‌ها ═════════ */
const svg = (p, w = 1.7) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
const IC = {
  bot: svg('<rect x="4" y="8" width="16" height="11" rx="3.5"/><path d="M12 8V4.5"/><circle cx="12" cy="3.6" r="1"/><circle cx="9" cy="13.5" r="1.1" fill="currentColor"/><circle cx="15" cy="13.5" r="1.1" fill="currentColor"/><path d="M2.5 12.5v2M21.5 12.5v2"/>'),
  spark: svg('<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M18.5 16.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z" stroke-width="1.3"/>'),
  photo: svg('<rect x="3.5" y="4.5" width="17" height="15" rx="3"/><circle cx="9" cy="10" r="1.7"/><path d="M4 17l4.5-4.5 3.5 3.5 3-3 5 5"/>'),
  wallet: svg('<rect x="3.5" y="6" width="17" height="13" rx="3"/><path d="M3.5 10h17"/><circle cx="16.5" cy="14.5" r="1" fill="currentColor"/>'),
  coin: svg('<circle cx="12" cy="12" r="8.5"/><path d="M13 7.5l-3.5 5H14l-3 4.5"/>'),
  chev: svg('<path d="M6 9l6 6 6-6"/>', 2.2),
  go: svg('<path d="M15 6l-6 6 6 6"/>', 2.2),
  back: svg('<path d="M9 6l6 6-6 6"/>', 2.2),
  x: svg('<path d="M6 6l12 12M18 6L6 18"/>', 2),
  plus: svg('<path d="M12 5v14M5 12h14"/>', 2),
  gear: svg('<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>'),
  upload: svg('<path d="M12 16V5M7.5 9.5L12 5l4.5 4.5"/><path d="M5 15v3a1.5 1.5 0 0 0 1.5 1.5h11A1.5 1.5 0 0 0 19 18v-3"/>', 2),
  animation: svg('<rect x="3" y="6" width="18" height="12" rx="3"/><path d="M10 9.5H8.5a1.5 1.5 0 0 0 0 5H10v-2M14 9.5v5M17.5 9.5h-2v5"/>', 1.6),
  video: svg('<rect x="3" y="6" width="13" height="12" rx="3"/><path d="M16 11l5-3v8l-5-3"/>'),
  audio: svg('<path d="M9 18V6l10-2v12"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="16.5" cy="16" r="2.5"/>'),
  voice: svg('<rect x="9" y="3.5" width="6" height="11" rx="3"/><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3"/>'),
  document: svg('<path d="M7 3.5h7l4 4v13a.5.5 0 0 1-.5.5h-10.5a.5.5 0 0 1-.5-.5v-16.5a.5.5 0 0 1 .5-.5z"/><path d="M14 3.5v4h4M9.5 12.5h5M9.5 16h5"/>'),
  copy: svg('<rect x="9" y="9" width="11" height="11" rx="2.5"/><path d="M5 15V6.5A2.5 2.5 0 0 1 7.5 4H15"/>', 2),
  play: `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5.5v13l11-6.5z"/></svg>`,
  flame: svg('<path d="M12 3c1 3.5 5 5.5 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4 .3 1.2 1 1.8 1.7 2C10.5 8.5 11 5.5 12 3z"/>'),
  trash: svg('<path d="M4.5 7h15M9.5 7V4.5h5V7M6.5 7l1 13h9l1-13"/>'),
  heal: svg('<path d="M3 12h4l2.5-6 4 12 2.5-6H21"/>'),
  dl: svg('<path d="M12 4v11M8 11l4 4 4-4M5 19h14"/>'),
  layers: svg('<path d="M12 4l8.5 4.5L12 13 3.5 8.5z"/><path d="M3.5 12.5L12 17l8.5-4.5M3.5 16.5L12 21l8.5-4.5"/>'),
  inbox: svg('<path d="M4 13l2.5-7h11L20 13v6H4z"/><path d="M4 13h4.5l1 2h5l1-2H20"/>'),
  users: svg('<circle cx="9" cy="9" r="3.3"/><path d="M3.5 19c.6-3.2 2.8-4.8 5.5-4.8s4.9 1.6 5.5 4.8M16 6.2a3.2 3.2 0 0 1 0 6M18 14.6c1.6.6 2.6 2 3 4.4"/>'),
  cal: svg('<rect x="4" y="5.5" width="16" height="14.5" rx="3"/><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4"/>'),
  card: svg('<rect x="3" y="6" width="18" height="12" rx="3"/><circle cx="8.5" cy="12" r="2"/><path d="M13 10.5h5M13 13.5h4"/>'),
  bag: svg('<path d="M5 8h14l-1 12H6z"/><path d="M9 8V6.5a3 3 0 0 1 6 0V8"/>'),
  headset: svg('<path d="M4.5 14v-2a7.5 7.5 0 0 1 15 0v2"/><rect x="3.5" y="13" width="4" height="6" rx="1.8"/><rect x="16.5" y="13" width="4" height="6" rx="1.8"/>'),
  form: svg('<rect x="5" y="4" width="14" height="16" rx="3"/><path d="M9 9h6M9 13h6M9 17h3"/>'),
  medal: svg('<circle cx="12" cy="9.5" r="4.5"/><path d="M9 13.5L7.5 21l4.5-2.5 4.5 2.5-1.5-7.5"/>'),
  quiz: svg('<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.6 2.2c-.7.4-1.1.9-1.1 1.8M12 16.5h.01"/>'),
  open: svg('<path d="M14 4h6v6M20 4l-9 9M10 6H6.5A2.5 2.5 0 0 0 4 8.5v9A2.5 2.5 0 0 0 6.5 20h9a2.5 2.5 0 0 0 2.5-2.5V14"/>'),
  shield: svg('<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/>'),
  refresh: svg('<path d="M20 12a8 8 0 1 1-2.6-5.9"/><path d="M20 4v5h-5"/>'),
  mega: svg('<path d="M4 10v4h3l7 4V6L7 10z"/><path d="M17.5 9.5a4 4 0 0 1 0 5"/>'),
  chart: svg('<path d="M5 19v-8M12 19V5M19 19v-5"/>', 2),
  key: svg('<circle cx="8" cy="12" r="3.5"/><path d="M11.5 12H20M17 12v3M14.5 12v2"/>'),
  stats: svg('<path d="M4 19h16M7 16v-5M12 16V6M17 16v-8"/>'),
  studio: svg('<circle cx="6" cy="6" r="2.4"/><circle cx="18" cy="8" r="2.4"/><circle cx="9.5" cy="18" r="2.4"/><path d="M8.3 6.8l7.4 1M7 8.3l1.8 7.3M16.7 10.2l-5.6 5.8"/>'),
  bolt: svg('<path d="M13 2.5L5.5 13H11l-1.2 8.5L18.5 11H13z"/>'),
  fit: svg('<path d="M9 4H4v5M15 4h5v5M9 20H4v-5M15 20h5v-5"/>'),
  minus: svg('<path d="M5 12h14"/>', 2),
  person: svg('<circle cx="12" cy="8.5" r="3.6"/><path d="M4.8 20c.7-3.7 3.6-5.6 7.2-5.6s6.5 1.9 7.2 5.6"/>'),
  star: svg('<path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.9-5.2-2.8-5.2 2.8 1-5.9-4.3-4.1 5.9-.8z"/>'),
  home: svg('<path d="M4 11l8-6.5 8 6.5"/><path d="M6 9.8V19a1 1 0 0 0 1 1h3.5v-5h3v5H17a1 1 0 0 0 1-1V9.8"/>'),
  image: svg('<rect x="3.5" y="4.5" width="17" height="15" rx="3"/><circle cx="9" cy="10" r="1.7"/><path d="M4 17l4.5-4.5 3.5 3.5 3-3 5 5"/>'),
  table: svg('<rect x="4" y="5" width="16" height="14" rx="2"/><path d="M4 10h16M10 10v9M4 15h16"/>'),
  sim: svg('<rect x="6" y="3" width="12" height="18" rx="3"/><path d="M10 6h4"/>'),
  clock: svg('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
};
const LOGO = svg('<rect x="4" y="8" width="16" height="11" rx="3.5"/><g class="ant"><path d="M12 8V4.6"/><circle cx="12" cy="3.5" r="1.1"/></g><g class="eyes"><circle class="eye" cx="9" cy="13.6" r="1.35" fill="currentColor" stroke="none"/><circle class="eye" cx="15" cy="13.6" r="1.35" fill="currentColor" stroke="none"/></g>', 1.7);
const KIND_FA = {photo:"عکس", video:"ویدیو", animation:"گیف", audio:"موسیقی", voice:"ویس", document:"فایل"};
const why = {signup:"پاداش ثبت‌نام", gen:"ساخت ربات", edit:"ارتقای ربات", ai_chat:"پیام هوشمند داخل ربات‌ها", broadcast:"اطلاعیه به کل کاربران", daily:"کش بک روزانه",
  referral:"دعوت موفق", invited:"پاداش ناوگان", milestone:"پاداش ویژه‌ی ناوگان", buy:"شارژ توکن", card:"خرید کارت‌به‌کارت", refund:"برگشت توکن", admin:"هدیه‌ی مدیر",
  enhance:"کامل‌تر کردن توضیح", coupon:"کد پاداش", template:"قالب آماده", task:"پاداش ماموریت", levelup:"پاداش ارتقای سطح", plan:"هدیه‌ی اشتراک",
  app_gen:"ساخت مینی‌اپ با هوش مصنوعی", app_tpl:"قالب مینی‌اپ"};

/* ═════════ هزینه‌ها ═════════ */
const billingFixed = () => S.cfg.billing === "fixed";
const costOf = isEdit => billingFixed() ? (isEdit ? S.cfg.edit : S.cfg.gen) : (S.cfg.typical || 12);
const costTxt = isEdit => billingFixed() ? N(costOf(isEdit)) : N("±" + (S.cfg.typical || 12));
const needCost = isEdit => billingFixed() ? costOf(isEdit) : (S.cfg.min || 5);
const cellsHTML = (on, total = 10) => Array.from({length: total}, (_, i) => `<i class="${i < on ? "on" : ""}"></i>`).join("");
const buildsLeft = () => Math.min(10, Math.floor(S.wallet.tokens / (costOf(false) || 6)));

/* ═════════ رسانه ═════════ */
const mediaById = id => S.media.find(m => m.id === id);
const miInner = m => (m.kind === "photo" || m.kind === "animation") ? `<img src="${API_BASE + esc(m.url)}" alt="" loading="lazy">` : IC[m.kind] || IC.document;
const sizeHTML = b => b < 1048576 ? N(Math.max(1, Math.round(b / 1024))) + " KB" : N((b / 1048576).toFixed(1)) + " MB";
function mediaPicker(key, cur){
  const items = S.media.map(m => `<button class="${m.id === cur ? "on" : ""}" data-sh="pickmedia" data-k="${key}" data-v="${m.id}"><div class="mi">${miInner(m)}</div><small>${esc(m.name)}</small></button>`).join("");
  return `<div class="mpick"><button class="${!cur ? "on" : ""}" data-sh="pickmedia" data-k="${key}" data-v=""><div class="mi">بدون</div><small>بدون رسانه</small></button>${items}<button class="up" data-sh="upmedia" data-k="${key}">آپلود</button></div>`;
}

/* ═════════ بارگذاری و رندر ═════════ */
function takeMe(d){
  for(const b of d.bots || []) for(const n of Object.values(b.config?.nodes || {})) if(n.kb === "reply"){ (n.buttons || []).forEach(r => r.forEach(x => { x.kb = "reply"; })); delete n.kb; }
  Object.assign(S, { card: d.card || { on: false, prices: {} }, bots: d.bots, wallet: d.wallet, cfg: d.cfg, packs: d.packs, media: d.media, used: d.used, ref: d.ref, joined: d.joined, templates: d.templates || [], admin: !!d.admin, tasks: d.tasks || [], plan: d.plan || null, me: d.me || null });
}
const tgHtml = t => esc(t).replace(/&lt;(\/?)(b|strong|i|em|u|ins|s|strike|del|code|pre|blockquote)&gt;/gi, "<$1$2>").replace(/&lt;a href=&quot;(https?:\/\/[^&"<>]*)&quot;&gt;/gi, '<a href="$1" target="_blank" rel="noopener">').replace(/&lt;\/a&gt;/gi, "</a>").replace(/&lt;tg-emoji emoji-id=&quot;(\d+)&quot;&gt;([\s\S]*?)&lt;\/tg-emoji&gt;/g, (m, id, ch) => emjTag(id, ch)).replace(/&lt;\/?tg-spoiler&gt;/gi, "");
function showFj(f){
  $("#dock").hidden = true;
  $("#app").innerHTML = `<div class="empty fjg"><div class="ib big">${IC.users}</div><h2>عضویت اجباری</h2><div class="fjt">${tgHtml(f.text)}</div>
    <div class="fjb">${f.channels.map(c => `<button class="b o" data-a="fjopen" data-u="${esc(c.url)}">${esc(c.label)}</button>`).join("")}<button class="b" data-a="fjchk">عضو شدم</button></div></div>`;
}
async function load(){
  try{ takeMe(await api("/api/me")); }
  catch(e){
    $("#dock").hidden = true;
    if(e.status === 403 && e.data?.fj) return showFj(e.data.fj);
    $("#app").innerHTML = `<div class="empty"><div class="ib big">${IC.bot}</div><h2>این برنامه را در تلگرام باز کن</h2><p class="muted">از داخل ربات مادر، روی «ساخت ربات» بزن.</p></div>`;
    return;
  }
  const want = new URLSearchParams(location.search).get("bot"), hit = want && S.bots.find(b => b.id === want);   // لینک مستقیم از چت ربات مادر
  if(hit){ S.cur = hit; S.view = "bot"; S.btab = "ai"; S.sbot = hit.id; S.ideas = []; S.stats = null; }
  render();
}
async function sync(){ try{ takeMe(await api("/api/me")); return true; }catch(_){ return false; } }

const TABS = [["create", "spark", "ساخت"], ["bots", "bot", "ربات‌ها"], ["studio", "studio", "استودیو"], ["miniapp", "layers", "مینی‌اپ"], ["media", "photo", "رسانه"], ["userbot", "person", "یوزربات"], ["account", "wallet", "حساب"]];
$("#dpanel").innerHTML = TABS.map(([k, ic, t]) => `<button class="dn" data-go="${k}" aria-label="${t}" title="${t}">${IC[ic]}</button>`).join("");
function setDock(on){ $("#dock").classList.toggle("open", on); $("#dscrim").classList.toggle("on", on); }
document.addEventListener("click", e => {
  const dk = e.target.closest("#dock");
  if(dk){                                  // وقتی نوار بسته است، فقط آیکونِ بیرون‌زده قابل لمس است و نوار را باز می‌کند
    if(!$("#dock").classList.contains("open")){
      e.stopImmediatePropagation();
      if(stSheetDirty()) return stGuardClose(() => setDock(true));
      setDock(true);
    }
    return;
  }
  if(e.target.closest("#dscrim")) setDock(false);
});
document.addEventListener("keydown", e => { if(e.key === "Escape") setDock(false); });

const WORDMARK = `<span class="wm" dir="ltr" aria-label="Azadi"><span class="wl k a1">A</span><span class="wl z">z</span><span class="wl m">a</span><span class="wl d">d</span><span class="wl k i1">i</span></span>`;
function initWordmark(){
  const wm = document.querySelector(".wm"); if(!wm) return;
  const go = () => {
    wm.querySelectorAll(".wl").forEach(el => { el.style.setProperty("--w", el.getBoundingClientRect().width + "px"); });
    wm.classList.add("on");
  };
  (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(() => requestAnimationFrame(go));
}
function tokPillHTML(){
  return `<button class="tokpill${S.wallet.can_claim ? " gift" : ""}" data-go="account" aria-label="${S.wallet.can_claim ? "موجودی توکن، جایزه‌ی امروز آماده است" : "موجودی توکن"}">${IC.coin}${N(S.wallet.tokens)}</button>`;
}
function renderTop(){
  const top = $("#top");
  const pill = top.querySelector(".tokpill");
  if(pill){ pill.outerHTML = tokPillHTML(); return; } // لوگو و انیمیشن دست نمی‌خورن تا ری‌استارت نشن
  top.innerHTML = `<div class="top-in"><div class="brand">${LOGO}${WORDMARK}</div>${tokPillHTML()}</div>`;
  initWordmark();
}
function render(){
  renderTop();
  if(S.view !== "studio" && typeof SIM !== "undefined" && SIM.on){ SIM.on = false; $("#simwrap")?.remove(); }   // شبیه‌ساز فقط داخل استودیو باز می‌ماند
  document.documentElement.classList.toggle("st-lock", S.view === "studio");
  VIEWS[S.view]();
  const cur = S.view === "bot" ? "bots" : S.view;
  document.querySelectorAll(".dn").forEach(el => el.classList.toggle("on", el.dataset.go === cur));
}
function goTo(where){
  setDock(false);
  if(S.busy) return toast("کار قبلی هنوز تمام نشده؛ کمی صبر کن");
  stGuardClose(() => stGo(where));
}
function stGo(where){
  closeSheet();
  if(S.view === "bot" && where !== "studio"){ S.cur = null; S.ideas = []; }
  S.view = where; render(); scrollTo({top: 0, behavior: "smooth"}); haptic();
  if(where === "userbot") ubLoad();
  if(["create", "bots", "account"].includes(where)) sync().then(ok => {
    if(!ok || S.view !== where) return;
    renderTop();
    if(where !== "create" && !document.activeElement?.matches?.("input,textarea,select")) render();
  });
}
const tabsHTML = (list, cur, act) => `<div class="tabs" role="tablist">${list.map(([k, t]) => `<button class="tab${k === cur ? " on" : ""}" role="tab" aria-selected="${k === cur}" data-a="${act}" data-k="${k}">${t}</button>`).join("")}</div>`;

/* ═════════ انیمیشن ساخت ═════════ */
const THINK = ["در حال تحلیل درخواست…", "طراحی ساختار مسیرها…", "چیدمان صفحه‌ها و دکمه‌ها…", "نوشتن متن پیام‌ها…", "اتصال منطق و متغیرها…", "بررسی سازگاری با تلگرام…", "بهینه‌سازی تجربه‌ی کاربر…", "تنظیم جزئیات نهایی…", "بازبینی و رفع ایرادها…", "کمی دیگر، تقریباً آماده‌ست…"];
const RB = `<svg class="rb" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><circle class="r1" cx="12" cy="12" r="10" stroke-dasharray="9 5"/><path class="r2" d="M12 6a6 6 0 0 1 6 6" /><path class="r2" d="M12 18a6 6 0 0 1-6-6" /><circle class="c" cx="12" cy="12" r="2" fill="currentColor" stroke="none"/></svg>`;
const FAD = n => String(n);          // اعداد لاتین، مثل بقیه‌ی جاهای اپ
const LQ_STEPS = ["تحلیل", "ساخت", "بررسی", "ذخیره"];
const LQ_IDX = {analyze: 0, fallback: 0, build: 1, review: 2, repair: 2, audit: 2, validate: 2, save: 3};
const LQ_LBL = {analyze: "تحلیل درخواست", fallback: "تغییر مدل و تلاش جایگزین", build: "ساخت بخش‌ها و مسیرها", review: "بازبینی و اصلاح نهایی", repair: "اصلاح پاسخ نامعتبر", audit: "ممیزی تطابق درخواست", validate: "بررسی سازگاری با تلگرام", save: "ذخیره‌ی ربات"};
let LQ = {};
function lqSteps(root, idx, all){
  root.querySelectorAll(".lqst li").forEach((li, i) => { li.classList.toggle("done", !!all || i < idx); li.classList.toggle("on", !all && i === idx); });
}
function startLive(title){
  const box = $("#live"); if(!box) return;
  $("#think")?.classList.remove("show");
  LQ = {t0: Date.now(), target: 0, shown: 0, th: "", ty: 0, real: false, st: ""};
  box.innerHTML = `<div class="lq" role="status" aria-busy="true" aria-label="${title}">
    <div class="lqh">${RB}<div class="lqt"><b>${title}</b><span class="lqs">${THINK[0]}</span></div><div class="lqp"><b class="lqpc">${FAD(0)}%</b><small class="lqtm">${FAD("0:00")}</small></div></div>
    <div class="lqbar ind"><i></i></div>
    <ol class="lqst">${LQ_STEPS.map(t => `<li><i></i>${t}</li>`).join("")}</ol>
    <div class="lqn" hidden></div><div class="lqth" hidden></div></div>`;
  box.scrollIntoView({behavior: "smooth", block: "center"});
  const root = box.querySelector(".lq"), sub = root.querySelector(".lqs"), pc = root.querySelector(".lqpc"), bar = root.querySelector(".lqbar"),
        tm = root.querySelector(".lqtm"), th = root.querySelector(".lqth");
  lqSteps(root, 0);
  let pool = [], last = THINK[0];
  const next = () => {
    if(!pool.length){ pool = THINK.slice().sort(() => Math.random() - .5); if(pool[pool.length - 1] === last) pool.reverse(); }
    return last = pool.pop();
  };
  clearInterval(startLive.t); clearInterval(startLive.c);
  startLive.t = setInterval(() => { if(!root.isConnected) return clearInterval(startLive.t); if(!LQ.real) sub.textContent = next(); }, 2800);   // وقتی پیشرفت واقعی از سرور نیست (استریم خاموش)، متن‌ها می‌چرخن
  startLive.c = setInterval(() => {
    if(!root.isConnected) return clearInterval(startLive.c);
    const el = Math.floor((Date.now() - LQ.t0) / 1000);
    tm.textContent = FAD(Math.floor(el / 60) + ":" + String(el % 60).padStart(2, "0"));
    if(LQ.real){
      const d = LQ.target - LQ.shown;
      LQ.shown = reduced() ? LQ.target : LQ.shown + d * .12 + (Math.abs(d) < .4 && LQ.shown < 96 ? .02 : 0);
      LQ.shown = Math.min(LQ.shown, LQ.done ? 100 : 99);
      pc.textContent = FAD(Math.round(LQ.shown)) + "%"; bar.firstElementChild.style.width = LQ.shown + "%";
    }
    if(LQ.th){
      if(LQ.ty > LQ.th.length) LQ.ty = LQ.th.length;
      LQ.ty = reduced() ? LQ.th.length : Math.min(LQ.th.length, LQ.ty + 3);
      th.hidden = false; th.textContent = LQ.th.slice(0, LQ.ty); th.classList.toggle("cur", LQ.ty < LQ.th.length);
    }
  }, 100);
}
function liveUpdate(pr){
  const root = $("#live .lq"); if(!root || !pr) return;
  LQ.real = true; LQ.target = Math.max(LQ.target, +pr.p || 0);
  if(pr.th) LQ.th = pr.th;
  root.querySelector(".lqbar").classList.remove("ind");
  if(pr.st && pr.st !== LQ.st){
    LQ.st = pr.st; root.querySelector(".lqs").textContent = LQ_LBL[pr.st] || LQ_LBL.analyze; lqSteps(root, LQ_IDX[pr.st] ?? 0);
  }
  if(pr.model_try && pr.model_total > 1 && pr.model_try > 1){
    const modelHint = ` · امتحان مدل جایگزین ${pr.model_try}/${pr.model_total}`;
    const label = root.querySelector(".lqs");
    label.textContent = label.textContent.replace(/ · امتحان مدل جایگزین \d+\/\d+$/, "") + modelHint;
  }
  const n = root.querySelector(".lqn");
  if(pr.n > 0){ n.hidden = false; n.innerHTML = `<b>${FAD(pr.n)}</b> بخش ساخته شد` + (pr.ti ? ` · آخرین: ${esc(pr.ti)}` : ""); }
}
function liveDone(){
  const root = $("#live .lq"); if(!root) return;
  LQ.real = LQ.done = true; LQ.target = LQ.shown = 100;
  root.querySelector(".lqbar").classList.remove("ind"); root.querySelector(".lqbar").firstElementChild.style.width = "100%";
  root.querySelector(".lqpc").textContent = FAD(100) + "%"; root.querySelector(".lqs").textContent = "آماده شد"; lqSteps(root, 3, true);
}
function stopLive(){ clearInterval(startLive.t); clearInterval(startLive.c); LQ = {}; const b = $("#live"); if(b) b.innerHTML = ""; }

async function runJob(prompt, botId){
  startLive(botId ? "در حال ارتقای ربات" : "در حال ساخت ربات");
  try{
    const d = await api("/api/generate", "POST", { prompt, bot_id: botId });
    S.wallet = d.wallet; renderTop();
    for(let i = 0; i < 960; i++){
      await sleep(1000);
      const r = await api(`/api/jobs/${d.job}`);
      const before = S.wallet?.tokens; S.wallet = r.wallet; if(r.wallet?.tokens !== before) renderTop();
      if(r.status === "done"){ liveDone(); await sleep(reduced() ? 0 : 500); return r; }
      if(r.status === "review"){ liveDone(); return {...r, job: d.job}; }
      if(r.status === "cancelled") throw new Error("درخواست لغو شد؛ رباتی ساخته نشد و توکنی کسر نشد.");
      if(r.status === "error") throw new Error(r.error);
      liveUpdate(r.prog);
    }
    throw new Error("ساخت بیش از حد طول کشید، دوباره امتحان کن");
  } finally { stopLive(); }
}
function showBuildReview(r){
  const gaps = (r.gaps || []).slice(0, 8).map((g, i) => `<div class="sub2"><b>${i + 1}. ${esc(g.want || "محدودیت شناسایی‌شده")}</b><p class="muted">${esc(g.why || "این بخش نیاز به بررسی بیشتری دارد.")}</p>${g.upgrade ? `<p class="muted">راهکار: ${esc(g.upgrade)}</p>` : ""}</div>`).join("");
  S.pendingReview = r.job; S.sheet = {kind: "info"};
  showSheet(head("قبل از ساخت، انتخاب با توست") + `<p>بررسی نهایی نشان داد بعضی بخش‌های درخواستت ممکن است دقیقاً اجرا نشده باشند. برای جلوگیری از تحویل بی‌اطلاع نسخه‌ی ناقص، هنوز رباتی ذخیره نشده و هیچ توکنی کم نشده است.</p>${gaps || `<p class="muted">جزئیات محدودیت در گزارش بررسی ثبت شده است.</p>`}<div class="sub"><b>هزینه در صورت تأیید: ${N(r.cost || 0)} توکن</b></div><div class="bar"><button class="b" data-a="reviewyes" data-id="${esc(r.job)}">ساخت نسخه با این محدودیت‌ها</button><button class="b o" data-a="reviewno" data-id="${esc(r.job)}">لغو درخواست — بدون کسر توکن</button></div><div class="fgap"></div>`);
}

function submitPrompt(){
  const ta = $("#prompt"), p = ta.value.trim(), botId = S.cur?.id || null;
  if(p.length < 5) return toast("توضیح بیشتری بنویس");
  const cost = needCost(!!botId);
  if(S.wallet.tokens < cost) return openBuy(`این کار حداقل ${cost} توکن می‌خواهد و موجودی تو ${S.wallet.tokens} توکن است.`);
  busy($("#gen"), async () => {
    ta.readOnly = true;
    try{
      const r = await runJob(p, botId);
      if(r.status === "review"){ showBuildReview(r); return; }
      const was = !!botId;
      S.bots = [r.bot, ...S.bots.filter(b => b.id !== r.bot.id)];
      S.cur = r.bot; S.view = "bot"; S.btab = "ai"; S.sbot = r.bot.id; S.fresh = true; S.ideas = r.ideas || []; S.stats = null;
      render(); bumpTokens(); if(!was) celebrate(); toast((was ? "ربات ارتقا پیدا کرد" : "ربات ساخته شد") + (r.cost ? `، ${r.cost} توکن` : "")); haptic("ok");
      scrollTo(0, 0);
    }catch(e){
      if(e.status === 402) openBuy(e.message); else toast(e.message);
    }finally{ if(ta.isConnected) ta.readOnly = false; }
  });
}
function celebrate(){
  if(reduced()) return;
  const w = document.createElement("div"); w.className = "rbfx";
  w.innerHTML = '<i class="scan"></i>';
  document.body.appendChild(w); setTimeout(() => w.remove(), 2200);
}
function bumpTokens(){ const p = $(".tokpill"); if(p){ p.classList.remove("bump"); void p.offsetWidth; p.classList.add("bump"); } }

/* ═════════════════ صفحه‌ی ساخت ═════════════════ */
const EXAMPLES = [
  ["فروشگاه", "یه ربات فروشگاه لوازم جانبی موبایل با منوی دسته‌بندی، صفحه‌ی هر محصول و فرم سفارش"],
  ["دستیار هوشمند", "یه ربات با دستیار هوشمند که به سوال‌های مشتری‌های فروشگاه من جواب بده و دکمه‌ی پشتیبانی هم داشته باشه"],
];
const goIc = IC.go.replace("<svg", '<svg class="go"');

function dailyCard(){
  const w = S.wallet;
  if(w.can_claim) return `<div class="daily"><div class="dt"><b>جایزه‌ی امروز آماده است</b>${N("+" + w.next_reward)} توکن${w.streak ? `، ${N(w.streak)} روز پیاپی` : ""}</div><button class="b amber sm" data-a="daily">دریافت</button></div>`;
  return `<div class="daily done"><div class="dt"><b>پاداش امروز دریافت شد</b>${w.streak ? `${N(w.streak)} روز پیاپی. فردا ${N("+" + w.next_reward)} توکن` : "فردا دوباره بیا"}</div></div>`;
}
function tplBlock(){
  const full = S.bots.length >= (S.cfg.max_bots || 10);
  let h = "";
  if(!S.bots.length) h += `<div class="steps"><div>${N(1)}ایده‌ات را بنویس</div><div>${N(2)}هوش مصنوعی می‌سازد</div><div>${N(3)}فعالش کن</div></div>`;
  if((S.templates || []).length && !full){
    h += `<div class="sec tplhead"><h2>قالب‌های آماده <small>کامل و دوزبانه؛ با یک لمس ساخته می‌شود</small></h2></div>
      <div class="tplgrid">${S.templates.map(t => { const fs = t.feats || [];
        return `<div class="tplc"><div class="tplt"><span class="ib">${IC[t.icon] || IC.bot}</span><div class="gt"><b>${esc(t.title)}</b><span>${esc(t.desc)}</span></div>
          <button class="b sm" data-a="tpl" data-id="${esc(t.id)}">ساخت</button></div>
        <div class="chips"><span class="xbd t">${t.cost ? N(t.cost) + " توکن" : "رایگان"}</span>${fs.slice(0, 2).map(f => `<span class="chip">${esc(f)}</span>`).join("")}${fs.length > 2 ? `<span class="chip">+${fa(fs.length - 2)}</span>` : ""}</div></div>`; }).join("")}</div>`;
  }
  return h;
}
function renderCreate(){
  const c = S.cfg, full = S.bots.length >= (c.max_bots || 10);
  $("#app").innerHTML = `
    <section class="hero-t"><h1>ایده‌ات را بنویس</h1><p>من برات می‌سازمش و هر وقت خواستی، گسترشش می‌دم.</p></section>
    ${full ? `<div class="panel"><h2>به سقف ${N(c.max_bots)} ربات رسیدی</h2><p class="muted">برای ساخت ربات تازه، یکی از ربات‌های قبلی را حذف کن؛ یا همین ربات‌ها را با هوش مصنوعی ارتقا بده.</p><div class="fgap"></div><button class="b o" data-go="bots">ربات‌های من</button></div>` : `
    <div class="console">
      <textarea id="prompt" maxlength="${c.max_prompt || 4000}" aria-label="توضیح ربات" placeholder="${esc(EXAMPLES[0][1])}"></textarea>
      <div class="chips">${EXAMPLES.map((e, i) => `<button class="chip" data-a="chip" data-i="${i}">${e[0]}</button>`).join("")}<button class="chip ai" data-a="enhance">${IC.spark}تکمیل خودکار</button></div>
      <div class="cfoot">
        <div class="gauge" title="تعداد رباتی که با موجودی فعلی می‌توانی بسازی"><div class="cells">${cellsHTML(buildsLeft())}</div><span class="cost">مصرف توکن ${costTxt(false)}</span></div>
        <button class="b" id="gen" data-a="gen">ساخت ربات</button>
      </div>
    </div>`}
    <div id="live"></div>
    ${bpBlock()}
    ${tplBlock()}`;
  startTyper();
  if(S.bps === undefined){
    S.bps = null;
    api("/api/blueprints").then(d => { S.bps = d.items || []; if(S.view === "create") render(); }).catch(() => { S.bps = []; });
  }
}

/* ── چی می‌خوای بسازی؟ کارت‌های نقشه‌ی آماده (ربات + مینی‌اپ با هم؛ رایگان و در یک دقیقه) ── */
function bpBlock(){
  const bps = S.bps;
  if(!bps || !bps.length || S.bots.length >= (S.cfg.max_bots || 10)) return "";
  return `<div class="sec bphead"><h2>چی می‌خوای بسازی؟  <small>نقشه‌های آماده؛ در یک دقیقه شخصی و آماده‌ی انتشار</small></h2></div>
    <div class="bpg">${bps.map(b => `<button class="bpc" data-a="bpopen" data-id="${esc(b.id)}">
      <span class="bpi">${IC[b.icon] || IC.bot}</span>
      <span class="bpt"><b>${esc(b.title)}</b><span>${esc(b.desc)}</span></span>
      <span class="bpf">${(b.feats || []).slice(0, 2).map(f => `<span class="chip">${esc(f)}</span>`).join("")}</span></button>`).join("")}</div>`;
}
function archSheet(){
  const b = D.bp, q = D.i || 0;
  if(q < b.questions.length){
    const qq = b.questions[q], a = D.answers[qq.k];
    const body = qq.kind === "choice"
      ? qq.opts.map(([v, l]) => `<button class="archopt${a === v ? " on" : ""}" data-a="archpick" data-v="${esc(v)}">${esc(l)}</button>`).join("")
      : `<input class="fa" id="arch-txt" value="${esc(a ?? qq.def ?? "")}" maxlength="500" placeholder="${esc(qq.hint || "بنویس…")}">`;
    return head("چی می‌خوای بسازی؟ · " + esc(b.title)) + `
      <p class="muted">${N(q + 1)} از ${N(b.questions.length)} · ${esc(qq.fa)}</p>
      <div class="fgap"></div>${body}
      <div class="bar">${q > 0 ? `<button class="b o" data-a="archprev">قبلی</button>` : `<button class="b o" data-a="archx">بی‌خیال</button>`}
        <button class="b" data-a="archnext">بعدی</button></div><div class="fgap"></div>`;
  }
  return head("آماده‌ی ساخت") + `
    <div class="panel"><b>${esc(b.title)}</b>
      <p class="muted mt">قابلیت‌هایی که دقیقاً ساخته می‌شوند، تک‌تک:</p>
      ${(b.feats || []).map(f => `<div class="vdl">${digitsHTML(f)}</div>`).join("")}
    </div>
    ${(S.bps || []).filter(x => x.id !== b.id).length ? `<div class="sub"><span>ترکیب با نقشه‌های دیگر (اختیاری)</span></div>
    <p class="muted">تا ۲ نقشه‌ی دیگر هم می‌توانی انتخاب کنی تا در همین ربات ادغام شوند. دکمه‌ی ورود به هرکدام به بخش «شروع» اضافه می‌شود.</p>
    <div class="chips">${(S.bps || []).filter(x => x.id !== b.id).map(x => `<button type="button" class="chip${(D.extra || []).includes(x.id) ? " on" : ""}" data-a="archextra" data-id="${esc(x.id)}">${IC.plus}${esc(x.title)}</button>`).join("")}</div>` : ""}
    <div class="bar"><button class="b" data-a="archgo">${IC.spark}بساز</button></div><div class="fgap"></div>`;
}
function archRead(){
  const qq = (D.bp.questions || [])[D.i || 0];
  if(!qq) return;
  if(qq.kind === "choice") return;
  const v = $("#arch-txt")?.value;
  if(v != null) D.answers[qq.k] = v;
}
function archMade(d){
  const b = D?.bp;
  S.bots = [d.bot, ...S.bots.filter(x => x.id !== d.bot.id)];
  if(d.wallet) S.wallet = d.wallet;
  S.cur = d.bot; S.sbot = d.bot.id;
  S.sheet = {kind: "info"};
  const cards = (d.cards || []).map(x => `<div class="vdl">${digitsHTML(x)}</div>`).join("");
  const steps = (d.steps || []).map(x => `<div class="steps2">← ${digitsHTML(x)}</div>`).join("");
  showSheet(head("چی ساخته شد؟") + `
    <div class="made"><h2>${esc(d.title || b?.title || "ربات ساخته شد")} آماده است</h2>${cards}${steps}</div>
    <p class="muted">${d.app ? "مینی‌اپ هم ساخته شد. از تب «مینی‌اپ» شخصی‌سازی‌اش کن و منتشرش کن." : "برای فعال‌سازی، به تب «انتشار» برو و توکن BotFather را وارد کن."}</p>
    <div class="bar"><button class="b" data-a="madetest">${IC.play}امتحانش کنم</button>
      <button class="b o" data-a="madebot">رفتن به ربات</button></div><div class="fgap"></div>`);
  haptic("ok"); bumpTokens();
}
/* متن نمونه که خودش تایپ می‌شود؛ تنها حرکت خودکار صفحه */
function startTyper(){
  const ta = $("#prompt"), id = ++startTyper.id;
  if(!ta || S.view !== "create" || reduced()) return;
  let i = 0, k = 0, hold = 0;
  (function tick(){
    if(id !== startTyper.id || !ta.isConnected) return;
    if(document.activeElement === ta || ta.value) return setTimeout(tick, 700);
    const t = EXAMPLES[i][1];
    if(k < t.length){ k += 1; ta.placeholder = t.slice(0, k); return setTimeout(tick, 42); }
    if(hold++ < 50) return setTimeout(tick, 50);
    hold = 0; k = 0; i = (i + 1) % EXAMPLES.length; setTimeout(tick, 120);
  })();
}
startTyper.id = 0;

/* ═════════════════ ربات‌های من ═════════════════ */
function renderBots(){
  const max = S.cfg.max_bots || 10, full = S.bots.length >= max;
  const list = S.bots.map(b => `<div class="gi botrow" role="button" tabindex="0" data-a="open" data-id="${esc(b.id)}">
      <span class="dot ${b.active ? "on" : ""}"></span>
      <span class="gt"><b>${esc(b.name)}</b><span class="${b.active ? "ltr" : ""}">${b.active ? "@" + esc(b.username) : "هنوز فعال نشده"}</span></span>${goIc}</div>`).join("");
  $("#app").innerHTML = `
    <div class="ph"><h1>ربات‌های من</h1><span class="cnt">${N(S.bots.length)}<span>از</span>${N(max)}</span></div>
    ${S.bots.length ? `<div class="group sep">${list}</div>${full ? "" : `<button class="b o sep-btn" data-go="create">${IC.plus}ربات جدید</button>`}`
      : `<div class="empty"><div class="ib big">${IC.bot}</div><h2>هنوز رباتی نداری</h2><p class="muted">اولین ربات را در چند دقیقه بساز.</p><button class="b sm" data-go="create">ساخت ربات</button></div>`}`;
}

/* ═════════════════ صفحه‌ی ربات ═════════════════ */
const CH_RE = /^https:\/\/t\.me\/([A-Za-z][A-Za-z0-9_]{4,31})\/?$/;
const NAME_RE = /^@?([A-Za-z][A-Za-z0-9_]{4,31})$/;
const stripTags = s => String(s || "").replace(/<[^>]*>/g, " ").replace(/&[a-zA-Z#0-9]+;/g, " ").replace(/\s+/g, " ").trim();
const titleOf = (cfg, id) => { const n = cfg.nodes[id]; return n ? (stripTags(n.title).slice(0, 26) || stripTags(n.text).slice(0, 26) || id) : "؟"; };
const kindOf = b => b.pay ? "pay" : b.app !== undefined ? "app" : b.goto !== undefined ? "goto" : b.alert !== undefined ? "alert" : b.copy !== undefined ? "copy" : b.share !== undefined ? "share" : CH_RE.test(b.url || "") ? "channel" : "url";

function renderBot(){
  const b = S.cur;
  const body = ({ai: tabAI, stats: tabStats, publish: tabPublish, more: tabMore}[S.btab] || tabAI)(b);
  $("#app").innerHTML = `
    <div class="bh2"><button class="iconb" data-a="back" aria-label="بازگشت">${IC.back}</button>
      <div class="bt"><h1>${esc(b.name)}</h1><span class="muted ${b.active ? "ltr" : ""}">${b.active ? "@" + esc(b.username) : "هنوز فعال نشده"}</span></div>
      <button class="iconb" data-sa="bot" aria-label="تنظیمات ربات">${IC.gear}</button></div>
    ${tabsHTML([["ai", "هوش مصنوعی"], ["stats", "آمار"], ["publish", "انتشار"], ["more", "بیشتر"]], S.btab, "btab")}
    ${body}`;
  if(S.btab === "ai"){
    if(S.fresh && b.thinking){ typeText($("#think .tt"), b.thinking); $("#think").scrollIntoView({behavior: "smooth", block: "nearest"}); }
    S.fresh = false;
  }
  if(S.btab === "stats" && b.active){ if(S.stats?._id === b.id) paintStats(S.stats); loadStats(); }
}
function tabAI(b){
  const c = S.cfg;
  let h = `<div class="console slim">
      <textarea id="prompt" maxlength="${c.max_prompt || 4000}" aria-label="درخواست ارتقا" placeholder="چه چیزی عوض شود؟ مثلاً: بخش پرسش‌های متداول اضافه کن"></textarea>
      <div class="cfoot"><div class="gauge"><span class="cost">مصرف توکن ${costTxt(true)}</span></div><button class="b" id="gen" data-a="gen">${IC.spark}ارتقا</button></div>
    </div>
    <div id="live"></div>
    <div class="think${b.thinking ? " show" : ""}" id="think"><span class="tt">${S.fresh ? "" : digitsHTML(b.thinking || "")}</span></div>`;
  if(S.ideas.length) h += `<div class="ideas">${S.ideas.map((t, i) => `<button class="chip" data-a="idea" data-i="${i}">${esc(t)}</button>`).join("")}</div>`;
  if(!b.active) h += `<div class="note"><div class="dt"><b>ربات هنوز فعال نیست</b>برای شروع کار، فعالش کن.</div><button class="b sm" data-a="btab" data-k="publish">فعال‌سازی</button></div>`;
  h += `<div class="panel mt" style="display:flex;flex-wrap:wrap;align-items:center;gap:12px">
      <span class="ib">${IC.studio}</span>
      <div style="flex:1;min-width:0"><b style="font-size:14px;display:block;line-height:1.6">استودیو</b><span class="muted" style="font-size:12px;line-height:1.7;display:block">نقشه‌ی ربات؛ بخش‌ها را با سیم به هم وصل کن.</span></div>
      <button class="b sm" data-a="studio" style="flex:1 0 100%">ورود به استودیو</button></div>`;
  if(b.versions) h += `<button class="b t mt" id="undo" data-a="undo">برگشت به نسخه‌ی قبلی</button>`;
  h += `<div class="panel mt"><b>تغییر با گفتگو <button class="b t" data-a="help" data-h="edit" style="min-width:26px;height:26px;padding:0 8px">؟</button></b><p class="muted mt">بگو چه چیزی عوض شود؛ پیشنهادها را تک‌تک می‌بینی و خودت تأیید می‌کنی. (${costTxt(true)} توکن)</p>
    <div class="fgap"></div><textarea id="arch-req" maxlength="1500" style="min-height:64px" placeholder="مثلاً: بخش پرسش‌های متداول اضافه کن"></textarea>
    <div class="fgap"></div><button class="b sm" data-a="archedgo">${IC.spark}اعمال تغییر</button></div>`;
  return h;
}
/* کارت‌های تغییر: خروجی معمار به‌صورت جمله‌های فارسی؛ برگشت کامل با یک دکمه */
function archCards(d){
  S.cur = d.bot; S.bots = S.bots.map(x => x.id === d.bot.id ? d.bot : x);
  if(d.wallet) S.wallet = d.wallet;
  S.sheet = {kind: "info"};
  showSheet(head("تغییرها اعمال شد") + `
    ${(d.cards || []).map(x => `<div class="vdl">${digitsHTML(x)}</div>`).join("")}
    <p class="muted mt">اگر پشیمان شدی، با یک لمس کل این تغییر برمی‌گردد.</p>
    <div class="bar"><button class="b o" data-a="archrev">${IC.refresh}برگشت این تغییر</button>
      <button class="b" data-a="archdone">تمام</button></div><div class="fgap"></div>`);
  bumpTokens(); renderTop();
}
const statCells = rows => rows.map(([k, v]) => `<div class="stat"><div class="k">${k}</div>${N(v)}</div>`).join("");
function tabStats(b){
  if(!b.active) return `<div class="empty"><div class="ib big">${IC.stats}</div><h2>هنوز آماری نیست</h2><p class="muted">بعد از فعال شدن ربات، کاربرها و بازدیدها اینجا نشان داده می‌شوند.</p><button class="b sm" data-a="btab" data-k="publish">فعال‌سازی</button></div>`;
  return `<div class="stats" id="stats">${statCells([["کاربرها", "–"], ["فعال در هفته", "–"], ["جدید امروز", "–"], ["بلاک‌شده", "–"], ["پاسخ فرم‌ها", "–"], ["توکن مصرفی AI", "–"]])}</div>
    <div id="statx"></div>
    <div class="two"><button class="b" data-a="bc">${IC.mega}پیام همگانی</button><button class="b o" data-a="subs">${IC.inbox}پاسخ فرم‌ها</button></div>`;
}
function paintStats(s){
  if(!$("#stats") || S.cur?.id !== s._id) return;
  $("#stats").innerHTML = statCells([["کاربرها", s.users], ["فعال در هفته", s.active7], ["جدید امروز", s.new24], ["بلاک‌شده", s.blocked], ["پاسخ فرم‌ها", s.forms], ["توکن مصرفی AI", s.ai_tokens]]);
  const ser = s.series || [], mx = Math.max(1, ...ser), top = s.top || [], tmx = Math.max(1, ...top.map(x => x.n));
  $("#statx").innerHTML = `<div class="sec"><h2>عضو جدید در ${N(7)} روز اخیر</h2></div>
    <div class="spark">${ser.map(v => `<i class="${v ? "" : "z"}" style="height:${Math.max(6, Math.round(v / mx * 100))}%" title="${v}"></i>`).join("")}</div>
    <div class="sparklbl"><span>${N(6)} روز پیش</span><span>امروز</span></div>
    ${top.length ? `<div class="sec"><h2>پربازدیدترین بخش‌ها</h2></div><div class="topn">${top.map(x => `<div class="tr"><span>${esc(x.title)}</span><div class="bar2"><i style="width:${Math.round(x.n / tmx * 100)}%"></i></div>${N(x.n)}</div>`).join("")}</div>` : ""}`;
}
async function loadStats(){
  try{
    const id = S.cur?.id; if(!id) return;
    const s = await api(`/api/bots/${id}/stats`); s._id = id; S.stats = s; paintStats(s);
  }catch(_){}
}
function tabPublish(b){
  if(!b.active) return `<div class="panel"><h2>فعال‌سازی</h2><p class="muted">ربات را از @BotFather بساز و توکنش را اینجا بگذار.</p>
      <div class="fgap"></div><input id="token" placeholder="123456:ABC..." autocomplete="off" aria-label="توکن ربات"><div class="fgap"></div>
      <button class="b" id="act" data-a="act">فعال کن</button></div>`;
  return `<div class="panel"><div class="pstat"><span class="dot on"></span><div><b class="ltr">@${esc(b.username)}</b><div class="muted">فعال است و تغییرات فوری اعمال می‌شوند.</div></div></div>
      <div class="two"><button class="b" data-a="openbot">${IC.open}باز کردن</button><button class="b o" data-a="sharebot">${IC.users}اشتراک</button></div>
      <p class="muted mt">برای دریافت پیام کاربرها، یک بار ربات خودت را استارت کن و با Reply جواب بده.</p></div>
    <button class="b r mt2" id="off" data-a="off">غیرفعال کردن</button>`;
}
function tabMore(b){
  const row = (a, ic, t, s) => `<button class="gi" ${a}><span class="ib">${IC[ic]}</span><span class="gt"><b>${t}</b><span>${s}</span></span>${goIc}</button>`;
  return `<div class="group">
      ${row('data-sa="bot"', "gear", "تنظیمات ربات", "نام، کانال، دستورها و متغیرها")}
      ${row('data-sa="mod"', "users", "مدیریت گروه و کانال", "قفل‌ها، کپچا، اخطار، خوش‌آمد و پست کانال")}
      ${row('data-sa="grp"', "spark", "ماشه‌های گروه", "کلمه یا دستور داخل گروه ← پاسخ، امتیاز و بازی")}
      ${row('data-a="health"', "heal", "بررسی مسیرها", "بخش‌های بدون مسیر و بن‌بست")}
      ${row('data-a="export"', "dl", "خروجی JSON", "نسخه‌ی پشتیبان از ربات")}
      ${row('data-a="subs"', "inbox", "پاسخ فرم‌ها", "آخرین پاسخ‌های ثبت‌شده")}
    </div>
    <button class="b r mt2" data-a="del">${IC.trash}حذف ربات</button>`;
}
function typeText(el, text){
  const id = ++typeText.id;
  if(!el) return;
  if(reduced()){ el.innerHTML = digitsHTML(text); return; }
  let i = 0; el.textContent = "";
  (function step(){
    if(id !== typeText.id || !el.isConnected) return;
    i = Math.min(text.length, i + 2); el.textContent = text.slice(0, i);
    if(i < text.length) setTimeout(step, 16); else el.innerHTML = digitsHTML(text);
  })();
}
typeText.id = 0;

/* ═════════════════ رسانه ═════════════════ */
function renderMedia(){
  const c = S.cfg, pct = Math.min(100, Math.round(S.used / (c.media_quota_mb * 1048576) * 100));
  $("#app").innerHTML = `
    <div class="ph"><h1>رسانه</h1><span class="cnt">${N(S.media.length)}<span>از</span>${N(c.max_media)} فایل</span></div>
    <div class="panel"><div class="usage"><div class="meter2"><i style="width:${pct}%"></i></div><span class="n">${(S.used / 1048576).toFixed(1)} / ${c.media_quota_mb} MB</span></div>
      <p class="muted mt">عکس، ویدیو، گیف، موسیقی، ویس و فایل تا ${N(c.media_max_mb)} مگابایت. هر فایل را موقع ویرایش بخش‌ها انتخاب کن.</p></div>
    <button class="dropbtn" data-a="upload">${IC.upload}<span>آپلود فایل</span></button>
    <div id="uplist">${S.uploads.map(uploadRow).join("")}</div>
    ${S.media.length ? `<div class="mgrid">${S.media.map(m => `<button class="tile" data-a="mdet" data-id="${esc(m.id)}"><div class="mi">${miInner(m)}<span class="mk">${KIND_FA[m.kind]}</span></div>
      <div class="tn"><b>${esc(m.name)}</b><span>${sizeHTML(m.size)}</span></div></button>`).join("")}</div>`
      : `<div class="empty"><div class="ib big">${IC.photo}</div><p class="muted">هنوز فایلی آپلود نکرده‌ای.</p></div>`}`;
}
const uploadRow = u => `<div class="upl" data-u="${u.id}">${esc(u.name)}<div class="pb"><i style="width:${Math.round(u.p * 100)}%"></i></div></div>`;
async function handleFiles(files, pickKey){
  for(const f of files){
    if(f.size > S.cfg.media_max_mb * 1048576){ toast(`«${f.name}» بزرگ‌تر از ${S.cfg.media_max_mb} مگابایت است`); continue; }
    const u = { id: Math.random().toString(36).slice(2), name: f.name, p: 0 };
    S.uploads.push(u); if(S.view === "media") renderMedia();
    try{
      const d = await uploadFile(f, p => { u.p = p; const el = document.querySelector(`[data-u="${u.id}"] .pb i`); if(el) el.style.width = Math.round(p * 100) + "%"; });
      S.media.unshift(d.item); S.used = d.used;
      if(pickKey && pickKey.startsWith("__cp:")) cpSt(pickKey.slice(5)).media = d.item.id;
      else if(pickKey && D){ D[pickKey] = d.item.id; }
      haptic("ok");
    }catch(e){ toast(e.message); }
    S.uploads = S.uploads.filter(x => x !== u);
  }
  if(S.view === "media") renderMedia();
  if(pickKey && pickKey.startsWith("__cp:")) return cpRefresh(pickKey.slice(5));
  if(pickKey && S.sheet) renderSheet();
}

/* ═════════════════ حساب ═════════════════ */
function packRows(){
  const best = S.packs.reduce((m, p) => p.tokens / p.stars > m.r ? {id: p.id, r: p.tokens / p.stars} : m, {id: "", r: 0}).id;
  return S.packs.map(p => { const bt = p.id === best && S.packs.length > 1;
    const cp = S.card?.on ? S.card.prices?.[p.id] : 0;
    return `<div class="pack${bt ? " best" : ""}"><div class="pt">${N(p.tokens)}<span>توکن</span></div>
    <div class="pr">${N(p.stars)} ستاره${cp ? `<br>${N(Number(cp).toLocaleString("en"))} تومان` : ""}${bt ? "<br>به‌صرفه‌ترین" : ""}</div>
    <div class="pbtns"><button class="b" data-a="buy" data-id="${esc(p.id)}">خرید</button>${cp ? `<button class="b o" data-a="cardbuy" data-id="${esc(p.id)}">کارت‌به‌کارت</button>` : ""}</div></div>`; }).join("");
}
function inviteCard(){
  const c = S.cfg, n = S.ref.count;
  return `<div class="panel"><h2>دعوت دوستان</h2>
    <p class="muted">هر دوست: <b class="n">+${N(c.ref_inviter)}</b> برای تو، <b class="n">+${N(c.ref_invitee)}</b> برای او.</p>
    ${S.ref.link ? `<div class="reflink"><code>${esc(S.ref.link)}</code><button class="b o sm" data-a="copyref">کپی</button></div><button class="b" data-a="shareref">ارسال لینک دعوت</button>`
      : `<p class="muted mt">لینک دعوت هنوز آماده نیست.</p>`}
    <div class="ms">${(c.milestones || []).map(([k, v]) => `<div class="${n >= k ? "hit" : ""}">${N(k)} دعوت<span class="n">+${v}</span></div>`).join("")}</div>
    <p class="muted mt">${N(n)} دعوت موفق${S.ref.earned ? ` · ${N(S.ref.earned)} توکن درآمد` : ""}</p></div>`;
}
function couponCard(){
  return `<div class="sec"><h2>کد هدیه</h2></div><div class="cpn"><input id="cpn" placeholder="CODE" autocomplete="off" aria-label="کد هدیه"><button class="b sm" data-a="coupon">ثبت</button></div>`;
}
function buildCard(){
  const c = S.cfg, lim = c.limits || {};
  const botsN = S.bots.length, botsMax = c.max_bots || 10;
  const medN = S.media.length, medMax = c.max_media || 60;
  const meter = (ic, k, v, m) => `<div class="qm${v >= m ? " full" : ""}"><span class="qi">${IC[ic]}</span><div class="qt"><span>${k}</span><b class="n">${v} <small>/ ${m}</small></b>
      <div class="lm-b"><i style="width:${Math.min(100, Math.round(v / Math.max(1, m) * 100))}%"></i></div></div></div>`;
  const cap = (ic, k, m) => `<div class="qc"><span class="qi">${IC[ic]}</span><b class="n">${m}</b><span>${k}</span></div>`;
  const FM = {
    agent:     ["bot",   "عامل هوشمند", "ربات با هوش مصنوعی؛ جواب می‌دهد و کار انجام می‌دهد"],
    games:     ["medal", "مرکز بازی", "بازی، رتبه‌بندی و دوئل با سکه‌ی مجازی"],
    growth:    ["users", "رشد واقعی", "دعوت، پاداش و جذب عضو با گزارش دقیق"],
    blueprint: ["layers", "نقشه‌های آماده", "قالب کامل گروه، کانال، فروشگاه و بازی"],
    whenthen:  ["bolt",  "وقتی…آنگاه", "قانون و واکنش خودکار بدون کدنویسی"],
    simulator: ["sim",   "شبیه‌ساز زنده", "تست رایگان ربات قبل از انتشار"],
    lists:     ["table", "لیست‌ها و جدول", "ذخیره‌ی داده، موجودی و سفارش‌ها"],
    doctor:    ["heal",  "دکتر ربات", "پیدا کردن و رفع خودکار مشکل‌ها"]
  };
  const ORD = Object.keys(FM);
  const keys = Object.entries(c.features || {}).filter(([, on]) => on).map(([k]) => k)
    .sort((x, y) => (ORD.indexOf(x) < 0 ? 99 : ORD.indexOf(x)) - (ORD.indexOf(y) < 0 ? 99 : ORD.indexOf(y)));
  const ft = k => { const f = FM[k] || ["spark", k, ""]; return `<div class="qf"><span class="qi">${IC[f[0]]}</span><div><b>${esc(f[1])}</b>${f[2] ? `<small>${f[2]}</small>` : ""}</div></div>`; };
  return `<div class="panel qb"><div class="qb-h"><h2>سقف‌ها و امکانات</h2><span class="bdg">v${esc(c.build || "3.0.0")}</span>
      <button class="b t qb-q" data-a="help" data-h="quota" aria-label="راهنما">؟</button></div>
    <div class="qb-m">${meter("bot", "ربات‌ها", botsN, botsMax)}${meter("photo", "فایل رسانه", medN, medMax)}</div>
    <div class="qb-c">${cap("layers", "بخش در هر ربات", lim.nodes || 200)}${cap("studio", "بلوک مینی‌اپ", lim.blocks || 120)}${cap("table", "جدول داده", lim.tables || 6)}</div>
    ${keys.length ? `<div class="qb-f">${keys.slice(0, 6).map(ft).join("")}</div>${keys.length > 6 ? `<details class="qb-more"><summary>${N(keys.length - 6)} امکان دیگر</summary><div class="qb-f">${keys.slice(6).map(ft).join("")}</div></details>` : ""}` : ""}
    <div class="qb-up"><span>سقف‌ها با اشتراک بزرگ‌تر می‌شوند</span><button class="b sm" data-a="goplan">${IC.star}دیدن اشتراک‌ها</button></div></div>`;
}
function tabWallet(){
  const w = S.wallet, c = S.cfg, per = costOf(false) || 6;
  return `<div class="wallet"><div class="big">${N(w.tokens)}<span>توکن</span></div>
      <div class="cells" title="تعداد رباتی که با این موجودی می‌توانی بسازی">${cellsHTML(buildsLeft())}</div>
      <span class="muted">برای حدود ${N(Math.floor(w.tokens / per))} ربات جدید کافی است</span>
      <div class="costs">${billingFixed() ? `<div>ساخت ربات<span class="n">${c.gen}</span></div><div>ارتقا<span class="n">${c.edit}</span></div><div>${c.ai_per} پیام هوشمند<span class="n">1</span></div>`
        : `<div>ساخت یا ارتقا<span class="n">~${c.typical}</span></div><div>حداقل<span class="n">${c.min}</span></div><div>اطلاعیه ویژه<span class="n">1/${c.bc_per}</span></div>`}</div></div>
    ${dailyCard()}
    ${buildCard()}
    <div class="sec"><h2>شارژ توکن  Ai</h2><span class="muted">با استارز تلگرام</span></div>
    <div class="group">${packRows() || '<div class="gi static"><span class="muted">فعلاً بسته‌ای تعریف نشده.</span></div>'}</div>
    ${couponCard()}`;
}
function tabHistory(){
  const w = S.wallet;
  return `<div class="stats"><div class="stat"><div class="k">ربات‌ها</div>${N(S.bots.length)}</div><div class="stat"><div class="k">ربات‌های فعال</div>${N(S.bots.filter(b => b.active).length)}</div>
      <div class="stat"><div class="k">توکن مصرف‌شده</div>${N(w.spent || 0)}</div><div class="stat"><div class="k">رسانه</div>${N(S.media.length)}</div></div>
    <div class="sec"><h2>آخرین تراکنش‌ها</h2></div>
    <div class="group" id="ledger"><div class="gi static"><span class="muted">در حال بارگذاری…</span></div></div>`;
}
function loadLedger(){
  api("/api/ledger").then(d => {
    const el = $("#ledger"); if(!el) return;
    el.innerHTML = d.items.length ? d.items.map(x => `<div class="led"><div>${why[x.why] || esc(x.why)}<small>${new Date(x.t).toLocaleDateString("fa-IR-u-nu-latn", {month: "long", day: "numeric"})}</small></div>
      <span class="n ${x.n > 0 ? "pos" : "neg"}">${x.n > 0 ? "+" : ""}${x.n}</span></div>`).join("") : '<div class="gi static"><span class="muted">هنوز تراکنشی نداری.</span></div>';
  }).catch(() => {});
}
function renderAccount(){
  const tu = tg?.initDataUnsafe?.user || {}, me = S.me || {};
  const u = {first_name: tu.first_name || me.name || "", last_name: tu.first_name ? tu.last_name : "", username: tu.username || me.username || "", photo_url: tu.photo_url};
  const name = [u.first_name, u.last_name].filter(Boolean).join(" ") || "کاربر";
  const tabs = [["wallet", "توکن"], ["plan", "ارتقا"], ["invite", "پاداش" + (readyTasks() ? '<span class="qdot"></span>' : "")], ["history", "تاریخچه"]]; if(S.admin) tabs.push(["admin", "مدیریت"]);
  if(!tabs.some(t => t[0] === S.atab)) S.atab = "wallet";
  const body = ({wallet: tabWallet, plan: planTab, invite: () => questsHTML() + '<div class="inv-end">' + inviteCard() + "</div>", history: tabHistory, admin: adminCard})[S.atab]();
  $("#app").innerHTML = `
    <div class="pf"><div class="av">${esc(name.trim().charAt(0))}${u.photo_url ? `<img src="${esc(u.photo_url)}" alt="" referrerpolicy="no-referrer" onerror="this.remove()">` : ""}</div>
      <div><h1>${esc(name)}</h1><div class="muted">${u.username ? `<span class="ltr">@${esc(u.username)}</span> · ` : ""}<span class="ltr">ID ${esc(me.id || tu.id || "")}</span>${S.plan ? ` · <span class="pbadge ${esc(S.plan.id)}" data-a="goplan">${esc(S.plan.title)}</span>` : ""}</div></div></div>
    ${tabsHTML(tabs, S.atab, "atab")}
    ${body}`;
  if(S.atab === "history") loadLedger();
  animBars();
  if(S.atab === "admin") admStart(); else admStop();
}

const VIEWS = { create: renderCreate, bots: renderBots, bot: renderBot, media: renderMedia, account: renderAccount, userbot: renderUserbot };   // «studio» در انتهای studio.js ثبت می‌شود

/* ═════════════════ اکشن‌های صفحه ═════════════════ */
const setBot = bot => { S.cur = bot; S.bots = S.bots.map(b => b.id === bot.id ? bot : b); };
const A = {
  gen: () => submitPrompt(),
  reviewyes: el => busy(el, async () => {
    const d = await api(`/api/jobs/${encodeURIComponent(el.dataset.id)}/review`, "POST", {decision: "yes"});
    closeSheet();
    if(!d.bot) throw new Error("ساخت تأیید شد اما اطلاعات ربات دریافت نشد؛ صفحه را تازه‌سازی کن.");
    S.wallet = d.wallet || S.wallet; S.bots = [d.bot, ...S.bots.filter(b => b.id !== d.bot.id)];
    S.cur = d.bot; S.view = "bot"; S.btab = "ai"; S.sbot = d.bot.id; S.fresh = true; S.ideas = d.ideas || []; S.stats = null;
    render(); bumpTokens(); toast(`نسخه‌ی تأییدشده ساخته شد${d.cost ? `، ${d.cost} توکن` : ""}`); haptic("ok"); scrollTo(0, 0);
  }),
  reviewno: el => busy(el, async () => {
    await api(`/api/jobs/${encodeURIComponent(el.dataset.id)}/review`, "POST", {decision: "no"});
    closeSheet(); await sync(); render(); toast("درخواست لغو شد؛ توکنی کسر نشد.");
  }),
  chip: el => { const t = $("#prompt"); t.value = EXAMPLES[+el.dataset.i][1]; t.focus(); },
  idea: el => { const t = $("#prompt"); t.value = S.ideas[+el.dataset.i]; t.focus(); t.scrollIntoView({behavior: "smooth", block: "center"}); },
  open: el => { S.cur = S.bots.find(b => b.id === el.dataset.id); if(!S.cur) return; S.view = "bot"; S.btab = "ai"; S.sbot = S.cur.id; S.ideas = []; S.stats = null; render(); scrollTo(0, 0); },
  back: () => { S.view = "bots"; S.cur = null; S.ideas = []; closeSheet(); render(); scrollTo(0, 0); sync().then(ok => { if(ok && S.view === "bots") render(); }); },
  btab: el => { if(S.busy) return toast("کار قبلی هنوز تمام نشده؛ کمی صبر کن"); S.btab = el.dataset.k; renderBot(); },
  atab: el => { S.atab = el.dataset.k; renderAccount(); },
  daily: el => busy(el, async () => {
    const d = await api("/api/daily", "POST");
    Object.assign(S, {wallet: d.wallet, cfg: d.cfg, tasks: d.tasks});
    if(S.sheet?.kind === "buy") closeSheet();
    render(); bumpTokens(); toast(`${d.reward} توکن جایزه گرفتی`); haptic("ok");
  }),
  claim: el => busy(el, async () => {
    const d = await api(`/api/tasks/${el.dataset.id}/claim`, "POST");
    Object.assign(S, {tasks: d.tasks, wallet: d.wallet, cfg: d.cfg});
    render(); bumpTokens(); haptic("ok"); toast(`${d.gain.tokens} توکن دریافت شد`);
  }),
  goplan: () => { S.atab = "plan"; goTo("account"); },
  planbuy: el => buyPlan(el.dataset.id, el),
  plantog: el => {
    const c = el.closest(".plan"), on = !c.classList.contains("open");
    document.querySelectorAll(".plan.open").forEach(x => { x.classList.remove("open"); x.querySelector(".plhd")?.setAttribute("aria-expanded", "false"); });
    c.classList.toggle("open", on); el.setAttribute("aria-expanded", String(on)); S.planOpen = on ? c.dataset.id : "";
  },
  emjdel: el => busy(el, async () => { const d = await api("/api/emojis/" + el.dataset.id, "DELETE"); S.emojis = d.items; renderAccount(); }),
  emjbot: () => { const m = /t\.me\/([^?\/]+)/.exec(S.ref?.link || ""); if(m) openLink("https://t.me/" + m[1]); else toast("ربات مادر را در تلگرام باز کن و ایموجی را برایش بفرست"); },
  adplan: el => busy(el, async () => {
    const v = id => $(id).value.trim();
    const d = await api("/api/admin/plan", "POST", {uid: v("#ap-uid"), plan: v("#ap-plan"), days: v("#ap-days")});
    toast(d.plan.id === "free" ? "اشتراک لغو شد" : `اشتراک ${d.plan.title} فعال شد (${d.plan.days_left} روز)`);
  }),
  undo: el => busy(el, async () => { const d = await api(`/api/bots/${S.cur.id}/undo`, "POST"); setBot(d.bot); S.ideas = []; render(); toast("برگشت داده شد"); }),
  act: el => { const t = $("#token").value.trim(); if(!t) return toast("توکن را وارد کن");
    busy(el, async () => { const d = await api(`/api/bots/${S.cur.id}/activate`, "POST", {token: t}); setBot(d.bot); render(); toast("ربات فعال شد"); haptic("ok"); }); },
  off: el => busy(el, async () => { const d = await api(`/api/bots/${S.cur.id}/deactivate`, "POST"); setBot(d.bot); render(); toast("ربات غیرفعال شد"); }),
  del: () => confirmQ("این ربات برای همیشه حذف شود؟", async ok => {
    if(!ok) return;
    try{ await api(`/api/bots/${S.cur.id}`, "DELETE"); S.view = "bots"; S.cur = null; await sync(); render(); scrollTo(0, 0); toast("ربات حذف شد"); }
    catch(e){ toast(e.message); }
  }),
  bc: () => openBc(),
  upload: () => { S.pickKey = null; $("#fileIn").click(); },
  mdet: el => openMedia(el.dataset.id),
  buy: el => buyPack(el.dataset.id, el),
  copyref: () => navigator.clipboard?.writeText(S.ref.link).then(() => toast("لینک دعوت کپی شد"), () => toast(S.ref.link)),
  help: el => {
    const H = {
      edit: ["تغییر با گفتگو", "درخواستت را بنویس تا هوش مصنوعی تغییرها را به‌صورت کارت‌های ساده پیشنهاد بدهد. هر کارت را تأیید یا رد کن؛ فقط تأییدشده‌ها اعمال می‌شوند و برای هر تغییر یک نسخه‌ی برگشت هم ساخته می‌شود."],
      studio: ["استودیو", "هر بخش یک پیام از ربات است. دایره‌ی کنار هر دکمه را روی بخش دیگری بکش تا مسیر آن دکمه ساخته شود. با «انتخاب» می‌توانی چند بخش را یک‌جا کپی یا حذف کنی."],
      tokens: ["توکن چیست؟", "ساخت و ارتقای ربات و پیام‌های هوشمند، توکن مصرف می‌کنند. توکن را از بسته‌های شارژ، جایزه‌ی روزانه و دعوت دوستان به‌دست می‌آوری. اگر ساخت ناموفق باشد، توکن به حسابت برمی‌گردد."],
      quota: ["سقف‌ها", "هر اشتراک برای تعداد ربات، بخش‌های هر ربات، بلوک مینی‌اپ و جدول داده سقف مشخصی دارد. با اشتراک Premium یا Pro این سقف‌ها بیشتر می‌شود."],
    };
    const [t, x] = H[el.dataset.h] || H.edit;
    S.sheet = {kind: "info"};
    showSheet(head(t) + `<p style="line-height:2">${digitsHTML(x)}</p><div class="fgap"></div>`);
  },
  shareref: () => openLink("https://t.me/share/url?url=" + encodeURIComponent(S.ref.link) + "&text=" + encodeURIComponent("با این ربات، هر رباتی که بخواهی را با هوش مصنوعی بساز")),
};

Object.assign(A, {
  bpopen: el => {
    const b = (S.bps || []).find(x => x.id === el.dataset.id);
    if(!b) return;
    D = {bp: b, answers: {}, i: 0, extra: []};
    S.sheet = {kind: "arch"}; renderSheet();
  },
  archextra: el => {
    const id = el.dataset.id;
    D.extra = D.extra || [];
    const i = D.extra.indexOf(id);
    if(i >= 0) D.extra.splice(i, 1); else if(D.extra.length < 2) D.extra.push(id); else return toast("حداکثر ۲ نقشه می‌توانی اضافه کنی");
    renderSheet();
  },
  archpick: el => { const qq = D.bp.questions[D.i]; D.answers[qq.k] = el.dataset.v; A.archnext(); },
  archnext: () => { archRead(); D.i = (D.i || 0) + 1; renderSheet(); },
  archprev: () => { archRead(); D.i = Math.max(0, (D.i || 0) - 1); renderSheet(); },
  archx: () => closeSheet(),
  archgo: el => busy(el, async () => {
    const d = await api("/api/arch/build", "POST", {bid: D.bp.id, answers: D.answers, extra: D.extra || []});
    S.bots.length && sync();
    archMade(d);
  }),
  madetest: () => { closeSheet(); const b = S.cur; S.view = "studio"; ST.botId = null; closeSheet(); render(); setTimeout(() => A.simopen(), 350); },
  madebot: () => { closeSheet(); S.view = "bot"; S.btab = "ai"; render(); scrollTo(0, 0); },
  archedgo: el => busy(el, async () => {
    const req = ($("#arch-req")?.value || "").trim();
    if(req.length < 4) return toast("بنویس چه چیزی عوض شود");
    const cost = needCost(true);
    if(S.wallet.tokens < cost) return openBuy(`این تغییر حداقل ${cost} توکن می‌خواهد.`);
    try{
      const d = await api(`/api/bots/${S.cur.id}/archedit`, "POST", {request: req});
      archPlan(d);                      // کارت‌ها قبل از ذخیره نمایش داده می‌شوند؛ تایید تک‌تک
      bumpTokens(); renderTop();
    }catch(e){ if(e.status === 402) openBuy(e.message); else toast(e.message); }
  }),
  archpick2: el => {
    const i = +el.dataset.i;
    const box = $(`#arch-op${i}`);
    if(box) box.checked = !box.checked;
    el.classList.toggle("on", box?.checked);
  },
  archapply: el => busy(el, async () => {
    const ops = D.ops.filter((_, i) => $(`#arch-op${i}`)?.checked);
    if(!ops.length) return toast("حداقل یک تغییر را تایید کن");
    try{
      const d = await api(`/api/bots/${S.cur.id}/archedit/apply`, "POST", {ops});
      archCards(d);
    }catch(e){ toast(e.message); }
  }),
  archrev: el => busy(el, async () => {
    const d = await api(`/api/bots/${S.cur.id}/undo`, "POST");
    setBot(d.bot); closeSheet(); render(); toast("برگشت داده شد");
  }),
  archdone: () => { closeSheet(); render(); },
});
function archPlan(d){
  D = {ops: d.ops || []};
  S.sheet = {kind: "info"};
  showSheet(head("این تغییرها آماده است — تایید کن") + `
    <p class="muted">هوش مصنوعی این تغییرها را پیشنهاد داده است. تیک آن‌هایی را که می‌خواهی بگذار و بقیه را بردار. هنوز چیزی ذخیره نشده.</p>
    ${(d.ops || []).map((op, i) => `<button type="button" class="archcard on" data-a="archpick2" data-i="${i}">
      <input type="checkbox" id="arch-op${i}" hidden checked><span class="tick">${IC.check}</span><span>${digitsHTML((d.cards || [])[i] || "تغییر پیشنهادی")}</span></button>`).join("")}
    <div class="bar"><button class="b" data-a="archapply">${IC.spark}اعمال تاییدشده‌ها</button>
      <button class="b o" data-a="archx">بی‌خیال</button></div><div class="fgap"></div>`);
}
document.addEventListener("click", e => {
  const g = e.target.closest("[data-go]"); if(g) return goTo(g.dataset.go);
  const a = e.target.closest("[data-a]"); if(a) return A[a.dataset.a]?.(a);
  const x = e.target.closest("[data-x],[data-sa],[data-sh]"); if(!x || x.tagName === "SELECT") return;
  const ds = x.dataset;
  if(ds.x) return stGuardClose(closeSheet);
  if(ds.sh) return shAction(ds.sh, ds);
  const r = ds.r !== undefined ? +ds.r : null;
  if(ds.sa === "bot") openBot();
  if(ds.sa === "mod") openMod();
  if(ds.sa === "grp") openGrp();
});
document.addEventListener("keydown", e => {
  if(e.key !== "Enter" && e.key !== " ") return;
  const r = e.target.closest?.(".botrow");
  if(r){ e.preventDefault(); A.open(r); }
});
document.addEventListener("change", e => {
  if(e.target.id === "fileIn"){ const files = [...e.target.files], k = S.pickKey; e.target.value = ""; if(files.length) handleFiles(files, k); return; }
  const a = e.target.dataset.sh;
  if(a === "mode" || a === "bkind" || a === "re") shAction(a, e.target.dataset);
});
document.addEventListener("focusin", e => {
  if(!e.target.matches?.("input,textarea,select")) return;
  setDock(false); $("#dock").classList.add("hide");
  if(e.target.id === "prompt" && S.view === "create") e.target.placeholder = "رباتی که لازم داری را توضیح بده…";
});
document.addEventListener("focusout", () => setTimeout(() => { if(!document.activeElement?.matches?.("input,textarea,select")) $("#dock").classList.remove("hide"); }, 150));

/* ═════════════════ ماموریت‌ها ═════════════════ */
IC.check = svg('<path d="M5 12.5l4.5 4.5L19 7.5"/>', 2.6);
S._bw = {};
/* نوارها و حلقه‌ی پیشرفت: از مقدار قبلی تا مقدار تازه با انیمیشن پر می‌شن (مرحله یا سطح عوض شد، از صفر) */
function animBars(){
  const rm = reduced(), D = 900;
  document.querySelectorAll("[data-p]").forEach(el => {
    const k = el.dataset.k, p = +el.dataset.p, st = el.dataset.s || "", prev = S._bw[k];
    const cv = document.querySelector(`[data-cv][data-k="${k}"]`), v = cv ? +cv.dataset.cv : 0;
    const same = prev && prev.s === st, p0 = same ? prev.p : 0, v0 = same ? prev.v : 0;
    S._bw[k] = {p, v, s: st};
    const set = q => { if(el.tagName === "circle") el.style.strokeDashoffset = 138.2 * (1 - q / 100); else el.style.width = q + "%"; };
    const put = (q, c) => { set(q); if(cv) cv.textContent = fa(Math.round(c)); };
    el.style.transition = "none";
    if(rm || (p0 === p && v0 === v)){ put(p, v); return; }
    put(p0, v0);
    const t0 = performance.now();
    const step = t => { const x = Math.min(1, (t - t0) / D), e = 1 - Math.pow(1 - x, 3); put(p0 + (p - p0) * e, v0 + (v - v0) * e); if(x < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  });
}
function richCard(t){
  const cur = t.steps.findIndex(s => !s.done), s = t.steps[cur];
  const rail = t.steps.map((x, i) => `<li class="${x.done ? "d" : x.ready ? "r" : i === cur ? "c" : ""}"><i>${x.done ? IC.check : N(i + 1)}</i><span>${N("+" + x.tokens)}</span></li>`).join("");
  const pct = s ? Math.round(Math.min(s.value, s.goal) / s.goal * 100) : 100;
  const body = !s ? "" : `<div class="mc"><div class="mn"><b>مرحله‌ی ${N(cur + 1)}: ${esc(s.label)}</b><span>${digitsHTML(s.hint)}</span></div>
    <div class="pbar"><i data-k="${t.id}" data-s="${cur}" data-p="${pct}"></i></div>
    <div class="qr"><span class="qg"><span class="n" data-cv="${s.value}" data-k="${t.id}">${fa(s.value)}</span> از ${N(fa(s.goal))}</span><span class="qrw"><span class="xbd t">${N("+" + s.tokens)} توکن</span></span>
    ${s.ready ? `<button class="b amber sm" data-a="claim" data-id="${esc(t.id)}">دریافت</button>` : ""}</div></div>`;
  return `<div class="mp"><div class="mph"><span class="ib">${IC[t.icon] || IC.spark}</span><div class="gt"><b>${esc(t.title)}</b><span>${t.done ? "همه‌ی مرحله‌ها را گرفتی" : esc(t.desc)}</span></div>
    <span class="mpc"><span class="n">${t.stage}/${t.total}</span></span></div><ol class="rail">${rail}</ol>${body}</div>`;
}
function taskCard(t){
  if(t.rich) return richCard(t);
  const v = Math.min(t.value, t.goal), pct = Math.round(v / t.goal * 100);
  const dots = Array.from({length: t.total}, (_, i) => `<i class="${i < t.stage ? "on" : ""}"></i>`).join("");
  const body = t.done ? "" : `<div class="pbar"><i data-k="${t.id}" data-s="${t.stage}" data-p="${pct}"></i></div>
    <div class="qr"><span class="qg"><span class="n" data-cv="${v}" data-k="${t.id}">${fa(v)}</span> از ${N(fa(t.goal))}</span>
      <span class="qrw">${t.tokens ? `<span class="xbd t">${N("+" + t.tokens)} توکن</span>` : ""}</span>
      ${t.ready ? `<button class="b amber sm" data-a="claim" data-id="${esc(t.id)}">دریافت</button>` : ""}</div>`;
  return `<div class="q${t.ready ? " ready" : ""}${t.done ? " fin" : ""}"><div class="qt"><span class="ib">${IC[t.icon] || IC.spark}</span>
    <div class="gt"><b>${esc(t.title)}</b><span>${t.done ? "همه‌ی مرحله‌ها کامل شد" : digitsHTML(t.text)}</span></div>${t.total > 1 ? `<div class="qdots">${dots}</div>` : ""}</div>${body}</div>`;
}
const readyTasks = () => (S.tasks || []).filter(t => t.ready).length;
function questsHTML(){
  const r = readyTasks(), list = [...(S.tasks || [])].sort((a, b) => (b.ready - a.ready) || (a.done - b.done));
  return `<div class="sec"><h2>ماموریت‌ها</h2>${r ? `<span class="muted">${N(r)} پاداش آماده</span>` : ""}</div><div class="qs">${list.map(taskCard).join("")}</div>`;
}
/* ═════════════════ اشتراک و ایموجی پرمیوم ═════════════════ */
const PLAN_RANK_FA = ["free", "premium", "pro"];
function planTab(){
  const cur = S.plan || {id: "free", title: "Free", days_left: 0}, rk = id => PLAN_RANK_FA.indexOf(id);
  const hd = cur.id === "free"
    ? `<div class="planhd"><small>پلن شما</small><h2>Free</h2><span class="muted">با Premium یا Pro به ایموجی پرمیوم، دکمه‌ی رنگی، یوزربات و سقف‌های بزرگ‌تر دسترسی پیدا می‌کنی.</span></div>`
    : `<div class="planhd on ${esc(cur.id)}"><small>پلن شما</small><h2>${esc(cur.title)}</h2><span class="muted">${N(cur.days_left)} روز مانده</span></div>`;
  const cards = (S.cfg.plans || []).filter(p => p.id !== "free").map(p => {
    const mine = cur.id === p.id, lower = rk(p.id) < rk(cur.id), cp = S.card?.on ? S.card.prices?.["plan_" + p.id] : 0;
    const verb = mine ? "تمدید" : cur.id !== "free" ? "ارتقا" : "خرید";
    const buy = lower ? `<button class="b o" disabled>پلن بالاتر فعاله</button>`
      : `<button class="b${p.id === "pro" ? "" : " o"}" data-a="planbuy" data-id="${esc(p.id)}">${verb} با ستاره · ${N(p.stars)} ستاره</button>${cp ? `<button class="b o" data-a="cardbuy" data-plan="${esc(p.id)}">${verb} با کارت‌به‌کارت · ${N(Number(cp).toLocaleString("en"))} تومان</button>` : ""}`;
    const open = S.planOpen === p.id;
    return `<div class="plan ${esc(p.id)}${mine ? " mine" : ""}${open ? " open" : ""}" data-id="${esc(p.id)}">
      <button class="plhd" data-a="plantog" aria-expanded="${open}"><span class="pic">${IC[p.id === "pro" ? "flame" : "spark"]}</span>
        <span class="pnm"><b>${esc(p.title)}</b><small>${mine ? `پلن فعلی · ${N(cur.days_left)} روز مانده` : `${N(p.days)} روز`}</small></span>
        <span class="ppr">${N(p.stars)}<small>ستاره</small></span><span class="chv">${IC.chev}</span></button>
      <div class="pbody"><ul>${p.perks.map(x => `<li>${digitsHTML(x)}</li>`).join("")}<li class="t">${N("+" + p.tokens)} توکن هدیه</li></ul><div class="pbuy">${buy}</div></div></div>`;
  }).join("");
  return `${hd}<div class="plans">${cards}</div>${emojiPanel()}`;
}
const emjImg = e => e.url ? `<img src="${esc(e.url)}" alt="${esc(e.char)}" loading="lazy" referrerpolicy="no-referrer">` : esc(e.char);
function emjTag(id, ch){
  const e = (S.emojis || []).find(x => x.id === id);
  return e && e.url ? `<img class="te" src="${esc(e.url)}" alt="${ch}">` : ch;
}
async function emjLoad(){
  try{ const d = await api("/api/emojis"); S.emojis = d.items; }catch(_){ S.emojis = []; }
  if(S.view === "account" && S.atab === "plan") renderAccount();
}
function emojiPanel(){
  const mx = S.cfg.emoji_max || 0;
  if(S.emojis === undefined && mx){ S.emojis = null; emjLoad(); }
  const list = S.emojis || [];
  const items = list.map(e => `<div class="emj"><span class="ei">${emjImg(e)}</span><button class="x" data-a="emjdel" data-id="${esc(e.id)}" aria-label="حذف">×</button></div>`).join("");
  return `<div class="sec"><h2>ایموجی‌های پرمیوم</h2>${mx ? `<span class="muted">${N(list.length)} از ${N(mx)}</span>` : ""}</div>
    <div class="panel"><p class="muted">${mx ? "ایموجی پرمیوم را برای ربات مادر بفرست تا به کتابخانه‌ات اضافه شود. بعد در ویرایشگر متن و دکمه‌ها، از همین‌جا انتخابش کن." : "با اشتراک Premium یا Pro می‌توانی ایموجی پرمیوم را در متن و دکمه‌های ربات‌هایت بگذاری."}</p>
      ${mx ? `<div class="emjs">${items || '<span class="muted">هنوز ایموجی‌ای اضافه نکردی.</span>'}</div><button class="b o sm" data-a="emjbot">ارسال ایموجی به ربات مادر</button>` : ""}
      <p class="muted mt">نکته: ایموجی پرمیوم فقط وقتی دیده می‌شود که حساب تلگرامِ سازنده‌ی ربات در BotFather، اشتراک تلگرام پرمیوم داشته باشد؛ وگرنه ایموجی معمولی نشان داده می‌شود. رنگ دکمه‌ها به این شرط نیاز ندارد.</p></div>`;
}

/* ═════════════════ ابزارهای ربات ═════════════════ */
const HEALTH_FA = [["unreachable nodes", "بخش‌های بدون مسیر ورود"], ["dead-end nodes", "بن‌بست‌ها (دکمه‌ی بازگشت ندارند)"], ["variables that are read", "متغیرهای بدون مقدار"]];
function textSheet(title, text, hint){
  S.sheet = {kind: "info"};
  showSheet(head(title) + (hint ? `<p class="muted" style="margin:6px 0 10px">${hint}</p>` : "") + `<textarea id="tx-out" class="code" readonly></textarea><div class="fgap"></div>
    <button class="b" data-a="copyout">${IC.copy}کپی</button><div class="fgap"></div><div class="fgap"></div>`);
  $("#tx-out").value = text;
}
const fdate = t => new Date(t).toLocaleString("fa-IR-u-nu-latn", {month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"});
async function openSubs(){
  S.sheet = {kind: "info"}; showSheet(head("پاسخ فرم‌ها") + `<p class="muted">در حال بارگذاری…</p>`);
  try{
    const d = await api(`/api/bots/${S.cur.id}/submissions`); S.subs = d.items;
    showSheet(head("پاسخ فرم‌ها") + (d.items.length ? `<button class="b o sm" data-a="csv">${IC.dl}خروجی CSV</button><div class="fgap"></div>` + d.items.map(r => `<div class="sub2"><small>${esc(r.title)}، ${esc(r.name)}${r.un ? " @" + esc(r.un) : ""}، ${fdate(r.t)}</small>${r.qa.length ? r.qa.map(([q, a]) => `${esc(q)}\n» <b>${esc(a)}</b>`).join("\n") : esc(r.text)}</div>`).join("") : `<p class="muted" style="margin-top:8px">هنوز پاسخی ثبت نشده.</p>`) + `<div class="fgap"></div>`);
  }catch(e){ closeSheet(); toast(e.message); }
}
const csvOf = items => { const q = v => '"' + String(v ?? "").replace(/"/g, '""') + '"';
  return ["time,section,name,username,answers", ...items.map(r => [r.t, r.title, r.name, r.un, (r.qa || []).map(([a, b]) => a + ": " + b).join(" | ") || r.text].map(q).join(","))].join("\n"); };

Object.assign(A, {
  studio: () => { const b = S.cur; if(!b) return toast("اول یک ربات انتخاب کن"); S.view = "studio"; S.btab = "ai"; S.sbot = b.id; closeSheet(); render(); },
  stback: () => stGuardClose(() => { stSaveNow(); S.view = "bot"; S.btab = "ai"; closeSheet(); render(); scrollTo(0, 0); }),
  stbots: () => stGuardClose(() => { stSaveNow(); S.view = "studio"; S.cur = null; S.sbot = null; ST.botId = null; render(); }),
  spick: el => { const b = S.bots.find(x => x.id === el.dataset.id); if(!b) return; S.cur = b; S.sbot = b.id; S.view = "studio"; ST.botId = null; render(); },
  stadd: () => addNode(),
  stzin: () => { const cv = $("#stc"); if(cv) stZoomAt(cv.clientWidth / 2, cv.clientHeight / 2, 1.22, true); },
  stzout: () => { const cv = $("#stc"); if(cv) stZoomAt(cv.clientWidth / 2, cv.clientHeight / 2, 1 / 1.22, true); },
  stfit: () => stFit(true),
  stlay: () => {
    const u = $("#stu"); if(!u || !S.cur) return;
    stMeasure();
    u.classList.add("arranging");              // سیم‌ها تا تمام شدن حرکت پنهان می‌مانند
    stAutoLayout(true);
    stPlaceCards();
    stMini(true);
    stFit(true);
    clearTimeout(ST._lt);
    ST._lt = setTimeout(() => { stPaintWires(); requestAnimationFrame(() => u.classList.remove("arranging")); }, 540);
    toast("بخش‌ها مرتب شدند");
  },
  stmenu: (el, e) => { e?.stopPropagation?.(); stCardMenu(el.dataset.n); },
  stenergy: () => { const b = S.cur; if(!b) return; S.view = "bot"; S.btab = "publish"; render(); scrollTo(0, 0); },
  stnew: () => stCreateConnected(),
  stpopx: () => { ST.drop = null; ST.dropAt = null; stClosePop(); },
  sthint: () => { try{ localStorage.setItem("azadi.studio.hint", "1"); }catch(_){} $(".st-hint")?.remove(); },
  strow: el => { if(!$("#stc")) return; openBtn(el.dataset.n, +el.dataset.r, +el.dataset.c); },
  health: el => busy(el, async () => {
    const d = await api(`/api/bots/${S.cur.id}/health`);
    const fa = s => { const m = [["unreachable nodes", "بخش‌های بدون مسیر ورود"], ["dead-end nodes", "بن‌بست‌ها"], ["variables that are read", "متغیرهای بدون مقدار"]].find(([k]) => s.startsWith(k));
      if(!m) return esc(s);
      return `<b>${m[1]}:</b> ` + esc(s.slice(s.indexOf(":") + 1).trim().split(",").map(x => titleOf(S.cur.config, x.trim()) || x.trim()).join("، ")); };
    S.sheet = {kind: "info"};
    showSheet(head("بررسی مسیرها") + (d.issues.length
      ? `<div class="group" style="margin-top:10px">${d.issues.map(s => `<div class="gi static"><span class="ib" style="color:var(--tok);background:var(--toks)">${IC.heal}</span><span class="gt" style="white-space:normal;font-size:13px;line-height:1.8">${fa(s)}</span></div>`).join("")}</div>`
      : `<div class="empty"><div class="ib big" style="color:var(--ok)">${IC.check}</div><h2>همه‌چیز سالم است</h2><p class="muted">از بخش شروع به همه‌ی بخش‌ها می‌شود رسید و هیچ بخشی بدون ادامه نیست.</p></div>`) + `<div class="fgap"></div>`);
  }),
  enhance: el => { const t = $("#prompt"), p = t?.value.trim() || ""; if(p.length < 5) return toast("اول یک توضیح کوتاه بنویس");
    if(S.wallet.tokens < (S.cfg.enhance || 1)) return openBuy("برای کامل‌تر کردن توضیح، توکن کافی نداری.");
    busy(el, async () => { const d = await api("/api/enhance", "POST", {prompt: p}); t.value = d.prompt; S.wallet = d.wallet; renderTop(); bumpTokens(); toast("توضیح کامل‌تر شد؛ بخوان و اگر خوب بود بساز"); haptic("ok"); }); },
  tpl: el => { const t = S.templates.find(x => x.id === el.dataset.id), c = t?.cost || 0;
    if(S.wallet.tokens < c) return openBuy(`این قالب ${c} توکن می‌خواهد و موجودی تو ${S.wallet.tokens} توکن است.`);
    busy(el, async () => {
      try{
        const d = await api(`/api/templates/${el.dataset.id}/create`, "POST");
        if(d.wallet) S.wallet = d.wallet;
        S.bots = [d.bot, ...S.bots]; S.cur = d.bot; S.view = "bot"; S.btab = "ai"; S.sbot = d.bot.id; S.fresh = true; S.ideas = []; S.stats = null;
        render(); bumpTokens(); celebrate(); toast("قالب آماده شد" + (d.cost ? `، ${d.cost} توکن` : "")); scrollTo(0, 0);
      }catch(e){ if(e.status === 402){ if(e.data?.wallet){ S.wallet = e.data.wallet; renderTop(); } openBuy(e.message); } else throw e; }
    }); },
  export: el => busy(el, async () => { const d = await api(`/api/bots/${S.cur.id}/export`); textSheet("خروجی JSON", JSON.stringify(d.config, null, 2), "نسخه‌ی پشتیبان از تنظیمات این ربات؛ آن را در جای امن نگه دار."); }),
  subs: () => openSubs(),
  csv: () => textSheet("خروجی CSV", csvOf(S.subs || []), "آخرین 50 پاسخ. در اکسل یا گوگل‌شیت پیست کن."),
  copyout: () => { const t = $("#tx-out"); t.select(); navigator.clipboard?.writeText(t.value).then(() => toast("کپی شد"), () => toast("متن را دستی کپی کن")); },
  openbot: () => openLink(`https://t.me/${S.cur.username}?start=test`),
  sharebot: () => openLink("https://t.me/share/url?url=" + encodeURIComponent(`https://t.me/${S.cur.username}`) + "&text=" + encodeURIComponent(S.cur.name)),
  coupon: el => { const v = ($("#cpn")?.value || "").trim(); if(!v) return toast("کد را وارد کن");
    busy(el, async () => { const d = await api("/api/coupon", "POST", {code: v}); S.wallet = d.wallet; render(); bumpTokens(); toast(`${d.got} توکن اضافه شد`); haptic("ok"); }); },
  copyid: el => navigator.clipboard?.writeText(el.dataset.id).then(() => toast("شناسه کپی شد"), () => toast(el.dataset.id)),
  agrant: el => busy(el, async () => { const d = await api("/api/admin/grant", "POST", {uid: $("#ag-uid").value.trim(), amount: $("#ag-amt").value.trim()}); toast(`موجودی جدید کاربر: ${d.bal}`); }),
  acoupon: el => busy(el, async () => { const v = id => $(id).value.trim(); const d = await api("/api/admin/coupon", "POST", {code: v("#ac-code"), tokens: v("#ac-tok"), max_uses: v("#ac-max"), days: v("#ac-days")});
    toast("کد ساخته شد: " + d.code); navigator.clipboard?.writeText(d.code); }),
  astats: el => busy(el, async () => { const d = await api("/api/admin/stats");
    $("#astats").innerHTML = statCells([["کاربران", d.users], ["آنلاین", d.online], ["جدید امروز", d.new24], ["ربات‌ها", d.bots], ["ربات فعال", d.active],
      ["مخاطب ربات‌ها", d.bot_users], ["پاسخ فرم‌ها", d.forms], ["توکن در گردش", d.circulation], ["دعوت موفق", d.referrals]]); }),
  aannounce: el => { const {text, media, fmt} = cpPayload("an"); if(!media && text.length < 3) return toast("متن اعلان را بنویس");
    const b = !!$("#an-b")?.checked, a = !!$("#an-a")?.checked; if(!b && !a) return toast("حداقل یک گیرنده را تیک بزن");
    confirmQ(`این اعلان برای ${[b && "سازنده‌ها", a && "مخاطبان ربات‌های فعال"].filter(Boolean).join(" و ")} فرستاده شود؟`, ok => ok && busy(el, async () => { const d = await api("/api/admin/announce", "POST", {text, media, fmt, builders: b, audience: a}); toast(`ارسال برای ${d.queued} نفر شروع شد`); cpReset("an"); })); },
  ausers: () => openUsers(),
});
document.addEventListener("click", e => { const c = e.target.closest("[data-pf=copyid]"); if(c) A.copyid(c); });

/* ═════════════════ مدیریت ═════════════════ */
const _op = k => S.aopen?.[k] ? " open" : "";
function adminSettings(){
  if(S.fj === undefined){ S.fj = null; api("/api/admin/force-join").then(d => { S.fj = d; admSetPaint(); }).catch(() => { S.fj = {on: false, channels: "", text: ""}; }); }
  const fj = S.fj || {on: false, channels: "", text: ""};
  const PRD = {on: false, min_users: 10, pct: 30, lock_pct: 20, channels: "", text: "", lock_text: "", stats: {}};
  if(S.pr === undefined){ S.pr = null; api("/api/admin/promo").then(d => { S.pr = d; admSetPaint(); }).catch(() => { S.pr = PRD; }); }
  const pr = S.pr || PRD;
  if(S.cd === undefined){ S.cd = null; api("/api/admin/card").then(d => { S.cd = d; admSetPaint(); }).catch(() => { S.cd = {on: false, number: "", holder: "", bank: "", text: "", prices: {}, orders: []}; }); }
  const cd = S.cd || {on: false, number: "", holder: "", bank: "", text: "", prices: {}, orders: []};
  const planPanel = `<details class="adv acc" data-ak="plan"${_op("plan")}><summary>اشتراک دستی</summary><div class="accb"><p class="muted">برای هدیه یا اصلاح اشتراک یک کاربر. «Free» اشتراک رو لغو می‌کند. تعداد روز خالی = یک دوره‌ی کامل.</p><div class="fgap"></div>
      <span class="lbl">آیدی عددی کاربر</span><input class="ltr" id="ap-uid" inputmode="numeric" autocomplete="off" aria-label="آیدی کاربر">
      <span class="lbl">پلن</span><select id="ap-plan" aria-label="پلن">${(S.cfg.plans || []).map(p => `<option value="${esc(p.id)}">${esc(p.title)}</option>`).join("")}</select>
      <span class="lbl">تعداد روز (اختیاری)</span><input class="ltr" id="ap-days" inputmode="numeric" autocomplete="off" aria-label="تعداد روز">
      <button class="b o" data-a="adplan">اعمال</button></div></details>`;
  return planPanel + `<details class="adv acc" data-ak="card"${_op("card")}><summary>کارت‌به‌کارت</summary><div class="accb"><p class="muted">کاربر مبلغ را واریز می‌کند، عکس رسید را در ربات می‌فرستد و تو با یک دکمه تأیید می‌کنی؛ توکن همان لحظه شارژ می‌شود. اسم صاحب کارت اختیاری است، ولی اپ بانکِ پرداخت‌کننده در هر حال اسم صاحب کارت را نشان می‌دهد.</p><div class="fgap"></div>
      <label class="chk"><input type="checkbox" id="cd-on"${cd.on ? " checked" : ""}> فعال باشد</label>
      <span class="lbl">شماره کارت (۱۶ رقم)</span><input class="ltr" id="cd-num" inputmode="numeric" value="${esc(cd.number)}" placeholder="6037 0000 0000 0000" autocomplete="off" aria-label="شماره کارت">
      <span class="lbl">به نام (اختیاری)</span><input class="fa" id="cd-holder" value="${esc(cd.holder)}" maxlength="60" aria-label="نام صاحب کارت">
      <span class="lbl">بانک (اختیاری)</span><input class="fa" id="cd-bank" value="${esc(cd.bank)}" maxlength="40" aria-label="بانک">
      <span class="lbl">قیمت هر بسته (تومان؛ خالی = بدون کارت‌به‌کارت)</span>
      ${S.packs.map(p => `<div class="cdp"><span>${N(p.tokens)} توکن</span><input class="ltr" id="cd-p-${esc(p.id)}" inputmode="numeric" value="${esc((cd.prices || {})[p.id] || "")}" placeholder="تومان" autocomplete="off" aria-label="قیمت بسته ${esc(p.tokens)} توکن"></div>`).join("")}
      <span class="lbl">قیمت اشتراک‌ها (تومان؛ خالی = بدون کارت‌به‌کارت)</span>
      ${(S.cfg.plans || []).filter(p => p.id !== "free").map(p => `<div class="cdp"><span>${esc(p.title)}</span><input class="ltr" id="cd-p-plan_${esc(p.id)}" inputmode="numeric" value="${esc((cd.prices || {})["plan_" + p.id] || "")}" placeholder="تومان" autocomplete="off" aria-label="قیمت اشتراک ${esc(p.title)}"></div>`).join("")}
      <span class="lbl">متن راهنما زیر مشخصات کارت (قالب HTML)</span><textarea class="fa" id="cd-tx" data-fmt maxlength="1200" style="min-height:90px" aria-label="متن راهنما">${esc(cd.text)}</textarea>${fmtTools("cd-tx")}
      <button class="b o" data-a="cdsave">ذخیره</button>
      <h3 class="mt" style="font-size:14px">آخرین سفارش‌ها</h3>
      ${(cd.orders || []).length ? cd.orders.map(o => `<div class="cdo"><div class="cdi"><b>${N("#" + o.id)}</b> ${esc(o.name || o.uid)}<br><span class="muted">${o.plan ? "اشتراک " + esc(o.plan) : N(o.tokens) + " توکن"} · ${N(Number(o.toman).toLocaleString("en"))} تومان · ${CD_ST[o.status] || esc(o.status)}</span></div>${o.status === "wait" || o.status === "sent" ? `<div class="cdb"><button class="b sm" data-a="cdok" data-id="${o.id}" aria-label="تأیید سفارش ${o.id}">${IC.check}</button><button class="b o sm" data-a="cdno" data-id="${o.id}" aria-label="رد سفارش ${o.id}">${IC.x}</button></div>` : ""}</div>`).join("") : `<p class="muted">هنوز سفارشی ثبت نشده.</p>`}
      <button class="b o sm mt" data-a="cdrefresh">تازه‌سازی</button></div></details>
    ` + `<details class="adv acc" data-ak="fj"${_op("fj")}><summary>عضویت اجباری ربات‌ساز</summary><div class="accb"><p class="muted">کاربر تا عضو این کانال‌ها نشود، نه ربات مادر و نه مینی‌اپ کار می‌کند. ربات مادر باید در کانال ادمین باشد. ادمین‌ها قفل نمی‌شوند.</p><div class="fgap"></div>
      <label class="chk"><input type="checkbox" id="fj-on"${fj.on ? " checked" : ""}> فعال باشد</label>
      <span class="lbl">آیدی کانال‌ها (تا ۳ تا، با فاصله)</span><input class="ltr" id="fj-ch" value="${esc(fj.channels)}" placeholder="@channel1 @channel2" autocomplete="off" aria-label="آیدی کانال‌ها">
      <p class="muted">کانال خصوصی: <b dir="ltr">-1001234567890=https://t.me/+invite</b></p>
      <span class="lbl">متن پیام عضویت (قالب HTML)</span><textarea class="fa" id="fj-tx" data-fmt maxlength="1500" style="min-height:90px" aria-label="متن پیام عضویت">${esc(fj.text)}</textarea>${fmtTools("fj-tx")}
      <button class="b o" data-a="afj">ذخیره</button></div></details>
    ` + `<details class="adv acc" data-ak="promo"${_op("promo")}><summary>تبلیغ روی ورودی‌های جدید</summary><div class="accb"><p class="muted">فقط برای ورودی‌های تازه‌ی ربات‌هایی که مخاطبشان از حد زیر بیشتر شده. مخاطبان قبلی، صاحب ربات و پشتیبان‌ها هرگز هدف نمی‌شوند. هر نفر یک بار می‌بیند، و کسی که از قبل عضو کانال است چیزی نمی‌بیند. ربات مادر باید در کانال ادمین باشد.</p><div class="fgap"></div>
      <label class="chk"><input type="checkbox" id="pr-on"${pr.on ? " checked" : ""}> فعال باشد</label>
      <label class="chk"><input type="checkbox" id="pr-test"${pr.test ? " checked" : ""}> حالت تست (فقط برای ادمین‌های ربات‌ساز)</label>
      <p class="muted">در حالت تست، هر بار با <b dir="ltr">/start</b> توی هر رباتی (حتی ربات خودت، حتی اگر عضو کانال باشی) تبلیغ را می‌بینی. کار که تمام شد خاموشش کن.</p>
      <span class="lbl">حداقل مخاطب هر ربات (بیشتر از این عدد)</span><input class="ltr" id="pr-min" inputmode="numeric" value="${esc(pr.min_users)}" autocomplete="off" aria-label="حداقل مخاطب">
      <span class="lbl">درصد ورودی‌های جدیدی که هدف می‌شوند</span><input class="ltr" id="pr-pct" inputmode="numeric" value="${esc(pr.pct)}" autocomplete="off" aria-label="درصد هدف">
      <span class="lbl">از هدف‌ها، چند درصد قفل عضویت بگیرند (بقیه فقط پیام می‌گیرند؛ ۰ = فقط پیام)</span><input class="ltr" id="pr-lock" inputmode="numeric" value="${esc(pr.lock_pct)}" autocomplete="off" aria-label="درصد قفل">
      <span class="lbl">کانال‌ها (خالی = همان کانال‌های عضویت اجباری)</span><input class="ltr" id="pr-ch" value="${esc(pr.channels)}" placeholder="@channel" autocomplete="off" aria-label="کانال‌های تبلیغ">
      <span class="lbl">متن پیام تبلیغی (قالب HTML)</span><textarea class="fa" id="pr-tx" data-fmt maxlength="1500" style="min-height:70px" aria-label="متن پیام تبلیغی">${esc(pr.text)}</textarea>${fmtTools("pr-tx")}
      <span class="lbl">متن قفل عضویت (قالب HTML)</span><textarea class="fa" id="pr-ltx" data-fmt maxlength="1500" style="min-height:70px" aria-label="متن قفل عضویت">${esc(pr.lock_text)}</textarea>${fmtTools("pr-ltx")}
      <div class="promo-f"><div><span>هدف‌گیری شدند</span>${N(pr.stats?.tgt || 0)}</div><div><span>قفل نشان داده شد</span>${N(pr.stats?.lock || 0)}</div><div><span>پیام تبلیغ</span>${N(pr.stats?.msg || 0)}</div><div><span>عضو شدند</span>${N(pr.stats?.joined || 0)}</div></div>
      ${(pr.stats?.err || 0) > 0 ? `<p class="muted" style="color:var(--bad)">${N(pr.stats.err)} بار بررسی عضویت خطا داد (ممکن است قدیمی باشد؛ بعد از اصلاح «صفر کردن آمار» را بزن).${pr.last_err ? `<br>آخرین خطای تلگرام: <span class="ltr">${esc(pr.last_err)}</span>` : ""}</p>` : ""}
      <h3 class="mt" style="font-size:13.5px">آخرین تصمیم‌ها <small class="muted">(چرا کسی هدف شد یا نشد)</small></h3>
      ${(pr.trace || []).length ? `<div class="ptr">${pr.trace.map(x => `<div><span class="muted">${ago(new Date(x.t * 1000).toISOString())}</span> ${esc(x.s)}</div>`).join("")}</div>` : '<p class="muted">هنوز ورودی جدیدی ثبت نشده.</p>'}
      <button class="b o sm" data-a="aprreset">صفر کردن آمار و تصمیم‌ها</button>
      ${(pr.stats?.terr || 0) > 0 ? `<p class="muted">${N(pr.stats.terr)} بار هم تلگرام موقتاً جواب نداد (محدودیت سرعت)؛ آن کاربرها دفعه‌ی بعد دوباره بررسی می‌شوند.</p>` : ""}
      <button class="b o" data-a="apr">ذخیره</button></div></details>
    ` + `<details class="adv acc" data-ak="tok"${_op("tok")}><summary>توکن کاربر</summary><div class="accb"><p class="muted">مقدار منفی یعنی کسر.</p><div class="fgap"></div>
      <div class="cmd"><input id="ag-uid" placeholder="آیدی عددی" inputmode="numeric" aria-label="آیدی عددی کاربر"><input id="ag-amt" placeholder="مقدار" inputmode="numeric" aria-label="مقدار توکن"></div>
      <button class="b o" data-a="agrant">اعمال</button></div></details>
    <details class="adv acc" data-ak="cpn"${_op("cpn")}><summary>کد هدیه</summary><div class="accb"><div class="fgap"></div>
      <div class="cmd"><input id="ac-code" placeholder="کد (خالی = خودکار)" aria-label="کد"><input id="ac-tok" placeholder="توکن" inputmode="numeric" aria-label="توکن"></div>
      <div class="cmd"><input id="ac-max" placeholder="ظرفیت (نفر)" inputmode="numeric" aria-label="ظرفیت"><input id="ac-days" placeholder="انقضا (روز)" inputmode="numeric" aria-label="انقضا"></div>
      <button class="b o" data-a="acoupon">ساخت کد</button></div></details>
`;
}
let UQ = "";
const ago = t => { if(!t) return "—"; const m = Math.max(0, (Date.now() - new Date(t)) / 60000); return m < 1 ? "همین الان" : m < 60 ? Math.floor(m) + " دقیقه پیش" : m < 1440 ? Math.floor(m / 60) + " ساعت پیش" : Math.floor(m / 1440) + " روز پیش"; };

/* ── ارسال اطلاعیه: متن (HTML اختیاری) + رسانه ── */
const CPS = {};
const cpNew = () => ({text: "", media: "", fmt: "html"});
const cpSt = p => CPS[p] || (CPS[p] = cpNew());
const FMT_TAGS = [["<b>B</b>", "پررنگ", "<b>", "</b>"], ["<i>I</i>", "کج", "<i>", "</i>"], ["<u>U</u>", "زیرخط", "<u>", "</u>"], ["<s>S</s>", "خط‌خورده", "<s>", "</s>"],
  ["&lt;/&gt;", "کد", "<code>", "</code>"], ["مخفی", "اسپویلر", "<tg-spoiler>", "</tg-spoiler>"], ["نقل", "نقل‌قول", "<blockquote>", "</blockquote>"], ["لینک", "لینک", '<a href="https://">', "</a>"]];
const cpTools = (p, on) => `<div class="fmtbar" id="${p}-tools"${on ? "" : ' style="display:none"'}>${FMT_TAGS.map((t, i) => `<button type="button" data-a="cpf" data-p="${p}" data-i="${i}" aria-label="${t[1]}">${t[0]}</button>`).join("")}</div>`;
const cpFmtSel = (p, fmt) => `<select id="${p}-fmt" data-cpfmt="${p}" aria-label="قالب متن" style="width:auto;min-width:150px"><option value="html"${fmt === "html" ? " selected" : ""}>قالب HTML (بولد، لینک و…)</option><option value="text"${fmt !== "html" ? " selected" : ""}>متن ساده</option></select>`;
const cpMediaHTML = p => { const cur = cpSt(p).media;
  const items = S.media.map(m => `<button class="${m.id === cur ? "on" : ""}" data-a="cpick" data-p="${p}" data-v="${m.id}"><div class="mi">${miInner(m)}</div><small>${esc(m.name)}</small></button>`).join("");
  return `<div class="mpick"><button class="${!cur ? "on" : ""}" data-a="cpick" data-p="${p}" data-v=""><div class="mi">بدون</div><small>بدون رسانه</small></button>${items}<button class="up" data-a="cpup" data-p="${p}">آپلود</button></div>`; };
const cpRefresh = p => { const el = $("#" + p + "-media"); if(el) el.innerHTML = cpMediaHTML(p); };
const cpBox = (p, ph) => { const st = cpSt(p);
  return `<textarea class="fa" id="${p}-text" data-cp="${p}" maxlength="3500" style="min-height:90px" placeholder="${ph}" aria-label="${ph}">${esc(st.text)}</textarea>
    <div style="display:flex;margin-top:6px">${cpFmtSel(p, st.fmt)}</div>${cpTools(p, st.fmt === "html")}
    <span class="lbl">رسانه (اختیاری، متن به‌عنوان کپشن می‌رود)</span><div id="${p}-media">${cpMediaHTML(p)}</div>`; };
const cpPayload = p => { const st = cpSt(p), t = $("#" + p + "-text"), f = $("#" + p + "-fmt"); if(t) st.text = t.value; if(f) st.fmt = f.value;
  return {text: st.text.trim(), media: st.media, fmt: st.fmt === "html" ? "html" : "text"}; };
const cpReset = p => { CPS[p] = cpNew(); const t = $("#" + p + "-text"); if(t) t.value = ""; cpRefresh(p); };
document.addEventListener("input", e => { const p = e.target.dataset?.cp; if(p) cpSt(p).text = e.target.value; });
document.addEventListener("change", e => { const p = e.target.dataset?.cpfmt; if(!p) return; cpSt(p).fmt = e.target.value;
  const t = $("#" + p + "-tools"); if(t) t.style.display = e.target.value === "html" ? "" : "none"; });
const CD_ST = {wait: "منتظر رسید", sent: "رسید آمد", ok: "تأیید شد", no: "رد شد"};
const cdReload = async () => { S.cd = await api("/api/admin/card"); admSetPaint(); };
const cdDecide = (el, ok) => confirmQ(ok ? "این پرداخت تأیید و توکن شارژ شود؟" : "این سفارش رد شود؟", yes => yes && busy(el, async () => {
  await api("/api/admin/card-orders/" + el.dataset.id, "POST", {ok}); toast(ok ? "تأیید شد" : "رد شد"); await cdReload(); }));
Object.assign(A, {
  cardbuy: el => busy(el, async () => { const o = await api("/api/card/order", "POST", el.dataset.plan ? {plan: el.dataset.plan} : {pack: el.dataset.id}); S.sheet = {kind: "card", o}; D = null; renderSheet(); }),
  cardrcpt: () => { const l = S.sheet?.o?.link; if(l) openLink(l); else toast("لینک ربات آماده نیست؛ رسید را مستقیم در ربات بفرست"); },
  cardcopy: el => navigator.clipboard?.writeText(el.dataset.v).then(() => toast("کپی شد"), () => toast(el.dataset.v)),
  cdsave: el => busy(el, async () => { const v = id => $(id).value.trim(), prices = {}; S.packs.forEach(p => { prices[p.id] = v("#cd-p-" + p.id); }); (S.cfg.plans || []).filter(p => p.id !== "free").forEach(p => { prices["plan_" + p.id] = v("#cd-p-plan_" + p.id); });
    await api("/api/admin/card", "POST", {on: $("#cd-on").checked, number: v("#cd-num"), holder: v("#cd-holder"), bank: v("#cd-bank"), text: v("#cd-tx"), prices});
    try{ S.card = (await api("/api/me")).card; }catch(_){}
    toast("ذخیره شد"); await cdReload(); }),
  cdok: el => cdDecide(el, true),
  cdno: el => cdDecide(el, false),
  cdrefresh: el => busy(el, cdReload),
  fmtb: el => { const t = el.dataset.t === "@last" ? FMT_LAST : $("#" + el.dataset.t);
    if(!t || !t.isConnected) return toast("اول روی کادر متن بزن، بعد قالب را انتخاب کن"); fmtInsert(t, +el.dataset.i); },
  fjopen: el => openLink(el.dataset.u),
  fjchk: el => busy(el, async () => { const d = await api("/api/fj");
    if(d.required){ toast("هنوز عضو نشدی"); return showFj(d); }
    $("#dock").hidden = false; await load(); }),
  afj: el => busy(el, async () => { const v = id => $(id).value.trim(), on = $("#fj-on").checked;
    const d = await api("/api/admin/force-join", "POST", {on, channels: v("#fj-ch"), text: v("#fj-tx")});
    S.fj = {on: on && !!v("#fj-ch"), channels: v("#fj-ch"), text: v("#fj-tx")}; toast(d.warn?.length ? d.warn[0] : "ذخیره شد"); }),
  apr: el => busy(el, async () => { const v = id => $(id).value.trim(), on = $("#pr-on").checked;
    const body = {on, test: $("#pr-test").checked, min_users: v("#pr-min"), pct: v("#pr-pct"), lock_pct: v("#pr-lock"), channels: v("#pr-ch"), text: v("#pr-tx"), lock_text: v("#pr-ltx")};
    const d = await api("/api/admin/promo", "POST", body);
    S.pr = Object.assign({}, S.pr || {}, {on: on && !!(body.channels || S.fj?.channels), min_users: body.min_users, pct: body.pct, lock_pct: body.lock_pct, channels: body.channels, text: body.text, lock_text: body.lock_text, test: body.test});
    admSetPaint(); toast(d.warn?.length ? d.warn[0] : "ذخیره شد");
    api("/api/admin/promo").then(x => { S.pr = x; admSetPaint(); }).catch(() => {}); }),
  aprreset: el => busy(el, async () => { await api("/api/admin/promo/reset", "POST"); S.pr = await api("/api/admin/promo"); admSetPaint(); toast("آمار صفر شد"); }),
  cpf: el => { const t = $("#" + el.dataset.p + "-text"); if(!t) return; const tg_ = FMT_TAGS[+el.dataset.i], o = tg_[2], c = tg_[3];
    const a = t.selectionStart ?? t.value.length, b = t.selectionEnd ?? a, sel = t.value.slice(a, b) || "متن";
    t.value = t.value.slice(0, a) + o + sel + c + t.value.slice(b); t.focus(); t.setSelectionRange(a + o.length, a + o.length + sel.length); t.dispatchEvent(new Event("input", {bubbles: true})); },
  cpick: el => { cpSt(el.dataset.p).media = el.dataset.v; cpRefresh(el.dataset.p); },
  cpup: el => { S.pickKey = "__cp:" + el.dataset.p; $("#fileIn").click(); },
  rb: el => { if(el.classList.contains("spin")) return; const u = el.dataset.s === "u";
    busy(el, async () => { const d = await api(u ? "/api/admin/users/refresh-blocks" : `/api/admin/bots/${AU.id}/refresh-blocks`, "POST");
      toast(d.started ? "بررسی بلاک‌ها شروع شد؛ نتیجه خودکار به‌روز می‌شود" : "یک بررسی دیگر هنوز در حال انجام است");
      clearTimeout(window.__ut); clearTimeout(window.__at); const f = u ? openUsers.tick : openAudience.tick; if(f) setTimeout(f, 1200); }); },
});
const headRb = (t, s) => `<div class="grab"></div><div class="sh"><h2>${t}</h2><div style="display:flex;gap:6px"><button class="iconb sm" id="rb-btn" data-a="rb" data-s="${s}" aria-label="بررسی دوباره‌ی بلاک‌ها" title="بررسی دوباره‌ی بلاک‌ها">${IC.refresh}</button><button class="iconb sm" data-x="close" aria-label="بستن">${IC.x}</button></div></div>`;
const scanTxt = d => d.scan ? ` · در حال بررسی ${N(d.scan.done)} از ${N(d.scan.total)}` : "";

/* ── کاربران ربات‌ساز ── */
const US = {sel: new Set()};
const usTg = () => US.sel.size ? `${N(US.sel.size)} نفر انتخاب‌شده` : "هیچ‌کس انتخاب نشده";
function userRow(r){
  const nm = r.name || (r.un ? "@" + r.un : "—"), id = String(r.id);
  const bots = r.bots.map(b => `<span class="ub${b.on ? " on" : ""}" data-ab="${esc(b.id)}">${b.on ? "@" + esc(b.un) : esc(b.name)}</span>`).join("");
  return `<div class="urow pick${US.sel.has(id) ? " sel" : ""}" data-us="${esc(id)}"><span class="ck">${IC.check}</span><span class="dot${r.online ? " on" : ""}"></span><div class="ui"><div class="u1"><b>${esc(nm)}</b>${r.un && r.name ? `<span class="muted ltr">@${esc(r.un)}</span>` : ""}${r.blocked ? '<span class="ub">بلاک‌شده</span>' : ""}</div>
    <div class="u2"><span class="cpy" data-pf="copyid" data-id="${esc(r.id)}">${esc(r.id)}</span><span class="muted">${r.blocked ? "غیرفعال" : r.online ? "آنلاین" : ago(r.seen)}</span><span class="muted">${N(r.tokens)} توکن</span></div>${bots ? `<div class="u3">${bots}</div>` : ""}</div><span class="ucnt n">${r.bots.length}</span></div>`;
}
const uSum = d => `<span class="dot on"></span><b>${N(d.online)}</b> آنلاین<span class="muted">از ${N(d.total)} کاربر${d.blocked ? " · " + N(d.blocked) + " بلاک" : ""}${scanTxt(d)}</span>`;
const usFilter = d => { const q = UQ.trim().toLowerCase().replace(/^@/, "");
  return d.items.filter(r => !q || String(r.id).includes(q) || (r.un || "").toLowerCase().includes(q) || (r.name || "").toLowerCase().includes(q) || r.bots.some(b => (b.un || "").toLowerCase().includes(q))); };
const uList = d => usFilter(d).map(userRow).join("") || '<p class="muted">موردی پیدا نشد</p>';
const usPaint = () => { const t = $("#utg"); if(t) t.innerHTML = usTg(); const l = $("#ulist"); if(l && openUsers.d) l.innerHTML = uList(openUsers.d); };
async function openUsers(){
  clearTimeout(window.__ut); clearTimeout(window.__at); clearInterval(window.__ut); clearInterval(window.__at);
  S.sheet = {kind: "info"}; UQ = ""; US.sel = new Set(); CPS.us = cpNew(); openUsers.d = null;
  showSheet(head("کاربران ربات‌ساز") + `<p class="muted">در حال بارگذاری…</p>`);
  const tick = async () => {
    if(S.sheet?.kind !== "info" || !$("#sheet").classList.contains("show")) return;
    let again = 10000;
    try{
      const d = await api("/api/admin/users"); openUsers.d = d; again = d.scan ? 2500 : 10000;
      if($("#ulist")){ $("#usum").innerHTML = uSum(d); $("#ulist").innerHTML = uList(d); $("#rb-btn")?.classList.toggle("spin", !!d.scan); }
      else showSheet(headRb("کاربران ربات‌ساز", "u") + `<div class="usum" id="usum">${uSum(d)}</div><input id="uq" class="fa" placeholder="جستجو: آیدی، یوزرنیم، ربات" autocomplete="off" aria-label="جستجو" style="margin-bottom:6px"><div id="ulist" class="scrl">${uList(d)}</div>
        <div class="atg"><span class="muted">برای ارسال، روی کاربرها بزن. گیرنده:</span><b id="utg">${usTg()}</b></div>
        <div class="cmd"><button class="b o sm" data-a="usall">انتخاب همه‌ی لیست</button><button class="b o sm" data-a="usclear">پاک کردن انتخاب</button></div>
        <div class="fgap"></div>${cpBox("us", "متن اطلاعیه برای کاربرهای انتخاب‌شده")}<div class="fgap"></div>
        <button class="b" data-a="ussend">${IC.mega}ارسال</button><div class="fgap"></div>`);
      $("#rb-btn")?.classList.toggle("spin", !!d.scan);
    }catch(e){ closeSheet(); return toast(e.message); }
    window.__ut = setTimeout(tick, again);
  };
  openUsers.tick = tick; await tick();
}

/* ── مخاطبان یک ربات + ارسال اطلاعیه از طریق همان ربات ── */
const AU = {id: "", mode: "ex", sel: new Set(), d: null};
const auName = r => r.name || (r.un ? "@" + r.un : "کاربر " + r.id);
function auRow(r){
  const id = String(r.id);
  return `<div class="urow pick${AU.sel.has(id) ? " sel" : ""}" data-au="${esc(id)}"><span class="ck">${IC.check}</span><span class="dot${r.online ? " on" : ""}"></span><div class="ui"><div class="u1"><b>${esc(auName(r))}</b>${r.un && r.name ? `<span class="muted ltr">@${esc(r.un)}</span>` : ""}${r.owner ? '<span class="ub on">سازنده</span>' : ""}${r.blocked ? '<span class="ub">بلاک‌شده</span>' : ""}</div>
    <div class="u2"><span class="cpy" data-pf="copyid" data-id="${esc(r.id)}">${esc(r.id)}</span><span class="muted">${r.blocked ? "غیرفعال" : r.online ? "آنلاین" : ago(r.seen)}</span><span class="ut">عضو: ${ago(r.joined)}</span></div></div></div>`;
}
const auSum = d => `<span class="dot on"></span><b>${N(d.online)}</b> آنلاین<span class="muted">از ${N(d.total)} مخاطب${d.blocked ? " · " + N(d.blocked) + " بلاک" : ""}${scanTxt(d)}</span>`;
const auTg = () => AU.sel.size ? `${N(AU.sel.size)} نفر انتخاب‌شده` : AU.mode === "all" ? "همه (با سازنده)" : "همه به‌جز سازنده";
const auFilter = d => { const q = ($("#aq")?.value || "").trim().toLowerCase().replace(/^@/, "");
  return d.items.filter(r => !q || String(r.id).includes(q) || (r.un || "").toLowerCase().includes(q) || (r.name || "").toLowerCase().includes(q)); };
const auList = d => auFilter(d).map(auRow).join("") || '<p class="muted">مخاطبی پیدا نشد</p>';
const auPaint = () => { const t = $("#atg"); if(t) t.innerHTML = auTg(); const l = $("#alist"); if(l && AU.d) l.innerHTML = auList(AU.d); };
async function openAudience(botId){
  clearTimeout(window.__ut); clearTimeout(window.__at); clearInterval(window.__ut); clearInterval(window.__at);
  S.sheet = {kind: "aud"}; AU.id = botId; AU.mode = "ex"; AU.sel = new Set(); AU.d = null; CPS.au = cpNew();
  showSheet(head("مخاطبان ربات") + `<p class="muted">در حال بارگذاری…</p>`);
  const tick = async () => {
    if(S.sheet?.kind !== "aud" || !$("#sheet").classList.contains("show")) return;
    let again = 10000;
    try{
      const d = await api(`/api/admin/bots/${AU.id}/audience`); AU.d = d; again = d.scan ? 2500 : 10000;
      if($("#alist")){ $("#asum").innerHTML = auSum(d); auPaint(); $("#rb-btn")?.classList.toggle("spin", !!d.scan); }
      else showSheet(headRb(d.bot.un ? "@" + esc(d.bot.un) : esc(d.bot.name), "a") + `<div class="usum" id="asum">${auSum(d)}</div>
        <input id="aq" class="fa" placeholder="جستجو: آیدی، یوزرنیم، اسم" autocomplete="off" aria-label="جستجو" style="margin-bottom:6px">
        <div id="alist" class="scrl">${auList(d)}</div>
        ${d.bot.on ? `<div class="atg"><span class="muted">برای ارسال، روی مخاطب‌ها بزن. گیرنده:</span><b id="atg">${auTg()}</b></div>
        <div class="cmd"><button class="b o sm" data-a="autg" data-t="ex">همه به‌جز سازنده</button><button class="b o sm" data-a="autg" data-t="all">همه با سازنده</button></div>
        <div class="cmd"><button class="b o sm" data-a="auall">انتخاب همه‌ی لیست</button><button class="b o sm" data-a="auclear">پاک کردن انتخاب</button></div>
        <div class="fgap"></div>${cpBox("au", "متن اطلاعیه از طریق این ربات")}<div class="fgap"></div>
        <button class="b" data-a="ausend">${IC.mega}ارسال</button>` : '<p class="muted">این ربات فعال نیست و ارسال ممکن نیست.</p>'}
        <div class="fgap"></div><button class="b o" data-a="ausers">بازگشت به کاربران</button>`);
      $("#rb-btn")?.classList.toggle("spin", !!d.scan);
    }catch(e){ toast(e.message); return; }
    window.__at = setTimeout(tick, again);
  };
  openAudience.tick = tick; await tick();
}
document.addEventListener("click", e => {
  const c = e.target.closest("[data-ab]"); if(c){ e.stopPropagation(); return openAudience(c.dataset.ab); }
  if(e.target.closest("[data-pf]")) return;
  const r = e.target.closest("[data-au]"); if(r && AU.d){ const id = r.dataset.au; AU.sel.has(id) ? AU.sel.delete(id) : AU.sel.add(id); return auPaint(); }
  const u = e.target.closest("[data-us]"); if(u && openUsers.d){ const id = u.dataset.us; US.sel.has(id) ? US.sel.delete(id) : US.sel.add(id); usPaint(); }
}, true);
Object.assign(A, {
  autg: el => { AU.mode = el.dataset.t; AU.sel.clear(); auPaint(); },
  auall: () => { if(!AU.d) return; auFilter(AU.d).filter(r => !r.blocked).forEach(r => AU.sel.add(String(r.id))); auPaint(); },
  auclear: () => { AU.sel.clear(); auPaint(); },
  usall: () => { if(!openUsers.d) return; usFilter(openUsers.d).filter(r => !r.blocked).forEach(r => US.sel.add(String(r.id))); usPaint(); },
  usclear: () => { US.sel.clear(); usPaint(); },
  ausend: el => { const {text, media, fmt} = cpPayload("au"); if(!media && text.length < 2) return toast("متن یا رسانه‌ی اطلاعیه را بنویس");
    const n = AU.sel.size, body = n ? {scope: "many", uids: [...AU.sel], text, media, fmt} : {scope: AU.mode === "all" ? "all" : "except_owner", text, media, fmt};
    confirmQ(`این پیام برای «${$("#atg")?.textContent || ""}» از طریق همین ربات فرستاده شود؟`, ok => ok && busy(el, async () => { const d = await api(`/api/admin/bots/${AU.id}/send`, "POST", body);
      toast(n === 1 ? "ارسال شد" : `ارسال برای ${d.queued} نفر شروع شد`); cpReset("au"); })); },
  ussend: el => { if(!US.sel.size) return toast("اول کاربرها را انتخاب کن (روی هر کاربر بزن)");
    const {text, media, fmt} = cpPayload("us"); if(!media && text.length < 3) return toast("متن یا رسانه‌ی اطلاعیه را بنویس");
    confirmQ(`این پیام برای ${US.sel.size} سازنده‌ی انتخاب‌شده فرستاده شود؟`, ok => ok && busy(el, async () => { const d = await api("/api/admin/announce", "POST", {ids: [...US.sel], text, media, fmt});
      toast(`ارسال برای ${d.queued} نفر شروع شد`); cpReset("us"); })); },
});
document.addEventListener("input", e => { if(e.target.id === "aq" && AU.d) auPaint(); });
document.addEventListener("input", e => { if(e.target.id === "uq" && openUsers.d){ UQ = e.target.value; usPaint(); } });

/* ═════════════════ هاب مدیریت: نمای کلی · ربات‌ها · کاربران · اطلاعیه · تنظیمات ═════════════════ */
const ASUBS = [["home", "نمای کلی"], ["bots", "ربات‌ها"], ["users", "کاربران"], ["ann", "اطلاعیه"], ["set", "تنظیمات"]];
const ADM = {d: {}, q: "", sort: "subs", st: "all", lim: 40, bsel: new Set(), meta: {}, uq: "", uf: "all", usel: new Set(), mode: "b", bto: "aud", own: false, hist: [], cnt: null};
const fnum = x => Number(x || 0).toLocaleString("en");
const admDot = n => `<span class="dot${n ? " on" : ""}"></span>`;
const ADM_SORTS = [["subs", "بیشترین مخاطب"], ["act24", "فعال‌ترین ۲۴ساعت"], ["online", "آنلاین الان"], ["new24", "رشد امروز"], ["recent", "جدیدترین"]];
const ADM_SORT_LBL = {subs: "مخاطب", act24: "فعال ۲۴س", online: "آنلاین", new24: "جدید امروز", recent: "مخاطب"};

function adminCard(){
  if(!ASUBS.some(s => s[0] === S.asub)) S.asub = "home";
  return `<div class="asubs" role="tablist">${ASUBS.map(([k, t]) => `<button class="${k === S.asub ? "on" : ""}" role="tab" aria-selected="${k === S.asub}" data-a="admsub" data-k="${k}">${t}${k === "ann" && ADM.hist.some(h => h.state === "run") ? '<span class="qdot"></span>' : ""}</button>`).join("")}</div>
    <div id="adm-body">${admBody()}</div>`;
}
const admBody = () => ({home: admHome, bots: admBots, users: admUsers, ann: admAnn, set: adminSettings})[S.asub]();
const admLoading = () => `<p class="muted adm-ld">در حال بارگذاری…</p>`;

/* ── بارگذاری و تازه‌سازی خودکار ── */
const admUrl = k => ({home: "/api/admin/overview", users: "/api/admin/users" + (ADM.uq ? "?q=" + encodeURIComponent(ADM.uq) : ""), ann: "/api/admin/announces",
  bots: `/api/admin/bots?sort=${ADM.sort}&st=${ADM.st}&limit=${ADM.lim}&q=${encodeURIComponent(ADM.q)}`})[k];
async function admLoad(k, fresh){
  try{
    const jobs = [api(admUrl(k) + (fresh ? (admUrl(k).includes("?") ? "&" : "?") + "fresh=1" : ""))];
    if(k === "ann") jobs.push(api("/api/admin/audience"));
    const [d, c] = await Promise.all(jobs);
    if(k === "ann"){ ADM.hist = d.items; ADM.cnt = c; }
    if(k === "bots") d.items.forEach(r => { ADM.meta[r.id] = r; });
    ADM.d[k] = d;
    if(S.asub === k) admPaint();
  }catch(e){ if(S.asub === k && !ADM.d[k]){ const b = $("#adm-body"); if(b) b.innerHTML = `<p class="muted">${esc(e.message || "خطا در دریافت اطلاعات")}</p>`; } }
}
function admStop(){ clearTimeout(window.__adm); }
function admStart(){
  admStop(); const k = S.asub;
  if(k === "set") return;
  admLoad(k);
  const gap = {home: 15000, bots: 20000, users: 10000, ann: ADM.hist.some(h => h.state === "run") ? 4000 : 15000}[k];
  window.__adm = setTimeout(function tick(){
    if(S.view !== "account" || S.atab !== "admin" || S.asub !== k || !$("#adm-body")) return;
    const run = !document.hidden && !S.sheet && !(k === "bots" && document.activeElement?.id === "abq");
    (run ? admLoad(k) : Promise.resolve()).finally(() => { window.__adm = setTimeout(tick, k === "ann" && ADM.hist.some(h => h.state === "run") ? 4000 : gap); });
  }, gap);
}
function admPaint(){
  if(S.view !== "account" || S.atab !== "admin") return;
  const k = S.asub, b = $("#adm-body"); if(!b) return;
  const part = id => $(id);
  if(k === "home") b.innerHTML = admHome();
  else if(k === "bots" && part("#abl")){ $("#abs").innerHTML = admBotsSum(); $("#abl").innerHTML = admBotsList(); admBotsBar(); }
  else if(k === "users" && part("#aul")){ $("#aus").innerHTML = admUsersSum(); $("#aul").innerHTML = admUsersList(); admUsersBar(); }
  else if(k === "ann" && part("#ahist")){ $("#aopts").innerHTML = admAnnOpts(); $("#ahist").innerHTML = admAnnHist(); admAnnPrev(); }
  else b.innerHTML = admBody();
}

/* ── نمای کلی ── */
function admBotRow(r, i, o = {}){
  const nm = r.un ? "@" + r.un : r.name || "ربات", sel = ADM.bsel.has(r.id), key = o.key || ADM.sort;
  const main = key === "recent" ? r.total : key === "subs" ? r.total - r.blocked : r[key];
  const rank = o.rank !== false && key !== "recent" ? `<span class="rk${i < 3 ? " r" + (i + 1) : ""}">${i + 1}</span>` : "";
  const own = r.owner?.name || (r.owner?.un ? "@" + r.owner.un : r.owner?.id || "");
  return `<div class="abr${sel ? " sel" : ""}" data-abo="${esc(r.id)}">
    ${o.pick === false ? "" : `<button class="ck" data-abk="${esc(r.id)}" aria-label="انتخاب ربات">${IC.check}</button>`}${rank}
    <div class="abi"><div class="ab1"><b class="ltr">${esc(nm)}</b>${r.on ? "" : '<span class="ub">غیرفعال</span>'}</div>
      <div class="ab2 muted">${r.un && r.name ? esc(r.name) + " · " : ""}سازنده: ${esc(own)}</div>
      <div class="abm"><span>${admDot(r.online)}<i>آنلاین</i> ${fnum(r.online)}</span><span><i>۲۴س</i> ${fnum(r.act24)}</span><span><i>جدید</i> +${fnum(r.new24)}</span>${r.blocked ? `<span class="bd"><i>بلاک</i> ${fnum(r.blocked)}</span>` : ""}</div></div>
    <div class="abn"><b class="n">${fnum(main)}</b><small>${ADM_SORT_LBL[key]}</small></div></div>`;
}
function admHome(){
  const d = ADM.d.home; if(!d) return admLoading();
  const cells = [["کاربران ربات‌ساز", d.users], ["جدید ۲۴ساعت", d.new24], ["ربات‌ها", d.bots], ["ربات فعال", d.active], ["مخاطب همه‌ی ربات‌ها", d.subs],
    ["فعال ۲۴ساعت", d.subs_act24], ["رشد امروز", d.subs_new24], ["بلاک‌شده", d.subs_blocked], ["پاسخ فرم‌ها", d.forms], ["توکن در گردش", d.circulation]];
  const list = (arr, key) => arr.length ? arr.map((r, i) => admBotRow(r, i, {key, pick: false})).join("") : '<p class="muted">هنوز داده‌ای نیست.</p>';
  return `<div class="live"><div><span class="dot on"></span><b class="n">${fnum(d.online)}</b><span class="muted"> سازنده آنلاین</span></div><div><b class="n">${fnum(d.subs_online)}</b><span class="muted"> مخاطب آنلاین در ربات‌ها</span></div></div>
    <div class="stats s3 mt">${statCells(cells.map(([k, v]) => [k, fnum(v)]))}</div>
    <div class="sec"><h2>برترین ربات‌ها <small>بیشترین مخاطب</small></h2><button class="b t" data-a="admgo" data-k="bots" data-s="subs">همه</button></div>
    <div class="panel abl-p">${list(d.top_subs, "subs")}</div>
    <div class="sec"><h2>فعال‌ترین ربات‌ها <small>۲۴ ساعت اخیر</small></h2><button class="b t" data-a="admgo" data-k="bots" data-s="act24">همه</button></div>
    <div class="panel abl-p">${list(d.top_act, "act24")}</div>
    <div class="two"><button class="b" data-a="admgo" data-k="ann">${IC.mega}اطلاعیه جدید</button><button class="b o" data-a="admgo" data-k="users">${IC.users}کاربران آنلاین</button></div>`;
}

/* ── ربات‌ها ── */
const admBotsSum = () => { const d = ADM.d.bots; if(!d) return ""; const s = d.summary;
  return `<b>${N(fnum(d.matched))}</b> ربات<span class="muted"> از ${N(fnum(s.bots))} · ${N(fnum(s.active))} فعال · ${N(fnum(s.subs))} مخاطب · ${N(fnum(s.online))} آنلاین</span>`; };
const admBotsList = () => { const d = ADM.d.bots; if(!d) return admLoading();
  return (d.items.map((r, i) => admBotRow(r, i)).join("") || '<p class="muted">رباتی پیدا نشد</p>') + (d.more ? '<button class="b o sm mt" data-a="admmore">نمایش بیشتر</button>' : ""); };
function admBotsBar(){
  const bar = $("#absel"); if(!bar) return; const n = ADM.bsel.size;
  bar.classList.toggle("show", n > 0);
  bar.innerHTML = n ? `<span><b class="n">${n}</b> ربات انتخاب‌شده</span><button class="b sm" data-a="admbsend">${IC.mega}ارسال اطلاعیه</button><button class="b o sm" data-a="admclr" data-w="b">پاک</button>` : "";
}
function admBots(){
  setTimeout(admBotsBar, 0);
  return `<div class="abtool"><input id="abq" class="fa" value="${esc(ADM.q)}" placeholder="جستجو: نام ربات، یوزرنیم یا سازنده" autocomplete="off" aria-label="جستجو"></div>
    <div class="chips">${ADM_SORTS.map(([k, t]) => `<button class="${ADM.sort === k ? "on" : ""}" data-a="admsort" data-k="${k}">${t}</button>`).join("")}</div>
    <div class="chips sm">${[["all", "همه"], ["on", "فعال"], ["off", "غیرفعال"]].map(([k, t]) => `<button class="${ADM.st === k ? "on" : ""}" data-a="admst" data-k="${k}">${t}</button>`).join("")}<button class="rf" data-a="admref" aria-label="تازه‌سازی">${IC.refresh}</button></div>
    <div class="usum" id="abs">${admBotsSum()}</div>
    <div class="panel abl-p"><div id="abl">${admBotsList()}</div></div><div class="absel" id="absel"></div>`;
}

/* ── کاربران ── */
const UFILT = [["all", "همه"], ["on", "آنلاین"], ["bots", "دارای ربات"], ["blk", "بلاک‌شده"]];
const admUsersFiltered = () => { const d = ADM.d.users; if(!d) return []; return d.items.filter(r => ADM.uf === "all" || (ADM.uf === "on" && r.online) || (ADM.uf === "bots" && r.bots.length) || (ADM.uf === "blk" && r.blocked)); };
const admUsersSum = () => { const d = ADM.d.users; if(!d) return ""; return `${admDot(1)}<b>${N(fnum(d.online))}</b> آنلاین<span class="muted"> از ${N(fnum(d.total))} کاربر${d.blocked ? " · " + N(fnum(d.blocked)) + " بلاک" : ""}${scanTxt(d)}</span>`; };
function admUserRow(r){
  const id = String(r.id), nm = r.name || (r.un ? "@" + r.un : "—");
  const bots = r.bots.map(b => `<span class="ub${b.on ? " on" : ""}" data-ab="${esc(b.id)}">${b.on ? "@" + esc(b.un) : esc(b.name)}</span>`).join("");
  return `<div class="urow pick${ADM.usel.has(id) ? " sel" : ""}" data-utk="${esc(id)}"><span class="ck">${IC.check}</span>${admDot(r.online)}<div class="ui"><div class="u1"><b>${esc(nm)}</b>${r.un && r.name ? `<span class="muted ltr">@${esc(r.un)}</span>` : ""}${r.blocked ? '<span class="ub">بلاک‌شده</span>' : ""}</div>
    <div class="u2"><span class="cpy" data-pf="copyid" data-id="${esc(r.id)}">${esc(r.id)}</span><span class="muted">${r.blocked ? "غیرفعال" : r.online ? "آنلاین" : ago(r.seen)}</span><span class="muted">${N(fnum(r.tokens))} توکن</span></div>${bots ? `<div class="u3">${bots}</div>` : ""}</div><span class="ucnt n">${r.bots.length}</span></div>`;
}
const admUsersList = () => ADM.d.users ? (admUsersFiltered().map(admUserRow).join("") || '<p class="muted">موردی پیدا نشد</p>') : admLoading();
function admUsersBar(){
  const bar = $("#ausel"); if(!bar) return; const n = ADM.usel.size;
  bar.classList.toggle("show", n > 0);
  bar.innerHTML = n ? `<span><b class="n">${n}</b> کاربر انتخاب‌شده</span><button class="b sm" data-a="admusend">${IC.mega}ارسال پیام</button><button class="b o sm" data-a="admclr" data-w="u">پاک</button>` : "";
}
function admUsers(){
  setTimeout(admUsersBar, 0);
  return `<input id="auq" class="fa" value="${esc(ADM.uq)}" placeholder="جستجو: آیدی، یوزرنیم یا اسم" autocomplete="off" aria-label="جستجو">
    <div class="chips sm">${UFILT.map(([k, t]) => `<button class="${ADM.uf === k ? "on" : ""}" data-a="admuf" data-k="${k}">${t}</button>`).join("")}<button class="rf" data-a="admurb" aria-label="بررسی دوباره‌ی بلاک‌ها" title="بررسی دوباره‌ی بلاک‌ها">${IC.refresh}</button><button class="b t" data-a="admuall">انتخاب لیست</button></div>
    <div class="usum" id="aus">${admUsersSum()}</div>
    <div class="panel abl-p"><div id="aul">${admUsersList()}</div></div><p class="muted">آخرین ۳۰۰ کاربر؛ برای پیدا کردن بقیه جستجو کن.</p><div class="absel" id="ausel"></div>`;
}

/* ── اطلاعیه ── */
const ANN_MODES = [["b", "همه‌ی سازنده‌ها", "کسانی که با ربات‌ساز ربات می‌سازند"], ["a", "مخاطبان همه‌ی ربات‌های فعال", "از طریق خودِ رباتشان، بدون سازنده"],
  ["ba", "سازنده‌ها + مخاطبان", "هر دو گروه"], ["bots", "ربات‌های انتخاب‌شده", "از تب «ربات‌ها» انتخاب کن"], ["users", "کاربران انتخاب‌شده", "از تب «کاربران» انتخاب کن"]];
function admAnnCount(m){
  const c = ADM.cnt || {}, sel = [...ADM.bsel].map(id => ADM.meta[id]).filter(Boolean);
  if(m === "b") return c.builders; if(m === "a") return c.audience; if(m === "ba") return (c.builders || 0) + (c.audience || 0);
  if(m === "users") return ADM.usel.size;
  return ADM.bto === "own" ? new Set(sel.map(r => r.owner?.id)).size : sel.reduce((s, r) => s + (r.on ? Math.max(0, r.total - r.blocked) : 0), 0);
}
function admAnnOpts(){
  return ANN_MODES.map(([k, t, h]) => { const n = admAnnCount(k);
    return `<button class="arad${ADM.mode === k ? " on" : ""}" data-a="admmode" data-k="${k}"><i></i><div><b>${t}</b><small>${k === "bots" && ADM.bsel.size ? ADM.bsel.size + " ربات انتخاب شده" : k === "users" && ADM.usel.size ? ADM.usel.size + " کاربر انتخاب شده" : h}</small></div><span class="n">${n === undefined ? "…" : fnum(n)}</span></button>`; }).join("")
    + (ADM.mode === "bots" ? `<div class="chips sm"><button class="${ADM.bto === "aud" ? "on" : ""}" data-a="admbto" data-k="aud">به مخاطبان آن ربات‌ها</button><button class="${ADM.bto === "own" ? "on" : ""}" data-a="admbto" data-k="own">به سازنده‌ی آن ربات‌ها</button></div>
      ${ADM.bto === "aud" ? `<label class="chk"><input type="checkbox" id="an-own"${ADM.own ? " checked" : ""}> سازنده‌ی هر ربات هم پیام را بگیرد</label>` : ""}<button class="b o sm mt" data-a="admgo" data-k="bots">${IC.bot}انتخاب ربات‌ها</button>` : "")
    + (ADM.mode === "users" ? `<button class="b o sm mt" data-a="admgo" data-k="users">${IC.users}انتخاب کاربرها</button>` : "");
}
const ANN_ST = {run: "در حال ارسال", done: "تمام شد", stale: "ناتمام ماند"};
const admAnnHist = () => ADM.hist.length ? ADM.hist.map(h => { const p = h.total ? Math.min(100, Math.round(h.sent / h.total * 100)) : 100;
  return `<div class="ahi ${h.state}"><div class="ah1"><b>${esc(h.label || h.kind)}</b><span class="muted">${ago(h.t)}</span></div>
    <div class="ah2">${h.media ? IC.photo + " " : ""}${esc(h.text.slice(0, 90)) || "بدون متن"}</div>
    ${h.state === "run" ? `<div class="lqbar"><i style="width:${p}%"></i></div>` : ""}
    <div class="muted">${ANN_ST[h.state]} · رسید به ${N(fnum(h.ok))} از ${N(fnum(h.total))} نفر</div></div>`; }).join("") : '<p class="muted">هنوز اطلاعیه‌ای نفرستادی.</p>';
function admAnnPrev(){ const el = $("#aprev"); if(!el) return; const m = ANN_MODES.find(x => x[0] === ADM.mode), n = admAnnCount(ADM.mode);
  el.innerHTML = `گیرنده: <b>${m[1]}</b> · حدود <b class="n">${n === undefined ? "…" : fnum(n)}</b> ${ADM.mode === "bots" && ADM.bto === "own" ? "سازنده" : "نفر"}`; }
function admAnn(){
  setTimeout(admAnnPrev, 0);
  return `<div class="panel"><h2>گیرنده</h2><div class="fgap"></div><div id="aopts">${admAnnOpts()}</div></div>
    <div class="panel mt"><h2>پیام</h2><div class="fgap"></div>${cpBox("an", "متن اطلاعیه")}<p class="aprev" id="aprev"></p>
      <button class="b" data-a="admsend">${IC.mega}ارسال اطلاعیه</button></div>
    <div class="sec"><h2>آخرین ارسال‌ها</h2></div><div class="panel abl-p" id="ahist">${admAnnHist()}</div>`;
}

/* ── رویدادها ── */
let __abq;
document.addEventListener("input", e => {
  if(e.target.id === "abq"){ ADM.q = e.target.value.trim(); ADM.lim = 40; clearTimeout(__abq); __abq = setTimeout(() => admLoad("bots"), 350); }
  if(e.target.id === "auq"){ ADM.uq = e.target.value.trim().replace(/^@/, ""); clearTimeout(__abq); __abq = setTimeout(() => admLoad("users"), 350); }
});
document.addEventListener("change", e => { if(e.target.id === "an-own") ADM.own = e.target.checked; });
document.addEventListener("click", e => {
  if(S.view !== "account" || S.atab !== "admin") return;
  const k = e.target.closest("[data-abk]"); if(k){ e.stopPropagation(); const id = k.dataset.abk; ADM.bsel.has(id) ? ADM.bsel.delete(id) : ADM.bsel.add(id); k.closest(".abr")?.classList.toggle("sel", ADM.bsel.has(id)); return admBotsBar(); }
  const o = e.target.closest("[data-abo]"); if(o && !e.target.closest("[data-pf]")) return openAudience(o.dataset.abo);
  const u = e.target.closest("[data-utk]"); if(u && !e.target.closest("[data-pf],[data-ab]")){ const id = u.dataset.utk; ADM.usel.has(id) ? ADM.usel.delete(id) : ADM.usel.add(id); u.classList.toggle("sel", ADM.usel.has(id)); admUsersBar(); }
});
const admTo = k => { S.asub = k; renderAccount(); scrollTo({top: 0, behavior: "smooth"}); };
Object.assign(A, {
  admsub: el => { if(S.asub !== el.dataset.k){ S.asub = el.dataset.k; renderAccount(); } },
  admgo: el => { if(el.dataset.s){ ADM.d.bots = null; ADM.sort = el.dataset.s; ADM.q = ""; ADM.st = "all"; ADM.lim = 40; } admTo(el.dataset.k); },
  admsort: el => { ADM.sort = el.dataset.k; ADM.lim = 40; ADM.d.bots = null; renderAccount(); },
  admst: el => { ADM.st = el.dataset.k; ADM.lim = 40; ADM.d.bots = null; renderAccount(); },
  admuf: el => { ADM.uf = el.dataset.k; renderAccount(); },
  admmore: () => { ADM.lim += 40; admLoad("bots"); },
  admref: el => { ADM.d.bots = null; $("#abl").innerHTML = admLoading(); admLoad("bots", true); },
  admclr: el => { if(el.dataset.w === "b"){ ADM.bsel.clear(); document.querySelectorAll(".abr.sel").forEach(x => x.classList.remove("sel")); admBotsBar(); } else { ADM.usel.clear(); document.querySelectorAll(".urow.sel[data-utk]").forEach(x => x.classList.remove("sel")); admUsersBar(); } },
  admuall: () => { admUsersFiltered().filter(r => !r.blocked).forEach(r => ADM.usel.add(String(r.id))); $("#aul").innerHTML = admUsersList(); admUsersBar(); },
  admurb: el => busy(el, async () => { const d = await api("/api/admin/users/refresh-blocks", "POST"); toast(d.started ? "بررسی بلاک‌ها شروع شد؛ نتیجه خودکار به‌روز می‌شود" : "یک بررسی دیگر هنوز در حال انجام است"); setTimeout(() => admLoad("users"), 1500); }),
  admbsend: () => { ADM.mode = "bots"; admTo("ann"); },
  admusend: () => { ADM.mode = "users"; admTo("ann"); },
  admmode: el => { ADM.mode = el.dataset.k; $("#aopts").innerHTML = admAnnOpts(); admAnnPrev(); },
  admbto: el => { ADM.bto = el.dataset.k; $("#aopts").innerHTML = admAnnOpts(); admAnnPrev(); },
  admsend: el => { const {text, media, fmt} = cpPayload("an"), m = ADM.mode; if(!media && text.length < 3) return toast("متن اعلان را بنویس");
    let url = "/api/admin/announce", body = {text, media, fmt};
    if(m === "b" || m === "a" || m === "ba") Object.assign(body, {builders: m !== "a", audience: m !== "b"});
    else if(m === "users"){ if(!ADM.usel.size) return toast("اول کاربرها را انتخاب کن"); body.ids = [...ADM.usel]; }
    else { const sel = [...ADM.bsel]; if(!sel.length) return toast("اول چند ربات انتخاب کن");
      if(ADM.bto === "own"){ const ids = [...new Set(sel.map(id => ADM.meta[id]?.owner?.id).filter(Boolean))]; if(!ids.length) return toast("سازنده‌ای پیدا نشد"); body.ids = ids; }
      else { url = "/api/admin/bots/broadcast"; body = {text, media, fmt, bots: sel, with_owner: !!$("#an-own")?.checked}; } }
    const lbl = ANN_MODES.find(x => x[0] === m)[1], n = admAnnCount(m);
    confirmQ(`این اعلان برای «${lbl}» (حدود ${n ?? "؟"} نفر) فرستاده شود؟`, ok => ok && busy(el, async () => { const d = await api(url, "POST", body);
      toast(`ارسال برای ${d.queued} نفر شروع شد${d.skipped ? ` (${d.skipped} ربات مشغول بود)` : ""}`); cpReset("an"); admLoad("ann"); setTimeout(admStart, 300); })); },
});
const admSetPaint = () => { if(S.view === "account" && S.atab === "admin" && S.asub === "set"){ const b = $("#adm-body"); if(b) b.innerHTML = adminSettings(); } };
document.addEventListener("toggle", e => { const d = e.target; if(d.classList?.contains("acc")){ (S.aopen = S.aopen || {})[d.dataset.ak] = d.open; } }, true);

/* حضور آنلاین */
if(INIT){ const ping = () => { if(!document.hidden) api("/api/ping", "POST").catch(() => {}); }; setInterval(ping, 25000); document.addEventListener("visibilitychange", ping); }

/* ═════════════════ یوزربات (اتصال اکانت شخصی تلگرام) ═════════════════ */
Object.assign(S, { ub: null, ubErr: "", ubSel: null, ubTab: "feat", ubCfg: null });
const UB_SAFE = [["test", "آزمایشی — فقط برای تست (ریسک محدود شدن اکانت)"], ["safe", "محتاط — کندتر و کم‌خطرتر (پیشنهادی)"], ["balanced", "متعادل"], ["fast", "سریع — برای اکانت‌های قدیمی و فعال"]];
const UB_SAFE_T = {test: "فقط برای تست کوتاه: حداقل ۳ دقیقه بین دو پیام به یک چت و تا ۳۰ ارسال در ساعت. بعد از تست حتماً به «محتاط» یا «متعادل» برگرد؛ در حالت آزمایشی احتمال محدود شدن اکانت بالاست.",
  safe: "حداکثر ۱۲ ارسال زمان‌بندی‌شده در ساعت، حداقل ۱ ساعت فاصله بین دو پیام به یک چت، مکث ۳۰ تا ۹۰ ثانیه بین ارسال‌ها.",
  balanced: "حداکثر ۲۴ ارسال در ساعت، حداقل ۳۰ دقیقه فاصله بین دو پیام به یک چت، مکث ۱۵ تا ۴۵ ثانیه بین ارسال‌ها.",
  fast: "حداکثر ۴۰ ارسال در ساعت، حداقل ۱۵ دقیقه فاصله بین دو پیام به یک چت، مکث ۸ تا ۲۵ ثانیه بین ارسال‌ها."};
const UB_REPLY = [["mention", "فقط وقتی منشن یا ریپلای شدم (ایمن‌تر)"], ["kw", "به کلمه‌های کلیدی در همه‌ی پیام‌ها"], ["off", "پاسخ خودکار نداشته باشد (فقط مقصد پیام زمان‌بندی‌شده)"]];
const UB_REPLY_T = {mention: "پاسخ هنگام منشن/ریپلای", kw: "پاسخ به کلمه‌های کلیدی", off: "فقط مقصد ارسال"};
const UB_WHERE = [["pm", "فقط چت خصوصی"], ["group", "فقط گروه‌های انتخاب‌شده"], ["both", "هر دو"]];
const UB_EVERY = [[3, "هر ۳ دقیقه (آزمایشی)"], [5, "هر ۵ دقیقه (آزمایشی)"], [10, "هر ۱۰ دقیقه (آزمایشی)"], [15, "هر ۱۵ دقیقه"], [30, "هر ۳۰ دقیقه"], [60, "هر ۱ ساعت"], [120, "هر ۲ ساعت"], [180, "هر ۳ ساعت"], [360, "هر ۶ ساعت"], [720, "هر ۱۲ ساعت"], [1440, "هر ۱ روز"], [2880, "هر ۲ روز"], [10080, "هر ۱ هفته"]];
const ubEveryT = m => (UB_EVERY.find(x => x[0] === m) || [0, `هر ${m} دقیقه`])[1];
const ubWhen = t => { try{ return t ? new Date(t * 1000).toLocaleString("fa-IR-u-nu-latn", {month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit"}) : ""; }catch(_){ return ""; } };

const ubI = t => `<button type="button" class="ubi" data-a="ubinfo" data-t="${esc(t)}" aria-label="توضیح">!</button>`;
const ubH = (t, tip) => `<h2 class="ubh2">${t}${tip ? ubI(tip) : ""}</h2>`;
const ubL = (t, tip) => `<span class="lbl">${t}${tip ? ubI(tip) : ""}</span>`;
function ubTipHide(){ clearTimeout(ubTip.t); document.getElementById("ubtip")?.remove(); document.querySelectorAll(".ubi.hl").forEach(b => b.classList.remove("hl")); }
function ubTip(el){
  const same = document.getElementById("ubtip") && el.classList.contains("hl"); ubTipHide(); if(same) return;
  el.classList.add("hl");
  const t = document.createElement("div"); t.id = "ubtip"; t.setAttribute("role", "tooltip"); t.textContent = el.dataset.t; document.body.appendChild(t);
  const r = el.getBoundingClientRect(), w = Math.min(300, innerWidth - 24); t.style.width = w + "px";
  t.style.left = Math.max(12, Math.min(innerWidth - w - 12, r.left + r.width / 2 - w / 2)) + "px";
  const h = t.offsetHeight; t.style.top = (r.bottom + 10 + h < innerHeight ? r.bottom + 10 : Math.max(8, r.top - 10 - h)) + "px";
  ubTip.t = setTimeout(ubTipHide, 7000);
}
document.addEventListener("click", e => { if(!e.target.closest?.(".ubi")) ubTipHide(); }, true);
document.addEventListener("contextmenu", e => { const b = e.target.closest?.(".ubi"); if(b){ e.preventDefault(); ubTip(b); } });
const ubFmtCd = sec => { sec = Math.max(0, Math.floor(sec)); const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), x = sec % 60, p = n => String(n).padStart(2, "0"); return (h ? h + ":" : "") + p(m) + ":" + p(x); };
const ubInWin = p => { let h = 12; try{ h = +new Date().toLocaleString("en-US", {timeZone: "Asia/Tehran", hour: "numeric", hour12: false}) % 24; }catch(_){} const a = p.from_h, b = p.to_h; if(a === b || (a === 0 && b === 24)) return true; return a < b ? (h >= a && h < b) : (h >= a || h < b); };
setInterval(() => { document.querySelectorAll("[data-cd]").forEach(el => { const to = +el.dataset.cd, from = +el.dataset.from, n = Date.now() / 1000, left = to - n;
  el.textContent = left > 0 ? ubFmtCd(left) : "الان"; const bar = el.closest(".ubc")?.querySelector(".ubpbar i"); if(bar && to > from) bar.style.width = Math.max(0, Math.min(100, (n - from) / (to - from) * 100)) + "%"; }); }, 1000);
setInterval(() => { if(S.view === "userbot" && S.ubSel && S.ubTab === "posts" && !S.sheet && !document.hidden) api(`/api/userbots/${S.ubSel}`).then(d => { ubPut(d.item); if(S.view === "userbot" && S.ubTab === "posts" && !S.sheet) renderUserbot(); }).catch(() => {}); }, 12000);
const UB_ST = { running: ["روشن", "on"], stopped: ["خاموش", ""], revoked: ["نیاز به اتصال دوباره", "bad"] };
const UB_WHO = [["all", "همه‌ی پیام‌های خصوصی"], ["contacts", "فقط مخاطب‌های من"], ["others", "فقط افراد خارج از مخاطبین"]];
const UB_MODE = [["has", "شامل این کلمه باشد"], ["start", "با این کلمه شروع شود"], ["exact", "دقیقاً همین باشد"]];
const UB_GAPS = [1, 3, 6, 12, 24, 48];
const ubItem = () => S.ub?.items.find(x => x.id === S.ubSel);
const ubPut = it => { const l = S.ub.items; const i = l.findIndex(x => x.id === it.id); if(i < 0) l.push(it); else l[i] = it; };
const ubTime = t => { try{ return new Date(t).toLocaleTimeString("fa-IR-u-nu-latn", {hour: "2-digit", minute: "2-digit"}); }catch(_){ return ""; } };

async function ubLoad(){
  try{ S.ub = await api("/api/userbots"); S.ubErr = ""; }
  catch(e){ S.ubErr = e.message || "خطا در ارتباط با سرور"; }
  if(S.view === "userbot" && !S.sheet && !document.activeElement?.matches?.("input,textarea,select")){
    const it = ubItem(); if(S.ubSel && !it) S.ubSel = null;
    renderUserbot();
  }
}

function renderUserbot(){
  const app = $("#app");
  if(S.ubErr && !S.ub){
    app.innerHTML = `<div class="empty"><div class="ib big">${IC.person}</div><h2>بارگذاری نشد</h2><p class="muted">${esc(S.ubErr)}</p><button class="b sm" data-a="ubreload">تلاش دوباره</button></div>`;
    return;
  }
  if(!S.ub){ app.innerHTML = `<div class="ph"><h1>یوزربات</h1></div><div class="group"><div class="gi static"><span class="muted">در حال بارگذاری…</span></div></div>`; ubLoad(); return; }
  if(!S.ub.ok){
    app.innerHTML = `<div class="empty"><div class="ib big">${IC.person}</div><h2>یوزربات فعلاً در دسترس نیست</h2><p class="muted">این بخش روی سرور فعال نشده. بعداً دوباره سر بزن.</p></div>`;
    return;
  }
  const it = ubItem();
  if(S.ubSel && !it) S.ubSel = null;
  app.innerHTML = S.ubSel ? ubDetailHTML(it) : ubListHTML();
}

function ubListHTML(){
  const u = S.ub, full = u.items.length >= u.max;
  if(!u.max && !u.items.length) return `<div class="ph"><h1>یوزربات</h1></div><div class="empty"><div class="ib big">${IC.person}</div><h2>یوزربات با اشتراک فعال می‌شه</h2><p class="muted">اکانت شخصی‌ات را وصل کن تا جواب بدهد و برایت پیام زمان‌بندی‌شده بفرستد. ویژه‌ی اشتراک Premium و Pro.</p><button class="b sm" data-a="goplan">مشاهده‌ی اشتراک‌ها</button></div>`;
  const rows = u.items.map(x => { const [t] = UB_ST[x.status] || UB_ST.stopped;
    return `<div class="gi ubrow" role="button" tabindex="0" data-a="ubopen" data-id="${esc(x.id)}"><span class="dot ${x.status === "running" ? "on" : ""}"></span>
      <span class="gt"><b>${esc(x.name || "اکانت تلگرام")}</b><span>${x.username ? `<bdi dir="ltr">@${esc(x.username)}</bdi> · ` : ""}${t}</span></span>${goIc}</div>`; }).join("");
  return `<div class="ph"><h1>یوزربات</h1><span class="cnt">${N(u.items.length)}<span>از</span>${N(u.max)}</span></div>
    ${u.items.length ? `<div class="group sep">${rows}</div>${full ? "" : `<button class="b o sep-btn" data-a="ubnew">${IC.plus}اتصال اکانت دیگر</button>`}`
      : `<div class="empty"><div class="ib big">${IC.person}</div><h2>هنوز اکانتی وصل نکردی</h2><p class="muted">اکانت شخصی تلگرامت رو وصل کن تا وقتی نیستی، پیام‌های خصوصی‌ات رو خودکار جواب بدهد.</p><button class="b sm" data-a="ubnew">اتصال اکانت</button></div>`}
    <div class="panel mt">${ubH("یوزربات چه کارهایی می‌کند؟", "پاسخ خودکار با کلمه‌ی کلیدی، پیام غیبت، پاسخ هوشمند و دستورهای شخصی در چت خصوصی؛ پاسخ خودکار در گروه‌های انتخابی؛ پیام زمان‌بندی‌شده با صف و سقف روزانه برای گروه و کانال؛ عضویت اجباری خودکار.")}</div>
    <div class="panel mt2">${ubH("امنیت و قوانین", "ورود فقط با کد خود تلگرام است. رمز دومرحله‌ای ذخیره نمی‌شود و نشست رمزنگاری می‌شود. هر وقت خواستی قطع کن؛ نشست از خود تلگرام هم بسته می‌شود. ارسال فقط به گروه و کانال‌هایی است که خودت عضوشان هستی و انتخاب کرده‌ای (نه کاربران ناشناس، نه جوین یا اد). همه‌ی ارسال‌ها سقف ساعتی و روزانه و مکث تصادفی دارند.")}</div>`;
}

function ubDetailHTML(x){
  const [st, sc] = UB_ST[x.status] || UB_ST.stopped, run = x.status === "running";
  const cnt = a => a?.length ? ` (${a.length})` : "";
  const tabs = tabsHTML([["feat", "قابلیت‌ها"], ["chats", "گروه‌ها و کانال‌ها" + cnt(S.ubCfg?.chats)], ["posts", "زمان‌بندی" + cnt(S.ubCfg?.posts)], ["rules", "قانون‌ها" + cnt(S.ubCfg?.rules)], ["log", "گزارش"]], S.ubTab, "ubtab");
  const body = ({feat: ubFeatHTML, chats: ubChatsHTML, posts: ubPostsHTML, rules: ubRulesHTML, log: ubLogHTML})[S.ubTab](x);
  return `<div class="ubh"><button class="iconb" data-a="ubback" aria-label="بازگشت">${IC.back}</button>
      <div class="gt"><b>${esc(x.name || "اکانت تلگرام")}</b><span class="muted">${x.username ? `<bdi dir="ltr">@${esc(x.username)}</bdi> · ` : ""}<span class="n">${esc(x.phone)}</span></span></div>
      <span class="ubst ${sc}"><i class="dot ${sc === "on" ? "on" : ""}"></i>${st}</span></div>
    <button class="b ${run ? "o" : ""} mt2" data-a="ubpower">${run ? "خاموش کردن یوزربات" : x.status === "revoked" ? "اتصال دوباره‌ی اکانت" : "روشن کردن یوزربات"}</button>
    ${tabs}${body}`;
}

function ubFeatHTML(x){
  const c = S.ubCfg, gaps = UB_GAPS.includes(c.away.gap_h) ? UB_GAPS : [...UB_GAPS, c.away.gap_h].sort((a, b) => a - b);
  const cost = billingFixed() ? `هر ${N(S.cfg.ai_per)} پاسخ هوشمند ${N(S.cfg.ai_cost)} توکن از موجودی‌ات کم می‌شود.` : "هزینه‌ی هر پاسخ هوشمند، بر اساس مصرف واقعی مدل از توکن‌هایت کم می‌شود.";
  return `<div class="panel">${ubH("سطح ایمنی ارسال", "تعیین می‌کند ارسال‌ها و پاسخ‌های خودکار چقدر آهسته و محتاطانه انجام شوند. برای اکانت اصلی «محتاط» را نگه دار. " + (UB_SAFE_T[c.safe] || ""))}
      <select id="ub-safe">${UB_SAFE.map(([k, t]) => `<option value="${k}"${c.safe === k ? " selected" : ""}>${t}</option>`).join("")}</select></div>
    <div class="panel mt2">${ubH("پاسخ به چه کسانی؟", "ترتیب بررسی: قانون‌های کلیدواژه ← پاسخ هوشمند ← پیام غیبت. هر پیام حداکثر یک پاسخ می‌گیرد.")}
      <select id="ub-who">${UB_WHO.map(([k, t]) => `<option value="${k}"${c.who === k ? " selected" : ""}>${t}</option>`).join("")}</select></div>
    <div class="panel mt2">${ubH("عضویت اجباری", "وقتی رباتِ یکی از گروه‌های انتخابی‌ات، در پاسخ به پیام خودت یا با منشن تو، بخواهد در کانال یا گروهی عضو شوی، یوزربات عضو می‌شود و همان پیام را دوباره در همان گپ می‌فرستد. پیام ربات‌ها برای بقیه نادیده گرفته می‌شود. عضویت‌های پشت‌سرهم تلگرام را حساس می‌کند؛ سقف را کم نگه دار.")}
      <select id="ub-join">${[["off", "خاموش"], ["notify", "فقط به من خبر بده"], ["auto", "خودکار عضو شو و دوباره بفرست"]].map(([k, t]) => `<option value="${k}"${c.join.mode === k ? " selected" : ""}>${t}</option>`).join("")}</select>
      ${ubL("سقف عضویت در روز")}<input id="ub-join-daily" type="number" min="1" max="10" inputmode="numeric" value="${c.join.daily}"></div>
    <div class="panel mt2">${ubH("پیام غیبت", "وقتی کسی برایت می‌نویسد، این پیام را می‌فرستد؛ هر چت فقط یک‌بار در بازه‌ی انتخابی. در متن‌ها می‌توانی از {name} (نام فرستنده)، {time} و {date} استفاده کنی.")}
      <label class="chk"><input type="checkbox" id="ub-away-on"${c.away.on ? " checked" : ""}> فعال باشد</label>
      <textarea class="fa" id="ub-away-text" maxlength="1000" aria-label="متن پیام غیبت">${esc(c.away.text)}</textarea>
      ${ubL("حداقل فاصله‌ی دو پیام به یک نفر")}
      <select id="ub-away-gap">${gaps.map(h => `<option value="${h}"${c.away.gap_h === h ? " selected" : ""}>${h} ساعت</option>`).join("")}</select></div>
    <div class="panel mt2">${ubH("پاسخ هوشمند", "اگر قانونی جور نشد، هوش مصنوعی به جای تو کوتاه و مودبانه جواب می‌دهد. " + cost)}
      <label class="chk"><input type="checkbox" id="ub-ai-on"${c.ai.on ? " checked" : ""}> فعال باشد</label>
      ${ubL("دستور برای دستیار", "نقش، لحن و اطلاعات مجاز. مثلاً: دستیار فروشگاه لوازم دیجیتال هستی. ساعت کاری ۹ تا ۱۸ است. قیمت و تخفیف نده، بگو خودم جواب می‌دهم.")}
      <textarea class="fa" id="ub-ai-prompt" maxlength="1500" aria-label="دستور دستیار">${esc(c.ai.prompt)}</textarea>
      ${ubL("سقف روزانه به هر نفر (خصوصی)")}<input id="ub-ai-daily" type="number" min="1" max="100" inputmode="numeric" value="${c.ai.daily}">
      ${ubL("سقف روزانه در هر گروه")}<input id="ub-ai-gdaily" type="number" min="1" max="300" inputmode="numeric" value="${c.ai.gdaily}">
      <label class="chk"><input type="checkbox" id="ub-ai-disc"${c.ai.disclose ? " checked" : ""}> ابتدای پاسخ مشخص شود خودکار است</label></div>
    <div class="panel mt2">${ubH("دستورهای شخصی", "در هر چتی پیام خودت را با نقطه شروع کن تا همان پیام ویرایش شود: .ping سرعت، .time ساعت و تاریخ شمسی، .id شناسه‌ی چت، .help راهنما.")}
      <label class="chk"><input type="checkbox" id="ub-cmds"${c.cmds.on ? " checked" : ""}> فعال باشند</label></div>
    <div class="bar"><button class="b" data-a="ubsave">ذخیره‌ی تنظیمات</button></div>`;
}

function ubRulesHTML(){
  const rules = S.ubCfg.rules, full = rules.length >= 30;
  const list = rules.map((r, i) => `<div class="gi" role="button" tabindex="0" data-a="ubredit" data-i="${i}"><span class="dot ${r.on === false ? "" : "on"}"></span>
      <span class="gt"><b>${r.kw.map(esc).join("، ")}</b><span>${(UB_WHERE.find(w => w[0] === (r.where || "pm")) || UB_WHERE[0])[1]} · ${esc(r.text.replace(/\s+/g, " "))}</span></span>${goIc}</div>`).join("");
  return `<div class="sec">${ubH("قانون‌ها", "وقتی پیام کسی شامل کلمه‌های کلیدی بود، متن تو پاسخ داده می‌شود. هر قانون برای چت خصوصی، گروه‌های انتخابی یا هر دو است. بین پاسخ‌ها مکث هست تا تکرار نشود.")}</div>
    ${rules.length ? `<div class="group sep">${list}</div>` : `<div class="empty" style="padding:22px 16px"><p class="muted">قانونی نداری. مثلاً «قیمت» ← لیست قیمت‌ها.</p></div>`}
    <button class="b o sep-btn mt2" data-a="ubradd"${full ? " disabled" : ""}>${IC.plus}قانون جدید</button>`;
}

function ubChatsHTML(x){
  const chats = S.ubCfg.chats, full = chats.length >= (x.lim?.chats || 60), run = x.status === "running";
  const list = chats.map((h, i) => `<div class="gi" role="button" tabindex="0" data-a="ubcedit" data-i="${i}"><span class="dot ${h.on && !h.err ? "on" : ""}"></span>
      <span class="gt"><b>${esc(h.title)}</b><span>${h.kind === "channel" ? "کانال" : "گروه"} · ${h.err ? `<span style="color:var(--bad)">${esc(h.err)}</span>` : h.on ? UB_REPLY_T[h.reply] + (h.ai && h.reply !== "off" ? " · هوشمند" : "") : "غیرفعال"}</span></span>${goIc}</div>`).join("");
  return `<div class="sec">${ubH("گروه‌ها و کانال‌ها", "چت‌هایی که یوزربات اجازه دارد در آن‌ها کار کند. در گروه‌ها می‌تواند وقتی منشن یا ریپلای شدی (یا به کلمه‌های کلیدی) جواب بدهد؛ در گروه و کانال پیام زمان‌بندی‌شده می‌فرستد. فقط چت‌هایی که عضوشان هستی.")}${run ? "" : `<span class="ububchip tok">یوزربات خاموش است</span>`}</div>
    ${chats.length ? `<div class="group sep">${list}</div>` : `<div class="empty" style="padding:22px 16px"><p class="muted">گروه یا کانالی اضافه نشده.</p></div>`}
    <button class="b o sep-btn mt2" data-a="ubcadd"${full ? " disabled" : ""}>${IC.plus}افزودن گروه یا کانال</button>`;
}

const UB_CH = {ok: ["ok", "ارسال شد"], w: ["tok", "در انتظار (محدودیت)"], x: ["bad", "ناموفق"]};
function ubPostCard(p, i, x){
  const s = x.ps?.[p.id] || {}, tn = Date.now() / 1000, chats = S.ubCfg.chats;
  const bad = p.chats.filter(id => chats.find(h => h.id === id)?.err).length;
  let st = ["ok", "در انتظار"];
  if(!p.on) st = ["off", "غیرفعال"];
  else if(s.pend && x.ph_max && x.ph >= x.ph_max) st = ["tok", "سقف ساعتی پر است"];
  else if(s.pend) st = ["ac", "در حال ارسال"];
  else if(x.hold > tn) st = ["tok", "محدودیت تلگرام"];
  else if(bad) st = ["bad", "مقصد متوقف"];
  else if((s.n || 0) >= p.daily) st = ["tok", "سقف امروز پر شد"];
  else if(!ubInWin(p)) st = ["vio", "ساعت سکوت"];
  const every = Math.max(60, p.every_min * 60), from = s.last || (s.next ? s.next - every : 0);
  const cd = p.on && !s.pend && s.next ? `<div class="cdw"><span class="cd n" data-cd="${s.next}" data-from="${from}">--:--</span><small>تا ارسال بعدی</small></div>` : s.pend ? `<div class="cdw"><span class="cd n">${N(s.pend)}</span><small>مقصد در صف</small></div>` : `<div class="cdw"><span class="cd n">—</span></div>`;
  const pct = s.next && s.next > from ? Math.max(0, Math.min(100, (tn - from) / (s.next - from) * 100)) : 0;
  const chips = p.chats.map(id => { const h = chats.find(c => c.id === id); if(!h) return ""; const r = s.tg?.[String(id)]; const k = h.err ? "bad" : r ? UB_CH[r.s]?.[0] || "" : "";
    return `<span class="ubchip ${k}" title="${esc(h.err || (r ? UB_CH[r.s]?.[1] + " · " + ubWhen(r.t) : "هنوز ارسال نشده"))}">${esc(h.title.slice(0, 18))}</span>`; }).join("");
  return `<div class="ubc ${st[0]}" role="button" tabindex="0" data-a="ubpedit" data-i="${i}">
    <div class="ubc-h"><b>${esc(p.name)}</b><span class="ubchip ${st[0]}">${st[1]}</span></div>
    <div class="ubc-m">${cd}<div class="ubc-s"><div><b class="n ok">${N(s.ok || 0)}</b><small>ارسال شد</small></div><div><b class="n bad">${N(s.bad || 0)}</b><small>ناموفق</small></div><div><b class="n">${N(s.n || 0)}/${N(p.daily)}</b><small>امروز</small></div></div></div>
    <div class="ubpbar"><i style="width:${pct}%"></i></div>
    <div class="ubc-c">${chips}</div>
    <div class="ubc-f"><small>${ubEveryT(p.every_min)}${p.media ? " · فایل" : ""} · ${String(p.from_h).padStart(2, "0")}–${String(p.to_h).padStart(2, "0")}</small>${s.err ? `<small class="bad">${esc(s.err)}</small>` : s.last ? `<small>آخرین دوره: ${ubWhen(s.last)}</small>` : ""}</div></div>`;
}

function ubPostsHTML(x){
  const posts = S.ubCfg.posts, full = posts.length >= (x.lim?.posts || 20), none = !S.ubCfg.chats.length;
  return `<div class="sec">${ubH("پیام‌های زمان‌بندی‌شده", "هر مورد یک زمان‌بندی است: بعد از ذخیره منتظر نوبتش می‌ماند و هر نوبت به همه‌ی مقصدها با مکث تصادفی و صف ارسال می‌شود. اگر تلگرام صبر بخواهد (اسلو‌مود یا فلود)، یوزربات صبر می‌کند و دوباره تلاش می‌کند. برای ارسال فوری، داخل هر کارت «ذخیره و ارسال همین حالا» را بزن.")}</div>
    ${posts.length ? posts.map((p, i) => ubPostCard(p, i, x)).join("") : `<div class="empty" style="padding:22px 16px"><p class="muted">${none ? "اول از تب «گروه‌ها و کانال‌ها» مقصد اضافه کن." : "زمان‌بندی‌ای نساخته‌ای."}</p></div>`}
    <button class="b o sep-btn mt2" data-a="ubpadd"${full || none ? " disabled" : ""}>${IC.plus}زمان‌بندی جدید</button>`;
}

function ubLogHTML(x){
  const log = x.log || [];
  return `<div class="stats" style="grid-template-columns:1fr 1fr 1fr"><div class="stat"><div class="k">پیام‌های دریافتی</div>${N(x.stats.in)}</div><div class="stat"><div class="k">پاسخ‌ها</div>${N(x.stats.out)}</div><div class="stat"><div class="k">پاسخ هوشمند</div>${N(x.stats.ai)}</div></div>
    <div class="sec"><h2>آخرین فعالیت‌ها</h2><button class="b o sm" data-a="ubrefresh">${IC.refresh}تازه‌سازی</button></div>
    <div class="group">${log.length ? log.map(l => `<div class="led"><div>${esc(l.k)}${l.w ? ` ← ${esc(l.w)}` : ""}</div><small class="muted n">${ubTime(l.t)}</small></div>`).join("") : `<div class="gi static"><span class="muted">هنوز فعالیتی ثبت نشده. متن پیام‌ها هیچ‌جا ذخیره نمی‌شود.</span></div>`}</div>
    <div class="sec"><h2>قطع اتصال</h2></div>
    <p class="muted" style="margin:0 2px 10px">یوزربات حذف می‌شود و نشست این اکانت از خود تلگرام هم بسته می‌شود. هر زمان خواستی از تنظیمات تلگرام ← دستگاه‌ها هم می‌توانی نشست «Azadi Userbot» را ببندی.</p>
    <button class="b r" data-a="ubdel">${IC.trash}قطع اتصال و حذف یوزربات</button>`;
}

/* فرم قابلیت‌ها را توی پیش‌نویس می‌خونه تا با عوض کردن تب چیزی گم نشه */
function ubRead(){
  if(!S.ubCfg || !$("#ub-who")) return;
  const c = S.ubCfg, v = id => $(id)?.value ?? "", k = id => !!$(id)?.checked;
  c.safe = v("#ub-safe") || c.safe; c.join = {mode: v("#ub-join") || c.join?.mode || "off", daily: Math.max(1, Math.min(10, +v("#ub-join-daily") || 5))}; c.who = v("#ub-who"); c.away.on = k("#ub-away-on"); c.away.text = v("#ub-away-text"); c.away.gap_h = +v("#ub-away-gap") || 6;
  c.ai.on = k("#ub-ai-on"); c.ai.prompt = v("#ub-ai-prompt"); c.ai.daily = Math.max(1, Math.min(100, +v("#ub-ai-daily") || 20)); c.ai.gdaily = Math.max(1, Math.min(300, +v("#ub-ai-gdaily") || 30)); c.ai.disclose = k("#ub-ai-disc"); c.cmds.on = k("#ub-cmds");
}
async function ubCommit(fn, msg = "ذخیره شد"){
  ubRead();
  const cfg = cp(S.ubCfg); fn?.(cfg);
  const d = await api(`/api/userbots/${S.ubSel}/config`, "PUT", {config: cfg});
  ubPut(d.item); S.ubCfg = ubNorm(d.item.config); toast(msg); haptic("ok");
}
const ubNorm = c => { c = cp(c || {}); c.chats ||= []; c.posts ||= []; c.rules ||= []; c.safe ||= "balanced"; c.join = Object.assign({mode: "off", daily: 5}, c.join || {}); c.away ||= {on: false, text: "", gap_h: 6}; c.cmds ||= {on: true}; c.ai = Object.assign({on: false, prompt: "", daily: 20, gdaily: 30, disclose: true}, c.ai || {}); return c; };
const ubOpen = id => { const it = S.ub.items.find(x => x.id === id); if(!it) return; S.ubSel = id; S.ubTab = "feat"; S.ubCfg = ubNorm(it.config); renderUserbot(); scrollTo(0, 0);
  api(`/api/userbots/${id}`).then(d => { ubPut(d.item); if(S.view === "userbot" && S.ubSel === id && S.ubTab === "log") renderUserbot(); }).catch(() => {}); };

Object.assign(A, {
  ubinfo: el => ubTip(el),
  ubreload: () => { S.ubErr = ""; S.ub = null; renderUserbot(); },
  ubopen: el => ubOpen(el.dataset.id),
  ubback: () => { ubRead(); S.ubSel = null; S.ubCfg = null; renderUserbot(); scrollTo(0, 0); ubLoad(); },
  ubtab: el => { ubRead(); S.ubTab = el.dataset.k; renderUserbot(); },
  ubsave: el => busy(el, async () => { await ubCommit(null); renderUserbot(); }),
  ubnew: () => openUbConn(),
  ubradd: () => { ubRead(); S.sheet = {kind: "ubrule"}; D = {i: null, kw: "", mode: "has", text: "", on: true, where: "pm"}; renderSheet(); },
  ubredit: el => { ubRead(); const i = +el.dataset.i, r = S.ubCfg.rules[i]; if(!r) return; S.sheet = {kind: "ubrule"}; D = {i, kw: r.kw.join("، "), mode: r.mode, text: r.text, on: r.on !== false, where: r.where || "pm"}; renderSheet(); },
  ubcadd: () => openUbPick(),
  ubcedit: el => { ubRead(); const i = +el.dataset.i, h = S.ubCfg.chats[i]; if(!h) return; S.sheet = {kind: "ubchat"}; D = {...cp(h), i}; renderSheet(); },
  ubpadd: () => { ubRead(); if(!S.ubCfg.chats.length) return toast("اول گروه یا کانال اضافه کن"); S.sheet = {kind: "ubpost"};
    D = {i: null, id: "", name: "", chats: [], text: "", media: "", fmt: "html", mode: "seq", every_min: 360, from_h: 8, to_h: 23, daily: 4, on: true, rp: false, rwin: 30, rnone: "plain", nl: false, mg: false, lg: false, lgs: "both", fb: "text", fwd: ""}; renderSheet(); },
  ubpedit: el => { ubRead(); const i = +el.dataset.i, p = S.ubCfg.posts[i]; if(!p) return; S.sheet = {kind: "ubpost"};
    D = {i, id: p.id, name: p.name, chats: [...p.chats], text: p.texts.join("\n---\n"), media: p.media || "", fmt: p.fmt || "html", mode: p.mode, every_min: p.every_min, from_h: p.from_h, to_h: p.to_h, daily: p.daily, on: p.on, rp: !!p.rp, rwin: p.rwin || 30, rnone: p.rnone || "plain", nl: !!p.nl, mg: !!p.mg, lg: !!p.lg, lgs: p.lgs || "both", fb: p.fb || "text", fwd: p.fwd || ""}; renderSheet(); },
  ubrefresh: el => busy(el, async () => { const d = await api(`/api/userbots/${S.ubSel}`); ubPut(d.item); renderUserbot(); }),
  ubpower: el => {
    const x = ubItem(); if(!x) return;
    if(x.status === "revoked") return openUbConn();
    busy(el, async () => {
      const d = await api(`/api/userbots/${x.id}/${x.status === "running" ? "stop" : "start"}`, "POST");
      ubPut(d.item); renderUserbot(); toast(d.item.status === "running" ? "یوزربات روشن شد" : "یوزربات خاموش شد"); haptic("ok");
    });
  },
  ubdel: () => confirmQ("یوزربات حذف شود و نشست این اکانت از تلگرام بسته شود؟", ok => { if(!ok) return;
    busy(null, async () => { await api(`/api/userbots/${S.ubSel}`, "DELETE"); S.ub.items = S.ub.items.filter(x => x.id !== S.ubSel); S.ubSel = null; S.ubCfg = null; renderUserbot(); scrollTo(0, 0); toast("اتصال قطع شد"); }); }),
});
document.addEventListener("input", e => {
  if(e.target.id === "ubp-q"){ const q = e.target.value.trim().toLowerCase(); document.querySelectorAll(".ubpick").forEach(r => { r.style.display = !q || r.dataset.t.includes(q) ? "" : "none"; }); }
});
document.addEventListener("keydown", e => {
  if(e.key === "Enter" || e.key === " "){ const r = e.target.closest?.(".ubrow"); if(r){ e.preventDefault(); A.ubopen(r); } const q = e.target.closest?.(".ubc"); if(q){ e.preventDefault(); A.ubpedit(q); } }
  if(e.key === "Enter" && e.target.id?.startsWith("uc-")){ e.preventDefault(); document.querySelector('[data-sh="ubsend"],[data-sh="ubverify"],[data-sh="ubpwgo"]')?.click(); }
});
