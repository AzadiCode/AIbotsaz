/* ═══════════════════════════════════════════════════════════════
   studio2.js — استودیو نسل ۲: سازنده‌ی «وقتی … آنگاه»، شبیه‌ساز چت (خصوصی و گروه با کاربر
   ساختگی)، پنل «مشکل‌ها» با رفع یک‌ضربه‌ای، تفاوت نسخه‌ها، «دکتر ربات» و ویرایشگر لیست‌ها
   شبیه اکسل. بعد از app.js و studio.js و builder.js بارگذاری می‌شود و به همان ابزارها
   (S، $، api، IC، SHEETS، A، commit، …) تکیه دارد. هیچ اصطلاح فنی به کاربر نشان داده نمی‌شود.
   ═══════════════════════════════════════════════════════════════ */
"use strict";
const S2 = {};                     // وضعیت داخلی ابزارهای این فایل (اسکن مشکل‌ها، جدول باز، نسخه‌ها و…)

/* ───────────────────────── ابزارهای مشترک ───────────────────────── */
const S2IC = {
  wt: svg('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
  sim: svg('<rect x="6" y="3" width="12" height="18" rx="3"/><path d="M10 6h4"/>'),
  fix: svg('<path d="M14 6l4 4-8 8H6v-4z"/><path d="M12 8l4 4"/>'),
  diff: svg('<path d="M8 4v16M16 4v16"/><path d="M8 9H4M8 15h4M16 9h4M16 15h-4"/>'),
  doctor: svg('<rect x="4" y="7" width="16" height="13" rx="3"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M12 11v5M9.5 13.5h5"/>'),
  table: svg('<rect x="4" y="5" width="16" height="14" rx="2"/><path d="M4 10h16M10 10v9M4 15h16"/>'),
};
const s2Esc = esc;
const S2_ROW_ACT = a => `<button class="b o sm" data-a="${a}" data-t="@@T@@">${IC.table}باز کردن</button>`;

/* ───────────────────────── ۱) سازنده‌ی «وقتی … آنگاه» ─────────────────────────
   قانون‌ها روی قابلیت‌های واقعی موتور سوارند: ماشه‌های گروه (کلمه/دستور ← پاسخ، امتیاز،
   خبر، پاک‌کردن، فاصله‌ی زمانی) و پیام ورود/خروج (مدیریت گروه) و دستورها. */
function wtTriggerBlank(){
  return {on: "contains", words: "", reply: "", act: "none", var: "points", val: "1-5", notify: "", cooldown: 0, del: false};
}
function wtData(){
  const cfg = S.cur.config, g = cfg.group || {};
  return {
    trs: (g.triggers || []).map(t => ({on: t.on || "contains", words: (t.words || []).join("، "), reply: t.reply || "",
      act: (t.do || []).some(a => a.op === "add") ? "add" : (t.do || []).some(a => a.op === "notify") ? "notify" : (t.do || []).length ? "both" : "none",
      var: ((t.do || []).find(a => a.op === "add") || {}).var || "points",
      val: ((t.do || []).find(a => a.op === "add") || {}).value || "1-5",
      notify: ((t.do || []).find(a => a.op === "notify") || {}).value || "",
      cooldown: t.cooldown || 0, del: !!t.delete})),
    del: [...(g.triggers || []).map(() => false)],
    new: null,
  };
}
function wtCard(t, i){
  const whenFa = {contains: "توی گروه نوشت", exact: "دقیقاً نوشت", starts: "پیامش با این شروع شد", command: "این دستور را زد"}[t.on] || "نوشت";
  const then = [];
  if(t.reply) then.push("پاسخ می‌فرستد");
  if(t.act === "add" || t.act === "both") then.push(`به ${s2Esc(t.var || "امتیاز")}ش اضافه می‌کند`);
  if(t.act === "notify" || t.act === "both") then.push("به تو خبر می‌دهد");
  if(t.del) then.push("پیامش پاک می‌شود");
  if(+t.cooldown) then.push(`هر ${fa(t.cooldown)} ثانیه یک بار`);
  return `<div class="wtc${t.del ? " gone" : ""}" data-i="${i}">
    <div class="wtc-w"><span class="tag w">وقتی</span><span>عضوی ${whenFa} «<b>${s2Esc(t.words)}</b>»</span></div>
    ${then.length ? `<div class="wtc-t"><span class="tag t">آنگاه</span><span>${then.join(" و ")}</span></div>` : `<div class="wtc-t"><span class="tag t">آنگاه</span><span class="muted">هیچ کاربری انجام نمی‌شود</span></div>`}
    ${(t.reply || "") ? `<div class="wtc-p">«${s2Esc(t.reply.replace(/<[^>]+>/g, "").slice(0, 90))}${t.reply.length > 90 ? "…" : ""}»</div>` : ""}
    <div class="wtc-ops"><button class="b t" data-a="wtedit" data-i="${i}">ویرایش</button>
      <button class="b r t" data-a="wtdel" data-i="${i}">حذف</button></div></div>`;
}
function wtSheet(){
  D = wtData();
  const cmds = Object.entries(S.cur.config.commands || {}).map(([c, nid]) =>
    `<div class="wtc"><div class="wtc-w"><span class="tag w">وقتی</span><span>کاربر /${s2Esc(c)} زد</span></div>
     <div class="wtc-t"><span class="tag t">آنگاه</span><span>بخش «${s2Esc(titleOf(S.cur.config, nid))}» باز می‌شود</span></div>
     <div class="wtc-ops"><button class="b t" data-a="wtcmd" data-c="${s2Esc(c)}">ویرایش در نقشه</button></div></div>`).join("");
  const joinCard = `<div class="wtc"><div class="wtc-w"><span class="tag w">وقتی</span><span>عضو جدید وارد گروه شد</span></div>
    <div class="wtc-t"><span class="tag t">آنگاه</span><span>${S.cur.config.mod ? "پیام خوش‌آمد فرستاده می‌شود" : "مدیریت گروه روشن نیست"}</span></div>
    <div class="wtc-ops"><button class="b t" data-a="wtmod">تنظیم خوش‌آمد</button></div></div>`;
  return head("وقتی … آنگاه") + `
    <p class="muted">قانون‌های خودکار ربات اینجاست. هر قانون یعنی: «وقتی این اتفاق افتاد، این کار را انجام بده».</p>
    <div class="sub"><span>قانون‌های گروه</span><button class="b sm" data-a="wtnew">${IC.plus}قانون جدید</button></div>
    ${(D.trs.length || D.new !== null) ? D.trs.map(wtCard).join("") : `<p class="muted">هنوز قانونی برای گروه نساخته‌ای.</p>`}
    ${D.new !== null ? wtEditCard(D.new) : ""}
    <div class="sub"><span>دستورهای ربات</span></div>
    ${cmds || `<p class="muted">دستوری نساخته‌ای؛ دستورها را در تنظیمات ربات می‌سازی.</p>`}
    <div class="sub"><span>عضویت و خروج</span></div>
    ${joinCard}
    <div class="bar"><button class="b" data-sh="save">ذخیره</button></div><div class="fgap"></div>`;
}
function wtEditCard(t){
  return `<div class="wtc edit">
    <span class="lbl">وقتی عضوی…</span>
    <select id="w-on">${[["contains", "توی گروه این کلمه را نوشت"], ["exact", "دقیقاً این را نوشت"], ["starts", "پیامش با این شروع شد"], ["command", "این دستور را زد"]].map(([v, l]) => `<option value="${v}"${t.on === v ? " selected" : ""}>${l}</option>`).join("")}</select>
    <span class="lbl">کلمه یا کلمه‌ها (با ویرگول)</span><input class="fa" id="w-words" value="${s2Esc(t.words)}" maxlength="200" placeholder="سلام، خسته نباشید">
    <span class="lbl">آنگاه…</span>
    <span class="lbl">پاسخ ربات (خالی = بی‌پاسخ)</span><textarea class="fa" id="w-reply" maxlength="1500" style="min-height:64px">${s2Esc(t.reply)}</textarea>${fmtTools("w-reply")}
    <label class="chk"><input type="checkbox" id="w-actadd"${t.act === "add" || t.act === "both" ? " checked" : ""}> به امتیاز یا سکه‌ی کاربر اضافه کن</label>
    ${t.act === "add" || t.act === "both" ? `<div class="cmd"><input class="ltr" id="w-var" list="vdl" value="${s2Esc(t.var)}" maxlength="20" placeholder="امتیاز (مثل points)"><input class="fa" id="w-val" value="${s2Esc(t.val)}" maxlength="40" placeholder="مقدار یا بازه مثل 1-5"></div>` : ""}
    <label class="chk"><input type="checkbox" id="w-actnotify"${t.act === "notify" || t.act === "both" ? " checked" : ""}> هم‌زمان به من خبر بده</label>
    ${t.act === "notify" || t.act === "both" ? `<input class="fa" id="w-notify" value="${s2Esc(t.notify)}" maxlength="200" placeholder="متن خبر برای تو">` : ""}
    <label class="chk"><input type="checkbox" id="w-del"${t.del ? " checked" : ""}> پیام کاربر بعد از پاسخ پاک شود</label>
    <span class="lbl">فاصله‌ی اجباری (ثانیه؛ ۰ = بی‌فاصله)</span><input class="ltr" id="w-cd" inputmode="numeric" value="${fa(t.cooldown || 0)}">
    <div class="bar"><button class="b" data-a="wtsave">این قانون اضافه شود</button><button class="b o" data-a="wtx">بی‌خیال</button></div></div>`;
}
function wtReadEdit(){
  const t = D.new;
  t.on = $("#w-on")?.value ?? t.on;
  t.words = $("#w-words")?.value ?? t.words;
  t.reply = $("#w-reply")?.value ?? t.reply;
  const add = $("#w-actadd")?.checked, nt = $("#w-actnotify")?.checked;
  t.act = add && nt ? "both" : add ? "add" : nt ? "notify" : "none";
  t.var = cleanVar($("#w-var")?.value ?? t.var);
  t.val = $("#w-val")?.value ?? t.val;
  t.notify = $("#w-notify")?.value ?? t.notify;
  t.del = $("#w-del") ? $("#w-del").checked : t.del;
  t.cooldown = Math.max(0, Math.min(86400, parseInt(($("#w-cd")?.value || "0").replace(/[۰-۹]/g, d => "۰۱۲۳۴۵۶۷۸۹".indexOf(d))) || 0));
}
function wtSaveAll(){
  const trs = [];
  for(let i = 0; i < D.trs.length; i++){
    if(D.del[i]) continue;
    const t = D.trs[i];
    const words = t.words.split(/[,،\n]+/).map(s => s.trim()).filter(Boolean);
    if(!words.length) continue;
    const o = {on: t.on, words};
    if((t.reply || "").trim()) o.reply = t.reply.trim();
    const do_ = [];
    if(t.act === "add" || t.act === "both") do_.push({op: "add", var: cleanVar(t.var) || "points", value: (t.val || "1").trim()});
    if(t.act === "notify" || t.act === "both") do_.push({op: "notify", value: (t.notify || "قانون گروه اجرا شد").trim()});
    if(do_.length) o.do = do_;
    if(t.del) o.delete = true;
    if(+t.cooldown) o.cooldown = +t.cooldown;
    trs.push(o);
  }
  busy($('[data-sh="save"]'), () => commit(cfg => {
    if(trs.length) cfg.group = {...(cfg.group || {}), triggers: trs};
    else if(cfg.group) delete cfg.group;
  }, "قانون‌های گروه ذخیره شد"));
}
Object.assign(SHEETS, {
  wt: {html: wtSheet, read(){ if(D.new !== null) wtReadEdit(); }, save: wtSaveAll},
  arch: {html: () => (typeof archSheet === "function" ? archSheet() : "")},
});

Object.assign(A, {
  wtopen: () => { if(!S.cur) return toast("اول یک ربات انتخاب کن"); S.sheet = {kind: "wt"}; D = null; renderSheet(); },
  wtnew: () => { readSheet(); D.new = wtTriggerBlank(); renderSheet(); },
  wtx: () => { readSheet(); D.new = null; renderSheet(); },
  wtedit: el => { readSheet(); D.new = null; S2._wtEdit = +el.dataset.i; const t = {...D.trs[S2._wtEdit]}; D.trs.splice(S2._wtEdit, 1); D.del.splice(S2._wtEdit, 1); D.new = t; renderSheet(); },
  wtdel: el => { readSheet(); D.new = null; D.del[+el.dataset.i] = true; renderSheet(); },
  wtsave: () => {
    wtReadEdit();
    const t = D.new;
    if(!t.words.trim()) return toast("کلمه‌ها را بنویس");
    if(!(t.reply || "").trim() && t.act === "none" && !t.del) return toast("حداقل یک کار برای «آنگاه» انتخاب کن");
    D.trs.push(t); D.new = null; renderSheet();
  },
  wtcmd: () => { closeSheet(); toast("دستورها در تنظیمات ربات ویرایش می‌شوند"); openBot(); },
  wtmod: () => { closeSheet(); openMod(); },
});

/* ───────────────────────── ۲) ویرایشگر لیست‌ها شبیه اکسل ───────────────────────── */
function s2TableNames(){
  const cfg = S.cur.config, names = new Set(Object.keys(cfg.dbfields || {}));
  for(const n of Object.values(cfg.nodes)){
    for(const a of n.do || []) if(String(a.op).startsWith("db_") && a.table) names.add(a.table);
    if(n.list?.table) names.add(n.list.table);
  }
  return [...names].filter(n => /^[a-z0-9_]{1,20}$/.test(n));
}
function listsSheet(){
  D = null;
  S2._lt = null;
  const names = s2TableNames();
  return head("لیست‌ها") + `
    <p class="muted">لیست‌ها مثل یک جدول اکسل‌اند: سفارش‌ها، سؤال‌ها، بازیکن‌ها… ربات و مینی‌اپ از همین لیست‌ها می‌خوانند و می‌نویسند.</p>
    <div class="sub"><span>لیست‌های این ربات</span></div>
    ${names.length ? `<div class="group">${names.map(t => `<button class="gi" data-a="ltopen" data-t="${s2Esc(t)}"><span class="ib">${S2IC.table}</span>
      <span class="gt"><b>${s2Esc(t)}</b><span>باز کردن جدول</span></span>${goIc}</button>`).join("")}</div>`
      : `<p class="muted">هنوز لیستی نداری. لیست‌ها وقتی ساخته می‌شوند که ربات یا مینی‌اپ داده‌ای ثبت کند؛ یا می‌توانی همین حالا یکی بسازی.</p>`}
    <div class="sub"><span>جدول تازه</span></div>
    <span class="lbl">نام جدول (انگلیسی، مثل orders)</span><input class="ltr" id="lt-name" maxlength="20" placeholder="orders" autocomplete="off">
    <span class="lbl">ستون‌ها (با ویرگول؛ اسم فارسی هم می‌شود)</span><input class="fa" id="lt-cols" maxlength="200" placeholder="نام محصول، قیمت، تلفن">
    <div class="bar"><button class="b" data-a="ltnew">${IC.plus}ساختن جدول</button></div><div class="fgap"></div>`;
}
function ltColsOf(t){
  const meta = S2._tmeta || {};
  if(meta[t]?.fields?.length) return meta[t].fields;
  return (S.cur.config.dbfields || {})[t] || [];
}
function ltHeaderFa(cols){
  return cols;
}
function listeditSheet(){
  const t = S2._lt, d = S2._ltd || {rows: [], fields: []};
  const cols = d.fields;
  const headCell = cols.length ? "" : "";
  const rowsHTML = d.rows.map((r, i) => `<div class="ltrow" data-i="${i}">
      ${cols.map((c, ci) => `<input class="ltcell" data-i="${i}" data-c="${ci}" value="${s2Esc(r[ci] ?? "")}">`).join("")}
      <button class="iconb sm" data-a="ltrowdel" data-i="${i}" aria-label="حذف ردیف" style="color:var(--bad)">${IC.x}</button></div>`).join("");
  return head("جدول «" + s2Esc(t) + "»") + `
    <p class="muted">مثل اکسل پرش کن. ستون‌ها را از پایین اضافه کن؛ یا از اکسل کپی بگیر و با «چسباندن CSV» همه‌ی ردیف‌ها را یک‌جا وارد کن.</p>
    <div class="sub"><span>ستون‌ها (${fa(cols.length)})</span><button class="b o sm" data-a="ltcoladd">${IC.plus}ستون</button></div>
    <div class="ltrow lth">${cols.map((c, ci) => `<input class="ltcell ltc" data-c="${ci}" value="${s2Esc(c)}" placeholder="اسم ستون">`).join("")}
      <button class="iconb sm" data-a="ltcoldel" aria-label="حذف ستون آخر" style="color:var(--bad)">${IC.minus}</button></div>
    <div class="sub"><span>ردیف‌ها (${fa(d.rows.length)})</span>
      <button class="b o sm" data-a="ltrowadd">${IC.plus}ردیف</button>
      <button class="b o sm" data-a="ltcsv">${IC.upload}چسباندن CSV</button></div>
    ${d.rows.length ? rowsHTML : `<p class="muted">هنوز ردیفی نیست.</p>`}
    <div class="bar"><button class="b" data-a="ltsave">ذخیره‌ی جدول</button></div><div class="fgap"></div>`;
}
function ltReadGrid(){
  const t = S2._lt, d = S2._ltd;
  const cols = [...document.querySelectorAll(".ltrow.lth .ltc")].map((x, i) => (x.value || "").trim() || `ستون ${i + 1}`);
  d.fields = cols;
  const maxc = Math.max(1, Math.min(12, cols.length));
  d.rows = [...document.querySelectorAll(".ltrow:not(.lth)")].map(rw => {
    const i = +rw.dataset.i;
    return cols.slice(0, maxc).map((_, ci) => (rw.querySelector(`.ltcell[data-i="${i}"][data-c="${ci}"]`)?.value ?? "")).slice(0, 12);
  });
}
Object.assign(SHEETS, {
  lists: {html: listsSheet},
  listedit: {html: listeditSheet},
});
Object.assign(A, {
  listsopen: () => { if(!S.cur) return toast("اول یک ربات انتخاب کن"); S.sheet = {kind: "lists"}; D = null; renderSheet(); },
  ltopen: el => busy(el, async () => {
    const t = el.dataset.t;
    const d = await api(`/api/bots/${S.cur.id}/tables/${encodeURIComponent(t)}`);
    S2._lt = t; S2._ltd = {fields: d.fields.length ? d.fields : ["ستون ۱", "ستون ۲"], rows: d.rows.map(r => r)};
    S.sheet = {kind: "listedit"}; renderSheet();
  }),
  ltnew: () => {
    const name = ($("#lt-name")?.value || "").toLowerCase().replace(/[^a-z0-9_]/g, "").replace(/^[0-9_]+/, "");
    if(!name) return toast("نام انگلیسی جدول را بنویس (مثل orders)");
    const cols = ($("#lt-cols")?.value || "").split(/[,،]/).map(s => s.trim()).filter(Boolean);
    S2._lt = name; S2._ltd = {fields: cols.length ? cols.slice(0, 12) : ["نام", "توضیح"], rows: []};
    S.sheet = {kind: "listedit"}; renderSheet();
  },
  ltcoladd: () => { ltReadGrid(); if(S2._ltd.fields.length >= 12) return toast("حداکثر ۱۲ ستون"); S2._ltd.fields.push("ستون " + (S2._ltd.fields.length + 1)); S2._ltd.rows.forEach(r => r.push("")); renderSheet(); },
  ltcoldel: () => { ltReadGrid(); if(S2._ltd.fields.length <= 1) return toast("حداقل یک ستون لازم است"); S2._ltd.fields.pop(); S2._ltd.rows.forEach(r => r.pop()); renderSheet(); },
  ltrowadd: () => { ltReadGrid(); S2._ltd.rows.push(S2._ltd.fields.map(() => "")); renderSheet(); },
  ltrowdel: el => { ltReadGrid(); S2._ltd.rows.splice(+el.dataset.i, 1); renderSheet(); },
  ltcsv: () => {
    ltReadGrid();
    const t = S2._ltd;
    S.sheet = {kind: "info"};
    showSheet(head("چسباندن CSV") + `
      <p class="muted">خط اول = اسم ستون‌ها؛ هر خط بعدی یک ردیف. از اکسل کپی کن و اینجا بچسبان (جداکننده: ویرگول یا تب).</p>
      <textarea class="code" id="lt-csvin" style="min-height:180px" placeholder="نام،قیمت&#10;چای،۲۰"></textarea>
      <div class="bar"><button class="b" data-a="ltcsvgo">ورود ردیف‌ها</button></div><div class="fgap"></div>`);
  },
  ltcsvgo: () => {
    const raw = ($("#lt-csvin")?.value || "").trim();
    if(!raw) return toast("متن CSV را بچسبان");
    const lines = raw.split(/\r?\n/).map(l => l.split(/[\t,؛;]/).map(c => c.trim()));
    if(lines.length < 2) return toast("حداقل یک خط سرستون و یک ردیف لازم است");
    const cols = lines[0].slice(0, 12);
    const rows = lines.slice(1, 201).map(l => { const r = cols.map(() => ""); l.forEach((c, i) => { if(i < r.length) r[i] = c; }); return r; });
    S2._ltd.fields = cols; S2._ltd.rows = rows;
    S.sheet = {kind: "listedit"}; renderSheet(); toast(`${fa(rows.length)} ردیف وارد شد؛ «ذخیره‌ی جدول» را بزن`);
  },
  ltsave: el => {
    ltReadGrid();
    const t = S2._lt, d = S2._ltd;
    if(!d.fields.length) return toast("حداقل یک ستون لازم است");
    busy(el, async () => {
      await api(`/api/bots/${S.cur.id}/tables/${encodeURIComponent(t)}`, "POST", {fields: d.fields, rows: d.rows});
      S2._tmeta = null;
      closeSheet(); toast("جدول ذخیره شد"); haptic("ok");
    });
  },
});

/* ───────────────────────── ۳) پنل «مشکل‌ها» ───────────────────────── */
function s2Scan(){
  const cfg = S.cur.config, out = [];
  const ids = Object.keys(cfg.nodes);
  for(const [id, n] of Object.entries(cfg.nodes)){
    const btns = (n.buttons || []).flat();
    if(!btns.length && !n.next && !(n.route || []).length && id !== cfg.start)
      out.push({k: "dead:" + id, p: 2, fa: `بخش «${titleOf(cfg, id)}» بن‌بست است؛ کاربر راه برگشت ندارد.`, fix: "btn", n: id});
    for(const [r, row] of (n.buttons || []).entries()) for(const [c, b] of row.entries())
      if(!b.goto && !b.url && !b.alert && !b.copy && !b.share && !b.pay && b.app === undefined)
        out.push({k: `btn:${id}:${r}:${c}`, p: 1, fa: `دکمه‌ی «${b.text}» به هیچ‌جا وصل نیست.`, fix: "btnrm", n: id, r, c});
    if((n.text || "").length < 4) out.push({k: "txt:" + id, p: 1, fa: `متن بخش «${titleOf(cfg, id)}» خیلی کوتاه است.`});
    if(n.ai && !btns.some(b => b.goto || b.app)) out.push({k: "ai:" + id, p: 2, fa: `گفتگوی هوشمندِ «${titleOf(cfg, id)}» دکمه‌ی بازگشت ندارد؛ کاربر گیر می‌کند.`, fix: "btn", n: id});
    if(n.board && !(n.board.var)) out.push({k: "bd:" + id, p: 1, fa: `جدول برترین‌های «${titleOf(cfg, id)}» متغیر ندارد.`});
  }
  if(!cfg.fallback || cfg.fallback === cfg.start) { /* پیش‌فرض مجاز است */ }
  const reach = (() => { const seen = new Set([cfg.start]), q = [cfg.start];
    while(q.length){ const id = q.pop(), n = cfg.nodes[id]; if(!n) continue;
      for(const b of (n.buttons || []).flat()){ if(b.goto && !seen.has(b.goto)){ seen.add(b.goto); q.push(b.goto); } if(b.pay?.goto && !seen.has(b.pay.goto)){ seen.add(b.pay.goto); q.push(b.pay.goto); } }
      if(n.next && !seen.has(n.next)){ seen.add(n.next); q.push(n.next); }
      for(const r of n.route || []) if(r.goto && !seen.has(r.goto)){ seen.add(r.goto); q.push(r.goto); } }
    return seen; })();
  for(const id of ids) if(!reach.has(id)) out.push({k: "unre:" + id, p: 2, fa: `هیچ دکمه‌ای به بخش «${titleOf(cfg, id)}» وصل نیست؛ کاربر هرگز آن را نمی‌بیند.`, fix: "link", n: id});
  for(const [c] of Object.entries(cfg.commands || {})) if(cfg.commands[c] && !cfg.nodes[cfg.commands[c]]) out.push({k: "cmd:" + c, p: 2, fa: `دستور /${c} به بخش ناموجود وصل است.`});
  return out;
}
function problemsSheet(){
  const scan = s2Scan();
  S2._scan = scan;
  return head("مشکل‌ها") + (scan.length ? `
    <p class="muted">این‌ها مانع کار کاربرها می‌شوند. با «رفع خودکار» یا «برو به آن» درستشان کن.</p>
    ${scan.map((x, i) => `<div class="pbm p${x.p}"><span class="pbm-t">${x.p === 2 ? "مهم" : "جزئی"}</span>
      <span class="gt"><b>${digitsHTML(x.fa)}</b></span>
      <span class="pbm-ops">${x.fix ? `<button class="b sm" data-a="pbfix" data-i="${i}">رفع با یک ضربه</button>` : ""}
      ${x.n ? `<button class="b o sm" data-a="pbgo" data-i="${i}">برو به آن</button>` : ""}</span></div>`).join("")}`
    : `<div class="empty" style="padding:24px 8px"><div class="ib big">${IC.check}</div><h2>همه‌چیز مرتب است</h2><p class="muted">هیچ بن‌بست یا دکمه‌ی بی‌مقصدی پیدا نشد.</p></div>`) + `<div class="fgap"></div>`;
}
Object.assign(SHEETS, {problems: {html: problemsSheet}});
Object.assign(A, {
  pbopen: () => { if(!S.cur) return toast("اول یک ربات انتخاب کن"); S.sheet = {kind: "problems"}; D = null; renderSheet(); },
  pbgo: el => { const x = S2._scan[+el.dataset.i]; if(!x) return; closeSheet(); stCenter(x.n); stHot(x.n, true); setTimeout(() => stHot(x.n, false), 1600); },
  pbfix: el => {
    const x = S2._scan[+el.dataset.i]; if(!x) return;
    busy(el, () => commit(cfg => {
      const n = cfg.nodes[x.n]; if(!n) return;
      if(x.fix === "btn") (n.buttons = n.buttons || [[{text: "منوی اصلی", goto: cfg.start}]]).length || n.buttons.push([{text: "منوی اصلی", goto: cfg.start}]);
      else if(x.fix === "btnrm"){ const rows = n.buttons || []; if(rows[x.r]) rows[x.r].splice(x.c, 1); n.buttons = rows.filter(r => r.length); }
      else if(x.fix === "link"){ const home = cfg.nodes[cfg.start]; (home.buttons = home.buttons || []).push([{"text": titleOf(cfg, x.n).slice(0, 22), goto: x.n}]); }
    }, "درست شد"));
  },
});

/* ───────────────────────── ۴) تفاوت نسخه‌ها ───────────────────────── */
function vdiffSheet(){
  if(!S2._vd) api(`/api/bots/${S.cur.id}/versions`).then(d => { S2._vd = d.items; if(S.sheet?.kind === "vdiff") renderSheet(); }).catch(() => { S2._vd = []; });
  const items = S2._vd;
  return head("نسخه‌ها") + (items ? (items.length ? items.map(v => `
    <div class="vdc"><b>نسخه‌ی ${N(v.i)}</b><small>${v.t ? new Date(v.t).toLocaleString("fa-IR-u-nu-latn", {month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"}) : ""}</small>
      ${(v.lines || []).length ? v.lines.map(l => `<div class="vdl">${esc(l)}</div>`).join("") : `<p class="muted">تغییر مهمی نسبت به نسخه‌ی بعدی نداشت.</p>`}</div>`).join("")
    : `<p class="muted">هنوز نسخه‌ی قبلی ثبت نشده؛ بعد از اولین ارتقا یا ویرایش، تاریخچه‌ی تغییرها اینجا دیده می‌شود.</p>`) : `<p class="muted">در حال بارگذاری…</p>`) + `<div class="fgap"></div>`;
}
Object.assign(SHEETS, {vdiff: {html: vdiffSheet}});
Object.assign(A, {
  vdopen: () => { if(!S.cur) return toast("اول یک ربات انتخاب کن"); S2._vd = null; S.sheet = {kind: "vdiff"}; D = null; renderSheet(); },
});

/* ───────────────────────── ۵) دکتر ربات ───────────────────────── */
function doctorSheet(){
  if(!S2._dr) api(`/api/bots/${S.cur.id}/doctor`).then(d => { S2._dr = d; if(S.sheet?.kind === "doctor") renderSheet(); }).catch(e => { S2._dr = {items: [{ok: false, fa: e.message}]}; if(S.sheet?.kind === "doctor") renderSheet(); });
  const d = S2._dr;
  return head("چرا کار نمی‌کند؟") + (d ? `
    <p class="muted">دکتر ربات اتصال، دسترسی‌ها و مینی‌اپ را چک می‌کند و راه‌حل را با زبان ساده می‌گوید.</p>
    ${(d.items || []).map(x => `<div class="dr ${x.ok ? "ok" : x.warn ? "wn" : "no"}"><span class="dot ${x.ok ? "on" : ""}"></span>
      <span class="gt"><b>${digitsHTML(x.fa)}</b>${x.fix ? `<span>${digitsHTML(x.fix)}</span>` : ""}</span></div>`).join("")}`
    : `<p class="muted">در حال بررسی…</p>`) + `<div class="fgap"></div><button class="b o" data-a="dragain">بررسی دوباره</button><div class="fgap"></div>`;
}
Object.assign(SHEETS, {doctor: {html: doctorSheet}});
Object.assign(A, {
  dropen: () => { if(!S.cur) return toast("اول یک ربات انتخاب کن"); S2._dr = null; S.sheet = {kind: "doctor"}; D = null; renderSheet(); },
  dragain: () => { S2._dr = null; renderSheet(); },
});

/* ───────────────────────── ۷) ربات رشد (B4) ───────────────────────── */
function growthSheet(){
  const g = S.cur.config.growth || {};
  D = {on: !!g.on, chat: g.chat || "", reward: g.reward ?? 10, per_day: g.per_day ?? 20, clawback: g.clawback !== false};
  return head("ربات رشد") + `
    <p class="muted">هر کاربر یک لینک دعوت مخصوص خودش می‌گیرد. فقط عضویت‌های واقعی از همان لینک شمرده می‌شوند و اگر عضوی خارج شود، پاداشش کم می‌شود.</p>
    <label class="chk"><input type="checkbox" id="gr-on"${D.on ? " checked" : ""}> رشد فعال باشد</label>
    <span class="lbl">گروه یا کانالِ رشد (که لینک‌ها برایش ساخته می‌شوند؛ ربات باید ادمینش باشد)</span>
    <input class="ltr" id="gr-chat" value="${esc(D.chat)}" placeholder="@mychannel یا -100…" autocomplete="off">
    <span class="lbl">پاداش هر دعوت تأییدشده</span><input class="ltr" id="gr-reward" inputmode="numeric" value="${fa(D.reward)}">
    <span class="lbl">پاداش به کدام متغیر اضافه شود (مثل points یا coins)</span><input class="ltr" id="gr-var" list="vdl" value="${esc(g.var || "points")}" maxlength="20">
    <span class="lbl">سقف پاداش روزانه هر دعوت‌کننده</span><input class="ltr" id="gr-cap" inputmode="numeric" value="${fa(D.per_day)}">
    <label class="chk"><input type="checkbox" id="gr-claw"${D.clawback ? " checked" : ""}> با ترک عضو، پاداش کسر شود</label>
    <label class="chk"><input type="checkbox" id="gr-wallet"${g.wallet ? " checked" : ""}> پاداش به کیف سکه‌ی بازی هم اضافه شود (اگر مرکز بازی روشن است)</label>
    <div class="aibox">در متن بخش‌های ربات از <b dir="ltr">{invite_link}</b> برای لینک اختصاصی کاربر و <b dir="ltr">{invites}</b> برای تعداد دعوت‌های تأییدشده استفاده کن. در مینی‌اپ، بلوک «دعوت دوستان» هم همین کار را می‌کند.</div>
    <div class="bar"><button class="b" data-sh="save">ذخیره</button></div><div class="fgap"></div>`;
}
Object.assign(SHEETS, {growth: {html: growthSheet, save(){
  const chat = ($("#gr-chat")?.value || "").trim();
  const on = $("#gr-on") ? $("#gr-on").checked : false;
  if(on && !/^(@[A-Za-z][A-Za-z0-9_]{4,31}|-100\d{5,15})$/.test(chat)) return toast("شناسه‌ی گروه/کانال معتبر نیست (@نام یا -100…)");
  busy($('[data-sh="save"]'), () => commit(cfg => {
    if(!on){ delete cfg.growth; return; }
    cfg.growth = {on: true, chat, reward: Math.max(0, Math.min(1000, parseInt(($("#gr-reward")?.value || "10").replace(/[۰-۹]/g, d => "۰۱۲۳۴۵۶۷۸۹".indexOf(d))) || 10)),
      var: cleanVar($("#gr-var")?.value) || "points", per_day: Math.max(0, Math.min(200, parseInt(($("#gr-cap")?.value || "20").replace(/[۰-۹]/g, d => "۰۱۲۳۴۵۶۷۸۹".indexOf(d))) || 20)),
      clawback: $("#gr-claw") ? $("#gr-claw").checked : true, wallet: $("#gr-wallet") ? $("#gr-wallet").checked : false};
  }, "تنظیمات رشد ذخیره شد؛ ربات را ادمینِ گروه/کانال کن"));
}}});

/* ───────────────────────── ۸) استودیوی عامل هوشمند (B5) ───────────────────────── */
function agentAiNodes(){
  return Object.entries(S.cur.config.nodes).filter(([, n]) => n.ai).map(([id, n]) => [id, n.title || (n.text || "").slice(0, 20)]);
}
function agentSheet(){
  const nodes = agentAiNodes();
  if(!nodes.length) return head("استودیوی عامل") + `
    <div class="empty" style="padding:20px 8px"><div class="ib big">${IC.bot}</div><h2>هنوز عامل نداری</h2>
    <p class="muted">در ویرایش یکی از بخش‌ها، حالت را «گفتگو با هوش مصنوعی» بگذار؛ بعد اینجا شخصیت، دانش و تستش را کامل می‌کنی.</p></div><div class="fgap"></div>`;
  const cur = S2._agn || nodes[0][0];
  S2._agn = cur;
  if(S2._kbl === undefined) api(`/api/bots/${S.cur.id}/kb`).then(d => { S2._kbl = d.items || []; if(S.sheet?.kind === "agent") renderSheet(); }).catch(() => { S2._kbl = []; });
  const kbl = S2._kbl;
  const node = S.cur.config.nodes[cur];
  if(S2._tbls === undefined) api(`/api/bots/${S.cur.id}/tables`).then(d => { S2._tbls = d.items || []; if(S.sheet?.kind === "agent") renderSheet(); }).catch(() => { S2._tbls = []; });
  const tls = node.ai?.tools || [];
  return head("استودیوی عامل") + `
    <span class="lbl">کدام گفتگوی هوشمند؟</span><select id="ag-node">${nodes.map(([id, t]) => `<option value="${esc(id)}"${id === cur ? " selected" : ""}>${esc(t)}</option>`).join("")}</select>
    <div class="sub"><span>ابزارها: جستجو در جدول‌های ربات (فهرست سفید)</span></div>
    ${(S2._tbls || []).length ? `<div class="chips">${S2._tbls.map(t => `<label class="chk" style="display:inline-flex;margin:0 0 6px 10px"><input type="checkbox" class="ag-tool" value="${esc(t.t)}"${tls.includes(t.t) ? " checked" : ""}> ${esc(t.t)}</label>`).join("")}</div>`
      : `<p class="muted">جدولی نداری؛ از «لیست‌ها» بساز تا عامل بتواند در آن‌ها جستجو کند.</p>`}
    <div class="sub"><span>شخصیت (دستور عامل)</span></div>
    <textarea class="fa" id="ag-prompt" maxlength="1500" style="min-height:110px">${esc(node.ai?.prompt || "")}</textarea>
    <p class="muted mt">مشخص کن عامل چه نقشی دارد، با چه لحنی جواب می‌دهد و چه چیزهایی را نمی‌گوید. پاسخ‌ها فقط بر پایه‌ی «دانش» زیر داده می‌شوند.</p>
    <div class="sub"><span>دانش عامل (${N((kbl || []).length)} قطعه)</span></div>
    ${(kbl || []).length ? kbl.map(k => `<div class="rl"><div class="cmd" style="justify-content:space-between"><b>${esc(k.t)}</b><button class="iconb sm" data-a="agkdel" data-id="${esc(k.id)}" aria-label="حذف" style="color:var(--bad)">${IC.x}</button></div><p class="muted">${esc(k.x.slice(0, 90))}${k.x.length > 90 ? "…" : ""}</p></div>`).join("")
      : `<p class="muted">هنوز دانشی نداری؛ ساعات کاری، آدرس، خدمات و قیمت‌ها را اضافه کن.</p>`}
    <input class="fa" id="ag-ktitle" placeholder="عنوان (مثل ساعات کاری)" maxlength="60">
    <textarea class="fa" id="ag-ktext" placeholder="متن دانش — هر خط یک نکته؛ بین بلوک‌ها خط خالی" style="min-height:70px" maxlength="4000"></textarea>
    <button class="b o sm" data-a="agkadd">${IC.plus}افزودن به دانش</button>
    <div class="sub"><span>تست زنده</span><span class="muted">هزینه‌ی هر تست مثل یک پیام هوشمند است</span></div>
    <div id="ag-out"></div>
    <div class="cmd"><input class="fa" id="ag-q" placeholder="سؤال را بپرس…" maxlength="500"><button class="b" data-a="agtest">بپرس</button></div>
    <div class="bar"><button class="b o" data-a="agsave">ذخیره‌ی شخصیت</button></div><div class="fgap"></div>`;
}
Object.assign(SHEETS, {agent: {html: agentSheet}});
Object.assign(A, {
  agentopen: () => { if(!S.cur) return toast("اول یک ربات انتخاب کن"); S2._agn = undefined; S2._kbl = undefined; S.sheet = {kind: "agent"}; D = null; renderSheet(); },
  growthopen: () => { if(!S.cur) return toast("اول یک ربات انتخاب کن"); S.sheet = {kind: "growth"}; D = null; renderSheet(); },
  agnode: () => {},
  agsave: el => {
    const nid = $("#ag-node")?.value || S2._agn;
    const p = ($("#ag-prompt")?.value || "").trim();
    if(!p) return toast("دستور عامل را بنویس");
    const tools = [...document.querySelectorAll(".ag-tool:checked")].map(x => x.value).slice(0, 3);
    busy(el, () => commit(cfg => {
      const n = cfg.nodes[nid];
      if(n?.ai){ n.ai.prompt = p; if(tools.length) n.ai.tools = tools; else delete n.ai.tools; }
    }, tools.length ? "شخصیت و ابزارهای عامل ذخیره شد" : "شخصیت عامل ذخیره شد"));
  },
  agkadd: el => busy(el, async () => {
    const title = ($("#ag-ktitle")?.value || "").trim(), text = ($("#ag-ktext")?.value || "").trim();
    if(text.length < 4) return toast("متن دانش را بنویس");
    await api(`/api/bots/${S.cur.id}/kb`, "POST", {title, text});
    S2._kbl = undefined;
    S.sheet = {kind: "agent"}; renderSheet(); toast("به دانش اضافه شد"); haptic("ok");
  }),
  agkdel: el => busy(el, async () => {
    await api(`/api/bots/${S.cur.id}/kb/${el.dataset.id}`, "DELETE");
    S2._kbl = (S2._kbl || []).filter(k => k.id !== el.dataset.id);
    renderSheet();
  }),
  agtest: el => busy(el, async () => {
    const q = ($("#ag-q")?.value || "").trim();
    if(!q) return toast("سؤال را بنویس");
    const out = $("#ag-out");
    out.innerHTML = `<p class="muted">…</p>`;
    try{
      const d = await api(`/api/bots/${S.cur.id}/agent/test`, "POST", {text: q, node: $("#ag-node")?.value || S2._agn});
      if(d.wallet) S.wallet = d.wallet;
      out.innerHTML = `<div class="aibox"><b>جواب عامل:</b><br>${esc(d.reply)}</div>
        ${d.used?.length ? `<p class="muted">از این دانش استفاده کرد: ${d.used.map(u => esc(u.t)).join("، ")}</p>` : `<p class="muted">از دانشی استفاده نکرد (شاید سؤال به دانش ربطی نداشت).</p>`}`;
    }catch(e){
      out.innerHTML = `<div class="aibox">${esc(e.message || "ناموفق بود")}${e.status === 402 ? ' <button class="b t" data-a="goplan">شارژ توکن</button>' : ""}</div>`;
    }
  }),
});
document.addEventListener("change", e => {
  if(e.target.id === "ag-node"){ S2._agn = e.target.value; const n = S.cur.config.nodes[e.target.value]; const p = $("#ag-prompt"); if(p && n?.ai) p.value = n.ai.prompt || ""; }
  if(e.target.classList?.contains("ag-tool") === false && e.target.id === "ag-node"){
    const tls = (S.cur.config.nodes[e.target.value]?.ai?.tools) || [];
    document.querySelectorAll(".ag-tool").forEach(cb => { cb.checked = tls.includes(cb.value); });
  }
});

/* ───────────────────────── ۹) کدهای تخفیف (اکشن disc) ───────────────────────── */
function discSheet(){
  if(S2._dcs === undefined) api(`/api/bots/${S.cur.id}/dcodes`).then(d => { S2._dcs = d.items || []; if(S.sheet?.kind === "discs") renderSheet(); }).catch(() => { S2._dcs = []; });
  const items = S2._dcs;
  return head("کدهای تخفیف") + `
    <p class="muted">در ربات، اکشن «کد تخفیف را بررسی و اعمال کن» همین کدها را بررسی می‌کند. هر کد می‌تواند درصدی یا مبلغی باشد و سقف مصرف و تاریخ انقضا داشته باشد.</p>
    ${(items || []).length ? items.map(c => `
      <div class="rl"><div class="cmd" style="justify-content:space-between">
        <b dir="ltr">${esc(c.code)}</b>
        <span class="muted">${c.kind === "amt" ? N(c.value) + " تومان" : N(c.value) + "٪"} · ${c.max ? N(c.used) + "/" + N(c.max) : N(c.used) + " بار"}${c.dead ? " · منقضی" : ""}</span>
        <button class="iconb sm" data-a="dcdel" data-c="${esc(c.code)}" aria-label="حذف کد" style="color:var(--bad)">${IC.x}</button>
      </div></div>`).join("")
    : `<p class="muted">هنوز کدی نساخته‌ای. اولین کد را بساز (مثل WELCOME با ۱۰٪).</p>`}
    <div class="sub"><span>کد جدید</span></div>
    <input class="fa ltr" id="dc-code" placeholder="کد (انگلیسی، مثل WELCOME)" maxlength="24" autocomplete="off">
    <select id="dc-kind"><option value="pct">درصدی (٪)</option><option value="amt">مبلغی (تومان)</option></select>
    <input class="fa ltr" id="dc-value" inputmode="decimal" placeholder="مقدار (مثل 10 یا 50000)">
    <input class="fa ltr" id="dc-max" inputmode="numeric" placeholder="سقف مصرف (خالی = بی‌نهایت)">
    <input class="fa ltr" id="dc-days" inputmode="numeric" placeholder="اعتبار به روز (خالی = همیشه)">
    <div class="bar"><button class="b" data-a="dcadd">${IC.plus}ساخت کد</button></div><div class="fgap"></div>`;
}
Object.assign(SHEETS, {discs: {html: discSheet}});
Object.assign(A, {
  dcopen: () => { if(!S.cur) return toast("اول یک ربات انتخاب کن"); S2._dcs = undefined; S.sheet = {kind: "discs"}; D = null; renderSheet(); },
  dcadd: el => busy(el, async () => {
    const body = {code: ($("#dc-code")?.value || "").trim(),
      kind: $("#dc-kind")?.value || "pct",
      value: ($("#dc-value")?.value || "").trim(),
      max: ($("#dc-max")?.value || "").trim(),
      days: ($("#dc-days")?.value || "").trim()};
    if(!body.code || !body.value) return toast("کد و مقدار تخفیف را بنویس");
    try{
      await api(`/api/bots/${S.cur.id}/dcodes`, "POST", body);
      S2._dcs = undefined; renderSheet(); toast("کد ساخته شد"); haptic("ok");
    }catch(e){ toast(e.message || "ساخت کد ناموفق بود"); }
  }),
  dcdel: el => busy(el, async () => {
    await api(`/api/bots/${S.cur.id}/dcodes/${encodeURIComponent(el.dataset.c)}`, "DELETE");
    S2._dcs = undefined; renderSheet();
  }),
});

/* ═════════════════ ۶) شبیه‌ساز چت ═════════════════
   موتور بدون تماس با تلگرام و بدون هزینه اجرا می‌شود: همان معنای کانفیگ (متغیر، شرط،
   اکشن، فرم، دستیار ساختگی، پرداخت ساختگی) در مرورگر. حالت گروه با چند کاربر ساختگی. */
const SIM = {on: false, mode: "pv", users: [], ui: 0, glo: {}, tables: {}, clock: 0, timers: [], log: [], scens: [], rec: []};
const SIM_NAMES = ["آرش", "سارا", "نیما"];
const SIM_TZ = 3.5 * 3600 * 1000;

function simInit(){
  SIM.mode = "pv"; SIM.ui = 0; SIM.glo = {}; SIM.tables = {}; SIM.timers = []; SIM.log = [];
  SIM.clock = Date.now();
  SIM.users = SIM_NAMES.map((n, i) => ({id: 1000 + i, name: n, vars: {}, visits: 0, refs: 0, expect: null, chat: []}));
  try{ SIM.scens = JSON.parse(localStorage.getItem("azadi.sim." + S.cur.id) || "[]"); }catch(_){ SIM.scens = []; }
  if(SIM.dcs === undefined) api(`/api/bots/${S.cur.id}/dcodes`).then(d => { SIM.dcs = d.items || []; }).catch(() => { SIM.dcs = []; });
}
const simU = () => SIM.users[SIM.ui] || SIM.users[0];
function simVar(st, k){
  if(k === "name" || k === "first_name") return st.name;
  if(k === "full_name") return st.name;
  if(k === "last_name") return "";
  if(k === "username") return "@" + st.name.toLowerCase();
  if(k === "id") return String(st.id);
  if(k === "lang") return "fa";
  if(k === "premium") return "0";
  if(k === "is_owner") return "0";
  if(k === "bot_name") return S.cur.config.name || "";
  if(k === "bot_username") return S.cur.username ? "@" + S.cur.username : "";
  if(k === "text") return st._last || "";
  if(k === "visits") return String(st.visits);
  if(k === "refs") return String(st.refs);
  if(k === "ticket_no") return "";
  if(k === "ref_link") return "https://t.me/" + (S.cur.username || "bot") + "?start=ref_" + st.id;
  const d = new Date(SIM.clock + SIM_TZ);
  if(k === "date"){ const j = simJalali(d); return `${j[0]}/${String(j[1]).padStart(2, "0")}/${String(j[2]).padStart(2, "0")}`; }
  if(k === "time") return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  if(k === "hour") return String(d.getHours());
  if(k === "weekday") return ["یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه"][d.getDay()];
  if(k in (S.cur.config.globals || {})) return String(SIM.glo[k] ?? (S.cur.config.globals || {})[k] ?? "");
  if(k in st.vars) return String(st.vars[k] ?? "");
  return String((S.cur.config.vars || {})[k] ?? "");
}
function simJalali(d){
  const gy = d.getFullYear(), gm = d.getMonth() + 1, gd = d.getDate();
  const gdm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
  const gy2 = gm > 2 ? gy + 1 : gy;
  let days = 355666 + 365 * gy + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) + Math.floor((gy2 + 399) / 400) + gd + gdm[gm - 1];
  let jy = -1595 + 33 * Math.floor(days / 12053); days %= 12053;
  jy += 4 * Math.floor(days / 1461); days %= 1461;
  if(days > 365){ jy += Math.floor((days - 1) / 365); days = (days - 1) % 365; }
  let jm, jd;
  if(days < 186){ jm = 1 + Math.floor(days / 31); jd = 1 + (days % 31); }
  else { jm = 7 + Math.floor((days - 186) / 30); jd = 1 + ((days - 186) % 30); }
  return [jy, jm, jd];
}
function simFill(t, st){
  return String(t ?? "").replace(/\{([a-z][a-z0-9_]{0,19})(?:\|([^{}]{0,60}))?\}/gi, (m, k, def) => {
    let v = simVar(st, k);
    if(v === "" && def != null) return def;
    return v == null ? m : String(v);
  });
}
function simCheck(c, st, depth = 0){
  if(!c || typeof c !== "object" || depth > 3) return false;
  if(Array.isArray(c.all)) return c.all.every(x => simCheck(x, st, depth + 1));
  if(Array.isArray(c.any)) return c.any.some(x => simCheck(x, st, depth + 1));
  if(c.not) return !simCheck(c.not, st, depth + 1);
  if(c.op === "sub") return simSubOk(st, c.plan);
  const a = String(simVar(st, c.var) ?? ""), op = c.op || "==";
  if(op === "empty") return a.trim() === "";
  if(op === "filled") return a.trim() !== "";
  const b = simFill(c.value ?? "", st);
  if(op === "contains") return b.casefold ? b.toLowerCase().includes(a.toLowerCase()) : a.toLowerCase().includes(b.toLowerCase());
  const x = parseFloat(a), y = parseFloat(b);
  if(op === "==") return (!isNaN(x) && !isNaN(y) ? x === y : a.trim().toLowerCase() === b.trim().toLowerCase());
  if(op === "!=") return !simCheck({...c, op: "=="}, st, depth + 1);
  if(isNaN(x) || isNaN(y)) return false;
  return op === ">" ? x > y : op === ">=" ? x >= y : op === "<" ? x < y : op === "<=" ? x <= y : false;
}
function simSet(st, k, v){
  if(k in (S.cur.config.globals || {})) SIM.glo[k] = String(v);
  else if(k in (S.cur.config.vars || {})) st.vars[k] = String(v);
}
function simAdd(st, k, val){
  const m = /^(\d+)-(\d+)$/.exec(String(val).trim());
  const amt = m ? Math.floor(Math.random() * (+m[2] - +m[1] + 1)) + +m[1] : (parseFloat(val) || 0);
  if(k in (S.cur.config.globals || {})) SIM.glo[k] = String((parseFloat(SIM.glo[k] ?? (S.cur.config.globals || {})[k]) || 0) + amt);
  else st.vars[k] = String((parseFloat(st.vars[k] ?? (S.cur.config.vars || {})[k]) || 0) + amt);
}
function simTables(t, scope){
  SIM.tables[t] = SIM.tables[t] || [];
  return SIM.tables[t];
}
function simDo(acts, st){
  for(const a of acts || []){
    const val = simFill(a.value ?? "", st);
    switch(a.op){
      case "set": simSet(st, a.var, val); break;
      case "add": case "db_inc": simAdd(st, a.var || a.k, val || "1"); break;
      case "clear": delete st.vars[a.var]; break;
      case "random": {
        const m = /^(\d+)-(\d+)$/.exec(val.trim()); const lo = m ? +m[1] : 1, hi = m ? +m[2] : 6;
        simSet(st, a.var, String(Math.floor(Math.random() * (hi - lo + 1)) + lo)); break;
      }
      case "pick": { const o = val.split("|").map(x => x.trim()).filter(Boolean); if(o.length) simSet(st, a.var, o[Math.floor(Math.random() * o.length)]); break; }
      case "dice": { const MX = {"🎲": 6, "🎯": 6, "🏀": 5, "⚽": 5, "🎳": 6, "🎰": 64}; simSet(st, a.var, String(1 + Math.floor(Math.random() * ((MX[a.emoji] || 6))))); break; }
      case "notify": simBot("خبر برای صاحب ربات: " + simFill(a.value || "(خبر)", st), st, true); break;
      case "remind": SIM.timers.push({at: SIM.clock + (a.minutes || 60) * 60000, text: simFill(a.value || "یادآوری", st), st}); simSys("یادآوری ساخته شد: " + simFill(a.value || "…", st)); break;
      case "db_add": { const tab = simTables(a.table); if(tab.length < 500) tab.push({u: st.id, d: Object.fromEntries(Object.entries(a.data || {}).map(([k, v]) => [k, simFill(v, st)]))}); break; }
      case "db_del": { const tab = simTables(a.table); const w = a.when; SIM.tables[a.table] = tab.filter(r => !(w ? simCheck(w, st) : (a.scope !== "all" && r.u === st.id))); break; }
      case "db_get": { const tab = simTables(a.table), w = a.when; const r = [...tab].reverse().find(r => !w || simCheck(w, st));
        for(const f of ((S.cur.config.dbfields || {})[a.table] || [])) simSet(st, (a.var ? a.var + "_" : "") + f, r ? (r.d[f] ?? "") : ""); break; }
      case "db_set": { const tab = simTables(a.table), w = a.when;
        tab.forEach(r => { if(!w || simCheck(w, st)) Object.entries(a.data || {}).forEach(([k, v]) => r.d[k] = simFill(v, st)); }); break; }
      case "fetch": simSet(st, a.var, ""); break;
      case "send": { const nid = a.node; if(S.cur.config.nodes[nid]) simSend(nid, st); break; }
      case "game_play": simSys("بازی «" + (a.game || "") + "» شروع می‌شود (در ربات واقعی، کارت بازی باز می‌شود)"); break;
      case "calc": { const v = simCalc(simFill(a.value || "", st)); if(v !== null) simSet(st, a.var, v); break; }
      case "disc": simDisc(a, st); break;
      case "sub_add": { const plan = (a.plan || "vip").toLowerCase(); const days = Math.max(1, parseFloat(simFill(a.days || "30", st)) || 30);
        st.subs = st.subs || {}; const cur = st.subs[plan] || 0; st.subs[plan] = Math.max(SIM.clock, cur) + days * 86400000;
        if(a.var){ st.vars[a.var] = plan; st.vars[a.var + "_exp"] = new Date(st.subs[plan]).toLocaleDateString("fa-IR-u-nu-latn"); }
        simSys("اشتراک «" + plan + "» برای " + days + " روز فعال شد"); break; }
      case "sub_del": { const plan = (a.plan || "vip").toLowerCase(); if(st.subs) delete st.subs[plan];
        simSys(" اشتراک «" + plan + "» لغو شد"); break; }
    }
  }
}
function simSubOk(st, plan){
  const subs = st.subs || {};
  if(!plan) return Object.values(subs).some(x => x > SIM.clock);
  return (subs[String(plan).toLowerCase()] || 0) > SIM.clock;
}
function simCalc(expr){
  const s = String(expr || "").replace(/\s+/g, "");
  if(!s || !/^[0-9+\-*/%.()]+$/.test(s)) return null;
  try{
    const out = [], ops = [];                          // شنت‌یارد کوچک (بدون eval)
    const PR = {"+": 1, "-": 1, "*": 2, "/": 2, "%": 2};
    let prev = "";
    for(let i = 0; i < s.length; i++){
      const ch = s[i];
      if(/[0-9.]/.test(ch)){ let j = i; while(j < s.length && /[0-9.]/.test(s[j])) j++; out.push(parseFloat(s.slice(i, j))); i = j - 1; prev = "n"; continue; }
      if(ch === "("){ ops.push(ch); prev = "("; continue; }
      if(ch === ")"){ while(ops.length && ops[ops.length - 1] !== "(") out.push(ops.pop()); if(!ops.length) return null; ops.pop(); prev = ")"; continue; }
      if(!(ch in PR)) return null;
      if((ch === "-" || ch === "+") && (prev === "" || prev === "(" || prev in PR)) out.push(0);   // منفیِ یکانی
      while(ops.length && PR[ops[ops.length - 1]] >= PR[ch]) out.push(ops.pop());
      ops.push(ch); prev = ch;
    }
    while(ops.length){ if(ops[ops.length - 1] === "(") return null; out.push(ops.pop()); }
    const st2 = [];
    for(const t of out){
      if(typeof t === "number") st2.push(t);
      else { const y = st2.pop(), x = st2.pop(); if(x === undefined || y === undefined) return null;
        st2.push(t === "+" ? x + y : t === "-" ? x - y : t === "*" ? x * y : t === "/" ? (y === 0 ? NaN : x / y) : (y === 0 ? NaN : x % y)); }
    }
    const v = st2.pop();
    if(st2.length || v === undefined || !isFinite(v)) return null;
    return String(Math.round(v * 1e6) / 1e6);
  }catch(_){ return null; }
}
function simDisc(a, st){
  const name = a.var || "code";
  const code = String(simVar(st, name) || "").replace(/[\s-]/g, "").toUpperCase();
  const price = parseFloat(simFill(a.price || "0", st)) || 0;
  const put = (k, v) => { st.vars[name + k] = String(v); };
  const d = (SIM.dcs || []).find(x => x.code === code && !x.dead);
  let off = null, err = "";
  if(!code) err = "کد وارد نشده";
  else if(!d) err = "کد تخفیف پیدا نشد";
  else if(d.max && d.used >= d.max) err = "ظرفیت این کد پر شده";
  else{
    const val = parseFloat(d.value) || 0;
    off = Math.min(d.kind === "amt" ? val : price * val / 100, price);
    d.used++;
  }
  if(off === null){ put("_ok", ""); put("_off", price || ""); put("_save", "0"); put("_err", err || "کد اعمال نشد"); }
  else{ put("_ok", "1"); put("_off", Math.round((price - off) * 100) / 100); put("_save", Math.round(off * 100) / 100); put("_err", ""); }
}
function simRoute(n, st){
  for(const r of n.route || []) if(simCheck(r.when, st)) return r.goto;
  return null;
}
function simAlt(n, st){
  for(const r of n.alt || []) if(simCheck(r.when, st)) return r.text;
  return null;
}
function simListHTML(n, st){
  const ls = n.list; if(!ls) return "";
  const tab = simTables(ls.table);
  let rows = tab.filter(r => ls.scope === "all" || r.u === st.id);
  if(ls.when){ const w = ls.when;
    rows = rows.filter(r => {
      const a = String(r.d[w.var] ?? ""), op = w.op || "==", b = String(w.value ?? "");
      if(op === "empty") return a.trim() === "";
      if(op === "filled") return a.trim() !== "";
      if(op === "contains") return a.toLowerCase().includes(b.toLowerCase());
      const x = parseFloat(a), y = parseFloat(b);
      if(op === "==") return (!isNaN(x) && !isNaN(y) ? x === y : a.trim().toLowerCase() === b.trim().toLowerCase());
      if(op === "!=") return !(x === y);
      if(isNaN(x) || isNaN(y)) return false;
      return op === ">" ? x > y : op === ">=" ? x >= y : op === "<" ? x < y : op === "<=" ? x <= y : false;
    });
  }
  if(ls.order !== "old") rows = rows.slice().reverse();
  rows = rows.slice(0, ls.limit || 5);
  if(!rows.length) return ls.empty || "هنوز چیزی ثبت نشده.";
  return rows.map((r, i) => simFill((ls.line || "#{n}").replace(/\{([a-z0-9_]+)\}/g, (m, k) => k === "n" ? String(i + 1) : k === "u" ? (SIM.users.find(x => x.id === r.u) || {}).name || "?" : (r.d[k] ?? "")), st)).join("\n");
}
function simRich(text){
  /* متن تلگرامی (b, i, u, s, code, pre, a, blockquote) را مثل خود تلگرام نشان می‌دهد؛ هر چیز دیگر امن و خام می‌ماند */
  return tgHtml(text).replace(/(<[^>]*>)|(\d+)/g, (m, tag, num) => tag ? tag : `<span class="n">${num}</span>`).replace(/\n/g, "<br>");
}
function simMsgHTML(text, kind, kw){
  return `<div class="sm ${kind || ""}" ${kw || ""}>${simRich(text)}</div>`;
}
function simBot(text, st, quiet){
  const u = simU();
  u.chat.push({who: "bot", text});
  simPaint();
}
function simSys(text){ simU().chat.push({who: "sys", text}); simPaint(); }
function simUserMsg(text, st){ st.chat.push({who: "me", text}); simPaint(); }

function simButtonsHTML(n){
  const rows = n.buttons || [];
  if(!rows.length) return "";
  const inl = rows.filter(r => !r.some(b => b.kb === "reply"));
  const rpl = rows.filter(r => r.some(b => b.kb === "reply"));
  const btn = (b, id) => `<button class="sbtn" data-simb="${id}">${esc(simU() ? simFill(b.text, simU()) : b.text)}</button>`;
  const vis = (b, i, j) => !b.when || simCheck(b.when, simU()) ? btn(b, i + "." + j) : "";
  let h = "";
  for(const [i, row] of inl.entries()){ const cells = row.map((b, j) => vis(b, i, j)).join(""); if(cells) h += `<div class="srow">${cells}</div>`; }
  for(const [i, row] of rpl.entries()){ const cells = row.map((b, j) => vis(b, "r" + i, j)).join(""); if(cells) h += `<div class="srow kb">${cells}</div>`; }
  return h ? `<div class="skb">${h}</div>` : "";
}
function simExpectHTML(st){
  if(!st.expect) return "";
  const n = S.cur.config.nodes[st.expect.nid];
  if(!n) return "";
  if(n.fields && st.expect.qi < n.fields.length) return `<div class="shint">${esc(n.fields[st.expect.qi])} ${n.types?.[st.expect.qi] === "number" ? "(فقط عدد)" : ""}</div>`;
  if(n.ask) return `<div class="shint">پیامت را بنویس…</div>`;
  return "";
}
function simSend(nid, st){
  const cfg = S.cur.config, n = cfg.nodes[nid];
  if(!n) return;
  st.visits++;
  st._lastNode = nid;
  try{ stHot(nid, true); }catch(_){}
  setTimeout(() => { try{ stHot(nid, false); }catch(_){} }, 1200);
  simDo(n.do, st);
  st.expect = null;
  if(n.ai){
    simBot(simFill(simAlt(n, st) || n.text, st), st);
    simBot("(پاسخ آزمایشی دستیار؛ در ربات واقعی، پاسخ هوشمند همین‌جا نمایش داده می‌شود)", st);
    simPaint();
    return;
  }
  let text = simAlt(n, st) || n.text;
  const lt = simListHTML(n, st);
  if(lt) text += "\n" + lt;
  if(n.board) text += "\n(جدول برترین‌ها در ربات واقعی اینجا نمایش داده می‌شود)";
  simBot(simFill(text, st), st);
  if(n.join) { simBot("(قفل عضویت؛ در ربات واقعی، تا زمانی که کاربر عضو کانال نشود ادامه پیدا نمی‌کند)", st); simPaint(); return; }
  const goto2 = simRoute(n, st);
  if(goto2) return simSend(goto2, st);
  if(n.fields?.length || n.ask){
    st.expect = {nid, qi: 0};
    simPaint();
    return;
  }
  simPaint();
}
function simFindBtn(nid, key){
  const n = S.cur.config.nodes[nid];
  if(!n) return null;
  const rows = n.buttons || [];
  const inl = rows.filter(r => !r.some(b => b.kb === "reply"));
  const rpl = rows.filter(r => r.some(b => b.kb === "reply"));
  const m = /^(r?)(\d+)[._](\d+)$/.exec(String(key));
  if(!m) return null;
  return ((m[1] ? rpl : inl)[+m[2]] || [])[+m[3]] || null;
}
function simPress(id, key){
  const st = simU(), b = simFindBtn(id, key);
  if(!b) return;
  st.chat.push({who: "me", text: simFill(b.text, st)});
  if(b.pay){
    simDo(b.do, st);
    simSys("پرداخت آزمایشی تأیید شد («" + simFill(b.pay.title || b.text, st) + "»)");
    if(b.pay.text) simBot(simFill(b.pay.text, st), st);
    if(b.pay.goto) return simSend(b.pay.goto, st);
    return simPaint();
  }
  simDo(b.do, st);
  if(b.alert !== undefined && b.alert !== ""){ simBot(simFill(b.alert, st), st); return simPaint(); }
  if(b.copy){ simSys("متن کپی شد: " + simFill(b.copy, st)); return simPaint(); }
  if(b.share){ simSys("پنجره‌ی اشتراک‌گذاری لینک دعوت باز می‌شود"); return simPaint(); }
  if(b.url){ simSys("لینک باز می‌شود: " + simFill(b.url, st)); return simPaint(); }
  if(b.app !== undefined){ simSys("مینی‌اپ باز می‌شود (در ربات واقعی)"); return simPaint(); }
  if(b.goto) return simSend(b.goto, st);
  simPaint();
}
function simUserText(raw){
  const st = simU(), cfg = S.cur.config;
  st._last = raw;
  st.chat.push({who: "me", text: raw});
  SIM.rec.push({type: "text", v: raw, u: SIM.ui});
  if(SIM.mode === "group"){
    const trs = (cfg.group || {}).triggers || [];
    for(const t of trs){
      const hay = raw.toLowerCase(), hit = (t.words || []).some(w => t.on === "command" ? hay === "/" + w : t.on === "exact" ? hay === w.toLowerCase() : t.on === "starts" ? hay.startsWith(w.toLowerCase()) : hay.includes(w.toLowerCase()));
      if(!hit) continue;
      simDo(t.do, st);
      if(t.reply) simBot(simFill(t.reply, st), st);
      if(t.delete) simSys("پیام کاربر پاک شد");
      return simPaint();
    }
  }
  if(st.expect){
    const n = cfg.nodes[st.expect.nid];
    if(n?.fields){
      const qi = st.expect.qi, ty = (n.types || [])[qi] || "text", v = (n.save || [])[qi];
      let ok = true;
      if(ty === "number") ok = !isNaN(parseFloat(raw));
      if(ty === "phone") ok = /^\+?\d{8,15}$/.test(raw.replace(/[\s\-()]/g, ""));
      if(ty === "email") ok = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(raw);
      if(!ok) { simBot(({number: "فقط عدد بفرست.", phone: "یک شماره‌ی معتبر بفرست (مثل 09123456789).", email: "یک ایمیل معتبر بفرست."}[ty] || "دوباره و درست بنویس."), st); return simPaint(); }
      if(v) simSet(st, v, raw);
      if(qi + 1 < n.fields.length){ st.expect.qi++; return simPaint(); }
      if(n.done) simBot(simFill(n.done, st), st);
      st.expect = null;
      if(n.next) return simSend(n.next, st);
      return simPaint();
    }
    if(n?.ask){
      st.expect = null;
      if(n.done) simBot(simFill(n.done, st), st);
      if(n.next) return simSend(n.next, st);
      return simPaint();
    }
  }
  const fb = cfg.fallback && cfg.nodes[cfg.fallback] ? cfg.fallback : cfg.start;
  simSend(fb, st);
}
function simEvent(kind){
  const st = simU();
  SIM.rec.push({type: "event", v: kind, u: SIM.ui});
  if(kind === "join"){
    simSys("عضو جدید وارد گروه شد: " + st.name);
    const w = (S.cur.config.mod || {}).welcome;
    if(w) simBot(simFill(w, st).replace(/\{group\}/g, "این گروه"), st);
    else simBot("(پیام خوش‌آمد تنظیم نشده — در «مدیریت گروه و کانال» بگذار)", st);
  }
  if(kind === "leave") simSys(st.name + " گروه را ترک کرد");
  if(kind === "pay"){ simSys("یک پرداخت آزمایشی انجام شد"); simBot("پرداخت دریافت شد. ممنون!", st); }
  if(kind === "jump"){ SIM.clock += 3600 * 1000; simSys("زمان یک ساعت جلو رفت؛ ساعت الان " + simVar(st, "time") + " است");
    const due = SIM.timers.filter(x => x.at <= SIM.clock);
    for(const x of due) simBot(x.text, st);
    SIM.timers = SIM.timers.filter(x => x.at > SIM.clock);
  }
  simPaint();
}
function simPaint(){
  const st = simU();
  const log = $("#simlog");
  if(!log) return;
  log.innerHTML = st.chat.map(m => m.who === "bot" ? simMsgHTML(m.text, "bot") : m.who === "me" ? simMsgHTML(m.text, "me") : `<div class="sm sys">${digitsHTML(m.text)}</div>`).join("")
    + `<div id="simmk"></div>`;
  const mk = $("#simmk");
  const lastBot = [...st.chat].reverse().find(m => m.who === "bot");
  const nid = st._lastNode;
  mk.innerHTML = (st.expect ? simExpectHTML(st) : "") + (nid && S.cur.config.nodes[nid] && !st.expect ? simButtonsHTML(S.cur.config.nodes[nid]) : "");
  log.scrollTop = log.scrollHeight;
}
/* بازچینش کامل قاب شبیه‌ساز (حالت/کاربر عوض شد) بدون از دست رفتن گفتگو */
function simRerender(){
  const w = $("#simwrap");
  if(!w) return;
  w.outerHTML = simHTML();
  simPaint();
}
function simHTML(){
  const b = S.cur;
  const users = SIM.users.map((u, i) => `<button class="chip ${i === SIM.ui ? "on" : ""}" data-a="simuser" data-i="${i}">${esc(u.name)}</button>`).join("");
  return `<div class="simwrap" id="simwrap">
    <div class="simbar">
      <div class="simr1"><b>${IC.sim} شبیه‌ساز</b>
        <div class="seg simseg">
          <button class="${SIM.mode === "pv" ? "on" : ""}" data-a="simmode" data-v="pv">چت خصوصی</button>
          <button class="${SIM.mode === "group" ? "on" : ""}" data-a="simmode" data-v="group">گروه</button>
        </div>
        <button class="iconb" data-a="simclose" aria-label="بستن شبیه‌ساز">${IC.x}</button></div>
      ${SIM.mode === "group" ? `<div class="simr2"><div class="simusers">${users}</div></div>` : ""}
      <div class="simr3">
        ${SIM.mode === "group" ? `<button class="b t" data-a="simev" data-v="join">${IC.plus}عضو جدید</button>` : ""}
        <button class="b t" data-a="simev" data-v="pay">${IC.coin}پرداخت آزمایشی</button>
        <button class="b t" data-a="simev" data-v="jump">${IC.clock}جلو بردن زمان</button>
        <button class="b t" data-a="simreset">${IC.refresh}شروع دوباره</button>
      </div>
    </div>
    <div class="simbody">
      <div class="simphone"><div class="simchat" id="simlog"></div>
        <div class="simcomp"><input id="simtext" placeholder="پیامت را بنویس…" autocomplete="off"><button class="b" data-a="simsend">ارسال</button></div>
        <div id="simkbd"></div></div>
      <div class="simside">
        <p class="muted">این فقط یک شبیه‌سازی است و توکنی مصرف نمی‌کند. هر بخشی که اجرا شود، روی نقشه سبز می‌شود.</p>
        <button class="b o sm" data-a="simstart">${IC.play}اجرای /start</button>
        <div class="sub"><span>سناریوها</span><button class="b o sm" data-a="simscsave">${IC.copy}ذخیره‌ی سناریو</button></div>
        ${SIM.scens.length ? SIM.scens.map((s, i) => `<button class="gi" data-a="simscgo" data-i="${i}"><span class="ib">${IC.play}</span><span class="gt"><b>${esc(s.name || "سناریو " + (i + 1))}</b><span>اجرای خودکار</span></span></button>`).join("") : `<p class="muted">سناریویی ذخیره نشده.</p>`}
      </div>
    </div></div>`;
}
Object.assign(A, {
  simopen: () => {
    if(!S.cur) return toast("اول یک ربات انتخاب کن");
    simInit();
    SIM.on = true;
    SIM.rec = [];
    document.getElementById("app").insertAdjacentHTML("beforeend", simHTML());
    simPaint();
  },
  simclose: () => { SIM.on = false; $("#simwrap")?.remove(); },
  simreset: () => { simInit(); SIM.rec = []; simRerender(); },
  simmode: el => { SIM.mode = el.dataset.v; SIM.ui = 0; simU().chat.push({who: "sys", text: SIM.mode === "group" ? "حالت گروه: پاسخ‌ها همان‌جا در گروه نمایش داده می‌شود" : "حالت چت خصوصی"}); simRerender(); },
  simuser: el => { SIM.ui = +el.dataset.i; simRerender(); },
  simev: el => simEvent(el.dataset.v),
  simsend: () => { const inp = $("#simtext"), v = (inp?.value || "").trim(); if(!v) return; inp.value = ""; simUserText(v); },
  simstart: () => { const st = simU(); SIM.rec.push({type: "start", u: SIM.ui}); st.chat = st.chat.filter(m => m.who === "sys"); simSend(S.cur.config.start, st); },
  simscsave: () => {
    if(!SIM.rec.length) return toast("اول چند مرحله را در شبیه‌ساز انجام بده (پیام، دکمه یا رویداد)");
    SIM.scens.push({name: "سناریو " + new Date().toLocaleTimeString("fa-IR-u-nu-latn", {hour: "2-digit", minute: "2-digit"}), steps: JSON.parse(JSON.stringify(SIM.rec.slice(-60)))});
    SIM.scens = SIM.scens.slice(-6);
    try{ localStorage.setItem("azadi.sim." + S.cur.id, JSON.stringify(SIM.scens)); }catch(_){}
    toast("سناریو ذخیره شد؛ بعداً با یک لمس اجرایش کن"); simRerender();
  },
  simscgo: el => {
    const sc = SIM.scens[+el.dataset.i]; if(!sc) return;
    simInit();
    SIM.on = true;
    for(const s of sc.steps){
      SIM.ui = s.u || 0;
      const st = simU();
      if(s.type === "text") simUserText(s.v);
      else if(s.type === "start") simSend(S.cur.config.start, st);
      else simEvent(s.v);
    }
    SIM.rec = JSON.parse(JSON.stringify(sc.steps));
    SIM.ui = 0;
    simRerender();
    toast("سناریو اجرا شد");
  },
});
document.addEventListener("click", e => {
  const b = e.target.closest("[data-simb]");
  if(!b || !SIM.on) return;
  const st = simU();
  if(st._lastNode) simPress(st._lastNode, b.dataset.simb);
});
document.addEventListener("keydown", e => {
  if(e.key !== "Enter" || !SIM.on) return;
  if(e.target?.id === "simtext"){ e.preventDefault(); A.simsend(); }
});

/* ───────────────────────── ۱۰) چندانتخابی بخش‌ها + کپی بین بات‌ها ───────────────────────── */
function stSelBar(){
  const cv = $("#stc");
  const bar = $("#selbar");
  const n = (S2.sel || []).length;
  if(!ST.selMode){
    if(bar) bar.remove();
    cv?.classList.remove("selsel");
    cv?.querySelectorAll(".stc-card.sel").forEach(c => c.classList.remove("sel"));
    return;
  }
  cv?.classList.add("selsel");
  if(!bar){
    const d = document.createElement("div");
    d.id = "selbar";
    d.innerHTML = `<b id="selcount"></b>
      <button class="b t sm" data-a="selcopy">${IC.copy}کپی به ربات دیگر</button>
      <button class="b r sm" data-a="seldel">${IC.x}حذف</button>
      <button class="b o sm" data-a="selselx">پایان</button>`;
    cv.appendChild(d);
  }
  const c = $("#selcount");
  if(c) c.textContent = n ? N(n) + " بخش انتخاب شده" : "روی بخش‌ها بزن تا انتخاب شوند";
}
function stSelToggle(id){
  S2.sel = S2.sel || [];
  const i = S2.sel.indexOf(id);
  if(i >= 0) S2.sel.splice(i, 1); else S2.sel.push(id);
  const card = $("#stc")?.querySelector(`.stc-card[data-id="${CSS.escape(id)}"]`);
  if(card) card.classList.toggle("sel", S2.sel.includes(id));
  stSelBar();
  haptic();
}
Object.assign(A, {
  selsel: () => {
    if(!S.cur) return toast("اول یک ربات انتخاب کن");
    ST.selMode = !ST.selMode;
    S2.sel = [];
    stSelBar();
    toast(ST.selMode ? "حالت انتخاب: روی بخش‌ها بزن (دوباره بزن تا خالی شود)" : "حالت انتخاب خاموش شد");
  },
  selselx: () => A.selsel(),
  seldel: el => {
    const ids = [...(S2.sel || [])];
    if(!ids.length) return toast("اول بخشی را انتخاب کن");
    const startId = S.cur.config.start;
    if(ids.includes(startId)) return toast("بخش شروع را نمی‌شود حذف کرد؛ اول از انتخاب‌ها بردارش");
    busy(el, () => commit(cfg => {
      for(const id of ids) delete cfg.nodes[id];
      for(const n of Object.values(cfg.nodes)){
        for(const row of n.buttons || []) for(const b of row) if(b.goto && !cfg.nodes[b.goto]) b.goto = startId;
        for(const r of n.route || []) if(r.goto && !cfg.nodes[r.goto]) r.goto = startId;
        if(n.next && !cfg.nodes[n.next]) delete n.next;
      }
    }, N(ids.length) + " بخش حذف شد و دکمه‌های سرگردان به شروع وصل شدند"));
    ST.selMode = false; S2.sel = []; stSelBar();
  },
  selcopy: () => {
    const ids = [...(S2.sel || [])];
    if(!ids.length) return toast("اول بخشی را انتخاب کن");
    S2._cpset = ids;
    S2._cpbot = undefined;
    S.sheet = {kind: "cpbot"}; D = null; renderSheet();
  },
});
function cpbotSheet(){
  const others = (S.bots || []).filter(b => b.id !== S.cur.id);
  if(!others.length) return head("کپی بخش‌ها به ربات دیگر") + `<p class="muted">ربات دیگری نداری؛ اول یکی بساز.</p><div class="fgap"></div>`;
  const other = others.find(b => b.id === S2._cpbot);
  let body = `<span class="lbl">به کدام ربات اضافه شود؟</span>
    <div class="chips">${others.map(b => `<button type="button" class="chip${other && b.id === other.id ? " on" : ""}" data-a="cppick" data-id="${esc(b.id)}">${esc(b.name)}</button>`).join("")}</div>`;
  if(other && (other.config?.nodes)){
    const src = other.config, cur = S.cur.config;
    const ids = (S2._cpset || []).filter(x => src.nodes[x]);
    const taken = new Set(Object.keys(cur.nodes));
    const clash = ids.filter(x => taken.has(x)).length;
    body += `<div class="sub"><span>${N(ids.length)} بخش انتخاب‌شده از «${esc(other.name)}»</span></div>
      ${ids.map(x => `<div class="vdl">${esc(titleOf(src, x))} <small dir="ltr">${esc(x)}</small></div>`).join("") || `<p class="muted">چیزی انتخاب نشده.</p>`}
      ${clash ? `<p class="muted">نام‌های همنام خودکار تازه می‌شوند.</p>` : ""}
      <div class="bar"><button class="b" data-a="cpdo"${ids.length ? "" : " disabled"}>${IC.copy}افزودن به «${esc(S.cur.name)}»</button></div>`;
  }
  return head("کپی بخش‌ها به ربات دیگر") + body + `<div class="fgap"></div>`;
}
Object.assign(SHEETS, {cpbot: {html: cpbotSheet}});
Object.assign(A, {
  cppick: el => { S2._cpbot = el.dataset.id; renderSheet(); },
  cpdo: el => busy(el, () => {
    const other = (S.bots || []).find(b => b.id === S2._cpbot);
    const ids = (S2._cpset || []).filter(x => other?.config?.nodes?.[x]);
    if(!other || !ids.length) return toast("اول ربات و بخش‌ها را انتخاب کن");
    commit(cfg => {
      const taken = new Set(Object.keys(cfg.nodes));
      const map = {};
      for(const id of ids){
        let nid = ("cp_" + id).replace(/[^a-z0-9_]/g, "").slice(0, 28) || "cp_x";
        while(taken.has(nid)) nid = nid.slice(0, 26) + "c";
        taken.add(nid);
        map[id] = nid;
      }
      for(const id of ids){
        const n = JSON.parse(JSON.stringify(other.config.nodes[id]));
        for(const row of n.buttons || []) for(const b of row) if(b.goto) b.goto = map[b.goto] || cfg.start;
        for(const r of n.route || []) if(r.goto) r.goto = map[r.goto] || cfg.start;
        if(n.next) n.next = map[n.next] || cfg.start;
        cfg.nodes[map[id]] = n;
      }
      const st = cfg.nodes[cfg.start];
      if(st){
        const b = {text: "بخش تازه", goto: map[ids[0]]};
        const row = (st.buttons || []).find(r => r.length < 3);
        if(row) row.push(b); else st.buttons = (st.buttons || []).concat([[b]]);
      }
    }, N(ids.length) + " بخش کپی شد و دکمه‌ی ورود به آن در «شروع» اضافه شد");
    ST.selMode = false; S2.sel = []; stSelBar(); closeSheet();
  }),
});
