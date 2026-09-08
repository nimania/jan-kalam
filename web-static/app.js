/* جان‌کلام — static build. Reads pre-generated JSON from ./data (no backend). */
const DATA = "data";

const CAT_FA = { iran: "ایران", world: "جهان", politics: "سیاست", economy: "اقتصاد",
  technology: "فناوری", ai: "هوش مصنوعی", culture: "فرهنگ" };
const IRAN_FA = { high: "ارتباط بالا با ایران", medium: "ارتباط با ایران",
  low: "ارتباط کم با ایران", none: "بدون ارتباط مستقیم با ایران" };
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

function setTab(w) { for (const t of ["feed", "topics"]) document.getElementById("tab-" + t).classList.toggle("active", w === t); }
function show(v) {
  document.getElementById("feed-view").style.display = v === "feed" ? "block" : "none";
  document.getElementById("detail-view").style.display = v === "detail" ? "block" : "none";
  document.getElementById("topics-view").style.display = v === "topics" ? "block" : "none";
  window.scrollTo({ top: 0, behavior: "instant" });
}
function showFeed() { show("feed"); setTab("feed"); }
function showTopics() { show("topics"); setTab("topics"); renderTopics(); }

function feedCard(s) {
  const imp = impInfo(s.importance_score);
  const badges = (s.source_names || []).slice(0, 4).map(x => `<span class="src-badge">${esc(x)}</span>`).join("");
  return `<button class="card" onclick="openStory('${s.id}')">
    <div class="meta"><span class="chip">${CAT_FA[s.category] || "خبر"}</span>
      <span class="dot"></span><span class="muted">${relTime(s.published_at)}</span>
      <span class="imp ${imp.cls}"><span class="bars"><i></i><i></i><i></i></span><span class="lbl">${imp.lbl}</span></span></div>
    <h2>${esc(s.headline_fa || "")}</h2>
    <p class="kalam">${esc(s.summary_fa || "")}</p>
    <div class="foot"><span class="sources-mini">${faN(s.source_count || 0)} منبع:</span>${badges}</div>
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
