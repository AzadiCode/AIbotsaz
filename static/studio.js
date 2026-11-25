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
  /* دنیای بی‌نهایت ممنوع: هر ستونِ بلند به چند ستونِ کوتاه (حداکثر PER بخش) شکسته می‌شود و اگر ستون‌ها از MAXL بیشتر شدند،
     نقشه مثل خط‌های متن به نوار بعدی (زیر نوار قبلی) می‌پیچد. نتیجه: نقشه‌ی جمع‌وجور، قابل نمایش و سبک حتی با ۶۰ بخش */
  const DW = ST_W + ST_GAP, GAP = 52, PER = 5, MAXL = 6;
  const cmp = (a, b) => ((a.b === null) - (b.b === null)) || ((a.b ?? 0) - (b.b ?? 0)) || (a.i - b.i);
  const order = Object.keys(cols).map(Number).sort((a, b) => a - b), minC = order.length ? order[0] : 0;
  const cy = {}, band = {};
  let lane = minC, curBand = 0, bandTop = 40, maxBottom = 40;
  for(const c of order){
    const raw = cols[c].map((id, i) => {
      const ps = (parents[id] || []).filter(p => cy[p] !== undefined);
      return {id, i, b: ps.length ? ps.reduce((a, p) => a + cy[p], 0) / ps.length : null};
    });
    raw.sort(cmp);
    const k = Math.max(1, Math.ceil(raw.length / PER)), size = Math.max(1, Math.ceil(raw.length / k));
    for(let s0 = 0; s0 < raw.length; s0 += size, lane++){
      const L = lane - minC, bd = Math.floor(L / MAXL);
      if(bd !== curBand){ curBand = bd; bandTop = maxBottom + 150; }
      const chunk = raw.slice(s0, s0 + size).map(it => {
        const ps = (parents[it.id] || []).filter(p => cy[p] !== undefined && band[p] === bd);
        return {id: it.id, i: it.i, b: ps.length ? ps.reduce((a, p) => a + cy[p], 0) / ps.length : null};
      });
      chunk.sort(cmp);
      let cur = bandTop;
      for(const it of chunk){
        const h = stH(it.id), y = it.b === null ? cur : Math.max(cur, it.b - h / 2);
        ST.pos[it.id] = {x: -(minC + (L % MAXL)) * DW, y: Math.round(y)};
        cy[it.id] = y + h / 2; band[it.id] = bd; cur = y + h + GAP; maxBottom = Math.max(maxBottom, cur);
      }
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
/* در حین حرکت دوربین، کلاس st-moving روی html می‌نشیند تا انیمیشن‌ها و بلورِ پس‌زمینه موقتاً بخوابند و تمام توان صرف حرکت نرم شود */
function stMovePulse(){
  ST._mat = performance.now();
  if(ST._mv) return;
  ST._mv = 1; document.documentElement.classList.add("st-moving");
  ST._mt = setTimeout(stMoveChk, 200);
}
function stMoveChk(){
  if(performance.now() - ST._mat < 180){ ST._mt = setTimeout(stMoveChk, 100); return; }
  ST._mv = 0; document.documentElement.classList.remove("st-moving");
}
function stApply(glide){
  const c = ST.cam || {x: 40, y: 40, z: 1}, w = (ST.w && ST.w.isConnected) ? ST.w : (ST.w = $("#stw"));
  if(w){
    if(glide && !reduced()){ w.classList.add("glide"); clearTimeout(ST._gt); ST._gt = setTimeout(() => w.classList.remove("glide"), 460); }
    else if(w.classList.contains("glide")){ w.classList.remove("glide"); clearTimeout(ST._gt); }
    w.style.transform = `translate(${c.x}px,${c.y}px) scale(${c.z})`;
    const was = w.classList.contains("far"), far = was ? c.z < .5 : c.z < .42;     // فاصله‌ی دو آستانه: دیگر روی مرز زوم پرپر نمی‌زند
    if(far !== was) w.classList.toggle("far", far);
  }
  const zt = Math.round(c.z * 100) + "%", z = $("#stz"); if(z && z.textContent !== zt) z.textContent = zt;
  stMovePulse();
  if(!ST._mr) ST._mr = requestAnimationFrame(() => { ST._mr = 0; stMini(); stCull(); });
}
/* عکس‌های بزرگ (چند مگاپیکسل) نباید برای ۲۵+ کارت هم‌زمان decode شوند؛ حافظه‌ی WebView تلگرام پر می‌شود و برنامه کرش می‌کند.
   هر عکس فقط یک‌بار (پشت‌سرهم) به نسخه‌ی ۶۴۰پیکسلی تبدیل می‌شود و فقط کارت‌های دیده‌شده (با زوم خوانا) آن را نشان می‌دهند. */
const ST_TH = new Map(), ST_THQ = []; let ST_THN = 0;
function stThumb(url){
  let p = ST_TH.get(url); if(p) return p;
  p = new Promise(res => { ST_THQ.push([url, res]); stThumbPump(); });
  ST_TH.set(url, p); return p;
}
function stThumbPump(){
  while(ST_THN < 2 && ST_THQ.length){
    const [url, res] = ST_THQ.shift(); ST_THN++;
    (async () => {
      try{
        const r = await fetch(url); if(!r.ok) throw 0;
        const bm = await createImageBitmap(await r.blob(), {resizeWidth: 640, resizeQuality: "medium"});
        const cv = document.createElement("canvas"); cv.width = bm.width; cv.height = bm.height;
        cv.getContext("2d").drawImage(bm, 0, 0); bm.close?.();
        const b = await new Promise(ok => cv.toBlob(ok, "image/jpeg", .82));
        cv.width = cv.height = 0;
        res(b ? URL.createObjectURL(b) : url);
      }catch(_){ res(url); }        // نشد: همان آدرس اصلی (باز هم فقط برای کارت‌های دیده‌شده)
      finally{ ST_THN--; stThumbPump(); }
    })();
  }
}
function stImgSet(el, on){
  el.querySelectorAll("img[data-src]").forEach(im => {
    if(on){
      if(im._on) return; im._on = 1;
      stThumb(im.dataset.src).then(u => { if(im._on && im.isConnected && im.getAttribute("src") !== u) im.src = u; });
    }else if(im._on){ im._on = 0; im.removeAttribute("src"); }
  });
}
/* فقط بخش‌هایی که در کادر دید (به‌علاوه‌ی حاشیه) هستند کشیده می‌شوند؛ بقیه visibility:hidden می‌شوند و هزینه‌ی رسم ندارند */
function stCull(){
  if(!ST.els || !S.cur) return;
  const many = ST.els.size > 8, c = ST.cam || {x: 40, y: 40, z: 1}, m = 380, sharp = c.z >= .45;
  const vw = ST.vw || innerWidth, vh = ST.vh || innerHeight;
  const x1 = (-m - c.x) / c.z, x2 = (vw + m - c.x) / c.z, y1 = (-m - c.y) / c.z, y2 = (vh + m - c.y) / c.z;
  for(const [id, el] of ST.els){
    const p = ST.pos[id]; if(!p) continue;
    let hide = false;
    if(many && !(ST.mode && ST.mode.id === id)){
      const z = ST.size[id], w = z ? z.w : ST_W, h = z ? z.h : stCardH(S.cur.config.nodes[id] || {});
      hide = !(p.x < x2 && p.x + w > x1 && p.y < y2 && p.y + h > y1);
    }
    if(el._cv !== hide){ el._cv = hide; el.classList.toggle("cv", hide); }
    const want = !hide && sharp;
    if(el._im !== want){ el._im = want; stImgSet(el, want); }
  }
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
    const zs = ST.size[id], w = zs ? zs.w : ST_W, h = zs ? zs.h : stCardH(S.cur.config.nodes[id]);
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
/* مسیریاب: راهروهای عمودیِ همیشه‌خالی (فاصله‌ی بین ستون‌های بخش‌ها) + کانال‌های افقیِ خالی بین بخش‌ها.
   روی این شبکه کوتاه‌ترین مسیر با کمترین پیچ (Dijkstra) پیدا می‌شود؛ پس سیم هیچ‌وقت روی بخشی نمی‌افتد، حتی با ۱۰۰ بخش. */
function stRouterBuild(rects){
  const M = 14, iv = rects.map(r => [r.x - M, r.x + r.w + M]).sort((a, b) => a[0] - b[0]), mg = [];
  for(const v of iv){ const l = mg[mg.length - 1]; if(l && v[0] <= l[1]) l[1] = Math.max(l[1], v[1]); else mg.push([v[0], v[1]]); }
  if(!mg.length) return null;
  const cx = [mg[0][0] - 34], hw = [30];
  for(let i = 0; i + 1 < mg.length; i++){ const w = mg[i + 1][0] - mg[i][1]; if(w >= 18){ cx.push((mg[i][1] + mg[i + 1][0]) / 2); hw.push(w / 2); } }
  cx.push(mg[mg.length - 1][1] + 34); hw.push(30);
  const base = new Set();
  for(const r of rects){ base.add(Math.round(r.y - 26)); base.add(Math.round(r.y + r.h + 26)); }
  const seg = [];
  for(let k = 0; k + 1 < cx.length; k++) seg.push(rects.filter(r => r.x + r.w > cx[k] && r.x < cx[k + 1]));
  return {cx, hw, base: [...base], seg};
}
function stHeapPush(h, it){ h.push(it); let i = h.length - 1; while(i > 0){ const p = (i - 1) >> 1; if(h[p][0] <= h[i][0]) break; [h[p], h[i]] = [h[i], h[p]]; i = p; } }
function stHeapPop(h){
  const top = h[0], last = h.pop();
  if(h.length){ h[0] = last; let i = 0; for(;;){ let l = 2 * i + 1, r = l + 1, m = i; if(l < h.length && h[l][0] < h[m][0]) m = l; if(r < h.length && h[r][0] < h[m][0]) m = r; if(m === i) break; [h[m], h[i]] = [h[i], h[m]]; i = m; } }
  return top;
}
function stRoute(e, idx, rects){
  const A = stPortPos(e.key), B = stInPos(e.to);
  if(!A || !B) return null;
  const rt = rects.rt || (rects.rt = stRouterBuild(rects));
  if(!rt) return null;
  const {cx, hw, seg} = rt, C = cx.length, TURN = 46;
  const ys = [...new Set([...rt.base, Math.round(A.y), Math.round(B.y)])].sort((a, b) => a - b), Y = ys.length;
  const iA = ys.indexOf(Math.round(A.y)), iB = ys.indexOf(Math.round(B.y));
  const free = (k, y, skip) => { for(const r of seg[k]) if(r.id !== skip[0] && r.id !== skip[1] && y > r.y - 10 && y < r.y + r.h + 10) return false; return true; };
  const memo = new Map();
  const hfree = (k, yi) => { const key = k * Y + yi; let v = memo.get(key); if(v === undefined){ v = free(k, ys[yi], [null, null]); memo.set(key, v); } return v; };
  /* خروج از لبه‌ی چپِ مبدأ: نزدیک‌ترین راهروی سمت چپ که مسیر افقی تا آن خالی باشد */
  let s = -1; for(let c = C - 1; c >= 0; c--){ if(cx[c] < A.x - 4){ let ok = true; for(let k = c; k < C - 1 && cx[k] < A.x; k++) if(!free(k, A.y, [e.from, null])){ ok = false; break; } if(ok){ s = c; break; } } }
  /* ورود از لبه‌ی راستِ مقصد: نزدیک‌ترین راهروی سمت راست */
  let t = -1; for(let c = 0; c < C; c++){ if(cx[c] > B.x + 4){ let ok = true; for(let k = c - 1; k >= 0 && cx[k + 1] > B.x; k--) if(!free(k, B.y, [e.to, null])){ ok = false; break; } if(ok){ t = c; break; } } }
  if(s < 0 || t < 0) return null;
  const N = C * Y * 2, dist = new Float64Array(N).fill(Infinity), prev = new Int32Array(N).fill(-1), heap = [];
  const id = (c, y, d) => (c * Y + y) * 2 + d;
  const st0 = id(s, iA, 1); dist[st0] = A.x - cx[s]; stHeapPush(heap, [dist[st0], st0]);
  let goal = -1;
  while(heap.length){
    const [dd, u] = stHeapPop(heap);
    if(dd > dist[u]) continue;
    const d = u & 1, cy = (u >> 1), c = (cy / Y) | 0, y = cy % Y;
    if(c === t && y === iB){ goal = u; break; }
    const relax = (v, w) => { if(dd + w < dist[v]){ dist[v] = dd + w; prev[v] = u; stHeapPush(heap, [dist[v], v]); } };
    if(y > 0) relax(id(c, y - 1, 0), ys[y] - ys[y - 1] + (d === 1 ? TURN : 0));
    if(y < Y - 1) relax(id(c, y + 1, 0), ys[y + 1] - ys[y] + (d === 1 ? TURN : 0));
    if(c > 0 && hfree(c - 1, y)) relax(id(c - 1, y, 1), cx[c] - cx[c - 1] + 30 + (d === 0 ? TURN : 0));
    if(c < C - 1 && hfree(c, y)) relax(id(c + 1, y, 1), cx[c + 1] - cx[c] + 30 + (d === 0 ? TURN : 0));
  }
  if(goal < 0) return null;
  const path = []; for(let u = goal; u >= 0; u = prev[u]) path.push(u); path.reverse();
  /* فاصله‌ی موازی: هر سیم کمی در راهرو و کانال جابه‌جا می‌شود تا سیم‌های هم‌مسیر روی هم نیفتند */
  const off = c => ((idx % 7) - 3) * Math.min(9, Math.max(0, (hw[c] - 10) / 3));
  const yo = ((idx % 5) - 2) * 3;
  const pts = [A];
  const P = u => { const cy = u >> 1, c = (cy / Y) | 0, y = cy % Y; return {x: cx[c] + off(c), y: ys[y] + (y === iA || y === iB ? 0 : yo)}; };
  for(const u of path) pts.push(P(u));
  pts.push(B);
  return {pts, back: B.x > A.x - 30};
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
/* دایره‌های خروجی روی لبه‌ی چپ بخش، هم‌تراز با دکمه‌شان؛ اگر چند دکمه در یک ردیف باشند کمی بالا و پایین می‌روند.
   اول از همه‌ی کارت‌ها می‌خواند، بعد می‌نویسد: فقط یک reflow به‌جای یکی برای هر کارت */
function stPlacePorts(cards){
  const plan = [];
  for(const card of cards){
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
    plan.push([card, h]);
  }
  for(const [card, h] of plan){
    card.querySelectorAll(".p-out").forEach(po => po.remove());
    if(h) card.insertAdjacentHTML("beforeend", h);
  }
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
const ST_KIND = {goto: ["رفتن به بخش", IC.go], pay: ["پرداخت", IC.coin], url: ["باز کردن لینک", IC.open], channel: ["کانال یا گروه", IC.open], alert: ["پیام پاپ‌آپ", IC.mega], copy: ["کپی متن", IC.copy], share: ["لینک دعوت", IC.users], app: ["باز کردن مینی‌اپ", IC.layers]};
const ST_MEDIA = {photo: "عکس", animation: "گیف", video: "ویدیو", audio: "موسیقی", voice: "ویس", document: "فایل"};

/* پیش‌نمایش رسانه‌ی بخش: عکس و گیف خودشان، بقیه آیکن + نام فایل */
function stMediaHTML(n){
  const m = n.media ? mediaById(n.media) : null;
  if(m && (m.kind === "photo" || m.kind === "animation") && m.url)
    return `<div class="stc-media"><img data-src="${API_BASE + esc(m.url)}" alt="" draggable="false" decoding="async"><span class="mk">${ST_MEDIA[m.kind]}</span></div>`;
  if(m) return `<div class="stc-media ico">${IC[m.kind] || IC.document}<b>${esc(m.name || "")}</b><span class="mk">${ST_MEDIA[m.kind] || "فایل"}</span></div>`;
  if(n.media) return `<div class="stc-media ico bad">${IC.document}<b>رسانه از کتابخانه حذف شده</b></div>`;
  if(n.photo && /^https?:\/\//i.test(n.photo)) return `<div class="stc-media"><img data-src="${esc(n.photo)}" alt="" draggable="false" decoding="async" referrerpolicy="no-referrer"><span class="mk">عکس لینکی</span></div>`;
  return "";
}
/* یک دکمه‌ی شیشه‌ای (یا کلیدِ کیبورد پایین چت) با دایره‌ی خروجیِ سیم */
function stBtnCell(id, r, c, b, cfg){
  const k = kindOf(b), [lab, ic] = ST_KIND[k] || ST_KIND.url;
  const tgt = k === "pay" ? b.pay?.goto : b.goto, wired = k === "goto" || (k === "pay" && !!b.pay?.goto);
  const broken = wired && !cfg.nodes[tgt];
  const tip = k === "goto" ? "رفتن به: " + titleOf(cfg, tgt) : k === "pay" ? `پرداخت ${b.pay.stars} ستاره` : lab;
  const anchor = wired ? `<span class="pa" data-pa="b|${id}|${r}|${c}" data-n="${esc(id)}" data-r="${r}" data-c="${c}" data-pc="${k === "pay" ? "var(--tok)" : "var(--ac)"}"></span>` : "";
  return `<div class="stk-cell"><button class="stk-btn k-${k}${broken ? " bad" : ""}${b.when ? " cond" : ""}" data-a="strow" data-n="${esc(id)}" data-r="${r}" data-c="${c}" title="${esc(tip)}"><span class="ki">${ic}</span><span class="kt">${esc(b.text)}</span></button>${anchor}</div>`;
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
  const txt = stripTags(n.text).trim();
  const bub = `<div class="stc-bub">${stMediaHTML(n)}<div class="tx${txt ? "" : " empty"}">${txt ? esc(txt.slice(0, 170)) + (txt.length > 170 ? "…" : "") : "هنوز متنی نوشته نشده"}</div></div>`;
  const grp = isRk => {
    const keys = btns.map((row, r) => { const cells = row.map((b, c) => (b.kb === "reply") === isRk ? stBtnCell(id, r, c, b, cfg) : "").join(""); return cells ? `<div class="stk-row">${cells}</div>` : ""; }).join("");
    return keys ? `<div class="stk${isRk ? " rk" : ""}"><div class="stk-cap">${isRk ? "کیبورد پایین چت" : "دکمه‌های شیشه‌ای زیر پیام"}</div>${keys}</div>` : "";
  };
  const kb = grp(false) + grp(true);
  let logic = "";
  (n.route || []).forEach((ru, i) => { logic += `<div class="stc-row"><span class="pa" data-pa="r|${id}|${i}" data-n="${esc(id)}" data-pc="var(--vio)"></span><span class="ric">${IC.go}</span><span class="rlb">${esc(condTxt(ru.when))} <small>· مسیر شرطی</small></span></div>`; });
  if(n.next) logic += `<div class="stc-row"><span class="pa" data-pa="x|${id}" data-n="${esc(id)}" data-pc="var(--ok)"></span><span class="ric">${IC.go}</span><span class="rlb">بعد از ثبت پاسخ <small>· رفتن به بخش بعدی</small></span></div>`;
  return `<div class="stc-card${isStart ? " start" : ""}${dead ? " dead" : ""}" data-id="${esc(id)}">
    <span class="stc-in${inc ? " has" : ""}" data-in="${esc(id)}"></span>
    <div class="stc-h"><span class="stc-ic">${stNodeIcon(n)}</span>
      <div class="stc-t"><b>${esc(titleOf(cfg, id))}</b><span class="ids">${esc(id)}</span></div>
      <button class="stc-menu" data-a="stmenu" data-n="${esc(id)}" aria-label="گزینه‌های بخش">⋮</button></div>
    ${tags.length ? `<div class="stc-badges">${tags.join("")}</div>` : ""}
    ${bub}${kb}
    ${logic ? `<div class="stc-sec">مسیرهای شرطی و خودکار</div>${logic}` : ""}
    <div class="stc-row plus"><span class="pa" data-pa="+" data-n="${esc(id)}" data-pc="var(--ac)"></span><span class="ric">${IC.plus}</span><span class="rlb">سیم بکش تا دکمه‌ی تازه بسازی</span></div>
    <div class="stc-act"><button data-a="stbtn" data-n="${esc(id)}">${IC.plus}دکمه‌ی جدید</button><button data-a="stkm" data-n="${esc(id)}">${IC.layers}مدیریت دکمه‌ها</button></div>
  </div>`;
}
function stPaintWires(){
  const svg = $("#stsvg"), cv = $("#stc");
  if(!svg || !cv) return;
  ST.wires.clear();
  let h = "", i = 0;
  const edges = stEdges(), rects = stRects(), flow = !!S.cur?.active && !reduced() && edges.length <= 8, glow = edges.length <= 20;
  ST.fast = edges.length > 80 || rects.length > 28;
  for(const e of edges){
    const g = stEdgeGeom(e, i, rects);
    if(!g) continue;
    const dot = flow ? `<circle class="w-dot" r="3.2"><animateMotion dur="${(2 + (i % 5) * .4).toFixed(1)}s" begin="-${(i * .43).toFixed(2)}s" repeatCount="indefinite" path="${g.d}"/></circle>` : "";
    h += `<g class="wire k-${e.kind}${g.back ? " back" : ""}" data-w="${e.key}">${glow ? `<path class="w-glow" d="${g.d}"/>` : ""}<path class="w-line" d="${g.d}"/><path class="w-hit" d="${g.d}"/>${dot}</g>`;
    e.i = i; ST.wires.set(e.key, e); i++;
  }
  /* کادر مشخص + contain:paint: بدونش Chromium برای هر سیمِ بلند یک لایه‌ی GPU جدا می‌سازد (صدها لایه‌ی غول‌پیکر → بوم سفید/کرش) */
  let x1 = 1e9, y1 = 1e9, x2 = -1e9, y2 = -1e9;
  for(const r of rects){ x1 = Math.min(x1, r.x); y1 = Math.min(y1, r.y); x2 = Math.max(x2, r.x + r.w); y2 = Math.max(y2, r.y + r.h); }
  if(x1 > x2){ x1 = y1 = 0; x2 = y2 = 400; }
  const PAD = 500, bx = Math.floor(x1 - PAD), by = Math.floor(y1 - PAD), bw = Math.ceil(x2 - x1 + 2 * PAD), bh = Math.ceil(y2 - y1 + 2 * PAD);
  svg.setAttribute("viewBox", `${bx} ${by} ${bw} ${bh}`); svg.setAttribute("width", bw); svg.setAttribute("height", bh);
  svg.style.left = bx + "px"; svg.style.top = by + "px"; svg.style.width = bw + "px"; svg.style.height = bh + "px";
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
/* اگر داده‌ی یک بخش خراب باشد، فقط همان کارت خطا نشان می‌دهد و بقیه‌ی نقشه باز می‌شود */
function stCardSafe(id, dead){
  try{ return stCardHTML(id, dead); }
  catch(err){
    console.error("studio card", id, err);
    return `<div class="stc-card dead" data-id="${esc(id)}"><span class="stc-in" data-in="${esc(id)}"></span><div class="stc-h"><span class="stc-ic">${IC.bot}</span><div class="stc-t"><b>${esc(id)}</b><span class="ids">خطا در نمایش این بخش</span></div><button class="stc-menu" data-a="stmenu" data-n="${esc(id)}" aria-label="گزینه‌های بخش">⋮</button></div></div>`;
  }
}
function stGridFallback(){
  Object.keys(S.cur.config.nodes).forEach((id, i) => { if(!ST.pos[id]) ST.pos[id] = {x: -(i % 4) * 330, y: 40 + Math.floor(i / 4) * 520}; });
}
function stSearchApply(center){
  const cv = $("#stc"), q = $("#stq"); if(!cv || !S.cur) return;
  const v = (q ? q.value : ST.q || "").trim().toLowerCase(); ST.q = v;
  let first = null;
  cv.querySelectorAll(".stc-card").forEach(el => {
    const n = S.cur.config.nodes[el.dataset.id] || {};
    const hit = !v || el.dataset.id.includes(v) || (n.title || "").toLowerCase().includes(v) || (n.text || "").toLowerCase().includes(v);
    el.classList.toggle("dim", !!v && !hit);
    if(v && hit && !first) first = el.dataset.id;
  });
  cv.querySelectorAll(".wire").forEach(w => w.classList.toggle("dim", !!v));
  if(center && v && first) stCenter(first);
}
/* رسم نقشه به‌صورت تفاضلی: کارتی که تغییری نکرده دست نمی‌خورد (نه پرپر، نه دوباره‌لود عکس، نه ازدست‌رفتن لمس) */
function stPaintWorld(){
  const wr = $("#stw"), cv = $("#stc");
  if(!wr || !cv || !S.cur) return;
  let fresh = false;
  try{ fresh = stEnsurePositions(); }catch(err){ console.error("studio layout", err); stGridFallback(); }
  const ids = Object.keys(S.cur.config.nodes), seen = stReach();
  const _ed = stEdges(); ST.inc = {}; for(const e of _ed) ST.inc[e.to] = (ST.inc[e.to] || 0) + 1;
  $("#stu")?.classList.toggle("many", _ed.length > 8 || ids.length > 10);
  $("#stu")?.classList.toggle("big", ids.length > 14);      // نقشه‌ی بزرگ: لایه‌ی GPU غول‌پیکر نساز (جلوگیری از بوم سفید)
  if(!wr.querySelector("#stsvg")) wr.insertAdjacentHTML("afterbegin", `<svg id="stsvg" xmlns="http://www.w3.org/2000/svg" width="2" height="2" aria-hidden="true"><path class="w-tmp" id="sttmp" d=""/></svg>`);
  const old = new Map();
  for(const el of wr.children) if(el.classList.contains("stc-card")) old.set(el.dataset.id, el);
  ST.sig = ST.sig || {}; ST.els = new Map();
  const added = [], tpl = document.createElement("template");
  for(const id of ids){
    const html = stCardSafe(id, !seen.has(id)), prev = old.get(id);
    if(prev && ST.sig[id] === html){ old.delete(id); ST.els.set(id, prev); continue; }
    tpl.innerHTML = html.trim();
    const el = tpl.content.firstElementChild;
    if(prev){ prev.replaceWith(el); old.delete(id); } else wr.appendChild(el);
    ST.sig[id] = html; ST.els.set(id, el); added.push(el);
  }
  for(const [id, el] of old){ el.remove(); delete ST.sig[id]; }
  stPlaceCards();
  stPlacePorts(added);
  stMeasure();
  if(fresh){ stAutoLayout(false); stPlaceCards(); stSave(); }      // بار اول: با اندازه‌ی واقعی بخش‌ها دوباره بچین
  stPaintWires();
  if(ST.q) stSearchApply(false);
  stMini(true);
  stApply();
  if(document.fonts?.ready && !ST._fw){            // بعد از آمدن فونت، ارتفاع‌ها عوض می‌شود؛ جای دایره‌ها را دوباره بسنج
    ST._fw = 1;
    document.fonts.ready.then(() => {
      ST._fw = 0;
      const c2 = $("#stc");
      if(S.view === "studio" && c2){ stPlacePorts([...c2.querySelectorAll(".stc-card")]); stMeasure(); stPaintWires(); stMini(true); stCull(); }
    });
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
        <button class="iconb" data-a="simopen" aria-label="تست زنده (شبیه‌ساز)" title="تست زنده‌ی ربات بدون هزینه">${IC.play}</button>
        <button class="iconb" data-a="dropen" aria-label="چرا کار نمی‌کند؟" title="دکتر ربات: چرا کار نمی‌کند؟">${S2IC.doctor}</button>
        <button class="iconb" data-a="pbopen" aria-label="مشکل‌ها" title="مشکل‌ها و رفع یک‌ضربه‌ای">${IC.heal}</button>
        <button class="b sm" id="stadd" data-a="stadd">${IC.plus}بخش جدید</button>
      </div>
      <div class="st-assist" id="stai">
        <span class="ib ai">${IC.spark}</span>
        <input id="stai-in" maxlength="1500" placeholder="دستیار: چه چیزی اضافه کنم؟ مثلاً: گردونه و بازی تاس" aria-label="درخواست دستیار استودیو">
        <button class="b sm" data-a="stai">${IC.plus}افزودن</button>
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
          <span class="sep"></span>
          <button class="tb lbl" data-a="wtopen" title="سازنده‌ی وقتی…آنگاه">${S2IC.wt}<span>وقتی…آنگاه</span></button>
          <button class="tb lbl" data-a="listsopen" title="لیست‌ها (شبیه اکسل)">${S2IC.table}<span>لیست‌ها</span></button>
          <button class="tb lbl" data-a="vdopen" title="نسخه‌ها و تفاوت‌ها">${S2IC.diff}<span>نسخه‌ها</span></button>
          <button class="tb lbl" data-a="growthopen" title="ربات رشد: لینک دعوت و پاداش">${IC.users}<span>رشد</span></button>
          <button class="tb lbl" data-a="agentopen" title="استودیوی عامل هوشمند">${IC.bot}<span>عامل</span></button>
          <button class="tb lbl" data-a="dcopen" title="کدهای تخفیف">${S2IC.doctor}<span>تخفیف</span></button>
          <button class="tb lbl" data-a="selsel" title="انتخاب چند بخش برای کپی یا حذف">${IC.copy}<span>انتخاب</span></button>
        </div>
      </div>
    </div>
    <div class="fgap"></div>
    <div class="panel mt" style="display:flex;flex-wrap:wrap;align-items:center;gap:12px;padding:10px 12px">
      <span class="ib">${IC.spark}</span>
      <div style="flex:1;min-width:0"><b style="font-size:13px;display:block;line-height:1.6">ساخت با هوش مصنوعی / ارتقای کامل ربات</b><span class="muted" style="font-size:11.5px;line-height:1.7;display:block">توضیح بده؛ علاوه بر دستیار رایگان، کل ساخت و ارتقا با هوش مصنوعی هم همین‌جا انجام می‌شود.</span></div>
      <textarea id="prompt" maxlength="${(S.cfg?.max_prompt) || 4000}" aria-label="درخواست ارتقا" placeholder="چه چیزی عوض شود؟ مثلاً: بازی تاس با شرط اضافه کن" style="flex:1 0 100%;min-height:64px"></textarea>
      <div id="live"></div>
      <div class="fgap"></div>
      <button class="b sm" data-a="gen">${IC.spark}ارتقا با AI</button>
    </div>`;
  ST.sig = {}; ST.els = new Map(); ST.q = ""; ST.w = null; ST.rect = null;
  const cv0 = $("#stc");
  ST.vw = cv0.clientWidth; ST.vh = cv0.clientHeight;
  ST._ro?.disconnect();
  if(window.ResizeObserver){
    ST._ro = new ResizeObserver(() => { ST.vw = cv0.clientWidth; ST.vh = cv0.clientHeight; ST.rect = null; if(S.view === "studio" && cv0.isConnected){ stMini(); stCull(); } });
    ST._ro.observe(cv0);
  }
  try{ stPaintWorld(); }
  catch(err){ console.error("studio paint", err); toast("نقشه درست نمایش داده نشد؛ یک بار از استودیو خارج شو و دوباره وارد شو"); }
  if(!ST.cam) requestAnimationFrame(stHome);
  stBindCanvas();
  $("#stq")?.addEventListener("input", () => stSearchApply(true));
  $("#stai-in")?.addEventListener("keydown", e => { if(e.key === "Enter"){ e.preventDefault(); A.stai($('[data-a="stai"]')); } });
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
    const r = ST.rect || (ST.rect = cv.getBoundingClientRect()), c = ST.cam || {x: 40, y: 40, z: 1};
    return {x: (e.clientX - r.left - c.x) / c.z, y: (e.clientY - r.top - c.y) / c.z};
  };
  cv.addEventListener("pointerdown", e => {
    if(e.pointerType === "mouse" && e.button !== 0) return;
    if(e.target.closest(".st-tools,.st-search,.st-hint,.st-energy,.st-pop,.st-mini,.stc-menu")) return;   // دکمه‌های روی بوم: بدون capture تا کلیکشان به خودشان برسد
    stClosePop();
    ST.rect = cv.getBoundingClientRect();
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
      const d = stDist(P), md = stMid(P), r = ST.rect || (ST.rect = cv.getBoundingClientRect());
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
      if(m.moved){ stSave(); stMini(true); stCull(); stPaintWires(); }
      else if(Date.now() - m.t0 < 500){ if(ST.selMode) stSelToggle(m.id); else openNode(m.id); }
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
  if(Object.keys(S.cur.config.nodes).length >= (S.cfg.max_nodes || 60)) return toast("به سقف تعداد بخش‌ها رسیده‌ای؛ برای ادامه، اشتراکت را ارتقا بده");
  const id = stNextId();
  ST.pos[id] = {x: Math.round(at.x / 8) * 8, y: Math.round(at.y / 8) * 8};
  const src = m.p === "+" ? {t: "new", n: m.n} : stParsePort(m.p);
  busy(null, async () => {
    await commit(cfg => {
      cfg.nodes[id] = {title: "بخش جدید", text: "متنِ این بخش را اینجا بنویس…", ask: false, buttons: []};
      stWireIn(cfg, src, id);
    }, "بخش ساخته و وصل شد");
    stCenter(id);
    openNode(id);
  });
}
function stCopy(id){
  if(Object.keys(S.cur.config.nodes).length >= (S.cfg.max_nodes || 60)) return toast("به سقف تعداد بخش‌ها رسیده‌ای؛ برای ادامه، اشتراکت را ارتقا بده");
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
  confirmQ("تغییرهای این فرم هنوز ذخیره نشده‌اند. بسته شود؟", ok => { if(ok) go(); });
}
const nodeOpts = (cfg, cur, extra = "") => extra + Object.keys(cfg.nodes).map(i => `<option value="${esc(i)}"${i === cur ? " selected" : ""}>${esc(titleOf(cfg, i))}</option>`).join("");
const head = t => `<div class="grab"></div><div class="sh"><h2>${t}</h2><button class="iconb sm" data-x="close" aria-label="بستن">${IC.x}</button></div>`;

/* ── منطق: متغیر، شرط و اکشن ── */
const OPS = [["==","مساوی باشد با"],["!=","مساوی نباشد با"],[">","بزرگ‌تر از"],[">=","بزرگ‌تر یا مساوی"],["<","کوچک‌تر از"],["<=","کوچک‌تر یا مساوی"],["contains","شامل باشد"],["empty","خالی باشد"],["filled","پر باشد"],["sub","اشتراک دوره‌اش فعال بود"]];
const ACTS = [["set","مقدار بده"],["add","جمع کن / کم کن"],["clear","پاک کن"],["random","عدد تصادفی"],["notify","به من خبر بده"],["remind","یادآوری بعد از چند دقیقه"],["calc","عبارت حسابی را حساب کن"],["disc","کد تخفیف را بررسی کن"],["sub_add","اشتراک دوره فعال کن"],["sub_del","اشتراک دوره لغو کن"]];
const APH = {set:"مقدار (می‌توانی {متغیر} بگذاری)", add:"عدد، مثلاً 5 یا -3", random:"بازه، مثلاً 1-6", notify:"متنی که برای خودت فرستاده می‌شود", remind:"متن یادآوری برای همین کاربر (اختیاری اگر بخش انتخاب کنی)",
  calc:"عبارت حسابی مثل {price} * {qty} یا (5+3)*2", disc:"قیمت پایه به عدد یا متغیر، مثل {price}", sub_add:"پلن اشتراک، مثل vip", sub_del:"پلن اشتراک، مثل vip"};
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
  if(c && c.op !== "sub" && !simpleCond(c)) return `<div class="muted">شرط ترکیبی؛ فقط با هوش مصنوعی عوض می‌شود</div>`;
  if(c && c.op === "sub") return `<div class="cmd"><select class="c-op" data-sh="re">${OPS.map(([v, l]) => `<option value="${v}"${v === c.op ? " selected" : ""}>${l}</option>`).join("")}</select>
    <input class="fa c-plan ltr" value="${esc(c.plan || "")}" placeholder="پلن (مثل vip؛ خالی = هر پلنی)" maxlength="16" autocomplete="off"></div>`;
  const x = c || blankCond(), nov = x.op === "empty" || x.op === "filled";
  return `<div class="cmd"><input class="c-var" list="vdl" value="${esc(x.var)}" placeholder="متغیر (مثلاً coins)" maxlength="20" autocomplete="off">
    <select class="c-op" data-sh="re">${OPS.map(([v, l]) => `<option value="${v}"${v === x.op ? " selected" : ""}>${l}</option>`).join("")}</select></div>
    ${nov ? "" : `<input class="fa c-val" value="${esc(x.value || "")}" placeholder="مقدار" maxlength="100">`}`;
}
function ruleHTML(list, o, i, cfg){
  const del = `<button class="iconb sm" data-sh="delrl" data-l="${list}" data-i="${i}" aria-label="حذف">${IC.x}</button>`;
  let inner;
  if(list === "do"){
    const noVar = o.op === "notify" || o.op === "remind" || o.op === "sub_add" || o.op === "sub_del";
    inner = `<div class="cmd"><select class="a-op" data-sh="re">${ACTS.map(([v, l]) => `<option value="${v}"${v === o.op ? " selected" : ""}>${l}</option>`).join("")}</select>
      ${noVar ? "" : `<input class="a-var" list="vdl" value="${esc(o.var || "")}" placeholder="نام متغیر" maxlength="20" autocomplete="off">`}${del}</div>
      ${o.op === "remind" ? `<div class="cmd"><input class="a-min" type="number" min="1" max="43200" value="${esc(o.minutes || 60)}" placeholder="چند دقیقه بعد؟"><select class="a-rg">${nodeOpts(cfg, o.goto || "", '<option value="">فقط پیام</option>')}</select></div>` : ""}
      ${o.op === "sub_add" ? `<div class="cmd"><input class="fa a-days ltr" inputmode="numeric" value="${esc(o.days || "30")}" maxlength="20" placeholder="چند روز؟ مثل 30"></div>` : ""}
      ${o.op === "clear" || o.op === "notify" || o.op === "remind" ? "" : `<input class="fa a-val" value="${esc(o.op === "sub_add" || o.op === "sub_del" ? (o.plan || "") : (o.value || ""))}" placeholder="${esc(APH[o.op])}" maxlength="${o.op === "notify" || o.op === "remind" ? 500 : 100}">`}`;
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
    if(q(".c-op")?.value === "sub") o.c = {op:"sub", plan:cleanVar(q(".c-plan")?.value || "")};
    else if(q(".c-var")) o.c = {var:cleanVar(q(".c-var").value), op:q(".c-op").value, value:q(".c-val")?.value ?? ""};
    if(q(".r-goto")) o.goto = q(".r-goto").value;
    if(q(".r-text")) o.text = q(".r-text").value;
    if(q(".a-op")){
      o.op = q(".a-op").value;
      if(o.op === "sub_add" || o.op === "sub_del"){
        o.plan = cleanVar(q(".a-val")?.value || o.plan || "") || "vip";
        if(q(".a-days")) o.days = (q(".a-days").value || "30").trim();
        delete o.var; delete o.value;
      } else {
        o.var = q(".a-var") ? cleanVar(q(".a-var").value) : (o.var || "");
        o.value = q(".a-val") ? q(".a-val").value : (o.value || "");
      }
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
    else if(a.op === "calc"){ if(!a.var) return "اسم متغیرِ نتیجه‌ی محاسبه را بنویس"; if(!(a.value || "").trim()) return "عبارت حسابی اکشن «محاسبه» را بنویس"; }
    else if(a.op === "disc"){ if(!a.var) return "اسم متغیری که کد کاربر در آن ذخیره می‌شود را بنویس"; if(!(a.value || "").trim()) return "قیمت پایه برای بررسی کد تخفیف را بنویس"; }
    else if(a.op === "sub_add" || a.op === "sub_del"){ if(!(a.plan || "").trim()) return "پلن اشتراک را بنویس (مثل vip)"; }
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
const outActs = l => l.map(a => {
  if(a.op === "remind") return {op:"remind", minutes:Math.max(1, Math.min(43200, parseInt(a.minutes) || 60)), ...((a.value || "").trim() ? {value:a.value.trim()} : {}), ...(a.goto ? {goto:a.goto} : {}), ...(a.key ? {key:a.key} : {})};
  if(a.op === "notify") return {op:"notify", value:a.value || ""};
  if(a.op === "clear") return {op:"clear", var:a.var};
  if(a.op === "calc") return {op:"calc", var:a.var, value:(a.value || "").trim()};
  if(a.op === "disc") return {op:"disc", var:a.var, price:(a.value || "0").trim()};
  if(a.op === "sub_add") return {op:"sub_add", plan:a.plan || "vip", days:String(a.days || "30").trim(), ...(a.var ? {var:a.var} : {})};
  if(a.op === "sub_del") return {op:"sub_del", plan:a.plan || "vip"};
  return {op:a.op, var:a.var, value:a.value || ""};
});

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
    ${cur === "reply" ? `<p class="muted mt">دکمه‌های کیبورد، همراه یک پیام کوچک، پایین چت نشان داده می‌شوند. در هر بخش می‌توانی هم دکمه‌ی شیشه‌ای داشته باشی، هم کیبورد.</p>` : ""} : ""}`;
}
let FMT_LAST = null;
document.addEventListener("focusin", e => { if(e.target.matches?.("[data-fmt]")) FMT_LAST = e.target; });
const fmtTools = tid => `<div class="fmtbar" title="قالب HTML تلگرام">${FMT_TAGS.map((t, i) => `<button type="button" data-a="fmtb" data-t="${tid}" data-i="${i}" aria-label="${t[1]}">${t[0]}</button>`).join("")}<button type="button" class="fx" data-a="emjbar" data-t="${tid}" aria-label="ایموجی پرمیوم" title="ایموجی پرمیوم">${IC.spark}</button></div>`;
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
      ${ruleSection("هدایت شرطی", "اولین شرطِ درست، کاربر را به بخش دیگری می‌فرستد (مثل قفل، سطح، ساعت کاری)", "route", cfg, 5)}
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
    await commit(c => { c.nodes[id] = {title: "بخش جدید", text: "متنِ این بخش را اینجا بنویس…", ask: false, buttons: [[{text: "منوی اصلی", goto: c.start}]]}; }, "بخش اضافه شد");
    stCenter(id);
    openNode(id);
  });
}

/* ── ویرایش دکمه ── */
function openBtn(nid, r, c){
  const cfg = S.cur.config;
  S.sheet = {kind: "btn", n: nid, r, c};
  if(c === null) D = {text: "دکمه‌ی جدید", kb: "inline", kind: "goto", goto: cfg.start, val: "", when: [], do: [], jch: "", jtx: "", adv: false, stars: 50, ptitle: "", pdesc: "", ptext: "", pgoto: "", style: "", icon: ""};
  else {
    const b = cfg.nodes[nid].buttons[r][c], k = kindOf(b);
    D = {text: b.text, kind: k, kb: b.kb === "reply" ? "reply" : "inline", goto: b.goto || cfg.start,
         val: k === "channel" ? "@" + CH_RE.exec(b.url)[1] : k === "app" ? (["1", 1, true].includes(b.app) ? "" : String(b.app || "")) : b.url || b.alert || b.copy || b.share || "",
         when: b.when ? [{c: cp(b.when)}] : [], do: cp(b.do || []), adv: false,
         jch: (b.join?.channels || []).map(c => "@" + c).join(" "), jtx: b.join?.text || "",
         stars: b.pay?.stars || 50, ptitle: b.pay?.title || "", pdesc: b.pay?.desc || "", ptext: b.pay?.text || "", pgoto: b.pay?.goto || "",
         style: b.style || "", icon: b.icon || ""};
  }
  const needLoad = S.cfg.emoji_max && S.emojis == null;
  if(needLoad) emjEnsure().then(() => { if(S.sheet?.kind === "btn" && $("#b-icons")){ readSheet(); renderSheet(); } });
  renderSheet();
}
const KINDS = [["goto", "رفتن به یک بخش"], ["channel", "کانال یا گروه تلگرام"], ["url", "لینک وب"], ["alert", "پیام پاپ‌آپ"], ["copy", "کپی کردن متن"], ["share", "اشتراک‌گذاری لینک دعوت"], ["pay", "پرداخت با ستاره‌ی تلگرام"], ["app", "باز کردن مینی‌اپ"]];
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
      <p class="muted mt">ستاره‌ها به حساب تلگرامِ تو می‌رود. اکشن‌های این دکمه فقط بعد از پرداختِ موفق اجرا می‌شوند (مثلاً فعال کردن متغیر vip). پرداخت‌ها با /payments دیده می‌شوند و با /refund کد برگشت می‌خورند.</p>`,
    app: `<span class="lbl">صفحه‌ی شروع مینی‌اپ (اختیاری)</span><input id="b-val" value="${esc(d.val)}" placeholder="home یا خالی برای صفحه‌ی اول" autocomplete="off">
      <p class="muted mt">با لمس این دکمه، مینی‌اپ ربات باز می‌شود (فقط در چت خصوصی و وقتی منتشر شده باشد). برای ساختن یا انتشار مینی‌اپ، تب «مینی‌اپ» را باز کن.</p>`
  }[d.kind];
  const canDo = d.kind === "goto" || d.kind === "alert" || d.kind === "pay";
  const nn = cfg.nodes[S.sheet.n], kbOk = !(nn.ask || nn.fields || nn.ai);
  return head(isNew ? "دکمه‌ی جدید" : "ویرایش دکمه") + `
    <span class="lbl">متن روی دکمه</span><input class="fa" id="b-text" value="${esc(d.text)}" maxlength="40">
    <span class="lbl">با لمس دکمه چه شود؟</span>
    <select id="b-kind" data-sh="bkind">${KINDS.map(([v, l]) => `<option value="${v}"${v === d.kind ? " selected" : ""}>${l}</option>`).join("")}</select>
    ${val}
    ${kbOk && d.kind !== "app" ? kbPicker(d.kb) : `<p class="muted mt">${d.kind === "app" ? "دکمه‌ی مینی‌اپ فقط شیشه‌ای می‌شود." : "این بخش فرم، دریافت پیام یا هوش مصنوعی است؛ دکمه‌هایش فقط شیشه‌ای می‌شوند."}</p>`}
    ${btnLook(d)}
    <details class="adv"${d.adv || d.when.length || d.do.length ? " open" : ""}><summary>شرط و اقدام‌ها (پیشرفته)</summary><div class="box">
      ${ruleSection("نمایش دکمه فقط در این شرایط", "مثلاً فقط برای صاحب ربات، یا وقتی امتیاز کافی است", "when", cfg, 1)}
      ${canDo ? ruleSection("وقتی دکمه لمس شد…", "قبل از رفتن به بخش یا نشان دادن پیام اجرا می‌شوند", "do", cfg, 6)
              : `<p class="muted">اقدام‌ها فقط برای دکمه‌های «رفتن به یک بخش»، «پیام پاپ‌آپ» و «پرداخت» کار می‌کنند.</p>`}
    </div></details>${canDo ? joinBox(d, "این دکمه") : ""}${dlist()}
    <div class="bar"><button class="b" data-sh="save">ذخیره</button>${isNew ? "" : `<button class="b r" data-sh="del">حذف دکمه</button>`}</div>`;
}
const BTN_STYLES = [["", "پیش‌فرض"], ["primary", "آبی"], ["success", "سبز"], ["danger", "قرمز"]];
function btnLook(d){
  const okS = S.cfg.btn_fx, okE = S.cfg.emoji_max, list = S.emojis || [];
  const lock = ok => ok ? "" : `<i class="pro">Premium / Pro</i>`;
  const sw = BTN_STYLES.map(([v, l]) => `<button type="button" class="sw ${v || "def"}${d.style === v ? " on" : ""}" data-sh="bstyle" data-v="${v}">${l}</button>`).join("");
  const cur = list.find(e => e.id === d.icon);
  const picks = [`<button type="button" class="${d.icon ? "" : "on"}" data-sh="bicon" data-v="">بدون</button>`,
    ...list.map(e => `<button type="button" class="${d.icon === e.id ? "on" : ""}" data-sh="bicon" data-v="${esc(e.id)}" aria-label="${esc(e.char)}">${emjImg(e)}</button>`)].join("");
  return `<span class="lbl">رنگ دکمه ${lock(okS)}</span><div class="sws${okS ? "" : " lock"}">${sw}</div>
    <span class="lbl">ایموجی پرمیوم کنار متن دکمه ${lock(okE)}</span>
    ${okE ? `<div class="emjpick" id="b-icons">${list.length ? picks : '<span class="muted">کتابخانه‌ی ایموجی‌هایت خالی است. ایموجی پرمیوم را برای ربات مادر بفرست.</span>'}</div>${d.icon && !cur && list.length ? `<p class="muted">این ایموجی دیگر در کتابخانه‌ات نیست، ولی روی دکمه می‌ماند.</p>` : ""}`
      : `<div class="sws lock"><button type="button" class="sw def" data-sh="bplan">دریافت اشتراک</button></div>`}
    <p class="muted mt">رنگ دکمه‌ها همه‌جا کار می‌کند. ایموجی پرمیوم فقط وقتی نشان داده می‌شود که حسابِ تلگرامِ سازنده‌ی ربات در BotFather، اشتراک پرمیوم تلگرام داشته باشد.</p>`;
}
function readBtn(){
  D.text = $("#b-text")?.value ?? D.text; D.kind = $("#b-kind")?.value ?? D.kind;
  if($("#b-goto")) D.goto = $("#b-goto").value;
  if($("#b-val")) D.val = $("#b-val").value;
  if($("#b-stars")){ D.stars = $("#b-stars").value; D.ptitle = $("#b-ptitle").value; D.pdesc = $("#b-pdesc").value; D.ptext = $("#b-ptext").value; D.pgoto = $("#b-pgoto").value; }
  readRl("when"); readRl("do"); readJoin();
  const ad = document.querySelector("details.adv"); if(ad) D.adv = ad.open;
}
function saveBtn(){
  const {n: nid, r, c} = S.sheet, d = D;
  if(!d.text.trim()) return toast("متن دکمه را بنویس");
  if(d.kind === "pay"){ const st = parseInt(d.stars); if(!(st >= 1 && st <= 10000)) return toast("قیمت باید عددی بین ۱ تا ۱۰٬۰۰۰ ستاره باشد"); }
  else if(d.kind === "app"){ const v = d.val.trim(); if(v && !/^[a-z0-9_]{1,30}$/.test(v)) return toast("شناسه‌ی صفحه باید حروف انگلیسی کوچک، عدد و _ باشد"); }
  else if(d.kind !== "goto" && d.kind !== "share" && !d.val.trim()) return toast("مقصد دکمه را وارد کن");
  const err = ruleErr(); if(err) return toast(err);
  const bj = (d.kind === "goto" || d.kind === "alert" || d.kind === "pay") ? chOut(d.jch, d.jtx) : null; if(typeof bj === "string") return toast(bj);
  const btn = {text: d.text.trim()};
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
  else if(d.kind === "app") btn.app = d.val.trim() || "1";
  else btn.url = d.val.trim();
  if(bj) btn.join = bj;
  if(d.style) btn.style = d.style;
  if(d.icon) btn.icon = d.icon;
  { const nn = S.cur.config.nodes[nid]; if(d.kb === "reply" && d.kind !== "app" && !(nn.ask || nn.fields || nn.ai)) btn.kb = "reply"; }
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
/* ── ماشه‌های گروه: کلمه یا دستور داخل گروه ← پاسخ و اکشن (امتیاز، رندوم، جدول برترین‌ها) ── */
const GRP_KINDS = [["contains", "شامل این کلمه باشد"], ["exact", "دقیقاً همین کلمه"], ["starts", "با این کلمه شروع شود"], ["command", "دستور (مثل /roll)"]];
const GRP_OPS = [["", "فقط پاسخ بده"], ["add", "اضافه کن به (عدد یا بازه مثل 1-10)"], ["set", "بگذار روی"]];
function grpDraft(t){
  const a = (t.do || [])[0], simple = !a || a.op === "add" || a.op === "set";
  return {raw: cp(t), on: t.on || "contains", words: (t.words || []).join("، "), reply: t.reply || "", op: simple ? (a?.op || "") : "_",
    var: simple ? (a?.var || "") : "", val: simple ? (a?.value ?? "") : "", cd: t.cooldown || 0, to: t.to === "replied", del: !!t.delete, bvar: t.board?.var || ""};
}
const GRP_BLANK = () => ({raw: {}, on: "exact", words: "", reply: "", op: "add", var: "points", val: "1-10", cd: 0, to: false, del: false, bvar: ""});
function openGrp(){
  S.sheet = {kind: "grp"};
  D = {t: (S.cur.config.group?.triggers || []).map(grpDraft)};
  renderSheet();
}
function grpSheet(){
  const sel = (v, o) => o.map(([k, t]) => `<option value="${k}"${v === k ? " selected" : ""}>${t}</option>`).join("");
  const rows = D.t.map((t, i) => `<div class="rl gtr" data-i="${i}">
      <div class="cmd" style="justify-content:space-between"><b>ماشه‌ی ${N(i + 1)}</b><button class="iconb sm" data-sh="delgt" data-i="${i}" aria-label="حذف">${IC.x}</button></div>
      <span class="lbl">وقتی عضوی در گروه…</span><select class="g-on">${sel(t.on, GRP_KINDS)}</select>
      <input class="fa g-words" value="${esc(t.words)}" placeholder="کلمه‌ها با ویرگول جدا شوند؛ مثلاً رندوم، شانس" maxlength="300">
      <span class="lbl">پاسخ ربات در گروه (می‌توانی از {name} و {points} استفاده کنی)</span>
      <textarea class="fa g-reply" data-fmt maxlength="1500" style="min-height:64px">${esc(t.reply)}</textarea>${fmtTools("@last")}
      <span class="lbl">اکشن روی متغیرِ عضو</span>
      ${t.op === "_" ? `<p class="muted">این ماشه اکشن پیشرفته دارد (با هوش مصنوعی ساخته شده) و بدون تغییر می‌ماند.</p><input type="hidden" class="g-op" value="_">`
        : `<div class="cmd"><select class="g-op">${sel(t.op, GRP_OPS)}</select><input class="g-var" list="vdl" value="${esc(t.var)}" placeholder="متغیر (مثلاً points)" maxlength="20" autocomplete="off"></div>
           <input class="fa g-val" value="${esc(t.val)}" placeholder="مقدار؛ برای امتیاز تصادفی مثل 1-10" maxlength="100">`}
      <span class="lbl">جدول برترین‌ها زیر پاسخ (نام متغیر عددی؛ اختیاری)</span><input class="g-bvar" list="vdl" value="${esc(t.bvar)}" placeholder="points" maxlength="20" autocomplete="off">
      <div class="cmd"><input class="ltr g-cd" inputmode="numeric" value="${esc(t.cd)}" aria-label="فاصله‌ی مجاز (ثانیه)" placeholder="۰"><span class="muted">ثانیه فاصله بین دو بار استفاده‌ی هر عضو (۰ = بدون محدودیت)</span></div>
      <label class="chk"><input type="checkbox" class="g-to"${t.to ? " checked" : ""}> روی عضوی که به پیامش ریپلای شده اعمال شود</label>
      <label class="chk"><input type="checkbox" class="g-del"${t.del ? " checked" : ""}> پیام خودِ عضو پاک شود</label></div>`).join("");
  return head("ماشه‌های گروه") + `
    <p class="muted">وقتی عضوی در گروه کلمه یا دستور خاصی بفرستد، ربات جواب می‌دهد و امتیاز می‌دهد. برای بازی‌ها و پاسخ خودکار گروه. ربات را به گروه اضافه و <b>ادمین</b> کن (یا در BotFather گزینه‌ی Group Privacy را خاموش کن)، وگرنه تلگرام پیام‌های عادی را به ربات نشان نمی‌دهد. برای هر پیام فقط اولین ماشه‌ی مطابق اجرا می‌شود.</p>
    <div class="rowh"><span class="lbl">ماشه‌ها</span>${D.t.length < 20 ? `<button class="b o sm" data-sh="addgt">${IC.plus}ماشه</button>` : ""}</div>
    <div id="g-list">${rows || '<p class="muted">هنوز ماشه‌ای نداری.</p>'}</div>${dlist()}
    <div class="bar"><button class="b" data-sh="save">ذخیره</button></div>`;
}
function readGrp(){
  if(!$("#g-list")) return;
  D.t = [...document.querySelectorAll("#g-list .gtr")].map((r, i) => {
    const q = s => r.querySelector(s), o = {...(D.t[i] || GRP_BLANK())};
    o.on = q(".g-on").value; o.words = q(".g-words").value; o.reply = q(".g-reply").value; o.op = q(".g-op").value;
    o.var = q(".g-var") ? cleanVar(q(".g-var").value) : o.var; o.val = q(".g-val") ? q(".g-val").value : o.val;
    o.bvar = cleanVar(q(".g-bvar").value); o.cd = parseInt(q(".g-cd").value) || 0; o.to = q(".g-to").checked; o.del = q(".g-del").checked;
    return o;
  });
}
function saveGrp(){
  const list = [];
  for(const t of D.t){
    const words = t.words.split(/[,،\n]+/).map(x => x.trim()).filter(Boolean);
    if(!words.length) return toast("برای هر ماشه حداقل یک کلمه یا دستور بنویس");
    if((t.op === "add" || t.op === "set") && !t.var) return toast("اسم متغیرِ اکشن را بنویس");
    if(!t.reply.trim() && !t.op && !t.bvar) return toast("هر ماشه باید پاسخ یا اکشن داشته باشد");
    const o = {...t.raw, on: t.on, words};
    if(t.reply.trim()) o.reply = t.reply.trim(); else delete o.reply;
    if(t.op === "add" || t.op === "set") o.do = [{op: t.op, var: t.var, value: String(t.val ?? "").trim() || (t.op === "add" ? "1" : "")}, ...(t.raw.do || []).slice(1)];
    else if(t.op === "") delete o.do;
    if(t.bvar) o.board = {...(t.raw.board || {}), var: t.bvar, top: t.raw.board?.top || 10}; else delete o.board;
    if(t.cd > 0) o.cooldown = t.cd; else delete o.cooldown;
    if(t.to) o.to = "replied"; else delete o.to;
    if(t.del) o.delete = true; else delete o.delete;
    list.push(o);
  }
  busy($('[data-sh="save"]'), () => commit(cfg => { if(list.length) cfg.group = {triggers: list}; else delete cfg.group; }, "ماشه‌های گروه ذخیره شد"));
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
  const o = S.sheet.o, row = (l, v, raw) => `<div class="cdrow"><div><span class="muted">${l}</span><div class="cdv">${v}</div></div>${raw ? `<button class="b o sm" data-a="cardcopy" data-v="${esc(raw)}">کپی</button>` : ""}</div>`;
  return head("پرداخت کارت‌به‌کارت") + `<div class="cardbox">
    ${row("مبلغ قابل پرداخت", N(Number(o.toman).toLocaleString("en")) + " تومان", String(o.toman))}
    ${row("شماره کارت", esc(o.number), o.raw)}
    ${o.holder ? row("به نام", esc(o.holder)) : ""}${o.bank ? row("بانک", esc(o.bank)) : ""}
  </div>
  <div class="fjt cdnote">${tgHtml(o.text)}</div>
  <button class="b" data-a="cardrcpt">ارسال رسید</button>
  <p class="muted mt">سفارش ${N("#" + o.order)} · ${o.plan ? "اشتراک " + esc(o.plan) : N(o.tokens) + " توکن"}</p><div class="fgap"></div>`;
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

async function buyPlan(id, btn){
  busy(btn, async () => {
    const d = await api("/api/plan/buy", "POST", { plan: id });
    const done = async () => { toast("پرداخت انجام شد"); for(let i = 0; i < 6; i++){ await sleep(i ? 1500 : 800); if(await sync() && S.plan?.id === id) break; } render(); bumpTokens(); };
    if(tg?.openInvoice) tg.openInvoice(d.url, st => {
      if(st === "paid") done();
      else if(st === "failed") toast("پرداخت ناموفق بود");
    }); else window.open(d.url, "_blank");
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
  grp:   {html: grpSheet,   read: readGrp,   save: saveGrp},
};
function renderSheet(){ if(S.sheet.kind === "bot" && !D) return openBot();   /* محافظ: شیت تنظیمات بدون داده‌ی اولیه باز نشود */
  showSheet(SHEETS[S.sheet.kind].html()); }
function readSheet(){ SHEETS[S.sheet?.kind]?.read?.(); }

function shAction(a, ds){
  if(!S.sheet) return;
  const prev = D?.kind;
  readSheet();
  if(a.startsWith("km")) return kmAct(a, ds);
  if(a.startsWith("ub")) return ubAct(a, ds);
  if(a === "stkm"){ const n = ds.n; return stGuardClose(() => { closeSheet(); openKm(n); }); }
  if(a === "stsetstart"){ const n = ds.n; closeSheet(); return busy(null, () => commit(cfg => { cfg.start = n; }, "حالا ربات از این بخش شروع می‌شود")); }
  if(a === "save"){
    const sh = SHEETS[S.sheet.kind];
    if(!sh?.save) return toast("چیزی برای ذخیره نیست");
    return sh.save();
  }
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
  else if(a === "addgt") D.t.push(GRP_BLANK());
  else if(a === "delgt") D.t.splice(+ds.i, 1);
  else if(a === "bstyle"){ if(!S.cfg.btn_fx) return emjNeedPlan(); D.style = ds.v; }
  else if(a === "bicon"){ if(!S.cfg.emoji_max) return emjNeedPlan(); D.icon = ds.v; }
  else if(a === "bplan") return emjNeedPlan();
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

/* ── ایموجی پرمیوم و رنگ دکمه داخل ادیتور ── */
async function emjEnsure(){
  if(S.emojis == null){ try{ S.emojis = (await api("/api/emojis")).items; }catch(_){ S.emojis = []; } }
  return S.emojis || [];
}
function emjNeedPlan(){
  confirmQ("ایموجی پرمیوم و دکمه‌ی رنگی با اشتراک Premium یا Pro فعال می‌شوند. صفحه‌ی اشتراک باز شود؟", ok => { if(ok) stGuardClose(() => { closeSheet(); A.goplan(); }); });
}
Object.assign(A, {
  emjbar: async el => {
    if(!S.cfg.emoji_max) return emjNeedPlan();
    const bar = el.closest(".fmtbar"), nxt = bar.nextElementSibling;
    if(nxt?.classList.contains("emjpick")){ nxt.remove(); return; }
    document.querySelectorAll(".fmtbar + .emjpick").forEach(x => x.remove());
    const list = await emjEnsure();
    const html = list.length ? list.map(e => `<button type="button" data-a="emjins" data-t="${esc(el.dataset.t)}" data-id="${esc(e.id)}" data-ch="${esc(e.char)}" aria-label="${esc(e.char)}">${emjImg(e)}</button>`).join("")
      : `<span class="muted">کتابخانه‌ی ایموجی‌هایت خالی است. ایموجی پرمیوم را برای ربات مادر بفرست.</span>`;
    if(bar.isConnected) bar.insertAdjacentHTML("afterend", `<div class="emjpick">${html}</div>`);
  },
  emjins: el => {
    const t = el.dataset.t === "@last" ? FMT_LAST : $("#" + el.dataset.t);
    if(!t || !t.isConnected) return toast("اول روی کادر متن بزن، بعد ایموجی را انتخاب کن");
    const tag = `<tg-emoji emoji-id="${el.dataset.id}">${el.dataset.ch}</tg-emoji>`, a = t.selectionStart ?? t.value.length, b = t.selectionEnd ?? a;
    t.value = t.value.slice(0, a) + tag + t.value.slice(b); t.focus(); t.setSelectionRange(a + tag.length, a + tag.length);
    t.dispatchEvent(new Event("input", {bubbles: true}));
  },
});
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
    <span class="lbl">کجا کار کند؟</span><select id="ur-where">${UB_WHERE.map(([k, t]) => `<option value="${k}"${(D.where || "pm") === k ? " selected" : ""}>${t}</option>`).join("")}</select>
    ${ubL("متن پاسخ", "می‌توانی از {name} (نام فرستنده)، {time} و {date} استفاده کنی.")}<textarea class="fa" id="ur-text" maxlength="1000" placeholder="متنی که فرستاده می‌شود">${esc(D.text)}</textarea>
    <label class="chk"><input type="checkbox" id="ur-on"${D.on ? " checked" : ""}> قانون فعال باشد</label>
    <div class="bar"><button class="b" data-sh="save">ذخیره</button>${isNew ? "" : `<button class="b r" data-sh="del">حذف</button>`}</div>`;
}
const ubruleRead = () => { D.kw = $("#ur-kw")?.value ?? D.kw; D.mode = $("#ur-mode")?.value ?? D.mode; D.text = $("#ur-text")?.value ?? D.text; D.where = $("#ur-where")?.value ?? D.where; D.on = $("#ur-on") ? $("#ur-on").checked : D.on; };
function ubruleSave(){
  const kw = D.kw.split(/[,،\n]/).map(s => s.trim()).filter(Boolean).slice(0, 8), text = D.text.trim();
  if(!kw.length) return toast("حداقل یک کلمه‌ی کلیدی بنویس");
  if(!text) return toast("متن پاسخ را بنویس");
  const rule = {kw, mode: D.mode, text, on: D.on, where: D.where || "pm"}, i = D.i;
  busy($('[data-sh="save"]'), async () => { await ubCommit(cfg => { if(i === null) cfg.rules.push(rule); else cfg.rules[i] = rule; }, "قانون ذخیره شد"); closeSheet(); renderUserbot(); });
}
function ubruleDel(){
  const i = D.i;
  confirmQ("این قانون حذف شود؟", ok => ok && busy($('[data-sh="del"]'), async () => { await ubCommit(cfg => { cfg.rules.splice(i, 1); }, "قانون حذف شد"); closeSheet(); renderUserbot(); }));
}


/* ── انتخاب گروه/کانال از اکانت ── */
function openUbPick(){
  ubRead();
  const x = ubItem(); if(!x) return;
  const mx = x.lim?.chats || 60;
  if(S.ubCfg.chats.length >= mx) return toast(`حداکثر ${mx} گروه یا کانال می‌توانی اضافه کنی`);
  if(x.status !== "running") return toast("اول یوزربات را روشن کن تا فهرست گروه‌ها خوانده شود");
  S.sheet = {kind: "ubpick"}; D = {items: null, err: ""}; renderSheet();
  const id = S.ubSel;
  api(`/api/userbots/${id}/chats`).then(d => { if(S.sheet?.kind === "ubpick" && S.ubSel === id){ D.items = d.items || []; D.scanned = d.scanned || 0; D.who = d.who || null; renderSheet(); } })
    .catch(e => { if(S.sheet?.kind === "ubpick"){ D.items = []; D.err = e.message || "خطا در خواندن فهرست"; renderSheet(); } });
}
function ubpickSheet(){
  if(D.items === null) return head("افزودن گروه یا کانال") + `<div class="gi static"><span class="muted">در حال خواندن چت‌های اکانت…</span></div>`;
  const have = new Set(S.ubCfg.chats.map(h => h.id));
  const rows = D.items.map(c => { const added = have.has(c.id), ok = !added;
    return `<div class="gi ubpick${ok ? "" : " static"}"${ok ? ` role="button" tabindex="0" data-sh="ubpick" data-id="${c.id}"` : ""} data-t="${esc(c.title.toLowerCase())}" style="${ok ? (c.can ? "" : "opacity:.7") : "opacity:.55"}"><span class="dot ${ok && c.can ? "on" : ""}"></span>
      <span class="gt"><b>${esc(c.title)}</b><span>${c.kind === "channel" ? "کانال" : "گروه"}${c.own ? " · ادمین" : ""}${c.members ? ` · ${N(c.members)} عضو` : ""}${added ? " · اضافه شده" : !c.can ? " · شاید اجازه‌ی ارسال نداشته باشی" : ""}</span></span></div>`; }).join("");
  const who = D.who ? `<div class="ubchip" style="margin:0 0 10px">${esc(D.who.name || "-")}${D.who.user ? ` · <bdi dir="ltr">@${esc(D.who.user)}</bdi>` : ""} · <bdi dir="ltr">${esc(D.who.phone)}</bdi></div>` : "";
  return head("افزودن گروه یا کانال") + who + (D.err ? `<p class="muted" style="color:var(--bad)">${esc(D.err)}</p>` : `<input id="ubp-q" placeholder="جستجوی نام…" autocomplete="off">`) +
    `<div class="panel mt2">${ubL("افزودن مستقیم", "یوزرنیم (@name)، لینک عمومی (t.me/name) یا آیدی عددی گروه/کانال. گروه یا کانال خصوصی را فقط وقتی پیدا می‌کند که اکانت وصل‌شده عضوش باشد. اگر گروه‌هایت در فهرست نیست، شاید با شماره‌ی دیگری وصل شده‌ای.")}<input id="ubp-ref" dir="ltr" autocomplete="off" placeholder="@username · t.me/xxx · -1001234567890" value="${esc(D.ref || "")}">
      <button class="b o sm mt2" data-sh="ubresolve">پیدا کن و اضافه کن</button></div>
     <div class="group sep mt2" style="max-height:44vh;overflow:auto">${rows || `<div class="gi static"><span class="muted">${D.err ? "" : "گروه یا کانالی پیدا نشد."}</span></div>`}</div>
     ${D.scanned ? `<small class="muted">${N(D.scanned)} چت بررسی شد · ${N(D.items.length)} گروه/کانال</small>` : ""}`;
}

/* ── شیت یک گروه/کانال ── */
function ubchatSheet(){
  const g = D.kind !== "channel";
  return head(esc(D.title)) + `
    ${D.err ? `<div class="panel" style="border-color:var(--bad)"><p class="muted" style="color:var(--bad);margin:0">متوقف شد: ${esc(D.err)}</p><button class="b o sm mt2" data-sh="ubcresume">ازسرگیری</button></div>` : ""}
    ${g ? `${ubL("پاسخ خودکار در این گروه", "«فقط منشن/ریپلای» ایمن‌تر است. «کلمه‌های کلیدی» به قانون‌های تب قانون‌ها (گزینه‌ی گروه‌ها یا هر دو) روی همه‌ی پیام‌ها جواب می‌دهد. پاسخ هوشمند را از تب قابلیت‌ها روشن کن؛ هزینه‌اش از توکن کم می‌شود.")}<select id="uh-reply">${UB_REPLY.map(([k, t]) => `<option value="${k}"${D.reply === k ? " selected" : ""}>${t}</option>`).join("")}</select>
    <label class="chk"><input type="checkbox" id="uh-ai"${D.ai ? " checked" : ""}> پاسخ هوشمند (فقط هنگام منشن یا ریپلای)</label>` : `<div class="ubchip">کانال — فقط مقصد پیام زمان‌بندی‌شده ${ubI("باید ادمین با اجازه‌ی ارسال پست باشی.")}</div>`}
    ${g ? `${ubL("محافظ هوشمند رسانه/لینک", "«خاموش» یعنی در این چت هیچ‌وقت متن یا رسانه‌ی پیام زمان‌بندی‌شده تغییر نکند (حتی اگر در پیام فعال باشد).")}<select id="uh-guard"><option value="auto"${D.guard !== "off" ? " selected" : ""}>طبق تنظیم هر پیام</option><option value="off"${D.guard === "off" ? " selected" : ""}>خاموش (بدون هیچ تغییری)</option></select>` : ""}
    <label class="chk"><input type="checkbox" id="uh-on"${D.on ? " checked" : ""}> این چت فعال باشد</label>
    <div class="bar"><button class="b" data-sh="save">ذخیره</button><button class="b r" data-sh="del">حذف از فهرست</button></div>`;
}
const ubchatRead = () => { if($("#uh-on")){ D.on = $("#uh-on").checked; if($("#uh-reply")){ D.reply = $("#uh-reply").value; D.ai = $("#uh-ai").checked; D.guard = $("#uh-guard")?.value || "auto"; } } };
function ubchatSave(){
  const i = D.i, h = {id: D.id, title: D.title, kind: D.kind, on: D.on, reply: D.reply, ai: D.ai, err: D.err || "", guard: D.guard === "off" ? "off" : "auto"};
  busy($('[data-sh="save"]'), async () => { await ubCommit(cfg => { cfg.chats[i] = h; }, "ذخیره شد"); closeSheet(); renderUserbot(); });
}
function ubchatDel(){
  const i = D.i;
  confirmQ("این چت از فهرست حذف شود؟ اگر تنها مقصد یک پیام زمان‌بندی‌شده باشد، آن پیام هم حذف می‌شود.", ok => ok && busy($('[data-sh="del"]'), async () => { await ubCommit(cfg => { cfg.chats.splice(i, 1); }, "حذف شد"); closeSheet(); renderUserbot(); }));
}

/* ── شیت پیام زمان‌بندی‌شده ── */
const ubSw = (id, on, label, sub, hint) => `<label class="chk"><input type="checkbox" id="${id}" class="ub-tg"${on ? " checked" : ""}> ${label}</label>${hint ? `<p class="muted" style="margin:2px 0 6px;font-size:12px">${hint}</p>` : ""}${sub ? `<div class="ub-sub" data-for="${id}" style="${on ? "" : "display:none;"}margin:4px 0 8px;padding-inline-start:10px;border-inline-start:2px solid rgba(120,140,160,.35)">${sub}</div>` : ""}`;
document.addEventListener("change", e => {
  const t = e.target; if(!t || !t.classList || !t.classList.contains("ub-tg")) return;
  const sub = document.querySelector(`.ub-sub[data-for="${t.id}"]`); if(sub) sub.style.display = t.checked ? "" : "none";
  const fb = document.getElementById("ub-fbbox"); if(fb) fb.style.display = (document.getElementById("up-mg")?.checked || document.getElementById("up-lg")?.checked) ? "" : "none";
});
function ubpostSheet(){
  const hrs = (v, max) => Array.from({length: max + 1}, (_, h) => `<option value="${h}"${h === v ? " selected" : ""}>${String(h).padStart(2, "0")}:00</option>`).join("");
  const every = UB_EVERY.some(x => x[0] === D.every_min) ? UB_EVERY : [...UB_EVERY, [D.every_min, ubEveryT(D.every_min)]].sort((a, b) => a[0] - b[0]);
  const isNew = D.i === null, g = {test: 3, safe: 60, balanced: 30, fast: 15}[S.ubCfg.safe] || 30;
  return head(isNew ? "زمان‌بندی جدید" : "ویرایش زمان‌بندی") + `
    ${ubL("نام")}<input id="up-name" maxlength="40" placeholder="مثلاً: تبلیغ صبحگاهی" value="${esc(D.name)}">
    ${ubL("ارسال به")}
    <div class="group sep">${S.ubCfg.chats.map(h => `<label class="gi chk" style="margin:0"><input type="checkbox" class="up-c" value="${h.id}"${D.chats.includes(h.id) ? " checked" : ""}> <span class="gt"><b>${esc(h.title)}</b><span>${h.kind === "channel" ? "کانال" : "گروه"}${h.err ? " · متوقف" : ""}${((ubItem()?.rs || {})[h.id] || []).map(k => k === "links" ? " · لینک/آیدی محدود" : " · رسانه محدود").join("")}</span></span></label>`).join("")}</div>
    ${ubL("متن‌ها", "تا ۵ متن؛ هر متن را با یک خط --- جدا کن. می‌توانی از {chat} (نام گروه/کانال)، {time} و {date} استفاده کنی. تکرار دقیقاً یک متن در چند گروه ریسک ریپورت دارد؛ چند متن متفاوت بنویس. اگر متن از ۱۰۰۰ نویسه بلندتر باشد، فایل جدا و متن بعد از آن می‌رود.")}
    <textarea class="fa" id="up-text" data-fmt rows="6" maxlength="16000" placeholder="متن اول&#10;---&#10;متن دوم">${esc(D.text)}</textarea>${fmtTools("up-text")}
    <div class="row2"><div>${ubL("قالب")}<select id="up-fmt"><option value="html"${D.fmt === "html" ? " selected" : ""}>HTML</option><option value="text"${D.fmt !== "html" ? " selected" : ""}>متن ساده</option></select></div>
      <div>${ubL("ترتیب متن‌ها")}<select id="up-mode"><option value="seq"${D.mode === "seq" ? " selected" : ""}>به‌نوبت</option><option value="rand"${D.mode === "rand" ? " selected" : ""}>تصادفی</option></select></div></div>
    ${ubL("عکس یا فایل (اختیاری)", "با همه‌ی متن‌های این زمان‌بندی ارسال می‌شود. فقط فایل بدون متن هم مجاز است.")}${mediaPicker("media", D.media)}
    ${ubSw("up-rp", D.rp, "ریپلای روی پیام کاربر فعال اخیر (به‌جای پست ساده)",
      `${ubL("پیام چه بازه‌ای باشد")}<select id="up-rwin">${[[10, "۱۰ دقیقه اخیر"], [30, "۳۰ دقیقه اخیر"], [60, "۱ ساعت اخیر"], [180, "۳ ساعت اخیر"], [720, "۱۲ ساعت اخیر"]].map(([v, t]) => `<option value="${v}"${(+D.rwin || 30) === v ? " selected" : ""}>${t}</option>`).join("")}</select>
       ${ubL("اگر در آن بازه کاربر فعالی نبود")}<select id="up-rnone"><option value="plain"${D.rnone !== "skip" ? " selected" : ""}>پست ساده بفرست</option><option value="skip"${D.rnone === "skip" ? " selected" : ""}>آن گروه را رد کن</option></select>`,
      "فعال‌ترین کاربران چند دقیقه‌ی اخیر انتخاب می‌شوند؛ ربات‌ها و پیام‌های خودت نادیده گرفته می‌شوند. در کانال‌ها اعمال نمی‌شود.")}
    ${ubSw("up-nl", D.nl, "اگر آخرین پیام گروه مال خودم است، ارسال نکن", "", "جلوگیری از پشت‌سرهم گذاشتن پیام در گروه‌های کم‌تحرک (ریسک ریپورت)")}
    ${ubSw("up-mg", D.mg, "تشخیص هوشمند محدودیت عکس و فایل", "", "حق‌های گروه برای اکانت تو بررسی می‌شود و اگر ارسال رسانه بسته بود، جایگزین زیر اجرا می‌شود. اگر خاموش باشد، رسانه‌ی ممنوع فقط رد می‌شود و چت متوقف نمی‌شود.")}
    ${ubSw("up-lg", D.lg, "تشخیص ربات آنتی‌لینک (حذف پیام دارای لینک/آیدی)",
      `${ubL("هنگام جایگزین، چه چیزی حذف شود")}<select id="up-lgs"><option value="both"${D.lgs !== "links" && D.lgs !== "ids" ? " selected" : ""}>لینک و آیدی</option><option value="links"${D.lgs === "links" ? " selected" : ""}>فقط لینک</option><option value="ids"${D.lgs === "ids" ? " selected" : ""}>فقط آیدی (@username)</option></select>`,
      "بعد از ارسالِ پیام دارای لینک/آیدی، چند ثانیه صبر می‌کند؛ اگر ربات گروه پیام را پاک کرد، جایگزین را می‌فرستد و تا ۲۴ ساعت آن گروه را لینک‌ممنوع به یاد می‌آورد.")}
    <div id="ub-fbbox" style="${D.mg || D.lg ? "" : "display:none"}">${ubL("جایگزین وقتی محدودیت تشخیص داده شد")}
      <select id="up-fb"><option value="text"${D.fb !== "fwd" && D.fb !== "skip" ? " selected" : ""}>فقط متن بفرست (بدون رسانه/لینک ممنوع)</option><option value="fwd"${D.fb === "fwd" ? " selected" : ""}>فوروارد یک پست از کانال</option><option value="skip"${D.fb === "skip" ? " selected" : ""}>آن گروه را رد کن</option></select>
      <input id="up-fwd" dir="ltr" autocomplete="off" placeholder="https://t.me/channel/123 (فقط برای حالت فوروارد)" value="${esc(D.fwd || "")}" style="margin-top:6px"></div>
    ${ubL("هر چند وقت", D.every_min < g ? `⚠️ سطح ایمنی فعلی حداقل ${g} دقیقه بین دو پیام به یک چت می‌گذارد، پس فاصله‌ی واقعی ${g} دقیقه می‌شود. برای تست کوتاه‌تر، سطح ایمنی را روی «آزمایشی» بگذار.` : `فاصله‌ی واقعی هیچ‌وقت کمتر از حداقل سطح ایمنی (${g} دقیقه) نمی‌شود.`)}<select id="up-every">${every.map(([m, t]) => `<option value="${m}"${D.every_min === m ? " selected" : ""}>${t}</option>`).join("")}</select>
    ${ubL("بازه‌ی مجاز ارسال", "ساعت تهران. بیرون از این بازه ساکت می‌ماند.")}
    <div style="display:flex;gap:8px;align-items:center"><select id="up-from">${hrs(D.from_h, 23)}</select><span class="muted">تا</span><select id="up-to">${hrs(D.to_h, 24).replace(/<option value="0".*?<\/option>/, "")}</select></div>
    ${ubL("حداکثر دفعه در روز")}<input id="up-daily" type="number" min="1" max="300" inputmode="numeric" value="${D.daily}">
    <label class="chk"><input type="checkbox" id="up-on"${D.on ? " checked" : ""}> فعال باشد</label>
    <div class="bar" style="flex-direction:column"><button class="b" data-sh="save">ذخیره</button>${isNew ? "" : `<button class="b o" data-sh="ubpostnow">ذخیره و ارسال همین حالا</button><button class="b r" data-sh="del">حذف</button>`}</div>`;
}
const ubpostRead = () => {
  if(!$("#up-name")) return;
  D.name = $("#up-name").value; D.text = $("#up-text").value; D.mode = $("#up-mode").value; D.fmt = $("#up-fmt")?.value || D.fmt; D.every_min = +$("#up-every").value || 360;
  D.rp = !!$("#up-rp")?.checked; D.rwin = +($("#up-rwin")?.value || D.rwin || 30); D.rnone = $("#up-rnone")?.value || D.rnone || "plain"; D.nl = !!$("#up-nl")?.checked; D.mg = !!$("#up-mg")?.checked; D.lg = !!$("#up-lg")?.checked; D.lgs = $("#up-lgs")?.value || D.lgs || "both"; D.fb = $("#up-fb")?.value || D.fb || "text"; D.fwd = ($("#up-fwd")?.value ?? D.fwd ?? "").trim(); D.from_h = +$("#up-from").value; D.to_h = +$("#up-to").value || 24; D.daily = Math.max(1, Math.min(300, +$("#up-daily").value || 4)); D.on = $("#up-on").checked;
  D.chats = [...document.querySelectorAll(".up-c:checked")].map(e => +e.value);
};
function ubpostBuild(){
  const texts = D.text.split(/^\s*-{3,}\s*$/m).map(t => t.trim()).filter(Boolean).slice(0, 5);
  if(!D.chats.length){ toast("حداقل یک مقصد انتخاب کن"); return null; }
  if(!texts.length && !D.media){ toast("متن یا فایل پیوست را مشخص کن"); return null; }
  if((D.mg || D.lg) && D.fb === "fwd" && !/t\.me\/(c\/\d+|[A-Za-z]\w{3,})\/\d+/.test(D.fwd || "")){ toast("برای فوروارد، لینک یک پست کانال را بنویس؛ مثل https://t.me/channel/123"); return null; }
  return {id: D.id, name: D.name.trim() || "پیام زمان‌بندی‌شده", chats: D.chats, texts, media: D.media || "", fmt: D.fmt || "html", mode: D.mode, every_min: D.every_min, from_h: D.from_h, to_h: D.to_h, daily: D.daily, on: D.on, rp: !!D.rp, rwin: D.rwin || 30, rnone: D.rnone || "plain", nl: !!D.nl, mg: !!D.mg, lg: !!D.lg, lgs: D.lgs || "both", fb: D.fb || "text", fwd: D.fwd || ""};
}
function ubpostSave(after){
  const p = ubpostBuild(); if(!p) return; const i = D.i;
  busy($('[data-sh="save"]'), async () => {
    await ubCommit(cfg => { if(i === null) cfg.posts.push(p); else cfg.posts[i] = p; }, "ذخیره شد");
    if(after){ const saved = i === null ? S.ubCfg.posts[S.ubCfg.posts.length - 1] : S.ubCfg.posts[i]; if(saved) await after(saved.id); }
    closeSheet(); renderUserbot();
  });
}
function ubpostDel(){
  const i = D.i;
  confirmQ("این پیام زمان‌بندی‌شده حذف شود؟", ok => ok && busy($('[data-sh="del"]'), async () => { await ubCommit(cfg => { cfg.posts.splice(i, 1); }, "حذف شد"); closeSheet(); renderUserbot(); }));
}

/* ── شیت اتصال اکانت: شماره ← کد ← (رمز دومرحله‌ای) ← تمام ── */
function openUbConn(){
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
  if(a === "ubpick"){
    const c = D.items?.find(x => String(x.id) === ds.id); if(!c) return;
    const mx = ubItem()?.lim?.chats || 60; if(S.ubCfg.chats.length >= mx) return toast(`حداکثر ${mx} گروه یا کانال می‌توانی اضافه کنی`);
    return busy(null, async () => { await ubCommit(cfg => { if(!cfg.chats.some(h => h.id === c.id)) cfg.chats.push({id: c.id, title: c.title, kind: c.kind, on: true, reply: c.kind === "group" ? "mention" : "off", ai: false, err: ""}); }, "اضافه شد");
      closeSheet(); S.ubTab = "chats"; renderUserbot(); });
  }
  if(a === "ubresolve"){
    const q = (D.ref || "").trim(); if(!q) return toast("یوزرنیم، لینک یا آیدی را بنویس");
    return busy($('[data-sh="ubresolve"]'), async () => {
      let c; try{ c = (await api(`/api/userbots/${S.ubSel}/chats/resolve`, "POST", {q})).item; }catch(e){ return toast(e.message); }
      if(S.ubCfg.chats.some(h => h.id === c.id)) return toast("این چت قبلاً اضافه شده");
      if(!c.can) toast("اضافه شد، ولی ممکن است اکانت اجازه‌ی ارسال نداشته باشد؛ در صورت خطا خودکار متوقف می‌شود");
      if(S.ubCfg.chats.length >= (ubItem()?.lim?.chats || 60)) return toast("به سقف تعداد گروه/کانال رسیده‌ای");
      await ubCommit(cfg => { cfg.chats.push({id: c.id, title: c.title, kind: c.kind, on: true, reply: c.kind === "group" ? "mention" : "off", ai: false, err: ""}); }, "اضافه شد");
      closeSheet(); S.ubTab = "chats"; renderUserbot();
    });
  }
  if(a === "ubcresume"){ D.err = ""; D.on = true; return renderSheet(); }
  if(a === "ubpostnow") return ubpostSave(async pid => { await api(`/api/userbots/${S.ubSel}/posts/${pid}/now`, "POST"); toast("در صف ارسال قرار گرفت؛ با مکث‌های ایمنی ارسال می‌شود"); });
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
SHEETS.ubpick = {html: ubpickSheet, read: () => { if($("#ubp-ref")) D.ref = $("#ubp-ref").value; }};
SHEETS.ubchat = {html: ubchatSheet, read: ubchatRead, save: ubchatSave, del: ubchatDel};
SHEETS.ubpost = {html: ubpostSheet, read: ubpostRead, save: () => ubpostSave(), del: ubpostDel};

/* ═════════════════ دستیار استودیو: پچ قطعی روی کانفیگ فعلی (رایگان) ═════════════════
   تب جداگانه‌ی «هوش مصنوعی» حذف شد؛ ساخت و ارتقای هوشمند همین‌جاست: دستیار رایگانِ قابلیت‌های
   کاتالوگ + ویرایش گفتگویی + ارتقای کامل با AI؛ پیش‌نمایش تغییر قبل از اعمال و برگشت با versions. */
Object.assign(A, {
  stai: el => busy(el, async () => {
    const ta = $("#stai-in"), req = (ta?.value || "").trim();
    if(req.length < 4) return toast("چه چیزی اضافه شود؟ کوتاه بنویس");
    try{
      const d = await api(`/api/bots/${S.cur.id}/assist`, "POST", {request: req});
      if(d.mode === "spec"){
        D = {assist: d};
        S.sheet = {kind: "info"};
        const pv = (d.preview || []).map(p => `<div class="vdl">${p.status === "ok" ? "✔" : p.status === "approx" ? "🟡" : "❌"} ${esc(p.text || "")}</div>`).join("");
        const news = (d.new_nodes || []).map(t => `<span class="chip">${esc(t)}</span>`).join("");
        showSheet(head("پیش‌نمایش تغییر — رایگان و قطعی") + `
          ${pv}
          <div class="sub"><b>بخش‌های تازه (${N(d.count || 0)}):</b></div>
          <div class="chips">${news || `<span class="muted">-</span>`}</div>
          <p class="muted mt">با تأیید، این قابلیت‌ها به همین ربات اضافه می‌شوند و بخش‌های قبلی دست نمی‌خورند. یک نسخه‌ی برگشت هم ذخیره می‌شود.</p>
          <div class="bar"><button class="b" data-a="staigo">${IC.check || IC.plus}اعمال روی ربات</button>
            <button class="b o" data-a="archx">بی‌خیال</button></div><div class="fgap"></div>`);
      }else{
        S.sheet = {kind: "info"};
        showSheet(head("دستیار استودیو") + `
          <p>برای این درخواست قابلیت آماده‌ای در کاتالوگ پیدا نشد.</p>
          <p class="muted">دو راه داری:</p>
          <div class="bar"><button class="b" data-a="archai">${IC.spark}ویرایش با هوش مصنوعی (${costTxt(true)} توکن)</button></div>
          <div class="fgap"></div>
          <textarea id="arch-req" maxlength="1500" style="min-height:64px" placeholder="مثلاً: متن بخش اصلی را عوض کن و دکمه کانال اضافه کن"></textarea>
          <div class="fgap"></div><button class="b sm" data-a="archedgo">${IC.spark}اعمال تغییر با AI</button>
          ${stAIChips()}
          <p class="muted mt">نمونه‌های آمادهٔ رایگان: «گردونه اضافه کن»، «بازی تاس اضافه کن»، «حدس عدد بگذار»، «مسابقه بساز»، «کیف سکه و هدیه روزانه».</p>
          <div class="fgap"></div>`);
      }
    }catch(e){ toast(e.message); }
  }),
  archai: () => { toast("درخواستت را بنویس و «اعمال تغییر با AI» را بزن"); },
  staigo: el => busy(el, async () => {
    if(!D?.assist) return closeSheet();
    try{
      const d = await api(`/api/bots/${S.cur.id}/assist/apply`, "POST", {spec: D.assist.spec});
      D = null;
      closeSheet();
      archCards(d);
      refreshStudio();
      stPaintWorld();
    }catch(e){ toast(e.message); }
  }),
});

/* ثبت صفحه‌ی استودیو در جدول صفحه‌ها (VIEWS در app.js تعریف می‌شود) */
VIEWS.studio = renderStudio;


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
    <div class="bpg">${SC3_PACKS.map(([id, t, d], i) => `<button class="bpc" data-a="packgo" data-i="${i}"><span class="bpi">${IC.spark}</span><span class="bpt"><b>${esc(t)}</b><span>${esc(d)}</span></span></button>`).join("")}</div><div class="fgap"></div>`;
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
/* ابزارهای متن هوش مصنوعی (قبلاً روی تب AI بودند؛ حالا شیت دستیار استودیو) */
function stAIChips(){
  return `<div class="chips" style="margin-top:8px"><button class="chip" data-a="aimode" data-m="explain">توضیح بده این ربات چه کار می‌کند</button>
    <button class="chip" data-a="aimode" data-m="improve">بهبود تجربه‌ی کاربر</button>
    <button class="chip" data-a="aimode" data-m="translate">ترجمه‌ی همه‌ی متن‌ها</button></div>`;
}
