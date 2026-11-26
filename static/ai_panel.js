/* ═══════════════════════════════════════════════════════════════
   ai_panel.js — پنل کشویی دستیار هوش مصنوعی در استودیو (BUILD 3.6.0)

   نقش: نسخهٔ جمع‌وجور اما کامل دستیار ساخت، داخل محیط استودیو:
   • ساخت از صفر / توسعهٔ پروژهٔ فعلی با یک درخواست (خط Spec → کامپایلر قطعی → تست پذیرش)
   • پیش‌نمایش شفاف قبل از ساخت: ✔ قابل اجرا · ❌ محدودیت موتور · 🧩 بدون ماژول آماده
   • ویزارد کاملاً دستی (بدون هوش مصنوعی و بدون هزینه)
   • سه قالب جامع
   باز/بسته‌کردن پنل هیچ وضعیت استودیو، ویرایش باز یا تغییرات ذخیره‌نشده را از بین نمی‌برد.
   ═══════════════════════════════════════════════════════════════ */
"use strict";

const AIP = {
  open: false,
  el: null,

  toggle(){
    this.open ? this.close() : this.show();
  },

  show(){
    if(!this.el){
      this.el = document.createElement("aside");
      this.el.className = "aiwrap";
      this.el.setAttribute("dir", "rtl");
      document.body.appendChild(this.el);
    }
    this.open = true;
    this.el.classList.add("on");
    this.render();
  },

  close(){
    /* بستن پنل: هیچ وضعیت پروژه، ویرایش باز یا تغییرات ذخیره‌نشده پاک نمی‌شود */
    if(!this.el) return;
    this.open = false;
    this.el.classList.remove("on");
    if(this._pollT){ clearTimeout(this._pollT); this._pollT = null; }
  },

  html(){
    const cur = S.cur, nodes = cur ? Object.keys(cur.config.nodes).length : 0;
    return `
    <header class="aih">
      <b>${IC.spark} دستیار ساخت</b>
      <button class="iconb" data-aip="close" aria-label="بستن">✕</button>
    </header>
    <div class="aib">
      <p class="muted">${cur ? `پروژهٔ باز: <b>${esc(cur.name)}</b> · ${N(nodes)} بخش — درخواستت روی همین پروژه اعمال می‌شود و با «برگشت به نسخهٔ قبلی» قابل بازگشت است.` : "پروژه‌ای باز نیست."}</p>
      <textarea id="aip-prompt" maxlength="4000" placeholder="مثلاً: یک بازی حدس عدد با کیف سکه و رتبه‌بندی اضافه کن"></textarea>
      <div class="bar">
        <button class="b" data-aip="preview">پیش‌نمایش</button>
        <button class="b o" data-aip="build">${IC.spark}${cur ? "ارتقای این ربات" : "ساخت ربات"}</button>
      </div>
      <div class="bar">
        <button class="b sm" data-aip="wizard">${IC.layers}ویزارد بدون هوش مصنوعی</button>
        <button class="b sm" data-aip="tpls">سه قالب آماده</button>
      </div>
      <div id="aip-out" class="aip-out"></div>
    </div>`;
  },

  render(){
    if(!this.el) return;
    this.el.innerHTML = this.html();
    this.el.querySelectorAll("[data-aip]").forEach(b => b.addEventListener("click", () => this.act(b.dataset.aip, b)));
  },

  out(html){ const o = this.el?.querySelector("#aip-out"); if(o) o.innerHTML = html; },

  busy(on, label){
    const btn = this.el?.querySelector('[data-aip="build"]');
    if(btn) btn.disabled = !!on;
    this.out(on ? `<div class="aip-prog">${IC.bot} ${esc(label || "در حال کار…")}</div>` : this._lastOut || "");
  },

  /* ── پیش‌نمایش Spec: شفاف و قبل از هر هزینه‌ای ── */
  async preview(){
    const p = (this.el?.querySelector("#aip-prompt")?.value || "").trim();
    if(p.length < 5) return toast("توضیح بیشتری بنویس");
    this.busy(true, "بررسی قابلیت‌ها…");
    try{
      const d = await api("/api/spec/preview", "POST", { prompt: p });
      this._lastOut = this.renderPreview(d);
      this.busy(false);
    }catch(e){ this.busy(false); toast(e.message || "پیش‌نمایش ممکن نشد"); }
  },

  renderPreview(d){
    if(!d.instant){
      return `<p class="muted">${esc(d.message || "روتر قطعی مطمئن نیست.")}</p>` +
        (d.limits || []).map(l => this.limitRow(l)).join("");
    }
    const pv = d.preview || {};
    const ok = (pv.ok || []).map(x => `<div class="aip-ok">✔ ${esc(x.fa)}</div>`).join("");
    const lim = (pv.engine_limit || []).map(l => this.limitRow(l)).join("");
    const miss = (d.limits || []).filter(l => !pv.engine_limit?.some(x => x.want === l.want)).map(l => this.limitRow(l)).join("");
    return `${ok ? `<div class="sub">قابلیت‌های قابل اجرا (کامپایلر قطعی)</div>${ok}` : ""}` +
      (lim ? `<div class="sub">❌ غیرقابل اجرا با موتور فعلی</div>${lim}` : "") +
      (miss ? `<div class="sub">🟡 موارد نیازمند بررسی</div>${miss}` : "") +
      `<p class="muted">لغو رایگان است؛ ساخت فقط پس از تأیید این پیش‌نمایش و با تست پذیرش موتور تحویل می‌شود.</p>`;
  },

  limitRow(l){
    return `<div class="aip-no">❌ ${esc(l.want || "")}<small>${esc(l.why || "")}</small><small>${esc(l.upgrade || "")}</small></div>`;
  },

  /* ── ساخت/ارتقا با خط Spec (کمترین مصرف مدل) ── */
  async build(){
    const ta = this.el?.querySelector("#aip-prompt");
    const p = (ta?.value || "").trim();
    if(p.length < 5) return toast("توضیح بیشتری بنویس");
    const botId = S.cur?.id || null;
    const cost = needCost(!!botId);
    if(S.wallet.tokens < cost) return openBuy(`این کار حداقل ${cost} توکن می‌خواهد.`);
    this.busy(true, botId ? "در حال ارتقا…" : "در حال ساخت…");
    try{
      const r0 = await api("/api/generate", "POST", { prompt: p, bot_id: botId });
      if(r0.wallet) { S.wallet = r0.wallet; renderTop(); }
      const r = await this.poll(r0.job);
      this.busy(false);
      if(r.status === "review"){ showBuildReview(r); return; }
      /* موفقیت: ربات به‌روز شد؛ در استودیو می‌مانیم و تاریخچه/برگشت در دسترس است */
      if(r.bot){
        S.wallet = r.wallet || S.wallet;
        S.bots = [r.bot, ...S.bots.filter(b => b.id !== r.bot.id)];
        S.cur = r.bot; S.sbot = r.bot.id;
        if(S.view !== "studio"){ S.view = "studio"; }
        render(); bumpTokens();
        toast((botId ? "ربات ارتقا یافت" : "ربات ساخته شد") + (r.cost ? `، ${N(r.cost)} توکن` : "") + " — تست پذیرش موتور پاس شد");
        haptic("ok");
      }
    }catch(e){
      this.busy(false);
      if(e.status === 402) return openBuy(e.message);
      showBuildFailure({job: e.job, canResume: e.canResume, wizard: e.wizard, error: e.message,
                        completedTasks: e.completedTasks, totalTasks: e.totalTasks, buildPhase: e.buildPhase});
    }
  },

  async poll(jid){
    for(let i = 0; i < 1300; i++){
      await sleep(1000);
      const r = await api(`/api/jobs/${encodeURIComponent(jid)}`);
      if(r.wallet && r.wallet.tokens !== S.wallet.tokens){ S.wallet = r.wallet; renderTop(); }
      if(r.status === "done") return r;
      if(r.status === "review") return { ...r, job: jid };
      if(r.status === "cancelled") throw new Error("درخواست لغو شد؛ توکنی کسر نشد.");
      if(r.status === "error"){
        const err = new Error(r.error || "ساخت ناموفق بود");
        err.job = jid; err.canResume = !!r.can_resume; err.wizard = !!r.wizard;
        err.completedTasks = Number(r.completed_tasks || 0); err.totalTasks = Number(r.total_tasks || 0);
        err.buildPhase = r.build_phase || "";
        throw err;
      }
      if(i % 3 === 0 && r.prog?.p != null) this.out(`<div class="aip-prog">${IC.bot} ${esc(LQ_LBL[r.prog.st] || "در حال ساخت")} · ${N(Math.round(r.prog.p))}%</div>`);
    }
    throw new Error("ساخت بیش از حد طول کشید؛ checkpoint ذخیره شده است.");
  },

  /* ── ویزارد کاملاً دستی: بدون مدل، بدون توکن ── */
  async wizard(){
    this.close();
    let mods = S._mods;
    if(!mods){
      try{
        const d = await api("/api/modules");
        mods = S._mods = d.modules || [];
      }catch(e){ return toast("کاتالوگ بارگذاری نشد"); }
    }
    const cats = {};
    mods.forEach(m => (cats[m.cat] = cats[m.cat] || []).push(m));
    const rows = Object.entries(cats).map(([c, ms]) =>
      `<div class="sub">${esc(c)}</div>` + ms.map(m =>
        `<label class="aip-mod"><input type="checkbox" value="${esc(m.id)}" data-req="${esc((m.requires || []).join(","))}">
         <span><b>${esc(m.fa)}</b><small>${esc(m.desc || "")}</small></span></label>`).join("")).join("");
    S.sheet = { kind: "info" };
    showSheet(head("ویزارد بدون هوش مصنوعی") +
      `<p class="muted">قابلیت‌ها را انتخاب کن؛ انتخاب‌ها مستقیماً به همان Spec استاندارد تبدیل و با کامپایلر قطعی (بدون مدل و بدون هزینه) ساخته می‌شوند.</p>
       <input id="wiz-name" class="fa" placeholder="نام ربات" maxlength="30" value="${esc(S.cur?.name || "ربات من")}">
       <div class="fgap"></div>${rows}<div class="fgap"></div>
       <div class="bar"><button class="b" data-a="wizgo2">${IC.layers}ساخت قطعی</button></div><div class="fgap"></div>`);
    Object.assign(A, {
      wizgo2: el => busy(el, async () => {
        const picked = [...document.querySelectorAll(".aip-mod input:checked")].map(x => x.value);
        if(!picked.length) return toast("حداقل یک قابلیت انتخاب کن");
        /* وابستگی‌ها (مثل کیف سکه) خودکار در اعتبارسنجی Spec اضافه می‌شوند */
        const feats = picked.map(id => ({ type: id, params: {} }));
        try{
          const d = await api("/api/wizard/compile", "POST", { name: $("#wiz-name")?.value || "ربات من", features: feats });
          closeSheet();
          if(d.bot){
            S.bots = [d.bot, ...S.bots]; S.cur = d.bot; S.sbot = d.bot.id;
            S._mods = d.catalog || S._mods;
            if(d.wallet) S.wallet = d.wallet;
            S.view = "studio"; render(); bumpTokens();
            toast("با ویزارد دستی ساخته شد — بدون هوش مصنوعی و بدون هزینه");
          }
        }catch(e){ toast(e.message || "ساخت ممکن نشد"); }
      }),
    });
  },

  /* ── سه قالب جامع (Spec-محور و قطعی) ── */
  templates(){
    this.close();
    const tpls = S.templates || [];
    if(!tpls.length) return toast("قالبی در دسترس نیست");
    S.sheet = { kind: "info" };
    showSheet(head("سه قالب جامع") +
      `<p class="muted">هر قالب با کامپایلر قطعی ساخته و بلافاصله در استودیو قابل ویرایش است.</p>` +
      tpls.map(t => `<div class="tplc"><div class="tplt"><span class="ib">${IC[t.icon] || IC.bot}</span>
        <div class="gt"><b>${esc(t.title)}</b><span>${esc(t.desc)}</span></div>
        <button class="b sm" data-a="tpl" data-id="${esc(t.id)}">${t.cost ? N(t.cost) + " توکن" : "ساخت"}</button></div>
        <div class="chips">${(t.feats || []).slice(0, 3).map(f => `<span class="chip">${esc(f)}</span>`).join("")}</div></div>`).join("") +
      `<div class="fgap"></div>`);
  },

  act(a, el){
    if(a === "close") this.close();
    else if(a === "preview") this.preview();
    else if(a === "build") this.build();
    else if(a === "wizard") this.wizard();
    else if(a === "tpls") this.templates();
  },
};

window.AIP = AIP;
