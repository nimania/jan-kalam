/* Pendar is the primary home for public figure profiles and quote archives. */
(() => {
  const DIRECTORY = "https://pendar.io/figures/directory/";
  const PROFILES = {
    "مهدی تدینی":"https://pendar.io/@mehdi-tadini/",
    "احمد زیدآبادی":"https://pendar.io/@ahmadzeidabad/",
    "عباس سوری":"https://pendar.io/@abbas-souri/",
    "عباس عبدی":"https://pendar.io/@abdiabbas/",
    "عباس آخوندی":"https://pendar.io/@abbas-akhoundi/",
    "محمد فاضلی":"https://pendar.io/@fazeli-mohammad/",
    "میلاد دخانچی":"https://pendar.io/@miladdokhanchi/",
    "سجاد فتاحی":"https://pendar.io/@sajjad-fattahi/",
    "علی میرزامحمدی":"https://pendar.io/@iransocialproblems/",
    "حمید رسایی":"https://pendar.io/@rasaee/",
    "صادق زیباکلام":"https://pendar.io/@sadeghzibakalam/",
    "پروانه سلحشوری":"https://pendar.io/@parvanehsalahshouri/",
    "سعید حجاریان":"https://pendar.io/@saeedhajarian/",
    "مصطفی تاجزاده":"https://pendar.io/@mostafatajzadeh/",
    "حشمت‌الله فلاحت‌پیشه":"https://pendar.io/@dr-hfalahatpisheh/",
    "عمادالدین باقی":"https://pendar.io/@emadbaghi/",
    "محسن برهانی":"https://pendar.io/@m-borhani57/",
    "وحید اشتری":"https://pendar.io/@ghabl-enghelab/",
    "امیرحسین ثابتی":"https://pendar.io/@sabety-ir/",
    "وحید یامین‌پور":"https://pendar.io/@yaminpour/",
    "علی قلهکی":"https://pendar.io/@ali-gholhaky/",
    "مالک شریعتی نیاسر":"https://pendar.io/@malekshariati-ir/",
    "سید هادی کسایی‌زاده":"https://pendar.io/@kasaeizade/",
    "حسن عباسی":"https://pendar.io/@hasanabbasi-students/",
    "علی علیزاده":"https://pendar.io/@ali-alizadeh/",
    "علی بندری":"https://pendar.io/@ali-bandari/",
    "جمشید چالنگی":"https://pendar.io/@jamshid-chalangi/",
    "بزرگمهر شرف‌الدین":"https://pendar.io/@bozorgmehr-sharafedin/",
    "احسان منصوری":"https://pendar.io/@ehsan-mansoori/",
    "اشکان زارع":"https://pendar.io/@ashkan-zare/",
    "علی عبدی":"https://pendar.io/@ali-abdi/",
    "آرش نعل‌چگر":"https://pendar.io/@arash-nalchegar/"
  };
  const normalize = value => String(value || "")
    .normalize("NFKC").replace(/[\u200c\sـ]/g, "")
    .replace(/[ي]/g, "ی").replace(/[ك]/g, "ک")
    .replace(/[أإآ]/g, "ا").replace(/[ۀة]/g, "ه");
  const profileIndex = new Map(Object.entries(PROFILES).map(([name, url]) => [normalize(name), url]));
  const profileForName = name => profileIndex.get(normalize(name)) || DIRECTORY;
  const go = url => { window.location.href = url; };
  async function profileForHandle(handle) {
    const key = String(handle || "").toLowerCase();
    try {
      const d = typeof loadFigures === "function" ? await loadFigures() : null;
      const f = (d?.figures || []).find(x => String(x.handle || "").toLowerCase() === key);
      if (f?.name_fa) return profileForName(f.name_fa);
      const n = typeof loadNewsPeople === "function" ? await loadNewsPeople() : null;
      const news = (n?.figures || []).find(x => String(x.handle || "").toLowerCase() === key);
      if (news?.name_fa) return profileForName(news.name_fa);
    } catch (_) {}
    return profileForName(handle);
  }
  window.showFigures = () => go(DIRECTORY);
  window.openFigure = async handle => go(await profileForHandle(handle));
  window.openNewsPerson = window.openFigure;
  window.openFigureByName = async name => go(profileForName(name));
  window.openStatement = async id => {
    try {
      const raw = decodeURIComponent(String(id || ""));
      const d = typeof loadFigures === "function" ? await loadFigures() : null;
      for (const f of (d?.figures || [])) {
        const post = (f.posts || []).find(x => String(x.id) === raw);
        if (post) return go(profileForName(f.name_fa));
      }
    } catch (_) {}
    go(DIRECTORY);
  };
  function makeLink(node, name) {
    const a = document.createElement("a");
    a.className = node.className || "";
    a.href = profileForName(name);
    a.innerHTML = node.innerHTML;
    a.setAttribute("aria-label", (name || "چهره") + " — صفحه و گفته‌ها در پندار");
    node.replaceWith(a);
  }
  function linkFigureControls() {
    document.querySelectorAll("button.fig-person").forEach(node => {
      const name = node.querySelector(".fp-name")?.textContent?.trim();
      if (name) makeLink(node, name);
    });
    document.querySelectorAll("button.story-person-main").forEach(node => {
      const name = node.querySelector(".story-person-name,.fp-name,.v-name")?.textContent?.trim()
        || node.textContent.trim().split("\n")[0];
      if (name) makeLink(node, name);
    });
    document.querySelectorAll("a.v-name,a.x-figure-name").forEach(node => {
      const name = node.textContent.trim();
      if (name && node.getAttribute("href")?.startsWith("#/figure/")) node.href = profileForName(name);
    });
    document.querySelectorAll(".x-figure-actions button").forEach(node => {
      if (!/پروفایل/.test(node.textContent)) return;
      const name = node.closest(".x-figure-content")?.querySelector(".x-figure-name")?.textContent?.trim();
      if (name) makeLink(node, name);
    });
  }
  linkFigureControls();
  new MutationObserver(linkFigureControls).observe(document.body, { childList: true, subtree: true });
})();
