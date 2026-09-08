/* جان‌کلام — static build. Reads pre-generated JSON from ./data (no backend). */
const DATA = "data";

const CAT_FA = { iran: "ایران", world: "جهان", politics: "سیاست", economy: "اقتصاد",
  technology: "فناوری", ai: "هوش مصنوعی", culture: "فرهنگ", sport: "ورزش", science: "علم" };
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
  const h = Math.floor((Date.now() - new Date(iso)) / 3.6e6);
  if (h < 1) return "همین حالا";
  if (h < 24) return faN(h) + " ساعت پیش";
  const d = Math.floor(h / 24);
  return d === 1 ? "دیروز" : faN(d) + " روز پیش";
}
async function getJSON(path) { const r = await fetch(path, { cache: "no-cache" }); if (!r.ok) throw new Error(r.status); return r.json(); }

const VIEWS = { feed: "feed-view", detail: "detail-view", trends: "trends-view",
  factchecks: "factchecks-view", topics: "topics-view", faq: "faq-view" };
const TABS = ["feed", "trends", "factchecks", "topics", "faq"];
function setTab(w) { for (const t of TABS) document.getElementById("tab-" + t).classList.toggle("active", w === t); }
function show(v) {
  for (const [key, id] of Object.entries(VIEWS))
    document.getElementById(id).style.display = key === v ? "block" : "none";
  window.scrollTo({ top: 0, behavior: "instant" });
}
function showFeed() { show("feed"); setTab("feed"); }
function showTopics() { show("topics"); setTab("topics"); renderTopics(); }
function showTrends() { show("trends"); setTab("trends"); renderTrends(); }
function showFactchecks() { show("factchecks"); setTab("factchecks"); renderFactchecks(); }
function showFaq() { show("faq"); setTab("faq"); renderFaq(); }

function credBadge(c) {
  if (!c) return "";
  let out = `<span class="cstatus ${CRED_CLS[c.level] || "st-neutral"}">${CRED_FA[c.level] || ""}</span>`;
  if (c.needs_verification) out += `<span class="cstatus st-warn">نیازمند راستی‌آزمایی</span>`;
  return out;
}
function fcBadge(f) {
  return f ? `<span class="cstatus st-ok fc-badge">✓ فکت‌نامه</span>` : "";
}

function feedCard(s) {
  const imp = impInfo(s.importance_score);
  const badges = (s.source_names || []).slice(0, 4).map(x => `<span class="src-badge">${esc(x)}</span>`).join("");
  return `<button class="card" onclick="openStory('${s.id}')">
    <div class="meta"><span class="chip">${CAT_FA[s.category] || "خبر"}</span>
      <span class="dot"></span><span class="muted">${relTime(s.published_at)}</span>
      <span class="imp ${imp.cls}"><span class="bars"><i></i><i></i><i></i></span><span class="lbl">${imp.lbl}</span></span></div>
    <h2>${esc(s.headline_fa || "")}</h2>
    <p class="kalam">${esc(s.summary_fa || "")}</p>
    <div class="foot"><span class="sources-mini">${faN(s.source_count || 0)} منبع:</span>${badges}
      <span class="cred-row">${credBadge(s.credibility)}${fcBadge(s.factcheck)}</span></div>
  </button>`;
}

async function loadFeed() {
  const el = document.getElementById("feed");
  try {
    const items = await getJSON(`${DATA}/stories.json`);
    if (!items.length) { el.innerHTML = `<div class="state"><div class="big">هنوز خبری منتشر نشده</div></div>`; return; }
    el.innerHTML = items.map(feedCard).join("");
  } catch (e) {
    el.innerHTML = `<div class="state"><div class="big">خبرها بارگذاری نشد</div></div>`;
  }
}

async function openStory(id) {
  show("detail"); setTab("feed");
  const v = document.getElementById("detail-view");
  v.innerHTML = `<div class="spinner"></div>`;
  let s;
  try { s = await getJSON(`${DATA}/story/${id}.json`); }
  catch (e) { v.innerHTML = `<div class="state"><div class="big">خبر بارگذاری نشد</div></div>`; return; }

  const imp = impInfo(s.importance_score);
  const li = a => (a || []).map(x => `<li>${esc(x)}</li>`).join("");
  const views = (s.source_views || []).map(sv => `<div class="view"><div class="v-h"><span class="v-name">${esc(sv.source_name)}</span></div><p>${esc(sv.viewpoint_fa || "")}</p></div>`).join("");
  const cites = (s.sources || []).map(c => `<a class="cite" href="${c.article_url || "#"}" target="_blank" rel="noopener">
      <div class="c-body"><div class="c-src">${esc(c.source_name)}</div><div class="c-title">${esc(c.original_headline || "")}</div></div>
      <span class="c-time">${relTime(c.published_at)}</span>
      <span class="ext"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17 17 7M8 7h9v9"/></svg></span></a>`).join("");
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

  const chips = (s.asks || []).map((a, i) => `<button class="qchip" onclick="showAsk(${i})">${esc(a.q)}</button>`).join("");
  window._asks = s.asks || [];

  v.innerHTML = `
    <button class="back" onclick="showFeed()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg> بازگشت به خط خبری</button>
    <div class="d-head"><div class="meta"><span class="chip">${CAT_FA[s.category] || "خبر"}</span><span class="dot"></span><span class="muted">${relTime(s.published_at)}</span></div>
      <h1>${esc(s.headline_fa || "")}</h1>
      <div class="d-meta"><span class="imp ${imp.cls}"><span class="bars"><i></i><i></i><i></i></span><span class="lbl">${imp.lbl}</span></span>
        <span class="dot"></span><span class="muted">${faN(s.source_count || 0)} منبع</span>
        <span class="dot"></span><span class="muted">${IRAN_FA[s.iran_relevance] || ""}</span></div></div>
    <div class="kalam-box"><span class="eyebrow">جان‌کلام <span class="ai">ترکیب هوش مصنوعی</span></span><p>${esc(s.summary_fa || "")}</p></div>
    <div class="twocol"><div class="qa"><h3>چه اتفاقی افتاد؟</h3><p>${esc(s.what_happened_fa || "—")}</p></div>
      <div class="qa"><h3>چرا اهمیت دارد؟</h3><p>${esc(s.why_it_matters_fa || "—")}</p></div></div>
    ${known}
    ${cred}
    <div class="layers"><h3 class="section-h">منابع چه می‌گویند <span class="n">دیدگاه هر منبع، جدا از واقعیت</span></h3><div class="views">${views || '<p class="muted">—</p>'}</div>${consensus}</div>
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
    const [t, prices] = await Promise.all([
      getJSON(`${DATA}/trends.json`),
      getJSON(`${DATA}/prices.json`).catch(() => []),
    ]);
    const priceRows = (prices || []).map(p => {
      const cls = p.dir === "up" ? "up" : p.dir === "down" ? "down" : "flat";
      const arrow = p.dir === "up" ? "▲" : p.dir === "down" ? "▼" : "—";
      return `<div class="price"><div class="p-label">${esc(p.label_fa)}</div>
        <div class="p-val">${faN(grp(p.value))} <span class="p-unit">${esc(p.unit_fa)}</span></div>
        <div class="p-chg ${cls}">${arrow} ${faN(Math.abs(p.dp || 0))}٪</div></div>`;
    }).join("");
    const priceBoard = (prices && prices.length) ? `
      <div class="rule" style="margin-top:0"><span>نرخِ لحظه‌ای بازار</span><span class="l"></span></div>
      <div class="price-grid">${priceRows}</div>
      <p class="muted" style="margin:2px 0 8px">منبع نرخ‌ها: tgju — هر ساعت به‌روز می‌شود.</p>` : "";
    const topics = (t.topics || []);
    const bars = topics.map(tp => `<div class="vbar"><div class="vb-name">${esc(tp.name_fa)}</div>
      <div class="vb-track"><div class="vb-fill" style="width:${Math.max(6, tp.pct)}%"></div></div>
      <div class="vb-num">${faN(tp.story_count)} خبر</div></div>`).join("");
    const hot = (t.hottest || []).map(h => `<div class="ticker" onclick="openStory('${h.id}')" style="cursor:pointer">
      <span class="t-name">${esc(h.headline_fa)}<span class="t-cat">${CAT_FA[h.category] || ""}</span></span>
      <span class="t-val">${faN(h.source_count)}</span>
      <span class="t-chg tx-up"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M12 5v14M6 11l6-6 6 6" stroke-linecap="round" stroke-linejoin="round"/></svg>منبع</span></div>`).join("");
    el.innerHTML = `
      ${priceBoard}
      <div class="tx-hero"><span class="val">${faN(t.story_total || 0)}</span><span class="lbl">خبرِ فعال روی تخته</span>
        <span class="spacer" style="flex:1"></span><span class="lbl">${faN(topics.length)} موضوع فعال</span></div>
      <div class="rule"><span>داغ‌ترین موضوع‌ها</span><span class="l"></span></div>
      <div class="bars-block">${bars || '<p class="muted">—</p>'}</div>
      <div class="rule" style="margin-top:26px"><span>پرپوشش‌ترین خبرها</span><span class="l"></span></div>
      <div class="tickers">${hot || '<p class="muted">—</p>'}</div>
      <p class="muted" style="margin-top:18px">«پوشش» یعنی چند منبعِ مستقل یک خبر را گزارش کرده‌اند. هرچه بیشتر، خبر داغ‌تر.</p>`;
    _trendsLoaded = true;
  } catch (e) {
    el.innerHTML = `<div class="state"><div class="big">بورس اخبار بارگذاری نشد</div></div>`;
  }
}

/* ---- راستی‌آزمایی‌ها (Factnameh) ---- */
let _fcLoaded = false;
async function renderFactchecks() {
  if (_fcLoaded) return;
  const el = document.getElementById("factchecks");
  try {
    const items = await getJSON(`${DATA}/factchecks.json`);
    if (!items.length) {
      el.innerHTML = `<div class="state"><div class="big">فعلاً راستی‌آزمایی تازه‌ای در دسترس نیست</div><p class="muted">این بخش با هر به‌روزرسانی از فکت‌نامه تازه می‌شود.</p></div>`;
      _fcLoaded = true; return;
    }
    el.innerHTML = `<div class="feed">` + items.map(f => `<a class="card fc-card" href="${f.url}" target="_blank" rel="noopener">
      <div class="meta"><span class="chip">فکت‌نامه</span><span class="dot"></span><span class="muted">${esc((f.published || "").slice(0, 10))}</span>
        <span class="ext" style="margin-inline-start:auto"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17 17 7M8 7h9v9"/></svg></span></div>
      <h2>${esc(f.title)}</h2>
      ${f.summary ? `<p class="kalam">${esc(f.summary)}</p>` : ""}</a>`).join("") + `</div>
      <p class="muted" style="margin-top:14px">منبع: فکت‌نامه — راستی‌آزماییِ مستقل و حرفه‌ای. برای متن کامل روی هر مورد بزن.</p>`;
    _fcLoaded = true;
  } catch (e) {
    el.innerHTML = `<div class="state"><div class="big">راستی‌آزمایی‌ها بارگذاری نشد</div></div>`;
  }
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

let followed = new Set();
try { const s = localStorage.getItem("jk_follows"); if (s) followed = new Set(JSON.parse(s)); } catch (e) {}
async function renderTopics() {
  const el = document.getElementById("topic-grid");
  try {
    const topics = await getJSON(`${DATA}/topics.json`);
    el.innerHTML = topics.map(t => {
      const on = followed.has(t.id);
      return `<div class="topic"><div class="t-body"><div class="t-fa">${esc(t.name_fa)}</div><div class="t-en">${esc(t.name_en || "")}</div></div>
        <button class="followbtn ${on ? "on" : ""}" onclick="toggleFollow('${t.id}')">${on ? "دنبال‌شده" : "دنبال کردن"}</button></div>`;
    }).join("");
  } catch (e) { el.innerHTML = `<div class="state"><div class="big">موضوعات بارگذاری نشد</div></div>`; }
}
function toggleFollow(id) {
  followed.has(id) ? followed.delete(id) : followed.add(id);
  try { localStorage.setItem("jk_follows", JSON.stringify([...followed])); } catch (e) {}
  renderTopics();
}

const root = document.documentElement;
document.getElementById("theme").addEventListener("click", () => {
  const cur = root.getAttribute("data-theme"), sysDark = matchMedia("(prefers-color-scheme:dark)").matches;
  root.setAttribute("data-theme", (cur === "dark" || (!cur && sysDark)) ? "light" : "dark");
});
if ("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));

// build time (optional data/meta.json)
getJSON(`${DATA}/meta.json`).then(m => { if (m.built) document.getElementById("built").textContent = "به‌روزرسانی: " + m.built; }).catch(() => {});
loadFeed();
