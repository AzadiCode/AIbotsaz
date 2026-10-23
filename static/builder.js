/* ═══════════════════════════════════════════════════════════════
   builder.js — تب «مینی‌اپ»: فهرست ربات‌ها، ویرایشگر بلوکی، پیش‌نمایش زنده (iframe +
   postMessage)، تم، داده، انتشار، نسخه‌ها، قالب‌ها و ساخت با هوش مصنوعی.
   بعد از app.js و studio.js بارگذاری می‌شود (به S، $، api، IC، showSheet، head، … تکیه دارد)
   و صفحه‌اش را با VIEWS.miniapp ثبت می‌کند. ذخیره‌ی پیش‌نویس با debounce یک‌ثانیه‌ای.
   ═══════════════════════════════════════════════════════════════ */
const MB = {draft: null, pub: false, ver: 0, caps: {}, screen: null, saveT: null, hist: [], hi: -1,
            pvT: null, lint: null, link: "", versions: [], stats: null, tpl: []};

const MB_T = {hero: "سربرگ", text: "متن", image: "تصویر", gallery: "گالری", video: "ویدیو", audio: "صدا",
  buttons: "دکمه‌ها", cards: "کارت‌ها", list: "فهرست داده", form: "فرم", stat: "آماره", board: "جدول برترین‌ها",
  faq: "سؤالات متداول", banner: "اطلاعیه", countdown: "شمارش معکوس", pay: "پرداخت", ai: "گفتگوی هوشمند",
  links: "لینک‌ها", divider: "جداکننده", spacer: "فاصله",
  games: "مرکز بازی", wallet: "کیف سکه", gamesboard: "رتبه‌ی بازی‌ها", shopcoins: "فروشگاه سکه‌ای"};
const MB_IC = {hero: "spark", text: "document", image: "photo", gallery: "photo", video: "video", audio: "audio",
  buttons: "layers", cards: "bag", list: "inbox", form: "form", stat: "stats", board: "medal", faq: "quiz",
  banner: "mega", countdown: "cal", pay: "coin", ai: "bot", links: "open", divider: "minus", spacer: "fit",
  games: "star", wallet: "coin", gamesboard: "medal", shopcoins: "bag"};
const MB_CAT = [["متن و رسانه", ["hero", "text", "image", "gallery", "video", "audio", "divider", "spacer"]],
  ["تعامل", ["buttons", "faq", "links", "banner", "countdown", "ai"]],
  ["داده", ["list", "stat", "board", "form"]],
  ["فروش", ["cards", "pay"]],
  ["بازی و جذابیت", ["games", "wallet", "gamesboard", "shopcoins"]]];
const MB_FLD_T = [["text", "متن"], ["number", "عدد"], ["phone", "شماره تماس"], ["email", "ایمیل"], ["select", "انتخابی"], ["date", "تاریخ"]];

/* ── تاریخچه‌ی برگشت (تا ۵۰ مرحله، در حافظه) ── */
function mbSnap(){ return JSON.stringify(MB.draft); }
function mbPush(){
  MB.hist = MB.hist.slice(0, MB.hi + 1);
  MB.hist.push(mbSnap());
  if(MB.hist.length > 50) MB.hist.shift();
  MB.hi = MB.hist.length - 1;
}
function mbRestore(s){
  try{
    MB.draft = JSON.parse(s);
    MB.screen = (MB.draft.screens || {})[MB.screen] ? MB.screen : MB.draft.home;
    mbSave();
    mbPaintBlocks();
    mbPostPreview();
    renderMiniapp();
  }catch(_){}
}
function mbUndo(){ if(MB.hi > 0){ MB.hi--; mbRestore(MB.hist[MB.hi]); } }
function mbRedo(){ if(MB.hi < MB.hist.length - 1){ MB.hi++; mbRestore(MB.hist[MB.hi]); } }

/* ── ذخیره‌ی خودکار (debounce یک‌ثانیه‌ای) + پیش‌نویس محلی ── */
function mbTouch(){ MB._dirty = true; clearTimeout(MB.saveT); MB.saveT = setTimeout(mbSave, 1000); clearTimeout(MB.pvT); MB.pvT = setTimeout(mbPostPreview, 250); }
async function mbSave(){
  if(!MB.draft || !S.cur) return;
  MB._dirty = false;
  try{
    const d = await api(`/api/bots/${S.cur.id}/app`, "PUT", {app: MB.draft});
    MB.draft = d.draft;
    const el = $("#bsave"); if(el) el.textContent = "ذخیره شد";
    try{ localStorage.setItem("azadi.app." + S.cur.id, JSON.stringify(MB.draft)); }catch(_){}
  }catch(e){ toast(e.message); }
}
function mbPostPreview(){
  const f = $("#bpv");
  if(!f || !MB.draft) return;
  try{
    const media = {};
    (S.media || []).forEach(m => { media[m.id] = {url: location.origin + m.url, kind: m.kind}; });
    const vars = {};
    Object.keys((S.cur.config || {}).vars || {}).forEach(k => { vars[k] = ""; });
    vars.name = "کاربر نمونه";
    f.contentWindow.postMessage({type: "azadi-app", app: MB.draft, media, vars, bot: {name: S.cur.name, username: S.cur.username || ""}}, "*");
  }catch(_){}
}

/* ── بارگذاری ── */
/* پاک‌سازی داده‌های قدیمی: اگر عنوان/برچسب‌ها به‌اشتباه تگ HTML (مثل <span class="n">) داشته باشند تمیز می‌شوند */
function mbCleanLegacy(d){
  if(!d || !d.screens) return false;
  const strip = v => { const o = String(v ?? ""); return o === (o.replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim()) ? o : o.replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim(); };
  let changed = false;
  for(const s of Object.values(d.screens)){
    const t0 = s.title; if(s.title) s.title = strip(s.title); if(s.title !== t0) changed = true;
    for(const b of s.blocks || []){
      for(const k of ["title", "label", "tag"]) if(b[k]){ const v = strip(b[k]); if(v !== b[k]){ b[k] = v; changed = true; } }
      if(b.cta?.text){ const v = strip(b.cta.text); if(v !== b.cta.text){ b.cta.text = v; changed = true; } }
      for(const row of b.rows || []) for(const x of row) if(x.text){ const v = strip(x.text); if(v !== x.text){ x.text = v; changed = true; } }
      for(const it of b.items || []) if(it) for(const k of ["title", "label", "q"]) if(it[k]){ const v = strip(it[k]); if(v !== it[k]){ it[k] = v; changed = true; } }
      for(const f of b.fields || []) if(f.label){ const v = strip(f.label); if(v !== f.label){ f.label = v; changed = true; } }
    }
  }
  return changed;
}
async function mbLoad(){
  if(!S.cur) return;
  try{
    const d = await api(`/api/bots/${S.cur.id}/app`);
    MB.draft = d.draft; MB.pub = !!d.pub; MB.ver = d.ver || 0; MB.caps = d.caps || {}; MB.versions = d.versions || [];
    if(!MB.draft){
      try{ const loc = JSON.parse(localStorage.getItem("azadi.app." + S.cur.id) || "null"); if(loc && loc.screens) MB.draft = loc; }catch(_){}
    }
    if(MB.draft && mbCleanLegacy(MB.draft)) mbTouch();      // عنوان‌های آلوده به تگ، یک‌باره تمیز و ذخیره می‌شوند
    MB.screen = MB.draft ? (MB.draft.screens[MB.draft.home] ? MB.draft.home : Object.keys(MB.draft.screens)[0]) : null;
    MB.hist = MB.draft ? [mbSnap()] : []; MB.hi = 0;
    MB.link = d.username ? `https://t.me/${d.username}?startapp` : "";
  }catch(e){ toast(e.message); }
}

/* ═════════ فهرست ربات‌ها (بدون ربات انتخاب‌شده) ═════════ */
async function renderMiniapp(){
  if(!S.cur){
    /* فهرست هر بار از سرور تازه گرفته می‌شود تا ربات تازه‌ساخته‌شده فوراً دیده شود */
    $("#app").innerHTML = `<div class="ph"><h1>مینی‌اپ</h1></div><div class="group"><div class="gi static"><span class="muted">در حال بارگذاری…</span></div></div>`;
    try{ MB._list = await api("/api/myapps"); MB._listErr = ""; }
    catch(e){ MB._listErr = e.message || "خطا در ارتباط با سرور"; }
    if(S.view !== "miniapp" || S.cur) return;      // کاربر در همین حین رفت به صفحه‌ی دیگر
    const l = MB._list;
    $("#app").innerHTML = `
      <div class="ph"><h1>مینی‌اپ</h1><span class="cnt">${l ? N((l.items || []).filter(x => x.on).length) + " فعال" : "…"}</span></div>
      <p class="muted" style="margin:-6px 2px 14px">برای هر ربات یک مینی‌اپ بساز: بدون کدنویسی، با چیدن بلوک‌ها یا توضیح دادن به هوش مصنوعی. کاربر با یک دکمه از داخل ربات بازش می‌کند.</p>
      ${MB._listErr ? `<div class="empty"><div class="ib big">${IC.bot}</div><h2>بارگذاری نشد</h2><p class="muted">${esc(MB._listErr)}</p><button class="b sm" data-a="mbrelist">تلاش دوباره</button></div>`
        : l && (l.items || []).length ? `<div class="group sep">${l.items.map(x => `
        <button class="gi" data-a="mbopen" data-id="${esc(x.id)}"><span class="dot ${x.on ? "on" : ""}"></span>
          <span class="gt"><b>${esc(x.name)}</b><span class="${x.active ? "ltr" : ""}">${x.active ? "@" + esc(x.username) : "غیرفعال"} · ${x.on ? "منتشر شده" : x.blocks ? "پیش‌نویس" : "خاموش"}</span></span>${goIc}</button>`).join("")}</div>`
        : l ? `<div class="empty"><div class="ib big">${IC.layers}</div><h2>هنوز مینی‌اپی نداری</h2><p class="muted">اول یک ربات انتخاب کن یا بساز.</p><button class="b sm" data-go="create">ساخت ربات</button></div>` : ""}
      ${l ? `<p class="muted" style="margin:12px 2px">مینی‌اپ فعال: ${N(l.caps.apps_used || 0)} از ${N(l.caps.apps || 1)} · سقف بلوک: ${N(l.caps.blocks || 30)}${(l.caps.apps_used || 0) >= (l.caps.apps || 1) ? ' · <button class="b t" data-a="goplan">ارتقا</button>' : ""}</p>` : ""}`;
    return;
  }
  if(MB.draft === null && MB._loadedFor !== S.cur.id){
    $("#app").innerHTML = `<div class="ph"><h1>مینی‌اپ</h1></div><div class="group"><div class="gi static"><span class="muted">در حال بارگذاری…</span></div></div>`;
    await mbLoad();
    MB._loadedFor = S.cur.id;
    if(S.view !== "miniapp") return;
  }
  if(MB._loadedFor !== S.cur.id){ MB._loadedFor = S.cur.id; MB.draft = null; await mbLoad(); if(S.view !== "miniapp") return; }
  if(!MB.draft){
    MB.draft = {v: 1, theme: {mode: "auto", accent: "#3CCFE3", radius: 16, font: "vazir", digits: "latin"},
      nav: {type: "tabs", items: ["home"]}, home: "home",
      screens: {home: {title: "خانه", icon: "home", blocks: []}}};
    MB.screen = "home"; MB.hist = [mbSnap()]; MB.hi = 0;
    mbTouch();
  }
  mbEditor();
}

/* ═════════ ویرایشگر ═════════ */
function mbEditor(){
  const b = S.cur;
  $("#app").innerHTML = `
    <div class="bph">
      <button class="iconb" data-a="mbback" aria-label="بازگشت">${IC.back}</button>
      <div class="bt"><b>${esc(b.name)}</b><span class="muted ${b.active ? "ltr" : ""}">${b.active ? "@" + esc(b.username) : "ربات غیرفعال"} · ${MB.pub ? "منتشر شده" : "پیش‌نویس"}</span></div>
      <span class="muted" id="bsave"></span>
      <button class="iconb" data-a="mbundo" aria-label="برگشت" ${MB.hi > 0 ? "" : "disabled"}>${IC.refresh}</button>
      <button class="iconb" data-a="mbredo" aria-label="جلو" ${MB.hi < MB.hist.length - 1 ? "" : "disabled"}>${IC.go}</button>
      <button class="b sm" data-a="mbpub">${MB.pub ? "انتشار" : "انتشار"}</button>
    </div>
    <div class="bframe"><div class="bphone"><iframe id="bpv" src="/a/${esc(b.id)}?preview=1" sandbox="allow-scripts" title="پیش‌نمایش مینی‌اپ"></iframe></div>
      <div class="bpf"><button class="b t" data-a="mbreload">${IC.refresh}تازه‌سازی</button>${MB.link ? `<button class="b t" data-a="mbcopy">${IC.copy}کپی لینک</button>` : ""}</div></div>
    <div class="bscr" id="bscr"></div>
    <div class="bblocks" id="bblocks"></div>
    <button class="badd" data-a="mbadd" aria-label="افزودن بلوک">${IC.plus}<span>افزودن بلوک</span></button>
    <div class="bfoot">
      <button class="gi" data-a="mbtheme"><span class="ib">${IC.spark}</span><span class="gt"><b>تم و ظاهر</b><span>رنگ، حالت روشن و تیره، گردی گوشه‌ها</span></span>${goIc}</button>
      <button class="gi" data-a="mbdata"><span class="ib">${IC.layers}</span><span class="gt"><b>داده‌ها</b><span>متغیرها و جدول‌های ربات برای بلوک‌های داده‌دار</span></span>${goIc}</button>
      <button class="gi" data-a="mbai"><span class="ib">${IC.bot}</span><span class="gt"><b>ساخت با هوش مصنوعی</b><span>توضیح بده، مینی‌اپ را بچین</span></span>${goIc}</button>
      <button class="gi" data-a="mbtpl"><span class="ib">${IC.bag}</span><span class="gt"><b>قالب‌های آماده</b><span>فروشگاه، رزرو، باشگاه و…</span></span>${goIc}</button>
      <button class="gi" data-a="mbstats"><span class="ib">${IC.stats}</span><span class="gt"><b>آمار</b><span>باز شدن، فرم و پرداخت</span></span>${goIc}</button>
      <button class="gi" data-a="mbver"><span class="ib">${IC.refresh}</span><span class="gt"><b>نسخه‌ها و JSON</b><span>بازگشت و پشتیبان</span></span>${goIc}</button>
    </div>`;
  const f = $("#bpv");
  if(f) f.addEventListener("load", mbPostPreview);
  mbPaintScreens();
  mbPaintBlocks();
  setTimeout(mbPostPreview, 400);
}

function mbPaintScreens(){
  const bar = $("#bscr");
  if(!bar || !MB.draft) return;
  const ids = Object.keys(MB.draft.screens);
  const inNav = (MB.draft.nav.items || []).includes(MB.screen);
  bar.innerHTML = ids.map(id => {
    const s = MB.draft.screens[id];
    return `<button class="chip ${id === MB.screen ? "on" : ""}" data-a="mbscr" data-id="${esc(id)}">${esc(s.title || id)}</button>`;
  }).join("") + `<button class="chip" data-a="mbscradd">${IC.plus}صفحه</button>`
    + (MB.screen && MB.screen !== MB.draft.home ? `<button class="chip ${inNav ? "ai" : ""}" data-a="mbnav">${inNav ? "− منو" : "+ منو"}</button>` : "");
}

/* خلاصه‌ی متنی هر بلوک؛ خروجی با esc رندر می‌شود پس فقط متن ساده (بدون N/HTML) */
function mbBlockSummary(x){
  const t = x.t;
  if(t === "hero") return x.title || (x.text || "").replace(/<[^>]+>/g, "").slice(0, 30);
  if(t === "text") return (x.text || "").replace(/<[^>]+>/g, "").slice(0, 40);
  if(t === "form") return (x.fields?.length || 0) + " فیلد" + (x.save?.table ? " · جدول " + x.save.table : "");
  if(t === "pay") return x.stars + " ستاره";
  if(t === "ai") return (x.prompt || "").slice(0, 34);
  if(t === "buttons") return (x.rows || []).reduce((a, r) => a + r.length, 0) + " دکمه";
  if(t === "cards") return (x.items?.length || 0) + " کارت";
  if(t === "list") return "جدول " + x.table;
  if(t === "board") return x.var === "refs" ? "دعوت‌ها" : x.var || "";
  if(t === "stat") return x.var || "";
  if(t === "faq") return (x.items?.length || 0) + " پرسش";
  if(t === "links") return (x.items?.length || 0) + " لینک";
  if(t === "games") return "۹ بازی سمت سرور";
  if(t === "wallet") return "سکه و پاداش روزانه";
  if(t === "shopcoins") return "فروشگاه سکه‌ای";
  if(t === "gamesboard") return "رتبه‌ی " + (x.game || "quiz");
  if(t === "countdown") return "تا زمان مشخص";
  if(t === "banner") return (x.text || "").replace(/<[^>]+>/g, "").slice(0, 30);
  return "";
}

/* آیکن‌های فلش بالا/پایین برای جابه‌جایی بلوک */
const MB_UP = svg('<path d="M12 19V5M6 11l6-6 6 6"/>', 2.2);
const MB_DOWN = svg('<path d="M12 5v14M6 13l6 6 6-6"/>', 2.2);

function mbPaintBlocks(){
  const box = $("#bblocks");
  if(!box || !MB.draft) return;
  const s = MB.draft.screens[MB.screen];
  if(!s){ box.innerHTML = ""; return; }
  const arr = s.blocks || [];
  box.innerHTML = `<div class="sub"><span>صفحه‌ی «${esc(s.title || MB.screen)}» · ${N(arr.length)} بلوک</span>
      <button class="iconb sm" data-a="mbscredit" aria-label="ویرایش صفحه">${IC.gear}</button></div>
    ${arr.length ? arr.map((x, i) => `<div class="brow-b">
      <div class="bblk" role="button" tabindex="0" data-a="mbedit" data-i="${i}"><span class="ib">${IC[MB_IC[x.t]] || IC.layers}</span>
        <span class="gt"><b>${MB_T[x.t] || x.t}</b><span>${esc(mbBlockSummary(x))}</span></span>
        <span class="bops">
          <button class="iconb sm" data-a="mbup" data-i="${i}" aria-label="بالا" ${i === 0 ? "disabled" : ""}>${MB_UP}</button>
          <button class="iconb sm" data-a="mbdown" data-i="${i}" aria-label="پایین" ${i === arr.length - 1 ? "disabled" : ""}>${MB_DOWN}</button>
          <button class="iconb sm" data-a="mbcp" data-i="${i}" aria-label="کپی">${IC.copy}</button>
          <button class="iconb sm" data-a="mbdel" data-i="${i}" aria-label="حذف" style="color:var(--bad)">${IC.trash}</button>
        </span></div></div>`).join("")
      : `<div class="empty" style="padding:22px 10px"><p class="muted">این صفحه خالی است. با دکمه‌ی «افزودن بلوک» شروع کن.</p></div>`}`;
}

function mbScreenIds(){ return Object.keys(MB.draft.screens); }
function mbNewId(){
  let i = 1;
  while(MB.draft.screens["p" + i]) i++;
  return "p" + i;
}
function mbBlockId(){
  const used = new Set();
  Object.values(MB.draft.screens).forEach(s => (s.blocks || []).forEach(b => used.add(b.id)));
  let i = used.size + 1;
  while(used.has("b" + i)) i++;
  return "b" + i;
}

/* ═════════ شیت‌های سازنده ═════════ */
function bpSheet(){
  const cats = MB_CAT.map(([cat, types]) => `<div class="sub"><span>${cat}</span></div>
    <div class="bgrid">${types.map(t => `<button class="bpick${(MB.draft.screens[MB.screen].blocks || []).length >= MB.caps.blocks ? " off" : ""}" data-a="mbpick" data-t="${t}">
      <span class="ib">${IC[MB_IC[t]] || IC.layers}</span><span>${MB_T[t]}</span></button>`).join("")}</div>`).join("");
  return head("افزودن بلوک") + cats + `<div class="fgap"></div>`;
}
function mbDefaultBlock(t){
  const id = mbBlockId();
  const d = {id, t};
  if(t === "hero") return {...d, title: "عنوان", text: "یک جمله‌ی کوتاه", cta: {text: "شروع", do: []}};
  if(t === "text") return {...d, text: "متن این بخش را اینجا بنویس."};
  if(t === "image") return {...d, caption: ""};
  if(t === "gallery") return {...d, items: []};
  if(t === "video" || t === "audio") return {...d, caption: ""};
  if(t === "buttons") return {...d, rows: [[{text: "دکمه", do: [{op: "goto", screen: MB.draft.home}]}]]};
  if(t === "cards") return {...d, items: [{title: "کارت اول", text: "توضیح کوتاه"}]};
  if(t === "list") return {...d, table: "items", scope: "my", limit: 10, line: "#{n} · {text}", empty: "هنوز چیزی ثبت نشده."};
  if(t === "form") return {...d, title: "فرم", fields: [{k: "name", label: "نام", type: "text", req: true}], save: {table: "forms"}, notify: true, done: "ثبت شد. ممنون!"};
  if(t === "stat") return {...d, var: "", label: "عنوان"};
  if(t === "board") return {...d, var: "", top: 10, label: "برترین‌ها"};
  if(t === "faq") return {...d, items: [{q: "سؤال", a: "پاسخ"}]};
  if(t === "banner") return {...d, style: "info", text: "متن اطلاعیه"};
  if(t === "countdown") return {...d, to: Math.floor(Date.now() / 1000) + 86400, title: "شروع به‌زودی", done: "شروع شد!"};
  if(t === "pay") return {...d, stars: 50, title: "خرید", desc: "", text: "پرداخت انجام شد. ممنون!", do: []};
  if(t === "ai") return {...d, prompt: "تو دستیار مفید این کسب‌وکار هستی. کوتاه و مؤدب جواب بده.", daily: 15, memory: 3, greeting: "سؤالت رو بنویس."};
  if(t === "links") return {...d, items: [{label: "کانال ما", url: "https://t.me/your_channel"}]};
  if(t === "spacer") return {...d, h: 16};
  if(t === "games" || t === "wallet" || t === "shopcoins") return {...d};
  if(t === "gamesboard") return {...d, game: "quiz"};
  return d;
}

function mbFindBlock(i){ return (MB.draft.screens[MB.screen].blocks || [])[+i]; }

/* مسیر تودرتو (مثل cta.do یا rows.0.1.do) به آرایه‌ی اکشن‌ها؛ در صورت نبود می‌سازد */
function mbDoArr(key, make){
  const parts = String(key).split(".");
  let o = D;
  for(let i = 0; i < parts.length - 1; i++) o = o[parts[i]] = o[parts[i]] || {};
  if(make && !Array.isArray(o[parts[parts.length - 1]])) o[parts[parts.length - 1]] = [];
  return o[parts[parts.length - 1]];
}

function bpropSheet(){
  const x = D, t = x.t;
  const scr = mbScreenIds();
  const scrOpts = (cur, extra = "") => extra + scr.map(s => `<option value="${esc(s)}"${s === cur ? " selected" : ""}>${esc(MB.draft.screens[s].title || s)}</option>`).join("");
  let h = head("بلوک «" + (MB_T[t] || t) + "»") + `<p class="muted">شناسه: <span class="ltr">${esc(x.id)}</span></p>`;
  const actEditor = (label, key) => `
    <span class="lbl">${label}</span>
    <div class="mbdo" data-k="${key}"></div>
    <button class="b o sm" data-a="mbdoadd" data-k="${key}">${IC.plus}اکشن</button>
    <p class="muted mt">اکشن‌ها به ترتیب اجرا می‌شوند. «رفتن به صفحه» و پیام‌های رابط همین‌جا اعمال می‌شوند؛ اکشن‌های داده و ارسال به ربات موقع انتشار بررسی می‌شوند.</p>`;
  const doRow = (a, key, i) => {
    const op = a.op || "goto";
    let body = "";
    if(op === "goto") body = `<select class="d-scr">${scrOpts(a.screen)}</select>`;
    else if(op === "url") body = `<input class="fa d-url" value="${esc(a.url || "")}" placeholder="https://... یا @channel">`;
    else if(op === "copy" || op === "share" || op === "toast") body = `<input class="fa d-txt" value="${esc(a.text || "")}" placeholder="متن" maxlength="200">`;
    else if(op === "send") body = `<input class="fa d-node" value="${esc(a.node || "")}" placeholder="شناسه‌ی بخش ربات (مثل home)" maxlength="30">`;
    else if(op === "set" || op === "add" || op === "random") body = `<input class="fa d-var" value="${esc(a.var || "")}" placeholder="متغیر" maxlength="20"><input class="fa d-val" value="${esc(a.value ?? "")}" placeholder="${op === "random" ? "1-6" : "مقدار"}" maxlength="100">`;
    else if(op === "notify") body = `<input class="fa d-val" value="${esc(a.value || "")}" placeholder="پیام برای خودت" maxlength="200">`;
    else if(op === "remind") body = `<input class="ltr d-min" type="number" min="1" max="43200" value="${esc(a.minutes || 60)}" aria-label="دقیقه"><input class="fa d-val" value="${esc(a.value || "")}" placeholder="متن یادآوری" maxlength="200">`;
    else if(op === "clear") body = `<input class="fa d-var" value="${esc(a.var || "")}" placeholder="متغیر" maxlength="20">`;
    else body = `<span class="muted">${op}</span>`;
    const lab = {goto: "رفتن به صفحه", url: "باز کردن لینک", copy: "کپی", share: "اشتراک", toast: "پیام کوتاه", close: "بستن", back: "بازگشت", refresh: "تازه‌سازی", send: "ارسال بخش ربات به چت", set: "تنظیم متغیر", add: "افزودن به متغیر", clear: "پاک کردن متغیر", random: "عدد تصادفی", notify: "خبر به من", remind: "یادآوری"}[op] || op;
    return `<div class="rl" data-i="${i}"><div class="cmd" style="justify-content:space-between"><b>${lab}</b><button class="iconb sm" data-a="mbdodel" data-k="${key}" data-i="${i}" aria-label="حذف">${IC.x}</button></div>
      <select class="d-op">${[["goto","رفتن به صفحه"],["url","باز کردن لینک"],["copy","کپی"],["share","اشتراک"],["toast","پیام کوتاه"],["back","بازگشت"],["refresh","تازه‌سازی"],["close","بستن مینی‌اپ"],["send","ارسال بخش ربات به چت"],["set","تنظیم متغیر"],["add","افزودن به متغیر"],["clear","پاک کردن متغیر"],["random","عدد تصادفی"],["notify","خبر به من"],["remind","یادآوری"]].map(([v, l]) => `<option value="${v}"${v === op ? " selected" : ""}>${l}</option>`).join("")}</select>
      ${body}</div>`;
  };
  const paintDo = () => {
    document.querySelectorAll(".mbdo").forEach(box => {
      const key = box.dataset.k, arr = key === "." ? x : key.split(".").reduce((o, k) => (o || {})[k], x) || [];
      box.innerHTML = arr.map((a, i) => doRow(a, key, i)).join("");
    });
  };
  window.__mbPaintDo = paintDo;
  if(t === "hero"){
    h += `<span class="lbl">عنوان</span><input class="fa" id="p-title" value="${esc(x.title || "")}" maxlength="80">
      <span class="lbl">متن</span><textarea class="fa" id="p-text" data-fmt maxlength="300">${esc(x.text || "")}</textarea>${fmtTools("p-text")}`;
    h += `<span class="lbl">رسانه (عکس از کتابخانه یا لینک)</span>${mediaPicker("media", x.media || "")}`;
    if(!x.media) h += `<span class="lbl">یا لینک عکس</span><input id="p-url" value="${esc(x.url || "")}" placeholder="https://...jpg" autocomplete="off">`;
    h += `<span class="lbl">دکمه‌ی اصلی</span><input class="fa" id="p-ctatext" value="${esc(x.cta?.text || "")}" maxlength="24" placeholder="متن دکمه (خالی = بدون دکمه)">`;
    h += actEditor("کار دکمه‌ی اصلی", "cta.do");
  }else if(t === "text"){
    h += `<span class="lbl">متن</span><textarea class="fa" id="p-text" data-fmt maxlength="2000" style="min-height:120px">${esc(x.text || "")}</textarea>${fmtTools("p-text")}`;
  }else if(t === "image" || t === "video" || t === "audio"){
    h += `<span class="lbl">رسانه</span>${mediaPicker("media", x.media || "")}`;
    if(!x.media) h += `<span class="lbl">یا لینک مستقیم https</span><input id="p-url" value="${esc(x.url || "")}" placeholder="https://..." autocomplete="off">`;
    h += `<span class="lbl">توضیح (اختیاری)</span><input class="fa" id="p-caption" value="${esc(x.caption || "")}" maxlength="200">`;
  }else if(t === "gallery"){
    h += `<div class="sub"><span>تصویرها (${N(x.items.length)} از ۱۰)</span><button class="b o sm" data-a="mbgaladd"${x.items.length >= 10 ? " disabled" : ""}>${IC.plus}تصویر</button></div>
      ${x.items.map((it, i) => `<div class="rl"><span class="muted">تصویر ${N(i + 1)}</span>${mediaPicker("gi" + i, it.media || "")}${!it.media ? `<input id="p-gi-${i}" value="${esc(it.url || "")}" placeholder="https://..." autocomplete="off">` : ""}<button class="b r sm" data-a="mbgaldel" data-i="${i}">حذف</button></div>`).join("")}`;
  }else if(t === "buttons"){
    h += `<div class="sub"><span>ردیف‌های دکمه</span><button class="b o sm" data-a="mbrowadd"${x.rows.length >= 4 ? " disabled" : ""}>${IC.plus}ردیف</button></div>
      ${x.rows.map((row, ri) => `<div class="rl"><span class="muted">ردیف ${N(ri + 1)}</span>
        ${row.map((btn, ci) => `<div class="cmd"><input class="fa bt-txt" data-r="${ri}" data-c="${ci}" value="${esc(btn.text || "")}" maxlength="24" placeholder="متن دکمه"><button class="iconb sm" data-a="mbbtdel" data-r="${ri}" data-c="${ci}" aria-label="حذف دکمه">${IC.x}</button></div>
          <div class="mbdo" data-k="rows.${ri}.${ci}.do"></div>
          <button class="b o sm" data-a="mbdoadd" data-k="rows.${ri}.${ci}.do">${IC.plus}اکشن این دکمه</button>`).join("")}
        ${row.length < 3 ? `<button class="b o sm" data-a="mbbtadd" data-r="${ri}">${IC.plus}دکمه</button>` : ""}</div>`).join("")}`;
  }else if(t === "cards"){
    h += `<div class="sub"><span>کارت‌ها (${N(x.items.length)} از ۵۰)</span><button class="b o sm" data-a="mbcardadd"${x.items.length >= 50 ? " disabled" : ""}>${IC.plus}کارت</button></div>
      ${x.items.map((it, i) => `<div class="rl"><div class="cmd" style="justify-content:space-between"><b>کارت ${N(i + 1)}</b><button class="iconb sm" data-a="mbcarddel" data-i="${i}" aria-label="حذف">${IC.x}</button></div>
        <input class="fa c-title" data-i="${i}" value="${esc(it.title || "")}" maxlength="60" placeholder="عنوان">
        <input class="fa c-text" data-i="${i}" value="${esc(it.text || "")}" maxlength="200" placeholder="توضیح">
        ${mediaPicker("ci" + i, it.media || "")}${!it.media ? `<input id="p-ci-${i}" value="${esc(it.url || "")}" placeholder="لینک تصویر https" autocomplete="off">` : ""}</div>`).join("")}`;
  }else if(t === "form"){
    h += `<span class="lbl">عنوان فرم</span><input class="fa" id="p-title" value="${esc(x.title || "")}" maxlength="40">
      <div class="sub"><span>فیلدها (${N(x.fields.length)} از ۱۲)</span><button class="b o sm" data-a="mbfldadd"${x.fields.length >= 12 ? " disabled" : ""}>${IC.plus}فیلد</button></div>
      ${x.fields.map((f, i) => `<div class="rl"><div class="cmd" style="justify-content:space-between"><b>فیلد ${N(i + 1)}</b><button class="iconb sm" data-a="mbflddel" data-i="${i}" aria-label="حذف">${IC.x}</button></div>
        <div class="cmd"><input class="fa f-lab" data-i="${i}" value="${esc(f.label || "")}" maxlength="60" placeholder="برچسب"><label class="chk" style="margin:0"><input type="checkbox" class="f-req" data-i="${i}"${f.req ? " checked" : ""}>لازم</label></div>
        <div class="cmd"><input class="f-k ltr" data-i="${i}" value="${esc(f.k || "")}" maxlength="20" placeholder="name"><select class="f-ty" data-i="${i}">${MB_FLD_T.map(([v, l]) => `<option value="${v}"${v === f.type ? " selected" : ""}>${l}</option>`).join("")}</select></div>
        ${f.type === "select" ? `<input class="fa f-opts" data-i="${i}" value="${esc((f.opts || []).join("، "))}" placeholder="گزینه‌ها با ویرگول">` : ""}</div>`).join("")}
      <span class="lbl">ذخیره در جدول (اختیاری، مثل orders)</span><input class="ltr" id="p-table" value="${esc(x.save?.table || "")}" maxlength="20" autocomplete="off">
      <label class="chk"><input type="checkbox" id="p-notify"${x.notify !== false ? " checked" : ""}> هر ثبت برای من پیام بیاید</label>
      <label class="chk"><input type="checkbox" id="p-ticket"${x.ticket ? " checked" : ""}> هر ثبت یک تیکت شماره‌دار شود (با دکمه‌ی پاسخ در چت ربات)</label>
      ${x.ticket ? `<span class="lbl">برچسب تیکت</span><input class="fa" id="p-tag" value="${esc(x.tag || "")}" maxlength="20">` : ""}
      <span class="lbl">پیام بعد از ثبت</span><input class="fa" id="p-done" value="${esc(x.done || "")}" maxlength="200">`;
  }else if(t === "stat"){
    h += `<span class="lbl">متغیر عددی ربات (مثل points)</span><input class="ltr" id="p-var" value="${esc(x.var || "")}" maxlength="20" autocomplete="off">
      <span class="lbl">عنوان</span><input class="fa" id="p-label" value="${esc(x.label || "")}" maxlength="40">`;
  }else if(t === "board"){
    h += `<span class="lbl">متغیر عددی ربات یا refs برای دعوت‌ها</span><input class="ltr" id="p-var" value="${esc(x.var || "")}" maxlength="20" autocomplete="off">
      <span class="lbl">تعداد نفرات (۳ تا ۲۰)</span><input class="ltr" id="p-top" type="number" min="3" max="20" value="${esc(x.top || 10)}">
      <span class="lbl">عنوان</span><input class="fa" id="p-label" value="${esc(x.label || "")}" maxlength="40">`;
  }else if(t === "list"){
    h += `<span class="lbl">نام جدول ربات (مثل orders)</span><input class="ltr" id="p-table" value="${esc(x.table || "")}" maxlength="20" autocomplete="off">
      <span class="lbl">نمایش رکوردهای</span><select id="p-scope"><option value="my"${x.scope !== "all" ? " selected" : ""}>هر کاربر فقط رکوردهای خودش</option><option value="all"${x.scope === "all" ? " selected" : ""}>همه (مشترک)</option></select>
      <span class="lbl">تعداد (۱ تا ۲۰)</span><input class="ltr" id="p-limit" type="number" min="1" max="20" value="${esc(x.limit || 10)}">
      <span class="lbl">قالب هر خط ({n} شماره، {u} کاربر، و فیلدها)</span><input class="fa" id="p-line" value="${esc(x.line || "")}" maxlength="200">
      <span class="lbl">متن وقتی خالی است</span><input class="fa" id="p-empty" value="${esc(x.empty || "")}" maxlength="100">`;
  }else if(t === "faq"){
    h += `<div class="sub"><span>پرسش‌ها (${N(x.items.length)} از ۲۰)</span><button class="b o sm" data-a="mbfaqadd"${x.items.length >= 20 ? " disabled" : ""}>${IC.plus}پرسش</button></div>
      ${x.items.map((it, i) => `<div class="rl"><div class="cmd" style="justify-content:space-between"><b>پرسش ${N(i + 1)}</b><button class="iconb sm" data-a="mbfaqdel" data-i="${i}" aria-label="حذف">${IC.x}</button></div>
        <input class="fa fq-q" data-i="${i}" value="${esc(it.q || "")}" maxlength="120" placeholder="سؤال">
        <textarea class="fa fq-a" data-i="${i}" maxlength="500" placeholder="پاسخ">${esc(it.a || "")}</textarea></div>`).join("")}`;
  }else if(t === "banner"){
    h += `<span class="lbl">سبک</span><select id="p-style">${[["info", "خنثی"], ["ok", "موفق"], ["warn", "هشدار"]].map(([v, l]) => `<option value="${v}"${v === x.style ? " selected" : ""}>${l}</option>`).join("")}</select>
      <span class="lbl">متن</span><textarea class="fa" id="p-text" maxlength="300">${esc(x.text || "")}</textarea>`;
  }else if(t === "countdown"){
    h += `<span class="lbl">زمان پایان (تاریخ)</span><input id="p-date" type="datetime-local" value="${new Date(((+x.to || 0) * 1000) - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16)}">
      <span class="lbl">عنوان</span><input class="fa" id="p-title" value="${esc(x.title || "")}" maxlength="80">
      <span class="lbl">پیام بعد از پایان</span><input class="fa" id="p-done" value="${esc(x.done || "")}" maxlength="200">`;
  }else if(t === "pay"){
    h += `<span class="lbl">قیمت (ستاره، ۱ تا ۱۰٬۰۰۰)</span><input id="p-stars" type="number" min="1" max="10000" value="${esc(x.stars || 50)}">
      <span class="lbl">عنوان</span><input class="fa" id="p-title" value="${esc(x.title || "")}" maxlength="32">
      <span class="lbl">توضیح</span><input class="fa" id="p-desc" value="${esc(x.desc || "")}" maxlength="255">
      <span class="lbl">پیام بعد از پرداخت موفق</span><input class="fa" id="p-text" value="${esc(x.text || "")}" maxlength="300">`;
    h += actEditor("اکشن‌های بعد از پرداخت موفق", "do");
  }else if(t === "ai"){
    h += `<span class="lbl">دستور دستیار (نقش، لحن، اطلاعات کسب‌وکار)</span><textarea class="fa" id="p-prompt" maxlength="1500" style="min-height:120px">${esc(x.prompt || "")}</textarea>
      <span class="lbl">سقف پیام هر کاربر در روز</span><input id="p-daily" type="number" min="1" max="100" value="${esc(x.daily || 15)}">
      <span class="lbl">حافظه (۰ تا ۶ پیام قبلی)</span><input id="p-mem" type="number" min="0" max="6" value="${esc(x.memory ?? 3)}">
      <span class="lbl">پیام خوش‌آمد</span><input class="fa" id="p-greet" value="${esc(x.greeting || "")}" maxlength="200">
      <p class="muted mt">هر پیام دستیار از توکن‌های صاحب ربات کم می‌کند.</p>`;
  }else if(t === "links"){
    h += `<div class="sub"><span>لینک‌ها (${N(x.items.length)} از ۲۰)</span><button class="b o sm" data-a="mblinkadd"${x.items.length >= 20 ? " disabled" : ""}>${IC.plus}لینک</button></div>
      ${x.items.map((it, i) => `<div class="rl"><div class="cmd" style="justify-content:space-between"><b>لینک ${N(i + 1)}</b><button class="iconb sm" data-a="mblinkdel" data-i="${i}" aria-label="حذف">${IC.x}</button></div>
        <input class="fa lk-l" data-i="${i}" value="${esc(it.label || "")}" maxlength="40" placeholder="برچسب">
        <input class="lk-u ltr" data-i="${i}" value="${esc(it.url || "")}" placeholder="https://t.me/..."></div>`).join("")}`;
  }else if(t === "spacer"){
    h += `<span class="lbl">ارتفاع (۸ تا ۸۰)</span><input id="p-h" type="number" min="8" max="80" value="${esc(x.h || 16)}">`;
  }
  if(!["hero", "pay"].includes(t) && t !== "text"){
    h += `<span class="lbl">نمایش شرطی (اختیاری؛ مثل coins >= 10)</span>
      <div class="cmd"><input class="ltr" id="p-wvar" value="${esc(x.when?.var || "")}" maxlength="20" placeholder="متغیر" autocomplete="off">
      <select id="p-wop">${[["==","="],["!=","≠"],[">",">"],[">=",">="],["<","<"],["<=","<="],["contains","شامل"],["empty","خالی"],["filled","پر"]].map(([v, l]) => `<option value="${v}"${v === x.when?.op ? " selected" : ""}>${l}</option>`).join("")}</select></div>
      ${x.when && !["empty", "filled"].includes(x.when.op || "") ? `<input class="fa" id="p-wval" value="${esc(x.when.value || "")}" maxlength="100" placeholder="مقدار">` : ""}`;
  }
  h += `<div class="bar"><button class="b" data-sh="save">ذخیره</button></div>`;
  setTimeout(() => window.__mbPaintDo && window.__mbPaintDo(), 0);
  return h;
}

function bthemeSheet(){
  const th = MB.draft.theme;
  const presets = [["#3CCFE3", "فیروزه‌ای"], ["#6C5CE7", "بنفش"], ["#168A5B", "سبز"], ["#E39A00", "طلایی"], ["#CC3547", "قرمز"], ["#2F7CF6", "آبی"]];
  return head("تم و ظاهر") + `
    <span class="lbl">حالت</span><select id="t-mode">${[["auto", "خودکار (هماهنگ با تلگرام)"], ["dark", "تیره"], ["light", "روشن"]].map(([v, l]) => `<option value="${v}"${th.mode === v ? " selected" : ""}>${l}</option>`).join("")}</select>
    <span class="lbl">رنگ اصلی</span>
    <div class="sws">${presets.map(([c, l]) => `<button type="button" class="sw ${th.accent?.toLowerCase() === c ? "on" : ""}" style="background:${c};color:#fff" data-a="mbac" data-c="${c}">${l}</button>`).join("")}</div>
    <input id="t-accent" value="${esc(th.accent || "#3CCFE3")}" maxlength="7" class="ltr" placeholder="#3CCFE3">
    <span class="lbl">گردی گوشه‌ها (۰ تا ۲۸)</span><input id="t-rad" type="number" min="0" max="28" value="${esc(th.radius ?? 16)}">
    <span class="lbl">رقم‌ها</span><select id="t-digits"><option value="latin"${th.digits !== "fa" ? " selected" : ""}>انگلیسی</option><option value="fa"${th.digits === "fa" ? " selected" : ""}>فارسی</option></select>
    <p class="muted mt">رنگ متن روی دکمه‌ها خودکار طوری انتخاب می‌شود که خوانا باشد.</p>
    <div class="bar"><button class="b" data-sh="save">ذخیره</button></div>`;
}

function bdataSheet(){
  const cfg = S.cur.config;
  return head("داده‌های ربات") + `
    <p class="muted">این متغیرها و جدول‌ها بین چت ربات و مینی‌اپ مشترک‌اند. تغییری که اینجا می‌دهی روی کانفیگ ربات ذخیره می‌شود.</p>
    <div class="sub"><span>متغیرها</span><button class="b o sm" data-a="mbvaradd">${IC.plus}متغیر</button></div>
    <div id="b-vars">${(cfg.vars ? Object.entries(cfg.vars) : []).map(([k, v], i) => `<div class="cmd"><input class="vn" value="${esc(k)}" maxlength="20" placeholder="coins"><input class="fa vd" value="${esc(v)}" maxlength="100" placeholder="مقدار شروع"><button class="iconb sm" data-a="mbvardel" data-i="${i}" aria-label="حذف">${IC.x}</button></div>`).join("") || '<p class="muted">متغیری نداری.</p>'}</div>
    <div class="sub"><span>متغیرهای مشترک</span><button class="b o sm" data-a="mbglobadd">${IC.plus}مشترک</button></div>
    <div id="b-globs">${(cfg.globals ? Object.entries(cfg.globals) : []).map(([k, v], i) => `<div class="cmd"><input class="gn" value="${esc(k)}" maxlength="20" placeholder="stock"><input class="fa gd" value="${esc(v)}" maxlength="100" placeholder="مقدار شروع"><button class="iconb sm" data-a="mbglobdel" data-i="${i}" aria-label="حذف">${IC.x}</button></div>`).join("") || '<p class="muted">متغیر مشترکی نداری.</p>'}</div>
    <div class="bar"><button class="b" data-sh="save">ذخیره</button></div>`;
}

function bpubSheet(){
  const b = S.cur, cap = MB.caps;
  const full = !MB.pub && (cap.apps_used || 0) >= (cap.apps || 1);
  return head("انتشار مینی‌اپ") + `
    <div class="bchk">
      <div class="gi static"><span class="dot ${b.active ? "on" : ""}"></span><span class="gt"><b>ربات ${b.active ? "فعال است" : "غیرفعال است"}</b><span>${b.active ? "دکمه‌ی مینی‌اپ و منو کار می‌کنند" : "برای باز شدن مینی‌اپ از ربات، اول ربات را فعال کن"}</span></span></div>
      <div class="gi static"><span class="dot ${MB.pub ? "on" : ""}"></span><span class="gt"><b>${MB.pub ? "هم‌اکنون منتشر شده (نسخه‌ی " + N(MB.ver) + ")" : "منتشر نشده"}</b><span>${MB.pub ? "با هر انتشار، نسخه‌ی قبلی قابل بازگشت می‌ماند" : "پیش‌نویس فعلی برای همه باز می‌شود"}</span></span></div>
      <div class="gi static"><span class="dot ${hasStartAppBtn() ? "on" : ""}"></span><span class="gt"><b>دکمه‌ی ورود در ربات</b><span>${hasStartAppBtn() ? "در بخش شروع هست" : "در بخش شروع ربات نیست"}</span></span>
        ${hasStartAppBtn() ? "" : `<button class="b o sm" data-a="mblink">افزودن دکمه</button>`}</div>
    </div>
    ${full ? `<div class="aibox">سقف مینی‌اپ فعال اشتراکت پر شده (${N(cap.apps)}). یکی را لغو انتشار کن یا اشتراکت را ارتقا بده. <button class="b t" data-a="goplan">ارتقا</button></div>` : ""}
    ${MB.lint === null ? `<p class="muted" id="blint">بررسی منطق…</p>` : (MB.lint.length ? `<div class="bwarn">${MB.lint.map(x => `<p>⚠️ ${esc(x)}</p>`).join("")}</div>` : `<p class="muted">بررسی منطق: مشکلی پیدا نشد.</p>`)}
    ${MB.pub && MB.link ? `<div class="reflink"><code>${esc(MB.link)}</code><button class="b o sm" data-a="mbcopy">کپی</button></div>
      <p class="muted">این لینک مینی‌اپ را مستقیم در تلگرام باز می‌کند. دکمه‌ی منوی کنار چت ربات هم بعد از انتشار خودکار گذاشته می‌شود.</p>` : ""}
    <p class="muted mt">نکته: اگر تلگرام هنگام باز کردن مینی‌اپ خطای دامنه داد، یک بار در BotFather دستور /setmenubutton را برای رباتت با همین آدرس بزن.</p>
    <div class="bar">${MB.pub ? `<button class="b o" data-a="mbunpub">لغو انتشار</button><button class="b" data-a="mbdoPub">انتشار نسخه‌ی تازه</button>`
      : `<button class="b" data-a="mbdoPub" ${full ? "disabled" : ""}>انتشار</button>`}</div>`;
}

function baiSheet(){
  const hasDraft = MB.draft && Object.keys(MB.draft.screens || {}).length;
  return head("ساخت مینی‌اپ با هوش مصنوعی") + `
    <p class="muted">بنویس مینی‌اپ چه کاری داشته باشد؛ برای همین ربات و با متغیرها و جدول‌هایش ساخته می‌شود.</p>
    <textarea class="fa" id="ai-prompt" maxlength="4000" style="min-height:110px" placeholder="مثلاً: یک مینی‌اپ فروشگاه با صفحه‌ی محصولات، فرم سفارش و کانال ما"></textarea>
    <div id="ai-live" hidden><p class="muted"><span class="spin"></span> در حال ساخت…</p></div>
    <div id="ai-ideas"></div>
    <div class="bar"><button class="b" data-a="mbaiGo">${IC.spark}ساخت</button></div>
    ${hasDraft ? `<div class="sub"><span>یا همین مینی‌اپ را بهتر کن</span></div>
    <p class="muted">هوش مصنوعی متن‌ها را بهتر می‌کند، بلوک‌ها را مرتب می‌چیند و جاهای خالی را پر می‌کند؛ هزینه‌اش مثل یک ویرایش است.</p>
    <div class="bar"><button class="b o" data-a="mbaiBetter">${IC.spark}بهتر کن</button></div>` : ""}`;
}

function tplPrev(p){
  const b0 = (p.blocks || [])[0] || {};
  const rows = b0.items || [];
  return `<div class="tpv" style="--ac:${esc(p.accent || "#3CCFE3")}">
    <div class="tpv-tb"></div>
    ${b0.title || b0.text ? `<div class="tpv-hero"><b>${esc(b0.title || "")}</b><span>${esc(b0.text || "")}</span></div>` : ""}
    ${(rows.length ? rows.slice(0, 3) : (p.blocks || []).slice(1, 3).map(b => ({t: b.title || b.text || b.t}))).map(x => `<div class="tpv-row"><i></i><b>${esc(x.t || "")}</b><span>${esc(x.price || x.d || "")}</span></div>`).join("")}
  </div>`;
}
function btplSheet(){
  if(!MB._tpls) api("/api/app/templates").then(d => { MB._tpls = d.items; if(S.sheet?.kind === "btpl") renderSheet(); }).catch(() => { MB._tpls = []; });
  const items = MB._tpls;
  return head("قالب‌های مینی‌اپ") + (items ? (items.length ? `<div class="tplgrid">${items.map(t => `
    <div class="tplc">${t.preview ? tplPrev(t.preview) : ""}
      <div class="tplt"><span class="ib">${IC.bag}</span><div class="gt"><b>${esc(t.title)}</b><span>${esc(t.desc)}</span></div></div>
      <div class="chips">${(t.feats || []).map(f => `<span class="chip">${esc(f)}</span>`).join("")}</div>
      <div class="tplf">${t.cost ? `<span class="xbd t">${N(t.cost)} توکن</span>` : '<span class="xbd t">رایگان</span>'}
        <button class="b sm" data-a="mbtplGo" data-id="${esc(t.id)}">اعمال</button></div></div>`).join("")}</div>` : '<p class="muted">قالبی نیست.</p>')
    : '<p class="muted">در حال بارگذاری…</p>') + `<div class="fgap"></div>`;
}

function bverSheet(){
  return head("نسخه‌ها و JSON") + `
    <div class="sub"><span>نسخه‌های منتشرشده</span></div>
    ${MB.versions.length ? `<div class="group">${MB.versions.map(v => `<button class="gi" data-a="mbundoVer" data-ver="${esc(v.ver)}"><span class="ib">${IC.refresh}</span><span class="gt"><b>نسخه‌ی ${N(v.ver)}</b><span>${v.t ? new Date(v.t).toLocaleString("fa-IR-u-nu-latn", {month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"}) : ""} · بازگرداندن به پیش‌نویس</span></span>${goIc}</button>`).join("")}</div>` : '<p class="muted">هنوز نسخه‌ای ثبت نشده. هر انتشار، نسخه‌ی قبلی را نگه می‌دارد.</p>'}
    <div class="sub"><span>پشتیبان JSON</span></div>
    <textarea class="code" id="bjson" readonly></textarea>
    <div class="two mt"><button class="b o" data-a="mbjsonCopy">${IC.copy}کپی</button>
      <button class="b o" data-a="mbjsonIn">${IC.upload}ورود JSON</button></div><div class="fgap"></div>`;
}

function bstatsSheet(){
  const s = MB.stats;
  return head("آمار مینی‌اپ") + (s ? `
    <div class="stats"><div class="stat"><div class="k">باز شدن امروز</div>${N(s.today?.open || 0)}</div>
      <div class="stat"><div class="k">کاربر امروز</div>${N(s.today?.uniq || 0)}</div>
      <div class="stat"><div class="k">ثبت فرم امروز</div>${N(s.today?.form || 0)}</div>
      <div class="stat"><div class="k">پرداخت امروز</div>${N(s.today?.pay || 0)}</div></div>
    <div class="sub"><span>بلوک‌های پرلمس</span></div>
    ${(s.top || []).length ? `<div class="topn">${s.top.map(x => `<div class="tr"><span>${esc(x.name || x.block)}</span><div class="bar2"><i style="width:${Math.min(100, Math.round(x.n / Math.max(1, s.top[0].n) * 100))}%"></i></div>${N(x.n)}</div>`).join("")}</div>` : '<p class="muted">هنوز کلیکی ثبت نشده.</p>'}
    ${s.on ? "" : '<p class="muted">مینی‌اپ منتشر نشده؛ آمار بعد از انتشار جمع می‌شود.</p>'}`
    : '<p class="muted">در حال بارگذاری…</p>') + `<div class="fgap"></div>`;
}

const SHEETS_B = {
  bp: {html: bpSheet},
  bprop: {html: bpropSheet, read: bpropRead, save: bpropSave},
  btheme: {html: bthemeSheet, read: bthemeRead, save: bthemeSave},
  bdata: {html: bdataSheet, read: bdataRead, save: bdataSave},
  bpub: {html: bpubSheet},
  bai: {html: baiSheet},
  btpl: {html: btplSheet},
  bver: {html: bverSheet},
  bstats: {html: bstatsSheet},
};
Object.assign(SHEETS, SHEETS_B);

/* ── خواندن و ذخیره‌ی شیت‌ها ── */
function bpropRead(){
  const g = s => $(s)?.value ?? null;
  const t = D.t;
  if(g("#p-title") !== null) D.title = g("#p-title");
  if(g("#p-text") !== null) D.text = g("#p-text");
  if(g("#p-url") !== null) D.url = g("#p-url");
  if(g("#p-caption") !== null) D.caption = g("#p-caption");
  if(g("#p-ctatext") !== null){ D.cta = D.cta || {text: "", do: []}; D.cta.text = g("#p-ctatext"); }
  if(D.t === "gallery") D.items.forEach((it, i) => { const u = $("#p-gi-" + i); if(u) it.url = u.value; if(D["gi" + i] !== undefined) it.media = D["gi" + i]; });
  if(D.t === "cards") D.items.forEach((it, i) => {
    const ti = document.querySelector(`.c-title[data-i="${i}"]`), te = document.querySelector(`.c-text[data-i="${i}"]`), u = $("#p-ci-" + i);
    if(ti) it.title = ti.value; if(te) it.text = te.value; if(u) it.url = u.value;
    if(D["ci" + i] !== undefined) it.media = D["ci" + i];
  });
  if(D.t === "form"){
    D.title = g("#p-title") ?? D.title;
    D.fields.forEach((f, i) => {
      const lab = document.querySelector(`.f-lab[data-i="${i}"]`), k = document.querySelector(`.f-k[data-i="${i}"]`),
            ty = document.querySelector(`.f-ty[data-i="${i}"]`), rq = document.querySelector(`.f-req[data-i="${i}"]`), op = document.querySelector(`.f-opts[data-i="${i}"]`);
      if(lab) f.label = lab.value; if(k) f.k = k.value.toLowerCase().replace(/[^a-z0-9_]/g, "").replace(/^[0-9_]+/, "");
      if(ty) f.type = ty.value; if(rq) f.req = rq.checked;
      if(op) f.opts = op.value.split(/[،,]/).map(s => s.trim()).filter(Boolean);
    });
    D.save = D.save || {};
    D.save.table = g("#p-table") ?? D.save.table;
    if(!D.save.table && !D.save.vars) delete D.save.table;
    D.notify = $("#p-notify") ? $("#p-notify").checked : D.notify;
    D.ticket = $("#p-ticket") ? $("#p-ticket").checked : D.ticket;
    D.tag = g("#p-tag") ?? D.tag;
    D.done = g("#p-done") ?? D.done;
  }
  if(t === "stat" || t === "board"){ D.var = ((g("#p-var") ?? D.var) || "").toLowerCase().replace(/[^a-z0-9_]/g, ""); }
  if(t === "stat" || t === "board" || t === "list" || t === "banner" || t === "countdown" || t === "form"){
    if(t === "board"){ D.top = +g("#p-top") || 10; D.label = g("#p-label") ?? D.label; }
    if(t === "stat") D.label = g("#p-label") ?? D.label;
    if(t === "list"){ D.table = ((g("#p-table") ?? D.table) || "").toLowerCase().replace(/[^a-z0-9_]/g, ""); D.scope = g("#p-scope") ?? D.scope;
      D.limit = Math.max(1, Math.min(20, +g("#p-limit") || 10)); D.line = g("#p-line") ?? D.line; D.empty = g("#p-empty") ?? D.empty; }
    if(t === "banner") D.style = g("#p-style") ?? D.style;
    if(t === "countdown"){ const d = g("#p-date"); if(d) D.to = Math.floor(new Date(d).getTime() / 1000); D.title = g("#p-title") ?? D.title; D.done = g("#p-done") ?? D.done; }
  }
  if(t === "faq") D.items.forEach((it, i) => {
    const q = document.querySelector(`.fq-q[data-i="${i}"]`), a = document.querySelector(`.fq-a[data-i="${i}"]`);
    if(q) it.q = q.value; if(a) it.a = a.value;
  });
  if(t === "links") D.items.forEach((it, i) => {
    const l = document.querySelector(`.lk-l[data-i="${i}"]`), u = document.querySelector(`.lk-u[data-i="${i}"]`);
    if(l) it.label = l.value; if(u) it.url = u.value.trim();
  });
  if(t === "buttons"){
    D.rows.forEach((row, ri) => row.forEach((btn, ci) => {
      const el = document.querySelector(`.bt-txt[data-r="${ri}"][data-c="${ci}"]`);
      if(el) btn.text = el.value;
    }));
  }
  if(t === "pay"){ D.stars = +g("#p-stars") || 50; D.title = g("#p-title") ?? D.title; D.desc = g("#p-desc") ?? D.desc; D.text = g("#p-text") ?? D.text; }
  if(t === "ai"){ D.prompt = g("#p-prompt") ?? D.prompt; D.daily = Math.max(1, Math.min(100, +g("#p-daily") || 15)); D.memory = Math.max(0, Math.min(6, +g("#p-mem") || 0)); D.greeting = g("#p-greet") ?? D.greeting; }
  if(t === "spacer") D.h = Math.max(8, Math.min(80, +g("#p-h") || 16));
  if(g("#p-wvar") !== null){
    const wv = g("#p-wvar").trim().toLowerCase().replace(/[^a-z0-9_]/g, ""), wo = g("#p-wop"), wv2 = g("#p-wval");
    if(wv) D.when = {var: wv, op: wo, ...(wo !== "empty" && wo !== "filled" ? {value: wv2 ?? ""} : {})};
    else delete D.when;
  }
}
function bpropSave(){
  const t = D.t;
  if(t === "text" && !(D.text || "").trim()) return toast("متن را بنویس");
  if(t === "form"){
    D.fields = D.fields.filter(f => (f.label || "").trim() || (f.k || "").trim());
    if(!D.fields.length) return toast("حداقل یک فیلد لازم است");
    if(D.fields.some(f => !f.k)) return toast("نام انگلیسی همه‌ی فیلدها را بنویس");
    if(!D.save?.table) delete D.save;
    if(D.ticket && !D.save?.table) return toast("فرم تیکتی باید در جدول ذخیره شود");
  }
  if((t === "stat" || t === "board") && !D.var) return toast("نام متغیر را بنویس");
  if(t === "list" && !D.table) return toast("نام جدول را بنویس");
  if(t === "buttons") D.rows = D.rows.map(r => r.filter(b => (b.text || "").trim())).filter(r => r.length);
  if(t === "links"){ D.items = D.items.filter(i => i.label.trim() && i.url.trim()); }
  if(t === "faq") D.items = D.items.filter(i => i.q.trim() && i.a.trim());
  const i = +MB._editI;
  const arr = MB.draft.screens[MB.screen].blocks;
  arr[i] = JSON.parse(JSON.stringify(D));
  mbPush(); mbTouch();
  closeSheet();
  mbPaintBlocks();
  mbPostPreview();
  toast("ذخیره شد");
}
function bthemeRead(){
  const t = MB.draft.theme;
  t.mode = $("#t-mode")?.value ?? t.mode;
  t.accent = ($("#t-accent")?.value || t.accent || "#3CCFE3").trim();
  t.radius = Math.max(0, Math.min(28, +$("#t-rad")?.value || 16));
  t.digits = $("#t-digits")?.value ?? t.digits;
}
function bthemeSave(){ mbPush(); mbTouch(); closeSheet(); renderMiniapp(); toast("تم ذخیره شد"); }
function bdataRead(){ /* همه‌چیز در save مستقیم از DOM خوانده می‌شود */ }
function bdataSave(){
  const vars = {}, globs = {};
  document.querySelectorAll("#b-vars .cmd").forEach(r => { const k = (r.querySelector(".vn")?.value || "").trim(); if(k) vars[k] = (r.querySelector(".vd")?.value || "").trim(); });
  document.querySelectorAll("#b-globs .cmd").forEach(r => { const k = (r.querySelector(".gn")?.value || "").trim(); if(k) globs[k] = (r.querySelector(".gd")?.value || "").trim(); });
  const cfg = cp(S.cur.config);
  if(Object.keys(vars).length) cfg.vars = vars; else delete cfg.vars;
  if(Object.keys(globs).length) cfg.globals = globs; else delete cfg.globals;
  busy($('[data-sh="save"]'), async () => {
    const d = await api(`/api/bots/${S.cur.id}/config`, "PUT", {config: cfg});
    setBot(d.bot);
    closeSheet(); renderMiniapp(); toast("داده‌های ربات ذخیره شد");
  });
}

function hasStartAppBtn(){
  const cfg = S.cur?.config;
  if(!cfg) return false;
  return Object.values(cfg.nodes).some(n => (n.buttons || []).some(r => r.some(b => b.app !== undefined)));
}

/* ═════════ اکشن‌ها ═════════ */
Object.assign(A, {
  mbopen: el => busy(null, async () => {
    let b = S.bots.find(x => x.id === el.dataset.id);
    if(!b && await sync()) b = S.bots.find(x => x.id === el.dataset.id);      // ربات تازه‌ساخته‌شده ممکن است هنوز در فهرست محلی نباشد
    if(!b) return toast("ربات پیدا نشد؛ دوباره تلاش کن");
    S.cur = b; S.sbot = b.id; MB._loadedFor = null; MB.draft = null; render(); scrollTo(0, 0);
  }),
  mbrelist: () => renderMiniapp(),
  mbback: () => stGuardClose(() => { mbSaveNow(); S.cur = null; MB.draft = null; MB._loadedFor = null; closeSheet(); render(); scrollTo(0, 0); sync(); }),
  mbundo: () => mbUndo(),
  mbredo: () => mbRedo(),
  mbreload: () => { MB.draft = null; MB._loadedFor = null; renderMiniapp(); },
  mbcopy: () => navigator.clipboard?.writeText(MB.link).then(() => toast("لینک کپی شد"), () => toast(MB.link)),
  mbscr: el => { MB.screen = el.dataset.id; MB.lint = null; mbPaintScreens(); mbPaintBlocks(); mbPostPreview(); },
  mbscradd: () => {
    const id = mbNewId();
    MB.draft.screens[id] = {title: "صفحه‌ی " + (mbScreenIds().length + 1), icon: "home", blocks: []};      // عنوان متنی؛ بدون HTML
    MB.screen = id; mbPush(); mbTouch(); mbPaintScreens(); mbPaintBlocks(); mbPostPreview();
  },
  mbscrsave: () => {
    const s = MB.draft.screens[MB.screen];
    if(!s) return closeSheet();
    const t = ($("#sc-title")?.value || "").trim().slice(0, 40);
    if(t) s.title = t;
    if($("#sc-icon")) s.icon = $("#sc-icon").value;
    mbPush(); mbTouch(); closeSheet(); mbPaintScreens(); mbPaintBlocks(); mbPostPreview(); toast("صفحه ذخیره شد");
  },
  mbscredit: () => {
    const s = MB.draft.screens[MB.screen];
    S.sheet = {kind: "info"};
    D = null;
    showSheet(head("ویرایش صفحه") + `
      <span class="lbl">عنوان</span><input class="fa" id="sc-title" value="${esc(s.title || "")}" maxlength="40">
      <span class="lbl">آیکن (در منوی پایین)</span><select id="sc-icon">${[["home", "خانه"], ["shop", "فروشگاه"], ["form", "فرم"], ["star", "ستاره"], ["info", "اطلاعات"], ["users", "کاربران"], ["phone", "تماس"], ["image", "تصویر"], ["chat", "گفتگو"], ["gift", "هدیه"], ["clock", "زمان"], ["trophy", "جایزه"]].map(([v, l]) => `<option value="${v}"${s.icon === v ? " selected" : ""}>${l}</option>`).join("")}</select>
      <div class="bar"><button class="b" data-a="mbscrsave">ذخیره</button></div>
      ${MB.screen !== MB.draft.home ? `<button class="b o" data-a="mbscrhome">صفحه‌ی شروع مینی‌اپ شود</button>
      <button class="b r mt" data-a="mbscrdel">حذف این صفحه</button>` : `<p class="muted mt">این صفحه، صفحه‌ی شروع مینی‌اپ است.</p>`}
      <div class="fgap"></div>`);
  },
  mbnav: () => {
    const items = MB.draft.nav.items || [], i = items.indexOf(MB.screen);
    if(i >= 0) items.splice(i, 1); else if(items.length < 6) items.push(MB.screen); else return toast("منوی پایین حداکثر ۶ صفحه دارد");
    MB.draft.nav.type = items.length ? "tabs" : "none";
    mbPush(); mbTouch(); mbPaintScreens(); mbPostPreview();
  },
  mbadd: () => { S.sheet = {kind: "bp"}; D = null; renderSheet(); },
  mbpick: el => {
    const t = el.dataset.t;
    if((MB.draft.screens[MB.screen].blocks || []).length >= (MB.caps.blocks || 30)) return toast("سقف بلوک اشتراکت پر شده");
    const blk = mbDefaultBlock(t);
    (MB.draft.screens[MB.screen].blocks = MB.draft.screens[MB.screen].blocks || []).push(blk);
    MB._editI = (MB.draft.screens[MB.screen].blocks.length - 1);
    mbPush(); mbTouch();
    D = cp(blk);
    S.sheet = {kind: "bprop"};
    renderSheet();
    mbPaintBlocks();
  },
  mbedit: el => { const x = mbFindBlock(el.dataset.i); if(!x) return; MB._editI = el.dataset.i; D = cp(x); S.sheet = {kind: "bprop"}; renderSheet(); },
  mbup: el => { const arr = MB.draft.screens[MB.screen].blocks, i = +el.dataset.i; if(i <= 0) return; [arr[i - 1], arr[i]] = [arr[i], arr[i - 1]]; mbPush(); mbTouch(); mbPaintBlocks(); mbPostPreview(); },
  mbdown: el => { const arr = MB.draft.screens[MB.screen].blocks, i = +el.dataset.i; if(i >= arr.length - 1) return; [arr[i + 1], arr[i]] = [arr[i], arr[i + 1]]; mbPush(); mbTouch(); mbPaintBlocks(); mbPostPreview(); },
  mbcp: el => {
    const arr = MB.draft.screens[MB.screen].blocks, i = +el.dataset.i;
    if(arr.length >= (MB.caps.blocks || 30)) return toast("سقف بلوک اشتراکت پر شده");
    const c = cp(arr[i]); c.id = "";
    arr.splice(i + 1, 0, c);
    const used = new Set(); Object.values(MB.draft.screens).forEach(s => (s.blocks || []).forEach(b => b.id && used.add(b.id)));
    let n = used.size + 1; while(used.has("b" + n)) n++;
    c.id = "b" + n;
    mbPush(); mbTouch(); mbPaintBlocks(); mbPostPreview(); toast("کپی شد");
  },
  mbdel: el => {
    const arr = MB.draft.screens[MB.screen].blocks, i = +el.dataset.i;
    const removed = arr.splice(i, 1)[0];
    mbPush(); mbTouch(); mbPaintBlocks(); mbPostPreview();
    toast("حذف شد؛ با برگشت برمی‌گردد");
  },
  mbtheme: () => { S.sheet = {kind: "btheme"}; D = null; renderSheet(); },
  mbdata: () => { S.sheet = {kind: "bdata"}; D = null; renderSheet(); },
  mbver: async () => { S.sheet = {kind: "bver"}; D = null; renderSheet(); const j = $("#bjson"); if(j) j.value = JSON.stringify(MB.draft, null, 2); },
  mbstats: async () => { S.sheet = {kind: "bstats"}; D = null; renderSheet();
    try{ MB.stats = await api(`/api/bots/${S.cur.id}/app/stats`); if(S.sheet?.kind === "bstats") renderSheet(); }catch(e){ toast(e.message); } },
  mbpub: async () => {
    MB.lint = null;
    S.sheet = {kind: "bpub"}; D = null; renderSheet();
    try{ const d = await api(`/api/bots/${S.cur.id}/app/lint`); MB.lint = d.issues || []; if(S.sheet?.kind === "bpub") renderSheet(); }catch(_){}
  },
  mblink: el => busy(el, async () => {
    const d = await api(`/api/bots/${S.cur.id}/app/link`, "POST");
    await sync(); toast(d.added === false ? "دکمه از قبل هست" : "دکمه به بخش شروع اضافه شد");
    if(S.sheet?.kind === "bpub") renderSheet();
  }),
  mbdoPub: el => busy(el, async () => {
    if(MB._dirty) await mbSave();
    const d = await api(`/api/bots/${S.cur.id}/app/publish`, "POST");
    MB.pub = true; MB.ver = d.ver; MB.link = d.link || MB.link;
    if(d.warns?.length) toast(d.warns[0]);
    toast("منتشر شد");
    haptic("ok");
    closeSheet(); renderMiniapp();
  }),
  mbunpub: el => busy(el, async () => {
    await api(`/api/bots/${S.cur.id}/app/unpublish`, "POST");
    MB.pub = false;
    toast("لغو انتشار شد");
    closeSheet(); renderMiniapp();
  }),
  mbundoVer: el => busy(el, async () => {
    const d = await api(`/api/bots/${S.cur.id}/app/undo`, "POST");
    MB.draft = d.draft; MB.screen = MB.draft.home; mbPush(); mbTouch();
    closeSheet(); renderMiniapp(); toast("به پیش‌نویس برگشت");
  }),
  mbjsonCopy: () => { const t = $("#bjson"); t.select(); navigator.clipboard?.writeText(t.value).then(() => toast("کپی شد"), () => {}); },
  mbjsonIn: () => {
    const j = $("#bjson");
    j.removeAttribute("readonly");
    j.value = "";
    j.placeholder = "JSON مینی‌اپ را اینجا بچسبان و دوباره دکمه را بزن";
    j.focus();
    if(j.dataset.in){ 
      try{ MB.draft = JSON.parse(j.value); mbPush(); mbTouch(); closeSheet(); renderMiniapp(); toast("JSON وارد شد"); }
      catch(e){ toast("JSON نامعتبر است"); }
    }else j.dataset.in = "1";
  },
  mbai: () => { S.sheet = {kind: "bai"}; D = null; renderSheet(); },
  mbaiBetter: el => busy(el, async () => {
    try{
      const d = await api(`/api/bots/${S.cur.id}/app/ai`, "POST", {});
      if(d.wallet) S.wallet = d.wallet;
      MB.draft = d.draft; MB.screen = MB.draft.home || MB.screen;
      mbPush(); mbTouch();
      closeSheet(); renderMiniapp();
      toast("مینی‌اپ بهتر شد" + (d.cost ? ` · ${d.cost} توکن` : ""));
      haptic("ok");
    }catch(e){ toast(e.message || "بهبود ناموفق بود"); }
  }),
  mbaiGo: el => {
    const p = $("#ai-prompt").value.trim();
    if(p.length < 5) return toast("توضیح بیشتری بنویس");
    busy(el, async () => {
      $("#ai-live").hidden = false;
      try{
        const d = await api(`/api/bots/${S.cur.id}/app/generate`, "POST", {prompt: p});
        for(let i = 0; i < 120; i++){
          await sleep(1000);
          const r = await api(`/api/appjobs/${d.job}`);
          if(r.status === "done"){
            $("#ai-live").hidden = true;
            MB.draft = r.app; MB.screen = MB.draft.home;
            mbPush(); mbTouch();
            closeSheet(); renderMiniapp();
            toast("مینی‌اپ ساخته شد" + (r.cost ? `، ${r.cost} توکن` : ""));
            haptic("ok");
            if(r.thinking) toast(r.thinking.slice(0, 90));
            return;
          }
          if(r.status === "error"){ $("#ai-live").hidden = true; return toast(r.error || "ناموفق بود"); }
        }
        $("#ai-live").hidden = true;
        toast("ساخت طول کشید؛ دوباره امتحان کن");
      }catch(e){ $("#ai-live").hidden = true; toast(e.message); }
    });
  },
  mbtpl: () => { S.sheet = {kind: "btpl"}; D = null; renderSheet(); },
  mbtplGo: el => busy(el, async () => {
    const t = (MB._tpls || []).find(x => x.id === el.dataset.id);
    if(t?.cost && S.wallet.tokens < t.cost) return openBuy(`این قالب ${t.cost} توکن می‌خواهد`);
    const d = await api(`/api/bots/${S.cur.id}/app/template`, "POST", {id: el.dataset.id});
    if(d.wallet) S.wallet = d.wallet;
    MB.draft = d.draft; MB.screen = MB.draft.home;
    mbPush(); mbTouch();
    closeSheet(); renderMiniapp(); renderTop();
    toast("قالب اعمال شد؛ الان شخصی‌سازی‌اش کن");
    haptic("ok");
  }),
  mbvaradd: () => { const r = document.createElement("div"); r.className = "cmd"; r.innerHTML = `<input class="vn" placeholder="coins" maxlength="20"><input class="fa vd" placeholder="مقدار شروع"><button class="iconb sm" data-a="mbvardel" aria-label="حذف">${IC.x}</button>`; $("#b-vars").appendChild(r); },
  mbvardel: el => el.closest(".cmd").remove(),
  mbglobadd: () => { const r = document.createElement("div"); r.className = "cmd"; r.innerHTML = `<input class="gn" placeholder="stock" maxlength="20"><input class="fa gd" placeholder="مقدار شروع"><button class="iconb sm" data-a="mbglobdel" aria-label="حذف">${IC.x}</button>`; $("#b-globs").appendChild(r); },
  mbglobdel: el => el.closest(".cmd").remove(),
  mbac: el => { const i = $("#t-accent"); if(i){ i.value = el.dataset.c; document.querySelectorAll(".sws .sw.on").forEach(x => x.classList.remove("on")); el.classList.add("on"); } },
  mbgaladd: () => { D.items.push({url: ""}); renderSheet(); },
  mbgaldel: el => { D.items.splice(+el.dataset.i, 1); renderSheet(); },
  mbcardadd: () => { D.items.push({title: "", text: ""}); renderSheet(); },
  mbcarddel: el => { D.items.splice(+el.dataset.i, 1); renderSheet(); },
  mbfldadd: () => { D.fields.push({k: "", label: "", type: "text"}); renderSheet(); },
  mbflddel: el => { D.fields.splice(+el.dataset.i, 1); renderSheet(); },
  mbfaqadd: () => { D.items.push({q: "", a: ""}); renderSheet(); },
  mbfaqdel: el => { D.items.splice(+el.dataset.i, 1); renderSheet(); },
  mblinkadd: () => { D.items.push({label: "", url: ""}); renderSheet(); },
  mblinkdel: el => { D.items.splice(+el.dataset.i, 1); renderSheet(); },
  mbrowadd: () => { D.rows.push([]); renderSheet(); },
  mbbtadd: el => { D.rows[+el.dataset.r].push({text: "دکمه", do: [{op: "goto", screen: MB.draft.home}]}); renderSheet(); },
  mbbtdel: el => { const r = +el.dataset.r, c = +el.dataset.c; D.rows[r].splice(c, 1); if(!D.rows[r].length) D.rows.splice(r, 1); renderSheet(); },
  mbdoadd: el => {
    const arr = mbDoArr(el.dataset.k, true);
    arr.push({op: "goto", screen: MB.draft.home});
    window.__mbPaintDo && window.__mbPaintDo();
  },
  mbdodel: el => {
    const arr = mbDoArr(el.dataset.k);
    arr.splice(+el.dataset.i, 1);
    window.__mbPaintDo && window.__mbPaintDo();
  },
  mbscrhome: () => { MB.draft.home = MB.screen; mbPush(); mbTouch(); closeSheet(); mbPaintScreens(); toast("صفحه‌ی شروع عوض شد"); },
  mbscrdel: () => {
    confirmQ("این صفحه و بلوک‌هایش حذف شود؟", ok => {
      if(!ok) return;
      delete MB.draft.screens[MB.screen];
      MB.draft.nav.items = (MB.draft.nav.items || []).filter(x => x !== MB.screen);
      MB.screen = MB.draft.home;
      mbPush(); mbTouch(); closeSheet(); mbPaintScreens(); mbPaintBlocks(); mbPostPreview();
    });
  },
});
function mbSaveNow(){ if(MB._dirty) mbSave(); }

/* تغییر نوع اکشن داخل ویرایشگر هندلر */
/* ردیف بلوک div است (دکمه داخل دکمه ممنوع)؛ با کیبورد هم باز می‌شود */
document.addEventListener("keydown", e => {
  if(e.key !== "Enter" && e.key !== " ") return;
  const r = e.target.closest?.(".bblk");
  if(r){ e.preventDefault(); A.mbedit(r); }
});
document.addEventListener("change", e => {
  if(!e.target.classList?.contains("d-op") || S.sheet?.kind !== "bprop") return;
  const row = e.target.closest(".rl"), i = +row.dataset.i;
  const key = row.closest(".mbdo")?.dataset.k;
  const arr = mbDoArr(key);
  const op = e.target.value, a = arr[i] || (arr[i] = {});
  a.op = op;
  delete a.screen; delete a.url; delete a.text; delete a.node; delete a.var; delete a.value; delete a.minutes;
  if(op === "goto") a.screen = MB.draft.home;
  if(op === "set" || op === "add" || op === "clear" || op === "random") a.var = "";
  if(op === "set" || op === "add" || op === "random" || op === "notify" || op === "remind") a.value = a.value ?? "";
  if(op === "remind") a.minutes = 60;
  window.__mbPaintDo && window.__mbPaintDo();
});

/* ثبت صفحه‌ی مینی‌اپ‌ساز (VIEWS در app.js تعریف می‌شود) */
VIEWS.miniapp = renderMiniapp;
