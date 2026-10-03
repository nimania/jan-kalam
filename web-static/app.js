/* جان‌کلام — static build. Reads pre-generated JSON from ./data (no backend). */
const DATA = "data";

const CAT_FA = { iran: "ایران", world: "جهان", politics: "سیاست", economy: "اقتصاد",
  technology: "فناوری", ai: "هوش مصنوعی", culture: "فرهنگ", sport: "ورزش", science: "علم", environment: "محیط‌زیست", entertainment: "سرگرمی", health: "سلامت" };
const IRAN_FA = { high: "ارتباط بالا با ایران", medium: "ارتباط با ایران",
  low: "ارتباط کم با ایران", none: "بدون ارتباط مستقیم با ایران" };
const CRED_FA = { high: "اعتبار بالا", medium: "چند منبع", low: "تک‌منبع" };
const CRED_CLS = { high: "st-ok", medium: "st-neutral", low: "st-warn" };
const faN = s => String(s).replace(".", "٫").replace(/\d/g, d => "۰۱۲۳۴۵۶۷۸۹"[d]);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function impInfo(v) {
  if (v >= 75) return { cls: "high", lbl: "بسیار مهم" };
  if (v >= 50) return { cls: "mid", lbl: "مهم" };
  return { cls: "low", lbl: "متوسط" };
}
function relTime(iso) {
  if (!iso) return "";
  // Build timestamps are UTC but may omit the timezone suffix. Without one,
  // new Date() parses them as the viewer's LOCAL time (e.g. +3:30 in Tehran),
  // so every item looked ~3.5h old. Force UTC when no offset is present.
  if (typeof iso === "string" && !/(Z|[+-]\d\d:?\d\d)$/.test(iso)) iso += "Z";
  const mins = Math.floor((Date.now() - new Date(iso)) / 6e4);
  if (mins < 1) return "همین حالا";
  if (mins < 60) return faN(mins) + " دقیقه پیش";
  const h = Math.floor(mins / 60);
  if (h < 24) return faN(h) + " ساعت پیش";
  const d = Math.floor(h / 24);
  return d === 1 ? "دیروز" : faN(d) + " روز پیش";
}
async function getJSON(path, timeoutMs = 12000) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetch(path, { cache: "no-cache", signal: ctl.signal });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return await r.json();
  } finally { clearTimeout(timer); }
}

const VIEWS = { feed: "feed-view", detail: "detail-view", trends: "trends-view",
  factchecks: "factchecks-view", topics: "topics-view", topicarchive: "topic-archive-view",
  weather: "weather-view", iran: "iran-view", faq: "faq-view", market: "market-view",
  figures: "figures-view", press: "press-view", tech: "tech-view" };
const TABS = ["feed", "trends", "factchecks", "iran", "topics"];
const SCOPE_FA = { local: "استانی", national: "کشوری", international: "بین‌المللی" };
function setTab(w) { for (const t of TABS) document.getElementById("tab-" + t).classList.toggle("active", w === t); }
function show(v) {
  for (const [key, id] of Object.entries(VIEWS))
    document.getElementById(id).style.display = key === v ? "block" : "none";
  window.scrollTo({ top: 0, behavior: "instant" });
}
function showFeed() { show("feed"); setTab("feed"); setHash(""); }
function showTopics() { show("topics"); setTab("topics"); renderTopics(); setHash("#/topics"); }
function showTrends() { show("trends"); setTab("trends"); renderTrends(); setHash("#/trends"); }
function showFactchecks() { show("factchecks"); setTab("factchecks"); renderFactchecks(); setHash("#/fact"); }
function showFaq() { show("faq"); setTab("faq"); renderFaq(); setHash("#/faq"); }

let periodicalRows = [];
let pressScope = "all";
let pressLanguage = "all";
let pressStatsCache = null;
let pressHealthCache = null;

const PRESS_SOURCES = [
  // خبرگزاری‌ها و رسانه‌های خبری داخل ایران
  {name:"ایرنا", aliases:["خبرگزاری ایرنا (IRNA)"], domain:"irna.ir", scope:"iran-agency", lang:"fa", type:"خبرگزاری"},
  {name:"ایسنا", aliases:["خبرگزاری ایسنا (ISNA)"], domain:"isna.ir", scope:"iran-agency", lang:"fa", type:"خبرگزاری"},
  {name:"مهر", aliases:["خبرگزاری مهر (Mehr)"], domain:"mehrnews.com", scope:"iran-agency", lang:"fa", type:"خبرگزاری"},
  {name:"فارس", aliases:["خبرگزاری فارس (Fars)"], domain:"farsnews.ir", scope:"iran-agency", lang:"fa", type:"خبرگزاری"},
  {name:"خبرگزاری صداوسیما", domain:"iribnews.ir", scope:"iran-agency", lang:"fa", type:"خبرگزاری"},
  {name:"باشگاه خبرنگاران جوان", domain:"yjc.ir", scope:"iran-agency", lang:"fa", type:"خبرگزاری"},
  {name:"خبرآنلاین", domain:"khabaronline.ir", scope:"iran-agency", lang:"fa", type:"رسانه خبری"},
  {name:"تابناک", domain:"tabnak.ir", scope:"iran-agency", lang:"fa", type:"رسانه خبری"},
  {name:"فرارو", domain:"fararu.com", scope:"iran-agency", lang:"fa", type:"رسانه خبری"},
  {name:"انتخاب", domain:"entekhab.ir", scope:"iran-agency", lang:"fa", type:"رسانه خبری"},
  {name:"عصر ایران", domain:"asriran.com", scope:"iran-agency", lang:"fa", type:"رسانه خبری"},
  {name:"فردانیوز", domain:"fardanews.com", scope:"iran-agency", lang:"fa", type:"رسانه خبری"},
  {name:"رویداد۲۴", domain:"rouydad24.ir", scope:"iran-agency", lang:"fa", type:"رسانه خبری"},
  {name:"آفتاب‌نیوز", domain:"aftabnews.ir", scope:"iran-agency", lang:"fa", type:"رسانه خبری"},
  {name:"مشرق نیوز", domain:"mashreghnews.ir", scope:"iran-agency", lang:"fa", type:"رسانه خبری"},
  {name:"انصاف نیوز", domain:"ensafnews.com", scope:"iran-agency", lang:"fa", type:"رسانه خبری"},

  // روزنامه‌ها و مطبوعات داخل ایران
  {name:"همشهری", aliases:["همشهری آنلاین"], domain:"hamshahrionline.ir", scope:"iran-paper", lang:"fa", type:"روزنامه"},
  {name:"پیام ما", aliases:["روزنامه پیام‌ما"], domain:"payamema.ir", scope:"iran-paper", lang:"fa", type:"روزنامه"},
  {name:"شرق", domain:"sharghdaily.com", scope:"iran-paper", lang:"fa", type:"روزنامه"},
  {name:"اعتماد", domain:"etemadonline.com", scope:"iran-paper", lang:"fa", type:"روزنامه"},
  {name:"دنیای اقتصاد", domain:"donya-e-eqtesad.com", scope:"iran-paper", lang:"fa", type:"روزنامه"},
  {name:"اطلاعات", domain:"ettelaat.com", scope:"iran-paper", lang:"fa", type:"روزنامه"},
  {name:"کیهان", domain:"kayhan.ir", scope:"iran-paper", lang:"fa", type:"روزنامه"},
  {name:"جمهوری اسلامی", domain:"jomhourieslami.net", scope:"iran-paper", lang:"fa", type:"روزنامه"},
  {name:"هم‌میهن", domain:"hammihanonline.ir", scope:"iran-paper", lang:"fa", type:"روزنامه"},
  {name:"سازندگی", domain:"sazandeginews.com", scope:"iran-paper", lang:"fa", type:"روزنامه"},
  // مجلات و فصلنامه‌های ایرانی
  {name:"تجربه", aliases:["مجله تجربه","ماهنامه تجربه"], domain:"taaghche.com", scope:"iran-magazine", lang:"fa", type:"ماهنامه فرهنگی و هنری"},
  {name:"آنگاه", aliases:["مجله آنگاه","فصلنامه آنگاه"], domain:"angahmag.com", scope:"iran-magazine", lang:"fa", type:"فصلنامه فرهنگی و هنری"},
  {name:"تراژدی", aliases:["مجله تراژدی"], domain:"taaghche.com", scope:"iran-magazine", lang:"fa", type:"مجله فرهنگی و هنری"},
  {name:"روزآروز", aliases:["مجله روزآروز","روز آ روز"], domain:"roozarooz.com", scope:"iran-magazine", lang:"fa", type:"مجله فرهنگی"},
  {name:"بخارا", aliases:["مجله بخارا"], domain:"bukharamag.com", scope:"iran-magazine", lang:"fa", type:"مجله فرهنگی و ادبی"},
  {name:"تنور", aliases:["مجله تنور"], domain:"taaghche.com", scope:"iran-magazine", lang:"fa", type:"مجله فرهنگی و ادبی"},
  {name:"ناداستان", aliases:["مجله ناداستان"], domain:"taaghche.com", scope:"iran-magazine", lang:"fa", type:"مجله روایت و ادبیات غیرداستانی"},
  {name:"عصر اندیشه", aliases:["مجله عصر اندیشه"], domain:"asreandisheh.ir", scope:"iran-magazine", lang:"fa", type:"مجله اندیشه و علوم انسانی"},
  {name:"شهریور", aliases:["مجله شهریور"], domain:"shahrivar.org", scope:"diaspora", lang:"fa", type:"مجله فارسی‌زبان خارج از ایران"},
  {name:"اندیشه پویا", aliases:["مجله اندیشه پویا"], domain:"andishepooya.ir", scope:"iran-magazine", lang:"fa", type:"ماهنامه فرهنگی و سیاسی"},
  {name:"مروارید", aliases:["مجله مروارید"], domain:"taaghche.com", scope:"iran-magazine", lang:"fa", type:"مجله فرهنگی"},
  {name:"غروب", aliases:["مجله غروب"], domain:"goroobonline.ir", scope:"iran-magazine", lang:"fa", type:"مجله فرهنگی و تاریخی"},
  {name:"تجربه و شهر", aliases:["مجله تجربه و شهر"], domain:"goroobonline.ir", scope:"iran-magazine", lang:"fa", type:"مجله شهر و فرهنگ"},
  {name:"هنر و جامعه", aliases:["مجله هنر و جامعه"], domain:"goroobonline.ir", scope:"iran-magazine", lang:"fa", type:"مجله هنر و جامعه"},
  {name:"روزنامک", aliases:["ماهنامه روزنامک"], domain:"rooznamak-magazine.com", scope:"iran-magazine", lang:"fa", type:"ماهنامه فرهنگی و تاریخی"},

  // رسانه‌های ایرانی غیرفارسی‌زبان؛ در دستهٔ داخل ایران، نه رسانه‌های جهان
  {name:"Press TV", domain:"presstv.ir", scope:"iran-agency", lang:"en", type:"تلویزیون/رسانه خبری"},
  {name:"Tehran Times", domain:"tehrantimes.com", scope:"iran-paper", lang:"en", type:"روزنامه"},
  {name:"Al-Alam", aliases:["العالم"], domain:"alalam.ir", scope:"iran-agency", lang:"ar", type:"تلویزیون/رسانه خبری"},

  // مجلات فارسی‌زبان خارج از ایران
  {name:"فریدون", aliases:["مجله فریدون"], domain:"fereydoun.org", scope:"diaspora", lang:"fa", type:"مجله فارسی‌زبان خارج از ایران"},
  {name:"ایران‌نامه", aliases:["ایران نامه","Iran Namag"], domain:"irannamag.com", scope:"diaspora", lang:"fa", type:"فصلنامه ایران‌شناسی خارج از ایران"},
  {name:"ایران‌شناسی", aliases:["ایران شناسی"], domain:"fis-iran.org", scope:"diaspora", lang:"fa", type:"فصلنامه ایران‌شناسی خارج از ایران"},

  // فارسی‌زبان خارج از ایران
  {name:"بی‌بی‌سی فارسی", aliases:["بی‌بی‌سی فارسی (BBC Persian)"], domain:"bbc.com", scope:"diaspora", lang:"fa", type:"رسانه بین‌المللی"},
  {name:"رادیو فردا", domain:"radiofarda.com", scope:"diaspora", lang:"fa", type:"رادیو/آنلاین"},
  {name:"ایران اینترنشنال", aliases:["ایران اینترنشنال (Iran International)"], domain:"iranintl.com", scope:"diaspora", lang:"fa", type:"تلویزیون/آنلاین"},
  {name:"دویچه‌وله فارسی", aliases:["دویچه‌وله فارسی (DW Persian)"], domain:"dw.com", scope:"diaspora", lang:"fa", type:"رسانه بین‌المللی"},
  {name:"یورونیوز فارسی", domain:"parsi.euronews.com", scope:"diaspora", lang:"fa", type:"رسانه بین‌المللی"},
  {name:"ایران‌وایر", domain:"iranwire.com", scope:"diaspora", lang:"fa", type:"رسانه آنلاین"},
  {name:"کیهان لندن", domain:"kayhan.london", scope:"diaspora", lang:"fa", type:"روزنامه/آنلاین"},
  {name:"رادیو زمانه", domain:"radiozamaneh.com", scope:"diaspora", lang:"fa", type:"رادیو/آنلاین"},
  {name:"ایندیپندنت فارسی", domain:"independentpersian.com", scope:"diaspora", lang:"fa", type:"رسانه آنلاین"},
  {name:"اخبار روز", domain:"akhbar-rooz.com", scope:"diaspora", lang:"fa", type:"رسانه آنلاین"},

  {name:"ایلنا", domain:"ilna.ir", scope:"iran-agency", lang:"fa", type:"خبرگزاری"},
  {name:"تسنیم", domain:"tasnimnews.com", scope:"iran-agency", lang:"fa", type:"خبرگزاری"},
  {name:"آنا", domain:"ana.ir", scope:"iran-agency", lang:"fa", type:"خبرگزاری"},
  {name:"اقتصادنیوز", domain:"eghtesadnews.com", scope:"iran-agency", lang:"fa", type:"اقتصادی"},
  {name:"اکوایران", domain:"ecoiran.com", scope:"iran-agency", lang:"fa", type:"اقتصادی"},
  {name:"دیپلماسی ایرانی", domain:"irdiplomacy.ir", scope:"iran-agency", lang:"fa", type:"تحلیلی"},
  {name:"جماران", domain:"jamaran.ir", scope:"iran-agency", lang:"fa", type:"رسانه خبری"},
  {name:"میزان", domain:"mizan.news", scope:"iran-agency", lang:"fa", type:"خبرگزاری"},
  {name:"شفقنا فارسی", domain:"fa.shafaqna.com", scope:"iran-agency", lang:"fa", type:"خبرگزاری"},
  {name:"هرانا", domain:"hra-news.org", scope:"iran-agency", lang:"fa", type:"حقوق بشر"},
  {name:"هەنگاو", domain:"hengaw.net", scope:"iran-agency", lang:"fa", type:"حقوق بشر"},
  {name:"گویا نیوز", domain:"news.gooya.com", scope:"diaspora", lang:"fa", type:"رسانه خبری"},
  {name:"ایران امروز", domain:"iran-emrooz.net", scope:"diaspora", lang:"fa", type:"رسانه آنلاین"},
  {name:"ایران پرس نیوز", domain:"iranpressnews.com", scope:"diaspora", lang:"fa", type:"رسانه آنلاین"},
  {name:"ایران گلوبال", domain:"iranglobal.info", scope:"diaspora", lang:"fa", type:"رسانه آنلاین"},
  {name:"فریدون", domain:"fereydoun.org", scope:"diaspora", lang:"fa", type:"تحلیلی"},
  {name:"ملی-مذهبی", domain:"melimazhabi.com", scope:"diaspora", lang:"fa", type:"تحلیلی"},
  {name:"صدای آمریکا فارسی", domain:"ir.voanews.com", scope:"diaspora", lang:"fa", type:"رسانه بین‌المللی"},
  {name:"العربیه فارسی", domain:"farsi.alarabiya.net", scope:"diaspora", lang:"fa", type:"رسانه بین‌المللی"},
  {name:"شرق‌الاوسط فارسی", domain:"persian.aawsat.com", scope:"diaspora", lang:"fa", type:"رسانه بین‌المللی"},
  {name:"اِپُک تایمز فارسی", domain:"persianepochtimes.com", scope:"diaspora", lang:"fa", type:"رسانه بین‌المللی"},
  {name:"آسو", domain:"aasoo.org", scope:"diaspora", lang:"fa", type:"محتوایی/تحلیلی"},
  {name:"Al-Monitor", domain:"al-monitor.com", scope:"world", lang:"en", type:"تحلیلی"},
  {name:"Axios", domain:"axios.com", scope:"world", lang:"en", type:"رسانه خبری"},
  {name:"Bloomberg", domain:"bloomberg.com", scope:"world", lang:"en", type:"خبرگزاری/اقتصادی"},
  {name:"CNBC", domain:"cnbc.com", scope:"world", lang:"en", type:"اقتصادی"},
  {name:"Foreign Affairs", domain:"foreignaffairs.com", scope:"world", lang:"en", type:"مجله تحلیلی"},
  {name:"Foreign Policy", domain:"foreignpolicy.com", scope:"world", lang:"en", type:"مجله تحلیلی"},
  {name:"NPR", domain:"npr.org", scope:"world", lang:"en", type:"رادیو/آنلاین"},
  {name:"Newsweek", domain:"newsweek.com", scope:"world", lang:"en", type:"مجله"},
  {name:"Sky News", domain:"news.sky.com", scope:"world", lang:"en", type:"تلویزیون/آنلاین"},
  {name:"Time", aliases:["تایم"], domain:"time.com", scope:"world", lang:"en", type:"مجله"},
  // رسانه‌های جهان
  {name:"Reuters", domain:"reuters.com", scope:"world", lang:"en", type:"خبرگزاری"},
  {name:"Associated Press", domain:"apnews.com", scope:"world", lang:"en", type:"خبرگزاری"},
  {name:"BBC", domain:"bbc.com", scope:"world", lang:"en", type:"رسانه عمومی"},
  {name:"The Guardian", domain:"theguardian.com", scope:"world", lang:"en", type:"روزنامه"},
  {name:"Guardian Weekly", aliases:["هفته‌نامه گاردین"], domain:"theguardian.com", scope:"world", lang:"en", type:"هفته‌نامه"},
  {name:"Financial Times", domain:"ft.com", scope:"world", lang:"en", type:"روزنامه"},
  {name:"The Economist", aliases:["اکونومیست"], domain:"economist.com", scope:"world", lang:"en", type:"هفته‌نامه"},
  {name:"The New York Times", domain:"nytimes.com", scope:"world", lang:"en", type:"روزنامه"},
  {name:"The Wall Street Journal", aliases:["وال‌استریت ژورنال"], domain:"wsj.com", scope:"world", lang:"en", type:"روزنامه"},
  {name:"The Washington Post", domain:"washingtonpost.com", scope:"world", lang:"en", type:"روزنامه"},
  {name:"CNN", domain:"cnn.com", scope:"world", lang:"en", type:"تلویزیون/آنلاین"},
  {name:"Al Jazeera English", aliases:["Al Jazeera"], domain:"aljazeera.com", scope:"world", lang:"en", type:"تلویزیون/آنلاین"},
  // جهان — اسپانیایی
  {name:"El País", domain:"elpais.com", scope:"world", lang:"es", type:"روزنامه"},
  {name:"Agencia EFE", domain:"efe.com", scope:"world", lang:"es", type:"خبرگزاری"},
  {name:"RTVE Noticias", domain:"rtve.es", scope:"world", lang:"es", type:"رسانه عمومی"},
  {name:"BBC Mundo", domain:"bbc.com", scope:"world", lang:"es", type:"رسانه بین‌المللی"},
  {name:"CNN en Español", domain:"cnnespanol.cnn.com", scope:"world", lang:"es", type:"تلویزیون/آنلاین"},
  {name:"DW Español", domain:"dw.com", scope:"world", lang:"es", type:"رسانه بین‌المللی"},
  {name:"France 24 Español", domain:"france24.com", scope:"world", lang:"es", type:"تلویزیون/آنلاین"},
  {name:"El Mundo", domain:"elmundo.es", scope:"world", lang:"es", type:"روزنامه"},
  {name:"La Vanguardia", domain:"lavanguardia.com", scope:"world", lang:"es", type:"روزنامه"},
  {name:"ABC España", domain:"abc.es", scope:"world", lang:"es", type:"روزنامه"},
  {name:"El Confidencial", domain:"elconfidencial.com", scope:"world", lang:"es", type:"رسانه آنلاین"},
  {name:"Clarín", domain:"clarin.com", scope:"world", lang:"es", type:"روزنامه"},
  {name:"La Nación", domain:"lanacion.com.ar", scope:"world", lang:"es", type:"روزنامه"},
  {name:"El Universal México", domain:"eluniversal.com.mx", scope:"world", lang:"es", type:"روزنامه"},
  {name:"NTN24", domain:"ntn24.com", scope:"world", lang:"es", type:"تلویزیون/آنلاین"},
  {name:"Le Monde", domain:"lemonde.fr", scope:"world", lang:"fr", type:"روزنامه"},
  {name:"France 24", domain:"france24.com", scope:"world", lang:"fr", type:"تلویزیون/آنلاین"},
  {name:"RFI", domain:"rfi.fr", scope:"world", lang:"fr", type:"رادیو/آنلاین"},
  {name:"Le Figaro", domain:"lefigaro.fr", scope:"world", lang:"fr", type:"روزنامه"},
  {name:"Libération", domain:"liberation.fr", scope:"world", lang:"fr", type:"روزنامه"},
  {name:"Anadolu Ajansı", domain:"aa.com.tr", scope:"world", lang:"tr", type:"خبرگزاری"},
  {name:"TRT Haber", domain:"trthaber.com", scope:"world", lang:"tr", type:"تلویزیون/آنلاین"},
  {name:"Hürriyet", domain:"hurriyet.com.tr", scope:"world", lang:"tr", type:"روزنامه"},
  {name:"Cumhuriyet", domain:"cumhuriyet.com.tr", scope:"world", lang:"tr", type:"روزنامه"},
  {name:"الجزيرة", domain:"aljazeera.net", scope:"world", lang:"ar", type:"تلویزیون/آنلاین"},
  {name:"العربية", domain:"alarabiya.net", scope:"world", lang:"ar", type:"تلویزیون/آنلاین"},
  {name:"الشرق الأوسط", domain:"aawsat.com", scope:"world", lang:"ar", type:"روزنامه"},
  {name:"Der Spiegel", domain:"spiegel.de", scope:"world", lang:"de", type:"مجله"},
  {name:"Frankfurter Allgemeine", domain:"faz.net", scope:"world", lang:"de", type:"روزنامه"},
  {name:"Süddeutsche Zeitung", domain:"sueddeutsche.de", scope:"world", lang:"de", type:"روزنامه"}
]

const PRESS_SCOPE_FA = {all:"همه", "iran-agency":"خبرگزاری‌ها و رسانه‌های خبری ایران", "iran-paper":"روزنامه‌های ایران", "iran-magazine":"مجلات ایران", diaspora:"فارسی‌زبان خارج", world:"رسانه‌های جهان", magazine:"همهٔ مجلات و هفته‌نامه‌ها"};
function pressMatchesScope(s, scope){
  if(scope==="all") return true;
  if(scope==="magazine") return /مجله|هفته‌نامه/.test(String(s.type||""));
  if(scope==="iran-magazine") return s.scope==="iran-magazine";
  return s.scope===scope;
}
const PRESS_LANG_FA = {all:"همه زبان‌ها", fa:"فارسی", en:"انگلیسی", es:"اسپانیایی", fr:"فرانسوی", tr:"ترکی", ar:"عربی", de:"آلمانی"};

function pressLogo(s) {
  const src = "https://www.google.com/s2/favicons?domain=" + encodeURIComponent(s.domain) + "&sz=128";
  return `<span class="press-logo"><img src="${src}" alt="" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='grid'"><b style="display:none">${esc((s.name||"ج").slice(0,1))}</b></span>`;
}
function setPressScope(v){ pressScope=v; renderPress(""); }
function setPressLanguage(v){ pressLanguage=v; renderPress(""); }

function showPress(sourceName) {
  show("press"); setTab("press");
  renderPress(sourceName || "");
  setHash(sourceName ? "#/press-source/" + encodeURIComponent(sourceName) : "#/press");
}
async function loadPeriodicals() {
  if (periodicalRows.length) return periodicalRows;
  let rows=[]; try { rows=await getJSON(`${DATA}/periodicals.json`); } catch (_) {}
  periodicalRows=Array.isArray(rows)?rows:((rows && Array.isArray(rows.articles))?rows.articles:[]);
  return periodicalRows;
}
async function loadPressStats(){
  if(pressStatsCache) return pressStatsCache;
  let rows=[]; try{rows=await getJSON(`${DATA}/press-stats.json`);}catch(_){}
  pressStatsCache=Array.isArray(rows)?rows:[];
  return pressStatsCache;
}
async function loadPressHealth(){
  if(pressHealthCache) return pressHealthCache;
  let rows=[]; try{rows=await getJSON(`${DATA}/press-source-health.json`);}catch(_){}
  pressHealthCache=Array.isArray(rows)?rows:[];
  return pressHealthCache;
}
function pressSourceHealth(s, rows){
  const names=[s.name,...(s.aliases||[])];
  const matches=(rows||[]).filter(x=>names.includes(x.source_name));
  if(!matches.length) return null;
  return matches.sort((a,b)=>String(b.last_run||"").localeCompare(String(a.last_run||"")))[0];
}
function pressHealthBadge(h){
  if(!h) return '<span class="press-health ph-pending">پایش در انتظار</span>';
  const map={
    active:["ph-active","فعال"],
    empty:["ph-empty","متصل · بدون آیتم"],
    error:["ph-error","خطای دریافت"],
    disabled:["ph-disabled","غیرفعال"],
    pending:["ph-pending","در انتظار"]
  };
  const x=map[h.state]||map.pending;
  return `<span class="press-health ${x[0]}" title="${esc(h.last_error||"")}">${x[1]}</span>`;
}
function pressSourceStats(s, stats){
  const names=[s.name,...(s.aliases||[])];
  const rows=stats.filter(x=>names.includes(x.source_name));
  return rows.reduce((a,x)=>({story_count:a.story_count+(x.story_count||0),iran_story_count:a.iran_story_count+(x.iran_story_count||0),latest_at:(!a.latest_at||((x.latest_at||"")>a.latest_at))?(x.latest_at||a.latest_at):a.latest_at}),{story_count:0,iran_story_count:0,latest_at:null});
}
async function renderPress(sourceName) {
  const el=document.getElementById("press-content");
  // Render the directory immediately. Generated datasets are enhancements,
  // never a prerequisite for navigation.
  const rows=periodicalRows||[];
  const stats=pressStatsCache||[];
  const health=pressHealthCache||[];
  const groups=new Map(); rows.forEach(x=>{const n=x.publisher||"نشریه";if(!groups.has(n))groups.set(n,[]);groups.get(n).push(x);});
  if(!periodicalRows.length || pressStatsCache===null){
    Promise.allSettled([loadPeriodicals(),loadPressStats()]).then(()=>{
      if(document.getElementById("press-content")===el && location.hash.startsWith("#/press")) renderPress(sourceName);
    });
  }

  if(!sourceName){
    const sources=PRESS_SOURCES.filter(s => pressMatchesScope(s,pressScope) && (pressLanguage==="all"||s.lang===pressLanguage));
    const scopeControls=Object.entries(PRESS_SCOPE_FA).map(([k,v])=>`<button class="fchip ${pressScope===k?"on":""}" onclick="setPressScope('${k}')">${v}</button>`).join("");
    const langs=[...new Set(PRESS_SOURCES.filter(s=>pressMatchesScope(s,pressScope)).map(s=>s.lang))];
    const langControls=["all",...langs].map(k=>`<button class="fchip ${pressLanguage===k?"on":""}" onclick="setPressLanguage('${k}')">${PRESS_LANG_FA[k]||k}</button>`).join("");
    const cards=sources.map(s=>{
      const items=[s.name,...(s.aliases||[])].flatMap(n=>groups.get(n)||[]);
      const st=pressSourceStats(s,stats);
      const h=pressSourceHealth(s,health);
      const bits=[];
      if(st.iran_story_count) bits.push(faN(st.iran_story_count)+" خبر مرتبط با ایران");
      else if(st.story_count) bits.push(faN(st.story_count)+" حضور در خط خبری");
      if(items.length) bits.push(faN(items.length)+" مطلب تفصیلی");
      if(st.latest_at) bits.push("آخرین: "+ago(st.latest_at));
      const status=bits.length?bits.join(" · "):"در فهرست پایش";
      return `<button class="press-source press-source-rich" onclick="showPress('${esc(s.name)}')">
        ${pressLogo(s)}
        <span class="press-source-copy"><span class="press-source-title"><strong>${esc(s.name)}</strong>${pressHealthBadge(h)}</span><small>${esc(s.type)} · ${PRESS_LANG_FA[s.lang]||s.lang}</small><em>${status}${h&&h.last_run?` · پایش ${ago(h.last_run)}`:""}</em></span>
      </button>`;
    }).join("");
    const known=new Set(PRESS_SOURCES.flatMap(s=>[s.name,...(s.aliases||[])]));
    const extra=[...groups.entries()].filter(([name])=>!known.has(name));
    el.innerHTML=`<div class="press-directory-note"><b>تمرکز تحریریه:</b> مطالبی که به ایران، ایرانیان، سیاست خارجی ایران یا پیامدهای منطقه‌ای مرتبط‌اند؛ زبان منبع محدودیت نیست.</div>
      <div class="press-filter-row">${scopeControls}</div>
      <div class="press-filter-row press-langs">${langControls}</div>
      <div class="press-grid">${cards}</div>
      ${extra.length?`<div class="rule"><span>دیگر نشریات پردازش‌شده</span><span class="l"></span></div><div class="press-grid">${extra.map(([name,items])=>`<button class="press-source" onclick="showPress('${esc(name)}')"><span class="press-mark">ج</span><strong>${esc(name)}</strong><small>${faN(items.length)} مطلب</small></button>`).join("")}</div>`:""}`;
    return;
  }

  const meta=PRESS_SOURCES.find(s=>s.name===sourceName);
  const items=meta ? [meta.name,...(meta.aliases||[])].flatMap(n=>groups.get(n)||[]) : (groups.get(sourceName)||[]);
  const st=meta?pressSourceStats(meta,stats):{story_count:0,iran_story_count:0,latest_at:null};
  const h=meta?pressSourceHealth(meta,health):null;
  // Source pages should also show ordinary news-feed stories, not only
  // long-form periodical/PDF articles.
  let feedItems=[];
  const names=meta?[meta.name,...(meta.aliases||[])]:[sourceName];
  try{
    // Prefer the 500-story press archive; fall back to the compact homepage feed
    // during deployments where the new export has not landed yet.
    const archive=await getJSON(`${DATA}/press-source-stories.json`);
    feedItems=names.flatMap(n => Array.isArray(archive && archive[n]) ? archive[n] : []);
    const seen=new Set();
    feedItems=feedItems.filter(x=>x && x.id && !seen.has(String(x.id)) && seen.add(String(x.id)))
      .sort((a,b)=>String(b.published_at||"").localeCompare(String(a.published_at||"")));
  }catch(_){
    try{
      const feed=await getJSON(`${DATA}/stories.json`);
      feedItems=(Array.isArray(feed)?feed:[]).filter(x=>(x.source_names||[]).some(n=>names.includes(n)));
    }catch(__){}
  }
  const sourceStoryCard=x=>{
    const metaBits=[];
    if(x.published_at) metaBits.push(relTime(x.published_at));
    if(x.category) metaBits.push(CAT_FA[x.category]||x.category);
    if(x.source_count>1) metaBits.push(faN(x.source_count)+" منبع");
    const relevance=IRAN_FA[x.iran_relevance]||"";
    if(relevance) metaBits.push(relevance);
    return `<article class="press-article press-click press-news-full" onclick="openStory('\\${esc(x.id)}')">
      <div class="press-news-meta"><span class="chip">${esc(sourceName)}</span>${metaBits.length?`<span>${metaBits.map(esc).join(" · ")}</span>`:""}</div>
      <h2>${esc(x.headline_fa||x.title_fa||"")}</h2>
      ${x.summary_fa?`<p>${esc(x.summary_fa)}</p>`:""}
      ${x.image_url?`<img class="press-news-thumb" src="${esc(x.image_url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">`:""}
      <div class="press-read">پروندهٔ کامل خبر ←</div>
    </article>`;
  };
  el.innerHTML=`<div class="press-source-head"><button class="back" onclick="showPress()">همهٔ رسانه‌ها</button>${meta?pressLogo(meta):""}<div><h2>${esc(sourceName)} ${pressHealthBadge(h)}</h2>${meta?`<p>${esc(meta.type)} · ${PRESS_LANG_FA[meta.lang]||meta.lang} · ${PRESS_SCOPE_FA[meta.scope]||""}${st.iran_story_count?` · ${faN(st.iran_story_count)} خبر مرتبط با ایران`:""}${st.latest_at?` · آخرین خبر: ${ago(st.latest_at)}`:""}${h&&h.last_run?` · آخرین پایش: ${ago(h.last_run)}`:""}${h?` · دریافت آخر: ${faN(h.last_fetched||0)} / جدید: ${faN(h.last_new||0)}`:""}</p>`:""}</div></div>
    ${(items.length||feedItems.length)?`<div class="press-source-count">${faN(feedItems.length)} خبر اخیر در آرشیو این منبع</div><div class="press-list">${feedItems.map(sourceStoryCard).join("")}${items.map(x=>`<article class="press-article press-click" onclick="openPressArticle(\'${esc(x.id)}\')"><span class="chip">${esc(sourceName)}</span><h2>${esc(x.headline_fa||x.title_fa||x.title_original||"")}</h2>${x.summary_fa?`<p>${esc(x.summary_fa)}</p>`:""}<div class="press-read">خواندن بازگویی تفصیلی ←</div></article>`).join("")}</div>`:`<div class="state press-empty"><div class="big">هنوز مطلبی از این رسانه پردازش نشده</div><p class="muted">این منبع در فهرست پایش است. مطالب مرتبط با ایران پس از دریافت و پردازش در همین صفحه ظاهر می‌شوند.</p></div>`}`;
}

async function openPressArticle(id) {
  show("press"); setTab("press"); const el=document.getElementById("press-content"); el.innerHTML='<div class="spinner"></div>';
  const rows=await loadPeriodicals(); const x=rows.find(r=>String(r.id)===String(id));
  if(!x){el.innerHTML='<div class="state"><div class="big">مطلب پیدا نشد</div></div>';return;}
  const body=x.body_fa||x.longform_fa||"";
  const points=(x.key_points_fa||[]).map(p=>`<li>${esc(p)}</li>`).join("");
  const hero=x.image_url||x.hero_image_url||x.source_image_url||x.og_image||"";
  el.innerHTML=`<article class="press-detail press-longread"><button class="back" onclick="showPress('${esc(x.publisher||"")}')">بازگشت به ${esc(x.publisher||"نشریه")}</button><header class="press-longread-head"><div class="press-detail-meta"><span class="chip">${esc(x.publisher||"نشریه")}</span>${x.issue?`<span>شماره ${esc(x.issue)}</span>`:""}</div><h1>${esc(x.headline_fa||x.title_original||"")}</h1>${x.title_original?`<div class="press-original">${esc(x.title_original)}</div>`:""}${x.summary_fa?`<p class="press-deck">${esc(x.summary_fa)}</p>`:""}</header>${hero?`<figure class="press-hero"><img src="${esc(hero)}" alt="" loading="eager" referrerpolicy="no-referrer" onerror="this.closest('figure').remove()"></figure>`:""}${points?`<section class="press-points"><h2>جانِ مطلب</h2><ul>${points}</ul></section>`:""}<section class="press-body">${body?body.split(/\\n{2,}/).map(p=>`<p>${esc(p)}</p>`).join(""):`<p class="muted">نسخهٔ تفصیلی این مطلب هنوز آماده نشده است؛ خلاصه و نکات اصلی بالا در دسترس است.</p>`}</section><footer class="press-longread-foot"><div class="press-copyright-note">این متن بازگویی فارسی و وفادارانهٔ محتوای منبع است، نه ترجمهٔ خط‌به‌خط یا جایگزین متن اصلی.</div>${x.source_url?`<a class="press-source-link" href="${esc(x.source_url)}" target="_blank" rel="noopener">مشاهدهٔ منبع اصلی ↗</a>`:""}</footer></article>`;
  setHash("#/press-article/"+encodeURIComponent(id));
}

/* ---- hash routing: shareable URLs + working Back button ----
   Each view/story gets its own #/… URL. Deep links and Back/Forward work.
   _navLock stops our own setHash() from re-triggering the router. */
let _navLock = false;
function setHash(h) {
  h = h || "#/";                              // home sentinel
  if ((location.hash || "#/") === h) return;  // no change (also no-op on first load)
  _navLock = true;
  location.hash = h;
  setTimeout(() => { _navLock = false; }, 0);
}
async function route() {
  const raw = (location.hash || "").replace(/^#\/?/, "");
  const i = raw.indexOf("/");
  const kind = i < 0 ? raw : raw.slice(0, i);
  const arg = i < 0 ? "" : decodeURIComponent(raw.slice(i + 1));
  if (kind === "story" && arg) return openStory(arg);
  if (kind === "person" && arg) return openEntity(arg);
  if (kind === "topic" && arg) return openTopic(arg);
  if (kind === "trend" && arg) return openTrendDossier(arg);
  if (kind === "source" && arg) return openSource(arg);
  if (kind === "province" && arg) return openProvince(arg);
  if (kind === "day" && arg) return openDay(arg);
  if (kind === "trends") return showTrends();
  if (kind === "fact") return showFactchecks();
  if (kind === "iran") return showIran();
  if (kind === "topics") return showTopics();
  if (kind === "market") return showMarket();
  if (kind === "weather") return showWeather();
  if (kind === "faq") return showFaq();
  if (kind === "figures") return showFigures();
  if (kind === "press") return showPress();
  if (kind === "press-source" && arg) return showPress(arg);
  if (kind === "press-article" && arg) return openPressArticle(arg);
  if (kind === "tech") return showTech();
  if (kind === "figure" && arg) return openFigure(arg);
  if (kind === "news-person" && arg) return openNewsPerson(arg);
  if (kind === "statement" && arg) return openStatement(arg);
  return showFeed();
}
window.addEventListener("hashchange", () => { if (!_navLock) route(); });

function credBadge(c) {
  if (!c) return "";
  let out = `<span class="cstatus ${CRED_CLS[c.level] || "st-neutral"}">${CRED_FA[c.level] || ""}</span>`;
  if (c.needs_verification) out += `<span class="cstatus st-warn">نیازمند راستی‌آزمایی</span>`;
  return out;
}
function fcBadge(f) {
  return f ? `<span class="cstatus st-ok fc-badge">✓ فکت‌نامه</span>` : "";
}
function geoBadge(g) {
  if (!g || !g.scope) return "";
  if (g.scope === "local") {
    const p = g.provinces && g.provinces[0];
    return `<span class="geo-badge local">${p ? esc(p.name_fa) : "استانی"}</span>`;
  }
  return `<span class="geo-badge ${g.scope}">${SCOPE_FA[g.scope] || ""}</span>`;
}

// Detail-view geo strip: bigger mini-map + a caption listing the highlighted places.
function detailGeoStrip(s) {
  const mm = miniMap(s, { detail: true });
  if (!mm) return "";
  const provs = (s.geo && s.geo.provinces || []).map(p => p.name_fa);
  const countries = (s.countries || []).map(c => c.name_fa);
  const parts = [];
  if (provs.length) parts.push("استان‌ها: " + provs.join("، "));
  if (countries.length) parts.push("کشورها: " + countries.join("، "));
  if (!parts.length && s.geo && s.geo.scope) {
    parts.push({ international: "بین‌المللی", national: "سراسر ایران",
                 local: "استانی" }[s.geo.scope] || "");
  }
  return `<div class="geo-strip">${mm}<span class="g-lbl">${esc(parts.join(" · "))}</span></div>`;
}

// A tiny "where is this story" map — Iran mini-map with highlighted provinces
// for local/national stories, world mini-map with highlighted countries otherwise.
// Purely for at-a-glance orientation; falls back to nothing when nothing to show.
function miniMap(s, opts) {
  opts = opts || {};
  const cls = opts.detail ? "mini-map mm-detail" : "mini-map";
  const provs = (s.geo && s.geo.provinces || []).map(p => p.slug);
  const scope = s.geo && s.geo.scope;
  const isIranMap = provs.length > 0 || scope === "local"
    || (scope === "national" && (!s.countries || s.countries.length === 0));

  if (isIranMap && window.IRAN_PATHS) {
    const hit = new Set(provs);
    const paths = Object.entries(window.IRAN_PATHS).map(([slug, p]) =>
      `<path d="${p.d}" class="${hit.has(slug) ? "mm-hit" : "mm-bg"}"/>`).join("");
    return `<span class="${cls}" title="${esc((s.geo && s.geo.provinces || []).map(p=>p.name_fa).join("، ") || "ایران")}">
      <svg viewBox="${window.IRAN_VIEWBOX}" preserveAspectRatio="xMidYMid meet">${paths}</svg></span>`;
  }
  if (!window.WORLD_PATHS) return "";
  const codes = new Set((s.countries || []).map(c => c.code));
  // If nothing detected but story is international, still show a world background.
  if (!codes.size && scope !== "international" && !opts.detail) return "";
  const paths = Object.entries(window.WORLD_PATHS).map(([code, d]) => {
    if (code === "_bg") return `<path d="${d}" class="mm-bg"/>`;
    return `<path d="${d}" class="${codes.has(code) ? "mm-hit" : "mm-bg"}"/>`;
  }).join("");
  const names = (s.countries || []).map(c => c.name_fa).join("، ");
  return `<span class="${cls}" title="${esc(names || "بین‌المللی")}">
    <svg viewBox="${window.WORLD_VIEWBOX}" preserveAspectRatio="xMidYMid meet">${paths}</svg></span>`;
}

// clickable chips for the named figures in a story → their own page
function peopleRow(ents) {
  if (!ents || !ents.length) return "";
  const chips = ents.slice(0, 6).map(e =>
    `<span class="person-chip" data-slug="${esc(e.slug)}" onclick="event.stopPropagation();openEntity(this.dataset.slug)">${esc(e.name_fa)}</span>`).join("");
  return `<div class="people">${chips}</div>`;
}
// self-contained styling (theme-aware) so no separate CSS file is needed
(function () {
  const css = `.people{display:flex;flex-wrap:wrap;gap:6px;margin:9px 0 2px}
.person-chip{font-size:12.5px;padding:3px 10px;border-radius:999px;cursor:pointer;
  background:rgba(26,157,126,.12);color:#1a9d7e;border:1px solid rgba(26,157,126,.32);white-space:nowrap}
.person-chip:hover{background:rgba(26,157,126,.22)}
.people-strip{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 4px}
.timeline{margin:6px 0 0}
.tl-item{display:flex;gap:12px;align-items:flex-start;width:100%;text-align:start;background:none;border:none;padding:9px 0;cursor:pointer;color:inherit;position:relative;font-family:inherit}
.tl-item:not(:last-child)::after{content:"";position:absolute;inset-inline-start:5px;top:20px;bottom:-9px;width:2px;background:rgba(26,157,126,.25)}
.tl-dot{flex:0 0 12px;width:12px;height:12px;border-radius:50%;background:#1a9d7e;margin-top:5px}
.tl-body{display:flex;flex-direction:column;gap:2px}
.tl-time{font-size:12px;color:#8fa89b}
.tl-h{font-size:15px;line-height:1.6}
.tl-cur{cursor:default}
.tl-cur .tl-dot{background:#e0b341;box-shadow:0 0 0 3px rgba(224,179,65,.2)}
.tl-cur .tl-h{font-weight:700}
.tl-now{font-size:11px;color:#e0b341}
button.tl-item:hover .tl-h{color:#1a9d7e}
.mini-map{flex:0 0 auto;width:78px;height:52px;border-radius:6px;background:rgba(26,157,126,.06);
  border:1px solid rgba(26,157,126,.22);padding:2px;overflow:hidden;display:inline-flex;align-items:center;justify-content:center}
.mini-map svg{width:100%;height:100%;display:block}
.mini-map .mm-bg{fill:rgba(143,168,155,.20);stroke:rgba(143,168,155,.35);stroke-width:.5;vector-effect:non-scaling-stroke}
.mini-map .mm-hit{fill:#1a9d7e;stroke:#0d5b48;stroke-width:.5;vector-effect:non-scaling-stroke}
.mm-detail{width:180px;height:120px}
.mm-caption{font-size:11.5px;color:#8fa89b;text-align:center;margin-top:4px}
.geo-strip{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:8px 0 6px}
.geo-strip .g-lbl{font-size:13px;color:#8fa89b}
.sb-click{cursor:pointer;transition:background .15s ease,color .15s ease;border-radius:8px;padding-inline:6px;margin-inline:-6px}
.sb-click:hover{background:rgba(26,157,126,.10);color:#1a9d7e}
.stile-click{cursor:pointer;transition:transform .12s ease,border-color .15s ease}
.stile-click:hover{transform:translateY(-1px);border-color:#1a9d7e;color:#1a9d7e}
.bars-svg .bar-click{cursor:pointer;transition:opacity .15s ease}
.bars-svg .bar-click:hover{opacity:.7}
.day-chips{display:flex;gap:6px;overflow-x:auto;padding:2px 0 6px;margin:0 -4px 6px;scrollbar-width:none}
.day-chips::-webkit-scrollbar{display:none}
.day-chip{flex:0 0 auto;padding:5px 12px;font-size:12.5px;border-radius:999px;
  border:1px solid rgba(143,168,155,.35);color:#a9c4b7;background:transparent;cursor:pointer;white-space:nowrap;font-family:inherit}
.day-chip .d-n{font-size:11px;color:#8fa89b;margin-inline-start:4px}
.day-chip:hover{border-color:#1a9d7e;color:#1a9d7e}
.day-chip.on{background:rgba(26,157,126,.15);border-color:#1a9d7e;color:#1a9d7e}
.card-thumb{flex:0 0 84px;width:84px;height:84px;border-radius:8px;object-fit:cover;background:rgba(143,168,155,.10);border:1px solid rgba(143,168,155,.18)}
.hero-img{width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:12px;background:rgba(143,168,155,.10);margin:6px 0 12px;display:block}
.hero-credit{font-size:12px;color:#8fa89b;margin:-6px 0 12px;text-align:end}
.ref-strip{display:flex;flex-direction:column;gap:6px;margin:0 0 14px;padding:10px 12px;background:rgba(26,157,126,.06);border:1px solid rgba(26,157,126,.20);border-radius:10px}
.ref-strip .ref-hd{font-size:12.5px;color:#8fa89b}
.ref-strip .ref-hd b{color:#a9c4b7}
.ref-links{display:flex;flex-wrap:wrap;gap:8px}
.ref-links a{font-size:13px;padding:4px 10px;border-radius:8px;text-decoration:none;background:rgba(26,157,126,.10);color:#1a9d7e;border:1px solid rgba(26,157,126,.22);white-space:nowrap}
.ref-links a:hover{background:rgba(26,157,126,.20)}
.ref-links a .ref-src{color:#8fa89b;font-size:11.5px;margin-inline-end:4px}`;
  const st = document.createElement("style");
  st.textContent = css;
  document.head.appendChild(st);
})();

function feedCard(s) {
  const imp = impInfo(s.importance_score);
  const badges = (s.source_names || []).slice(0, 4).map(x => `<span class="src-badge clickable" data-src="${esc(x)}" onclick="event.stopPropagation();openSource(this.dataset.src)">${esc(x)}</span>`).join("");
  // Show the article's image when the outlet's RSS provided one; otherwise
  // fall back to the mini-map (so every card has a visual anchor).
  const thumb = s.image_url
    ? `<img class="card-thumb" loading="lazy" src="${esc(s.image_url)}" alt="" onerror="this.remove()">`
    : miniMap(s);
  return `<button class="card" onclick="openStory('${s.id}')">
    <div class="meta"><span class="chip">${CAT_FA[s.category] || "خبر"}</span>
      <span class="dot"></span><span class="muted">${relTime(s.published_at)}</span>${geoBadge(s.geo)}${trendBadge(s.trend)}
      <span class="imp ${imp.cls}"><span class="bars"><i></i><i></i><i></i></span><span class="lbl">${imp.lbl}</span></span></div>
    <div style="display:flex;gap:12px;align-items:flex-start">
      <div style="flex:1;min-width:0">
        <h2>${esc(s.headline_fa || "")}</h2>
        <p class="kalam">${esc(s.summary_fa || "")}</p>
      </div>
      ${thumb}
    </div>
    ${peopleRow(s.entities)}
    <div class="foot"><span class="sources-mini">${faN(s.source_count || 0)} منبع:</span>${badges}
      <span class="cred-row">${s.figure_count ? `<span class="fig-badge" title="دیدگاه چهره‌ها دربارهٔ این خبر">${faN(s.figure_count)} دیدگاه</span>` : ""}${credBadge(s.credibility)}${fcBadge(s.factcheck)}${saveBtn(s.id)}</span></div>
  </button>`;
}

let ALL = [];
let tier = "all";
let feedRange = "all";
async function loadFeed() {
  const el = document.getElementById("feed");
  try {
    ALL = await getJSON(`${DATA}/stories.json`);
    renderFeed();
    renderDayChips();
    updateFreshness();
  } catch (e) {
    const why = e && e.name === "AbortError" ? "دریافت داده بیش از حد طول کشید." : "فایل خبرها در دسترس نیست.";
    el.innerHTML = `<div class="state"><div class="big">خبرها بارگذاری نشد</div>
      <p class="muted">${why}</p>
      <button class="fchip on" onclick="retryFeed()">تلاش دوباره</button></div>`;
  }
}
async function retryFeed() {
  const el = document.getElementById("feed");
  el.innerHTML = '<div class="loader"></div>';
  await loadFeed();
}
// A small horizontally-scrolling strip above the feed: today, yesterday, and
// the last few days that actually have stories. Fast browse "back in time".
function renderDayChips() {
  const holder = document.getElementById("day-chips");
  if (!holder) return;
  const counts = {};
  ALL.forEach(s => {
    const d = (s.published_at || "").slice(0, 10);
    if (d) counts[d] = (counts[d] || 0) + 1;
  });
  const days = Object.keys(counts).sort().reverse().slice(0, 10);
  if (!days.length) { holder.innerHTML = ""; return; }
  holder.innerHTML = days.map(d =>
    `<button class="day-chip" onclick="openDay('${d}')">${esc(dayLabel(d))}
      <span class="d-n">${faN(counts[d])}</span></button>`).join("");
}
const tierOf = s => impInfo(s.importance_score).cls;   // high | mid | low
function feedFilter(mode) {
  if (mode === "mine") return mineFeed();
  if (mode === "rising") return ALL.filter(s => s.trend && s.trend.rising);
  if (mode === "hot") return ALL.filter(s => s.trend && s.trend.hot);
  if (mode === "high" || mode === "mid" || mode === "low") return ALL.filter(s => tierOf(s) === mode);
  return ALL;
}
function renderFeed() {
  const el = document.getElementById("feed");
  if (!ALL.length) { el.innerHTML = `<div class="state"><div class="big">هنوز خبری منتشر نشده</div></div>`; return; }
  if (tier === "mine" && followCount() === 0 && !(FOLLOW.saved && FOLLOW.saved.length)) {
    el.innerHTML = `<div class="state mine-empty"><div class="big">خط خبریِ تو خالی است</div>
      <p class="muted">با زدنِ ستارهٔ ★ روی موضوع‌ها (در تبِ موضوعات)، استان‌ها (در صفحهٔ ایران) و منابع، یا ذخیرهٔ خبرها، اینجا خط خبریِ شخصیِ خودت ساخته می‌شود — روی همین دستگاه.</p></div>`;
    return;
  }
  let items = feedFilter(tier);
  if (feedRange !== "all") { const newest = items.map(s => new Date(s.published_at || 0).getTime()).filter(Number.isFinite).reduce((a,b)=>Math.max(a,b),0); const base = newest || Date.now(); const cut = base - Number(feedRange) * 3600e3; items = items.filter(s => { const t=new Date(s.published_at||0).getTime(); return Number.isFinite(t) && t >= cut; }); }
  if (sortMode === "new") items = items.slice().sort((a, b) => String(b.published_at || "").localeCompare(String(a.published_at || "")));
  else if (sortMode === "sources") items = items.slice().sort((a,b)=>(b.source_count||0)-(a.source_count||0));
  else if (sortMode === "views") items = items.slice().sort((a,b)=>(b.figure_count||0)-(a.figure_count||0) || (b.source_count||0)-(a.source_count||0));
  else if (sortMode === "rising") items = items.slice().sort((a,b)=>((b.trend&&b.trend.velocity)||0)-((a.trend&&a.trend.velocity)||0));
  const empty = { rising: "الان خبری در حالِ رشد نیست", hot: "الان خبرِ داغی نداریم",
    mine: "هنوز خبری از دنبال‌شده‌هایت نیست" }[tier] || "خبری در این نما نیست";
  el.innerHTML = items.length ? items.map(feedCard).join("")
    : `<div class="state"><div class="big">${empty}</div></div>`;
}
function setTier(t) {
  tier = t;
  document.querySelectorAll("#imp-filter .fchip").forEach(c =>
    c.classList.toggle("on", (c.getAttribute("onclick") || "").indexOf("'" + t + "'") >= 0));
  renderFeed();
}
function setFeedRange(r) { feedRange = r; document.querySelectorAll(".day-range-chips > .day-chip[data-range]").forEach(b => b.classList.toggle("on", String(b.dataset.range) === String(r))); renderFeed(); }
let sortMode = "imp";
function setSort(m) {
  sortMode = m;
  ["imp","new","sources","views","rising"].forEach(x => { const b=document.getElementById("sort-"+x); if(b) b.classList.toggle("on",m===x); });
  renderFeed();
}

// stories that share figures / topics with this one — the thread around it
function relatedStories(s) {
  const ents = new Set((s.entities || []).map(e => e.slug));
  const tops = new Set((s.topics || []).map(t => t.slug));
  return ALL.filter(c => c.id !== s.id).map(c => {
    let sc = 0;
    (c.entities || []).forEach(e => { if (ents.has(e.slug)) sc += 3; });
    (c.topics || []).forEach(t => { if (tops.has(t.slug)) sc += 1; });
    return { c, sc };
  }).filter(x => x.sc > 0)
    .sort((a, b) => b.sc - a.sc
      || String(b.c.published_at || "").localeCompare(String(a.c.published_at || "")))
    .slice(0, 8).map(x => x.c);
}
// a vertical timeline of this story + its related coverage (newest first)
function timelineSection(s, related) {
  if (!related.length) return "";
  const all = related.concat([{ __cur: true, id: s.id, headline_fa: s.headline_fa,
    published_at: s.published_at, source_count: s.source_count }]);
  all.sort((a, b) => String(b.published_at || "").localeCompare(String(a.published_at || "")));
  const rows = all.map(c => c.__cur
    ? `<div class="tl-item tl-cur"><span class="tl-dot"></span><div class="tl-body">
        <span class="tl-time">${relTime(c.published_at)}</span>
        <span class="tl-h">${esc(c.headline_fa || "")}</span><span class="tl-now">همین خبر</span></div></div>`
    : `<button class="tl-item" onclick="openStory('${c.id}')"><span class="tl-dot"></span><div class="tl-body">
        <span class="tl-time">${relTime(c.published_at)} · ${faN(c.source_count || 0)} منبع</span>
        <span class="tl-h">${esc(c.headline_fa || "")}</span></div></button>`).join("");
  return `<div class="layers"><h3 class="section-h">روندِ ماجرا <span class="n">خبرهای مرتبط، به‌ترتیبِ زمان</span></h3>
    <div class="timeline">${rows}</div></div>`;
}

async function storyPeopleSuggestions(s) {
  const d = await loadFigures();
  const norm = v => String(v || "").replace(/‌/g," ").replace(/\s+/g," ").trim();
  const names = new Set((s.person_statements || []).map(q => norm(q.person_name_fa)).filter(Boolean));
  (s.entities || []).forEach(e => {
    const n = norm(e.name_fa || e.name || e.label_fa);
    if (n) names.add(n);
  });
  const people = (d.figures || []).filter(f => names.has(norm(f.name_fa))).slice(0, 8);
  if (!people.length) return "";
  return `<div class="layers story-people"><h3 class="section-h">چهره‌های مرتبط <span class="n">پروفایل و گفته‌های بیشتر</span></h3>
    <div class="story-people-grid">${people.map(p => `<article class="story-person-card">
      <button class="story-person-main" onclick="openFigure('${esc(p.handle)}')">
        ${avatar(p,"md")}<span class="story-person-copy"><b>${esc(p.name_fa)}</b><small>${esc(p.role_fa||p.field_fa||"")}</small><em>${faN((p.posts||[]).length)} گفته</em></span>
      </button>
      ${figureFollowBtn(p.handle,true)}
    </article>`).join("")}</div></div>`;
}

async function openStory(id) {
  // Defensive normalization for copied/encoded deep links.  A stray control
  // character (e.g. %01 before a UUID) previously produced a valid-looking
  // route that could never match an exported story JSON file.
  const rawId = String(id || "");
  const uuidMatch = rawId.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
  const cleanId = uuidMatch ? uuidMatch[0] : rawId.replace(/[\\x00-\\x1F\\x7F]/g, "").trim();
  if (cleanId !== rawId) {
    history.replaceState(null, "", "#/story/" + encodeURIComponent(cleanId));
  } else {
    setHash("#/story/" + cleanId);
  }
  show("detail"); setTab("feed");
  const v = document.getElementById("detail-view");
  v.innerHTML = `<div class="spinner"></div>`;
  let s;
  try { s = await getJSON(`${DATA}/story/${cleanId}.json`); }
  catch (e) {
    // Deep links can outlive the compact feed.  Give a useful failure state
    // rather than leaving a blank/spinner page.
    v.innerHTML = `<button class="back" onclick="showFeed()">بازگشت به خط خبری</button><div class="state"><div class="big">این خبر در آرشیو فعلی پیدا نشد</div><p class="muted">شناسهٔ خبر: ${esc(cleanId)}</p></div>`;
    return;
  }

  const imp = impInfo(s.importance_score);
  const peopleSuggestions = await storyPeopleSuggestions(s);
  const li = a => (a || []).map(x => `<li>${esc(x)}</li>`).join("");
  const views = (s.source_views || []).map(sv => `<div class="view"><div class="v-h"><span class="v-name">${esc(sv.source_name)}</span></div><p>${esc(sv.viewpoint_fa || "")}</p></div>`).join("");
  const cites = (s.sources || []).map(c => `<a class="cite" href="${c.article_url || "#"}" target="_blank" rel="noopener">
      <div class="c-body"><div class="c-src">${esc(c.source_name)}</div><div class="c-title">${esc(c.original_headline || "")}</div></div>
      <span class="c-time">${relTime(c.published_at)}</span>
      <span class="ext"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17 17 7M8 7h9v9"/></svg></span></a>`).join("");
  const quotedPeople = (s.person_statements || []).length ? `
    <div class="layers"><h3 class="section-h">چه کسانی در این خبر حرف زده‌اند <span class="n">گفتهٔ شخص، با لینک منبع</span></h3>
      <div class="views">${(s.person_statements || []).map(q => `<div class="view fig-view">
        <div class="v-h"><button class="fig-profile-link v-name" onclick="openFigureByName('${esc(q.person_name_fa)}')">${esc(q.person_name_fa)}</button>
          <span class="fig-role">${esc(q.role_fa || "")}</span></div>
        <p>${esc(q.statement_fa || "")}</p>
        <div class="fig-foot"><span class="muted">${q.direct_quote ? "نقل‌قول مستقیم" : "گفته در گزارش"}</span>
          <a href="${esc(q.article_url)}" target="_blank" rel="noopener">منبع · ${esc(q.source_name)} ↗</a></div>
      </div>`).join("")}</div>
    </div>` : "";
  const known = (s.facts && s.facts.length) || (s.uncertainties && s.uncertainties.length) ? `
    <div class="layers"><h3 class="section-h">واقعیت در برابر ابهام</h3><div class="know">
      <div class="panel fact"><div class="p-h"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M20 6 9 17l-5-5"/></svg> آنچه معلوم است</div><ul>${li(s.facts)}</ul></div>
      <div class="panel warn"><div class="p-h"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.2 2.4c-.7.3-1.2.8-1.2 1.6v.3M12 17h.01"/></svg> آنچه هنوز نامشخص است</div><ul>${li(s.uncertainties)}</ul></div>
    </div></div>` : "";
  const consensus = (s.agreements && s.agreements.length) || (s.disagreements && s.disagreements.length) ? `
      <div class="consensus"><div class="cbox ag"><h4>نقطهٔ اشتراک</h4><p>${esc((s.agreements || [])[0] || "—")}</p></div>
        <div class="cbox dis"><h4>نقطهٔ اختلاف</h4><p>${esc((s.disagreements || [])[0] || "—")}</p></div></div>` : "";

  // Our own credibility signal + Factnameh link
  const c = s.credibility;
  const cred = c ? `
    <div class="layers"><h3 class="section-h">اعتبارِ خبر <span class="n">سنجهٔ خودکار — نه حکمِ نهایی</span></h3>
      <div class="cred-box ${c.level}">
        <div class="cred-top"><span class="cstatus ${CRED_CLS[c.level]}">${CRED_FA[c.level]}</span>
          <span class="cred-lbl">${esc(c.label_fa || "")}</span></div>
        <p class="cred-note">${esc(c.note_fa || "")}</p>
        <div class="cred-stats"><span>${faN(c.independent_sources)} منبعِ مستقل</span>
          <span class="dot"></span><span>${faN(c.agreements)} نقطهٔ اشتراک</span>
          <span class="dot"></span><span>${faN(c.disagreements)} نقطهٔ اختلاف</span></div>
      </div>
      ${s.factcheck ? `<a class="fc-link" href="${s.factcheck.url}" target="_blank" rel="noopener">
        <span class="fc-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3Z" stroke-linejoin="round"/><path d="M9 12l2 2 4-4" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
        <span class="fc-body"><b>راستی‌آزمایی‌شده در فکت‌نامه</b><span class="muted">${esc(s.factcheck.title || "مشاهدهٔ گزارش")}</span></span>
        <span class="ext"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17 17 7M8 7h9v9"/></svg></span></a>` : ""}
    </div>` : "";

  const tr = s.trend;
  const trendSec = (tr && tr.total_sources > 1) ? `
    <div class="layers"><h3 class="section-h">روندِ پوشش <span class="n">۴۸ ساعتِ اخیر</span> ${trendBadge(tr)}</h3>
      <div class="trend-box">
        <div class="trend-stat"><span class="ts-v">${faN(tr.total_sources)}</span><span>منبع تاکنون</span></div>
        <div class="trend-stat"><span class="ts-v">${faN(tr.velocity)}</span><span>در ۶ ساعتِ اخیر</span></div>
        <div class="trend-stat"><span class="ts-v">${faN(tr.ratio)}×</span><span>شتابِ پوشش</span></div>
      </div>
      <div class="chart-wrap">${svgSpark(tr.curve || [], { w: 320, h: 60 })}</div>
      <p class="muted" style="margin:6px 0 0">شمارِ تجمعیِ منابعِ مستقل که این خبر را پوشش داده‌اند؛ شیبِ تندتر یعنی خبر سریع‌تر در حالِ گسترش است.</p>
    </div>` : "";

  const chips = (s.asks || []).map((a, i) => `<button class="qchip" onclick="showAsk(${i})">${esc(a.q)}</button>`).join("");
  window._asks = s.asks || [];
  const relSection = timelineSection(s, relatedStories(s));

  v.innerHTML = `
    <button class="back" onclick="showFeed()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg> بازگشت به خط خبری</button>
    <div class="d-head"><div class="meta"><span class="chip">${CAT_FA[s.category] || "خبر"}</span><span class="dot"></span><span class="muted">${relTime(s.published_at)}</span>${trendBadge(s.trend)}<span class="spacer" style="flex:1"></span>${saveBtn(s.id)}</div>
      <h1>${esc(s.headline_fa || "")}</h1>
      <div class="d-meta"><span class="imp ${imp.cls}"><span class="bars"><i></i><i></i><i></i></span><span class="lbl">${imp.lbl}</span></span>
        <span class="dot"></span><span class="muted">${faN(s.source_count || 0)} منبع</span>
        <span class="dot"></span><span class="muted">${IRAN_FA[s.iran_relevance] || ""}</span></div></div>
    ${s.image_url ? `<img class="hero-img" src="${esc(s.image_url)}" alt="" loading="lazy" onerror="this.parentElement.querySelector('.hero-credit')?.remove();this.remove()">` : ''}
    ${s.image_url && s.image_credit ? `<div class="hero-credit">عکس از: ${esc(s.image_credit)}</div>` : ''}
    <div class="kalam-box"><span class="eyebrow">جان‌کلام <span class="ai">ترکیب هوش مصنوعی</span></span><p>${esc(s.summary_fa || "")}</p></div>
    ${detailGeoStrip(s)}
    ${peopleRow(s.entities)}
    ${peopleSuggestions}
    <div class="twocol"><div class="qa"><h3>چه اتفاقی افتاد؟</h3><p>${esc(s.what_happened_fa || "—")}</p></div>
      <div class="qa"><h3>چرا اهمیت دارد؟</h3><p>${esc(s.why_it_matters_fa || "—")}</p></div></div>
    ${known}
    ${cred}
    ${trendSec}
    ${relSection}
    <div class="layers"><h3 class="section-h">منابع چه می‌گویند <span class="n">دیدگاه هر منبع، جدا از واقعیت</span></h3><div class="views">${views || '<p class="muted">—</p>'}</div>${consensus}</div>
    ${figuresSection(s.figures)}
    <div class="layers"><h3 class="section-h">منابع</h3><div class="cites">${cites}</div></div>
    <div class="ask"><div class="a-h"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" style="color:var(--accent)"><path d="M21 11.5a8.5 8.5 0 0 1-12.3 7.6L3 21l1.9-5.7A8.5 8.5 0 1 1 21 11.5Z" stroke-linejoin="round"/></svg> دربارهٔ این خبر بپرس</div>
      <p class="a-sub">پاسخ‌های آماده از روی همین خبر.</p>
      <div class="chips">${chips}</div>
      <div class="answer" id="answer"><div class="a-bubble" id="a-bubble"></div>
        <div class="grounded"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M20 6 9 17l-5-5"/></svg> مبتنی بر منابع همین خبر</div></div>
    </div>`;
}
function showAsk(i) {
  document.querySelectorAll(".qchip").forEach(c => c.classList.remove("on"));
  document.getElementById("answer").classList.add("show");
  document.getElementById("a-bubble").textContent = (window._asks[i] || {}).a || "—";
}

/* ---- بورس اخبار ---- */
let _trendsLoaded = false;
const grp = n => Number(n).toLocaleString("en-US");
async function renderTrends() {
  if (_trendsLoaded) return;
  const el = document.getElementById("trends");
  try {
    if (!ALL.length) { try { ALL = await getJSON(`${DATA}/stories.json`); } catch (e) {} }
    const [t, st, ents] = await Promise.all([
      getJSON(`${DATA}/trends.json`),
      getJSON(`${DATA}/stats.json`).catch(() => null),
      getJSON(`${DATA}/entities.json`).catch(() => []),
    ]);
    const peopleChips = (ents || []).slice(0, 24).map(x =>
      `<span class="person-chip" data-slug="${esc(x.slug)}" onclick="openEntity(this.dataset.slug)">${esc(x.name_fa)} <span class="chip-n">${faN(x.count)}</span></span>`).join("");
    const peopleSection = peopleChips
      ? `<div class="rule" style="margin-top:22px"><span>چهره‌ها در خبرها</span><span class="l"></span></div>
         <div class="people-strip">${peopleChips}</div>` : "";
    const topics = (t.topics || []);
    const g = t.google || {};
    const googleOn = Object.keys(g).length > 0;
    const rows = topics.map(tp => {
      const series = tp.series || [];
      const cmp = g[tp.slug];
      const chart = cmp
        ? `<div class="tp-chart cmp">${svgCompare(series, cmp.points.map(p => p.v))}</div>
           <div class="cmp-legend"><span class="lg a">جان‌کلام</span><span class="lg b">گوگل ترندز</span></div>`
        : `<div class="tp-chart">${svgSpark(series, { w: 150, h: 34 })}</div>`;
      return `<button class="tp-row" onclick="openTrendDossier('${tp.slug}')">
        <div class="tp-head"><span class="tp-name">${esc(tp.name_fa)}</span>${growthTag(tp.growth)}
          <span class="tp-n">${faN(tp.story_count)} خبر · هفته: ${faN(tp.last7 == null ? tp.story_count : tp.last7)}</span></div>
        ${chart}</button>`;
    }).join("");
    const hot = (t.hottest || []).map(h => `<div class="ticker" onclick="openStory('${h.id}')" style="cursor:pointer">
      <span class="t-name">${esc(h.headline_fa)}<span class="t-cat">${CAT_FA[h.category] || ""}</span></span>
      <span class="t-val">${faN(h.source_count)}</span>
      <span class="t-chg tx-up"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M12 5v14M6 11l6-6 6 6" stroke-linecap="round" stroke-linejoin="round"/></svg>منبع</span></div>`).join("");
    const statsSection = st ? `<div class="rule" style="margin-top:2px"><span>نبض خبری</span><span class="l"></span></div>${statsBlock(st)}` : "";
    el.innerHTML = `
      ${statsSection}
      <div class="tx-hero"><span class="val">${faN(t.story_total || 0)}</span><span class="lbl">خبرِ فعال روی تخته</span>
        <span class="spacer" style="flex:1"></span><span class="lbl">${faN(topics.length)} موضوع فعال</span></div>
      ${peopleSection}
      <div class="rule"><span>رشدِ موضوع‌ها <span class="n">۱۴ روزِ اخیر</span></span><span class="l"></span></div>
      <div class="tp-board">${rows || '<p class="muted">—</p>'}</div>
      ${googleOn ? '' : '<p class="muted" style="margin:8px 0 0">مقایسه با گوگل ترندز فعلاً در دسترس نیست (آزمایشی).</p>'}
      <div class="rule" style="margin-top:26px"><span>پرپوشش‌ترین خبرها</span><span class="l"></span></div>
      <div class="tickers">${hot || '<p class="muted">—</p>'}</div>
      <p class="muted" style="margin-top:18px">«رشد» = مقایسهٔ خبرهای این هفته با هفتهٔ پیش. «پوشش» = چند منبعِ مستقل یک خبر را گفته‌اند.</p>`;
    _trendsLoaded = true;
  } catch (e) {
    el.innerHTML = `<div class="state"><div class="big">بورس اخبار بارگذاری نشد</div></div>`;
  }
}

/* ---- فکت — hub with sub-tabs: needs-verification / disagreement / Factnameh ---- */
function fcCard(f) {
  return `<a class="card fc-card" href="${f.url}" target="_blank" rel="noopener">
    <div class="meta"><span class="chip">فکت‌نامه</span><span class="dot"></span><span class="muted">${esc((f.published || "").slice(0, 10))}</span>
      <span class="ext" style="margin-inline-start:auto"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17 17 7M8 7h9v9"/></svg></span></div>
    <h2>${esc(f.title)}</h2>${f.summary ? `<p class="kalam">${esc(f.summary)}</p>` : ""}</a>`;
}
let _factData = { needs: [], disp: [], fn: [] };
async function renderFactchecks() {
  const el = document.getElementById("factchecks");
  try {
    if (!ALL.length) { try { ALL = await getJSON(`${DATA}/stories.json`); } catch (e) {} }
    const fn = await getJSON(`${DATA}/factchecks.json`).catch(() => []);
    const needs = ALL.filter(s => s.credibility && s.credibility.needs_verification);
    const disp = ALL.filter(s => s.credibility && (s.credibility.disagreements || 0) > 0);
    _factData = { needs, disp, fn };
    const tabs = [["needs", "نیازمندِ راستی‌آزمایی", needs.length],
                  ["disp", "اختلافِ منابع", disp.length],
                  ["fn", "فکت‌نامه", fn.length]];
    const first = (tabs.find(t => t[2] > 0) || tabs[0])[0];
    el.innerHTML = `<div class="fact-note">این سنجه‌ها <b>خودکار</b>ند و از روی منابعِ هر خبر ساخته می‌شوند — نه حکمِ نهایی. راستی‌آزماییِ قطعی کارِ فکت‌نامه است.</div>
      <div class="imp-filter" id="fact-tabs">${tabs.map(t => `<button class="fchip" data-k="${t[0]}" onclick="setFactTab('${t[0]}')">${t[1]}${t[2] ? ` <span class="chip-n">${faN(t[2])}</span>` : ""}</button>`).join("")}</div>
      <div id="fact-body"></div>`;
    setFactTab(first);
  } catch (e) { el.innerHTML = `<div class="state"><div class="big">بارگذاری نشد</div></div>`; }
}
function setFactTab(k) {
  document.querySelectorAll("#fact-tabs .fchip").forEach(c => c.classList.toggle("on", c.dataset.k === k));
  const d = _factData;
  const b = document.getElementById("fact-body");
  const empty = `<div class="state"><div class="big">موردی نیست</div></div>`;
  if (k === "needs")
    b.innerHTML = d.needs.length ? `<p class="muted" style="margin:0 0 12px">خبرهای تک‌منبع که هنوز منبعِ مستقلِ دیگری تأییدشان نکرده.</p><div class="feed">${d.needs.map(feedCard).join("")}</div>` : empty;
  else if (k === "disp")
    b.innerHTML = d.disp.length ? `<p class="muted" style="margin:0 0 12px">خبرهایی که منابع در جزئیاتشان با هم اختلاف دارند.</p><div class="feed">${d.disp.map(feedCard).join("")}</div>` : empty;
  else
    b.innerHTML = d.fn.length ? `<p class="muted" style="margin:0 0 12px">راستی‌آزماییِ مستقل و حرفه‌ای (شریکِ برنامهٔ متا). روی هر مورد بزن.</p><div class="feed">${d.fn.map(fcCard).join("")}</div>` : empty;
}

/* ---- راهنما / FAQ ---- */
let _faqLoaded = false;
const FAQ = [
  ["خبرها از کجا می‌آیند؟",
    "جان‌کلام به‌طور خودکار از فیدِ (RSS) ده‌ها خبرگزاری می‌خواند: منابعِ جهانی (رویترز، AP، بی‌بی‌سی، گاردین، الجزیره)، منابعِ داخلیِ فارسی (ایرنا، ایسنا، تسنیم) و منابعِ فارسیِ برون‌مرزی (بی‌بی‌سی فارسی، ایران اینترنشنال، رادیو فردا، دویچه‌وله). هدف این است که هم روایتِ داخلی و هم روایتِ خارجی کنارِ هم دیده شوند."],
  ["چطور از چند منبع یک خبر می‌سازد؟",
    "سیستم خبرهایی که دربارهٔ یک رویدادِ واحد هستند را «خوشه‌بندی» می‌کند: عنوان‌ها و متن‌ها را مقایسه می‌کند و گزارش‌های مربوط به یک اتفاق را در یک خبرِ واحد کنار هم می‌گذارد. برای همین زیرِ هر خبر می‌بینی «۳ منبع» یا «۵ منبع»."],
  ["منظور از تفکیکِ «واقعیت / دیدگاه / جان‌کلام / ابهام» چیست؟",
    "هر خبر چهار لایه دارد که عمداً از هم جدا نگه داشته شده‌اند: <b>واقعیت</b> (آنچه معلوم است)، <b>دیدگاهِ هر منبع</b> (هر خبرگزاری چه می‌گوید، جدا از بقیه)، <b>جان‌کلام</b> (خلاصهٔ کوتاهِ ترکیبی)، و <b>ابهام</b> (آنچه هنوز روشن نیست). این‌طوری تحلیل با واقعیت قاطی نمی‌شود."],
  ["برچسبِ «مهم / بسیار مهم» چطور حساب می‌شود؟",
    "یک امتیازِ شفاف از ۱۰۰ که از پنج عامل ساخته می‌شود: تعدادِ منابعِ مستقل (تا ۳۵)، اعتبارِ منابع (تا ۲۰)، سرعتِ پوشش/تعدادِ گزارش‌ها (تا ۱۵)، تازگیِ خبر (تا ۲۰)، و میزانِ ارتباط با ایران (تا ۱۰). امتیازِ ۷۵ به بالا «بسیار مهم»، ۵۰ تا ۷۵ «مهم»، و پایین‌تر «متوسط» است. هیچ‌چیزِ آن جعبهٔ سیاه نیست."],
  ["«اعتبارِ خبر» با فکت‌نامه چه فرقی دارد؟",
    "«اعتبارِ خبر» یک سنجهٔ <b>خودکارِ</b> ماست که فقط به دو چیز نگاه می‌کند: چند منبعِ مستقل خبر را گفته‌اند و آیا با هم توافق دارند یا اختلاف. خبرِ تک‌منبعی برچسبِ «نیازمند راستی‌آزمایی» می‌گیرد. این «حکمِ درست/غلط» نیست — فقط نشان می‌دهد یک ادعا چقدر پشتوانهٔ چندمنبعی دارد. راستی‌آزماییِ واقعی و انسانی کارِ نهادهایی مثلِ فکت‌نامه است."],
  ["فکت‌نامه چیست و کِی برچسبش را می‌بینم؟",
    "فکت‌نامه یک نهادِ مستقل و حرفه‌ایِ راستی‌آزمایی به فارسی است (شریکِ برنامهٔ راستی‌آزماییِ متا). آخرین گزارش‌هایش را در بخشِ «فکت‌نامه» می‌بینی، و اگر یکی از خبرهای ما با یک گزارشِ فکت‌نامه هم‌موضوع باشد، رویِ آن خبر برچسبِ «راستی‌آزمایی‌شده در فکت‌نامه» با لینک ظاهر می‌شود."],
  ["ارتباط با ایران چطور تعیین می‌شود؟",
    "بر اساسِ واژه‌های کلیدیِ مرتبط با ایران در متنِ خبر. اگر ربطی نباشد، سیستم به‌زور ربطی نمی‌سازد — خبر بی‌ارتباط صریحاً «بدون ارتباط مستقیم با ایران» علامت می‌خورد."],
  ["کپی‌رایت چه می‌شود؟ آیا متنِ کاملِ خبرها را می‌آورید؟",
    "نه. جان‌کلام هیچ‌وقت متنِ کاملِ مقاله‌ها را بازنشر نمی‌کند. فقط خلاصهٔ کوتاه می‌سازد و به منبعِ اصلی لینک می‌دهد تا خودت آنجا کامل بخوانی."],
  ["هوش مصنوعی دقیقاً چه‌کار می‌کند؟",
    "خلاصه و تفکیکِ چهارلایه را یک مدلِ هوش مصنوعی (جمینای) می‌سازد، اما خروجی‌اش پیش از انتشار اعتبارسنجیِ ساختاری می‌شود و همیشه به منابعِ واقعی گره خورده است. متنِ منابع دست‌نخورده و لینک‌دار می‌ماند."],
  ["هر چند وقت به‌روز می‌شود؟",
    "هر یک ساعت، به‌صورتِ خودکار. زمانِ آخرین به‌روزرسانی بالای «خط خبری» نوشته شده است."],
];
function renderFaq() {
  if (_faqLoaded) return;
  document.getElementById("faq").innerHTML = FAQ.map(([q, a]) =>
    `<details class="faq-item"><summary>${esc(q)}</summary><div class="faq-a">${a}</div></details>`).join("")
    + `<p class="muted" style="margin-top:18px;text-align:center">جان‌کلام — واقعیت جدا از تحلیل، هر منبع به‌تفکیک.</p>`;
  _faqLoaded = true;
}

async function renderTopics() {
  const el = document.getElementById("topic-grid");
  try {
    if (!ALL.length) { try { ALL = await getJSON(`${DATA}/stories.json`); } catch (e) {} }
    const topics = await getJSON(`${DATA}/topics.json`);
    const counted = topics
      .map(t => ({ ...t, n: ALL.filter(s => (s.topics || []).some(x => x.slug === t.slug)).length }))
      .filter(t => t.n > 0)
      .sort((a, b) => b.n - a.n);
    if (!counted.length) {
      el.innerHTML = `<div class="state"><div class="big">هنوز موضوعی دسته‌بندی نشده</div><p class="muted">با به‌روزرسانیِ بعدی پر می‌شود.</p></div>`;
      return;
    }
    el.innerHTML = counted.map(t => `<div class="topic" role="button" tabindex="0" onclick="openTopic('${t.slug}')">
      <div class="t-body"><div class="t-fa">${esc(t.name_fa)}</div><div class="t-count">${faN(t.n)} خبر</div></div>
      ${followBtn("topics", t.slug, "دنبال", "دنبال کن")}</div>`).join("");
  } catch (e) { el.innerHTML = `<div class="state"><div class="big">موضوعات بارگذاری نشد</div></div>`; }
}

// archive feed grouped by importance tier ("به تفکیک اهمیت")
const TIERS = [["high", "بسیار مهم"], ["mid", "مهم"], ["low", "متوسط"]];
function groupedFeed(items) {
  if (!items.length) return `<div class="state"><div class="big">خبری نیست</div></div>`;
  let html = "";
  for (const [cls, label] of TIERS) {
    const g = items.filter(s => tierOf(s) === cls);
    if (!g.length) continue;
    html += `<div class="rule"><span>${label}</span><span class="l"></span></div>
      <div class="feed">${g.map(feedCard).join("")}</div>`;
  }
  return html;
}

/* ---- Day archive: خبرهای «امروز/دیروز/…» با تفکیک دسته ---- */
// UTC date (YYYY-MM-DD) — matches what stories.published_at.slice(0,10) uses.
function utcDayISO(offsetDays) {
  offsetDays = offsetDays || 0;
  return new Date(Date.now() + offsetDays * 86400e3).toISOString().slice(0, 10);
}
function dayLabel(dateStr) {
  if (dateStr === utcDayISO(0)) return "امروز";
  if (dateStr === utcDayISO(-1)) return "دیروز";
  const diff = Math.floor((Date.parse(utcDayISO(0)) - Date.parse(dateStr)) / 86400e3);
  if (diff > 1 && diff < 30) return faN(diff) + " روز پیش";
  return dateStr;
}
function groupedByCategory(items) {
  if (!items.length)
    return `<div class="state"><div class="big">خبری در این روز نیست</div></div>`;
  const order = Object.keys(CAT_FA).concat(["_other"]);
  const groups = {};
  items.forEach(s => {
    const k = CAT_FA[s.category] ? s.category : "_other";
    (groups[k] = groups[k] || []).push(s);
  });
  let html = "";
  for (const k of order) {
    const g = groups[k]; if (!g || !g.length) continue;
    const label = k === "_other" ? "سایر" : CAT_FA[k];
    html += `<div class="rule"><span>${esc(label)} <span class="n">${faN(g.length)}</span></span><span class="l"></span></div>
      <div class="feed">${g.map(feedCard).join("")}</div>`;
  }
  return html;
}
function openDay(dateStr) {
  if (!ALL.length) return;
  setHash("#/day/" + dateStr);
  show("topicarchive"); setTab("feed");
  document.getElementById("ta-back-t").textContent = "بازگشت به خط خبری";
  document.getElementById("ta-back").onclick = showFeed;
  const items = ALL.filter(s => (s.published_at || "").slice(0, 10) === dateStr);
  document.getElementById("ta-title").textContent = "خبرهای " + dayLabel(dateStr);
  document.getElementById("ta-sub").textContent = faN(items.length) + " خبر · " + dateStr;
  document.getElementById("ta-feed").innerHTML = groupedByCategory(items);
}

async function openTrendDossier(slug) {
  if (!ALL.length) { try { ALL = await getJSON(`${DATA}/stories.json`); } catch (e) {} }
  const t = await getJSON(`${DATA}/trends.json`).catch(() => ({ topics: [] }));
  const tp = (t.topics || []).find(x => x.slug === slug);
  if (!tp) return openTopic(slug);
  setHash("#/trend/" + slug);
  show("topicarchive"); setTab("trends");
  document.getElementById("ta-back-t").textContent = "بازگشت به بورس اخبار";
  document.getElementById("ta-back").onclick = showTrends;
  document.getElementById("ta-title").textContent = "جانِ ماجرا: " + (tp.name_fa || slug);
  const d = tp.dossier || {};
  document.getElementById("ta-sub").textContent =
    faN(d.development_count || tp.story_count || 0) + " تحول مستقل · " +
    faN(d.source_coverage || tp.coverage || 0) + " پوشش منبع";
  const ids = new Set(d.story_ids || []);
  const items = ALL.filter(s => ids.has(s.id) || (s.topics || []).some(x => x.slug === slug));
  const timeline = items.slice().sort((a,b) => String(b.published_at||"").localeCompare(String(a.published_at||"")));
  document.getElementById("ta-feed").innerHTML =
    `<div class="trend-dossier">
      <div class="rule"><span>جانِ ماجرا</span><span class="l"></span></div>
      <p class="kalam">${esc(d.summary_fa || "این پرونده از چند تحول خبری مستقل ساخته شده است.")}</p>
      ${d.why_now_fa ? `<div class="rule"><span>چرا الان مهم است؟</span><span class="l"></span></div><p class="kalam">${esc(d.why_now_fa)}</p>` : ""}
      <div class="trend-dossier-stats"><span><b>${faN(d.development_count || tp.story_count || 0)}</b> تحول مستقل</span><span><b>${faN(d.source_coverage || tp.coverage || 0)}</b> پوشش منبع</span>${tp.growth != null ? `<span><b>${faN(tp.growth)}٪</b> رشد</span>` : ""}</div>
      <div class="rule"><span>مسیر ماجرا</span><span class="l"></span></div>
    </div>` + groupedFeed(timeline);
}

function openTopic(slug) {
  setHash("#/topic/" + slug);
  show("topicarchive"); setTab("topics");
  document.getElementById("ta-back-t").textContent = "بازگشت به موضوعات";
  document.getElementById("ta-back").onclick = showTopics;
  const items = ALL.filter(s => (s.topics || []).some(t => t.slug === slug));
  const name = ((items[0] && items[0].topics.find(t => t.slug === slug)) || {}).name_fa || slug;
  document.getElementById("ta-title").textContent = "موضوع: " + name;
  document.getElementById("ta-sub").textContent = faN(items.length) + " خبر در این موضوع";
  document.getElementById("ta-feed").innerHTML = groupedFeed(items);
}

// pre-baked reference links (persian + english wikipedia + Grokipedia) so a
// reader can pick up context from multiple encyclopedias with different tones
// and compare — same "چند منبع، خودت مقایسه کن" ethos as the news layer.
function referenceStrip(ent) {
  if (!ent || !ent.refs) return "";
  const links = ent.refs.map(r => `<a href="${esc(r.url)}" target="_blank" rel="noopener">
    <span class="ref-src">${esc(r.src)}</span>${esc(r.label)}</a>`).join("");
  return `<div class="ref-strip">
    <div class="ref-hd"><b>پیش‌زمینه از چند مرجع</b> — روایت‌ها متفاوت است، خودتان مقایسه کنید.</div>
    <div class="ref-links">${links}</div></div>`;
}

// a figure's page: all their stories in one place (+ follow into "my feed")
function openEntity(slug) {
  if (!ALL.length) return;
  setHash("#/person/" + slug);
  show("topicarchive"); setTab("feed");
  document.getElementById("ta-back-t").textContent = "بازگشت به خط خبری";
  document.getElementById("ta-back").onclick = showFeed;
  const items = ALL.filter(s => (s.entities || []).some(e => e.slug === slug));
  const meta = items.flatMap(s => s.entities || []).find(e => e.slug === slug) || {};
  const name = meta.name_fa || slug;
  document.getElementById("ta-title").textContent = (meta.kind === "body" ? "نهاد: " : "چهره: ") + name;
  document.getElementById("ta-sub").textContent = faN(items.length) + " خبر مرتبط";
  document.getElementById("ta-feed").innerHTML =
    followBar("entities", slug, "خبرهای این چهره در «خط خبری من» بیاید")
    + referenceStrip(meta) + groupedFeed(items);
}

function followBar(kind, id, note) {
  return `<div class="follow-bar">${followBtn(kind, id, "در حال دنبال‌کردن", "دنبال کن")}<span class="fb-note">${esc(note)}</span></div>`;
}
function openSource(name) {
  if (!ALL.length) return;
  setHash("#/source/" + encodeURIComponent(name));
  show("topicarchive"); setTab("feed");
  document.getElementById("ta-back-t").textContent = "بازگشت به خط خبری";
  document.getElementById("ta-back").onclick = showFeed;
  const items = ALL.filter(s => (s.source_names || []).includes(name));
  document.getElementById("ta-title").textContent = "منبع: " + name;
  document.getElementById("ta-sub").textContent = faN(items.length) + " خبر از این منبع";
  document.getElementById("ta-feed").innerHTML = followBar("sources", name, "خبرهای این منبع در «خط خبری من» بیاید") + groupedFeed(items);
}

/* ---- ایران — province map + scope classification ----
   نقشهٔ واقعیِ استان‌ها (choropleth): مسیرهای دقیق در iran-provinces.js
   (برگرفته از masoudnemati/iran-map با مجوز MIT). */
const PATHS = (typeof window !== "undefined" && window.IRAN_PATHS) || {};
const VIEWBOX = (typeof window !== "undefined" && window.IRAN_VIEWBOX) || "0 0 990 890";

let _iranScope = "all";
function showIran() { show("iran"); setTab("iran"); renderIran(); setHash("#/iran"); }
async function renderIran() {
  const el = document.getElementById("iran");
  try {
    if (!ALL.length) { try { ALL = await getJSON(`${DATA}/stories.json`); } catch (e) {} }
    const geo = await getJSON(`${DATA}/geo.json`).catch(() => ({ provinces: {}, scope: {} }));
    const pc = geo.provinces || {};
    const max = Math.max(1, ...Object.values(pc));
    const paths = Object.entries(PATHS).map(([slug, p]) => {
      const n = pc[slug] || 0;
      const alpha = n ? (0.30 + 0.70 * (n / max)) : 0;
      const fill = n ? ` fill="rgba(26,157,126,${alpha.toFixed(3)})"` : "";
      const cls = "prov" + (n ? " has" : "");
      const tip = esc(p.fa) + (n ? ` — ${faN(n)} خبر` : "");
      return `<path d="${p.d}" class="${cls}"${fill} onclick="openProvince('${slug}')"><title>${tip}</title></path>`;
    }).join("");
    const sc = geo.scope || {};
    const total = (sc.local || 0) + (sc.national || 0) + (sc.international || 0);
    const scopes = [["all", "همه", total], ["local", "استانی", sc.local || 0],
      ["national", "کشوری", sc.national || 0], ["international", "بین‌المللی", sc.international || 0]];
    const provChips = Object.entries(PATHS).map(([slug, p]) => {
      const n = pc[slug] || 0, on = isF("provinces", slug);
      return `<button class="pfollow ${on ? "on" : ""}" onclick="hitProvFollow('${slug}',this)"><span class="pf-star">★</span>${esc(p.fa)}${n ? ` <span class="chip-n">${faN(n)}</span>` : ""}</button>`;
    }).join("");
    el.innerHTML = `
      <div class="iran-map">
        <svg viewBox="${VIEWBOX}" class="iran-svg" role="img" aria-label="نقشهٔ استان‌های ایران">${paths}</svg>
      </div>
      <p class="muted" style="text-align:center;margin:2px 0 12px">روی هر استان بزن تا خبرهایش را ببینی — رنگِ پررنگ‌تر یعنی خبرِ بیشتر.</p>
      <details class="prov-follow"><summary>دنبال‌کردنِ استان‌ها ★</summary>
        <p class="muted" style="margin:8px 0">استان‌هایی که دنبال کنی، خبرهایشان در «خط خبری من» می‌آید (روی این دستگاه ذخیره می‌شود).</p>
        <div class="pfollow-grid">${provChips}</div></details>
      <div class="imp-filter" id="iran-scopes">${scopes.map(s => `<button class="fchip" data-s="${s[0]}" onclick="setIranScope('${s[0]}')">${s[1]}${s[2] ? ` <span class="chip-n">${faN(s[2])}</span>` : ""}</button>`).join("")}</div>
      <div id="iran-body"></div>`;
    setIranScope(_iranScope);
  } catch (e) { el.innerHTML = `<div class="state"><div class="big">صفحهٔ ایران بارگذاری نشد</div></div>`; }
}
function setIranScope(s) {
  _iranScope = s;
  document.querySelectorAll("#iran-scopes .fchip").forEach(c => c.classList.toggle("on", c.dataset.s === s));
  const items = s === "all" ? ALL : ALL.filter(x => x.geo && x.geo.scope === s);
  document.getElementById("iran-body").innerHTML = groupedFeed(items);
}
function openProvince(slug) {
  if (!ALL.length) return;
  setHash("#/province/" + slug);
  show("topicarchive"); setTab("iran");
  document.getElementById("ta-back-t").textContent = "بازگشت به ایران";
  document.getElementById("ta-back").onclick = showIran;
  const items = ALL.filter(s => s.geo && (s.geo.provinces || []).some(p => p.slug === slug));
  const name = (PATHS[slug] || {}).fa || slug;
  document.getElementById("ta-title").textContent = "استان: " + name;
  document.getElementById("ta-sub").textContent = faN(items.length) + " خبر در این استان";
  document.getElementById("ta-feed").innerHTML = followBar("provinces", slug, "خبرهای این استان در «خط خبری من» بیاید") + groupedFeed(items);
}
function hitProvFollow(slug, btn) {
  toggleF("provinces", slug);
  btn.classList.toggle("on", isF("provinces", slug));
  updateMineBadge();
}

const root = document.documentElement;
document.getElementById("theme").addEventListener("click", () => {
  const cur = root.getAttribute("data-theme"), sysDark = matchMedia("(prefers-color-scheme:dark)").matches;
  root.setAttribute("data-theme", (cur === "dark" || (!cur && sysDark)) ? "light" : "dark");
});
if ("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));

// freshness line: when the SYSTEM last checked, and how old the NEWEST story is
let META = null;
getJSON(`${DATA}/meta.json`).then(m => { META = m; updateFreshness(); }).catch(() => {});
function updateFreshness() {
  const el = document.getElementById("built"); if (!el) return;
  const parts = [];
  if (META && (META.built_iso || META.built)) parts.push("آخرین بازبینیِ سیستم: " + (META.built_iso ? relTime(META.built_iso) : META.built));
  if (ALL && ALL.length) {
    const newest = ALL.map(s => s.published_at).filter(Boolean).sort().slice(-1)[0];
    if (newest) parts.push("تازه‌ترین خبر: " + relTime(newest));
  }
  if (parts.length) el.textContent = parts.join(" · ");
}

// compact price strip on the home page (dollar / euro / lira / emami coin)
async function renderHomePrices() {
  const el = document.getElementById("home-prices");
  if (!el) return;
  try {
    const prices = await getJSON(`${DATA}/prices.json`);
    if (!prices || !prices.length) return;
    const want = ["دلار آمریکا", "یورو", "لیر ترکیه", "سکه امامی"];
    const pick = want.map(w => prices.find(p => p.label_fa === w)).filter(Boolean);
    if (!pick.length) return;
    el.innerHTML = pick.map(p => {
      const cls = p.dir === "up" ? "up" : p.dir === "down" ? "down" : "flat";
      const arrow = p.dir === "up" ? "▲" : p.dir === "down" ? "▼" : "—";
      return `<div class="hp"><span class="hp-label">${esc(p.label_fa)}</span>
        <span class="hp-val">${faN(grp(p.value))}</span>
        <span class="hp-chg ${cls}">${arrow} ${faN(Math.abs(p.dp || 0))}٪</span></div>`;
    }).join("") + `<button class="hp-more" onclick="showMarket()">بازار ›</button>`;
  } catch (e) {}
}

// Compact market + weather table directly below the home stats.
async function renderHomeGlance() {
  const el = document.getElementById("home-glance");
  if (!el) return;
  try {
    const [prices, weather] = await Promise.all([
      getJSON(`${DATA}/prices.json`).catch(() => []),
      getJSON(`${DATA}/weather.json`).catch(() => [])
    ]);
    const usd = (prices || []).find(p => p.label_fa === "دلار آمریکا");
    const tr = (prices || []).find(p => p.label_fa === "لیر ترکیه");
    const cities = ["نوشهر", "چالوس", "کرمان", "تهران"]
      .map(name => (weather || []).find(w => w.city_fa === name)).filter(Boolean);
    const delta = (n, unit="") => {
      if (n === null || n === undefined || Number.isNaN(Number(n))) return "";
      const v=Number(n), cls=v>0?"up":v<0?"down":"flat", sign=v>0?"+":v<0?"−":"";
      return `<span class="hg-delta ${cls}">${sign}${faN(grp(Math.abs(v)))}${unit} <i>۲۴ساعت</i></span>`;
    };
    const market = [usd, tr].filter(Boolean).map(p =>
      `<button class="hg-cell" onclick="showMarket()"><span class="hg-label">${esc(p.label_fa)}</span><b>${faN(grp(p.value))}</b>${delta(p.delta24,"")}<small>تومان · ${p.dp ? faN(Math.abs(p.dp))+"٪" : "بدون تغییر"}</small></button>`
    ).join("");
    const wx = cities.map(c =>
      `<button class="hg-cell" onclick="showWeather()"><span class="hg-label">${c.icon || "🌡️"} ${esc(c.city_fa)}</span><b>${faN(c.temp)}°</b>${delta(c.delta24,"°")}<small>${esc(c.cond_fa || "")} · ${faN(c.min)}°/${faN(c.max)}°</small></button>`
    ).join("");
    if (!market && !wx) return;
    el.innerHTML = `<div class="hg-grid">${market}${wx}</div>`;
  } catch (_) {}
}

// Homepage Jan-e Majra: a compact window into the strongest current topic dossiers.
function scrollHomeMajra(dir) {
  const el = document.getElementById("home-majra-cards");
  if (!el) return;
  const card = el.querySelector(".hm-strip-card");
  const step = card ? card.getBoundingClientRect().width + 10 : 300;
  el.scrollBy({ left: dir * step, behavior: "smooth" });
}

async function renderHomeMajra() {
  const section = document.getElementById("home-majra");
  const el = document.getElementById("home-majra-cards");
  if (!section || !el) return;
  try {
    const [t, stories] = await Promise.all([
      getJSON(`${DATA}/trends.json`, 18000),
      getJSON(`${DATA}/stories.json`).catch(() => [])
    ]);
    const byId = new Map((stories || []).map(s => [String(s.id), s]));
    // A single story can be attached to several topic/trend slugs. On the
    // homepage that used to render the same event more than once. Keep the
    // highest-ranked topic for each lead story; topics without a resolvable
    // lead story get a stable dossier key instead.
    const seenMajra = new Set();
    const topics = [];
    for (const tp of (t.topics || []).filter(x => x && x.slug)) {
      const ids = (tp.dossier && tp.dossier.story_ids) || [];
      const story = ids.map(id => byId.get(String(id))).find(Boolean);
      const key = story ? `story:${story.id}` : `dossier:${tp.slug}`;
      if (seenMajra.has(key)) continue;
      seenMajra.add(key);
      topics.push(tp);
      if (topics.length >= 8) break;
    }
    if (!topics.length) { section.style.display = "none"; return; }
    el.innerHTML = topics.map(tp => {
      const d = tp.dossier || {};
      const story = (d.story_ids || []).map(id => byId.get(String(id))).find(Boolean);
      const image = story && story.image_url
        ? `<img loading="lazy" src="${esc(story.image_url)}" alt="" onerror="this.parentElement.classList.add('no-img');this.remove()">`
        : "";
      const dossierName = tp.name_fa || tp.slug;
      const latestHeadline = story && story.headline_fa ? story.headline_fa : "";
      const when = story && story.published_at ? relTime(story.published_at) : "";
      return `<button class="hm-strip-card ${image ? "" : "no-img"}" onclick="openTrendDossier('${esc(tp.slug)}')">
        <span class="hm-strip-media">${image}</span>
        <span class="hm-strip-copy">
          <span class="hm-dossier-name">${esc(dossierName)}</span>
          ${latestHeadline ? `<strong>${esc(latestHeadline)}</strong>` : ""}
          ${when ? `<small>${esc(when)}</small>` : ""}
        </span>
      </button>`;
    }).join("");
    if (!section.querySelector(".hm-scroll-controls")) {
      section.insertAdjacentHTML("beforeend", `<div class="hm-scroll-controls" aria-label="مرور جان ماجرا">
        <button onclick="scrollHomeMajra(1)" aria-label="قبلی">›</button>
        <button onclick="scrollHomeMajra(-1)" aria-label="بعدی">‹</button>
      </div>`);
    }
    section.style.display = "";
  } catch (e) {
    section.style.display = "none";
  }
}

// بازار — dedicated market page (full price board)
function showMarket() { show("market"); setTab("feed"); renderMarket(); setHash("#/market"); }
async function renderMarket() {
  const el = document.getElementById("market");
  try {
    const [prices, crypto] = await Promise.all([
      getJSON(`${DATA}/prices.json`).catch(() => []),
      getJSON(`${DATA}/crypto.json`).catch(() => []),
    ]);
    if ((!prices || !prices.length) && (!crypto || !crypto.length)) {
      el.innerHTML = `<div class="state"><div class="big">نرخ‌ها در دسترس نیست</div></div>`; return;
    }
    const priceRows = (prices || []).map(p => {
      const cls = p.dir === "up" ? "up" : p.dir === "down" ? "down" : "flat";
      const arrow = p.dir === "up" ? "▲" : p.dir === "down" ? "▼" : "—";
      return `<div class="price"><div class="p-label">${esc(p.label_fa)}</div>
        <div class="p-val">${faN(grp(p.value))} <span class="p-unit">${esc(p.unit_fa)}</span></div>
        <div class="p-chg ${cls}">${arrow} ${faN(Math.abs(p.dp || 0))}٪</div></div>`;
    }).join("");
    const cryptoRows = (crypto || []).map(p => {
      const cls = p.dir === "up" ? "up" : p.dir === "down" ? "down" : "flat";
      const arrow = p.dir === "up" ? "▲" : p.dir === "down" ? "▼" : "—";
      const value = p.value >= 1000 ? grp(Math.round(p.value)) : Number(p.value).toLocaleString("en-US", {maximumFractionDigits: p.value < 1 ? 4 : 2});
      return `<div class="price crypto-price"><div class="p-label">${esc(p.label_fa)} <span class="p-symbol">${esc(p.symbol || "")}</span></div>
        <div class="p-val">$ ${faN(value)}</div>
        <div class="p-chg ${cls}">${arrow} ${faN(Math.abs(p.dp || 0))}٪ <span class="p-unit">۲۴ساعت</span></div></div>`;
    }).join("");
    const fiatUnits = (prices || []).filter(p => ["دلار آمریکا","یورو","پوند","لیر ترکیه","درهم امارات"].includes(p.label_fa))
      .map(p => ({ id: "fiat:" + p.label_fa, label: p.label_fa, toman: Number(p.value) }));
    const usdToman = (fiatUnits.find(x => x.label === "دلار آمریکا") || {}).toman || 0;
    const cryptoUnits = (crypto || []).filter(p => Number(p.value) > 0 && usdToman > 0)
      .map(p => ({ id: "crypto:" + p.symbol, label: p.label_fa + " (" + p.symbol + ")", toman: Number(p.value) * usdToman }));
    window.JK_MARKET_UNITS = [{id:"toman",label:"تومان",toman:1}, ...fiatUnits, ...cryptoUnits];

    el.innerHTML =
      `<div class="rule"><span>تبدیل واحد مالی</span><span class="l"></span></div>
       <div class="money-converter">
         <div class="mc-field"><label>مقدار</label><input id="mc-amount" type="number" inputmode="decimal" min="0" step="any" value="1" oninput="convertMarketUnit()"></div>
         <div class="mc-field"><label>از</label><select id="mc-from" onchange="convertMarketUnit()"></select></div>
         <button class="mc-swap" onclick="swapMarketUnits()" aria-label="جابه‌جایی واحدها">⇄</button>
         <div class="mc-field"><label>به</label><select id="mc-to" onchange="convertMarketUnit()"></select></div>
         <div class="mc-result" id="mc-result">—</div>
       </div>` +
      (priceRows ? `<div class="rule"><span>ارز و طلا</span><span class="l"></span></div><div class="price-grid">${priceRows}</div>` : "") +
      (cryptoRows ? `<div class="rule" style="margin-top:26px"><span>رمزارزها</span><span class="l"></span></div><div class="price-grid crypto-grid">${cryptoRows}</div>` : "") +
      `<p class="muted" style="margin-top:14px">ارز و طلا: TGJU · رمزارزها: CoinGecko. تبدیل‌ها تقریبی و بر اساس همین آخرین نرخ‌های ذخیره‌شده‌اند.</p>`;
  setupMarketConverter();
  } catch (e) { el.innerHTML = `<div class="state"><div class="big">بازار بارگذاری نشد</div></div>`; }
}

function setupMarketConverter() {
  const units = window.JK_MARKET_UNITS || [], from = document.getElementById("mc-from"), to = document.getElementById("mc-to");
  if (!from || !to || !units.length) return;
  const opts = units.map(u => `<option value="${esc(u.id)}">${esc(u.label)}</option>`).join("");
  from.innerHTML = opts; to.innerHTML = opts;
  const usd = units.findIndex(u => u.label === "دلار آمریکا");
  from.selectedIndex = usd >= 0 ? usd : 0; to.selectedIndex = 0;
  convertMarketUnit();
}
function convertMarketUnit() {
  const units = window.JK_MARKET_UNITS || [], amount = Number(document.getElementById("mc-amount")?.value || 0);
  const from = units.find(u => u.id === document.getElementById("mc-from")?.value);
  const to = units.find(u => u.id === document.getElementById("mc-to")?.value);
  const out = document.getElementById("mc-result");
  if (!out || !from || !to || !Number.isFinite(amount) || !to.toman) return;
  const result = amount * from.toman / to.toman;
  const digits = result < 0.01 ? 8 : result < 1 ? 6 : result < 100 ? 4 : 2;
  out.innerHTML = `<b>${faN(amount.toLocaleString("en-US"))}</b> ${esc(from.label)} = <strong>${faN(result.toLocaleString("en-US",{maximumFractionDigits:digits}))}</strong> ${esc(to.label)}`;
}
function swapMarketUnits() {
  const a=document.getElementById("mc-from"), b=document.getElementById("mc-to"); if(!a||!b)return;
  const v=a.value; a.value=b.value; b.value=v; convertMarketUnit();
}

// weather — home strip (4 cities) + dedicated page
function showWeather() { show("weather"); setTab("feed"); renderWeather(); setHash("#/weather"); }
async function renderHomeWeather() {
  const el = document.getElementById("home-weather");
  if (!el) return;
  try {
    const w = await getJSON(`${DATA}/weather.json`);
    if (!w || !w.length) return;
    el.innerHTML = w.slice(0, 4).map(c => `<div class="hp"><span class="hp-label">${c.icon || ""} ${esc(c.city_fa)}</span>
      <span class="hp-val">${faN(c.temp)}°</span>
      <span class="hp-chg flat">${faN(c.min)}° / ${faN(c.max)}°</span></div>`).join("")
      + `<button class="hp-more" onclick="showWeather()">آب‌وهوا ›</button>`;
  } catch (e) {}
}
async function renderWeather() {
  const el = document.getElementById("weather");
  try {
    const w = await getJSON(`${DATA}/weather.json`);
    if (!w || !w.length) { el.innerHTML = `<div class="state"><div class="big">آب‌وهوا در دسترس نیست</div></div>`; return; }
    el.innerHTML = `<div class="wx-grid">` + w.map(c => `<div class="wx">
      <div class="wx-ic">${c.icon || "🌡️"}</div>
      <div class="wx-city">${esc(c.city_fa)}</div>
      <div class="wx-temp">${faN(c.temp)}°</div>
      <div class="wx-cond">${esc(c.cond_fa || "")}</div>
      <div class="wx-mm"><span class="wx-min">${faN(c.min)}°</span> / <span class="wx-max">${faN(c.max)}°</span></div></div>`).join("")
      + `</div><aside class="weather-expert"><div><span class="weather-expert-kicker">کارشناس مرتبط</span><strong>محمد اصغری</strong><p>پیش‌بینی، تحلیل سامانه‌های بارشی، هشدارهای جوی و هواشناسی کشاورزی</p></div><button onclick="openFigure(\'asghari_weatherman\')">صفحهٔ محمد اصغری ←</button></aside><p class="muted" style="margin-top:14px">منبع دادهٔ عددی: Open-Meteo — دمای کنونی و کمینه/بیشینهٔ امروز. هر ساعت به‌روز می‌شود. تحلیل‌های محمد اصغری به‌عنوان دیدگاه کارشناس، جدا از دادهٔ عددی نمایش داده می‌شوند.</p>`;
  } catch (e) { el.innerHTML = `<div class="state"><div class="big">آب‌وهوا بارگذاری نشد</div></div>`; }
}

/* ============================================================
   Charts (dependency-free inline SVG), follow store, and stats
   ============================================================ */

function _pts(vals, w, h, pad) {
  pad = pad == null ? 2 : pad;
  const n = vals.length; if (!n) return [];
  const mx = Math.max(...vals, 1), mn = Math.min(...vals, 0), rng = (mx - mn) || 1;
  return vals.map((v, i) => {
    const x = n === 1 ? w / 2 : pad + i * (w - 2 * pad) / (n - 1);
    const y = h - pad - ((v - mn) / rng) * (h - 2 * pad);
    return [x, y];
  });
}
// sparkline (area + line), scales to container width
function svgSpark(vals, o) {
  o = o || {}; const w = o.w || 120, h = o.h || 30;
  const p = _pts(vals, w, h, 2); if (!p.length) return "";
  const line = p.map(a => a[0].toFixed(1) + "," + a[1].toFixed(1)).join(" ");
  const area = p[0][0].toFixed(1) + "," + (h - 2) + " " + line + " " + p[p.length - 1][0].toFixed(1) + "," + (h - 2);
  const cls = o.cls || "a";
  return `<svg class="spark s-${cls}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><polygon class="sp-area" points="${area}"/><polyline class="sp-line" points="${line}"/></svg>`;
}
// vertical bars (activity)
function svgBars(vals, o) {
  o = o || {}; const w = o.w || 300, h = o.h || 64, n = vals.length, gap = o.gap || 2;
  const mx = Math.max(...vals, 1), bw = (w - gap * (n - 1)) / n;
  let r = "";
  for (let i = 0; i < n; i++) {
    const bh = Math.max(1.5, (vals[i] / mx) * (h - 2)), x = i * (bw + gap), y = h - bh;
    const lbl = (o.labels && o.labels[i]) ? esc(o.labels[i]) + " — " : "";
    // optional per-bar click handler + slight cursor hint via class="bar-click"
    const click = (o.onclick && o.onclick[i]) ? ` class="bar bar-click" onclick="${o.onclick[i]}"` : ' class="bar"';
    r += `<rect${click} x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="1.5"><title>${lbl}${faN(vals[i])} خبر</title></rect>`;
  }
  return `<svg class="bars-svg" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">${r}</svg>`;
}
// two-series comparison, each normalized to its own max (shape compare, one axis)
function svgCompare(a, b, o) {
  o = o || {}; const w = o.w || 260, h = o.h || 64;
  const norm = v => { const m = Math.max(...v, 1); return v.map(x => x / m * 100); };
  const mk = (vals, cls) => {
    const p = _pts(norm(vals), w, h, 3); if (!p.length) return "";
    return `<polyline class="cmp-line c-${cls}" points="${p.map(a => a[0].toFixed(1) + "," + a[1].toFixed(1)).join(" ")}"/>` +
      `<circle class="cmp-dot c-${cls}" cx="${p[p.length - 1][0].toFixed(1)}" cy="${p[p.length - 1][1].toFixed(1)}" r="2.6"/>`;
  };
  return `<svg class="cmp-svg" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">${mk(a, "a")}${b && b.length ? mk(b, "b") : ""}</svg>`;
}
function growthTag(g) {
  if (g == null) return "";
  if (g > 0) return `<span class="gtag up">▲ ${faN(g)}٪</span>`;
  if (g < 0) return `<span class="gtag down">▼ ${faN(Math.abs(g))}٪</span>`;
  return `<span class="gtag flat">—</span>`;
}
function trendBadge(t) {
  if (!t) return "";
  if (t.hot) return `<span class="tbadge hot">🔥 داغ</span>`;
  if (t.rising) return `<span class="tbadge rise">در حال رشد</span>`;
  return "";
}

/* ----- follow / saved store (per-device, localStorage) ----- */
const FKEY = "jk_follow_v1";
function loadF() { try { return JSON.parse(localStorage.getItem(FKEY)) || {}; } catch (e) { return {}; } }
function saveF() { try { localStorage.setItem(FKEY, JSON.stringify(FOLLOW)); } catch (e) {} }
let FOLLOW = Object.assign({ topics: [], provinces: [], sources: [], entities: [], saved: [] }, loadF());
function isF(kind, id) { return (FOLLOW[kind] || []).includes(id); }
function toggleF(kind, id) {
  const a = FOLLOW[kind] || (FOLLOW[kind] = []);
  const i = a.indexOf(id); if (i >= 0) a.splice(i, 1); else a.push(id);
  saveF();
}
function followCount() {
  return (FOLLOW.topics.length + FOLLOW.provinces.length + FOLLOW.sources.length
    + (FOLLOW.entities ? FOLLOW.entities.length : 0));
}
// a reusable follow/save button
function followBtn(kind, id, labelOn, labelOff) {
  const on = isF(kind, id);
  return `<button class="follow-btn ${on ? "on" : ""}" onclick="event.stopPropagation();hitFollow('${kind}','${String(id).replace(/'/g, "\\'")}',this)">
    <svg viewBox="0 0 24 24" fill="${on ? "currentColor" : "none"}" stroke="currentColor" stroke-width="1.8"><path d="M12 17.3l-6.2 3.7 1.6-7L2 9.2l7.1-.6L12 2l2.9 6.6 7.1.6-5.4 4.8 1.6 7z" stroke-linejoin="round"/></svg>
    <span class="fb-t">${on ? (labelOn || "دنبال می‌کنی") : (labelOff || "دنبال کن")}</span></button>`;
}
function hitFollow(kind, id, btn) {
  toggleF(kind, id);
  const on = isF(kind, id);
  btn.classList.toggle("on", on);
  const t = btn.querySelector(".fb-t"); if (t) t.textContent = on ? "دنبال می‌کنی" : "دنبال کن";
  const svg = btn.querySelector("svg"); if (svg) svg.setAttribute("fill", on ? "currentColor" : "none");
  updateMineBadge();
}
function saveBtn(id) {
  const on = isF("saved", id);
  return `<button class="save-btn ${on ? "on" : ""}" title="ذخیره" aria-label="ذخیره" onclick="event.stopPropagation();hitSave('${id}',this)">
    <svg viewBox="0 0 24 24" fill="${on ? "currentColor" : "none"}" stroke="currentColor" stroke-width="1.8"><path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1Z" stroke-linejoin="round"/></svg></button>`;
}
function hitSave(id, btn) {
  toggleF("saved", id);
  const on = isF("saved", id);
  btn.classList.toggle("on", on);
  const svg = btn.querySelector("svg"); if (svg) svg.setAttribute("fill", on ? "currentColor" : "none");
  updateMineBadge();
}
function updateMineBadge() {
  const b = document.getElementById("mine-badge");
  if (!b) return;
  const n = followCount() + (FOLLOW.saved ? FOLLOW.saved.length : 0);
  b.textContent = n ? faN(n) : "";
  b.style.display = n ? "inline-flex" : "none";
}

/* ----- personalized feed ("خط خبری من") ----- */
function mineFeed() {
  return ALL.filter(s =>
    (s.topics || []).some(t => isF("topics", t.slug)) ||
    (s.geo && (s.geo.provinces || []).some(p => isF("provinces", p.slug))) ||
    (s.source_names || []).some(n => isF("sources", n)) ||
    (s.entities || []).some(e => isF("entities", e.slug)) ||
    isF("saved", s.id));
}

/* ----- home stats strip ("نبض خبری") ----- */
async function renderHomeStats() {
  const el = document.getElementById("home-stats");
  if (!el) return;
  try {
    const [st, figs] = await Promise.all([
      getJSON(`${DATA}/stats.json`),
      getJSON(`${DATA}/figures.json`).catch(() => ({ figures: [] }))
    ]);
    STATS = st;
    const roll = liveRolling(st);
    const people = (figs.figures || []);
    const allPosts = people.flatMap(f => (f.posts || []).map(p => ({...p, _person:f})));
    const now = Date.now(), countPosts = h => allPosts.filter(p => p.published_at && new Date(p.published_at).getTime() >= now-h*3600e3).length;
    const activePeople = h => new Set(allPosts.filter(p => p.published_at && new Date(p.published_at).getTime() >= now-h*3600e3).map(p => p._person.handle || p._person.name_fa)).size;
    const opinionCount = allPosts.length;
    const daily = (st.activity_daily || []).map(x => x.n);
    const figDaily = Array.from({length:7},(_,i)=>{
      const a=now-(6-i)*86400e3, b=a+86400e3;
      return allPosts.filter(p=>{const t=p.published_at?new Date(p.published_at).getTime():0;return t>=a&&t<b}).length;
    });
    const today = utcDayISO(0), yday = utcDayISO(-1);
    el.innerHTML = `<div class="statbar statbar-rich">
      <div class="sb-metrics">
        <span class="sb-item sb-click" onclick="showTrends()"><b>${faN(st.total || 0)}</b><span>کل خبرها</span></span>
        <span class="sb-sep"></span>
        <span class="sb-item sb-click" onclick="showFigures()"><b>${faN(people.length)}</b><span>چهره‌ها</span></span>
        <span class="sb-sep"></span>
        <span class="sb-item sb-click sb-opinions" onclick="showFigures()"><b>${faN(opinionCount)}</b><span>کل اظهارنظرها</span></span>
        <span class="sb-sep"></span>
        <span class="sb-item sb-click" onclick="showFigures()"><b>${faN(countPosts(24))}</b><span>نظر · ۲۴ساعت</span></span>
        <span class="sb-item sb-click" onclick="showFigures()"><b>${faN(activePeople(24))}</b><span>چهرهٔ فعال · ۲۴ساعت</span></span>
        <span class="sb-sep"></span>
        <span class="sb-item sb-click" onclick="openDay('${today}')"><b>${faN(st.calendar ? st.calendar.today : 0)}</b><span>خبر امروز ›</span></span>
        <span class="sb-item sb-click" onclick="showTrends()"><b>${faN(roll.h24)}</b><span>خبر · ۲۴ساعت</span></span>
      </div>
      <div class="sb-charts">
        <div class="sb-mini sb-click" onclick="showTrends()"><span>خبر · ۱۴ روز</span>${svgSpark(daily, { w: 150, h: 34 })}</div>
        <div class="sb-mini sb-click" onclick="showFigures()"><span>اظهارنظر · ۷ روز</span>${svgSpark(figDaily, { w: 120, h: 34, cls:"b" })}</div>
      </div>
    </div>`;
  } catch (e) {}
}
let STATS = null;
// recompute rolling windows live from the timeline so 4h/8h/12h stay fresh
function liveRolling(st) {
  const tl = (st && st.timeline) || [];
  const now = Date.now();
  const c = h => tl.filter(ms => ms >= now - h * 3600e3).length;
  return { h4: c(4), h8: c(8), h12: c(12), h24: c(24) };
}
function statsBlock(st) {
  const roll = liveRolling(st), cal = st.calendar || {};
  const daily = (st.activity_daily || []);
  const today = utcDayISO(0), yday = utcDayISO(-1);
  // rolling windows (not tied to a single day) are non-clickable; day tiles link.
  const tiles = [
    ["۴ ساعت", roll.h4, null], ["۸ ساعت", roll.h8, null],
    ["۱۲ ساعت", roll.h12, null], ["۲۴ ساعت", roll.h24, null],
    ["امروز ›", cal.today || 0, today], ["دیروز ›", cal.yesterday || 0, yday],
    ["این هفته", cal.this_week || 0, null], ["هفتهٔ پیش", cal.last_week || 0, null],
  ];
  const labels = daily.map(d => d.d.slice(5));
  // bars: each day-bar becomes a button that jumps to that day's archive
  const barsSvg = svgBars(daily.map(d => d.n), {
    labels, w: 320, h: 70,
    onclick: daily.map(d => `openDay('${d.d}')`),
  });
  return `
    <div class="stat-hero"><span class="val">${faN(st.total || 0)}</span><span class="lbl">کل خبرهای سیستم</span></div>
    <div class="stat-tiles">${tiles.map(t => {
      const cls = t[2] ? "stile stile-click" : "stile";
      const onc = t[2] ? ` onclick="openDay('${t[2]}')"` : "";
      return `<div class="${cls}"${onc}><b>${faN(t[1])}</b><span>${t[0]}</span></div>`;
    }).join("")}</div>
    <div class="rule"><span>فعالیتِ ۱۴ روزِ گذشته <span class="n">— روی هر روز بزن</span></span><span class="l"></span></div>
    <div class="chart-wrap">${barsSvg}</div>
    <p class="muted" style="margin:6px 0 4px">شمارِ خبرهای تازه در هر روز. روی «امروز/دیروز» یا هر میله بزن تا خبرهای همان روز را با تفکیک دسته ببینی.</p>`;
}

loadFeed().then(route);   // load the feed, then honor any deep link in the URL
renderHomeStats();
renderHomeGlance();
renderHomeMajra();
renderHomePrices();
renderHomeWeather();
updateMineBadge();


/* ---- جان‌کلام چهره‌ها — commentators' views, kept apart from the facts ----
   Data: story.figures (matched per story) + data/figures.json (all figures).
   A view is always attributed to its author and linked to the original post. */
const KIND_NOTE = { party_claim: "ادعای یکی از طرفین" };
const SOCIAL_ICON = {
  telegram: '<path d="M21.5 4.5 2.5 11.8l5 1.6 1.9 5.6 2.7-3 4.5 3.3z" stroke-linejoin="round"/>',
  bale: '<rect x="4" y="4" width="16" height="16" rx="5"/><path d="M8 8h5a3 3 0 0 1 0 6H8zm0 6h6a3 3 0 0 1 0 6" stroke-linejoin="round"/>',
  x: '<path d="M4 4l16 16M20 4L4 20" stroke-linecap="round"/>',
  instagram: '<rect x="4" y="4" width="16" height="16" rx="4.5"/><circle cx="12" cy="12" r="3.4"/><circle cx="17" cy="7" r="1" fill="currentColor" stroke="none"/>',
  youtube: '<rect x="3" y="6" width="18" height="12" rx="3.5"/><path d="M11 9.5l4 2.5-4 2.5z" fill="currentColor" stroke="none"/>',
  facebook: '<path d="M14 8h2V5h-2a3 3 0 0 0-3 3v2H9v3h2v6h3v-6h2.2l.4-3H14V8.5a.5.5 0 0 1 .5-.5z" stroke-linejoin="round"/>',
  website: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.5 3.5 6 3.5 9S14.5 18.5 12 21c-2.5-2.5-3.5-6-3.5-9S9.5 5.5 12 3z"/>',
  truthsocial: '<path d="M6 5h12M12 5v14M7.5 10.5h9" stroke-linecap="round"/><circle cx="12" cy="12" r="9"/>',
};
function avatar(p, cls) {
  if (p.avatar) return `<img class="fig-avatar ${cls || ""}" src="${esc(p.avatar)}" alt="" loading="lazy" onerror="this.classList.add('broken')">`;
  const ini = (p.name_fa || "?").trim().charAt(0);
  return `<span class="fig-avatar ${cls || ""} ini">${esc(ini)}</span>`;
}
function socialLinks(links) {
  if (!links || !links.length) return "";
  return `<div class="fig-social">${links.map(l => `<a href="${esc(l.url)}" target="_blank" rel="noopener" title="${esc(l.label)}" aria-label="${esc(l.label)}">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">${SOCIAL_ICON[l.kind] || SOCIAL_ICON.website}</svg><span>${esc(l.label)}</span></a>`).join("")}</div>`;
}
(function () {
  const st = document.createElement("style");
  st.textContent = `.figure-timeline{display:flex;flex-direction:column;gap:12px;margin:8px 0 24px}
.home-fig-card{padding:16px 18px;border:1px solid rgba(143,168,155,.22);border-radius:14px;background:rgba(26,157,126,.035)}
.home-fig-card:hover{border-color:rgba(26,157,126,.5)}
.home-fig-topic{font-size:17px;line-height:1.6;margin:10px 0 3px}
.home-fig-card .kalam{margin:0 0 10px;line-height:1.9}
.home-fig-card .fig-foot{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.fig-profile-link{border:0;background:none;padding:0;color:#1a9d7e;font:inherit;cursor:pointer}
.fig-profile-link:hover{text-decoration:underline}
.fig-tl-controls{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin:0 0 12px}
.fig-tl-controls .imp-filter{margin:0}
.fig-field-select{font:inherit;color:inherit;background:transparent;border:1px solid rgba(143,168,155,.35);border-radius:999px;padding:6px 12px}
.fig-follow{font:inherit;font-size:12px;border:1px solid rgba(143,168,155,.35);border-radius:999px;background:transparent;color:#8fa89b;padding:4px 9px;cursor:pointer;white-space:nowrap}
.fig-follow.on{color:#e0b341;border-color:rgba(224,179,65,.5);background:rgba(224,179,65,.08)}
.fig-follow.compact{font-size:11px;padding:3px 7px}
.news-statement-tag{display:inline-block;margin:9px 0 0;font-size:12px;color:#8fa89b;background:rgba(143,168,155,.10);border-radius:999px;padding:3px 9px}
.fig-source-stats{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:7px 0 10px;font-size:13px;color:#8fa89b}
.fig-source-stats b{color:var(--text)}
.fig-profile-filters{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 16px}
@media(max-width:600px){.home-fig-card{padding:14px}.home-fig-card .v-h{align-items:flex-start}.home-fig-card .muted{font-size:11px}}`;
  document.head.appendChild(st);
})();

function statementKey(p) { return encodeURIComponent(String(p.id || "")); }
function figureCard(p, withName) {
  const party = p.kind === "party_claim"
    ? `<span class="cstatus st-warn" title="این شخص خودش طرفِ این ماجراست">${KIND_NOTE.party_claim}</span>` : "";
  const head = withName
    ? `<div class="v-h">${avatar(p, "sm")}<div class="fig-id"><a class="v-name" href="#/figure/${esc(p.handle)}" onclick="event.preventDefault();${p._newsPerson ? "openNewsPerson" : "openFigure"}('${esc(p.handle)}')">${esc(p.name_fa)}</a><span class="fig-role">${esc(p.role_fa)}</span></div><span class="spacer" style="flex:1"></span>${party}</div>`
    : `<div class="v-h"><span class="fig-topic">${esc(p.topic_fa || "")}</span><span class="spacer" style="flex:1"></span>${party}</div>`;
  return `<div class="view fig-view">${head}
    <p>${esc(p.summary_fa || "")}</p>
    <div class="fig-foot"><button class="fig-profile-link" onclick="openStatement(\'${statementKey(p)}\')">صفحهٔ این گفته</button><span class="muted">${relTime(p.published_at)}${p.source_language && p.source_language !== "fa" ? " · " + esc(p.translation_label_fa || ("ترجمه از " + p.source_language)) : ""}</span>
      <a href="${esc(p.url)}" target="_blank" rel="noopener">${p.kind === "news_statement" ? "منبع این گفته" : p.platform === "truthsocial" ? "پست اصلی در تروث سوشیال" : "متن کامل در " + (String(p.url || "").includes("ble.ir/") ? "بله" : "تلگرام")} ↗</a></div></div>`;
}
const FIG_FOLLOW_KEY = "jankalam-figure-follows";
let _figTimelineMode = "all";
let _figTimelineField = "all";
function figureFollows() {
  try { return new Set(JSON.parse(localStorage.getItem(FIG_FOLLOW_KEY) || "[]")); }
  catch (e) { return new Set(); }
}
function isFigureFollowed(handle) { return figureFollows().has(String(handle).toLowerCase()); }
function toggleFigureFollow(handle, ev) {
  if (ev) { ev.preventDefault(); ev.stopPropagation(); }
  const key = String(handle).toLowerCase(), s = figureFollows();
  s.has(key) ? s.delete(key) : s.add(key);
  localStorage.setItem(FIG_FOLLOW_KEY, JSON.stringify([...s]));
  renderFigureTimeline();
  if (document.getElementById("figures-view").style.display === "block" && location.hash.startsWith("#/figure/")) openFigure(handle);
}
function figureFollowBtn(handle, compact) {
  const on = isFigureFollowed(handle);
  return `<button class="fig-follow ${on ? "on" : ""} ${compact ? "compact" : ""}" onclick="toggleFigureFollow('${esc(handle)}',event)" aria-label="${on ? "دنبال نکردن" : "دنبال کردن"}">${on ? "★ دنبال می‌کنم" : "☆ دنبال کن"}</button>`;
}
function setFigureTimelineMode(mode) { _figTimelineMode = mode; renderFigureTimeline(); }
function setFigureTimelineField(field) { _figTimelineField = field; renderFigureTimeline(); }
async function renderFigureTimeline() {
  const el = document.getElementById("figure-timeline");
  if (!el) return;
  const d = await loadFigures();
  const isNewsMode = _figTimelineMode === "news";
  const fields = d.fields || {};
  let posts = (d.figures || []).flatMap(f => (f.posts || []).map(p => ({
    ...p, field: f.field,
    name_fa: p.name_fa || f.name_fa,
    role_fa: p.role_fa || f.role_fa,
    field_fa: f.field_fa || fields[f.field] || "",
    avatar: p.avatar || f.avatar,
    _newsPerson: isNewsMode
  }))).sort((a, b) => String(b.published_at || "").localeCompare(String(a.published_at || "")));
  const follows = figureFollows();
  if (isNewsMode) posts = posts.filter(p => p.kind === "news_statement");
  if (_figTimelineMode === "following") posts = posts.filter(p => follows.has(String(p.handle).toLowerCase()));
  if (_figTimelineField !== "all" && !isNewsMode) posts = posts.filter(p => p.field === _figTimelineField);
  // Self-heal stale/removed field values left behind by an older deployment.
  // This also protects deep links after the exported field taxonomy changes.
  if (!posts.length && _figTimelineMode === "all" && _figTimelineField !== "all") {
    _figTimelineField = "all";
    posts = (d.figures || []).flatMap(f => (f.posts || []).map(p => ({
      ...p, field: f.field,
      name_fa: p.name_fa || f.name_fa,
      role_fa: p.role_fa || f.role_fa,
      field_fa: f.field_fa || fields[f.field] || "",
      avatar: p.avatar || f.avatar,
      _newsPerson: false
    }))).sort((a,b) => String(b.published_at || "").localeCompare(String(a.published_at || "")));
  }
  const controls = `<div class="fig-tl-controls">
    <div class="imp-filter">
      <button class="fchip ${_figTimelineMode === "all" ? "on" : ""}" onclick="setFigureTimelineMode('all')">همه</button>
      <button class="fchip ${_figTimelineMode === "following" ? "on" : ""}" onclick="setFigureTimelineMode('following')">★ دنبال‌شده‌ها ${follows.size ? '<span class="chip-n">'+faN(follows.size)+'</span>' : ""}</button>
      ${(d.figures || []).some(f => (f.posts || []).some(p => p.kind === "news_statement")) ? `<button class="fchip ${_figTimelineMode === "news" ? "on" : ""}" onclick="setFigureTimelineMode('news')">چهره‌های خبر</button>` : ""}
    </div>
    <select class="fig-field-select" onchange="setFigureTimelineField(this.value)" aria-label="فیلتر حوزه" ${isNewsMode ? "disabled" : ""}>
      <option value="all">همهٔ حوزه‌ها</option>
      ${Object.entries(fields).map(([k,v]) => `<option value="${esc(k)}" ${_figTimelineField===k?"selected":""}>${esc(v)}</option>`).join("")}
    </select>
  </div>`;
  if (!posts.length) {
    const msg = _figTimelineMode === "following" && !follows.size
      ? "هنوز هیچ چهره‌ای را دنبال نکرده‌ای — روی ☆ کنار نام افراد بزن."
      : "در این فیلتر دیدگاه تازه‌ای نیست.";
    el.innerHTML = controls + `<div class="state"><div class="big">${msg}</div></div>`;
    return;
  }
  el.innerHTML = controls + `<div class="x-figure-stream">` + posts.slice(0, 40).map(p => `<article class="x-figure-post">
    <div class="x-figure-avatar">${avatar(p, "sm")}</div>
    <div class="x-figure-content">
      <div class="x-figure-head">
        <div class="x-figure-identity"><a class="x-figure-name" href="#/figure/${esc(p.handle)}" onclick="event.preventDefault();${p._newsPerson ? "openNewsPerson" : "openFigure"}('${esc(p.handle)}')">${esc(p.name_fa)}</a><span class="x-figure-role">${esc(p.role_fa || p.field_fa || "")}</span><span class="x-figure-dot">·</span><time>${relTime(p.published_at)}</time></div>
        ${figureFollowBtn(p.handle,true)}
      </div>
      ${p.kind === "news_statement" ? `<div class="x-figure-context">گفته در خبر · ${esc(p.source_name || "منبع خبری")}</div>` : ""}
      ${p.topic_fa ? `<h2 class="x-figure-topic">${esc(p.topic_fa)}</h2>` : ""}
      <p class="x-figure-text">${esc(p.summary_fa || "")}</p>
      ${telegramEmbed(p)}
      <div class="x-figure-actions">
        <button onclick="${p._newsPerson ? "openNewsPerson" : "openFigure"}('${esc(p.handle)}')">◯ <span>پروفایل</span></button>
        <button onclick="openStatement('${statementKey(p)}')">▢ <span>صفحهٔ گفته</span></button>
        <a href="${esc(p.url)}" target="_blank" rel="noopener">↗ <span>متن اصلی</span></a>
      </div>
    </div>
  </article>`).join("") + `</div>`;
}

function figuresSection(list) {
  if (!list || !list.length) return "";
  return `<div class="layers"><h3 class="section-h">چهره‌ها چه می‌گویند <span class="n">دیدگاه شخصی — نه واقعیتِ خبر</span></h3>
    <div class="views">${list.map(p => figureCard(p, true)).join("")}</div>
    <p class="muted fig-note">دیدگاه‌های مستقیم از کانال‌های عمومی خود افراد و «گفته در خبر» از منابع خبری جدا برچسب می‌خورند؛ لینک هر مورد به منبع همان گفته می‌رود.
      <a href="#/figures" onclick="event.preventDefault();showFigures()">همهٔ چهره‌ها</a></p></div>`;
}
let _FIG = null, _NEWS_PEOPLE = null, _CURATED_POEMS = null, _figDirectoryMode = "direct";
async function loadCuratedPoems(){ if(_CURATED_POEMS) return _CURATED_POEMS; try{_CURATED_POEMS=await getJSON(`${DATA}/curated-figure-poems.json`);}catch(_){_CURATED_POEMS={};} return _CURATED_POEMS||{}; }
async function loadFigures() {
  if (_FIG) return _FIG;
  try { _FIG = await getJSON(`${DATA}/figures.json`); } catch (e) { _FIG = { figures: [], fields: {} }; }
  return _FIG;
}
async function loadNewsPeople() {
  if (_NEWS_PEOPLE) return _NEWS_PEOPLE;
  try { _NEWS_PEOPLE = await getJSON(`${DATA}/news-people.json`); } catch (e) { _NEWS_PEOPLE = { figures: [], fields: {} }; }
  return _NEWS_PEOPLE;
}
function setFigureDirectoryMode(mode) {
  _figDirectoryMode = mode;
  renderFigures();
}
function showTech() {
  show("tech"); setTab(""); setHash("#/tech");
  const el = document.getElementById("tech-content");
  el.innerHTML = `
    <div class="tech-grid">
      <article class="tech-card"><h2>رابط فارسی و RTL</h2><p>کامپوننت‌های رابط با الگوهای بومیِ راست‌چین طراحی شده‌اند؛ کارت، آمار، آواتار، تب‌ها، نشان‌ها، خط زمان، حالت خالی و بارگذاری.</p><div class="tech-tags"><span class="tech-tag">Card</span><span class="tech-tag">Stat</span><span class="tech-tag">Avatar</span><span class="tech-tag">Tabs</span><span class="tech-tag">Badge</span></div></article>
      <article class="tech-card"><h2>VibeFarsi UI</h2><p>برای زبان بصری و رفتار کامپوننت‌های فارسی از VibeFarsi الهام گرفته‌ایم. جان‌کلام فعلاً پروژهٔ React/Tailwind نیست؛ بنابراین الگوها در CSS/JavaScript موجود بازپیاده‌سازی شده‌اند و خود کتابخانه dependency اجرایی سایت نیست.</p><div class="tech-tags"><a class="tech-tag" href="https://vibefarsi.ir/" target="_blank" rel="noopener">vibefarsi.ir ↗</a></div></article>
      <article class="tech-card"><h2>خبر و تحلیل</h2><p>Backend پایتون خبرها را دریافت، خوشه‌بندی، رتبه‌بندی و برای خروجی استاتیک آماده می‌کند. واقعیت خبر، تحلیل رسانه و دیدگاه اشخاص در لایه‌های جدا نگهداری می‌شوند.</p><div class="tech-tags"><span class="tech-tag">Python</span><span class="tech-tag">SQLAlchemy</span><span class="tech-tag">JSON</span></div></article>
      <article class="tech-card"><h2>انتشار استاتیک</h2><p>خروجی نهایی HTML/CSS/JavaScript است و با GitHub Actions ساخته و روی GitHub Pages منتشر می‌شود؛ بنابراین خواندن سایت به سرور اپلیکیشن دائمی وابسته نیست.</p><div class="tech-tags"><span class="tech-tag">GitHub Actions</span><span class="tech-tag">GitHub Pages</span><span class="tech-tag">PWA</span></div></article>
    </div>
    <div class="rule"><span>نقشهٔ فناوری</span><span class="l"></span></div>
    <div class="tech-stack">
      <div class="tech-row"><b>جمع‌آوری</b><span>منابع خبری، منابع عمومی چهره‌ها و داده‌های مکمل</span></div>
      <div class="tech-row"><b>پردازش</b><span>Python · خوشه‌بندی خبر · استخراج گفته‌ها · رتبه‌بندی و synthesis</span></div>
      <div class="tech-row"><b>داده</b><span>SQLAlchemy و خروجی‌های JSON برای رابط استاتیک</span></div>
      <div class="tech-row"><b>رابط</b><span>HTML + Vanilla JavaScript + CSS؛ فارسی و RTL از ابتدا</span></div>
      <div class="tech-row"><b>طراحی</b><span>Design tokens داخلی جان‌کلام + الگوهای سازگارشده از VibeFarsi UI</span></div>
      <div class="tech-row"><b>انتشار</b><span>GitHub Actions → GitHub Pages</span></div>
    </div>
    <div class="rule"><span>VibeFarsi کجا اثر گذاشته؟</span><span class="l"></span></div>
    <div class="tech-card"><p>در بازطراحی تدریجی جان‌کلام، الگوهای Card و Stat برای خلاصه‌ها و اعداد، Avatar برای چهره‌ها، Segmented Control/Tabs برای فیلترها، Badge برای وضعیت‌ها، Timeline برای زنجیرهٔ رویداد و Skeleton/Empty State برای وضعیت‌های بارگذاری و نبود داده مبنا قرار می‌گیرند. این تطبیق مرحله‌ای است تا معماری سبک فعلی حفظ شود.</p></div>
  `;
}
function showFigures() {
  show("figures"); setTab("");
  document.getElementById("figures-lede").style.display = "";
  document.getElementById("figures").innerHTML = "";
  // A previous visit can leave timeline filters in local page state.  The
  // /figures route itself must always open on a useful default instead of an
  // apparently broken empty filtered view.
  _figTimelineMode = "all";
  _figTimelineField = "all";
  renderFigureTimeline();
  setHash("#/figures");
}
function renderFiguresDirectory() {
  document.getElementById("figure-timeline").innerHTML = "";
  _figDirectoryMode = "direct";
  renderFigures();
}
async function renderFigures() {
  document.getElementById("figures-lede").style.display = "";
  const el = document.getElementById("figures");
  el.innerHTML = `<div class="spinner"></div>`;
  const d = await loadFigures();
  const people = (d.figures || []).filter(x => x.directory !== false)
    .sort((a,b) => (b.count||0)-(a.count||0) || String(a.name_fa||"").localeCompare(String(b.name_fa||""),"fa"));
  el.innerHTML = `<p class="muted">چهره‌ها در یک فهرست واحد؛ دیدگاه‌های مستقیم و گفته‌های منتسب در خبرها داخل همان پروفایل جمع می‌شوند.</p>` +
    (people.length ? `<div class="fig-grid">${people.map(x => `<button class="fig-person" onclick="openFigure('${esc(x.handle)}')">
      ${avatar(x, "md")}
      <span class="fp-body"><span class="fp-name">${esc(x.name_fa)}</span><span class="fp-role">${esc(x.role_fa||"")}</span>
      <span class="fp-count">${faN(x.count||0)} گفته</span></span></button>`).join("")}</div>`
    : `<div class="state"><div class="big">هنوز شخصی ثبت نشده</div></div>`);
}
async function openNewsPerson(handle) { return openFigure(handle); }
async function openFigureByName(name) {
  const d = await loadFigures();
  const norm = s => String(s || "").replace(/‌/g, " ").replace(/\s+/g, " ").trim();
  const x = (d.figures || []).find(f => norm(f.name_fa) === norm(name));
  if (x) return openFigure(x.handle);
}
let _figureProfileFilter = "all";
function setFigureProfileFilter(handle, mode) {
  _figureProfileFilter = mode;
  openFigure(handle, false);
}
async function openStatement(id) {
  const raw = decodeURIComponent(id);
  const direct = await loadFigures();
  let person = null, post = null, isNews = false;
  for (const f of (direct.figures || [])) {
    const p = (f.posts || []).find(x => String(x.id) === raw);
    if (p) { person = f; post = p; break; }
  }
  if (post) isNews = post.kind === "news_statement";
  show("figures"); setTab("");
  document.getElementById("figures-lede").style.display = "none";
  document.getElementById("figure-timeline").innerHTML = "";
  const el = document.getElementById("figures");
  if (!post) { el.innerHTML = '<div class="state"><div class="big">این گفته پیدا نشد</div></div>'; return; }
  setHash("#/statement/" + encodeURIComponent(raw));
  el.innerHTML = '<button class="back" onclick="' + (isNews ? "openNewsPerson" : "openFigure") + "(\'" + esc(person.handle) + "\')\">بازگشت به پروفایل</button>" +
    '<div class="fig-head">' + avatar(person,"lg") + '<div class="fig-head-body"><h1>' + esc(person.name_fa) + '</h1><p class="muted">' + esc(person.role_fa||"") + '</p></div></div>' +
    '<div class="rule"><span>' + (isNews ? "گفته در خبر" : "دیدگاه") + '</span><span class="l"></span></div>' +
    figureCard(post,false) +
    ((post.related_people || []).length ? '<div class="rule"><span>ارتباط این گفته</span><span class="l"></span></div><div class="views">' +
      post.related_people.map(r => `<button class="fig-person" onclick="openFigure('${esc(r.handle)}')"><span class="fp-body"><span class="fp-name">${esc(r.name_fa)}</span><span class="fp-role">${r.relation === "response" ? "پاسخ / واکنش مرتبط" : "شخص نام‌برده در این گفته"}</span></span></button>`).join("") + '</div>' : '') +
    '<p class="muted fig-note">این صفحه نشانی مستقل دارد و می‌توان مستقیماً به همین گفته ارجاع داد.</p>';
}
function telegramEmbed(post) {
  if (!post || !post.telegram_media || !String(post.url || "").startsWith("https://t.me/")) return "";
  const m = String(post.url).match(/^https:\/\/t\.me\/([^/?#]+)\/(\d+)/);
  if (!m) return "";
  const src = `https://t.me/${encodeURIComponent(m[1])}/${m[2]}?embed=1&mode=tme`;
  return `<div class="telegram-embed telegram-embed-${esc(post.telegram_media)}"><iframe src="${src}" loading="lazy" frameborder="0" scrolling="no" allow="autoplay; encrypted-media; picture-in-picture" title="رسانهٔ پست تلگرام"></iframe></div>`;
}

async function openFigure(handle, resetFilter = true) {
  if (resetFilter) _figureProfileFilter = "all";
  setHash("#/figure/" + handle);
  show("figures"); setTab("");
  document.getElementById("figures-lede").style.display = "none";
  document.getElementById("figure-timeline").innerHTML = "";
  const el = document.getElementById("figures");
  el.innerHTML = `<div class="spinner"></div>`;
  const [d, curatedPoems] = await Promise.all([loadFigures(), loadCuratedPoems()]);
  const x = (d.figures || []).find(f => f.handle.toLowerCase() === String(handle).toLowerCase());
  if (!x) { el.innerHTML = `<div class="state"><div class="big">این چهره پیدا نشد</div></div>`; return; }
  const direct = (x.posts || []).filter(p => p.kind !== "news_statement");
  const news = (x.posts || []).filter(p => p.kind === "news_statement");
  const shown = _figureProfileFilter === "direct" ? direct : _figureProfileFilter === "news" ? news : _figureProfileFilter === "works" ? [] : (x.posts || []);
  const latest = (x.posts || []).map(p => p.published_at).filter(Boolean).sort().pop();
  const poems = Array.isArray(curatedPoems[x.handle]) ? curatedPoems[x.handle] : [];
  const poemSection = poems.length ? `<section class="curated-poems"><div class="curated-poems-head"><div><span class="curated-kicker">گزیدهٔ ویژه</span><h2>شعرها</h2><p>متن‌های ارسالی، با حفظ سطر‌بندی شعر</p></div><span class="curated-count">${faN(poems.length)} قطعه</span></div><div class="curated-poem-list">${poems.map((p,i)=>`<article class="curated-poem"><div class="curated-poem-no">${faN(i+1)}</div><div class="curated-poem-text">${esc(p.text||"").replace(/\\n/g,"<br>")}</div></article>`).join("")}</div></section>` : "";
  const postRow = p => `<article class="x-post">
    <div class="x-post-rail">${avatar(x,"sm")}</div>
    <div class="x-post-body">
      <div class="x-post-meta"><b>${esc(x.name_fa)}</b><span>·</span><time>${relTime(p.published_at)}</time></div>
      ${p.kind === "news_statement" ? `<div class="x-post-context">گفته در خبر · ${esc(p.source_name || "منبع خبری")}</div>` : (p.topic_fa ? `<div class="x-post-topic">${esc(p.topic_fa)}</div>` : "")}
      <p>${esc(p.summary_fa || "")}</p>
      ${telegramEmbed(p)}
      <div class="x-post-actions">
        <button onclick="openStatement(' ${statementKey(p)}'.trim())" title="صفحهٔ این گفته">◯ <span>صفحهٔ گفته</span></button>
        <a href="${esc(p.url)}" target="_blank" rel="noopener" title="متن اصلی">↗ <span>متن اصلی</span></a>
      </div>
    </div>
  </article>`;
  el.innerHTML = `<div class="x-profile">
    <div class="x-profile-top"><button class="x-back" onclick="showFigures()" aria-label="بازگشت">←</button><div><b>${esc(x.name_fa)}</b><small>${faN((x.posts||[]).length)} گفته</small></div></div>
    <div class="x-cover"></div>
    <div class="x-profile-main">
      <div class="x-avatar-wrap">${avatar(x,"lg")}</div>
      <div class="x-profile-actions">${figureFollowBtn(x.handle,false)}</div>
      <h1>${esc(x.name_fa)}</h1>
      <div class="x-handle">@${esc(x.handle)}</div>
      <p class="x-bio">${esc(x.role_fa || "")}</p>
      ${socialLinks(x.social)}
      <div class="x-profile-stats"><span><b>${faN(direct.length)}</b> دیدگاه مستقیم</span><span><b>${faN(news.length)}</b> گفته در خبر</span>${latest ? `<span>آخرین فعالیت ${relTime(latest)}</span>` : ""}</div>
    </div>
    <nav class="x-profile-tabs" aria-label="بخش‌های پروفایل">
      <button class="${_figureProfileFilter==="all"?"on":""}" onclick="setFigureProfileFilter('${esc(x.handle)}','all')">همه</button>
      <button class="${_figureProfileFilter==="direct"?"on":""}" onclick="setFigureProfileFilter('${esc(x.handle)}','direct')">دیدگاه‌ها</button>
      <button class="${_figureProfileFilter==="news"?"on":""}" onclick="setFigureProfileFilter('${esc(x.handle)}','news')">در خبرها</button>
      ${poems.length ? `<button class="${_figureProfileFilter==="works"?"on":""}" onclick="setFigureProfileFilter(\'${esc(x.handle)}\',\'works\')">آثار</button>` : ""}
    </nav>
    ${_figureProfileFilter==="works" ? poemSection : ""}\n    <div class="x-profile-feed" ${_figureProfileFilter==="works" ? 'style="display:none"' : ""}>${shown.length ? shown.map(postRow).join("") : '<div class="state"><div class="big">در این بخش موردی ثبت نشده.</div></div>'}</div>
    <p class="muted fig-note x-profile-note">دیدگاه‌ها از منابع عمومی خود شخص می‌آیند؛ موارد «در خبرها» گفته‌هایی هستند که رسانه‌ها به او نسبت داده‌اند.</p>
  </div>`;
}
