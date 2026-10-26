/* ═══════════════════════════════════════════════════════════════
   builder3.js — تکمیل مینی‌اپ‌ساز: طرح‌های آماده (variant)، اتصال دوضربه‌ای بلوک→لیست
   با پیش‌نمایش داده‌ی واقعی، لینک مستقیم هر صفحه، خروجی CSV لیست‌ها و اجرای سناریوها
   قبل از انتشار. بعد از builder2.js بارگذاری می‌شود.
   ═══════════════════════════════════════════════════════════════ */
"use strict";

/* ── ۱) طرح‌های آماده (variant) در چیدمان ── */
const _mbLayout0 = mbLayoutSheet;
mbLayoutSheet = function(x){
  let h = _mbLayout0(x);
  const st = x.st || {};
  const hasV = ["cards", "buttons", "gallery", "hero", "product", "pricing"].includes(x.t);
  if(!hasV) return h;
  const opts = [["", "خودکار"], ["rows", "ردیفی"], ["grid", "شبکه‌ای"], ["mini", "مینی"], ["cover", "کاور"], ["chips", "چیپی"]];
  h = h.replace('<span class="lbl">انیمیشن ورود</span>',
    `<span class="lbl">طرح آماده</span><div class="sws">${opts.map(([v, l]) => `<button type="button" class="sw${(st.v || "") === v ? " on" : ""}" data-a="mbstv" data-v="${v}">${l}</button>`).join("")}</div>
    <span class="lbl">انیمیشن ورود</span>`);
  return h;
};
Object.assign(A, {mbstv: el => { D.st = D.st || {}; D.st.v = el.dataset.v || null; renderSheet(); }});

/* ── ۲) اتصال دوضربه‌ای بلوک → لیست (با پیش‌نمایش داده‌ی واقعی) ── */
Object.assign(SHEETS, {
  blink: {html(){
    if(S2._blt === undefined){
      api(`/api/bots/${S.cur.id}/tables`).then(d => { S2._blt = d.items || []; if(S.sheet?.kind === "blink") renderSheet(); }).catch(() => { S2._blt = []; });
    }
    const items = S2._blt;
    return head("اتصال به لیست") + (items ? (items.length ? `
      <p class="muted">جدول را لمس کن؛ فیلدها و سه ردیف اولِ داده‌ی واقعی را می‌بینی و بلوک به همان جدول وصل می‌شود.</p>
      ${items.map(t => `<button class="gi" data-a="blpick" data-t="${esc(t.t)}"><span class="ib">${S2IC.table}</span>
        <span class="gt"><b>${esc(t.t)}</b><span>${N(t.rows)} ردیف · ${t.fields.map(esc).join("، ").slice(0, 40)}</span></span>${goIc}</button>`).join("")}`
      : `<p class="muted">هنوز لیستی نداری؛ از استودیو ← «لیست‌ها» یکی بساز.</p>`)
      : `<p class="muted">در حال بارگذاری…</p>`) + `<div class="fgap"></div>`;
  }},
});
Object.assign(A, {
  blinkopen: () => { S2._blt = undefined; S.sheet = {kind: "blink"}; D = null; renderSheet(); },
  blpick: el => busy(el, async () => {
    const t = el.dataset.t;
    D.table = t;
    if(D.t === "chart") D.field = "total";
    if(D.t === "board" || D.t === "stat") D.var = D.var || "points";
    try{
      const d = await api(`/api/bots/${S.cur.id}/tables/${encodeURIComponent(t)}`);
      S2._blprev = (d.rows || []).slice(0, 3).map(r => r.join(" · "));
    }catch(_){ S2._blprev = []; }
    S.sheet = {kind: "bprop"}; renderSheet(); toast("به جدول «" + t + "» وصل شد");
  }),
});
/* دکمه‌ی اتصال در ویرایشگر بلوک‌های داده‌دار */
const _bpropSheet2 = bpropSheet;
bpropSheet = function(){
  let h = _bpropSheet2();
  if(D && ["list", "board", "stat", "chart", "orders"].includes(D.t)){
    h = h.replace('<div class="bar"><button class="b" data-sh="save">ذخیره</button></div>',
      `<div class="sub"><span>اتصال سریع</span></div><button class="b o sm" data-a="blinkopen">${S2IC.table}انتخاب از لیست‌های ربات</button>
       ${(S2._blprev || []).length && D.table ? `<p class="muted">نمونه‌ی داده‌ی «${esc(D.table)}»: ${S2._blprev.map(x => esc(x)).join(" | ").slice(0, 90)}</p>` : ""}
       <div class="bar"><button class="b" data-sh="save">ذخیره</button></div>`);
  }
  return h;
};

/* ── ۳) لینک مستقیم هر صفحه ── */
const _mbPaintScreens3 = mbPaintScreens;
mbPaintScreens = function(){
  _mbPaintScreens3();
  const bar = $("#bscr");
  if(bar && !bar.querySelector("[data-a='mbscrlink']")){
    bar.insertAdjacentHTML("beforeend", `<button class="chip" data-a="mbscrlink">${IC.copy}لینک صفحه</button>`);
  }
};
Object.assign(A, {
  mbscrlink: () => {
    const u = "https://t.me/" + (S.cur.username || "") + "?startapp=" + encodeURIComponent(MB.screen);
    navigator.clipboard?.writeText(u).then(
      () => toast("لینک این صفحه کپی شد (برای باز شدن مستقیم، مینی‌اپ باید منتشر شده باشد)"),
      () => toast(u));
  },
});

/* ── ۴) خروجی CSV از ویرایشگر لیست‌ها ── */
const _listedit0 = SHEETS.listedit.html;
SHEETS.listedit.html = function(){
  let h = _listedit0();
  h = h.replace('<button class="b o sm" data-a="ltcsv">${IC.upload}چسباندن CSV</button>',
    '<button class="b o sm" data-a="ltcsv">${IC.upload}چسباندن CSV</button><button class="b o sm" data-a="ltcsvexp">${IC.dl}خروجی CSV</button>');
  return h;
};
Object.assign(A, {
  ltcsvexp: () => {
    ltReadGrid();
    const t = S2._lt, d = S2._ltd;
    const q = v => '"' + String(v ?? "").replace(/"/g, '""') + '"';
    const csv = [d.fields.map(q).join(","), ...d.rows.map(r => r.map(q).join(","))].join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["\uFEFF" + csv], {type: "text/csv;charset=utf-8"}));
    a.download = t + ".csv";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 3000);
    toast("فایل CSV دانلود شد");
  },
});

/* ── ۵) اجرای همه‌ی سناریوها قبل از انتشار ── */
const _bpubSheet0 = bpubSheet;
bpubSheet = function(){
  let h = _bpubSheet0();
  let scens = [];
  try{ scens = JSON.parse(localStorage.getItem("azadi.sim." + S.cur.id) || "[]"); }catch(_){}
  h += scens.length ? `<div class="sub"><span>تست قبل از انتشار</span></div>
    <p class="muted">${N(scens.length)} سناریوی ذخیره‌شده داری؛ همه را یک‌جا اجرا کن و جواب‌ها را ببین.</p>
    <button class="b o sm" data-a="simrunall">${IC.play}اجرای همه‌ی سناریوها</button>`
    : `<p class="muted mt">برای اطمینان، اول در استودیو با شبیه‌ساز چند سناریو بساز و ذخیره کن؛ بعد همین‌جا همه را یک‌جا اجرا می‌کنی.</p>`;
  return h;
};
Object.assign(A, {
  simrunall: () => {
    closeSheet();
    S.view = "studio"; S.btab = "ai"; closeSheet(); render();
    setTimeout(() => {
      A.simopen();
      const scens = (() => { try{ return JSON.parse(localStorage.getItem("azadi.sim." + S.cur.id) || "[]"); }catch(_){ return []; } })();
      let i = 0;
      (function next(){
        if(i >= scens.length){ toast("همه‌ی سناریوها اجرا شد"); return; }
        const sc = scens[i++];
        const ev = new CustomEvent("sc3runscen", {detail: sc});
        dispatchEvent(ev);
        setTimeout(next, 2500);
      })();
    }, 400);
  },
});
addEventListener("sc3runscen", e => {
  const sc = e.detail;
  if(typeof SIM === "undefined" || !SIM.on || !sc) return;
  simInit();
  SIM.on = true;
  for(const s of (sc.steps || [])){
    SIM.ui = s.u || 0;
    const st = simU();
    if(s.type === "text") simUserText(s.v);
    else if(s.type === "start") simSend(S.cur.config.start, st);
    else simEvent(s.v);
  }
  SIM.ui = 0;
  simRerender();
});
