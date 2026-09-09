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
  const mins = Math.floor((Date.now() - new Date(iso)) / 6e4);
  if (mins < 1) return "همین حالا";
  if (mins < 60) return faN(mins) + " دقیقه پیش";
  const h = Math.floor(mins / 60);
  if (h < 24) return faN(h) + " ساعت پیش";
  const d = Math.floor(h / 24);
  return d === 1 ? "دیروز" : faN(d) + " روز پیش";
}
async function getJSON(path) { const r = await fetch(path, { cache: "no-cache" }); if (!r.ok) throw new Error(r.status); return r.json(); }

const VIEWS = { feed: "feed-view", detail: "detail-view", trends: "trends-view",
  factchecks: "factchecks-view", topics: "topics-view", topicarchive: "topic-archive-view",
  weather: "weather-view", iran: "iran-view", faq: "faq-view", market: "market-view" };
const TABS = ["feed", "trends", "factchecks", "iran", "topics"];
const SCOPE_FA = { local: "استانی", national: "کشوری", international: "بین‌المللی" };
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
function geoBadge(g) {
  if (!g || !g.scope) return "";
  if (g.scope === "local") {
    const p = g.provinces && g.provinces[0];
    return `<span class="geo-badge local">${p ? esc(p.name_fa) : "استانی"}</span>`;
  }
  return `<span class="geo-badge ${g.scope}">${SCOPE_FA[g.scope] || ""}</span>`;
}

function feedCard(s) {
  const imp = impInfo(s.importance_score);
  const badges = (s.source_names || []).slice(0, 4).map(x => `<span class="src-badge clickable" data-src="${esc(x)}" onclick="event.stopPropagation();openSource(this.dataset.src)">${esc(x)}</span>`).join("");
  return `<button class="card" onclick="openStory('${s.id}')">
    <div class="meta"><span class="chip">${CAT_FA[s.category] || "خبر"}</span>
      <span class="dot"></span><span class="muted">${relTime(s.published_at)}</span>${geoBadge(s.geo)}${trendBadge(s.trend)}
      <span class="imp ${imp.cls}"><span class="bars"><i></i><i></i><i></i></span><span class="lbl">${imp.lbl}</span></span></div>
    <h2>${esc(s.headline_fa || "")}</h2>
    <p class="kalam">${esc(s.summary_fa || "")}</p>
    <div class="foot"><span class="sources-mini">${faN(s.source_count || 0)} منبع:</span>${badges}
      <span class="cred-row">${credBadge(s.credibility)}${fcBadge(s.factcheck)}${saveBtn(s.id)}</span></div>
  </button>`;
}

let ALL = [];
let tier = "all";
async function loadFeed() {
  const el = document.getElementById("feed");
  try {
    ALL = await getJSON(`${DATA}/stories.json`);
    renderFeed();
    updateFreshness();
  } catch (e) {
    el.innerHTML = `<div class="state"><div class="big">خبرها بارگذاری نشد</div></div>`;
  }
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
  if (sortMode === "new") items = items.slice().sort((a, b) => String(b.published_at || "").localeCompare(String(a.published_at || "")));
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
let sortMode = "imp";
function setSort(m) {
  sortMode = m;
  document.getElementById("sort-imp").classList.toggle("on", m === "imp");
  document.getElementById("sort-new").classList.toggle("on", m === "new");
  renderFeed();
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

  v.innerHTML = `
    <button class="back" onclick="showFeed()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg> بازگشت به خط خبری</button>
    <div class="d-head"><div class="meta"><span class="chip">${CAT_FA[s.category] || "خبر"}</span><span class="dot"></span><span class="muted">${relTime(s.published_at)}</span>${trendBadge(s.trend)}<span class="spacer" style="flex:1"></span>${saveBtn(s.id)}</div>
      <h1>${esc(s.headline_fa || "")}</h1>
      <div class="d-meta"><span class="imp ${imp.cls}"><span class="bars"><i></i><i></i><i></i></span><span class="lbl">${imp.lbl}</span></span>
        <span class="dot"></span><span class="muted">${faN(s.source_count || 0)} منبع</span>
        <span class="dot"></span><span class="muted">${IRAN_FA[s.iran_relevance] || ""}</span></div></div>
    <div class="kalam-box"><span class="eyebrow">جان‌کلام <span class="ai">ترکیب هوش مصنوعی</span></span><p>${esc(s.summary_fa || "")}</p></div>
    <div class="twocol"><div class="qa"><h3>چه اتفاقی افتاد؟</h3><p>${esc(s.what_happened_fa || "—")}</p></div>
      <div class="qa"><h3>چرا اهمیت دارد؟</h3><p>${esc(s.why_it_matters_fa || "—")}</p></div></div>
    ${known}
    ${cred}
    ${trendSec}
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
    if (!ALL.length) { try { ALL = await getJSON(`${DATA}/stories.json`); } catch (e) {} }
    const [t, st] = await Promise.all([
      getJSON(`${DATA}/trends.json`),
      getJSON(`${DATA}/stats.json`).catch(() => null),
    ]);
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
      return `<button class="tp-row" onclick="openTopic('${tp.slug}')">
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

function openTopic(slug) {
  show("topicarchive"); setTab("topics");
  document.getElementById("ta-back-t").textContent = "بازگشت به موضوعات";
  document.getElementById("ta-back").onclick = showTopics;
  const items = ALL.filter(s => (s.topics || []).some(t => t.slug === slug));
  const name = ((items[0] && items[0].topics.find(t => t.slug === slug)) || {}).name_fa || slug;
  document.getElementById("ta-title").textContent = "موضوع: " + name;
  document.getElementById("ta-sub").textContent = faN(items.length) + " خبر در این موضوع";
  document.getElementById("ta-feed").innerHTML = groupedFeed(items);
}

function followBar(kind, id, note) {
  return `<div class="follow-bar">${followBtn(kind, id, "در حال دنبال‌کردن", "دنبال کن")}<span class="fb-note">${esc(note)}</span></div>`;
}
function openSource(name) {
  if (!ALL.length) return;
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
function showIran() { show("iran"); setTab("iran"); renderIran(); }
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

// بازار — dedicated market page (full price board)
function showMarket() { show("market"); setTab("feed"); renderMarket(); }
async function renderMarket() {
  const el = document.getElementById("market");
  try {
    const prices = await getJSON(`${DATA}/prices.json`);
    if (!prices || !prices.length) { el.innerHTML = `<div class="state"><div class="big">نرخ‌ها در دسترس نیست</div></div>`; return; }
    const rows = prices.map(p => {
      const cls = p.dir === "up" ? "up" : p.dir === "down" ? "down" : "flat";
      const arrow = p.dir === "up" ? "▲" : p.dir === "down" ? "▼" : "—";
      return `<div class="price"><div class="p-label">${esc(p.label_fa)}</div>
        <div class="p-val">${faN(grp(p.value))} <span class="p-unit">${esc(p.unit_fa)}</span></div>
        <div class="p-chg ${cls}">${arrow} ${faN(Math.abs(p.dp || 0))}٪</div></div>`;
    }).join("");
    el.innerHTML = `<div class="price-grid">${rows}</div>
      <p class="muted" style="margin-top:14px">منبع نرخ‌ها: tgju — هر ساعت به‌روز می‌شود. مقادیر به تومان‌اند مگر آنکه واحدِ دیگری ذکر شده باشد.</p>`;
  } catch (e) { el.innerHTML = `<div class="state"><div class="big">بازار بارگذاری نشد</div></div>`; }
}

// weather — home strip (4 cities) + dedicated page
function showWeather() { show("weather"); setTab("feed"); renderWeather(); }
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
      + `</div><p class="muted" style="margin-top:14px">منبع: Open-Meteo — دمای کنونی و کمینه/بیشینهٔ امروز. هر ساعت به‌روز می‌شود.</p>`;
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
    r += `<rect class="bar" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="1.5"><title>${lbl}${faN(vals[i])} خبر</title></rect>`;
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
let FOLLOW = Object.assign({ topics: [], provinces: [], sources: [], saved: [] }, loadF());
function isF(kind, id) { return (FOLLOW[kind] || []).includes(id); }
function toggleF(kind, id) {
  const a = FOLLOW[kind] || (FOLLOW[kind] = []);
  const i = a.indexOf(id); if (i >= 0) a.splice(i, 1); else a.push(id);
  saveF();
}
function followCount() {
  return (FOLLOW.topics.length + FOLLOW.provinces.length + FOLLOW.sources.length);
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
    isF("saved", s.id));
}

/* ----- home stats strip ("نبض خبری") ----- */
async function renderHomeStats() {
  const el = document.getElementById("home-stats");
  if (!el) return;
  try {
    const st = await getJSON(`${DATA}/stats.json`);
    STATS = st;
    const roll = liveRolling(st);
    const daily = (st.activity_daily || []).map(x => x.n);
    el.innerHTML = `<button class="statbar" onclick="showTrends()">
      <span class="sb-item"><b>${faN(st.total || 0)}</b><span>کل خبرها</span></span>
      <span class="sb-sep"></span>
      <span class="sb-item"><b>${faN(st.calendar ? st.calendar.today : 0)}</b><span>امروز</span></span>
      <span class="sb-item"><b>${faN(roll.h24)}</b><span>۲۴ ساعت</span></span>
      <span class="sb-spark">${svgSpark(daily, { w: 90, h: 26 })}</span>
      <span class="sb-go">نبض خبری ›</span></button>`;
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
  const tiles = [
    ["۴ ساعت", roll.h4], ["۸ ساعت", roll.h8], ["۱۲ ساعت", roll.h12], ["۲۴ ساعت", roll.h24],
    ["امروز", cal.today || 0], ["دیروز", cal.yesterday || 0],
    ["این هفته", cal.this_week || 0], ["هفتهٔ پیش", cal.last_week || 0],
  ];
  const labels = daily.map(d => d.d.slice(5));
  return `
    <div class="stat-hero"><span class="val">${faN(st.total || 0)}</span><span class="lbl">کل خبرهای سیستم</span></div>
    <div class="stat-tiles">${tiles.map(t => `<div class="stile"><b>${faN(t[1])}</b><span>${t[0]}</span></div>`).join("")}</div>
    <div class="rule"><span>فعالیتِ ۱۴ روزِ گذشته</span><span class="l"></span></div>
    <div class="chart-wrap">${svgBars(daily.map(d => d.n), { labels, w: 320, h: 70 })}</div>
    <p class="muted" style="margin:6px 0 4px">شمارِ خبرهای تازه در هر روز. پنجره‌های «۴ تا ۲۴ ساعت» زنده‌اند و لحظه‌ای حساب می‌شوند.</p>`;
}

loadFeed();
renderHomeStats();
renderHomePrices();
renderHomeWeather();
updateMineBadge();
