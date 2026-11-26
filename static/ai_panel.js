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
    this._liveStop();
  },

  html(){
    const cur = S.cur, nodes = cur ? Object.keys(cur.config.nodes).length : 0;
    return `
    <header class="aih">
      <span class="aih-ic">${IC.spark}</span>
      <b>دستیار ساخت</b>
      <button class="iconb" data-aip="close" aria-label="بستن">${IC.x}</button>
    </header>
    <div class="aib">
      <p class="muted">${cur ? `پروژهٔ باز: <b>${esc(cur.name)}</b> · ${N(nodes)} بخش — درخواستت روی همین پروژه اعمال می‌شود.` : "پروژه‌ای باز نیست."}</p>
      <textarea id="aip-prompt" maxlength="4000" placeholder="مثلاً: یک بازی حدس عدد با کیف سکه و رتبه‌بندی اضافه کن"></textarea>
      <div id="aip-out" class="aip-out"></div>
    </div>
    <footer class="aip-foot">
      <button class="b" data-aip="build">${IC.spark}${cur ? "ارتقای این ربات" : "ساخت ربات"}</button>
      <button class="b o" data-aip="preview">پیش‌نمایش</button>
      <button class="b o" data-aip="tpls">${IC.layers}سه قالب آماده</button>
      <button class="b o" data-aip="wizard">${IC.layers}ویزارد بدون هوش مصنوعی</button>
    </footer>`;
  },

  render(){
    if(!this.el) return;
    this.el.innerHTML = this.html();
    const ta = this.el.querySelector("#aip-prompt");
    if(ta){
      ta.value = this._prompt || "";
      ta.addEventListener("input", () => { this._prompt = ta.value; });
    }
    this.el.querySelectorAll("[data-aip]").forEach(b => b.addEventListener("click", () => this.act(b.dataset.aip, b)));
  },

  out(html){ const o = this.el?.querySelector("#aip-out"); if(o) o.innerHTML = html; },

  /* وضعیت شغلی: یا جعبهٔ ساخت زندهٔ کامل (الگوی lq صفحهٔ ساخت) یا بازگرداندن آخرین پیش‌نمایش */
  busy(on, label){
    const btn = this.el?.querySelector('[data-aip="build"]');
    if(btn) btn.disabled = !!on;
    if(on){
      this._lv = {t0: Date.now(), target: 0, shown: 0, st: "", real: false, done: false};
      this.out(this.liveHTML(label));
      this._liveTimers();
    }else{
      this._liveStop();
      this.out(this._lastOut || "");
    }
  },

  /* جعبهٔ پیشرفت ساخت — همان الگوی «lq» صفحهٔ ساخت: سرعت + درصد + زمان + نوار + مرحله‌ها */
  liveHTML(title){
    const t = esc(title || "در حال ساخت ربات");
    return `<div class="lq aip-live" role="status" aria-busy="true" aria-label="${t}">
      <div class="lqh">${RB}<div class="lqt"><b>${t}</b><span class="lqs aip-lqs">${THINK[0]}</span></div>
        <div class="lqp"><b class="aip-pc">0%</b><small class="aip-tm">0:00</small></div></div>
      <div class="lqbar ind"><i></i></div>
      <ol class="lqst">${LQ_STEPS.map(x => `<li><i></i>${x}</li>`).join("")}</ol>
      <div class="lqn aip-lqn" hidden></div></div>`;
  },

  _liveTimers(){
    this._liveStop(true);
    const root = this.el?.querySelector(".aip-live");
    if(!root || !this._lv) return;
    const sub = root.querySelector(".aip-lqs"), pc = root.querySelector(".aip-pc"),
          bar = root.querySelector(".lqbar"), tm = root.querySelector(".aip-tm");
    let pool = [], last = THINK[0];
    const next = () => { if(!pool.length){ pool = THINK.slice().sort(() => Math.random() - .5); if(pool[pool.length - 1] === last) pool.reverse(); } return last = pool.pop(); };
    this._lvT = setInterval(() => {
      if(!root.isConnected){ this._liveStop(); return; }
      if(!this._lv.real) sub.textContent = next();
    }, 2800);
    this._lvC = setInterval(() => {
      if(!root.isConnected){ this._liveStop(); return; }
      const el = Math.floor((Date.now() - this._lv.t0) / 1000);
      tm.textContent = FAD(Math.floor(el / 60) + ":" + String(el % 60).padStart(2, "0"));
      if(this._lv.real){
        const d = this._lv.target - this._lv.shown;
        this._lv.shown = reduced() ? this._lv.target : this._lv.shown + d * .12 + (Math.abs(d) < .4 && this._lv.shown < 96 ? .02 : 0);
        this._lv.shown = Math.min(this._lv.shown, this._lv.done ? 100 : 99);
        pc.textContent = FAD(Math.round(this._lv.shown)) + "%";
        bar.firstElementChild.style.width = this._lv.shown + "%";
      }
    }, 100);
  },

  _liveStop(soft){
    if(this._lvT){ clearInterval(this._lvT); this._lvT = null; }
    if(this._lvC){ clearInterval(this._lvC); this._lvC = null; }
    if(!soft) this._lv = null;
  },

  /* به‌روزرسانی زندهٔ پیشرفت از سرور — همان قرارداد liveUpdate صفحهٔ ساخت */
  liveUpd(pr){
    const root = this.el?.querySelector(".aip-live");
    if(!root || !pr || !this._lv) return;
    this._lv.real = true; this._lv.target = Math.max(this._lv.target, +pr.p || 0);
    root.querySelector(".lqbar").classList.remove("ind");
    if(pr.st && pr.st !== this._lv.st){
      this._lv.st = pr.st;
      root.querySelector(".aip-lqs").textContent = LQ_LBL[pr.st] || LQ_LBL.analyze;
      const idx = LQ_IDX[pr.st] ?? 0;
      root.querySelectorAll(".lqst li").forEach((li, i) => { li.classList.toggle("done", i < idx); li.classList.toggle("on", i === idx); });
    }
    const n = root.querySelector(".aip-lqn");
    if(pr.task_n){
      n.hidden = false;
      n.textContent = `وظیفه ${FAD(Math.max(0, Number(pr.task_i || 0)))} از ${FAD(pr.task_n)}${pr.task_title ? ` · ${pr.task_title}` : ""}`;
    }else if(pr.n > 0){ n.hidden = false; n.textContent = `${FAD(pr.n)} بخش ساخته شد` + (pr.ti ? ` · آخرین: ${pr.ti}` : ""); }
  },

  /* ── پیش‌نمایش Spec: شفاف و قبل از هر هزینه‌ای — همان الگوی باکس «پیش‌نمایش ساخت» صفحهٔ ساخت ── */
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
    const pv = d.preview || {};
    const instant = !!d.instant;
    const name = d.spec?.name || "";
    const subs = instant
      ? (name ? `«${esc(name)}» · ` : "") + `${N((pv.ok || []).length)} قابلیت شناسایی شد`
      : esc(d.message || "قابلیتی آماده‌ای پیدا نشد؛ هوش مصنوعی طراحی می‌کند");
    const feats = (pv.features && pv.features.length ? pv.features : (pv.ok || [])).slice(0, 18);
    const chips = feats.map((x, i) => `<span class="pvm" style="animation-delay:${i * 45}ms">${esc(x.fa || x.id)}</span>`).join("");
    /* محدودیت‌ها: ❌ محدودیت موتور + سایر محدودیت‌های شناخته‌شده، بدون تکرار بر اساس «want» */
    const seen = {}, lims = [];
    (pv.engine_limit || []).concat(d.limits || []).forEach(l => {
      const k = (l && l.want) || ""; if(!k || seen[k]) return; seen[k] = 1; lims.push(l);
    });
    const limHTML = lims.length
      ? `<div class="pvlim">${lims.map(x => `<div><b>${esc(x.want || "")}</b><span>${esc(x.why || "")}</span>${x.upgrade ? `<span>راهکار: ${esc(x.upgrade)}</span>` : ""}</div>`).join("")}</div>`
      : "";
    return `<div class="lqi aip-pv">
      <div class="lqih">${RB}<div class="lqt"><b>پیش‌نمایش ساخت</b><span class="aip-pvs">${subs}</span></div>
        <span class="pvbadge ${instant ? "ok" : "ai"}">${instant ? "ساخت آنی" : "ساخت با هوش مصنوعی"}</span></div>
      ${chips ? `<div class="pvmods">${chips}</div>` : ""}
      ${limHTML}
      <ol class="lqst">${LQ_STEPS.map(t => `<li><i></i>${t}</li>`).join("")}</ol>
    </div>
    <p class="aip-note">لغو رایگان است؛ ساخت فقط پس از تأیید این پیش‌نمایش و با تست پذیرش موتور تحویل می‌شود.</p>`;
  },

  /* ── ساخت/ارتقا با خط Spec (کمترین مصرف مدل) ──
     هر نتیجه (موفقیت/شکست/بازبینی/خرید) در شیت مرکزی نشان داده می‌شود؛ پنل قبل از آن
     به‌صورت کنترل‌شده بسته می‌شود تا گزارش هرگز زیر پنل نماند. درخواست و وضعیت پروژه حفظ می‌شود. */
  async build(){
    const ta = this.el?.querySelector("#aip-prompt");
    const p = (ta?.value || "").trim();
    if(p.length < 5) return toast("توضیح بیشتری بنویس");
    const botId = S.cur?.id || null;
    const cost = needCost(!!botId);
    if(S.wallet.tokens < cost) { this.close(); return openBuy(`این کار حداقل ${cost} توکن می‌خواهد.`); }
    this.busy(true, botId ? "در حال ارتقا…" : "در حال ساخت…");
    try{
      const r0 = await api("/api/generate", "POST", { prompt: p, bot_id: botId });
      if(r0.wallet) { S.wallet = r0.wallet; renderTop(); }
      const r = await this.poll(r0.job);
      this._liveStop();
      if(r.status === "review"){
        this.close();
        showBuildReview(r);
        return;
      }
      /* موفقیت: ربات به‌روز شد؛ پنل بسته می‌شود تا استودیوی به‌روزشده دیده شود؛ درخواست برای ادامهٔ کار می‌ماند */
      if(r.bot){
        S.wallet = r.wallet || S.wallet;
        S.bots = [r.bot, ...S.bots.filter(b => b.id !== r.bot.id)];
        S.cur = r.bot; S.sbot = r.bot.id;
        if(S.view !== "studio"){ S.view = "studio"; }
        render(); bumpTokens();
        this._lastOut = "";
        this.close();
        toast((botId ? "ربات ارتقا یافت" : "ربات ساخته شد") + (r.cost ? `، ${N(r.cost)} توکن` : "") + " — تست پذیرش موتور پاس شد");
        haptic("ok");
      }
    }catch(e){
      this._liveStop();
      if(e.status === 402){ this.close(); return openBuy(e.message); }
      this.close();
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
      if(r.prog) this.liveUpd(r.prog);
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
