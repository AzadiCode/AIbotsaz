/* ═══════════════════════════════════════════════════════════════
   studio3.js — تکمیل استودیو (بعد از studio2.js): نوار «کجا کار می‌کنه؟»، بسته‌های
   یک‌ضربه‌ای، شیت پست کانال، شیت اتصال‌ها (اینلاین/وب‌هوک/RSS)، یادداشت و قاب رنگی بخش‌ها
   (فقط داخل استودیو)، ماشه‌های ری‌اکشن/منشن در وقتی…آنگاه، حالت‌های هوش مصنوعی و
   اجرای همه‌ی سناریوها قبل از انتشار.
   ═══════════════════════════════════════════════════════════════ */
"use strict";

/* ── نوار «کجا کار می‌کنه؟» ── */
function sc3Scopes(){
  const cfg = S.cur?.config || {};
  return [
    ["pv", "چت خصوصی", true, null],
    ["group", "گروه", !!(cfg.mod || (cfg.group || {}).triggers || cfg.growth || cfg.games || cfg.digest), "wtopen"],
    ["channel", "کانال", !!(cfg.channelpost || cfg.rss || (cfg.mod || {}).channel), "chanopen"],
    ["app", "مینی‌اپ", !!(cfg.nodes || {}) && Object.values(cfg.nodes || {}).some(n => (n.buttons || []).flat().some(b => b.app !== undefined)), null],
  ];
}
function scopeBarInject(){
  const host = $("#stc");
  if(!host || $("#scopebar")) return;
  const on = sc3Scopes().filter(s => s[2]).map(s => `<span class="chip sc3on">${s[1]}</span>`).join("");
  host.insertAdjacentHTML("afterbegin", `<div class="scopebar" id="scopebar"><span class="muted">کار می‌کند در:</span>${on}</div>`);
}
const _VIEWS_STUDIO0 = VIEWS.studio;
VIEWS.studio = function(){ _VIEWS_STUDIO0(); scopeBarInject(); };

/* ── یادداشت و قاب رنگی بخش‌ها (فقط داخل استودیو، بدون تغییر کانفیگ) ── */
function sc3notes(){
  try{ return JSON.parse(localStorage.getItem("azadi.notes." + (S.cur?.id || "")) || "{}"); }catch(_){ return {}; }
}
function sc3saveNotes(n){
  try{ localStorage.setItem("azadi.notes." + (S.cur?.id || ""), JSON.stringify(n)); }catch(_){}
}
const _stCardSafe0 = stCardSafe;
stCardSafe = function(id, dead){
  let h = _stCardSafe0(id, dead);
  const n = sc3notes()[id];
  if(n){
    if(n.frame) h = h.replace('class="stc-card"', `class="stc-card stfr-${n.frame}"`);
    if(n.note) h = h.replace("</small></button>", `</small><i class="stnote">${esc(n.note)}</i></button>`);
  }
  return h;
};
const _origStPaintWorld3 = stPaintWorld;
stPaintWorld = function(){ _origStPaintWorld3(); document.querySelectorAll("#stw .stc-card").forEach(c => { const n = sc3notes()[c.dataset.id]; if(n?.frame) c.classList.add("stfr-" + n.frame); }); };

Object.assign(SHEETS, {
  note: {html(){
    const id = S.sheet.id, n = sc3notes()[id] || {};
    return head("یادداشت و قاب بخش") + `
      <span class="lbl">یادداشت خصوصی (فقط خودت می‌بینی)</span><input class="fa" id="nt-note" value="${esc(n.note || "")}" maxlength="100" placeholder="مثلاً: بعد از جلسه پرش کن">
      <span class="lbl">قاب رنگی روی نقشه</span><div class="sws">
      ${[["", "بدون"], ["red", "قرمز"], ["green", "سبز"], ["blue", "آبی"], ["amber", "طلایی"], ["violet", "بنفش"]].map(([v, l]) => `<button type="button" class="sw ${(n.frame || "") === v ? "on" : ""}" data-a="ntframe" data-v="${v}">${l}</button>`).join("")}</div>
      <div class="bar"><button class="b" data-a="ntsave">ذخیره</button></div><div class="fgap"></div>`;
  }},
});
Object.assign(A, {
  ntop: el => { S.sheet = {kind: "note", id: el.dataset.n}; D = null; renderSheet(); },
  ntframe: el => { const i = $("#nt-cur"); S2._fr = el.dataset.v; document.querySelectorAll(".sws .sw.on").forEach(x => { if(x.closest && x.parentElement.previousElementSibling?.textContent?.includes("قاب")) x.classList.remove("on"); }); el.classList.add("on"); },
  ntsave: () => {
    const id = S.sheet.id, notes = sc3notes();
    notes[id] = {note: ($("#nt-note")?.value || "").trim(), frame: S2._fr != null ? S2._fr : ((notes[id] || {}).frame || "")};
    if(!notes[id].note && !notes[id].frame) delete notes[id];
    sc3saveNotes(notes); S2._fr = undefined;
    closeSheet(); stPaintWorld(); toast("ذخیره شد");
  },
});
/* دکمه‌ی یادداشت در منوی هر کارت نقشه */
const _stCardMenu0 = stCardMenu;
stCardMenu = function(id){
  _stCardMenu0(id);
  const sh = $("#sheet .sh");
  if(sh) sh.insertAdjacentHTML("afterend", `<button class="b o sm" data-a="ntop" data-n="${esc(id)}" style="margin:8px 12px 0">${S2IC.diff}یادداشت و قاب</button>`);
};

/* ── بسته‌های آماده‌ی یک‌ضربه‌ای ── */
const SC3_PACKS = [
  ["welcome", "خوش‌آمد", "بخش خوش‌آمد با قوانین و بازگشت", [["welcome", "سلام {name} عزیز 👋\nبه ربات ما خوش اومدی!\nقوانین رو رعایت کن تا همیشه خوش بگذره.", [["📜 قوانین", "rules"], ["🏠 شروع", "@start"]]], ["rules", "📜 <b>قوانین</b>\n۱) احترام\n۲) بدون تبلیغ\n۳) اسپم ممنوع", [["🏠 منوی اصلی", "@start"]]]]],
  ["faq", "پرسش‌های متداول", "۶ پرسش و پاسخ آماده", [["faq", "<b>سؤالات متداول</b>", [["🕐 ساعات کاری", "@start"], ["🏠 منوی اصلی", "@start"]]]]],
  ["contact", "فرم تماس", "فرم تماس با تیکت شماره‌دار", [["contact", "پیامت رو بنویس؛ سریع جواب می‌دیم.", [["🏠 منوی اصلی", "@start"]]]]],
  ["poll", "نظرسنجی", "بخش نظرسنجی با گزینه‌ها", [["poll", "نظرت رو با دکمه‌ها بگو 👇", [["🏠 منوی اصلی", "@start"]]]]],
  ["shop", "منوی فروشگاه", "دسته‌ها، محصول و سفارش", [["shop", "<b>🛍 فروشگاه</b>\nاز دسته‌ها شروع کن:", [["🛒 سفارش", "order"], ["🏠 منوی اصلی", "@start"]]], ["order", "سفارش: اسم و شماره‌ات رو بنویس.", [["🛍 فروشگاه", "shop"]]]]],
  ["board", "رتبه‌بندی", "جدول برترین‌ها بر اساس امتیاز", [["board", "🏆 <b>برترین‌های امروز</b>", [["🏠 منوی اصلی", "@start"]]]]],
];
function packsSheet(){
  return head("بسته‌های آماده") + `
    <p class="muted">هر بسته چند بخش آماده به ربات اضافه می‌کند؛ بعداً همه‌چیزش قابل ویرایش است.</p>
    <div class="bpg">${SC3_PACKS.map(([id, t, d], i) => `<button class="bpc" data-a="packgo" data-i="${i}"><span class="bpr"><span class="bpi">${IC.spark}</span><span class="bpt"><b>${esc(t)}</b><span>${esc(d)}</span></span></span></button>`).join("")}</div><div class="fgap"></div>`;
}
Object.assign(SHEETS, {packs: {html: packsSheet}});
Object.assign(A, {
  packsopen: () => { if(!S.cur) return toast("اول یک ربات انتخاب کن"); S.sheet = {kind: "packs"}; D = null; renderSheet(); },
  packgo: el => {
    const pk = SC3_PACKS[+el.dataset.i];
    if(!pk) return;
    busy(el, () => commit(cfg => {
      const nodes = cfg.nodes;
      let k = Object.keys(nodes).length + 1;
      const nid = p => { let id2 = p; while(nodes[id2]) id2 = p + "_" + (k++); return id2; };
      for(const [pid, text, btns] of pk[3]){
        const id2 = nid(pid);
        nodes[id2] = {text, title: pk[1] + " " + id2, ask: false, buttons: []};
        for(const [lb, tgt] of btns){
          const dest = tgt === "@start" ? cfg.start : nid(tgt);
          nodes[id2].buttons.push([{text: lb, goto: dest}]);
        }
      }
      if(pk[0] === "contact"){ const n = Object.entries(nodes).find(([k2]) => k2.startsWith("contact")); if(n){ n[1].ask = true; n[1].ticket = true; } }
      if(pk[0] === "poll"){ const n = Object.entries(nodes).find(([k2]) => k2.startsWith("poll")); if(n){ n[1].buttons = [[{"text": "👍 خوب", "alert": "مرسی از رأیت!"}, {"text": "👎 بد", "alert": "بهترش می‌کنیم!"}]]; } }
      if(pk[0] === "faq"){ const n = Object.entries(nodes).find(([k2]) => k2.startsWith("faq")); if(n) n[1].text = "<b>سؤالات متداول</b>\nساعت کاری: ۹ تا ۲۱\nارسال: ۲ روز کاری\nمرجوعی: تا ۷ روز"; }
      if(pk[0] === "board"){ const n = Object.entries(nodes).find(([k2]) => k2.startsWith("board")); if(n){ n[1].board = {var: "points", top: 10, label: "برترین‌ها"}; cfg.vars = {...(cfg.vars || {}), points: "0"}; } }
    }, `بسته‌ی «${pk[1]}» اضافه شد`));
  },
});

/* ── شیت پست کانال ── */
Object.assign(SHEETS, {
  chan: {html(){
    const c = S.cur.config.channelpost || {};
    return head("پست کانال") + `
      <p class="muted">پست‌ها را داخل چت ربات با دستور <b dir="ltr">/post</b> بنویس؛ کارت تأیید برای تو (و پشتیبان‌ها) می‌آید و در زمان انتخابی به کانال می‌رود.</p>
      <label class="chk"><input type="checkbox" id="cp-on"${c.on ? " checked" : ""}> فعال باشد</label>
      <span class="lbl">کانال مقصد (@نام یا -100…)</span><input class="ltr" id="cp-chat" value="${esc(c.chat || "")}" placeholder="@mychannel">
      <label class="chk"><input type="checkbox" id="cp-appr"${c.approve !== false ? " checked" : ""}> انتشار فقط بعد از تأیید مدیر</label>
      <span class="lbl">دکمه‌ی زیر پست (اختیاری)</span>
      <div class="cmd"><input class="fa" id="cp-bt" value="${esc(c.btn_text || "")}" maxlength="24" placeholder="متن دکمه"><input class="lk-u ltr" id="cp-bu" value="${esc(c.btn_url || "")}" placeholder="https://..."></div>
      <span class="lbl">نظرسنجی خودکار زیر پست (اختیاری)</span>
      <input class="fa" id="cp-pq" value="${esc(c.poll_q || "")}" maxlength="100" placeholder="سؤال نظرسنجی">
      <input class="fa" id="cp-po" value="${esc((c.poll_opts || []).join("، "))}" maxlength="140" placeholder="گزینه‌ها با ویرگول (حداقل ۲)">
      <div class="bar"><button class="b" data-sh="save">ذخیره</button></div><div class="fgap"></div>`;
  }, save(){
    const on = $("#cp-on")?.checked, chat = ($("#cp-chat")?.value || "").trim();
    if(on && !/^(@[A-Za-z][A-Za-z0-9_]{4,31}|-100\d{5,15})$/.test(chat)) return toast("شناسه‌ی کانال معتبر نیست");
    busy($('[data-sh="save"]'), () => commit(cfg => {
      if(!on){ delete cfg.channelpost; return; }
      cfg.channelpost = {on: true, chat, approve: $("#cp-appr")?.checked !== false};
      const bt = ($("#cp-bt")?.value || "").trim(), bu = ($("#cp-bu")?.value || "").trim();
      if(bt && bu){ cfg.channelpost.btn_text = bt; cfg.channelpost.btn_url = bu; }
      const pq = ($("#cp-pq")?.value || "").trim();
      const po = ($("#cp-po")?.value || "").split(/[,،]/).map(x => x.trim()).filter(Boolean);
      if(pq && po.length >= 2){ cfg.channelpost.poll_q = pq; cfg.channelpost.poll_opts = po; }
    }, "پست کانال ذخیره شد؛ ربات را ادمین کانال کن (با اجازه‌ی ارسال)"));
  }},
});

/* ── شیت اتصال‌ها: اینلاین، وب‌هوک ورودی، RSS ── */
Object.assign(SHEETS, {
  conn: {html(){
    const cfg = S.cur.config;
    const inl = cfg.inline || {}, wb = cfg.webin || {}, rss = cfg.rss || {};
    return head("اتصال‌ها") + `
      <details class="adv" open><summary>جستجوی اینلاین ربات (پاسخ از یک جدول)</summary><div class="box">
        <label class="chk"><input type="checkbox" id="in-on"${inl.on ? " checked" : ""}> فعال باشد (کاربر از هر چتی می‌تواند جستجو کند)</label>
        <span class="lbl">نام جدول و فیلدها (مثل prods / name / desc / url)</span>
        <div class="cmd"><input class="ltr" id="in-tab" value="${esc(inl.table || "")}" maxlength="20" placeholder="prods"><input class="ltr" id="in-tf" value="${esc(inl.title_f || "title")}" maxlength="20" placeholder="name"></div>
        <div class="cmd"><input class="ltr" id="in-df" value="${esc(inl.desc_f || "")}" maxlength="20" placeholder="desc"><input class="ltr" id="in-uf" value="${esc(inl.url_f || "")}" maxlength="20" placeholder="url"></div>
      </div></details>
      <details class="adv" open><summary>وب‌هوک ورودی (رخداد از سایت یا اپ بیرونی)</summary><div class="box">
        <label class="chk"><input type="checkbox" id="wb-on"${wb.on ? " checked" : ""}> فعال باشد</label>
        <span class="lbl">ذخیره در جدول</span><input class="ltr" id="wb-tab" value="${esc(wb.table || "hooks")}" maxlength="20" placeholder="hooks">
        <label class="chk"><input type="checkbox" id="wb-nt"${wb.notify !== false ? " checked" : ""}> هر رخداد به من خبر بده</label>
        <button class="b o sm" data-a="wblink">${IC.copy}دیدن آدرس وب‌هوک</button><div id="wb-url"></div>
      </div></details>
      <details class="adv" open><summary>RSS (اخبار خودکار در کانال/گروه)</summary><div class="box">
        <label class="chk"><input type="checkbox" id="rs-on"${rss.on ? " checked" : ""}> فعال باشد</label>
        <span class="lbl">آدرس منبع RSS</span><input class="ltr" id="rs-u" value="${esc(rss.url || "")}" placeholder="https://site.ir/feed">
        <span class="lbl">مقصد (@کانال یا @گروه — ربات ادمین باشد)</span><input class="ltr" id="rs-c" value="${esc(rss.chat || "")}" placeholder="@mychannel">
        <span class="lbl">بازه‌ی چک (دقیقه، ۱۰ تا ۱۴۴۰)</span><input class="ltr" id="rs-m" inputmode="numeric" value="${fa(rss.mins || 30)}">
      </div></details>
      <div class="bar"><button class="b" data-sh="save">ذخیره</button></div><div class="fgap"></div>`;
  }, save(){
    busy($('[data-sh="save"]'), () => commit(cfg => {
      if($("#in-on")?.checked){
        const tab = ($("#in-tab")?.value || "").toLowerCase().replace(/[^a-z0-9_]/g, "");
        if(tab) cfg.inline = {on: true, table: tab, title_f: cleanVar($("#in-tf")?.value) || "title", desc_f: cleanVar($("#in-df")?.value), url_f: cleanVar($("#in-uf")?.value)};
      } else delete cfg.inline;
      if($("#wb-on")?.checked){
        const tab = ($("#wb-tab")?.value || "hooks").toLowerCase().replace(/[^a-z0-9_]/g, "");
        if(tab) cfg.webin = {on: true, table: tab, notify: $("#wb-nt")?.checked !== false};
      } else delete cfg.webin;
      if($("#rs-on")?.checked){
        const u = ($("#rs-u")?.value || "").trim(), c = ($("#rs-c")?.value || "").trim();
        if(/^https:\/\//.test(u) && /^(@[A-Za-z][A-Za-z0-9_]{4,31}|-100\d{5,15})$/.test(c))
          cfg.rss = {on: true, url: u, chat: c, mins: Math.max(10, Math.min(1440, parseInt(($("#rs-m")?.value || "30").replace(/[۰-۹]/g, d => "۰۱۲۳۴۵۶۷۸۹".indexOf(d))) || 30))};
      } else delete cfg.rss;
    }, "اتصال‌ها ذخیره شد"));
  }},
});
Object.assign(A, {
  chanopen: () => { if(!S.cur) return toast("اول یک ربات انتخاب کن"); S.sheet = {kind: "chan"}; D = null; renderSheet(); },
  connopen: () => { if(!S.cur) return toast("اول یک ربات انتخاب کن"); S.sheet = {kind: "conn"}; D = null; renderSheet(); },
  wblink: async () => {
    try{
      const d = await api(`/api/bots/${S.cur.id}/webin`);
      $("#wb-url").innerHTML = d.on ? `<div class="reflink" style="margin-top:8px"><code>${esc(d.url)}</code><button class="b o sm" data-a="wbcopy">کپی</button></div><p class="muted">این آدرس را به سایت یا اپ بیرونی بده؛ هر رخداد در جدول ربات ذخیره می‌شود.</p>` : `<p class="muted">اول فعالش کن و ذخیره بزن.</p>`;
    }catch(e){ toast(e.message); }
  },
  wbcopy: () => { const c = $("#wb-url code"); if(c) navigator.clipboard?.writeText(c.textContent).then(() => toast("کپی شد"), () => {}); },
});

/* ── ماشه‌های ری‌اکشن و منشن در وقتی…آنگاه ── */
const _wtSheet0 = SHEETS.wt.html;
SHEETS.wt.html = function(){
  let h = _wtSheet0();
  h = h.replace(`<option value="${"command"}"${"command" === "command" ? " selected" : ""}>`,
                `<option value="${"command"}"${"command" === "command" ? " selected" : ""}>`);
  h = h.replace('</select>\n    <span class="lbl">کلمه یا کلمه‌ها',
    `<option value="reaction">وقتی کسی به پیام واکنش داد</option><option value="mention">وقتی ربات منشن شد (جواب عامل)</option></select>
    <span id="w-mentionbox" hidden><span class="lbl">بخش گفتگوی هوشمند که جواب می‌دهد</span><select id="w-ainode">${Object.entries(S.cur.config.nodes).filter(([, n]) => n.ai).map(([id, n]) => `<option value="${esc(id)}">${esc(n.title || id)}</option>`).join("")}</select></span>
    <span class="lbl">کلمه یا کلمه‌ها`);
  return h;
};
document.addEventListener("change", e => {
  if(e.target.id === "w-on"){
    const box = $("#w-mentionbox"), words = e.target.closest(".wtc")?.querySelector('[id="w-words"]');
    if(box) box.hidden = e.target.value !== "mention";
    if(words){ const lab = words.previousElementSibling; if(lab) lab.textContent = e.target.value === "reaction" ? "ایموجی واکنش‌ها (با ویرگول، مثل 👍،❤️)" : "کلمه یا کلمه‌ها (با ویرگول)"; }
  }
});
const _wtReadEdit0 = wtReadEdit;
wtReadEdit = function(){
  _wtReadEdit0();
  const t = D.new;
  if(t && t.on === "mention"){
    const n = $("#w-ainode")?.value;
    if(n) t.ai = n;
    t.words = "";
  }
};
const _wtSaveAll0 = wtSaveAll;
wtSaveAll = function(){
  const trsBak = D.trs;
  for(let i = 0; i < D.trs.length; i++) if(D.trs[i].on === "mention") D.trs[i].words = "—";
  _wtSaveAll0();
  D.trs = trsBak;
};
const _wtNew0 = wtTriggerBlank;
wtTriggerBlank = function(){ const t = _wtNew0(); return t; };
const _wtSaveAllRules = wtSaveAll;
/* واکنش/منشن: کلمه اجباری نیست */
wtSaveAll = function(){
  const savedTrs = [];
  for(let i = 0; i < D.trs.length; i++){
    if(D.del[i]) continue;
    const t = D.trs[i];
    if((t.on === "mention")){
      savedTrs.push({on: "mention", words: [], reply: (t.reply || "").trim(), do: [], ai: t.ai, cooldown: +t.cooldown || 0});
      continue;
    }
    if(t.on === "reaction"){
      const ws = t.words.split(/[,،\n]+/).map(x => x.trim()).filter(Boolean);
      if(!ws.length || !(t.reply || "").trim()) continue;
      savedTrs.push({on: "reaction", words: ws, reply: t.reply.trim(), do: [], cooldown: +t.cooldown || 0});
      continue;
    }
    savedTrs.push(t);
  }
  busy($('[data-sh="save"]'), () => commit(cfg => {
    if(savedTrs.length) cfg.group = {...(cfg.group || {}), triggers: savedTrs};
    else if(cfg.group) delete cfg.group;
  }, "قانون‌های گروه ذخیره شد"));
};

/* ── حالت‌های هوش مصنوعی: توضیح بده / بهتر کن / ترجمه کن ── */
Object.assign(A, {
  aimode: el => busy(el, async () => {
    const mode = el.dataset.m;
    const d = await api(`/api/bots/${S.cur.id}/ai/mode`, "POST", {mode});
    if(d.wallet) S.wallet = d.wallet;
    if(mode === "translate"){
      S.bots = S.bots.map(x => x.id === d.bot.id ? d.bot : x); S.cur = d.bot;
      renderTop(); render(); toast("ترجمه شد؛ با «برگشت به نسخه‌ی قبلی» قابل برگشت است"); haptic("ok");
      return;
    }
    S.sheet = {kind: "info"};
    showSheet(head(mode === "explain" ? "این ربات چه می‌کند؟" : "پیشنهادهای بهتر شدن") +
      `<div class="panel">${digitsHTML(d.text).replace(/\n/g, "<br>")}</div><div class="fgap"></div>`);
  }),
});

/* ── دکمه‌های ابزار تازه + حالت‌های AI در تب هوش مصنوعی ── */
const _scopeBar0 = scopeBarInject;
scopeBarInject = function(){
  _scopeBar0();
  const tools = document.querySelector(".st-tools");
  if(tools && !tools.querySelector("[data-a='packsopen']")){
    tools.insertAdjacentHTML("beforeend", `<span class="sep"></span>
      <button class="tb lbl" data-a="packsopen" title="بسته‌های آماده">${IC.spark}<span>بسته‌ها</span></button>
      <button class="tb lbl" data-a="chanopen" title="پست کانال">${IC.mega}<span>پست کانال</span></button>
      <button class="tb lbl" data-a="connopen" title="اتصال‌ها: اینلاین، وب‌هوک، RSS">${IC.open}<span>اتصال‌ها</span></button>`);
  }
};
const _tabAI0 = tabAI;
tabAI = function(b){
  let h = _tabAI0(b);
  h += `<div class="chips" style="margin-top:8px"><button class="chip" data-a="aimode" data-m="explain">توضیح بده این ربات چه کار می‌کند</button>
    <button class="chip" data-a="aimode" data-m="improve">بهبود تجربه‌ی کاربر</button>
    <button class="chip" data-a="aimode" data-m="translate">ترجمه‌ی همه‌ی متن‌ها</button></div>`;
  return h;
};
