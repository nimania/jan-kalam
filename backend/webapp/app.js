/* جان‌کلام — web app (v1). Talks to the live backend at /api/v1. */
const API = window.JK_API || "/api/v1";

// --- device identity (anonymous, for follows) ---
function deviceId() {
  let id;
  try { id = localStorage.getItem("jk_device"); } catch (e) {}
  if (!id) {
    id = "dev-" + Math.random().toString(36).slice(2, 10);
    try { localStorage.setItem("jk_device", id); } catch (e) {}
  }
  return id;
}

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json", "X-User-Id": deviceId() },
    ...opts,
  });
  if (!res.ok) throw new Error("http_" + res.status);
  return res.json();
}

// --- labels ---
const CAT_FA = { iran: "ایران", world: "جهان", politics: "سیاست", economy: "اقتصاد",
  technology: "فناوری", ai: "هوش مصنوعی", culture: "فرهنگ" };
const IRAN_FA = { high: "ارتباط بالا با ایران", medium: "ارتباط با ایران",
  low: "ارتباط کم با ایران", none: "بدون ارتباط مستقیم با ایران" };
const faN = s => String(s).replace(".", "٫").replace(/\d/g, d => "۰۱۲۳۴۵۶۷۸۹"[d]);

function impInfo(score) {
  if (score >= 75) return { cls: "high", lbl: "بسیار مهم" };
  if (score >= 50) return { cls: "mid", lbl: "مهم" };
  return { cls: "low", lbl: "متوسط" };
}

function relTime(iso) {
  if (!iso) return "";
  const d = new Date(iso), now = new Date();
  const h = Math.floor((now - d) / 3.6e6);
  if (h < 1) return "همین حالا";
  if (h < 24) return faN(h) + " ساعت پیش";
  const days = Math.floor(h / 24);
  if (days === 1) return "دیروز";
  return faN(days) + " روز پیش";
}

// --- view switching ---
function setTab(which) {
  for (const t of ["feed", "topics"]) {
    const el = document.getElementById("tab-" + t);
    if (el) el.classList.toggle("active", which === t);
  }
}
function show(view) {
  document.getElementById("feed-view").style.display = view === "feed" ? "block" : "none";
  document.getElementById("detail-view").style.display = view === "detail" ? "block" : "none";
  document.getElementById("topics-view").style.display = view === "topics" ? "block" : "none";
  window.scrollTo({ top: 0, behavior: "instant" });
}
function showFeed() { show("feed"); setTab("feed"); }
function showTopics() { show("topics"); setTab("topics"); renderTopics(); }

// --- feed ---
function feedCard(s) {
  const imp = impInfo(s.importance_score);
  const badges = (s.source_names || []).slice(0, 4)
    .map(x => `<span class="src-badge">${esc(x)}</span>`).join("");
  return `<button class="card" onclick="openStory('${s.id}')">
    <div class="meta">
      <span class="chip">${CAT_FA[s.category] || "خبر"}</span>
      <span class="dot"></span><span class="muted">${relTime(s.published_at)}</span>
      <span class="imp ${imp.cls}"><span class="bars"><i></i><i></i><i></i></span>
        <span class="lbl">${imp.lbl}</span></span>
    </div>
    <h2>${esc(s.headline_fa || "")}</h2>
    <p class="kalam">${esc(s.summary_fa || "")}</p>
    <div class="foot"><span class="sources-mini">${faN(s.source_count || 0)} منبع:</span>${badges}</div>
  </button>`;
}

async function loadFeed() {
  const el = document.getElementById("feed");
  try {
    const data = await api("/stories?limit=30");
    setOffline(false);
    if (!data.items || !data.items.length) {
      el.innerHTML = `<div class="state"><div class="big">هنوز خبری منتشر نشده</div>
        <p>خط پردازش را اجرا کن تا خبرها ساخته شوند:</p>
        <p><code>POST /api/v1/admin/ingest → cluster → rank → synthesize</code></p></div>`;
      return;
    }
    el.innerHTML = data.items.map(feedCard).join("");
  } catch (e) {
    setOffline(true);
    el.innerHTML = `<div class="state"><div class="big">به سرور وصل نشد</div>
      <p>مطمئن شو بک‌اند در حال اجراست: <code>uvicorn app.main:app</code></p></div>`;
  }
}

// --- story detail ---
async function openStory(id) {
  show("detail"); setTab("feed");
  const v = document.getElementById("detail-view");
  v.innerHTML = `<button class="back" onclick="showFeed()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
      بازگشت به خط خبری</button><div class="spinner"></div>`;
  let s;
  try { s = await api("/stories/" + id); }
  catch (e) { v.innerHTML = `<div class="state"><div class="big">خبر بارگذاری نشد</div></div>`; return; }

  const imp = impInfo(s.importance_score);
  const li = a => a.map(x => `<li>${esc(x)}</li>`).join("");
  const views = (s.source_views || []).map(sv => `<div class="view">
      <div class="v-h"><span class="v-name">${esc(sv.source_name)}</span></div>
      <p>${esc(sv.viewpoint_fa || "")}</p></div>`).join("");
  const cites = (s.sources || []).map(c => `<a class="cite" href="${c.article_url || "#"}" target="_blank" rel="noopener">
      <div class="c-body"><div class="c-src">${esc(c.source_name)}</div>
        <div class="c-title">${esc(c.original_headline || "")}</div></div>
      <span class="c-time">${relTime(c.published_at)}</span>
      <span class="ext"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17 17 7M8 7h9v9"/></svg></span>
    </a>`).join("");

  const known = (s.facts && s.facts.length) || (s.uncertainties && s.uncertainties.length) ? `
    <div class="layers"><h3 class="section-h">واقعیت در برابر ابهام</h3>
      <div class="know">
        <div class="panel fact"><div class="p-h"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M20 6 9 17l-5-5"/></svg> آنچه معلوم است</div>
          <ul>${li(s.facts || [])}</ul></div>
        <div class="panel warn"><div class="p-h"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.2 2.4c-.7.3-1.2.8-1.2 1.6v.3M12 17h.01"/></svg> آنچه هنوز نامشخص است</div>
          <ul>${li(s.uncertainties || [])}</ul></div>
      </div></div>` : "";

  const consensus = (s.agreements && s.agreements.length) || (s.disagreements && s.disagreements.length) ? `
      <div class="consensus">
        <div class="cbox ag"><h4>نقطهٔ اشتراک</h4><p>${esc((s.agreements || [])[0] || "—")}</p></div>
        <div class="cbox dis"><h4>نقطهٔ اختلاف</h4><p>${esc((s.disagreements || [])[0] || "—")}</p></div>
      </div>` : "";

  v.innerHTML = `
    <button class="back" onclick="showFeed()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
      بازگشت به خط خبری</button>
    <div class="d-head">
      <div class="meta"><span class="chip">${CAT_FA[s.category] || "خبر"}</span>
        <span class="dot"></span><span class="muted">${relTime(s.published_at)}</span></div>
      <h1>${esc(s.headline_fa || "")}</h1>
      <div class="d-meta"><span class="imp ${imp.cls}"><span class="bars"><i></i><i></i><i></i></span>
          <span class="lbl">${imp.lbl}</span></span>
        <span class="dot"></span><span class="muted">${faN(s.source_count || 0)} منبع</span>
        <span class="dot"></span><span class="muted">${IRAN_FA[s.iran_relevance] || ""}</span></div>
    </div>
    <div class="kalam-box"><span class="eyebrow">جان‌کلام <span class="ai">ترکیب هوش مصنوعی</span></span>
      <p>${esc(s.summary_fa || "")}</p></div>
    <div class="twocol">
      <div class="qa"><h3>چه اتفاقی افتاد؟</h3><p>${esc(s.what_happened_fa || "—")}</p></div>
      <div class="qa"><h3>چرا اهمیت دارد؟</h3><p>${esc(s.why_it_matters_fa || "—")}</p></div>
    </div>
    ${known}
    <div class="layers"><h3 class="section-h">منابع چه می‌گویند <span class="n">دیدگاه هر منبع، جدا از واقعیت</span></h3>
      <div class="views">${views || '<p class="muted">—</p>'}</div>${consensus}</div>
    <div class="layers"><h3 class="section-h">منابع</h3><div class="cites">${cites}</div></div>
    <div class="ask"><div class="a-h"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" style="color:var(--accent)"><path d="M21 11.5a8.5 8.5 0 0 1-12.3 7.6L3 21l1.9-5.7A8.5 8.5 0 1 1 21 11.5Z" stroke-linejoin="round"/></svg> دربارهٔ این خبر بپرس</div>
      <p class="a-sub">پاسخ فقط از روی اطلاعات همین خبر ساخته می‌شود.</p>
      <div class="chips" id="ask-chips">
        ${["چرا این خبر مهم است؟", "ساده‌تر توضیح بده", "چه چیزی هنوز مشخص نیست؟"]
          .map(q => `<button class="qchip" onclick="askQ('${id}', this.textContent)">${q}</button>`).join("")}
      </div>
      <form class="ask-form" onsubmit="askSubmit(event,'${id}')">
        <input id="ask-input" placeholder="سؤالت را بنویس…" autocomplete="off">
        <button type="submit">بپرس</button>
      </form>
      <div class="answer" id="answer"><div class="a-bubble" id="a-bubble"></div>
        <div class="grounded"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M20 6 9 17l-5-5"/></svg>
          مبتنی بر منابع همین خبر</div></div>
    </div>`;
}

async function askQ(id, question) {
  document.querySelectorAll(".qchip").forEach(c => c.classList.remove("on"));
  const bubble = document.getElementById("a-bubble");
  document.getElementById("answer").classList.add("show");
  bubble.textContent = "…";
  try {
    const a = await api("/stories/" + id + "/ask", {
      method: "POST", body: JSON.stringify({ question }),
    });
    bubble.textContent = a.answer_fa + (a.note ? "  — " + a.note : "");
  } catch (e) { bubble.textContent = "پاسخ گرفته نشد."; }
}
function askSubmit(ev, id) {
  ev.preventDefault();
  const inp = document.getElementById("ask-input");
  const q = inp.value.trim();
  if (q) { askQ(id, q); inp.value = ""; }
}

// --- topics ---
let followed = new Set();
try { const s = localStorage.getItem("jk_follows"); if (s) followed = new Set(JSON.parse(s)); } catch (e) {}

async function renderTopics() {
  const el = document.getElementById("topic-grid");
  try {
    const topics = await api("/topics");
    if (!topics.length) { el.innerHTML = `<div class="state"><div class="big">موضوعی تعریف نشده</div></div>`; return; }
    el.innerHTML = topics.map(t => {
      const on = followed.has(t.id);
      return `<div class="topic"><div class="t-body">
          <div class="t-fa">${esc(t.name_fa)}</div>
          <div class="t-en">${esc(t.name_en || "")}</div></div>
        <button class="followbtn ${on ? "on" : ""}" onclick="toggleFollow('${t.id}')">
          ${on ? "دنبال‌شده" : "دنبال کردن"}</button></div>`;
    }).join("");
  } catch (e) {
    el.innerHTML = `<div class="state"><div class="big">موضوعات بارگذاری نشد</div></div>`;
  }
}
async function toggleFollow(id) {
  const on = followed.has(id);
  try {
    if (on) { await api("/topics/" + id + "/follow", { method: "DELETE" }); followed.delete(id); }
    else { await api("/topics/" + id + "/follow", { method: "POST" }); followed.add(id); }
    try { localStorage.setItem("jk_follows", JSON.stringify([...followed])); } catch (e) {}
    renderTopics();
  } catch (e) {}
}

// --- misc ---
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function setOffline(v) { document.getElementById("offline").classList.toggle("show", v); }

const root = document.documentElement, tbtn = document.getElementById("theme");
tbtn.addEventListener("click", () => {
  const cur = root.getAttribute("data-theme");
  const sysDark = matchMedia("(prefers-color-scheme:dark)").matches;
  root.setAttribute("data-theme", (cur === "dark" || (!cur && sysDark)) ? "light" : "dark");
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}

loadFeed();
