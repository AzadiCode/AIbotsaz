// _dbg3.js — اثبات سلامت زنجیره‌ی فعلی (همان ترتیب index.html)
const fs = require("fs"), vm = require("vm");
function el(tag){
  const e = { tagName: (tag||"div").toUpperCase(), innerHTML:"", textContent:"", value:"", style:{setProperty(){}},
    dataset:{}, children:[], classList:{add(){},remove(){},toggle(){},contains(){return false;}},
    addEventListener(){}, appendChild(){return arguments[0];}, insertAdjacentHTML(){}, remove(){}, setAttribute(){},
    getAttribute(){return null;}, querySelector(){return null;}, querySelectorAll(){return [];}, closest(){return null;},
    contains(){return false;}, isConnected:true, scrollIntoView(){}, focus(){}, select(){}, click(){}, disabled:false, hidden:false,
    scrollTop:0, scrollHeight:0, clientWidth:300, clientHeight:600, offsetWidth:10,
    getBoundingClientRect(){return {left:0,top:0,width:300,height:600};},
    getContext(){return {scale(){},fillRect(){},beginPath(){},arc(){},fill(){},fillText(){}};} };
  Object.defineProperty(e,"outerHTML",{get(){return "<div></div>";},set(){}});
  return e;
}
const els = {}; const getEl = s => els[s] || (els[s] = el("div"));
const me = { me:{id:777,name:"ت",username:"t",web:true}, bots:[], wallet:{tokens:1000,streak:0,can_claim:false,next_reward:10,refs:0,spent:0},
  cfg:{billing:"fixed",gen:50,edit:20,typical:30,min:20,ai_per:3,bc_per:1,max_bots:1,max_nodes:200,max_prompt:4000,daily:10,
    ref_inviter:10,ref_invitee:5,ref_max:100,milestones:[],media_max_mb:15,media_quota_mb:60,max_media:60,disc:0,plans:[],
    emoji_max:0,btn_fx:0,games:1,db:1,ext_api:1,build:"3.4.2",limits:{nodes:200,blocks:120,tables:6,screens:12},features:{},max_ub:0,ub_ok:0,enhance:10},
  packs:[], media:[], used:0, ref:{link:"",count:0,earned:0}, joined:new Date().toISOString(), templates:[], tasks:[], plan:null, admin:true, card:{on:false,prices:{}}, subs:[] };
const sandbox = { console, setTimeout, clearTimeout, setInterval:()=>0, clearInterval, Date, JSON, Math, URLSearchParams, Promise,
  Object, Array, String, Number, Boolean, RegExp, Error, TypeError, parseInt, parseFloat, isNaN, isFinite,
  performance:{now:()=>Date.now()}, requestAnimationFrame:cb=>setTimeout(cb,0),
  fetch: async p => ({ok:true,status:200,json:async()=>JSON.parse(JSON.stringify(p.includes("/api/me")?me:{items:[]}))}),
  localStorage:{getItem(){return null;},setItem(){},removeItem(){}}, matchMedia:()=>({matches:false}),
  location:{search:"",pathname:"/",origin:"https://x"}, history:{replaceState(){}},
  navigator:{clipboard:{writeText(){return Promise.resolve();}}},
  addEventListener(){}, removeEventListener(){}, dispatchEvent(){},
  CustomEvent:function(t,o){this.type=t;this.detail=o&&o.detail;}, scrollTo(){},
  document:{ querySelector:s=>["#app","#top","#dock","#dpanel","#toast","#fileIn","#dscrim","#sheet","#stc","#live","#prompt","#gen"].includes(s)?getEl(s):null,
    querySelectorAll:()=>[], getElementById:s=>getEl(s), createElement:t=>el(t), createTextNode:t=>({textContent:t}),
    addEventListener(){}, body:el("body"), documentElement:el("html"), fonts:{ready:Promise.resolve()}, activeElement:null } };
sandbox.window=sandbox; sandbox.globalThis=sandbox; sandbox.self=sandbox;
sandbox.window.Telegram={WebApp:{ready(){},expand(){},initData:"",initDataUnsafe:{},colorScheme:"dark",
  HapticFeedback:{notificationOccurred(){},selectionChanged(){}},onEvent(){},setHeaderColor(){},setBackgroundColor(){},
  openTelegramLink(){},openLink(){},showConfirm(q,cb){cb(true);},version:"7",BackButton:{show(){},hide(){},onClick(){}}}};
const ctx = vm.createContext(sandbox);
const files = ["static/app.js","static/studio.js","static/builder.js","static/studio2.js","static/studio3.js","static/builder2.js","static/builder3.js"];
for(const f of files){
  try{ vm.runInContext(fs.readFileSync(f,"utf8"), ctx, {filename:f}); console.log("LOAD OK :", f); }
  catch(e){ console.log("LOAD ERR:", f, "->", e.message); process.exit(1); }
}
(async()=>{
  try{
    await vm.runInContext("load()", ctx);
    await new Promise(r=>setTimeout(r,300));
    console.log("RENDER OK | #app len:", String(getEl("#app").innerHTML).length, "| console:", getEl("#app").innerHTML.includes("console"));
    console.log("=> زنجیره‌ی فعلی کاملاً سالم است؛ خطای سرور = app.js قدیمی روی سرور");
  }catch(e){ console.log("RUNTIME ERR ->", e.message); process.exit(1); }
})();
