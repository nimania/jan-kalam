/* News archive and legacy links arriving from Pendar. */
const PENDAR_NEWS_DATA = "https://pendar.io/data/";
const NEWS_UUID = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
let _newsArchivePromise = null;
let _archiveQuery = "", _archiveCategory = "", _archiveLimit = 40;

function isPendarReport(story) {
  return !!(story?.editorial_report || story?.has_editorial_report);
}
async function pendarReportURL(id, story) {
  const reports = await getJSON("data/pendar-reports.json").catch(() => ({}));
  const url = reports[id];
  if (typeof url === "string" && url.startsWith("https://pendar.io/story/")) return url;
  return isPendarReport(story) ? "https://pendar.io/story/" + encodeURIComponent(id) + "/" : "";
}
async function resolveNewsId(raw) {
  const value = String(raw || "").trim();
  if (NEWS_UUID.test(value)) return value.toLowerCase();
  const aliases = await getJSON("data/story-permalinks.json").catch(() => ({}));
  return aliases.slug_to_id?.[value] || value;
}
async function loadMissingNewsStory(key, snapshot, timeoutMs) {
  const id = key.slice(6, -5);
  if (!key.startsWith("story/") || !key.endsWith(".json") || !NEWS_UUID.test(id)) {
    throw new Error("Missing snapshot data: " + key);
  }
  // A fresh Pendar link may precede the next Jan Kalam publication. Read only
  // that public JSON record; never send readers back into a redirect loop.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(PENDAR_NEWS_DATA + key, {
      mode: "cors", credentials: "omit", cache: "no-cache", signal: controller.signal
    });
    if (!response.ok) throw new Error("HTTP " + response.status);
    const story = await response.json();
    if (String(story?.id || "").toLowerCase() !== id.toLowerCase()) throw new Error("Story identity mismatch");
    snapshot[key] = story;
    return story;
  } finally { clearTimeout(timer); }
}
async function loadNewsArchive() {
  if (!_newsArchivePromise) {
    _newsArchivePromise = Promise.all([
      getJSON("data/news-archive.json").catch(() => getJSON("data/stories.json")),
      getJSON("data/pendar-reports.json").catch(() => ({}))
    ]).then(([rows, reports]) => (Array.isArray(rows) ? rows : [])
      .filter(row => NEWS_UUID.test(String(row?.id || "")) && !reports[row.id] && !isPendarReport(row)))
      .catch(error => { _newsArchivePromise = null; throw error; });
  }
  return _newsArchivePromise;
}
async function showNewsArchive(query = "") {
  show("newsarchive"); setTab("feed"); setHash("#/archive");
  document.title = "آرشیو و جست‌وجوی خبرها | جان‌کلام";
  _archiveQuery = String(query || ""); _archiveCategory = ""; _archiveLimit = 40;
  document.getElementById("news-archive-query").value = _archiveQuery;
  document.getElementById("news-archive-category").value = "";
  await renderNewsArchive();
}
function filterNewsArchive(query, category) {
  _archiveQuery = String(query || ""); _archiveCategory = category || ""; _archiveLimit = 40;
  renderNewsArchive();
}
async function renderNewsArchive() {
  const host = document.getElementById("news-archive-feed");
  try {
    const rows = await loadNewsArchive();
    const normalize = value => String(value || "").toLowerCase().replace(/ي/g,"ی").replace(/ك/g,"ک").replace(/‌/g," ");
    const terms = normalize(_archiveQuery).split(/\s+/).filter(Boolean);
    const visible = rows.filter(row => (!_archiveCategory || row.category === _archiveCategory) &&
      terms.every(term => normalize([row.headline_fa, row.summary_fa, ...(row.source_names || [])].join(" ")).includes(term)))
      .sort((a,b) => String(b.published_at || "").localeCompare(String(a.published_at || "")));
    document.getElementById("news-archive-count").textContent = faN(visible.length) + " خبر";
    host.innerHTML = visible.slice(0, _archiveLimit).map(feedCard).join("") || '<p class="muted">خبری با این مشخصات پیدا نشد.</p>';
    document.getElementById("news-archive-more").hidden = visible.length <= _archiveLimit;
  } catch (_) { host.innerHTML = '<p>آرشیو بارگذاری نشد. <button onclick="renderNewsArchive()">تلاش دوباره</button></p>'; }
}
function moreNewsArchive() { _archiveLimit += 40; renderNewsArchive(); }
async function openNewsEvent(id) {
  if (String(id).startsWith("editorial-")) {
    location.replace("https://pendar.io/event/" + encodeURIComponent(id) + "/");
    return;
  }
  const anchor = String(id).replace(/^event-/, "");
  if (NEWS_UUID.test(anchor)) return openStory(anchor);
  return showNewsArchive(String(id));
}
