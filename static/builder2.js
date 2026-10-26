/* ═══════════════════════════════════════════════════════════════
   builder2.js — مینی‌اپ‌ساز نسل ۲ (بعد از builder.js بارگذاری می‌شود و آن را گسترش می‌دهد):
   • گالری ۸۰ بلوک با پیش‌نمایش کوچک زنده‌نما، دسته‌بندی و جستجو
   • ویرایشگر جدول‌محور برای بلوک‌های تازه (بدون اصطلاح فنی)
   • چیدمان بصری هر بلوک (ستون، فاصله، پس‌زمینه، گردی، سایه، انیمیشن، طرح)
   • ویرایشگر منو (پایین/بالا، سبک ساده/شیشه‌ای/گرد/جزیره، فقط-آیکن، ترتیب)
   • ۱۲ تم آماده + فونت
   • کامپوننت‌ها: ذخیره‌ی بلوک به‌عنوان قطعه‌ی قابل‌استفاده‌ی دوباره
   همه‌ی توابع سراسری builder.js با پوشش (wrap) گسترش می‌یابند؛ رفتار قدیمی دست‌نخورده می‌ماند.
   ═══════════════════════════════════════════════════════════════ */
"use strict";

/* ── نام‌ها، آیکن‌ها و دسته‌های بلوک‌های تازه ── */
Object.assign(MB_T, {
  accordion: "آکاردئون", tabs: "تب‌ها", steps: "مراحل", timeline: "خط زمان", quote: "نقل‌قول",
  tags: "برچسب‌ها", table: "جدول", copytext: "متن کپی‌شدنی", article: "مقاله", heading: "تیتر",
  bullets: "لیست نشانه‌دار", numberlist: "لیست شماره‌دار", marquee: "نوار متحرک", consent: "پذیرش قوانین",
  slider: "اسلایدر", stories: "استوری", logos: "لوگوها", before_after: "قبل و بعد", imagegrid: "شبکه‌ی تصویر",
  file: "دانلود فایل", player: "پخش‌کننده",
  floatbtn: "دکمه‌ی شناور", quicklinks: "میان‌برها", gridmenu: "منوی کاشی", searchbar: "جستجو",
  product: "کارت محصول", catalog: "کاتالوگ با فیلتر", cart: "سبد خرید", pricing: "جدول قیمت",
  discount: "کد تخفیف", invoice: "فاکتور", orders: "سفارش‌های من",
  chart: "نمودار", progress: "نوار پیشرفت", xpbar: "سطح و امتیاز", statrow: "ردیف آمار",
  countup: "شمارنده‌ی متحرک", events: "رویدادها", calendar: "تقویم", inbox: "پاسخ‌های اخیر",
  checkin: "چک‌این روزانه", badges: "نشان‌ها", invite: "دعوت دوستان",
  profile: "پروفایل", reviews: "نظرات", team: "تیم ما", services: "خدمات", menu: "منو",
  contact: "تماس", social: "شبکه‌های اجتماعی", map: "نقشه و آدرس", linktree: "همه‌ی لینک‌ها",
  pollstat: "نتیجه‌ی نظرسنجی", hours: "ساعات کاری", changelog: "تغییرات", booking: "رزرو نوبت",
});
Object.assign(MB_IC, {
  accordion: "faq", tabs: "layers", steps: "fit", timeline: "clock", quote: "document", tags: "spark",
  table: "stats", copytext: "copy", article: "document", heading: "document", bullets: "inbox",
  numberlist: "inbox", marquee: "mega", consent: "shield", slider: "photo", stories: "photo",
  logos: "image", before_after: "photo", imagegrid: "photo", file: "dl", player: "audio",
  floatbtn: "bolt", quicklinks: "open", gridmenu: "layers", searchbar: "quiz",
  product: "bag", catalog: "bag", cart: "bag", pricing: "coin", discount: "gift", invoice: "document",
  orders: "inbox", chart: "chart", progress: "stats", xpbar: "medal", statrow: "stats",
  countup: "stats", events: "cal", calendar: "cal", inbox: "inbox", checkin: "gift", badges: "medal",
  invite: "users", profile: "person", reviews: "star", team: "users", services: "star", menu: "bag",
  contact: "phone", social: "open", map: "info", linktree: "open", pollstat: "quiz", hours: "clock",
  changelog: "refresh", booking: "cal",
});
const MB_CAT2 = [
  ["متن و محتوا", ["heading", "article", "bullets", "numberlist", "accordion", "tabs", "steps", "timeline", "quote", "tags", "table", "copytext", "marquee", "consent"]],
  ["رسانه", ["slider", "stories", "imagegrid", "logos", "before_after", "file", "player"]],
  ["دکمه و ناوبری", ["quicklinks", "gridmenu", "searchbar", "floatbtn"]],
  ["فروش", ["product", "catalog", "cart", "pricing", "discount", "invoice", "orders", "menu", "booking"]],
  ["داده و آمار", ["chart", "statrow", "progress", "xpbar", "countup", "events", "calendar", "inbox", "pollstat", "hours"]],
  ["بازی و جذابیت", ["checkin", "badges", "scratch", "invite"]],
  ["اجتماعی", ["profile", "reviews", "team", "services", "contact", "social", "map", "linktree", "changelog"]],
];
const MB_DEF2 = {
  accordion: {items: [{t: "سؤال یا عنوان", d: "متن پاسخ"}]},
  tabs: {items: [{t: "تب اول", d: "محتوای تب اول"}, {t: "تب دوم", d: "محتوای تب دوم"}]},
  steps: {items: [{t: "قدم اول", d: "توضیح کوتاه"}, {t: "قدم دوم", d: "توضیح کوتاه"}]},
  timeline: {items: [{t: "۱۴۰۳", d: "شروع کار"}, {t: "۱۴۰۴", d: "افتتاح شعبه دوم"}]},
  quote: {text: "بهترین زمان کاشتن درخت بیست سال پیش بود؛ دومین زمان خوب همین امروز است.", by: "ضرب‌المثل"},
  tags: {items: [{t: "ارسال رایگان"}, {t: "ضمانت"}, {t: "پرداخت در محل"}]},
  table: {head: ["کالا", "قیمت"], rows: [["چای", "۲۰"]]},
  copytext: {text: "کد: WELCOME"},
  article: {title: "درباره ما", text: "متن مقاله را اینجا بنویس."},
  heading: {text: "یک تیتر جذاب", size: 1},
  bullets: {items: [{t: "مزیت اول"}, {t: "مزیت دوم"}]},
  numberlist: {items: [{t: "سفارش بده"}, {t: "ما ارسال می‌کنیم"}]},
  marquee: {text: "🎁 تا پایان هفته ارسال رایگان!"},
  consent: {text: "قوانین را خواندم و می‌پذیرم.", label: "می‌پذیرم", do: []},
  slider: {items: [], auto: false},
  stories: {items: []},
  logos: {items: []},
  before_after: {la: "قبل", lb: "بعد"},
  imagegrid: {items: []},
  file: {label: "دانلود کاتالوگ"},
  player: {title: "قسمت اول پادکست", by: ""},
  floatbtn: {text: "ثبت سفارش", do: []},
  quicklinks: {items: [{t: "تماس با ما", ic: "📞"}, {t: "کانال ما", ic: "📢"}]},
  gridmenu: {items: [{t: "محصولات", ic: "🛍"}, {t: "سفارش‌ها", ic: "📦"}, {t: "پشتیبانی", ic: "💬"}]},
  searchbar: {items: [{t: "مورد اول", d: "توضیح"}, {t: "مورد دوم", d: "توضیح"}]},
  product: {title: "محصول ویژه", price: "۱۹۰٬۰۰۰", old: "", badge: "پرفروش", text: "توضیح کوتاه", btn: "خرید", do: []},
  catalog: {items: [{t: "چای سیاه", price: "۸۰", tag: "نوشیدنی"}, {t: "قهوه", price: "۱۲۰", tag: "نوشیدنی"}]},
  cart: {items: [{t: "چای سیاه", price: "80000"}], cur: "تومان", btn: "ثبت سفارش", do: []},
  pricing: {items: [{t: "پلن پایه", price: "۹۹٬۰۰۰", d: "یک ماه"}, {t: "پلن ویژه", price: "۱۹۹٬۰۰۰", d: "سه ماه", hi: true}]},
  discount: {code: "WELCOME", text: "۱۰٪ تخفیف اولین خرید"},
  invoice: {items: [{t: "چای سیاه", price: "80000"}], cur: "تومان", note: ""},
  orders: {table: "orders", scope: "my", limit: 10, empty: "هنوز سفارشی نداری."},
  chart: {kind: "bar", table: "orders", field: "total", key: "", label: "فروش هفته"},
  progress: {var: "", label: "پیشرفت هدف", max: 100},
  xpbar: {var: "", label: "سطح", per: 100},
  statrow: {items: [{var: "visits", label: "بازدید"}, {var: "points", label: "امتیاز"}]},
  countup: {var: "visits", label: "بازدید کل"},
  events: {items: [{t: "کارگاه فروش", date: "۱۴۰۴/۰۲/۱۵", d: "ساعت ۱۸"}]},
  calendar: {items: [{t: "کارگاه فروش", date: "۱۴۰۴/۰۲/۱۵"}]},
  inbox: {limit: 8},
  checkin: {},
  badges: {items: [{t: "اولین خرید", ic: "🥇"}, {t: "مشتری طلایی", ic: "🌟"}]},
  invite: {text: "دوستانت را دعوت کن؛ برای هر دعوت جایزه بگیر!", btn: "📤 ارسال لینک دعوت"},
  profile: {items: [{var: "points", label: "امتیاز"}], bio: ""},
  reviews: {items: [{t: "سارا", d: "خیلی عالی بود!", ic: "5"}]},
  team: {items: [{t: "علی محمدی", d: "مدیر فروش"}]},
  services: {items: [{t: "مشاوره", d: "۳۰ دقیقه گفتگو", ic: "📞"}]},
  menu: {items: [{t: "چای ماسالا", price: "۸۵", d: "با شیر و ادویه"}], cur: "هزار تومان"},
  contact: {items: [{t: "تلفن", d: "۰۲۱-۱۲۳۴۵۶۷۸", url: "tel:02112345678"}]},
  social: {items: [{t: "اینستاگرام", ic: "📸", url: "https://instagram.com/"}]},
  map: {addr: "تهران، خیابان ولیعصر، پلاک ۱۰", url: ""},
  linktree: {title: "همه‌جای ما", items: [{t: "کانال تلگرام", url: "https://t.me/your_channel"}]},
  pollstat: {items: [{t: "گزینه‌ی اول", var: ""}]},
  hours: {items: [{t: "شنبه تا چهارشنبه", d: "۹ تا ۲۱"}, {t: "پنجشنبه", d: "۹ تا ۱۴"}]},
  changelog: {items: [{t: "۲.۱", d: "افزودن پرداخت آنلاین"}]},
  booking: {items: [{t: "۱۰:۰۰", d: "ظرفیت دارد"}, {t: "۱۷:۰۰", d: "ظرفیت دارد"}]},
};

/* ── اسکیمای ویرایشگر جدول‌محور: f = [کلید، برچسب، سقف] ── */
const MB_SCHEMA = {
  accordion: {items: {cap: 20, f: [["t", "عنوان", 60], ["d", "متن", 300]], ta: ["d"]}},
  tabs: {items: {cap: 10, f: [["t", "عنوان تب", 40], ["d", "محتوا", 400]], ta: ["d"]}},
  steps: {items: {cap: 12, f: [["t", "عنوان قدم", 60], ["d", "توضیح", 200]], ta: ["d"]}},
  timeline: {items: {cap: 12, f: [["t", "عنوان", 60], ["d", "توضیح", 200]], ta: ["d"]}},
  tags: {items: {cap: 24, f: [["t", "برچسب", 24]]}},
  bullets: {items: {cap: 20, f: [["t", "مورد", 140]]}},
  numberlist: {items: {cap: 20, f: [["t", "مورد", 140]]}},
  events: {items: {cap: 20, f: [["t", "عنوان", 60], ["date", "تاریخ", 20], ["d", "توضیح", 200]]}},
  calendar: {items: {cap: 20, f: [["t", "عنوان", 60], ["date", "تاریخ (۱۴۰۴/۰۲/۱۵)", 20]]}},
  badges: {items: {cap: 12, f: [["ic", "ایموجی", 8], ["t", "نشان", 30]]}},
  reviews: {items: {cap: 20, f: [["t", "اسم", 40], ["ic", "ستاره (۱-۵)", 4], ["d", "متن نظر", 300]], ta: ["d"]}},
  team: {items: {cap: 12, f: [["t", "اسم", 40], ["d", "سمت", 120]], media: 1}},
  services: {items: {cap: 12, f: [["ic", "ایموجی", 8], ["t", "خدمت", 40], ["d", "توضیح", 120]]}},
  menu: {items: {cap: 30, f: [["t", "نام غذا", 40], ["price", "قیمت", 20], ["d", "توضیح", 120]]}, plain: [["cur", "واحد پول", 10]]},
  contact: {items: {cap: 6, f: [["t", "عنوان", 40], ["d", "مقدار", 120], ["url", "لینک (tel: یا https)", 300]]}},
  social: {items: {cap: 8, f: [["ic", "ایموجی", 8], ["t", "اسم", 20], ["url", "لینک", 300]]}},
  linktree: {plain: [["title", "تیتر", 40]], items: {cap: 12, f: [["t", "برچسب", 40], ["url", "لینک", 300]]}},
  hours: {items: {cap: 7, f: [["t", "روزها", 40], ["d", "ساعات", 20]]}},
  changelog: {items: {cap: 20, f: [["t", "نسخه", 20], ["d", "تغییرات", 300]], ta: ["d"]}},
  booking: {items: {cap: 12, f: [["t", "ساعت/تاریخ", 30], ["d", "وضعیت", 60]], do: "نوبت"}},
  quicklinks: {items: {cap: 12, f: [["ic", "ایموجی", 8], ["t", "برچسب", 24], ["url", "لینک (اختیاری)", 300]], do: "میان‌بر"}},
  gridmenu: {items: {cap: 12, f: [["ic", "ایموجی", 8], ["t", "برچسب", 24], ["url", "لینک (اختیاری)", 300]], do: "کاشی"}},
  searchbar: {items: {cap: 50, f: [["t", "عنوان", 40], ["d", "توضیح", 120]]}},
  product: {plain: [["title", "نام محصول", 60], ["price", "قیمت", 20], ["old", "قیمت قبل (خط‌خورده)", 20], ["badge", "برچسب", 20], ["text", "توضیح", 300]], media: 1, act: [["btn", "دکمه‌ی خرید", "do"]]},
  catalog: {items: {cap: 30, f: [["t", "نام", 60], ["price", "قیمت", 20], ["tag", "دسته", 20], ["text", "توضیح", 120]]}, mediaPer: 1},
  cart: {items: {cap: 20, f: [["t", "کالا", 40], ["price", "قیمت عددی", 20]]}, plain: [["cur", "واحد پول", 10], ["btn", "متن دکمه", 24]], act: [[null, "دکمه‌ی ثبت", "do"]]},
  pricing: {items: {cap: 6, f: [["t", "نام پلن", 40], ["price", "قیمت", 20], ["d", "امکانات", 200], ["hi", "پلن ویژه (هایلایت)"]], chk: ["hi"], do: "انتخاب پلن"}},
  discount: {plain: [["code", "کد تخفیف", 40], ["text", "توضیح", 200]]},
  invoice: {items: {cap: 15, f: [["t", "ردیف", 40], ["price", "مبلغ عددی", 20]]}, plain: [["cur", "واحد پول", 10], ["note", "یادداشت", 200]]},
  orders: {plain: [["table", "نام جدول (مثل orders)", 20]], sel: [["scope", "نمایش", [["my", "هر کاربر سفارش‌های خودش"], ["all", "همه (مشترک)"]]]], num: [["limit", "تعداد (۱-۲۰)", 1, 20]]},
  chart: {sel: [["kind", "نوع نمودار", [["bar", "میله‌ای"], ["line", "خطی"], ["donut", "دایره‌ای"]]]], plain: [["table", "نام جدول", 20], ["field", "فیلد عددی", 20], ["key", "دسته‌بندی بر اساس فیلد (اختیاری)", 20], ["label", "عنوان", 40]]},
  progress: {plain: [["var", "نام متغیر عددی", 20], ["label", "عنوان", 40], ["max", "سقف", 10]]},
  xpbar: {plain: [["var", "نام متغیر عددی", 20], ["label", "عنوان", 40], ["per", "امتیاز هر سطح", 10]]},
  countup: {plain: [["var", "نام متغیر عددی", 20], ["label", "عنوان", 40]]},
  statrow: {items: {cap: 4, f: [["var", "متغیر", 20], ["label", "برچسب", 30]]}},
  profile: {items: {cap: 4, f: [["var", "متغیر", 20], ["label", "برچسب", 30]]}, plain: [["bio", "درباره (اختیاری)", 200]]},
  pollstat: {items: {cap: 8, f: [["t", "گزینه", 40], ["var", "متغیر شمارنده (مشترک)", 20]]}},
  quote: {plain: [["text", "متن نقل‌قول", 500], ["by", "گفته‌شده از", 60]], ta: ["text"]},
  copytext: {plain: [["text", "متن کپی‌شدنی", 300]]},
  article: {plain: [["title", "تیتر", 80], ["text", "متن", 3000]], ta: ["text"], fmt: ["text"]},
  heading: {plain: [["text", "متن تیتر", 120]], num: [["size", "اندازه (۱=بزرگ تا ۳=کوچک)", 1, 3]]},
  marquee: {plain: [["text", "متن نوار", 200]]},
  consent: {plain: [["text", "متن قوانین", 1000], ["label", "برچسب چک‌باکس", 40]], ta: ["text"], fmt: ["text"], act: [[null, "دکمه‌ی ادامه", "do"]]},
  table: {table: 1},
  slider: {mediaList: {cap: 10, label: "تصویر"}, chk2: [["auto", "پخش خودکار"]]},
  stories: {mediaList: {cap: 12, label: "استوری", lab: "label"}},
  logos: {mediaList: {cap: 12, label: "لوگو"}},
  imagegrid: {mediaList: {cap: 12, label: "تصویر"}},
  before_after: {media2: 1, plain: [["la", "برچسب اول", 20], ["lb", "برچسب دوم", 20]]},
  file: {media: 1, plain: [["label", "برچسب دکمه", 60]]},
  player: {media: 1, plain: [["title", "عنوان", 60], ["by", "زیرعنوان", 40]]},
  floatbtn: {plain: [["text", "متن دکمه", 24]], act: [[null, "کار دکمه", "do"]]},
  inbox: {num: [["limit", "تعداد (۱-۲۰)", 1, 20]]},
  invite: {plain: [["text", "متن", 200], ["btn", "متن دکمه", 24]]},
  checkin: {},
};

/* ── پیش‌نمایش کوچک هر بلوک در گالری (شکل کلی، بدون کد) ── */
const MB_PV = {
  hero: "hero", text: "txt", heading: "txt lg", article: "txt many", quote: "txt qt2", copytext: "txt code",
  image: "img", gallery: "imgs", slider: "imgs", stories: "circles", logos: "chips2", before_after: "img split",
  imagegrid: "imgs3", file: "btnrow", player: "btnrow",
  buttons: "btns", floatbtn: "btns one", quicklinks: "rows2", gridmenu: "tiles", searchbar: "bar",
  cards: "cards2", product: "cardp", catalog: "cards2", cart: "rows2", pricing: "cards3", discount: "txt code",
  invoice: "rows2", orders: "rows2", menu: "rows2", booking: "tiles",
  list: "rows2", board: "rows2", form: "form", stat: "stat", statrow: "stat2", chart: "chart",
  progress: "bar", xpbar: "bar", countup: "stat", events: "rows2", calendar: "grid7", inbox: "rows2",
  faq: "acc2", accordion: "acc2", tabs: "acc2", steps: "num2", timeline: "num2", bullets: "num2",
  numberlist: "num2", tags: "chips2", table: "grid7", marquee: "bar thin", consent: "form",
  banner: "bar", countdown: "stat", pay: "btns one", ai: "chat", links: "rows2", divider: "hr",
  spacer: "hr", games: "tiles", wallet: "stat", gamesboard: "rows2", shopcoins: "rows2",
  invite: "btns", profile: "stat2", reviews: "rows2", team: "rows2", services: "rows2", contact: "rows2",
  social: "rows2", map: "img low", linktree: "rows2", pollstat: "chart", hours: "rows2", changelog: "num2",
  checkin: "btns one", badges: "tiles",
};
const mbPreview = t => `<span class="bpp ${MB_PV[t] || "txt"}"></span>`;

/* ── گالری تازه (جستجو + پیش‌نمایش + کامپوننت‌ها) ── */
function bpSheet2(){
  if(MB._q2 === undefined) MB._q2 = "";
  const q = MB._q2.trim().toLowerCase();
  const comps = mbComps();
  const hit = t => !q || (MB_T[t] || t).toLowerCase().includes(q);
  const cats = MB_CAT.concat(MB_CAT2).map(([cat, types]) => {
    const ts = types.filter(hit);
    if(!ts.length) return "";
    return `<div class="sub"><span>${cat}</span></div>
      <div class="bgrid">${ts.map(t => `<button class="bpick${(MB.draft.screens[MB.screen].blocks || []).length >= MB.caps.blocks ? " off" : ""}" data-a="mbpick" data-t="${esc(t)}">
        ${mbPreview(t)}<span>${MB_T[t] || t}</span></button>`).join("")}</div>`;
  }).join("");
  const compHTML = MB._comps === undefined ? "" : (comps.length ? `<div class="sub"><span>قطعه‌های ذخیره‌شده‌ی تو (روی همه‌ی دستگاه‌ها)</span></div>
    <div class="bgrid">${comps.map((c, i) => `<button class="bpick" data-a="mbcompins" data-i="${i}">${mbPreview(c.b.t)}<span>${esc(c.name)}</span><i class="cpx" data-a="mbcompdel" data-i="${i}">×</i></button>`).join("")}</div>`
    : `<div class="sub"><span>قطعه‌های ذخیره‌شده‌ی تو</span></div><p class="muted">از منوی هر بلوک «ذخیره به‌عنوان قطعه» را بزن تا اینجا ذخیره شود.</p>`);
  return head("افزودن بلوک") + `
    <input class="fa" id="bp-q" placeholder="جستجوی بلوک…" value="${esc(MB._q2)}" autocomplete="off">
    ${compHTML}${cats}<div class="fgap"></div>`;
}
function mbComps(){
  if(MB._comps === undefined){
    MB._comps = null;
    api("/api/comps").then(d => { MB._comps = d.items || []; if(S.sheet?.kind === "bp") renderSheet(); }).catch(() => { MB._comps = []; });
  }
  return MB._comps || [];
}
const _bpSheet0 = bpSheet;
bpSheet = function() { return bpSheet2(); };

/* ── بلوک پیش‌فرض برای انواع تازه ── */
const _mbDefaultBlock0 = mbDefaultBlock;
mbDefaultBlock = function(t){
  const d = _mbDefaultBlock0(t);
  if(MB_DEF2[t]){
    const extra = JSON.parse(JSON.stringify(MB_DEF2[t]));
    Object.assign(d, extra);
    if(d.do) d.do = [];
  }
  if(d.hid !== undefined) delete d.hid;
  return d;
};

/* ── خلاصه‌ی بلوک برای انواع تازه ── */
const _mbBlockSummary0 = mbBlockSummary;
mbBlockSummary = function(x){
  const t = x.t, s = MB_SCHEMA[t];
  if(t === "chart") return {bar: "میله‌ای", line: "خطی", donut: "دایره‌ای"}[x.kind] + " · " + (x.table || "");
  if(t === "progress" || t === "xpbar" || t === "countup") return x.var || "";
  if(s?.items) return (x.items?.length || 0) + " آیتم";
  if(t === "product") return (x.price ? x.price : "") + (x.badge ? " · " + x.badge : "");
  if(t === "heading") return (x.text || "").slice(0, 30);
  if(t === "article" || t === "quote") return (x.text || "").replace(/<[^>]+>/g, "").slice(0, 30);
  if(t === "copytext" || t === "marquee" || t === "discount") return (x.text || x.code || "").slice(0, 30);
  if(t === "table") return (x.rows?.length || 0) + " ردیف";
  if(t === "slider" || t === "stories" || t === "logos" || t === "imagegrid") return (x.items?.length || 0) + " تصویر";
  if(t === "invite" || t === "checkin" || t === "consent") return "";
  return _mbBlockSummary0(x);
};

/* ── ویرایشگر جدول‌محور ── */
function mbGenSheet(x){
  const sch = MB_SCHEMA[x.t], t = x.t;
  let h = head("بلوک «" + (MB_T[t] || t) + "»");
  const inp = (k, label, len, val, ta) => (ta
    ? `<span class="lbl">${label}</span><textarea class="fa" id="g-${k}" data-fmt maxlength="${len}" style="min-height:70px">${esc(val ?? "")}</textarea>${fmtTools("g-" + k)}`
    : `<span class="lbl">${label}</span><input class="fa" id="g-${k}" value="${esc(val ?? "")}" maxlength="${len}">`);
  if(s.ta) for(const k of s.ta){ const f = (s.items?.f || []).find(z => z[0] === k) || null; }
  if(s.plain) for(const [k, label, len] of s.plain){
    h += inp(k, label, len, x[k], (s.ta || []).includes(k));
  }
  if(s.sel) for(const [k, label, opts] of s.sel){
    h += `<span class="lbl">${label}</span><select id="g-${k}">${opts.map(([v, l]) => `<option value="${esc(v)}"${x[k] === v ? " selected" : ""}>${esc(l)}</option>`).join("")}</select>`;
  }
  if(s.num) for(const [k, label, lo, hi] of s.num){
    h += `<span class="lbl">${label}</span><input id="g-${k}" type="number" min="${lo}" max="${hi}" value="${esc(x[k] ?? lo)}">`;
  }
  if(s.chk2) for(const [k, label] of s.chk2){
    h += `<label class="chk"><input type="checkbox" id="g-${k}"${x[k] ? " checked" : ""}> ${label}</label>`;
  }
  if(s.media) h += `<span class="lbl">رسانه</span>${mediaPicker("media", x.media || "")}${!x.media ? `<span class="lbl">یا لینک مستقیم https</span><input id="g-url" value="${esc(x.url || "")}" placeholder="https://..." autocomplete="off">` : ""}`;
  if(s.media2){
    h += `<span class="lbl">تصویر اول (قبل)</span>${mediaPicker("media", x.media || "")}${!x.media ? `<span class="lbl">یا لینک</span><input id="g-url" value="${esc(x.url || "")}" autocomplete="off">` : ""}
      <span class="lbl">تصویر دوم (بعد)</span>${mediaPicker("media2", x.media2 || "")}${!x.media2 ? `<span class="lbl">یا لینک</span><input id="g-url2" value="${esc(x.url2 || "")}" autocomplete="off">` : ""}`;
  }
  if(s.mediaList){
    h += `<div class="sub"><span>${s.mediaList.label}ها (${N(x.items.length)} از ${s.mediaList.cap})</span><button class="b o sm" data-a="mbg2add"${x.items.length >= s.mediaList.cap ? " disabled" : ""}>${IC.plus}افزودن</button></div>`;
    h += x.items.map((it, i) => `<div class="rl">${mediaPicker("gi" + i, it.media || "")}${!it.media ? `<input id="g-gi-${i}" value="${esc(it.url || "")}" placeholder="https://..." autocomplete="off">` : ""}
      ${s.mediaList.lab ? `<input class="fa g2lab" data-i="${i}" value="${esc(it.label || "")}" maxlength="30" placeholder="برچسب">` : ""}
      <button class="b r sm" data-a="mbg2del" data-i="${i}">حذف</button></div>`).join("");
  }
  if(s.items){
    const cap = s.items.cap, fs = s.items.f;
    h += `<div class="sub"><span>آیتم‌ها (${N((x.items || []).length)} از ${N(cap)})</span><button class="b o sm" data-a="mbitadd"${(x.items || []).length >= cap ? " disabled" : ""}>${IC.plus}آیتم</button></div>`;
    h += (x.items || []).map((it, i) => `<div class="rl"><div class="cmd" style="justify-content:space-between"><b>آیتم ${N(i + 1)}</b><button class="iconb sm" data-a="mbitdel" data-i="${i}" aria-label="حذف">${IC.x}</button></div>
      ${fs.filter(f => f[0] !== "hi").map(([k, label, len]) => `<input class="fa it-f" data-i="${i}" data-k="${k}" value="${esc(it[k] ?? "")}" maxlength="${len}" placeholder="${label}">`).join("")}
      ${(s.items.chk || []).map(k => `<label class="chk"><input type="checkbox" class="it-c" data-i="${i}" data-k="${k}"${it[k] ? " checked" : ""}> ${(fs.find(f => f[0] === k) || [])[1] || k}</label>`).join("")}
      ${s.items.media ? mediaPicker("it" + i, it.media || "") : ""}
      ${s.items.do ? `<div class="mbdo" data-k="items.${i}.do"></div><button class="b o sm" data-a="mbdoadd" data-k="items.${i}.do">${IC.plus}کار این آیتم</button>` : ""}
      </div>`).join("");
  }
  if(s.act) for(const [btnK, label, key] of s.act){
    h += `<span class="lbl">${label}</span><div class="mbdo" data-k="${key}"></div><button class="b o sm" data-a="mbdoadd" data-k="${key}">${IC.plus}اکشن</button>`;
    if(btnK) h += `<input class="fa" id="g-${btnK}" value="${esc(x[btnK] || "")}" maxlength="24" placeholder="متن دکمه">`;
  }
  if(s.table){
    h += `<div class="sub"><span>سرستون‌ها</span></div><div class="cmd">${(x.head || []).map((c, i) => `<input class="fa tb-h" data-i="${i}" value="${esc(c)}" maxlength="30">`).join("")}</div>
      <button class="b o sm" data-a="mbcoladd"${(x.head || []).length >= 6 ? " disabled" : ""}>${IC.plus}ستون</button>
      <div class="sub"><span>ردیف‌ها</span><button class="b o sm" data-a="mbrow2add">${IC.plus}ردیف</button></div>
      ${(x.rows || []).map((r, ri) => `<div class="rl"><div class="cmd">${r.map((c, ci) => `<input class="fa tb-c" data-r="${ri}" data-c="${ci}" value="${esc(c)}" maxlength="60">`).join("")}<button class="iconb sm" data-a="mbrow2del" data-r="${ri}" aria-label="حذف ردیف" style="color:var(--bad)">${IC.x}</button></div></div>`).join("")}`;
  }
  h += mbLayoutSheet(x);
  h += `<div class="bar"><button class="b" data-sh="save">ذخیره</button></div>`;
  setTimeout(() => window.__mbPaintDo && window.__mbPaintDo(), 0);
  return h;
}
/* چیدمان بصری مشترک همه‌ی بلوک‌ها */
function mbLayoutSheet(x){
  const st = x.st || {};
  return `<details class="adv"><summary>چیدمان و ظاهر</summary><div class="box">
    <span class="lbl">ستون‌بندی</span><div class="sws">${[[null, "خودکار"], [1, "۱"], [2, "۲"], [3, "۳"]].map(([v, l]) => `<button type="button" class="sw${(st.cols || null) === v ? " on" : ""}" data-a="mbstc" data-v="${v == null ? "" : v}">${l}</button>`).join("")}</div>
    <span class="lbl">پس‌زمینه</span><div class="sws">${[["", "بدون"], ["soft", "ملایم"], ["card", "کارت"], ["grad", "گرادیان"]].map(([v, l]) => `<button type="button" class="sw${(st.bg || "") === v ? " on" : ""}" data-a="mbstb" data-v="${v}">${l}</button>`).join("")}</div>
    <span class="lbl">گردی گوشه‌ها: ${N(st.rad || 0)}</span><input type="range" min="0" max="28" value="${st.rad || 0}" data-a="mbstra" aria-label="گردی">
    <span class="lbl">فاصله‌ی داخلی آیتم‌ها: ${N(st.gap || 0)}</span><input type="range" min="0" max="24" value="${st.gap || 0}" data-a="mbstg" aria-label="فاصله">
    <label class="chk"><input type="checkbox" id="g-stsh"${st.shadow ? " checked" : ""}> سایه</label>
    <span class="lbl">انیمیشن ورود</span><div class="sws">${[["", "بدون"], ["fade", "محو"], ["up", "از پایین"]].map(([v, l]) => `<button type="button" class="sw${(st.anim || "") === v ? " on" : ""}" data-a="mbsta" data-v="${v}">${l}</button>`).join("")}</div>
  </div></details>`;
}
const _bpropSheet0 = bpropSheet;
bpropSheet = function(){
  const x = D;
  if(MB_SCHEMA[x.t]) return mbGenSheet(x);
  return _bpropSheet0();
};
function mbGenRead(x){
  const sch = MB_SCHEMA[x.t], g = k => $("#g-" + k)?.value;
  if(sch.plain) for(const [k] of sch.plain){ if(g(k) != null) x[k] = g(k); }
  if(sch.sel) for(const [k] of sch.sel){ if($("#g-" + k)) x[k] = $("#g-" + k).value; }
  if(sch.num) for(const [k, , lo] of sch.num){ if($("#g-" + k)) x[k] = Math.max(lo, Math.min((sch.num.find(z => z[0] === k)[3]), +$("#g-" + k).value || lo)); }
  if(sch.chk2) for(const [k] of sch.chk2){ if($("#g-" + k)) x[k] = $("#g-" + k).checked; }
  if(sch.media){ if(D.media !== undefined) x.media = D.media; const u = $("#g-url"); if(u) x.url = u.value.trim(); }
  if(sch.media2){ if(D.media !== undefined) x.media = D.media; if(D.media2 !== undefined) x.media2 = D.media2;
    const u = $("#g-url"), u2 = $("#g-url2"); if(u) x.url = u.value.trim(); if(u2) x.url2 = u2.value.trim(); }
  if(sch.mediaList){
    x.items.forEach((it, i) => { if(D["gi" + i] !== undefined) it.media = D["gi" + i]; const u = $("#g-gi-" + i); if(u) it.url = u.value.trim();
      const l = document.querySelector(`.g2lab[data-i="${i}"]`); if(l) it.label = l.value; });
  }
  if(sch.items){
    x.items.forEach((it, i) => {
      document.querySelectorAll(`.it-f[data-i="${i}"]`).forEach(inp => { it[inp.dataset.k] = inp.value; });
      document.querySelectorAll(`.it-c[data-i="${i}"]`).forEach(cb => { it[cb.dataset.k] = cb.checked; });
      if(D["it" + i] !== undefined) it.media = D["it" + i];
    });
  }
  if(sch.act) for(const [btnK] of sch.act){ if(btnK && $("#g-" + btnK)) x[btnK] = $("#g-" + btnK).value; }
  if(sch.table){
    x.head = [...document.querySelectorAll(".tb-h")].map(i2 => i2.value.trim()).filter(Boolean);
    const rows = {};
    document.querySelectorAll(".tb-c").forEach(inp => { const r = +inp.dataset.r; (rows[r] = rows[r] || [])[+inp.dataset.c] = inp.value; });
    x.rows = Object.keys(rows).sort((a, b) => a - b).map(r => { const row = rows[r]; while(row.length < x.head.length) row.push(""); return row.slice(0, x.head.length); });
  }
  if(g("stsh")) void 0;
}
const _bpropRead0 = bpropRead;
bpropRead = function(){
  if(MB_SCHEMA[D.t]) return mbGenRead(D);
  return _bpropRead0();
};
const _bpropSave0 = bpropSave;
bpropSave = function(){
  const t = D.t, sch = MB_SCHEMA[t];
  if(!sch) return _bpropSave0();
  if(sch.items){
    D.items = (D.items || []).filter(it => (sch.items.f || []).some(([k]) => String(it[k] ?? "").trim()));
    if(!D.items.length && t !== "checkin") return toast("حداقل یک آیتم لازم است");
  }
  if(t === "table" && (!(D.head || []).length || !(D.rows || []).length)) return toast("جدول حداقل یک ستون و یک ردیف لازم دارد");
  if(t === "heading" && !(D.text || "").trim()) return toast("متن تیتر را بنویس");
  if((t === "copytext" || t === "marquee" || t === "discount") && !(String(D.text || D.code || "")).trim()) return toast("متن را بنویس");
  if(t === "product" && !(D.title || "").trim()) return toast("نام محصول را بنویس");
  if(t === "chart" && (!D.table || !D.field)) return toast("نام جدول و فیلد عددی لازم است");
  if((t === "progress" || t === "xpbar" || t === "countup" || t === "pollstat" || t === "statrow")
     && ((t === "statrow" || t === "pollstat") ? !(D.items || []).length : !D.var)) return toast("نام متغیر یا آیتم لازم است");
  if((t === "slider") && (D.items || []).length < 2) return toast("اسلایدر حداقل دو تصویر لازم دارد");
  if(t === "cart" || t === "pricing" || t === "booking"){
    const key = t === "cart" ? "do" : null;
    if(t === "pricing") D.items.forEach(it => { if(!it.do?.length) delete it.hid; });
    if(t === "booking") D.items.forEach(it => { if(!it.do?.length) delete it.hid; });
    void key;
  }
  const i = +MB._editI;
  const arr = MB.draft.screens[MB.screen].blocks;
  arr[i] = JSON.parse(JSON.stringify(D));
  mbPush(); mbTouch();
  closeSheet();
  mbPaintBlocks();
  mbPostPreview();
  toast("ذخیره شد");
};
const _mbDoArrPaint = () => {
  document.querySelectorAll(".mbdo").forEach(box => {
    const key = box.dataset.k;
    const arr = key === "." ? D : key.split(".").reduce((o, k) => (o || {})[k], D) || [];
    box.innerHTML = arr.map((a, i) => mbGenDoRow(a, key, i)).join("");
  });
};
function mbGenDoRow(a, key, i){
  const op = a.op || "goto";
  const scr = mbScreenIds();
  const lab = {goto: "رفتن به صفحه", url: "باز کردن لینک", copy: "کپی", share: "اشتراک", toast: "پیام کوتاه", close: "بستن", back: "بازگشت", refresh: "تازه‌سازی", send: "ارسال بخش ربات به چت", set: "تنظیم متغیر", add: "افزودن به متغیر", clear: "پاک کردن متغیر", random: "عدد تصادفی", notify: "خبر به من", remind: "یادآوری"}[op] || op;
  let body = "";
  if(op === "goto") body = `<select class="d-scr">${scr.map(s2 => `<option value="${esc(s2)}"${s2 === a.screen ? " selected" : ""}>${esc(MB.draft.screens[s2].title || s2)}</option>`).join("")}</select>`;
  else if(op === "url") body = `<input class="fa d-url" value="${esc(a.url || "")}" placeholder="https://... یا @channel">`;
  else if(op === "copy" || op === "share" || op === "toast") body = `<input class="fa d-txt" value="${esc(a.text || "")}" placeholder="متن" maxlength="200">`;
  else if(op === "send") body = `<input class="fa d-node" value="${esc(a.node || "")}" placeholder="شناسه‌ی بخش ربات" maxlength="30">`;
  else if(op === "set" || op === "add" || op === "random") body = `<input class="fa d-var" value="${esc(a.var || "")}" placeholder="متغیر" maxlength="20"><input class="fa d-val" value="${esc(a.value ?? "")}" placeholder="${op === "random" ? "1-6" : "مقدار"}" maxlength="100">`;
  else if(op === "notify") body = `<input class="fa d-val" value="${esc(a.value || "")}" placeholder="پیام برای خودت" maxlength="200">`;
  else body = `<span class="muted">${lab}</span>`;
  return `<div class="rl" data-i="${i}"><div class="cmd" style="justify-content:space-between"><b>${lab}</b><button class="iconb sm" data-a="mbdodel" data-k="${key}" data-i="${i}" aria-label="حذف">${IC.x}</button></div>
    <select class="d-op">${[["goto", "رفتن به صفحه"], ["url", "باز کردن لینک"], ["copy", "کپی"], ["share", "اشتراک"], ["toast", "پیام کوتاه"], ["back", "بازگشت"], ["refresh", "تازه‌سازی"], ["close", "بستن مینی‌اپ"], ["send", "ارسال بخش ربات به چت"], ["set", "تنظیم متغیر"], ["add", "افزودن به متغیر"], ["clear", "پاک کردن متغیر"], ["random", "عدد تصادفی"], ["notify", "خبر به من"], ["remind", "یادآوری"]].map(([v, l]) => `<option value="${v}"${v === op ? " selected" : ""}>${l}</option>`).join("")}</select>
    ${body}</div>`;
}
window.__mbPaintDo = _mbDoArrPaint;

/* ── ۱۲ تم آماده ── */
const MB_THEMES = [
  ["فیروزه‌ای", "#3CCFE3", 16], ["بنفش", "#6C5CE7", 18], ["سبز جنگلی", "#168A5B", 14],
  ["طلایی", "#E39A00", 16], ["قرمز پرانرژی", "#CC3547", 18], ["آبی اقیانوس", "#2F7CF6", 16],
  ["نارنجی", "#F0742E", 20], ["صورتی", "#E0619C", 22], ["سرمه‌ای", "#274690", 12],
  ["زمرد", "#0E9F7E", 14], ["قهوه‌ای قهوه‌خانه", "#8A5A2B", 12], ["مشکی مینیمال", "#20262B", 8],
];
function bthemeSheet2(){
  const th = MB.draft.theme;
  const presets = MB_THEMES.map(([l, c, r]) => `<button type="button" class="sw ${th.accent?.toLowerCase() === c.toLowerCase() ? "on" : ""}" style="background:${c};color:#fff" data-a="mbth" data-c="${c}" data-r="${r}">${l}</button>`).join("");
  return head("تم و ظاهر") + `
    <span class="lbl">حالت</span><select id="t-mode">${[["auto", "خودکار (هماهنگ با تلگرام)"], ["dark", "تیره"], ["light", "روشن"]].map(([v, l]) => `<option value="${v}"${th.mode === v ? " selected" : ""}>${l}</option>`).join("")}</select>
    <span class="lbl">۱۲ تم آماده</span><div class="sws th12">${presets}</div>
    <span class="lbl">رنگ اصلی (دلخواه)</span><input id="t-accent" value="${esc(th.accent || "#3CCFE3")}" maxlength="7" class="ltr" placeholder="#3CCFE3">
    <input type="file" id="t-logo" accept="image/*" hidden>
    <button type="button" class="b o sm" data-a="mbpal">${IC.image}پالت رنگ از لوگو</button>
    <p class="muted mt">لوگوی برندت را انتخاب کن تا سه رنگ اصلی‌اش را پیدا کنیم. روی هر رنگ بزن تا رنگ اصلیِ مینی‌اپ شود.</p>
    <div class="sws" id="t-palout"></div>
    <span class="lbl">فونت</span><select id="t-font">${[["vazir", "وزیرمتن (پیش‌فرض)"], ["oxanium_vazir", "عددهای رباتیک (Oxanium)"], ["system", "فونت خود گوشی"]].map(([v, l]) => `<option value="${v}"${th.font === v ? " selected" : ""}>${l}</option>`).join("")}</select>
    <span class="lbl">گردی گوشه‌ها (۰ تا ۲۸)</span><input id="t-rad" type="number" min="0" max="28" value="${esc(th.radius ?? 16)}">
    <span class="lbl">رقم‌ها</span><select id="t-digits"><option value="latin"${th.digits !== "fa" ? " selected" : ""}>انگلیسی</option><option value="fa"${th.digits === "fa" ? " selected" : ""}>فارسی</option></select>
    <p class="muted mt">رنگ متن روی دکمه‌ها خودکار طوری انتخاب می‌شود که خوانا باشد.</p>
    <div class="bar"><button class="b" data-sh="save">ذخیره</button></div>`;
}
const _bthemeSheet0 = bthemeSheet;
bthemeSheet = function() { return bthemeSheet2(); };

/* ── ویرایشگر منو (نوع، سبک، آیکن‌ها، ترتیب) ── */
function bnavSheet(){
  const nv = MB.draft.nav || {type: "tabs", items: []};
  D = {type: nv.type || "tabs", style: nv.style || "simple", icons: !!nv.icons, items: [...(nv.items || [])]};
  const opts = mbScreenIds().filter(id2 => id2 !== MB.draft.home);
  return head("منوی مینی‌اپ") + `
    <p class="muted">ناوبری مینی‌اپ را همین‌جا عوض کن؛ پیش‌نمایش همان لحظه عوض می‌شود.</p>
    <span class="lbl">جای منو</span><div class="sws">${[["tabs", "نوار پایین"], ["top", "نوار بالا"], ["none", "بدون منو"]].map(([v, l]) => `<button type="button" class="sw${D.type === v ? " on" : ""}" data-a="mbnv2" data-k="type" data-v="${v}">${l}</button>`).join("")}</div>
    <span class="lbl">سبک</span><div class="sws">${[["simple", "ساده"], ["glass", "شیشه‌ای"], ["round", "گرد شناور"], ["island", "جزیره"]].map(([v, l]) => `<button type="button" class="sw${D.style === v ? " on" : ""}" data-a="mbnv2" data-k="style" data-v="${v}">${l}</button>`).join("")}</div>
    <label class="chk"><input type="checkbox" id="nv-icons"${D.icons ? " checked" : ""}> فقط آیکن (بدون نوشته)</label>
    <div class="sub"><span>صفحه‌های منو (با فلش‌ها جابه‌جا کن)</span></div>
    ${D.items.length ? D.items.map((id2, i) => `<div class="cmd"><span class="ib">${IC[MB_IC[(MB.draft.screens[id2] || {}).icon] || "home"] || IC.layers}</span><span class="gt" style="flex:1"><b>${esc((MB.draft.screens[id2] || {}).title || id2)}</b></span>
      <button class="iconb sm" data-a="mbnvup" data-i="${i}" aria-label="بالا" ${i === 0 ? "disabled" : ""}>${MB_UP}</button>
      <button class="iconb sm" data-a="mbnvdown" data-i="${i}" aria-label="پایین" ${i === D.items.length - 1 ? "disabled" : ""}>${MB_DOWN}</button>
      <button class="iconb sm" data-a="mbnvrm" data-i="${i}" aria-label="برداشتن" style="color:var(--bad)">${IC.x}</button></div>`).join("")
      : `<p class="muted">منو خالی است؛ صفحه‌ها را اضافه کن.</p>`}
    <div class="sub"><span>افزودن صفحه</span></div>
    <div class="chips">${opts.filter(id2 => !D.items.includes(id2)).map(id2 => `<button class="chip" data-a="mbnvadd" data-id="${esc(id2)}">${IC.plus}${esc((MB.draft.screens[id2] || {}).title || id2)}</button>`).join("") || '<span class="muted">صفحه‌ی دیگری نیست.</span>'}</div>
    <p class="muted mt">صفحه‌ی شروع (${esc((MB.draft.screens[MB.draft.home] || {}).title || "خانه")}) همیشه در مینی‌اپ باز می‌شود و لازم نیست در منو باشد.</p>
    <div class="bar"><button class="b" data-sh="save">ذخیره</button></div><div class="fgap"></div>`;
}
function bnavRead(){
  D.icons = $("#nv-icons") ? $("#nv-icons").checked : D.icons;
}
function bnavSave(){
  MB.draft.nav = {type: D.type === "none" ? "none" : D.type, style: D.style, icons: D.icons, items: D.items};
  mbPush(); mbTouch(); closeSheet(); mbPaintScreens(); mbPostPreview(); toast("منو ذخیره شد");
}
SHEETS.bnav = {html: bnavSheet, read: bnavRead, save: bnavSave};
/* مرجع‌های شیت که builder.js هنگام لود گرفته بود، به نسخه‌های گسترش‌یافته به‌روزرسانی می‌شوند */
SHEETS.bp.html = bpSheet;
SHEETS.bprop = {html: bpropSheet, read: bpropRead, save: bpropSave};
function bthemeRead2(){
  const f = $("#t-font");
  if(f) MB.draft.theme.font = f.value;
  bthemeRead();
}
SHEETS.btheme = {html: bthemeSheet, read: bthemeRead2, save: bthemeSave};

/* ── اکشن‌ها ── */
Object.assign(A, {
  mbnav2: () => { S.sheet = {kind: "bnav"}; D = null; renderSheet(); },
  mbnv2: el2 => { readSheet(); D[el2.dataset.k] = el2.dataset.v; renderSheet(); },
  mbnvadd: el2 => { readSheet(); if(D.items.length >= 5) return toast("منو حداکثر ۵ صفحه دارد"); D.items.push(el2.dataset.id); renderSheet(); },
  mbnvrm: el2 => { readSheet(); D.items.splice(+el2.dataset.i, 1); renderSheet(); },
  mbnvup: el2 => { readSheet(); const i = +el2.dataset.i; if(i <= 0) return; [D.items[i - 1], D.items[i]] = [D.items[i], D.items[i - 1]]; renderSheet(); },
  mbnvdown: el2 => { readSheet(); const i = +el2.dataset.i; if(i >= D.items.length - 1) return; [D.items[i + 1], D.items[i]] = [D.items[i], D.items[i + 1]]; renderSheet(); },
  mbth: el2 => { const i = $("#t-accent"); if(i){ i.value = el2.dataset.c; const r = $("#t-rad"); if(r) r.value = el2.dataset.r; document.querySelectorAll(".sws.th12 .sw.on").forEach(x => x.classList.remove("on")); el2.classList.add("on"); } },
  mbpal: () => { const f = $("#t-logo"); if(f) f.click(); },
  mbpalset: el2 => { const i = $("#t-accent"); if(i) i.value = el2.dataset.c; document.querySelectorAll("#t-palout .sw").forEach(x => x.classList.remove("on")); el2.classList.add("on"); },
  mbcomp: el2 => {
    const i = +el2.dataset.i;
    const blk = JSON.parse(JSON.stringify((MB.draft.screens[MB.screen].blocks || [])[i]));
    if(!blk) return;
    const comps = mbComps();
    if((comps.length || 0) >= 12) return toast("حداکثر ۱۲ قطعه ذخیره می‌شود؛ یکی را پاک کن");
    const name = (MB_T[blk.t] || blk.t) + " " + ((comps.length || 0) + 1);
    busy(el2, async () => {
      await api("/api/comps", "POST", {name, b: blk});
      MB._comps = undefined; mbComps();
      toast("قطعه ذخیره شد و روی همه‌ی دستگاه‌هایت در دسترس است"); haptic("ok");
    });
  },
  mbcompins: el2 => {
    const c = mbComps()[+el2.dataset.i];
    if(!c) return;
    if((MB.draft.screens[MB.screen].blocks || []).length >= (MB.caps.blocks || 30)) return toast("سقف بلوک اشتراکت پر شده");
    const blk = JSON.parse(JSON.stringify(c.b));
    blk.id = mbBlockId();
    (MB.draft.screens[MB.screen].blocks = MB.draft.screens[MB.screen].blocks || []).push(blk);
    mbPush(); mbTouch(); closeSheet(); mbPaintBlocks(); mbPostPreview(); toast("قطعه اضافه شد");
  },
  mbcompdel: el2 => busy(el2, async () => {
    const c = mbComps()[+el2.dataset.i];
    if(c) await api("/api/comps/" + encodeURIComponent(c.id), "DELETE");
    MB._comps = undefined;
    S.sheet = {kind: "bp"}; renderSheet();
  }),
  mbstc: el2 => { D.st = D.st || {}; D.st.cols = el2.dataset.v ? +el2.dataset.v : null; renderSheet(); },
  mbstb: el2 => { D.st = D.st || {}; D.st.bg = el2.dataset.v || null; renderSheet(); },
  mbsta: el2 => { D.st = D.st || {}; D.st.anim = el2.dataset.v || null; renderSheet(); },
  mbstra: el2 => { D.st = D.st || {}; D.st.rad = +el2.value; el2.previousElementSibling && (el2.previousElementSibling.textContent = "گردی گوشه‌ها: " + el2.value); },
  mbstg: el2 => { D.st = D.st || {}; D.st.gap = +el2.value; el2.previousElementSibling && (el2.previousElementSibling.textContent = "فاصله‌ی داخلی آیتم‌ها: " + el2.value); },
  mbitadd: () => { const sch = MB_SCHEMA[D.t]; if((D.items || []).length >= sch.items.cap) return; (D.items = D.items || []).push({}); if(window.__mbPaintDo) window.__mbPaintDo(); renderSheet(); },
  mbitdel: el2 => { D.items.splice(+el2.dataset.i, 1); renderSheet(); },
  mbg2add: () => { const sch = MB_SCHEMA[D.t]; if((D.items || []).length >= sch.mediaList.cap) return; D.items.push({}); renderSheet(); },
  mbg2del: el2 => { D.items.splice(+el2.dataset.i, 1); renderSheet(); },
  mbcoladd: () => { if((D.head || []).length >= 6) return; D.head = D.head || []; D.head.push("ستون " + (D.head.length + 1)); D.rows.forEach(r => r.push("")); renderSheet(); },
  mbrow2add: () => { D.rows = D.rows || []; D.rows.push((D.head || []).map(() => "")); renderSheet(); },
  mbrow2del: el2 => { D.rows.splice(+el2.dataset.r, 1); renderSheet(); },
});
/* نوار صفحه‌ها: چیپ «منو» + ردیف بلوک‌ها: دکمه‌ی «قطعه» */
const _origMbPaintScreens = mbPaintScreens;
mbPaintScreens = function(){
  _origMbPaintScreens();
  const bar = $("#bscr");
  if(bar && !bar.querySelector("[data-a='mbnav2']")){
    bar.insertAdjacentHTML("beforeend", `<button class="chip" data-a="mbnav2">${IC.layers}منو</button>`);
  }
};
const _origMbPaintBlocks2 = mbPaintBlocks;
mbPaintBlocks = function(){
  _origMbPaintBlocks2();
  document.querySelectorAll("#bblocks .bops").forEach(ops => {
    const cp = ops.querySelector("[data-a='mbcp']");
    if(cp && !ops.querySelector("[data-a='mbcomp']")){
      cp.insertAdjacentHTML("afterend", `<button class="iconb sm" data-a="mbcomp" data-i="${esc(cp.dataset.i)}" aria-label="ذخیره به‌عنوان قطعه" title="ذخیره به‌عنوان قطعه">${IC.star}</button>`);
    }
  });
};
/* جستجوی گالری + اسلایدرهای چیدمان */
document.addEventListener("input", e => {
  if(e.target.id === "bp-q"){ MB._q2 = e.target.value; const cur = e.target.selectionStart; renderSheet(); const q = $("#bp-q"); if(q){ q.focus(); q.setSelectionRange(cur, cur); } }
  const da = e.target.dataset?.a;
  if(da === "mbstra" || da === "mbstg") A[da](e.target);
});

/* ── پالت رنگ از لوگو: استخراج سه رنگ غالب از تصویر (بدون سرور) ── */
document.addEventListener("change", e => {
  if(e.target.id !== "t-logo") return;
  const f = e.target.files && e.target.files[0];
  if(!f) return;
  const img = new Image(), url = URL.createObjectURL(f);
  img.onload = () => {
    try{
      const cv = document.createElement("canvas");
      cv.width = cv.height = 48;
      const cx = cv.getContext("2d");
      cx.drawImage(img, 0, 0, 48, 48);
      const d = cx.getImageData(0, 0, 48, 48).data;
      const buckets = {};
      for(let i = 0; i < d.length; i += 4){
        const a = d[i + 3];
        if(a < 128) continue;
        const r = d[i], g = d[i + 1], b = d[i + 2];
        const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
        const sat = mx === 0 ? 0 : (mx - mn) / mx;
        if(mx > 245 && sat < 0.06) continue;                      // پس‌زمینه‌ی سفید
        if(mx < 24) continue;                                     // سیاه کامل
        const k = (r >> 4) + "," + (g >> 4) + "," + (b >> 4);
        const bk = buckets[k] || (buckets[k] = {n: 0, r: 0, g: 0, b: 0});
        bk.n++; bk.r += r; bk.g += g; bk.b += b;
      }
      const cand = Object.values(buckets).map(bk => {
        const r = Math.round(bk.r / bk.n), g = Math.round(bk.g / bk.n), b = Math.round(bk.b / bk.n);
        const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
        return {c: "#" + [r, g, b].map(x => x.toString(16).padStart(2, "0")).join(""), score: bk.n * (0.25 + (mx - mn) / mx || 0)};
      }).sort((a, b) => b.score - a.score).slice(0, 3);
      const out = $("#t-palout");
      if(out) out.innerHTML = cand.length ? cand.map(x => `<button type="button" class="sw" style="background:${x.c};color:#fff" data-a="mbpalset" data-c="${x.c}">${x.c}</button>`).join("") : '<span class="muted">رنگی پیدا نشد؛ لوگویی با کیفیت بهتر انتخاب کن.</span>';
      if(cand.length){ const i = $("#t-accent"); if(i) i.value = cand[0].c; }
    }catch(_){ toast("خواندن تصویر ناموفق بود"); }
    URL.revokeObjectURL(url);
  };
  img.onerror = () => { toast("تصویر باز نشد"); URL.revokeObjectURL(url); };
  img.src = url;
  e.target.value = "";
});
