/* ═══════════════════════════════════════════════════════════════
   studio.js — ویرایشگر ربات: استودیوی گرافیکی (بخش‌ها و سیم‌ها) + شیت‌های ویرایش (بخش، دکمه،
   منطق، تنظیمات ربات، مدیریت گروه و کانال، رسانه و پیام همگانی) + شیت‌های یوزربات.
   بعد از app.js بارگذاری می‌شود و به وضعیت و ابزارهای آن (S، $، api، IC، …) تکیه دارد.
   ═══════════════════════════════════════════════════════════════ */
/* ═════════════════ استودیو گرافیکی: بخش + سیم + انرژی ═════════════════ */
const ST = { botId: null, cam: null, pos: {}, ptr: new Map(), mode: null, wires: new Map(), drop: null, dropAt: null, _la: null, size: {}, po: {}, pi: {} };
const ST_W = 268, ST_GAP = 124;
let OP_FA = null;                       // بعد از تعریف OPS پر می‌شود
const condTxt = w => {
  if(!w) return "…";
  if(!OP_FA) OP_FA = Object.fromEntries(OPS);
  return simpleCond(w) ? `${w.var} ${OP_FA[w.op] || w.op}${w.op === "empty" || w.op === "filled" ? "" : " " + (w.value ?? "")}` : "شرط ترکیبی";
};

function stKey(){ return "azadi.studio." + (S.cur?.id || ""); }
function stLoad(){
  ST.pos = {}; ST.cam = null;
  try{
    const d = JSON.parse(localStorage.getItem(stKey()) || "null");
    if(d && d.p) for(const [k, v] of Object.entries(d.p)) if(Array.isArray(v)) ST.pos[k] = {x: +v[0] || 0, y: +v[1] || 0};
    if(d && Array.isArray(d.cam)) ST.cam = {x: +d.cam[0] || 0, y: +d.cam[1] || 0, z: Math.min(1.5, Math.max(.16, +d.cam[2] || 1))};
  }catch(_){}
}
function stSaveNow(){
  if(!S.cur) return;
  const p = {};
  for(const id of Object.keys(S.cur.config.nodes)) if(ST.pos[id]) p[id] = [Math.round(ST.pos[id].x), Math.round(ST.pos[id].y)];
  const c = ST.cam || {x: 0, y: 0, z: 1};
  try{ localStorage.setItem(stKey(), JSON.stringify({p, cam: [Math.round(c.x), Math.round(c.y), +c.z.toFixed(3)]})); }catch(_){}
}
let stSaveT = null;
function stSave(){ clearTimeout(stSaveT); stSaveT = setTimeout(stSaveNow, 400); }
addEventListener("pagehide", () => { if(S.view === "studio") stSaveNow(); });

function stNextId(){
  const cfg = S.cur.config;
  let k = Object.keys(cfg.nodes).length + 1;
  while(cfg.nodes["page_" + k]) k++;
  return "page_" + k;
}
const stNodeIcon = n => n.ai ? IC.spark : n.fields ? IC.form : n.ask ? IC.inbox : n.board ? IC.medal : IC.bot;

/* همه‌ی سیم‌های ربات: هر goto یک سیم است */
function stEdges(){
  const cfg = S.cur.config, out = [];
  for(const [id, n] of Object.entries(cfg.nodes)){
    (n.buttons || []).forEach((row, r) => row.forEach((b, c) => {
      if(b.goto !== undefined) out.push({key: `b|${id}|${r}|${c}`, from: id, to: b.goto, kind: "btn", n: id, r, c});
      else if(b.pay?.goto) out.push({key: `b|${id}|${r}|${c}`, from: id, to: b.pay.goto, kind: "pay", n: id, r, c});
    }));
    (n.route || []).forEach((ru, i) => out.push({key: `r|${id}|${i}`, from: id, to: ru.goto, kind: "route", n: id, ri: i}));
    if(n.next) out.push({key: `x|${id}`, from: id, to: n.next, kind: "next", n: id});
  }
  return out;
}
function stParsePort(p){
  const t = p.split("|");
  return t[0] === "b" ? {t: "btn", n: t[1], r: +t[2], c: +t[3]} : t[0] === "r" ? {t: "route", n: t[1], ri: +t[2]} : {t: "next", n: t[1]};
}
/* اعمال یک اتصال روی کانفیگ */
function stWireIn(cfg, src, tid){
  const n = cfg.nodes[src.n];
  if(!n || !cfg.nodes[tid]) return;
  if(src.t === "btn"){ const b = n.buttons[src.r]?.[src.c]; if(!b) return; if(b.pay) b.pay.goto = tid; else b.goto = tid; }
  else if(src.t === "route"){ const ru = n.route?.[src.ri]; if(ru) ru.goto = tid; }
  else if(src.t === "next"){ n.next = tid; }
  else if(src.t === "new"){
    n.buttons = (n.buttons || []).filter(r => r.length);
    const row = n.buttons.find(r => r.length < 3);
    if(row) row.push({text: "دکمه‌ی جدید", goto: tid});
    else if(n.buttons.length < 6) n.buttons.push([{text: "دکمه‌ی جدید", goto: tid}]);
  }
}
/* بخش‌های قابل دسترس از شروع/ناشناس/دستورها */
function stReach(){
  const cfg = S.cur.config, seen = new Set(), st = [cfg.start, cfg.fallback, ...Object.values(cfg.commands || {})];
  while(st.length){
    const i = st.pop();
    if(seen.has(i) || !cfg.nodes[i]) continue;
    seen.add(i);
    const n = cfg.nodes[i];
    for(const row of n.buttons || []) for(const b of row){ if(b.goto) st.push(b.goto); if(b.pay?.goto) st.push(b.pay.goto); }
    for(const ru of n.route || []) st.push(ru.goto);
    if(n.next) st.push(n.next);
  }
  return seen;
}
/* چیدمان لایه‌ای از راست (شروع) به چپ */
/* چیدمان لایه‌ای از راست (شروع) به چپ؛ هر بخش نزدیکِ میانگینِ بخش‌هایی قرار می‌گیرد که به آن می‌رسند تا سیم‌ها کوتاه و کم‌تقاطع باشند */
const stH = id => (ST.size[id] ? ST.size[id].h : stCardH(S.cur.config.nodes[id]));
function stAutoLayout(save){
  const cfg = S.cur.config, ids = Object.keys(cfg.nodes), col = {}, q = [];
  const roots = [cfg.start, cfg.fallback, ...Object.values(cfg.commands || {})].filter((r, i, a) => cfg.nodes[r] && a.indexOf(r) === i);
  const edges = stEdges(), out = {};
  for(const e of edges) (out[e.from] = out[e.from] || []).push(e.to);
  for(const r of roots){ col[r] = 0; q.push(r); }
  while(q.length){
    const id = q.shift();
    for(const t of out[id] || []) if(cfg.nodes[t] && col[t] === undefined){ col[t] = col[id] + 1; q.push(t); }
  }
  for(const id of ids) if(col[id] === undefined) col[id] = -1;      // بخش‌های بی‌اتصال کنار شروع می‌روند، نه ته نقشه
  const parents = {};
  for(const e of edges) if(cfg.nodes[e.to] && col[e.from] < col[e.to]) (parents[e.to] = parents[e.to] || []).push(e.from);
  const cols = {};
  for(const id of [...new Set([...roots, ...ids])]) (cols[col[id]] = cols[col[id]] || []).push(id);
  const cy = {}, DW = ST_W + ST_GAP, GAP = 52;
  for(const c of Object.keys(cols).map(Number).sort((a, b) => a - b)){
    const list = cols[c].map((id, i) => {
      const ps = (parents[id] || []).filter(p => cy[p] !== undefined);
      return {id, i, b: ps.length ? ps.reduce((a, p) => a + cy[p], 0) / ps.length : null};
    });
    list.sort((a, b) => ((a.b === null) - (b.b === null)) || ((a.b ?? 0) - (b.b ?? 0)) || (a.i - b.i));
    let cur = 40;
    for(const it of list){
      const h = stH(it.id), y = it.b === null ? cur : Math.max(cur, it.b - h / 2);
      ST.pos[it.id] = {x: -c * DW, y: Math.round(y)};
      cy[it.id] = y + h / 2; cur = y + h + GAP;
    }
  }
  let minY = 1e9;
  for(const id of ids) minY = Math.min(minY, ST.pos[id].y);
  for(const id of ids) ST.pos[id].y += 40 - minY;
  if(save) stSave();
}
/* جای بخش‌های بدون مختصات ذخیره‌شده */
/* جای بخش‌های بدون مختصات ذخیره‌شده؛ اگر همه تازه بودند true برمی‌گرداند */
function stEnsurePositions(){
  const ids = Object.keys(S.cur.config.nodes);
  const missing = ids.filter(id => !ST.pos[id]);
  if(!missing.length) return false;
  const keep = {...ST.pos};
  stAutoLayout(false);
  for(const id of ids) if(keep[id]) ST.pos[id] = keep[id];
  for(const id of missing){
    let p = {...(ST.pos[id] || {x: 0, y: 0})}, guard = 0, hit;
    const find = () => ids.find(o => o !== id && ST.pos[o] && o !== id && Math.abs(ST.pos[o].x - p.x) < ST_W + 24 && p.y < ST.pos[o].y + stH(o) + 24 && ST.pos[o].y < p.y + stH(id) + 24);
    while((hit = find()) && guard++ < 40) p = {x: p.x, y: ST.pos[hit].y + stH(hit) + 40};
    ST.pos[id] = p;
  }
  stSave();
  return missing.length === ids.length;
}

/* ── دوربین ── */
function stApply(glide){
  const c = ST.cam || {x: 40, y: 40, z: 1}, w = $("#stw");
  if(w){
    if(glide && !reduced()){ w.classList.add("glide"); clearTimeout(ST._gt); ST._gt = setTimeout(() => w.classList.remove("glide"), 460); }
    else if(w.classList.contains("glide")){ w.classList.remove("glide"); clearTimeout(ST._gt); }
    w.style.transform = `translate(${c.x}px,${c.y}px) scale(${c.z})`;
    const far = c.z < .5; if(far !== w.classList.contains("far")) w.classList.toggle("far", far);
  }
  const z = $("#stz"); if(z) z.textContent = Math.round(c.z * 100) + "%";
  if(!ST._mr) ST._mr = requestAnimationFrame(() => { ST._mr = 0; stMini(); });
}
function stZoomAt(px, py, f, glide){
  const c = ST.cam || {x: 40, y: 40, z: 1};
  const z = Math.min(1.5, Math.max(.16, c.z * f));
  ST.cam = {z, x: px - (px - c.x) * z / c.z, y: py - (py - c.y) * z / c.z};
  stApply(glide); stSave();
}
function stFit(glide){
  const cv = $("#stc"), ids = Object.keys(S.cur?.config.nodes || {});
  if(!cv || !ids.length) return;
  let x1 = 1e9, y1 = 1e9, x2 = -1e9, y2 = -1e9;
  for(const id of ids){
    const p = ST.pos[id]; if(!p) continue;
    const el = cv.querySelector(`.stc-card[data-id="${id}"]`);
    const w = el ? el.offsetWidth : 268, h = el ? el.offsetHeight : stCardH(S.cur.config.nodes[id]);
    x1 = Math.min(x1, p.x); y1 = Math.min(y1, p.y); x2 = Math.max(x2, p.x + w); y2 = Math.max(y2, p.y + h);
  }
  if(x1 > x2) return;
  const cw = cv.clientWidth, ch = cv.clientHeight, bw = x2 - x1, bh = y2 - y1;
  const z = Math.min(1.25, Math.max(.16, Math.min((cw - 70) / Math.max(1, bw), (ch - 150) / Math.max(1, bh))));
  ST.cam = {z, x: (cw - bw * z) / 2 - x1 * z, y: (ch - bh * z) / 2 - y1 * z + 8};
  stApply(glide); stSave();
}
function stCenter(id){
  const cv = $("#stc"), el = cv?.querySelector(`.stc-card[data-id="${id}"]`);
  if(!cv || !el || !ST.pos[id]) return;
  const c = ST.cam || {x: 40, y: 40, z: 1};
  ST.cam = {...c, x: cv.clientWidth / 2 - (ST.pos[id].x + el.offsetWidth / 2) * c.z, y: cv.clientHeight / 2 - (ST.pos[id].y + el.offsetHeight / 2) * c.z};
  stApply(true); stSave();
  el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash");
}

/* ── هندسه‌ی سیم ── */
/* مختصات مرکز یک عنصر داخل بخش، در دنیای بوم */
function stWorldOf(el){
  const card = el.closest(".stc-card"), p = (card && ST.pos[card.dataset.id]) || {x: 0, y: 0};
  let x = card ? card.clientLeft : 0, y = card ? card.clientTop : 0, n = el;
  while(n && n !== card){ x += n.offsetLeft; y += n.offsetTop; n = n.offsetParent; }
  return {x: p.x + x + el.offsetWidth / 2, y: p.y + y + el.offsetHeight / 2};
}
/* سیم‌کشی هوشمند: سیم از لبه‌ی چپ بخش مبدأ خارج و از لبه‌ی راست بخش مقصد وارد می‌شود، با زاویه‌ی قائم و بدون عبور از روی بخش‌ها */
const stRects = () => { const r = []; for(const id of Object.keys(S.cur.config.nodes)){ const p = ST.pos[id], z = ST.size[id]; if(p && z) r.push({id, x: p.x, y: p.y, w: z.w, h: z.h}); } return r; };
const stHit = (r, x1, y1, x2, y2, m = 10) => Math.min(x1, x2) < r.x + r.w + m && Math.max(x1, x2) > r.x - m && Math.min(y1, y2) < r.y + r.h + m && Math.max(y1, y2) > r.y - m;
const stPortPos = key => { const o = ST.po[key], p = o && ST.pos[o.id]; return o && p ? {x: p.x + o.x, y: p.y + o.y} : null; };
const stInPos = id => { const o = ST.pi[id], p = ST.pos[id]; return o && p ? {x: p.x + o.x, y: p.y + o.y} : null; };
function stRoute(e, idx, rects){
  const A = stPortPos(e.key), B = stInPos(e.to);
  if(!A || !B) return null;
  const lane = (idx % 5) * 7, free = (list, x1, y1, x2, y2) => !list.some(r => stHit(r, x1, y1, x2, y2));
  const mid = rects.filter(r => r.id !== e.from && r.id !== e.to), noSrc = rects.filter(r => r.id !== e.from), noTgt = rects.filter(r => r.id !== e.to);
  if(A.x - B.x > 70){
    const lo = B.x + 20, hi = A.x - 20, base = (lo + hi) / 2 + lane - 14;
    for(const d of [0, 14, -14, 28, -28, 42, -42, 56, -56, 70, -70]){
      const xm = Math.min(hi, Math.max(lo, base + d));
      if(free(mid, xm, A.y, xm, B.y) && free(noSrc, A.x, A.y, xm, A.y) && free(noTgt, xm, B.y, B.x, B.y))
        return {pts: [A, {x: xm, y: A.y}, {x: xm, y: B.y}, B], back: false};
    }
  }
  const ax = A.x - 22 - lane, bx = B.x + 22 + lane, lx = Math.min(ax, bx), hx = Math.max(ax, bx);
  const ys = new Set(), sR = rects.find(r => r.id === e.from), tR = rects.find(r => r.id === e.to);
  if(sR && tR){ ys.add(Math.min(sR.y, tR.y) - 26 - lane); ys.add(Math.max(sR.y + sR.h, tR.y + tR.h) + 26 + lane); }
  for(const r of rects){ ys.add(r.y - 24 - lane); ys.add(r.y + r.h + 24 + lane); }
  const cand = [...ys].map(y => ({y, c: Math.abs(y - A.y) + Math.abs(y - B.y)})).sort((a, b) => a.c - b.c);
  for(const {y} of cand){
    if(free(rects, lx, y, hx, y) && free(rects, ax, A.y, ax, y) && free(rects, bx, y, bx, B.y))
      return {pts: [A, {x: ax, y: A.y}, {x: ax, y}, {x: bx, y}, {x: bx, y: B.y}, B], back: true};
  }
  return null;
}
function stPoly(pts){
  const p = [pts[0]];
  for(let i = 1; i < pts.length; i++){ const q = pts[i], l = p[p.length - 1]; if(Math.abs(q.x - l.x) > .5 || Math.abs(q.y - l.y) > .5) p.push(q); }
  if(p.length < 2) return "";
  const f = v => v.toFixed(1);
  let d = `M${f(p[0].x)} ${f(p[0].y)}`;
  for(let i = 1; i < p.length - 1; i++){
    const a = p[i - 1], c = p[i], b = p[i + 1];
    const l1 = Math.hypot(c.x - a.x, c.y - a.y), l2 = Math.hypot(b.x - c.x, b.y - c.y), r = Math.min(10, l1 / 2, l2 / 2);
    d += `L${f(c.x + (a.x - c.x) / l1 * r)} ${f(c.y + (a.y - c.y) / l1 * r)}Q${f(c.x)} ${f(c.y)} ${f(c.x + (b.x - c.x) / l2 * r)} ${f(c.y + (b.y - c.y) / l2 * r)}`;
  }
  const e = p[p.length - 1];
  return d + `L${f(e.x)} ${f(e.y)}`;
}
function stEdgeGeom(e, idx, rects){
  const r = stRoute(e, idx, rects);
  if(r) return {d: stPoly(r.pts), back: r.back};
  const A = stPortPos(e.key), B = stInPos(e.to);
  return A && B ? {d: stPath(A, B), back: B.x > A.x - 30} : null;
}
/* اندازه‌ی واقعی بخش‌ها و جای دقیق دایره‌های ورودی/خروجی را یک بار اندازه می‌گیرد */
function stMeasure(){
  const cv = $("#stc"); if(!cv) return;
  ST.size = {}; ST.po = {}; ST.pi = {};
  cv.querySelectorAll(".stc-card").forEach(card => {
    const id = card.dataset.id;
    ST.size[id] = {w: card.offsetWidth, h: card.offsetHeight};
    const rel = el => { let x = card.clientLeft, y = card.clientTop, n = el; while(n && n !== card){ x += n.offsetLeft; y += n.offsetTop; n = n.offsetParent; } return {x: x + el.offsetWidth / 2, y: y + el.offsetHeight / 2}; };
    card.querySelectorAll(".p-out").forEach(po => { if(po.dataset.port !== "+") ST.po[po.dataset.port] = {id, ...rel(po)}; });
    const inn = card.querySelector(".stc-in"); if(inn) ST.pi[id] = rel(inn);
  });
}
/* دایره‌های خروجی روی لبه‌ی چپ بخش، هم‌تراز با دکمه‌شان؛ اگر چند دکمه در یک ردیف باشند کمی بالا و پایین می‌روند */
function stPlacePorts(card){
  card.querySelectorAll(".p-out").forEach(po => po.remove());
  const groups = new Map();
  card.querySelectorAll(".pa").forEach(a => {
    let y = 0, n = a;
    while(n && n !== card){ y += n.offsetTop; n = n.offsetParent; }
    const g = a.closest(".stk-row") || a;
    if(!groups.has(g)) groups.set(g, []);
    groups.get(g).push({a, cy: y + a.offsetHeight / 2});
  });
  let h = "";
  for(const list of groups.values()) list.forEach((it, i) => {
    const d = it.a.dataset, off = (i - (list.length - 1) / 2) * 13;
    h += `<span class="p-out" data-port="${esc(d.pa)}" data-n="${esc(d.n)}"${d.r !== undefined ? ` data-r="${d.r}" data-c="${d.c}"` : ""} style="top:${(it.cy + off).toFixed(1)}px;--pc:${d.pc}"></span>`;
  });
  card.insertAdjacentHTML("beforeend", h);
}
function stPlaceCards(){
  const cv = $("#stc"); if(!cv) return;
  cv.querySelectorAll(".stc-card").forEach(el => { const p = ST.pos[el.dataset.id]; if(p) el.style.transform = `translate(${p.x}px,${p.y}px)`; });
}
function stPath(a, b){
  const d = Math.max(46, Math.min(170, Math.abs(a.x - b.x) * .55));
  return `M ${a.x.toFixed(1)} ${a.y.toFixed(1)} C ${(a.x - d).toFixed(1)} ${a.y.toFixed(1)}, ${(b.x + d).toFixed(1)} ${b.y.toFixed(1)}, ${b.x.toFixed(1)} ${b.y.toFixed(1)}`;
}

/* ── رندر بخش‌ها و سیم‌ها ── */
const ST_KIND = {goto: ["رفتن به بخش", IC.go], pay: ["پرداخت", IC.coin], url: ["باز کردن لینک", IC.open], channel: ["کانال یا گروه", IC.open], alert: ["پیام پاپ‌آپ", IC.mega], copy: ["کپی متن", IC.copy], share: ["لینک دعوت", IC.users]};
const BTN_COLORS = {blue: "🔵", green: "🟢", red: "🔴", yellow: "🟡", purple: "🟣", orange: "🟠", black: "⚫"};
const BTN_COLOR_FA = {blue: "آبی", green: "سبز", red: "قرمز", yellow: "زرد", purple: "بنفش", orange: "نارنجی", black: "مشکی"};
const stripEmojiTags = t => String(t ?? "").replace(/<tg-emoji\s+emoji-id="\d+"\s*>(.*?)<\/tg-emoji\s*>/gi, "$1");
const ST_MEDIA = {photo: "عکس", animation: "گیف", video: "ویدیو", audio: "موسیقی", voice: "ویس", document: "فایل"};

/* پیش‌نمایش رسانه‌ی بخش: عکس و گیف خودشان، بقیه آیکن + نام فایل */
function stMediaHTML(n){
  const m = n.media ? mediaById(n.media) : null;
  if(m && (m.kind === "photo" || m.kind === "animation") && m.url)
    return `<div class="stc-media"><img src="${API_BASE + esc(m.url)}" alt="" draggable="false" loading="lazy" decoding="async"><span class="mk">${ST_MEDIA[m.kind]}</span></div>`;
  if(m) return `<div class="stc-media ico">${IC[m.kind] || IC.document}<b>${esc(m.name || "")}</b><span class="mk">${ST_MEDIA[m.kind] || "فایل"}</span></div>`;
  if(n.media) return `<div class="stc-media ico bad">${IC.document}<b>رسانه از کتابخانه حذف شده</b></div>`;
  if(n.photo && /^https?:\/\//i.test(n.photo)) return `<div class="stc-media"><img src="${esc(n.photo)}" alt="" draggable="false" loading="lazy" decoding="async" referrerpolicy="no-referrer"><span class="mk">عکس لینکی</span></div>`;
  return "";
}
/* یک دکمه‌ی شیشه‌ای (یا کلیدِ کیبورد پایین چت) با دایره‌ی خروجیِ سیم */
function stBtnCell(id, r, c, b, cfg){
  const k = kindOf(b), [lab, ic] = ST_KIND[k] || ST_KIND.url;
  const tgt = k === "pay" ? b.pay?.goto : b.goto, wired = k === "goto" || (k === "pay" && !!b.pay?.goto);
  const broken = wired && !cfg.nodes[tgt];
  const tip = k === "goto" ? "رفتن به: " + titleOf(cfg, tgt) : k === "pay" ? `پرداخت ${b.pay.stars} ستاره` : lab;
  const anchor = wired ? `<span class="pa" data-pa="b|${id}|${r}|${c}" data-n="${esc(id)}" data-r="${r}" data-c="${c}" data-pc="${k === "pay" ? "var(--tok)" : "var(--ac)"}"></span>` : "";
  return `<div class="stk-cell"><button class="stk-btn k-${k}${broken ? " bad" : ""}${b.when ? " cond" : ""}" data-a="strow" data-n="${esc(id)}" data-r="${r}" data-c="${c}" title="${esc(tip)}"><span class="ki">${ic}</span><span class="kt">${b.color && BTN_COLORS[b.color] ? BTN_COLORS[b.color] + " " : ""}${esc(b.text)}</span></button>${anchor}</div>`;
}
function stCardH(n){
  const gr = [false, true].map(x => (n.buttons || []).filter(row => row.some(b => (b.kb === "reply") === x)).length), rows = gr[0] + gr[1], caps = (gr[0] ? 1 : 0) + (gr[1] ? 1 : 0), lg = (n.route?.length || 0) + (n.next ? 1 : 0);
  const lines = Math.min(5, Math.ceil(((n.text || "").length || 1) / 34));
  return 196 + ((n.media || n.photo) ? 118 : 0) + lines * 21 + (rows ? 24 * caps + rows * 39 : 0) + (lg ? 22 + lg * 30 : 0);
}
function stCardHTML(id, dead){
  const cfg = S.cur.config, n = cfg.nodes[id], p = ST.pos[id] || {x: 0, y: 0};
  const isStart = id === cfg.start, isFb = id === cfg.fallback && id !== cfg.start;
  const inc = (ST.inc || {})[id] || 0, btns = n.buttons || [];
  const tags = [];
  if(isStart) tags.push('<span class="tag st">شروع ربات</span>');
  if(isFb) tags.push('<span class="tag">پاسخ پیش‌فرض</span>');
  if(n.ai) tags.push('<span class="tag ai">هوش مصنوعی</span>');
  if(n.fields) tags.push('<span class="tag">فرم</span>'); else if(n.ask) tags.push('<span class="tag">دریافت پیام</span>');
  if(n.ticket) tags.push('<span class="tag">تیکت</span>');
  if(n.do?.length || n.route?.length || n.alt?.length) tags.push('<span class="tag">شرط و متغیر</span>');
  if(inc) tags.push(`<span class="tag cnt">${fa(inc)} ورودی</span>`);
  if(dead) tags.push('<span class="tag warn" title="هیچ دکمه یا مسیری به این بخش نمی‌رسد">بدون ورودی</span>');
  if(!btns.length && !n.ask && !n.fields && !n.ai && !n.next && !n.route?.length) tags.push('<span class="tag warn" title="بعد از این بخش، کاربر راهی برای ادامه ندارد">بدون ادامه</span>');
  const txt = (n.text || "").trim();
  const bub = `<div class="stc-bub">${stMediaHTML(n)}<div class="tx${txt ? "" : " empty"}">${txt ? esc(stripEmojiTags(txt).slice(0, 170)) + (txt.length > 170 ? "…" : "") : "هنوز متنی نوشته نشده"}</div></div>`;
  const grp = isRk => {
    const keys = btns.map((row, r) => { const cells = row.map((b, c) => (b.kb === "reply") === isRk ? stBtnCell(id, r, c, b, cfg) : "").join(""); return cells ? `<div class="stk-row">${cells}</div>` : ""; }).join("");
    return keys ? `<div class="stk${isRk ? " rk" : ""}"><div class="stk-cap">${isRk ? "کیبورد پایین چت" : "دکمه‌های شیشه‌ای زیر پیام"}</div>${keys}</div>` : "";
  };
  const kb = grp(false) + grp(true);
  let logic = "";
  (n.route || []).forEach((ru, i) => { logic += `<div class="stc-row"><span class="pa" data-pa="r|${id}|${i}" data-n="${esc(id)}" data-pc="var(--vio)"></span><span class="ric">${IC.go}</span><span class="rlb">${esc(condTxt(ru.when))} <small>· مسیر شرطی</small></span></div>`; });
  if(n.next) logic += `<div class="stc-row"><span class="pa" data-pa="x|${id}" data-n="${esc(id)}" data-pc="var(--ok)"></span><span class="ric">${IC.go}</span><span class="rlb">بعد از ثبت پاسخ <small>· رفتن به بخش بعدی</small></span></div>`;
  return `<div class="stc-card${isStart ? " start" : ""}${dead ? " dead" : ""}" data-id="${esc(id)}" style="transform:translate(${p.x}px,${p.y}px)">
    <span class="stc-in${inc ? " has" : ""}" data-in="${esc(id)}"></span>
    <div class="stc-h"><span class="stc-ic">${stNodeIcon(n)}</span>
      <div class="stc-t"><b>${esc(titleOf(cfg, id))}</b><span class="ids">${esc(id)}</span></div>
      <button class="stc-menu" data-a="stmenu" data-n="${esc(id)}" aria-label="گزینه‌های بخش">⋮</button></div>
    ${tags.length ? `<div class="stc-badges">${tags.join("")}</div>` : ""}
    ${bub}${kb}
    ${logic ? `<div class="stc-sec">مسیرهای شرطی و خودکار</div>${logic}` : ""}
    <div class="stc-row plus"><span class="pa" data-pa="+" data-n="${esc(id)}" data-pc="var(--ac)"></span><span class="ric">${IC.plus}</span><span class="rlb">سیم بکش تا دکمه‌ی جدید بسازی</span></div>
    <div class="stc-act"><button data-a="stbtn" data-n="${esc(id)}">${IC.plus}دکمه‌ی جدید</button><button data-a="stkm" data-n="${esc(id)}">${IC.layers}مدیریت دکمه‌ها</button></div>
  </div>`;
}
function stPaintWires(){
  const svg = $("#stsvg"), cv = $("#stc");
  if(!svg || !cv) return;
  ST.wires.clear();
  let h = "", i = 0;
  const edges = stEdges(), flow = !!S.cur?.active && !reduced() && edges.length <= 10, rects = stRects();
  for(const e of edges){
    const g = stEdgeGeom(e, i, rects);
    if(!g) continue;
    const dot = flow ? `<circle class="w-dot" r="3.2"><animateMotion dur="${(2 + (i % 5) * .4).toFixed(1)}s" begin="-${(i * .43).toFixed(2)}s" repeatCount="indefinite" path="${g.d}"/></circle>` : "";
    h += `<g class="wire k-${e.kind}${g.back ? " back" : ""}" data-w="${e.key}"><path class="w-glow" d="${g.d}"/><path class="w-line" d="${g.d}"/><path class="w-hit" d="${g.d}"/>${dot}</g>`;
    e.i = i; ST.wires.set(e.key, e); i++;
  }
  svg.innerHTML = h + `<path class="w-tmp" id="sttmp" d=""/>`;
}
function stUpdateWiresFor(id){
  const svg = $("#stsvg");
  if(!svg) return;
  const rects = stRects();
  for(const [key, e] of ST.wires){
    if(e.from !== id && e.to !== id) continue;
    const g = svg.querySelector(`.wire[data-w="${key}"]`), geo = g && stEdgeGeom(e, e.i || 0, rects);
    if(!g || !geo) continue;
    g.querySelectorAll("path").forEach(pp => pp.setAttribute("d", geo.d));
    g.classList.toggle("back", geo.back);
    g.querySelector("animateMotion")?.setAttribute("path", geo.d);
  }
}
function stHot(id, on){
  const sv = $("#stsvg"); if(!sv) return;
  for(const [k, e] of ST.wires) if(e.from === id || e.to === id) sv.querySelector(`.wire[data-w="${k}"]`)?.classList.toggle("hot", on);
}
/* نقشه‌ی کوچک: چیدمان کل گراف + کادر دید فعلی؛ لمس/کشیدن روی آن دوربین را جابه‌جا می‌کند */
function stMini(full){
  const mm = $("#stmm"), cv = $("#stc"); if(!mm || !cv || !S.cur) return;
  if(full || !ST.mini){
    const cfg = S.cur.config, r = []; let x1 = 1e9, y1 = 1e9, x2 = -1e9, y2 = -1e9;
    for(const id of Object.keys(cfg.nodes)){
      const p = ST.pos[id]; if(!p) continue;
      const h = stH(id); r.push([id, p.x, p.y, h]);
      x1 = Math.min(x1, p.x); y1 = Math.min(y1, p.y); x2 = Math.max(x2, p.x + ST_W); y2 = Math.max(y2, p.y + h);
    }
    if(!r.length) return;
    x1 -= 140; y1 -= 140; x2 += 140; y2 += 140;
    const W = 96, H = 72, sc = Math.min(W / (x2 - x1), H / (y2 - y1));
    const m = ST.mini = {x1, y1, s: sc, ox: (W - (x2 - x1) * sc) / 2, oy: (H - (y2 - y1) * sc) / 2};
    mm.innerHTML = r.map(([id, x, y, h]) => `<i${id === cfg.start ? ' class="s"' : ""} style="left:${(m.ox + (x - x1) * sc).toFixed(1)}px;top:${(m.oy + (y - y1) * sc).toFixed(1)}px;width:${(ST_W * sc).toFixed(1)}px;height:${(h * sc).toFixed(1)}px"></i>`).join("") + '<b id="stmv"></b>';
  }
  const m = ST.mini, v = $("#stmv"); if(!m || !v) return;
  const c = ST.cam || {x: 40, y: 40, z: 1};
  v.style.left = (m.ox + (-c.x / c.z - m.x1) * m.s) + "px"; v.style.top = (m.oy + (-c.y / c.z - m.y1) * m.s) + "px";
  v.style.width = (cv.clientWidth / c.z * m.s) + "px"; v.style.height = (cv.clientHeight / c.z * m.s) + "px";
}
/* دید اولیه: اگر نمایش کل گراف خیلی ریز شود، روی بخش شروع با زوم خوانا باز می‌شود */
function stHome(){
  const cv = $("#stc"), cfg = S.cur?.config; if(!cv || !cfg) return;
  stFit();
  const c = ST.cam; if(!c || c.z >= .62) return;
  const p = ST.pos[cfg.start], el = cv.querySelector(`.stc-card[data-id="${cfg.start}"]`);
  if(!p || !el) return;
  const z = .85;
  ST.cam = {z, x: cv.clientWidth - (p.x + el.offsetWidth) * z - 16, y: 136 - p.y * z};
  stApply(); stSave();
}
function stPaintWorld(){
  const wr = $("#stw"), cv = $("#stc");
  if(!wr || !cv || !S.cur) return;
  const fresh = stEnsurePositions();
  const seen = stReach();
  const _ed = stEdges(); ST.inc = {}; for(const e of _ed) ST.inc[e.to] = (ST.inc[e.to] || 0) + 1;
  $("#stu")?.classList.toggle("many", _ed.length > 12 || Object.keys(S.cur.config.nodes).length > 14);
  let h = `<svg id="stsvg" xmlns="http://www.w3.org/2000/svg" width="2" height="2" style="overflow:visible" aria-hidden="true"><path class="w-tmp" id="sttmp" d=""/></svg>`;
  for(const id of Object.keys(S.cur.config.nodes)) h += stCardHTML(id, !seen.has(id));
  wr.innerHTML = h;
  cv.querySelectorAll(".stc-card").forEach(stPlacePorts);
  stMeasure();
  if(fresh){ stAutoLayout(false); stPlaceCards(); stSave(); }      // بار اول: با اندازه‌ی واقعی بخش‌ها دوباره بچین
  stPaintWires();
  stMini(true);
  stApply();
  if(document.fonts?.ready && !ST._fw){            // بعد از آمدن فونت، ارتفاع‌ها عوض می‌شود؛ جای دایره‌ها را دوباره بسنج
    ST._fw = 1;
    document.fonts.ready.then(() => { ST._fw = 0; if(S.view === "studio" && $("#stc")){ stMeasure(); stPaintWires(); stMini(true); } });
  }
}

/* ── ورود به استودیو ── */
function stHintHTML(){
  try{ if(localStorage.getItem("azadi.studio.hint") === "1") return ""; }catch(_){}
  return `<div class="st-hint"><span><b>راهنما:</b> هر بخش یک پیامِ ربات است؛ رویش بزن تا ویرایشش کنی. از دایره‌ی کنار هر دکمه سیم بکش و به یک بخش دیگر وصلش کن تا با زدن آن دکمه، همان بخش نمایش داده شود.</span><button class="b sm" data-a="sthint">متوجه شدم</button></div>`;
}
function renderStudio(){
  if(!S.bots.length){
    $("#app").innerHTML = `<div class="empty" style="padding-top:70px"><div class="ib big">${IC.studio}</div><h2>استودیو</h2><p class="muted">اول یک ربات بساز؛ بعد اینجا بخش‌هایش را ویرایش می‌کنی و به هم وصل می‌کنی.</p><button class="b sm" data-go="create">ساخت ربات</button></div>`;
    return;
  }
  let bot = S.cur && S.bots.find(b => b.id === S.cur.id) ? S.cur : (S.sbot ? S.bots.find(b => b.id === S.sbot) : null);
  if(!bot){
    $("#app").innerHTML = `<div class="st-picker"><div class="ph"><h1>استودیو</h1></div>
      <p class="muted" style="margin:-4px 4px 14px">رباتی را که می‌خواهی ویرایش کنی انتخاب کن. بخش‌هایش را می‌بینی، تغییر می‌دهی و با سیم به هم وصل می‌کنی.</p>
      <div class="group sep">${S.bots.map(b => `<button class="gi" data-a="spick" data-id="${esc(b.id)}"><span class="dot ${b.active ? "on" : ""}"></span><span class="gt"><b>${esc(b.name)}</b><span class="${b.active ? "ltr" : ""}">${b.active ? "@" + esc(b.username) : "هنوز فعال نشده"} · ${N(Object.keys(b.config.nodes).length)} بخش</span></span>${goIc}</button>`).join("")}</div></div>`;
    return;
  }
  S.cur = bot; S.sbot = bot.id;
  if(ST.botId !== bot.id){ ST.botId = bot.id; stLoad(); }
  const nodes = Object.keys(bot.config.nodes).length;
  $("#app").innerHTML = `
    <div class="studio${bot.active ? " live" : ""}" id="stu">
      <div class="st-bar">
        <button class="iconb" data-a="stback" aria-label="بازگشت">${IC.back}</button>
        <button class="st-title" data-a="stbots" aria-label="تغییر ربات">
          <span class="dot ${bot.active ? "on" : ""}"></span>
          <span class="tt"><b>${esc(bot.name)}</b><small id="stsub" class="${bot.active ? "ltr" : ""}">${bot.active ? "@" + esc(bot.username) : "غیرفعال"} · ${N(nodes)} بخش</small></span>
        </button>
        ${bot.versions ? `<button class="iconb" data-a="undo" aria-label="برگشت به نسخه‌ی قبلی" title="برگشت به نسخه‌ی قبلی">${IC.refresh}</button>` : ""}
        <button class="iconb" data-a="health" aria-label="بررسی مسیرها" title="بررسی مسیرها">${IC.heal}</button>
        <button class="b sm" id="stadd" data-a="stadd">${IC.plus}بخش جدید</button>
      </div>
      <div class="st-canvas" id="stc">
        <div class="st-world" id="stw"></div>
        <div class="st-mini" id="stmini" aria-hidden="true"><div class="mm" id="stmm"></div></div>
        <div class="st-search"><input id="stq" placeholder="جستجوی بخش…" autocomplete="off" aria-label="جستجوی بخش"></div>
        <button class="st-energy${bot.active ? " live" : ""}" data-a="stenergy">${IC.bolt}${bot.active ? "ربات روشن است" : "ربات خاموش است"}</button>
        ${stHintHTML()}
        <div class="st-tools">
          <button class="tb" data-a="stzout" aria-label="کوچک‌نمایی">${IC.minus}</button>
          <span class="st-z n" id="stz">100%</span>
          <button class="tb" data-a="stzin" aria-label="بزرگ‌نمایی">${IC.plus}</button>
          <span class="sep"></span>
          <button class="tb" data-a="stfit" aria-label="نمایش همه‌ی بخش‌ها" title="نمایش همه‌ی بخش‌ها">${IC.fit}</button>
          <button class="tb lbl" data-a="stlay" aria-label="چیدمان خودکار" title="بخش‌ها را خودکار مرتب می‌کند">${IC.layers}<span>مرتب‌سازی</span></button>
        </div>
      </div>
    </div>`;
  stPaintWorld();
  if(!ST.cam) requestAnimationFrame(stHome);
  stBindCanvas();
  const q = $("#stq");
  q?.addEventListener("input", () => {
    const v = q.value.trim().toLowerCase(), cv = $("#stc");
    if(!cv) return;
    let first = null;
    cv.querySelectorAll(".stc-card").forEach(el => {
      const n = S.cur.config.nodes[el.dataset.id] || {};
      const hit = !v || el.dataset.id.includes(v) || (n.title || "").toLowerCase().includes(v) || (n.text || "").toLowerCase().includes(v);
      el.classList.toggle("dim", !!v && !hit);
      if(v && hit && !first) first = el.dataset.id;
    });
    cv.querySelectorAll(".wire").forEach(w => w.classList.toggle("dim", !!v));
    if(v && first) stCenter(first);
  });
}
function refreshStudio(){
  if(S.view !== "studio" || !S.cur) return;
  if(!$("#stc")) return renderStudio();
  stPaintWorld();
  const t = $("#stsub"), b = S.cur;
  if(t) t.textContent = `${b.active ? "@" + b.username : "غیرفعال"} · ${fa(Object.keys(b.config.nodes).length)} بخش`;
}

/* ── لمس و ماوس: پن، پینچ، درگ بخش، کشیدن سیم ── */
function stClosePop(){ $("#stpop")?.remove(); }
function stTmpWireTo(wp){ const tp = $("#sttmp"); if(tp && ST._la) tp.setAttribute("d", stPath(ST._la, wp)); }
/* لغزشِ نرم بعد از رها کردن بوم */
function stInertia(vx, vy){
  cancelAnimationFrame(ST._in);
  let last = performance.now();
  const step = t => {
    const dt = Math.min(32, t - last); last = t;
    const f = Math.pow(.93, dt / 16); vx *= f; vy *= f;
    const c = ST.cam || {x: 40, y: 40, z: 1};
    ST.cam = {...c, x: c.x + vx * dt, y: c.y + vy * dt};
    stApply();
    if(Math.hypot(vx, vy) > .04) ST._in = requestAnimationFrame(step); else { ST._in = 0; stSave(); }
  };
  ST._in = requestAnimationFrame(step);
}
const stBtnOf = po => (po && po.dataset.r !== undefined) ? $(`#stc .stk-btn[data-n="${CSS.escape(po.dataset.n)}"][data-r="${po.dataset.r}"][data-c="${po.dataset.c}"]`) : null;
const stDist = P => { const v = [...P.values()]; return Math.hypot(v[0].x - v[1].x, v[0].y - v[1].y); };
const stMid = P => { const v = [...P.values()]; return {x: (v[0].x + v[1].x) / 2, y: (v[0].y + v[1].y) / 2}; };
function stTap(e){
  const now = Date.now(), cv = $("#stc");
  if(stTap.last && now - stTap.last < 320 && Math.hypot(e.clientX - (stTap.x || 0), e.clientY - (stTap.y || 0)) < 44){
    stTap.last = 0;
    const c = ST.cam;
    if(c && cv){ if(c.z < .85) stZoomAt(cv.clientWidth / 2, cv.clientHeight / 2, 1 / c.z); else stFit(); }
    return;
  }
  stTap.last = now; stTap.x = e.clientX; stTap.y = e.clientY;
}
function stBindCanvas(){
  const cv = $("#stc"); if(!cv) return;
  const P = ST.ptr;
  const w2p = e => {
    const r = cv.getBoundingClientRect(), c = ST.cam || {x: 40, y: 40, z: 1};
    return {x: (e.clientX - r.left - c.x) / c.z, y: (e.clientY - r.top - c.y) / c.z};
  };
  cv.addEventListener("pointerdown", e => {
    if(e.pointerType === "mouse" && e.button !== 0) return;
    if(e.target.closest(".st-tools,.st-search,.st-hint,.st-energy,.st-pop,.st-mini,.stc-menu")) return;   // دکمه‌های روی بوم: بدون capture تا کلیکشان به خودشان برسد
    stClosePop();
    cancelAnimationFrame(ST._in); $("#stw")?.classList.remove("glide");
    P.set(e.pointerId, {x: e.clientX, y: e.clientY});
    const port = e.target.closest(".p-out"), card = e.target.closest(".stc-card");
    if(P.size >= 2){
      if(ST.mode?.t === "card") cv.querySelectorAll(".stc-card.drag").forEach(c => c.classList.remove("drag"));
      if(ST.mode?.t === "link"){ $("#stu")?.classList.remove("linking"); const tp = $("#sttmp"); if(tp) tp.setAttribute("d", ""); }
      ST.mode = {t: "pinch", d0: stDist(P), z0: (ST.cam || {z: 1}).z, m0: stMid(P), c0: {...(ST.cam || {x: 40, y: 40, z: 1})}};
      try{ cv.setPointerCapture(e.pointerId); }catch(_){}
      return;
    }
    if(port){
      ST.mode = {t: "link", n: port.dataset.n, p: port.dataset.port, moved: false};
      ST._la = stWorldOf(port);
      stBtnOf(port)?.classList.add("hl");
      $("#stu")?.classList.add("linking");
      try{ cv.setPointerCapture(e.pointerId); }catch(_){}
      stTmpWireTo(w2p(e));
      return;
    }
    if(card && !e.target.closest("button,[data-a],.stc-in")){
      const wp = w2p(e), id = card.dataset.id, p0 = ST.pos[id] || {x: 0, y: 0};
      ST.mode = {t: "card", id, dx: wp.x - p0.x, dy: wp.y - p0.y, sx: e.clientX, sy: e.clientY, moved: false, t0: Date.now()};
      card.classList.add("drag"); stHot(id, true);
      try{ cv.setPointerCapture(e.pointerId); }catch(_){}
      return;
    }
    ST.mode = {t: "pan", sx: e.clientX, sy: e.clientY, c0: {...(ST.cam || {x: 40, y: 40, z: 1})}, moved: false, t0: Date.now()};
    cv.classList.add("panning");
    if(!e.target.closest("[data-a]")) try{ cv.setPointerCapture(e.pointerId); }catch(_){}
  });
  cv.addEventListener("pointermove", e => {
    const m = ST.mode;
    if(!m || !P.has(e.pointerId)) return;
    P.set(e.pointerId, {x: e.clientX, y: e.clientY});
    if(m.t === "pan"){
      if(Math.hypot(e.clientX - m.sx, e.clientY - m.sy) > 6) m.moved = true;
      const now = performance.now();
      if(m.lt){ const dt = Math.max(1, now - m.lt); m.vx = .75 * (m.vx || 0) + .25 * (e.clientX - m.lx) / dt; m.vy = .75 * (m.vy || 0) + .25 * (e.clientY - m.ly) / dt; }
      m.lt = now; m.lx = e.clientX; m.ly = e.clientY;
      ST.cam = {z: m.c0.z, x: m.c0.x + (e.clientX - m.sx), y: m.c0.y + (e.clientY - m.sy)};
      stApply();
    }
    else if(m.t === "pinch"){
      if(P.size < 2) return;
      const d = stDist(P), md = stMid(P), r = cv.getBoundingClientRect();
      const z = Math.min(1.5, Math.max(.16, m.z0 * d / Math.max(20, m.d0)));
      const wx = (m.m0.x - r.left - m.c0.x) / m.z0, wy = (m.m0.y - r.top - m.c0.y) / m.z0;
      ST.cam = {z, x: (md.x - r.left) - wx * z, y: (md.y - r.top) - wy * z};
      stApply();
    }
    else if(m.t === "card"){
      if(Math.hypot(e.clientX - m.sx, e.clientY - m.sy) > 6) m.moved = true;
      if(m.moved){
        const wp = w2p(e), p = ST.pos[m.id] || (ST.pos[m.id] = {x: 0, y: 0});
        p.x = Math.round(wp.x - m.dx);
        p.y = Math.round(wp.y - m.dy);
        m.el = m.el || cv.querySelector(`.stc-card[data-id="${m.id}"]`);
        if(m.el) m.el.style.transform = `translate(${p.x}px,${p.y}px)`;
        if(!ST._wr){ ST._wr = requestAnimationFrame(() => { ST._wr = 0; if(ST.mode?.t === "card") stUpdateWiresFor(ST.mode.id); }); }
      }
    }
    else if(m.t === "link"){
      m.moved = true;
      stTmpWireTo(w2p(e));
      const el = document.elementFromPoint(e.clientX, e.clientY)?.closest(".stc-card");
      cv.querySelectorAll(".stc-card.tgt").forEach(c => c.classList.remove("tgt"));
      if(el && el.dataset.id !== m.n) el.classList.add("tgt");
    }
  });
  const finish = e => {
    const m = ST.mode;
    P.delete(e.pointerId);
    cv.querySelectorAll(".stc-card.tgt").forEach(c => c.classList.remove("tgt"));
    if(!m) return;
    if(m.t === "link"){
      cv.querySelectorAll(".stk-btn.hl").forEach(b => b.classList.remove("hl"));
      $("#stu")?.classList.remove("linking");
      const tp = $("#sttmp"); if(tp) tp.setAttribute("d", "");
      const tid = document.elementFromPoint(e.clientX, e.clientY)?.closest(".stc-card")?.dataset.id;
      ST.noClick = Date.now();
      if(tid && tid !== m.n) stConnect(m, tid);
      else if(m.moved && !tid) stDropNew(m, e);
      else if(m.moved) toast("سیم را به یک بخش دیگر وصل کن");
      haptic();
    }
    else if(m.t === "card"){
      cv.querySelectorAll(".stc-card.drag").forEach(c => c.classList.remove("drag"));
      stHot(m.id, false);
      if(m.moved){ stUpdateWiresFor(m.id); stSave(); stMini(true); }
      else if(Date.now() - m.t0 < 500) openNode(m.id);
    }
    else if(m.t === "pan"){
      cv.classList.remove("panning");
      if(m.moved){
        stSave(); ST.noClick = Date.now();
        const sp = Math.hypot(m.vx || 0, m.vy || 0);
        if(!reduced() && performance.now() - (m.lt || 0) < 90 && sp > .3) stInertia(m.vx, m.vy);
      }
      else stTap(e);
    }
    if(P.size === 0) ST.mode = null;
    else if(P.size === 1 && m.t === "pinch"){
      const rem = [...P.values()][0];
      ST.mode = {t: "pan", sx: rem.x, sy: rem.y, c0: {...(ST.cam || {x: 40, y: 40, z: 1})}, moved: true, t0: 0};
    }
  };
  cv.addEventListener("pointerup", finish);
  cv.addEventListener("pointercancel", e => {
    P.delete(e.pointerId);
    cv.classList.remove("panning");
    cv.querySelectorAll(".stc-card.drag,.stc-card.tgt").forEach(c => c.classList.remove("drag", "tgt"));
    $("#stsvg")?.querySelectorAll(".wire.hot").forEach(w => w.classList.remove("hot"));
    $("#stu")?.classList.remove("linking");
    const tp = $("#sttmp"); if(tp) tp.setAttribute("d", "");
    if(!P.size) ST.mode = null;
  });
  cv.addEventListener("wheel", e => {
    e.preventDefault();
    const r = cv.getBoundingClientRect();
    stZoomAt(e.clientX - r.left, e.clientY - r.top, Math.exp(-e.deltaY * .0016));
  }, {passive: false});
  cv.addEventListener("dblclick", e => { if(!e.target.closest(".stc-card,.st-tools,.st-pop,.st-search,.st-hint")) stFit(); });
  cv.addEventListener("click", e => {
    if(!e.target.closest("#stpop") && Date.now() - (ST.popT || 0) > 450) stClosePop();
    if(Date.now() - (ST.noClick || 0) < 350) return;
    if(e.target.closest(".stc-card,.st-tools,.st-pop,.st-search,.st-hint,.st-energy,.st-mini")) return;
    const ed = stWireAt(e);
    if(ed) stWireMenu(ed);
  });
  cv.addEventListener("contextmenu", e => e.preventDefault());
  cv.addEventListener("pointerover", e => { const po = e.target.closest?.(".p-out"); if(po) stBtnOf(po)?.classList.add("hl"); });
  cv.addEventListener("pointerout", e => { const po = e.target.closest?.(".p-out"); if(po && !ST.mode) stBtnOf(po)?.classList.remove("hl"); });
  const mini = $("#stmini");
  if(mini){
    const jump = e => {
      const m = ST.mini; if(!m) return;
      const r = mini.getBoundingClientRect(), c = ST.cam || {x: 40, y: 40, z: 1};
      const wx = (e.clientX - r.left - m.ox) / m.s + m.x1, wy = (e.clientY - r.top - m.oy) / m.s + m.y1;
      ST.cam = {z: c.z, x: cv.clientWidth / 2 - wx * c.z, y: cv.clientHeight / 2 - wy * c.z}; stApply();
    };
    mini.addEventListener("pointerdown", e => { e.stopPropagation(); try{ mini.setPointerCapture(e.pointerId); }catch(_){} mini._d = true; jump(e); });
    mini.addEventListener("pointermove", e => { if(mini._d) jump(e); });
    const end = () => { if(mini._d){ mini._d = false; stSave(); } };
    mini.addEventListener("pointerup", end); mini.addEventListener("pointercancel", end);
  }
}

/* ── اتصال و ساخت ── */
function stConnect(m, tid){
  const t = titleOf(S.cur.config, tid);
  let src;
  if(m.p === "+"){
    const rows = S.cur.config.nodes[m.n]?.buttons || [];
    if(rows.length >= 6 && rows.every(r => r.length >= 3)) return toast("این بخش به حداکثر تعداد دکمه رسیده");
    if(rows.some(r => r.some(b => b.goto === tid))) return toast("این بخش از قبل دکمه‌ای به همان مقصد دارد");
    src = {t: "new", n: m.n};
  } else src = stParsePort(m.p);
  busy(null, () => commit(cfg => stWireIn(cfg, src, tid), `سیم به «${t}» وصل شد`));
}
function stDropNew(m, e){
  stClosePop();
  const cv = $("#stc"); if(!cv) return;
  const r = cv.getBoundingClientRect(), c = ST.cam || {x: 40, y: 40, z: 1};
  ST.popT = Date.now();
  ST.drop = m;
  ST.dropAt = {x: (e.clientX - r.left - c.x) / c.z - 110, y: (e.clientY - r.top - c.y) / c.z - 40};
  const pop = document.createElement("div");
  pop.className = "st-pop"; pop.id = "stpop";
  pop.style.left = Math.min(cv.clientWidth - 190, Math.max(6, e.clientX - r.left)) + "px";
  pop.style.top = Math.min(cv.clientHeight - 96, Math.max(6, e.clientY - r.top)) + "px";
  pop.innerHTML = `<button data-a="stnew">${IC.plus}<span>ساخت بخش جدید و اتصال</span></button><button data-a="stpopx">${IC.x}<span>انصراف</span></button>`;
  cv.appendChild(pop);
}
function stCreateConnected(){
  const m = ST.drop, at = ST.dropAt;
  ST.drop = null; ST.dropAt = null;
  if(!m || !at || !S.cur) return;
  if(Object.keys(S.cur.config.nodes).length >= (S.cfg.max_nodes || 60)) return toast("به سقف تعداد بخش‌ها رسیدی");
  const id = stNextId();
  ST.pos[id] = {x: Math.round(at.x / 8) * 8, y: Math.round(at.y / 8) * 8};
  const src = m.p === "+" ? {t: "new", n: m.n} : stParsePort(m.p);
  busy(null, async () => {
    await commit(cfg => {
      cfg.nodes[id] = {title: "بخش جدید", text: "متن این بخش را اینجا بنویس", ask: false, buttons: []};
      stWireIn(cfg, src, id);
    }, "بخش ساخته و وصل شد");
    stCenter(id);
    openNode(id);
  });
}
function stCopy(id){
  if(Object.keys(S.cur.config.nodes).length >= (S.cfg.max_nodes || 60)) return toast("به سقف تعداد بخش‌ها رسیدی");
  const nid = stNextId(), p = ST.pos[id] || {x: 0, y: 0};
  ST.pos[nid] = {x: p.x + 40, y: p.y + 80};
  busy(null, () => commit(cfg => {
    const n = cp(cfg.nodes[id]);
    if(n.title) n.title = (n.title + " (کپی)").slice(0, 30);
    cfg.nodes[nid] = n;
  }, "بخش کپی شد"));
}

/* ── منوها ── */
const stBadIc = ic => `<span class="ib" style="color:var(--bad);background:color-mix(in srgb,var(--bad) 10%,transparent)">${ic}</span>`;
function stCardMenu(id){
  const cfg = S.cur.config, isRoot = id === cfg.start || id === cfg.fallback;
  S.sheet = {kind: "info"};
  showSheet(head("بخشِ «" + esc(titleOf(cfg, id)) + "»") + `<div class="group" style="margin-top:10px">
    <button class="gi" data-sh="stedit" data-n="${esc(id)}"><span class="ib">${IC.gear}</span><span class="gt"><b>ویرایش بخش</b><span>متن، عکس، فرم، هوش مصنوعی و شرط‌ها</span></span>${goIc}</button>
    <button class="gi" data-sh="stkm" data-n="${esc(id)}"><span class="ib">${IC.layers}</span><span class="gt"><b>دکمه‌ها و کیبورد</b><span>افزودن، ویرایش، ترتیب و نوع نمایش</span></span>${goIc}</button>
    <button class="gi" data-sh="stcopy" data-n="${esc(id)}"><span class="ib">${IC.copy}</span><span class="gt"><b>کپی بخش</b><span>با همه‌ی دکمه‌ها و تنظیماتش</span></span>${goIc}</button>
    <button class="gi" data-sh="stcenter" data-n="${esc(id)}"><span class="ib">${IC.fit}</span><span class="gt"><b>نمایش در وسط صفحه</b><span>نقشه روی همین بخش می‌آید</span></span>${goIc}</button>
    ${id === cfg.start ? "" : `<button class="gi" data-sh="stsetstart" data-n="${esc(id)}"><span class="ib">${IC.bolt}</span><span class="gt"><b>شروع ربات از این بخش</b><span>کاربر بعد از زدن /start اول همین بخش را می‌بیند</span></span>${goIc}</button>`}
    ${isRoot ? "" : `<button class="gi" data-sh="stdel" data-n="${esc(id)}">${stBadIc(IC.trash)}<span class="gt"><b>حذف بخش</b><span>دکمه‌هایی که به این بخش می‌رسند هم برداشته می‌شوند</span></span>${goIc}</button>`}
  </div><div class="fgap"></div>`);
}
function stWireMenu(ed){
  const cfg = S.cur.config;
  let title, body;
  if(ed.kind === "btn" || ed.kind === "pay"){
    const b = cfg.nodes[ed.n]?.buttons[ed.r]?.[ed.c] || {};
    title = `سیمِ دکمه‌ی «${esc(b.text || "")}»`;
    body = `<button class="gi" data-sh="stwe" data-k="${ed.key}"><span class="ib">${IC.gear}</span><span class="gt"><b>ویرایش دکمه</b><span>متن، نوع و مقصد</span></span>${goIc}</button>
      <button class="gi" data-sh="stwx" data-k="${ed.key}">${stBadIc(IC.trash)}<span class="gt"><b>حذف دکمه</b><span>دکمه و سیمش برداشته می‌شود</span></span>${goIc}</button>`;
  } else if(ed.kind === "route"){
    title = "سیمِ هدایت شرطی";
    body = `<button class="gi" data-sh="stwr" data-k="${ed.key}"><span class="ib">${IC.gear}</span><span class="gt"><b>ویرایش شرط</b><span>از قسمت «منطق پیشرفته» در ویرایش بخش</span></span>${goIc}</button>
      <button class="gi" data-sh="stwrx" data-k="${ed.key}">${stBadIc(IC.trash)}<span class="gt"><b>حذف شرط</b><span>این مسیر شرطی برداشته می‌شود</span></span>${goIc}</button>`;
  } else {
    title = "سیمِ ادامه بعد از ثبت";
    body = `<button class="gi" data-sh="stwr" data-k="${ed.key}"><span class="ib">${IC.gear}</span><span class="gt"><b>ویرایش بخش</b><span>مقصد بعد از ثبت پاسخ را عوض کن</span></span>${goIc}</button>
      <button class="gi" data-sh="stnx" data-k="${ed.key}">${stBadIc(IC.trash)}<span class="gt"><b>قطع این مسیر</b><span>بعد از ثبت پاسخ، کاربر به بخش شروع برمی‌گردد</span></span>${goIc}</button>`;
  }
  S.sheet = {kind: "info"};
  showSheet(head(title) + `<div class="group" style="margin-top:10px">${body}</div><div class="fgap"></div>`);
}


/* ═════════════════ شیت پایین: زیرساخت ═════════════════ */
async function commit(fn, msg = "ذخیره شد"){
  const cfg = cp(S.cur.config); fn(cfg);
  const d = await api(`/api/bots/${S.cur.id}/config`, "PUT", {config: cfg});
  setBot(d.bot);
  stSheetDirty.touched = false;   // همین فرم ذخیره شد؛ هشدار تغییرات لازم نیست
  closeSheet();
  if(S.view === "studio") refreshStudio(); else renderBot();
  toast(msg); haptic("ok");
}
function closeSheet(){ if(S.sheet?.kind === "ubconn" && D && (D.step === "code" || D.step === "password")) api("/api/userbots/login/cancel", "POST").catch(() => {}); clearInterval(window.__ut); clearInterval(window.__at); clearTimeout(window.__ut); clearTimeout(window.__at); $("#sheet").classList.remove("show"); $("#sheet").innerHTML = ""; S.sheet = null; D = null; stSheetDirty.touched = false; }
function showSheet(html){
  const sh = $("#sheet"), keep = sh.querySelector(".sp")?.scrollTop || 0;
  sh.innerHTML = `<div class="sb" data-x="close"></div><div class="sp" role="dialog" aria-modal="true">${html}</div>`;
  sh.classList.add("show"); sh.querySelector(".sp").scrollTop = keep;
  stSheetDirty.touched = false;
}
/* اگر در استودیو فرمِ ویرایشِ بخش/دکمه چیزی عوض شده باشد، بستنِ ناگهانی با تایید همراه می‌شود */
document.addEventListener("input", e => { if(S.sheet && $("#sheet")?.contains(e.target)) stSheetDirty.touched = true; });
document.addEventListener("change", e => { if(S.sheet && $("#sheet")?.contains(e.target)) stSheetDirty.touched = true; });
function stSheetDirty(){
  return !!(stSheetDirty.touched && S.view === "studio" && S.sheet && (S.sheet.kind === "node" || S.sheet.kind === "btn"));
}
function stGuardClose(go){
  if(!stSheetDirty()) return go();
  confirmQ("تغییرهای این فرم ذخیره نشده. بسته شود؟", ok => { if(ok) go(); });
}
const nodeOpts = (cfg, cur, extra = "") => extra + Object.keys(cfg.nodes).map(i => `<option value="${esc(i)}"${i === cur ? " selected" : ""}>${esc(titleOf(cfg, i))}</option>`).join("");
const head = t => `<div class="grab"></div><div class="sh"><h2>${t}</h2><button class="iconb sm" data-x="close" aria-label="بستن">${IC.x}</button></div>`;

/* ── منطق: متغیر، شرط و اکشن ── */
const OPS = [["==","مساوی باشد با"],["!=","مساوی نباشد با"],[">","بزرگ‌تر از"],[">=","بزرگ‌تر یا مساوی"],["<","کوچک‌تر از"],["<=","کوچک‌تر یا مساوی"],["contains","شامل باشد"],["empty","خالی باشد"],["filled","پر باشد"]];
const ACTS = [["set","مقدار بده"],["add","جمع کن / کم کن"],["clear","پاک کن"],["random","عدد تصادفی"],["notify","به من خبر بده"],["remind","یادآوری بعد از چند دقیقه"]];
const APH = {set:"مقدار (می‌توانی {متغیر} بگذاری)", add:"عدد، مثلاً 5 یا -3", random:"بازه، مثلاً 1-6", notify:"متنی که برای خودت فرستاده می‌شود", remind:"متن یادآوری برای همین کاربر (اختیاری اگر بخش انتخاب کنی)"};
const TYPES = [["text","متن"],["number","عدد"],["phone","شماره تماس"],["email","ایمیل"]];
const BUILTIN_HELP = [["name","اسم کاربر"],["first_name","اسم (بدون جایگزین)"],["last_name","فامیلی"],["full_name","اسم کامل"],["username","@آیدی کاربر"],["id","آیدی عددی"],
  ["lang","زبان تلگرام (fa, en…)"],["premium","پریمیوم؟ 1 یا 0"],["is_owner","صاحب ربات؟ 1 یا 0"],["visits","تعداد استارت‌های کاربر"],["refs","تعداد دعوت‌های موفق کاربر"],["ref_link","لینک دعوت شخصی کاربر"],["text","آخرین پیام کاربر"],
  ["param","پارامتر لینک /start"],["date","تاریخ شمسی"],["time","ساعت تهران"],["hour","ساعت (0 تا 23)"],["weekday","روز هفته"],["ticket_no","شماره‌ی آخرین تیکت کاربر"],["bot_name","نام ربات"],["bot_username","آیدی ربات"]];
const BUILTIN = BUILTIN_HELP.map(x => x[0]);
const chList = v => String(v || "").split(/[\s,،]+/).filter(Boolean).map(x => x.replace(/^(https?:\/\/)?(t\.me|telegram\.me)\//i, "").replace(/^@/, ""));
const chOut = (v, text) => { const l = chList(v); if(l.length > 3) return "حداکثر ۳ کانال"; if(l.some(c => !/^[A-Za-z][A-Za-z0-9_]{4,31}$/.test(c))) return "آیدی کانال معتبر نیست (مثل @channel_id)"; return l.length ? {channels: l, text: (text || "").trim()} : null; };
const joinBox = (d, what) => `<details class="adv jn"${d.jch ? " open" : ""}><summary>عضویت اجباری در کانال</summary><div class="box">
      <p class="muted" style="margin-bottom:8px">${what} فقط وقتی کاربر عضو این کانال‌ها باشد کار می‌کند؛ وگرنه پیام عضویت می‌بیند و بعد از عضو شدن مستقیم به همین‌جا می‌رسد. ربات باید در کانال ادمین باشد. خالی یعنی غیرفعال.</p>
      <span class="lbl">کانال‌ها (تا ${N(3)} تا، با فاصله)</span><input class="ltr" id="j-ch" value="${esc(d.jch)}" placeholder="@channel1 @channel2" autocomplete="off">
      <span class="lbl">پیام درخواست عضویت</span><input class="fa" id="j-tx" data-fmt value="${esc(d.jtx)}" maxlength="500" placeholder="برای ادامه اول عضو کانال شو.">${fmtTools("j-tx")}
    </div></details>`;
const readJoin = () => { if($("#j-ch")){ D.jch = $("#j-ch").value; D.jtx = $("#j-tx").value; } };
const cleanVar = v => String(v || "").toLowerCase().replace(/[^a-z0-9_]/g, "").replace(/^[0-9_]+/, "").slice(0, 20);
const simpleCond = c => !!c && typeof c.var === "string" && !c.all && !c.any && !c.not;
const blankCond = () => ({var:"", op:"==", value:""});
const newRule = l => l === "do" ? {op:"set", var:"", value:""} : l === "route" ? {c:blankCond(), goto:S.cur.config.start} : l === "alt" ? {c:blankCond(), text:""} : {c:blankCond()};
const dlist = () => `<datalist id="vdl">${[...Object.keys(S.cur.config.vars || {}), ...Object.keys(S.cur.config.globals || {}), ...BUILTIN].map(v => `<option value="${esc(v)}"></option>`).join("")}</datalist>`;

function condHTML(c){
  if(c && !simpleCond(c)) return `<div class="muted">شرط ترکیبی؛ فقط با هوش مصنوعی عوض می‌شود</div>`;
  const x = c || blankCond(), nov = x.op === "empty" || x.op === "filled";
  return `<div class="cmd"><input class="c-var" list="vdl" value="${esc(x.var)}" placeholder="متغیر (مثلاً coins)" maxlength="20" autocomplete="off">
    <select class="c-op" data-sh="re">${OPS.map(([v, l]) => `<option value="${v}"${v === x.op ? " selected" : ""}>${l}</option>`).join("")}</select></div>
    ${nov ? "" : `<input class="fa c-val" value="${esc(x.value || "")}" placeholder="مقدار" maxlength="100">`}`;
}
function ruleHTML(list, o, i, cfg){
  const del = `<button class="iconb sm" data-sh="delrl" data-l="${list}" data-i="${i}" aria-label="حذف">${IC.x}</button>`;
  let inner;
  if(list === "do"){
    inner = `<div class="cmd"><select class="a-op" data-sh="re">${ACTS.map(([v, l]) => `<option value="${v}"${v === o.op ? " selected" : ""}>${l}</option>`).join("")}</select>
      ${o.op === "notify" || o.op === "remind" ? "" : `<input class="a-var" list="vdl" value="${esc(o.var || "")}" placeholder="نام متغیر" maxlength="20" autocomplete="off">`}${del}</div>
      ${o.op === "remind" ? `<div class="cmd"><input class="a-min" type="number" min="1" max="43200" value="${esc(o.minutes || 60)}" placeholder="چند دقیقه بعد؟"><select class="a-rg">${nodeOpts(cfg, o.goto || "", '<option value="">فقط پیام</option>')}</select></div>` : ""}
      ${o.op === "clear" ? "" : `<input class="fa a-val" value="${esc(o.value || "")}" placeholder="${esc(APH[o.op])}" maxlength="${o.op === "notify" || o.op === "remind" ? 500 : 100}">`}`;
  } else {
    inner = `<div class="cmd" style="justify-content:space-between"><span class="muted">${list === "when" ? "فقط وقتی…" : "اگر…"}</span>${del}</div>${condHTML(o.c)}`;
    if(list === "route") inner += `<span class="lbl">بعدش برو به</span><select class="r-goto">${nodeOpts(cfg, o.goto)}</select>`;
    if(list === "alt") inner += `<div class="fgap"></div><textarea class="fa r-text" data-fmt maxlength="3500" placeholder="متن جایگزین">${esc(o.text || "")}</textarea>${fmtTools("@last")}`;
  }
  return `<div class="rl" data-list="${list}" data-i="${i}">${inner}</div>`;
}
function ruleSection(title, hint, list, cfg, max){
  const arr = D[list];
  return `<div class="sub"><span>${title}</span>${arr.length < max ? `<button class="iconb sm" data-sh="addrl" data-l="${list}" aria-label="افزودن">${IC.plus}</button>` : ""}</div>
    ${hint ? `<p class="muted" style="margin:-3px 0 8px">${hint}</p>` : ""}${arr.map((o, i) => ruleHTML(list, o, i, cfg)).join("")}`;
}
function readRl(list){
  const rows = [...document.querySelectorAll(`.rl[data-list="${list}"]`)];
  if(!rows.length || !D[list]) return;
  D[list] = rows.map((r, i) => {
    const o = {...(D[list][i] || {})}, q = s => r.querySelector(s);
    if(q(".c-var")) o.c = {var:cleanVar(q(".c-var").value), op:q(".c-op").value, value:q(".c-val")?.value ?? ""};
    if(q(".r-goto")) o.goto = q(".r-goto").value;
    if(q(".r-text")) o.text = q(".r-text").value;
    if(q(".a-op")){
      o.op = q(".a-op").value;
      o.var = q(".a-var") ? cleanVar(q(".a-var").value) : (o.var || "");
      o.value = q(".a-val") ? q(".a-val").value : (o.value || "");
      if(q(".a-min")) o.minutes = parseInt(q(".a-min").value) || 0;
      if(q(".a-rg")) o.goto = q(".a-rg").value;
    }
    return o;
  });
}
function ruleErr(){
  const empty = c => c && simpleCond(c) && !c.var;
  for(const a of D.do || []){
    if(a.op === "notify"){ if(!(a.value || "").trim()) return "متن اعلانِ اکشن «به من خبر بده» را بنویس"; }
    else if(a.op === "remind"){
      const mm = a.minutes === undefined ? 60 : +a.minutes;
      if(!(mm >= 1 && mm <= 43200)) return "زمان یادآوری باید بین ۱ تا ۴۳۲۰۰ دقیقه (۳۰ روز) باشد";
      if(!(a.value || "").trim() && !a.goto) return "برای یادآوری، متن بنویس یا یک بخش انتخاب کن";
    }
    else if(!a.var) return "اسم متغیرِ اکشن را بنویس";
  }
  for(const r of D.route || []) if(empty(r.c)) return "برای هدایت شرطی، اسم متغیرِ شرط را بنویس";
  for(const r of D.alt || []){
    if(empty(r.c)) return "برای متن جایگزین، اسم متغیرِ شرط را بنویس";
    if(!(r.text || "").trim()) return "متن جایگزین نباید خالی باشد";
  }
  for(const r of D.when || []) if(empty(r.c)) return "برای نمایش شرطیِ دکمه، اسم متغیرِ شرط را بنویس";
  return null;
}
const outActs = l => l.map(a => a.op === "remind" ? {op:"remind", minutes:Math.max(1, Math.min(43200, parseInt(a.minutes) || 60)), ...((a.value || "").trim() ? {value:a.value.trim()} : {}), ...(a.goto ? {goto:a.goto} : {}), ...(a.key ? {key:a.key} : {})} : a.op === "notify" ? {op:"notify", value:a.value || ""} : a.op === "clear" ? {op:"clear", var:a.var} : {op:a.op, var:a.var, value:a.value || ""});

/* ── ویرایش بخش ── */
function openNode(id){
  const cfg = S.cur.config, n = cfg.nodes[id];
  S.sheet = {kind: "node", id};
  D = { title: n.title || "", text: n.text, photo: n.photo || "", media: n.media || "", doneMedia: n.done_media || "", done: n.done || "", next: n.next || "",
        fields: n.fields ? n.fields.map((q, i) => ({q, v: (n.save || [])[i] || "", t: (n.types || [])[i] || "text"})) : [{q: "", v: "", t: "text"}],
        silent: !!n.silent, mode: n.fields ? "form" : n.ask ? "ask" : n.ai ? "ai" : "show",
        aip: n.ai?.prompt || "", aid: n.ai?.daily || 15, aim: n.ai?.memory ?? 3,
        start: id === cfg.start, fb: id === cfg.fallback,
        jch: (n.join?.channels || []).map(c => "@" + c).join(" "), jtx: n.join?.text || "",
        ticket: !!n.ticket, tag: n.tag || "", bvar: n.board?.var || "", btop: n.board?.top || 10,
        do: cp(n.do || []), route: (n.route || []).map(r => ({c: cp(r.when), goto: r.goto})), alt: (n.alt || []).map(r => ({c: cp(r.when), text: r.text})), adv: false };
  renderSheet();
}
function kbSummary(n){
  const all = (n.buttons || []).flat(), rk = all.filter(b => b.kb === "reply").length, gl = all.length - rk;
  return [gl ? N(gl) + " شیشه‌ای" : "", rk ? N(rk) + " کیبورد چت" : ""].filter(Boolean).join(" · ") || "بدون دکمه";
}
function kbPicker(cur){
  const inl = `<svg viewBox="0 0 58 44" fill="none" stroke="currentColor" stroke-width="1.4"><rect x="4" y="3" width="40" height="17" rx="6" fill="currentColor" fill-opacity=".14" stroke="none"/><rect x="4.7" y="24" width="23" height="8" rx="3.5"/><rect x="30.7" y="24" width="23" height="8" rx="3.5"/><rect x="4.7" y="34.5" width="49" height="7" rx="3.5"/></svg>`;
  const rpl = `<svg viewBox="0 0 58 44" fill="none" stroke="currentColor" stroke-width="1.4"><rect x="4" y="2" width="40" height="15" rx="6" fill="currentColor" fill-opacity=".14" stroke="none"/><rect x="1" y="24" width="56" height="19" rx="4" fill="currentColor" fill-opacity=".1" stroke="none"/><rect x="4" y="27" width="15" height="6" rx="2"/><rect x="21.5" y="27" width="15" height="6" rx="2"/><rect x="39" y="27" width="15" height="6" rx="2"/><rect x="4" y="35" width="50" height="5" rx="2"/></svg>`;
  return `<span class="lbl">نوع این دکمه</span>
    <div class="seg">
      <button class="${cur !== "reply" ? "on" : ""}" data-sh="kbt" data-v="inline">${inl}<b>شیشه‌ای</b><small>زیر پیام، چسبیده به آن</small></button>
      <button class="${cur === "reply" ? "on" : ""}" data-sh="kbt" data-v="reply">${rpl}<b>کیبورد</b><small>پایین چت، مثل منوی ثابت</small></button>
    </div>
    ${cur === "reply" ? `<p class="muted mt">دکمه‌های کیبورد با یک پیام کوچک (👇) زیر چت می‌آیند. در یک بخش می‌توانی هم دکمه‌ی شیشه‌ای داشته باشی هم کیبورد.</p>` : ""} : ""}`;
}
let FMT_LAST = null;
document.addEventListener("focusin", e => { if(e.target.matches?.("[data-fmt]")) FMT_LAST = e.target; });
const fmtTools = tid => `<div class="fmtbar" title="قالب HTML تلگرام">${FMT_TAGS.map((t, i) => `<button type="button" data-a="fmtb" data-t="${tid}" data-i="${i}" aria-label="${t[1]}">${t[0]}</button>`).join("")}<button type="button" data-a="emojitag" data-t="${tid}" title="ایموجی پرمیوم (اشتراک پرمیوم و پرو)" aria-label="ایموجی پرمیوم">✨</button></div>`;
function emojiInsert(t){
  if(!S.cfg.emoji){ toast("ایموجی پرمیوم مخصوص اشتراک پرمیوم و پرو است"); return; }
  const a = t.selectionStart ?? t.value.length, b = t.selectionEnd ?? a;
  let sel = t.value.slice(a, b) || "😀";
  const open = '<tg-emoji emoji-id="', id0 = "1234567890", close = '">' + sel + "</tg-emoji>";
  t.value = t.value.slice(0, a) + open + id0 + close + t.value.slice(b);
  const s0 = a + open.length, s1 = s0 + id0.length;
  t.focus(); t.setSelectionRange(s0, s1);
  t.dispatchEvent(new Event("input", {bubbles: true}));
  toast("آیدی عددی ایموجی را جایگزین کن");
}
function fmtInsert(t, i){
  const tg_ = FMT_TAGS[i], o = tg_[2], c = tg_[3], a = t.selectionStart ?? t.value.length, b = t.selectionEnd ?? a, sel = t.value.slice(a, b) || "متن";
  t.value = t.value.slice(0, a) + o + sel + c + t.value.slice(b); t.focus(); t.setSelectionRange(a + o.length, a + o.length + sel.length); t.dispatchEvent(new Event("input", {bubbles: true}));
}
function nodeSheet(){
  const cfg = S.cur.config, d = D;
  const advOpen = d.adv || d.do.length || d.route.length || d.alt.length || d.bvar;
  return head("ویرایش بخش") + `
    <span class="lbl">نام بخش (فقط برای خودت)</span><input class="fa" id="f-title" value="${esc(d.title)}" maxlength="30" placeholder="مثلاً: منوی اصلی">
    <span class="lbl">متن پیام</span><textarea class="fa" id="f-text" data-fmt maxlength="3500">${esc(d.text)}</textarea>${fmtTools("f-text")}
    <p class="muted mt">برای شخصی‌سازی پیام از متغیر استفاده کن؛ مثل <b dir="ltr">{name}</b> برای اسم کاربر یا <b dir="ltr">{coins}</b> برای متغیر خودت. فهرست کامل در تنظیمات ربات است.</p>
    <span class="lbl">رسانه (عکس، ویدیو، گیف، موسیقی، ویس یا فایل)</span>${mediaPicker("media", d.media)}
    ${d.media ? `<p class="muted">متن بخش همراه رسانه، به‌عنوان توضیحِ زیر آن فرستاده می‌شود.</p>` : `<span class="lbl">یا لینک مستقیم عکس (اختیاری)</span><input id="f-photo" value="${esc(d.photo)}" placeholder="https://.../photo.jpg" autocomplete="off">`}
    <span class="lbl">این بخش چه کاری انجام بدهد؟</span>
    <select id="f-mode" data-sh="mode">
      <option value="show"${d.mode === "show" ? " selected" : ""}>نمایش پیام (با دکمه)</option>
      <option value="ai"${d.mode === "ai" ? " selected" : ""}>گفتگو با هوش مصنوعی</option>
      <option value="ask"${d.mode === "ask" ? " selected" : ""}>گرفتن یک پیام از کاربر</option>
      <option value="form"${d.mode === "form" ? " selected" : ""}>فرم چندمرحله‌ای</option>
    </select>
    ${d.mode === "ai" ? `<span class="lbl">دستور دستیار (نقش، لحن، اطلاعات کسب‌وکار)</span>
      <textarea class="fa" id="f-aip" maxlength="1500" style="min-height:140px" placeholder="مثلاً: تو دستیار فروشگاه موبایل «نوید» هستی. محترم و کوتاه جواب بده. ساعت کاری ۹ تا ۲۱ است.">${esc(d.aip)}</textarea>
      <span class="lbl">سقف پیام هر کاربر در روز</span><input id="f-aid" type="number" min="1" max="100" value="${esc(d.aid)}">
      <span class="lbl">حافظه‌ی گفتگو (چند پیام قبلی، 0 تا 6)</span><input id="f-aim" type="number" min="0" max="6" value="${esc(d.aim)}">
      <div class="aibox">${billingFixed() ? `هر ${N(S.cfg.ai_per)} پیام هوشمند، ${N(1)} توکن` : "هزینه‌ی هر پیام هوشمند از روی مصرف واقعی حساب می‌شود (کسری از یک توکن تا ۱ توکن)؛"} از حساب تو کم می‌شود. موجودی تو ${N(S.wallet.tokens)} توکن است و با تمام شدنش این بخش برای کاربرها غیرفعال می‌شود. حتماً یک دکمه‌ی بازگشت به این بخش اضافه کن.</div>` : ""}
    ${d.mode === "form" ? `<span class="lbl">سؤال‌ها به ترتیب</span>
      ${d.fields.map((f, i) => `<div class="rl fq"><div class="cmd"><input class="fa fld" data-fmt value="${esc(f.q)}" placeholder="مثلاً: اسمت چیست؟" maxlength="200"><button class="iconb sm" data-sh="delfld" data-i="${i}" aria-label="حذف سؤال">${IC.x}</button></div>
        <div class="cmd"><input class="fv" list="vdl" value="${esc(f.v)}" placeholder="ذخیره در متغیر (اختیاری)" maxlength="20" autocomplete="off">
        <select class="ft">${TYPES.map(([v, l]) => `<option value="${v}"${v === f.t ? " selected" : ""}>${l}</option>`).join("")}</select></div></div>`).join("")}
      ${fmtTools("@last")}
      ${d.fields.length < 6 ? `<button class="b o sm" data-sh="addfld">${IC.plus}سؤال</button>` : ""}
      <label class="chk"><input type="checkbox" id="f-silent"${d.silent ? " checked" : ""}> نتیجه‌ی فرم برای من فرستاده نشود</label>` : ""}
    ${d.mode === "ask" || d.mode === "form" ? `<span class="lbl">پیام تشکر بعد از ثبت</span><input class="fa" id="f-done" data-fmt value="${esc(d.done)}" maxlength="500" placeholder="ثبت شد، ممنون!">${fmtTools("f-done")}
      <span class="lbl">رسانه‌ی پیام تشکر (اختیاری)</span>${mediaPicker("doneMedia", d.doneMedia)}
      <span class="lbl">بعد از ثبت پاسخ، کدام بخش نمایش داده شود؟</span><select id="f-next">${nodeOpts(cfg, d.next, '<option value="">منوی شروع</option>')}</select>
      <label class="chk"><input type="checkbox" id="f-ticket"${d.ticket ? " checked" : ""}> هر پیام یک تیکت شماره‌دار شود (دکمه‌ی «پاسخ» برای من و پشتیبان‌ها)</label>
      ${d.ticket ? `<span class="lbl">برچسب تیکت (اختیاری، مثلاً فروش یا فنی)</span><input class="fa" id="f-tag" value="${esc(d.tag)}" maxlength="20">` : ""}
      <p class="muted mt">${d.ticket ? "پیام کاربر با شماره‌ی تیکت برایت می‌آید و زیرش دکمه‌های پاسخ، سابقه، بستن و مسدود کردن است. با /tickets تیکت‌های باز را می‌بینی." : "پیام کاربرها برای تو فرستاده می‌شود. داخل ربات با Reply روی هر کدام، جوابت به خودش می‌رسد."}</p>` : ""}
    <div class="sub"><span>دکمه‌ها</span></div>
    <div class="group"><button class="gi" data-sh="stkm" data-n="${esc(S.sheet.id)}"><span class="ib">${IC.layers}</span><span class="gt"><b>دکمه‌ها و کیبورد</b><span>${N((cfg.nodes[S.sheet.id].buttons || []).reduce((a, r) => a + r.length, 0))} دکمه · ${kbSummary(cfg.nodes[S.sheet.id])}</span></span>${goIc}</button></div>
    <details class="adv"${advOpen ? " open" : ""}><summary>منطق پیشرفته: متغیر و شرط</summary><div class="box">
      ${ruleSection("وقتی کاربر وارد این بخش شد…", "مثلاً امتیاز جمع کن، مقداری ذخیره کن یا به خودت خبر بده", "do", cfg, 6)}
      ${ruleSection("هدایت شرطی", "اولین شرطِ درست، کاربر را به بخش دیگری می‌فرستد (مثل قفل، اشتراک ویژه، ساعت کاری)", "route", cfg, 5)}
      ${ruleSection("متن جایگزین شرطی", "اگر شرط درست بود، به‌جای متن اصلی نشان داده می‌شود", "alt", cfg, 4)}
      <div class="sub"><span>جدول برترین‌ها</span></div><p class="muted" style="margin:-3px 0 8px">زیر متن این بخش رتبه‌بندی کاربرها بر اساس یک متغیر عددی (یا refs برای دعوت‌ها) نشان داده می‌شود. خالی یعنی غیرفعال.</p>
      <div class="cmd"><input class="ltr" id="f-bvar" list="vdl" value="${esc(d.bvar)}" placeholder="متغیر عددی، مثلاً coins" maxlength="20" autocomplete="off"><input id="f-btop" type="number" min="3" max="20" value="${esc(d.btop)}" placeholder="چند نفر؟"></div>
    </div></details>${joinBox(d, "این بخش")}${dlist()}
    <label class="chk"><input type="checkbox" id="f-start"${d.start ? " checked disabled" : ""}> بخش شروع ربات (/start)</label>
    <label class="chk"><input type="checkbox" id="f-fb"${d.fb ? " checked disabled" : ""}> پاسخ به پیام‌هایی که ربات متوجه‌شان نمی‌شود</label>
    <div class="bar"><button class="b" data-sh="save">ذخیره</button>${d.start || d.fb ? "" : `<button class="b r" data-sh="del">حذف بخش</button>`}</div>`;
}
function readNode(){
  const g = s => $(s)?.value ?? null;
  D.title = g("#f-title") ?? D.title; D.text = g("#f-text") ?? D.text; D.photo = g("#f-photo") ?? D.photo;
  D.mode = g("#f-mode") ?? D.mode;
  D.aip = g("#f-aip") ?? D.aip; D.aid = g("#f-aid") ?? D.aid; D.aim = g("#f-aim") ?? D.aim;
  const fq = [...document.querySelectorAll(".fq")];
  if(fq.length) D.fields = fq.map(r => ({q: r.querySelector(".fld").value, v: cleanVar(r.querySelector(".fv").value), t: r.querySelector(".ft").value}));
  if($("#f-silent")) D.silent = $("#f-silent").checked;
  if($("#f-ticket")) D.ticket = $("#f-ticket").checked;
  if($("#f-tag")) D.tag = $("#f-tag").value;
  if($("#f-bvar")){ D.bvar = cleanVar($("#f-bvar").value); D.btop = $("#f-btop").value; }
  if($("#f-done")){ D.done = g("#f-done"); D.next = g("#f-next"); }
  if($("#f-start") && !$("#f-start").disabled) D.start = $("#f-start").checked;
  if($("#f-fb") && !$("#f-fb").disabled) D.fb = $("#f-fb").checked;
  for(const l of ["do", "route", "alt"]) readRl(l);
  readJoin();
  const ad = document.querySelector("details.adv"); if(ad) D.adv = ad.open;
}
function saveNode(){
  const id = S.sheet.id, node = S.cur.config.nodes[id];
  if(!D.text.trim()) return toast("متن پیام نباید خالی باشد");
  if(D.mode === "form" && !D.fields.some(f => f.q.trim())) return toast("حداقل یک سؤال برای فرم بنویس");
  if(D.mode === "ai"){
    if(!D.aip.trim()) return toast("دستور دستیار را بنویس");
    if(!node.buttons.length) return toast("برای خروج کاربر از گفتگو، اول یک دکمه‌ی بازگشت به این بخش اضافه کن");
  }
  const err = ruleErr(); if(err) return toast(err);
  const nj = chOut(D.jch, D.jtx); if(typeof nj === "string") return toast(nj);
  busy($('[data-sh="save"]'), () => commit(cfg => {
    const n = cfg.nodes[id], ob = n.board;
    if(D.mode !== "show") (n.buttons || []).forEach(r => r.forEach(b => { delete b.kb; }));
    for(const k of ["title", "photo", "media", "done_media", "ai", "ask", "fields", "save", "types", "silent", "done", "next", "kb", "do", "route", "alt", "ticket", "tag", "board", "join"]) delete n[k];
    if(nj) n.join = nj;
    if(D.bvar) n.board = {var: D.bvar, top: Math.max(3, Math.min(20, parseInt(D.btop) || 10)), ...(ob?.label ? {label: ob.label} : {})};
    n.text = D.text.trim();
    if(D.title.trim()) n.title = D.title.trim();
    if(D.media && mediaById(D.media)) n.media = D.media;
    else if(D.photo.trim()) n.photo = D.photo.trim();
    if(D.mode === "ask") n.ask = true;
    if(D.mode === "ai") n.ai = {prompt: D.aip.trim(), daily: Math.max(1, Math.min(100, parseInt(D.aid) || 15)), memory: Math.max(0, Math.min(6, isNaN(parseInt(D.aim)) ? 3 : parseInt(D.aim)))};
    if(D.mode === "form"){
      const fl = D.fields.filter(f => f.q.trim());
      n.fields = fl.map(f => f.q.trim());
      if(fl.some(f => f.v)) n.save = fl.map(f => f.v);
      if(fl.some(f => f.t !== "text")) n.types = fl.map(f => f.t);
      if(D.silent) n.silent = true;
    }
    if(D.mode === "ask" || D.mode === "form"){
      if(D.ticket){ n.ticket = true; if((D.tag || "").trim()) n.tag = D.tag.trim(); }
      if(D.done.trim()) n.done = D.done.trim();
      if(D.doneMedia && mediaById(D.doneMedia)) n.done_media = D.doneMedia;
      if(D.next) n.next = D.next;
    }
    if(D.do.length) n.do = outActs(D.do);
    if(D.route.length) n.route = D.route.map(r => ({when: r.c, goto: r.goto}));
    if(D.alt.length) n.alt = D.alt.map(r => ({when: r.c, text: r.text.trim()}));
    if(D.start) cfg.start = id;
    if(D.fb) cfg.fallback = id;
  }));
}
function delNode(){
  const id = S.sheet.id;
  const go = ok => ok && busy($('[data-sh="del"]'), () => commit(cfg => {
    delete cfg.nodes[id];
    for(const n of Object.values(cfg.nodes)){
      n.buttons = n.buttons.map(r => r.map(b => { if(b.pay?.goto === id){ const c = {...b}; delete c.pay.goto; return c; } return b; })
        .filter(b => b.goto !== id)).filter(r => r.length);
      if(n.next === id) delete n.next;
      if(n.route){ n.route = n.route.filter(r => r.goto !== id); if(!n.route.length) delete n.route; }
    }
    for(const k of Object.keys(cfg.commands || {})) if(cfg.commands[k] === id) delete cfg.commands[k];
    delete ST.pos[id];
  }, "بخش حذف شد"));
  confirmQ("این بخش و دکمه‌هایی که به آن وصل‌اند حذف شوند؟", go);
}
function addNode(at){
  const cfg = S.cur.config, ids = Object.keys(cfg.nodes), max = S.cfg.max_nodes || 60;
  if(ids.length >= max) return toast(`حداکثر ${max} بخش`);
  const id = stNextId();
  if(!at){
    const cv = $("#stc"), c = ST.cam || {x: 40, y: 40, z: 1};
    at = cv ? {x: (cv.clientWidth / 2 - c.x) / c.z - 110, y: (cv.clientHeight / 2 - c.y) / c.z - 60} : {x: 40, y: 40};
  }
  ST.pos[id] = {x: Math.round(at.x / 8) * 8, y: Math.round(at.y / 8) * 8};
  busy($("#stadd"), async () => {
    await commit(c => { c.nodes[id] = {title: "بخش جدید", text: "متن این بخش را اینجا بنویس", ask: false, buttons: [[{text: "منوی اصلی", goto: c.start}]]}; }, "بخش اضافه شد");
    stCenter(id);
    openNode(id);
  });
}

/* ── ویرایش دکمه ── */
function openBtn(nid, r, c){
  const cfg = S.cur.config;
  S.sheet = {kind: "btn", n: nid, r, c};
  if(c === null) D = {text: "دکمه‌ی جدید", color: "", kb: "inline", kind: "goto", goto: cfg.start, val: "", when: [], do: [], jch: "", jtx: "", adv: false, stars: 50, ptitle: "", pdesc: "", ptext: "", pgoto: ""};
  else {
    const b = cfg.nodes[nid].buttons[r][c], k = kindOf(b);
    D = {text: b.text, color: b.color || "", kind: k, kb: b.kb === "reply" ? "reply" : "inline", goto: b.goto || cfg.start,
         val: k === "channel" ? "@" + CH_RE.exec(b.url)[1] : b.url || b.alert || b.copy || b.share || "",
         when: b.when ? [{c: cp(b.when)}] : [], do: cp(b.do || []), adv: false,
         jch: (b.join?.channels || []).map(c => "@" + c).join(" "), jtx: b.join?.text || "",
         stars: b.pay?.stars || 50, ptitle: b.pay?.title || "", pdesc: b.pay?.desc || "", ptext: b.pay?.text || "", pgoto: b.pay?.goto || ""};
  }
  renderSheet();
}
const KINDS = [["goto", "رفتن به یک بخش"], ["channel", "کانال یا گروه تلگرام"], ["url", "لینک وب"], ["alert", "پیام پاپ‌آپ"], ["copy", "کپی کردن متن"], ["share", "اشتراک‌گذاری لینک دعوت"], ["pay", "پرداخت با ستاره‌ی تلگرام"]];
function colorPicker(){
  if(!S.cfg.color) return `<p class="muted">رنگ دکمه مخصوص اشتراک پرمیوم و پرو است. <button class="b t sm" data-a="goplan" style="display:inline;min-height:0;padding:0 4px">دیدن اشتراک‌ها</button></p>`;
  const opts = [`<button type="button" class="${!D.color ? "on" : ""}" data-sh="pickcolor" data-v="" title="بی‌رنگ">⭕</button>`,
    ...Object.entries(BTN_COLORS).map(([k, e]) => `<button type="button" class="${D.color === k ? "on" : ""}" data-sh="pickcolor" data-v="${k}" title="${BTN_COLOR_FA[k]}">${e}</button>`)].join("");
  return `<div class="cdots">${opts}</div><p class="muted mt">نقطه‌ی رنگی اولِ متن دکمه در ربات نمایش داده می‌شود.</p>`;
}
function btnSheet(){
  const cfg = S.cur.config, d = D, isNew = S.sheet.c === null;
  const val = {
    goto: `<span class="lbl">به کدام بخش برود؟</span><select id="b-goto">${nodeOpts(cfg, d.goto)}</select>`,
    channel: `<span class="lbl">آیدی کانال یا گروه</span><input id="b-val" value="${esc(d.val)}" placeholder="@channel_id" autocomplete="off">`,
    url: `<span class="lbl">آدرس لینک</span><input id="b-val" value="${esc(d.val)}" placeholder="https://..." autocomplete="off">`,
    alert: `<span class="lbl">متنی که کاربر در پاپ‌آپ می‌بیند</span><textarea class="fa" id="b-val" maxlength="200">${esc(d.val)}</textarea><p class="muted">می‌توانی از <b dir="ltr">{coins}</b> یا هر متغیر دیگری استفاده کنی؛ بعد از اجرای اکشن‌ها محاسبه می‌شود.</p>`,
    copy: `<span class="lbl">متنی که با لمس دکمه کپی می‌شود</span><input class="fa" id="b-val" value="${esc(d.val)}" maxlength="256" placeholder="مثلاً شماره کارت یا کد تخفیف">`,
    share: `<span class="lbl">متنی که همراه لینک دعوت فرستاده می‌شود</span><input class="fa" id="b-val" value="${esc(d.val)}" maxlength="200" placeholder="بیا این ربات را ببین"><p class="muted">با لمس این دکمه، پنجره‌ی ارسال تلگرام با لینک دعوت شخصیِ همان کاربر باز می‌شود. برای پاداش دعوت، در تنظیمات ربات «پاداش دعوت» را پر کن.</p>`,
    pay: `<span class="lbl">قیمت (ستاره‌ی تلگرام، ۱ تا ۱۰٬۰۰۰)</span><input id="b-stars" type="number" min="1" max="10000" value="${esc(d.stars)}">
      <span class="lbl">عنوان فاکتور</span><input class="fa" id="b-ptitle" value="${esc(d.ptitle)}" maxlength="32" placeholder="مثلاً اشتراک ویژه">
      <span class="lbl">توضیح فاکتور (اختیاری)</span><input class="fa" id="b-pdesc" value="${esc(d.pdesc)}" maxlength="255">
      <span class="lbl">پیام بعد از پرداخت موفق</span><input class="fa" id="b-ptext" data-fmt value="${esc(d.ptext)}" maxlength="300" placeholder="پرداخت انجام شد، ممنون!">${fmtTools("b-ptext")}
      <span class="lbl">بعد از پرداخت کدام بخش نشان داده شود؟</span><select id="b-pgoto">${nodeOpts(cfg, d.pgoto, '<option value="">هیچ‌کدام</option>')}</select>
      <p class="muted mt">ستاره‌ها به حساب تلگرامِ تو می‌رود. اکشن‌های این دکمه فقط بعد از پرداختِ موفق اجرا می‌شوند (مثلاً فعال کردن متغیر vip). پرداخت‌ها با /payments دیده می‌شوند و با /refund کد برگشت می‌خورند.</p>`
  }[d.kind];
  const canDo = d.kind === "goto" || d.kind === "alert" || d.kind === "pay";
  const nn = cfg.nodes[S.sheet.n], kbOk = !(nn.ask || nn.fields || nn.ai);
  return head(isNew ? "دکمه‌ی جدید" : "ویرایش دکمه") + `
    <span class="lbl">متن روی دکمه</span><input class="fa" id="b-text" value="${esc(d.text)}" maxlength="40">
    <span class="lbl">رنگ دکمه (اشتراک پرمیوم و پرو)</span>${colorPicker()}
    <span class="lbl">با لمس دکمه چه شود؟</span>
    <select id="b-kind" data-sh="bkind">${KINDS.map(([v, l]) => `<option value="${v}"${v === d.kind ? " selected" : ""}>${l}</option>`).join("")}</select>
    ${val}
    ${kbOk ? kbPicker(d.kb) : `<p class="muted mt">این بخش فرم، دریافت پیام یا هوش مصنوعی است؛ دکمه‌هایش فقط شیشه‌ای می‌شوند.</p>`}
    <details class="adv"${d.adv || d.when.length || d.do.length ? " open" : ""}><summary>شرط و اقدام‌ها (پیشرفته)</summary><div class="box">
      ${ruleSection("نمایش دکمه فقط در این شرایط", "مثلاً فقط برای صاحب ربات، یا وقتی امتیاز کافی است", "when", cfg, 1)}
      ${canDo ? ruleSection("وقتی دکمه لمس شد…", "قبل از رفتن به بخش یا نشان دادن پیام اجرا می‌شوند", "do", cfg, 6)
              : `<p class="muted">اقدام‌ها فقط برای دکمه‌های «رفتن به یک بخش»، «پیام پاپ‌آپ» و «پرداخت» کار می‌کنند.</p>`}
    </div></details>${canDo ? joinBox(d, "این دکمه") : ""}${dlist()}
    <div class="bar"><button class="b" data-sh="save">ذخیره</button>${isNew ? "" : `<button class="b r" data-sh="del">حذف دکمه</button>`}</div>`;
}
function readBtn(){
  D.text = $("#b-text")?.value ?? D.text; D.kind = $("#b-kind")?.value ?? D.kind;  if($("#b-goto")) D.goto = $("#b-goto").value;
  if($("#b-val")) D.val = $("#b-val").value;
  if($("#b-stars")){ D.stars = $("#b-stars").value; D.ptitle = $("#b-ptitle").value; D.pdesc = $("#b-pdesc").value; D.ptext = $("#b-ptext").value; D.pgoto = $("#b-pgoto").value; }
  readRl("when"); readRl("do"); readJoin();
  const ad = document.querySelector("details.adv"); if(ad) D.adv = ad.open;
}
function saveBtn(){
  const {n: nid, r, c} = S.sheet, d = D;
  if(!d.text.trim()) return toast("متن دکمه را بنویس");
  if(d.kind === "pay"){ const st = parseInt(d.stars); if(!(st >= 1 && st <= 10000)) return toast("قیمت باید عددی بین ۱ تا ۱۰٬۰۰۰ ستاره باشد"); }
  else if(d.kind !== "goto" && d.kind !== "share" && !d.val.trim()) return toast("مقصد دکمه را وارد کن");
  const err = ruleErr(); if(err) return toast(err);
  const bj = (d.kind === "goto" || d.kind === "alert" || d.kind === "pay") ? chOut(d.jch, d.jtx) : null; if(typeof bj === "string") return toast(bj);
  const btn = {text: d.text.trim()};
  if(d.color && BTN_COLORS[d.color]) btn.color = d.color;
  if(d.kind === "goto") btn.goto = d.goto;
  else if(d.kind === "alert") btn.alert = d.val.trim();
  else if(d.kind === "copy") btn.copy = d.val.trim();
  else if(d.kind === "share") btn.share = d.val.trim() || "بیا این ربات را ببین";
  else if(d.kind === "pay"){
    btn.pay = {stars: parseInt(d.stars), title: (d.ptitle.trim() || d.text.trim()).slice(0, 32)};
    if(d.pdesc.trim()) btn.pay.desc = d.pdesc.trim();
    if(d.ptext.trim()) btn.pay.text = d.ptext.trim();
    if(d.pgoto) btn.pay.goto = d.pgoto;
  }
  else btn.url = d.val.trim();
  if(bj) btn.join = bj;
  { const nn = S.cur.config.nodes[nid]; if(d.kb === "reply" && !(nn.ask || nn.fields || nn.ai)) btn.kb = "reply"; }
  if(d.when.length) btn.when = d.when[0].c;
  if(d.do.length && (d.kind === "goto" || d.kind === "alert" || d.kind === "pay")) btn.do = outActs(d.do);
  busy($('[data-sh="save"]'), () => commit(cfg => {
    const rows = cfg.nodes[nid].buttons;
    if(c !== null) rows[r][c] = btn;
    else if(r !== null && rows[r]) rows[r].push(btn);
    else rows.push([btn]);
  }));
}
function delBtn(){
  const {n: nid, r, c} = S.sheet;
  busy($('[data-sh="del"]'), () => commit(cfg => {
    const rows = cfg.nodes[nid].buttons; rows[r].splice(c, 1); if(!rows[r].length) rows.splice(r, 1);
  }, "دکمه حذف شد"));
}

/* ── تنظیمات کلی ربات ── */
/* ═════════════════ مدیریت گروه و کانال ═════════════════ */
const MOD_LK = {link: "لینک", forward: "فوروارد", photo: "عکس", video: "ویدیو", sticker: "استیکر", voice: "ویس", document: "فایل", contact: "مخاطب",
  mention: "منشن @", animation: "گیف", audio: "موزیک", poll: "نظرسنجی", location: "موقعیت", via_bot: "ربات اینلاین"};
const MOD_CL = {join: "پیام ورود", leave: "پیام خروج", pin: "پیام سنجاق", title: "تغییر نام و عکس گروه"};
const MOD_DEF = () => ({welcome: "", welcome_del: 60, goodbye: "", rules: "", captcha: {on: true, mins: 3}, lock: ["link", "forward"], words: [], flood: {n: 6, secs: 8},
  action: "warn", warns: {max: 3, then: "mute", mins: 60}, clean: ["join", "leave"], report: true, channel: {}});
function openMod(){
  const m = S.cur.config.mod;
  S.sheet = {kind: "mod"};
  D = {on: !!m, m: Object.assign(MOD_DEF(), m ? JSON.parse(JSON.stringify(m)) : {})};
  renderSheet();
}
function modSheet(){
  const m = D.m, ch = m.channel || {}, bt = ch.button || {}, w = m.warns || {}, sel = (v, o) => Object.entries(o).map(([k, t]) => `<option value="${k}"${v === k ? " selected" : ""}>${t}</option>`).join("");
  const box = (cls, key, on) => `<label class="chk" style="display:inline-flex;margin:0 0 6px 12px"><input type="checkbox" class="${cls}" value="${key}"${on ? " checked" : ""}> ${(cls === "m-lk" ? MOD_LK : MOD_CL)[key]}</label>`;
  return head("مدیریت گروه و کانال") + `
    <p class="muted">ربات را به گروه یا کانال اضافه کن و <b>ادمین</b> کن (حذف پیام، محدود کردن کاربران، سنجاق؛ در کانال: ارسال و ویرایش پیام). بدون ادمین بودن، تلگرام پیام‌ها را به ربات نشان نمی‌دهد. وقتی ربات اضافه شود در چت ربات خبرت می‌کند.</p>
    <label class="chk"><input type="checkbox" id="m-on"${D.on ? " checked" : ""}> مدیریت فعال باشد</label>
    <details class="adv" open><summary>خوش‌آمد و قوانین</summary><div class="box">
      <span class="lbl">پیام خوش‌آمد (قالب HTML؛ {name} و {group})</span><textarea class="fa" id="m-w" data-fmt maxlength="1000" style="min-height:70px">${esc(m.welcome)}</textarea>${fmtTools("m-w")}
      <span class="lbl">حذف خودکار خوش‌آمد بعد از (ثانیه، ۰ = نگه دار)</span><input class="ltr" id="m-wd" inputmode="numeric" value="${esc(m.welcome_del ?? 60)}">
      <span class="lbl">پیام خداحافظی (اختیاری)</span><input class="fa" id="m-g" maxlength="500" value="${esc(m.goodbye)}">
      <span class="lbl">قوانین گروه (با /rules نمایش داده می‌شود)</span><textarea class="fa" id="m-r" maxlength="2000" style="min-height:70px">${esc(m.rules)}</textarea>
    </div></details>
    <details class="adv" open><summary>امنیت ورود (کپچا)</summary><div class="box">
      <label class="chk"><input type="checkbox" id="m-cp"${m.captcha?.on ? " checked" : ""}> عضو جدید تا زدن دکمه ساکت باشد</label>
      <span class="lbl">مهلت (دقیقه؛ بعدش اخراج می‌شود)</span><input class="ltr" id="m-cpm" inputmode="numeric" value="${esc(m.captcha?.mins ?? 3)}">
    </div></details>
    <details class="adv" open><summary>قفل‌ها و ممنوعیت‌ها</summary><div class="box">
      <p class="muted" style="margin-bottom:8px">این نوع پیام‌ها از اعضای عادی پاک می‌شود. مدیرها همیشه آزادند.</p>
      ${Object.keys(MOD_LK).map(k => box("m-lk", k, (m.lock || []).includes(k))).join("")}
      <span class="lbl">کلمات ممنوع (با خط جدید یا ویرگول جدا کن)</span><textarea class="fa" id="m-wo" maxlength="2000" style="min-height:60px">${esc((m.words || []).join("\n"))}</textarea>
      <span class="lbl">ضد اسپم: بیشتر از (تعداد) پیام در (ثانیه)؛ تعداد ۰ = خاموش</span>
      <div class="cmd"><input class="ltr" id="m-fn" inputmode="numeric" value="${esc(m.flood?.n ?? 0)}" aria-label="تعداد پیام"><input class="ltr" id="m-fs" inputmode="numeric" value="${esc(m.flood?.secs ?? 8)}" aria-label="ثانیه"></div>
    </div></details>
    <details class="adv"><summary>مجازات و اخطار</summary><div class="box">
      <span class="lbl">وقتی عضوی قفل یا کلمه‌ی ممنوع را رعایت نکند</span>
      <select id="m-ac">${sel(m.action || "warn", {warn: "پیام پاک شود و اخطار بگیرد", mute: "پیام پاک شود و ساکت شود", delete: "فقط پیام پاک شود"})}</select>
      <span class="lbl">حداکثر اخطار</span><input class="ltr" id="m-wm" inputmode="numeric" value="${esc(w.max ?? 3)}">
      <span class="lbl">بعد از رسیدن به سقف</span><select id="m-wt">${sel(w.then || "mute", {mute: "ساکت شود", ban: "بن شود", kick: "اخراج شود"})}</select>
      <span class="lbl">مدت سکوت (دقیقه)</span><input class="ltr" id="m-wmin" inputmode="numeric" value="${esc(w.mins ?? 60)}">
    </div></details>
    <details class="adv"><summary>تمیزکاری</summary><div class="box">
      ${Object.keys(MOD_CL).map(k => box("m-cl", k, (m.clean || []).includes(k))).join("")}
      <label class="chk"><input type="checkbox" id="m-rp"${m.report !== false ? " checked" : ""}> اعضا بتوانند با /report پیام را به مدیران گزارش بدهند</label>
    </div></details>
    <details class="adv"${ch.id ? " open" : ""}><summary>کانال</summary><div class="box">
      <p class="muted" style="margin-bottom:8px">ربات باید ادمین کانال باشد. زیر هر پست جدید دکمه می‌گذارد و واکنش می‌زند. برای انتشار از خود ربات: در چت ربات روی هر پیام ریپلای کن و <b dir="ltr">/post</b> یا <b dir="ltr">/post 30</b> (۳۰ دقیقه‌ی بعد) بنویس.</p>
      <span class="lbl">آیدی کانال</span><input class="ltr" id="m-ci" value="${esc(ch.id || "")}" placeholder="@mychannel یا -1001234567890" autocomplete="off">
      <span class="lbl">دکمه‌ی زیر پست‌ها (متن و لینک؛ اختیاری)</span>
      <div class="cmd"><input class="fa" id="m-bt" maxlength="30" value="${esc(bt.text || "")}" placeholder="متن دکمه"><input class="ltr" id="m-bu" value="${esc(bt.url || "")}" placeholder="https://t.me/..." autocomplete="off"></div>
      <span class="lbl">واکنش خودکار (یک ایموجی؛ اختیاری)</span><input class="ltr" id="m-re" maxlength="8" value="${esc(ch.react || "")}" placeholder="👍">
    </div></details>
    <div class="bar"><button class="b" data-sh="save">ذخیره</button></div>`;
}
function readMod(){
  if(!$("#m-on")) return;
  const g = id => $("#" + id)?.value ?? "", n = id => parseInt(String(g(id)).replace(/[۰-۹]/g, c => "۰۱۲۳۴۵۶۷۸۹".indexOf(c)), 10);
  D.on = $("#m-on").checked;
  D.m = {welcome: g("m-w").trim(), welcome_del: n("m-wd") || 0, goodbye: g("m-g").trim(), rules: g("m-r").trim(),
    captcha: $("#m-cp").checked ? {on: true, mins: n("m-cpm") || 3} : undefined,
    lock: [...document.querySelectorAll(".m-lk:checked")].map(x => x.value),
    words: g("m-wo").split(/[\n,،]+/).map(x => x.trim()).filter(Boolean),
    flood: n("m-fn") >= 2 ? {n: n("m-fn"), secs: n("m-fs") || 8} : undefined,
    action: g("m-ac"), warns: {max: n("m-wm") || 3, then: g("m-wt"), mins: n("m-wmin") || 60},
    clean: [...document.querySelectorAll(".m-cl:checked")].map(x => x.value), report: $("#m-rp").checked,
    channel: {id: g("m-ci").trim(), button: {text: g("m-bt").trim(), url: g("m-bu").trim()}, react: g("m-re").trim()}};
}
function saveMod(){
  const d = D;
  busy($('[data-sh="save"]'), () => commit(cfg => { if(d.on) cfg.mod = d.m; else delete cfg.mod; }, d.on ? "مدیریت گروه و کانال ذخیره شد" : "مدیریت خاموش شد"));
}
function openBot(){
  const cfg = S.cur.config, ref = cfg.on_ref?.find(a => a.op === "add");
  S.sheet = {kind: "bot"};
  D = { name: cfg.name, channels: (cfg.join?.channels || []).map(c => "@" + c).join(" "), jtext: cfg.join?.text || "",
        cmds: Object.entries(cfg.commands || {}), vars: Object.entries(cfg.vars || {}), globs: Object.entries(cfg.globals || {}),
        staff: (cfg.desk?.staff || []).join(" "), dclosed: cfg.desk?.closed || "", drbtn: cfg.desk?.reply_btn || "",
        refVar: ref?.var || "", refAmt: ref?.value || "", refText: cfg.ref_text || "" };
  renderSheet();
}
function botSheet(){
  const cfg = S.cur.config, d = D;
  return head("تنظیمات ربات") + `
    <span class="lbl">نام ربات</span><input class="fa" id="s-name" value="${esc(d.name)}" maxlength="50">
    ${d.channels ? `<span class="lbl">عضویت اجباری کل ربات</span>
    <input id="s-chs" value="${esc(d.channels)}" placeholder="@channel1 @channel2" autocomplete="off">
    <p class="muted mt">این قفلِ کل ربات است. برای قفل کردن فقط یک بخش یا دکمه، از ویرایش همان بخش یا دکمه استفاده کن. خالی کردن این فیلد قفل را برمی‌دارد.</p>
    <span class="lbl">پیام درخواست عضویت</span><textarea class="fa" id="s-jtext" data-fmt maxlength="500">${esc(d.jtext)}</textarea>${fmtTools("s-jtext")}` : ""}
    <div class="rowh"><span class="lbl">دستورها (مثل /help)</span>${d.cmds.length < 10 ? `<button class="b o sm" data-sh="addcmd">${IC.plus}دستور</button>` : ""}</div>
    <div class="fgap"></div>
    ${d.cmds.map(([k, v], i) => `<div class="cmd"><span>/</span><input class="cmdn" value="${esc(k)}" placeholder="help" maxlength="30" autocomplete="off"><select class="cmdv">${nodeOpts(cfg, v)}</select><button class="iconb sm" data-sh="delcmd" data-i="${i}" aria-label="حذف">${IC.x}</button></div>`).join("") || '<p class="muted">دستور اضافه‌ای نداری.</p>'}
    <div class="rowh"><span class="lbl">متغیرهای ربات</span>${d.vars.length < 40 ? `<button class="b o sm" data-sh="addvar">${IC.plus}متغیر</button>` : ""}</div>
    <p class="muted" style="margin:2px 0 8px">هر کاربر مقدار مخصوص خودش را دارد (مثل امتیاز یا شهر). اسم انگلیسی بده و مقدار شروع را بنویس.</p>
    ${d.vars.map(([k, v], i) => `<div class="cmd"><input class="vn" value="${esc(k)}" placeholder="coins" maxlength="20" autocomplete="off"><input class="fa vd" value="${esc(v)}" placeholder="مقدار شروع" maxlength="100"><button class="iconb sm" data-sh="delvar" data-i="${i}" aria-label="حذف">${IC.x}</button></div>`).join("") || '<p class="muted">متغیری تعریف نشده.</p>'}
    <div class="rowh"><span class="lbl">متغیرهای مشترک (بین همه‌ی کاربرها)</span>${d.globs.length < 20 ? `<button class="b o sm" data-sh="addglob">${IC.plus}مشترک</button>` : ""}</div>
    <p class="muted" style="margin:2px 0 8px">یک مقدار برای کل ربات: شمارنده‌ی رأی‌ها، موجودی محدود، هدف جمعیِ جامعه. مثل متغیر عادی در متن‌ها و اکشن‌ها استفاده می‌شود.</p>
    ${d.globs.map(([k, v], i) => `<div class="cmd"><input class="gn" value="${esc(k)}" placeholder="stock" maxlength="20" autocomplete="off"><input class="fa gd" value="${esc(v)}" placeholder="مقدار شروع" maxlength="100"><button class="iconb sm" data-sh="delglob" data-i="${i}" aria-label="حذف">${IC.x}</button></div>`).join("") || '<p class="muted">متغیر مشترکی تعریف نشده.</p>'}
    <details class="adv"${d.staff || d.dclosed || d.drbtn ? " open" : ""}><summary>پشتیبانی و تیکت</summary><div class="box">
      <p class="muted" style="margin-bottom:8px">تیکت‌ها همیشه برای خودت می‌آیند. اگه می‌خوای همکارها هم ببینند و جواب بدهند، آیدی عددی تلگرامشان را بنویس (تا ${N(5)} نفر، با فاصله).</p>
      <span class="lbl">آیدی عددی پشتیبان‌ها</span><input class="ltr" id="s-staff" value="${esc(d.staff)}" placeholder="123456789 987654321" inputmode="numeric" autocomplete="off">
      <span class="lbl">پیام بسته شدن تیکت (می‌تواند {ticket_no} داشته باشد)</span><input class="fa" id="s-dclosed" value="${esc(d.dclosed)}" maxlength="300" placeholder="تیکت #{ticket_no} بسته شد.">
      <span class="lbl">متن دکمه‌ی پاسخ کاربر</span><input class="fa" id="s-drbtn" value="${esc(d.drbtn)}" maxlength="30" placeholder="پاسخ به پشتیبانی">
    </div></details>
    <details class="adv"${d.refVar ? " open" : ""}><summary>پاداش دعوت</summary><div class="box">
      <p class="muted" style="margin-bottom:8px">وقتی کسی با لینک دعوتِ یکی از کاربرهای ربات تو وارد شود، آن کاربر (دعوت‌کننده) این مقدار را می‌گیرد. لینک و تعداد دعوت‌ها با <b dir="ltr">{ref_link}</b> و <b dir="ltr">{refs}</b> در متن‌ها قابل نمایش است.</p>
      <div class="cmd"><input class="ltr" id="s-rv" list="vdl" value="${esc(d.refVar)}" placeholder="متغیر (مثلاً coins)" maxlength="20" autocomplete="off"><input id="s-ra" value="${esc(d.refAmt)}" placeholder="مقدار (مثلاً 5)" maxlength="10" inputmode="numeric"></div>
      <span class="lbl">پیام برای دعوت‌کننده (اختیاری)</span><input class="fa" id="s-rt" data-fmt value="${esc(d.refText)}" maxlength="500" placeholder="یک نفر با لینک تو آمد. سکه‌های تو: {coins}">${fmtTools("s-rt")}
      <p class="muted mt">برای هر کاربر فقط وقتی حساب می‌شود که برای اولین بار ربات را استارت کند.</p>
    </div></details>
    <details class="adv"><summary>متغیرهای آماده‌ی تلگرام</summary><div class="box">
      <p class="muted" style="margin-bottom:8px">در متن‌ها و شرط‌ها قابل استفاده‌اند؛ مثلاً <b dir="ltr">{name}</b>. اگر خالی بود می‌توانی جایگزین بگذاری: <b dir="ltr">{username|بدون آیدی}</b></p>
      ${BUILTIN_HELP.map(([k, l]) => `<div class="kvr"><code dir="ltr">{${k}}</code><span>${l}</span></div>`).join("")}
    </div></details>${dlist()}
    <div class="bar"><button class="b" data-sh="save">ذخیره</button></div>`;
}
function readBot(){
  D.name = $("#s-name")?.value ?? D.name; D.channels = $("#s-chs")?.value ?? D.channels; D.jtext = $("#s-jtext")?.value ?? D.jtext;
  const ns = [...document.querySelectorAll(".cmdn")], vs = [...document.querySelectorAll(".cmdv")];
  if(ns.length || document.querySelector("#s-name")) D.cmds = ns.map((n, i) => [n.value, vs[i].value]);
  if(document.querySelector("#s-name")){
    const vn = [...document.querySelectorAll(".vn")], vd = [...document.querySelectorAll(".vd")];
    D.vars = vn.map((n, i) => [cleanVar(n.value), vd[i].value]);
    D.globs = [...document.querySelectorAll(".gn")].map((n, i) => [cleanVar(n.value), document.querySelectorAll(".gd")[i].value]);
    D.staff = $("#s-staff")?.value ?? D.staff; D.dclosed = $("#s-dclosed")?.value ?? D.dclosed; D.drbtn = $("#s-drbtn")?.value ?? D.drbtn;
    D.refVar = cleanVar($("#s-rv")?.value ?? D.refVar); D.refAmt = $("#s-ra")?.value ?? D.refAmt; D.refText = $("#s-rt")?.value ?? D.refText;
  }
}
function saveBot(){
  const d = D, chs = d.channels.split(/[\s,،]+/).filter(Boolean);
  const amt = String(d.refAmt).trim();
  if(d.refVar && !/^-?\d+(\.\d+)?$/.test(amt)) return toast("مقدار پاداش دعوت باید عدد باشد");
  const staff = d.staff.split(/[\s,،]+/).filter(Boolean).map(x => x.replace(/[۰-۹]/g, c => "۰۱۲۳۴۵۶۷۸۹".indexOf(c)));
  if(staff.some(x => !/^\d{5,15}$/.test(x)) || staff.length > 5) return toast("آیدی پشتیبان‌ها باید عددی باشد (حداکثر ۵ نفر)");
  const gnames = d.globs.map(g => g[0]).filter(Boolean);
  if(new Set(gnames).size !== gnames.length || gnames.some(g => d.vars.some(v => v[0] === g) || BUILTIN.includes(g))) return toast("اسم متغیر مشترک نباید تکراری یا هم‌نام متغیرهای دیگر باشد");
  busy($('[data-sh="save"]'), () => commit(cfg => {
    cfg.name = d.name.trim() || "ربات من";
    if(chs.length) cfg.join = {channels: chs, text: d.jtext.trim()}; else delete cfg.join;
    cfg.commands = {};
    d.cmds.forEach(([k, v]) => { k = k.trim().replace(/^\//, "").toLowerCase(); if(k) cfg.commands[k] = v; });
    const vars = {};
    d.vars.forEach(([k, v]) => { if(k) vars[k] = v.trim(); });
    if(d.refVar && !(d.refVar in vars)) vars[d.refVar] = "0";
    if(Object.keys(vars).length) cfg.vars = vars; else delete cfg.vars;
    const gl = {}; d.globs.forEach(([k, v]) => { if(k) gl[k] = v.trim(); });
    if(Object.keys(gl).length) cfg.globals = gl; else delete cfg.globals;
    const dk = {}; if(staff.length) dk.staff = staff.map(Number); if(d.dclosed.trim()) dk.closed = d.dclosed.trim(); if(d.drbtn.trim()) dk.reply_btn = d.drbtn.trim();
    if(Object.keys(dk).length) cfg.desk = dk; else delete cfg.desk;
    if(d.refVar){ cfg.on_ref = [{op: "add", var: d.refVar, value: amt}]; } else delete cfg.on_ref;
    if(d.refText.trim()) cfg.ref_text = d.refText.trim(); else delete cfg.ref_text;
  }));
}

/* ── رسانه، پیام همگانی و خرید ── */
function openMedia(id){ const m = mediaById(id); if(!m) return; S.sheet = {kind: "media", id}; D = {name: m.name}; renderSheet(); }
function mediaSheet(){
  const m = mediaById(S.sheet.id);
  return head("رسانه") + ((m.kind === "photo" || m.kind === "animation") ? `<img class="prev" src="${API_BASE + esc(m.url)}" alt="">` : `<div class="prevbox">${IC[m.kind] || IC.document}</div>`) + `
    <span class="muted">${KIND_FA[m.kind]}، ${sizeHTML(m.size)}</span>
    <span class="lbl">اسم فایل (هوش مصنوعی از روی اسم می‌فهمد کجا بگذارتش)</span><input class="fa" id="m-name" value="${esc(D.name)}" maxlength="80">
    <div class="bar"><button class="b" data-sh="save">ذخیره</button><button class="b r" data-sh="del">حذف</button></div>`;
}
const readMedia = () => { D.name = $("#m-name")?.value ?? D.name; };
function saveMedia(){
  const id = S.sheet.id;
  if(!D.name.trim()) return toast("اسم فایل نباید خالی باشد");
  busy($('[data-sh="save"]'), async () => { const d = await api(`/api/media/${id}`, "PUT", {name: D.name.trim()}); Object.assign(mediaById(id), d.item); closeSheet(); render(); toast("ذخیره شد"); });
}
function delMedia(){
  const id = S.sheet.id, q = "این فایل برای همیشه پاک شود؟ بخش‌هایی که از آن استفاده می‌کنند بدون رسانه نمایش داده می‌شوند.";
  const go = ok => ok && busy($('[data-sh="del"]'), async () => { const d = await api(`/api/media/${id}`, "DELETE"); S.media = S.media.filter(m => m.id !== id); S.used = d.used; closeSheet(); render(); toast("فایل پاک شد"); });
  confirmQ(q, go);
}
function openBc(){ S.sheet = {kind: "bc"}; D = {text: "", media: "", fmt: "html"}; renderSheet(); }
function bcSheet(){
  const live = S.stats ? Math.max(0, S.stats.users - S.stats.blocked) : 0, per = S.cfg.bc_per, cost = Math.max(1, Math.ceil(live / per));
  return head("پیام همگانی") + `<p class="muted">این پیام برای همه‌ی کاربرهای ربات فرستاده می‌شود. الان ${N(live)} مخاطب فعال داری.</p>
    <span class="lbl">متن پیام</span><textarea class="fa" id="bc-text" maxlength="3500" placeholder="متن اطلاعیه">${esc(D.text)}</textarea>
    <div style="display:flex;margin-top:6px">${cpFmtSel("bc", D.fmt)}</div>${cpTools("bc", D.fmt === "html")}
    <span class="lbl">رسانه (اختیاری)</span>${mediaPicker("media", D.media)}
    <p class="muted mt">هزینه: ${N(cost)} توکن (هر ${N(per)} نفر ${N(1)} توکن). موجودی تو ${N(S.wallet.tokens)} توکن است.</p>
    <div class="bar"><button class="b" data-sh="save">${IC.mega}ارسال</button></div>`;
}
const readBc = () => { D.text = $("#bc-text")?.value ?? D.text; D.fmt = $("#bc-fmt")?.value ?? D.fmt; };
function saveBc(){
  if(!D.text.trim() && !D.media) return toast("متن یا رسانه‌ی پیام را وارد کن");
  const go = ok => ok && busy($('[data-sh="save"]'), async () => {
    try{
      const d = await api(`/api/bots/${S.cur.id}/broadcast`, "POST", {text: D.text.trim(), media: D.media, fmt: D.fmt === "html" ? "html" : "text"});
      S.wallet = d.wallet; renderTop(); closeSheet(); toast(`ارسال برای ${d.queued} نفر شروع شد. وقتی تمام شود خبرت می‌کنم`); haptic("ok");
    }catch(e){ if(e.status === 402){ closeSheet(); openBuy(e.message); } else throw e; }
  });
  confirmQ("این پیام برای همه‌ی کاربرها فرستاده شود؟", go);
}
function buySheet(){
  const m = S.sheet.msg, w = S.wallet, c = S.cfg;
  return head("توکن بیشتر") + `${m ? `<p class="muted" style="margin-bottom:12px">${digitsHTML(m)}</p>` : ""}
    ${w.can_claim ? `<div class="daily" style="margin:0 0 12px"><div class="dt"><b>پاداش امروزتو نگرفتی ! است</b>${N("+" + w.next_reward)} توکن</div><button class="b amber sm" data-a="daily">دریافت</button></div>` : ""}
    <div class="group">${packRows() || '<div class="gi static"><span class="muted">فعلاً بسته‌ای تعریف نشده.</span></div>'}</div>
    ${S.ref.link ? `<button class="b o mt" data-a="shareref">${IC.users}دعوت دوستان، ${N("+" + c.ref_inviter)} توکن برای هر نفر</button>` : ""}
    <div class="fgap"></div>`;
}
function cardSheet(){
  const o = S.sheet.o || {}, row = (l, v, raw) => {
    if(v == null || v === "") return "";
    return `<div class="cdrow"><div><span class="muted">${l}</span><div class="cdv">${v}</div></div>${raw ? `<button class="b o sm" data-a="cardcopy" data-v="${esc(raw)}">کپی</button>` : ""}</div>`;
  };
  const num = row("مبلغ قابل پرداخت", (o.toman ? N(Number(o.toman).toLocaleString("en")) + " تومان" : ""), o.toman);
  const crd = row("شماره کارت", o.number || "", o.raw);
  const hld = row("به نام", o.holder || "");
  const bnk = row("بانک", o.bank || "");
  const note = o.text ? `<div class="fjt cdnote">${tgHtml(o.text)}</div>` : "";
  const title = o.ptitle ? `اشتراک ${esc(o.ptitle)}` : `${N(o.tokens || 0)} توکن`;
  return head("پرداخت کارت‌به‌کارت") + `<div class="cardbox">${num}${crd}${hld}${bnk}</div>
    ${note}
    <button class="b" data-a="cardrcpt">ارسال رسید</button>
    <p class="muted mt">سفارش ${N("#" + (o.order || ""))} · ${title}</p><div class="fgap"></div>`;
}
function openBuy(msg){ S.sheet = {kind: "buy", msg}; D = null; renderSheet(); }
async function refreshWallet(waitInc){
  const t0 = S.wallet.tokens;
  for(let i = 0; i < (waitInc ? 8 : 1); i++){
    await sleep(i ? 1500 : 700);
    try{ const d = await api("/api/me"); S.wallet = d.wallet; S.ref = d.ref; }catch(_){}
    renderTop();
    if(!waitInc || S.wallet.tokens > t0) break;
  }
  if(S.sheet?.kind === "buy") closeSheet();
  if(S.view === "create" || S.view === "account") render();
}
async function buyPack(id, btn){
  busy(btn, async () => {
    const d = await api("/api/buy", "POST", { pack: id });
    if(tg?.openInvoice) tg.openInvoice(d.url, st => {
      if(st === "paid"){ toast("پرداخت انجام شد"); refreshWallet(true); }
      else if(st === "failed") toast("پرداخت ناموفق بود");
    }); else window.open(d.url, "_blank");
  });
}
async function subPlan(id, btn){
  busy(btn, async () => {
    const d = await api("/api/subscribe", "POST", { plan: id });
    const done = async () => { try{ takeMe(await api("/api/me")); }catch(_){} render(); toast("اشتراک فعال شد"); haptic("ok"); };
    if(tg?.openInvoice) tg.openInvoice(d.url, st => {
      if(st === "paid") done();
      else if(st === "failed") toast("پرداخت ناموفق بود");
    }); else { window.open(d.url, "_blank"); toast("بعد از پرداخت، صفحه را تازه کن"); }
  });
}

/* ── هماهنگی شیت‌ها ── */
const SHEETS = {
  node:  {html: nodeSheet,  read: readNode,  save: saveNode,  del: delNode},
  btn:   {html: btnSheet,   read: readBtn,   save: saveBtn,   del: delBtn},
  bot:   {html: botSheet,   read: readBot,   save: saveBot},
  mod:   {html: modSheet,   read: readMod,   save: saveMod},
  media: {html: mediaSheet, read: readMedia, save: saveMedia, del: delMedia},
  bc:    {html: bcSheet,    read: readBc,    save: saveBc},
  buy:   {html: buySheet},
  card:  {html: cardSheet},
  km:    {html: kmSheet},
};
function renderSheet(){ showSheet(SHEETS[S.sheet.kind].html()); }
function readSheet(){ SHEETS[S.sheet?.kind]?.read?.(); }

function shAction(a, ds){
  if(!S.sheet) return;
  const prev = D?.kind;
  readSheet();
  if(a.startsWith("km")) return kmAct(a, ds);
  if(a.startsWith("ub")) return ubAct(a, ds);
  if(a === "stkm"){ const n = ds.n; return stGuardClose(() => { closeSheet(); openKm(n); }); }
  if(a === "stsetstart"){ const n = ds.n; closeSheet(); return busy(null, () => commit(cfg => { cfg.start = n; }, "حالا ربات از این بخش شروع می‌شود")); }
  if(a === "save") return SHEETS[S.sheet.kind].save();
  if(a === "del") return SHEETS[S.sheet.kind].del();
  if(a === "upmedia"){ S.pickKey = ds.k; return $("#fileIn").click(); }
  if(a === "stedit"){ const n = ds.n; closeSheet(); openNode(n); return; }
  if(a === "stcopy"){ closeSheet(); return stCopy(ds.n); }
  if(a === "stcenter"){ closeSheet(); return stCenter(ds.n); }
  if(a === "stdel"){ const n = ds.n; closeSheet(); S.sheet = {kind: "node", id: n}; return delNode(); }
  if(a === "stwe" || a === "stwr"){ const ed = ST.wires.get(ds.k); closeSheet(); if(!ed) return; return ed.kind === "route" || ed.kind === "next" ? openNode(ed.n) : openBtn(ed.n, ed.r, ed.c); }
  if(a === "stwx"){ const ed = ST.wires.get(ds.k); closeSheet(); if(!ed) return; S.sheet = {kind: "btn", n: ed.n, r: ed.r, c: ed.c}; return delBtn(); }
  if(a === "stwrx"){ const ed = ST.wires.get(ds.k); closeSheet(); if(!ed) return;
    return busy(null, () => commit(cfg => { const n = cfg.nodes[ed.n]; if(n?.route){ n.route.splice(ed.ri, 1); if(!n.route.length) delete n.route; } }, "قانون حذف شد")); }
  if(a === "stnx"){ const ed = ST.wires.get(ds.k); closeSheet(); if(!ed) return;
    return busy(null, () => commit(cfg => { const n = cfg.nodes[ed.n]; if(n) delete n.next; }, "ادامه قطع شد")); }
  if(a === "pickmedia") D[ds.k] = ds.v;
  else if(a === "bkind"){
    const k = D.kind, wasText = prev === "channel" || prev === "url";
    if(k === "channel"){ const m = CH_RE.exec(D.val) || NAME_RE.exec(D.val); D.val = m ? "@" + m[1] : ""; }
    else if(k === "url"){ D.val = NAME_RE.test(D.val) ? "https://t.me/" + D.val.replace("@", "") : (wasText ? D.val : ""); }
    else if(k !== "goto" && prev !== k) D.val = "";
  }
  else if(a === "kbt") D.kb = ds.v;
  else if(a === "pickcolor") D.color = ds.v;
  else if(a === "addfld") D.fields.push({q: "", v: "", t: "text"});
  else if(a === "delfld") D.fields.splice(+ds.i, 1), D.fields.length || D.fields.push({q: "", v: "", t: "text"});
  else if(a === "addcmd") D.cmds.push(["help", S.cur.config.start]);
  else if(a === "delcmd") D.cmds.splice(+ds.i, 1);
  else if(a === "addvar") D.vars.push(["", ""]);
  else if(a === "delvar") D.vars.splice(+ds.i, 1);
  else if(a === "addglob") D.globs.push(["", ""]);
  else if(a === "delglob") D.globs.splice(+ds.i, 1);
  else if(a === "addrl"){ D[ds.l].push(newRule(ds.l)); D.adv = true; }
  else if(a === "delrl"){ D[ds.l].splice(+ds.i, 1); D.adv = true; }
  renderSheet();
}

/* ═════════ استودیو: ابزارهای تازه ═════════ */
/* کدام سیم زیر نقطه‌ی لمس است؟ (سیم‌ها بالای بخش‌ها رسم می‌شوند و لمس را نمی‌گیرند؛ تشخیص با هندسه) */
function stWireAt(e){
  const svg = $("#stsvg"); if(!svg || !svg.getScreenCTM) return null;
  const ctm = svg.getScreenCTM(); if(!ctm) return null;
  const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
  const p = pt.matrixTransform(ctm.inverse());
  for(const g of svg.querySelectorAll(".wire")){
    const h = g.querySelector(".w-hit");
    try{ if(h && h.isPointInStroke(p)) return ST.wires.get(g.dataset.w) || null; }catch(_){}
  }
  return null;
}
document.addEventListener("error", e => {
  const t = e.target, box = t && t.tagName === "IMG" && t.closest ? t.closest(".stc-media") : null;
  if(box) box.classList.add("bad");
}, true);

/* ── مدیریت دکمه‌ها و نوع کیبورد ── */
function openKm(id){ if(!S.cur?.config.nodes[id]) return; S.sheet = {kind: "km", id}; D = null; renderSheet(); }
function kmBtn(cfg, b, r, c, len){
  const k = kindOf(b), [lab, ic] = ST_KIND[k] || ST_KIND.url, tgt = k === "pay" ? b.pay?.goto : b.goto;
  const sub = k === "goto" ? "← " + esc(titleOf(cfg, tgt)) : k === "pay" ? `پرداخت ${N(b.pay.stars)} ستاره` + (tgt ? " ← " + esc(titleOf(cfg, tgt)) : "") : lab;
  const op = (act, ch, aria, off) => `<button class="iconb sm" data-sh="${act}" data-r="${r}" data-c="${c}" aria-label="${aria}"${off ? " disabled" : ""}>${ch}</button>`;
  return `<div class="km-b"><button class="km-t" data-sh="kmedit" data-r="${r}" data-c="${c}"><span class="ki">${ic}</span><span class="tt"><b>${esc(b.text)}</b><small>${sub}${b.kb === "reply" ? " · کیبورد" : " · شیشه‌ای"}${b.when ? " · شرطی" : ""}</small></span></button>
    <div class="km-ops">${op("kmr", "→", "یک جا جلوتر", c === 0)}${op("kml", "←", "یک جا عقب‌تر", c === len - 1)}${op("kmu", "↑", "به ردیف بالا", false)}${op("kmd", "↓", "به ردیف پایین", false)}${op("kmdel", IC.trash, "حذف دکمه", false)}</div></div>`;
}
function kmSheet(){
  const cfg = S.cur.config, id = S.sheet.id, n = cfg.nodes[id], rows = n.buttons || [];
  const total = rows.reduce((a, r) => a + r.length, 0), full = rows.length >= 6 && rows[rows.length - 1].length >= 3;
  const list = rows.length ? rows.map((row, r) => `<div class="km-row"><div class="km-cap">ردیف ${N(r + 1)}</div>${row.map((b, c) => kmBtn(cfg, b, r, c, row.length)).join("")}</div>`).join("")
    : `<div class="km-empty">این بخش هنوز دکمه‌ای ندارد.</div>`;
  return head("دکمه‌های «" + esc(titleOf(cfg, id)) + "»") + `
    <p class="muted" style="margin-bottom:4px">هر ردیف تا ${N(3)} دکمه و هر بخش تا ${N(6)} ردیف دارد. روی هر دکمه بزن تا ویرایشش کنی و با فلش‌ها جابه‌جایش کن.</p>
    <div class="sub"><span>${N(total)} دکمه</span><button class="b sm" data-sh="kmadd"${full ? " disabled" : ""}>${IC.plus}دکمه‌ی تازه</button></div>
    ${list}<div class="fgap"></div>`;
}
function kmMove(rows, r, c, dir){
  const tr = r + dir, alone = rows[r].length === 1;
  if(alone && (tr < 0 || tr >= rows.length)) return false;
  const b = rows[r][c];
  if(tr >= 0 && tr < rows.length){ if(rows[tr].length >= 3) return false; rows[r].splice(c, 1); rows[tr].push(b); }
  else { if(rows.length >= 6) return false; rows[r].splice(c, 1); if(dir < 0) rows.unshift([b]); else rows.push([b]); }
  for(let i = rows.length - 1; i >= 0; i--) if(!rows[i].length) rows.splice(i, 1);
  return true;
}
function kmAct(a, ds){
  const id = S.sheet.id, r = +ds.r, c = +ds.c, n = S.cur.config.nodes[id];
  const run = (fn, msg) => busy(null, async () => { await commit(fn, msg); openKm(id); });
  if(a === "kmadd"){ closeSheet(); return A.stbtn({dataset: {n: id}}); }
  if(a === "kmedit"){ closeSheet(); return openBtn(id, r, c); }
  if(a === "kmdel") return run(cfg => { const rows = cfg.nodes[id].buttons; rows[r].splice(c, 1); if(!rows[r].length) rows.splice(r, 1); }, "دکمه حذف شد");
  if(a === "kmr" || a === "kml"){
    const to = a === "kmr" ? c - 1 : c + 1;
    return run(cfg => { const row = cfg.nodes[id].buttons[r]; [row[c], row[to]] = [row[to], row[c]]; }, "جابه‌جا شد");
  }
  if(a === "kmu" || a === "kmd"){
    const dir = a === "kmu" ? -1 : 1;
    if(!kmMove(cp(n.buttons), r, c, dir)) return toast("آن طرف جا نیست؛ ردیف‌ها حداکثر ۳ دکمه دارند");
    return run(cfg => { kmMove(cfg.nodes[id].buttons, r, c, dir); }, "جابه‌جا شد");
  }
}

Object.assign(A, {
  stbtn: el => {
    if(!$("#stc")) return;
    const id = el.dataset.n, n = S.cur.config.nodes[id]; if(!n) return;
    const rows = n.buttons || [], last = rows.length - 1;
    if(rows.length >= 6 && rows[last].length >= 3) return toast("این بخش به حداکثر تعداد دکمه رسیده (۶ ردیف، هر ردیف ۳ دکمه)");
    openBtn(id, rows.length && rows[last].length < 3 ? last : null, null);
  },
  stkm: el => openKm(el.dataset.n),
});
/* ── شیت قانون ── */
function ubruleSheet(){
  const isNew = D.i === null;
  return head(isNew ? "قانون جدید" : "ویرایش قانون") + `
    <span class="lbl">کلمه‌های کلیدی (با کاما جدا کن)</span><input id="ur-kw" maxlength="300" placeholder="قیمت، تعرفه، چنده" value="${esc(D.kw)}">
    <span class="lbl">شرط تطبیق</span><select id="ur-mode">${UB_MODE.map(([k, t]) => `<option value="${k}"${D.mode === k ? " selected" : ""}>${t}</option>`).join("")}</select>
    <span class="lbl">متن پاسخ</span><textarea class="fa" id="ur-text" maxlength="1000" placeholder="متنی که فرستاده می‌شود">${esc(D.text)}</textarea>
    <p class="muted mt2">می‌توانی از <span class="ltr">{name}</span> و <span class="ltr">{time}</span> و <span class="ltr">{date}</span> استفاده کنی.</p>
    <label class="chk"><input type="checkbox" id="ur-on"${D.on ? " checked" : ""}> قانون فعال باشد</label>
    <div class="bar"><button class="b" data-sh="save">ذخیره</button>${isNew ? "" : `<button class="b r" data-sh="del">حذف</button>`}</div>`;
}
const ubruleRead = () => { D.kw = $("#ur-kw")?.value ?? D.kw; D.mode = $("#ur-mode")?.value ?? D.mode; D.text = $("#ur-text")?.value ?? D.text; D.on = $("#ur-on") ? $("#ur-on").checked : D.on; };
function ubruleSave(){
  const kw = D.kw.split(/[,،\n]/).map(s => s.trim()).filter(Boolean).slice(0, 8), text = D.text.trim();
  if(!kw.length) return toast("حداقل یک کلمه‌ی کلیدی بنویس");
  if(!text) return toast("متن پاسخ را بنویس");
  const rule = {kw, mode: D.mode, text, on: D.on}, i = D.i;
  busy($('[data-sh="save"]'), async () => { await ubCommit(cfg => { if(i === null) cfg.rules.push(rule); else cfg.rules[i] = rule; }, "قانون ذخیره شد"); closeSheet(); renderUserbot(); });
}
function ubruleDel(){
  const i = D.i;
  confirmQ("این قانون حذف شود؟", ok => ok && busy($('[data-sh="del"]'), async () => { await ubCommit(cfg => { cfg.rules.splice(i, 1); }, "قانون حذف شد"); closeSheet(); renderUserbot(); }));
}

/* ── شیت اتصال اکانت: شماره ← کد ← (رمز دومرحله‌ای) ← تمام ── */
function openUbConn(){
  if(S.ub?.locked) return toast("یوزربات مخصوص اشتراک پرو است");
  if(S.ub && S.ub.items.length >= S.ub.max && !S.ub.items.some(x => x.status === "revoked")) return toast(`حداکثر ${S.ub.max} یوزربات می‌توانی داشته باشی`);
  S.sheet = {kind: "ubconn"}; D = {step: "phone", phone: "", code: "", pw: "", aid: "", ah: "", item: null}; renderSheet();
}
function ubconnSheet(){
  const own = !!S.ub?.own_api;
  if(D.step === "phone") return head("اتصال اکانت تلگرام") + `
    <p class="muted">شماره‌ی اکانتی که می‌خواهی یوزربات رویش کار کند را با کد کشور بنویس. تلگرام یک کد ورود داخل خود اپ برایت می‌فرستد.</p>
    <span class="lbl">شماره‌ی تلفن</span><input id="uc-phone" dir="ltr" inputmode="tel" autocomplete="off" placeholder="+989121234567" value="${esc(D.phone)}">
    ${own ? `<span class="lbl">API ID</span><input id="uc-aid" dir="ltr" inputmode="numeric" autocomplete="off" value="${esc(D.aid)}">
      <span class="lbl">API Hash</span><input id="uc-ah" dir="ltr" autocomplete="off" value="${esc(D.ah)}">
      <p class="muted mt2">این دو مورد را از <span class="ltr">my.telegram.org</span> ← API development tools بگیر.</p>` : ""}
    <p class="muted mt2">اگر تلگرام نشان می‌دهد «ورود جدید» با نام <span class="ltr">Azadi Userbot</span>، همان خودِ توست. هر زمان بخواهی می‌توانی آن را ببندی.</p>
    <div class="bar" style="flex-direction:column"><button class="b" data-sh="ubsend">ارسال کد</button>${S.ub?.pending ? `<button class="b o" data-sh="ubresume">کد فرستاده شده را دارم</button>` : ""}</div>`;
  if(D.step === "code") return head("کد تلگرام") + `
    <p class="muted">کدی که تلگرام فرستاد (پیام رسمی «Telegram» توی اپ) را وارد کن. اگر مینی‌اپ بسته شد، دوباره باز کن؛ ورود تا ۱۰ دقیقه معتبر است. <b>این کد را برای هیچ‌کس نفرست.</b></p>
    <span class="lbl">کد ورود</span><input id="uc-code" dir="ltr" inputmode="numeric" maxlength="8" autocomplete="one-time-code" value="${esc(D.code)}">
    <div class="bar" style="flex-direction:column"><button class="b" data-sh="ubverify">تأیید</button><button class="b o" data-sh="ubstepback">شماره‌ی دیگر / ارسال دوباره</button></div>`;
  if(D.step === "password") return head("رمز دومرحله‌ای") + `
    <p class="muted">این اکانت رمز دومرحله‌ای دارد. رمز ذخیره نمی‌شود و فقط برای همین ورود استفاده می‌شود.</p>
    <span class="lbl">رمز</span><input id="uc-pw" type="password" autocomplete="off" value="">
    <div class="bar"><button class="b" data-sh="ubpwgo">ورود</button></div>`;
  const x = D.item;
  return head("اکانت وصل شد") + `<div class="empty" style="padding:18px 8px"><div class="ib big">${IC.check}</div><h2>${esc(x?.name || "اکانت تلگرام")}</h2>
    <p class="muted">یوزربات روشن است. حالا قابلیت‌هایش را تنظیم کن.</p><button class="b sm" data-sh="ubfinish">تنظیم یوزربات</button></div>`;
}
const ubconnRead = () => { if(D.step === "phone"){ D.phone = $("#uc-phone")?.value ?? D.phone; D.aid = $("#uc-aid")?.value ?? D.aid; D.ah = $("#uc-ah")?.value ?? D.ah; }
  if(D.step === "code") D.code = $("#uc-code")?.value ?? D.code; if(D.step === "password") D.pw = $("#uc-pw")?.value ?? D.pw; };
function ubDone(d){
  ubPut(d.item); S.ub.pending = false; D.step = "done"; D.item = d.item; renderSheet(); haptic("ok");
  if(d.warn) toast(d.warn);
}
function ubAct(a, ds){
  const fail = e => { if(e.data?.reset){ D.step = "phone"; renderSheet(); } toast(e.message); };
  const run = fn => busy($(`[data-sh="${a}"]`), async () => { try{ await fn(); }catch(e){ fail(e); } });
  if(a === "ubsend"){
    if(!D.phone.trim()) return toast("شماره‌ی تلفن را بنویس");
    return run(async () => { await api("/api/userbots/login/start", "POST", {phone: D.phone, api_id: D.aid, api_hash: D.ah}); S.ub.pending = true; D.step = "code"; D.code = ""; renderSheet(); });
  }
  if(a === "ubresume"){ D.step = "code"; return renderSheet(); }
  if(a === "ubverify"){
    if(!D.code.trim()) return toast("کد را وارد کن");
    return run(async () => { const d = await api("/api/userbots/login/code", "POST", {code: D.code}); if(d.step === "password"){ D.step = "password"; renderSheet(); } else ubDone(d); });
  }
  if(a === "ubpwgo"){
    if(!D.pw) return toast("رمز را وارد کن");
    return run(async () => { const d = await api("/api/userbots/login/password", "POST", {password: D.pw}); ubDone(d); });
  }
  if(a === "ubstepback"){ api("/api/userbots/login/cancel", "POST").catch(() => {}); S.ub.pending = false; D.step = "phone"; return renderSheet(); }
  if(a === "ubfinish"){ const id = D.item?.id; closeSheet(); S.view = "userbot"; if(id) ubOpen(id); else renderUserbot(); return; }
}
SHEETS.ubrule = {html: ubruleSheet, read: ubruleRead, save: ubruleSave, del: ubruleDel};
SHEETS.ubconn = {html: ubconnSheet, read: ubconnRead};

/* ثبت صفحه‌ی استودیو در جدول صفحه‌ها (VIEWS در app.js تعریف می‌شود) */
VIEWS.studio = renderStudio;
