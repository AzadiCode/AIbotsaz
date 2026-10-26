/* ═══════════════════════════════════════════════════════════════
   mapp.js — رانتایم مینی‌اپ: رندرر ثابت کانفیگ JSON (هیچ کد کاربر اجرا نمی‌شود).
   یک بار نوشته شده تا هم پیش‌نمایش سازنده (?preview=1 با postMessage) و هم مینی‌اپ واقعی
   (احراز با initData امضاشده با توکن همان ربات، از مسیرهای /rt/) از همین کد استفاده کنند.
   همه‌ی متن‌ها با textContent و ویژگی‌های امن ساخته می‌شوند؛ فقط متن مالکِ ربات با
   زیرمجموعه‌ی امنِ HTML تلگرام رندر می‌شود (whitelist).
   ═══════════════════════════════════════════════════════════════ */
(function(){
"use strict";
const QS = new URLSearchParams(location.search);
const PREVIEW = QS.get("preview") === "1";
const BOT_ID = (location.pathname.split("/")[2] || "").replace(/[^0-9a-f]/g, "");
const tgw = window.Telegram && window.Telegram.WebApp;
const $ = s => document.querySelector(s);
const ACT_OPS = new Set(["set","add","clear","random","notify","remind","dice","pick","db_add","db_get","db_set","db_inc","db_del","fetch","send","game_play"]);
const UI_OPS = new Set(["goto","url","copy","share","toast","close","back","refresh"]);
const FAD = d => "۰۱۲۳۴۵۶۷۸۹"[d];
const FADI = s => String(s ?? "").replace(/[۰-۹]/g, d => "۰۱۲۳۴۵۶۷۸۹".indexOf(d));

const ST = {app: null, ver: 0, media: {}, screen: null, stack: [], vars: {}, glo: {}, user: null, bot: {},
            guest: null, preview: PREVIEW, timers: {}};

/* ── ابزارهای امن ── */
function el(tag, cls, text){
  const e = document.createElement(tag);
  if(cls) e.className = cls;
  if(text != null) e.textContent = text;
  return e;
}
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
/* متن مالک ربات: زیرمجموعه‌ی امن HTML تلگرام (بولد، کج، کد، نقل‌قول، لینک https و اسپویلر) */
function rich(t){
  let h = esc(t ?? "");
  h = h.replace(/&lt;(\/?)(b|strong|i|em|u|ins|s|strike|del|code|pre|blockquote|tg-spoiler)&gt;/gi, "<$1$2>");
  h = h.replace(/&lt;a href=&quot;(https?:\/\/[^&"<>]+)&quot;&gt;/gi, '<a href="$1" target="_blank" rel="noopener noreferrer">');
  h = h.replace(/&lt;\/a&gt;/gi, "</a>");
  h = h.replace(/&lt;tg-emoji emoji-id=&quot;\d+&quot;&gt;([\s\S]*?)&lt;\/tg-emoji&gt;/g, "$1");
  return h.replace(/\n/g, "<br>");
}
function fd(s){
  if(!ST.app || ST.app.theme.digits !== "fa") return String(s);
  return String(s).replace(/\d/g, x => FAD(x));
}
/* جایگزینی {متغیر} و {متغیر|پیش‌فرض} — فقط متن، مثل موتور ربات */
function fill(t){
  return String(t ?? "").replace(/\{([a-z][a-z0-9_]{0,19})(?:\|([^{}]{0,60}))?\}/gi, (m, k, def) => {
    let v = varOf(k);
    if((v === "" || v == null) && def != null) return def;
    return v == null ? m : String(v);
  });
}
function varOf(k){
  const u = ST.user || {};
  if(k === "name") return u.first_name || "دوست من";
  if(k === "id") return String(u.id || "");
  if(k === "username") return u.username ? "@" + u.username : "";
  if(k === "bot_name") return ST.bot.name || "";
  if(k === "bot_username") return ST.bot.username ? "@" + ST.bot.username : "";
  if(k === "is_owner") return String(u.is_owner || 0);
  if(k in ST.vars) return String(ST.vars[k] ?? "");
  if(k in ST.glo) return String(ST.glo[k] ?? "");
  return "";
}
/* ارزیابی شرط «when» (همان معنای موتور ربات؛ فقط برای پنهان‌کردن نمایشی) */
function when(c){
  if(!c || typeof c !== "object") return true;
  if(Array.isArray(c.all)) return c.all.every(when);
  if(Array.isArray(c.any)) return c.any.some(when);
  if(c.not) return !when(c.not);
  const a = String(varOf(c.var) ?? ""), op = c.op || "==";
  if(op === "empty") return a.trim() === "";
  if(op === "filled") return a.trim() !== "";
  let b = String(fill(c.value ?? ""));
  const x = parseFloat(FADI(a)), y = parseFloat(FADI(b));
  if(op === "contains") return a.toLowerCase().includes(b.toLowerCase());
  if(op === "==") return (!isNaN(x) && !isNaN(y) ? x === y : a.trim().toLowerCase() === b.trim().toLowerCase());
  if(op === "!=") return !when({...c, op: "=="});
  if(isNaN(x) || isNaN(y)) return false;
  return op === ">" ? x > y : op === ">=" ? x >= y : op === "<" ? x < y : op === "<=" ? x <= y : false;
}
function haptic(k){ try{ k ? tgw?.HapticFeedback?.notificationOccurred("success") : tgw?.HapticFeedback?.selectionChanged(); }catch(_){} }
let toastT = null;
function toast(m){
  const t = $("#mtoast");
  t.textContent = m; t.classList.add("show");
  clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove("show"), 2600);
}
function openUrl(u){
  try{ if(/^https:\/\/t\.me\//.test(u) && tgw?.openTelegramLink) return tgw.openTelegramLink(u);
       if(/^https:\/\//.test(u) && tgw?.openLink) return tgw.openLink(u); }catch(_){}
  window.open(u, "_blank", "noopener");
}
function mediaSrc(b){
  if(b.media && ST.media[b.media]) return ST.media[b.media].url;
  if(/^https:\/\//.test(b.url || "")) return b.url;
  return "";
}
function clearTimers(){ Object.values(ST.timers).forEach(clearInterval); ST.timers = {}; }

/* ── تم ── */
function applyTheme(){
  const th = (ST.app && ST.app.theme) || {};
  const mode = th.mode === "auto" ? ((tgw?.colorScheme || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"))) : (th.mode || "dark");
  document.documentElement.dataset.mode = mode === "light" ? "light" : "dark";
  const r = document.documentElement.style;
  if(/^#[0-9a-fA-F]{6}$/.test(th.accent || "")) r.setProperty("--ac", th.accent);
  if(/^#[0-9a-fA-F]{6}$/.test(th.on_accent || "")) r.setProperty("--onac", th.on_accent);
  r.setProperty("--rad", (Math.max(0, Math.min(28, +th.radius || 16))) + "px");
  const f = th.font === "system" ? "system-ui" : th.font === "oxanium_vazir" ? '"Oxanium","Vazirmatn",Tahoma,system-ui' : '"Vazirmatn",Tahoma,system-ui';
  document.body.style.fontFamily = f;
  try{
    const dark = mode !== "light";
    tgw?.setHeaderColor?.(dark ? "#081116" : "#EAF0F2");
    tgw?.setBackgroundColor?.(dark ? "#081116" : "#EAF0F2");
  }catch(_){}
}

/* ── اکشن‌ها ── */
function needServer(doList){ return (doList || []).some(a => ACT_OPS.has(a.op)); }
function applyDirs(dirs){
  let rerender = false;
  (dirs || []).forEach(d => {
    if(d.a === "goto" && d.screen){ if(screenOf(d.screen) && d.screen !== ST.screen) go(d.screen); }
    else if(d.a === "url") openUrl(d.url);
    else if(d.a === "copy"){ try{ navigator.clipboard?.writeText(d.text || ""); }catch(_){} toast("کپی شد"); }
    else if(d.a === "share") openUrl("https://t.me/share/url?url=" + encodeURIComponent("https://t.me/" + (ST.bot.username || "")) + "&text=" + encodeURIComponent(d.text || ""));
    else if(d.a === "toast") toast(d.text || "");
    else if(d.a === "close"){ try{ tgw?.close(); }catch(_){} }
    else if(d.a === "back") goBack();
    else if(d.a === "refresh") rerender = true;
  });
  return rerender;
}
async function runDo(doList, hid){
  if(ST.preview){
    if(needServer(doList)) return toast("این اکشن در پیش‌نمایش غیرفعال است");
    applyDirs(doList.map(a => ({...a, a: a.op})));
    return;
  }
  if(!needServer(doList)){
    applyDirs(doList.map(a => ({...a, a: a.op})));
    return;
  }
  try{
    const r = await api("/rt/" + BOT_ID + "/act", {h: hid});
    const rerender = applyDirs(r.dirs);
    if(r.vars) ST.vars = r.vars;
    if(r.globals) ST.glo = r.globals;
    if(r.ver && r.ver !== ST.ver) return silentRefresh();
    if(rerender) render(ST.screen, true);
  }catch(e){ toast(e.message || "خطا در اجرا"); }
}
function api(path, body){
  return fetch(path, {method: body ? "POST" : "GET",
    headers: {"Content-Type": "application/json", ...(tgw?.initData ? {"X-Init-Data": tgw.initData} : {})},
    body: body ? JSON.stringify(body) : undefined})
    .then(async r => {
      const d = await r.json().catch(() => ({}));
      if(!r.ok){ const e = new Error(d.error || "ارتباط برقرار نشد"); e.status = r.status; throw e; }
      return d;
    });
}
async function silentRefresh(){
  try{
    const d = await api("/rt/" + BOT_ID + "/boot", {});
    if(d.status === "ok"){ ST.app = d.app; ST.ver = d.ver; ST.media = d.media || {}; ST.vars = d.vars || {}; ST.glo = d.globals || {};
      if(!screenOf(ST.screen)) ST.screen = d.app.home;
      applyTheme(); render(ST.screen, true); }
  }catch(_){}
}

/* ── ناوبری ── */
function screenOf(id){ return (ST.app && ST.app.screens && ST.app.screens[id]) || null; }
function go(id){
  if(!screenOf(id)) return;
  if(ST.screen && ST.screen !== id) ST.stack.push(ST.screen);
  if(ST.stack.length > 24) ST.stack.shift();
  render(id);
}
function goBack(){
  const prev = ST.stack.pop();
  render(prev || ST.app.home);
}
function backBtn(){
  try{
    if(ST.preview || !tgw?.BackButton) return;
    if(!backBtn.bound){ tgw.BackButton.onClick(goBack); backBtn.bound = true; }   // فقط یک بار ثبت می‌شود؛ ثبت تکراری یعنی یک لمس چند بار برگشت
    if(ST.stack.length) tgw.BackButton.show();
    else tgw.BackButton.hide();
  }catch(_){}
}

/* ── رندر بلوک‌ها ── */
const IC = {
  home: '<path d="M3.5 10.5L12 4l8.5 6.5"/><path d="M6 9.5V19a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V9.5"/>',
  shop: '<path d="M5 8h14l-1 12H6z"/><path d="M9 8V6.5a3 3 0 0 1 6 0V8"/>',
  form: '<rect x="5" y="4" width="14" height="16" rx="3"/><path d="M9 9h6M9 13h6M9 17h3"/>',
  star: '<path d="M12 3l2.5 5.7 6.2.6-4.7 4.1 1.4 6.1L12 16.3 6.6 19.5 8 13.4 3.3 9.3l6.2-.6z"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 10.5V17M12 7.2h.01"/>',
  users: '<circle cx="9" cy="9" r="3.3"/><path d="M3.5 19c.6-3.2 2.8-4.8 5.5-4.8s4.9 1.6 5.5 4.8M16 6.2a3.2 3.2 0 0 1 0 6"/>',
  phone: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/>',
  image: '<rect x="3.5" y="4.5" width="17" height="15" rx="3"/><circle cx="9" cy="10" r="1.7"/><path d="M4 17l4.5-4.5 3.5 3.5 3-3 5 5"/>',
  chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>',
  gift: '<rect x="4" y="10" width="16" height="10" rx="2"/><path d="M12 10v10M4 10h16M8 10a2.5 2.5 0 1 1 1.5-4.5C11 6.8 12 10 12 10s1-3.2 2.5-4.5A2.5 2.5 0 1 1 16 10"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  trophy: '<path d="M8 4h8v5a4 4 0 0 1-8 0z"/><path d="M8 5H5.5a2.5 2.5 0 0 0 2.7 4M16 5h2.5a2.5 2.5 0 0 1-2.7 4M12 13v4M8.5 20h7"/>',
  go: '<path d="M15 6l-6 6 6 6"/>',
};
const svg = p => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
const ICON = k => svg(IC[k] || IC.home);

const BLOCKS = {
  hero(b){
    if(!b.title && !b.text && !mediaSrc(b) && !(b.cta && b.cta.text)) return document.createDocumentFragment();      // هیروی خالی: باکس بزرگ بی‌مصرف نمی‌سازد
    const w = el("div", "blk");
    const c = el("div", "hero");
    const src = mediaSrc(b);
    if(src && /\.(png|jpe?g|webp|gif)(\?|$)/i.test(src) || (b.media && ST.media[b.media]?.kind === "photo")){
      const im = el("img"); im.loading = "lazy"; im.alt = ""; im.src = src; c.appendChild(im);
    }
    const inr = el("div", "hin");
    if(b.title) inr.appendChild(el("h2", "", fill(b.title)));
    if(b.text){ const p = el("p"); p.innerHTML = rich(fill(b.text)); inr.appendChild(p); }
    if(b.cta && b.cta.text && b.cta.hid){
      const bt = el("button", "cta", fill(b.cta.text));
      bt.addEventListener("click", () => { haptic(); runDo(b.cta.do, b.cta.hid); });
      inr.appendChild(bt);
    }
    c.appendChild(inr);
    w.appendChild(c);
    return w;
  },
  text(b){
    const d = el("div", "blk card");
    const p = el("div", "txt");
    p.innerHTML = rich(fill(b.text));
    d.appendChild(p);
    return d;
  },
  image(b){
    const src = mediaSrc(b);
    if(!src) return document.createDocumentFragment();
    const w = el("div", "blk media");
    const im = el("img"); im.loading = "lazy"; im.alt = ""; im.src = src; w.appendChild(im);
    if(b.caption) w.appendChild(el("div", "mcap", fill(b.caption)));
    return w;
  },
  gallery(b){
    const g = el("div", "blk gal");
    (b.items || []).forEach(it => { const src = mediaSrc(it); if(src){ const im = el("img"); im.loading = "lazy"; im.alt = ""; im.src = src; g.appendChild(im); } });
    return g;
  },
  video(b){
    const src = mediaSrc(b);
    if(!src) return document.createDocumentFragment();
    const w = el("div", "blk media");
    const v = el("video"); v.controls = true; v.preload = "none"; v.playsInline = true; v.src = src; w.appendChild(v);
    if(b.caption) w.appendChild(el("div", "mcap", fill(b.caption)));
    return w;
  },
  audio(b){
    const src = mediaSrc(b);
    if(!src) return document.createDocumentFragment();
    const w = el("div", "blk media card");
    const a = el("audio"); a.controls = true; a.preload = "none"; a.src = src; w.appendChild(a);
    if(b.caption) w.appendChild(el("div", "mcap", fill(b.caption)));
    return w;
  },
  buttons(b){
    const w = el("div", "blk");
    (b.rows || []).forEach(row => {
      const r = el("div", "brow");
      row.forEach(x => {
        if(!x.hid || !x.text) return;
        const bt = el("button", "bbtn", fill(x.text));
        bt.addEventListener("click", () => { haptic(); runDo(x.do, x.hid); });
        r.appendChild(bt);
      });
      if(r.children.length) w.appendChild(r);
    });
    return w;
  },
  cards(b){
    const g = el("div", "blk cgrid");
    (b.items || []).forEach(it => {
      const c = el("div", "citem");
      const src = mediaSrc(it);
      if(src){ const im = el("img", "cim"); im.loading = "lazy"; im.alt = ""; im.src = src; c.appendChild(im); }
      const inr = el("div", "cin");
      if(it.title) inr.appendChild(el("b", "", fill(it.title)));
      if(it.text) inr.appendChild(el("span", "", fill(it.text)));
      c.appendChild(inr);
      if(it.hid && (it.do || []).length){
        c.style.cursor = "pointer";
        c.setAttribute("role", "button"); c.setAttribute("tabindex", "0");
        const act = () => { haptic(); runDo(it.do, it.hid); };
        c.addEventListener("click", act);
        c.addEventListener("keydown", e => { if(e.key === "Enter") act(); });
      }
      g.appendChild(c);
    });
    return g;
  },
  list(b){
    const w = el("div", "blk lst");
    if(ST.preview){ w.textContent = b.empty || "هنوز چیزی ثبت نشده."; return w; }
    w.textContent = "…";
    api("/rt/" + BOT_ID + "/data?b=" + encodeURIComponent(b.id || ""))
      .then(d => { w.textContent = (d.items || []).length ? d.items.map(fd).join("\n") : (d.empty || "هنوز چیزی ثبت نشده."); })
      .catch(() => { w.textContent = b.empty || "هنوز چیزی ثبت نشده."; });
    return w;
  },
  board(b){
    const w = el("div", "blk lst bd");
    if(ST.preview){ w.textContent = (b.label || "برترین‌ها") + "\n—"; return w; }
    w.textContent = "…";
    api("/rt/" + BOT_ID + "/data?b=" + encodeURIComponent(b.id || ""))
      .then(d => { w.textContent = fd(d.text || ""); })
      .catch(() => { w.textContent = b.label || "برترین‌ها"; });
    return w;
  },
  form(b){
    const w = el("div", "blk card");
    if(b.title) w.appendChild(el("b", "", fill(b.title)));
    const vals = {};
    (b.fields || []).forEach(f => {
      const wrap = el("div", "fld");
      const lab = el("label");
      lab.appendChild(document.createTextNode(f.label || f.k));
      if(f.req) lab.appendChild(el("i", "", " *"));
      wrap.appendChild(lab);
      let inp;
      if(f.type === "select"){
        inp = el("select");
        const o0 = el("option", "", "— انتخاب کن —"); o0.value = ""; inp.appendChild(o0);
        (f.opts || []).forEach(o => { const op = el("option", "", o); op.value = o; inp.appendChild(op); });
      }else if(f.type === "date"){
        inp = el("input"); inp.type = "date";
      }else{
        inp = el("input");
        inp.type = f.type === "number" ? "text" : f.type === "phone" ? "tel" : f.type === "email" ? "email" : "text";
        inp.inputMode = f.type === "number" ? "decimal" : f.type === "phone" ? "tel" : "";
        inp.placeholder = f.type === "number" ? "عدد" : f.type === "phone" ? "09xxxxxxxxx" : f.type === "email" ? "name@mail.com" : "";
      }
      inp.name = f.k;
      inp.setAttribute("aria-label", f.label || f.k);
      inp.addEventListener("input", () => { wrap.classList.remove("bad"); vals[f.k] = inp.value; });
      inp.addEventListener("change", () => { wrap.classList.remove("bad"); vals[f.k] = inp.value; });
      wrap.appendChild(inp);
      wrap.appendChild(el("div", "err", "مقدار درست بنویس" + (f.req ? " (لازم است)" : "")));
      w.appendChild(wrap);
    });
    const bt = el("button", "cta", "ثبت");
    bt.addEventListener("click", async () => {
      let bad = null;
      (b.fields || []).forEach(f => {
        const inp = w.querySelector('[name="' + f.k + '"]');
        const wrap = inp && inp.closest(".fld");
        const v = String((inp && inp.value) || "").trim();
        let ok = !!v || !f.req;
        if(v && f.type === "number" && isNaN(parseFloat(FADI(v)))) ok = false;
        if(v && f.type === "phone" && !/^\+?\d{8,15}$/.test(v.replace(/[\s\-()]/g, ""))) ok = false;
        if(v && f.type === "email" && !/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(v)) ok = false;
        if(wrap) wrap.classList.toggle("bad", !ok);
        if(!ok && !bad) bad = f;
      });
      if(bad) return toast("«" + (bad.label || "") + "» را درست پر کن");
      if(ST.preview) return toast("ثبت فرم در پیش‌نمایش غیرفعال است");
      bt.disabled = true;
      try{
        const r = await api("/rt/" + BOT_ID + "/form", {block: b.id, values: vals, k: Math.random().toString(36).slice(2) + Date.now().toString(36)});
        if(r.vars) ST.vars = r.vars;
        if(r.globals) ST.glo = r.globals;
        haptic(true);
        const done = el("div", "fdone", (r.done || "ثبت شد. ممنون!") + (r.ticket ? " (تیکت #" + r.ticket + ")" : ""));
        w.querySelectorAll(".fld,button.cta").forEach(x => x.remove());
        w.appendChild(done);
        w.appendChild(el("div", "", ""));
      }catch(e){ toast(e.message || "ثبت ناموفق بود"); }
      finally{ bt.disabled = false; }
    });
    w.appendChild(bt);
    return w;
  },
  stat(b){
    const w = el("div", "blk card stat");
    const v = el("div", "sv", fd(fill("{" + (b.var || "") + "|0}")));
    w.appendChild(el("div", "mut", b.label || ""));
    w.appendChild(v);
    return w;
  },
  faq(b){
    const w = el("div", "blk");
    (b.items || []).forEach(it => {
      const f = el("div", "faqi");
      const q = el("button", "q");
      q.appendChild(el("span", "", it.q));
      q.insertAdjacentHTML("beforeend", '<span class="ch">' + svg('<path d="M6 9l6 6 6-6"/>', "") + "</span>");
      q.querySelector(".ch").innerHTML = svg('<path d="M6 9l6 6 6-6"/>');
      const a = el("div", "a", it.a);
      q.addEventListener("click", () => { f.classList.toggle("open"); haptic(); });
      f.appendChild(q); f.appendChild(a);
      w.appendChild(f);
    });
    return w;
  },
  banner(b){
    if(!when(b.when)) return document.createDocumentFragment();
    const d = el("div", "blk banner " + (b.style === "ok" || b.style === "warn" ? b.style : "info"));
    d.innerHTML = rich(fill(b.text));
    return d;
  },
  countdown(b){
    const w = el("div", "blk card cd");
    if(b.title) w.appendChild(el("b", "", fill(b.title)));
    const box = el("div", "big");
    const units = [["d", "روز"], ["h", "ساعت"], ["m", "دقیقه"], ["s", "ثانیه"]];
    const els = {};
    units.forEach(([k, lab]) => { const d = el("div"); const n = el("b", "", "0"); d.appendChild(n); d.appendChild(el("small", "", lab)); box.appendChild(d); els[k] = n; });
    w.appendChild(box);
    const to = +b.to || 0;
    const tick = () => {
      let s = Math.max(0, Math.floor(to - Date.now() / 1000));
      if(!s){ clearInterval(ST.timers[b.id]); if(b.done){ box.hidden = true; w.appendChild(el("div", "mut", fill(b.done))); } return; }
      els.d.textContent = fd(Math.floor(s / 86400));
      els.h.textContent = fd(String(Math.floor(s % 86400 / 3600)).padStart(2, "0"));
      els.m.textContent = fd(String(Math.floor(s % 3600 / 60)).padStart(2, "0"));
      els.s.textContent = fd(String(s % 60).padStart(2, "0"));
    };
    tick();
    ST.timers[b.id] = setInterval(tick, 1000);
    return w;
  },
  pay(b){
    const w = el("div", "blk card");
    w.appendChild(el("b", "", fill(b.title || "خرید")));
    if(b.desc) w.appendChild(el("div", "mut", fill(b.desc)));
    const bt = el("button", "cta", fd(b.stars + " ⭐"));
    bt.addEventListener("click", async () => {
      if(ST.preview) return toast("پرداخت در پیش‌نمایش غیرفعال است");
      bt.disabled = true;
      try{
        const r = await api("/rt/" + BOT_ID + "/act", {h: b.id});
        if(r.invoice && tgw?.openInvoice){
          tgw.openInvoice(r.invoice, st => {
            if(st === "paid"){ toast("پرداخت انجام شد. ممنون!"); haptic(true); silentRefresh(); }
          });
        }else if(r.invoice) window.open(r.invoice, "_blank", "noopener");
      }catch(e){ toast(e.message || "فاکتور ساخته نشد"); }
      finally{ bt.disabled = false; }
    });
    w.appendChild(bt);
    return w;
  },
  ai(b){
    const w = el("div", "blk aichat");
    const log = el("div", "ailog");
    const g = el("div", "aim a", fill(b.greeting || "سؤالت رو بنویس."));
    log.appendChild(g);
    const trail = el("div", "aitrail");
    const inp = el("input");
    inp.placeholder = "پیام…"; inp.setAttribute("aria-label", "پیام به دستیار");
    const send = el("button", "aisend");
    send.innerHTML = svg('<path d="M20 12H4M11 5l-7 7 7 7"/>');
    async function ask(){
      const t = String(inp.value || "").trim();
      if(!t) return;
      inp.value = ""; send.disabled = true;
      const um = el("div", "aim u", t); log.appendChild(um);
      const ty = el("div", "aim a typ", "…"); log.appendChild(ty);
      log.scrollTop = log.scrollHeight;
      if(ST.preview){ await new Promise(r => setTimeout(r, 600)); ty.remove(); log.appendChild(el("div", "aim a", "این یک پاسخ نمونه است؛ بعد از انتشار، دستیار واقعی همین‌جا جواب می‌دهد.")); send.disabled = false; return; }
      try{
        const r = await api("/rt/" + BOT_ID + "/act", {h: b.id, text: t});
        ty.remove();
        log.appendChild(el("div", "aim a", r.reply || "جوابی نیامد."));
      }catch(e){ ty.remove(); log.appendChild(el("div", "aim a", e.message || "الان نتونستم جواب بدم.")); }
      finally{ send.disabled = false; log.scrollTop = log.scrollHeight; }
    }
    send.addEventListener("click", ask);
    inp.addEventListener("keydown", e => { if(e.key === "Enter") ask(); });
    trail.appendChild(inp); trail.appendChild(send);
    w.appendChild(log); w.appendChild(trail);
    return w;
  },
  links(b){
    const w = el("div", "blk lbox");
    (b.items || []).forEach(it => {
      const a = el("button", "lnk");
      a.appendChild(el("span", "", fill(it.label || "")));
      a.insertAdjacentHTML("beforeend", svg('<path d="M14 4h6v6M20 4l-9 9M10 6H6.5A2.5 2.5 0 0 0 4 8.5v9A2.5 2.5 0 0 0 6.5 20h9a2.5 2.5 0 0 0 2.5-2.5V14"/>'));
      a.addEventListener("click", () => { haptic(); openUrl(it.url || ""); });
      w.appendChild(a);
    });
    return w;
  },
  divider(){ return el("div", "blk divider"); },
  spacer(b){ const s = el("div", "blk spacer"); s.style.height = (Math.max(8, Math.min(80, +b.h || 16))) + "px"; return s; },

  /* ═════════ مرکز بازی (همه‌ی شانس و امتیاز سمت سرور؛ اینجا فقط نمایش) ═════════ */
  games(b){
    const w = el("div", "blk gm");
    if(ST.preview){ w.innerHTML = `<div class="gm-top"><b>🎮 مرکز بازی</b><small>پیش‌نمایش</small></div>`; return w; }
    w.innerHTML = `<p class="mut">در حال آماده‌سازی بازی‌ها…</p>`;
    api("/rt/" + BOT_ID + "/game/boot", {}).then(d => { ST.gm = d; gmHome(w); })
      .catch(() => { w.innerHTML = `<p class="mut">بازی‌ها الان در دسترس نیست.</p>`; });
    return w;
  },
  wallet(b){
    const w = el("div", "blk gm");
    if(ST.preview){ w.innerHTML = `<div class="gm-top"><b>🪙 ۱۲۳</b><small>کیف سکه</small></div>`; return w; }
    w.innerHTML = `<p class="mut">…</p>`;
    api("/rt/" + BOT_ID + "/game/boot", {}).then(d => gmWallet(w, d)).catch(() => { w.innerHTML = `<p class="mut">فعلاً در دسترس نیست.</p>`; });
    return w;
  },
  gamesboard(b){
    const w = el("div", "blk gm gm-board");
    if(ST.preview){ w.innerHTML = `<div class="gm-q">🏆 برترین‌های بازی‌ها</div>`; return w; }
    gmBoard(w, b.game || "quiz", "d");
    return w;
  },
  shopcoins(b){
    const w = el("div", "blk gm");
    if(ST.preview){ w.innerHTML = `<div class="gm-q">🛍 فروشگاه سکه‌ای</div>`; return w; }
    w.innerHTML = `<p class="mut">…</p>`;
    api("/rt/" + BOT_ID + "/game/boot", {}).then(d => gmShop(w, d)).catch(() => { w.innerHTML = `<p class="mut">فعلاً در دسترس نیست.</p>`; });
    return w;
  },
};

/* ── اجزای مرکز بازی: هر بازی UI خودش را دارد و نتیجه را سرور می‌سنجد ── */
function gmCoins(){ return (ST.gm || {}).coins || 0; }
function gmHead(t, sub){
  const d = el("div", "gm-top");
  d.appendChild(el("b", "", "🪙 " + fd(gmCoins())));
  d.appendChild(el("small", "", sub || ""));
  return d;
}
function gmHome(w){
  const d = ST.gm;
  if(!d) return;
  w.innerHTML = "";
  w.appendChild(gmHead("coins", "مرکز بازی"));
  const daily = el("button", "gm-btn");
  daily.textContent = d.daily.done ? `🎁 امروز گرفتی (استریک ${fd(d.daily.streak)} روز)` : `🎁 سکه‌ی روزانه +${fd(d.daily.next)}`;
  daily.disabled = !!d.daily.done;
  daily.addEventListener("click", async () => {
    daily.disabled = true;
    try{
      const r = await api("/rt/" + BOT_ID + "/game/daily", {});
      ST.gm.coins = r.coins; ST.gm.daily.done = true; ST.gm.daily.streak = r.streak;
      haptic(true); toast("+" + fd(r.gain) + " سکه!");
      gmHome(w);
    }catch(e){ toast(e.message || "انجام نشد"); daily.disabled = false; }
  });
  w.appendChild(daily);
  const gr = el("div", "gm-grid");
  (d.games || []).forEach(g => {
    const c = el("button", "gm-card");
    c.appendChild(el("b", "", g.icon + " " + g.fa));
    c.appendChild(el("small", "", "رکورد تو: " + fd(g.best || 0)));
    c.addEventListener("click", () => gmPlay(w, g.k, g.fa));
    gr.appendChild(c);
  });
  w.appendChild(gr);
  const bar = el("div", "gm-grid");
  const bd = el("button", "gm-card"); bd.appendChild(el("b", "", "🏆 رتبه‌ها"));
  bd.addEventListener("click", () => gmBoard(w, ((d.games || [])[0] || {}).k || "quiz", "d"));
  const sh = el("button", "gm-card"); sh.appendChild(el("b", "", "🛍 فروشگاه"));
  sh.addEventListener("click", () => gmShop(w, d));
  bar.appendChild(bd); bar.appendChild(sh);
  w.appendChild(bar);
}
function gmWallet(w, d){
  w.innerHTML = "";
  w.appendChild(gmHead("coins", "کیف سکه"));
  const box = el("div", "gm-q");
  box.appendChild(el("div", "gm-num", fd(d.coins)));
  box.appendChild(el("div", "mut", (d.coin || "سکه") + " مجازی؛ مخصوص بازی‌های همین ربات و بدون ارزش پولی"));
  w.appendChild(box);
  const daily = el("button", "gm-btn");
  daily.textContent = d.daily.done ? "🎁 امروز گرفتی" : `🎁 سکه‌ی روزانه +${fd(d.daily.next)}`;
  daily.disabled = !!d.daily.done;
  daily.addEventListener("click", async () => {
    try{
      const r = await api("/rt/" + BOT_ID + "/game/daily", {});
      haptic(true); toast("+" + fd(r.gain) + " سکه!");
      d.coins = r.coins; d.daily.done = true; gmWallet(w, d);
    }catch(e){ toast(e.message || "انجام نشد"); }
  });
  w.appendChild(daily);
}
function gmBoard(w, g, p){
  w.innerHTML = "";
  const tabs = el("div", "gm-tab");
  [["d", "امروز"], ["w", "هفته"], ["m", "فصل"]].forEach(([k, l]) => {
    const t = el("button", k === p ? "on" : "", l);
    t.addEventListener("click", () => gmBoard(w, g, k));
    tabs.appendChild(t);
  });
  w.appendChild(tabs);
  w.appendChild(el("div", "mut", "…"));
  api("/rt/" + BOT_ID + "/game/board?p=" + p + "&g=" + encodeURIComponent(g), null).then(d => {
    w.innerHTML = "";
    w.appendChild(tabs);
    const box = el("div", "gm-q");
    box.appendChild(el("b", "", "🏆 " + d.label));
    if(!(d.rows || []).length) box.appendChild(el("div", "mut", "هنوز رکوردی نیست؛ اولین نفر باش!"));
    (d.rows || []).forEach((r, i) => {
      const tr = el("div", "tr");
      tr.appendChild(el("span", "", ["🥇", "🥈", "🥉"][i] || fd(i + 1)));
      tr.appendChild(el("b", "", r.nm));
      tr.appendChild(el("span", "n", fd(r.n)));
      box.appendChild(tr);
    });
    w.appendChild(box);
    const back = el("button", "gm-back", "↩ برگشت به بازی‌ها");
    back.addEventListener("click", () => { if(ST.gm) gmHome(w); else render(ST.screen, true); });
    w.appendChild(back);
  }).catch(() => { w.innerHTML = `<p class="mut">رتبه‌ها باز نشد.</p>`; });
}
function gmShop(w, d){
  w.innerHTML = "";
  w.appendChild(gmHead("coins", "فروشگاه"));
  if(!(d.shop || []).length) w.appendChild(el("div", "gm-q", "فروشگاه هنوز خالی است."));
  (d.shop || []).forEach(it => {
    const r = el("div", "gm-row");
    const t = el("div");
    t.appendChild(el("b", "", it.title));
    t.appendChild(el("div", "mut", fd(it.price) + " " + (d.coin || "سکه") + (it.have ? ` · داری: ${fd(it.have)}` : "")));
    r.appendChild(t);
    const buy = el("button", "gm-btn", "خرید");
    buy.style.minWidth = "74px";
    buy.addEventListener("click", async () => {
      buy.disabled = true;
      try{
        const r2 = await api("/rt/" + BOT_ID + "/game/buy", {id: it.id});
        ST.gm.coins = r2.coins; it.have = (it.have || 0) + 1;
        haptic(true); toast("«" + it.title + "» خریدی!");
        gmShop(w, d);
      }catch(e){ toast(e.message || "نشد"); buy.disabled = false; }
    });
    r.appendChild(buy);
    w.appendChild(r);
  });
  const back = el("button", "gm-back", "↩ برگشت");
  back.addEventListener("click", () => { if(ST.gm) gmHome(w); else render(ST.screen, true); });
  w.appendChild(back);
}
function gmPlay(w, g, fa){
  w.innerHTML = "";
  const back = el("button", "gm-back", "↩ برگشت به بازی‌ها");
  back.addEventListener("click", () => { gmHome(w); });
  w.appendChild(back);
  const title = el("div", "gm-q");
  title.appendChild(el("b", "", fa));
  title.appendChild(el("div", "mut", "…"));
  w.appendChild(title);
  api("/rt/" + BOT_ID + "/game/start", {game: g}).then(d => {
    title.innerHTML = "";
    if(d.error){ title.appendChild(el("div", "mut", d.error)); return; }
    const st = d.st || {};
    const fn = {quiz: gmQuiz, memory: gmMemory, tap: gmTap, wheel: gmWheel, word: gmText, math: gmText, typing: gmText, puzzle: gmPuzzle}[g];
    if(fn) w.appendChild(fn(w, g, st));
    else title.appendChild(el("div", "mut", "این بازی فعلاً اینجا کار نمی‌کند؛ از داخل گروه با /play امتحان کن."));
  }).catch(e => { title.innerHTML = ""; title.appendChild(el("div", "mut", e.message || "باز نشد")); });
}
function gmResultNote(w, gain){
  const d = el("div", "gm-q");
  d.appendChild(el("div", "gm-num", "+" + fd(gain) + " 🪙"));
  const b = el("button", "gm-btn", "برگشت به بازی‌ها");
  b.addEventListener("click", () => { render(ST.screen, true); gmHome(w); });
  d.appendChild(b);
  haptic(true);
  render(ST.screen, true);
  return d;
}
function gmQuiz(w, g, st){
  const box = el("div", "gm");
  const q = el("div", "gm-q");
  const opts = el("div", "gm-opts");
  box.appendChild(q); box.appendChild(opts);
  let cur = st, done = false, sc = 0;
  const qs = (function(){ const a = []; (function collect(s){ if(s) a.push(s); })(st); return a; })();
  const answers = [];
  function paint(){
    q.textContent = "";
    q.appendChild(el("div", "mut", `سؤال ${fd((cur.i || 0) + 1)} از ${fd(cur.total || 4)}`));
    q.appendChild(el("div", "", cur.q || ""));
    opts.innerHTML = "";
    answers[cur.i] = null;
    (cur.opts || []).forEach((o, i) => {
      const b = el("button", "gm-opt", o);
      b.addEventListener("click", async () => {
        if(done) return;
        done = true;
        answers[cur.i] = i;
        try{
          const r = await api("/rt/" + BOT_ID + "/game/act", {game: "quiz", i: cur.i, pick: i,
            st: {score: sc, qs: (function(){ const out = []; for(let k = 0; k <= (cur.i || 0); k++) out.push([null, null, answers[k]]); return out; })()}});
          sc = r.score != null ? r.score : sc;
          if(r.done){ box.appendChild(gmResultNote(w, r.gain)); return; }
          cur = r.st; done = false; paint();
        }catch(e){ toast(e.message || "خطا"); done = false; }
      });
      opts.appendChild(b);
    });
  }
  paint();
  return box;
}
function gmMemory(w, g, st){
  const box = el("div", "gm");
  const info = el("div", "gm-q", "جفت‌های یکسان را پیدا کن!");
  const grid = el("div", "gm-grid3");
  box.appendChild(info); box.appendChild(grid);
  const emo = ["🍎", "🚀", "🐱", "⚽", "🎲", "🌈"];
  const pool = [];
  for(let i = 0; i < 6; i++){ pool.push(i, i); }
  pool.sort(() => Math.random() - .5);
  const cards = pool.map(i => ({e: emo[i], up: false, done: false}));
  let open = [], found = 0, moves = 0, lock = false;
  function paint(){
    grid.innerHTML = "";
    cards.forEach((c, i) => {
      const b = el("button", "gm-cell", c.up || c.done ? c.e : "🂠");
      b.addEventListener("click", async () => {
        if(lock || c.up || c.done) return;
        c.up = true; open.push(i); paint();
        if(open.length === 2){
          moves++; lock = true;
          const a = open[0], b2 = open[1];
          if(cards[a].e === cards[b2].e){
            cards[a].done = cards[b2].done = true; found++;
            open = []; lock = false; paint();
            if(found === 6){
              try{
                const r = await api("/rt/" + BOT_ID + "/game/act", {game: "memory", moves, pairs: 6});
                if(r.done) box.appendChild(gmResultNote(w, r.gain));
              }catch(e){ toast(e.message); }
            }
          }else{
            setTimeout(() => { cards[a].up = cards[b2].up = false; open = []; lock = false; paint(); }, 650);
          }
        }
      });
      grid.appendChild(b);
    });
  }
  paint();
  return box;
}
function gmTap(w, g, st){
  const box = el("div", "gm");
  const num = el("div", "gm-num", fd(0));
  const left = el("div", "mut", fd(st.secs || 10) + " ثانیه");
  const btn = el("button", "gm-tap", "⚡ بزن!");
  box.appendChild(num); box.appendChild(left); box.appendChild(btn);
  let over = false;
  btn.addEventListener("click", async () => {
    if(over) return;
    try{
      const r = await api("/rt/" + BOT_ID + "/game/act", {game: "tap"});
      if(r.done){ over = true; num.textContent = fd(r.n); left.textContent = "تمام شد!"; box.appendChild(gmResultNote(w, r.gain)); return; }
      num.textContent = fd(r.n); left.textContent = fd(r.left) + " ثانیه";
    }catch(e){ over = true; toast(e.message || "تمام شد"); }
  });
  return box;
}
function gmWheel(w, g, st){
  const box = el("div", "gm");
  const wh = el("div", "gm-wheel");
  const txt = el("div", "gm-q", "گردونه می‌چرخد…");
  box.appendChild(wh); box.appendChild(txt);
  requestAnimationFrame(() => {
    const base = 1440 + (360 - ((st.i || 0) * 45) - 22);
    wh.style.transform = `rotate(${base}deg)`;
  });
  setTimeout(() => { txt.textContent = "🎯 جایزه: +" + fd(st.gain || 0) + " سکه"; }, 2700);
  return box;
}
function gmText(w, g, st){
  const box = el("div", "gm");
  const q = el("div", "gm-q");
  if(g === "word") q.appendChild(el("div", "", "🔤 " + (st.letters || []).join("، ")));
  if(g === "math") q.appendChild(el("div", "", `➗ ${fd(st.a)} ${st.op} ${fd(st.b)} = ؟`));
  if(g === "typing") q.appendChild(el("blockquote", "", st.line || ""));
  const row = el("div", "gm-in");
  const inp = el("input");
  inp.placeholder = g === "typing" ? "همین جمله را تایپ کن…" : "جواب…";
  inp.setAttribute("aria-label", "پاسخ");
  const go = el("button", "gm-btn", "فرست");
  row.appendChild(inp); row.appendChild(go);
  box.appendChild(q); box.appendChild(row);
  const send = async () => {
    const v = (inp.value || "").trim();
    if(!v) return;
    go.disabled = true;
    try{
      const r = await api("/rt/" + BOT_ID + "/game/act", {game: g, text: v});
      if(!r.ok){ q.appendChild(el("div", "bad", "❌ درست نبود؛ جواب: " + r.answer)); return; }
      box.appendChild(gmResultNote(w, r.gain));
    }catch(e){ toast(e.message || "خطا"); go.disabled = false; }
  };
  go.addEventListener("click", send);
  inp.addEventListener("keydown", e => { if(e.key === "Enter") send(); });
  return box;
}
function gmPuzzle(w, g, st){
  const box = el("div", "gm");
  const info = el("div", "mut", "۱ تا ۸ را به ترتیب بچین");
  const grid = el("div", "gm-grid3");
  box.appendChild(info); box.appendChild(grid);
  let nums = (st.nums || []).slice(), moves = 0, won = false;
  function paint(){
    grid.innerHTML = "";
    nums.forEach((n, i) => {
      const c = el("button", "gm-cell", n ? fd(n) : "⬜");
      c.addEventListener("click", async () => {
        if(won) return;
        const zi = nums.indexOf(0);
        const adj = [zi - 1, zi + 1, zi - 3, zi + 3].filter(j => j >= 0 && j < 9 &&
          !(Math.abs(zi - j) === 1 && (zi % 3 === 0 ? j === zi - 1 : (j % 3 === 0 && j === zi + 1))));
        if(!adj.includes(i)) return;
        [nums[zi], nums[i]] = [nums[i], nums[zi]];
        moves++;
        paint();
        if(nums.slice(0, 8).every((x, k) => x === k + 1)){
          won = true;
          try{
            const r = await api("/rt/" + BOT_ID + "/game/act", {game: "puzzle", moves, done: true});
            if(r.done) box.appendChild(gmResultNote(w, r.gain));
          }catch(e){ toast(e.message); }
        }
      });
      grid.appendChild(c);
    });
  }
  paint();
  return box;
}

/* ═════════════════ بلوک‌های نسل ۲: خانواده‌های مشترک (فهرست‌ها، رسانه، فروش، داده) ═════════════════ */
const HUE = i => ["#3CCFE3", "#6C5CE7", "#47D79B", "#FFC24A", "#FF7B88", "#5B8DEF"][i % 6];
function reducedMotion(){ return matchMedia("(prefers-reduced-motion:reduce)").matches; }
function fill2(t){ return fill(t); }
function openMediaFull(src){
  const ov = el("div", "storov");
  const im = el("img"); im.src = src; im.alt = "";
  const x = el("button", "storx", "×");
  x.addEventListener("click", () => ov.remove());
  ov.appendChild(im); ov.appendChild(x);
  ov.addEventListener("click", e => { if(e.target === ov) ov.remove(); });
  document.body.appendChild(ov);
}
function itemsList(b, cls, renderItem){
  const w = el("div", "blk " + cls);
  (b.items || []).forEach((it, i) => {
    try{ w.appendChild(renderItem(it, i)); }catch(e){ /* یک آیتم خراب بقیه را نمی‌شکند */ }
  });
  return w;
}
function iconOf(ic){ return el("span", "bic", ic || "•"); }
function stars(n){
  const v = Math.max(0, Math.min(5, parseInt(n) || 0));
  return el("span", "stars", "★".repeat(v) + "☆".repeat(5 - v));
}
Object.assign(BLOCKS, {

  /* ── متن و محتوا ── */
  accordion(b){
    return itemsList(b, "acrd", (it) => {
      const f = el("div", "faqi");
      const q = el("button", "q");
      q.appendChild(el("span", "", fill2(it.t || "")));
      const a = el("div", "a");
      a.innerHTML = rich(fill2(it.d || ""));
      q.addEventListener("click", () => { f.classList.toggle("open"); haptic(); });
      f.appendChild(q); f.appendChild(a);
      return f;
    });
  },
  tabs(b){
    const w = el("div", "blk tbx");
    const bar = el("div", "tbbar");
    const panes = el("div");
    (b.items || []).forEach((it, i) => {
      const t = el("button", "tbt" + (i === 0 ? " on" : ""), fill2(it.t || ""));
      t.addEventListener("click", () => { [...bar.children].forEach((x, k) => x.classList.toggle("on", k === i)); [...panes.children].forEach((x, k) => x.hidden = k !== i); haptic(); });
      bar.appendChild(t);
      const p = el("div", "tbpane");
      p.innerHTML = rich(fill2(it.d || ""));
      p.hidden = i !== 0;
      panes.appendChild(p);
    });
    w.appendChild(bar); w.appendChild(panes);
    return w;
  },
  steps(b){
    return itemsList(b, "stp", (it, i) => {
      const r = el("div", "stpr");
      r.appendChild(el("span", "stpn", fd(i + 1)));
      const d = el("div");
      d.appendChild(el("b", "", fill2(it.t || "")));
      if(it.d) d.appendChild(el("div", "mut", fill2(it.d)));
      r.appendChild(d);
      return r;
    });
  },
  timeline(b){
    return itemsList(b, "tln", (it) => {
      const r = el("div", "tlnr");
      r.appendChild(el("i"));
      const d = el("div");
      d.appendChild(el("b", "", fill2(it.t || "")));
      if(it.d) d.appendChild(el("div", "mut", fill2(it.d)));
      r.appendChild(d);
      return r;
    });
  },
  quote(b){
    const w = el("div", "blk qt");
    const q = el("blockquote");
    q.innerHTML = rich(fill2(b.text || ""));
    w.appendChild(q);
    if(b.by) w.appendChild(el("div", "mut qby", "— " + fill2(b.by)));
    return w;
  },
  tags(b){
    const w = el("div", "blk tags");
    (b.items || []).forEach(it => w.appendChild(el("span", "tagc", fill2(it.t || ""))));
    return w;
  },
  table(b){
    const w = el("div", "blk tblw card");
    const t = el("table", "tbl");
    const tr = el("tr");
    (b.head || []).forEach(h => tr.appendChild(el("th", "", fill2(h))));
    t.appendChild(tr);
    (b.rows || []).forEach(r => {
      const row = el("tr");
      r.forEach(c => row.appendChild(el("td", "", fill2(c))));
      t.appendChild(row);
    });
    w.appendChild(t);
    return w;
  },
  copytext(b){
    const w = el("div", "blk cpy card");
    const code = el("code", "", fill2(b.text || ""));
    const bt = el("button", "cpyb", "📋 کپی");
    bt.addEventListener("click", () => { try{ navigator.clipboard?.writeText(b.text || ""); }catch(_){} toast("کپی شد"); haptic(); });
    w.appendChild(code); w.appendChild(bt);
    return w;
  },
  article(b){
    const w = el("div", "blk art card");
    if(b.title) w.appendChild(el("h3", "", fill2(b.title)));
    const p = el("div", "txt");
    p.innerHTML = rich(fill2(b.text || ""));
    w.appendChild(p);
    return w;
  },
  heading(b){
    const w = el("div", "blk hdg");
    w.appendChild(el("h2", "hdgh s" + (b.size || 1), fill2(b.text || "")));
    return w;
  },
  bullets(b){
    const w = el("div", "blk blt card");
    const ul = el("ul");
    (b.items || []).forEach(it => ul.appendChild(el("li", "", fill2(it.t || ""))));
    w.appendChild(ul);
    return w;
  },
  numberlist(b){
    return itemsList(b, "nls card", (it, i) => {
      const r = el("div", "nlr");
      r.appendChild(el("span", "nl n", fd(i + 1)));
      r.appendChild(el("span", "", fill2(it.t || "")));
      return r;
    });
  },
  marquee(b){
    const w = el("div", "blk mrq");
    w.appendChild(el("div", "mrqi", fill2(b.text || "") + "　　" + fill2(b.text || "")));
    return w;
  },
  consent(b){
    const w = el("div", "blk cns card");
    const p = el("div", "txt");
    p.innerHTML = rich(fill2(b.text || ""));
    w.appendChild(p);
    const lab = el("label", "chk");
    const cb = el("input"); cb.type = "checkbox";
    lab.appendChild(cb);
    lab.appendChild(document.createTextNode(fill2(b.label || "می‌پذیرم")));
    w.appendChild(lab);
    if(b.hid && (b.do || []).length){
      const bt = el("button", "cta", "ادامه");
      bt.disabled = true;
      cb.addEventListener("change", () => { bt.disabled = !cb.checked; });
      bt.addEventListener("click", () => { if(cb.checked){ haptic(); runDo(b.do, b.hid); } });
      w.appendChild(bt);
    }
    return w;
  },

  /* ── رسانه ── */
  slider(b){
    const w = el("div", "blk slr");
    const strip = el("div", "slri");
    const srcs = [];
    (b.items || []).forEach(it => {
      const src = mediaSrc(it);
      if(!src) return;
      srcs.push(src);
      const c = el("div", "slrc");
      const im = el("img"); im.loading = "lazy"; im.alt = ""; im.src = src;
      im.addEventListener("click", () => openMediaFull(src));
      c.appendChild(im);
      if(it.label) c.appendChild(el("span", "slrl", fill2(it.label)));
      strip.appendChild(c);
    });
    w.appendChild(strip);
    if(srcs.length > 1){
      const dots = el("div", "slrd");
      srcs.forEach((_, i) => dots.appendChild(el("i", i === 0 ? "on" : "")));
      w.appendChild(dots);
      strip.addEventListener("scroll", () => {
        const i = Math.round(strip.scrollLeft / Math.max(1, strip.clientWidth));
        [...dots.children].forEach((d, k) => d.classList.toggle("on", k === Math.min(srcs.length - 1, i)));
      }, {passive: true});
      if(b.auto && !reducedMotion()){
        ST.timers[b.id] = setInterval(() => {
          const nx = (Math.round(strip.scrollLeft / Math.max(1, strip.clientWidth)) + 1) % srcs.length;
          strip.scrollTo({left: nx * strip.clientWidth, behavior: "smooth"});
        }, 4200);
      }
    }
    return w;
  },
  stories(b){
    const w = el("div", "blk str");
    (b.items || []).forEach(it => {
      const src = mediaSrc(it);
      if(!src) return;
      const c = el("button", "strc");
      const im = el("img"); im.loading = "lazy"; im.alt = ""; im.src = src;
      c.appendChild(im);
      if(it.label) c.appendChild(el("span", "", fill2(it.label)));
      c.addEventListener("click", () => { haptic(); openMediaFull(src); });
      w.appendChild(c);
    });
    return w;
  },
  logos(b){
    const w = el("div", "blk lgs");
    (b.items || []).forEach(it => {
      const src = mediaSrc(it);
      if(!src) return;
      const im = el("img"); im.loading = "lazy"; im.alt = ""; im.src = src;
      w.appendChild(im);
    });
    return w;
  },
  before_after(b){
    const sa = mediaSrc(b);
    const sb = b.media2 ? (ST.media[b.media2] || {}).url : (/^https:\/\//.test(b.url2 || "") ? b.url2 : "");
    if(!sa || !sb) return document.createDocumentFragment();
    const w = el("div", "blk bfa card");
    const box = el("div", "bfab");
    const im2 = el("img"); im2.src = sb; im2.alt = "";
    const im1 = el("img"); im1.src = sa; im1.alt = "";
    im1.style.clipPath = "inset(0 0 0 50%)";
    box.appendChild(im2); box.appendChild(im1);
    const rng = el("input"); rng.type = "range"; rng.min = 0; rng.max = 100; rng.value = 50;
    rng.setAttribute("aria-label", "مقایسه‌ی قبل و بعد");
    rng.addEventListener("input", () => { im1.style.clipPath = "inset(0 0 0 " + rng.value + "%)"; });
    w.appendChild(box); w.appendChild(rng);
    const lab = el("div", "bfal");
    lab.appendChild(el("span", "", b.la || "قبل"));
    lab.appendChild(el("span", "", b.lb || "بعد"));
    w.appendChild(lab);
    return w;
  },
  imagegrid(b){
    const w = el("div", "blk img");
    (b.items || []).forEach(it => {
      const src = mediaSrc(it);
      if(!src) return;
      const im = el("img"); im.loading = "lazy"; im.alt = ""; im.src = src;
      im.addEventListener("click", () => openMediaFull(src));
      w.appendChild(im);
    });
    return w;
  },
  file(b){
    const src = mediaSrc(b);
    if(!src) return document.createDocumentFragment();
    const w = el("div", "blk fls");
    const a = el("button", "lnk");
    a.appendChild(el("span", "", fill2(b.label || "دانلود فایل")));
    a.insertAdjacentHTML("beforeend", svg('<path d="M12 4v11M8 11l4 4 4-4M5 19h14"/>'));
    a.addEventListener("click", () => { haptic(); openUrl(src); });
    w.appendChild(a);
    return w;
  },
  player(b){
    const src = mediaSrc(b);
    if(!src) return document.createDocumentFragment();
    const w = el("div", "blk ply card");
    w.appendChild(el("b", "", fill2(b.title || "پخش")));
    if(b.by) w.appendChild(el("div", "mut", fill2(b.by)));
    const a = el("audio"); a.controls = true; a.preload = "none"; a.src = src;
    w.appendChild(a);
    return w;
  },

  /* ── دکمه و ناوبری ── */
  floatbtn(b){
    const w = el("div", "blk flt");
    const bt = el("button", "fltb", fill2(b.text || ""));
    if(b.hid) bt.addEventListener("click", () => { haptic(); runDo(b.do, b.hid); });
    w.appendChild(bt);
    return w;
  },
  quicklinks(b){
    return itemsList(b, "qlk", (it) => {
      const c = el("button", "qlkc");
      if(it.ic) c.appendChild(iconOf(it.ic));
      c.appendChild(el("b", "", fill2(it.t || "")));
      if(it.do && it.hid) c.addEventListener("click", () => { haptic(); runDo(it.do, it.hid); });
      else if(it.url) c.addEventListener("click", () => { haptic(); openUrl(it.url); });
      return c;
    });
  },
  gridmenu(b){
    return itemsList(b, "grm", (it) => {
      const c = el("button", "grmc");
      c.appendChild(iconOf(it.ic || "⭐"));
      c.appendChild(el("span", "", fill2(it.t || "")));
      if(it.do && it.hid) c.addEventListener("click", () => { haptic(); runDo(it.do, it.hid); });
      else if(it.url) c.addEventListener("click", () => { haptic(); openUrl(it.url); });
      return c;
    });
  },
  searchbar(b){
    const w = el("div", "blk srb card");
    const inp = el("input");
    inp.placeholder = "جستجو…"; inp.setAttribute("aria-label", "جستجو");
    const res = el("div", "srbr");
    const paint = (q) => {
      res.innerHTML = "";
      const list = (b.items || []).filter(it => !q || String(it.t || "").toLowerCase().includes(q));
      if(!list.length){ res.appendChild(el("div", "mut", "چیزی پیدا نشد.")); return; }
      list.slice(0, 20).forEach(it => {
        const r = el("div", "qlkc");
        r.appendChild(el("b", "", fill2(it.t || "")));
        if(it.d) r.appendChild(el("div", "mut", fill2(it.d)));
        res.appendChild(r);
      });
    };
    inp.addEventListener("input", () => paint(inp.value.trim().toLowerCase()));
    w.appendChild(inp); w.appendChild(res);
    paint("");
    return w;
  },

  /* ── فروش ── */
  product(b){
    const w = el("div", "blk prd card");
    const src = mediaSrc(b);
    if(src){ const im = el("img", "prdim"); im.loading = "lazy"; im.alt = ""; im.src = src; w.appendChild(im); }
    const inr = el("div", "prdin");
    const top = el("div", "prdt");
    top.appendChild(el("b", "", fill2(b.title || "")));
    if(b.badge) top.appendChild(el("span", "bdg2", fill2(b.badge)));
    inr.appendChild(top);
    if(b.text) inr.appendChild(el("div", "mut", fill2(b.text)));
    const pr = el("div", "pric");
    pr.appendChild(el("b", "n", fill2(b.price || "")));
    if(b.old) pr.appendChild(el("s", "n", fill2(b.old)));
    inr.appendChild(pr);
    if(b.btn && b.hid){
      const bt = el("button", "cta", fill2(b.btn));
      bt.addEventListener("click", () => { haptic(); runDo(b.do, b.hid); });
      inr.appendChild(bt);
    }
    w.appendChild(inr);
    return w;
  },
  catalog(b){
    const w = el("div", "blk cat card");
    const tags = [...new Set((b.items || []).map(x => x.tag).filter(Boolean))];
    const bar = el("div", "tagbar");
    let cur = "";
    const grid = el("div", "catg");
    const paint = () => {
      grid.innerHTML = "";
      (b.items || []).filter(x => !cur || x.tag === cur).forEach(x => {
        const c = el("div", "catc");
        const src = x.media && ST.media[x.media] ? ST.media[x.media].url : "";
        if(src){ const im = el("img"); im.loading = "lazy"; im.alt = ""; im.src = src; c.appendChild(im); }
        c.appendChild(el("b", "", fill2(x.t || "")));
        if(x.price) c.appendChild(el("span", "n pric2", fill2(x.price)));
        if(x.text) c.appendChild(el("div", "mut", fill2(x.text)));
        grid.appendChild(c);
      });
      if(!grid.children.length) grid.appendChild(el("div", "mut", "چیزی در این دسته نیست."));
    };
    if(tags.length){
      const all = el("button", "chip on", "همه");
      all.addEventListener("click", () => { cur = ""; [...bar.children].forEach(x => x.classList.remove("on")); all.classList.add("on"); paint(); });
      bar.appendChild(all);
      tags.forEach(tg2 => {
        const t = el("button", "chip", fill2(tg2));
        t.addEventListener("click", () => { cur = tg2; [...bar.children].forEach(x => x.classList.remove("on")); t.classList.add("on"); paint(); haptic(); });
        bar.appendChild(t);
      });
      w.appendChild(bar);
    }
    w.appendChild(grid);
    paint();
    return w;
  },
  cart(b){
    const w = el("div", "blk crt card");
    w.appendChild(el("b", "", "🛒 سبد خرید"));
    const rows = el("div", "crtr");
    const qty = {};
    const num = s => { const x = parseFloat(String(s).replace(/[^\d.]/g, "")); return isNaN(x) ? 0 : x; };
    const total = el("div", "crts");
    const paint = () => {
      let sum = 0;
      (b.items || []).forEach((it, i) => { sum += num(it.price) * (qty[i] || 0); });
      total.innerHTML = "";
      total.appendChild(el("span", "", "جمع: "));
      total.appendChild(el("b", "n", fd(sum.toLocaleString("en-US")) + " " + fill2(b.cur || "تومان")));
    };
    (b.items || []).forEach((it, i) => {
      const r = el("div", "crtrw");
      r.appendChild(el("b", "", fill2(it.t || "")));
      const ops = el("div", "crtq");
      const minus = el("button", "qbtn", "−"), plus = el("button", "qbtn", "+");
      const q = el("span", "n qv", "۰");
      minus.addEventListener("click", () => { qty[i] = Math.max(0, (qty[i] || 0) - 1); q.textContent = fd(qty[i]); paint(); haptic(); });
      plus.addEventListener("click", () => { qty[i] = (qty[i] || 0) + 1; q.textContent = fd(qty[i]); paint(); haptic(); });
      ops.appendChild(minus); ops.appendChild(q); ops.appendChild(plus);
      r.appendChild(ops);
      r.appendChild(el("span", "n mut", fill2(it.price || "")));
      rows.appendChild(r);
    });
    w.appendChild(rows);
    w.appendChild(total);
    if(b.hid && (b.do || []).length){
      const bt = el("button", "cta", fill2(b.btn || "ثبت سفارش"));
      bt.addEventListener("click", () => { haptic(); runDo(b.do, b.hid); });
      w.appendChild(bt);
    }
    paint();
    return w;
  },
  pricing(b){
    const w = el("div", "blk prg");
    (b.items || []).forEach(it => {
      const c = el("div", "prgc" + (it.hi ? " hi" : ""));
      c.appendChild(el("b", "", fill2(it.t || "")));
      c.appendChild(el("div", "pric", fill2(it.price || "")));
      if(it.d) c.appendChild(el("div", "mut", fill2(it.d)));
      if(it.hid && (it.do || []).length){
        const bt = el("button", it.hi ? "cta" : "cta g", "انتخاب");
        bt.addEventListener("click", () => { haptic(); runDo(it.do, it.hid); });
        c.appendChild(bt);
      }
      w.appendChild(c);
    });
    return w;
  },
  discount(b){
    const w = el("div", "blk dsc card");
    const code = el("code", "", fill2(b.code || ""));
    const bt = el("button", "cpyb", "📋 کپی کد");
    bt.addEventListener("click", () => { try{ navigator.clipboard?.writeText(b.code || ""); }catch(_){} toast("کد کپی شد"); haptic(); });
    w.appendChild(code); w.appendChild(bt);
    if(b.text) w.appendChild(el("div", "mut", fill2(b.text)));
    return w;
  },
  invoice(b){
    const w = el("div", "blk inv card");
    w.appendChild(el("b", "", "🧾 فاکتور"));
    let sum = 0;
    const num = s => { const x = parseFloat(String(s).replace(/[^\d.]/g, "")); return isNaN(x) ? 0 : x; };
    (b.items || []).forEach(it => {
      const r = el("div", "invr");
      r.appendChild(el("span", "", fill2(it.t || "")));
      r.appendChild(el("span", "n", fill2(it.price || "")));
      sum += num(it.price);
      w.appendChild(r);
    });
    const t = el("div", "invr invt");
    t.appendChild(el("b", "", "جمع کل"));
    t.appendChild(el("b", "n", fd(sum.toLocaleString("en-US")) + " " + fill2(b.cur || "تومان")));
    w.appendChild(t);
    if(b.note) w.appendChild(el("div", "mut", fill2(b.note)));
    return w;
  },
  orders(b){
    const w = el("div", "blk ordr");
    if(ST.preview){ w.textContent = b.empty || "هنوز سفارشی نداری."; return w; }
    w.textContent = "…";
    api("/rt/" + BOT_ID + "/data?b=" + encodeURIComponent(b.id || ""))
      .then(d => { w.textContent = (d.items || []).length ? d.items.map(fd).join("\n") : (d.empty || "هنوز سفارشی نداری."); })
      .catch(() => { w.textContent = b.empty || "هنوز سفارشی نداری."; });
    return w;
  },

  /* ── داده و آمار ── */
  chart(b){
    const w = el("div", "blk chrt card");
    if(ST.preview){ w.textContent = (b.label || "نمودار") + " — از جدول داده"; return w; }
    w.textContent = "…";
    api("/rt/" + BOT_ID + "/data?b=" + encodeURIComponent(b.id || "")).then(d => {
      w.innerHTML = "";
      if(b.label) w.appendChild(el("b", "", fill2(b.label)));
      const rows = d.rows || [];
      if(!rows.length){ w.appendChild(el("div", "mut", "هنوز داده‌ای ثبت نشده.")); return; }
      const mx = Math.max(1, ...rows.map(r => Math.abs(r.n || 0)));
      if(d.kind === "donut"){
        const total = rows.reduce((a, r) => a + Math.abs(r.n || 0), 0) || 1;
        let acc = 0;
        const seg = rows.map(r => { const from = acc / total * 360; acc += Math.abs(r.n || 0); const to = acc / total * 360; return HUE(rows.indexOf(r)) + " " + from + "deg " + to + "deg"; }).join(",");
        const don = el("div", "chnut");
        don.style.background = "conic-gradient(" + seg + ", rgba(128,128,128,.15) 0)";
        w.appendChild(don);
      }else{
        const box = el("div", d.kind === "line" ? "chline" : "chbars");
        rows.forEach((r, ri) => {
          if(d.kind === "line"){
            const p = el("i");
            p.style.height = Math.max(4, Math.round(Math.abs(r.n || 0) / mx * 100)) + "%";
            p.title = r.k + ": " + r.n;
            box.appendChild(p);
          }else{
            const row = el("div", "chrow");
            row.appendChild(el("span", "chlab", r.k));
            const bar = el("div", "chbar");
            const bi = el("i");
            bi.style.width = Math.max(3, Math.round(Math.abs(r.n || 0) / mx * 100)) + "%";
            bi.style.background = HUE(ri);
            bar.appendChild(bi);
            row.appendChild(bar);
            row.appendChild(el("span", "n", fd(r.n)));
            box.appendChild(row);
          }
        });
        w.appendChild(box);
      }
      const leg = el("div", "chleg");
      rows.slice(0, 6).forEach((r, i) => {
        const l = el("span", "chlegi");
        if(d.kind === "donut"){ const di = el("i"); di.style.background = HUE(i); l.appendChild(di); }
        l.appendChild(document.createTextNode(r.k + " (" + fd(r.n) + ")"));
        leg.appendChild(l);
      });
      w.appendChild(leg);
    }).catch(() => { w.textContent = "نمودار باز نشد."; });
    return w;
  },
  progress(b){
    const w = el("div", "blk prg2 card");
    w.appendChild(el("div", "mut", b.label || ""));
    const bar = el("div", "pbar2");
    const fillEl = el("i");
    bar.appendChild(fillEl);
    w.appendChild(bar);
    const val = el("div", "n mut", "");
    w.appendChild(val);
    const v = parseFloat(String(varOf(b.var || "")).replace(/[^\d.-]/g, "")) || 0;
    const mx = +b.max || 100;
    fillEl.style.width = Math.max(0, Math.min(100, Math.round(v / mx * 100))) + "%";
    val.textContent = fd(v) + " از " + fd(mx);
    return w;
  },
  xpbar(b){
    const w = el("div", "blk xpb card");
    const per = +b.per || 100;
    const v = parseFloat(String(varOf(b.var || "")).replace(/[^\d.-]/g, "")) || 0;
    const lvl = Math.floor(v / per) + 1, inlvl = v % per;
    w.appendChild(el("div", "xph", (b.label || "سطح") + " " + fd(lvl)));
    const bar = el("div", "pbar2");
    const f = el("i"); f.style.width = Math.round(inlvl / per * 100) + "%";
    bar.appendChild(f);
    w.appendChild(bar);
    w.appendChild(el("div", "mut n", fd(per - inlvl) + " تا سطح بعد"));
    return w;
  },
  statrow(b){
    const w = el("div", "blk stw");
    (b.items || []).forEach(it => {
      const c = el("div", "stat card");
      c.appendChild(el("div", "mut", it.label || ""));
      c.appendChild(el("div", "sv", fd(fill2("{" + (it.var || "") + "|0}"))));
      w.appendChild(c);
    });
    return w;
  },
  countup(b){
    const w = el("div", "blk ctp card");
    w.appendChild(el("div", "mut", b.label || ""));
    const v = el("div", "sv", fd(0));
    w.appendChild(v);
    const target = parseFloat(String(varOf(b.var || "")).replace(/[^\d.-]/g, "")) || 0;
    if(reducedMotion()){ v.textContent = fd(target.toLocaleString("en-US")); return w; }
    const t0 = performance.now(), D = 1100;
    (function step(t){
      const x = Math.min(1, (t - t0) / D), e = 1 - Math.pow(1 - x, 3);
      v.textContent = fd(Math.round(target * e).toLocaleString("en-US"));
      if(x < 1 && v.isConnected) requestAnimationFrame(step);
    })(t0);
    return w;
  },
  events(b){
    return itemsList(b, "evt card", (it) => {
      const r = el("div", "evtr");
      if(it.date) r.appendChild(el("span", "evtd n", fill2(it.date)));
      const d = el("div");
      d.appendChild(el("b", "", fill2(it.t || "")));
      if(it.d) d.appendChild(el("div", "mut", fill2(it.d)));
      r.appendChild(d);
      return r;
    });
  },
  calendar(b){
    const w = el("div", "blk cal card");
    const now2 = new Date();
    const y = now2.getFullYear(), m = now2.getMonth();
    const byDate = {};
    (b.items || []).forEach(it => { if(it.date) byDate[String(it.date).slice(5)] = it; });
    try{ w.appendChild(el("b", "", fd(now2.toLocaleDateString("fa-IR-u-nu-latn", {month: "long", year: "numeric"})))); }catch(_){}
    const grid = el("div", "calg");
    ["ش", "ی", "د", "س", "چ", "پ", "ج"].forEach(d => grid.appendChild(el("span", "calh", d)));
    const first = (new Date(y, m, 1).getDay() + 1) % 7;   // شنبه = ۰
    const days = new Date(y, m + 1, 0).getDate();
    for(let i = 0; i < first; i++) grid.appendChild(el("span"));
    for(let d = 1; d <= days; d++){
      const c = el("span", "cald" + (d === now2.getDate() ? " today" : ""), fd(d));
      const key = String(m + 1).padStart(2, "0") + "/" + String(d).padStart(2, "0");
      if(byDate[key]){ c.classList.add("has"); c.title = byDate[key].t || ""; }
      grid.appendChild(c);
    }
    w.appendChild(grid);
    if((b.items || []).length){
      const list = el("div", "call");
      (b.items || []).slice(0, 5).forEach(it => {
        const r = el("div", "evtr");
        if(it.date) r.appendChild(el("span", "evtd n", fill2(it.date)));
        r.appendChild(el("b", "", fill2(it.t || "")));
        list.appendChild(r);
      });
      w.appendChild(list);
    }
    return w;
  },
  inbox(b){
    const w = el("div", "blk inb card");
    w.appendChild(el("b", "", "📥 پاسخ‌های اخیر"));
    const box = el("div");
    w.appendChild(box);
    if(ST.preview){ box.textContent = "فقط برای صاحب ربات."; return w; }
    box.textContent = "…";
    api("/rt/" + BOT_ID + "/data?b=" + encodeURIComponent(b.id || "")).then(d => {
      box.innerHTML = "";
      if(!(d.items || []).length){ box.textContent = d.empty || "هنوز پاسخی ثبت نشده."; return; }
      d.items.forEach(it => {
        const r = el("div", "inbr");
        r.appendChild(el("b", "", it.t || ""));
        r.appendChild(el("div", "mut", it.d || ""));
        box.appendChild(r);
      });
    }).catch(() => { box.textContent = "باز نشد."; });
    return w;
  },

  /* ── بازی و جذابیت ── */
  checkin(b){
    const w = el("div", "blk chki card");
    if(ST.preview){ w.textContent = "🎁 چک‌این روزانه با سکه"; return w; }
    w.textContent = "…";
    api("/rt/" + BOT_ID + "/game/boot", {}).then(d => {
      w.innerHTML = "";
      const bt = el("button", "gm-btn");
      bt.textContent = d.daily.done ? "🎁 امروز گرفتی (استریک " + fd(d.daily.streak) + " روز)" : "🎁 سکه‌ی روزانه +" + fd(d.daily.next);
      bt.disabled = !!d.daily.done;
      bt.addEventListener("click", async () => {
        try{
          const r = await api("/rt/" + BOT_ID + "/game/daily", {});
          haptic(true); toast("+" + fd(r.gain) + " سکه!");
          bt.disabled = true; bt.textContent = "🎁 گرفتی (استریک " + fd(r.streak) + " روز)";
        }catch(e){ toast(e.message || "انجام نشد"); }
      });
      w.appendChild(bt);
    }).catch(() => { w.textContent = "برای چک‌این، بازی‌های ربات روشن باشند."; });
    return w;
  },
  badges(b){
    return itemsList(b, "bdg3", (it) => {
      const c = el("div", "bdgc");
      c.appendChild(iconOf(it.ic || "🏅"));
      c.appendChild(el("span", "", fill2(it.t || "")));
      return c;
    });
  },
  invite(b){
    const w = el("div", "blk ivt card");
    w.appendChild(el("div", "txt", fill2(b.text || "")));
    w.appendChild(el("div", "mut n", "دعوت‌های تو: " + fd(fill2("{refs|0}"))));
    const bt = el("button", "cta", fill2(b.btn || "📤 ارسال لینک دعوت"));
    bt.addEventListener("click", () => {
      haptic();
      openUrl("https://t.me/share/url?url=" + encodeURIComponent("https://t.me/" + (ST.bot.username || "")) + "&text=" + encodeURIComponent("بیا به این ربات سر بزن!"));
    });
    w.appendChild(bt);
    return w;
  },
  scratch(b){
    const w = el("div", "blk scr card");
    const box = el("div", "scrb");
    const txt = el("div", "scrt", fill2(b.text || ""));
    const cv = el("canvas");
    box.appendChild(txt); box.appendChild(cv);
    w.appendChild(box);
    let done = false;
    requestAnimationFrame(() => {
      const dpr = Math.min(2, devicePixelRatio || 1);
      const W = box.clientWidth || 280, H = 110;
      cv.width = W * dpr; cv.height = H * dpr;
      cv.style.width = W + "px"; cv.style.height = H + "px";
      const ctx = cv.getContext("2d");
      ctx.scale(dpr, dpr);
      ctx.fillStyle = "#8AA0A9";
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = "rgba(255,255,255,.6)";
      ctx.font = "bold 15px Vazirmatn, Tahoma";
      ctx.textAlign = "center";
      ctx.fillText("اینجا را بکش", W / 2, H / 2 + 5);
      let down = false, painted = 0;
      const scratch = (e) => {
        if(done) return;
        const r = cv.getBoundingClientRect();
        const x = (e.touches ? e.touches[0].clientX : e.clientX) - r.left;
        const y = (e.touches ? e.touches[0].clientY : e.clientY) - r.top;
        ctx.globalCompositeOperation = "destination-out";
        ctx.beginPath(); ctx.arc(x, y, 16, 0, 7); ctx.fill();
        painted++;
        if(painted > 24 && !done){
          done = true;
          cv.style.opacity = "0";
          haptic(true);
          if(b.hid) runDo(b.do, b.hid);
        }
      };
      cv.addEventListener("pointerdown", e => { down = true; scratch(e); });
      cv.addEventListener("pointermove", e => { if(down) scratch(e); });
      addEventListener("pointerup", () => { down = false; });
    });
    return w;
  },

  /* ── اجتماعی و فروشگاهی ── */
  profile(b){
    const w = el("div", "blk prf card");
    const av = el("div", "prfav", (varOf("name") || "؟").charAt(0));
    w.appendChild(av);
    w.appendChild(el("b", "", fill2("{name|دوست من}")));
    if(varOf("username")) w.appendChild(el("div", "mut ltr", varOf("username")));
    if(b.bio) w.appendChild(el("div", "mut", fill2(b.bio)));
    if((b.items || []).length){
      const grid = el("div", "stw");
      (b.items || []).forEach(it => {
        const c = el("div", "stat");
        c.appendChild(el("div", "mut", it.label || ""));
        c.appendChild(el("div", "sv", fd(fill2("{" + (it.var || "") + "|0}"))));
        grid.appendChild(c);
      });
      w.appendChild(grid);
    }
    return w;
  },
  reviews(b){
    return itemsList(b, "rvw", (it) => {
      const c = el("div", "rvwc card");
      const top = el("div", "rvwt");
      top.appendChild(el("b", "", fill2(it.t || "")));
      top.appendChild(stars(it.ic));
      c.appendChild(top);
      if(it.d) c.appendChild(el("div", "mut", fill2(it.d)));
      return c;
    });
  },
  team(b){
    return itemsList(b, "team", (it) => {
      const c = el("div", "teamc card");
      if(it.media && ST.media[it.media]){
        const im = el("img", "teamim"); im.loading = "lazy"; im.alt = ""; im.src = ST.media[it.media].url;
        c.appendChild(im);
      }else{
        c.appendChild(el("div", "prfav", (it.t || "؟").charAt(0)));
      }
      const d = el("div");
      d.appendChild(el("b", "", fill2(it.t || "")));
      if(it.d) d.appendChild(el("div", "mut", fill2(it.d)));
      c.appendChild(d);
      return c;
    });
  },
  services(b){
    return itemsList(b, "svc", (it) => {
      const c = el("div", "svcc card");
      c.appendChild(iconOf(it.ic || "✨"));
      const d = el("div");
      d.appendChild(el("b", "", fill2(it.t || "")));
      if(it.d) d.appendChild(el("div", "mut", fill2(it.d)));
      c.appendChild(d);
      return c;
    });
  },
  menu(b){
    const w = el("div", "blk mnw card");
    w.appendChild(el("b", "", "🍽 منو"));
    (b.items || []).forEach(it => {
      const r = el("div", "mnr");
      r.appendChild(el("b", "", fill2(it.t || "")));
      r.appendChild(el("span", "n pric2", fill2(it.price || "")));
      w.appendChild(r);
      if(it.d) w.appendChild(el("div", "mut mnd", fill2(it.d)));
    });
    return w;
  },
  contact(b){
    return itemsList(b, "cnt", (it) => {
      const c = el("button", "lnk");
      c.appendChild(el("span", "", fill2(it.t || "") + (it.d ? " · " + fill2(it.d) : "")));
      c.addEventListener("click", () => {
        haptic();
        const u = it.url || "";
        if(u.startsWith("tel:") || u.startsWith("mailto:")) location.href = u;
        else if(u) openUrl(u);
      });
      return c;
    });
  },
  social(b){
    const w = el("div", "blk scl");
    (b.items || []).forEach(it => {
      const c = el("button", "sclc");
      c.appendChild(iconOf(it.ic || "🔗"));
      c.appendChild(el("span", "", fill2(it.t || "")));
      c.addEventListener("click", () => { haptic(); if(it.url) openUrl(it.url); });
      w.appendChild(c);
    });
    return w;
  },
  map(b){
    const w = el("div", "blk map card");
    const src = mediaSrc(b);
    if(src){ const im = el("img", "mapim"); im.loading = "lazy"; im.alt = ""; im.src = src; w.appendChild(im); }
    if(b.addr) w.appendChild(el("div", "txt", "📍 " + fill2(b.addr)));
    if(b.url){
      const bt = el("button", "cta g", "مسیریابی");
      bt.addEventListener("click", () => { haptic(); openUrl(b.url); });
      w.appendChild(bt);
    }
    return w;
  },
  linktree(b){
    const w = el("div", "blk lkt");
    if(b.title) w.appendChild(el("b", "lkt-t", fill2(b.title)));
    (b.items || []).forEach(it => {
      const c = el("button", "lktb");
      c.appendChild(el("span", "", fill2(it.t || "")));
      c.insertAdjacentHTML("beforeend", svg('<path d="M15 6l-6 6 6 6"/>'));
      c.addEventListener("click", () => { haptic(); if(it.url) openUrl(it.url); });
      w.appendChild(c);
    });
    return w;
  },
  pollstat(b){
    const w = el("div", "blk pls card");
    w.appendChild(el("b", "", "📊 نتیجه‌ی نظرسنجی"));
    const rows = (b.items || []).map(it => ({t: it.t || "", n: parseFloat(String(varOf(it.var || "")).replace(/[^\d.-]/g, "")) || 0}));
    const mx = Math.max(1, ...rows.map(r => r.n));
    rows.forEach((r, ri) => {
      const row = el("div", "chrow");
      row.appendChild(el("span", "chlab", fill2(r.t)));
      const bar = el("div", "chbar");
      const bi = el("i");
      bi.style.width = Math.round(r.n / mx * 100) + "%";
      bi.style.background = HUE(ri);
      bar.appendChild(bi);
      row.appendChild(bar);
      row.appendChild(el("span", "n", fd(r.n)));
      w.appendChild(row);
    });
    return w;
  },
  hours(b){
    const w = el("div", "blk hrs card");
    w.appendChild(el("b", "", "🕐 ساعات کاری"));
    const todayIdx = (new Date().getDay() + 1) % 7;   // شنبه = ۰
    (b.items || []).forEach((it, i) => {
      const r = el("div", "hnrr" + (i === todayIdx ? " today" : ""));
      r.appendChild(el("b", "", fill2(it.t || "")));
      r.appendChild(el("span", "n", fill2(it.d || "")));
      w.appendChild(r);
    });
    return w;
  },
  changelog(b){
    return itemsList(b, "chl", (it) => {
      const r = el("div", "chlr");
      r.appendChild(el("span", "n chlv", fill2(it.t || "")));
      const d = el("div");
      if(it.d) d.innerHTML = rich(fill2(it.d));
      r.appendChild(d);
      return r;
    });
  },
  booking(b){
    const w = el("div", "blk bkg card");
    w.appendChild(el("b", "", "📅 نوبت بگیر"));
    const grid = el("div", "bkgr");
    (b.items || []).forEach(it => {
      const c = el("button", "bkgc");
      c.appendChild(el("b", "", fill2(it.t || "")));
      if(it.d) c.appendChild(el("span", "mut", fill2(it.d)));
      if(it.hid && (it.do || []).length) c.addEventListener("click", () => { haptic(); runDo(it.do, it.hid); });
      grid.appendChild(c);
    });
    w.appendChild(grid);
    return w;
  },
});

function renderScreen(id){
  const s = screenOf(id);
  const box = $("#m");
  box.innerHTML = "";
  clearTimers();
  const wrap = el("div");
  wrap.id = "mcontent";
  const sc = el("div", "mwrap");
  sc.id = "sc-" + id;
  if(s.when && !when(s.when)){
    sc.appendChild(el("p", "mut", "این بخش فعلاً در دسترس نیست."));
  }
  (s.blocks || []).forEach(b => {
    try{
      if(b.when && !when(b.when)) return;
      const fn = BLOCKS[b.t];
      if(!fn) return;
      const frag = fn(b);
      const stl = b.st;
      if(stl && frag && frag.nodeType === 1){
        const wrap = el("div", "stw2" + (stl.bg ? " bg-" + stl.bg : "") + (stl.anim ? " an-" + stl.anim : "") + (stl.shadow ? " shdw" : "") + (stl.v ? " v-" + stl.v : ""));
        if(stl.align === "center") wrap.style.textAlign = "center";
        if(stl.rad != null) wrap.style.setProperty("--bw-r", stl.rad + "px");
        const inner = frag.querySelector ? frag.querySelector(".cgrid,.catg,.grm,.qlk,.img,.lgs,.str,.bdg3,.bkgr,.stw,.brow,.tbbar") : null;
        if(inner){
          if(stl.cols) inner.style.gridTemplateColumns = "repeat(" + stl.cols + ",1fr)";
          if(stl.gap != null) inner.style.gap = stl.gap + "px";
        }
        if(stl.cols && !inner){
          wrap.style.display = "grid";
          wrap.style.gridTemplateColumns = "repeat(" + stl.cols + ",1fr)";
          if(stl.gap != null) wrap.style.gap = stl.gap + "px";
        }
        wrap.appendChild(frag);
        sc.appendChild(wrap);
      }else{
        sc.appendChild(frag);
      }
    }catch(e){ /* یک بلوک خراب بقیه صفحه را نمی‌شکند */ }
  });
  if(!sc.children.length) sc.appendChild(el("p", "mut", "این صفحه خالی است."));
  wrap.appendChild(sc);
  box.appendChild(wrap);
}

function renderNav(){
  const nav = $("#mnav"), inr = $("#mnavin");
  const nv = (ST.app && ST.app.nav) || {};
  const items = ((nv.type === "tabs" || nv.type === "top") && nv.items) || [];
  nav.className = "mnav nv-" + (nv.type === "top" ? "top" : "bottom") + " nvs-" + (nv.style || "simple");
  if(!items.length){ nav.hidden = true; return; }
  nav.hidden = false;
  inr.innerHTML = "";
  items.forEach(id => {
    const s = screenOf(id);
    if(!s) return;
    if(s.when && !when(s.when)) return;      // آیتم منو فقط وقتی شرط صفحه برقرار است
    const b = el("button", ST.screen === id ? "on" : "");
    b.innerHTML = ICON(s.icon || "home");
    if(!nv.icons) b.appendChild(el("span", "", s.title || id));
    b.setAttribute("aria-label", s.title || id);
    b.addEventListener("click", () => { if(ST.screen !== id){ ST.stack = []; render(id); haptic(); } });
    inr.appendChild(b);
  });
}

function render(id, keepStack){
  if(!ST.app) return;
  id = screenOf(id) ? id : ST.app.home;
  ST.screen = id;
  renderScreen(id);
  renderNav();
  backBtn();
  if(!keepStack) scrollTo(0, 0);
}

/* ── حالت‌های خاص ── */
function page(title, text, ic){
  clearTimers();
  $("#mnav").hidden = true;
  $("#m").innerHTML = `<div class="gpage"><div class="ic">${ICON(ic || "info")}</div><h2></h2><p></p></div>`;
  $("#m h2").textContent = title;
  $("#m p").textContent = text;
}
function bootDone(){
  applyTheme();
  ST.screen = null;
  let first = ST.app.home;
  try{
    const sp = tgw?.initDataUnsafe?.start_param || "";
    if(sp && screenOf(sp)) first = sp;      // لینک مستقیم صفحه: t.me/bot?startapp=screen
  }catch(_){}
  render(first);
  try{ tgw?.ready(); tgw?.expand(); }catch(_){}
}

/* ── بوت ── */
async function boot(){
  if(PREVIEW){
    addEventListener("message", e => {
      const d = e.data;
      if(!d || d.type !== "azadi-app" || !d.app || !d.app.screens) return;
      ST.app = d.app; ST.media = d.media || {}; ST.vars = d.vars || {}; ST.glo = d.globals || {};
      ST.user = {first_name: "کاربر نمونه", id: 0, is_owner: 0};
      ST.bot = d.bot || {name: "پیش‌نمایش", username: ""};
      bootDone();
    });
    try{ tgw?.ready(); }catch(_){}
    return;
  }
  if(!tgw || !tgw.initData){
    page("از داخل تلگرام باز کن", "این مینی‌اپ فقط داخل تلگرام کار می‌کند؛ ربات را باز کن و دکمه‌ی مینی‌اپ را بزن.", "info");
    return;
  }
  try{ tgw.ready(); tgw.expand(); }catch(_){}
  try{
    const d = await api("/rt/" + BOT_ID + "/boot", {});      // حتماً POST؛ بدون body متد GET می‌شود و مسیر 405 می‌دهد
    if(d.status === "off") return page("ربات خاموش است", "سازنده‌ی این مینی‌اپ فعلاً رباتش را غیرفعال کرده. کمی بعد دوباره سر بزن.", "info");
    if(d.status === "none" || d.error) return page("هنوز آماده نیست", d.error || "این مینی‌اپ هنوز منتشر نشده است.", "info");
    ST.app = d.app; ST.ver = d.ver; ST.media = d.media || {}; ST.vars = d.vars || {}; ST.glo = d.globals || {};
    ST.user = d.user || {}; ST.bot = d.bot || {};
    bootDone();
  }catch(e){
    page("باز نشد", e.status === 401 ? "برای باز کردن این مینی‌اپ، از داخل تلگرام وارد شو." : (e.message || "ارتباط برقرار نشد؛ دوباره امتحان کن."), "info");
  }
}
try{ tgw?.onEvent?.("themeChanged", () => { if(ST.app) applyTheme(); }); }catch(_){}
addEventListener("pagehide", clearTimers);
boot();
})();
